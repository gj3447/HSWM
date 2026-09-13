#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runKnowledgeCatalogCli } from "./knowledge-catalog-cli.js"
if (import.meta.main) process.exitCode = await runArgvProcessMain({ program: runKnowledgeCatalogCli, describeFailure: (error) => error.detail }, process.argv.slice(2))
