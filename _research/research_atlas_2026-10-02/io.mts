/** Effect-wrapped local file/Git I/O. No model, network, graph database or runtime-state access. */
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import { createHash } from 'node:crypto';
import { strict as assert } from 'node:assert';
import { cut, base, catalogPath, entityPath, sha, json } from './domain.mts';
export const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
export const root = fileURLToPath(new URL('../../', import.meta.url));
export const io = <A>(f: () => Promise<A>) => Effect.tryPromise({ try: f, catch: (e: unknown) => new Error(String(e)) });
export const read = (path: string) => io(() => readFile(resolve(root, path)));
export const write = (path: string, data: string | Uint8Array) => Effect.gen(function* () {
  yield* io(() => mkdir(resolve(root, dirname(path)), { recursive: true }));
  yield* io(() => writeFile(resolve(root, path), data));
});
export const git = (args: string[], input?: string) => io(() => new Promise<Buffer>((ok, fail) => {
  const process = spawn('git', args, { cwd: root, stdio: ['pipe','pipe','pipe'] });
  const out: Buffer[] = [], err: Buffer[] = [];
  process.stdout.on('data', b => out.push(b)); process.stderr.on('data', b => err.push(b));
  process.on('error', fail); process.stdin.on('error', fail);
  process.on('close', code => code === 0 ? ok(Buffer.concat(out)) : fail(new Error(`git ${args[0]}: ${Buffer.concat(err)}`)));
  process.stdin.end(input);
}));
export const loadSnapshot = () => Effect.gen(function* () {
  const tree = (yield* git(['ls-tree','-r','-z',cut])).toString().split('\0').filter(Boolean).map(row => {
    const [meta, path] = row.split('\t'), [mode,type,oid] = meta.split(' '); assert.equal(type,'blob');
    return { path, git_mode: mode, git_blob_oid: oid };
  }).sort((a,b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
  const oids = [...new Set(tree.map(t => t.git_blob_oid))];
  const batch = yield* git(['cat-file','--batch'], oids.join('\n') + '\n');
  const blobs = new Map<string, Buffer>(); let at = 0;
  for (const oid of oids) {
    const end = batch.indexOf(10, at), [actual,type,size] = batch.subarray(at,end).toString().split(' ');
    assert.equal(actual,oid); assert.equal(type,'blob');
    const bytes = batch.subarray(end + 1,end + 1 + Number(size)); assert.equal(bytes.length,Number(size));
    assert.equal(createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex'),oid);
    assert.equal(batch[end + 1 + Number(size)],10); blobs.set(oid,bytes); at = end + 2 + Number(size);
  }
  assert.equal(at,batch.length);
  return { tree, files: new Map(tree.map(t => [t.path,blobs.get(t.git_blob_oid)!])) };
});
export const loadCuration = () => Effect.gen(function* () {
  const records: any[] = [];
  for (const suffix of ['a','b','c']) {
    const x = JSON.parse((yield* read(`${base}/curation-${suffix}.v1.json`)).toString());
    assert.equal(x.schema_version,'hswm-research-atlas-curation/v1'); assert.equal(x.source_revision,cut); records.push(...x.records);
  }
  return records.sort((a,b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
});
/** Catalog trust is pinned by the bundle's artifact bindings, not by a caller-supplied path. */
export const loadBoundCatalog = () => Effect.gen(function* () {
  const { output } = yield* Effect.promise(() => import('./domain.mts'));
  const bundle = JSON.parse((yield* read(output)).toString());
  const raw = yield* read(catalogPath), binding = bundle.artifact_bindings.find(b => b.path === catalogPath);
  assert(binding && sha(raw) === binding.sha256,'Catalog byte binding drift');
  const catalog = JSON.parse(raw.toString()); assert.equal(catalog.source_revision,cut);
  return { catalog, bundle };
});
export const loadBoundEntities = (bundle: any) => Effect.gen(function* () {
  const raw = yield* read(entityPath), binding = bundle.artifact_bindings.find(b => b.path === entityPath);
  assert(binding && sha(raw) === binding.sha256,'Entity index byte binding drift'); return JSON.parse(raw.toString());
});
export const readOriginal = (row: any) => Effect.gen(function* () {
  const bytes = yield* git(['show', `${cut}:${row.path}`]);
  assert.equal(sha(bytes),row.sha256,'Original source digest drift'); assert.equal(bytes.length,row.bytes);
  return bytes;
});
