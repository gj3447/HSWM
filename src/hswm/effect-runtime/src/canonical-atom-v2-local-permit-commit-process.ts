#!/usr/bin/env node
/**
 * One-request process bridge for the v1 local Permit commit.
 *
 * A Python research instrument (g1_micro) hands one exact state transition to
 * this process: pre-state bytes, post-state bytes, and the Permit claims that
 * bind them.  The process mints one ephemeral Ed25519 issuer, issues one
 * signed Permit envelope, and commits it through the fsync'd no-replace local
 * journal slot.  The ephemeral private key never leaves this process; the
 * public trust snapshot is written beside the journal so a later process can
 * recover and re-verify every committed record.
 *
 * The whole request is one Effect program: the request is decoded by Schema,
 * every refusal is a typed failure, the filesystem is the `PosixFileSystem`
 * service, and the executable's only runtime boundary is `runProcessMain`.
 *
 * This is the real local owner/Permit admission path for one transition.  It
 * is not an authoritative, distributed, or trusted-time Permit, not canonical
 * HSWM admission, not outcome truth, causal credit, learning, or efficacy.
 */
import { createHash } from "node:crypto"
import { isAbsolute } from "node:path"
import { pathToFileURL } from "node:url"

import { Effect, Either, Schema } from "effect"

import type { CanonicalJson } from "./canonical-atom-v2-json.js"
import {
  HSWM_LOCAL_PERMIT_COMMIT_STATUS,
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitCommitStoreLayer,
  makeLocalPermitVerifierContext,
  LocalPermitCommitStoreService,
  type LocalPermitCommitError,
  type LocalPermitCommitReceipt
} from "./canonical-atom-v2-local-permit-commit.js"
import type { CanonicalPermitHeadBinding } from "./canonical-atom-v2-permit-envelope.js"
import { PosixFileSystem, type PosixIoError } from "./effect-posix-services.js"
import { ProcessRefusal, refuse, runProcessMain } from "./effect-process-main.js"

export const HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION =
  "hswm-local-permit-commit-process/v1" as const
export const HSWM_LOCAL_PERMIT_COMMIT_PROCESS_CLAIM_BOUNDARY =
  "ONE_SHOT_LOCAL_EPHEMERAL_KEY_PERMIT_COMMIT_OF_ONE_EXACT_STATE_TRANSITION_NOT_AUTHORITATIVE_NOT_DISTRIBUTED_NOT_TRUSTED_TIME_NOT_CANONICAL_HSWM_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY" as const

const MAX_STATE_BYTES = 262_144
const MAX_TRUST_SNAPSHOT_BYTES = 65_536

// ---------------------------------------------------------------------------
// Request schemas: the whole wire contract is declared, not hand-parsed.
// ---------------------------------------------------------------------------

const Identifier = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const Digest = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const SafeInteger = Schema.Number.pipe(Schema.int(), Schema.nonNegative(), Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER))
const AbsolutePath = Schema.String.pipe(
  Schema.minLength(1),
  Schema.maxLength(4096),
  Schema.filter((value) => !value.includes("\0") && isAbsolute(value), { message: () => "path must be absolute" })
)
const Base64Url = Schema.String.pipe(Schema.minLength(1), Schema.pattern(/^[A-Za-z0-9_-]+$/))

const HeadSchema = Schema.Struct({
  lineageId: Identifier,
  sequence: SafeInteger,
  stateDigest: Digest,
  recordDigest: Digest
})

const ClaimsSchema = Schema.Struct({
  permitId: Identifier,
  executionId: Identifier,
  executionIntentDigest: Digest,
  permitDigest: Digest,
  proposalDigest: Digest,
  transitionInvariantDigest: Digest,
  priorHead: HeadSchema,
  expectedNextHead: HeadSchema,
  target: Schema.Struct({ schemaVersion: Identifier, lineageId: Identifier, atomUid: Identifier }),
  expectedRevision: Identifier,
  candidateRevision: Identifier,
  authorizationRef: Identifier,
  scope: Identifier,
  linearizationIndex: SafeInteger
})

