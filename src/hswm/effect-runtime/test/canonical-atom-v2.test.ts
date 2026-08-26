import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit } from "effect"

import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  canonicalAtomV2KeyId,
  decodeCommitCanonicalAtomsV2Command,
  decodeHSWMCanonicalSchemaV2,
  evolveCanonicalAtomsV2,
  initialCanonicalAtomV2State,
  validateCanonicalAtomV2State,
  validateHSWMCanonicalSchemaV2,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/index.js"

const SCHEMA_VERSION = "hswm:test:canonical:v2"

const key = (
  atomUid: string,
  revisionId = 0,
  lineageId = "lineage:main",
  schemaVersion = SCHEMA_VERSION
): CanonicalAtomV2Key => ({
  schemaVersion,
  lineageId,
  atomUid,
  revisionId
})

const schemaFixture = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement:
    "A bounded external verifier authorizes this reference-kernel fixture.",
  owners: [
    {
      address: "owner:entity",
      obligation: "Answer for entity correctness, lineage, and recovery."
    },
    {
      address: "owner:relation",
      obligation: "Answer for relation correctness, lineage, and recovery."
    },
    {
      address: "owner:trace",
      obligation: "Answer for trace correctness, lineage, and recovery."
    }
  ],
  kinds: [
    {
      kind: "kind:entity",
      form: "ENTITY",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:entity"],
      minimumArity: 0,
      referenceContracts: [
        {
          referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
          roles: [
            {
              role: HSWM_SUPERSEDES_REFERENCE_ROLE,
              targetKinds: ["kind:entity"],
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
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:relation"],
      minimumArity: 2,
      referenceContracts: [
        {
          referenceType: "reference:member",
          roles: [
            {
              role: "role:left",
              targetKinds: ["kind:entity"],
              minimum: 1,
              maximum: 1
            },
            {
              role: "role:right",
              targetKinds: ["kind:entity"],
              minimum: 1,
              maximum: 1
            }
          ]
        },
        {
          referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
          roles: [
            {
              role: HSWM_SUPERSEDES_REFERENCE_ROLE,
              targetKinds: ["kind:relation"],
              minimum: 0,
              maximum: 1
            }
          ]
        }
      ]
    },
    {
      kind: "kind:trace",
      form: "ENTITY",
      revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:trace"],
      minimumArity: 0,
      referenceContracts: []
    }
  ]
})

const atomFixture = (
  atomUid: string,
  options: {
    readonly revisionId?: number
    readonly lineageId?: string
    readonly schemaVersion?: string
    readonly kind?: string
    readonly owner?: string
    readonly references?: CanonicalAtomV2["references"]
    readonly provenance?: CanonicalAtomV2["provenance"]
    readonly sha?: string
  } = {}
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(
    atomUid,
    options.revisionId ?? 0,
    options.lineageId ?? "lineage:main",
    options.schemaVersion ?? SCHEMA_VERSION
  ),
  kind: options.kind ?? "kind:entity",
  responsibilityOwner: options.owner ?? "owner:entity",
  content: {
    mediaType: "application/json",
    byteLength: 2,
    sha256: options.sha ?? "a".repeat(64)
  },
  provenance:
    options.provenance ?? {
      mode: "BOOTSTRAP",
      evidenceSha256: "b".repeat(64),
      sourceRef: null
    },
  lifecycle: "ADMITTED",
  references: options.references ?? []
})

const commandFixture = (
  writes: ReadonlyArray<CanonicalAtomV2>,
  options: {
    readonly transitionId?: string
    readonly expectedStateRevision?: number
    readonly schemaVersion?: string
    readonly readSet?: ReadonlyArray<CanonicalAtomV2Key>
    readonly traceRef?: CanonicalAtomV2Key | null
  } = {}
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId: options.transitionId ?? "transition:one",
  expectedStateRevision: options.expectedStateRevision ?? 0,
  schemaVersion: options.schemaVersion ?? SCHEMA_VERSION,
  actorClaim: "actor:fixture",
  authorizationRef: "authorization:fixture",
  scope: "scope:canonical-write",
  decidedAt: "2026-08-26T00:00:00.000Z",
  traceRef: options.traceRef ?? null,
  readSet: options.readSet ?? [],
  writes,
  provenanceSha256: "c".repeat(64)
})

