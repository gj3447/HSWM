import { Context, Data, Effect, Either, Layer, Schema } from "effect"

import { canonicalS2SControlSha256 } from "./s2s-canonical.js"
import {
  S2S_ADJUDICATION_ARTIFACT_NAME,
  S2SArtifactEvidenceSchema,
  S2S_CANDIDATE_ARTIFACT_NAME,
  S2S_CONFIRMATORY_POLICY,
  S2S_REGISTRATION_ARTIFACT_NAME,
  S2SSha256Schema,
  type S2SArtifactEvidence
} from "./s2s-confirmatory.js"
import {
  S2SGitHubObserver,
  validateS2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownload,
  type S2SGitHubArtifactProjection,
  type S2SGitHubArtifactsProjection,
  type S2SGitHubObservation,
  type S2SGitHubObserverError,
  type S2SGitHubWorkflowJobProjection,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection
} from "./s2s-live-github.js"
import {
  validateS2SArtifactZip,
  type S2SArtifactZipValidationError,
  type S2SExpectedZipMember,
  type S2SValidatedArtifactZip
} from "./s2s-zip.js"

export type S2SArtifactRole =
  | "REGISTRATION"
  | "CANDIDATE"
  | "ADJUDICATION"

interface RolePolicy {
  readonly jobName: string
  readonly artifactName: string
  readonly maximumArchiveBytes: number
  readonly maximumExpandedBytes: number
  readonly expectedMembers: ReadonlyArray<S2SExpectedZipMember>
}

