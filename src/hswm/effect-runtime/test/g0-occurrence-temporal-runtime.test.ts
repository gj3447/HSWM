import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit } from "effect"

import { hswm_g0_occurrence_validate_transition } from "../src/g0-occurrence-temporal-activities.js"
import {
  HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
  HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1
} from "../src/g0-occurrence-temporal-contract.js"
import {
  buildG0TemporalOneShotStartPlan,
  runG0TemporalLocalRehearsalWorker,
  signalG0TemporalOneShot
} from "../src/g0-occurrence-temporal-runtime.js"
import * as TemporalPublic from "../src/g0-occurrence-temporal-public.js"

const digest = (value: number): string => value.toString(16).padStart(64, "0")

const configuration = () => ({
  address: "127.0.0.1:7233",
  namespace: "default",
  task_queue: "hswm-g0-typescript",
  signal_authorization_binding_sha256: digest(4)
})

const occurrence = () => ({
  occurrence_uid: "future-outcome-ts-001",
  worm_claim_receipt: { name: "candidate_worm_claim_receipt", sha256: digest(1) },
  registration_evidence: { name: "registration_evidence", sha256: digest(2) },
  occurrence_timeout_seconds: 600
})

const transition = () => ({
  next_phase: "SCHEDULED",
  evidence: { name: "scheduled_evidence", sha256: digest(5) },
  timing: "PRE_PULSE"
})

it("builds the exact duplicate-rejecting TypeScript Temporal start plan", () => {
  const result = buildG0TemporalOneShotStartPlan(configuration(), {
    occurrence: occurrence(),
    executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
    operatorQualificationReceiptSha256: digest(3)
  })
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) return
  expect(result.right).toMatchObject({
    authoritySchemaVersion: HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
    workflowType: "hswm_g0_occurrence_one_shot_workflow",
    workflowId: "g0-occurrence/future-outcome-ts-001",
    workflowIdReusePolicy: "REJECT_DUPLICATE",
    workflowIdConflictPolicy: "FAIL",
    workflowMaximumAttempts: 1,
    activityMaximumAttempts: 1,
    replacementRoundAllowed: false,
    occurrenceTimeoutSeconds: 600,
    terminalCloseGraceSeconds: 60,
    executionTimeoutSeconds: 660,
    workflowTaskTimeoutSeconds: 10,
    postStartEvidence: "SIGNAL_ONLY_NOT_PRELOADED",
    credentialsAccepted: false,
    publicationEligible: false,
    g0Passed: false
  })
  expect(result.right.startInput).toEqual({
    schema_version: HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
    occurrence: occurrence(),
    execution_classification: "SIMULATED_OPERATOR_REHEARSAL",
    operator_qualification_receipt_sha256: digest(3),
    signal_authorization_binding_sha256: digest(4)
  })
  expect(JSON.stringify(result.right)).not.toContain("forbidden")
  expect(Object.isFrozen(result.right)).toBe(true)
})

it("refuses excess start authority and cross-role digest collisions", () => {
  expect(Either.isLeft(buildG0TemporalOneShotStartPlan(configuration(), {
    occurrence: occurrence(),
    executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
    operatorQualificationReceiptSha256: digest(3),
    endpoint: "forbidden"
  }))).toBe(true)
  expect(Either.isLeft(buildG0TemporalOneShotStartPlan(configuration(), {
    occurrence: occurrence(),
    executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
    operatorQualificationReceiptSha256: digest(4)
  }))).toBe(true)
  const live = buildG0TemporalOneShotStartPlan(configuration(), {
    occurrence: occurrence(),
    executionClassification: "LIVE_EXTERNAL_OPERATOR",
    operatorQualificationReceiptSha256: digest(3)
  })
  expect(Either.isLeft(live)).toBe(true)
  if (Either.isLeft(live)) expect(live.left.reason).toBe("LIVE_ADMISSION_BLOCKED")
})

it("validates transition activity wire with one deterministic result shape", async () => {
  await expect(hswm_g0_occurrence_validate_transition(transition())).resolves.toEqual({
    accepted: true,
    transition: {
      nextPhase: "SCHEDULED",
      evidence: {
        name: "scheduled_evidence",
        sha256: digest(5),
        mediaType: "application/vnd.hswm.content-descriptor+json"
      },
      timing: "PRE_PULSE"
    }
  })
  await expect(hswm_g0_occurrence_validate_transition({
    ...transition(),
    credential: "forbidden"
  })).resolves.toEqual({ accepted: false, transition: null })
})

it.effect("refuses malformed signals before contacting a Temporal handle", () =>
  Effect.gen(function* () {
    let called = false
    const handle = {
      signal: () => {
        called = true
        return Promise.resolve()
      }
    }
    const result = yield* signalG0TemporalOneShot(
      handle as never,
      "not-a-digest",
      transition()
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    expect(called).toBe(false)
  })
)

it.effect("refuses a non-loopback address in the plaintext rehearsal runner", () =>
  Effect.gen(function* () {
    const exit = yield* Effect.exit(runG0TemporalLocalRehearsalWorker({
      ...configuration(),
      address: "temporal.example.invalid:7233"
    }, "/unused/workflows.js"))
    expect(Exit.isFailure(exit)).toBe(true)
  })
)

it("keeps the signal envelope version explicit", () => {
  expect(HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1).toBe(
    "hswm-g0-occurrence-authorized-signal/v1"
  )
  expect(TemporalPublic.HSWM_G0_TEMPORAL_LIVE_ADMISSION_STATUS).toBe(
    "BLOCKED_NO_QUALIFIED_AUTHENTICATED_EXTERNAL_INGRESS"
  )
  expect(typeof TemporalPublic.startG0TemporalOneShot).toBe("function")
  expect(typeof TemporalPublic.exportG0TemporalTerminalAuditCandidate).toBe("function")
  expect("simulateG0TestOnlyOperator" in TemporalPublic).toBe(false)
  expect("runG0TemporalLocalRehearsalWorker" in TemporalPublic).toBe(false)
})
