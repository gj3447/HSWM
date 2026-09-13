import { createHash } from "node:crypto"

import { Effect, Either } from "effect"

import { renderNativeTaskJson } from "./native-task-json-domain.js"
import { decodeNativeAuditQualification, NATIVE_OCCURRENCE_QUALIFICATION_PATH, NATIVE_OCCURRENCE_TOOLCHAIN_PATH, verifyQualifiedNativeExternalAudit } from "./native-occurrence-audit-runtime.js"
import { completeNativeOccurrenceWithAudit, NativeCompletionError, replayNativeOccurrenceCompletion, type NativeCompletionAuditRequest, type NativeCompletionAuditService, type NativeIssuedCompletionReceipt, type NativeOccurrenceCompletionInput } from "./native-occurrence-completion-domain.js"
import { nativeDualAssessmentCanonical } from "./native-occurrence-dual-evaluator-domain.js"
import { nativeOccurrenceAssessmentCanonical } from "./native-occurrence-integrity-domain.js"
import { nativeOccurrenceWorkflowCanonical } from "./native-occurrence-workflow-domain.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { NativePinnedVerifier } from "./native-pinned-verifier-runtime.js"

export interface NativeOccurrenceAuditMaterialPaths {
  readonly auditManifest: string
  readonly cosignBundle: string
  readonly temporalTerminalReceipt: string
  readonly temporalHistoryExport: string
}

const hash = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const completionFailure = (detail: string): NativeCompletionError => new NativeCompletionError({ code: "INPUT_INVALID", detail })
const asPaths = (value: unknown): NativeOccurrenceAuditMaterialPaths | null => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null
  const record = new Map(Object.entries(value))
  const auditManifest = record.get("auditManifest"), cosignBundle = record.get("cosignBundle"), temporalTerminalReceipt = record.get("temporalTerminalReceipt"), temporalHistoryExport = record.get("temporalHistoryExport")
  if (typeof auditManifest !== "string" || !auditManifest.startsWith("/") || typeof cosignBundle !== "string" || !cosignBundle.startsWith("/") || typeof temporalTerminalReceipt !== "string" || !temporalTerminalReceipt.startsWith("/") || typeof temporalHistoryExport !== "string" || !temporalHistoryExport.startsWith("/")) return null
  return Object.freeze({ auditManifest, cosignBundle, temporalTerminalReceipt, temporalHistoryExport })
}
const digestTask = (value: Uint8Array): string => hash(value)

