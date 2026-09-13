/** Source-bound cases from tests/test_occurrence_dual_evaluator.py. */
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { nativeAssessDualEvaluation, nativeDualAssessmentCanonical } from "../src/native-occurrence-dual-evaluator-domain.js"
import { renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js"

const differential = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/occurrence_integrity_v1/differential.original.v1.json", import.meta.url), "utf8")) as { readonly dual: Readonly<Record<string, { readonly terminal: string; readonly reason: string }>> }
const originalDualCase = (name: string): { readonly terminal: string; readonly reason: string } => {
  const value = differential.dual[name]
  if (value === undefined) throw new Error(`missing original dual-evaluator differential case: ${name}`)
  return value
}

const hash = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const descriptor = (seed: string): Readonly<Record<string, TaskJson>> => ({ media_type: "application/json", sha256: seed.repeat(64), byte_length: 1 })
const role = (name: "evaluator_a" | "evaluator_b"): Readonly<Record<string, TaskJson>> => ({ role: name, issuer: `issuer-${name}`, subject: `subject-${name}`, account: `account-${name}`, admin_domain: `admin-${name}`, key_ref: `key-${name}`, operations: ["evaluate"] })
const unsignedA = (): Readonly<Record<string, TaskJson>> => ({ blind_to_arm_identity: true, canonical_decision_score_sha256: "1".repeat(64), config: descriptor("d"), evaluator: role("evaluator_a"), implementation: descriptor("a"), input: descriptor("e"), inspect_requirement: "inspect-ai==0.3.260", occurrence_uid: "g0-occurrence-1", output: descriptor("f"), scorer: descriptor("c"), task: descriptor("b") })
const unsignedB = (): Readonly<Record<string, TaskJson>> => ({ blind_to_arm_identity: true, canonical_decision_score_sha256: "1".repeat(64), config: descriptor("6"), evaluator: role("evaluator_b"), implementation: descriptor("3"), input: descriptor("e"), occurrence_uid: "g0-occurrence-1", output: descriptor("7"), scorer: descriptor("5"), task: descriptor("4") })
const signed = (kind: "a" | "b", verified = true): Readonly<Record<string, TaskJson>> => {
  const unsigned = kind === "a" ? unsignedA() : unsignedB()
  return { ...unsigned, signature: { authority: `verifier-${kind}`, cryptographically_verified: verified, scheme: "dsse", signed_envelope: descriptor(kind === "a" ? "2" : "8"), signed_payload_sha256: hash({ ...unsigned, schema: "hswm-occurrence-dual-evaluation/v1" }), verification_receipt: descriptor(kind === "a" ? "9" : "a") } }
}
const result = (a: TaskJson | null, b: TaskJson | null) => {
  const value = nativeAssessDualEvaluation(a, b)
  expect(Either.isRight(value)).toBe(true)
  if (Either.isLeft(value)) throw new Error(value.left.detail)
  return value.right
}

it("ports exact blinded agreement and the Python canonical assessment shape", () => {
  const assessment = result(signed("a"), signed("b"))
  expect(assessment.terminal).toBe("SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT")
  const canonical = nativeDualAssessmentCanonical(assessment)
  expect(Either.isRight(canonical)).toBe(true)
  if (Either.isRight(canonical)) expect(canonical.right).toMatchObject({ schema: "hswm-occurrence-dual-evaluation/v1", terminal: "SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT", claim_ceiling: "DUAL_EVALUATION_INTEGRITY_CONTRACT_ONLY_NOT_OUTCOME_TRUTH_NOT_PERMIT_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING" })
})

it("blocks missing or unverified external signature evidence", () => {
  const missing = signed("a") as Readonly<Record<string, TaskJson>>
  const unsigned = { ...missing, signature: null }
  expect(result(unsigned, signed("b"))).toMatchObject(originalDualCase("missing_signature"))
  expect(result(signed("a", false), signed("b"))).toMatchObject(originalDualCase("unverified_signature"))
  expect(result(null, signed("b"))).toMatchObject(originalDualCase("missing_judgment"))
})

it("preserves the Python terminal order and exact disagreement reasons", () => {
  const b = signed("b") as Readonly<Record<string, TaskJson>>
  const changedScoreUnsigned = { ...unsignedB(), canonical_decision_score_sha256: "0".repeat(64) }
  const changedScore = { ...changedScoreUnsigned, signature: null }
  expect(result(signed("a"), changedScore)).toMatchObject(originalDualCase("different_score"))
  const inputUnsigned = { ...b, input: descriptor("9"), signature: null }
  expect(result(signed("a"), inputUnsigned)).toMatchObject(originalDualCase("different_input"))
  const uidUnsigned = { ...b, occurrence_uid: "g0-occurrence-2", signature: null }
  expect(result(signed("a"), uidUnsigned)).toMatchObject(originalDualCase("different_uid"))
})

it("rejects nonindependent people and implementations before signatures", () => {
  const b = signed("b") as Readonly<Record<string, TaskJson>>
  const bRole = b["evaluator"] as Readonly<Record<string, TaskJson>>
  const a = signed("a") as Readonly<Record<string, TaskJson>>
  const aRole = a["evaluator"] as Readonly<Record<string, TaskJson>>
  expect(result(a, { ...b, evaluator: { ...bRole, account: aRole["account"]! }, signature: null }).reason).toBe("evaluator roles do not have independent identity and control bindings")
  expect(result(a, { ...b, implementation: descriptor("a"), signature: null })).toMatchObject(originalDualCase("shared_implementation"))
})

it("rejects original construction drifts and refuses a structural forged assessment", () => {
  const a = signed("a") as Readonly<Record<string, TaskJson>>
  expect(Either.isLeft(nativeAssessDualEvaluation({ ...a, inspect_requirement: "inspect-ai==0.3.261", signature: null }, signed("b")))).toBe(true)
  expect(Either.isLeft(nativeAssessDualEvaluation({ ...a, blind_to_arm_identity: false, signature: null }, signed("b")))).toBe(true)
  expect(Either.isLeft(nativeAssessDualEvaluation({ ...a, signature: { ...(a["signature"] as Readonly<Record<string, TaskJson>>), signed_payload_sha256: "0".repeat(64) } }, signed("b")))).toBe(true)
  const forged = { terminal: "BLOCKED_EXTERNAL", claimCeiling: "DUAL_EVALUATION_INTEGRITY_CONTRACT_ONLY_NOT_OUTCOME_TRUTH_NOT_PERMIT_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING", reason: "forged", evidenceSha256: "0".repeat(64), bindingSha256: "0".repeat(64) }
  expect(Either.isLeft(nativeDualAssessmentCanonical(forged as never))).toBe(true)
  const issued = result(signed("a"), signed("b"))
  expect(Either.isLeft(nativeDualAssessmentCanonical({ ...issued }))).toBe(true)
})

it("keeps Python integer descriptors exact and rejects frozen-schema role drift", () => {
  const a = signed("a") as Readonly<Record<string, TaskJson>>
  const b = signed("b") as Readonly<Record<string, TaskJson>>
  const hugeInput = { media_type: "application/json", sha256: "e".repeat(64), byte_length: 9_007_199_254_740_993n }
  expect(result({ ...a, input: hugeInput, signature: null }, { ...b, input: hugeInput, signature: null }).terminal).toBe("BLOCKED_EXTERNAL")
  const bRole = b["evaluator"] as Readonly<Record<string, TaskJson>>
  expect(Either.isLeft(nativeAssessDualEvaluation(a, { ...b, evaluator: { ...bRole, operations: ["evaluate", "evaluate"] }, signature: null }))).toBe(true)
})
