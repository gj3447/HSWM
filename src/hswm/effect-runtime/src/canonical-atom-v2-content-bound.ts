import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes,
  HSWM_CANONICAL_JSON_MEDIA_TYPE,
  HSWM_CANONICAL_JSON_VERSION
} from "./canonical-atom-v2-json.js"
import {
  CanonicalAtomV2ContentDescriptorSchema,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  CanonicalAtomV2Error,
  validateHSWMCanonicalSchemaV2,
  type CanonicalAtomV2EffectReceipt,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  CanonicalAtomV2KeySchema,
  CanonicalAtomV2Schema,
  CommitCanonicalAtomsV2CommandSchema,
  HSWMCanonicalSchemaV2Schema,
  canonicalAtomV2KeyId,
  snapshotCanonicalAtomV2,
  snapshotHSWMCanonicalSchemaV2,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export const HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE =
  "application/vnd.hswm.canonical-schema-v2+json" as const
export const HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE =
  "application/vnd.hswm.canonical-atom-v2+json" as const
export const HSWM_CANONICAL_CONTENT_BOUND_TRANSITION_V2_CONTRACT_VERSION =
  "hswm-canonical-content-bound-transition/v2" as const
export const HSWM_CANONICAL_CONTENT_BOUND_RECEIPT_V2_CONTRACT_VERSION =
  "hswm-canonical-content-bound-receipt/v2" as const

const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)

export interface CanonicalAtomV2ValidatedSchemaContent {
  readonly schema: HSWMCanonicalSchemaV2
  readonly binding: CanonicalAtomV2SchemaContentBinding
  readonly canonicalBytes: Uint8Array
  readonly encoding: typeof HSWM_CANONICAL_JSON_VERSION
}

export interface CanonicalAtomV2WriteContentBinding {
  readonly key: CanonicalAtomV2Key
  readonly payload: CanonicalAtomV2ContentDescriptor
  readonly envelope: CanonicalAtomV2ContentDescriptor
}

export const CanonicalAtomV2WriteContentBindingSchema: Schema.Schema<CanonicalAtomV2WriteContentBinding> =
  Schema.Struct({
    key: CanonicalAtomV2KeySchema,
    payload: CanonicalAtomV2ContentDescriptorSchema,
    envelope: CanonicalAtomV2ContentDescriptorSchema
  })

export interface CommitCanonicalAtomsV2ContentBound {
  readonly _tag: "CommitCanonicalAtomsV2ContentBound"
  readonly contractVersion: typeof HSWM_CANONICAL_CONTENT_BOUND_TRANSITION_V2_CONTRACT_VERSION
  readonly schemaContentSha256: string
  readonly command: CommitCanonicalAtomsV2Command
  readonly writeBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
}

export const CommitCanonicalAtomsV2ContentBoundSchema: Schema.Schema<CommitCanonicalAtomsV2ContentBound> =
  Schema.Struct({
    _tag: Schema.Literal("CommitCanonicalAtomsV2ContentBound"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CONTENT_BOUND_TRANSITION_V2_CONTRACT_VERSION
    ),
    schemaContentSha256: Sha256,
    command: CommitCanonicalAtomsV2CommandSchema,
    writeBindings: Schema.Array(
      CanonicalAtomV2WriteContentBindingSchema
    ).pipe(Schema.minItems(1), Schema.maxItems(64))
  })

export interface CanonicalAtomV2ContentAuthorizationGrant {
  readonly authorizationRef: string
  readonly schemaVersion: string
  readonly schemaContentSha256: string
  readonly scopes: ReadonlyArray<string>
}

export const CanonicalAtomV2ContentAuthorizationGrantSchema: Schema.Schema<CanonicalAtomV2ContentAuthorizationGrant> =
  Schema.Struct({
    authorizationRef: Identifier,
    schemaVersion: Identifier,
    schemaContentSha256: Sha256,
    scopes: Schema.Array(Identifier).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    )
  })

export const CanonicalAtomV2ContentAuthorizationGrantsSchema = Schema.Array(
  CanonicalAtomV2ContentAuthorizationGrantSchema
).pipe(Schema.maxItems(256))

export interface CanonicalAtomV2ContentBoundReceipt {
  readonly _tag: "CanonicalAtomV2ContentBoundReceipt"
  readonly contractVersion: typeof HSWM_CANONICAL_CONTENT_BOUND_RECEIPT_V2_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly effect: CanonicalAtomV2EffectReceipt
  readonly writeBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
  readonly contentDurability: "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE"
}

export interface CanonicalAtomV2ContentBoundState {
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly canonical: CanonicalAtomV2State
  readonly atomBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
}

export interface CanonicalAtomV2ContentBoundEvolution {
  readonly state: CanonicalAtomV2ContentBoundState
  readonly receipt: CanonicalAtomV2ContentBoundReceipt
}

