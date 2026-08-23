import { randomUUID } from "node:crypto"
import { constants } from "node:fs"
import {
  link,
  lstat,
  open,
  realpath,
  unlink
} from "node:fs/promises"
import { isAbsolute, join, resolve } from "node:path"

import { Context, Data, Effect, Either, Layer } from "effect"

import { rawS2SFileSha256 } from "./s2s-canonical.js"
import {
  S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS,
  S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES,
  buildS2STestOnlyGoldenArtifact,
  buildS2STestOnlyGoldenUploadPostcondition,
  reconstructS2STestOnlyGoldenUploadPostcondition,
  validateS2STestOnlyGoldenArtifactReadback,
  type S2STestOnlyGoldenArtifactMemberInput,
  type S2STestOnlyGoldenRole,
  type S2STestOnlyGoldenUploadFailure
} from "./s2s-test-only-golden-upload.js"

export interface S2STestOnlyGoldenArtifactPublicationReceipt {
  readonly _tag: "S2STestOnlyGoldenArtifactPublicationReceipt"
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly origin: "LOCAL_TEST_LAYER"
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: string
  readonly disposition: "CREATED"
  readonly archiveSha256: string
  readonly archiveByteLength: number
  readonly postconditionPublicationKey: string
  readonly postconditionSha256: string
  readonly postconditionByteLength: number
  readonly readArchiveBytes: () => Uint8Array
}

export interface S2STestOnlyGoldenArtifactReadbackMember {
  readonly name: string
  readonly rawSha256: string
  readonly byteLength: number
  readonly readBytes: () => Uint8Array
}

export interface S2STestOnlyGoldenArtifactReadback {
  readonly _tag: "S2STestOnlyGoldenArtifactReadback"
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly origin: "LOCAL_TEST_LAYER"
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: string
  readonly archiveSha256: string
  readonly archiveByteLength: number
  readonly postconditionPublicationKey: string
  readonly postconditionSha256: string
  readonly postconditionByteLength: number
  readonly member: S2STestOnlyGoldenArtifactReadbackMember
  readonly readArchiveBytes: () => Uint8Array
  readonly readPostconditionArchiveBytes: () => Uint8Array
  readonly readPostconditionDocumentBytes: () => Uint8Array
}

export class S2STestOnlyGoldenArtifactStoreError extends Data.TaggedError(
  "S2STestOnlyGoldenArtifactStoreError"
)<{
  readonly operation: "INITIALIZE" | "PUBLISH" | "READBACK"
  readonly reason:
    | "ROOT_UNSAFE"
    | "PUBLISH_FAILED"
    | "PUBLICATION_OUTCOME_UNKNOWN"
    | "READBACK_FAILED"
    | "READBACK_MISMATCH"
    | "POSTCONDITION_INVALID"
    | "RECOVERY_MISMATCH"
    | "CREATE_ONLY_CONFLICT"
  readonly role: S2STestOnlyGoldenRole | null
  readonly detail: string
}> {}

export class S2STestOnlyGoldenArtifactStore extends Context.Tag(
  "hswm/S2S/TestOnlyGoldenArtifactStore"
)<
  S2STestOnlyGoldenArtifactStore,
  {
    readonly publishGoldenArtifact: (
      role: S2STestOnlyGoldenRole,
      exactMembers: ReadonlyArray<S2STestOnlyGoldenArtifactMemberInput>
    ) => Effect.Effect<
      S2STestOnlyGoldenArtifactPublicationReceipt,
      S2STestOnlyGoldenArtifactStoreError
    >
    readonly readBackGoldenArtifact: (
      receipt: S2STestOnlyGoldenArtifactPublicationReceipt
    ) => Effect.Effect<
      S2STestOnlyGoldenArtifactReadback,
      S2STestOnlyGoldenArtifactStoreError
    >
    readonly recoverGoldenArtifactWithFreshLayer: (
      receipt: S2STestOnlyGoldenArtifactPublicationReceipt
    ) => Effect.Effect<
      S2STestOnlyGoldenArtifactReadback,
      S2STestOnlyGoldenArtifactStoreError
    >
  }
