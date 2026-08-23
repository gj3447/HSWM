import { createHash } from "node:crypto"
import { constants } from "node:fs"
import {
  chmod,
  lstat,
  mkdtemp,
  open,
  realpath,
  rm,
  type FileHandle
} from "node:fs/promises"
import { tmpdir } from "node:os"
import { isAbsolute, join, resolve } from "node:path"

import { Context, Data, Effect, Either, Layer, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  runS2SBoundedProcess,
  type S2SBoundedProcessError
} from "./s2s-bounded-process.js"
import { S2SSha256Schema, type S2SSha256 } from "./s2s-confirmatory.js"
import {
  S2S_QUICKNET_CHAIN_HASH,
  S2S_QUICKNET_GENESIS_TIME,
  S2S_QUICKNET_PERIOD_SECONDS,
  s2sQuicknetRoundTimeUnix
} from "./s2s-quicknet.js"
import { deriveS2SExternalSeed } from "./s2s-seed.js"

export const S2S_DRAND_FIXTURE_SCHEMA_VERSION =
  "hswm-swm0w-drand-official-pulse-fixture/v1" as const
export const S2S_DRAND_RECEIPT_SCHEMA_VERSION =
  "hswm-swm0w-drand-verification-receipt/v1" as const
export const S2S_DRAND_HELPER_VERSION =
  "hswm-swm0w-drand-node-verifier/v1" as const
export const S2S_DRAND_EXACT_PULSE_MAX_BYTES = 65_536 as const
export const S2S_DRAND_RECEIPT_MAX_BYTES = 16_384 as const
export const S2S_DRAND_VERIFIER_TIMEOUT_MILLIS = 120_000 as const

export const S2S_DRAND_HELPER_SHA256 =
  "0f0643c67cb18ec0e760c087d0b6a95d5f5b3fcc063686fec42e0a03d6390fc6" as const
export const S2S_DRAND_TOOL_PACKAGE_JSON_SHA256 =
  "128b8bb80d427414497ef513808103e395da1abcedd6be7264275d78a81e798d" as const
export const S2S_DRAND_PACKAGE_LOCK_SHA256 =
  "ca0acb4a88ab7e1ade131e9e2f2fecc7d716b8cfb788922c172f4dbcd9eb4be6" as const
export const S2S_DRAND_CLIENT_PACKAGE_JSON_SHA256 =
  "71271cae1994991202a8e717923560d62db0c615e19e31e9a60f40b92d8ee9f7" as const
export const S2S_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256 =
  "c5f6eff0d5692efd8f2e19953a49713d17554739016f9d0f3235380aab9ea904" as const
export const S2S_DRAND_NODE_EXECUTABLE_SHA256 =
  "53fb205ae78805130177e24bcb459a69a1518c8d98f8965f31d85aae7ea840fc" as const
export const S2S_DRAND_NODE_VERSION = "v24.13.0" as const

const DRAND_TOOL_RELATIVE_ROOT = "tools/swm0w_drand"
const DRAND_HELPER_RELATIVE_PATH = "verify-beacon.mjs"
const DRAND_TOOL_PACKAGE_RELATIVE_PATH = "package.json"
const DRAND_LOCK_RELATIVE_PATH = "package-lock.json"
const DRAND_CLIENT_PACKAGE_RELATIVE_PATH =
  "node_modules/drand-client/package.json"
const DRAND_CLIENT_BUNDLE_RELATIVE_PATH =
  "node_modules/drand-client/build/esm/index.mjs"
const PINNED_FILE_MAX_BYTES = 8 * 1_048_576
const NODE_EXECUTABLE_MAX_BYTES = 128 * 1_048_576
const DRAND_STDERR_MAX_BYTES = 8_192
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true })

const PINNED_CHAIN = Object.freeze({
  beacon_id: "quicknet" as const,
  genesis_time: S2S_QUICKNET_GENESIS_TIME,
  group_hash:
    "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e" as const,
  hash: S2S_QUICKNET_CHAIN_HASH,
  period: S2S_QUICKNET_PERIOD_SECONDS,
  public_key:
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a" as const,
  scheme_id: "bls-unchained-g1-rfc9380" as const
})

const PINNED_VERIFIER = Object.freeze({
  git_commit: "ef8c9260294f8699b5e8c27a6b764f8f0d768bea" as const,
  git_tag_url:
    "https://github.com/drand/drand-client/tree/v1.4.2" as const,
  helper_sha256: S2S_DRAND_HELPER_SHA256,
  npm_integrity:
    "sha512-jeNJmrVplfgIA/GVndxxJ5mo8y63BS2pEdNhk1siU4pQ+z/BnxsqRnxjH9ag1ip887s12SEgo0MTZPbQNz27NA==" as const,
  npm_shasum: "f9108eef6881e62c0c0f154f30f7bd0a818ea809" as const,
  package: "drand-client" as const,
  package_json_sha256: S2S_DRAND_CLIENT_PACKAGE_JSON_SHA256,
  package_lock_sha256: S2S_DRAND_PACKAGE_LOCK_SHA256,
  runtime_bundle_sha256: S2S_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256,
  runtime_engine: "Node.js" as const,
  runtime_exec_sha256: S2S_DRAND_NODE_EXECUTABLE_SHA256,
  runtime_trust_status:
    "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED" as const,
  runtime_version: S2S_DRAND_NODE_VERSION,
  source_tarball:
    "https://registry.npmjs.org/drand-client/-/drand-client-1.4.2.tgz" as const,
  version: "1.4.2" as const
})

