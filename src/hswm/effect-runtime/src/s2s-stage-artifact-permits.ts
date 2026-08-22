import { Data, Effect, Either, Exit, Ref } from "effect"

import { canonicalS2SControlSha256 } from "./s2s-canonical.js"
import {
  inspectS2SCurrentRunStageAuthority,
  type S2SCurrentRunInputError,
  type S2SCurrentRunStageAuthority,
  type S2SCurrentRunStageEvidence
} from "./s2s-run-authority.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  type S2SConfirmatoryArtifactReadOperation,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"

export const S2S_STAGE_ARTIFACT_PERMIT_EVIDENCE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-stage-artifact-permit-evidence/v1" as const

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const REQUEST_ID_PATTERN = /^[\u0021-\u007e]{1,256}$/
const RFC3339_UTC_SECONDS_PATTERN =
  /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/

export type S2SStageArtifactLedgerPhase =
  | "CURRENT_RUN_RUN_START"
  | "CURRENT_RUN_JOBS"
  | "CURRENT_RUN_RUNS_FOR_HEAD"
  | "CURRENT_RUN_RUN_END"
  | "LOOKUP_RUN_START"
  | "LOOKUP_JOBS"
  | "LOOKUP_ARTIFACTS_1"
  | "LOOKUP_RUN_END_1"
  | "LOOKUP_ARTIFACTS_2"
  | "LOOKUP_RUN_END_2"
  | "LOOKUP_ARTIFACTS_3"
  | "LOOKUP_RUN_END_3"
  | "READBACK_RUN_START"
  | "READBACK_ARTIFACT"
  | "READBACK_DOWNLOAD_REDIRECT"
  | "READBACK_RUN_END"

export interface S2SStageArtifactLedgerEntry {
  readonly operation: "CURRENT_RUN_AUTHORITY" | S2SConfirmatoryArtifactReadOperation
  readonly phase: S2SStageArtifactLedgerPhase
  readonly githubRequestId: string
  readonly receiptSha256: string
  readonly observedAtUnixSeconds: number
}

export interface S2SStageArtifactPermitIdentity {
  readonly workflowRunId: number
  readonly workflowRunAttempt: 1
  readonly registrationCommitB: string
  readonly workflowApiPath: string
  readonly workflowRunCreatedAt: string
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly stage: S2SConfirmatoryJobStage
  readonly currentJobDatabaseId: number
  readonly predecessorJobDatabaseIds: ReadonlyArray<number>
}

export interface S2SStageArtifactPermitEvidence {
  readonly schemaVersion: typeof S2S_STAGE_ARTIFACT_PERMIT_EVIDENCE_SCHEMA_VERSION
  readonly authorityScope:
    | "TRUSTED_SINGLE_MODULE_CURRENT_JOB"
    | "TEST_ONLY_NON_AUTHORIZING"
  readonly authorizationClaimed: boolean
  readonly oneUseClaim:
    | "ONE_USE_PER_GENUINE_AUTHORITY_AND_PROCESS_IDENTITY_SLOT"
    | "MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE"
  readonly crossWorkerReplayPreventionClaimed: false
  readonly crossModuleCopyReplayPreventionClaimed: false
  readonly crossProcessReplayPreventionClaimed: false
  readonly durableReplayPreventionClaimed: false
  readonly identity: S2SStageArtifactPermitIdentity
  readonly operation: S2SConfirmatoryArtifactReadOperation
  readonly ledgerCapacity: 16 | 40
  readonly ledgerEntries: ReadonlyArray<S2SStageArtifactLedgerEntry>
  readonly receiptSha256: string
}

export class S2SStageArtifactPermitError extends Data.TaggedError(
  "S2SStageArtifactPermitError"
)<{
  readonly reason:
    | "INVALID_AUTHORITY"
    | "PRODUCTION_IDENTITY_SLOT_OCCUPIED"
    | "SEED_REQUEST_ID_REUSED"
    | "OPERATION_NOT_PERMITTED"
    | "PERMIT_IN_FLIGHT"
    | "PERMIT_ALREADY_SPENT"
    | "PERMIT_OUT_OF_ORDER"
    | "STAGE_VOID"
    | "SCOPE_CLOSED"
    | "REQUEST_ID_REUSED"
    | "REQUEST_ID_LEDGER_EXHAUSTED"
    | "LEDGER_ENTRY_REJECTED"
    | "CANDIDATE_FINGERPRINT_REJECTED"
    | "CANDIDATE_REREAD_MISMATCH"
    | "EVIDENCE_NOT_CANONICAL"
  readonly operation: S2SConfirmatoryArtifactReadOperation | null
  readonly detail: string
}> {}

