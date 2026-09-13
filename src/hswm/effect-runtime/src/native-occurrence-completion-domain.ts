/** Original completion predicates. Local issued records establish construction, never outcome truth. */
import { createHash } from "node:crypto"
import { Data, Effect, Either } from "effect"
import { makeNativeIssuedRecordFactory } from "./native-issued-record-domain.js"
import { nativePythonInstantMicroseconds } from "./native-python-instant-domain.js"
import { nativeAssessDualEvaluation, nativeDualAssessmentCanonical, type NativeDualAssessment } from "./native-occurrence-dual-evaluator-domain.js"
import { nativeOccurrenceAssessmentCanonical, type NativeOccurrenceAssessment } from "./native-occurrence-integrity-domain.js"
import { nativeOccurrenceWorkflowCanonical, type NativeOccurrenceWorkflowState } from "./native-occurrence-workflow-domain.js"
import { nativeQualifiedExternalAuditCanonical, type NativeQualifiedExternalAudit } from "./native-occurrence-audit-runtime.js"
import { renderNativeTaskJson, type TaskJson } from "./native-task-json-domain.js"

export const HSWM_NATIVE_OCCURRENCE_COMPLETION_V1 = "hswm-occurrence-completion/v1" as const
export const HSWM_NATIVE_OCCURRENCE_COMPLETION_CLAIM_CEILING = "COMPLETION_HANDSHAKE_AND_QUALIFIED_EXTERNAL_AUDIT_BINDING_ONLY_NOT_OUTCOME_TRUTH_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING" as const
export const NATIVE_PENDING_EXTERNAL_AUDIT_REASON = "candidate evidence is pending external audit verification and Temporal finalization"
const VERIFIED_REASON = "qualified Cosign verification binds the signed external audit manifest to the candidate and exact Temporal finalization"
const VERIFICATION_FAILED_REASON = "qualified external audit verification failed or did not bind the candidate and terminal workflow"
type ObjectJson = { readonly [key: string]: TaskJson }
export class NativeCompletionError extends Data.TaggedError("NativeCompletionError")<{ readonly code: "INPUT_INVALID" | "AUDIT_REQUIRED"; readonly detail: string }> {}
const fail = <A = never>(detail: string): Either.Either<A, NativeCompletionError> => Either.left(new NativeCompletionError({ code: "INPUT_INVALID", detail }))
export interface NativeIssuedCompletionReceipt {
  readonly occurrenceUid: string
  readonly terminalStatus: "VOID" | "BLOCKED" | "PENDING_EXTERNAL_AUDIT" | "SEALED"
  readonly reason: string
  readonly startedAt: string
  readonly terminalAt: string
  readonly integrityAssessmentSha256: string
  readonly integrityChainSha256: string
  readonly workflowSha256: string
  readonly workflowEvidenceSha256s: readonly string[]
  readonly dualEvaluationAssessmentSha256: string | null
  readonly dualEvaluationEvidenceSha256: string | null
  readonly externalAuditVerificationSha256: string | null
  readonly claimCeiling: typeof HSWM_NATIVE_OCCURRENCE_COMPLETION_CLAIM_CEILING
  readonly receiptSha256: string
}
const receipts = makeNativeIssuedRecordFactory<NativeIssuedCompletionReceipt>()
export const nativeCompletionReceiptCanonical = (value: NativeIssuedCompletionReceipt): Either.Either<ObjectJson, NativeCompletionError> => receipts.isIssued(value) ? Either.right({
  claim_ceiling: value.claimCeiling, dual_evaluation_assessment_sha256: value.dualEvaluationAssessmentSha256,
  dual_evaluation_evidence_sha256: value.dualEvaluationEvidenceSha256, external_audit_verification_sha256: value.externalAuditVerificationSha256,
  integrity_assessment_sha256: value.integrityAssessmentSha256, integrity_chain_sha256: value.integrityChainSha256,
  occurrence_uid: value.occurrenceUid, reason: value.reason, schema_version: HSWM_NATIVE_OCCURRENCE_COMPLETION_V1,
  started_at: value.startedAt, terminal_at: value.terminalAt, terminal_status: value.terminalStatus,
  workflow_evidence_sha256s: value.workflowEvidenceSha256s, workflow_sha256: value.workflowSha256, receipt_sha256: value.receiptSha256
}) : fail("receipt was not issued by complete occurrence")
export const nativeCompletionReceiptPayload = (value: NativeIssuedCompletionReceipt): Either.Either<ObjectJson, NativeCompletionError> => nativeCompletionReceiptCanonical(value).pipe(Either.map(({ receipt_sha256: _self, ...payload }) => Object.freeze(payload)))
export interface NativeOccurrenceCompletionInput {
  readonly assessment: NativeOccurrenceAssessment
  readonly workflow: NativeOccurrenceWorkflowState
  readonly dualEvaluation: NativeDualAssessment | null
  readonly judgmentA: TaskJson | null
  readonly judgmentB: TaskJson | null
  readonly startedAt: string
  readonly terminalAt: string
  readonly candidateReceipt?: NativeIssuedCompletionReceipt | null
  readonly externalAuditMaterial?: unknown
  readonly previousReceipt?: NativeIssuedCompletionReceipt | null
}
const digest = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const same = (left: readonly string[], right: readonly string[]): boolean => left.length === right.length && left.every((value, index) => value === right[index])
const instant = (value: unknown): bigint | null => typeof value === "string" && value.trim() === value && value.includes("T") ? nativePythonInstantMicroseconds(value) : null
const judgmentUid = (value: TaskJson | null): TaskJson | undefined => value !== null && typeof value === "object" && !Array.isArray(value) ? (value as ObjectJson)["occurrence_uid"] : undefined
interface PreparedCompletion {
  readonly input: NativeOccurrenceCompletionInput
  readonly assessmentDigest: string
  readonly dualDigest: string | null
  readonly workflowDigest: string
}
const issueReceipt = (p: PreparedCompletion, terminalStatus: NativeIssuedCompletionReceipt["terminalStatus"], reason: string, audit: NativeQualifiedExternalAudit | null = null): NativeIssuedCompletionReceipt => {
  const i = p.input
  const payload: ObjectJson = {
    claim_ceiling: HSWM_NATIVE_OCCURRENCE_COMPLETION_CLAIM_CEILING,
    dual_evaluation_assessment_sha256: p.dualDigest, dual_evaluation_evidence_sha256: i.dualEvaluation?.evidenceSha256 ?? null,
    external_audit_verification_sha256: audit?.verificationSha256 ?? null,
    integrity_assessment_sha256: p.assessmentDigest, integrity_chain_sha256: i.assessment.chainDigest,
    occurrence_uid: i.workflow.occurrenceUid, reason, schema_version: HSWM_NATIVE_OCCURRENCE_COMPLETION_V1,
    started_at: i.startedAt, terminal_at: i.terminalAt, terminal_status: terminalStatus,
    workflow_evidence_sha256s: i.workflow.evidenceSha256s, workflow_sha256: p.workflowDigest
  }
  return receipts.issue({ occurrenceUid: i.workflow.occurrenceUid, terminalStatus, reason, startedAt: i.startedAt, terminalAt: i.terminalAt,
    integrityAssessmentSha256: p.assessmentDigest, integrityChainSha256: i.assessment.chainDigest, workflowSha256: p.workflowDigest,
    workflowEvidenceSha256s: Object.freeze([...i.workflow.evidenceSha256s]), dualEvaluationAssessmentSha256: p.dualDigest,
    dualEvaluationEvidenceSha256: i.dualEvaluation?.evidenceSha256 ?? null, externalAuditVerificationSha256: audit?.verificationSha256 ?? null,
    claimCeiling: HSWM_NATIVE_OCCURRENCE_COMPLETION_CLAIM_CEILING, receiptSha256: digest(payload) })
}
type CompletionStep = Readonly<{ readonly _tag: "Receipt"; readonly receipt: NativeIssuedCompletionReceipt }> | Readonly<{ readonly _tag: "Verify"; readonly prepared: PreparedCompletion; readonly candidate: NativeIssuedCompletionReceipt; readonly dual: NativeDualAssessment }>
const receiptStep = (receipt: NativeIssuedCompletionReceipt): CompletionStep => Object.freeze({ _tag: "Receipt", receipt })
const prepare = (input: NativeOccurrenceCompletionInput): Either.Either<CompletionStep, NativeCompletionError> => {
  const ac = nativeOccurrenceAssessmentCanonical(input.assessment), wc = nativeOccurrenceWorkflowCanonical(input.workflow)
  if (Either.isLeft(ac) || Either.isLeft(wc)) return fail("exact assessment/workflow values are required")
  const start = instant(input.startedAt), end = instant(input.terminalAt)
  if (start === null || end === null) return fail("completion timestamps must include a valid UTC offset")
  if (end < start) return fail("terminal_at precedes started_at")
  const previous = input.previousReceipt
  if (previous != null) {
    if (!receipts.isIssued(previous) || previous.occurrenceUid !== input.workflow.occurrenceUid) return fail("previous terminal receipt mismatch")
    if (previous.terminalStatus !== "SEALED" && previous.terminalStatus !== "VOID") return fail("only final SEALED or VOID receipts are immutable prior receipts")
  }
  const actualDual = nativeAssessDualEvaluation(input.judgmentA, input.judgmentB)
  if (Either.isLeft(actualDual)) return fail(actualDual.left.detail)
  const actualCanonical = nativeDualAssessmentCanonical(actualDual.right)
  if (Either.isLeft(actualCanonical)) return fail(actualCanonical.left.detail)
  const dc = input.dualEvaluation === null ? Either.right(null) : nativeDualAssessmentCanonical(input.dualEvaluation)
  if (Either.isLeft(dc)) return fail(dc.left.detail)
  const p: PreparedCompletion = Object.freeze({ input, assessmentDigest: digest(ac.right), dualDigest: dc.right === null ? null : digest(dc.right), workflowDigest: digest(wc.right) })
  const output = (status: NativeIssuedCompletionReceipt["terminalStatus"], reason: string) => Either.right(receiptStep(issueReceipt(p, status, reason)))
  const a = input.assessment, w = input.workflow, d = input.dualEvaluation
  if (w.phase === "VOID") return output("VOID", "one-shot workflow became VOID")
  if (a.terminal.startsWith("VOID_")) return output("VOID", `central integrity: ${a.terminal}`)
  if (d !== null && (d.terminal === "VOID_EVALUATOR_DISAGREEMENT" || d.terminal === "VOID_EVALUATOR_NONINDEPENDENT")) return output("VOID", `dual evaluation: ${d.terminal}`)
  if (a.terminal !== "CANDIDATE_REQUIRES_EXTERNAL_AUDIT") return output("BLOCKED", "central integrity lacks an external-audit candidate")
  if (w.phase !== "DUAL_EVALUATED" && w.phase !== "SEALED") return output("BLOCKED", "workflow is not at an exact completion phase")
  if (a.workflowEvidenceSha256s.length === 0) return output("BLOCKED", "central integrity lacks a workflow evidence projection")
  if (w.phase === "DUAL_EVALUATED" && !same(w.evidenceSha256s, a.workflowEvidenceSha256s)) return output("BLOCKED", "workflow history does not match the central integrity chain")
  if (w.phase === "SEALED" && !same(w.evidenceSha256s.slice(0, -1), a.workflowEvidenceSha256s)) return output("BLOCKED", "terminal workflow prefix does not match central integrity")
  if (d === null || d.terminal !== "SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT" || p.dualDigest !== digest(actualCanonical.right)) return output("BLOCKED", "A/B agreement candidate is absent, unverified, or not reproducible")
  if (a.dualEvaluationEvidenceSha256 !== d.evidenceSha256) return output("BLOCKED", "central integrity bridge does not bind dual-evaluation evidence")
  if (a.dualEvaluationBindingSha256 !== d.bindingSha256) return output("BLOCKED", "central and dual evaluator normalized bindings do not match")
  if (judgmentUid(input.judgmentA) !== w.occurrenceUid || judgmentUid(input.judgmentB) !== w.occurrenceUid) return output("BLOCKED", "judgments do not bind the workflow occurrence UID")
  if (w.phase === "DUAL_EVALUATED") return input.candidateReceipt != null || input.externalAuditMaterial != null
    ? output("BLOCKED", "finalization input was supplied before candidate issuance")
    : output("PENDING_EXTERNAL_AUDIT", NATIVE_PENDING_EXTERNAL_AUDIT_REASON)
  const candidate = input.candidateReceipt
  if (candidate == null || !receipts.isIssued(candidate)) return output("BLOCKED", "Temporal SEALED lacks the pending audit candidate receipt")
  if (candidate.occurrenceUid !== w.occurrenceUid || candidate.terminalStatus !== "PENDING_EXTERNAL_AUDIT" || candidate.reason !== NATIVE_PENDING_EXTERNAL_AUDIT_REASON
    || candidate.startedAt !== input.startedAt || candidate.integrityAssessmentSha256 !== p.assessmentDigest || candidate.integrityChainSha256 !== a.chainDigest
    || candidate.dualEvaluationAssessmentSha256 !== p.dualDigest || candidate.dualEvaluationEvidenceSha256 !== d.evidenceSha256
    || !same(w.evidenceSha256s, [...candidate.workflowEvidenceSha256s, candidate.receiptSha256])) return output("BLOCKED", "Temporal SEALED does not exactly extend the pending audit candidate")
  const candidateTime = instant(candidate.terminalAt)
  if (candidateTime === null || candidateTime > end) return output("BLOCKED", "Temporal finalization predates the pending audit candidate")
  if (input.externalAuditMaterial == null) return output("BLOCKED", "qualified external audit material is absent")
  return Either.right(Object.freeze({ _tag: "Verify", prepared: p, candidate, dual: d }))
}
const verifyPrevious = (input: NativeOccurrenceCompletionInput, receipt: NativeIssuedCompletionReceipt): Either.Either<NativeIssuedCompletionReceipt, NativeCompletionError> => {
  const previous = input.previousReceipt
  if (previous == null) return Either.right(receipt)
  const a = nativeCompletionReceiptCanonical(previous), b = nativeCompletionReceiptCanonical(receipt)
  return Either.isRight(a) && Either.isRight(b) && renderNativeTaskJson(a.right) === renderNativeTaskJson(b.right) ? Either.right(previous) : fail("previous receipt does not match fresh completion inputs")
}
/** Pure candidate/VOID/BLOCKED paths. External verification is required before a final receipt can be issued. */
export const completeNativeOccurrence = (input: NativeOccurrenceCompletionInput): Either.Either<NativeIssuedCompletionReceipt, NativeCompletionError> => prepare(input).pipe(Either.flatMap(step => step._tag === "Receipt" ? verifyPrevious(input, step.receipt) : Either.left(new NativeCompletionError({ code: "AUDIT_REQUIRED", detail: "completion requires fresh external audit verification" }))))
export interface NativeCompletionAuditRequest {
  readonly candidate: NativeIssuedCompletionReceipt
  readonly assessment: NativeOccurrenceAssessment
  readonly dual: NativeDualAssessment
  readonly workflow: NativeOccurrenceWorkflowState
  readonly material: unknown
  readonly startedAt: string
  readonly terminalAt: string
}
export interface NativeCompletionAuditService<Requirements = never> { readonly verify: (input: NativeCompletionAuditRequest) => Effect.Effect<NativeQualifiedExternalAudit, NativeCompletionError, Requirements> }
/** Always invokes the supplied typed I/O boundary afresh; never accepts a serialized verification record. */
export const completeNativeOccurrenceWithAudit = <Requirements>(input: NativeOccurrenceCompletionInput, service: NativeCompletionAuditService<Requirements>): Effect.Effect<NativeIssuedCompletionReceipt, NativeCompletionError, Requirements> => Effect.gen(function*() {
  const step = yield* prepare(input)
  if (step._tag === "Receipt") return yield* verifyPrevious(input, step.receipt)
  const audit = yield* service.verify({ candidate: step.candidate, assessment: input.assessment, dual: step.dual, workflow: input.workflow, material: input.externalAuditMaterial, startedAt: input.startedAt, terminalAt: input.terminalAt }).pipe(Effect.either)
  if (Either.isLeft(audit)) return yield* verifyPrevious(input, issueReceipt(step.prepared, "BLOCKED", VERIFICATION_FAILED_REASON))
  const canonical = nativeQualifiedExternalAuditCanonical(audit.right)
  const expected: Readonly<Record<string, unknown>> = {
    candidate_receipt_sha256: step.candidate.receiptSha256, assessment_sha256: step.prepared.assessmentDigest,
    assessment_chain_sha256: input.assessment.chainDigest, dual_assessment_sha256: step.prepared.dualDigest,
    dual_evidence_sha256: step.dual.evidenceSha256, candidate_workflow_sha256: step.candidate.workflowSha256,
    candidate_workflow_evidence_sha256s: step.candidate.workflowEvidenceSha256s, terminal_workflow_sha256: step.prepared.workflowDigest,
    terminal_workflow_evidence_sha256s: input.workflow.evidenceSha256s, completion_started_at: input.startedAt, completion_terminal_at: input.terminalAt
  }
  const valid = Either.isRight(canonical) && Object.entries(expected).every(([key, value]) => JSON.stringify(canonical.right[key]) === JSON.stringify(value))
  return yield* verifyPrevious(input, valid ? issueReceipt(step.prepared, "SEALED", VERIFIED_REASON, audit.right) : issueReceipt(step.prepared, "BLOCKED", VERIFICATION_FAILED_REASON))
})
export const replayNativeOccurrenceCompletion = <Requirements>(input: NativeOccurrenceCompletionInput, service: NativeCompletionAuditService<Requirements>): Effect.Effect<NativeIssuedCompletionReceipt, NativeCompletionError, Requirements> => completeNativeOccurrenceWithAudit({ ...input, previousReceipt: null }, service)
