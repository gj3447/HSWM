/**
 * Strict Python-v1-compatible Temporal wire codec for the G0 occurrence.
 *
 * This is a pure boundary: it parses descriptor-only JSON and maps the
 * snake_case Temporal payloads to the Effect phase-kernel's camelCase ingress.
 * It neither imports Temporal nor executes, queues, authenticates, or retries
 * a workflow. Unsupported phase/timing strings deliberately remain strings so
 * the phase kernel, not this codec, applies its terminal-first ORDER semantics.
 */
import { Data, Either } from "effect"

import {
  type G0ContentDescriptor,
  type G0OccurrenceInput,
  type G0OccurrenceState
} from "./g0-occurrence-phase-kernel.js"
import {
  decodeG0TemporalDomainStart,
  decodeG0TemporalDomainTransition
} from "./g0-occurrence-temporal-domain.js"

/** Version of the selected TypeScript wire; bytes retain the Python-v1 schema. */
export const HSWM_G0_OCCURRENCE_TS_AUTHORITY_WIRE_V1 =
  "hswm-g0-occurrence-ts-authority-wire/v1" as const
export const HSWM_G0_OCCURRENCE_TEMPORAL_WORKER_WIRE_V1 =
  "hswm-g0-occurrence-temporal-worker/v1" as const
export const HSWM_G0_OCCURRENCE_MAX_INPUT_JSON_BYTES = 65_536 as const

const digestPattern = /^[0-9a-f]{64}(?![\s\S])/u

export class G0OccurrenceTemporalWireError extends Data.TaggedError(
  "G0OccurrenceTemporalWireError"
)<{
  readonly reason: "INVALID_JSON" | "INPUT_INVALID" | "TRANSITION_INVALID" | "CONFIG_INVALID"
  readonly detail: string
}> {}

export interface G0OccurrenceTemporalWorkerConfiguration {
  readonly address: string
  readonly namespace: string
  readonly taskQueue: string
  readonly signalAuthorizationBindingSha256: string
}

/** Deliberately string-valued for Python-v1 invalid-phase/timing → kernel ORDER parity. */
export interface G0OccurrenceTemporalTransitionIngress {
  readonly nextPhase: string
  readonly evidence: G0ContentDescriptor
  readonly timing: string
}

export interface G0OccurrenceTemporalTerminalProjection {
  readonly schema_version: typeof HSWM_G0_OCCURRENCE_TEMPORAL_WORKER_WIRE_V1
  readonly occurrence_uid: string
  readonly phase: string
  readonly void_reason: string | null
  readonly rejected_evidence_sha256: string | null
  readonly evidence_sha256s: ReadonlyArray<string>
  readonly terminal: boolean
  readonly completion_handshake_required: true
  readonly publication_eligible: false
  readonly g0_status: "NOT_EVIDENCE_BY_ITSELF"
}

const failure = (
  reason: G0OccurrenceTemporalWireError["reason"],
  detail: string
): G0OccurrenceTemporalWireError => new G0OccurrenceTemporalWireError({ reason, detail })

const exactObject = (
  input: unknown,
  keys: ReadonlyArray<string>,
  reason: G0OccurrenceTemporalWireError["reason"],
  name: string
): Either.Either<Readonly<Record<string, unknown>>, G0OccurrenceTemporalWireError> => {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    return Either.left(failure(reason, `${name} must be a JSON object`))
  }
  const record = input as Readonly<Record<string, unknown>>
  const actual = Object.keys(record)
  if (actual.length !== keys.length || actual.some((key) => !keys.includes(key))) {
    return Either.left(failure(reason, `${name} has an unsupported shape`))
  }
  return Either.right(record)
}

const stringField = (
  record: Readonly<Record<string, unknown>>,
  key: string,
  reason: G0OccurrenceTemporalWireError["reason"],
  context: string
): Either.Either<string, G0OccurrenceTemporalWireError> =>
  typeof record[key] === "string"
    ? Either.right(record[key])
    : Either.left(failure(reason, `${context}.${key} must be a string`))

const parseJson = (
  bytes: Uint8Array,
  reason: G0OccurrenceTemporalWireError["reason"]
): Either.Either<unknown, G0OccurrenceTemporalWireError> => {
  if (bytes.byteLength > HSWM_G0_OCCURRENCE_MAX_INPUT_JSON_BYTES) {
    return Either.left(failure(reason, "JSON input exceeds byte limit"))
  }
  if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    return Either.left(failure("INVALID_JSON", "UTF-8 BOM is not accepted by the Python-v1 wire"))
  }
  try {
    return Either.right(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as unknown)
  } catch {
    return Either.left(failure("INVALID_JSON", "JSON input is not valid UTF-8 JSON"))
  }
}

