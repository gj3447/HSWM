import { createHash } from "node:crypto"
import {
  chmodSync,
  linkSync,
  mkdtempSync,
  rmSync,
  unlinkSync,
  writeFileSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import {
  HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE,
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeLayer,
  makeCanonicalAtomV2DurableRuntimeFileLayer,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest,
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2ContentFileStoreLayer } from "../src/canonical-atom-v2-content-file.js"
import type { CanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"
import {
  CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST,
  canonicalAtomV2StateJournalSlotName,
  makeCanonicalAtomV2StateJournalFileStoreLayer,
  makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest,
  type CanonicalAtomV2StateJournalFilePublicationCheckpointForTest
} from "../src/canonical-atom-v2-state-journal-file.js"
import { CanonicalAtomV2StateJournalStore } from "../src/canonical-atom-v2-state-journal-store.js"
import { decodeCanonicalAtomV2StateJournalRecordBytes } from "../src/canonical-atom-v2-state-journal.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"

const SCHEMA_VERSION = "hswm:test:durable-runtime:v2"
const JOURNAL_LINEAGE = "journal:durable-runtime:main"
const AUTHORIZATION = "authorization:durable-writer"
const WRITE_SCOPE = "scope:canonical-write"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const sha256 = (value: Uint8Array): string =>
  createHash("sha256").update(value).digest("hex")

const rightOrThrow = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("fixture construction failed")
  return value.right
}

const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId: "lineage:atoms:main",
  atomUid,
  revisionId
})
const schemaFixture = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement:
    "The durable runtime fixture has an explicitly bounded bootstrap trust statement.",
  owners: [
    {
      address: "owner:atom",
      obligation: "Answer for atom correctness, lineage, and recovery."
    }
  ],
  kinds: [
    {
      kind: "kind:atom",
      form: "ENTITY",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:atom"],
      minimumArity: 0,
      referenceContracts: [
        {
          referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
          roles: [
            {
              role: HSWM_SUPERSEDES_REFERENCE_ROLE,
              targetKinds: ["kind:atom"],
              minimum: 0,
              maximum: 1
            }
          ]
        }
      ]
    }
  ]
})

const rawSchemaBytes = (): Uint8Array => utf8(JSON.stringify(schemaFixture()))

const schemaContent = () =>
  rightOrThrow(decodeCanonicalAtomV2SchemaContent(rawSchemaBytes()))

const grants = (): ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> => [
  {
    authorizationRef: AUTHORIZATION,
    schemaVersion: SCHEMA_VERSION,
    schemaContentSha256: schemaContent().binding.content.sha256,
    scopes: [WRITE_SCOPE]
  }
]

const atomFixture = (
  atomUid: string,
  content: CanonicalAtomV2ContentDescriptor,
  revisionId = 0
): CanonicalAtomV2 => {
  const predecessor = revisionId === 0 ? null : key(atomUid, revisionId - 1)
  return {
    _tag: "CanonicalAtomV2",
    contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: key(atomUid, revisionId),
    kind: "kind:atom",
    responsibilityOwner: "owner:atom",
    content,
    provenance:
      predecessor === null
        ? {
            mode: "BOOTSTRAP",
            evidenceSha256: "b".repeat(64),
            sourceRef: null
          }
        : {
            mode: "DERIVATION",
            evidenceSha256: "d".repeat(64),
            sourceRef: predecessor
          },
    lifecycle: "ADMITTED",
    references:
      predecessor === null
        ? []
        : [
            {
              referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
              role: HSWM_SUPERSEDES_REFERENCE_ROLE,
              target: predecessor
            }
          ]
  }
}

const commandFixture = (
  atom: CanonicalAtomV2,
  expectedStateRevision = 0
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId: `transition:${atom.key.atomUid}:${atom.key.revisionId}`,
  expectedStateRevision,
  schemaVersion: SCHEMA_VERSION,
  actorClaim: "actor:durable-writer",
  authorizationRef: AUTHORIZATION,
  scope: WRITE_SCOPE,
  decidedAt:
    expectedStateRevision === 0
      ? "2026-08-26T12:00:00.000Z"
      : "2026-08-26T12:01:00.000Z",
  traceRef: null,
  readSet:
    atom.key.revisionId === 0
      ? []
      : [key(atom.key.atomUid, atom.key.revisionId - 1)],
  writes: [atom],
  provenanceSha256: "c".repeat(64)
})

