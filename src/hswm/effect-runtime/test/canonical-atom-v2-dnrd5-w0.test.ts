import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  makeCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "../src/canonical-atom-v2-content.js"
import {
  DNRD5_W0_STATUS,
  validateDnrd5W0ForkManifestBytes
} from "../src/canonical-atom-v2-dnrd5-w0.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)

const put = (
  content: Map<string, Uint8Array>,
  value: string
): CanonicalAtomV2ContentDescriptor => {
  const bytes = utf8(value)
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    "application/octet-stream",
    bytes
  )
  if (Either.isLeft(descriptor)) throw new Error(descriptor.left.detail)
  content.set(descriptor.right.sha256, bytes)
  return descriptor.right
}

const fixture = () => {
  const content = new Map<string, Uint8Array>()
  const state = put(content, "canonical-w0-state")
  const readset = put(content, "canonical-w0-behavior-readset")
  const journalHead = put(content, "durable-journal-head")
  const projectionPolicy = put(content, "projection-policy")
  const manifest = {
    _tag: "Dnrd5W0ForkManifest",
    contractVersion: "hswm-dnrd5-w0-four-fork-identity/v1",
    blockId: "DNRD5-BLOCK-0001",
    w0: {
      w0Id: "w0:block:0001",
      state,
      behaviorReadset: readset,
      journalHead,
      projectionPolicy
    },
    forks: [0, 1, 2, 3].map((index) => ({
      opaqueForkId: `opaque:fork:${index}`,
      w0Id: "w0:block:0001",
      state,
      behaviorReadset: readset,
      isolationReceipt: put(content, `isolation-receipt:${index}`),
      assignmentStatus: "UNASSIGNED"
    })),
    terminal: "CALLER_SUPPLIED_CONTENT_MAP_NOT_DURABLE_RECOVERY_OR_ISOLATION_PROOF"
  }
  const encoded = canonicalJsonBytes(manifest)
  if (Either.isLeft(encoded)) throw new Error(encoded.left.detail)
  return { content, manifest, bytes: encoded.right }
}

const validateFixture = (value: ReturnType<typeof fixture>) => {
  const encoded = canonicalJsonBytes(value.manifest)
  if (Either.isLeft(encoded)) throw new Error(encoded.left.detail)
  return validateDnrd5W0ForkManifestBytes(encoded.right, value.content)
}

it("verifies four pre-assignment forks against actual W0 state and readset bytes", () => {
  const value = fixture()
  const result = validateDnrd5W0ForkManifestBytes(value.bytes, value.content)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) return
  expect(result.right.status).toBe(DNRD5_W0_STATUS)
  expect(result.right.manifest.forks).toHaveLength(4)
  expect(Object.isFrozen(result.right.manifest.forks[0])).toBe(true)

  value.manifest.forks[0]!.w0Id = "w0:mutated"
  value.content.get(result.right.w0StateSha256)?.fill(0)
  expect(result.right.manifest.forks[0]!.w0Id).toBe("w0:block:0001")
  expect(result.right.w0StateSha256).not.toBe("0".repeat(64))
})

it("rejects missing, corrupt, nonidentical, and cross-W0 content bindings", () => {
  const missing = fixture()
  missing.content.delete(missing.manifest.w0.journalHead.sha256)
  expect(Either.isLeft(validateFixture(missing))).toBe(true)

  const corrupt = fixture()
  corrupt.content.set(corrupt.manifest.w0.state.sha256, utf8("corrupt"))
  expect(Either.isLeft(validateFixture(corrupt))).toBe(true)

  const nonidenticalState = fixture()
  nonidenticalState.manifest.forks[0]!.state = put(
    nonidenticalState.content,
    "different-state"
  )
  expect(Either.isLeft(validateFixture(nonidenticalState))).toBe(true)

  const nonidenticalReadset = fixture()
  nonidenticalReadset.manifest.forks[0]!.behaviorReadset = put(
    nonidenticalReadset.content,
    "different-readset"
  )
  expect(Either.isLeft(validateFixture(nonidenticalReadset))).toBe(true)

  const crossW0 = fixture()
  crossW0.manifest.forks[0]!.w0Id = "w0:other"
  expect(Either.isLeft(validateFixture(crossW0))).toBe(true)
})

it("rejects duplicate, unordered, arm-labelled, malformed, and noncanonical manifests", () => {
  const duplicate = fixture()
  duplicate.manifest.forks[1]!.opaqueForkId =
    duplicate.manifest.forks[0]!.opaqueForkId
  expect(Either.isLeft(validateFixture(duplicate))).toBe(true)

  const unordered = fixture()
  unordered.manifest.forks.reverse()
  expect(Either.isLeft(validateFixture(unordered))).toBe(true)

  const armLabel = fixture()
  armLabel.manifest.forks[0]!.opaqueForkId = "opaque:fork:active"
  expect(Either.isLeft(validateFixture(armLabel))).toBe(true)

  const extra = fixture()
  ;(extra.manifest.w0 as typeof extra.manifest.w0 & { extra?: boolean }).extra = true
  expect(Either.isLeft(validateFixture(extra))).toBe(true)

  const zeroBlock = fixture()
  zeroBlock.manifest.blockId = "DNRD5-BLOCK-0000"
  expect(Either.isLeft(validateFixture(zeroBlock))).toBe(true)

  expect(
    Either.isLeft(
      validateDnrd5W0ForkManifestBytes(
        utf8(` ${new TextDecoder().decode(fixture().bytes)}`),
        fixture().content
      )
    )
  ).toBe(true)
})
