"""Neo4j is the recommendation engine, not an optional logging sink.

OSRM retains responsibility for road topology. Cypher traverses each candidate's
sample/readings graph and ranks eligible routes by AQI-time exposure.
"""
import threading
from neo4j import GraphDatabase, Query
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from .errors import ServiceError

SAVE_QUERY = """
MERGE (t:Trip:SvasTrip {id: $trip_id})
SET t.created_at = datetime(), t.expires_at = datetime() + duration({minutes:$retention})
WITH t
UNWIND $routes AS route
MERGE (r:Route:SvasRoute {id: $trip_id + ':' + route.id})
SET r.option_id = route.id, r.duration_seconds = route.duration_seconds,
    r.expires_at = t.expires_at
MERGE (t)-[:HAS_CANDIDATE]->(r)
WITH t, r, route
UNWIND route.samples AS sample
MERGE (s:RouteSample:SvasSample {id: r.id + ':' + toString(sample.index)})
SET s.seconds = sample.seconds, s.sequence = sample.index, s.expires_at = t.expires_at
MERGE (r)-[:HAS_SAMPLE]->(s)
MERGE (z:AirZone:SvasZone {id: sample.zone_id})
SET z.location = point({latitude:sample.grid_lat, longitude:sample.grid_lng}),
    z.source = sample.source, z.station_name = sample.station_name, z.expires_at = t.expires_at
MERGE (s)-[:IN_ZONE]->(z)
MERGE (a:AQIReading:SvasReading {id:sample.reading_id})
SET a.aqi = sample.aqi, a.standard = 'US', a.observed_at = datetime(sample.observed_at),
    a.expires_at = t.expires_at
MERGE (z)-[:HAS_READING]->(a)
MERGE (s)-[:USES_READING]->(a)
"""

RANK_QUERY = """
MATCH (t:SvasTrip {id:$trip_id})-[:HAS_CANDIDATE]->(r:SvasRoute)
MATCH (r)-[:HAS_SAMPLE]->(s:SvasSample)-[:USES_READING]->(a:SvasReading)
WITH r, sum(s.seconds) AS sampled_seconds,
     sum(s.seconds * a.aqi) AS aqi_seconds,
     sum(CASE WHEN a.aqi > $threshold THEN s.seconds ELSE 0 END) AS high_aqi_seconds,
     max(a.aqi) AS max_sampled_aqi,
     min(a.observed_at) AS oldest_reading, count(s) AS sample_count
WITH r, sampled_seconds, aqi_seconds, high_aqi_seconds, max_sampled_aqi, oldest_reading, sample_count,
     aqi_seconds / sampled_seconds AS average_aqi,
     aqi_seconds / 60.0 AS routing_cost,
     r.duration_seconds <= $window * 60 AND ($mask OR high_aqi_seconds = 0)
       AND ($max_aqi IS NULL OR max_sampled_aqi < $max_aqi) AS eligible
SET r.routing_cost = routing_cost, r.average_aqi = average_aqi,
    r.exposure_index = aqi_seconds / 60.0, r.high_aqi_seconds = high_aqi_seconds,
    r.max_sampled_aqi = max_sampled_aqi
RETURN r.option_id AS id, average_aqi, aqi_seconds / 60.0 AS exposure_index,
       high_aqi_seconds, max_sampled_aqi, routing_cost, eligible, sample_count,
       toString(oldest_reading) AS observed_at
ORDER BY eligible DESC, exposure_index ASC, r.duration_seconds ASC
"""

SUMMARY_QUERY = """
MATCH (z:SvasZone)<-[:IN_ZONE]-(s:SvasSample)<-[:HAS_SAMPLE]-(r:SvasRoute)
MATCH (s)-[:USES_READING]->(a:SvasReading)
WHERE r.expires_at > datetime()
RETURN z.id AS id, z.location.latitude AS lat, z.location.longitude AS lng,
       z.source AS source, z.station_name AS station_name,
       max(a.aqi) AS aqi, count(DISTINCT r) AS affected_routes,
       toString(max(a.observed_at)) AS observed_at
ORDER BY affected_routes DESC, aqi DESC LIMIT 20
"""

