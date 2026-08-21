import { Data, Either } from "effect"

import { rawS2SFileSha256 } from "./s2s-canonical.js"
import { S2SSha256Schema, type S2SSha256 } from "./s2s-confirmatory.js"

const LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50
const CENTRAL_DIRECTORY_HEADER_SIGNATURE = 0x02014b50
const DATA_DESCRIPTOR_SIGNATURE = 0x08074b50
const END_OF_CENTRAL_DIRECTORY_SIGNATURE = 0x06054b50
const STORED_COMPRESSION_METHOD = 0
const DATA_DESCRIPTOR_FLAG = 0x0008
const ARCHIVER_VERSION_MADE_BY = 0x032d
const DATA_DESCRIPTOR_VERSION_NEEDED = 20
const UNIX_FILE_TYPE_MASK = 0o170000
const UNIX_REGULAR_FILE = 0o100000
const DOS_ARCHIVE_ATTRIBUTE = 0x20
const ZIP64_EXTRA_FIELD = 0x0001
const AES_EXTRA_FIELD = 0x9901
const MAX_MEMBER_NAME_BYTES = 512
const MAX_ARCHIVE_OR_EXPANDED_BYTES = 64 * 1024 * 1024

export interface S2SExpectedZipMember {
  readonly name: string
  readonly maximumBytes: number
}

export interface S2SArtifactZipValidationPolicy {
  readonly expectedArchiveSha256: S2SSha256
  readonly expectedArchiveByteLength: number
  readonly expectedMembers: ReadonlyArray<S2SExpectedZipMember>
  readonly maximumArchiveBytes: number
  readonly maximumExpandedBytes: number
}

export interface S2SValidatedZipMember {
  readonly name: string
  readonly readBytes: () => Uint8Array
  readonly byteLength: number
  readonly crc32: number
  readonly rawBytesSha256: S2SSha256
}

export interface S2SValidatedArtifactZip {
  readonly archiveByteLength: number
  readonly archiveSha256: S2SSha256
  readonly expandedByteLength: number
  readonly largestMemberByteLength: number
  readonly members: ReadonlyArray<S2SValidatedZipMember>
}

export class S2SArtifactZipValidationError extends Data.TaggedError(
  "S2SArtifactZipValidationError"
)<{
  readonly reason:
    | "ARCHIVE_HASH_MISMATCH"
    | "ARCHIVE_SIZE_INVALID"
    | "CENTRAL_DIRECTORY_INVALID"
    | "COMPRESSION_POLICY_MISMATCH"
    | "CRC32_MISMATCH"
    | "DATA_DESCRIPTOR_INVALID"
    | "DUPLICATE_MEMBER"
    | "ENCRYPTION_UNSUPPORTED"
    | "END_RECORD_INVALID"
    | "EXTRA_FIELD_INVALID"
    | "FILE_TYPE_INVALID"
    | "INVALID_POLICY"
    | "LAYOUT_INVALID"
    | "LOCAL_CENTRAL_MISMATCH"
    | "MEMBER_NAME_UNSAFE"
    | "MEMBER_ROSTER_MISMATCH"
    | "MEMBER_SIZE_INVALID"
    | "MULTIDISK_UNSUPPORTED"
    | "ZIP64_UNSUPPORTED"
  readonly memberName: string | null
  readonly detail: string
}> {}

interface CentralEntry {
  readonly name: string
  readonly versionNeeded: number
  readonly flags: number
  readonly compressionMethod: number
  readonly lastModifiedTime: number
  readonly lastModifiedDate: number
  readonly crc32: number
  readonly compressedSize: number
  readonly uncompressedSize: number
  readonly localHeaderOffset: number
}

const validationError = (
  reason: S2SArtifactZipValidationError["reason"],
  detail: string,
  memberName: string | null = null
): S2SArtifactZipValidationError =>
  new S2SArtifactZipValidationError({ reason, memberName, detail })

const reject = (
  reason: S2SArtifactZipValidationError["reason"],
  detail: string,
  memberName: string | null = null
): never => {
  throw validationError(reason, detail, memberName)
}

