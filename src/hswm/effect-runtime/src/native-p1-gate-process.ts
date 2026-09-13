#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runNativeP1GateCli } from "./native-p1-gate-cli.js"

if (import.meta.main) process.exitCode = await runArgvProcessMain({
  program: runNativeP1GateCli,
  describeFailure: error => error.detail,
}, process.argv.slice(2))
