#!/usr/bin/env node
/** Explicit process entrypoint for the TypeScript G0 Temporal worker. */
import { fileURLToPath } from "node:url"

import { Effect, Either } from "effect"

import { runG0TemporalLocalRehearsalWorker } from "./g0-occurrence-temporal-runtime.js"
import { decodeG0OccurrenceTemporalWorkerConfigurationWire } from "./g0-occurrence-temporal-wire.js"

const configurationFromEnvironment = (): Readonly<Record<string, unknown>> => ({
  address: process.env["HSWM_G0_TEMPORAL_ADDRESS"] ?? "",
  namespace: process.env["HSWM_G0_TEMPORAL_NAMESPACE"] ?? "",
  task_queue: process.env["HSWM_G0_TEMPORAL_TASK_QUEUE"] ?? "",
  signal_authorization_binding_sha256:
    process.env["HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING"] ?? ""
})

export const main = async (argv: ReadonlyArray<string> = process.argv.slice(2)): Promise<number> => {
  if (argv.length === 1 && argv[0] === "--serve") {
    process.stderr.write("refused: live external admission is blocked; only --serve-rehearsal is available\n")
    return 2
  }
  if (argv.length !== 1 || (argv[0] !== "--serve-rehearsal" && argv[0] !== "--preflight")) {
    process.stderr.write("refused: pass exactly --serve-rehearsal or --preflight\n")
    return 2
  }
  const configuration = configurationFromEnvironment()
  const validated = decodeG0OccurrenceTemporalWorkerConfigurationWire(configuration)
  if (Either.isLeft(validated)) {
    process.stderr.write("refused: incomplete or invalid non-secret Temporal worker configuration\n")
    return 2
  }
  if (argv.length === 1 && argv[0] === "--preflight") {
    process.stdout.write(`${JSON.stringify({
      schema_version: "hswm-g0-temporal-typescript-worker-preflight/v1",
      status: "CONFIGURED_NOT_CONNECTED_NOT_EXECUTED_NOT_G0",
      address_configured: true,
      namespace_configured: true,
      task_queue_configured: true,
      signal_authorization_binding_configured: true,
      credentials_accepted: false,
      live_external_admission: false
    })}\n`)
    return 0
  }
  const workflowsPath = fileURLToPath(new URL("./g0-occurrence-temporal-workflow.js", import.meta.url))
  const exit = await Effect.runPromiseExit(runG0TemporalLocalRehearsalWorker(configuration, workflowsPath))
  return exit._tag === "Success" ? 0 : 2
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().then(
    (code) => {
      process.exitCode = code
    },
    () => {
      process.stderr.write("refused: unexpected worker process failure\n")
      process.exitCode = 2
    }
  )
}
