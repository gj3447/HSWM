import { types as nodeTypes } from "node:util"

import { Data, Effect, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2SArtifactEvidenceSchema,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_POLICY,
  S2SGitCommitShaSchema,
  S2SSha256Schema,
  type S2SArtifactEvidence,
  type S2SSha256
} from "./s2s-confirmatory.js"
import { parseS2SJsonBytes } from "./s2s-json.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
  S2S_GITHUB_JSON_MAX_BYTES,
  S2S_GITHUB_REPOSITORY,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  validateS2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownloadReceipt,
  type S2SGitHubArtifactProjection,
  type S2SGitHubArtifactsProjection,
  type S2SGitHubObservation,
  type S2SGitHubObservationError,
  type S2SGitHubProjection,
  type S2SGitHubWorkflowJobProjection,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection
} from "./s2s-live-github.js"
import type { S2SCurrentRunStageEvidence } from "./s2s-run-authority.js"
import {
  validateS2SCurrentRunStageEvidence
} from "./s2s-stage-artifact-read-replay.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "./s2s-stage-artifact-spec.js"
import {
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
  S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
  S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION,
  S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
  S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES,
  s2sStageUploadPostconditionObservationCount,
  s2sStageUploadPostconditionRawBodyMaximumBytes
} from "./s2s-stage-upload-postcondition-contract.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_EVENT,
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_NAME,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"
import {
  buildS2SStoredZip,
  validateS2SArtifactZip,
  type S2SValidatedArtifactZip
} from "./s2s-zip.js"

const MEBIBYTE = 1_048_576
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GITHUB_REQUEST_ID_PATTERN = /^[\u0021-\u007e]{1,256}$/
const HTTP_ETAG_PATTERN = /^(?:W\/)?"[\u0021\u0023-\u007e]{0,508}"$/
const RFC3339_UTC_SECONDS_PATTERN =
  /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/

export const S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-stage-upload-assertion-permit-evidence/v1" as const
export const S2S_STAGE_UPLOAD_ASSERTION_OPERATION =
  "ASSERT_AND_RECOVER_CURRENT_STAGE_ARTIFACT" as const

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
const LedgerPhaseSchema = Schema.Literal(
  "CURRENT_RUN_RUN_START",
  "CURRENT_RUN_JOBS",
  "CURRENT_RUN_RUNS_FOR_HEAD",
  "CURRENT_RUN_RUN_END",
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
)

const CompactObservationSchema = Schema.Struct({
  ordinal: Schema.Number.pipe(Schema.int(), Schema.between(1, 11)),
  phase: ObservationPhaseSchema,
  kind: ObservationKindSchema,
  offset: NonNegativeSafeIntegerSchema.pipe(
    Schema.between(0, S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES)
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
  stage: StageSchema,
  currentJobDatabaseId: PositiveSafeIntegerSchema,
  predecessorJobDatabaseIds: Schema.Array(PositiveSafeIntegerSchema).pipe(
    Schema.maxItems(2)
  )
})

const AssertionLedgerEntrySchema = Schema.Struct({
  operation: Schema.Literal(
    "CURRENT_RUN_AUTHORITY",
    S2S_STAGE_UPLOAD_ASSERTION_OPERATION
  ),
  phase: LedgerPhaseSchema,
  githubRequestId: RequestIdSchema,
  receiptSha256: S2SSha256Schema,
  observedAtUnixSeconds: NonNegativeSafeIntegerSchema
})

const AssertionPermitEvidenceSchema = Schema.Struct({
  schemaVersion: Schema.Literal(
    S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION
  ),
  authorityScope: Schema.Literal(
    "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
    "TEST_ONLY_NON_AUTHORIZING"
  ),
  authorizationClaimed: Schema.Boolean,
  oneUseClaim: Schema.Literal(
    "ONE_USE_PER_GENUINE_AUTHORITY_AND_PROCESS_IDENTITY_SLOT",
    "MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE"
  ),
  crossWorkerReplayPreventionClaimed: Schema.Literal(false),
  crossModuleCopyReplayPreventionClaimed: Schema.Literal(false),
  crossProcessReplayPreventionClaimed: Schema.Literal(false),
  durableReplayPreventionClaimed: Schema.Literal(false),
  identity: PermitIdentitySchema,
  operation: Schema.Literal(S2S_STAGE_UPLOAD_ASSERTION_OPERATION),
  ledgerCapacity: Schema.Literal(16),
  ledgerEntries: Schema.Array(AssertionLedgerEntrySchema).pipe(
    Schema.minItems(12),
    Schema.maxItems(16)
  ),
  receiptSha256: S2SSha256Schema
})

const DownloadReceiptSchema = Schema.Struct({
  schemaVersion: Schema.Literal(
    S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION
  ),
  apiVersion: Schema.Literal(S2S_GITHUB_API_VERSION),
  repository: Schema.Literal(S2S_GITHUB_REPOSITORY),
  artifactId: PositiveSafeIntegerSchema,
  endpointPathAndQuery: Schema.String,
  downloadedAtUnixSeconds: NonNegativeSafeIntegerSchema,
  redirectHttpStatus: Schema.Literal(302),
  redirectGitHubRequestId: RequestIdSchema,
  redirectGitHubApiVersionSelected: Schema.Literal(S2S_GITHUB_API_VERSION),
  redirectResponseEtag: Schema.NullOr(EtagSchema),
  redirectUrlSha256: S2SSha256Schema,
  redirectOrigin: Schema.String,
  archiveHttpStatus: Schema.Literal(200),
  archiveMediaType: Schema.Literal(
    "application/octet-stream",
    "application/zip",
    "binary/octet-stream"
  ),
  archiveResponseEtag: Schema.NullOr(EtagSchema),
  archiveByteLength: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 64 * MEBIBYTE)
  ),
  downloadedArchiveSha256: S2SSha256Schema,
  receiptSha256: S2SSha256Schema
})

const ArchiveMemberBase = {
  byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 60 * MEBIBYTE)
  ),
  crc32: NonNegativeSafeIntegerSchema.pipe(
    Schema.between(0, 0xffff_ffff)
  ),
  raw_bytes_sha256: S2SSha256Schema
} as const

const PreparedMemberBase = {
  byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 60 * MEBIBYTE)
  ),
  raw_bytes_sha256: S2SSha256Schema
} as const

const archiveMember = <Name extends string>(name: Name) =>
  Schema.Struct({ name: Schema.Literal(name), ...ArchiveMemberBase })
const preparedMember = <Name extends string>(name: Name) =>
  Schema.Struct({ name: Schema.Literal(name), ...PreparedMemberBase })

const ControlArchiveMemberSchema = archiveMember("control_receipt.json")
const CandidateArchiveMemberSchema = archiveMember("numeric_candidate.json")
const AdjudicationArchiveMemberSchema = archiveMember(
  "numeric_adjudication.json"
)
const ControlPreparedMemberSchema = preparedMember("control_receipt.json")
const CandidatePreparedMemberSchema = preparedMember("numeric_candidate.json")
const AdjudicationPreparedMemberSchema = preparedMember(
  "numeric_adjudication.json"
)

const archiveProjection = <Members extends Schema.Schema.Any>(
  members: Members
) =>
  Schema.Struct({
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
    members
  })

const commonManifestFields = {
  schema_version: Schema.Literal(
    S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION
  ),
  representation: Schema.Literal(
    S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION
  ),
  experiment_id: Schema.Literal(S2S_CONFIRMATORY_EXPERIMENT_ID),
  classification: Schema.Literal(
    "PRODUCTION_INTENDED_STAGE_UPLOAD_POSTCONDITION"
  ),
  authority_scope: Schema.Literal("PROCESS_LOCAL_STAGE_ENTRY"),
  publication_claim: Schema.Literal(
    "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
  ),
  publisher_return_used_as_evidence: Schema.Literal(false),
  historical_uniqueness_claimed: Schema.Literal(false),
  external_exactly_once_claimed: Schema.Literal(false),
  cross_worker_replay_prevention_claimed: Schema.Literal(false),
  cross_module_copy_replay_prevention_claimed: Schema.Literal(false),
  cross_process_replay_prevention_claimed: Schema.Literal(false),
  durable_replay_prevention_claimed: Schema.Literal(false),
  source_commit_a: S2SGitCommitShaSchema,
  current_run_evidence_receipt_sha256: S2SSha256Schema,
  assertion_permit_evidence: AssertionPermitEvidenceSchema,
  producer_job_id: PositiveSafeIntegerSchema,
  artifact_id: PositiveSafeIntegerSchema,
  artifact_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, 64 * MEBIBYTE)
  ),
  artifact_sha256: S2SSha256Schema,
  successful_attempt_ordinal: Schema.Literal(1, 2, 3),
  observation_count: Schema.Literal(7, 9, 11),
  observation_blob_byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES)
  ),
  observation_blob_sha256: S2SSha256Schema,
  observations: Schema.Array(CompactObservationSchema).pipe(
    Schema.minItems(7),
    Schema.maxItems(11)
  ),
  download_receipt: DownloadReceiptSchema,
  artifact_evidence: S2SArtifactEvidenceSchema,
  archive_members_equal_prepared_members: Schema.Literal(true),
  postcondition_receipt_sha256: S2SSha256Schema
} as const

const registerIdentity = Schema.Struct({
  ...PermitIdentitySchema.fields,
  stage: Schema.Literal("REGISTER"),
  predecessorJobDatabaseIds: Schema.Tuple()
})
const confirmIdentity = Schema.Struct({
  ...PermitIdentitySchema.fields,
  stage: Schema.Literal("CONFIRM"),
  predecessorJobDatabaseIds: Schema.Tuple(PositiveSafeIntegerSchema)
})
const adjudicateIdentity = Schema.Struct({
  ...PermitIdentitySchema.fields,
  stage: Schema.Literal("ADJUDICATE"),
  predecessorJobDatabaseIds: Schema.Tuple(
    PositiveSafeIntegerSchema,
    PositiveSafeIntegerSchema
  )
})

