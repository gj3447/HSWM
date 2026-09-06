import { createHash, randomUUID } from "node:crypto"
import { dirname, isAbsolute, join, resolve } from "node:path"

import { Effect, Either, Layer, Ref } from "effect"

import {
  CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES,
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
  CanonicalAtomV2StateJournalStore,
  CanonicalAtomV2StateJournalStoreError,
  makeCanonicalAtomV2StateJournalStoreError,
  snapshotCanonicalAtomV2StateJournalRecovery,
  snapshotCanonicalAtomV2StateJournalRecoveryLimits,
  type CanonicalAtomV2StateJournalEntry,
  type CanonicalAtomV2StateJournalPublish,
  type CanonicalAtomV2StateJournalPublication,
  type CanonicalAtomV2StateJournalRecoveryLimits,
  type CanonicalAtomV2StateJournalStoreFailure
} from "./canonical-atom-v2-state-journal-store.js"
import { makeCanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import type { CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"
import {
  NodePosixFileSystem,
  PosixFileSystem,
  PosixIoError,
  type BoundedReadResult,
  type PosixFileSystemShape,
  type PosixIoErrorCode
} from "./effect-posix-filesystem.js"

const OBJECTS = "journal-objects"
const SLOTS = "journal-slots"
const DIGEST = /^[0-9a-f]{64}$/
const LINEAGE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const FS_OPERATION = "canonical-atom-v2-state-journal"

/** Package-root-private in-process interruption points for tests, not power-loss simulation. */
export const CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST =
  Object.freeze([
    "object-file-fsync:before",
    "object-file-fsync:after",
    "object-link:before",
    "object-link:after",
    "object-directory-fsync:before",
    "object-directory-fsync:after",
    "object-readback:before",
    "object-readback:after",
    "slot-link:before",
    "slot-link:after",
    "slot-directory-fsync:before",
    "slot-directory-fsync:after",
    "journal-readback:before",
    "journal-readback:after"
  ] as const)

export type CanonicalAtomV2StateJournalFilePublicationCheckpointForTest =
  typeof CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST[number]

/** Native-like adapter calls that internal tests may fail without changing production wiring. */
export const CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_IO_FAULT_POINTS_FOR_TEST =
  Object.freeze([
    "object-file-fsync",
    "object-link",
    "object-directory-fsync",
    "object-readback",
    "slot-link",
    "slot-directory-fsync",
    "slot-reconciliation-readback",
    "journal-readback",
    "known-commit-object-directory-fsync",
    "known-commit-slot-directory-fsync"
  ] as const)

export type CanonicalAtomV2StateJournalFileIoFaultPointForTest =
  typeof CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_IO_FAULT_POINTS_FOR_TEST[number]

export type CanonicalAtomV2StateJournalFileIoFaultCodeForTest =
  | "EIO"
  | "ENOSYS"
  | "ENOTSUP"
  | "EOPNOTSUPP"
  | "EXDEV"

export interface CanonicalAtomV2StateJournalFileIoFaultForTest {
  readonly point: CanonicalAtomV2StateJournalFileIoFaultPointForTest
  readonly phase: "before" | "after"
  readonly code: CanonicalAtomV2StateJournalFileIoFaultCodeForTest
  readonly onInjected?: () => void
}

type StoreError = CanonicalAtomV2StateJournalStoreError
type StoreOperation = StoreError["operation"]
/**
 * Internal effects carry two failure kinds: an exact store failure, or the
 * adapter's typed I/O failure standing in for the raw errno the operation
 * boundary maps to its operation-specific IO_FAILED.
 */
type JournalEffect<A> = Effect.Effect<A, StoreError | PosixIoError>
type PublicationInterruptionForTest =
  CanonicalAtomV2StateJournalFilePublicationCheckpointForTest | null
/** Fails with the native-like typed code the adapter would have reported at that call. */
type IoFaultInjectorForTest = (
  point: CanonicalAtomV2StateJournalFileIoFaultPointForTest,
  phase: CanonicalAtomV2StateJournalFileIoFaultForTest["phase"]
) => Effect.Effect<void, PosixIoError>
type BeforeSlotLinkForTest = (() => Promise<void>) | null

interface DirectoryIdentity { readonly path: string; readonly device: number; readonly inode: number }
interface Identity { readonly root: DirectoryIdentity; readonly objects: DirectoryIdentity; readonly slots: DirectoryIdentity }

const error = makeCanonicalAtomV2StateJournalStoreError
const hash = (text: string): string => createHash("sha256").update(text, "utf8").digest("hex")
const sameBytes = (a: Uint8Array, b: Uint8Array): boolean => a.byteLength === b.byteLength && a.every((x, i) => x === b[i])
const sameDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor | null,
  right: CanonicalAtomV2StateJournalRecordDescriptor | null
): boolean =>
  left === null || right === null
    ? left === right
    : left.mediaType === right.mediaType &&
      left.byteLength === right.byteLength &&
      left.sha256 === right.sha256
const fromEither = <A>(either: Either.Either<A, StoreError>): Effect.Effect<A, StoreError> =>
  Either.isLeft(either) ? Effect.fail(either.left) : Effect.succeed(either.right)
const noFault: IoFaultInjectorForTest = () => Effect.void

const COMMIT_MAY_BE_VISIBLE_CHECKPOINTS: ReadonlySet<CanonicalAtomV2StateJournalFilePublicationCheckpointForTest> =
  new Set<CanonicalAtomV2StateJournalFilePublicationCheckpointForTest>([
    "slot-link:after",
    "slot-directory-fsync:before",
    "slot-directory-fsync:after",
    "journal-readback:before",
    "journal-readback:after"
  ])
const UNSUPPORTED_LINK_CODES: ReadonlySet<string> = new Set<string>(["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"])

const interruptPublicationForTest = (
  interruption: PublicationInterruptionForTest,
  checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest
): Effect.Effect<void, StoreError> =>
  interruption === checkpoint
    ? Effect.fail(error(
        "PUBLISH",
        COMMIT_MAY_BE_VISIBLE_CHECKPOINTS.has(checkpoint)
          ? "PUBLICATION_OUTCOME_UNKNOWN"
          : "IO_FAILED",
        `test-only publication interruption at ${checkpoint}`
      ))
    : Effect.void

/** EIO has no dedicated adapter code; the adapter reports it as IO_FAILED, exactly as a native EIO would surface. */
const faultCode = (code: CanonicalAtomV2StateJournalFileIoFaultCodeForTest): PosixIoErrorCode =>
  code === "EIO" ? "IO_FAILED" : code

const makeIoFaultInjectorForTest = (
  plan: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>
): Effect.Effect<IoFaultInjectorForTest> => {
  const retained: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest> =
    Object.freeze(plan.map((fault) => Object.freeze({ ...fault })))
  return Effect.map(Ref.make(0), (nextIndex): IoFaultInjectorForTest => (point, phase) =>
    Ref.modify(nextIndex, (index): readonly [CanonicalAtomV2StateJournalFileIoFaultForTest | null, number] => {
      const next = retained[index]
      return next === undefined || next.point !== point || next.phase !== phase
        ? [null, index]
        : [next, index + 1]
    }).pipe(
      Effect.flatMap((next) =>
        next === null
          ? Effect.void
          : Effect.sync(() => { next.onInjected?.() }).pipe(
              Effect.zipRight(Effect.fail(new PosixIoError({
                operation: FS_OPERATION,
                path: `${point}:${phase}`,
                code: faultCode(next.code),
                detail: `test-only ${next.code} at ${point}:${phase}`
              })))
            )
      )
    )
  )
}

const snapshotExpectedPredecessor = (
  input: CanonicalAtomV2StateJournalRecordDescriptor | null
): Either.Either<CanonicalAtomV2StateJournalRecordDescriptor | null, StoreError> => {
  if (input === null) return Either.right(null)
  if (
    typeof input !== "object" ||
    input.mediaType !== HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE ||
    !Number.isSafeInteger(input.byteLength) ||
    input.byteLength < 1 ||
    input.byteLength > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES ||
    !DIGEST.test(input.sha256)
  ) {
    return Either.left(error("PUBLISH", "PREDECESSOR_MISMATCH", "predecessor must be an exact journal record descriptor or null"))
  }
  return Either.right(Object.freeze({ ...input }))
}

const recordDescriptor = (
  bytes: Uint8Array,
  operation: "RECOVER" | "PUBLISH"
): Either.Either<CanonicalAtomV2StateJournalRecordDescriptor, StoreError> => {
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
    bytes
  )
  if (Either.isLeft(descriptor)) {
    return Either.left(error(
      operation,
      operation === "RECOVER" ? "CORRUPT_ENTRY" : "BYTE_LENGTH_INVALID",
      "journal bytes cannot form a record descriptor"
    ))
  }
  return Either.right(Object.freeze({
    mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
    byteLength: descriptor.right.byteLength,
    sha256: descriptor.right.sha256
  }))
}

