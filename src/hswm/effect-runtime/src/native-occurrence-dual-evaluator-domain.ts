import { makeNativeIssuedRecordFactory } from "./native-issued-record-domain.js"
/** Pure, fail-closed port of occurrence_dual_evaluator.py. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { renderNativeTaskJson, taskJsonRecord, type TaskJson } from "./native-task-json-domain.js"

export const NATIVE_DUAL_EVALUATION_SCHEMA = "hswm-occurrence-dual-evaluation/v1" as const
export const NATIVE_DUAL_EVALUATION_CLAIM_CEILING = "DUAL_EVALUATION_INTEGRITY_CONTRACT_ONLY_NOT_OUTCOME_TRUTH_NOT_PERMIT_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING" as const
export type NativeDualTerminal = "BLOCKED_EXTERNAL" | "VOID_EVALUATOR_DISAGREEMENT" | "VOID_EVALUATOR_NONINDEPENDENT" | "SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT"
export class NativeDualEvaluationError extends Data.TaggedError("NativeDualEvaluationError")<{ readonly detail: string }> {}
type ObjectJson = Readonly<Record<string, TaskJson>> & Readonly<{ media_type?: TaskJson; sha256?: TaskJson; byte_length?: TaskJson; role?: TaskJson; issuer?: TaskJson; subject?: TaskJson; account?: TaskJson; admin_domain?: TaskJson; key_ref?: TaskJson; operations?: TaskJson; scheme?: TaskJson; authority?: TaskJson; signed_envelope?: TaskJson; verification_receipt?: TaskJson; signed_payload_sha256?: TaskJson; cryptographically_verified?: TaskJson; occurrence_uid?: TaskJson; evaluator?: TaskJson; implementation?: TaskJson; task?: TaskJson; scorer?: TaskJson; config?: TaskJson; input?: TaskJson; output?: TaskJson; canonical_decision_score_sha256?: TaskJson; blind_to_arm_identity?: TaskJson; signature?: TaskJson; inspect_requirement?: TaskJson }>
type Judgment = NativeJudgmentA | NativeJudgmentB
export interface NativeContentDescriptor { readonly mediaType: string; readonly sha256: string; readonly byteLength: number | bigint }
export interface NativeRoleBinding { readonly role: string; readonly issuer: string; readonly subject: string; readonly account: string; readonly adminDomain: string; readonly keyRef: string; readonly operations: readonly string[] }
export interface NativeSignatureEvidence { readonly scheme: "dsse" | "cms" | "openpgp"; readonly authority: string; readonly signedEnvelope: NativeContentDescriptor; readonly verificationReceipt: NativeContentDescriptor; readonly signedPayloadSha256: string; readonly cryptographicallyVerified: boolean }
export interface NativeJudgmentA { readonly occurrenceUid: string; readonly evaluator: NativeRoleBinding; readonly inspectRequirement: string; readonly implementation: NativeContentDescriptor; readonly task: NativeContentDescriptor; readonly scorer: NativeContentDescriptor; readonly config: NativeContentDescriptor; readonly input: NativeContentDescriptor; readonly output: NativeContentDescriptor; readonly scoreSha256: string; readonly blind: true; readonly signature: NativeSignatureEvidence | null }
export interface NativeJudgmentB extends Omit<NativeJudgmentA, "inspectRequirement"> {}
const fail = <A = never>(detail: string): Either.Either<A, NativeDualEvaluationError> => Either.left(new NativeDualEvaluationError({ detail }))
const identifier = (value: string): boolean => /^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,159}$/.test(value)
const sha256 = (value: string): boolean => /^[0-9a-f]{64}$/.test(value)
const object = (value: TaskJson | undefined): value is ObjectJson => value !== undefined && taskJsonRecord(value)
const digest = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const sameDescriptor = (left: NativeContentDescriptor, right: NativeContentDescriptor): boolean => left.mediaType === right.mediaType && left.sha256 === right.sha256 && left.byteLength === right.byteLength
const nativeInteger = (value: TaskJson | undefined): value is number | bigint => typeof value === "bigint" || typeof value === "number" && Number.isSafeInteger(value)
const descriptor = (value: TaskJson | undefined): Either.Either<NativeContentDescriptor, NativeDualEvaluationError> => {
  if (!object(value) || Object.keys(value).length !== 3 || typeof value.media_type !== "string" || value.media_type.length === 0 || value.media_type.length > 160 || typeof value.sha256 !== "string" || !sha256(value.sha256) || !nativeInteger(value.byte_length) || value.byte_length < 0) return fail("content descriptor")
  return Either.right(Object.freeze({ mediaType: value.media_type, sha256: value.sha256, byteLength: value.byte_length }))
}
const canonicalDescriptor = (value: NativeContentDescriptor): ObjectJson => ({ byte_length: value.byteLength, media_type: value.mediaType, sha256: value.sha256 })
const role = (value: TaskJson | undefined, expected: string): Either.Either<NativeRoleBinding, NativeDualEvaluationError> => {
  if (!object(value) || Object.keys(value).length !== 7 || value.role !== expected || typeof value.issuer !== "string" || !identifier(value.issuer) || typeof value.subject !== "string" || !identifier(value.subject) || typeof value.account !== "string" || !identifier(value.account) || typeof value.admin_domain !== "string" || !identifier(value.admin_domain) || typeof value.key_ref !== "string" || !identifier(value.key_ref) || !Array.isArray(value.operations) || value.operations.length === 0 || value.operations.some(item => typeof item !== "string" || !identifier(item)) || new Set(value.operations).size !== value.operations.length || value.operations.includes("*") || value.operations.includes("canonical_write") || value.operations.includes("permit_issue")) return fail("evaluator role binding")
  const operations = value.operations as readonly string[]
  return Either.right(Object.freeze({ role: expected, issuer: value.issuer, subject: value.subject, account: value.account, adminDomain: value.admin_domain, keyRef: value.key_ref, operations: Object.freeze([...operations]) }))
}
const canonicalRole = (value: NativeRoleBinding): ObjectJson => ({ account: value.account, admin_domain: value.adminDomain, issuer: value.issuer, key_ref: value.keyRef, operations: value.operations, role: value.role, subject: value.subject })
const signature = (value: TaskJson | undefined): Either.Either<NativeSignatureEvidence | null, NativeDualEvaluationError> => {
  if (value === null) return Either.right(null)
  if (!object(value) || Object.keys(value).length !== 6 || (value.scheme !== "dsse" && value.scheme !== "cms" && value.scheme !== "openpgp") || typeof value.authority !== "string" || !identifier(value.authority) || typeof value.signed_payload_sha256 !== "string" || !sha256(value.signed_payload_sha256) || typeof value.cryptographically_verified !== "boolean") return fail("signature evidence")
  const envelope = descriptor(value.signed_envelope); if (Either.isLeft(envelope)) return fail(envelope.left.detail)
  const receipt = descriptor(value.verification_receipt); if (Either.isLeft(receipt)) return fail(receipt.left.detail)
  return Either.right(Object.freeze({ scheme: value.scheme, authority: value.authority, signedEnvelope: envelope.right, verificationReceipt: receipt.right, signedPayloadSha256: value.signed_payload_sha256, cryptographicallyVerified: value.cryptographically_verified }))
}
const canonicalSignature = (value: NativeSignatureEvidence | null): TaskJson => value === null ? null : ({ authority: value.authority, cryptographically_verified: value.cryptographicallyVerified, scheme: value.scheme, signed_envelope: canonicalDescriptor(value.signedEnvelope), signed_payload_sha256: value.signedPayloadSha256, verification_receipt: canonicalDescriptor(value.verificationReceipt) })
const canonicalJudgment = (judgment: Judgment, includeSignature: boolean): ObjectJson => ({ blind_to_arm_identity: judgment.blind, canonical_decision_score_sha256: judgment.scoreSha256, config: canonicalDescriptor(judgment.config), evaluator: canonicalRole(judgment.evaluator), implementation: canonicalDescriptor(judgment.implementation), input: canonicalDescriptor(judgment.input), ...("inspectRequirement" in judgment ? { inspect_requirement: judgment.inspectRequirement } : {}), occurrence_uid: judgment.occurrenceUid, output: canonicalDescriptor(judgment.output), scorer: canonicalDescriptor(judgment.scorer), schema: NATIVE_DUAL_EVALUATION_SCHEMA, task: canonicalDescriptor(judgment.task), ...(includeSignature ? { signature: canonicalSignature(judgment.signature) } : {}) })
const parse = (value: TaskJson, kind: "a" | "b"): Either.Either<Judgment, NativeDualEvaluationError> => {
  if (!object(value)) return fail("judgment")
  const keys = ["occurrence_uid", "evaluator", "implementation", "task", "scorer", "config", "input", "output", "canonical_decision_score_sha256", "blind_to_arm_identity", "signature", ...(kind === "a" ? ["inspect_requirement"] : [])]
  if (Object.keys(value).length !== keys.length || !keys.every(key => Object.hasOwn(value, key)) || typeof value.occurrence_uid !== "string" || !identifier(value.occurrence_uid) || typeof value.canonical_decision_score_sha256 !== "string" || !sha256(value.canonical_decision_score_sha256) || value.blind_to_arm_identity !== true || (kind === "a" && value.inspect_requirement !== "inspect-ai==0.3.260")) return fail("judgment")
  const evaluator = role(value.evaluator, kind === "a" ? "evaluator_a" : "evaluator_b"); if (Either.isLeft(evaluator)) return fail(evaluator.left.detail)
  const implementation = descriptor(value.implementation); if (Either.isLeft(implementation)) return fail(implementation.left.detail)
  const task = descriptor(value.task); if (Either.isLeft(task)) return fail(task.left.detail)
  const scorer = descriptor(value.scorer); if (Either.isLeft(scorer)) return fail(scorer.left.detail)
  const config = descriptor(value.config); if (Either.isLeft(config)) return fail(config.left.detail)
  const input = descriptor(value.input); if (Either.isLeft(input)) return fail(input.left.detail)
  const output = descriptor(value.output); if (Either.isLeft(output)) return fail(output.left.detail)
  const signed = signature(value.signature); if (Either.isLeft(signed)) return fail(signed.left.detail)
  const base = { occurrenceUid: value.occurrence_uid, evaluator: evaluator.right, implementation: implementation.right, task: task.right, scorer: scorer.right, config: config.right, input: input.right, output: output.right, scoreSha256: value.canonical_decision_score_sha256, blind: true as const, signature: signed.right }
  const judgment: Judgment = kind === "a" ? Object.freeze({ ...base, inspectRequirement: "inspect-ai==0.3.260" }) : Object.freeze(base)
  if (judgment.signature !== null && judgment.signature.signedPayloadSha256 !== digest(canonicalJudgment(judgment, false))) return fail("signature does not bind unsigned record")
  return Either.right(judgment)
}
const bindingProjection = (judgment: Judgment | null): TaskJson => judgment === null || judgment.signature === null ? null : ({ blind_to_arm_identity: judgment.blind, config: canonicalDescriptor(judgment.config), implementation: canonicalDescriptor(judgment.implementation), input: canonicalDescriptor(judgment.input), occurrence_uid: judgment.occurrenceUid, output: canonicalDescriptor(judgment.output), role: canonicalRole(judgment.evaluator), score_sha256: judgment.scoreSha256, scorer: canonicalDescriptor(judgment.scorer), signature_audit: canonicalDescriptor(judgment.signature.verificationReceipt), signature_receipt: canonicalDescriptor(judgment.signature.signedEnvelope), task: canonicalDescriptor(judgment.task) })
/** Identity branding is deliberately kept in this closure: symbols can be copied. */
const dualRecords = makeNativeIssuedRecordFactory<NativeDualAssessment>()
export interface NativeDualAssessment { readonly terminal: NativeDualTerminal; readonly claimCeiling: typeof NATIVE_DUAL_EVALUATION_CLAIM_CEILING; readonly reason: string; readonly evidenceSha256: string; readonly bindingSha256: string }
const assessment = (terminal: NativeDualTerminal, reason: string, evidenceSha256: string, bindingSha256: string): NativeDualAssessment => {
  const value: NativeDualAssessment = Object.freeze({ terminal, claimCeiling: NATIVE_DUAL_EVALUATION_CLAIM_CEILING, reason, evidenceSha256, bindingSha256 })
  return dualRecords.issue(value)
}
export const nativeAssessDualEvaluation = (aValue: TaskJson | null, bValue: TaskJson | null): Either.Either<NativeDualAssessment, NativeDualEvaluationError> => {
  const a = aValue === null ? Either.right(null) : parse(aValue, "a"); if (Either.isLeft(a)) return fail(a.left.detail)
  const b = bValue === null ? Either.right(null) : parse(bValue, "b"); if (Either.isLeft(b)) return fail(b.left.detail)
  const evidenceSha256 = digest({ schema: NATIVE_DUAL_EVALUATION_SCHEMA, judgment_a: a.right === null ? null : canonicalJudgment(a.right, true), judgment_b: b.right === null ? null : canonicalJudgment(b.right, true) })
  const bindingSha256 = digest({ judgment_a: bindingProjection(a.right), judgment_b: bindingProjection(b.right), schema: "hswm-dual-evaluation-binding/v1" })
  if (a.right === null || b.right === null) return Either.right(assessment("BLOCKED_EXTERNAL", "both externally supplied judgments are required", evidenceSha256, bindingSha256))
  if (a.right.occurrenceUid !== b.right.occurrenceUid) return Either.right(assessment("VOID_EVALUATOR_DISAGREEMENT", "judgments bind different occurrence UIDs", evidenceSha256, bindingSha256))
  if ([a.right.evaluator.subject === b.right.evaluator.subject, a.right.evaluator.account === b.right.evaluator.account, a.right.evaluator.adminDomain === b.right.evaluator.adminDomain, a.right.evaluator.keyRef === b.right.evaluator.keyRef, a.right.evaluator.issuer === b.right.evaluator.issuer].some(Boolean)) return Either.right(assessment("VOID_EVALUATOR_NONINDEPENDENT", "evaluator roles do not have independent identity and control bindings", evidenceSha256, bindingSha256))
  if (a.right.implementation.sha256 === b.right.implementation.sha256) return Either.right(assessment("VOID_EVALUATOR_NONINDEPENDENT", "evaluator implementations are not distinct", evidenceSha256, bindingSha256))
  if (!sameDescriptor(a.right.input, b.right.input)) return Either.right(assessment("VOID_EVALUATOR_DISAGREEMENT", "judgments do not bind the same exact input descriptor", evidenceSha256, bindingSha256))
  if (a.right.scoreSha256 !== b.right.scoreSha256) return Either.right(assessment("VOID_EVALUATOR_DISAGREEMENT", "canonical decision/score digests disagree", evidenceSha256, bindingSha256))
  if (a.right.signature === null || b.right.signature === null || !a.right.signature.cryptographicallyVerified || !b.right.signature.cryptographicallyVerified) return Either.right(assessment("BLOCKED_EXTERNAL", "signature evidence is missing or not externally cryptographically verified", evidenceSha256, bindingSha256))
  return Either.right(assessment("SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT", "exact blinded agreement is only a candidate pending independent signature audit", evidenceSha256, bindingSha256))
}
export const nativeDualAssessmentCanonical = (value: NativeDualAssessment): Either.Either<ObjectJson, NativeDualEvaluationError> => dualRecords.isIssued(value) ? Either.right({ claim_ceiling: value.claimCeiling, evidence_sha256: value.evidenceSha256, binding_sha256: value.bindingSha256, reason: value.reason, schema: NATIVE_DUAL_EVALUATION_SCHEMA, terminal: value.terminal }) : fail("assessment was not issued by the evaluator factory")
