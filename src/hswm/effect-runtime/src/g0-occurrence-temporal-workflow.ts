/**
 * Authoritative TypeScript Temporal orchestration for a future G0 occurrence.
 *
 * Temporal history is the durable orchestration source. External OSF, WORM,
 * Sigstore, RFC3161, drand, custody, evaluation, and completion-audit facts are
 * still supplied only as content-addressed evidence. A terminal workflow is
 * not G0 and is never publication eligibility by itself.
 */
import {
  ApplicationFailure,
  condition,
  defineQuery,
  defineSignal,
  proxyActivities,
  setHandler
} from "@temporalio/workflow"

import {
  advanceG0TemporalDomain,
  decodeG0TemporalDomainStart,
  decodeG0TemporalDomainTransition,
  registeredG0TemporalDomain,
  voidG0TemporalDomain,
  type G0TemporalDomainStart,
  type G0TemporalDomainState
} from "./g0-occurrence-temporal-domain.js"
import type { G0OccurrenceTransitionActivityResult } from "./g0-occurrence-temporal-activities.js"
import {
  HSWM_G0_TEMPORAL_CLAIM_BOUNDARY,
  HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
  HSWM_G0_TEMPORAL_SIGNAL_NAME,
  HSWM_G0_TEMPORAL_STATE_QUERY_NAME,
  HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
  HSWM_G0_TEMPORAL_WORKFLOW_TYPE,
  type G0TemporalExecutionClassification,
  type G0TemporalWorkflowResultV1
} from "./g0-occurrence-temporal-contract.js"
interface G0OccurrenceActivities {
  readonly hswm_g0_occurrence_validate_transition: (
    value: unknown
  ) => Promise<G0OccurrenceTransitionActivityResult>
}

interface AcceptedStart {
  readonly occurrence: G0TemporalDomainStart
  readonly executionClassification: G0TemporalExecutionClassification
  readonly operatorQualificationReceiptSha256: string
  readonly signalAuthorizationBindingSha256: string
}

interface QueuedSignal {
  readonly acceptedEnvelope: boolean
  readonly transition: unknown
}

const digestPattern = /^[0-9a-f]{64}(?![\s\S])/u
const maximumPendingSignals = 8 as const

const validateTransition = proxyActivities<G0OccurrenceActivities>({
  startToCloseTimeout: "30 seconds",
  retry: { maximumAttempts: 1 }
}).hswm_g0_occurrence_validate_transition

export const submitG0OccurrenceTransition =
  defineSignal<[unknown]>(HSWM_G0_TEMPORAL_SIGNAL_NAME)
export const readG0OccurrenceState =
  defineQuery<G0TemporalWorkflowResultV1>(HSWM_G0_TEMPORAL_STATE_QUERY_NAME)

const isExactObject = (input: unknown, keys: ReadonlyArray<string>): input is Readonly<Record<string, unknown>> => {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return false
  const actual = Object.keys(input)
  return actual.length === keys.length && actual.every((key) => keys.includes(key))
}

const decodeStart = (input: unknown): AcceptedStart | null => {
  if (!isExactObject(input, [
    "schema_version",
    "occurrence",
    "execution_classification",
    "operator_qualification_receipt_sha256",
    "signal_authorization_binding_sha256"
  ])) return null
  if (input["schema_version"] !== HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1) return null
  const classification = input["execution_classification"]
  // LIVE_EXTERNAL_OPERATOR is reserved by the versioned contract, but this
  // build has no qualified authenticated ingress capable of issuing it. Keep
  // the refusal inside replayed workflow code so a raw SDK start cannot bypass
  // the client adapter's admission gate.
  if (classification !== "SIMULATED_OPERATOR_REHEARSAL") return null
  const qualification = input["operator_qualification_receipt_sha256"]
  const signalBinding = input["signal_authorization_binding_sha256"]
  if (
    typeof qualification !== "string" ||
    typeof signalBinding !== "string" ||
    !digestPattern.test(qualification) ||
    !digestPattern.test(signalBinding) ||
    qualification === signalBinding
  ) return null
  const occurrence = decodeG0TemporalDomainStart(input["occurrence"])
  if (!occurrence.ok) return null
  if (
    occurrence.value.registrationEvidence.sha256 === qualification ||
    occurrence.value.registrationEvidence.sha256 === signalBinding ||
    occurrence.value.wormClaimReceipt.sha256 === qualification ||
    occurrence.value.wormClaimReceipt.sha256 === signalBinding
  ) return null
  return Object.freeze({
    occurrence: occurrence.value,
    executionClassification: classification,
    operatorQualificationReceiptSha256: qualification,
    signalAuthorizationBindingSha256: signalBinding
  })
}

const decodeSignalEnvelope = (
  input: unknown,
  expectedBinding: string
): QueuedSignal => {
  if (!isExactObject(input, ["schema_version", "signal_authorization_binding_sha256", "transition"])) {
    return Object.freeze({ acceptedEnvelope: false, transition: null })
  }
  if (
    input["schema_version"] !== HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1 ||
    input["signal_authorization_binding_sha256"] !== expectedBinding
  ) return Object.freeze({ acceptedEnvelope: false, transition: null })
  return Object.freeze({ acceptedEnvelope: true, transition: input["transition"] })
}

