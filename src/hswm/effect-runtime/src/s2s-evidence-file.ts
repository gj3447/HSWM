import { randomUUID } from "node:crypto"
import { constants } from "node:fs"
import {
  link,
  lstat,
  mkdir,
  open,
  realpath,
  unlink
} from "node:fs/promises"
import { isAbsolute, join, resolve } from "node:path"

import { Context, Data, Effect, Either, Layer, Schema } from "effect"

import { rawS2SFileSha256 } from "./s2s-canonical.js"
import {
  S2SGitCommitShaSchema,
  S2SSha256Schema,
  type S2SGitCommitSha
} from "./s2s-confirmatory.js"
import {
  S2S_EVIDENCE_CLAIM_MAX_BYTES,
  S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES,
  S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS,
  S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES,
  S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES,
  S2SEvidenceEnvelopeError,
  buildS2SEvidenceClaim,
  s2sEvidenceClaimFileName,
  validateS2SEvidenceClaim,
  validateS2SEvidenceClaimForEnvelope,
  validateS2SEvidenceEnvelope,
  validateS2SEvidenceEnvelopeSnapshot,
  type S2SEvidenceClaimSnapshot,
  type S2SEvidenceEnvelopeSnapshot,
  type S2SEvidenceStage
} from "./s2s-evidence-envelope.js"

const OBJECTS_DIRECTORY_NAME = "objects"
const CLAIMS_DIRECTORY_NAME = "claims"
const CONTENT_OBJECT_PATTERN = /^[0-9a-f]{64}$/

const StageIdentitySchema = Schema.Struct({
  sourceCommitA: S2SGitCommitShaSchema,
  registrationCommitB: S2SGitCommitShaSchema,
  workflowRunId: Schema.Number.pipe(
    Schema.int(),
    Schema.between(1, Number.MAX_SAFE_INTEGER)
  ),
  stage: Schema.Literal("REGISTER", "CONFIRM", "ADJUDICATE")
})

const ManifestAttachmentIndexSchema = Schema.Struct({
  attachments: Schema.Array(
    Schema.Struct({
      raw_sha256: S2SSha256Schema,
      byte_length: Schema.Number.pipe(
        Schema.int(),
        Schema.between(1, S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES)
      )
    })
  ).pipe(
    Schema.minItems(1),
    Schema.maxItems(S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS)
  )
})

export interface S2SEvidenceStageIdentity {
  readonly sourceCommitA: S2SGitCommitSha
  readonly registrationCommitB: S2SGitCommitSha
  readonly workflowRunId: number
  readonly stage: S2SEvidenceStage
}

export interface S2SDurableEvidenceStage {
  readonly envelope: S2SEvidenceEnvelopeSnapshot
  readonly claim: S2SEvidenceClaimSnapshot
}

export interface S2SDurableEvidenceRecovery {
  readonly chain: ReadonlyArray<S2SDurableEvidenceStage>
  readonly latest: S2SDurableEvidenceStage
}

const AUTHENTIC_DURABLE_EVIDENCE_RECOVERIES = new WeakSet<object>()

/** Root-private process-local provenance check for file-store-issued recovery. */
export const isAuthenticS2SDurableEvidenceRecovery = (
  input: unknown
): input is S2SDurableEvidenceRecovery =>
  input !== null &&
  typeof input === "object" &&
  AUTHENTIC_DURABLE_EVIDENCE_RECOVERIES.has(input)

export interface S2SDurableEvidencePublication {
  readonly _tag: "Committed" | "AlreadyCommitted"
  readonly recovery: S2SDurableEvidenceRecovery
}

export class S2SDurableEvidenceFileStoreError extends Data.TaggedError(
  "S2SDurableEvidenceFileStoreError"
)<{
  readonly operation: "INITIALIZE" | "RECOVER" | "COMMIT"
  readonly reason:
    | "ATOMIC_PUBLICATION_UNSUPPORTED"
    | "CLAIM_CONFLICT"
    | "CLAIM_NOT_FOUND"
    | "COMMITTED_READBACK_FAILED"
    | "CONTENT_ADDRESS_CORRUPTION"
    | "FILE_TOO_LARGE"
    | "FILE_TYPE_INVALID"
    | "IDENTITY_INVALID"
    | "IDENTITY_MISMATCH"
    | "IO_FAILED"
    | "PREDECESSOR_MISMATCH"
    | "PREDECESSOR_MISSING"
    | "PUBLICATION_OUTCOME_UNKNOWN"
    | "ROOT_UNSAFE"
  readonly detail: string
}> {}

export type S2SDurableEvidenceFileStoreFailure =
  | S2SEvidenceEnvelopeError
  | S2SDurableEvidenceFileStoreError

