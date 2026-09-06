import { randomUUID } from "node:crypto"
import { dirname, isAbsolute, join, resolve } from "node:path"

import { Effect, Either, Layer, Option, Schema } from "effect"

import {
  CanonicalAtomV2ContentDescriptorSchema,
  CanonicalAtomV2ContentStore,
  CanonicalAtomV2ContentStoreError,
  CanonicalAtomV2SchemaContentBindingSchema,
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  canonicalJsonBytes,
  canonicalJsonSha256,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  NodePosixFileSystem,
  PosixFileSystem,
  type PosixFileSystemShape,
  type PosixIoError
} from "./effect-posix-services.js"

const OBJECTS = "objects"
const BINDINGS = "schema-bindings"
const DIGEST = /^[0-9a-f]{64}$/
const MAX_BINDING_BYTES = 1_048_576
const FS_OPERATION = "canonical-atom-v2-content-file"
const UNSUPPORTED_LINK_CODES: ReadonlySet<PosixIoError["code"]> = new Set<PosixIoError["code"]>([
  "ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"
])

type Operation = CanonicalAtomV2ContentStoreError["operation"]

/**
 * Internal helpers leave POSIX failures that the original adapter did not
 * classify as raw `PosixIoError` values; each public operation maps whatever
 * remains to `IO_FAILED`, and the few call sites that distinguish `ENOENT`
 * do so before that boundary.
 */
type StoreFailure = CanonicalAtomV2ContentStoreError | PosixIoError

interface DirectoryIdentity {
  readonly path: string
  readonly device: number
  readonly inode: number
}

interface StoreIdentity {
  readonly root: DirectoryIdentity
  readonly objects: DirectoryIdentity
  readonly bindings: DirectoryIdentity
}

const error = (
  operation: Operation,
  reason: CanonicalAtomV2ContentStoreError["reason"],
  detail: string
): CanonicalAtomV2ContentStoreError =>
  new CanonicalAtomV2ContentStoreError({ operation, reason, detail })

const ioFailed = (operation: Operation, detail: string) =>
  <A, R>(program: Effect.Effect<A, StoreFailure, R>): Effect.Effect<A, CanonicalAtomV2ContentStoreError, R> =>
    program.pipe(Effect.catchTag("PosixIoError", () => Effect.fail(error(operation, "IO_FAILED", detail))))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((byte, index) => byte === right[index])

const snapshot = (descriptor: CanonicalAtomV2ContentDescriptor) =>
  Object.freeze({ ...descriptor })

const inspectDirectory = (
  fs: PosixFileSystemShape,
  path: string,
  operation: Operation
): Effect.Effect<DirectoryIdentity, StoreFailure> =>
  Effect.gen(function* () {
    const identity = yield* fs.identity(path, FS_OPERATION)
    if (identity.kind !== "DIRECTORY" || identity.mode !== 0o700) {
      return yield* Effect.fail(error(operation, "ROOT_UNSAFE", "content root must be a private plain 0700 directory"))
    }
    return Object.freeze({ path, device: identity.device, inode: identity.inode })
  })

const assertDirectory = (
  fs: PosixFileSystemShape,
  identity: DirectoryIdentity,
  operation: Operation
): Effect.Effect<void, StoreFailure> =>
  Effect.gen(function* () {
    const current = yield* fs.identity(identity.path, FS_OPERATION)
    if (
      current.kind !== "DIRECTORY" || current.device !== identity.device ||
      current.inode !== identity.inode || current.mode !== 0o700
    ) {
      return yield* Effect.fail(error(operation, "ROOT_UNSAFE", "content directory identity or permissions changed"))
    }
  })

/** fsync of a provisioning parent; any failure is a typed `IO_FAILED`. */
const syncProvisionedDirectory = (
  fs: PosixFileSystemShape,
  path: string,
  operation: Operation
): Effect.Effect<void, CanonicalAtomV2ContentStoreError> =>
  fs.syncDirectory(path, FS_OPERATION).pipe(
    Effect.mapError(() => error(operation, "IO_FAILED", "directory provisioning sync failed"))
  )

