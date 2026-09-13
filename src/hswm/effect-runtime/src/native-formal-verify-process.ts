#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runNativeFormalVerifyCli } from "./native-formal-verify-cli.js"
if(import.meta.main)process.exitCode=await runArgvProcessMain({program:runNativeFormalVerifyCli,describeFailure:error=>error.detail},process.argv.slice(2))
