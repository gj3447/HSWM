import { types as nodeTypes } from "node:util"

import { Data, Effect, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2SArtifactEvidenceSchema,
  S2S_CANDIDATE_ARTIFACT_NAME,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_POLICY,
  S2S_REGISTRATION_ARTIFACT_NAME,
  S2SGitCommitShaSchema,
  S2SSha256Schema,
  type S2SSha256
} from "./s2s-confirmatory.js"
import {
  validateS2SEvidenceClaimForEnvelope,
  type S2SEvidenceEnvelopeSnapshot
} from "./s2s-evidence-envelope.js"
import { validateS2SSuccessStageEvidenceEnvelope } from "./s2s-evidence-profile.js"
import {
  isAuthenticS2SDurableEvidenceRecovery,
  type S2SDurableEvidenceRecovery,
  type S2SDurableEvidenceStage
} from "./s2s-evidence-file.js"
import { parseS2SJsonBytes } from "./s2s-json.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_JSON_MAX_BYTES,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  validateS2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownloadReceipt,
  type S2SGitHubObservationError,
  type S2SGitHubArtifactProjection,
  type S2SGitHubArtifactsProjection,
  type S2SGitHubObservation,
  type S2SGitHubProjection,
  type S2SGitHubWorkflowJobProjection,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection
} from "./s2s-live-github.js"
import {
  S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION,
  isAuthenticS2SValidatedStageArtifactRead,
  type S2SValidatedStageArtifactRead
} from "./s2s-live-artifact.js"
import type { S2SCurrentRunStageEvidence } from "./s2s-run-authority.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "./s2s-stage-artifact-spec.js"
import {
  validateS2SStageArtifactPermitEvidence,
  type S2SStageArtifactPermitEvidence,
  type S2SStageArtifactPermitIdentity,
  type S2SStageArtifactLedgerPhase
} from "./s2s-stage-artifact-permits.js"
import {
  S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES,
  S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME,
  S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES,
  S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES,
  S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME,
  S2S_STAGE_ARTIFACT_READ_REPLAY_REPRESENTATION,
  S2S_STAGE_ARTIFACT_READ_REPLAY_SCHEMA_VERSION,
  S2S_STAGE_ARTIFACT_READ_REPLAY_ZIP_FRAMING_BYTES,
  s2sStageArtifactReadReplayObservationCount,
  s2sStageArtifactReadReplayRawBodyMaximumBytes
} from "./s2s-stage-artifact-read-replay-contract.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_EVENT,
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_NAME,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  s2sArtifactReadContract
} from "./s2s-workflow-contract.js"
import {
  buildS2SStoredZip,
  validateS2SArtifactZip,
  type S2SValidatedArtifactZip
} from "./s2s-zip.js"

const KIBIBYTE = 1_024
const MEBIBYTE = 1_048_576
const GITHUB_REQUEST_ID_PATTERN = /^[\u0021-\u007e]{1,256}$/
const HTTP_ETAG_PATTERN = /^(?:W\/)?"[\u0021\u0023-\u007e]{0,508}"$/
const RFC3339_UTC_SECONDS_PATTERN =
  /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/

const PositiveSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER)
)
const NonNegativeSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER)
)
const RequestIdSchema = Schema.String.pipe(
  Schema.pattern(GITHUB_REQUEST_ID_PATTERN)
)
const EtagSchema = Schema.String.pipe(Schema.pattern(HTTP_ETAG_PATTERN))
const TimestampSchema = Schema.String.pipe(
  Schema.pattern(RFC3339_UTC_SECONDS_PATTERN)
)
const StageSchema = Schema.Literal("REGISTER", "CONFIRM", "ADJUDICATE")
const ConsumerStageSchema = Schema.Literal("CONFIRM", "ADJUDICATE")
const ArtifactRoleSchema = Schema.Literal("REGISTRATION", "CANDIDATE")
const OperationSchema = Schema.Literal(
  "CONFIRM_READ_REGISTRATION",
  "ADJUDICATE_READ_REGISTRATION",
  "ADJUDICATE_READ_CANDIDATE_FIRST",
  "ADJUDICATE_REREAD_CANDIDATE"
)
const ObservationKindSchema = Schema.Literal(
  "WORKFLOW_RUN",
  "WORKFLOW_ATTEMPT_JOBS",
  "RUN_ARTIFACTS",
  "ARTIFACT"
)
const ObservationPhaseSchema = Schema.Literal(
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
  "READBACK_RUN_END"
)

const CompactObservationSchema = Schema.Struct({
  ordinal: Schema.Number.pipe(Schema.int(), Schema.between(1, 11)),
  phase: ObservationPhaseSchema,
  kind: ObservationKindSchema,
  offset: NonNegativeSafeIntegerSchema.pipe(
    Schema.between(0, S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES)
  ),
  byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, S2S_GITHUB_JSON_MAX_BYTES)
  ),
  raw_body_sha256: S2SSha256Schema,
  observed_at_unix_seconds: NonNegativeSafeIntegerSchema,
  github_request_id: RequestIdSchema,
  response_etag: EtagSchema,
  projection_sha256: S2SSha256Schema,
  receipt_sha256: S2SSha256Schema
})

const PermitIdentitySchema = Schema.Struct({
  workflowRunId: PositiveSafeIntegerSchema,
  workflowRunAttempt: Schema.Literal(1),
  registrationCommitB: S2SGitCommitShaSchema,
  workflowApiPath: Schema.Literal(
    S2S_CONFIRMATORY_WORKFLOW_PATH,
    `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`
  ),
  workflowRunCreatedAt: TimestampSchema,
  workflowRunCreatedAtUnixSeconds: NonNegativeSafeIntegerSchema,
  stage: ConsumerStageSchema,
  currentJobDatabaseId: PositiveSafeIntegerSchema,
  predecessorJobDatabaseIds: Schema.Array(PositiveSafeIntegerSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(2)
  )
})

const SourceArchiveReferenceSchema = Schema.Struct({
  source_stage: Schema.Literal("REGISTER", "CONFIRM"),
  source_manifest_raw_sha256: S2SSha256Schema,
  source_claim_raw_sha256: S2SSha256Schema,
  logical_name: Schema.Literal(
    "upload/registration_archive.zip",
    "upload/candidate_archive.zip"
  ),
  role: Schema.Literal(
    "REGISTRATION_UPLOAD_ARCHIVE",
    "CANDIDATE_UPLOAD_ARCHIVE"
  ),
  schema_version: Schema.Literal(
    "hswm-swm0w-s2s-registration-carrier/v1",
    "hswm-swm0w-s2s-candidate-carrier/v1"
  ),
  media_type: Schema.Literal("application/zip"),
  byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 64 * MEBIBYTE)
  ),
  raw_sha256: S2SSha256Schema
})

const ArchiveMemberProjectionSchema = Schema.Struct({
  name: Schema.Literal(
    "control_receipt.json",
    "numeric_candidate.json"
  ),
  byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 60 * MEBIBYTE)
  ),
  crc32: NonNegativeSafeIntegerSchema.pipe(
    Schema.between(0, 0xffff_ffff)
  ),
  raw_bytes_sha256: S2SSha256Schema
})

const ArchiveProjectionSchema = Schema.Struct({
  archive_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 64 * MEBIBYTE)
  ),
  archive_sha256: S2SSha256Schema,
  expanded_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 64 * MEBIBYTE)
  ),
  largest_member_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 60 * MEBIBYTE)
  ),
  members: Schema.Array(ArchiveMemberProjectionSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(2)
  )
})

const ReplayManifestSchema = Schema.Struct({
  schema_version: Schema.Literal(
    S2S_STAGE_ARTIFACT_READ_REPLAY_SCHEMA_VERSION
  ),
  representation: Schema.Literal(
    S2S_STAGE_ARTIFACT_READ_REPLAY_REPRESENTATION
  ),
  experiment_id: Schema.Literal(S2S_CONFIRMATORY_EXPERIMENT_ID),
  lookup_trace_schema_version: Schema.Literal(
    S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION
  ),
  source_commit_a: S2SGitCommitShaSchema,
  current_run_evidence_receipt_sha256: S2SSha256Schema,
  identity: PermitIdentitySchema,
  operation: OperationSchema,
  role: ArtifactRoleSchema,
  producer_job_id: PositiveSafeIntegerSchema,
  producer_job_name: Schema.Literal("register", "confirm"),
  artifact_id: PositiveSafeIntegerSchema,
  artifact_name: Schema.Literal(
    S2S_REGISTRATION_ARTIFACT_NAME,
    S2S_CANDIDATE_ARTIFACT_NAME
  ),
  artifact_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 64 * MEBIBYTE)
  ),
  artifact_sha256: S2SSha256Schema,
  successful_attempt_ordinal: Schema.Literal(1, 2, 3),
  observation_count: Schema.Literal(7, 9, 11),
  observation_blob_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES)
  ),
  observation_blob_sha256: S2SSha256Schema,
  observations: Schema.Array(CompactObservationSchema).pipe(
    Schema.minItems(7),
    Schema.maxItems(11)
  ),
  download_receipt: Schema.Unknown,
  artifact_evidence: S2SArtifactEvidenceSchema,
  archive_reference: SourceArchiveReferenceSchema,
  archive_validation: ArchiveProjectionSchema,
  permit_evidence: Schema.Unknown,
  candidate_fingerprint_sha256: Schema.NullOr(S2SSha256Schema),
  replay_receipt_sha256: S2SSha256Schema
})

const CurrentRunObservationSchema = Schema.Struct({
  receiptSha256: S2SSha256Schema,
  githubRequestId: RequestIdSchema,
  observedAtUnixSeconds: NonNegativeSafeIntegerSchema
})

const CurrentRunEvidenceSchema = Schema.Struct({
  schemaVersion: Schema.Literal(
    "hswm-swm0w-s2s-current-run-stage-evidence/v1"
  ),
  authorityScope: Schema.Literal("PROCESS_LOCAL_STAGE_ENTRY"),
  uniquenessClaim: Schema.Literal("ROSTER_OBSERVATION_INSTANT_ONLY"),
  historicalUniquenessClaimed: Schema.Literal(false),
  crossExecutionReplayPreventionClaimed: Schema.Literal(false),
  durableCommitRequiresFreshTerminalObservation: Schema.Literal(true),
  sourceCommitA: S2SGitCommitShaSchema,
  registrationCommitB: S2SGitCommitShaSchema,
  registrationAuthorityReceiptSha256: S2SSha256Schema,
  currentInvocationReceiptSha256: S2SSha256Schema,
  workflowContractSha256: S2SSha256Schema,
  workflowFileSha256: S2SSha256Schema,
  trackedBytesManifestSha256: S2SSha256Schema,
  workflowApiPath: Schema.Literal(
    S2S_CONFIRMATORY_WORKFLOW_PATH,
    `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`
  ),
  workflowRunId: PositiveSafeIntegerSchema,
  workflowRunAttempt: Schema.Literal(1),
  stage: StageSchema,
  currentJobId: Schema.Literal("register", "confirm", "adjudicate"),
  currentJobDatabaseId: PositiveSafeIntegerSchema,
  predecessorJobDatabaseIds: Schema.Array(PositiveSafeIntegerSchema).pipe(
    Schema.maxItems(2)
  ),
  workflowRunCreatedAt: TimestampSchema,
  workflowRunCreatedAtUnixSeconds: NonNegativeSafeIntegerSchema,
  invocationCapturedAtUnixSeconds: NonNegativeSafeIntegerSchema,
  observations: Schema.Struct({
    runStart: CurrentRunObservationSchema,
    jobs: CurrentRunObservationSchema,
    runsForHead: CurrentRunObservationSchema,
    runEnd: CurrentRunObservationSchema
  }),
  receiptSha256: S2SSha256Schema
})

