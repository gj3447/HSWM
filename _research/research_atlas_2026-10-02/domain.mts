/** Pure navigation model. Research summaries are attributed views, never learned HSWM state. */
import { createHash } from 'node:crypto';
import { posix } from 'node:path';
import { strict as assert } from 'node:assert';

export const cut = 'a7272a13cd6d304b7f8a1911dca0158e0bc67f29';
export const base = '_research/research_atlas_2026-10-02';
export const queryBase = 'ontology/queries/hswm_research_atlas_2026-10-02';
export const output = 'ontology/knowledge_map/HSWM_RESEARCH_ATLAS_2026-10-02.v1.json';
export const catalogPath = `${base}/catalog.v1.json`;
export const entityPath = `${base}/entities.v1.json`;
export const artifacts = 'docs/research/artifacts/hswm_research_atlas_2026-10-02';
export const topicPages = 'docs/research/atlas_2026-10-02';
export const sha = (x: string | Uint8Array) => createHash('sha256').update(x).digest('hex');
export const json = (x: unknown) => JSON.stringify(x, null, 2) + '\n';
export const uid = (key: string) => `sym:AbstractNode:hswm-research-atlas-20261002-${key}`;
export const bundleUid = uid('root');
export const sourceId = (path: string) => `source-${sha(path).slice(0, 24)}`;
export const mainResearch = (path: string) => /^docs\/research\/[^/]+\.md$/.test(path);
export const sourceKind = (path: string): string => {
  if (mainResearch(path)) return 'MAIN_RESEARCH';
  if (/^docs\/canon\/.*\.(md|txt)$/.test(path)) return 'CANON_SOURCE';
  if (/^docs\/research\/.*\.md$/.test(path)) return 'RESEARCH_SUPPORT';
  if (/^docs\/operations\/.*\.md$/.test(path)) return 'OPERATIONS_SOURCE';
  if (/^results\/.*\.md$/.test(path)) return 'RESULT_SOURCE';
  if (/^_findings\/.*\.(md|txt)$/.test(path)) return 'HISTORICAL_FINDING';
  if (/^(?:_research|research)\/.*\.md$/.test(path)) return 'EXPERIMENT_NOTE';
  if (/^formal\/.*\.lean$/.test(path)) return 'LEAN_MODULE';
  if (/^ontology\/.*\.json$/.test(path)) return 'ONTOLOGY_SOURCE';
  if (path === 'F1_R8_RESULTS_LOG.md') return 'RESEARCH_LOG';
  return 'TRACKED_ARTIFACT';
};
export const kinds = ['TARGET','THEORY','FORMAL','IMPLEMENTATION','PROTOCOL','PLAN','RESULT','REVIEW','HISTORY','NAVIGATION'];
export const facets = ['proof','implementation','experiment','negative','hypothesis','plan','protocol','philosophy','map','learning','comparison','operations','history'];