const makeDirectoryIfAbsent = (fs: PosixFileSystemShape, path: string): Effect.Effect<void, PosixIoError> =>
  fs.makeDirectory(path, { mode: 0o700, operation: FS_OPERATION }).pipe(
    Effect.catchIf((cause) => cause.code === "EEXIST", () => Effect.void)
  )

const initialize = (fs: PosixFileSystemShape, input: string): Effect.Effect<StoreIdentity, CanonicalAtomV2ContentStoreError> =>
  Effect.gen(function* () {
    if (!isAbsolute(input)) return yield* Effect.fail(error("PUT", "ROOT_UNSAFE", "content root must be absolute"))
    const requested = resolve(input)
    yield* makeDirectoryIfAbsent(fs, requested)
    const requestedIdentity = yield* fs.identity(requested, FS_OPERATION)
    if (requestedIdentity.kind !== "DIRECTORY") {
      return yield* Effect.fail(error("PUT", "ROOT_UNSAFE", "requested content root must be a plain directory"))
    }
    const rootPath = yield* fs.realpath(requested, FS_OPERATION)
    const root = yield* inspectDirectory(fs, rootPath, "PUT")
    yield* syncProvisionedDirectory(fs, dirname(root.path), "PUT")
    yield* makeDirectoryIfAbsent(fs, join(root.path, OBJECTS))
    yield* makeDirectoryIfAbsent(fs, join(root.path, BINDINGS))
    const objects = yield* inspectDirectory(fs, join(root.path, OBJECTS), "PUT")
    const bindings = yield* inspectDirectory(fs, join(root.path, BINDINGS), "PUT")
    yield* syncProvisionedDirectory(fs, root.path, "PUT")
    return Object.freeze({ root, objects, bindings })
  }).pipe(ioFailed("PUT", "content store initialization failed"))

/**
 * Bounded no-follow read of one immutable 0400 entry whose directory and file
 * identities are re-checked.  `ENOENT` and other unclassified POSIX failures
 * stay raw so callers can decide between absence and I/O failure.
 */
const readRegular = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  name: string,
  maximum: number,
  operation: Operation
): Effect.Effect<Uint8Array, StoreFailure> =>
  Effect.gen(function* () {
    yield* assertDirectory(fs, directory, operation)
    const result = yield* fs.readRegularBounded(
      join(directory.path, name),
      { maximumBytes: maximum, requiredMode: 0o400, operation: FS_OPERATION }
    ).pipe(
      Effect.mapError((cause): StoreFailure =>
        cause.code === "ELOOP"
          ? error(operation, "FILE_TYPE_INVALID", "content entry must not be a symlink")
          : cause.code === "NOT_REGULAR_FILE"
            ? error(operation, "FILE_TYPE_INVALID", "content entry is not a regular file")
            : cause.code === "MODE_INVALID"
              ? error(operation, "FILE_TYPE_INVALID", "immutable content entry must have mode 0400")
              : cause.code === "BYTE_BOUND_EXCEEDED"
                ? error(operation, "BYTE_LENGTH_EXCEEDED", "content entry violates byte bound")
                : cause.code === "IDENTITY_CHANGED"
                  ? error(operation, "CONTENT_CORRUPT", "content entry changed during bounded read")
                  : cause
      )
    )
    return result.bytes
  })

const syncDirectory = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  operation: Operation
): Effect.Effect<void, StoreFailure> =>
  Effect.gen(function* () {
    yield* assertDirectory(fs, directory, operation)
    yield* fs.syncDirectory(directory.path, FS_OPERATION)
  })

/**
 * One no-replace publication: exclusive private staging file, fsync, hard
 * link into the digest-named entry, directory fsync, exact readback, and
 * unconditional staging cleanup.  A link that is refused because the entry
 * already exists is reconciled by comparing the existing bytes.
 */
