import { Context, Data, Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES,
  S2SCurrentInvocation,
  S2SCurrentInvocationLive,
  inspectS2SCurrentInvocationAuthority,
  readS2SCurrentInvocationEventBytes,
  type S2SCurrentInvocationEvidence
} from "./s2s-invocation.js"
import {
  S2S_GITHUB_JSON_MAX_BYTES,
  S2SGitHubObserver,
  S2SGitHubObserverLive,
  makeS2SGitHubHttpTransportLiveLayer,
  validateS2SGitHubWorkflowAttemptJobsObservation,
  validateS2SGitHubWorkflowRunObservation,
  validateS2SGitHubWorkflowRunsForHeadObservation,
  type S2SGitHubLiveTransportConfig,
  type S2SGitHubObservation,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection,
  type S2SGitHubWorkflowRunsProjection
} from "./s2s-live-github.js"
import {
  inspectS2SRegistrationCommitAuthority,
  inspectS2SRegistrationWorkflowManifestBinding,
  type S2SRegistrationCommitAuthorityEvidence,
  type S2SRegistrationWorkflowManifestBinding
} from "./s2s-preregistration.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_EVENT,
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_NAME,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT,
  s2sConfirmatoryWorkflowContractSha256,
  type S2SConfirmatoryJobId,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"