const RegisterManifestSchema = Schema.Struct({
  ...commonManifestFields,
  identity: registerIdentity,
  stage: Schema.Literal("REGISTER"),
  role: Schema.Literal("REGISTRATION"),
  producer_job_name: Schema.Literal("register"),
  artifact_name: Schema.Literal("s2s-registration"),
  archive_reference: Schema.Struct({
    logical_name: Schema.Literal("upload/registration_archive.zip"),
    role: Schema.Literal("REGISTRATION_UPLOAD_ARCHIVE"),
    schema_version: Schema.Literal(
      "hswm-swm0w-s2s-registration-carrier/v1"
    ),
    media_type: Schema.Literal("application/zip"),
    byte_length: PositiveSafeIntegerSchema.pipe(
      Schema.between(1, 4 * MEBIBYTE)
    ),
    raw_sha256: S2SSha256Schema
  }),
  archive_validation: archiveProjection(
    Schema.Tuple(ControlArchiveMemberSchema)
  ),
  prepared_members: Schema.Tuple(ControlPreparedMemberSchema)
})

const ConfirmManifestSchema = Schema.Struct({
  ...commonManifestFields,
  identity: confirmIdentity,
  stage: Schema.Literal("CONFIRM"),
  role: Schema.Literal("CANDIDATE"),
  producer_job_name: Schema.Literal("confirm"),
  artifact_name: Schema.Literal("s2s-candidate"),
  archive_reference: Schema.Struct({
    logical_name: Schema.Literal("upload/candidate_archive.zip"),
    role: Schema.Literal("CANDIDATE_UPLOAD_ARCHIVE"),
    schema_version: Schema.Literal("hswm-swm0w-s2s-candidate-carrier/v1"),
    media_type: Schema.Literal("application/zip"),
    byte_length: PositiveSafeIntegerSchema.pipe(
      Schema.between(1, 64 * MEBIBYTE)
    ),
    raw_sha256: S2SSha256Schema
  }),
  archive_validation: archiveProjection(
    Schema.Tuple(ControlArchiveMemberSchema, CandidateArchiveMemberSchema)
  ),
  prepared_members: Schema.Tuple(
    ControlPreparedMemberSchema,
    CandidatePreparedMemberSchema
  )
})

const AdjudicateManifestSchema = Schema.Struct({
  ...commonManifestFields,
  identity: adjudicateIdentity,
  stage: Schema.Literal("ADJUDICATE"),
  role: Schema.Literal("ADJUDICATION"),
  producer_job_name: Schema.Literal("adjudicate"),
  artifact_name: Schema.Literal("s2s-adjudication"),
  archive_reference: Schema.Struct({
    logical_name: Schema.Literal("upload/adjudication_archive.zip"),
    role: Schema.Literal("ADJUDICATION_UPLOAD_ARCHIVE"),
    schema_version: Schema.Literal(
      "hswm-swm0w-s2s-adjudication-carrier/v1"
    ),
    media_type: Schema.Literal("application/zip"),
    byte_length: PositiveSafeIntegerSchema.pipe(
      Schema.between(1, 4 * MEBIBYTE)
    ),
    raw_sha256: S2SSha256Schema
  }),
  archive_validation: archiveProjection(
    Schema.Tuple(ControlArchiveMemberSchema, AdjudicationArchiveMemberSchema)
  ),
  prepared_members: Schema.Tuple(
    ControlPreparedMemberSchema,
    AdjudicationPreparedMemberSchema
  )
})

const StageUploadPostconditionManifestSchema = Schema.Union(
  RegisterManifestSchema,
  ConfirmManifestSchema,
  AdjudicateManifestSchema
)

export type S2SStageUploadAssertionPermitEvidence = Schema.Schema.Type<
  typeof AssertionPermitEvidenceSchema
>
export type S2SStageUploadPostconditionManifest = Schema.Schema.Type<
  typeof StageUploadPostconditionManifestSchema
>
export type S2SStageUploadObservationPhase = Schema.Schema.Type<
  typeof ObservationPhaseSchema
>

export interface S2SStageUploadPreparedMember {
  readonly name:
    | "control_receipt.json"
    | "numeric_candidate.json"
    | "numeric_adjudication.json"
  readonly byteLength: number
  readonly rawBytesSha256: string
  readonly readBytes: () => Uint8Array
}

export interface S2SStageUploadBuildObservation {
  readonly phase: S2SStageUploadObservationPhase
  readonly observation: S2SGitHubObservation
}

export interface S2SStageUploadPostconditionReconstruction {
  readonly _tag: "ValidatedNonAuthorizingStageUploadPostcondition"
  readonly manifest: S2SStageUploadPostconditionManifest
  readonly manifestRawSha256: S2SSha256
  readonly observations: ReadonlyArray<S2SGitHubObservation>
  readonly archiveValidation: S2SValidatedArtifactZip
  readonly artifactEvidence: S2SArtifactEvidence
  readonly assertionPermitEvidence: S2SStageUploadAssertionPermitEvidence
  readonly readManifestBytes: () => Uint8Array
  readonly readObservationBlob: () => Uint8Array
  readonly readArchiveBytes: () => Uint8Array
}

export interface S2SStageUploadPostconditionSnapshot
  extends S2SStageUploadPostconditionReconstruction {
  readonly carrierRawSha256: S2SSha256
  readonly carrierByteLength: number
  readonly readCarrierBytes: () => Uint8Array
}

export class S2SStageUploadPostconditionError extends Data.TaggedError(
  "S2SStageUploadPostconditionError"
)<{
  readonly reason:
    | "ARCHIVE_REFERENCE_INVALID"
    | "ARCHIVE_REPLAY_INVALID"
    | "ARTIFACT_BINDING_MISMATCH"
    | "BYTE_BUDGET_EXCEEDED"
    | "CARRIER_INVALID"
    | "CURRENT_RUN_BINDING_MISMATCH"
    | "DOWNLOAD_REPLAY_INVALID"
    | "INPUT_INVALID"
    | "MANIFEST_INVALID"
    | "MANIFEST_SELF_HASH_MISMATCH"
    | "OBSERVATION_REPLAY_INVALID"
    | "OBSERVATION_TOPOLOGY_INVALID"
    | "PERMIT_BINDING_MISMATCH"
    | "PREPARED_MEMBER_MISMATCH"
    | "STAGE_IDENTITY_MISMATCH"
    | "TEST_ONLY_GOLDEN_REJECTED"
  readonly phase: string
  readonly detail: string
}> {}

const postconditionError = (
  reason: S2SStageUploadPostconditionError["reason"],
  phase: string,
  detail: string
): S2SStageUploadPostconditionError =>
  new S2SStageUploadPostconditionError({ reason, phase, detail })

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
    const a = canonicalS2SControlSha256(left)
    const b = canonicalS2SControlSha256(right)
    return Either.isRight(a) && Either.isRight(b) && a.right === b.right
  } catch {
    return false
  }
}

/** Compare hostile input against a trusted bounded projection shape. */
const exactCanonicalDataEqual = (input: unknown, expected: unknown): boolean => {
  try {
    if (expected === null || typeof expected !== "object") {
      return Object.is(input, expected)
    }
    if (Array.isArray(expected)) {
      if (
        !Array.isArray(input) ||
        nodeTypes.isProxy(input) ||
        Object.getPrototypeOf(input) !== Array.prototype
      ) {
        return false
      }
      const keys = Reflect.ownKeys(input)
      if (
        keys.length !== expected.length + 1 ||
        keys.some((key) => typeof key !== "string")
      ) {
        return false
      }
      const length = Object.getOwnPropertyDescriptor(input, "length")
      if (
        length === undefined ||
        !("value" in length) ||
        length.value !== expected.length
      ) {
        return false
      }
      for (let index = 0; index < expected.length; index += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
        if (
          descriptor === undefined ||
          descriptor.enumerable !== true ||
          !("value" in descriptor) ||
          !exactCanonicalDataEqual(descriptor.value, expected[index])
        ) {
          return false
        }
      }
      return true
    }
    if (
      input === null ||
      typeof input !== "object" ||
      Array.isArray(input) ||
      nodeTypes.isProxy(input)
    ) {
      return false
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) return false
    const inputKeys = Reflect.ownKeys(input)
    const expectedKeys = Reflect.ownKeys(expected)
    if (
      inputKeys.length !== expectedKeys.length ||
      inputKeys.some((key) => typeof key !== "string") ||
      expectedKeys.some((key) => typeof key !== "string")
    ) {
      return false
    }
    const actual = inputKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
    const wanted = expectedKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
    if (!actual.every((key, index) => key === wanted[index])) return false
    for (const key of wanted) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      const trustedDescriptor = Object.getOwnPropertyDescriptor(expected, key)
      if (
        descriptor === undefined ||
        trustedDescriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor) ||
        !("value" in trustedDescriptor) ||
        !exactCanonicalDataEqual(
          descriptor.value,
          trustedDescriptor.value
        )
      ) {
        return false
      }
    }
    return true
  } catch {
    return false
  }
}