export type S2SStageArtifactReadReplayManifest = Schema.Schema.Type<
  typeof ReplayManifestSchema
>

export interface S2SStageArtifactReadReplaySnapshot {
  readonly manifest: S2SStageArtifactReadReplayManifest
  readonly manifestRawSha256: S2SSha256
  readonly carrierRawSha256: S2SSha256
  readonly carrierByteLength: number
  readonly observations: ReadonlyArray<S2SGitHubObservation>
  readonly archiveValidation: S2SValidatedArtifactZip
  readonly permitEvidence: S2SStageArtifactPermitEvidence
  readonly readCarrierBytes: () => Uint8Array
  readonly readObservationBlob: () => Uint8Array
  readonly readArchiveBytes: () => Uint8Array
}

export class S2SStageArtifactReadReplayError extends Data.TaggedError(
  "S2SStageArtifactReadReplayError"
)<{
  readonly reason:
    | "ARCHIVE_REFERENCE_INVALID"
    | "ARCHIVE_REPLAY_INVALID"
    | "BYTE_BUDGET_EXCEEDED"
    | "CANDIDATE_FINGERPRINT_MISMATCH"
    | "CARRIER_INVALID"
    | "CURRENT_RUN_BINDING_MISMATCH"
    | "INPUT_INVALID"
    | "LEDGER_BINDING_MISMATCH"
    | "MANIFEST_INVALID"
    | "MANIFEST_SELF_HASH_MISMATCH"
    | "OBSERVATION_REPLAY_INVALID"
    | "POLL_TOPOLOGY_INVALID"
    | "READ_IDENTITY_MISMATCH"
  readonly phase: string
  readonly detail: string
}> {}

const replayError = (
  reason: S2SStageArtifactReadReplayError["reason"],
  phase: string,
  detail: string
): S2SStageArtifactReadReplayError =>
  new S2SStageArtifactReadReplayError({ reason, phase, detail })

const suspendEither = <Success, Failure>(
  evaluate: () => Either.Either<Success, Failure>
): Effect.Effect<Success, Failure> =>
  Effect.suspend(() => {
    const result = evaluate()
    return Either.isLeft(result)
      ? Effect.fail(result.left)
      : Effect.succeed(result.right)
  })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameCanonicalData = (left: unknown, right: unknown): boolean => {
  try {
    const leftHash = canonicalS2SControlSha256(left)
    const rightHash = canonicalS2SControlSha256(right)
    return (
      Either.isRight(leftHash) &&
      Either.isRight(rightHash) &&
      leftHash.right === rightHash.right
    )
  } catch {
    return false
  }
}

