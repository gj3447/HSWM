import { strict as assert } from 'node:assert';
import { resolve } from 'node:path';
import { sha, sourceKey, uid, excluded, textCandidate, liveOccurrences } from './domain.mts';
import { Effect, read, git, objects, load, print } from './io.mts';

export function page(rows: any[], offset = 0, limit = 50) {
  assert(Number.isSafeInteger(offset) && offset >= 0 && Number.isSafeInteger(limit) && limit >= 1 && limit <= 1000);
  return { total: rows.length, offset, limit, next_offset: offset + limit < rows.length ? offset + limit : null, rows: rows.slice(offset, offset + limit) };
}
export function query(c: any, command: string, args: string[]) {
  if (command === 'overview') return { repositories: c.repositories, counts: { commits: c.commits.length, changes: c.changes.length, sources: c.sources.length, kg_nodes: c.kg_nodes.length, kg_relations: c.kg_relations.length }, policy: c.policy };
  if (command === 'timeline') {
    const [repo = 'HSWM', term = '', offset = '0', limit = '50'] = args;
    return page(c.commits.filter((x: any) => x.repo === repo && `${x.subject} ${x.committed.utc} ${x.oid}`.toLowerCase().includes(term.toLowerCase()))
      .sort((a: any, b: any) => a.committed.utc.localeCompare(b.committed.utc) || a.oid.localeCompare(b.oid)), Number(offset), Number(limit));
  }
  if (command === 'search') {
    const [term, offset = '0', limit = '50'] = args; assert(term?.trim(), 'Search requires a literal term'); const q = term.toLowerCase();
    const currentPaths = new Set(c.inventory.map((x: any) => sourceKey(x.repo, x.path)));
    const historicalPaths = [...new Set<string>(c.changes.map((x: any) => sourceKey(x.repo, x.path)))].filter(x => !currentPaths.has(x) && x.toLowerCase().includes(q));
    const rows = [...c.sources.filter((x: any) => `${x.key} ${x.title}`.toLowerCase().includes(q)).map((x: any) => ({ kind: 'SOURCE', ...x })),
      ...historicalPaths.map(key => ({ kind: 'HISTORICAL_PATH_NOT_AT_CUT', key })),
      ...c.kg_nodes.filter((x: any) => `${x.uid} ${x.name}`.toLowerCase().includes(q)).map((x: any) => ({ kind: 'KG_OCCURRENCE', ...x })),
      ...c.commits.filter((x: any) => x.subject.toLowerCase().includes(q)).map((x: any) => ({ kind: 'COMMIT', ...x }))];
    return { match: 'LITERAL_METADATA_NOT_FULLTEXT_OR_SEMANTIC_SEARCH', ...page(rows, Number(offset), Number(limit)) };
  }
  if (command === 'path') {
    const [repo, path, offset = '0', limit = '50'] = args; assert(repo && path);
    const key = sourceKey(repo, path), source = c.sources.find((x: any) => x.key === key) ?? null;
    const changes = c.changes.filter((x: any) => x.repo === repo && x.path === path);
    const oids = new Set([...(source ? [source.oid] : []), ...changes.flatMap((x: any) => [x.old_oid, x.new_oid])].filter((x: string) => !/^0+$/.test(x)));
    const byteMatches = new Map<string, any>();
    for (const x of c.sources) if (x.key !== key && oids.has(x.oid)) byteMatches.set(x.key, { repo: x.repo, path: x.path, oid: x.oid, basis: 'EXACT_GIT_BLOB' });
    for (const x of c.changes) if (sourceKey(x.repo, x.path) !== key && (oids.has(x.old_oid) || oids.has(x.new_oid))) {
      const k = sourceKey(x.repo, x.path); if (!byteMatches.has(k)) byteMatches.set(k, { repo: x.repo, path: x.path, oid: oids.has(x.new_oid) ? x.new_oid : x.old_oid, basis: 'EXACT_GIT_BLOB_IN_HISTORY' });
    }
    return { source, scope: 'First-parent changes; byte matches do not prove entity identity or causal migration', changes: page(changes, Number(offset), Number(limit)),
      byte_matches: page([...byteMatches.values()], Number(offset), Number(limit)), citations: page(c.citations.filter((x: any) => x.source === key || sourceKey(x.repo, x.path) === key), Number(offset), Number(limit)) };
  }
  if (command === 'kg') {
    const [id, offset = '0', limit = '50'] = args; assert(id);
    return { uid: id, interpretation: 'Source-scoped occurrences; choose source and pointer. No merged authority or current-state selection.',
      nodes: page(c.kg_nodes.filter((x: any) => x.uid === id), Number(offset), Number(limit)),
      relations: page(c.kg_relations.filter((x: any) => x.original.from_uid === id || x.original.to_uid === id), Number(offset), Number(limit)),
      live_observations: page(liveOccurrences(c).filter(x => x.uid === id), Number(offset), Number(limit)),
      live_subject_reads: (c.live_kg?.records ?? []).filter((r: any) => r.args?.uid === id || r.args?.subject_uid === id) };
  }
  if (command === 'gaps') {
    const [offset = '0', limit = '50'] = args;
    return { limitations: c.policy.limitations, unresolved_citations: page(c.citations.filter((x: any) => x.kind === 'FILE_CITATION' && x.resolution === 'NOT_AT_CAPTURED_CUT'), Number(offset), Number(limit)),
      unexpanded: page(c.inventory.filter((x: any) => ['GITLINK_NOT_EXPANDED', 'SYMLINK_NOT_FOLLOWED', 'EXCLUDED_PATH', 'OVER_TEXT_BUDGET'].includes(x.disposition)), Number(offset), Number(limit)),
      dirty_repositories: c.repositories.filter((r: any) => r.worktree_status.length).map((r: any) => ({ id: r.id, status: r.worktree_status })) };
  }
  if (command === 'usl') {
    const [repo, path, kgUid] = args, key = sourceKey(repo, path), s = c.sources.find((x: any) => x.key === key); assert(s, 'Source not indexed');
    const source = uid(`source:${key}`), revision = uid(`commit:${repo}:${s.revision}`);
    // Portable logical locators; no actual checkout roots or resolver access is disclosed.
    const nodes: any[] = [{ uid: source, properties: { locator: `kg://hswm-history-local/${source}` } },
      { uid: revision, properties: { locator: `kg://hswm-history-local/${revision}` } }];
    const relations: any[] = [{ uid: uid(`usl:${key}`), from_uid: source, to_uid: revision, type: 'REFERENCES', properties: {
      description: `File occurrence ${key} is bound to Git ${s.revision}, blob ${s.oid}, sha256 ${s.sha256}; no resolver access or authority is granted.`,
      participants: [{ role: 'source', uid: source }, { role: 'revision', uid: revision }],
      contract: { scope: 'EXACT_SOURCE_BINDING_NOT_EXECUTION', checks: [{ name: 'bytes', description: 'Resolve through the owner-scoped CLI read and verify Git object/SHA-256.', evidenceRoles: ['source', 'revision'] }] } } }];
    if (kgUid) {
      assert(c.kg_nodes.some((x: any) => x.source === key && x.uid === kgUid), 'KG UID must occur in this exact source');
      nodes.push({ uid: kgUid, properties: { locator: `kg://canonical-neo4j/${kgUid}` } });
      relations[0].properties.participants.push({ role: 'kg_referent', uid: kgUid });
      relations[0].properties.description += ` Native UID ${kgUid} occurs in this source; its live version and authority are not inferred.`;
    }
    return { nodes, relations };
  }
  throw new Error(`Unknown command: ${command}`);
}