export class S2SDurableEvidenceFileStore extends Context.Tag(
  "hswm/S2S/DurableEvidenceFileStore"
)<
  S2SDurableEvidenceFileStore,
  {
    readonly recover: (
      identity: S2SEvidenceStageIdentity
    ) => Effect.Effect<
      S2SDurableEvidenceRecovery,
      S2SDurableEvidenceFileStoreFailure
    >
    readonly commit: (
      envelope: S2SEvidenceEnvelopeSnapshot
    ) => Effect.Effect<
      S2SDurableEvidencePublication,
      S2SDurableEvidenceFileStoreFailure
    >
  }
>() {}

interface DirectoryIdentity {
  readonly path: string
  readonly device: number
  readonly inode: number
  readonly label: "root" | "objects" | "claims"
}

interface StoreIdentity {
  readonly root: DirectoryIdentity
  readonly objects: DirectoryIdentity
  readonly claims: DirectoryIdentity
}

interface PreparedCommit {
  readonly envelope: S2SEvidenceEnvelopeSnapshot
  readonly claim: S2SEvidenceClaimSnapshot
}

type FileState = "MISSING" | "SAME" | "DIFFERENT"
type CreateOnlyOutcome = "Published" | "AlreadyPresent"
type CollisionReason = "CLAIM_CONFLICT" | "CONTENT_ADDRESS_CORRUPTION"

const hasErrorCode = (error: unknown): error is { readonly code: string } =>
  typeof error === "object" &&
  error !== null &&
  "code" in error &&
  typeof error.code === "string"

const errorDetail = (error: unknown): string =>
  hasErrorCode(error) ? error.code : "UNKNOWN_FILESYSTEM_ERROR"

const storeError = (
  operation: S2SDurableEvidenceFileStoreError["operation"],
  reason: S2SDurableEvidenceFileStoreError["reason"],
  detail: string
): S2SDurableEvidenceFileStoreError =>
  new S2SDurableEvidenceFileStoreError({ operation, reason, detail })

const filesystemError = (
  operation: S2SDurableEvidenceFileStoreError["operation"],
  error: unknown
): S2SDurableEvidenceFileStoreError =>
  error instanceof S2SDurableEvidenceFileStoreError
    ? error
    : storeError(operation, "IO_FAILED", errorDetail(error))

const filesystemEffect = <A>(
  operation: S2SDurableEvidenceFileStoreError["operation"],
  task: () => Promise<A>
): Effect.Effect<A, S2SDurableEvidenceFileStoreError> =>
  Effect.tryPromise({
    try: task,
    catch: (error) => filesystemError(operation, error)
  }).pipe(Effect.uninterruptible)

const initializationError = (
  error: unknown
): S2SDurableEvidenceFileStoreError =>
  error instanceof S2SDurableEvidenceFileStoreError
    ? error
    : hasErrorCode(error) &&
        ["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(error.code)
      ? storeError(
          "INITIALIZE",
          "ATOMIC_PUBLICATION_UNSUPPORTED",
          `evidence root lacks required POSIX durability: ${error.code}`
        )
    : hasErrorCode(error) &&
        ["EEXIST", "ENOENT", "ENOTDIR", "ELOOP"].includes(error.code)
      ? storeError(
          "INITIALIZE",
          "ROOT_UNSAFE",
          `evidence root is not one private directory: ${error.code}`
        )
      : filesystemError("INITIALIZE", error)

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const exactIdentity = (
  input: unknown
): Either.Either<
  S2SEvidenceStageIdentity,
  S2SDurableEvidenceFileStoreError
> => {
  try {
    const decoded = Schema.decodeUnknownEither(StageIdentitySchema, {
      onExcessProperty: "error"
    })(input)
    if (Either.isLeft(decoded)) {
      return Either.left(
        storeError(
          "RECOVER",
          "IDENTITY_INVALID",
          "stage identity violates the exact fixed schema"
        )
      )
    }
    return Either.right(Object.freeze({ ...decoded.right }))
  } catch {
    return Either.left(
      storeError(
        "RECOVER",
        "IDENTITY_INVALID",
        "stage identity could not be inspected safely"
      )
    )
  }
}

const inspectPrivateDirectory = async (
  path: string,
  label: DirectoryIdentity["label"]
): Promise<DirectoryIdentity> => {
  const stat = await lstat(path)
  if (
    stat.isSymbolicLink() ||
    !stat.isDirectory() ||
    (stat.mode & 0o777) !== 0o700
  ) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      `${label} must be one plain 0700 directory`
    )
  }
  const canonical = await realpath(path)
  if (canonical !== resolve(path)) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      `${label} must not traverse a symbolic link`
    )
  }
  const canonicalStat = await lstat(canonical)
  if (
    canonicalStat.isSymbolicLink() ||
    !canonicalStat.isDirectory() ||
    (canonicalStat.mode & 0o777) !== 0o700
  ) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      `${label} canonical directory is not plain 0700`
    )
  }
  return Object.freeze({
    path: canonical,
    device: canonicalStat.dev,
    inode: canonicalStat.ino,
    label
  })
}