const deepFreezeCanonical = <A>(input: A): A => {
  if (input !== null && typeof input === "object") {
    for (const key of Object.keys(input)) {
      deepFreezeCanonical((input as Record<string, unknown>)[key])
    }
    Object.freeze(input)
  }
  return input
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
    const actual = ownKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
    const expected = [...keys].sort()
    if (!actual.every((key, index) => key === expected[index])) return null
    const output: Record<string, unknown> = Object.create(null)
    for (const key of actual) {
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
    const copy = Uint8Array.from(input)
    return copy.byteLength === input.byteLength ? copy : null
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

const snapshotCanonicalValue = (
  input: unknown,
  ancestors: ReadonlySet<object> = new Set()
): unknown | null => {
  if (
    input === null ||
    typeof input === "boolean" ||
    typeof input === "string"
  ) {
    return input
  }
  if (typeof input === "number") {
    return Number.isSafeInteger(input) && !Object.is(input, -0) ? input : null
  }
  if (
    typeof input !== "object" ||
    nodeTypes.isProxy(input) ||
    ancestors.has(input)
  ) {
    return null
  }
  const nextAncestors = new Set(ancestors)
  nextAncestors.add(input)
  if (Array.isArray(input)) {
    const values = snapshotDenseArray(input, 64, 0)
    if (values === null) return null
    const output: Array<unknown> = []
    for (const value of values) {
      const snapshot = snapshotCanonicalValue(value, nextAncestors)
      if (snapshot === null && value !== null) return null
      output.push(snapshot)
    }
    return Object.freeze(output)
  }
  const prototype = Object.getPrototypeOf(input)
  if (prototype !== Object.prototype && prototype !== null) return null
  const ownKeys = Reflect.ownKeys(input)
  if (ownKeys.some((key) => typeof key !== "string")) return null
  const output: Record<string, unknown> = Object.create(null)
  for (const key of ownKeys.filter(
    (value): value is string => typeof value === "string"
  )) {
    const descriptor = Object.getOwnPropertyDescriptor(input, key)
    if (
      descriptor === undefined ||
      descriptor.enumerable !== true ||
      !("value" in descriptor)
    ) {
      return null
    }
    const snapshot = snapshotCanonicalValue(descriptor.value, nextAncestors)
    if (snapshot === null && descriptor.value !== null) return null
    output[key] = snapshot
  }
  return Object.freeze(output)
}

interface ExpectedObservation {
  readonly phase: S2SStageUploadObservationPhase
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
        phase: `LOOKUP_ARTIFACTS_${ordinal}` as S2SStageUploadObservationPhase,
        kind: "RUN_ARTIFACTS"
      },
      {
        phase: `LOOKUP_RUN_END_${ordinal}` as S2SStageUploadObservationPhase,
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

const validateCurrentRunEvidence = (
  input: unknown
): Either.Either<
  S2SCurrentRunStageEvidence,
  S2SStageUploadPostconditionError
> => {
  const validated = validateS2SCurrentRunStageEvidence(input)
  return Either.isLeft(validated)
    ? Either.left(
        postconditionError(
          "CURRENT_RUN_BINDING_MISMATCH",
          "CURRENT_RUN_EVIDENCE",
          validated.left.detail
        )
      )
    : Either.right(validated.right)
}

const identityFromCurrent = (
  current: S2SCurrentRunStageEvidence
): Schema.Schema.Type<typeof PermitIdentitySchema> =>
  deepFreezeCanonical(PermitIdentitySchema.make({
    workflowRunId: current.workflowRunId,
    workflowRunAttempt: 1 as const,
    registrationCommitB: S2SGitCommitShaSchema.make(current.registrationCommitB),
    workflowApiPath:
      current.workflowApiPath === S2S_CONFIRMATORY_WORKFLOW_PATH
        ? S2S_CONFIRMATORY_WORKFLOW_PATH
        : `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`,
    workflowRunCreatedAt: current.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds: current.workflowRunCreatedAtUnixSeconds,
    stage: current.stage,
    currentJobDatabaseId: current.currentJobDatabaseId,
    predecessorJobDatabaseIds: [...current.predecessorJobDatabaseIds]
  }))

interface PreparedMemberSnapshot extends S2SStageUploadPreparedMember {
  readonly bytes: Uint8Array
}

const snapshotPreparedMembers = (
  input: unknown,
  stage: S2SConfirmatoryJobStage
): Either.Either<
  ReadonlyArray<PreparedMemberSnapshot>,
  S2SStageUploadPostconditionError
> => {
  const spec = S2S_STAGE_ARTIFACT_SPECS[stage]
  const values = snapshotDenseArray(
    input,
    spec.expectedMembers.length,
    spec.expectedMembers.length
  )
  if (values === null || values.length !== spec.expectedMembers.length) {
    return Either.left(
      postconditionError(
        "PREPARED_MEMBER_MISMATCH",
        "PREPARED_MEMBERS",
        "prepared members must be one exact stage-owned dense tuple"
      )
    )
  }
  const output: Array<PreparedMemberSnapshot> = []
  for (let index = 0; index < values.length; index += 1) {
    const expected = spec.expectedMembers[index]
    const record = exactDataRecord(values[index], [
      "byteLength",
      "name",
      "rawBytesSha256",
      "readBytes"
    ])
    if (
      expected === undefined ||
      record === null ||
      record["name"] !== expected.name ||
      typeof record["byteLength"] !== "number" ||
      !Number.isSafeInteger(record["byteLength"]) ||
      record["byteLength"] < 1 ||
      record["byteLength"] > expected.maximumBytes ||
      typeof record["rawBytesSha256"] !== "string" ||
      !SHA256_PATTERN.test(record["rawBytesSha256"]) ||
      typeof record["readBytes"] !== "function"
    ) {
      return Either.left(
        postconditionError(
          "PREPARED_MEMBER_MISMATCH",
          `PREPARED_MEMBERS_${index}`,
          "prepared member metadata differs from the fixed stage roster"
        )
      )
    }
    let bytes: Uint8Array | null = null
    try {
      bytes = snapshotPlainBytes(
        Reflect.apply(record["readBytes"], undefined, []),
        expected.maximumBytes
      )
    } catch {
      bytes = null
    }
    if (
      bytes === null ||
      bytes.byteLength !== record["byteLength"] ||
      rawS2SFileSha256(bytes) !== record["rawBytesSha256"]
    ) {
      return Either.left(
        postconditionError(
          "PREPARED_MEMBER_MISMATCH",
          `PREPARED_MEMBERS_${index}`,
          "prepared member bytes differ from their declared length or hash"
        )
      )
    }
    const memberBytes = Uint8Array.from(bytes)
    output.push(
      Object.freeze({
        name: expected.name as PreparedMemberSnapshot["name"],
        byteLength: memberBytes.byteLength,
        rawBytesSha256: record["rawBytesSha256"],
        bytes: memberBytes,
        readBytes: (): Uint8Array => Uint8Array.from(memberBytes)
      })
    )
  }
  return Either.right(Object.freeze(output))
}

const preparedMemberProjection = (
  members: ReadonlyArray<PreparedMemberSnapshot>
) =>
  deepFreezeCanonical(
    members.map((member) => ({
      name: member.name,
      byte_length: member.byteLength,
      raw_bytes_sha256: S2SSha256Schema.make(member.rawBytesSha256)
    }))
  )

const archiveValidationProjection = (
  archive: S2SValidatedArtifactZip
) =>
  deepFreezeCanonical({
    archive_byte_length: archive.archiveByteLength,
    archive_sha256: archive.archiveSha256,
    expanded_byte_length: archive.expandedByteLength,
    largest_member_byte_length: archive.largestMemberByteLength,
    members: archive.members.map((member) => ({
      name: member.name,
      byte_length: member.byteLength,
      crc32: member.crc32,
      raw_bytes_sha256: member.rawBytesSha256
    }))
  })

const archiveMatchesPreparedMembers = (
  archive: S2SValidatedArtifactZip,
  prepared: ReadonlyArray<PreparedMemberSnapshot>
): boolean => {
  if (archive.members.length !== prepared.length) return false
  for (let index = 0; index < archive.members.length; index += 1) {
    const actual = archive.members[index]
    const expected = prepared[index]
    if (
      actual === undefined ||
      expected === undefined ||
      actual.name !== expected.name ||
      actual.byteLength !== expected.byteLength ||
      actual.rawBytesSha256 !== expected.rawBytesSha256 ||
      !sameBytes(actual.readBytes(), expected.bytes)
    ) {
      return false
    }
  }
  return true
}

const OBSERVATION_RECEIPT_KEYS = Object.freeze([
  "apiVersion",
  "endpointPathAndQuery",
  "githubApiVersionSelected",
  "githubRequestId",
  "httpStatus",
  "kind",
  "observedAtUnixSeconds",
  "projection",
  "projectionSha256",
  "rawBodyByteLength",
  "rawBodySha256",
  "receiptSha256",
  "repository",
  "responseEtag",
  "schemaVersion"
] as const)

interface TrustedObservationMetadata {
  readonly observedAtUnixSeconds: number
  readonly githubRequestId: string
  readonly responseEtag: string
}

const trustedObservationMetadata = (
  input: unknown
): TrustedObservationMetadata | null => {
  const receipt = exactDataRecord(input, OBSERVATION_RECEIPT_KEYS)
  if (
    receipt === null ||
    typeof receipt["observedAtUnixSeconds"] !== "number" ||
    !Number.isSafeInteger(receipt["observedAtUnixSeconds"]) ||
    receipt["observedAtUnixSeconds"] < 0 ||
    typeof receipt["githubRequestId"] !== "string" ||
    !GITHUB_REQUEST_ID_PATTERN.test(receipt["githubRequestId"]) ||
    typeof receipt["responseEtag"] !== "string" ||
    !HTTP_ETAG_PATTERN.test(receipt["responseEtag"])
  ) {
    return null
  }
  return Object.freeze({
    observedAtUnixSeconds: receipt["observedAtUnixSeconds"],
    githubRequestId: receipt["githubRequestId"],
    responseEtag: receipt["responseEtag"]
  })
}

const observeRawBody = (
  kind: ExpectedObservation["kind"],
  rawBody: Uint8Array,
  workflowRunId: number,
  artifactId: number | null,
  metadata: TrustedObservationMetadata
): Either.Either<S2SGitHubObservation, S2SStageUploadPostconditionError> => {
  if (kind === "ARTIFACT" && artifactId === null) {
    return Either.left(
      postconditionError(
        "OBSERVATION_REPLAY_INVALID",
        kind,
        "artifact ID is unavailable before artifact requery reconstruction"
      )
    )
  }
  const provenance = Object.freeze({
    githubRequestId: metadata.githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: metadata.responseEtag
  })
  const observed: Either.Either<
    S2SGitHubObservation,
    S2SGitHubObservationError
  > = (() => {
    switch (kind) {
      case "WORKFLOW_RUN":
        return Either.map(
          observeS2SGitHubWorkflowRun(
            rawBody,
            workflowRunId,
            metadata.observedAtUnixSeconds,
            provenance
          ),
          (value): S2SGitHubObservation => value
        )
      case "WORKFLOW_ATTEMPT_JOBS":
        return Either.map(
          observeS2SGitHubWorkflowAttemptJobs(
            rawBody,
            workflowRunId,
            1,
            metadata.observedAtUnixSeconds,
            provenance
          ),
          (value): S2SGitHubObservation => value
        )
      case "RUN_ARTIFACTS":
        return Either.map(
          observeS2SGitHubRunArtifacts(
            rawBody,
            workflowRunId,
            metadata.observedAtUnixSeconds,
            provenance
          ),
          (value): S2SGitHubObservation => value
        )
      case "ARTIFACT":
        return Either.map(
          observeS2SGitHubArtifact(
            rawBody,
            artifactId as number,
            metadata.observedAtUnixSeconds,
            provenance
          ),
          (value): S2SGitHubObservation => value
        )
    }
  })()
  return Either.isLeft(observed)
    ? Either.left(
        postconditionError(
          "OBSERVATION_REPLAY_INVALID",
          kind,
          `raw GitHub response could not be reconstructed: ${observed.left.reason}`
        )
      )
    : Either.right(observed.right)
}

const suppliedReceiptMatchesTrusted = (
  suppliedInput: unknown,
  trusted: S2SGitHubObservation["receipt"]
): boolean => {
  const supplied = exactDataRecord(suppliedInput, OBSERVATION_RECEIPT_KEYS)
  if (supplied === null) return false
  if (!exactCanonicalDataEqual(supplied["projection"], trusted.projection)) {
    return false
  }
  const scalarKeys = OBSERVATION_RECEIPT_KEYS.filter(
    (key) => key !== "projection"
  )
  return scalarKeys.every((key) => supplied[key] === trusted[key])
}

type CompactObservationDescriptor =
  S2SStageUploadPostconditionManifest["observations"][number]

interface SnapshottedBuildObservations {
  readonly descriptors: ReadonlyArray<CompactObservationDescriptor>
  readonly observations: ReadonlyArray<S2SGitHubObservation>
  readonly blob: Uint8Array
  readonly selectedArtifact: S2SGitHubArtifactProjection
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

const snapshotBuildObservations = (
  input: unknown,
  successfulAttemptOrdinal: 1 | 2 | 3,
  current: S2SCurrentRunStageEvidence
): Either.Either<
  SnapshottedBuildObservations,
  S2SStageUploadPostconditionError
> => {
  const expected = expectedObservations(successfulAttemptOrdinal)
  const values = snapshotDenseArray(input, expected.length, expected.length)
  if (values === null || values.length !== expected.length) {
    return Either.left(
      postconditionError(
        "OBSERVATION_TOPOLOGY_INVALID",
        "BUILD_OBSERVATIONS",
        "builder requires the exact ordinal-specific observation tuple"
      )
    )
  }
  const descriptors: Array<CompactObservationDescriptor> = []
  const observations: Array<S2SGitHubObservation> = []
  const rawBodies: Array<Uint8Array> = []
  let selectedArtifact: S2SGitHubArtifactProjection | undefined
  let offset = 0
  for (let index = 0; index < values.length; index += 1) {
    const expectedEntry = expected[index]
    const entry = exactDataRecord(values[index], ["observation", "phase"])
    const wrapper = exactDataRecord(entry?.["observation"], [
      "readRawBody",
      "receipt"
    ])
    const metadata = trustedObservationMetadata(wrapper?.["receipt"])
    if (
      expectedEntry === undefined ||
      entry === null ||
      entry["phase"] !== expectedEntry.phase ||
      wrapper === null ||
      typeof wrapper["readRawBody"] !== "function" ||
      metadata === null
    ) {
      return Either.left(
        postconditionError(
          "INPUT_INVALID",
          expectedEntry?.phase ?? "BUILD_OBSERVATIONS",
          "observation input is not one exact plain trusted wrapper"
        )
      )
    }
    let rawBody: Uint8Array | null = null
    try {
      rawBody = snapshotPlainBytes(
        Reflect.apply(wrapper["readRawBody"], undefined, []),
        S2S_GITHUB_JSON_MAX_BYTES
      )
    } catch {
      rawBody = null
    }
    if (rawBody === null) {
      return Either.left(
        postconditionError(
          "BYTE_BUDGET_EXCEEDED",
          expectedEntry.phase,
          "observation raw body is not one bounded plain byte array"
        )
      )
    }
    const trusted = observeRawBody(
      expectedEntry.kind,
      rawBody,
      current.workflowRunId,
      expectedEntry.kind === "ARTIFACT" ? selectedArtifact?.id ?? null : null,
      metadata
    )
    if (Either.isLeft(trusted)) return Either.left(trusted.left)
    if (!suppliedReceiptMatchesTrusted(wrapper["receipt"], trusted.right.receipt)) {
      return Either.left(
        postconditionError(
          "OBSERVATION_REPLAY_INVALID",
          expectedEntry.phase,
          "supplied observation receipt differs from trusted reconstruction"
        )
      )
    }
    if (
      expectedEntry.phase ===
      `LOOKUP_ARTIFACTS_${successfulAttemptOrdinal}`
    ) {
      const projection = trusted.right.receipt
        .projection as S2SGitHubArtifactsProjection
      const matches = projection.artifacts.filter(
        (artifact) =>
          artifact.name === S2S_STAGE_ARTIFACT_SPECS[current.stage].artifactName
      )
      if (matches.length === 1) selectedArtifact = matches[0]
    }
    const receipt = trusted.right.receipt
    descriptors.push(
      Object.freeze({
        ordinal: index + 1,
        phase: expectedEntry.phase,
        kind: expectedEntry.kind,
        offset,
        byte_length: rawBody.byteLength,
        raw_body_sha256: S2SSha256Schema.make(receipt.rawBodySha256),
        observed_at_unix_seconds: receipt.observedAtUnixSeconds,
        github_request_id: receipt.githubRequestId,
        response_etag: receipt.responseEtag,
        projection_sha256: S2SSha256Schema.make(receipt.projectionSha256),
        receipt_sha256: S2SSha256Schema.make(receipt.receiptSha256)
      })
    )
    observations.push(trusted.right)
    rawBodies.push(rawBody)
    offset += rawBody.byteLength
  }
  if (selectedArtifact === undefined) {
    return Either.left(
      postconditionError(
        "ARTIFACT_BINDING_MISMATCH",
        "LOOKUP_SUCCESS",
        "successful lookup does not contain exactly one fixed-name artifact"
      )
    )
  }
  const blob = concatenateObservationBytes(
    rawBodies,
    s2sStageUploadPostconditionRawBodyMaximumBytes(successfulAttemptOrdinal)
  )
  return blob === null
    ? Either.left(
        postconditionError(
          "BYTE_BUDGET_EXCEEDED",
          "BUILD_OBSERVATIONS",
          "raw observation concatenation exceeds its ordinal-specific cap"
        )
      )
    : Either.right(
        Object.freeze({
          descriptors: Object.freeze(descriptors),
          observations: Object.freeze(observations),
          blob,
          selectedArtifact
        })
      )
}

interface ReplayedObservation {
  readonly phase: S2SStageUploadObservationPhase
  readonly observation: S2SGitHubObservation
}

const reconstructObservation = (
  descriptor: CompactObservationDescriptor,
  rawBody: Uint8Array,
  manifest: S2SStageUploadPostconditionManifest
): Either.Either<S2SGitHubObservation, S2SStageUploadPostconditionError> => {
  const observed = observeRawBody(
    descriptor.kind,
    rawBody,
    manifest.identity.workflowRunId,
    descriptor.kind === "ARTIFACT" ? manifest.artifact_id : null,
    Object.freeze({
      observedAtUnixSeconds: descriptor.observed_at_unix_seconds,
      githubRequestId: descriptor.github_request_id,
      responseEtag: descriptor.response_etag
    })
  )
  if (Either.isLeft(observed)) return Either.left(observed.left)
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
      postconditionError(
        "OBSERVATION_REPLAY_INVALID",
        descriptor.phase,
        "compact observation metadata differs from trusted reconstruction"
      )
    )
  }
  return Either.right(observed.right)
}

const reconstructObservations = (
  manifest: S2SStageUploadPostconditionManifest,
  observationBytes: Uint8Array
): Either.Either<
  ReadonlyArray<ReplayedObservation>,
  S2SStageUploadPostconditionError
> => {
  const expected = expectedObservations(manifest.successful_attempt_ordinal)
  if (
    manifest.observation_count !== expected.length ||
    manifest.observation_count !==
      s2sStageUploadPostconditionObservationCount(
        manifest.successful_attempt_ordinal
      ) ||
    manifest.observations.length !== expected.length ||
    observationBytes.byteLength !== manifest.observation_blob_byte_length ||
    observationBytes.byteLength >
      s2sStageUploadPostconditionRawBodyMaximumBytes(
        manifest.successful_attempt_ordinal
      ) ||
    rawS2SFileSha256(observationBytes) !==
      manifest.observation_blob_sha256
  ) {
    return Either.left(
      postconditionError(
        "OBSERVATION_TOPOLOGY_INVALID",
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
        postconditionError(
          "OBSERVATION_TOPOLOGY_INVALID",
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
        postconditionError(
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
      postconditionError(
        "OBSERVATION_TOPOLOGY_INVALID",
        "OBSERVATIONS",
        "observation slices do not exhaust the exact blob"
      )
    )
  }
  return Either.right(Object.freeze(output))
}

const observationAt = <Projection extends S2SGitHubProjection>(
  observations: ReadonlyArray<ReplayedObservation>,
  phase: S2SStageUploadObservationPhase
): S2SGitHubObservation<Projection> | undefined =>
  observations.find((entry) => entry.phase === phase)?.observation as
    | S2SGitHubObservation<Projection>
    | undefined

const hasExpectedWorkflowIdentity = (
  projection: S2SGitHubWorkflowRunProjection,
  identity: Schema.Schema.Type<typeof PermitIdentitySchema>
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

const jobsMatchIdentity = (
  run: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  identity: Schema.Schema.Type<typeof PermitIdentitySchema>
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
      return false
    }
  }
  return true
}

const seedLedger = (
  current: S2SCurrentRunStageEvidence
): ReadonlyArray<Schema.Schema.Type<typeof AssertionLedgerEntrySchema>> =>
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
        receiptSha256: S2SSha256Schema.make(observation.receiptSha256),
        observedAtUnixSeconds: observation.observedAtUnixSeconds
      })
    )
  )