const Hex32Schema = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Hex48Schema = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{96}$/))
const Hex96Schema = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{192}$/))
const GitShaSchema = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{40}$/))
const PositiveSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER)
)

const CommittedRequestSchema = Schema.Struct({
  beaconId: Schema.Literal("quicknet"),
  beaconChainHashHex: Schema.Literal(S2S_QUICKNET_CHAIN_HASH),
  futureRound: PositiveSafeIntegerSchema,
  futureRoundCommitmentSelfHashSha256: Hex32Schema
})

const ExactPulseSchema = Schema.Struct({
  randomness: Hex32Schema,
  round: PositiveSafeIntegerSchema,
  signature: Hex48Schema
})

const ReceiptChainSchema = Schema.Struct({
  beacon_id: Schema.String,
  genesis_time: PositiveSafeIntegerSchema,
  group_hash: Hex32Schema,
  hash: Hex32Schema,
  period: PositiveSafeIntegerSchema,
  public_key: Hex96Schema,
  scheme_id: Schema.String
})

const ReceiptPulseSchema = Schema.Struct({
  randomness: Hex32Schema,
  round: PositiveSafeIntegerSchema,
  round_time_unix: PositiveSafeIntegerSchema,
  signature: Hex48Schema
})

const ReceiptVerificationSchema = Schema.Struct({
  accepted_beacon_sha256: Hex32Schema,
  accepted_by: Schema.Literal("drand-client.fetchBeacon"),
  network_policy: Schema.Literal("OFFLINE_INJECTED_CLIENT_FETCH_GUARD"),
  randomness_derivation: Schema.Literal("SHA256(raw_signature_bytes)"),
  signature_scheme: Schema.Literal("bls-unchained-g1-rfc9380")
})

const ReceiptVerifierSchema = Schema.Struct({
  git_commit: GitShaSchema,
  git_tag_url: Schema.String,
  helper_sha256: Hex32Schema,
  npm_integrity: Schema.String,
  npm_shasum: GitShaSchema,
  package: Schema.String,
  package_json_sha256: Hex32Schema,
  package_lock_sha256: Hex32Schema,
  runtime_bundle_sha256: Hex32Schema,
  runtime_engine: Schema.String,
  runtime_exec_sha256: Hex32Schema,
  runtime_trust_status: Schema.String,
  runtime_version: Schema.String,
  source_tarball: Schema.String,
  version: Schema.String
})

export const S2SDrandVerificationReceiptSchema = Schema.Struct({
  chain: ReceiptChainSchema,
  chronology_claim_allowed: Schema.Literal(false),
  helper_version: Schema.Literal(S2S_DRAND_HELPER_VERSION),
  input_fixture_sha256: Hex32Schema,
  mode: Schema.Literal("offline"),
  pulse: ReceiptPulseSchema,
  pulse_source_url: Schema.String,
  receipt_sha256: Hex32Schema,
  schema_version: Schema.Literal(S2S_DRAND_RECEIPT_SCHEMA_VERSION),
  verification: ReceiptVerificationSchema,
  verified_at_unix: PositiveSafeIntegerSchema,
  verifier: ReceiptVerifierSchema
})

export type S2SDrandVerificationReceipt = Schema.Schema.Type<
  typeof S2SDrandVerificationReceiptSchema
>

export interface S2SCommittedDrandPulseRequest {
  readonly beaconId: "quicknet"
  readonly beaconChainHashHex: typeof S2S_QUICKNET_CHAIN_HASH
  readonly futureRound: number
  readonly futureRoundCommitmentSelfHashSha256: string
}

export interface S2SExactDrandPulseRequest {
  readonly chainHashHex: typeof S2S_QUICKNET_CHAIN_HASH
  readonly round: number
  readonly url: string
  readonly maximumResponseBytes: typeof S2S_DRAND_EXACT_PULSE_MAX_BYTES
}

export interface S2SDrandProcessConfig {
  readonly repositoryRoot: string
  readonly nodeExecutable: string
  readonly timeoutMillis?: number
}

export interface S2SVerifiedDrandPulse {
  readonly beaconId: "quicknet"
  readonly beaconChainHashHex: typeof S2S_QUICKNET_CHAIN_HASH
  readonly round: number
  readonly roundTimeUnix: number
  readonly randomnessHex: string
  readonly signatureHex: string
  readonly pulseSourceUrl: string
  readonly futureRoundCommitmentSelfHashSha256: S2SSha256
  readonly externalSeedHex: S2SSha256
  readonly exactPulseRawSha256: S2SSha256
  readonly exactPulseByteLength: number
  readonly inputFixtureSha256: S2SSha256
  readonly acceptedBeaconSha256: S2SSha256
  readonly verificationReceiptSha256: S2SSha256
  readonly receiptRawSha256: S2SSha256
  readonly stableProjectionSha256: S2SSha256
  readonly receiptByteLength: number
  readonly verifiedAtUnix: number
  readonly commandElapsedNanoseconds: number
  /** A new copy is returned on every access. */
  readonly exactPulseBytes: Uint8Array
  /** A new copy is returned on every access. */
  readonly receiptBytes: Uint8Array
}

export class S2SExactDrandPulseSourceError extends Data.TaggedError(
  "S2SExactDrandPulseSourceError"
)<{
  readonly reason: "INTERRUPTED_OR_TIMED_OUT" | "SOURCE_FAILED"
  readonly detail: string
}> {}

/**
 * A deliberately narrow port. Implementations may fetch only the URL and
 * round supplied here; there is no latest-round or round-selection operation.
 */
