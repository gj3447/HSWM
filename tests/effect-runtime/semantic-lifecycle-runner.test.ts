import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

import { Effect, Layer } from "effect"
import { expect, it } from "vitest"

import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { NodePosixFileSystemLive } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"
import { LifecycleHost, runLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runner.js"
import { AdaptiveHttpClient } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"

it("records a timed-out first child as a typed failed diagnostic without retrying", async () => {
  const parent = mkdtempSync(join(tmpdir(), "hswm-semantic-lifecycle-runner-"))
  const output = join(parent, "attempt")
  let observations = 0
  const repository = resolve(fileURLToPath(new URL("../..", import.meta.url)))
  const host = Layer.succeed(LifecycleHost, {
    repository,
    nodeExecutable: process.execPath,
    nodeVersion: process.version,
    environment: {}
  })
  const subprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({
    observe: () => {
      observations += 1
      return Effect.succeed({
        exitCode: null, signal: "SIGTERM", timedOut: true, outputTruncated: false,
        launchError: null, stdout: new Uint8Array(), stderr: new Uint8Array()
      })
    }
  }))
  try {
    const result = await Effect.runPromise(runLifecycle({ output, transport: "scripted", cellPath: null }).pipe(
      Effect.either,
      Effect.provideService(AdaptiveHttpClient, { postJson: () => Effect.die("No transport should run after child timeout") }),
      Effect.provide(Layer.mergeAll(NodePosixFileSystemLive, host, subprocess))
    ))
    expect(result._tag).toBe("Left")
    if (result._tag === "Left") expect(result.left).toMatchObject({ code: "PROCESS_FAILED" })
    expect(observations).toBe(1)
    expect(existsSync(join(output, "config.json"))).toBe(true)
    expect(existsSync(join(output, "source-pins.json"))).toBe(true)
    expect(existsSync(join(output, "summary.json"))).toBe(false)
    const failure = JSON.parse(readFileSync(join(output, "failure.json"), "utf8"))
    expect(failure).toMatchObject({ status: "FAILED_DIAGNOSTIC", launches: [], plannedHeldoutCasesPerArm: 4, errorCode: "PROCESS_FAILED" })
  } finally {
    rmSync(parent, { recursive: true, force: true })
  }
})
