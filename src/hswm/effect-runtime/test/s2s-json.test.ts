import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  S2S_JSON_MAX_DEPTH,
  parseS2SJsonBytes
} from "../src/s2s-json.js"

const bytes = (value: string): Uint8Array => new TextEncoder().encode(value)

const leftReason = (value: string): string => {
  const outcome = parseS2SJsonBytes(bytes(value))
  expect(Either.isLeft(outcome)).toBe(true)
  return Either.isLeft(outcome) ? outcome.left.reason : ""
}

it("parses and freezes the strict integer-only JSON dialect", () => {
  const outcome = parseS2SJsonBytes(
    bytes('{"z":[null,true,false,-7],"a":{"safe":9007199254740991}}\n')
  )
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isRight(outcome)) {
    expect(outcome.right).toEqual({
      z: [null, true, false, -7],
      a: { safe: Number.MAX_SAFE_INTEGER }
    })
    expect(Object.isFrozen(outcome.right)).toBe(true)
    const root = outcome.right as { readonly z: ReadonlyArray<unknown> }
    expect(Object.isFrozen(root.z)).toBe(true)
    expect(Object.getPrototypeOf(outcome.right)).toBe(null)
  }
})

it("rejects duplicate decoded keys including escaped aliases", () => {
  expect(leftReason('{"key":1,"key":2}')).toBe("DUPLICATE_OBJECT_KEY")
  expect(leftReason('{"a":1,"\\u0061":2}')).toBe("DUPLICATE_OBJECT_KEY")
  expect(leftReason('{"__proto__":1,"__proto__":2}')).toBe(
    "DUPLICATE_OBJECT_KEY"
  )
})

it("rejects lossy and non-integer number forms", () => {
  expect(leftReason("9007199254740992")).toBe("NON_SAFE_INTEGER")
  expect(leftReason("-0")).toBe("NON_SAFE_INTEGER")
  expect(leftReason("1.0")).toBe("UNSUPPORTED_NUMBER")
  expect(leftReason("1e3")).toBe("UNSUPPORTED_NUMBER")
  expect(leftReason("01")).toBe("INVALID_JSON")
})

it("rejects invalid UTF-8, BOMs, unpaired surrogates, and control text", () => {
  const invalidUtf8 = parseS2SJsonBytes(Uint8Array.from([0xc3, 0x28]))
  expect(Either.isLeft(invalidUtf8)).toBe(true)
  if (Either.isLeft(invalidUtf8)) {
    expect(invalidUtf8.left.reason).toBe("INVALID_UTF8")
  }
  expect(leftReason("\ufeff{}")).toBe("INVALID_JSON")
  expect(leftReason('"\\ud800"')).toBe("INVALID_JSON")
  expect(leftReason('"\\udc00"')).toBe("INVALID_JSON")
  expect(leftReason('"line\nfeed"')).toBe("INVALID_JSON")
  const supplementary = parseS2SJsonBytes(bytes('"\\ud83d\\ude80"'))
  expect(Either.isRight(supplementary)).toBe(true)
  if (Either.isRight(supplementary)) expect(supplementary.right).toBe("🚀")
})

it("rejects malformed containers and trailing data", () => {
  for (const value of ["", "[1,]", '{"a":1,}', "[1 2]", "{}{}", "{a:1}"]) {
    expect(leftReason(value)).toBe("INVALID_JSON")
  }
})

it("enforces byte and nesting bounds before accepting a value", () => {
  const oversized = parseS2SJsonBytes(bytes("[0]"), 2)
  expect(Either.isLeft(oversized)).toBe(true)
  if (Either.isLeft(oversized)) {
    expect(oversized.left.reason).toBe("BYTE_LIMIT_EXCEEDED")
  }
  const nested = `${"[".repeat(S2S_JSON_MAX_DEPTH + 2)}0${"]".repeat(
    S2S_JSON_MAX_DEPTH + 2
  )}`
  expect(leftReason(nested)).toBe("DEPTH_LIMIT_EXCEEDED")
})

it("rejects exotic or shared byte containers", () => {
  const exotic = bytes("{}")
  Object.defineProperty(exotic, Symbol.iterator, {
    value: Uint8Array.prototype[Symbol.iterator]
  })
  const exoticOutcome = parseS2SJsonBytes(exotic)
  expect(Either.isLeft(exoticOutcome)).toBe(true)
  if (Either.isLeft(exoticOutcome)) {
    expect(exoticOutcome.left.reason).toBe("INVALID_INPUT")
  }

  if (typeof SharedArrayBuffer !== "undefined") {
    const shared = new Uint8Array(new SharedArrayBuffer(2))
    shared.set(bytes("{}"))
    const sharedOutcome = parseS2SJsonBytes(shared)
    expect(Either.isLeft(sharedOutcome)).toBe(true)
    if (Either.isLeft(sharedOutcome)) {
      expect(sharedOutcome.left.reason).toBe("INVALID_INPUT")
    }
  }
})

it("returns typed invalid input for proxies and byte metadata accessors", () => {
  const proxy = new Proxy(bytes("{}"), {})
  let proxyOutcome: ReturnType<typeof parseS2SJsonBytes> | undefined
  expect(() => {
    proxyOutcome = parseS2SJsonBytes(proxy)
  }).not.toThrow()
  expect(proxyOutcome !== undefined && Either.isLeft(proxyOutcome)).toBe(true)
  if (proxyOutcome !== undefined && Either.isLeft(proxyOutcome)) {
    expect(proxyOutcome.left.reason).toBe("INVALID_INPUT")
  }

  let accessorRead = false
  const accessor = bytes("{}")
  Object.defineProperty(accessor, "byteLength", {
    configurable: true,
    get: () => {
      accessorRead = true
      throw new Error("must not read")
    }
  })
  const accessorOutcome = parseS2SJsonBytes(accessor)
  expect(Either.isLeft(accessorOutcome)).toBe(true)
  if (Either.isLeft(accessorOutcome)) {
    expect(accessorOutcome.left.reason).toBe("INVALID_INPUT")
  }
  expect(accessorRead).toBe(false)

  const trapped = new Proxy(bytes("{}"), {
    ownKeys: () => {
      throw new Error("hostile ownKeys trap")
    }
  })
  expect(() => parseS2SJsonBytes(trapped)).not.toThrow()
  const trappedOutcome = parseS2SJsonBytes(trapped)
  expect(Either.isLeft(trappedOutcome)).toBe(true)
})
