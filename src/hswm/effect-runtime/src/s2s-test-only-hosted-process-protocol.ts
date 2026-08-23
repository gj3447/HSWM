import { createHmac, timingSafeEqual } from "node:crypto"
import { isProxy } from "node:util/types"

import { Data, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import { parseS2SJsonBytes } from "./s2s-json.js"
import {
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  type S2SConfirmatoryJobId,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"

export const S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION =
  "hswm-swm0w-s2s-test-only-hosted-process-continuity/v1" as const

export const S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION =
  "TEST_ONLY_NON_AUTHORIZING" as const

export const S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES = 2_048 as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_SECRET_BYTES = 32 as const

const HEX_64_PATTERN = /^[0-9a-f]{64}$/
const NODE_VERSION_PATTERN = /^v[0-9]+\.[0-9]+\.[0-9]+$/
const PROC_START_TICKS_PATTERN = /^[1-9][0-9]{0,31}$/

const PositiveSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER)
)
const Hex64Schema = Schema.String.pipe(Schema.pattern(HEX_64_PATTERN))

const RuntimeIdentitySchema = Schema.Struct({
  rootPid: PositiveSafeIntegerSchema,
  procStartTicks: Schema.String.pipe(Schema.pattern(PROC_START_TICKS_PATTERN)),
  bootIdSha256: Hex64Schema,
  nodeVersion: Schema.String.pipe(Schema.pattern(NODE_VERSION_PATTERN)),
  nodeExecutableSha256: Hex64Schema,
  nodeExecutableDevice: PositiveSafeIntegerSchema,
  nodeExecutableInode: PositiveSafeIntegerSchema,
  instanceId: Hex64Schema
})

const BindingSchema = Schema.Struct({
  protocolVersion: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION
  ),
  nonce: Hex64Schema,
  workflowRunId: PositiveSafeIntegerSchema,
  workflowRunAttempt: Schema.Literal(1),
  feasibilityAttempt: Schema.Literal(1, 2, 3),
  stage: Schema.Literal("REGISTER", "CONFIRM", "ADJUDICATE"),
  jobId: Schema.Literal("register", "confirm", "adjudicate"),
  runtimeIdentity: RuntimeIdentitySchema
})

const ReadySchema = Schema.Struct({
  classification: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
  ),
  transition: Schema.Literal("READY"),
  sequence: Schema.Literal(0),
  binding: BindingSchema,
  tokenSha256: Hex64Schema,
  productionAuthorityClaimed: Schema.Literal(false),
  scientificEvidenceClaimed: Schema.Literal(false),
  authTag: Hex64Schema
})

const UploadStepOutcomeSchema = Schema.Literal(
  "success",
  "failure",
  "cancelled",
  "skipped",
  "unknown"
)

const ReconcileCoreSchema = Schema.Struct({
  classification: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
  ),
  transition: Schema.Literal("RECONCILE"),
  sequence: Schema.Literal(1),
  binding: BindingSchema,
  uploadStepOutcome: UploadStepOutcomeSchema
})

const ReconcileSchema = Schema.Struct({
  classification: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
  ),
  transition: Schema.Literal("RECONCILE"),
  sequence: Schema.Literal(1),
  binding: BindingSchema,
  uploadStepOutcome: UploadStepOutcomeSchema,
  authTag: Hex64Schema
})

const TerminalStatusSchema = Schema.Literal(
  "RECONCILED_ACTION_SUCCESS",
  "RECONCILED_ACTION_FAILURE",
  "RECONCILED_ACTION_UNKNOWN_NO_RETRY",
  "VOID_NO_COMPLETION"
)

const TerminalCoreSchema = Schema.Struct({
  classification: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
  ),
  transition: Schema.Literal("TERMINAL"),
  sequence: Schema.Literal(2),
  binding: BindingSchema,
  uploadStepOutcome: UploadStepOutcomeSchema,
  terminalStatus: TerminalStatusSchema,
  rootPidObservations: Schema.Tuple(
    PositiveSafeIntegerSchema,
    PositiveSafeIntegerSchema,
    PositiveSafeIntegerSchema
  ),
  reconciliationProbeCount: Schema.Literal(0, 1),
  publicationRetryCount: Schema.Literal(0),
  productionCompletionClaimed: Schema.Literal(false),
  externalExactlyOnceClaimed: Schema.Literal(false),
  scientificEvidenceClaimed: Schema.Literal(false)
})

const TerminalSchema = Schema.Struct({
  classification: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
  ),
  transition: Schema.Literal("TERMINAL"),
  sequence: Schema.Literal(2),
  binding: BindingSchema,
  uploadStepOutcome: UploadStepOutcomeSchema,
  terminalStatus: TerminalStatusSchema,
  rootPidObservations: Schema.Tuple(
    PositiveSafeIntegerSchema,
    PositiveSafeIntegerSchema,
    PositiveSafeIntegerSchema
  ),
  reconciliationProbeCount: Schema.Literal(0, 1),
  publicationRetryCount: Schema.Literal(0),
  productionCompletionClaimed: Schema.Literal(false),
  externalExactlyOnceClaimed: Schema.Literal(false),
  scientificEvidenceClaimed: Schema.Literal(false),
  authTag: Hex64Schema
})

