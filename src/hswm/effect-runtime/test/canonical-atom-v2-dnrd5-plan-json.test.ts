import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_DNRD5_PLAN_JSON_V1_CONTRACT_VERSION,
  HSWM_DNRD5_PLAN_JSON_V1_MAX_DEPTH,
  HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES,
  HSWM_DNRD5_PLAN_JSON_V1_MAX_KEY_BYTES,
  HSWM_DNRD5_PLAN_JSON_V1_MAX_NODES,
  HSWM_DNRD5_PLAN_JSON_V1_MIN_KEY_BYTES,
  type Dnrd5PlanJsonError,
  decodeDnrd5PlanJsonBytes,
  dnrd5PlanJsonSha256,
  encodeDnrd5PlanJsonBytes
} from "../src/canonical-atom-v2-dnrd5-plan-json.js"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const KAT_URL = new URL(
  "../../../../_research/dnrd5/vectors/plan_json_v1_kat.json",
  import.meta.url
)
const KAT_SHA256 = "012dcc2ebf71dd6b54dfceec9aeeb72673961c64830694ab7bb7c678deb6051f"
const katBytes = readFileSync(KAT_URL)
const kat = JSON.parse(katBytes.toString("utf8")) as {
  readonly schema_version: string
  readonly contract: {
    readonly contract_version: string
    readonly key_domain: string
    readonly key_max_length: number
    readonly key_min_length: number
    readonly max_bytes: number
    readonly max_depth: number
    readonly max_nodes: number
    readonly value_string_domain: string
  }
  readonly generated_over_1mib_case: {
    readonly kind: string
    readonly key: string
    readonly character: string
    readonly repeat_count: number
    readonly expected_byte_length: number
    readonly expected_sha256: string
  }
  readonly full_plan_known_answers: ReadonlyArray<{
    readonly expected_byte_length: number
    readonly expected_sha256: string
    readonly expected_study_plan_sha256: string
    readonly future_randomness_hex: string
    readonly study_binding_sha256: string
  }>
  readonly invalid_raw: ReadonlyArray<{ readonly id: string; readonly raw_utf8: string }>
  readonly valid: ReadonlyArray<{ readonly id: string; readonly value: unknown; readonly canonical_utf8: string; readonly sha256: string }>
}

const expectLeftCode = <A>(value: Either.Either<A, Dnrd5PlanJsonError>, code: string): void => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isLeft(value)) expect(value.left.code).toBe(code)
}

it("encodes exact compact UTF-8 with printable-ASCII object keys", () => {
  const value = {
    z: "line\nquote\"é",
    "fork-0123456789abcdef0123456789abcdef": { a: -7, b: [true, null, 0] },
    A: "😀"
  }
  const encoded = encodeDnrd5PlanJsonBytes(value)
  expect(encoded).toEqual(Either.right(utf8('{"A":"😀","fork-0123456789abcdef0123456789abcdef":{"a":-7,"b":[true,null,0]},"z":"line\\nquote\\\"é"}')))
  if (Either.isLeft(encoded)) return
  expect(decodeDnrd5PlanJsonBytes(encoded.right)).toEqual(Either.right(value))
  expect(dnrd5PlanJsonSha256(value)).toEqual(
    Either.right(createHash("sha256").update(encoded.right).digest("hex"))
  )
})

it("consumes the shared Python/TypeScript plan-json v1 known-answer corpus", () => {
  expect(createHash("sha256").update(katBytes).digest("hex")).toBe(KAT_SHA256)
  expect(kat.schema_version).toBe("hswm-dnrd5-plan-json-kat/v1")
  expect(kat.contract).toEqual({
    contract_version: HSWM_DNRD5_PLAN_JSON_V1_CONTRACT_VERSION,
    key_domain: "PRINTABLE_ASCII_U0020_THROUGH_U007E",
    key_max_length: HSWM_DNRD5_PLAN_JSON_V1_MAX_KEY_BYTES,
    key_min_length: HSWM_DNRD5_PLAN_JSON_V1_MIN_KEY_BYTES,
    max_bytes: HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES,
    max_depth: HSWM_DNRD5_PLAN_JSON_V1_MAX_DEPTH,
    max_nodes: HSWM_DNRD5_PLAN_JSON_V1_MAX_NODES,
    value_string_domain: "UNICODE_SCALARS_NO_LONE_SURROGATES"
  })
  expect(kat.full_plan_known_answers).toHaveLength(2)
  for (const row of kat.valid) {
    const encoded = encodeDnrd5PlanJsonBytes(row.value)
    expect(encoded).toEqual(Either.right(utf8(row.canonical_utf8)))
    expect(dnrd5PlanJsonSha256(row.value)).toEqual(Either.right(row.sha256))
    expect(decodeDnrd5PlanJsonBytes(utf8(row.canonical_utf8))).toEqual(Either.right(row.value))
  }
  for (const row of kat.invalid_raw) {
    expect(Either.isLeft(decodeDnrd5PlanJsonBytes(utf8(row.raw_utf8))), row.id).toBe(true)
  }
})

