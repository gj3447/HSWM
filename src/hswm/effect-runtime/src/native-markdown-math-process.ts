#!/usr/bin/env node
import { runArgvProcessMain } from "./effect-process-main.js"
import { runNativeMarkdownMathCli } from "./native-markdown-math-cli.js"
if(import.meta.main)process.exitCode=await runArgvProcessMain({program:runNativeMarkdownMathCli,describeFailure:e=>e.detail},process.argv.slice(2))
