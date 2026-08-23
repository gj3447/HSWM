import { types as nodeTypes } from "node:util"

import { Data, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256,
  type S2SCanonicalJsonError
} from "./s2s-canonical.js"
import { S2SSha256Schema } from "./s2s-confirmatory.js"
import {
  S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
  S2S_NUMERIC_CANDIDATE_MAX_BYTES
} from "./s2s-live-python.js"
import {
  buildS2SStoredZip,
  validateS2SArtifactZip,
  type S2SArtifactZipValidationError,
  type S2SStoredZipBuildError
} from "./s2s-zip.js"

const MEBIBYTE = 1_048_576

export const S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION =
  "hswm-swm0w-s2s-test-only-golden-upload-postcondition/v1" as const
export const S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME =
  "postcondition.json" as const
export const S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_MAX_BYTES = 4 * 1_024
export const S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES = 8 * 1_024

export const S2STestOnlyGoldenRoleSchema = Schema.Literal(
  "GOLDEN_CANDIDATE",
  "GOLDEN_ADJUDICATION"
)

export type S2STestOnlyGoldenRole = Schema.Schema.Type<
  typeof S2STestOnlyGoldenRoleSchema
>

export type S2STestOnlyGoldenMemberName =
  | "numeric_candidate.json"
  | "numeric_adjudication.json"

export type S2STestOnlyGoldenPublicationKey =
  | "s2s-test-only-golden-candidate.zip"
  | "s2s-test-only-golden-adjudication.zip"

export type S2STestOnlyGoldenPostconditionPublicationKey =
  | "s2s-test-only-golden-candidate-upload-postcondition.zip"
  | "s2s-test-only-golden-adjudication-upload-postcondition.zip"

export interface S2STestOnlyGoldenArtifactSpec {
  readonly publicationKey: S2STestOnlyGoldenPublicationKey
  readonly postconditionPublicationKey: S2STestOnlyGoldenPostconditionPublicationKey
  readonly memberName: S2STestOnlyGoldenMemberName
  readonly memberMaximumBytes: number
  readonly archiveMaximumBytes: number
  readonly expandedMaximumBytes: number
}

export const S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS: Readonly<
  Record<S2STestOnlyGoldenRole, S2STestOnlyGoldenArtifactSpec>
> = Object.freeze({
  GOLDEN_CANDIDATE: Object.freeze({
    publicationKey: "s2s-test-only-golden-candidate.zip",
    postconditionPublicationKey:
      "s2s-test-only-golden-candidate-upload-postcondition.zip",
    memberName: "numeric_candidate.json",
    memberMaximumBytes: S2S_NUMERIC_CANDIDATE_MAX_BYTES,
    archiveMaximumBytes: 64 * MEBIBYTE,
    expandedMaximumBytes: S2S_NUMERIC_CANDIDATE_MAX_BYTES
  }),
  GOLDEN_ADJUDICATION: Object.freeze({
    publicationKey: "s2s-test-only-golden-adjudication.zip",
    postconditionPublicationKey:
      "s2s-test-only-golden-adjudication-upload-postcondition.zip",
    memberName: "numeric_adjudication.json",
    memberMaximumBytes: S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
    archiveMaximumBytes: 4 * MEBIBYTE,
    expandedMaximumBytes: S2S_NUMERIC_ADJUDICATION_MAX_BYTES
  })
})

export interface S2STestOnlyGoldenArtifactMemberInput {
  readonly name: S2STestOnlyGoldenMemberName
  readonly bytes: Uint8Array
}

export interface S2STestOnlyGoldenMemberSnapshot {
  readonly name: S2STestOnlyGoldenMemberName
  readonly byteLength: number
  readonly rawBytesSha256: string
  readonly readBytes: () => Uint8Array
}

export interface S2STestOnlyGoldenArtifactSnapshot {
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: S2STestOnlyGoldenPublicationKey
  readonly postconditionPublicationKey: S2STestOnlyGoldenPostconditionPublicationKey
  readonly archiveByteLength: number
  readonly archiveRawSha256: string
  readonly members: readonly [S2STestOnlyGoldenMemberSnapshot]
  readonly readArchiveBytes: () => Uint8Array
}

