/** Local source-bound research view. Never reads or writes a live graph. */
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
export const root = fileURLToPath(new URL('../../', import.meta.url));
export const base = '_research/research_map_2026-09-30';
export const queryBase = 'ontology/queries/hswm_research_map_2026-09-30';
export const output = 'ontology/development/HSWM_RESEARCH_MAP_2026-09-30.v1.json';
export const bundleUid = 'sym:AbstractNode:hswm-research-map-2026-09-30';
export const sha = (bytes: string | Uint8Array) => createHash('sha256').update(bytes).digest('hex');
export const uid = (kind: string, key: string) => `sym:${kind}:hswm-research-map-20260930-${key}`;
const sourceUid = (path: string) => uid('Reference', sha(path).slice(0, 24));
const boundary = 'SOURCE_BOUND_RESEARCH_SYNTHESIS_NOT_CANONICAL_STATE_OR_NEW_EFFICACY';
export const json = (value: unknown) => JSON.stringify(value, null, 2) + '\n';
const io = <A>(op: () => Promise<A>) => Effect.tryPromise({ try: op, catch: (error: unknown) => new Error(String(error)) });
export const loadInputs = () => Effect.gen(function* () {
  const read = (path: string) => io(() => readFile(resolve(root, path)));
  const curation = JSON.parse((yield* read(`${base}/curation.v1.json`)).toString());
  const pins = JSON.parse((yield* read(`${base}/source-pins.v1.json`)).toString());
  const files = new Map<string, Buffer>();
  for (const pin of pins.sources) {
    const bytes = yield* read(pin.path);
    if (sha(bytes) !== pin.sha256 || bytes.length !== pin.bytes) throw new Error(`Source drift: ${pin.path}; recover pinned revision, do not refresh historical hashes`);
    files.set(pin.path, bytes);
  }
  for (const record of curation.records) {
    if (!files.get(record.source_path)?.toString().includes(record.source_locator)) throw new Error(`Missing source locator: ${record.key}`);
    for (const key of ['source_path', 'original_source', 'code']) if (record[key] && !files.has(record[key])) throw new Error(`Unbound ${key}: ${record.key}`);
  }
  const extra = [`${base}/curation.v1.json`, `${base}/source-pins.v1.json`, `${base}/build.mts`, `${base}/verify.mts`,
    `${queryBase}/shapes.ttl`, ...Array.from({ length: 8 }, (_, i) => `${queryBase}/q${i + 1}.rq`)];
  const bindings = pins.sources.map((p: any) => ({ path: p.path, sha256: p.sha256 }));
  for (const path of extra) bindings.push({ path, sha256: sha(yield* read(path)) });
  return { curation, pins, files, bindings };
});

