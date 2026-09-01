import { createHash, randomUUID } from "node:crypto"
import { constants } from "node:fs"
import { link, lstat, mkdir, open, opendir, readdir, realpath, unlink } from "node:fs/promises"
import { dirname, isAbsolute, join, resolve } from "node:path"

import { Effect, Either, Layer } from "effect"

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

const OBJECTS = "journal-objects"
const SLOTS = "journal-slots"
const DIGEST = /^[0-9a-f]{64}$/

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

type PublicationInterruptionForTest =
  CanonicalAtomV2StateJournalFilePublicationCheckpointForTest | null
type IoFaultInjectorForTest = (
  point: CanonicalAtomV2StateJournalFileIoFaultPointForTest,
  phase: CanonicalAtomV2StateJournalFileIoFaultForTest["phase"]
) => void
type BeforeSlotLinkForTest = (() => Promise<void>) | null

interface DirectoryIdentity { readonly path: string; readonly device: number; readonly inode: number }
interface Identity { readonly root: DirectoryIdentity; readonly objects: DirectoryIdentity; readonly slots: DirectoryIdentity }

const error = makeCanonicalAtomV2StateJournalStoreError
const hash = (text: string): string => createHash("sha256").update(text, "utf8").digest("hex")
const sameBytes = (a: Uint8Array, b: Uint8Array): boolean => a.byteLength === b.byteLength && a.every((x, i) => x === b[i])
const hasCode = (input: unknown): input is { readonly code: string } =>
  typeof input === "object" && input !== null && "code" in input &&
  typeof input.code === "string"
const sameDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor | null,
  right: CanonicalAtomV2StateJournalRecordDescriptor | null
): boolean =>
  left === null || right === null
    ? left === right
    : left.mediaType === right.mediaType &&
      left.byteLength === right.byteLength &&
      left.sha256 === right.sha256

const COMMIT_MAY_BE_VISIBLE_CHECKPOINTS = new Set<CanonicalAtomV2StateJournalFilePublicationCheckpointForTest>([
  "slot-link:after",
  "slot-directory-fsync:before",
  "slot-directory-fsync:after",
  "journal-readback:before",
  "journal-readback:after"
])

const interruptPublicationForTest = (
  interruption: PublicationInterruptionForTest,
  checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest
): void => {
  if (interruption !== checkpoint) return
  throw error(
    "PUBLISH",
    COMMIT_MAY_BE_VISIBLE_CHECKPOINTS.has(checkpoint)
      ? "PUBLICATION_OUTCOME_UNKNOWN"
      : "IO_FAILED",
    `test-only publication interruption at ${checkpoint}`
  )
}

const makeIoFaultInjectorForTest = (
  plan: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>
): IoFaultInjectorForTest => {
  const retained = plan.map((fault) => Object.freeze({ ...fault }))
  let nextIndex = 0
  return (point, phase): void => {
    const next = retained[nextIndex]
    if (next === undefined || next.point !== point || next.phase !== phase) return
    nextIndex += 1
    next.onInjected?.()
    throw Object.assign(
      new Error(`test-only ${next.code} at ${point}:${phase}`),
      { code: next.code }
    )
  }
}

const snapshotExpectedPredecessor = (
  input: CanonicalAtomV2StateJournalRecordDescriptor | null
): CanonicalAtomV2StateJournalRecordDescriptor | null => {
  if (input === null) return null
  if (
    typeof input !== "object" ||
    input.mediaType !== HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE ||
    !Number.isSafeInteger(input.byteLength) ||
    input.byteLength < 1 ||
    input.byteLength > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES ||
    !DIGEST.test(input.sha256)
  ) {
    throw error("PUBLISH", "PREDECESSOR_MISMATCH", "predecessor must be an exact journal record descriptor or null")
  }
  return Object.freeze({ ...input })
}

