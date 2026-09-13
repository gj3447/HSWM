MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->(topic)
MATCH (topic)-[:HAS_SOURCE]->(snapshot)
WHERE topic.standard_graph_role = 'KNOWLEDGE_MAP_TOPIC'
  AND snapshot.standard_graph_role = 'SOURCE_SNAPSHOT'
  AND snapshot.navigation_status = 'CURRENT_ENTRYPOINT'
RETURN topic.uid AS topic_uid,
       topic.name AS topic_name,
       snapshot.uid AS snapshot_uid,
       snapshot.source_path AS source_path,
       snapshot.raw_source_status AS raw_source_status,
       snapshot.navigation_status AS navigation_status,
       snapshot.source_bundle_uid AS source_bundle_uid
ORDER BY topic_name, source_path, snapshot_uid