export interface S2STestOnlyGoldenArtifactReadback {
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: S2STestOnlyGoldenPublicationKey
  readonly postconditionPublicationKey: S2STestOnlyGoldenPostconditionPublicationKey
  readonly archiveByteLength: number
  readonly archiveRawSha256: string
  readonly readbackByteLength: number
  readonly readbackRawSha256: string
  readonly archiveReadbackBytesEqual: true
  readonly members: readonly [S2STestOnlyGoldenMemberSnapshot]
  readonly readArchiveBytes: () => Uint8Array
  readonly readReadbackBytes: () => Uint8Array
}

export interface S2STestOnlyGoldenPostconditionMemberDocument {
  readonly name: S2STestOnlyGoldenMemberName
  readonly raw_bytes_sha256: string
  readonly byte_length: number
}

export interface S2STestOnlyGoldenUploadPostconditionDocument {
  readonly schema_version: typeof S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly origin: "LOCAL_TEST_LAYER"
  readonly role: S2STestOnlyGoldenRole
  readonly publication_key: S2STestOnlyGoldenPublicationKey
  readonly publication_disposition: "CREATED"
  readonly archive_raw_sha256: string
  readonly archive_byte_length: number
  readonly readback_raw_sha256: string
  readonly readback_byte_length: number
  readonly archive_readback_bytes_equal: true
  readonly members: readonly [S2STestOnlyGoldenPostconditionMemberDocument]
  readonly receipt_sha256: string
}

export interface S2STestOnlyGoldenUploadPostconditionSnapshot {
  readonly document: S2STestOnlyGoldenUploadPostconditionDocument
  readonly documentByteLength: number
  readonly documentRawSha256: string
  readonly archiveByteLength: number
  readonly archiveRawSha256: string
  readonly readDocumentBytes: () => Uint8Array
  readonly readArchiveBytes: () => Uint8Array
}

export class S2STestOnlyGoldenUploadError extends Data.TaggedError(
  "S2STestOnlyGoldenUploadError"
)<{
  readonly operation:
    | "BUILD_ARTIFACT"
    | "VALIDATE_READBACK"
    | "BUILD_POSTCONDITION"
    | "RECONSTRUCT_POSTCONDITION"
  readonly role: S2STestOnlyGoldenRole | null
  readonly reason:
    | "ARCHIVE_NOT_DETERMINISTIC"
    | "ARCHIVE_READBACK_MISMATCH"
    | "CROSS_BINDING_MISMATCH"
    | "INPUT_INVALID"
    | "MEMBER_BINDING_MISMATCH"
    | "MEMBER_ROSTER_MISMATCH"
    | "POSTCONDITION_NOT_CANONICAL"
    | "POSTCONDITION_PARSE_FAILED"
    | "POSTCONDITION_SCHEMA_REJECTED"
    | "PUBLICATION_DISPOSITION_INVALID"
    | "PUBLICATION_KEY_MISMATCH"
    | "RECEIPT_HASH_MISMATCH"
    | "ROLE_INVALID"
  readonly detail: string
}> {}

export type S2STestOnlyGoldenUploadFailure =
  | S2STestOnlyGoldenUploadError
  | S2SCanonicalJsonError
  | S2SStoredZipBuildError
  | S2SArtifactZipValidationError

type S2STestOnlyGoldenUploadOperation =
  S2STestOnlyGoldenUploadError["operation"]

interface SnapshottedMemberInput {
  readonly name: S2STestOnlyGoldenMemberName
  readonly bytes: Uint8Array
}

interface ValidatedRoleArchive {
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: S2STestOnlyGoldenPublicationKey
  readonly postconditionPublicationKey: S2STestOnlyGoldenPostconditionPublicationKey
  readonly archiveByteLength: number
  readonly archiveRawSha256: string
  readonly member: S2STestOnlyGoldenMemberSnapshot
  readonly bytes: Uint8Array
}

const Sha256TextSchema = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}$/)
)

const PositiveArtifactByteLengthSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, 64 * MEBIBYTE)
)

