MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)-[:PRESERVES]->(cap)
WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' AND cap.standard_graph_role = 'EXISTING_CAPABILITY'
RETURN a.candidate_id AS candidateId, a.decision AS decision, cap.id AS capabilityId, cap.name AS capabilityName
ORDER BY candidateId, capabilityId
