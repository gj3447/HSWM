import { createHash } from "node:crypto"
import {
  appendFileSync,
  cpSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"
import { beforeAll } from "vitest"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256,
  S2S_DRAND_EXACT_PULSE_MAX_BYTES,
  S2S_DRAND_HELPER_SHA256,
  S2S_DRAND_NODE_EXECUTABLE_SHA256,
  S2S_DRAND_PACKAGE_LOCK_SHA256,
  S2SExactDrandPulseSourceError,
  S2SLiveDrandVerifier,
  makeS2SExactDrandPulseSourceTestLayer,
  makeS2SLiveDrandVerifierProcessLayer,
  validateS2SDrandVerificationReceipt,
  verifyS2SCommittedDrandPulseFromBytes,
  type S2SCommittedDrandPulseRequest,
  type S2SExactDrandPulseRequest,
  type S2SVerifiedDrandPulse
} from "../src/s2s-live-drand.js"
import { S2S_QUICKNET_CHAIN_HASH } from "../src/s2s-quicknet.js"

const PACKAGE_ROOT = process.cwd()
const REPOSITORY_ROOT = resolve(PACKAGE_ROOT, "../../..")
const OFFICIAL_FIXTURE_PATH = join(
  REPOSITORY_ROOT,
  "tools/swm0w_drand/fixtures/quicknet-round-1000.json"
)
const OFFICIAL_FIXTURE_RAW_SHA256 =
  "a6f8a2c86bef9172dfb18fa976b3b4b90b6c6e284c71b7cd29093cdf2709d1b3"
const PRIVATE_FIXTURE_SHA256 =
  "77441b9c58cc32832e4330fa9d84cfea7839ef9ca3e19e6b8a5fb32f8ba8b448"
const STABLE_RECEIPT_PROJECTION_SHA256 =
  "973989a01a5bc37e9278475476df462121292c275e41d6bae3ce5c5f9a92dcb7"
const EXTERNAL_SEED_SHA256 =
  "b462f0ca2e49101ee6e49e888c6f34f9422e6055fcbfb0398b242f3580e0a07b"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)

const officialFixtureRawBytes = new Uint8Array(
  readFileSync(OFFICIAL_FIXTURE_PATH)
)
const officialFixture: unknown = JSON.parse(
  new TextDecoder("utf-8", { fatal: true }).decode(officialFixtureRawBytes)
)
if (!isRecord(officialFixture) || !isRecord(officialFixture["pulse"])) {
  throw new Error("checked-in drand fixture has no pulse object")
}

const encodeCanonical = (value: unknown): Uint8Array => {
  const encoded = canonicalS2SControlJsonBytes(value)
  if (Either.isLeft(encoded)) throw encoded.left
  return encoded.right
}

const exactPulseBytes = encodeCanonical(officialFixture["pulse"])
const exactPulse = officialFixture["pulse"]

const committedRequest: S2SCommittedDrandPulseRequest = Object.freeze({
  beaconId: "quicknet",
  beaconChainHashHex: S2S_QUICKNET_CHAIN_HASH,
  futureRound: 1_000,
  futureRoundCommitmentSelfHashSha256: "11".repeat(32)
})

const processConfig = Object.freeze({
  repositoryRoot: REPOSITORY_ROOT,
  nodeExecutable: process.execPath
})

let observedSourceRequest: S2SExactDrandPulseRequest | null = null
let verifiedFixture: S2SVerifiedDrandPulse | null = null

const exactSourceLayer = makeS2SExactDrandPulseSourceTestLayer((request) =>
  Effect.sync(() => {
    observedSourceRequest = structuredClone(request)
    return new Uint8Array(exactPulseBytes)
  })
)

beforeAll(async () => {
  const verifierLayer = makeS2SLiveDrandVerifierProcessLayer(
    processConfig
  ).pipe(Layer.provide(exactSourceLayer))
  verifiedFixture = await Effect.runPromise(
    Effect.gen(function* () {
      const verifier = yield* S2SLiveDrandVerifier
      return yield* verifier.verifyCommitted(committedRequest)
    }).pipe(Effect.provide(verifierLayer))
  )
})

