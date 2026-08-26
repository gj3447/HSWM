import { Schema } from "effect"

export const HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION =
  "hswm-canonical-schema-contract/v2" as const
export const HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION =
  "hswm-canonical-atom/v2" as const
export const HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION =
  "hswm-canonical-transition/v2" as const
export const HSWM_CANONICAL_RECEIPT_V2_CONTRACT_VERSION =
  "hswm-canonical-effect-receipt/v2" as const
export const HSWM_SUPERSEDES_REFERENCE_TYPE =
  "hswm:reference:supersedes" as const
export const HSWM_SUPERSEDES_REFERENCE_ROLE =
  "hswm:role:predecessor" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)

const Text = Schema.String.pipe(
  Schema.minLength(1),
  Schema.maxLength(8_192)
)

const Sha256 = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}$/)
)

const SafeNonNegativeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

const CanonicalInstant = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
)

const MediaType = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/),
  Schema.maxLength(255)
)

export interface CanonicalAtomV2Key {
  readonly schemaVersion: string
  readonly lineageId: string
  readonly atomUid: string
  readonly revisionId: number
}

export const CanonicalAtomV2KeySchema: Schema.Schema<CanonicalAtomV2Key> =
  Schema.Struct({
    schemaVersion: Identifier,
    lineageId: Identifier,
    atomUid: Identifier,
    revisionId: SafeNonNegativeInteger
  })

export interface CanonicalAtomV2Reference {
  readonly referenceType: string
  readonly role: string
  readonly target: CanonicalAtomV2Key
}

export const CanonicalAtomV2ReferenceSchema: Schema.Schema<CanonicalAtomV2Reference> =
  Schema.Struct({
    referenceType: Identifier,
    role: Identifier,
    target: CanonicalAtomV2KeySchema
  })

export interface CanonicalAtomV2Content {
  readonly mediaType: string
  readonly byteLength: number
  readonly sha256: string
}

export const CanonicalAtomV2ContentSchema: Schema.Schema<CanonicalAtomV2Content> =
  Schema.Struct({
    mediaType: MediaType,
    byteLength: SafeNonNegativeInteger,
    sha256: Sha256
  })

export interface CanonicalAtomV2Provenance {
  readonly mode: "BOOTSTRAP" | "OBSERVATION" | "DERIVATION" | "MIGRATION"
  readonly evidenceSha256: string
  readonly sourceRef: CanonicalAtomV2Key | null
}

export const CanonicalAtomV2ProvenanceSchema: Schema.Schema<CanonicalAtomV2Provenance> =
  Schema.Struct({
    mode: Schema.Literal(
      "BOOTSTRAP",
      "OBSERVATION",
      "DERIVATION",
      "MIGRATION"
    ),
    evidenceSha256: Sha256,
    sourceRef: Schema.NullOr(CanonicalAtomV2KeySchema)
  })

export interface CanonicalAtomV2 {
  readonly _tag: "CanonicalAtomV2"
  readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION
  readonly key: CanonicalAtomV2Key
  readonly kind: string
  readonly responsibilityOwner: string
  readonly content: CanonicalAtomV2Content
  readonly provenance: CanonicalAtomV2Provenance
  readonly lifecycle: "ADMITTED"
  readonly references: ReadonlyArray<CanonicalAtomV2Reference>
}

export const CanonicalAtomV2Schema: Schema.Schema<CanonicalAtomV2> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION
    ),
    key: CanonicalAtomV2KeySchema,
    kind: Identifier,
    responsibilityOwner: Identifier,
    content: CanonicalAtomV2ContentSchema,
    provenance: CanonicalAtomV2ProvenanceSchema,
    lifecycle: Schema.Literal("ADMITTED"),
    references: Schema.Array(CanonicalAtomV2ReferenceSchema).pipe(
      Schema.maxItems(256)
    )
  })

export interface CanonicalAtomV2OwnerContract {
  readonly address: string
  readonly obligation: string
}

export const CanonicalAtomV2OwnerContractSchema: Schema.Schema<CanonicalAtomV2OwnerContract> =
  Schema.Struct({
    address: Identifier,
    obligation: Text
  })

export interface CanonicalAtomV2ReferenceRoleContract {
  readonly role: string
  readonly targetKinds: ReadonlyArray<string>
  readonly minimum: number
  readonly maximum: number
}

