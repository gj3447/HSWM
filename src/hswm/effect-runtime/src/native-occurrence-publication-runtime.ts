/** Publication always replays completion and independently re-verifies a SEALED audit. */
import { Effect } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { NativePinnedVerifier } from "./native-pinned-verifier-runtime.js"
import { nativeCompletionReceiptCanonical, type NativeIssuedCompletionReceipt, type NativeOccurrenceCompletionInput } from "./native-occurrence-completion-domain.js"
import { replayNativeOccurrenceCompletionRuntime, verifyNativeOccurrenceAuditForCompletion } from "./native-occurrence-completion-runtime.js"
import { NativeOccurrencePublicationError, projectNativeIssuedOccurrencePublication, type NativeOccurrenceArtifact, type NativeOccurrencePublication } from "./native-occurrence-publication.js"
import { renderNativeTaskJson } from "./native-task-json-domain.js"
const invalid = (detail: string) => new NativeOccurrencePublicationError({ code: "RECEIPT_INVALID", detail })
export const publishNativeOccurrenceProjection = (receipt: NativeIssuedCompletionReceipt, replay: NativeOccurrenceCompletionInput, artifacts: readonly NativeOccurrenceArtifact[], producer = "https://github.com/gj3447/HSWM"): Effect.Effect<NativeOccurrencePublication, NativeOccurrencePublicationError, PosixFileSystem | BoundedSubprocess | NativePinnedVerifier> => Effect.gen(function* () {
  const claimed = yield* nativeCompletionReceiptCanonical(receipt).pipe(Effect.mapError(error => invalid(error.detail)))
  const recomputed = yield* replayNativeOccurrenceCompletionRuntime(replay).pipe(Effect.mapError(error => invalid(error.detail)))
  const actual = yield* nativeCompletionReceiptCanonical(recomputed).pipe(Effect.mapError(error => invalid(error.detail)))
  if (renderNativeTaskJson(claimed) !== renderNativeTaskJson(actual)) return yield* Effect.fail(invalid("terminal receipt does not match fresh completion verification"))
  if (receipt.terminalStatus !== "SEALED" && receipt.terminalStatus !== "VOID") return yield* Effect.fail(invalid("terminal_status must be SEALED or VOID"))
  if (receipt.terminalStatus === "VOID") return yield* projectNativeIssuedOccurrencePublication(receipt, null, artifacts, producer)
  if (replay.candidateReceipt == null || replay.dualEvaluation === null || replay.externalAuditMaterial == null) return yield* Effect.fail(invalid("SEALED publication replay lacks external audit inputs"))
  const audit = yield* verifyNativeOccurrenceAuditForCompletion({ candidate: replay.candidateReceipt, assessment: replay.assessment, dual: replay.dualEvaluation, workflow: replay.workflow, material: replay.externalAuditMaterial, startedAt: replay.startedAt, terminalAt: replay.terminalAt }).pipe(Effect.mapError(error => invalid(error.detail)))
  if (audit.verificationSha256 !== receipt.externalAuditVerificationSha256) return yield* Effect.fail(invalid("fresh audit verification differs from the terminal receipt"))
  return yield* projectNativeIssuedOccurrencePublication(receipt, audit, artifacts, producer)
})
