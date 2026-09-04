/**
 * Read-only Temporal history export and terminal-audit candidate material.
 *
 * This module accepts a strict normalized history, not a raw Temporal protobuf
 * response. A source-pinned adapter must preserve every event and add decoded
 * `hswmDecodedInput` / `hswmDecodedResult` values to the first and last event.
 * The exporter compares those values before emitting canonical bytes.
 *
 * It has no Temporal client, filesystem, endpoint, credential, signing, or
 * execution capability. Its candidate is deliberately schema-incompatible
 * with the independent auditor receipt accepted by Python completion.
 */
import { Data, Effect, Either } from "effect"

import { canonicalJsonBytes, canonicalJsonSha256, type CanonicalJson } from "./canonical-atom-v2-json.js"
import {
  HSWM_G0_TEMPORAL_CLAIM_BOUNDARY,
  HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
  HSWM_G0_TEMPORAL_WORKFLOW_TYPE,
  type G0TemporalWorkflowResultV1
} from "./g0-occurrence-temporal-contract.js"
import {
  decodeG0TemporalDomainStart,
  type G0TemporalDomainStart
} from "./g0-occurrence-temporal-domain.js"

export const HSWM_G0_TEMPORAL_HISTORY_EXPORT_V1 = "hswm-temporal-history-export/v1" as const
export const HSWM_G0_TEMPORAL_HISTORY_SOURCE_API =
  "temporal.api.workflowservice.v1.WorkflowService/GetWorkflowExecutionHistory" as const
export const HSWM_G0_TEMPORAL_TERMINAL_AUDIT_CANDIDATE_V1 =
  "hswm-temporal-terminal-audit-candidate/v1" as const
export const HSWM_G0_TEMPORAL_AUDIT_CANDIDATE_CLAIM_BOUNDARY =
  "local exporter assertion over supplied normalized history; not the qualified independent terminal audit receipt, not a Temporal-native signature, outcome truth, G0, Permit, canonical admission, or learning evidence" as const
export const HSWM_G0_TEMPORAL_NORMALIZED_HISTORY_INPUT_BOUNDARY =
  "STRICT_COMPLETE_SOURCE_PINNED_NORMALIZATION_REQUIRED_NOT_RAW_PROTOBUF" as const

const digestPattern = /^[0-9a-f]{64}(?![\s\S])/u
const uidPattern = /^[A-Za-z][A-Za-z0-9._:-]{0,127}(?![\s\S])/u
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![\s\S])/u
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})(?![\s\S])/u

export interface G0TemporalNormalizedHistoryEvent {
  readonly eventId: number | string
  readonly eventType: string
  readonly eventTime: string
  readonly [field: string]: CanonicalJson
}

/** One fully fetched, request-identity-bound history page-set. */
export interface G0TemporalNormalizedHistoryReadback {
  readonly sourceApi: typeof HSWM_G0_TEMPORAL_HISTORY_SOURCE_API
  readonly namespace: string
  readonly workflowId: string
  readonly runId: string
  readonly nextPageToken: ""
  readonly events: ReadonlyArray<G0TemporalNormalizedHistoryEvent>
}

export interface G0TemporalTerminalAuditCandidateInput {
  readonly history: G0TemporalNormalizedHistoryReadback
  readonly serverIdentitySha256: string
  readonly candidateReceiptSha256: string
  readonly exporterIdentity: string
  readonly retrievedAt: string
}

export interface G0TemporalHistoryExportV1 {
  readonly schema_version: typeof HSWM_G0_TEMPORAL_HISTORY_EXPORT_V1
  readonly source_api: typeof HSWM_G0_TEMPORAL_HISTORY_SOURCE_API
  readonly namespace: string
  readonly workflow_id: string
  readonly run_id: string
  readonly retrieved_at: string
  readonly server_identity_sha256: string
  readonly signal_authorization_binding_sha256: string
  readonly next_page_token: ""
  readonly events: ReadonlyArray<G0TemporalNormalizedHistoryEvent>
}

/**
 * Unsigned local candidate for independent review. Its schema and claim
 * boundary intentionally cannot pass the external completion-auditor parser.
 */
