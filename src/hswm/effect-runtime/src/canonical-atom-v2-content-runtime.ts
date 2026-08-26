import type { ParseResult } from "effect"
import { Context, Data, Effect, Either, Layer, Ref, Schema } from "effect"

import {
  CanonicalAtomV2ContentStore,
  CanonicalAtomV2ContentStoreError,
  makeCanonicalAtomV2ContentStoreMemoryLayer,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import { makeCanonicalAtomV2ContentFileStoreLayer } from "./canonical-atom-v2-content-file.js"
import {
  CanonicalAtomV2ContentAuthorizationGrantsSchema,
  CanonicalAtomV2ContentBindingError,
  CommitCanonicalAtomsV2ContentBoundSchema,
  HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
  canonicalAtomV2EnvelopeBytes,
  decodeCanonicalAtomV2SchemaContent,
  sameCanonicalAtomV2SchemaBinding,
  snapshotCanonicalAtomV2SchemaContentBinding,
  snapshotCanonicalAtomV2WriteContentBinding,
  validateCanonicalAtomV2WriteContentBindings,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2ContentBoundEvolution,
  type CanonicalAtomV2ContentBoundReceipt,
  type CanonicalAtomV2ContentBoundState,
  type CanonicalAtomV2ValidatedSchemaContent,
  type CanonicalAtomV2WriteContentBinding,
  type CommitCanonicalAtomsV2ContentBound
} from "./canonical-atom-v2-content-bound.js"
import {
  CanonicalAtomV2Error,
  evolveCanonicalAtomsV2,
  initialCanonicalAtomV2State,
  makeCanonicalAtomV2AcceptedReceipt,
  snapshotCanonicalAtomV2Receipt,
  snapshotCanonicalAtomV2State,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  canonicalAtomV2KeyId,
  snapshotCommitCanonicalAtomsV2Command,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export class CanonicalAtomV2ContentAuthorizationDenied extends Data.TaggedError(
  "CanonicalAtomV2ContentAuthorizationDenied"
)<{
  readonly reason:
    | "NOT_GRANTED"
    | "SCHEMA_CONTENT_MISMATCH"
    | "SCHEMA_MISMATCH"
    | "SCOPE_DENIED"
  readonly authorizationRef: string
}> {}

export class CanonicalAtomV2ContentAuthorizationConfigurationError extends Data.TaggedError(
  "CanonicalAtomV2ContentAuthorizationConfigurationError"
)<{
  readonly detail: string
}> {}

export class CanonicalAtomV2ContentRuntime extends Context.Tag(
  "hswm/CanonicalAtomV2ContentRuntime"
)<
  CanonicalAtomV2ContentRuntime,
  {
    readonly schema: HSWMCanonicalSchemaV2
    readonly schemaContent: CanonicalAtomV2SchemaContentBinding
    readonly contentDurability: "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE"
    readonly stageContent: (
      mediaType: string,
      bytes: Uint8Array
    ) => Effect.Effect<
      CanonicalAtomV2ContentDescriptor,
      CanonicalAtomV2ContentStoreError
    >
    readonly readContent: (
      descriptor: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<Uint8Array, CanonicalAtomV2ContentStoreError>
    readonly snapshot: Effect.Effect<CanonicalAtomV2ContentBoundState>
    readonly history: Effect.Effect<
      ReadonlyArray<CanonicalAtomV2ContentBoundReceipt>
    >
    readonly submit: (
      input: unknown
    ) => Effect.Effect<
      CanonicalAtomV2ContentBoundEvolution,
      | ParseResult.ParseError
      | CanonicalAtomV2ContentAuthorizationDenied
      | CanonicalAtomV2ContentBindingError
      | CanonicalAtomV2ContentStoreError
      | CanonicalAtomV2Error
    >
  }
>() {}

interface CanonicalAtomV2ContentMemory {
  readonly state: CanonicalAtomV2State
  readonly atomBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
  readonly journal: ReadonlyArray<CanonicalAtomV2ContentBoundReceipt>
}

type CommitAttempt =
  | {
      readonly _tag: "Committed"
      readonly value: CanonicalAtomV2ContentBoundEvolution
    }
  | { readonly _tag: "Rejected"; readonly error: CanonicalAtomV2Error }

const snapshotGrant = (
  grant: CanonicalAtomV2ContentAuthorizationGrant
): CanonicalAtomV2ContentAuthorizationGrant =>
  Object.freeze({
    authorizationRef: grant.authorizationRef,
    schemaVersion: grant.schemaVersion,
    schemaContentSha256: grant.schemaContentSha256,
    scopes: Object.freeze([...grant.scopes])
  })

const snapshotContentReceipt = (
  receipt: CanonicalAtomV2ContentBoundReceipt
): CanonicalAtomV2ContentBoundReceipt =>
  Object.freeze({
    _tag: receipt._tag,
    contractVersion: receipt.contractVersion,
    schema: snapshotCanonicalAtomV2SchemaContentBinding(receipt.schema),
    effect: snapshotCanonicalAtomV2Receipt(receipt.effect),
    writeBindings: Object.freeze(
      receipt.writeBindings.map(snapshotCanonicalAtomV2WriteContentBinding)
    ),
    contentDurability: receipt.contentDurability
  })

const snapshotContentState = (
  schema: CanonicalAtomV2SchemaContentBinding,
  memory: CanonicalAtomV2ContentMemory
): CanonicalAtomV2ContentBoundState =>
  Object.freeze({
    schema: snapshotCanonicalAtomV2SchemaContentBinding(schema),
    canonical: snapshotCanonicalAtomV2State(memory.state),
    atomBindings: Object.freeze(
      memory.atomBindings.map(snapshotCanonicalAtomV2WriteContentBinding)
    )
  })

const makeAuthorizer = (
  activeSchema: CanonicalAtomV2SchemaContentBinding,
  grants: ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant>
) => {
  const retained = Object.freeze(grants.map(snapshotGrant))
  return (
    input: CommitCanonicalAtomsV2ContentBound
  ): Effect.Effect<void, CanonicalAtomV2ContentAuthorizationDenied> => {
    const command = input.command
    if (
      input.schemaContentSha256 !== activeSchema.content.sha256
    ) {
      return Effect.fail(
        new CanonicalAtomV2ContentAuthorizationDenied({
          reason: "SCHEMA_CONTENT_MISMATCH",
          authorizationRef: command.authorizationRef
        })
      )
    }
    const matchingReference = retained.filter(
      ({ authorizationRef }) =>
        authorizationRef === command.authorizationRef
    )
    if (matchingReference.length === 0) {
      return Effect.fail(
        new CanonicalAtomV2ContentAuthorizationDenied({
          reason: "NOT_GRANTED",
          authorizationRef: command.authorizationRef
        })
      )
    }
    const matchingSchema = matchingReference.filter(
      ({ schemaVersion }) => schemaVersion === command.schemaVersion
    )
    if (matchingSchema.length === 0) {
      return Effect.fail(
        new CanonicalAtomV2ContentAuthorizationDenied({
          reason: "SCHEMA_MISMATCH",
          authorizationRef: command.authorizationRef
        })
      )
    }
    const matchingContent = matchingSchema.filter(
      ({ schemaContentSha256 }) =>
        schemaContentSha256 === activeSchema.content.sha256
    )
    if (matchingContent.length === 0) {
      return Effect.fail(
        new CanonicalAtomV2ContentAuthorizationDenied({
          reason: "SCHEMA_CONTENT_MISMATCH",
          authorizationRef: command.authorizationRef
        })
      )
    }
    if (
      !matchingContent.some(({ scopes }) => scopes.includes(command.scope))
    ) {
      return Effect.fail(
        new CanonicalAtomV2ContentAuthorizationDenied({
          reason: "SCOPE_DENIED",
          authorizationRef: command.authorizationRef
        })
      )
    }
    return Effect.void
  }
}

const decodeContentBoundInput = Schema.decodeUnknown(
  CommitCanonicalAtomsV2ContentBoundSchema,
  { onExcessProperty: "error" }
)

const decodeContentGrants = Schema.decodeUnknown(
  CanonicalAtomV2ContentAuthorizationGrantsSchema,
  { onExcessProperty: "error" }
)

const validateGrantConfiguration = (
  schema: CanonicalAtomV2SchemaContentBinding,
  grants: ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant>
): Effect.Effect<
  ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant>,
  CanonicalAtomV2ContentAuthorizationConfigurationError
> => {
  const grantKeys = grants.map(
    ({ authorizationRef, schemaVersion, schemaContentSha256 }) =>
      `${authorizationRef}|${schemaVersion}|${schemaContentSha256}`
  )
  const invalid =
    new Set(grantKeys).size !== grantKeys.length ||
    grants.some(
      ({ schemaVersion, schemaContentSha256, scopes }) =>
        schemaVersion !== schema.schemaVersion ||
        schemaContentSha256 !== schema.content.sha256 ||
        new Set(scopes).size !== scopes.length
    )
  return invalid
    ? Effect.fail(
        new CanonicalAtomV2ContentAuthorizationConfigurationError({
          detail:
            "content-bound grants must be unique and match the exact active schema bytes"
        })
      )
    : Effect.succeed(Object.freeze(grants.map(snapshotGrant)))
}

const prepareWriteContent = (
  store: CanonicalAtomV2ContentStore["Type"],
  command: CommitCanonicalAtomsV2Command,
  bindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): Effect.Effect<
  ReadonlyArray<CanonicalAtomV2WriteContentBinding>,
  CanonicalAtomV2ContentBindingError | CanonicalAtomV2ContentStoreError
> =>
  Effect.gen(function* () {
    const checked = validateCanonicalAtomV2WriteContentBindings(
      command.writes,
      bindings
    )
    if (Either.isLeft(checked)) return yield* checked.left
    const atomByKey = new Map(
      command.writes.map(
        (atom) => [canonicalAtomV2KeyId(atom.key), atom] as const
      )
    )
    const envelopes: Array<{
      readonly binding: CanonicalAtomV2WriteContentBinding
      readonly bytes: Uint8Array
    }> = []
    for (const binding of checked.right) {
      yield* store.verify(binding.payload)
      const atom = atomByKey.get(canonicalAtomV2KeyId(binding.key))
      if (atom === undefined) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "BINDING_BIJECTION_INVALID",
          detail: "validated binding lost its write atom"
        })
      }
      const envelopeBytes = canonicalAtomV2EnvelopeBytes(atom)
      if (Either.isLeft(envelopeBytes)) return yield* envelopeBytes.left
      envelopes.push({ binding, bytes: envelopeBytes.right })
    }
    for (const { binding, bytes } of envelopes) {
      const storedEnvelope = yield* store.put(
        HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
        bytes
      )
      if (
        !sameCanonicalAtomV2ContentDescriptor(
          storedEnvelope,
          binding.envelope
        )
      ) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "ATOM_ENVELOPE_INVALID",
          detail: "stored atom envelope differs from the declared descriptor"
        })
      }
    }
    return checked.right
  })