const bindingFor = (
  atom: CanonicalAtomV2
): CanonicalAtomV2WriteContentBinding => ({
  key: atom.key,
  payload: atom.content,
  envelope: rightOrThrow(describeCanonicalAtomV2Envelope(atom))
})

const inputFor = (atom: CanonicalAtomV2, expectedStateRevision = 0) =>
  makeCanonicalAtomV2ContentBoundInput(
    schemaContent().binding.content.sha256,
    commandFixture(atom, expectedStateRevision),
    [bindingFor(atom)]
  )

const fileLayer = (root: string) =>
  makeCanonicalAtomV2DurableRuntimeFileLayer(
    root,
    JOURNAL_LINEAGE,
    rawSchemaBytes(),
    grants()
  )

const interruptedFileLayer = (
  root: string,
  checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest
) => makeCanonicalAtomV2DurableRuntimeLayer(
  JOURNAL_LINEAGE,
  rawSchemaBytes(),
  grants()
).pipe(
  Layer.provide([
    makeCanonicalAtomV2ContentFileStoreLayer(root),
    makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest(
      root,
      JOURNAL_LINEAGE,
      schemaContent().binding.content.sha256,
      checkpoint
    )
  ])
)

const rawJournalLayer = (root: string) =>
  makeCanonicalAtomV2StateJournalFileStoreLayer(
    root,
    JOURNAL_LINEAGE,
    schemaContent().binding.content.sha256
  )

const commitMayBeVisible = (
  checkpoint: CanonicalAtomV2StateJournalFilePublicationCheckpointForTest
): boolean =>
  checkpoint === "slot-link:after" ||
  checkpoint === "slot-directory-fsync:before" ||
  checkpoint === "slot-directory-fsync:after" ||
  checkpoint === "journal-readback:before" ||
  checkpoint === "journal-readback:after"

const withTemporaryRoot = <A, E>(
  use: (root: string) => Effect.Effect<A, E>
): Effect.Effect<A, E> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-v2-durable-runtime-"))
  return use(root).pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(root, { recursive: true, force: true }))
    )
  )
}

const commitTwoAtomRevisions = (root: string, atomUid: string) =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const firstPayload = yield* runtime.stageContent(
      "text/plain",
      utf8(`${atomUid}:v0`)
    )
    const first = yield* runtime.submit(
      inputFor(atomFixture(atomUid, firstPayload))
    )
    const secondPayload = yield* runtime.stageContent(
      "text/plain",
      utf8(`${atomUid}:v1`)
    )
    const second = yield* runtime.submit(
      inputFor(atomFixture(atomUid, secondPayload, 1), 1)
    )
    return { first, second }
  }).pipe(Effect.provide(fileLayer(root)))

it.effect("provides a defensive raw journal recovery witness replayed from one durable prefix", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const payload = yield* runtime.stageContent("text/plain", utf8("witness"))
      yield* runtime.submit(inputFor(atomFixture("atom:witness", payload)))

      const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
      const raw = yield* Effect.gen(function* () {
        const store = yield* CanonicalAtomV2StateJournalStore
        return yield* store.recover
      }).pipe(Effect.provide(rawJournalLayer(root)))
      expect(witness.journal).toHaveLength(2)
      expect(witness.journal.map((entry) => entry.descriptor)).toEqual(
        raw.map((entry) => entry.descriptor)
      )
      expect(witness.journal.map((entry) => Array.from(entry.bytes))).toEqual(
        raw.map((entry) => Array.from(entry.bytes))
      )
      expect(witness.journal[0]?.bytes).not.toBe(raw[0]?.bytes)
      expect(witness.state.canonical.revision).toBe(1)
      expect(witness.history).toHaveLength(1)
      expect(witness.history[0]?.record).toEqual(witness.journal[1]?.descriptor)

      const retainedFirstByte = witness.journal[0]!.bytes[0]!
      witness.journal[0]!.bytes[0] = retainedFirstByte ^ 0xff
      const afterMutation = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
      expect(afterMutation.journal[0]?.bytes).toEqual(raw[0]?.bytes)
    }).pipe(Effect.provide(fileLayer(root)))
  )
)

it.effect("rejects an unregistered runtime at the internal recovery seam", () =>
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
    {} as CanonicalAtomV2DurableRuntime["Type"]
  ).pipe(
    Effect.flip,
    Effect.tap((error) =>
      Effect.sync(() =>
        expect(error).toMatchObject({
          reason: "CONFIGURATION_INVALID",
          detail: expect.stringContaining("not registered")
        })
      )
    )
  )
)

