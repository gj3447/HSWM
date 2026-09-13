#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runNativeKgCli } from "./native-kg-cli.js"
if (import.meta.main) process.exitCode = await runArgvProcessMain({ program: runNativeKgCli, describeFailure: error => error.detail }, process.argv.slice(2))