>() {}

interface DirectoryIdentity {
  readonly path: string
  readonly device: number
  readonly inode: number
}

interface ReceiptAuthority {
  readonly root: DirectoryIdentity
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: string
  readonly postconditionPublicationKey: string
  readonly archiveBytes: Uint8Array
  readonly postconditionBytes: Uint8Array
  readonly memberName: string
  readonly memberBytes: Uint8Array
}

const RECEIPT_AUTHORITY = new WeakMap<object, ReceiptAuthority>()

export interface S2STestOnlyGoldenArtifactStorePosixOps {
  readonly lstat: typeof lstat
  readonly open: typeof open
  readonly realpath: (path: string) => Promise<string>
  readonly link: typeof link
  readonly unlink: typeof unlink
  readonly syncDirectory: (path: string) => Promise<void>
}

const syncDirectory = async (path: string): Promise<void> => {
  const handle = await open(
    path,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW
  )
  try {
    await handle.sync()
  } finally {
    await handle.close()
  }
}

const NODE_POSIX_OPS: S2STestOnlyGoldenArtifactStorePosixOps = Object.freeze({
  lstat,
  open,
  realpath,
  link,
  unlink,
  syncDirectory
})

const withPosixOverrides = (
  overrides: Partial<S2STestOnlyGoldenArtifactStorePosixOps>
): S2STestOnlyGoldenArtifactStorePosixOps =>
  Object.freeze({
    lstat: overrides.lstat ?? NODE_POSIX_OPS.lstat,
    open: overrides.open ?? NODE_POSIX_OPS.open,
    realpath: overrides.realpath ?? NODE_POSIX_OPS.realpath,
    link: overrides.link ?? NODE_POSIX_OPS.link,
    unlink: overrides.unlink ?? NODE_POSIX_OPS.unlink,
    syncDirectory:
      overrides.syncDirectory ?? NODE_POSIX_OPS.syncDirectory
  })

const hasErrorCode = (error: unknown): error is { readonly code: string } =>
  typeof error === "object" &&
  error !== null &&
  "code" in error &&
  typeof error.code === "string"

const errorDetail = (error: unknown): string =>
  error instanceof S2STestOnlyGoldenArtifactStoreError
    ? `${error.reason}:${error.detail}`
    : hasErrorCode(error)
      ? error.code
      : "UNKNOWN_FILESYSTEM_ERROR"

const storeError = (
  operation: S2STestOnlyGoldenArtifactStoreError["operation"],
  reason: S2STestOnlyGoldenArtifactStoreError["reason"],
  role: S2STestOnlyGoldenRole | null,
  detail: string
): S2STestOnlyGoldenArtifactStoreError =>
  new S2STestOnlyGoldenArtifactStoreError({
    operation,
    reason,
    role,
    detail
  })

const pureFailureDetail = (
  error: S2STestOnlyGoldenUploadFailure
): string => `${error._tag}:${error.reason}`

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameRoot = (
  left: DirectoryIdentity,
  right: DirectoryIdentity
): boolean =>
  left.path === right.path &&
  left.device === right.device &&
  left.inode === right.inode

const initializeDirectory = async (
  inputRoot: string,
  posix: S2STestOnlyGoldenArtifactStorePosixOps
): Promise<DirectoryIdentity> => {
  if (!isAbsolute(inputRoot)) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      null,
      "golden artifact root must be an absolute caller-owned path"
    )
  }
  const requested = resolve(inputRoot)
  const requestedStat = await posix.lstat(requested)
  if (
    requestedStat.isSymbolicLink() ||
    !requestedStat.isDirectory() ||
    (requestedStat.mode & 0o777) !== 0o700
  ) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      null,
      "golden artifact root must be one plain 0700 directory"
    )
  }
  const canonical = await posix.realpath(requested)
  if (canonical !== requested) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      null,
      "golden artifact root must not traverse a symbolic link"
    )
  }
  const canonicalStat = await posix.lstat(canonical)
  if (
    canonicalStat.isSymbolicLink() ||
    !canonicalStat.isDirectory() ||
    (canonicalStat.mode & 0o777) !== 0o700
  ) {
    throw storeError(
      "INITIALIZE",
      "ROOT_UNSAFE",
      null,
      "canonical golden artifact root must be one plain 0700 directory"
    )
  }
  return Object.freeze({
    path: canonical,
    device: canonicalStat.dev,
    inode: canonicalStat.ino
  })
}

