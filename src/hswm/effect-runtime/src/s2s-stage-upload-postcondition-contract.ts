import { S2S_GITHUB_JSON_MAX_BYTES } from "./s2s-resource-limits.js"

export const S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION =
  "hswm-swm0w-s2s-stage-upload-postcondition/v1" as const
export const S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION =
  "STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_CURRENT_STAGE_ARCHIVE_REFERENCE" as const

export const S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME =
  "manifest.json" as const
export const S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME =
  "observations.bin" as const

export const S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES =
  1_048_576 as const
export const S2S_STAGE_UPLOAD_POSTCONDITION_MAX_OBSERVATION_COUNT = 11 as const
export const S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES =
  S2S_STAGE_UPLOAD_POSTCONDITION_MAX_OBSERVATION_COUNT *
  S2S_GITHUB_JSON_MAX_BYTES

/**
 * Two fixed names in the pinned stored-ZIP dialect: two local headers, signed
 * data descriptors, central headers, both names twice, and one end record.
 */
export const S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES =
  2 * (30 + 16 + 46) + 2 * (13 + 16) + 22

export const S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES =
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES +
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES +
  S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES

const S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATION_COUNTS = Object.freeze({
  1: 7,
  2: 9,
  3: 11
} as const)

export const s2sStageUploadPostconditionObservationCount = (
  successfulAttemptOrdinal: 1 | 2 | 3
): 7 | 9 | 11 =>
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATION_COUNTS[
    successfulAttemptOrdinal
  ]

export const s2sStageUploadPostconditionRawBodyMaximumBytes = (
  successfulAttemptOrdinal: 1 | 2 | 3
): number =>
  s2sStageUploadPostconditionObservationCount(successfulAttemptOrdinal) *
  S2S_GITHUB_JSON_MAX_BYTES

if (
  S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES !== 264 ||
  S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES !== 12_583_176
) {
  throw new Error("S2S stage-upload postcondition byte formula drifted")
}