export const CanonicalAtomV2ReferenceRoleContractSchema: Schema.Schema<CanonicalAtomV2ReferenceRoleContract> =
  Schema.Struct({
    role: Identifier,
    targetKinds: Schema.Array(Identifier).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    ),
    minimum: SafeNonNegativeInteger,
    maximum: SafeNonNegativeInteger
  })

export interface CanonicalAtomV2ReferenceContract {
  readonly referenceType: string
  readonly roles: ReadonlyArray<CanonicalAtomV2ReferenceRoleContract>
}

export const CanonicalAtomV2ReferenceContractSchema: Schema.Schema<CanonicalAtomV2ReferenceContract> =
  Schema.Struct({
    referenceType: Identifier,
    roles: Schema.Array(CanonicalAtomV2ReferenceRoleContractSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    )
  })

export interface CanonicalAtomV2KindContract {
  readonly kind: string
  readonly form: "ENTITY" | "RELATION"
  readonly revisionPolicy: "SINGLETON" | "LINEAR"
  readonly allowedOwners: ReadonlyArray<string>
  readonly minimumArity: number
  readonly referenceContracts: ReadonlyArray<CanonicalAtomV2ReferenceContract>
}

export const CanonicalAtomV2KindContractSchema: Schema.Schema<CanonicalAtomV2KindContract> =
  Schema.Struct({
    kind: Identifier,
    form: Schema.Literal("ENTITY", "RELATION"),
    revisionPolicy: Schema.Literal("SINGLETON", "LINEAR"),
    allowedOwners: Schema.Array(Identifier).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    ),
    minimumArity: SafeNonNegativeInteger,
    referenceContracts: Schema.Array(
      CanonicalAtomV2ReferenceContractSchema
    ).pipe(Schema.maxItems(128))
  })

export interface HSWMCanonicalSchemaV2 {
  readonly _tag: "HSWMCanonicalSchemaV2"
  readonly contractVersion: typeof HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION
  readonly schemaVersion: string
  readonly scientificStatus: "UNJUDGED"
  readonly bootstrapTrustStatement: string
  readonly owners: ReadonlyArray<CanonicalAtomV2OwnerContract>
  readonly kinds: ReadonlyArray<CanonicalAtomV2KindContract>
}

export const HSWMCanonicalSchemaV2Schema: Schema.Schema<HSWMCanonicalSchemaV2> =
  Schema.Struct({
    _tag: Schema.Literal("HSWMCanonicalSchemaV2"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION
    ),
    schemaVersion: Identifier,
    scientificStatus: Schema.Literal("UNJUDGED"),
    bootstrapTrustStatement: Text,
    owners: Schema.Array(CanonicalAtomV2OwnerContractSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    ),
    kinds: Schema.Array(CanonicalAtomV2KindContractSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    )
  })

export interface CanonicalAtomV2AuthorizationGrant {
  readonly authorizationRef: string
  readonly schemaVersion: string
  readonly scopes: ReadonlyArray<string>
}

export const CanonicalAtomV2AuthorizationGrantSchema: Schema.Schema<CanonicalAtomV2AuthorizationGrant> =
  Schema.Struct({
    authorizationRef: Identifier,
    schemaVersion: Identifier,
    scopes: Schema.Array(Identifier).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    )
  })

export const CanonicalAtomV2AuthorizationGrantsSchema = Schema.Array(
  CanonicalAtomV2AuthorizationGrantSchema
).pipe(Schema.maxItems(256))

export interface CommitCanonicalAtomsV2Command {
  readonly _tag: "CommitCanonicalAtomsV2"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION
  readonly transitionId: string
  readonly expectedStateRevision: number
  readonly schemaVersion: string
  readonly actorClaim: string
  readonly authorizationRef: string
  readonly scope: string
  readonly decidedAt: string
  readonly traceRef: CanonicalAtomV2Key | null
  readonly readSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly writes: ReadonlyArray<CanonicalAtomV2>
  readonly provenanceSha256: string
}

export const CommitCanonicalAtomsV2CommandSchema: Schema.Schema<CommitCanonicalAtomsV2Command> =
  Schema.Struct({
    _tag: Schema.Literal("CommitCanonicalAtomsV2"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION
    ),
    transitionId: Identifier,
    expectedStateRevision: SafeNonNegativeInteger,
    schemaVersion: Identifier,
    actorClaim: Identifier,
    authorizationRef: Identifier,
    scope: Identifier,
    decidedAt: CanonicalInstant,
    traceRef: Schema.NullOr(CanonicalAtomV2KeySchema),
    readSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(
      Schema.maxItems(512)
    ),
    writes: Schema.Array(CanonicalAtomV2Schema).pipe(
      Schema.minItems(1),
      Schema.maxItems(64)
    ),
    provenanceSha256: Sha256
  })

