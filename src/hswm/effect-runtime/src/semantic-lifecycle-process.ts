#!/usr/bin/env node
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Effect, Layer } from "effect"
import { runArgvProcessMain } from "./effect-process-main.js"
import { parseLifecycleArgs } from "./semantic-lifecycle-domain.js"
import { LifecycleHost, runLifecycle } from "./semantic-lifecycle-runner.js"

export const lifecycleUsage = `Usage: node src/hswm/effect-runtime/dist/semantic-lifecycle-process.js --output NEW_PRIVATE_DIRECTORY --transport scripted|http [--cell CELL_JSON]
Build src/hswm/effect-runtime first. Scripted mode performs no network/model calls.
HTTP mode requires an explicit cell {base_url, model, max_tokens, api_key_env?}.
On maintainer DGX, use the documented hswm-run preflight and execution wrapper.
All outputs are a finite authored diagnostic, not HSWM efficacy evidence.\n`

export const lifecycleCli = (argv: ReadonlyArray<string>, cwd: string) => Effect.gen(function* () {
  const options = yield* parseLifecycleArgs(argv, cwd)
  if (options === null) return lifecycleUsage
  const { report, heldout } = yield* runLifecycle(options)
  return `${JSON.stringify({ output: options.output, status: report.status, claimCeiling: report.claimCeiling,
    reopened: report.reopened, sharedEvidence: report.sharedEvidence, httpModelRequests: report.httpModelRequests, heldout })}\n`
})

/** The sole parent-process composition root; imports do not execute the program. */
export const semanticLifecycleMain = (argv: ReadonlyArray<string>) => {
  const environment = Object.fromEntries(Object.entries(process.env).flatMap(([key, value]) => value === undefined ? [] : [[key, value]]))
  const host = Layer.succeed(LifecycleHost, { repository: resolve(dirname(fileURLToPath(import.meta.url)), "../../../.."),
    nodeExecutable: process.execPath, nodeVersion: process.version, environment })
  return runArgvProcessMain({ program: args => lifecycleCli(args, process.cwd()).pipe(Effect.provide(host)),
    refusalPrefix: "SEMANTIC_LIFECYCLE_REFUSED", describeFailure: error => error.code, failureExitCode: 1 }, argv)
}
if (import.meta.main) process.exitCode = await semanticLifecycleMain(process.argv.slice(2))
