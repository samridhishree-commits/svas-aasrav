// Run each block separately in the Neo4j Aura Query tool.
// Select the same database as NEO4J_DATABASE in your backend environment.

// 1. Recent completed-comparison logs, newest trip first.
MATCH (t:SvasTrip)-[:HAS_EVENT]->(e:SvasLog)
WHERE e.expires_at > datetime()
RETURN t.id AS comparison, e.sequence AS step, e.stage AS stage,
       e.message AS message, e.level AS level, e.recorded_at AS time
ORDER BY t.created_at DESC, e.sequence ASC
LIMIT 100;

// 2. Copy the Comparison reference from the dashboard and replace the value.
:param tripId => 'PASTE-COMPARISON-REFERENCE-HERE';

MATCH (t:SvasTrip {id:$tripId})-[:HAS_EVENT]->(e:SvasLog)
WHERE e.expires_at > datetime()
RETURN e.sequence AS step, e.stage AS stage, e.message AS message,
       e.level AS level, e.recorded_at AS time
ORDER BY step;

// 3. Graph view of one comparison's logs and route choices.
MATCH (t:SvasTrip {id:$tripId})-[relationship:HAS_EVENT|HAS_CANDIDATE]->(detail)
WHERE t.expires_at > datetime()
RETURN t, relationship, detail;

// 4. Expand the scoring graph for the same comparison.
MATCH path=(t:SvasTrip {id:$tripId})-[:HAS_CANDIDATE]->(:SvasRoute)
           -[:HAS_SAMPLE]->(:SvasSample)-[:USES_READING]->(:SvasReading)
WHERE t.expires_at > datetime()
RETURN path LIMIT 80;
