import { createHash } from "node:crypto"
import { Either } from "effect"
import { expect, it } from "vitest"
import fixture from "../../_research/usl_adapter/examples/preview.v2.json" with { type: "json" }
import { captureUslNativeSnapshot } from "../../src/hswm/effect-runtime/src/usl-native-snapshot.js"

const clone = <A>(value: A): A => structuredClone(value)
const sha = (value: unknown): string => `sha256:${createHash("sha256").update(JSON.stringify(value)).digest("hex")}`
const nativeDigest = `sha256:${"a".repeat(64)}`

const result = () => {
  const prepared = {
    plan: clone(fixture.plan), report: clone(fixture.report), policy: clone(fixture.policy),
    allowed_reads: [["usl", "references_resolve"] as const], now: 1_788_868_860, revision: "native-observation-1",
  }
  const source = { adapter: "property-graph/v1", digest: nativeDigest }
  const identities = {
    resources: { "sym:Implementation:adaptive": "implementation", "sym:Concept:hswm": "concept", "sym:Context:development": "context", "sym:Note:unrelated": "unrelated_note", "sym:Catalog:unrelated": "unrelated_catalog" },
    links: { "sym:Relation:documents-development": "development", "sym:Relation:unrelated-release": "unrelated_release" },
  }
  const receipt = {
    sourceDigest: source.digest,
    planDigest: sha(prepared.plan),
    resultDigest: sha(prepared),
    digest: sha({ source, identities, sourceDigest: source.digest, planDigest: sha(prepared.plan), resultDigest: sha(prepared) }),
  }
  return { source, identities, result: prepared, receipt }
}
const expected = () => ({ nativeSourceDigest: nativeDigest, hswmPlanDigest: fixture.policy.plan_digest })
const right = (value: ReturnType<typeof captureUslNativeSnapshot>) => {
  expect(Either.isRight(value), Either.isLeft(value) ? `${value.left.code}: ${value.left.detail}` : "").toBe(true)
  return (value as any).right
}

it("captures an immutable lossless native/USL snapshot without promoting meaning", () => {
  const input = result()
  const snapshot = right(captureUslNativeSnapshot(input, expected()))
  expect(snapshot.schema).toBe("hswm-usl-native-snapshot/v1")
  expect(snapshot.native.sourceDigest).toBe(nativeDigest)
  expect(snapshot.usl.sourceDigest).toBe(fixture.report.sourceDigest)
  expect(snapshot.native.sourceDigest).not.toBe(snapshot.usl.sourceDigest)
  expect(snapshot.usl.semanticTruth).toBe("NOT_EVALUATED")
  expect(snapshot.integrity).toBe("TRUSTED_ADAPTER_OUTPUT_INTEGRITY_NOT_NATIVE_SOURCE_ATTESTATION")
  expect(snapshot.prepared).toEqual(input.result)
  expect(snapshot.relations[0]).toEqual({
    nativeRelationUid: "sym:Relation:documents-development",
    meaning: { name: "documents", definition: fixture.plan.meanings[0] },
    participants: [
      { role: "code", nativeUid: "sym:Implementation:adaptive" },
      { role: "target", nativeUid: "sym:Concept:hswm" },
      { role: "context", nativeUid: "sym:Context:development" },
    ],
  })
  expect(Object.isFrozen(snapshot)).toBe(true)
  expect(Object.isFrozen(snapshot.relations[0]!.participants)).toBe(true)
  input.result.plan.meanings[0]!.description = "mutated after observation"
  input.identities.resources["sym:Implementation:adaptive"] = "context"
  expect(snapshot.relations[0]!.meaning.definition.description).toBe(fixture.plan.meanings[0]!.description)
  expect(snapshot.native.identities.resources["sym:Implementation:adaptive"]).toBe("implementation")
})

it("rejects receipt, expected native source, plan/meaning, and identity tampering", () => {
  const badReceipt = result()
  badReceipt.receipt.resultDigest = `sha256:${"b".repeat(64)}`
  expect(Either.isLeft(captureUslNativeSnapshot(badReceipt, expected()))).toBe(true)

  const badSource = result()
  badSource.source.digest = `sha256:${"c".repeat(64)}`
  expect(Either.isLeft(captureUslNativeSnapshot(badSource, expected()))).toBe(true)

  const badMeaning = result()
  badMeaning.result.plan.meanings[0]!.description = "forged meaning"
  badMeaning.receipt.planDigest = sha(badMeaning.result.plan)
  badMeaning.receipt.resultDigest = sha(badMeaning.result)
  badMeaning.receipt.digest = sha({ source: badMeaning.source, identities: badMeaning.identities, ...badMeaning.receipt })
  expect(Either.isLeft(captureUslNativeSnapshot(badMeaning, expected()))).toBe(true)

  const badIdentity = result()
  badIdentity.identities.resources["sym:Implementation:adaptive"] = "missing"
  badIdentity.receipt.digest = sha({ source: badIdentity.source, identities: badIdentity.identities, ...badIdentity.receipt })
  expect(Either.isLeft(captureUslNativeSnapshot(badIdentity, expected()))).toBe(true)
})

it("keeps null authored-source binding distinct from a non-null native response digest", () => {
  const input = result()
  ;(input.result.report as any).sourceDigest = null
  ;(input.result.policy as any).source_digest = null
  input.receipt.resultDigest = sha(input.result)
  input.receipt.digest = sha({ source: input.source, identities: input.identities, sourceDigest: input.receipt.sourceDigest, planDigest: input.receipt.planDigest, resultDigest: input.receipt.resultDigest })
  const snapshot = right(captureUslNativeSnapshot(input, expected()))
  expect(snapshot.usl.sourceDigest).toBeNull()
  expect(snapshot.native.sourceDigest).toBe(nativeDigest)
})

it.each([42, "not-a-sha256-source-digest"])("rejects a re-signed non-USL source digest (%j)", (forgedSourceDigest) => {
  const input = result()
  ;(input.result.report as any).sourceDigest = forgedSourceDigest
  ;(input.result.policy as any).source_digest = forgedSourceDigest
  input.receipt.resultDigest = sha(input.result)
  input.receipt.digest = sha({ source: input.source, identities: input.identities, sourceDigest: input.receipt.sourceDigest, planDigest: input.receipt.planDigest, resultDigest: input.receipt.resultDigest })
  expect(Either.isLeft(captureUslNativeSnapshot(input, expected()))).toBe(true)
})

it("does not misrepresent a recomputed receipt as authentication of unseen host bytes", () => {
  const input = result()
  const resources = input.identities.resources
  ;[resources["sym:Implementation:adaptive"], resources["sym:Context:development"]] = [resources["sym:Context:development"]!, resources["sym:Implementation:adaptive"]!]
  input.receipt.digest = sha({ source: input.source, identities: input.identities, sourceDigest: input.receipt.sourceDigest, planDigest: input.receipt.planDigest, resultDigest: input.receipt.resultDigest })
  const snapshot = right(captureUslNativeSnapshot(input, expected()))
  expect(snapshot.integrity).toBe("TRUSTED_ADAPTER_OUTPUT_INTEGRITY_NOT_NATIVE_SOURCE_ATTESTATION")
  expect(snapshot.relations[0]!.participants[0]!.nativeUid).toBe("sym:Context:development")
})
