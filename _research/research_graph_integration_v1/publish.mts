/** Publish only the reviewed 2026-09-20 bundle through the existing guarded adapter. */
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
const require = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url));
const { Effect, Either, Cause, Exit } = require('effect'), neo4j = require('neo4j-driver');
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const { makeNativeDevelopmentProjectionPublisher, parseNativeDevelopmentProjectionSourceConfig } = await import('../../src/hswm/effect-runtime/dist/native-development-projection-publisher.js');
const path = 'ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json';
const expected = 'b361596768c8e56807464b7723aea3c2bfdcfeb9644e04412a7ed82161c08453';
const reportPath = 'docs/research/artifacts/hswm_research_integration_2026-09-20/live-publication.v1.json';
const sha = (x: Uint8Array) => createHash('sha256').update(x).digest('hex');
const io = (f: () => Promise<any>) => Effect.tryPromise({ try: f, catch: (e: unknown) => e });
const main = Effect.gen(function* () {
  if (process.argv.length !== 3) throw new Error('Usage: node publish.mts PRIVATE_SOURCE_CONFIG');
  const bytes = yield* io(() => readFile(path));
  if (sha(bytes) !== expected) throw new Error('Reviewed bundle drift');
  const { bundle } = Either.getOrThrowWith(decodeKgBundleSource({ sourceId: 'research', rawBytes: bytes }, 'v2'), (e: any) => e);
  for (const binding of bundle.artifact_bindings) {
    const b = yield* io(() => readFile(binding.path));
    if (sha(b) !== binding.sha256) throw new Error('Artifact binding drift');
  }
  const configBytes = yield* io(() => readFile(process.argv[2], 'utf8'));
  const config = yield* parseNativeDevelopmentProjectionSourceConfig(configBytes);
  const labels = new Map<string, string>([...bundle.nodes.map((n: any) => [n.uid, n.labels[0]]), ...bundle.anchors.map((n: any) => [n.uid, n.required_labels[0]])] as [string, string][]);
  // The existing publisher validates registry membership and exact anchor labels
  // before any relationship statement. Add only those validated labels to endpoint
  // matches so Neo4j can use UID indexes. Keep global collision/readback queries
  // unchanged; no batching, automatic retry, schema change or extra write is added.
  const endpoint = (id: unknown) => {
    const label = typeof id === 'string' ? labels.get(id) : undefined;
    if (label === undefined || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(label)) throw new Error('Invalid bound endpoint');
    return label;
  };
  let rewrittenQueries = 0;
  const factory = (cfg: any) => {
    const driver = neo4j.driver(cfg.uri, neo4j.auth.basic(cfg.user, cfg.password), { connectionTimeout: 30000, maxTransactionRetryTime: 0 });
    return { close: () => driver.close(), session: (options: any) => {
      const session = driver.session(options);
      return { close: () => session.close(), beginTransaction: (options: any) => {
        const tx = session.beginTransaction(options);
        return { commit: () => tx.commit(), rollback: () => tx.rollback(), run: (statement: string, parameters: any) => {
          let query = statement;
          if (query.includes('(a {uid:$from_uid})')) query = query.replace('(a {uid:$from_uid})', `(a:${endpoint(parameters.from_uid)} {uid:$from_uid})`);
          if (query.includes('(b {uid:$to_uid})')) query = query.replace('(b {uid:$to_uid})', `(b:${endpoint(parameters.to_uid)} {uid:$to_uid})`);
          if (query !== statement) rewrittenQueries++;
          return tx.run(query, parameters);
        } };
      } };
    } };
  };
  const started = new Date().toISOString();
  const counts = yield* makeNativeDevelopmentProjectionPublisher(config, factory, '180 seconds').publish(bundle, expected);
  const adapter = yield* io(() => readFile(new URL(import.meta.url)));
  const publisher = yield* io(() => readFile('src/hswm/effect-runtime/src/native-development-projection-publisher.ts'));
  const report = { schema_version: 'hswm-research-live-publication/v1', attempt: 2,
    started_at: started, finished_at: new Date().toISOString(), bundle_uid: bundle.bundle_uid, bundle_sha256: expected,
    source_path: path, publisher_source: 'src/hswm/effect-runtime/src/native-development-projection-publisher.ts', publisher_sha256: sha(publisher),
    query_adapter_source: '_research/research_graph_integration_v1/publish.mts', query_adapter_sha256: sha(adapter),
    query_optimization: 'Registry-validated endpoint labels; EXPLAIN changes relation-type scan to UID unique index seek. Global collision checks unchanged.',
    rewritten_queries: rewrittenQueries, transaction: 'EXISTING_REGISTRY_ANCHOR_COLLISION_CREATE_ONLY_AND_EXACT_READBACK_TRANSACTION',
    existing_anchor_count: bundle.anchors.length, counts, status: 'COMMITTED_WITH_EXACT_NODE_AND_RELATION_READBACK',
    nonclaim: 'RESEARCH_PROJECTION_NOT_CANONICAL_COGNITION_OR_LEARNING' };
  yield* io(() => writeFile(reportPath, JSON.stringify(report, null, 2) + '\n'));
  console.log(JSON.stringify(report));
});
const result = await Effect.runPromiseExit(main);
if (Exit.isFailure(result)) { console.error(Cause.pretty(result.cause)); process.exitCode = 1; }