const initializeError = (
  error: unknown
): S2STestOnlyGoldenArtifactStoreError =>
  error instanceof S2STestOnlyGoldenArtifactStoreError
    ? error
    : storeError(
        "INITIALIZE",
        "ROOT_UNSAFE",
        null,
        `golden artifact root inspection failed: ${errorDetail(error)}`
      )

const assertDirectoryIdentity = async (
  identity: DirectoryIdentity,
  posix: S2STestOnlyGoldenArtifactStorePosixOps,
  operation: "PUBLISH" | "READBACK",
  role: S2STestOnlyGoldenRole
): Promise<void> => {
  const current = await posix.lstat(identity.path)
  if (
    current.isSymbolicLink() ||
    !current.isDirectory() ||
    current.dev !== identity.device ||
    current.ino !== identity.inode ||
    (current.mode & 0o777) !== 0o700
  ) {
    throw storeError(
      operation,
      operation === "PUBLISH" ? "PUBLISH_FAILED" : "READBACK_FAILED",
      role,
      "golden artifact root identity or permissions changed"
    )
  }
}

const readBoundedRegularFile = async (input: {
  readonly identity: DirectoryIdentity
  readonly posix: S2STestOnlyGoldenArtifactStorePosixOps
  readonly path: string
  readonly maximumBytes: number
  readonly operation: "PUBLISH" | "READBACK"
  readonly role: S2STestOnlyGoldenRole
}): Promise<Uint8Array> => {
  await assertDirectoryIdentity(
    input.identity,
    input.posix,
    input.operation,
    input.role
  )
  let handle
  try {
    handle = await input.posix.open(
      input.path,
      constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK
    )
  } catch (error) {
    throw storeError(
      input.operation,
      "READBACK_FAILED",
      input.role,
      `golden artifact open failed: ${errorDetail(error)}`
    )
  }
  try {
    const before = await handle.stat()
    if (!before.isFile() || (before.mode & 0o777) !== 0o400) {
      throw storeError(
        input.operation,
        "READBACK_FAILED",
        input.role,
        "golden artifact entry must be one plain 0400 regular file"
      )
    }
    if (before.size < 1 || before.size > input.maximumBytes) {
      throw storeError(
        input.operation,
        "READBACK_FAILED",
        input.role,
        "golden artifact entry violates its fixed byte bound"
      )
    }
    const bounded = Buffer.alloc(before.size + 1)
    let total = 0
    while (total < bounded.byteLength) {
      const result = await handle.read(
        bounded,
        total,
        bounded.byteLength - total,
        total
      )
      if (result.bytesRead === 0) break
      total += result.bytesRead
    }
    const after = await handle.stat()
    if (
      after.dev !== before.dev ||
      after.ino !== before.ino ||
      after.size !== before.size ||
      after.mode !== before.mode ||
      total !== before.size
    ) {
      throw storeError(
        input.operation,
        "READBACK_FAILED",
        input.role,
        "golden artifact entry changed during bounded read"
      )
    }
    return Uint8Array.from(bounded.subarray(0, total))
  } catch (error) {
    throw error instanceof S2STestOnlyGoldenArtifactStoreError
      ? error
      : storeError(
          input.operation,
          "READBACK_FAILED",
          input.role,
          `golden artifact read failed: ${errorDetail(error)}`
        )
  } finally {
    await handle.close()
  }
}

const destinationExists = async (
  path: string,
  posix: S2STestOnlyGoldenArtifactStorePosixOps
): Promise<boolean> => {
  try {
    await posix.lstat(path)
    return true
  } catch (error) {
    if (hasErrorCode(error) && error.code === "ENOENT") return false
    throw error
  }
}

