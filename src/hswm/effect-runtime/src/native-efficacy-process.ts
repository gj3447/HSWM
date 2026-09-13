#!/usr/bin/env node
import { resolve } from "node:path"
import { parseArgs } from "node:util"
import { Data, Effect } from "effect"
import { runArgvProcessMain, type ProcessReply } from "./effect-process-main.js"
import { renderNativeTaskJson } from "./native-task-json-domain.js"
import { verifyNativeEfficacyCheckout } from "./native-efficacy-runtime.js"
export class NativeEfficacyCliError extends Data.TaggedError("NativeEfficacyCliError")<{readonly detail:string}>{}
const usage="usage: hswm-verify-efficacy [--root HSWM_SOURCE_CHECKOUT] [--pretty]"
const defaultRoot=resolve(import.meta.dirname,"..","..","..","..")
export const runNativeEfficacyCli=(argv:readonly string[]):Effect.Effect<ProcessReply,NativeEfficacyCliError,import("./effect-posix-filesystem.js").PosixFileSystem>=>Effect.gen(function*(){const parsed=yield* Effect.try({try:()=>parseArgs({args:[...argv],allowPositionals:false,strict:true,options:{root:{type:"string"},pretty:{type:"boolean"},help:{type:"boolean"}}}),catch:()=>new NativeEfficacyCliError({detail:usage})});if(parsed.values.help)return{stdout:`${usage}\n`,exitCode:0};const snapshot=yield* verifyNativeEfficacyCheckout(resolve(parsed.values.root??defaultRoot)).pipe(Effect.mapError(e=>new NativeEfficacyCliError({detail:e.detail})));return{stdout:`${renderNativeTaskJson(snapshot,parsed.values.pretty?"pretty":"canonical")}\n`,exitCode:0}})
if(import.meta.main)process.exitCode=await runArgvProcessMain({program:runNativeEfficacyCli,describeFailure:e=>e.detail},process.argv.slice(2))