const exactDataRecord = (
  input: unknown,
  keys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      nodeTypes.isProxy(input)
    ) {
      return null
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) return null
    const ownKeys = Reflect.ownKeys(input)
    if (
      ownKeys.length !== keys.length ||
      ownKeys.some((key) => typeof key !== "string")
    ) {
      return null
    }
    const sorted = ownKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
    const expected = [...keys].sort()
    if (!sorted.every((key, index) => key === expected[index])) return null
    const output: Record<string, unknown> = Object.create(null)
    for (const key of sorted) {
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

const snapshotPlainBytes = (
  input: unknown,
  maximumBytes: number,
  minimumBytes = 1
): Uint8Array | null => {
  try {
    if (
      !(input instanceof Uint8Array) ||
      nodeTypes.isProxy(input) ||
      Object.getPrototypeOf(input) !== Uint8Array.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0 ||
      Object.getOwnPropertyDescriptor(input, "byteLength") !== undefined ||
      Object.getOwnPropertyDescriptor(input, "buffer") !== undefined ||
      input.byteLength < minimumBytes ||
      input.byteLength > maximumBytes ||
      (typeof SharedArrayBuffer !== "undefined" &&
        input.buffer instanceof SharedArrayBuffer)
    ) {
      return null
    }
    return Uint8Array.from(input)
  } catch {
    return null
  }
}

const snapshotDenseArray = (
  input: unknown,
  maximumLength: number,
  minimumLength: number
): ReadonlyArray<unknown> | null => {
  try {
    if (
      !Array.isArray(input) ||
      nodeTypes.isProxy(input) ||
      Object.getPrototypeOf(input) !== Array.prototype
    ) {
      return null
    }
    const length = input.length
    if (
      !Number.isSafeInteger(length) ||
      length < minimumLength ||
      length > maximumLength ||
      Reflect.ownKeys(input).length !== length + 1
    ) {
      return null
    }
    const output: Array<unknown> = []
    for (let index = 0; index < length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      output.push(descriptor.value)
    }
    return Object.freeze(output)
  } catch {
    return null
  }
}

const currentRunFailure = (detail: string) =>
  Either.left(
    replayError(
      "CURRENT_RUN_BINDING_MISMATCH",
      "CURRENT_RUN_EVIDENCE",
      detail
    )
  )

export const validateS2SCurrentRunStageEvidence = (
  input: unknown
): Either.Either<
  S2SCurrentRunStageEvidence,
  S2SStageArtifactReadReplayError
> => {
  try {
    const root = exactDataRecord(input, [
      "schemaVersion",
      "authorityScope",
      "uniquenessClaim",
      "historicalUniquenessClaimed",
      "crossExecutionReplayPreventionClaimed",
      "durableCommitRequiresFreshTerminalObservation",
      "sourceCommitA",
      "registrationCommitB",
      "registrationAuthorityReceiptSha256",
      "currentInvocationReceiptSha256",
      "workflowContractSha256",
      "workflowFileSha256",
      "trackedBytesManifestSha256",
      "workflowApiPath",
      "workflowRunId",
      "workflowRunAttempt",
      "stage",
      "currentJobId",
      "currentJobDatabaseId",
      "predecessorJobDatabaseIds",
      "workflowRunCreatedAt",
      "workflowRunCreatedAtUnixSeconds",
      "invocationCapturedAtUnixSeconds",
      "observations",
      "receiptSha256"
    ])
    const predecessors = snapshotDenseArray(
      root?.["predecessorJobDatabaseIds"],
      2,
      0
    )
    const observations = exactDataRecord(root?.["observations"], [
      "runStart",
      "jobs",
      "runsForHead",
      "runEnd"
    ])
    const observationKeys = [
      "receiptSha256",
      "githubRequestId",
      "observedAtUnixSeconds"
    ] as const
    const runStart = exactDataRecord(observations?.["runStart"], observationKeys)
    const jobs = exactDataRecord(observations?.["jobs"], observationKeys)
    const runsForHead = exactDataRecord(
      observations?.["runsForHead"],
      observationKeys
    )
    const runEnd = exactDataRecord(observations?.["runEnd"], observationKeys)
    if (
      root === null ||
      predecessors === null ||
      observations === null ||
      runStart === null ||
      jobs === null ||
      runsForHead === null ||
      runEnd === null
    ) {
      return currentRunFailure("current-run evidence is not exact canonical data")
    }
    const safeRoot = Object.freeze({
      ...root,
      predecessorJobDatabaseIds: predecessors,
      observations: Object.freeze({ runStart, jobs, runsForHead, runEnd })
    })
    if (Either.isLeft(canonicalS2SControlSha256(safeRoot))) {
      return currentRunFailure("current-run evidence is not exact canonical data")
    }
    const decoded = Schema.decodeUnknownEither(CurrentRunEvidenceSchema, {
      onExcessProperty: "error"
    })(safeRoot)
    if (Either.isLeft(decoded)) {
      return currentRunFailure("current-run evidence violates its fixed schema")
    }
    const evidence = decoded.right
    const { receiptSha256, ...core } = evidence
    const receipt = canonicalS2SControlSha256(core)
    const expectedJobId = S2S_CONFIRMATORY_STAGE_CONTRACTS[evidence.stage].jobId
    const expectedPredecessorCount =
      evidence.stage === "REGISTER" ? 0 : evidence.stage === "CONFIRM" ? 1 : 2
    const observationValues = Object.values(evidence.observations)
    if (
      Either.isLeft(receipt) ||
      receipt.right !== receiptSha256 ||
      evidence.sourceCommitA === evidence.registrationCommitB ||
      evidence.currentJobId !== expectedJobId ||
      evidence.predecessorJobDatabaseIds.length !== expectedPredecessorCount ||
      new Set(evidence.predecessorJobDatabaseIds).size !==
        evidence.predecessorJobDatabaseIds.length ||
      evidence.predecessorJobDatabaseIds.includes(
        evidence.currentJobDatabaseId
      ) ||
      Date.parse(evidence.workflowRunCreatedAt) / 1_000 !==
        evidence.workflowRunCreatedAtUnixSeconds ||
      new Set(observationValues.map((value) => value.githubRequestId)).size !==
        observationValues.length ||
      new Set(observationValues.map((value) => value.receiptSha256)).size !==
        observationValues.length ||
      observationValues.some(
        (value, index) =>
          index > 0 &&
          value.observedAtUnixSeconds <
            (observationValues[index - 1]?.observedAtUnixSeconds ?? 0)
      )
    ) {
      return currentRunFailure(
        "current-run evidence self-hash or semantic identity is invalid"
      )
    }
    return Either.right(structuredClone(evidence) as S2SCurrentRunStageEvidence)
  } catch {
    return currentRunFailure("current-run evidence validation failed closed")
  }
}

/** Compatibility wrapper retained with the predecessor-read-only domain. */
export const validateS2SCurrentRunStageEvidenceForArtifactReplay = (
  input: unknown
): Either.Either<
  S2SCurrentRunStageEvidence,
  S2SStageArtifactReadReplayError
> => {
  const validated = validateS2SCurrentRunStageEvidence(input)
  return Either.isRight(validated) && validated.right.stage === "REGISTER"
    ? currentRunFailure(
        "predecessor artifact replay has no REGISTER consumer surface"
      )
    : validated
}

const decodeReplayManifest = (
  input: Uint8Array
): Either.Either<
  S2SStageArtifactReadReplayManifest,
  S2SStageArtifactReadReplayError
> => {
  try {
    const parsed = parseS2SJsonBytes(
      input,
      S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES
    )
    if (Either.isLeft(parsed)) {
      return Either.left(
        replayError(
          "MANIFEST_INVALID",
          "MANIFEST",
          `strict JSON rejected the manifest: ${parsed.left.reason}`
        )
      )
    }
    const decoded = Schema.decodeUnknownEither(ReplayManifestSchema, {
      onExcessProperty: "error"
    })(parsed.right)
    if (Either.isLeft(decoded)) {
      return Either.left(
        replayError(
          "MANIFEST_INVALID",
          "MANIFEST",
          "manifest violates the exact v1 schema"
        )
      )
    }
    const canonical = canonicalS2SControlJsonBytes(decoded.right)
    if (Either.isLeft(canonical) || !sameBytes(canonical.right, input)) {
      return Either.left(
        replayError(
          "MANIFEST_INVALID",
          "MANIFEST",
          "manifest is not the exact canonical ASCII JSON line"
        )
      )
    }
    const { replay_receipt_sha256: declaredReceipt, ...core } = decoded.right
    const receipt = canonicalS2SControlSha256(core)
    if (Either.isLeft(receipt) || receipt.right !== declaredReceipt) {
      return Either.left(
        replayError(
          "MANIFEST_SELF_HASH_MISMATCH",
          "MANIFEST",
          "manifest aggregate receipt does not match its canonical core"
        )
      )
    }
    return Either.right(structuredClone(decoded.right))
  } catch {
    return Either.left(
      replayError(
        "MANIFEST_INVALID",
        "MANIFEST",
        "manifest decoding failed closed"
      )
    )
  }
}

interface DecodedReplayCarrier {
  readonly carrierBytes: Uint8Array
  readonly carrierRawSha256: S2SSha256
  readonly manifestBytes: Uint8Array
  readonly observationBytes: Uint8Array
  readonly manifest: S2SStageArtifactReadReplayManifest
}

const decodeReplayCarrier = (
  input: unknown
): Either.Either<DecodedReplayCarrier, S2SStageArtifactReadReplayError> => {
  const carrierBytes = snapshotPlainBytes(
    input,
    S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES
  )
  if (carrierBytes === null) {
    return Either.left(
      replayError(
        "BYTE_BUDGET_EXCEEDED",
        "CARRIER",
        "replay carrier is not one bounded plain byte array"
      )
    )
  }
  const carrierRawSha256 = S2SSha256Schema.make(
    rawS2SFileSha256(carrierBytes)
  )
  const zip = validateS2SArtifactZip(carrierBytes, {
    expectedArchiveSha256: carrierRawSha256,
    expectedArchiveByteLength: carrierBytes.byteLength,
    expectedMembers: Object.freeze([
      Object.freeze({
        name: S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME,
        maximumBytes: S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES
      }),
      Object.freeze({
        name: S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME,
        maximumBytes: S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES
      })
    ]),
    maximumArchiveBytes: S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES,
    maximumExpandedBytes:
      S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES +
      S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES
  })
  if (Either.isLeft(zip)) {
    return Either.left(
      replayError(
        "CARRIER_INVALID",
        "CARRIER",
        `stored ZIP rejected the replay: ${zip.left.reason}`
      )
    )
  }
  const manifestMember = zip.right.members.find(
    (member) =>
      member.name === S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME
  )
  const observationMember = zip.right.members.find(
    (member) =>
      member.name === S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME
  )
  if (manifestMember === undefined || observationMember === undefined) {
    return Either.left(
      replayError(
        "CARRIER_INVALID",
        "CARRIER",
        "replay ZIP lacks one of its two fixed members"
      )
    )
  }
  const manifestBytes = manifestMember.readBytes()
  const observationBytes = observationMember.readBytes()
  if (
    carrierBytes.byteLength !==
    manifestBytes.byteLength +
      observationBytes.byteLength +
      S2S_STAGE_ARTIFACT_READ_REPLAY_ZIP_FRAMING_BYTES
  ) {
    return Either.left(
      replayError(
        "CARRIER_INVALID",
        "CARRIER",
        "replay ZIP does not have the exact fixed 264-byte framing"
      )
    )
  }
  const manifest = decodeReplayManifest(manifestBytes)
  if (Either.isLeft(manifest)) return Either.left(manifest.left)
  return Either.right(
    Object.freeze({
      carrierBytes,
      carrierRawSha256,
      manifestBytes,
      observationBytes,
      manifest: manifest.right
    })
  )
}

const sameWorkflowLineage = (
  left: S2SEvidenceEnvelopeSnapshot,
  right: S2SEvidenceEnvelopeSnapshot
): boolean => {
  const a = left.document
  const b = right.document
  return (
    a.source_commit_a === b.source_commit_a &&
    a.registration_commit_b === b.registration_commit_b &&
    a.workflow_run_id === b.workflow_run_id &&
    a.workflow_run_attempt === b.workflow_run_attempt &&
    a.workflow_head_sha === b.workflow_head_sha &&
    a.workflow_run_created_at_unix_seconds ===
      b.workflow_run_created_at_unix_seconds &&
    a.workflow_api_path === b.workflow_api_path &&
    a.workflow_file_sha256 === b.workflow_file_sha256 &&
    a.workflow_contract_sha256 === b.workflow_contract_sha256
  )
}

const matchesCurrentWorkflowLineage = (
  envelope: S2SEvidenceEnvelopeSnapshot,
  current: S2SCurrentRunStageEvidence,
  predecessorOrdinal: number
): boolean => {
  const document = envelope.document
  return (
    document.source_commit_a === current.sourceCommitA &&
    document.registration_commit_b === current.registrationCommitB &&
    document.workflow_run_id === current.workflowRunId &&
    document.workflow_run_attempt === current.workflowRunAttempt &&
    document.workflow_head_sha === current.registrationCommitB &&
    document.workflow_run_created_at_unix_seconds ===
      current.workflowRunCreatedAtUnixSeconds &&
    document.workflow_api_path === current.workflowApiPath &&
    document.workflow_file_sha256 === current.workflowFileSha256 &&
    document.workflow_contract_sha256 === current.workflowContractSha256 &&
    document.current_job_database_id ===
      current.predecessorJobDatabaseIds[predecessorOrdinal]
  )
}

interface ResolvedSourceArchive {
  readonly reference: S2SStageArtifactReadReplayManifest["archive_reference"]
  readonly bytes: Uint8Array
}

const validateRecoveredPredecessorChain = (
  input: unknown,
  current: S2SCurrentRunStageEvidence
): Either.Either<
  ReadonlyArray<S2SDurableEvidenceStage>,
  S2SStageArtifactReadReplayError
> => {
  try {
    if (!isAuthenticS2SDurableEvidenceRecovery(input)) {
      throw new Error(
        "recovery was not issued by the durable evidence file store"
      )
    }
    const chainInput = input.chain
    const latestInput = input.latest
    const chain = snapshotDenseArray(chainInput, 2, 1)
    const expectedStages =
      current.stage === "CONFIRM"
        ? (["REGISTER"] as const)
        : (["REGISTER", "CONFIRM"] as const)
    if (
      chain === null ||
      chain.length !== expectedStages.length ||
      latestInput !== chain[chain.length - 1]
    ) {
      throw new Error("recovery does not expose the exact predecessor chain")
    }
    const validatedStages: Array<S2SDurableEvidenceStage> = []
    for (let index = 0; index < chain.length; index += 1) {
      const stageRecord = exactDataRecord(chain[index], ["claim", "envelope"])
      if (stageRecord === null) throw new Error("durable stage shape is invalid")
      const envelopeInput = stageRecord["envelope"]
      if (
        envelopeInput === null ||
        typeof envelopeInput !== "object" ||
        nodeTypes.isProxy(envelopeInput)
      ) {
        throw new Error("source success envelope is not an exact snapshot")
      }
      const envelope = validateS2SSuccessStageEvidenceEnvelope(envelopeInput)
      if (Either.isLeft(envelope)) {
        throw new Error("source success envelope failed revalidation")
      }
      const claimInput = stageRecord["claim"]
      if (
        claimInput === null ||
        typeof claimInput !== "object" ||
        nodeTypes.isProxy(claimInput)
      ) {
        throw new Error("source claim snapshot is invalid")
      }
      const claimBytes = snapshotPlainBytes(
        Reflect.get(claimInput, "canonicalBytes"),
        16 * KIBIBYTE
      )
      if (claimBytes === null) throw new Error("source claim bytes are invalid")
      const claim = validateS2SEvidenceClaimForEnvelope(
        claimBytes,
        envelope.right
      )
      if (Either.isLeft(claim)) {
        throw new Error("source claim does not bind its envelope")
      }
      if (
        envelope.right.document.stage !== expectedStages[index] ||
        !matchesCurrentWorkflowLineage(envelope.right, current, index)
      ) {
        throw new Error("source stage identity differs from the current run")
      }
      const previous = validatedStages[index - 1]
      if (previous !== undefined) {
        const predecessor = envelope.right.document.predecessor
        if (
          predecessor === null ||
          predecessor.stage !== previous.envelope.document.stage ||
          predecessor.manifest_raw_sha256 !==
            previous.envelope.manifestRawSha256 ||
          predecessor.claim_raw_sha256 !== previous.claim.claimRawSha256 ||
          !sameWorkflowLineage(previous.envelope, envelope.right)
        ) {
          throw new Error("source durable chain predecessor binding diverged")
        }
      }
      validatedStages.push(
        Object.freeze({ envelope: envelope.right, claim: claim.right })
      )
    }
    return Either.right(Object.freeze(validatedStages))
  } catch (error) {
    return Either.left(
      replayError(
        "ARCHIVE_REFERENCE_INVALID",
        "ARCHIVE_REFERENCE",
        error instanceof Error
          ? error.message
          : "source chain validation failed closed"
      )
    )
  }
}

const snapshotSourceArchiveFromRecovery = (
  input: unknown,
  current: S2SCurrentRunStageEvidence,
  role: "REGISTRATION" | "CANDIDATE"
): Either.Either<ResolvedSourceArchive, S2SStageArtifactReadReplayError> => {
  const validated = validateRecoveredPredecessorChain(input, current)
  if (Either.isLeft(validated)) return Either.left(validated.left)
  try {
    const policy = expectedSourceReference(role)
    const source = validated.right.find(
      (stage) => stage.envelope.document.stage === policy.sourceStage
    )
    if (source === undefined) {
      throw new Error("exact source stage is absent from the chain")
    }
    const matches = source.envelope.attachments.filter((attachment) => {
      const descriptor = attachment.descriptor
      return (
        descriptor.logical_name === policy.logicalName &&
        descriptor.role === policy.role &&
        descriptor.schema_version === policy.schemaVersion &&
        descriptor.media_type === "application/zip"
      )
    })
    if (matches.length !== 1 || matches[0] === undefined) {
      throw new Error("exact source upload attachment is absent")
    }
    const attachment = matches[0]
    const descriptor = attachment.descriptor
    const bytes = snapshotPlainBytes(
      attachment.readBytes(),
      policy.maximumArchiveBytes
    )
    if (
      bytes === null ||
      bytes.byteLength !== descriptor.byte_length ||
      rawS2SFileSha256(bytes) !== descriptor.raw_sha256
    ) {
      throw new Error("exact source upload bytes are unavailable or corrupt")
    }
    return Either.right(
      Object.freeze({
        reference: Object.freeze({
          source_stage: policy.sourceStage,
          source_manifest_raw_sha256: source.envelope.manifestRawSha256,
          source_claim_raw_sha256: source.claim.claimRawSha256,
          logical_name: policy.logicalName,
          role: policy.role,
          schema_version: policy.schemaVersion,
          media_type: "application/zip" as const,
          byte_length: descriptor.byte_length,
          raw_sha256: descriptor.raw_sha256
        }),
        bytes
      })
    )
  } catch (error) {
    return Either.left(
      replayError(
        "ARCHIVE_REFERENCE_INVALID",
        "ARCHIVE_REFERENCE",
        error instanceof Error
          ? error.message
          : "source snapshot failed closed"
      )
    )
  }
}

interface ExpectedObservation {
  readonly phase: Schema.Schema.Type<typeof ObservationPhaseSchema>
  readonly kind: Schema.Schema.Type<typeof ObservationKindSchema>
}

const expectedObservations = (
  successfulAttemptOrdinal: 1 | 2 | 3
): ReadonlyArray<ExpectedObservation> => {
  const expected: Array<ExpectedObservation> = [
    { phase: "LOOKUP_RUN_START", kind: "WORKFLOW_RUN" },
    { phase: "LOOKUP_JOBS", kind: "WORKFLOW_ATTEMPT_JOBS" }
  ]
  for (let ordinal = 1; ordinal <= successfulAttemptOrdinal; ordinal += 1) {
    expected.push(
      {
        phase: `LOOKUP_ARTIFACTS_${ordinal}` as ExpectedObservation["phase"],
        kind: "RUN_ARTIFACTS"
      },
      {
        phase: `LOOKUP_RUN_END_${ordinal}` as ExpectedObservation["phase"],
        kind: "WORKFLOW_RUN"
      }
    )
  }
  expected.push(
    { phase: "READBACK_RUN_START", kind: "WORKFLOW_RUN" },
    { phase: "READBACK_ARTIFACT", kind: "ARTIFACT" },
    { phase: "READBACK_RUN_END", kind: "WORKFLOW_RUN" }
  )
  return Object.freeze(expected.map((entry) => Object.freeze(entry)))
}

interface ReplayedObservation {
  readonly phase: ExpectedObservation["phase"]
  readonly observation: S2SGitHubObservation
}

const reconstructObservation = (
  descriptor: S2SStageArtifactReadReplayManifest["observations"][number],
  rawBody: Uint8Array,
  manifest: S2SStageArtifactReadReplayManifest
): Either.Either<S2SGitHubObservation, S2SStageArtifactReadReplayError> => {
  const provenance = Object.freeze({
    githubRequestId: descriptor.github_request_id,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: descriptor.response_etag
  })
  const observed: Either.Either<
    S2SGitHubObservation,
    S2SGitHubObservationError
  > = (() => {
    switch (descriptor.kind) {
      case "WORKFLOW_RUN":
        return Either.map(
          observeS2SGitHubWorkflowRun(
            rawBody,
            manifest.identity.workflowRunId,
            descriptor.observed_at_unix_seconds,
            provenance
          ),
          (observation): S2SGitHubObservation => observation
        )
      case "WORKFLOW_ATTEMPT_JOBS":
        return Either.map(
          observeS2SGitHubWorkflowAttemptJobs(
            rawBody,
            manifest.identity.workflowRunId,
            1,
            descriptor.observed_at_unix_seconds,
            provenance
          ),
          (observation): S2SGitHubObservation => observation
        )
      case "RUN_ARTIFACTS":
        return Either.map(
          observeS2SGitHubRunArtifacts(
            rawBody,
            manifest.identity.workflowRunId,
            descriptor.observed_at_unix_seconds,
            provenance
          ),
          (observation): S2SGitHubObservation => observation
        )
      case "ARTIFACT":
        return Either.map(
          observeS2SGitHubArtifact(
            rawBody,
            manifest.artifact_id,
            descriptor.observed_at_unix_seconds,
            provenance
          ),
          (observation): S2SGitHubObservation => observation
        )
    }
  })()
  if (Either.isLeft(observed)) {
    return Either.left(
      replayError(
        "OBSERVATION_REPLAY_INVALID",
        descriptor.phase,
        `raw GitHub response could not be reconstructed: ${observed.left.reason}`
      )
    )
  }
  const receipt = observed.right.receipt
  if (
    receipt.kind !== descriptor.kind ||
    receipt.rawBodyByteLength !== descriptor.byte_length ||
    receipt.rawBodySha256 !== descriptor.raw_body_sha256 ||
    receipt.observedAtUnixSeconds !== descriptor.observed_at_unix_seconds ||
    receipt.githubRequestId !== descriptor.github_request_id ||
    receipt.responseEtag !== descriptor.response_etag ||
    receipt.projectionSha256 !== descriptor.projection_sha256 ||
    receipt.receiptSha256 !== descriptor.receipt_sha256
  ) {
    return Either.left(
      replayError(
        "OBSERVATION_REPLAY_INVALID",
        descriptor.phase,
        "compact observation metadata differs from trusted reconstruction"
      )
    )
  }
  return Either.right(observed.right as S2SGitHubObservation)
}

const reconstructObservations = (
  manifest: S2SStageArtifactReadReplayManifest,
  observationBytes: Uint8Array
): Either.Either<
  ReadonlyArray<ReplayedObservation>,
  S2SStageArtifactReadReplayError
> => {
  const expected = expectedObservations(manifest.successful_attempt_ordinal)
  if (
    manifest.observation_count !== expected.length ||
    manifest.observation_count !==
      s2sStageArtifactReadReplayObservationCount(
        manifest.successful_attempt_ordinal
      ) ||
    manifest.observations.length !== expected.length ||
    observationBytes.byteLength !== manifest.observation_blob_byte_length ||
    observationBytes.byteLength >
      s2sStageArtifactReadReplayRawBodyMaximumBytes(
        manifest.successful_attempt_ordinal
      ) ||
    rawS2SFileSha256(observationBytes) !==
      manifest.observation_blob_sha256
  ) {
    return Either.left(
      replayError(
        "POLL_TOPOLOGY_INVALID",
        "OBSERVATIONS",
        "observation count, aggregate length, or blob hash is inconsistent"
      )
    )
  }
  const output: Array<ReplayedObservation> = []
  let offset = 0
  for (let index = 0; index < manifest.observations.length; index += 1) {
    const descriptor = manifest.observations[index]
    const expectedDescriptor = expected[index]
    if (
      descriptor === undefined ||
      expectedDescriptor === undefined ||
      descriptor.ordinal !== index + 1 ||
      descriptor.phase !== expectedDescriptor.phase ||
      descriptor.kind !== expectedDescriptor.kind ||
      descriptor.offset !== offset ||
      descriptor.offset + descriptor.byte_length > observationBytes.byteLength
    ) {
      return Either.left(
        replayError(
          "POLL_TOPOLOGY_INVALID",
          expectedDescriptor?.phase ?? "OBSERVATIONS",
          "observation tuple or contiguous byte partition is invalid"
        )
      )
    }
    const rawBody = Uint8Array.from(
      observationBytes.subarray(offset, offset + descriptor.byte_length)
    )
    if (rawS2SFileSha256(rawBody) !== descriptor.raw_body_sha256) {
      return Either.left(
        replayError(
          "OBSERVATION_REPLAY_INVALID",
          descriptor.phase,
          "observation slice differs from its raw SHA-256"
        )
      )
    }
    const observation = reconstructObservation(descriptor, rawBody, manifest)
    if (Either.isLeft(observation)) return Either.left(observation.left)
    output.push(
      Object.freeze({
        phase: descriptor.phase,
        observation: observation.right
      })
    )
    offset += descriptor.byte_length
  }
  if (offset !== observationBytes.byteLength) {
    return Either.left(
      replayError(
        "POLL_TOPOLOGY_INVALID",
        "OBSERVATIONS",
        "observation slices do not exhaust the exact blob"
      )
    )
  }
  return Either.right(Object.freeze(output))
}

const observationAt = <Projection extends S2SGitHubProjection>(
  observations: ReadonlyArray<ReplayedObservation>,
  phase: ExpectedObservation["phase"]
): S2SGitHubObservation<Projection> | undefined =>
  observations.find((entry) => entry.phase === phase)?.observation as
    | S2SGitHubObservation<Projection>
    | undefined

const hasExpectedWorkflowIdentity = (
  projection: S2SGitHubWorkflowRunProjection,
  identity: S2SStageArtifactPermitIdentity
): boolean =>
  projection.id === identity.workflowRunId &&
  projection.runAttempt === 1 &&
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
  left.headBranch === right.headBranch &&
  left.createdAt === right.createdAt &&
  left.createdAtUnixSeconds === right.createdAtUnixSeconds

const expectedProducerJobId = (
  identity: S2SStageArtifactPermitIdentity,
  role: "REGISTRATION" | "CANDIDATE"
): number | undefined =>
  role === "REGISTRATION"
    ? identity.predecessorJobDatabaseIds[0]
    : identity.predecessorJobDatabaseIds[1]

const jobsMatchIdentity = (
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  identity: S2SStageArtifactPermitIdentity
): boolean => {
  const projection = jobs.receipt.projection
  if (
    projection.totalCount !== S2S_CONFIRMATORY_JOB_STAGES.length ||
    projection.jobs.length !== S2S_CONFIRMATORY_JOB_STAGES.length
  ) {
    return false
  }
  const jobsByStage = new Map<
    (typeof S2S_CONFIRMATORY_JOB_STAGES)[number],
    S2SGitHubWorkflowJobProjection
  >()
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    const expectedName = S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobName
    const matches = projection.jobs.filter((job) => job.name === expectedName)
    if (matches.length !== 1 || matches[0] === undefined) return false
    jobsByStage.set(stage, matches[0])
  }
  if (
    projection.jobs.some(
      (job) =>
        job.runId !== identity.workflowRunId ||
        job.runAttempt !== 1 ||
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
    const stage = S2S_CONFIRMATORY_JOB_STAGES[index]
    const predecessor = stage === undefined ? undefined : jobsByStage.get(stage)
    if (
      predecessor === undefined ||
      predecessor.status !== "completed" ||
      predecessor.conclusion !== "success" ||
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
      (value, index) => value !== identity.predecessorJobDatabaseIds[index]
    )
  ) {
    return false
  }
  const notStarted = new Set([
    "queued",
    "waiting",
    "pending",
    "requested"
  ])
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
      return false
    }
  }
  return true
}