const expectedAssertionLedger = (
  current: S2SCurrentRunStageEvidence,
  observations: ReadonlyArray<ReplayedObservation>,
  download: S2SGitHubArtifactDownloadReceipt
): ReadonlyArray<Schema.Schema.Type<typeof AssertionLedgerEntrySchema>> => {
  const entries: Array<Schema.Schema.Type<typeof AssertionLedgerEntrySchema>> = [
    ...seedLedger(current)
  ]
  for (const entry of observations) {
    if (entry.phase === "READBACK_RUN_END") {
      entries.push(
        Object.freeze({
          operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
          phase: "READBACK_DOWNLOAD_REDIRECT" as const,
          githubRequestId: download.redirectGitHubRequestId,
          receiptSha256: S2SSha256Schema.make(download.receiptSha256),
          observedAtUnixSeconds: download.downloadedAtUnixSeconds
        })
      )
    }
    entries.push(
      Object.freeze({
        operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
        phase: entry.phase,
        githubRequestId: entry.observation.receipt.githubRequestId,
        receiptSha256: S2SSha256Schema.make(
          entry.observation.receipt.receiptSha256
        ),
        observedAtUnixSeconds:
          entry.observation.receipt.observedAtUnixSeconds
      })
    )
  }
  return Object.freeze(entries)
}