const recordDescriptor = (
  bytes: Uint8Array,
  operation: "RECOVER" | "PUBLISH"
): CanonicalAtomV2StateJournalRecordDescriptor => {
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
    bytes
  )
  if (Either.isLeft(descriptor)) {
    throw error(
      operation,
      operation === "RECOVER" ? "CORRUPT_ENTRY" : "BYTE_LENGTH_INVALID",
      "journal bytes cannot form a record descriptor"
    )
  }
  return Object.freeze({
    mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
    byteLength: descriptor.right.byteLength,
    sha256: descriptor.right.sha256
  })
}

export const canonicalAtomV2StateJournalSlotName = (
  journalLineageId: string,
  schemaContentSha256: string,
  stateRevision: number
): string => hash(`hswm-canonical-atom-v2-state-journal-slot/v1\u0000${journalLineageId}\u0000${schemaContentSha256}\u0000${stateRevision}`)

const inspectDirectory = async (path: string, operation: "INITIALIZE" | "RECOVER" | "PUBLISH"): Promise<DirectoryIdentity> => {
  const stat = await lstat(path)
  if (stat.isSymbolicLink() || !stat.isDirectory() || (stat.mode & 0o777) !== 0o700) throw error(operation, "ROOT_UNSAFE", "journal directory must be a private plain 0700 directory")
  return Object.freeze({ path, device: stat.dev, inode: stat.ino })
}
const assertDirectory = async (directory: DirectoryIdentity, operation: "INITIALIZE" | "RECOVER" | "PUBLISH"): Promise<void> => {
  const stat = await lstat(directory.path)
  if (stat.isSymbolicLink() || !stat.isDirectory() || stat.dev !== directory.device || stat.ino !== directory.inode || (stat.mode & 0o777) !== 0o700) throw error(operation, "ROOT_UNSAFE", "journal directory identity or permissions changed")
}
const syncPlainDirectoryPath = async (path: string): Promise<void> => {
  const handle = await open(path, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW)
  try { await handle.sync() } finally { await handle.close() }
}
const initialize = async (rootPath: string): Promise<Identity> => {
  if (!isAbsolute(rootPath)) throw error("INITIALIZE", "ROOT_UNSAFE", "journal root must be absolute")
  const requested = resolve(rootPath)
  try { await mkdir(requested, { mode: 0o700 }) } catch (cause) {
    if (!hasCode(cause) || cause.code !== "EEXIST") throw cause
  }
  const requestedStat = await lstat(requested)
  if (requestedStat.isSymbolicLink() || !requestedStat.isDirectory()) {
    throw error("INITIALIZE", "ROOT_UNSAFE", "requested journal root must be a plain directory")
  }
  const root = await inspectDirectory(await realpath(requested), "INITIALIZE")
  await syncPlainDirectoryPath(dirname(root.path))
  for (const name of [OBJECTS, SLOTS]) {
    try { await mkdir(join(root.path, name), { mode: 0o700 }) } catch (cause) {
      if (!hasCode(cause) || cause.code !== "EEXIST") throw cause
    }
  }
  const objects = await inspectDirectory(join(root.path, OBJECTS), "INITIALIZE")
  const slots = await inspectDirectory(join(root.path, SLOTS), "INITIALIZE")
  await syncPlainDirectoryPath(root.path)
  return Object.freeze({ root, objects, slots })
}