const requireVerifiedFixture = (): S2SVerifiedDrandPulse => {
  if (verifiedFixture === null) throw new Error("offline fixture setup failed")
  return verifiedFixture
}

const decodeReceipt = (bytes: Uint8Array): Record<string, unknown> => {
  const value: unknown = JSON.parse(
    new TextDecoder("utf-8", { fatal: true }).decode(bytes)
  )
  if (!isRecord(value)) throw new Error("expected receipt object")
  return value
}

const rehashReceipt = (receipt: Record<string, unknown>): Uint8Array => {
  const unsigned: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(receipt)) {
    if (key !== "receipt_sha256") unsigned[key] = value
  }
  const selfHash = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(selfHash)) throw selfHash.left
  receipt["receipt_sha256"] = selfHash.right
  return encodeCanonical(receipt)
}

it("verifies the checked-in pulse offline and freezes stable evidence hashes", () => {
  const result = requireVerifiedFixture()
  expect(rawS2SFileSha256(officialFixtureRawBytes)).toBe(
    OFFICIAL_FIXTURE_RAW_SHA256
  )
  expect(observedSourceRequest).toEqual({
    chainHashHex: S2S_QUICKNET_CHAIN_HASH,
    round: 1_000,
    url: `https://api.drand.sh/${S2S_QUICKNET_CHAIN_HASH}/public/1000`,
    maximumResponseBytes: S2S_DRAND_EXACT_PULSE_MAX_BYTES
  })
  expect(result.round).toBe(1_000)
  expect(result.roundTimeUnix).toBe(1_692_806_364)
  expect(result.randomnessHex).toBe(
    "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
  )
  expect(result.inputFixtureSha256).toBe(PRIVATE_FIXTURE_SHA256)
  expect(result.stableProjectionSha256).toBe(
    STABLE_RECEIPT_PROJECTION_SHA256
  )
  expect(result.externalSeedHex).toBe(EXTERNAL_SEED_SHA256)
  expect(result.receiptRawSha256).toBe(
    rawS2SFileSha256(result.receiptBytes)
  )
  expect(result.receiptByteLength).toBe(result.receiptBytes.byteLength)

  const receipt = decodeReceipt(result.receiptBytes)
  expect(receipt["chronology_claim_allowed"]).toBe(false)
  const verifier = receipt["verifier"]
  expect(isRecord(verifier)).toBe(true)
  if (isRecord(verifier)) {
    expect(verifier["helper_sha256"]).toBe(S2S_DRAND_HELPER_SHA256)
    expect(verifier["package_lock_sha256"]).toBe(
      S2S_DRAND_PACKAGE_LOCK_SHA256
    )
    expect(verifier["runtime_bundle_sha256"]).toBe(
      S2S_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
    )
    expect(verifier["runtime_exec_sha256"]).toBe(
      S2S_DRAND_NODE_EXECUTABLE_SHA256
    )
  }

  const firstCopy = result.receiptBytes
  firstCopy[0] = 0x00
  expect(result.receiptBytes[0]).toBe(0x7b)
  expect(Object.isFrozen(result)).toBe(true)
})

it.effect("rejects a chain other than the exactly committed Quicknet chain", () =>
  Effect.gen(function* () {
    const outcome = yield* verifyS2SCommittedDrandPulseFromBytes(
      processConfig,
      {
        ...committedRequest,
        beaconChainHashHex: "00".repeat(32)
      },
      exactPulseBytes
    ).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("REQUEST_CONTRACT_REJECTED")
    }
  })
)

it.effect("rejects pulse bytes for a round other than the committed round", () =>
  Effect.gen(function* () {
    const wrongRoundBytes = encodeCanonical({
      ...exactPulse,
      round: 1_001
    })
    const outcome = yield* verifyS2SCommittedDrandPulseFromBytes(
      processConfig,
      committedRequest,
      wrongRoundBytes
    ).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("PULSE_CONTRACT_REJECTED")
    }
  })
)

