/** Bounded owner-selected local discovery. Never contacts a remote or follows a symlink. */
import { resolve } from 'node:path';
import { strict as assert } from 'node:assert';
import { readFile } from 'node:fs/promises';
import { base, sha, json, excluded, textCandidate, sourceKey, parseTree, parseChanges, parseCommit, citations, indexJson, validateCatalog, makeBundle, resolveCitations } from './domain.mts';
import { Effect, io, read, write, git, objects, print, load } from './io.mts';

export const collectRepo = (r: any) => Effect.gen(function* () {
  assert(/^[A-Z][A-Z0-9_]*$/.test(r.id)); assert(/^[a-f0-9]{40}$/.test(r.cut));
  const maximumTextBytes = r.maximum_text_bytes ?? 8 * 1024 * 1024;
  assert(Number.isSafeInteger(maximumTextBytes) && maximumTextBytes > 0 && maximumTextBytes <= 32 * 1024 * 1024);
  const tips = [...new Set([r.cut, ...r.refs.map((x: any) => x.oid)])] as string[];
  for (const tip of tips) assert(/^[a-f0-9]{40}$/.test(tip));
  const ids = (yield* git(r.root, ['rev-list', '--topo-order', ...tips])).toString().trim().split('\n');
  const rawCommits = yield* objects(r.root, ids, 'commit');
  const commits = ids.map(oid => ({ repo: r.id, ...parseCommit(oid, rawCommits.get(oid)!) }));
  const tree = parseTree(yield* git(r.root, ['ls-tree', '-r', '-z', r.cut]));
  const candidates = tree.filter(t => t.type === 'blob' && t.mode !== '120000' && textCandidate(t.path));
  const sizes = (yield* git(r.root, ['cat-file', '--batch-check=%(objectname) %(objectsize)'], candidates.map(t => t.oid).join('\n') + '\n')).toString().trim().split('\n');
  const sizeMap = new Map(sizes.map(row => { const [oid, size] = row.split(' '); return [oid, Number(size)]; }));
  const bounded = candidates.filter(t => sizeMap.get(t.oid)! <= maximumTextBytes);
  const blobs = yield* objects(r.root, [...new Set(bounded.map(t => t.oid))], 'blob');
  const selected = bounded.filter(t => r.id === 'HSWM' || r.id === 'HSWM_LIKENESS' || /hswm/i.test(t.path) || /hswm/i.test(blobs.get(t.oid)!.toString()));
  const selectedPaths = new Set(selected.map(t => t.path));
  const changes = (yield* Effect.forEach(commits, c => Effect.gen(function* () {
    const args = c.parents.length ? ['diff-tree', '--no-commit-id', '-r', '--raw', '-z', '--no-renames', c.parents[0], c.oid]
      : ['diff-tree', '--root', '--no-commit-id', '-r', '--raw', '-z', '--no-renames', c.oid];
    return parseChanges(yield* git(r.root, args)).filter(x => r.id === 'HSWM' || selectedPaths.has(x.path) || /hswm/i.test(x.path))
      .map(x => ({ repo: r.id, commit: c.oid, parent: c.parents[0] ?? null, ...x }));
  }), { concurrency: 4 })).flat();
  const inventory = tree.map(t => ({ repo: r.id, revision: r.cut, ...t, disposition: selectedPaths.has(t.path) ? 'INDEXED_SOURCE'
    : t.type !== 'blob' ? 'GITLINK_NOT_EXPANDED' : t.mode === '120000' ? 'SYMLINK_NOT_FOLLOWED' : excluded(t.path) ? 'EXCLUDED_PATH'
      : sizeMap.get(t.oid)! > maximumTextBytes ? 'OVER_TEXT_BUDGET' : 'METADATA_ONLY' }));
  const sources = selected.map(t => {
    const bytes = blobs.get(t.oid)!, text = bytes.toString();
    return { key: sourceKey(r.id, t.path), repo: r.id, revision: r.cut, ...t, sha256: sha(bytes), bytes: bytes.length,
      title: (text.match(/^#\s+(.+)$/m)?.[1] ?? t.path), selection: r.id === 'HSWM' || r.id === 'HSWM_LIKENESS' ? 'OWNER_CORPUS' : /hswm/i.test(t.path) ? 'LITERAL_PATH_MATCH' : 'LITERAL_CONTENT_MATCH' };
  });
  return { commits, changes, inventory, sources, blobs,
    repository: { id: r.id, cut: r.cut, refs: r.refs, maximum_text_bytes: maximumTextBytes, captured_commits: commits.length, selected_sources: sources.length,
      selection: 'HSWM and HSWM_LIKENESS nonexcluded text corpus; other owners: literal HSWM in current path or content, plus history of those paths and historical HSWM paths',
      worktree_status: r.worktree_status, shallow: (yield* git(r.root, ['rev-parse', '--is-shallow-repository'])).toString().trim() === 'true' } };
});

export const build = (config: any) => Effect.gen(function* () {
  const repositories: any[] = [], commits: any[] = [], changes: any[] = [], inventory: any[] = [], sources: any[] = [], citationRows: any[] = [], kg_nodes: any[] = [], kg_relations: any[] = [], bundles: any[] = [];
  const names = new Set<string>(config.repositories.map((r: any) => r.id));
  for (const r of config.repositories) {
    const x = yield* collectRepo(r); repositories.push(x.repository); commits.push(...x.commits); changes.push(...x.changes); inventory.push(...x.inventory); sources.push(...x.sources);
    for (const s of x.sources) {
      const bytes = x.blobs.get(s.oid)!;
      if (/\.(md|txt)$/.test(s.path)) citationRows.push(...citations(s.repo, s.path, bytes.toString(), names).map(c => ({ source: s.key, source_sha256: s.sha256, ...c })));
      if (s.path.endsWith('.json')) { const k = indexJson(s, bytes); kg_nodes.push(...k.nodes); kg_relations.push(...k.relations); if (k.bundle) bundles.push(k.bundle); }
    }
    process.stderr.write(`${r.id}: ${x.sources.length} sources, ${x.commits.length} commits, ${x.changes.length} changes\n`);
  }
  const catalog: any = { schema: 'hswm-history-catalog/v1', recorded_at: config.recorded_at,
    policy: { authority: 'SECONDARY_AI_NAVIGATION', historical_time: 'Git authored/committed times only; no event time inferred from filenames',
      history_diff: 'Every captured reachable commit retained. Exact first-parent changes; roots compared to empty tree; no similarity rename inference. Other parents remain in the commit DAG.',
      limitations: ['Not a global live KG export', 'No hidden/unreachable Git objects or uncaptured remotes', 'Dirty and untracked work excluded from source bytes; status only',
        'Other repositories selected by explicit literal HSWM matching, not an exhaustive semantic classification', 'Symlinks, submodules, credential-looking paths, vendored code and oversized text not expanded',
        'No remote hosts, private chat stores or ignored experiment payloads read', 'No HSWM execution/admission/learning or efficacy claim'] },
    repositories, commits, changes, inventory, sources, citations: citationRows, kg_nodes, kg_relations, bundles };
  const byHash = new Map<string, any[]>();
  for (const s of sources) byHash.set(s.sha256, [...(byHash.get(s.sha256) ?? []), s.key]);
  catalog.same_bytes = [...byHash].filter(([, rows]) => new Set(rows.map((s: string) => s.split(':')[0])).size > 1).map(([sha256, occurrences]) => ({ sha256, occurrences, meaning: 'EXACT_BYTES_NOT_ENTITY_EQUIVALENCE' }));
  validateCatalog(catalog);
  return catalog;
});

if (import.meta.main) await Effect.runPromise(Effect.gen(function* () {
  const [configPath, output, fromFlag, previous] = process.argv.slice(2);
  assert(configPath && output && (process.argv.length === 4 || (process.argv.length === 6 && fromFlag === '--from' && previous)), 'Usage: node build.mts PRIVATE_CONFIG NEW_OUTPUT_DIRECTORY [--from VERIFIED_INVENTORY_DIRECTORY]');
  const config = JSON.parse((yield* read(resolve(configPath))).toString());
  const tooling: Record<string, string> = {};
  for (const f of ['domain.mts', 'io.mts', 'build.mts', 'cli.mts', 'verify.mts', 'shapes.ttl', 'timeline.rq', 'sources.rq']) tooling[`${base}/${f}`] = sha(yield* io(() => readFile(resolve(base, f))));
  const prior = previous ? yield* load(previous) : null;
  if (prior) assert.equal(prior.manifest.config_sha256, sha(json(config)), 'Cannot reuse another source scope');
  const catalog = prior ? prior.catalog : yield* build(config);
  catalog.citations = resolveCitations(catalog);
  if (config.kg_snapshot) catalog.live_kg = JSON.parse((yield* read(resolve(config.kg_snapshot))).toString());
  const raw = Buffer.from(json(catalog));
  // Preserve the expensive inventory even if projection qualification fails.
  yield* write(resolve(output, 'catalog.json'), raw);
  const bundle = makeBundle(catalog, [{ path: 'catalog.json', sha256: sha(raw) }]), bundleBytes = Buffer.from(json(bundle));
  const { decodeKgBundleSource } = yield* Effect.promise(() => import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js'));
  const { Either } = yield* Effect.promise(() => import('./io.mts'));
  const decoded = decodeKgBundleSource({ sourceId: 'history', rawBytes: bundleBytes }, 'v2');
  assert(Either.isRight(decoded), Either.isLeft(decoded) ? decoded.left.detail : '');
  const files: Record<string, string> = { 'catalog.json': sha(raw), 'bundle.json': sha(bundleBytes) };
  for (const [path, digest] of Object.entries(tooling)) assert.equal(sha(yield* read(resolve(path))), digest, 'Generator changed while running');
  yield* write(resolve(output, 'bundle.json'), bundleBytes);
  yield* write(resolve(output, 'manifest.json'), json({ schema: 'hswm-history-manifest/v1', recorded_at: config.recorded_at, config_sha256: sha(json(config)), files, tooling,
    reused_inventory_manifest_sha256: prior ? sha(yield* read(resolve(previous!, 'manifest.json'))) : null,
    counts: { repositories: catalog.repositories.length, commits: catalog.commits.length, changes: catalog.changes.length, inventory: catalog.inventory.length, sources: catalog.sources.length,
      kg_nodes: catalog.kg_nodes.length, kg_relations: catalog.kg_relations.length, citations: catalog.citations.length, same_bytes_groups: catalog.same_bytes.length, graph: bundle.expected_counts } }));
  print({ status: 'CREATED_LOCAL_SOURCE_BOUND_INDEX', output: resolve(output), counts: { sources: catalog.sources.length, commits: catalog.commits.length, changes: catalog.changes.length, ...bundle.expected_counts } });
}));
