import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

import { rawS2SFileSha256 } from "../src/s2s-canonical.js"
import { S2SSha256Schema } from "../src/s2s-confirmatory.js"
import {
  validateS2SArtifactZip,
  type S2SArtifactZipValidationError,
  type S2SArtifactZipValidationPolicy,
  type S2SExpectedZipMember
} from "../src/s2s-zip.js"

const LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50
const CENTRAL_DIRECTORY_HEADER_SIGNATURE = 0x02014b50
const DATA_DESCRIPTOR_SIGNATURE = 0x08074b50
const END_OF_CENTRAL_DIRECTORY_SIGNATURE = 0x06054b50
const encoder = new TextEncoder()

interface FixtureMember {
  readonly name: string
  readonly bytes: Uint8Array
}

interface FixtureOffsets {
  readonly localOffset: number
  readonly dataOffset: number
  readonly descriptorOffset: number
  readonly centralOffset: number
}

interface ZipFixture {
  readonly bytes: Uint8Array
  readonly members: ReadonlyArray<FixtureMember>
  readonly offsets: ReadonlyArray<FixtureOffsets>
  readonly centralOffset: number
  readonly endOffset: number
}

interface ZipDialectOverrides {
  readonly archiveComment?: Uint8Array
  readonly centralDate?: number
  readonly centralDisk?: number
  readonly centralExtra?: Uint8Array
  readonly centralFlags?: number
  readonly centralMethod?: number
  readonly centralTime?: number
  readonly descriptorCrcDelta?: number
  readonly descriptorSignature?: boolean
  readonly diskNumber?: number
  readonly entriesOnDisk?: number
  readonly entryCount?: number
  readonly externalAttributes?: number
  readonly internalAttributes?: number
  readonly localCrcActual?: boolean
  readonly localDate?: number
  readonly localExtra?: Uint8Array
  readonly localFlags?: number
  readonly localMethod?: number
  readonly localSizesActual?: boolean
  readonly localTime?: number
  readonly memberComment?: Uint8Array
  readonly versionMadeBy?: number
  readonly versionNeeded?: number
}

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

const fixtureCrc32 = (bytes: Uint8Array): number => {
  let value = 0xffffffff
  for (const byte of bytes) {
    const next = CRC32_TABLE[(value ^ byte) & 0xff]
    if (next === undefined) throw new Error("fixture CRC table lookup failed")
    value = next ^ (value >>> 8)
  }
  return (value ^ 0xffffffff) >>> 0
}

const concatBytes = (chunks: ReadonlyArray<Uint8Array>): Uint8Array =>
  Uint8Array.from(Buffer.concat(chunks.map((chunk) => Buffer.from(chunk))))

const regularExternalAttributes = (permissions = 0o644): number =>
  (((0o100000 | permissions) << 16) | 0x20) >>> 0

