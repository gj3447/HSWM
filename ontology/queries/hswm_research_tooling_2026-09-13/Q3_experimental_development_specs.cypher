MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)-[:REFERS_TO]->(c)
WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' AND c.standard_graph_role = 'TOOL_CANDIDATE' AND a.decision = 'WATCH_EXPERIMENTAL'
RETURN a.candidate_id AS candidateId, c.name AS candidateName, c.standard_status AS standardStatus, c.verified_version AS observedVersion, a.decision AS decision
ORDER BY candidateId
