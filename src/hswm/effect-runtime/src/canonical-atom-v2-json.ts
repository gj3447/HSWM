import { createHash } from "node:crypto"

import { Data, Either } from "effect"

export const HSWM_CANONICAL_JSON_V1_CONTRACT_VERSION =
  "hswm-canonical-json/v1" as const
export const HSWM_CANONICAL_JSON_VERSION =
  HSWM_CANONICAL_JSON_V1_CONTRACT_VERSION
export const HSWM_CANONICAL_JSON_MEDIA_TYPE =
  "application/vnd.hswm.canonical-json+json" as const
export const HSWM_CANONICAL_JSON_V1_MAX_BYTES = 1_048_576 as const
export const HSWM_CANONICAL_JSON_V1_MAX_DEPTH = 128 as const
export const HSWM_CANONICAL_JSON_V1_MAX_NODES = 100_000 as const

export type CanonicalJson =
  | null
  | boolean
  | string
  | number
  | ReadonlyArray<CanonicalJson>
  | { readonly [key: string]: CanonicalJson }

export type CanonicalJsonErrorCode =
  | "BYTE_LIMIT_EXCEEDED"
  | "UTF8_INVALID"
  | "JSON_INVALID"
  | "DUPLICATE_KEY"
  | "DEPTH_LIMIT_EXCEEDED"
  | "NODE_LIMIT_EXCEEDED"
  | "NUMBER_INVALID"
  | "STRING_INVALID"
  | "VALUE_INVALID"

export class CanonicalJsonError extends Data.TaggedError("CanonicalJsonError")<{
  readonly code: CanonicalJsonErrorCode
  readonly detail: string
}> {}

const fail = (
  code: CanonicalJsonErrorCode,
  detail: string
): Either.Either<never, CanonicalJsonError> =>
  Either.left(new CanonicalJsonError({ code, detail }))

const isWhitespace = (character: string): boolean =>
  character === " " ||
  character === "\n" ||
  character === "\r" ||
  character === "\t"

const isDigit = (character: string): boolean =>
  character >= "0" && character <= "9"

const isHex = (character: string): boolean =>
  (character >= "0" && character <= "9") ||
  (character >= "a" && character <= "f") ||
  (character >= "A" && character <= "F")

const hasLoneSurrogate = (value: string): boolean => {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (!Number.isFinite(next) || next < 0xdc00 || next > 0xdfff) {
        return true
      }
      index += 1
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true
    }
  }
  return false
}

class JsonParser {
  private index = 0
  private nodes = 0

  constructor(readonly source: string) {}

  parse(): Either.Either<CanonicalJson, CanonicalJsonError> {
    this.skipWhitespace()
    const value = this.parseValue(0)
    if (Either.isLeft(value)) return value
    this.skipWhitespace()
    return this.index === this.source.length
      ? value
      : fail("JSON_INVALID", "trailing non-whitespace data follows JSON value")
  }

  private parseValue(depth: number): Either.Either<CanonicalJson, CanonicalJsonError> {
    if (depth > HSWM_CANONICAL_JSON_V1_MAX_DEPTH) {
      return fail("DEPTH_LIMIT_EXCEEDED", "JSON nesting exceeds the v1 bound")
    }
    this.nodes += 1
    if (this.nodes > HSWM_CANONICAL_JSON_V1_MAX_NODES) {
      return fail("NODE_LIMIT_EXCEEDED", "JSON node count exceeds the v1 bound")
    }
    const character = this.source[this.index]
    if (character === undefined) return fail("JSON_INVALID", "unexpected end of JSON input")
    if (character === "\"") return this.parseString()
    if (character === "{") return this.parseObject(depth + 1)
    if (character === "[") return this.parseArray(depth + 1)
    if (character === "t") return this.parseLiteral("true", true)
    if (character === "f") return this.parseLiteral("false", false)
    if (character === "n") return this.parseLiteral("null", null)
    if (character === "-" || isDigit(character)) return this.parseNumber()
    return fail("JSON_INVALID", `unexpected JSON character at offset ${this.index}`)
  }