const buildStoredZip = (
  inputMembers: ReadonlyArray<FixtureMember>,
  overrides: ZipDialectOverrides = {}
): ZipFixture => {
  const members = inputMembers.map((member) => ({
    name: member.name,
    bytes: Uint8Array.from(member.bytes)
  }))
  const localChunks: Array<Uint8Array> = []
  const mutableOffsets: Array<{
    localOffset: number
    dataOffset: number
    descriptorOffset: number
    centralOffset: number
  }> = []
  const localExtra = overrides.localExtra ?? new Uint8Array()
  const centralExtra = overrides.centralExtra ?? new Uint8Array()
  const memberComment = overrides.memberComment ?? new Uint8Array()
  const versionNeeded = overrides.versionNeeded ?? 20
  const centralFlags = overrides.centralFlags ?? 0x0008
  const localFlags = overrides.localFlags ?? centralFlags
  const centralMethod = overrides.centralMethod ?? 0
  const localMethod = overrides.localMethod ?? centralMethod
  const centralTime = overrides.centralTime ?? 0x1c25
  const centralDate = overrides.centralDate ?? 0x5d15
  const localTime = overrides.localTime ?? centralTime
  const localDate = overrides.localDate ?? centralDate
  let cursor = 0

  for (const member of members) {
    const name = encoder.encode(member.name)
    const crc = fixtureCrc32(member.bytes)
    const header = Buffer.alloc(30)
    header.writeUInt32LE(LOCAL_FILE_HEADER_SIGNATURE, 0)
    header.writeUInt16LE(versionNeeded, 4)
    header.writeUInt16LE(localFlags, 6)
    header.writeUInt16LE(localMethod, 8)
    header.writeUInt16LE(localTime, 10)
    header.writeUInt16LE(localDate, 12)
    header.writeUInt32LE(overrides.localCrcActual === true ? crc : 0, 14)
    header.writeUInt32LE(
      overrides.localSizesActual === true ? member.bytes.byteLength : 0,
      18
    )
    header.writeUInt32LE(
      overrides.localSizesActual === true ? member.bytes.byteLength : 0,
      22
    )
    header.writeUInt16LE(name.byteLength, 26)
    header.writeUInt16LE(localExtra.byteLength, 28)
    const dataOffset = cursor + header.byteLength + name.byteLength + localExtra.byteLength
    const descriptorOffset = dataOffset + member.bytes.byteLength
    const signedDescriptor = overrides.descriptorSignature !== false
    const descriptor = Buffer.alloc(signedDescriptor ? 16 : 12)
    const descriptorFieldsOffset = signedDescriptor ? 4 : 0
    if (signedDescriptor) {
      descriptor.writeUInt32LE(DATA_DESCRIPTOR_SIGNATURE, 0)
    }
    descriptor.writeUInt32LE(
      (crc + (overrides.descriptorCrcDelta ?? 0)) >>> 0,
      descriptorFieldsOffset
    )
    descriptor.writeUInt32LE(member.bytes.byteLength, descriptorFieldsOffset + 4)
    descriptor.writeUInt32LE(member.bytes.byteLength, descriptorFieldsOffset + 8)
    mutableOffsets.push({
      localOffset: cursor,
      dataOffset,
      descriptorOffset,
      centralOffset: -1
    })
    localChunks.push(header, name, localExtra, member.bytes, descriptor)
    cursor = descriptorOffset + descriptor.byteLength
  }

  const centralOffset = cursor
  const centralChunks: Array<Uint8Array> = []
  for (let index = 0; index < members.length; index += 1) {
    const member = members[index]
    const offsets = mutableOffsets[index]
    if (member === undefined || offsets === undefined) {
      throw new Error("fixture member disappeared")
    }
    const name = encoder.encode(member.name)
    const crc = fixtureCrc32(member.bytes)
    const header = Buffer.alloc(46)
    header.writeUInt32LE(CENTRAL_DIRECTORY_HEADER_SIGNATURE, 0)
    header.writeUInt16LE(overrides.versionMadeBy ?? 0x032d, 4)
    header.writeUInt16LE(versionNeeded, 6)
    header.writeUInt16LE(centralFlags, 8)
    header.writeUInt16LE(centralMethod, 10)
    header.writeUInt16LE(centralTime, 12)
    header.writeUInt16LE(centralDate, 14)
    header.writeUInt32LE(crc, 16)
    header.writeUInt32LE(member.bytes.byteLength, 20)
    header.writeUInt32LE(member.bytes.byteLength, 24)
    header.writeUInt16LE(name.byteLength, 28)
    header.writeUInt16LE(centralExtra.byteLength, 30)
    header.writeUInt16LE(memberComment.byteLength, 32)
    header.writeUInt16LE(0, 34)
    header.writeUInt16LE(overrides.internalAttributes ?? 0, 36)
    header.writeUInt32LE(
      overrides.externalAttributes ?? regularExternalAttributes(),
      38
    )
    header.writeUInt32LE(offsets.localOffset, 42)
    offsets.centralOffset = cursor
    centralChunks.push(header, name, centralExtra, memberComment)
    cursor +=
      header.byteLength +
      name.byteLength +
      centralExtra.byteLength +
      memberComment.byteLength
  }

  const endOffset = cursor
  const archiveComment = overrides.archiveComment ?? new Uint8Array()
  const end = Buffer.alloc(22)
  end.writeUInt32LE(END_OF_CENTRAL_DIRECTORY_SIGNATURE, 0)
  end.writeUInt16LE(overrides.diskNumber ?? 0, 4)
  end.writeUInt16LE(overrides.centralDisk ?? 0, 6)
  end.writeUInt16LE(overrides.entriesOnDisk ?? members.length, 8)
  end.writeUInt16LE(overrides.entryCount ?? members.length, 10)
  end.writeUInt32LE(endOffset - centralOffset, 12)
  end.writeUInt32LE(centralOffset, 16)
  end.writeUInt16LE(archiveComment.byteLength, 20)

  return {
    bytes: concatBytes([...localChunks, ...centralChunks, end, archiveComment]),
    members,
    offsets: mutableOffsets.map((offsets) => Object.freeze({ ...offsets })),
    centralOffset,
    endOffset
  }
}

