import { randomUUID } from "node:crypto"
import { constants } from "node:fs"
import {
  link,
  lstat,
  mkdir,
  open,
  readdir,
  realpath,
  unlink
} from "node:fs/promises"
import { isAbsolute, join, resolve } from "node:path"

import { Context, Data, Effect, Either, Layer, Option } from "effect"

import {
  S2S_DURABLE_JOURNAL_MAX_FILE_BYTES,
  S2S_DURABLE_JOURNAL_MAX_FILES,
  S2SDurableJournalError,
  reconstructS2SDurableJournalChain,
  type S2SDurableJournalSnapshot
} from "./s2s-durable.js"

export { S2S_DURABLE_JOURNAL_MAX_FILE_BYTES } from "./s2s-durable.js"

const JOURNAL_FILE_PATTERN = /^control-journal-(\d{2})\.json$/
const JOURNAL_FILE_PREFIX = "control-journal-"

export type S2SDurableJournalSlot = 1 | 2 | 3 | 4

export interface S2SDurableJournalRecovery {
  readonly exactJournals: ReadonlyArray<Uint8Array>
  readonly latest: Option.Option<S2SDurableJournalSnapshot>
}

export interface S2SDurableJournalPublication {
  readonly _tag: "Published" | "AlreadyPresent"
  readonly slot: S2SDurableJournalSlot
  readonly recovery: S2SDurableJournalRecovery
}

export class S2SDurableJournalFileStoreError extends Data.TaggedError(
  "S2SDurableJournalFileStoreError"
)<{
  readonly operation: "INITIALIZE" | "RECOVER" | "PUBLISH"
  readonly reason:
    | "ATOMIC_PUBLICATION_UNSUPPORTED"
    | "CHAIN_FULL"
    | "CONCURRENT_PUBLICATION_CONFLICT"
    | "FILE_TOO_LARGE"
    | "FILE_TYPE_INVALID"
    | "IO_FAILED"
    | "PUBLICATION_OUTCOME_UNKNOWN"
    | "ROOT_UNSAFE"
    | "SLOT_GAP"
  readonly detail: string
}> {}

export type S2SDurableJournalFileStoreFailure =
  | S2SDurableJournalError
  | S2SDurableJournalFileStoreError

export class S2SDurableJournalFileStore extends Context.Tag(
  "hswm/S2S/DurableJournalFileStore"
)<
  S2SDurableJournalFileStore,
  {
    readonly recover: Effect.Effect<
      S2SDurableJournalRecovery,
      S2SDurableJournalFileStoreFailure
    >
    readonly publishNext: (
      canonicalBytes: Uint8Array
    ) => Effect.Effect<
      S2SDurableJournalPublication,
      S2SDurableJournalFileStoreFailure
    >
  }
>() {}

interface DirectoryIdentity {
  readonly root: string
  readonly device: number
  readonly inode: number
}

const fileNameForSlot = (slot: S2SDurableJournalSlot): string =>
  `control-journal-${String(slot).padStart(2, "0")}.json`

const toSlot = (value: number): S2SDurableJournalSlot | null => {
  switch (value) {
    case 1:
    case 2:
    case 3:
    case 4:
      return value
    default:
      return null
  }
}

const hasErrorCode = (error: unknown): error is { readonly code: string } =>
  typeof error === "object" &&
  error !== null &&
  "code" in error &&
  typeof error.code === "string"

const errorDetail = (error: unknown): string =>
  hasErrorCode(error) ? error.code : "UNKNOWN_FILESYSTEM_ERROR"

const storeError = (
  operation: S2SDurableJournalFileStoreError["operation"],
  reason: S2SDurableJournalFileStoreError["reason"],
  detail: string
): S2SDurableJournalFileStoreError =>
  new S2SDurableJournalFileStoreError({ operation, reason, detail })

const filesystemError = (
  operation: S2SDurableJournalFileStoreError["operation"],
  error: unknown
): S2SDurableJournalFileStoreError =>
  error instanceof S2SDurableJournalFileStoreError
    ? error
    : storeError(operation, "IO_FAILED", errorDetail(error))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const initializeDirectory = async (
  inputRoot: string
): Promise<DirectoryIdentity> => {
  if (!isAbsolute(inputRoot)) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      "journal root must be an absolute path"
    )
  }
  const requestedRoot = resolve(inputRoot)
  await mkdir(requestedRoot, { recursive: true, mode: 0o700 })
  const requestedStat = await lstat(requestedRoot)
  if (
    requestedStat.isSymbolicLink() ||
    !requestedStat.isDirectory() ||
    (requestedStat.mode & 0o077) !== 0
  ) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      "journal root must be a private plain directory"
    )
  }
  const canonicalRoot = await realpath(requestedRoot)
  const canonicalStat = await lstat(canonicalRoot)
  if (
    canonicalStat.isSymbolicLink() ||
    !canonicalStat.isDirectory() ||
    (canonicalStat.mode & 0o077) !== 0
  ) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      "canonical journal root must be a private plain directory"
    )
  }
  return Object.freeze({
    root: canonicalRoot,
    device: canonicalStat.dev,
    inode: canonicalStat.ino
  })
}

