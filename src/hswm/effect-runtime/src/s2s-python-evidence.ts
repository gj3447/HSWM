import { Data, Either } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2S_PYTHON_EXECUTION_EVIDENCE_SCHEMA_VERSION,
  S2SNanosecondsSchema,
  S2SSha256Schema,
  type S2SPythonExecutionEvidence,
  type S2SSha256
} from "./s2s-confirmatory.js"
import {
  S2S_NUMERIC_ADJUDICATE_ARGUMENTS,
  S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS,
  S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
  S2S_NUMERIC_CANDIDATE_MAX_BYTES,
  S2S_NUMERIC_CONFIRM_ARGUMENTS,
  S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS,
  S2S_NUMERIC_ORACLE_SOURCE_SHA256,
  S2S_NUMERIC_STDERR_MAX_BYTES,
  validateS2SPythonRssTelemetryBytes,
  type S2SPythonNumericOutput,
  type S2SPythonRuntimeSourceIdentityReceipt
} from "./s2s-live-python.js"

export const S2S_PYTHON_INVOCATION_IDENTITY_SCHEMA_VERSION =
  "hswm-swm0w-s2s-python-invocation-identity/v1" as const

export interface S2SPythonInvocationIdentityReceipt {
  readonly schemaVersion: typeof S2S_PYTHON_INVOCATION_IDENTITY_SCHEMA_VERSION
  readonly operation: "confirm" | "adjudicate"
  readonly pythonExecutableArgv0: string
  readonly arguments: ReadonlyArray<string>
  readonly inputRawBytesSha256: S2SSha256
  readonly timeoutMillis: number
  readonly stdoutLimitBytes: number
  readonly stderrLimitBytes: number
  readonly processEnvironmentContractSha256: S2SSha256
  readonly runtimeSourceIdentityReceiptSha256: S2SSha256
  readonly numericOracleSourceSha256: typeof S2S_NUMERIC_ORACLE_SOURCE_SHA256
  readonly receiptSha256: S2SSha256
}

export interface S2SPythonExecutionBinding {
  readonly evidence: S2SPythonExecutionEvidence
  readonly invocationIdentity: S2SPythonInvocationIdentityReceipt
  readonly readInvocationIdentityCanonicalBytes: () => Uint8Array
}

export class S2SPythonExecutionEvidenceError extends Data.TaggedError(
  "S2SPythonExecutionEvidenceError"
)<{
  readonly reason:
    | "EXECUTOR_OUTPUT_DRIFT"
    | "HASH_COLLISION_OR_ALIAS"
    | "INVOCATION_NOT_CANONICAL"
    | "REQUEST_BINDING_MISMATCH"
    | "RUNTIME_IDENTITY_MISMATCH"
  readonly detail: string
}> {}

const evidenceError = (
  reason: S2SPythonExecutionEvidenceError["reason"],
  detail: string
): S2SPythonExecutionEvidenceError =>
  new S2SPythonExecutionEvidenceError({ reason, detail })

const SHA256_PATTERN = /^[0-9a-f]{64}$/

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const invocationCore = (
  output: S2SPythonNumericOutput,
  runtime: S2SPythonRuntimeSourceIdentityReceipt
) => {
  const confirm = output.operation === "CONFIRM"
  return Object.freeze({
    schemaVersion: S2S_PYTHON_INVOCATION_IDENTITY_SCHEMA_VERSION,
    operation: confirm ? ("confirm" as const) : ("adjudicate" as const),
    pythonExecutableArgv0: runtime.pythonExecutableArgv0,
    arguments: confirm
      ? S2S_NUMERIC_CONFIRM_ARGUMENTS
      : S2S_NUMERIC_ADJUDICATE_ARGUMENTS,
    inputRawBytesSha256: output.inputRawBytesSha256,
    timeoutMillis: confirm
      ? S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS
      : S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS,
    stdoutLimitBytes: confirm
      ? S2S_NUMERIC_CANDIDATE_MAX_BYTES
      : S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
    stderrLimitBytes: S2S_NUMERIC_STDERR_MAX_BYTES,
    processEnvironmentContractSha256:
      runtime.processEnvironmentContractSha256,
    runtimeSourceIdentityReceiptSha256: runtime.receiptSha256,
    numericOracleSourceSha256: S2S_NUMERIC_ORACLE_SOURCE_SHA256
  })
}

