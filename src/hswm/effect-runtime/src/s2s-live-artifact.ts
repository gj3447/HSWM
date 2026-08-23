import { Context, Data, Effect, Either, Layer, Schema } from "effect"

import { canonicalS2SControlSha256 } from "./s2s-canonical.js"
import {
  S2SArtifactEvidenceSchema,
  S2S_CONFIRMATORY_POLICY,
  S2SSha256Schema,
  type S2SArtifactEvidence
} from "./s2s-confirmatory.js"
import {
  S2S_GITHUB_JSON_MAX_BYTES,
  S2SGitHubObserver,
  S2SGitHubObserverLive,
  makeS2SGitHubHttpTransportLiveLayer,
  validateS2SGitHubArtifactDownload,
  validateS2SGitHubArtifactObservation,
  validateS2SGitHubRunArtifactsObservation,
  validateS2SGitHubWorkflowAttemptJobsObservation,
  validateS2SGitHubWorkflowRunObservation,
  type S2SGitHubArtifactDownload,
  type S2SGitHubArtifactProjection,
  type S2SGitHubArtifactsProjection,
  type S2SGitHubLiveTransportConfig,
  type S2SGitHubObservation,
  type S2SGitHubWorkflowJobProjection,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection
} from "./s2s-live-github.js"
import {
  S2SCurrentRunStage,
  makeS2SCurrentRunStageAuthorityLiveLayer
} from "./s2s-run-authority.js"
import { S2S_NUMERIC_ADJUDICATION_MAX_BYTES } from "./s2s-live-python.js"
import {
  appendS2SStageArtifactLedgerEntry,
  claimS2SStageArtifactPermitScope,
  closeS2SStageArtifactPermitScope,
  makeS2SStageArtifactPermitTestScope,
  snapshotS2SStageArtifactPermitEvidence,
  useS2SStageArtifactPermit,
  type S2SStageArtifactLedgerPhase,
  type S2SStageArtifactPermitEvidence,
  type S2SStageArtifactPermitIdentity,
  type S2SStageArtifactPermitScope,
  type S2SStageArtifactPermitTestSeed
} from "./s2s-stage-artifact-permits.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_EVENT,
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_NAME,
  type S2SConfirmatoryArtifactReadOperation,
  type S2SConfirmatoryArtifactRole,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"
import {
  validateS2SArtifactZip,
  type S2SArtifactZipValidationError,
  type S2SExpectedZipMember,
  type S2SValidatedArtifactZip
} from "./s2s-zip.js"

export { S2SStageArtifactPermitError } from "./s2s-stage-artifact-permits.js"

export type S2SArtifactRole = S2SConfirmatoryArtifactRole

export const S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-artifact-successful-lookup-trace/v1" as const
/** Initial run + jobs + at most three artifacts/run observation pairs. */
export const S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES =
  8 * S2S_GITHUB_JSON_MAX_BYTES

interface RolePolicy {
  readonly jobName: string
  readonly artifactName: string
  readonly maximumArchiveBytes: number
  readonly maximumExpandedBytes: number
  readonly expectedMembers: ReadonlyArray<S2SExpectedZipMember>
}

const ROLE_POLICY: Readonly<Record<S2SArtifactRole, RolePolicy>> = Object.freeze({
  REGISTRATION: Object.freeze({
    jobName: S2S_CONFIRMATORY_STAGE_CONTRACTS.REGISTER.jobName,
    artifactName:
      S2S_CONFIRMATORY_STAGE_CONTRACTS.REGISTER.producesArtifactName,
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    expectedMembers: Object.freeze([
      Object.freeze({ name: "control_receipt.json", maximumBytes: 1_048_576 })
    ])
  }),
  CANDIDATE: Object.freeze({
    jobName: S2S_CONFIRMATORY_STAGE_CONTRACTS.CONFIRM.jobName,
    artifactName: S2S_CONFIRMATORY_STAGE_CONTRACTS.CONFIRM.producesArtifactName,
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes,
    expectedMembers: Object.freeze([
      Object.freeze({ name: "control_receipt.json", maximumBytes: 1_048_576 }),
      Object.freeze({
        name: "numeric_candidate.json",
        maximumBytes: S2S_CONFIRMATORY_POLICY.archive.candidateMemberMaximumBytes
      })
    ])
  }),
  ADJUDICATION: Object.freeze({
    jobName: S2S_CONFIRMATORY_STAGE_CONTRACTS.ADJUDICATE.jobName,
    artifactName:
      S2S_CONFIRMATORY_STAGE_CONTRACTS.ADJUDICATE.producesArtifactName,
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
    expectedMembers: Object.freeze([
      Object.freeze({ name: "control_receipt.json", maximumBytes: 1_048_576 }),
      Object.freeze({
        name: "numeric_adjudication.json",
        maximumBytes: S2S_NUMERIC_ADJUDICATION_MAX_BYTES
      })
    ])
  })
})

export type S2SArtifactLookupAmbiguity =
  | "ABSENCE_RECONCILIATION_NOT_CANONICAL"
  | "ABSENCE_OBSERVATIONS_NOT_DISTINCT"
  | "ABSENCE_OBSERVATIONS_TOO_CLOSE"
  | "ARTIFACT_NOT_OBSERVED"
  | "ARTIFACT_EXPIRED"
  | "ARTIFACT_OUTSIDE_PRODUCER_INTERVAL"
  | "DUPLICATE_ARTIFACT_NAME"
  | "HEAD_SHA_MISMATCH"
  | "OBSERVATION_ORDER_INVALID"
  | "OBSERVATION_PRECEDES_JOB_COMPLETION"
  | "PRODUCER_JOB_NOT_COMPLETED"
  | "PRODUCER_JOB_NOT_FOUND"
  | "PRODUCER_JOB_IDENTITY_DRIFT"
  | "WORKFLOW_RUN_DID_NOT_SUCCEED"

export interface S2SArtifactObservationUnavailable {
  readonly _tag: "ObservationUnavailable"
  readonly role: S2SArtifactRole
  readonly operation:
    | "OBSERVE_RUN"
    | "OBSERVE_JOBS"
    | "OBSERVE_ARTIFACTS"
    | "REVALIDATE_RUN"
    | "REVALIDATE_JOBS"
    | "REVALIDATE_ARTIFACTS"
  readonly errorTag: string
  readonly errorReason: string
}

export interface S2SArtifactProducerDidNotSucceed {
  readonly _tag: "ProducerDidNotCompleteSuccessfully"
  readonly role: S2SArtifactRole
  readonly producerJobId: number
  readonly status: string
  readonly conclusion: string | null
  readonly initialWorkflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowJobsObservation: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly artifactsObservation: S2SGitHubObservation<S2SGitHubArtifactsProjection>
}

export interface S2SArtifactAbsenceObservationPair {
  readonly artifactsObservation: S2SGitHubObservation<S2SGitHubArtifactsProjection>
  readonly workflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
}

export interface S2SArtifactLookupAttempt<
  Ordinal extends 1 | 2 | 3 = 1 | 2 | 3,
  Classification extends
    | "ARTIFACT_NOT_OBSERVED"
    | "ARTIFACT_OBSERVED" = "ARTIFACT_NOT_OBSERVED" | "ARTIFACT_OBSERVED"
> {
  readonly ordinal: Ordinal
  readonly classification: Classification
  readonly artifactsObservation: S2SGitHubObservation<S2SGitHubArtifactsProjection>
  readonly workflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
}