it.effect("strictly decodes the open-registry v2 schema and transition", () =>
  Effect.gen(function* () {
    const decodedSchema = yield* decodeHSWMCanonicalSchemaV2(schemaFixture())
    expect(decodedSchema.kinds.map(({ kind }) => kind)).toEqual([
      "kind:entity",
      "kind:relation",
      "kind:trace"
    ])

    const decodedCommand = yield* decodeCommitCanonicalAtomsV2Command(
      commandFixture([atomFixture("atom:a")])
    )
    expect(decodedCommand.writes[0]?.responsibilityOwner).toBe("owner:entity")

    const malformed: ReadonlyArray<unknown> = [
      { ...schemaFixture(), unexpected: true },
      { ...commandFixture([atomFixture("atom:a")]), unexpected: true },
      commandFixture([
        {
          ...atomFixture("atom:a"),
          responsibilityOwner: undefined
        } as unknown as CanonicalAtomV2
      ]),
      commandFixture([
        {
          ...atomFixture("atom:a"),
          owners: ["owner:entity", "owner:relation"]
        } as unknown as CanonicalAtomV2
      ]),
      commandFixture([
        {
          ...atomFixture("atom:a"),
          content: {
            ...atomFixture("atom:a").content,
            byteLength: Number.NaN
          }
        }
      ])
    ]
    const exits = yield* Effect.forEach(malformed, (input, index) => {
      const decoded =
        index === 0
          ? decodeHSWMCanonicalSchemaV2(input).pipe(Effect.asVoid)
          : decodeCommitCanonicalAtomsV2Command(input).pipe(Effect.asVoid)
      return Effect.exit(decoded)
    })
    expect(exits.every(Exit.isFailure)).toBe(true)
  })
)

it("validates an open schema registry without fixed H/W/A/F/Pi owners", () => {
  const valid = validateHSWMCanonicalSchemaV2(schemaFixture())
  expect(Either.isRight(valid)).toBe(true)

  const duplicateOwner = schemaFixture()
  const invalid = validateHSWMCanonicalSchemaV2({
    ...duplicateOwner,
    owners: [...duplicateOwner.owners, duplicateOwner.owners[0]!]
  })
  expect(Either.isLeft(invalid)).toBe(true)
  if (Either.isLeft(invalid)) expect(invalid.left.code).toBe("SCHEMA_INVALID")
})

it("scopes canonical identity to schema, lineage, atom, and revision", () => {
  expect(canonicalAtomV2KeyId(key("atom:a"))).not.toBe(
    canonicalAtomV2KeyId(key("atom:a", 0, "lineage:fork"))
  )
  expect(canonicalAtomV2KeyId(key("atom:a"))).not.toBe(
    canonicalAtomV2KeyId(
      key("atom:a", 0, "lineage:main", "hswm:test:other:v2")
    )
  )
  expect(canonicalAtomV2KeyId(key("atom:a"))).not.toBe(
    canonicalAtomV2KeyId(key("atom:a", 1))
  )
})

it("admits entity and persistent relation atoms atomically with one owner each", () => {
  const entityA = atomFixture("atom:a")
  const entityB = atomFixture("atom:b", { sha: "d".repeat(64) })
  const relation = atomFixture("relation:ab", {
    kind: "kind:relation",
    owner: "owner:relation",
    sha: "e".repeat(64),
    references: [
      {
        referenceType: "reference:member",
        role: "role:left",
        target: entityA.key
      },
      {
        referenceType: "reference:member",
        role: "role:right",
        target: entityB.key
      }
    ]
  })
  const evolved = evolveCanonicalAtomsV2(
    schemaFixture(),
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([entityA, entityB, relation])
  )

  expect(Either.isRight(evolved)).toBe(true)
  if (Either.isRight(evolved)) {
    expect(evolved.right.atoms).toHaveLength(3)
    expect(
      evolved.right.atoms.find(({ kind }) => kind === "kind:relation")
        ?.responsibilityOwner
    ).toBe("owner:relation")
  }
})