const isSafePositiveInteger = (value: number): boolean =>
  Number.isSafeInteger(value) && value >= 1

const isValidDosDateTime = (time: number, date: number): boolean => {
  const doubledSecond = time & 0x1f
  const minute = (time >>> 5) & 0x3f
  const hour = (time >>> 11) & 0x1f
  const day = date & 0x1f
  const month = (date >>> 5) & 0x0f
  const year = 1980 + (date >>> 9)
  if (
    doubledSecond > 29 ||
    minute > 59 ||
    hour > 23 ||
    year > 2043 ||
    month < 1 ||
    month > 12 ||
    day < 1
  ) {
    return false
  }
  return day <= new Date(Date.UTC(year, month, 0)).getUTCDate()
}

const isSafeMemberName = (name: string): boolean =>
  name.length >= 1 &&
  name.length <= MAX_MEMBER_NAME_BYTES &&
  /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(name)

const makeCrc32Table = (): Uint32Array => {
  const table = new Uint32Array(256)
  for (let index = 0; index < table.length; index += 1) {
    let value = index
    for (let bit = 0; bit < 8; bit += 1) {
      value = (value & 1) === 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
    }
    table[index] = value >>> 0
  }
  return table
}

const CRC32_TABLE = makeCrc32Table()

const crc32 = (bytes: Uint8Array): number => {
  let value = 0xffffffff
  for (const byte of bytes) {
    const tableIndex = (value ^ byte) & 0xff
    const next =
      CRC32_TABLE[tableIndex] ??
      reject("CRC32_MISMATCH", "CRC table lookup failed")
    value = next ^ (value >>> 8)
  }
  return (value ^ 0xffffffff) >>> 0
}

const requireRange = (
  bytes: Uint8Array,
  offset: number,
  length: number,
  reason: S2SArtifactZipValidationError["reason"],
  detail: string,
  memberName: string | null = null
): void => {
  if (
    !Number.isSafeInteger(offset) ||
    !Number.isSafeInteger(length) ||
    offset < 0 ||
    length < 0 ||
    offset + length > bytes.byteLength
  ) {
    reject(reason, detail, memberName)
  }
}

const decodeMemberName = (
  bytes: Uint8Array,
  offset: number,
  length: number
): string => {
  if (length < 1 || length > MAX_MEMBER_NAME_BYTES) {
    reject("MEMBER_NAME_UNSAFE", "member name violates the byte bound")
  }
  requireRange(
    bytes,
    offset,
    length,
    "MEMBER_NAME_UNSAFE",
    "member name extends beyond the archive"
  )
  const nameBytes = bytes.subarray(offset, offset + length)
  if (nameBytes.some((byte) => byte < 0x20 || byte > 0x7e)) {
    reject("MEMBER_NAME_UNSAFE", "member name must be printable ASCII")
  }
  let name = ""
  for (const byte of nameBytes) name += String.fromCharCode(byte)
  if (!isSafeMemberName(name)) {
    reject("MEMBER_NAME_UNSAFE", "member name is not a safe relative file", name)
  }
  return name
}

const validateExtraFields = (
  view: DataView,
  bytes: Uint8Array,
  offset: number,
  length: number,
  memberName: string
): void => {
  requireRange(
    bytes,
    offset,
    length,
    "EXTRA_FIELD_INVALID",
    "extra fields extend beyond the archive",
    memberName
  )
  if (length !== 0) {
    const identifier = length >= 2 ? view.getUint16(offset, true) : null
    if (identifier === ZIP64_EXTRA_FIELD) {
      reject("ZIP64_UNSUPPORTED", "ZIP64 extra field is forbidden", memberName)
    }
    if (identifier === AES_EXTRA_FIELD) {
      reject(
        "ENCRYPTION_UNSUPPORTED",
        "AES extra field is forbidden",
        memberName
      )
    }
    reject(
      "EXTRA_FIELD_INVALID",
      "the pinned artifact ZIP dialect has no extra fields",
      memberName
    )
  }
}

