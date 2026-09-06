// Read-only discovery queries. Run the parameter command in Neo4j Browser,
// then execute each MATCH query separately. All new interpretations are
// SECONDARY_AI. TESTS means proposed discrimination, never an observed PASS.
:param bundle => 'sym:AbstractNode:hswm-research-insights-2026-09-06-v1';

// Q1: Which observations motivate a rule and a concrete next experiment?
MATCH (rule)-[d:DERIVED_FROM]->(basis), (rule)-[m:MOTIVATES]->(experiment)
WHERE rule.ontology_bundle_uid = $bundle
  AND 'proposed_rule' IN rule.semantic_roles
  AND d.ontology_bundle_uid = $bundle AND m.ontology_bundle_uid = $bundle
RETURN rule.insight_id AS rule, rule.name AS proposal,
       collect(DISTINCT basis.insight_id) AS evidence_or_interpretation,
       collect(DISTINCT experiment.insight_id) AS experiments,
       rule.ratification AS authority_boundary
ORDER BY rule LIMIT 20;

// Q2: Which untested explanations can each experiment distinguish?
MATCH (experiment)-[r:TESTS]->(hypothesis)
WHERE r.ontology_bundle_uid = $bundle
RETURN experiment.insight_id AS experiment, experiment.readiness AS readiness,
       hypothesis.insight_id AS hypothesis, hypothesis.name AS explanation,
       hypothesis.falsifier AS discriminating_result, r.scope AS test_scope
ORDER BY experiment, hypothesis LIMIT 30;

// Q3: What is still missing from each proposed experiment?
MATCH (experiment)
WHERE experiment.ontology_bundle_uid = $bundle
  AND 'experiment' IN experiment.semantic_roles
OPTIONAL MATCH (experiment)-[r:DEPENDS_ON]->(dependency)
WHERE r.ontology_bundle_uid = $bundle
RETURN experiment.insight_id AS experiment, experiment.name AS next_work,
       experiment.readiness AS current_limit,
       collect(DISTINCT dependency.insight_id) AS dependencies,
       experiment.falsifier AS failure_or_boundary
ORDER BY experiment LIMIT 20;

// Q4: Why do prompt-payload sufficiency and canonical mediation coexist?
MATCH (a)-[r]->(b)
WHERE r.ontology_bundle_uid = $bundle
  AND a.insight_id IN ['I-03', 'H-01', 'R-6']
  AND type(r) IN ['RELATED_TO', 'ALTERNATIVE_TO', 'MOTIVATES']
RETURN a.insight_id AS subject, type(r) AS relation, b.insight_id AS object,
       r.scope AS meaning, a.description AS context
ORDER BY subject, object LIMIT 20;

// Q5: Keep prior failure, programme-file closure and scientific status visible.
MATCH (n)
WHERE n.ontology_bundle_uid = $bundle
  AND n.insight_id IN ['O-01', 'O-02', 'O-10', 'O-13', 'O-14', 'S-01']
RETURN n.insight_id AS id, n.name AS name, n.description AS reading,
       n.terminal AS historical_terminal, n.g0 AS g0, n.g1 AS g1,
       n.source_paths AS sources
ORDER BY id LIMIT 20;