const initializeStore = async (inputRoot: string): Promise<StoreIdentity> => {
  if (!isAbsolute(inputRoot)) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      "evidence root must be an absolute path"
    )
  }
  const requestedRoot = resolve(inputRoot)
  // The root itself is provisioned by the caller so its parent-directory
  // durability and mount semantics stay outside this adapter's claim.
  const root = await inspectPrivateDirectory(requestedRoot, "root")
  const objectsPath = join(root.path, OBJECTS_DIRECTORY_NAME)
  const claimsPath = join(root.path, CLAIMS_DIRECTORY_NAME)
  for (const path of [objectsPath, claimsPath]) {
    try {
      await mkdir(path, { mode: 0o700 })
    } catch (error) {
      if (!(hasErrorCode(error) && error.code === "EEXIST")) throw error
    }
  }
  const objects = await inspectPrivateDirectory(objectsPath, "objects")
  const claims = await inspectPrivateDirectory(claimsPath, "claims")
  const rootHandle = await open(
    root.path,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW
  )
  try {
    await rootHandle.sync()
  } finally {
    await rootHandle.close()
  }
  await assertDirectoryIdentity(root, "INITIALIZE")
  return Object.freeze({ root, objects, claims })
}

const assertDirectoryIdentity = async (
  identity: DirectoryIdentity,
  operation: S2SDurableEvidenceFileStoreError["operation"]
): Promise<void> => {
  const current = await lstat(identity.path)
  if (
    current.isSymbolicLink() ||
    !current.isDirectory() ||
    current.dev !== identity.device ||
    current.ino !== identity.inode ||
    (current.mode & 0o777) !== 0o700
  ) {
    throw storeError(
      operation,
      "ROOT_UNSAFE",
      `${identity.label} identity or permissions changed`
    )
  }
}

const assertStoreIdentity = async (
  identity: StoreIdentity,
  operation: S2SDurableEvidenceFileStoreError["operation"]
): Promise<void> => {
  await assertDirectoryIdentity(identity.root, operation)
  await assertDirectoryIdentity(identity.objects, operation)
  await assertDirectoryIdentity(identity.claims, operation)
}

const readBoundedRegularFile = async (
  path: string,
  maximumBytes: number,
  operation: S2SDurableEvidenceFileStoreError["operation"]
): Promise<Uint8Array> => {
  const flags = constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK
  let handle
  try {
    handle = await open(path, flags)
  } catch (error) {
    if (hasErrorCode(error) && error.code === "ELOOP") {
      throw storeError(
        operation,
        "FILE_TYPE_INVALID",
        "durable evidence entry must not be a symbolic link"
      )
    }
    throw error
  }
  try {
    const before = await handle.stat()
    if (!before.isFile()) {
      throw storeError(
        operation,
        "FILE_TYPE_INVALID",
        "durable evidence entry is not a regular file"
      )
    }
    if (before.size < 1 || before.size > maximumBytes) {
      throw storeError(
        operation,
        "FILE_TOO_LARGE",
        "durable evidence entry violates its fixed byte bound"
      )
    }
    const bounded = Buffer.alloc(before.size + 1)
    let total = 0
    while (total < bounded.byteLength) {
      const result = await handle.read(
        bounded,
        total,
        bounded.byteLength - total,
        total
      )
      if (result.bytesRead === 0) break
      total += result.bytesRead
    }
    if (total > maximumBytes) {
      throw storeError(
        operation,
        "FILE_TOO_LARGE",
        "durable evidence entry grew beyond its fixed byte bound"
      )
    }
    const after = await handle.stat()
    if (
      after.dev !== before.dev ||
      after.ino !== before.ino ||
      after.size !== before.size ||
      total !== before.size
    ) {
      throw storeError(
        operation,
        "IO_FAILED",
        "durable evidence entry changed during bounded read"
      )
    }
    return Uint8Array.from(bounded.subarray(0, total))
  } finally {
    await handle.close()
  }
}

const syncDirectory = async (
  identity: DirectoryIdentity,
  operation: S2SDurableEvidenceFileStoreError["operation"]
): Promise<void> => {
  await assertDirectoryIdentity(identity, operation)
  const handle = await open(
    identity.path,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW
  )
  try {
    await handle.sync()
  } finally {
    await handle.close()
  }
}

const inspectExistingFile = async (
  path: string,
  expected: Uint8Array,
  maximumBytes: number,
  operation: S2SDurableEvidenceFileStoreError["operation"]
): Promise<FileState> => {
  try {
    const existing = await readBoundedRegularFile(path, maximumBytes, operation)
    return sameBytes(existing, expected) ? "SAME" : "DIFFERENT"
  } catch (error) {
    if (hasErrorCode(error) && error.code === "ENOENT") return "MISSING"
    throw error
  }
}

