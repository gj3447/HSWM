import { randomUUID } from "node:crypto"
import { constants } from "node:fs"
import { link, lstat, mkdir, open, realpath, unlink } from "node:fs/promises"
import { dirname, isAbsolute, join, resolve } from "node:path"

import { Effect, Either, Layer, Schema } from "effect"

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

const OBJECTS = "objects"
const BINDINGS = "schema-bindings"
const DIGEST = /^[0-9a-f]{64}$/

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
  operation: CanonicalAtomV2ContentStoreError["operation"],
  reason: CanonicalAtomV2ContentStoreError["reason"],
  detail: string
): CanonicalAtomV2ContentStoreError =>
  new CanonicalAtomV2ContentStoreError({ operation, reason, detail })

const hasCode = (input: unknown): input is { readonly code: string } =>
  typeof input === "object" && input !== null && "code" in input &&
  typeof input.code === "string"

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((byte, index) => byte === right[index])

const snapshot = (descriptor: CanonicalAtomV2ContentDescriptor) =>
  Object.freeze({ ...descriptor })

const inspectDirectory = async (path: string, operation: CanonicalAtomV2ContentStoreError["operation"]): Promise<DirectoryIdentity> => {
  const stat = await lstat(path)
  if (stat.isSymbolicLink() || !stat.isDirectory() || (stat.mode & 0o777) !== 0o700) {
    throw error(operation, "ROOT_UNSAFE", "content root must be a private plain 0700 directory")
  }
  return Object.freeze({ path, device: stat.dev, inode: stat.ino })
}

const syncPlainDirectoryPath = async (
  path: string,
  operation: CanonicalAtomV2ContentStoreError["operation"]
): Promise<void> => {
  const handle = await open(
    path,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW
  )
  try {
    await handle.sync()
  } catch (cause) {
    throw cause instanceof CanonicalAtomV2ContentStoreError
      ? cause
      : error(operation, "IO_FAILED", "directory provisioning sync failed")
  } finally {
    await handle.close()
  }
}

const assertDirectory = async (identity: DirectoryIdentity, operation: CanonicalAtomV2ContentStoreError["operation"]): Promise<void> => {
  const current = await lstat(identity.path)
  if (current.isSymbolicLink() || !current.isDirectory() || current.dev !== identity.device || current.ino !== identity.inode || (current.mode & 0o777) !== 0o700) {
    throw error(operation, "ROOT_UNSAFE", "content directory identity or permissions changed")
  }
}

const initialize = async (input: string): Promise<StoreIdentity> => {
  if (!isAbsolute(input)) throw error("PUT", "ROOT_UNSAFE", "content root must be absolute")
  const requested = resolve(input)
  try {
    await mkdir(requested, { mode: 0o700 })
  } catch (cause) {
    if (!hasCode(cause) || cause.code !== "EEXIST") throw cause
  }
  const requestedStat = await lstat(requested)
  if (requestedStat.isSymbolicLink() || !requestedStat.isDirectory()) {
    throw error("PUT", "ROOT_UNSAFE", "requested content root must be a plain directory")
  }
  const root = await inspectDirectory(await realpath(requested), "PUT")
  await syncPlainDirectoryPath(dirname(root.path), "PUT")
  for (const name of [OBJECTS, BINDINGS]) {
    try { await mkdir(join(root.path, name), { mode: 0o700 }) } catch (cause) {
      if (!hasCode(cause) || cause.code !== "EEXIST") throw cause
    }
  }
  const objects = await inspectDirectory(join(root.path, OBJECTS), "PUT")
  const bindings = await inspectDirectory(join(root.path, BINDINGS), "PUT")
  await syncPlainDirectoryPath(root.path, "PUT")
  return Object.freeze({ root, objects, bindings })
}