/**
 * Serialized permit evidence is never a bearer. Builds in this codec-only
 * slice accept test evidence exclusively; recovery may recheck either declared
 * scope structurally but still returns a non-authorizing snapshot.
 */
const validateAssertionPermitEvidence = (
  input: unknown,
  current: S2SCurrentRunStageEvidence,
  observations: ReadonlyArray<ReplayedObservation>,
  download: S2SGitHubArtifactDownloadReceipt,
  mode: "TEST_ONLY_BUILD" | "STRUCTURAL_RECOVERY"
): Either.Either<
  S2SStageUploadAssertionPermitEvidence,
  S2SStageUploadPostconditionError
> => {
  try {
    const snapshot = snapshotCanonicalValue(input)
    if (snapshot === null) {
      throw new Error("permit evidence is not canonical plain data")
    }
    const decoded = Schema.decodeUnknownEither(AssertionPermitEvidenceSchema, {
      onExcessProperty: "error"
    })(snapshot)
    if (Either.isLeft(decoded)) {
      throw new Error("permit evidence violates its exact v1 schema")
    }
    const evidence = deepFreezeCanonical(structuredClone(decoded.right))
    const claimsMatch =
      (evidence.authorityScope === "TRUSTED_SINGLE_MODULE_CURRENT_JOB" &&
        evidence.authorizationClaimed === true &&
        evidence.oneUseClaim ===
          "ONE_USE_PER_GENUINE_AUTHORITY_AND_PROCESS_IDENTITY_SLOT") ||
      (evidence.authorityScope === "TEST_ONLY_NON_AUTHORIZING" &&
        evidence.authorizationClaimed === false &&
        evidence.oneUseClaim === "MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE")
    const { receiptSha256, ...core } = evidence
    const receipt = canonicalS2SControlSha256(core)
    const expectedIdentity = identityFromCurrent(current)
    const expectedEntries = expectedAssertionLedger(
      current,
      observations,
      download
    )
    const requestIds = new Set(evidence.ledgerEntries.map(
      (entry) => entry.githubRequestId
    ))
    const receiptHashes = new Set(evidence.ledgerEntries.map(
      (entry) => entry.receiptSha256
    ))
    const monotonic = evidence.ledgerEntries.every(
      (entry, index) =>
        index === 0 ||
        entry.observedAtUnixSeconds >=
          (evidence.ledgerEntries[index - 1]?.observedAtUnixSeconds ?? 0)
    )
    if (
      !claimsMatch ||
      (mode === "TEST_ONLY_BUILD" &&
        evidence.authorityScope !== "TEST_ONLY_NON_AUTHORIZING") ||
      Either.isLeft(receipt) ||
      receipt.right !== receiptSha256 ||
      !sameCanonicalData(evidence.identity, expectedIdentity) ||
      evidence.ledgerEntries.length !== expectedEntries.length ||
      evidence.ledgerEntries.some(
        (entry, index) => !sameCanonicalData(entry, expectedEntries[index])
      ) ||
      requestIds.size !== evidence.ledgerEntries.length ||
      receiptHashes.size !== evidence.ledgerEntries.length ||
      !monotonic
    ) {
      throw new Error(
        "permit claims, self-hash, identity, or exact non-evicting ledger diverged"
      )
    }
    return Either.right(evidence)
  } catch (error) {
    return Either.left(
      postconditionError(
        "PERMIT_BINDING_MISMATCH",
        "ASSERTION_PERMIT_EVIDENCE",
        error instanceof Error
          ? error.message
          : "permit evidence validation failed closed"
      )
    )
  }
}

interface ValidatedUploadSemantics {
  readonly observations: ReadonlyArray<S2SGitHubObservation>
  readonly archive: S2SValidatedArtifactZip
  readonly artifactEvidence: S2SArtifactEvidence
  readonly assertionPermitEvidence: S2SStageUploadAssertionPermitEvidence
}

const decodeDerivedArtifactEvidence = (
  input: unknown,
  phase: string
): Either.Either<S2SArtifactEvidence, S2SStageUploadPostconditionError> => {
  const decoded = Schema.decodeUnknownEither(S2SArtifactEvidenceSchema, {
    onExcessProperty: "error"
  })(input)
  return Either.isLeft(decoded)
    ? Either.left(
        postconditionError(
          "ARTIFACT_BINDING_MISMATCH",
          phase,
          "derived artifact evidence violates its fixed schema"
        )
      )
    : Either.right(deepFreezeCanonical(structuredClone(decoded.right)))
}

const validateStageUploadSemantics = (
  manifest: S2SStageUploadPostconditionManifest,
  current: S2SCurrentRunStageEvidence,
  observations: ReadonlyArray<ReplayedObservation>,
  archiveBytes: Uint8Array,
  prepared: ReadonlyArray<PreparedMemberSnapshot>
): Either.Either<
  ValidatedUploadSemantics,
  S2SStageUploadPostconditionError