interface S2SArtifactSuccessfulLookupTraceBase {
  readonly schemaVersion: typeof S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION
  readonly initialWorkflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowJobsObservation: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly totalRawBodyByteLength: number
}

export type S2SArtifactSuccessfulLookupTrace =
  | (S2SArtifactSuccessfulLookupTraceBase & {
      readonly successfulAttemptOrdinal: 1
      readonly attempts: readonly [
        S2SArtifactLookupAttempt<1, "ARTIFACT_OBSERVED">
      ]
    })
  | (S2SArtifactSuccessfulLookupTraceBase & {
      readonly successfulAttemptOrdinal: 2
      readonly attempts: readonly [
        S2SArtifactLookupAttempt<1, "ARTIFACT_NOT_OBSERVED">,
        S2SArtifactLookupAttempt<2, "ARTIFACT_OBSERVED">
      ]
    })
  | (S2SArtifactSuccessfulLookupTraceBase & {
      readonly successfulAttemptOrdinal: 3
      readonly attempts: readonly [
        S2SArtifactLookupAttempt<1, "ARTIFACT_NOT_OBSERVED">,
        S2SArtifactLookupAttempt<2, "ARTIFACT_NOT_OBSERVED">,
        S2SArtifactLookupAttempt<3, "ARTIFACT_OBSERVED">
      ]
    })

export interface S2SArtifactAbsenceReconciliationReceipt {
  readonly schemaVersion: "hswm-swm0w-s2s-artifact-absence-reconciliation/v3"
  readonly classification: "RECONCILED_ABSENCE_NOT_PROOF"
  readonly observationCount: 3
  readonly minimumGapSeconds: 10
  readonly role: S2SArtifactRole
  readonly workflowRunId: number
  readonly expectedHeadSha: string
  readonly producerJobId: number
  readonly expectedArtifactName: string
  readonly initialWorkflowRunObservationReceiptSha256: string
  readonly workflowJobsObservationReceiptSha256: string
  readonly absenceArtifactObservationReceiptSha256s: readonly [string, string, string]
  readonly absenceRunObservationReceiptSha256s: readonly [string, string, string]
  readonly receiptSha256: string
}

export interface S2SArtifactReconciledAbsence {
  readonly _tag: "ReconciledAbsentAfterProducerCompleted"
  readonly role: S2SArtifactRole
  readonly producerJobId: number
  readonly expectedArtifactName: string
  readonly producerCompletedAtUnixSeconds: number
  readonly observedAtUnixSeconds: number
  readonly initialWorkflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowJobsObservation: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly absenceObservationPairs: readonly [
    S2SArtifactAbsenceObservationPair,
    S2SArtifactAbsenceObservationPair,
    S2SArtifactAbsenceObservationPair
  ]
  readonly reconciliationReceipt: S2SArtifactAbsenceReconciliationReceipt
  readonly reconciliationReceiptSha256: string
}

export interface S2SArtifactAmbiguous {
  readonly _tag: "Ambiguous"
  readonly role: S2SArtifactRole
  readonly reason: S2SArtifactLookupAmbiguity
  readonly workflowRunObservationReceiptSha256: string
  readonly workflowJobsObservationReceiptSha256: string
  readonly artifactsObservationReceiptSha256: string
}

export type S2SArtifactNegativeOutcome =
  | S2SArtifactObservationUnavailable
  | S2SArtifactProducerDidNotSucceed
  | S2SArtifactReconciledAbsence
  | S2SArtifactAmbiguous

interface S2SClassifiedObservedArtifact {
  readonly _tag: "Observed"
  readonly role: S2SArtifactRole
  readonly workflowRunId: number
  readonly expectedHeadSha: string
  readonly producerJob: S2SGitHubWorkflowJobProjection
  readonly artifact: S2SGitHubArtifactProjection
  readonly initialWorkflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowJobsObservation: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly artifactsObservation: S2SGitHubObservation<S2SGitHubArtifactsProjection>
}

interface S2SObservedArtifact extends S2SClassifiedObservedArtifact {
  readonly successfulLookupTrace: S2SArtifactSuccessfulLookupTrace
}

export interface S2SValidatedStageArtifactRead {
  readonly _tag: "ValidatedStageArtifactRead"
  readonly stage: "CONFIRM" | "ADJUDICATE"
  readonly operation: S2SConfirmatoryArtifactReadOperation
  readonly role: "REGISTRATION" | "CANDIDATE"
  readonly producerJob: S2SGitHubWorkflowJobProjection
  readonly artifact: S2SGitHubArtifactProjection
  readonly initialWorkflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowJobsObservation: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly artifactsObservation: S2SGitHubObservation<S2SGitHubArtifactsProjection>
  readonly successfulLookupTrace: S2SArtifactSuccessfulLookupTrace
  readonly readbackStartRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly artifactRequeryObservation: S2SGitHubObservation<S2SGitHubArtifactProjection>
  readonly artifactDownload: S2SGitHubArtifactDownload
  readonly readbackFinalRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly artifactEvidence: S2SArtifactEvidence
  readonly validatedArchive: S2SValidatedArtifactZip
  readonly permitEvidence: S2SStageArtifactPermitEvidence
  readonly readArchiveBytes: () => Uint8Array
}

export class S2SStageArtifactReadError extends Data.TaggedError(
  "S2SStageArtifactReadError"
)<{
  readonly reason:
    | "OBSERVATION_UNAVAILABLE"
    | "OBSERVATION_REVALIDATION_FAILED"
    | "FRESH_JOB_BINDING_DRIFT"
    | "LOOKUP_REJECTED"
  readonly phase: string
  readonly detail: string
  readonly outcome: S2SArtifactNegativeOutcome | null
}> {}

export class S2SArtifactReadbackError extends Data.TaggedError(
  "S2SArtifactReadbackError"
)<{
  readonly reason:
    | "API_REQUERY_FAILED"
    | "API_REQUERY_MISMATCH"
    | "DOWNLOAD_FAILED"
    | "DOWNLOAD_MISMATCH"
    | "EVIDENCE_NOT_CANONICAL"
    | "OBSERVATION_ORDER_INVALID"
    | "RUN_REQUERY_FAILED"
    | "RUN_REQUERY_MISMATCH"
    | "ZIP_REJECTED"
  readonly causeTag: string
  readonly causeReason: string
}> {}

export type S2SStageArtifactReadFailure =
  | import("./s2s-stage-artifact-permits.js").S2SStageArtifactPermitError
  | S2SStageArtifactReadError
  | S2SArtifactReadbackError

export interface S2SRegisterStageArtifactReads {
  readonly stage: "REGISTER"
}

export interface S2SConfirmStageArtifactReads {
  readonly stage: "CONFIRM"
  readonly confirmReadRegistration: Effect.Effect<
    S2SValidatedStageArtifactRead,
    S2SStageArtifactReadFailure
  >
}

export interface S2SAdjudicateStageArtifactReads {
  readonly stage: "ADJUDICATE"
  readonly adjudicateReadRegistration: Effect.Effect<
    S2SValidatedStageArtifactRead,
    S2SStageArtifactReadFailure
  >
  readonly adjudicateReadCandidateFirst: Effect.Effect<
    S2SValidatedStageArtifactRead,
    S2SStageArtifactReadFailure
  >
  readonly adjudicateRereadCandidate: Effect.Effect<
    S2SValidatedStageArtifactRead,
    S2SStageArtifactReadFailure
  >
}

export type S2SStageArtifactReadsService =
  | S2SRegisterStageArtifactReads
  | S2SConfirmStageArtifactReads
  | S2SAdjudicateStageArtifactReads

