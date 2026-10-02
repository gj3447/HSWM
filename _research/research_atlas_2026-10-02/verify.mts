/** Read-only qualification of the fixed-cut research atlas.  --record is the sole writer. */
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';
import { gzipSync, gunzipSync } from 'node:zlib';
import { performance } from 'node:perf_hooks';
import { strict as assert } from 'node:assert';
import { build } from './build.mts';
import { Effect, Either, readOriginal, root } from './io.mts';
import { artifacts, base, catalogPath, cut, entityPath, json, output, queryBase, sections, sha, selectUnits, localContext, uid, validateCuration } from './domain.mts';

const { Effect: NativeEffect } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
assert.equal(NativeEffect, Effect, 'atlas must use the local Effect runtime');
const { compileKgBundle, decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const { validateKgShacl, queryKgBundle } = await import('../../src/hswm/effect-runtime/dist/native-kg-standards.js');
const io = <A>(op: () => Promise<A>) => Effect.tryPromise({ try: op, catch: (e: unknown) => new Error(String(e)) });
const bytesAt = (path: string) => io(() => readFile(resolve(root, path)));
const termRows = (result: any) => {
  assert(Array.isArray(result), 'competency query must be SELECT');
  return result.map((row: any) => Object.fromEntries(Object.entries(row).map(([key, term]: any) => [key, term?.value ?? null])));
};
const compile = (bundle: any) => {
  const result = compileKgBundle([{ sourceId: 'research-atlas', rawBytes: Buffer.from(json(bundle)) }], 'v2');
  if (Either.isLeft(result)) throw new Error(result.left.detail);
  return result.right;
};
const sorted = (items: any[]) => [...items].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));

function verifyCatalog(catalog: any, snapshot: any) {
  assert.equal(catalog.source_revision, cut);
  assert.equal(catalog.files.length, snapshot.tree.length, 'catalog must inventory every fixed-cut path');
  assert.equal(new Set(catalog.files.map((f: any) => f.path)).size, snapshot.tree.length, 'catalog path duplicate');
  for (const row of catalog.files) {
    const original = snapshot.files.get(row.path); assert(original, `catalog path absent from cut: ${row.path}`);
    assert.equal(row.sha256, sha(original), `catalog SHA mismatch: ${row.path}`);
    assert.equal(row.bytes, original.length, `catalog byte count mismatch: ${row.path}`);
  }
  const main = [...snapshot.files.keys()].filter(path => /^docs\/research\/[^/]+\.md$/.test(path)).sort();
  assert.deepEqual(catalog.documents.filter((d: any) => d.source_kind === 'MAIN_RESEARCH').map((d: any) => d.path).sort(), main, 'all 157 direct research docs must be indexed');
  assert.equal(catalog.documents.filter((d: any) => d.curation).length, main.length, 'all direct research docs must be curated');
}

function verifySpans(catalog: any, snapshot: any) {
  for (const doc of catalog.documents) {
    const original = snapshot.files.get(doc.path)!;
    assert(original, `document absent from fixed cut: ${doc.path}`);
    assert.equal(doc.sha256, sha(original)); assert.equal(doc.bytes, original.length);
    const exact = /\.(md|txt)$/.test(doc.path) ? sections(original) : [{ id: 'full', title: '원문 전체', level: 0, start_byte: 0, end_byte: original.length }];
    assert.deepEqual(doc.sections, exact, `section index drift: ${doc.path}`);
    assert.equal(doc.sections[0].id, 'full'); assert.equal(doc.sections[0].start_byte, 0); assert.equal(doc.sections[0].end_byte, original.length);
    for (const span of doc.sections) {
      assert(Number.isSafeInteger(span.start_byte) && Number.isSafeInteger(span.end_byte));
      assert(span.start_byte >= 0 && span.start_byte < span.end_byte && span.end_byte <= original.length, `bad section bounds: ${doc.path}:${span.id}`);
      new TextDecoder('utf-8', { fatal: true }).decode(original.subarray(span.start_byte, span.end_byte));
    }
    for (const span of doc.sections.filter((s: any) => s.id !== 'full')) {
      const descendants = doc.sections.filter((s: any) => s.id !== 'full' && s.start_byte > span.start_byte && s.start_byte < span.end_byte);
      assert(descendants.every((s: any) => s.level > span.level), `section hierarchy leaks peer/ancestor: ${doc.path}:${span.id}`);
    }
  }
}

