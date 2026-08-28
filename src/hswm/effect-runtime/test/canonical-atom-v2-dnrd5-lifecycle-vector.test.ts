import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  canonicalJsonBytes,
  canonicalJsonSha256
} from "../src/canonical-atom-v2-json.js"
import {
  DNRD5_LIFECYCLE_VECTOR_TERMINAL,
  validateDnrd5LifecycleVectorBytes
} from "../src/canonical-atom-v2-dnrd5-lifecycle-vector.js"

const VECTOR_URL = new URL(
  "../../../../_research/dnrd5/vectors/lifecycle_contract_v1.json",
  import.meta.url
)
const VECTOR_SHA256 = "179225541585267214a6cc5b358551c39597c66e546adf46bebad121550763cc"
const LIFECYCLE_SHA256 = "8b4c5fcd2333fe5c1a499983837f7eaa33ba764ebddf2bca14cb94366ff0e9fc"
const raw = () => new Uint8Array(readFileSync(VECTOR_URL))
const encoded = (value: unknown): Uint8Array => {
  const result = canonicalJsonBytes(value)
  if (Either.isLeft(result)) throw new Error(result.left.detail)
  return result.right
}

it("matches the independent Python UTF-16 ordering and hash known answer", () => {
  const value = { "😀": 1, "\uffff": 2 }
  const bytes = encoded(value)
  const hash = canonicalJsonSha256(value)
  expect(bytes).toEqual(
    new TextEncoder().encode('{"😀":1,"\uffff":2}')
  )
  expect(hash).toEqual(
    Either.right("c6b1b96b618d8be475f379fe69c6646b44d7a5d3c01630c43509562f09d1024b")
  )
})

it("consumes the exact no-suffix shared vector and rederives every descriptor", () => {
  const bytes = raw()
  expect(bytes.at(-1)).not.toBe(0x0a)
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(VECTOR_SHA256)
  const result = validateDnrd5LifecycleVectorBytes(bytes)
  if (Either.isLeft(result)) {
    throw new Error(`${result.left.code}: ${result.left.detail}`)
  }
  expect(Either.isRight(result)).toBe(true)
  expect(result.right.vectorSha256).toBe(VECTOR_SHA256)
  expect(result.right.lifecycleSha256).toBe(LIFECYCLE_SHA256)
  expect(result.right.artifactCount).toBe(59)
  expect(result.right.generationCallCount).toBe(9)
  expect(result.right.terminal).toBe(DNRD5_LIFECYCLE_VECTOR_TERMINAL)
  expect(result.right.productionContentValidated).toBe(false)
  expect(result.right.occurrenceEstablished).toBe(false)
  expect(result.right.scientificTerminalIssued).toBe(false)
  expect(Object.isFrozen(result.right.vector.lifecycle.events[0]?.artifacts[0]?.content)).toBe(true)
})

it("rejects root, terminal, lifecycle, descriptor, and content-row drift", () => {
  const source = JSON.parse(new TextDecoder().decode(raw())) as any
  const mutations: ReadonlyArray<(value: any) => void> = [
    (value) => { value.extra = true },
    (value) => { value.expectedTerminal = "CAUSAL_MACROPLASTICITY_GO" },
    (value) => { value.lifecycle.blockId = "DNRD5-BLOCK-0000" },
    (value) => { value.lifecycle.events[0].manifestSha256 = "0".repeat(64) },
    (value) => { value.lifecycle.events[0].artifacts[0].content.sha256 = "0".repeat(64) },
    (value) => { value.artifactContents[0].content.kind = "BLOCK_SPEC" },
    (value) => { value.artifactContents.reverse() }
  ]
  for (const mutate of mutations) {
    const value = structuredClone(source)
    mutate(value)
    expect(Either.isLeft(validateDnrd5LifecycleVectorBytes(encoded(value)))).toBe(true)
  }
})

it("rejects transport suffixes and duplicate keys before semantic validation", () => {
  const withLf = new Uint8Array([...raw(), 0x0a])
  expect(Either.isLeft(validateDnrd5LifecycleVectorBytes(withLf))).toBe(true)
  expect(
    Either.isLeft(
      validateDnrd5LifecycleVectorBytes(
        new TextEncoder().encode('{"_tag":"x","_tag":"x"}')
      )
    )
  ).toBe(true)
})