export type S2STestOnlyHostedProcessRuntimeIdentity =
  typeof RuntimeIdentitySchema.Type
export type S2STestOnlyHostedProcessBinding = typeof BindingSchema.Type
export type S2STestOnlyHostedProcessUploadStepOutcome =
  typeof UploadStepOutcomeSchema.Type
export type S2STestOnlyHostedProcessTerminalStatus =
  typeof TerminalStatusSchema.Type
export type S2STestOnlyHostedProcessReady = typeof ReadySchema.Type
export type S2STestOnlyHostedProcessReconcile = typeof ReconcileSchema.Type
export type S2STestOnlyHostedProcessTerminal = typeof TerminalSchema.Type

export class S2STestOnlyHostedProcessProtocolError extends Data.TaggedError(
  "S2STestOnlyHostedProcessProtocolError"
)<{
  readonly phase: "INPUT" | "READY" | "RECONCILE" | "TERMINAL"
  readonly reason:
    | "SECRET_INVALID"
    | "FRAME_INVALID"
    | "FRAME_NON_CANONICAL"
    | "SCHEMA_INVALID"
    | "AUTHENTICATION_FAILED"
    | "BINDING_MISMATCH"
    | "STAGE_JOB_MISMATCH"
    | "ATTEMPT_STAGE_MISMATCH"
    | "ROOT_IDENTITY_DRIFT"
    | "TERMINAL_INVARIANT_INVALID"
  readonly detail: string
}> {}

const protocolError = (
  phase: S2STestOnlyHostedProcessProtocolError["phase"],
  reason: S2STestOnlyHostedProcessProtocolError["reason"],
  detail: string
): S2STestOnlyHostedProcessProtocolError =>
  new S2STestOnlyHostedProcessProtocolError({ phase, reason, detail })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const isPlainSecret = (input: unknown): input is Uint8Array =>
  input instanceof Uint8Array &&
  Object.getPrototypeOf(input) === Uint8Array.prototype &&
  input.byteLength === S2S_TEST_ONLY_HOSTED_PROCESS_SECRET_BYTES &&
  !(typeof SharedArrayBuffer !== "undefined" &&
    input.buffer instanceof SharedArrayBuffer)

const snapshotSecret = (
  input: unknown,
  phase: S2STestOnlyHostedProcessProtocolError["phase"]
): Either.Either<Uint8Array, S2STestOnlyHostedProcessProtocolError> => {
  try {
    return isPlainSecret(input)
      ? Either.right(new Uint8Array(input))
      : Either.left(
          protocolError(
            phase,
            "SECRET_INVALID",
            "authentication secret must be one plain unshared 32-byte Uint8Array"
          )
        )
  } catch {
    return Either.left(
      protocolError(
        phase,
        "SECRET_INVALID",
        "authentication secret inspection failed closed"
      )
    )
  }
}

const useSecret = <A>(
  input: unknown,
  phase: S2STestOnlyHostedProcessProtocolError["phase"],
  use: (
    secret: Uint8Array
  ) => Either.Either<A, S2STestOnlyHostedProcessProtocolError>
): Either.Either<A, S2STestOnlyHostedProcessProtocolError> => {
  const snapshot = snapshotSecret(input, phase)
  if (Either.isLeft(snapshot)) return Either.left(snapshot.left)
  try {
    return use(snapshot.right)
  } finally {
    snapshot.right.fill(0)
  }
}

const snapshotExactPlainRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>,
  phase: S2STestOnlyHostedProcessProtocolError["phase"],
  detail: string
): Either.Either<
  ReadonlyMap<string, unknown>,
  S2STestOnlyHostedProcessProtocolError
> => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      isProxy(input) ||
      Object.getPrototypeOf(input) !== Object.prototype
    ) {
      return Either.left(protocolError(phase, "SCHEMA_INVALID", detail))
    }
    const keys = Reflect.ownKeys(input)
    if (
      keys.length !== expectedKeys.length ||
      keys.some(
        (key) => typeof key !== "string" || !expectedKeys.includes(key)
      )
    ) {
      return Either.left(protocolError(phase, "SCHEMA_INVALID", detail))
    }
    const values = new Map<string, unknown>()
    for (const key of expectedKeys) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor)
      ) {
        return Either.left(protocolError(phase, "SCHEMA_INVALID", detail))
      }
      values.set(key, descriptor.value)
    }
    return Either.right(values)
  } catch {
    return Either.left(protocolError(phase, "SCHEMA_INVALID", detail))
  }
}