export const canonicalAtomV2StateJournalSlotName = (
  journalLineageId: string,
  schemaContentSha256: string,
  stateRevision: number
): string => hash(`hswm-canonical-atom-v2-state-journal-slot/v1\u0000${journalLineageId}\u0000${schemaContentSha256}\u0000${stateRevision}`)

const inspectDirectory = (
  fs: PosixFileSystemShape,
  path: string,
  operation: StoreOperation
): JournalEffect<DirectoryIdentity> =>
  fs.identity(path, FS_OPERATION).pipe(
    Effect.flatMap((identity) =>
      identity.kind !== "DIRECTORY" || identity.mode !== 0o700
        ? Effect.fail(error(operation, "ROOT_UNSAFE", "journal directory must be a private plain 0700 directory"))
        : Effect.succeed(Object.freeze({ path, device: identity.device, inode: identity.inode }))
    )
  )

const assertDirectory = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  operation: StoreOperation
): JournalEffect<void> =>
  fs.identity(directory.path, FS_OPERATION).pipe(
    Effect.flatMap((identity) =>
      identity.kind !== "DIRECTORY" ||
      identity.device !== directory.device ||
      identity.inode !== directory.inode ||
      identity.mode !== 0o700
        ? Effect.fail(error(operation, "ROOT_UNSAFE", "journal directory identity or permissions changed"))
        : Effect.void
    )
  )