type PermitStatus = "ISSUED" | "IN_FLIGHT" | "SPENT_SUCCESS" | "SPENT_VOID"
type StageStatus = "ACTIVE" | "IN_FLIGHT" | "COMPLETE" | "VOID" | "CLOSED"

interface S2SStageArtifactPermitState {
  readonly stageStatus: StageStatus
  readonly nextOrdinal: number
  readonly activeOperation: S2SConfirmatoryArtifactReadOperation | null
  readonly permits: Readonly<
    Partial<Record<S2SConfirmatoryArtifactReadOperation, PermitStatus>>
  >
  readonly ledgerEntries: ReadonlyArray<S2SStageArtifactLedgerEntry>
  readonly candidateFingerprint: string | null
}

const S2S_STAGE_ARTIFACT_PERMIT_SCOPE_BRAND: unique symbol = Symbol(
  "hswm/S2SStageArtifactPermitScope"
)

export interface S2SStageArtifactPermitScope {
  readonly [S2S_STAGE_ARTIFACT_PERMIT_SCOPE_BRAND]: true
  readonly mode: "PRODUCTION" | "TEST_ONLY_NON_AUTHORIZING"
  readonly identity: S2SStageArtifactPermitIdentity
  readonly ledgerCapacity: 4 | 16 | 40
  readonly state: Ref.Ref<S2SStageArtifactPermitState>
}

export interface S2SStageArtifactPermitTestSeed {
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly workflowRunId: number
  readonly registrationCommitB: string
  readonly workflowApiPath: string
  readonly workflowRunCreatedAt: string
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly stage: S2SConfirmatoryJobStage
  readonly currentJobDatabaseId: number
  readonly predecessorJobDatabaseIds: ReadonlyArray<number>
  readonly observations: S2SCurrentRunStageEvidence["observations"]
}

const permitError = (
  reason: S2SStageArtifactPermitError["reason"],
  operation: S2SConfirmatoryArtifactReadOperation | null,
  detail: string
): S2SStageArtifactPermitError =>
  new S2SStageArtifactPermitError({ reason, operation, detail })

const ledgerCapacityForStage = (
  stage: S2SConfirmatoryJobStage
): 4 | 16 | 40 =>
  stage === "REGISTER" ? 4 : stage === "CONFIRM" ? 16 : 40

const exactPlainRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (input === null || typeof input !== "object") return null
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) return null
    if (Object.getOwnPropertySymbols(input).length !== 0) return null
    const keys = Object.keys(input).sort()
    const expected = [...expectedKeys].sort()
    if (
      keys.length !== expected.length ||
      keys.some((key, index) => key !== expected[index])
    ) {
      return null
    }
    const record = input as Readonly<Record<string, unknown>>
    const snapshot: Record<string, unknown> = Object.create(null)
    for (const key of expected) {
      const descriptor = Object.getOwnPropertyDescriptor(record, key)
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      snapshot[key] = descriptor.value
    }
    return Object.freeze(snapshot)
  } catch {
    return null
  }
}

const snapshotPositiveIntegerArray = (
  input: unknown
): ReadonlyArray<number> | null => {
  try {
    if (!Array.isArray(input) || Object.getPrototypeOf(input) !== Array.prototype) {
      return null
    }
    if (Object.getOwnPropertySymbols(input).length !== 0) return null
    const lengthDescriptor = Object.getOwnPropertyDescriptor(input, "length")
    if (
      lengthDescriptor === undefined ||
      !("value" in lengthDescriptor) ||
      typeof lengthDescriptor.value !== "number" ||
      !Number.isSafeInteger(lengthDescriptor.value) ||
      lengthDescriptor.value < 0 ||
      lengthDescriptor.value > 2
    ) {
      return null
    }
    const values: Array<number> = []
    for (let index = 0; index < lengthDescriptor.value; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor) ||
        typeof descriptor.value !== "number" ||
        !Number.isSafeInteger(descriptor.value) ||
        descriptor.value < 1
      ) {
        return null
      }
      values.push(descriptor.value)
    }
    if (
      Object.keys(input).length !== values.length ||
      new Set(values).size !== values.length
    ) {
      return null
    }
    return Object.freeze(values)
  } catch {
    return null
  }
}