const freezeRuntimeIdentity = (
  identity: S2STestOnlyHostedProcessRuntimeIdentity
): S2STestOnlyHostedProcessRuntimeIdentity => Object.freeze({ ...identity })

const freezeBinding = (
  binding: S2STestOnlyHostedProcessBinding
): S2STestOnlyHostedProcessBinding =>
  Object.freeze({
    ...binding,
    runtimeIdentity: freezeRuntimeIdentity(binding.runtimeIdentity)
  })

const bindingMatches = (
  left: S2STestOnlyHostedProcessBinding,
  right: S2STestOnlyHostedProcessBinding
): boolean =>
  left.protocolVersion === right.protocolVersion &&
  left.nonce === right.nonce &&
  left.workflowRunId === right.workflowRunId &&
  left.workflowRunAttempt === right.workflowRunAttempt &&
  left.feasibilityAttempt === right.feasibilityAttempt &&
  left.stage === right.stage &&
  left.jobId === right.jobId &&
  left.runtimeIdentity.rootPid === right.runtimeIdentity.rootPid &&
  left.runtimeIdentity.procStartTicks === right.runtimeIdentity.procStartTicks &&
  left.runtimeIdentity.bootIdSha256 === right.runtimeIdentity.bootIdSha256 &&
  left.runtimeIdentity.nodeVersion === right.runtimeIdentity.nodeVersion &&
  left.runtimeIdentity.nodeExecutableSha256 ===
    right.runtimeIdentity.nodeExecutableSha256 &&
  left.runtimeIdentity.nodeExecutableDevice ===
    right.runtimeIdentity.nodeExecutableDevice &&
  left.runtimeIdentity.nodeExecutableInode ===
    right.runtimeIdentity.nodeExecutableInode &&
  left.runtimeIdentity.instanceId === right.runtimeIdentity.instanceId

const stageJobMatches = (
  binding: S2STestOnlyHostedProcessBinding
): boolean =>
  S2S_CONFIRMATORY_STAGE_CONTRACTS[binding.stage].jobId === binding.jobId

const ATTEMPT_STAGE = Object.freeze({
  1: "REGISTER",
  2: "CONFIRM",
  3: "ADJUDICATE"
} as const)

const attemptStageMatches = (
  binding: S2STestOnlyHostedProcessBinding
): boolean => ATTEMPT_STAGE[binding.feasibilityAttempt] === binding.stage

const expectedTerminalStatus = (
  outcome: S2STestOnlyHostedProcessUploadStepOutcome
): Exclude<S2STestOnlyHostedProcessTerminalStatus, "VOID_NO_COMPLETION"> =>
  outcome === "success"
    ? "RECONCILED_ACTION_SUCCESS"
    : outcome === "unknown"
      ? "RECONCILED_ACTION_UNKNOWN_NO_RETRY"
      : "RECONCILED_ACTION_FAILURE"

const terminalInvariantMatches = (
  outcome: S2STestOnlyHostedProcessUploadStepOutcome,
  status: S2STestOnlyHostedProcessTerminalStatus,
  reconciliationProbeCount: 0 | 1
): boolean =>
  status === "VOID_NO_COMPLETION"
    ? reconciliationProbeCount === 0
    : reconciliationProbeCount === 1 &&
      status === expectedTerminalStatus(outcome)

interface CanonicalSurfaceBudget {
  nodes: number
  encodedBytes: number
}

const jsonStringEncodedByteLength = (
  value: string,
  maximumBytes: number
): number => {
  let bytes = 2
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code === 0x22 || code === 0x5c) {
      bytes += 2
    } else if (code <= 0x1f) {
      bytes +=
        code === 0x08 ||
        code === 0x09 ||
        code === 0x0a ||
        code === 0x0c ||
        code === 0x0d
          ? 2
          : 6
    } else if (code <= 0x7f) {
      bytes += 1
    } else if (code <= 0x7ff) {
      bytes += 2
    } else if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (next >= 0xdc00 && next <= 0xdfff) {
        bytes += 4
        index += 1
      } else {
        bytes += 6
      }
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      bytes += 6
    } else {
      bytes += 3
    }
    if (bytes > maximumBytes) return maximumBytes + 1
  }
  return bytes
}

const reserveCanonicalBytes = (
  budget: CanonicalSurfaceBudget,
  additionalBytes: number
): boolean => {
  if (
    !Number.isSafeInteger(additionalBytes) ||
    additionalBytes < 0 ||
    additionalBytes > S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES -
      budget.encodedBytes
  ) {
    return false
  }
  budget.encodedBytes += additionalBytes
  return true
}

