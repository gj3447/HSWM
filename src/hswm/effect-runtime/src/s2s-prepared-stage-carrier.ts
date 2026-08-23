import { types as nodeTypes } from "node:util"

import { Data, Either, Schema } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2SArtifactEvidenceSchema,
  type S2SArtifactEvidence
} from "./s2s-confirmatory.js"
import {
  prepareS2SAdjudicationCarrier,
  prepareS2SCandidateCarrier,
  prepareS2SRegistrationCarrier,
  type S2SAdjudicationCarrierPlan,
  type S2SAdjudicationStageEvents,
  type S2SCandidateCarrierPlan,
  type S2SCandidateStageEvents,
  type S2SCarrierReadback,
  type S2SJobSequenceFailure,
  type S2SRegistrationCarrierPlan,
  type S2SRegistrationStageEvents,
  type S2SUploadMember
} from "./s2s-job-sequence.js"
import {
  inspectS2SCurrentRunStageAuthority,
  type S2SCurrentRunInputError,
  type S2SCurrentRunStageAuthority,
  type S2SCurrentRunStageEvidence
} from "./s2s-run-authority.js"
import {
  inspectS2SStageArtifactReadReplaySnapshot,
  validateS2SCandidateReadReplayPair,
  type S2SStageArtifactReadReplayError,
  type S2SStageArtifactReadReplaySnapshot
} from "./s2s-stage-artifact-read-replay.js"
import {
  S2S_STAGE_ARTIFACT_SPECS,
  type S2SStageArtifactArchiveLogicalName,
  type S2SStageArtifactArchiveProfileRole,
  type S2SStageArtifactCarrierSchemaVersion
} from "./s2s-stage-artifact-spec.js"
import type {
  S2SConfirmatoryArtifactRole,
  S2SConfirmatoryJobId,
  S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"

export const S2S_PREPARED_STAGE_CARRIER_SCHEMA_VERSION =
  "hswm-swm0w-s2s-prepared-stage-carrier/v1" as const

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const RFC3339_UTC_SECONDS_PATTERN =
  /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/

const S2S_PREPARED_STAGE_CARRIER_BRAND: unique symbol = Symbol(
  "hswm/S2SPreparedStageCarrierCapability"
)

/**
 * Opaque process-local bearer. The symbol is only a TypeScript brand;
 * authenticity is the private WeakMap identity below.
 */
export interface S2SPreparedStageCarrierCapability {
  readonly [S2S_PREPARED_STAGE_CARRIER_BRAND]: true
}

export interface S2SPreparedStageCarrierMember {
  readonly name:
    | "control_receipt.json"
    | "numeric_candidate.json"
    | "numeric_adjudication.json"
  readonly byteLength: number
  readonly rawBytesSha256: string
  /** A new defensive copy is returned on every call. */
  readonly readBytes: () => Uint8Array
}

export interface S2SPreparedStageCarrierSnapshot {
  readonly schemaVersion: typeof S2S_PREPARED_STAGE_CARRIER_SCHEMA_VERSION
  readonly authorityScope:
    | "TRUSTED_SINGLE_MODULE_CURRENT_JOB"
    | "TEST_ONLY_NON_AUTHORIZING"
  readonly authorizationClaimed: boolean
  readonly oneSemanticProductionSlotClaimed: boolean
  readonly stage: S2SConfirmatoryJobStage
  readonly role: S2SConfirmatoryArtifactRole
  readonly jobId: S2SConfirmatoryJobId
  readonly jobName: S2SConfirmatoryJobId
  readonly artifactName: string
  readonly archiveLogicalName: S2SStageArtifactArchiveLogicalName
  readonly archiveProfileRole: S2SStageArtifactArchiveProfileRole
  readonly carrierSchemaVersion: S2SStageArtifactCarrierSchemaVersion
  readonly maximumArchiveBytes: number
  readonly maximumExpandedBytes: number
  readonly sourceCommitA: string
  readonly currentRunEvidenceReceiptSha256: string
  readonly workflowRunId: number
  readonly workflowRunAttempt: 1
  readonly registrationCommitB: string
  readonly workflowApiPath: string
  readonly workflowRunCreatedAt: string
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly currentJobDatabaseId: number
  readonly predecessorJobDatabaseIds: ReadonlyArray<number>
  readonly predecessorReplayReceiptSha256s: ReadonlyArray<string>
  readonly predecessorReplayCarrierSha256s: ReadonlyArray<string>
  readonly carrierRawSha256: string
  readonly carrierByteLength: number
  readonly members: ReadonlyArray<S2SPreparedStageCarrierMember>
  readonly preparationReceiptSha256: string
}

export interface S2SRegisterPreparedCarrierInput {
  readonly events: S2SRegistrationStageEvents
}

export interface S2SConfirmPreparedCarrierInput {
  readonly registrationReplay: S2SStageArtifactReadReplaySnapshot
  readonly numericCandidateBytes: Uint8Array
  readonly events: S2SCandidateStageEvents
}

export interface S2SAdjudicatePreparedCarrierInput {
  readonly registrationReplay: S2SStageArtifactReadReplaySnapshot
  readonly candidateFirstReplay: S2SStageArtifactReadReplaySnapshot
  readonly candidateRereadReplay: S2SStageArtifactReadReplaySnapshot
  readonly numericAdjudicationBytes: Uint8Array
  readonly events: S2SAdjudicationStageEvents
}

/** The authority, never this union, selects the production stage. */
export type S2SCurrentStageCarrierInput =
  | S2SRegisterPreparedCarrierInput
  | S2SConfirmPreparedCarrierInput
  | S2SAdjudicatePreparedCarrierInput

export interface S2SPreparedStageCarrierTestSeed {
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly stage: S2SConfirmatoryJobStage
  readonly sourceCommitA: string
  readonly currentRunEvidenceReceiptSha256: string
  readonly workflowRunId: number
  readonly registrationCommitB: string
  readonly workflowApiPath: string
  readonly workflowRunCreatedAt: string
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly currentJobDatabaseId: number
  readonly predecessorJobDatabaseIds: ReadonlyArray<number>
}

export interface S2SConfirmPreparedCarrierTestInput {
  readonly registrationReadback: S2SCarrierReadback
  readonly numericCandidateBytes: Uint8Array
  readonly events: S2SCandidateStageEvents
}

export interface S2SAdjudicatePreparedCarrierTestInput {
  readonly registrationReadback: S2SCarrierReadback
  readonly candidateReadback: S2SCarrierReadback
  readonly numericAdjudicationBytes: Uint8Array
  readonly events: S2SAdjudicationStageEvents
}

export type S2SPreparedStageCarrierTestInput =
  | S2SRegisterPreparedCarrierInput
  | S2SConfirmPreparedCarrierTestInput
  | S2SAdjudicatePreparedCarrierTestInput

export class S2SPreparedStageCarrierError extends Data.TaggedError(
  "S2SPreparedStageCarrierError"
)<{
  readonly reason:
    | "AUTHORITY_CAPABILITY_MISMATCH"
    | "EVIDENCE_NOT_CANONICAL"
    | "INPUT_INVALID"
    | "INVALID_CAPABILITY"
    | "PREDECESSOR_REPLAY_BINDING_MISMATCH"
    | "PREPARATION_CONFLICT"
    | "PREPARED_MEMBER_MISMATCH"
    | "PRODUCTION_IDENTITY_SLOT_OCCUPIED"
  readonly stage: S2SConfirmatoryJobStage | null
  readonly detail: string
}> {}

export type S2SPreparedStageCarrierFailure =
  | S2SCurrentRunInputError
  | S2SStageArtifactReadReplayError
  | S2SJobSequenceFailure
  | S2SPreparedStageCarrierError

interface PreparedIdentity {
  readonly stage: S2SConfirmatoryJobStage
  readonly sourceCommitA: string
  readonly currentRunEvidenceReceiptSha256: string
  readonly workflowRunId: number
  readonly workflowRunAttempt: 1
  readonly registrationCommitB: string
  readonly workflowApiPath: string
  readonly workflowRunCreatedAt: string
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly currentJobDatabaseId: number
  readonly predecessorJobDatabaseIds: ReadonlyArray<number>
}

interface InternalPreparedMember {
  readonly name: S2SPreparedStageCarrierMember["name"]
  readonly byteLength: number
  readonly rawBytesSha256: string
  readonly bytes: Uint8Array
}

interface InternalPreparedSnapshot extends PreparedIdentity {
  readonly authorityScope: S2SPreparedStageCarrierSnapshot["authorityScope"]
  readonly authorizationClaimed: boolean
  readonly oneSemanticProductionSlotClaimed: boolean
  readonly predecessorReplayReceiptSha256s: ReadonlyArray<string>
  readonly predecessorReplayCarrierSha256s: ReadonlyArray<string>
  readonly carrierRawSha256: string
  readonly carrierByteLength: number
  readonly members: ReadonlyArray<InternalPreparedMember>
  readonly preparationReceiptSha256: string
}

interface ProductionPreparationSlot {
  readonly identityKey: string
  readonly authority: S2SCurrentRunStageAuthority
  readonly fingerprint: string
  readonly capability: S2SPreparedStageCarrierCapability
}

const PRODUCTION_CAPABILITIES = new WeakMap<
  object,
  { readonly authority: S2SCurrentRunStageAuthority; readonly snapshot: InternalPreparedSnapshot }
>()
const TEST_ONLY_CAPABILITIES = new WeakMap<object, InternalPreparedSnapshot>()
const TEST_ONLY_BY_SEED = new WeakMap<
  object,
  { readonly fingerprint: string; readonly capability: S2SPreparedStageCarrierCapability }
>()
let PRODUCTION_IDENTITY_SLOT: ProductionPreparationSlot | undefined

const preparedError = (
  reason: S2SPreparedStageCarrierError["reason"],
  stage: S2SConfirmatoryJobStage | null,
  detail: string
): S2SPreparedStageCarrierError =>
  new S2SPreparedStageCarrierError({ reason, stage, detail })

const failPrepared = (
  reason: S2SPreparedStageCarrierError["reason"],
  stage: S2SConfirmatoryJobStage | null,
  detail: string
): Either.Either<never, S2SPreparedStageCarrierError> =>
  Either.left(preparedError(reason, stage, detail))

const exactPlainRecord = (
  input: unknown,
  expectedNames: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      Array.isArray(input) ||
      nodeTypes.isProxy(input) ||
      Object.getPrototypeOf(input) !== Object.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0
    ) {
      return null
    }
    const names = Object.getOwnPropertyNames(input).sort()
    const expected = [...expectedNames].sort()
    if (
      names.length !== expected.length ||
      names.some((name, index) => name !== expected[index])
    ) {
      return null
    }
    const snapshot: Record<string, unknown> = {}
    for (const name of names) {
      const descriptor = Object.getOwnPropertyDescriptor(input, name)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor)
      ) {
        return null
      }
      snapshot[name] = descriptor.value
    }
    return Object.freeze(snapshot)
  } catch {
    return null
  }
}

