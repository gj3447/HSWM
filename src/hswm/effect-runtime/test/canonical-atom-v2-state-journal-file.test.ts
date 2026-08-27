import {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  truncateSync,
  unlinkSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  canonicalAtomV2StateJournalSlotName,
  makeCanonicalAtomV2StateJournalFileStoreLayer,
  makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest,
  makeCanonicalAtomV2StateJournalFileStoreLayerWithIoFaultsForTest,
  type CanonicalAtomV2StateJournalFileIoFaultCodeForTest,
  type CanonicalAtomV2StateJournalFileIoFaultForTest,
  type CanonicalAtomV2StateJournalFileIoFaultPointForTest
} from "../src/canonical-atom-v2-state-journal-file.js"
import { CanonicalAtomV2StateJournalStore } from "../src/canonical-atom-v2-state-journal-store.js"

const lineage = "lineage:journal:file"
const schema = "b".repeat(64)
const bytes = (value: string) => new TextEncoder().encode(value)
const cleanup = (path: string) => Effect.sync(() => rmSync(path, { force: true, recursive: true }))
const layer = (root: string) => makeCanonicalAtomV2StateJournalFileStoreLayer(root, lineage, schema)
const fault = (
  point: CanonicalAtomV2StateJournalFileIoFaultPointForTest,
  code: CanonicalAtomV2StateJournalFileIoFaultCodeForTest = "EIO",
  phase: CanonicalAtomV2StateJournalFileIoFaultForTest["phase"] = "before",
  onInjected?: () => void
): CanonicalAtomV2StateJournalFileIoFaultForTest =>
  onInjected === undefined
    ? Object.freeze({ point, code, phase })
    : Object.freeze({ point, code, phase, onInjected })
const faultLayer = (
  root: string,
  faults: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>
) => makeCanonicalAtomV2StateJournalFileStoreLayerWithIoFaultsForTest(
  root,
  lineage,
  schema,
  faults
)
const interruptedLayer = (
  root: string,
  checkpoint: "slot-link:before" | "slot-link:after"
) => makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest(
  root,
  lineage,
  schema,
  checkpoint
)

const publishRevisionZero = (
  root: string,
  record: Uint8Array,
  faults: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>
) => Effect.gen(function* () {
  const store = yield* CanonicalAtomV2StateJournalStore
  return yield* store.publish({
    stateRevision: 0,
    expectedPredecessor: null,
    bytes: record
  })
}).pipe(Effect.provide(faultLayer(root, faults)))

const recoverFresh = (root: string) => Effect.gen(function* () {
  const store = yield* CanonicalAtomV2StateJournalStore
  return yield* store.recover
}).pipe(Effect.provide(layer(root)))

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

