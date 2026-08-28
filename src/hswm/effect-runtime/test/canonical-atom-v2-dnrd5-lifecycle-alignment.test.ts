import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  validateDnrd5LifecycleAtomAlignment,
  type Dnrd5LifecycleAtomAlignmentError
} from "../src/canonical-atom-v2-dnrd5-lifecycle-alignment.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

const alignmentUrl = new URL(
  "../../../../_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json",
  import.meta.url
)
const lifecycleUrl = new URL(
  "../../../../_research/dnrd5/vectors/lifecycle_contract_v1.json",
  import.meta.url
)
const alignment = JSON.parse(readFileSync(alignmentUrl, "utf8")) as Record<string, unknown>
const alignmentBytes = new Uint8Array(readFileSync(alignmentUrl))
const lifecycleBytes = new Uint8Array(readFileSync(lifecycleUrl))
const clone = (): Record<string, any> => JSON.parse(JSON.stringify(alignment)) as Record<string, any>
const encoded = (value: unknown): Uint8Array => {
  const result = canonicalJsonBytes(value)
  if (Either.isLeft(result)) throw result.left
  return result.right
}
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const expectCode = (result: ReturnType<typeof validateDnrd5LifecycleAtomAlignment>, code: string): void => {
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect((result.left as Dnrd5LifecycleAtomAlignmentError).code).toBe(code)
}

it("independently binds exact lifecycle bytes, chronology, counts, schema and bounded claims", () => {
  const result = validateDnrd5LifecycleAtomAlignment(alignmentBytes, lifecycleBytes)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) return
  expect(result.right).toEqual({
    eventCount: 15,
    artifactCount: 59,
    artifactKindCount: 27,
    generationCallCount: 9,
    claimFlags: {
      canonicalAtomsBound: false,
      actualProductionBytesPresent: false,
      providerCallPresent: false,
      permitAdmissionOccurrenceLearningOrResult: false
    }
  })
})

it("fails closed for lifecycle bytes/root and lifecycle chronology mutations", () => {
  const changedBytes = Uint8Array.from(lifecycleBytes)
  changedBytes[0] = "[".charCodeAt(0)
  expectCode(validateDnrd5LifecycleAtomAlignment(alignmentBytes, changedBytes), "BYTES_INVALID")
  const root = clone()
  root["extra"] = true
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(root), lifecycleBytes), "ROOT_INVALID")
  const lifecycle = JSON.parse(new TextDecoder().decode(lifecycleBytes)) as Record<string, any>
  lifecycle["lifecycle"]["events"][0]["ordinal"] = 9
  const altered = encoded(lifecycle)
  const rebound = clone()
  rebound["lifecycleVectorSha256"] = sha256(altered)
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(rebound), altered), "LIFECYCLE_INVALID")
  const noncanonicalLifecycle = new Uint8Array([...lifecycleBytes, 0x20])
  const reboundNoncanonical = clone()
  reboundNoncanonical["lifecycleVectorSha256"] = sha256(noncanonicalLifecycle)
  expectCode(
    validateDnrd5LifecycleAtomAlignment(encoded(reboundNoncanonical), noncanonicalLifecycle),
    "BYTES_INVALID"
  )
  expectCode(
    validateDnrd5LifecycleAtomAlignment(new Uint8Array([...alignmentBytes, 0x20]), lifecycleBytes),
    "BYTES_INVALID"
  )
  const duplicate = new TextEncoder().encode(
    `{"_tag":"duplicate",${new TextDecoder().decode(alignmentBytes).slice(1)}`
  )
  expectCode(validateDnrd5LifecycleAtomAlignment(duplicate, lifecycleBytes), "BYTES_INVALID")
})

it("rejects declared count/order, schema binding, mapping, authority and nonclaim drift", () => {
  const count = clone()
  count["observedLifecycle"]["artifactCount"] = 58
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(count), lifecycleBytes), "COUNT_INVALID")
  const schema = clone()
  schema["canonicalSchemaSha256"] = "0".repeat(64)
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(schema), lifecycleBytes), "SCHEMA_INVALID")
  const mapping = clone()
  mapping["kindMappings"][7]["canonicalAtomCount"] = 4
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(mapping), lifecycleBytes), "MAPPING_INVALID")
  const authority = clone()
  authority["kindMappings"][0]["closureReady"] = true
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(authority), lifecycleBytes), "AUTHORITY_INVALID")
  const nonclaim = clone()
  nonclaim["hardNonclaims"] = []
  expectCode(validateDnrd5LifecycleAtomAlignment(encoded(nonclaim), lifecycleBytes), "NONCLAIM_INVALID")
})
