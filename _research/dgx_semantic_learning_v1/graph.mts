/** A source-bound research projection; no runtime or canonical learning authority. */
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { digest } from './domain.mts';
const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const io = (f: () => Promise<any>) => Effect.tryPromise({ try: f, catch: (e: unknown) => e });
const artifactRoot = 'docs/research/artifacts/hswm_dgx_frontier_2026-09-20';
const root = 'sym:AbstractNode:hswm-dgx-frontier-research-2026-09-20';
const id = (kind: string, slug: string) => `sym:${kind}:hswm-dgxf-20260920-${slug}`;
const boundary = 'BOUNDED_SYNTHETIC_RESEARCH_AND_CANDIDATE_SELECTION_NOT_HSWM_EFFICACY_OR_CR_FCL_CLOSURE';
function construct(catalog: any, results: any[], previous: any, bindings: any[]) {
  const nodes: any[] = [], relations: any[] = [];
  const add = (uid: string, label: string, role: string, name: string, description: string, properties: any = {}) => {
    nodes.push({ uid, labels: label === 'AbstractNode' ? ['Concept', 'AbstractNode'] : [label], properties: {
      name, description, standard_graph_role: role, authority_class: 'SECONDARY_AI', ontology_authority_class_v1: 'SECONDARY_AI',
      ontology_kind_v1: label === 'Reference' ? 'DOCUMENT' : 'CONCEPT', ontology_domain_v1: 'ENGINEERING',
      ontology_plane_v1: 'RESEARCH_PROJECTION', ontology_canonical_scope_v1: 'PENDING_OR_PRELIMINARY',
      ontology_epistemic_state_v1: 'PENDING', ontology_record_lifecycle_v1: 'ACTIVE', ontology_review_required_v1: true,
      ontology_sensitivity_v1: 'NORMAL', responsibility_owner: 'hswm:research:dgx-frontier:2026-09-20',
      status: 'SOURCE_BOUND_SECONDARY_RESEARCH', claim_boundary: boundary,
      projection_nonclaim: 'NOT_CANONICAL_COGNITION_ROUTING_ADMISSION_OR_LEARNING', ...properties
    } }); return uid;
  };
  const link = (from_uid: string, type: string, to_uid: string, scope = 'BOUNDED_RESEARCH_PROJECTION') => relations.push({ from_uid, type, to_uid, authority_class: 'SECONDARY_AI', scope, status: 'SOURCE_BOUND_SECONDARY_RESEARCH' });
  const sourceMap = new Map<string, string>();
  const source = (location: string, name = location) => {
    if (sourceMap.has(location)) return sourceMap.get(location)!;
    const bound = bindings.find(b => b.path === location);
    const uid = add(id('Reference', digest(location).slice(0, 18)), 'Reference', 'RESEARCH_SOURCE', name,
      bound ? 'Exact repository artifact bytes.' : 'Official source location reviewed 2026-09-20; URL digest does not establish content identity.',
      { source_ref: location, ...(bound ? { source_sha256: bound.sha256 } : { source_location_sha256: digest(location) }) });
    sourceMap.set(location, uid); return uid;
  };
  const occurrence = (assertion: string, role: string, ordinal: number, target: string) => {
    const uid = add(id('AbstractNode', 'occ-' + digest(assertion + role + ordinal).slice(0, 18)), 'AbstractNode', 'ROLE_PARTICIPATION', role,
      'Ordered role occurrence retains participant identity and assertion scope.', { role_name: role, ordinal, participant_uid: target,
        assertion_uid: assertion, source_ref: artifactRoot + '/catalog.v1.json' });
    link(assertion, 'HAS_PARTICIPATION', uid); link(uid, 'REFERENCES', target);
  };
  add(root, 'AbstractNode', 'RESEARCH_PROGRAM', 'HSWM DGX 실험·최신 AI 도입 연구 2026-09-20',
    'Actual native durable semantic revision on DGX, preserved failed conditions, output-format controls and official-source model/tool qualification.',
    { source_ref: 'docs/research/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.md', cr_fcl_promotion: false });
  const priorRoot = previous.nodes.find((n: any) => n.uid === previous.bundle_uid);
  const anchors = [{ uid: previous.bundle_uid, name: priorRoot.properties.name, required_labels: priorRoot.labels }];
  link(root, 'DERIVED_FROM', previous.bundle_uid, 'CONTINUES_PRIOR_JEV_CHATGPT_DGX_RESEARCH_WITHOUT_REWRITING_IT');
  const identity = add(id('Claim', 'identity'), 'Claim', 'LITERATURE_CLAIM', 'HSWM 목표 정체성 및 증거 한계',
    'HSWM is one large AI, organized as a hypergraph neural network, using LLM functions as basic computation and operating through hypergraph Semantic Weight. The large hypergraph is AI state; the local LLM is an internal operator. This research is a bounded vertical slice, not the full target.',
    { source_ref: 'docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md', cr_fcl_promotion: false });
  for (const p of ['docs/canon/HSWM_CONSTITUTION_2026-08-20.md', 'docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md', 'docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md']) link(identity, 'DERIVED_FROM', source(p));
  link(root, 'HAS_CONCEPT', identity);
  for (const c of catalog.candidates) {
    const artifact = add(id('Concept', c.id), 'Concept', 'TOOL_OR_MODEL_CANDIDATE', c.name, c.reason, {
      source_ref: c.source, revision: c.revision, license: c.license, source_authority: c.authority,
      status: c.recommendation, installed_or_executed: c.installed_or_executed,
      ...(c.tensor_storage_lower_bound_bytes ? { tensor_storage_lower_bound_bytes: c.tensor_storage_lower_bound_bytes, memory_boundary: c.memory_caveat } : {}) });
    const obligation = add(id('ResearchQuestion', c.id), 'ResearchQuestion', 'OPEN_OBLIGATION', c.name + ' qualification', c.qualification,
      { source_ref: artifactRoot + '/catalog.v1.json', status: 'OPEN_NOT_EXECUTED', cr_fcl_promotion: false });
    const claim = add(id('Claim', c.id), 'Claim', 'RESEARCH_PROPOSAL', c.name + ': ' + c.recommendation, c.reason,
      { source_ref: artifactRoot + '/catalog.v1.json', limitation: c.qualification, status: 'CANDIDATE_NOT_INSTALLED_OR_VALIDATED' });
    const s = source(c.revision_url ?? c.source, c.name + ' official source');
    link(claim, 'DERIVED_FROM', s); link(claim, 'RELATES_TO', obligation); link(claim, 'ABOUT', artifact); link(root, 'HAS_CONCEPT', claim);
    occurrence(claim, 'candidate', 0, artifact); occurrence(claim, 'official_source', 1, s); occurrence(claim, 'qualification', 2, obligation);
  }
  for (const p of catalog.papers) {
    const claim = add(id('Claim', p.id), 'Claim', 'LITERATURE_CLAIM', p.title, p.finding,
      { source_ref: p.url, paper_date: p.date, pdf_url: p.pdf, transfer_boundary: p.transfer, status: 'PAPER_REPORTED_NOT_HSWM_TRANSFER' });
    link(claim, 'DERIVED_FROM', source(p.url, p.title)); link(root, 'HAS_CONCEPT', claim);
  }
  for (let i = 0; i < results.length; i++) {
    const r = results[i], slug = 'v' + (i + 1), ref = source(artifactRoot + '/observations.' + slug + '.json');
    const experiment = add(id('Experiment', slug), 'Experiment', 'EMPIRICAL_RUN', 'DGX semantic learning ' + slug,
      'Native prediction, caller-owned observed feedback, admitted semantic revision and fresh-process evaluation. Complete means execution/control completion, not scientific success.',
      { source_ref: artifactRoot + '/observations.' + slug + '.json', protocol_sha256: r.protocol_sha256,
        planned_trials: r.planned_trials, complete_trials: r.complete_trials, runtime_committed_learns: r.runtime_committed_learns,
        successful_http_responses: r.http.successfulResponses, prompt_tokens: r.http.prompt_tokens, completion_tokens: r.http.completion_tokens,
        status: i === 0 ? 'INSTRUMENT_AND_SERVING_FAILURE_PRESERVED' : i === 1 ? 'FORMAT_FAILURE_PRESERVED' : 'BOUNDED_OBSERVATION_NO_EFFICACY_PROMOTION', cr_fcl_promotion: false });
    link(experiment, 'DERIVED_FROM', ref); link(root, 'HAS_CONCEPT', experiment);
    for (const a of r.aggregates.filter((a: any) => a.total > 0)) {
      const uid = add(id('Claim', slug + '-' + a.arm), 'Claim', 'OBSERVED_RESULT', slug + ' ' + a.arm,
        'Held-out synthetic exact bit accuracy; malformed batch receives zero credit under the frozen protocol.',
        { source_ref: artifactRoot + '/observations.' + slug + '.json', model: a.model, arm: a.arm, n: a.total, correct: a.correct,
          batches: a.batches, valid_batches: a.validBatches, cr_fcl_promotion: false, status: 'MEASURED_SYNTHETIC_ONLY' });
      link(uid, 'DERIVED_FROM', ref); link(experiment, 'HAS_CONCEPT', uid);
      occurrence(uid, 'experiment', 0, experiment); occurrence(uid, 'observed_evidence', 1, ref); occurrence(uid, 'identity_boundary', 2, identity);
    }
  }
  for (const b of bindings) link(root, 'REFERENCES', source(b.path));
  return { schema_version: 'hswm-kg-bundle/v1', bundle_uid: root, status: 'SOURCE_BOUND_RESEARCH_PROJECTION',
    nonclaim: boundary, source_accessed_on: '2026-09-20', authority_boundary: 'SECONDARY_AI synthesis; USER_PRIMARY identity remains at its original source; no scientific promotion.',
    artifact_bindings: bindings, anchors, nodes, relations, expected_counts: { nodes: nodes.length, anchors: anchors.length, relations: relations.length } };
}
const main = Effect.gen(function* () {
  const paths = [artifactRoot + '/catalog.v1.json', ...[1, 2, 3].map(v => artifactRoot + `/observations.v${v}.json`),
    artifactRoot + '/environment.v1.json', artifactRoot + '/validation.v1.json',
    'docs/research/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.md', 'results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md',
    'docs/canon/HSWM_CONSTITUTION_2026-08-20.md', 'docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md',
    'docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md', 'docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md',
    'docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md', 'docs/research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md',
    'evidence/hswm_dgx_semantic_learning_2026-09-20/0eb4eb8b79c2a4abcb7fe7b220f48c5094e2a1aedfb99f87f9047f297692baed.json',
    '_research/dgx_semantic_learning_v1/attempt-source-map.v1.json', '_research/dgx_semantic_learning_v1/analyze.mts',
    ...[1, 2, 3].map(v => `_research/dgx_semantic_learning_v1/source-pins.v${v}.json`)];
  const raw = yield* Effect.all(paths.map(p => io(() => readFile(p))), { concurrency: 'unbounded' });
  const previous = JSON.parse(yield* io(() => readFile('ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json', 'utf8')));
  const bundle = construct(JSON.parse(raw[0]), [1, 2, 3].map(i => JSON.parse(raw[i])), previous,
    paths.map((path, i) => ({ path, sha256: digest(raw[i]) })));
  const bytes = JSON.stringify(bundle, null, 2) + '\n';
  Either.getOrThrowWith(decodeKgBundleSource({ sourceId: 'dgx-frontier', rawBytes: Buffer.from(bytes) }, 'v2'), (e: any) => e);
  const path = 'ontology/development/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.v1.json';
  yield* io(() => writeFile(path, bytes)); console.log(JSON.stringify({ path, sha256: digest(bytes), ...bundle.expected_counts }));
});
Effect.runPromise(main).catch((e: unknown) => { console.error(e); process.exitCode = 1; });
