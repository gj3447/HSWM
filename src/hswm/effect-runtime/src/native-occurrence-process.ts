#!/usr/bin/env node
import { pathToFileURL } from "node:url"
import { Effect } from "effect"
import { runArgvProcessMain } from "./effect-process-main.js"
import { NodeOccurrencePreflightLive } from "./native-occurrence-preflight-runtime.js"
import { runNativeOccurrenceCli } from "./native-occurrence-cli.js"
import type { NativeOccurrenceCliError } from "./native-occurrence-cli-domain.js"
export const describeNativeOccurrenceCliError=(e:NativeOccurrenceCliError):string=>`hswm-g0-occurrence: error: ${e.detail}`
export const runNativeOccurrenceProcess=(argv:ReadonlyArray<string>)=>runArgvProcessMain({program:args=>runNativeOccurrenceCli(args).pipe(Effect.provide(NodeOccurrencePreflightLive)),describeFailure:describeNativeOccurrenceCliError},argv)
if(import.meta.url===pathToFileURL(process.argv[1]??"").href)process.exitCode=await runNativeOccurrenceProcess(process.argv.slice(2))
