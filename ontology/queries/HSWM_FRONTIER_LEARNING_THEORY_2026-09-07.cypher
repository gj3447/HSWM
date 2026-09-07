// Execute each Q block independently; all relations are bounded research references.
// Q1: Complete paper -> mechanism -> HSWM candidate -> falsifier chains (35 rows).
MATCH (s {ontology_bundle_uid:'sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1',standard_graph_role:'LITERATURE_SOURCE'})-[:HAS_CONCEPT]->(m)-[:SPECULATIVE_LINK]->(b)-[:REQUIRES]->(t)
RETURN s.name AS paper,s.url AS url,s.family AS family,m.description AS mechanism,b.description AS bridge,t.description AS falsifier
ORDER BY family,paper;

// Q2: Near-term review candidates; priority is not efficacy.
MATCH (b {ontology_bundle_uid:'sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1',standard_graph_role:'HSWM_BRIDGE_CANDIDATE',priority:'near'})
RETURN b.name AS candidate,b.limitation AS limitation,b.implementation_status AS implementation,b.efficacy_status AS efficacy
ORDER BY candidate;

// Q3: Sources first submitted in 2026, with source review limits.
MATCH (s {ontology_bundle_uid:'sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1',standard_graph_role:'LITERATURE_SOURCE',year:2026})
RETURN s.name AS paper,s.source_date AS date,s.url AS url,s.source_status AS publication,s.inspected_scope AS inspection
ORDER BY date,paper;

// Q4: Current implementation snapshot, independently of literature candidates.
MATCH (s {ontology_bundle_uid:'sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1',standard_graph_role:'IMPLEMENTATION_SNAPSHOT'})
RETURN s.name AS implementation,s.implementation_status AS status,s.efficacy_status AS efficacy,s.description AS description;