for (const checkpoint of CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST) {
  it.effect(`fresh replay exposes only an exact old or new prefix after ${checkpoint}`, () =>
    withTemporaryRoot((root) =>
      Effect.gen(function* () {
        yield* Effect.gen(function* () {
          const runtime = yield* CanonicalAtomV2DurableRuntime
          return yield* runtime.snapshot
        }).pipe(Effect.provide(fileLayer(root)))

        const attempt = yield* Effect.gen(function* () {
          const runtime = yield* CanonicalAtomV2DurableRuntime
          const payload = yield* runtime.stageContent(
            "text/plain",
            utf8(`fault:${checkpoint}`)
          )
          return yield* runtime.submit(
            inputFor(atomFixture("atom:fault", payload))
          )
        }).pipe(
          Effect.provide(interruptedFileLayer(root, checkpoint)),
          Effect.either
        )

        expect(Either.isLeft(attempt)).toBe(true)
        if (Either.isLeft(attempt)) {
          expect(attempt.left).toMatchObject({
            operation: "PUBLISH",
            reason: commitMayBeVisible(checkpoint)
              ? "PUBLICATION_OUTCOME_UNKNOWN"
              : "IO_FAILED"
          })
        }

        const recovered = yield* Effect.gen(function* () {
          const runtime = yield* CanonicalAtomV2DurableRuntime
          return {
            state: yield* runtime.snapshot,
            history: yield* runtime.history
          }
        }).pipe(Effect.provide(fileLayer(root)))
        const expectedRevision = commitMayBeVisible(checkpoint) ? 1 : 0
        expect(recovered.state.canonical.revision).toBe(expectedRevision)
        expect(recovered.history).toHaveLength(expectedRevision)
        if (expectedRevision === 1) {
          expect(recovered.state.canonical.atoms[0]?.key.atomUid).toBe(
            "atom:fault"
          )
          expect(recovered.history[0]?.commit.receipt.transitionId).toBe(
            "transition:atom:fault:0"
          )
        }
      })
    )
  )
}

for (const checkpoint of [
  "object-file-fsync:after",
  "slot-link:after"
] as const) {
  it.effect(`genesis interruption has an exact recoverable meaning after ${checkpoint}`, () =>
    withTemporaryRoot((root) =>
      Effect.gen(function* () {
        const attempt = yield* Effect.gen(function* () {
          return yield* CanonicalAtomV2DurableRuntime
        }).pipe(
          Effect.provide(interruptedFileLayer(root, checkpoint)),
          Effect.either
        )
        expect(Either.isLeft(attempt)).toBe(true)

        const observed = yield* Effect.gen(function* () {
          const store = yield* CanonicalAtomV2StateJournalStore
          return yield* store.recover
        }).pipe(Effect.provide(rawJournalLayer(root)))
        expect(observed).toHaveLength(checkpoint === "slot-link:after" ? 1 : 0)
        if (observed[0] !== undefined) {
          const decoded = decodeCanonicalAtomV2StateJournalRecordBytes(
            observed[0].bytes
          )
          expect(Either.isRight(decoded)).toBe(true)
          if (Either.isRight(decoded)) {
            expect(decoded.right._tag).toBe(
              "CanonicalAtomV2StateJournalGenesis"
            )
            expect(decoded.right.stateRevision).toBe(0)
          }
        }

        const initialized = yield* Effect.gen(function* () {
          const runtime = yield* CanonicalAtomV2DurableRuntime
          return {
            state: yield* runtime.snapshot,
            history: yield* runtime.history
          }
        }).pipe(Effect.provide(fileLayer(root)))
        expect(initialized.state.canonical.revision).toBe(0)
        expect(initialized.history).toEqual([])
      })
    )
  )
}

