const LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50
const CENTRAL_DIRECTORY_HEADER_SIGNATURE = 0x02014b50
const DATA_DESCRIPTOR_SIGNATURE = 0x08074b50
const END_OF_CENTRAL_DIRECTORY_SIGNATURE = 0x06054b50
const encoder = new TextEncoder()

export interface S2STestZipMember {
  readonly name: string
  readonly bytes: Uint8Array
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

const crc32 = (bytes: Uint8Array): number => {
  let value = 0xffffffff
  for (const byte of bytes) {
    const next = CRC32_TABLE[(value ^ byte) & 0xff]
    if (next === undefined) throw new Error("test ZIP CRC lookup failed")
    value = next ^ (value >>> 8)
  }
  return (value ^ 0xffffffff) >>> 0
}

const concat = (chunks: ReadonlyArray<Uint8Array>): Uint8Array =>
  Uint8Array.from(Buffer.concat(chunks.map((chunk) => Buffer.from(chunk))))

/** Independent fixture for the exact pinned Archiver level-zero file dialect. */
export const buildS2STestActionZip = (
  inputs: ReadonlyArray<S2STestZipMember>
): Uint8Array => {
  const members = inputs.map((member) => ({
    name: member.name,
    bytes: Uint8Array.from(member.bytes)
  }))
  const localChunks: Array<Uint8Array> = []
  const localOffsets: Array<number> = []
  let offset = 0
  for (const member of members) {
    const name = encoder.encode(member.name)
    const checksum = crc32(member.bytes)
    const header = Buffer.alloc(30)
    header.writeUInt32LE(LOCAL_FILE_HEADER_SIGNATURE, 0)
    header.writeUInt16LE(20, 4)
    header.writeUInt16LE(0x0008, 6)
    header.writeUInt16LE(0, 8)
    header.writeUInt16LE(0, 10)
    header.writeUInt16LE(0x0021, 12)
    header.writeUInt16LE(name.byteLength, 26)
    const descriptor = Buffer.alloc(16)
    descriptor.writeUInt32LE(DATA_DESCRIPTOR_SIGNATURE, 0)
    descriptor.writeUInt32LE(checksum, 4)
    descriptor.writeUInt32LE(member.bytes.byteLength, 8)
    descriptor.writeUInt32LE(member.bytes.byteLength, 12)
    localOffsets.push(offset)
    localChunks.push(header, name, member.bytes, descriptor)
    offset += header.byteLength + name.byteLength + member.bytes.byteLength + 16
  }

  const centralOffset = offset
  const centralChunks: Array<Uint8Array> = []
  for (let index = 0; index < members.length; index += 1) {
    const member = members[index]
    const localOffset = localOffsets[index]
    if (member === undefined || localOffset === undefined) {
      throw new Error("test ZIP member disappeared")
    }
    const name = encoder.encode(member.name)
    const header = Buffer.alloc(46)
    header.writeUInt32LE(CENTRAL_DIRECTORY_HEADER_SIGNATURE, 0)
    header.writeUInt16LE(0x032d, 4)
    header.writeUInt16LE(20, 6)
    header.writeUInt16LE(0x0008, 8)
    header.writeUInt16LE(0, 10)
    header.writeUInt16LE(0, 12)
    header.writeUInt16LE(0x0021, 14)
    header.writeUInt32LE(crc32(member.bytes), 16)
    header.writeUInt32LE(member.bytes.byteLength, 20)
    header.writeUInt32LE(member.bytes.byteLength, 24)
    header.writeUInt16LE(name.byteLength, 28)
    header.writeUInt32LE((((0o100644 << 16) | 0x20) >>> 0), 38)
    header.writeUInt32LE(localOffset, 42)
    centralChunks.push(header, name)
    offset += header.byteLength + name.byteLength
  }

  const end = Buffer.alloc(22)
  end.writeUInt32LE(END_OF_CENTRAL_DIRECTORY_SIGNATURE, 0)
  end.writeUInt16LE(members.length, 8)
  end.writeUInt16LE(members.length, 10)
  end.writeUInt32LE(offset - centralOffset, 12)
  end.writeUInt32LE(centralOffset, 16)
  return concat([...localChunks, ...centralChunks, end])
}
