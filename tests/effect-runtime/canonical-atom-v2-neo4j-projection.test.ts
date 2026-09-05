import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit } from "effect"

import {
  publishNeo4jHypergraphProjection,
  type Neo4jHypergraphProjectionError
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-neo4j-projection.js"
import { compileHypergraphProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.js"
import { makeHypergraphProjectionRehearsal } from "../../src/hswm/effect-runtime/src/hypergraph-projection-rehearsal.js"

type Primitive = string | number | boolean
type Row = { readonly get: (key: string) => unknown }
type StoredNode = { readonly labels: string[]; readonly properties: Record<string, Primitive> }
type StoredRelationship = { readonly type: string; readonly properties: Record<string, Primitive>; readonly from: string; readonly to: string }

const record = (values: Readonly<Record<string, unknown>>): Row => ({ get: (key) => values[key] })
const count = (value: number) => ({ records: [record({ count: value })] })
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("rehearsal projection failed")
  return value.right
}
const projection = () => {
  const rehearsal = makeHypergraphProjectionRehearsal(`journal:neo4j-unit:${crypto.randomUUID()}`)
  return right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
}

/** Small managed-transaction model: callback failure restores its snapshot. */
const mockDriver = (options: { readonly foreignAttachment?: boolean; readonly corruptReadback?: boolean } = {}) => {
  const nodes = new Map<string, StoredNode>()
  const relationships = new Map<string, StoredRelationship>()
  const outside = { labels: ["Unrelated"], properties: { id: "outside", projectionId: "outside" } }
  nodes.set("outside", outside)
  let writes = 0
  let rollbacks = 0
  const snapshot = () => ({
    nodes: new Map([...nodes].map(([id, node]) => [id, { labels: [...node.labels], properties: { ...node.properties } }])),
    relationships: new Map([...relationships].map(([id, relationship]) => [id, { ...relationship, properties: { ...relationship.properties } }]))
  })
  const transaction = {
    run: async (query: string, parameters: Record<string, unknown> = {}) => {
      const projectionId = parameters["projectionId"]
      if (query.includes("RETURN count(r) AS count")) return count(options.foreignAttachment ? 1 : 0)
      if (query.includes("RETURN n ORDER BY n.id")) {
        const values = [...nodes.values()]
          .filter((node) => node.properties["projectionId"] === projectionId && node.labels.includes("HSWMProjectionV1"))
          .map((node) => record({ n: node }))
        return { records: options.corruptReadback && writes > 0 ? values.slice(0, -1) : values }
      }
      if (query.includes("RETURN from.id AS from")) {
        return { records: [...relationships.values()].filter((relationship) => relationship.properties["projectionId"] === projectionId).map((relationship) => record({ from: relationship.from, to: relationship.to, r: relationship })) }
      }
      if (query.includes("DELETE r")) {
        for (const [id, relationship] of relationships) if (relationship.properties["projectionId"] === projectionId) relationships.delete(id)
        writes += 1
        return { records: [] }
      }
      if (query.includes("DELETE n")) {
        for (const [id, node] of nodes) if (node.properties["projectionId"] === projectionId) nodes.delete(id)
        writes += 1
        return { records: [] }
      }
      if (query.startsWith("MERGE (n:")) {
        const properties = parameters["properties"] as Record<string, Primitive>
        const labels = query.includes(":Atom:Hyperedge") ? ["HSWMProjectionV1", "Atom", "Hyperedge"]
          : query.includes(":Participation") ? ["HSWMProjectionV1", "Participation"]
          : query.includes(":ProjectionRun") ? ["HSWMProjectionV1", "ProjectionRun"]
          : ["HSWMProjectionV1", "Atom"]
        nodes.set(parameters["id"] as string, { labels, properties: { ...properties } })
        writes += 1
        return { records: [] }
      }
      if (query.includes("MERGE (from)-[r:")) {
        const properties = parameters["properties"] as Record<string, Primitive>
        const match = /\[r:([A-Z_]+)/.exec(query)
        relationships.set(parameters["id"] as string, { type: match?.[1] ?? "INVALID", properties: { ...properties }, from: parameters["from"] as string, to: parameters["to"] as string })
        writes += 1
        return { records: [] }
      }
      throw new Error("unexpected bounded query")
    }
  }
  const session = {
    executeRead: async <A>(use: (tx: typeof transaction) => Promise<A>) => use(transaction),
    executeWrite: async <A>(use: (tx: typeof transaction) => Promise<A>) => {
      const before = snapshot()
      try { return await use(transaction) } catch (cause) {
        nodes.clear(); for (const [id, node] of before.nodes) nodes.set(id, node)
        relationships.clear(); for (const [id, relationship] of before.relationships) relationships.set(id, relationship)
        rollbacks += 1
        throw cause
      }
    },
    close: async () => undefined
  }
  return {
    driver: { session: () => session } as never,
    state: { nodes, relationships, outside, writes: () => writes, rollbacks: () => rollbacks }
  }
}

const failed = async (effect: Effect.Effect<unknown, Neo4jHypergraphProjectionError>) => {
  const exit = await Effect.runPromiseExit(effect)
  expect(Exit.isFailure(exit)).toBe(true)
  return exit
}

it("dry run reads only and does not mutate an empty projection namespace", async () => {
  const mock = mockDriver()
  const result = await Effect.runPromise(publishNeo4jHypergraphProjection(mock.driver, projection(), { database: "unit" }))
  expect(result.applied).toBe(false)
  expect(mock.state.writes()).toBe(0)
  expect(mock.state.nodes.get("outside")).toEqual(mock.state.outside)
})

it("fails closed and rolls back every materialized row when exact readback is mismatched", async () => {
  const mock = mockDriver({ corruptReadback: true })
  await failed(publishNeo4jHypergraphProjection(mock.driver, projection(), { database: "unit", apply: true }))
  expect(mock.state.rollbacks()).toBe(1)
  expect(mock.state.nodes.size).toBe(1)
  expect(mock.state.relationships.size).toBe(0)
  expect(mock.state.nodes.get("outside")).toEqual(mock.state.outside)
})

it("refuses a foreign attachment before any write", async () => {
  const mock = mockDriver({ foreignAttachment: true })
  await failed(publishNeo4jHypergraphProjection(mock.driver, projection(), { database: "unit", apply: true }))
  expect(mock.state.writes()).toBe(0)
  expect(mock.state.rollbacks()).toBe(1)
  expect(mock.state.nodes.get("outside")).toEqual(mock.state.outside)
})

it("is idempotent for an exact namespace and preserves nodes outside it", async () => {
  const mock = mockDriver()
  const input = projection()
  const first = await Effect.runPromise(publishNeo4jHypergraphProjection(mock.driver, input, { database: "unit", apply: true }))
  const writes = mock.state.writes()
  const second = await Effect.runPromise(publishNeo4jHypergraphProjection(mock.driver, input, { database: "unit", apply: true }))
  expect(first.applied).toBe(true)
  expect(second.idempotent).toBe(true)
  expect(mock.state.writes()).toBe(writes)
  expect(mock.state.nodes.get("outside")).toEqual(mock.state.outside)
})
