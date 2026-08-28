/**
 * Exact codec for the DNRD-5 randomization-plan blob.
 *
 * This deliberately does not use (or widen) canonical-json/v1: a complete
 * 300-block plan is larger than that runtime codec's 1 MiB boundary.  It is a
 * narrow transport codec, not a general runtime serialization facility and
 * does not establish provenance, chronology, execution, or scientific facts.
 */

import { createHash } from "node:crypto"

import { Data, Either } from "effect"

export const HSWM_DNRD5_PLAN_JSON_V1_CONTRACT_VERSION =
  "hswm-dnrd5-plan-json/v1" as const
export const HSWM_DNRD5_PLAN_JSON_V1_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.randomization-plan-v1+json" as const
export const HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES = 2_000_000 as const
export const HSWM_DNRD5_PLAN_JSON_V1_MAX_DEPTH = 128 as const
export const HSWM_DNRD5_PLAN_JSON_V1_MAX_NODES = 100_000 as const
export const HSWM_DNRD5_PLAN_JSON_V1_MIN_KEY_BYTES = 1 as const
export const HSWM_DNRD5_PLAN_JSON_V1_MAX_KEY_BYTES = 128 as const
export const HSWM_DNRD5_PLAN_JSON_V1_STATUS =
  "CODEC_ONLY_NOT_RUNTIME_QUALIFICATION_NOT_OCCURRENCE_NOT_SCIENTIFIC_RESULT" as const

export type Dnrd5PlanJson =
  | null
  | boolean
  | string
  | number
  | ReadonlyArray<Dnrd5PlanJson>
  | { readonly [key: string]: Dnrd5PlanJson }

export type Dnrd5PlanJsonErrorCode =
  | "BYTE_LIMIT_EXCEEDED"
  | "UTF8_INVALID"
  | "JSON_INVALID"
  | "DUPLICATE_KEY"
  | "KEY_INVALID"
  | "DEPTH_LIMIT_EXCEEDED"
  | "NODE_LIMIT_EXCEEDED"
  | "NUMBER_INVALID"
  | "STRING_INVALID"
  | "VALUE_INVALID"
  | "BYTES_NOT_CANONICAL"

export class Dnrd5PlanJsonError extends Data.TaggedError("Dnrd5PlanJsonError")<{
  readonly code: Dnrd5PlanJsonErrorCode
  readonly detail: string
}> {}

const fail = (
  code: Dnrd5PlanJsonErrorCode,
  detail: string
): Either.Either<never, Dnrd5PlanJsonError> =>
  Either.left(new Dnrd5PlanJsonError({ code, detail }))

const isWhitespace = (character: string): boolean =>
  character === " " || character === "\n" || character === "\r" || character === "\t"

const isDigit = (character: string): boolean => character >= "0" && character <= "9"

const isHex = (character: string): boolean =>
  (character >= "0" && character <= "9") ||
  (character >= "a" && character <= "f") ||
  (character >= "A" && character <= "F")

const hasLoneSurrogate = (value: string): boolean => {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (!Number.isFinite(next) || next < 0xdc00 || next > 0xdfff) return true
      index += 1
    } else if (code >= 0xdc00 && code <= 0xdfff) return true
  }
  return false
}

const isPlanKey = (key: string): boolean => {
  if (
    key.length < HSWM_DNRD5_PLAN_JSON_V1_MIN_KEY_BYTES ||
    key.length > HSWM_DNRD5_PLAN_JSON_V1_MAX_KEY_BYTES
  ) return false
  for (let index = 0; index < key.length; index += 1) {
    const code = key.charCodeAt(index)
    if (code < 0x20 || code > 0x7e) return false
  }
  return true
}

class Parser {
  private index = 0
  private nodes = 0

  constructor(readonly source: string) {}

  parse(): Either.Either<Dnrd5PlanJson, Dnrd5PlanJsonError> {
    // Whitespace is syntactically recognized here only so exact re-encoding
    // can classify it as a canonical-byte failure rather than accept it.
    this.skipWhitespace()
    const value = this.parseValue(0)
    if (Either.isLeft(value)) return value
    this.skipWhitespace()
    return this.index === this.source.length
      ? value
      : fail("JSON_INVALID", "trailing non-whitespace data follows JSON value")
  }

  private parseValue(depth: number): Either.Either<Dnrd5PlanJson, Dnrd5PlanJsonError> {
    if (depth > HSWM_DNRD5_PLAN_JSON_V1_MAX_DEPTH) {
      return fail("DEPTH_LIMIT_EXCEEDED", "plan JSON nesting exceeds the v1 bound")
    }
    this.nodes += 1
    if (this.nodes > HSWM_DNRD5_PLAN_JSON_V1_MAX_NODES) {
      return fail("NODE_LIMIT_EXCEEDED", "plan JSON node count exceeds the v1 bound")
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
  ): Either.Either<T, Dnrd5PlanJsonError> {
    if (!this.source.startsWith(literal, this.index)) return fail("JSON_INVALID", "invalid literal")
    this.index += literal.length
    return Either.right(value)
  }

  private parseString(): Either.Either<string, Dnrd5PlanJsonError> {
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
      const simple: Readonly<Record<string, string>> = {
        "\"": "\"", "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t"
      }
      if (escape === "u") {
        const hexadecimal = this.source.slice(this.index + 1, this.index + 5)
        if (hexadecimal.length !== 4 || [...hexadecimal].some((digit) => !isHex(digit))) {
          return fail("JSON_INVALID", "invalid Unicode escape in JSON string")
        }
        output += String.fromCharCode(Number.parseInt(hexadecimal, 16))
        this.index += 5
      } else if (Object.hasOwn(simple, escape)) {
        output += simple[escape] as string
        this.index += 1
      } else return fail("JSON_INVALID", "invalid JSON string escape")
    }
    return fail("JSON_INVALID", "unterminated JSON string")
  }

