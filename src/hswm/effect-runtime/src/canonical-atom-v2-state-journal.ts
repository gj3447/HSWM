import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  CanonicalAtomV2ContentDescriptorSchema,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
  HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
  canonicalAtomV2EnvelopeBytes,
  canonicalAtomV2SchemaContentBytes,
  snapshotCanonicalAtomV2SchemaContentBinding,
  snapshotCanonicalAtomV2WriteContentBinding,
  validateCanonicalAtomV2WriteContentBindings,
  type CanonicalAtomV2WriteContentBinding
} from "./canonical-atom-v2-content-bound.js"
import {
  CanonicalAtomV2Error,
  evolveCanonicalAtomsV2,
  initialCanonicalAtomV2State,
  makeCanonicalAtomV2AcceptedReceipt,
  snapshotCanonicalAtomV2Receipt,
  snapshotCanonicalAtomV2State,
  type CanonicalAtomV2EffectReceipt,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_RECEIPT_V2_CONTRACT_VERSION,
  CanonicalAtomV2Schema,
  CanonicalAtomV2KeySchema,
  canonicalAtomV2KeyId,
  snapshotCanonicalAtomV2,
  snapshotHSWMCanonicalSchemaV2,
  type CanonicalAtomV2,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import {
  HSWM_CANONICAL_JSON_VERSION,
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"

export const HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION =
  "hswm-canonical-atom-v2-state-journal/v1" as const
export const HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-atom-v2-state-journal+json" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

export interface CanonicalAtomV2StateJournalRecordDescriptor {
  readonly mediaType: typeof HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE
  readonly byteLength: number
  readonly sha256: string
}

export const CanonicalAtomV2StateJournalRecordDescriptorSchema: Schema.Schema<CanonicalAtomV2StateJournalRecordDescriptor> =
  Schema.Struct({
    mediaType: Schema.Literal(HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE),
    byteLength: SafeInteger,
    sha256: Sha256
  })

const SchemaBindingSchema: Schema.Schema<CanonicalAtomV2SchemaContentBinding> =
  Schema.Struct({
    schemaVersion: Identifier,
    content: CanonicalAtomV2ContentDescriptorSchema
  })

const GuardSchema = Schema.Struct({
  schema: Schema.Literal("PASSED"),
  ownerTotality: Schema.Literal("PASSED"),
  references: Schema.Literal("PASSED"),
  revision: Schema.Literal("PASSED"),
  permission: Schema.Literal("REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT")
})

const EffectReceiptSchema: Schema.Schema<CanonicalAtomV2EffectReceipt> = Schema.Struct({
  _tag: Schema.Literal("CanonicalAtomV2EffectReceipt"),
  contractVersion: Schema.Literal(HSWM_CANONICAL_RECEIPT_V2_CONTRACT_VERSION),
  transitionId: Identifier,
  schemaVersion: Identifier,
  previousStateRevision: SafeInteger,
  nextStateRevision: SafeInteger,
  readSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.maxItems(512)),
  writeSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.maxItems(64)),
  traceRef: Schema.NullOr(CanonicalAtomV2KeySchema),
  guard: GuardSchema,
  actorClaim: Identifier,
  authorizationRef: Identifier,
  scope: Identifier,
  decidedAt: Schema.String.pipe(
    Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  ),
  decision: Schema.Literal("ACCEPTED"),
  provenanceSha256: Sha256
})

const WriteBindingSchema: Schema.Schema<CanonicalAtomV2WriteContentBinding> =
  Schema.Struct({
    key: CanonicalAtomV2KeySchema,
    payload: CanonicalAtomV2ContentDescriptorSchema,
    envelope: CanonicalAtomV2ContentDescriptorSchema
  })

export interface CanonicalAtomV2StateJournalGenesis {
  readonly _tag: "CanonicalAtomV2StateJournalGenesis"
  readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION
  readonly encoding: typeof HSWM_CANONICAL_JSON_VERSION
  readonly journalLineageId: string
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly stateRevision: 0
  readonly bootstrapClosed: false
  readonly predecessor: null
  readonly resultingStateSha256: string
}

