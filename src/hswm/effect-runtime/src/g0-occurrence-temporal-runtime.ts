/**
 * Effect boundary around the official Temporal TypeScript SDK.
 *
 * Callers supply already-created Temporal clients/connections. This module
 * accepts no credentials, private holdout, OSF material, or canonical-write
 * capability. Workflow input contains content digests only.
 */
import {
  WorkflowIdConflictPolicy,
  WorkflowIdReusePolicy
} from "@temporalio/common"
import type {
  WorkflowClient,
  WorkflowHandle,
  WorkflowHandleWithStartDetails
} from "@temporalio/client"
import { NativeConnection, Worker } from "@temporalio/worker"
import { Data, Effect, Either } from "effect"

import { hswm_g0_occurrence_validate_transition } from "./g0-occurrence-temporal-activities.js"
import {
  HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
  HSWM_G0_TEMPORAL_SIGNAL_NAME,
  HSWM_G0_TEMPORAL_LIVE_ADMISSION_STATUS,
  HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
  HSWM_G0_TEMPORAL_WORKFLOW_TYPE,
  type G0TemporalAuthoritativeStartV1,
  type G0TemporalExecutionClassification,
  type G0TemporalWorkflowResultV1
} from "./g0-occurrence-temporal-contract.js"
import {
  decodeG0OccurrenceTemporalStartWire,
  decodeG0OccurrenceTemporalTransitionWire,
  decodeG0OccurrenceTemporalWorkerConfigurationWire,
  type G0OccurrenceTemporalWorkerConfiguration
} from "./g0-occurrence-temporal-wire.js"

export const HSWM_G0_TEMPORAL_TERMINAL_CLOSE_GRACE_SECONDS = 60 as const
export const HSWM_G0_TEMPORAL_WORKFLOW_TASK_TIMEOUT_SECONDS = 10 as const

type G0TemporalWorkflow = (input: unknown) => Promise<G0TemporalWorkflowResultV1>
export type G0TemporalWorkflowHandle = WorkflowHandle<G0TemporalWorkflow>
export type G0TemporalWorkflowStartHandle = WorkflowHandleWithStartDetails<G0TemporalWorkflow>

export interface G0TemporalOperatorStartRequest {
  readonly occurrence: unknown
  readonly executionClassification: G0TemporalExecutionClassification
  readonly operatorQualificationReceiptSha256: string
}

export interface G0TemporalOneShotStartPlan {
  readonly authoritySchemaVersion: typeof HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1
  readonly workflowType: typeof HSWM_G0_TEMPORAL_WORKFLOW_TYPE
  readonly workflowId: string
  readonly taskQueue: string
  readonly workflowIdReusePolicy: "REJECT_DUPLICATE"
  readonly workflowIdConflictPolicy: "FAIL"
  readonly workflowMaximumAttempts: 1
  readonly activityMaximumAttempts: 1
  readonly replacementRoundAllowed: false
  readonly occurrenceTimeoutSeconds: number
  readonly terminalCloseGraceSeconds: typeof HSWM_G0_TEMPORAL_TERMINAL_CLOSE_GRACE_SECONDS
  readonly executionTimeoutSeconds: number
  readonly workflowTaskTimeoutSeconds: typeof HSWM_G0_TEMPORAL_WORKFLOW_TASK_TIMEOUT_SECONDS
  readonly postStartEvidence: "SIGNAL_ONLY_NOT_PRELOADED"
  readonly credentialsAccepted: false
  readonly publicationEligible: false
  readonly g0Passed: false
  readonly startInput: G0TemporalAuthoritativeStartV1
}

export class G0TemporalRuntimeError extends Data.TaggedError("G0TemporalRuntimeError")<{
  readonly reason:
    | "CONFIG_INVALID"
    | "START_INVALID"
    | "LIVE_ADMISSION_BLOCKED"
    | "SIGNAL_INVALID"
    | "TEMPORAL_START_FAILED"
    | "TEMPORAL_SIGNAL_FAILED"
    | "WORKER_FAILED"
  readonly detail: string
}> {}

const runtimeError = (
  reason: G0TemporalRuntimeError["reason"],
  detail: string
): G0TemporalRuntimeError => new G0TemporalRuntimeError({ reason, detail })

const digestPattern = /^[0-9a-f]{64}(?![\s\S])/u

