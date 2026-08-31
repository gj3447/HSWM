import {
  createHash,
  generateKeyPairSync,
  randomBytes,
  randomUUID,
  sign as signMessage,
  type KeyObject
} from "node:crypto"
import { constants } from "node:fs"
import { link, mkdir, open, readdir, unlink } from "node:fs/promises"
import { dirname, join } from "node:path"

import { Data, Effect, Either, Schema } from "effect"

import {
  assembleCanonicalPermitEnvelope,
  canonicalPermitTrustSnapshotBytes,
  decodeCanonicalPermitEnvelopeBytes,
  decodeCanonicalPermitTrustSnapshotBytes,
  verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext,
  HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_PERMIT_TRUST_STATUS,
  type CanonicalPermitClaims,
  type CanonicalPermitEnvelope,
  type CanonicalPermitExpectedBindings,
  type CanonicalPermitHeadBinding,
  type CanonicalPermitTrustSnapshot
} from "./canonical-atom-v2-permit-envelope.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"

/**
 * A deliberately narrow local occurrence adapter.  A successful receipt says
 * that this process verified a real Ed25519 signature against its own
 * caller-retained public trust snapshot and made one POSIX-visible, fsync'd
 * journal-slot publication. It is not an authoritative production Permit, a
 * distributed transaction, an admission decision, process-crash recovery of a
 * private issuer, or a Lean refinement proof.
 */
export const HSWM_LOCAL_PERMIT_COMMIT_V1 = "hswm-local-permit-commit/v1" as const
export const HSWM_LOCAL_PERMIT_COMMIT_STATUS =
  "LOCAL_POSIX_ATOMIC_NO_REPLACE_PROCESS_CRASH_TESTED_CALLER_RELATIVE_PUBLIC_TRUST_AND_TIME_VERIFIED_SINGLE_USE_SLOT_COMMITTED_NOT_AUTHORITATIVE_NOT_DISTRIBUTED_NOT_TRUSTED_TIME_NOT_PRIVATE_ISSUER_RECOVERY_NOT_POWER_LOSS_NOT_LEAN_REFINEMENT" as const

const Identifier = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const Digest = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Instant = Schema.String.pipe(Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/))
const SafeInteger = Schema.Number.pipe(Schema.int(), Schema.nonNegative(), Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER))
const Base64Url = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9_-]+$/), Schema.maxLength(1_500_000))
const MAX_LOCAL_STATE_BYTES = 1_048_576
const MAX_LOCAL_RECORD_BYTES = 4_600_000
const FINAL_SLOT = /^\d{16}\.json$/
const PRIVATE_STAGING_SLOT = /^\.local-permit-commit-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.tmp$/

interface LocalPermitCommitRecord {
  readonly _tag: "LocalPermitCommitRecord"
  readonly contractVersion: typeof HSWM_LOCAL_PERMIT_COMMIT_V1
  readonly status: typeof HSWM_LOCAL_PERMIT_COMMIT_STATUS
  readonly committedAt: string
  readonly verificationTime: string
  readonly envelopeBytesBase64Url: string
  readonly envelopeSha256: string
  readonly preStateBytesBase64Url: string
  readonly postStateBytesBase64Url: string
  readonly executionIntentDigest: string
  readonly nonceDigest: string
  readonly priorHead: CanonicalPermitHeadBinding
  readonly expectedNextHead: CanonicalPermitHeadBinding
}

const HeadSchema: Schema.Schema<CanonicalPermitHeadBinding> = Schema.Struct({
  lineageId: Identifier,
  sequence: SafeInteger,
  stateDigest: Digest,
  recordDigest: Digest
})

const LocalPermitCommitRecordSchema: Schema.Schema<LocalPermitCommitRecord> = Schema.Struct({
  _tag: Schema.Literal("LocalPermitCommitRecord"),
  contractVersion: Schema.Literal(HSWM_LOCAL_PERMIT_COMMIT_V1),
  status: Schema.Literal(HSWM_LOCAL_PERMIT_COMMIT_STATUS),
  committedAt: Instant,
  verificationTime: Instant,
  envelopeBytesBase64Url: Base64Url,
  envelopeSha256: Digest,
  preStateBytesBase64Url: Base64Url,
  postStateBytesBase64Url: Base64Url,
  executionIntentDigest: Digest,
  nonceDigest: Digest,
  priorHead: HeadSchema,
  expectedNextHead: HeadSchema
})

