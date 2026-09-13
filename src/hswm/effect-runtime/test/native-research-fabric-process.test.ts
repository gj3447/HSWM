import { execFileSync, spawnSync } from "node:child_process"
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { pathToFileURL } from "node:url"
import { Effect, Either, Layer } from "effect"
import { afterAll, beforeAll, expect, it } from "vitest"
import { observedVersion } from "../src/native-research-fabric.js"
import { fabricSpecs } from "../src/native-research-fabric-domain.js"
import { NodeResearchFabricRuntimeLive, ResearchFabricRuntime } from "../src/native-research-fabric-runtime.js"
import { BoundedSubprocess } from "../src/effect-bounded-subprocess.js"
const runtime = resolve(import.meta.dirname,".."), temp = mkdtempSync(join(tmpdir(),"hswm-fabric-process-")), out = join(temp,"dist")
let compiled = false
const emit = () => {
 if(compiled)return
 mkdirSync(out);symlinkSync(join(runtime,"node_modules"),join(temp,"node_modules"),"dir")
 writeFileSync(join(temp,"package.json"),'{"type":"module"}')
 writeFileSync(join(temp,"tsconfig.json"),JSON.stringify({extends:join(runtime,"tsconfig.build.json"),compilerOptions:{rootDir:join(runtime,"src"),outDir:out,declaration:false,declarationMap:false,sourceMap:false},include:[join(runtime,"src/native-research-fabric-process.ts")],exclude:[]}))
 execFileSync(join(runtime,"node_modules/.bin/tsc"),["-p",join(temp,"tsconfig.json")],{cwd:runtime});compiled=true
}
beforeAll(() => { emit() }, 30_000)
afterAll(()=>rmSync(temp,{recursive:true,force:true}))
it("exits the launcher independently of its isolated detached Node child",()=>{
 emit()
 const record=join(temp,"child.json")
 const script=`import{Effect}from'effect';import{writeFileSync}from'node:fs';import{ResearchFabricRuntime,NodeResearchFabricRuntimeLive}from ${JSON.stringify(pathToFileURL(join(out,"native-research-fabric-runtime.js")).href)};const result=await Effect.runPromise(Effect.gen(function*(){const host=yield*ResearchFabricRuntime;return yield*host.launch({name:'phoenix',executable:${JSON.stringify(process.execPath)},argv:['-e','setInterval(()=>{},1000)']},{},${JSON.stringify(join(temp,"service.log"))})}).pipe(Effect.provide(NodeResearchFabricRuntimeLive)));writeFileSync(${JSON.stringify(record)},JSON.stringify(result));`
 const parent=spawnSync(process.execPath,["--input-type=module","-e",script],{cwd:temp,encoding:"utf8",env:{PATH:""},timeout:10000})
 let pid:number|undefined
 try{const child=JSON.parse(readFileSync(record,"utf8")) as {pid:number;startTicks:number};pid=child.pid;expect(parent.status,parent.stderr).toBe(0);expect(child.startTicks).toBeGreaterThan(0);expect(()=>process.kill(child.pid,0)).not.toThrow()}
 finally{if(pid!==undefined){try{process.kill(-pid,"SIGTERM")}catch{}}}
})
it("refuses symlinked or group-readable private secrets using the opened file identity",async()=>{
 const file=join(temp,"secret.json"),link=join(temp,"secret-link.json");writeFileSync(file,'{"private":true}',{mode:0o600});symlinkSync(file,link)
 const read=(path:string)=>Effect.runPromise(Effect.gen(function*(){return yield*(yield*ResearchFabricRuntime).readPrivateText(path,4096)}).pipe(Effect.provide(NodeResearchFabricRuntimeLive),Effect.either))
 expect(Either.isRight(await read(file))).toBe(true);expect(Either.isLeft(await read(link))).toBe(true);chmodSync(file,0o640);expect(Either.isLeft(await read(file))).toBe(true)
})
it("removes service and session secrets from bounded version probes",async()=>{
 const host=Layer.succeed(BoundedSubprocess,{observe:request=>{expect(request.timeoutMs).toBe(10000);expect(request.maximumOutputBytes).toBe(32768);expect(request.environment).toEqual({PATH:"/p"});return Effect.succeed({exitCode:0,signal:null,timedOut:false,outputTruncated:false,launchError:null,stdout:Buffer.from("20.4.0\n"),stderr:Buffer.alloc(0)})}})
 expect(await Effect.runPromise(observedVersion(fabricSpecs("/state","/bin").phoenix,"/vendor/phoenix",{PATH:"/p",OPENAI_API_KEY:"test-secret",PHOENIX_SECRET:"test-secret"}).pipe(Effect.provide(host)))).toBe("20.4.0")
})
it("accepts the documented timeout and resolves relative state roots from a foreign working directory",()=>{
 emit();const result=spawnSync(process.execPath,[join(out,"native-research-fabric-process.js"),"status","--service","temporal","--state-dir","absent-state","--timeout","120"],{cwd:temp,encoding:"utf8",env:{PATH:""},timeout:15000})
 expect([0,1]).toContain(result.status);const body=JSON.parse(result.stdout) as {state_root:string;services:readonly unknown[]};expect(body.state_root).toBe(join(temp,"absent-state"));expect(body.services.length).toBe(1)
})
