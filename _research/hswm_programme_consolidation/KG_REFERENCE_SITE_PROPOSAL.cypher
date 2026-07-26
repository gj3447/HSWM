// PROPOSAL ONLY. Do not execute without explicit user authorization for KG writes.
// Parameters:
//   $programme_name, $contract_name, $binding_id, $baseline_scope,
//   $actor, $manifest_path, $recorded_at, $bindings
// Each $bindings row must contain sourceId, source_root, source_path,
// line_range, qualified_symbol, symbol_kind, sha256, binding_state,
// confidence, evidence_json.

MATCH (programme:KnowledgeNode:SemanticAnchor {name: $programme_name})
MATCH (contract:KnowledgeNode:AptContract {name: $contract_name})
MATCH (programme)-[:HAS_CONTRACT]->(contract)
UNWIND $bindings AS b
WITH programme, contract, b
WHERE b.source_path IS NOT NULL
MERGE (rs:ReferenceSite:Longinus:KG_REFERENCE {
  name: $binding_id + '--' + b.sourceId
})
ON CREATE SET
  rs.binding_id = $binding_id,
  rs.sourceId = b.sourceId,
  rs.sourceRoot = b.source_root,
  rs.sourcePath = b.source_path,
  rs.lineRange = b.line_range,
  rs.qualified_symbol = b.qualified_symbol,
  rs.symbol_kind = b.symbol_kind,
  rs.sha256 = b.sha256,
  rs.sha256_baseline = b.sha256,
  rs.sha256_status = 'BASELINE',
  rs.binding_state = b.binding_state,
  rs.confidence = b.confidence,
  rs.baseline_scope = $baseline_scope,
  rs.repo_tag = 'HSWM',
  rs.provenance_actor = $actor,
  rs.provenance_source_path = $manifest_path,
  rs.provenance_timestamp = datetime($recorded_at),
  rs.evidence_json = b.evidence_json,
  rs.claim_boundary = 'REFERENCE_INTEGRITY_ONLY_NO_SCIENTIFIC_VERDICT',
  rs.no_external_citation_reason =
    'Local repository and Proxmox LakatoTree readback; no external citation applicable',
  rs.depth = 0
MERGE (contract)-[:HAS_REFERENCE_SITE]->(rs)
MERGE (programme)-[:HAS_REFERENCE_SITE]->(rs)
RETURN count(rs) AS proposed_reference_sites;
