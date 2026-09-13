MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(c)
WHERE c.standard_graph_role = 'TOOL_CANDIDATE' AND NOT EXISTS { MATCH (c)-[:HAS_SOURCE]->(s) WHERE s.standard_graph_role = 'RESEARCH_SOURCE' }
RETURN c.id AS itemId, 'CANDIDATE_WITHOUT_SOURCE' AS issue
UNION ALL
MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(c)
WHERE c.standard_graph_role = 'TOOL_CANDIDATE' AND NOT EXISTS { MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)-[:REFERS_TO]->(c) WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' }
RETURN c.id AS itemId, 'CANDIDATE_WITHOUT_ASSESSMENT' AS issue
UNION ALL
MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)
WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' AND NOT EXISTS { MATCH (a)-[:HAS_CONCEPT]->(q) WHERE q.standard_graph_role = 'QUALIFICATION' }
RETURN a.candidate_id AS itemId, 'ASSESSMENT_WITHOUT_QUALIFICATION' AS issue
UNION ALL
MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(req)
WHERE req.standard_graph_role = 'RESEARCH_REQUIREMENT' AND NOT EXISTS { MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(a)-[:REQUIRES]->(req) WHERE a.standard_graph_role = 'INTEGRATED_ASSESSMENT' }
RETURN req.id AS itemId, 'REQUIREMENT_WITHOUT_ASSESSMENT' AS issue
ORDER BY itemId, issue
