// Run in Neo4j Aura Query after planning a live ride.
// This displays actual app-created relationships, not a seeded sample network.
MATCH (t:SvasTrip)-[:HAS_CANDIDATE]->(r:SvasRoute)
      -[:HAS_SAMPLE]->(s:SvasSample)-[:IN_ZONE]->(z:SvasZone)
MATCH (s)-[:USES_READING]->(a:SvasReading)
RETURN t, r, s, z, a
LIMIT 150;

// Explain the route decision to judges.
MATCH (t:SvasTrip)-[:HAS_CANDIDATE]->(r:SvasRoute)
RETURN t.id AS trip, r.option_id AS route,
       round(r.duration_seconds / 60.0, 1) AS minutes,
       round(r.average_aqi, 1) AS us_aqi,
       round(r.exposure_index, 1) AS aqi_minutes,
       round(r.routing_cost, 2) AS composite_cost
ORDER BY t.id, composite_cost;

// Show shared air-quality model cells affecting multiple candidates.
MATCH (r:SvasRoute)-[:HAS_SAMPLE]->(:SvasSample)-[:IN_ZONE]->(z:SvasZone)
RETURN z.id AS zone, count(DISTINCT r) AS affected_routes
ORDER BY affected_routes DESC;
