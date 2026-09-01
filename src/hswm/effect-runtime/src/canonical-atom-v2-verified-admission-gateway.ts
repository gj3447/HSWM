import { createHash } from "node:crypto"
import { realpathSync, statSync } from "node:fs"
import { isAbsolute } from "node:path"

import { Data, Effect, Either } from "effect"

import {
  HSWM_LOCAL_PERMIT_COMMIT_STATUS,
  HSWM_LOCAL_PERMIT_COMMIT_V1,
  LocalPermitCommitError,
  makeLocalPermitVerifierContext,
  makeVerifiedAdmissionCommitBackend,
  makeVerifiedAdmissionCommitBackendV2,
  type LocalPermitCommitReceipt,
  type LocalPermitCommitRequest,
  type LocalPermitRecovery,
  type LocalPermitVerifierContext,
  type VerifiedAdmissionDecisionArtifact,
  type VerifiedAdmissionLocalCommitV2Receipt,
  type VerifiedAdmissionRecoveryV2,
  type VerifiedAdmissionPreflight
} from "./canonical-atom-v2-local-permit-commit.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { runS2SBoundedProcess } from "./s2s-bounded-process.js"

/** A Lean CLI gate over the protected, separate local journal namespace. */
export const HSWM_VERIFIED_ADMISSION_GATEWAY_V1 = "hswm-verified-admission-gateway/v1" as const
export const HSWM_VERIFIED_ADMISSION_GATEWAY_V2 = "hswm-verified-admission-gateway/v2" as const
export const HSWM_VERIFIED_ADMISSION_WIRE_V1 = "hswm-verified-admission-wire/v1" as const
export const HSWM_VERIFIED_ADMISSION_GATEWAY_STATUS =
  "CALLER_CONFIGURED_UNPINNED_LEAN_CLI_EXACT_CANONICAL_DECISION_LIVE_GATE_ONLY_RECOVERY_DOES_NOT_PERSIST_DECISION_128_NONCE_WIRE_CEILING_PROCESS_LOCAL_REALPATH_ROOT_SERIALIZATION_LINUX_ONLY_NO_CROSS_PROCESS_OR_OS_UID_GUARANTEE_NOT_CRYPTO_CLOCK_OR_TS_SOURCE_REFINEMENT" as const
export const HSWM_VERIFIED_ADMISSION_GATEWAY_V2_STATUS =
  "CALLER_CONFIGURED_UNPINNED_LEAN_CLI_EXACT_CANONICAL_DECISION_PERSISTED_IN_SAME_IMMUTABLE_COMMIT_RECORD_AND_RECOVERY_REVALIDATED_128_NONCE_WIRE_CEILING_PROCESS_LOCAL_REALPATH_ROOT_SERIALIZATION_LINUX_ONLY_NO_CROSS_PROCESS_OR_OS_UID_GUARANTEE_NOT_CRYPTO_CLOCK_POWER_LOSS_OR_TS_SOURCE_REFINEMENT" as const

export class VerifiedAdmissionGatewayError extends Data.TaggedError("VerifiedAdmissionGatewayError")<{
  readonly code: "CONFIG_INVALID" | "LEAN_PROCESS_REJECTED" | "LEAN_RESPONSE_REJECTED"
  readonly detail: string
}> {}

export interface VerifiedAdmissionGatewayConfig {
  readonly leanExecutable: string
  readonly timeoutMillis?: number
}

export interface VerifiedAdmissionGatewayReceipt {
  readonly commit: LocalPermitCommitReceipt
  readonly requestSha256: string
  readonly decisionSha256: string
  readonly status: typeof HSWM_VERIFIED_ADMISSION_GATEWAY_STATUS
}

export interface VerifiedAdmissionGateway {
  readonly submit: (request: LocalPermitCommitRequest) => Effect.Effect<VerifiedAdmissionGatewayReceipt, LocalPermitCommitError | VerifiedAdmissionGatewayError>
  readonly recover: () => Effect.Effect<LocalPermitRecovery, LocalPermitCommitError>
}

export interface VerifiedAdmissionGatewayV2Receipt {
  readonly commit: VerifiedAdmissionLocalCommitV2Receipt
  readonly decision: VerifiedAdmissionDecisionArtifact
  readonly status: typeof HSWM_VERIFIED_ADMISSION_GATEWAY_V2_STATUS
}

export interface VerifiedAdmissionGatewayV2 {
  readonly submit: (request: LocalPermitCommitRequest) => Effect.Effect<VerifiedAdmissionGatewayV2Receipt, LocalPermitCommitError | VerifiedAdmissionGatewayError>
  readonly recover: () => Effect.Effect<VerifiedAdmissionRecoveryV2, LocalPermitCommitError>
}

