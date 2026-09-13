MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)-[:REQUIRES]->(req), (a)-[:HAS_CONCEPT]->(q)
WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' AND req.standard_graph_role = 'RESEARCH_REQUIREMENT' AND q.standard_graph_role = 'QUALIFICATION'
RETURN req.id AS requirementId, a.candidate_id AS candidateId, q.id AS qualificationId, q.priority AS priority, q.trigger AS trigger, q.acceptance AS acceptance, q.source_status AS qualificationStatus
ORDER BY requirementId, candidateId, qualificationId
