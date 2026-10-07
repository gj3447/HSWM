import { resolve } from 'node:path';
import { strict as assert } from 'node:assert';
import { Effect, read, write, load, print } from './io.mts';
import { base, sha, sourceKey, liveOccurrences } from './domain.mts';
await Effect.runPromise(Effect.gen(function* () {
  const [directory, configPath, output, worktreeDirectory] = process.argv.slice(2); assert(directory && configPath && output);
  const { catalog: c, manifest, root } = yield* load(directory);
  const verification = JSON.parse((yield* read(resolve(root, 'verification.json'))).toString()); assert.equal(verification.status, 'PASS');
  assert.equal(verification.manifest_sha256, sha(yield* read(resolve(root, 'manifest.json'))));
  const current = new Set(c.inventory.map((s: any) => sourceKey(s.repo, s.path))), deleted = new Map<string, any>();
  for (const x of c.changes) { const key = sourceKey(x.repo, x.path); if (!current.has(key)) deleted.set(key, { key, repo: x.repo, path: x.path }); }
  const live = new Map<string, any[]>(); for (const x of liveOccurrences(c)) live.set(x.uid, [...(live.get(x.uid) ?? []), x]);
  let worktree = null;
  if (worktreeDirectory) {
    const raw = yield* read(resolve(worktreeDirectory, 'worktree.json')); const captured = JSON.parse(raw.toString());
    assert.equal(captured.config_sha256, manifest.config_sha256);
    for (const s of captured.sources) assert.equal(sha(yield* read(resolve(worktreeDirectory, 'blobs', s.sha256))), s.sha256);
    worktree = { ...captured, directory: worktreeDirectory, manifest_sha256: sha(raw) };
  }
  const data = { snapshot: directory, config: configPath, worktree, catalog_sha256: manifest.files['catalog.json'], recorded_at: c.recorded_at, verified: 'PASS',
    repositories: c.repositories.map((r: any) => ({ id: r.id, cut: r.cut })), sources: c.sources,
    commits: c.commits.map((x: any) => ({ repo: x.repo, oid: x.oid, subject: x.subject, date: x.committed.utc, parents: x.parents })).sort((a: any, b: any) => a.date.localeCompare(b.date)),
    hswm_commits: c.commits.filter((x: any) => x.repo === 'HSWM').length, changes: c.changes, kg: c.kg_nodes,
    live: [...live].map(([uid, observations]) => ({ uid, observations })), citations: c.citations.filter((x: any) => x.kind === 'FILE_CITATION'),
    deleted: [...deleted.values()], gaps: c.citations.filter((x: any) => x.kind === 'FILE_CITATION' && x.resolution === 'NOT_AT_CAPTURED_CUT') };
  const template = (yield* read(resolve(base, 'explorer.html'))).toString(); assert.equal(template.split('__HISTORY_DATA__').length, 2);
  const html = template.replace('__HISTORY_DATA__', JSON.stringify(data).replaceAll('<', '\\u003c').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029'));
  yield* write(resolve(output), html); print({ output: resolve(output), bytes: Buffer.byteLength(html), sha256: sha(html) });
}));
