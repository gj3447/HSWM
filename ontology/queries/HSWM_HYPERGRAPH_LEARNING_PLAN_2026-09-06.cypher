// Execute each read-only Q block independently on the live KG.
// Scope is the immutable plan bundle; rows describe proposals, not actual runs.

// Q1: Expected 25 role incidences in four design assertions.
MATCH (a {ontology_bundle_uid: 'sym:AbstractNode:hswm-hypergraph-learning-plan-2026-09-06-v1', standard_graph_role: 'LEARNING_ASSERTION'})
      -[:HAS_PARTICIPATION]->(p)-[:TARGET]->(t)
RETURN a.name AS assertion, a.learning_scale AS scale, p.ordinal AS ordinal,
       p.role_name AS role, t.name AS target, p.revision_scope AS revisionScope
ORDER BY assertion, ordinal;

// Q2: Expected two distinct credit scales, each connected to observation and revision proposal.
MATCH (r {ontology_bundle_uid: 'sym:AbstractNode:hswm-hypergraph-learning-plan-2026-09-06-v1'})
      -[:DEPENDS_ON]->(c)-[:DEPENDS_ON]->(p)-[:ADDRESSES]->(h)
WHERE c.learning_scale IN ['LOCAL', 'INTERACTION']
RETURN c.learning_scale AS scale, c.name AS credit, p.name AS observation,
       h.name AS explanations, r.name AS revision
ORDER BY scale;

// Q3: Expected seven incidences; the whole remains the same target in two distinct roles.
MATCH (a {uid: 'sym:AbstractNode:hswm-hgplan-recursive-participation-2026-09-06-v1'})
      -[:HAS_PARTICIPATION]->(p)-[:TARGET]->(t)
RETURN p.ordinal AS ordinal, p.role_name AS role, t.name AS target,
       t.description AS obligation
ORDER BY ordinal;

// Q4: Expected six planned conceptual artifacts, all PLANNED_NOT_COMPLETED.
MATCH (s {ontology_bundle_uid: 'sym:AbstractNode:hswm-hypergraph-learning-plan-2026-09-06-v1', standard_graph_role: 'LEARNING_PLAN_STEP'})
RETURN s.plan_id AS step, s.next_artifact AS nextArtifact, s.open_choice AS openChoice,
       s.status AS status
ORDER BY step;
