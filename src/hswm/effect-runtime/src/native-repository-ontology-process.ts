#!/usr/bin/env node
import { parseArgs } from "node:util"
import { fileURLToPath } from "node:url"
import { resolve } from "node:path"
import { Effect } from "effect"
import { runArgvProcessMain, refuse } from "./effect-process-main.js"
import { verifyNativeRepositoryOntology } from "./native-repository-ontology-runtime.js"

export const runNativeRepositoryOntologyCli = (argv: readonly string[]) => Effect.gen(function* () {
  const parsed = yield* Effect.try({ try: () => parseArgs({ args: [...argv], options: { "repo-root": { type: "string" }, help: { type: "boolean" } }, strict: true, allowPositionals: false }), catch: () => refuse("usage: hswm-repository-ontology [--repo-root ROOT]") })
  if (parsed.values.help) return { stdout: "hswm-repository-ontology [--repo-root ROOT]\nRead-only native repository layout verification.\n", exitCode: 0 }
  const result = yield* verifyNativeRepositoryOntology(parsed.values["repo-root"] ?? resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../.."))
  const sorted = Object.entries(result).sort(([left], [right]) => left.localeCompare(right))
  return { stdout: `{${sorted.map(([key, value]) => `${JSON.stringify(key)}: ${JSON.stringify(value)}`).join(", ")}}\n`, exitCode: 0 }
}).pipe(Effect.mapError(error => refuse(error.detail)))
if (import.meta.main) process.exitCode = await runArgvProcessMain({ program: runNativeRepositoryOntologyCli, describeFailure: error => error.detail }, process.argv.slice(2))