export const S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-current-run-stage-evidence/v1" as const
export const S2S_CURRENT_RUN_BRACKET_TIMEOUT_MILLIS = 480_000 as const
export const S2S_CURRENT_RUN_REPLAY_MAX_RAW_BYTES =
  S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES + 4 * S2S_GITHUB_JSON_MAX_BYTES

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const REVIEWED_WORKFLOW_API_PATHS = Object.freeze([
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`
] as const)
const NOT_STARTED_JOB_STATUSES = new Set([
  "queued",
  "waiting",
  "pending",
  "requested"
])

export class S2SCurrentRunInputError extends Data.TaggedError(
  "S2SCurrentRunInputError"
)<{
  readonly reason:
    | "REGISTRATION_AUTHORITY_REJECTED"
    | "INVOCATION_AUTHORITY_REJECTED"
    | "REGISTRATION_INVOCATION_MISMATCH"
    | "WORKFLOW_CONTRACT_MISMATCH"
    | "WORKFLOW_SOURCE_BYTES_OPEN"
    | "WORKFLOW_BINDING_REJECTED"
    | "WORKFLOW_HASH_MISMATCH"
    | "REVIEWED_FIXTURE_REJECTED"
    | "INVALID_CURRENT_RUN_AUTHORITY"
    | "INVOCATION_SOURCE_REJECTED"
  readonly detail: string
}> {}

export class S2SCurrentRunAcquisitionError extends Data.TaggedError(
  "S2SCurrentRunAcquisitionError"
)<{
  readonly phase:
    | "CONFIGURE_GITHUB"
    | "RUN_START"
    | "JOBS"
    | "RUNS_FOR_HEAD"
    | "RUN_END"
    | "BRACKET"
  readonly reason:
    | "OBSERVATION_FAILED"
    | "REVALIDATION_FAILED"
    | "BRACKET_TIMED_OUT"
  readonly causeTag: string
}> {}

export class S2SCurrentRunPolicyError extends Data.TaggedError(
  "S2SCurrentRunPolicyError"
)<{
  readonly reason:
    | "INPUT_EVIDENCE_REJECTED"
    | "REQUEST_ID_REUSED"
    | "OBSERVATION_ORDER_INVALID"
    | "RUN_MULTIPLICITY_ZERO"
    | "RUN_MULTIPLICITY_MULTIPLE"
    | "CURRENT_RUN_MISMATCH"
    | "RUN_IDENTITY_DRIFT"
    | "WORKFLOW_PATH_REJECTED"
    | "RUN_STATE_REJECTED"
    | "JOB_ROSTER_REJECTED"
    | "CURRENT_JOB_REJECTED"
    | "PREDECESSOR_REJECTED"
    | "LATER_JOB_REJECTED"
    | "EVIDENCE_NOT_CANONICAL"
  readonly path: string
  readonly detail: string
}> {}

export type S2SCurrentRunError =
  | S2SCurrentRunInputError
  | S2SCurrentRunAcquisitionError
  | S2SCurrentRunPolicyError
  | S2SCurrentRunReplaySnapshotError

export interface S2SCurrentRunObservationEvidence {
  readonly receiptSha256: string
  readonly githubRequestId: string
  readonly observedAtUnixSeconds: number
}

export interface S2SCurrentRunStageEvidence {
  readonly schemaVersion: typeof S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION
  readonly authorityScope: "PROCESS_LOCAL_STAGE_ENTRY"
  readonly uniquenessClaim: "ROSTER_OBSERVATION_INSTANT_ONLY"
  readonly historicalUniquenessClaimed: false
  readonly crossExecutionReplayPreventionClaimed: false
  readonly durableCommitRequiresFreshTerminalObservation: true
  readonly sourceCommitA: string
  readonly registrationCommitB: string
  readonly registrationAuthorityReceiptSha256: string
  readonly currentInvocationReceiptSha256: string
  readonly workflowContractSha256: string
  readonly workflowFileSha256: string
  readonly trackedBytesManifestSha256: string
  readonly workflowApiPath: string
  readonly workflowRunId: number
  readonly workflowRunAttempt: typeof S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT
  readonly stage: S2SConfirmatoryJobStage
  readonly currentJobId: S2SConfirmatoryJobId
  readonly currentJobDatabaseId: number
  readonly predecessorJobDatabaseIds: ReadonlyArray<number>
  readonly workflowRunCreatedAt: string
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly invocationCapturedAtUnixSeconds: number
  readonly observations: {
    readonly runStart: S2SCurrentRunObservationEvidence
    readonly jobs: S2SCurrentRunObservationEvidence
    readonly runsForHead: S2SCurrentRunObservationEvidence
    readonly runEnd: S2SCurrentRunObservationEvidence
  }
  readonly receiptSha256: string
}

const S2S_CURRENT_RUN_STAGE_AUTHORITY_BRAND: unique symbol = Symbol(
  "hswm/S2SCurrentRunStageAuthority"
)

export interface S2SCurrentRunStageAuthority {
  readonly [S2S_CURRENT_RUN_STAGE_AUTHORITY_BRAND]: true
}

interface S2SCurrentRunBracketSnapshot {
  readonly runStart: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly runsForHead: S2SGitHubObservation<S2SGitHubWorkflowRunsProjection>
  readonly runEnd: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
}

interface S2SCurrentRunStageSnapshot {
  readonly evidence: S2SCurrentRunStageEvidence
  readonly invocationEvidence: S2SCurrentInvocationEvidence
  readonly invocationEventBytes: Uint8Array
  readonly bracket: S2SCurrentRunBracketSnapshot
}

export interface S2SCurrentRunReplaySnapshot {
  readonly currentRunEvidence: S2SCurrentRunStageEvidence
  readonly invocationEvidence: S2SCurrentInvocationEvidence
  /** A new copy is returned on every access. */
  readonly readInvocationEventBytes: () => Uint8Array
  readonly bracket: S2SCurrentRunBracketSnapshot
  readonly totalRawByteLength: number
}

export class S2SCurrentRunReplaySnapshotError extends Data.TaggedError(
  "S2SCurrentRunReplaySnapshotError"
)<{
  readonly reason:
    | "INVOCATION_EVENT_DRIFT"
    | "OBSERVATION_REVALIDATION_FAILED"
    | "RECEIPT_BINDING_MISMATCH"
    | "RAW_BYTE_BUDGET_EXCEEDED"
  readonly phase:
    | "CURRENT_RUN_EVIDENCE"
    | "INVOCATION_EVENT"
    | "RUN_START"
    | "JOBS"
    | "RUNS_FOR_HEAD"
    | "RUN_END"
  readonly causeTag: string | null
}> {}

const S2S_CURRENT_RUN_STAGE_SNAPSHOTS = new WeakMap<
  object,
  S2SCurrentRunStageSnapshot
>()

export const inspectS2SCurrentRunStageAuthority = (
  input: unknown
): Either.Either<S2SCurrentRunStageEvidence, S2SCurrentRunInputError> => {
  try {
    if (input === null || typeof input !== "object") {
      return Either.left(
        new S2SCurrentRunInputError({
          reason: "INVALID_CURRENT_RUN_AUTHORITY",
          detail: "current-run authority is not an issued object"
        })
      )
    }
    const snapshot = S2S_CURRENT_RUN_STAGE_SNAPSHOTS.get(input)
    return snapshot === undefined
      ? Either.left(
          new S2SCurrentRunInputError({
            reason: "INVALID_CURRENT_RUN_AUTHORITY",
            detail: "current-run authority was not issued by this module"
          })
        )
      : Either.right(snapshot.evidence)
  } catch {
    return Either.left(
      new S2SCurrentRunInputError({
        reason: "INVALID_CURRENT_RUN_AUTHORITY",
        detail: "current-run authority inspection failed closed"
      })
    )
  }
}

export class S2SCurrentRunStage extends Context.Tag(
  "hswm/S2S/CurrentRunStage"
)<
  S2SCurrentRunStage,
  { readonly authority: S2SCurrentRunStageAuthority }
>() {}

class S2SRegistrationAuthorityInput extends Context.Tag(
  "hswm/S2S/RegistrationAuthorityInput"
)<S2SRegistrationAuthorityInput, { readonly authority: unknown }>() {}

interface ReviewedWorkflowFixture {
  readonly workflowApiPath: string
  readonly workflowFileSha256: string
}

type WorkflowSourcePolicy =
  | { readonly status: "OPEN_UNTIL_WORKFLOW_BYTES_EXIST" }
  | ({ readonly status: "PINNED_REVIEWED_WORKFLOW_BYTES" } &
      ReviewedWorkflowFixture)

type PinnedWorkflowSourcePolicy = Extract<
  WorkflowSourcePolicy,
  { readonly status: "PINNED_REVIEWED_WORKFLOW_BYTES" }
>

const PRODUCTION_WORKFLOW_SOURCE_POLICY: WorkflowSourcePolicy = Object.freeze({
  status: "OPEN_UNTIL_WORKFLOW_BYTES_EXIST"
})

/**
 * Root-private, non-authorizing preflight. It exposes only whether the
 * production workflow-source gate is closed; it never returns reviewed bytes,
 * a fixture, or an authority bearer.
 */
export const requireS2SProductionWorkflowSourcePolicy = (): Either.Either<
  void,
  S2SCurrentRunInputError
> =>
  PRODUCTION_WORKFLOW_SOURCE_POLICY.status ===
  "OPEN_UNTIL_WORKFLOW_BYTES_EXIST"
    ? Either.left(
        new S2SCurrentRunInputError({
          reason: "WORKFLOW_SOURCE_BYTES_OPEN",
          detail: "reviewed workflow source bytes are not pinned"
        })
      )
    : Either.right(undefined)

interface BoundRunInput {
  readonly registration: S2SRegistrationCommitAuthorityEvidence
  readonly invocation: S2SCurrentInvocationEvidence
  readonly invocationEventBytes: Uint8Array
  readonly workflowBinding: S2SRegistrationWorkflowManifestBinding
}

interface RunAuthorityPolicyInput extends BoundRunInput {
  readonly runStart: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly runsForHead: S2SGitHubObservation<S2SGitHubWorkflowRunsProjection>
  readonly runEnd: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
}

interface RunAuthorityCandidate extends S2SCurrentRunStageSnapshot {}

const inputFailure = (
  reason: S2SCurrentRunInputError["reason"],
  detail: string
): S2SCurrentRunInputError => new S2SCurrentRunInputError({ reason, detail })

const policyFailure = (
  reason: S2SCurrentRunPolicyError["reason"],
  path: string,
  detail: string
): S2SCurrentRunPolicyError =>
  new S2SCurrentRunPolicyError({ reason, path, detail })

const acquisitionFailure = (
  phase: S2SCurrentRunAcquisitionError["phase"],
  reason: S2SCurrentRunAcquisitionError["reason"],
  causeTag: string
): S2SCurrentRunAcquisitionError =>
  new S2SCurrentRunAcquisitionError({ phase, reason, causeTag })

const fromEither = <Success, Failure>(
  value: Either.Either<Success, Failure>
): Effect.Effect<Success, Failure> =>
  Either.isLeft(value) ? Effect.fail(value.left) : Effect.succeed(value.right)

const isPlainExactRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>
): input is Readonly<Record<string, unknown>> => {
  if (input === null || typeof input !== "object") return false
  const prototype = Object.getPrototypeOf(input)
  if (prototype !== Object.prototype && prototype !== null) return false
  const ownKeys = Reflect.ownKeys(input)
  if (ownKeys.some((key) => typeof key !== "string")) return false
  const keys = ownKeys
    .filter((key): key is string => typeof key === "string")
    .sort()
  const expected = [...expectedKeys].sort()
  if (
    keys.length !== expected.length ||
    keys.some((key, index) => key !== expected[index])
  ) {
    return false
  }
  return keys.every((key) => {
    const descriptor = Object.getOwnPropertyDescriptor(input, key)
    return (
      descriptor !== undefined &&
      descriptor.enumerable === true &&
      "value" in descriptor
    )
  })
}

const snapshotReviewedWorkflowFixture = (
  input: unknown
): Either.Either<ReviewedWorkflowFixture, S2SCurrentRunInputError> => {
  try {
    if (
      !isPlainExactRecord(input, ["workflowApiPath", "workflowFileSha256"])
    ) {
      return Either.left(
        inputFailure(
          "REVIEWED_FIXTURE_REJECTED",
          "reviewed test fixture must be one exact plain data record"
        )
      )
    }
    const workflowApiPath = input["workflowApiPath"]
    const workflowFileSha256 = input["workflowFileSha256"]
    if (
      typeof workflowApiPath !== "string" ||
      !REVIEWED_WORKFLOW_API_PATHS.some((path) => path === workflowApiPath) ||
      typeof workflowFileSha256 !== "string" ||
      !SHA256_PATTERN.test(workflowFileSha256)
    ) {
      return Either.left(
        inputFailure(
          "REVIEWED_FIXTURE_REJECTED",
          "reviewed test workflow path or SHA-256 is not canonical"
        )
      )
    }
    return Either.right(
      Object.freeze({ workflowApiPath, workflowFileSha256 })
    )
  } catch {
    return Either.left(
      inputFailure(
        "REVIEWED_FIXTURE_REJECTED",
        "reviewed test fixture inspection failed closed"
      )
    )
  }
}

const canonicalHashMatches = (
  value: Readonly<Record<string, unknown>>,
  receiptSha256: string
): boolean => {
  const outcome = canonicalS2SControlSha256(value)
  return Either.isRight(outcome) && outcome.right === receiptSha256
}

const inspectBoundRunInput = (
  registrationAuthority: unknown,
  invocationAuthority: unknown,
  workflowPolicy: WorkflowSourcePolicy
): Either.Either<BoundRunInput, S2SCurrentRunInputError> => {
  const registration = inspectS2SRegistrationCommitAuthority(
    registrationAuthority
  )
  if (Either.isLeft(registration)) {
    return Either.left(
      inputFailure(
        "REGISTRATION_AUTHORITY_REJECTED",
        "registration-B authority is not module-authentic"
      )
    )
  }
  const invocation = inspectS2SCurrentInvocationAuthority(invocationAuthority)
  if (Either.isLeft(invocation)) {
    return Either.left(
      inputFailure(
        "INVOCATION_AUTHORITY_REJECTED",
        "current invocation authority is not module-authentic"
      )
    )
  }
  const invocationEventBytes = readS2SCurrentInvocationEventBytes(
    invocationAuthority
  )
  if (Either.isLeft(invocationEventBytes)) {
    return Either.left(
      inputFailure(
        "INVOCATION_AUTHORITY_REJECTED",
        "current invocation event bytes are not module-authentic"
      )
    )
  }
  const registrationEvidence = registration.right
  const invocationEvidence = invocation.right
  if (
    invocationEventBytes.right.byteLength !==
      invocationEvidence.eventBodyByteLength ||
    rawS2SFileSha256(invocationEventBytes.right) !==
      invocationEvidence.eventBodySha256
  ) {
    return Either.left(
      inputFailure(
        "INVOCATION_AUTHORITY_REJECTED",
        "current invocation event bytes drifted from their evidence"
      )
    )
  }
  if (
    registrationEvidence.sourceCommitA !== invocationEvidence.pushBeforeSha ||
    registrationEvidence.registrationCommitB !==
      invocationEvidence.pushAfterSha ||
    invocationEvidence.environmentProjection.commitSha !==
      registrationEvidence.registrationCommitB ||
    invocationEvidence.environmentProjection.workflowSourceCommitSha !==
      registrationEvidence.registrationCommitB
  ) {
    return Either.left(
      inputFailure(
        "REGISTRATION_INVOCATION_MISMATCH",
        "registration A/B does not match the current push invocation"
      )
    )
  }
  const contractHash = s2sConfirmatoryWorkflowContractSha256()
  if (
    Either.isLeft(contractHash) ||
    invocationEvidence.workflowContractSha256 !== contractHash.right
  ) {
    return Either.left(
      inputFailure(
        "WORKFLOW_CONTRACT_MISMATCH",
        "current invocation does not bind the checked-in workflow contract"
      )
    )
  }
  if (workflowPolicy.status === "OPEN_UNTIL_WORKFLOW_BYTES_EXIST") {
    return Either.left(
      inputFailure(
        "WORKFLOW_SOURCE_BYTES_OPEN",
        "reviewed workflow source bytes are not pinned"
      )
    )
  }
  const binding = inspectS2SRegistrationWorkflowManifestBinding(
    registrationAuthority
  )
  if (Either.isLeft(binding)) {
    return Either.left(
      inputFailure(
        "WORKFLOW_BINDING_REJECTED",
        "source A does not bind one exact workflow blob"
      )
    )
  }
  if (
    binding.right.workflowPath !== S2S_CONFIRMATORY_WORKFLOW_PATH ||
    binding.right.mode !== "100644" ||
    binding.right.objectType !== "blob" ||
    binding.right.workflowFileSha256 !== workflowPolicy.workflowFileSha256 ||
    binding.right.trackedBytesManifestSha256 !==
      registrationEvidence.trackedBytesManifestSha256
  ) {
    return Either.left(
      inputFailure(
        "WORKFLOW_HASH_MISMATCH",
        "reviewed workflow bytes do not match the source-A manifest binding"
      )
    )
  }
  return Either.right(
    Object.freeze({
      registration: registrationEvidence,
      invocation: invocationEvidence,
      invocationEventBytes: new Uint8Array(invocationEventBytes.right),
      workflowBinding: binding.right
    })
  )
}

const observationEvidence = (
  observation: S2SGitHubObservation<
    | S2SGitHubWorkflowRunProjection
    | S2SGitHubWorkflowJobsProjection
    | S2SGitHubWorkflowRunsProjection
  >
): S2SCurrentRunObservationEvidence =>
  Object.freeze({
    receiptSha256: observation.receipt.receiptSha256,
    githubRequestId: observation.receipt.githubRequestId,
    observedAtUnixSeconds: observation.receipt.observedAtUnixSeconds
  })

const hasExpectedRunIdentity = (
  run: S2SGitHubWorkflowRunProjection,
  invocation: S2SCurrentInvocationEvidence,
  workflowApiPath: string
): boolean =>
  run.id === invocation.workflowRunId &&
  run.runAttempt === S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT &&
  run.repository === S2S_CONFIRMATORY_REPOSITORY &&
  run.headRepository === S2S_CONFIRMATORY_REPOSITORY &&
  run.headSha === invocation.pushAfterSha &&
  run.name === S2S_CONFIRMATORY_WORKFLOW_NAME &&
  run.path === workflowApiPath &&
  run.event === S2S_CONFIRMATORY_EVENT &&
  run.headBranch === S2S_CONFIRMATORY_BRANCH

const sameImmutableRunIdentity = (
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
  left.headBranch === right.headBranch &&
  left.createdAt === right.createdAt &&
  left.createdAtUnixSeconds === right.createdAtUnixSeconds

const validateTrustedInputEvidence = (
  input: RunAuthorityPolicyInput,
  reviewed: ReviewedWorkflowFixture
): S2SCurrentRunPolicyError | undefined => {
  const { registration, invocation, workflowBinding } = input
  if (
    !GIT_SHA_PATTERN.test(registration.sourceCommitA) ||
    !GIT_SHA_PATTERN.test(registration.registrationCommitB) ||
    registration.sourceCommitA === registration.registrationCommitB ||
    !SHA256_PATTERN.test(registration.receiptSha256) ||
    !SHA256_PATTERN.test(invocation.receiptSha256) ||
    !SHA256_PATTERN.test(invocation.workflowContractSha256) ||
    !SHA256_PATTERN.test(registration.trackedBytesManifestSha256) ||
    !SHA256_PATTERN.test(workflowBinding.workflowFileSha256) ||
    registration.sourceCommitA !== invocation.pushBeforeSha ||
    registration.registrationCommitB !== invocation.pushAfterSha ||
    invocation.environmentProjection.commitSha !==
      registration.registrationCommitB ||
    invocation.environmentProjection.workflowSourceCommitSha !==
      registration.registrationCommitB ||
    invocation.workflowPath !== S2S_CONFIRMATORY_WORKFLOW_PATH ||
    invocation.workflowRunAttempt !== S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT ||
    S2S_CONFIRMATORY_STAGE_CONTRACTS[invocation.stage].jobId !==
      invocation.jobId ||
    workflowBinding.workflowPath !== S2S_CONFIRMATORY_WORKFLOW_PATH ||
    workflowBinding.mode !== "100644" ||
    workflowBinding.objectType !== "blob" ||
    workflowBinding.workflowFileSha256 !== reviewed.workflowFileSha256 ||
    workflowBinding.trackedBytesManifestSha256 !==
      registration.trackedBytesManifestSha256
  ) {
    return policyFailure(
      "INPUT_EVIDENCE_REJECTED",
      "$input",
      "registration, invocation, or workflow evidence is inconsistent"
    )
  }
  const contractHash = s2sConfirmatoryWorkflowContractSha256()
  if (
    Either.isLeft(contractHash) ||
    contractHash.right !== invocation.workflowContractSha256
  ) {
    return policyFailure(
      "INPUT_EVIDENCE_REJECTED",
      "$input.invocation.workflowContractSha256",
      "workflow contract digest is inconsistent"
    )
  }
  const { receiptSha256: registrationReceipt, ...registrationCore } =
    registration
  const { receiptSha256: invocationReceipt, ...invocationCore } = invocation
  if (
    !canonicalHashMatches(registrationCore, registrationReceipt) ||
    !canonicalHashMatches(invocationCore, invocationReceipt)
  ) {
    return policyFailure(
      "INPUT_EVIDENCE_REJECTED",
      "$input",
      "authority evidence self-hash is inconsistent"
    )
  }
  return undefined
}

const classifyRunAuthorityPolicy = (
  input: RunAuthorityPolicyInput,
  reviewed: ReviewedWorkflowFixture
): Either.Either<RunAuthorityCandidate, S2SCurrentRunPolicyError> => {
  try {
    const inputEvidenceFailure = validateTrustedInputEvidence(input, reviewed)
    if (inputEvidenceFailure !== undefined) {
      return Either.left(inputEvidenceFailure)
    }
    const observations = [
      input.runStart,
      input.jobs,
      input.runsForHead,
      input.runEnd
    ] as const
    const requestIds = observations.map(
      (observation) => observation.receipt.githubRequestId
    )
    if (new Set(requestIds).size !== observations.length) {
      return Either.left(
        policyFailure(
          "REQUEST_ID_REUSED",
          "$observations",
          "the four GitHub requests must have pairwise-distinct request IDs"
        )
      )
    }
    const observedAt = [
      input.runStart.receipt.observedAtUnixSeconds,
      input.jobs.receipt.observedAtUnixSeconds,
      input.runsForHead.receipt.observedAtUnixSeconds,
      input.runEnd.receipt.observedAtUnixSeconds
    ] as const
    if (
      input.invocation.capturedAtUnixSeconds > observedAt[0] ||
      observedAt.some(
        (timestamp, index) =>
          index > 0 && timestamp < (observedAt[index - 1] ?? 0)
      )
    ) {
      return Either.left(
        policyFailure(
          "OBSERVATION_ORDER_INVALID",
          "$observations",
          "invocation capture and bracket observations are not nondecreasing"
        )
      )
    }
    const startRun = input.runStart.receipt.projection
    const endRun = input.runEnd.receipt.projection
    const rosterProjection = input.runsForHead.receipt.projection
    if (rosterProjection.totalCount === 0) {
      return Either.left(
        policyFailure(
          "RUN_MULTIPLICITY_ZERO",
          "$runsForHead",
          "the exact-head roster contains no workflow run"
        )
      )
    }
    if (
      rosterProjection.totalCount !== 1 ||
      rosterProjection.workflowRuns.length !== 1
    ) {
      return Either.left(
        policyFailure(
          "RUN_MULTIPLICITY_MULTIPLE",
          "$runsForHead",
          "the exact-head roster contains more than one workflow run"
        )
      )
    }
    const rosterRun = rosterProjection.workflowRuns[0]
    if (rosterRun === undefined || rosterRun.id !== input.invocation.workflowRunId) {
      return Either.left(
        policyFailure(
          "CURRENT_RUN_MISMATCH",
          "$runsForHead.workflowRuns[0]",
          "the sole roster row is not the current invocation run"
        )
      )
    }
    if (
      startRun.path !== reviewed.workflowApiPath ||
      rosterRun.path !== reviewed.workflowApiPath ||
      endRun.path !== reviewed.workflowApiPath
    ) {
      return Either.left(
        policyFailure(
          "WORKFLOW_PATH_REJECTED",
          "$workflow.path",
          "workflow API path does not match the reviewed representation"
        )
      )
    }
    if (
      !hasExpectedRunIdentity(
        startRun,
        input.invocation,
        reviewed.workflowApiPath
      ) ||
      !hasExpectedRunIdentity(
        rosterRun,
        input.invocation,
        reviewed.workflowApiPath
      ) ||
      !hasExpectedRunIdentity(
        endRun,
        input.invocation,
        reviewed.workflowApiPath
      ) ||
      !sameImmutableRunIdentity(startRun, rosterRun) ||
      !sameImmutableRunIdentity(rosterRun, endRun)
    ) {
      return Either.left(
        policyFailure(
          "RUN_IDENTITY_DRIFT",
          "$workflow",
          "immutable workflow-run identity drifted across the bracket"
        )
      )
    }
    if (
      startRun.status !== "in_progress" ||
      startRun.conclusion !== null ||
      endRun.status !== "in_progress" ||
      endRun.conclusion !== null ||
      rosterRun.status === "completed" ||
      rosterRun.conclusion !== null
    ) {
      return Either.left(
        policyFailure(
          "RUN_STATE_REJECTED",
          "$workflow.status",
          "direct reads must remain active and the roster cannot contradict them with a terminal state"
        )
      )
    }
    if (
      startRun.createdAtUnixSeconds >
        input.invocation.capturedAtUnixSeconds ||
      startRun.createdAtUnixSeconds > observedAt[0]
    ) {
      return Either.left(
        policyFailure(
          "OBSERVATION_ORDER_INVALID",
          "$workflow.createdAt",
          "workflow creation occurs after invocation capture or observation"
        )
      )
    }
    const jobProjection = input.jobs.receipt.projection
    if (
      jobProjection.totalCount !== S2S_CONFIRMATORY_JOB_STAGES.length ||
      jobProjection.jobs.length !== S2S_CONFIRMATORY_JOB_STAGES.length
    ) {
      return Either.left(
        policyFailure(
          "JOB_ROSTER_REJECTED",
          "$jobs",
          "the attempt-one job roster must contain exactly the three fixed jobs"
        )
      )
    }
    const jobsByStage = new Map<
      S2SConfirmatoryJobStage,
      S2SGitHubWorkflowJobsProjection["jobs"][number]
    >()
    for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
      const expectedName = S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobName
      const matches = jobProjection.jobs.filter(
        (job) => job.name === expectedName
      )
      if (matches.length !== 1 || matches[0] === undefined) {
        return Either.left(
          policyFailure(
            "JOB_ROSTER_REJECTED",
            "$jobs",
            "each fixed job name must occur exactly once"
          )
        )
      }
      jobsByStage.set(stage, matches[0])
    }
    if (
      jobProjection.jobs.some(
        (job) =>
          job.runId !== input.invocation.workflowRunId ||
          job.runAttempt !== S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT ||
          job.headSha !== input.invocation.pushAfterSha ||
          job.startedAtUnixSeconds < startRun.createdAtUnixSeconds ||
          job.startedAtUnixSeconds > observedAt[1]
      )
    ) {
      return Either.left(
        policyFailure(
          "JOB_ROSTER_REJECTED",
          "$jobs",
          "job run, attempt, head, or timestamp identity is inconsistent"
        )
      )
    }
    const stageIndex = S2S_CONFIRMATORY_JOB_STAGES.indexOf(
      input.invocation.stage
    )
    const currentJob = jobsByStage.get(input.invocation.stage)
    if (
      stageIndex < 0 ||
      currentJob === undefined ||
      currentJob.name !== input.invocation.jobId ||
      currentJob.status !== "in_progress" ||
      currentJob.conclusion !== null ||
      currentJob.completedAt !== null ||
      currentJob.completedAtUnixSeconds !== null ||
      currentJob.startedAtUnixSeconds >
        input.invocation.capturedAtUnixSeconds
    ) {
      return Either.left(
        policyFailure(
          "CURRENT_JOB_REJECTED",
          "$jobs.current",
          "the invocation job is not the sole active stage job"
        )
      )
    }
    const predecessorJobIds: Array<number> = []
    let previousCompletion = startRun.createdAtUnixSeconds
    for (let index = 0; index < stageIndex; index += 1) {
      const predecessorStage = S2S_CONFIRMATORY_JOB_STAGES[index]
      const predecessor =
        predecessorStage === undefined
          ? undefined
          : jobsByStage.get(predecessorStage)
      if (
        predecessor === undefined ||
        predecessor.status !== "completed" ||
        predecessor.conclusion !== "success" ||
        predecessor.completedAt === null ||
        predecessor.completedAtUnixSeconds === null ||
        predecessor.startedAtUnixSeconds < previousCompletion ||
        predecessor.completedAtUnixSeconds < predecessor.startedAtUnixSeconds ||
        predecessor.completedAtUnixSeconds > currentJob.startedAtUnixSeconds ||
        predecessor.completedAtUnixSeconds > observedAt[1]
      ) {
        return Either.left(
          policyFailure(
            "PREDECESSOR_REJECTED",
            "$jobs.predecessors",
            "each required predecessor must complete successfully in order"
          )
        )
      }
      predecessorJobIds.push(predecessor.id)
      previousCompletion = predecessor.completedAtUnixSeconds
    }
    for (
      let index = stageIndex + 1;
      index < S2S_CONFIRMATORY_JOB_STAGES.length;
      index += 1
    ) {
      const laterStage = S2S_CONFIRMATORY_JOB_STAGES[index]
      const later = laterStage === undefined ? undefined : jobsByStage.get(laterStage)
      if (
        later === undefined ||
        !NOT_STARTED_JOB_STATUSES.has(later.status) ||
        later.conclusion !== null ||
        later.completedAt !== null ||
        later.completedAtUnixSeconds !== null
      ) {
        return Either.left(
          policyFailure(
            "LATER_JOB_REJECTED",
            "$jobs.later",
            "later stage jobs must remain uncompleted and inactive"
          )
        )
      }
    }
    const frozenPredecessorJobIds = Object.freeze([...predecessorJobIds])
    const frozenObservationEvidence = Object.freeze({
      runStart: observationEvidence(input.runStart),
      jobs: observationEvidence(input.jobs),
      runsForHead: observationEvidence(input.runsForHead),
      runEnd: observationEvidence(input.runEnd)
    })
    const evidenceCore = Object.freeze({
      schemaVersion: S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
      authorityScope: "PROCESS_LOCAL_STAGE_ENTRY" as const,
      uniquenessClaim: "ROSTER_OBSERVATION_INSTANT_ONLY" as const,
      historicalUniquenessClaimed: false as const,
      crossExecutionReplayPreventionClaimed: false as const,
      durableCommitRequiresFreshTerminalObservation: true as const,
      sourceCommitA: input.registration.sourceCommitA,
      registrationCommitB: input.registration.registrationCommitB,
      registrationAuthorityReceiptSha256: input.registration.receiptSha256,
      currentInvocationReceiptSha256: input.invocation.receiptSha256,
      workflowContractSha256: input.invocation.workflowContractSha256,
      workflowFileSha256: input.workflowBinding.workflowFileSha256,
      trackedBytesManifestSha256:
        input.workflowBinding.trackedBytesManifestSha256,
      workflowApiPath: reviewed.workflowApiPath,
      workflowRunId: input.invocation.workflowRunId,
      workflowRunAttempt: S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT,
      stage: input.invocation.stage,
      currentJobId: input.invocation.jobId,
      currentJobDatabaseId: currentJob.id,
      predecessorJobDatabaseIds: frozenPredecessorJobIds,
      workflowRunCreatedAt: startRun.createdAt,
      workflowRunCreatedAtUnixSeconds: startRun.createdAtUnixSeconds,
      invocationCapturedAtUnixSeconds:
        input.invocation.capturedAtUnixSeconds,
      observations: frozenObservationEvidence
    })
    const evidenceHash = canonicalS2SControlSha256(evidenceCore)
    if (Either.isLeft(evidenceHash)) {
      return Either.left(
        policyFailure(
          "EVIDENCE_NOT_CANONICAL",
          "$evidence",
          "current-run evidence cannot be canonically hashed"
        )
      )
    }
    const evidence: S2SCurrentRunStageEvidence = Object.freeze({
      ...evidenceCore,
      receiptSha256: evidenceHash.right
    })
    const bracket: S2SCurrentRunBracketSnapshot = Object.freeze({
      runStart: input.runStart,
      jobs: input.jobs,
      runsForHead: input.runsForHead,
      runEnd: input.runEnd
    })
    return Either.right(
      Object.freeze({
        evidence,
        invocationEvidence: input.invocation,
        invocationEventBytes: new Uint8Array(input.invocationEventBytes),
        bracket
      })
    )
  } catch {
    return Either.left(
      policyFailure(
        "INPUT_EVIDENCE_REJECTED",
        "$input",
        "current-run policy classification failed closed"
      )
    )
  }
}

const observerCauseTag = (error: unknown): string =>
  error !== null &&
  typeof error === "object" &&
  "_tag" in error &&
  typeof error._tag === "string"
    ? error._tag
    : "UnknownObserverFailure"

const observeAndRevalidateRun = (
  github: S2SGitHubObserver["Type"],
  runId: number,
  phase: "RUN_START" | "RUN_END"
) =>
  github.observeWorkflowRun(runId).pipe(
    Effect.mapError((error) =>
      acquisitionFailure(
        phase,
        "OBSERVATION_FAILED",
        observerCauseTag(error)
      )
    ),
    Effect.flatMap((observation) =>
      validateS2SGitHubWorkflowRunObservation(observation, runId).pipe(
        Effect.mapError((error) =>
          acquisitionFailure(phase, "REVALIDATION_FAILED", error._tag)
        )
      )
    )
  )

const acquireRunAuthorityCandidate = (
  github: S2SGitHubObserver["Type"],
  bound: BoundRunInput,
  reviewed: ReviewedWorkflowFixture
): Effect.Effect<
  RunAuthorityCandidate,
  S2SCurrentRunAcquisitionError | S2SCurrentRunPolicyError
> =>
  Effect.gen(function* () {
    const runStart = yield* observeAndRevalidateRun(
      github,
      bound.invocation.workflowRunId,
      "RUN_START"
    )
    const jobs = yield* github
      .observeWorkflowAttemptJobs(bound.invocation.workflowRunId)
      .pipe(
        Effect.mapError((error) =>
          acquisitionFailure(
            "JOBS",
            "OBSERVATION_FAILED",
            observerCauseTag(error)
          )
        ),
        Effect.flatMap((observation) =>
          validateS2SGitHubWorkflowAttemptJobsObservation(
            observation,
            bound.invocation.workflowRunId
          ).pipe(
            Effect.mapError((error) =>
              acquisitionFailure("JOBS", "REVALIDATION_FAILED", error._tag)
            )
          )
        )
      )
    const runsForHead = yield* github
      .observeWorkflowRunsForHead(bound.registration.registrationCommitB)
      .pipe(
        Effect.mapError((error) =>
          acquisitionFailure(
            "RUNS_FOR_HEAD",
            "OBSERVATION_FAILED",
            observerCauseTag(error)
          )
        ),
        Effect.flatMap((observation) =>
          validateS2SGitHubWorkflowRunsForHeadObservation(
            observation,
            bound.registration.registrationCommitB
          ).pipe(
            Effect.mapError((error) =>
              acquisitionFailure(
                "RUNS_FOR_HEAD",
                "REVALIDATION_FAILED",
                error._tag
              )
            )
          )
        )
      )
    const runEnd = yield* observeAndRevalidateRun(
      github,
      bound.invocation.workflowRunId,
      "RUN_END"
    )
    return yield* fromEither(
      classifyRunAuthorityPolicy(
        Object.freeze({ ...bound, runStart, jobs, runsForHead, runEnd }),
        reviewed
      )
    )
  }).pipe(
    Effect.timeoutFail({
      duration: S2S_CURRENT_RUN_BRACKET_TIMEOUT_MILLIS,
      onTimeout: () =>
        acquisitionFailure(
          "BRACKET",
          "BRACKET_TIMED_OUT",
          "S2SCurrentRunBracketTimeout"
        )
    })
  )

const issueCurrentRunStageAuthority = (
  candidate: RunAuthorityCandidate
): S2SCurrentRunStageAuthority => {
  const authority: S2SCurrentRunStageAuthority = Object.freeze({
    [S2S_CURRENT_RUN_STAGE_AUTHORITY_BRAND]: true as const
  })
  S2S_CURRENT_RUN_STAGE_SNAPSHOTS.set(authority, candidate)
  return authority
}

const replayFailure = (
  reason: S2SCurrentRunReplaySnapshotError["reason"],
  phase: S2SCurrentRunReplaySnapshotError["phase"],
  causeTag: string | null = null
): S2SCurrentRunReplaySnapshotError =>
  new S2SCurrentRunReplaySnapshotError({ reason, phase, causeTag })

const compactObservationMatches = (
  expected: S2SCurrentRunObservationEvidence,
  observation: S2SGitHubObservation
): boolean =>
  expected.receiptSha256 === observation.receipt.receiptSha256 &&
  expected.githubRequestId === observation.receipt.githubRequestId &&
  expected.observedAtUnixSeconds === observation.receipt.observedAtUnixSeconds

const materializeS2SCurrentRunReplaySnapshot = (
  snapshot: S2SCurrentRunStageSnapshot
): Effect.Effect<
  S2SCurrentRunReplaySnapshot,
  S2SCurrentRunReplaySnapshotError
> =>
  Effect.gen(function* () {
    const invocationEventBytes = new Uint8Array(snapshot.invocationEventBytes)
    const { receiptSha256: invocationReceipt, ...invocationCore } =
      snapshot.invocationEvidence
    if (
      invocationEventBytes.byteLength !==
        snapshot.invocationEvidence.eventBodyByteLength ||
      invocationEventBytes.byteLength > S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES ||
      rawS2SFileSha256(invocationEventBytes) !==
        snapshot.invocationEvidence.eventBodySha256 ||
      !canonicalHashMatches(invocationCore, invocationReceipt)
    ) {
      return yield* replayFailure(
        "INVOCATION_EVENT_DRIFT",
        "INVOCATION_EVENT"
      )
    }
    const { receiptSha256: currentRunReceipt, ...currentRunCore } =
      snapshot.evidence
    if (!canonicalHashMatches(currentRunCore, currentRunReceipt)) {
      return yield* replayFailure(
        "RECEIPT_BINDING_MISMATCH",
        "CURRENT_RUN_EVIDENCE"
      )
    }
    const runStart = yield* validateS2SGitHubWorkflowRunObservation(
      snapshot.bracket.runStart,
      snapshot.evidence.workflowRunId
    ).pipe(
      Effect.mapError((error) =>
        replayFailure(
          "OBSERVATION_REVALIDATION_FAILED",
          "RUN_START",
          error._tag
        )
      )
    )
    const jobs = yield* validateS2SGitHubWorkflowAttemptJobsObservation(
      snapshot.bracket.jobs,
      snapshot.evidence.workflowRunId
    ).pipe(
      Effect.mapError((error) =>
        replayFailure(
          "OBSERVATION_REVALIDATION_FAILED",
          "JOBS",
          error._tag
        )
      )
    )
    const runsForHead =
      yield* validateS2SGitHubWorkflowRunsForHeadObservation(
        snapshot.bracket.runsForHead,
        snapshot.evidence.registrationCommitB
      ).pipe(
        Effect.mapError((error) =>
          replayFailure(
            "OBSERVATION_REVALIDATION_FAILED",
            "RUNS_FOR_HEAD",
            error._tag
          )
        )
      )
    const runEnd = yield* validateS2SGitHubWorkflowRunObservation(
      snapshot.bracket.runEnd,
      snapshot.evidence.workflowRunId
    ).pipe(
      Effect.mapError((error) =>
        replayFailure(
          "OBSERVATION_REVALIDATION_FAILED",
          "RUN_END",
          error._tag
        )
      )
    )
    const bindings = [
      ["RUN_START", snapshot.evidence.observations.runStart, runStart],
      ["JOBS", snapshot.evidence.observations.jobs, jobs],
      [
        "RUNS_FOR_HEAD",
        snapshot.evidence.observations.runsForHead,
        runsForHead
      ],
      ["RUN_END", snapshot.evidence.observations.runEnd, runEnd]
    ] as const
    for (const [phase, expected, observation] of bindings) {
      if (!compactObservationMatches(expected, observation)) {
        return yield* replayFailure(
          "RECEIPT_BINDING_MISMATCH",
          phase
        )
      }
    }
    const totalRawByteLength =
      invocationEventBytes.byteLength +
      runStart.receipt.rawBodyByteLength +
      jobs.receipt.rawBodyByteLength +
      runsForHead.receipt.rawBodyByteLength +
      runEnd.receipt.rawBodyByteLength
    if (
      !Number.isSafeInteger(totalRawByteLength) ||
      totalRawByteLength < 1 ||
      totalRawByteLength > S2S_CURRENT_RUN_REPLAY_MAX_RAW_BYTES
    ) {
      return yield* replayFailure(
        "RAW_BYTE_BUDGET_EXCEEDED",
        "CURRENT_RUN_EVIDENCE"
      )
    }
    return Object.freeze({
      currentRunEvidence: snapshot.evidence,
      invocationEvidence: snapshot.invocationEvidence,
      readInvocationEventBytes: () => new Uint8Array(invocationEventBytes),
      bracket: Object.freeze({ runStart, jobs, runsForHead, runEnd }),
      totalRawByteLength
    })
  })

const inspectCurrentRunService = (
  input: unknown
): Either.Either<S2SCurrentRunStageSnapshot, S2SCurrentRunInputError> => {
  try {
    if (!isPlainExactRecord(input, ["authority"])) {
      return Either.left(
        inputFailure(
          "INVALID_CURRENT_RUN_AUTHORITY",
          "current-run service is not one exact data record"
        )
      )
    }
    const descriptor = Object.getOwnPropertyDescriptor(input, "authority")
    if (descriptor === undefined || !("value" in descriptor)) {
      return Either.left(
        inputFailure(
          "INVALID_CURRENT_RUN_AUTHORITY",
          "current-run service authority is not a data property"
        )
      )
    }
    const authority = descriptor.value
    if (authority === null || typeof authority !== "object") {
      return Either.left(
        inputFailure(
          "INVALID_CURRENT_RUN_AUTHORITY",
          "current-run service authority is not an issued object"
        )
      )
    }
    const snapshot = S2S_CURRENT_RUN_STAGE_SNAPSHOTS.get(authority)
    return snapshot === undefined
      ? Either.left(
          inputFailure(
            "INVALID_CURRENT_RUN_AUTHORITY",
            "current-run service does not carry a module-issued authority"
          )
        )
      : Either.right(snapshot)
  } catch {
    return Either.left(
      inputFailure(
        "INVALID_CURRENT_RUN_AUTHORITY",
        "current-run service inspection failed closed"
      )
    )
  }
}

/**
 * Root-private, selector-free replay materializer. It can only inspect the
 * current Effect service and never exposes or accepts an authority bearer.
 */
export const snapshotS2SCurrentRunReplay: Effect.Effect<
  S2SCurrentRunReplaySnapshot,
  S2SCurrentRunInputError | S2SCurrentRunReplaySnapshotError,
  S2SCurrentRunStage
> = Effect.suspend(() =>
  Effect.gen(function* () {
    const current = yield* S2SCurrentRunStage
    const snapshot = yield* fromEither(inspectCurrentRunService(current))
    return yield* materializeS2SCurrentRunReplaySnapshot(snapshot)
  })
)

const makeOpenS2SCurrentRunStageLayer = () =>
  Layer.effect(
    S2SCurrentRunStage,
    Effect.gen(function* () {
      const registrationInput = yield* S2SRegistrationAuthorityInput
      const invocation = yield* S2SCurrentInvocation
      yield* fromEither(
        inspectBoundRunInput(
          registrationInput.authority,
          invocation.authority,
          PRODUCTION_WORKFLOW_SOURCE_POLICY
        )
      )
      return yield* Effect.dieMessage(
        "OPEN workflow policy unexpectedly admitted current-run issuance"
      )
    })
  )

const makePinnedS2SCurrentRunStageCoreLayer = (
  workflowPolicy: PinnedWorkflowSourcePolicy
) =>
  Layer.effect(
    S2SCurrentRunStage,
    Effect.gen(function* () {
      const registrationInput = yield* S2SRegistrationAuthorityInput
      const invocation = yield* S2SCurrentInvocation
      const bound = yield* fromEither(
        inspectBoundRunInput(
          registrationInput.authority,
          invocation.authority,
          workflowPolicy
        )
      )
      const github = yield* S2SGitHubObserver
      const candidate = yield* acquireRunAuthorityCandidate(
        github,
        bound,
        workflowPolicy
      )
      return S2SCurrentRunStage.of({
        authority: issueCurrentRunStageAuthority(candidate)
      })
    })
  )

/**
 * Closed production Layer graph. The constructor has no run-identity, observer,
 * or source-policy override; invocation and GitHub services are fixed to Live.
 * This boundary assumes a trusted same-process runtime and does not claim to
 * resist ambient `process.env` or `globalThis.fetch` monkeypatching. The Layer is
 * intentionally gate-closed while workflow source bytes remain OPEN.
 */
export const makeS2SCurrentRunStageAuthorityLiveLayer = (
  registrationAuthority: unknown,
  githubConfig: S2SGitHubLiveTransportConfig
) => {
  const registrationInput = Layer.succeed(
    S2SRegistrationAuthorityInput,
    S2SRegistrationAuthorityInput.of({ authority: registrationAuthority })
  )
  const invocationLive = S2SCurrentInvocationLive.pipe(
    Layer.mapError(() =>
      inputFailure(
        "INVOCATION_SOURCE_REJECTED",
        "live current-invocation capture failed closed"
      )
    )
  )
  if (
    PRODUCTION_WORKFLOW_SOURCE_POLICY.status ===
    "OPEN_UNTIL_WORKFLOW_BYTES_EXIST"
  ) {
    return makeOpenS2SCurrentRunStageLayer().pipe(
      Layer.provide([registrationInput, invocationLive])
    )
  }
  const githubObserverLive = S2SGitHubObserverLive.pipe(
    Layer.provide(
      makeS2SGitHubHttpTransportLiveLayer(githubConfig).pipe(
        Layer.mapError((error) =>
          acquisitionFailure(
            "CONFIGURE_GITHUB",
            "OBSERVATION_FAILED",
            error._tag
          )
        )
      )
    )
  )
  return makePinnedS2SCurrentRunStageCoreLayer(
    PRODUCTION_WORKFLOW_SOURCE_POLICY
  ).pipe(
    Layer.provide([registrationInput, invocationLive, githubObserverLive])
  )
}

/**
 * @internal TEST-ONLY, NON-AUTHORIZING.
 *
 * Exercises the authentic-input, four-read acquisition, revalidation, and
 * policy path against a caller-supplied test observer. Success is only `void`;
 * it never calls the private issuer or inserts into the authority WeakMap.
 */
export const probeS2SRunAuthorityAcquisitionForTest = (
  registrationAuthority: unknown,
  invocationAuthority: unknown,
  github: S2SGitHubObserver["Type"],
  reviewedFixture: unknown
): Effect.Effect<void, S2SCurrentRunError> =>
  Effect.suspend<void, S2SCurrentRunError, never>(() => {
    const reviewed = snapshotReviewedWorkflowFixture(reviewedFixture)
    if (Either.isLeft(reviewed)) return Effect.fail(reviewed.left)
    const testPolicy: PinnedWorkflowSourcePolicy = Object.freeze({
      status: "PINNED_REVIEWED_WORKFLOW_BYTES",
      ...reviewed.right
    })
    const bound = inspectBoundRunInput(
      registrationAuthority,
      invocationAuthority,
      testPolicy
    )
    if (Either.isLeft(bound)) return Effect.fail(bound.left)
    return acquireRunAuthorityCandidate(
      github,
      bound.right,
      reviewed.right
    ).pipe(
      Effect.flatMap(materializeS2SCurrentRunReplaySnapshot),
      Effect.asVoid
    )
  })