const publishCreateOnly = async (input: {
  readonly identity: DirectoryIdentity
  readonly posix: S2STestOnlyGoldenArtifactStorePosixOps
  readonly role: S2STestOnlyGoldenRole
  readonly finalName: string
  readonly bytes: Uint8Array
  readonly maximumBytes: number
}): Promise<void> => {
  const bytes = Uint8Array.from(input.bytes)
  if (bytes.byteLength < 1 || bytes.byteLength > input.maximumBytes) {
    throw storeError(
      "PUBLISH",
      "PUBLISH_FAILED",
      input.role,
      "golden artifact publication violates its fixed byte bound"
    )
  }
  await assertDirectoryIdentity(
    input.identity,
    input.posix,
    "PUBLISH",
    input.role
  )
  const finalPath = join(input.identity.path, input.finalName)
  let alreadyExists: boolean
  try {
    alreadyExists = await destinationExists(finalPath, input.posix)
  } catch (error) {
    throw storeError(
      "PUBLISH",
      "PUBLISH_FAILED",
      input.role,
      `create-only destination inspection failed: ${errorDetail(error)}`
    )
  }
  if (alreadyExists) {
    throw storeError(
      "PUBLISH",
      "CREATE_ONLY_CONFLICT",
      input.role,
      `create-only destination already exists: ${input.finalName}`
    )
  }

  const temporaryPath = join(
    input.identity.path,
    `.s2s-test-only-golden-${randomUUID()}.tmp`
  )
  let temporaryCreated = false
  try {
    let handle
    try {
      handle = await input.posix.open(
        temporaryPath,
        constants.O_WRONLY |
          constants.O_CREAT |
          constants.O_EXCL |
          constants.O_NOFOLLOW,
        0o600
      )
      temporaryCreated = true
      try {
        await handle.writeFile(bytes)
        await handle.chmod(0o400)
        await handle.sync()
      } finally {
        await handle.close()
      }
    } catch (error) {
      throw storeError(
        "PUBLISH",
        "PUBLISH_FAILED",
        input.role,
        `temporary publication failed: ${errorDetail(error)}`
      )
    }

    try {
      await input.posix.link(temporaryPath, finalPath)
    } catch (error) {
      if (hasErrorCode(error) && error.code === "EEXIST") {
        throw storeError(
          "PUBLISH",
          "CREATE_ONLY_CONFLICT",
          input.role,
          `create-only destination won a concurrent race: ${input.finalName}`
        )
      }
      let observed = false
      try {
        observed = await destinationExists(finalPath, input.posix)
      } catch {
        throw storeError(
          "PUBLISH",
          "PUBLICATION_OUTCOME_UNKNOWN",
          input.role,
          `link failed and destination could not be reconciled: ${errorDetail(error)}`
        )
      }
      throw storeError(
        "PUBLISH",
        observed ? "PUBLICATION_OUTCOME_UNKNOWN" : "PUBLISH_FAILED",
        input.role,
        `single create-only link failed: ${errorDetail(error)}`
      )
    }

    try {
      await assertDirectoryIdentity(
        input.identity,
        input.posix,
        "PUBLISH",
        input.role
      )
      await input.posix.syncDirectory(input.identity.path)
    } catch (error) {
      throw storeError(
        "PUBLISH",
        "PUBLICATION_OUTCOME_UNKNOWN",
        input.role,
        `directory durability is unknown after link: ${errorDetail(error)}`
      )
    }
  } finally {
    if (temporaryCreated) {
      try {
        await input.posix.unlink(temporaryPath)
      } catch {
        // A stale private temp does not name either fixed publication key.
      }
    }
  }
}

const exactMemberSnapshot = (
  role: S2STestOnlyGoldenRole,
  exactMembers: ReadonlyArray<S2STestOnlyGoldenArtifactMemberInput>
): Either.Either<
  { readonly name: string; readonly bytes: Uint8Array },
  S2STestOnlyGoldenArtifactStoreError
