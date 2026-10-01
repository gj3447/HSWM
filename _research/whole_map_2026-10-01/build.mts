/** Dated navigation projection; Git objects are the evidence boundary, never a live store. */
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import { strict as assert } from 'node:assert';
const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
export const root = fileURLToPath(new URL('../../', import.meta.url));
export const cut = 'df687475622e0a251a6c0c9124a9f3c92c0b42f3';
export const base = '_research/whole_map_2026-10-01';
export const queryBase = 'ontology/queries/hswm_whole_map_2026-10-01';
export const output = 'ontology/knowledge_map/HSWM_WHOLE_MAP_2026-10-01.v1.json';
export const corpusPath = `${base}/corpus.v1.json`;
export const artifactBase = 'docs/research/artifacts/hswm_whole_map_2026-10-01';
export const uid = (key: string) => `sym:AbstractNode:hswm-whole-map-20261001-${key}`;
export const bundleUid = uid('root');
export const sha = (bytes: string | Uint8Array) => createHash('sha256').update(bytes).digest('hex');
export const json = (value: unknown) => JSON.stringify(value, null, 2) + '\n';
export const io = <A>(op: () => Promise<A>) => Effect.tryPromise({ try: op, catch: (e: unknown) => new Error(String(e)) });
const git = (args: string[], input?: string) => io(() => new Promise<Buffer>((ok, fail) => {
  const p = spawn('git', args, { cwd: root, stdio: ['pipe', 'pipe', 'pipe'] });
  const out: Buffer[] = [], err: Buffer[] = [];
  p.stdout.on('data', x => out.push(x)); p.stderr.on('data', x => err.push(x));
  p.on('error', fail); p.stdin.on('error', fail);
  p.on('close', code => code === 0 ? ok(Buffer.concat(out)) : fail(new Error(`git ${args[0]}: ${Buffer.concat(err)}`)));
  p.stdin.end(input);
}));
const topicsPath = 'ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json';
const oldMapPath = 'ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_2026-09-13.v1.json';
const researchPath = 'ontology/development/HSWM_RESEARCH_MAP_2026-09-30.v1.json';
const crosswalk: Record<string, string[]> = {
  identity: ['target_identity_and_authority'], semantics: ['conceptual_c1_c3_and_conditional_capabilities'],
  execution: ['native_effect_runtime_and_ice'], learning: ['relation_learning_ru1_and_llm_calibration', 'learning_literature_and_frontier_baselines'],
  map: ['fractal_composition_and_philosophy'], composition: ['fractal_composition_and_philosophy'],
  proof: ['constructive_realizability_and_proof'], evaluation: ['opaque_identifiability_and_negative_results', 'causal_composition_experiment_spine'],
  ecosystem: ['research_coordination_and_usl_interfaces']
};
export function validateRecord(r: any, topics: any[], files: Map<string, Buffer>) {
  assert(topics.some(t => t.id === r.topic), `Unknown topic: ${r.topic}`);
  assert(r.source_locator?.length > 0 && files.get(r.source_path)?.toString().includes(r.source_locator), `Missing locator: ${r.key}`);
  for (const p of r.support_paths ?? []) assert(files.has(p), `Missing support: ${p}`);
  for (const k of ['key', 'title', 'statement', 'kind', 'claim_boundary', 'source_status']) assert(typeof r[k] === 'string' && r[k].length > 0, `Missing ${k}`);
  assert.equal(typeof r.negative, 'boolean');
}
export const loadInputs = () => Effect.gen(function* () {
  const treeBytes: Buffer = yield* git(['ls-tree', '-r', '-z', cut]);
  const tree = treeBytes.toString().split('\0').filter(Boolean).map(row => {
    const [meta, path] = row.split('\t'); const [mode, type, oid] = meta.split(' ');
    assert.equal(type, 'blob', 'This snapshot profile has no submodule expansion');
    return { path, mode, git_blob_oid: oid };
  }).sort((a, b) => a.path.localeCompare(b.path, 'en'));
  const oids = [...new Set(tree.map(t => t.git_blob_oid))];
  const batch: Buffer = yield* git(['cat-file', '--batch'], oids.join('\n') + '\n');
  const blobs = new Map<string, Buffer>(); let at = 0;
  for (const oid of oids) {
    const end = batch.indexOf(10, at), [actual, type, size] = batch.subarray(at, end).toString().split(' ');
    assert.equal(actual, oid); assert.equal(type, 'blob');
    const bytes = batch.subarray(end + 1, end + 1 + Number(size));
    assert.equal(createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex'), oid);
    assert.equal(batch[end + 1 + Number(size)], 10); blobs.set(oid, bytes); at = end + 2 + Number(size);
  }
  assert.equal(at, batch.length);
  const files = new Map(tree.map(t => [t.path, blobs.get(t.git_blob_oid)!]));
  const parse = (path: string) => JSON.parse(files.get(path)!.toString());
  const registry = parse(topicsPath), oldMap = parse(oldMapPath), research = parse(researchPath);
  const additions = [];
  for (const name of ['research-additions', 'runtime-additions']) additions.push(...JSON.parse((yield* io(() => readFile(resolve(root, `${base}/${name}.v1.json`)))).toString()).records);
  assert.equal(new Set(additions.map(r => r.key)).size, additions.length);
  for (const r of additions) validateRecord(r, registry.topics, files);
  // Exact UID occurrences are retained. A local anchor does not assert global uniqueness or live presence.
  const owned = new Map<string, any[]>();
  for (const [path, bytes] of files) if (path.startsWith('ontology/') && path.endsWith('.json')) {
    const b = JSON.parse(bytes.toString());
    for (const n of Array.isArray(b.nodes) ? b.nodes : []) if (typeof n.uid === 'string' && Array.isArray(n.labels)) {
      const occurrences = owned.get(n.uid) ?? []; occurrences.push({ path, node: n, kind: 'OWNED_NODE' }); owned.set(n.uid, occurrences);
    }
    // Legacy evidence snapshots can declare a bundle identity without native nodes.
    // Retain that narrower declaration; do not pretend it passed the v2 node schema.
    if (typeof b.bundle_uid === 'string' && /^sym:[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9][A-Za-z0-9._-]*$/.test(b.bundle_uid) && !((Array.isArray(b.nodes) ? b.nodes : []).some((n: any) => n.uid === b.bundle_uid && Array.isArray(n.labels)))) {
      const occurrences = owned.get(b.bundle_uid) ?? [];
      occurrences.push({ path, kind: 'BUNDLE_UID_DECLARATION', node: { uid: b.bundle_uid, labels: [b.bundle_uid.split(':')[1]], properties: { name: b.title ?? b.bundle_uid } } });
      owned.set(b.bundle_uid, occurrences);
    }
  }
  const selected = new Set([topicsPath, oldMapPath, researchPath, 'ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json']);
  for (const t of registry.topics) for (const e of t.entrypoints) selected.add(e.path.split('#')[0]);
  for (const r of additions) { selected.add(r.source_path); for (const p of r.support_paths ?? []) selected.add(p); }
  const resolutions = new Map<string, any>();
  const resolveAnchor = (id: string, preferred?: string) => {
    if (resolutions.has(id)) return;
    const occurrences = owned.get(id) ?? []; assert(occurrences.length > 0, `Anchor absent: ${id}`);
    const occurrence = preferred ? occurrences.find(o => o.path === preferred) : occurrences[0]; assert(occurrence, `Anchor source absent: ${id}`);
    assert(occurrence.node.properties?.name, `Unnamed anchor: ${id}`);
    selected.add(occurrence.path); resolutions.set(id, { ...occurrence, occurrence_paths: occurrences.map(o => o.path) });
  };
  resolveAnchor(oldMap.bundle_uid, oldMapPath); resolveAnchor(research.bundle_uid, researchPath);
  for (const t of registry.topics) {
    resolveAnchor(`${oldMap.bundle_uid}-topic-${t.id}`, oldMapPath);
    for (const id of t.existing_uids) resolveAnchor(id);
  }
  for (const n of research.nodes.filter((n: any) => ['RESEARCH_SYNTHESIS', 'EXISTING_OBLIGATION_REFERENCE'].includes(n.properties.standard_graph_role))) resolveAnchor(n.uid, researchPath);
  for (const r of additions) for (const id of r.anchor_uids ?? []) resolveAnchor(id);
  for (const p of selected) assert(files.has(p), `Selected file absent from cut: ${p}`);
  const rows = tree.map(t => ({ ...t, sha256: sha(files.get(t.path)!), bytes: files.get(t.path)!.length,
    classification: t.path.includes('/') ? t.path.split('/')[0] : '(root)',
    disposition: selected.has(t.path) ? 'CURATED_SOURCE' : 'INVENTORIED_ONLY' }));
  const corpus = { schema_version: 'hswm-whole-map-corpus/v1', source_revision: cut,
    inclusion_rule: 'Every blob path returned by git ls-tree -r at source_revision, exactly once; symlink bytes are recorded without following links.',
    semantic_scope: 'CURATED_SOURCE means selected navigation/source inspection, not exhaustive semantic review. All remaining tracked files are INVENTORIED_ONLY. Untracked files and later worktree changes are outside the cut.',
    full_semantic_audit: false, tracked_paths: rows.length, selected_sources: selected.size,
    anchor_resolutions: [...resolutions.entries()].map(([uid, r]) => ({ uid, selected_path: r.path, kind: r.kind, occurrence_paths: r.occurrence_paths })), rows };
  const bindings = rows.filter(r => selected.has(r.path)).map(r => ({ path: r.path, sha256: r.sha256 }));
  bindings.push({ path: corpusPath, sha256: sha(json(corpus)) });
  for (const path of [`${base}/build.mts`, `${base}/verify.mts`, `${base}/research-additions.v1.json`, `${base}/runtime-additions.v1.json`, `${queryBase}/shapes.ttl`, ...Array.from({ length: 8 }, (_, i) => `${queryBase}/q${i + 1}.rq`)]) {
    bindings.push({ path, sha256: sha(yield* io(() => readFile(resolve(root, path)))) });
  }
  return { registry, oldMap, research, additions, files, resolutions, corpus, selected, bindings };
});

export function construct(i: any) {
  const nodes: any[] = [], relations: any[] = [], anchors: any[] = [];
  const boundary = 'SOURCE_BOUND_NAVIGATION_NOT_CANONICAL_STATE_NOT_NEW_EFFICACY';
  const add = (id: string, role: string, name: string, description: string, props: any = {}) => {
    nodes.push({ uid: id, labels: ['AbstractNode'], properties: { name, description, standard_graph_role: role,
      authority_class: 'SECONDARY_AI', canonical_scope: 'PENDING_OR_PRELIMINARY', state_plane: 'INQUIRY',
      recorded_on: '2026-10-01', actor: 'agent:codex', responsibility_owner: 'hswm:whole-map:2026-10-01',
      record_lifecycle: 'ACTIVE', status: 'SOURCE_BOUND_NAVIGATION', source_revision: cut,
      claim_boundary: boundary, projection_nonclaim: boundary, runtime_write_path: false, ...props } }); return id;
  };
  const edgeKeys = new Set<string>();
  const link = (from: string, type: string, to: string, scope = 'NAVIGATION_NOT_AUTHORITY_OR_COMPLETION') => {
    const key = `${from}|${type}|${to}`; if (edgeKeys.has(key)) return; edgeKeys.add(key);
    relations.push({ from_uid: from, to_uid: to, type, scope, status: 'PROPOSED', authority_class: 'SECONDARY_AI' });
  };
  const pathUid = (path: string) => `sym:AbstractNode:hswm-path-${cut}-${sha(path)}`;
  const topicUid = (id: string) => uid(`topic-${id}`);
  add(bundleUid, 'WHOLE_MAP', 'HSWM 전체 내용 지도', '13개 기존 탐색 축과 연구·구현 보완 자료를 연결한 시점별 지도. 전체 파일 목록은 내용 검토 완료를 뜻하지 않는다.', { full_semantic_audit: false, tracked_paths: i.corpus.tracked_paths, selected_sources: i.selected.size });
  for (const [id, r] of i.resolutions) anchors.push({ uid: id, name: r.node.properties.name, required_labels: r.node.labels });
  const contents = new Set<string>();
  for (const row of i.corpus.rows.filter((r: any) => i.selected.has(r.path))) {
    const contentUid = `sym:AbstractNode:hswm-content-sha256-${row.sha256}`;
    if (!contents.has(contentUid)) { add(contentUid, 'ARTIFACT_CONTENT', `sha256:${row.sha256}`, '정확한 바이트의 내용 식별자. 같은 내용의 여러 경로는 별도 occurrence이다.', { content_sha256: row.sha256, content_bytes: row.bytes }); contents.add(contentUid); }
    add(pathUid(row.path), 'REPOSITORY_PATH_AT_CUT', row.path, '고정 Git 커밋의 경로 occurrence. 작업트리나 live graph의 현재 상태를 뜻하지 않는다.', { source_path: row.path, source_sha256: row.sha256, source_bytes: row.bytes, git_blob_oid: row.git_blob_oid, git_mode: row.mode, event_date: 'UNKNOWN_NOT_INFERRED_FROM_FILENAME' });
    link(pathUid(row.path), 'HAS_CONTENT', contentUid, 'EXACT_BYTES_AT_FIXED_COMMIT');
    link(bundleUid, 'REFERENCES', pathUid(row.path), 'SELECTED_SOURCE_INVENTORY');
  }
  for (const [id, r] of i.resolutions) link(pathUid(r.path), 'REFERENCES', id, 'EXACT_UID_AT_SELECTED_LOCAL_OCCURRENCE_NOT_GLOBAL_UNIQUENESS');
  for (const t of i.registry.topics) {
    const id = add(topicUid(t.id), 'TOPIC_REFERENCE', t.title, t.description, { topic_id: t.id, source_status_as_of: '2026-09-13', design_status: t.design_status, engineering_status: t.engineering_status, formal_status: t.formal_status, efficacy_status: t.efficacy_status, status: 'HISTORICAL_TOPIC_REFERENCE_WITH_LATER_LINKS' });
    link(bundleUid, 'HAS_CONCEPT', id); link(id, 'REFERENCES', `${i.oldMap.bundle_uid}-topic-${t.id}`);
    link(id, 'DERIVED_FROM', pathUid(topicsPath));
    for (const e of t.entrypoints) link(id, 'HAS_SOURCE', pathUid(e.path.split('#')[0]), `HISTORICAL_ENTRYPOINT: ${e.role}; ${e.reason}`);
    for (const existing of t.existing_uids) link(id, 'REFERENCES', existing);
    for (const [ordinal, text] of t.open_questions.entries()) {
      const q = add(uid(`question-${t.id}-${ordinal}`), 'HISTORICAL_OPEN_QUESTION', `${t.id} Q${ordinal + 1}`, text, { source_status_as_of: '2026-09-13', status: 'HISTORICAL_OPEN_QUESTION_NOT_REEVALUATED', ordinal });
      link(q, 'ABOUT', id); link(q, 'DERIVED_FROM', pathUid(topicsPath));
    }
  }
  for (const n of i.research.nodes.filter((n: any) => n.properties.standard_graph_role === 'RESEARCH_SYNTHESIS')) {
    const p = n.properties;
    const id = add(uid(`previous-${p.record_key}`), 'HISTORICAL_RESEARCH_REFERENCE', p.name, p.description, { record_key: p.record_key, source_status: p.status, source_status_as_of: '2026-09-30', research_kind: p.research_kind, original_uid: n.uid, negative_or_limiting_result: p.negative_or_limiting_result, claim_boundary: p.claim_boundary, original_source_path: p.source_path, original_source_sha256: p.source_sha256, status: 'HISTORICAL_REFERENCE_NOT_REEVALUATED' });
    link(id, 'REFERENCES', n.uid); link(id, 'DERIVED_FROM', pathUid(researchPath));
    const oldTopic = i.research.relations.find((r: any) => r.from_uid === n.uid && r.type === 'ABOUT').to_uid.replace('sym:Concept:hswm-research-map-20260930-', '');
    assert(crosswalk[oldTopic]); for (const t of crosswalk[oldTopic]) link(id, 'ABOUT', topicUid(t), 'AI_NAVIGATION_CROSSWALK_NOT_EQUIVALENCE');
  }
  for (const n of i.research.nodes.filter((n: any) => n.properties.standard_graph_role === 'EXISTING_OBLIGATION_REFERENCE')) {
    const p = n.properties, id = add(uid(`obligation-${p.obligation_id}`), 'OBLIGATION_REFERENCE', p.name, p.description, { obligation_id: p.obligation_id, original_uid: p.original_uid, source_status: p.source_status, source_status_as_of: p.source_status_as_of, discharged_by_this_map: false, status: 'REFERENCE_ONLY_NOT_DISCHARGED' });
    link(id, 'REFERENCES', n.uid); link(id, 'DERIVED_FROM', pathUid(researchPath)); link(id, 'ABOUT', topicUid('constructive_realizability_and_proof'));
  }
  for (const r of i.additions) {
    const id = add(uid(`addition-${r.key}`), 'CURATED_ADDITION', r.title, r.statement, { record_key: r.key, research_kind: r.kind, source_status: r.source_status, source_path: r.source_path, source_locator: r.source_locator, source_sha256: sha(i.files.get(r.source_path)), claim_boundary: r.claim_boundary, negative_or_limiting_result: r.negative, event_date: r.event_date ?? 'UNKNOWN_NOT_INFERRED', event_date_basis: r.event_date ? 'SOURCE_REPORTED_NOT_NEW_RUN' : 'UNKNOWN', status: 'SOURCE_BOUND_REFERENCE_NOT_NEW_EXECUTION' });
    link(id, 'ABOUT', topicUid(r.topic)); link(id, 'DERIVED_FROM', pathUid(r.source_path));
    for (const p of r.support_paths ?? []) link(id, 'REFERENCES', pathUid(p), 'SUPPORTING_SOURCE_NOT_RERUN');
    for (const a of r.anchor_uids ?? []) link(id, 'REFERENCES', a, 'EXISTING_IDENTITY_NOT_NEW_CANON');
  }
  const classes = [...new Set(i.corpus.rows.map((r: any) => r.classification))].sort();
  for (const c of classes) {
    const rows = i.corpus.rows.filter((r: any) => r.classification === c);
    const selected = rows.filter((r: any) => r.disposition === 'CURATED_SOURCE').length;
    const id = add(uid(`coverage-${sha(String(c)).slice(0, 16)}`), 'CORPUS_COVERAGE', String(c), '파일 경로 영역별 목록 수와 선별 출처 수. 과학적 완성률이나 내용 감사율이 아니다.', { corpus_class: c, tracked_paths: rows.length, selected_sources: selected, inventoried_only: rows.length - selected, corpus_sha256: sha(json(i.corpus)), full_semantic_audit: false });
    link(bundleUid, 'HAS_CONCEPT', id);
  }
  link(bundleUid, 'REFERENCES', i.oldMap.bundle_uid, 'EARLIER_NAVIGATION_SNAPSHOT_UNMODIFIED');
  link(bundleUid, 'REFERENCES', i.research.bundle_uid, 'EARLIER_34_RECORD_RESEARCH_SNAPSHOT_UNMODIFIED');
  return { schema_version: 'hswm-whole-map/v1', bundle_uid: bundleUid, status: 'SOURCE_BOUND_NAVIGATION', nonclaim: boundary,
    authority_boundary: 'All new summaries SECONDARY_AI; existing UID anchors retain source authority, neither permissions nor completion are inferred.', source_accessed_on: '2026-10-01',
    artifact_bindings: i.bindings, expected_counts: { nodes: nodes.length, anchors: anchors.length, relations: relations.length }, anchors, nodes, relations };
}
export const build = () => Effect.gen(function* () {
  const inputs = yield* loadInputs(), bundle = construct(inputs), bytes = Buffer.from(json(bundle));
  const decoded = decodeKgBundleSource({ sourceId: 'whole-map', rawBytes: bytes }, 'v2');
  if (Either.isLeft(decoded)) throw new Error(decoded.left.detail);
  return { inputs, bundle, bytes };
});
if (import.meta.main) await Effect.runPromise(Effect.gen(function* () {
  assert.deepEqual(process.argv.slice(2), ['--write'], 'Usage: node _research/whole_map_2026-10-01/build.mts --write');
  const { inputs, bundle, bytes } = yield* build();
  for (const [path, data] of [[output, bytes], [corpusPath, json(inputs.corpus)]]) {
    yield* io(() => mkdir(resolve(root, dirname(path as string)), { recursive: true }));
    yield* io(() => writeFile(resolve(root, path as string), data));
  }
  console.log(json({ output, source_revision: cut, tracked_paths: inputs.corpus.tracked_paths, selected_sources: inputs.selected.size, ...bundle.expected_counts }));
}));