const exactStartRequest = (input: unknown): input is G0TemporalOperatorStartRequest => {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return false
  const raw = input as Readonly<Record<string, unknown>>
  const keys = Object.keys(raw)
  return keys.length === 3 &&
    keys.every((key) => [
      "occurrence",
      "executionClassification",
      "operatorQualificationReceiptSha256"
    ].includes(key)) &&
    (raw["executionClassification"] === "LIVE_EXTERNAL_OPERATOR" ||
      raw["executionClassification"] === "SIMULATED_OPERATOR_REHEARSAL") &&
    typeof raw["operatorQualificationReceiptSha256"] === "string" &&
    digestPattern.test(raw["operatorQualificationReceiptSha256"])
}

export const buildG0TemporalOneShotStartPlan = (
  rawConfiguration: unknown,
  rawRequest: unknown
): Either.Either<G0TemporalOneShotStartPlan, G0TemporalRuntimeError> => {
  const configuration = decodeG0OccurrenceTemporalWorkerConfigurationWire(rawConfiguration)
  if (Either.isLeft(configuration)) {
    return Either.left(runtimeError("CONFIG_INVALID", configuration.left.detail))
  }
  if (!exactStartRequest(rawRequest)) {
    return Either.left(runtimeError("START_INVALID", "operator start request is not an exact descriptor-only shape"))
  }
  if (rawRequest.executionClassification === "LIVE_EXTERNAL_OPERATOR") {
    return Either.left(runtimeError(
      "LIVE_ADMISSION_BLOCKED",
      HSWM_G0_TEMPORAL_LIVE_ADMISSION_STATUS
    ))
  }
  const occurrence = decodeG0OccurrenceTemporalStartWire(rawRequest.occurrence)
  if (Either.isLeft(occurrence)) {
    return Either.left(runtimeError("START_INVALID", occurrence.left.detail))
  }
  const qualification = rawRequest.operatorQualificationReceiptSha256
  const binding = configuration.right.signalAuthorizationBindingSha256
  if (
    qualification === binding ||
    qualification === occurrence.right.registrationEvidence.sha256 ||
    qualification === occurrence.right.wormClaimReceipt.sha256
  ) {
    return Either.left(runtimeError("START_INVALID", "qualification, policy, and evidence digests must be role-separated"))
  }
  const timeout = occurrence.right.occurrenceTimeoutSeconds
  return Either.right(Object.freeze({
    authoritySchemaVersion: HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
    workflowType: HSWM_G0_TEMPORAL_WORKFLOW_TYPE,
    workflowId: `g0-occurrence/${occurrence.right.occurrenceUid}`,
    taskQueue: configuration.right.taskQueue,
    workflowIdReusePolicy: "REJECT_DUPLICATE",
    workflowIdConflictPolicy: "FAIL",
    workflowMaximumAttempts: 1,
    activityMaximumAttempts: 1,
    replacementRoundAllowed: false,
    occurrenceTimeoutSeconds: timeout,
    terminalCloseGraceSeconds: HSWM_G0_TEMPORAL_TERMINAL_CLOSE_GRACE_SECONDS,
    executionTimeoutSeconds: timeout + HSWM_G0_TEMPORAL_TERMINAL_CLOSE_GRACE_SECONDS,
    workflowTaskTimeoutSeconds: HSWM_G0_TEMPORAL_WORKFLOW_TASK_TIMEOUT_SECONDS,
    postStartEvidence: "SIGNAL_ONLY_NOT_PRELOADED",
    credentialsAccepted: false,
    publicationEligible: false,
    g0Passed: false,
    startInput: Object.freeze({
      schema_version: HSWM_G0_TEMPORAL_TYPESCRIPT_AUTHORITY_V1,
      occurrence: rawRequest.occurrence,
      execution_classification: rawRequest.executionClassification,
      operator_qualification_receipt_sha256: qualification,
      signal_authorization_binding_sha256: binding
    })
  }))
}

