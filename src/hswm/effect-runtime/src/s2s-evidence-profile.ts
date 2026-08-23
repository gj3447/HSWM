import { Data, Either } from "effect"

import {
  S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES,
  S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES,
  buildS2SEvidenceEnvelope,
  validateS2SEvidenceEnvelopeSnapshot,
  type S2SEvidenceEnvelopeError,
  type S2SEvidenceEnvelopeInput,
  type S2SEvidenceEnvelopeSnapshot,
  type S2SEvidenceStage
} from "./s2s-evidence-envelope.js"

export const S2S_SUCCESS_STAGE_ATTACHMENT_PROFILE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-success-stage-attachment-profile/v1" as const

export type S2SEvidenceProfileMediaType =
  | "application/json"
  | "application/octet-stream"
  | "application/zip"

export interface S2SEvidenceProfileAttachmentSpec {
  readonly logicalName: string
  readonly role: string
  readonly schemaVersion: string | null
  readonly mediaType: S2SEvidenceProfileMediaType
  readonly maximumBytes: number
}

const KIBIBYTE = 1_024
const MEBIBYTE = 1_048_576

const entry = (
  logicalName: string,
  role: string,
  schemaVersion: string | null,
  mediaType: S2SEvidenceProfileMediaType,
  maximumBytes: number
): S2SEvidenceProfileAttachmentSpec =>
  Object.freeze({ logicalName, role, schemaVersion, mediaType, maximumBytes })

const COMMON = Object.freeze([
  entry(
    "authority/current_invocation_event.json",
    "CURRENT_INVOCATION_EVENT_BYTES",
    null,
    "application/json",
    1 * MEBIBYTE
  ),
  entry(
    "authority/current_invocation_evidence.json",
    "CURRENT_INVOCATION_EVIDENCE",
    "hswm-swm0w-s2s-current-invocation-evidence/v1",
    "application/json",
    256 * KIBIBYTE
  ),
  entry(
    "authority/current_run_replay.zip",
    "CURRENT_RUN_REPLAY_SNAPSHOT",
    "hswm-swm0w-s2s-current-run-replay-snapshot/v1",
    "application/zip",
    8 * MEBIBYTE
  )
])

const sortedProfile = (
  entries: ReadonlyArray<S2SEvidenceProfileAttachmentSpec>
): ReadonlyArray<S2SEvidenceProfileAttachmentSpec> =>
  Object.freeze(
    [...entries].sort((left, right) =>
      left.logicalName < right.logicalName
        ? -1
        : left.logicalName > right.logicalName
          ? 1
          : 0
    )
  )

const REGISTER = sortedProfile([
  ...COMMON,
  entry(
    "authority/registration_commit_evidence.json",
    "REGISTRATION_COMMIT_AUTHORITY_EVIDENCE",
    "hswm-swm0w-s2s-registration-commit-authority-evidence/v1",
    "application/json",
    256 * KIBIBYTE
  ),
  entry(
    "config/operational_policy.json",
    "OPERATIONAL_POLICY_DOCUMENT",
    "hswm-swm0w-s2s-confirmatory-operational-policy/v4",
    "application/json",
    256 * KIBIBYTE
  ),
  entry(
    "config/protocol_config.json",
    "PROTOCOL_CONFIG_DOCUMENT",
    "hswm-swm0w-s2s-protocol-config/v1",
    "application/json",
    64 * KIBIBYTE
  ),
  entry(
    "config/workflow_contract.json",
    "WORKFLOW_CONTRACT_DOCUMENT",
    "hswm-swm0w-s2s-workflow-contract/v1",
    "application/json",
    256 * KIBIBYTE
  ),
  entry(
    "source/pilot_adoption_receipt.json",
    "PILOT_ADOPTION_RECEIPT",
    "hswm-swm0w-s2s-pilot-adoption/v1",
    "application/json",
    4 * MEBIBYTE
  ),
  entry(
    "source/preregistration.json",
    "PREREGISTRATION_DOCUMENT",
    "hswm-swm0w-s2s-preregistration/v1",
    "application/json",
    4 * MEBIBYTE
  ),
  entry(
    "source/registration_source.zip",
    "REGISTRATION_SOURCE_SNAPSHOT",
    "hswm-swm0w-s2s-registration-source-snapshot/v1",
    "application/zip",
    64 * MEBIBYTE
  ),
  entry(
    "source/workflow.yml",
    "WORKFLOW_SOURCE_BYTES",
    null,
    "application/octet-stream",
    1 * MEBIBYTE
  ),
  entry(
    "upload/registration_archive.zip",
    "REGISTRATION_UPLOAD_ARCHIVE",
    "hswm-swm0w-s2s-registration-carrier/v1",
    "application/zip",
    4 * MEBIBYTE
  ),
  entry(
    "upload/registration_postcondition.zip",
    "REGISTRATION_UPLOAD_POSTCONDITION",
    "hswm-swm0w-s2s-stage-upload-postcondition/v1",
    "application/zip",
    16 * MEBIBYTE
  )
])