const PostconditionMemberDocumentSchema = Schema.Struct({
  name: Schema.Literal("numeric_candidate.json", "numeric_adjudication.json"),
  raw_bytes_sha256: Sha256TextSchema,
  byte_length: Schema.Number.pipe(
    Schema.int(),
    Schema.between(1, S2S_NUMERIC_CANDIDATE_MAX_BYTES)
  )
})

const PostconditionDocumentSchema = Schema.Struct({
  schema_version: Schema.Literal(
    S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION
  ),
  classification: Schema.Literal("TEST_ONLY_NON_AUTHORIZING"),
  origin: Schema.Literal("LOCAL_TEST_LAYER"),
  role: S2STestOnlyGoldenRoleSchema,
  publication_key: Schema.Literal(
    "s2s-test-only-golden-candidate.zip",
    "s2s-test-only-golden-adjudication.zip"
  ),
  publication_disposition: Schema.Literal("CREATED"),
  archive_raw_sha256: Sha256TextSchema,
  archive_byte_length: PositiveArtifactByteLengthSchema,
  readback_raw_sha256: Sha256TextSchema,
  readback_byte_length: PositiveArtifactByteLengthSchema,
  archive_readback_bytes_equal: Schema.Literal(true),
  members: Schema.Tuple(PostconditionMemberDocumentSchema),
  receipt_sha256: Sha256TextSchema
})

const uploadError = (
  operation: S2STestOnlyGoldenUploadOperation,
  role: S2STestOnlyGoldenRole | null,
  reason: S2STestOnlyGoldenUploadError["reason"],
  detail: string
): S2STestOnlyGoldenUploadError =>
  new S2STestOnlyGoldenUploadError({ operation, role, reason, detail })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const singleFrozenTuple = <A>(value: A): readonly [A] =>
  Object.freeze([value])

const decodeRole = (
  input: unknown,
  operation: S2STestOnlyGoldenUploadOperation
): Either.Either<S2STestOnlyGoldenRole, S2STestOnlyGoldenUploadError> => {
  const decoded = Schema.decodeUnknownEither(S2STestOnlyGoldenRoleSchema)(input)
  return Either.isLeft(decoded)
    ? Either.left(
        uploadError(
          operation,
          null,
          "ROLE_INVALID",
          "golden role must be one fixed test-only role"
        )
      )
    : Either.right(decoded.right)
}

const exactPlainRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      nodeTypes.isProxy(input)
    ) {
      return null
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) return null
    if (Object.getOwnPropertySymbols(input).length !== 0) return null
    const keys = Object.getOwnPropertyNames(input).sort()
    const expected = [...expectedKeys].sort()
    if (
      keys.length !== expected.length ||
      keys.some((key, index) => key !== expected[index])
    ) {
      return null
    }
    const snapshot: Record<string, unknown> = Object.create(null)
    for (const key of expected) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      snapshot[key] = descriptor.value
    }
    return Object.freeze(snapshot)
  } catch {
    return null
  }
}

const snapshotPlainBytes = (
  input: unknown,
  maximumBytes: number
): Uint8Array | null => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      nodeTypes.isProxy(input) ||
      !(input instanceof Uint8Array) ||
      Object.getPrototypeOf(input) !== Uint8Array.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0 ||
      Object.getOwnPropertyDescriptor(input, "byteLength") !== undefined ||
      Object.getOwnPropertyDescriptor(input, "buffer") !== undefined ||
      (typeof SharedArrayBuffer !== "undefined" &&
        input.buffer instanceof SharedArrayBuffer) ||
      input.byteLength < 1 ||
      input.byteLength > maximumBytes
    ) {
      return null
    }
    const snapshot = Uint8Array.from(input)
    return snapshot.byteLength === input.byteLength ? snapshot : null
  } catch {
    return null
  }
}