export class S2SExactDrandPulseSource extends Context.Tag(
  "hswm/S2S/ExactDrandPulseSource"
)<
  S2SExactDrandPulseSource,
  {
    readonly acquireExact: (
      request: S2SExactDrandPulseRequest
    ) => Effect.Effect<Uint8Array, S2SExactDrandPulseSourceError>
  }
>() {}

export class S2SLiveDrandVerificationError extends Data.TaggedError(
  "S2SLiveDrandVerificationError"
)<{
  readonly reason:
    | "CONFIGURATION_INVALID"
    | "FILESYSTEM_FAILED"
    | "PROCESS_FAILED"
    | "PROVENANCE_MISMATCH"
    | "PULSE_CONTRACT_REJECTED"
    | "RECEIPT_CONTRACT_REJECTED"
    | "REQUEST_CONTRACT_REJECTED"
    | "SEED_DERIVATION_FAILED"
    | "SOURCE_FAILED"
    | "STDERR_CONTRACT_REJECTED"
    | "VERIFICATION_REJECTED"
    | "VERIFIER_TIMED_OUT"
  readonly exitCode: number | null
  readonly detail: string
}> {}

export class S2SLiveDrandVerifier extends Context.Tag(
  "hswm/S2S/LiveDrandVerifier"
)<
  S2SLiveDrandVerifier,
  {
    readonly verifyCommitted: (
      request: S2SCommittedDrandPulseRequest
    ) => Effect.Effect<S2SVerifiedDrandPulse, S2SLiveDrandVerificationError>
  }
>() {}

interface PreparedRequest {
  readonly beaconId: "quicknet"
  readonly beaconChainHashHex: typeof S2S_QUICKNET_CHAIN_HASH
  readonly futureRound: number
  readonly futureRoundCommitmentSelfHashSha256: S2SSha256
  readonly pulseSourceUrl: string
}

interface ExactPulse {
  readonly randomness: string
  readonly round: number
  readonly signature: string
}

interface PreparedDrandConfig {
  readonly repositoryRoot: string
  readonly toolRoot: string
  readonly helperPath: string
  readonly nodeExecutable: string
  readonly nodeExecutableRealPath: string
  readonly timeoutMillis: number
}

interface PinnedNodeExecutable {
  readonly handle: FileHandle
  readonly procExecutablePath: string
}

interface PrivateFixture {
  readonly root: string
  readonly path: string
}

const verificationError = (
  reason: S2SLiveDrandVerificationError["reason"],
  detail: string,
  exitCode: number | null = null
): S2SLiveDrandVerificationError =>
  new S2SLiveDrandVerificationError({ reason, exitCode, detail })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameCanonicalValue = (left: unknown, right: unknown): boolean => {
  const leftHash = canonicalS2SControlSha256(left)
  const rightHash = canonicalS2SControlSha256(right)
  return (
    Either.isRight(leftHash) &&
    Either.isRight(rightHash) &&
    leftHash.right === rightHash.right
  )
}

const exactPulseUrl = (round: number): string =>
  `https://api.drand.sh/${S2S_QUICKNET_CHAIN_HASH}/public/${round}`

const isPlainRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  (Object.getPrototypeOf(value) === Object.prototype ||
    Object.getPrototypeOf(value) === null)

const snapshotRequest = (
  input: unknown
): Either.Either<PreparedRequest, S2SLiveDrandVerificationError> => {
  if (!isPlainRecord(input)) {
    return Either.left(
      verificationError(
        "REQUEST_CONTRACT_REJECTED",
        "committed pulse request must be one plain data record"
      )
    )
  }
  const expectedKeys = [
    "beaconChainHashHex",
    "beaconId",
    "futureRound",
    "futureRoundCommitmentSelfHashSha256"
  ]
  const keys = Reflect.ownKeys(input)
  if (
    keys.some((key) => typeof key !== "string") ||
    keys.length !== expectedKeys.length ||
    !keys
      .filter((key): key is string => typeof key === "string")
      .sort()
      .every((key, index) => key === expectedKeys[index])
  ) {
    return Either.left(
      verificationError(
        "REQUEST_CONTRACT_REJECTED",
        "committed pulse request keys differ from the exact contract"
      )
    )
  }
  const snapshot: Record<string, unknown> = {}
  for (const key of expectedKeys) {
    const descriptor = Object.getOwnPropertyDescriptor(input, key)
    if (
      descriptor === undefined ||
      descriptor.enumerable !== true ||
      !("value" in descriptor)
    ) {
      return Either.left(
        verificationError(
          "REQUEST_CONTRACT_REJECTED",
          "committed pulse request must not contain accessors"
        )
      )
    }
    snapshot[key] = descriptor.value
  }
  const decoded = Schema.decodeUnknownEither(CommittedRequestSchema, {
    onExcessProperty: "error"
  })(snapshot)
  if (Either.isLeft(decoded)) {
    return Either.left(
      verificationError(
        "REQUEST_CONTRACT_REJECTED",
        "committed pulse identity, chain, round, or commitment is invalid"
      )
    )
  }
  if (s2sQuicknetRoundTimeUnix(decoded.right.futureRound) === null) {
    return Either.left(
      verificationError(
        "REQUEST_CONTRACT_REJECTED",
        "committed round has no exact Quicknet time representation"
      )
    )
  }
  return Either.right(
    Object.freeze({
      beaconId: "quicknet",
      beaconChainHashHex: S2S_QUICKNET_CHAIN_HASH,
      futureRound: decoded.right.futureRound,
      futureRoundCommitmentSelfHashSha256: S2SSha256Schema.make(
        decoded.right.futureRoundCommitmentSelfHashSha256
      ),
      pulseSourceUrl: exactPulseUrl(decoded.right.futureRound)
    })
  )
}