const validateFlagsAndMethod = (
  flags: number,
  compressionMethod: number,
  memberName: string
): void => {
  if ((flags & 0x0001) !== 0 || (flags & 0x0040) !== 0) {
    reject(
      "ENCRYPTION_UNSUPPORTED",
      "encrypted ZIP members are forbidden",
      memberName
    )
  }
  if (flags !== DATA_DESCRIPTOR_FLAG) {
    reject(
      "CENTRAL_DIRECTORY_INVALID",
      "member flags disagree with the pinned streaming dialect",
      memberName
    )
  }
  if (compressionMethod !== STORED_COMPRESSION_METHOD) {
    reject(
      "COMPRESSION_POLICY_MISMATCH",
      "only stored compression-level-zero members are accepted",
      memberName
    )
  }
}

const validatePolicy = (policy: S2SArtifactZipValidationPolicy): void => {
  if (
    !/^[0-9a-f]{64}$/.test(policy.expectedArchiveSha256) ||
    !isSafePositiveInteger(policy.expectedArchiveByteLength) ||
    !isSafePositiveInteger(policy.maximumArchiveBytes) ||
    !isSafePositiveInteger(policy.maximumExpandedBytes) ||
    policy.maximumArchiveBytes > MAX_ARCHIVE_OR_EXPANDED_BYTES ||
    policy.maximumExpandedBytes > MAX_ARCHIVE_OR_EXPANDED_BYTES ||
    policy.expectedArchiveByteLength > policy.maximumArchiveBytes ||
    policy.expectedMembers.length < 1 ||
    policy.expectedMembers.length > 4
  ) {
    reject("INVALID_POLICY", "ZIP validation policy violates a fixed bound")
  }
  const names = new Set<string>()
  for (const member of policy.expectedMembers) {
    if (
      !isSafeMemberName(member.name) ||
      !isSafePositiveInteger(member.maximumBytes) ||
      member.maximumBytes > policy.maximumExpandedBytes ||
      names.has(member.name)
    ) {
      reject("INVALID_POLICY", "expected member policy is invalid")
    }
    names.add(member.name)
  }
}