const assertJournalDirectories = (
  fs: PosixFileSystemShape,
  identity: Identity,
  operation: StoreOperation
): JournalEffect<void> =>
  Effect.gen(function* () {
    yield* assertDirectory(fs, identity.root, operation)
    yield* assertDirectory(fs, identity.objects, operation)
    yield* assertDirectory(fs, identity.slots, operation)
  })

/** mkdir 0700 whose EEXIST is not a failure; the caller inspects the result either way. */
const makeDirectoryIfAbsent = (fs: PosixFileSystemShape, path: string): Effect.Effect<void, PosixIoError> =>
  fs.makeDirectory(path, { mode: 0o700, operation: FS_OPERATION }).pipe(
    Effect.catchIf((cause) => cause.code === "EEXIST", () => Effect.void)
  )

const initialize = (fs: PosixFileSystemShape, rootPath: string): JournalEffect<Identity> =>
  Effect.gen(function* () {
    if (!isAbsolute(rootPath)) return yield* Effect.fail(error("INITIALIZE", "ROOT_UNSAFE", "journal root must be absolute"))
    const requested = resolve(rootPath)
    yield* makeDirectoryIfAbsent(fs, requested)
    const requestedIdentity = yield* fs.identity(requested, FS_OPERATION)
    if (requestedIdentity.kind !== "DIRECTORY") {
      return yield* Effect.fail(error("INITIALIZE", "ROOT_UNSAFE", "requested journal root must be a plain directory"))
    }
    const rootRealPath = yield* fs.realpath(requested, FS_OPERATION)
    const root = yield* inspectDirectory(fs, rootRealPath, "INITIALIZE")
    yield* fs.syncDirectory(dirname(root.path), FS_OPERATION)
    yield* makeDirectoryIfAbsent(fs, join(root.path, OBJECTS))
    yield* makeDirectoryIfAbsent(fs, join(root.path, SLOTS))
    const objects = yield* inspectDirectory(fs, join(root.path, OBJECTS), "INITIALIZE")
    const slots = yield* inspectDirectory(fs, join(root.path, SLOTS), "INITIALIZE")
    yield* fs.syncDirectory(root.path, FS_OPERATION)
    return Object.freeze({ root, objects, slots })
  })

const boundedReadFailure = (operation: "RECOVER" | "PUBLISH") => (cause: PosixIoError): StoreError | PosixIoError =>
  cause.code === "NOT_REGULAR_FILE" || cause.code === "MODE_INVALID"
    ? error(operation, "FILE_TYPE_INVALID", "journal entry must be immutable regular 0400 file")
    : cause.code === "BYTE_BOUND_EXCEEDED"
      ? error(operation, "CORRUPT_ENTRY", "journal entry violates byte bound")
      : cause.code === "IDENTITY_CHANGED"
        ? error(operation, "CORRUPT_ENTRY", "journal entry changed during bounded read")
        : cause