const defaultAuditService: NativeCompletionAuditService<PosixFileSystem | BoundedSubprocess | NativePinnedVerifier> = {
  verify: (request: NativeCompletionAuditRequest) => Effect.gen(function* () {
    const paths = asPaths(request.material)
    if (paths === null) return yield* Effect.fail(completionFailure("external audit material must name four absolute files"))
    const fs = yield* PosixFileSystem
    const read = (path: string, maximumBytes: number, operation: string) => fs.readRegularBounded(path, { maximumBytes, minimumBytes: 1, operation }).pipe(Effect.mapError(() => completionFailure(`cannot read ${operation}`)))
    const qualificationBytes = (yield* read(NATIVE_OCCURRENCE_QUALIFICATION_PATH, 64 * 1024, "fixed occurrence audit qualification")).bytes
    const toolchainBytes = (yield* read(NATIVE_OCCURRENCE_TOOLCHAIN_PATH, 64 * 1024, "fixed occurrence audit toolchain")).bytes
    const qualification = decodeNativeAuditQualification(qualificationBytes, toolchainBytes)
    if (Either.isLeft(qualification)) return yield* Effect.fail(completionFailure(qualification.left.detail))
    const manifestBytes = (yield* read(paths.auditManifest, 16 * 1024 * 1024, "external audit manifest")).bytes
    const bundleBytes = (yield* read(paths.cosignBundle, 16 * 1024 * 1024, "external audit bundle")).bytes
    const temporalReceiptBytes = (yield* read(paths.temporalTerminalReceipt, 16 * 1024 * 1024, "Temporal terminal receipt")).bytes
    const temporalHistoryBytes = (yield* read(paths.temporalHistoryExport, 16 * 1024 * 1024, "Temporal history export")).bytes
    const rootBytes = (yield* read(qualification.right.trustedRootPath, 16 * 1024 * 1024, "qualified trusted root")).bytes
    const licenseBytes = (yield* read(qualification.right.cosignLicensePath, 16 * 1024 * 1024, "qualified Cosign license")).bytes
    const assessment = nativeOccurrenceAssessmentCanonical(request.assessment)
    const dual = nativeDualAssessmentCanonical(request.dual)
    const workflow = nativeOccurrenceWorkflowCanonical(request.workflow)
    if (Either.isLeft(assessment) || Either.isLeft(dual) || Either.isLeft(workflow)) return yield* Effect.fail(completionFailure("completion values cannot canonicalize for audit"))
    return yield* verifyQualifiedNativeExternalAudit({
      manifestPath: paths.auditManifest, bundlePath: paths.cosignBundle, manifestBytes, bundleBytes, rootBytes, licenseBytes, temporalReceiptBytes, temporalHistoryBytes, cwd: process.cwd(),
      temporal: { occurrenceUid: request.workflow.occurrenceUid, candidateReceiptSha256: request.candidate.receiptSha256, workflowSha256: digestTask(new TextEncoder().encode(renderNativeTaskJson(workflow.right))), workflowEvidenceSha256s: request.workflow.evidenceSha256s, completionStartedAt: request.startedAt, candidateTerminalAt: request.candidate.terminalAt, completionTerminalAt: request.terminalAt },
      crossBinding: { candidateReceiptSha256: request.candidate.receiptSha256, assessmentSha256: digestTask(new TextEncoder().encode(renderNativeTaskJson(assessment.right))), assessmentChainSha256: request.assessment.chainDigest, dualAssessmentSha256: digestTask(new TextEncoder().encode(renderNativeTaskJson(dual.right))), dualEvidenceSha256: request.dual.evidenceSha256, candidateWorkflowSha256: request.candidate.workflowSha256, terminalWorkflowSha256: digestTask(new TextEncoder().encode(renderNativeTaskJson(workflow.right))), candidateEvidenceSha256s: request.candidate.workflowEvidenceSha256s, terminalEvidenceSha256s: request.workflow.evidenceSha256s, completionStartedAt: request.startedAt, completionTerminalAt: request.terminalAt, qualificationSha256: hash(qualificationBytes), temporalHistoryExportSha256: hash(temporalHistoryBytes), temporalTerminalReceiptSha256: hash(temporalReceiptBytes) }
    }).pipe(Effect.mapError(error => completionFailure(error.detail)))
  })
}

export const completeNativeOccurrenceRuntime = (input: NativeOccurrenceCompletionInput): Effect.Effect<NativeIssuedCompletionReceipt, NativeCompletionError, PosixFileSystem | BoundedSubprocess | NativePinnedVerifier> => completeNativeOccurrenceWithAudit(input, defaultAuditService)
export const replayNativeOccurrenceCompletionRuntime = (input: NativeOccurrenceCompletionInput): Effect.Effect<NativeIssuedCompletionReceipt, NativeCompletionError, PosixFileSystem | BoundedSubprocess | NativePinnedVerifier> => replayNativeOccurrenceCompletion(input, defaultAuditService)
/** Performs the runtime-owned qualified audit only; callers cannot inject a verifier. */
export const verifyNativeOccurrenceAuditForCompletion = (request: NativeCompletionAuditRequest): Effect.Effect<import("./native-occurrence-audit-runtime.js").NativeQualifiedExternalAudit, NativeCompletionError, PosixFileSystem | BoundedSubprocess | NativePinnedVerifier> => defaultAuditService.verify(request)