const parseCentralDirectory = (
  view: DataView,
  bytes: Uint8Array,
  centralOffset: number,
  centralSize: number,
  entryCount: number,
  policy: S2SArtifactZipValidationPolicy
): ReadonlyArray<CentralEntry> => {
  const centralEnd = centralOffset + centralSize
  requireRange(
    bytes,
    centralOffset,
    centralSize,
    "CENTRAL_DIRECTORY_INVALID",
    "central directory extends beyond the archive"
  )
  const entries: Array<CentralEntry> = []
  const names = new Set<string>()
  let cursor = centralOffset
  for (let index = 0; index < entryCount; index += 1) {
    requireRange(
      bytes,
      cursor,
      46,
      "CENTRAL_DIRECTORY_INVALID",
      "central directory header is truncated"
    )
    if (
      view.getUint32(cursor, true) !== CENTRAL_DIRECTORY_HEADER_SIGNATURE
    ) {
      reject(
        "CENTRAL_DIRECTORY_INVALID",
        "central directory signature disagrees"
      )
    }
    const versionMadeBy = view.getUint16(cursor + 4, true)
    const versionNeeded = view.getUint16(cursor + 6, true)
    const flags = view.getUint16(cursor + 8, true)
    const compressionMethod = view.getUint16(cursor + 10, true)
    const lastModifiedTime = view.getUint16(cursor + 12, true)
    const lastModifiedDate = view.getUint16(cursor + 14, true)
    const crc = view.getUint32(cursor + 16, true)
    const compressedSize = view.getUint32(cursor + 20, true)
    const uncompressedSize = view.getUint32(cursor + 24, true)
    const nameLength = view.getUint16(cursor + 28, true)
    const extraLength = view.getUint16(cursor + 30, true)
    const commentLength = view.getUint16(cursor + 32, true)
    const diskStart = view.getUint16(cursor + 34, true)
    const internalAttributes = view.getUint16(cursor + 36, true)
    const externalAttributes = view.getUint32(cursor + 38, true)
    const localHeaderOffset = view.getUint32(cursor + 42, true)
    if (
      compressedSize === 0xffffffff ||
      uncompressedSize === 0xffffffff ||
      localHeaderOffset === 0xffffffff
    ) {
      reject("ZIP64_UNSUPPORTED", "ZIP64 member metadata is forbidden")
    }
    const variableLength = nameLength + extraLength + commentLength
    if (cursor + 46 + variableLength > centralEnd) {
      reject(
        "CENTRAL_DIRECTORY_INVALID",
        "central directory variable fields are truncated"
      )
    }
    const name = decodeMemberName(bytes, cursor + 46, nameLength)
    if (names.has(name)) {
      reject("DUPLICATE_MEMBER", "archive repeats a member name", name)
    }
    names.add(name)
    validateFlagsAndMethod(flags, compressionMethod, name)
    if (!isValidDosDateTime(lastModifiedTime, lastModifiedDate)) {
      reject(
        "CENTRAL_DIRECTORY_INVALID",
        "member has an invalid DOS date or time",
        name
      )
    }
    if (
      versionMadeBy !== ARCHIVER_VERSION_MADE_BY ||
      versionNeeded !== DATA_DESCRIPTOR_VERSION_NEEDED
    ) {
      reject(
        "CENTRAL_DIRECTORY_INVALID",
        "member versions disagree with the pinned Archiver dialect",
        name
      )
    }
    validateExtraFields(
      view,
      bytes,
      cursor + 46 + nameLength,
      extraLength,
      name
    )
    if (commentLength !== 0 || diskStart !== 0 || internalAttributes !== 0) {
      reject(
        "CENTRAL_DIRECTORY_INVALID",
        "member comment, disk start, or internal attributes disagree",
        name
      )
    }
    const unixMode = externalAttributes >>> 16
    if (
      (externalAttributes & 0xffff) !== DOS_ARCHIVE_ATTRIBUTE ||
      (unixMode & UNIX_FILE_TYPE_MASK) !== UNIX_REGULAR_FILE
    ) {
      reject(
        "FILE_TYPE_INVALID",
        "member is not an Archiver-produced Unix regular file",
        name
      )
    }
    if (
      compressedSize < 1 ||
      uncompressedSize < 1 ||
      compressedSize !== uncompressedSize
    ) {
      reject(
        "MEMBER_SIZE_INVALID",
        "stored member sizes must be equal and nonzero",
        name
      )
    }
    const expected =
      policy.expectedMembers.find((member) => member.name === name) ??
      reject(
        "MEMBER_ROSTER_MISMATCH",
        "central member is not in the exact roster",
        name
      )
    if (uncompressedSize > expected.maximumBytes) {
      reject(
        "MEMBER_SIZE_INVALID",
        "member exceeds its role-specific byte bound",
        name
      )
    }
    entries.push({
      name,
      versionNeeded,
      flags,
      compressionMethod,
      lastModifiedTime,
      lastModifiedDate,
      crc32: crc,
      compressedSize,
      uncompressedSize,
      localHeaderOffset
    })
    cursor += 46 + variableLength
  }
  if (cursor !== centralEnd) {
    reject(
      "CENTRAL_DIRECTORY_INVALID",
      "central directory contains trailing or unparsed records"
    )
  }
  return Object.freeze(entries)
}