export type LocalPermitCommitErrorCode =
  | "INPUT_INVALID"
  | "ISSUANCE_INVALID"
  | "NONCE_NOT_MINTED_OR_ALREADY_ISSUED"
  | "PERMIT_VERIFICATION_FAILED"
  | "NONCE_ALREADY_CONSUMED"
  | "PREDECESSOR_MISMATCH"
  | "SLOT_ALREADY_COMMITTED"
  | "ATOMIC_PUBLICATION_UNSUPPORTED"
  | "COMMIT_OUTCOME_UNKNOWN"
  | "IO_FAILED"
  | "RECOVERY_INVALID"

export class LocalPermitCommitError extends Data.TaggedError("LocalPermitCommitError")<{
  readonly code: LocalPermitCommitErrorCode
  readonly detail: string
}> {}

const failure = (code: LocalPermitCommitErrorCode, detail: string): LocalPermitCommitError =>
  new LocalPermitCommitError({ code, detail })

const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const nowIso = (clock: () => Date): string => clock().toISOString()
const identicalHead = (left: CanonicalPermitHeadBinding, right: CanonicalPermitHeadBinding): boolean =>
  left.lineageId === right.lineageId && left.sequence === right.sequence &&
  left.stateDigest === right.stateDigest && left.recordDigest === right.recordDigest
const identicalBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((value, index) => value === right[index])

const expectedFromClaims = (claims: CanonicalPermitClaims): CanonicalPermitExpectedBindings => Object.freeze({
  permitId: claims.permitId,
  executionId: claims.executionId,
  executionIntentDigest: claims.executionIntentDigest,
  permitDigest: claims.permitDigest,
  proposalDigest: claims.proposalDigest,
  transitionInvariantDigest: claims.transitionInvariantDigest,
  priorHead: Object.freeze({ ...claims.priorHead }),
  expectedNextHead: Object.freeze({ ...claims.expectedNextHead }),
  target: Object.freeze({ ...claims.target }),
  expectedRevision: claims.expectedRevision,
  candidateRevision: claims.candidateRevision,
  authorizationRef: claims.authorizationRef,
  authorizer: claims.authorizer,
  scope: claims.scope,
  nonceDigest: claims.nonceDigest,
  keyPolicyVersion: claims.keyPolicyVersion,
  revocationEpoch: claims.revocationEpoch,
  linearizationIndex: claims.linearizationIndex
})

const safeSlotName = (sequence: number): string => `${String(sequence).padStart(16, "0")}.json`
const lineageDirectory = (lineageId: string): string => createHash("sha256").update(lineageId, "utf8").digest("hex")
const validHeadTransition = (prior: CanonicalPermitHeadBinding, next: CanonicalPermitHeadBinding): boolean =>
  prior.lineageId === next.lineageId && prior.sequence < Number.MAX_SAFE_INTEGER &&
  next.sequence === prior.sequence + 1

const syncDirectory = async (path: string): Promise<void> => {
  const handle = await open(path, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW)
  try { await handle.sync() } finally { await handle.close() }
}

const readStableCommitFile = async (
  path: string,
  errorCode: "RECOVERY_INVALID" | "COMMIT_OUTCOME_UNKNOWN"
): Promise<Uint8Array> => {
  let handle
  try {
    handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  } catch {
    throw failure(errorCode, "local commit slot cannot be opened as a regular file")
  }
  try {
    const before = await handle.stat()
    if (!before.isFile() || (before.mode & 0o777) !== 0o400 || before.size < 1 || before.size > MAX_LOCAL_RECORD_BYTES) {
      throw failure(errorCode, "local commit slot must be an immutable bounded 0400 regular file")
    }
    const buffer = Buffer.alloc(before.size + 1)
    let total = 0
    while (total < buffer.byteLength) {
      const result = await handle.read(buffer, total, buffer.byteLength - total, total)
      if (result.bytesRead === 0) break
      total += result.bytesRead
    }
    const after = await handle.stat()
    if (total !== before.size || after.dev !== before.dev || after.ino !== before.ino ||
        after.size !== before.size || (after.mode & 0o777) !== 0o400) {
      throw failure(errorCode, "local commit slot changed during its bounded read")
    }
    return Uint8Array.from(buffer.subarray(0, total))
  } finally {
    await handle.close()
  }
}