/** Bounded no-follow 0400 read whose file identity is re-checked after the read. */
const readRegular = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  name: string,
  operation: "RECOVER" | "PUBLISH",
  injectIoFault: IoFaultInjectorForTest = noFault,
  faultPoint: CanonicalAtomV2StateJournalFileIoFaultPointForTest | null = null
): JournalEffect<BoundedReadResult> =>
  Effect.gen(function* () {
    yield* assertDirectory(fs, directory, operation)
    if (faultPoint !== null) yield* injectIoFault(faultPoint, "before")
    const result = yield* fs.readRegularBounded(join(directory.path, name), {
      maximumBytes: CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES,
      minimumBytes: 1,
      requiredMode: 0o400,
      operation: FS_OPERATION
    }).pipe(Effect.mapError(boundedReadFailure(operation)))
    if (faultPoint !== null) yield* injectIoFault(faultPoint, "after")
    return result
  })

const syncDirectory = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  operation: "PUBLISH" | "RECOVER",
  injectIoFault: IoFaultInjectorForTest,
  faultPoint: CanonicalAtomV2StateJournalFileIoFaultPointForTest
): JournalEffect<void> =>
  Effect.gen(function* () {
    yield* assertDirectory(fs, directory, operation)
    yield* injectIoFault(faultPoint, "before")
    yield* fs.syncDirectory(directory.path, FS_OPERATION)
    yield* injectIoFault(faultPoint, "after")
  })

