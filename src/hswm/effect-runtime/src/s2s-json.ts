import { Data, Either } from "effect"

/**
 * Deliberately narrower than arbitrary JSON. The live control plane only needs
 * exact identifiers, timestamps, booleans, nulls, arrays, and safe integer API
 * counters. Rejecting fractional/exponent numbers avoids accepting a value that
 * JavaScript may round before it reaches a schema projection.
 */
export type S2SJson =
  | null
  | boolean
  | number
  | string
  | ReadonlyArray<S2SJson>
  | { readonly [key: string]: S2SJson }

export const S2S_JSON_DEFAULT_MAX_BYTES = 8 * 1_048_576
export const S2S_JSON_MAX_DEPTH = 64 as const
export const S2S_JSON_MAX_NODES = 1_000_000 as const

export class S2SJsonParseError extends Data.TaggedError("S2SJsonParseError")<{
  readonly reason:
    | "BYTE_LIMIT_EXCEEDED"
    | "DEPTH_LIMIT_EXCEEDED"
    | "DUPLICATE_OBJECT_KEY"
    | "INVALID_INPUT"
    | "INVALID_JSON"
    | "INVALID_UTF8"
    | "NODE_LIMIT_EXCEEDED"
    | "NON_SAFE_INTEGER"
    | "UNSUPPORTED_NUMBER"
  /** UTF-16 code-unit offset, or zero for a byte/input-level rejection. */
  readonly offset: number
  readonly detail: string
}> {}

interface ParserState {
  readonly text: string
  offset: number
  nodes: number
}

const parseError = (
  reason: S2SJsonParseError["reason"],
  offset: number,
  detail: string
): S2SJsonParseError => new S2SJsonParseError({ reason, offset, detail })

const isWhitespace = (code: number): boolean =>
  code === 0x20 || code === 0x09 || code === 0x0a || code === 0x0d

const skipWhitespace = (state: ParserState): void => {
  while (
    state.offset < state.text.length &&
    isWhitespace(state.text.charCodeAt(state.offset))
  ) {
    state.offset += 1
  }
}

const countNode = (state: ParserState): void => {
  state.nodes += 1
  if (state.nodes > S2S_JSON_MAX_NODES) {
    throw parseError(
      "NODE_LIMIT_EXCEEDED",
      state.offset,
      "JSON node count exceeds the fixed control-plane bound"
    )
  }
}

const hasUnpairedSurrogate = (value: string): boolean => {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code >= 0xd800 && code <= 0xdbff) {
      const low = value.charCodeAt(index + 1)
      if (!(low >= 0xdc00 && low <= 0xdfff)) return true
      index += 1
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true
    }
  }
  return false
}

const parseString = (state: ParserState): string => {
  const start = state.offset
  state.offset += 1
  while (state.offset < state.text.length) {
    const code = state.text.charCodeAt(state.offset)
    if (code === 0x22) {
      state.offset += 1
      let decoded: unknown
      try {
        decoded = JSON.parse(state.text.slice(start, state.offset))
      } catch {
        throw parseError(
          "INVALID_JSON",
          start,
          "string token is not valid JSON"
        )
      }
      if (typeof decoded !== "string" || hasUnpairedSurrogate(decoded)) {
        throw parseError(
          "INVALID_JSON",
          start,
          "string contains an unpaired Unicode surrogate"
        )
      }
      return decoded
    }
    if (code < 0x20) {
      throw parseError(
        "INVALID_JSON",
        state.offset,
        "string contains an unescaped control character"
      )
    }
    if (code === 0x5c) {
      const escapeOffset = state.offset
      state.offset += 1
      if (state.offset >= state.text.length) {
        throw parseError(
          "INVALID_JSON",
          escapeOffset,
          "string ends inside an escape sequence"
        )
      }
      const escape = state.text[state.offset]
      if (escape === "u") {
        const digits = state.text.slice(state.offset + 1, state.offset + 5)
        if (digits.length !== 4 || !/^[0-9a-fA-F]{4}$/.test(digits)) {
          throw parseError(
            "INVALID_JSON",
            escapeOffset,
            "Unicode escape must contain exactly four hexadecimal digits"
          )
        }
        state.offset += 5
        continue
      }
      if (
        escape !== '"' &&
        escape !== "\\" &&
        escape !== "/" &&
        escape !== "b" &&
        escape !== "f" &&
        escape !== "n" &&
        escape !== "r" &&
        escape !== "t"
      ) {
        throw parseError(
          "INVALID_JSON",
          escapeOffset,
          "string contains an unsupported escape sequence"
        )
      }
      state.offset += 1
      continue
    }
    state.offset += 1
  }
  throw parseError("INVALID_JSON", start, "unterminated string")
}