const snapshotBoundedBytes = (
  input: unknown,
  maximumBytes: number,
  reason: "PULSE_CONTRACT_REJECTED" | "RECEIPT_CONTRACT_REJECTED"
): Either.Either<Uint8Array, S2SLiveDrandVerificationError> => {
  if (
    !(input instanceof Uint8Array) ||
    Object.getPrototypeOf(input) !== Uint8Array.prototype ||
    Object.getOwnPropertySymbols(input).length !== 0 ||
    input.byteLength < 2 ||
    input.byteLength > maximumBytes ||
    (typeof SharedArrayBuffer !== "undefined" &&
      input.buffer instanceof SharedArrayBuffer)
  ) {
    return Either.left(
      verificationError(reason, "bytes violate the fixed unshared byte bound")
    )
  }
  return Either.right(new Uint8Array(input))
}

const decodeExactPulse = (
  bytes: Uint8Array,
  expectedRound: number
): Either.Either<ExactPulse, S2SLiveDrandVerificationError> => {
  if (bytes.some((byte) => byte > 0x7f || byte === 0x00)) {
    return Either.left(
      verificationError(
        "PULSE_CONTRACT_REJECTED",
        "exact pulse source is not bounded ASCII JSON"
      )
    )
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(UTF8_DECODER.decode(bytes))
  } catch {
    return Either.left(
      verificationError(
        "PULSE_CONTRACT_REJECTED",
        "exact pulse source is not valid UTF-8 JSON"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(ExactPulseSchema, {
    onExcessProperty: "error"
  })(parsed)
  if (Either.isLeft(decoded) || decoded.right.round !== expectedRound) {
    return Either.left(
      verificationError(
        "PULSE_CONTRACT_REJECTED",
        "pulse fields or round differ from the committed exact round"
      )
    )
  }
  const derivedRandomness = createHash("sha256")
    .update(Buffer.from(decoded.right.signature, "hex"))
    .digest("hex")
  if (derivedRandomness !== decoded.right.randomness) {
    return Either.left(
      verificationError(
        "PULSE_CONTRACT_REJECTED",
        "pulse randomness is not SHA256 of its signature bytes"
      )
    )
  }
  return Either.right(
    Object.freeze({
      randomness: decoded.right.randomness,
      round: decoded.right.round,
      signature: decoded.right.signature
    })
  )
}

const buildOfflineFixture = (
  request: PreparedRequest,
  pulse: ExactPulse
): Either.Either<Uint8Array, S2SLiveDrandVerificationError> => {
  const encoded = canonicalS2SControlJsonBytes({
    chain_hash: request.beaconChainHashHex,
    pulse,
    schema_version: S2S_DRAND_FIXTURE_SCHEMA_VERSION,
    source_url: request.pulseSourceUrl
  })
  if (
    Either.isLeft(encoded) ||
    encoded.right.byteLength > S2S_DRAND_EXACT_PULSE_MAX_BYTES
  ) {
    return Either.left(
      verificationError(
        "PULSE_CONTRACT_REJECTED",
        "private offline fixture could not be canonically bounded"
      )
    )
  }
  return Either.right(encoded.right)
}

const readPinnedFile = async (
  path: string,
  expectedSha256: string,
  maximumBytes: number
): Promise<void> => {
  const resolvedPath = resolve(path)
  if ((await realpath(resolvedPath)) !== resolvedPath) {
    throw verificationError(
      "PROVENANCE_MISMATCH",
      "a pinned drand provenance path is indirect"
    )
  }
  const handle = await open(resolvedPath, constants.O_RDONLY | constants.O_NOFOLLOW)
  try {
    const stat = await handle.stat()
    if (!stat.isFile() || stat.size < 1 || stat.size > maximumBytes) {
      throw verificationError(
        "PROVENANCE_MISMATCH",
        "a pinned drand provenance file violates its byte bound"
      )
    }
    const bytes = new Uint8Array(await handle.readFile())
    if (
      bytes.byteLength !== stat.size ||
      rawS2SFileSha256(bytes) !== expectedSha256
    ) {
      throw verificationError(
        "PROVENANCE_MISMATCH",
        "a pinned drand provenance file differs from its reviewed SHA-256"
      )
    }
  } finally {
    await handle.close()
  }
}

const prepareConfig = async (
  input: S2SDrandProcessConfig
): Promise<PreparedDrandConfig> => {
  const timeoutMillis = input.timeoutMillis ?? S2S_DRAND_VERIFIER_TIMEOUT_MILLIS
  if (
    process.platform !== "linux" ||
    !isAbsolute(input.repositoryRoot) ||
    !isAbsolute(input.nodeExecutable) ||
    input.repositoryRoot.includes("\0") ||
    input.nodeExecutable.includes("\0") ||
    !Number.isSafeInteger(timeoutMillis) ||
    timeoutMillis < 1 ||
    timeoutMillis > S2S_DRAND_VERIFIER_TIMEOUT_MILLIS
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "drand process configuration violates the fixed Linux boundary"
    )
  }
  const requestedRoot = resolve(input.repositoryRoot)
  const rootStat = await lstat(requestedRoot)
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "repository root must be a plain directory"
    )
  }
  const repositoryRoot = await realpath(requestedRoot)
  const toolRoot = join(repositoryRoot, DRAND_TOOL_RELATIVE_ROOT)
  if ((await realpath(toolRoot)) !== toolRoot) {
    throw verificationError(
      "PROVENANCE_MISMATCH",
      "drand tool root is not the reviewed direct path"
    )
  }
  const toolStat = await lstat(toolRoot)
  if (toolStat.isSymbolicLink() || !toolStat.isDirectory()) {
    throw verificationError(
      "PROVENANCE_MISMATCH",
      "drand tool root is not a plain directory"
    )
  }
  const nodeExecutable = resolve(input.nodeExecutable)
  const nodeExecutableRealPath = await realpath(nodeExecutable)
  const nodeStat = await lstat(nodeExecutableRealPath)
  if (
    !nodeStat.isFile() ||
    (nodeStat.mode & 0o111) === 0 ||
    nodeStat.size < 1 ||
    nodeStat.size > NODE_EXECUTABLE_MAX_BYTES
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "resolved Node executable is not one bounded executable file"
    )
  }
  await readPinnedFile(
    nodeExecutableRealPath,
    S2S_DRAND_NODE_EXECUTABLE_SHA256,
    NODE_EXECUTABLE_MAX_BYTES
  )
  await Promise.all([
    readPinnedFile(
      join(toolRoot, DRAND_HELPER_RELATIVE_PATH),
      S2S_DRAND_HELPER_SHA256,
      PINNED_FILE_MAX_BYTES
    ),
    readPinnedFile(
      join(toolRoot, DRAND_TOOL_PACKAGE_RELATIVE_PATH),
      S2S_DRAND_TOOL_PACKAGE_JSON_SHA256,
      PINNED_FILE_MAX_BYTES
    ),
    readPinnedFile(
      join(toolRoot, DRAND_LOCK_RELATIVE_PATH),
      S2S_DRAND_PACKAGE_LOCK_SHA256,
      PINNED_FILE_MAX_BYTES
    ),
    readPinnedFile(
      join(toolRoot, DRAND_CLIENT_PACKAGE_RELATIVE_PATH),
      S2S_DRAND_CLIENT_PACKAGE_JSON_SHA256,
      PINNED_FILE_MAX_BYTES
    ),
    readPinnedFile(
      join(toolRoot, DRAND_CLIENT_BUNDLE_RELATIVE_PATH),
      S2S_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256,
      PINNED_FILE_MAX_BYTES
    )
  ])
  return Object.freeze({
    repositoryRoot,
    toolRoot,
    helperPath: join(toolRoot, DRAND_HELPER_RELATIVE_PATH),
    nodeExecutable,
    nodeExecutableRealPath,
    timeoutMillis
  })
}

