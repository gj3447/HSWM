// Q1: All 44 immutable source bindings in this dated snapshot.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-development-day-2026-09-08-v1',standard_graph_role:'SOURCE_ARTIFACT'})
RETURN n.source_path AS path,n.source_commit AS commit,n.source_sha256 AS sha256 ORDER BY path;

// Q2: User instruction and its exact source; does not ratify implementation.
MATCH (n {uid:'sym:AbstractNode:hswm-development-day-2026-09-08-user-request'})-[:HAS_SOURCE]->(s)
RETURN n.name AS name,n.authority_class AS authority,n.verbatim_text AS quote,s.source_path AS path,s.source_sha256 AS sha256;

// Q3: Two retested historical P2 findings and the still-open direct-projection P2.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-development-day-2026-09-08-v1',severity:'P2'})
RETURN n.name AS name,n.status AS status,n.description AS scope ORDER BY name;

// Q4: The 17 documented stack members; projected roles are not new ownership.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-development-day-2026-09-08-v1',status:'DOCUMENTED_PROJECTED_ROLE'})
RETURN n.component AS component,n.role AS role,n.description AS scope ORDER BY component;

// Q5: Four self-development runs; keep test scopes separate.
MATCH (n {ontology_bundle_uid:'sym:AbstractNode:hswm-development-day-2026-09-08-v1'})
WHERE n.reported_episode IS NOT NULL
RETURN n.name AS name,n.reported_episode AS episode,n.reported_test_pass_count AS passed,n.output_sha256 AS sha256 ORDER BY name;

// Q6: Agent feedback changed an internal score, not a measured efficacy result.
MATCH (n {uid:'sym:AbstractNode:hswm-development-day-2026-09-08-self-feedback-report'})
RETURN n.feedback_source AS source,n.before_revision AS before_revision,n.after_revision AS after_revision,n.before_score AS before_score,n.after_score AS after_score,n.reported_pending_feedback AS pending_at_snapshot;
