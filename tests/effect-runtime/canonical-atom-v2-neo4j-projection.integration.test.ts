import neo4j from "neo4j-driver"
import { Effect } from "effect"
import { expect, it } from "@effect/vitest"

import {
  publishNeo4jHypergraphProjection,
  readNeo4jHypergraphProjection,
  rebuildNeo4jHypergraphProjection
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-neo4j-projection.js"
import { compileHypergraphProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.js"
import { makeHypergraphProjectionRehearsal } from "../../src/hswm/effect-runtime/src/hypergraph-projection-rehearsal.js"
import { Either } from "effect"

const uri = process.env["HSWM_NEO4J_INTEGRATION_URI"]
const username = process.env["HSWM_NEO4J_INTEGRATION_USERNAME"]
const password = process.env["HSWM_NEO4J_INTEGRATION_PASSWORD"]
const database = process.env["HSWM_NEO4J_INTEGRATION_DATABASE"]
const configured = uri !== undefined && username !== undefined && password !== undefined && database !== undefined

const compiled = () => {
  const rehearsal = makeHypergraphProjectionRehearsal(`journal:neo4j-integration:${crypto.randomUUID()}`)
  const result = compileHypergraphProjection(rehearsal.schema, rehearsal.source)
  if (Either.isLeft(result)) throw new Error("rehearsal projection did not compile")
  return result.right
}

it.skipIf(!configured)("publishes an isolated namespace, checks exact readback, and deterministically rebuilds it", async () => {
  const driver = neo4j.driver(uri!, neo4j.auth.basic(username!, password!))
  try {
    const projection = compiled()
    const dry = await Effect.runPromise(publishNeo4jHypergraphProjection(driver, projection, { database: database! }))
    expect(dry.applied).toBe(false)
    const first = await Effect.runPromise(publishNeo4jHypergraphProjection(driver, projection, { database: database!, apply: true }))
    expect(first.applied).toBe(true)
    expect(first.readback.graphSha256).toBe(projection.manifest.graphSha256)
    const second = await Effect.runPromise(publishNeo4jHypergraphProjection(driver, projection, { database: database!, apply: true }))
    expect(second.idempotent).toBe(true)
    const rebuilt = await Effect.runPromise(rebuildNeo4jHypergraphProjection(driver, projection, { database: database!, apply: true }))
    expect(rebuilt.readback.graphSha256).toBe(projection.manifest.graphSha256)
    const readback = await Effect.runPromise(readNeo4jHypergraphProjection(driver, projection.manifest.projectionId, { database: database! }))
    expect(readback).toEqual(rebuilt.readback)
  } finally {
    await driver.close()
  }
})