const snapshotObservationSeed = (
  input: unknown
): S2SCurrentRunStageEvidence["observations"] | null => {
  const observations = exactPlainRecord(input, [
    "jobs",
    "runEnd",
    "runStart",
    "runsForHead"
  ])
  if (observations === null) return null
  const snapshot = (
    value: unknown
  ): S2SCurrentRunStageEvidence["observations"]["runStart"] | null => {
    const record = exactPlainRecord(value, [
      "githubRequestId",
      "observedAtUnixSeconds",
      "receiptSha256"
    ])
    if (record === null) return null
    const requestId = record["githubRequestId"]
    const timestamp = record["observedAtUnixSeconds"]
    const receiptSha256 = record["receiptSha256"]
    if (
      typeof requestId !== "string" ||
      !REQUEST_ID_PATTERN.test(requestId) ||
      typeof timestamp !== "number" ||
      !Number.isSafeInteger(timestamp) ||
      timestamp < 0 ||
      typeof receiptSha256 !== "string" ||
      !SHA256_PATTERN.test(receiptSha256)
    ) {
      return null
    }
    return Object.freeze({
      githubRequestId: requestId,
      observedAtUnixSeconds: timestamp,
      receiptSha256
    })
  }
  const runStart = snapshot(observations["runStart"])
  const jobs = snapshot(observations["jobs"])
  const runsForHead = snapshot(observations["runsForHead"])
  const runEnd = snapshot(observations["runEnd"])
  if (
    runStart === null ||
    jobs === null ||
    runsForHead === null ||
    runEnd === null
  ) {
    return null
  }
  return Object.freeze({ runStart, jobs, runsForHead, runEnd })
}

const identityFromEvidence = (
  evidence: S2SCurrentRunStageEvidence
): S2SStageArtifactPermitIdentity =>
  Object.freeze({
    workflowRunId: evidence.workflowRunId,
    workflowRunAttempt: 1 as const,
    registrationCommitB: evidence.registrationCommitB,
    workflowApiPath: evidence.workflowApiPath,
    workflowRunCreatedAt: evidence.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds: evidence.workflowRunCreatedAtUnixSeconds,
    stage: evidence.stage,
    currentJobDatabaseId: evidence.currentJobDatabaseId,
    predecessorJobDatabaseIds: Object.freeze([
      ...evidence.predecessorJobDatabaseIds
    ])
  })

const seedLedger = (
  observations: S2SCurrentRunStageEvidence["observations"]
): ReadonlyArray<S2SStageArtifactLedgerEntry> =>
  Object.freeze([
    Object.freeze({
      operation: "CURRENT_RUN_AUTHORITY" as const,
      phase: "CURRENT_RUN_RUN_START" as const,
      ...observations.runStart
    }),
    Object.freeze({
      operation: "CURRENT_RUN_AUTHORITY" as const,
      phase: "CURRENT_RUN_JOBS" as const,
      ...observations.jobs
    }),
    Object.freeze({
      operation: "CURRENT_RUN_AUTHORITY" as const,
      phase: "CURRENT_RUN_RUNS_FOR_HEAD" as const,
      ...observations.runsForHead
    }),
    Object.freeze({
      operation: "CURRENT_RUN_AUTHORITY" as const,
      phase: "CURRENT_RUN_RUN_END" as const,
      ...observations.runEnd
    })
  ])

const makeScope = (
  identity: S2SStageArtifactPermitIdentity,
  observations: S2SCurrentRunStageEvidence["observations"],
  mode: S2SStageArtifactPermitScope["mode"]
): Either.Either<S2SStageArtifactPermitScope, S2SStageArtifactPermitError> => {
  const ledgerEntries = seedLedger(observations)
  if (
    new Set(ledgerEntries.map((entry) => entry.githubRequestId)).size !==
      ledgerEntries.length ||
    new Set(ledgerEntries.map((entry) => entry.receiptSha256)).size !==
      ledgerEntries.length ||
    ledgerEntries.some(
      (entry, index) =>
        index > 0 &&
        entry.observedAtUnixSeconds <
          (ledgerEntries[index - 1]?.observedAtUnixSeconds ?? 0)
    )
  ) {
    return Either.left(
      permitError(
        "SEED_REQUEST_ID_REUSED",
        null,
        "the four current-run bracket receipts must be distinct and ordered"
      )
    )
  }
  const operations =
    S2S_CONFIRMATORY_STAGE_CONTRACTS[identity.stage].artifactReadOperations
  const permits = Object.freeze(
    Object.fromEntries(
      operations.map((contract) => [contract.operation, "ISSUED" as const])
    )
  )
  const initial: S2SStageArtifactPermitState = Object.freeze({
    stageStatus: operations.length === 0 ? "COMPLETE" : "ACTIVE",
    nextOrdinal: 1,
    activeOperation: null,
    permits,
    ledgerEntries,
    candidateFingerprint: null
  })
  return Either.right(
    Object.freeze({
      [S2S_STAGE_ARTIFACT_PERMIT_SCOPE_BRAND]: true as const,
      mode,
      identity,
      ledgerCapacity: ledgerCapacityForStage(identity.stage),
      state: Ref.unsafeMake(initial)
    })
  )
}