SAVE_ACTIVITY_QUERY = """
MATCH (t:SvasTrip {id:$trip_id})
UNWIND $events AS event
MERGE (e:ActivityLog:SvasLog {id:$trip_id + ':' + toString(event.sequence)})
SET e.sequence=event.sequence, e.stage=event.stage, e.message=event.message,
    e.level=event.level, e.route_id=event.route_id,
    e.recorded_at=datetime(event.recorded_at), e.expires_at=t.expires_at
MERGE (t)-[:HAS_EVENT]->(e)
WITH e ORDER BY e.sequence
RETURN e.id AS id, e.sequence AS sequence, e.stage AS stage,
       e.message AS message, e.level AS level, e.route_id AS route_id,
       toString(e.recorded_at) AS recorded_at
"""

class Database:
    def __init__(self, settings):
        self.settings = settings
        self.driver = None
        self._schema_ready = False
        self._schema_lock = threading.Lock()
        if settings.neo4j_uri and settings.neo4j_password:
            try:
                self.driver = GraphDatabase.driver(settings.neo4j_uri,
                    auth=(settings.neo4j_username,settings.neo4j_password),
                    connection_timeout=10, connection_acquisition_timeout=15, max_transaction_retry_time=10)
            except (ValueError, Neo4jError):
                # Keep city AQI and health available even when database config needs fixing.
                self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def ensure_available(self):
        if self.driver is None:
            raise ServiceError('Set NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD in backend/.env.', 503, 'NEO4J_NOT_CONFIGURED')
        try:
            self.driver.verify_connectivity()
        except (Neo4jError, ServiceUnavailable, SessionExpired, OSError):
            raise ServiceError('Neo4j is unavailable. Check the database connection and credentials.', 503, 'NEO4J_UNAVAILABLE') from None

    def initialize(self):
        self.ensure_available()
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                with self.driver.session(database=self.settings.neo4j_database) as session:
                    for label in ['SvasTrip','SvasRoute','SvasSample','SvasZone','SvasReading','SvasLog']:
                        session.run(f'CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE').consume()
                self._schema_ready = True
            except (Neo4jError, ServiceUnavailable, SessionExpired):
                raise ServiceError('Neo4j schema setup failed. Check NEO4J_DATABASE and database write permissions.', 503, 'NEO4J_SCHEMA_FAILED') from None

    def rank_routes(self, trip_id, routes, request):
        self.initialize()
        def transaction(tx):
            # Only delete expired nodes owned by this app, never user road-network data.
            for label in ['SvasLog','SvasSample','SvasRoute','SvasTrip','SvasReading','SvasZone']:
                tx.run(f'MATCH (n:{label}) WHERE n.expires_at < datetime() DETACH DELETE n').consume()
            tx.run(SAVE_QUERY, trip_id=trip_id, routes=routes,
                retention=self.settings.graph_retention_minutes).consume()
            return tx.run(RANK_QUERY, trip_id=trip_id, threshold=self.settings.high_aqi_threshold,
                pollution_weight=self.settings.pollution_weight, window=request.delivery_window_minutes,
                mask=request.has_mask, max_aqi=request.max_aqi).data()
        try:
            with self.driver.session(database=self.settings.neo4j_database) as session:
                rows = session.execute_write(transaction)
            if len(rows) != len(routes):
                raise ServiceError('Neo4j could not score every route. No partial ranking was returned.', 503, 'INCOMPLETE_GRAPH')
            return rows
        except (Neo4jError, ServiceUnavailable, SessionExpired, OSError):
            raise ServiceError('Neo4j could not rank the routes. Check database permissions and connectivity.', 503, 'NEO4J_QUERY_FAILED') from None

    def save_activity(self, trip_id, events):
        try:
            with self.driver.session(database=self.settings.neo4j_database) as session:
                rows=session.execute_write(lambda tx:tx.run(SAVE_ACTIVITY_QUERY,trip_id=trip_id,events=events).data())
            if len(rows)!=len(events):
                raise ServiceError('The comparison log could not be saved completely.',503,'ACTIVITY_LOG_UNAVAILABLE')
            return rows
        except (Neo4jError, ServiceUnavailable, SessionExpired, OSError):
            raise ServiceError('The comparison log could not be saved.',503,'ACTIVITY_LOG_UNAVAILABLE') from None

    def summary(self):
        self.ensure_available()
        try:
            with self.driver.session(database=self.settings.neo4j_database) as session:
                return session.run(Query(SUMMARY_QUERY, timeout=10)).data()
        except (Neo4jError, ServiceUnavailable, SessionExpired):
            raise ServiceError('Neo4j zone summary is unavailable.', 503, 'NEO4J_QUERY_FAILED') from None