/** fsync the immediate namespace parents involved in a first local publication. */
const initializeCommitDirectories = async (rootPath: string, root: string, commitsRoot: string): Promise<void> => {
  await mkdir(commitsRoot, { recursive: true, mode: 0o700 })
  await syncDirectory(dirname(rootPath))
  await syncDirectory(rootPath)
  await syncDirectory(root)
  await syncDirectory(commitsRoot)
}

export interface LocalPermitIssuerConfig {
  readonly keyId: string
  readonly authorizer: string
  readonly policyVersion: string
  readonly revocationEpoch: number
  readonly clock?: () => Date
}

export interface LocalPermitIssuer {
  readonly trustSnapshot: CanonicalPermitTrustSnapshot
  readonly trustSnapshotBytes: Uint8Array
  /** Mints only an opaque digest; raw nonce bytes never leave this local issuer. */
  readonly mintNonce: () => Either.Either<{ readonly nonceDigest: string }, LocalPermitCommitError>
  readonly issue: (
    claims: Omit<CanonicalPermitClaims, "authorizer" | "keyPolicyVersion" | "revocationEpoch" | "issuedAt" | "notBefore" | "expiresAt">,
    lifetimeMilliseconds: number
  ) => Either.Either<{ readonly envelope: CanonicalPermitEnvelope; readonly envelopeBytes: Uint8Array; readonly expectedBindings: CanonicalPermitExpectedBindings }, LocalPermitCommitError>
}