/** All summaries belong to this view; pre-existing subjects stay anchors. */
export function construct({ curation, pins, files, bindings }: any) {
  const nodes: any[] = [], relations: any[] = [], anchors: any[] = [];
  const anchorMap = new Map<string, any>();
  const add = (id: string, label: string, role: string, name: string, description: string, props: any = {}) => {
    nodes.push({ uid: id, labels: [label], properties: {
      name, description, standard_graph_role: role, authority_class: 'SECONDARY_AI',
      ontology_kind: label === 'Claim' ? 'STATEMENT' : label === 'Reference' ? 'ARTIFACT' : 'CONCEPT',
      ontology_plane: 'INQUIRY', ontology_domain: 'ENGINEERING',
      canonical_scope: 'PENDING_OR_PRELIMINARY', record_lifecycle: 'ACTIVE',
      epistemic_state: 'SOURCE_BOUND_SYNTHESIS', workflow_state: 'RECORDED', review_required: true,
      status: 'SOURCE_BOUND_REFERENCE', recorded_on: curation.recorded_on, actor: curation.actor,
      responsibility_owner: 'hswm:research:map:2026-09-30', claim_boundary: boundary,
      projection_nonclaim: 'NOT_COGNITION_NOT_RUNTIME_WRITE_NOT_CR_FCL_PROMOTION', ...props
    } });
    return id;
  };
  const link = (from: string, type: string, to: string, scope: string) => relations.push({
    from_uid: from, to_uid: to, type, authority_class: 'SECONDARY_AI', scope, status: 'PROPOSED'
  });
  const anchor = (node: any) => {
    if (!anchorMap.has(node.uid)) { const a = { uid: node.uid, name: node.properties.name, required_labels: node.labels }; anchors.push(a); anchorMap.set(a.uid, a); }
    return node.uid;
  };
  add(bundleUid, 'AbstractNode', 'RESEARCH_INTEGRATION', 'HSWM 연구 내용과 근거 지도', curation.scope,
    { source_revision: pins.source_revision, current_runtime_state: false, full_research_audit: false });
  for (const topic of curation.topics) {
    add(uid('Concept', topic.key), 'Concept', 'RESEARCH_TOPIC', topic.title, '연구 탐색을 위한 AI 분류이며 정본 subsystem 분해가 아니다.');
    link(bundleUid, 'HAS_CONCEPT', uid('Concept', topic.key), 'NAVIGATION_MEMBERSHIP_NOT_PARTITION');
  }
  for (const pin of pins.sources) {
    add(sourceUid(pin.path), 'Reference', 'REPOSITORY_SOURCE', pin.path, '현재 정리에서 읽거나 anchor를 해결한 정확한 파일 바이트. 원문의 진실성을 인증하지 않는다.', {
      source_path: pin.path, source_sha256: pin.sha256, source_bytes: pin.bytes, source_revision: pin.source_revision,
      source_authority: pin.path.startsWith('docs/canon/sources/') ? 'USER_PRIMARY_ORIGINAL_TEXT' : 'READ_SOURCE_LOCAL_AUTHORITY',
      status: 'PINNED_REPOSITORY_BYTES', full_semantic_audit: false
    });
    link(bundleUid, 'REFERENCES', sourceUid(pin.path), 'SELECTED_SOURCE_INVENTORY');
  }
  for (const path of curation.anchor_bundles) {
    const b = JSON.parse(files.get(path).toString());
    const entry = b.nodes.find((n: any) => n.uid === b.bundle_uid);
    if (entry) link(sourceUid(path), 'REFERENCES', anchor(entry), 'EXISTING_LOCAL_BUNDLE_IDENTITY_NOT_LIVE_PRESENCE');
  }
  const theory = JSON.parse(files.get('ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_THEORY_ONTOLOGY.v1.json').toString());
  const cr = JSON.parse(files.get(curation.cr_source).toString()).obligations;
  const fcl = JSON.parse(files.get(curation.fcl_source).toString()).nodes.filter((n: any) => n.uid.startsWith('sym:Concept:hswm-fractal-law-'));
  const obligations = new Map<string, string>();
  for (const [index, o] of cr.entries()) {
    const old = theory.nodes.find((n: any) => n.properties.obligation_id === o.id);
    if (!old) throw new Error(`Unresolved CR anchor: ${o.id}`);
    const id = add(uid('AbstractNode', o.id), 'AbstractNode', 'EXISTING_OBLIGATION_REFERENCE', `${o.id} ${o.title}`, '과거 계약 상태를 그대로 참조한다. 후속 부분 증명을 전체 의무 완료로 바꾸지 않는다.', {
      obligation_id: o.id, source_status: o.status, source_status_as_of: '2026-09-10', status: 'REFERENCE_ONLY_NOT_DISCHARGED',
      source_path: curation.cr_source, source_selector: `#/obligations/${index}`, source_authority: 'SECONDARY_AI',
      original_uid: old.uid, fcl_mapping: o.fcl, discharged_by_this_map: false
    });
    obligations.set(o.id, id); link(id, 'REFERENCES', anchor(old), 'EXISTING_OBLIGATION_IDENTITY');
    link(id, 'DERIVED_FROM', sourceUid(curation.cr_source), 'HISTORICAL_STATUS_SOURCE');
    link(bundleUid, 'HAS_CONCEPT', id, 'OBLIGATION_INDEX');
  }
  for (const o of fcl) {
    const code = o.properties.name.match(/^FCL-\d+/)[0];
    const id = add(uid('AbstractNode', code), 'AbstractNode', 'EXISTING_OBLIGATION_REFERENCE', o.properties.name, o.properties.description, {
      obligation_id: code, source_status: o.properties.epistemic_state, source_status_as_of: '2026-08-28',
      status: 'REFERENCE_ONLY_NOT_DISCHARGED', source_authority: o.properties.authority_class,
      source_path: curation.fcl_source, original_uid: o.uid, acceptance_logic: o.properties.acceptance_logic,
      claim_boundary: o.properties.claim_boundary, discharged_by_this_map: false
    });
    obligations.set(code, id); link(id, 'REFERENCES', anchor(o), 'EXISTING_OBLIGATION_IDENTITY');
    link(id, 'DERIVED_FROM', sourceUid(curation.fcl_source), 'HISTORICAL_CONTRACT_SOURCE');
    link(bundleUid, 'HAS_CONCEPT', id, 'OBLIGATION_INDEX');
  }
  for (const o of cr) for (const target of o.fcl.filter((s: string) => s.startsWith('FCL-'))) link(obligations.get(o.id)!, 'RELATES_TO', obligations.get(target)!, 'ORIGINAL_CR_TO_FCL_CROSSWALK');
  for (const record of curation.records) {
    const id = uid('Claim', record.key), topic = uid('Concept', record.topic), source = sourceUid(record.source_path);
    add(id, 'Claim', 'RESEARCH_SYNTHESIS', record.title, record.statement, {
      record_key: record.key, research_kind: record.kind, source_path: record.source_path, source_locator: record.source_locator,
      source_sha256: pins.sources.find((p: any) => p.path === record.source_path).sha256,
      source_revision: pins.source_revision, source_authority: record.source_authority ?? 'SECONDARY_AI',
      claim_boundary: record.claim_boundary, negative_or_limiting_result: record.negative ?? false,
      event_date: record.event_date ?? 'UNKNOWN_OR_NOT_APPLICABLE', event_date_basis: record.event_date ? 'SOURCE_REPORTED_DATE_NOT_NEW_RUN' : 'NOT_INFERRED_FROM_INGESTION',
      status: record.kind === 'OPEN_QUESTION' || record.kind === 'RESEARCH_PROPOSAL' ? 'PROPOSED_NOT_COMPLETED' : 'SOURCE_BOUND_REFERENCE',
      ...(record.comparator_version ? { comparator_version: record.comparator_version, comparator_commit: record.comparator_commit } : {})
    });
    link(bundleUid, 'HAS_CONCEPT', id, 'CURATED_ASSERTION_INDEX');
    link(id, 'ABOUT', topic, 'RESEARCH_TOPIC_NOT_SYSTEM_PART');
    link(id, 'DERIVED_FROM', source, 'REPORTED_SOURCE_NOT_NEW_OBSERVATION');
    const participants = [['subject', topic], ['source', source]];
    if (record.original_source) { link(id, 'REFERENCES', sourceUid(record.original_source), 'IMMUTABLE_USER_ORIGINAL_NOT_AI_PARAPHRASE'); participants.push(['original', sourceUid(record.original_source)]); }
    if (record.code) { link(id, 'REFERENCES', sourceUid(record.code), 'IMPLEMENTATION_LOCATION_NOT_EXECUTION_PROOF'); participants.push(['implementation', sourceUid(record.code)]); }
    for (const o of record.obligations ?? []) {
      if (!obligations.has(o)) throw new Error(`Unknown obligation: ${o}`);
      link(id, 'RELATES_TO', obligations.get(o)!, 'RELEVANCE_NOT_DISCHARGE'); participants.push(['obligation', obligations.get(o)!]);
    }
    for (const [ordinal, [role, participant]] of participants.entries()) {
      const slot = add(uid('AbstractNode', `${record.key}-slot-${ordinal}`), 'AbstractNode', 'ROLE_PARTICIPATION', `${record.key} ${role} ${ordinal}`, '주장 관계의 역할 있는 참여 occurrence. 같은 역할의 복수 의무와 순서를 보존한다.', {
        assertion_uid: id, participant_uid: participant, role_name: role, ordinal
      });
      link(id, 'HAS_PARTICIPATION', slot, 'ORDERED_ASSERTION_PARTICIPANT');
      link(slot, 'REFERENCES', participant, 'EXACT_ROLE_TARGET');
    }
  }
  return { schema_version: 'hswm-research-map/v1', bundle_uid: bundleUid, status: 'SOURCE_BOUND_RESEARCH_SYNTHESIS',
    authority_boundary: curation.authority_boundary, nonclaim: boundary, source_accessed_on: curation.recorded_on,
    artifact_bindings: bindings, expected_counts: { nodes: nodes.length, anchors: anchors.length, relations: relations.length }, anchors, nodes, relations };
}

export const build = () => Effect.gen(function* () {
  const inputs = yield* loadInputs();
  const bundle = construct(inputs), bytes = Buffer.from(json(bundle));
  const decoded = decodeKgBundleSource({ sourceId: 'research-map', rawBytes: bytes }, 'v2');
  if (Either.isLeft(decoded)) throw new Error(decoded.left.detail);
  return { bundle, bytes, inputs };
});
if (import.meta.main) {
  if (process.argv.length > 2) throw new Error('Usage: node _research/research_map_2026-09-30/build.mts');
  await Effect.runPromise(Effect.gen(function* () {
    const { bundle, bytes } = yield* build();
    yield* io(() => writeFile(resolve(root, output), bytes));
    console.log(json({ output, ...bundle.expected_counts }));
  }));
}
