/** Bounded private JSON operations through the existing POSIX Effect service. */
import { Effect, Schema } from "effect"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { LifecycleConfigSchema, decodeLifecycleCell, lifecycleFailure } from "./semantic-lifecycle-domain.js"

export const readLifecycleJson = (path: string) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const raw = yield* fs.readRegularBounded(path, { maximumBytes: 16_777_216, operation: "semantic-lifecycle-json-read" })
  return yield* Effect.try({ try: (): unknown => JSON.parse(new TextDecoder().decode(raw.bytes)), catch: () => lifecycleFailure("JSON_INVALID", "Invalid lifecycle JSON") })
})
export const writeLifecycleJson = (path: string, value: unknown) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const encoded = yield* Effect.try({ try: () => JSON.stringify(value, null, 2), catch: () => lifecycleFailure("JSON_INVALID", "Lifecycle output is not JSON serializable") })
  if (encoded === undefined) return yield* Effect.fail(lifecycleFailure("JSON_INVALID", "Lifecycle output has no JSON root"))
  yield* fs.writeExclusive(path, new TextEncoder().encode(`${encoded}\n`), { mode: 0o600, sync: true, operation: "semantic-lifecycle-json-write" })
})
export const readLifecycleConfig = (path: string) => Effect.gen(function* () {
  const raw = yield* readLifecycleJson(path)
  const config = yield* Schema.decodeUnknown(LifecycleConfigSchema)(raw, { onExcessProperty: "error" }).pipe(
    Effect.mapError(() => lifecycleFailure("CONFIG_INVALID", "Invalid lifecycle configuration")))
  yield* decodeLifecycleCell(config.cell)
  return config
})