const terminal = (
  state: G0TemporalDomainState,
  accepted: AcceptedStart
): G0TemporalWorkflowResultV1 => Object.freeze({
  schema_version: "hswm-g0-occurrence-temporal-worker/v1",
  occurrence_uid: state.occurrenceUid,
  phase: state.phase,
  void_reason: state.voidReason,
  rejected_evidence_sha256: state.rejectedEvidenceSha256,
  evidence_sha256s: Object.freeze([...state.evidenceSha256s]),
  terminal: state.terminal,
  completion_handshake_required: true,
  publication_eligible: false,
  g0_status: "NOT_EVIDENCE_BY_ITSELF",
  authority_schema_version: HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
  workflow_type: HSWM_G0_TEMPORAL_WORKFLOW_TYPE,
  execution_classification: accepted.executionClassification,
  operator_qualification_receipt_sha256: accepted.operatorQualificationReceiptSha256,
  signal_authorization_binding_sha256: accepted.signalAuthorizationBindingSha256,
  orchestration_authority: "TYPESCRIPT_TEMPORAL",
  temporal_execution_observed: true,
  external_operator_qualification_claimed: false,
  scientific_evidence_claimed: false,
  g0_passed: false,
  claim_boundary: HSWM_G0_TEMPORAL_CLAIM_BOUNDARY
})

const explicitVoid = (
  state: G0TemporalDomainState,
  reason: "LATE" | "INVALID_EVIDENCE_DESCRIPTOR" | "TERMINAL_REENTRY",
  rejectedDigest: string | null = null
): G0TemporalDomainState => {
  const result = voidG0TemporalDomain(state, reason, rejectedDigest)
  if (!result.ok) {
    throw ApplicationFailure.nonRetryable(result.detail, "G0_STATE_INVALID")
  }
  return result.value
}

const rejectedDigest = (queued: ReadonlyArray<QueuedSignal>): string | null => {
  const first = queued[0]
  if (first === undefined || !first.acceptedEnvelope) return null
  const decoded = decodeG0TemporalDomainTransition(first.transition)
  return decoded.ok ? decoded.value.evidence.sha256 : null
}

/**
 * The export name intentionally preserves the fixed Python-v1 workflow type.
 * Existing live histories do not exist; a future deployment must still replay
 * its own pre-production history before this worker is admitted.
 */
export async function hswm_g0_occurrence_one_shot_workflow(
  rawInput: unknown
): Promise<G0TemporalWorkflowResultV1> {
  const accepted = decodeStart(rawInput)
  if (accepted === null) {
    throw ApplicationFailure.nonRetryable(
      "G0 Temporal start input is not an exact admitted descriptor-only shape",
      "G0_OCCURRENCE_INPUT_INVALID"
    )
  }

  const registered = registeredG0TemporalDomain(accepted.occurrence)
  const claimed = advanceG0TemporalDomain(registered, {
    nextPhase: "CLAIMED",
    evidence: accepted.occurrence.wormClaimReceipt,
    timing: "PRE_PULSE"
  })
  if (!claimed.ok) {
    throw ApplicationFailure.nonRetryable(claimed.detail, "G0_STATE_INVALID")
  }

  let state = claimed.value
  const pending: QueuedSignal[] = []
  let signalOverflow = false
  const deadline = Date.now() + accepted.occurrence.occurrenceTimeoutSeconds * 1_000

  setHandler(submitG0OccurrenceTransition, (rawSignal) => {
    if (pending.length >= maximumPendingSignals) {
      signalOverflow = true
      return
    }
    pending.push(decodeSignalEnvelope(rawSignal, accepted.signalAuthorizationBindingSha256))
  })
  setHandler(readG0OccurrenceState, () => terminal(state, accepted))

  while (!state.terminal) {
    const remaining = deadline - Date.now()
    if (remaining <= 0) {
      state = explicitVoid(state, "LATE")
      break
    }
    const ready = await condition(() => pending.length > 0, remaining)
    if (!ready) {
      state = explicitVoid(state, "LATE")
      break
    }
    const requested = pending.shift()
    if (requested === undefined || !requested.acceptedEnvelope) {
      state = explicitVoid(state, "INVALID_EVIDENCE_DESCRIPTOR")
      continue
    }
    let activityResult: G0OccurrenceTransitionActivityResult
    try {
      activityResult = await validateTransition(requested.transition)
    } catch {
      state = explicitVoid(state, "INVALID_EVIDENCE_DESCRIPTOR")
      continue
    }
    // Unlike the retired Python adapter, do not admit an activity result that
    // arrived after the committed occurrence deadline.
    if (Date.now() >= deadline) {
      state = explicitVoid(state, "LATE")
      continue
    }
    if (!activityResult.accepted || activityResult.transition === null) {
      state = explicitVoid(state, "INVALID_EVIDENCE_DESCRIPTOR")
      continue
    }
    const advanced = advanceG0TemporalDomain(state, activityResult.transition)
    if (!advanced.ok) {
      throw ApplicationFailure.nonRetryable(advanced.detail, "G0_STATE_INVALID")
    }
    state = advanced.value
  }

  if (state.phase === "SEALED" && (pending.length > 0 || signalOverflow)) {
    state = explicitVoid(state, "TERMINAL_REENTRY", rejectedDigest(pending))
  }
  return terminal(state, accepted)
}
