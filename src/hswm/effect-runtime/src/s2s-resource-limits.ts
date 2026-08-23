/** Pure scalar limits shared by codecs and their live adapters. */
export const S2S_GITHUB_JSON_MAX_BYTES = 1_048_576 as const
export const S2S_NUMERIC_CANDIDATE_MAX_BYTES = 60 * 1_048_576

// One MiB remains available inside the four-MiB adjudication archive for the
// control member and stored-ZIP framing; the archive cap is checked separately.
export const S2S_NUMERIC_ADJUDICATION_MAX_BYTES = 3 * 1_048_576