  private parseNumber(): Either.Either<number, Dnrd5PlanJsonError> {
    const start = this.index
    if (this.source[this.index] === "-") this.index += 1
    const first = this.source[this.index]
    if (first === "0") this.index += 1
    else if (first !== undefined && first >= "1" && first <= "9") {
      this.index += 1
      while (isDigit(this.source[this.index] ?? "")) this.index += 1
    } else return fail("JSON_INVALID", "invalid JSON number")
    if (this.source[this.index] === "." || this.source[this.index] === "e" || this.source[this.index] === "E") {
      return fail("NUMBER_INVALID", "plan JSON v1 permits safe integers only")
    }
    const value = Number(this.source.slice(start, this.index))
    return Number.isSafeInteger(value) && !Object.is(value, -0)
      ? Either.right(value)
      : fail("NUMBER_INVALID", "JSON number is not a safe integer other than -0")
  }

  private parseArray(depth: number): Either.Either<ReadonlyArray<Dnrd5PlanJson>, Dnrd5PlanJsonError> {
    this.index += 1; this.skipWhitespace()
    const values: Array<Dnrd5PlanJson> = []
    if (this.source[this.index] === "]") { this.index += 1; return Either.right(values) }
    while (true) {
      this.skipWhitespace()
      const value = this.parseValue(depth)
      if (Either.isLeft(value)) return Either.left(value.left)
      values.push(value.right); this.skipWhitespace()
      if (this.source[this.index] === "]") { this.index += 1; return Either.right(values) }
      if (this.source[this.index] !== ",") return fail("JSON_INVALID", "array element separator is missing")
      this.index += 1; this.skipWhitespace()
    }
  }

  private parseObject(depth: number): Either.Either<{ readonly [key: string]: Dnrd5PlanJson }, Dnrd5PlanJsonError> {
    this.index += 1; this.skipWhitespace()
    const output: Record<string, Dnrd5PlanJson> = Object.create(null)
    const keys = new Set<string>()
    if (this.source[this.index] === "}") { this.index += 1; return Either.right(output) }
    while (true) {
      this.skipWhitespace()
      if (this.source[this.index] !== "\"") return fail("JSON_INVALID", "object key must be a JSON string")
      const key = this.parseString()
      if (Either.isLeft(key)) return Either.left(key.left)
      if (!isPlanKey(key.right)) return fail("KEY_INVALID", "plan object key is not printable bounded ASCII")
      if (keys.has(key.right)) return fail("DUPLICATE_KEY", "duplicate object key")
      keys.add(key.right)
      this.skipWhitespace()
      if (this.source[this.index] !== ":") return fail("JSON_INVALID", "object key/value separator is missing")
      this.index += 1; this.skipWhitespace()
      const value = this.parseValue(depth)
      if (Either.isLeft(value)) return Either.left(value.left)
      output[key.right] = value.right; this.skipWhitespace()
      if (this.source[this.index] === "}") { this.index += 1; return Either.right(output) }
      if (this.source[this.index] !== ",") return fail("JSON_INVALID", "object member separator is missing")
      this.index += 1; this.skipWhitespace()
    }
  }

  private skipWhitespace(): void {
    while (isWhitespace(this.source[this.index] ?? "")) this.index += 1
  }
}

const encodeString = (value: string): string => {
  let output = "\""
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    const character = value[index] as string
    switch (character) {
      case "\"": output += "\\\""; break
      case "\\": output += "\\\\"; break
      case "\b": output += "\\b"; break
      case "\f": output += "\\f"; break
      case "\n": output += "\\n"; break
      case "\r": output += "\\r"; break
      case "\t": output += "\\t"; break
      default: output += code < 0x20 ? `\\u${code.toString(16).padStart(4, "0")}` : character
    }
  }
  return `${output}\"`
}

