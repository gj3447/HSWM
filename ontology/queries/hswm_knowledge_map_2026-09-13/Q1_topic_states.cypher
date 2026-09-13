MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->(topic)
WHERE topic.standard_graph_role = 'KNOWLEDGE_MAP_TOPIC'
RETURN topic.uid AS topic_uid,
       topic.name AS topic_name,
       topic.design_status AS design_status,
       topic.engineering_status AS engineering_status,
       topic.formal_status AS formal_status,
       topic.efficacy_status AS efficacy_status
ORDER BY topic_name, topic_uid