/** Exact UTF-8 spans; a heading section includes its descendants and stops at the next peer/ancestor. */
export function sections(bytes: Buffer) {
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  const headings: any[] = []; let offset = 0, fence: { marker: string; length: number } | null = null;
  for (const line of text.match(/.*(?:\r?\n|$)/g)!.filter(Boolean)) {
    const marker = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    const wasFenced = fence !== null;
    if (marker) {
      if (fence === null) fence = { marker: marker[1][0], length: marker[1].length };
      else if (fence.marker === marker[1][0] && marker[1].length >= fence.length && /^\s*$/.test(line.slice(marker[0].length))) fence = null;
    }
    if (!fence && !wasFenced) {
      const h = line.match(/^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*(?:\r?\n)?$/);
      if (h) h[2] = h[2].replace(/[ \t]+#+[ \t]*$/, '');
      if (h) headings.push({ id: `section-${offset}`, title: h[2], level: h[1].length, start_byte: offset });
    }
    offset += Buffer.byteLength(line);
  }
  assert.equal(offset, bytes.length);
  return [{ id: 'full', title: '원문 전체', level: 0, start_byte: 0, end_byte: bytes.length }, ...headings.map((h, index) => ({ ...h, end_byte: headings.slice(index + 1).find(n => n.level <= h.level)?.start_byte ?? bytes.length }))];
}

/** Extract explicit local Markdown links only. They are citations, never dependency or support judgments. */
export function citations(path: string, text: string, paths: Set<string>) {
  const found: any[] = [], seen = new Set<string>();
  for (const m of text.matchAll(/\[[^\]\n]*\]\(([^)\n]+)\)/g)) {
    const raw = m[1].replace(/^<|>$/g, '').split(/\s+"/)[0];
    if (/^[a-z][a-z0-9+.-]*:/i.test(raw) || raw.startsWith('#') || raw.startsWith('/')) continue;
    const [file, fragment] = raw.split('#', 2); let decoded: string;
    try { decoded = decodeURIComponent(file); } catch { continue; }
    const target = posix.normalize(posix.join(posix.dirname(path), decoded));
    if (target.startsWith('../') || !target) continue;
    const key = `${target}#${fragment ?? ''}`; if (seen.has(key)) continue; seen.add(key);
    found.push({ path: target, fragment: fragment ?? '', status: paths.has(target) ? 'AT_SOURCE_CUT' : 'UNRESOLVED_AT_SOURCE_CUT', relation: 'EXPLICIT_CITATION_NOT_DEPENDENCY' });
  }
  return found;
}

export function validateCuration(records: any[], topics: any[], files: Map<string, Buffer>) {
  const expected = [...files.keys()].filter(mainResearch).sort();
  assert.deepEqual(records.map(r => r.path).sort(), expected, 'Every main research document must occur exactly once, with no duplicates or additions');
  const topicIds = new Set(topics.map(t => t.id));
  for (const r of records) {
    for (const key of ['path','title','summary','kind','source_status','locator','boundary']) assert(typeof r[key] === 'string' && r[key].trim().length > 0, `Missing ${key}: ${r.path}`);
    assert(kinds.includes(r.kind), `Unknown kind: ${r.path}`);
    assert(Array.isArray(r.topics) && r.topics.length && new Set(r.topics).size === r.topics.length && r.topics.every(t => topicIds.has(t)), `Invalid topic placement: ${r.path}`);
    assert(Array.isArray(r.facets) && new Set(r.facets).size === r.facets.length && r.facets.every(f => facets.includes(f)), `Invalid facet: ${r.path}`);
    assert(files.get(r.path)!.toString().includes(r.locator), `Absent source locator: ${r.path}`);
  }
}

