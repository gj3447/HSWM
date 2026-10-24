/** Scoped read reuse. Native admission/recovery remain the authority; no persisted cache is trusted. */
import { createHash } from "node:crypto"
import { isAbsolute, join } from "node:path"
import { Effect, Ref } from "effect"
import { CanonicalAtomV2DurableRuntimeError, type CanonicalAtomV2DurableRuntime, type CanonicalAtomV2DurableState } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2StateJournalSlotName } from "./canonical-atom-v2-state-journal-file.js"
import { NodePosixFileSystem, type PosixFileSystemShape } from "./effect-posix-filesystem.js"
import { contextHash } from "./semantic-context-domain.js"
import { CanonicalAtomV2ContentStoreError } from "./canonical-atom-v2-content.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const invalid = (detail: string) => new CanonicalAtomV2DurableRuntimeError({ reason: "CONFIGURATION_INVALID", detail })
const sameHead = (a: CanonicalAtomV2DurableState, b: CanonicalAtomV2DurableState) =>
  a.journalLineageId === b.journalLineageId && contextHash(a.journalHead) === contextHash(b.journalHead)

/** No global payload replay within a stable head. Cold recovery and every native commit stay global.
 * Old, unrelated file corruption is checked at the final full audit, not at every snapshot access.
 * The head probe assumes the existing append-only owner publication contract; it is not a full audit.
 */
export const withLocalActivationSession = <A, E, R>(root: string, base: Runtime,
  use: (runtime: Runtime) => Effect.Effect<A, E, R>, fs: PosixFileSystemShape = NodePosixFileSystem) => Effect.gen(function* () {
  if (!isAbsolute(root)) return yield* Effect.fail(invalid("Local session requires the exact absolute native store root"))
  const paths = [root, join(root, "journal-objects"), join(root, "journal-slots")]
  const directories = yield* Effect.forEach(paths, path => fs.identity(path, "activation-read-session"))
  if (directories.some(d => d.kind !== "DIRECTORY" || d.mode !== 0o700)) return yield* Effect.fail(invalid("Session directories must be private plain directories"))
  const initial = yield* base.snapshot
  const state = yield* Ref.make(initial)
  const active = yield* Ref.make(true)
  const stats = yield* Ref.make({ fullSnapshots: 1, snapshotRequests: 0, headProbes: 0, headBytes: 0, contentReads: 0, contentBytes: 0, nativeSubmissions: 0 })
  const mutex = yield* Effect.makeSemaphore(1)
  const probe = (snapshot: CanonicalAtomV2DurableState) => Effect.gen(function* () {
    if (!(yield* Ref.get(active))) return yield* Effect.fail(invalid("Read session has closed"))
    const currentDirs = yield* Effect.forEach(paths, path => fs.identity(path, "activation-read-session"))
    if (currentDirs.some((d, i) => d.kind !== "DIRECTORY" || d.mode !== 0o700 || d.device !== directories[i]?.device || d.inode !== directories[i]?.inode))
      return yield* Effect.fail(invalid("Store directory changed during the read session"))
    const slot = (revision: number) => join(root, "journal-slots", canonicalAtomV2StateJournalSlotName(snapshot.journalLineageId, snapshot.schema.content.sha256, revision))
    const successor = yield* fs.identity(slot(snapshot.canonical.revision + 1), "activation-read-session").pipe(
      Effect.map(() => true), Effect.catchIf(error => error.code === "ENOENT", () => Effect.succeed(false)))
    if (successor) return yield* Effect.fail(invalid("Journal advanced outside this read session; reopen explicitly"))
    const options = { maximumBytes: 1048576, minimumBytes: 1, requiredMode: 0o400, operation: "activation-read-session" }
    const head = yield* fs.readRegularBounded(slot(snapshot.canonical.revision), options)
    const object = yield* fs.readRegularBounded(join(root, "journal-objects", snapshot.journalHead.sha256), options)
    const sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
    if (head.bytes.byteLength !== snapshot.journalHead.byteLength || sha(head.bytes) !== snapshot.journalHead.sha256 ||
      sha(object.bytes) !== snapshot.journalHead.sha256 || head.device !== object.device || head.inode !== object.inode)
      return yield* Effect.fail(invalid("Session head no longer matches the native immutable journal links"))
    yield* Ref.update(stats, s => ({ ...s, headProbes: s.headProbes + 1, headBytes: s.headBytes + head.bytes.byteLength + object.bytes.byteLength }))
  }).pipe(Effect.mapError(error => error instanceof CanonicalAtomV2DurableRuntimeError ? error : invalid(`Head probe failed: ${error._tag}`)))
  const runtime: Runtime = { ...base,
    stageContent: (mediaType, bytes) => Ref.get(active).pipe(Effect.flatMap(open => open ? base.stageContent(mediaType, bytes) : Effect.fail(new CanonicalAtomV2ContentStoreError({ operation: "PUT", reason: "IO_FAILED", detail: "Read session has closed" })))),
    snapshot: mutex.withPermits(1)(Effect.gen(function* () {
      const current = yield* Ref.get(state)
      yield* probe(current)
      yield* Ref.update(stats, s => ({ ...s, snapshotRequests: s.snapshotRequests + 1 }))
      return current
    })),
    readContent: descriptor => Ref.get(active).pipe(Effect.flatMap(open => open ? base.readContent(descriptor) : Effect.fail(new CanonicalAtomV2ContentStoreError({ operation: "GET", reason: "IO_FAILED", detail: "Read session has closed" }))), Effect.tap(bytes => Ref.update(stats,
      s => ({ ...s, contentReads: s.contentReads + 1, contentBytes: s.contentBytes + bytes.byteLength })))),
    submit: input => mutex.withPermits(1)(Effect.gen(function* () {
      yield* probe(yield* Ref.get(state))
      // All authorization, exact read-set, payload, predecessor and global replay checks are native.
      const committed = yield* base.submit(input)
      yield* Ref.set(state, committed.state)
      yield* Ref.update(stats, s => ({ ...s, nativeSubmissions: s.nativeSubmissions + 1 }))
      return committed
    }))
  }
  return yield* Effect.acquireUseRelease(Effect.void, () => Effect.gen(function* () {
    yield* probe(initial)
    const result = yield* use(runtime)
    const final = yield* base.snapshot
    yield* Ref.update(stats, s => ({ ...s, fullSnapshots: s.fullSnapshots + 1 }))
    const expected = yield* Ref.get(state)
    if (!sameHead(final, expected) || contextHash(final) !== contextHash(expected)) return yield* Effect.fail(invalid("Final global audit differs; no successful session result"))
    return { result, reads: yield* Ref.get(stats), locality: "SCOPED_HEAD_AND_CONTENT_READS_WITH_GLOBAL_OPEN_COMMIT_AND_CLOSE" as const }
  }), () => Ref.set(active, false))
})