const pythonAttachments = (
  operation: "confirm" | "adjudicate"
): ReadonlyArray<S2SEvidenceProfileAttachmentSpec> => {
  const upper = operation.toUpperCase()
  return Object.freeze([
    entry(
      "numeric/python_execution.json",
      `${upper}_PYTHON_EXECUTION`,
      "hswm-swm0w-s2s-python-execution-evidence/v1",
      "application/json",
      256 * KIBIBYTE
    ),
    entry(
      "numeric/python_golden_replay.zip",
      `${upper}_PYTHON_GOLDEN_REPLAY`,
      "hswm-swm0w-s2s-python-golden-replay/v1",
      "application/zip",
      1 * MEBIBYTE
    ),
    entry(
      "numeric/python_invocation.json",
      `${upper}_PYTHON_INVOCATION`,
      "hswm-swm0w-s2s-python-invocation-identity/v1",
      "application/json",
      256 * KIBIBYTE
    ),
    entry(
      "numeric/python_rss.json",
      `${upper}_PYTHON_RSS`,
      "hswm-swm0w-s2s-python-rss-telemetry/v1",
      "application/json",
      8 * KIBIBYTE
    ),
    entry(
      "numeric/python_runtime.json",
      `${upper}_PYTHON_RUNTIME`,
      "hswm-swm0w-s2s-python-runtime-source-identity/v2",
      "application/json",
      4 * MEBIBYTE
    )
  ])
}

const drandAttachments = (
  operation: "confirm" | "adjudicate"
): ReadonlyArray<S2SEvidenceProfileAttachmentSpec> => {
  const upper = operation.toUpperCase()
  return Object.freeze([
    entry(
      `randomness/${operation}_drand_execution.json`,
      `${upper}_DRAND_EXECUTION`,
      "hswm-swm0w-s2s-drand-execution-evidence/v1",
      "application/json",
      256 * KIBIBYTE
    ),
    entry(
      `randomness/${operation}_drand_fixture.json`,
      `${upper}_DRAND_FIXTURE`,
      "hswm-swm0w-drand-official-pulse-fixture/v1",
      "application/json",
      64 * KIBIBYTE
    ),
    entry(
      `randomness/${operation}_drand_pulse.json`,
      `${upper}_DRAND_PULSE_RAW`,
      "hswm-swm0w-s2s-drand-exact-pulse/v1",
      "application/json",
      64 * KIBIBYTE
    ),
    entry(
      `randomness/${operation}_drand_request.json`,
      `${upper}_DRAND_REQUEST`,
      "hswm-swm0w-s2s-committed-drand-request/v1",
      "application/json",
      64 * KIBIBYTE
    ),
    entry(
      `randomness/${operation}_drand_verification.json`,
      `${upper}_DRAND_VERIFICATION`,
      "hswm-swm0w-drand-verification-receipt/v1",
      "application/json",
      16 * KIBIBYTE
    )
  ])
}

const CONFIRM = sortedProfile([
  ...COMMON,
  entry(
    "input/registration_read.zip",
    "CONFIRM_REGISTRATION_READ_REPLAY",
    "hswm-swm0w-s2s-stage-artifact-read-replay/v1",
    "application/zip",
    16 * MEBIBYTE
  ),
  entry(
    "numeric/confirm_request.json",
    "NUMERIC_CONFIRM_REQUEST",
    "hswm-swm0w-s2s-numeric-confirm-request/v1",
    "application/json",
    64 * KIBIBYTE
  ),
  ...pythonAttachments("confirm"),
  ...drandAttachments("confirm"),
  entry(
    "upload/candidate_archive.zip",
    "CANDIDATE_UPLOAD_ARCHIVE",
    "hswm-swm0w-s2s-candidate-carrier/v1",
    "application/zip",
    64 * MEBIBYTE
  ),
  entry(
    "upload/candidate_postcondition.zip",
    "CANDIDATE_UPLOAD_POSTCONDITION",
    "hswm-swm0w-s2s-stage-upload-postcondition/v1",
    "application/zip",
    16 * MEBIBYTE
  )
])

const ADJUDICATE = sortedProfile([
  ...COMMON,
  entry(
    "input/candidate_first_read.zip",
    "ADJUDICATE_CANDIDATE_FIRST_READ_REPLAY",
    "hswm-swm0w-s2s-stage-artifact-read-replay/v1",
    "application/zip",
    16 * MEBIBYTE
  ),
  entry(
    "input/candidate_reread.zip",
    "ADJUDICATE_CANDIDATE_REREAD_REPLAY",
    "hswm-swm0w-s2s-stage-artifact-read-replay/v1",
    "application/zip",
    16 * MEBIBYTE
  ),
  entry(
    "input/registration_read.zip",
    "ADJUDICATE_REGISTRATION_READ_REPLAY",
    "hswm-swm0w-s2s-stage-artifact-read-replay/v1",
    "application/zip",
    16 * MEBIBYTE
  ),
  ...pythonAttachments("adjudicate"),
  ...drandAttachments("adjudicate"),
  entry(
    "upload/adjudication_archive.zip",
    "ADJUDICATION_UPLOAD_ARCHIVE",
    "hswm-swm0w-s2s-adjudication-carrier/v1",
    "application/zip",
    4 * MEBIBYTE
  ),
  entry(
    "upload/adjudication_postcondition.zip",
    "ADJUDICATION_UPLOAD_POSTCONDITION",
    "hswm-swm0w-s2s-stage-upload-postcondition/v1",
    "application/zip",
    16 * MEBIBYTE
  )
])