const archiveProjection = (
  archive: S2SValidatedArtifactZip
): S2SStageArtifactReadReplayManifest["archive_validation"] =>
  Object.freeze({
    archive_byte_length: archive.archiveByteLength,
    archive_sha256: archive.archiveSha256,
    expanded_byte_length: archive.expandedByteLength,
    largest_member_byte_length: archive.largestMemberByteLength,
    members: Object.freeze(
      archive.members.map((member) =>
        Object.freeze({
          name: member.name as
            | "control_receipt.json"
            | "numeric_candidate.json",
          byte_length: member.byteLength,
          crc32: member.crc32,
          raw_bytes_sha256: member.rawBytesSha256
        })
      )
    )
  })

const expectedSourceReference = (
  role: "REGISTRATION" | "CANDIDATE"
) => {
  if (role === "REGISTRATION") {
    const spec = S2S_STAGE_ARTIFACT_SPECS.REGISTER
    return Object.freeze({
      sourceStage: spec.stage,
      logicalName: spec.archiveLogicalName,
      role: spec.archiveProfileRole,
      schemaVersion: spec.carrierSchemaVersion,
      artifactName: spec.artifactName,
      producerJobName: spec.jobName,
      maximumArchiveBytes: spec.maximumArchiveBytes,
      expectedMembers: spec.expectedMembers
    })
  }
  const spec = S2S_STAGE_ARTIFACT_SPECS.CONFIRM
  return Object.freeze({
    sourceStage: spec.stage,
    logicalName: spec.archiveLogicalName,
    role: spec.archiveProfileRole,
    schemaVersion: spec.carrierSchemaVersion,
    artifactName: spec.artifactName,
    producerJobName: spec.jobName,
    maximumArchiveBytes: spec.maximumArchiveBytes,
    expectedMembers: spec.expectedMembers
  })
}

