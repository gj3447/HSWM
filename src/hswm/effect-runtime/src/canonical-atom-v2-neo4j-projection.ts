/**
 * Bounded Neo4j read-model publisher for Hypergraph Projection Contract v1.
 * This module never writes canonical atom state: it can only materialize an
 * already verified projection into its own projectionId namespace.
 */
import { Data, Effect, Either } from "effect"
import type { Driver, ManagedTransaction, Node, Relationship } from "neo4j-driver"

import {
  projectionGraphSha256,
  verifyHypergraphProjection,
  type HypergraphProjection,
  type ProjectionNode,
  type ProjectionRelationship
} from "./canonical-atom-v2-hypergraph-projection.js"

export const HSWM_NEO4J_HYPERGRAPH_PROJECTION_V1_CONTRACT_VERSION =
  "hswm-neo4j-hypergraph-projection/v1" as const

/**
 * Neo4j Community has no scoped uniqueness primitive that this bounded
 * publisher can install without mutating the whole database.  A caller must
 * serialize apply/rebuild operations for one projectionId.  Exact readback
 * detects a bad result; it is not a distributed single-writer guarantee.
 */
export const HSWM_NEO4J_HYPERGRAPH_PROJECTION_CONCURRENCY =
  "CALLER_SERIALIZED_SINGLE_WRITER_PER_PROJECTION_ID_NO_DISTRIBUTED_EXCLUSIVITY_CLAIM" as const

const labels = ["Atom", "Hyperedge", "Participation", "ProjectionRun"] as const
const relationshipTypes = ["HAS_PARTICIPATION", "TARGET", "DERIVED_FROM", "PROJECTED"] as const
type ProjectionLabel = typeof labels[number] | "AtomHyperedge"
type ProjectionRelationshipType = typeof relationshipTypes[number]
type Primitive = string | number | boolean
type Properties = Readonly<Record<string, Primitive>>

export class Neo4jHypergraphProjectionError extends Data.TaggedError(
  "Neo4jHypergraphProjectionError"
)<{
  readonly code:
    | "PROJECTION_INVALID"
    | "DATABASE_FAILURE"
    | "SCOPE_CONFLICT"
    | "CROSS_SCOPE_ATTACHMENT"
    | "READBACK_MISMATCH"
    | "REBUILD_REFUSED"
  readonly detail: string
}> {}

export interface Neo4jHypergraphProjectionOptions {
  /** Always select the target database; no implicit home-database sessions. */
  readonly database: string
  /** Writes are disabled unless this is exactly true. */
  readonly apply?: boolean
}

export interface Neo4jHypergraphProjectionReadback {
  readonly projectionId: string
  readonly nodes: ReadonlyArray<ProjectionNode>
  readonly relationships: ReadonlyArray<ProjectionRelationship>
  readonly graphSha256: string
}

export interface Neo4jHypergraphProjectionPublishResult {
  readonly applied: boolean
  readonly idempotent: boolean
  readonly readback: Neo4jHypergraphProjectionReadback
}

const error = (
  code: Neo4jHypergraphProjectionError["code"],
  detail: string
): Neo4jHypergraphProjectionError => new Neo4jHypergraphProjectionError({ code, detail })

const isRecord = (input: unknown): input is Record<string, unknown> =>
  typeof input === "object" && input !== null && !Array.isArray(input)

// Driver errors can contain a URI, query text, or server configuration.  This
// boundary reports only a stable category to its caller.
const safeError = (_cause: unknown): string => "bounded Neo4j operation failed"

const expectedNodes = (projection: HypergraphProjection): ReadonlyArray<ProjectionNode> =>
  projection.nodes.map((node) => ({
    id: node.id,
    labels: [...node.labels].sort(),
    properties: Object.freeze({ ...node.properties })
  }))

const expectedRelationships = (projection: HypergraphProjection): ReadonlyArray<ProjectionRelationship> =>
  projection.relationships.map((relationship) => ({
    id: relationship.id,
    from: relationship.from,
    to: relationship.to,
    type: relationship.type,
    properties: Object.freeze({ ...relationship.properties })
  }))

const stable = (input: unknown): string => JSON.stringify(input, (_key, value) =>
  isRecord(value) ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))) : value)

const normaliseNodes = (nodes: ReadonlyArray<ProjectionNode>): ReadonlyArray<ProjectionNode> =>
  [...nodes].map((node) => ({ ...node, labels: [...node.labels].sort(), properties: { ...node.properties } }))
    .sort((a, b) => a.id.localeCompare(b.id))

const normaliseRelationships = (relationships: ReadonlyArray<ProjectionRelationship>): ReadonlyArray<ProjectionRelationship> =>
  [...relationships].map((relationship) => ({ ...relationship, properties: { ...relationship.properties } }))
    .sort((a, b) => a.id.localeCompare(b.id))

