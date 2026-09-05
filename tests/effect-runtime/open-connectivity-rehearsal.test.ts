import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import { validateCanonicalAtomV2State } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.js"
import { compileHypergraphProjection, decodeHypergraphProjectionBytes, hypergraphProjectionBytes, verifyHypergraphProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.js"
import { makeHypergraphProjectionRehearsal } from "../../src/hswm/effect-runtime/src/hypergraph-projection-rehearsal.js"
import { makeOpenConnectivityRehearsal } from "../../src/hswm/effect-runtime/src/open-connectivity-rehearsal.js"

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("expected successful open connectivity rehearsal")
  return value.right
}

it("deterministically projects recursive composition, lateral peers, external n-ary roles, and ports", () => {
  const rehearsal = makeOpenConnectivityRehearsal()
  const first = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  const second = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  expect(first).toEqual(second)
  expect(right(verifyHypergraphProjection(first))).toEqual(first)
  expect(right(decodeHypergraphProjectionBytes(right(hypergraphProjectionBytes(first))))).toEqual(first)
  expect(first.manifest.writeBack).toBe("FORBIDDEN")
  expect(first.manifest.claimCeiling).toBe("BOUNDED_METADATA_PARITY_NOT_HSWM_REALIZATION_OR_LEARNING")
  const atoms = first.nodes.filter((node) => node.labels.includes("Atom"))
  expect(atoms.filter((node) => node.properties["kind"] === "kind:composition")).toHaveLength(2)
  expect(atoms.filter((node) => node.properties["kind"] === "kind:lateral-peer-connection")).toHaveLength(1)
  expect(atoms.filter((node) => node.properties["kind"] === "kind:external-nary-binding")).toHaveLength(1)
  const participation = first.nodes.filter((node) => node.labels.includes("Participation"))
  const roles = new Set(participation.map((node) => node.properties["role"]))
  for (const name of ["role:member", "role:composite", "role:left-peer", "role:right-peer", "role:human", "role:tool", "role:sensor", "role:knowledge", "role:host", "role:sender", "role:receiver"]) expect(roles.has(name)).toBe(true)
  expect(atoms.filter((node) => node.properties["kind"] === "kind:observation-packet")).toHaveLength(2)
  expect(atoms.filter((node) => node.properties["kind"] === "kind:context-proposal-packet")).toHaveLength(2)
  expect(participation.every((node) => node.properties["authority"] === "DERIVED_REFERENCE_VIEW")).toBe(true)
  expect(atoms.every((node) => typeof node.properties["ownerUid"] === "string" && node.properties["ownerUid"].startsWith("owner:"))).toBe(true)
})

it("retains the actual nested, peer, and internal/external exchange paths in projected metadata", () => {
  const rehearsal = makeOpenConnectivityRehearsal()
  const projection = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  const atomId = (uid: string) => projection.nodes.find((node) => node.properties["uid"] === uid)!.id
  const targets = (uid: string, role: string) => projection.nodes
    .filter((node) => node.labels.includes("Participation") && node.properties["sourceAtomId"] === atomId(uid) && node.properties["role"] === role)
    .sort((left, right) => Number(left.properties["ordinal"]) - Number(right.properties["ordinal"]))
    .map((node) => node.properties["targetAtomId"])
  expect(targets("atom:composition-local", "role:composite")).toEqual([atomId("atom:cell-collective")])
  expect(targets("atom:composition-nested", "role:member")).toEqual([atomId("atom:cell-collective"), atomId("atom:cell-beta")])
  expect(targets("atom:composition-nested", "role:composite")).toEqual([atomId("atom:cell-macro")])
  expect(targets("atom:lateral-alpha-beta", "role:left-peer")).toEqual([atomId("atom:cell-alpha")])
  expect(targets("atom:lateral-alpha-beta", "role:right-peer")).toEqual([atomId("atom:cell-beta")])
  for (const [packet, sender, receiver] of [
    ["atom:packet-observation", "atom:port-alpha-observation-out", "atom:port-collective-ingress"],
    ["atom:packet-context-proposal", "atom:port-macro-egress", "atom:port-collective-context-in"],
    ["atom:packet-external-observation", "atom:endpoint-sensor", "atom:port-collective-ingress"],
    ["atom:packet-external-context-proposal", "atom:port-macro-egress", "atom:endpoint-tool"]
  ] as const) {
    expect(targets(packet, "role:sender")).toEqual([atomId(sender)])
    expect(targets(packet, "role:receiver")).toEqual([atomId(receiver)])
  }
  for (const [port, host] of [
    ["atom:port-alpha-observation-out", "atom:cell-alpha"],
    ["atom:port-collective-ingress", "atom:cell-collective"],
    ["atom:port-collective-context-in", "atom:cell-collective"],
    ["atom:port-macro-egress", "atom:cell-macro"]
  ] as const) expect(targets(port, "role:host")).toEqual([atomId(host)])
})