> => {
  try {
    const member = exactMembers[0]
    const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[role]
    if (
      exactMembers.length !== 1 ||
      member === undefined ||
      member.name !== spec.memberName ||
      !(member.bytes instanceof Uint8Array)
    ) {
      return Either.left(
        storeError(
          "PUBLISH",
          "PUBLISH_FAILED",
          role,
          "golden artifact members do not match the fixed singleton roster"
        )
      )
    }
    return Either.right(
      Object.freeze({ name: member.name, bytes: Uint8Array.from(member.bytes) })
    )
  } catch {
    return Either.left(
      storeError(
        "PUBLISH",
        "PUBLISH_FAILED",
        role,
        "golden artifact members could not be snapshotted safely"
      )
    )
  }
}

const makeReceipt = (input: {
  readonly root: DirectoryIdentity
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: string
  readonly postconditionPublicationKey: string
  readonly archiveBytes: Uint8Array
  readonly postconditionBytes: Uint8Array
  readonly memberName: string
  readonly memberBytes: Uint8Array
}): S2STestOnlyGoldenArtifactPublicationReceipt => {
  const archiveBytes = Uint8Array.from(input.archiveBytes)
  const postconditionBytes = Uint8Array.from(input.postconditionBytes)
  const memberBytes = Uint8Array.from(input.memberBytes)
  const receipt = Object.freeze({
    _tag: "S2STestOnlyGoldenArtifactPublicationReceipt" as const,
    classification: "TEST_ONLY_NON_AUTHORIZING" as const,
    origin: "LOCAL_TEST_LAYER" as const,
    role: input.role,
    publicationKey: input.publicationKey,
    disposition: "CREATED" as const,
    archiveSha256: rawS2SFileSha256(archiveBytes),
    archiveByteLength: archiveBytes.byteLength,
    postconditionPublicationKey: input.postconditionPublicationKey,
    postconditionSha256: rawS2SFileSha256(postconditionBytes),
    postconditionByteLength: postconditionBytes.byteLength,
    readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes)
  })
  RECEIPT_AUTHORITY.set(
    receipt,
    Object.freeze({
      root: input.root,
      role: input.role,
      publicationKey: input.publicationKey,
      postconditionPublicationKey: input.postconditionPublicationKey,
      archiveBytes,
      postconditionBytes,
      memberName: input.memberName,
      memberBytes
    })
  )
  return receipt
}

const authenticReceipt = (
  root: DirectoryIdentity,
  input: S2STestOnlyGoldenArtifactPublicationReceipt
): Either.Either<ReceiptAuthority, S2STestOnlyGoldenArtifactStoreError> => {
  const authority =
    input !== null && typeof input === "object"
      ? RECEIPT_AUTHORITY.get(input)
      : undefined
  if (authority === undefined) {
    return Either.left(
      storeError(
        "READBACK",
        "READBACK_FAILED",
        null,
        "readback requires one module-issued receipt bound to this exact root"
      )
    )
  }
  if (!sameRoot(root, authority.root)) {
    return Either.left(
      storeError(
        "READBACK",
        "RECOVERY_MISMATCH",
        authority.role,
        "module-issued receipt belongs to a different root identity"
      )
    )
  }
  const archiveSha256 = rawS2SFileSha256(authority.archiveBytes)
  const postconditionSha256 = rawS2SFileSha256(authority.postconditionBytes)
  if (
    input._tag !== "S2STestOnlyGoldenArtifactPublicationReceipt" ||
    input.classification !== "TEST_ONLY_NON_AUTHORIZING" ||
    input.origin !== "LOCAL_TEST_LAYER" ||
    input.role !== authority.role ||
    input.publicationKey !== authority.publicationKey ||
    input.disposition !== "CREATED" ||
    input.archiveSha256 !== archiveSha256 ||
    input.archiveByteLength !== authority.archiveBytes.byteLength ||
    input.postconditionPublicationKey !==
      authority.postconditionPublicationKey ||
    input.postconditionSha256 !== postconditionSha256 ||
    input.postconditionByteLength !== authority.postconditionBytes.byteLength
  ) {
    return Either.left(
      storeError(
        "READBACK",
        "READBACK_FAILED",
        authority.role,
        "module-issued receipt surface diverges from its hidden binding"
      )
    )
  }
  return Either.right(authority)
}

