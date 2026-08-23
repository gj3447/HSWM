import { types as nodeTypes } from "node:util"

import { Cause, Context, Data, Effect, Either, Exit, Layer, Ref } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2SGitCommitShaSchema,
  S2SSha256Schema
} from "./s2s-confirmatory.js"
import {
  S2S_GITHUB_ARCHIVE_TIMEOUT_MILLIS,
  S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
  S2SGitHubObservationError,
  S2SGitHubObservationValidationError,
  S2SGitHubObserver,
  S2SGitHubObserverLive,
  S2SGitHubTransportError,
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
  inspectS2SPreparedStageCarrierCapability,
  inspectS2SPreparedStageCarrierTestCapability,
  type S2SPreparedStageCarrierCapability,
  type S2SPreparedStageCarrierSnapshot
} from "./s2s-prepared-stage-carrier.js"
import {
  inspectS2SCurrentRunStageAuthority,
  requireS2SProductionWorkflowSourcePolicy,
  S2SCurrentRunStage,
  type S2SCurrentRunInputError,
  type S2SCurrentRunStageEvidence
} from "./s2s-run-authority.js"
import { validateS2SCurrentRunStageEvidence } from "./s2s-stage-artifact-read-replay.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "./s2s-stage-artifact-spec.js"
import {
  S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
  S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION
} from "./s2s-stage-upload-postcondition-contract.js"
import {
  S2SStageUploadPostconditionError,
  buildS2SStageUploadPostcondition,
  buildS2SStageUploadPostconditionFromProductionShell,
  validateS2SStageUploadPostcondition,
  type S2SStageUploadAssertionPermitEvidence,
  type S2SStageUploadBuildObservation,
  type S2SStageUploadPostconditionSnapshot,
  type S2SStageUploadPreparedMember
} from "./s2s-stage-upload-postcondition.js"
import {
  classifyS2SStageUploadOutcome,
  type S2SStageUploadOutcome,
  type S2SStageUploadOutcomeClassification
} from "./s2s-stage-upload-outcome.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_EVENT,
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_NAME,
  S2S_CONFIRMATORY_WORKFLOW_PATH
} from "./s2s-workflow-contract.js"
import { validateS2SArtifactZip } from "./s2s-zip.js"

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const REQUEST_ID_PATTERN = /^[\u0021-\u007e]{1,256}$/
const S2S_CONFIRMATORY_WORKFLOW_PATH_AT_MAIN =
  `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}` as const

export type S2SStageUploadAssertionLedgerPhase =
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

export interface S2SStageUploadAssertionLedgerObservation {
  readonly githubRequestId: string
  readonly receiptSha256: string
  readonly observedAtUnixSeconds: number
}

export interface S2SStageUploadAssertionLedgerEntry
  extends S2SStageUploadAssertionLedgerObservation {
  readonly operation:
    | "CURRENT_RUN_AUTHORITY"
    | typeof S2S_STAGE_UPLOAD_ASSERTION_OPERATION
  readonly phase: S2SStageUploadAssertionLedgerPhase
}

export type S2SStageUploadAssertionPermitStatus =
  | "ISSUED"
  | "IN_FLIGHT"
  | "SPENT_SUCCESS"
  | "SPENT_VOID"
  | "CLOSED"

export class S2SStageUploadAssertionPermitError extends Data.TaggedError(
  "S2SStageUploadAssertionPermitError"
)<{
  readonly reason:
    | "INVALID_AUTHORITY"
    | "INVALID_PREPARED_CAPABILITY"
    | "INVALID_COMPLETION_CAPABILITY"
    | "INVALID_REPLAY_SNAPSHOT"
    | "PREPARED_CAPABILITY_BINDING_MISMATCH"
    | "PRODUCTION_SEMANTIC_SLOT_OCCUPIED"
    | "PRODUCTION_ASSERTION_SHELL_OPEN"
    | "PRODUCTION_PROCESS_CONTINUITY_OPEN"
    | "TEST_SEED_INVALID"
    | "SEED_REQUEST_ID_REUSED"
    | "PERMIT_IN_FLIGHT"
    | "PERMIT_ALREADY_SPENT"
    | "STAGE_VOID"
    | "SCOPE_CLOSED"
    | "LEDGER_ENTRY_REJECTED"
    | "REQUEST_ID_REUSED"
    | "RECEIPT_HASH_REUSED"
    | "OBSERVATION_ORDER_INVALID"
    | "LEDGER_CAPACITY_EXHAUSTED"
    | "EVIDENCE_NOT_SEALABLE"
    | "EVIDENCE_NOT_CANONICAL"
    | "OUTCOME_CLASSIFICATION_INVALID"
  readonly phase: S2SStageUploadAssertionLedgerPhase | null
  readonly detail: string
}> {}

const permitError = (
  reason: S2SStageUploadAssertionPermitError["reason"],
  phase: S2SStageUploadAssertionLedgerPhase | null,
  detail: string
): S2SStageUploadAssertionPermitError =>
  new S2SStageUploadAssertionPermitError({ reason, phase, detail })

const S2S_STAGE_UPLOAD_ASSERTION_PERMIT_SCOPE_BRAND: unique symbol = Symbol(
  "hswm/S2SStageUploadAssertionPermitScope"
)

/** Opaque process-local bearer. Its fields are not its authority. */
export interface S2SStageUploadAssertionPermitScope {
  readonly [S2S_STAGE_UPLOAD_ASSERTION_PERMIT_SCOPE_BRAND]: true
}

type AssertionIdentity = S2SStageUploadAssertionPermitEvidence["identity"]

interface AssertionPermitState {
  readonly status: S2SStageUploadAssertionPermitStatus
  readonly ledgerEntries: ReadonlyArray<S2SStageUploadAssertionLedgerEntry>
  readonly activeLease: AssertionPermitLease | null
  readonly layerClaims: ReadonlyArray<AssertionLayerClaim>
}

const ASSERTION_LAYER_CLAIM_BRAND: unique symbol = Symbol(
  "hswm/S2SStageUploadAssertionLayerClaim"
)

interface AssertionLayerClaim {
  readonly [ASSERTION_LAYER_CLAIM_BRAND]: true
}

const ASSERTION_PERMIT_LEASE_BRAND: unique symbol = Symbol(
  "hswm/S2SStageUploadAssertionPermitLease"
)

interface AssertionPermitLease {
  readonly [ASSERTION_PERMIT_LEASE_BRAND]: true
}

type AssertionPermitReservation =
  | {
      readonly _tag: "Reserved"
      readonly lease: AssertionPermitLease
    }
  | {
      readonly _tag: "Rejected"
      readonly error: S2SStageUploadAssertionPermitError
    }

interface AssertionScopeState {
  readonly mode: "PRODUCTION" | "TEST_ONLY_NON_AUTHORIZING"
  readonly current: S2SCurrentRunStageEvidence
  readonly identity: AssertionIdentity
  readonly prepared: S2SPreparedStageCarrierSnapshot
  readonly state: Ref.Ref<AssertionPermitState>
}

interface ProductionSemanticSlot {
  readonly authority: object
  readonly capability: object
  readonly scope: S2SStageUploadAssertionPermitScope
}

interface TestFixtureSlot {
  readonly capability: object
  readonly scope: S2SStageUploadAssertionPermitScope
}

const PRODUCTION_SCOPE_STATES = new WeakMap<
  object,
  AssertionScopeState
>()
const TEST_SCOPE_STATES = new WeakMap<object, AssertionScopeState>()
const TEST_FIXTURE_SCOPES = new WeakMap<object, TestFixtureSlot>()
let PRODUCTION_SEMANTIC_SLOT: ProductionSemanticSlot | undefined

const exactPlainRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      nodeTypes.isProxy(input) ||
      Object.getPrototypeOf(input) !== Object.prototype
    ) {
      return null
    }
    const keys = Reflect.ownKeys(input)
    if (
      keys.length !== expectedKeys.length ||
      keys.some((key) => typeof key !== "string") ||
      expectedKeys.some((key) => !keys.includes(key))
    ) {
      return null
    }
    const output: Record<string, unknown> = {}
    for (const key of expectedKeys) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      output[key] = descriptor.value
    }
    return Object.freeze(output)
  } catch {
    return null
  }
}

const isSafeNonNegativeInteger = (input: unknown): input is number =>
  typeof input === "number" &&
  Number.isSafeInteger(input) &&
  input >= 0

const sameNumberArray = (
  left: ReadonlyArray<number>,
  right: ReadonlyArray<number>
): boolean =>
  left.length === right.length &&
  left.every((value, index) => value === right[index])

const preparedMatchesCurrent = (
  current: S2SCurrentRunStageEvidence,
  prepared: S2SPreparedStageCarrierSnapshot
): boolean =>
  prepared.sourceCommitA === current.sourceCommitA &&
  prepared.currentRunEvidenceReceiptSha256 === current.receiptSha256 &&
  prepared.workflowRunId === current.workflowRunId &&
  prepared.workflowRunAttempt === current.workflowRunAttempt &&
  prepared.registrationCommitB === current.registrationCommitB &&
  prepared.workflowApiPath === current.workflowApiPath &&
  prepared.workflowRunCreatedAt === current.workflowRunCreatedAt &&
  prepared.workflowRunCreatedAtUnixSeconds ===
    current.workflowRunCreatedAtUnixSeconds &&
  prepared.stage === current.stage &&
  prepared.currentJobDatabaseId === current.currentJobDatabaseId &&
  sameNumberArray(
    prepared.predecessorJobDatabaseIds,
    current.predecessorJobDatabaseIds
  )

const identityFromCurrent = (
  current: S2SCurrentRunStageEvidence
): Either.Either<AssertionIdentity, S2SStageUploadAssertionPermitError> => {
  const workflowApiPath = current.workflowApiPath
  if (
    workflowApiPath !== S2S_CONFIRMATORY_WORKFLOW_PATH &&
    workflowApiPath !== S2S_CONFIRMATORY_WORKFLOW_PATH_AT_MAIN
  ) {
    return Either.left(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "current-run workflow API path is not fixed"
      )
    )
  }
  const fixedWorkflowApiPath =
    workflowApiPath === S2S_CONFIRMATORY_WORKFLOW_PATH
      ? S2S_CONFIRMATORY_WORKFLOW_PATH
      : S2S_CONFIRMATORY_WORKFLOW_PATH_AT_MAIN
  return Either.right(
    Object.freeze({
      workflowRunId: current.workflowRunId,
      workflowRunAttempt: 1 as const,
      registrationCommitB: S2SGitCommitShaSchema.make(
        current.registrationCommitB
      ),
      workflowApiPath: fixedWorkflowApiPath,
      workflowRunCreatedAt: current.workflowRunCreatedAt,
      workflowRunCreatedAtUnixSeconds:
        current.workflowRunCreatedAtUnixSeconds,
      stage: current.stage,
      currentJobDatabaseId: current.currentJobDatabaseId,
      predecessorJobDatabaseIds: Object.freeze([
        ...current.predecessorJobDatabaseIds
      ])
    })
  )
}

const seedLedger = (
  current: S2SCurrentRunStageEvidence
): ReadonlyArray<S2SStageUploadAssertionLedgerEntry> =>
  Object.freeze(
    (
      [
        ["CURRENT_RUN_RUN_START", current.observations.runStart],
        ["CURRENT_RUN_JOBS", current.observations.jobs],
        ["CURRENT_RUN_RUNS_FOR_HEAD", current.observations.runsForHead],
        ["CURRENT_RUN_RUN_END", current.observations.runEnd]
      ] as const
    ).map(([phase, observation]) =>
      Object.freeze({
        operation: "CURRENT_RUN_AUTHORITY" as const,
        phase,
        githubRequestId: observation.githubRequestId,
        receiptSha256: observation.receiptSha256,
        observedAtUnixSeconds: observation.observedAtUnixSeconds
      })
    )
  )

const makeScope = (
  current: S2SCurrentRunStageEvidence,
  prepared: S2SPreparedStageCarrierSnapshot,
  mode: AssertionScopeState["mode"]
): Either.Either<
  S2SStageUploadAssertionPermitScope,
  S2SStageUploadAssertionPermitError
> => {
  const preparedClaimsMatchMode =
    mode === "PRODUCTION"
      ? prepared.authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB" &&
        prepared.authorizationClaimed === true &&
        prepared.oneSemanticProductionSlotClaimed === true
      : prepared.authorityScope === "TEST_ONLY_NON_AUTHORIZING" &&
        prepared.authorizationClaimed === false &&
        prepared.oneSemanticProductionSlotClaimed === false
  if (!preparedClaimsMatchMode) {
    return Either.left(
      permitError(
        "PREPARED_CAPABILITY_BINDING_MISMATCH",
        null,
        "prepared carrier authority claims do not match the permit scope"
      )
    )
  }
  if (!preparedMatchesCurrent(current, prepared)) {
    return Either.left(
      permitError(
        "PREPARED_CAPABILITY_BINDING_MISMATCH",
        null,
        "prepared carrier does not bind the exact current-run stage identity"
      )
    )
  }
  const identity = identityFromCurrent(current)
  if (Either.isLeft(identity)) return Either.left(identity.left)
  const ledgerEntries = seedLedger(current)
  if (
    new Set(ledgerEntries.map((entry) => entry.githubRequestId)).size !== 4 ||
    new Set(ledgerEntries.map((entry) => entry.receiptSha256)).size !== 4 ||
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
        "the four current-run seed receipts must be distinct and monotonic"
      )
    )
  }
  const scope: S2SStageUploadAssertionPermitScope = Object.freeze({
    [S2S_STAGE_UPLOAD_ASSERTION_PERMIT_SCOPE_BRAND]: true as const
  })
  const state: AssertionScopeState = Object.freeze({
    mode,
    current,
    identity: identity.right,
    prepared,
    state: Ref.unsafeMake<AssertionPermitState>(
      Object.freeze({
        status: "ISSUED" as const,
        ledgerEntries,
        activeLease: null,
        layerClaims: Object.freeze([])
      })
    )
  })
  ;(mode === "PRODUCTION"
    ? PRODUCTION_SCOPE_STATES
    : TEST_SCOPE_STATES
  ).set(scope, state)
  return Either.right(scope)
}