export const decodeHSWMCanonicalSchemaV2 = Schema.decodeUnknown(
  HSWMCanonicalSchemaV2Schema,
  { onExcessProperty: "error" }
)

export const decodeCommitCanonicalAtomsV2Command = Schema.decodeUnknown(
  CommitCanonicalAtomsV2CommandSchema,
  { onExcessProperty: "error" }
)

export const decodeCanonicalAtomV2AuthorizationGrants = Schema.decodeUnknown(
  CanonicalAtomV2AuthorizationGrantsSchema,
  { onExcessProperty: "error" }
)

export const canonicalAtomV2KeyId = (key: CanonicalAtomV2Key): string =>
  `${key.schemaVersion}|${key.lineageId}|${key.atomUid}|${key.revisionId}`

const snapshotKey = (key: CanonicalAtomV2Key): CanonicalAtomV2Key =>
  Object.freeze({ ...key })

const snapshotReference = (
  reference: CanonicalAtomV2Reference
): CanonicalAtomV2Reference =>
  Object.freeze({
    referenceType: reference.referenceType,
    role: reference.role,
    target: snapshotKey(reference.target)
  })

export const snapshotCanonicalAtomV2 = (
  atom: CanonicalAtomV2
): CanonicalAtomV2 =>
  Object.freeze({
    _tag: atom._tag,
    contractVersion: atom.contractVersion,
    key: snapshotKey(atom.key),
    kind: atom.kind,
    responsibilityOwner: atom.responsibilityOwner,
    content: Object.freeze({ ...atom.content }),
    provenance: Object.freeze({
      mode: atom.provenance.mode,
      evidenceSha256: atom.provenance.evidenceSha256,
      sourceRef:
        atom.provenance.sourceRef === null
          ? null
          : snapshotKey(atom.provenance.sourceRef)
    }),
    lifecycle: atom.lifecycle,
    references: Object.freeze(atom.references.map(snapshotReference))
  })

export const snapshotHSWMCanonicalSchemaV2 = (
  schema: HSWMCanonicalSchemaV2
): HSWMCanonicalSchemaV2 =>
  Object.freeze({
    _tag: schema._tag,
    contractVersion: schema.contractVersion,
    schemaVersion: schema.schemaVersion,
    scientificStatus: schema.scientificStatus,
    bootstrapTrustStatement: schema.bootstrapTrustStatement,
    owners: Object.freeze(
      schema.owners.map((owner) => Object.freeze({ ...owner }))
    ),
    kinds: Object.freeze(
      schema.kinds.map((kind) =>
        Object.freeze({
          kind: kind.kind,
          form: kind.form,
          revisionPolicy: kind.revisionPolicy,
          allowedOwners: Object.freeze([...kind.allowedOwners]),
          minimumArity: kind.minimumArity,
          referenceContracts: Object.freeze(
            kind.referenceContracts.map((reference) =>
              Object.freeze({
                referenceType: reference.referenceType,
                roles: Object.freeze(
                  reference.roles.map((role) =>
                    Object.freeze({
                      role: role.role,
                      targetKinds: Object.freeze([...role.targetKinds]),
                      minimum: role.minimum,
                      maximum: role.maximum
                    })
                  )
                )
              })
            )
          )
        })
      )
    )
  })

export const snapshotCommitCanonicalAtomsV2Command = (
  command: CommitCanonicalAtomsV2Command
): CommitCanonicalAtomsV2Command =>
  Object.freeze({
    _tag: command._tag,
    contractVersion: command.contractVersion,
    transitionId: command.transitionId,
    expectedStateRevision: command.expectedStateRevision,
    schemaVersion: command.schemaVersion,
    actorClaim: command.actorClaim,
    authorizationRef: command.authorizationRef,
    scope: command.scope,
    decidedAt: command.decidedAt,
    traceRef:
      command.traceRef === null ? null : snapshotKey(command.traceRef),
    readSet: Object.freeze(command.readSet.map(snapshotKey)),
    writes: Object.freeze(command.writes.map(snapshotCanonicalAtomV2)),
    provenanceSha256: command.provenanceSha256
  })
