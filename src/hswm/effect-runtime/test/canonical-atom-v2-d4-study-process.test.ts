import { expect, it } from "@effect/vitest"
import { Effect } from "effect"

import { executeD4StudyProcess } from "../src/canonical-atom-v2-d4-study-process.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-services.js"

it.effect("refuses an underspecified or non-ACTIVE D4 write before any journal operation", () => Effect.gen(function* () {
  const missingInstance = {
    contractVersion: "hswm-d4-study-process/v1",
    operation: "commit",
    rootPath: "/tmp/d4-test-root",
    trustSnapshotPath: "/tmp/d4-test-root/trust-snapshot.json",
    leanExecutable: "/tmp/d4-test-lean",
    occurrenceUid: "occurrence:d4-test",
    lifetimeMs: 60_000,
    mode: "ACTIVE",
    payloads: { task: {}, trajectory: {}, outcome: {}, credit: {}, disposition: {} }
  }
  const controlMode = { ...missingInstance, mode: "SHAM" }
  const first = yield* executeD4StudyProcess(missingInstance as never).pipe(Effect.flip, Effect.provide(NodePosixFileSystemLive))
  const second = yield* executeD4StudyProcess(controlMode as never).pipe(Effect.flip, Effect.provide(NodePosixFileSystemLive))
  expect(first._tag).toBe("ProcessRefusal")
  expect(second._tag).toBe("ProcessRefusal")
}))