const scopeState = (
  scope: unknown
): Either.Either<AssertionScopeState, S2SStageUploadAssertionPermitError> => {
  try {
    if (scope === null || typeof scope !== "object") {
      return Either.left(
        permitError("INVALID_AUTHORITY", null, "permit scope is not an object")
      )
    }
    const production = PRODUCTION_SCOPE_STATES.get(scope)
    if (production !== undefined) return Either.right(production)
    const test = TEST_SCOPE_STATES.get(scope)
    return test === undefined
      ? Either.left(
          permitError(
            "INVALID_AUTHORITY",
            null,
            "permit scope was not issued by this module"
          )
        )
      : Either.right(test)
  } catch {
    return Either.left(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "permit scope inspection failed closed"
      )
    )
  }
}

/**
 * Claims the sole process semantic slot only for an exact module-issued
 * current-run authority and the production prepared capability bound to it.
 */
export const claimS2SStageUploadAssertionPermitScope = (
  authority: unknown,
  capability: unknown
): Either.Either<
  S2SStageUploadAssertionPermitScope,
  S2SStageUploadAssertionPermitError
> => {
  const current = inspectS2SCurrentRunStageAuthority(authority)
  if (Either.isLeft(current)) {
    return Either.left(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "current-run authority was not issued by this module"
      )
    )
  }
  const prepared = inspectS2SPreparedStageCarrierCapability(
    authority,
    capability
  )
  if (Either.isLeft(prepared)) {
    return Either.left(
      permitError(
        "INVALID_PREPARED_CAPABILITY",
        null,
        "prepared carrier capability was not issued for this authority"
      )
    )
  }
  if (
    authority === null ||
    typeof authority !== "object" ||
    capability === null ||
    typeof capability !== "object"
  ) {
    return Either.left(
      permitError(
        "INVALID_PREPARED_CAPABILITY",
        null,
        "production authority and capability must be objects"
      )
    )
  }
  if (PRODUCTION_SEMANTIC_SLOT !== undefined) {
    return PRODUCTION_SEMANTIC_SLOT.authority === authority &&
      PRODUCTION_SEMANTIC_SLOT.capability === capability
      ? Either.right(PRODUCTION_SEMANTIC_SLOT.scope)
      : Either.left(
          permitError(
            "PRODUCTION_SEMANTIC_SLOT_OCCUPIED",
            null,
            "the one process semantic assertion slot is already occupied"
          )
        )
  }
  const scope = makeScope(current.right, prepared.right, "PRODUCTION")
  if (Either.isLeft(scope)) return scope
  PRODUCTION_SEMANTIC_SLOT = Object.freeze({
    authority,
    capability,
    scope: scope.right
  })
  return scope
}

export interface S2SStageUploadAssertionPermitTestSeed {
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly currentRunEvidence: S2SCurrentRunStageEvidence
}

/** @internal TEST-ONLY, NON-AUTHORIZING. */
export const makeS2SStageUploadAssertionPermitTestScope = (
  seed: unknown,
  capability: unknown
): Either.Either<
  S2SStageUploadAssertionPermitScope,
  S2SStageUploadAssertionPermitError
> => {
  const record = exactPlainRecord(seed, [
    "classification",
    "currentRunEvidence"
  ])
  if (
    record === null ||
    record["classification"] !== "TEST_ONLY_NON_AUTHORIZING" ||
    seed === null ||
    typeof seed !== "object"
  ) {
    return Either.left(
      permitError(
        "TEST_SEED_INVALID",
        null,
        "test scope requires one exact non-authorizing fixture"
      )
    )
  }
  if (capability === null || typeof capability !== "object") {
    return Either.left(
      permitError(
        "INVALID_PREPARED_CAPABILITY",
        null,
        "test prepared capability is not an object"
      )
    )
  }
  const current = validateS2SCurrentRunStageEvidence(
    record["currentRunEvidence"]
  )
  if (Either.isLeft(current)) {
    return Either.left(
      permitError(
        "TEST_SEED_INVALID",
        null,
        "test current-run evidence is not canonical"
      )
    )
  }
  const prepared = inspectS2SPreparedStageCarrierTestCapability(capability)
  if (Either.isLeft(prepared)) {
    return Either.left(
      permitError(
        "INVALID_PREPARED_CAPABILITY",
        null,
        "test prepared capability was not issued by the test-only registry"
      )
    )
  }
  const existing = TEST_FIXTURE_SCOPES.get(seed)
  if (existing !== undefined) {
    return existing.capability === capability
      ? Either.right(existing.scope)
      : Either.left(
          permitError(
            "PREPARED_CAPABILITY_BINDING_MISMATCH",
            null,
            "the test fixture is already bound to another prepared capability"
          )
        )
  }
  const scope = makeScope(
    current.right,
    prepared.right,
    "TEST_ONLY_NON_AUTHORIZING"
  )
  if (Either.isLeft(scope)) return scope
  TEST_FIXTURE_SCOPES.set(
    seed,
    Object.freeze({ capability, scope: scope.right })
  )
  return scope
}

const ASSERTION_TOPOLOGIES = Object.freeze([
  Object.freeze([
    "LOOKUP_RUN_START",
    "LOOKUP_JOBS",
    "LOOKUP_ARTIFACTS_1",
    "LOOKUP_RUN_END_1",
    "READBACK_RUN_START",
    "READBACK_ARTIFACT",
    "READBACK_DOWNLOAD_REDIRECT",
    "READBACK_RUN_END"
  ] as const),
  Object.freeze([
    "LOOKUP_RUN_START",
    "LOOKUP_JOBS",
    "LOOKUP_ARTIFACTS_1",
    "LOOKUP_RUN_END_1",
    "LOOKUP_ARTIFACTS_2",
    "LOOKUP_RUN_END_2",
    "READBACK_RUN_START",
    "READBACK_ARTIFACT",
    "READBACK_DOWNLOAD_REDIRECT",
    "READBACK_RUN_END"
  ] as const),
  Object.freeze([
    "LOOKUP_RUN_START",
    "LOOKUP_JOBS",
    "LOOKUP_ARTIFACTS_1",
    "LOOKUP_RUN_END_1",
    "LOOKUP_ARTIFACTS_2",
    "LOOKUP_RUN_END_2",
    "LOOKUP_ARTIFACTS_3",
    "LOOKUP_RUN_END_3",
    "READBACK_RUN_START",
    "READBACK_ARTIFACT",
    "READBACK_DOWNLOAD_REDIRECT",
    "READBACK_RUN_END"
  ] as const)
])

const assertionPhases = (
  entries: ReadonlyArray<S2SStageUploadAssertionLedgerEntry>
): ReadonlyArray<S2SStageUploadAssertionLedgerPhase> =>
  entries.slice(4).map((entry) => entry.phase)

const samePhases = (
  left: ReadonlyArray<S2SStageUploadAssertionLedgerPhase>,
  right: ReadonlyArray<S2SStageUploadAssertionLedgerPhase>
): boolean =>
  left.length === right.length &&
  left.every((phase, index) => phase === right[index])

const isCompleteTopology = (
  entries: ReadonlyArray<S2SStageUploadAssertionLedgerEntry>
): boolean => {
  const phases = assertionPhases(entries)
  return ASSERTION_TOPOLOGIES.some((expected) => samePhases(phases, expected))
}

const allowedNextPhases = (
  entries: ReadonlyArray<S2SStageUploadAssertionLedgerEntry>
): ReadonlySet<S2SStageUploadAssertionLedgerPhase> => {
  const phases = assertionPhases(entries)
  const allowed = new Set<S2SStageUploadAssertionLedgerPhase>()
  for (const topology of ASSERTION_TOPOLOGIES) {
    if (
      phases.length < topology.length &&
      phases.every((phase, index) => phase === topology[index])
    ) {
      const next = topology[phases.length]
      if (next !== undefined) allowed.add(next)
    }
  }
  return allowed
}

const snapshotLedgerObservation = (
  input: unknown
): S2SStageUploadAssertionLedgerObservation | null => {
  const record = exactPlainRecord(input, [
    "githubRequestId",
    "observedAtUnixSeconds",
    "receiptSha256"
  ])
  if (
    record === null ||
    typeof record["githubRequestId"] !== "string" ||
    !REQUEST_ID_PATTERN.test(record["githubRequestId"]) ||
    typeof record["receiptSha256"] !== "string" ||
    !SHA256_PATTERN.test(record["receiptSha256"]) ||
    !isSafeNonNegativeInteger(record["observedAtUnixSeconds"])
  ) {
    return null
  }
  return Object.freeze({
    githubRequestId: record["githubRequestId"],
    receiptSha256: record["receiptSha256"],
    observedAtUnixSeconds: record["observedAtUnixSeconds"]
  })
}