interface ProductionIdentitySlot {
  readonly key: string
  readonly authority: S2SCurrentRunStageAuthority
  readonly scope: S2SStageArtifactPermitScope
}

const PRODUCTION_SCOPES = new WeakMap<object, S2SStageArtifactPermitScope>()
const TEST_ONLY_SCOPES = new WeakMap<object, S2SStageArtifactPermitScope>()
let PRODUCTION_IDENTITY_SLOT: ProductionIdentitySlot | undefined

const identityKey = (
  identity: S2SStageArtifactPermitIdentity
): Either.Either<string, S2SStageArtifactPermitError> => {
  const hashed = canonicalS2SControlSha256(identity)
  return Either.isLeft(hashed)
    ? Either.left(
        permitError(
          "EVIDENCE_NOT_CANONICAL",
          null,
          "current-job permit identity is not canonical"
        )
      )
    : Either.right(hashed.right)
}

/**
 * Claims the one bounded production identity slot only after the private
 * current-run inspector accepts the exact bearer. Rebuilding a Layer with the
 * same bearer shares its spent state; another bearer cannot replenish it.
 */
export const claimS2SStageArtifactPermitScope = (
  authority: unknown
): Either.Either<
  S2SStageArtifactPermitScope,
  S2SCurrentRunInputError | S2SStageArtifactPermitError
> => {
  const inspected = inspectS2SCurrentRunStageAuthority(authority)
  if (Either.isLeft(inspected)) return Either.left(inspected.left)
  if (authority === null || typeof authority !== "object") {
    return Either.left(
      permitError("INVALID_AUTHORITY", null, "authority is not an object")
    )
  }
  const existing = PRODUCTION_SCOPES.get(authority)
  if (existing !== undefined) return Either.right(existing)
  const genuineAuthority = authority as S2SCurrentRunStageAuthority
  const identity = identityFromEvidence(inspected.right)
  const key = identityKey(identity)
  if (Either.isLeft(key)) return Either.left(key.left)
  if (PRODUCTION_IDENTITY_SLOT !== undefined) {
    return Either.left(
      permitError(
        "PRODUCTION_IDENTITY_SLOT_OCCUPIED",
        null,
        PRODUCTION_IDENTITY_SLOT.key === key.right
          ? "this current-job identity was already bound to another genuine bearer"
          : "the single-module current-job identity slot is already occupied"
      )
    )
  }
  const scope = makeScope(
    identity,
    inspected.right.observations,
    "PRODUCTION"
  )
  if (Either.isLeft(scope)) return scope
  PRODUCTION_SCOPES.set(genuineAuthority, scope.right)
  PRODUCTION_IDENTITY_SLOT = Object.freeze({
    key: key.right,
    authority: genuineAuthority,
    scope: scope.right
  })
  return scope
}

