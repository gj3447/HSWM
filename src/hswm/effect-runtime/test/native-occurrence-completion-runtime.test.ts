import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import type { SubprocessObservation } from "../src/effect-bounded-subprocess.js"
import { NativePinnedVerifierError, type NativePinnedVerifierShape } from "../src/native-pinned-verifier-runtime.js"
import { nativeCompletionReceiptCanonical } from "../src/native-occurrence-completion-domain.js"
import { completeNativeOccurrenceRuntime, replayNativeOccurrenceCompletionRuntime } from "../src/native-occurrence-completion-runtime.js"
import { completionTestBase, freshCandidateReceipt, originalSealedReceipt, qualifiedAuditServices, qualifiedAuditServicesWith, sealedCompletionInput } from "./fixtures/native-occurrence-audit.js"

const canonical = (receipt: Parameters<typeof nativeCompletionReceiptCanonical>[0]): Readonly<Record<string, unknown>> => {
  const result = nativeCompletionReceiptCanonical(receipt)
  if (Either.isLeft(result)) throw new Error(result.left.detail)
  return result.right
}

it.effect("completes the original source-pinned positive occurrence through qualified runtime verification", () =>
  Effect.gen(function* () {
    const receipt = yield* completeNativeOccurrenceRuntime(sealedCompletionInput())
    expect(canonical(receipt)).toEqual(originalSealedReceipt)
    expect(receipt.terminalStatus).toBe("SEALED")
  }).pipe(Effect.provide(qualifiedAuditServices)))

it.effect("replays the original positive completion afresh with the same issued receipt", () =>
  Effect.gen(function* () {
    const receipt = yield* replayNativeOccurrenceCompletionRuntime(sealedCompletionInput())
    expect(canonical(receipt)).toEqual(originalSealedReceipt)
  }).pipe(Effect.provide(qualifiedAuditServices)))

it.effect("refuses stale and tampered finalization instead of reusing a terminal receipt", () =>
  Effect.gen(function* () {
    const input = sealedCompletionInput()
    const stale = yield* Effect.either(completeNativeOccurrenceRuntime({ ...input, previousReceipt: freshCandidateReceipt() }))
    expect(Either.isLeft(stale)).toBe(true)
    const tampered = yield* completeNativeOccurrenceRuntime({ ...input, terminalAt: "2026-09-03T00:02:00.000001Z" })
    expect(tampered.terminalStatus).toBe("BLOCKED")
    expect(tampered.externalAuditVerificationSha256).toBe(null)
    const base = completionTestBase()
    expect(base.workflow.phase).toBe("DUAL_EVALUATED")
  }).pipe(Effect.provide(qualifiedAuditServices)))

it.effect("keeps the checked-in BLOCKED qualification authoritative before fixture material or Cosign can run", () =>
  Effect.gen(function* () {
    const receipt = yield* completeNativeOccurrenceRuntime(sealedCompletionInput())
    expect(receipt.terminalStatus).toBe("BLOCKED")
    expect(receipt.externalAuditVerificationSha256).toBe(null)
  }).pipe(Effect.provide(NodePosixServicesLive)))

const failedObservation = (patch: Pick<SubprocessObservation, "exitCode" | "timedOut" | "outputTruncated">): SubprocessObservation => ({
  exitCode: patch.exitCode, signal: null, timedOut: patch.timedOut, outputTruncated: patch.outputTruncated,
  launchError: null, stdout: new Uint8Array(), stderr: new Uint8Array()
})
for (const [name, observation] of [
  ["timeout", failedObservation({ exitCode: null, timedOut: true, outputTruncated: false })],
  ["nonzero exit", failedObservation({ exitCode: 1, timedOut: false, outputTruncated: false })],
  ["truncated output", failedObservation({ exitCode: 0, timedOut: false, outputTruncated: true })],
  ["version mismatch", failedObservation({ exitCode: 0, timedOut: false, outputTruncated: false })]
] as const) {
  it.effect(`blocks qualified-audit ${name} observations`, () =>
    Effect.gen(function* () {
      const receipt = yield* completeNativeOccurrenceRuntime(sealedCompletionInput())
      expect(receipt.terminalStatus).toBe("BLOCKED")
      expect(receipt.externalAuditVerificationSha256).toBe(null)
    }).pipe(Effect.provide(qualifiedAuditServicesWith({ observation: () => observation }))))
}

it.effect("detects audit inputs changed after the pre-invocation pin check", () =>
  Effect.gen(function* () {
    const receipt = yield* completeNativeOccurrenceRuntime(sealedCompletionInput())
    expect(receipt.terminalStatus).toBe("BLOCKED")
    expect(receipt.externalAuditVerificationSha256).toBe(null)
  }).pipe(Effect.provide(qualifiedAuditServicesWith({
    pinnedVerifier: { verify: (): ReturnType<NativePinnedVerifierShape["verify"]> => Effect.fail(new NativePinnedVerifierError({ code: "PIN_MISMATCH", detail: "held audit input changed" })) }
  }))))