/** Independent small fixture: byte offsets are UTF-8, and fenced pseudo-headings stay body text. */
function verifySectionFixture() {
  const raw = Buffer.from('# 한글\n본문\n```md\n## 가짜\n```\n## 실제\n끝\n', 'utf8');
  const indexed = sections(raw);
  const actual = indexed.map((s: any) => ({ id:s.id, title:s.title, level:s.level, start:s.start_byte, end:s.end_byte }));
  const second = Buffer.byteLength('# 한글\n본문\n```md\n## 가짜\n```\n', 'utf8');
  assert.deepEqual(actual, [
    { id:'full', title:'원문 전체', level:0, start:0, end:raw.length },
    { id:'section-0', title:'한글', level:1, start:0, end:raw.length },
    { id:`section-${second}`, title:'실제', level:2, start:second, end:raw.length }
  ]);
  const longFence = Buffer.from('````md\n```\n# still fenced\n````\n   # 진짜 C#\n');
  assert.deepEqual(sections(longFence).filter(s => s.level > 0).map(s => s.title), ['진짜 C#']);
}

function verifyEntities(entities: any, catalog: any, snapshot: any) {
  assert.equal(entities.source_revision, cut);
  const actual: any[] = [];
  const parsedByPath = new Map<string, any>();
  for (const doc of catalog.documents.filter((d: any) => d.source_kind === 'ONTOLOGY_SOURCE')) {
    const raw = snapshot.files.get(doc.path)!; const parsed = JSON.parse(raw.toString()); parsedByPath.set(doc.path, parsed);
    for (const [index, node] of (Array.isArray(parsed.nodes) ? parsed.nodes : []).entries()) if (typeof node.uid === 'string') actual.push({ uid: node.uid, path: doc.path, pointer: `/nodes/${index}`, source_sha256: doc.sha256 });
  }
  const indexed = entities.occurrences.map((o: any) => ({ uid: o.uid, path: o.path, pointer: o.pointer, source_sha256: o.source_sha256 }));
  assert.deepEqual(sorted(indexed), sorted(actual), 'entity index must retain every exact source-scoped UID occurrence');
  assert.equal(new Set(indexed.map((o: any) => `${o.uid}|${o.path}|${o.pointer}`)).size, indexed.length, 'entity occurrence duplicated');
  for (const occurrence of entities.occurrences) {
    const index = Number(occurrence.pointer.split('/').at(-1));
    assert.equal(parsedByPath.get(occurrence.path).nodes[index].uid, occurrence.uid, `entity pointer drift: ${occurrence.path}:${occurrence.pointer}`);
  }
}

function verifySavedExports(target: string, compressed: Buffer, projection: any, validation: any) {
  return Effect.gen(function* () {
    const exists = yield* io(() => stat(target).then(() => true, () => false)); if (!exists) return false;
    const gz = yield* io(() => readFile(resolve(target, 'rdf/dataset.nq.gz')));
    const descriptor = yield* io(() => readFile(resolve(target, 'rdf/descriptor.json')));
    const provenance = yield* io(() => readFile(resolve(target, 'rdf/provenance.jsonld')));
    const receipt = yield* io(() => readFile(resolve(target, 'validation.v1.json')));
    assert.deepEqual(gz, compressed, 'saved compressed dataset drift');
    assert.deepEqual(gunzipSync(gz), Buffer.from(projection.nquads), 'saved compressed dataset decompression drift');
    assert.deepEqual(descriptor, Buffer.from(json(projection.descriptor)), 'saved descriptor drift');
    assert.deepEqual(provenance, Buffer.from(projection.provO), 'saved provenance drift');
    const saved = JSON.parse(receipt.toString());
    assert.equal(saved.schema_version, validation.schema_version); assert.equal(saved.source_revision, cut);
    const { checked_at: _savedTime, node_version: _savedNode, ...savedStable } = saved;
    const { checked_at: _freshTime, node_version: _freshNode, ...freshStable } = validation;
    assert.deepEqual(savedStable, freshStable, 'saved validation receipt drift');
    return true;
  });
}

