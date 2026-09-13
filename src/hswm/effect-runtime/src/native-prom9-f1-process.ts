#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js";
import { runNativeProm9F1Cli } from "./native-prom9-f1-cli.js";
if (import.meta.main)
    process.exitCode = await runArgvProcessMain({ program: runNativeProm9F1Cli, describeFailure: error => error.detail }, process.argv.slice(2));
