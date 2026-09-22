/** Build a bounded, source-bound research projection. It never writes runtime state. */
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url));
const { Either } = require('effect');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const catalogPath = '_research/jev_graph_engineering_v1/catalog.v1.json';
const outputPath = 'ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json';
const sha256 = (value: Uint8Array | string) => createHash('sha256').update(value).digest('hex');
const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as Record<string, any>;
const old = JSON.parse(await readFile('ontology/development/HSWM_JEV_PRINCIPLES_2026-09-21.v1.json', 'utf8')) as Record<string, any>;
const bindings = await Promise.all(catalog.local_sources.map(async (path: string) => ({ path, sha256: sha256(await readFile(path)) })));
const uid = (kind: string, value: string) => `sym:${kind}:hswm-jev-ge-20260922-${value}`;
const node = (uid: string, label: string, role: string, name: string, description: string, extra: Record<string, unknown> = {}) => ({
  uid, labels: label === 'AbstractNode' ? ['Concept', 'AbstractNode'] : [label], properties: {
    name, description, standard_graph_role: role, authority_class: 'SECONDARY_AI',
    ontology_authority_class_v1: 'SECONDARY_AI', ontology_kind_v1: label === 'Reference' ? 'DOCUMENT' : 'CONCEPT',
    ontology_domain_v1: 'ENGINEERING', ontology_plane_v1: 'RESEARCH_PROJECTION',
    ontology_canonical_scope_v1: 'PENDING_OR_PRELIMINARY', ontology_epistemic_state_v1: 'PENDING',
    ontology_record_lifecycle_v1: 'ACTIVE', ontology_review_required_v1: true, ontology_sensitivity_v1: 'NORMAL',
    responsibility_owner: catalog.owner, status: 'SOURCE_BOUND_GRAPH_ENGINEERING_PLAN',
    claim_boundary: catalog.nonclaim, projection_nonclaim: 'NOT_CANONICAL_COGNITION_ROUTING_ADMISSION_OR_LEARNING',
    cr_fcl_promotion: false, ...extra
  }
});
const nodes: any[] = [], relations: any[] = [];
const add = (...args: Parameters<typeof node>) => { const value = node(...args); nodes.push(value); return value.uid; };
const link = (from_uid: string, type: string, to_uid: string, scope = 'SOURCE_BOUND_GRAPH_ENGINEERING') => relations.push({ from_uid, type, to_uid, authority_class: 'SECONDARY_AI', scope, status: 'SOURCE_BOUND_GRAPH_ENGINEERING_PLAN' });
const sourceNodes = new Map<string, string>();
const source = (path: string) => {
  const known = sourceNodes.get(path); if (known) return known;
  const binding = bindings.find((item: any) => item.path === path);
  if (!binding) throw new Error(`unbound local source ${path}`);
  const id = add(uid('Reference', sha256(path).slice(0, 18)), 'Reference', 'RESEARCH_SOURCE', path, 'Exact local artifact bytes.', { source_ref: path, source_sha256: binding.sha256 });
  sourceNodes.set(path, id); return id;
};
const standard = (entry: any) => {
  const id = add(uid('Reference', sha256(entry.url).slice(0, 18)), 'Reference', 'STANDARD_REFERENCE', entry.name,
    'Official standard location reviewed 2026-09-22; location digest is not content identity.',
    { source_ref: entry.url, source_location_sha256: sha256(entry.url), accessed_on: '2026-09-22', status: entry.status });
  return id;
};
const root = add(catalog.root_uid, 'AbstractNode', 'RESEARCH_PROGRAM', 'HSWM Jev standard graph engineering 2026-09-22',
  'Source-bound organization of inherited Jev findings, W3C graph exchange contracts and next research work; no runtime implementation or efficacy promotion.',
  { source_ref: 'docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md' });
for (const p of catalog.local_sources) link(root, 'REFERENCES', source(p));
link(root, 'DERIVED_FROM', source('docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md'));
for (const item of catalog.standards) link(root, 'REFERENCES', standard(item), 'OFFICIAL_STANDARD_REFERENCE');
const oldNode = new Map(old.nodes.map((item: any) => [item.uid, item]));
const anchorIds = ['sym:AbstractNode:hswm-jev-principles-2026-09-21', ...catalog.principles.map((item: any) => item.anchor), 'sym:Claim:hswm-jevp-20260921-no-semantic-change', 'sym:Concept:hswm-jevp-20260921-hyperon',
  'sym:ResearchQuestion:hswm-jevp-20260921-cr-0', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-1', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-2', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-3', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-4', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-5', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-6', 'sym:ResearchQuestion:hswm-jevp-20260921-cr-7',
  'sym:ResearchQuestion:hswm-jevp-20260921-fcl-1', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-2', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-3', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-4', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-5', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-6', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-7', 'sym:ResearchQuestion:hswm-jevp-20260921-fcl-8'];