/**
 * Root-private fixed stage surface. No operation accepts caller-selected run,
 * head, job, role, artifact, operation, or capability identity.
 */
export class S2SStageArtifactReads extends Context.Tag(
  "hswm/S2S/StageArtifactReads"
)<S2SStageArtifactReads, S2SStageArtifactReadsService>() {}

const S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT = 3 as const
const S2S_ARTIFACT_ABSENCE_SETTLE_MILLIS = 10_000 as const
const S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS = 10 as const
const NOT_STARTED_JOB_STATUSES = new Set([
  "queued",
  "waiting",
  "pending",
  "requested"
])

const observerFailureReason = (error: unknown): string =>
  error !== null &&
  typeof error === "object" &&
  "reason" in error &&
  typeof error.reason === "string"
    ? error.reason
    : "UNKNOWN_OBSERVATION_FAILURE"

const observerFailureTag = (error: unknown): string =>
  error !== null &&
  typeof error === "object" &&
  "_tag" in error &&
  typeof error._tag === "string"
    ? error._tag
    : "UnknownObservationFailure"

const stageReadError = (
  reason: S2SStageArtifactReadError["reason"],
  phase: string,
  detail: string,
  outcome: S2SArtifactNegativeOutcome | null = null
): S2SStageArtifactReadError =>
  new S2SStageArtifactReadError({ reason, phase, detail, outcome })

const readbackError = (
  reason: S2SArtifactReadbackError["reason"],
  causeTag: string,
  causeReason: string
): S2SArtifactReadbackError =>
  new S2SArtifactReadbackError({ reason, causeTag, causeReason })

const unavailable = (
  role: S2SArtifactRole,
  operation: S2SArtifactObservationUnavailable["operation"],
  error: unknown
): S2SArtifactObservationUnavailable =>
  Object.freeze({
    _tag: "ObservationUnavailable" as const,
    role,
    operation,
    errorTag: observerFailureTag(error),
    errorReason: observerFailureReason(error)
  })

const ambiguous = (
  role: S2SArtifactRole,
  reason: S2SArtifactLookupAmbiguity,
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  artifacts: S2SGitHubObservation<S2SGitHubArtifactsProjection>
): S2SArtifactAmbiguous =>
  Object.freeze({
    _tag: "Ambiguous" as const,
    role,
    reason,
    workflowRunObservationReceiptSha256: run.receipt.receiptSha256,
    workflowJobsObservationReceiptSha256: jobs.receipt.receiptSha256,
    artifactsObservationReceiptSha256: artifacts.receipt.receiptSha256
  })

const hasExpectedWorkflowIdentity = (
  projection: S2SGitHubWorkflowRunProjection,
  identity: S2SStageArtifactPermitIdentity
): boolean =>
  projection.id === identity.workflowRunId &&
  projection.runAttempt === identity.workflowRunAttempt &&
  projection.repository === S2S_CONFIRMATORY_REPOSITORY &&
  projection.headRepository === S2S_CONFIRMATORY_REPOSITORY &&
  projection.headSha === identity.registrationCommitB &&
  projection.name === S2S_CONFIRMATORY_WORKFLOW_NAME &&
  projection.path === identity.workflowApiPath &&
  projection.event === S2S_CONFIRMATORY_EVENT &&
  projection.headBranch === S2S_CONFIRMATORY_BRANCH &&
  projection.createdAt === identity.workflowRunCreatedAt &&
  projection.createdAtUnixSeconds ===
    identity.workflowRunCreatedAtUnixSeconds &&
  projection.status === "in_progress" &&
  projection.conclusion === null

const sameWorkflowIdentity = (
  left: S2SGitHubWorkflowRunProjection,
  right: S2SGitHubWorkflowRunProjection
): boolean =>
  left.id === right.id &&
  left.runAttempt === right.runAttempt &&
  left.repository === right.repository &&
  left.headRepository === right.headRepository &&
  left.headSha === right.headSha &&
  left.name === right.name &&
  left.path === right.path &&
  left.event === right.event &&
  left.headBranch === right.headBranch

const expectedProducerJobId = (
  identity: S2SStageArtifactPermitIdentity,
  role: "REGISTRATION" | "CANDIDATE"
): number | undefined =>
  role === "REGISTRATION"
    ? identity.predecessorJobDatabaseIds[0]
    : identity.predecessorJobDatabaseIds[1]

const freshJobsMatchPermit = (
  identity: S2SStageArtifactPermitIdentity,
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
): boolean => {
  const projection = jobs.receipt.projection
  if (
    projection.totalCount !== S2S_CONFIRMATORY_JOB_STAGES.length ||
    projection.jobs.length !== S2S_CONFIRMATORY_JOB_STAGES.length
  ) {
    return false
  }
  const jobsByStage = new Map<
    S2SConfirmatoryJobStage,
    S2SGitHubWorkflowJobProjection
  >()
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    const name = S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobName
    const matches = projection.jobs.filter((job) => job.name === name)
    if (matches.length !== 1 || matches[0] === undefined) return false
    jobsByStage.set(stage, matches[0])
  }
  if (
    projection.jobs.some(
      (job) =>
        job.runId !== identity.workflowRunId ||
        job.runAttempt !== identity.workflowRunAttempt ||
        job.headSha !== identity.registrationCommitB ||
        job.startedAtUnixSeconds < run.receipt.projection.createdAtUnixSeconds ||
        job.startedAtUnixSeconds > jobs.receipt.observedAtUnixSeconds
    )
  ) {
    return false
  }
  const stageIndex = S2S_CONFIRMATORY_JOB_STAGES.indexOf(identity.stage)
  const current = jobsByStage.get(identity.stage)
  if (
    stageIndex < 0 ||
    current === undefined ||
    current.id !== identity.currentJobDatabaseId ||
    current.name !== S2S_CONFIRMATORY_STAGE_CONTRACTS[identity.stage].jobName ||
    current.status !== "in_progress" ||
    current.conclusion !== null ||
    current.completedAt !== null ||
    current.completedAtUnixSeconds !== null
  ) {
    return false
  }
  const predecessorIds: Array<number> = []
  let previousCompletion = run.receipt.projection.createdAtUnixSeconds
  for (let index = 0; index < stageIndex; index += 1) {
    const predecessorStage = S2S_CONFIRMATORY_JOB_STAGES[index]
    const predecessor =
      predecessorStage === undefined ? undefined : jobsByStage.get(predecessorStage)
    if (
      predecessor === undefined ||
      predecessor.status !== "completed" ||
      predecessor.conclusion !== "success" ||
      predecessor.completedAt === null ||
      predecessor.completedAtUnixSeconds === null ||
      predecessor.startedAtUnixSeconds < previousCompletion ||
      predecessor.completedAtUnixSeconds < predecessor.startedAtUnixSeconds ||
      predecessor.completedAtUnixSeconds > current.startedAtUnixSeconds ||
      predecessor.completedAtUnixSeconds > jobs.receipt.observedAtUnixSeconds
    ) {
      return false
    }
    predecessorIds.push(predecessor.id)
    previousCompletion = predecessor.completedAtUnixSeconds
  }
  if (
    predecessorIds.length !== identity.predecessorJobDatabaseIds.length ||
    predecessorIds.some(
      (jobId, index) => jobId !== identity.predecessorJobDatabaseIds[index]
    )
  ) {
    return false
  }
  for (let index = stageIndex + 1; index < S2S_CONFIRMATORY_JOB_STAGES.length; index += 1) {
    const laterStage = S2S_CONFIRMATORY_JOB_STAGES[index]
    const later = laterStage === undefined ? undefined : jobsByStage.get(laterStage)
    if (
      later === undefined ||
      !NOT_STARTED_JOB_STATUSES.has(later.status) ||
      later.conclusion !== null ||
      later.completedAt !== null ||
      later.completedAtUnixSeconds !== null
    ) {
      return false
    }
  }
  return true
}