export function makeCatalog(tree: any[], files: Map<string, Buffer>, records: any[], topics: any[]) {
  validateCuration(records, topics, files);
  const curated = new Map(records.map(r => [r.path, r])), pathSet = new Set(files.keys());
  const all = tree.map(t => ({ id: sourceId(t.path), ...t, sha256: sha(files.get(t.path)!), bytes: files.get(t.path)!.length, source_kind: sourceKind(t.path),
    native_binding_compatible: /^[A-Za-z0-9_][A-Za-z0-9_./:+-]{0,255}$/.test(t.path) }));
  assert.equal(new Set(all.map(r => r.id)).size, all.length, 'Truncated identifier collision');
  const documents = all.filter(r => r.source_kind !== 'TRACKED_ARTIFACT').map(row => {
    const bytes = files.get(row.path)!, text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    const spans = /\.(md|txt)$/.test(row.path) ? sections(bytes) : [{ id: 'full', title: '원문 전체', level: 0, start_byte: 0, end_byte: bytes.length }];
    const c = curated.get(row.path), links = row.path.endsWith('.md') ? citations(row.path, text, pathSet) : [];
    return { ...row, title: c?.title ?? spans.find(s => s.level === 1)?.title ?? row.path,
      curation_status: c ? 'AI_SOURCE_BOUND_SUMMARY' : 'SOURCE_STRUCTURE_INDEX_ONLY',
      ...(c ? { curation: c } : {}), sections: spans, citations: links };
  });
  const indexedPaths = new Set(documents.map(d => d.path));
  const citationRows = documents.flatMap(d => d.citations.map(c => ({ ...c, from: d.path })));
  const projectedRows = citationRows.filter(c => indexedPaths.has(c.path));
  return { schema_version: 'hswm-research-atlas-catalog/v1', source_revision: cut, recorded_on: '2026-10-02',
    scope: 'All tracked paths inventoried; all main docs/research/*.md content-curated; declared text/Lean/ontology corpus structurally indexed. Post-cut curation and tooling separately SHA-bound. No exhaustive claim truth audit.',
    source_event_time: 'NOT_INFERRED_FROM_FILENAME_OR_INGESTION',
    topics, files: all, documents, coverage: { tracked_files: all.length, curated_documents: records.length, indexed_documents: documents.length,
      sections: documents.reduce((n, d) => n + d.sections.length, 0), resolved_citations: citationRows.filter(c => c.status === 'AT_SOURCE_CUT').length, unresolved_citations: citationRows.filter(c => c.status !== 'AT_SOURCE_CUT').length,
      resolved_citations_outside_document_index: citationRows.filter(c => c.status === 'AT_SOURCE_CUT' && !indexedPaths.has(c.path)).length,
      graph_citation_pairs_between_indexed_documents: new Set(projectedRows.map(c => `${c.from}|${c.path}`)).size,
      graph_citation_fragment_collapse: projectedRows.length - new Set(projectedRows.map(c => `${c.from}|${c.path}`)).size } };
}

/** Keep exact owned-node occurrences. An identical UID in several snapshots is not merged into one claim. */
export function makeEntityIndex(catalog: any, files: Map<string, Buffer>) {
  const occurrences: any[] = [], bundles: any[] = [];
  for (const row of catalog.documents.filter(d => d.source_kind === 'ONTOLOGY_SOURCE')) {
    const b = JSON.parse(files.get(row.path)!.toString());
    const nodes = Array.isArray(b.nodes) ? b.nodes : [];
    bundles.push({ path: row.path, sha256: row.sha256, bundle_uid: b.bundle_uid ?? null, schema: b.schema_version ?? null, node_count: nodes.length, declared_relation_count: Array.isArray(b.relations) ? b.relations.length : null, interpretation: 'ORIGINAL_SOURCE_FORMAT_NOT_AUTOMATIC_NATIVE_V2_CONFORMANCE' });
    for (const [index, n] of nodes.entries()) if (typeof n.uid === 'string') {
      const p = n.properties ?? n;
      occurrences.push({ uid: n.uid, path: row.path, pointer: `/nodes/${index}`, name: p.name ?? p.title ?? n.uid,
        labels: Array.isArray(n.labels) ? n.labels : [], source_role: p.standard_graph_role ?? 'UNSPECIFIED',
        source_authority: p.authority_class ?? b.authority ?? 'UNSPECIFIED', source_status: p.status ?? p.epistemic_state ?? 'UNSPECIFIED', source_sha256: row.sha256 });
    }
  }
  return { schema_version: 'hswm-research-atlas-entity-index/v1', source_revision: cut,
    interpretation: 'Source-scoped UID occurrences, not a live graph or identity merge; select a source path before resolving multiple occurrences.', bundles, occurrences };
}

