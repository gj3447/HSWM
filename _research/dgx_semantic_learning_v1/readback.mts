import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { digest } from './domain.mts';
const require = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url));
const { Effect } = require('effect'), neo4j = require('neo4j-driver');
const { parseNativeDevelopmentProjectionSourceConfig } = await import('../../src/hswm/effect-runtime/dist/native-development-projection-publisher.js');
const config = await Effect.runPromise(parseNativeDevelopmentProjectionSourceConfig(await readFile(process.argv[2], 'utf8')));
const raw = await readFile('ontology/development/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.v1.json');
const bundle = JSON.parse(raw.toString()), hash = digest(raw);
const normalize = (x: any): any => neo4j.isInt(x) ? x.toNumber() : Array.isArray(x) ? x.map(normalize) : x && typeof x === 'object'
  ? Object.fromEntries(Object.keys(x).sort().map(k => [k, normalize(x[k])])) : x;
const equal = (a: any, b: any) => JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
const driver = neo4j.driver(config.uri, neo4j.auth.basic(config.user, config.password), { maxTransactionRetryTime: 0 });
const session = driver.session({ database: config.database, defaultAccessMode: neo4j.session.READ });
try {
  const nodes = await session.run('MATCH (n {ontology_bundle_uid:$uid}) RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties', { uid: bundle.bundle_uid });
  const edges = await session.run('MATCH (a)-[r {ontology_bundle_uid:$uid}]->(b) RETURN a.uid AS from_uid, b.uid AS to_uid, type(r) AS type, properties(r) AS properties', { uid: bundle.bundle_uid });
  if (nodes.records.length !== bundle.nodes.length || edges.records.length !== bundle.relations.length) throw new Error('Live counts differ');
  for (const row of bundle.nodes) {
    const found = nodes.records.filter((r: any) => r.get('uid') === row.uid);
    if (found.length !== 1 || !equal(found[0].get('labels').sort(), [...row.labels].sort()) || !equal(found[0].get('properties'),
      { ...row.properties, uid: row.uid, ontology_bundle_uid: bundle.bundle_uid, ontology_projection_sha256: hash })) throw new Error('Live node mismatch ' + row.uid);
  }
  for (const row of bundle.relations) {
    const found = edges.records.filter((r: any) => r.get('from_uid') === row.from_uid && r.get('to_uid') === row.to_uid && r.get('type') === row.type);
    if (found.length !== 1 || !equal(found[0].get('properties'), { ontology_bundle_uid: bundle.bundle_uid, ontology_projection_sha256: hash,
      authority_class: row.authority_class, scope: row.scope, status: row.status })) throw new Error('Live relation mismatch');
  }
  const report = { schema_version: 'hswm-post-commit-readback/v1', at: new Date().toISOString(), bundle_uid: bundle.bundle_uid,
    bundle_sha256: hash, nodes: nodes.records.length, relations: edges.records.length, exactNodePropertiesAndLabels: true,
    exactRelationPropertiesAndEndpoints: true, freshReadSessionAfterPublication: true, nonclaim: 'EXACT_RESEARCH_PROJECTION_READBACK_NOT_TRUTH_OR_EFFICACY' };
  await writeFile('docs/research/artifacts/hswm_dgx_frontier_2026-09-20/post-commit-readback.v1.json', JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify(report));
} finally { await session.close(); await driver.close(); }
