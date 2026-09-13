#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js";
import { runNativeInfrastructureSmokeCli } from "./native-infrastructure-smoke-cli.js";
if (import.meta.main)
    process.exitCode = await runArgvProcessMain({ program: runNativeInfrastructureSmokeCli, describeFailure: error => error.detail }, process.argv.slice(2));