export const startG0TemporalOneShot = (
  client: WorkflowClient,
  rawConfiguration: unknown,
  rawRequest: unknown
): Effect.Effect<G0TemporalWorkflowStartHandle, G0TemporalRuntimeError> => {
  const plan = buildG0TemporalOneShotStartPlan(rawConfiguration, rawRequest)
  if (Either.isLeft(plan)) return Effect.fail(plan.left)
  return Effect.tryPromise({
    try: () => client.start<G0TemporalWorkflow>(HSWM_G0_TEMPORAL_WORKFLOW_TYPE, {
      args: [plan.right.startInput],
      taskQueue: plan.right.taskQueue,
      workflowId: plan.right.workflowId,
      workflowIdReusePolicy: WorkflowIdReusePolicy.REJECT_DUPLICATE,
      workflowIdConflictPolicy: WorkflowIdConflictPolicy.FAIL,
      retry: { maximumAttempts: 1 },
      workflowExecutionTimeout: plan.right.executionTimeoutSeconds * 1_000,
      workflowRunTimeout: plan.right.executionTimeoutSeconds * 1_000,
      workflowTaskTimeout: plan.right.workflowTaskTimeoutSeconds * 1_000
    }),
    catch: () => runtimeError("TEMPORAL_START_FAILED", "Temporal refused the one-shot workflow start")
  })
}

export const signalG0TemporalOneShot = (
  handle: G0TemporalWorkflowHandle,
  signalAuthorizationBindingSha256: unknown,
  rawTransition: unknown
): Effect.Effect<void, G0TemporalRuntimeError> => {
  const transition = decodeG0OccurrenceTemporalTransitionWire(rawTransition)
  if (
    typeof signalAuthorizationBindingSha256 !== "string" ||
    !digestPattern.test(signalAuthorizationBindingSha256) ||
    Either.isLeft(transition)
  ) return Effect.fail(runtimeError("SIGNAL_INVALID", "signal is not an exact policy-bound transition"))
  return Effect.tryPromise({
    try: () => handle.signal(HSWM_G0_TEMPORAL_SIGNAL_NAME, {
      schema_version: HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
      signal_authorization_binding_sha256: signalAuthorizationBindingSha256,
      transition: rawTransition
    }),
    catch: () => runtimeError("TEMPORAL_SIGNAL_FAILED", "Temporal refused the occurrence signal")
  })
}

export const createG0TemporalWorker = (
  rawConfiguration: unknown,
  workflowsPath: string,
  connection: NativeConnection
): Effect.Effect<Worker, G0TemporalRuntimeError> => {
  const configuration = decodeG0OccurrenceTemporalWorkerConfigurationWire(rawConfiguration)
  if (Either.isLeft(configuration)) {
    return Effect.fail(runtimeError("CONFIG_INVALID", configuration.left.detail))
  }
  return Effect.tryPromise({
    try: () => Worker.create({
      connection,
      namespace: configuration.right.namespace,
      taskQueue: configuration.right.taskQueue,
      workflowsPath,
      activities: { hswm_g0_occurrence_validate_transition }
    }),
    catch: () => runtimeError("WORKER_FAILED", "Temporal worker construction failed")
  })
}

const isLoopbackAddress = (address: string): boolean =>
  /^(?:127(?:\.[0-9]{1,3}){3}|localhost|\[::1\]):[0-9]{1,5}(?![\s\S])/u.test(address)

/** Plaintext local runner for disposable rehearsal only; never a hosted live deployment. */
export const runG0TemporalLocalRehearsalWorker = (
  rawConfiguration: unknown,
  workflowsPath: string
): Effect.Effect<never, G0TemporalRuntimeError> => {
  const configuration = decodeG0OccurrenceTemporalWorkerConfigurationWire(rawConfiguration)
  if (Either.isLeft(configuration)) {
    return Effect.fail(runtimeError("CONFIG_INVALID", configuration.left.detail))
  }
  if (!isLoopbackAddress(configuration.right.address)) {
    return Effect.fail(runtimeError(
      "CONFIG_INVALID",
      "local rehearsal worker requires an explicit loopback Temporal address"
    ))
  }
  return Effect.tryPromise({
    try: async () => {
      const connection = await NativeConnection.connect({ address: configuration.right.address })
      try {
        const worker = await Worker.create({
          connection,
          namespace: configuration.right.namespace,
          taskQueue: configuration.right.taskQueue,
          workflowsPath,
          activities: { hswm_g0_occurrence_validate_transition }
        })
        await worker.run()
        throw new Error("Temporal worker stopped without an explicit shutdown")
      } finally {
        await connection.close()
      }
    },
    catch: () => runtimeError("WORKER_FAILED", "Temporal worker connection or run failed")
  })
}

export type { G0OccurrenceTemporalWorkerConfiguration }