  private parseLiteral<T extends null | boolean>(
    literal: string,
    value: T
  ): Either.Either<T, CanonicalJsonError> {
    if (!this.source.startsWith(literal, this.index)) {
      return fail("JSON_INVALID", `invalid literal at offset ${this.index}`)
    }
    this.index += literal.length
    return Either.right(value)
  }

  private parseString(): Either.Either<string, CanonicalJsonError> {
    this.index += 1
    let output = ""
    while (this.index < this.source.length) {
      const character = this.source[this.index]
      if (character === "\"") {
        this.index += 1
        return hasLoneSurrogate(output)
          ? fail("STRING_INVALID", "JSON string contains a lone surrogate")
          : Either.right(output)
      }
      if (character === undefined || character.charCodeAt(0) < 0x20) {
        return fail("JSON_INVALID", "unescaped control character in JSON string")
      }
      if (character !== "\\") {
        output += character
        this.index += 1
        continue
      }

      this.index += 1
      const escape = this.source[this.index]
      if (escape === undefined) return fail("JSON_INVALID", "unterminated JSON escape")
      const simpleEscapes: Readonly<Record<string, string>> = {
        "\"": "\"",
        "\\": "\\",
        "/": "/",
        b: "\b",
        f: "\f",
        n: "\n",
        r: "\r",
        t: "\t"
      }
      if (escape === "u") {
        const hexadecimal = this.source.slice(this.index + 1, this.index + 5)
        if (hexadecimal.length !== 4 || [...hexadecimal].some((digit) => !isHex(digit))) {
          return fail("JSON_INVALID", "invalid unicode escape in JSON string")
        }
        output += String.fromCharCode(Number.parseInt(hexadecimal, 16))
        this.index += 5
      } else if (Object.hasOwn(simpleEscapes, escape)) {
        output += simpleEscapes[escape] as string
        this.index += 1
      } else {
        return fail("JSON_INVALID", "invalid JSON string escape")
      }
    }
    return fail("JSON_INVALID", "unterminated JSON string")
  }

  private parseNumber(): Either.Either<number, CanonicalJsonError> {
    const start = this.index
    if (this.source[this.index] === "-") this.index += 1
    const first = this.source[this.index]
    if (first === "0") {
      this.index += 1
    } else if (first !== undefined && first >= "1" && first <= "9") {
      this.index += 1
      while (isDigit(this.source[this.index] ?? "")) this.index += 1
    } else {
      return fail("JSON_INVALID", "invalid JSON number")
    }
    if (this.source[this.index] === "." || this.source[this.index] === "e" || this.source[this.index] === "E") {
      return fail("NUMBER_INVALID", "canonical JSON v1 permits safe integers only")
    }
    const text = this.source.slice(start, this.index)
    const value = Number(text)
    return Number.isSafeInteger(value) && !Object.is(value, -0)
      ? Either.right(value)
      : fail("NUMBER_INVALID", "JSON number is not a safe non-negative-zero integer")
  }

  private parseArray(depth: number): Either.Either<ReadonlyArray<CanonicalJson>, CanonicalJsonError> {
    this.index += 1
    this.skipWhitespace()
    const values: Array<CanonicalJson> = []
    if (this.source[this.index] === "]") {
      this.index += 1
      return Either.right(values)
    }
    while (true) {
      this.skipWhitespace()
      const value = this.parseValue(depth)
      if (Either.isLeft(value)) return Either.left(value.left)
      values.push(value.right)
      this.skipWhitespace()
      const separator = this.source[this.index]
      if (separator === "]") {
        this.index += 1
        return Either.right(values)
      }
      if (separator !== ",") return fail("JSON_INVALID", "array element separator is missing")
      this.index += 1
      this.skipWhitespace()
    }
  }