const appendLedgerEntry = (
  scope: S2SStageUploadAssertionPermitScope,
  lease: AssertionPermitLease | null,
  requiredMode: AssertionScopeState["mode"],
  phase: S2SStageUploadAssertionLedgerPhase,
  observation: unknown
): Effect.Effect<void, S2SStageUploadAssertionPermitError> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  if (inspected.right.mode !== requiredMode) {
    return Effect.fail(
      permitError(
        "INVALID_AUTHORITY",
        phase,
        "ledger admission mode does not match the issued scope"
      )
    )
  }
  const snapshot = snapshotLedgerObservation(observation)
  if (snapshot === null) {
    return Effect.fail(
      permitError(
        "LEDGER_ENTRY_REJECTED",
        phase,
        "ledger observation is not exact canonical metadata"
      )
    )
  }
  return Ref.modify(inspected.right.state, (state) => {
    if (
      state.status !== "IN_FLIGHT" ||
      (lease !== null && state.activeLease !== lease)
    ) {
      return [
        permitError(
          state.status === "CLOSED" ? "SCOPE_CLOSED" : "STAGE_VOID",
          phase,
          "ledger admission requires the exact in-flight assertion permit"
        ),
        state
      ] as const
    }
    if (state.ledgerEntries.length >= 16) {
      return [
        permitError(
          "LEDGER_CAPACITY_EXHAUSTED",
          phase,
          "the fixed non-evicting assertion ledger is full"
        ),
        state
      ] as const
    }
    if (!allowedNextPhases(state.ledgerEntries).has(phase)) {
      return [
        permitError(
          "LEDGER_ENTRY_REJECTED",
          phase,
          "ledger phase is not the next fixed assertion phase"
        ),
        state
      ] as const
    }
    if (
      state.ledgerEntries.some(
        (entry) => entry.githubRequestId === snapshot.githubRequestId
      )
    ) {
      return [
        permitError(
          "REQUEST_ID_REUSED",
          phase,
          "GitHub request ID already exists in the non-evicting ledger"
        ),
        state
      ] as const
    }
    if (
      state.ledgerEntries.some(
        (entry) => entry.receiptSha256 === snapshot.receiptSha256
      )
    ) {
      return [
        permitError(
          "RECEIPT_HASH_REUSED",
          phase,
          "receipt hash already exists in the non-evicting ledger"
        ),
        state
      ] as const
    }
    const previous = state.ledgerEntries.at(-1)
    if (
      previous !== undefined &&
      snapshot.observedAtUnixSeconds < previous.observedAtUnixSeconds
    ) {
      return [
        permitError(
          "OBSERVATION_ORDER_INVALID",
          phase,
          "ledger observation time is not monotonic"
        ),
        state
      ] as const
    }
    const entry: S2SStageUploadAssertionLedgerEntry = Object.freeze({
      operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
      phase,
      ...snapshot
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
}

/** @internal TEST-ONLY, NON-AUTHORIZING. */
export const appendS2SStageUploadAssertionLedgerEntryForTest = (
  scope: S2SStageUploadAssertionPermitScope,
  phase: S2SStageUploadAssertionLedgerPhase,
  observation: unknown
): Effect.Effect<void, S2SStageUploadAssertionPermitError> =>
  appendLedgerEntry(
    scope,
    null,
    "TEST_ONLY_NON_AUTHORIZING",
    phase,
    observation
  )

const reservePermit = (
  scope: S2SStageUploadAssertionPermitScope,
  requiredLayerClaim: AssertionLayerClaim | null = null
): Effect.Effect<AssertionPermitLease, S2SStageUploadAssertionPermitError> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  const lease: AssertionPermitLease = Object.freeze({
    [ASSERTION_PERMIT_LEASE_BRAND]: true as const
  })
  return Ref.modify(inspected.right.state, (state): readonly [
    AssertionPermitReservation,
    AssertionPermitState
  ] => {
    if (
      requiredLayerClaim !== null &&
      !state.layerClaims.includes(requiredLayerClaim)
    ) {
      return [
        Object.freeze({
          _tag: "Rejected" as const,
          error: permitError(
            "SCOPE_CLOSED",
            null,
            "the owning assertion Layer claim is no longer active"
          )
        }),
        state
      ] as const
    }
    switch (state.status) {
      case "ISSUED":
        return [
          Object.freeze({ _tag: "Reserved" as const, lease }),
          Object.freeze({
            ...state,
            status: "IN_FLIGHT" as const,
            activeLease: lease
          })
        ] as const
      case "IN_FLIGHT":
        return [
          Object.freeze({
            _tag: "Rejected" as const,
            error: permitError(
              "PERMIT_IN_FLIGHT",
              null,
              "the one-use assertion permit is already in flight"
            )
          }),
          state
        ] as const
      case "SPENT_SUCCESS":
        return [
          Object.freeze({
            _tag: "Rejected" as const,
            error: permitError(
              "PERMIT_ALREADY_SPENT",
              null,
              "the one-use assertion permit was already spent successfully"
            )
          }),
          state
        ] as const
      case "SPENT_VOID":
        return [
          Object.freeze({
            _tag: "Rejected" as const,
            error: permitError(
              "STAGE_VOID",
              null,
              "the one-use assertion permit was voided by its prior use"
            )
          }),
          state
        ] as const
      case "CLOSED":
        return [
          Object.freeze({
            _tag: "Rejected" as const,
            error: permitError(
              "SCOPE_CLOSED",
              null,
              "the assertion permit scope is closed"
            )
          }),
          state
        ] as const
    }
  }).pipe(
    Effect.flatMap((reserved) =>
      reserved._tag === "Rejected"
        ? Effect.fail(reserved.error)
        : Effect.succeed(reserved.lease)
    )
  )
}

export interface S2SStageUploadAssertionCompletion<A> {
  readonly outcome: S2SStageUploadOutcome
  readonly value: A
}

export interface S2SStageUploadAssertionClassifiedResult<A> {
  readonly classification: S2SStageUploadOutcomeClassification
  readonly value: A
}

interface ClassifiedCompletion<A> {
  readonly classification: S2SStageUploadOutcomeClassification
  readonly value: A
}

const classifyCompletion = <A>(
  input: S2SStageUploadAssertionCompletion<A>
): Either.Either<
  ClassifiedCompletion<A>,
  S2SStageUploadAssertionPermitError
> => {
  const record = exactPlainRecord(input, ["outcome", "value"])
  if (record === null) {
    return Either.left(
      permitError(
        "OUTCOME_CLASSIFICATION_INVALID",
        null,
        "assertion completion must be one exact outcome/value record"
      )
    )
  }
  const classified = classifyS2SStageUploadOutcome(record["outcome"])
  if (Either.isLeft(classified)) {
    return Either.left(
      permitError(
        "OUTCOME_CLASSIFICATION_INVALID",
        null,
        "assertion completion outcome is outside the frozen taxonomy"
      )
    )
  }
  return Either.right(
    Object.freeze({
      classification: classified.right,
      value: input.value
    })
  )
}

const validateHealthyCompletionTopology = <A>(
  scope: S2SStageUploadAssertionPermitScope,
  classified: ClassifiedCompletion<A>
): Effect.Effect<
  ClassifiedCompletion<A>,
  S2SStageUploadAssertionPermitError
> => {
  if (classified.classification._tag !== "Healthy") {
    return Effect.succeed(classified)
  }
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  return Ref.get(inspected.right.state).pipe(
    Effect.flatMap((state) =>
      state.status === "IN_FLIGHT" &&
      state.ledgerEntries.at(-1)?.phase === "READBACK_RUN_END" &&
      isCompleteTopology(state.ledgerEntries)
        ? Effect.succeed(classified)
        : Effect.fail(
            permitError(
              "EVIDENCE_NOT_SEALABLE",
              null,
              "a healthy assertion requires one exact completed in-flight topology"
            )
          )
    )
  )
}

const finalizePermit = <A, E>(
  scope: S2SStageUploadAssertionPermitScope,
  lease: AssertionPermitLease,
  exit: Exit.Exit<ClassifiedCompletion<A>, E>
): Effect.Effect<void> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.void
  return Ref.update(inspected.right.state, (state) => {
    if (state.status !== "IN_FLIGHT" || state.activeLease !== lease) {
      return state
    }
    const healthy =
      Exit.isSuccess(exit) && exit.value.classification._tag === "Healthy"
    return Object.freeze({
      ...state,
      status: healthy ? ("SPENT_SUCCESS" as const) : ("SPENT_VOID" as const),
      activeLease: null
    })
  })
}

/**
 * Atomically reserves one permit, runs one lazy assertion, and burns the
 * permit on every typed failure, defect, interruption, invalid outcome, or
 * nonhealthy successful classification.
 */
/** @internal TEST-ONLY, NON-AUTHORIZING. */
export const useS2SStageUploadAssertionPermitForTest = <A, E, R>(
  scope: S2SStageUploadAssertionPermitScope,
  use: () => Effect.Effect<S2SStageUploadAssertionCompletion<A>, E, R>
): Effect.Effect<
  S2SStageUploadAssertionClassifiedResult<A>,
  E | S2SStageUploadAssertionPermitError,
  R
> =>
  Effect.suspend(() => {
    const inspected = scopeState(scope)
    if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
    if (inspected.right.mode === "PRODUCTION") {
      return Effect.fail(
        permitError(
          "PRODUCTION_ASSERTION_SHELL_OPEN",
          null,
          "production permit use is closed until the module-local live assertion shell lands"
        )
      )
    }
    return Effect.acquireUseRelease(
      reservePermit(scope),
      (_lease) =>
        Effect.suspend(use).pipe(
          Effect.flatMap((completion) => {
            const classified = classifyCompletion<A>(completion)
            return Either.isLeft(classified)
              ? Effect.fail(classified.left)
              : validateHealthyCompletionTopology(scope, classified.right)
          })
        ),
      (lease, exit) => finalizePermit(scope, lease, exit)
    ).pipe(
      Effect.map((result) =>
        Object.freeze({
          classification: result.classification,
          value: result.value
        })
      )
    )
  })

const sealPermitEvidence = (
  scope: S2SStageUploadAssertionPermitScope,
  lease: AssertionPermitLease | null,
  requiredMode: AssertionScopeState["mode"]
): Effect.Effect<
  S2SStageUploadAssertionPermitEvidence,
  S2SStageUploadAssertionPermitError
> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  if (inspected.right.mode !== requiredMode) {
    return Effect.fail(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "permit evidence mode does not match the issued scope"
      )
    )
  }
  return Ref.get(inspected.right.state).pipe(
    Effect.flatMap((state) => {
      if (
        state.status !== "IN_FLIGHT" ||
        (lease !== null && state.activeLease !== lease) ||
        state.ledgerEntries.at(-1)?.phase !== "READBACK_RUN_END" ||
        !isCompleteTopology(state.ledgerEntries)
      ) {
        return Effect.fail(
          permitError(
            "EVIDENCE_NOT_SEALABLE",
            null,
            "permit evidence requires one exact completed in-flight topology"
          )
        )
      }
      const ledgerEntries = Object.freeze(
        state.ledgerEntries.map((entry) =>
          Object.freeze({
            operation: entry.operation,
            phase: entry.phase,
            githubRequestId: entry.githubRequestId,
            receiptSha256: S2SSha256Schema.make(entry.receiptSha256),
            observedAtUnixSeconds: entry.observedAtUnixSeconds
          })
        )
      )
      const core = Object.freeze({
        schemaVersion:
          S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION,
        authorityScope:
          inspected.right.mode === "PRODUCTION"
            ? ("TRUSTED_SINGLE_MODULE_CURRENT_JOB" as const)
            : ("TEST_ONLY_NON_AUTHORIZING" as const),
        authorizationClaimed: inspected.right.mode === "PRODUCTION",
        oneUseClaim:
          inspected.right.mode === "PRODUCTION"
            ? ("ONE_USE_PER_GENUINE_AUTHORITY_AND_PROCESS_IDENTITY_SLOT" as const)
            : ("MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE" as const),
        crossWorkerReplayPreventionClaimed: false as const,
        crossModuleCopyReplayPreventionClaimed: false as const,
        crossProcessReplayPreventionClaimed: false as const,
        durableReplayPreventionClaimed: false as const,
        identity: inspected.right.identity,
        operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
        ledgerCapacity: 16 as const,
        ledgerEntries
      })
      const receipt = canonicalS2SControlSha256(core)
      if (Either.isLeft(receipt)) {
        return Effect.fail(
          permitError(
            "EVIDENCE_NOT_CANONICAL",
            null,
            "assertion permit evidence cannot be canonically hashed"
          )
        )
      }
      return Effect.succeed(
        Object.freeze({
          ...core,
          receiptSha256: S2SSha256Schema.make(receipt.right)
        })
      )
    })
  )
}

/** @internal TEST-ONLY, NON-AUTHORIZING. */
export const snapshotS2SStageUploadAssertionPermitEvidenceForTest = (
  scope: S2SStageUploadAssertionPermitScope
): Effect.Effect<
  S2SStageUploadAssertionPermitEvidence,
  S2SStageUploadAssertionPermitError
> =>
  sealPermitEvidence(scope, null, "TEST_ONLY_NON_AUTHORIZING")

/** @internal TEST-ONLY, NON-AUTHORIZING compatibility close. */
export const closeS2SStageUploadAssertionPermitScope = (
  scope: S2SStageUploadAssertionPermitScope
): Effect.Effect<void> => {
  const inspected = scopeState(scope)
  return Either.isLeft(inspected) ||
    inspected.right.mode !== "TEST_ONLY_NON_AUTHORIZING"
    ? Effect.void
    : Ref.update(inspected.right.state, (state) =>
        state.status === "IN_FLIGHT"
          ? state
          : Object.freeze({
              ...state,
              status: "CLOSED" as const,
              activeLease: null
            })
      )
}

const closeTestScopeUnlessForeignUseIsInFlight = (
  scope: S2SStageUploadAssertionPermitScope
): Effect.Effect<void> => {
  const inspected = scopeState(scope)
  return Either.isLeft(inspected)
    ? Effect.void
    : Ref.update(inspected.right.state, (state) =>
        state.status === "IN_FLIGHT"
          ? state
          : Object.freeze({
              ...state,
              status: "CLOSED" as const,
              activeLease: null
            })
      )
}

export interface S2SStageUploadAssertionTestRunInput {
  readonly phase: Extract<
    S2SStageUploadAssertionLedgerPhase,
    | "LOOKUP_RUN_START"
    | `LOOKUP_RUN_END_${1 | 2 | 3}`
    | "READBACK_RUN_START"
    | "READBACK_RUN_END"
  >
  readonly workflowRunId: number
}

export interface S2SStageUploadAssertionTestJobsInput {
  readonly workflowRunId: number
  readonly workflowRunAttempt: 1
}

export interface S2SStageUploadAssertionTestArtifactListInput {
  readonly workflowRunId: number
  readonly artifactName: string
  readonly successfulAttemptCandidate: 1 | 2 | 3
}

export interface S2SStageUploadAssertionTestArtifactInput {
  readonly artifactId: number
}

export interface S2SStageUploadAssertionTestDownloadInput {
  readonly artifactId: number
  readonly maximumBytes: number
}

export interface S2SStageUploadAssertionTestSettleInput {
  readonly completedAttemptOrdinal: 1 | 2
}

export type S2SStageUploadAssertionTestNonHealthyOutcome =
  Exclude<
    S2SStageUploadOutcome,
    "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
  >

export type S2SStageUploadAssertionTestArtifactListResult =
  | {
      readonly _tag: "Absent"
      readonly observation: S2SStageUploadAssertionLedgerObservation
    }
  | {
      readonly _tag: "Observed"
      readonly observation: S2SStageUploadAssertionLedgerObservation
      readonly artifactId: number
    }
  | {
      readonly _tag: "NonHealthy"
      readonly observation: S2SStageUploadAssertionLedgerObservation
      readonly outcome: S2SStageUploadAssertionTestNonHealthyOutcome
    }

export type S2SStageUploadAssertionTestArtifactResult =
  | {
      readonly _tag: "Matched"
      readonly observation: S2SStageUploadAssertionLedgerObservation
    }
  | {
      readonly _tag: "NonHealthy"
      readonly observation: S2SStageUploadAssertionLedgerObservation
      readonly outcome: S2SStageUploadAssertionTestNonHealthyOutcome
    }

export type S2SStageUploadAssertionTestDownloadResult =
  | {
      readonly _tag: "Matched"
      readonly redirectReceipt: S2SStageUploadAssertionLedgerObservation
    }
  | {
      readonly _tag: "NonHealthy"
      readonly outcome: S2SStageUploadAssertionTestNonHealthyOutcome
    }

export interface S2SStageUploadAssertionTestObserver<E = never, R = never> {
  readonly observeWorkflowRun: (
    input: S2SStageUploadAssertionTestRunInput
  ) => Effect.Effect<S2SStageUploadAssertionLedgerObservation, E, R>
  readonly observeWorkflowAttemptJobs: (
    input: S2SStageUploadAssertionTestJobsInput
  ) => Effect.Effect<S2SStageUploadAssertionLedgerObservation, E, R>
  readonly observeRunArtifacts: (
    input: S2SStageUploadAssertionTestArtifactListInput
  ) => Effect.Effect<S2SStageUploadAssertionTestArtifactListResult, E, R>
  readonly observeArtifact: (
    input: S2SStageUploadAssertionTestArtifactInput
  ) => Effect.Effect<S2SStageUploadAssertionTestArtifactResult, E, R>
  readonly downloadArtifactArchive: (
    input: S2SStageUploadAssertionTestDownloadInput
  ) => Effect.Effect<S2SStageUploadAssertionTestDownloadResult, E, R>
  readonly settleAfterAbsence: (
    input: S2SStageUploadAssertionTestSettleInput
  ) => Effect.Effect<void, E, R>
}

const completion = <A>(
  outcome: S2SStageUploadOutcome,
  value: A
): S2SStageUploadAssertionCompletion<A> =>
  Object.freeze({ outcome, value })

const runTestAssertion = <E, R>(
  scope: S2SStageUploadAssertionPermitScope,
  observer: S2SStageUploadAssertionTestObserver<E, R>
): Effect.Effect<
  S2SStageUploadAssertionCompletion<
    S2SStageUploadAssertionPermitEvidence | null
  >,
  E | S2SStageUploadAssertionPermitError,
  R
> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  const runtime = inspected.right
  const runObservation = (
    phase: S2SStageUploadAssertionTestRunInput["phase"]
  ) =>
    observer
      .observeWorkflowRun({
        phase,
        workflowRunId: runtime.identity.workflowRunId
      })
      .pipe(
        Effect.tap((observation) =>
          appendS2SStageUploadAssertionLedgerEntryForTest(
            scope,
            phase,
            observation
          )
        )
      )
  return Effect.gen(function* () {
    yield* runObservation("LOOKUP_RUN_START")
    const jobs = yield* observer.observeWorkflowAttemptJobs({
      workflowRunId: runtime.identity.workflowRunId,
      workflowRunAttempt: 1
    })
    yield* appendS2SStageUploadAssertionLedgerEntryForTest(
      scope,
      "LOOKUP_JOBS",
      jobs
    )
    for (let attempt = 1 as 1 | 2 | 3; attempt <= 3; attempt += 1) {
      const ordinal = attempt as 1 | 2 | 3
      const listing = yield* observer.observeRunArtifacts({
        workflowRunId: runtime.identity.workflowRunId,
        artifactName: runtime.prepared.artifactName,
        successfulAttemptCandidate: ordinal
      })
      yield* appendS2SStageUploadAssertionLedgerEntryForTest(
        scope,
        `LOOKUP_ARTIFACTS_${ordinal}`,
        listing.observation
      )
      yield* runObservation(`LOOKUP_RUN_END_${ordinal}`)
      if (listing._tag === "NonHealthy") {
        return completion(listing.outcome, null)
      }
      if (listing._tag === "Absent") {
        if (ordinal === 3) {
          return completion(
            "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
            null
          )
        }
        yield* observer.settleAfterAbsence({
          completedAttemptOrdinal: ordinal
        })
        continue
      }
      yield* runObservation("READBACK_RUN_START")
      const artifact = yield* observer.observeArtifact({
        artifactId: listing.artifactId
      })
      yield* appendS2SStageUploadAssertionLedgerEntryForTest(
        scope,
        "READBACK_ARTIFACT",
        artifact.observation
      )
      if (artifact._tag === "NonHealthy") {
        return completion(artifact.outcome, null)
      }
      const download = yield* observer.downloadArtifactArchive({
        artifactId: listing.artifactId,
        maximumBytes: runtime.prepared.maximumArchiveBytes
      })
      if (download._tag === "NonHealthy") {
        return completion(download.outcome, null)
      }
      yield* appendS2SStageUploadAssertionLedgerEntryForTest(
        scope,
        "READBACK_DOWNLOAD_REDIRECT",
        download.redirectReceipt
      )
      yield* runObservation("READBACK_RUN_END")
      const evidence = yield* snapshotS2SStageUploadAssertionPermitEvidenceForTest(
        scope
      )
      return completion(
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED",
        evidence
      )
    }
    return completion(
      "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
      null
    )
  })
}

/**
 * @internal TEST-ONLY, NON-AUTHORIZING.
 *
 * Runs the fixed selector-free assertion topology against an injected fake
 * observer, returns only void, never touches the production registry, and
 * closes the fixture-bound scope on every exit.
 */
export const probeS2SStageUploadAssertionMechanicsForTest = <E, R>(
  fixture: S2SStageUploadAssertionPermitTestSeed | unknown,
  capability: S2SPreparedStageCarrierCapability | unknown,
  observer: S2SStageUploadAssertionTestObserver<E, R>
): Effect.Effect<void, E | S2SStageUploadAssertionPermitError, R> =>
  Effect.suspend(() => {
    const scope = makeS2SStageUploadAssertionPermitTestScope(
      fixture,
      capability
    )
    if (Either.isLeft(scope)) return Effect.fail(scope.left)
    return useS2SStageUploadAssertionPermitForTest(scope.right, () =>
      runTestAssertion(scope.right, observer)
    ).pipe(
      Effect.onExit(() =>
        closeTestScopeUnlessForeignUseIsInFlight(scope.right)
      ),
      Effect.asVoid
    )
  })

export const S2S_STAGE_UPLOAD_ASSERTION_SETTLE_MILLIS = 10_000 as const
export const S2S_STAGE_UPLOAD_ASSERTION_DOWNLOAD_PHASE_TIMEOUT_MILLIS =
  420_000 as const
export const S2S_STAGE_UPLOAD_ASSERTION_DERIVED_EXTERNAL_CAP_MILLIS =
  1_760_000 as const
export const S2S_STAGE_UPLOAD_ASSERTION_WHOLE_TIMEOUT_MILLIS =
  1_800_000 as const

if (
  S2S_STAGE_UPLOAD_ASSERTION_DOWNLOAD_PHASE_TIMEOUT_MILLIS !==
    S2S_GITHUB_METADATA_TIMEOUT_MILLIS +
      S2S_GITHUB_ARCHIVE_TIMEOUT_MILLIS ||
  S2S_STAGE_UPLOAD_ASSERTION_WHOLE_TIMEOUT_MILLIS -
    S2S_STAGE_UPLOAD_ASSERTION_DERIVED_EXTERNAL_CAP_MILLIS !==
    40_000
) {
  throw new Error("S2S stage-upload assertion deadline formula drifted")
}

type S2SStageUploadAssertionEmittableFailureOutcome = Exclude<
  S2SStageUploadOutcome,
  | "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
  | "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH"
  | "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED"
>

export class S2SStageUploadAssertionShellError extends Data.TaggedError(
  "S2SStageUploadAssertionShellError"
)<{
  readonly outcome: S2SStageUploadAssertionEmittableFailureOutcome
  readonly phase: S2SStageUploadAssertionLedgerPhase | "WHOLE_ASSERTION"
  readonly detail: string
  readonly causeTag: string | null
}> {}

export type S2SStageUploadAssertionFailure =
  | S2SStageUploadAssertionPermitError
  | S2SStageUploadAssertionShellError

const shellError = (
  outcome: S2SStageUploadAssertionEmittableFailureOutcome,
  phase: S2SStageUploadAssertionShellError["phase"],
  detail: string,
  causeTag: string | null = null
): S2SStageUploadAssertionShellError =>
  new S2SStageUploadAssertionShellError({
    outcome,
    phase,
    detail,
    causeTag
  })

type ProductionProcessContinuityPolicy =
  | { readonly status: "OPEN_UNTIL_TOPOLOGY_FROZEN" }
  | { readonly status: "PINNED_REVIEWED_PROCESS_CONTINUITY" }

const PRODUCTION_PROCESS_CONTINUITY_POLICY: ProductionProcessContinuityPolicy =
  Object.freeze({ status: "OPEN_UNTIL_TOPOLOGY_FROZEN" })

const productionAssertionPreflight = (
  workflowGate: Either.Either<void, S2SCurrentRunInputError>
): Either.Either<
  void,
  S2SCurrentRunInputError | S2SStageUploadAssertionPermitError
> => {
  if (Either.isLeft(workflowGate)) return workflowGate
  return PRODUCTION_PROCESS_CONTINUITY_POLICY.status ===
    "OPEN_UNTIL_TOPOLOGY_FROZEN"
    ? Either.left(
        permitError(
          "PRODUCTION_PROCESS_CONTINUITY_OPEN",
          null,
          "production process continuity is not yet pinned and reviewed"
        )
      )
    : Either.right(undefined)
}

/** @internal TEST-ONLY, NON-AUTHORIZING closed-workflow preflight probe. */
export const probeS2SProductionProcessContinuityGateForTest = ():
  Either.Either<void, S2SStageUploadAssertionPermitError> => {
  const result = productionAssertionPreflight(Either.right(undefined))
  return Either.isLeft(result) &&
    result.left instanceof S2SStageUploadAssertionPermitError
    ? Either.left(result.left)
    : Either.right(undefined)
}

const S2S_STAGE_UPLOAD_ASSERTION_COMPLETION_BRAND: unique symbol = Symbol(
  "hswm/S2SStageUploadAssertionCompletionCapability"
)

/** Opaque process-local bearer; serialized fields never restore authority. */
export interface S2SStageUploadAssertionCompletionCapability {
  readonly [S2S_STAGE_UPLOAD_ASSERTION_COMPLETION_BRAND]: true
}

const S2S_STAGE_UPLOAD_ASSERTION_REPLAY_BRAND: unique symbol = Symbol(
  "hswm/S2SStageUploadAssertionReplaySnapshot"
)

/** Module-authenticated, non-authorizing replay snapshot. */
export interface S2SStageUploadAssertionReplaySnapshot {
  readonly [S2S_STAGE_UPLOAD_ASSERTION_REPLAY_BRAND]: true
  readonly _tag: "ValidatedNonAuthorizingStageUploadAssertionReplay"
  readonly authorityScope:
    | "TRUSTED_SINGLE_MODULE_CURRENT_JOB"
    | "TEST_ONLY_NON_AUTHORIZING"
  readonly authorizationClaimed: false
  readonly outcome: "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
  readonly stage: S2SCurrentRunStageEvidence["stage"]
  readonly completionReceiptSha256: string
  readonly currentRunEvidenceReceiptSha256: string
  readonly preparationReceiptSha256: string
  readonly permitReceiptSha256: string
  readonly postconditionReceiptSha256: string
  readonly postconditionCarrierSha256: string
  readonly currentStageArchiveSha256: string
  readonly readPostconditionCarrierBytes: () => Uint8Array
  readonly readCurrentStageArchiveBytes: () => Uint8Array
}

export interface S2SStageUploadAssertionCompletionSnapshot {
  readonly authorityScope:
    | "TRUSTED_SINGLE_MODULE_CURRENT_JOB"
    | "TEST_ONLY_NON_AUTHORIZING"
  readonly authorizationClaimed: boolean
  readonly outcome: "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
  readonly stage: S2SCurrentRunStageEvidence["stage"]
  readonly completionReceiptSha256: string
  readonly currentRunEvidenceReceiptSha256: string
  readonly preparationReceiptSha256: string
  readonly permitReceiptSha256: string
  readonly postconditionReceiptSha256: string
  readonly postconditionCarrierSha256: string
  readonly currentStageArchiveSha256: string
  readonly postcondition: S2SStageUploadPostconditionSnapshot
  readonly readPostconditionCarrierBytes: () => Uint8Array
  readonly readCurrentStageArchiveBytes: () => Uint8Array
}

interface RetainedPreparedMember extends S2SStageUploadPreparedMember {
  readonly bytes: Uint8Array
}

interface AssertionCompletionRecord {
  readonly mode: AssertionScopeState["mode"]
  readonly scope: S2SStageUploadAssertionPermitScope
  readonly owner: object
  readonly preparedCapability: object
  readonly completion: S2SStageUploadAssertionCompletionCapability
  readonly current: S2SCurrentRunStageEvidence
  readonly prepared: S2SPreparedStageCarrierSnapshot
  readonly preparedMembers: ReadonlyArray<RetainedPreparedMember>
  readonly permit: S2SStageUploadAssertionPermitEvidence
  readonly postcondition: S2SStageUploadPostconditionSnapshot
  readonly postconditionCarrierBytes: Uint8Array
  readonly currentStageArchiveBytes: Uint8Array
  readonly completionReceiptSha256: string
}

interface AssertionReplayRecord {
  readonly record: AssertionCompletionRecord
  readonly snapshot: S2SStageUploadAssertionReplaySnapshot
}

interface HealthyAssertionCandidate {
  readonly witness: object
  readonly completion: S2SStageUploadAssertionCompletionCapability
  readonly record: AssertionCompletionRecord
}

const PRODUCTION_HEALTHY_WITNESSES = new WeakSet<object>()
const TEST_HEALTHY_WITNESSES = new WeakSet<object>()
const PRODUCTION_COMPLETIONS = new WeakMap<object, AssertionCompletionRecord>()
const TEST_COMPLETIONS = new WeakMap<object, AssertionCompletionRecord>()
const PRODUCTION_REPLAYS = new WeakMap<object, AssertionReplayRecord>()
const TEST_REPLAYS = new WeakMap<object, AssertionReplayRecord>()

export class S2SStageUploadAssertion extends Context.Tag(
  "hswm/S2S/StageUploadAssertion"
)<
  S2SStageUploadAssertion,
  {
    readonly assertAndRecover: Effect.Effect<
      S2SStageUploadAssertionCompletionCapability,
      S2SStageUploadAssertionFailure
    >
  }
>() {}

const observationLedgerMetadata = (
  observation: S2SGitHubObservation
): S2SStageUploadAssertionLedgerObservation =>
  Object.freeze({
    githubRequestId: observation.receipt.githubRequestId,
    receiptSha256: observation.receipt.receiptSha256,
    observedAtUnixSeconds: observation.receipt.observedAtUnixSeconds
  })

const expectedWorkflowPath = (
  current: S2SCurrentRunStageEvidence
): string =>
  current.workflowApiPath === S2S_CONFIRMATORY_WORKFLOW_PATH
    ? S2S_CONFIRMATORY_WORKFLOW_PATH
    : S2S_CONFIRMATORY_WORKFLOW_PATH_AT_MAIN

const hasExpectedRunIdentity = (
  run: S2SGitHubWorkflowRunProjection,
  current: S2SCurrentRunStageEvidence
): boolean =>
  run.id === current.workflowRunId &&
  run.runAttempt === 1 &&
  run.repository === S2S_CONFIRMATORY_REPOSITORY &&
  run.headRepository === S2S_CONFIRMATORY_REPOSITORY &&
  run.headSha === current.registrationCommitB &&
  run.name === S2S_CONFIRMATORY_WORKFLOW_NAME &&
  run.path === expectedWorkflowPath(current) &&
  run.event === S2S_CONFIRMATORY_EVENT &&
  run.headBranch === S2S_CONFIRMATORY_BRANCH &&
  run.createdAt === current.workflowRunCreatedAt &&
  run.createdAtUnixSeconds === current.workflowRunCreatedAtUnixSeconds &&
  run.status === "in_progress" &&
  run.conclusion === null