const validateLocalEntries = (
  view: DataView,
  bytes: Uint8Array,
  entries: ReadonlyArray<CentralEntry>,
  centralOffset: number,
  maximumExpandedBytes: number
): {
  readonly members: ReadonlyArray<S2SValidatedZipMember>
  readonly expandedByteLength: number
  readonly largestMemberByteLength: number
} => {
  const members: Array<S2SValidatedZipMember> = []
  let expandedByteLength = 0
  let largestMemberByteLength = 0
  let expectedOffset = 0
  for (let index = 0; index < entries.length; index += 1) {
    const entry =
      entries[index] ??
      reject("LAYOUT_INVALID", "central entry disappeared during validation")
    if (entry.localHeaderOffset !== expectedOffset) {
      reject(
        "LAYOUT_INVALID",
        "local entries must form one exact prefix without gaps",
        entry.name
      )
    }
    const offset = entry.localHeaderOffset
    requireRange(
      bytes,
      offset,
      30,
      "LAYOUT_INVALID",
      "local file header is truncated",
      entry.name
    )
    if (view.getUint32(offset, true) !== LOCAL_FILE_HEADER_SIGNATURE) {
      reject("LAYOUT_INVALID", "local file signature disagrees", entry.name)
    }
    const versionNeeded = view.getUint16(offset + 4, true)
    const flags = view.getUint16(offset + 6, true)
    const compressionMethod = view.getUint16(offset + 8, true)
    const lastModifiedTime = view.getUint16(offset + 10, true)
    const lastModifiedDate = view.getUint16(offset + 12, true)
    const localCrc = view.getUint32(offset + 14, true)
    const localCompressedSize = view.getUint32(offset + 18, true)
    const localUncompressedSize = view.getUint32(offset + 22, true)
    const nameLength = view.getUint16(offset + 26, true)
    const extraLength = view.getUint16(offset + 28, true)
    const name = decodeMemberName(bytes, offset + 30, nameLength)
    validateExtraFields(
      view,
      bytes,
      offset + 30 + nameLength,
      extraLength,
      name
    )
    if (
      name !== entry.name ||
      versionNeeded !== entry.versionNeeded ||
      flags !== entry.flags ||
      compressionMethod !== entry.compressionMethod ||
      lastModifiedTime !== entry.lastModifiedTime ||
      lastModifiedDate !== entry.lastModifiedDate
    ) {
      reject(
        "LOCAL_CENTRAL_MISMATCH",
        "local and central member headers disagree",
        entry.name
      )
    }
    validateFlagsAndMethod(flags, compressionMethod, name)
    const dataStart = offset + 30 + nameLength + extraLength
    const dataEnd = dataStart + entry.compressedSize
    const next = entries[index + 1]
    const boundary = next?.localHeaderOffset ?? centralOffset
    if (dataEnd > boundary || boundary > centralOffset) {
      reject(
        "LAYOUT_INVALID",
        "member data overlaps another ZIP record",
        entry.name
      )
    }
    if (
      localCrc !== 0 ||
      localCompressedSize !== 0 ||
      localUncompressedSize !== 0
    ) {
      reject(
        "LOCAL_CENTRAL_MISMATCH",
        "streaming local CRC and sizes must be zero",
        entry.name
      )
    }
    if (boundary - dataEnd !== 16) {
      reject(
        "DATA_DESCRIPTOR_INVALID",
        "the signed 16-byte data descriptor is required",
        entry.name
      )
    }
    requireRange(
      bytes,
      dataEnd,
      16,
      "DATA_DESCRIPTOR_INVALID",
      "data descriptor is truncated",
      entry.name
    )
    if (
      view.getUint32(dataEnd, true) !== DATA_DESCRIPTOR_SIGNATURE ||
      view.getUint32(dataEnd + 4, true) !== entry.crc32 ||
      view.getUint32(dataEnd + 8, true) !== entry.compressedSize ||
      view.getUint32(dataEnd + 12, true) !== entry.uncompressedSize
    ) {
      reject(
        "DATA_DESCRIPTOR_INVALID",
        "data descriptor disagrees with central metadata",
        entry.name
      )
    }
    const memberBytes = Uint8Array.from(bytes.subarray(dataStart, dataEnd))
    if (crc32(memberBytes) !== entry.crc32) {
      reject("CRC32_MISMATCH", "member CRC-32 disagrees", entry.name)
    }
    expandedByteLength += memberBytes.byteLength
    if (
      !Number.isSafeInteger(expandedByteLength) ||
      expandedByteLength > maximumExpandedBytes
    ) {
      reject(
        "MEMBER_SIZE_INVALID",
        "expanded archive exceeds its aggregate bound",
        entry.name
      )
    }
    largestMemberByteLength = Math.max(
      largestMemberByteLength,
      memberBytes.byteLength
    )
    members.push(
      Object.freeze({
        name: entry.name,
        readBytes: (): Uint8Array => Uint8Array.from(memberBytes),
        byteLength: memberBytes.byteLength,
        crc32: entry.crc32,
        rawBytesSha256: S2SSha256Schema.make(
          rawS2SFileSha256(memberBytes)
        )
      })
    )
    expectedOffset = boundary
  }
  if (expectedOffset !== centralOffset) {
    reject(
      "LAYOUT_INVALID",
      "local member region does not end at the central directory"
    )
  }
  return {
    members: Object.freeze(members),
    expandedByteLength,
    largestMemberByteLength
  }
}