const digest = (bytes: Uint8Array) =>
  S2SSha256Schema.make(rawS2SFileSha256(bytes))

const policyFor = (
  bytes: Uint8Array,
  expectedMembers: ReadonlyArray<S2SExpectedZipMember>,
  overrides: Partial<S2SArtifactZipValidationPolicy> = {}
): S2SArtifactZipValidationPolicy => ({
  expectedArchiveSha256: digest(bytes),
  expectedArchiveByteLength: bytes.byteLength,
  expectedMembers,
  maximumArchiveBytes: 4 * 1024 * 1024,
  maximumExpandedBytes: 4 * 1024 * 1024,
  ...overrides
})

const exactMemberPolicy = (
  members: ReadonlyArray<FixtureMember>
): ReadonlyArray<S2SExpectedZipMember> =>
  members.map((member) => ({
    name: member.name,
    maximumBytes: Math.max(1, member.bytes.byteLength)
  }))

const expectFailure = (
  bytes: Uint8Array,
  expectedMembers: ReadonlyArray<S2SExpectedZipMember>,
  reason: S2SArtifactZipValidationError["reason"],
  label: string
): void => {
  const result = validateS2SArtifactZip(bytes, policyFor(bytes, expectedMembers))
  expect(Either.isLeft(result), label).toBe(true)
  if (Either.isRight(result)) throw new Error(`${label}: unexpectedly accepted`)
  expect(result.left.reason, label).toBe(reason)
}

const mutateUint16 = (
  input: Uint8Array,
  offset: number,
  value: number
): Uint8Array => {
  const bytes = Uint8Array.from(input)
  new DataView(bytes.buffer).setUint16(offset, value, true)
  return bytes
}

it("accepts only the exact stored streaming layout and returns defensive members", () => {
  const markerPayload = Uint8Array.from([
    ...encoder.encode("123456789"),
    0x50,
    0x4b,
    0x05,
    0x06,
    0x50,
    0x4b,
    0x07,
    0x08
  ])
  expect(fixtureCrc32(encoder.encode("123456789"))).toBe(0xcbf43926)
  const fixture = buildStoredZip([
    { name: "numeric_candidate.json", bytes: markerPayload },
    { name: "control_receipt.json", bytes: encoder.encode("{\"ok\":true}\n") }
  ])
  const expected = exactMemberPolicy([...fixture.members].reverse())
  const result = validateS2SArtifactZip(fixture.bytes, policyFor(fixture.bytes, expected))
  if (Either.isLeft(result)) throw result.left
  expect(result.right.archiveByteLength).toBe(fixture.bytes.byteLength)
  expect(result.right.archiveSha256).toBe(digest(fixture.bytes))
  expect(result.right.expandedByteLength).toBe(
    fixture.members.reduce((sum, member) => sum + member.bytes.byteLength, 0)
  )
  expect(result.right.members.map((member) => member.name)).toEqual(
    fixture.members.map((member) => member.name)
  )
  const firstRead = result.right.members[0]?.readBytes()
  const secondRead = result.right.members[0]?.readBytes()
  expect(firstRead).toBeDefined()
  expect(secondRead).toBeDefined()
  if (firstRead === undefined || secondRead === undefined) return
  firstRead[0] = 0
  fixture.bytes.fill(0)
  expect(secondRead[0]).not.toBe(0)
  expect(result.right.members[0]?.readBytes()).toEqual(secondRead)
})

