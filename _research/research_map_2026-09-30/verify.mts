/** Competency-question and falsification checks for the dated research view. */
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { strict as assert } from 'node:assert';
import { build, root, output, base, queryBase, uid, sha, json } from './build.mts';
const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const { compileKgBundle, decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const { validateKgShacl, queryKgBundle } = await import('../../src/hswm/effect-runtime/dist/native-kg-standards.js');
const io = <A>(op: () => Promise<A>) => Effect.tryPromise({ try: op, catch: (error: unknown) => new Error(String(error)) });
const compile = (bundle: any) => {
  const r = compileKgBundle([{ sourceId: 'research-map', rawBytes: Buffer.from(json(bundle)) }], 'v2');
  if (Either.isLeft(r)) throw new Error(r.left.detail);
  return r.right;
};
function checkSlots(bundle: any) {
  const nodes = new Map(bundle.nodes.map((n: any) => [n.uid, n]));
  for (const c of bundle.nodes.filter((n: any) => n.properties.standard_graph_role === 'RESEARCH_SYNTHESIS')) {
    const slots = bundle.relations.filter((r: any) => r.from_uid === c.uid && r.type === 'HAS_PARTICIPATION').map((r: any) => nodes.get(r.to_uid) as any);
    assert.deepEqual(slots.map((s: any) => s.properties.ordinal).sort((a: number, b: number) => a - b), slots.map((_: any, i: number) => i));
    assert.equal(slots.filter((s: any) => s.properties.role_name === 'subject').length, 1);
    assert.equal(slots.filter((s: any) => s.properties.role_name === 'source').length, 1);
    for (const s of slots) {
      assert.equal(s.properties.assertion_uid, c.uid);
      assert(nodes.has(s.properties.participant_uid));
      const edges = bundle.relations.filter((r: any) => r.from_uid === s.uid && r.type === 'REFERENCES');
      assert.deepEqual(edges.map((e: any) => e.to_uid), [s.properties.participant_uid]);
      const direct = s.properties.role_name === 'subject' ? 'ABOUT' : s.properties.role_name === 'source' ? 'DERIVED_FROM' : s.properties.role_name === 'obligation' ? 'RELATES_TO' : 'REFERENCES';
      assert(bundle.relations.some((r: any) => r.from_uid === c.uid && r.to_uid === s.properties.participant_uid && r.type === direct));
    }
  }
}
await Effect.runPromise(Effect.gen(function* () {
  const { bundle, bytes, inputs } = yield* build();
  const checkedIn = yield* io(() => readFile(resolve(root, output)));
  assert.deepEqual(checkedIn, bytes, 'Generated bundle differs; rebuild explicitly');
  checkSlots(bundle);
  const projection = compile(bundle), validation: any[] = [], queries: any = {};
  const standard = yield* io(() => readFile(resolve(root, 'schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl')));
  const local = yield* io(() => readFile(resolve(root, `${queryBase}/shapes.ttl`)));
  for (const [name, shape] of [['existing-v2', standard], ['research-map', local]] as const) {
    const report = yield* validateKgShacl(projection, shape); assert(report.conforms, json(report));
    validation.push({ name, conforms: report.conforms, engine: report.engine, profile: report.profile });
  }
  for (let i = 1; i <= 8; i++) {
    const text = (yield* io(() => readFile(resolve(root, `${queryBase}/q${i}.rq`)))).toString();
    const rows = yield* queryKgBundle(projection, text);
    assert(Array.isArray(rows));
    queries[`q${i}`] = rows.map((r: any) => Object.fromEntries(Object.entries(r).map(([k, v]: any) => [k, v?.value ?? null])));
  }
  const records = inputs.curation.records;
  const keys = (rows: any[]) => rows.map(r => r.key).sort();
  assert.deepEqual(queries.q1.map((r: any) => r.topic).sort(), inputs.curation.topics.map((t: any) => t.title).sort());
  for (const topic of inputs.curation.topics) assert.equal(Number(queries.q1.find((r: any) => r.topic === topic.title).records), records.filter((r: any) => r.topic === topic.key).length);
  assert.deepEqual(keys(queries.q2), records.map((r: any) => r.key).sort());
  for (const r of records) {
    const actual = queries.q2.find((x: any) => x.key === r.key);
    assert.equal(actual.statement, r.statement); assert.equal(actual.kind, r.kind); assert.equal(actual.ceiling, r.claim_boundary);
    assert.equal(actual.source, r.source_path); assert.equal(actual.locator, r.source_locator); assert.equal(actual.authority, 'SECONDARY_AI');
    assert.equal(actual.sha256, inputs.pins.sources.find((p: any) => p.path === r.source_path).sha256);
  }
  assert.deepEqual(keys(queries.q3), records.filter((r: any) => r.negative).map((r: any) => r.key).sort());
  assert.deepEqual(queries.q4.map((r: any) => r.obligation).sort(), [...Array.from({ length: 8 }, (_, i) => `CR-${i}`), ...Array.from({ length: 8 }, (_, i) => `FCL-${i + 1}`)].sort());
  for (const r of queries.q4) {
    const n = bundle.nodes.find((n: any) => n.properties.obligation_id === r.obligation);
    assert.equal(r.originalUid, n.properties.original_uid); assert.equal(r.historicalStatus, n.properties.source_status);
    assert.equal(r.currentReferenceStatus, 'REFERENCE_ONLY_NOT_DISCHARGED');
  }
  assert.deepEqual(keys(queries.q5), records.filter((r: any) => ['OPEN_QUESTION', 'RESEARCH_PROPOSAL'].includes(r.kind)).map((r: any) => r.key).sort());
  assert.deepEqual(queries.q6, []);
  assert.deepEqual(queries.q7.map((r: any) => [r.roleName, Number(r.ordinal)]).sort((a: any, b: any) => a[1] - b[1]), [['subject', 0], ['source', 1], ['obligation', 2], ['obligation', 3], ['obligation', 4]]);
  assert(queries.q7.every((r: any) => r.edgeStatus === 'PROPOSED' && r.edgeScope === 'EXACT_ROLE_TARGET'));
  for (const r of queries.q7) {
    const slot = bundle.nodes.find((n: any) => n.uid === uid('AbstractNode', `dgx-learning-slot-${r.ordinal}`));
    assert.equal(r.targetUid, slot.properties.participant_uid);
  }
  assert.deepEqual(queries.q8.map((r: any) => [r.key, r.version, r.commit]), [['hyperon', 'hyperon-experimental v0.2.10', '3f76dc460da6961f57f69f6c3e550c59c74ada83']]);

  // Each mutation represents a concrete semantic error that this view must reject.
  const rejected: string[] = [];
  for (const [name, mutate] of [
    ['AI summary promoted to USER_PRIMARY', (b: any) => { b.nodes.find((n: any) => n.uid === uid('Claim', 'identity')).properties.authority_class = 'USER_PRIMARY'; }],
    ['CR obligation declared discharged', (b: any) => { b.nodes.find((n: any) => n.properties.obligation_id === 'CR-7').properties.discharged_by_this_map = true; }],
    ['source derivation removed', (b: any) => { b.relations = b.relations.filter((r: any) => !(r.from_uid === uid('Claim', 'dgx-learning') && r.type === 'DERIVED_FROM')); }],
    ['edge silently promoted to ACTIVE', (b: any) => { b.relations[0].status = 'ACTIVE'; }]
  ] as const) {
    const b = structuredClone(bundle); mutate(b); b.expected_counts.relations = b.relations.length;
    const report = yield* validateKgShacl(compile(b), local); assert.equal(report.conforms, false, name); rejected.push(name);
  }
  const duplicate = structuredClone(bundle); duplicate.nodes.push(duplicate.nodes[0]); duplicate.expected_counts.nodes++;
  assert(Either.isLeft(decodeKgBundleSource({ sourceId: 'duplicate', rawBytes: Buffer.from(json(duplicate)) }, 'v2'))); rejected.push('duplicate owned UID');
  const dangling = structuredClone(bundle); dangling.relations[0].to_uid = 'sym:Concept:missing-map-target';
  assert(Either.isLeft(decodeKgBundleSource({ sourceId: 'dangling', rawBytes: Buffer.from(json(dangling)) }, 'v2'))); rejected.push('dangling relationship endpoint');
  const reordered = structuredClone(bundle); reordered.nodes.find((n: any) => n.uid === uid('AbstractNode', 'dgx-learning-slot-1')).properties.ordinal = 0;
  assert.throws(() => checkSlots(reordered)); rejected.push('duplicate participation ordinal');
  const unsupported = structuredClone(bundle);
  unsupported.relations = unsupported.relations.filter((r: any) => !(r.from_uid === uid('Claim', 'dgx-learning') && r.type === 'DERIVED_FROM'));
  unsupported.expected_counts.relations = unsupported.relations.length;
  const q6 = (yield* io(() => readFile(resolve(root, `${queryBase}/q6.rq`)))).toString();
  const missing = yield* queryKgBundle(compile(unsupported), q6);
  assert.equal(missing.length, 1); assert.equal(missing[0].key.value, 'dgx-learning'); rejected.push('unsupported-claim query detects removed source');

  const toolchain = [];
  for (const path of ['src/hswm/effect-runtime/dist/native-kg-bundle-domain.js', 'src/hswm/effect-runtime/dist/native-kg-standards.js', 'src/hswm/effect-runtime/dist/native-kg-vendor.js', 'src/hswm/effect-runtime/package-lock.json']) {
    toolchain.push({ path, sha256: sha(yield* io(() => readFile(resolve(root, path)))) });
  }
  const report = { schema_version: 'hswm-research-map-validation/v1', checked_at: new Date().toISOString(), toolchain,
    bundle_sha256: sha(bytes), node_version: process.version, source_revision: inputs.pins.source_revision,
    scope: 'Local graph structure, byte bindings and competency questions. No model runs or Lean replay.',
    source_bindings_verified: inputs.pins.sources.length, shacl: validation,
    competency_questions: Object.fromEntries(Object.entries(queries).map(([k, v]: any) => [k, { passed: true, rows: v.length }])),
    falsification_checks: rejected, queries, claim_ceiling: 'RESEARCH_ORGANIZATION_AND_STRUCTURAL_VALIDATION_ONLY' };
  yield* io(() => writeFile(resolve(root, 'docs/research/artifacts/hswm_research_map_2026-09-30/validation.v1.json'), json(report)));
  console.log(json({ passed: true, sources: report.source_bindings_verified, shacl: validation, questions: report.competency_questions, rejected_mutations: rejected.length }));
}));