/** Generates an ephemeral real Ed25519 key; callers must not treat it as a production authority. */
export const makeEphemeralLocalPermitIssuer = (
  config: LocalPermitIssuerConfig
): Either.Either<LocalPermitIssuer, LocalPermitCommitError> => {
  if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(config.keyId) ||
      !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(config.authorizer) ||
      !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(config.policyVersion) ||
      !Number.isSafeInteger(config.revocationEpoch) || config.revocationEpoch < 0) {
    return Either.left(failure("INPUT_INVALID", "local issuer configuration is invalid"))
  }
  const clock = config.clock ?? (() => new Date())
  let privateKey: KeyObject
  let publicSpki: Uint8Array
  try {
    const generated = generateKeyPairSync("ed25519")
    privateKey = generated.privateKey
    publicSpki = Uint8Array.from(generated.publicKey.export({ format: "der", type: "spki" }))
  } catch {
    return Either.left(failure("ISSUANCE_INVALID", "Node could not generate an Ed25519 keypair"))
  }
  let issuedAt: string
  try {
    issuedAt = nowIso(clock)
  } catch {
    return Either.left(failure("ISSUANCE_INVALID", "local issuer clock is invalid"))
  }
  const trustSnapshot: CanonicalPermitTrustSnapshot = Object.freeze({
    _tag: "CanonicalPermitTrustSnapshot",
    contractVersion: HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
    policyVersion: config.policyVersion,
    revocationEpoch: config.revocationEpoch,
    snapshotAt: issuedAt,
    keys: Object.freeze([Object.freeze({
      keyId: config.keyId,
      algorithm: "Ed25519" as const,
      publicKeySpkiDerBase64Url: Buffer.from(publicSpki).toString("base64url"),
      authorizedAuthorizer: config.authorizer,
      notBefore: issuedAt,
      expiresAt: "2099-12-31T23:59:59.999Z",
      status: "ACTIVE" as const,
      revokedAt: null
    })]),
    status: HSWM_CANONICAL_PERMIT_TRUST_STATUS
  })
  const trustBytes = canonicalPermitTrustSnapshotBytes(trustSnapshot)
  if (Either.isLeft(trustBytes)) return Either.left(failure("ISSUANCE_INVALID", trustBytes.left.detail))
  const unissuedNonceDigests = new Set<string>()

  return Either.right(Object.freeze({
    trustSnapshot,
    trustSnapshotBytes: Uint8Array.from(trustBytes.right),
    mintNonce: () => {
      try {
        for (let attempt = 0; attempt < 128; attempt += 1) {
          const nonceDigest = digest(randomBytes(32))
          if (unissuedNonceDigests.has(nonceDigest)) continue
          unissuedNonceDigests.add(nonceDigest)
          return Either.right(Object.freeze({ nonceDigest }))
        }
        return Either.left(failure("ISSUANCE_INVALID", "local nonce mint exhausted its collision-retry bound"))
      } catch {
        return Either.left(failure("ISSUANCE_INVALID", "Node could not mint local nonce entropy"))
      }
    },
    issue: (
      input: Omit<CanonicalPermitClaims, "authorizer" | "keyPolicyVersion" | "revocationEpoch" | "issuedAt" | "notBefore" | "expiresAt">,
      lifetimeMilliseconds: number
    ) => {
      if (!Number.isSafeInteger(lifetimeMilliseconds) || lifetimeMilliseconds < 1) {
        return Either.left(failure("INPUT_INVALID", "Permit lifetime must be a positive safe integer"))
      }
      if (!unissuedNonceDigests.delete(input.nonceDigest)) {
        return Either.left(failure(
          "NONCE_NOT_MINTED_OR_ALREADY_ISSUED",
          "local issuer requires one previously minted, not-yet-issued nonce digest"
        ))
      }
      let start: string
      let expires: string
      try {
        start = nowIso(clock)
        expires = new Date(Date.parse(start) + lifetimeMilliseconds).toISOString()
      } catch {
        return Either.left(failure("ISSUANCE_INVALID", "local issuer clock or Permit expiry is invalid"))
      }
      const claims: CanonicalPermitClaims = Object.freeze({
        ...input,
        priorHead: Object.freeze({ ...input.priorHead }),
        expectedNextHead: Object.freeze({ ...input.expectedNextHead }),
        target: Object.freeze({ ...input.target }),
        authorizer: config.authorizer,
        keyPolicyVersion: config.policyVersion,
        revocationEpoch: config.revocationEpoch,
        issuedAt: start,
        notBefore: start,
        expiresAt: expires
      })
      const assembled = assembleCanonicalPermitEnvelope(claims, config.keyId, (bytes) =>
        Uint8Array.from(signMessage(null, bytes, privateKey))
      )
      if (Either.isLeft(assembled)) return Either.left(failure("ISSUANCE_INVALID", assembled.left.detail))
      return Either.right(Object.freeze({
        envelope: assembled.right.envelope,
        envelopeBytes: Uint8Array.from(assembled.right.envelopeBytes),
        expectedBindings: expectedFromClaims(claims)
      }))
    }
  }))
}

export interface LocalPermitCommitRequest {
  readonly envelopeBytes: Uint8Array
  readonly expectedBindings: CanonicalPermitExpectedBindings
  /** Bounded local state bytes whose digest must equal Permit priorHead.stateDigest. */
  readonly preStateBytes: Uint8Array
  /** Bounded local state bytes whose digest must equal Permit expectedNextHead.stateDigest. */
  readonly postStateBytes: Uint8Array
}

export interface LocalPermitCommitReceipt {
  readonly recordSha256: string
  readonly slotPath: string
  readonly nonceDigest: string
  readonly executionIntentDigest: string
  readonly priorHead: CanonicalPermitHeadBinding
  readonly expectedNextHead: CanonicalPermitHeadBinding
  readonly verificationTime: string
  readonly postStateBytes: Uint8Array
  readonly status: typeof HSWM_LOCAL_PERMIT_COMMIT_STATUS
}

export interface LocalPermitRecovery {
  readonly commits: ReadonlyArray<LocalPermitCommitReceipt>
  readonly head: CanonicalPermitHeadBinding | null
  readonly status: typeof HSWM_LOCAL_PERMIT_COMMIT_STATUS
}