it("matches a deterministic archive emitted by the pinned Archiver stack", () => {
  const fixture = buildStoredZip(
    [
      { name: "control_receipt.json", bytes: encoder.encode("alpha\n") },
      { name: "numeric_candidate.json", bytes: encoder.encode("beta\n") }
    ],
    { centralTime: 0, centralDate: 0x0021 }
  )
  expect(fixture.bytes.byteLength).toBe(301)
  expect(digest(fixture.bytes)).toBe(
    "a003eb3d8edbd7cb69bd7bbe5a4fad6a02330851975e173dca17244d3218e255"
  )
  expect(fixture.offsets.map(({ localOffset }) => localOffset)).toEqual([0, 72])
  expect(fixture.offsets.map(({ dataOffset }) => dataOffset)).toEqual([50, 124])
  expect(fixture.offsets.map(({ descriptorOffset }) => descriptorOffset)).toEqual([
    56, 129
  ])
  expect(fixture.offsets.map(({ centralOffset }) => centralOffset)).toEqual([
    145, 211
  ])
  expect(fixture.endOffset).toBe(279)
})

it("accepts the checked-in upload-artifact v4.6.2 golden archive", () => {
  const repositoryRoot = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../.."
  )
  const bytes = Uint8Array.from(
    readFileSync(
      resolve(
        repositoryRoot,
        "artifacts/swm0w_s2s/pilot_adoption/32442437970/pilot_artifact.zip"
      )
    )
  )
  const policy: S2SArtifactZipValidationPolicy = {
    expectedArchiveSha256: S2SSha256Schema.make(
      "b5a29cab118737f48083613f45a34212ae73f15a1321a597947d838c077f63c5"
    ),
    expectedArchiveByteLength: 1_366_046,
    expectedMembers: [{ name: "pilot.json", maximumBytes: 1_365_912 }],
    maximumArchiveBytes: 4 * 1024 * 1024,
    maximumExpandedBytes: 4 * 1024 * 1024
  }
  const result = validateS2SArtifactZip(bytes, policy)
  if (Either.isLeft(result)) throw result.left
  expect(result.right.members).toHaveLength(1)
  expect(result.right.members[0]?.byteLength).toBe(1_365_912)
  expect(result.right.members[0]?.crc32).toBe(0x7bc25832)
})

it("binds both API digest and exact API byte length before parsing", () => {
  const fixture = buildStoredZip([
    { name: "control_receipt.json", bytes: encoder.encode("{}\n") }
  ])
  const expected = exactMemberPolicy(fixture.members)
  const wrongHash = validateS2SArtifactZip(fixture.bytes, {
    ...policyFor(fixture.bytes, expected),
    expectedArchiveSha256: S2SSha256Schema.make("0".repeat(64))
  })
  expect(Either.isLeft(wrongHash) && wrongHash.left.reason).toBe(
    "ARCHIVE_HASH_MISMATCH"
  )
  const wrongLength = validateS2SArtifactZip(fixture.bytes, {
    ...policyFor(fixture.bytes, expected),
    expectedArchiveByteLength: fixture.bytes.byteLength + 1
  })
  expect(Either.isLeft(wrongLength) && wrongLength.left.reason).toBe(
    "ARCHIVE_SIZE_INVALID"
  )
})