const openPinnedNodeExecutable = async (
  config: PreparedDrandConfig
): Promise<PinnedNodeExecutable> => {
  if ((await realpath(config.nodeExecutable)) !== config.nodeExecutableRealPath) {
    throw verificationError(
      "PROVENANCE_MISMATCH",
      "Node executable link target changed after preflight"
    )
  }
  const handle = await open(
    config.nodeExecutableRealPath,
    constants.O_RDONLY | constants.O_NOFOLLOW
  )
  try {
    const stat = await handle.stat()
    const bytes = new Uint8Array(await handle.readFile())
    if (
      !stat.isFile() ||
      stat.size < 1 ||
      stat.size > NODE_EXECUTABLE_MAX_BYTES ||
      bytes.byteLength !== stat.size ||
      rawS2SFileSha256(bytes) !== S2S_DRAND_NODE_EXECUTABLE_SHA256 ||
      !Number.isSafeInteger(handle.fd) ||
      handle.fd < 0
    ) {
      throw verificationError(
        "PROVENANCE_MISMATCH",
        "opened Node executable inode differs from its runtime pin"
      )
    }
    return {
      handle,
      procExecutablePath: `/proc/${process.pid}/fd/${handle.fd}`
    }
  } catch (error) {
    await handle.close()
    throw error
  }
}

const acquirePrivateFixture = async (
  fixtureBytes: Uint8Array
): Promise<PrivateFixture> => {
  const root = await mkdtemp(join(tmpdir(), "hswm-s2s-drand-"))
  try {
    await chmod(root, 0o700)
    const rootStat = await lstat(root)
    if (
      rootStat.isSymbolicLink() ||
      !rootStat.isDirectory() ||
      (rootStat.mode & 0o077) !== 0
    ) {
      throw verificationError(
        "FILESYSTEM_FAILED",
        "private drand fixture root is not a private directory"
      )
    }
    const privateRoot = await realpath(root)
    const path = join(privateRoot, "pulse.json")
    const handle = await open(
      path,
      constants.O_CREAT |
        constants.O_EXCL |
        constants.O_WRONLY |
        constants.O_NOFOLLOW,
      0o600
    )
    try {
      await handle.writeFile(fixtureBytes)
      await handle.sync()
      const stat = await handle.stat()
      if (
        !stat.isFile() ||
        stat.size !== fixtureBytes.byteLength ||
        (stat.mode & 0o077) !== 0
      ) {
        throw verificationError(
          "FILESYSTEM_FAILED",
          "private drand fixture write was not exact and private"
        )
      }
    } finally {
      await handle.close()
    }
    return Object.freeze({ root: privateRoot, path })
  } catch (error) {
    await rm(root, { force: true, recursive: true })
    throw error
  }
}