const snapshotExactMembers = (
  input: unknown,
  role: S2STestOnlyGoldenRole
): Either.Either<SnapshottedMemberInput, S2STestOnlyGoldenUploadError> => {
  const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[role]
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      nodeTypes.isProxy(input) ||
      !Array.isArray(input) ||
      Object.getPrototypeOf(input) !== Array.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0
    ) {
      return Either.left(
        uploadError(
          "BUILD_ARTIFACT",
          role,
          "INPUT_INVALID",
          "exact members must be one plain dense array"
        )
      )
    }
    const lengthDescriptor = Object.getOwnPropertyDescriptor(input, "length")
    const entryDescriptor = Object.getOwnPropertyDescriptor(input, "0")
    if (
      lengthDescriptor === undefined ||
      !("value" in lengthDescriptor) ||
      lengthDescriptor.value !== 1 ||
      entryDescriptor === undefined ||
      entryDescriptor.enumerable !== true ||
      !("value" in entryDescriptor) ||
      Object.getOwnPropertyNames(input).sort().join("\u0000") !== "0\u0000length"
    ) {
      return Either.left(
        uploadError(
          "BUILD_ARTIFACT",
          role,
          "MEMBER_ROSTER_MISMATCH",
          "golden artifact must contain exactly one role-owned member"
        )
      )
    }
    const member = exactPlainRecord(entryDescriptor.value, ["bytes", "name"])
    if (member === null) {
      return Either.left(
        uploadError(
          "BUILD_ARTIFACT",
          role,
          "INPUT_INVALID",
          "golden member must be one exact plain data record"
        )
      )
    }
    if (member["name"] !== spec.memberName) {
      return Either.left(
        uploadError(
          "BUILD_ARTIFACT",
          role,
          "MEMBER_ROSTER_MISMATCH",
          "golden member name disagrees with its role"
        )
      )
    }
    const bytes = snapshotPlainBytes(
      member["bytes"],
      spec.memberMaximumBytes
    )
    if (bytes === null) {
      return Either.left(
        uploadError(
          "BUILD_ARTIFACT",
          role,
          "INPUT_INVALID",
          "golden member bytes violate the plain bounded byte contract"
        )
      )
    }
    return Either.right(Object.freeze({ name: spec.memberName, bytes }))
  } catch {
    return Either.left(
      uploadError(
        "BUILD_ARTIFACT",
        role,
        "INPUT_INVALID",
        "golden member roster could not be inspected safely"
      )
    )
  }
}

const validateRoleArchive = (
  role: S2STestOnlyGoldenRole,
  input: unknown,
  operation: S2STestOnlyGoldenUploadOperation
): Either.Either<ValidatedRoleArchive, S2STestOnlyGoldenUploadFailure> => {
  const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[role]
  const bytes = snapshotPlainBytes(input, spec.archiveMaximumBytes)
  if (bytes === null) {
    return Either.left(
      uploadError(
        operation,
        role,
        "INPUT_INVALID",
        "golden archive must be one plain bounded byte array"
      )
    )
  }
  const rawSha256 = S2SSha256Schema.make(rawS2SFileSha256(bytes))
  const validated = validateS2SArtifactZip(bytes, {
    expectedArchiveSha256: rawSha256,
    expectedArchiveByteLength: bytes.byteLength,
    expectedMembers: [
      { name: spec.memberName, maximumBytes: spec.memberMaximumBytes }
    ],
    maximumArchiveBytes: spec.archiveMaximumBytes,
    maximumExpandedBytes: spec.expandedMaximumBytes
  })
  if (Either.isLeft(validated)) return Either.left(validated.left)
  const member = validated.right.members[0]
  if (
    validated.right.members.length !== 1 ||
    member === undefined ||
    member.name !== spec.memberName ||
    member.byteLength < 1 ||
    member.byteLength > spec.memberMaximumBytes
  ) {
    return Either.left(
      uploadError(
        operation,
        role,
        "MEMBER_ROSTER_MISMATCH",
        "validated archive disagrees with the exact role roster"
      )
    )
  }
  const memberBytes = member.readBytes()
  const rebuilt = buildS2SStoredZip([
    { name: spec.memberName, bytes: memberBytes }
  ])
  if (Either.isLeft(rebuilt)) return Either.left(rebuilt.left)
  if (!sameBytes(rebuilt.right.readArchiveBytes(), bytes)) {
    return Either.left(
      uploadError(
        operation,
        role,
        "ARCHIVE_NOT_DETERMINISTIC",
        "archive is valid ZIP but not the exact deterministic stored framing"
      )
    )
  }
  const memberSnapshot = Uint8Array.from(memberBytes)
  return Either.right(
    Object.freeze({
      role,
      publicationKey: spec.publicationKey,
      postconditionPublicationKey: spec.postconditionPublicationKey,
      archiveByteLength: bytes.byteLength,
      archiveRawSha256: rawSha256,
      member: Object.freeze({
        name: spec.memberName,
        byteLength: memberSnapshot.byteLength,
        rawBytesSha256: member.rawBytesSha256,
        readBytes: (): Uint8Array => Uint8Array.from(memberSnapshot)
      }),
      bytes
    })
  )
}