it.effect("publishes genesis, recovers two predecessor-bound revisions after fresh-layer restarts, and returns frozen receipts", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const first = yield* Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const initial = yield* runtime.snapshot
        const initialHistory = yield* runtime.history
        expect(initial.canonical.revision).toBe(0)
        expect(initialHistory).toEqual([])

        const payload = yield* runtime.stageContent(
          "text/plain",
          utf8("durable-v0")
        )
        return yield* runtime.submit(inputFor(atomFixture("atom:a", payload)))
      }).pipe(Effect.provide(fileLayer(root)))

      expect(first.state.canonical.revision).toBe(1)
      expect(first.state.stateDurability).toBe(
        HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE
      )
      expect(first.state.journalHead).toEqual(first.receipt.record)
      expect(first.receipt.commit.durability).toBe(
        "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"
      )
      expect(Object.isFrozen(first.state)).toBe(true)
      expect(Object.isFrozen(first.receipt)).toBe(true)
      expect(Object.isFrozen(first.receipt.commit.receipt.guard)).toBe(true)

      const second = yield* Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const recovered = yield* runtime.snapshot
        const history = yield* runtime.history
        expect(recovered.canonical).toEqual(first.state.canonical)
        expect(recovered.journalHead).toEqual(first.receipt.record)
        expect(history).toEqual([first.receipt])

        const payload = yield* runtime.stageContent(
          "text/plain",
          utf8("durable-v1")
        )
        const revision = atomFixture("atom:a", payload, 1)
        return yield* runtime.submit(inputFor(revision, 1))
      }).pipe(Effect.provide(fileLayer(root)))

      expect(second.state.canonical.revision).toBe(2)
      expect(second.state.canonical.atoms).toHaveLength(2)
      expect(second.receipt.commit.predecessor).toEqual(first.receipt.record)

      const final = yield* Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        return {
          state: yield* runtime.snapshot,
          history: yield* runtime.history
        }
      }).pipe(Effect.provide(fileLayer(root)))
      expect(final.state.canonical).toEqual(second.state.canonical)
      expect(final.state.atomBindings).toHaveLength(2)
      expect(final.history).toEqual([first.receipt, second.receipt])
    })
  )
)

it.effect("uses the fixed journal slot as a one-winner CAS across independent runtime layers", () =>
  withTemporaryRoot((root) => {
    const attempt = (atomUid: string, payloadText: string) =>
      Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const payload = yield* runtime.stageContent(
          "text/plain",
          utf8(payloadText)
        )
        return yield* runtime.submit(inputFor(atomFixture(atomUid, payload)))
      }).pipe(Effect.provide(fileLayer(root)), Effect.either)

    return Effect.gen(function* () {
      const results = yield* Effect.all(
        [attempt("atom:left", "left"), attempt("atom:right", "right")],
        { concurrency: 2 }
      )
      expect(results.filter(Either.isRight)).toHaveLength(1)
      expect(results.filter(Either.isLeft)).toHaveLength(1)

      const recovered = yield* Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        return {
          state: yield* runtime.snapshot,
          history: yield* runtime.history
        }
      }).pipe(Effect.provide(fileLayer(root)))
      expect(recovered.state.canonical.revision).toBe(1)
      expect(recovered.state.canonical.atoms).toHaveLength(1)
      expect(recovered.history).toHaveLength(1)
    })
  })
)

it.effect("fails closed on a changed finalized journal inode and on missing reachable payload content", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const committed = yield* Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const payload = yield* runtime.stageContent(
          "text/plain",
          utf8("tamper-target")
        )
        const result = yield* runtime.submit(
          inputFor(atomFixture("atom:tamper", payload))
        )
        return { result, payload }
      }).pipe(Effect.provide(fileLayer(root)))

      const schemaDigest = schemaContent().binding.content.sha256
      const slot = canonicalAtomV2StateJournalSlotName(
        JOURNAL_LINEAGE,
        schemaDigest,
        1
      )
      chmodSync(join(root, "journal-slots", slot), 0o600)
      const unsafeJournal = yield* Effect.gen(function* () {
        yield* CanonicalAtomV2DurableRuntime
      }).pipe(Effect.provide(fileLayer(root)), Effect.either)
      expect(Either.isLeft(unsafeJournal)).toBe(true)

      chmodSync(join(root, "journal-slots", slot), 0o400)
      unlinkSync(join(root, "objects", committed.payload.sha256))
      const missingPayload = yield* Effect.gen(function* () {
        yield* CanonicalAtomV2DurableRuntime
      }).pipe(Effect.provide(fileLayer(root)), Effect.either)
      expect(Either.isLeft(missingPayload)).toBe(true)
      expect(committed.result.state.canonical.revision).toBe(1)
    })
  )
)