const publish = (
  fs: PosixFileSystemShape,
  directory: DirectoryIdentity,
  name: string,
  bytes: Uint8Array,
  maximum: number,
  operation: Operation
): Effect.Effect<void, StoreFailure> => {
  if (!DIGEST.test(name)) return Effect.fail(error(operation, "DESCRIPTOR_INVALID", "publication filename must be digest-derived"))
  if (bytes.byteLength > maximum) return Effect.fail(error(operation, "BYTE_LENGTH_EXCEEDED", "publication exceeds byte bound"))
  const finalPath = join(directory.path, name)
  const reconcileLink = (cause: PosixIoError): Effect.Effect<void, StoreFailure> =>
    readRegular(fs, directory, name, maximum, operation).pipe(
      Effect.flatMap((existing) =>
        sameBytes(existing, bytes)
          ? Effect.void
          : Effect.fail(error(operation, "CONTENT_CORRUPT", "immutable destination contains different bytes"))
      ),
      Effect.catchTag("PosixIoError", (readCause) =>
        Effect.fail(
          UNSUPPORTED_LINK_CODES.has(cause.code)
            ? error(operation, "ATOMIC_PUBLICATION_UNSUPPORTED", cause.code)
            : readCause
        )
      )
    )
  const reconcileSync: Effect.Effect<void, StoreFailure> = Effect.gen(function* () {
    const existing = yield* readRegular(fs, directory, name, maximum, operation)
    if (!sameBytes(existing, bytes)) {
      return yield* Effect.fail(error(operation, "PUBLICATION_OUTCOME_UNKNOWN", "directory sync failed and entry differs"))
    }
    yield* syncDirectory(fs, directory, operation)
  }).pipe(
    Effect.catchTag("PosixIoError", () =>
      Effect.fail(error(operation, "PUBLICATION_OUTCOME_UNKNOWN", "directory sync outcome cannot be reconciled"))
    )
  )
  const staged = (temporaryPath: string): Effect.Effect<void, StoreFailure> =>
    Effect.gen(function* () {
      yield* fs.writeExclusive(temporaryPath, bytes, { mode: 0o600, finalMode: 0o400, sync: true, operation: FS_OPERATION })
      yield* fs.linkNoReplace(temporaryPath, finalPath, FS_OPERATION).pipe(Effect.catchTag("PosixIoError", reconcileLink))
      yield* syncDirectory(fs, directory, operation).pipe(Effect.catchAll(() => reconcileSync))
      const exact = yield* readRegular(fs, directory, name, maximum, operation)
      if (!sameBytes(exact, bytes)) {
        return yield* Effect.fail(error(operation, "PUBLICATION_OUTCOME_UNKNOWN", "readback differs after publication"))
      }
    })
  return Effect.gen(function* () {
    yield* assertDirectory(fs, directory, operation)
    const temporaryPath = yield* Effect.sync(() => join(directory.path, `.canonical-v2-${randomUUID()}.tmp`))
    // A stale private staging file is not committed; its removal never changes the outcome.
    yield* staged(temporaryPath).pipe(Effect.ensuring(fs.unlinkIfPresent(temporaryPath, FS_OPERATION).pipe(Effect.ignore)))
  })
}

const descriptorError = (operation: Operation, detail: string) =>
  error(operation, "DESCRIPTOR_INVALID", detail)

const bindingName = (schemaVersion: string): Either.Either<string, CanonicalAtomV2ContentStoreError> => {
  const digest = canonicalJsonSha256({ schemaVersion })
  return Either.isLeft(digest)
    ? Either.left(descriptorError("BIND_SCHEMA", "schema version cannot form canonical binding key"))
    : Either.right(digest.right)
}