const classifyArtifact = (
  identity: S2SStageArtifactPermitIdentity,
  role: "REGISTRATION" | "CANDIDATE",
  initialRun: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  artifacts: S2SGitHubObservation<S2SGitHubArtifactsProjection>
): S2SClassifiedObservedArtifact | S2SArtifactNegativeOutcome => {
  const policy = ROLE_POLICY[role]
  if (
    initialRun.receipt.observedAtUnixSeconds >
      jobs.receipt.observedAtUnixSeconds ||
    jobs.receipt.observedAtUnixSeconds >
      artifacts.receipt.observedAtUnixSeconds ||
    artifacts.receipt.observedAtUnixSeconds > run.receipt.observedAtUnixSeconds
  ) {
    return ambiguous(role, "OBSERVATION_ORDER_INVALID", run, jobs, artifacts)
  }
  if (
    !hasExpectedWorkflowIdentity(initialRun.receipt.projection, identity) ||
    !hasExpectedWorkflowIdentity(run.receipt.projection, identity) ||
    !sameWorkflowIdentity(
      initialRun.receipt.projection,
      run.receipt.projection
    )
  ) {
    return ambiguous(role, "HEAD_SHA_MISMATCH", run, jobs, artifacts)
  }
  const expectedProducerId = expectedProducerJobId(identity, role)
  const producers = jobs.receipt.projection.jobs.filter(
    (job) => job.name === policy.jobName
  )
  const producer = producers.length === 1 ? producers[0] : undefined
  if (producer === undefined || expectedProducerId === undefined) {
    return ambiguous(role, "PRODUCER_JOB_NOT_FOUND", run, jobs, artifacts)
  }
  if (producer.id !== expectedProducerId) {
    return ambiguous(role, "PRODUCER_JOB_IDENTITY_DRIFT", run, jobs, artifacts)
  }
  if (
    producer.runId !== identity.workflowRunId ||
    producer.runAttempt !== identity.workflowRunAttempt ||
    producer.headSha !== identity.registrationCommitB ||
    artifacts.receipt.projection.artifacts.some(
      (artifact) =>
        artifact.workflowRunId !== identity.workflowRunId ||
        artifact.workflowHeadSha !== identity.registrationCommitB
    )
  ) {
    return ambiguous(role, "HEAD_SHA_MISMATCH", run, jobs, artifacts)
  }
  if (producer.status !== "completed" || producer.completedAtUnixSeconds === null) {
    return ambiguous(role, "PRODUCER_JOB_NOT_COMPLETED", run, jobs, artifacts)
  }
  if (producer.conclusion !== "success") {
    return Object.freeze({
      _tag: "ProducerDidNotCompleteSuccessfully" as const,
      role,
      producerJobId: producer.id,
      status: producer.status,
      conclusion: producer.conclusion,
      initialWorkflowRunObservation: initialRun,
      workflowRunObservation: run,
      workflowJobsObservation: jobs,
      artifactsObservation: artifacts
    })
  }
  if (
    (initialRun.receipt.projection.status === "completed" &&
      initialRun.receipt.projection.conclusion !== "success") ||
    (run.receipt.projection.status === "completed" &&
      run.receipt.projection.conclusion !== "success")
  ) {
    return ambiguous(role, "WORKFLOW_RUN_DID_NOT_SUCCEED", run, jobs, artifacts)
  }
  if (artifacts.receipt.observedAtUnixSeconds < producer.completedAtUnixSeconds) {
    return ambiguous(
      role,
      "OBSERVATION_PRECEDES_JOB_COMPLETION",
      run,
      jobs,
      artifacts
    )
  }
  const matching = artifacts.receipt.projection.artifacts.filter(
    (artifact) => artifact.name === policy.artifactName
  )
  if (matching.length < 1) {
    return ambiguous(role, "ARTIFACT_NOT_OBSERVED", run, jobs, artifacts)
  }
  if (matching.length > 1 || matching[0] === undefined) {
    return ambiguous(role, "DUPLICATE_ARTIFACT_NAME", run, jobs, artifacts)
  }
  const artifact = matching[0]
  if (artifact.expired) {
    return ambiguous(role, "ARTIFACT_EXPIRED", run, jobs, artifacts)
  }
  if (
    artifact.createdAtUnixSeconds < producer.startedAtUnixSeconds ||
    artifact.createdAtUnixSeconds > producer.completedAtUnixSeconds
  ) {
    return ambiguous(
      role,
      "ARTIFACT_OUTSIDE_PRODUCER_INTERVAL",
      run,
      jobs,
      artifacts
    )
  }
  return Object.freeze({
    _tag: "Observed" as const,
    role,
    workflowRunId: identity.workflowRunId,
    expectedHeadSha: identity.registrationCommitB,
    producerJob: producer,
    artifact,
    initialWorkflowRunObservation: initialRun,
    workflowRunObservation: run,
    workflowJobsObservation: jobs,
    artifactsObservation: artifacts
  })
}

const lookupAttempt = <
  const Ordinal extends 1 | 2 | 3,
  const Classification extends
    | "ARTIFACT_NOT_OBSERVED"
    | "ARTIFACT_OBSERVED"
>(
  ordinal: Ordinal,
  classification: Classification,
  pair: S2SArtifactAbsenceObservationPair
): S2SArtifactLookupAttempt<Ordinal, Classification> =>
  Object.freeze({
    ordinal,
    classification,
    artifactsObservation: pair.artifactsObservation,
    workflowRunObservation: pair.workflowRunObservation
  })

const successfulLookupTraceBase = (
  observed: S2SClassifiedObservedArtifact,
  attempts: ReadonlyArray<S2SArtifactLookupAttempt>
): S2SArtifactSuccessfulLookupTraceBase => {
  const totalRawBodyByteLength =
    observed.initialWorkflowRunObservation.receipt.rawBodyByteLength +
    observed.workflowJobsObservation.receipt.rawBodyByteLength +
    attempts.reduce(
      (total, attempt) =>
        total +
        attempt.artifactsObservation.receipt.rawBodyByteLength +
        attempt.workflowRunObservation.receipt.rawBodyByteLength,
      0
    )
  if (
    !Number.isSafeInteger(totalRawBodyByteLength) ||
    totalRawBodyByteLength < 0 ||
    totalRawBodyByteLength >
      S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES
  ) {
    throw new Error(
      "successful artifact lookup raw-byte budget invariant violated"
    )
  }
  return Object.freeze({
    schemaVersion: S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION,
    initialWorkflowRunObservation: observed.initialWorkflowRunObservation,
    workflowJobsObservation: observed.workflowJobsObservation,
    totalRawBodyByteLength
  })
}

