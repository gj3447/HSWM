import { createHash } from "node:crypto"
import { describe, expect, it } from "vitest"
import { Either } from "effect"
import { canonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import type { SemanticReadFrame } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { compareSemanticFrameRepresentations, decodeSemanticFrameRepresentationBytes, encodeSemanticFrameRepresentation } from "../../src/hswm/effect-runtime/src/semantic-frame-representation.js"

const hash = (text: string) => createHash("sha256").update(text).digest("hex")
const key = (atomUid: string, revisionId = 0) => ({ schemaVersion: "schema:test", lineageId: "lineage:test", atomUid, revisionId })
const right = <A,E>(value: Either.Either<A,E>): A => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left))
  return value.right
}
const participant = (role: string, id: string, contentUtf8: string) => ({
  referenceType: "hswm:semantic:role", role, key: key(id), owner: "owner:test",
  contentSha256: hash(contentUtf8), contentUtf8
})
const fixture = (): SemanticReadFrame => {
  const bare = {
    event: "event:prediction", stateRevision: 3,
    relation: { key: key("relation", 1), owner: "owner:test", semantic: {
      semanticText: "문맥에 따른 관계\nshared Ω", disposition: "predict", uncertainty: "not calibrated",
      exceptionRefs: ["shared", "exception"], trace: null, outcome: null
    } },
    roles: [participant("subject", "shared", "same content"), participant("context", "context", '{"context":1}'),
      participant("evidence", "evidence", "past observation"), participant("exception", "shared", "same content"),
      participant("exception", "exception", "a separate exception")],
    priorEvidence: null
  }
  return { ...bare, frameSha256: hash(JSON.stringify(bare)) }
}
const mutated = (kind: "direct_json" | "incidence" | "role_table", change: (value: any) => void) => {
  const encoded = right(encodeSemanticFrameRepresentation(fixture(), kind))
  const value = JSON.parse(new TextDecoder().decode(encoded.bytes))
  change(value)
  return decodeSemanticFrameRepresentationBytes(kind, right(canonicalJsonBytes(value)))
}

describe("semantic frame representations", () => {
  it("round-trips actual bytes in three distinct structures, preserving duplicate endpoint roles and exceptions", () => {
    const source = fixture()
    const compared = right(compareSemanticFrameRepresentations(source))
    expect(compared.fullRoundTripFidelity).toBe(true)
    for (const view of compared.representations) {
      expect(right(decodeSemanticFrameRepresentationBytes(view.kind, view.bytes))).toEqual(source)
      expect(view.serializationBytes).toBe(view.bytes.byteLength)
      expect(view.sourceCanonicalSha256).toBe(compared.sourceCanonicalSha256)
      expect(right(encodeSemanticFrameRepresentation(right(decodeSemanticFrameRepresentationBytes(view.kind, view.bytes)), view.kind)).bytes).toEqual(view.bytes)
    }
    const incidence = JSON.parse(new TextDecoder().decode(compared.representations[1]!.bytes))
    expect(incidence.body.participants).toHaveLength(4)
    expect(incidence.body.incidences).toHaveLength(5)
    expect(incidence.body.incidences[0].target).toBe(incidence.body.incidences[3].target)
    const table = JSON.parse(new TextDecoder().decode(compared.representations[2]!.bytes))
    expect(table.body.columns).toContain("ordinal")
    expect(Array.isArray(table.body.rows[0])).toBe(true)
    expect(compared.conclusion).toBe("NO_UNIVERSAL_MINIMUM_WINNER")
  })

  it("preserves prior outcome descriptors, revision evidence and prior-evidence values", () => {
    const source = fixture()
    const descriptor = (type: string) => ({ mediaType: "application/vnd.hswm.llm-semantic-" + type + "-v1+json", sha256: hash(type), byteLength: 10 })
    const evolved: SemanticReadFrame = { ...source, relation: { ...source.relation, semantic: { ...source.relation.semantic,
      trace: descriptor("trace"), outcome: { ...descriptor("outcome"), status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED" },
      revisionEvidence: descriptor("revision")
    } }, priorEvidence: { prediction: "1", uncertainty: "u", observed: "0", source: "fixture", status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED" } }
    for (const view of right(compareSemanticFrameRepresentations(evolved)).representations) {
      expect(right(decodeSemanticFrameRepresentationBytes(view.kind, view.bytes))).toEqual(evolved)
    }
  })

  it("rejects deleted, duplicate, reordered or dangling incidence bindings", () => {
    const mutations = [
      (v: any) => v.body.incidences.pop(),
      (v: any) => v.body.incidences[1].ordinal = 0,
      (v: any) => v.body.incidences.reverse(),
      (v: any) => v.body.participants.pop(),
      (v: any) => v.body.participants.push(v.body.participants[0]),
      (v: any) => v.body.incidences[0].target = "missing"
    ]
    for (const change of mutations) expect(Either.isLeft(mutated("incidence", change))).toBe(true)
  })

  it("rejects wrong table columns, tuple arity, missing rows and changed role order", () => {
    for (const change of [
      (v: any) => v.body.columns.reverse(),
      (v: any) => v.body.rows[0].pop(),
      (v: any) => v.body.rows.pop(),
      (v: any) => v.body.rows.reverse()
    ]) expect(Either.isLeft(mutated("role_table", change))).toBe(true)
  })

  it("rejects malformed direct frames, mismatched content and inconsistent shared endpoint descriptions", () => {
    for (const change of [
      (v: any) => v.body.frame = { roles: [] },
      (v: any) => v.body.frame.roles[0].owner = 4,
      (v: any) => v.body.frame.roles[0].contentUtf8 = "tampered",
      (v: any) => v.body.frame.relation.semantic.exceptionRefs = ["absent"],
      (v: any) => { v.body.frame.roles[3].owner = "another-owner" },
      (v: any) => v.body.frame.relation.semantic.trace = { sha256: "bad" }
    ]) expect(Either.isLeft(mutated("direct_json", change))).toBe(true)
    const conflicting = fixture()
    expect(Either.isLeft(compareSemanticFrameRepresentations({ ...conflicting, roles: conflicting.roles.map((role, i) => i === 3 ? { ...role, owner: "another-owner" } : role) }))).toBe(true)
  })

  it("checks the canonical source commitment and duplicate-free serialized envelope", () => {
    const changed = mutated("direct_json", v => v.body.frame.relation.semantic.semanticText = "changed meaning")
    expect(Either.isLeft(changed)).toBe(true)
    if (Either.isLeft(changed)) expect(changed.left.code).toBe("COMMITMENT_MISMATCH")
    const encoded = right(encodeSemanticFrameRepresentation(fixture(), "direct_json"))
    const duplicate = new TextDecoder().decode(encoded.bytes).replace('"kind":"direct_json"', '"kind":"direct_json","kind":"incidence"')
    expect(Either.isLeft(decodeSemanticFrameRepresentationBytes("direct_json", new TextEncoder().encode(duplicate)))).toBe(true)
    const prettyPrinted = JSON.stringify(JSON.parse(new TextDecoder().decode(encoded.bytes)), null, 2)
    expect(Either.isLeft(decodeSemanticFrameRepresentationBytes("direct_json", new TextEncoder().encode(prettyPrinted)))).toBe(true)
    expect(Either.isLeft(mutated("direct_json", v => v.body.frame.event = "x".repeat(8193)))).toBe(true)
    expect(Either.isLeft(mutated("direct_json", v => v.kind = "unknown"))).toBe(true)
  })
})
