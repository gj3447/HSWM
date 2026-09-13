#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runNativeDevelopmentProjectionCli } from "./native-development-projection-cli.js"
if (import.meta.main) process.exitCode = await runArgvProcessMain({ program: argv => runNativeDevelopmentProjectionCli(argv), describeFailure: error => error.detail }, process.argv.slice(2))
