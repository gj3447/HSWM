import { createHash } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  type CanonicalJsonError,
  HSWM_CANONICAL_JSON_V1_MAX_BYTES,
  canonicalJsonBytes,
  canonicalJsonSha256,
  decodeCanonicalJsonBytes
} from "../src/canonical-atom-v2-json.js"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)

const expectLeftCode = <A>(
  value: Either.Either<A, CanonicalJsonError>,
  code: string
): void => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isLeft(value)) expect(value.left.code).toBe(code)
}

it("decodes bounded UTF-8 JSON and rejects duplicate keys before object materialization", () => {
  const decoded = decodeCanonicalJsonBytes(utf8('{"a":[true,null,"x"],"b":0}'))
  expect(decoded).toEqual(Either.right({ a: [true, null, "x"], b: 0 }))

  expectLeftCode(decodeCanonicalJsonBytes(utf8('{"a":1,"a":2}')), "DUPLICATE_KEY")
  expectLeftCode(decodeCanonicalJsonBytes(utf8('{"a":1,"\\u0061":2}')), "DUPLICATE_KEY")
  expectLeftCode(decodeCanonicalJsonBytes(utf8('{"__proto__":1,"__proto__":2}')), "DUPLICATE_KEY")
})

it("rejects malformed UTF-8, non-integer JSON numbers, -0, lone surrogates, and excess bytes", () => {
  expectLeftCode(decodeCanonicalJsonBytes(new Uint8Array([0xc3, 0x28])), "UTF8_INVALID")
  expectLeftCode(decodeCanonicalJsonBytes(utf8("1.5")), "NUMBER_INVALID")
  expectLeftCode(decodeCanonicalJsonBytes(utf8("1e3")), "NUMBER_INVALID")
  expectLeftCode(decodeCanonicalJsonBytes(utf8("-0")), "NUMBER_INVALID")
  expectLeftCode(decodeCanonicalJsonBytes(utf8("9007199254740992")), "NUMBER_INVALID")
  expectLeftCode(decodeCanonicalJsonBytes(utf8('"\\ud800"')), "STRING_INVALID")
  expectLeftCode(
    decodeCanonicalJsonBytes(new Uint8Array(HSWM_CANONICAL_JSON_V1_MAX_BYTES + 1)),
    "BYTE_LIMIT_EXCEEDED"
  )
})

it("emits no-whitespace canonical UTF-8 with UTF-16 lexical key ordering", () => {
  const value = {
    z: "line\nquote\"",
    a: 1,
    "\ud83d\ude00": true,
    "\uffff": null
  }
  const bytes = canonicalJsonBytes(value)
  expect(bytes).toEqual(Either.right(utf8('{"a":1,"z":"line\\nquote\\\"","😀":true,"￿":null}')))
  if (Either.isLeft(bytes)) return
  expect(new TextDecoder().decode(bytes.right).endsWith("\n")).toBe(false)
  expect(new TextDecoder().decode(bytes.right)).not.toContain(" ")

  const roundTrip = decodeCanonicalJsonBytes(bytes.right)
  expect(Either.isRight(roundTrip)).toBe(true)
})

it("hashes exactly the canonical bytes", () => {
  const bytes = canonicalJsonBytes({ b: 2, a: 1 })
  const digest = canonicalJsonSha256({ a: 1, b: 2 })
  expect(Either.isRight(bytes)).toBe(true)
  expect(Either.isRight(digest)).toBe(true)
  if (Either.isLeft(bytes) || Either.isLeft(digest)) return
  expect(digest.right).toBe(createHash("sha256").update(bytes.right).digest("hex"))
})

it("rejects non-JSON runtime values without invoking accessors", () => {
  const cycle: { self?: unknown } = {}
  cycle.self = cycle
  const sparse = ["a", , "c"]
  const accessor = Object.defineProperty({}, "x", {
    enumerable: true,
    get: () => {
      throw new Error("must not execute")
    }
  })
  const hidden = Object.defineProperty({ visible: true }, "secret", {
    value: 1,
    enumerable: false
  })
  const arrayWithHiddenKey = Object.defineProperty(["x"], "secret", {
    value: 1,
    enumerable: false
  })

  const invalid: ReadonlyArray<unknown> = [
    undefined,
    Symbol("x"),
    1n,
    new Date(),
    cycle,
    sparse,
    accessor,
    hidden,
    arrayWithHiddenKey,
    { [Symbol("x")]: 1 }
  ]
  for (const value of invalid) expectLeftCode(canonicalJsonBytes(value), "VALUE_INVALID")
  for (const value of [1.25, Number.NaN, Number.POSITIVE_INFINITY]) {
    expectLeftCode(canonicalJsonBytes(value), "NUMBER_INVALID")
  }
  expectLeftCode(canonicalJsonBytes(-0), "NUMBER_INVALID")
  expectLeftCode(canonicalJsonBytes("\ud800"), "STRING_INVALID")
  expectLeftCode(canonicalJsonBytes({ "\ud800": true }), "STRING_INVALID")

  const hostile = new Proxy(
    {},
    {
      getPrototypeOf: () => {
        throw new Error("must become an Either failure")
      }
    }
  )
  expectLeftCode(canonicalJsonBytes(hostile), "VALUE_INVALID")
})

it("enforces depth and node bounds for both decode and canonicalize", () => {
  let nested: unknown = null
  for (let index = 0; index < 130; index += 1) nested = [nested]
  expectLeftCode(canonicalJsonBytes(nested), "DEPTH_LIMIT_EXCEEDED")
  expectLeftCode(decodeCanonicalJsonBytes(utf8("[".repeat(130) + "null" + "]".repeat(130))), "DEPTH_LIMIT_EXCEEDED")
})
