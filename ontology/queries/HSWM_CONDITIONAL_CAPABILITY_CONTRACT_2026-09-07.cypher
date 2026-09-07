// Read-only queries after publication. Empty results do not describe external state.
// Q1. Proposed generation boundary and its still-open workshop gap.
MATCH (n {standard_graph_role:'CONDITIONAL_CAPABILITY_GENERATION'})-[r:REFINES]->(gap)
WHERE r.ontology_bundle_uid = 'sym:AbstractNode:hswm-conditional-capability-contract-2026-09-07-v1'
RETURN n.uid AS node_uid, n.name AS node, n.status AS status,
       gap.uid AS gap_uid, gap.name AS gap, r.status AS relation_status;

// Q2. Relation/disposition or cell candidates that motivate the next interpreter.
MATCH (n)-[r:MOTIVATES]->(i {standard_graph_role:'CONDITIONAL_CAPABILITY_NEXT_INTERPRETER'})
WHERE r.ontology_bundle_uid = 'sym:AbstractNode:hswm-conditional-capability-contract-2026-09-07-v1'
  AND n.standard_graph_role IN ['CONDITIONAL_CAPABILITY_COMPUTATION','CONDITIONAL_CAPABILITY_CELL','CONDITIONAL_CAPABILITY_GENERATION']
RETURN n.uid AS candidate_uid, n.name AS candidate, n.standard_graph_role AS role,
       i.uid AS interpreter_uid, i.name AS interpreter, n.status AS status
ORDER BY role;

// Q3. Source/refinement anchors plus owned draft authority; no promotion is inferred.
MATCH (n)-[r:HAS_SOURCE|REFINES]->(a)
WHERE n.ontology_bundle_uid = 'sym:AbstractNode:hswm-conditional-capability-contract-2026-09-07-v1'
RETURN n.uid AS owned_uid, n.authority_class AS authority, n.status AS status,
       type(r) AS predicate, a.uid AS anchor_uid, a.name AS anchor_name
ORDER BY predicate, anchor_name;
