#!/usr/bin/env node
import { Effect } from "effect"
import { runArgvProcessMain, refuse } from "./effect-process-main.js"
import { qualifyNativeShaclCore } from "./native-kg-qualification.js"
export const runNativeKgQualification = (argv: readonly string[]) => Effect.gen(function* () {
  if (argv.length !== 1 || argv[0] === undefined) return yield* Effect.fail(refuse("usage: native-kg-qualification SHACL_CHECKOUT"))
  const result = yield* qualifyNativeShaclCore(argv[0])
  return { stdout: `${JSON.stringify(result, null, 2)}\n`, exitCode: result.failed === 0 ? 0 : 1 }
}).pipe(Effect.mapError(e => refuse(e.detail)))
if (import.meta.main) process.exitCode = await runArgvProcessMain({ program: runNativeKgQualification, describeFailure: e => e.detail }, process.argv.slice(2))
