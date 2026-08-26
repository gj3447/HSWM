import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit } from "effect"

import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  CanonicalAtomV2Runtime,
  makeCanonicalAtomV2ReferenceLayer,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/index.js"

const SCHEMA_VERSION = "hswm:test:runtime:v2"
const WRITE_SCOPE = "scope:canonical-write"
const AUTHORIZATION = "authorization:writer"

const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId: "lineage:main",
  atomUid,
  revisionId
})

const schemaFixture = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement:
    "The reference runtime receives an explicit external test authorization.",
  owners: [
    {
      address: "owner:atom",
      obligation: "Answer for atom validation and recovery."
    },
    {
      address: "owner:relation",
      obligation: "Answer for relation validation and recovery."
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
    },
    {
      kind: "kind:relation",
      form: "RELATION",
      revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:relation"],
      minimumArity: 2,
      referenceContracts: [
        {
          referenceType: "reference:member",
          roles: [
            {
              role: "role:member",
              targetKinds: ["kind:atom"],
              minimum: 2,
              maximum: 8
            }
          ]
        }
      ]
    }
  ]
})

const atomFixture = (
  atomUid: string,
  options: {
    readonly kind?: string
    readonly owner?: string
    readonly references?: CanonicalAtomV2["references"]
  } = {}
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid),
  kind: options.kind ?? "kind:atom",
  responsibilityOwner: options.owner ?? "owner:atom",
  content: {
    mediaType: "application/octet-stream",
    byteLength: 4,
    sha256: "a".repeat(64)
  },
  provenance: {
    mode: "BOOTSTRAP",
    evidenceSha256: "b".repeat(64),
    sourceRef: null
  },
  lifecycle: "ADMITTED",
  references: options.references ?? []
})

const commandFixture = (
  transitionId: string,
  writes: ReadonlyArray<CanonicalAtomV2>,
  overrides: Partial<CommitCanonicalAtomsV2Command> = {}
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId,
  expectedStateRevision: 0,
  schemaVersion: SCHEMA_VERSION,
  actorClaim: "actor:writer",
  authorizationRef: AUTHORIZATION,
  scope: WRITE_SCOPE,
  decidedAt: "2026-08-26T01:00:00.000Z",
  traceRef: null,
  readSet: [],
  writes,
  provenanceSha256: "c".repeat(64),
  ...overrides
})

const runtimeLayer = () =>
  makeCanonicalAtomV2ReferenceLayer(schemaFixture(), [
    {
      authorizationRef: AUTHORIZATION,
      schemaVersion: SCHEMA_VERSION,
      scopes: [WRITE_SCOPE]
    }
  ])

it.effect("commits one frozen state and complete accepted receipt", () => {
  const input = commandFixture("transition:one", [atomFixture("atom:a")]) as
    CommitCanonicalAtomsV2Command & {
      actorClaim: string
      writes: Array<CanonicalAtomV2 & { responsibilityOwner: string }>
    }

  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2Runtime
    const committed = yield* runtime.submit(input)

    input.actorClaim = "actor:tampered"
    input.writes[0]!.responsibilityOwner = "owner:tampered"

    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history
    expect(snapshot.revision).toBe(1)
    expect(snapshot.atoms[0]?.responsibilityOwner).toBe("owner:atom")
    expect(history).toHaveLength(1)
    expect(history[0]).toEqual(committed.receipt)
    expect(history[0]?.guard).toEqual({
      schema: "PASSED",
      ownerTotality: "PASSED",
      references: "PASSED",
      revision: "PASSED",
      permission: "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"
    })
    expect(history[0]?.actorClaim).toBe("actor:writer")
    expect(history[0]?.authorizationRef).toBe(AUTHORIZATION)
    expect(history[0]?.writeSet).toEqual([key("atom:a")])
    expect(Object.isFrozen(snapshot)).toBe(true)
    expect(Object.isFrozen(snapshot.atoms)).toBe(true)
    expect(Object.isFrozen(snapshot.atoms[0]?.content)).toBe(true)
    expect(Object.isFrozen(history[0]?.guard)).toBe(true)
  })

  return program.pipe(Effect.provide(runtimeLayer()))
})

it.effect("keeps owner, actor claim, and permission independent", () => {
  const command = commandFixture("transition:owner-is-not-permit", [
    atomFixture("atom:a")
  ], {
    actorClaim: "owner:atom",
    authorizationRef: "owner:atom"
  })
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2Runtime
    const outcome = yield* Effect.exit(runtime.submit(command))
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(outcome)).toBe(true)
    expect(snapshot.revision).toBe(0)
    expect(snapshot.atoms).toEqual([])
    expect(history).toEqual([])
  })

  return program.pipe(Effect.provide(runtimeLayer()))
})