const makeSuccessfulLookupTrace = (
  priorAbsencePairs: ReadonlyArray<S2SArtifactAbsenceObservationPair>,
  observed: S2SClassifiedObservedArtifact
): S2SArtifactSuccessfulLookupTrace => {
  const successfulPair: S2SArtifactAbsenceObservationPair = Object.freeze({
    artifactsObservation: observed.artifactsObservation,
    workflowRunObservation: observed.workflowRunObservation
  })
  if (priorAbsencePairs.length === 0) {
    const attempts = Object.freeze([
      lookupAttempt(1, "ARTIFACT_OBSERVED", successfulPair)
    ] as const)
    return Object.freeze({
      ...successfulLookupTraceBase(observed, attempts),
      successfulAttemptOrdinal: 1 as const,
      attempts
    })
  }
  const first = priorAbsencePairs[0]
  if (first === undefined) {
    throw new Error("successful artifact lookup trace invariant violated")
  }
  if (priorAbsencePairs.length === 1) {
    const attempts = Object.freeze([
      lookupAttempt(1, "ARTIFACT_NOT_OBSERVED", first),
      lookupAttempt(2, "ARTIFACT_OBSERVED", successfulPair)
    ] as const)
    return Object.freeze({
      ...successfulLookupTraceBase(observed, attempts),
      successfulAttemptOrdinal: 2 as const,
      attempts
    })
  }
  const second = priorAbsencePairs[1]
  if (priorAbsencePairs.length !== 2 || second === undefined) {
    throw new Error("successful artifact lookup trace invariant violated")
  }
  const attempts = Object.freeze([
    lookupAttempt(1, "ARTIFACT_NOT_OBSERVED", first),
    lookupAttempt(2, "ARTIFACT_NOT_OBSERVED", second),
    lookupAttempt(3, "ARTIFACT_OBSERVED", successfulPair)
  ] as const)
  return Object.freeze({
    ...successfulLookupTraceBase(observed, attempts),
    successfulAttemptOrdinal: 3 as const,
    attempts
  })
}

const sameArtifactProjection = (
  left: S2SGitHubArtifactProjection,
  right: S2SGitHubArtifactProjection
): boolean => {
  const leftHash = canonicalS2SControlSha256(left)
  const rightHash = canonicalS2SControlSha256(right)
  return (
    Either.isRight(leftHash) &&
    Either.isRight(rightHash) &&
    leftHash.right === rightHash.right
  )
}

const runObservationMatches = (
  observed: S2SObservedArtifact,
  identity: S2SStageArtifactPermitIdentity,
  observation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
): boolean =>
  observation.receipt.observedAtUnixSeconds >=
    observed.workflowRunObservation.receipt.observedAtUnixSeconds &&
  hasExpectedWorkflowIdentity(observation.receipt.projection, identity) &&
  sameWorkflowIdentity(
    observed.workflowRunObservation.receipt.projection,
    observation.receipt.projection
  )

const recordObservation = (
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  phase: S2SStageArtifactLedgerPhase,
  observation: S2SGitHubObservation
) =>
  appendS2SStageArtifactLedgerEntry(
    scope,
    operation,
    phase,
    observation.receipt.githubRequestId,
    observation.receipt.receiptSha256,
    observation.receipt.observedAtUnixSeconds
  )

const observeValidatedRun = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  phase: S2SStageArtifactLedgerPhase,
  role: "REGISTRATION" | "CANDIDATE"
) =>
  github.observeWorkflowRun(scope.identity.workflowRunId).pipe(
    Effect.mapError((error) =>
      stageReadError(
        "OBSERVATION_UNAVAILABLE",
        phase,
        observerFailureReason(error),
        unavailable(role, "OBSERVE_RUN", error)
      )
    ),
    Effect.flatMap((observation) =>
      validateS2SGitHubWorkflowRunObservation(
        observation,
        scope.identity.workflowRunId
      ).pipe(
        Effect.mapError((error) =>
          stageReadError(
            "OBSERVATION_REVALIDATION_FAILED",
            phase,
            error.reason,
            unavailable(role, "REVALIDATE_RUN", error)
          )
        )
      )
    ),
    Effect.tap((observation) =>
      recordObservation(scope, operation, phase, observation)
    )
  )

const observeValidatedJobs = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  role: "REGISTRATION" | "CANDIDATE"
) =>
  github.observeWorkflowAttemptJobs(scope.identity.workflowRunId).pipe(
    Effect.mapError((error) =>
      stageReadError(
        "OBSERVATION_UNAVAILABLE",
        "LOOKUP_JOBS",
        observerFailureReason(error),
        unavailable(role, "OBSERVE_JOBS", error)
      )
    ),
    Effect.flatMap((observation) =>
      validateS2SGitHubWorkflowAttemptJobsObservation(
        observation,
        scope.identity.workflowRunId
      ).pipe(
        Effect.mapError((error) =>
          stageReadError(
            "OBSERVATION_REVALIDATION_FAILED",
            "LOOKUP_JOBS",
            error.reason,
            unavailable(role, "REVALIDATE_JOBS", error)
          )
        )
      )
    ),
    Effect.tap((observation) =>
      recordObservation(scope, operation, "LOOKUP_JOBS", observation)
    )
  )

const observeValidatedArtifacts = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  phase: Extract<S2SStageArtifactLedgerPhase, `LOOKUP_ARTIFACTS_${number}`>,
  role: "REGISTRATION" | "CANDIDATE"
) =>
  github.observeRunArtifacts(scope.identity.workflowRunId).pipe(
    Effect.mapError((error) =>
      stageReadError(
        "OBSERVATION_UNAVAILABLE",
        phase,
        observerFailureReason(error),
        unavailable(role, "OBSERVE_ARTIFACTS", error)
      )
    ),
    Effect.flatMap((observation) =>
      validateS2SGitHubRunArtifactsObservation(
        observation,
        scope.identity.workflowRunId
      ).pipe(
        Effect.mapError((error) =>
          stageReadError(
            "OBSERVATION_REVALIDATION_FAILED",
            phase,
            error.reason,
            unavailable(role, "REVALIDATE_ARTIFACTS", error)
          )
        )
      )
    ),
    Effect.tap((observation) =>
      recordObservation(scope, operation, phase, observation)
    )
  )