const mapProcessError = (
  error: S2SBoundedProcessError
): S2SLiveDrandVerificationError =>
  verificationError(
    error.reason === "TIMED_OUT" ? "VERIFIER_TIMED_OUT" : "PROCESS_FAILED",
    `bounded offline drand verifier rejected: ${error.reason}`,
    error.exitCode
  )

const runOfflineHelper = (
  config: PreparedDrandConfig,
  fixture: PrivateFixture,
  round: number
) =>
  Effect.acquireUseRelease(
    Effect.tryPromise({
      try: () => openPinnedNodeExecutable(config),
      catch: (error) =>
        error instanceof S2SLiveDrandVerificationError
          ? error
          : verificationError(
              "PROVENANCE_MISMATCH",
              "Node executable inode could not be pinned"
            )
    }),
    (pinned) =>
      runS2SBoundedProcess({
        operation: "DRAND_OFFLINE_VERIFY",
        executable: pinned.procExecutablePath,
        argv0: config.nodeExecutable,
        arguments: [
          config.helperPath,
          "offline",
          "--expected-round",
          String(round),
          "--pulse-file",
          fixture.path
        ],
        cwd: config.toolRoot,
        environment: Object.freeze({
          LANG: "C",
          LC_ALL: "C",
          PATH: "/usr/bin:/bin",
          TZ: "UTC"
        }),
        stdin: null,
        timeoutMillis: config.timeoutMillis,
        stdoutLimitBytes: S2S_DRAND_RECEIPT_MAX_BYTES,
        stderrLimitBytes: DRAND_STDERR_MAX_BYTES
      }).pipe(Effect.mapError(mapProcessError)),
    (pinned) =>
      Effect.tryPromise({
        try: () => pinned.handle.close(),
        catch: () =>
          verificationError(
            "PROVENANCE_MISMATCH",
            "pinned Node executable handle could not be closed"
          )
      }).pipe(Effect.orDie)
  )

const receiptUnsigned = (receipt: S2SDrandVerificationReceipt) => ({
  chain: receipt.chain,
  chronology_claim_allowed: receipt.chronology_claim_allowed,
  helper_version: receipt.helper_version,
  input_fixture_sha256: receipt.input_fixture_sha256,
  mode: receipt.mode,
  pulse: receipt.pulse,
  pulse_source_url: receipt.pulse_source_url,
  schema_version: receipt.schema_version,
  verification: receipt.verification,
  verified_at_unix: receipt.verified_at_unix,
  verifier: receipt.verifier
})

const receiptStableProjection = (receipt: S2SDrandVerificationReceipt) => ({
  chain: receipt.chain,
  chronology_claim_allowed: receipt.chronology_claim_allowed,
  helper_version: receipt.helper_version,
  input_fixture_sha256: receipt.input_fixture_sha256,
  mode: receipt.mode,
  pulse: receipt.pulse,
  pulse_source_url: receipt.pulse_source_url,
  schema_version: receipt.schema_version,
  verification: receipt.verification,
  verifier: receipt.verifier
})

const makeDefensiveResult = (
  receipt: S2SDrandVerificationReceipt,
  exactPulseBytes: Uint8Array,
  receiptBytes: Uint8Array,
  request: PreparedRequest,
  externalSeedHex: S2SSha256,
  stableProjectionSha256: S2SSha256,
  commandElapsedNanoseconds: number
): S2SVerifiedDrandPulse => {
  const exactPulseSnapshot = new Uint8Array(exactPulseBytes)
  const receiptSnapshot = new Uint8Array(receiptBytes)
  return Object.freeze({
    beaconId: "quicknet" as const,
    beaconChainHashHex: S2S_QUICKNET_CHAIN_HASH,
    round: receipt.pulse.round,
    roundTimeUnix: receipt.pulse.round_time_unix,
    randomnessHex: receipt.pulse.randomness,
    signatureHex: receipt.pulse.signature,
    pulseSourceUrl: receipt.pulse_source_url,
    futureRoundCommitmentSelfHashSha256:
      request.futureRoundCommitmentSelfHashSha256,
    externalSeedHex,
    exactPulseRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(exactPulseSnapshot)
    ),
    exactPulseByteLength: exactPulseSnapshot.byteLength,
    inputFixtureSha256: S2SSha256Schema.make(receipt.input_fixture_sha256),
    acceptedBeaconSha256: S2SSha256Schema.make(
      receipt.verification.accepted_beacon_sha256
    ),
    verificationReceiptSha256: S2SSha256Schema.make(receipt.receipt_sha256),
    receiptRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(receiptSnapshot)
    ),
    stableProjectionSha256,
    receiptByteLength: receiptSnapshot.byteLength,
    verifiedAtUnix: receipt.verified_at_unix,
    commandElapsedNanoseconds,
    get exactPulseBytes(): Uint8Array {
      return new Uint8Array(exactPulseSnapshot)
    },
    get receiptBytes(): Uint8Array {
      return new Uint8Array(receiptSnapshot)
    }
  })
}

