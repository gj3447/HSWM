import { createHash } from "node:crypto"

import { Context, Data, Effect, Either, Layer, Schema } from "effect"

export const CANONICAL_ATOM_V2_CONTENT_MAX_BYTES = 16_777_216 as const

const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const MediaType = Schema.String.pipe(
  Schema.pattern(
    /^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/
  ),
  Schema.maxLength(255)
)
const ByteLength = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, CANONICAL_ATOM_V2_CONTENT_MAX_BYTES)
)

export interface CanonicalAtomV2ContentDescriptor {
  readonly mediaType: string
  readonly byteLength: number
  readonly sha256: string
}

export const CanonicalAtomV2ContentDescriptorSchema: Schema.Schema<CanonicalAtomV2ContentDescriptor> =
  Schema.Struct({
    mediaType: MediaType,
    byteLength: ByteLength,
    sha256: Sha256
  })

export interface CanonicalAtomV2SchemaContentBinding {
  readonly schemaVersion: string
  readonly content: CanonicalAtomV2ContentDescriptor
}

export const CanonicalAtomV2SchemaContentBindingSchema: Schema.Schema<CanonicalAtomV2SchemaContentBinding> =
  Schema.Struct({
    schemaVersion: Identifier,
    content: CanonicalAtomV2ContentDescriptorSchema
  })

export class CanonicalAtomV2ContentStoreError extends Data.TaggedError(
  "CanonicalAtomV2ContentStoreError"
)<{
  readonly operation: "PUT" | "GET" | "VERIFY" | "BIND_SCHEMA" | "RESOLVE_SCHEMA"
  readonly reason:
    | "BYTE_LENGTH_EXCEEDED"
    | "ATOMIC_PUBLICATION_UNSUPPORTED"
    | "CONTENT_CORRUPT"
    | "CONTENT_NOT_FOUND"
    | "DESCRIPTOR_INVALID"
    | "FILE_TYPE_INVALID"
    | "IO_FAILED"
    | "PUBLICATION_OUTCOME_UNKNOWN"
    | "ROOT_UNSAFE"
    | "SCHEMA_BINDING_CONFLICT"
    | "SCHEMA_NOT_BOUND"
  readonly detail: string
}> {}

const storeError = (
  operation: CanonicalAtomV2ContentStoreError["operation"],
  reason: CanonicalAtomV2ContentStoreError["reason"],
  detail: string
): CanonicalAtomV2ContentStoreError =>
  new CanonicalAtomV2ContentStoreError({ operation, reason, detail })

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const snapshotDescriptor = (
  descriptor: CanonicalAtomV2ContentDescriptor
): CanonicalAtomV2ContentDescriptor => Object.freeze({ ...descriptor })

export const sameCanonicalAtomV2ContentDescriptor = (
  left: CanonicalAtomV2ContentDescriptor,
  right: CanonicalAtomV2ContentDescriptor
): boolean =>
  left.mediaType === right.mediaType &&
  left.byteLength === right.byteLength &&
  left.sha256 === right.sha256

export const makeCanonicalAtomV2ContentDescriptor = (
  mediaType: string,
  input: Uint8Array
): Either.Either<
  CanonicalAtomV2ContentDescriptor,
  CanonicalAtomV2ContentStoreError