/** One retry re-establishes durability of an already-visible exact commit; a second failure is an unknown outcome. */
const syncKnownCommit = (
  fs: PosixFileSystemShape,
  identity: Identity,
  injectIoFault: IoFaultInjectorForTest
): Effect.Effect<void, StoreError> => {
  const attempt = syncDirectory(fs, identity.objects, "PUBLISH", injectIoFault, "known-commit-object-directory-fsync").pipe(
    Effect.zipRight(syncDirectory(fs, identity.slots, "PUBLISH", injectIoFault, "known-commit-slot-directory-fsync"))
  )
  return attempt.pipe(
    Effect.catchAll(() =>
      attempt.pipe(
        Effect.mapError(() => error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal object and slot durability could not be re-established"))
      )
    )
  )
}

/**
 * Content-addressed object publication: exclusive private staging file with
 * fsync, no-replace hard link into the immutable object name, directory
 * fsync with one reconciled retry, exact readback, and unconditional staging
 * cleanup.  Every failure is a typed value.
 */
const publishObject = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  name: string,
  bytes: Uint8Array,
  interruption: PublicationInterruptionForTest,
  injectIoFault: IoFaultInjectorForTest
): JournalEffect<void> => {
  const finalPath = join(directory.path, name)
  const interrupt = (checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest) =>
    interruptPublicationForTest(interruption, checkpoint)
  const readExisting = (): JournalEffect<BoundedReadResult> => readRegular(fs, directory, name, "PUBLISH")
  // A failed link is reconciled by exact readback; only when the destination
  // cannot be read does the link's own code decide the failure.
  const reconcileLink = (cause: PosixIoError): JournalEffect<void> =>
    readExisting().pipe(
      Effect.flatMap((existing) =>
        sameBytes(existing.bytes, bytes)
          ? Effect.void
          : Effect.fail(error("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "immutable journal destination has different bytes"))
      ),
      Effect.catchTag("PosixIoError", (readCause) =>
        Effect.fail(
          UNSUPPORTED_LINK_CODES.has(cause.code)
            ? error("PUBLISH", "ATOMIC_PUBLICATION_UNSUPPORTED", cause.code)
            : readCause
        )
      )
    )
  const syncObjectDirectory = (): JournalEffect<void> =>
    syncDirectory(fs, directory, "PUBLISH", injectIoFault, "object-directory-fsync")
  const establishObjectDurability: JournalEffect<void> = syncObjectDirectory().pipe(
    Effect.catchAll(() =>
      readExisting().pipe(
        Effect.flatMap((existing) =>
          sameBytes(existing.bytes, bytes)
            ? syncObjectDirectory()
            : Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal entry differs after directory sync failure"))
        ),
        Effect.catchTag("PosixIoError", () =>
          Effect.fail(error("PUBLISH", "IO_FAILED", "object directory durability could not be established before slot publication"))
        )
      )
    )
  )
  const stage = (temporary: string): JournalEffect<void> =>
    Effect.gen(function* () {
      // The staging write, 0400 chmod, and file fsync are one exclusive adapter call.
      yield* interrupt("object-file-fsync:before")
      yield* injectIoFault("object-file-fsync", "before")
      yield* fs.writeExclusive(temporary, bytes, { mode: 0o600, finalMode: 0o400, sync: true, operation: FS_OPERATION })
      yield* injectIoFault("object-file-fsync", "after")
      yield* interrupt("object-file-fsync:after")
      yield* interrupt("object-link:before")
      yield* injectIoFault("object-link", "before").pipe(
        Effect.zipRight(fs.linkNoReplace(temporary, finalPath, FS_OPERATION)),
        Effect.zipRight(injectIoFault("object-link", "after")),
        Effect.catchAll(reconcileLink)
      )
      yield* interrupt("object-link:after")
      yield* interrupt("object-directory-fsync:before")
      yield* establishObjectDurability
      yield* interrupt("object-directory-fsync:after")
      yield* interrupt("object-readback:before")
      const exact = yield* readRegular(fs, directory, name, "PUBLISH", injectIoFault, "object-readback")
      if (!sameBytes(exact.bytes, bytes)) {
        return yield* Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal readback differs"))
      }
      yield* interrupt("object-readback:after")
    })
  return Effect.gen(function* () {
    yield* assertDirectory(fs, directory, "PUBLISH")
    const temporary = join(directory.path, `.journal-${randomUUID()}.tmp`)
    // An orphan private staging file has no journal meaning; its removal never changes the outcome.
    yield* stage(temporary).pipe(
      Effect.ensuring(fs.unlinkIfPresent(temporary, FS_OPERATION).pipe(Effect.ignore))
    )
  })
}

const recover = (
  fs: PosixFileSystemShape,
  identity: Identity,
  journalLineageId: string,
  schemaContentSha256: string,
  rawLimits: CanonicalAtomV2StateJournalRecoveryLimits | null = null
): JournalEffect<ReadonlyArray<CanonicalAtomV2StateJournalEntry>> =>
  Effect.gen(function* () {
    yield* assertJournalDirectories(fs, identity, "RECOVER")
    const limits = rawLimits === null
      ? null
      : yield* fromEither(snapshotCanonicalAtomV2StateJournalRecoveryLimits(rawLimits))
    const entries: ReadonlyArray<import("./effect-posix-filesystem.js").DirectoryEntry> =
      yield* fs.listDirectory(identity.slots.path, FS_OPERATION)
    if (limits !== null && entries.length > limits.maximumRecords) {
      return yield* Effect.fail(error("RECOVER", "RECOVERY_LIMIT_EXCEEDED", "journal recovery exceeds the record limit"))
    }
    if (entries.some((entry) => entry.kind !== "FILE" || !DIGEST.test(entry.name))) {
      return yield* Effect.fail(error("RECOVER", "SLOT_LAYOUT_INVALID", "journal slots contain malformed or nonregular entry"))
    }
    const finalNames = entries.map((entry) => entry.name)
    const expected: ReadonlySet<string> = new Set(
      finalNames.map((_, revision) => canonicalAtomV2StateJournalSlotName(journalLineageId, schemaContentSha256, revision))
    )
    if (finalNames.length !== expected.size || finalNames.some((name) => !expected.has(name))) {
      return yield* Effect.fail(error("RECOVER", "SLOT_LAYOUT_INVALID", "journal slots must be exactly the contiguous revision prefix"))
    }
    const recovered: Array<CanonicalAtomV2StateJournalEntry> = []
    let recoveredBytes = 0
    for (let revision = 0; revision < finalNames.length; revision += 1) {
      const slot = canonicalAtomV2StateJournalSlotName(journalLineageId, schemaContentSha256, revision)
      if (limits !== null) {
        const slotIdentity = yield* fs.identity(join(identity.slots.path, slot), FS_OPERATION)
        if (slotIdentity.kind !== "FILE") {
          return yield* Effect.fail(error("RECOVER", "SLOT_LAYOUT_INVALID", "journal slot changed to a nonregular entry during recovery"))
        }
        if (
          !Number.isSafeInteger(recoveredBytes + slotIdentity.size) ||
          recoveredBytes + slotIdentity.size > limits.maximumRecoveredJournalBytes
        ) {
          return yield* Effect.fail(error("RECOVER", "RECOVERY_LIMIT_EXCEEDED", "journal recovery exceeds the byte limit"))
        }
      }
      const slotEntry = yield* readRegular(fs, identity.slots, slot, "RECOVER")
      recoveredBytes += slotEntry.bytes.byteLength
      if (
        limits !== null &&
        (!Number.isSafeInteger(recoveredBytes) || recoveredBytes > limits.maximumRecoveredJournalBytes)
      ) {
        return yield* Effect.fail(error("RECOVER", "RECOVERY_LIMIT_EXCEEDED", "journal recovery exceeds the byte limit"))
      }
      const descriptor = yield* fromEither(recordDescriptor(slotEntry.bytes, "RECOVER"))
      const objectEntry = yield* readRegular(fs, identity.objects, descriptor.sha256, "RECOVER").pipe(
        Effect.catchTag("PosixIoError", (cause) =>
          Effect.fail(
            cause.code === "ENOENT"
              ? error("RECOVER", "CORRUPT_ENTRY", "journal slot has no exact content-addressed object")
              : cause
          )
        )
      )
      if (
        !sameBytes(slotEntry.bytes, objectEntry.bytes) ||
        slotEntry.device !== objectEntry.device ||
        slotEntry.inode !== objectEntry.inode
      ) {
        return yield* Effect.fail(error("RECOVER", "CORRUPT_ENTRY", "journal slot and object must be identical hard links"))
      }
      recovered.push(Object.freeze({ descriptor, bytes: Uint8Array.from(slotEntry.bytes) }))
    }
    yield* assertJournalDirectories(fs, identity, "RECOVER")
    return snapshotCanonicalAtomV2StateJournalRecovery(recovered)
  })

/** After the slot may already be visible, a raw reconciliation failure is an unknown outcome, never an old-prefix claim. */
const recoverAfterSlotMayBeVisible = (
  fs: PosixFileSystemShape,
  identity: Identity,
  journalLineageId: string,
  schemaContentSha256: string,
  detail: string,
  injectIoFault: IoFaultInjectorForTest
): Effect.Effect<ReadonlyArray<CanonicalAtomV2StateJournalEntry>, StoreError> =>
  injectIoFault("slot-reconciliation-readback", "before").pipe(
    Effect.zipRight(recover(fs, identity, journalLineageId, schemaContentSha256)),
    Effect.tap(() => injectIoFault("slot-reconciliation-readback", "after")),
    Effect.catchTag("PosixIoError", () => Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", detail)))
  )

interface StoreContext {
  readonly fs: PosixFileSystemShape
  readonly identity: Identity
  readonly journalLineageId: string
  readonly schemaContentSha256: string
  readonly interruption: PublicationInterruptionForTest
  readonly injectIoFault: IoFaultInjectorForTest
  readonly beforeSlotLink: BeforeSlotLinkForTest
  readonly minimumInjectedRevision: number
}

const publish = (
  context: StoreContext,
  input: CanonicalAtomV2StateJournalPublish
): Effect.Effect<CanonicalAtomV2StateJournalPublication, CanonicalAtomV2StateJournalStoreFailure> => {
  const { fs, identity, journalLineageId, schemaContentSha256 } = context
  const alreadyCommitted = (recovery: ReadonlyArray<CanonicalAtomV2StateJournalEntry>): CanonicalAtomV2StateJournalPublication =>
    Object.freeze({ _tag: "AlreadyCommitted" as const, recovery })
  return Effect.gen(function* () {
    if (
      !Number.isSafeInteger(input.stateRevision) ||
      input.stateRevision < 0 ||
      !(input.bytes instanceof Uint8Array) ||
      input.bytes.byteLength < 1 ||
      input.bytes.byteLength > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES
    ) {
      return yield* Effect.fail(error("PUBLISH", "BYTE_LENGTH_INVALID", "journal publication input is invalid"))
    }
    const expectedPredecessor = yield* fromEither(snapshotExpectedPredecessor(input.expectedPredecessor))
    const bytes = Uint8Array.from(input.bytes)
    const descriptor = yield* fromEither(recordDescriptor(bytes, "PUBLISH"))
    const injected = input.stateRevision >= context.minimumInjectedRevision
    const interruption = injected ? context.interruption : null
    const injectIoFault = injected ? context.injectIoFault : noFault
    const beforeSlotLink = injected ? context.beforeSlotLink : null
    const interrupt = (checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest) =>
      interruptPublicationForTest(interruption, checkpoint)
    const before = yield* recover(fs, identity, journalLineageId, schemaContentSha256)
    const revisionPredecessor = input.stateRevision === 0
      ? null
      : before[input.stateRevision - 1]?.descriptor ?? null
    if (!sameDescriptor(expectedPredecessor, revisionPredecessor)) {
      return yield* Effect.fail(error("PUBLISH", "PREDECESSOR_MISMATCH", "journal predecessor does not match the exact preceding record descriptor"))
    }
    const existing = before[input.stateRevision]
    if (existing !== undefined) {
      if (!sameBytes(existing.bytes, bytes)) {
        return yield* Effect.fail(error("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "journal revision is occupied by different bytes"))
      }
      yield* syncKnownCommit(fs, identity, injectIoFault)
      return alreadyCommitted(before)
    }
    if (input.stateRevision !== before.length) {
      return yield* Effect.fail(error("PUBLISH", "REVISION_CONFLICT", "journal revision is not next contiguous slot"))
    }
    if (!sameDescriptor(before.at(-1)?.descriptor ?? null, expectedPredecessor)) {
      return yield* Effect.fail(error("PUBLISH", "PREDECESSOR_MISMATCH", "journal predecessor does not match recovered tail"))
    }
    yield* publishObject(fs, identity.objects, descriptor.sha256, bytes, interruption, injectIoFault)
    const slot = canonicalAtomV2StateJournalSlotName(journalLineageId, schemaContentSha256, input.stateRevision)
    yield* assertDirectory(fs, identity.objects, "PUBLISH")
    yield* assertDirectory(fs, identity.slots, "PUBLISH")
    yield* interrupt("slot-link:before")
    if (beforeSlotLink !== null) {
      // The process-race seam is a caller-supplied Promise barrier; it is
      // consumed here exactly once and never re-exposed as Promise state.
      yield* Effect.tryPromise({
        try: beforeSlotLink,
        catch: (cause) =>
          cause instanceof CanonicalAtomV2StateJournalStoreError
            ? cause
            : error("PUBLISH", "IO_FAILED", "journal publication failed")
      })
    }
    const linked = yield* injectIoFault("slot-link", "before").pipe(
      Effect.zipRight(fs.linkNoReplace(
        join(identity.objects.path, descriptor.sha256),
        join(identity.slots.path, slot),
        FS_OPERATION
      )),
      Effect.zipRight(injectIoFault("slot-link", "after")),
      Effect.either
    )
    if (Either.isLeft(linked)) {
      const after = yield* recoverAfterSlotMayBeVisible(
        fs, identity, journalLineageId, schemaContentSha256,
        "slot-link outcome could not be reconciled",
        injectIoFault
      )
      const winner = after[input.stateRevision]
      if (winner !== undefined && sameBytes(winner.bytes, bytes)) {
        yield* syncKnownCommit(fs, identity, injectIoFault)
        return alreadyCommitted(after)
      }
      if (winner !== undefined) {
        return yield* Effect.fail(error("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "journal slot has a different winner"))
      }
      if (UNSUPPORTED_LINK_CODES.has(linked.left.code)) {
        return yield* Effect.fail(error("PUBLISH", "ATOMIC_PUBLICATION_UNSUPPORTED", linked.left.code))
      }
      return yield* Effect.fail(linked.left)
    }
    yield* interrupt("slot-link:after")
    yield* interrupt("slot-directory-fsync:before")
    yield* syncDirectory(fs, identity.slots, "PUBLISH", injectIoFault, "slot-directory-fsync").pipe(
      Effect.catchAll(() =>
        Effect.gen(function* () {
          const after = yield* recoverAfterSlotMayBeVisible(
            fs, identity, journalLineageId, schemaContentSha256,
            "slot durability could not be reconciled",
            injectIoFault
          )
          const winner = after[input.stateRevision]
          if (winner === undefined || !sameBytes(winner.bytes, bytes)) {
            return yield* Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "slot durability is unknown"))
          }
          yield* syncDirectory(fs, identity.slots, "PUBLISH", injectIoFault, "slot-directory-fsync").pipe(
            Effect.catchTag("PosixIoError", () =>
              Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "slot durability could not be re-established"))
            )
          )
        })
      )
    )
    yield* interrupt("slot-directory-fsync:after")
    yield* interrupt("journal-readback:before")
    const after = yield* injectIoFault("journal-readback", "before").pipe(
      Effect.zipRight(recover(fs, identity, journalLineageId, schemaContentSha256)),
      Effect.tap(() => injectIoFault("journal-readback", "after")),
      Effect.catchTag("PosixIoError", () =>
        Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "final journal readback failed after slot publication"))
      )
    )
    if (!sameBytes(after[input.stateRevision]?.bytes ?? new Uint8Array(), bytes)) {
      return yield* Effect.fail(error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal readback differs"))
    }
    yield* interrupt("journal-readback:after")
    return Object.freeze({ _tag: "Committed" as const, recovery: after })
  }).pipe(
    Effect.catchTag("PosixIoError", () => Effect.fail(error("PUBLISH", "IO_FAILED", "journal publication failed")))
  )
}

const makeLayer = <R>(
  acquireFileSystem: Effect.Effect<PosixFileSystemShape, never, R>,
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  interruption: PublicationInterruptionForTest,
  ioFaultPlan: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>,
  beforeSlotLink: BeforeSlotLinkForTest,
  minimumInjectedRevision: number
): Layer.Layer<CanonicalAtomV2StateJournalStore, CanonicalAtomV2StateJournalStoreError, R> =>
  Layer.effect(CanonicalAtomV2StateJournalStore, Effect.gen(function* () {
    if (
      !LINEAGE.test(journalLineageId) ||
      !DIGEST.test(schemaContentSha256) ||
      !Number.isSafeInteger(minimumInjectedRevision) ||
      minimumInjectedRevision < 0
    ) {
      return yield* Effect.fail(error("INITIALIZE", "ROOT_UNSAFE", "journal configuration is invalid"))
    }
    const fs = yield* acquireFileSystem
    const identity = yield* initialize(fs, rootPath).pipe(
      Effect.catchTag("PosixIoError", () => Effect.fail(error("INITIALIZE", "IO_FAILED", "journal initialization failed")))
    )
    const injectIoFault = yield* makeIoFaultInjectorForTest(ioFaultPlan)
    const context: StoreContext = Object.freeze({
      fs, identity, journalLineageId, schemaContentSha256, interruption, injectIoFault, beforeSlotLink, minimumInjectedRevision
    })
    return CanonicalAtomV2StateJournalStore.of({
      journalLineageId,
      schemaContentSha256,
      recover: recover(fs, identity, journalLineageId, schemaContentSha256).pipe(
        Effect.catchTag("PosixIoError", () => Effect.fail(error("RECOVER", "IO_FAILED", "journal recovery failed")))
      ),
      recoverWithin: (limits) => recover(fs, identity, journalLineageId, schemaContentSha256, limits).pipe(
        Effect.catchTag("PosixIoError", () => Effect.fail(error("RECOVER", "IO_FAILED", "bounded journal recovery failed")))
      ),
      publish: (input) => publish(context, input)
    })
  }))

/** POSIX/local filesystem adapter; controlled parents required because Node lacks openat2. */
export const makeCanonicalAtomV2StateJournalFileStoreLayer = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string
): Layer.Layer<CanonicalAtomV2StateJournalStore, CanonicalAtomV2StateJournalStoreError> =>
  makeLayer(Effect.succeed(NodePosixFileSystem), rootPath, journalLineageId, schemaContentSha256, null, [], null, 0)

/** Effect-native service form of the file store; the Layer requires the POSIX filesystem service. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerFromService = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string
): Layer.Layer<CanonicalAtomV2StateJournalStore, CanonicalAtomV2StateJournalStoreError, PosixFileSystem> =>
  makeLayer(PosixFileSystem, rootPath, journalLineageId, schemaContentSha256, null, [], null, 0)

/** Package-root-private deterministic interruption seam for internal tests. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest,
  minimumInjectedRevisionForTest = 0
): Layer.Layer<CanonicalAtomV2StateJournalStore, CanonicalAtomV2StateJournalStoreError> =>
  makeLayer(Effect.succeed(NodePosixFileSystem), rootPath, journalLineageId, schemaContentSha256, checkpoint, [], null, minimumInjectedRevisionForTest)

/** Package-root-private native-like I/O fault seam for internal tests. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerWithIoFaultsForTest = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  faults: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>,
  minimumInjectedRevisionForTest = 0
): Layer.Layer<CanonicalAtomV2StateJournalStore, CanonicalAtomV2StateJournalStoreError> =>
  makeLayer(Effect.succeed(NodePosixFileSystem), rootPath, journalLineageId, schemaContentSha256, null, faults, null, minimumInjectedRevisionForTest)

/** Package-root-private coordination hook for deterministic process-race tests. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerWithBeforeSlotLinkForTest = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  beforeSlotLink: () => Promise<void>,
  minimumInjectedRevisionForTest = 0
): Layer.Layer<CanonicalAtomV2StateJournalStore, CanonicalAtomV2StateJournalStoreError> =>
  makeLayer(
    Effect.succeed(NodePosixFileSystem),
    rootPath,
    journalLineageId,
    schemaContentSha256,
    null,
    [],
    beforeSlotLink,
    minimumInjectedRevisionForTest
  )