const evidenceCore = (
  output: S2SPythonNumericOutput,
  requestDocumentSha256: S2SSha256,
  requestSelfSha256: S2SSha256,
  runtime: S2SPythonRuntimeSourceIdentityReceipt,
  invocationIdentitySha256: S2SSha256
) =>
  Object.freeze({
    schemaVersion: S2S_PYTHON_EXECUTION_EVIDENCE_SCHEMA_VERSION,
    operation:
      output.operation === "CONFIRM"
        ? ("confirm" as const)
        : ("adjudicate" as const),
    inputRawBytesSha256: output.inputRawBytesSha256,
    outputRawBytesSha256: output.rawBytesSha256,
    requestDocumentSha256,
    requestSelfSha256,
    numericOracleSourceSha256: S2S_NUMERIC_ORACLE_SOURCE_SHA256,
    pythonRuntimeIdentitySha256: runtime.receiptSha256,
    invocationIdentitySha256,
    exitCode: 0 as const,
    elapsedNanoseconds: S2SNanosecondsSchema.make(
      output.commandElapsedNanoseconds
    )
  })

/**
 * Binds a process-backed executor result to the v3 lifecycle evidence shape.
 * Numeric bytes are only snapshotted and hashed; they are never parsed or
 * reserialized by this control-plane adapter.
 */
export const bindS2SPythonExecutionEvidence = (input: {
  readonly output: S2SPythonNumericOutput
  readonly runtimeSourceIdentity: S2SPythonRuntimeSourceIdentityReceipt
  readonly requestDocumentSha256: string
  readonly requestSelfSha256: string
}): Either.Either<
  S2SPythonExecutionBinding,
  S2SPythonExecutionEvidenceError