it("rejects unknown owners, ownerless relation atoms, and invalid endpoints", () => {
  const state = initialCanonicalAtomV2State(SCHEMA_VERSION)
  const entityA = atomFixture("atom:a")
  const relation = atomFixture("relation:bad", {
    kind: "kind:relation",
    owner: "owner:relation",
    references: [
      {
        referenceType: "reference:member",
        role: "role:left",
        target: entityA.key
      },
      {
        referenceType: "reference:member",
        role: "role:right",
        target: key("atom:missing")
      }
    ]
  })
  const cases = [
    commandFixture([atomFixture("atom:a", { owner: "owner:unknown" })]),
    commandFixture([entityA, relation])
  ]

  const results = cases.map((input) =>
    evolveCanonicalAtomsV2(schemaFixture(), state, input)
  )
  expect(results.every(Either.isLeft)).toBe(true)
  if (Either.isLeft(results[0]!)) expect(results[0].left.code).toBe("OWNER_INVALID")
  if (Either.isLeft(results[1]!)) expect(results[1].left.code).toBe("REFERENCE_INVALID")
  expect(state.atoms).toEqual([])
  expect(state.revision).toBe(0)
})

it("creates linear revisions without overwriting owner history", () => {
  const schema = schemaFixture()
  const firstAtom = atomFixture("atom:a")
  const first = evolveCanonicalAtomsV2(
    schema,
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([firstAtom])
  )
  expect(Either.isRight(first)).toBe(true)
  if (Either.isLeft(first)) return

  const revision = atomFixture("atom:a", {
    revisionId: 1,
    sha: "f".repeat(64),
    provenance: {
      mode: "DERIVATION",
      evidenceSha256: "1".repeat(64),
      sourceRef: firstAtom.key
    },
    references: [
      {
        referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
        role: HSWM_SUPERSEDES_REFERENCE_ROLE,
        target: firstAtom.key
      }
    ]
  })
  const second = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture([revision], {
      transitionId: "transition:two",
      expectedStateRevision: 1,
      readSet: [firstAtom.key]
    })
  )
  expect(Either.isRight(second)).toBe(true)
  if (Either.isRight(second)) {
    expect(second.right.atoms).toHaveLength(2)
    expect(second.right.atoms.map(({ responsibilityOwner }) => responsibilityOwner)).toEqual([
      "owner:entity",
      "owner:entity"
    ])
  }

  const ownerChange = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture(
      [
        {
          ...revision,
          responsibilityOwner: "owner:relation"
        }
      ],
      {
        transitionId: "transition:owner-change",
        expectedStateRevision: 1,
        readSet: [firstAtom.key]
      }
    )
  )
  expect(Either.isLeft(ownerChange)).toBe(true)
  if (Either.isLeft(ownerChange)) {
    expect(["OWNER_INVALID", "REVISION_INVALID"]).toContain(
      ownerChange.left.code
    )
  }
})

it("closes bootstrap provenance permanently after the genesis commit", () => {
  const schema = schemaFixture()
  const first = evolveCanonicalAtomsV2(
    schema,
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([atomFixture("atom:genesis")])
  )
  expect(Either.isRight(first)).toBe(true)
  if (Either.isLeft(first)) return
  expect(first.right.bootstrapClosed).toBe(true)

  const reopened = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture([atomFixture("atom:late-bootstrap")], {
      transitionId: "transition:late-bootstrap",
      expectedStateRevision: 1
    })
  )
  expect(Either.isLeft(reopened)).toBe(true)
  if (Either.isLeft(reopened)) {
    expect(reopened.left.code).toBe("PROVENANCE_INVALID")
  }

  const observed = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture(
      [
        atomFixture("atom:later-observation", {
          provenance: {
            mode: "OBSERVATION",
            evidenceSha256: "5".repeat(64),
            sourceRef: null
          }
        })
      ],
      {
        transitionId: "transition:observation",
        expectedStateRevision: 1
      }
    )
  )
  expect(Either.isRight(observed)).toBe(true)
})