const snapshotDenseArray = (
  input: unknown,
  expectedLength: number
): ReadonlyArray<unknown> | null => {
  try {
    if (
      !Array.isArray(input) ||
      nodeTypes.isProxy(input) ||
      input.length !== expectedLength ||
      Object.getPrototypeOf(input) !== Array.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0
    ) {
      return null
    }
    const expectedNames = [
      ...Array.from({ length: expectedLength }, (_, index) => String(index)),
      "length"
    ].sort()
    const names = Object.getOwnPropertyNames(input).sort()
    if (
      names.length !== expectedNames.length ||
      names.some((name, index) => name !== expectedNames[index])
    ) {
      return null
    }
    const values: Array<unknown> = []
    for (let index = 0; index < expectedLength; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor)
      ) {
        return null
      }
      values.push(descriptor.value)
    }
    return Object.freeze(values)
  } catch {
    return null
  }
}

const isPassiveDataGraph = (
  input: unknown,
  ancestors: ReadonlySet<object> = new Set()
): boolean => {
  try {
    if (
      input === null ||
      typeof input === "string" ||
      typeof input === "boolean" ||
      (typeof input === "number" && Number.isSafeInteger(input))
    ) {
      return true
    }
    if (typeof input !== "object" || nodeTypes.isProxy(input)) return false
    if (ancestors.has(input)) return false
    const next = new Set(ancestors)
    next.add(input)
    if (Array.isArray(input)) {
      if (
        Object.getPrototypeOf(input) !== Array.prototype ||
        Object.getOwnPropertySymbols(input).length !== 0
      ) {
        return false
      }
      const expected = new Set<string>(["length"])
      for (let index = 0; index < input.length; index += 1) {
        expected.add(String(index))
      }
      const names = Object.getOwnPropertyNames(input)
      if (
        names.length !== expected.size ||
        names.some((name) => !expected.has(name))
      ) {
        return false
      }
      for (let index = 0; index < input.length; index += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
        if (
          descriptor === undefined ||
          !descriptor.enumerable ||
          !("value" in descriptor) ||
          !isPassiveDataGraph(descriptor.value, next)
        ) {
          return false
        }
      }
      return true
    }
    if (
      Object.getPrototypeOf(input) !== Object.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0
    ) {
      return false
    }
    for (const name of Object.getOwnPropertyNames(input)) {
      const descriptor = Object.getOwnPropertyDescriptor(input, name)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor) ||
        !isPassiveDataGraph(descriptor.value, next)
      ) {
        return false
      }
    }
    return true
  } catch {
    return false
  }
}