const sameRunIdentity = (
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

const validateLookupJobs = (
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  current: S2SCurrentRunStageEvidence
): Either.Either<
  S2SGitHubWorkflowJobProjection,
  S2SStageUploadAssertionShellError
> => {
  const projection = jobs.receipt.projection
  if (
    projection.totalCount !== S2S_CONFIRMATORY_JOB_STAGES.length ||
    projection.jobs.length !== S2S_CONFIRMATORY_JOB_STAGES.length ||
    jobs.receipt.observedAtUnixSeconds <
      run.receipt.observedAtUnixSeconds
  ) {
    return Either.left(
      shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        "LOOKUP_JOBS",
        "job roster count or observation order diverged"
      )
    )
  }
  const jobsByStage = new Map<
    (typeof S2S_CONFIRMATORY_JOB_STAGES)[number],
    S2SGitHubWorkflowJobProjection
  >()
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    const expectedName = S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobName
    const matches = projection.jobs.filter((job) => job.name === expectedName)
    if (matches.length !== 1 || matches[0] === undefined) {
      return Either.left(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "LOOKUP_JOBS",
          "job roster does not contain one exact row for every stage"
        )
      )
    }
    jobsByStage.set(stage, matches[0])
  }
  if (
    projection.jobs.some(
      (job) =>
        job.runId !== current.workflowRunId ||
        job.runAttempt !== 1 ||
        job.headSha !== current.registrationCommitB ||
        job.startedAtUnixSeconds <
          run.receipt.projection.createdAtUnixSeconds ||
        job.startedAtUnixSeconds > jobs.receipt.observedAtUnixSeconds
    )
  ) {
    return Either.left(
      shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        "LOOKUP_JOBS",
        "job run, head, or start time diverged"
      )
    )
  }
  const stageIndex = S2S_CONFIRMATORY_JOB_STAGES.indexOf(current.stage)
  const producer = jobsByStage.get(current.stage)
  if (
    stageIndex < 0 ||
    producer === undefined ||
    producer.id !== current.currentJobDatabaseId ||
    producer.status !== "in_progress" ||
    producer.conclusion !== null ||
    producer.completedAt !== null ||
    producer.completedAtUnixSeconds !== null
  ) {
    return Either.left(
      shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        "LOOKUP_JOBS",
        "authority-bound producer is not the sole current in-progress job"
      )
    )
  }
  const predecessorIds: Array<number> = []
  let previousCompletion = run.receipt.projection.createdAtUnixSeconds
  for (let index = 0; index < stageIndex; index += 1) {
    const stage = S2S_CONFIRMATORY_JOB_STAGES[index]
    const predecessor = stage === undefined ? undefined : jobsByStage.get(stage)
    if (
      predecessor === undefined ||
      predecessor.status !== "completed" ||
      predecessor.conclusion !== "success" ||
      predecessor.completedAtUnixSeconds === null ||
      predecessor.startedAtUnixSeconds < previousCompletion ||
      predecessor.completedAtUnixSeconds < predecessor.startedAtUnixSeconds ||
      predecessor.completedAtUnixSeconds > producer.startedAtUnixSeconds ||
      predecessor.completedAtUnixSeconds > jobs.receipt.observedAtUnixSeconds
    ) {
      return Either.left(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "LOOKUP_JOBS",
          "predecessor completion chain diverged"
        )
      )
    }
    predecessorIds.push(predecessor.id)
    previousCompletion = predecessor.completedAtUnixSeconds
  }
  if (
    predecessorIds.length !== current.predecessorJobDatabaseIds.length ||
    predecessorIds.some(
      (value, index) => value !== current.predecessorJobDatabaseIds[index]
    )
  ) {
    return Either.left(
      shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        "LOOKUP_JOBS",
        "predecessor job identities differ from current-run authority"
      )
    )
  }
  const notStarted = new Set(["queued", "waiting", "pending", "requested"])
  for (
    let index = stageIndex + 1;
    index < S2S_CONFIRMATORY_JOB_STAGES.length;
    index += 1
  ) {
    const stage = S2S_CONFIRMATORY_JOB_STAGES[index]
    const later = stage === undefined ? undefined : jobsByStage.get(stage)
    if (
      later === undefined ||
      !notStarted.has(later.status) ||
      later.conclusion !== null ||
      later.completedAt !== null ||
      later.completedAtUnixSeconds !== null
    ) {
      return Either.left(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "LOOKUP_JOBS",
          "a later stage has already started or completed"
        )
      )
    }
  }
  return Either.right(producer)
}

const sameArtifactProjection = (
  left: S2SGitHubArtifactProjection,
  right: S2SGitHubArtifactProjection
): boolean =>
  left.id === right.id &&
  left.name === right.name &&
  left.sizeInBytes === right.sizeInBytes &&
  left.digestSha256 === right.digestSha256 &&
  left.expired === right.expired &&
  left.createdAt === right.createdAt &&
  left.createdAtUnixSeconds === right.createdAtUnixSeconds &&
  left.expiresAt === right.expiresAt &&
  left.expiresAtUnixSeconds === right.expiresAtUnixSeconds &&
  left.workflowRunId === right.workflowRunId &&
  left.workflowHeadSha === right.workflowHeadSha

const classifyArtifactListing = (
  ordinal: 1 | 2 | 3,
  initialRun: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  producer: S2SGitHubWorkflowJobProjection,
  listing: S2SGitHubObservation<S2SGitHubArtifactsProjection>,
  closingRun: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  current: S2SCurrentRunStageEvidence,
  prepared: S2SPreparedStageCarrierSnapshot,
  previousObservedAtUnixSeconds: number
): Either.Either<
  S2SGitHubArtifactProjection | null,
  S2SStageUploadAssertionShellError
> => {
  const phase = `LOOKUP_ARTIFACTS_${ordinal}` as const
  if (
    listing.receipt.observedAtUnixSeconds < previousObservedAtUnixSeconds ||
    closingRun.receipt.observedAtUnixSeconds <
      listing.receipt.observedAtUnixSeconds ||
    !hasExpectedRunIdentity(closingRun.receipt.projection, current) ||
    !sameRunIdentity(
      initialRun.receipt.projection,
      closingRun.receipt.projection
    ) ||
    listing.receipt.projection.artifacts.some(
      (artifact) =>
        artifact.workflowRunId !== current.workflowRunId ||
        artifact.workflowHeadSha !== current.registrationCommitB
    )
  ) {
    return Either.left(
      shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        phase,
        "artifact listing bracket has run, head, or time drift"
      )
    )
  }
  const matching = listing.receipt.projection.artifacts.filter(
    (artifact) => artifact.name === prepared.artifactName
  )
  if (matching.length === 0) return Either.right(null)
  const selected = matching.length === 1 ? matching[0] : undefined
  if (
    selected === undefined ||
    selected.expired ||
    selected.createdAtUnixSeconds < producer.startedAtUnixSeconds ||
    selected.createdAtUnixSeconds > listing.receipt.observedAtUnixSeconds ||
    selected.expiresAtUnixSeconds <= listing.receipt.observedAtUnixSeconds ||
    selected.sizeInBytes > prepared.maximumArchiveBytes
  ) {
    return Either.left(
      shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        phase,
        "fixed-name artifact is duplicate, expired, oversized, or temporally impossible"
      )
    )
  }
  return Either.right(selected)
}

const githubObservationFailure = (
  error:
    | S2SGitHubObservationError
    | S2SGitHubObservationValidationError
    | S2SGitHubTransportError,
  phase: S2SStageUploadAssertionLedgerPhase
): S2SStageUploadAssertionShellError =>
  error instanceof S2SGitHubTransportError
    ? shellError(
        "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        phase,
        "GitHub transport outcome is unknown",
        error._tag
      )
    : error instanceof S2SGitHubObservationError &&
        error.reason === "IDENTITY_MISMATCH"
      ? shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase,
          "GitHub observation identifies a different run, job, or artifact",
          error._tag
        )
    : shellError(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        phase,
        "GitHub observation or strict wrapper validation failed",
        error._tag
      )

const mapDirectFailure = <A, E, E2, R>(
  effect: Effect.Effect<A, E, R>,
  mapFailure: (error: E) => E2
): Effect.Effect<A, E2, R> =>
  Effect.mapErrorCause(effect, Cause.map(mapFailure))

const metadataTimeoutFailure = (
  phase: S2SStageUploadAssertionLedgerPhase
): S2SStageUploadAssertionShellError =>
  shellError(
    "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
    phase,
    "GitHub metadata phase exceeded the fixed 120-second deadline",
    "S2SStageUploadAssertionMetadataTimeout"
  )

const observeValidatedRun = (
  github: S2SGitHubObserver["Type"],
  workflowRunId: number,
  phase: Extract<
    S2SStageUploadAssertionLedgerPhase,
    | "LOOKUP_RUN_START"
    | `LOOKUP_RUN_END_${1 | 2 | 3}`
    | "READBACK_RUN_START"
    | "READBACK_RUN_END"
  >
): Effect.Effect<
  S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  S2SStageUploadAssertionShellError
> =>
  mapDirectFailure(
    github.observeWorkflowRun(workflowRunId).pipe(
    Effect.flatMap((observation) =>
      validateS2SGitHubWorkflowRunObservation(observation, workflowRunId)
    )),
    (error) => githubObservationFailure(error, phase)
  ).pipe(
    Effect.timeoutFail({
      duration: S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
      onTimeout: () => metadataTimeoutFailure(phase)
    })
  )

const observeValidatedJobs = (
  github: S2SGitHubObserver["Type"],
  workflowRunId: number
): Effect.Effect<
  S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  S2SStageUploadAssertionShellError
> =>
  mapDirectFailure(
    github.observeWorkflowAttemptJobs(workflowRunId).pipe(
    Effect.flatMap((observation) =>
      validateS2SGitHubWorkflowAttemptJobsObservation(
        observation,
        workflowRunId
      )
    )),
    (error) => githubObservationFailure(error, "LOOKUP_JOBS")
  ).pipe(
    Effect.timeoutFail({
      duration: S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
      onTimeout: () => metadataTimeoutFailure("LOOKUP_JOBS")
    })
  )

const observeValidatedArtifacts = (
  github: S2SGitHubObserver["Type"],
  workflowRunId: number,
  ordinal: 1 | 2 | 3
): Effect.Effect<
  S2SGitHubObservation<S2SGitHubArtifactsProjection>,
  S2SStageUploadAssertionShellError
> => {
  const phase = `LOOKUP_ARTIFACTS_${ordinal}` as const
  return mapDirectFailure(
    github.observeRunArtifacts(workflowRunId).pipe(
    Effect.flatMap((observation) =>
      validateS2SGitHubRunArtifactsObservation(observation, workflowRunId)
    )),
    (error) => githubObservationFailure(error, phase)
  ).pipe(
    Effect.timeoutFail({
      duration: S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
      onTimeout: () => metadataTimeoutFailure(phase)
    })
  )
}

const observeValidatedArtifact = (
  github: S2SGitHubObserver["Type"],
  artifactId: number
): Effect.Effect<
  S2SGitHubObservation<S2SGitHubArtifactProjection>,
  S2SStageUploadAssertionShellError
> =>
  mapDirectFailure(
    github.observeArtifact(artifactId).pipe(
    Effect.flatMap((observation) =>
      validateS2SGitHubArtifactObservation(observation, artifactId)
    )),
    (error) => githubObservationFailure(error, "READBACK_ARTIFACT")
  ).pipe(
    Effect.timeoutFail({
      duration: S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
      onTimeout: () => metadataTimeoutFailure("READBACK_ARTIFACT")
    })
  )

const observeValidatedDownload = (
  github: S2SGitHubObserver["Type"],
  artifactId: number,
  maximumArchiveBytes: number
): Effect.Effect<
  S2SGitHubArtifactDownload,
  S2SStageUploadAssertionShellError
> =>
  mapDirectFailure(
    github.downloadArtifactArchive(artifactId, maximumArchiveBytes),
    (error) =>
      shellError(
        "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        "READBACK_DOWNLOAD_REDIRECT",
        "GitHub artifact download outcome is unknown",
        error._tag
      )
  ).pipe(
    Effect.flatMap((download) => {
      const validated = validateS2SGitHubArtifactDownload(
        download,
        artifactId,
        maximumArchiveBytes
      )
      return Either.isLeft(validated)
        ? Effect.fail(
            shellError(
              "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
              "READBACK_DOWNLOAD_REDIRECT",
              "artifact download receipt or retained bytes failed validation",
              validated.left._tag
            )
          )
        : Effect.succeed(validated.right)
    }),
    Effect.timeoutFail({
      duration: S2S_STAGE_UPLOAD_ASSERTION_DOWNLOAD_PHASE_TIMEOUT_MILLIS,
      onTimeout: () =>
        shellError(
          "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
          "READBACK_DOWNLOAD_REDIRECT",
          "artifact download phase exceeded the fixed 420-second deadline",
          "S2SStageUploadAssertionDownloadTimeout"
        )
    })
  )

