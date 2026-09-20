/** Source-bound research projection. Pure graph construction, Effect-wrapped file I/O. */
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const base = 'docs/research/artifacts/hswm_research_integration_2026-09-20';
const output = 'ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json';
const root = 'sym:AbstractNode:hswm-research-integration-2026-09-20';
const sha = (s: string | Uint8Array) => createHash('sha256').update(s).digest('hex');
const uid = (kind: string, key: string) => `sym:${kind}:hswm-ri-20260920-${key}`;
const boundary = 'SOURCE_BOUND_RESEARCH_PROJECTION_NOT_CANONICAL_COGNITION_LEARNING_OR_CR_FCL_PROMOTION';
type Props = Record<string, string | number | boolean | readonly string[]>;
const topics: Record<string, string> = {
  identity: 'HSWM identity and evidence ceiling', hypergraph: 'Hypergraph state, roles and Hyperon comparator',
  semantic: 'Semantic Weight and local realization', locality: 'Local read sufficiency and execution',
  credit: 'Outcome binding and causal credit', learning: 'Durable learning and revision',
  composition: 'Recursive composition and FCL obligations', memory: 'Temporal retrieval and memory projections',
  execution: 'Durable execution and bounded transport', evidence: 'Provenance, observations and uncertainty',
  evaluation: 'Independent evaluation and falsification', standards: 'Graph interchange and validation standards',
  jev: 'Jev typed decision models', uncertainty: 'Concentration, correctness confidence and calibration',
  theory: 'Conditional mathematical dynamics and learning theory', inventory: 'Versioned research source inventory'
};
const classify = (text: string): string => {
  const s = text.toLowerCase();
  for (const [pattern, topic] of [
    ['jev|typesafe', 'jev'], ['hyperon|hypergraph|nary|n-ary', 'hypergraph'], ['semantic.weight|semantic.graph|semantic.engine|disposition', 'semantic'],
    ['fractal|composition|compositional', 'composition'], ['credit|causal', 'credit'], ['locality|local.operator|activation', 'locality'],
    ['learning|learner|gepa|optimizer', 'learning'], ['theor|proof|mathemat|lean', 'theory'], ['memory|temporal|storage', 'memory'],
    ['evaluat|benchmark|efficacy|qualification', 'evaluation'], ['provenance|receipt|evidence|observability', 'evidence'],
    ['rdf|ontology|interop|shacl|standard', 'standards'], ['constitution|user.primary|identity', 'identity'], ['runtime|execution|effect|transport', 'execution']
  ]) if (new RegExp(pattern).test(s)) return topic;
  return 'inventory';
};
function construct(repository: any, prior: any, live: any, analysis: any, result: any, repositoryAnchors: any, bindings: any[]) {
  const nodes: any[] = [], relations: any[] = [];
  const add = (id: string, label: string, role: string, name: string, description: string, properties: Props = {}) => {
    nodes.push({ uid: id, labels: label === 'AbstractNode' ? ['Concept', 'AbstractNode'] : [label], properties: {
      name, description, standard_graph_role: role, status: 'SOURCE_BOUND_SECONDARY_SYNTHESIS',
      authority_class: 'SECONDARY_AI', ontology_authority_class_v1: 'SECONDARY_AI',
      ontology_kind_v1: label === 'Reference' ? 'DOCUMENT' : 'CONCEPT', ontology_domain_v1: 'ENGINEERING',
      ontology_plane_v1: 'RESEARCH_PROJECTION', ontology_canonical_scope_v1: 'PENDING_OR_PRELIMINARY',
      ontology_epistemic_state_v1: 'PENDING', ontology_record_lifecycle_v1: 'ACTIVE',
      ontology_review_required_v1: true, ontology_sensitivity_v1: 'NORMAL',
      responsibility_owner: 'hswm:research:integration:2026-09-20',
      claim_boundary: boundary, projection_nonclaim: 'NOT_COGNITION_ROUTING_CANONICAL_ADMISSION_OR_LEARNING',
      ...properties } });
    return id;
  };
  const link = (from: string, type: string, to: string, scope = 'SOURCE_BOUND_RESEARCH_VIEW') => relations.push({
    from_uid: from, to_uid: to, type, authority_class: 'SECONDARY_AI', scope, status: 'PROPOSED_RESEARCH_PROJECTION' });
  const anchored = [...new Map([...live.records.map((r: any) => ({ uid: r.uid, name: r.name, required_labels: r.labels })), ...repositoryAnchors.anchors].map(a => [a.uid, a])).values()];
  add(root, 'AbstractNode', 'RESEARCH_INTEGRATION', 'HSWM 연구 통합 — Jev, ChatGPT 연구, DGX 실측 2026-09-20', analysis.conceptual_delta,
    { status: 'SOURCE_BOUND_INTEGRATION_WITH_BOUNDED_OBSERVATION', source_ref: 'docs/research/HSWM_RESEARCH_INTEGRATION_2026-09-20.md',
      repository_sources: repository.sources.length, prior_research_responses: prior.records.length, live_source_records: live.records.length,
      inventory_boundary: repository.scope, all_sources_semantically_audited: false });
  for (const [key, title] of Object.entries(topics)) {
    add(uid('Concept', key), 'Concept', 'RESEARCH_TOPIC', title, title, { source_ref: `${base}/analysis.v1.json` });
    link(root, 'HAS_CONCEPT', uid('Concept', key));
  }
  const byPath = new Map<string, string>();
  for (const r of repository.sources) {
    const id = uid('Reference', 'repo-' + sha(r.path).slice(0, 20)); byPath.set(r.path, id);
    add(id, 'Reference', 'REPOSITORY_SOURCE', r.title, r.coverage, { source_ref: r.path, source_sha256: r.sha256,
      source_bytes: r.bytes, source_kind: r.kind, declared_source_status: r.source_status ?? 'READ_ORIGINAL_FOR_CLAIM_STATUS',
      declared_bundle_uid: r.bundle_uid ?? '', inventory_only: true, status: 'INVENTORIED_EXACT_BYTES_NOT_NEW_REVIEW',
      live_anchor_resolution: r.bundle_uid ? (repositoryAnchors.anchors.some((a: any) => a.uid === r.bundle_uid) ? 'RESOLVED_NORMAL_SOURCE' : 'UNRESOLVED_IN_BOUNDED_NORMAL_SOURCE_LOOKUP') : 'NOT_A_BUNDLE' });
    link(root, 'REFERENCES', id); link(id, 'ABOUT', uid('Concept', classify(r.path)));
    if (repositoryAnchors.anchors.some((a: any) => a.uid === r.bundle_uid)) link(id, 'REFERENCES', r.bundle_uid, 'EXISTING_LIVE_BUNDLE_ENTRYPOINT');
  }
  const external = new Map<string, string>();
  const url = (raw: string, title?: string, verified = false) => {
    const u = raw.replace(/[.,;]+$/, '');
    if (!/^https?:\/\//.test(u)) throw new Error('Not an external URL');
    if (external.has(u)) {
      if (verified) { const n = nodes.find(n => n.uid === external.get(u)); n.properties.status = 'OFFICIAL_SOURCE_REVIEWED_2026_09_20'; }
      return external.get(u)!;
    }
    const id = uid('Reference', 'url-' + sha(u).slice(0, 20)); external.set(u, id);
    add(id, 'Reference', 'EXTERNAL_SOURCE', title ?? u, 'Public source location. A URL identity hash is not a content hash.', {
      source_ref: u, source_location_sha256: sha(u), status: verified ? 'OFFICIAL_SOURCE_REVIEWED_2026_09_20' : 'PRIOR_ASSISTANT_CITATION_NOT_REVERIFIED',
      content_digest_available: false });
    return id;
  };
  const priorIds = new Map<number, string>();
  for (const r of prior.records) {
    const id = uid('Reference', 'chatgpt-' + r.ordinal); priorIds.set(r.ordinal, id);
    add(id, 'Reference', 'PRIOR_RESEARCH_RESPONSE', `ChatGPT research ${r.ordinal}: ${r.job_id}`,
      'Exact response digest verified against private stored bytes. Public graph contains summaries and citation locations only.', {
        source_ref: r.source_ref, source_sha256: r.assistant_sha256, source_commit: r.source_commit,
        sourcepack_sha256: r.sourcepack_sha256, source_characters: r.characters, status: r.state, raw_text_public: false,
        model_observation: r.model_observation, research_ordinal: r.ordinal });
    link(root, 'REFERENCES', id);
    for (const u of r.public_source_urls) link(id, 'REFERENCES', url(u), 'CITATION_REPORTED_BY_PRIOR_ASSISTANT');
  }
  const liveIds = new Map<string, string>();
  for (const r of live.records) {
    const id = uid('Reference', 'kg-' + sha(r.uid).slice(0, 20)); liveIds.set(r.uid, id);
    add(id, 'Reference', 'EXISTING_KG_SOURCE', r.title ?? r.name, r.coverage, {
      source_ref: r.uid, source_sha256: r.text_sha256, source_characters: r.text_chars,
      source_field: r.body_field, source_authority_class: r.authority_class ?? 'UNDECLARED', status: 'EXISTING_SOURCE_NOT_REWRITTEN' });
    link(id, 'REFERENCES', r.uid); link(root, 'REFERENCES', id); link(id, 'ABOUT', uid('Concept', classify(r.uid)));
    for (const u of r.public_source_urls) link(id, 'REFERENCES', url(u), 'CITATION_REPORTED_BY_EXISTING_KG_SOURCE');
  }
  const occurrence = (assertion: string, role: string, ordinal: number, target: string) => {
    const id = uid('AbstractNode', 'occ-' + sha(assertion + ':' + role + ':' + ordinal).slice(0, 20));
    add(id, 'AbstractNode', 'ROLE_PARTICIPATION', role, `Role ${role} at slot ${ordinal}; target identity preserved independently of role.`,
      { role_name: role, ordinal, assertion_uid: assertion, participant_uid: target, source_ref: `${base}/analysis.v1.json` });
    link(assertion, 'HAS_PARTICIPATION', id); link(id, 'REFERENCES', target, 'ROLE_BEARING_PARTICIPANT');
  };
  for (const r of analysis.prior_research) {
    const claim = uid('Claim', 'proposal-' + r.ordinal), question = uid('ResearchQuestion', 'obligation-' + r.ordinal);
    add(claim, 'Claim', 'RESEARCH_PROPOSAL', r.title, r.proposal, { limitation: r.limitation,
      status: 'PROPOSED_NOT_ADOPTED_OR_EXECUTED', source_ref: prior.records.find((p: any) => p.ordinal === r.ordinal).source_ref });
    add(question, 'ResearchQuestion', 'OPEN_OBLIGATION', `Qualification ${r.ordinal}: ${r.title}`, r.next,
      { status: 'OPEN', source_ref: `${base}/analysis.v1.json` });
    link(claim, 'DERIVED_FROM', priorIds.get(r.ordinal)!); link(claim, 'ABOUT', uid('Concept', r.topic));
    link(claim, 'RELATES_TO', question, 'REQUIRES_INDEPENDENT_QUALIFICATION'); link(question, 'ABOUT', uid('Concept', r.topic));
    link(root, 'HAS_CONCEPT', claim);
    occurrence(claim, 'proposed_capability', 0, uid('Concept', r.topic));
    occurrence(claim, 'source_response', 1, priorIds.get(r.ordinal)!);
    occurrence(claim, 'remaining_obligation', 2, question);
  }
  const identity = add(uid('Claim', 'identity-reference'), 'Claim', 'TARGET_IDENTITY_REFERENCE', 'Four HSWM identity commitments together', analysis.identity,
    { status: 'CANONICAL_TARGET_REFERENCE_NOT_IMPLEMENTATION_EVIDENCE', source_ref: 'docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md' });
  link(identity, 'DERIVED_FROM', byPath.get('docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md')!);
  link(identity, 'DERIVED_FROM', byPath.get('docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md')!);
  link(root, 'HAS_CONCEPT', identity); link(identity, 'ABOUT', uid('Concept', 'identity'));
  for (const r of live.records.filter((r: any) => /-r[0-8]-|dynamics-v01|learning-theory-v01|p1-/.test(r.uid))) {
    const id = add(uid('Claim', 'formal-' + sha(r.uid).slice(0, 16)), 'Claim', 'FORMAL_PROPOSAL_REFERENCE', r.title,
      'Existing formal vocabulary, contract, conditional theorem or proposed benchmark. Consult the bound source for premises and exact scope; no new proof or empirical closure is inferred.',
      { source_ref: r.uid, status: 'PRELIMINARY_FORMAL_SOURCE_NOT_EFFICACY' });
    link(id, 'DERIVED_FROM', liveIds.get(r.uid)!); link(id, 'ABOUT', uid('Concept', classify(r.uid))); link(root, 'HAS_CONCEPT', id);
  }
  for (const r of analysis.jev_claims) {
    const id = add(uid('Claim', 'jev-' + r.id), 'Claim', 'LITERATURE_CLAIM', r.title, r.text, { source_ref: r.source, status: r.status });
    link(id, 'DERIVED_FROM', url(r.source, undefined, true)); link(id, 'ABOUT', uid('Concept', r.topic)); link(root, 'HAS_CONCEPT', id);
  }
  for (const r of analysis.papers) {
    const source = url(r.url, r.title, true), id = add(uid('Claim', 'paper-' + r.id), 'Claim', 'LITERATURE_CLAIM', r.title, r.finding,
      { transfer_boundary: r.transfer, paper_version: r.version, source_ref: r.url, status: 'PAPER_REPORTED_RESULT_NOT_HSWM_TRANSFER' });
    link(id, 'DERIVED_FROM', source); link(id, 'ABOUT', uid('Concept', r.topic)); link(root, 'HAS_CONCEPT', id);
  }
  for (const r of analysis.standards) {
    const source = url(r.url, r.title, true), id = add(uid('Concept', 'standard-' + r.id), 'Concept', 'STANDARD_USAGE', r.title, r.use,
      { standard_maturity: r.maturity, source_ref: r.url, status: 'USED_FOR_RESEARCH_EXCHANGE_NOT_HSWM_COGNITION' });
    link(id, 'DERIVED_FROM', source); link(id, 'ABOUT', uid('Concept', 'standards')); link(root, 'HAS_CONCEPT', id);
  }
  const experiment = add(uid('Experiment', 'dgx-locality'), 'Experiment', 'OBSERVED_EXPERIMENT', 'DGX local semantic interpretation: 80 inference requests',
    'Sixteen fixed truth-table cases, five prompt interventions. No training, canonical revision, Jev execution, Hyperon comparison or equal-cost efficacy test.',
    { source_ref: '_research/semantic_locality_dgx_v1/summary.json', status: 'OBSERVED_BOUNDED_SYNTHETIC_RESULT', requests: result.requests,
      protocol_sha256: result.protocol_sha256, runner_sha256: result.runner_sha256, model_checkpoint_verified: false, cr_fcl_promotion: false });
  const model = add(uid('Reference', 'dgx-model'), 'Reference', 'MODEL_OBSERVATION', 'Qwen3.6-35B-A3B-FP8 / qwen3.6-35b-a3b',
    'Existing DGX vLLM service reports this model alias/root and vLLM 0.25.1. Exact loaded checkpoint commit was not independently verified. No model was downloaded.',
    { source_ref: 'https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8', status: 'SERVICE_REPORTED_MODEL_NOT_CHECKPOINT_ATTESTATION' });
  const protocol = add(uid('Reference', 'dgx-protocol'), 'Reference', 'EXPERIMENT_PROTOCOL', 'Frozen local interpretation protocol',
    'Truth labels computed before inference. Role swap changes facts; meaning removal changes available information and token count. Restored means identical prompt re-input.',
    { source_ref: '_research/semantic_locality_dgx_v1/protocol.v1.json', source_sha256: result.protocol_sha256, status: 'FROZEN_BEFORE_INFERENCE' });
  link(experiment, 'DERIVED_FROM', protocol); link(experiment, 'ABOUT', uid('Concept', 'locality')); link(root, 'HAS_CONCEPT', experiment);
  for (const r of result.arms) {
    const id = add(uid('Claim', 'dgx-' + r.arm), 'Claim', 'OBSERVED_RESULT', `DGX ${r.arm}: ${r.correct}/${r.n} original-label agreement`,
      'Descriptive agreement on the frozen finite task family. Role-swap disagreement can be correct response to changed facts, not model failure.',
      { source_ref: '_research/semantic_locality_dgx_v1/observations.jsonl', status: 'OBSERVED_SYNTHETIC_NOT_GENERAL_EFFICACY',
        arm: r.arm, n: r.n, correct: r.correct, valid: r.valid, brier_original_label_agreement: r.brier_correctness,
        comparison_target: 'ORIGINAL_LABEL_AGREEMENT_NOT_CHANGED_INPUT_CORRECTNESS',
        confidence_metric_boundary: 'NOT_POPULATION_CALIBRATION_ROLE_SWAP_CONFIDENCE_TARGET_DIFFERS',
        prompt_tokens: r.prompt_tokens, completion_tokens: r.completion_tokens, mean_latency_ms: r.mean_latency_ms, cr_fcl_promotion: false });
    link(id, 'DERIVED_FROM', experiment); link(id, 'ABOUT', uid('Concept', 'locality')); link(experiment, 'HAS_CONCEPT', id);
    occurrence(id, 'protocol', 0, protocol); occurrence(id, 'model_observation', 1, model); occurrence(id, 'execution', 2, experiment);
  }
  const next = add(uid('ResearchQuestion', 'dgx-next'), 'ResearchQuestion', 'OPEN_OBLIGATION', 'Remove semantic shortcuts before claiming relation utility',
    'Meaning-removed agreement is 15/16 versus full 16/16, with majority-deny 13/16. Predeclare balanced counterfactual meanings and held-out role/context combinations, match budgets, pin checkpoint, then connect outcome-conditioned durable revision and mandatory Hyperon comparator.',
    { source_ref: '_research/semantic_locality_dgx_v1/summary.json', status: 'OPEN_NOT_RESCUED_BY_PERFECT_FULL_SCORE' });
  link(next, 'DERIVED_FROM', experiment); link(next, 'ABOUT', uid('Concept', 'evaluation')); link(experiment, 'RELATES_TO', next);
  for (const path of ['docs/research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md', 'docs/research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md', 'docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md', 'docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md', 'docs/research/HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md']) link(next, 'REFERENCES', byPath.get(path)!);
  const unique = [...new Map(relations.map(r => [JSON.stringify([r.from_uid, r.type, r.to_uid]), r])).values()];
  return { schema_version: 'hswm-research-integration/v1', bundle_uid: root, status: 'SOURCE_BOUND_SECONDARY_RESEARCH_WITH_LIMITED_OBSERVATION',
    nonclaim: boundary, authority_boundary: 'USER_PRIMARY_TARGETS_REMAIN_AT_ORIGINAL_SOURCES_AI_SYNTHESIS_NOT_RATIFICATION', source_accessed_on: '2026-09-20',
    artifact_bindings: bindings, expected_counts: { nodes: nodes.length, anchors: anchored.length, relations: unique.length },
    anchors: anchored, nodes, relations: unique };
}
const io = (f: () => Promise<any>) => Effect.tryPromise({ try: f, catch: (e: unknown) => e });
const main = Effect.gen(function* () {
  const paths = [`${base}/repository-sources.v1.json`, `${base}/prior-research-manifest.v1.json`, `${base}/kg-sources.v1.json`, `${base}/analysis.v1.json`, '_research/semantic_locality_dgx_v1/summary.json', `${base}/repository-live-anchors.v1.json`];
  const bytes = yield* Effect.all(paths.map(path => io(() => readFile(path))), { concurrency: 'unbounded' });
  const objects = bytes.map((b: Uint8Array) => JSON.parse(Buffer.from(b).toString()));
  const extraPaths = ['_research/semantic_locality_dgx_v1/run.mts', '_research/semantic_locality_dgx_v1/protocol.v1.json', '_research/semantic_locality_dgx_v1/observations.jsonl', '_research/semantic_locality_dgx_v1/analysis.v1.json', '_research/semantic_locality_dgx_v1/durable-receipt.v1.json', '_research/research_graph_integration_v1/build.mts', 'docs/research/HSWM_RESEARCH_INTEGRATION_2026-09-20.md', 'results/HSWM_LOCAL_SEMANTIC_PROBE_2026-09-20.md', 'schemas/HSWM_RESEARCH_INTEGRATION_SHACL_2026-09-20.ttl'];
  const extra = yield* Effect.all(extraPaths.map(path => io(() => readFile(path))), { concurrency: 'unbounded' });
  const bindings = [...paths.map((path, i) => ({ path, sha256: sha(bytes[i]) })), ...extraPaths.map((path, i) => ({ path, sha256: sha(extra[i]) }))];
  const bundle = construct(...objects as [any, any, any, any, any, any], bindings);
  const raw = JSON.stringify(bundle, null, 2) + '\n';
  Either.getOrThrowWith(decodeKgBundleSource({ sourceId: 'research20260920', rawBytes: Buffer.from(raw) }, 'v2'), (e: any) => e);
  yield* io(() => mkdir('ontology/development', { recursive: true }));
  yield* io(() => writeFile(output, raw));
  console.log(JSON.stringify({ output, sha256: sha(raw), ...bundle.expected_counts }));
});
Effect.runPromise(main).catch((e: unknown) => { console.error(String(e)); process.exitCode = 1; });
