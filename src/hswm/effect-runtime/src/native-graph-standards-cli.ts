import { resolve } from "node:path"
import { parseArgs } from "node:util"
import { Data, Effect } from "effect"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import type { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "./native-task-json-domain.js"
import { fetchNativeGraphStandardSource, qualifyNativeGraphStandardsProfile, verifyNativeGraphStandardsCheckout } from "./native-graph-standards-runtime.js"
import { Either } from "effect"
export class NativeGraphStandardsCliError extends Data.TaggedError("NativeGraphStandardsCliError")<{readonly detail:string}>{}
const usage="usage: hswm-graph-standards [--repository-root ROOT] [--manifest PATH] verify | fetch --source-id ID --destination PATH | qualify --profile ID --source-root PATH [--output PATH]"
const defaultRoot=resolve(import.meta.dirname,"..","..","..","..")
export const runNativeGraphStandardsCli=(argv:readonly string[]):Effect.Effect<string,NativeGraphStandardsCliError,PosixFileSystem|BoundedSubprocess>=>Effect.gen(function*(){
 const parsed=yield* Effect.try({try:()=>parseArgs({args:[...argv],allowPositionals:true,strict:true,options:{"repository-root":{type:"string"},manifest:{type:"string"},"source-id":{type:"string"},destination:{type:"string"},profile:{type:"string"},"source-root":{type:"string"},output:{type:"string"}}}),catch:()=>new NativeGraphStandardsCliError({detail:usage})})
 const command=parsed.positionals[0],root=resolve(parsed.values["repository-root"]??defaultRoot),manifest=resolve(parsed.values.manifest??resolve(root,"_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json"))
 if((command!=="verify"&&command!=="fetch"&&command!=="qualify")||parsed.positionals.length!==1)return yield* Effect.fail(new NativeGraphStandardsCliError({detail:usage}))
 if(command==="verify"){const result=yield* verifyNativeGraphStandardsCheckout(root,manifest).pipe(Effect.mapError(e=>new NativeGraphStandardsCliError({detail:e.detail})));return `${renderNativeTaskJson(result,"pretty")}\n`}
 const fs=yield* PosixFileSystem
 const lockBytes=yield* fs.readRegularBounded(manifest,{maximumBytes:64*1024*1024,minimumBytes:1,operation:"graph standards lock"}).pipe(Effect.map(x=>x.bytes),Effect.mapError(e=>new NativeGraphStandardsCliError({detail:`cannot read graph standards lock: ${e.detail}`})))
 const lock=decodeNativeTaskJson(lockBytes);if(Either.isLeft(lock))return yield* Effect.fail(new NativeGraphStandardsCliError({detail:"cannot read graph standards lock"}))
 if(command==="fetch"){const check=yield* verifyNativeGraphStandardsCheckout(root,manifest).pipe(Effect.mapError(e=>new NativeGraphStandardsCliError({detail:e.detail})));void check;const sourceId=parsed.values["source-id"],destination=parsed.values.destination;if(sourceId===undefined||destination===undefined)return yield* Effect.fail(new NativeGraphStandardsCliError({detail:usage}));const rootLock=taskJsonRecord(lock.right)?lock.right:undefined;const sources=rootLock?.["suite_sources"];if(!Array.isArray(sources))return yield* Effect.fail(new NativeGraphStandardsCliError({detail:"suite_sources must be an array"}));const source=sources.find(x=>taskJsonRecord(x)&&x["id"]===sourceId);if(source===undefined)return yield* Effect.fail(new NativeGraphStandardsCliError({detail:`unknown suite source: ${sourceId}`}));const result=yield* fetchNativeGraphStandardSource(source,resolve(destination),root).pipe(Effect.mapError(e=>new NativeGraphStandardsCliError({detail:e.detail})));const response:TaskJson=taskJsonRecord(result)?{...result,source_id:sourceId}:result;return `${renderNativeTaskJson(response,"pretty")}\n`}
 const profile=parsed.values.profile,sourceRoot=parsed.values["source-root"];if(profile===undefined||sourceRoot===undefined)return yield* Effect.fail(new NativeGraphStandardsCliError({detail:usage}));const result=yield* qualifyNativeGraphStandardsProfile(lock.right,profile,resolve(sourceRoot),root,parsed.values.output===undefined?undefined:resolve(parsed.values.output)).pipe(Effect.mapError(e=>new NativeGraphStandardsCliError({detail:e.detail})))
 return `${renderNativeTaskJson(result,"pretty")}\n`
})