const snapshotCanonicalData = (
  input: unknown,
  phase: S2STestOnlyHostedProcessProtocolError["phase"],
  depth = 0,
  budget: CanonicalSurfaceBudget = { nodes: 0, encodedBytes: 0 }
): Either.Either<unknown, S2STestOnlyHostedProcessProtocolError> => {
  budget.nodes += 1
  if (depth > 12 || budget.nodes > 512) {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "canonical frame surface is too deep or large")
    )
  }
  if (input === null) {
    return reserveCanonicalBytes(budget, 4)
      ? Either.right(input)
      : Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical frame byte budget exceeded")
        )
  }
  if (typeof input === "string") {
    const bytes = jsonStringEncodedByteLength(
      input,
      S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES
    )
    return reserveCanonicalBytes(budget, bytes)
      ? Either.right(input)
      : Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical string byte budget exceeded")
        )
  }
  if (typeof input === "boolean") {
    return reserveCanonicalBytes(budget, input ? 4 : 5)
      ? Either.right(input)
      : Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical frame byte budget exceeded")
        )
  }
  if (typeof input === "number" && Number.isFinite(input)) {
    const bytes = String(input).length
    if (!reserveCanonicalBytes(budget, bytes)) {
      return Either.left(
        protocolError(phase, "FRAME_INVALID", "canonical number byte budget exceeded")
      )
    }
    return Either.right(input)
  }
  if (typeof input !== "object" || isProxy(input)) {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "canonical frame surface is invalid")
    )
  }
  try {
    if (Array.isArray(input)) {
      if (Object.getPrototypeOf(input) !== Array.prototype) {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical array surface is invalid")
        )
      }
      const lengthDescriptor = Object.getOwnPropertyDescriptor(input, "length")
      if (
        lengthDescriptor === undefined ||
        !("value" in lengthDescriptor) ||
        !Number.isSafeInteger(lengthDescriptor.value) ||
        lengthDescriptor.value < 0 ||
        lengthDescriptor.value > 256
      ) {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical array length is invalid")
        )
      }
      const length = lengthDescriptor.value
      if (!reserveCanonicalBytes(budget, 2 + Math.max(0, length - 1))) {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical array byte budget exceeded")
        )
      }
      const keys = Reflect.ownKeys(input)
      if (
        keys.length !== length + 1 ||
        !keys.includes("length")
      ) {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical array must be dense data")
        )
      }
      const output: Array<unknown> = []
      for (let index = 0; index < length; index += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
        if (
          descriptor === undefined ||
          !descriptor.enumerable ||
          !("value" in descriptor)
        ) {
          return Either.left(
            protocolError(phase, "FRAME_INVALID", "canonical array entry is invalid")
          )
        }
        const child = snapshotCanonicalData(
          descriptor.value,
          phase,
          depth + 1,
          budget
        )
        if (Either.isLeft(child)) return Either.left(child.left)
        output.push(child.right)
      }
      return Either.right(Object.freeze(output))
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) {
      return Either.left(
        protocolError(phase, "FRAME_INVALID", "canonical object surface is invalid")
      )
    }
    const keys = Reflect.ownKeys(input)
    if (
      keys.length > 128 ||
      keys.some((key) => typeof key !== "string")
    ) {
      return Either.left(
        protocolError(phase, "FRAME_INVALID", "canonical object keys are invalid")
      )
    }
    if (!reserveCanonicalBytes(budget, 2 + Math.max(0, keys.length * 2 - 1))) {
      return Either.left(
        protocolError(phase, "FRAME_INVALID", "canonical object byte budget exceeded")
      )
    }
    const output: Record<string, unknown> = {}
    for (const key of keys) {
      if (typeof key !== "string") {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical object key is invalid")
        )
      }
      const keyBytes = jsonStringEncodedByteLength(key, 256)
      if (keyBytes > 256 || !reserveCanonicalBytes(budget, keyBytes)) {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical object key byte budget exceeded")
        )
      }
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor)
      ) {
        return Either.left(
          protocolError(phase, "FRAME_INVALID", "canonical object entry is invalid")
        )
      }
      const child = snapshotCanonicalData(
        descriptor.value,
        phase,
        depth + 1,
        budget
      )
      if (Either.isLeft(child)) return Either.left(child.left)
      Object.defineProperty(output, key, {
        value: child.right,
        enumerable: true,
        configurable: false,
        writable: false
      })
    }
    return Either.right(Object.freeze(output))
  } catch {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "canonical frame inspection failed")
    )
  }
}

const canonicalBytes = (
  input: unknown,
  phase: S2STestOnlyHostedProcessProtocolError["phase"]
): Either.Either<Uint8Array, S2STestOnlyHostedProcessProtocolError> => {
  const snapshot = snapshotCanonicalData(input, phase)
  if (Either.isLeft(snapshot)) return Either.left(snapshot.left)
  let encoded: Either.Either<Uint8Array, unknown>
  try {
    encoded = canonicalS2SControlJsonBytes(snapshot.right)
  } catch {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "canonical frame inspection failed")
    )
  }
  if (Either.isLeft(encoded)) {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "canonical frame encoding failed")
    )
  }
  if (encoded.right.byteLength > S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES) {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "frame exceeds the 2,048-byte bound")
    )
  }
  return Either.right(encoded.right)
}