const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const protectedRootSemaphores = new Map<string, ReturnType<typeof Effect.unsafeMakeSemaphore>>()
const semaphoreForRoot = (root: string): ReturnType<typeof Effect.unsafeMakeSemaphore> => {
  const current = protectedRootSemaphores.get(root)
  if (current !== undefined) return current
  const created = Effect.unsafeMakeSemaphore(1)
  protectedRootSemaphores.set(root, created)
  return created
}
const sameBytes = (left: Uint8Array, right: Uint8Array): boolean => left.byteLength === right.byteLength && left.every((v, i) => v === right[i])
const plainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)
const exactKeys = (value: unknown, keys: ReadonlyArray<string>): value is Record<string, unknown> =>
  plainObject(value) && Object.keys(value).sort().join("\u0000") === [...keys].sort().join("\u0000")
const sameJson = (left: unknown, right: unknown): boolean => {
  const leftBytes = canonicalJsonBytes(left)
  const rightBytes = canonicalJsonBytes(right)
  return Either.isRight(leftBytes) && Either.isRight(rightBytes) && sameBytes(leftBytes.right, rightBytes.right)
}

const wireRequest = (preflight: VerifiedAdmissionPreflight): Record<string, unknown> => Object.freeze({
  adapterFacts: Object.freeze({ permitEnvelopeAccepted: true, stateBytesAccepted: true, verificationTimeAccepted: true }),
  contractVersion: HSWM_VERIFIED_ADMISSION_WIRE_V1,
  record: Object.freeze({
    committedAt: preflight.record.committedAt,
    contractVersion: HSWM_LOCAL_PERMIT_COMMIT_V1,
    envelopeDigest: preflight.record.envelopeDigest,
    executionIntentDigest: preflight.record.executionIntentDigest,
    expectedNextHead: Object.freeze({ ...preflight.record.expectedNextHead }),
    nonceDigest: preflight.record.nonceDigest,
    priorHead: Object.freeze({ ...preflight.record.priorHead }),
    status: HSWM_LOCAL_PERMIT_COMMIT_STATUS,
    verificationTime: preflight.record.verificationTime
  }),
  view: Object.freeze({
    consumedNonces: Object.freeze([...preflight.view.consumedNonces]),
    head: preflight.view.head === null ? null : Object.freeze({ ...preflight.view.head })
  })
})

const acceptedResponseIsExact = (bytes: Uint8Array, request: Record<string, unknown>): boolean => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded) || !exactKeys(decoded.right, ["contractVersion", "decision", "request", "successor"])) return false
  const response = decoded.right
  if (response["contractVersion"] !== HSWM_VERIFIED_ADMISSION_WIRE_V1 || response["decision"] !== "accepted" || !sameJson(response["request"], request)) return false
  if (!exactKeys(response["successor"], ["consumedNonces", "head"])) return false
  const record = request["record"] as Record<string, unknown>
  const expectedSuccessor = {
    consumedNonces: [record["nonceDigest"], ...((request["view"] as Record<string, unknown>)["consumedNonces"] as string[])],
    head: record["expectedNextHead"]
  }
  if (!sameJson(response["successor"], expectedSuccessor)) return false
  const canonical = canonicalJsonBytes(response)
  return Either.isRight(canonical) && sameBytes(canonical.right, bytes)
}

/**
 * The only package-root API for the protected namespace.  The underlying
 * prepared state and approval never cross this API: Permit/state/recovery
 * checks, exact Lean decision, then no-replace publication occur in one call.
 */