const anchors = anchorIds.map((id: string) => { const found = oldNode.get(id); if (!found) throw new Error(`missing inherited anchor ${id}`); return { uid: id, name: found.properties.name, required_labels: found.labels }; });
link(root, 'DERIVED_FROM', 'sym:AbstractNode:hswm-jev-principles-2026-09-21', 'INHERITED_PRIOR_BUNDLE_ROOT_ANCHOR');
const mappingIds = new Map<string, string>();
for (const principle of catalog.principles) {
  const id = add(uid('Claim', principle.id.toLowerCase()), 'Claim', 'PRINCIPLE_MAPPING', `${principle.id} ${principle.role}`, principle.contract,
    { principle_id: principle.id, graph_engineering_role: principle.role, adopted_measurement_contract: principle.contract, unproven_hswm_extension: principle.extension, status: principle.status, source_ref: 'ontology/development/HSWM_JEV_PRINCIPLES_2026-09-21.v1.json' });
  link(id, 'ABOUT', principle.anchor, 'INHERITED_JEV_PRINCIPLE_ANCHOR'); link(id, 'DERIVED_FROM', source('ontology/development/HSWM_JEV_PRINCIPLES_2026-09-21.v1.json')); link(root, 'HAS_CONCEPT', id);
  mappingIds.set(principle.id, id);
}
const contractIds = new Map<string, string>();
for (const contract of catalog.data_contracts) {
  const id = add(uid('Concept', contract.id), 'Concept', 'GRAPH_DATA_CONTRACT', contract.name, contract.distinction,
    { contract_id: contract.id, minimum_fields: contract.minimum_fields, distinction: contract.distinction,
      owner_lineage_obligation: 'Persistent, revisable or recoverable relation/incidence records require one schema-relative owner and their own revision lineage; this is a proposed contract, not runtime implementation.',
      status: 'PROPOSED_DATA_DICTIONARY_NOT_RUNTIME_IMPLEMENTED', source_ref: 'docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md' });
  link(id, 'DERIVED_FROM', source('docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md')); link(root, 'HAS_CONCEPT', id); contractIds.set(contract.id, id);
}
const principleContracts: Readonly<Record<string, readonly string[]>> = {
  P1: ['relation_version', 'read_frame', 'decision_contract_candidate_set', 'execution_prediction'],
  P2: ['execution_prediction', 'outcome', 'calibration_artifact', 'revision_proposal_committed_revision'],
  P3: ['read_frame', 'execution_prediction', 'revision_proposal_committed_revision'],
  P4: ['read_frame', 'decision_contract_candidate_set'],
  P5: ['role_participation', 'decision_contract_candidate_set'],
  P6: ['relation_version', 'role_participation', 'revision_proposal_committed_revision']
};
for (const [principle, contracts] of Object.entries(principleContracts)) for (const contract of contracts) link(mappingIds.get(principle)!, 'RELATES_TO', contractIds.get(contract)!, 'PRINCIPLE_TO_PROPOSED_DATA_CONTRACT');
const negative = add(uid('Claim', 'negative'), 'Claim', 'INHERITED_NEGATIVE_EVIDENCE', 'Inherited negative: four revisions changed no semantic fields',
  'The 2026-09-21 audit observed four committed revisions with zero semantic-field changes and an oracle/local semantic-execution bottleneck. It is preserved, not rerouted into support.',
  { status: 'OBSERVED_NO_SEMANTIC_DELTA_AND_ORACLE_BOTTLENECK', source_ref: 'docs/research/artifacts/hswm_jev_principles_2026-09-21/audit.v1.json', reroute_rule: 'Do not use topology, batching or scale to rescue this upstream failure.' });
link(negative, 'DERIVED_FROM', source('docs/research/artifacts/hswm_jev_principles_2026-09-21/audit.v1.json')); link(negative, 'DERIVED_FROM', source('docs/research/artifacts/hswm_jev_principles_2026-09-21/observations.v1.json')); link(negative, 'DERIVED_FROM', source('results/HSWM_JEV_PRINCIPLES_2026-09-21.md')); link(negative, 'ABOUT', 'sym:Claim:hswm-jevp-20260921-no-semantic-change', 'INHERITED_NEGATIVE_ANCHOR'); link(root, 'HAS_CONCEPT', negative);
const workIds = new Map<string, string>();
const hyperon = add(uid('Concept', 'hyperon'), 'Concept', 'MANDATORY_COMPARATOR', 'OpenCog Hyperon comparator boundary',
  'Persistent metagraph and neural bridges are compared at the pinned audit maturity only; this graph neither executes Hyperon nor selects a backend.',
  { status: 'PINNED_PRIOR_AUDIT_NOT_EXECUTED_OR_ADOPTED', source_ref: 'docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md', metta_version: '0.2.10', source_commit: '3f76dc460da6961f57f69f6c3e550c59c74ada83' });