const makeAbsenceOutcome = (
  identity: S2SStageArtifactPermitIdentity,
  role: "REGISTRATION" | "CANDIDATE",
  initialRun: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  pairs: readonly [
    S2SArtifactAbsenceObservationPair,
    S2SArtifactAbsenceObservationPair,
    S2SArtifactAbsenceObservationPair
  ]
): S2SArtifactReconciledAbsence | S2SArtifactAmbiguous => {
  const artifactHashes = Object.freeze([
    pairs[0].artifactsObservation.receipt.receiptSha256,
    pairs[1].artifactsObservation.receipt.receiptSha256,
    pairs[2].artifactsObservation.receipt.receiptSha256
  ] as const)
  const runHashes = Object.freeze([
    pairs[0].workflowRunObservation.receipt.receiptSha256,
    pairs[1].workflowRunObservation.receipt.receiptSha256,
    pairs[2].workflowRunObservation.receipt.receiptSha256
  ] as const)
  const allHashes = [...artifactHashes, ...runHashes]
  const latest = pairs[2]
  const producerId = expectedProducerJobId(identity, role)
  const producer = jobs.receipt.projection.jobs.find(
    (job) => job.id === producerId && job.name === ROLE_POLICY[role].jobName
  )
  if (new Set(allHashes).size !== allHashes.length) {
    return ambiguous(
      role,
      "ABSENCE_OBSERVATIONS_NOT_DISTINCT",
      latest.workflowRunObservation,
      jobs,
      latest.artifactsObservation
    )
  }
  if (
    pairs[1].artifactsObservation.receipt.observedAtUnixSeconds -
        pairs[0].artifactsObservation.receipt.observedAtUnixSeconds <
      S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS ||
    pairs[2].artifactsObservation.receipt.observedAtUnixSeconds -
        pairs[1].artifactsObservation.receipt.observedAtUnixSeconds <
      S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS
  ) {
    return ambiguous(
      role,
      "ABSENCE_OBSERVATIONS_TOO_CLOSE",
      latest.workflowRunObservation,
      jobs,
      latest.artifactsObservation
    )
  }
  if (producer === undefined || producer.completedAtUnixSeconds === null) {
    return ambiguous(
      role,
      "PRODUCER_JOB_NOT_COMPLETED",
      latest.workflowRunObservation,
      jobs,
      latest.artifactsObservation
    )
  }
  const core = Object.freeze({
    schemaVersion: "hswm-swm0w-s2s-artifact-absence-reconciliation/v3" as const,
    classification: "RECONCILED_ABSENCE_NOT_PROOF" as const,
    observationCount: 3 as const,
    minimumGapSeconds: 10 as const,
    role,
    workflowRunId: identity.workflowRunId,
    expectedHeadSha: identity.registrationCommitB,
    producerJobId: producer.id,
    expectedArtifactName: ROLE_POLICY[role].artifactName,
    initialWorkflowRunObservationReceiptSha256:
      initialRun.receipt.receiptSha256,
    workflowJobsObservationReceiptSha256: jobs.receipt.receiptSha256,
    absenceArtifactObservationReceiptSha256s: artifactHashes,
    absenceRunObservationReceiptSha256s: runHashes
  })
  const hash = canonicalS2SControlSha256(core)
  if (Either.isLeft(hash)) {
    return ambiguous(
      role,
      "ABSENCE_RECONCILIATION_NOT_CANONICAL",
      latest.workflowRunObservation,
      jobs,
      latest.artifactsObservation
    )
  }
  const reconciliationReceipt: S2SArtifactAbsenceReconciliationReceipt =
    Object.freeze({ ...core, receiptSha256: hash.right })
  return Object.freeze({
    _tag: "ReconciledAbsentAfterProducerCompleted" as const,
    role,
    producerJobId: producer.id,
    expectedArtifactName: ROLE_POLICY[role].artifactName,
    producerCompletedAtUnixSeconds: producer.completedAtUnixSeconds,
    observedAtUnixSeconds:
      latest.workflowRunObservation.receipt.observedAtUnixSeconds,
    initialWorkflowRunObservation: initialRun,
    workflowJobsObservation: jobs,
    absenceObservationPairs: Object.freeze([
      pairs[0],
      pairs[1],
      pairs[2]
    ] as const),
    reconciliationReceipt,
    reconciliationReceiptSha256: hash.right
  })
}

const lookupArtifact = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  role: "REGISTRATION" | "CANDIDATE",
  settleBetweenAbsenceObservations: Effect.Effect<void>
): Effect.Effect<
  S2SObservedArtifact,
  | S2SStageArtifactReadError
  | import("./s2s-stage-artifact-permits.js").S2SStageArtifactPermitError
> =>
  Effect.gen(function* () {
    const initialRun = yield* observeValidatedRun(
      github,
      scope,
      operation,
      "LOOKUP_RUN_START",
      role
    )
    if (!hasExpectedWorkflowIdentity(initialRun.receipt.projection, scope.identity)) {
      return yield* stageReadError(
        "LOOKUP_REJECTED",
        "LOOKUP_RUN_START",
        "fresh run identity differs from the authority-bound current run"
      )
    }
    const jobs = yield* observeValidatedJobs(github, scope, operation, role)
    if (!freshJobsMatchPermit(scope.identity, initialRun, jobs)) {
      return yield* stageReadError(
        "FRESH_JOB_BINDING_DRIFT",
        "LOOKUP_JOBS",
        "fresh attempt-one roster differs from the authority-bound current and predecessor numeric jobs"
      )
    }
    const pairs: Array<S2SArtifactAbsenceObservationPair> = []
    for (
      let index = 0;
      index < S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT;
      index += 1
    ) {
      const ordinal = index + 1
      const artifactsPhase = `LOOKUP_ARTIFACTS_${ordinal}` as Extract<
        S2SStageArtifactLedgerPhase,
        `LOOKUP_ARTIFACTS_${number}`
      >
      const runPhase = `LOOKUP_RUN_END_${ordinal}` as Extract<
        S2SStageArtifactLedgerPhase,
        `LOOKUP_RUN_END_${number}`
      >
      const artifacts = yield* observeValidatedArtifacts(
        github,
        scope,
        operation,
        artifactsPhase,
        role
      )
      if (
        artifacts.receipt.projection.artifacts.some(
          (artifact) =>
            artifact.workflowRunId !== scope.identity.workflowRunId ||
            artifact.workflowHeadSha !== scope.identity.registrationCommitB
        )
      ) {
        return yield* stageReadError(
          "LOOKUP_REJECTED",
          artifactsPhase,
          "fresh artifact roster differs from the authority-bound run/head"
        )
      }
      const run = yield* observeValidatedRun(
        github,
        scope,
        operation,
        runPhase,
        role
      )
      const classified = classifyArtifact(
        scope.identity,
        role,
        initialRun,
        run,
        jobs,
        artifacts
      )
      if (classified._tag === "Observed") {
        return Object.freeze({
          ...classified,
          successfulLookupTrace: makeSuccessfulLookupTrace(pairs, classified)
        })
      }
      if (classified._tag !== "Ambiguous" || classified.reason !== "ARTIFACT_NOT_OBSERVED") {
        return yield* stageReadError(
          "LOOKUP_REJECTED",
          artifactsPhase,
          classified._tag,
          classified
        )
      }
      pairs.push(
        Object.freeze({
          artifactsObservation: artifacts,
          workflowRunObservation: run
        })
      )
      if (ordinal < S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT) {
        yield* settleBetweenAbsenceObservations
      }
    }
    const [first, second, third] = pairs
    if (first === undefined || second === undefined || third === undefined) {
      return yield* Effect.dieMessage(
        "bounded artifact absence observation invariant violated"
      )
    }
    const absence = makeAbsenceOutcome(
      scope.identity,
      role,
      initialRun,
      jobs,
      [first, second, third]
    )
    return yield* stageReadError(
      "LOOKUP_REJECTED",
      "LOOKUP_ARTIFACTS_3",
      absence._tag,
      absence
    )
  })

interface ValidatedReadbackCore {
  readonly observed: S2SObservedArtifact
  readonly readbackStartRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly artifactRequeryObservation: S2SGitHubObservation<S2SGitHubArtifactProjection>
  readonly artifactDownload: S2SGitHubArtifactDownload
  readonly readbackFinalRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly artifactEvidence: S2SArtifactEvidence
  readonly validatedArchive: S2SValidatedArtifactZip
  readonly readArchiveBytes: () => Uint8Array
}

const readbackArtifact = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  observed: S2SObservedArtifact
): Effect.Effect<
  ValidatedReadbackCore,
  | S2SArtifactReadbackError
  | import("./s2s-stage-artifact-permits.js").S2SStageArtifactPermitError