it("rejects alternate ZIP dialects and spoofed file metadata", () => {
  const member = { name: "control_receipt.json", bytes: encoder.encode("{}\n") }
  const expected = exactMemberPolicy([member])
  const cases: ReadonlyArray<{
    readonly label: string
    readonly fixture: ZipFixture
    readonly reason: S2SArtifactZipValidationError["reason"]
  }> = [
    {
      label: "non-descriptor flags",
      fixture: buildStoredZip([member], { centralFlags: 0 }),
      reason: "CENTRAL_DIRECTORY_INVALID"
    },
    {
      label: "UTF-8 flag",
      fixture: buildStoredZip([member], { centralFlags: 0x0808 }),
      reason: "CENTRAL_DIRECTORY_INVALID"
    },
    {
      label: "encryption flag",
      fixture: buildStoredZip([member], { centralFlags: 0x0009 }),
      reason: "ENCRYPTION_UNSUPPORTED"
    },
    {
      label: "deflate method",
      fixture: buildStoredZip([member], { centralMethod: 8 }),
      reason: "COMPRESSION_POLICY_MISMATCH"
    },
    {
      label: "FAT creator",
      fixture: buildStoredZip([member], { versionMadeBy: 0x002d }),
      reason: "CENTRAL_DIRECTORY_INVALID"
    },
    {
      label: "old extraction version",
      fixture: buildStoredZip([member], { versionNeeded: 10 }),
      reason: "CENTRAL_DIRECTORY_INVALID"
    },
    {
      label: "central internal attributes",
      fixture: buildStoredZip([member], { internalAttributes: 1 }),
      reason: "CENTRAL_DIRECTORY_INVALID"
    },
    {
      label: "spoofed symlink mode",
      fixture: buildStoredZip([member], {
        versionMadeBy: 0x032d,
        externalAttributes: (((0o120777 << 16) | 0x20) >>> 0)
      }),
      reason: "FILE_TYPE_INVALID"
    },
    {
      label: "wrong DOS attribute",
      fixture: buildStoredZip([member], {
        externalAttributes: (regularExternalAttributes() | 0x10) >>> 0
      }),
      reason: "FILE_TYPE_INVALID"
    },
    {
      label: "arbitrary extra field",
      fixture: buildStoredZip([member], {
        centralExtra: Uint8Array.from([0xfe, 0xca, 0, 0])
      }),
      reason: "EXTRA_FIELD_INVALID"
    },
    {
      label: "ZIP64 extra field",
      fixture: buildStoredZip([member], {
        centralExtra: Uint8Array.from([1, 0, 0, 0])
      }),
      reason: "ZIP64_UNSUPPORTED"
    },
    {
      label: "AES extra field",
      fixture: buildStoredZip([member], {
        centralExtra: Uint8Array.from([0x01, 0x99, 0, 0])
      }),
      reason: "ENCRYPTION_UNSUPPORTED"
    },
    {
      label: "local extra field",
      fixture: buildStoredZip([member], {
        localExtra: Uint8Array.from([0xfe, 0xca, 0, 0])
      }),
      reason: "EXTRA_FIELD_INVALID"
    },
    {
      label: "invalid future DOS timestamp",
      fixture: buildStoredZip([member], {
        centralDate: ((2044 - 1980) << 9) | (1 << 5) | 1
      }),
      reason: "CENTRAL_DIRECTORY_INVALID"
    }
  ]
  for (const sample of cases) {
    expectFailure(sample.fixture.bytes, expected, sample.reason, sample.label)
  }
})

it("rejects unsigned, contradictory, corrupt, or padded data descriptors", () => {
  const member = { name: "control_receipt.json", bytes: encoder.encode("123456789") }
  const expected = exactMemberPolicy([member])
  const unsigned = buildStoredZip([member], { descriptorSignature: false })
  expectFailure(unsigned.bytes, expected, "DATA_DESCRIPTOR_INVALID", "unsigned descriptor")
  const contradictoryLocal = buildStoredZip([member], { localCrcActual: true })
  expectFailure(
    contradictoryLocal.bytes,
    expected,
    "LOCAL_CENTRAL_MISMATCH",
    "nonzero local CRC"
  )
  const contradictorySizes = buildStoredZip([member], { localSizesActual: true })
  expectFailure(
    contradictorySizes.bytes,
    expected,
    "LOCAL_CENTRAL_MISMATCH",
    "nonzero local sizes"
  )
  const wrongDescriptor = buildStoredZip([member], { descriptorCrcDelta: 1 })
  expectFailure(
    wrongDescriptor.bytes,
    expected,
    "DATA_DESCRIPTOR_INVALID",
    "wrong descriptor CRC"
  )
  const valid = buildStoredZip([member])
  const corruptPayload = Uint8Array.from(valid.bytes)
  const dataOffset = valid.offsets[0]?.dataOffset
  if (dataOffset === undefined) throw new Error("fixture offset missing")
  corruptPayload[dataOffset] = (corruptPayload[dataOffset] ?? 0) ^ 0xff
  expectFailure(corruptPayload, expected, "CRC32_MISMATCH", "payload corruption")
})