const assertDirectoryIdentity = async (
  identity: DirectoryIdentity,
  operation: S2SDurableJournalFileStoreError["operation"]
): Promise<void> => {
  const current = await lstat(identity.root)
  if (
    current.isSymbolicLink() ||
    !current.isDirectory() ||
    current.dev !== identity.device ||
    current.ino !== identity.inode ||
    (current.mode & 0o077) !== 0
  ) {
    throw storeError(
      operation,
      "ROOT_UNSAFE",
      "journal root identity or permissions changed"
    )
  }
}

const readBoundedRegularFile = async (
  path: string,
  operation: S2SDurableJournalFileStoreError["operation"]
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
        "journal slot must not be a symbolic link"
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
        "journal slot is not a regular file"
      )
    }
    if (
      before.size < 1 ||
      before.size > S2S_DURABLE_JOURNAL_MAX_FILE_BYTES
    ) {
      throw storeError(
        operation,
        "FILE_TOO_LARGE",
        "journal slot violates the fixed byte bound"
      )
    }

    const bounded = Buffer.alloc(S2S_DURABLE_JOURNAL_MAX_FILE_BYTES + 1)
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
    if (total > S2S_DURABLE_JOURNAL_MAX_FILE_BYTES) {
      throw storeError(
        operation,
        "FILE_TOO_LARGE",
        "journal slot grew beyond the fixed byte bound"
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
        "journal slot changed during bounded read"
      )
    }
    return Uint8Array.from(bounded.subarray(0, total))
  } finally {
    await handle.close()
  }
}

const readCanonicalChainBytes = async (
  identity: DirectoryIdentity
): Promise<ReadonlyArray<Uint8Array>> => {
  await assertDirectoryIdentity(identity, "RECOVER")
  const entries = await readdir(identity.root, { withFileTypes: true })
  const slots: Array<S2SDurableJournalSlot> = []
  for (const entry of entries) {
    if (!entry.name.startsWith(JOURNAL_FILE_PREFIX)) continue
    const match = JOURNAL_FILE_PATTERN.exec(entry.name)
    const slotText = match?.[1]
    const slot = slotText === undefined ? null : toSlot(Number(slotText))
    if (slot === null) {
      throw storeError(
        "RECOVER",
        "SLOT_GAP",
        "journal directory contains an invalid slot name"
      )
    }
    if (!entry.isFile()) {
      throw storeError(
        "RECOVER",
        "FILE_TYPE_INVALID",
        "journal slot is not a plain directory entry"
      )
    }
    slots.push(slot)
  }
  slots.sort((left, right) => left - right)
  if (slots.some((slot, index) => slot !== index + 1)) {
    throw storeError(
      "RECOVER",
      "SLOT_GAP",
      "journal slots must form one contiguous prefix"
    )
  }
  const files: Array<Uint8Array> = []
  for (const slot of slots) {
    files.push(
      await readBoundedRegularFile(
        join(identity.root, fileNameForSlot(slot)),
        "RECOVER"
      )
    )
  }
  await assertDirectoryIdentity(identity, "RECOVER")
  return Object.freeze(files.map((bytes) => Uint8Array.from(bytes)))
}

const makeRecovery = (
  canonicalJournals: ReadonlyArray<Uint8Array>
): Either.Either<S2SDurableJournalRecovery, S2SDurableJournalError> => {
  const journalSnapshots = Object.freeze(
    canonicalJournals.map((bytes) => Uint8Array.from(bytes))
  )
  if (journalSnapshots.length === 0) {
    const recovery: S2SDurableJournalRecovery = {
      get exactJournals(): ReadonlyArray<Uint8Array> {
        return Object.freeze([])
      },
      get latest(): Option.Option<S2SDurableJournalSnapshot> {
        return Option.none()
      }
    }
    return Either.right(
      Object.freeze(recovery)
    )
  }
  const reconstructed = reconstructS2SDurableJournalChain(journalSnapshots)
  if (Either.isLeft(reconstructed)) return Either.left(reconstructed.left)
  const latestSnapshot = reconstructed.right
  const recovery: S2SDurableJournalRecovery = {
    get exactJournals(): ReadonlyArray<Uint8Array> {
      return Object.freeze(
        journalSnapshots.map((bytes) => Uint8Array.from(bytes))
      )
    },
    get latest(): Option.Option<S2SDurableJournalSnapshot> {
      return Option.some(latestSnapshot)
    }
  }
  return Either.right(
    Object.freeze(recovery)
  )
}

