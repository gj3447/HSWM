// Read each Q independently. Authored scenario records are not actual occurrences.

// Q1: Three connected concept drafts; previous planned records remain unchanged.
MATCH (s {ontology_bundle_uid: 'sym:AbstractNode:hswm-workshop-c1-c3-2026-09-07-v1', standard_graph_role: 'WORKED_SPEC_SECTION'})-[:REFINES]->(p)
RETURN s.plan_id AS step, s.draft_status AS status, s.description AS content,
       p.uid AS predecessor ORDER BY step;

// Q2: Twelve predictions from three researcher-supplied hypotheses.
MATCH (h {ontology_bundle_uid: 'sym:AbstractNode:hswm-workshop-c1-c3-2026-09-07-v1', standard_graph_role: 'ILLUSTRATIVE_HYPOTHESIS'})
UNWIND h.predictions AS prediction
RETURN h.hypothesis_id AS hypothesis, prediction, h.origin AS origin
ORDER BY hypothesis, prediction;

// Q3: Three distinct revision candidates; none has actual admission support.
MATCH (r {ontology_bundle_uid: 'sym:AbstractNode:hswm-workshop-c1-c3-2026-09-07-v1', standard_graph_role: 'WORKED_REVISION_CANDIDATE'})
RETURN r.revision_id AS revision, r.revision_scope AS scope, r.description AS change,
       r.support_status AS support, r.revision_state AS state ORDER BY revision;

// Q4: Four untested design intuitions.
MATCH (i {ontology_bundle_uid: 'sym:AbstractNode:hswm-workshop-c1-c3-2026-09-07-v1', standard_graph_role: 'WORKED_DESIGN_INSIGHT'})
RETURN i.insight_id AS insight, i.name AS name, i.description AS description,
       i.status AS status ORDER BY insight;