/** @internal TEST-ONLY, NON-AUTHORIZING. Never touches production registries. */
export const makeS2SStageArtifactPermitTestScope = (
  input: unknown
): Either.Either<S2SStageArtifactPermitScope, S2SStageArtifactPermitError> => {
  if (input !== null && typeof input === "object") {
    const existing = TEST_ONLY_SCOPES.get(input)
    if (existing !== undefined) return Either.right(existing)
  }
  const record = exactPlainRecord(input, [
    "classification",
    "currentJobDatabaseId",
    "observations",
    "predecessorJobDatabaseIds",
    "registrationCommitB",
    "stage",
    "workflowApiPath",
    "workflowRunCreatedAt",
    "workflowRunCreatedAtUnixSeconds",
    "workflowRunId"
  ])
  if (record === null || record["classification"] !== "TEST_ONLY_NON_AUTHORIZING") {
    return Either.left(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "test permit seed must be an exact non-authorizing fixture"
      )
    )
  }
  const stage = record["stage"]
  const workflowRunId = record["workflowRunId"]
  const registrationCommitB = record["registrationCommitB"]
  const workflowApiPath = record["workflowApiPath"]
  const workflowRunCreatedAt = record["workflowRunCreatedAt"]
  const workflowRunCreatedAtUnixSeconds =
    record["workflowRunCreatedAtUnixSeconds"]
  const currentJobDatabaseId = record["currentJobDatabaseId"]
  const predecessorJobDatabaseIds = snapshotPositiveIntegerArray(
    record["predecessorJobDatabaseIds"]
  )
  const observations = snapshotObservationSeed(record["observations"])
  if (
    (stage !== "REGISTER" && stage !== "CONFIRM" && stage !== "ADJUDICATE") ||
    typeof workflowRunId !== "number" ||
    !Number.isSafeInteger(workflowRunId) ||
    workflowRunId < 1 ||
    typeof registrationCommitB !== "string" ||
    !GIT_SHA_PATTERN.test(registrationCommitB) ||
    (workflowApiPath !== S2S_CONFIRMATORY_WORKFLOW_PATH &&
      workflowApiPath !==
        `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`) ||
    typeof workflowRunCreatedAt !== "string" ||
    !RFC3339_UTC_SECONDS_PATTERN.test(workflowRunCreatedAt) ||
    typeof workflowRunCreatedAtUnixSeconds !== "number" ||
    !Number.isSafeInteger(workflowRunCreatedAtUnixSeconds) ||
    workflowRunCreatedAtUnixSeconds < 0 ||
    Date.parse(workflowRunCreatedAt) / 1_000 !==
      workflowRunCreatedAtUnixSeconds ||
    typeof currentJobDatabaseId !== "number" ||
    !Number.isSafeInteger(currentJobDatabaseId) ||
    currentJobDatabaseId < 1 ||
    predecessorJobDatabaseIds === null ||
    predecessorJobDatabaseIds.length !==
      (stage === "REGISTER" ? 0 : stage === "CONFIRM" ? 1 : 2) ||
    new Set(predecessorJobDatabaseIds).size !== predecessorJobDatabaseIds.length ||
    predecessorJobDatabaseIds.includes(currentJobDatabaseId) ||
    observations === null
  ) {
    return Either.left(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "test permit seed identity is not canonical"
      )
    )
  }
  const identity: S2SStageArtifactPermitIdentity = Object.freeze({
    workflowRunId,
    workflowRunAttempt: 1 as const,
    registrationCommitB,
    workflowApiPath,
    workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds,
    stage,
    currentJobDatabaseId,
    predecessorJobDatabaseIds: Object.freeze([...predecessorJobDatabaseIds])
  })
  const scope = makeScope(
    identity,
    observations,
    "TEST_ONLY_NON_AUTHORIZING"
  )
  if (
    Either.isRight(scope) &&
    input !== null &&
    typeof input === "object"
  ) {
    TEST_ONLY_SCOPES.set(input, scope.right)
  }
  return scope
}

const reservePermit = (
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation
): Effect.Effect<void, S2SStageArtifactPermitError> =>
  Ref.modify(scope.state, (state) => {
    const contract = S2S_CONFIRMATORY_STAGE_CONTRACTS[
      scope.identity.stage
    ].artifactReadOperations.find((entry) => entry.operation === operation)
    if (contract === undefined) {
      return [
        permitError(
          "OPERATION_NOT_PERMITTED",
          operation,
          "operation is absent from the authentic stage contract"
        ),
        state
      ] as const
    }
    if (state.stageStatus === "VOID") {
      return [
        permitError("STAGE_VOID", operation, "stage was voided by a prior use"),
        state
      ] as const
    }
    if (state.stageStatus === "CLOSED") {
      return [
        permitError("SCOPE_CLOSED", operation, "permit scope is closed"),
        state
      ] as const
    }
    if (state.stageStatus === "IN_FLIGHT") {
      return [
        permitError(
          "PERMIT_IN_FLIGHT",
          operation,
          "another stage artifact operation is already in flight"
        ),
        state
      ] as const
    }
    const status = state.permits[operation]
    if (status === "SPENT_SUCCESS" || status === "SPENT_VOID") {
      return [
        permitError(
          "PERMIT_ALREADY_SPENT",
          operation,
          "the one-use operation permit was already spent"
        ),
        state
      ] as const
    }
    if (state.stageStatus === "COMPLETE" || status !== "ISSUED") {
      return [
        permitError(
          "PERMIT_ALREADY_SPENT",
          operation,
          "the stage has no remaining issued permit"
        ),
        state
      ] as const
    }
    if (contract.ordinalWithinStage !== state.nextOrdinal) {
      return [
        permitError(
          "PERMIT_OUT_OF_ORDER",
          operation,
          `expected ordinal ${state.nextOrdinal}`
        ),
        state
      ] as const
    }
    return [
      null,
      Object.freeze({
        ...state,
        stageStatus: "IN_FLIGHT" as const,
        activeOperation: operation,
        permits: Object.freeze({
          ...state.permits,
          [operation]: "IN_FLIGHT" as const
        })
      })
    ] as const
  }).pipe(
    Effect.flatMap((error) =>
      error === null ? Effect.void : Effect.fail(error)
    )
  )