const validateReceipt = (
  receiptBytes: Uint8Array,
  request: PreparedRequest,
  pulse: ExactPulse,
  exactPulseBytes: Uint8Array,
  fixtureBytes: Uint8Array,
  commandElapsedNanoseconds: number
): Either.Either<S2SVerifiedDrandPulse, S2SLiveDrandVerificationError> => {
  if (
    receiptBytes[receiptBytes.byteLength - 1] !== 0x0a ||
    receiptBytes.some((byte) => byte > 0x7f) ||
    receiptBytes
      .subarray(0, receiptBytes.byteLength - 1)
      .some((byte) => byte === 0x0a || byte === 0x0d)
  ) {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "verifier receipt is not one canonical ASCII line"
      )
    )
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(UTF8_DECODER.decode(receiptBytes))
  } catch {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "verifier receipt is not valid UTF-8 JSON"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(S2SDrandVerificationReceiptSchema, {
    onExcessProperty: "error"
  })(parsed)
  if (Either.isLeft(decoded)) {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "verifier receipt differs from its strict schema"
      )
    )
  }
  const receipt = decoded.right
  const canonicalBytes = canonicalS2SControlJsonBytes(receipt)
  if (Either.isLeft(canonicalBytes) || !sameBytes(canonicalBytes.right, receiptBytes)) {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "verifier receipt bytes are not canonical JSON with one terminal LF"
      )
    )
  }
  if (
    !sameCanonicalValue(receipt.chain, PINNED_CHAIN) ||
    !sameCanonicalValue(receipt.verifier, PINNED_VERIFIER)
  ) {
    return Either.left(
      verificationError(
        "PROVENANCE_MISMATCH",
        "receipt chain or verifier provenance differs from every frozen pin"
      )
    )
  }
  const roundTime = s2sQuicknetRoundTimeUnix(request.futureRound)
  const expectedFixtureSha256 = rawS2SFileSha256(fixtureBytes)
  const expectedBeaconSha256 = canonicalS2SControlSha256(pulse)
  const expectedReceiptSha256 = canonicalS2SControlSha256(
    receiptUnsigned(receipt)
  )
  if (
    roundTime === null ||
    Either.isLeft(expectedBeaconSha256) ||
    Either.isLeft(expectedReceiptSha256) ||
    receipt.input_fixture_sha256 !== expectedFixtureSha256 ||
    receipt.pulse_source_url !== request.pulseSourceUrl ||
    receipt.pulse.round !== request.futureRound ||
    receipt.pulse.round_time_unix !== roundTime ||
    receipt.pulse.randomness !== pulse.randomness ||
    receipt.pulse.signature !== pulse.signature ||
    receipt.verification.accepted_beacon_sha256 !==
      expectedBeaconSha256.right ||
    receipt.receipt_sha256 !== expectedReceiptSha256.right
  ) {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "receipt does not bind the exact request, fixture, pulse, or self hash"
      )
    )
  }
  const seed = deriveS2SExternalSeed({
    beaconChainHashHex: request.beaconChainHashHex,
    round: request.futureRound,
    verifiedRandomnessHex: receipt.pulse.randomness,
    futureRoundCommitmentSelfHashHex:
      request.futureRoundCommitmentSelfHashSha256
  })
  if (Either.isLeft(seed)) {
    return Either.left(
      verificationError(
        "SEED_DERIVATION_FAILED",
        `external seed derivation rejected: ${seed.left.reason}`
      )
    )
  }
  const stableProjectionSha256 = canonicalS2SControlSha256(
    receiptStableProjection(receipt)
  )
  if (Either.isLeft(stableProjectionSha256)) {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "stable receipt projection is not canonical control JSON"
      )
    )
  }
  return Either.right(
    makeDefensiveResult(
      receipt,
      exactPulseBytes,
      receiptBytes,
      request,
      S2SSha256Schema.make(seed.right.externalSeedHex),
      S2SSha256Schema.make(stableProjectionSha256.right),
      commandElapsedNanoseconds
    )
  )
}

/**
 * Pure validation entry point for an already-produced offline receipt. It
 * performs no I/O and is useful for artifact readback/tamper verification.
 */
export const validateS2SDrandVerificationReceipt = (input: {
  readonly request: unknown
  readonly exactPulseBytes: unknown
  readonly receiptBytes: unknown
  readonly commandElapsedNanoseconds: number
}): Either.Either<S2SVerifiedDrandPulse, S2SLiveDrandVerificationError> => {
  const request = snapshotRequest(input.request)
  if (Either.isLeft(request)) return Either.left(request.left)
  const pulseBytes = snapshotBoundedBytes(
    input.exactPulseBytes,
    S2S_DRAND_EXACT_PULSE_MAX_BYTES,
    "PULSE_CONTRACT_REJECTED"
  )
  if (Either.isLeft(pulseBytes)) return Either.left(pulseBytes.left)
  const pulse = decodeExactPulse(pulseBytes.right, request.right.futureRound)
  if (Either.isLeft(pulse)) return Either.left(pulse.left)
  const fixture = buildOfflineFixture(request.right, pulse.right)
  if (Either.isLeft(fixture)) return Either.left(fixture.left)
  const receiptBytes = snapshotBoundedBytes(
    input.receiptBytes,
    S2S_DRAND_RECEIPT_MAX_BYTES,
    "RECEIPT_CONTRACT_REJECTED"
  )
  if (Either.isLeft(receiptBytes)) return Either.left(receiptBytes.left)
  if (
    !Number.isSafeInteger(input.commandElapsedNanoseconds) ||
    input.commandElapsedNanoseconds < 0
  ) {
    return Either.left(
      verificationError(
        "RECEIPT_CONTRACT_REJECTED",
        "command elapsed telemetry must be a nonnegative safe integer"
      )
    )
  }
  return validateReceipt(
    receiptBytes.right,
    request.right,
    pulse.right,
    pulseBytes.right,
    fixture.right,
    input.commandElapsedNanoseconds
  )
}

