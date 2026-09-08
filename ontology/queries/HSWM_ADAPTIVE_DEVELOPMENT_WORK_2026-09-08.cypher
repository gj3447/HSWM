// Execute each Q block independently. These are dated reference queries.
// Q1: Implemented capability -> exact Git source, with claim boundary.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-adaptive-development-work-2026-09-08-v1',standard_graph_role:'IMPLEMENTED_CAPABILITY'})-[:HAS_SOURCE]->(s)
RETURN n.name AS capability,n.status AS status,n.description AS scope,s.source_path AS path,s.source_commit AS commit,s.source_sha256 AS sha256
ORDER BY capability,path;

// Q2: Three dated first-run reports, not current runtime state or efficacy.
MATCH (r {ontology_bundle_uid:'sym:AbstractNode:hswm-adaptive-development-work-2026-09-08-v1',standard_graph_role:'DATED_ENGINEERING_REPORT'})-[:TESTS]->(p {standard_graph_role:'DEVELOPMENT_PROFILE'})
WHERE r.reported_test_pass_count IS NOT NULL
RETURN p.name AS project,r.observed_on AS reported_date,r.reported_test_pass_count AS passed,r.feedback_at_report AS feedback_then,r.status AS evidence_status
ORDER BY project;

// Q3: Open work remains distinct from implemented surfaces.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-adaptive-development-work-2026-09-08-v1'})-[:REQUIRES]->(g {standard_graph_role:'OPEN_WORK_ITEM'})
RETURN n.name AS context,g.name AS remaining_work,g.status AS status,g.description AS scope
ORDER BY remaining_work;

// Q4: New implementation references its unchanged historical design.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-adaptive-development-work-2026-09-08-v1'})-[:REFINES]->(a)
RETURN n.name AS implementation,n.status AS local_status,a.uid AS historical_uid,a.name AS historical_design,a.status AS preserved_historical_status
ORDER BY implementation;