export const readOriginal = (c: any, config: any, repo: string, path: string, requestedOid?: string) => Effect.gen(function* () {
  assert(textCandidate(path) && !excluded(path), 'Path excluded from source reads');
  const r = config.repositories.find((x: any) => x.id === repo); assert(r, 'Repository not configured');
  const s = c.sources.find((x: any) => x.repo === repo && x.path === path);
  const oid = requestedOid ?? s?.oid; assert(oid && /^[a-f0-9]{40}$/.test(oid), 'Use an indexed source or explicit historical blob OID');
  assert(s?.oid === oid || c.changes.some((x: any) => x.repo === repo && x.path === path && [x.old_oid, x.new_oid].includes(oid)), 'Blob is outside this source history');
  const maximumTextBytes = c.repositories.find((x: any) => x.id === repo).maximum_text_bytes ?? 8 * 1024 * 1024;
  const size = Number((yield* git(r.root, ['cat-file', '-s', oid])).toString()); assert(size <= maximumTextBytes, 'Historical blob exceeds read budget');
  const bytes = (yield* objects(r.root, [oid], 'blob')).get(oid)!;
  if (s?.oid === oid) assert.equal(sha(bytes), s.sha256, 'Pinned source SHA drift');
  return { repo, path, oid, sha256: sha(bytes), bytes: bytes.length, text: new TextDecoder('utf-8', { fatal: true }).decode(bytes) };
});

if (import.meta.main) await Effect.runPromise(Effect.gen(function* () {
  const [dir, command, ...args] = process.argv.slice(2);
  assert(dir && command, 'Usage: node cli.mts SNAPSHOT <overview|timeline|search|path|kg|gaps|usl|read> ...');
  const { catalog } = yield* load(dir);
  if (command === 'read') {
    const [configPath, repo, path, oid] = args; assert(configPath && repo && path);
    print(yield* readOriginal(catalog, JSON.parse((yield* read(resolve(configPath))).toString()), repo, path, oid));
  } else print(query(catalog, command, args));
}));