const parseLiteral = (
  state: ParserState,
  literal: "true" | "false" | "null",
  value: boolean | null
): boolean | null => {
  if (!state.text.startsWith(literal, state.offset)) {
    throw parseError("INVALID_JSON", state.offset, `expected ${literal}`)
  }
  state.offset += literal.length
  return value
}

const isDigit = (code: number): boolean => code >= 0x30 && code <= 0x39

const parseInteger = (state: ParserState): number => {
  const start = state.offset
  if (state.text.charCodeAt(state.offset) === 0x2d) state.offset += 1
  if (state.offset >= state.text.length) {
    throw parseError("INVALID_JSON", start, "number has no integer digits")
  }
  const first = state.text.charCodeAt(state.offset)
  if (first === 0x30) {
    state.offset += 1
    if (isDigit(state.text.charCodeAt(state.offset))) {
      throw parseError("INVALID_JSON", start, "number contains a leading zero")
    }
  } else if (first >= 0x31 && first <= 0x39) {
    state.offset += 1
    while (isDigit(state.text.charCodeAt(state.offset))) state.offset += 1
  } else {
    throw parseError("INVALID_JSON", start, "number has no integer digits")
  }
  const suffix = state.text[state.offset]
  if (suffix === "." || suffix === "e" || suffix === "E") {
    throw parseError(
      "UNSUPPORTED_NUMBER",
      start,
      "fractional and exponent-form numbers are outside the control-plane dialect"
    )
  }
  const token = state.text.slice(start, state.offset)
  const value = Number(token)
  if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
    throw parseError(
      "NON_SAFE_INTEGER",
      start,
      "integer cannot be represented exactly as a non-negative-zero JavaScript number"
    )
  }
  return value
}

const parseValue = (state: ParserState, depth: number): S2SJson => {
  if (depth > S2S_JSON_MAX_DEPTH) {
    throw parseError(
      "DEPTH_LIMIT_EXCEEDED",
      state.offset,
      "JSON nesting exceeds the fixed control-plane bound"
    )
  }
  skipWhitespace(state)
  countNode(state)
  const code = state.text.charCodeAt(state.offset)
  if (code === 0x22) return parseString(state)
  if (code === 0x7b) return parseObject(state, depth)
  if (code === 0x5b) return parseArray(state, depth)
  if (code === 0x74) return parseLiteral(state, "true", true)
  if (code === 0x66) return parseLiteral(state, "false", false)
  if (code === 0x6e) return parseLiteral(state, "null", null)
  if (code === 0x2d || isDigit(code)) return parseInteger(state)
  throw parseError("INVALID_JSON", state.offset, "expected a JSON value")
}

const parseArray = (state: ParserState, depth: number): ReadonlyArray<S2SJson> => {
  state.offset += 1
  skipWhitespace(state)
  const values: Array<S2SJson> = []
  if (state.text.charCodeAt(state.offset) === 0x5d) {
    state.offset += 1
    return Object.freeze(values)
  }
  while (true) {
    values.push(parseValue(state, depth + 1))
    skipWhitespace(state)
    const code = state.text.charCodeAt(state.offset)
    if (code === 0x5d) {
      state.offset += 1
      return Object.freeze(values)
    }
    if (code !== 0x2c) {
      throw parseError("INVALID_JSON", state.offset, "expected ',' or ']'")
    }
    state.offset += 1
    skipWhitespace(state)
    if (state.text.charCodeAt(state.offset) === 0x5d) {
      throw parseError("INVALID_JSON", state.offset, "trailing comma in array")
    }
  }
}