const snapshotPlainBytes = (input: unknown): Uint8Array | null => {
  try {
    if (
      !(input instanceof Uint8Array) ||
      nodeTypes.isProxy(input) ||
      Object.getPrototypeOf(input) !== Uint8Array.prototype ||
      !(input.buffer instanceof ArrayBuffer) ||
      input.byteOffset !== 0 ||
      input.byteLength !== input.buffer.byteLength
    ) {
      return null
    }
    return Uint8Array.from(input)
  } catch {
    return null
  }
}

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameNumbers = (
  left: ReadonlyArray<number>,
  right: ReadonlyArray<number>
): boolean =>
  left.length === right.length &&
  left.every((value, index) => value === right[index])

const identityFromCurrentRun = (
  evidence: S2SCurrentRunStageEvidence
): PreparedIdentity =>
  Object.freeze({
    stage: evidence.stage,
    sourceCommitA: evidence.sourceCommitA,
    currentRunEvidenceReceiptSha256: evidence.receiptSha256,
    workflowRunId: evidence.workflowRunId,
    workflowRunAttempt: 1 as const,
    registrationCommitB: evidence.registrationCommitB,
    workflowApiPath: evidence.workflowApiPath,
    workflowRunCreatedAt: evidence.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds:
      evidence.workflowRunCreatedAtUnixSeconds,
    currentJobDatabaseId: evidence.currentJobDatabaseId,
    predecessorJobDatabaseIds: Object.freeze([
      ...evidence.predecessorJobDatabaseIds
    ])
  })

const snapshotTestSeed = (
  input: unknown
): Either.Either<PreparedIdentity, S2SPreparedStageCarrierError> => {
  const record = exactPlainRecord(input, [
    "classification",
    "currentJobDatabaseId",
    "currentRunEvidenceReceiptSha256",
    "predecessorJobDatabaseIds",
    "registrationCommitB",
    "sourceCommitA",
    "stage",
    "workflowApiPath",
    "workflowRunCreatedAt",
    "workflowRunCreatedAtUnixSeconds",
    "workflowRunId"
  ])
  if (record === null || record["classification"] !== "TEST_ONLY_NON_AUTHORIZING") {
    return failPrepared(
      "INPUT_INVALID",
      null,
      "test preparation requires one exact TEST_ONLY_NON_AUTHORIZING seed"
    )
  }
  const stage = record["stage"]
  const sourceCommitA = record["sourceCommitA"]
  const currentRunEvidenceReceiptSha256 =
    record["currentRunEvidenceReceiptSha256"]
  const workflowRunId = record["workflowRunId"]
  const registrationCommitB = record["registrationCommitB"]
  const workflowApiPath = record["workflowApiPath"]
  const workflowRunCreatedAt = record["workflowRunCreatedAt"]
  const workflowRunCreatedAtUnixSeconds =
    record["workflowRunCreatedAtUnixSeconds"]
  const currentJobDatabaseId = record["currentJobDatabaseId"]
  const predecessorJobDatabaseIds = snapshotDenseArray(
    record["predecessorJobDatabaseIds"],
    stage === "REGISTER" ? 0 : stage === "CONFIRM" ? 1 : 2
  )
  if (
    (stage !== "REGISTER" && stage !== "CONFIRM" && stage !== "ADJUDICATE") ||
    typeof sourceCommitA !== "string" ||
    !GIT_SHA_PATTERN.test(sourceCommitA) ||
    typeof currentRunEvidenceReceiptSha256 !== "string" ||
    !SHA256_PATTERN.test(currentRunEvidenceReceiptSha256) ||
    typeof workflowRunId !== "number" ||
    !Number.isSafeInteger(workflowRunId) ||
    workflowRunId < 1 ||
    typeof registrationCommitB !== "string" ||
    !GIT_SHA_PATTERN.test(registrationCommitB) ||
    typeof workflowApiPath !== "string" ||
    workflowApiPath.length < 1 ||
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
    predecessorJobDatabaseIds.some(
      (value) =>
        typeof value !== "number" ||
        !Number.isSafeInteger(value) ||
        value < 1 ||
        value === currentJobDatabaseId
    ) ||
    new Set(predecessorJobDatabaseIds).size !== predecessorJobDatabaseIds.length
  ) {
    return failPrepared(
      "INPUT_INVALID",
      stage === "REGISTER" || stage === "CONFIRM" || stage === "ADJUDICATE"
        ? stage
        : null,
      "test preparation identity is not canonical"
    )
  }
  return Either.right(
    Object.freeze({
      stage,
      sourceCommitA,
      currentRunEvidenceReceiptSha256,
      workflowRunId,
      workflowRunAttempt: 1 as const,
      registrationCommitB,
      workflowApiPath,
      workflowRunCreatedAt,
      workflowRunCreatedAtUnixSeconds,
      currentJobDatabaseId,
      predecessorJobDatabaseIds: Object.freeze(
        predecessorJobDatabaseIds as ReadonlyArray<number>
      )
    })
  )
}

