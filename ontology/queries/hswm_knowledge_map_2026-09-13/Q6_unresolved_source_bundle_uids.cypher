MATCH (snapshot {standard_graph_role: 'SOURCE_SNAPSHOT'})
WHERE snapshot.source_bundle_uid IS NOT NULL
  AND EXISTS {
    MATCH ({uid: 'sym:AbstractNode:hswm-knowledge-map-2026-09-13'})-[:HAS_CONCEPT]->()-[:HAS_SOURCE]->(snapshot)
  }
  AND NOT EXISTS {
    MATCH (target {uid: snapshot.source_bundle_uid})
  }
RETURN DISTINCT snapshot.uid AS snapshot_uid,
       snapshot.source_path AS source_path,
       snapshot.source_bundle_uid AS source_bundle_uid,
       snapshot.raw_source_status AS raw_source_status,
       snapshot.navigation_status AS navigation_status,
       snapshot.live_resolution AS live_resolution
ORDER BY source_bundle_uid, source_path, snapshot_uid