> => {
  const requestDocumentSha256 = input.requestDocumentSha256
  const requestSelfSha256 = input.requestSelfSha256
  if (
    !SHA256_PATTERN.test(requestDocumentSha256) ||
    !SHA256_PATTERN.test(requestSelfSha256) ||
    input.output.inputRawBytesSha256 !== requestDocumentSha256
  ) {
    return Either.left(
      evidenceError(
        "REQUEST_BINDING_MISMATCH",
        "executor stdin hash must equal the bound request document hash"
      )
    )
  }
  const runtime = input.runtimeSourceIdentity
  const oracleSource = runtime.sourceClosure.find(
    (entry) =>
      entry.path === "src/hswm/experiments/swm0w_s2s_numeric_oracle.py"
  )
  if (
    input.output.runtimeSourceIdentityReceiptSha256 !== runtime.receiptSha256 ||
    oracleSource?.rawBytesSha256 !== S2S_NUMERIC_ORACLE_SOURCE_SHA256
  ) {
    return Either.left(
      evidenceError(
        "RUNTIME_IDENTITY_MISMATCH",
        "executor result and frozen numeric-oracle closure must share one runtime identity"
      )
    )
  }
  let outputBytes: Uint8Array
  let rssTelemetryBytes: Uint8Array
  try {
    outputBytes = input.output.readCanonicalBytes()
    rssTelemetryBytes = input.output.readRssTelemetryCanonicalBytes()
  } catch {
    return Either.left(
      evidenceError(
        "EXECUTOR_OUTPUT_DRIFT",
        "executor output bytes could not be snapshotted"
      )
    )
  }
  const rssTelemetry = validateS2SPythonRssTelemetryBytes(
    input.output.operation,
    rssTelemetryBytes
  )
  const maximumOutputBytes =
    input.output.operation === "CONFIRM"
      ? S2S_NUMERIC_CANDIDATE_MAX_BYTES
      : S2S_NUMERIC_ADJUDICATION_MAX_BYTES
  if (
    (input.output.operation !== "CONFIRM" &&
      input.output.operation !== "ADJUDICATE") ||
    Either.isLeft(rssTelemetry) ||
    !(outputBytes instanceof Uint8Array) ||
    outputBytes.byteLength !== input.output.byteLength ||
    !Number.isSafeInteger(input.output.byteLength) ||
    input.output.byteLength < 1 ||
    input.output.byteLength > maximumOutputBytes ||
    rawS2SFileSha256(outputBytes) !== input.output.rawBytesSha256 ||
    (Either.isRight(rssTelemetry) &&
      (rssTelemetry.right.peakRssKiB !== input.output.peakRssKiB ||
        rssTelemetry.right.rawBytesSha256 !==
          input.output.rssTelemetryRawSha256)) ||
    !Number.isSafeInteger(input.output.commandElapsedNanoseconds) ||
    input.output.commandElapsedNanoseconds < 1 ||
    (input.output.operation === "CONFIRM" &&
      input.output.memberName !== "numeric_candidate.json") ||
    (input.output.operation === "ADJUDICATE" &&
      input.output.memberName !== "numeric_adjudication.json")
  ) {
    return Either.left(
      evidenceError(
        "EXECUTOR_OUTPUT_DRIFT",
        "executor output identity or elapsed time drifted"
      )
    )
  }
  const invocationUnsigned = invocationCore(input.output, runtime)
  const invocationHash = canonicalS2SControlSha256(invocationUnsigned)
  if (Either.isLeft(invocationHash)) {
    return Either.left(
      evidenceError(
        "INVOCATION_NOT_CANONICAL",
        "invocation identity cannot be canonically encoded"
      )
    )
  }
  const invocationIdentity = Object.freeze({
    ...invocationUnsigned,
    receiptSha256: S2SSha256Schema.make(invocationHash.right)
  })
  const invocationBytes = canonicalS2SControlJsonBytes(invocationIdentity)
  if (Either.isLeft(invocationBytes)) {
    return Either.left(
      evidenceError(
        "INVOCATION_NOT_CANONICAL",
        "invocation receipt cannot be canonically encoded"
      )
    )
  }
  const evidenceUnsigned = evidenceCore(
    input.output,
    S2SSha256Schema.make(requestDocumentSha256),
    S2SSha256Schema.make(requestSelfSha256),
    runtime,
    invocationIdentity.receiptSha256
  )
  const receipt = canonicalS2SControlSha256(evidenceUnsigned)
  if (Either.isLeft(receipt)) {
    return Either.left(
      evidenceError(
        "INVOCATION_NOT_CANONICAL",
        "execution evidence cannot be canonically encoded"
      )
    )
  }
  const identityHashes = [
    S2S_NUMERIC_ORACLE_SOURCE_SHA256,
    runtime.receiptSha256,
    invocationIdentity.receiptSha256
  ]
  if (new Set(identityHashes).size !== identityHashes.length) {
    return Either.left(
      evidenceError(
        "HASH_COLLISION_OR_ALIAS",
        "source, runtime, and invocation identities must be distinct"
      )
    )
  }
  const frozenInvocationBytes = new Uint8Array(invocationBytes.right)
  const evidence: S2SPythonExecutionEvidence = Object.freeze({
    ...evidenceUnsigned,
    receiptSha256: S2SSha256Schema.make(receipt.right)
  })
  if (!sameBytes(frozenInvocationBytes, invocationBytes.right)) {
    return Either.left(
      evidenceError(
        "INVOCATION_NOT_CANONICAL",
        "invocation byte snapshot drifted"
      )
    )
  }
  return Either.right(
    Object.freeze({
      evidence,
      invocationIdentity,
      readInvocationIdentityCanonicalBytes: () =>
        new Uint8Array(frozenInvocationBytes)
    })
  )
}