const equalGraph = (left: Neo4jHypergraphProjectionReadback, right: Neo4jHypergraphProjectionReadback): boolean =>
  stable(normaliseNodes(left.nodes)) === stable(normaliseNodes(right.nodes)) &&
  stable(normaliseRelationships(left.relationships)) === stable(normaliseRelationships(right.relationships))

const projectionLabel = (node: ProjectionNode): ProjectionLabel | undefined => {
  const nonBase = node.labels.filter((label) => label !== "HSWMProjectionV1")
  if (nonBase.length === 2 && nonBase.includes("Atom") && nonBase.includes("Hyperedge")) return "AtomHyperedge"
  return nonBase.length === 1 && labels.includes(nonBase[0] as typeof labels[number])
    ? nonBase[0] as ProjectionLabel
    : undefined
}

const nodeQueryByLabel: Readonly<Record<ProjectionLabel, string>> = {
  Atom: "MERGE (n:HSWMProjectionV1:Atom {id: $id, projectionId: $projectionId}) SET n += $properties",
  AtomHyperedge: "MERGE (n:HSWMProjectionV1:Atom:Hyperedge {id: $id, projectionId: $projectionId}) SET n += $properties",
  Hyperedge: "MERGE (n:HSWMProjectionV1:Hyperedge {id: $id, projectionId: $projectionId}) SET n += $properties",
  Participation: "MERGE (n:HSWMProjectionV1:Participation {id: $id, projectionId: $projectionId}) SET n += $properties",
  ProjectionRun: "MERGE (n:HSWMProjectionV1:ProjectionRun {id: $id, projectionId: $projectionId}) SET n += $properties"
}

const relationshipQueryByType: Readonly<Record<ProjectionRelationshipType, string>> = {
  HAS_PARTICIPATION: "MATCH (from:HSWMProjectionV1 {id: $from, projectionId: $projectionId}) MATCH (to:HSWMProjectionV1 {id: $to, projectionId: $projectionId}) MERGE (from)-[r:HAS_PARTICIPATION {id: $id, projectionId: $projectionId}]->(to) SET r += $properties",
  TARGET: "MATCH (from:HSWMProjectionV1 {id: $from, projectionId: $projectionId}) MATCH (to:HSWMProjectionV1 {id: $to, projectionId: $projectionId}) MERGE (from)-[r:TARGET {id: $id, projectionId: $projectionId}]->(to) SET r += $properties",
  DERIVED_FROM: "MATCH (from:HSWMProjectionV1 {id: $from, projectionId: $projectionId}) MATCH (to:HSWMProjectionV1 {id: $to, projectionId: $projectionId}) MERGE (from)-[r:DERIVED_FROM {id: $id, projectionId: $projectionId}]->(to) SET r += $properties",
  PROJECTED: "MATCH (from:HSWMProjectionV1 {id: $from, projectionId: $projectionId}) MATCH (to:HSWMProjectionV1 {id: $to, projectionId: $projectionId}) MERGE (from)-[r:PROJECTED {id: $id, projectionId: $projectionId}]->(to) SET r += $properties"
}

const asPrimitive = (value: unknown): Primitive | undefined => {
  if (typeof value === "string" || typeof value === "boolean") return value
  if (typeof value === "number") return Number.isFinite(value) && (Number.isSafeInteger(value) || !Number.isInteger(value)) ? value : undefined
  // neo4j-driver represents Cypher INTEGER as an Integer by default.
  if (isRecord(value) && typeof value["toNumber"] === "function" && typeof value["inSafeRange"] === "function" && value["inSafeRange"]() === true) {
    const number = value["toNumber"]()
    return typeof number === "number" && Number.isSafeInteger(number) ? number : undefined
  }
  return undefined
}

const asProperties = (value: unknown): Properties | undefined => {
  if (!isRecord(value)) return undefined
  const result: Record<string, Primitive> = Object.create(null) as Record<string, Primitive>
  for (const [key, property] of Object.entries(value)) {
    const primitive = asPrimitive(property)
    if (primitive === undefined) return undefined
    result[key] = primitive
  }
  return result
}

const validated = (projection: HypergraphProjection): Either.Either<HypergraphProjection, Neo4jHypergraphProjectionError> => {
  const checked = verifyHypergraphProjection(projection)
  if (Either.isLeft(checked)) return Either.left(error("PROJECTION_INVALID", checked.left.detail))
  return Either.right(checked.right)
}

const expectedReadback = (projection: HypergraphProjection): Neo4jHypergraphProjectionReadback => ({
  projectionId: projection.manifest.projectionId,
  nodes: expectedNodes(projection),
  relationships: expectedRelationships(projection),
  graphSha256: projectionGraphSha256({ nodes: projection.nodes, relationships: projection.relationships })
})

