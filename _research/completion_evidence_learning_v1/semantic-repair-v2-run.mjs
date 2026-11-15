#!/usr/bin/env node
/** Versioned v2 orchestration derived from pinned v1; historical v1 bytes stay unchanged. */
import { readFile, writeFile, mkdir, readdir, realpath } from "node:fs/promises"
import { resolve, join, dirname, basename } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { io, need, json, save, boundedJson, ledger, verifyNativeStorage } from "./run.mjs"
import { pinsFor } from "./judgment-run.mjs"
import { client, auditRows } from "./quality-run.mjs"
import { runtime, seedQuality, inStore, stateHash, executeQuality } from "./quality-native.mjs"
import { loadRepairDatasetV2 as loadRepairDataset } from "./semantic-repair-v2-data.mjs"
import { repairedPrograms, repairProtocol, compareRepairRows, qualifiesRepair, seriesCost, diagnostics, previousTrial } from "./semantic-repair-v2-domain.mts"
import { sha256, canonical } from "./domain.mts"

const self=fileURLToPath(import.meta.url), here=dirname(self), arms=["baseline","candidate"]
const prepare = (root,data) => Effect.gen(function*(){
  yield* need(!!process.env.STORAGE_ARTIFACT_DIR && (yield* io(()=>realpath(dirname(root))))===(yield* io(()=>realpath(process.env.STORAGE_ARTIFACT_DIR))),"New managed artifact child required")
  const dataset=yield* io(()=>loadRepairDataset(data)), programs={baseline:dataset.baselinePrograms,candidate:repairedPrograms(dataset.baselinePrograms)}
  yield* io(()=>mkdir(root,{mode:0o700}));yield* io(()=>mkdir(join(root,"implementation"),{mode:0o700}))
  const pins=yield* io(()=>pinsFor([self,join(here,"semantic-repair-v2-domain.mts"),join(here,"semantic-repair-v2-data.mjs"),join(here,"receipts",`${previousTrial.receiptSha256}.json`),join(here,"semantic-repair-v2.md")]))
  for(const pin of pins)yield* io(async()=>{try{await writeFile(join(root,"implementation",pin.sha256),await readFile(pin.path),{flag:"wx",mode:0o600})}catch(e){if(e.code!=="EEXIST")throw e}})
  const expiresAt=new Date(Date.now()+repairProtocol.durationMs).toISOString(), children={}
  for(const arm of arms){
    const child=join(root,arm);yield* io(()=>mkdir(child,{mode:0o700}))
    for(const d of ["stores","rows","wire"])yield* io(()=>mkdir(join(child,d),{mode:0o700}))
    const p={...repairProtocol,root:child,parentRoot:root,variant:arm,cases:dataset.cases,programs:programs[arm],pins,expiresAt,
      maximumCalls:repairProtocol.maximumCalls/2,maximumTokens:repairProtocol.maximumTokens/2,
      shortEvaluator:"MIXED_SCIFACT_OR_AUTHORED_REFERENCE/v1;SEE_CASE_LABEL_SOURCE"}
    yield* save(join(child,"plan.json"),p);children[arm]={root:child,planSha256:sha256(yield* io(()=>readFile(join(child,"plan.json"))))}
  }
  yield* save(join(root,"plan.json"),{...repairProtocol,root,expiresAt,createdAt:new Date().toISOString(),children,pins,
    previousTrial:dataset.previousTrial,parentPlanSha256:dataset.parentPlanSha256,exposedGroups:dataset.exposedGroups,selection:dataset.selection,testGroups:dataset.testGroups,
    programsSha256:sha256(canonical(programs)),maximumCallsPerArm:76,maximumTokensPerArm:600000})
  yield* save(join(root,"access.json"),{revoked:false,expiresAt,planSha256:sha256(yield* io(()=>readFile(join(root,"plan.json")))),
    approvalBasis:"CURRENT_USER_REQUEST_CONTINUE_HSWM_COMPLETION_WORK",recipient:"designated gj3447 HSWM maintainer",visibility:"LOCAL_ONLY",
    purpose:"Bounded source-grounded semantic-program repair; frozen W and new local source-group evaluation",
    mappings:[{resource:"urn:hswm:semantic-repair:v2",workspace:"selected-hswm-project",representation:root,capability:"ISOLATED_NATIVE_AUDIT_AND_ARTIFACTS"},
      {resource:"urn:scifact:source-pinned-v1",workspace:"selected-public-dataset",representation:resolve(data),capability:"PINNED_READ_ONLY"},
      {resource:"urn:hswm:existing-model",workspace:"existing-loopback",representation:repairProtocol.transport,capability:"ONE_MODELS_GET_AND_152_BOUNDED_TOKENIZE_COMPLETIONS"}],
    transmitted:["complete public abstract and current claim","authored generic instructions and examples","native source/program identities"],
    excluded:["reference labels and rationales","split names","private paths","credentials"],revocation:"Set revoked:true; every model boundary rechecks. No automatic retry or renewal."})
  return {status:"PREPARED",development:20,freshTest:18,maximumCalls:152,programsSha256:sha256(canonical(programs))}
})
const scope = root => Effect.gen(function*(){
  const parent=dirname(root),p=yield* json(join(root,"plan.json")),m=yield* json(join(parent,"plan.json")),access=yield* json(join(parent,"access.json"))
  yield* need(p.root===root && p.parentRoot===parent && m.root===parent && arms.includes(basename(root)) && m.children[basename(root)].root===root &&
    m.children[basename(root)].planSha256===sha256(yield* io(()=>readFile(join(root,"plan.json")))) &&
    access.planSha256===sha256(yield* io(()=>readFile(join(parent,"plan.json")))) && access.revoked===false && access.expiresAt===p.expiresAt && Date.now()<Date.parse(p.expiresAt),"NOT_READY: changed/expired/revoked scope")
  for(const pin of p.pins)yield* need(sha256(yield* io(()=>readFile(pin.path)))===pin.sha256,`Changed implementation: ${pin.path}`)
  yield* need(p.maximumCalls===76 && p.maximumTokens===600000 && canonical(p.sampling)===canonical(repairProtocol.sampling),"Changed budget or sampling")
  return p
})
const initialize = root => Effect.gen(function*(){
  const m=yield* json(join(root,"plan.json"));yield* scope(m.children.baseline.root);yield* scope(m.children.candidate.root)
  yield* save(join(root,"initialize-started.json"),{at:new Date().toISOString()})
  const models=yield* io(async()=>{const res=await fetch(repairProtocol.transport+"/models",{signal:AbortSignal.timeout(10000)});if(!res.ok)throw new Error(`NOT_READY_MODELS_${res.status}`);return boundedJson(res)})
  yield* need(models.data?.length===1 && models.data[0].id==="qwen3-4b-real","NOT_READY: registered model changed")
  const r=yield* runtime()
  for(const arm of arms){
    const child=m.children[arm].root,p=yield* scope(child)
    yield* save(join(child,"model.json"),{id:models.data[0].id,registration:models,checkpoint:"PROVIDER_DECLARATION_NOT_WEIGHT_ATTESTATION"})
    yield* verifyNativeStorage(child,r.NodePosixFileSystem)
    const initialized=yield* inStore(r,child,rt=>Effect.gen(function*(){
      yield* seedQuality(r,rt,p.cases,p.programs,{source:"PINNED_SCIFACT_AND_AUTHORED_BOUNDARIES",parentPlanSha256:m.parentPlanSha256,programsSha256:sha256(canonical(p.programs))})
      const s=yield* rt.snapshot;yield* save(join(child,"frozen.json"),{stateSha256:stateHash(r,s),revision:s.canonical.revision})
    }))
    yield* save(join(child,"initialization-read-audit.json"),initialized.reads)
  }
  return {status:"INITIALIZED",model:models.data[0].id}
})
const rowsFor = (root,split) => Effect.gen(function*(){
  const rows=[]
  for(const name of yield* io(()=>readdir(join(root,"rows")))){const row=yield* json(join(root,"rows",name));if(split==="test"?row.split==="test":row.split!=="test")rows.push(row)}
  return rows
})
const score = (p,rows,mode) => {
  const table=compareRepairRows(rows[0],rows[1]),boundary=rows[1].filter(x=>x.split==="regression"&&x.assessment.correct).length
  const insufficient=rows.map(part=>part.filter(x=>p.cases.find(c=>c.id===x.caseId).expected.relation==="INSUFFICIENT"&&x.assessment.labelCorrect).length)
  return {status:mode==="develop"?"DEVELOPMENT_SCORED":"FRESH_TEST_SCORED",passed:qualifiesRepair(table,mode,boundary,insufficient),table,boundary,insufficient,inference:repairProtocol.inference}
}
const auditDevelopment = (roots,plans,r,rows) => Effect.gen(function*(){
  for(let i=0;i<2;i++){
    const seen=new Set(),frozen=yield* json(join(roots[i],"frozen.json")),model=(yield* json(join(roots[i],"model.json"))).id
    yield* inStore(r,roots[i],rt=>auditRows(roots[i],plans[i],r,rt,rows[i],model,frozen,seen),true)
    yield* need(rows[i].length===20,"Incomplete development cohort cannot open evaluation")
  }
})
const phase = (root,mode) => Effect.gen(function*(){
  const m=yield* json(join(root,"plan.json")),roots=arms.map(a=>m.children[a].root),plans=yield* Effect.forEach(roots,scope),r=yield* runtime()
  if(mode==="evaluate"){
    const gate=yield* json(join(root,"development.json")),rows=yield* Effect.forEach(roots,path=>rowsFor(path,"dev"))
    yield* auditDevelopment(roots,plans,r,rows)
    yield* need(canonical(score(plans[0],rows,"develop"))===canonical(gate),"Development gate differs from verified rows")
    if(!gate.passed)return {status:"DEVELOPMENT_REJECTED_TEST_NOT_OPENED",freshCalls:0}
  }
  yield* save(join(root,`${mode}-started.json`),{at:new Date().toISOString(),pid:process.pid})
  const frozen=yield* Effect.forEach(roots,path=>json(join(path,"frozen.json"))), model=(yield* json(join(roots[0],"model.json"))).id
  const session=yield* inStore(r,roots[0],a=>inStore(r,roots[1],b=>Effect.gen(function*(){
    const stores=[a,b]
    for(let i=0;i<2;i++)yield* need(stateHash(r,yield* stores[i].snapshot)===frozen[i].stateSha256,"Frozen graph drift")
    const cases=plans[0].cases.filter(c=>mode==="evaluate"?c.split==="test":c.split!=="test")
    for(const [i,c]of cases.entries())for(const k of (i%2?[1,0]:[0,1])){
      const label=`${c.id}-reasoned`,ids=[],p=plans[k]
      const result=yield* executeQuality(r,stores[k],c,"reasoned",p,model,client(roots[k],p,r,model,label,ids,scope))
      yield* need(ids.length===result.stages.length && ids.length>=1,"Missing observed stage")
      const wires=yield* Effect.forEach(ids,id=>json(join(roots[k],"wire",`${id}-response.json`)))
      yield* need(wires.every(w=>w.response.model===model),"Provider response model differs from registration")
      const tokens=wires.reduce((n,w)=>n+w.response.usage.total_tokens,0)
      yield* save(join(roots[k],"rows",`${label}.json`),{label,caseId:c.id,operator:"reasoned",split:c.split,wireIds:ids,tokens,elapsedMs:wires.reduce((n,w)=>n+w.elapsedMs,0),...result})
      process.stdout.write(JSON.stringify({variant:arms[k],caseId:c.id,split:c.split,labelCorrect:result.assessment.labelCorrect,grounded:result.assessment.correct,tokens})+"\n")
    }
    for(let i=0;i<2;i++)yield* need(stateHash(r,yield* stores[i].snapshot)===frozen[i].stateSha256,"AUDIT changed W")
  })))
  yield* save(join(root,`${mode}-read-audit.json`),{baseline:session.reads,candidate:session.result.reads})
  const rows=yield* Effect.forEach(roots,path=>rowsFor(path,mode==="evaluate"?"test":"dev"))
  if(mode==="develop")yield* auditDevelopment(roots,plans,r,rows)
  const result=score(plans[0],rows,mode)
  yield* save(join(root,mode==="develop"?"development.json":"evaluation.json"),result)
  return result
})
const check = root => Effect.gen(function*(){
  const m=yield* json(join(root,"plan.json")),dev=yield* json(join(root,"development.json")),r=yield* runtime(),stats=[],fingerprints=new Set()
  for(const arm of arms){
    const child=m.children[arm].root,p=yield* scope(child),rows=[]
    for(const name of yield* io(()=>readdir(join(child,"rows"))))rows.push(yield* json(join(child,"rows",name)))
    const expected=p.cases.filter(c=>dev.passed||c.split!=="test").map(c=>`${c.id}-reasoned`)
    yield* need(rows.length===expected.length&&new Set(rows.map(x=>x.label)).size===expected.length&&expected.every(id=>rows.some(x=>x.label===id)),"Incomplete comparison")
    const frozen=yield* json(join(child,"frozen.json")),model=(yield* json(join(child,"model.json"))).id,seen=new Set()
    const audited=yield* inStore(r,child,rt=>auditRows(child,p,r,rt,rows,model,frozen,seen),true),usage=yield* ledger(child)
    yield* need(seen.size===usage.calls && [...seen].sort((a,b)=>a-b).every((x,i)=>x===i+1) && usage.calls<=76 && usage.tokens<=600000,"Wire/cost mismatch")
    for(const id of seen){const response=(yield* json(join(child,"wire",`${id}-response.json`))).response;yield* need(response.model===model,"Reply model changed");fingerprints.add(response.system_fingerprint??"UNREPORTED")}
    stats.push({arm,...usage,rows:rows.length,nativeWireVerified:true,reads:audited.reads,diagnostics:diagnostics(rows,p.cases)})
  }
  const evaluation=dev.passed?yield* json(join(root,"evaluation.json")):null
  const summary={status:"VERIFIED_NATIVE_SEMANTIC_REPAIR",development:dev,evaluation,stats,calls:stats.reduce((n,x)=>n+x.calls,0),tokens:stats.reduce((n,x)=>n+x.tokens,0),
    nativeWireVerified:true,wMode:"FROZEN_AUDIT",freshTestOpened:dev.passed,passed:evaluation?.passed??false,providerFingerprints:[...fingerprints],inference:repairProtocol.inference}
  yield* need(summary.calls<=152&&summary.tokens<=1200000,"Parent cumulative budget exceeded")
  const complete={...summary,series:seriesCost(summary.calls,summary.tokens)}
  yield* save(join(root,"summary.json"),complete);return complete
})
if(import.meta.url===pathToFileURL(process.argv[1]??"").href){
  const [command,rootArg,data]=process.argv.slice(2)
  if(command==="--help")console.log("semantic-repair-v2-run.mjs prepare ROOT DATA | initialize ROOT | develop ROOT | evaluate ROOT | check ROOT. Managed new root; 152-call total cap, development gate before 18 new test cases; no retries and frozen W.")
  else{
    const root=resolve(rootArg??""),program=command==="prepare"?prepare(root,resolve(data??"")):command==="initialize"?initialize(root):command==="develop"?phase(root,"develop"):command==="evaluate"?phase(root,"evaluate"):command==="check"?check(root):Effect.fail(new Error("Use --help"))
    const result=await Effect.runPromise(Effect.either(program));console.log(JSON.stringify(Either.isLeft(result)?{status:"FAILED_OR_NOT_READY",error:String(result.left),detail:result.left.detail}:result.right));if(Either.isLeft(result))process.exitCode=1
  }
}