export interface CanonicalAtomV2StateJournalCommit {
  readonly _tag: "CanonicalAtomV2StateJournalCommit"
  readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION
  readonly encoding: typeof HSWM_CANONICAL_JSON_VERSION
  readonly journalLineageId: string
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly stateRevision: number
  readonly predecessor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly receipt: CanonicalAtomV2EffectReceipt
  readonly writeBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
  readonly previousStateSha256: string
  readonly resultingStateSha256: string
  readonly durability: "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"
}

export type CanonicalAtomV2StateJournalRecord =
  | CanonicalAtomV2StateJournalGenesis
  | CanonicalAtomV2StateJournalCommit

export const CanonicalAtomV2StateJournalGenesisSchema: Schema.Schema<CanonicalAtomV2StateJournalGenesis> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2StateJournalGenesis"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION),
    encoding: Schema.Literal(HSWM_CANONICAL_JSON_VERSION),
    journalLineageId: Identifier,
    schema: SchemaBindingSchema,
    stateRevision: Schema.Literal(0),
    bootstrapClosed: Schema.Literal(false),
    predecessor: Schema.Null,
    resultingStateSha256: Sha256
  })

export const CanonicalAtomV2StateJournalCommitSchema: Schema.Schema<CanonicalAtomV2StateJournalCommit> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2StateJournalCommit"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION),
    encoding: Schema.Literal(HSWM_CANONICAL_JSON_VERSION),
    journalLineageId: Identifier,
    schema: SchemaBindingSchema,
    stateRevision: SafeInteger.pipe(Schema.greaterThanOrEqualTo(1)),
    predecessor: CanonicalAtomV2StateJournalRecordDescriptorSchema,
    receipt: EffectReceiptSchema,
    writeBindings: Schema.Array(WriteBindingSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(64)
    ),
    previousStateSha256: Sha256,
    resultingStateSha256: Sha256,
    durability: Schema.Literal(
      "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"
    )
  })

export const CanonicalAtomV2StateJournalRecordSchema: Schema.Schema<CanonicalAtomV2StateJournalRecord> =
  Schema.Union(
    CanonicalAtomV2StateJournalGenesisSchema,
    CanonicalAtomV2StateJournalCommitSchema
  )

export class CanonicalAtomV2StateJournalError extends Data.TaggedError(
  "CanonicalAtomV2StateJournalError"
)<{
  readonly code:
    | "RECORD_INVALID"
    | "RECORD_NOT_CANONICAL"
    | "SCHEMA_BINDING_INVALID"
    | "GENESIS_INVALID"
    | "PREDECESSOR_INVALID"
    | "RECEIPT_INVALID"
    | "WRITE_BINDING_INVALID"
    | "ENVELOPE_INVALID"
    | "STATE_DIGEST_INVALID"
  readonly detail: string
}> {}

const fail = (
  code: CanonicalAtomV2StateJournalError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2StateJournalError> =>
  Either.left(new CanonicalAtomV2StateJournalError({ code, detail }))

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((byte, index) => byte === right[index])

const compareText = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0

const bindingsAreStrictlyAscending = (
  bindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): boolean =>
  bindings.every(
    (binding, index) =>
      index === 0 ||
      compareText(
        canonicalAtomV2KeyId(bindings[index - 1]!.key),
        canonicalAtomV2KeyId(binding.key)
      ) < 0
  )

const snapshotDescriptor = (
  descriptor: CanonicalAtomV2StateJournalRecordDescriptor
): CanonicalAtomV2StateJournalRecordDescriptor => Object.freeze({ ...descriptor })

const sameDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor,
  right: CanonicalAtomV2StateJournalRecordDescriptor
): boolean =>
  left.mediaType === right.mediaType &&
  left.byteLength === right.byteLength &&
  left.sha256 === right.sha256

const snapshotGenesis = (
  record: CanonicalAtomV2StateJournalGenesis
): CanonicalAtomV2StateJournalGenesis =>
  Object.freeze({
    ...record,
    schema: snapshotCanonicalAtomV2SchemaContentBinding(record.schema)
  })

const snapshotCommit = (
  record: CanonicalAtomV2StateJournalCommit
): CanonicalAtomV2StateJournalCommit =>
  Object.freeze({
    ...record,
    schema: snapshotCanonicalAtomV2SchemaContentBinding(record.schema),
    predecessor: snapshotDescriptor(record.predecessor),
    receipt: snapshotCanonicalAtomV2Receipt(record.receipt),
    writeBindings: Object.freeze(
      record.writeBindings.map(snapshotCanonicalAtomV2WriteContentBinding)
    )
  })

