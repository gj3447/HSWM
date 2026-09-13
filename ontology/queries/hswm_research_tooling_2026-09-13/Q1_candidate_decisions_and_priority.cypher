MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)-[:REFERS_TO]->(c), (a)-[:HAS_CONCEPT]->(q)
WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' AND c.standard_graph_role = 'TOOL_CANDIDATE' AND q.standard_graph_role = 'QUALIFICATION'
RETURN a.candidate_id AS candidateId, c.name AS candidateName, a.decision AS decision, q.priority AS priority, q.id AS qualificationId, q.source_status AS qualificationStatus
ORDER BY candidateId
