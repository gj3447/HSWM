MATCH (snapshot {standard_graph_role: 'SOURCE_SNAPSHOT'})
WHERE EXISTS {
  MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->()-[:HAS_SOURCE]->(snapshot)
}
WITH snapshot.source_path AS source_path, count(DISTINCT snapshot) AS descriptor_count
WHERE descriptor_count > 1
RETURN 'DUPLICATE_SOURCE_PATH' AS ambiguity_kind,
       source_path,
       descriptor_count,
       NULL AS snapshot_uid,
       NULL AS navigation_status,
       NULL AS raw_source_status
UNION
MATCH (snapshot {standard_graph_role: 'SOURCE_SNAPSHOT'})
WHERE snapshot.raw_source_status STARTS WITH 'CANONICAL_TARGET'
  AND snapshot.navigation_status = 'RETIRED_TARGET_FORMAT'
  AND EXISTS {
    MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->()-[:HAS_SOURCE]->(snapshot)
  }
RETURN 'CANONICAL_RAW_RETIRED_NAVIGATION_CONFLICT' AS ambiguity_kind,
       snapshot.source_path AS source_path,
       NULL AS descriptor_count,
       snapshot.uid AS snapshot_uid,
       snapshot.navigation_status AS navigation_status,
       snapshot.raw_source_status AS raw_source_status
ORDER BY ambiguity_kind, source_path, snapshot_uid