it.effect("lets the pinned BLS verifier reject a wrong signature", () =>
  Effect.gen(function* () {
    const signatureValue = exactPulse["signature"]
    if (typeof signatureValue !== "string") {
      return yield* Effect.dieMessage("fixture signature is not text")
    }
    const signature = `${signatureValue[0] === "0" ? "1" : "0"}${signatureValue.slice(1)}`
    const randomness = createHash("sha256")
      .update(Buffer.from(signature, "hex"))
      .digest("hex")
    const wrongSignatureBytes = encodeCanonical({
      randomness,
      round: 1_000,
      signature
    })
    const outcome = yield* verifyS2SCommittedDrandPulseFromBytes(
      processConfig,
      committedRequest,
      wrongSignatureBytes
    ).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("VERIFICATION_REJECTED")
      expect(outcome.left.exitCode).toBe(1)
    }
  })
)

it.effect("rejects frozen helper provenance drift before execution", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-drand-pin-"))
  const copiedToolRoot = join(temporaryRoot, "tools/swm0w_drand")
  mkdirSync(join(temporaryRoot, "tools"))
  cpSync(join(REPOSITORY_ROOT, "tools/swm0w_drand"), copiedToolRoot, {
    recursive: true
  })
  appendFileSync(join(copiedToolRoot, "verify-beacon.mjs"), "\n// drift\n")
  return Effect.acquireUseRelease(
    Effect.void,
    () =>
      Effect.gen(function* () {
        const outcome = yield* verifyS2SCommittedDrandPulseFromBytes(
          {
            repositoryRoot: temporaryRoot,
            nodeExecutable: process.execPath
          },
          committedRequest,
          exactPulseBytes
        ).pipe(Effect.either)
        expect(Either.isLeft(outcome)).toBe(true)
        if (Either.isLeft(outcome)) {
          expect(outcome.left.reason).toBe("PROVENANCE_MISMATCH")
        }
      }),
    () => Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
  )
})

it.effect("times out and reaps the bounded verifier process", () =>
  Effect.gen(function* () {
    const outcome = yield* verifyS2SCommittedDrandPulseFromBytes(
      {
        ...processConfig,
        timeoutMillis: 1
      },
      committedRequest,
      exactPulseBytes
    ).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("VERIFIER_TIMED_OUT")
    }
  })
)

it("rejects canonical receipt tampering even after the attacker rehashes it", () => {
  const result = requireVerifiedFixture()
  const tampered = decodeReceipt(result.receiptBytes)
  const pulse = tampered["pulse"]
  if (!isRecord(pulse)) throw new Error("expected receipt pulse")
  pulse["randomness"] = "00".repeat(32)
  const outcome = validateS2SDrandVerificationReceipt({
    request: committedRequest,
    exactPulseBytes,
    receiptBytes: rehashReceipt(tampered),
    commandElapsedNanoseconds: result.commandElapsedNanoseconds
  })
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isLeft(outcome)) {
    expect(outcome.left.reason).toBe("RECEIPT_CONTRACT_REJECTED")
  }
})

it("rejects receipt-declared provenance drift even with a valid self hash", () => {
  const result = requireVerifiedFixture()
  const tampered = decodeReceipt(result.receiptBytes)
  const verifier = tampered["verifier"]
  if (!isRecord(verifier)) throw new Error("expected receipt verifier")
  verifier["package_lock_sha256"] = "00".repeat(32)
  const outcome = validateS2SDrandVerificationReceipt({
    request: committedRequest,
    exactPulseBytes,
    receiptBytes: rehashReceipt(tampered),
    commandElapsedNanoseconds: result.commandElapsedNanoseconds
  })
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isLeft(outcome)) {
    expect(outcome.left.reason).toBe("PROVENANCE_MISMATCH")
  }
})

it.effect("maps an exact source failure without acquiring any alternate round", () => {
  const failingSource = makeS2SExactDrandPulseSourceTestLayer(() =>
    Effect.fail(
      new S2SExactDrandPulseSourceError({
        reason: "SOURCE_FAILED",
        detail: "offline test source unavailable"
      })
    )
  )
  const verifierLayer = makeS2SLiveDrandVerifierProcessLayer(
    processConfig
  ).pipe(Layer.provide(failingSource))
  return Effect.gen(function* () {
    const verifier = yield* S2SLiveDrandVerifier
    const outcome = yield* verifier
      .verifyCommitted(committedRequest)
      .pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("SOURCE_FAILED")
    }
  }).pipe(Effect.provide(verifierLayer))
})