const readbackIn = async (tx: ManagedTransaction, projectionId: string): Promise<Neo4jHypergraphProjectionReadback> => {
  const attachment = await tx.run(
    "MATCH (n:HSWMProjectionV1 {projectionId: $projectionId})-[r]-(other) WHERE r.projectionId IS NULL OR r.projectionId <> $projectionId OR NOT other:HSWMProjectionV1 OR other.projectionId IS NULL OR other.projectionId <> $projectionId RETURN count(r) AS count",
    { projectionId }
  )
  const attached = attachment.records[0]?.get("count")
  if (typeof attached === "number" ? attached !== 0 : attached?.toNumber?.() !== 0) {
    throw error("CROSS_SCOPE_ATTACHMENT", `projection namespace ${projectionId} has a foreign relationship attachment`)
  }
  const unrooted = await tx.run(
    "MATCH (left)-[r]-(right) WHERE r.projectionId = $projectionId AND (NOT left:HSWMProjectionV1 OR left.projectionId IS NULL OR left.projectionId <> $projectionId OR NOT right:HSWMProjectionV1 OR right.projectionId IS NULL OR right.projectionId <> $projectionId) RETURN count(r) AS count",
    { projectionId }
  )
  const unrootedCount = unrooted.records[0]?.get("count")
  if (typeof unrootedCount === "number" ? unrootedCount !== 0 : unrootedCount?.toNumber?.() !== 0) {
    throw error("CROSS_SCOPE_ATTACHMENT", `projection namespace ${projectionId} has an unrooted scoped relationship`)
  }
  const nodesResult = await tx.run(
    "MATCH (n:HSWMProjectionV1 {projectionId: $projectionId}) RETURN n ORDER BY n.id",
    { projectionId }
  )
  const nodes: ProjectionNode[] = []
  for (const record of nodesResult.records) {
    const node = record.get("n") as Node
    const properties = asProperties(node.properties)
    if (properties === undefined || typeof properties["id"] !== "string" || typeof properties["projectionId"] !== "string") {
      throw error("READBACK_MISMATCH", "Neo4j returned a node outside the primitive projection property profile")
    }
    nodes.push({ id: properties["id"], labels: [...node.labels].sort(), properties })
  }
  const relationshipsResult = await tx.run(
    "MATCH (from:HSWMProjectionV1 {projectionId: $projectionId})-[r]->(to:HSWMProjectionV1 {projectionId: $projectionId}) WHERE r.projectionId = $projectionId RETURN from.id AS from, to.id AS to, r ORDER BY r.id",
    { projectionId }
  )
  const relationships: ProjectionRelationship[] = []
  for (const record of relationshipsResult.records) {
    const relationship = record.get("r") as Relationship
    const properties = asProperties(relationship.properties)
    const from = record.get("from")
    const to = record.get("to")
    if (properties === undefined || typeof properties["id"] !== "string" || typeof properties["projectionId"] !== "string" || typeof from !== "string" || typeof to !== "string" || !relationshipTypes.includes(relationship.type as ProjectionRelationshipType)) {
      throw error("READBACK_MISMATCH", "Neo4j returned a relationship outside the bounded projection profile")
    }
    relationships.push({ id: properties["id"], from, to, type: relationship.type, properties })
  }
  return {
    projectionId,
    nodes: normaliseNodes(nodes),
    relationships: normaliseRelationships(relationships),
    graphSha256: projectionGraphSha256({ nodes, relationships })
  }
}

const withSession = <A>(driver: Driver, database: string, use: (session: ReturnType<Driver["session"]>) => Promise<A>): Promise<A> => {
  const session = driver.session({ database })
  return use(session).finally(async () => { await session.close() })
}

/** Reads exactly one projection namespace and rejects foreign attachments. */
export const readNeo4jHypergraphProjection = (
  driver: Driver,
  projectionId: string,
  options: Pick<Neo4jHypergraphProjectionOptions, "database">
): Effect.Effect<Neo4jHypergraphProjectionReadback, Neo4jHypergraphProjectionError> =>
  options.database.length === 0
    ? Effect.fail(error("PROJECTION_INVALID", "database must be a nonempty explicit name"))
    : Effect.tryPromise({
    try: () => withSession(driver, options.database, (session) => session.executeRead((tx) => readbackIn(tx, projectionId))),
    catch: (cause) => cause instanceof Neo4jHypergraphProjectionError ? cause : error("DATABASE_FAILURE", safeError(cause))
    })

/**
 * Default is a dry run. With apply:true this creates only missing rows in the
 * named namespace and verifies the full readback before commit. A divergent
 * existing namespace is refused; use the explicit rebuild operation instead.
 */