const replayMatchesCurrentRun = (
  replay: S2SStageArtifactReadReplaySnapshot,
  evidence: S2SCurrentRunStageEvidence,
  operation:
    | "CONFIRM_READ_REGISTRATION"
    | "ADJUDICATE_READ_REGISTRATION"
    | "ADJUDICATE_READ_CANDIDATE_FIRST"
    | "ADJUDICATE_REREAD_CANDIDATE",
  role: "REGISTRATION" | "CANDIDATE"
): boolean => {
  const manifest = replay.manifest
  const identity = manifest.identity
  const permit = replay.permitEvidence
  return (
    manifest.operation === operation &&
    manifest.role === role &&
    manifest.source_commit_a === evidence.sourceCommitA &&
    manifest.current_run_evidence_receipt_sha256 === evidence.receiptSha256 &&
    identity.workflowRunId === evidence.workflowRunId &&
    identity.workflowRunAttempt === evidence.workflowRunAttempt &&
    identity.registrationCommitB === evidence.registrationCommitB &&
    identity.workflowApiPath === evidence.workflowApiPath &&
    identity.workflowRunCreatedAt === evidence.workflowRunCreatedAt &&
    identity.workflowRunCreatedAtUnixSeconds ===
      evidence.workflowRunCreatedAtUnixSeconds &&
    identity.stage === evidence.stage &&
    identity.currentJobDatabaseId === evidence.currentJobDatabaseId &&
    sameNumbers(
      identity.predecessorJobDatabaseIds,
      evidence.predecessorJobDatabaseIds
    ) &&
    permit.authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB" &&
    permit.authorizationClaimed === true &&
    permit.operation === operation &&
    permit.identity.workflowRunId === evidence.workflowRunId &&
    permit.identity.registrationCommitB === evidence.registrationCommitB &&
    permit.identity.stage === evidence.stage &&
    permit.identity.currentJobDatabaseId === evidence.currentJobDatabaseId &&
    sameNumbers(
      permit.identity.predecessorJobDatabaseIds,
      evidence.predecessorJobDatabaseIds
    )
  )
}

const inspectBoundReplay = (
  input: unknown,
  evidence: S2SCurrentRunStageEvidence,
  operation:
    | "CONFIRM_READ_REGISTRATION"
    | "ADJUDICATE_READ_REGISTRATION"
    | "ADJUDICATE_READ_CANDIDATE_FIRST"
    | "ADJUDICATE_REREAD_CANDIDATE",
  role: "REGISTRATION" | "CANDIDATE"
): Either.Either<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError | S2SPreparedStageCarrierError
> => {
  const inspected = inspectS2SStageArtifactReadReplaySnapshot(input)
  if (Either.isLeft(inspected)) return Either.left(inspected.left)
  return replayMatchesCurrentRun(inspected.right, evidence, operation, role)
    ? Either.right(inspected.right)
    : failPrepared(
        "PREDECESSOR_REPLAY_BINDING_MISMATCH",
        evidence.stage,
        `authentic predecessor replay does not bind ${operation} to the current authority`
      )
}

const readbackFromReplay = (
  replay: S2SStageArtifactReadReplaySnapshot
): S2SCarrierReadback =>
  Object.freeze({
    artifact: structuredClone(replay.manifest.artifact_evidence),
    archiveBytes: replay.readArchiveBytes()
  })

type PreparedPlan =
  | S2SRegistrationCarrierPlan
  | S2SCandidateCarrierPlan
  | S2SAdjudicationCarrierPlan

interface BuiltPreparation {
  readonly plan: PreparedPlan
  readonly predecessorReplayReceiptSha256s: ReadonlyArray<string>
  readonly predecessorReplayCarrierSha256s: ReadonlyArray<string>
}

const eventJobDatabaseIdMatches = (
  event: Readonly<Record<string, unknown>>,
  identity: PreparedIdentity
): boolean => {
  const registrationJobDatabaseId =
    identity.stage === "REGISTER"
      ? identity.currentJobDatabaseId
      : identity.predecessorJobDatabaseIds[0]
  const confirmJobDatabaseId =
    identity.stage === "CONFIRM"
      ? identity.currentJobDatabaseId
      : identity.stage === "ADJUDICATE"
        ? identity.predecessorJobDatabaseIds[1]
        : undefined
  switch (event["_tag"]) {
    case "BeginRegistration":
    case "VerifyRegistration":
      return event["registrationJobId"] === registrationJobDatabaseId
    case "BeginConfirm":
    case "AcceptVerifiedPulse":
    case "BeginNumericConfirm":
    case "RecordCandidateProduced":
    case "VerifyCandidateArtifact":
      return event["confirmJobId"] === confirmJobDatabaseId
    case "BeginAdjudication":
    case "RecordAdjudicationProduced":
      return event["adjudicationJobId"] === identity.currentJobDatabaseId
    default:
      return false
  }
}

const carrierBindsIdentity = (
  plan: PreparedPlan,
  identity: PreparedIdentity
): boolean => {
  try {
    const events = plan.carrier.document.events
    if (
      events.length !== (identity.stage === "REGISTER" ? 1 : identity.stage === "CONFIRM" ? 6 : 9)
    ) {
      return false
    }
    return events.every((event) => {
      const record = event as unknown as Readonly<Record<string, unknown>>
      const binding = record["binding"] as
        | Readonly<Record<string, unknown>>
        | undefined
      return (
        binding !== undefined &&
        binding["sourceCommitA"] === identity.sourceCommitA &&
        binding["registrationCommitB"] === identity.registrationCommitB &&
        binding["workflowRunId"] === identity.workflowRunId &&
        binding["workflowRunAttempt"] === identity.workflowRunAttempt &&
        binding["workflowHeadSha"] === identity.registrationCommitB &&
        record["workflowRunId"] === identity.workflowRunId &&
        eventJobDatabaseIdMatches(record, identity)
      )
    })
  } catch {
    return false
  }
}