export class CanonicalAtomV2ContentBindingError extends Data.TaggedError(
  "CanonicalAtomV2ContentBindingError"
)<{
  readonly reason:
    | "ATOM_ENVELOPE_INVALID"
    | "BINDING_BIJECTION_INVALID"
    | "CANONICAL_ENCODING_INVALID"
    | "SCHEMA_BYTES_INVALID"
    | "SCHEMA_CONTENT_MISMATCH"
  readonly detail: string
}> {}

const bindingError = (
  reason: CanonicalAtomV2ContentBindingError["reason"],
  detail: string
): CanonicalAtomV2ContentBindingError =>
  new CanonicalAtomV2ContentBindingError({ reason, detail })

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const descriptorFor = (
  mediaType: string,
  bytes: Uint8Array
): CanonicalAtomV2ContentDescriptor =>
  Object.freeze({
    mediaType,
    byteLength: bytes.byteLength,
    sha256: sha256(bytes)
  })

const snapshotDescriptor = (
  descriptor: CanonicalAtomV2ContentDescriptor
): CanonicalAtomV2ContentDescriptor => Object.freeze({ ...descriptor })

const snapshotKey = (key: CanonicalAtomV2Key): CanonicalAtomV2Key =>
  Object.freeze({ ...key })

const compareText = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0

const compareKeys = (
  left: CanonicalAtomV2Key,
  right: CanonicalAtomV2Key
): number => compareText(canonicalAtomV2KeyId(left), canonicalAtomV2KeyId(right))

export const snapshotCanonicalAtomV2WriteContentBinding = (
  binding: CanonicalAtomV2WriteContentBinding
): CanonicalAtomV2WriteContentBinding =>
  Object.freeze({
    key: snapshotKey(binding.key),
    payload: snapshotDescriptor(binding.payload),
    envelope: snapshotDescriptor(binding.envelope)
  })

export const snapshotCanonicalAtomV2SchemaContentBinding = (
  binding: CanonicalAtomV2SchemaContentBinding
): CanonicalAtomV2SchemaContentBinding =>
  Object.freeze({
    schemaVersion: binding.schemaVersion,
    content: snapshotDescriptor(binding.content)
  })

export const canonicalAtomV2SchemaContentBytes = (
  schema: HSWMCanonicalSchemaV2
): Either.Either<Uint8Array, CanonicalAtomV2ContentBindingError> => {
  const decoded = Schema.decodeUnknownEither(HSWMCanonicalSchemaV2Schema, {
    onExcessProperty: "error"
  })(schema)
  if (Either.isLeft(decoded)) {
    return Either.left(
      bindingError(
        "SCHEMA_BYTES_INVALID",
        "schema does not satisfy the strict v2 structural contract"
      )
    )
  }
  const validated = validateHSWMCanonicalSchemaV2(decoded.right)
  if (Either.isLeft(validated)) {
    return Either.left(
      bindingError(
        "SCHEMA_BYTES_INVALID",
        "schema does not satisfy the semantic v2 contract"
      )
    )
  }
  const encoded = canonicalJsonBytes(
    snapshotHSWMCanonicalSchemaV2(validated.right)
  )
  return Either.isLeft(encoded)
    ? Either.left(
        bindingError(
          "CANONICAL_ENCODING_INVALID",
          "validated schema cannot be represented by the bounded canonical JSON contract"
        )
      )
    : Either.right(Uint8Array.from(encoded.right))
}

export const canonicalAtomV2EnvelopeBytes = (
  atom: CanonicalAtomV2
): Either.Either<Uint8Array, CanonicalAtomV2ContentBindingError> => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
    onExcessProperty: "error"
  })(atom)
  if (Either.isLeft(decoded)) {
    return Either.left(
      bindingError(
        "ATOM_ENVELOPE_INVALID",
        "atom does not satisfy the strict v2 contract"
      )
    )
  }
  const encoded = canonicalJsonBytes(snapshotCanonicalAtomV2(decoded.right))
  return Either.isLeft(encoded)
    ? Either.left(
        bindingError(
          "CANONICAL_ENCODING_INVALID",
          "atom cannot be represented by the bounded canonical JSON contract"
        )
      )
    : Either.right(Uint8Array.from(encoded.right))
}

