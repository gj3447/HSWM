#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js";
import { runNativeS2SModelCli } from "./native-s2s-model-cli.js";
if (import.meta.main)
    process.exitCode = await runArgvProcessMain({ program: runNativeS2SModelCli, describeFailure: error => error.detail }, process.argv.slice(2));
