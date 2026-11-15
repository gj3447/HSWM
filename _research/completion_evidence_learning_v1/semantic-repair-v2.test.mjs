import { test } from "node:test"
import assert from "node:assert/strict"
import { readFile, mkdtemp, mkdir, writeFile, rm } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { Effect } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { runtime, programsFor, seedQuality, inStore, executeQuality, stateHash } from "./quality-native.mjs"
import { boundaryCases } from "./judgment-data.mjs"
import { canonical, sha256 } from "./domain.mts"
import { loadRepairDatasetV2, inventory } from "./semantic-repair-v2-data.mjs"
import { repairedPrograms, repairProtocol, compactComparisonProgram, evidenceClosureRules,
  seriesCost, assertSealedPriorTrial, diagnostics } from "./semantic-repair-v2-domain.mts"
import { repairProtocol as v1, qualifiesRepair as oldGate } from "./semantic-repair-domain.mts"

test("candidate changes two program texts without diagnostic IDs or biomedical answer hints",()=>{
  const base=Object.freeze({direct:"old direct",reasoned:"old reasoning",judge:"old judge",short:"old short"}),out=repairedPrograms(base)
  assert.equal(out.judge,base.judge);assert.equal(out.short,base.short);assert.ok(out.reasoned.startsWith(base.reasoned))
  assert.equal(out.direct,compactComparisonProgram);assert.ok(out.direct.includes("ANALYSIS_COMPLETE"))
  assert.ok(!/scifact-|Gpr124|GATA-?3|glycolysis|GAPDH|gemcitabine|IPI-926|20888849/i.test(out.direct+evidenceClosureRules))
  assert.ok(!/EVIDENCE:\s*\d/.test(evidenceClosureRules));assert.equal(base.direct,"old direct")
})

test("comparison gates, model sampling and output bounds are unchanged",()=>{
  for(const k of ["maximumCalls","maximumTokens","maxTokens","durationMs","development","acceptance","sampling","transport"])
    assert.deepEqual(repairProtocol[k],v1[k])
  const score={cases:20,baselineLabels:17,candidateLabels:18,baselineGrounded:15,candidateGrounded:16,labelGains:2,labelLosses:1,baselineTokens:1,candidateTokens:2}
  assert.equal(oldGate(score,"develop",8,[7,8]),false)
  assert.equal(oldGate({...score,candidateGrounded:17},"develop",8,[7,8]),true)
})

test("cumulative costs preserve the completed trial and reject invalid current usage",()=>{
  assert.equal(seriesCost(0,0).totalCalls,80)
  assert.equal(seriesCost(152,1200000).totalCalls,232)
  assert.equal(seriesCost(152,1200000).totalTokens,1407581)
  for(const [calls,tokens] of [[-1,0],[153,0],[0,1200001],[true,0],[1,NaN],[1,1.5]])assert.throws(()=>seriesCost(calls,tokens))
})

test("a prior opened, uncertain or changed-cost trial cannot certify an unused holdout",()=>{
  const valid={nativeWireVerified:true,development:{passed:false},freshTestOpened:false,evaluation:null,calls:80,tokens:207581}
  assert.doesNotThrow(()=>assertSealedPriorTrial(valid))
  for(const patch of [{nativeWireVerified:false},{development:{passed:true}},{freshTestOpened:true},{evaluation:{}},{calls:81},{tokens:207582}])
    assert.throws(()=>assertSealedPriorTrial({...valid,...patch}))
})

test("inventory detects unreported requests without modifying historical evidence",async()=>{
  const root=await mkdtemp(join(process.env.STORAGE_MEMORY_TMPDIR??tmpdir(),"repair-v2-inventory-"))
  try{
    for(const dir of ["rows","wire"])await mkdir(join(root,dir))
    await writeFile(join(root,"rows","one.json"),"{}")
    const before=await inventory(root)
    await writeFile(join(root,"wire","1-request.json"),"{}")
    const after=await inventory(root)
    assert.equal(after.files,before.files+1);assert.notEqual(after.sha256,before.sha256)
  }finally{await rm(root,{recursive:true,force:true})}
})