const artifactSnapshotFromValidated = (
  validated: ValidatedRoleArchive
): S2STestOnlyGoldenArtifactSnapshot => {
  const archive = Uint8Array.from(validated.bytes)
  return Object.freeze({
    role: validated.role,
    publicationKey: validated.publicationKey,
    postconditionPublicationKey: validated.postconditionPublicationKey,
    archiveByteLength: archive.byteLength,
    archiveRawSha256: validated.archiveRawSha256,
    members: singleFrozenTuple(validated.member),
    readArchiveBytes: (): Uint8Array => Uint8Array.from(archive)
  })
}

/** Build the role-owned singleton numeric ZIP without production carrier fields. */
export const buildS2STestOnlyGoldenArtifact = (
  roleInput: unknown,
  exactMembers: unknown
): Either.Either<
  S2STestOnlyGoldenArtifactSnapshot,
  S2STestOnlyGoldenUploadFailure
> => {
  const role = decodeRole(roleInput, "BUILD_ARTIFACT")
  if (Either.isLeft(role)) return Either.left(role.left)
  const member = snapshotExactMembers(exactMembers, role.right)
  if (Either.isLeft(member)) return Either.left(member.left)
  const built = buildS2SStoredZip([
    { name: member.right.name, bytes: member.right.bytes }
  ])
  if (Either.isLeft(built)) return Either.left(built.left)
  const validated = validateRoleArchive(
    role.right,
    built.right.readArchiveBytes(),
    "BUILD_ARTIFACT"
  )
  return Either.isLeft(validated)
    ? Either.left(validated.left)
    : Either.right(artifactSnapshotFromValidated(validated.right))
}

/**
 * Revalidate independently read bytes and exact-compare both archive and member
 * bytes. Hash equality is recorded, but is not substituted for byte equality.
 */
export const validateS2STestOnlyGoldenArtifactReadback = (
  roleInput: unknown,
  archiveInput: unknown,
  readbackInput: unknown
): Either.Either<
  S2STestOnlyGoldenArtifactReadback,
  S2STestOnlyGoldenUploadFailure
> => {
  const role = decodeRole(roleInput, "VALIDATE_READBACK")
  if (Either.isLeft(role)) return Either.left(role.left)
  const archive = validateRoleArchive(
    role.right,
    archiveInput,
    "VALIDATE_READBACK"
  )
  if (Either.isLeft(archive)) return Either.left(archive.left)
  const readback = validateRoleArchive(
    role.right,
    readbackInput,
    "VALIDATE_READBACK"
  )
  if (Either.isLeft(readback)) return Either.left(readback.left)
  const archiveMemberBytes = archive.right.member.readBytes()
  const readbackMemberBytes = readback.right.member.readBytes()
  if (
    archive.right.archiveByteLength !== readback.right.archiveByteLength ||
    archive.right.archiveRawSha256 !== readback.right.archiveRawSha256 ||
    !sameBytes(archive.right.bytes, readback.right.bytes)
  ) {
    return Either.left(
      uploadError(
        "VALIDATE_READBACK",
        role.right,
        "ARCHIVE_READBACK_MISMATCH",
        "readback archive differs from the exact published archive"
      )
    )
  }
  if (
    archive.right.member.name !== readback.right.member.name ||
    archive.right.member.byteLength !== readback.right.member.byteLength ||
    archive.right.member.rawBytesSha256 !==
      readback.right.member.rawBytesSha256 ||
    !sameBytes(archiveMemberBytes, readbackMemberBytes)
  ) {
    return Either.left(
      uploadError(
        "VALIDATE_READBACK",
        role.right,
        "MEMBER_BINDING_MISMATCH",
        "readback member differs from the exact published member"
      )
    )
  }
  const archiveBytes = Uint8Array.from(archive.right.bytes)
  const readbackBytes = Uint8Array.from(readback.right.bytes)
  return Either.right(
    Object.freeze({
      role: role.right,
      publicationKey: archive.right.publicationKey,
      postconditionPublicationKey: archive.right.postconditionPublicationKey,
      archiveByteLength: archiveBytes.byteLength,
      archiveRawSha256: archive.right.archiveRawSha256,
      readbackByteLength: readbackBytes.byteLength,
      readbackRawSha256: readback.right.archiveRawSha256,
      archiveReadbackBytesEqual: true as const,
      members: singleFrozenTuple(archive.right.member),
      readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes),
      readReadbackBytes: (): Uint8Array => Uint8Array.from(readbackBytes)
    })
  )
}