export const describeCanonicalAtomV2Envelope = (
  atom: CanonicalAtomV2
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2ContentBindingError> => {
  const bytes = canonicalAtomV2EnvelopeBytes(atom)
  return Either.isLeft(bytes)
    ? Either.left(bytes.left)
    : Either.right(
        descriptorFor(HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE, bytes.right)
      )
}

export const decodeCanonicalAtomV2SchemaContent = (
  input: Uint8Array
): Either.Either<CanonicalAtomV2ValidatedSchemaContent, CanonicalAtomV2ContentBindingError | CanonicalAtomV2Error> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return Either.left(
      bindingError(
        "SCHEMA_BYTES_INVALID",
        "schema bytes are not duplicate-free bounded JSON"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(HSWMCanonicalSchemaV2Schema, {
    onExcessProperty: "error"
  })(parsed.right)
  if (Either.isLeft(decoded)) {
    return Either.left(
      bindingError(
        "SCHEMA_BYTES_INVALID",
        "schema bytes do not satisfy the strict v2 structural contract"
      )
    )
  }
  const validated = validateHSWMCanonicalSchemaV2(decoded.right)
  if (Either.isLeft(validated)) return Either.left(validated.left)
  const schema = snapshotHSWMCanonicalSchemaV2(validated.right)
  const canonical = canonicalAtomV2SchemaContentBytes(schema)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  const content = descriptorFor(
    HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
    canonical.right
  )
  return Either.right(
    Object.freeze({
      schema,
      binding: snapshotCanonicalAtomV2SchemaContentBinding({
        schemaVersion: schema.schemaVersion,
        content
      }),
      get canonicalBytes(): Uint8Array {
        return Uint8Array.from(canonical.right)
      },
      encoding: HSWM_CANONICAL_JSON_VERSION
    })
  )
}

export const makeCanonicalAtomV2ContentBoundInput = (
  schemaContentSha256: string,
  command: CommitCanonicalAtomsV2Command,
  writeBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): CommitCanonicalAtomsV2ContentBound =>
  Object.freeze({
    _tag: "CommitCanonicalAtomsV2ContentBound",
    contractVersion:
      HSWM_CANONICAL_CONTENT_BOUND_TRANSITION_V2_CONTRACT_VERSION,
    schemaContentSha256,
    command: Object.freeze({
      ...command,
      traceRef:
        command.traceRef === null ? null : snapshotKey(command.traceRef),
      readSet: Object.freeze(command.readSet.map(snapshotKey)),
      writes: Object.freeze(command.writes.map(snapshotCanonicalAtomV2))
    }),
    writeBindings: Object.freeze(
      writeBindings.map(snapshotCanonicalAtomV2WriteContentBinding)
    )
  })

export const validateCanonicalAtomV2WriteContentBindings = (
  writes: ReadonlyArray<CanonicalAtomV2>,
  bindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): Either.Either<ReadonlyArray<CanonicalAtomV2WriteContentBinding>, CanonicalAtomV2ContentBindingError> => {
  const writeByKey = new Map(
    writes.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
  )
  const bindingIds = bindings.map(({ key }) => canonicalAtomV2KeyId(key))
  if (
    writeByKey.size !== writes.length ||
    new Set(bindingIds).size !== bindingIds.length ||
    bindings.length !== writes.length ||
    bindingIds.some((id) => !writeByKey.has(id))
  ) {
    return Either.left(
      bindingError(
        "BINDING_BIJECTION_INVALID",
        "write bindings must form an exact one-to-one map over the command write set"
      )
    )
  }
  const snapshots: Array<CanonicalAtomV2WriteContentBinding> = []
  for (const binding of bindings) {
    const atom = writeByKey.get(canonicalAtomV2KeyId(binding.key))
    if (atom === undefined) {
      return Either.left(
        bindingError("BINDING_BIJECTION_INVALID", "write binding is missing its atom")
      )
    }
    if (!sameCanonicalAtomV2ContentDescriptor(atom.content, binding.payload)) {
      return Either.left(
        bindingError(
          "BINDING_BIJECTION_INVALID",
          `payload descriptor for ${atom.key.atomUid} differs from the atom envelope`
        )
      )
    }
    const expectedEnvelope = describeCanonicalAtomV2Envelope(atom)
    if (
      Either.isLeft(expectedEnvelope) ||
      !sameCanonicalAtomV2ContentDescriptor(
        expectedEnvelope.right,
        binding.envelope
      )
    ) {
      return Either.left(
        bindingError(
          "ATOM_ENVELOPE_INVALID",
          `metadata envelope for ${atom.key.atomUid} does not match its canonical bytes`
        )
      )
    }
    snapshots.push(snapshotCanonicalAtomV2WriteContentBinding(binding))
  }
  return Either.right(
    Object.freeze(
      snapshots.sort((left, right) => compareKeys(left.key, right.key))
    )
  )
}

export const sameCanonicalAtomV2SchemaBinding = (
  left: CanonicalAtomV2SchemaContentBinding,
  right: CanonicalAtomV2SchemaContentBinding
): boolean =>
  left.schemaVersion === right.schemaVersion &&
  sameCanonicalAtomV2ContentDescriptor(left.content, right.content)

// Exported so callers can label the schema bytes without confusing them with
// arbitrary JSON payload bytes.
export const HSWM_CANONICAL_SCHEMA_JSON_ENCODING = Object.freeze({
  version: HSWM_CANONICAL_JSON_VERSION,
  genericMediaType: HSWM_CANONICAL_JSON_MEDIA_TYPE,
  schemaMediaType: HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE
})