const candidateFingerprint = (
  artifact: Readonly<
    Pick<
      S2SStageArtifactReadReplayManifest,
      | "role"
      | "artifact_id"
      | "artifact_name"
      | "artifact_byte_length"
      | "artifact_sha256"
    >
  >,
  download: S2SGitHubArtifactDownloadReceipt,
  archive: S2SValidatedArtifactZip
): string | null => {
  if (artifact.role !== "CANDIDATE") return null
  const hashed = canonicalS2SControlSha256({
    artifactId: artifact.artifact_id,
    artifactName: artifact.artifact_name,
    artifactSizeInBytes: artifact.artifact_byte_length,
    apiDigestSha256: artifact.artifact_sha256,
    downloadedArchiveSha256: download.downloadedArchiveSha256,
    validatedArchiveSha256: archive.archiveSha256
  })
  return Either.isRight(hashed) ? hashed.right : null
}

interface ValidatedReplaySemantics {
  readonly observations: ReadonlyArray<ReplayedObservation>
  readonly archive: S2SValidatedArtifactZip
  readonly permit: S2SStageArtifactPermitEvidence
  readonly archiveBytes: Uint8Array
}

const validateReplaySemantics = (
  manifest: S2SStageArtifactReadReplayManifest,
  current: S2SCurrentRunStageEvidence,
  observations: ReadonlyArray<ReplayedObservation>,
  source: ResolvedSourceArchive
): Either.Either<
  ValidatedReplaySemantics,
  S2SStageArtifactReadReplayError
> => {
  if (!sameCanonicalData(manifest.archive_reference, source.reference)) {
    return Either.left(
      replayError(
        "ARCHIVE_REFERENCE_INVALID",
        "ARCHIVE_REFERENCE",
        "replay archive reference differs from the recovered source snapshot"
      )
    )
  }
  const contract = s2sArtifactReadContract(
    manifest.identity.stage,
    manifest.operation
  )
  const policy = expectedSourceReference(manifest.role)
  const identityMatchesCurrent =
    manifest.source_commit_a === current.sourceCommitA &&
    manifest.current_run_evidence_receipt_sha256 === current.receiptSha256 &&
    manifest.identity.workflowRunId === current.workflowRunId &&
    manifest.identity.workflowRunAttempt === current.workflowRunAttempt &&
    manifest.identity.registrationCommitB === current.registrationCommitB &&
    manifest.identity.workflowApiPath === current.workflowApiPath &&
    manifest.identity.workflowRunCreatedAt === current.workflowRunCreatedAt &&
    manifest.identity.workflowRunCreatedAtUnixSeconds ===
      current.workflowRunCreatedAtUnixSeconds &&
    manifest.identity.stage === current.stage &&
    manifest.identity.currentJobDatabaseId === current.currentJobDatabaseId &&
    sameCanonicalData(
      manifest.identity.predecessorJobDatabaseIds,
      current.predecessorJobDatabaseIds
    )
  if (
    !identityMatchesCurrent ||
    contract === undefined ||
    contract.artifactRole !== manifest.role ||
    manifest.artifact_name !== policy.artifactName ||
    manifest.producer_job_name !== policy.producerJobName ||
    manifest.archive_reference.source_stage !== policy.sourceStage ||
    manifest.archive_reference.logical_name !== policy.logicalName ||
    manifest.archive_reference.role !== policy.role ||
    manifest.archive_reference.schema_version !== policy.schemaVersion ||
    manifest.archive_reference.media_type !== "application/zip"
  ) {
    return Either.left(
      replayError(
        "READ_IDENTITY_MISMATCH",
        "IDENTITY",
        "current run, operation, role, or source-archive policy diverged"
      )
    )
  }

  const initialRun = observationAt<S2SGitHubWorkflowRunProjection>(
    observations,
    "LOOKUP_RUN_START"
  )
  const jobs = observationAt<S2SGitHubWorkflowJobsProjection>(
    observations,
    "LOOKUP_JOBS"
  )
  const readbackStart = observationAt<S2SGitHubWorkflowRunProjection>(
    observations,
    "READBACK_RUN_START"
  )
  const artifactRequery = observationAt<S2SGitHubArtifactProjection>(
    observations,
    "READBACK_ARTIFACT"
  )
  const readbackEnd = observationAt<S2SGitHubWorkflowRunProjection>(
    observations,
    "READBACK_RUN_END"
  )
  if (
    initialRun === undefined ||
    jobs === undefined ||
    readbackStart === undefined ||
    artifactRequery === undefined ||
    readbackEnd === undefined ||
    !hasExpectedWorkflowIdentity(initialRun.receipt.projection, manifest.identity) ||
    !jobsMatchIdentity(initialRun, jobs, manifest.identity)
  ) {
    return Either.left(
      replayError(
        "READ_IDENTITY_MISMATCH",
        "LOOKUP",
        "lookup run or exact attempt-one job roster is invalid"
      )
    )
  }

  const producerId = expectedProducerJobId(manifest.identity, manifest.role)
  const producers = jobs.receipt.projection.jobs.filter(
    (job) => job.name === policy.producerJobName
  )
  const producer = producers.length === 1 ? producers[0] : undefined
  if (
    producer === undefined ||
    producerId === undefined ||
    producer.id !== producerId ||
    producer.id !== manifest.producer_job_id ||
    producer.status !== "completed" ||
    producer.conclusion !== "success" ||
    producer.completedAtUnixSeconds === null
  ) {
    return Either.left(
      replayError(
        "READ_IDENTITY_MISMATCH",
        "LOOKUP_JOBS",
        "producer job is not the exact successful predecessor"
      )
    )
  }

  let selectedArtifact: S2SGitHubArtifactProjection | undefined
  let previousTime = jobs.receipt.observedAtUnixSeconds
  for (
    let ordinal = 1;
    ordinal <= manifest.successful_attempt_ordinal;
    ordinal += 1
  ) {
    const artifacts = observationAt<S2SGitHubArtifactsProjection>(
      observations,
      `LOOKUP_ARTIFACTS_${ordinal}` as ExpectedObservation["phase"]
    )
    const run = observationAt<S2SGitHubWorkflowRunProjection>(
      observations,
      `LOOKUP_RUN_END_${ordinal}` as ExpectedObservation["phase"]
    )
    if (
      artifacts === undefined ||
      run === undefined ||
      artifacts.receipt.observedAtUnixSeconds < previousTime ||
      run.receipt.observedAtUnixSeconds <
        artifacts.receipt.observedAtUnixSeconds ||
      artifacts.receipt.observedAtUnixSeconds <
        producer.completedAtUnixSeconds ||
      !hasExpectedWorkflowIdentity(run.receipt.projection, manifest.identity) ||
      !sameWorkflowIdentity(
        initialRun.receipt.projection,
        run.receipt.projection
      ) ||
      artifacts.receipt.projection.artifacts.some(
        (artifact) =>
          artifact.workflowRunId !== manifest.identity.workflowRunId ||
          artifact.workflowHeadSha !== manifest.identity.registrationCommitB
      )
    ) {
      return Either.left(
        replayError(
          "POLL_TOPOLOGY_INVALID",
          `LOOKUP_ARTIFACTS_${ordinal}`,
          "lookup observation order or run/head binding is invalid"
        )
      )
    }
    const matching = artifacts.receipt.projection.artifacts.filter(
      (artifact) => artifact.name === policy.artifactName
    )
    const isFinal = ordinal === manifest.successful_attempt_ordinal
    if ((!isFinal && matching.length !== 0) || (isFinal && matching.length !== 1)) {
      return Either.left(
        replayError(
          "POLL_TOPOLOGY_INVALID",
          `LOOKUP_ARTIFACTS_${ordinal}`,
          "earlier polls must be absent and the successful poll exactly singular"
        )
      )
    }
    if (isFinal) selectedArtifact = matching[0]
    previousTime = run.receipt.observedAtUnixSeconds
  }
  if (
    selectedArtifact === undefined ||
    selectedArtifact.expired ||
    selectedArtifact.createdAtUnixSeconds < producer.startedAtUnixSeconds ||
    selectedArtifact.createdAtUnixSeconds > producer.completedAtUnixSeconds ||
    selectedArtifact.id !== manifest.artifact_id ||
    selectedArtifact.name !== manifest.artifact_name ||
    selectedArtifact.sizeInBytes !== manifest.artifact_byte_length ||
    selectedArtifact.digestSha256 !== manifest.artifact_sha256 ||
    manifest.archive_reference.byte_length !== manifest.artifact_byte_length ||
    manifest.archive_reference.raw_sha256 !== manifest.artifact_sha256 ||
    source.bytes.byteLength !== manifest.artifact_byte_length ||
    rawS2SFileSha256(source.bytes) !== manifest.artifact_sha256
  ) {
    return Either.left(
      replayError(
        "READ_IDENTITY_MISMATCH",
        "LOOKUP_SUCCESS",
        "selected artifact, source content object, and manifest identity diverge"
      )
    )
  }
  if (
    !hasExpectedWorkflowIdentity(
      readbackStart.receipt.projection,
      manifest.identity
    ) ||
    !hasExpectedWorkflowIdentity(
      readbackEnd.receipt.projection,
      manifest.identity
    ) ||
    !sameWorkflowIdentity(
      initialRun.receipt.projection,
      readbackStart.receipt.projection
    ) ||
    !sameWorkflowIdentity(
      readbackStart.receipt.projection,
      readbackEnd.receipt.projection
    ) ||
    readbackStart.receipt.observedAtUnixSeconds < previousTime ||
    artifactRequery.receipt.observedAtUnixSeconds <
      readbackStart.receipt.observedAtUnixSeconds ||
    !sameCanonicalData(
      artifactRequery.receipt.projection,
      selectedArtifact
    )
  ) {
    return Either.left(
      replayError(
        "READ_IDENTITY_MISMATCH",
        "READBACK",
        "fresh readback run or exact artifact requery diverged"
      )
    )
  }

  const download = validateS2SGitHubArtifactDownload(
    Object.freeze({
      receipt: manifest.download_receipt,
      readArchiveBytes: () => Uint8Array.from(source.bytes)
    }),
    manifest.artifact_id,
    policy.maximumArchiveBytes
  )
  if (Either.isLeft(download)) {
    return Either.left(
      replayError(
        "ARCHIVE_REPLAY_INVALID",
        "DOWNLOAD",
        `download receipt rejected referenced bytes: ${download.left.reason}`
      )
    )
  }
  const downloadReceipt = download.right.receipt
  if (
    downloadReceipt.downloadedAtUnixSeconds <
      artifactRequery.receipt.observedAtUnixSeconds ||
    readbackEnd.receipt.observedAtUnixSeconds <
      downloadReceipt.downloadedAtUnixSeconds ||
    downloadReceipt.archiveByteLength !== manifest.artifact_byte_length ||
    downloadReceipt.downloadedArchiveSha256 !== manifest.artifact_sha256
  ) {
    return Either.left(
      replayError(
        "ARCHIVE_REPLAY_INVALID",
        "DOWNLOAD",
        "download receipt order or archive binding is invalid"
      )
    )
  }
  const archive = validateS2SArtifactZip(source.bytes, {
    expectedArchiveSha256: S2SSha256Schema.make(manifest.artifact_sha256),
    expectedArchiveByteLength: manifest.artifact_byte_length,
    expectedMembers: policy.expectedMembers,
    maximumArchiveBytes: policy.maximumArchiveBytes,
    maximumExpandedBytes: policy.maximumArchiveBytes
  })
  if (
    Either.isLeft(archive) ||
    (Either.isRight(archive) &&
      !sameCanonicalData(
        archiveProjection(archive.right),
        manifest.archive_validation
      ))
  ) {
    return Either.left(
      replayError(
        "ARCHIVE_REPLAY_INVALID",
        "ARCHIVE",
        Either.isLeft(archive)
          ? `referenced archive ZIP rejected: ${archive.left.reason}`
          : "archive/member projection differs from fresh validation"
      )
    )
  }
  const expectedArtifactEvidence = Object.freeze({
    artifactName: manifest.artifact_name,
    artifactId: manifest.artifact_id,
    artifactCount: 1,
    archiveSizeBytes: manifest.artifact_byte_length,
    largestMemberSizeBytes: archive.right.largestMemberByteLength,
    compressionLevel: S2S_CONFIRMATORY_POLICY.archive.compressionLevel,
    retentionDays: S2S_CONFIRMATORY_POLICY.archive.retentionDays,
    overwrite: S2S_CONFIRMATORY_POLICY.archive.overwrite,
    apiDigestSha256: manifest.artifact_sha256,
    downloadedArchiveSha256: downloadReceipt.downloadedArchiveSha256
  })
  if (!sameCanonicalData(expectedArtifactEvidence, manifest.artifact_evidence)) {
    return Either.left(
      replayError(
        "ARCHIVE_REPLAY_INVALID",
        "ARTIFACT_EVIDENCE",
        "artifact evidence differs from the replayed archive"
      )
    )
  }
  const fingerprint = candidateFingerprint(manifest, downloadReceipt, archive.right)
  if (fingerprint !== manifest.candidate_fingerprint_sha256) {
    return Either.left(
      replayError(
        "CANDIDATE_FINGERPRINT_MISMATCH",
        "CANDIDATE_FINGERPRINT",
        "candidate fingerprint differs from the fixed six-field preimage"
      )
    )
  }

  const permit = validateS2SStageArtifactPermitEvidence(
    manifest.permit_evidence,
    current
  )
  if (
    Either.isLeft(permit) ||
    (Either.isRight(permit) &&
      (!sameCanonicalData(permit.right.identity, manifest.identity) ||
        permit.right.operation !== manifest.operation))
  ) {
    return Either.left(
      replayError(
        "LEDGER_BINDING_MISMATCH",
        "PERMIT_EVIDENCE",
        Either.isLeft(permit)
          ? `permit evidence rejected: ${permit.left.reason}`
          : "permit identity or operation differs from the manifest"
      )
    )
  }
  const operationEntries = permit.right.ledgerEntries.filter(
    (entry) => entry.operation === manifest.operation
  )
  const expectedEntries = manifest.observations.flatMap((descriptor) => {
    const observation = observations.find(
      (entry) => entry.phase === descriptor.phase
    )?.observation
    if (observation === undefined) return []
    const entry = Object.freeze({
      operation: manifest.operation,
      phase: descriptor.phase as S2SStageArtifactLedgerPhase,
      githubRequestId: observation.receipt.githubRequestId,
      receiptSha256: observation.receipt.receiptSha256,
      observedAtUnixSeconds: observation.receipt.observedAtUnixSeconds
    })
    return descriptor.phase === "READBACK_RUN_END"
      ? [
          Object.freeze({
            operation: manifest.operation,
            phase: "READBACK_DOWNLOAD_REDIRECT" as const,
            githubRequestId: downloadReceipt.redirectGitHubRequestId,
            receiptSha256: downloadReceipt.receiptSha256,
            observedAtUnixSeconds: downloadReceipt.downloadedAtUnixSeconds
          }),
          entry
        ]
      : [entry]
  })
  if (
    operationEntries.length !== expectedEntries.length ||
    operationEntries.some(
      (entry, index) => !sameCanonicalData(entry, expectedEntries[index])
    )
  ) {
    return Either.left(
      replayError(
        "LEDGER_BINDING_MISMATCH",
        "PERMIT_LEDGER",
        "operation ledger is not the exact raw-observation/download sequence"
      )
    )
  }
  return Either.right(
    Object.freeze({
      observations,
      archive: archive.right,
      permit: permit.right,
      archiveBytes: Uint8Array.from(source.bytes)
    })
  )
}