const authenticationTag = (
  domain: "READY" | "RECONCILE" | "TERMINAL",
  core: unknown,
  secret: Uint8Array,
  phase: S2STestOnlyHostedProcessProtocolError["phase"]
): Either.Either<string, S2STestOnlyHostedProcessProtocolError> => {
  const bytes = canonicalBytes(core, phase)
  return Either.map(bytes, (canonical) =>
    createHmac("sha256", secret)
      .update(S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION, "ascii")
      .update("\0", "ascii")
      .update(domain, "ascii")
      .update("\0", "ascii")
      .update(canonical)
      .digest("hex")
  )
}

const verifyAuthenticationTag = (
  expected: string,
  actual: string
): boolean => {
  if (!HEX_64_PATTERN.test(expected) || !HEX_64_PATTERN.test(actual)) {
    return false
  }
  return timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(actual, "hex"))
}

const decodeCanonical = <A, I>(
  frame: unknown,
  schema: Schema.Schema<A, I>,
  phase: S2STestOnlyHostedProcessProtocolError["phase"]
): Either.Either<A, S2STestOnlyHostedProcessProtocolError> => {
  let snapshot: Uint8Array
  try {
    if (
      !(frame instanceof Uint8Array) ||
      Object.getPrototypeOf(frame) !== Uint8Array.prototype ||
      (typeof SharedArrayBuffer !== "undefined" &&
        frame.buffer instanceof SharedArrayBuffer) ||
      frame.byteLength < 2 ||
      frame.byteLength > S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES
    ) {
      return Either.left(
        protocolError(phase, "FRAME_INVALID", "frame byte surface is invalid")
      )
    }
    snapshot = new Uint8Array(frame)
  } catch {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "frame inspection failed closed")
    )
  }
  const parsed = parseS2SJsonBytes(
    snapshot,
    S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES
  )
  if (Either.isLeft(parsed)) {
    return Either.left(
      protocolError(phase, "FRAME_INVALID", "frame JSON was rejected")
    )
  }
  const recoded = canonicalBytes(parsed.right, phase)
  if (Either.isLeft(recoded)) return Either.left(recoded.left)
  if (!sameBytes(snapshot, recoded.right)) {
    return Either.left(
      protocolError(
        phase,
        "FRAME_NON_CANONICAL",
        "wire frame is not exact canonical JSON plus one LF"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(schema, {
    onExcessProperty: "error"
  })(parsed.right)
  return Either.isLeft(decoded)
    ? Either.left(
        protocolError(phase, "SCHEMA_INVALID", "wire schema was rejected")
      )
    : Either.right(decoded.right)
}

const BINDING_KEYS = Object.freeze([
  "protocolVersion",
  "nonce",
  "workflowRunId",
  "workflowRunAttempt",
  "feasibilityAttempt",
  "stage",
  "jobId",
  "runtimeIdentity"
] as const)

const RUNTIME_IDENTITY_KEYS = Object.freeze([
  "rootPid",
  "procStartTicks",
  "bootIdSha256",
  "nodeVersion",
  "nodeExecutableSha256",
  "nodeExecutableDevice",
  "nodeExecutableInode",
  "instanceId"
] as const)

const READY_KEYS = Object.freeze([
  "classification",
  "transition",
  "sequence",
  "binding",
  "tokenSha256",
  "productionAuthorityClaimed",
  "scientificEvidenceClaimed",
  "authTag"
] as const)

const decodeBinding = (
  input: unknown
): Either.Either<
  S2STestOnlyHostedProcessBinding,
  S2STestOnlyHostedProcessProtocolError
> => {
  const bindingSurface = snapshotExactPlainRecord(
    input,
    BINDING_KEYS,
    "INPUT",
    "binding must be one exact plain data object"
  )
  if (Either.isLeft(bindingSurface)) return Either.left(bindingSurface.left)
  const runtimeSurface = snapshotExactPlainRecord(
    bindingSurface.right.get("runtimeIdentity"),
    RUNTIME_IDENTITY_KEYS,
    "INPUT",
    "runtime identity must be one exact plain data object"
  )
  if (Either.isLeft(runtimeSurface)) return Either.left(runtimeSurface.left)
  const candidate = {
    protocolVersion: bindingSurface.right.get("protocolVersion"),
    nonce: bindingSurface.right.get("nonce"),
    workflowRunId: bindingSurface.right.get("workflowRunId"),
    workflowRunAttempt: bindingSurface.right.get("workflowRunAttempt"),
    feasibilityAttempt: bindingSurface.right.get("feasibilityAttempt"),
    stage: bindingSurface.right.get("stage"),
    jobId: bindingSurface.right.get("jobId"),
    runtimeIdentity: {
      rootPid: runtimeSurface.right.get("rootPid"),
      procStartTicks: runtimeSurface.right.get("procStartTicks"),
      bootIdSha256: runtimeSurface.right.get("bootIdSha256"),
      nodeVersion: runtimeSurface.right.get("nodeVersion"),
      nodeExecutableSha256: runtimeSurface.right.get("nodeExecutableSha256"),
      nodeExecutableDevice: runtimeSurface.right.get("nodeExecutableDevice"),
      nodeExecutableInode: runtimeSurface.right.get("nodeExecutableInode"),
      instanceId: runtimeSurface.right.get("instanceId")
    }
  }
  let decoded: Either.Either<S2STestOnlyHostedProcessBinding, unknown>
  try {
    decoded = Schema.decodeUnknownEither(BindingSchema, {
      onExcessProperty: "error"
    })(candidate)
  } catch {
    return Either.left(
      protocolError("INPUT", "SCHEMA_INVALID", "binding schema inspection failed")
    )
  }
  if (Either.isLeft(decoded)) {
    return Either.left(
      protocolError("INPUT", "SCHEMA_INVALID", "binding schema was rejected")
    )
  }
  if (!stageJobMatches(decoded.right)) {
    return Either.left(
      protocolError(
        "INPUT",
        "STAGE_JOB_MISMATCH",
        "stage and job ID do not match the fixed workflow contract"
      )
    )
  }
  if (!attemptStageMatches(decoded.right)) {
    return Either.left(
      protocolError(
        "INPUT",
        "ATTEMPT_STAGE_MISMATCH",
        "attempt and stage do not match the fixed feasibility sequence"
      )
    )
  }
  return Either.right(freezeBinding(decoded.right))
}

export const makeS2STestOnlyHostedProcessBinding = (
  input: unknown
): Either.Either<
  S2STestOnlyHostedProcessBinding,
  S2STestOnlyHostedProcessProtocolError
> => decodeBinding(input)

export const makeS2STestOnlyHostedProcessReady = (
  bindingInput: unknown,
  tokenInput: unknown,
  tokenSha256: string
): Either.Either<
  S2STestOnlyHostedProcessReady,
  S2STestOnlyHostedProcessProtocolError
> => {
  const binding = decodeBinding(bindingInput)
  if (Either.isLeft(binding)) return Either.left(binding.left)
  return useSecret(tokenInput, "READY", (token) => {
    if (
      !HEX_64_PATTERN.test(tokenSha256) ||
      rawS2SFileSha256(token) !== tokenSha256
    ) {
      return Either.left(
        protocolError("READY", "SCHEMA_INVALID", "token hash is invalid")
      )
    }
    const core = Object.freeze({
      classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
      transition: "READY" as const,
      sequence: 0 as const,
      binding: binding.right,
      tokenSha256,
      productionAuthorityClaimed: false as const,
      scientificEvidenceClaimed: false as const
    })
    const tag = authenticationTag("READY", core, token, "READY")
    return Either.map(tag, (authTag) => Object.freeze({ ...core, authTag }))
  })
}

export const makeS2STestOnlyHostedProcessReconcileFrame = (
  ready: S2STestOnlyHostedProcessReady,
  outcome: S2STestOnlyHostedProcessUploadStepOutcome,
  tokenInput: unknown
): Either.Either<Uint8Array, S2STestOnlyHostedProcessProtocolError> => {
  const readySurface = snapshotExactPlainRecord(
    ready,
    READY_KEYS,
    "RECONCILE",
    "ready input must be one exact plain data object"
  )
  if (Either.isLeft(readySurface)) return Either.left(readySurface.left)
  const binding = decodeBinding(readySurface.right.get("binding"))
  if (Either.isLeft(binding)) return Either.left(binding.left)
  const core = Object.freeze({
    classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
    transition: "RECONCILE" as const,
    sequence: 1 as const,
    binding: binding.right,
    uploadStepOutcome: outcome
  })
  const decoded = Schema.decodeUnknownEither(ReconcileCoreSchema, {
    onExcessProperty: "error"
  })(core)
  if (
    Either.isLeft(decoded) ||
    !stageJobMatches(core.binding) ||
    !attemptStageMatches(core.binding)
  ) {
    return Either.left(
      protocolError(
        "RECONCILE",
        "SCHEMA_INVALID",
        "reconcile core was rejected"
      )
    )
  }
  return useSecret(tokenInput, "RECONCILE", (token) => {
    const tag = authenticationTag("RECONCILE", core, token, "RECONCILE")
    return Either.flatMap(tag, (authTag) =>
      canonicalBytes(Object.freeze({ ...core, authTag }), "RECONCILE")
    )
  })
}

export const decodeS2STestOnlyHostedProcessReadyFrame = (
  frame: unknown,
  tokenInput: unknown
): Either.Either<
  S2STestOnlyHostedProcessReady,
  S2STestOnlyHostedProcessProtocolError
> =>
  useSecret(tokenInput, "READY", (token) => {
  const decoded = decodeCanonical(frame, ReadySchema, "READY")
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  if (rawS2SFileSha256(token) !== decoded.right.tokenSha256) {
    return Either.left(
      protocolError(
        "READY",
        "AUTHENTICATION_FAILED",
        "ready token commitment did not match"
      )
    )
  }
  if (
    !stageJobMatches(decoded.right.binding) ||
    !attemptStageMatches(decoded.right.binding)
  ) {
    return Either.left(
      protocolError("READY", "STAGE_JOB_MISMATCH", "ready binding drifted")
    )
  }
  const core = Object.freeze({
    classification: decoded.right.classification,
    transition: decoded.right.transition,
    sequence: decoded.right.sequence,
    binding: freezeBinding(decoded.right.binding),
    tokenSha256: decoded.right.tokenSha256,
    productionAuthorityClaimed: decoded.right.productionAuthorityClaimed,
    scientificEvidenceClaimed: decoded.right.scientificEvidenceClaimed
  })
  const tag = authenticationTag("READY", core, token, "READY")
  if (Either.isLeft(tag)) return Either.left(tag.left)
  if (!verifyAuthenticationTag(tag.right, decoded.right.authTag)) {
    return Either.left(
      protocolError("READY", "AUTHENTICATION_FAILED", "ready HMAC did not match")
    )
  }
  return Either.right(
    Object.freeze({ ...core, authTag: decoded.right.authTag })
  )
  })

export const decodeS2STestOnlyHostedProcessReconcileFrame = (
  frame: unknown,
  expectedBinding: S2STestOnlyHostedProcessBinding,
  tokenInput: unknown
): Either.Either<
  S2STestOnlyHostedProcessReconcile,
  S2STestOnlyHostedProcessProtocolError
> => {
  const expected = decodeBinding(expectedBinding)
  if (Either.isLeft(expected)) return Either.left(expected.left)
  return useSecret(tokenInput, "RECONCILE", (token) => {
  const decoded = decodeCanonical(frame, ReconcileSchema, "RECONCILE")
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  if (
    !stageJobMatches(decoded.right.binding) ||
    !attemptStageMatches(decoded.right.binding)
  ) {
    return Either.left(
      protocolError(
        "RECONCILE",
        "STAGE_JOB_MISMATCH",
        "reconcile stage/job binding drifted"
      )
    )
  }
  if (!bindingMatches(decoded.right.binding, expected.right)) {
    return Either.left(
      protocolError(
        "RECONCILE",
        "BINDING_MISMATCH",
        "reconcile binding does not match the live root"
      )
    )
  }
  const core = Object.freeze({
    classification: decoded.right.classification,
    transition: decoded.right.transition,
    sequence: decoded.right.sequence,
    binding: freezeBinding(decoded.right.binding),
    uploadStepOutcome: decoded.right.uploadStepOutcome
  })
  const tag = authenticationTag(
    "RECONCILE",
    core,
    token,
    "RECONCILE"
  )
  if (Either.isLeft(tag)) return Either.left(tag.left)
  if (!verifyAuthenticationTag(tag.right, decoded.right.authTag)) {
    return Either.left(
      protocolError(
        "RECONCILE",
        "AUTHENTICATION_FAILED",
        "reconcile HMAC did not match"
      )
    )
  }
  return Either.right(
    Object.freeze({ ...core, authTag: decoded.right.authTag })
  )
  })
}

export const makeS2STestOnlyHostedProcessTerminal = (
  bindingInput: unknown,
  outcome: S2STestOnlyHostedProcessUploadStepOutcome,
  status: S2STestOnlyHostedProcessTerminalStatus,
  reconciliationProbeCount: 0 | 1,
  tokenInput: unknown
): Either.Either<
  S2STestOnlyHostedProcessTerminal,
  S2STestOnlyHostedProcessProtocolError
> => {
  const binding = decodeBinding(bindingInput)
  if (Either.isLeft(binding)) return Either.left(binding.left)
  const pid = binding.right.runtimeIdentity.rootPid
  const core = Object.freeze({
    classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
    transition: "TERMINAL" as const,
    sequence: 2 as const,
    binding: binding.right,
    uploadStepOutcome: outcome,
    terminalStatus: status,
    rootPidObservations: Object.freeze([pid, pid, pid] as const),
    reconciliationProbeCount,
    publicationRetryCount: 0 as const,
    productionCompletionClaimed: false as const,
    externalExactlyOnceClaimed: false as const,
    scientificEvidenceClaimed: false as const
  })
  const decoded = Schema.decodeUnknownEither(TerminalCoreSchema, {
    onExcessProperty: "error"
  })(core)
  if (
    Either.isLeft(decoded) ||
    !terminalInvariantMatches(outcome, status, reconciliationProbeCount)
  ) {
    return Either.left(
      protocolError(
        "TERMINAL",
        Either.isLeft(decoded)
          ? "SCHEMA_INVALID"
          : "TERMINAL_INVARIANT_INVALID",
        "terminal core or outcome/status/probe invariant was rejected"
      )
    )
  }
  return useSecret(tokenInput, "TERMINAL", (token) => {
    const tag = authenticationTag("TERMINAL", core, token, "TERMINAL")
    return Either.map(tag, (authTag) => Object.freeze({ ...core, authTag }))
  })
}

export const canonicalS2STestOnlyHostedProcessFrame = (
  document: unknown,
  phase: "READY" | "RECONCILE" | "TERMINAL"
): Either.Either<Uint8Array, S2STestOnlyHostedProcessProtocolError> =>
  canonicalBytes(document, phase)

export const decodeS2STestOnlyHostedProcessTerminalFrame = (
  frame: unknown,
  expectedBinding: S2STestOnlyHostedProcessBinding,
  tokenInput: unknown
): Either.Either<
  S2STestOnlyHostedProcessTerminal,
  S2STestOnlyHostedProcessProtocolError
> => {
  const expected = decodeBinding(expectedBinding)
  if (Either.isLeft(expected)) return Either.left(expected.left)
  return useSecret(tokenInput, "TERMINAL", (token) => {
  const decoded = decodeCanonical(frame, TerminalSchema, "TERMINAL")
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  if (!bindingMatches(decoded.right.binding, expected.right)) {
    return Either.left(
      protocolError(
        "TERMINAL",
        "BINDING_MISMATCH",
        "terminal binding does not match the live root"
      )
    )
  }
  const pid = expected.right.runtimeIdentity.rootPid
  if (
    decoded.right.rootPidObservations[0] !== pid ||
    decoded.right.rootPidObservations[1] !== pid ||
    decoded.right.rootPidObservations[2] !== pid
  ) {
    return Either.left(
      protocolError(
        "TERMINAL",
        "ROOT_IDENTITY_DRIFT",
        "terminal root PID observations are not identical"
      )
    )
  }
  if (
    !stageJobMatches(decoded.right.binding) ||
    !attemptStageMatches(decoded.right.binding) ||
    !terminalInvariantMatches(
      decoded.right.uploadStepOutcome,
      decoded.right.terminalStatus,
      decoded.right.reconciliationProbeCount
    )
  ) {
    return Either.left(
      protocolError(
        "TERMINAL",
        "TERMINAL_INVARIANT_INVALID",
        "terminal binding or outcome/status/probe invariant drifted"
      )
    )
  }
  const core = Object.freeze({
    classification: decoded.right.classification,
    transition: decoded.right.transition,
    sequence: decoded.right.sequence,
    binding: freezeBinding(decoded.right.binding),
    uploadStepOutcome: decoded.right.uploadStepOutcome,
    terminalStatus: decoded.right.terminalStatus,
    rootPidObservations: Object.freeze([
      decoded.right.rootPidObservations[0],
      decoded.right.rootPidObservations[1],
      decoded.right.rootPidObservations[2]
    ] as const),
    reconciliationProbeCount: decoded.right.reconciliationProbeCount,
    publicationRetryCount: decoded.right.publicationRetryCount,
    productionCompletionClaimed: decoded.right.productionCompletionClaimed,
    externalExactlyOnceClaimed: decoded.right.externalExactlyOnceClaimed,
    scientificEvidenceClaimed: decoded.right.scientificEvidenceClaimed
  })
  const tag = authenticationTag("TERMINAL", core, token, "TERMINAL")
  if (Either.isLeft(tag)) return Either.left(tag.left)
  if (!verifyAuthenticationTag(tag.right, decoded.right.authTag)) {
    return Either.left(
      protocolError(
        "TERMINAL",
        "AUTHENTICATION_FAILED",
        "terminal HMAC did not match"
      )
    )
  }
  return Either.right(
    Object.freeze({ ...core, authTag: decoded.right.authTag })
  )
  })
}

export const s2sTestOnlyHostedProcessStageJobMatches = (
  stage: S2SConfirmatoryJobStage,
  jobId: S2SConfirmatoryJobId
): boolean => S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobId === jobId

export const s2sTestOnlyHostedProcessAttemptStageJobMatches = (
  feasibilityAttempt: 1 | 2 | 3,
  stage: S2SConfirmatoryJobStage,
  jobId: S2SConfirmatoryJobId
): boolean =>
  ATTEMPT_STAGE[feasibilityAttempt] === stage &&
  S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobId === jobId