export function construct(catalog: any, records: any[], oldTopics: any, bindings: any[]) {
  const nodes: any[] = [], relations: any[] = [], anchors: any[] = [];
  const boundary = 'SOURCE_BOUND_MULTISCALE_NAVIGATION_NOT_HSWM_RUNTIME_OR_EFFICACY';
  const add = (id: string, role: string, name: string, description: string, props: any = {}) => {
    nodes.push({ uid: id, labels: ['AbstractNode'], properties: { name, description, standard_graph_role: role,
      authority_class: 'SECONDARY_AI', canonical_scope: 'PENDING_OR_PRELIMINARY', ontology_plane: 'INQUIRY',
      recorded_on: '2026-10-02', actor: 'agent:codex', responsibility_owner: 'hswm:research-atlas:2026-10-02',
      source_revision: cut, claim_boundary: boundary, projection_nonclaim: boundary, runtime_write_path: false,
      status: 'SOURCE_BOUND_NAVIGATION', ...props } }); return id;
  };
  const keys = new Set<string>();
  const link = (a: string, type: string, b: string, scope: string) => {
    const key = `${a}|${type}|${b}`; if (keys.has(key)) return; keys.add(key);
    relations.push({ from_uid: a, to_uid: b, type, scope, authority_class: 'SECONDARY_AI', status: 'PROPOSED' });
  };
  const topicUid = (id: string) => uid(`topic-${id}`), sourceUid = (id: string) => uid(id);
  add(bundleUid, 'RESEARCH_ATLAS', 'HSWM 다중 해상도 연구 지도', '기존 주제에서 연구 요약·역할 있는 배치·정확한 원문으로 이동하는 조회용 지도.', { ...catalog.coverage, curation_complete_for_declared_main_corpus: true, full_semantic_audit: false });
  for (const topic of catalog.topics) {
    const old = oldTopics.nodes.find(n => n.uid.endsWith(`-topic-${topic.id}`)); assert(old);
    anchors.push({ uid: old.uid, name: old.properties.name, required_labels: old.labels });
    const id = add(topicUid(topic.id), 'TOPIC_VIEW', topic.title, topic.description, { topic_id: topic.id, map_resolution: 'TOPIC', historical_questions: topic.open_questions, question_status_as_of: '2026-09-13' });
    link(bundleUid, 'HAS_VIEW', id, 'TOPIC_VIEW_NOT_SYSTEM_PARTITION'); link(id, 'REFERENCES', old.uid, 'EXISTING_TOPIC_IDENTITY');
  }
  for (const doc of catalog.documents) {
    add(sourceUid(doc.id), 'SOURCE_VIEW', doc.title, '고정 Git revision의 원문과 구조 색인. 원문 내용의 진실성이나 실행 권한을 보증하지 않는다.', {
      source_id: doc.id, source_path: doc.path, source_sha256: doc.sha256, source_bytes: doc.bytes,
      git_blob_oid: doc.git_blob_oid, source_kind: doc.source_kind, curation_status: doc.curation_status,
      source_binding_mode: doc.native_binding_compatible ? 'DIRECT_NATIVE_ARTIFACT_BINDING' : 'SHA256_BOUND_CATALOG_TO_EXACT_GIT_BYTES',
      map_resolution: 'ORIGINAL_SOURCE', sections_count: doc.sections.length, event_date: 'UNKNOWN_NOT_INFERRED'
    });
    // No automatic whole-corpus fan-out in the local reader; this is membership metadata only.
    link(bundleUid, 'HAS_SOURCE', sourceUid(doc.id), 'CORPUS_MEMBERSHIP_NOT_AUTOMATIC_ACTIVATION');
  }
  const docs = new Map(catalog.documents.map(d => [d.path, d]));
  for (const record of records) {
    const doc: any = docs.get(record.path), id = uid(`unit-${doc.id}`);
    add(id, 'RESEARCH_UNIT', record.title, record.summary, { source_path: doc.path, record_kind: record.kind,
      source_status: record.source_status, source_locator: record.locator, source_sha256: doc.sha256,
      claim_boundary: record.boundary, map_resolution: 'ATTRIBUTED_SUMMARY', facets: record.facets,
      summary_authority: 'SECONDARY_AI', source_authority: 'READ_ORIGINAL_AUTHORITY_NO_INHERITANCE',
      loss_boundary: 'Summary omits detailed assumptions, exceptions, numbers and proof bodies; consult the pinned source before substantive use.' });
    link(id, 'SUMMARIZES', sourceUid(doc.id), 'LOSSY_AI_SUMMARY_WITH_EXACT_ORIGINAL_FALLBACK');
    for (const t of record.topics) {
      const binding = add(uid(`binding-${doc.id}-${t}`), 'MAP_BINDING', `${record.title} @ ${t}`, '같은 연구 단위의 문맥별 배치. 주제·요약·원문은 서로 다른 참여 역할이다.', {
        topic_id: t, source_path: doc.path, context_facets: record.facets, participant_ordering: 'UNORDERED_DISTINCT_ROLES',
        mapping_semantics: 'NAVIGATION_RELEVANCE_NOT_EQUIVALENCE_OR_DEPENDENCY', map_resolution: 'PLACEMENT'
      });
      link(binding, 'IN_TOPIC', topicUid(t), 'ROLE_TOPIC'); link(binding, 'HAS_UNIT', id, 'ROLE_SUMMARY'); link(binding, 'HAS_ORIGINAL', sourceUid(doc.id), 'ROLE_ORIGINAL');
    }
  }
  for (const doc of catalog.documents) for (const c of doc.citations) if (docs.has(c.path)) {
    link(sourceUid(doc.id), 'CITES', sourceUid((docs.get(c.path) as any).id), 'EXPLICIT_DOCUMENT_CITATION_NOT_SUPPORT_OR_REQUIRES');
  }
  return { schema_version: 'hswm-research-atlas/v1', bundle_uid: bundleUid, status: 'SOURCE_BOUND_MULTISCALE_NAVIGATION',
    nonclaim: boundary, source_accessed_on: '2026-10-02', authority_boundary: 'All new interpretations are SECONDARY_AI; originals and previous claims retain their own authority. No learned W, live KG write, permit or efficacy inference.',
    artifact_bindings: bindings, expected_counts: { nodes: nodes.length, anchors: anchors.length, relations: relations.length }, anchors, nodes, relations };
}

