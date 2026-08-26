import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit, Layer } from "effect"

import {
  CanonicalAtomV2ContentRuntime,
  makeCanonicalAtomV2ContentRuntimeFileLayer,
  makeCanonicalAtomV2ContentRuntimeLayer
} from "../src/canonical-atom-v2-content-runtime.js"
import {
  CanonicalAtomV2ContentStore,
  makeCanonicalAtomV2ContentStoreMemoryLayer,
  type CanonicalAtomV2ContentDescriptor
} from "../src/canonical-atom-v2-content.js"
import {
  canonicalAtomV2SchemaContentBytes,
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
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

const SCHEMA_VERSION = "hswm:test:content-runtime:v2"
const AUTHORIZATION = "authorization:content-writer"
const WRITE_SCOPE = "scope:canonical-write"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)

const rightOrThrow = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("fixture construction failed")
  return value.right
}

const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId: "lineage:main",
  atomUid,
  revisionId
})

const schemaFixture = (
  bootstrapTrustStatement = "The fixture has an explicitly bounded bootstrap trust statement."
): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement,
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

const rawSchemaBytes = (schema = schemaFixture()): Uint8Array =>
  utf8(JSON.stringify(schema))

const decodedSchema = (bytes = rawSchemaBytes()) =>
  rightOrThrow(decodeCanonicalAtomV2SchemaContent(bytes))

const grantFor = (
  digest: string,
  overrides: Partial<CanonicalAtomV2ContentAuthorizationGrant> = {}
): CanonicalAtomV2ContentAuthorizationGrant => ({
  authorizationRef: AUTHORIZATION,
  schemaVersion: SCHEMA_VERSION,
  schemaContentSha256: digest,
  scopes: [WRITE_SCOPE],
  ...overrides
})

const atomFixture = (
  atomUid: string,
  content: CanonicalAtomV2ContentDescriptor
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid),
  kind: "kind:atom",
  responsibilityOwner: "owner:atom",
  content,
  provenance: {
    mode: "BOOTSTRAP",
    evidenceSha256: "b".repeat(64),
    sourceRef: null
  },
  lifecycle: "ADMITTED",
  references: []
})

const commandFixture = (
  atom: CanonicalAtomV2,
  overrides: Partial<CommitCanonicalAtomsV2Command> = {}
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId: `transition:${atom.key.atomUid}`,
  expectedStateRevision: 0,
  schemaVersion: SCHEMA_VERSION,
  actorClaim: "actor:content-writer",
  authorizationRef: AUTHORIZATION,
  scope: WRITE_SCOPE,
  decidedAt: "2026-08-26T02:00:00.000Z",
  traceRef: null,
  readSet: [],
  writes: [atom],
  provenanceSha256: "c".repeat(64),
  ...overrides
})

const bindingFor = (atom: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({
  key: atom.key,
  payload: atom.content,
  envelope: rightOrThrow(describeCanonicalAtomV2Envelope(atom))
})

const contentRuntimeLayer = (
  schemaBytes: Uint8Array,
  grants: unknown
) =>
  makeCanonicalAtomV2ContentRuntimeLayer(schemaBytes, grants).pipe(
    Layer.provide(makeCanonicalAtomV2ContentStoreMemoryLayer())
  )

it("accepts duplicate-free noncanonical schema order but derives a stable canonical digest, and rejects duplicate keys", () => {
  const schema = schemaFixture()
  const noncanonical = rawSchemaBytes(schema)
  const decoded = decodedSchema(noncanonical)
  const canonical = rightOrThrow(canonicalAtomV2SchemaContentBytes(schema))

  expect(noncanonical).not.toEqual(canonical)
  expect(decoded.binding.content.sha256).toBe(
    decodedSchema(canonical).binding.content.sha256
  )
  expect(decoded.canonicalBytes).toEqual(canonical)

  const source = new TextDecoder().decode(noncanonical)
  const duplicate = utf8(
    source.replace(
      '"schemaVersion":"hswm:test:content-runtime:v2"',
      '"schemaVersion":"hswm:test:other:v2","schemaVersion":"hswm:test:content-runtime:v2"'
    )
  )
  const duplicateResult = decodeCanonicalAtomV2SchemaContent(duplicate)
  expect(Either.isLeft(duplicateResult)).toBe(true)
})

it.effect("stages payload bytes and commits an exactly bound, frozen content receipt", () => {
  const schema = decodedSchema()
  const layer = contentRuntimeLayer(
    rawSchemaBytes(),
    [grantFor(schema.binding.content.sha256)]
  )
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2ContentRuntime
    const payload = yield* runtime.stageContent("text/plain", utf8("payload-a"))
    const atom = atomFixture("atom:a", payload)
    const binding = bindingFor(atom)
    const committed = yield* runtime.submit(
      makeCanonicalAtomV2ContentBoundInput(
        runtime.schemaContent.content.sha256,
        commandFixture(atom),
        [binding]
      )
    )
    const history = yield* runtime.history
    const readback = yield* runtime.readContent(payload)

    expect(new TextDecoder().decode(readback)).toBe("payload-a")
    expect(committed.receipt.schema).toEqual(runtime.schemaContent)
    expect(committed.receipt.writeBindings).toEqual([binding])
    expect(committed.receipt.effect.writeSet).toEqual([atom.key])
    expect(history).toEqual([committed.receipt])
    expect(committed.receipt.contentDurability).toBe(
      "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE"
    )
    expect(Object.isFrozen(committed.receipt)).toBe(true)
    expect(Object.isFrozen(committed.receipt.schema)).toBe(true)
    expect(Object.isFrozen(committed.receipt.schema.content)).toBe(true)
    expect(Object.isFrozen(committed.receipt.writeBindings)).toBe(true)
    expect(Object.isFrozen(committed.receipt.writeBindings[0])).toBe(true)
    expect(Object.isFrozen(committed.receipt.writeBindings[0]?.payload)).toBe(true)
    expect(Object.isFrozen(committed.receipt.writeBindings[0]?.envelope)).toBe(true)
  })
  return program.pipe(Effect.provide(layer))
})

