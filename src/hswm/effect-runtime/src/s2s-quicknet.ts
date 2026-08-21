/**
 * Pure Quicknet identity and round-time arithmetic shared by preregistration
 * and confirmatory chronology validation. This module performs no I/O and
 * gives callers no clock, beacon, or future-round selection authority.
 */

export const S2S_QUICKNET_CHAIN_HASH =
  "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971" as const

export const S2S_QUICKNET_GENESIS_TIME = 1_692_803_367 as const
export const S2S_QUICKNET_PERIOD_SECONDS = 3 as const

const MAX_QUICKNET_ROUND =
  Math.floor(
    (Number.MAX_SAFE_INTEGER - S2S_QUICKNET_GENESIS_TIME) /
      S2S_QUICKNET_PERIOD_SECONDS
  ) + 1

/** Returns the exact Unix-second time for a valid safe round, otherwise null. */
export const s2sQuicknetRoundTimeUnix = (round: number): number | null => {
  if (
    !Number.isSafeInteger(round) ||
    round < 1 ||
    round > MAX_QUICKNET_ROUND
  ) {
    return null
  }
  return (
    S2S_QUICKNET_GENESIS_TIME +
    (round - 1) * S2S_QUICKNET_PERIOD_SECONDS
  )
}
