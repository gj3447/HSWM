// Read-only WP0–3 implementation scope; does not retrieve efficacy recommendations.
MATCH (b {uid:'sym:AbstractNode:hswm-ice-graph-implementation-wp0-3-2026-09-08-v1'})-[:HAS_CONCEPT]->(n)
RETURN n.uid AS uid,n.role AS role,n.status AS status,n.description AS description ORDER BY role,uid;