it("rejects schema crossing, hidden reads, and migration claims", () => {
  const schema = schemaFixture()
  const atomA = atomFixture("atom:a")
  const first = evolveCanonicalAtomsV2(
    schema,
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([atomA])
  )
  expect(Either.isRight(first)).toBe(true)
  if (Either.isLeft(first)) return

  const derived = atomFixture("atom:b", {
    provenance: {
      mode: "DERIVATION",
      evidenceSha256: "2".repeat(64),
      sourceRef: atomA.key
    }
  })
  const hiddenRead = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture([derived], {
      transitionId: "transition:hidden-read",
      expectedStateRevision: 1
    })
  )
  expect(Either.isLeft(hiddenRead)).toBe(true)
  if (Either.isLeft(hiddenRead)) expect(hiddenRead.left.code).toBe("READ_SET_INVALID")

  const migration = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture(
      [
        atomFixture("atom:migration", {
          provenance: {
            mode: "MIGRATION",
            evidenceSha256: "3".repeat(64),
            sourceRef: atomA.key
          }
        })
      ],
      {
        transitionId: "transition:migration",
        expectedStateRevision: 1,
        readSet: [atomA.key]
      }
    )
  )
  expect(Either.isLeft(migration)).toBe(true)
  if (Either.isLeft(migration)) {
    expect(migration.left.code).toBe("MIGRATION_UNSUPPORTED")
  }

  const crossing = evolveCanonicalAtomsV2(
    schema,
    first.right,
    commandFixture(
      [
        atomFixture("atom:cross", {
          schemaVersion: "hswm:test:other:v2",
          provenance: {
            mode: "OBSERVATION",
            evidenceSha256: "6".repeat(64),
            sourceRef: null
          }
        })
      ],
      {
        transitionId: "transition:cross",
        expectedStateRevision: 1
      }
    )
  )
  expect(Either.isLeft(crossing)).toBe(true)
  if (Either.isLeft(crossing)) {
    expect(crossing.left.code).toBe("SCHEMA_VERSION_MISMATCH")
  }
})

it("enforces declared reference roles rather than arity alone", () => {
  const entityA = atomFixture("atom:a")
  const entityB = atomFixture("atom:b")
  const malformedRelation = atomFixture("relation:roles", {
    kind: "kind:relation",
    owner: "owner:relation",
    references: [
      {
        referenceType: "reference:member",
        role: "role:left",
        target: entityA.key
      },
      {
        referenceType: "reference:member",
        role: "role:left",
        target: entityB.key
      }
    ]
  })
  const result = evolveCanonicalAtomsV2(
    schemaFixture(),
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([entityA, entityB, malformedRelation])
  )
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left.code).toBe("REFERENCE_INVALID")
})

it("rejects forged prior state and cyclic same-batch provenance", () => {
  const schema = schemaFixture()
  const forgedState = {
    schemaVersion: SCHEMA_VERSION,
    revision: 1,
    bootstrapClosed: true,
    atoms: [atomFixture("atom:forged", { owner: "owner:unknown" })],
    acceptedTransitionIds: ["transition:forged"]
  }
  const validation = validateCanonicalAtomV2State(schema, forgedState)
  expect(Either.isLeft(validation)).toBe(true)
  if (Either.isLeft(validation)) expect(validation.left.code).toBe("STATE_INVALID")

  const continued = evolveCanonicalAtomsV2(
    schema,
    forgedState,
    commandFixture([atomFixture("atom:new")], {
      expectedStateRevision: 1
    })
  )
  expect(Either.isLeft(continued)).toBe(true)
  if (Either.isLeft(continued)) expect(continued.left.code).toBe("STATE_INVALID")

  const selfKey = key("atom:self-derived")
  const selfDerived = atomFixture("atom:self-derived", {
    provenance: {
      mode: "DERIVATION",
      evidenceSha256: "4".repeat(64),
      sourceRef: selfKey
    }
  })
  const cyclic = evolveCanonicalAtomsV2(
    schema,
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([selfDerived])
  )
  expect(Either.isLeft(cyclic)).toBe(true)
  if (Either.isLeft(cyclic)) expect(cyclic.left.code).toBe("PROVENANCE_INVALID")
})

it("keeps trace admission closed until a sealed-trajectory contract exists", () => {
  const trace = atomFixture("atom:trace", {
    kind: "kind:trace",
    owner: "owner:trace"
  })
  const result = evolveCanonicalAtomsV2(
    schemaFixture(),
    initialCanonicalAtomV2State(SCHEMA_VERSION),
    commandFixture([trace], { traceRef: trace.key })
  )
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left.code).toBe("TRACE_UNSUPPORTED")
})