const postconditionCore = (
  readback: S2STestOnlyGoldenArtifactReadback
): Omit<S2STestOnlyGoldenUploadPostconditionDocument, "receipt_sha256"> => {
  const member = readback.members[0]
  return Object.freeze({
    schema_version:
      S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
    classification: "TEST_ONLY_NON_AUTHORIZING" as const,
    origin: "LOCAL_TEST_LAYER" as const,
    role: readback.role,
    publication_key: readback.publicationKey,
    publication_disposition: "CREATED" as const,
    archive_raw_sha256: readback.archiveRawSha256,
    archive_byte_length: readback.archiveByteLength,
    readback_raw_sha256: readback.readbackRawSha256,
    readback_byte_length: readback.readbackByteLength,
    archive_readback_bytes_equal: true as const,
    members: singleFrozenTuple(
      Object.freeze({
        name: member.name,
        raw_bytes_sha256: member.rawBytesSha256,
        byte_length: member.byteLength
      })
    )
  })
}

const snapshotPostcondition = (
  document: S2STestOnlyGoldenUploadPostconditionDocument,
  documentBytesInput: Uint8Array,
  archiveBytesInput: Uint8Array
): S2STestOnlyGoldenUploadPostconditionSnapshot => {
  const documentBytes = Uint8Array.from(documentBytesInput)
  const archiveBytes = Uint8Array.from(archiveBytesInput)
  const member = document.members[0]
  const frozenDocument: S2STestOnlyGoldenUploadPostconditionDocument =
    Object.freeze({
      ...document,
      members: singleFrozenTuple(Object.freeze({ ...member }))
    })
  return Object.freeze({
    document: frozenDocument,
    documentByteLength: documentBytes.byteLength,
    documentRawSha256: rawS2SFileSha256(documentBytes),
    archiveByteLength: archiveBytes.byteLength,
    archiveRawSha256: rawS2SFileSha256(archiveBytes),
    readDocumentBytes: (): Uint8Array => Uint8Array.from(documentBytes),
    readArchiveBytes: (): Uint8Array => Uint8Array.from(archiveBytes)
  })
}

const decodePostconditionBuildInput = (
  input: unknown
): Either.Either<
  {
    readonly role: S2STestOnlyGoldenRole
    readonly archiveBytes: unknown
    readonly readbackBytes: unknown
  },
  S2STestOnlyGoldenUploadError
> => {
  const record = exactPlainRecord(input, [
    "archiveBytes",
    "publicationDisposition",
    "publicationKey",
    "readbackBytes",
    "role"
  ])
  if (record === null) {
    return Either.left(
      uploadError(
        "BUILD_POSTCONDITION",
        null,
        "INPUT_INVALID",
        "postcondition binding must be one exact plain data record"
      )
    )
  }
  const role = decodeRole(record["role"], "BUILD_POSTCONDITION")
  if (Either.isLeft(role)) return Either.left(role.left)
  const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[role.right]
  if (record["publicationKey"] !== spec.publicationKey) {
    return Either.left(
      uploadError(
        "BUILD_POSTCONDITION",
        role.right,
        "PUBLICATION_KEY_MISMATCH",
        "publication key must be derived from the fixed golden role"
      )
    )
  }
  if (record["publicationDisposition"] !== "CREATED") {
    return Either.left(
      uploadError(
        "BUILD_POSTCONDITION",
        role.right,
        "PUBLICATION_DISPOSITION_INVALID",
        "test-only golden publication must be newly CREATED"
      )
    )
  }
  return Either.right(
    Object.freeze({
      role: role.right,
      archiveBytes: record["archiveBytes"],
      readbackBytes: record["readbackBytes"]
    })
  )
}