const ROLE_POLICY: Readonly<Record<S2SArtifactRole, RolePolicy>> = Object.freeze({
  REGISTRATION: Object.freeze({
    jobName: "register",
    artifactName: S2S_REGISTRATION_ARTIFACT_NAME,
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    expectedMembers: Object.freeze([
      Object.freeze({ name: "control_receipt.json", maximumBytes: 1_048_576 })
    ])
  }),
  CANDIDATE: Object.freeze({
    jobName: "confirm",
    artifactName: S2S_CANDIDATE_ARTIFACT_NAME,
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
    jobName: "adjudicate",
    artifactName: S2S_ADJUDICATION_ARTIFACT_NAME,
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
    expectedMembers: Object.freeze([
      Object.freeze({ name: "control_receipt.json", maximumBytes: 1_048_576 }),
      Object.freeze({ name: "numeric_adjudication.json", maximumBytes: 3_145_728 })
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
  | "DUPLICATE_PRODUCER_JOB_NAME"
  | "HEAD_SHA_MISMATCH"
  | "OBSERVATION_ORDER_INVALID"
  | "OBSERVATION_REQUEST_IDS_NOT_DISTINCT"
  | "OBSERVATION_PRECEDES_JOB_COMPLETION"
  | "PRODUCER_JOB_NOT_COMPLETED"
  | "PRODUCER_JOB_NOT_FOUND"
  | "WORKFLOW_RUN_DID_NOT_SUCCEED"

export interface S2SArtifactObservationUnavailable {
  readonly _tag: "ObservationUnavailable"
  readonly role: S2SArtifactRole
  readonly operation: "OBSERVE_RUN" | "OBSERVE_JOBS" | "OBSERVE_ARTIFACTS"
  readonly errorTag: S2SGitHubObserverError["_tag"]
  readonly errorReason: string
}

export interface S2SArtifactInvalidRequest {
  readonly _tag: "InvalidRequest"
  readonly reason:
    | "INVALID_WORKFLOW_RUN_ID"
    | "INVALID_HEAD_SHA"
    | "INVALID_ROLE"
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
  readonly workflowJobsObservationReceiptSha256: string
  readonly workflowRunObservationReceiptSha256: string
  readonly artifactsObservationReceiptSha256: string
}

export interface S2SArtifactReconciledAbsence {
  readonly _tag: "ReconciledAbsentAfterProducerCompleted"
  readonly role: S2SArtifactRole
  readonly producerJobId: number
  readonly expectedArtifactName: string
  readonly producerCompletedAtUnixSeconds: number
  readonly observedAtUnixSeconds: number
  readonly initialWorkflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly workflowJobsObservation: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly absenceObservations: readonly [
    S2SGitHubObservation<S2SGitHubArtifactsProjection>,
    S2SGitHubObservation<S2SGitHubArtifactsProjection>,
    S2SGitHubObservation<S2SGitHubArtifactsProjection>
  ]
  readonly absenceObservationReceiptSha256s: readonly [string, string, string]
  readonly reconciliationReceipt: S2SArtifactAbsenceReconciliationReceipt
  readonly reconciliationReceiptSha256: string
  readonly initialWorkflowRunObservationReceiptSha256: string
  readonly workflowRunObservationReceiptSha256: string
  readonly workflowJobsObservationReceiptSha256: string
  readonly artifactsObservationReceiptSha256: string
}

export interface S2SArtifactAbsenceReconciliationReceipt {
  readonly schemaVersion: "hswm-swm0w-s2s-artifact-absence-reconciliation/v2"
  readonly classification: "RECONCILED_ABSENCE_NOT_PROOF"
  readonly observationCount: 3
  readonly minimumGapSeconds: 10
  readonly role: S2SArtifactRole
  readonly workflowRunId: number
  readonly expectedHeadSha: string
  readonly producerJobId: number
  readonly expectedArtifactName: string
  readonly initialWorkflowRunObservationReceiptSha256: string
  readonly workflowRunObservationReceiptSha256: string
  readonly workflowJobsObservationReceiptSha256: string
  readonly absenceObservationReceiptSha256s: readonly [string, string, string]
  readonly receiptSha256: string
}

export interface S2SArtifactAmbiguous {
  readonly _tag: "Ambiguous"
  readonly role: S2SArtifactRole
  readonly reason: S2SArtifactLookupAmbiguity
  readonly workflowRunObservationReceiptSha256: string
  readonly workflowJobsObservationReceiptSha256: string
  readonly artifactsObservationReceiptSha256: string
}

declare const observedArtifactAuthorityBrand: unique symbol

export interface S2SObservedArtifactAuthority {
  readonly [observedArtifactAuthorityBrand]: true
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

export type S2SArtifactLookupOutcome =
  | S2SArtifactInvalidRequest
  | S2SArtifactObservationUnavailable
  | S2SArtifactProducerDidNotSucceed
  | S2SArtifactReconciledAbsence
  | S2SArtifactAmbiguous
  | S2SObservedArtifactAuthority

export interface S2SValidatedArtifactReadback {
  readonly authority: S2SObservedArtifactAuthority
  readonly readbackStartRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly artifactRequeryObservation: S2SGitHubObservation<S2SGitHubArtifactProjection>
  readonly artifactDownload: S2SGitHubArtifactDownload
  readonly readbackFinalRunObservation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly readbackStartRunObservationReceiptSha256: string
  readonly readbackFinalRunObservationReceiptSha256: string
  readonly requeryObservationReceiptSha256: string
  readonly downloadObservationReceiptSha256: string
  readonly artifactEvidence: S2SArtifactEvidence
  readonly validatedArchive: S2SValidatedArtifactZip
  readonly readArchiveBytes: () => Uint8Array
}

export class S2SArtifactReadbackError extends Data.TaggedError(
  "S2SArtifactReadbackError"
)<{
  readonly reason:
    | "API_REQUERY_FAILED"
    | "API_REQUERY_MISMATCH"
    | "DOWNLOAD_FAILED"
    | "DOWNLOAD_MISMATCH"
    | "INVALID_AUTHORITY"
    | "OBSERVATION_ORDER_INVALID"
    | "RUN_REQUERY_FAILED"
    | "RUN_REQUERY_MISMATCH"
    | "ZIP_REJECTED"
  readonly causeTag: string
  readonly causeReason: string
}> {}

export class S2SArtifactAuthority extends Context.Tag(
  "hswm/S2S/ArtifactAuthority"
)<
  S2SArtifactAuthority,
  {
    readonly observeRoleArtifact: (
      workflowRunId: number,
      expectedHeadSha: string,
      role: S2SArtifactRole
    ) => Effect.Effect<S2SArtifactLookupOutcome>
    readonly readback: (
      authority: S2SObservedArtifactAuthority
    ) => Effect.Effect<S2SValidatedArtifactReadback, S2SArtifactReadbackError>
  }
>() {}

const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const S2S_CONFIRMATORY_WORKFLOW_NAME = "SWM-0W-S2S confirmatory"
const S2S_CONFIRMATORY_WORKFLOW_PATH =
  ".github/workflows/swm0w-s2s-confirmatory.yml"
const S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT = 3 as const
const S2S_ARTIFACT_ABSENCE_SETTLE_MILLIS = 10_000 as const
const S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS = 10 as const

const observerFailureReason = (error: S2SGitHubObserverError): string =>
  "reason" in error && typeof error.reason === "string"
    ? error.reason
    : "UNKNOWN_OBSERVATION_FAILURE"

const unavailable = (
  role: S2SArtifactRole,
  operation: S2SArtifactObservationUnavailable["operation"],
  error: S2SGitHubObserverError
): S2SArtifactObservationUnavailable =>
  Object.freeze({
    _tag: "ObservationUnavailable",
    role,
    operation,
    errorTag: error._tag,
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
    _tag: "Ambiguous",
    role,
    reason,
    workflowRunObservationReceiptSha256: run.receipt.receiptSha256,
    workflowJobsObservationReceiptSha256: jobs.receipt.receiptSha256,
    artifactsObservationReceiptSha256: artifacts.receipt.receiptSha256
  })

const hasExpectedWorkflowIdentity = (
  projection: S2SGitHubWorkflowRunProjection,
  workflowRunId: number,
  expectedHeadSha: string
): boolean =>
  projection.id === workflowRunId &&
  projection.runAttempt === 1 &&
  projection.repository === "gj3447/HSWM" &&
  projection.headRepository === "gj3447/HSWM" &&
  projection.headSha === expectedHeadSha &&
  projection.name === S2S_CONFIRMATORY_WORKFLOW_NAME &&
  projection.path === S2S_CONFIRMATORY_WORKFLOW_PATH &&
  projection.event === "push" &&
  projection.headBranch === "main"

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

interface GitHubRequestIdentified {
  readonly receipt: {
    readonly githubRequestId: string
  }
}

const distinctGitHubRequestIds = (
  observations: ReadonlyArray<GitHubRequestIdentified>
): boolean => {
  const requestIds = observations.map(
    (observation) => observation.receipt.githubRequestId
  )
  return new Set(requestIds).size === requestIds.length
}

const classifyArtifact = (
  workflowRunId: number,
  expectedHeadSha: string,
  role: S2SArtifactRole,
  initialRun: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  artifacts: S2SGitHubObservation<S2SGitHubArtifactsProjection>,
  issuedAuthorities: WeakSet<object>
): S2SArtifactLookupOutcome => {
  const policy = ROLE_POLICY[role]
  const runProjection = run.receipt.projection
  if (!distinctGitHubRequestIds([initialRun, jobs, artifacts, run])) {
    return ambiguous(
      role,
      "OBSERVATION_REQUEST_IDS_NOT_DISTINCT",
      run,
      jobs,
      artifacts
    )
  }
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
    !hasExpectedWorkflowIdentity(
      initialRun.receipt.projection,
      workflowRunId,
      expectedHeadSha
    ) ||
    !hasExpectedWorkflowIdentity(
      runProjection,
      workflowRunId,
      expectedHeadSha
    ) ||
    !sameWorkflowIdentity(initialRun.receipt.projection, runProjection)
  ) {
    return ambiguous(role, "HEAD_SHA_MISMATCH", run, jobs, artifacts)
  }
  const producers = jobs.receipt.projection.jobs.filter(
    (job) => job.name === policy.jobName
  )
  if (producers.length < 1) {
    return ambiguous(role, "PRODUCER_JOB_NOT_FOUND", run, jobs, artifacts)
  }
  if (producers.length > 1) {
    return ambiguous(
      role,
      "DUPLICATE_PRODUCER_JOB_NAME",
      run,
      jobs,
      artifacts
    )
  }
  const producer = producers[0]
  if (producer === undefined) {
    return ambiguous(role, "PRODUCER_JOB_NOT_FOUND", run, jobs, artifacts)
  }
  if (
    producer.runId !== workflowRunId ||
    producer.runAttempt !== 1 ||
    producer.headSha !== expectedHeadSha ||
    artifacts.receipt.projection.artifacts.some(
      (artifact) =>
        artifact.workflowRunId !== workflowRunId ||
        artifact.workflowHeadSha !== expectedHeadSha
    )
  ) {
    return ambiguous(role, "HEAD_SHA_MISMATCH", run, jobs, artifacts)
  }
  if (producer.status !== "completed" || producer.completedAtUnixSeconds === null) {
    return ambiguous(role, "PRODUCER_JOB_NOT_COMPLETED", run, jobs, artifacts)
  }
  if (producer.conclusion !== "success") {
    return Object.freeze({
      _tag: "ProducerDidNotCompleteSuccessfully",
      role,
      producerJobId: producer.id,
      status: producer.status,
      conclusion: producer.conclusion,
      initialWorkflowRunObservation: initialRun,
      workflowRunObservation: run,
      workflowJobsObservation: jobs,
      artifactsObservation: artifacts,
      workflowRunObservationReceiptSha256: run.receipt.receiptSha256,
      workflowJobsObservationReceiptSha256: jobs.receipt.receiptSha256,
      artifactsObservationReceiptSha256: artifacts.receipt.receiptSha256
    })
  }
  if (
    (initialRun.receipt.projection.status === "completed" &&
      initialRun.receipt.projection.conclusion !== "success") ||
    (runProjection.status === "completed" &&
      runProjection.conclusion !== "success")
  ) {
    return ambiguous(
      role,
      "WORKFLOW_RUN_DID_NOT_SUCCEED",
      run,
      jobs,
      artifacts
    )
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
  if (matching.length > 1) {
    return ambiguous(role, "DUPLICATE_ARTIFACT_NAME", run, jobs, artifacts)
  }
  const artifact = matching[0]
  if (artifact === undefined) {
    return ambiguous(role, "DUPLICATE_ARTIFACT_NAME", run, jobs, artifacts)
  }
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
  const authority = Object.freeze({
    _tag: "Observed" as const,
    role,
    workflowRunId,
    expectedHeadSha,
    producerJob: producer,
    artifact,
    initialWorkflowRunObservation: initialRun,
    workflowRunObservation: run,
    workflowJobsObservation: jobs,
    artifactsObservation: artifacts
  }) as S2SObservedArtifactAuthority
  issuedAuthorities.add(authority)
  return authority
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

const runObservationMatchesAuthority = (
  authority: S2SObservedArtifactAuthority,
  observation: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
): boolean =>
  observation.receipt.observedAtUnixSeconds >=
    authority.workflowRunObservation.receipt.observedAtUnixSeconds &&
  hasExpectedWorkflowIdentity(
    observation.receipt.projection,
    authority.workflowRunId,
    authority.expectedHeadSha
  ) &&
  !(
    observation.receipt.projection.status === "completed" &&
    observation.receipt.projection.conclusion !== "success"
  ) &&
  sameWorkflowIdentity(
    authority.workflowRunObservation.receipt.projection,
    observation.receipt.projection
  )

const readbackError = (
  reason: S2SArtifactReadbackError["reason"],
  causeTag: string,
  causeReason: string
): S2SArtifactReadbackError =>
  new S2SArtifactReadbackError({ reason, causeTag, causeReason })

const readbackArtifact = (
  github: S2SGitHubObserver["Type"],
  authority: S2SObservedArtifactAuthority,
  issuedAuthorities: WeakSet<object>
): Effect.Effect<S2SValidatedArtifactReadback, S2SArtifactReadbackError> => {
  if (
    !issuedAuthorities.has(authority) ||
    authority._tag !== "Observed" ||
    !GIT_SHA_PATTERN.test(authority.expectedHeadSha)
  ) {
    return Effect.fail(
      readbackError(
        "INVALID_AUTHORITY",
        "S2SObservedArtifactAuthority",
        "UNISSUED"
      )
    )
  }
  const policy = ROLE_POLICY[authority.role]
  return Effect.gen(function* () {
    const readbackStartRun = yield* github
      .observeWorkflowRun(authority.workflowRunId)
      .pipe(
        Effect.mapError((error) =>
          readbackError(
            "RUN_REQUERY_FAILED",
            error._tag,
            observerFailureReason(error)
          )
        )
      )
    if (!runObservationMatchesAuthority(authority, readbackStartRun)) {
      return yield* readbackError(
        "RUN_REQUERY_MISMATCH",
        "S2SGitHubWorkflowRunProjection",
        "WORKFLOW_IDENTITY_DRIFT_BEFORE_READBACK"
      )
    }
    if (
      !distinctGitHubRequestIds([
        authority.initialWorkflowRunObservation,
        authority.workflowRunObservation,
        authority.workflowJobsObservation,
        authority.artifactsObservation,
        readbackStartRun
      ])
    ) {
      return yield* readbackError(
        "OBSERVATION_ORDER_INVALID",
        "S2SGitHubObservationReceipt",
        "GITHUB_REQUEST_ID_REUSED_BEFORE_READBACK"
      )
    }
    const requery = yield* github.observeArtifact(authority.artifact.id).pipe(
      Effect.mapError((error) =>
        readbackError(
          "API_REQUERY_FAILED",
          error._tag,
          observerFailureReason(error)
        )
      )
    )
    if (
      requery.receipt.observedAtUnixSeconds <
        readbackStartRun.receipt.observedAtUnixSeconds ||
      requery.receipt.observedAtUnixSeconds <
        authority.artifactsObservation.receipt.observedAtUnixSeconds ||
      requery.receipt.receiptSha256 ===
        authority.artifactsObservation.receipt.receiptSha256 ||
      !distinctGitHubRequestIds([
        authority.initialWorkflowRunObservation,
        authority.workflowRunObservation,
        authority.workflowJobsObservation,
        authority.artifactsObservation,
        readbackStartRun,
        requery
      ])
    ) {
      return yield* readbackError(
        "OBSERVATION_ORDER_INVALID",
        "S2SGitHubObservationReceipt",
        "REQUERY_NOT_DISTINCT_OR_LATER"
      )
    }
    if (!sameArtifactProjection(authority.artifact, requery.receipt.projection)) {
      return yield* readbackError(
        "API_REQUERY_MISMATCH",
        "S2SGitHubArtifactProjection",
        "PROJECTION_DRIFT"
      )
    }
    const download = yield* github
      .downloadArtifactArchive(authority.artifact.id, policy.maximumArchiveBytes)
      .pipe(
        Effect.mapError((error) =>
          readbackError("DOWNLOAD_FAILED", error._tag, error.reason)
        )
      )
    const validatedDownload = validateS2SGitHubArtifactDownload(
      download,
      authority.artifact.id,
      policy.maximumArchiveBytes
    )
    if (Either.isLeft(validatedDownload)) {
      return yield* readbackError(
        "DOWNLOAD_MISMATCH",
        validatedDownload.left._tag,
        validatedDownload.left.reason
      )
    }
    const trustedDownload = validatedDownload.right
    if (
      trustedDownload.receipt.downloadedAtUnixSeconds <
        requery.receipt.observedAtUnixSeconds ||
      trustedDownload.receipt.archiveByteLength !== authority.artifact.sizeInBytes ||
      trustedDownload.receipt.downloadedArchiveSha256 !==
        authority.artifact.digestSha256 ||
      trustedDownload.receipt.receiptSha256 === requery.receipt.receiptSha256 ||
      trustedDownload.receipt.receiptSha256 ===
        authority.artifactsObservation.receipt.receiptSha256 ||
      new Set([
        authority.initialWorkflowRunObservation.receipt.githubRequestId,
        authority.workflowRunObservation.receipt.githubRequestId,
        authority.workflowJobsObservation.receipt.githubRequestId,
        authority.artifactsObservation.receipt.githubRequestId,
        readbackStartRun.receipt.githubRequestId,
        requery.receipt.githubRequestId,
        trustedDownload.receipt.redirectGitHubRequestId
      ]).size !== 7
    ) {
      return yield* readbackError(
        "DOWNLOAD_MISMATCH",
        "S2SGitHubArtifactDownloadReceipt",
        "ARCHIVE_IDENTITY_OR_OBSERVATION_DRIFT"
      )
    }
    const archiveBytes = trustedDownload.readArchiveBytes()
    const validated = validateS2SArtifactZip(archiveBytes, {
      expectedArchiveSha256: S2SSha256Schema.make(
        authority.artifact.digestSha256
      ),
      expectedArchiveByteLength: authority.artifact.sizeInBytes,
      expectedMembers: policy.expectedMembers,
      maximumArchiveBytes: policy.maximumArchiveBytes,
      maximumExpandedBytes: policy.maximumExpandedBytes
    })
    if (Either.isLeft(validated)) {
      const zipError: S2SArtifactZipValidationError = validated.left
      return yield* readbackError(
        "ZIP_REJECTED",
        zipError._tag,
        zipError.reason
      )
    }
    const artifactEvidence = Schema.decodeUnknownEither(
      S2SArtifactEvidenceSchema,
      { onExcessProperty: "error" }
    )({
      artifactName: authority.artifact.name,
      artifactId: authority.artifact.id,
      artifactCount: 1,
      archiveSizeBytes: authority.artifact.sizeInBytes,
      largestMemberSizeBytes: validated.right.largestMemberByteLength,
      compressionLevel: S2S_CONFIRMATORY_POLICY.archive.compressionLevel,
      retentionDays: S2S_CONFIRMATORY_POLICY.archive.retentionDays,
      overwrite: S2S_CONFIRMATORY_POLICY.archive.overwrite,
      apiDigestSha256: authority.artifact.digestSha256,
      downloadedArchiveSha256: trustedDownload.receipt.downloadedArchiveSha256
    })
    if (Either.isLeft(artifactEvidence)) {
      return yield* readbackError(
        "DOWNLOAD_MISMATCH",
        "S2SArtifactEvidence",
        "VALIDATED_READBACK_CANNOT_FORM_EVENT_EVIDENCE"
      )
    }
    const artifactEvidenceSnapshot = Object.freeze({ ...artifactEvidence.right })
    const readbackFinalRun = yield* github
      .observeWorkflowRun(authority.workflowRunId)
      .pipe(
        Effect.mapError((error) =>
          readbackError(
            "RUN_REQUERY_FAILED",
            error._tag,
            observerFailureReason(error)
          )
        )
      )
    if (
      !runObservationMatchesAuthority(authority, readbackFinalRun) ||
      readbackFinalRun.receipt.observedAtUnixSeconds <
        readbackStartRun.receipt.observedAtUnixSeconds ||
      readbackFinalRun.receipt.observedAtUnixSeconds <
        trustedDownload.receipt.downloadedAtUnixSeconds ||
      !sameWorkflowIdentity(
        readbackStartRun.receipt.projection,
        readbackFinalRun.receipt.projection
      ) ||
      new Set([
        authority.initialWorkflowRunObservation.receipt.githubRequestId,
        authority.workflowRunObservation.receipt.githubRequestId,
        authority.workflowJobsObservation.receipt.githubRequestId,
        authority.artifactsObservation.receipt.githubRequestId,
        readbackStartRun.receipt.githubRequestId,
        requery.receipt.githubRequestId,
        trustedDownload.receipt.redirectGitHubRequestId,
        readbackFinalRun.receipt.githubRequestId
      ]).size !== 8
    ) {
      return yield* readbackError(
        "RUN_REQUERY_MISMATCH",
        "S2SGitHubWorkflowRunProjection",
        "WORKFLOW_IDENTITY_DRIFT_DURING_READBACK"
      )
    }
    const archiveSnapshot = new Uint8Array(archiveBytes)
    return Object.freeze({
      authority,
      readbackStartRunObservation: readbackStartRun,
      artifactRequeryObservation: requery,
      artifactDownload: trustedDownload,
      readbackFinalRunObservation: readbackFinalRun,
      readbackStartRunObservationReceiptSha256:
        readbackStartRun.receipt.receiptSha256,
      readbackFinalRunObservationReceiptSha256:
        readbackFinalRun.receipt.receiptSha256,
      requeryObservationReceiptSha256: requery.receipt.receiptSha256,
      downloadObservationReceiptSha256: trustedDownload.receipt.receiptSha256,
      artifactEvidence: artifactEvidenceSnapshot,
      validatedArchive: validated.right,
      readArchiveBytes: () => new Uint8Array(archiveSnapshot)
    })
  })
}

const makeAbsenceOutcome = (
  role: S2SArtifactRole,
  initialRun: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  observations: readonly [
    S2SGitHubObservation<S2SGitHubArtifactsProjection>,
    S2SGitHubObservation<S2SGitHubArtifactsProjection>,
    S2SGitHubObservation<S2SGitHubArtifactsProjection>
  ]
): S2SArtifactLookupOutcome => {
  const hashes = Object.freeze([
    observations[0].receipt.receiptSha256,
    observations[1].receipt.receiptSha256,
    observations[2].receipt.receiptSha256
  ]) as readonly [string, string, string]
  const requestIds = Object.freeze([
    observations[0].receipt.githubRequestId,
    observations[1].receipt.githubRequestId,
    observations[2].receipt.githubRequestId
  ])
  const finalObservation = observations[2]
  const producer = jobs.receipt.projection.jobs.find(
    (job) => job.name === ROLE_POLICY[role].jobName
  )
  if (
    new Set(hashes).size !== S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT ||
    new Set(requestIds).size !== S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT
  ) {
    return ambiguous(
      role,
      "ABSENCE_OBSERVATIONS_NOT_DISTINCT",
      run,
      jobs,
      finalObservation
    )
  }
  if (
    observations[1].receipt.observedAtUnixSeconds -
        observations[0].receipt.observedAtUnixSeconds <
      S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS ||
    observations[2].receipt.observedAtUnixSeconds -
        observations[1].receipt.observedAtUnixSeconds <
      S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS
  ) {
    return ambiguous(
      role,
      "ABSENCE_OBSERVATIONS_TOO_CLOSE",
      run,
      jobs,
      finalObservation
    )
  }
  if (producer === undefined || producer.completedAtUnixSeconds === null) {
    return ambiguous(role, "PRODUCER_JOB_NOT_COMPLETED", run, jobs, finalObservation)
  }
  const reconciliationCore = Object.freeze({
    schemaVersion: "hswm-swm0w-s2s-artifact-absence-reconciliation/v2",
    classification: "RECONCILED_ABSENCE_NOT_PROOF",
    observationCount: S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT,
    minimumGapSeconds: S2S_ARTIFACT_ABSENCE_MINIMUM_GAP_SECONDS,
    role,
    workflowRunId: run.receipt.projection.id,
    expectedHeadSha: run.receipt.projection.headSha,
    producerJobId: producer.id,
    expectedArtifactName: ROLE_POLICY[role].artifactName,
    initialWorkflowRunObservationReceiptSha256:
      initialRun.receipt.receiptSha256,
    workflowRunObservationReceiptSha256: run.receipt.receiptSha256,
    workflowJobsObservationReceiptSha256: jobs.receipt.receiptSha256,
    absenceObservationReceiptSha256s: hashes
  })
  const reconciliationHash = canonicalS2SControlSha256(reconciliationCore)
  if (Either.isLeft(reconciliationHash)) {
    return ambiguous(
      role,
      "ABSENCE_RECONCILIATION_NOT_CANONICAL",
      run,
      jobs,
      finalObservation
    )
  }
  const reconciliationReceipt = Object.freeze({
    ...reconciliationCore,
    receiptSha256: reconciliationHash.right
  })
  const frozenObservations = Object.freeze([
    observations[0],
    observations[1],
    observations[2]
  ]) as unknown as S2SArtifactReconciledAbsence["absenceObservations"]
  return Object.freeze({
    _tag: "ReconciledAbsentAfterProducerCompleted" as const,
    role,
    producerJobId: producer.id,
    expectedArtifactName: ROLE_POLICY[role].artifactName,
    producerCompletedAtUnixSeconds: producer.completedAtUnixSeconds,
    observedAtUnixSeconds: finalObservation.receipt.observedAtUnixSeconds,
    initialWorkflowRunObservation: initialRun,
    workflowRunObservation: run,
    workflowJobsObservation: jobs,
    absenceObservations: frozenObservations,
    absenceObservationReceiptSha256s: hashes,
    reconciliationReceipt,
    reconciliationReceiptSha256: reconciliationHash.right,
    initialWorkflowRunObservationReceiptSha256:
      initialRun.receipt.receiptSha256,
    workflowRunObservationReceiptSha256: run.receipt.receiptSha256,
    workflowJobsObservationReceiptSha256: jobs.receipt.receiptSha256,
    artifactsObservationReceiptSha256: finalObservation.receipt.receiptSha256
  })
}

const makeS2SArtifactAuthorityLayer = (
  settleBetweenAbsenceObservations: Effect.Effect<void>
) =>
  Layer.effect(
    S2SArtifactAuthority,
    Effect.gen(function* () {
      const github = yield* S2SGitHubObserver
      const issuedAuthorities = new WeakSet<object>()
      return S2SArtifactAuthority.of({
        observeRoleArtifact: (workflowRunId, expectedHeadSha, role) => {
          if (
            typeof role !== "string" ||
            !Object.hasOwn(ROLE_POLICY, role)
          ) {
            return Effect.succeed(
              Object.freeze({
                _tag: "InvalidRequest" as const,
                reason: "INVALID_ROLE" as const
              })
            )
          }
          if (!Number.isSafeInteger(workflowRunId) || workflowRunId < 1) {
            return Effect.succeed(
              Object.freeze({
                _tag: "InvalidRequest" as const,
                reason: "INVALID_WORKFLOW_RUN_ID" as const
              })
            )
          }
          if (
            typeof expectedHeadSha !== "string" ||
            !GIT_SHA_PATTERN.test(expectedHeadSha)
          ) {
            return Effect.succeed(
              Object.freeze({
                _tag: "InvalidRequest" as const,
                reason: "INVALID_HEAD_SHA" as const
              })
            )
          }
          return Effect.gen(function* () {
            const runOutcome = yield* github
              .observeWorkflowRun(workflowRunId)
              .pipe(Effect.either)
            if (Either.isLeft(runOutcome)) {
              return unavailable(role, "OBSERVE_RUN", runOutcome.left)
            }
            const jobsOutcome = yield* github
              .observeWorkflowAttemptJobs(workflowRunId)
              .pipe(Effect.either)
            if (Either.isLeft(jobsOutcome)) {
              return unavailable(role, "OBSERVE_JOBS", jobsOutcome.left)
            }
            const absenceObservations: Array<
              S2SGitHubObservation<S2SGitHubArtifactsProjection>
            > = []
            const seenRequestIds = new Set([
              runOutcome.right.receipt.githubRequestId,
              jobsOutcome.right.receipt.githubRequestId
            ])
            const initialRequestIdsDistinct = seenRequestIds.size === 2
            let latestRun = runOutcome.right
            for (
              let index = 0;
              index < S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT;
              index += 1
            ) {
              const artifactsOutcome = yield* github
                .observeRunArtifacts(workflowRunId)
                .pipe(Effect.either)
              if (Either.isLeft(artifactsOutcome)) {
                return unavailable(
                  role,
                  "OBSERVE_ARTIFACTS",
                  artifactsOutcome.left
                )
              }
              const currentRunOutcome = yield* github
                .observeWorkflowRun(workflowRunId)
                .pipe(Effect.either)
              if (Either.isLeft(currentRunOutcome)) {
                return unavailable(role, "OBSERVE_RUN", currentRunOutcome.left)
              }
              latestRun = currentRunOutcome.right
              const currentRequestIds = [
                artifactsOutcome.right.receipt.githubRequestId,
                latestRun.receipt.githubRequestId
              ]
              if (
                !initialRequestIdsDistinct ||
                currentRequestIds[0] === currentRequestIds[1] ||
                currentRequestIds.some((requestId) =>
                  seenRequestIds.has(requestId)
                )
              ) {
                return ambiguous(
                  role,
                  "OBSERVATION_REQUEST_IDS_NOT_DISTINCT",
                  latestRun,
                  jobsOutcome.right,
                  artifactsOutcome.right
                )
              }
              for (const requestId of currentRequestIds) {
                seenRequestIds.add(requestId)
              }
              const classified = classifyArtifact(
                workflowRunId,
                expectedHeadSha,
                role,
                runOutcome.right,
                latestRun,
                jobsOutcome.right,
                artifactsOutcome.right,
                issuedAuthorities
              )
              if (
                classified._tag !== "Ambiguous" ||
                classified.reason !== "ARTIFACT_NOT_OBSERVED"
              ) {
                return classified
              }
              absenceObservations.push(artifactsOutcome.right)
              if (index + 1 < S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT) {
                yield* settleBetweenAbsenceObservations
              }
            }
            const [first, second, third] = absenceObservations
            if (first === undefined || second === undefined || third === undefined) {
              return yield* Effect.dieMessage(
                "bounded artifact absence observation invariant violated"
              )
            }
            return makeAbsenceOutcome(
              role,
              runOutcome.right,
              latestRun,
              jobsOutcome.right,
              [first, second, third]
            )
          })
        },
        readback: (authority) =>
          readbackArtifact(github, authority, issuedAuthorities)
      })
    })
  )

export const S2SArtifactAuthorityLive = makeS2SArtifactAuthorityLayer(
  Effect.sleep(S2S_ARTIFACT_ABSENCE_SETTLE_MILLIS)
)

export const makeS2SArtifactAuthorityTestLayer = () =>
  makeS2SArtifactAuthorityLayer(Effect.yieldNow())