const readRegular = async (
  directory: DirectoryIdentity,
  name: string,
  operation: "RECOVER" | "PUBLISH",
  injectIoFault: IoFaultInjectorForTest | null = null,
  faultPoint: CanonicalAtomV2StateJournalFileIoFaultPointForTest | null = null
): Promise<{ readonly bytes: Uint8Array; readonly device: number; readonly inode: number }> => {
  await assertDirectory(directory, operation)
  if (injectIoFault !== null && faultPoint !== null) {
    injectIoFault(faultPoint, "before")
  }
  const handle = await open(join(directory.path, name), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  try {
    const before = await handle.stat()
    if (!before.isFile() || (before.mode & 0o777) !== 0o400) throw error(operation, "FILE_TYPE_INVALID", "journal entry must be immutable regular 0400 file")
    if (before.size < 1 || before.size > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES) throw error(operation, "CORRUPT_ENTRY", "journal entry violates byte bound")
    const buffer = Buffer.alloc(before.size + 1)
    let total = 0
    while (total < buffer.byteLength) { const result = await handle.read(buffer, total, buffer.byteLength - total, total); if (result.bytesRead === 0) break; total += result.bytesRead }
    const after = await handle.stat()
    if (total !== before.size || after.dev !== before.dev || after.ino !== before.ino || after.size !== before.size) throw error(operation, "CORRUPT_ENTRY", "journal entry changed during bounded read")
    const result = Object.freeze({ bytes: Uint8Array.from(buffer.subarray(0, total)), device: before.dev, inode: before.ino })
    if (injectIoFault !== null && faultPoint !== null) {
      injectIoFault(faultPoint, "after")
    }
    return result
  } finally { await handle.close() }
}
const syncDirectory = async (
  directory: DirectoryIdentity,
  operation: "PUBLISH" | "RECOVER",
  injectIoFault: IoFaultInjectorForTest,
  faultPoint: CanonicalAtomV2StateJournalFileIoFaultPointForTest
): Promise<void> => {
  await assertDirectory(directory, operation)
  const handle = await open(directory.path, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW)
  try {
    injectIoFault(faultPoint, "before")
    await handle.sync()
    injectIoFault(faultPoint, "after")
  } finally { await handle.close() }
}
const syncKnownCommit = async (
  identity: Identity,
  injectIoFault: IoFaultInjectorForTest
): Promise<void> => {
  try {
    await syncDirectory(
      identity.objects,
      "PUBLISH",
      injectIoFault,
      "known-commit-object-directory-fsync"
    )
    await syncDirectory(
      identity.slots,
      "PUBLISH",
      injectIoFault,
      "known-commit-slot-directory-fsync"
    )
  } catch {
    try {
      await syncDirectory(
        identity.objects,
        "PUBLISH",
        injectIoFault,
        "known-commit-object-directory-fsync"
      )
      await syncDirectory(
        identity.slots,
        "PUBLISH",
        injectIoFault,
        "known-commit-slot-directory-fsync"
      )
    } catch {
      throw error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal object and slot durability could not be re-established")
    }
  }
}
const publishObject = async (
  directory: DirectoryIdentity,
  name: string,
  bytes: Uint8Array,
  interruption: PublicationInterruptionForTest,
  injectIoFault: IoFaultInjectorForTest
): Promise<void> => {
  await assertDirectory(directory, "PUBLISH")
  const finalPath = join(directory.path, name)
  const temporary = join(directory.path, `.journal-${randomUUID()}.tmp`)
  let made = false
  try {
    const handle = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600)
    made = true
    try {
      await handle.writeFile(bytes)
      await handle.chmod(0o400)
      interruptPublicationForTest(interruption, "object-file-fsync:before")
      injectIoFault("object-file-fsync", "before")
      await handle.sync()
      injectIoFault("object-file-fsync", "after")
      interruptPublicationForTest(interruption, "object-file-fsync:after")
    } finally { await handle.close() }
    interruptPublicationForTest(interruption, "object-link:before")
    try {
      injectIoFault("object-link", "before")
      await link(temporary, finalPath)
      injectIoFault("object-link", "after")
    } catch (cause) {
      try { const existing = await readRegular(directory, name, "PUBLISH"); if (!sameBytes(existing.bytes, bytes)) throw error("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "immutable journal destination has different bytes") } catch (readCause) {
        if (readCause instanceof Error && "_tag" in readCause) throw readCause
        const code = typeof cause === "object" && cause !== null && "code" in cause ? cause.code : ""
        if (["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(String(code))) throw error("PUBLISH", "ATOMIC_PUBLICATION_UNSUPPORTED", String(code))
        throw readCause
      }
    }
    interruptPublicationForTest(interruption, "object-link:after")
    interruptPublicationForTest(interruption, "object-directory-fsync:before")
    try {
      await syncDirectory(
        directory,
        "PUBLISH",
        injectIoFault,
        "object-directory-fsync"
      )
    } catch {
      try {
        const existing = await readRegular(directory, name, "PUBLISH")
        if (!sameBytes(existing.bytes, bytes)) {
          throw error(
            "PUBLISH",
            "PUBLICATION_OUTCOME_UNKNOWN",
            "journal entry differs after directory sync failure"
          )
        }
        await syncDirectory(
          directory,
          "PUBLISH",
          injectIoFault,
          "object-directory-fsync"
        )
      } catch (cause) {
        if (cause instanceof Error && "_tag" in cause) throw cause
        throw error(
          "PUBLISH",
          "IO_FAILED",
          "object directory durability could not be established before slot publication"
        )
      }
    }
    interruptPublicationForTest(interruption, "object-directory-fsync:after")
    interruptPublicationForTest(interruption, "object-readback:before")
    const exact = await readRegular(
      directory,
      name,
      "PUBLISH",
      injectIoFault,
      "object-readback"
    )
    if (!sameBytes(exact.bytes, bytes)) throw error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal readback differs")
    interruptPublicationForTest(interruption, "object-readback:after")
  } finally { if (made) { try { await unlink(temporary) } catch { /* orphan temporary has no journal meaning */ } } }
}

const recover = async (
  identity: Identity,
  lineage: string,
  schema: string,
  rawLimits: CanonicalAtomV2StateJournalRecoveryLimits | null = null
): Promise<ReadonlyArray<CanonicalAtomV2StateJournalEntry>> => {
  await assertDirectory(identity.root, "RECOVER"); await assertDirectory(identity.objects, "RECOVER"); await assertDirectory(identity.slots, "RECOVER")
  const limits = rawLimits === null
    ? null
    : snapshotCanonicalAtomV2StateJournalRecoveryLimits(rawLimits)
  if (limits !== null && Either.isLeft(limits)) throw limits.left
  let entries: ReadonlyArray<import("node:fs").Dirent>
  if (limits === null) {
    entries = await readdir(identity.slots.path, { withFileTypes: true })
  } else {
    const boundedEntries: Array<import("node:fs").Dirent> = []
    const directory = await opendir(identity.slots.path)
    try {
      for await (const entry of directory) {
        boundedEntries.push(entry)
        if (boundedEntries.length > limits.right.maximumRecords) {
          throw error("RECOVER", "RECOVERY_LIMIT_EXCEEDED", "journal recovery exceeds the record limit")
        }
      }
    } finally {
      try { await directory.close() } catch { /* async iteration may already close it */ }
    }
    entries = boundedEntries
  }
  if (entries.some((entry) => !entry.isFile() || !DIGEST.test(entry.name))) throw error("RECOVER", "SLOT_LAYOUT_INVALID", "journal slots contain malformed or nonregular entry")
  const finalNames = entries.map((entry) => entry.name)
  const expected = new Set(Array.from({ length: finalNames.length }, (_, revision) => canonicalAtomV2StateJournalSlotName(lineage, schema, revision)))
  if (finalNames.length !== expected.size || finalNames.some((name) => !expected.has(name))) throw error("RECOVER", "SLOT_LAYOUT_INVALID", "journal slots must be exactly the contiguous revision prefix")
  const recovered: Array<CanonicalAtomV2StateJournalEntry> = []
  let recoveredBytes = 0
  for (let revision = 0; revision < finalNames.length; revision += 1) {
    const slot = canonicalAtomV2StateJournalSlotName(lineage, schema, revision)
    if (limits !== null) {
      const stat = await lstat(join(identity.slots.path, slot))
      if (!stat.isFile()) {
        throw error("RECOVER", "SLOT_LAYOUT_INVALID", "journal slot changed to a nonregular entry during recovery")
      }
      if (
        !Number.isSafeInteger(recoveredBytes + stat.size) ||
        recoveredBytes + stat.size > limits.right.maximumRecoveredJournalBytes
      ) {
        throw error("RECOVER", "RECOVERY_LIMIT_EXCEEDED", "journal recovery exceeds the byte limit")
      }
    }
    const slotEntry = await readRegular(identity.slots, slot, "RECOVER")
    recoveredBytes += slotEntry.bytes.byteLength
    if (
      limits !== null &&
      (!Number.isSafeInteger(recoveredBytes) ||
        recoveredBytes > limits.right.maximumRecoveredJournalBytes)
    ) {
      throw error("RECOVER", "RECOVERY_LIMIT_EXCEEDED", "journal recovery exceeds the byte limit")
    }
    const descriptor = recordDescriptor(slotEntry.bytes, "RECOVER")
    let objectEntry
    try {
      objectEntry = await readRegular(identity.objects, descriptor.sha256, "RECOVER")
    } catch (cause) {
      if (hasCode(cause) && cause.code === "ENOENT") {
        throw error("RECOVER", "CORRUPT_ENTRY", "journal slot has no exact content-addressed object")
      }
      throw cause
    }
    if (!sameBytes(slotEntry.bytes, objectEntry.bytes) || slotEntry.device !== objectEntry.device || slotEntry.inode !== objectEntry.inode) throw error("RECOVER", "CORRUPT_ENTRY", "journal slot and object must be identical hard links")
    recovered.push(Object.freeze({ descriptor, bytes: Uint8Array.from(slotEntry.bytes) }))
  }
  await assertDirectory(identity.root, "RECOVER"); await assertDirectory(identity.objects, "RECOVER"); await assertDirectory(identity.slots, "RECOVER")
  return snapshotCanonicalAtomV2StateJournalRecovery(recovered)
}

const recoverAfterSlotMayBeVisible = async (
  identity: Identity,
  lineage: string,
  schema: string,
  detail: string,
  injectIoFault: IoFaultInjectorForTest
): Promise<ReadonlyArray<CanonicalAtomV2StateJournalEntry>> => {
  try {
    injectIoFault("slot-reconciliation-readback", "before")
    const recovered = await recover(identity, lineage, schema)
    injectIoFault("slot-reconciliation-readback", "after")
    return recovered
  } catch (cause) {
    if (cause instanceof Error && "_tag" in cause) throw cause
    throw error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", detail)
  }
}

const makeLayer = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  interruption: PublicationInterruptionForTest,
  ioFaultPlan: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>,
  beforeSlotLink: BeforeSlotLinkForTest,
  minimumInjectedRevision: number
) =>
  Layer.effect(CanonicalAtomV2StateJournalStore, Effect.gen(function* () {
    if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(journalLineageId) || !DIGEST.test(schemaContentSha256) || !Number.isSafeInteger(minimumInjectedRevision) || minimumInjectedRevision < 0) return yield* Effect.fail(error("INITIALIZE", "ROOT_UNSAFE", "journal configuration is invalid"))
    const identity = yield* Effect.tryPromise({ try: () => initialize(rootPath), catch: (cause) => cause instanceof CanonicalAtomV2StateJournalStoreError ? cause : error("INITIALIZE", "IO_FAILED", "journal initialization failed") })
    const injectIoFault = makeIoFaultInjectorForTest(ioFaultPlan)
    return CanonicalAtomV2StateJournalStore.of({
      journalLineageId, schemaContentSha256,
      recover: Effect.tryPromise({ try: () => recover(identity, journalLineageId, schemaContentSha256), catch: (cause) => cause instanceof Error && "_tag" in cause ? cause as CanonicalAtomV2StateJournalStoreFailure : error("RECOVER", "IO_FAILED", "journal recovery failed") }),
      recoverWithin: (limits) => Effect.tryPromise({ try: () => recover(identity, journalLineageId, schemaContentSha256, limits), catch: (cause) => cause instanceof Error && "_tag" in cause ? cause as CanonicalAtomV2StateJournalStoreFailure : error("RECOVER", "IO_FAILED", "bounded journal recovery failed") }),
      publish: (input: CanonicalAtomV2StateJournalPublish) => Effect.tryPromise({ try: async (): Promise<CanonicalAtomV2StateJournalPublication> => {
        if (!Number.isSafeInteger(input.stateRevision) || input.stateRevision < 0 || !(input.bytes instanceof Uint8Array) || input.bytes.byteLength < 1 || input.bytes.byteLength > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES) throw error("PUBLISH", "BYTE_LENGTH_INVALID", "journal publication input is invalid")
        const expectedPredecessor = snapshotExpectedPredecessor(input.expectedPredecessor)
        const bytes = Uint8Array.from(input.bytes)
        const descriptor = recordDescriptor(bytes, "PUBLISH")
        const injected = input.stateRevision >= minimumInjectedRevision
        const activeInterruption = injected ? interruption : null
        const activeInjectIoFault: IoFaultInjectorForTest = injected ? injectIoFault : () => undefined
        const activeBeforeSlotLink = injected ? beforeSlotLink : null
        const before = await recover(identity, journalLineageId, schemaContentSha256)
        const revisionPredecessor = input.stateRevision === 0
          ? null
          : before[input.stateRevision - 1]?.descriptor ?? null
        if (!sameDescriptor(expectedPredecessor, revisionPredecessor)) throw error("PUBLISH", "PREDECESSOR_MISMATCH", "journal predecessor does not match the exact preceding record descriptor")
        const existing = before[input.stateRevision]
        if (existing !== undefined) {
          if (sameBytes(existing.bytes, bytes)) {
            await syncKnownCommit(identity, activeInjectIoFault)
            return Object.freeze({ _tag: "AlreadyCommitted", recovery: before })
          }
          throw error("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "journal revision is occupied by different bytes")
        }
        if (input.stateRevision !== before.length) throw error("PUBLISH", "REVISION_CONFLICT", "journal revision is not next contiguous slot")
        if (!sameDescriptor(before.at(-1)?.descriptor ?? null, expectedPredecessor)) throw error("PUBLISH", "PREDECESSOR_MISMATCH", "journal predecessor does not match recovered tail")
        await publishObject(
          identity.objects,
          descriptor.sha256,
          bytes,
          activeInterruption,
          activeInjectIoFault
        )
        const slot = canonicalAtomV2StateJournalSlotName(journalLineageId, schemaContentSha256, input.stateRevision)
        await assertDirectory(identity.objects, "PUBLISH"); await assertDirectory(identity.slots, "PUBLISH")
        interruptPublicationForTest(activeInterruption, "slot-link:before")
        if (activeBeforeSlotLink !== null) await activeBeforeSlotLink()
        try {
          activeInjectIoFault("slot-link", "before")
          await link(
            join(identity.objects.path, descriptor.sha256),
            join(identity.slots.path, slot)
          )
          activeInjectIoFault("slot-link", "after")
        } catch (cause) {
          const after = await recoverAfterSlotMayBeVisible(
            identity,
            journalLineageId,
            schemaContentSha256,
            "slot-link outcome could not be reconciled",
            activeInjectIoFault
          )
          const winner = after[input.stateRevision]
          if (winner !== undefined && sameBytes(winner.bytes, bytes)) {
            await syncKnownCommit(identity, activeInjectIoFault)
            return Object.freeze({ _tag: "AlreadyCommitted", recovery: after })
          }
          if (winner !== undefined) throw error("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "journal slot has a different winner")
          const code = typeof cause === "object" && cause !== null && "code" in cause ? cause.code : ""
          if (["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(String(code))) throw error("PUBLISH", "ATOMIC_PUBLICATION_UNSUPPORTED", String(code))
          throw cause
        }
        interruptPublicationForTest(activeInterruption, "slot-link:after")
        interruptPublicationForTest(activeInterruption, "slot-directory-fsync:before")
        try {
          await syncDirectory(
            identity.slots,
            "PUBLISH",
            activeInjectIoFault,
            "slot-directory-fsync"
          )
        } catch {
          const after = await recoverAfterSlotMayBeVisible(
            identity,
            journalLineageId,
            schemaContentSha256,
            "slot durability could not be reconciled",
            activeInjectIoFault
          )
          const winner = after[input.stateRevision]
          if (winner === undefined || !sameBytes(winner.bytes, bytes)) {
            throw error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "slot durability is unknown")
          }
          try {
            await syncDirectory(
              identity.slots,
              "PUBLISH",
              activeInjectIoFault,
              "slot-directory-fsync"
            )
          } catch (cause) {
            if (cause instanceof Error && "_tag" in cause) throw cause
            throw error(
              "PUBLISH",
              "PUBLICATION_OUTCOME_UNKNOWN",
              "slot durability could not be re-established"
            )
          }
        }
        interruptPublicationForTest(activeInterruption, "slot-directory-fsync:after")
        interruptPublicationForTest(activeInterruption, "journal-readback:before")
        let after: ReadonlyArray<CanonicalAtomV2StateJournalEntry>
        try {
          activeInjectIoFault("journal-readback", "before")
          after = await recover(identity, journalLineageId, schemaContentSha256)
          activeInjectIoFault("journal-readback", "after")
        } catch (cause) {
          if (cause instanceof Error && "_tag" in cause) throw cause
          throw error(
            "PUBLISH",
            "PUBLICATION_OUTCOME_UNKNOWN",
            "final journal readback failed after slot publication"
          )
        }
        if (!sameBytes(after[input.stateRevision]?.bytes ?? new Uint8Array(), bytes)) throw error("PUBLISH", "PUBLICATION_OUTCOME_UNKNOWN", "journal readback differs")
        interruptPublicationForTest(activeInterruption, "journal-readback:after")
        return Object.freeze({ _tag: "Committed", recovery: after })
      }, catch: (cause) => cause instanceof Error && "_tag" in cause ? cause as CanonicalAtomV2StateJournalStoreFailure : error("PUBLISH", "IO_FAILED", "journal publication failed") })
    })
  }))

/** POSIX/local filesystem adapter; controlled parents required because Node lacks openat2. */
export const makeCanonicalAtomV2StateJournalFileStoreLayer = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string
) => makeLayer(rootPath, journalLineageId, schemaContentSha256, null, [], null, 0)

/** Package-root-private deterministic interruption seam for internal tests. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest,
  minimumInjectedRevisionForTest = 0
) => makeLayer(rootPath, journalLineageId, schemaContentSha256, checkpoint, [], null, minimumInjectedRevisionForTest)

/** Package-root-private native-like I/O fault seam for internal tests. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerWithIoFaultsForTest = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  faults: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>,
  minimumInjectedRevisionForTest = 0
) => makeLayer(rootPath, journalLineageId, schemaContentSha256, null, faults, null, minimumInjectedRevisionForTest)

/** Package-root-private coordination hook for deterministic process-race tests. */
export const makeCanonicalAtomV2StateJournalFileStoreLayerWithBeforeSlotLinkForTest = (
  rootPath: string,
  journalLineageId: string,
  schemaContentSha256: string,
  beforeSlotLink: () => Promise<void>,
  minimumInjectedRevisionForTest = 0
) => makeLayer(
  rootPath,
  journalLineageId,
  schemaContentSha256,
  null,
  [],
  beforeSlotLink,
  minimumInjectedRevisionForTest
)