const CommitRequestSchema = Schema.Struct({
  contractVersion: Schema.Literal(HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION),
  operation: Schema.Literal("commit"),
  rootPath: AbsolutePath,
  trustSnapshotPath: AbsolutePath,
  issuer: Schema.Struct({ keyId: Identifier, authorizer: Identifier, policyVersion: Identifier, revocationEpoch: SafeInteger }),
  lifetimeMs: Schema.Number.pipe(Schema.int(), Schema.greaterThanOrEqualTo(1), Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)),
  claims: ClaimsSchema,
  preStateBase64Url: Base64Url,
  postStateBase64Url: Base64Url
})

const RecoverRequestSchema = Schema.Struct({
  contractVersion: Schema.Literal(HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION),
  operation: Schema.Literal("recover"),
  rootPath: AbsolutePath,
  trustSnapshotPath: AbsolutePath
})

const RequestSchema = Schema.Union(CommitRequestSchema, RecoverRequestSchema)
type CommitRequest = typeof CommitRequestSchema.Type
type RecoverRequest = typeof RecoverRequestSchema.Type

export type LocalPermitCommitProcessError = ProcessRefusal | LocalPermitCommitError

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")

const decodeStateBytes = (encoded: string, label: string): Effect.Effect<Uint8Array, ProcessRefusal> => {
  const decoded = Uint8Array.from(Buffer.from(encoded, "base64url"))
  return decoded.byteLength < 1 || decoded.byteLength > MAX_STATE_BYTES || Buffer.from(decoded).toString("base64url") !== encoded
    ? Effect.fail(refuse(`${label} must be nonempty, bounded, canonical base64url`))
    : Effect.succeed(decoded)
}

const asObject = (value: CanonicalJson): Readonly<Record<string, CanonicalJson>> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Readonly<Record<string, CanonicalJson>>) : null

const decodeRequest = (request: CanonicalJson): Effect.Effect<CommitRequest | RecoverRequest, ProcessRefusal> => {
  const decoded = Schema.decodeUnknownEither(RequestSchema, { onExcessProperty: "error" })(request)
  if (Either.isRight(decoded)) return Effect.succeed(decoded.right)
  const shape = asObject(request)
  if (shape === null) return Effect.fail(refuse("request must be an object"))
  if (shape["contractVersion"] !== HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION) {
    return Effect.fail(refuse("request contract version is not supported"))
  }
  if (shape["operation"] !== "commit" && shape["operation"] !== "recover") {
    return Effect.fail(refuse("operation must be commit or recover"))
  }
  return Effect.fail(refuse(`request is not a valid ${String(shape["operation"])} request: ${String(decoded.left.message).split("\n")[0] ?? "schema mismatch"}`))
}

const headJson = (head: CanonicalPermitHeadBinding) => Object.freeze({
  lineageId: head.lineageId, sequence: head.sequence, stateDigest: head.stateDigest, recordDigest: head.recordDigest
})

const receiptJson = (receipt: LocalPermitCommitReceipt) => Object.freeze({
  recordSha256: receipt.recordSha256,
  slotPath: receipt.slotPath,
  nonceDigest: receipt.nonceDigest,
  executionIntentDigest: receipt.executionIntentDigest,
  priorHead: headJson(receipt.priorHead),
  expectedNextHead: headJson(receipt.expectedNextHead),
  verificationTime: receipt.verificationTime,
  postStateSha256: digest(receipt.postStateBytes),
  status: receipt.status
})

const trustSnapshotWriteRefusal = (cause: PosixIoError): ProcessRefusal =>
  refuse(cause.code === "EEXIST"
    ? "trust snapshot path already exists; one bridge process owns one fresh root"
    : "cannot write the public trust snapshot beside the local journal")

// ---------------------------------------------------------------------------
// Programs
// ---------------------------------------------------------------------------

/**
 * Commit needs the issuer before the store layer can exist, so the program is
 * assembled in two steps: mint the issuer, then provide the store layer bound
 * to that issuer's trust snapshot.
 */
