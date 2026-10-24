#!/usr/bin/env node
/** Bounded real-source consumer. All native state and original model evidence remain private. */
import { readFile, writeFile, mkdir, readdir } from "node:fs/promises"
import { resolve, join, dirname } from "node:path"
import { createHash } from "node:crypto"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import { Effect, Either, Layer } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer, makeCanonicalAtomV2DurableRuntimeLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2ContentFileStoreLayerFromService } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-file.js"
import { makeCanonicalAtomV2StateJournalFileStoreLayerFromService } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-state-journal-file.js"
import { NodePosixFileSystem, PosixFileSystem } from "../../src/hswm/effect-runtime/dist/effect-posix-filesystem.js"
import { NativeAdaptiveHttpClient, AdaptiveExecutorError } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"
import { readWorkspaceActivationSource, selectWorkspaceSourceUnit, seedWorkspaceActivation, executeWorkspaceActivation, workspaceActivationSchema, workspaceActivationSpec, workspaceActivationConfig } from "../../src/hswm/effect-runtime/dist/workspace-activation-runtime.js"
import { withLocalActivationSession } from "../../src/hswm/effect-runtime/dist/semantic-context-read-session.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { assembleContextActivation } from "../../src/hswm/effect-runtime/dist/semantic-context-activation-runtime.js"
import { contextHash } from "../../src/hswm/effect-runtime/dist/semantic-context-domain.js"
import { decodeWorkspaceManifest } from "../../src/hswm/effect-runtime/dist/workspace-manifest-domain.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const help = `node _research/workspace_activation_v2/run.mjs prepare NEW_PRIVATE_ROOT MODEL_ID
node _research/workspace_activation_v2/run.mjs run ROOT
node _research/workspace_activation_v2/check.mjs ROOT
node _research/workspace_activation_v2/run.mjs measure ROOT ENTRY_ID
Internal: resume ROOT (three fresh-process AUDIT calls)
Prepare pins the current 49-entry manifest, complete selected sources and implementation.
Run uses existing loopback http://127.0.0.1:18801/v1; 49 TRAIN + 3 AUDIT, maximum 52 calls / 2 hours.
No service changes, remote publishing, retries, credential reads or policy promotion.
Source scope is the complete first level-one Markdown section; its full parent and section catalog are stored natively.\nThe task is exact source-heading extraction: integration coverage, not natural-task efficacy.
Read-only measure compares actual bounded-file reads of native assembly, excluding runtime opening.
Historical source-only status remains historical. W is the neural operator gate; LLM weights are frozen.\n`
const io = f => Effect.tryPromise({ try: f, catch: e => new Error(String(e)) })
const need = (ok, message) => ok ? Effect.void : Effect.fail(new Error(message))
const hash = bytes => createHash("sha256").update(bytes).digest("hex")
const text = value => JSON.stringify(value, null, 2)+"\n"
const read = path => io(() => readFile(path))
const json = path => read(path).pipe(Effect.map(bytes => JSON.parse(bytes)))
const save = (path, value) => io(() => writeFile(path, text(value), { flag: "wx", mode: 0o600 }))
const unwrap = e => { if (Either.isLeft(e)) throw e.left; return e.right }
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(workspaceActivationSchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const grants = [{ authorizationRef: "workspace-source-operator", schemaVersion: workspaceActivationSchema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["read-reason-source"] }]
const modules = ["workspace-activation-runtime", "workspace-source-units-domain", "semantic-context-read-session", "semantic-context-neural-domain", "semantic-context-activation-domain", "semantic-context-activation-runtime", "semantic-context-loop-runtime", "semantic-context-runtime", "semantic-context-presentation-domain", "workspace-navigation-runtime", "canonical-atom-v2-durable-runtime"]
const pins = () => Effect.gen(function* () {
  const queue=modules.map(name=>`src/hswm/effect-runtime/dist/${name}.js`),seen=new Set(),result=[]
  for(let i=0;i<queue.length;i++){
    const path=queue[i];if(seen.has(path))continue;seen.add(path)
    const bytes=yield* read(path);result.push({path,sha256:hash(bytes)})
    for(const match of bytes.toString("utf8").matchAll(/(?:from\s*|import\s*|import\(\s*)["'](\.[^"']+\.js)["']/g))queue.push(join(dirname(path),match[1]))
  }
  for(const path of ["src/hswm/effect-runtime/package-lock.json"])result.push({path,sha256:hash(yield* read(path))})
  return result.sort((a,b)=>a.path.localeCompare(b.path))
})
const manifestPath = "ontology/workspace/HSWM_WORKSPACE.v1.json"
const getManifest = () => read(manifestPath).pipe(Effect.flatMap(bytes => decodeWorkspaceManifest(JSON.parse(bytes))))
const getSource = (manifest, id, unitId) => readWorkspaceActivationSource(manifest, id, (path, maximumBytes = 16777216) =>
  NodePosixFileSystem.readRegularBounded(resolve(path), { maximumBytes, operation: "workspace-activation-source" }).pipe(Effect.map(r => r.bytes))).pipe(
    Effect.flatMap(source => unitId === undefined ? Effect.succeed(source) : selectWorkspaceSourceUnit(source, unitId)))
const heading = body => /^#\s+(.+)$/m.exec(body)?.[1]?.trim() ?? null
const nativeRoot = (root, id) => join(root, "native", id)
const layer = (root, id) => makeCanonicalAtomV2DurableRuntimeFileLayer(nativeRoot(root,id), "workspace-source", schemaBytes, grants)
const scope = root => Effect.gen(function* () {
  const plan = yield* json(join(root,"plan.json")), access = yield* json(join(root,"access.json"))
  yield* need(!access.revoked && Date.now() < Date.parse(access.expiresAt) && access.expiresAt===plan.expiresAt && plan.root===root &&
    access.planSha256===hash(yield* read(join(root,"plan.json"))) && contextHash(plan.pins)===contextHash(yield* pins()) &&
    plan.runnerSha256===hash(yield* read(new URL(import.meta.url))) && plan.manifestSha256===hash(yield* read(manifestPath)), "NOT_READY: scope expired, revoked or changed")
  return plan
})
const prepare = (root, model) => Effect.gen(function* () {
  yield* need(typeof model==="string" && model.length>0 && model.length<256,"Explicit existing model ID required")
  yield* io(() => mkdir(root,{recursive:false,mode:0o700}))
  yield* io(() => mkdir(join(root,"native"),{mode:0o700}))
  yield* io(() => mkdir(join(root,"sources"),{mode:0o700}))
  const manifest = yield* getManifest(), cases=[]
  for (const entry of manifest.entries) {
    const whole=yield* getSource(manifest,entry.id), unit=whole.units.find(u=>u.heading?.level===1)
    yield* need(!!unit,`No complete level-one heading unit for ${entry.id}`)
    const source=yield* selectWorkspaceSourceUnit(whole,unit.id), expected=heading(whole.documentText)
    yield* need(expected!==null,`No top-level heading for ${entry.id}; no fabricated oracle`)
    yield* save(join(root,"sources",`${entry.id}.json`),source)
    cases.push({id:entry.id,sourceId:source.sourceId,unitId:unit.id,expected,question:"Return the exact text of the first Markdown level-one heading in the evidence source, excluding the leading # and surrounding whitespace. Copy original characters without translating. Preserve punctuation and inline Markdown. Output only that heading as prediction."})
  }
  const createdAt=new Date().toISOString(),expiresAt=new Date(Date.now()+7200000).toISOString()
  const plan={contract:"hswm-workspace-activation-study/v2",root,createdAt,expiresAt,model,transport:"http://127.0.0.1:18801/v1",maximumCalls:cases.length+3,
    cases, restart:["identity","fractal","tool-harness"],manifestSha256:hash(yield* read(manifestPath)),pins:yield* pins(),runnerSha256:hash(yield* read(new URL(import.meta.url))),
    evaluator:"EXACT_FIRST_MARKDOWN_HEADING/v1",scope:"REAL_SOURCE_EXTRACTION_INTEGRATION_NOT_NATURAL_EFFICACY",checkpoint:"NOT_ATTESTED",maxTokens:384}
  yield* io(()=>mkdir(join(root,"implementation"),{mode:0o700}))
  const archived=new Set()
  for(const pin of plan.pins){if(archived.has(pin.sha256))continue;archived.add(pin.sha256);yield* io(async()=>{const bytes=await readFile(pin.path);if(hash(bytes)!==pin.sha256)throw new Error("Implementation changed during archive");await writeFile(join(root,"implementation",pin.sha256),bytes,{flag:"wx",mode:0o600})})}
  yield* io(async()=>writeFile(join(root,"implementation","runner.mjs"),await readFile(new URL(import.meta.url)),{flag:"wx",mode:0o600}))
  yield* save(join(root,"plan.json"),plan)
  yield* save(join(root,"access.json"),{planSha256:hash(yield* read(join(root,"plan.json"))),recipient:"designated gj3447 HSWM maintainer (current Codex task)",
    purpose:"User-requested remaining local activation integration",approvalBasis:"CURRENT_USER_REQUEST",visibility:"LOCAL_ONLY",expiresAt,revoked:false,
    mappings:[{resource:"urn:hswm:workspace-topics",workspace:"selected-project",representation:process.cwd(),capability:"PINNED_SOURCE_READ_AND_ISOLATED_NATIVE_PARTITIONS"},
      {resource:"urn:hswm:existing-model",workspace:"loopback-model",representation:plan.transport,capability:`MODELS_GET_AND_${plan.maximumCalls}_TOKENIZE_AND_COMPLETIONS`}],
    revocation:"Set revoked:true here; checked before every call. No automatic renewal."})
  return {status:"PREPARED",entries:cases.length,maximumCalls:plan.maximumCalls,expiresAt}
})
const one = (root,plan,c,mode) => Effect.gen(function* () {
  yield* scope(root)
  const source=yield* getSource(yield* getManifest(),c.id,c.unitId)
  yield* need(source.sourceId===c.sourceId,"Visited source changed; preserve old W and create a new source binding")
  const started=performance.now()
  const result=yield* Effect.gen(function* () {
    const base=yield* CanonicalAtomV2DurableRuntime
    if(mode==="TRAIN") yield* seedWorkspaceActivation(base,source)
    const before=yield* base.snapshot
    const prior=before.canonical.atoms.filter(a=>a.key.atomUid==="policy:operators").sort((a,b)=>b.key.revisionId-a.key.revisionId)[0]
    const beforePolicy=JSON.parse(new TextDecoder().decode(yield* base.readContent(prior.content)))
    const http={postJson:request=>Effect.gen(function* () {
      yield* scope(root)
      const calls=(yield* io(()=>readdir(root))).filter(n=>/^wire-\d+-request.json$/.test(n)).length
      yield* need(calls<plan.maximumCalls,"Provider budget exhausted")
      yield* save(join(root,`wire-${calls+1}-request.json`),JSON.parse(new TextDecoder().decode(request.body)))
      const wire=JSON.parse(new TextDecoder().decode(request.body))
      const tokenized=yield* io(async()=>{const r=await fetch("http://127.0.0.1:18801/tokenize",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({model:wire.model,messages:wire.messages}),signal:AbortSignal.timeout(10000)});if(!r.ok)throw new Error(`tokenize status ${r.status}`);return r.json()})
      yield* save(join(root,`wire-${calls+1}-tokens.json`),{count:tokenized.count,max_model_len:tokenized.max_model_len,reservedOutput:wire.max_tokens})
      yield* need(Number.isSafeInteger(tokenized.count)&&Number.isSafeInteger(tokenized.max_model_len)&&tokenized.count+wire.max_tokens<=tokenized.max_model_len,
        "Complete selected unit exceeds the actual model token budget; no truncation or provider retry")
      const start=performance.now(),response=yield* NativeAdaptiveHttpClient.postJson({...request,timeoutMs:30000}).pipe(Effect.tapError(error=>
        save(join(root,`wire-${calls+1}-error.json`),{tag:error._tag,code:error.code,detail:error.detail})))
      yield* save(join(root,`wire-${calls+1}-response.json`),JSON.parse(new TextDecoder().decode(response)))
      yield* save(join(root,`wire-${calls+1}-time.json`),{elapsedMs:performance.now()-start,entry:c.id,mode})
      return response
    }).pipe(Effect.mapError(e=>new AdaptiveExecutorError({code:"HTTP_FAILED",detail:String(e)})))}
    const session=yield* withLocalActivationSession(nativeRoot(root,c.id),base,local=>executeWorkspaceActivation(local,source,
      {question:c.question,intent:"EXACT",mode,cell:{base_url:plan.transport,model:plan.model,max_tokens:plan.maxTokens}},
      {http,admit:p=>local.submit(p.candidate),evaluate:execution=>Effect.succeed({reward:Number(execution.trace.prediction===c.expected),observed:c.expected,
        source:plan.evaluator+":DECLARED_SOURCE_EXTRACTION_ORACLE",continue:true})}))
    const after=yield* base.snapshot
    yield* need(contextHash(before.canonical.atoms.filter(a=>a.kind!=="semantic_context_policy"))===contextHash(after.canonical.atoms.filter(a=>a.kind!=="semantic_context_policy")),"Source rules changed")
    return {beforeRevision:before.canonical.revision,afterRevision:after.canonical.revision,beforePolicy,session}
  }).pipe(Effect.provide(layer(root,c.id)))
  yield* need((yield* getSource(yield* getManifest(),c.id,c.unitId)).sourceId===c.sourceId,"Source changed during execution; retain partial evidence")
  const row={entry:c.id,mode,sourceId:c.sourceId,elapsedMs:performance.now()-started,...result}
  yield* save(join(root,`${mode.toLowerCase()}-${c.id}.json`),row)
  return {entry:c.id,mode,reward:row.session.result.assessment.reward,policyRevision:row.session.result.execution.selection.policyKey.revisionId,updated:row.session.result.status==="UPDATED",reads:row.session.reads}
})
const resume = root => Effect.gen(function* () {
  const plan=yield* scope(root),rows=[]
  for(const id of plan.restart) { const c=plan.cases.find(c=>c.id===id); yield* need(!!c,"Unknown restart entry"); rows.push(yield* one(root,plan,c,"AUDIT")) }
  return {status:"REOPENED",separateOsProcess:true,rows}
})
const run = root => Effect.gen(function* () {
  const plan=yield* scope(root)
  const files=yield* io(()=>readdir(root));yield* need(!files.some(n=>n.startsWith("wire-")),"Partial or finished run exists; no retry")
  const probe=yield* io(async()=>{const r=await fetch(plan.transport+"/models",{signal:AbortSignal.timeout(5000)});if(!r.ok)throw new Error(`models status ${r.status}`);return r.json()})
  yield* need(Array.isArray(probe.data)&&probe.data.some(x=>x.id===plan.model),"Registered model is unreachable")
  yield* save(join(root,"reachability.json"),{reachable:true,model:plan.model,at:new Date().toISOString()})
  const rows=[]
  for(const c of plan.cases) { const r=yield* one(root,plan,c,"TRAIN");rows.push(r);yield* Effect.sync(()=>process.stderr.write(text({entry:r.entry,reward:r.reward,updated:r.updated}))) }
  const child=yield* io(()=>promisify(execFile)(process.execPath,[new URL(import.meta.url).pathname,"resume",root],{timeout:180000,maxBuffer:1048576}))
  const restarted=JSON.parse(child.stdout);yield* save(join(root,"reopened.json"),restarted)
  const summary={status:"COMPLETED",rows,restarted};yield* save(join(root,"summary.json"),summary);return summary
})
const measure = (root,id) => Effect.gen(function* () {
  const plan=yield* json(join(root,"plan.json")),c=plan.cases.find(c=>c.id===id);yield* need(!!c,"Unknown entry")
  const source=yield* json(join(root,"sources",`${id}.json`))
  const metrics={calls:0,bytes:0,byPath:{}}
  const fs={...NodePosixFileSystem,readRegularBounded:(path,options)=>NodePosixFileSystem.readRegularBounded(path,options).pipe(Effect.tap(r=>Effect.sync(()=>{
    metrics.calls++;metrics.bytes+=r.bytes.byteLength;const relative=path.slice(nativeRoot(root,id).length+1);metrics.byPath[relative]=(metrics.byPath[relative]??0)+r.bytes.byteLength
  })))}
  const measuredLayer=makeCanonicalAtomV2DurableRuntimeLayer("workspace-source",schemaBytes,grants).pipe(Layer.provide([
    makeCanonicalAtomV2ContentFileStoreLayerFromService(nativeRoot(root,id)),makeCanonicalAtomV2StateJournalFileStoreLayerFromService(nativeRoot(root,id),"workspace-source",schemaHash)
  ]),Layer.provide(Layer.succeed(PosixFileSystem,fs)))
  return yield* Effect.gen(function* () {
    const base=yield* CanonicalAtomV2DurableRuntime
    const assemble=runtime=>Effect.gen(function* () {
      const state=yield* runtime.snapshot,policy=state.canonical.atoms.filter(a=>a.key.atomUid==="policy:operators").sort((a,b)=>b.key.revisionId-a.key.revisionId)[0]
      const context=yield* prepareSemanticContext(runtime,workspaceActivationSpec(JSON.stringify({question:c.question,intent:"EXACT",sourceId:source.sourceId})))
      return yield* assembleContextActivation(runtime,context,{policyKey:policy.key,mode:"EXPLOIT",features:{encoderRevision:workspaceActivationConfig.encoderRevision,eventSha256:contextHash(context.spec.event),values:[1,0,Math.min(1,c.question.length/4096)]}})
    })
    const reset=()=>{metrics.calls=0;metrics.bytes=0;metrics.byPath={}}
    reset();const before=performance.now(),baseline=yield* assemble(base),baselineMs=performance.now()-before,baselineReads=structuredClone(metrics)
    reset();const start=performance.now(),local=yield* withLocalActivationSession(nativeRoot(root,id),base,assemble,fs),localMs=performance.now()-start,localReads=structuredClone(metrics)
    yield* need(contextHash(baseline)===contextHash(local.result),"Assembly changed")
    return {entry:id,assemblyIdentical:true,baseline:{elapsedMs:baselineMs,...baselineReads},local:{elapsedMs:localMs,...localReads},session:local.reads,
      boundary:"BOUNDED_FILE_READ_RETURN_BYTES_NOT_PHYSICAL_DISK_IO;EXCLUDES_LAYER_OPEN;INCLUDES_SESSION_OPEN_AND_FINAL_GLOBAL_AUDIT;ONE_PARTITION_ONLY"}
  }).pipe(Effect.provide(measuredLayer))
})

const main = args => {
  if(args[0]==="--help"||args.length===0)return Effect.succeed(help)
  const root=resolve(args[1]??"")
  if(args[0]==="prepare")return prepare(root,args[2]).pipe(Effect.map(text))
  if(args[0]==="run")return run(root).pipe(Effect.map(text))
  if(args[0]==="resume")return resume(root).pipe(Effect.map(text))
  if(args[0]==="measure")return measure(root,args[2]).pipe(Effect.map(text))
  return Effect.fail(new Error("Use --help; independent verification is check.mjs ROOT"))
}
process.exitCode=await runArgvProcessMain({refusalPrefix:"WORKSPACE_ACTIVATION_REFUSED",program:()=>main(process.argv.slice(2)),describeFailure:e=>e.detail??e.message??String(e)},[])