const exactEvents = <Events extends ReadonlyArray<unknown>>(
  input: unknown,
  length: number
): Events | null => {
  const snapshot = snapshotDenseArray(input, length)
  return snapshot === null || snapshot.some((event) => !isPassiveDataGraph(event))
    ? null
    : (snapshot as Events)
}

const buildProductionPlan = (
  evidence: S2SCurrentRunStageEvidence,
  input: unknown
): Either.Either<BuiltPreparation, S2SPreparedStageCarrierFailure> => {
  switch (evidence.stage) {
    case "REGISTER": {
      const record = exactPlainRecord(input, ["events"])
      const events = exactEvents<S2SRegistrationStageEvents>(record?.["events"], 1)
      if (record === null || events === null) {
        return failPrepared(
          "INPUT_INVALID",
          evidence.stage,
          "REGISTER preparation requires exactly its one-event tuple"
        )
      }
      const plan = prepareS2SRegistrationCarrier(events)
      return Either.isLeft(plan)
        ? Either.left(plan.left)
        : Either.right(
            Object.freeze({
              plan: plan.right,
              predecessorReplayReceiptSha256s: Object.freeze([]),
              predecessorReplayCarrierSha256s: Object.freeze([])
            })
          )
    }
    case "CONFIRM": {
      const record = exactPlainRecord(input, [
        "events",
        "numericCandidateBytes",
        "registrationReplay"
      ])
      const events = exactEvents<S2SCandidateStageEvents>(record?.["events"], 5)
      const numericCandidateBytes = snapshotPlainBytes(
        record?.["numericCandidateBytes"]
      )
      if (record === null || events === null || numericCandidateBytes === null) {
        return failPrepared(
          "INPUT_INVALID",
          evidence.stage,
          "CONFIRM preparation input is not an exact defensive snapshot"
        )
      }
      const registration = inspectBoundReplay(
        record["registrationReplay"],
        evidence,
        "CONFIRM_READ_REGISTRATION",
        "REGISTRATION"
      )
      if (Either.isLeft(registration)) return Either.left(registration.left)
      const plan = prepareS2SCandidateCarrier({
        registrationReadback: readbackFromReplay(registration.right),
        numericCandidateBytes,
        events
      })
      return Either.isLeft(plan)
        ? Either.left(plan.left)
        : Either.right(
            Object.freeze({
              plan: plan.right,
              predecessorReplayReceiptSha256s: Object.freeze([
                registration.right.manifest.replay_receipt_sha256
              ]),
              predecessorReplayCarrierSha256s: Object.freeze([
                registration.right.carrierRawSha256
              ])
            })
          )
    }
    case "ADJUDICATE": {
      const record = exactPlainRecord(input, [
        "candidateFirstReplay",
        "candidateRereadReplay",
        "events",
        "numericAdjudicationBytes",
        "registrationReplay"
      ])
      const events = exactEvents<S2SAdjudicationStageEvents>(record?.["events"], 3)
      const numericAdjudicationBytes = snapshotPlainBytes(
        record?.["numericAdjudicationBytes"]
      )
      if (record === null || events === null || numericAdjudicationBytes === null) {
        return failPrepared(
          "INPUT_INVALID",
          evidence.stage,
          "ADJUDICATE preparation input is not an exact defensive snapshot"
        )
      }
      const registration = inspectBoundReplay(
        record["registrationReplay"],
        evidence,
        "ADJUDICATE_READ_REGISTRATION",
        "REGISTRATION"
      )
      if (Either.isLeft(registration)) return Either.left(registration.left)
      const first = inspectBoundReplay(
        record["candidateFirstReplay"],
        evidence,
        "ADJUDICATE_READ_CANDIDATE_FIRST",
        "CANDIDATE"
      )
      if (Either.isLeft(first)) return Either.left(first.left)
      const reread = inspectBoundReplay(
        record["candidateRereadReplay"],
        evidence,
        "ADJUDICATE_REREAD_CANDIDATE",
        "CANDIDATE"
      )
      if (Either.isLeft(reread)) return Either.left(reread.left)
      const pair = validateS2SCandidateReadReplayPair(first.right, reread.right)
      if (Either.isLeft(pair)) return Either.left(pair.left)
      const plan = prepareS2SAdjudicationCarrier({
        registrationReadback: readbackFromReplay(registration.right),
        candidateReadback: readbackFromReplay(pair.right[1]),
        numericAdjudicationBytes,
        events
      })
      return Either.isLeft(plan)
        ? Either.left(plan.left)
        : Either.right(
            Object.freeze({
              plan: plan.right,
              predecessorReplayReceiptSha256s: Object.freeze([
                registration.right.manifest.replay_receipt_sha256,
                pair.right[0].manifest.replay_receipt_sha256,
                pair.right[1].manifest.replay_receipt_sha256
              ]),
              predecessorReplayCarrierSha256s: Object.freeze([
                registration.right.carrierRawSha256,
                pair.right[0].carrierRawSha256,
                pair.right[1].carrierRawSha256
              ])
            })
          )
    }
  }
}

const snapshotArtifact = (input: unknown): S2SArtifactEvidence | null => {
  try {
    const decoded = Schema.decodeUnknownEither(S2SArtifactEvidenceSchema, {
      onExcessProperty: "error"
    })(input)
    return Either.isLeft(decoded)
      ? null
      : Object.freeze(structuredClone(decoded.right))
  } catch {
    return null
  }
}

const snapshotTestReadback = (input: unknown): S2SCarrierReadback | null => {
  const record = exactPlainRecord(input, ["archiveBytes", "artifact"])
  if (record === null) return null
  const artifact = snapshotArtifact(record["artifact"])
  const archiveBytes = snapshotPlainBytes(record["archiveBytes"])
  return artifact === null || archiveBytes === null
    ? null
    : Object.freeze({ artifact, archiveBytes })
}

const buildTestPlan = (
  identity: PreparedIdentity,
  input: unknown
): Either.Either<
  BuiltPreparation,
  S2SJobSequenceFailure | S2SPreparedStageCarrierError
