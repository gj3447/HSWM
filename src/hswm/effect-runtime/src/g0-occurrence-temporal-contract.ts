/** Shared, runtime-neutral names and wire envelopes for G0 Temporal TS authority. */
import type { G0OccurrenceTemporalTerminalProjection } from "./g0-occurrence-temporal-wire.js"

export const HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1 =
  "hswm-g0-temporal-typescript-authority/v1" as const
export const HSWM_G0_TEMPORAL_WORKFLOW_TYPE =
  "hswm_g0_occurrence_one_shot_workflow" as const
export const HSWM_G0_TEMPORAL_SIGNAL_NAME = "submit_phase_transition" as const
export const HSWM_G0_TEMPORAL_STATE_QUERY_NAME = "read_g0_occurrence_state" as const
export const HSWM_G0_TEMPORAL_ACTIVITY_NAME =
  "hswm_g0_occurrence_validate_transition" as const
export const HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1 =
  "hswm-g0-occurrence-authorized-signal/v1" as const
export const HSWM_G0_TEMPORAL_CLAIM_BOUNDARY =
  "TYPESCRIPT_TEMPORAL_ORCHESTRATION_ONLY_EXTERNAL_QUALIFICATION_AND_SIGNAL_AUTHORIZATION_DECLARED_NOT_PROVEN_TERMINAL_NOT_G0_NOT_PUBLICATION_NOT_PERMIT_NOT_LEARNING" as const
export const HSWM_G0_TEMPORAL_LIVE_ADMISSION_STATUS =
  "BLOCKED_NO_QUALIFIED_AUTHENTICATED_EXTERNAL_INGRESS" as const

export type G0TemporalExecutionClassification =
  | "LIVE_EXTERNAL_OPERATOR"
  | "SIMULATED_OPERATOR_REHEARSAL"

export interface G0TemporalAuthoritativeStartV1 {
  readonly schema_version: typeof HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1
  readonly occurrence: unknown
  readonly execution_classification: G0TemporalExecutionClassification
  readonly operator_qualification_receipt_sha256: string
  readonly signal_authorization_binding_sha256: string
}

export interface G0TemporalAuthorizedSignalV1 {
  readonly schema_version: typeof HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1
  readonly signal_authorization_binding_sha256: string
  readonly transition: unknown
}

export interface G0TemporalWorkflowResultV1 extends G0OccurrenceTemporalTerminalProjection {
  readonly authority_schema_version: typeof HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1
  readonly workflow_type: typeof HSWM_G0_TEMPORAL_WORKFLOW_TYPE
  readonly execution_classification: G0TemporalExecutionClassification
  readonly operator_qualification_receipt_sha256: string
  readonly signal_authorization_binding_sha256: string
  readonly orchestration_authority: "TYPESCRIPT_TEMPORAL"
  readonly temporal_execution_observed: true
  readonly external_operator_qualification_claimed: false
  readonly scientific_evidence_claimed: false
  readonly g0_passed: false
  readonly claim_boundary: typeof HSWM_G0_TEMPORAL_CLAIM_BOUNDARY
}
