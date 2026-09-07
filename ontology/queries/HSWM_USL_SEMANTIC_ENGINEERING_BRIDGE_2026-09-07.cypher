// Read-only questions after the declared bundle has been published.
// Empty rows before publication are not an absence claim about external USL.
MATCH (p)-[r:MOTIVATES]->(c)<-[:CHALLENGES]-(f)
WHERE r.ontology_bundle_uid = 'sym:AbstractNode:hswm-usl-bridge-2026-09-07-v1'
RETURN p.chain_id AS chain, p.description AS premise,
       c.description AS contract, f.description AS counterexample,
       p.authority_class AS authority, p.status AS proposal_status
ORDER BY chain;

MATCH (s)-[r:HAS_SOURCE]->(external)
WHERE r.ontology_bundle_uid = 'sym:AbstractNode:hswm-usl-bridge-2026-09-07-v1'
  AND s.standard_graph_role = 'EXTERNAL_SOURCE_READING'
RETURN external.uid AS external_uid, external.authority_class AS source_authority,
       external.ontology_authority_class_v1 AS mapped_source_authority,
       s.external_bundle_sha256 AS source_digest, s.external_receipt_uid AS publication_receipt;

MATCH (n)-[r:RELATED_TO]->(q:OpenQuestion)
WHERE r.ontology_bundle_uid = 'sym:AbstractNode:hswm-usl-bridge-2026-09-07-v1'
RETURN DISTINCT q.uid AS original_question, q.name AS question_name,
       q.question_status AS current_source_status, q.user_answered AS current_user_answered;