const nextArtifactLedgerPhases = (
  phases: ReadonlyArray<S2SStageArtifactLedgerPhase>
): ReadonlySet<S2SStageArtifactLedgerPhase> => {
  const last = phases[phases.length - 1]
  if (last === undefined) return new Set(["LOOKUP_RUN_START"])
  switch (last) {
    case "LOOKUP_RUN_START":
      return new Set(["LOOKUP_JOBS"])
    case "LOOKUP_JOBS":
      return new Set(["LOOKUP_ARTIFACTS_1"])
    case "LOOKUP_ARTIFACTS_1":
      return new Set(["LOOKUP_RUN_END_1"])
    case "LOOKUP_RUN_END_1":
      return new Set(["LOOKUP_ARTIFACTS_2", "READBACK_RUN_START"])
    case "LOOKUP_ARTIFACTS_2":
      return new Set(["LOOKUP_RUN_END_2"])
    case "LOOKUP_RUN_END_2":
      return new Set(["LOOKUP_ARTIFACTS_3", "READBACK_RUN_START"])
    case "LOOKUP_ARTIFACTS_3":
      return new Set(["LOOKUP_RUN_END_3"])
    case "LOOKUP_RUN_END_3":
      return new Set(["READBACK_RUN_START"])
    case "READBACK_RUN_START":
      return new Set(["READBACK_ARTIFACT"])
    case "READBACK_ARTIFACT":
      return new Set(["READBACK_DOWNLOAD_REDIRECT"])
    case "READBACK_DOWNLOAD_REDIRECT":
      return new Set(["READBACK_RUN_END"])
    case "READBACK_RUN_END":
    case "CURRENT_RUN_RUN_START":
    case "CURRENT_RUN_JOBS":
    case "CURRENT_RUN_RUNS_FOR_HEAD":
    case "CURRENT_RUN_RUN_END":
      return new Set()
  }
}