const isAtomicLinkUnsupported = (error: unknown): boolean =>
  hasErrorCode(error) &&
  ["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(error.code)

const confirmPublication = async (
  directory: DirectoryIdentity,
  finalPath: string,
  expected: Uint8Array,
  maximumBytes: number,
  collisionReason: CollisionReason
): Promise<void> => {
  try {
    await syncDirectory(directory, "COMMIT")
  } catch (firstError) {
    const state = await inspectExistingFile(
      finalPath,
      expected,
      maximumBytes,
      "COMMIT"
    )
    if (state !== "SAME") {
      throw storeError(
        "COMMIT",
        "PUBLICATION_OUTCOME_UNKNOWN",
        `directory sync failed and final entry is ${state}`
      )
    }
    try {
      await syncDirectory(directory, "COMMIT")
    } catch (secondError) {
      if (isAtomicLinkUnsupported(secondError)) {
        throw storeError(
          "COMMIT",
          "ATOMIC_PUBLICATION_UNSUPPORTED",
          errorDetail(secondError)
        )
      }
      throw storeError(
        "COMMIT",
        "PUBLICATION_OUTCOME_UNKNOWN",
        `${errorDetail(firstError)}:${errorDetail(secondError)}`
      )
    }
  }
  let readback: FileState
  try {
    readback = await inspectExistingFile(
      finalPath,
      expected,
      maximumBytes,
      "COMMIT"
    )
  } catch (error) {
    throw storeError(
      "COMMIT",
      "PUBLICATION_OUTCOME_UNKNOWN",
      `durable entry readback failed: ${errorDetail(error)}`
    )
  }
  if (readback === "MISSING") {
    throw storeError(
      "COMMIT",
      "PUBLICATION_OUTCOME_UNKNOWN",
      "durable entry disappeared after directory sync"
    )
  }
  if (readback === "DIFFERENT") {
    throw storeError(
      "COMMIT",
      collisionReason,
      "durable entry contains different bytes after directory sync"
    )
  }
}

const publishCreateOnly = async (
  directory: DirectoryIdentity,
  finalName: string,
  inputBytes: Uint8Array,
  maximumBytes: number,
  collisionReason: CollisionReason
): Promise<CreateOnlyOutcome> => {
  const bytes = Uint8Array.from(inputBytes)
  if (bytes.byteLength < 1 || bytes.byteLength > maximumBytes) {
    throw storeError(
      "COMMIT",
      "FILE_TOO_LARGE",
      "publication violates its fixed byte bound"
    )
  }
  await assertDirectoryIdentity(directory, "COMMIT")
  const finalPath = join(directory.path, finalName)
  const temporaryPath = join(
    directory.path,
    `.s2s-evidence-${randomUUID()}.tmp`
  )
  let temporaryCreated = false
  try {
    const handle = await open(
      temporaryPath,
      constants.O_WRONLY |
        constants.O_CREAT |
        constants.O_EXCL |
        constants.O_NOFOLLOW,
      0o600
    )
    temporaryCreated = true
    try {
      await handle.writeFile(bytes)
      await handle.chmod(0o400)
      await handle.sync()
    } finally {
      await handle.close()
    }

    let outcome: CreateOnlyOutcome
    try {
      await link(temporaryPath, finalPath)
      outcome = "Published"
    } catch (error) {
      const existing = await inspectExistingFile(
        finalPath,
        bytes,
        maximumBytes,
        "COMMIT"
      )
      if (existing === "SAME") {
        outcome = "AlreadyPresent"
      } else if (existing === "DIFFERENT") {
        throw storeError(
          "COMMIT",
          collisionReason,
          "create-only destination already contains different bytes"
        )
      } else if (isAtomicLinkUnsupported(error)) {
        throw storeError(
          "COMMIT",
          "ATOMIC_PUBLICATION_UNSUPPORTED",
          errorDetail(error)
        )
      } else {
        throw error
      }
    }
    await confirmPublication(
      directory,
      finalPath,
      bytes,
      maximumBytes,
      collisionReason
    )
    return outcome
  } finally {
    if (temporaryCreated) {
      try {
        await unlink(temporaryPath)
      } catch {
        // A private stale temp does not name a committed content object or claim.
      }
    }
  }
}

const readRequiredFile = async (input: {
  readonly path: string
  readonly maximumBytes: number
  readonly missingReason:
    | "CLAIM_NOT_FOUND"
    | "CONTENT_ADDRESS_CORRUPTION"
    | "PREDECESSOR_MISSING"
  readonly missingDetail: string
}): Promise<Uint8Array> => {
  try {
    return await readBoundedRegularFile(
      input.path,
      input.maximumBytes,
      "RECOVER"
    )
  } catch (error) {
    if (hasErrorCode(error) && error.code === "ENOENT") {
      throw storeError("RECOVER", input.missingReason, input.missingDetail)
    }
    throw error
  }
}

const readContentObject = async (
  identity: StoreIdentity,
  rawSha256: string,
  maximumBytes: number
): Promise<Uint8Array> => {
  if (!CONTENT_OBJECT_PATTERN.test(rawSha256)) {
    throw storeError(
      "RECOVER",
      "CONTENT_ADDRESS_CORRUPTION",
      "content object key is not one lowercase SHA-256"
    )
  }
  const bytes = await readRequiredFile({
    path: join(identity.objects.path, rawSha256),
    maximumBytes,
    missingReason: "CONTENT_ADDRESS_CORRUPTION",
    missingDetail: `referenced content object ${rawSha256} is missing`
  })
  if (rawS2SFileSha256(bytes) !== rawSha256) {
    throw storeError(
      "RECOVER",
      "CONTENT_ADDRESS_CORRUPTION",
      `content object ${rawSha256} contains bytes for another hash`
    )
  }
  return bytes
}

const extractManifestAttachmentIndex = (
  manifestBytes: Uint8Array
): Either.Either<
  ReadonlyArray<{ readonly rawSha256: string; readonly byteLength: number }>,
  S2SDurableEvidenceFileStoreError
> => {
  try {
    const parsed: unknown = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(manifestBytes)
    )
    const decoded = Schema.decodeUnknownEither(ManifestAttachmentIndexSchema)(
      parsed
    )
    if (Either.isLeft(decoded)) {
      return Either.left(
        storeError(
          "RECOVER",
          "CONTENT_ADDRESS_CORRUPTION",
          "manifest attachment index violates its fixed bounds"
        )
      )
    }
    let total = 0
    const lengths = new Map<string, number>()
    for (const attachment of decoded.right.attachments) {
      total += attachment.byte_length
      if (
        !Number.isSafeInteger(total) ||
        total > S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES
      ) {
        return Either.left(
          storeError(
            "RECOVER",
            "CONTENT_ADDRESS_CORRUPTION",
            "manifest attachment index exceeds the total byte bound"
          )
        )
      }
      const priorLength = lengths.get(attachment.raw_sha256)
      if (priorLength !== undefined && priorLength !== attachment.byte_length) {
        return Either.left(
          storeError(
            "RECOVER",
            "CONTENT_ADDRESS_CORRUPTION",
            "one content hash has divergent declared lengths"
          )
        )
      }
      lengths.set(attachment.raw_sha256, attachment.byte_length)
    }
    return Either.right(
      Object.freeze(
        Array.from(lengths, ([rawSha256, byteLength]) =>
          Object.freeze({ rawSha256, byteLength })
        )
      )
    )
  } catch {
    return Either.left(
      storeError(
        "RECOVER",
        "CONTENT_ADDRESS_CORRUPTION",
        "manifest attachment index could not be parsed"
      )
    )
  }
}