const decodeBinding = (bytes: Uint8Array): Either.Either<CanonicalAtomV2SchemaContentBinding, CanonicalAtomV2ContentStoreError> => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) return Either.left(descriptorError("RESOLVE_SCHEMA", "binding bytes are not canonical JSON"))
  const binding = Schema.decodeUnknownEither(CanonicalAtomV2SchemaContentBindingSchema)(decoded.right)
  if (Either.isLeft(binding)) return Either.left(descriptorError("RESOLVE_SCHEMA", "binding record is invalid"))
  const recanonical = canonicalJsonBytes(binding.right)
  if (Either.isLeft(recanonical) || !sameBytes(recanonical.right, bytes)) {
    return Either.left(descriptorError("RESOLVE_SCHEMA", "binding bytes drift from canonical form"))
  }
  return Either.right(Object.freeze({ schemaVersion: binding.right.schemaVersion, content: snapshot(binding.right.content) }))
}

const sameBinding = (
  left: CanonicalAtomV2SchemaContentBinding,
  right: CanonicalAtomV2SchemaContentBinding
): boolean =>
  left.schemaVersion === right.schemaVersion &&
  sameCanonicalAtomV2ContentDescriptor(left.content, right.content)

const makeContentFileStore = (
  fs: PosixFileSystemShape,
  rootPath: string
): Effect.Effect<CanonicalAtomV2ContentStore["Type"], CanonicalAtomV2ContentStoreError> =>
  Effect.gen(function* () {
    const identity = yield* initialize(fs, rootPath)
    const get = (
      descriptor: CanonicalAtomV2ContentDescriptor,
      operation: "GET" | "VERIFY"
    ): Effect.Effect<Uint8Array, CanonicalAtomV2ContentStoreError> =>
      Effect.gen(function* () {
        const valid = Schema.decodeUnknownEither(CanonicalAtomV2ContentDescriptorSchema)(descriptor)
        if (Either.isLeft(valid)) return yield* Effect.fail(descriptorError(operation, "descriptor is invalid"))
        const bytes = yield* readRegular(fs, identity.objects, descriptor.sha256, descriptor.byteLength, operation).pipe(
          Effect.catchTag("PosixIoError", (cause) =>
            Effect.fail(
              cause.code === "ENOENT"
                ? error(operation, "CONTENT_NOT_FOUND", "content digest is absent")
                : error(operation, "IO_FAILED", "content read failed")
            )
          )
        )
        const actual = makeCanonicalAtomV2ContentDescriptor(descriptor.mediaType, bytes)
        if (Either.isLeft(actual) || !sameCanonicalAtomV2ContentDescriptor(actual.right, descriptor)) {
          return yield* Effect.fail(error(operation, "CONTENT_CORRUPT", "content does not match descriptor"))
        }
        return Uint8Array.from(bytes)
      })
    return CanonicalAtomV2ContentStore.of({
      put: (mediaType, bytes) => {
        // Caller bytes are copied at invocation so later mutation cannot reach the store.
        const copied = Uint8Array.from(bytes)
        const descriptor = makeCanonicalAtomV2ContentDescriptor(mediaType, copied)
        return Effect.gen(function* () {
          if (Either.isLeft(descriptor)) return yield* Effect.fail(descriptor.left)
          yield* publish(fs, identity.objects, descriptor.right.sha256, copied, descriptor.right.byteLength, "PUT").pipe(
            ioFailed("PUT", "content write failed")
          )
          return snapshot(descriptor.right)
        })
      },
      get: (descriptor) => get(descriptor, "GET"),
      verify: (descriptor) => get(descriptor, "VERIFY").pipe(Effect.asVoid),
      bindSchema: (binding) => Effect.gen(function* () {
        const valid = Schema.decodeUnknownEither(CanonicalAtomV2SchemaContentBindingSchema)(binding)
        if (Either.isLeft(valid)) return yield* Effect.fail(descriptorError("BIND_SCHEMA", "binding is invalid"))
        yield* get(valid.right.content, "VERIFY")
        const name = bindingName(valid.right.schemaVersion)
        if (Either.isLeft(name)) return yield* Effect.fail(name.left)
        const bytes = canonicalJsonBytes(valid.right)
        if (Either.isLeft(bytes)) return yield* Effect.fail(descriptorError("BIND_SCHEMA", "binding cannot be canonicalized"))
        const previous = yield* readRegular(fs, identity.bindings, name.right, MAX_BINDING_BYTES, "BIND_SCHEMA").pipe(
          Effect.map(Option.some),
          Effect.catchTag("PosixIoError", (cause) =>
            cause.code === "ENOENT"
              ? Effect.succeed(Option.none<Uint8Array>())
              : Effect.fail(error("BIND_SCHEMA", "IO_FAILED", "schema binding failed"))
          )
        )
        if (Option.isSome(previous)) {
          const decoded = decodeBinding(previous.value)
          if (Either.isLeft(decoded) || !sameBinding(decoded.right, valid.right)) {
            return yield* Effect.fail(error("BIND_SCHEMA", "SCHEMA_BINDING_CONFLICT", "schema version is bound to different content"))
          }
          return
        }
        yield* publish(fs, identity.bindings, name.right, bytes.right, bytes.right.byteLength, "BIND_SCHEMA").pipe(
          ioFailed("BIND_SCHEMA", "schema binding failed")
        )
        const published = yield* readRegular(fs, identity.bindings, name.right, bytes.right.byteLength, "BIND_SCHEMA").pipe(
          ioFailed("BIND_SCHEMA", "schema binding failed")
        )
        const readback = decodeBinding(published)
        if (Either.isLeft(readback) || !sameBinding(readback.right, valid.right)) {
          return yield* Effect.fail(error("BIND_SCHEMA", "SCHEMA_BINDING_CONFLICT", "schema version is bound to different content"))
        }
      }),
      resolveSchema: (schemaVersion) => Effect.gen(function* () {
        const name = bindingName(schemaVersion)
        if (Either.isLeft(name)) return yield* Effect.fail(name.left)
        const bytes = yield* readRegular(fs, identity.bindings, name.right, MAX_BINDING_BYTES, "RESOLVE_SCHEMA").pipe(
          Effect.catchTag("PosixIoError", (cause) =>
            Effect.fail(
              cause.code === "ENOENT"
                ? error("RESOLVE_SCHEMA", "SCHEMA_NOT_BOUND", "schema version has no binding")
                : error("RESOLVE_SCHEMA", "IO_FAILED", "schema binding lookup failed")
            )
          )
        )
        const binding = decodeBinding(bytes)
        if (Either.isLeft(binding) || binding.right.schemaVersion !== schemaVersion) {
          return yield* Effect.fail(error("RESOLVE_SCHEMA", "CONTENT_CORRUPT", "binding record is corrupt"))
        }
        yield* get(binding.right.content, "VERIFY")
        return snapshot(binding.right.content)
      })
    })
  })

/**
 * POSIX/Linux local-filesystem adapter. Its root and parents must be controlled
 * by the caller: Node lacks openat2, so hostile parent replacement, network
 * filesystem semantics, and cross-host durability are explicitly out of scope.
 */
export const makeCanonicalAtomV2ContentFileStoreLayer = (
  rootPath: string
): Layer.Layer<CanonicalAtomV2ContentStore, CanonicalAtomV2ContentStoreError> =>
  Layer.effect(CanonicalAtomV2ContentStore, makeContentFileStore(NodePosixFileSystem, rootPath))

/** The same adapter over whichever `PosixFileSystem` the composition root provides. */
export const makeCanonicalAtomV2ContentFileStoreLayerFromService = (
  rootPath: string
): Layer.Layer<CanonicalAtomV2ContentStore, CanonicalAtomV2ContentStoreError, PosixFileSystem> =>
  Layer.effect(
    CanonicalAtomV2ContentStore,
    Effect.flatMap(PosixFileSystem, (fs) => makeContentFileStore(fs, rootPath))
  )
