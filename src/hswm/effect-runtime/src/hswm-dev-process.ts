#!/usr/bin/env node
import { runAdaptiveCli, describeAdaptiveCliError } from "./adaptive-cli.js"
import { runArgvProcessMain } from "./effect-process-main.js"

if (import.meta.main) {
  process.exitCode = await runArgvProcessMain({
    program: (argv) => runAdaptiveCli("development", argv), describeFailure: describeAdaptiveCliError
  }, process.argv.slice(2))
}
