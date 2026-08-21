import { createHash } from "node:crypto"

import { Data, Either } from "effect"

export type S2SControlJson =
  | null
  | boolean
  | number
  | string
  | ReadonlyArray<S2SControlJson>
  | { readonly [key: string]: S2SControlJson }

export class S2SCanonicalJsonError extends Data.TaggedError(
  "S2SCanonicalJsonError"
)<{
  readonly reason:
    | "ARRAY_HOLE"
    | "ARRAY_PROPERTY"
    | "CYCLIC_VALUE"
    | "INVALID_OBJECT"
    | "NON_ASCII_KEY"
    | "NON_ASCII_STRING"
    | "NON_ENUMERABLE_PROPERTY"
    | "NON_SAFE_INTEGER"
    | "SYMBOL_KEY"
    | "ACCESSOR_PROPERTY"
    | "UNSUPPORTED_VALUE"
  readonly path: string
}> {}

const ASCII_KEY = /^[\u0020-\u007e]+$/
const ASCII_STRING = /^[\u0000-\u007f]*$/

const encode = (
  value: unknown,
  path: string,
  ancestors: ReadonlySet<object>
): Either.Either<string, S2SCanonicalJsonError> => {
  if (value === null) return Either.right("null")
  if (typeof value === "boolean") {
    return Either.right(value ? "true" : "false")
  }
  if (typeof value === "string") {
    return ASCII_STRING.test(value)
      ? Either.right(JSON.stringify(value))
      : Either.left(
          new S2SCanonicalJsonError({ reason: "NON_ASCII_STRING", path })
        )
  }
  if (typeof value === "number") {
    return Number.isSafeInteger(value) && !Object.is(value, -0)
      ? Either.right(String(value))
      : Either.left(
          new S2SCanonicalJsonError({
            reason: "NON_SAFE_INTEGER",
            path
          })
        )
  }
  if (typeof value !== "object" || value === undefined) {
    return Either.left(
      new S2SCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path })
    )
  }
  if (ancestors.has(value)) {
    return Either.left(
      new S2SCanonicalJsonError({ reason: "CYCLIC_VALUE", path })
    )
  }
  const nextAncestors = new Set(ancestors)
  nextAncestors.add(value)
  if (Array.isArray(value)) {
    const ownKeys = Reflect.ownKeys(value)
    const expectedKeys = new Set<string>(["length"])
    for (let index = 0; index < value.length; index += 1) {
      expectedKeys.add(String(index))
    }
    if (
      ownKeys.some(
        (key) => typeof key !== "string" || !expectedKeys.has(key)
      ) ||
      ownKeys.length !== expectedKeys.size
    ) {
      return Either.left(
        new S2SCanonicalJsonError({ reason: "ARRAY_PROPERTY", path })
      )
    }
    const entries: Array<string> = []
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
      if (descriptor === undefined) {
        return Either.left(
          new S2SCanonicalJsonError({
            reason: "ARRAY_HOLE",
            path: `${path}[${index}]`
          })
        )
      }
      if (!descriptor.enumerable || !("value" in descriptor)) {
        return Either.left(
          new S2SCanonicalJsonError({
            reason: "ARRAY_PROPERTY",
            path: `${path}[${index}]`
          })
        )
      }
      const entry = encode(
        descriptor.value,
        `${path}[${index}]`,
        nextAncestors
      )
      if (Either.isLeft(entry)) return entry
      entries.push(entry.right)
    }
    return Either.right(`[${entries.join(",")}]`)
  }
  const prototype = Object.getPrototypeOf(value)
  if (prototype !== Object.prototype && prototype !== null) {
    return Either.left(
      new S2SCanonicalJsonError({ reason: "INVALID_OBJECT", path })
    )
  }
  const ownKeys = Reflect.ownKeys(value)
  if (ownKeys.some((key) => typeof key === "symbol")) {
    return Either.left(
      new S2SCanonicalJsonError({ reason: "SYMBOL_KEY", path })
    )
  }
  const keys = ownKeys.filter((key): key is string => typeof key === "string").sort()
  const entries: Array<string> = []
  for (const key of keys) {
    if (!ASCII_KEY.test(key)) {
      return Either.left(
        new S2SCanonicalJsonError({
          reason: "NON_ASCII_KEY",
          path: `${path}.${key}`
        })
      )
    }
    const descriptor = Object.getOwnPropertyDescriptor(value, key)
    if (descriptor === undefined || !descriptor.enumerable) {
      return Either.left(
        new S2SCanonicalJsonError({
          reason: "NON_ENUMERABLE_PROPERTY",
          path: `${path}.${key}`
        })
      )
    }
    if (!("value" in descriptor)) {
      return Either.left(
        new S2SCanonicalJsonError({
          reason: "ACCESSOR_PROPERTY",
          path: `${path}.${key}`
        })
      )
    }
    const entry = encode(
      descriptor.value,
      `${path}.${key}`,
      nextAncestors
    )
    if (Either.isLeft(entry)) return entry
    entries.push(`${JSON.stringify(key)}:${entry.right}`)
  }
  return Either.right(`{${entries.join(",")}}`)
}

/**
 * Canonical float-free JSON shared with the numeric boundary: ASCII keys,
 * sorted object keys, compact separators, UTF-8, and exactly one terminal LF.
 */
export const canonicalS2SControlJson = (
  value: unknown
): Either.Either<string, S2SCanonicalJsonError> =>
  encode(value, "$", new Set())

export const canonicalS2SControlJsonBytes = (
  value: unknown
): Either.Either<Uint8Array, S2SCanonicalJsonError> =>
  Either.map(canonicalS2SControlJson(value), (canonical) =>
    new TextEncoder().encode(`${canonical}\n`)
  )

export const canonicalS2SControlSha256 = (
  value: unknown
): Either.Either<string, S2SCanonicalJsonError> =>
  Either.map(canonicalS2SControlJson(value), (canonical) =>
    createHash("sha256").update(canonical, "utf8").digest("hex")
  )

export const rawS2SFileSha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")