> => {
  switch (identity.stage) {
    case "REGISTER": {
      const record = exactPlainRecord(input, ["events"])
      const events = exactEvents<S2SRegistrationStageEvents>(record?.["events"], 1)
      if (record === null || events === null) {
        return failPrepared("INPUT_INVALID", identity.stage, "invalid REGISTER test input")
      }
      const plan = prepareS2SRegistrationCarrier(events)
      return Either.isLeft(plan)
        ? Either.left(plan.left)
        : Either.right(
            Object.freeze({
              plan: plan.right,
              predecessorReplayReceiptSha256s: Object.freeze([]),
              predecessorReplayCarrierSha256s: Object.freeze([])
            })
          )
    }
    case "CONFIRM": {
      const record = exactPlainRecord(input, [
        "events",
        "numericCandidateBytes",
        "registrationReadback"
      ])
      const events = exactEvents<S2SCandidateStageEvents>(record?.["events"], 5)
      const numericCandidateBytes = snapshotPlainBytes(
        record?.["numericCandidateBytes"]
      )
      const registrationReadback = snapshotTestReadback(
        record?.["registrationReadback"]
      )
      if (
        record === null ||
        events === null ||
        numericCandidateBytes === null ||
        registrationReadback === null
      ) {
        return failPrepared("INPUT_INVALID", identity.stage, "invalid CONFIRM test input")
      }
      const plan = prepareS2SCandidateCarrier({
        registrationReadback,
        numericCandidateBytes,
        events
      })
      return Either.isLeft(plan)
        ? Either.left(plan.left)
        : Either.right(
            Object.freeze({
              plan: plan.right,
              predecessorReplayReceiptSha256s: Object.freeze([]),
              predecessorReplayCarrierSha256s: Object.freeze([])
            })
          )
    }
    case "ADJUDICATE": {
      const record = exactPlainRecord(input, [
        "candidateReadback",
        "events",
        "numericAdjudicationBytes",
        "registrationReadback"
      ])
      const events = exactEvents<S2SAdjudicationStageEvents>(record?.["events"], 3)
      const numericAdjudicationBytes = snapshotPlainBytes(
        record?.["numericAdjudicationBytes"]
      )
      const registrationReadback = snapshotTestReadback(
        record?.["registrationReadback"]
      )
      const candidateReadback = snapshotTestReadback(record?.["candidateReadback"])
      if (
        record === null ||
        events === null ||
        numericAdjudicationBytes === null ||
        registrationReadback === null ||
        candidateReadback === null
      ) {
        return failPrepared(
          "INPUT_INVALID",
          identity.stage,
          "invalid ADJUDICATE test input"
        )
      }
      const plan = prepareS2SAdjudicationCarrier({
        registrationReadback,
        candidateReadback,
        numericAdjudicationBytes,
        events
      })
      return Either.isLeft(plan)
        ? Either.left(plan.left)
        : Either.right(
            Object.freeze({
              plan: plan.right,
              predecessorReplayReceiptSha256s: Object.freeze([]),
              predecessorReplayCarrierSha256s: Object.freeze([])
            })
          )
    }
  }
}

const snapshotPlan = (
  identity: PreparedIdentity,
  built: BuiltPreparation,
  authorityScope: InternalPreparedSnapshot["authorityScope"]
): Either.Either<InternalPreparedSnapshot, S2SPreparedStageCarrierError> => {
  const spec = S2S_STAGE_ARTIFACT_SPECS[identity.stage]
  if (!carrierBindsIdentity(built.plan, identity)) {
    return failPrepared(
      "PREPARED_MEMBER_MISMATCH",
      identity.stage,
      "stage builder carrier does not bind the exact current-run identity and job roster"
    )
  }
  const carrierBytes = built.plan.carrier.canonicalBytes
  const expected = spec.expectedMembers
  if (built.plan.members.length !== expected.length) {
    return failPrepared(
      "PREPARED_MEMBER_MISMATCH",
      identity.stage,
      "stage builder did not return the exact stage-derived member count"
    )
  }
  const members: Array<InternalPreparedMember> = []
  for (let index = 0; index < expected.length; index += 1) {
    const expectedMember = expected[index]
    const member = built.plan.members[index] as
      | S2SUploadMember<string>
      | undefined
    if (expectedMember === undefined || member === undefined) {
      return failPrepared(
        "PREPARED_MEMBER_MISMATCH",
        identity.stage,
        "stage-derived member disappeared during preparation"
      )
    }
    const bytes = snapshotPlainBytes(member.readBytes())
    if (
      bytes === null ||
      member.name !== expectedMember.name ||
      member.byteLength !== bytes.byteLength ||
      member.rawBytesSha256 !== rawS2SFileSha256(bytes) ||
      bytes.byteLength < 1 ||
      bytes.byteLength > expectedMember.maximumBytes
    ) {
      return failPrepared(
        "PREPARED_MEMBER_MISMATCH",
        identity.stage,
        `stage-derived member ${expectedMember.name} is not self-consistent`
      )
    }
    if (
      member.name !== "control_receipt.json" &&
      member.name !== "numeric_candidate.json" &&
      member.name !== "numeric_adjudication.json"
    ) {
      return failPrepared(
        "PREPARED_MEMBER_MISMATCH",
        identity.stage,
        "stage builder returned an unknown upload member"
      )
    }
    members.push(
      Object.freeze({
        name: member.name,
        byteLength: bytes.byteLength,
        rawBytesSha256: member.rawBytesSha256,
        bytes
      })
    )
  }
  if (members[0] === undefined || !sameBytes(members[0].bytes, carrierBytes)) {
    return failPrepared(
      "PREPARED_MEMBER_MISMATCH",
      identity.stage,
      "control_receipt.json is not the exact prepared carrier"
    )
  }
  const carrierRawSha256 = rawS2SFileSha256(carrierBytes)
  const core = Object.freeze({
    schemaVersion: S2S_PREPARED_STAGE_CARRIER_SCHEMA_VERSION,
    authorityScope,
    authorizationClaimed:
      authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
    oneSemanticProductionSlotClaimed:
      authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
    stage: identity.stage,
    role: spec.role,
    jobId: spec.jobId,
    jobName: spec.jobName,
    artifactName: spec.artifactName,
    archiveLogicalName: spec.archiveLogicalName,
    archiveProfileRole: spec.archiveProfileRole,
    carrierSchemaVersion: spec.carrierSchemaVersion,
    maximumArchiveBytes: spec.maximumArchiveBytes,
    maximumExpandedBytes: spec.maximumExpandedBytes,
    sourceCommitA: identity.sourceCommitA,
    currentRunEvidenceReceiptSha256:
      identity.currentRunEvidenceReceiptSha256,
    workflowRunId: identity.workflowRunId,
    workflowRunAttempt: identity.workflowRunAttempt,
    registrationCommitB: identity.registrationCommitB,
    workflowApiPath: identity.workflowApiPath,
    workflowRunCreatedAt: identity.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds:
      identity.workflowRunCreatedAtUnixSeconds,
    currentJobDatabaseId: identity.currentJobDatabaseId,
    predecessorJobDatabaseIds: identity.predecessorJobDatabaseIds,
    predecessorReplayReceiptSha256s:
      built.predecessorReplayReceiptSha256s,
    predecessorReplayCarrierSha256s:
      built.predecessorReplayCarrierSha256s,
    carrierRawSha256,
    carrierByteLength: carrierBytes.byteLength,
    members: members.map(({ name, byteLength, rawBytesSha256 }) => ({
      name,
      byteLength,
      rawBytesSha256
    }))
  })
  const hashed = canonicalS2SControlSha256(core)
  if (Either.isLeft(hashed)) {
    return failPrepared(
      "EVIDENCE_NOT_CANONICAL",
      identity.stage,
      "prepared carrier evidence cannot be canonically hashed"
    )
  }
  return Either.right(
    Object.freeze({
      ...identity,
      authorityScope,
      authorizationClaimed:
        authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
      oneSemanticProductionSlotClaimed:
        authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
      predecessorReplayReceiptSha256s: Object.freeze([
        ...built.predecessorReplayReceiptSha256s
      ]),
      predecessorReplayCarrierSha256s: Object.freeze([
        ...built.predecessorReplayCarrierSha256s
      ]),
      carrierRawSha256,
      carrierByteLength: carrierBytes.byteLength,
      members: Object.freeze(members),
      preparationReceiptSha256: hashed.right
    })
  )
}

