import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Layer } from "effect"
import { expect, it } from "@effect/vitest"
import { BoundedSubprocess } from "../src/effect-bounded-subprocess.js"
import { REQUIRED_BINDINGS, ROLE_BINDINGS, classifyOccurrencePreflight } from "../src/native-occurrence-preflight-domain.js"
import { ExecutableLocator, OccurrenceEnvironmentService, observeOccurrencePreflight } from "../src/native-occurrence-preflight-runtime.js"

const complete=Object.freeze({...Object.fromEntries(REQUIRED_BINDINGS.map((name,index)=>[name,`binding-${index}`])),...Object.fromEntries(ROLE_BINDINGS.map(([role,name],index)=>[name,`${role}-${index}`]))})
it("matches complete source-bound historical Python preflight reports", () => {
  const cases = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/native_migration/occurrence_preflight_v1/reports.json"), "utf8")) as readonly {name: string; input: Parameters<typeof classifyOccurrencePreflight>[0]; expected: unknown}[];
  for (const row of cases) expect(classifyOccurrencePreflight(row.input), row.name).toEqual(row.expected);
});
it("fails closed when a runtime adapter omits, duplicates, or adds a fixed tool observation",()=>{
 const binaries=[{name:"cosign",candidateVersion:"3.1.3",present:true,versionOutput:"3.1.3"},{name:"temporal",candidateVersion:"1.8.3",present:true,versionOutput:"1.8.3"},{name:"aws",candidateVersion:"2.36.36",present:true,versionOutput:"2.36.36"},{name:"openssl",candidateVersion:"3.5.6",present:true,versionOutput:"3.5.6"}] as const
 for(const observed of [[],binaries.slice(1),[...binaries,binaries[0]!],[...binaries,{name:"unexpected",candidateVersion:"1",present:true,versionOutput:"1"}]]){
  const report=classifyOccurrencePreflight({environment:complete,binaries:observed});expect(report).toMatchObject({status:"BLOCKED_LOCAL_ENGINEERING",local_engineering_ready:false})
 }
});
it("runtime test doubles preserve executable presence but fail timeout and truncation qualification",async()=>{
 const environment=Layer.succeed(OccurrenceEnvironmentService,{snapshot:Effect.succeed({values:complete,path:"/tools",cwd:"/tmp"})}),locator=Layer.succeed(ExecutableLocator,{locate:name=>Effect.succeed(`/tools/${name}`)})
 const run=async(timedOut:boolean,outputTruncated:boolean,exitCode:number)=>Effect.runPromise(observeOccurrencePreflight().pipe(Effect.provide(Layer.mergeAll(environment,locator,Layer.succeed(BoundedSubprocess,{observe:()=>Effect.succeed({exitCode,signal:null,timedOut,outputTruncated,launchError:null,stdout:new TextEncoder().encode("3.1.3 1.8.3 2.36.36 3.5.6"),stderr:new Uint8Array()})})))) )
 const failed=await run(false,false,1),timeout=await run(true,false,0),truncated=await run(false,true,0);for(const report of [failed,timeout,truncated]){expect(report).toMatchObject({status:"BLOCKED_LOCAL_ENGINEERING",local_engineering_ready:false});expect((report["binaries"] as Array<Record<string,unknown>>).every(binary=>binary["present"]===true&&binary["candidate_version_observed"]===false)).toBe(true)}
})
