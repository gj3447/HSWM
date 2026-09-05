import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  compileHypergraphProjection,
  verifyHypergraphProjection,
  type HypergraphProjection
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.js"
import { makeHypergraphProjectionRehearsal } from "../../src/hswm/effect-runtime/src/hypergraph-projection-rehearsal.js"

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("expected successful bounded projection")
  return value.right
}

it("deterministically preserves ternary role-bearing repeated-target participation", () => {
  const rehearsal = makeHypergraphProjectionRehearsal()
  const first = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  const second = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  expect(first).toEqual(second)
  expect(first.manifest.writeBack).toBe("FORBIDDEN")
  const participations = first.nodes.filter((node) => node.labels.includes("Participation"))
  expect(participations).toHaveLength(3)
  const trajectoryRoles = participations.filter((node) => node.properties["targetAtomId"] === participations[0]!.properties["targetAtomId"])
  expect(trajectoryRoles.map((node) => node.properties["role"]).sort()).toEqual(["role:compared-trajectory", "role:trajectory"])
  expect(new Set(trajectoryRoles.map((node) => node.properties["ordinal"]))).toEqual(new Set([0, 1]))
  expect(participations.every((node) => node.properties["provenanceScope"] === "INHERITED_SOURCE_ATOM_NOT_INDEPENDENT_INCIDENCE_ATTESTATION")).toBe(true)
})

it("gives a journal-lineage fork a distinct source-bound projection identity", () => {
  const main = makeHypergraphProjectionRehearsal("journal:projection-main")
  const fork = makeHypergraphProjectionRehearsal("journal:projection-fork")
  const mainProjection = right(compileHypergraphProjection(main.schema, main.source))
  const forkProjection = right(compileHypergraphProjection(fork.schema, fork.source))
  expect(mainProjection.manifest.sourceSha256).not.toBe(forkProjection.manifest.sourceSha256)
  expect(mainProjection.manifest.projectionId).not.toBe(forkProjection.manifest.projectionId)
})

it("rejects stale source material and detects graph, manifest, and relationship tampering", () => {
  const rehearsal = makeHypergraphProjectionRehearsal()
  const stale = { ...rehearsal.source, schemaBinding: { ...rehearsal.source.schemaBinding, schemaVersion: "hswm:stale" } }
  expect(Either.isLeft(compileHypergraphProjection(rehearsal.schema, stale))).toBe(true)
  const projection = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  const variants: HypergraphProjection[] = [
    { ...projection, nodes: projection.nodes.map((node, index) => index === 0 ? { ...node, labels: ["tampered"] } : node) },
    { ...projection, nodes: projection.nodes.map((node, index) => index === 0 ? { ...node, properties: { ...node.properties, uid: "tampered" } } : node) },
    { ...projection, relationships: projection.relationships.map((edge, index) => index === 0 ? { ...edge, type: "TAMPERED" } : edge) },
    { ...projection, manifest: { ...projection.manifest, graphSha256: "0".repeat(64) } }
  ]
  for (const variant of variants) expect(Either.isLeft(verifyHypergraphProjection(variant))).toBe(true)
})