link(hyperon, 'DERIVED_FROM', source('docs/research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md')); link(hyperon, 'ABOUT', 'sym:Concept:hswm-jevp-20260921-hyperon', 'INHERITED_COMPARATOR_ANCHOR'); link(root, 'RELATES_TO', hyperon);
for (const work of catalog.work) {
  const id = add(uid('ResearchQuestion', work.id.toLowerCase()), 'ResearchQuestion', 'NEXT_WORK', `${work.id} ${work.name}`, work.dependencies,
    { work_id: work.id, priority: work.priority, dependencies: work.dependencies, failure_reroute: work.failure_reroute, related_obligations: work.related, status: 'PLANNED_NOT_STARTED', source_ref: 'docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md' });
  link(id, 'DERIVED_FROM', source('docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md')); link(id, 'RELATES_TO', negative, 'UPSTREAM_NEGATIVE_MUST_REMAIN_VISIBLE');
  for (const obligation of work.related.split(';').map((x: string) => x.trim())) link(id, 'RELATES_TO', `sym:ResearchQuestion:hswm-jevp-20260921-${obligation.toLowerCase()}`, 'RELATED_OPEN_OBLIGATION_NOT_PROMOTED');
  link(root, 'HAS_CONCEPT', id);
  workIds.set(work.id, id);
}
link(workIds.get('W2')!, 'DEPENDS_ON', workIds.get('W1')!, 'W1_EXECUTABLE_CONDITION_FOR_W2_LEARNING_EFFICACY_ONLY');
for (const prerequisite of ['W1', 'W2', 'W3']) link(workIds.get('W4')!, 'DEPENDS_ON', workIds.get(prerequisite)!, 'W1_W3_REQUIRED_CONDITIONS_BEFORE_JOINT_BATCHED_EXECUTION');
for (const prerequisite of ['W4', 'W2']) link(workIds.get('W5')!, 'DEPENDS_ON', workIds.get(prerequisite)!, 'LOCAL_LEARNING_AND_JOINT_EXECUTION_EVIDENCE_BEFORE_TWO_SCALE_WORK');
for (const [name, description] of [['Read contract', 'A local LLM receives relation text, ordered typed roles, context, exceptions and evidence under an explicitly bounded read scope.'], ['Write contract', 'A proposal is separate from a canonical write and has no admission, Permit or learning effect in this projection.'], ['Revision contract', 'Observed outcome, semantic disposition, evidence mass, routing score and causal credit remain distinct.'], ['Projection contract', 'RDF/PROV-O/SHACL/SPARQL are bounded read-only exchange and validation surfaces.']] as const) {
  const id = add(uid('Concept', sha256(name).slice(0, 14)), 'Concept', 'GRAPH_ENGINEERING_CONTRACT', name, description, { source_ref: 'docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md', status: 'ADOPTED_MEASUREMENT_OR_EXCHANGE_CONTRACT_NOT_RUNTIME_IMPLEMENTATION' });
  link(id, 'DERIVED_FROM', source('docs/research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md')); link(root, 'HAS_CONCEPT', id);
}
for (const item of nodes) {
  const properties = item.properties as Record<string, unknown>, reference = properties.source_ref;
  if (typeof reference === 'string' && !reference.startsWith('https://')) {
    const binding = bindings.find((candidate: any) => candidate.path === reference);
    if (!binding) throw new Error(`unbound local node source_ref ${reference}`);
    if (properties.source_sha256 !== undefined && properties.source_sha256 !== binding.sha256) throw new Error(`local node source hash drift ${reference}`);
    properties.source_sha256 = binding.sha256;
  }
}
const bundle = { schema_version: 'hswm-kg-bundle/v1', bundle_uid: catalog.root_uid, status: 'SOURCE_BOUND_RESEARCH_PROJECTION', nonclaim: catalog.nonclaim,
  source_accessed_on: '2026-09-22', authority_boundary: 'SECONDARY_AI graph-engineering organization; USER_PRIMARY authority remains in original sources.', artifact_bindings: bindings, expected_counts: { nodes: nodes.length, anchors: anchors.length, relations: relations.length }, anchors, nodes, relations };
const bytes = Buffer.from(JSON.stringify(bundle, null, 2) + '\n');
Either.getOrThrowWith(decodeKgBundleSource({ sourceId: 'jev_graph_engineering', rawBytes: bytes }, 'v2'), (error: any) => error);
await writeFile(outputPath, bytes, { flag: 'wx' });
console.log(JSON.stringify({ path: outputPath, sha256: sha256(bytes), ...bundle.expected_counts }));
