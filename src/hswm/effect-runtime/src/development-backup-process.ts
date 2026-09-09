#!/usr/bin/env node
import { runDevelopmentBackupCli } from "./development-backup.js"
import { runArgvProcessMain } from "./effect-process-main.js"

if (import.meta.main) {
  process.exitCode = await runArgvProcessMain({ program: runDevelopmentBackupCli, describeFailure: (error) => error.detail }, process.argv.slice(2))
}