it.effect("rejects missing or forged content bindings and schema-digest drift without state or receipt mutation", () => {
  const schema = decodedSchema()
  const layer = contentRuntimeLayer(
    rawSchemaBytes(),
    [grantFor(schema.binding.content.sha256)]
  )
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2ContentRuntime
    const missing: CanonicalAtomV2ContentDescriptor = {
      mediaType: "text/plain",
      byteLength: 7,
      sha256: "d".repeat(64)
    }
    const missingAtom = atomFixture("atom:missing", missing)
    const missingBinding = bindingFor(missingAtom)
    const staged = yield* runtime.stageContent("text/plain", utf8("present"))
    const forgedAtom = atomFixture("atom:forged", staged)
    const forgedBinding = bindingFor(forgedAtom)
    const forgedEnvelope: CanonicalAtomV2WriteContentBinding = {
      ...forgedBinding,
      envelope: { ...forgedBinding.envelope, sha256: "e".repeat(64) }
    }

    const attempts = yield* Effect.forEach(
      [
        makeCanonicalAtomV2ContentBoundInput(
          runtime.schemaContent.content.sha256,
          commandFixture(missingAtom),
          [missingBinding]
        ),
        makeCanonicalAtomV2ContentBoundInput(
          runtime.schemaContent.content.sha256,
          commandFixture(forgedAtom, { transitionId: "transition:forged" }),
          [forgedEnvelope]
        ),
        makeCanonicalAtomV2ContentBoundInput(
          "0".repeat(64),
          commandFixture(forgedAtom, { transitionId: "transition:schema-drift" }),
          [forgedBinding]
        )
      ],
      (input) => Effect.exit(runtime.submit(input))
    )
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(attempts.every(Exit.isFailure)).toBe(true)
    expect(snapshot.canonical.revision).toBe(0)
    expect(snapshot.canonical.atoms).toEqual([])
    expect(snapshot.atomBindings).toEqual([])
    expect(history).toEqual([])
  })
  return program.pipe(Effect.provide(layer))
})

it.effect("rejects grant schema-digest drift at layer initialization before it creates a runtime", () => {
  const schema = decodedSchema()
  const program = Effect.gen(function* () {
    yield* CanonicalAtomV2ContentRuntime
  })
  const outcome = Effect.exit(
    program.pipe(
      Effect.provide(
        contentRuntimeLayer(rawSchemaBytes(), [grantFor("f".repeat(64))])
      )
    )
  )
  return Effect.gen(function* () {
    const exit = yield* outcome
    expect(Exit.isFailure(exit)).toBe(true)
    expect(schema.binding.content.sha256).not.toBe("f".repeat(64))
  })
})

it.effect("does not publish an atom envelope when pure-domain validation rejects the command", () => {
  const schema = decodedSchema()
  const layer = contentRuntimeLayer(
    rawSchemaBytes(),
    [grantFor(schema.binding.content.sha256)]
  )
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2ContentRuntime
    const payload = yield* runtime.stageContent("text/plain", utf8("payload-invalid"))
    const atom = atomFixture("atom:invalid", payload)
    const binding = bindingFor(atom)
    const failed = yield* Effect.exit(
      runtime.submit(
        makeCanonicalAtomV2ContentBoundInput(
          runtime.schemaContent.content.sha256,
          commandFixture(atom, { expectedStateRevision: 1 }),
          [binding]
        )
      )
    )
    const envelope = yield* runtime.readContent(binding.envelope).pipe(Effect.either)
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(failed)).toBe(true)
    expect(Either.isLeft(envelope)).toBe(true)
    expect(snapshot.canonical.revision).toBe(0)
    expect(history).toEqual([])
  })
  return program.pipe(Effect.provide(layer))
})