function expectedQueries(catalog: any, bundle: any) {
  const records = catalog.documents.filter((d: any) => d.curation);
  const unit = new Map(bundle.nodes.filter((n: any) => n.properties.standard_graph_role === 'RESEARCH_UNIT').map((n: any) => [n.properties.source_path, n]));
  const source = new Map(bundle.nodes.filter((n: any) => n.properties.standard_graph_role === 'SOURCE_VIEW').map((n: any) => [n.properties.source_path, n]));
  const bindings = bundle.nodes.filter((n: any) => n.properties.standard_graph_role === 'MAP_BINDING');
  const q1 = catalog.topics.map((t: any) => ({ topicId: t.id, title: t.title, units: String(records.filter((d: any) => d.curation.topics.includes(t.id)).length) }));
  const q2 = records.map((d: any) => ({ path:d.path, title:d.curation.title, summary:d.curation.summary, kind:d.curation.kind, status:d.curation.source_status, ceiling:d.curation.boundary, locator:d.curation.locator, sha256:d.sha256 }));
  const q3 = q2.filter((_: any, i: number) => records[i].curation.kind === 'FORMAL');
  const q4 = q2.filter((_: any, i: number) => records[i].curation.facets.includes('negative'));
  const group = new Map<string, any[]>(); for (const d of catalog.documents) group.set(d.source_kind, [...(group.get(d.source_kind) ?? []), d]);
  const q5 = [...group.entries()].map(([kind, docs]) => ({ source_kind:kind, sources:String(docs.length), bytes:String(docs.reduce((n: number, d: any) => n + d.bytes, 0)) }));
  const q6 = bindings.map((b: any) => ({ bindingUid:b.uid, topicId:b.properties.topic_id, path:b.properties.source_path, unitUid:unit.get(b.properties.source_path)!.uid, sourceId:source.get(b.properties.source_path)!.uid }));
  const indexedPaths = new Set(catalog.documents.map((d: any) => d.path));
  const pairs = new Map<string, any>();
  for (const d of catalog.documents) for (const c of d.citations) if (indexedPaths.has(c.path)) pairs.set(`${d.path}|${c.path}`, { sourcePath:d.path, targetPath:c.path });
  const q7 = [...pairs.values()];
  return { q1, q2, q3, q4, q5, q6, q7 };
}

function verifyQueries(actual: Record<string, any[]>, expected: any) {
  for (const key of ['q1','q2','q3','q4','q5','q6','q7'] as const) assert.deepEqual(sorted(actual[key]), sorted(expected[key]), `${key} result mismatch`);
  assert.deepEqual(actual.q8, [], 'q8 must report no local structural violations');
}

function checkSourceDigests(catalog: any, snapshot: any) {
  for (const doc of catalog.documents) {
    const raw = snapshot.files.get(doc.path)!;
    assert.equal(doc.sha256, sha(raw), `source hash mismatch: ${doc.path}`); assert.equal(doc.bytes, raw.length, `source bytes mismatch: ${doc.path}`);
  }
}