export const publishNeo4jHypergraphProjection = (
  driver: Driver,
  projection: HypergraphProjection,
  options: Neo4jHypergraphProjectionOptions
): Effect.Effect<Neo4jHypergraphProjectionPublishResult, Neo4jHypergraphProjectionError> =>
  Effect.suspend(() => {
    if (options.database.length === 0) return Effect.fail(error("PROJECTION_INVALID", "database must be a nonempty explicit name"))
    const verified = validated(projection)
    if (Either.isLeft(verified)) return Effect.fail(verified.left)
    const expected = expectedReadback(verified.right)
    const read = () => readNeo4jHypergraphProjection(driver, expected.projectionId, options)
    if (options.apply !== true) return read().pipe(Effect.map((readback): Neo4jHypergraphProjectionPublishResult => ({ applied: false, idempotent: equalGraph(readback, expected), readback })))
    return Effect.tryPromise({
      try: () => withSession(driver, options.database, async (session) => session.executeWrite(async (tx) => {
        const before = await readbackIn(tx, expected.projectionId)
        if (before.nodes.length !== 0 || before.relationships.length !== 0) {
          if (!equalGraph(before, expected)) throw error("SCOPE_CONFLICT", `projection namespace ${expected.projectionId} already contains a different snapshot`)
          return { applied: false, idempotent: true, readback: before }
        }
        for (const node of expected.nodes) {
          const label = projectionLabel(node)
          if (label === undefined) throw error("PROJECTION_INVALID", `node ${node.id} has no fixed projection label`)
          await tx.run(nodeQueryByLabel[label], { id: node.id, projectionId: expected.projectionId, properties: node.properties })
        }
        for (const relationship of expected.relationships) {
          if (!relationshipTypes.includes(relationship.type as ProjectionRelationshipType)) throw error("PROJECTION_INVALID", `relationship ${relationship.id} has a disallowed type`)
          await tx.run(relationshipQueryByType[relationship.type as ProjectionRelationshipType], { ...relationship, projectionId: expected.projectionId, properties: relationship.properties })
        }
        const after = await readbackIn(tx, expected.projectionId)
        if (!equalGraph(after, expected) || after.graphSha256 !== expected.graphSha256) throw error("READBACK_MISMATCH", `exact Neo4j readback differs for ${expected.projectionId}`)
        return { applied: true, idempotent: false, readback: after }
      })),
      catch: (cause) => cause instanceof Neo4jHypergraphProjectionError ? cause : error("DATABASE_FAILURE", safeError(cause))
    })
  })

/** Explicitly replaces one validated namespace after proving it has no foreign attachment. */
export const rebuildNeo4jHypergraphProjection = (
  driver: Driver,
  projection: HypergraphProjection,
  options: Neo4jHypergraphProjectionOptions
): Effect.Effect<Neo4jHypergraphProjectionPublishResult, Neo4jHypergraphProjectionError> =>
  Effect.suspend(() => {
    if (options.database.length === 0) return Effect.fail(error("PROJECTION_INVALID", "database must be a nonempty explicit name"))
    const verified = validated(projection)
    if (Either.isLeft(verified)) return Effect.fail(verified.left)
    if (options.apply !== true) return publishNeo4jHypergraphProjection(driver, verified.right, options)
    const expected = expectedReadback(verified.right)
    return Effect.tryPromise({
      try: () => withSession(driver, options.database, async (session) => session.executeWrite(async (tx) => {
        await readbackIn(tx, expected.projectionId)
        await tx.run("MATCH (:HSWMProjectionV1 {projectionId: $projectionId})-[r {projectionId: $projectionId}]-(:HSWMProjectionV1 {projectionId: $projectionId}) DELETE r", { projectionId: expected.projectionId })
        // Plain DELETE deliberately fails and rolls back if a foreign
        // attachment races the preflight; DETACH DELETE would erase it.
        await tx.run("MATCH (n:HSWMProjectionV1 {projectionId: $projectionId}) DELETE n", { projectionId: expected.projectionId })
        for (const node of expected.nodes) {
          const label = projectionLabel(node)
          if (label === undefined) throw error("PROJECTION_INVALID", `node ${node.id} has no fixed projection label`)
          await tx.run(nodeQueryByLabel[label], { id: node.id, projectionId: expected.projectionId, properties: node.properties })
        }
        for (const relationship of expected.relationships) {
          await tx.run(relationshipQueryByType[relationship.type as ProjectionRelationshipType], { ...relationship, projectionId: expected.projectionId, properties: relationship.properties })
        }
        const after = await readbackIn(tx, expected.projectionId)
        if (!equalGraph(after, expected) || after.graphSha256 !== expected.graphSha256) throw error("READBACK_MISMATCH", `rebuilt Neo4j readback differs for ${expected.projectionId}`)
        return { applied: true, idempotent: false, readback: after }
      })),
      catch: (cause) => cause instanceof Neo4jHypergraphProjectionError ? cause : error("DATABASE_FAILURE", safeError(cause))
    })
  })
