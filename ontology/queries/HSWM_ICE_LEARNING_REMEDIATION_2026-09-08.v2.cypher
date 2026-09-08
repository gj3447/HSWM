// Read-only default retrieval for the corrected v2 design only.
MATCH (bundle {uid: 'sym:AbstractNode:hswm-ice-learning-remediation-2026-09-08-v2'})
MATCH (bundle)-[:HAS_CONCEPT]->(item)
WHERE item.status <> 'V1_INVALID_SEMANTIC_MAPPING_SUPERSEDED_BY_V2'
OPTIONAL MATCH (item)-[link:REQUIRES|TESTS|PRESERVES|SPECULATIVE_LINK|HAS_SOURCE]->(target)
RETURN item.uid AS uid, item.role AS role, item.status AS status,
       collect(DISTINCT {type:type(link), target:target.uid}) AS links
ORDER BY role, uid;
