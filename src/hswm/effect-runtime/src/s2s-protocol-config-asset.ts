import { constants } from "node:fs"
import { open } from "node:fs/promises"
import { fileURLToPath } from "node:url"

import { Context, Data, Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
} from "./s2s-confirmatory.js"

export const S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH = 1_973 as const
export const S2S_ADOPTED_PROTOCOL_CONFIG_MAX_BYTES = 65_536 as const

const ASSET_URL = new URL(
  "../assets/adopted-protocol-config.json",
  import.meta.url
)

export interface S2SAdoptedProtocolConfigAssetSnapshot {
  readonly byteLength: typeof S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH
  readonly rawBytesSha256: typeof S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256
  readonly receiptSha256: typeof S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  /** A new copy is returned on every access. */
  readonly readCanonicalBytes: () => Uint8Array
}

export class S2SAdoptedProtocolConfigAssetError extends Data.TaggedError(
  "S2SAdoptedProtocolConfigAssetError"
)<{
  readonly reason:
    | "ASSET_BYTES_INVALID"
    | "ASSET_FILE_INVALID"
    | "ASSET_HASH_MISMATCH"
    | "ASSET_IO_FAILED"
    | "ASSET_NOT_CANONICAL"
    | "ASSET_RECEIPT_MISMATCH"
  readonly detail: string
}> {}

export class S2SAdoptedProtocolConfigAsset extends Context.Tag(
  "hswm/S2S/AdoptedProtocolConfigAsset"
)<S2SAdoptedProtocolConfigAsset, S2SAdoptedProtocolConfigAssetSnapshot>() {}

const assetError = (
  reason: S2SAdoptedProtocolConfigAssetError["reason"],
  detail: string
): S2SAdoptedProtocolConfigAssetError =>
  new S2SAdoptedProtocolConfigAssetError({ reason, detail })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const isPlainUnsharedBytes = (input: unknown): input is Uint8Array =>
  input instanceof Uint8Array &&
  Object.getPrototypeOf(input) === Uint8Array.prototype &&
  Object.getOwnPropertySymbols(input).length === 0 &&
  Object.getOwnPropertyDescriptor(input, "byteLength") === undefined &&
  Object.getOwnPropertyDescriptor(input, "buffer") === undefined &&
  !(
    typeof SharedArrayBuffer !== "undefined" &&
    input.buffer instanceof SharedArrayBuffer
  )

/** Pure validator used by the fixed asset reader and by replay verification. */
export const validateS2SAdoptedProtocolConfigAsset = (
  input: unknown
): Either.Either<
  S2SAdoptedProtocolConfigAssetSnapshot,
  S2SAdoptedProtocolConfigAssetError
> => {
  let bytes: Uint8Array
  try {
    if (!isPlainUnsharedBytes(input)) {
      return Either.left(
        assetError(
          "ASSET_BYTES_INVALID",
          "protocol config must be one plain unshared Uint8Array"
        )
      )
    }
    bytes = new Uint8Array(input)
  } catch {
    return Either.left(
      assetError(
        "ASSET_BYTES_INVALID",
        "protocol config bytes could not be inspected safely"
      )
    )
  }
  if (
    bytes.byteLength !== S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH ||
    bytes.byteLength > S2S_ADOPTED_PROTOCOL_CONFIG_MAX_BYTES ||
    rawS2SFileSha256(bytes) !== S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256
  ) {
    return Either.left(
      assetError(
        "ASSET_HASH_MISMATCH",
        "protocol config bytes differ from the adopted document pin"
      )
    )
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes))
  } catch {
    return Either.left(
      assetError(
        "ASSET_NOT_CANONICAL",
        "protocol config is not valid UTF-8 JSON"
      )
    )
  }
  const canonical = canonicalS2SControlJsonBytes(parsed)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, bytes)) {
    return Either.left(
      assetError(
        "ASSET_NOT_CANONICAL",
        "protocol config is not exact canonical control JSON"
      )
    )
  }
  if (
    parsed === null ||
    typeof parsed !== "object" ||
    Array.isArray(parsed) ||
    Object.getPrototypeOf(parsed) !== Object.prototype
  ) {
    return Either.left(
      assetError("ASSET_NOT_CANONICAL", "protocol config root is not an object")
    )
  }
  const document = parsed as Record<string, unknown>
  const receiptValue = document["receipt_sha256"]
  const unsigned: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(document)) {
    if (key !== "receipt_sha256") unsigned[key] = value
  }
  const expectedReceipt = canonicalS2SControlSha256(unsigned)
  if (
    receiptValue !== S2S_PROTOCOL_CONFIG_RECEIPT_SHA256 ||
    Either.isLeft(expectedReceipt) ||
    expectedReceipt.right !== receiptValue
  ) {
    return Either.left(
      assetError(
        "ASSET_RECEIPT_MISMATCH",
        "protocol config self receipt differs from the adopted receipt pin"
      )
    )
  }
  const snapshot = new Uint8Array(bytes)
  return Either.right(
    Object.freeze({
      byteLength: S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH,
      rawBytesSha256: S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256,
      receiptSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
      readCanonicalBytes: () => new Uint8Array(snapshot)
    })
  )
}

const readFixedAsset = async (): Promise<Uint8Array> => {
  const path = fileURLToPath(ASSET_URL)
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW)
  try {
    const before = await handle.stat()
    if (
      !before.isFile() ||
      before.size !== S2S_ADOPTED_PROTOCOL_CONFIG_BYTE_LENGTH ||
      before.size > S2S_ADOPTED_PROTOCOL_CONFIG_MAX_BYTES
    ) {
      throw assetError(
        "ASSET_FILE_INVALID",
        "protocol config asset is not the exact bounded regular file"
      )
    }
    const bytes = new Uint8Array(await handle.readFile())
    const after = await handle.stat()
    if (
      before.dev !== after.dev ||
      before.ino !== after.ino ||
      before.size !== after.size ||
      bytes.byteLength !== before.size
    ) {
      throw assetError(
        "ASSET_FILE_INVALID",
        "protocol config asset identity changed while it was read"
      )
    }
    return bytes
  } finally {
    await handle.close()
  }
}

/** Lazily reads only the package-owned, content-pinned production asset. */
export const loadS2SAdoptedProtocolConfigAsset: Effect.Effect<
  S2SAdoptedProtocolConfigAssetSnapshot,
  S2SAdoptedProtocolConfigAssetError
> = Effect.tryPromise({
  try: readFixedAsset,
  catch: (error) =>
    error instanceof S2SAdoptedProtocolConfigAssetError
      ? error
      : assetError("ASSET_IO_FAILED", "protocol config asset could not be read")
}).pipe(
  Effect.flatMap((bytes) => {
    const validated = validateS2SAdoptedProtocolConfigAsset(bytes)
    return Either.isLeft(validated)
      ? Effect.fail(validated.left)
      : Effect.succeed(validated.right)
  })
)

export const S2SAdoptedProtocolConfigAssetLive = Layer.effect(
  S2SAdoptedProtocolConfigAsset,
  loadS2SAdoptedProtocolConfigAsset
)