for (const point of ["object-link", "slot-link"] as const) {
  it.effect(`maps native-like EIO before ${point} to a typed old-prefix failure`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-link-eio-"))
    const program = Effect.gen(function* () {
      const result = yield* publishRevisionZero(
        root,
        bytes(`record:${point}`),
        [fault(point)]
      ).pipe(Effect.either)
      expect(Either.isLeft(result)).toBe(true)
      if (Either.isLeft(result)) {
        expect(result.left).toMatchObject({
          operation: "PUBLISH",
          reason: "IO_FAILED"
        })
      }
      expect(yield* recoverFresh(root)).toEqual([])
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })

  for (const code of [
    "ENOSYS",
    "ENOTSUP",
    "EOPNOTSUPP",
    "EXDEV"
  ] as const) {
    it.effect(`maps native-like ${code} before ${point} to unsupported atomic publication`, () => {
      const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-link-unsupported-"))
      const program = Effect.gen(function* () {
        const result = yield* publishRevisionZero(
          root,
          bytes(`record:${point}:${code}`),
          [fault(point, code)]
        ).pipe(Effect.either)
        expect(Either.isLeft(result)).toBe(true)
        if (Either.isLeft(result)) {
          expect(result.left).toMatchObject({
            operation: "PUBLISH",
            reason: "ATOMIC_PUBLICATION_UNSUPPORTED"
          })
        }
        expect(yield* recoverFresh(root)).toEqual([])
      })
      return program.pipe(Effect.ensuring(cleanup(root)))
    })
  }
}

for (const point of [
  "object-directory-fsync",
  "slot-directory-fsync"
] as const) {
  it.effect(`re-establishes publication after one native-like EIO at ${point}`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-fsync-once-"))
    const record = bytes(`record:${point}`)
    let injected = 0
    const program = Effect.gen(function* () {
      const published = yield* publishRevisionZero(root, record, [
        fault(point, "EIO", "before", () => {
          injected += 1
        })
      ])
      expect(published._tag).toBe("Committed")
      expect(injected).toBe(1)
      const recovered = yield* recoverFresh(root)
      expect(recovered).toHaveLength(1)
      expect(recovered[0]?.bytes).toEqual(record)
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })
}

it.effect("keeps the old prefix when object readback returns native-like EIO", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-object-read-eio-"))
  const program = Effect.gen(function* () {
    const result = yield* publishRevisionZero(
      root,
      bytes("object-readback"),
      [fault("object-readback")]
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left.reason).toBe("IO_FAILED")
    }
    expect(yield* recoverFresh(root)).toEqual([])
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("reconciles an exact slot when native-like EIO is reported after link", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-slot-link-after-"))
  const record = bytes("slot-link-after")
  const program = Effect.gen(function* () {
    const published = yield* publishRevisionZero(
      root,
      record,
      [fault("slot-link", "EIO", "after")]
    )
    expect(published._tag).toBe("AlreadyCommitted")
    const recovered = yield* recoverFresh(root)
    expect(recovered).toHaveLength(1)
    expect(recovered[0]?.bytes).toEqual(record)
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("reports old-prefix I/O failure after repeated object-directory fsync failure", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-object-fsync-repeat-"))
  const repeated = fault("object-directory-fsync")
  const program = Effect.gen(function* () {
    const result = yield* publishRevisionZero(
      root,
      bytes("object-fsync-repeat"),
      [repeated, repeated]
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left.reason).toBe("IO_FAILED")
    }
    expect(yield* recoverFresh(root)).toEqual([])
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

for (const testCase of [
  {
    name: "repeated slot-directory fsync failure",
    faults: [
      fault("slot-directory-fsync"),
      fault("slot-directory-fsync")
    ]
  },
  {
    name: "final journal readback EIO",
    faults: [fault("journal-readback")]
  }
] as const) {
  it.effect(`reports unknown outcome but fresh recovery sees the exact record after ${testCase.name}`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-visible-unknown-"))
    const record = bytes(testCase.name)
    const program = Effect.gen(function* () {
      const result = yield* publishRevisionZero(
        root,
        record,
        testCase.faults
      ).pipe(Effect.either)
      expect(Either.isLeft(result)).toBe(true)
      if (Either.isLeft(result)) {
        expect(result.left.reason).toBe("PUBLICATION_OUTCOME_UNKNOWN")
      }
      const recovered = yield* recoverFresh(root)
      expect(recovered).toHaveLength(1)
      expect(recovered[0]?.bytes).toEqual(record)
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })
}

for (const trigger of [
  fault("slot-link", "EIO", "after"),
  fault("slot-directory-fsync")
] as const) {
  it.effect(`normalizes raw reconciliation failure after ${trigger.point}:${trigger.phase} to unknown outcome`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-reconcile-eio-"))
    const record = bytes(`reconcile:${trigger.point}:${trigger.phase}`)
    const program = Effect.gen(function* () {
      const result = yield* publishRevisionZero(root, record, [
        trigger,
        fault("slot-reconciliation-readback")
      ]).pipe(Effect.either)
      expect(Either.isLeft(result)).toBe(true)
      if (Either.isLeft(result)) {
        expect(result.left.reason).toBe("PUBLICATION_OUTCOME_UNKNOWN")
      }
      const recovered = yield* recoverFresh(root)
      expect(recovered).toHaveLength(1)
      expect(recovered[0]?.bytes).toEqual(record)
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })
}

for (const point of [
  "known-commit-object-directory-fsync",
  "known-commit-slot-directory-fsync"
] as const) {
  it.effect(`returns AlreadyCommitted after one exact-retry resync EIO at ${point}`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-retry-once-"))
    const record = bytes(`retry:${point}`)
    let injected = 0
    const program = Effect.gen(function* () {
      yield* publishRevisionZero(root, record, [])
      const retry = yield* publishRevisionZero(root, record, [
        fault(point, "EIO", "before", () => {
          injected += 1
        })
      ])
      expect(retry._tag).toBe("AlreadyCommitted")
      expect(injected).toBe(1)
      const recovered = yield* recoverFresh(root)
      expect(recovered).toHaveLength(1)
      expect(recovered[0]?.bytes).toEqual(record)
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })

  it.effect(`returns unknown outcome after persistent exact-retry resync EIO at ${point}`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-retry-repeat-"))
    const record = bytes(`retry-repeat:${point}`)
    const repeated = fault(point)
    const program = Effect.gen(function* () {
      yield* publishRevisionZero(root, record, [])
      const retry = yield* publishRevisionZero(
        root,
        record,
        [repeated, repeated]
      ).pipe(Effect.either)
      expect(Either.isLeft(retry)).toBe(true)
      if (Either.isLeft(retry)) {
        expect(retry.left.reason).toBe("PUBLICATION_OUTCOME_UNKNOWN")
      }
      const recovered = yield* recoverFresh(root)
      expect(recovered).toHaveLength(1)
      expect(recovered[0]?.bytes).toEqual(record)
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })
}

it.effect("reports unknown exact-retry outcome when second-pass object resync fails", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-retry-cross-"))
  const record = bytes("retry-cross-pass")
  const program = Effect.gen(function* () {
    yield* publishRevisionZero(root, record, [])
    const retry = yield* publishRevisionZero(root, record, [
      fault("known-commit-slot-directory-fsync"),
      fault("known-commit-object-directory-fsync")
    ]).pipe(Effect.either)
    expect(Either.isLeft(retry)).toBe(true)
    if (Either.isLeft(retry)) {
      expect(retry.left.reason).toBe("PUBLICATION_OUTCOME_UNKNOWN")
    }
    const recovered = yield* recoverFresh(root)
    expect(recovered).toHaveLength(1)
    expect(recovered[0]?.bytes).toEqual(record)
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

for (const testCase of [
  {
    checkpoint: "slot-link:before",
    firstReason: "IO_FAILED",
    retryTag: "Committed"
  },
  {
    checkpoint: "slot-link:after",
    firstReason: "PUBLICATION_OUTCOME_UNKNOWN",
    retryTag: "AlreadyCommitted"
  }
] as const) {
  it.effect(`distinguishes exact retry after ${testCase.checkpoint} by recovered slot visibility`, () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-retry-visibility-"))
    const record = bytes(`retry:${testCase.checkpoint}`)
    const program = Effect.gen(function* () {
      const first = yield* Effect.gen(function* () {
        const store = yield* CanonicalAtomV2StateJournalStore
        return yield* store.publish({
          stateRevision: 0,
          expectedPredecessor: null,
          bytes: record
        })
      }).pipe(
        Effect.provide(interruptedLayer(root, testCase.checkpoint)),
        Effect.either
      )
      expect(Either.isLeft(first)).toBe(true)
      if (Either.isLeft(first)) {
        expect(first.left.reason).toBe(testCase.firstReason)
      }
      const visibleBeforeRetry = yield* recoverFresh(root)
      expect(visibleBeforeRetry).toHaveLength(
        testCase.checkpoint === "slot-link:before" ? 0 : 1
      )
      if (visibleBeforeRetry[0] !== undefined) {
        expect(visibleBeforeRetry[0].bytes).toEqual(record)
      }
      const retry = yield* publishRevisionZero(root, record, [])
      expect(retry._tag).toBe(testCase.retryTag)
      const recovered = yield* recoverFresh(root)
      expect(recovered).toHaveLength(1)
      expect(recovered[0]?.bytes).toEqual(record)
    })
    return program.pipe(Effect.ensuring(cleanup(root)))
  })
}

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
    let injected = 0
    const wrongRetry = yield* Effect.gen(function* () {
      const freshStore = yield* CanonicalAtomV2StateJournalStore
      return yield* freshStore.publish({
        stateRevision: 1,
        expectedPredecessor: wrongLength,
        bytes: bytes("second")
      })
    }).pipe(
      Effect.provide(faultLayer(root, [
        fault(
          "known-commit-object-directory-fsync",
          "EIO",
          "before",
          () => {
            injected += 1
          }
        )
      ])),
      Effect.either
    )
    expect(Either.isLeft(wrongRetry)).toBe(true)
    if (Either.isLeft(wrongRetry)) {
      expect(wrongRetry.left.reason).toBe("PREDECESSOR_MISMATCH")
    }
    expect(injected).toBe(0)

    const exactRetry = yield* Effect.gen(function* () {
      const freshStore = yield* CanonicalAtomV2StateJournalStore
      return yield* freshStore.publish({
        stateRevision: 1,
        expectedPredecessor: predecessor,
        bytes: bytes("second")
      })
    }).pipe(Effect.provide(faultLayer(root, [
      fault(
        "known-commit-object-directory-fsync",
        "EIO",
        "before",
        () => {
          injected += 1
        }
      )
    ])))
    expect(exactRetry._tag).toBe("AlreadyCommitted")
    expect(injected).toBe(1)
    expect(yield* recoverFresh(root)).toHaveLength(2)
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

it.effect("fails closed when a non-tail slot deletion creates a revision gap", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-gap-"))
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const first = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("zero") })
    const firstDescriptor = first.recovery[0]?.descriptor
    if (firstDescriptor === undefined) return
    const second = yield* store.publish({ stateRevision: 1, expectedPredecessor: firstDescriptor, bytes: bytes("one") })
    const secondDescriptor = second.recovery[1]?.descriptor
    if (secondDescriptor === undefined) return
    yield* store.publish({ stateRevision: 2, expectedPredecessor: secondDescriptor, bytes: bytes("two") })
    unlinkSync(join(
      root,
      "journal-slots",
      canonicalAtomV2StateJournalSlotName(lineage, schema, 1)
    ))
    const recovery = yield* store.recover.pipe(Effect.either)
    expect(Either.isLeft(recovery)).toBe(true)
    if (Either.isLeft(recovery)) expect(recovery.left.reason).toBe("SLOT_LAYOUT_INVALID")
  }).pipe(Effect.provide(layer(root)))
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("fails closed when a hard-linked journal record is truncated", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-truncated-"))
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const published = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("record-to-truncate") })
    const descriptor = published.recovery[0]?.descriptor
    if (descriptor === undefined) return
    const objectPath = join(root, "journal-objects", descriptor.sha256)
    chmodSync(objectPath, 0o600)
    truncateSync(objectPath, descriptor.byteLength - 1)
    chmodSync(objectPath, 0o400)
    const recovery = yield* store.recover.pipe(Effect.either)
    expect(Either.isLeft(recovery)).toBe(true)
    if (Either.isLeft(recovery)) expect(recovery.left.reason).toBe("CORRUPT_ENTRY")
  }).pipe(Effect.provide(layer(root)))
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("fails closed when the content-addressed object link is missing", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-journal-object-missing-"))
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    const published = yield* store.publish({ stateRevision: 0, expectedPredecessor: null, bytes: bytes("record") })
    const descriptor = published.recovery[0]?.descriptor
    if (descriptor === undefined) return
    unlinkSync(join(root, "journal-objects", descriptor.sha256))
    const recovery = yield* store.recover.pipe(Effect.either)
    expect(Either.isLeft(recovery)).toBe(true)
    if (Either.isLeft(recovery)) expect(recovery.left.reason).toBe("CORRUPT_ENTRY")
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