export const snapshotCanonicalAtomV2StateJournalRecord = (
  record: CanonicalAtomV2StateJournalRecord
): CanonicalAtomV2StateJournalRecord =>
  record._tag === "CanonicalAtomV2StateJournalGenesis"
    ? snapshotGenesis(record)
    : snapshotCommit(record)

const decodeRecord = (
  input: unknown
): Either.Either<CanonicalAtomV2StateJournalRecord, CanonicalAtomV2StateJournalError> => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2StateJournalRecordSchema, {
    onExcessProperty: "error"
  })(input)
  return Either.isLeft(decoded)
    ? fail("RECORD_INVALID", "journal record violates the strict v1 structural contract")
    : Either.right(snapshotCanonicalAtomV2StateJournalRecord(decoded.right))
}

export const canonicalAtomV2StateCommitmentBytes = (
  state: CanonicalAtomV2State
): Either.Either<Uint8Array, CanonicalAtomV2StateJournalError> => {
  const encoded = canonicalJsonBytes(snapshotCanonicalAtomV2State(state))
  return Either.isLeft(encoded)
    ? fail("STATE_DIGEST_INVALID", "state cannot be represented by canonical JSON/v1")
    : Either.right(Uint8Array.from(encoded.right))
}

export const canonicalAtomV2StateSha256 = (
  state: CanonicalAtomV2State
): Either.Either<string, CanonicalAtomV2StateJournalError> => {
  const bytes = canonicalAtomV2StateCommitmentBytes(state)
  return Either.isLeft(bytes) ? Either.left(bytes.left) : Either.right(sha256(bytes.right))
}

export const canonicalAtomV2StateJournalRecordBytes = (
  input: CanonicalAtomV2StateJournalRecord
): Either.Either<Uint8Array, CanonicalAtomV2StateJournalError> => {
  const record = decodeRecord(input)
  if (Either.isLeft(record)) return Either.left(record.left)
  const encoded = canonicalJsonBytes(record.right)
  return Either.isLeft(encoded)
    ? fail("RECORD_INVALID", "journal record cannot be represented by canonical JSON/v1")
    : Either.right(Uint8Array.from(encoded.right))
}

export const describeCanonicalAtomV2StateJournalRecord = (
  record: CanonicalAtomV2StateJournalRecord
): Either.Either<CanonicalAtomV2StateJournalRecordDescriptor, CanonicalAtomV2StateJournalError> => {
  const bytes = canonicalAtomV2StateJournalRecordBytes(record)
  return Either.isLeft(bytes)
    ? Either.left(bytes.left)
    : Either.right(
        Object.freeze({
          mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
          byteLength: bytes.right.byteLength,
          sha256: sha256(bytes.right)
        })
      )
}

export const decodeCanonicalAtomV2StateJournalRecordBytes = (
  bytes: Uint8Array
): Either.Either<CanonicalAtomV2StateJournalRecord, CanonicalAtomV2StateJournalError> => {
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed)) {
    return fail("RECORD_INVALID", "journal record bytes are not bounded duplicate-free JSON")
  }
  const record = decodeRecord(parsed.right)
  if (Either.isLeft(record)) return Either.left(record.left)
  const canonical = canonicalAtomV2StateJournalRecordBytes(record.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return sameBytes(bytes, canonical.right)
    ? Either.right(record.right)
    : fail("RECORD_NOT_CANONICAL", "journal record bytes must be exact canonical JSON/v1")
}

const schemaBindingFor = (
  schema: HSWMCanonicalSchemaV2
): Either.Either<CanonicalAtomV2SchemaContentBinding, CanonicalAtomV2StateJournalError> => {
  const canonical = canonicalAtomV2SchemaContentBytes(schema)
  if (Either.isLeft(canonical)) {
    return fail("SCHEMA_BINDING_INVALID", "active schema cannot produce canonical schema bytes")
  }
  return Either.right(
    Object.freeze({
      schemaVersion: schema.schemaVersion,
      content: Object.freeze({
        mediaType: HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
        byteLength: canonical.right.byteLength,
        sha256: sha256(canonical.right)
      })
    })
  )
}

