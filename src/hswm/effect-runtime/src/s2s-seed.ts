import { createHash } from "node:crypto"

import { Data, Either } from "effect"

export const S2S_EXTERNAL_SEED_DOMAIN =
  "HSWM-SWM0W-S2S-EXTERNAL-SEED-V1" as const

export interface S2SExternalSeedInput {
  readonly beaconChainHashHex: string
  readonly round: number
  readonly verifiedRandomnessHex: string
  readonly futureRoundCommitmentSelfHashHex: string
}

export interface S2SExternalSeedDerivation {
  readonly domain: typeof S2S_EXTERNAL_SEED_DOMAIN
  readonly materialByteLength: 139
  readonly materialHex: string
  readonly externalSeedHex: string
}

export class S2SExternalSeedDerivationError extends Data.TaggedError(
  "S2SExternalSeedDerivationError"
)<{
  readonly reason:
    | "INVALID_BEACON_CHAIN_HASH"
    | "INVALID_COMMITMENT_SELF_HASH"
    | "INVALID_RANDOMNESS"
    | "INVALID_ROUND"
}> {}

const HEX_32_BYTES = /^[0-9a-f]{64}$/

/**
 * Derive the one external seed without clock, randomness, network, or file I/O.
 * The five raw components are separated by exactly four NUL bytes.
 */
export const deriveS2SExternalSeed = (
  input: S2SExternalSeedInput
): Either.Either<S2SExternalSeedDerivation, S2SExternalSeedDerivationError> => {
  if (!HEX_32_BYTES.test(input.beaconChainHashHex)) {
    return Either.left(
      new S2SExternalSeedDerivationError({
        reason: "INVALID_BEACON_CHAIN_HASH"
      })
    )
  }
  if (!HEX_32_BYTES.test(input.verifiedRandomnessHex)) {
    return Either.left(
      new S2SExternalSeedDerivationError({ reason: "INVALID_RANDOMNESS" })
    )
  }
  if (!HEX_32_BYTES.test(input.futureRoundCommitmentSelfHashHex)) {
    return Either.left(
      new S2SExternalSeedDerivationError({
        reason: "INVALID_COMMITMENT_SELF_HASH"
      })
    )
  }
  if (!Number.isSafeInteger(input.round) || input.round <= 0) {
    return Either.left(
      new S2SExternalSeedDerivationError({ reason: "INVALID_ROUND" })
    )
  }

  const roundBytes = Buffer.alloc(8)
  roundBytes.writeBigUInt64BE(BigInt(input.round))
  const separator = Buffer.from([0])
  const material = Buffer.concat([
    Buffer.from(S2S_EXTERNAL_SEED_DOMAIN, "ascii"),
    separator,
    Buffer.from(input.beaconChainHashHex, "hex"),
    separator,
    roundBytes,
    separator,
    Buffer.from(input.verifiedRandomnessHex, "hex"),
    separator,
    Buffer.from(input.futureRoundCommitmentSelfHashHex, "hex")
  ])
  const externalSeedHex = createHash("sha256").update(material).digest("hex")
  return Either.right(
    Object.freeze({
      domain: S2S_EXTERNAL_SEED_DOMAIN,
      materialByteLength: 139,
      materialHex: material.toString("hex"),
      externalSeedHex
    })
  )
}
