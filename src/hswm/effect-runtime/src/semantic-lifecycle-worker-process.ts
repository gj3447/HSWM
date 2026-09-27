#!/usr/bin/env node
/** One isolated lifecycle child stage; the parent owns sequencing and summary. */
import { Effect, Layer } from "effect"

import { AdaptiveHttpClient, NativeAdaptiveHttpClient } from "./adaptive-executor.js"
import { runArgvProcessMain } from "./effect-process-main.js"
import { lifecycleFailure } from "./semantic-lifecycle-domain.js"
import { runLifecycleWorker } from "./semantic-lifecycle-worker.js"

export const semanticLifecycleWorkerCli = (argv: ReadonlyArray<string>) => Effect.gen(function* () {
  const [stage, configPath, arm] = argv
  if (argv.length !== 3 || stage === undefined || configPath === undefined || arm === undefined || stage.length === 0 || configPath.length === 0 || arm.length === 0) {
    return yield* Effect.fail(lifecycleFailure("WORKER_CLI_INVALID", "Expected exactly: STAGE CONFIG_PATH ARM"))
  }
  const report = yield* runLifecycleWorker(stage, configPath, arm)
  return `${JSON.stringify({ stage: report.stage, arm: report.arm, processId: report.processId })}\n`
})

export const semanticLifecycleWorkerMain = (argv: ReadonlyArray<string>) =>
  runArgvProcessMain({
    program: (args) => semanticLifecycleWorkerCli(args).pipe(Effect.provide(Layer.succeed(AdaptiveHttpClient, NativeAdaptiveHttpClient))),
    refusalPrefix: "SEMANTIC_LIFECYCLE_WORKER_REFUSED",
    describeFailure: (error) => "code" in error && typeof error.code === "string" ? error.code : "WORKER_FAILURE",
    failureExitCode: 1
  }, argv)

if (import.meta.main) process.exitCode = await semanticLifecycleWorkerMain(process.argv.slice(2))