const makeReadback = (input: {
  readonly authority: ReceiptAuthority
  readonly archiveBytes: Uint8Array
  readonly postconditionBytes: Uint8Array
  readonly postconditionDocumentBytes: Uint8Array
  readonly memberName: string
  readonly memberBytes: Uint8Array
}): S2STestOnlyGoldenArtifactReadback => {
  const archiveBytes = Uint8Array.from(input.archiveBytes)
  const postconditionBytes = Uint8Array.from(input.postconditionBytes)
  const postconditionDocumentBytes = Uint8Array.from(
    input.postconditionDocumentBytes
  )
  const memberBytes = Uint8Array.from(input.memberBytes)
  const member = Object.freeze({
    name: input.memberName,
    rawSha256: rawS2SFileSha256(memberBytes),
    byteLength: memberBytes.byteLength,
    readBytes: (): Uint8Array => Uint8Array.from(memberBytes)
  })
  return Object.freeze({
    _tag: "S2STestOnlyGoldenArtifactReadback" as const,
    classification: "TEST_ONLY_NON_AUTHORIZING" as const,
    origin: "LOCAL_TEST_LAYER" as const,
    role: input.authority.role,
    publicationKey: input.authority.publicationKey,
    archiveSha256: rawS2SFileSha256(archiveBytes),
    archiveByteLength: archiveBytes.byteLength,
    postconditionPublicationKey:
      input.authority.postconditionPublicationKey,
    postconditionSha256: rawS2SFileSha256(postconditionBytes),
    postconditionByteLength: postconditionBytes.byteLength,
    member,
    readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes),
    readPostconditionArchiveBytes: (): Uint8Array =>
      Uint8Array.from(postconditionBytes),
    readPostconditionDocumentBytes: (): Uint8Array =>
      Uint8Array.from(postconditionDocumentBytes)
  })
}

const publishGolden = (
  root: DirectoryIdentity,
  posix: S2STestOnlyGoldenArtifactStorePosixOps,
  role: S2STestOnlyGoldenRole,
  inputMembers: ReadonlyArray<S2STestOnlyGoldenArtifactMemberInput>
): Effect.Effect<
  S2STestOnlyGoldenArtifactPublicationReceipt,
  S2STestOnlyGoldenArtifactStoreError
