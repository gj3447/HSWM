/** Read-only audit; --record writes fresh exports and a verification record exclusively. */
import { strict as assert } from 'node:assert';
import { resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import { base, sha, json, uid, rootUid, parseTree, parseChanges, indexJson, validateCatalog, makeBundle, isDocument, sourceKey, resolveCitations } from './domain.mts';
import { Effect, Either, read, write, git, objects, load, print } from './io.mts';
import { query, readOriginal } from './cli.mts';

const sort = (x: any[]) => x.map(x => JSON.stringify(x)).sort();
export function fixtures() {
  assert.deepEqual(parseTree(Buffer.from('100644 blob ' + 'a'.repeat(40) + '\t한글\tname.md\0'))[0].path, '한글\tname.md');
  const changes = parseChanges(Buffer.from(`:100644 000000 ${'a'.repeat(40)} ${'0'.repeat(40)} D\0old.md\0:000000 100644 ${'0'.repeat(40)} ${'a'.repeat(40)} A\0new.md\0`));
  assert.equal(changes[0].status, 'D'); assert.equal(changes[1].status, 'A'); assert.equal(changes[0].old_oid, changes[1].new_oid);
  const b = Buffer.from(json({ nodes: [{ uid: 'same', properties: { authority_class: 'USER_PRIMARY', status: 'RETIRED' } }, { uid: 'same', properties: { authority_class: 'SECONDARY_AI' } }], relations: [{ from_uid: 'same', to_uid: 'else', type: 'REFERENCES', status: 'RETIRED', roles: ['a', 'b'] }] }));
  const indexed = indexJson({ key: 'HSWM:fixture.json', sha256: sha(b) }, b);
  assert.equal(indexed.nodes.length, 2); assert.notEqual(indexed.nodes[0].pointer, indexed.nodes[1].pointer);
  assert.equal(indexed.nodes[0].authority_class, 'USER_PRIMARY'); assert.equal(indexed.relations[0].original.status, 'RETIRED');
  assert.deepEqual(indexed.relations[0].original.roles, ['a', 'b']);
  assert.deepEqual(resolveCitations({ inventory: [{ repo: 'HSWM', path: 'docs/a.md' }], citations: [
    { kind: 'FILE_CITATION', repo: 'HSWM', path: 'docs/' }, { kind: 'FILE_CITATION', repo: 'HSWM', path: 'absent.md' }
  ] }).map(x => x.resolution), ['DIRECTORY_VIEW_AT_CAPTURED_CUT', 'NOT_AT_CAPTURED_CUT']);
}

if (import.meta.main) await Effect.runPromise(Effect.gen(function* () {
  const [directory, configPath, flag] = process.argv.slice(2);
  assert(directory && configPath && (!flag || flag === '--record'), 'Usage: node verify.mts SNAPSHOT PRIVATE_CONFIG [--record]');
  const { catalog: c, manifest, root } = yield* load(directory), config = JSON.parse((yield* read(resolve(configPath))).toString());
  assert.equal(sha(json(config)), manifest.config_sha256, 'Config changed since capture');
  for (const [path, digest] of Object.entries(manifest.tooling)) assert.equal(sha(yield* read(resolve(path))), digest, `Tooling drift: ${path}`);
  const bundleRaw = yield* read(resolve(root, 'bundle.json')); assert.equal(sha(bundleRaw), manifest.files['bundle.json']);
  const bundle = JSON.parse(bundleRaw.toString()); validateCatalog(c); fixtures();
  assert.deepEqual(c.citations, resolveCitations(c));
  assert.deepEqual(bundle, makeBundle(c, [{ path: 'catalog.json', sha256: manifest.files['catalog.json'] }]));
  const ids = new Set(bundle.nodes.map((n: any) => n.uid)); assert.equal(ids.size, bundle.nodes.length);
  for (const r of bundle.relations) { assert(ids.has(r.from_uid) && ids.has(r.to_uid)); assert.equal(r.status, 'PROPOSED'); }
  let originals = 0, pointerChecks = 0;
  for (const repo of c.repositories) {
    const rc = config.repositories.find((r: any) => r.id === repo.id); assert(rc);
    const expectedIds = (yield* git(rc.root, ['rev-list', ...new Set([repo.cut, ...repo.refs.map((r: any) => r.oid)])])).toString().trim().split('\n').sort();
    assert.deepEqual(c.commits.filter((x: any) => x.repo === repo.id).map((x: any) => x.oid).sort(), expectedIds, 'Full captured reachability');
    const tree = parseTree(yield* git(rc.root, ['ls-tree', '-r', '-z', repo.cut]));
    assert.deepEqual(c.inventory.filter((x: any) => x.repo === repo.id).map((x: any) => [x.path, x.mode, x.type, x.oid]), tree.map(x => [x.path, x.mode, x.type, x.oid]));
    const sources = c.sources.filter((s: any) => s.repo === repo.id), blobs = yield* objects(rc.root, [...new Set(sources.map((s: any) => s.oid))] as string[], 'blob');
    for (const s of sources) {
      const raw = blobs.get(s.oid)!; assert.equal(sha(raw), s.sha256); assert.equal(raw.length, s.bytes); originals++;
      const actual = indexJson(s, raw);
      assert.deepEqual(c.kg_nodes.filter((x: any) => x.source === s.key), actual.nodes);
      assert.deepEqual(c.kg_relations.filter((x: any) => x.source === s.key), actual.relations);
      pointerChecks += actual.nodes.length + actual.relations.length;
    }
    // Independently replay every selected change's raw first-parent diff. Full HSWM expected diff completeness is checked.
    const all = c.commits.filter((x: any) => x.repo === repo.id), selectedPaths = new Set(sources.map((s: any) => s.path));
    for (const commit of all) {
      const argv = commit.parents.length ? ['diff-tree', '--no-commit-id', '-r', '--raw', '-z', '--no-renames', commit.parents[0], commit.oid] : ['diff-tree', '--root', '--no-commit-id', '-r', '--raw', '-z', '--no-renames', commit.oid];
      const expected = parseChanges(yield* git(rc.root, argv)).filter(x => repo.id === 'HSWM' || selectedPaths.has(x.path) || /hswm/i.test(x.path));
      const actual = c.changes.filter((x: any) => x.repo === repo.id && x.commit === commit.oid).map(({ repo, commit, parent, ...x }: any) => x);
      assert.deepEqual(actual, expected, `Change inventory ${repo.id}:${commit.oid}`);
    }
    process.stderr.write(`Verified ${repo.id}: sources and change history\n`);
  }
  const { compileKgBundle } = yield* Effect.promise(() => import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js'));
  const { validateKgShacl, queryKgBundle } = yield* Effect.promise(() => import('../../src/hswm/effect-runtime/dist/native-kg-standards.js'));
  const projection = compileKgBundle([{ sourceId: 'history', rawBytes: bundleRaw }], 'v2');
  assert(Either.isRight(projection), Either.isLeft(projection) ? projection.left.detail : '');
  const p = projection.right;
  const shapes = yield* read(resolve(base, 'shapes.ttl')), validation = yield* validateKgShacl(p, shapes); assert(validation.conforms, json(validation));
  const terms = (x: any[]) => x.map(row => Object.fromEntries(Object.entries(row).map(([k, v]: any) => [k, v.value])));
  const timeline = terms(yield* queryKgBundle(p, (yield* read(resolve(base, 'timeline.rq'))).toString()));
  assert.deepEqual(sort(timeline), sort(c.commits.filter((x: any) => x.repo === 'HSWM').map((x: any) => ({ oid: x.oid, subject: x.subject, committed: x.committed.utc }))));
  const sources = terms(yield* queryKgBundle(p, (yield* read(resolve(base, 'sources.rq'))).toString()));
  assert.deepEqual(sort(sources), sort(c.sources.filter((s: any) => isDocument(s.path)).map((s: any) => ({ repo: s.repo, path: s.path, revision: s.revision, digest: s.sha256 }))));
  const mutation = structuredClone(bundle); mutation.relations[0].to_uid = uid('missing');
  assert(Either.isLeft(compileKgBundle([{ sourceId: 'bad', rawBytes: Buffer.from(json(mutation)) }], 'v2')), 'Missing endpoint must fail');
  const badAuthority = structuredClone(bundle); badAuthority.nodes[0].properties.authority_class = 'USER_PRIMARY';
  const bp = compileKgBundle([{ sourceId: 'bad-authority', rawBytes: Buffer.from(json(badAuthority)) }], 'v2');
  if (Either.isRight(bp)) assert(!(yield* validateKgShacl(bp.right, shapes)).conforms);
  const duplicate = structuredClone(c); duplicate.sources.push(duplicate.sources[0]); assert.throws(() => validateCatalog(duplicate));
  const migrate = query(c, 'path', ['SYMPOSIUM', 'HSWM/README.md']); assert(migrate.source && migrate.changes.total > 0);
  const migrationOriginal = yield* readOriginal(c, config, 'SYMPOSIUM', 'HSWM/README.md'); assert(migrationOriginal.text.includes('2026-08-10'));
  const negative = query(c, 'search', ['negative']); assert(negative.total > 0);
  const canon = yield* readOriginal(c, config, 'HSWM', 'docs/canon/HSWM_CONSTITUTION_2026-08-20.md'); assert(canon.text.length > 0);
  const uslGraph = query(c, 'usl', ['HSWM', 'docs/canon/HSWM_CONSTITUTION_2026-08-20.md']);
  const uslRoot = config.repositories.find((r: any) => r.id === 'USL').root;
  const { adaptPropertyGraph } = yield* Effect.promise(() => import(resolve(uslRoot, 'dist/src/integrations/property-graph.js')));
  const adapted = adaptPropertyGraph(json(uslGraph), { namespace: 'hswm.history' }); assert.equal(adapted._tag, 'Right');
  const toolchain = { node: process.version, native_compiler_sha256: sha(yield* read(resolve('src/hswm/effect-runtime/dist/native-kg-bundle-domain.js'))),
    native_standards_sha256: sha(yield* read(resolve('src/hswm/effect-runtime/dist/native-kg-standards.js'))),
    usl_adapter_sha256: sha(yield* read(resolve(uslRoot, 'dist/src/integrations/property-graph.js'))) };
  const report = { schema: 'hswm-history-verification/v1', status: 'PASS', manifest_sha256: sha(yield* read(resolve(root, 'manifest.json'))),
    originals, source_scoped_pointers: pointerChecks, commits: c.commits.length, first_parent_changes: c.changes.length,
    shacl: validation, queries: { timeline_rows: timeline.length, source_rows: sources.length, exact_answers_compared: true },
    rejection_checks: ['duplicate source', 'missing graph endpoint', 'authority promotion'],
    competency_checks: ['SYMPOSIUM migration original', 'negative-result discovery', 'constitution original', 'USL compiled source/revision roles'],
    usl_source_digest: adapted.right.source.digest, toolchain, limitations: c.policy.limitations };
  if (flag === '--record') {
    yield* write(resolve(root, 'verification.json'), json(report));
    yield* write(resolve(root, 'rdf/dataset.nq.gz'), gzipSync(p.nquads));
    yield* write(resolve(root, 'rdf/descriptor.json'), json(p.descriptor));
    yield* write(resolve(root, 'rdf/provenance.jsonld'), p.provO);
    yield* write(resolve(root, 'usl-example.graph.json'), json(uslGraph));
    yield* write(resolve(root, 'usl-example.compiled.json'), json(adapted.right));
  }
  print(report);
}));