const canonicalize = (
  value: unknown,
  depth: number,
  nodes: { value: number },
  ancestors: ReadonlySet<object>
): Either.Either<string, Dnrd5PlanJsonError> => {
  if (depth > HSWM_DNRD5_PLAN_JSON_V1_MAX_DEPTH) return fail("DEPTH_LIMIT_EXCEEDED", "plan value nesting exceeds the v1 bound")
  nodes.value += 1
  if (nodes.value > HSWM_DNRD5_PLAN_JSON_V1_MAX_NODES) return fail("NODE_LIMIT_EXCEEDED", "plan value node count exceeds the v1 bound")
  if (value === null) return Either.right("null")
  if (typeof value === "boolean") return Either.right(value ? "true" : "false")
  if (typeof value === "string") return hasLoneSurrogate(value) ? fail("STRING_INVALID", "value string contains a lone surrogate") : Either.right(encodeString(value))
  if (typeof value === "number") return Number.isSafeInteger(value) && !Object.is(value, -0) ? Either.right(String(value)) : fail("NUMBER_INVALID", "value number must be a safe integer other than -0")
  if (typeof value !== "object") return fail("VALUE_INVALID", "plan JSON excludes this value type")
  if (ancestors.has(value)) return fail("VALUE_INVALID", "plan JSON value contains a cycle")
  const next = new Set(ancestors); next.add(value)
  if (Array.isArray(value)) {
    const ownKeys = Object.keys(value); const names = Object.getOwnPropertyNames(value)
    if (ownKeys.length !== value.length || names.length !== value.length + 1 || names.some((name) => name !== "length" && (!/^(0|[1-9][0-9]*)$/.test(name) || Number(name) >= value.length)) || Object.getOwnPropertySymbols(value).length > 0) {
      return fail("VALUE_INVALID", "plan JSON arrays cannot have holes, extra keys, or symbols")
    }
    const items: string[] = []
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.hasOwn(value, index)) return fail("VALUE_INVALID", "plan JSON arrays cannot have holes")
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
      if (descriptor === undefined || !("value" in descriptor) || !descriptor.enumerable) return fail("VALUE_INVALID", "plan JSON arrays cannot contain accessors")
      const item = canonicalize(descriptor.value, depth + 1, nodes, next)
      if (Either.isLeft(item)) return item
      items.push(item.right)
    }
    return Either.right(`[${items.join(",")}]`)
  }
  if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) return fail("VALUE_INVALID", "plan JSON objects must be plain objects")
  if (Object.getOwnPropertySymbols(value).length > 0) return fail("VALUE_INVALID", "plan JSON objects cannot contain symbol keys")
  const descriptors = Object.getOwnPropertyDescriptors(value)
  const keys = Object.keys(descriptors)
  for (const key of keys) {
    if (!isPlanKey(key)) return fail("KEY_INVALID", "plan object key is not printable bounded ASCII")
    const descriptor = descriptors[key]
    if (descriptor === undefined || !("value" in descriptor) || !descriptor.enumerable) return fail("VALUE_INVALID", "plan JSON objects cannot contain accessors")
  }
  const members: string[] = []
  for (const key of [...keys].sort()) {
    const descriptor = descriptors[key]
    if (descriptor === undefined || !("value" in descriptor)) return fail("VALUE_INVALID", "object descriptor disappeared during canonicalization")
    const member = canonicalize(descriptor.value, depth + 1, nodes, next)
    if (Either.isLeft(member)) return member
    members.push(`${encodeString(key)}:${member.right}`)
  }
  return Either.right(`{${members.join(",")}}`)
}

export const encodeDnrd5PlanJsonBytes = (value: unknown): Either.Either<Uint8Array, Dnrd5PlanJsonError> => {
  let encoded: Either.Either<string, Dnrd5PlanJsonError>
  try { encoded = canonicalize(value, 0, { value: 0 }, new Set()) }
  catch { return fail("VALUE_INVALID", "value could not be inspected without executing hostile object traps") }
  if (Either.isLeft(encoded)) return Either.left(encoded.left)
  const bytes = new TextEncoder().encode(encoded.right)
  return bytes.byteLength > HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES
    ? fail("BYTE_LIMIT_EXCEEDED", "plan JSON bytes exceed the v1 2,000,000-byte bound")
    : Either.right(bytes)
}

export const decodeDnrd5PlanJsonBytes = (bytes: Uint8Array): Either.Either<Dnrd5PlanJson, Dnrd5PlanJsonError> => {
  if (bytes.byteLength > HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES) return fail("BYTE_LIMIT_EXCEEDED", "plan JSON bytes exceed the v1 2,000,000-byte bound")
  let source: string
  try { source = new TextDecoder("utf-8", { fatal: true }).decode(bytes) }
  catch { return fail("UTF8_INVALID", "plan JSON input is not valid UTF-8") }
  const parsed = new Parser(source).parse()
  if (Either.isLeft(parsed)) return parsed
  const exact = encodeDnrd5PlanJsonBytes(parsed.right)
  if (Either.isLeft(exact)) return Either.left(exact.left)
  if (exact.right.byteLength !== bytes.byteLength || !exact.right.every((byte, index) => byte === bytes[index])) {
    return fail("BYTES_NOT_CANONICAL", "plan JSON bytes are not the exact v1 encoding")
  }
  return parsed
}

export const dnrd5PlanJsonSha256 = (value: unknown): Either.Either<string, Dnrd5PlanJsonError> => {
  const bytes = encodeDnrd5PlanJsonBytes(value)
  return Either.isLeft(bytes)
    ? Either.left(bytes.left)
    : Either.right(createHash("sha256").update(bytes.right).digest("hex"))
}