const commitWithIssuerBoundStore = (request: CommitRequest) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const preState = yield* decodeStateBytes(request.preStateBase64Url, "preStateBase64Url")
  const postState = yield* decodeStateBytes(request.postStateBase64Url, "postStateBase64Url")
  if (digest(preState) !== request.claims.priorHead.stateDigest) {
    return yield* Effect.fail(refuse("pre-state bytes do not match claims.priorHead.stateDigest"))
  }
  if (digest(postState) !== request.claims.expectedNextHead.stateDigest) {
    return yield* Effect.fail(refuse("post-state bytes do not match claims.expectedNextHead.stateDigest"))
  }
  if (request.claims.priorHead.sequence !== 0 || request.claims.expectedNextHead.sequence !== 1) {
    return yield* Effect.fail(refuse("this one-shot bridge commits exactly the sequence-zero to sequence-one transition"))
  }
  const issuer = yield* makeEphemeralLocalPermitIssuer(request.issuer)
  const minted = yield* issuer.mintNonce()
  const issued = yield* issuer.issue({ ...request.claims, nonceDigest: minted.nonceDigest }, request.lifetimeMs)
  yield* fs.writeExclusive(request.trustSnapshotPath, issuer.trustSnapshotBytes, { mode: 0o600, sync: true, operation: "trust-snapshot" }).pipe(
    Effect.mapError(trustSnapshotWriteRefusal)
  )
  const receipt = yield* Effect.gen(function* () {
    const store = yield* LocalPermitCommitStoreService
    return yield* store.commit({
      envelopeBytes: issued.envelopeBytes,
      expectedBindings: issued.expectedBindings,
      preStateBytes: preState,
      postStateBytes: postState
    })
  }).pipe(Effect.provide(makeLocalPermitCommitStoreLayer(request.rootPath, issuer)))
  return Object.freeze({
    _tag: "LocalPermitCommitProcessResult",
    contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
    operation: "commit",
    receipt: receiptJson(receipt),
    envelopeSha256: digest(issued.envelopeBytes),
    envelopeBytesBase64Url: Buffer.from(issued.envelopeBytes).toString("base64url"),
    trustSnapshotPath: request.trustSnapshotPath,
    trustSnapshotSha256: digest(issuer.trustSnapshotBytes),
    preStateSha256: digest(preState),
    postStateSha256: digest(postState),
    commitStatus: HSWM_LOCAL_PERMIT_COMMIT_STATUS,
    claimBoundary: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_CLAIM_BOUNDARY
  })
})

const recover = (request: RecoverRequest) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const trust = yield* fs.readRegularBounded(request.trustSnapshotPath, { maximumBytes: MAX_TRUST_SNAPSHOT_BYTES, minimumBytes: 1, operation: "trust-snapshot" }).pipe(
    Effect.mapError(() => refuse("cannot read the public trust snapshot"))
  )
  const verifier = yield* makeLocalPermitVerifierContext(trust.bytes)
  const recovered = yield* Effect.gen(function* () {
    const store = yield* LocalPermitCommitStoreService
    return yield* store.recover()
  }).pipe(Effect.provide(makeLocalPermitCommitStoreLayer(request.rootPath, verifier)))
  return Object.freeze({
    _tag: "LocalPermitCommitProcessResult",
    contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
    operation: "recover",
    commits: recovered.commits.map(receiptJson),
    head: recovered.head === null ? null : headJson(recovered.head),
    trustSnapshotPath: request.trustSnapshotPath,
    trustSnapshotSha256: digest(trust.bytes),
    commitStatus: recovered.status,
    claimBoundary: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_CLAIM_BOUNDARY
  })
})

/** The whole process as one Effect program over the POSIX filesystem service. */
export const executeLocalPermitCommitProcess = (
  request: CanonicalJson
): Effect.Effect<CanonicalJson, LocalPermitCommitProcessError, PosixFileSystem> =>
  Effect.gen(function* () {
    const decoded = yield* decodeRequest(request)
    const reply = decoded.operation === "commit" ? yield* commitWithIssuerBoundStore(decoded) : yield* recover(decoded)
    return reply as unknown as CanonicalJson
  })

export const describeLocalPermitCommitProcessFailure = (error: LocalPermitCommitProcessError): string =>
  error._tag === "ProcessRefusal" ? error.detail : `${error.code}: ${error.detail}`

export const runLocalPermitCommitProcess = (): Promise<number> =>
  runProcessMain({
    refusalPrefix: "HSWM_LOCAL_PERMIT_COMMIT_REFUSED",
    program: executeLocalPermitCommitProcess,
    describeFailure: describeLocalPermitCommitProcessFailure
  })

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  void runLocalPermitCommitProcess().then((exitCode) => { process.exitCode = exitCode })
}