/**
 * Content-bound reference layer. Schema, payload, and atom-envelope bytes are
 * durable only to the guarantees of the supplied content-store adapter. The
 * canonical state and receipt journal remain process-local and non-durable.
 */
export const makeCanonicalAtomV2ContentRuntimeLayer = (
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) => {
  const retainedSchemaBytes =
    rawSchemaBytes instanceof Uint8Array
      ? Uint8Array.from(rawSchemaBytes)
      : null
  return Layer.effect(
    CanonicalAtomV2ContentRuntime,
    Effect.gen(function* () {
      if (retainedSchemaBytes === null) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "SCHEMA_BYTES_INVALID",
          detail: "schema ingress must be Uint8Array"
        })
      }
      const store = yield* CanonicalAtomV2ContentStore
      const decodedSchema = decodeCanonicalAtomV2SchemaContent(
        retainedSchemaBytes
      )
      if (Either.isLeft(decodedSchema)) return yield* decodedSchema.left
      const schemaContent: CanonicalAtomV2ValidatedSchemaContent =
        decodedSchema.right
      const storedSchema = yield* store.put(
        schemaContent.binding.content.mediaType,
        schemaContent.canonicalBytes
      )
      if (
        !sameCanonicalAtomV2ContentDescriptor(
          storedSchema,
          schemaContent.binding.content
        )
      ) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "SCHEMA_CONTENT_MISMATCH",
          detail: "stored schema bytes differ from the validated schema binding"
        })
      }
      yield* store.bindSchema(schemaContent.binding)
      const resolvedSchema = yield* store.resolveSchema(
        schemaContent.binding.schemaVersion
      )
      if (
        !sameCanonicalAtomV2SchemaBinding(schemaContent.binding, {
          schemaVersion: schemaContent.binding.schemaVersion,
          content: resolvedSchema
        })
      ) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "SCHEMA_CONTENT_MISMATCH",
          detail: "content store resolved a different schema binding"
        })
      }

      const decodedGrants = yield* decodeContentGrants(rawGrants)
      const grants = yield* validateGrantConfiguration(
        schemaContent.binding,
        decodedGrants
      )
      const authorize = makeAuthorizer(schemaContent.binding, grants)
      const memory = yield* Ref.make<CanonicalAtomV2ContentMemory>({
        state: initialCanonicalAtomV2State(
          schemaContent.schema.schemaVersion
        ),
        atomBindings: Object.freeze([]),
        journal: Object.freeze([])
      })

      const transact = (
        command: CommitCanonicalAtomsV2Command,
        writeBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
      ): Effect.Effect<CanonicalAtomV2ContentBoundEvolution, CanonicalAtomV2Error> =>
        Ref.modify(
          memory,
          (current): readonly [CommitAttempt, CanonicalAtomV2ContentMemory] => {
            const evolved = evolveCanonicalAtomsV2(
              schemaContent.schema,
              current.state,
              command
            )
            if (Either.isLeft(evolved)) {
              return [
                { _tag: "Rejected", error: evolved.left },
                current
              ]
            }
            const effectReceipt = makeCanonicalAtomV2AcceptedReceipt(
              command,
              current.state.revision,
              evolved.right.revision
            )
            const receipt = snapshotContentReceipt({
              _tag: "CanonicalAtomV2ContentBoundReceipt",
              contractVersion:
                "hswm-canonical-content-bound-receipt/v2",
              schema: schemaContent.binding,
              effect: effectReceipt,
              writeBindings,
              contentDurability:
                "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE"
            })
            const nextMemory: CanonicalAtomV2ContentMemory = {
              state: evolved.right,
              atomBindings: Object.freeze([
                ...current.atomBindings,
                ...writeBindings.map(
                  snapshotCanonicalAtomV2WriteContentBinding
                )
              ]),
              journal: Object.freeze([...current.journal, receipt])
            }
            const value = Object.freeze({
              state: snapshotContentState(
                schemaContent.binding,
                nextMemory
              ),
              receipt
            })
            return [{ _tag: "Committed", value }, nextMemory]
          }
        ).pipe(
          Effect.flatMap((attempt) =>
            attempt._tag === "Committed"
              ? Effect.succeed(attempt.value)
              : Effect.fail(attempt.error)
          )
        )

      return CanonicalAtomV2ContentRuntime.of({
        schema: schemaContent.schema,
        schemaContent: snapshotCanonicalAtomV2SchemaContentBinding(
          schemaContent.binding
        ),
        contentDurability: "CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE",
        stageContent: (mediaType, inputBytes) => {
          const retained = Uint8Array.from(inputBytes)
          return store.put(mediaType, retained)
        },
        readContent: (descriptor) => store.get(descriptor),
        snapshot: Ref.get(memory).pipe(
          Effect.map((current) =>
            snapshotContentState(schemaContent.binding, current)
          )
        ),
        history: Ref.get(memory).pipe(
          Effect.map(({ journal }) =>
            Object.freeze(journal.map(snapshotContentReceipt))
          )
        ),
        submit: (input) =>
          Effect.gen(function* () {
            const decoded = yield* decodeContentBoundInput(input)
            const command = snapshotCommitCanonicalAtomsV2Command(
              decoded.command
            )
            const contentInput: CommitCanonicalAtomsV2ContentBound =
              Object.freeze({
                _tag: decoded._tag,
                contractVersion: decoded.contractVersion,
                schemaContentSha256: decoded.schemaContentSha256,
                command,
                writeBindings: Object.freeze(
                  decoded.writeBindings.map(
                    snapshotCanonicalAtomV2WriteContentBinding
                  )
                )
              })
            yield* authorize(contentInput)
            yield* store.verify(schemaContent.binding.content)

            // Reject semantically invalid commands before publishing any new
            // envelope bytes. A concurrent winner may still leave a valid,
            // unreferenced envelope blob; it never receives a receipt.
            const current = yield* Ref.get(memory)
            for (const binding of current.atomBindings) {
              yield* store.verify(binding.payload)
              yield* store.verify(binding.envelope)
            }
            const candidate = evolveCanonicalAtomsV2(
              schemaContent.schema,
              current.state,
              command
            )
            if (Either.isLeft(candidate)) return yield* candidate.left
            const bindings = yield* prepareWriteContent(
              store,
              command,
              contentInput.writeBindings
            )
            return yield* transact(command, bindings)
          })
      })
    })
  )
}

/** In-memory content integrity witness; neither bytes nor state survive restart. */
export const makeCanonicalAtomV2ContentRuntimeMemoryLayer = (
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) =>
  makeCanonicalAtomV2ContentRuntimeLayer(
    rawSchemaBytes,
    rawGrants
  ).pipe(Layer.provide(makeCanonicalAtomV2ContentStoreMemoryLayer()))

/**
 * Local POSIX content durability plus process-local canonical state. The
 * supplied directory does not make the state/receipt journal durable.
 */
export const makeCanonicalAtomV2ContentRuntimeFileLayer = (
  rootPath: string,
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) =>
  makeCanonicalAtomV2ContentRuntimeLayer(
    rawSchemaBytes,
    rawGrants
  ).pipe(Layer.provide(makeCanonicalAtomV2ContentFileStoreLayer(rootPath)))