  private parseObject(depth: number): Either.Either<{ readonly [key: string]: CanonicalJson }, CanonicalJsonError> {
    this.index += 1
    this.skipWhitespace()
    const output: Record<string, CanonicalJson> = Object.create(null)
    const keys = new Set<string>()
    if (this.source[this.index] === "}") {
      this.index += 1
      return Either.right(output)
    }
    while (true) {
      this.skipWhitespace()
      if (this.source[this.index] !== "\"") {
        return fail("JSON_INVALID", "object key must be a JSON string")
      }
      const key = this.parseString()
      if (Either.isLeft(key)) return Either.left(key.left)
      if (keys.has(key.right)) {
        return fail("DUPLICATE_KEY", `duplicate object key ${JSON.stringify(key.right)}`)
      }
      keys.add(key.right)
      this.skipWhitespace()
      if (this.source[this.index] !== ":") {
        return fail("JSON_INVALID", "object key/value separator is missing")
      }
      this.index += 1
      this.skipWhitespace()
      const value = this.parseValue(depth)
      if (Either.isLeft(value)) return Either.left(value.left)
      output[key.right] = value.right
      this.skipWhitespace()
      const separator = this.source[this.index]
      if (separator === "}") {
        this.index += 1
        return Either.right(output)
      }
      if (separator !== ",") return fail("JSON_INVALID", "object member separator is missing")
      this.index += 1
      this.skipWhitespace()
    }
  }

  private skipWhitespace(): void {
    while (isWhitespace(this.source[this.index] ?? "")) this.index += 1
  }
}

const decodeUtf8 = (bytes: Uint8Array): Either.Either<string, CanonicalJsonError> => {
  if (bytes.byteLength > HSWM_CANONICAL_JSON_V1_MAX_BYTES) {
    return fail("BYTE_LIMIT_EXCEEDED", "JSON byte input exceeds the v1 1 MiB bound")
  }
  try {
    return Either.right(new TextDecoder("utf-8", { fatal: true }).decode(bytes))
  } catch {
    return fail("UTF8_INVALID", "JSON input is not valid UTF-8")
  }
}

export const decodeCanonicalJsonBytes = (
  bytes: Uint8Array
): Either.Either<CanonicalJson, CanonicalJsonError> => {
  const decoded = decodeUtf8(bytes)
  return Either.isLeft(decoded) ? decoded : new JsonParser(decoded.right).parse()
}

const encodeString = (value: string): string => {
  let output = "\""
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    const character = value[index] as string
    switch (character) {
      case "\"":
        output += "\\\""
        break
      case "\\":
        output += "\\\\"
        break
      case "\b":
        output += "\\b"
        break
      case "\f":
        output += "\\f"
        break
      case "\n":
        output += "\\n"
        break
      case "\r":
        output += "\\r"
        break
      case "\t":
        output += "\\t"
        break
      default:
        output += code < 0x20 ? `\\u${code.toString(16).padStart(4, "0")}` : character
    }
  }
  return `${output}\"`
}

const compareUtf16 = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0