export const appendS2SStageArtifactLedgerEntry = (
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  phase: S2SStageArtifactLedgerPhase,
  githubRequestId: string,
  receiptSha256: string,
  observedAtUnixSeconds: number
): Effect.Effect<void, S2SStageArtifactPermitError> =>
  Ref.modify(scope.state, (state) => {
    if (
      state.stageStatus !== "IN_FLIGHT" ||
      state.activeOperation !== operation ||
      state.permits[operation] !== "IN_FLIGHT"
    ) {
      return [
        permitError(
          "STAGE_VOID",
          operation,
          "ledger admission requires the exact reserved in-flight permit"
        ),
        state
      ] as const
    }
    if (
      !REQUEST_ID_PATTERN.test(githubRequestId) ||
      !SHA256_PATTERN.test(receiptSha256) ||
      !Number.isSafeInteger(observedAtUnixSeconds) ||
      observedAtUnixSeconds < 0
    ) {
      return [
        permitError(
          "LEDGER_ENTRY_REJECTED",
          operation,
          "validated response provenance is not canonical"
        ),
        state
      ] as const
    }
    const operationPhases = state.ledgerEntries
      .filter((entry) => entry.operation === operation)
      .map((entry) => entry.phase)
    if (!nextArtifactLedgerPhases(operationPhases).has(phase)) {
      return [
        permitError(
          "LEDGER_ENTRY_REJECTED",
          operation,
          "validated receipt phase is outside the fixed operation topology"
        ),
        state
      ] as const
    }
    if (
      state.ledgerEntries.some(
        (entry) => entry.githubRequestId === githubRequestId
      )
    ) {
      return [
        permitError(
          "REQUEST_ID_REUSED",
          operation,
          "GitHub request ID was already accepted by this current-job ledger"
        ),
        state
      ] as const
    }
    const previous = state.ledgerEntries[state.ledgerEntries.length - 1]
    if (
      previous === undefined ||
      observedAtUnixSeconds < previous.observedAtUnixSeconds ||
      state.ledgerEntries.some(
        (entry) => entry.receiptSha256 === receiptSha256
      )
    ) {
      return [
        permitError(
          "LEDGER_ENTRY_REJECTED",
          operation,
          "validated receipt is not a fresh ordered addition to the stage ledger"
        ),
        state
      ] as const
    }
    if (state.ledgerEntries.length >= scope.ledgerCapacity) {
      return [
        permitError(
          "REQUEST_ID_LEDGER_EXHAUSTED",
          operation,
          "the exact non-evicting stage ledger capacity was exhausted"
        ),
        state
      ] as const
    }
    const entry: S2SStageArtifactLedgerEntry = Object.freeze({
      operation,
      phase,
      githubRequestId,
      receiptSha256,
      observedAtUnixSeconds
    })
    return [
      null,
      Object.freeze({
        ...state,
        ledgerEntries: Object.freeze([...state.ledgerEntries, entry])
      })
    ] as const
  }).pipe(
    Effect.flatMap((error) =>
      error === null ? Effect.void : Effect.fail(error)
    )
  )

const validateCandidateFingerprint = (
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  fingerprint: string | null
): Effect.Effect<void, S2SStageArtifactPermitError> => {
  if (
    operation !== "ADJUDICATE_READ_CANDIDATE_FIRST" &&
    operation !== "ADJUDICATE_REREAD_CANDIDATE"
  ) {
    return Effect.void
  }
  if (fingerprint === null || !SHA256_PATTERN.test(fingerprint)) {
    return Effect.fail(
      permitError(
        "CANDIDATE_FINGERPRINT_REJECTED",
        operation,
        "candidate read did not produce one canonical fingerprint"
      )
    )
  }
  if (operation === "ADJUDICATE_READ_CANDIDATE_FIRST") return Effect.void
  return Ref.get(scope.state).pipe(
    Effect.flatMap((state) =>
      state.candidateFingerprint === fingerprint
        ? Effect.void
        : Effect.fail(
            permitError(
              "CANDIDATE_REREAD_MISMATCH",
              operation,
              "independent candidate reread differs from the first read"
            )
          )
    )
  )
}

const finalizePermit = <A, E>(
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  exit: Exit.Exit<readonly [A, string | null], E>
): Effect.Effect<void> =>
  Ref.update(scope.state, (state) => {
    if (
      state.stageStatus !== "IN_FLIGHT" ||
      state.activeOperation !== operation ||
      state.permits[operation] !== "IN_FLIGHT"
    ) {
      return Object.freeze({
        ...state,
        stageStatus: "VOID" as const,
        activeOperation: null,
        permits: Object.freeze({
          ...state.permits,
          [operation]: "SPENT_VOID" as const
        })
      })
    }
    if (!Exit.isSuccess(exit)) {
      return Object.freeze({
        ...state,
        stageStatus: "VOID" as const,
        activeOperation: null,
        permits: Object.freeze({
          ...state.permits,
          [operation]: "SPENT_VOID" as const
        })
      })
    }
    const contract = S2S_CONFIRMATORY_STAGE_CONTRACTS[
      scope.identity.stage
    ].artifactReadOperations.find((entry) => entry.operation === operation)
    const nextOrdinal = state.nextOrdinal + 1
    const complete =
      contract === undefined ||
      nextOrdinal >
        S2S_CONFIRMATORY_STAGE_CONTRACTS[scope.identity.stage]
          .artifactReadOperations.length
    return Object.freeze({
      ...state,
      stageStatus: complete ? ("COMPLETE" as const) : ("ACTIVE" as const),
      nextOrdinal,
      activeOperation: null,
      permits: Object.freeze({
        ...state.permits,
        [operation]: "SPENT_SUCCESS" as const
      }),
      candidateFingerprint:
        operation === "ADJUDICATE_READ_CANDIDATE_FIRST"
          ? exit.value[1]
          : state.candidateFingerprint
    })
  })