export const decodeG0OccurrenceTemporalStartWire = (
  input: unknown
): Either.Either<G0OccurrenceInput, G0OccurrenceTemporalWireError> => {
  const decoded = decodeG0TemporalDomainStart(input)
  if (!decoded.ok) return Either.left(failure("INPUT_INVALID", decoded.detail))
  return Either.right(Object.freeze({
    occurrenceUid: decoded.value.occurrenceUid,
    wormClaimReceipt: decoded.value.wormClaimReceipt,
    registrationEvidence: decoded.value.registrationEvidence,
    occurrenceTimeoutSeconds: decoded.value.occurrenceTimeoutSeconds
  }))
}

export const decodeG0OccurrenceTemporalStartJsonBytes = (
  bytes: Uint8Array
): Either.Either<G0OccurrenceInput, G0OccurrenceTemporalWireError> => {
  const parsed = parseJson(bytes, "INPUT_INVALID")
  return Either.isLeft(parsed)
    ? Either.left(parsed.left)
    : decodeG0OccurrenceTemporalStartWire(parsed.right)
}

export const decodeG0OccurrenceTemporalTransitionWire = (
  input: unknown
): Either.Either<G0OccurrenceTemporalTransitionIngress, G0OccurrenceTemporalWireError> => {
  const decoded = decodeG0TemporalDomainTransition(input)
  return decoded.ok
    ? Either.right(Object.freeze({
      nextPhase: decoded.value.nextPhase,
      evidence: decoded.value.evidence,
      timing: decoded.value.timing
    }))
    : Either.left(failure("TRANSITION_INVALID", decoded.detail))
}

export const decodeG0OccurrenceTemporalTransitionJsonBytes = (
  bytes: Uint8Array
): Either.Either<G0OccurrenceTemporalTransitionIngress, G0OccurrenceTemporalWireError> => {
  const parsed = parseJson(bytes, "TRANSITION_INVALID")
  return Either.isLeft(parsed)
    ? Either.left(parsed.left)
    : decodeG0OccurrenceTemporalTransitionWire(parsed.right)
}

export const decodeG0OccurrenceTemporalWorkerConfigurationWire = (
  input: unknown
): Either.Either<G0OccurrenceTemporalWorkerConfiguration, G0OccurrenceTemporalWireError> => {
  const raw = exactObject(
    input,
    ["address", "namespace", "task_queue", "signal_authorization_binding_sha256"],
    "CONFIG_INVALID",
    "worker configuration"
  )
  if (Either.isLeft(raw)) return Either.left(raw.left)
  const address = stringField(raw.right, "address", "CONFIG_INVALID", "worker configuration")
  const namespace = stringField(raw.right, "namespace", "CONFIG_INVALID", "worker configuration")
  const taskQueue = stringField(raw.right, "task_queue", "CONFIG_INVALID", "worker configuration")
  const signalBinding = stringField(raw.right, "signal_authorization_binding_sha256", "CONFIG_INVALID", "worker configuration")
  if (Either.isLeft(address)) return Either.left(address.left)
  if (Either.isLeft(namespace)) return Either.left(namespace.left)
  if (Either.isLeft(taskQueue)) return Either.left(taskQueue.left)
  if (Either.isLeft(signalBinding)) return Either.left(signalBinding.left)
  const coordinates = [address.right, namespace.right, taskQueue.right]
  if (coordinates.some((value) => !value || value.length > 256 || /\s/u.test(value)) || !digestPattern.test(signalBinding.right)) {
    return Either.left(failure("CONFIG_INVALID", "worker configuration fields are invalid"))
  }
  return Either.right(Object.freeze({
    address: address.right,
    namespace: namespace.right,
    taskQueue: taskQueue.right,
    signalAuthorizationBindingSha256: signalBinding.right
  }))
}

export const projectG0OccurrenceTemporalTerminal = (
  state: G0OccurrenceState
): G0OccurrenceTemporalTerminalProjection => Object.freeze({
  schema_version: HSWM_G0_OCCURRENCE_TEMPORAL_WORKER_WIRE_V1,
  occurrence_uid: state.occurrenceUid,
  phase: state.phase,
  void_reason: state.voidReason,
  rejected_evidence_sha256: state.rejectedEvidenceSha256,
  evidence_sha256s: Object.freeze([...state.evidenceSha256s]),
  terminal: state.terminal,
  completion_handshake_required: true,
  publication_eligible: false,
  g0_status: "NOT_EVIDENCE_BY_ITSELF"
})