const AUTHENTIC_REPLAY_SNAPSHOTS = new WeakSet<object>()

/**
 * Root-private runtime authenticity check for a freshly validated predecessor
 * replay. A structurally valid or serialized replay is evidence data, not this
 * process-local bearer.
 */
export const inspectS2SStageArtifactReadReplaySnapshot = (
  input: unknown
): Either.Either<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError
> => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      !AUTHENTIC_REPLAY_SNAPSHOTS.has(input)
    ) {
      return Either.left(
        replayError(
          "INPUT_INVALID",
          "AUTHENTIC_REPLAY",
          "predecessor replay was not issued by this module instance"
        )
      )
    }
    return Either.right(input as S2SStageArtifactReadReplaySnapshot)
  } catch {
    return Either.left(
      replayError(
        "INPUT_INVALID",
        "AUTHENTIC_REPLAY",
        "predecessor replay authenticity inspection failed closed"
      )
    )
  }
}

const makeReplaySnapshot = (
  carrier: DecodedReplayCarrier,
  semantics: ValidatedReplaySemantics
): S2SStageArtifactReadReplaySnapshot => {
  const manifestSnapshot = structuredClone(carrier.manifest)
  const carrierBytes = Uint8Array.from(carrier.carrierBytes)
  const observationBytes = Uint8Array.from(carrier.observationBytes)
  const archiveBytes = Uint8Array.from(semantics.archiveBytes)
  const observations = Object.freeze(
    semantics.observations.map((entry) => entry.observation)
  )
  const snapshot = Object.freeze({
    get manifest(): S2SStageArtifactReadReplayManifest {
      return structuredClone(manifestSnapshot)
    },
    manifestRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(carrier.manifestBytes)
    ),
    carrierRawSha256: carrier.carrierRawSha256,
    carrierByteLength: carrierBytes.byteLength,
    get observations(): ReadonlyArray<S2SGitHubObservation> {
      return observations
    },
    archiveValidation: semantics.archive,
    permitEvidence: semantics.permit,
    readCarrierBytes: (): Uint8Array => Uint8Array.from(carrierBytes),
    readObservationBlob: (): Uint8Array => Uint8Array.from(observationBytes),
    readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes)
  })
  AUTHENTIC_REPLAY_SNAPSHOTS.add(snapshot)
  return snapshot
}

const validateDecodedReplayWithPreparedSource = (
  carrier: DecodedReplayCarrier,
  current: S2SCurrentRunStageEvidence,
  source: ResolvedSourceArchive
): Either.Either<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError
> => {
  const observations = reconstructObservations(
    carrier.manifest,
    carrier.observationBytes
  )
  if (Either.isLeft(observations)) return Either.left(observations.left)
  const semantics = validateReplaySemantics(
    carrier.manifest,
    current,
    observations.right,
    source
  )
  return Either.isLeft(semantics)
    ? Either.left(semantics.left)
    : Either.right(makeReplaySnapshot(carrier, semantics.right))
}

export const validateS2SStageArtifactReadReplay = (
  input: unknown
): Either.Either<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError
> => {
  try {
    const root = exactDataRecord(input, [
      "carrierBytes",
      "currentRunEvidence",
      "predecessorRecovery"
    ])
    if (root === null) {
      return Either.left(
        replayError(
          "INPUT_INVALID",
          "INPUT",
          "replay validation input must be one exact plain data record"
        )
      )
    }
    const current =
      validateS2SCurrentRunStageEvidenceForArtifactReplay(
        root["currentRunEvidence"]
      )
    if (Either.isLeft(current)) return Either.left(current.left)
    const carrier = decodeReplayCarrier(root["carrierBytes"])
    if (Either.isLeft(carrier)) return Either.left(carrier.left)
    const source = snapshotSourceArchiveFromRecovery(
      root["predecessorRecovery"],
      current.right,
      carrier.right.manifest.role
    )
    if (Either.isLeft(source)) return Either.left(source.left)
    return validateDecodedReplayWithPreparedSource(
      carrier.right,
      current.right,
      source.right
    )
  } catch {
    return Either.left(
      replayError(
        "INPUT_INVALID",
        "INPUT",
        "replay validation failed closed"
      )
    )
  }
}

export const validateS2SStageArtifactReadReplayEffect = (
  input: unknown
): Effect.Effect<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError
> => suspendEither(() => validateS2SStageArtifactReadReplay(input))

