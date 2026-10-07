/** Optional immutable working-copy observations. Never mixed into Git/canonical source versions. */
import { resolve, relative } from 'node:path';
import { open, realpath, lstat } from 'node:fs/promises';
import { constants } from 'node:fs';
import { strict as assert } from 'node:assert';
import { Effect, io, read, write, git, print } from './io.mts';
import { base, textCandidate, sha, json, sourceKey, indexJson } from './domain.mts';

await Effect.runPromise(Effect.gen(function* () {
  const [command, first, second, repo, path] = process.argv.slice(2);
  if (command === 'read') {
    const manifestRaw = yield* read(resolve(first, 'worktree.json')), manifest = JSON.parse(manifestRaw.toString());
    const source = manifest.sources.find((x: any) => x.repo === second && x.path === repo); assert(source, 'Unknown working-copy observation');
    const bytes = yield* read(resolve(first, 'blobs', source.sha256)); assert.equal(sha(bytes), source.sha256);
    print({ ...source, text: new TextDecoder('utf-8', { fatal: true }).decode(bytes) }); return;
  }
  assert(command === 'capture' && first && second && !repo, 'Usage: worktree.mts capture PRIVATE_CONFIG NEW_DIRECTORY | read DIRECTORY REPO PATH');
  const config = JSON.parse((yield* read(resolve(first))).toString()), output = resolve(second), sources: any[] = [], skipped: any[] = [], kg_nodes: any[] = [], kg_relations: any[] = [];
  const blobs = new Map<string, Buffer>();
  for (const r of config.repositories) {
    const changed = (yield* git(r.root, ['diff', '--name-only', '-z', r.cut])).toString().split('\0').filter(Boolean);
    const untracked = (yield* git(r.root, ['ls-files', '--others', '--exclude-standard', '-z'])).toString().split('\0').filter(Boolean);
    for (const path of [...new Set([...changed, ...untracked])].sort()) {
      if (!textCandidate(path) || path.startsWith(base + '/') || /(^|\/)(\.claude|\.codex|\.agents|output)(\/|$)/.test(path)
          || /(^|\/)(settings\.local\.json|secrets?[^/]*)$/i.test(path)) continue;
      const absolute = resolve(r.root, path), rel = relative(r.root, absolute); assert(!rel.startsWith('..') && !rel.startsWith('/'));
      const result = yield* io(async () => {
        try {
          const stat = await lstat(absolute); if (!stat.isFile() || stat.isSymbolicLink()) return { skipped: 'NOT_REGULAR_FILE' };
          if (await realpath(absolute) !== absolute) return { skipped: 'SYMLINK_ANCESTOR' };
          if (stat.size > (r.maximum_text_bytes ?? 8 * 1024 * 1024)) return { skipped: 'OVER_TEXT_BUDGET' };
          const file = await open(absolute, constants.O_RDONLY | constants.O_NOFOLLOW);
          try {
            const before = await file.stat(), bytes = await file.readFile(), after = await file.stat();
            if (before.ino !== after.ino || before.mtimeMs !== after.mtimeMs || before.size !== after.size || after.size !== bytes.length) return { skipped: 'CHANGED_DURING_READ' };
            const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
            if (!['HSWM', 'HSWM_LIKENESS'].includes(r.id) && !/hswm/i.test(path + '\n' + text)) return { skipped: 'NO_LITERAL_HSWM_MATCH' };
            return { bytes, title: text.match(/^#\s+(.+)$/m)?.[1] ?? path };
          } finally { await file.close(); }
        } catch (e: any) { return { skipped: e.code === 'ENOENT' ? 'ABSENT_OR_DELETED' : 'READ_REFUSED' }; }
      });
      if (!result.bytes) { skipped.push({ repo: r.id, path, reason: result.skipped }); continue; }
      const digest = sha(result.bytes), source = { key: sourceKey(r.id, path), repo: r.id, path, base_revision: r.cut,
        observation_status: untracked.includes(path) ? 'UNTRACKED_WORKTREE_BYTES' : 'WORKTREE_DIFFERS_FROM_CAPTURED_CUT',
        title: result.title, sha256: digest, bytes: result.bytes.length, observed_at: new Date().toISOString(),
        authority_class: 'SECONDARY_AI_OBSERVATION_NOT_SOURCE_AUTHORITY', content_location: `blobs/${digest}` };
      sources.push(source); blobs.set(digest, result.bytes);
      if (path.endsWith('.json')) { const k = indexJson(source, result.bytes); kg_nodes.push(...k.nodes); kg_relations.push(...k.relations); }
    }
  }
  for (const [digest, bytes] of blobs) { yield* write(resolve(output, 'blobs', digest), bytes); assert.equal(sha(yield* read(resolve(output, 'blobs', digest))), digest); }
  const manifest = { schema: 'hswm-history-worktree-observations/v1', captured_at: new Date().toISOString(), config_sha256: sha(json(config)),
    boundary: 'Observed working-copy bytes, not Git commit contents, user canon, completed work or execution authority. Sources may subsequently change.',
    sources, skipped, kg_nodes, kg_relations, verification: { source_blobs_rehashed: blobs.size, status: 'PASS' } };
  yield* write(resolve(output, 'worktree.json'), json(manifest));
  print({ output, sources: sources.length, kg_node_occurrences: kg_nodes.length, kg_relation_occurrences: kg_relations.length, skipped: skipped.length, status: 'CAPTURED_AND_REHASHED' });
}));