export interface LocalPermitCommitStore {
  readonly commit: (request: LocalPermitCommitRequest) => Effect.Effect<LocalPermitCommitReceipt, LocalPermitCommitError>
  readonly recover: () => Effect.Effect<LocalPermitRecovery, LocalPermitCommitError>
}

export type LocalPermitCommitPublicationCheckpointForTest =
  | "prepared-file-fsync:after"
  | "slot-link:after"

type LocalPermitCommitCheckpoint = (
  checkpoint: LocalPermitCommitPublicationCheckpointForTest
) => void

/**
 * Restart-loadable public verification material only. Persisting this canonical
 * snapshot lets another process verify/recover journal records, but does not
 * persist or restore private signing authority.
 */
export interface LocalPermitVerifierContext {
  readonly trustSnapshotBytes: Uint8Array
}

export const makeLocalPermitVerifierContext = (
  trustSnapshotBytes: Uint8Array
): Either.Either<LocalPermitVerifierContext, LocalPermitCommitError> => {
  const decoded = decodeCanonicalPermitTrustSnapshotBytes(trustSnapshotBytes)
  return Either.isLeft(decoded)
    ? Either.left(failure("INPUT_INVALID", "local verifier context requires canonical public trust snapshot bytes"))
    : Either.right(Object.freeze({ trustSnapshotBytes: Uint8Array.from(trustSnapshotBytes) }))
}

const decodeRecord = (bytes: Uint8Array): Either.Either<LocalPermitCommitRecord, LocalPermitCommitError> => {
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed)) return Either.left(failure("RECOVERY_INVALID", "commit record is not canonical JSON"))
  const decoded = Schema.decodeUnknownEither(LocalPermitCommitRecordSchema, { onExcessProperty: "error" })(parsed.right)
  if (Either.isLeft(decoded)) return Either.left(failure("RECOVERY_INVALID", "commit record violates the exact v1 schema"))
  const canonical = canonicalJsonBytes(decoded.right)
  if (Either.isLeft(canonical) || canonical.right.byteLength !== bytes.byteLength || !canonical.right.every((value, index) => value === bytes[index])) {
    return Either.left(failure("RECOVERY_INVALID", "commit record bytes are not exact canonical JSON"))
  }
  return Either.right(Object.freeze({ ...decoded.right, priorHead: Object.freeze({ ...decoded.right.priorHead }), expectedNextHead: Object.freeze({ ...decoded.right.expectedNextHead }) }))
}

const strictStateBytes = (encoded: string): Either.Either<Uint8Array, LocalPermitCommitError> => {
  try {
    const decoded = Uint8Array.from(Buffer.from(encoded, "base64url"))
    return decoded.byteLength > 0 && decoded.byteLength <= MAX_LOCAL_STATE_BYTES &&
      Buffer.from(decoded).toString("base64url") === encoded
      ? Either.right(decoded)
      : Either.left(failure("RECOVERY_INVALID", "local state bytes are empty, oversized, or noncanonical base64url"))
  } catch {
    return Either.left(failure("RECOVERY_INVALID", "local state bytes cannot be decoded"))
  }
}

const boundedStateBytes = (bytes: Uint8Array): Either.Either<Uint8Array, LocalPermitCommitError> =>
  bytes instanceof Uint8Array && bytes.byteLength > 0 && bytes.byteLength <= MAX_LOCAL_STATE_BYTES
    ? Either.right(Uint8Array.from(bytes))
    : Either.left(failure("INPUT_INVALID", "local state bytes must be nonempty and bounded"))