const makeCapability = (): S2SPreparedStageCarrierCapability =>
  Object.freeze({ [S2S_PREPARED_STAGE_CARRIER_BRAND]: true as const })

const publicSnapshot = (
  internal: InternalPreparedSnapshot
): S2SPreparedStageCarrierSnapshot => {
  const spec = S2S_STAGE_ARTIFACT_SPECS[internal.stage]
  return Object.freeze({
    schemaVersion: S2S_PREPARED_STAGE_CARRIER_SCHEMA_VERSION,
    authorityScope: internal.authorityScope,
    authorizationClaimed: internal.authorizationClaimed,
    oneSemanticProductionSlotClaimed:
      internal.oneSemanticProductionSlotClaimed,
    stage: internal.stage,
    role: spec.role,
    jobId: spec.jobId,
    jobName: spec.jobName,
    artifactName: spec.artifactName,
    archiveLogicalName: spec.archiveLogicalName,
    archiveProfileRole: spec.archiveProfileRole,
    carrierSchemaVersion: spec.carrierSchemaVersion,
    maximumArchiveBytes: spec.maximumArchiveBytes,
    maximumExpandedBytes: spec.maximumExpandedBytes,
    sourceCommitA: internal.sourceCommitA,
    currentRunEvidenceReceiptSha256:
      internal.currentRunEvidenceReceiptSha256,
    workflowRunId: internal.workflowRunId,
    workflowRunAttempt: internal.workflowRunAttempt,
    registrationCommitB: internal.registrationCommitB,
    workflowApiPath: internal.workflowApiPath,
    workflowRunCreatedAt: internal.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds:
      internal.workflowRunCreatedAtUnixSeconds,
    currentJobDatabaseId: internal.currentJobDatabaseId,
    predecessorJobDatabaseIds: Object.freeze([
      ...internal.predecessorJobDatabaseIds
    ]),
    predecessorReplayReceiptSha256s: Object.freeze([
      ...internal.predecessorReplayReceiptSha256s
    ]),
    predecessorReplayCarrierSha256s: Object.freeze([
      ...internal.predecessorReplayCarrierSha256s
    ]),
    carrierRawSha256: internal.carrierRawSha256,
    carrierByteLength: internal.carrierByteLength,
    members: Object.freeze(
      internal.members.map((member) =>
        Object.freeze({
          name: member.name,
          byteLength: member.byteLength,
          rawBytesSha256: member.rawBytesSha256,
          readBytes: (): Uint8Array => Uint8Array.from(member.bytes)
        })
      )
    ),
    preparationReceiptSha256: internal.preparationReceiptSha256
  })
}

const identityFingerprint = (
  identity: PreparedIdentity
): Either.Either<string, S2SPreparedStageCarrierError> => {
  const hashed = canonicalS2SControlSha256(identity)
  return Either.isLeft(hashed)
    ? failPrepared(
        "EVIDENCE_NOT_CANONICAL",
        identity.stage,
        "current-job preparation identity is not canonical"
      )
    : Either.right(hashed.right)
}

/**
 * Production preparation is gate-closed unless the exact current-run bearer
 * and every required predecessor replay are authentic in this module graph.
 */
export const prepareS2SCurrentStageCarrier = (
  authority: unknown,
  input: unknown
): Either.Either<
  S2SPreparedStageCarrierCapability,
  S2SPreparedStageCarrierFailure
