import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { Parser } from "n3"

import { compileHypergraphProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.js"
import { buildHypergraphProjectionPackage } from "../../src/hswm/effect-runtime/src/hypergraph-projection-receipt.js"
import { makeHypergraphProjectionRehearsal } from "../../src/hswm/effect-runtime/src/hypergraph-projection-rehearsal.js"

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("expected bounded package")
  return value.right
}
const projection = () => {
  const rehearsal = makeHypergraphProjectionRehearsal()
  return right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
}
const evidence = (value = projection()) => ({
  bytes: new TextEncoder().encode(JSON.stringify({ conforms: true, datasetSha256: value.manifest.rdfSha256, sourceStateSha256: value.rdf.manifest.source.stateSha256 })),
  mediaType: "application/json"
})
const input = (value = projection()) => ({ runId: "8f706a87-2222-4a66-8999-123456789abc", startedAt: "2026-09-05T00:00:00.000Z", completedAt: "2026-09-05T00:00:01.000Z", producer: "https://example.invalid/hswm", parity: { mode: "LOCAL_COMPILER_ONLY" as const, shaclEvidence: evidence(value) } })

it("packages a real compiler fixture as OpenLineage, RO-Crate, and parseable PROV N-Quads", () => {
  const value = projection(), first = right(buildHypergraphProjectionPackage(value, input(value))), second = right(buildHypergraphProjectionPackage(value, input(value)))
  expect([...first.files.entries()]).toEqual([...second.files.entries()])
  expect(first.receipt["parity"]).toEqual({ mode: "LOCAL_COMPILER_ONLY" })
  expect(new Parser({ format: "N-Quads" }).parse(new TextDecoder().decode(first.files.get("projection-run.prov.nq")!))).toHaveLength(6)
  expect(new TextDecoder().decode(first.files.get("ro-crate-metadata.json")!)).toContain("https://w3id.org/ro/crate/1.3")
  expect(new TextDecoder().decode(first.files.get("openlineage-complete.json")!)).toContain("COMPLETE")
})

it("rejects invalid execution identities, forged source evidence, and changed readback", () => {
  const value = projection()
  const noCredentials = buildHypergraphProjectionPackage(value, { ...input(value), producer: "https://user:pw@example.invalid" })
  const badUuid = buildHypergraphProjectionPackage(value, { ...input(value), runId: "not-a-uuid" })
  const badDate = buildHypergraphProjectionPackage(value, { ...input(value), startedAt: "2026-02-30T00:00:00.000Z" })
  const forgedEvidence = buildHypergraphProjectionPackage(value, { ...input(value), parity: { mode: "LOCAL_COMPILER_ONLY", shaclEvidence: { bytes: new TextEncoder().encode(JSON.stringify({ conforms: true, datasetSha256: value.manifest.rdfSha256, sourceStateSha256: "0".repeat(64) })), mediaType: "application/json" } } })
  const changedReadback = buildHypergraphProjectionPackage(value, { ...input(value), parity: { mode: "CALLER_REPORTED_LIVE_NEO4J_PARITY", shaclEvidence: evidence(value), readbackGraph: { nodes: value.nodes.slice(1), relationships: value.relationships } } })
  const malformedEvidence = buildHypergraphProjectionPackage(value, { ...input(value), parity: { mode: "LOCAL_COMPILER_ONLY", shaclEvidence: undefined as never } } as never)
  for (const result of [noCredentials, badUuid, badDate, forgedEvidence, changedReadback, malformedEvidence]) expect(Either.isLeft(result)).toBe(true)
})