export function selectUnits(catalog: any, options: { topic?: string; facet?: string; query?: string } = {}) {
  if (options.topic) assert(catalog.topics.some(t => t.id === options.topic), 'Unknown topic');
  if (options.facet) assert(facets.includes(options.facet), 'Unknown facet');
  const tokens = options.query?.toLocaleLowerCase('en').split(/\s+/).filter(Boolean) ?? [];
  return catalog.documents.filter(d => d.curation).filter(d => !options.topic || d.curation.topics.includes(options.topic)).filter(d => !options.facet || d.curation.facets.includes(options.facet)).filter(d => {
    const text = `${d.path} ${d.title} ${d.curation.summary} ${d.curation.source_status} ${d.curation.boundary}`.toLocaleLowerCase('en');
    return tokens.every(t => text.includes(t));
  });
}

export function localContext(catalog: any, options: any, budget: number) {
  assert(Number.isSafeInteger(budget) && budget > 0 && budget <= 1_000_000, 'Budget must be 1..1000000 UTF-8 bytes');
  assert(options.topic || options.facet || options.query?.trim(), 'Context needs an explicit topic, facet or query; whole-corpus activation is not implicit');
  const docs = selectUnits(catalog, options);
  const items = docs.map(d => ({ id: d.id, path: d.path, title: d.title, summary: d.curation.summary, status: d.curation.source_status, boundary: d.curation.boundary, source_sha256: d.sha256, original_bytes: d.bytes, original_command: `node ${base}/cli.mts read ${d.id} full`, sections_command: `node ${base}/cli.mts show ${d.id}` }));
  const bytes = Buffer.byteLength(json(items));
  return { status: bytes <= budget ? 'SUMMARY_CONTEXT_READY' : 'NEEDS_NARROWING', selection: options,
    candidates: items.length, required_bytes: bytes, budget_bytes: budget,
    original_bytes: docs.reduce((n, d) => n + d.bytes, 0),
    selection_method: 'EXPLICIT_CURATED_TOPIC_AND_FACET_WITH_OPTIONAL_LEXICAL_CONJUNCTION_NOT_SEMANTIC_WEIGHT',
    claim_boundary: 'Navigation summary only; no original has been activated, no required-evidence closure or scientific truth is certified.',
    items: bytes <= budget ? items : [], omitted_to_fit: false };
}