test("the actual prior receipt remains intact and v2 reuses exactly the sealed cases and baseline",async()=>{
  const d=await loadRepairDatasetV2(".hswm-local/judgment-scifact-v1")
  const old=JSON.parse(await readFile(".hswm-local/semantic-repair-20261115/baseline/plan.json","utf8"))
  assert.ok(canonical(d.cases)===canonical(old.cases),"case identity/order drift")
  assert.ok(canonical(d.baselinePrograms)===canonical(old.programs),"baseline drift")
  assert.equal(d.cases.filter(c=>c.split==="test").length,18)
  assert.equal(sha256(await readFile("_research/completion_evidence_learning_v1/semantic-repair-run.mjs")),"b8ec9fa3510c611fe0e81677e155ff451ab66a450067b8c9c0ff74d238049a0a")
})

test("length and additional-citation diagnostics do not become semantic truth or acceptance",()=>{
  const c={...boundaryCases[0],id:"fixture",sentences:["setup","result","unrelated"],rationales:[[0,1]]}
  const d=diagnostics([{caseId:"fixture",analysis:{text:"x".repeat(256)},certificate:"EVIDENCE: 0,1,2"}],[c])
  assert.equal(d.atNativeLimit,1);assert.equal(d.citationIndices,3);assert.equal(d.additionalIndicesVersusClosestReference,1)
  assert.match(d.scope,/NOT_SEMANTIC/)
  assert.throws(()=>diagnostics([{caseId:"missing"}],[c]))
})

test("native v2 programs stay in their own store/stage and audit does not mutate canonical state",{timeout:120000},async()=>{
  const parent=await mkdtemp(join(process.env.STORAGE_MEMORY_TMPDIR??tmpdir(),"repair-v2-native-")),roots=[join(parent,"baseline"),join(parent,"candidate")]
  try{
    const r=await Effect.runPromise(runtime()),c=boundaryCases.find(x=>x.id==="boundary-risk-utility"),original=programsFor([])
    const base={...original,direct:original.direct+"\nBASE_DIRECT_MARKER"},programs=[base,repairedPrograms(base)]
    for(const [i,root]of roots.entries()){
      await mkdir(root);await mkdir(join(root,"stores"))
      await Effect.runPromise(inStore(r,root,rt=>seedQuality(r,rt,[c],programs[i],{fixture:true,version:2,arm:i})))
    }
    const session=await Effect.runPromise(inStore(r,roots[0],a=>inStore(r,roots[1],b=>Effect.gen(function*(){
      const stores=[a,b],before=yield* Effect.forEach(stores,rt=>rt.snapshot.pipe(Effect.map(s=>stateHash(r,s))))
      for(const i of [1,0]){
        let calls=0
        const http={postJson:request=>Effect.sync(()=>{
          const prompt=JSON.parse(new TextDecoder().decode(request.body)).messages[0].content,stage=calls++
          assert.equal(prompt.includes("COMPACT_SOURCE_COMPARISON_V2"),i===1&&stage===0)
          assert.equal(prompt.includes("EVIDENCE_CLOSURE_V2"),i===1&&stage===1)
          assert.equal(prompt.includes("BASE_DIRECT_MARKER"),i===0&&stage===0)
          const answer=stage===0?{prediction:"ANALYSIS_COMPLETE",uncertainty:"OBS: controlled risk; CLAIM: improved utility; GAP: utility unmeasured [0]"}:{prediction:"U",uncertainty:"EVIDENCE: none"}
          return new TextEncoder().encode(JSON.stringify({choices:[{message:{content:JSON.stringify(answer)}}],usage:{prompt_tokens:10,completion_tokens:10,total_tokens:20}}))
        })}
        const result=yield* executeQuality(r,stores[i],c,"reasoned",repairProtocol,"SCRIPTED_NOT_MODEL",http)
        assert.equal(calls,2);assert.equal(result.assessment.correct,true)
      }
      const after=yield* Effect.forEach(stores,rt=>rt.snapshot.pipe(Effect.map(s=>stateHash(r,s))));assert.deepEqual(after,before)
    }))))
    assert.equal(session.reads.nativeSubmissions,0);assert.equal(session.result.reads.nativeSubmissions,0)
  }finally{await rm(parent,{recursive:true,force:true})}
})
