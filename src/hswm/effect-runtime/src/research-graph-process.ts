#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runResearchGraphCli } from "./research-graph-cli.js"

if (import.meta.main) {
  process.exitCode = await runArgvProcessMain({ program: runResearchGraphCli, describeFailure: (error) => error.detail }, process.argv.slice(2))
}
