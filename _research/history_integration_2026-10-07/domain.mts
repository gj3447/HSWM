/** Source-scoped navigation only. No identity merge, canon promotion or learned W. */
import { createHash } from 'node:crypto';
import { posix } from 'node:path';
import { strict as assert } from 'node:assert';

export const base = '_research/history_integration_2026-10-07';
export const sha = (x: string | Uint8Array) => createHash('sha256').update(x).digest('hex');
export const json = (x: unknown) => JSON.stringify(x, null, 2) + '\n';
export const uid = (s: string) => `sym:AbstractNode:hswm-history-20261007-${sha(s)}`;
export const rootUid = uid('root');
export const excluded = (p: string) => /(^|\/)(node_modules|vendor|\.git|\.venv|\.hswm-local|dist|build)(\/|$)/.test(p)
  || /(^|\/)(\.env(?:\..*)?|credentials[^/]*|id_rsa|id_ed25519|\.mcp\.json)$|\.(?:pem|key|sqlite|sqlite3|db)$/i.test(p);
export const textCandidate = (p: string) => !excluded(p) && /\.(?:md|txt|json|jsonld|usl|ts|mts|js|mjs|py|lean|rs|ttl|rq|yaml|yml|toml)$/.test(p);
export const sourceKey = (repo: string, path: string) => `${repo}:${path}`;
export const isDocument = (p: string) => /\.(md|txt|usl)$/.test(p) || /(^|\/)ontology\/.*\.json$/.test(p);
export function liveOccurrences(c: any) {
  const out: any[] = [];
  for (const [recordIndex, r] of (c.live_kg?.records ?? []).entries()) {
    for (const [rowIndex, row] of (Array.isArray(r.data) ? r.data : []).entries()) {
      const id = row?.uid ?? row?.neighbor_uid ?? row?.verdict_uid;
      if (typeof id === 'string') out.push({ uid: id, operation: r.operation, record_index: recordIndex, row_index: rowIndex, original: row });
    }
  }
  return out;
}
export function resolveCitations(c: any) {
  const paths = new Set(c.inventory.map((s: any) => sourceKey(s.repo, s.path))), directories = new Set<string>();
  for (const s of c.inventory) {
    directories.add(sourceKey(s.repo, ''));
    for (let dir = posix.dirname(s.path); dir !== '.' && dir !== ''; dir = posix.dirname(dir)) directories.add(sourceKey(s.repo, dir));
  }
  return c.citations.map((x: any) => x.kind !== 'FILE_CITATION' ? x : { ...x,
    resolution: paths.has(sourceKey(x.repo, x.path)) ? 'AT_CAPTURED_CUT'
      : directories.has(sourceKey(x.repo, x.path.replace(/\/$/, ''))) ? 'DIRECTORY_VIEW_AT_CAPTURED_CUT' : 'NOT_AT_CAPTURED_CUT' });
}
export function parseTree(raw: Buffer) {
  return raw.toString().split('\0').filter(Boolean).map(row => {
    const tab = row.indexOf('\t'); assert(tab > 0);
    const [mode, type, oid] = row.slice(0, tab).split(' ');
    return { path: row.slice(tab + 1), mode, type, oid };
  });
}
export function parseChanges(raw: Buffer) {
  const parts = raw.toString().split('\0'); const out: any[] = [];
  for (let i = 0; i < parts.length && parts[i]; i += 2) {
    const m = parts[i].match(/^:(\d+) (\d+) ([a-f0-9]+) ([a-f0-9]+) ([AMDTUXB])$/);
    assert(m && parts[i + 1], 'Expected exact no-renames raw Git diff');
    out.push({ path: parts[i + 1], old_mode: m[1], new_mode: m[2], old_oid: m[3], new_oid: m[4], status: m[5] });
  }
  return out;
}
export function parseCommit(oid: string, bytes: Buffer) {
  assert.equal(createHash('sha1').update(`commit ${bytes.length}\0`).update(bytes).digest('hex'), oid);
  const split = bytes.indexOf('\n\n'), header = bytes.subarray(0, split).toString();
  const time = (role: string) => {
    const m = header.match(new RegExp(`^${role} .* ([0-9]+) ([+-][0-9]{4})$`, 'm'));
    assert(m, `Missing ${role} timestamp`);
    return { unix_seconds: Number(m[1]), timezone: m[2], utc: new Date(Number(m[1]) * 1000).toISOString() };
  };
  return { oid, tree: header.match(/^tree ([a-f0-9]+)$/m)![1], parents: [...header.matchAll(/^parent ([a-f0-9]+)$/gm)].map(m => m[1]),
    authored: time('author'), committed: time('committer'), subject: bytes.subarray(split + 2).toString().split('\n')[0], sha256: sha(bytes) };
}
/** Literal citations preserve occurrences and fragments; they do not imply support. */
export function citations(repo: string, path: string, text: string, repos: Set<string>) {
  const rows: any[] = [];
  for (const m of text.matchAll(/\[[^\]\n]*\]\(([^)\n]+)\)/g)) {
    const raw = m[1].replace(/^<|>$/g, '').split(/\s+"/)[0];
    if (!raw || raw.startsWith('#')) continue;
    if (/^[a-z][a-z0-9+.-]*:/i.test(raw)) {
      // Credential-bearing URLs are never copied into the index.
      try { const u = new URL(raw); if (u.username || u.password || u.search) continue; } catch { continue; }
      if (/^https?:\/\//.test(raw)) rows.push({ raw, kind: 'EXTERNAL_URL', offset: m.index });
      continue;
    }
    if (raw.startsWith('/')) continue;
    let decoded: string; try { decoded = decodeURIComponent(raw.split('#')[0]); } catch { continue; }
    const target = posix.normalize(posix.join(repo, posix.dirname(path), decoded));
    const slash = target.indexOf('/'), targetRepo = target.slice(0, slash), targetPath = target.slice(slash + 1);
    rows.push({ kind: 'FILE_CITATION', repo: targetRepo, path: targetPath, fragment: raw.split('#')[1] ?? '',
      raw, offset: m.index, scope_status: repos.has(targetRepo) ? 'SELECTED_REPOSITORY' : 'OUTSIDE_SELECTED_REPOSITORIES' });
  }
  return rows;
}
export function indexJson(source: any, bytes: Buffer) {
  let b: any; try { b = JSON.parse(bytes.toString()); } catch { return { nodes: [], relations: [], bundle: null }; }
  const nodes: any[] = [], relations: any[] = [];
  for (const [i, n] of (Array.isArray(b.nodes) ? b.nodes : []).entries()) if (typeof n?.uid === 'string') {
    const p = n.properties ?? n;
    nodes.push({ source: source.key, source_sha256: source.sha256, pointer: `/nodes/${i}`, uid: n.uid,
      name: p.name ?? p.title ?? n.uid, authority_class: p.authority_class ?? 'UNSPECIFIED',
      canonical_scope: p.canonical_scope ?? 'UNSPECIFIED', status: p.status ?? 'UNSPECIFIED',
      record_lifecycle: p.record_lifecycle ?? 'UNSPECIFIED', role: p.standard_graph_role ?? 'UNSPECIFIED' });
  }
  for (const [i, r] of (Array.isArray(b.relations) ? b.relations : []).entries()) if (r && typeof r === 'object') {
    relations.push({ source: source.key, source_sha256: source.sha256, pointer: `/relations/${i}`, original: r });
  }
  return { nodes, relations, bundle: typeof b.bundle_uid === 'string' ? { source: source.key, uid: b.bundle_uid, schema: b.schema_version ?? null } : null };
}
export function validateCatalog(c: any) {
  assert.equal(c.schema, 'hswm-history-catalog/v1');
  const keys = new Set(c.sources.map((s: any) => s.key)); assert.equal(keys.size, c.sources.length);
  for (const repo of c.repositories) {
    const commits = c.commits.filter((x: any) => x.repo === repo.id), ids = new Set(commits.map((x: any) => x.oid));
    assert.equal(ids.size, commits.length); assert(ids.has(repo.cut));
    for (const x of commits) for (const p of x.parents) assert(ids.has(p), `Missing Git parent ${p}`);
    for (const x of c.changes.filter((x: any) => x.repo === repo.id)) {
      assert(ids.has(x.commit)); assert(x.parent === null || ids.has(x.parent));
      assert.equal(x.parent, commits.find((k: any) => k.oid === x.commit).parents[0] ?? null);
    }
  }
  for (const s of c.sources) { assert.equal(s.key, sourceKey(s.repo, s.path)); assert(/^[a-f0-9]{64}$/.test(s.sha256)); assert(!excluded(s.path)); }
  const seen = new Set<string>();
  for (const n of c.kg_nodes) {
    assert(keys.has(n.source)); const key = `${n.source}${n.pointer}`; assert(!seen.has(key)); seen.add(key);
    assert.equal(c.sources.find((s: any) => s.key === n.source).sha256, n.source_sha256);
  }
  return true;
}
/** Compact standard graph: commits + document sources + explicit citations, with indexes retained separately. */
export function makeBundle(c: any, bindings: any[]) {
  const nodes: any[] = [], relations: any[] = [], seen = new Set<string>();
  const add = (key: string, role: string, name: string, extra: any = {}) => {
    const id = uid(key); nodes.push({ uid: id, labels: ['AbstractNode'], properties: {
      name: name || key, standard_graph_role: role, authority_class: 'SECONDARY_AI', canonical_scope: 'PENDING_OR_PRELIMINARY',
      ontology_plane: 'INQUIRY', actor: 'agent:codex', recorded_on: '2026-10-07', runtime_write_path: false,
      claim_boundary: 'HISTORICAL_NAVIGATION_NOT_CANONICAL_STATE_OR_EFFICACY', ...extra } }); return id;
  };
  const link = (a: string, type: string, b: string, scope: string) => {
    const k = `${a}|${type}|${b}|${scope}`; if (seen.has(k)) return; seen.add(k);
    relations.push({ from_uid: a, type, to_uid: b, scope, status: 'PROPOSED', authority_class: 'SECONDARY_AI' });
  };
  add('root', 'HISTORY_INDEX', 'HSWM source-bound history', { full_semantic_audit: false, live_kg_complete: false });
  for (const r of c.repositories) {
    add(`repo:${r.id}`, 'REPOSITORY_VIEW', r.id, { repository_id: r.id, source_revision: r.cut });
    link(rootUid, 'HAS_VIEW', uid(`repo:${r.id}`), 'SELECTED_OWNER_REPOSITORY');
  }
  // HSWM's complete captured reachable history. Other repositories' full commit tables stay in the catalog.
  for (const x of c.commits.filter((x: any) => x.repo === 'HSWM')) {
    const id = add(`commit:${x.repo}:${x.oid}`, 'GIT_COMMIT', x.subject, { repository_id: x.repo, commit_oid: x.oid,
      committed_at: x.committed.utc, authored_at: x.authored.utc, git_object_sha256: x.sha256 });
    link(uid('repo:HSWM'), 'HAS_CONTENT', id, 'CAPTURED_REACHABLE_COMMIT');
    for (const [i, p] of x.parents.entries()) link(id, 'REFERENCES', uid(`commit:HSWM:${p}`), `GIT_PARENT_INDEX_${i}`);
  }
  const docs = c.sources.filter((s: any) => isDocument(s.path)), docKeys = new Set(docs.map((s: any) => s.key));
  for (const s of docs) {
    add(`source:${s.key}`, 'SOURCE_VIEW', s.title, { repository_id: s.repo, source_path: s.path, source_revision: s.revision,
      source_sha256: s.sha256, source_bytes: s.bytes, git_blob_oid: s.oid });
    link(uid(`repo:${s.repo}`), 'HAS_SOURCE', uid(`source:${s.key}`), 'SOURCE_OCCURRENCE_AT_FIXED_CUT');
  }
  for (const x of c.citations) if (x.kind === 'FILE_CITATION' && docKeys.has(x.source) && docKeys.has(sourceKey(x.repo, x.path)))
    link(uid(`source:${x.source}`), 'REFERENCES', uid(`source:${sourceKey(x.repo, x.path)}`), 'EXPLICIT_CITATION_NOT_DEPENDENCY_OR_SUPPORT');
  for (const s of docs.filter((s: any) => s.repo === 'HSWM'))
    link(uid(`source:${s.key}`), 'REFERENCES', uid(`commit:HSWM:${s.revision}`), 'EXACT_SOURCE_CUT_NOT_EVENT_TIME');
  for (const x of c.changes.filter((x: any) => x.repo === 'HSWM' && docKeys.has(sourceKey(x.repo, x.path))))
    link(uid(`commit:HSWM:${x.commit}`), 'REFERENCES', uid(`source:${sourceKey(x.repo, x.path)}`), 'CHANGED_PATH_SEE_CATALOG_FOR_HISTORICAL_PREIMAGE_NOT_CURRENT_BYTES');
  const liveIds = new Set<string>(liveOccurrences(c).map(x => x.uid));
  for (const id of liveIds) {
    add(`live:${id}`, 'LIVE_KG_REFERENCE', id, { original_uid: id, observation_complete: false,
      source_observation: 'catalog.live_kg.records; retain original authority, edge status and API scope there' });
    link(rootUid, 'REFERENCES', uid(`live:${id}`), 'BOUNDED_API_OBSERVATION_NOT_GLOBAL_KG');
  }
  for (const n of c.kg_nodes) if (liveIds.has(n.uid) && docKeys.has(n.source))
    link(uid(`source:${n.source}`), 'REFERENCES', uid(`live:${n.uid}`), 'EXACT_NATIVE_UID_OCCURRENCE_NOT_AUTHORITY_OR_VERSION_EQUIVALENCE');
  for (const group of c.same_bytes) {
    const members = group.occurrences.filter((key: string) => docKeys.has(key));
    if (members.length < 2) continue;
    add(`content:${group.sha256}`, 'CONTENT_IDENTITY', `sha256:${group.sha256}`, { content_sha256: group.sha256 });
    for (const member of members) link(uid(`source:${member}`), 'HAS_CONTENT', uid(`content:${group.sha256}`), 'EXACT_BYTES_NOT_ENTITY_EQUIVALENCE');
  }
  return { schema_version: 'hswm-history-integration/v1', bundle_uid: rootUid, status: 'SOURCE_BOUND_NAVIGATION',
    nonclaim: 'Historical source navigation, not canonical state, identity merging, execution authority, learning or efficacy.',
    artifact_bindings: bindings, anchors: [], nodes, relations,
    expected_counts: { nodes: nodes.length, anchors: 0, relations: relations.length } };
}