export const makeVerifiedAdmissionGateway = (
  rootPath: string,
  verifier: LocalPermitVerifierContext,
  config: VerifiedAdmissionGatewayConfig,
  clock: () => Date = () => new Date()
): Either.Either<VerifiedAdmissionGateway, VerifiedAdmissionGatewayError> => {
  if (!isAbsolute(rootPath) || !isAbsolute(config.leanExecutable) || !Number.isSafeInteger(config.timeoutMillis ?? 10_000) || (config.timeoutMillis ?? 10_000) < 1 || (config.timeoutMillis ?? 10_000) > 60_000) {
    return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway requires absolute root and Lean executable plus a 1..60000ms timeout" }))
  }
  let normalizedRoot: string
  try {
    normalizedRoot = realpathSync.native(rootPath)
    if (!statSync(normalizedRoot).isDirectory()) {
      return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway root must be an existing directory" }))
    }
  } catch {
    return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway root must be an existing realpath-resolvable directory" }))
  }
  const leanExecutable = config.leanExecutable
  const timeoutMillis = config.timeoutMillis ?? 10_000
  const verifierSnapshot = makeLocalPermitVerifierContext(Uint8Array.from(verifier.trustSnapshotBytes))
  if (Either.isLeft(verifierSnapshot)) {
    return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway verifier snapshot must be exact canonical public trust bytes" }))
  }
  const rootSemaphore = semaphoreForRoot(normalizedRoot)
  const decisions = new WeakMap<object, { readonly requestSha256: string; readonly decisionSha256: string }>()
  const backend = makeVerifiedAdmissionCommitBackend(normalizedRoot, verifierSnapshot.right, (preflight, mintApproval) => Effect.gen(function* () {
    if (preflight.view.consumedNonces.length >= 128) {
      return yield* Effect.fail(new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission wire refuses more than 128 recovered nonce digests" }))
    }
    const request = wireRequest(preflight)
    const encoded = canonicalJsonBytes(request)
    if (Either.isLeft(encoded) || encoded.right.byteLength > 65_536) {
      return yield* Effect.fail(new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission request could not be canonically bounded" }))
    }
    const result = yield* Effect.mapError(
      runS2SBoundedProcess({
        operation: "HSWM_VERIFIED_ADMISSION_LEAN_CLI", executable: leanExecutable,
        arguments: [], cwd: normalizedRoot, environment: {}, stdin: encoded.right,
        timeoutMillis, stdoutLimitBytes: 131_072, stderrLimitBytes: 16_384
      }),
      () => new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission Lean CLI process failed closed" })
    )
    if (result.exitCode !== 0 || result.stderr.byteLength !== 0 || !acceptedResponseIsExact(result.stdout, request)) {
      return yield* Effect.fail(new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission Lean CLI did not return the exact accepted canonical successor" }))
    }
    const approval = mintApproval()
    decisions.set(approval, Object.freeze({ requestSha256: sha256(encoded.right), decisionSha256: sha256(result.stdout) }))
    return approval
  }), clock)
  return Either.right(Object.freeze({
    recover: backend.recover,
    submit: (request: LocalPermitCommitRequest) => rootSemaphore.withPermits(1)(Effect.gen(function* () {
      // Snapshot all caller-owned byte arrays before the first asynchronous
      // recovery/Lean boundary; publication uses precisely these bytes.
      const frozenRequest: LocalPermitCommitRequest = Object.freeze({
        envelopeBytes: Uint8Array.from(request.envelopeBytes),
        expectedBindings: Object.freeze({ ...request.expectedBindings, priorHead: Object.freeze({ ...request.expectedBindings.priorHead }), expectedNextHead: Object.freeze({ ...request.expectedBindings.expectedNextHead }), target: Object.freeze({ ...request.expectedBindings.target }) }),
        preStateBytes: Uint8Array.from(request.preStateBytes), postStateBytes: Uint8Array.from(request.postStateBytes)
      })
      const published = yield* backend.submit(frozenRequest)
      const decision = decisions.get(published.admission)
      if (decision === undefined) return yield* Effect.fail(new VerifiedAdmissionGatewayError({ code: "LEAN_RESPONSE_REJECTED", detail: "accepted decision receipt was unavailable after publication" }))
      decisions.delete(published.admission)
      return Object.freeze({ commit: published.receipt, ...decision, status: HSWM_VERIFIED_ADMISSION_GATEWAY_STATUS })
    }))
  }))
}

/**
 * V2 keeps v1's bounded Lean gate but publishes the exact canonical request
 * and accepted response in the same immutable slot as the state transition.
 * Recovery validates those stored bytes against the journal-reconstructed
 * predecessor view; it never re-runs a potentially changed executable.
 */
export const makeVerifiedAdmissionGatewayV2 = (
  rootPath: string,
  verifier: LocalPermitVerifierContext,
  config: VerifiedAdmissionGatewayConfig,
  clock: () => Date = () => new Date()
): Either.Either<VerifiedAdmissionGatewayV2, VerifiedAdmissionGatewayError> => {
  if (!isAbsolute(rootPath) || !isAbsolute(config.leanExecutable) || !Number.isSafeInteger(config.timeoutMillis ?? 10_000) || (config.timeoutMillis ?? 10_000) < 1 || (config.timeoutMillis ?? 10_000) > 60_000) {
    return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway requires absolute root and Lean executable plus a 1..60000ms timeout" }))
  }
  let normalizedRoot: string
  try {
    normalizedRoot = realpathSync.native(rootPath)
    if (!statSync(normalizedRoot).isDirectory()) {
      return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway root must be an existing directory" }))
    }
  } catch {
    return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway root must be an existing realpath-resolvable directory" }))
  }
  const leanExecutable = config.leanExecutable
  const timeoutMillis = config.timeoutMillis ?? 10_000
  const verifierSnapshot = makeLocalPermitVerifierContext(Uint8Array.from(verifier.trustSnapshotBytes))
  if (Either.isLeft(verifierSnapshot)) {
    return Either.left(new VerifiedAdmissionGatewayError({ code: "CONFIG_INVALID", detail: "gateway verifier snapshot must be exact canonical public trust bytes" }))
  }
  const validatePersistedDecision = (
    preflight: VerifiedAdmissionPreflight,
    artifact: VerifiedAdmissionDecisionArtifact
  ): Either.Either<void, LocalPermitCommitError> => {
    if (preflight.view.consumedNonces.length >= 128) {
      return Either.left(new LocalPermitCommitError({ code: "RECOVERY_INVALID", detail: "verified-admission wire refuses more than 128 recovered nonce digests" }))
    }
    const request = wireRequest(preflight)
    const encoded = canonicalJsonBytes(request)
    if (Either.isLeft(encoded) || encoded.right.byteLength > 65_536 ||
        artifact.wireContractVersion !== HSWM_VERIFIED_ADMISSION_WIRE_V1 ||
        !sameBytes(encoded.right, artifact.canonicalRequestBytes) ||
        !acceptedResponseIsExact(artifact.canonicalResponseBytes, request)) {
      return Either.left(new LocalPermitCommitError({ code: "RECOVERY_INVALID", detail: "persisted verified-admission decision is not the exact canonical request and accepted successor for the reconstructed view" }))
    }
    return Either.right(undefined)
  }
  const backend = makeVerifiedAdmissionCommitBackendV2(
    normalizedRoot,
    verifierSnapshot.right,
    (preflight, mintApproval) => Effect.gen(function* () {
      if (preflight.view.consumedNonces.length >= 128) {
        return yield* Effect.fail(new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission wire refuses more than 128 recovered nonce digests" }))
      }
      const request = wireRequest(preflight)
      const encoded = canonicalJsonBytes(request)
      if (Either.isLeft(encoded) || encoded.right.byteLength > 65_536) {
        return yield* Effect.fail(new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission request could not be canonically bounded" }))
      }
      const result = yield* Effect.mapError(
        runS2SBoundedProcess({
          operation: "HSWM_VERIFIED_ADMISSION_LEAN_CLI_V2", executable: leanExecutable,
          arguments: [], cwd: normalizedRoot, environment: {}, stdin: encoded.right,
          timeoutMillis, stdoutLimitBytes: 131_072, stderrLimitBytes: 16_384
        }),
        () => new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission Lean CLI process failed closed" })
      )
      if (result.exitCode !== 0 || result.stderr.byteLength !== 0 || !acceptedResponseIsExact(result.stdout, request)) {
        return yield* Effect.fail(new LocalPermitCommitError({ code: "PERMIT_VERIFICATION_FAILED", detail: "verified-admission Lean CLI did not return the exact accepted canonical successor" }))
      }
      return mintApproval(Object.freeze({
        wireContractVersion: HSWM_VERIFIED_ADMISSION_WIRE_V1,
        canonicalRequestBytes: Uint8Array.from(encoded.right),
        canonicalResponseBytes: Uint8Array.from(result.stdout),
        requestSha256: sha256(encoded.right),
        decisionSha256: sha256(result.stdout)
      }))
    }),
    validatePersistedDecision,
    clock
  )
  const rootSemaphore = semaphoreForRoot(normalizedRoot)
  return Either.right(Object.freeze({
    recover: backend.recover,
    submit: (request: LocalPermitCommitRequest) => rootSemaphore.withPermits(1)(Effect.gen(function* () {
      const frozenRequest: LocalPermitCommitRequest = Object.freeze({
        envelopeBytes: Uint8Array.from(request.envelopeBytes),
        expectedBindings: Object.freeze({ ...request.expectedBindings, priorHead: Object.freeze({ ...request.expectedBindings.priorHead }), expectedNextHead: Object.freeze({ ...request.expectedBindings.expectedNextHead }), target: Object.freeze({ ...request.expectedBindings.target }) }),
        preStateBytes: Uint8Array.from(request.preStateBytes), postStateBytes: Uint8Array.from(request.postStateBytes)
      })
      const published = yield* backend.submit(frozenRequest)
      return Object.freeze({ ...published, status: HSWM_VERIFIED_ADMISSION_GATEWAY_V2_STATUS })
    }))
  }))
}