it.effect("serializes same-revision content commits: one receipt wins and the loser envelope is never claimed", () => {
  const schema = decodedSchema()
  const layer = contentRuntimeLayer(
    rawSchemaBytes(),
    [grantFor(schema.binding.content.sha256)]
  )
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2ContentRuntime
    const payload = yield* runtime.stageContent("text/plain", utf8("shared-payload"))
    const atomA = atomFixture("atom:a", payload)
    const atomB = atomFixture("atom:b", payload)
    const bindingA = bindingFor(atomA)
    const bindingB = bindingFor(atomB)
    const outcomes = yield* Effect.all(
      [
        runtime.submit(
          makeCanonicalAtomV2ContentBoundInput(
            runtime.schemaContent.content.sha256,
            commandFixture(atomA),
            [bindingA]
          )
        ).pipe(Effect.either),
        runtime.submit(
          makeCanonicalAtomV2ContentBoundInput(
            runtime.schemaContent.content.sha256,
            commandFixture(atomB),
            [bindingB]
          )
        ).pipe(Effect.either)
      ],
      { concurrency: 2 }
    )
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history
    const acceptedBindingKeys = new Set(
      history.flatMap((receipt) => receipt.writeBindings.map(({ key }) => key.atomUid))
    )

    expect(outcomes.filter(Either.isRight)).toHaveLength(1)
    expect(outcomes.filter(Either.isLeft)).toHaveLength(1)
    expect(snapshot.canonical.revision).toBe(1)
    expect(snapshot.canonical.atoms).toHaveLength(1)
    expect(history).toHaveLength(1)
    expect(acceptedBindingKeys).toEqual(
      new Set([snapshot.canonical.atoms[0]?.key.atomUid])
    )
    expect(history[0]?.contentDurability).toBe(
      "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE"
    )
  })
  return program.pipe(Effect.provide(layer))
})

it.effect("rejects same schemaVersion bound to different canonical schema bytes in one content store", () => {
  const firstBytes = rawSchemaBytes(schemaFixture("first schema body"))
  const secondBytes = rawSchemaBytes(schemaFixture("different schema body"))
  const first = decodedSchema(firstBytes)
  const second = decodedSchema(secondBytes)
  expect(first.binding.schemaVersion).toBe(second.binding.schemaVersion)
  expect(first.binding.content.sha256).not.toBe(second.binding.content.sha256)

  const storeLayer = makeCanonicalAtomV2ContentStoreMemoryLayer()
  const runtimeFor = (bytes: Uint8Array, digest: string) =>
    makeCanonicalAtomV2ContentRuntimeLayer(bytes, [grantFor(digest)])
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    const storeOnly = Layer.succeed(CanonicalAtomV2ContentStore, store)
    const firstRuntime = yield* Effect.gen(function* () {
      return yield* CanonicalAtomV2ContentRuntime
    }).pipe(
      Effect.provide(
        runtimeFor(firstBytes, first.binding.content.sha256).pipe(
          Layer.provide(storeOnly)
        )
      )
    )
    expect(firstRuntime.schemaContent.content.sha256).toBe(first.binding.content.sha256)

    const secondAttempt = yield* Effect.exit(
      Effect.gen(function* () {
        return yield* CanonicalAtomV2ContentRuntime
      }).pipe(
        Effect.provide(
          runtimeFor(secondBytes, second.binding.content.sha256).pipe(
            Layer.provide(storeOnly)
          )
        )
      )
    )
    expect(Exit.isFailure(secondAttempt)).toBe(true)
  })
  return program.pipe(Effect.provide(storeLayer))
})

it.effect("recovers durable content but honestly starts a fresh non-durable state journal", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-runtime-"))
  const schema = decodedSchema()
  const grants = [grantFor(schema.binding.content.sha256)]
  const layer = () =>
    makeCanonicalAtomV2ContentRuntimeFileLayer(
      root,
      rawSchemaBytes(),
      grants
    )

  const program = Effect.gen(function* () {
    const payload = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2ContentRuntime
      const stored = yield* runtime.stageContent("text/plain", utf8("durable-payload"))
      const atom = atomFixture("atom:durable", stored)
      yield* runtime.submit(
        makeCanonicalAtomV2ContentBoundInput(
          runtime.schemaContent.content.sha256,
          commandFixture(atom),
          [bindingFor(atom)]
        )
      )
      const snapshot = yield* runtime.snapshot
      expect(snapshot.canonical.revision).toBe(1)
      return stored
    }).pipe(Effect.provide(layer()))

    yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2ContentRuntime
      const restoredBytes = yield* runtime.readContent(payload)
      const snapshot = yield* runtime.snapshot
      const history = yield* runtime.history

      expect(new TextDecoder().decode(restoredBytes)).toBe("durable-payload")
      expect(snapshot.canonical.revision).toBe(0)
      expect(snapshot.canonical.atoms).toEqual([])
      expect(history).toEqual([])
      expect(runtime.contentDurability).toBe(
        "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE"
      )
    }).pipe(Effect.provide(layer()))
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(root, { force: true, recursive: true }))
    )
  )
})
