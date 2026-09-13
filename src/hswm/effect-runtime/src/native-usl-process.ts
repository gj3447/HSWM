#!/usr/bin/env node
import { pathToFileURL } from "node:url"
import { runArgvProcessMain } from "./effect-process-main.js"
import { describeNativeUslCliError, runNativeUslCli } from "./native-usl-cli.js"

export const runNativeUslProcess = (argv: ReadonlyArray<string>) => runArgvProcessMain({ program: runNativeUslCli, describeFailure: describeNativeUslCliError }, argv)
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) process.exitCode = await runNativeUslProcess(process.argv.slice(2))