/**
 * Verify exact supplied pulse bytes. This function never has a network or
 * round-selection capability and always invokes the pinned helper in offline
 * mode through the bounded process boundary.
 */
export const verifyS2SCommittedDrandPulseFromBytes = (
  configInput: S2SDrandProcessConfig,
  requestInput: unknown,
  exactPulseBytesInput: unknown
): Effect.Effect<S2SVerifiedDrandPulse, S2SLiveDrandVerificationError> => {
  const configSnapshot: S2SDrandProcessConfig = Object.freeze({
    repositoryRoot: configInput.repositoryRoot,
    nodeExecutable: configInput.nodeExecutable,
    ...(configInput.timeoutMillis === undefined
      ? {}
      : { timeoutMillis: configInput.timeoutMillis })
  })
  const request = snapshotRequest(requestInput)
  const exactPulseBytes = snapshotBoundedBytes(
    exactPulseBytesInput,
    S2S_DRAND_EXACT_PULSE_MAX_BYTES,
    "PULSE_CONTRACT_REJECTED"
  )
  return Effect.gen(function* () {
    if (Either.isLeft(request)) return yield* Effect.fail(request.left)
    if (Either.isLeft(exactPulseBytes)) {
      return yield* Effect.fail(exactPulseBytes.left)
    }
    const pulse = decodeExactPulse(
      exactPulseBytes.right,
      request.right.futureRound
    )
    if (Either.isLeft(pulse)) return yield* Effect.fail(pulse.left)
    const fixtureBytes = buildOfflineFixture(request.right, pulse.right)
    if (Either.isLeft(fixtureBytes)) {
      return yield* Effect.fail(fixtureBytes.left)
    }
    const config = yield* Effect.tryPromise({
      try: () => prepareConfig(configSnapshot),
      catch: (error) =>
        error instanceof S2SLiveDrandVerificationError
          ? error
          : verificationError(
              "PROVENANCE_MISMATCH",
              "drand process provenance could not be verified"
            )
    })
    const processResult = yield* Effect.acquireUseRelease(
      Effect.tryPromise({
        try: () => acquirePrivateFixture(fixtureBytes.right),
        catch: (error) =>
          error instanceof S2SLiveDrandVerificationError
            ? error
            : verificationError(
                "FILESYSTEM_FAILED",
                "private offline drand fixture could not be created"
              )
      }),
      (privateFixture) =>
        runOfflineHelper(config, privateFixture, request.right.futureRound),
      (privateFixture) =>
        Effect.tryPromise({
          try: () => rm(privateFixture.root, { force: true, recursive: true }),
          catch: () =>
            verificationError(
              "FILESYSTEM_FAILED",
              "private offline drand fixture could not be removed"
            )
        }).pipe(Effect.orDie)
    )
    if (processResult.exitCode !== 0) {
      return yield* Effect.fail(
        verificationError(
          "VERIFICATION_REJECTED",
          "pinned offline drand verifier rejected the exact pulse",
          processResult.exitCode
        )
      )
    }
    if (processResult.stderr.byteLength !== 0) {
      return yield* Effect.fail(
        verificationError(
          "STDERR_CONTRACT_REJECTED",
          "successful offline drand verification emitted stderr",
          processResult.exitCode
        )
      )
    }
    const validated = validateReceipt(
      processResult.stdout,
      request.right,
      pulse.right,
      exactPulseBytes.right,
      fixtureBytes.right,
      processResult.elapsedNanoseconds
    )
    if (Either.isLeft(validated)) {
      return yield* Effect.fail(validated.left)
    }
    return validated.right
  })
}

export const makeS2SExactDrandPulseSourceTestLayer = (
  acquireExact: (
    request: S2SExactDrandPulseRequest
  ) => Effect.Effect<Uint8Array, S2SExactDrandPulseSourceError>
) =>
  Layer.succeed(
    S2SExactDrandPulseSource,
    S2SExactDrandPulseSource.of({ acquireExact })
  )

/**
 * Process-backed adapter layer. It requires an exact-pulse source capability;
 * this module intentionally provides no online implementation of that port.
 */
export const makeS2SLiveDrandVerifierProcessLayer = (
  config: S2SDrandProcessConfig
) =>
  Layer.effect(
    S2SLiveDrandVerifier,
    Effect.gen(function* () {
      const source = yield* S2SExactDrandPulseSource
      return S2SLiveDrandVerifier.of({
        verifyCommitted: (request) => {
          const prepared = snapshotRequest(request)
          if (Either.isLeft(prepared)) return Effect.fail(prepared.left)
          const sourceRequest = Object.freeze({
            chainHashHex: S2S_QUICKNET_CHAIN_HASH,
            round: prepared.right.futureRound,
            url: prepared.right.pulseSourceUrl,
            maximumResponseBytes: S2S_DRAND_EXACT_PULSE_MAX_BYTES
          })
          const committedRequest = Object.freeze({
            beaconId: prepared.right.beaconId,
            beaconChainHashHex: prepared.right.beaconChainHashHex,
            futureRound: prepared.right.futureRound,
            futureRoundCommitmentSelfHashSha256:
              prepared.right.futureRoundCommitmentSelfHashSha256
          })
          return source.acquireExact(sourceRequest).pipe(
            Effect.mapError((error) =>
              verificationError(
                "SOURCE_FAILED",
                `exact pulse source rejected: ${error.reason}`
              )
            ),
            Effect.flatMap((bytes) =>
              verifyS2SCommittedDrandPulseFromBytes(
                config,
                committedRequest,
                bytes
              )
            )
          )
        }
      })
    })
  )