const stagesThrough = (
  stage: S2SEvidenceStage
): ReadonlyArray<S2SEvidenceStage> => {
  switch (stage) {
    case "REGISTER":
      return Object.freeze(["REGISTER"])
    case "CONFIRM":
      return Object.freeze(["REGISTER", "CONFIRM"])
    case "ADJUDICATE":
      return Object.freeze(["REGISTER", "CONFIRM", "ADJUDICATE"])
  }
}

const stageIdentityMatches = (
  identity: S2SEvidenceStageIdentity,
  input: {
    readonly source_commit_a: string
    readonly registration_commit_b: string
    readonly workflow_run_id: number
    readonly workflow_run_attempt: number
    readonly stage: S2SEvidenceStage
  },
  stage: S2SEvidenceStage
): boolean =>
  input.source_commit_a === identity.sourceCommitA &&
  input.registration_commit_b === identity.registrationCommitB &&
  input.workflow_run_id === identity.workflowRunId &&
  input.workflow_run_attempt === 1 &&
  input.stage === stage

const sameWorkflowLineage = (
  left: S2SEvidenceEnvelopeSnapshot,
  right: S2SEvidenceEnvelopeSnapshot
): boolean => {
  const leftDocument = left.document
  const rightDocument = right.document
  return (
    leftDocument.source_commit_a === rightDocument.source_commit_a &&
    leftDocument.registration_commit_b ===
      rightDocument.registration_commit_b &&
    leftDocument.workflow_run_id === rightDocument.workflow_run_id &&
    leftDocument.workflow_run_attempt ===
      rightDocument.workflow_run_attempt &&
    leftDocument.workflow_head_sha === rightDocument.workflow_head_sha &&
    leftDocument.workflow_run_created_at_unix_seconds ===
      rightDocument.workflow_run_created_at_unix_seconds &&
    leftDocument.workflow_api_path === rightDocument.workflow_api_path &&
    leftDocument.workflow_file_sha256 ===
      rightDocument.workflow_file_sha256 &&
    leftDocument.workflow_contract_sha256 ===
      rightDocument.workflow_contract_sha256
  )
}

const makeDurableStage = (
  envelope: S2SEvidenceEnvelopeSnapshot,
  claim: S2SEvidenceClaimSnapshot
): S2SDurableEvidenceStage => Object.freeze({ envelope, claim })