> =>
  Effect.gen(function* () {
    const member = exactMemberSnapshot(role, inputMembers)
    if (Either.isLeft(member)) return yield* member.left
    const artifact = buildS2STestOnlyGoldenArtifact(role, [member.right])
    if (Either.isLeft(artifact)) {
      return yield* storeError(
        "PUBLISH",
        "PUBLISH_FAILED",
        role,
        pureFailureDetail(artifact.left)
      )
    }
    const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[role]
    const archiveBytes = artifact.right.readArchiveBytes()
    yield* Effect.tryPromise({
      try: () =>
        publishCreateOnly({
          identity: root,
          posix,
          role,
          finalName: spec.publicationKey,
          bytes: archiveBytes,
          maximumBytes: spec.archiveMaximumBytes
        }),
      catch: (error) =>
        error instanceof S2STestOnlyGoldenArtifactStoreError
          ? error
          : storeError(
              "PUBLISH",
              "PUBLISH_FAILED",
              role,
              errorDetail(error)
            )
    })
    const artifactReadbackBytes = yield* Effect.tryPromise({
      try: () =>
        readBoundedRegularFile({
          identity: root,
          posix,
          path: join(root.path, spec.publicationKey),
          maximumBytes: spec.archiveMaximumBytes,
          operation: "PUBLISH",
          role
        }),
      catch: (error) =>
        error instanceof S2STestOnlyGoldenArtifactStoreError
          ? error
          : storeError(
              "PUBLISH",
              "READBACK_FAILED",
              role,
              errorDetail(error)
            )
    })
    const validated = validateS2STestOnlyGoldenArtifactReadback(
      role,
      archiveBytes,
      artifactReadbackBytes
    )
    if (Either.isLeft(validated)) {
      return yield* storeError(
        "PUBLISH",
        "READBACK_MISMATCH",
        role,
        pureFailureDetail(validated.left)
      )
    }
    const postcondition = buildS2STestOnlyGoldenUploadPostcondition({
      role,
      publicationKey: spec.publicationKey,
      publicationDisposition: "CREATED",
      archiveBytes,
      readbackBytes: artifactReadbackBytes
    })
    if (Either.isLeft(postcondition)) {
      return yield* storeError(
        "PUBLISH",
        "POSTCONDITION_INVALID",
        role,
        pureFailureDetail(postcondition.left)
      )
    }
    const postconditionBytes = postcondition.right.readArchiveBytes()
    yield* Effect.tryPromise({
      try: () =>
        publishCreateOnly({
          identity: root,
          posix,
          role,
          finalName: spec.postconditionPublicationKey,
          bytes: postconditionBytes,
          maximumBytes:
            S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES
        }),
      catch: (error) =>
        error instanceof S2STestOnlyGoldenArtifactStoreError
          ? error
          : storeError(
              "PUBLISH",
              "PUBLISH_FAILED",
              role,
              errorDetail(error)
            )
    })
    const postconditionReadbackBytes = yield* Effect.tryPromise({
      try: () =>
        readBoundedRegularFile({
          identity: root,
          posix,
          path: join(root.path, spec.postconditionPublicationKey),
          maximumBytes:
            S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES,
          operation: "PUBLISH",
          role
        }),
      catch: (error) =>
        error instanceof S2STestOnlyGoldenArtifactStoreError
          ? error
          : storeError(
              "PUBLISH",
              "READBACK_FAILED",
              role,
              errorDetail(error)
            )
    })
    const reconstructed = reconstructS2STestOnlyGoldenUploadPostcondition(
      postconditionReadbackBytes,
      {
        role,
        publicationKey: spec.publicationKey,
        publicationDisposition: "CREATED",
        archiveBytes,
        readbackBytes: artifactReadbackBytes
      }
    )
    if (Either.isLeft(reconstructed)) {
      return yield* storeError(
        "PUBLISH",
        "POSTCONDITION_INVALID",
        role,
        pureFailureDetail(reconstructed.left)
      )
    }
    return makeReceipt({
      root,
      role,
      publicationKey: spec.publicationKey,
      postconditionPublicationKey: spec.postconditionPublicationKey,
      archiveBytes,
      postconditionBytes: postconditionReadbackBytes,
      memberName: member.right.name,
      memberBytes: member.right.bytes
    })
  }).pipe(Effect.uninterruptible)

const readBackGolden = (
  root: DirectoryIdentity,
  posix: S2STestOnlyGoldenArtifactStorePosixOps,
  receipt: S2STestOnlyGoldenArtifactPublicationReceipt
): Effect.Effect<
  S2STestOnlyGoldenArtifactReadback,
  S2STestOnlyGoldenArtifactStoreError