> => {
  const spec = S2S_STAGE_ARTIFACT_SPECS[current.stage]
  const expectedIdentity = identityFromCurrent(current)
  if (
    manifest.source_commit_a !== current.sourceCommitA ||
    manifest.current_run_evidence_receipt_sha256 !== current.receiptSha256 ||
    manifest.stage !== current.stage ||
    !sameCanonicalData(manifest.identity, expectedIdentity) ||
    manifest.role !== spec.role ||
    manifest.producer_job_id !== current.currentJobDatabaseId ||
    manifest.producer_job_name !== spec.jobName ||
    manifest.artifact_name !== spec.artifactName
  ) {
    return Either.left(
      postconditionError(
        "STAGE_IDENTITY_MISMATCH",
        "IDENTITY",
        "current run, stage, role, producer job, or artifact policy diverged"
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
      postconditionError(
        "STAGE_IDENTITY_MISMATCH",
        "LOOKUP",
        "lookup run or exact attempt-one job roster is invalid"
      )
    )
  }
  const producerMatches = jobs.receipt.projection.jobs.filter(
    (job) => job.name === spec.jobName
  )
  const producer = producerMatches.length === 1 ? producerMatches[0] : undefined
  if (
    producer === undefined ||
    producer.id !== current.currentJobDatabaseId ||
    producer.id !== manifest.producer_job_id ||
    producer.status !== "in_progress" ||
    producer.conclusion !== null ||
    producer.completedAt !== null ||
    producer.completedAtUnixSeconds !== null
  ) {
    return Either.left(
      postconditionError(
        "STAGE_IDENTITY_MISMATCH",
        "LOOKUP_JOBS",
        "producer is not the authority-bound current in-progress job"
      )
    )
  }

  let selectedArtifact: S2SGitHubArtifactProjection | undefined
  let selectedAtUnixSeconds: number | undefined
  let previousTime = jobs.receipt.observedAtUnixSeconds
  for (
    let ordinal = 1;
    ordinal <= manifest.successful_attempt_ordinal;
    ordinal += 1
  ) {
    const artifacts = observationAt<S2SGitHubArtifactsProjection>(
      observations,
      `LOOKUP_ARTIFACTS_${ordinal}` as S2SStageUploadObservationPhase
    )
    const run = observationAt<S2SGitHubWorkflowRunProjection>(
      observations,
      `LOOKUP_RUN_END_${ordinal}` as S2SStageUploadObservationPhase
    )
    if (
      artifacts === undefined ||
      run === undefined ||
      artifacts.receipt.observedAtUnixSeconds < previousTime ||
      run.receipt.observedAtUnixSeconds <
        artifacts.receipt.observedAtUnixSeconds ||
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
        postconditionError(
          "OBSERVATION_TOPOLOGY_INVALID",
          `LOOKUP_ARTIFACTS_${ordinal}`,
          "lookup observation order or run/head binding is invalid"
        )
      )
    }
    const matching = artifacts.receipt.projection.artifacts.filter(
      (artifact) => artifact.name === spec.artifactName
    )
    const final = ordinal === manifest.successful_attempt_ordinal
    if ((!final && matching.length !== 0) || (final && matching.length !== 1)) {
      return Either.left(
        postconditionError(
          "ARTIFACT_BINDING_MISMATCH",
          `LOOKUP_ARTIFACTS_${ordinal}`,
          "earlier polls must be absent and the successful poll exactly singular"
        )
      )
    }
    if (final) {
      selectedArtifact = matching[0]
      selectedAtUnixSeconds = artifacts.receipt.observedAtUnixSeconds
    }
    previousTime = run.receipt.observedAtUnixSeconds
  }
  if (
    selectedArtifact === undefined ||
    selectedAtUnixSeconds === undefined ||
    selectedArtifact.expired ||
    selectedArtifact.createdAtUnixSeconds < producer.startedAtUnixSeconds ||
    selectedArtifact.createdAtUnixSeconds > selectedAtUnixSeconds ||
    selectedArtifact.id !== manifest.artifact_id ||
    selectedArtifact.name !== manifest.artifact_name ||
    selectedArtifact.sizeInBytes !== manifest.artifact_byte_length ||
    selectedArtifact.digestSha256 !== manifest.artifact_sha256 ||
    selectedArtifact.sizeInBytes > spec.maximumArchiveBytes
  ) {
    return Either.left(
      postconditionError(
        "ARTIFACT_BINDING_MISMATCH",
        "LOOKUP_SUCCESS",
        "selected artifact is expired, temporally impossible, or manifest-divergent"
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
      postconditionError(
        "ARTIFACT_BINDING_MISMATCH",
        "READBACK",
        "fresh readback run or exact artifact requery diverged"
      )
    )
  }

  const download = validateS2SGitHubArtifactDownload(
    Object.freeze({
      receipt: manifest.download_receipt,
      readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes)
    }),
    manifest.artifact_id,
    spec.maximumArchiveBytes
  )
  if (Either.isLeft(download)) {
    return Either.left(
      postconditionError(
        "DOWNLOAD_REPLAY_INVALID",
        "DOWNLOAD",
        `download receipt rejected recovered bytes: ${download.left.reason}`
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
    downloadReceipt.downloadedArchiveSha256 !== manifest.artifact_sha256 ||
    archiveBytes.byteLength !== manifest.artifact_byte_length ||
    rawS2SFileSha256(archiveBytes) !== manifest.artifact_sha256
  ) {
    return Either.left(
      postconditionError(
        "DOWNLOAD_REPLAY_INVALID",
        "DOWNLOAD",
        "download order, length, or raw archive binding is invalid"
      )
    )
  }

  const archive = validateS2SArtifactZip(archiveBytes, {
    expectedArchiveSha256: S2SSha256Schema.make(manifest.artifact_sha256),
    expectedArchiveByteLength: manifest.artifact_byte_length,
    expectedMembers: spec.expectedMembers,
    maximumArchiveBytes: spec.maximumArchiveBytes,
    maximumExpandedBytes: spec.maximumExpandedBytes
  })
  if (Either.isLeft(archive)) {
    return Either.left(
      postconditionError(
        "ARCHIVE_REPLAY_INVALID",
        "ARCHIVE",
        `current-stage archive ZIP rejected: ${archive.left.reason}`
      )
    )
  }
  if (!archiveMatchesPreparedMembers(archive.right, prepared)) {
    return Either.left(
      postconditionError(
        "PREPARED_MEMBER_MISMATCH",
        "PREPARED_MEMBERS",
        "recovered archive member bytes differ from the prepared tuple"
      )
    )
  }
  const expectedArchiveProjection = archiveValidationProjection(archive.right)
  const expectedPreparedProjection = preparedMemberProjection(prepared)
  if (
    !sameCanonicalData(
      expectedArchiveProjection,
      manifest.archive_validation
    ) ||
    !sameCanonicalData(
      expectedPreparedProjection,
      manifest.prepared_members
    )
  ) {
    return Either.left(
      postconditionError(
        "PREPARED_MEMBER_MISMATCH",
        "ARCHIVE_PROJECTION",
        "manifest archive or prepared-member projection differs from fresh bytes"
      )
    )
  }

  const expectedArchiveReference = deepFreezeCanonical({
    logical_name: spec.archiveLogicalName,
    role: spec.archiveProfileRole,
    schema_version: spec.carrierSchemaVersion,
    media_type: "application/zip" as const,
    byte_length: archiveBytes.byteLength,
    raw_sha256: S2SSha256Schema.make(rawS2SFileSha256(archiveBytes))
  })
  if (!sameCanonicalData(expectedArchiveReference, manifest.archive_reference)) {
    return Either.left(
      postconditionError(
        "ARCHIVE_REFERENCE_INVALID",
        "ARCHIVE_REFERENCE",
        "current-stage archive reference differs from recovered bytes and policy"
      )
    )
  }

  const expectedArtifactEvidence = decodeDerivedArtifactEvidence({
    artifactName: spec.artifactName,
    artifactId: selectedArtifact.id,
    artifactCount: 1,
    archiveSizeBytes: selectedArtifact.sizeInBytes,
    largestMemberSizeBytes: archive.right.largestMemberByteLength,
    compressionLevel: S2S_CONFIRMATORY_POLICY.archive.compressionLevel,
    retentionDays: S2S_CONFIRMATORY_POLICY.archive.retentionDays,
    overwrite: S2S_CONFIRMATORY_POLICY.archive.overwrite,
    apiDigestSha256: selectedArtifact.digestSha256,
    downloadedArchiveSha256: downloadReceipt.downloadedArchiveSha256
  }, "ARTIFACT_EVIDENCE")
  if (Either.isLeft(expectedArtifactEvidence)) {
    return Either.left(expectedArtifactEvidence.left)
  }
  if (!sameCanonicalData(expectedArtifactEvidence.right, manifest.artifact_evidence)) {
    return Either.left(
      postconditionError(
        "ARTIFACT_BINDING_MISMATCH",
        "ARTIFACT_EVIDENCE",
        "artifact evidence differs from fresh observation and archive validation"
      )
    )
  }
  const permit = validateAssertionPermitEvidence(
    manifest.assertion_permit_evidence,
    current,
    observations,
    downloadReceipt,
    "STRUCTURAL_RECOVERY"
  )
  if (Either.isLeft(permit)) return Either.left(permit.left)
  return Either.right(
    Object.freeze({
      observations: Object.freeze(
        observations.map((entry) => entry.observation)
      ),
      archive: archive.right,
      artifactEvidence: expectedArtifactEvidence.right,
      assertionPermitEvidence: permit.right
    })
  )
}

const decodeManifest = (
  input: Uint8Array
): Either.Either<
  S2SStageUploadPostconditionManifest,
  S2SStageUploadPostconditionError
> => {
  try {
    const parsed = parseS2SJsonBytes(
      input,
      S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES
    )
    if (Either.isLeft(parsed)) {
      return Either.left(
        postconditionError(
          "MANIFEST_INVALID",
          "MANIFEST",
          `strict JSON rejected the manifest: ${parsed.left.reason}`
        )
      )
    }
    const parsedRecord =
      parsed.right !== null &&
      typeof parsed.right === "object" &&
      !Array.isArray(parsed.right)
        ? exactDataRecord(
            parsed.right,
            Object.keys(parsed.right as Readonly<Record<string, unknown>>)
          )
        : null
    if (
      parsedRecord?.["schema_version"] ===
      "hswm-swm0w-s2s-test-only-golden-upload-postcondition/v1"
    ) {
      return Either.left(
        postconditionError(
          "TEST_ONLY_GOLDEN_REJECTED",
          "MANIFEST",
          "test-only golden postconditions have no production codec adapter"
        )
      )
    }
    const decoded = Schema.decodeUnknownEither(
      StageUploadPostconditionManifestSchema,
      { onExcessProperty: "error" }
    )(parsed.right)
    if (Either.isLeft(decoded)) {
      return Either.left(
        postconditionError(
          "MANIFEST_INVALID",
          "MANIFEST",
          "manifest violates the exact correlated v1 stage schema"
        )
      )
    }
    const manifest = deepFreezeCanonical(structuredClone(decoded.right))
    const canonical = canonicalS2SControlJsonBytes(manifest)
    if (Either.isLeft(canonical) || !sameBytes(canonical.right, input)) {
      return Either.left(
        postconditionError(
          "MANIFEST_INVALID",
          "MANIFEST",
          "manifest is not the exact canonical ASCII JSON line"
        )
      )
    }
    const {
      postcondition_receipt_sha256: declaredReceipt,
      ...core
    } = manifest
    const receipt = canonicalS2SControlSha256(core)
    if (Either.isLeft(receipt) || receipt.right !== declaredReceipt) {
      return Either.left(
        postconditionError(
          "MANIFEST_SELF_HASH_MISMATCH",
          "MANIFEST",
          "postcondition receipt differs from the canonical manifest core"
        )
      )
    }
    return Either.right(manifest)
  } catch {
    return Either.left(
      postconditionError(
        "MANIFEST_INVALID",
        "MANIFEST",
        "manifest decoding failed closed"
      )
    )
  }
}

interface DecodedPostconditionCarrier {
  readonly carrierBytes: Uint8Array
  readonly carrierRawSha256: S2SSha256
  readonly manifestBytes: Uint8Array
  readonly observationBytes: Uint8Array
  readonly manifest: S2SStageUploadPostconditionManifest
}

const decodeCarrier = (
  input: unknown
): Either.Either<
  DecodedPostconditionCarrier,
  S2SStageUploadPostconditionError
> => {
  const carrierBytes = snapshotPlainBytes(
    input,
    S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES
  )
  if (carrierBytes === null) {
    return Either.left(
      postconditionError(
        "BYTE_BUDGET_EXCEEDED",
        "CARRIER",
        "postcondition carrier is not one bounded plain byte array"
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
        name: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
        maximumBytes: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES
      }),
      Object.freeze({
        name: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
        maximumBytes: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES
      })
    ]),
    maximumArchiveBytes: S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
    maximumExpandedBytes:
      S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES +
      S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES
  })
  if (Either.isLeft(zip)) {
    return Either.left(
      postconditionError(
        "CARRIER_INVALID",
        "CARRIER",
        `stored ZIP rejected the postcondition: ${zip.left.reason}`
      )
    )
  }
  const manifestMember = zip.right.members[0]
  const observationMember = zip.right.members[1]
  if (
    zip.right.members.length !== 2 ||
    manifestMember === undefined ||
    observationMember === undefined ||
    manifestMember.name !==
      S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME ||
    observationMember.name !==
      S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME
  ) {
    return Either.left(
      postconditionError(
        "CARRIER_INVALID",
        "CARRIER",
        "postcondition ZIP does not expose its exact ordered two-member roster"
      )
    )
  }
  const manifestBytes = manifestMember.readBytes()
  const observationBytes = observationMember.readBytes()
  if (
    carrierBytes.byteLength !==
    manifestBytes.byteLength +
      observationBytes.byteLength +
      S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES
  ) {
    return Either.left(
      postconditionError(
        "CARRIER_INVALID",
        "CARRIER",
        "postcondition ZIP does not have the exact fixed 264-byte framing"
      )
    )
  }
  const rebuilt = buildS2SStoredZip([
    {
      name: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
      bytes: manifestBytes
    },
    {
      name: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
      bytes: observationBytes
    }
  ])
  if (
    Either.isLeft(rebuilt) ||
    (Either.isRight(rebuilt) &&
      !sameBytes(rebuilt.right.readArchiveBytes(), carrierBytes))
  ) {
    return Either.left(
      postconditionError(
        "CARRIER_INVALID",
        "CARRIER",
        Either.isLeft(rebuilt)
          ? `deterministic stored ZIP rebuild failed: ${rebuilt.left.reason}`
          : "carrier is valid ZIP but not exact deterministic stored framing"
      )
    )
  }
  const manifest = decodeManifest(manifestBytes)
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