const validateSchemaBinding = (
  schema: HSWMCanonicalSchemaV2,
  binding: CanonicalAtomV2SchemaContentBinding
): Either.Either<void, CanonicalAtomV2StateJournalError> => {
  const expected = schemaBindingFor(snapshotHSWMCanonicalSchemaV2(schema))
  if (
    Either.isLeft(expected) ||
    !sameCanonicalAtomV2ContentDescriptor(expected.right.content, binding.content) ||
    binding.schemaVersion !== expected.right.schemaVersion
  ) {
    return fail("SCHEMA_BINDING_INVALID", "journal record is not bound to the exact active schema bytes")
  }
  return Either.right(undefined)
}

export const makeCanonicalAtomV2StateJournalGenesis = (
  journalLineageId: string,
  schema: HSWMCanonicalSchemaV2
): Either.Either<CanonicalAtomV2StateJournalGenesis, CanonicalAtomV2StateJournalError> => {
  if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(journalLineageId)) {
    return fail("GENESIS_INVALID", "journalLineageId is invalid")
  }
  const binding = schemaBindingFor(snapshotHSWMCanonicalSchemaV2(schema))
  if (Either.isLeft(binding)) return Either.left(binding.left)
  const state = initialCanonicalAtomV2State(schema.schemaVersion)
  const digest = canonicalAtomV2StateSha256(state)
  if (Either.isLeft(digest)) return Either.left(digest.left)
  return Either.right(
    snapshotGenesis({
      _tag: "CanonicalAtomV2StateJournalGenesis",
      contractVersion: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION,
      encoding: HSWM_CANONICAL_JSON_VERSION,
      journalLineageId,
      schema: binding.right,
      stateRevision: 0,
      bootstrapClosed: false,
      predecessor: null,
      resultingStateSha256: digest.right
    })
  )
}

export const applyCanonicalAtomV2StateJournalGenesis = (
  schema: HSWMCanonicalSchemaV2,
  record: CanonicalAtomV2StateJournalGenesis
): Either.Either<CanonicalAtomV2State, CanonicalAtomV2StateJournalError> => {
  const decoded = decodeRecord(record)
  if (Either.isLeft(decoded) || decoded.right._tag !== "CanonicalAtomV2StateJournalGenesis") {
    return fail("GENESIS_INVALID", "genesis record violates the strict v1 contract")
  }
  const binding = validateSchemaBinding(schema, decoded.right.schema)
  if (Either.isLeft(binding)) return Either.left(binding.left)
  const state = initialCanonicalAtomV2State(schema.schemaVersion)
  const digest = canonicalAtomV2StateSha256(state)
  if (Either.isLeft(digest)) return Either.left(digest.left)
  return digest.right === decoded.right.resultingStateSha256
    ? Either.right(state)
    : fail("STATE_DIGEST_INVALID", "genesis resulting state digest does not match revision zero")
}

export type CanonicalAtomV2JournalEnvelopeInput =
  | ReadonlyArray<CanonicalAtomV2>
  | ReadonlyArray<Uint8Array>

const decodeEnvelopeAtoms = (
  inputs: CanonicalAtomV2JournalEnvelopeInput,
  bindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): Either.Either<ReadonlyArray<CanonicalAtomV2>, CanonicalAtomV2StateJournalError> => {
  if (inputs.length !== bindings.length) {
    return fail("ENVELOPE_INVALID", "journal commit must supply exactly one envelope per write binding")
  }
  const atoms: Array<CanonicalAtomV2> = []
  for (let index = 0; index < inputs.length; index += 1) {
    const input = inputs[index]!
    let atom: CanonicalAtomV2
    let bytes: Uint8Array
    if (input instanceof Uint8Array) {
      const parsed = decodeCanonicalJsonBytes(input)
      if (Either.isLeft(parsed)) return fail("ENVELOPE_INVALID", "atom envelope bytes are not bounded duplicate-free JSON")
      const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
        onExcessProperty: "error"
      })(parsed.right)
      if (Either.isLeft(decoded)) return fail("ENVELOPE_INVALID", "atom envelope bytes violate the strict atom contract")
      atom = snapshotCanonicalAtomV2(decoded.right)
      const canonical = canonicalAtomV2EnvelopeBytes(atom)
      if (Either.isLeft(canonical) || !sameBytes(input, canonical.right)) {
        return fail("ENVELOPE_INVALID", "atom envelope bytes must be exact canonical JSON/v1")
      }
      bytes = canonical.right
    } else {
      const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
        onExcessProperty: "error"
      })(input)
      if (Either.isLeft(decoded)) return fail("ENVELOPE_INVALID", "decoded atom envelope violates the strict atom contract")
      atom = snapshotCanonicalAtomV2(decoded.right)
      const canonical = canonicalAtomV2EnvelopeBytes(atom)
      if (Either.isLeft(canonical)) return fail("ENVELOPE_INVALID", "decoded atom has no canonical envelope encoding")
      bytes = canonical.right
    }
    const binding = bindings[index]!
    const expected = binding.envelope
    if (
      expected.mediaType !== HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE ||
      expected.byteLength !== bytes.byteLength ||
      expected.sha256 !== sha256(bytes) ||
      canonicalAtomV2KeyId(atom.key) !== canonicalAtomV2KeyId(binding.key) ||
      !sameCanonicalAtomV2ContentDescriptor(atom.content, binding.payload)
    ) {
      return fail("ENVELOPE_INVALID", "atom envelope does not exactly match its journal binding")
    }
    atoms.push(atom)
  }
  return Either.right(Object.freeze(atoms))
}

