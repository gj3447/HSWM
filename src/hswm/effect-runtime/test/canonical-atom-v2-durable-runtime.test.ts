import { chmodSync, mkdtempSync, rmSync, unlinkSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE,
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import type { CanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"
import { canonicalAtomV2StateJournalSlotName } from "../src/canonical-atom-v2-state-journal-file.js"
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
