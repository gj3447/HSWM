import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  CanonicalAtomV2StateJournalStore,
  makeCanonicalAtomV2StateJournalStoreMemoryLayer
} from "../src/canonical-atom-v2-state-journal-store.js"

const lineage = "lineage:journal:test"
const schema = "a".repeat(64)
const bytes = (value: string) => new TextEncoder().encode(value)

it.effect("appends contiguous immutable entries and makes exact retry idempotent", () => {
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("one") })
    const retry = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("one") })
    const second = yield* store.publish({ stateRevision: 1, expectedPredecessor: first.recovery[0]?.descriptor ?? null, bytes: bytes("two") })
    expect(first._tag).toBe("Committed")
    expect(retry._tag).toBe("AlreadyCommitted")
    expect(second.recovery).toHaveLength(2)
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2StateJournalStoreMemoryLayer(lineage, schema)))
})

it.effect("rejects stale predecessor and divergent same-revision writers", () => {
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("one") })
    const stale = yield* store.publish({ stateRevision: 1, expectedPredecessor: null, bytes: bytes("two") }).pipe(Effect.either)
    const conflict = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("other") }).pipe(Effect.either)
    expect(Either.isLeft(stale)).toBe(true)
    expect(Either.isLeft(conflict)).toBe(true)
    expect((yield* store.recover)[0]?.descriptor).toEqual(first.recovery[0]?.descriptor)
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2StateJournalStoreMemoryLayer(lineage, schema)))
})

it.effect("compares the complete predecessor descriptor rather than only its digest", () => {
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("one") })
    const predecessor = first.recovery[0]?.descriptor
    if (predecessor === undefined) return
    const wrongLength = Object.freeze({ ...predecessor, byteLength: predecessor.byteLength + 1 })
    const result = yield* store.publish({
      stateRevision: 1,
      expectedPredecessor: wrongLength,
      bytes: bytes("two")
    }).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.reason).toBe("PREDECESSOR_MISMATCH")
    expect(yield* store.recover).toHaveLength(1)
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2StateJournalStoreMemoryLayer(lineage, schema)))
})

it.effect("fails closed when bounded recovery record, byte, or limit inputs are exceeded", () => {
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({
      stateRevision: 0,
      expectedPredecessor: null,
      bytes: bytes("one")
    })
    yield* store.publish({
      stateRevision: 1,
      expectedPredecessor: first.recovery[0]?.descriptor ?? null,
      bytes: bytes("two")
    })

    const exact = yield* store.recoverWithin({
      maximumRecords: 2,
      maximumRecoveredJournalBytes: 6
    })
    const failures = yield* Effect.forEach([
      { maximumRecords: 1, maximumRecoveredJournalBytes: 6 },
      { maximumRecords: 2, maximumRecoveredJournalBytes: 5 },
      { maximumRecords: 0, maximumRecoveredJournalBytes: 6 },
      {
        maximumRecords: 2,
        maximumRecoveredJournalBytes: Number.MAX_SAFE_INTEGER + 1
      }
    ], (limits) => store.recoverWithin(limits).pipe(Effect.either))

    expect(exact).toHaveLength(2)
    expect(failures.every((result) => Either.isLeft(result))).toBe(true)
    for (const result of failures) {
      if (Either.isLeft(result)) {
        expect(result.left.reason).toBe("RECOVERY_LIMIT_EXCEEDED")
      }
    }
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2StateJournalStoreMemoryLayer(lineage, schema)))
})