it("rejects central/local drift, non-tiled layout, multidisk, and trailing bytes", () => {
  const member = { name: "control_receipt.json", bytes: encoder.encode("{}\n") }
  const expected = exactMemberPolicy([member])
  const valid = buildStoredZip([member])
  const localTimeDrift = mutateUint16(
    valid.bytes,
    (valid.offsets[0]?.localOffset ?? 0) + 10,
    0x1c26
  )
  expectFailure(
    localTimeDrift,
    expected,
    "LOCAL_CENTRAL_MISMATCH",
    "DOS time drift"
  )
  const prefixed = new Uint8Array(valid.bytes.byteLength + 1)
  prefixed.set(valid.bytes, 1)
  const prefixResult = validateS2SArtifactZip(prefixed, policyFor(prefixed, expected))
  expect(Either.isLeft(prefixResult)).toBe(true)
  const trailing = concatBytes([valid.bytes, Uint8Array.of(0)])
  expectFailure(trailing, expected, "END_RECORD_INVALID", "trailing byte")
  const multidisk = buildStoredZip([member], { diskNumber: 1 })
  expectFailure(multidisk.bytes, expected, "MULTIDISK_UNSUPPORTED", "multidisk")
  const commented = buildStoredZip([member], { archiveComment: Uint8Array.of(1) })
  expectFailure(commented.bytes, expected, "END_RECORD_INVALID", "archive comment")
})

it("enforces the frozen roster, safe names, and member/aggregate bounds", () => {
  const first = { name: "control_receipt.json", bytes: encoder.encode("12345") }
  const second = { name: "numeric_candidate.json", bytes: encoder.encode("67890") }
  const duplicate = buildStoredZip([first, first])
  expectFailure(
    duplicate.bytes,
    exactMemberPolicy([first, second]),
    "DUPLICATE_MEMBER",
    "duplicate member"
  )
  for (const unsafeName of ["../escape", "/absolute", "a\\b", "a/b", "C:drive"]) {
    const unsafe = buildStoredZip([{ name: unsafeName, bytes: encoder.encode("x") }])
    expectFailure(
      unsafe.bytes,
      [{ name: "control_receipt.json", maximumBytes: 1 }],
      "MEMBER_NAME_UNSAFE",
      unsafeName
    )
  }
  const valid = buildStoredZip([first, second])
  const wrongRoster = exactMemberPolicy([first])
  expectFailure(valid.bytes, wrongRoster, "MEMBER_ROSTER_MISMATCH", "missing roster member")
  const memberCap = validateS2SArtifactZip(valid.bytes, {
    ...policyFor(valid.bytes, exactMemberPolicy([first, second])),
    expectedMembers: [
      { name: first.name, maximumBytes: 4 },
      { name: second.name, maximumBytes: 5 }
    ]
  })
  expect(Either.isLeft(memberCap) && memberCap.left.reason).toBe(
    "MEMBER_SIZE_INVALID"
  )
  const aggregateCap = validateS2SArtifactZip(valid.bytes, {
    ...policyFor(valid.bytes, exactMemberPolicy([first, second])),
    maximumExpandedBytes: 9
  })
  expect(Either.isLeft(aggregateCap) && aggregateCap.left.reason).toBe(
    "MEMBER_SIZE_INVALID"
  )
})

it("rejects invalid or overbroad validation policies", () => {
  const fixture = buildStoredZip([
    { name: "control_receipt.json", bytes: encoder.encode("{}\n") }
  ])
  const expected = exactMemberPolicy(fixture.members)
  const policies: ReadonlyArray<S2SArtifactZipValidationPolicy> = [
    policyFor(fixture.bytes, expected, { maximumArchiveBytes: 64 * 1024 * 1024 + 1 }),
    policyFor(fixture.bytes, expected, {
      maximumExpandedBytes: 2,
      expectedMembers: [{ name: "control_receipt.json", maximumBytes: 3 }]
    }),
    policyFor(fixture.bytes, [expected[0]!, expected[0]!])
  ]
  for (const policy of policies) {
    const result = validateS2SArtifactZip(fixture.bytes, policy)
    expect(Either.isLeft(result) && result.left.reason).toBe("INVALID_POLICY")
  }
})