const validateArchiveAgainstPreparation = (
  selected: S2SGitHubArtifactProjection,
  download: S2SGitHubArtifactDownload,
  prepared: S2SPreparedStageCarrierSnapshot
): Either.Either<Uint8Array, S2SStageUploadAssertionShellError> => {
  try {
    const archiveBytes = download.readArchiveBytes()
    if (
      download.receipt.archiveByteLength !== selected.sizeInBytes ||
      download.receipt.downloadedArchiveSha256 !== selected.digestSha256 ||
      archiveBytes.byteLength !== selected.sizeInBytes ||
      rawS2SFileSha256(archiveBytes) !== selected.digestSha256
    ) {
      return Either.left(
        shellError(
          "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          "READBACK_DOWNLOAD_REDIRECT",
          "download length or digest differs from the selected artifact"
        )
      )
    }
    const spec = S2S_STAGE_ARTIFACT_SPECS[prepared.stage]
    const archive = validateS2SArtifactZip(archiveBytes, {
      expectedArchiveSha256: S2SSha256Schema.make(selected.digestSha256),
      expectedArchiveByteLength: selected.sizeInBytes,
      expectedMembers: spec.expectedMembers,
      maximumArchiveBytes: prepared.maximumArchiveBytes,
      maximumExpandedBytes: prepared.maximumExpandedBytes
    })
    if (Either.isLeft(archive)) {
      return Either.left(
        shellError(
          "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          "READBACK_DOWNLOAD_REDIRECT",
          `downloaded stored ZIP failed strict validation: ${archive.left.reason}`,
          archive.left._tag
        )
      )
    }
    if (archive.right.members.length !== prepared.members.length) {
      return Either.left(
        shellError(
          "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          "READBACK_DOWNLOAD_REDIRECT",
          "archive member count differs from the prepared stage tuple"
        )
      )
    }
    for (let index = 0; index < archive.right.members.length; index += 1) {
      const actual = archive.right.members[index]
      const expected = prepared.members[index]
      if (actual === undefined || expected === undefined) {
        return Either.left(
          shellError(
            "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
            "READBACK_DOWNLOAD_REDIRECT",
            "archive member tuple is sparse"
          )
        )
      }
      const expectedBytes = expected.readBytes()
      const actualBytes = actual.readBytes()
      if (
        actual.name !== expected.name ||
        actual.byteLength !== expected.byteLength ||
        actual.rawBytesSha256 !== expected.rawBytesSha256 ||
        expectedBytes.byteLength !== expected.byteLength ||
        rawS2SFileSha256(expectedBytes) !== expected.rawBytesSha256 ||
        actualBytes.byteLength !== expectedBytes.byteLength ||
        actualBytes.some((byte, byteIndex) => byte !== expectedBytes[byteIndex])
      ) {
        return Either.left(
          shellError(
            "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
            "READBACK_DOWNLOAD_REDIRECT",
            "archive member metadata or bytes differ from preparation"
          )
        )
      }
    }
    return Either.right(Uint8Array.from(archiveBytes))
  } catch (error) {
    return Either.left(
      shellError(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        "READBACK_DOWNLOAD_REDIRECT",
        "archive or prepared-member byte access failed closed",
        error instanceof Error ? error.name : null
      )
    )
  }
}

const postconditionFailure = (
  error: S2SStageUploadPostconditionError
): S2SStageUploadAssertionShellError =>
  error.reason === "STAGE_IDENTITY_MISMATCH" ||
  error.reason === "ARTIFACT_BINDING_MISMATCH" ||
  error.reason === "OBSERVATION_TOPOLOGY_INVALID"
    ? shellError(
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        "READBACK_RUN_END",
        error.detail,
        error._tag
      )
    : shellError(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        "READBACK_RUN_END",
        error.detail,
        error._tag
      )

const retainPreparedMembers = (
  prepared: S2SPreparedStageCarrierSnapshot
): Either.Either<
  ReadonlyArray<RetainedPreparedMember>,
  S2SStageUploadAssertionShellError
> => {
  try {
    const retained: Array<RetainedPreparedMember> = []
    for (const member of prepared.members) {
      const bytes = member.readBytes()
      if (
        bytes.byteLength !== member.byteLength ||
        rawS2SFileSha256(bytes) !== member.rawBytesSha256
      ) {
        return Either.left(
          shellError(
            "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
            "READBACK_RUN_END",
            "prepared member drifted before completion retention"
          )
        )
      }
      const snapshot = Uint8Array.from(bytes)
      retained.push(
        Object.freeze({
          name: member.name,
          byteLength: snapshot.byteLength,
          rawBytesSha256: member.rawBytesSha256,
          bytes: snapshot,
          readBytes: (): Uint8Array => Uint8Array.from(snapshot)
        })
      )
    }
    return Either.right(Object.freeze(retained))
  } catch {
    return Either.left(
      shellError(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        "READBACK_RUN_END",
        "prepared member retention failed closed"
      )
    )
  }
}

interface FixedAssertionRuntime {
  readonly scope: S2SStageUploadAssertionPermitScope
  readonly layerClaim: AssertionLayerClaim
  readonly lease: AssertionPermitLease
  readonly mode: AssertionScopeState["mode"]
  readonly owner: object
  readonly preparedCapability: object
  readonly current: S2SCurrentRunStageEvidence
  readonly prepared: S2SPreparedStageCarrierSnapshot
  readonly github: S2SGitHubObserver["Type"]
}

const makeHealthyAssertionCandidate = (
  runtime: FixedAssertionRuntime,
  permit: S2SStageUploadAssertionPermitEvidence,
  postcondition: S2SStageUploadPostconditionSnapshot,
  archiveBytesInput: Uint8Array
): Either.Either<
  HealthyAssertionCandidate,
  S2SStageUploadAssertionShellError
> => {
  try {
    const retainedMembers = retainPreparedMembers(runtime.prepared)
    if (Either.isLeft(retainedMembers)) return Either.left(retainedMembers.left)
    const postconditionCarrierBytes = postcondition.readCarrierBytes()
    const archiveBytes = Uint8Array.from(archiveBytesInput)
    const postconditionCarrierSha256 = rawS2SFileSha256(
      postconditionCarrierBytes
    )
    const currentStageArchiveSha256 = rawS2SFileSha256(archiveBytes)
    if (
      postconditionCarrierSha256 !== postcondition.carrierRawSha256 ||
      currentStageArchiveSha256 !==
        postcondition.manifest.artifact_sha256 ||
      permit.receiptSha256 !==
        postcondition.manifest.assertion_permit_evidence.receiptSha256
    ) {
      return Either.left(
        shellError(
          "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          "READBACK_RUN_END",
          "postcondition bytes or permit binding drifted before completion"
        )
      )
    }
    const authorityScope =
      runtime.mode === "PRODUCTION"
        ? ("TRUSTED_SINGLE_MODULE_CURRENT_JOB" as const)
        : ("TEST_ONLY_NON_AUTHORIZING" as const)
    const completionCore = Object.freeze({
      schemaVersion: "hswm-swm0w-s2s-stage-upload-assertion-completion/v1",
      authorityScope,
      authorizationClaimed: runtime.mode === "PRODUCTION",
      outcome:
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
      stage: runtime.current.stage,
      currentRunEvidenceReceiptSha256: runtime.current.receiptSha256,
      preparationReceiptSha256: runtime.prepared.preparationReceiptSha256,
      permitReceiptSha256: permit.receiptSha256,
      postconditionReceiptSha256:
        postcondition.manifest.postcondition_receipt_sha256,
      postconditionCarrierSha256,
      postconditionCarrierByteLength: postconditionCarrierBytes.byteLength,
      currentStageArchiveSha256,
      currentStageArchiveByteLength: archiveBytes.byteLength,
      historicalUniquenessClaimed: false,
      crossProcessReplayPreventionClaimed: false,
      durableReplayPreventionClaimed: false,
      externalExactlyOnceClaimed: false
    })
    const completionReceipt = canonicalS2SControlSha256(completionCore)
    if (Either.isLeft(completionReceipt)) {
      return Either.left(
        shellError(
          "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          "READBACK_RUN_END",
          "completion record is not canonically hashable"
        )
      )
    }
    const completion: S2SStageUploadAssertionCompletionCapability =
      Object.freeze({
        [S2S_STAGE_UPLOAD_ASSERTION_COMPLETION_BRAND]: true as const
      })
    const witness = Object.freeze({})
    const record: AssertionCompletionRecord = Object.freeze({
      mode: runtime.mode,
      scope: runtime.scope,
      owner: runtime.owner,
      preparedCapability: runtime.preparedCapability,
      completion,
      current: runtime.current,
      prepared: runtime.prepared,
      preparedMembers: retainedMembers.right,
      permit,
      postcondition,
      postconditionCarrierBytes: Uint8Array.from(postconditionCarrierBytes),
      currentStageArchiveBytes: archiveBytes,
      completionReceiptSha256: completionReceipt.right
    })
    ;(runtime.mode === "PRODUCTION"
      ? PRODUCTION_HEALTHY_WITNESSES
      : TEST_HEALTHY_WITNESSES
    ).add(witness)
    return Either.right(Object.freeze({ witness, completion, record }))
  } catch (error) {
    return Either.left(
      shellError(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        "READBACK_RUN_END",
        "completion candidate construction failed closed",
        error instanceof Error ? error.name : null
      )
    )
  }
}

const runFixedAssertion = (
  runtime: FixedAssertionRuntime
): Effect.Effect<
  HealthyAssertionCandidate,
  S2SStageUploadAssertionFailure
> =>
  Effect.gen(function* () {
    const observations: Array<S2SStageUploadBuildObservation> = []
    const retainObservation = (
      phase: S2SStageUploadBuildObservation["phase"],
      observation: S2SGitHubObservation
    ): Effect.Effect<void, S2SStageUploadAssertionPermitError> =>
      appendLedgerEntry(
        runtime.scope,
        runtime.lease,
        runtime.mode,
        phase,
        observationLedgerMetadata(observation)
      ).pipe(
        Effect.tap(() =>
          Effect.sync(() => {
            observations.push(Object.freeze({ phase, observation }))
          })
        )
      )

    const initialRun = yield* observeValidatedRun(
      runtime.github,
      runtime.current.workflowRunId,
      "LOOKUP_RUN_START"
    )
    if (
      initialRun.receipt.observedAtUnixSeconds <
        runtime.current.observations.runEnd.observedAtUnixSeconds ||
      !hasExpectedRunIdentity(initialRun.receipt.projection, runtime.current)
    ) {
      return yield* Effect.fail(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "LOOKUP_RUN_START",
          "lookup run identity, state, or observation time diverged"
        )
      )
    }
    yield* retainObservation("LOOKUP_RUN_START", initialRun)

    const jobs = yield* observeValidatedJobs(
      runtime.github,
      runtime.current.workflowRunId
    )
    const producer = validateLookupJobs(initialRun, jobs, runtime.current)
    if (Either.isLeft(producer)) return yield* Effect.fail(producer.left)
    yield* retainObservation("LOOKUP_JOBS", jobs)

    let selectedArtifact: S2SGitHubArtifactProjection | undefined
    let successfulAttemptOrdinal: 1 | 2 | 3 | undefined
    let previousObservedAtUnixSeconds = jobs.receipt.observedAtUnixSeconds
    for (const ordinal of [1, 2, 3] as const) {
      const listing = yield* observeValidatedArtifacts(
        runtime.github,
        runtime.current.workflowRunId,
        ordinal
      )
      const closingRunPhase = `LOOKUP_RUN_END_${ordinal}` as const
      const closingRun = yield* observeValidatedRun(
        runtime.github,
        runtime.current.workflowRunId,
        closingRunPhase
      )
      const decision = classifyArtifactListing(
        ordinal,
        initialRun,
        producer.right,
        listing,
        closingRun,
        runtime.current,
        runtime.prepared,
        previousObservedAtUnixSeconds
      )
      if (Either.isLeft(decision)) return yield* Effect.fail(decision.left)
      const listingPhase = `LOOKUP_ARTIFACTS_${ordinal}` as const
      yield* retainObservation(listingPhase, listing)
      yield* retainObservation(closingRunPhase, closingRun)
      previousObservedAtUnixSeconds =
        closingRun.receipt.observedAtUnixSeconds
      if (decision.right === null) {
        if (ordinal === 3) {
          return yield* Effect.fail(
            shellError(
              "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
              listingPhase,
              "three valid bracketed observations found no fixed-name artifact"
            )
          )
        }
        yield* Effect.sleep(S2S_STAGE_UPLOAD_ASSERTION_SETTLE_MILLIS)
        continue
      }
      selectedArtifact = decision.right
      successfulAttemptOrdinal = ordinal
      break
    }
    if (
      selectedArtifact === undefined ||
      successfulAttemptOrdinal === undefined
    ) {
      return yield* Effect.fail(
        shellError(
          "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
          "LOOKUP_ARTIFACTS_3",
          "bounded artifact lookup ended without one selected artifact"
        )
      )
    }

    const readbackStart = yield* observeValidatedRun(
      runtime.github,
      runtime.current.workflowRunId,
      "READBACK_RUN_START"
    )
    if (
      readbackStart.receipt.observedAtUnixSeconds <
        previousObservedAtUnixSeconds ||
      !hasExpectedRunIdentity(readbackStart.receipt.projection, runtime.current) ||
      !sameRunIdentity(
        initialRun.receipt.projection,
        readbackStart.receipt.projection
      )
    ) {
      return yield* Effect.fail(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "READBACK_RUN_START",
          "readback-start run identity or time diverged"
        )
      )
    }
    yield* retainObservation("READBACK_RUN_START", readbackStart)

    const artifact = yield* observeValidatedArtifact(
      runtime.github,
      selectedArtifact.id
    )
    if (
      artifact.receipt.observedAtUnixSeconds <
        readbackStart.receipt.observedAtUnixSeconds ||
      artifact.receipt.projection.expired ||
      artifact.receipt.projection.expiresAtUnixSeconds <=
        artifact.receipt.observedAtUnixSeconds ||
      !sameArtifactProjection(
        artifact.receipt.projection,
        selectedArtifact
      )
    ) {
      return yield* Effect.fail(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "READBACK_ARTIFACT",
          "exact artifact requery or observation time diverged"
        )
      )
    }
    yield* retainObservation("READBACK_ARTIFACT", artifact)

    const download = yield* observeValidatedDownload(
      runtime.github,
      selectedArtifact.id,
      runtime.prepared.maximumArchiveBytes
    )
    if (
      download.receipt.downloadedAtUnixSeconds <
        artifact.receipt.observedAtUnixSeconds ||
      selectedArtifact.expiresAtUnixSeconds <=
        download.receipt.downloadedAtUnixSeconds
    ) {
      return yield* Effect.fail(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "READBACK_DOWNLOAD_REDIRECT",
          "download receipt predates the exact artifact requery"
        )
      )
    }
    yield* appendLedgerEntry(
      runtime.scope,
      runtime.lease,
      runtime.mode,
      "READBACK_DOWNLOAD_REDIRECT",
      Object.freeze({
        githubRequestId: download.receipt.redirectGitHubRequestId,
        receiptSha256: download.receipt.receiptSha256,
        observedAtUnixSeconds: download.receipt.downloadedAtUnixSeconds
      })
    )
    const archive = validateArchiveAgainstPreparation(
      selectedArtifact,
      download,
      runtime.prepared
    )
    if (Either.isLeft(archive)) return yield* Effect.fail(archive.left)

    const finalRun = yield* observeValidatedRun(
      runtime.github,
      runtime.current.workflowRunId,
      "READBACK_RUN_END"
    )
    if (
      finalRun.receipt.observedAtUnixSeconds <
        download.receipt.downloadedAtUnixSeconds ||
      !hasExpectedRunIdentity(finalRun.receipt.projection, runtime.current) ||
      !sameRunIdentity(
        readbackStart.receipt.projection,
        finalRun.receipt.projection
      )
    ) {
      return yield* Effect.fail(
        shellError(
          "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          "READBACK_RUN_END",
          "final fresh run identity, state, or time diverged"
        )
      )
    }
    yield* retainObservation("READBACK_RUN_END", finalRun)

    const permit = yield* sealPermitEvidence(
      runtime.scope,
      runtime.lease,
      runtime.mode
    )
    const buildInput = Object.freeze({
      artifactDownload: download,
      assertionPermitEvidence: permit,
      currentRunEvidence: runtime.current,
      observations: Object.freeze([...observations]),
      preparedMembers: runtime.prepared.members,
      successfulAttemptOrdinal
    })
    const built =
      runtime.mode === "PRODUCTION"
        ? buildS2SStageUploadPostconditionFromProductionShell(buildInput)
        : buildS2SStageUploadPostcondition(buildInput)
    if (Either.isLeft(built)) {
      return yield* Effect.fail(postconditionFailure(built.left))
    }
    const independentlyValidated = validateS2SStageUploadPostcondition({
      carrierBytes: built.right.readCarrierBytes(),
      currentRunEvidence: runtime.current,
      currentStageArchiveBytes: archive.right,
      preparedMembers: runtime.prepared.members
    })
    if (Either.isLeft(independentlyValidated)) {
      return yield* Effect.fail(postconditionFailure(independentlyValidated.left))
    }
    if (
      independentlyValidated.right.carrierRawSha256 !==
        built.right.carrierRawSha256 ||
      independentlyValidated.right.manifest.postcondition_receipt_sha256 !==
        built.right.manifest.postcondition_receipt_sha256
    ) {
      return yield* Effect.fail(
        shellError(
          "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          "READBACK_RUN_END",
          "independent postcondition revalidation diverged"
        )
      )
    }
    const candidate = makeHealthyAssertionCandidate(
      runtime,
      permit,
      independentlyValidated.right,
      archive.right
    )
    return Either.isLeft(candidate)
      ? yield* Effect.fail(candidate.left)
      : candidate.right
  })

