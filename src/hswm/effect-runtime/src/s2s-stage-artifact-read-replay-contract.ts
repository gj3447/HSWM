import { S2S_GITHUB_JSON_MAX_BYTES } from "./s2s-live-github.js"

export const S2S_STAGE_ARTIFACT_READ_REPLAY_SCHEMA_VERSION =
  "hswm-swm0w-s2s-stage-artifact-read-replay/v1" as const
export const S2S_STAGE_ARTIFACT_READ_REPLAY_REPRESENTATION =
  "STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_PREDECESSOR_CONTENT_REFERENCE" as const

export const S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME =
  "manifest.json" as const
export const S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME =
  "observations.bin" as const

export const S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES =
  1_048_576 as const
export const S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_OBSERVATION_COUNT = 11 as const
export const S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES =
  S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_OBSERVATION_COUNT *
  S2S_GITHUB_JSON_MAX_BYTES

/**
 * Two fixed names in the pinned stored-ZIP dialect:
 *
 * - two 30-byte local headers;
 * - two signed 16-byte data descriptors;
 * - two 46-byte central headers;
 * - each 13/16-byte member name appears in its local and central header; and
 * - one 22-byte end-of-central-directory record.
 */
export const S2S_STAGE_ARTIFACT_READ_REPLAY_ZIP_FRAMING_BYTES =
  2 * (30 + 16 + 46) + 2 * (13 + 16) + 22

export const S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES =
  S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES +
  S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES +
  S2S_STAGE_ARTIFACT_READ_REPLAY_ZIP_FRAMING_BYTES

export const s2sStageArtifactReadReplayObservationCount = (
  successfulAttemptOrdinal: 1 | 2 | 3
): 7 | 9 | 11 =>
  (5 + 2 * successfulAttemptOrdinal) as 7 | 9 | 11

export const s2sStageArtifactReadReplayRawBodyMaximumBytes = (
  successfulAttemptOrdinal: 1 | 2 | 3
): number =>
  s2sStageArtifactReadReplayObservationCount(successfulAttemptOrdinal) *
  S2S_GITHUB_JSON_MAX_BYTES

if (
  S2S_STAGE_ARTIFACT_READ_REPLAY_ZIP_FRAMING_BYTES !== 264 ||
  S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES !== 12_583_176
) {
  throw new Error("S2S stage-artifact replay byte formula drifted")
}