> => {
  const policy = ROLE_POLICY[observed.role]
  return Effect.gen(function* () {
    const readbackStartRaw = yield* github
      .observeWorkflowRun(observed.workflowRunId)
      .pipe(
        Effect.mapError((error) =>
          readbackError(
            "RUN_REQUERY_FAILED",
            observerFailureTag(error),
            observerFailureReason(error)
          )
        )
      )
    const readbackStartRun = yield* validateS2SGitHubWorkflowRunObservation(
      readbackStartRaw,
      observed.workflowRunId
    ).pipe(
      Effect.mapError((error) =>
        readbackError("RUN_REQUERY_FAILED", error._tag, error.reason)
      )
    )
    yield* recordObservation(
      scope,
      operation,
      "READBACK_RUN_START",
      readbackStartRun
    )
    if (!runObservationMatches(observed, scope.identity, readbackStartRun)) {
      return yield* readbackError(
        "RUN_REQUERY_MISMATCH",
        "S2SGitHubWorkflowRunProjection",
        "WORKFLOW_IDENTITY_DRIFT_BEFORE_READBACK"
      )
    }
    const requeryRaw = yield* github.observeArtifact(observed.artifact.id).pipe(
      Effect.mapError((error) =>
        readbackError(
          "API_REQUERY_FAILED",
          observerFailureTag(error),
          observerFailureReason(error)
        )
      )
    )
    const requery = yield* validateS2SGitHubArtifactObservation(
      requeryRaw,
      observed.artifact.id
    ).pipe(
      Effect.mapError((error) =>
        readbackError("API_REQUERY_FAILED", error._tag, error.reason)
      )
    )
    yield* recordObservation(
      scope,
      operation,
      "READBACK_ARTIFACT",
      requery
    )
    if (
      requery.receipt.observedAtUnixSeconds <
        readbackStartRun.receipt.observedAtUnixSeconds ||
      requery.receipt.observedAtUnixSeconds <
        observed.artifactsObservation.receipt.observedAtUnixSeconds ||
      !sameArtifactProjection(observed.artifact, requery.receipt.projection)
    ) {
      return yield* readbackError(
        "API_REQUERY_MISMATCH",
        "S2SGitHubArtifactProjection",
        "PROJECTION_OR_OBSERVATION_ORDER_DRIFT"
      )
    }
    const downloadRaw = yield* github
      .downloadArtifactArchive(observed.artifact.id, policy.maximumArchiveBytes)
      .pipe(
        Effect.mapError((error) =>
          readbackError("DOWNLOAD_FAILED", error._tag, error.reason)
        )
      )
    const validatedDownload = validateS2SGitHubArtifactDownload(
      downloadRaw,
      observed.artifact.id,
      policy.maximumArchiveBytes
    )
    if (Either.isLeft(validatedDownload)) {
      return yield* readbackError(
        "DOWNLOAD_MISMATCH",
        validatedDownload.left._tag,
        validatedDownload.left.reason
      )
    }
    const download = validatedDownload.right
    yield* appendS2SStageArtifactLedgerEntry(
      scope,
      operation,
      "READBACK_DOWNLOAD_REDIRECT",
      download.receipt.redirectGitHubRequestId,
      download.receipt.receiptSha256,
      download.receipt.downloadedAtUnixSeconds
    )
    if (
      download.receipt.downloadedAtUnixSeconds <
        requery.receipt.observedAtUnixSeconds ||
      download.receipt.archiveByteLength !== observed.artifact.sizeInBytes ||
      download.receipt.downloadedArchiveSha256 !==
        observed.artifact.digestSha256
    ) {
      return yield* readbackError(
        "DOWNLOAD_MISMATCH",
        "S2SGitHubArtifactDownloadReceipt",
        "ARCHIVE_IDENTITY_OR_OBSERVATION_DRIFT"
      )
    }
    const archiveBytes = download.readArchiveBytes()
    const validatedArchive = validateS2SArtifactZip(archiveBytes, {
      expectedArchiveSha256: S2SSha256Schema.make(
        observed.artifact.digestSha256
      ),
      expectedArchiveByteLength: observed.artifact.sizeInBytes,
      expectedMembers: policy.expectedMembers,
      maximumArchiveBytes: policy.maximumArchiveBytes,
      maximumExpandedBytes: policy.maximumExpandedBytes
    })
    if (Either.isLeft(validatedArchive)) {
      const zipError: S2SArtifactZipValidationError = validatedArchive.left
      return yield* readbackError("ZIP_REJECTED", zipError._tag, zipError.reason)
    }
    const evidence = Schema.decodeUnknownEither(
      S2SArtifactEvidenceSchema,
      { onExcessProperty: "error" }
    )({
      artifactName: observed.artifact.name,
      artifactId: observed.artifact.id,
      artifactCount: 1,
      archiveSizeBytes: observed.artifact.sizeInBytes,
      largestMemberSizeBytes: validatedArchive.right.largestMemberByteLength,
      compressionLevel: S2S_CONFIRMATORY_POLICY.archive.compressionLevel,
      retentionDays: S2S_CONFIRMATORY_POLICY.archive.retentionDays,
      overwrite: S2S_CONFIRMATORY_POLICY.archive.overwrite,
      apiDigestSha256: observed.artifact.digestSha256,
      downloadedArchiveSha256: download.receipt.downloadedArchiveSha256
    })
    if (Either.isLeft(evidence)) {
      return yield* readbackError(
        "DOWNLOAD_MISMATCH",
        "S2SArtifactEvidence",
        "VALIDATED_READBACK_CANNOT_FORM_EVENT_EVIDENCE"
      )
    }
    const finalRunRaw = yield* github
      .observeWorkflowRun(observed.workflowRunId)
      .pipe(
        Effect.mapError((error) =>
          readbackError(
            "RUN_REQUERY_FAILED",
            observerFailureTag(error),
            observerFailureReason(error)
          )
        )
      )
    const finalRun = yield* validateS2SGitHubWorkflowRunObservation(
      finalRunRaw,
      observed.workflowRunId
    ).pipe(
      Effect.mapError((error) =>
        readbackError("RUN_REQUERY_FAILED", error._tag, error.reason)
      )
    )
    yield* recordObservation(
      scope,
      operation,
      "READBACK_RUN_END",
      finalRun
    )
    if (
      !runObservationMatches(observed, scope.identity, finalRun) ||
      finalRun.receipt.observedAtUnixSeconds <
        readbackStartRun.receipt.observedAtUnixSeconds ||
      finalRun.receipt.observedAtUnixSeconds <
        download.receipt.downloadedAtUnixSeconds ||
      !sameWorkflowIdentity(
        readbackStartRun.receipt.projection,
        finalRun.receipt.projection
      )
    ) {
      return yield* readbackError(
        "RUN_REQUERY_MISMATCH",
        "S2SGitHubWorkflowRunProjection",
        "WORKFLOW_IDENTITY_DRIFT_DURING_READBACK"
      )
    }
    const archiveSnapshot = new Uint8Array(archiveBytes)
    return Object.freeze({
      observed,
      readbackStartRunObservation: readbackStartRun,
      artifactRequeryObservation: requery,
      artifactDownload: download,
      readbackFinalRunObservation: finalRun,
      artifactEvidence: Object.freeze({ ...evidence.right }),
      validatedArchive: validatedArchive.right,
      readArchiveBytes: () => new Uint8Array(archiveSnapshot)
    })
  })
}

const validatedRead = (
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  core: ValidatedReadbackCore,
  permitEvidence: S2SStageArtifactPermitEvidence
): S2SValidatedStageArtifactRead => {
  const stage = scope.identity.stage
  const role = core.observed.role
  if (stage === "REGISTER" || role === "ADJUDICATION") {
    throw new Error("validated stage artifact read contract invariant violated")
  }
  return Object.freeze({
    _tag: "ValidatedStageArtifactRead" as const,
    stage,
    operation,
    role,
    producerJob: core.observed.producerJob,
    artifact: core.observed.artifact,
    initialWorkflowRunObservation: core.observed.initialWorkflowRunObservation,
    workflowRunObservation: core.observed.workflowRunObservation,
    workflowJobsObservation: core.observed.workflowJobsObservation,
    artifactsObservation: core.observed.artifactsObservation,
    successfulLookupTrace: core.observed.successfulLookupTrace,
    readbackStartRunObservation: core.readbackStartRunObservation,
    artifactRequeryObservation: core.artifactRequeryObservation,
    artifactDownload: core.artifactDownload,
    readbackFinalRunObservation: core.readbackFinalRunObservation,
    artifactEvidence: core.artifactEvidence,
    validatedArchive: core.validatedArchive,
    permitEvidence,
    readArchiveBytes: core.readArchiveBytes
  })
}