/** Build a distinct non-authorizing upload/readback postcondition ZIP. */
export const buildS2STestOnlyGoldenUploadPostcondition = (
  input: unknown
): Either.Either<
  S2STestOnlyGoldenUploadPostconditionSnapshot,
  S2STestOnlyGoldenUploadFailure
> => {
  const decoded = decodePostconditionBuildInput(input)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const readback = validateS2STestOnlyGoldenArtifactReadback(
    decoded.right.role,
    decoded.right.archiveBytes,
    decoded.right.readbackBytes
  )
  if (Either.isLeft(readback)) return Either.left(readback.left)
  const core = postconditionCore(readback.right)
  const receipt = canonicalS2SControlSha256(core)
  if (Either.isLeft(receipt)) return Either.left(receipt.left)
  const document: S2STestOnlyGoldenUploadPostconditionDocument = Object.freeze({
    ...core,
    receipt_sha256: receipt.right
  })
  const documentBytes = canonicalS2SControlJsonBytes(document)
  if (Either.isLeft(documentBytes)) return Either.left(documentBytes.left)
  if (
    documentBytes.right.byteLength >
    S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_MAX_BYTES
  ) {
    return Either.left(
      uploadError(
        "BUILD_POSTCONDITION",
        readback.right.role,
        "POSTCONDITION_NOT_CANONICAL",
        "postcondition exceeds its fixed control-document byte bound"
      )
    )
  }
  const archive = buildS2SStoredZip([
    {
      name: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME,
      bytes: documentBytes.right
    }
  ])
  if (Either.isLeft(archive)) return Either.left(archive.left)
  if (
    archive.right.archiveByteLength >
    S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES
  ) {
    return Either.left(
      uploadError(
        "BUILD_POSTCONDITION",
        readback.right.role,
        "POSTCONDITION_NOT_CANONICAL",
        "postcondition archive exceeds its fixed byte bound"
      )
    )
  }
  return Either.right(
    snapshotPostcondition(
      document,
      documentBytes.right,
      archive.right.readArchiveBytes()
    )
  )
}

const postconditionCoreFromDocument = (
  document: S2STestOnlyGoldenUploadPostconditionDocument
): Omit<S2STestOnlyGoldenUploadPostconditionDocument, "receipt_sha256"> =>
  Object.freeze({
    schema_version: document.schema_version,
    classification: document.classification,
    origin: document.origin,
    role: document.role,
    publication_key: document.publication_key,
    publication_disposition: document.publication_disposition,
    archive_raw_sha256: document.archive_raw_sha256,
    archive_byte_length: document.archive_byte_length,
    readback_raw_sha256: document.readback_raw_sha256,
    readback_byte_length: document.readback_byte_length,
    archive_readback_bytes_equal: document.archive_readback_bytes_equal,
    members: singleFrozenTuple(
      Object.freeze({ ...document.members[0] })
    )
  })

/**
 * Reconstruct unknown postcondition bytes against the actual publication and
 * readback bytes. A recomputed self-hash cannot override this external binding.
 */
export const reconstructS2STestOnlyGoldenUploadPostcondition = (
  postconditionArchiveInput: unknown,
  expectedBinding: unknown
): Either.Either<
  S2STestOnlyGoldenUploadPostconditionSnapshot,
  S2STestOnlyGoldenUploadFailure
