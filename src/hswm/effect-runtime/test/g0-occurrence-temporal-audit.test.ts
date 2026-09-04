import { expect, it } from "@effect/vitest"
import { Effect, Exit } from "effect"

import {
  exportG0TemporalTerminalAuditCandidate,
  HSWM_G0_TEMPORAL_AUDIT_CANDIDATE_CLAIM_BOUNDARY,
  HSWM_G0_TEMPORAL_HISTORY_EXPORT_V1,
  HSWM_G0_TEMPORAL_NORMALIZED_HISTORY_INPUT_BOUNDARY,
  HSWM_G0_TEMPORAL_TERMINAL_AUDIT_CANDIDATE_V1
} from "../src/g0-occurrence-temporal-audit.js"

const digest = (value: number): string => value.toString(16).padStart(64, "0")
const completedAt = "2026-09-04T12:01:00Z"

const startInput = () => ({
  schema_version: "hswm-g0-temporal-typescript-authority/v1",
  occurrence: {
    occurrence_uid: "future-outcome-ts-001",
    worm_claim_receipt: { name: "candidate_worm_claim_receipt", sha256: digest(1) },
    registration_evidence: { name: "registration_evidence", sha256: digest(2) },
    occurrence_timeout_seconds: 600
  },
  execution_classification: "SIMULATED_OPERATOR_REHEARSAL",
  operator_qualification_receipt_sha256: digest(3),
  signal_authorization_binding_sha256: digest(4)
} as const)

const terminalResult = () => ({
  schema_version: "hswm-g0-occurrence-temporal-worker/v1",
  occurrence_uid: "future-outcome-ts-001",
  phase: "SEALED",
  void_reason: null,
  rejected_evidence_sha256: null,
  evidence_sha256s: [digest(2), digest(1), digest(7)],
  terminal: true,
  completion_handshake_required: true,
  publication_eligible: false,
  g0_status: "NOT_EVIDENCE_BY_ITSELF",
  authority_schema_version: "hswm-g0-temporal-typescript-authority/v1",
  workflow_type: "hswm_g0_occurrence_one_shot_workflow",
  execution_classification: "SIMULATED_OPERATOR_REHEARSAL",
  operator_qualification_receipt_sha256: digest(3),
  signal_authorization_binding_sha256: digest(4),
  orchestration_authority: "TYPESCRIPT_TEMPORAL",
  temporal_execution_observed: true,
  external_operator_qualification_claimed: false,
  scientific_evidence_claimed: false,
  g0_passed: false,
  claim_boundary: "TYPESCRIPT_TEMPORAL_ORCHESTRATION_ONLY_EXTERNAL_QUALIFICATION_AND_SIGNAL_AUTHORIZATION_DECLARED_NOT_PROVEN_TERMINAL_NOT_G0_NOT_PUBLICATION_NOT_PERMIT_NOT_LEARNING"
} as const)

const input = () => ({
  history: {
    sourceApi: "temporal.api.workflowservice.v1.WorkflowService/GetWorkflowExecutionHistory",
    namespace: "g0-test",
    workflowId: "g0-occurrence/future-outcome-ts-001",
    runId: "123e4567-e89b-42d3-a456-426614174000",
    nextPageToken: "" as const,
    events: [
      {
        eventId: "1",
        eventType: "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED",
        eventTime: "2026-09-04T12:00:00Z",
        workflowExecutionStartedEventAttributes: {
          workflowType: { name: "hswm_g0_occurrence_one_shot_workflow" },
          hswmDecodedInput: startInput()
        }
      },
      {
        eventId: 2,
        eventType: "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
        eventTime: completedAt,
        workflowExecutionCompletedEventAttributes: { hswmDecodedResult: terminalResult() }
      }
    ]
  },
  serverIdentitySha256: digest(5),
  candidateReceiptSha256: digest(6),
  exporterIdentity: "test-exporter",
  retrievedAt: "2026-09-04T12:02:00Z"
})

it.effect("exports bound canonical history and an explicitly non-auditor candidate", () =>
  Effect.gen(function* () {
    const exported = yield* exportG0TemporalTerminalAuditCandidate(input())
    expect(exported.normalizedHistoryInputBoundary).toBe(HSWM_G0_TEMPORAL_NORMALIZED_HISTORY_INPUT_BOUNDARY)
    expect(exported.history.schema_version).toBe(HSWM_G0_TEMPORAL_HISTORY_EXPORT_V1)
    expect(JSON.parse(new TextDecoder().decode(exported.historyBytes))).toEqual(exported.history)
    expect(exported.candidate.schema_version).toBe(HSWM_G0_TEMPORAL_TERMINAL_AUDIT_CANDIDATE_V1)
    expect(exported.candidate.claim_boundary).toBe(HSWM_G0_TEMPORAL_AUDIT_CANDIDATE_CLAIM_BOUNDARY)
    expect(exported.candidate).toMatchObject({
      terminal_phase: "SEALED", workflow_id_reuse_policy: "REJECT_DUPLICATE",
      workflow_maximum_attempts: 1, activity_maximum_attempts: 1,
      replacement_round_allowed: false, completed_at: completedAt
    })
    expect(exported.externalAuditReceiptClaimed).toBe(false)
    expect(exported.independentAuditClaimed).toBe(false)
    expect(exported.scientificEvidenceClaimed).toBe(false)
    expect(exported.g0Passed).toBe(false)
    expect(exported.historySha256).toMatch(/^[0-9a-f]{64}$/u)
    expect(exported.candidateSha256).toMatch(/^[0-9a-f]{64}$/u)
  })
)

it.effect("refuses incomplete history and any start/completion/result mismatch", () =>
  Effect.gen(function* () {
    const base = input()
    const first = base.history.events[0]
    const last = base.history.events[1]
    for (const candidate of [
      { ...base, history: { ...base.history, nextPageToken: "unfinished" } },
      { ...base, history: { ...base.history, events: [{ ...first, eventId: 2 }, last] } },
      { ...base, history: { ...base.history, workflowId: "g0-occurrence/different" } },
      {
        ...base,
        history: {
          ...base.history,
          events: [first, {
            ...last,
            workflowExecutionCompletedEventAttributes: {
              hswmDecodedResult: { ...terminalResult(), occurrence_uid: "different" }
            }
          }]
        }
      },
      {
        ...base,
        history: {
          ...base.history,
          events: [{
            ...first,
            workflowExecutionStartedEventAttributes: {
              workflowType: { name: "hswm_g0_occurrence_one_shot_workflow" },
              hswmDecodedInput: { ...startInput(), execution_classification: "LIVE_EXTERNAL_OPERATOR" }
            }
          }, last]
        }
      },
      { ...base, retrievedAt: "2026-09-04T11:00:00Z" }
    ]) {
      const exit = yield* Effect.exit(exportG0TemporalTerminalAuditCandidate(candidate))
      expect(Exit.isFailure(exit)).toBe(true)
    }
  })
)