export interface G0TemporalTerminalAuditCandidateV1 {
  readonly schema_version: typeof HSWM_G0_TEMPORAL_TERMINAL_AUDIT_CANDIDATE_V1
  readonly claim_boundary: typeof HSWM_G0_TEMPORAL_AUDIT_CANDIDATE_CLAIM_BOUNDARY
  readonly occurrence_uid: string
  readonly namespace: string
  readonly workflow_id: string
  readonly run_id: string
  readonly workflow_type: typeof HSWM_G0_TEMPORAL_WORKFLOW_TYPE
  readonly terminal_phase: "SEALED"
  readonly candidate_receipt_sha256: string
  readonly workflow_sha256: string
  readonly workflow_evidence_sha256s: ReadonlyArray<string>
  readonly history_export_sha256: string
  readonly history_event_count: number
  readonly history_first_event_id: number
  readonly history_last_event_id: number
  readonly completed_at: string
  readonly workflow_id_reuse_policy: "REJECT_DUPLICATE"
  readonly workflow_maximum_attempts: 1
  readonly activity_maximum_attempts: 1
  readonly replacement_round_allowed: false
  readonly signal_authorization_binding_sha256: string
  readonly server_identity_sha256: string
  readonly exporter_identity: string
}

export interface G0TemporalTerminalAuditCandidateExport {
  readonly normalizedHistoryInputBoundary: typeof HSWM_G0_TEMPORAL_NORMALIZED_HISTORY_INPUT_BOUNDARY
  readonly history: G0TemporalHistoryExportV1
  readonly historyBytes: Uint8Array
  readonly historySha256: string
  readonly candidate: G0TemporalTerminalAuditCandidateV1
  readonly candidateBytes: Uint8Array
  readonly candidateSha256: string
  readonly externalAuditReceiptClaimed: false
  readonly independentAuditClaimed: false
  readonly scientificEvidenceClaimed: false
  readonly g0Passed: false
}

export class G0TemporalAuditCandidateError extends Data.TaggedError("G0TemporalAuditCandidateError")<{
  readonly reason: "INPUT_INVALID" | "HISTORY_INVALID" | "TERMINAL_INVALID" | "CANONICALIZATION_FAILED"
  readonly detail: string
}> {}

interface AcceptedNormalizedStart {
  readonly occurrence: G0TemporalDomainStart
  readonly executionClassification: "SIMULATED_OPERATOR_REHEARSAL"
  readonly operatorQualificationReceiptSha256: string
  readonly signalAuthorizationBindingSha256: string
}

interface ValidatedHistory {
  readonly namespace: string
  readonly workflowId: string
  readonly runId: string
  readonly events: ReadonlyArray<G0TemporalNormalizedHistoryEvent>
  readonly start: AcceptedNormalizedStart
  readonly terminal: G0TemporalWorkflowResultV1
}

const fail = (
  reason: G0TemporalAuditCandidateError["reason"],
  detail: string
): Either.Either<never, G0TemporalAuditCandidateError> =>
  Either.left(new G0TemporalAuditCandidateError({ reason, detail }))

const exactObject = (value: unknown, keys: ReadonlyArray<string>): value is Readonly<Record<string, unknown>> =>
  typeof value === "object" && value !== null && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key))

const record = (value: unknown): Readonly<Record<string, unknown>> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Readonly<Record<string, unknown>>
    : null

const boundedText = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= 1024 && value.trim() === value && !value.includes("\0")

const isDigest = (value: unknown): value is string => typeof value === "string" && digestPattern.test(value)
const isTimestamp = (value: unknown): value is string =>
  typeof value === "string" && boundedText(value) && timestampPattern.test(value) && Number.isFinite(Date.parse(value))

const eventId = (value: unknown): number | null => {
  const numeric = typeof value === "string" && /^[0-9]+(?![\s\S])/u.test(value)
    ? Number(value)
    : value
  return typeof numeric === "number" && Number.isSafeInteger(numeric) && numeric > 0 ? numeric : null
}

const frozen = <A>(value: A): A => Object.freeze(value)

