#!/usr/bin/env node
/** Independent outcome and gradient arithmetic, then native byte/readback checks. No model calls. */
import assert from "node:assert/strict"
import { readFile, readdir } from "node:fs/promises"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { workspaceActivationSchema } from "../../src/hswm/effect-runtime/dist/workspace-activation-runtime.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
const io = f => Effect.tryPromise({try:f,catch:e=>new Error(String(e))})
const checked = f => Effect.try({try:f,catch:e=>new Error(String(e))})
const read = path => io(()=>readFile(path))
const json = path => read(path).pipe(Effect.map(b=>JSON.parse(b)))
const hash = b => createHash("sha256").update(b).digest("hex")
const digest = x => hash(JSON.stringify(x))
const nativeInventory = root => io(async()=>{
  const queue=[join(root,"native")],files=[]
  for(let i=0;i<queue.length;i++)for(const entry of await readdir(queue[i],{withFileTypes:true})){
    const path=join(queue[i],entry.name)
    if(entry.isDirectory())queue.push(path)
    else if(entry.isFile())files.push({path:path.slice(root.length+1),sha256:hash(await readFile(path))})
    else throw new Error("Unexpected native file type")
  }
  return files.sort((a,b)=>a.path.localeCompare(b.path))
})
const close = (a,b) => {assert.equal(a.length,b.length);a.forEach((x,i)=>{if(Array.isArray(x))close(x,b[i]);else assert(Math.abs(x-b[i])<1e-12,`${x} != ${b[i]}`)})}
// Independent scalar chain rule for 0.5*(sigmoid(v.tanh(Wx))-reward)^2.
const learnedNetwork = (before,x,selected,reward) => {
  const g=before.network,aug=[...x,1],hidden=[]
  for(const row of g.hidden){let total=0;for(let j=0;j<aug.length;j++)total+=row[j]*aug[j];hidden.push(Math.tanh(total))}
  let output=g.outputs[selected][hidden.length]
  for(let i=0;i<hidden.length;i++)output+=g.outputs[selected][i]*hidden[i]
  const prediction=1/(1+Math.exp(-output)),d=(prediction-reward)*prediction*(1-prediction)
  const dh=[],dv=g.outputs.map(row=>row.map(()=>0))
  for(let i=0;i<hidden.length;i++)dh.push(aug.map(z=>d*g.outputs[selected][i]*(1-hidden[i]*hidden[i])*z))
  for(let i=0;i<hidden.length;i++)dv[selected][i]=d*hidden[i]
  dv[selected][hidden.length]=d
  const norm=Math.sqrt([...dh.flat(),...dv.flat()].reduce((a,b)=>a+b*b,0)),config=before.config.neural
  const step=config.learningRate*(norm>config.gradientNormLimit?config.gradientNormLimit/norm:1)
  return {hidden:g.hidden.map((row,i)=>row.map((v,j)=>v-step*dh[i][j])),outputs:g.outputs.map((row,i)=>row.map((v,j)=>v-step*dv[i][j]))}
}
const inspect = (row,source,c,plan) => {
  assert.equal(row.sourceId,source.sourceId);assert.equal(digest(source.binding),source.sourceId)
  assert.equal(source.sourceId,c.sourceId)
  assert.equal(hash(source.documentText),source.binding.documentSha256)
  assert.equal(hash(source.sourceText),source.binding.activationSha256)
  assert.equal(Buffer.from(source.documentText).subarray(source.binding.selection.startByte,source.binding.selection.endByte).toString("utf8"),source.sourceText)
  assert.equal(source.binding.selection.unitId,c.unitId)
  assert.equal(source.units.map(u=>u.text).join(""),source.documentText)
  const result=row.session.result,expected=/^#\s+(.+)$/m.exec(source.documentText)?.[1]?.trim()
  assert.equal(expected,c.expected)
  const observed=Number(result.execution.trace.prediction===expected)
  assert.equal(result.assessment.reward,observed)
  if(plan.extraction){
    const v=result.sourceVerification
    assert.equal(v.contract,"hswm-workspace-extraction/v1");assert.equal(v.selector,plan.extraction)
    assert.equal(v.sourceId,source.sourceId);assert.equal(v.documentSha256,hash(source.documentText));assert.equal(v.activationSha256,hash(source.sourceText))
    const match=/^#[\t ]+([^\r\n]*)/m.exec(source.documentText)
    const start=match.index+match[0].indexOf(expected)
    assert.equal(v.startByte,Buffer.byteLength(source.documentText.slice(0,start)));assert.equal(v.endByte,v.startByte+Buffer.byteLength(expected))
    assert.equal(Buffer.from(source.documentText).subarray(v.startByte,v.endByte).toString("utf8"),expected)
    assert.equal(v.status,observed?"MATCH":"MISMATCH");assert.equal(v.expectedSha256,hash(expected));assert.equal(v.observedSha256,hash(result.execution.trace.prediction))
    assert.equal(result.verifiedPrediction,observed?expected:null)
    const event=JSON.parse(result.execution.assembly.payload.event),{status,expectedSha256,observedSha256,...binding}=v
    assert.deepEqual(event.extraction,binding);assert.deepEqual(JSON.parse(result.assessment.observed).verification,v)
  }else assert.equal(result.assessment.observed,expected)
  assert.equal(result.execution.selection.policySha256,digest(row.beforePolicy))
  assert.equal(result.execution.selection.source,"NEURAL_TOP1_OPERATOR_GATE_NOT_LLM_WEIGHT_TRAINING")
  assert.deepEqual(result.execution.assembly.payload.frames.map(f=>f.relation.key.atomUid),["rule:required",`rule:${result.execution.selection.candidateId}`])
  for(const frame of result.execution.assembly.payload.frames){
    assert.deepEqual(frame.roles.map(r=>r.role),["subject","context","evidence","exception"])
    assert.equal(frame.roles.find(r=>r.role==="evidence").contentUtf8,source.sourceText)
    assert.deepEqual(JSON.parse(frame.roles.find(r=>r.role==="context").contentUtf8),plan.sourceRoles==="NAVIGATION_DISTINCT_V1"?{...source.binding,titleRole:"NAVIGATION_LABEL_NOT_DOCUMENT_HEADING"}:source.binding)
  }
  assert.equal(row.session.reads.fullSnapshots,2)
  if(row.mode==="TRAIN"){
    assert.equal(row.beforeRevision,Math.ceil((source.units.length+9)/64)+1);assert.equal(row.afterRevision,row.beforeRevision+1)
    assert.equal(result.execution.selection.policyKey.revisionId,0);assert.equal(result.proposal.policyKey.revisionId,1)
    assert.equal(result.status,"UPDATED");assert.equal(row.session.reads.nativeSubmissions,1)
    const selected=row.beforePolicy.arms.findIndex(a=>a.candidateId===result.execution.selection.candidateId)
    const expectedNetwork=learnedNetwork(row.beforePolicy,result.execution.selection.features.values,selected,observed)
    close(expectedNetwork.hidden,result.proposal.policy.network.hidden);close(expectedNetwork.outputs,result.proposal.policy.network.outputs)
    assert.notEqual(digest(row.beforePolicy.network),digest(result.proposal.policy.network))
    assert.deepEqual(result.readback.policy,result.proposal.policy)
  }else{
    assert.equal(row.beforeRevision,Math.ceil((source.units.length+9)/64)+2);assert.equal(row.afterRevision,row.beforeRevision)
    assert.equal(result.execution.selection.policyKey.revisionId,1);assert.equal(result.status,"AUDITED")
    assert.equal(result.proposal,null);assert.equal(row.session.reads.nativeSubmissions,0)
  }
  return observed
}
const main = root => Effect.gen(function* () {
  const nativeBefore=yield* nativeInventory(root)
  const plan=yield* json(join(root,"plan.json")),summary=yield* json(join(root,"summary.json")),reopened=yield* json(join(root,"reopened.json"))
  const allEntries=plan.contract==="hswm-workspace-activation-study/v4-extraction-all",extraction=allEntries||plan.contract==="hswm-workspace-activation-study/v3-extraction"
  const entryCount=extraction&&!allEntries?2:49,restartCount=allEntries?49:extraction?2:3,callCount=entryCount+restartCount
  const manifest=allEntries?yield* read("ontology/workspace/HSWM_WORKSPACE.v1.json"):null
  yield* checked(()=>{assert(extraction||plan.contract==="hswm-workspace-activation-study/v2");
    if(extraction){assert.equal(plan.extraction,"FIRST_ATX_H1_TEXT_V1");
      if(allEntries){assert.equal(hash(manifest),plan.manifestSha256);assert.deepEqual(plan.cases.map(c=>c.id),JSON.parse(manifest).entries.map(e=>e.id));assert.equal(new Set(plan.cases.map(c=>c.id)).size,49);assert.equal(plan.presentation,"source_evidence_tail")}
      else assert.deepEqual(plan.cases.map(c=>c.id),["performance-proof","optimization-rules"])
      assert.deepEqual(plan.restart,plan.cases.map(c=>c.id))}
    else assert.equal(plan.extraction,undefined)
    assert.equal(plan.maximumCalls,callCount);assert.equal(plan.cases.length,entryCount);assert.equal(summary.rows.length,entryCount);assert.equal(reopened.separateOsProcess,true);assert.equal(reopened.rows.length,restartCount)})
  for(const pin of plan.pins){const actual=hash(yield* read(pin.path)),archived=hash(yield* read(join(root,"implementation",pin.sha256)));yield* checked(()=>{assert.equal(actual,pin.sha256,`Implementation drift: ${pin.path}`);assert.equal(archived,pin.sha256)})}
  const runnerSha=hash(yield* read(join(root,"implementation","runner.mjs")));yield* checked(()=>assert.equal(runnerSha,plan.runnerSha256))
  const wire=new Map()
  for(let i=1;i<=callCount;i++){
    const timing=yield* json(join(root,`wire-${i}-time.json`)),request=yield* json(join(root,`wire-${i}-request.json`)),response=yield* json(join(root,`wire-${i}-response.json`))
    const key=`${timing.mode}:${timing.entry}`
    yield* checked(()=>assert(!wire.has(key),"Duplicate wire attempt"));const tokens=yield* json(join(root,`wire-${i}-tokens.json`))
    yield* checked(()=>{assert(tokens.count+tokens.reservedOutput<=tokens.max_model_len);assert.equal(tokens.reservedOutput,request.max_tokens)})
    wire.set(key,{request,response,tokens})
  }
  const schema=canonicalAtomV2SchemaContentBytes(workspaceActivationSchema)
  if(Either.isLeft(schema))return yield* Effect.fail(new Error("Invalid native schema"))
  let trainCorrect=0,auditCorrect=0,calls=0,totalTokens=0,unknownUsage=0,logicalPromptBytes=0,nativeContentChecks=0,sourceUnits=0,maxPromptTokens=0
  for(const c of plan.cases){
    const source=yield* json(join(root,"sources",`${c.id}.json`)),row=yield* json(join(root,`train-${c.id}.json`))
    sourceUnits+=source.units.length
    trainCorrect+=yield* checked(()=>inspect(row,source,c,plan))
    const rows=[row]
    if(plan.restart.includes(c.id)){const audit=yield* json(join(root,`audit-${c.id}.json`));auditCorrect+=yield* checked(()=>inspect(audit,source,c,plan));rows.push(audit)}
    yield* Effect.gen(function* () {
      const runtime=yield* CanonicalAtomV2DurableRuntime,state=yield* runtime.snapshot
      yield* checked(()=>assert.equal(state.canonical.revision,row.afterRevision))
      const nativeJson=descriptor=>runtime.readContent(descriptor).pipe(Effect.tap(bytes=>Effect.sync(()=>{assert.equal(hash(bytes),descriptor.sha256);nativeContentChecks++})),Effect.map(bytes=>JSON.parse(new TextDecoder().decode(bytes))))
      const current=state.canonical.atoms.find(a=>a.key.atomUid==="policy:operators"&&a.key.revisionId===1)
      yield* checked(()=>assert(current))
      const initial=state.canonical.atoms.find(a=>a.key.atomUid==="policy:operators"&&a.key.revisionId===0)
      const initialPolicy=yield* nativeJson(initial.content)
      yield* checked(()=>assert.deepEqual(initialPolicy,row.beforePolicy))
      const archive=state.canonical.atoms.find(a=>a.key.atomUid==="source:archive")
      const archiveBytes=yield* runtime.readContent(archive.content)
      yield* checked(()=>assert.equal(new TextDecoder().decode(archiveBytes),source.documentText))
      const catalogAtom=state.canonical.atoms.find(a=>a.key.atomUid==="source:catalog"),catalog=yield* nativeJson(catalogAtom.content)
      yield* checked(()=>{assert.equal(catalog.documentSha256,source.binding.documentSha256);assert.deepEqual(catalog.units,source.units.map(({text,...u})=>u));
        assert.deepEqual(catalogAtom.references.map(r=>r.target.atomUid),source.units.map(u=>`source:${u.id}`))})
      const storedPolicy=yield* nativeJson(current.content)
      yield* checked(()=>assert.deepEqual(storedPolicy,row.session.result.proposal.policy))
      for(const r of rows){
        const result=r.session.result,trace=result.execution.trace
        const storedTrace=yield* nativeJson(trace.traceContent)
        yield* checked(()=>{const {traceContent,...expected}=trace;assert.deepEqual(storedTrace,expected)})
        const request=yield* nativeJson(trace.requestContent),wireRequest=yield* nativeJson(trace.transport.request),wireResponse=yield* nativeJson(trace.transport.response)
        yield* checked(()=>{assert.deepEqual(request.assembly,result.execution.assembly);assert.equal(request.presentation,plan.presentation??"execution_tail");assert.equal(wireRequest.messages[0].content,request.prompt);
          assert.deepEqual(wireRequest,wire.get(`${r.mode}:${r.entry}`)?.request);assert.deepEqual(wireResponse,wire.get(`${r.mode}:${r.entry}`)?.response);
          assert.equal(JSON.parse(wireResponse.choices[0].message.content).prediction,trace.prediction)})
        if(result.proposal){const feedback=yield* nativeJson(result.proposal.outcomeContent);yield* checked(()=>{assert.equal(feedback.reward,result.assessment.reward);assert.equal(feedback.traceContent.sha256,trace.traceContent.sha256)})}
        if(extraction){const record=JSON.parse(result.assessment.observed).record,saved=yield* nativeJson(record)
          yield* checked(()=>{assert.equal(record.mediaType,"application/vnd.hswm.workspace-extraction-outcome-v1+json");assert.equal(result.assessment.source,`EXACT_SOURCE_SPAN_VERIFIER:${record.sha256}`);
            assert.deepEqual(saved.verification,result.sourceVerification);assert.deepEqual(saved.traceContent,trace.traceContent);
            assert.equal(saved.callerAssessment.observed,c.expected);assert.equal(saved.callerAssessment.reward,Number(trace.prediction===c.expected))})}
        maxPromptTokens=Math.max(maxPromptTokens,wire.get(`${r.mode}:${r.entry}`).tokens.count)
        calls++;logicalPromptBytes+=Buffer.byteLength(request.prompt)
        if(Number.isFinite(wireResponse.usage?.total_tokens))totalTokens+=wireResponse.usage.total_tokens;else unknownUsage++
      }
    }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(join(root,"native",c.id),"workspace-source",schema.right)))
  }
  const files=yield* io(()=>readdir(root));yield* checked(()=>{assert.equal(calls,callCount);assert.equal(files.filter(n=>/^wire-\d+-request.json$/.test(n)).length,calls)})
  const c=plan.cases[0],source=yield* json(join(root,"sources",`${c.id}.json`)),row=yield* json(join(root,`train-${c.id}.json`))
  for(const mutate of [r=>{r.session.result.assessment.reward=1-r.session.result.assessment.reward},r=>{r.session.result.execution.assembly.payload.frames[0].roles.pop()},r=>{r.session.result.proposal.policy.network.hidden[0][0]+=0.1}]){
    yield* checked(()=>{const changed=structuredClone(row);mutate(changed);assert.throws(()=>inspect(changed,source,c,plan))})
  }
  const nativeAfter=yield* nativeInventory(root);yield* checked(()=>assert.deepEqual(nativeAfter,nativeBefore))
  const checkerSha256=hash(yield* read(new URL(import.meta.url)))
  return {status:"PASS",nativeFilesUnchanged:true,nativeFiles:nativeBefore.length,checkerSha256,entries:entryCount,sourceUnits,maxPromptTokens,calls,nativeUpdates:entryCount,train:{correct:trainCorrect,total:entryCount},restart:{correct:auditCorrect,total:restartCount,policyRevision:1},
    totalTokens:unknownUsage?null:totalTokens,knownTokenSubtotal:totalTokens,unknownUsage,logicalPromptBytes,nativeContentChecks,mutationChecks:3,
    neuralParameterUpdates:true,modelWeightTraining:false,independentNaturalTaskEfficacy:false,locality:"ONE_SOURCE_PARTITION_WITH_GLOBAL_RECOVERY_WITHIN_THAT_PARTITION"}
})
if(process.argv[2]==="--help")process.stdout.write("node _research/workspace_activation_v2/check.mjs ROOT\nNo provider calls or policy writes. Checks outcomes, independent neural gradients, original wire and native readback.\n")
else process.exitCode=await runArgvProcessMain({refusalPrefix:"WORKSPACE_ACTIVATION_CHECK_REFUSED",program:()=>main(resolve(process.argv[2]??"")).pipe(Effect.map(x=>JSON.stringify(x,null,2)+"\n")),describeFailure:String},[])