const makeRecovery = (
  inputChain: ReadonlyArray<S2SDurableEvidenceStage>
): S2SDurableEvidenceRecovery => {
  const chainSnapshot = Object.freeze(Array.from(inputChain))
  const latest = chainSnapshot[chainSnapshot.length - 1]
  if (latest === undefined) {
    throw storeError(
      "RECOVER",
      "CONTENT_ADDRESS_CORRUPTION",
      "a recovered evidence chain must be nonempty"
    )
  }
  const recovery = Object.freeze({
    chain: chainSnapshot,
    latest
  })
  AUTHENTIC_DURABLE_EVIDENCE_RECOVERIES.add(recovery)
  return recovery
}

const recoverCommittedClaim = (
  storeIdentity: StoreIdentity,
  identity: S2SEvidenceStageIdentity,
  claim: S2SEvidenceClaimSnapshot
): Effect.Effect<
  S2SDurableEvidenceRecovery,
  S2SDurableEvidenceFileStoreError
> =>
  recoverFromDisk(storeIdentity, identity).pipe(
    Effect.mapError((error) =>
      storeError(
        "COMMIT",
        "COMMITTED_READBACK_FAILED",
        `stage=${identity.stage};claim=${claim.claimRawSha256};cause=${error._tag}:${error.reason}`
      )
    )
  )

const recoverFromDisk = (
  storeIdentity: StoreIdentity,
  requestedIdentity: S2SEvidenceStageIdentity
): Effect.Effect<
  S2SDurableEvidenceRecovery,
  S2SDurableEvidenceFileStoreFailure
> =>
  Effect.gen(function* () {
    yield* filesystemEffect("RECOVER", () =>
      assertStoreIdentity(storeIdentity, "RECOVER")
    )
    const stages = stagesThrough(requestedIdentity.stage)
    const chain: Array<S2SDurableEvidenceStage> = []
    for (let index = 0; index < stages.length; index += 1) {
      const stage = stages[index]
      if (stage === undefined) {
        return yield* storeError(
          "RECOVER",
          "CONTENT_ADDRESS_CORRUPTION",
          "stage sequence contains an impossible gap"
        )
      }
      const claimBytes = yield* filesystemEffect(
        "RECOVER",
        () =>
          readRequiredFile({
            path: join(
              storeIdentity.claims.path,
              s2sEvidenceClaimFileName(
                requestedIdentity.registrationCommitB,
                stage
              )
            ),
            maximumBytes: S2S_EVIDENCE_CLAIM_MAX_BYTES,
            missingReason:
              index === stages.length - 1
                ? "CLAIM_NOT_FOUND"
                : "PREDECESSOR_MISSING",
            missingDetail: `claim anchor for ${stage} is missing`
          })
      )
      const claimResult = validateS2SEvidenceClaim(claimBytes)
      if (Either.isLeft(claimResult)) return yield* claimResult.left
      const claim = claimResult.right
      const claimDocument = claim.document
      if (!stageIdentityMatches(requestedIdentity, claimDocument, stage)) {
        return yield* storeError(
          "RECOVER",
          "IDENTITY_MISMATCH",
          `claim anchor for ${stage} does not match the requested identity`
        )
      }

      const manifestBytes = yield* filesystemEffect(
        "RECOVER",
        () =>
          readContentObject(
            storeIdentity,
            claimDocument.manifest_raw_sha256,
            S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES
          )
      )
      const indexResult = extractManifestAttachmentIndex(manifestBytes)
      if (Either.isLeft(indexResult)) return yield* indexResult.left
      const attachments = yield* Effect.forEach(
        indexResult.right,
        (attachment) =>
          filesystemEffect("RECOVER", async () => {
              const bytes = await readContentObject(
                storeIdentity,
                attachment.rawSha256,
                attachment.byteLength
              )
              if (bytes.byteLength !== attachment.byteLength) {
                throw storeError(
                  "RECOVER",
                  "CONTENT_ADDRESS_CORRUPTION",
                  `content object ${attachment.rawSha256} has a divergent length`
                )
              }
              return Object.freeze({
                rawSha256: attachment.rawSha256,
                bytes
              })
          }),
        { concurrency: 1 }
      )
      const envelopeResult = validateS2SEvidenceEnvelope({
        manifestBytes,
        attachments
      })
      if (Either.isLeft(envelopeResult)) return yield* envelopeResult.left
      const envelope = envelopeResult.right
      const boundClaimResult = validateS2SEvidenceClaimForEnvelope(
        claimBytes,
        envelope
      )
      if (Either.isLeft(boundClaimResult)) return yield* boundClaimResult.left
      const boundClaim = boundClaimResult.right
      const envelopeDocument = envelope.document
      if (
        !stageIdentityMatches(requestedIdentity, envelopeDocument, stage)
      ) {
        return yield* storeError(
          "RECOVER",
          "IDENTITY_MISMATCH",
          `claim and manifest identity diverge at ${stage}`
        )
      }

      const previous = chain[chain.length - 1]
      if (previous === undefined) {
        if (
          envelopeDocument.predecessor !== null ||
          claimDocument.predecessor_claim_raw_sha256 !== null
        ) {
          return yield* storeError(
            "RECOVER",
            "PREDECESSOR_MISMATCH",
            "registration evidence unexpectedly names a predecessor"
          )
        }
      } else {
        const predecessor = envelopeDocument.predecessor
        if (
          predecessor === null ||
          predecessor.stage !== previous.envelope.document.stage ||
          predecessor.manifest_raw_sha256 !==
            previous.envelope.manifestRawSha256 ||
          predecessor.claim_raw_sha256 !== previous.claim.claimRawSha256 ||
          claimDocument.predecessor_claim_raw_sha256 !==
            previous.claim.claimRawSha256 ||
          !sameWorkflowLineage(previous.envelope, envelope)
        ) {
          return yield* storeError(
            "RECOVER",
            "PREDECESSOR_MISMATCH",
            `predecessor chain diverges at ${stage}`
          )
        }
      }
      chain.push(makeDurableStage(envelope, boundClaim))
    }
    yield* filesystemEffect("RECOVER", () =>
      assertStoreIdentity(storeIdentity, "RECOVER")
    )
    return makeRecovery(chain)
  })

