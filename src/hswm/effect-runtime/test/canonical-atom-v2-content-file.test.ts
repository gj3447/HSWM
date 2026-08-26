import {
  chmodSync,
  mkdtempSync,
  mkdirSync,
  rmSync,
  symlinkSync,
  unlinkSync,
  writeFileSync
} from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import { CanonicalAtomV2ContentStore } from "../src/canonical-atom-v2-content.js"
import { makeCanonicalAtomV2ContentFileStoreLayer } from "../src/canonical-atom-v2-content-file.js"

const bytes = (text: string): Uint8Array => new TextEncoder().encode(text)

const withStore = <A, E>(
  root: string,
  program: Effect.Effect<A, E, CanonicalAtomV2ContentStore>
) =>
  program.pipe(Effect.provide(makeCanonicalAtomV2ContentFileStoreLayer(root)))

const cleanup = (root: string) =>
  Effect.sync(() => rmSync(root, { force: true, recursive: true }))

it.effect("persists content and schema binding through a fresh Layer", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-content-"))
  const program = Effect.gen(function* () {
    const descriptor = yield* withStore(root, Effect.gen(function* () {
      const store = yield* CanonicalAtomV2ContentStore
      const content = yield* store.put("application/json", bytes("{}"))
      yield* store.bindSchema({ schemaVersion: "hswm:test:file:v2", content })
      return content
    }))
    const restored = yield* withStore(root, Effect.gen(function* () {
      const store = yield* CanonicalAtomV2ContentStore
      const bound = yield* store.resolveSchema("hswm:test:file:v2")
      const raw = yield* store.get(bound)
      return { bound, raw }
    }))
    expect(restored.bound).toEqual(descriptor)
    expect(new TextDecoder().decode(restored.raw)).toBe("{}")
  })
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("is idempotent, copies caller bytes at invocation, and refuses a schema conflict", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-idempotent-"))
  const raw = bytes("first")
  const program = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    const pending = store.put("text/plain", raw)
    raw.fill(0)
    const first = yield* pending
    const duplicate = yield* store.put("text/plain", bytes("first"))
    expect(duplicate).toEqual(first)
    yield* store.bindSchema({ schemaVersion: "hswm:test:conflict:v2", content: first })
    const other = yield* store.put("text/plain", bytes("second"))
    const conflict = yield* store.bindSchema({ schemaVersion: "hswm:test:conflict:v2", content: other }).pipe(Effect.either)
    expect(Either.isLeft(conflict)).toBe(true)
    if (Either.isLeft(conflict)) expect(conflict.left.reason).toBe("SCHEMA_BINDING_CONFLICT")
  }).pipe(Effect.provide(makeCanonicalAtomV2ContentFileStoreLayer(root)))
  return program.pipe(Effect.ensuring(cleanup(root)))
})

it.effect("rejects relative roots, symlink objects, and corrupted content", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-canonical-v2-unsafe-"))
  const symlinkRoot = `${root}-link`
  symlinkSync(root, symlinkRoot)
  const relative = Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    return yield* store.resolveSchema("hswm:test:missing:v2")
  }).pipe(
    Effect.provide(makeCanonicalAtomV2ContentFileStoreLayer("relative-content-root")),
    Effect.either
  )
  const program = Effect.gen(function* () {
    const relativeResult = yield* relative
    expect(Either.isLeft(relativeResult)).toBe(true)

    const symlinkRootResult = yield* Effect.gen(function* () {
      yield* CanonicalAtomV2ContentStore
    }).pipe(
      Effect.provide(makeCanonicalAtomV2ContentFileStoreLayer(symlinkRoot)),
      Effect.either
    )
    expect(Either.isLeft(symlinkRootResult)).toBe(true)

    const descriptor = yield* withStore(root, Effect.gen(function* () {
      const store = yield* CanonicalAtomV2ContentStore
      return yield* store.put("text/plain", bytes("safe"))
    }))
    const objectPath = join(root, "objects", descriptor.sha256)
    chmodSync(objectPath, 0o600)
    writeFileSync(objectPath, "bad", { mode: 0o400 })
    const corrupt = yield* withStore(root, Effect.gen(function* () {
      const store = yield* CanonicalAtomV2ContentStore
      return yield* store.get(descriptor).pipe(Effect.either)
    }))
    expect(Either.isLeft(corrupt)).toBe(true)

    const linkRoot = join(root, "linked")
    mkdirSync(linkRoot, { mode: 0o700 })
    symlinkSync(join(root, "objects"), join(linkRoot, "objects"))
    const linked = yield* Effect.gen(function* () {
      const store = yield* CanonicalAtomV2ContentStore
      return yield* store.resolveSchema("hswm:test:missing:v2")
    }).pipe(Effect.provide(makeCanonicalAtomV2ContentFileStoreLayer(linkRoot)), Effect.either)
    expect(Either.isLeft(linked)).toBe(true)
  })
  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => {
        unlinkSync(symlinkRoot)
        rmSync(root, { force: true, recursive: true })
      })
    )
  )
})