it.effect("fails an invalid multi-atom write without partial state or receipt", () => {
  const atomA = atomFixture("atom:a")
  const invalidRelation = atomFixture("relation:incomplete", {
    kind: "kind:relation",
    owner: "owner:relation",
    references: [
      {
        referenceType: "reference:member",
        role: "role:member",
        target: atomA.key
      }
    ]
  })
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2Runtime
    const outcome = yield* Effect.exit(
      runtime.submit(
        commandFixture("transition:invalid-batch", [atomA, invalidRelation])
      )
    )
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(outcome)).toBe(true)
    expect(snapshot.revision).toBe(0)
    expect(snapshot.atoms).toEqual([])
    expect(history).toEqual([])
  })

  return program.pipe(Effect.provide(runtimeLayer()))
})

it.effect("serializes conflicting concurrent transitions with one winner", () => {
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2Runtime
    const outcomes = yield* Effect.all(
      [
        runtime
          .submit(
            commandFixture("transition:race-a", [atomFixture("atom:a")])
          )
          .pipe(Effect.either),
        runtime
          .submit(
            commandFixture("transition:race-b", [atomFixture("atom:b")])
          )
          .pipe(Effect.either)
      ],
      { concurrency: 2 }
    )
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(outcomes.filter(Either.isRight)).toHaveLength(1)
    expect(outcomes.filter(Either.isLeft)).toHaveLength(1)
    expect(snapshot.revision).toBe(1)
    expect(snapshot.atoms).toHaveLength(1)
    expect(history).toHaveLength(1)
  })

  return program.pipe(Effect.provide(runtimeLayer()))
})

it.effect("rejects excess nested input before authorization or state change", () => {
  const atom = atomFixture("atom:a")
  const input = commandFixture("transition:unknown-field", [
    {
      ...atom,
      content: { ...atom.content, unexpected: true }
    } as CanonicalAtomV2
  ])
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2Runtime
    const outcome = yield* Effect.exit(runtime.submit(input))
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(outcome)).toBe(true)
    expect(snapshot.revision).toBe(0)
    expect(history).toEqual([])
  })

  return program.pipe(Effect.provide(runtimeLayer()))
})

it.effect("rejects a non-calendar instant without mutating state", () => {
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2Runtime
    const outcome = yield* Effect.exit(
      runtime.submit(
        commandFixture("transition:bad-time", [atomFixture("atom:a")], {
          decidedAt: "2026-02-30T01:00:00.000Z"
        })
      )
    )
    const snapshot = yield* runtime.snapshot
    const history = yield* runtime.history

    expect(Exit.isFailure(outcome)).toBe(true)
    expect(snapshot.revision).toBe(0)
    expect(history).toEqual([])
  })

  return program.pipe(Effect.provide(runtimeLayer()))
})

it.effect("strictly rejects invalid raw schemas when the Layer is built", () => {
  const schema = schemaFixture()
  const program = Effect.gen(function* () {
    yield* CanonicalAtomV2Runtime
  })
  return Effect.gen(function* () {
    const malformed: ReadonlyArray<unknown> = [
      {
        ...schema,
        owners: [...schema.owners, schema.owners[0]!]
      },
      { ...schema, unexpected: true },
      { ...schema, owners: null }
    ]
    const outcomes = yield* Effect.forEach(malformed, (rawSchema) =>
      Effect.exit(
        program.pipe(
          Effect.provide(
            makeCanonicalAtomV2ReferenceLayer(rawSchema, [])
          )
        )
      )
    )
    expect(outcomes.every(Exit.isFailure)).toBe(true)
  })
})

it.effect("strictly rejects malformed or ambiguous reference grants", () => {
  const program = Effect.gen(function* () {
    yield* CanonicalAtomV2Runtime
  })
  return Effect.gen(function* () {
    const baseGrant = {
      authorizationRef: AUTHORIZATION,
      schemaVersion: SCHEMA_VERSION,
      scopes: [WRITE_SCOPE]
    }
    const malformed: ReadonlyArray<unknown> = [
      [{ ...baseGrant, scopes: WRITE_SCOPE }],
      [{ ...baseGrant, unexpected: true }],
      [{ ...baseGrant, scopes: [WRITE_SCOPE, WRITE_SCOPE] }],
      [baseGrant, baseGrant],
      null
    ]
    const outcomes = yield* Effect.forEach(malformed, (rawGrants) =>
      Effect.exit(
        program.pipe(
          Effect.provide(
            makeCanonicalAtomV2ReferenceLayer(
              schemaFixture(),
              rawGrants
            )
          )
        )
      )
    )
    expect(outcomes.every(Exit.isFailure)).toBe(true)
  })
})