const permitAuthorityProjection = (evidence: S2SStageArtifactPermitEvidence) =>
  Object.freeze({
    schemaVersion: evidence.schemaVersion,
    authorityScope: evidence.authorityScope,
    authorizationClaimed: evidence.authorizationClaimed,
    oneUseClaim: evidence.oneUseClaim,
    crossWorkerReplayPreventionClaimed:
      evidence.crossWorkerReplayPreventionClaimed,
    crossModuleCopyReplayPreventionClaimed:
      evidence.crossModuleCopyReplayPreventionClaimed,
    crossProcessReplayPreventionClaimed:
      evidence.crossProcessReplayPreventionClaimed,
    durableReplayPreventionClaimed: evidence.durableReplayPreventionClaimed,
    identity: evidence.identity,
    ledgerCapacity: evidence.ledgerCapacity
  })

const isExactPermitLedgerPrefix = (
  prefix: S2SStageArtifactPermitEvidence,
  extension: S2SStageArtifactPermitEvidence
): boolean =>
  prefix.ledgerEntries.length < extension.ledgerEntries.length &&
  prefix.ledgerEntries.every((entry, index) =>
    sameCanonicalData(entry, extension.ledgerEntries[index])
  )

export const validateS2SCandidateReadReplayPair = (
  firstInput: unknown,
  rereadInput: unknown
): Either.Either<
  readonly [
    S2SStageArtifactReadReplaySnapshot,
    S2SStageArtifactReadReplaySnapshot
  ],
  S2SStageArtifactReadReplayError
> => {
  try {
    if (
      firstInput === null ||
      typeof firstInput !== "object" ||
      rereadInput === null ||
      typeof rereadInput !== "object" ||
      !AUTHENTIC_REPLAY_SNAPSHOTS.has(firstInput) ||
      !AUTHENTIC_REPLAY_SNAPSHOTS.has(rereadInput)
    ) {
      return Either.left(
        replayError(
          "INPUT_INVALID",
          "CANDIDATE_PAIR",
          "candidate comparison requires two freshly validated replay snapshots"
        )
      )
    }
    const first = firstInput as S2SStageArtifactReadReplaySnapshot
    const reread = rereadInput as S2SStageArtifactReadReplaySnapshot
    const a = first.manifest
    const b = reread.manifest
    if (
      a.operation !== "ADJUDICATE_READ_CANDIDATE_FIRST" ||
      b.operation !== "ADJUDICATE_REREAD_CANDIDATE" ||
      a.role !== "CANDIDATE" ||
      b.role !== "CANDIDATE" ||
      a.candidate_fingerprint_sha256 === null ||
      a.candidate_fingerprint_sha256 !== b.candidate_fingerprint_sha256 ||
      a.source_commit_a !== b.source_commit_a ||
      !sameCanonicalData(a.identity, b.identity) ||
      !sameCanonicalData(a.archive_reference, b.archive_reference) ||
      a.artifact_id !== b.artifact_id ||
      a.artifact_name !== b.artifact_name ||
      a.artifact_byte_length !== b.artifact_byte_length ||
      a.artifact_sha256 !== b.artifact_sha256 ||
      !sameBytes(first.readArchiveBytes(), reread.readArchiveBytes())
    ) {
      return Either.left(
        replayError(
          "CANDIDATE_FINGERPRINT_MISMATCH",
          "CANDIDATE_PAIR",
          "candidate reread differs from the independently validated first read"
        )
      )
    }
    if (
      a.current_run_evidence_receipt_sha256 !==
        b.current_run_evidence_receipt_sha256 ||
      !sameCanonicalData(
        permitAuthorityProjection(first.permitEvidence),
        permitAuthorityProjection(reread.permitEvidence)
      ) ||
      !isExactPermitLedgerPrefix(
        first.permitEvidence,
        reread.permitEvidence
      )
    ) {
      return Either.left(
        replayError(
          "LEDGER_BINDING_MISMATCH",
          "CANDIDATE_PAIR",
          "candidate reread is not one exact cumulative permit-ledger extension of the first read"
        )
      )
    }
    return Either.right(Object.freeze([first, reread] as const))
  } catch {
    return Either.left(
      replayError(
        "INPUT_INVALID",
        "CANDIDATE_PAIR",
        "candidate replay comparison failed closed"
      )
    )
  }
}

export const validateS2SCandidateReadReplayPairEffect = (
  firstInput: unknown,
  rereadInput: unknown
): Effect.Effect<
  readonly [
    S2SStageArtifactReadReplaySnapshot,
    S2SStageArtifactReadReplaySnapshot
  ],
  S2SStageArtifactReadReplayError
> =>
  suspendEither(() =>
    validateS2SCandidateReadReplayPair(firstInput, rereadInput)
  )

export interface S2SStageArtifactReadReplayBuildInput {
  readonly validatedRead: S2SValidatedStageArtifactRead
  readonly currentRunEvidence: S2SCurrentRunStageEvidence
  readonly predecessorRecovery: S2SDurableEvidenceRecovery
}

interface BuildObservation {
  readonly phase: ExpectedObservation["phase"]
  readonly observation: S2SGitHubObservation
}

const snapshotBuildObservation = (
  input: BuildObservation,
  ordinal: number,
  offset: number
): Either.Either<
  {
    readonly descriptor: S2SStageArtifactReadReplayManifest["observations"][number]
    readonly bytes: Uint8Array
  },
  S2SStageArtifactReadReplayError
> => {
  try {
    const wrapper = exactDataRecord(input.observation, ["readRawBody", "receipt"])
    if (wrapper === null || typeof wrapper["readRawBody"] !== "function") {
      throw new Error("observation wrapper is not exact")
    }
    const bytes = snapshotPlainBytes(
      Reflect.apply(wrapper["readRawBody"], undefined, []),
      S2S_GITHUB_JSON_MAX_BYTES
    )
    const receipt = wrapper["receipt"] as
      | S2SGitHubObservation["receipt"]
      | undefined
    if (
      bytes === null ||
      receipt === undefined ||
      receipt.rawBodyByteLength !== bytes.byteLength ||
      receipt.rawBodySha256 !== rawS2SFileSha256(bytes) ||
      (receipt.kind !== "WORKFLOW_RUN" &&
        receipt.kind !== "WORKFLOW_ATTEMPT_JOBS" &&
        receipt.kind !== "RUN_ARTIFACTS" &&
        receipt.kind !== "ARTIFACT")
    ) {
      throw new Error("observation raw body differs from its receipt")
    }
    return Either.right(
      Object.freeze({
        descriptor: Object.freeze({
          ordinal,
          phase: input.phase,
          kind: receipt.kind,
          offset,
          byte_length: bytes.byteLength,
          raw_body_sha256: S2SSha256Schema.make(receipt.rawBodySha256),
          observed_at_unix_seconds: receipt.observedAtUnixSeconds,
          github_request_id: receipt.githubRequestId,
          response_etag: receipt.responseEtag,
          projection_sha256: S2SSha256Schema.make(receipt.projectionSha256),
          receipt_sha256: S2SSha256Schema.make(receipt.receiptSha256)
        }),
        bytes
      })
    )
  } catch (error) {
    return Either.left(
      replayError(
        "OBSERVATION_REPLAY_INVALID",
        input.phase,
        error instanceof Error
          ? error.message
          : "observation snapshot failed closed"
      )
    )
  }
}

const concatenateObservationBytes = (
  values: ReadonlyArray<Uint8Array>,
  maximumBytes: number
): Uint8Array | null => {
  const total = values.reduce((sum, bytes) => sum + bytes.byteLength, 0)
  if (!Number.isSafeInteger(total) || total < 1 || total > maximumBytes) {
    return null
  }
  const output = new Uint8Array(total)
  let offset = 0
  for (const bytes of values) {
    output.set(bytes, offset)
    offset += bytes.byteLength
  }
  return offset === total ? output : null
}

const inputArchiveSurfacesMatch = (
  read: S2SValidatedStageArtifactRead,
  source: ResolvedSourceArchive,
  freshArchive: S2SValidatedArtifactZip
): boolean => {
  try {
    const readBytes = snapshotPlainBytes(
      read.readArchiveBytes(),
      source.bytes.byteLength
    )
    const downloadBytes = snapshotPlainBytes(
      read.artifactDownload.readArchiveBytes(),
      source.bytes.byteLength
    )
    if (
      readBytes === null ||
      downloadBytes === null ||
      !sameBytes(readBytes, source.bytes) ||
      !sameBytes(downloadBytes, source.bytes) ||
      !sameCanonicalData(
        archiveProjection(read.validatedArchive),
        archiveProjection(freshArchive)
      ) ||
      read.validatedArchive.members.length !== freshArchive.members.length
    ) {
      return false
    }
    for (let index = 0; index < freshArchive.members.length; index += 1) {
      const supplied = read.validatedArchive.members[index]
      const expected = freshArchive.members[index]
      if (
        supplied === undefined ||
        expected === undefined ||
        !sameBytes(supplied.readBytes(), expected.readBytes())
      ) {
        return false
      }
    }
    return true
  } catch {
    return false
  }
}