const acquireAssertionLayerClaim = (
  scope: S2SStageUploadAssertionPermitScope,
  requiredMode: AssertionScopeState["mode"]
): Effect.Effect<AssertionLayerClaim, S2SStageUploadAssertionPermitError> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  if (inspected.right.mode !== requiredMode) {
    return Effect.fail(
      permitError(
        "INVALID_AUTHORITY",
        null,
        "Layer claim mode does not match the issued assertion scope"
      )
    )
  }
  const claim: AssertionLayerClaim = Object.freeze({
    [ASSERTION_LAYER_CLAIM_BRAND]: true as const
  })
  return Ref.modify(inspected.right.state, (state) =>
    state.status === "CLOSED"
      ? [
          permitError(
            "SCOPE_CLOSED",
            null,
            "the assertion permit scope is closed"
          ),
          state
        ] as const
      : [
          null,
          Object.freeze({
            ...state,
            layerClaims: Object.freeze([...state.layerClaims, claim])
          })
        ] as const
  ).pipe(
    Effect.flatMap((error) =>
      error === null ? Effect.succeed(claim) : Effect.fail(error)
    )
  )
}

const releaseAssertionLayerClaim = (
  scope: S2SStageUploadAssertionPermitScope,
  claim: AssertionLayerClaim
): Effect.Effect<void> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.void
  return Ref.update(inspected.right.state, (state) => {
    if (!state.layerClaims.includes(claim)) return state
    const layerClaims = Object.freeze(
      state.layerClaims.filter((candidate) => candidate !== claim)
    )
    return Object.freeze({
      ...state,
      status:
        layerClaims.length === 0 && state.status === "ISSUED"
          ? ("CLOSED" as const)
          : state.status,
      activeLease:
        layerClaims.length === 0 && state.status === "ISSUED"
          ? null
          : state.activeLease,
      layerClaims
    })
  })
}

const finalizeFixedAssertion = (
  runtime: Omit<FixedAssertionRuntime, "github">,
  exit: Exit.Exit<HealthyAssertionCandidate, S2SStageUploadAssertionFailure>
): Effect.Effect<void> => {
  const inspected = scopeState(runtime.scope)
  if (Either.isLeft(inspected)) return Effect.void
  const registry =
    runtime.mode === "PRODUCTION"
      ? PRODUCTION_COMPLETIONS
      : TEST_COMPLETIONS
  const witnesses =
    runtime.mode === "PRODUCTION"
      ? PRODUCTION_HEALTHY_WITNESSES
      : TEST_HEALTHY_WITNESSES
  if (!Exit.isSuccess(exit)) {
    return Ref.update(inspected.right.state, (state) =>
      state.status === "IN_FLIGHT" && state.activeLease === runtime.lease
        ? Object.freeze({
            ...state,
            status: "SPENT_VOID" as const,
            activeLease: null
          })
        : state
    )
  }
  const candidate = exit.value
  return Ref.get(inspected.right.state).pipe(
    Effect.flatMap((state) => {
      const authentic =
        state.status === "IN_FLIGHT" &&
        state.activeLease === runtime.lease &&
        state.layerClaims.includes(runtime.layerClaim) &&
        state.ledgerEntries.at(-1)?.phase === "READBACK_RUN_END" &&
        isCompleteTopology(state.ledgerEntries) &&
        witnesses.has(candidate.witness) &&
        candidate.record.mode === runtime.mode &&
        candidate.record.scope === runtime.scope &&
        candidate.record.owner === runtime.owner &&
        candidate.record.preparedCapability === runtime.preparedCapability
      const registered = authentic
        ? yieldRegistryRegistration(registry, candidate)
        : Effect.succeed(false)
      return registered.pipe(
        Effect.flatMap((didRegister) =>
          Ref.modify(inspected.right.state, (latest) => {
            const leaseExact =
              latest.status === "IN_FLIGHT" &&
              latest.activeLease === runtime.lease
            const committed =
              leaseExact &&
              latest.layerClaims.includes(runtime.layerClaim) &&
              didRegister
            return [
              committed,
              leaseExact
                ? Object.freeze({
                    ...latest,
                    status: committed
                      ? ("SPENT_SUCCESS" as const)
                      : ("SPENT_VOID" as const),
                    activeLease: null
                  })
                : latest
            ] as const
          })
        ),
        Effect.flatMap((committed) =>
          committed
            ? Effect.void
            : Effect.sync(() => {
                registry.delete(candidate.completion)
              })
        )
      )
    })
  )
}

const yieldRegistryRegistration = (
  registry: WeakMap<object, AssertionCompletionRecord>,
  candidate: HealthyAssertionCandidate
): Effect.Effect<boolean> =>
  Effect.sync(() => {
    try {
      registry.set(candidate.completion, candidate.record)
      return true
    } catch {
      return false
    }
  })

const runOneFixedAssertion = <R>(
  scope: S2SStageUploadAssertionPermitScope,
  layerClaim: AssertionLayerClaim,
  mode: AssertionScopeState["mode"],
  owner: object,
  preparedCapability: object,
  acquireObserver: Effect.Effect<
    S2SGitHubObserver["Type"],
    S2SStageUploadAssertionShellError,
    R
  >
): Effect.Effect<
  S2SStageUploadAssertionCompletionCapability,
  S2SStageUploadAssertionFailure,
  R
> =>
  Effect.suspend(() => {
    const inspected = scopeState(scope)
    if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
    if (inspected.right.mode !== mode) {
      return Effect.fail(
        permitError(
          "INVALID_AUTHORITY",
          null,
          "assertion operation mode does not match the issued scope"
        )
      )
    }
    return Effect.acquireUseRelease(
      reservePermit(scope, layerClaim),
      (lease) =>
        acquireObserver.pipe(
          Effect.flatMap((github) =>
            runFixedAssertion({
              scope,
              layerClaim,
              lease,
              mode,
              owner,
              preparedCapability,
              current: inspected.right.current,
              prepared: inspected.right.prepared,
              github
            })
          ),
          Effect.timeoutFail({
            duration: S2S_STAGE_UPLOAD_ASSERTION_WHOLE_TIMEOUT_MILLIS,
            onTimeout: () =>
              shellError(
                "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
                "WHOLE_ASSERTION",
                "whole assertion use exceeded the fixed 1,800-second deadline",
                "S2SStageUploadAssertionWholeTimeout"
              )
          })
        ),
      (lease, exit) =>
        finalizeFixedAssertion(
          {
            scope,
            layerClaim,
            lease,
            mode,
            owner,
            preparedCapability,
            current: inspected.right.current,
            prepared: inspected.right.prepared
          },
          exit
        )
    ).pipe(
      Effect.flatMap((candidate) =>
        completionRecord(
          mode,
          owner,
          preparedCapability,
          candidate.completion
        ).pipe(Effect.as(candidate.completion))
      )
    )
  })

interface AssertionLayerResource {
  readonly scope: S2SStageUploadAssertionPermitScope
  readonly claim: AssertionLayerClaim
  readonly owner: object
  readonly preparedCapability: object
}

const makeAssertionService = (
  resource: AssertionLayerResource,
  mode: AssertionScopeState["mode"],
  acquireObserver: Effect.Effect<
    S2SGitHubObserver["Type"],
    S2SStageUploadAssertionShellError
  >
) =>
  S2SStageUploadAssertion.of({
    assertAndRecover: runOneFixedAssertion(
      resource.scope,
      resource.claim,
      mode,
      resource.owner,
      resource.preparedCapability,
      acquireObserver
    )
  })

const makeS2SStageUploadAssertionTestLayerWithAcquisition = (
  fixture: S2SStageUploadAssertionPermitTestSeed | unknown,
  capability: S2SPreparedStageCarrierCapability | unknown,
  acquireObserver: Effect.Effect<
    S2SGitHubObserver["Type"],
    S2SStageUploadAssertionShellError
  >
) =>
  Layer.scoped(
    S2SStageUploadAssertion,
    Effect.acquireRelease(
      Effect.suspend(() => {
        const scope = makeS2SStageUploadAssertionPermitTestScope(
          fixture,
          capability
        )
        if (Either.isLeft(scope)) return Effect.fail(scope.left)
        if (
          fixture === null ||
          typeof fixture !== "object" ||
          capability === null ||
          typeof capability !== "object"
        ) {
          return Effect.fail(
            permitError(
              "TEST_SEED_INVALID",
              null,
              "test Layer requires exact object identities"
            )
          )
        }
        return acquireAssertionLayerClaim(
          scope.right,
          "TEST_ONLY_NON_AUTHORIZING"
        ).pipe(
          Effect.map((claim) =>
            Object.freeze({
              scope: scope.right,
              claim,
              owner: fixture,
              preparedCapability: capability
            })
          )
        )
      }),
      (resource) =>
        releaseAssertionLayerClaim(resource.scope, resource.claim)
    ).pipe(
      Effect.map((resource) =>
        makeAssertionService(
          resource,
          "TEST_ONLY_NON_AUTHORIZING",
          acquireObserver
        )
      )
    )
  )

/** @internal TEST-ONLY, NON-AUTHORIZING full-semantics Layer. */
export const makeS2SStageUploadAssertionTestLayer = (
  fixture: S2SStageUploadAssertionPermitTestSeed | unknown,
  capability: S2SPreparedStageCarrierCapability | unknown,
  github: S2SGitHubObserver["Type"]
) =>
  makeS2SStageUploadAssertionTestLayerWithAcquisition(
    fixture,
    capability,
    Effect.succeed(github)
  )

/** @internal TEST-ONLY, NON-AUTHORIZING convenience probe. */
export const probeS2SStageUploadAssertionShellForTest = (
  fixture: S2SStageUploadAssertionPermitTestSeed | unknown,
  capability: S2SPreparedStageCarrierCapability | unknown,
  github: S2SGitHubObserver["Type"]
): Effect.Effect<
  S2SStageUploadAssertionCompletionCapability,
  S2SStageUploadAssertionFailure
> =>
  Effect.gen(function* () {
    const assertion = yield* S2SStageUploadAssertion
    return yield* assertion.assertAndRecover
  }).pipe(
    Effect.provide(
      makeS2SStageUploadAssertionTestLayer(fixture, capability, github)
    )
  )