it("keeps temporary activation separate from durable disposition and does not project raw packet payload bytes", () => {
  const rehearsal = makeOpenConnectivityRehearsal()
  const projection = right(compileHypergraphProjection(rehearsal.schema, rehearsal.source))
  const sourceAtoms = rehearsal.source.state.atoms
  const observation = sourceAtoms.find((atom) => atom.key.atomUid === "atom:packet-observation")!
  const proposal = sourceAtoms.find((atom) => atom.key.atomUid === "atom:packet-context-proposal")!
  expect(observation.content.sha256).not.toBe(proposal.content.sha256)
  expect(sourceAtoms.find((atom) => atom.key.atomUid === "atom:activation-temporary")!.kind).toBe("kind:temporary-activation")
  expect(sourceAtoms.find((atom) => atom.key.atomUid === "atom:disposition-durable")!.kind).toBe("kind:durable-disposition")
  const serialized = JSON.stringify(projection)
  expect(serialized).not.toContain("synthetic bottom-up observation")
  expect(serialized).not.toContain("synthetic top-down context")
  expect(serialized).not.toContain("synthetic sensor boundary observation")
  expect(serialized).not.toContain("synthetic tool boundary context")
})

it("gives a journal-lineage fork a distinct source-bound projection identity and rejects malformed roles", () => {
  const main = makeOpenConnectivityRehearsal("journal:open-connectivity-main")
  const fork = makeOpenConnectivityRehearsal("journal:open-connectivity-fork")
  const mainProjection = right(compileHypergraphProjection(main.schema, main.source))
  const forkProjection = right(compileHypergraphProjection(fork.schema, fork.source))
  expect(mainProjection.manifest.projectionId).not.toBe(forkProjection.manifest.projectionId)
  const malformed = {
    ...main.source.state,
    atoms: main.source.state.atoms.map((atom) => atom.key.atomUid === "atom:binding-external-nary"
      ? { ...atom, references: atom.references.map((reference, index) => index === 0 ? { ...reference, role: "role:unknown" } : reference) }
      : atom)
  }
  expect(Either.isLeft(validateCanonicalAtomV2State(main.schema, malformed))).toBe(true)
})

it("rejects dangling references, external role target-kind mismatches, and invalid owner declarations", () => {
  const rehearsal = makeOpenConnectivityRehearsal()
  const replace = (atomUid: string, change: (atom: typeof rehearsal.source.state.atoms[number]) => typeof rehearsal.source.state.atoms[number]) => ({
    ...rehearsal.source.state,
    atoms: rehearsal.source.state.atoms.map((atom) => atom.key.atomUid === atomUid ? change(atom) : atom)
  })
  const dangling = replace("atom:port-collective-ingress", (atom) => ({
    ...atom,
    references: atom.references.map((reference) => ({
      ...reference,
      target: { ...reference.target, atomUid: "atom:missing-host" }
    }))
  }))
  const wrongExternalKind = replace("atom:binding-external-nary", (atom) => ({
    ...atom,
    references: atom.references.map((reference) => reference.role === "role:human"
      ? { ...reference, target: rehearsal.source.state.atoms.find((candidate) => candidate.key.atomUid === "atom:endpoint-tool")!.key }
      : reference)
  }))
  const missingOwner = replace("atom:cell-alpha", (atom) => ({ ...atom, responsibilityOwner: "" }))
  const duplicateOwnerRegistry = {
    ...rehearsal.schema,
    owners: [...rehearsal.schema.owners, rehearsal.schema.owners[0]!]
  }
  for (const state of [dangling, wrongExternalKind, missingOwner]) {
    expect(Either.isLeft(validateCanonicalAtomV2State(rehearsal.schema, state))).toBe(true)
  }
  expect(Either.isLeft(validateCanonicalAtomV2State(duplicateOwnerRegistry, rehearsal.source.state))).toBe(true)
})

it("does not change the existing bounded hypergraph rehearsal projection identity", () => {
  const existing = makeHypergraphProjectionRehearsal()
  const projection = right(compileHypergraphProjection(existing.schema, existing.source))
  expect(projection.manifest.projectionId).toBe(
    "hswm-projection-v1:80924c9fdfe89d88cfb8ddce80eea04f62db1e6a7d253346675a72202527d87e"
  )
})