const makeReconstructionSnapshot = (
  manifestInput: S2SStageUploadPostconditionManifest,
  manifestBytesInput: Uint8Array,
  observationBytesInput: Uint8Array,
  archiveBytesInput: Uint8Array,
  semantics: ValidatedUploadSemantics
): S2SStageUploadPostconditionReconstruction => {
  const manifest = deepFreezeCanonical(structuredClone(manifestInput))
  const manifestBytes = Uint8Array.from(manifestBytesInput)
  const observationBytes = Uint8Array.from(observationBytesInput)
  const archiveBytes = Uint8Array.from(archiveBytesInput)
  return Object.freeze({
    _tag: "ValidatedNonAuthorizingStageUploadPostcondition" as const,
    manifest,
    manifestRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(manifestBytes)
    ),
    observations: semantics.observations,
    archiveValidation: semantics.archive,
    artifactEvidence: semantics.artifactEvidence,
    assertionPermitEvidence: semantics.assertionPermitEvidence,
    readManifestBytes: (): Uint8Array => Uint8Array.from(manifestBytes),
    readObservationBlob: (): Uint8Array => Uint8Array.from(observationBytes),
    readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes)
  })
}

const reconstructFromSnapshots = (
  manifestBytes: Uint8Array,
  observationBytes: Uint8Array,
  current: S2SCurrentRunStageEvidence,
  archiveBytes: Uint8Array,
  prepared: ReadonlyArray<PreparedMemberSnapshot>
): Either.Either<
  S2SStageUploadPostconditionReconstruction,
  S2SStageUploadPostconditionError
> => {
  const manifest = decodeManifest(manifestBytes)
  if (Either.isLeft(manifest)) return Either.left(manifest.left)
  const observations = reconstructObservations(
    manifest.right,
    observationBytes
  )
  if (Either.isLeft(observations)) return Either.left(observations.left)
  const semantics = validateStageUploadSemantics(
    manifest.right,
    current,
    observations.right,
    archiveBytes,
    prepared
  )
  return Either.isLeft(semantics)
    ? Either.left(semantics.left)
    : Either.right(
        makeReconstructionSnapshot(
          manifest.right,
          manifestBytes,
          observationBytes,
          archiveBytes,
          semantics.right
        )
      )
}

/**
 * Reconstructs every raw GitHub body and independently cross-binds the
 * canonical manifest, current-stage archive, and prepared member bytes. The
 * result is deliberately structural and never restores process-local authority.
 */
export const reconstructS2SStageUploadPostcondition = (
  input: unknown
): Either.Either<
  S2SStageUploadPostconditionReconstruction,
  S2SStageUploadPostconditionError
> => {
  try {
    const root = exactDataRecord(input, [
      "currentRunEvidence",
      "currentStageArchiveBytes",
      "manifestBytes",
      "observationBytes",
      "preparedMembers"
    ])
    if (root === null) {
      return Either.left(
        postconditionError(
          "INPUT_INVALID",
          "RECONSTRUCT_INPUT",
          "reconstruction input must be one exact plain data record"
        )
      )
    }
    const current = validateCurrentRunEvidence(root["currentRunEvidence"])
    if (Either.isLeft(current)) return Either.left(current.left)
    const spec = S2S_STAGE_ARTIFACT_SPECS[current.right.stage]
    const manifestBytes = snapshotPlainBytes(
      root["manifestBytes"],
      S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES
    )
    const observationBytes = snapshotPlainBytes(
      root["observationBytes"],
      S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES
    )
    const archiveBytes = snapshotPlainBytes(
      root["currentStageArchiveBytes"],
      spec.maximumArchiveBytes
    )
    const prepared = snapshotPreparedMembers(
      root["preparedMembers"],
      current.right.stage
    )
    if (
      manifestBytes === null ||
      observationBytes === null ||
      archiveBytes === null
    ) {
      return Either.left(
        postconditionError(
          "BYTE_BUDGET_EXCEEDED",
          "RECONSTRUCT_INPUT",
          "one reconstruction byte surface violates its exact cap"
        )
      )
    }
    if (Either.isLeft(prepared)) return Either.left(prepared.left)
    return reconstructFromSnapshots(
      manifestBytes,
      observationBytes,
      current.right,
      archiveBytes,
      prepared.right
    )
  } catch {
    return Either.left(
      postconditionError(
        "INPUT_INVALID",
        "RECONSTRUCT_INPUT",
        "postcondition reconstruction failed closed"
      )
    )
  }
}

/** Decode the deterministic two-member carrier, then perform full recovery. */
export const validateS2SStageUploadPostcondition = (
  input: unknown
): Either.Either<
  S2SStageUploadPostconditionSnapshot,
  S2SStageUploadPostconditionError
> => {
  try {
    const root = exactDataRecord(input, [
      "carrierBytes",
      "currentRunEvidence",
      "currentStageArchiveBytes",
      "preparedMembers"
    ])
    if (root === null) {
      return Either.left(
        postconditionError(
          "INPUT_INVALID",
          "VALIDATE_INPUT",
          "validator input must be one exact plain data record"
        )
      )
    }
    const carrier = decodeCarrier(root["carrierBytes"])
    if (Either.isLeft(carrier)) return Either.left(carrier.left)
    const current = validateCurrentRunEvidence(root["currentRunEvidence"])
    if (Either.isLeft(current)) return Either.left(current.left)
    const spec = S2S_STAGE_ARTIFACT_SPECS[current.right.stage]
    const archiveBytes = snapshotPlainBytes(
      root["currentStageArchiveBytes"],
      spec.maximumArchiveBytes
    )
    const prepared = snapshotPreparedMembers(
      root["preparedMembers"],
      current.right.stage
    )
    if (archiveBytes === null) {
      return Either.left(
        postconditionError(
          "BYTE_BUDGET_EXCEEDED",
          "CURRENT_STAGE_ARCHIVE",
          "current-stage archive is not one bounded plain byte array"
        )
      )
    }
    if (Either.isLeft(prepared)) return Either.left(prepared.left)
    const reconstruction = reconstructFromSnapshots(
      carrier.right.manifestBytes,
      carrier.right.observationBytes,
      current.right,
      archiveBytes,
      prepared.right
    )
    if (Either.isLeft(reconstruction)) return Either.left(reconstruction.left)
    const carrierBytes = Uint8Array.from(carrier.right.carrierBytes)
    return Either.right(
      Object.freeze({
        ...reconstruction.right,
        carrierRawSha256: carrier.right.carrierRawSha256,
        carrierByteLength: carrierBytes.byteLength,
        readCarrierBytes: (): Uint8Array => Uint8Array.from(carrierBytes)
      })
    )
  } catch {
    return Either.left(
      postconditionError(
        "INPUT_INVALID",
        "VALIDATE_INPUT",
        "postcondition validation failed closed"
      )
    )
  }
}

/**
 * Builds only from current-run evidence, raw independently observed GitHub
 * surfaces, recovered archive bytes, and the ordered prepared member tuple.
 * Every policy selector and every derived hash remains internal.
 */
export const buildS2SStageUploadPostcondition = (
  input: unknown
): Either.Either<
  S2SStageUploadPostconditionSnapshot,
  S2SStageUploadPostconditionError