/** @internal TEST-ONLY, NON-AUTHORIZING whole-use deadline probe. */
export const probeS2SStageUploadAssertionWholeTimeoutForTest = (
  fixture: S2SStageUploadAssertionPermitTestSeed | unknown,
  capability: S2SPreparedStageCarrierCapability | unknown,
  onObserverAcquisition: Effect.Effect<void>
): Effect.Effect<
  S2SStageUploadAssertionCompletionCapability,
  S2SStageUploadAssertionFailure
> =>
  Effect.gen(function* () {
    const assertion = yield* S2SStageUploadAssertion
    return yield* assertion.assertAndRecover
  }).pipe(
    Effect.provide(
      makeS2SStageUploadAssertionTestLayerWithAcquisition(
        fixture,
        capability,
        onObserverAcquisition.pipe(Effect.zipRight(Effect.never))
      )
    )
  )

const closedAssertionLayer = (
  failure: S2SCurrentRunInputError | S2SStageUploadAssertionPermitError
) => Layer.effect(S2SStageUploadAssertion, Effect.fail(failure))

/**
 * Root-private production Layer. Workflow-source and process-continuity gates
 * are evaluated before current-run service access, capability inspection,
 * GitHub configuration, transport/observer construction, scope claim, or I/O.
 */
export const makeS2SStageUploadAssertionLiveLayer = (
  preparedCapability: S2SPreparedStageCarrierCapability,
  githubConfig: S2SGitHubLiveTransportConfig
) => {
  const preflight = productionAssertionPreflight(
    requireS2SProductionWorkflowSourcePolicy()
  )
  if (Either.isLeft(preflight)) return closedAssertionLayer(preflight.left)
  return Layer.scoped(
    S2SStageUploadAssertion,
    Effect.gen(function* () {
      const current = yield* S2SCurrentRunStage
      const resource = yield* Effect.acquireRelease(
        Effect.suspend(() => {
          const scope = claimS2SStageUploadAssertionPermitScope(
            current.authority,
            preparedCapability
          )
          if (Either.isLeft(scope)) return Effect.fail(scope.left)
          return acquireAssertionLayerClaim(scope.right, "PRODUCTION").pipe(
            Effect.map((claim) =>
              Object.freeze({
                scope: scope.right,
                claim,
                owner: current.authority,
                preparedCapability
              })
            )
          )
        }),
        (acquired) =>
          releaseAssertionLayerClaim(acquired.scope, acquired.claim)
      )
      const liveObserverLayer = S2SGitHubObserverLive.pipe(
        Layer.provide(makeS2SGitHubHttpTransportLiveLayer(githubConfig))
      )
      const liveAssertion = runOneFixedAssertion(
        resource.scope,
        resource.claim,
        "PRODUCTION",
        resource.owner,
        resource.preparedCapability,
        Effect.gen(function* () {
          return yield* S2SGitHubObserver
        })
      ).pipe(Effect.provide(liveObserverLayer))
      return S2SStageUploadAssertion.of({
        assertAndRecover: mapDirectFailure(liveAssertion, (error) =>
          error instanceof S2SGitHubTransportError
            ? shellError(
                "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
                "LOOKUP_RUN_START",
                "live GitHub observer construction failed closed",
                error._tag
              )
            : error
        )
      })
    })
  )
}

const completionRecord = (
  mode: AssertionScopeState["mode"],
  owner: unknown,
  preparedCapability: unknown,
  completion: unknown
): Effect.Effect<
  AssertionCompletionRecord,
  S2SStageUploadAssertionPermitError
> =>
  Effect.suspend(() => {
    if (
      owner === null ||
      typeof owner !== "object" ||
      preparedCapability === null ||
      typeof preparedCapability !== "object" ||
      completion === null ||
      typeof completion !== "object"
    ) {
      return Effect.fail(
        permitError(
          "INVALID_COMPLETION_CAPABILITY",
          null,
          "completion inspection requires exact object identities"
        )
      )
    }
    const registry =
      mode === "PRODUCTION" ? PRODUCTION_COMPLETIONS : TEST_COMPLETIONS
    let record: AssertionCompletionRecord | undefined
    try {
      record = registry.get(completion)
    } catch {
      record = undefined
    }
    if (
      record === undefined ||
      record.mode !== mode ||
      record.owner !== owner ||
      record.preparedCapability !== preparedCapability
    ) {
      return Effect.fail(
        permitError(
          "INVALID_COMPLETION_CAPABILITY",
          null,
          "completion was not issued for these exact module-local bearers"
        )
      )
    }
    const inspected = scopeState(record.scope)
    if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
    return Ref.get(inspected.right.state).pipe(
      Effect.flatMap((state) =>
        state.status === "SPENT_SUCCESS" &&
        state.activeLease === null &&
        isCompleteTopology(state.ledgerEntries)
          ? Effect.succeed(record)
          : Effect.fail(
              permitError(
                "INVALID_COMPLETION_CAPABILITY",
                null,
                "completion registry and successful permit state diverged"
              )
            )
      )
    )
  })

const publicCompletionSnapshot = (
  record: AssertionCompletionRecord
): S2SStageUploadAssertionCompletionSnapshot => {
  const postconditionCarrierBytes = Uint8Array.from(
    record.postconditionCarrierBytes
  )
  const currentStageArchiveBytes = Uint8Array.from(
    record.currentStageArchiveBytes
  )
  return Object.freeze({
    authorityScope:
      record.mode === "PRODUCTION"
        ? ("TRUSTED_SINGLE_MODULE_CURRENT_JOB" as const)
        : ("TEST_ONLY_NON_AUTHORIZING" as const),
    authorizationClaimed: record.mode === "PRODUCTION",
    outcome:
      "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
    stage: record.current.stage,
    completionReceiptSha256: record.completionReceiptSha256,
    currentRunEvidenceReceiptSha256: record.current.receiptSha256,
    preparationReceiptSha256: record.prepared.preparationReceiptSha256,
    permitReceiptSha256: record.permit.receiptSha256,
    postconditionReceiptSha256:
      record.postcondition.manifest.postcondition_receipt_sha256,
    postconditionCarrierSha256: record.postcondition.carrierRawSha256,
    currentStageArchiveSha256: rawS2SFileSha256(currentStageArchiveBytes),
    postcondition: record.postcondition,
    readPostconditionCarrierBytes: (): Uint8Array =>
      Uint8Array.from(postconditionCarrierBytes),
    readCurrentStageArchiveBytes: (): Uint8Array =>
      Uint8Array.from(currentStageArchiveBytes)
  })
}

export const inspectS2SStageUploadAssertionCompletion = (
  authority: unknown,
  preparedCapability: unknown,
  completion: unknown
): Effect.Effect<
  S2SStageUploadAssertionCompletionSnapshot,
  S2SStageUploadAssertionPermitError
> =>
  completionRecord(
    "PRODUCTION",
    authority,
    preparedCapability,
    completion
  ).pipe(Effect.map(publicCompletionSnapshot))

/** @internal TEST-ONLY, NON-AUTHORIZING completion inspector. */
export const inspectS2SStageUploadAssertionCompletionForTest = (
  fixture: unknown,
  preparedCapability: unknown,
  completion: unknown
): Effect.Effect<
  S2SStageUploadAssertionCompletionSnapshot,
  S2SStageUploadAssertionPermitError
> =>
  completionRecord(
    "TEST_ONLY_NON_AUTHORIZING",
    fixture,
    preparedCapability,
    completion
  ).pipe(Effect.map(publicCompletionSnapshot))

const makeReplaySnapshot = (
  record: AssertionCompletionRecord
): Either.Either<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionShellError
> => {
  const preparedMembers = record.preparedMembers.map((member) =>
    Object.freeze({
      name: member.name,
      byteLength: member.byteLength,
      rawBytesSha256: member.rawBytesSha256,
      readBytes: (): Uint8Array => Uint8Array.from(member.bytes)
    })
  )
  const validated = validateS2SStageUploadPostcondition({
    carrierBytes: Uint8Array.from(record.postconditionCarrierBytes),
    currentRunEvidence: record.current,
    currentStageArchiveBytes: Uint8Array.from(
      record.currentStageArchiveBytes
    ),
    preparedMembers
  })
  if (Either.isLeft(validated)) {
    return Either.left(postconditionFailure(validated.left))
  }
  if (
    validated.right.carrierRawSha256 !==
      record.postcondition.carrierRawSha256 ||
    validated.right.manifest.postcondition_receipt_sha256 !==
      record.postcondition.manifest.postcondition_receipt_sha256 ||
    validated.right.assertionPermitEvidence.receiptSha256 !==
      record.permit.receiptSha256
  ) {
    return Either.left(
      shellError(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        "READBACK_RUN_END",
        "retained completion bytes diverged during replay"
      )
    )
  }
  const postconditionCarrierBytes = Uint8Array.from(
    record.postconditionCarrierBytes
  )
  const currentStageArchiveBytes = Uint8Array.from(
    record.currentStageArchiveBytes
  )
  return Either.right(
    Object.freeze({
      [S2S_STAGE_UPLOAD_ASSERTION_REPLAY_BRAND]: true as const,
      _tag: "ValidatedNonAuthorizingStageUploadAssertionReplay" as const,
      authorityScope:
        record.mode === "PRODUCTION"
          ? ("TRUSTED_SINGLE_MODULE_CURRENT_JOB" as const)
          : ("TEST_ONLY_NON_AUTHORIZING" as const),
      authorizationClaimed: false as const,
      outcome:
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
      stage: record.current.stage,
      completionReceiptSha256: record.completionReceiptSha256,
      currentRunEvidenceReceiptSha256: record.current.receiptSha256,
      preparationReceiptSha256: record.prepared.preparationReceiptSha256,
      permitReceiptSha256: record.permit.receiptSha256,
      postconditionReceiptSha256:
        record.postcondition.manifest.postcondition_receipt_sha256,
      postconditionCarrierSha256: record.postcondition.carrierRawSha256,
      currentStageArchiveSha256: rawS2SFileSha256(currentStageArchiveBytes),
      readPostconditionCarrierBytes: (): Uint8Array =>
        Uint8Array.from(postconditionCarrierBytes),
      readCurrentStageArchiveBytes: (): Uint8Array =>
        Uint8Array.from(currentStageArchiveBytes)
    })
  )
}

const materializeReplay = (
  mode: AssertionScopeState["mode"],
  owner: unknown,
  preparedCapability: unknown,
  completion: unknown
): Effect.Effect<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionFailure
> =>
  completionRecord(mode, owner, preparedCapability, completion).pipe(
    Effect.flatMap((record) => {
      const replay = makeReplaySnapshot(record)
      if (Either.isLeft(replay)) return Effect.fail(replay.left)
      const registry =
        mode === "PRODUCTION" ? PRODUCTION_REPLAYS : TEST_REPLAYS
      return Effect.sync(() => {
        registry.set(
          replay.right,
          Object.freeze({ record, snapshot: replay.right })
        )
        return replay.right
      })
    })
  )

export const materializeS2SStageUploadAssertionReplay = (
  authority: unknown,
  preparedCapability: unknown,
  completion: unknown
): Effect.Effect<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionFailure
> =>
  materializeReplay(
    "PRODUCTION",
    authority,
    preparedCapability,
    completion
  )

/** @internal TEST-ONLY, NON-AUTHORIZING replay materializer. */
export const materializeS2SStageUploadAssertionReplayForTest = (
  fixture: unknown,
  preparedCapability: unknown,
  completion: unknown
): Effect.Effect<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionFailure
> =>
  materializeReplay(
    "TEST_ONLY_NON_AUTHORIZING",
    fixture,
    preparedCapability,
    completion
  )

const inspectReplay = (
  mode: AssertionScopeState["mode"],
  owner: unknown,
  preparedCapability: unknown,
  replay: unknown
): Effect.Effect<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionPermitError
> =>
  Effect.suspend(() => {
    if (
      owner === null ||
      typeof owner !== "object" ||
      preparedCapability === null ||
      typeof preparedCapability !== "object" ||
      replay === null ||
      typeof replay !== "object"
    ) {
      return Effect.fail(
        permitError(
          "INVALID_REPLAY_SNAPSHOT",
          null,
          "replay inspection requires exact object identities"
        )
      )
    }
    const registry = mode === "PRODUCTION" ? PRODUCTION_REPLAYS : TEST_REPLAYS
    let replayRecord: AssertionReplayRecord | undefined
    try {
      replayRecord = registry.get(replay)
    } catch {
      replayRecord = undefined
    }
    if (
      replayRecord === undefined ||
      replayRecord.snapshot !== replay ||
      replayRecord.record.mode !== mode ||
      replayRecord.record.owner !== owner ||
      replayRecord.record.preparedCapability !== preparedCapability
    ) {
      return Effect.fail(
        permitError(
          "INVALID_REPLAY_SNAPSHOT",
          null,
          "replay was not materialized for these exact module-local bearers"
        )
      )
    }
    return completionRecord(
      mode,
      owner,
      preparedCapability,
      replayRecord.record.completion
    ).pipe(
      Effect.as(replayRecord.snapshot),
      Effect.mapError(() =>
        permitError(
          "INVALID_REPLAY_SNAPSHOT",
          null,
          "replay completion state is no longer authentic"
        )
      )
    )
  })

export const inspectS2SStageUploadAssertionReplay = (
  authority: unknown,
  preparedCapability: unknown,
  replay: unknown
): Effect.Effect<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionPermitError
> => inspectReplay("PRODUCTION", authority, preparedCapability, replay)

/** @internal TEST-ONLY, NON-AUTHORIZING replay inspector. */
export const inspectS2SStageUploadAssertionReplayForTest = (
  fixture: unknown,
  preparedCapability: unknown,
  replay: unknown
): Effect.Effect<
  S2SStageUploadAssertionReplaySnapshot,
  S2SStageUploadAssertionPermitError
> =>
  inspectReplay(
    "TEST_ONLY_NON_AUTHORIZING",
    fixture,
    preparedCapability,
    replay
  )