const recoverFromDisk = (
  identity: DirectoryIdentity
): Effect.Effect<
  S2SDurableJournalRecovery,
  S2SDurableJournalFileStoreFailure
> =>
  Effect.gen(function* () {
    const bytes = yield* Effect.tryPromise({
      try: () => readCanonicalChainBytes(identity),
      catch: (error) => filesystemError("RECOVER", error)
    })
    const recovery = makeRecovery(bytes)
    if (Either.isLeft(recovery)) return yield* recovery.left
    return recovery.right
  })

const syncDirectory = async (identity: DirectoryIdentity): Promise<void> => {
  await assertDirectoryIdentity(identity, "PUBLISH")
  const handle = await open(identity.root, constants.O_RDONLY)
  try {
    await handle.sync()
  } finally {
    await handle.close()
  }
}

type ExistingSlot = "MISSING" | "SAME" | "DIFFERENT"

const inspectExistingSlot = async (
  finalPath: string,
  expected: Uint8Array
): Promise<ExistingSlot> => {
  try {
    const existing = await readBoundedRegularFile(finalPath, "PUBLISH")
    return sameBytes(existing, expected) ? "SAME" : "DIFFERENT"
  } catch (error) {
    if (hasErrorCode(error) && error.code === "ENOENT") return "MISSING"
    throw error
  }
}

