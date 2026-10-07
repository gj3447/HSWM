import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { strict as assert } from 'node:assert';
import { resolve, dirname } from 'node:path';
import { sha, json } from './domain.mts';
export const { Effect, Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
export const io = <A>(f: () => Promise<A>) => Effect.tryPromise({ try: f, catch: (e: unknown) => new Error(String(e)) });
export const read = (p: string) => io(() => readFile(p));
export const write = (p: string, b: string | Uint8Array) => Effect.gen(function* () {
  yield* io(() => mkdir(dirname(p), { recursive: true, mode: 0o700 }));
  yield* io(() => writeFile(p, b, { flag: 'wx', mode: 0o600 }));
});
export const git = (root: string, args: string[], input?: string, codes = [0]) => io(() => new Promise<Buffer>((ok, fail) => {
  const p = spawn('git', args, { cwd: root, stdio: ['pipe', 'pipe', 'pipe'] });
  const out: Buffer[] = [], err: Buffer[] = [];
  p.stdout.on('data', b => out.push(b)); p.stderr.on('data', b => err.push(b));
  p.on('error', fail); p.stdin.on('error', fail);
  p.on('close', code => codes.includes(code!) ? ok(Buffer.concat(out)) : fail(new Error(`git ${args[0]}: ${Buffer.concat(err)}`)));
  p.stdin.end(input);
}));
export const objects = (root: string, oids: string[], type: string) => Effect.gen(function* () {
  const result = new Map<string, Buffer>();
  for (let start = 0; start < oids.length; start += 64) {
    const selected = oids.slice(start, start + 64), raw = yield* git(root, ['cat-file', '--batch'], selected.join('\n') + '\n');
    let at = 0;
    for (const oid of selected) {
      const end = raw.indexOf(10, at), [actual, kind, size] = raw.subarray(at, end).toString().split(' ');
      assert.equal(actual, oid); assert.equal(kind, type);
      const bytes = raw.subarray(end + 1, end + 1 + Number(size)); assert.equal(bytes.length, Number(size));
      assert.equal(createHash('sha1').update(`${type} ${bytes.length}\0`).update(bytes).digest('hex'), oid);
      assert.equal(raw[end + 1 + Number(size)], 10); at = end + 2 + Number(size); result.set(oid, bytes);
    }
    assert.equal(at, raw.length);
  }
  return result;
});
export const load = (directory: string) => Effect.gen(function* () {
  const root = resolve(directory), manifest = JSON.parse((yield* read(resolve(root, 'manifest.json'))).toString());
  const get = (name: string) => Effect.gen(function* () {
    const bytes = yield* read(resolve(root, name)); assert.equal(sha(bytes), manifest.files[name], `Index binding drift: ${name}`); return JSON.parse(bytes.toString());
  });
  return { manifest, catalog: yield* get('catalog.json'), root };
});
export const print = (x: unknown) => process.stdout.write(json(x));