const prepareCommit = (
  input: S2SEvidenceEnvelopeSnapshot
): Either.Either<PreparedCommit, S2SDurableEvidenceFileStoreFailure> => {
  const validated = validateS2SEvidenceEnvelopeSnapshot(input)
  if (Either.isLeft(validated)) return Either.left(validated.left)
  const claim = buildS2SEvidenceClaim(validated.right)
  if (Either.isLeft(claim)) return Either.left(claim.left)
  return Either.right(
    Object.freeze({ envelope: validated.right, claim: claim.right })
  )
}

const predecessorStage = (
  stage: S2SEvidenceStage
): "REGISTER" | "CONFIRM" | null => {
  switch (stage) {
    case "REGISTER":
      return null
    case "CONFIRM":
      return "REGISTER"
    case "ADJUDICATE":
      return "CONFIRM"
  }
}

const identityForEnvelope = (
  envelope: S2SEvidenceEnvelopeSnapshot
): S2SEvidenceStageIdentity => {
  const document = envelope.document
  return Object.freeze({
    sourceCommitA: document.source_commit_a,
    registrationCommitB: document.registration_commit_b,
    workflowRunId: document.workflow_run_id,
    stage: document.stage
  })
}

const commitPrepared = (
  storeIdentity: StoreIdentity,
  prepared: PreparedCommit
): Effect.Effect<
  S2SDurableEvidencePublication,
  S2SDurableEvidenceFileStoreFailure