const isAtomicLinkUnsupported = (error: unknown): boolean =>
  hasErrorCode(error) &&
  ["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(error.code)

const confirmDirectoryDurability = async (
  identity: DirectoryIdentity,
  finalPath: string,
  expected: Uint8Array
): Promise<void> => {
  try {
    await syncDirectory(identity)
    return
  } catch (firstError) {
    const state = await inspectExistingSlot(finalPath, expected)
    if (state !== "SAME") {
      throw storeError(
        "PUBLISH",
        "PUBLICATION_OUTCOME_UNKNOWN",
        `directory sync failed and final slot is ${state}`
      )
    }
    try {
      await syncDirectory(identity)
      return
    } catch (secondError) {
      if (isAtomicLinkUnsupported(secondError)) {
        throw storeError(
          "PUBLISH",
          "ATOMIC_PUBLICATION_UNSUPPORTED",
          errorDetail(secondError)
        )
      }
      throw storeError(
        "PUBLISH",
        "PUBLICATION_OUTCOME_UNKNOWN",
        `${errorDetail(firstError)}:${errorDetail(secondError)}`
      )
    }
  }
}

const publishCreateOnly = async (
  identity: DirectoryIdentity,
  slot: S2SDurableJournalSlot,
  inputBytes: Uint8Array
): Promise<"Published" | "AlreadyPresent"> => {
  const bytes = Uint8Array.from(inputBytes)
  if (
    bytes.byteLength < 1 ||
    bytes.byteLength > S2S_DURABLE_JOURNAL_MAX_FILE_BYTES
  ) {
    throw storeError(
      "PUBLISH",
      "FILE_TOO_LARGE",
      "journal publication violates the fixed byte bound"
    )
  }
  await assertDirectoryIdentity(identity, "PUBLISH")
  const finalPath = join(identity.root, fileNameForSlot(slot))
  const temporaryPath = join(
    identity.root,
    `.s2s-durable-${String(slot).padStart(2, "0")}-${randomUUID()}.tmp`
  )
  let temporaryCreated = false
  try {
    const flags =
      constants.O_WRONLY |
      constants.O_CREAT |
      constants.O_EXCL |
      constants.O_NOFOLLOW
    const handle = await open(temporaryPath, flags, 0o600)
    temporaryCreated = true
    try {
      await handle.writeFile(bytes)
      await handle.chmod(0o400)
      await handle.sync()
    } finally {
      await handle.close()
    }

    let outcome: "Published" | "AlreadyPresent"
    try {
      await link(temporaryPath, finalPath)
      outcome = "Published"
    } catch (error) {
      const existing = await inspectExistingSlot(finalPath, bytes)
      if (existing === "SAME") {
        outcome = "AlreadyPresent"
      } else if (existing === "DIFFERENT") {
        throw storeError(
          "PUBLISH",
          "CONCURRENT_PUBLICATION_CONFLICT",
          "journal slot already contains different canonical bytes"
        )
      } else if (isAtomicLinkUnsupported(error)) {
        throw storeError(
          "PUBLISH",
          "ATOMIC_PUBLICATION_UNSUPPORTED",
          errorDetail(error)
        )
      } else {
        throw error
      }
    }
    await confirmDirectoryDurability(identity, finalPath, bytes)
    return outcome
  } finally {
    if (temporaryCreated) {
      try {
        await unlink(temporaryPath)
      } catch {
        // A private stale temp file never changes an immutable journal slot.
      }
    }
  }
}

/**
 * POSIX/Linux local-filesystem adapter. The injected absolute root and its
 * parents must be controlled by the runner; Node does not expose openat2, so
 * an attacker able to replace parent directories is outside this adapter's
 * safety boundary.
 */
export const makeS2SDurableJournalFileStoreLayer = (directory: string) =>
  Layer.effect(
    S2SDurableJournalFileStore,
    Effect.gen(function* () {
      const identity = yield* Effect.tryPromise({
        try: () => initializeDirectory(directory),
        catch: (error) => filesystemError("INITIALIZE", error)
      })
      return S2SDurableJournalFileStore.of({
        recover: recoverFromDisk(identity),
        publishNext: (inputBytes) => {
          if (
            !(inputBytes instanceof Uint8Array) ||
            inputBytes.byteLength < 1 ||
            inputBytes.byteLength > S2S_DURABLE_JOURNAL_MAX_FILE_BYTES
          ) {
            return Effect.fail(
              storeError(
                "PUBLISH",
                "FILE_TOO_LARGE",
                "journal publication violates the fixed byte bound"
              )
            )
          }
          const canonicalBytes = Uint8Array.from(inputBytes)
          return Effect.gen(function* () {
            const current = yield* recoverFromDisk(identity)
            const currentJournals = current.exactJournals
            const alreadyPresentIndex = currentJournals.findIndex(
              (bytes) => sameBytes(bytes, canonicalBytes)
            )
            if (alreadyPresentIndex >= 0) {
              const slot = toSlot(alreadyPresentIndex + 1)
              if (slot === null) {
                return yield* storeError(
                  "PUBLISH",
                  "CHAIN_FULL",
                  "existing journal index exceeds the fixed chain bound"
                )
              }
              const finalPath = join(identity.root, fileNameForSlot(slot))
              yield* Effect.tryPromise({
                try: () =>
                  confirmDirectoryDurability(
                    identity,
                    finalPath,
                    canonicalBytes
                  ),
                catch: (error) => filesystemError("PUBLISH", error)
              })
              const recovery = yield* recoverFromDisk(identity)
              const stored = recovery.exactJournals[slot - 1]
              if (stored === undefined || !sameBytes(stored, canonicalBytes)) {
                return yield* storeError(
                  "PUBLISH",
                  "PUBLICATION_OUTCOME_UNKNOWN",
                  "reconciled existing slot does not equal the submitted bytes"
                )
              }
              return Object.freeze({
                _tag: "AlreadyPresent" as const,
                slot,
                recovery
              })
            }
            for (
              let prefixLength = 0;
              prefixLength < currentJournals.length;
              prefixLength += 1
            ) {
              const occupiedSlotCandidate =
                reconstructS2SDurableJournalChain([
                  ...currentJournals.slice(0, prefixLength),
                  canonicalBytes
                ])
              if (Either.isRight(occupiedSlotCandidate)) {
                return yield* storeError(
                  "PUBLISH",
                  "CONCURRENT_PUBLICATION_CONFLICT",
                  "submitted bytes target an occupied slot with different bytes"
                )
              }
            }
            if (
              currentJournals.length >=
              S2S_DURABLE_JOURNAL_MAX_FILES
            ) {
              return yield* storeError(
                "PUBLISH",
                "CHAIN_FULL",
                "durable journal chain already has four slots"
              )
            }
            const candidateChain = [
              ...currentJournals,
              canonicalBytes
            ]
            const validated = reconstructS2SDurableJournalChain(candidateChain)
            if (Either.isLeft(validated)) return yield* validated.left
            const slot = toSlot(candidateChain.length)
            if (slot === null) {
              return yield* storeError(
                "PUBLISH",
                "CHAIN_FULL",
                "candidate journal exceeds the fixed chain bound"
              )
            }
            const outcome = yield* Effect.tryPromise({
              try: () => publishCreateOnly(identity, slot, canonicalBytes),
              catch: (error) => filesystemError("PUBLISH", error)
            })
            const recovery = yield* recoverFromDisk(identity)
            const stored = recovery.exactJournals[slot - 1]
            if (stored === undefined || !sameBytes(stored, canonicalBytes)) {
              return yield* storeError(
                "PUBLISH",
                "PUBLICATION_OUTCOME_UNKNOWN",
                "recovered slot does not equal the submitted bytes"
              )
            }
            return Object.freeze({ _tag: outcome, slot, recovery })
          })
        }
      })
    })
  )
