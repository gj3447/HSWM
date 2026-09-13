/**
 * Narrow Neo4j adapter for the three reviewed development projections.
 * It cannot publish arbitrary graph writes: its only input is an already
 * validated KgBundle plus the reviewed raw-byte SHA from the projection domain.
 */
import neo4j from "neo4j-driver"
import { Data, Duration, Effect } from "effect"
import { kgCanonicalJson, type KgBundle } from "./native-kg-bundle-domain.js"
import { NativeDevelopmentProjectionError, type NativeDevelopmentProjectionPublisher } from "./native-development-projection-domain.js"

const registryUid = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
const label = /^[A-Za-z_][A-Za-z0-9_]*$/
const relation = /^[A-Z_][A-Z0-9_]*$/
const strings = (value: unknown): readonly string[] => Array.isArray(value) && value.every(item => typeof item === "string") ? value : []
const safePublicationDetail = (cause: unknown): string => cause instanceof Error && /^(?:KG schema registry not found: sym:KG_INFRA:schema-registry-v1-2026-08-03|unregistered schema tokens|required remote anchors are missing|anchor drift: sym:[A-Za-z0-9:._-]+|refusing a partial pre-existing projection|node collision: sym:[A-Za-z0-9:._-]+|duplicate remote relation|relationship property collision: sym:[A-Za-z0-9:._-]+|refusing a partial pre-existing relation set|remote node readback UID mismatch|node readback mismatch: sym:[A-Za-z0-9:._-]+|remote relation readback mismatch: sym:[A-Za-z0-9:._-]+|remote ownership count mismatch)$/.test(cause.message) ? cause.message : "native development projection publication failed"
export class NativeDevelopmentProjectionPublisherError extends Data.TaggedError("NativeDevelopmentProjectionPublisherError")<{ readonly detail: string }> {}
export interface NativeDevelopmentProjectionSourceConfig { readonly uri: string; readonly user: string; readonly password: string; readonly database: string }
/** The narrow Neo4j surface used by this adapter, including its managed transaction callback. */
export interface NativeDevelopmentProjectionRecord { readonly get: (key: string) => unknown }
export interface NativeDevelopmentProjectionResult { readonly records: readonly NativeDevelopmentProjectionRecord[] }
export interface NativeDevelopmentProjectionTransaction {
  readonly run: (statement: string, parameters: Readonly<Record<string, unknown>>) => Promise<NativeDevelopmentProjectionResult>
  readonly commit: () => Promise<void>
  readonly rollback: () => Promise<void>
}
export interface NativeDevelopmentProjectionSession {
  /** Neo4j transaction timeout in milliseconds; sent to the server with BEGIN. */
  readonly beginTransaction: (config: { readonly timeout: number }) => NativeDevelopmentProjectionTransaction
  readonly close: () => Promise<void>
}
export interface NativeDevelopmentProjectionDriver {
  readonly session: (config: { readonly database: string }) => NativeDevelopmentProjectionSession
  readonly close: () => Promise<void>
}
/** Injection seam for deterministic transaction tests; the default is the pinned driver. */
export type NativeDevelopmentProjectionDriverFactory = (config: NativeDevelopmentProjectionSourceConfig) => NativeDevelopmentProjectionDriver
export const parseNativeDevelopmentProjectionSourceConfig = (text: string): Effect.Effect<NativeDevelopmentProjectionSourceConfig, NativeDevelopmentProjectionPublisherError> => Effect.gen(function* () {
  const values = new Map<string, string>()
  for (const line of text.split(/\r?\n/)) {
    if (line.trimStart().startsWith("#") || !line.includes(":")) continue
    const index = line.indexOf(":")
    const key = line.slice(0, index).trim(), value = line.slice(index + 1).trim().replace(/^['"]|['"]$/g, "")
    if (["uri", "user", "password", "database"].includes(key)) values.set(key, value)
  }
  const uri = values.get("uri"), user = values.get("user"), password = values.get("password"), database = values.get("database")
  if (uri === undefined || user === undefined || password === undefined || database === undefined || !/^(?:neo4j|bolt)(?:\+s|\+ssc)?:\/\//.test(uri) || !user || !password || !/^[A-Za-z0-9_.-]{1,128}$/.test(database)) return yield* Effect.fail(new NativeDevelopmentProjectionPublisherError({ detail: "source config requires uri, user, password and safe database" }))
  return Object.freeze({ uri, user, password, database })
})
const props = (bundle: KgBundle, row: KgBundle["nodes"][number], sha: string): Record<string, unknown> => Object.freeze({ ...row.properties, uid: row.uid, ontology_bundle_uid: bundle.bundle_uid, ontology_projection_sha256: sha })
const relationProps = (bundle: KgBundle, row: KgBundle["relations"][number], sha: string): Record<string, unknown> => Object.freeze({ ontology_bundle_uid: bundle.bundle_uid, ontology_projection_sha256: sha, authority_class: row.authority_class, scope: row.scope, status: row.status })
const error = (detail: string): NativeDevelopmentProjectionPublisherError => new NativeDevelopmentProjectionPublisherError({ detail })
const record = (value: unknown): value is Readonly<Record<string, unknown>> => value !== null && typeof value === "object"
const count = (result: NativeDevelopmentProjectionResult): number => {
  const value = result.records[0]?.get("count")
  if (typeof value === "number") return value
  const toNumber = record(value) ? value["toNumber"] : undefined
  return typeof toNumber === "function" ? toNumber.call(value) : Number.NaN
}
const attempt = <Value>(operation: () => Promise<Value>): Effect.Effect<Value, NativeDevelopmentProjectionPublisherError> => Effect.tryPromise({ try: operation, catch: cause => error(safePublicationDetail(cause)) })
const run = (transaction: NativeDevelopmentProjectionTransaction, statement: string, parameters: Readonly<Record<string, unknown>>): Effect.Effect<NativeDevelopmentProjectionResult, NativeDevelopmentProjectionPublisherError> => attempt(() => transaction.run(statement, parameters))
const finalize = (operation: () => Promise<void>): Effect.Effect<void, never> =>
  attempt(operation).pipe(Effect.timeoutFail({ duration: "5 seconds", onTimeout: () => error("native development projection cleanup timed out") }), Effect.ignore)
const transactionPublication = (transaction: NativeDevelopmentProjectionTransaction, bundle: KgBundle, sha: string): Effect.Effect<Readonly<Record<string, number>>, NativeDevelopmentProjectionPublisherError> => Effect.gen(function* () {
  const registry = yield* run(transaction, "MATCH (r:SchemaRegistry {uid:$uid}) RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations", { uid: registryUid })
  if (registry.records.length !== 1) return yield* Effect.fail(error(`KG schema registry not found: ${registryUid}`))
  const allowedLabels = new Set<string>(strings(registry.records[0]!.get("labels"))), allowedRelations = new Set<string>(strings(registry.records[0]!.get("relations")))
  const labels = new Set(bundle.nodes.flatMap(node => node.labels)), types = new Set(bundle.relations.map(edge => edge.type))
  if ([...labels].some(value => !label.test(value) || !allowedLabels.has(value)) || [...types].some(value => !relation.test(value) || !allowedRelations.has(value))) return yield* Effect.fail(error("unregistered schema tokens"))
  const nodeLookup = "MATCH (n) WHERE n.uid IN $uids RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties"
  const anchorRows = yield* run(transaction, nodeLookup, { uids: bundle.anchors.map(anchor => anchor.uid) })
  if (anchorRows.records.length !== bundle.anchors.length) return yield* Effect.fail(error("required remote anchors are missing"))
  for (const anchor of bundle.anchors) {
    const found = anchorRows.records.find(item => item.get("uid") === anchor.uid), foundProperties = found?.get("properties")
    if (found === undefined || !record(foundProperties) || foundProperties["name"] !== anchor.name || !anchor.required_labels.every(required => strings(found.get("labels")).includes(required))) return yield* Effect.fail(error(`anchor drift: ${anchor.uid}`))
  }
  const existing = yield* run(transaction, nodeLookup, { uids: bundle.nodes.map(node => node.uid) })
  if (existing.records.length !== 0 && existing.records.length !== bundle.nodes.length) return yield* Effect.fail(error("refusing a partial pre-existing projection"))
  for (const node of bundle.nodes) if (existing.records.length !== 0) {
    const found = existing.records.find(item => item.get("uid") === node.uid)
    if (found === undefined || kgCanonicalJson([...strings(found.get("labels"))].sort()) !== kgCanonicalJson([...node.labels].sort()) || kgCanonicalJson(found.get("properties")) !== kgCanonicalJson(props(bundle, node, sha))) return yield* Effect.fail(error(`node collision: ${node.uid}`))
  }
  if (existing.records.length === 0) yield* Effect.forEach(bundle.nodes, node => run(transaction, `CREATE (n:${node.labels.join(":")}) SET n=$properties`, { properties: props(bundle, node, sha) }), { discard: true })
  const present = yield* Effect.forEach(bundle.relations, edge => Effect.gen(function* () {
    const found = yield* run(transaction, `MATCH (a {uid:$from_uid})-[r:${edge.type}]->(b {uid:$to_uid}) RETURN properties(r) AS properties`, { from_uid: edge.from_uid, to_uid: edge.to_uid })
    if (found.records.length > 1) return yield* Effect.fail(error("duplicate remote relation"))
    if (found.records.length === 1 && kgCanonicalJson(found.records[0]!.get("properties")) !== kgCanonicalJson(relationProps(bundle, edge, sha))) return yield* Effect.fail(error(`relationship property collision: ${edge.from_uid}:${edge.type}:${edge.to_uid}`))
    return found.records.length === 1
  }))
  if (present.some(Boolean) && !present.every(Boolean)) return yield* Effect.fail(error("refusing a partial pre-existing relation set"))
  if (!present.some(Boolean)) yield* Effect.forEach(bundle.relations, edge => run(transaction, `MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) CREATE (a)-[r:${edge.type}]->(b) SET r=$properties`, { from_uid: edge.from_uid, to_uid: edge.to_uid, properties: relationProps(bundle, edge, sha) }), { discard: true })
  const readNodes = yield* run(transaction, nodeLookup, { uids: bundle.nodes.map(node => node.uid) })
  if (readNodes.records.length !== bundle.nodes.length) return yield* Effect.fail(error("remote node readback UID mismatch"))
  for (const node of bundle.nodes) {
    const found = readNodes.records.find(item => item.get("uid") === node.uid)
    if (found === undefined || kgCanonicalJson([...strings(found.get("labels"))].sort()) !== kgCanonicalJson([...node.labels].sort()) || kgCanonicalJson(found.get("properties")) !== kgCanonicalJson(props(bundle, node, sha))) return yield* Effect.fail(error(`node readback mismatch: ${node.uid}`))
  }
  yield* Effect.forEach(bundle.relations, edge => Effect.gen(function* () {
    const found = yield* run(transaction, `MATCH (a {uid:$from_uid})-[r:${edge.type}]->(b {uid:$to_uid}) RETURN properties(r) AS properties`, { from_uid: edge.from_uid, to_uid: edge.to_uid })
    if (found.records.length !== 1 || kgCanonicalJson(found.records[0]!.get("properties")) !== kgCanonicalJson(relationProps(bundle, edge, sha))) return yield* Effect.fail(error(`remote relation readback mismatch: ${edge.from_uid}:${edge.type}:${edge.to_uid}`))
  }), { discard: true })
  const nodeCount = yield* run(transaction, "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count", { uid: bundle.bundle_uid })
  const relationCount = yield* run(transaction, "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count", { uid: bundle.bundle_uid })
  if (count(nodeCount) !== bundle.nodes.length || count(relationCount) !== bundle.relations.length) return yield* Effect.fail(error("remote ownership count mismatch"))
  return Object.freeze({ created_nodes: existing.records.length === 0 ? bundle.nodes.length : 0, created_relations: present.some(Boolean) ? 0 : bundle.relations.length, existing_nodes: existing.records.length, existing_relations: present.some(Boolean) ? bundle.relations.length : 0, readback_nodes: count(nodeCount), readback_relations: count(relationCount) })
})
/** Uses a single write transaction and projection-scoped CREATE statements after registry validation. */
export const makeNativeDevelopmentProjectionPublisher = (config: NativeDevelopmentProjectionSourceConfig, factory: NativeDevelopmentProjectionDriverFactory = input => neo4j.driver(input.uri, neo4j.auth.basic(input.user, input.password), { connectionTimeout: 30_000, maxTransactionRetryTime: 30_000 }), timeout: Duration.DurationInput = "30 seconds"): NativeDevelopmentProjectionPublisher => Object.freeze({ publish: (bundle: KgBundle, sha: string) =>
  Effect.acquireUseRelease(
    Effect.try({ try: () => factory(config), catch: cause => error(safePublicationDetail(cause)) }),
    driver => Effect.acquireUseRelease(
      Effect.try({ try: () => driver.session({ database: config.database }), catch: cause => error(safePublicationDetail(cause)) }),
      session => Effect.acquireUseRelease(
        Effect.try({ try: () => session.beginTransaction({ timeout: Duration.toMillis(timeout) }), catch: cause => error(safePublicationDetail(cause)) }),
        transaction => transactionPublication(transaction, bundle, sha).pipe(Effect.tap(() => attempt(() => transaction.commit()))).pipe(Effect.timeoutFail({ duration: timeout, onTimeout: () => error("native development projection publication timed out") })),
        transaction => finalize(() => transaction.rollback())
      ),
      session => finalize(() => session.close())
    ),
    driver => finalize(() => driver.close())
  ).pipe(Effect.mapError(publisherError => new NativeDevelopmentProjectionError({ detail: publisherError.detail })))
})