it.effect("fresh durable recovery fails closed on a non-tail journal gap", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      yield* commitTwoAtomRevisions(root, "atom:gap")
      unlinkSync(join(
        root,
        "journal-slots",
        canonicalAtomV2StateJournalSlotName(
          JOURNAL_LINEAGE,
          schemaContent().binding.content.sha256,
          1
        )
      ))
      const reopened = yield* Effect.gen(function* () {
        return yield* CanonicalAtomV2DurableRuntime
      }).pipe(Effect.provide(fileLayer(root)), Effect.either)
      expect(Either.isLeft(reopened)).toBe(true)
      if (Either.isLeft(reopened)) {
        expect(reopened.left).toMatchObject({ reason: "SLOT_LAYOUT_INVALID" })
      }
    })
  )
)

it.effect("fresh durable recovery preserves the complete-tail anti-rollback nonclaim", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const committed = yield* commitTwoAtomRevisions(root, "atom:tail")
      unlinkSync(join(
        root,
        "journal-slots",
        canonicalAtomV2StateJournalSlotName(
          JOURNAL_LINEAGE,
          schemaContent().binding.content.sha256,
          2
        )
      ))
      const reopened = yield* Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        return {
          state: yield* runtime.snapshot,
          history: yield* runtime.history
        }
      }).pipe(Effect.provide(fileLayer(root)))
      expect(reopened.state.canonical.revision).toBe(1)
      expect(reopened.history).toEqual([committed.first.receipt])
      expect(reopened.state.canonical.atoms).toHaveLength(1)
      expect(reopened.state.canonical.atoms[0]?.key.revisionId).toBe(0)
    })
  )
)

it.effect("fresh durable recovery fails closed when a referenced journal object link is missing", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const committed = yield* commitTwoAtomRevisions(root, "atom:object")
      unlinkSync(join(
        root,
        "journal-objects",
        committed.second.receipt.record.sha256
      ))
      const reopened = yield* Effect.gen(function* () {
        return yield* CanonicalAtomV2DurableRuntime
      }).pipe(Effect.provide(fileLayer(root)), Effect.either)
      expect(Either.isLeft(reopened)).toBe(true)
      if (Either.isLeft(reopened)) {
        expect(reopened.left).toMatchObject({ reason: "CORRUPT_ENTRY" })
      }
    })
  )
)

it.effect("strict replay rejects re-addressed noncanonical journal bytes that pass raw hard-link recovery", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const committed = yield* commitTwoAtomRevisions(root, "atom:noncanonical")
      const oldObject = join(
        root,
        "journal-objects",
        committed.second.receipt.record.sha256
      )
      const invalidRecord = utf8("{}")
      const newObject = join(root, "journal-objects", sha256(invalidRecord))
      chmodSync(oldObject, 0o600)
      writeFileSync(oldObject, invalidRecord)
      chmodSync(oldObject, 0o400)
      linkSync(oldObject, newObject)
      unlinkSync(oldObject)

      const structurallyRecovered = yield* Effect.gen(function* () {
        const store = yield* CanonicalAtomV2StateJournalStore
        return yield* store.recover
      }).pipe(Effect.provide(rawJournalLayer(root)))
      expect(structurallyRecovered).toHaveLength(3)
      expect(structurallyRecovered[2]?.descriptor.sha256).toBe(
        sha256(invalidRecord)
      )

      const reopened = yield* Effect.gen(function* () {
        return yield* CanonicalAtomV2DurableRuntime
      }).pipe(Effect.provide(fileLayer(root)), Effect.either)
      expect(Either.isLeft(reopened)).toBe(true)
      if (Either.isLeft(reopened)) {
        expect(reopened.left).toMatchObject({ code: "RECORD_INVALID" })
      }
    })
  )
)

it.effect("keeps the durable prefix unchanged when content validation rejects a proposed transition", () => {
  const layer = makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest(
    JOURNAL_LINEAGE,
    rawSchemaBytes(),
    grants()
  )
  return Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const missing: CanonicalAtomV2ContentDescriptor = {
      mediaType: "text/plain",
      byteLength: 7,
      sha256: "f".repeat(64)
    }
    const attempt = yield* runtime
      .submit(inputFor(atomFixture("atom:missing", missing)))
      .pipe(Effect.either)
    const state = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Either.isLeft(attempt)).toBe(true)
    expect(state.canonical.revision).toBe(0)
    expect(state.atomBindings).toEqual([])
    expect(history).toEqual([])
  }).pipe(Effect.provide(layer))
})