const makeLocalPermitCommitStoreInternal = (
  rootPath: string,
  verifier: LocalPermitVerifierContext,
  clock: () => Date,
  checkpoint: LocalPermitCommitCheckpoint
): LocalPermitCommitStore => {
  const root = join(rootPath, "local-permit-commits-v1")
  const commitsRoot = join(root, "commits")
  const recover = (): Effect.Effect<LocalPermitRecovery, LocalPermitCommitError> => Effect.tryPromise({
    try: async () => {
      try { await initializeCommitDirectories(rootPath, root, commitsRoot) } catch { throw failure("IO_FAILED", "cannot initialize and fsync local commit root") }
      const directories = await readdir(commitsRoot, { withFileTypes: true })
      if (directories.some((entry) => !entry.isDirectory() || !/^[0-9a-f]{64}$/.test(entry.name))) {
        throw failure("RECOVERY_INVALID", "local commit root contains an unexpected or non-directory entry")
      }
      const lineageDirectories = directories.filter((entry) => entry.isDirectory())
      if (lineageDirectories.length > 1) {
        throw failure("RECOVERY_INVALID", "one local commit store may recover exactly one connected lineage")
      }
      const receipts: LocalPermitCommitReceipt[] = []
      for (const directory of lineageDirectories) {
        const base = join(commitsRoot, directory.name)
        const entries = await readdir(base, { withFileTypes: true })
        if (entries.some((entry) => !entry.isFile() || (!FINAL_SLOT.test(entry.name) && !PRIVATE_STAGING_SLOT.test(entry.name)))) {
          throw failure("RECOVERY_INVALID", "local lineage directory contains an unexpected entry")
        }
        // A recognized private staging file has no committed meaning.  It can
        // remain after process death before or after the no-replace hard link.
        const slots = entries
          .filter((entry) => FINAL_SLOT.test(entry.name))
          .sort((a, b) => a.name.localeCompare(b.name))
        let previous: LocalPermitCommitRecord | null = null
        let previousPostState: Uint8Array | null = null
        const nonces = new Set<string>()
        for (const slot of slots) {
          const bytes = await readStableCommitFile(join(base, slot.name), "RECOVERY_INVALID")
          const record = decodeRecord(bytes)
          if (Either.isLeft(record)) throw record.left
          const envelope = decodeCanonicalPermitEnvelopeBytes(Buffer.from(record.right.envelopeBytesBase64Url, "base64url"))
          if (Either.isLeft(envelope) || digest(Buffer.from(record.right.envelopeBytesBase64Url, "base64url")) !== record.right.envelopeSha256) {
            throw failure("RECOVERY_INVALID", "commit record envelope bytes are invalid or digest-mismatched")
          }
          const verification = verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
            Buffer.from(record.right.envelopeBytesBase64Url, "base64url"), expectedFromClaims(envelope.right.claims), verifier.trustSnapshotBytes, record.right.verificationTime
          )
          if (Either.isLeft(verification)) throw failure("RECOVERY_INVALID", "commit record signature or local trust binding does not verify")
          const claims = envelope.right.claims
          const preState = strictStateBytes(record.right.preStateBytesBase64Url)
          const postState = strictStateBytes(record.right.postStateBytesBase64Url)
          if (Either.isLeft(preState) || Either.isLeft(postState)) {
            throw failure("RECOVERY_INVALID", "commit record has invalid local state bytes")
          }
          if (record.right.committedAt !== record.right.verificationTime ||
              claims.executionIntentDigest !== record.right.executionIntentDigest || claims.nonceDigest !== record.right.nonceDigest ||
              !identicalHead(claims.priorHead, record.right.priorHead) || !identicalHead(claims.expectedNextHead, record.right.expectedNextHead) ||
              digest(preState.right) !== claims.priorHead.stateDigest || digest(postState.right) !== claims.expectedNextHead.stateDigest ||
              !validHeadTransition(claims.priorHead, claims.expectedNextHead) ||
              directory.name !== lineageDirectory(claims.expectedNextHead.lineageId) ||
              Number(slot.name.slice(0, 16)) !== claims.expectedNextHead.sequence ||
              (previous === null
                ? claims.priorHead.sequence !== 0
                : (!identicalHead(previous.expectedNextHead, claims.priorHead) || previousPostState === null || !identicalBytes(previousPostState, preState.right))) ||
              nonces.has(claims.nonceDigest)) {
            throw failure("RECOVERY_INVALID", "commit record does not form a one-shot contiguous local journal")
          }
          nonces.add(claims.nonceDigest)
          previous = record.right
          previousPostState = postState.right
          receipts.push(Object.freeze({ recordSha256: digest(bytes), slotPath: join(base, slot.name), nonceDigest: claims.nonceDigest, executionIntentDigest: claims.executionIntentDigest, priorHead: Object.freeze({ ...claims.priorHead }), expectedNextHead: Object.freeze({ ...claims.expectedNextHead }), verificationTime: record.right.verificationTime, postStateBytes: Uint8Array.from(postState.right), status: HSWM_LOCAL_PERMIT_COMMIT_STATUS }))
        }
      }
      const heads = receipts.map((receipt) => receipt.expectedNextHead)
      return Object.freeze({ commits: Object.freeze(receipts), head: heads.length === 0 ? null : Object.freeze({ ...heads[heads.length - 1]! }), status: HSWM_LOCAL_PERMIT_COMMIT_STATUS })
    },
    catch: (cause) => cause instanceof LocalPermitCommitError ? cause : failure("IO_FAILED", "local commit recovery I/O failed")
  })

  return Object.freeze({
    recover,
    commit: (request: LocalPermitCommitRequest) => Effect.gen(function* () {
      let verifiedAt: string
      try {
        verifiedAt = nowIso(clock)
      } catch {
        return yield* Effect.fail(failure("PERMIT_VERIFICATION_FAILED", "local verifier clock is invalid"))
      }
      const verification = verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
        request.envelopeBytes, request.expectedBindings, verifier.trustSnapshotBytes, verifiedAt
      )
      if (Either.isLeft(verification)) return yield* Effect.fail(failure("PERMIT_VERIFICATION_FAILED", verification.left.detail))
      const claims = verification.right.envelope.claims
      const preState = boundedStateBytes(request.preStateBytes)
      const postState = boundedStateBytes(request.postStateBytes)
      if (Either.isLeft(preState)) return yield* Effect.fail(preState.left)
      if (Either.isLeft(postState)) return yield* Effect.fail(postState.left)
      if (digest(preState.right) !== claims.priorHead.stateDigest || digest(postState.right) !== claims.expectedNextHead.stateDigest) {
        return yield* Effect.fail(failure("PREDECESSOR_MISMATCH", "local pre/post state bytes do not match exact Permit head state digests"))
      }
      if (!validHeadTransition(claims.priorHead, claims.expectedNextHead)) {
        return yield* Effect.fail(failure("PREDECESSOR_MISMATCH", "Permit heads must name one lineage and one immediate successor"))
      }
      const recovered = yield* recover()
      if (recovered.commits.some((entry) => entry.nonceDigest === claims.nonceDigest)) {
        return yield* Effect.fail(failure("NONCE_ALREADY_CONSUMED", "Permit nonce already occurs in the recovered local journal"))
      }
      const lineageHead = [...recovered.commits].reverse().find(
        (entry) => entry.expectedNextHead.lineageId === claims.priorHead.lineageId
      )
      if (recovered.commits.length === 0 && claims.priorHead.sequence !== 0) {
        return yield* Effect.fail(failure("PREDECESSOR_MISMATCH", "the first local Permit must extend the signed sequence-zero genesis head"))
      }
      if (recovered.commits.length > 0 && (lineageHead === undefined || !identicalHead(lineageHead.expectedNextHead, claims.priorHead))) {
        return yield* Effect.fail(failure("PREDECESSOR_MISMATCH", "Permit prior head is not the recovered local journal head"))
      }
      const directory = join(commitsRoot, lineageDirectory(claims.expectedNextHead.lineageId))
      const path = join(directory, safeSlotName(claims.expectedNextHead.sequence))
      const temporaryPath = join(directory, `.local-permit-commit-${randomUUID()}.tmp`)
      const record: LocalPermitCommitRecord = Object.freeze({
        _tag: "LocalPermitCommitRecord", contractVersion: HSWM_LOCAL_PERMIT_COMMIT_V1, status: HSWM_LOCAL_PERMIT_COMMIT_STATUS,
        committedAt: verifiedAt, verificationTime: verifiedAt,
        envelopeBytesBase64Url: Buffer.from(request.envelopeBytes).toString("base64url"), envelopeSha256: digest(request.envelopeBytes),
        preStateBytesBase64Url: Buffer.from(preState.right).toString("base64url"), postStateBytesBase64Url: Buffer.from(postState.right).toString("base64url"),
        executionIntentDigest: claims.executionIntentDigest, nonceDigest: claims.nonceDigest,
        priorHead: Object.freeze({ ...claims.priorHead }), expectedNextHead: Object.freeze({ ...claims.expectedNextHead })
      })
      const encoded = canonicalJsonBytes(record)
      if (Either.isLeft(encoded)) return yield* Effect.fail(failure("INPUT_INVALID", "local commit record cannot be canonically encoded"))
      yield* Effect.tryPromise({
        try: async () => {
          await initializeCommitDirectories(rootPath, root, commitsRoot)
          await mkdir(directory, { recursive: true, mode: 0o700 })
          await syncDirectory(commitsRoot)
          await syncDirectory(directory)
          let staged = false
          try {
            const handle = await open(
              temporaryPath,
              constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
              0o600
            )
            staged = true
            try {
              await handle.writeFile(encoded.right)
              await handle.chmod(0o400)
              await handle.sync()
            } finally {
              await handle.close()
            }
            checkpoint("prepared-file-fsync:after")
            try {
              await link(temporaryPath, path)
            } catch (cause) {
              const code = typeof cause === "object" && cause !== null && "code" in cause ? String(cause.code) : ""
              if (code === "EEXIST") throw failure("SLOT_ALREADY_COMMITTED", "local journal slot was already committed by another writer")
              if (["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(code)) {
                throw failure("ATOMIC_PUBLICATION_UNSUPPORTED", `local filesystem cannot provide no-replace hard-link publication: ${code}`)
              }
              throw failure("COMMIT_OUTCOME_UNKNOWN", "local journal hard-link outcome is unknown; recover before retrying")
            }
            checkpoint("slot-link:after")
            await syncDirectory(directory)
            const exact = await readStableCommitFile(path, "COMMIT_OUTCOME_UNKNOWN")
            if (!identicalBytes(exact, encoded.right)) {
              throw failure("COMMIT_OUTCOME_UNKNOWN", "published local journal slot differs on exact readback")
            }
          } finally {
            if (staged) {
              try { await unlink(temporaryPath) } catch { /* an orphan private staging file is not committed */ }
            }
          }
        },
        catch: (cause) => {
          if (cause instanceof LocalPermitCommitError) return cause
          const code = typeof cause === "object" && cause !== null && "code" in cause && cause.code === "EEXIST"
            ? "SLOT_ALREADY_COMMITTED" : "COMMIT_OUTCOME_UNKNOWN"
          return failure(code, code === "SLOT_ALREADY_COMMITTED" ? "local journal slot was already committed by another writer" : "write outcome is unknown; recover before retrying")
        }
      })
      return Object.freeze({ recordSha256: digest(encoded.right), slotPath: path, nonceDigest: claims.nonceDigest, executionIntentDigest: claims.executionIntentDigest, priorHead: Object.freeze({ ...claims.priorHead }), expectedNextHead: Object.freeze({ ...claims.expectedNextHead }), verificationTime: verifiedAt, postStateBytes: Uint8Array.from(postState.right), status: HSWM_LOCAL_PERMIT_COMMIT_STATUS })
    })
  })
}

export const makeLocalPermitCommitStore = (
  rootPath: string,
  verifier: LocalPermitVerifierContext,
  clock: () => Date = () => new Date()
): LocalPermitCommitStore => makeLocalPermitCommitStoreInternal(rootPath, verifier, clock, () => undefined)

/** Package-root-private seam used only by independent-process crash tests. */
export const makeLocalPermitCommitStoreWithCheckpointForTest = (
  rootPath: string,
  verifier: LocalPermitVerifierContext,
  clock: () => Date,
  selected: LocalPermitCommitPublicationCheckpointForTest,
  onCheckpoint: () => void
): LocalPermitCommitStore => makeLocalPermitCommitStoreInternal(
  rootPath,
  verifier,
  clock,
  (checkpoint) => { if (checkpoint === selected) onCheckpoint() }
)
