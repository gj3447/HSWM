#!/usr/bin/env node
import { pathToFileURL } from "node:url"
import { runArgvProcessMain } from "./effect-process-main.js"
import { describeNativeLegacyReplayError, runNativeLegacyReplayCli } from "./native-legacy-replay-cli.js"
export const runNativeLegacyReplayProcess=(argv:ReadonlyArray<string>)=>runArgvProcessMain({program:runNativeLegacyReplayCli,describeFailure:describeNativeLegacyReplayError},argv)
if(import.meta.url===pathToFileURL(process.argv[1]??"").href)process.exitCode=await runNativeLegacyReplayProcess(process.argv.slice(2))