> =>
  Effect.gen(function* () {
    const authenticated = authenticReceipt(root, receipt)
    if (Either.isLeft(authenticated)) return yield* authenticated.left
    const authority = authenticated.right
    const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[authority.role]
    const archiveBytes = yield* Effect.tryPromise({
      try: () =>
        readBoundedRegularFile({
          identity: root,
          posix,
          path: join(root.path, authority.publicationKey),
          maximumBytes: spec.archiveMaximumBytes,
          operation: "READBACK",
          role: authority.role
        }),
      catch: (error) =>
        error instanceof S2STestOnlyGoldenArtifactStoreError
          ? error
          : storeError(
              "READBACK",
              "READBACK_FAILED",
              authority.role,
              errorDetail(error)
            )
    })
    if (!sameBytes(archiveBytes, authority.archiveBytes)) {
      return yield* storeError(
        "READBACK",
        "READBACK_MISMATCH",
        authority.role,
        "independently read artifact differs from the module-issued receipt"
      )
    }
    const validated = validateS2STestOnlyGoldenArtifactReadback(
      authority.role,
      authority.archiveBytes,
      archiveBytes
    )
    if (Either.isLeft(validated)) {
      return yield* storeError(
        "READBACK",
        "READBACK_MISMATCH",
        authority.role,
        pureFailureDetail(validated.left)
      )
    }
    const postconditionBytes = yield* Effect.tryPromise({
      try: () =>
        readBoundedRegularFile({
          identity: root,
          posix,
          path: join(root.path, authority.postconditionPublicationKey),
          maximumBytes:
            S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES,
          operation: "READBACK",
          role: authority.role
        }),
      catch: (error) =>
        error instanceof S2STestOnlyGoldenArtifactStoreError
          ? error
          : storeError(
              "READBACK",
              "READBACK_FAILED",
              authority.role,
              errorDetail(error)
            )
    })
    if (!sameBytes(postconditionBytes, authority.postconditionBytes)) {
      return yield* storeError(
        "READBACK",
        "READBACK_MISMATCH",
        authority.role,
        "independently read postcondition differs from its issued receipt"
      )
    }
    const reconstructed = reconstructS2STestOnlyGoldenUploadPostcondition(
      postconditionBytes,
      {
        role: authority.role,
        publicationKey: authority.publicationKey,
        publicationDisposition: "CREATED",
        archiveBytes: authority.archiveBytes,
        readbackBytes: archiveBytes
      }
    )
    if (Either.isLeft(reconstructed)) {
      return yield* storeError(
        "READBACK",
        "POSTCONDITION_INVALID",
        authority.role,
        pureFailureDetail(reconstructed.left)
      )
    }
    return makeReadback({
      authority,
      archiveBytes,
      postconditionBytes,
      postconditionDocumentBytes: reconstructed.right.readDocumentBytes(),
      memberName: validated.right.members[0].name,
      memberBytes: validated.right.members[0].readBytes()
    })
  })

const makeLayer = (
  directory: string,
  posix: S2STestOnlyGoldenArtifactStorePosixOps
): Layer.Layer<
  S2STestOnlyGoldenArtifactStore,
  S2STestOnlyGoldenArtifactStoreError
> =>
  Layer.effect(
    S2STestOnlyGoldenArtifactStore,
    Effect.gen(function* () {
      const identity = yield* Effect.tryPromise({
        try: () => initializeDirectory(directory, posix),
        catch: initializeError
      }).pipe(Effect.uninterruptible)
      const mutex = yield* Effect.makeSemaphore(1)
      return S2STestOnlyGoldenArtifactStore.of({
        publishGoldenArtifact: (role, exactMembers) =>
          mutex.withPermits(1)(
            Effect.suspend(() =>
              publishGolden(identity, posix, role, exactMembers)
            )
          ),
        readBackGoldenArtifact: (receipt) =>
          mutex.withPermits(1)(
            Effect.suspend(() =>
              readBackGolden(identity, posix, receipt)
            )
          ),
        recoverGoldenArtifactWithFreshLayer: (receipt) =>
          Effect.suspend(() =>
            Effect.gen(function* () {
              const freshStore = yield* S2STestOnlyGoldenArtifactStore
              return yield* freshStore.readBackGoldenArtifact(receipt)
            }).pipe(Effect.provide(makeLayer(identity.path, posix)))
          )
      })
    })
  )

/**
 * Root-private local POSIX test adapter. `directory` must already be one
 * caller-owned absolute 0700 directory. It is intentionally not exported from
 * the package root and does not represent GitHub or shared durable storage.
 */
export const makeS2STestOnlyGoldenArtifactStoreFileLayer = (
  callerOwnedTemporaryRoot: string
) => makeLayer(callerOwnedTemporaryRoot, NODE_POSIX_OPS)

/** Deterministic fault-injection seam for this root-private adapter's tests. */
export const makeS2STestOnlyGoldenArtifactStoreFileLayerWithPosixForTest = (
  callerOwnedTemporaryRoot: string,
  overrides: Partial<S2STestOnlyGoldenArtifactStorePosixOps>
) => makeLayer(callerOwnedTemporaryRoot, withPosixOverrides(overrides))
