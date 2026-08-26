import { chmodSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, unlinkSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  canonicalAtomV2StateJournalSlotName,
  makeCanonicalAtomV2StateJournalFileStoreLayer
} from "../src/canonical-atom-v2-state-journal-file.js"
import { CanonicalAtomV2StateJournalStore } from "../src/canonical-atom-v2-state-journal-store.js"

const lineage = "lineage:journal:file"
const schema = "b".repeat(64)
const bytes = (value: string) => new TextEncoder().encode(value)
const cleanup = (path: string) => Effect.sync(() => rmSync(path, { force: true, recursive: true }))
const layer = (root: string) => makeCanonicalAtomV2StateJournalFileStoreLayer(root, lineage, schema)

it.effect("recovers exact create-only journal entries after a fresh Layer", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-"))
  const program = Effect.gen(function* () {
    const first = yield* Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      return yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("first") })
    }).pipe(Effect.provide(layer(root)))
    const recovered = yield* Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      return yield* store.recover
    }).pipe(Effect.provide(layer(root)))
    expect(recovered).toHaveLength(1)
    expect(recovered[0]?.descriptor).toEqual(first.recovery[0]?.descriptor)
    expect(new TextDecoder().decode(recovered[0]?.bytes)).toBe("first")
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("has exactly one concurrent winner and exact retry is idempotent", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-race-"))
  const program = Effect.gen(function* () {
    const results = yield* Effect.all(
      [bytes("left"), bytes("right")].map((entry) =>
        Effect.gen(function* () {
          const store = yield* CanonicalAtomV2StateJournalStore
          return yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: entry }).pipe(Effect.either)
        }).pipe(Effect.provide(layer(root)))
      ),
      { concurrency: 2 }
    )
    expect(results.filter(Either.isRight)).toHaveLength(1)
    expect(results.filter(Either.isLeft)).toHaveLength(1)
    const winner = results.find(Either.isRight)
    if (winner === undefined || Either.isLeft(winner)) return
    const retry = yield* Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      return yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: winner.right.recovery[0]?.bytes ?? bytes("") })
    }).pipe(Effect.provide(layer(root)))
    expect(retry._tag).toBe("AlreadyCommitted")
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("uses the complete predecessor descriptor for file publication CAS", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-cas-"))
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("first") })
    const predecessor = first.recovery[0]?.descriptor
    if (predecessor === undefined) return
    const wrongLength = Object.freeze({ ...predecessor, byteLength: predecessor.byteLength + 1 })
    const mismatch = yield* store.publish({
      stateRevision: 1,
      expectedPredecessor: wrongLength,
      bytes: bytes("second")
    }).pipe(Effect.either)
    expect(Either.isLeft(mismatch)).toBe(true)
    if (Either.isLeft(mismatch)) expect(mismatch.left.reason).toBe("PREDECESSOR_MISMATCH")
    const second = yield* store.publish({
      stateRevision: 1,
      expectedPredecessor: predecessor,
      bytes: bytes("second")
    })
    expect(second.recovery).toHaveLength(2)
  }).pipe(Effect.provide(layer(root)))
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("keeps complete tail deletion an explicit external-witness anti-rollback nonclaim", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-rollback-"))
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("first") })
    const predecessor = first.recovery[0]?.descriptor
    if (predecessor === undefined) return
    yield* store.publish({
      stateRevision: 1,
      expectedPredecessor: predecessor,
      bytes: bytes("second")
    })
    unlinkSync(join(
      root,
      "journal-slots",
      canonicalAtomV2StateJournalSlotName(lineage, schema, 1)
    ))
    const observedPrefix = yield* store.recover
    expect(observedPrefix).toHaveLength(1)
    expect(observedPrefix[0]?.descriptor).toEqual(predecessor)
  }).pipe(Effect.provide(layer(root)))
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("fails closed for symlinked slots and relative roots", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-unsafe-"))
  const program = Effect.gen(function* () {
    const relative = yield* Effect.gen(function* () { return yield* CanonicalAtomV2StateJournalStore }).pipe(Effect.provide(makeCanonicalAtomV2StateJournalFileStoreLayer("relative", lineage, schema)), Effect.either)
    expect(Either.isLeft(relative)).toBe(true)
    const store = yield* CanonicalAtomV2StateJournalStore
    const published = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("safe") })
    const slot = join(root, "journal-slots")
    const target = join(slot, published.recovery[0]?.descriptor.sha256 ?? "missing")
    void target
    chmodSync(slot, 0o700)
    symlinkSync(join(root, "journal-objects"), join(slot, "not-a-slot"))
    const recovery = yield* store.recover.pipe(Effect.either)
    expect(Either.isLeft(recovery)).toBe(true)
  }).pipe(Effect.provide(layer(root)))
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("rejects a symlink supplied as the journal root", () => {
  const base = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-root-link-"))
  const target = join(base, "target")
  const rootLink = join(base, "root-link")
  mkdirSync(target, { mode: 0o700 })
  symlinkSync(target, rootLink)
  const program = Effect.gen(function* () {
    const result = yield* Effect.gen(function* () {
      return yield* CanonicalAtomV2StateJournalStore
    }).pipe(Effect.provide(layer(rootLink)), Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left.operation).toBe("INITIALIZE")
      expect(result.left.reason).toBe("ROOT_UNSAFE")
    }
  })
  return program.pipe(Effect.ensuring(cleanup(base)))
})