const decodeNormalizedStart = (
  value: unknown
): Either.Either<AcceptedNormalizedStart, G0TemporalAuditCandidateError> => {
  if (!exactObject(value, [
    "schema_version", "occurrence", "execution_classification",
    "operator_qualification_receipt_sha256", "signal_authorization_binding_sha256"
  ]) || value["schema_version"] !== HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1 ||
      value["execution_classification"] !== "SIMULATED_OPERATOR_REHEARSAL" ||
      !isDigest(value["operator_qualification_receipt_sha256"]) ||
      !isDigest(value["signal_authorization_binding_sha256"])) {
    return fail("HISTORY_INVALID", "normalized start input is not the exact admitted rehearsal envelope")
  }
  const occurrence = decodeG0TemporalDomainStart(value["occurrence"])
  if (!occurrence.ok) return fail("HISTORY_INVALID", "normalized start occurrence is invalid")
  const qualification = value["operator_qualification_receipt_sha256"]
  const binding = value["signal_authorization_binding_sha256"]
  if (
    qualification === binding ||
    qualification === occurrence.value.registrationEvidence.sha256 ||
    qualification === occurrence.value.wormClaimReceipt.sha256 ||
    binding === occurrence.value.registrationEvidence.sha256 ||
    binding === occurrence.value.wormClaimReceipt.sha256
  ) return fail("HISTORY_INVALID", "normalized start descriptor roles are not digest-separated")
  return Either.right(frozen({
    occurrence: occurrence.value,
    executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
    operatorQualificationReceiptSha256: qualification,
    signalAuthorizationBindingSha256: binding
  }))
}

const terminalWorkflowShape = (value: unknown): value is G0TemporalWorkflowResultV1 =>
  exactObject(value, [
    "schema_version", "occurrence_uid", "phase", "void_reason", "rejected_evidence_sha256",
    "evidence_sha256s", "terminal", "completion_handshake_required", "publication_eligible",
    "g0_status", "authority_schema_version", "workflow_type", "execution_classification",
    "operator_qualification_receipt_sha256", "signal_authorization_binding_sha256",
    "orchestration_authority", "temporal_execution_observed", "external_operator_qualification_claimed",
    "scientific_evidence_claimed", "g0_passed", "claim_boundary"
  ])

const validateTerminal = (
  value: unknown
): Either.Either<G0TemporalWorkflowResultV1, G0TemporalAuditCandidateError> => {
  if (!terminalWorkflowShape(value)) return fail("TERMINAL_INVALID", "normalized terminal result has the wrong shape")
  if (
    !uidPattern.test(value.occurrence_uid) || value.phase !== "SEALED" || value.terminal !== true ||
    value.void_reason !== null || value.rejected_evidence_sha256 !== null ||
    value.schema_version !== "hswm-g0-occurrence-temporal-worker/v1" ||
    value.workflow_type !== HSWM_G0_TEMPORAL_WORKFLOW_TYPE ||
    value.completion_handshake_required !== true || value.publication_eligible !== false ||
    value.g0_status !== "NOT_EVIDENCE_BY_ITSELF" ||
    value.authority_schema_version !== HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1 ||
    value.execution_classification !== "SIMULATED_OPERATOR_REHEARSAL" ||
    value.orchestration_authority !== "TYPESCRIPT_TEMPORAL" || value.temporal_execution_observed !== true ||
    value.external_operator_qualification_claimed !== false || value.scientific_evidence_claimed !== false ||
    value.g0_passed !== false || value.claim_boundary !== HSWM_G0_TEMPORAL_CLAIM_BOUNDARY ||
    !isDigest(value.signal_authorization_binding_sha256) ||
    !isDigest(value.operator_qualification_receipt_sha256) || !Array.isArray(value.evidence_sha256s) ||
    value.evidence_sha256s.length < 2 || value.evidence_sha256s.some((digest) => !isDigest(digest)) ||
    new Set(value.evidence_sha256s).size !== value.evidence_sha256s.length
  ) return fail("TERMINAL_INVALID", "normalized terminal result is not a sealed non-promoting rehearsal result")
  return Either.right(value)
}