const parseObject = (
  state: ParserState,
  depth: number
): { readonly [key: string]: S2SJson } => {
  state.offset += 1
  skipWhitespace(state)
  const output: Record<string, S2SJson> = Object.create(null)
  const seen = new Set<string>()
  if (state.text.charCodeAt(state.offset) === 0x7d) {
    state.offset += 1
    return Object.freeze(output)
  }
  while (true) {
    if (state.text.charCodeAt(state.offset) !== 0x22) {
      throw parseError("INVALID_JSON", state.offset, "object key must be a string")
    }
    const keyOffset = state.offset
    const key = parseString(state)
    if (seen.has(key)) {
      throw parseError(
        "DUPLICATE_OBJECT_KEY",
        keyOffset,
        "object contains a duplicate decoded key"
      )
    }
    seen.add(key)
    skipWhitespace(state)
    if (state.text.charCodeAt(state.offset) !== 0x3a) {
      throw parseError("INVALID_JSON", state.offset, "expected ':' after object key")
    }
    state.offset += 1
    output[key] = parseValue(state, depth + 1)
    skipWhitespace(state)
    const code = state.text.charCodeAt(state.offset)
    if (code === 0x7d) {
      state.offset += 1
      return Object.freeze(output)
    }
    if (code !== 0x2c) {
      throw parseError("INVALID_JSON", state.offset, "expected ',' or '}'")
    }
    state.offset += 1
    skipWhitespace(state)
    if (state.text.charCodeAt(state.offset) === 0x7d) {
      throw parseError("INVALID_JSON", state.offset, "trailing comma in object")
    }
  }
}

const isPlainUint8Array = (input: unknown): input is Uint8Array =>
  input instanceof Uint8Array &&
  Object.getPrototypeOf(input) === Uint8Array.prototype &&
  Object.getOwnPropertySymbols(input).length === 0 &&
  Object.getOwnPropertyDescriptor(input, "byteLength") === undefined &&
  Object.getOwnPropertyDescriptor(input, "buffer") === undefined &&
  !(typeof SharedArrayBuffer !== "undefined" &&
    input.buffer instanceof SharedArrayBuffer)

export const parseS2SJsonBytes = (
  input: unknown,
  maximumBytes: number = S2S_JSON_DEFAULT_MAX_BYTES
): Either.Either<S2SJson, S2SJsonParseError> => {
  let snapshot: Uint8Array
  try {
    if (
      !isPlainUint8Array(input) ||
      !Number.isSafeInteger(maximumBytes) ||
      maximumBytes < 1 ||
      maximumBytes > S2S_JSON_DEFAULT_MAX_BYTES
    ) {
      return Either.left(
        parseError(
          "INVALID_INPUT",
          0,
          "input must be a plain unshared Uint8Array and maximumBytes must be within the fixed bound"
        )
      )
    }
    if (input.byteLength > maximumBytes) {
      return Either.left(
        parseError(
          "BYTE_LIMIT_EXCEEDED",
          0,
          "JSON input exceeds the selected fixed byte bound"
        )
      )
    }
    snapshot = new Uint8Array(input)
  } catch {
    return Either.left(
      parseError(
        "INVALID_INPUT",
        0,
        "JSON input introspection or snapshot failed closed"
      )
    )
  }
  let text: string
  try {
    text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(
      snapshot
    )
  } catch {
    return Either.left(
      parseError("INVALID_UTF8", 0, "JSON input is not canonical UTF-8 text")
    )
  }
  if (text.charCodeAt(0) === 0xfeff) {
    return Either.left(
      parseError("INVALID_JSON", 0, "JSON input must not begin with a BOM")
    )
  }
  const state: ParserState = { text, offset: 0, nodes: 0 }
  try {
    const value = parseValue(state, 0)
    skipWhitespace(state)
    if (state.offset !== text.length) {
      throw parseError(
        "INVALID_JSON",
        state.offset,
        "unexpected data follows the root JSON value"
      )
    }
    return Either.right(value)
  } catch (error: unknown) {
    return Either.left(
      error instanceof S2SJsonParseError
        ? error
        : parseError("INVALID_JSON", state.offset, "JSON parser failed closed")
    )
  }
}
