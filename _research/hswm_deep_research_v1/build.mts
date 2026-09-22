/** Source-bound deep-research graph compiler; never implements or mutates HSWM runtime state. */
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url));
const { Either } = require('effect');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const sha = (value: Uint8Array | string) => createHash('sha256').update(value).digest('hex');
const catalogPath = '_research/hswm_deep_research_v1/catalog.v1.json';
const outputPath = 'ontology/development/HSWM_DEEP_RESEARCH_2026-09-22.v1.json';
const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as Record<string, any>;
const previous = JSON.parse(await readFile('ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json', 'utf8')) as Record<string, any>;
const bindings = await Promise.all(catalog.local_sources.map(async (path: string) => ({ path, sha256: sha(await readFile(path)) })));
const uid = (kind: string, value: string) => `sym:${kind}:hswm-deep-20260922-${value}`;
const nodes: any[] = [], relations: any[] = [];
const add = (id: string, label: string, role: string, name: string, description: string, more: Record<string, unknown> = {}) => {
  nodes.push({ uid: id, labels: label === 'AbstractNode' ? ['Concept', 'AbstractNode'] : [label], properties: {
    name, description, standard_graph_role: role, authority_class: 'SECONDARY_AI', ontology_authority_class_v1: 'SECONDARY_AI',
    ontology_kind_v1: label === 'Reference' ? 'DOCUMENT' : 'CONCEPT', ontology_domain_v1: 'ENGINEERING', ontology_plane_v1: 'RESEARCH_PROJECTION',
    ontology_canonical_scope_v1: 'PENDING_OR_PRELIMINARY', ontology_epistemic_state_v1: 'PENDING', ontology_record_lifecycle_v1: 'ACTIVE', ontology_review_required_v1: true, ontology_sensitivity_v1: 'NORMAL',
    responsibility_owner: catalog.owner, status: 'SOURCE_BOUND_DEEP_RESEARCH', claim_boundary: catalog.nonclaim,
    projection_nonclaim: 'NOT_CANONICAL_COGNITION_ROUTING_ADMISSION_OR_LEARNING', cr_fcl_promotion: false, ...more } }); return id;
};
const link = (from_uid: string, type: string, to_uid: string, scope = 'SOURCE_BOUND_DEEP_RESEARCH') => relations.push({ from_uid, type, to_uid, authority_class: 'SECONDARY_AI', scope, status: 'SOURCE_BOUND_DEEP_RESEARCH' });
const sourceIds = new Map<string, string>();
const source = (path: string) => { const existing = sourceIds.get(path); if (existing) return existing; const binding = bindings.find((x: any) => x.path === path); if (!binding) throw new Error(`unbound source ${path}`); const id = add(uid('Reference', sha(path).slice(0, 18)), 'Reference', 'RESEARCH_SOURCE', path, 'Exact local source bytes.', { source_ref: path, source_sha256: binding.sha256 }); sourceIds.set(path, id); return id; };
const root = add(catalog.root_uid, 'AbstractNode', 'RESEARCH_PROGRAM', 'HSWM deep research and realization 2026-09-22', 'Source-bound research synthesis and next-work map; not a runtime implementation or efficacy result.', { source_ref: 'docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md' });
for (const path of catalog.local_sources) link(root, 'REFERENCES', source(path));
link(root, 'DERIVED_FROM', source('docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md'));
const priorNodes = new Map(previous.nodes.map((x: any) => [x.uid, x]));
const anchorIds = ['sym:AbstractNode:hswm-jev-graph-engineering-2026-09-22', 'sym:Claim:hswm-jev-ge-20260922-negative'];
const anchors = anchorIds.map(id => { const node = priorNodes.get(id); if (!node) throw new Error(`missing prior anchor ${id}`); return { uid: id, name: node.properties.name, required_labels: node.labels }; });
link(root, 'DERIVED_FROM', 'sym:AbstractNode:hswm-jev-graph-engineering-2026-09-22', 'INHERITED_PRIOR_RESEARCH_ANCHOR');
const sourceCatalogPaths = [
  'docs/research/artifacts/hswm_deep_research_2026-09-22/learning-sources.v1.json',
  'docs/research/artifacts/hswm_deep_research_2026-09-22/state-composition-sources.v1.json',
  'docs/research/artifacts/hswm_deep_research_2026-09-22/synthesis-sources.v1.json'
];
const sourceCatalogs = await Promise.all(sourceCatalogPaths.map(async (path) => ({ path, value: JSON.parse(await readFile(path, 'utf8')) as Record<string, any> })));
const seenExternalSources = new Set<string>();
for (const { path: catalogSource, value } of sourceCatalogs) {
  for (const item of value.sources ?? []) {
    const isPrimary = item.authority === 'PRIMARY_RESEARCH_PAPER' || String(item.kind).startsWith('primary_') || catalogSource.endsWith('/learning-sources.v1.json');
    if (!isPrimary || seenExternalSources.has(item.id)) continue;
    seenExternalSources.add(item.id);
    const name = item.title ?? item.citation;
    const version = item.version ?? item.version_or_date ?? item.publication_status ?? item.citation;
    if (!name || !version || !item.official_url && !item.url) throw new Error(`incomplete primary source metadata ${item.id}`);
    const id = add(uid('Reference', item.id), 'Reference', 'PRIMARY_PAPER_SOURCE', name, 'Metadata-only primary research source; no result or implementation adoption is asserted by this projection.', {
      source_ref: item.official_url ?? item.url, source_version: version, source_status: item.status ?? item.publication_status ?? 'PRIMARY_RESEARCH_PAPER', source_sections: item.sections ?? item.scope_read,
      source_maturity: 'PRIMARY_RESEARCH_SOURCE_SEE_PUBLICATION_METADATA', source_catalog: catalogSource, source_citation: item.citation ?? item.title, metadata_only: true
    });
    link(root, 'REFERENCES', id, 'PRIMARY_SOURCE_METADATA');
    link(id, 'DERIVED_FROM', source(catalogSource), 'SOURCE_CATALOG_LINEAGE');
  }
}
const hyperonNames: Record<string, string> = {
  'hyperon-whitepaper-2026': 'Hyperon Whitepaper 2026',
  'hyperon-experimental-release': 'hyperon-experimental release v0.2.10'
};
const stateCatalog = sourceCatalogs.find((item) => item.path.endsWith('/state-composition-sources.v1.json'))!.value;
for (const item of stateCatalog.sources.filter((x: any) => Object.hasOwn(hyperonNames, x.id))) {
  const id = add(uid('Reference', item.id), 'Reference', 'OFFICIAL_COMPARATOR_SOURCE', hyperonNames[item.id], 'Metadata-only mandatory Hyperon comparator source; architecture, implementation, and benchmark maturity remain distinct.', {
    source_ref: item.url, source_version: item.version, source_commit: item.commit, source_status: item.status, source_release_status: item.reviewed_release_status, source_sections: item.sections,
    source_maturity: item.reviewed_release_status ?? 'OFFICIAL_ARCHITECTURE_SOURCE', source_catalog: 'docs/research/artifacts/hswm_deep_research_2026-09-22/state-composition-sources.v1.json', metadata_only: true
  });
  link(root, 'REFERENCES', id, 'MANDATORY_HYPERON_COMPARATOR_METADATA');
  link(id, 'DERIVED_FROM', source('docs/research/artifacts/hswm_deep_research_2026-09-22/state-composition-sources.v1.json'), 'SOURCE_CATALOG_LINEAGE');
}
const negative = add(uid('Claim', 'inherited-negative'), 'Claim', 'INHERITED_NEGATIVE_EVIDENCE', 'Inherited JEV result: no semantic delta and oracle local-execution bottleneck', 'Four committed revisions changed no visible semantic fields; oracle direct readout was 27/48 in the bounded JEV audit. This remains a negative starting point.', { source_ref: 'docs/research/artifacts/hswm_deep_research_2026-09-22/mechanism-audit.md', reroute_rule: 'Do not use topology, batching, scale or candidate revision to rescue upstream local-execution failure.', status: 'INHERITED_NEGATIVE_NOT_EFFICACY' });
link(negative, 'DERIVED_FROM', source('docs/research/artifacts/hswm_deep_research_2026-09-22/mechanism-audit.md')); link(negative, 'ABOUT', 'sym:Claim:hswm-jev-ge-20260922-negative', 'INHERITED_NEGATIVE_ANCHOR'); link(root, 'HAS_CONCEPT', negative);
const findings = [
  ['local-execution-audit', 'Local code-confirmed finding: direct oracle is not a representation oracle', 'The sealed JEV path reads a frozen model next-token decision under an oracle-written relation; it does not execute a deterministic relation evaluator.', 'docs/research/artifacts/hswm_deep_research_2026-09-22/mechanism-audit.md'],
  ['revision-audit', 'Local code-confirmed finding: identity revisions are structurally admitted', 'The audited runtime accepted shape-valid identity proposals; semantic learning mediation was not demonstrated.', 'docs/research/artifacts/hswm_deep_research_2026-09-22/mechanism-audit.md']
];
for (const [slug, name, description, path] of findings) { const id = add(uid('Claim', slug), 'Claim', 'LOCAL_CODE_CONFIRMED_FINDING', name, description, { source_ref: path, status: 'CODE_CONFIRMED_SCOPE_BOUND' }); link(id, 'DERIVED_FROM', source(path)); link(id, 'ABOUT', negative); link(root, 'HAS_CONCEPT', id); }
const workIds = new Map<string, string>();
for (const work of catalog.work) { const id = add(uid('ResearchQuestion', work.id.toLowerCase()), 'ResearchQuestion', 'RESEARCH_DECISION', `${work.id} ${work.name}`, work.decision, { work_id: work.id, priority: work.priority, decision: work.decision, failure_reroute: work.reroute, related_obligations: work.related, obligation_boundary: 'Historical source-bound reference only; no current global status or promotion is asserted.', status: work.status, source_ref: 'docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md' }); link(id, 'DERIVED_FROM', source('docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md')); link(id, 'RELATES_TO', negative, 'PRIOR_NEGATIVE_REMAINS_VISIBLE'); link(root, 'HAS_CONCEPT', id); workIds.set(work.id, id); }
link(workIds.get('W2')!, 'DEPENDS_ON', workIds.get('W1')!, 'W1_EXECUTION_FIDELITY_REQUIRED_BEFORE_REVISION_EFFICACY');
link(workIds.get('W3')!, 'DEPENDS_ON', workIds.get('W1')!, 'W1_EXECUTION_READINESS_REQUIRED');
link(workIds.get('W3')!, 'DEPENDS_ON', workIds.get('W2')!, 'W2_LEARNING_CLAIM_BOUNDARY_REQUIRED');
link(workIds.get('W4')!, 'DEPENDS_ON', workIds.get('W1')!, 'LOCAL_EXECUTION_REQUIRED');
link(workIds.get('W4')!, 'DEPENDS_ON', workIds.get('W2')!, 'REVISION_EFFECT_BOUNDARY_REQUIRED');
link(workIds.get('W4')!, 'DEPENDS_ON', workIds.get('W3')!, 'READ_SUFFICIENCY_REQUIRED');
link(workIds.get('W5')!, 'DEPENDS_ON', workIds.get('W2')!, 'REVISION_EFFECT_BOUNDARY_REQUIRED');
link(workIds.get('W5')!, 'DEPENDS_ON', workIds.get('W4')!, 'JOINT_LAW_REQUIRED');
for (const work of catalog.work) { const id = add(uid('Experiment', work.id.toLowerCase()), 'Experiment', 'EMPIRICAL_EXPERIMENT_NOT_RUN', `${work.id} empirical protocol`, `No experiment has run. Proposed scope: ${work.decision}`, { work_id: work.id, status: 'NOT_RUN', source_ref: 'docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md' }); link(id, 'DERIVED_FROM', source('docs/research/HSWM_DEEP_RESEARCH_AND_REALIZATION_2026-09-22.md')); link(id, 'ABOUT', workIds.get(work.id)!); link(root, 'HAS_CONCEPT', id); }
for (const node of nodes) { const p = node.properties as Record<string, unknown>; if (typeof p.source_ref === 'string' && !p.source_ref.startsWith('https://')) { const b = bindings.find((x: any) => x.path === p.source_ref); if (!b) throw new Error(`unbound local node source ${p.source_ref}`); p.source_sha256 = b.sha256; } }
const bundle = { schema_version: 'hswm-kg-bundle/v1', bundle_uid: catalog.root_uid, status: 'SOURCE_BOUND_RESEARCH_PROJECTION', nonclaim: catalog.nonclaim, source_accessed_on: '2026-09-22', authority_boundary: 'SECONDARY_AI research organization; USER_PRIMARY identity remains in original canon.', artifact_bindings: bindings, expected_counts: { nodes: nodes.length, anchors: anchors.length, relations: relations.length }, anchors, nodes, relations };
const bytes = Buffer.from(JSON.stringify(bundle, null, 2) + '\n'); Either.getOrThrowWith(decodeKgBundleSource({ sourceId: 'deep_research', rawBytes: bytes }, 'v2'), (error: any) => error); await writeFile(outputPath, bytes, { flag: 'wx' }); console.log(JSON.stringify({ path: outputPath, sha256: sha(bytes), ...bundle.expected_counts }));