const validateHistory = (
  history: unknown,
  retrievedAt: string
): Either.Either<ValidatedHistory, G0TemporalAuditCandidateError> => {
  if (!exactObject(history, ["sourceApi", "namespace", "workflowId", "runId", "nextPageToken", "events"]) ||
      history["sourceApi"] !== HSWM_G0_TEMPORAL_HISTORY_SOURCE_API || history["nextPageToken"] !== "" ||
      !boundedText(history["namespace"]) || !boundedText(history["workflowId"]) ||
      typeof history["runId"] !== "string" || !uuidPattern.test(history["runId"]) ||
      !Array.isArray(history["events"]) || history["events"].length === 0) {
    return fail("HISTORY_INVALID", "history must be one complete identity-bound normalized readback")
  }
  const events = history["events"] as ReadonlyArray<G0TemporalNormalizedHistoryEvent>
  let priorId = 0
  let priorTime = Number.NEGATIVE_INFINITY
  for (const [index, event] of events.entries()) {
    if (record(event) === null || !Object.hasOwn(event, "eventId") ||
        !Object.hasOwn(event, "eventType") || !Object.hasOwn(event, "eventTime")) {
      return fail("HISTORY_INVALID", `normalized event ${index} lacks eventId/eventType/eventTime`)
    }
    const id = eventId(event.eventId)
    const time = isTimestamp(event.eventTime) ? Date.parse(event.eventTime) : Number.NaN
    if (id === null || id !== priorId + 1 || !boundedText(event.eventType) ||
        !Number.isFinite(time) || time < priorTime) {
      return fail("HISTORY_INVALID", `normalized event ${index} is invalid, non-contiguous, or out of order`)
    }
    if (Either.isLeft(canonicalJsonBytes(event))) {
      return fail("CANONICALIZATION_FAILED", `normalized event ${index} is not canonical-JSON compatible`)
    }
    priorId = id
    priorTime = time
  }
  const first = events[0] as G0TemporalNormalizedHistoryEvent
  const last = events.at(-1) as G0TemporalNormalizedHistoryEvent
  const started = record(first["workflowExecutionStartedEventAttributes"])
  const completed = record(last["workflowExecutionCompletedEventAttributes"])
  const workflowType = record(started?.["workflowType"])
  if (first.eventType !== "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED" ||
      last.eventType !== "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED" || started === null || completed === null ||
      workflowType?.["name"] !== HSWM_G0_TEMPORAL_WORKFLOW_TYPE ||
      !Object.hasOwn(started, "hswmDecodedInput") || !Object.hasOwn(completed, "hswmDecodedResult") ||
      Date.parse(retrievedAt) < Date.parse(last.eventTime)) {
    return fail("HISTORY_INVALID", "history lacks fixed terminals or source-pinned decoded payload values")
  }
  const start = decodeNormalizedStart(started["hswmDecodedInput"])
  if (Either.isLeft(start)) return Either.left(start.left)
  const terminal = validateTerminal(completed["hswmDecodedResult"])
  if (Either.isLeft(terminal)) return Either.left(terminal.left)
  if (
    history["workflowId"] !== `g0-occurrence/${start.right.occurrence.occurrenceUid}` ||
    terminal.right.occurrence_uid !== start.right.occurrence.occurrenceUid ||
    terminal.right.execution_classification !== start.right.executionClassification ||
    terminal.right.operator_qualification_receipt_sha256 !== start.right.operatorQualificationReceiptSha256 ||
    terminal.right.signal_authorization_binding_sha256 !== start.right.signalAuthorizationBindingSha256 ||
    terminal.right.evidence_sha256s[0] !== start.right.occurrence.registrationEvidence.sha256 ||
    terminal.right.evidence_sha256s[1] !== start.right.occurrence.wormClaimReceipt.sha256
  ) return fail("TERMINAL_INVALID", "normalized start, completion, workflow ID, or initial evidence do not bind")
  return Either.right(frozen({
    namespace: history["namespace"],
    workflowId: history["workflowId"],
    runId: history["runId"],
    events: Object.freeze([...events]),
    start: start.right,
    terminal: terminal.right
  }))
}

const workflowDigestPayload = (workflow: G0TemporalWorkflowResultV1): Readonly<Record<string, CanonicalJson>> => ({
  evidence_sha256s: [...workflow.evidence_sha256s],
  occurrence_uid: workflow.occurrence_uid,
  phase: workflow.phase,
  rejected_evidence_sha256: workflow.rejected_evidence_sha256,
  schema_version: workflow.schema_version,
  void_reason: workflow.void_reason
})