> => {
  try {
    const root = exactDataRecord(input, [
      "artifactDownload",
      "assertionPermitEvidence",
      "currentRunEvidence",
      "observations",
      "preparedMembers",
      "successfulAttemptOrdinal"
    ])
    const successfulAttemptOrdinal = root?.["successfulAttemptOrdinal"]
    if (
      root === null ||
      (successfulAttemptOrdinal !== 1 &&
        successfulAttemptOrdinal !== 2 &&
        successfulAttemptOrdinal !== 3)
    ) {
      return Either.left(
        postconditionError(
          "INPUT_INVALID",
          "BUILD_INPUT",
          "builder input and successful attempt ordinal must be exact"
        )
      )
    }
    const current = validateCurrentRunEvidence(root["currentRunEvidence"])
    if (Either.isLeft(current)) return Either.left(current.left)
    const spec = S2S_STAGE_ARTIFACT_SPECS[current.right.stage]
    const prepared = snapshotPreparedMembers(
      root["preparedMembers"],
      current.right.stage
    )
    if (Either.isLeft(prepared)) return Either.left(prepared.left)
    const observations = snapshotBuildObservations(
      root["observations"],
      successfulAttemptOrdinal,
      current.right
    )
    if (Either.isLeft(observations)) return Either.left(observations.left)
    const selectedArtifact = observations.right.selectedArtifact
    const download = validateS2SGitHubArtifactDownload(
      root["artifactDownload"],
      selectedArtifact.id,
      spec.maximumArchiveBytes
    )
    if (Either.isLeft(download)) {
      return Either.left(
        postconditionError(
          "DOWNLOAD_REPLAY_INVALID",
          "BUILD_DOWNLOAD",
          `download input was rejected: ${download.left.reason}`
        )
      )
    }
    const archiveBytes = snapshotPlainBytes(
      download.right.readArchiveBytes(),
      spec.maximumArchiveBytes
    )
    if (archiveBytes === null) {
      return Either.left(
        postconditionError(
          "DOWNLOAD_REPLAY_INVALID",
          "BUILD_DOWNLOAD",
          "download validator did not retain bounded archive bytes"
        )
      )
    }
    const archive = validateS2SArtifactZip(archiveBytes, {
      expectedArchiveSha256: S2SSha256Schema.make(
        rawS2SFileSha256(archiveBytes)
      ),
      expectedArchiveByteLength: archiveBytes.byteLength,
      expectedMembers: spec.expectedMembers,
      maximumArchiveBytes: spec.maximumArchiveBytes,
      maximumExpandedBytes: spec.maximumExpandedBytes
    })
    if (Either.isLeft(archive)) {
      return Either.left(
        postconditionError(
          "ARCHIVE_REPLAY_INVALID",
          "BUILD_ARCHIVE",
          `downloaded current-stage archive ZIP rejected: ${archive.left.reason}`
        )
      )
    }
    if (!archiveMatchesPreparedMembers(archive.right, prepared.right)) {
      return Either.left(
        postconditionError(
          "PREPARED_MEMBER_MISMATCH",
          "BUILD_PREPARED_MEMBERS",
          "downloaded member bytes differ from the prepared tuple"
        )
      )
    }
    const expected = expectedObservations(successfulAttemptOrdinal)
    const replayed: ReadonlyArray<ReplayedObservation> = Object.freeze(
      observations.right.observations.map((observation, index) =>
        Object.freeze({
          phase: expected[index]?.phase ?? "READBACK_RUN_END",
          observation
        })
      )
    )
    const permit = validateAssertionPermitEvidence(
      root["assertionPermitEvidence"],
      current.right,
      replayed,
      download.right.receipt,
      "TEST_ONLY_BUILD"
    )
    if (Either.isLeft(permit)) return Either.left(permit.left)
    const identity = identityFromCurrent(current.right)
    const artifactEvidence = decodeDerivedArtifactEvidence({
      artifactName: spec.artifactName,
      artifactId: selectedArtifact.id,
      artifactCount: 1,
      archiveSizeBytes: selectedArtifact.sizeInBytes,
      largestMemberSizeBytes: archive.right.largestMemberByteLength,
      compressionLevel: S2S_CONFIRMATORY_POLICY.archive.compressionLevel,
      retentionDays: S2S_CONFIRMATORY_POLICY.archive.retentionDays,
      overwrite: S2S_CONFIRMATORY_POLICY.archive.overwrite,
      apiDigestSha256: selectedArtifact.digestSha256,
      downloadedArchiveSha256: download.right.receipt.downloadedArchiveSha256
    }, "BUILD_ARTIFACT_EVIDENCE")
    if (Either.isLeft(artifactEvidence)) {
      return Either.left(artifactEvidence.left)
    }
    const provisional = deepFreezeCanonical({
      schema_version: S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
      representation: S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION,
      experiment_id: S2S_CONFIRMATORY_EXPERIMENT_ID,
      classification: "PRODUCTION_INTENDED_STAGE_UPLOAD_POSTCONDITION" as const,
      authority_scope: "PROCESS_LOCAL_STAGE_ENTRY" as const,
      publication_claim:
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
      publisher_return_used_as_evidence: false as const,
      historical_uniqueness_claimed: false as const,
      external_exactly_once_claimed: false as const,
      cross_worker_replay_prevention_claimed: false as const,
      cross_module_copy_replay_prevention_claimed: false as const,
      cross_process_replay_prevention_claimed: false as const,
      durable_replay_prevention_claimed: false as const,
      source_commit_a: current.right.sourceCommitA,
      current_run_evidence_receipt_sha256: current.right.receiptSha256,
      identity,
      assertion_permit_evidence: permit.right,
      stage: current.right.stage,
      role: spec.role,
      producer_job_id: current.right.currentJobDatabaseId,
      producer_job_name: spec.jobName,
      artifact_name: spec.artifactName,
      artifact_id: selectedArtifact.id,
      artifact_byte_length: selectedArtifact.sizeInBytes,
      artifact_sha256: S2SSha256Schema.make(selectedArtifact.digestSha256),
      successful_attempt_ordinal: successfulAttemptOrdinal,
      observation_count: s2sStageUploadPostconditionObservationCount(
        successfulAttemptOrdinal
      ),
      observation_blob_byte_length: observations.right.blob.byteLength,
      observation_blob_sha256: S2SSha256Schema.make(
        rawS2SFileSha256(observations.right.blob)
      ),
      observations: observations.right.descriptors,
      download_receipt: structuredClone(download.right.receipt),
      artifact_evidence: artifactEvidence.right,
      archive_reference: {
        logical_name: spec.archiveLogicalName,
        role: spec.archiveProfileRole,
        schema_version: spec.carrierSchemaVersion,
        media_type: "application/zip" as const,
        byte_length: archiveBytes.byteLength,
        raw_sha256: S2SSha256Schema.make(rawS2SFileSha256(archiveBytes))
      },
      archive_validation: archiveValidationProjection(archive.right),
      prepared_members: preparedMemberProjection(prepared.right),
      archive_members_equal_prepared_members: true as const
    })
    const receipt = canonicalS2SControlSha256(provisional)
    if (Either.isLeft(receipt)) {
      return Either.left(
        postconditionError(
          "MANIFEST_INVALID",
          "BUILD_MANIFEST",
          "postcondition manifest core is not canonical"
        )
      )
    }
    const manifestCandidate = deepFreezeCanonical({
      ...provisional,
      postcondition_receipt_sha256: S2SSha256Schema.make(receipt.right)
    })
    const manifest = Schema.decodeUnknownEither(
      StageUploadPostconditionManifestSchema,
      { onExcessProperty: "error" }
    )(manifestCandidate)
    if (Either.isLeft(manifest)) {
      return Either.left(
        postconditionError(
          "MANIFEST_INVALID",
          "BUILD_MANIFEST",
          "built postcondition violates the correlated stage schema"
        )
      )
    }
    const manifestBytes = canonicalS2SControlJsonBytes(manifest.right)
    if (
      Either.isLeft(manifestBytes) ||
      manifestBytes.right.byteLength >
        S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES
    ) {
      return Either.left(
        postconditionError(
          "BYTE_BUDGET_EXCEEDED",
          "BUILD_MANIFEST",
          "canonical postcondition manifest exceeds its fixed cap"
        )
      )
    }
    const zip = buildS2SStoredZip([
      {
        name: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
        bytes: manifestBytes.right
      },
      {
        name: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
        bytes: observations.right.blob
      }
    ])
    if (
      Either.isLeft(zip) ||
      (Either.isRight(zip) &&
        zip.right.archiveByteLength > S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES)
    ) {
      return Either.left(
        postconditionError(
          "CARRIER_INVALID",
          "BUILD_CARRIER",
          Either.isLeft(zip)
            ? `stored ZIP build failed: ${zip.left.reason}`
            : "stored ZIP exceeds the exact derived carrier maximum"
        )
      )
    }
    const validationMembers = prepared.right.map((member) =>
      Object.freeze({
        name: member.name,
        byteLength: member.byteLength,
        rawBytesSha256: member.rawBytesSha256,
        readBytes: (): Uint8Array => member.readBytes()
      })
    )
    return validateS2SStageUploadPostcondition({
      carrierBytes: zip.right.readArchiveBytes(),
      currentRunEvidence: current.right,
      currentStageArchiveBytes: archiveBytes,
      preparedMembers: validationMembers
    })
  } catch (error) {
    return Either.left(
      postconditionError(
        "INPUT_INVALID",
        "BUILD_INPUT",
        error instanceof Error
          ? error.message
          : "postcondition build failed closed"
      )
    )
  }
}

export const buildS2SStageUploadPostconditionEffect = (
  input: unknown
): Effect.Effect<
  S2SStageUploadPostconditionSnapshot,
  S2SStageUploadPostconditionError
> => suspendEither(() => buildS2SStageUploadPostcondition(input))

export const validateS2SStageUploadPostconditionEffect = (
  input: unknown
): Effect.Effect<
  S2SStageUploadPostconditionSnapshot,
  S2SStageUploadPostconditionError
> => suspendEither(() => validateS2SStageUploadPostcondition(input))