const main = Effect.gen(function* () {
  const args = process.argv.slice(2); assert(args.length === 0 || (args.length === 1 && args[0] === '--record'), `Usage: node ${base}/verify.mts [--record]`);
  const started = performance.now();
  const built: any = yield* build(); const { catalog, entities, bundle, bytes, artifacts: generated } = built;
  const snapshot = { tree: built.tree, files: built.files };
  assert.equal(bundle.source_accessed_on, '2026-10-02');
  for (const [path, expected] of generated as Map<string, Buffer>) assert.deepEqual(yield* bytesAt(path), expected, `checked artifact differs: ${path}; run build.mts --write explicitly`);
  assert.deepEqual(yield* bytesAt(output), bytes, 'bundle artifact differs');
  verifyCatalog(catalog, snapshot); verifySpans(catalog, snapshot); verifySectionFixture(); verifyEntities(entities, catalog, snapshot); checkSourceDigests(catalog, snapshot);

  const { run } = yield* Effect.promise(() => import('./cli.mts'));
  const sample = catalog.documents.find((d: any) => d.curation)!;
  const rawSample = yield* readOriginal(sample);
  assert.equal(yield* run(['read', sample.id, 'full']), new TextDecoder('utf-8', { fatal:true }).decode(rawSample), 'CLI full read must be exact original');
  const child = sample.sections.find((s: any) => s.id !== 'full');
  if (child) assert.equal(yield* run(['read', sample.id, child.id]), new TextDecoder('utf-8', { fatal:true }).decode(rawSample.subarray(child.start_byte, child.end_byte)), 'CLI child span must be exact original');
  const unicode = catalog.documents.find((d: any) => /[^\x00-\x7f]/.test(d.path));
  if (unicode) {
    const raw = yield* readOriginal(unicode), cliRaw = Buffer.from(yield* run(['read', unicode.id, 'full']), 'utf8');
    assert.equal(sha(cliRaw), unicode.sha256, 'Unicode-path CLI full read SHA'); assert.deepEqual(cliRaw, raw, 'Unicode-path CLI full read bytes');
    const sourceNode = bundle.nodes.find((n: any) => n.properties.standard_graph_role === 'SOURCE_VIEW' && n.properties.source_path === unicode.path);
    assert(sourceNode, 'Unicode-path source view missing'); assert.equal(sourceNode.properties.source_sha256, unicode.sha256);
  }

  const projection = compile(bundle);
  const nativeShape = yield* bytesAt('schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl');
  const localShape = yield* bytesAt(`${queryBase}/shapes.ttl`);
  const shacl: any[] = [];
  for (const [name, shape] of [['native-v2', nativeShape], ['research-atlas', localShape]] as const) { const report = yield* validateKgShacl(projection, shape); assert(report.conforms, json(report)); shacl.push({ name, conforms:report.conforms, engine:report.engine, profile:report.profile, sha256:sha(shape) }); }
  const queries: Record<string, any[]> = {};
  for (let n = 1; n <= 8; n++) queries[`q${n}`] = termRows(yield* queryKgBundle(projection, (yield* bytesAt(`${queryBase}/q${n}.rq`)).toString()));
  verifyQueries(queries, expectedQueries(catalog, bundle));

  const rejected: string[] = [];
  const rejectShape = (name: string, mutate: (b: any) => void) => Effect.gen(function* () { const b = structuredClone(bundle); mutate(b); b.expected_counts.nodes = b.nodes.length; b.expected_counts.relations = b.relations.length; const report = yield* validateKgShacl(compile(b), localShape); assert.equal(report.conforms, false, `${name} accepted by local SHACL`); rejected.push(name); });
  yield* rejectShape('authority promotion', b => { b.nodes.find((n: any) => n.properties.standard_graph_role === 'RESEARCH_UNIT').properties.authority_class = 'USER_PRIMARY'; });
  yield* rejectShape('source removal', b => { const n = b.nodes.find((x: any) => x.properties.standard_graph_role === 'RESEARCH_UNIT'); b.relations = b.relations.filter((r: any) => !(r.from_uid === n.uid && r.type === 'SUMMARIZES')); });
  yield* rejectShape('binding original role removed', b => { const n = b.nodes.find((x: any) => x.properties.standard_graph_role === 'MAP_BINDING'); b.relations = b.relations.filter((r: any) => !(r.from_uid === n.uid && r.type === 'HAS_ORIGINAL')); });
  const records = built.records as any[]; assert.throws(() => validateCuration(records.slice(1), catalog.topics, snapshot.files)); rejected.push('removed curation record');
  assert.throws(() => validateCuration([{ ...records[0], locator:'absent locator' }, ...records.slice(1)], catalog.topics, snapshot.files)); rejected.push('bad locator');
  const bad = structuredClone(catalog); bad.documents[0].sha256 = '0'.repeat(64); assert.throws(() => checkSourceDigests(bad, snapshot)); rejected.push('wrong source hash');
  const duplicate = structuredClone(bundle); duplicate.nodes.push(structuredClone(duplicate.nodes[0])); assert(Either.isLeft(decodeKgBundleSource({ sourceId:'duplicate',rawBytes:Buffer.from(json(duplicate)) }, 'v2'))); rejected.push('duplicate UID');
  const dangling = structuredClone(bundle); dangling.relations[0].to_uid = uid('missing'); assert(Either.isLeft(decodeKgBundleSource({ sourceId:'dangling',rawBytes:Buffer.from(json(dangling)) }, 'v2'))); rejected.push('dangling edge');

  const benchmarks: any[] = [];
  for (const query of ['HSWM_LEAN_VALIDATION_REVIEW','HSWM_DGX_FRONTIER_RESEARCH','HSWM_MAP_STATISTICAL_EMERGENCE','HYPERON_2026_DIRECT']) {
    const matched = selectUnits(catalog, { query }); assert.equal(matched.length, 1, `benchmark must select one exact document: ${query}`);
    const context = localContext(catalog, { query }, 1_000_000); assert.equal(context.status, 'SUMMARY_CONTEXT_READY'); assert.equal(context.items.length, 1); assert(context.items[0].original_command.includes(' read ') && context.items[0].sections_command.includes(' show '));
    const narrow = localContext(catalog, { query }, 1); assert.equal(narrow.status, 'NEEDS_NARROWING'); assert.deepEqual(narrow.items, []); assert.equal(narrow.omitted_to_fit, false);
    benchmarks.push({ query, paths:matched.map((d: any) => d.path), original_bytes:context.original_bytes, summary_bytes:Buffer.byteLength(json(context.items)), result:'SYNTHETIC_FIXED_CASE_NAVIGATION_NOT_SEMANTIC_QUALITY_OR_W' });
  }
  assert.throws(() => localContext(catalog, {}, 100)); rejected.push('implicit whole-corpus context');
  assert.throws(() => localContext(catalog, { query:'   ' }, 100)); rejected.push('blank-query whole-corpus context');
  const duplicateUid = entities.occurrences.find((o: any) => entities.occurrences.filter((p: any) => p.uid === o.uid).length > 1);
  if (duplicateUid) { const response = JSON.parse(yield* run(['entities', duplicateUid.uid])); assert.equal(response.status, 'SOURCE_SELECTION_REQUIRED'); }

  const nquads = Buffer.from(projection.nquads); const compressed = gzipSync(nquads); assert.deepEqual(gunzipSync(compressed), nquads, 'compressed dataset readback');
  const toolchainPaths = ['src/hswm/effect-runtime/dist/native-kg-bundle-domain.js','src/hswm/effect-runtime/dist/native-kg-standards.js','src/hswm/effect-runtime/dist/native-kg-vendor.js','src/hswm/effect-runtime/package-lock.json'];
  const toolchain: any[] = []; for (const path of toolchainPaths) toolchain.push({ path, sha256:sha(yield* bytesAt(path)) });
  const validation = { schema_version:'hswm-research-atlas-validation/v1', source_revision:cut, checked_at:new Date().toISOString(), node_version:process.version,
    scope:'Fixed-cut original source bytes plus separately SHA-bound post-cut curation, generator, query, shape and toolchain inputs; generated-artifact, graph-structure and local navigation checks. No external run, model, live graph write, truth audit, efficacy claim, or W evaluation.', toolchain, bundle_sha256:sha(bytes), shacl,
    competency_questions:Object.fromEntries(Object.entries(queries).map(([key, result]) => [key, { passed:true, rows:result.length }])), queries, rejected_mutations:rejected,
    retrieval_benchmarks:{ label:'SYNTHETIC_FIXED_CASE_NAVIGATION_NOT_SEMANTIC_QUALITY_OR_W', whole_corpus_original_bytes:catalog.documents.reduce((n: number, d: any) => n+d.bytes,0), cases:benchmarks },
    exports:{ 'rdf/dataset.nq.gz':{ sha256:sha(compressed), bytes:compressed.length, decompressed_nquads_sha256:sha(nquads), decompressed_bytes:nquads.length }, 'rdf/descriptor.json':{ sha256:sha(json(projection.descriptor)) }, 'rdf/provenance.jsonld':{ sha256:sha(projection.provO) } } };
  const saved_exports_readback = yield* verifySavedExports(resolve(root, artifacts), compressed, projection, validation);
  if (args[0] === '--record') {
    const target = resolve(root, artifacts); yield* io(() => mkdir(target, { recursive:false })); yield* io(() => mkdir(resolve(target, 'rdf'), { recursive:true }));
    for (const [path,data] of [['rdf/dataset.nq.gz',compressed],['rdf/descriptor.json',json(projection.descriptor)],['rdf/provenance.jsonld',projection.provO],['validation.v1.json',json(validation)]] as const) yield* io(() => writeFile(resolve(target,path),data));
  }
  process.stdout.write(json({ passed:true, artifacts_checked:generated.size, shacl, rejected_mutations:rejected.length, saved_exports_readback, elapsed_ms:Math.round(performance.now()-started), record:args[0] === '--record' }));
});
await Effect.runPromise(main);