const exportEither = (
  input: unknown
): Either.Either<G0TemporalTerminalAuditCandidateExport, G0TemporalAuditCandidateError> => {
  if (!exactObject(input, [
    "history", "serverIdentitySha256", "candidateReceiptSha256", "exporterIdentity", "retrievedAt"
  ])) return fail("INPUT_INVALID", "candidate input must have the exact read-only descriptor shape")
  if (!isDigest(input["serverIdentitySha256"]) || !isDigest(input["candidateReceiptSha256"]) ||
      !boundedText(input["exporterIdentity"]) || !isTimestamp(input["retrievedAt"])) {
    return fail("INPUT_INVALID", "server, candidate, exporter, or retrieval fields are invalid")
  }
  const validated = validateHistory(input["history"], input["retrievedAt"])
  if (Either.isLeft(validated)) return Either.left(validated.left)
  const value = validated.right
  const history: G0TemporalHistoryExportV1 = frozen({
    schema_version: HSWM_G0_TEMPORAL_HISTORY_EXPORT_V1,
    source_api: HSWM_G0_TEMPORAL_HISTORY_SOURCE_API,
    namespace: value.namespace,
    workflow_id: value.workflowId,
    run_id: value.runId,
    retrieved_at: input["retrievedAt"],
    server_identity_sha256: input["serverIdentitySha256"],
    signal_authorization_binding_sha256: value.start.signalAuthorizationBindingSha256,
    next_page_token: "",
    events: value.events
  })
  const historyBytes = canonicalJsonBytes(history)
  const historySha = canonicalJsonSha256(history)
  const workflowSha = canonicalJsonSha256(workflowDigestPayload(value.terminal))
  if (Either.isLeft(historyBytes) || Either.isLeft(historySha) || Either.isLeft(workflowSha)) {
    return fail("CANONICALIZATION_FAILED", "validated export material could not be canonicalized")
  }
  const firstId = eventId(value.events[0]?.eventId)
  const lastId = eventId(value.events.at(-1)?.eventId)
  if (firstId === null || lastId === null) return fail("HISTORY_INVALID", "history event IDs vanished after validation")
  const candidate: G0TemporalTerminalAuditCandidateV1 = frozen({
    schema_version: HSWM_G0_TEMPORAL_TERMINAL_AUDIT_CANDIDATE_V1,
    claim_boundary: HSWM_G0_TEMPORAL_AUDIT_CANDIDATE_CLAIM_BOUNDARY,
    occurrence_uid: value.terminal.occurrence_uid,
    namespace: value.namespace,
    workflow_id: value.workflowId,
    run_id: value.runId,
    workflow_type: HSWM_G0_TEMPORAL_WORKFLOW_TYPE,
    terminal_phase: "SEALED",
    candidate_receipt_sha256: input["candidateReceiptSha256"],
    workflow_sha256: workflowSha.right,
    workflow_evidence_sha256s: Object.freeze([...value.terminal.evidence_sha256s]),
    history_export_sha256: historySha.right,
    history_event_count: value.events.length,
    history_first_event_id: firstId,
    history_last_event_id: lastId,
    completed_at: value.events.at(-1)?.eventTime as string,
    workflow_id_reuse_policy: "REJECT_DUPLICATE",
    workflow_maximum_attempts: 1,
    activity_maximum_attempts: 1,
    replacement_round_allowed: false,
    signal_authorization_binding_sha256: value.start.signalAuthorizationBindingSha256,
    server_identity_sha256: input["serverIdentitySha256"],
    exporter_identity: input["exporterIdentity"]
  })
  const candidateBytes = canonicalJsonBytes(candidate)
  const candidateSha = canonicalJsonSha256(candidate)
  if (Either.isLeft(candidateBytes) || Either.isLeft(candidateSha)) {
    return fail("CANONICALIZATION_FAILED", "terminal audit candidate could not be canonicalized")
  }
  return Either.right(frozen({
    normalizedHistoryInputBoundary: HSWM_G0_TEMPORAL_NORMALIZED_HISTORY_INPUT_BOUNDARY,
    history,
    historyBytes: historyBytes.right,
    historySha256: historySha.right,
    candidate,
    candidateBytes: candidateBytes.right,
    candidateSha256: candidateSha.right,
    externalAuditReceiptClaimed: false,
    independentAuditClaimed: false,
    scientificEvidenceClaimed: false,
    g0Passed: false
  }))
}

/** Pure, read-only Effect facade. No fetcher, signer, or verifier is supplied. */
export const exportG0TemporalTerminalAuditCandidate = (
  input: unknown
): Effect.Effect<G0TemporalTerminalAuditCandidateExport, G0TemporalAuditCandidateError> => {
  const result = exportEither(input)
  return Either.isLeft(result) ? Effect.fail(result.left) : Effect.succeed(result.right)
}