export const useS2SStageArtifactPermit = <A, E, R, E2 = never>(
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation,
  use: () => Effect.Effect<A, E, R>,
  successFingerprint?: (value: A) => Either.Either<string, E2>
): Effect.Effect<A, E | E2 | S2SStageArtifactPermitError, R> =>
  Effect.suspend(() =>
    Effect.acquireUseRelease(
      reservePermit(scope, operation),
      () =>
        Effect.suspend(use).pipe(
          Effect.flatMap(
            (value): Effect.Effect<readonly [A, string | null], E2> => {
              if (successFingerprint === undefined) {
                return Effect.succeed(
                  [value, null] as readonly [A, string | null]
                )
              }
              const fingerprint = successFingerprint(value)
              return Either.isLeft(fingerprint)
                ? Effect.fail(fingerprint.left)
                : Effect.succeed(
                    [value, fingerprint.right] as readonly [A, string | null]
                  )
            }
          ),
          Effect.tap(([, fingerprint]) =>
            validateCandidateFingerprint(scope, operation, fingerprint)
          )
        ),
      (_reserved, exit) => finalizePermit(scope, operation, exit)
    ).pipe(Effect.map(([value]) => value))
  )

export const snapshotS2SStageArtifactPermitEvidence = (
  scope: S2SStageArtifactPermitScope,
  operation: S2SConfirmatoryArtifactReadOperation
): Effect.Effect<S2SStageArtifactPermitEvidence, S2SStageArtifactPermitError> =>
  Ref.get(scope.state).pipe(
    Effect.flatMap((state) => {
      if (
        state.stageStatus !== "IN_FLIGHT" ||
        state.activeOperation !== operation ||
        state.ledgerEntries
          .filter((entry) => entry.operation === operation)
          .at(-1)?.phase !== "READBACK_RUN_END"
      ) {
        return Effect.fail(
          permitError(
            "STAGE_VOID",
            operation,
            "permit evidence can only be sealed by its active operation"
          )
        )
      }
      if (scope.ledgerCapacity === 4) {
        return Effect.fail(
          permitError(
            "OPERATION_NOT_PERMITTED",
            operation,
            "REGISTER has no artifact read evidence"
          )
        )
      }
      const core = Object.freeze({
        schemaVersion: S2S_STAGE_ARTIFACT_PERMIT_EVIDENCE_SCHEMA_VERSION,
        authorityScope:
          scope.mode === "PRODUCTION"
            ? ("TRUSTED_SINGLE_MODULE_CURRENT_JOB" as const)
            : ("TEST_ONLY_NON_AUTHORIZING" as const),
        authorizationClaimed: scope.mode === "PRODUCTION",
        oneUseClaim:
          scope.mode === "PRODUCTION"
            ? ("ONE_USE_PER_GENUINE_AUTHORITY_AND_PROCESS_IDENTITY_SLOT" as const)
            : ("MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE" as const),
        crossWorkerReplayPreventionClaimed: false as const,
        crossModuleCopyReplayPreventionClaimed: false as const,
        crossProcessReplayPreventionClaimed: false as const,
        durableReplayPreventionClaimed: false as const,
        identity: scope.identity,
        operation,
        ledgerCapacity: scope.ledgerCapacity,
        ledgerEntries: Object.freeze([...state.ledgerEntries])
      })
      const hashed = canonicalS2SControlSha256(core)
      return Either.isLeft(hashed)
        ? Effect.fail(
            permitError(
              "EVIDENCE_NOT_CANONICAL",
              operation,
              "permit evidence cannot be canonically hashed"
            )
          )
        : Effect.succeed(
            Object.freeze({ ...core, receiptSha256: hashed.right })
          )
    })
  )

export const closeS2SStageArtifactPermitScope = (
  scope: S2SStageArtifactPermitScope
): Effect.Effect<void> =>
  Ref.update(scope.state, (state) =>
    Object.freeze({
      ...state,
      stageStatus: "CLOSED" as const,
      activeOperation: null,
      permits: Object.freeze(
        Object.fromEntries(
          Object.entries(state.permits).map(([operation, status]) => [
            operation,
            status === "SPENT_SUCCESS" || status === "SPENT_VOID"
              ? status
              : "SPENT_VOID"
          ])
        )
      )
    })
  )