> => {
  if (!(input instanceof Uint8Array)) {
    return Either.left(
      storeError("PUT", "DESCRIPTOR_INVALID", "content must be Uint8Array")
    )
  }
  if (input.byteLength > CANONICAL_ATOM_V2_CONTENT_MAX_BYTES) {
    return Either.left(
      storeError(
        "PUT",
        "BYTE_LENGTH_EXCEEDED",
        "content exceeds the reference-port byte limit"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2ContentDescriptorSchema)(
    { mediaType, byteLength: input.byteLength, sha256: sha256(input) }
  )
  if (decoded._tag === "Left") {
    return Either.left(
      storeError("PUT", "DESCRIPTOR_INVALID", "descriptor fields are invalid")
    )
  }
  return Either.right(snapshotDescriptor(decoded.right))
}

export class CanonicalAtomV2ContentStore extends Context.Tag(
  "hswm/CanonicalAtomV2ContentStore"
)<
  CanonicalAtomV2ContentStore,
  {
    readonly put: (
      mediaType: string,
      bytes: Uint8Array
    ) => Effect.Effect<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2ContentStoreError>
    readonly get: (
      descriptor: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<Uint8Array, CanonicalAtomV2ContentStoreError>
    readonly verify: (
      descriptor: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<void, CanonicalAtomV2ContentStoreError>
    readonly bindSchema: (
      binding: CanonicalAtomV2SchemaContentBinding
    ) => Effect.Effect<void, CanonicalAtomV2ContentStoreError>
    readonly resolveSchema: (
      schemaVersion: string
    ) => Effect.Effect<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2ContentStoreError>
  }
>() {}

const validateDescriptor = (
  descriptor: CanonicalAtomV2ContentDescriptor,
  operation: CanonicalAtomV2ContentStoreError["operation"]
): CanonicalAtomV2ContentStoreError | null => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2ContentDescriptorSchema)(
    descriptor
  )
  return decoded._tag === "Left"
    ? storeError(operation, "DESCRIPTOR_INVALID", "descriptor is not schema-valid")
    : null
}

interface MemoryState {
  readonly content: Map<string, Uint8Array>
  readonly bindings: Map<string, CanonicalAtomV2ContentDescriptor>
}

export const makeCanonicalAtomV2ContentStoreMemoryLayer = () =>
  Layer.effect(
    CanonicalAtomV2ContentStore,
    Effect.gen(function* () {
      const memory = yield* Effect.sync(() =>
        new Map<string, Uint8Array>()
      )
      const bindings = yield* Effect.sync(() =>
        new Map<string, CanonicalAtomV2ContentDescriptor>()
      )
      const state: MemoryState = { content: memory, bindings }

      const get = (
        descriptor: CanonicalAtomV2ContentDescriptor,
        operation: "GET" | "VERIFY"
      ): Effect.Effect<Uint8Array, CanonicalAtomV2ContentStoreError> =>
        Effect.try({
          try: () => {
            const descriptorError = validateDescriptor(descriptor, operation)
            if (descriptorError !== null) throw descriptorError
            const bytes = state.content.get(descriptor.sha256)
            if (bytes === undefined) {
              throw storeError(operation, "CONTENT_NOT_FOUND", "content digest is absent")
            }
            if (bytes.byteLength !== descriptor.byteLength || sha256(bytes) !== descriptor.sha256) {
              throw storeError(operation, "CONTENT_CORRUPT", "content does not match descriptor")
            }
            return Uint8Array.from(bytes)
          },
          catch: (error) =>
            error instanceof CanonicalAtomV2ContentStoreError
              ? error
              : storeError(operation, "CONTENT_CORRUPT", "memory content lookup failed")
        })

      return CanonicalAtomV2ContentStore.of({
        put: (mediaType, bytes) => {
          const copied = Uint8Array.from(bytes)
          const made = makeCanonicalAtomV2ContentDescriptor(
            mediaType,
            copied
          )
          return Effect.try({
            try: () => {
              if (made._tag === "Left") throw made.left
              const descriptor = made.right
              const previous = state.content.get(descriptor.sha256)
              if (
                previous !== undefined &&
                (previous.byteLength !== copied.byteLength ||
                  !previous.every((byte, index) => byte === copied[index]))
              ) {
                throw storeError("PUT", "CONTENT_CORRUPT", "digest collision has different bytes")
              }
              if (previous === undefined) state.content.set(descriptor.sha256, copied)
              return descriptor
            },
            catch: (error) =>
              error instanceof CanonicalAtomV2ContentStoreError
                ? error
                : storeError("PUT", "DESCRIPTOR_INVALID", "content put failed")
          })
        },
        get: (descriptor) => get(descriptor, "GET"),
        verify: (descriptor) => get(descriptor, "VERIFY").pipe(Effect.asVoid),
        bindSchema: (binding) =>
          Effect.gen(function* () {
            const decoded = Schema.decodeUnknownEither(CanonicalAtomV2SchemaContentBindingSchema)(
              binding
            )
            if (decoded._tag === "Left") {
              return yield* Effect.fail(
                storeError("BIND_SCHEMA", "DESCRIPTOR_INVALID", "binding is not schema-valid")
              )
            }
            yield* get(decoded.right.content, "VERIFY")
            const previous = state.bindings.get(decoded.right.schemaVersion)
            if (
              previous !== undefined &&
              !sameCanonicalAtomV2ContentDescriptor(previous, decoded.right.content)
            ) {
              return yield* Effect.fail(
                storeError("BIND_SCHEMA", "SCHEMA_BINDING_CONFLICT", "schema version is already bound to other content")
              )
            }
            if (previous === undefined) {
              state.bindings.set(
                decoded.right.schemaVersion,
                snapshotDescriptor(decoded.right.content)
              )
            }
          }),
        resolveSchema: (schemaVersion) =>
          Effect.try({
            try: () => {
              const decoded = Schema.decodeUnknownEither(Identifier)(schemaVersion)
              if (decoded._tag === "Left") {
                throw storeError("RESOLVE_SCHEMA", "DESCRIPTOR_INVALID", "schema version is invalid")
              }
              const descriptor = state.bindings.get(schemaVersion)
              if (descriptor === undefined) {
                throw storeError("RESOLVE_SCHEMA", "SCHEMA_NOT_BOUND", "schema version has no content binding")
              }
              return snapshotDescriptor(descriptor)
            },
            catch: (error) =>
              error instanceof CanonicalAtomV2ContentStoreError
                ? error
                : storeError("RESOLVE_SCHEMA", "DESCRIPTOR_INVALID", "schema binding lookup failed")
          })
      })
    })
  )