> =>
  Effect.gen(function* () {
    yield* filesystemEffect("COMMIT", () =>
      assertStoreIdentity(storeIdentity, "COMMIT")
    )
    const identity = identityForEnvelope(prepared.envelope)
    const claimPath = join(
      storeIdentity.claims.path,
      s2sEvidenceClaimFileName(identity.registrationCommitB, identity.stage)
    )
    const existingClaim = yield* filesystemEffect(
      "COMMIT",
      () =>
        inspectExistingFile(
          claimPath,
          prepared.claim.canonicalBytes,
          S2S_EVIDENCE_CLAIM_MAX_BYTES,
          "COMMIT"
        )
    )
    if (existingClaim === "DIFFERENT") {
      return yield* storeError(
        "COMMIT",
        "CLAIM_CONFLICT",
        "registration commit and stage already have a divergent claim"
      )
    }
    if (existingClaim === "SAME") {
      yield* filesystemEffect(
        "COMMIT",
        () =>
          confirmPublication(
            storeIdentity.claims,
            claimPath,
            prepared.claim.canonicalBytes,
            S2S_EVIDENCE_CLAIM_MAX_BYTES,
            "CLAIM_CONFLICT"
          )
      )
      const recovery = yield* recoverCommittedClaim(
        storeIdentity,
        identity,
        prepared.claim
      )
      if (
        !sameBytes(
          recovery.latest.claim.canonicalBytes,
          prepared.claim.canonicalBytes
        )
      ) {
        return yield* storeError(
          "COMMIT",
          "PUBLICATION_OUTCOME_UNKNOWN",
          "recovered claim differs from the submitted exact claim"
        )
      }
      return Object.freeze({
        _tag: "AlreadyCommitted" as const,
        recovery
      })
    }

    const expectedPredecessor = predecessorStage(identity.stage)
    if (expectedPredecessor !== null) {
      const priorIdentity = Object.freeze({
        ...identity,
        stage: expectedPredecessor
      })
      const priorResult = yield* recoverFromDisk(
        storeIdentity,
        priorIdentity
      ).pipe(Effect.either)
      if (Either.isLeft(priorResult)) {
        if (
          priorResult.left instanceof S2SDurableEvidenceFileStoreError &&
          (priorResult.left.reason === "CLAIM_NOT_FOUND" ||
            priorResult.left.reason === "PREDECESSOR_MISSING")
        ) {
          return yield* storeError(
            "COMMIT",
            "PREDECESSOR_MISSING",
            `committed ${expectedPredecessor} evidence is required first`
          )
        }
        return yield* priorResult.left
      }
      const prior = priorResult.right.latest
      const predecessor = prepared.envelope.document.predecessor
      if (
        predecessor === null ||
        predecessor.stage !== expectedPredecessor ||
        predecessor.manifest_raw_sha256 !==
          prior.envelope.manifestRawSha256 ||
        predecessor.claim_raw_sha256 !== prior.claim.claimRawSha256 ||
        prepared.claim.document.predecessor_claim_raw_sha256 !==
          prior.claim.claimRawSha256 ||
        !sameWorkflowLineage(prior.envelope, prepared.envelope)
      ) {
        return yield* storeError(
          "COMMIT",
          "PREDECESSOR_MISMATCH",
          "submitted envelope does not extend the committed predecessor"
        )
      }
    }

    const publishedAttachmentHashes = new Set<string>()
    for (const attachment of prepared.envelope.attachments) {
      const descriptor = attachment.descriptor
      if (publishedAttachmentHashes.has(descriptor.raw_sha256)) continue
      const bytes = attachment.readBytes()
      yield* filesystemEffect(
        "COMMIT",
        () =>
          publishCreateOnly(
            storeIdentity.objects,
            descriptor.raw_sha256,
            bytes,
            descriptor.byte_length,
            "CONTENT_ADDRESS_CORRUPTION"
          )
      )
      publishedAttachmentHashes.add(descriptor.raw_sha256)
    }
    yield* filesystemEffect(
      "COMMIT",
      () =>
        publishCreateOnly(
          storeIdentity.objects,
          prepared.envelope.manifestRawSha256,
          prepared.envelope.canonicalBytes,
          S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES,
          "CONTENT_ADDRESS_CORRUPTION"
        )
    )
    return yield* Effect.uninterruptible(
      Effect.gen(function* () {
        const claimOutcome = yield* filesystemEffect(
          "COMMIT",
          () =>
            publishCreateOnly(
              storeIdentity.claims,
              s2sEvidenceClaimFileName(
                identity.registrationCommitB,
                identity.stage
              ),
              prepared.claim.canonicalBytes,
              S2S_EVIDENCE_CLAIM_MAX_BYTES,
              "CLAIM_CONFLICT"
            )
        )
        const recovery = yield* recoverCommittedClaim(
          storeIdentity,
          identity,
          prepared.claim
        )
        if (
          !sameBytes(
            recovery.latest.claim.canonicalBytes,
            prepared.claim.canonicalBytes
          ) ||
          recovery.latest.envelope.manifestRawSha256 !==
            prepared.envelope.manifestRawSha256
        ) {
          return yield* storeError(
            "COMMIT",
            "PUBLICATION_OUTCOME_UNKNOWN",
            "post-commit recovery does not equal the submitted envelope and claim"
          )
        }
        return Object.freeze({
          _tag:
            claimOutcome === "AlreadyPresent"
              ? ("AlreadyCommitted" as const)
              : ("Committed" as const),
          recovery
        })
      })
    )
  })

/**
 * Root-private POSIX adapter. Cross-process or cross-job durability exists only
 * when the caller supplies `directory` as a pre-provisioned, shared durable
 * POSIX filesystem root. A runner-local or ephemeral directory does not become
 * GitHub artifact storage merely by using this Layer. The caller owns the
 * root's parent-directory durability and filesystem hard-link/fsync semantics.
 * All parents and the root must exclude hostile same-UID writers and path
 * replacement: Node does not expose openat2-style path confinement, and 0400
 * mode is not immutability against the owning UID.
 *
 * One Layer serializes recovery and commit to bound local memory and I/O.
 * Independent processes still meet at the hard-link CAS; a losing divergent
 * process may leave unreferenced content objects, which are harmless but are
 * not garbage-collected here. Published byte maxima are hard acceptance limits,
 * not an economical memory budget: full three-stage recovery retains all three
 * validated stage snapshots.
 */
export const makeS2SDurableEvidenceFileStoreLayer = (directory: string) =>
  Layer.effect(
    S2SDurableEvidenceFileStore,
    Effect.gen(function* () {
      const identity = yield* Effect.tryPromise({
        try: () => initializeStore(directory),
        catch: initializationError
      }).pipe(Effect.uninterruptible)
      const mutex = yield* Effect.makeSemaphore(1)
      return S2SDurableEvidenceFileStore.of({
        recover: (inputIdentity) =>
          mutex.withPermits(1)(
            Effect.suspend(() => {
              const decoded = exactIdentity(inputIdentity)
              return Either.isLeft(decoded)
                ? Effect.fail(decoded.left)
                : recoverFromDisk(identity, decoded.right)
            })
          ),
        commit: (inputEnvelope) =>
          mutex.withPermits(1)(
            Effect.suspend(() => {
              const prepared = prepareCommit(inputEnvelope)
              return Either.isLeft(prepared)
                ? Effect.fail(prepared.left)
                : commitPrepared(identity, prepared.right)
            })
          )
      })
    })
  )