const receiptCommand = (
  receipt: CanonicalAtomV2EffectReceipt,
  writes: ReadonlyArray<CanonicalAtomV2>
) =>
  Object.freeze({
    _tag: "CommitCanonicalAtomsV2" as const,
    contractVersion: "hswm-canonical-transition/v2" as const,
    transitionId: receipt.transitionId,
    expectedStateRevision: receipt.previousStateRevision,
    schemaVersion: receipt.schemaVersion,
    actorClaim: receipt.actorClaim,
    authorizationRef: receipt.authorizationRef,
    scope: receipt.scope,
    decidedAt: receipt.decidedAt,
    traceRef: receipt.traceRef,
    readSet: receipt.readSet,
    writes,
    provenanceSha256: receipt.provenanceSha256
  })

const sameReceipt = (
  left: CanonicalAtomV2EffectReceipt,
  right: CanonicalAtomV2EffectReceipt
): boolean => {
  const leftBytes = canonicalJsonBytes(snapshotCanonicalAtomV2Receipt(left))
  const rightBytes = canonicalJsonBytes(snapshotCanonicalAtomV2Receipt(right))
  return Either.isRight(leftBytes) && Either.isRight(rightBytes) && sameBytes(leftBytes.right, rightBytes.right)
}

export interface CanonicalAtomV2StateJournalAppliedCommit {
  readonly state: CanonicalAtomV2State
  readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly record: CanonicalAtomV2StateJournalCommit
}