export const buildS2SStageArtifactReadReplay = (
  input: unknown
): Either.Either<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError
> => {
  try {
    const root = exactDataRecord(input, [
      "validatedRead",
      "currentRunEvidence",
      "predecessorRecovery"
    ])
    const validatedReadInput = root?.["validatedRead"]
    if (
      root === null ||
      !isAuthenticS2SValidatedStageArtifactRead(validatedReadInput)
    ) {
      return Either.left(
        replayError(
          "INPUT_INVALID",
          "BUILD_INPUT",
          "replay builder requires one module-issued validated-read input"
        )
      )
    }
    const readRecord = exactDataRecord(validatedReadInput, [
      "_tag",
      "stage",
      "operation",
      "role",
      "producerJob",
      "artifact",
      "initialWorkflowRunObservation",
      "workflowRunObservation",
      "workflowJobsObservation",
      "artifactsObservation",
      "successfulLookupTrace",
      "readbackStartRunObservation",
      "artifactRequeryObservation",
      "artifactDownload",
      "readbackFinalRunObservation",
      "artifactEvidence",
      "validatedArchive",
      "permitEvidence",
      "readArchiveBytes"
    ])
    if (
      readRecord === null ||
      readRecord["_tag"] !== "ValidatedStageArtifactRead"
    ) {
      return Either.left(
        replayError(
          "INPUT_INVALID",
          "BUILD_INPUT",
          "replay builder requires one exact validated-read input"
        )
      )
    }
    const current =
      validateS2SCurrentRunStageEvidenceForArtifactReplay(
        root["currentRunEvidence"]
      )
    if (Either.isLeft(current)) return Either.left(current.left)
    const read = validatedReadInput
    if (
      read.stage !== current.right.stage ||
      (read.role !== "REGISTRATION" && read.role !== "CANDIDATE") ||
      s2sArtifactReadContract(read.stage, read.operation)?.artifactRole !==
        read.role
    ) {
      return Either.left(
        replayError(
          "READ_IDENTITY_MISMATCH",
          "BUILD_INPUT",
          "validated read does not belong to the current stage contract"
        )
      )
    }
    const source = snapshotSourceArchiveFromRecovery(
      root["predecessorRecovery"],
      current.right,
      read.role
    )
    if (Either.isLeft(source)) return Either.left(source.left)
    const policy = expectedSourceReference(read.role)
    const freshArchive = validateS2SArtifactZip(source.right.bytes, {
      expectedArchiveSha256: S2SSha256Schema.make(
        source.right.reference.raw_sha256
      ),
      expectedArchiveByteLength: source.right.reference.byte_length,
      expectedMembers: policy.expectedMembers,
      maximumArchiveBytes: policy.maximumArchiveBytes,
      maximumExpandedBytes: policy.maximumArchiveBytes
    })
    if (
      Either.isLeft(freshArchive) ||
      (Either.isRight(freshArchive) &&
        !inputArchiveSurfacesMatch(read, source.right, freshArchive.right))
    ) {
      return Either.left(
        replayError(
          "ARCHIVE_REPLAY_INVALID",
          "BUILD_ARCHIVE",
          Either.isLeft(freshArchive)
            ? `source archive rejected: ${freshArchive.left.reason}`
            : "validated-read archive surfaces differ from predecessor bytes"
        )
      )
    }

    const trace = read.successfulLookupTrace
    const expectedCount = s2sStageArtifactReadReplayObservationCount(
      trace.successfulAttemptOrdinal
    )
    if (
      trace.schemaVersion !==
        S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION ||
      trace.attempts.length !== trace.successfulAttemptOrdinal ||
      trace.attempts.some(
        (attempt, index) =>
          attempt.ordinal !== index + 1 ||
          attempt.classification !==
            (index + 1 === trace.successfulAttemptOrdinal
              ? "ARTIFACT_OBSERVED"
              : "ARTIFACT_NOT_OBSERVED")
      ) ||
      trace.initialWorkflowRunObservation.receipt.receiptSha256 !==
        read.initialWorkflowRunObservation.receipt.receiptSha256 ||
      trace.workflowJobsObservation.receipt.receiptSha256 !==
        read.workflowJobsObservation.receipt.receiptSha256 ||
      trace.attempts.at(-1)?.artifactsObservation.receipt.receiptSha256 !==
        read.artifactsObservation.receipt.receiptSha256 ||
      trace.attempts.at(-1)?.workflowRunObservation.receipt.receiptSha256 !==
        read.workflowRunObservation.receipt.receiptSha256
    ) {
      return Either.left(
        replayError(
          "POLL_TOPOLOGY_INVALID",
          "BUILD_LOOKUP_TRACE",
          "successful lookup trace does not exactly bind the validated read"
        )
      )
    }
    const buildObservations: Array<BuildObservation> = [
      {
        phase: "LOOKUP_RUN_START",
        observation: trace.initialWorkflowRunObservation
      },
      { phase: "LOOKUP_JOBS", observation: trace.workflowJobsObservation }
    ]
    for (const attempt of trace.attempts) {
      buildObservations.push(
        {
          phase: `LOOKUP_ARTIFACTS_${attempt.ordinal}` as ExpectedObservation["phase"],
          observation: attempt.artifactsObservation
        },
        {
          phase: `LOOKUP_RUN_END_${attempt.ordinal}` as ExpectedObservation["phase"],
          observation: attempt.workflowRunObservation
        }
      )
    }
    buildObservations.push(
      {
        phase: "READBACK_RUN_START",
        observation: read.readbackStartRunObservation
      },
      {
        phase: "READBACK_ARTIFACT",
        observation: read.artifactRequeryObservation
      },
      {
        phase: "READBACK_RUN_END",
        observation: read.readbackFinalRunObservation
      }
    )
    if (buildObservations.length !== expectedCount) {
      return Either.left(
        replayError(
          "POLL_TOPOLOGY_INVALID",
          "BUILD_OBSERVATIONS",
          "builder observation tuple has an impossible length"
        )
      )
    }
    const descriptors: Array<
      S2SStageArtifactReadReplayManifest["observations"][number]
    > = []
    const rawBodies: Array<Uint8Array> = []
    let offset = 0
    for (let index = 0; index < buildObservations.length; index += 1) {
      const buildObservation = buildObservations[index]
      if (buildObservation === undefined) {
        throw new Error("build observation disappeared")
      }
      const snapshot = snapshotBuildObservation(
        buildObservation,
        index + 1,
        offset
      )
      if (Either.isLeft(snapshot)) return Either.left(snapshot.left)
      descriptors.push(snapshot.right.descriptor)
      rawBodies.push(snapshot.right.bytes)
      offset += snapshot.right.bytes.byteLength
    }
    const observationBlob = concatenateObservationBytes(
      rawBodies,
      s2sStageArtifactReadReplayRawBodyMaximumBytes(
        trace.successfulAttemptOrdinal
      )
    )
    if (observationBlob === null) {
      return Either.left(
        replayError(
          "BYTE_BUDGET_EXCEEDED",
          "BUILD_OBSERVATIONS",
          "raw observation concatenation exceeds the ordinal-specific cap"
        )
      )
    }
    const identity: S2SStageArtifactPermitIdentity = Object.freeze({
      workflowRunId: current.right.workflowRunId,
      workflowRunAttempt: 1,
      registrationCommitB: current.right.registrationCommitB,
      workflowApiPath: current.right.workflowApiPath,
      workflowRunCreatedAt: current.right.workflowRunCreatedAt,
      workflowRunCreatedAtUnixSeconds:
        current.right.workflowRunCreatedAtUnixSeconds,
      stage: current.right.stage,
      currentJobDatabaseId: current.right.currentJobDatabaseId,
      predecessorJobDatabaseIds: Object.freeze([
        ...current.right.predecessorJobDatabaseIds
      ])
    })
    const download = validateS2SGitHubArtifactDownload(
      Object.freeze({
        receipt: read.artifactDownload.receipt,
        readArchiveBytes: () => Uint8Array.from(source.right.bytes)
      }),
      read.artifact.id,
      policy.maximumArchiveBytes
    )
    if (Either.isLeft(download)) {
      return Either.left(
        replayError(
          "ARCHIVE_REPLAY_INVALID",
          "BUILD_DOWNLOAD",
          `download receipt rejected source bytes: ${download.left.reason}`
        )
      )
    }
    const provisional = {
      schema_version: S2S_STAGE_ARTIFACT_READ_REPLAY_SCHEMA_VERSION,
      representation: S2S_STAGE_ARTIFACT_READ_REPLAY_REPRESENTATION,
      experiment_id: S2S_CONFIRMATORY_EXPERIMENT_ID,
      lookup_trace_schema_version:
        S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION,
      source_commit_a: current.right.sourceCommitA,
      current_run_evidence_receipt_sha256: current.right.receiptSha256,
      identity,
      operation: read.operation,
      role: read.role,
      producer_job_id: read.producerJob.id,
      producer_job_name: policy.producerJobName,
      artifact_id: read.artifact.id,
      artifact_name: policy.artifactName,
      artifact_byte_length: read.artifact.sizeInBytes,
      artifact_sha256: read.artifact.digestSha256,
      successful_attempt_ordinal: trace.successfulAttemptOrdinal,
      observation_count: expectedCount,
      observation_blob_byte_length: observationBlob.byteLength,
      observation_blob_sha256: S2SSha256Schema.make(
        rawS2SFileSha256(observationBlob)
      ),
      observations: Object.freeze(descriptors),
      download_receipt: structuredClone(download.right.receipt),
      artifact_evidence: structuredClone(read.artifactEvidence),
      archive_reference: source.right.reference,
      archive_validation: archiveProjection(freshArchive.right),
      permit_evidence: structuredClone(read.permitEvidence),
      candidate_fingerprint_sha256:
        read.role === "CANDIDATE"
          ? candidateFingerprint(
              {
                artifact_id: read.artifact.id,
                artifact_name: policy.artifactName,
                artifact_byte_length: read.artifact.sizeInBytes,
                artifact_sha256: S2SSha256Schema.make(
                  read.artifact.digestSha256
                ),
                role: read.role
              },
              download.right.receipt,
              freshArchive.right
            )
          : null
    }
    const receipt = canonicalS2SControlSha256(provisional)
    if (Either.isLeft(receipt)) {
      return Either.left(
        replayError(
          "MANIFEST_INVALID",
          "BUILD_MANIFEST",
          "replay manifest core is not canonical"
        )
      )
    }
    const manifestCandidate = Object.freeze({
      ...provisional,
      replay_receipt_sha256: S2SSha256Schema.make(receipt.right)
    })
    const manifest = Schema.decodeUnknownEither(ReplayManifestSchema, {
      onExcessProperty: "error"
    })(manifestCandidate)
    if (Either.isLeft(manifest)) {
      return Either.left(
        replayError(
          "MANIFEST_INVALID",
          "BUILD_MANIFEST",
          "built replay manifest violates the exact schema"
        )
      )
    }
    const manifestBytes = canonicalS2SControlJsonBytes(manifest.right)
    if (
      Either.isLeft(manifestBytes) ||
      manifestBytes.right.byteLength >
        S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES
    ) {
      return Either.left(
        replayError(
          "BYTE_BUDGET_EXCEEDED",
          "BUILD_MANIFEST",
          "canonical replay manifest exceeds its fixed cap"
        )
      )
    }
    const zip = buildS2SStoredZip([
      {
        name: S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME,
        bytes: manifestBytes.right
      },
      {
        name: S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME,
        bytes: observationBlob
      }
    ])
    if (
      Either.isLeft(zip) ||
      (Either.isRight(zip) &&
        zip.right.archiveByteLength >
          S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES)
    ) {
      return Either.left(
        replayError(
          "CARRIER_INVALID",
          "BUILD_CARRIER",
          Either.isLeft(zip)
            ? `stored ZIP build failed: ${zip.left.reason}`
            : "stored ZIP exceeds its exact derived maximum"
        )
      )
    }
    const decodedCarrier = decodeReplayCarrier(zip.right.readArchiveBytes())
    return Either.isLeft(decodedCarrier)
      ? Either.left(decodedCarrier.left)
      : validateDecodedReplayWithPreparedSource(
          decodedCarrier.right,
          current.right,
          source.right
        )
  } catch (error) {
    return Either.left(
      replayError(
        "INPUT_INVALID",
        "BUILD_INPUT",
        error instanceof Error ? error.message : "replay build failed closed"
      )
    )
  }
}

export const buildS2SStageArtifactReadReplayEffect = (
  input: unknown
): Effect.Effect<
  S2SStageArtifactReadReplaySnapshot,
  S2SStageArtifactReadReplayError
> => suspendEither(() => buildS2SStageArtifactReadReplay(input))