> => {
  try {
    const inspected = inspectS2SCurrentRunStageAuthority(authority)
    if (Either.isLeft(inspected)) return Either.left(inspected.left)
    if (authority === null || typeof authority !== "object") {
      return failPrepared("INPUT_INVALID", null, "authority is not an object")
    }
    const genuineAuthority = authority as S2SCurrentRunStageAuthority
    const identity = identityFromCurrentRun(inspected.right)
    const identityKey = identityFingerprint(identity)
    if (Either.isLeft(identityKey)) return Either.left(identityKey.left)
    if (
      PRODUCTION_IDENTITY_SLOT !== undefined &&
      PRODUCTION_IDENTITY_SLOT.authority !== genuineAuthority
    ) {
      return failPrepared(
        "PRODUCTION_IDENTITY_SLOT_OCCUPIED",
        identity.stage,
        PRODUCTION_IDENTITY_SLOT.identityKey === identityKey.right
          ? "the current-job identity is already bound to another genuine bearer"
          : "the single-module production preparation slot is already occupied"
      )
    }
    const built = buildProductionPlan(inspected.right, input)
    if (Either.isLeft(built)) return Either.left(built.left)
    const snapshot = snapshotPlan(
      identity,
      built.right,
      "TRUSTED_SINGLE_MODULE_CURRENT_JOB"
    )
    if (Either.isLeft(snapshot)) return Either.left(snapshot.left)
    if (PRODUCTION_IDENTITY_SLOT !== undefined) {
      return PRODUCTION_IDENTITY_SLOT.fingerprint ===
        snapshot.right.preparationReceiptSha256
        ? Either.right(PRODUCTION_IDENTITY_SLOT.capability)
        : failPrepared(
            "PREPARATION_CONFLICT",
            identity.stage,
            "this genuine authority already prepared different carrier bytes"
          )
    }
    const capability = makeCapability()
    PRODUCTION_CAPABILITIES.set(capability, {
      authority: genuineAuthority,
      snapshot: snapshot.right
    })
    PRODUCTION_IDENTITY_SLOT = Object.freeze({
      identityKey: identityKey.right,
      authority: genuineAuthority,
      fingerprint: snapshot.right.preparationReceiptSha256,
      capability
    })
    return Either.right(capability)
  } catch {
    return failPrepared(
      "INPUT_INVALID",
      null,
      "production carrier preparation failed closed"
    )
  }
}

/** Root-private production inspector; structural or test-only copies fail. */
export const inspectS2SPreparedStageCarrierCapability = (
  authority: unknown,
  capability: unknown
): Either.Either<
  S2SPreparedStageCarrierSnapshot,
  S2SCurrentRunInputError | S2SPreparedStageCarrierError
> => {
  try {
    const inspected = inspectS2SCurrentRunStageAuthority(authority)
    if (Either.isLeft(inspected)) return Either.left(inspected.left)
    if (capability === null || typeof capability !== "object") {
      return failPrepared(
        "INVALID_CAPABILITY",
        inspected.right.stage,
        "prepared carrier capability is not an issued object"
      )
    }
    const entry = PRODUCTION_CAPABILITIES.get(capability)
    if (entry === undefined) {
      return failPrepared(
        "INVALID_CAPABILITY",
        inspected.right.stage,
        "prepared carrier capability was not issued by the production registry"
      )
    }
    if (entry.authority !== authority) {
      return failPrepared(
        "AUTHORITY_CAPABILITY_MISMATCH",
        inspected.right.stage,
        "prepared carrier capability belongs to a different genuine authority"
      )
    }
    return Either.right(publicSnapshot(entry.snapshot))
  } catch {
    return failPrepared(
      "INVALID_CAPABILITY",
      null,
      "prepared carrier capability inspection failed closed"
    )
  }
}

/**
 * @internal TEST-ONLY, NON-AUTHORIZING. This never reads or writes either
 * production registry and therefore cannot make the production gate true.
 */
export const makeS2SPreparedStageCarrierTestCapability = (
  seed: unknown,
  input: unknown
): Either.Either<
  S2SPreparedStageCarrierCapability,
  S2SJobSequenceFailure | S2SPreparedStageCarrierError
> => {
  try {
    const identity = snapshotTestSeed(seed)
    if (Either.isLeft(identity)) return Either.left(identity.left)
    const built = buildTestPlan(identity.right, input)
    if (Either.isLeft(built)) return Either.left(built.left)
    const snapshot = snapshotPlan(
      identity.right,
      built.right,
      "TEST_ONLY_NON_AUTHORIZING"
    )
    if (Either.isLeft(snapshot)) return Either.left(snapshot.left)
    if (seed === null || typeof seed !== "object") {
      return failPrepared("INPUT_INVALID", identity.right.stage, "seed is not an object")
    }
    const existing = TEST_ONLY_BY_SEED.get(seed)
    if (existing !== undefined) {
      return existing.fingerprint === snapshot.right.preparationReceiptSha256
        ? Either.right(existing.capability)
        : failPrepared(
            "PREPARATION_CONFLICT",
            identity.right.stage,
            "this test seed already prepared different carrier bytes"
          )
    }
    const capability = makeCapability()
    TEST_ONLY_CAPABILITIES.set(capability, snapshot.right)
    TEST_ONLY_BY_SEED.set(
      seed,
      Object.freeze({
        fingerprint: snapshot.right.preparationReceiptSha256,
        capability
      })
    )
    return Either.right(capability)
  } catch {
    return failPrepared(
      "INPUT_INVALID",
      null,
      "test-only carrier preparation failed closed"
    )
  }
}

/** @internal TEST-ONLY, NON-AUTHORIZING mechanics probe. */
export const inspectS2SPreparedStageCarrierTestCapability = (
  capability: unknown
): Either.Either<
  S2SPreparedStageCarrierSnapshot,
  S2SPreparedStageCarrierError
> => {
  try {
    if (capability === null || typeof capability !== "object") {
      return failPrepared(
        "INVALID_CAPABILITY",
        null,
        "test prepared carrier capability is not an issued object"
      )
    }
    const snapshot = TEST_ONLY_CAPABILITIES.get(capability)
    return snapshot === undefined
      ? failPrepared(
          "INVALID_CAPABILITY",
          null,
          "capability was not issued by the disjoint test-only registry"
        )
      : Either.right(publicSnapshot(snapshot))
  } catch {
    return failPrepared(
      "INVALID_CAPABILITY",
      null,
      "test prepared carrier capability inspection failed closed"
    )
  }
}
