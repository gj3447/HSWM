MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->(obligation)
WHERE obligation.standard_graph_role = 'COVERAGE_OBLIGATION'
RETURN obligation.uid AS obligation_uid,
       obligation.obligation_id AS obligation_id,
       obligation.name AS obligation_name,
       obligation.design_status AS design_status,
       obligation.engineering_status AS engineering_status,
       obligation.formal_status AS formal_status,
       obligation.efficacy_status AS efficacy_status
ORDER BY obligation_id, obligation_uid