const readRegular = async (
  directory: DirectoryIdentity,
  name: string,
  maximum: number,
  operation: CanonicalAtomV2ContentStoreError["operation"]
): Promise<Uint8Array> => {
  await assertDirectory(directory, operation)
  let handle
  try {
    handle = await open(join(directory.path, name), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  } catch (cause) {
    if (hasCode(cause) && cause.code === "ENOENT") throw cause
    if (hasCode(cause) && cause.code === "ELOOP") throw error(operation, "FILE_TYPE_INVALID", "content entry must not be a symlink")
    throw cause
  }
  try {
    const before = await handle.stat()
    if (!before.isFile()) throw error(operation, "FILE_TYPE_INVALID", "content entry is not a regular file")
    if ((before.mode & 0o777) !== 0o400) {
      throw error(operation, "FILE_TYPE_INVALID", "immutable content entry must have mode 0400")
    }
    if (before.size < 0 || before.size > maximum) throw error(operation, "BYTE_LENGTH_EXCEEDED", "content entry violates byte bound")
    const buffer = Buffer.alloc(before.size + 1)
    let total = 0
    while (total < buffer.byteLength) {
      const result = await handle.read(buffer, total, buffer.byteLength - total, total)
      if (result.bytesRead === 0) break
      total += result.bytesRead
    }
    const after = await handle.stat()
    if (total !== before.size || after.size !== before.size || after.ino !== before.ino || after.dev !== before.dev || (after.mode & 0o777) !== 0o400) {
      throw error(operation, "CONTENT_CORRUPT", "content entry changed during bounded read")
    }
    return Uint8Array.from(buffer.subarray(0, total))
  } finally { await handle.close() }
}

const syncDirectory = async (directory: DirectoryIdentity, operation: CanonicalAtomV2ContentStoreError["operation"]): Promise<void> => {
  await assertDirectory(directory, operation)
  const handle = await open(directory.path, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW)
  try { await handle.sync() } finally { await handle.close() }
}

const publish = async (
  directory: DirectoryIdentity,
  name: string,
  bytes: Uint8Array,
  maximum: number,
  operation: CanonicalAtomV2ContentStoreError["operation"]
): Promise<void> => {
  if (!DIGEST.test(name)) throw error(operation, "DESCRIPTOR_INVALID", "publication filename must be digest-derived")
  if (bytes.byteLength > maximum) throw error(operation, "BYTE_LENGTH_EXCEEDED", "publication exceeds byte bound")
  await assertDirectory(directory, operation)
  const finalPath = join(directory.path, name)
  const temporaryPath = join(directory.path, `.canonical-v2-${randomUUID()}.tmp`)
  let temporary = false
  try {
    const handle = await open(temporaryPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600)
    temporary = true
    try { await handle.writeFile(bytes); await handle.chmod(0o400); await handle.sync() } finally { await handle.close() }
    try { await link(temporaryPath, finalPath) } catch (cause) {
      try {
        const existing = await readRegular(directory, name, maximum, operation)
        if (!sameBytes(existing, bytes)) throw error(operation, "CONTENT_CORRUPT", "immutable destination contains different bytes")
      } catch (readCause) {
        if (readCause instanceof CanonicalAtomV2ContentStoreError) throw readCause
        if (hasCode(cause) && ["ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EXDEV"].includes(cause.code)) {
          throw error(operation, "ATOMIC_PUBLICATION_UNSUPPORTED", cause.code)
        }
        throw readCause
      }
    }
    try { await syncDirectory(directory, operation) } catch (first) {
      try {
        const existing = await readRegular(directory, name, maximum, operation)
        if (!sameBytes(existing, bytes)) throw error(operation, "PUBLICATION_OUTCOME_UNKNOWN", "directory sync failed and entry differs")
        await syncDirectory(directory, operation)
      } catch (second) {
        if (second instanceof CanonicalAtomV2ContentStoreError) throw second
        throw error(operation, "PUBLICATION_OUTCOME_UNKNOWN", "directory sync outcome cannot be reconciled")
      }
    }
    const exact = await readRegular(directory, name, maximum, operation)
    if (!sameBytes(exact, bytes)) throw error(operation, "PUBLICATION_OUTCOME_UNKNOWN", "readback differs after publication")
  } finally {
    if (temporary) { try { await unlink(temporaryPath) } catch { /* stale private temp is not committed */ } }
  }
}

const descriptorError = (operation: CanonicalAtomV2ContentStoreError["operation"], detail: string) =>
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

/**
 * POSIX/Linux local-filesystem adapter. Its root and parents must be controlled
 * by the caller: Node lacks openat2, so hostile parent replacement, network
 * filesystem semantics, and cross-host durability are explicitly out of scope.
 */
export const makeCanonicalAtomV2ContentFileStoreLayer = (rootPath: string) =>
  Layer.effect(CanonicalAtomV2ContentStore, Effect.gen(function* () {
    const identity = yield* Effect.tryPromise({
      try: () => initialize(rootPath),
      catch: (cause) =>
        cause instanceof CanonicalAtomV2ContentStoreError
          ? cause
          : error("PUT", "IO_FAILED", "content store initialization failed")
    })
    const get = (descriptor: CanonicalAtomV2ContentDescriptor, operation: "GET" | "VERIFY") => Effect.tryPromise({
      try: async () => {
        const valid = Schema.decodeUnknownEither(CanonicalAtomV2ContentDescriptorSchema)(descriptor)
        if (Either.isLeft(valid)) throw descriptorError(operation, "descriptor is invalid")
        let bytes: Uint8Array
        try { bytes = await readRegular(identity.objects, descriptor.sha256, descriptor.byteLength, operation) } catch (cause) {
          if (hasCode(cause) && cause.code === "ENOENT") throw error(operation, "CONTENT_NOT_FOUND", "content digest is absent")
          throw cause
        }
        const actual = makeCanonicalAtomV2ContentDescriptor(descriptor.mediaType, bytes)
        if (Either.isLeft(actual) || !sameCanonicalAtomV2ContentDescriptor(actual.right, descriptor)) throw error(operation, "CONTENT_CORRUPT", "content does not match descriptor")
        return Uint8Array.from(bytes)
      },
      catch: (cause) => cause instanceof CanonicalAtomV2ContentStoreError ? cause : error(operation, "IO_FAILED", "content read failed")
    })
    return CanonicalAtomV2ContentStore.of({
      put: (mediaType, bytes) => {
        const copied = Uint8Array.from(bytes)
        const descriptor = makeCanonicalAtomV2ContentDescriptor(mediaType, copied)
        return Effect.tryPromise({
        try: async () => {
          if (Either.isLeft(descriptor)) throw descriptor.left
          await publish(identity.objects, descriptor.right.sha256, copied, descriptor.right.byteLength, "PUT")
          return snapshot(descriptor.right)
        },
        catch: (cause) => cause instanceof CanonicalAtomV2ContentStoreError ? cause : error("PUT", "IO_FAILED", "content write failed")
        })
      },
      get: (descriptor) => get(descriptor, "GET"),
      verify: (descriptor) => get(descriptor, "VERIFY").pipe(Effect.asVoid),
      bindSchema: (binding) => Effect.tryPromise({
        try: async () => {
          const valid = Schema.decodeUnknownEither(CanonicalAtomV2SchemaContentBindingSchema)(binding)
          if (Either.isLeft(valid)) throw descriptorError("BIND_SCHEMA", "binding is invalid")
          const content = await get(valid.right.content, "VERIFY").pipe(Effect.runPromise)
          void content
          const name = bindingName(valid.right.schemaVersion)
          if (Either.isLeft(name)) throw name.left
          const bytes = canonicalJsonBytes(valid.right)
          if (Either.isLeft(bytes)) throw descriptorError("BIND_SCHEMA", "binding cannot be canonicalized")
          try {
            const previous = decodeBinding(
              await readRegular(identity.bindings, name.right, 1_048_576, "BIND_SCHEMA")
            )
            if (
              Either.isLeft(previous) ||
              previous.right.schemaVersion !== valid.right.schemaVersion ||
              !sameCanonicalAtomV2ContentDescriptor(previous.right.content, valid.right.content)
            ) {
              throw error("BIND_SCHEMA", "SCHEMA_BINDING_CONFLICT", "schema version is bound to different content")
            }
            return
          } catch (cause) {
            if (cause instanceof CanonicalAtomV2ContentStoreError) throw cause
            if (!hasCode(cause) || cause.code !== "ENOENT") throw cause
          }
          await publish(identity.bindings, name.right, bytes.right, bytes.right.byteLength, "BIND_SCHEMA")
          const readback = decodeBinding(await readRegular(identity.bindings, name.right, bytes.right.byteLength, "BIND_SCHEMA"))
          if (Either.isLeft(readback) || readback.right.schemaVersion !== valid.right.schemaVersion || !sameCanonicalAtomV2ContentDescriptor(readback.right.content, valid.right.content)) {
            throw error("BIND_SCHEMA", "SCHEMA_BINDING_CONFLICT", "schema version is bound to different content")
          }
        },
        catch: (cause) => cause instanceof CanonicalAtomV2ContentStoreError ? cause : error("BIND_SCHEMA", "IO_FAILED", "schema binding failed")
      }),
      resolveSchema: (schemaVersion) => Effect.tryPromise({
        try: async () => {
          const name = bindingName(schemaVersion)
          if (Either.isLeft(name)) throw name.left
          let bytes: Uint8Array
          try { bytes = await readRegular(identity.bindings, name.right, 1_048_576, "RESOLVE_SCHEMA") } catch (cause) {
            if (hasCode(cause) && cause.code === "ENOENT") throw error("RESOLVE_SCHEMA", "SCHEMA_NOT_BOUND", "schema version has no binding")
            throw cause
          }
          const binding = decodeBinding(bytes)
          if (Either.isLeft(binding) || binding.right.schemaVersion !== schemaVersion) throw error("RESOLVE_SCHEMA", "CONTENT_CORRUPT", "binding record is corrupt")
          await get(binding.right.content, "VERIFY").pipe(Effect.runPromise)
          return snapshot(binding.right.content)
        },
        catch: (cause) => cause instanceof CanonicalAtomV2ContentStoreError ? cause : error("RESOLVE_SCHEMA", "IO_FAILED", "schema binding lookup failed")
      })
    })
  }))