const performStageRead = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  settleBetweenAbsenceObservations: Effect.Effect<void>
): Effect.Effect<S2SValidatedStageArtifactRead, S2SStageArtifactReadFailure> => {
  const contract = S2S_CONFIRMATORY_STAGE_CONTRACTS[
    scope.identity.stage
  ].artifactReadOperations.find((entry) => entry.operation === operation)
  if (contract === undefined) {
    return Effect.dieMessage("fixed stage operation contract invariant violated")
  }
  const role = contract.artifactRole
  return Effect.gen(function* () {
    const observed = yield* lookupArtifact(
      github,
      scope,
      operation,
      role,
      settleBetweenAbsenceObservations
    )
    const readback = yield* readbackArtifact(
      github,
      scope,
      operation,
      observed
    )
    const permitEvidence = yield* snapshotS2SStageArtifactPermitEvidence(
      scope,
      operation
    )
    return validatedRead(scope, operation, readback, permitEvidence)
  })
}

const candidateReadFingerprint = (
  value: S2SValidatedStageArtifactRead
): Either.Either<string, S2SArtifactReadbackError> => {
  const fingerprint = canonicalS2SControlSha256(
    Object.freeze({
      artifactId: value.artifact.id,
      artifactName: value.artifact.name,
      artifactSizeInBytes: value.artifact.sizeInBytes,
      apiDigestSha256: value.artifact.digestSha256,
      downloadedArchiveSha256:
        value.artifactDownload.receipt.downloadedArchiveSha256,
      validatedArchiveSha256: value.validatedArchive.archiveSha256
    })
  )
  return Either.isLeft(fingerprint)
    ? Either.left(
        readbackError(
          "EVIDENCE_NOT_CANONICAL",
          "S2SCandidateArtifactFingerprint",
          "candidate fingerprint cannot be canonically hashed"
        )
      )
    : Either.right(fingerprint.right)
}

const makeStageArtifactReads = (
  github: S2SGitHubObserver["Type"],
  scope: S2SStageArtifactPermitScope,
  settleBetweenAbsenceObservations: Effect.Effect<void>
): S2SStageArtifactReadsService => {
  const read = (operation: S2SConfirmatoryArtifactReadOperation) =>
    useS2SStageArtifactPermit(
      scope,
      operation,
      () =>
        performStageRead(
          github,
          scope,
          operation,
          settleBetweenAbsenceObservations
        ),
      operation === "ADJUDICATE_READ_CANDIDATE_FIRST" ||
        operation === "ADJUDICATE_REREAD_CANDIDATE"
        ? candidateReadFingerprint
        : undefined
    )
  if (scope.identity.stage === "REGISTER") {
    return Object.freeze({ stage: "REGISTER" as const })
  }
  if (scope.identity.stage === "CONFIRM") {
    return Object.freeze({
      stage: "CONFIRM" as const,
      confirmReadRegistration: read("CONFIRM_READ_REGISTRATION")
    })
  }
  return Object.freeze({
    stage: "ADJUDICATE" as const,
    adjudicateReadRegistration: read("ADJUDICATE_READ_REGISTRATION"),
    adjudicateReadCandidateFirst: read(
      "ADJUDICATE_READ_CANDIDATE_FIRST"
    ),
    adjudicateRereadCandidate: read("ADJUDICATE_REREAD_CANDIDATE")
  })
}

const fromEither = <A, E>(either: Either.Either<A, E>): Effect.Effect<A, E> =>
  Either.isLeft(either) ? Effect.fail(either.left) : Effect.succeed(either.right)

const makeS2SStageArtifactReadsFromCurrentRunLiveLayer = (
  githubConfig: S2SGitHubLiveTransportConfig
) =>
  Layer.effect(
    S2SStageArtifactReads,
    Effect.gen(function* () {
      const current = yield* S2SCurrentRunStage
      const scope = yield* fromEither(
        claimS2SStageArtifactPermitScope(current.authority)
      )
      const observerLive = S2SGitHubObserverLive.pipe(
        Layer.provide(makeS2SGitHubHttpTransportLiveLayer(githubConfig))
      )
      const github = yield* S2SGitHubObserver.pipe(
        Effect.provide(observerLive)
      )
      return makeStageArtifactReads(
        github,
        scope,
        Effect.sleep(S2S_ARTIFACT_ABSENCE_SETTLE_MILLIS)
      )
    })
  )

/**
 * Closed production composition root for programs that need both the exact
 * current-run replay source and fixed artifact reads. One current-run Layer
 * node is sequentially provided to the read Layer and retained for the whole
 * program, so both consumers share one authority bearer and one acquisition.
 */
export const makeS2SCurrentRunAndStageArtifactReadsLiveLayer = (
  registrationAuthority: unknown,
  githubConfig: S2SGitHubLiveTransportConfig
) => {
  const currentRunLive = makeS2SCurrentRunStageAuthorityLiveLayer(
    registrationAuthority,
    githubConfig
  )
  const artifactReadsAfterCurrent =
    makeS2SStageArtifactReadsFromCurrentRunLiveLayer(githubConfig)
  return artifactReadsAfterCurrent.pipe(Layer.provideMerge(currentRunLive))
}

/**
 * Compatibility projection for consumers that only need fixed artifact reads.
 * Current-run issuance and inspection must succeed before GitHub artifact
 * transport configuration is evaluated. While workflow bytes remain OPEN,
 * this fails with zero artifact configuration or artifact I/O and no
 * permit-scope attachment.
 */
export const makeS2SStageArtifactReadsLiveLayer = (
  registrationAuthority: unknown,
  githubConfig: S2SGitHubLiveTransportConfig
) => {
  const currentRunLive = makeS2SCurrentRunStageAuthorityLiveLayer(
    registrationAuthority,
    githubConfig
  )
  return makeS2SStageArtifactReadsFromCurrentRunLiveLayer(githubConfig).pipe(
    Layer.provide(currentRunLive)
  )
}

/**
 * @internal TEST-ONLY, NON-AUTHORIZING.
 *
 * Exercises the exact fixed-operation mechanics against a strict synthetic
 * seed and caller-supplied observer. It never inspects or issues current-run
 * authority, never touches production registries, returns only `void`, and
 * closes the ephemeral driver when the callback exits.
 */
export const probeS2SStageArtifactReadMechanicsForTest = <E, R>(
  fixture: S2SStageArtifactPermitTestSeed | unknown,
  github: S2SGitHubObserver["Type"],
  use: (
    reads: S2SStageArtifactReadsService
  ) => Effect.Effect<unknown, E, R>
): Effect.Effect<
  void,
  E | S2SStageArtifactReadFailure,
  R
> =>
  Effect.suspend(() => {
    return fromEither(makeS2SStageArtifactPermitTestScope(fixture)).pipe(
      Effect.flatMap((scope) => {
        const reads = makeStageArtifactReads(
          github,
          scope,
          Effect.yieldNow()
        )
        return Effect.suspend(() => use(reads)).pipe(
          Effect.onExit(() => closeS2SStageArtifactPermitScope(scope)),
          Effect.asVoid
        )
      })
    )
  })