/**
 * Strict seekable validator for the compression-level-zero ZIPs emitted by
 * the pinned GitHub artifact action. Its signed bit-3 data descriptors are
 * cross-checked against the central directory; ZIP64 and every alternate ZIP
 * dialect are deliberately outside this boundary.
 */
export const validateS2SArtifactZip = (
  inputBytes: Uint8Array,
  policy: S2SArtifactZipValidationPolicy
): Either.Either<S2SValidatedArtifactZip, S2SArtifactZipValidationError> => {
  try {
    validatePolicy(policy)
    if (
      inputBytes.byteLength < 22 ||
      inputBytes.byteLength > MAX_ARCHIVE_OR_EXPANDED_BYTES ||
      inputBytes.byteLength > policy.maximumArchiveBytes ||
      inputBytes.byteLength !== policy.expectedArchiveByteLength
    ) {
      reject(
        "ARCHIVE_SIZE_INVALID",
        "archive violates the fixed compressed byte bound"
      )
    }
    const bytes = Uint8Array.from(inputBytes)
    const archiveSha256 = rawS2SFileSha256(bytes)
    if (archiveSha256 !== policy.expectedArchiveSha256) {
      reject(
        "ARCHIVE_HASH_MISMATCH",
        "archive bytes disagree with the API-bound digest"
      )
    }
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    const endOffset = bytes.byteLength - 22
    if (
      view.getUint32(endOffset, true) !== END_OF_CENTRAL_DIRECTORY_SIGNATURE ||
      view.getUint16(endOffset + 20, true) !== 0
    ) {
      reject(
        "END_RECORD_INVALID",
        "archive must end in one comment-free central-directory record"
      )
    }
    const diskNumber = view.getUint16(endOffset + 4, true)
    const centralDisk = view.getUint16(endOffset + 6, true)
    const entriesOnDisk = view.getUint16(endOffset + 8, true)
    const entryCount = view.getUint16(endOffset + 10, true)
    const centralSize = view.getUint32(endOffset + 12, true)
    const centralOffset = view.getUint32(endOffset + 16, true)
    if (diskNumber !== 0 || centralDisk !== 0 || entriesOnDisk !== entryCount) {
      reject("MULTIDISK_UNSUPPORTED", "multi-disk ZIP archives are forbidden")
    }
    if (
      entryCount === 0xffff ||
      centralSize === 0xffffffff ||
      centralOffset === 0xffffffff
    ) {
      reject("ZIP64_UNSUPPORTED", "ZIP64 end records are forbidden")
    }
    if (
      entryCount !== policy.expectedMembers.length ||
      centralOffset + centralSize !== endOffset
    ) {
      reject(
        "MEMBER_ROSTER_MISMATCH",
        "end record disagrees with the exact member roster or layout"
      )
    }
    const entries = parseCentralDirectory(
      view,
      bytes,
      centralOffset,
      centralSize,
      entryCount,
      policy
    )
    const local = validateLocalEntries(
      view,
      bytes,
      entries,
      centralOffset,
      policy.maximumExpandedBytes
    )
    return Either.right(
      Object.freeze({
        archiveByteLength: bytes.byteLength,
        archiveSha256: S2SSha256Schema.make(archiveSha256),
        expandedByteLength: local.expandedByteLength,
        largestMemberByteLength: local.largestMemberByteLength,
        members: local.members
      })
    )
  } catch (error) {
    return Either.left(
      error instanceof S2SArtifactZipValidationError
        ? error
        : validationError(
            "CENTRAL_DIRECTORY_INVALID",
            "archive parsing failed closed"
          )
    )
  }
}