const canonicalizeValue = (
  value: unknown,
  depth: number,
  nodes: { value: number },
  ancestors: ReadonlySet<object>
): Either.Either<string, CanonicalJsonError> => {
  if (depth > HSWM_CANONICAL_JSON_V1_MAX_DEPTH) {
    return fail("DEPTH_LIMIT_EXCEEDED", "value nesting exceeds the v1 bound")
  }
  nodes.value += 1
  if (nodes.value > HSWM_CANONICAL_JSON_V1_MAX_NODES) {
    return fail("NODE_LIMIT_EXCEEDED", "value node count exceeds the v1 bound")
  }
  if (value === null) return Either.right("null")
  if (typeof value === "boolean") return Either.right(value ? "true" : "false")
  if (typeof value === "string") {
    return hasLoneSurrogate(value)
      ? fail("STRING_INVALID", "value string contains a lone surrogate")
      : Either.right(encodeString(value))
  }
  if (typeof value === "number") {
    return Number.isSafeInteger(value) && !Object.is(value, -0)
      ? Either.right(String(value))
      : fail("NUMBER_INVALID", "value number must be a safe integer other than -0")
  }
  if (typeof value !== "object") {
    return fail("VALUE_INVALID", "canonical JSON v1 excludes this value type")
  }
  if (ancestors.has(value)) return fail("VALUE_INVALID", "canonical JSON value contains a cycle")
  const nextAncestors = new Set(ancestors)
  nextAncestors.add(value)

  if (Array.isArray(value)) {
    const ownKeys = Object.keys(value)
    const ownNames = Object.getOwnPropertyNames(value)
    if (
      ownKeys.length !== value.length ||
      ownNames.length !== value.length + 1 ||
      ownNames.some(
        (name) =>
          name !== "length" &&
          (!/^(0|[1-9][0-9]*)$/.test(name) || Number(name) >= value.length)
      )
    ) {
      return fail("VALUE_INVALID", "canonical JSON arrays cannot have holes or extra keys")
    }
    const items: Array<string> = []
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.hasOwn(value, index)) {
        return fail("VALUE_INVALID", "canonical JSON arrays cannot have holes")
      }
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
      if (descriptor === undefined || !("value" in descriptor) || !descriptor.enumerable) {
        return fail("VALUE_INVALID", "canonical JSON arrays cannot contain accessors")
      }
      const item = canonicalizeValue(descriptor.value, depth + 1, nodes, nextAncestors)
      if (Either.isLeft(item)) return item
      items.push(item.right)
    }
    if (Object.getOwnPropertySymbols(value).length > 0) {
      return fail("VALUE_INVALID", "canonical JSON arrays cannot contain symbol keys")
    }
    return Either.right(`[${items.join(",")}]`)
  }

  const prototype = Object.getPrototypeOf(value)
  if (prototype !== Object.prototype && prototype !== null) {
    return fail("VALUE_INVALID", "canonical JSON objects must be plain objects")
  }
  if (Object.getOwnPropertySymbols(value).length > 0) {
    return fail("VALUE_INVALID", "canonical JSON objects cannot contain symbol keys")
  }
  const descriptors = Object.getOwnPropertyDescriptors(value)
  const keys = Object.keys(descriptors)
  for (const key of keys) {
    if (hasLoneSurrogate(key)) {
      return fail("STRING_INVALID", "object key contains a lone surrogate")
    }
    const descriptor = descriptors[key]
    if (descriptor === undefined || !("value" in descriptor) || !descriptor.enumerable) {
      return fail("VALUE_INVALID", "canonical JSON objects cannot contain accessors")
    }
  }
  const sorted = [...keys].sort(compareUtf16)
  const members: Array<string> = []
  for (const key of sorted) {
    const descriptor = descriptors[key]
    if (descriptor === undefined || !("value" in descriptor)) {
      return fail("VALUE_INVALID", "object descriptor disappeared during canonicalization")
    }
    const member = canonicalizeValue(descriptor.value, depth + 1, nodes, nextAncestors)
    if (Either.isLeft(member)) return member
    members.push(`${encodeString(key)}:${member.right}`)
  }
  return Either.right(`{${members.join(",")}}`)
}

export const canonicalJsonBytes = (
  value: unknown
): Either.Either<Uint8Array, CanonicalJsonError> => {
  let canonical: Either.Either<string, CanonicalJsonError>
  try {
    canonical = canonicalizeValue(value, 0, { value: 0 }, new Set())
  } catch {
    return fail(
      "VALUE_INVALID",
      "value could not be inspected without executing hostile object traps"
    )
  }
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  const bytes = new TextEncoder().encode(canonical.right)
  return bytes.byteLength > HSWM_CANONICAL_JSON_V1_MAX_BYTES
    ? fail("BYTE_LIMIT_EXCEEDED", "canonical JSON output exceeds the v1 1 MiB bound")
    : Either.right(bytes)
}

export const canonicalJsonSha256 = (
  value: unknown
): Either.Either<string, CanonicalJsonError> => {
  const bytes = canonicalJsonBytes(value)
  return Either.isLeft(bytes)
    ? Either.left(bytes.left)
    : Either.right(createHash("sha256").update(bytes.right).digest("hex"))
}
