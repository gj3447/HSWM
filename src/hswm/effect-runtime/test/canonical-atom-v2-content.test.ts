import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  CanonicalAtomV2ContentStore,
  makeCanonicalAtomV2ContentDescriptor,
  makeCanonicalAtomV2ContentStoreMemoryLayer,
  type CanonicalAtomV2ContentDescriptor
} from "../src/canonical-atom-v2-content.js"

const bytes = (text: string): Uint8Array => new TextEncoder().encode(text)

it("derives an exact raw-byte descriptor", () => {
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    "text/plain",
    bytes("hello")
  )
  expect(Either.isRight(descriptor)).toBe(true)
  if (Either.isRight(descriptor)) {
    expect(descriptor.right.byteLength).toBe(5)
    expect(descriptor.right.sha256).toBe(
      "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
  }
})

it.effect("copies caller bytes at put invocation and returns defensive copies", () => {
  const input = bytes("hello")
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    const pending = store.put("text/plain", input)
    input.fill(0)
    const descriptor = yield* pending
    const first = yield* store.get(descriptor)
    first.fill(0)
    const second = yield* store.get(descriptor)
    expect(new TextDecoder().decode(second)).toBe("hello")
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2ContentStoreMemoryLayer()))
})

it.effect("binds a schema immutably and rejects a different descriptor", () => {
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    const first = yield* store.put("application/json", bytes("{}"))
    const second = yield* store.put("application/json", bytes("[]"))
    yield* store.bindSchema({ schemaVersion: "hswm:test:schema:v2", content: first })
    yield* store.bindSchema({ schemaVersion: "hswm:test:schema:v2", content: first })
    const conflict = yield* store.bindSchema({ schemaVersion: "hswm:test:schema:v2", content: second }).pipe(Effect.either)
    expect(Either.isLeft(conflict)).toBe(true)
    if (Either.isLeft(conflict)) expect(conflict.left.reason).toBe("SCHEMA_BINDING_CONFLICT")
    expect(yield* store.resolveSchema("hswm:test:schema:v2")).toEqual(first)
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2ContentStoreMemoryLayer()))
})

it.effect("fails closed for missing or corrupt descriptors", () => {
  const absent: CanonicalAtomV2ContentDescriptor = {
    mediaType: "application/octet-stream",
    byteLength: 1,
    sha256: "a".repeat(64)
  }
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    const outcome = yield* store.get(absent).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) expect(outcome.left.reason).toBe("CONTENT_NOT_FOUND")
  })
  return program.pipe(Effect.provide(makeCanonicalAtomV2ContentStoreMemoryLayer()))
})
