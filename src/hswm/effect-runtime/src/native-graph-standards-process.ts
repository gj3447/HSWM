#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runNativeGraphStandardsCli } from "./native-graph-standards-cli.js"
if(import.meta.main)process.exitCode=await runArgvProcessMain({refusalPrefix:"REFUSED",program:runNativeGraphStandardsCli,describeFailure:e=>e.detail},process.argv.slice(2))
