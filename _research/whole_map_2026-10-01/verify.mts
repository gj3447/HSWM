/** Read-only qualification for the dated whole-map navigation projection. */
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { strict as assert } from 'node:assert';
import { build, root, cut, output, corpusPath, artifactBase, queryBase, sha, json, validateRecord } from './build.mts';

const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const { compileKgBundle, decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const { validateKgShacl, queryKgBundle } = await import('../../src/hswm/effect-runtime/dist/native-kg-standards.js');

const io = <A>(op: () => Promise<A>) => Effect.tryPromise({ try: op, catch: (error: unknown) => new Error(String(error)) });
const value = (term: any) => term?.value ?? null;
const rows = (result: any) => {
  assert(Array.isArray(result), 'competency query must be SELECT');
  return result.map((row: any) => Object.fromEntries(Object.entries(row).map(([key, term]) => [key, value(term)])));
};
const compile = (bundle: any) => {
  const result = compileKgBundle([{ sourceId: 'whole-map', rawBytes: Buffer.from(json(bundle)) }], 'v2');
  if (Either.isLeft(result)) throw new Error(result.left.detail);
  return result.right;
};
const sourceBytes = async (path: string) => readFile(resolve(root, path));
const sameJson = (left: Uint8Array, right: unknown, detail: string) => assert.deepEqual(Buffer.from(left), Buffer.from(json(right)), detail);
const distinct = (items: readonly string[], detail: string) => assert.equal(new Set(items).size, items.length, detail);

function verifyCorpus(inputs: any, bundle: any) {
  const rowsByPath = new Map(inputs.corpus.rows.map((row: any) => [row.path, row]));
  assert.equal(rowsByPath.size, inputs.corpus.rows.length, 'corpus path duplicated');
  assert.equal(rowsByPath.size, inputs.files.size, 'corpus does not cover the fixed-cut file inventory');
  for (const [path, bytes] of inputs.files) {
    const row = rowsByPath.get(path); assert(row, `corpus omits fixed-cut path: ${path}`);
    assert.equal(row.sha256, sha(bytes), `corpus SHA mismatch: ${path}`);
    assert.equal(row.bytes, bytes.length, `corpus byte count mismatch: ${path}`);
    assert.equal(row.disposition, inputs.selected.has(path) ? 'CURATED_SOURCE' : 'INVENTORIED_ONLY', `corpus disposition mismatch: ${path}`);
  }
  const nodes = new Map(bundle.nodes.map((node: any) => [node.uid, node]));
  const has = (from: string, type: string, to: string) => bundle.relations.some((edge: any) => edge.from_uid === from && edge.type === type && edge.to_uid === to);
  const selectedRows = inputs.corpus.rows.filter((row: any) => row.disposition === 'CURATED_SOURCE');
  const expectedContents = new Set(selectedRows.map((row: any) => `sym:AbstractNode:hswm-content-sha256-${row.sha256}`));
  const actualContents = bundle.nodes.filter((node: any) => node.properties.standard_graph_role === 'ARTIFACT_CONTENT').map((node: any) => node.uid);
  distinct(actualContents, 'ARTIFACT_CONTENT UID duplicated');
  assert.deepEqual([...actualContents].sort(), [...expectedContents].sort(), 'content nodes must be exactly the unique selected-byte SHA set');
  for (const row of selectedRows) {
    const pathNode = `sym:AbstractNode:hswm-path-${cut}-${sha(row.path)}`;
    const contentNode = `sym:AbstractNode:hswm-content-sha256-${row.sha256}`;
    assert(nodes.has(pathNode), `selected path node absent: ${row.path}`);
    assert(nodes.has(contentNode), `content node absent: ${row.path}`);
    assert.equal(nodes.get(pathNode).properties.source_sha256, row.sha256, `path node SHA mismatch: ${row.path}`);
    assert(has(pathNode, 'HAS_CONTENT', contentNode), `missing exact HAS_CONTENT: ${row.path}`);
  }
  for (const anchor of bundle.anchors) {
    const resolution = inputs.resolutions.get(anchor.uid); assert(resolution, `anchor lacks source occurrence: ${anchor.uid}`);
    assert(inputs.selected.has(resolution.path), `anchor source is not selected: ${anchor.uid}`);
    assert(inputs.files.has(resolution.path), `anchor source absent from cut: ${anchor.uid}`);
  }
}

function checkCounts(inputs: any, bundle: any) {
  const previous = bundle.nodes.filter((node: any) => node.properties.standard_graph_role === 'HISTORICAL_RESEARCH_REFERENCE');
  const topics = bundle.nodes.filter((node: any) => node.properties.standard_graph_role === 'TOPIC_REFERENCE');
  const questions = bundle.nodes.filter((node: any) => node.properties.standard_graph_role === 'HISTORICAL_OPEN_QUESTION');
  const obligations = bundle.nodes.filter((node: any) => node.properties.standard_graph_role === 'OBLIGATION_REFERENCE');
  assert.equal(previous.length, 34, 'all 34 prior research records must be preserved');
  assert.equal(topics.length, 13, 'all 13 historical topics must be preserved');
  assert.equal(questions.length, 26, 'all 26 historical questions must be preserved');
  assert.equal(obligations.length, 16, 'all CR/FCL obligations must be preserved');
  assert.equal(inputs.research.nodes.filter((node: any) => node.properties.standard_graph_role === 'RESEARCH_SYNTHESIS').length, 34, 'input research map record count drift');
  for (const n of previous) {
    const original = inputs.research.nodes.find((o: any) => o.uid === n.properties.original_uid);
    assert(original, 'historical reference lost its original identity');
    for (const key of ['name', 'description', 'record_key', 'research_kind', 'claim_boundary', 'negative_or_limiting_result']) assert.deepEqual(n.properties[key], original.properties[key], `historical ${key} changed`);
    assert.equal(n.properties.source_status, original.properties.status);
    assert.equal(n.properties.status, 'HISTORICAL_REFERENCE_NOT_REEVALUATED');
  }
}

function expectQueryResults(queryResults: Record<string, any[]>, inputs: any, bundle: any) {
  const byKey = (items: any[]) => items.map(item => item.key).sort();
  const topicRows = queryResults.q1;
  assert.equal(topicRows.length, 13, 'q1 topic count');
  assert.deepEqual(topicRows.map(row => row.topicId).sort(), inputs.registry.topics.map((topic: any) => topic.id).sort(), 'q1 topic identifiers');
  for (const topic of inputs.registry.topics) {
    const row = topicRows.find(item => item.topicId === topic.id); assert(row, `q1 missing ${topic.id}`);
    assert.equal(row.title, topic.title); assert.equal(row.design, topic.design_status); assert.equal(row.engineering, topic.engineering_status);
    assert.equal(row.formal, topic.formal_status); assert.equal(row.efficacy, topic.efficacy_status); assert.equal(row.asOf, '2026-09-13');
  }
  assert.deepEqual(byKey(queryResults.q2), inputs.additions.map((record: any) => record.key).sort(), 'q2 additions');
  for (const record of inputs.additions) {
    const row = queryResults.q2.find(item => item.key === record.key); assert(row, `q2 missing ${record.key}`);
    assert.equal(row.title, record.title); assert.equal(row.statement, record.statement); assert.equal(row.kind, record.kind);
    assert.equal(row.status, record.source_status); assert.equal(row.source, record.source_path); assert.equal(row.locator, record.source_locator);
    assert.equal(row.sha256, sha(inputs.files.get(record.source_path))); assert.equal(row.authority, 'SECONDARY_AI');
    assert.equal(row.ceiling, record.claim_boundary); assert.equal(row.negative, String(record.negative));
  }
  assert.equal(queryResults.q3.length, 16, 'q3 obligations');
  const obligationIds = [...Array.from({ length: 8 }, (_, i) => `CR-${i}`), ...Array.from({ length: 8 }, (_, i) => `FCL-${i + 1}`)].sort();
  assert.deepEqual(queryResults.q3.map(row => row.obligation).sort(), obligationIds, 'q3 obligation IDs');
  for (const row of queryResults.q3) {
    const mapped = bundle.nodes.find((node: any) => node.properties.standard_graph_role === 'OBLIGATION_REFERENCE' && node.properties.obligation_id === row.obligation);
    assert(mapped, `q3 missing mapped obligation ${row.obligation}`);
    const original = inputs.research.nodes.find((node: any) => node.properties.standard_graph_role === 'EXISTING_OBLIGATION_REFERENCE' && node.properties.obligation_id === row.obligation);
    assert(original, `q3 original obligation absent: ${row.obligation}`);
    assert.equal(row.originalUid, original.properties.original_uid); assert.equal(row.historicalStatus, original.properties.source_status);
    assert.equal(row.asOf, original.properties.source_status_as_of); assert.equal(row.discharged, 'false');
  }
  const expectedNegative = [...inputs.additions.filter((record: any) => record.negative).map((record: any) => record.key), ...bundle.nodes.filter((node: any) => node.properties.standard_graph_role === 'HISTORICAL_RESEARCH_REFERENCE' && node.properties.negative_or_limiting_result === true).map((node: any) => node.properties.record_key)].sort();
  assert.deepEqual(byKey(queryResults.q4), expectedNegative, 'q4 negative record coverage');
  for (const row of queryResults.q4) { assert(row.title); assert(row.ceiling); assert(row.role); }
  const selected = inputs.corpus.rows.filter((row: any) => row.disposition === 'CURATED_SOURCE');
  assert.equal(queryResults.q5.length, selected.length, 'q5 selected source inventory');
  assert.deepEqual(queryResults.q5.map(row => row.path).sort(), selected.map((row: any) => row.path).sort(), 'q5 paths');
  for (const selectedRow of selected) {
    const row = queryResults.q5.find(item => item.path === selectedRow.path); assert(row, `q5 missing ${selectedRow.path}`);
    assert.equal(row.revision, cut); assert.equal(row.blob, selectedRow.git_blob_oid); assert.equal(row.sha256, selectedRow.sha256);
    assert.equal(row.content, selectedRow.sha256); assert.equal(Number(row.bytes), selectedRow.bytes);
  }
  const expectedQuestions = inputs.registry.topics.flatMap((topic: any) => topic.open_questions.map((question: string, ordinal: number) => [topic.id, String(ordinal), question, 'HISTORICAL_OPEN_QUESTION_NOT_REEVALUATED']));
  assert.deepEqual(queryResults.q6.map(row => [row.topicId, row.ordinal, row.question, row.status]).sort(), expectedQuestions.sort(), 'q6 historical questions');
  const classes = [...new Set(inputs.corpus.rows.map((row: any) => row.classification))].sort();
  assert.equal(queryResults.q7.length, classes.length, 'q7 corpus coverage classes');
  for (const classification of classes) {
    const sourceRows = inputs.corpus.rows.filter((row: any) => row.classification === classification);
    const row = queryResults.q7.find(item => item.class === classification); assert(row, `q7 missing ${classification}`);
    const selectedCount = sourceRows.filter((item: any) => item.disposition === 'CURATED_SOURCE').length;
    assert.equal(Number(row.tracked), sourceRows.length); assert.equal(Number(row.selected), selectedCount);
    assert.equal(Number(row.inventoryOnly), sourceRows.length - selectedCount);
  }
  const expectedAnchors = [inputs.oldMap.bundle_uid, inputs.research.bundle_uid].sort();
  assert.deepEqual(queryResults.q8.map(row => row.uid).sort(), expectedAnchors, 'q8 old map and research anchors');
  for (const row of queryResults.q8) assert(row.name);
}

function expectMutants(inputs: any, bundle: any, localShape: Uint8Array) {
  return Effect.gen(function* () {
    const rejected: string[] = [];
    const shaclReject = (name: string, mutate: (candidate: any) => void) => Effect.gen(function* () {
      const candidate = structuredClone(bundle); mutate(candidate);
      candidate.expected_counts.nodes = candidate.nodes.length; candidate.expected_counts.relations = candidate.relations.length;
      const report = yield* validateKgShacl(compile(candidate), localShape);
      assert.equal(report.conforms, false, `${name} accepted by local SHACL`); rejected.push(name);
    });
    yield* shaclReject('AI summary promoted', candidate => { candidate.nodes.find((node: any) => node.properties.standard_graph_role === 'CURATED_ADDITION').properties.authority_class = 'USER_PRIMARY'; });
    yield* shaclReject('obligation discharged', candidate => { candidate.nodes.find((node: any) => node.properties.standard_graph_role === 'OBLIGATION_REFERENCE').properties.discharged_by_this_map = true; });
    yield* shaclReject('addition source removed', candidate => { const node = candidate.nodes.find((item: any) => item.properties.standard_graph_role === 'CURATED_ADDITION'); candidate.relations = candidate.relations.filter((edge: any) => !(edge.from_uid === node.uid && edge.type === 'DERIVED_FROM')); });
    const duplicate = structuredClone(bundle); duplicate.nodes.push(structuredClone(duplicate.nodes[0])); duplicate.expected_counts.nodes = duplicate.nodes.length;
    assert(Either.isLeft(decodeKgBundleSource({ sourceId: 'duplicate', rawBytes: Buffer.from(json(duplicate)) }, 'v2'))); rejected.push('duplicate owned UID');
    const dangling = structuredClone(bundle); dangling.relations[0].to_uid = 'sym:Concept:missing-whole-map-target';
    assert(Either.isLeft(decodeKgBundleSource({ sourceId: 'dangling', rawBytes: Buffer.from(json(dangling)) }, 'v2'))); rejected.push('dangling relationship endpoint');
    const sample = inputs.additions[0];
    assert.throws(() => validateRecord({ ...sample, topic: 'unknown-topic' }, inputs.registry.topics, inputs.files)); rejected.push('unknown addition topic');
    assert.throws(() => validateRecord({ ...sample, source_locator: 'not present in source' }, inputs.registry.topics, inputs.files)); rejected.push('bad addition locator');
    const badCorpus = structuredClone(inputs.corpus); badCorpus.rows[0].disposition = badCorpus.rows[0].disposition === 'CURATED_SOURCE' ? 'INVENTORIED_ONLY' : 'CURATED_SOURCE';
    assert.throws(() => verifyCorpus({ ...inputs, corpus: badCorpus }, bundle)); rejected.push('corpus disposition drift');
    const badShaCorpus = structuredClone(inputs.corpus); badShaCorpus.rows[0].sha256 = '0'.repeat(64);
    assert.throws(() => verifyCorpus({ ...inputs, corpus: badShaCorpus }, bundle)); rejected.push('corpus SHA drift');
    return rejected;
  });
}

const main = Effect.gen(function* () {
  const record = process.argv.slice(2); assert(record.length === 0 || (record.length === 1 && record[0] === '--record'), 'Usage: node _research/whole_map_2026-10-01/verify.mts [--record]');
  const { inputs, bundle, bytes } = yield* build();
  const checkedBundle = yield* io(() => sourceBytes(output));
  const checkedCorpus = yield* io(() => sourceBytes(corpusPath));
  assert.deepEqual(checkedBundle, bytes, 'generated whole-map bundle differs; run build.mts --write explicitly');
  sameJson(checkedCorpus, inputs.corpus, 'generated corpus differs; run build.mts --write explicitly');
  checkCounts(inputs, bundle); verifyCorpus(inputs, bundle);
  const projection = compile(bundle);
  const nativeShape = yield* io(() => sourceBytes('schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl'));
  const localShape = yield* io(() => sourceBytes(`${queryBase}/shapes.ttl`));
  const shacl = [] as any[];
  for (const [name, shape] of [['native-v2', nativeShape], ['whole-map', localShape]] as const) {
    const report = yield* validateKgShacl(projection, shape); assert(report.conforms, json(report));
    shacl.push({ name, conforms: report.conforms, engine: report.engine, profile: report.profile, sha256: sha(shape) });
  }
  const queries: Record<string, any[]> = {};
  for (let index = 1; index <= 8; index += 1) {
    const query = (yield* io(() => sourceBytes(`${queryBase}/q${index}.rq`))).toString();
    queries[`q${index}`] = rows(yield* queryKgBundle(projection, query));
  }
  expectQueryResults(queries, inputs, bundle);
  const rejected = yield* expectMutants(inputs, bundle, localShape);
  const exportFiles = [
    ['rdf/dataset.nq', projection.nquads],
    ['rdf/descriptor.json', Buffer.from(json(projection.descriptor))],
    ['rdf/provenance.jsonld', projection.provO]
  ] as const;
  const toolchainPaths = ['src/hswm/effect-runtime/dist/native-kg-bundle-domain.js', 'src/hswm/effect-runtime/dist/native-kg-standards.js', 'src/hswm/effect-runtime/dist/native-kg-vendor.js', 'src/hswm/effect-runtime/package-lock.json'];
  const toolchain = [] as any[];
  for (const path of toolchainPaths) toolchain.push({ path, sha256: sha(yield* io(() => sourceBytes(path))) });
  const validation = {
    schema_version: 'hswm-whole-map-validation/v1', source_revision: cut, checked_at: new Date().toISOString(), node_version: process.version,
    scope: 'Fixed subject-corpus cut plus separately SHA-bound post-cut curation, generator, query and toolchain inputs; bundle/corpus equality, local RDF/SHACL/SPARQL structure and negative mutations. No live KG, model, Lean, service, or efficacy run.',
    toolchain, bundle_sha256: sha(bytes), corpus_sha256: sha(json(inputs.corpus)),
    exports: Object.fromEntries(exportFiles.map(([path, data]) => [path, { sha256: sha(data), bytes: data.length }])),
    shacl, competency_questions: Object.fromEntries(Object.entries(queries).map(([key, result]) => [key, { passed: true, rows: result.length }])),
    queries, rejected_mutations: rejected, claim_ceiling: 'WHOLE_MAP_STRUCTURE_AND_FIXED_CUT_BYTE_BINDING_ONLY'
  };
  if (record[0] === '--record') {
    const target = resolve(root, artifactBase);
    yield* io(() => mkdir(target, { recursive: false }));
    for (const [path, data] of exportFiles) {
      const destination = resolve(target, path); const directory = destination.slice(0, destination.lastIndexOf('/'));
      yield* io(() => mkdir(directory, { recursive: true })); yield* io(() => writeFile(destination, data));
    }
    yield* io(() => writeFile(resolve(target, 'validation.v1.json'), json(validation)));
  }
  // Re-running verification checks recorded outputs too, without refreshing their date or hashes.
  const saved = yield* io(async () => {
    try { return JSON.parse((await readFile(resolve(root, artifactBase, 'validation.v1.json'))).toString()); }
    catch (error: any) { if (error.code === 'ENOENT') return null; throw error; }
  });
  if (saved) {
    assert.equal(saved.bundle_sha256, validation.bundle_sha256);
    assert.equal(saved.corpus_sha256, validation.corpus_sha256);
    assert.deepEqual(saved.exports, validation.exports);
    assert.deepEqual(saved.queries, validation.queries);
    assert.deepEqual(saved.rejected_mutations, validation.rejected_mutations);
    for (const [path, data] of exportFiles) assert.deepEqual(yield* io(() => readFile(resolve(root, artifactBase, path))), Buffer.from(data), `Recorded export drift: ${path}`);
  }
  console.log(json({ passed: true, record: record[0] === '--record', bundle_sha256: validation.bundle_sha256, corpus_sha256: validation.corpus_sha256, questions: validation.competency_questions, rejected_mutations: rejected.length }));
});

if (import.meta.main) await Effect.runPromise(main);