export const applyCanonicalAtomV2StateJournalCommit = (
  schema: HSWMCanonicalSchemaV2,
  previous: {
    readonly state: CanonicalAtomV2State
    readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor
    readonly journalLineageId: string
    readonly schema: CanonicalAtomV2SchemaContentBinding
  },
  recordInput: CanonicalAtomV2StateJournalCommit,
  envelopes: CanonicalAtomV2JournalEnvelopeInput
): Either.Either<CanonicalAtomV2StateJournalAppliedCommit, CanonicalAtomV2StateJournalError | CanonicalAtomV2Error> => {
  const decoded = decodeRecord(recordInput)
  if (Either.isLeft(decoded) || decoded.right._tag !== "CanonicalAtomV2StateJournalCommit") {
    return fail("RECORD_INVALID", "commit record violates the strict v1 contract")
  }
  const record = decoded.right
  if (
    record.journalLineageId !== previous.journalLineageId ||
    !sameDescriptor(record.predecessor, previous.descriptor) ||
    record.stateRevision !== previous.state.revision + 1
  ) {
    return fail("PREDECESSOR_INVALID", "commit does not name the exact immediate journal predecessor")
  }
  if (
    record.schema.schemaVersion !== previous.schema.schemaVersion ||
    !sameCanonicalAtomV2ContentDescriptor(record.schema.content, previous.schema.content)
  ) {
    return fail("SCHEMA_BINDING_INVALID", "commit changes the active schema binding; migration is not implemented")
  }
  const binding = validateSchemaBinding(schema, record.schema)
  if (Either.isLeft(binding)) return Either.left(binding.left)
  const previousDigest = canonicalAtomV2StateSha256(previous.state)
  if (Either.isLeft(previousDigest)) return Either.left(previousDigest.left)
  if (previousDigest.right !== record.previousStateSha256) {
    return fail("STATE_DIGEST_INVALID", "commit previous state digest does not bind the supplied predecessor state")
  }
  if (
    record.receipt.previousStateRevision !== previous.state.revision ||
    record.receipt.nextStateRevision !== record.stateRevision ||
    record.receipt.schemaVersion !== schema.schemaVersion ||
    record.receipt.decision !== "ACCEPTED" ||
    record.receipt.guard.permission !== "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"
  ) {
    return fail("RECEIPT_INVALID", "commit receipt does not describe this non-authorizing state transition")
  }
  const atoms = decodeEnvelopeAtoms(envelopes, record.writeBindings)
  if (Either.isLeft(atoms)) return Either.left(atoms.left)
  if (!bindingsAreStrictlyAscending(record.writeBindings)) {
    return fail("WRITE_BINDING_INVALID", "persisted journal write bindings must use ascending canonical key order")
  }
  const bindings = validateCanonicalAtomV2WriteContentBindings(atoms.right, record.writeBindings)
  if (Either.isLeft(bindings)) {
    return fail("WRITE_BINDING_INVALID", bindings.left.detail)
  }
  const command = receiptCommand(record.receipt, atoms.right)
  const evolved = evolveCanonicalAtomsV2(schema, previous.state, command)
  if (Either.isLeft(evolved)) return Either.left(evolved.left)
  const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(
    command,
    previous.state.revision,
    evolved.right.revision
  )
  if (!sameReceipt(record.receipt, expectedReceipt)) {
    return fail("RECEIPT_INVALID", "commit receipt is not the exact deterministic receipt for its envelopes")
  }
  const resultingDigest = canonicalAtomV2StateSha256(evolved.right)
  if (Either.isLeft(resultingDigest)) return Either.left(resultingDigest.left)
  if (resultingDigest.right !== record.resultingStateSha256) {
    return fail("STATE_DIGEST_INVALID", "commit resulting state digest does not match deterministic replay")
  }
  const descriptor = describeCanonicalAtomV2StateJournalRecord(record)
  if (Either.isLeft(descriptor)) return Either.left(descriptor.left)
  return Either.right(
    Object.freeze({
      state: evolved.right,
      descriptor: descriptor.right,
      record: snapshotCommit(record)
    })
  )
}

export const makeCanonicalAtomV2StateJournalCommit = (
  schema: HSWMCanonicalSchemaV2,
  previous: {
    readonly state: CanonicalAtomV2State
    readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor
    readonly journalLineageId: string
    readonly schema: CanonicalAtomV2SchemaContentBinding
  },
  receipt: CanonicalAtomV2EffectReceipt,
  writeBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>,
  envelopes: CanonicalAtomV2JournalEnvelopeInput
): Either.Either<CanonicalAtomV2StateJournalCommit, CanonicalAtomV2StateJournalError | CanonicalAtomV2Error> => {
  const before = canonicalAtomV2StateSha256(previous.state)
  if (Either.isLeft(before)) return Either.left(before.left)
  const atoms = decodeEnvelopeAtoms(envelopes, writeBindings)
  if (Either.isLeft(atoms)) return Either.left(atoms.left)
  const command = receiptCommand(receipt, atoms.right)
  const evolved = evolveCanonicalAtomsV2(schema, previous.state, command)
  if (Either.isLeft(evolved)) return Either.left(evolved.left)
  const after = canonicalAtomV2StateSha256(evolved.right)
  if (Either.isLeft(after)) return Either.left(after.left)
  const record = snapshotCommit({
    _tag: "CanonicalAtomV2StateJournalCommit",
    contractVersion: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION,
    encoding: HSWM_CANONICAL_JSON_VERSION,
    journalLineageId: previous.journalLineageId,
    schema: previous.schema,
    stateRevision: evolved.right.revision,
    predecessor: previous.descriptor,
    receipt,
    writeBindings: Object.freeze(writeBindings.map(snapshotCanonicalAtomV2WriteContentBinding)),
    previousStateSha256: before.right,
    resultingStateSha256: after.right,
    durability: "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"
  })
  const applied = applyCanonicalAtomV2StateJournalCommit(schema, previous, record, envelopes)
  return Either.isLeft(applied) ? Either.left(applied.left) : Either.right(applied.right.record)
}