export const S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES: Readonly<
  Record<S2SEvidenceStage, ReadonlyArray<S2SEvidenceProfileAttachmentSpec>>
> = Object.freeze({ REGISTER, CONFIRM, ADJUDICATE })

export class S2SEvidenceProfileError extends Data.TaggedError(
  "S2SEvidenceProfileError"
)<{
  readonly stage: S2SEvidenceStage | "UNKNOWN"
  readonly reason:
    | "ATTACHMENT_COUNT_MISMATCH"
    | "ATTACHMENT_DESCRIPTOR_MISMATCH"
    | "ATTACHMENT_PROFILE_LIMIT_EXCEEDED"
    | "STRUCTURAL_ENVELOPE_REJECTED"
  readonly logicalName: string | null
  readonly detail: string
}> {}

const profileError = (
  stage: S2SEvidenceStage | "UNKNOWN",
  reason: S2SEvidenceProfileError["reason"],
  detail: string,
  logicalName: string | null = null
): S2SEvidenceProfileError =>
  new S2SEvidenceProfileError({ stage, reason, logicalName, detail })

const validateSnapshotProfile = (
  envelope: S2SEvidenceEnvelopeSnapshot
): Either.Either<S2SEvidenceEnvelopeSnapshot, S2SEvidenceProfileError> => {
  const stage = envelope.document.stage
  const expected = S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES[stage]
  if (envelope.attachments.length !== expected.length) {
    return Either.left(
      profileError(
        stage,
        "ATTACHMENT_COUNT_MISMATCH",
        "stage attachment count differs from the exact success profile"
      )
    )
  }
  for (let index = 0; index < expected.length; index += 1) {
    const spec = expected[index]
    const actual = envelope.attachments[index]?.descriptor
    if (spec === undefined || actual === undefined) {
      return Either.left(
        profileError(
          stage,
          "ATTACHMENT_COUNT_MISMATCH",
          "stage attachment roster is incomplete"
        )
      )
    }
    if (
      actual.logical_name !== spec.logicalName ||
      actual.role !== spec.role ||
      actual.schema_version !== spec.schemaVersion ||
      actual.media_type !== spec.mediaType
    ) {
      return Either.left(
        profileError(
          stage,
          "ATTACHMENT_DESCRIPTOR_MISMATCH",
          "attachment descriptor differs from the exact success profile",
          spec.logicalName
        )
      )
    }
    if (actual.byte_length > spec.maximumBytes) {
      return Either.left(
        profileError(
          stage,
          "ATTACHMENT_PROFILE_LIMIT_EXCEEDED",
          "attachment exceeds its narrower semantic-profile byte bound",
          spec.logicalName
        )
      )
    }
  }
  return Either.right(envelope)
}

export const buildS2SSuccessStageEvidenceEnvelope = (
  input: S2SEvidenceEnvelopeInput
): Either.Either<
  S2SEvidenceEnvelopeSnapshot,
  S2SEvidenceEnvelopeError | S2SEvidenceProfileError
> => {
  const built = buildS2SEvidenceEnvelope(input)
  return Either.isLeft(built) ? built : validateSnapshotProfile(built.right)
}

export const validateS2SSuccessStageEvidenceEnvelope = (
  input: unknown
): Either.Either<
  S2SEvidenceEnvelopeSnapshot,
  S2SEvidenceProfileError
> => {
  const structural = validateS2SEvidenceEnvelopeSnapshot(input)
  return Either.isLeft(structural)
    ? Either.left(
        profileError(
          "UNKNOWN",
          "STRUCTURAL_ENVELOPE_REJECTED",
          structural.left.reason
        )
      )
    : validateSnapshotProfile(structural.right)
}

// Module-load invariant: a profile can never silently exceed the substrate.
for (const profile of Object.values(S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES)) {
  const maximumTotal = profile.reduce(
    (total, attachment) => total + attachment.maximumBytes,
    0
  )
  if (
    profile.some(
      (attachment) =>
        attachment.maximumBytes < 1 ||
        attachment.maximumBytes > S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES
    ) ||
    maximumTotal > S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES
  ) {
    throw new Error("S2S success attachment profile exceeds envelope bounds")
  }
}