it("strictly rejects noncanonical raw forms, duplicate keys, and invalid object keys", () => {
  const invalid: ReadonlyArray<readonly [string, string]> = [
    ['{ "a":1}', "BYTES_NOT_CANONICAL"],
    ['{"a":1}\n', "BYTES_NOT_CANONICAL"],
    ['{"b":1,"a":2}', "BYTES_NOT_CANONICAL"],
    ['{"a":1,"a":2}', "DUPLICATE_KEY"],
    ['{"a":1,"\\u0061":2}', "DUPLICATE_KEY"],
    ['{"é":1}', "KEY_INVALID"],
    ['{"\\u00e9":1}', "KEY_INVALID"],
    ['{"":1}', "KEY_INVALID"],
    ['{"a":1.0}', "NUMBER_INVALID"],
    ['{"a":1e0}', "NUMBER_INVALID"],
    ['{"a":-0}', "NUMBER_INVALID"],
    ['{"a":"\\u0062"}', "BYTES_NOT_CANONICAL"],
    ['{"a":"\\/"}', "BYTES_NOT_CANONICAL"]
  ]
  for (const [raw, code] of invalid) expectLeftCode(decodeDnrd5PlanJsonBytes(utf8(raw)), code)
  expectLeftCode(decodeDnrd5PlanJsonBytes(new Uint8Array([0xc3, 0x28])), "UTF8_INVALID")
})

it("refuses hostile or non-plan runtime values without executing accessors", () => {
  const cycle: { self?: unknown } = {}; cycle.self = cycle
  const accessor = Object.defineProperty({}, "a", { enumerable: true, get: () => { throw new Error("must not execute") } })
  const hidden = Object.defineProperty({ a: 1 }, "b", { value: 2, enumerable: false })
  const invalid: ReadonlyArray<unknown> = [
    undefined, Symbol("x"), 1n, new Date(), cycle, ["a", , "b"], accessor, hidden,
    { "é": 1 }, { [Symbol("x")]: 1 }, 1.25, Number.NaN, Number.POSITIVE_INFINITY, -0
  ]
  for (const value of invalid) expect(Either.isLeft(encodeDnrd5PlanJsonBytes(value))).toBe(true)
  expect(Either.isRight(encodeDnrd5PlanJsonBytes({ ["x".repeat(128)]: 1 }))).toBe(true)
  expectLeftCode(encodeDnrd5PlanJsonBytes({ ["x".repeat(129)]: 1 }), "KEY_INVALID")
  expectLeftCode(encodeDnrd5PlanJsonBytes("\ud800"), "STRING_INVALID")
})

it("allows a complete plan-sized payload above generic canonical-json/v1's 1 MiB boundary", () => {
  const generated = kat.generated_over_1mib_case
  expect(generated.kind).toBe("repeat_string_value")
  const value = { [generated.key]: generated.character.repeat(generated.repeat_count) }
  const encoded = encodeDnrd5PlanJsonBytes(value)
  expect(Either.isRight(encoded)).toBe(true)
  if (Either.isLeft(encoded)) return
  expect(encoded.right.byteLength).toBe(generated.expected_byte_length)
  expect(createHash("sha256").update(encoded.right).digest("hex")).toBe(generated.expected_sha256)
  expect(encoded.right.byteLength).toBeGreaterThan(1_048_576)
  expect(encoded.right.byteLength).toBeLessThanOrEqual(HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES)
  expect(decodeDnrd5PlanJsonBytes(encoded.right)).toEqual(Either.right(value))
})

it("enforces plan byte, depth, and node boundaries", () => {
  const exactLimit = { value: "x".repeat(HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES - utf8('{"value":""}').byteLength) }
  const exactBytes = encodeDnrd5PlanJsonBytes(exactLimit)
  expect(Either.isRight(exactBytes)).toBe(true)
  if (Either.isRight(exactBytes)) expect(exactBytes.right.byteLength).toBe(HSWM_DNRD5_PLAN_JSON_V1_MAX_BYTES)
  expectLeftCode(encodeDnrd5PlanJsonBytes({ value: `${exactLimit.value}x` }), "BYTE_LIMIT_EXCEEDED")
  let nested: unknown = null
  for (let index = 0; index < 128; index += 1) nested = [nested]
  expect(Either.isRight(encodeDnrd5PlanJsonBytes(nested))).toBe(true)
  nested = [nested]
  expectLeftCode(encodeDnrd5PlanJsonBytes(nested), "DEPTH_LIMIT_EXCEEDED")
  expect(Either.isRight(encodeDnrd5PlanJsonBytes(Array.from({ length: 99_999 }, () => 0)))).toBe(true)
  expectLeftCode(encodeDnrd5PlanJsonBytes(Array.from({ length: 100_000 }, () => 0)), "NODE_LIMIT_EXCEEDED")
})
