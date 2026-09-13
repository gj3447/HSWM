MATCH ({uid: 'sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13'})-[:HAS_CONCEPT]->(c)-[:HAS_CONCEPT]->(e)-[:HAS_SOURCE]->(s)
WHERE c.standard_graph_role = 'TOOL_CANDIDATE' AND e.standard_graph_role = 'ADOPTION_EVIDENCE' AND s.standard_graph_role = 'RESEARCH_SOURCE'
RETURN c.id AS candidateId, e.evidence_class AS evidenceClass, e.statement AS statement, s.source_file AS sourceFile, s.source_id AS sourceId, s.url AS sourceUrl, s.source_scope AS sourceScope
ORDER BY candidateId, sourceFile, sourceId