> => {
  const expected = buildS2STestOnlyGoldenUploadPostcondition(expectedBinding)
  if (Either.isLeft(expected)) return Either.left(expected.left)
  const role = expected.right.document.role
  const archiveBytes = snapshotPlainBytes(
    postconditionArchiveInput,
    S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES
  )
  if (archiveBytes === null) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        role,
        "INPUT_INVALID",
        "postcondition archive must be one plain bounded byte array"
      )
    )
  }
  const validated = validateS2SArtifactZip(archiveBytes, {
    expectedArchiveSha256: S2SSha256Schema.make(
      rawS2SFileSha256(archiveBytes)
    ),
    expectedArchiveByteLength: archiveBytes.byteLength,
    expectedMembers: [
      {
        name: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME,
        maximumBytes: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_MAX_BYTES
      }
    ],
    maximumArchiveBytes: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES,
    maximumExpandedBytes: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_MAX_BYTES
  })
  if (Either.isLeft(validated)) return Either.left(validated.left)
  const member = validated.right.members[0]
  if (
    validated.right.members.length !== 1 ||
    member === undefined ||
    member.name !== S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME
  ) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        role,
        "MEMBER_ROSTER_MISMATCH",
        "postcondition ZIP must contain only postcondition.json"
      )
    )
  }
  const documentBytes = member.readBytes()
  let parsed: unknown
  try {
    parsed = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(documentBytes)
    )
  } catch {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        role,
        "POSTCONDITION_PARSE_FAILED",
        "postcondition member is not valid UTF-8 JSON"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(PostconditionDocumentSchema, {
    onExcessProperty: "error"
  })(parsed)
  if (Either.isLeft(decoded)) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        role,
        "POSTCONDITION_SCHEMA_REJECTED",
        "postcondition document violates its exact schema"
      )
    )
  }
  const decodedMember = decoded.right.members[0]
  const document: S2STestOnlyGoldenUploadPostconditionDocument = Object.freeze({
    ...decoded.right,
    members: singleFrozenTuple(Object.freeze({ ...decodedMember }))
  })
  const canonical = canonicalS2SControlJsonBytes(document)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  if (!sameBytes(canonical.right, documentBytes)) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        role,
        "POSTCONDITION_NOT_CANONICAL",
        "postcondition member is not exact canonical control JSON"
      )
    )
  }
  const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[document.role]
  if (
    document.publication_key !== spec.publicationKey ||
    document.members[0].name !== spec.memberName ||
    document.members[0].byte_length > spec.memberMaximumBytes ||
    document.archive_byte_length > spec.archiveMaximumBytes ||
    document.readback_byte_length > spec.archiveMaximumBytes ||
    document.archive_raw_sha256 !== document.readback_raw_sha256 ||
    document.archive_byte_length !== document.readback_byte_length
  ) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        document.role,
        "CROSS_BINDING_MISMATCH",
        "postcondition role, key, archive, readback, or member bindings diverge"
      )
    )
  }
  const receipt = canonicalS2SControlSha256(
    postconditionCoreFromDocument(document)
  )
  if (
    Either.isLeft(receipt) ||
    receipt.right !== document.receipt_sha256
  ) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        document.role,
        "RECEIPT_HASH_MISMATCH",
        "postcondition self-receipt disagrees with its unsigned core"
      )
    )
  }
  const deterministicArchive = buildS2SStoredZip([
    {
      name: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME,
      bytes: documentBytes
    }
  ])
  if (Either.isLeft(deterministicArchive)) {
    return Either.left(deterministicArchive.left)
  }
  if (!sameBytes(deterministicArchive.right.readArchiveBytes(), archiveBytes)) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        document.role,
        "ARCHIVE_NOT_DETERMINISTIC",
        "postcondition ZIP is not the exact deterministic stored framing"
      )
    )
  }
  if (
    !sameBytes(documentBytes, expected.right.readDocumentBytes()) ||
    !sameBytes(archiveBytes, expected.right.readArchiveBytes())
  ) {
    return Either.left(
      uploadError(
        "RECONSTRUCT_POSTCONDITION",
        document.role,
        "CROSS_BINDING_MISMATCH",
        "postcondition does not bind the expected publication/readback bytes"
      )
    )
  }
  return Either.right(
    snapshotPostcondition(document, documentBytes, archiveBytes)
  )
}
