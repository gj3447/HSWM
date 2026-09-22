#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runWorkspaceCli } from "./workspace-cli.js"
if (import.meta.main) process.exitCode = await runArgvProcessMain({ program: runWorkspaceCli, describeFailure: error => error.detail }, process.argv.slice(2))
