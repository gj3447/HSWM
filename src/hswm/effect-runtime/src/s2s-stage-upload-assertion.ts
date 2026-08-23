import { types as nodeTypes } from "node:util"

import { Data, Effect, Either, Exit, Ref } from "effect"

import {
  canonicalS2SControlSha256
} from "./s2s-canonical.js"
import {
  S2SGitCommitShaSchema,
  S2SSha256Schema
} from "./s2s-confirmatory.js"
import {
  inspectS2SPreparedStageCarrierCapability,
  inspectS2SPreparedStageCarrierTestCapability,
  type S2SPreparedStageCarrierCapability,
  type S2SPreparedStageCarrierSnapshot
} from "./s2s-prepared-stage-carrier.js"
import {
  inspectS2SCurrentRunStageAuthority,
  type S2SCurrentRunStageEvidence
} from "./s2s-run-authority.js"
import { validateS2SCurrentRunStageEvidence } from "./s2s-stage-artifact-read-replay.js"
import {
  S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
  S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION
} from "./s2s-stage-upload-postcondition-contract.js"
import type { S2SStageUploadAssertionPermitEvidence } from "./s2s-stage-upload-postcondition.js"
import {
  classifyS2SStageUploadOutcome,
  type S2SStageUploadOutcome,
  type S2SStageUploadOutcomeClassification
} from "./s2s-stage-upload-outcome.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_WORKFLOW_PATH
} from "./s2s-workflow-contract.js"

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
    | "PREPARED_CAPABILITY_BINDING_MISMATCH"
    | "PRODUCTION_SEMANTIC_SLOT_OCCUPIED"
    | "PRODUCTION_ASSERTION_SHELL_OPEN"
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
}

interface AssertionScopeState {
  readonly mode: "PRODUCTION" | "TEST_ONLY_NON_AUTHORIZING"
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
    identity: identity.right,
    prepared,
    state: Ref.unsafeMake<AssertionPermitState>(
      Object.freeze({
        status: "ISSUED" as const,
        ledgerEntries
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

/** @internal TEST-ONLY, NON-AUTHORIZING. */
export const appendS2SStageUploadAssertionLedgerEntryForTest = (
  scope: S2SStageUploadAssertionPermitScope,
  phase: S2SStageUploadAssertionLedgerPhase,
  observation: unknown
): Effect.Effect<void, S2SStageUploadAssertionPermitError> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  if (inspected.right.mode === "PRODUCTION") {
    return Effect.fail(
      permitError(
        "PRODUCTION_ASSERTION_SHELL_OPEN",
        phase,
        "production observation admission is closed until the module-local live assertion shell lands"
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
    if (state.status !== "IN_FLIGHT") {
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

const reservePermit = (
  scope: S2SStageUploadAssertionPermitScope
): Effect.Effect<void, S2SStageUploadAssertionPermitError> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  return Ref.modify(inspected.right.state, (state) => {
    switch (state.status) {
      case "ISSUED":
        return [
          null,
          Object.freeze({ ...state, status: "IN_FLIGHT" as const })
        ] as const
      case "IN_FLIGHT":
        return [
          permitError(
            "PERMIT_IN_FLIGHT",
            null,
            "the one-use assertion permit is already in flight"
          ),
          state
        ] as const
      case "SPENT_SUCCESS":
        return [
          permitError(
            "PERMIT_ALREADY_SPENT",
            null,
            "the one-use assertion permit was already spent successfully"
          ),
          state
        ] as const
      case "SPENT_VOID":
        return [
          permitError(
            "STAGE_VOID",
            null,
            "the one-use assertion permit was voided by its prior use"
          ),
          state
        ] as const
      case "CLOSED":
        return [
          permitError(
            "SCOPE_CLOSED",
            null,
            "the assertion permit scope is closed"
          ),
          state
        ] as const
    }
  }).pipe(
    Effect.flatMap((error) =>
      error === null ? Effect.void : Effect.fail(error)
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
  exit: Exit.Exit<ClassifiedCompletion<A>, E>
): Effect.Effect<void> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.void
  return Ref.update(inspected.right.state, (state) => {
    if (state.status === "CLOSED") return state
    const healthy =
      Exit.isSuccess(exit) && exit.value.classification._tag === "Healthy"
    return Object.freeze({
      ...state,
      status: healthy ? ("SPENT_SUCCESS" as const) : ("SPENT_VOID" as const)
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
      () =>
        Effect.suspend(use).pipe(
          Effect.flatMap((completion) => {
            const classified = classifyCompletion<A>(completion)
            return Either.isLeft(classified)
              ? Effect.fail(classified.left)
              : validateHealthyCompletionTopology(scope, classified.right)
          })
        ),
      (_reserved, exit) => finalizePermit(scope, exit)
    ).pipe(
      Effect.map((result) =>
        Object.freeze({
          classification: result.classification,
          value: result.value
        })
      )
    )
  })

/** @internal TEST-ONLY, NON-AUTHORIZING. */
export const snapshotS2SStageUploadAssertionPermitEvidenceForTest = (
  scope: S2SStageUploadAssertionPermitScope
): Effect.Effect<
  S2SStageUploadAssertionPermitEvidence,
  S2SStageUploadAssertionPermitError
> => {
  const inspected = scopeState(scope)
  if (Either.isLeft(inspected)) return Effect.fail(inspected.left)
  if (inspected.right.mode === "PRODUCTION") {
    return Effect.fail(
      permitError(
        "PRODUCTION_ASSERTION_SHELL_OPEN",
        null,
        "production evidence sealing is closed until the module-local live assertion shell lands"
      )
    )
  }
  return Ref.get(inspected.right.state).pipe(
    Effect.flatMap((state) => {
      if (
        state.status !== "IN_FLIGHT" ||
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

export const closeS2SStageUploadAssertionPermitScope = (
  scope: S2SStageUploadAssertionPermitScope
): Effect.Effect<void> => {
  const inspected = scopeState(scope)
  return Either.isLeft(inspected)
    ? Effect.void
    : Ref.update(inspected.right.state, (state) =>
        Object.freeze({ ...state, status: "CLOSED" as const })
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
          : Object.freeze({ ...state, status: "CLOSED" as const })
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
