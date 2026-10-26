#!/usr/bin/env node
/** Bounded query-directed USL/native-W study. Raw evidence stays in a new private root. */
import { readFile, writeFile, mkdir, readdir } from "node:fs/promises"
import { resolve, join, dirname } from "node:path"
import { pathToFileURL } from "node:url"
import { createHash } from "node:crypto"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const help = `node _research/multihop_activation_v1/evidence.mjs prepare NEW_PRIVATE_ROOT MODEL_ID USL_CHECKOUT
node _research/multihop_activation_v1/evidence.mjs run PRIVATE_ROOT
node _research/multihop_activation_v1/evidence.mjs check PRIVATE_ROOT
node _research/multihop_activation_v1/evidence.mjs inspect-usl USL_CHECKOUT
Internal: audit PRIVATE_ROOT (fresh process, never writes W).
Requires the built HSWM runtime and the selected built USL checkout.
Existing loopback provider only; 24-call cap, 2-hour local scope, no retries.
Two training questions; three held-out questions in frozen and trained arms.
Held-out means new question/route combinations in the same corpus, not unseen documents.
USL context construction is offline; locators are symbolic and are never resolved.
All native journals, actual model wire and original outcomes remain local.
Use the managed runner for prepare/run/check; do not rerun a partial root.
`
const io = f => Effect.tryPromise({ try: f, catch: e => new Error(String(e)) })
const need = (ok, message) => ok ? Effect.void : Effect.fail(new Error(message))
const hash = bytes => createHash("sha256").update(bytes).digest("hex")
const read = path => io(() => readFile(path))
const json = path => read(path).pipe(Effect.map(bytes => JSON.parse(bytes)))
const save = (path, value) => io(() => writeFile(path, JSON.stringify(value, null, 2)+"\n", { flag: "wx", mode: 0o600 }))
const unwrap = e => { if (Either.isLeft(e)) throw e.left; return e.right }
const dist = "src/hswm/effect-runtime/dist"
const loadRuntime = () => io(async () => {
  const loaded = await Promise.all(["canonical-atom-v2-durable-runtime", "canonical-atom-v2-content-bound", "semantic-context-evidence-runtime",
    "semantic-context-evidence-example", "semantic-context-activation-runtime", "semantic-context-runtime", "semantic-context-domain", "adaptive-executor", "effect-posix-services"].map(n => import(pathToFileURL(resolve(dist, n+".js")).href)))
  return Object.assign({}, ...loaded)
})
const closurePins = async paths => {
  const seen = new Set(), pins = []
  for (let i=0; i<paths.length; i++) {
    const path = resolve(paths[i]); if(seen.has(path)) continue; seen.add(path)
    const bytes = await readFile(path); pins.push({ path, sha256: hash(bytes) })
    for (const m of bytes.toString().matchAll(/(?:from\s*|import\s*|import\(\s*)["'](\.[^"']+\.js)["']/g)) paths.push(join(dirname(path),m[1]))
  }
  return pins.sort((a,b)=>a.path.localeCompare(b.path))
}
const definitions = [
  {id:"root", ancestors:[], source:"Luma was made by Iven. Neri was made by Varo. The maker of an object not listed here is unknown.", next:["iven","varo"]},
  {id:"iven", ancestors:["root"], source:"Iven uses Sola port for cargo and Mira port for signals.", next:["sola","mira"]},
  {id:"varo", ancestors:["root"], source:"Varo uses Reni port for cargo and Tavi port for signals.", next:["reni","tavi"]},
  {id:"sola", ancestors:["root","iven"], source:"Sola port's marker color is cyan.", next:[]},
  {id:"mira", ancestors:["root","iven"], source:"Mira port's marker color is amber.", next:[]},
  {id:"reni", ancestors:["root","varo"], source:"Reni port's marker color is violet.", next:[]},
  {id:"tavi", ancestors:["root","varo"], source:"Tavi port's marker color is silver.", next:[]}
]
const cases = [
  {id:"train-luma-cargo", split:"train", question:"What color marks the cargo port used by the maker of Luma?", route:["root","iven","sola"], answer:"cyan"},
  {id:"train-neri-signal", split:"train", question:"What color marks the signals port used by the maker of Neri?", route:["root","varo","tavi"], answer:"silver"},
  {id:"test-luma-signal", split:"test", question:"Give the marker color of the port handling signals for Luma's maker.", route:["root","iven","mira"], answer:"amber"},
  {id:"test-neri-cargo", split:"test", question:"Give the marker color of the port handling cargo for Neri's maker.", route:["root","varo","reni"], answer:"violet"},
  {id:"test-missing", split:"test", question:"What color marks the cargo port used by the maker of the unlisted object Zefi?", route:["root"], answer:null}
]
const buildCorpus = uslRoot => Effect.gen(function* () {
  const usl = resolve(uslRoot)
  const {compileProgram} = yield* io(()=>import(pathToFileURL(join(usl,"dist/src/language/compiler.js")).href))
  const {agentContext} = yield* io(()=>import(pathToFileURL(join(usl,"dist/src/language/navigation.js")).href))
  const declarations = definitions.map(n=>({tag:"resource",name:n.id,locator:`kg://authored-evidence/${n.id}`}))
  declarations.push({tag:"resource",name:"boundary",locator:"kg://authored-evidence/boundary"})
  declarations.push({tag:"meaning",name:"next",roles:[{name:"from",kind:"kg"},{name:"to",kind:"kg"},{name:"scope",kind:"kg"}],
    description:"A local document link. Resource names identify subjects to consult. It declares navigation, not factual support or access permission."})
  for(const n of definitions) for(const next of n.next) declarations.push({tag:"link",name:`${n.id}_${next}`,meaning:"next",participants:[{role:"from",resource:n.id},{role:"to",resource:next},{role:"scope",resource:"boundary"}]})
  const plan = unwrap(compileProgram({languageVersion:"0.1",namespace:"hswm.evidence.study",declarations}))
  return definitions.map(n=>({id:n.id,ancestors:n.ancestors,source:n.source,
    navigation:unwrap(agentContext(plan,{focus:n.id,routes:[{meaning:"next",enter:"from",exit:"to"}],maxHops:1,maxResources:16,maxLinks:16,maxVisits:128})),
    edges:n.next.map((next,i)=>({id:i===0?"left":"right",link:`${n.id}_${next}`,resource:next,enteredRole:"from",exitedRole:"to",next}))}))
})
const prepare = (root, model, uslRoot) => Effect.gen(function* () {
  yield* need(model && uslRoot && root.startsWith(resolve(".hswm-local")+"/"), "Explicit existing model, USL checkout and ignored private root required")
  const usl = resolve(uslRoot), nodes=yield* buildCorpus(usl)
  const pins = yield* io(()=>closurePins([join(dist,"semantic-context-evidence-runtime.js"),join(dist,"semantic-context-evidence-example.js"),join(usl,"dist/src/language/compiler.js"),join(usl,"dist/src/language/navigation.js")]))
  pins.push({path:resolve("src/hswm/effect-runtime/package-lock.json"),sha256:hash(yield* read("src/hswm/effect-runtime/package-lock.json"))},
    {path:join(usl,"package-lock.json"),sha256:hash(yield* read(join(usl,"package-lock.json")))})
  const createdAt = new Date().toISOString(), expiresAt = new Date(Date.now()+7200000).toISOString()
  yield* io(()=>mkdir(root,{recursive:false,mode:0o700}))
  yield* save(join(root,"plan.json"),{contract:"hswm-evidence-study/v1",root,model,uslRoot:usl,createdAt,expiresAt,transport:"http://127.0.0.1:18801/v1",
    maximumCalls:24,maxTokens:512,maximumHops:3,nodes,cases,pins,runnerSha256:hash(yield* read(new URL(import.meta.url))),
    checkpoint:"NOT_ATTESTED",claim:"AUTHORED_COMPOSITION_HOLDOUT_NOT_NATURAL_TASK_GENERALIZATION",programLearning:false})
  yield* save(join(root,"access.json"),{planSha256:hash(yield* read(join(root,"plan.json"))),approvalBasis:"CURRENT_USER_REQUEST",recipient:"designated gj3447 HSWM maintainer (current task)",
    visibility:"LOCAL_ONLY",purpose:"Bounded question-directed activation and native W integration",expiresAt,revoked:false,
    mappings:[{resource:"urn:hswm:evidence-study",workspace:"selected-hswm-project",representation:root,capability:"ISOLATED_NATIVE_STATE"},
      {resource:"urn:usl:context-sdk",workspace:"selected-usl-checkout",representation:usl,capability:"PINNED_LOCAL_CONTEXT_FUNCTIONS"},
      {resource:"urn:hswm:existing-model",workspace:"existing-loopback",representation:"http://127.0.0.1:18801/v1",capability:"ONE_MODELS_GET_AND_24_TOKENIZE_AND_COMPLETIONS"}],
    revocation:"Set revoked:true; checked before each call. Expired/refused paths never renew or retry automatically."})
  return {status:"PREPARED",maximumCalls:24,expiresAt}
})
const scope = root => Effect.gen(function* () {
  const p=yield* json(join(root,"plan.json")), a=yield* json(join(root,"access.json"))
  yield* need(p.root===root&&!a.revoked&&Date.now()<Date.parse(a.expiresAt)&&a.expiresAt===p.expiresAt&&a.planSha256===hash(yield* read(join(root,"plan.json")))&&
    p.runnerSha256===hash(yield* read(new URL(import.meta.url))),"NOT_READY: changed, expired or revoked scope")
  for(const pin of p.pins) yield* need(hash(yield* read(pin.path))===pin.sha256,"NOT_READY: implementation drift; preserve predecessor")
  return p
})
const layer = (r,root,arm) => {
  const bytes=unwrap(r.canonicalAtomV2SchemaContentBytes(r.evidenceExampleSchema)), sha=unwrap(r.decodeCanonicalAtomV2SchemaContent(bytes)).binding.content.sha256
  return r.makeCanonicalAtomV2DurableRuntimeFileLayer(join(root,arm),"evidence-study",bytes,[{authorizationRef:"traversal-example",schemaVersion:r.evidenceExampleSchema.schemaVersion,schemaContentSha256:sha,scopes:["isolated-example"]}])
}
const judge = (c, id, action, nodes) => {
  const index=c.route.indexOf(id)
  if(action.action==="ABSTAIN") return c.answer===null
  if(action.action==="FOLLOW") {const expected=c.route[index+1];return index>=0&&nodes.find(n=>n.id===id)?.edges.find(e=>e.id===action.edgeId)?.next===expected&&expected!==undefined}
  return action.action==="ANSWER"&&c.answer!==null&&action.answer===c.answer&&c.route.every(id=>action.citations?.some(q=>q.sourceId===id))
}
const one = (root,p,r,arm,c,mode) => Effect.gen(function* () {
  const row=yield* Effect.gen(function* () {
    const runtime=yield* r.CanonicalAtomV2DurableRuntime, before=(yield* runtime.snapshot).canonical.revision
    const http={postJson:request=>Effect.gen(function* () {
      yield* scope(root)
      const names=yield* io(()=>readdir(root)), number=names.filter(n=>/^wire-\d+-request.json$/.test(n)).length+1
      yield* need(number<=p.maximumCalls,"Call budget exhausted")
      const wire=JSON.parse(new TextDecoder().decode(request.body)); yield* save(join(root,`wire-${number}-request.json`),wire)
      const tokenized=yield* io(async()=>{const response=await fetch("http://127.0.0.1:18801/tokenize",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({model:wire.model,messages:wire.messages}),signal:AbortSignal.timeout(10000)});if(!response.ok)throw new Error(`Tokenizer ${response.status}`);return response.json()})
      yield* save(join(root,`wire-${number}-tokens.json`),tokenized)
      yield* need(Number.isSafeInteger(tokenized.count)&&Number.isSafeInteger(tokenized.max_model_len)&&tokenized.count+wire.max_tokens<=tokenized.max_model_len,"Complete context exceeds model budget; no truncation")
      const start=performance.now(),response=yield* r.NativeAdaptiveHttpClient.postJson({...request,timeoutMs:30000})
      yield* save(join(root,`wire-${number}-response.json`),{arm,caseId:c.id,elapsedMs:performance.now()-start,response:JSON.parse(new TextDecoder().decode(response))})
      return response
    }).pipe(Effect.mapError(e=>new r.AdaptiveExecutorError({code:"HTTP_FAILED",detail:String(e)})))}
    const result=yield* r.executeEvidenceTraversal(runtime,{entry:r.evidenceExampleKey("step:root"),question:c.question,mode,maximumHops:p.maximumHops,
      maximumEvidenceBytes:8192,maximumWireBytes:393216,cell:{base_url:p.transport,model:p.model,max_tokens:p.maxTokens}}, {
      http,admit:proposal=>runtime.submit(proposal.candidate),target:key=>r.evidenceExampleTarget(key.atomUid,key.revisionId+1),
      features:(plan,step)=>Effect.succeed({encoderRevision:r.evidenceExampleConfig.encoderRevision,eventSha256:r.contextHash(plan.spec.event),
        values:[1,Math.min(c.question.length/4096,1),JSON.parse(plan.spec.event).hop/8,step.edges.length/8]}),
      evaluate:execution=>Effect.sync(()=>{let correct=false;try{correct=judge(c,execution.selection.policyKey.atomUid.slice("policy:".length),JSON.parse(execution.trace?.prediction??""),p.nodes)}catch{}
        return {reward:Number(correct),observed:JSON.stringify({caseId:c.id,correct}),source:"AUTHORED_PER_HOP_REFERENCE_NOT_CAUSAL_CREDIT",continue:true}})
    })
    const after=(yield* runtime.snapshot).canonical.revision
    yield* need(mode!=="AUDIT"||before===after,"AUDIT must not modify canonical state")
    return {caseId:c.id,arm,mode,before,after,result,correct:c.answer===null?result.status==="ABSTAINED":result.status==="ANSWERED"&&result.answer===c.answer}
  }).pipe(Effect.provide(layer(r,root,arm)),Effect.provide(r.NodePosixServicesLive))
  yield* save(join(root,`${arm}-${c.id}.json`),row)
  return {caseId:c.id,arm,correct:row.correct,status:row.result.status,hops:row.result.hops.length}
})
const audit = root => Effect.gen(function* () {
  const p=yield* scope(root),r=yield* loadRuntime(),rows=[]
  for(const c of p.cases.filter(c=>c.split==="test"))rows.push(yield* one(root,p,r,"trained",c,"AUDIT"))
  return {freshProcess:true,rows}
})
const run = root => Effect.gen(function* () {
  const p=yield* scope(root),r=yield* loadRuntime()
  yield* need(!(yield* io(()=>readdir(root))).includes("started.json"),"A partial study must not be rerun")
  yield* save(join(root,"started.json"),{at:new Date().toISOString()})
  const models=yield* io(async()=>{const response=await fetch(p.transport+"/models",{signal:AbortSignal.timeout(10000)});if(!response.ok)throw new Error(`NOT_READY: ${response.status}`);return response.json()})
  yield* need(models.data?.some(m=>m.id===p.model),"NOT_READY: selected model absent")
  yield* save(join(root,"reachability.json"),{at:new Date().toISOString(),selectedModel:p.model,status:"REACHABLE"})
  for(const arm of ["frozen","trained"]) yield* Effect.gen(function* () {const runtime=yield* r.CanonicalAtomV2DurableRuntime;yield* r.seedEvidenceExample(runtime,p.nodes)}).pipe(Effect.provide(layer(r,root,arm)),Effect.provide(r.NodePosixServicesLive))
  const rows=[]
  for(const c of p.cases.filter(c=>c.split==="test"))rows.push(yield* one(root,p,r,"frozen",c,"AUDIT"))
  for(const c of p.cases.filter(c=>c.split==="train"))rows.push(yield* one(root,p,r,"trained",c,"TRAIN"))
  const child=yield* io(()=>promisify(execFile)(process.execPath,[new URL(import.meta.url).pathname,"audit",root],{cwd:process.cwd(),timeout:240000,maxBuffer:1048576}))
  const restart=JSON.parse(child.stdout)
  yield* save(join(root,"summary.json"),{rows,restart,checkpoint:p.checkpoint,claim:p.claim,programLearning:false})
  return {rows,restart}
})
const check = root => Effect.gen(function* () {
  // Offline replay does not reuse the live authorization or contact any provider.
  const p=yield* json(join(root,"plan.json")),summary=yield* json(join(root,"summary.json")),r=yield* loadRuntime()
  yield* need(p.contract==="hswm-evidence-study/v1"&&summary.restart.freshProcess===true,"Completed pinned study required")
  const rows=[...summary.rows,...summary.restart.rows]
  yield* need(rows.length===8,"Two training and two three-question test arms required")
  const inventory=async directory=>{const rows=[];for(const e of await readdir(directory,{withFileTypes:true})){
    const path=join(directory,e.name)
    if(e.isDirectory())rows.push(...await inventory(path));else if(e.isFile())rows.push([path,hash(await readFile(path))]);else throw new Error("Unexpected native store entry")
  }return rows.sort((a,b)=>a[0].localeCompare(b[0]))}
  const before=yield* io(async()=>[...await inventory(join(root,"frozen")),...await inventory(join(root,"trained"))])
  let calls=0,tokenSubtotal=0,unknownUsage=0
  for(const row of rows){
    const saved=yield* json(join(root,`${row.arm}-${row.caseId}.json`)),c=p.cases.find(c=>c.id===row.caseId)
    yield* need(!!c&&saved.result.hops.length<=p.maximumHops,"Unknown question or hop budget violation")
    const observed=saved.result.status==="ANSWERED"?saved.result.answer:null
    const correct=c.answer===null?saved.result.status==="ABSTAINED":saved.result.status==="ANSWERED"&&observed===c.answer
    yield* need(correct===row.correct&&correct===saved.correct,"Terminal scalar outcome mismatch")
    if(saved.mode==="AUDIT")yield* need(saved.before===saved.after&&saved.result.hops.every(h=>h.result.readback===null),"Frozen audit wrote W")
    yield* Effect.gen(function* () {
      const runtime=yield* r.CanonicalAtomV2DurableRuntime,state=(yield* runtime.snapshot).canonical
      const native=content=>runtime.readContent(content).pipe(Effect.map(b=>JSON.parse(new TextDecoder().decode(b))))
      const receipt=yield* native(saved.result.receiptContent)
      yield* need(receipt.answer===observed&&receipt.status===saved.result.status&&receipt.hops.length===saved.result.hops.length,"Native traversal mismatch")
      for(const h of saved.result.hops){
        const trace=h.result.execution.trace; yield* need(trace!==null,"Actual execution trace missing")
        const stored=yield* native(trace.traceContent),request=yield* native(stored.requestContent),response=yield* native(stored.responseContent)
        const wire=yield* native(stored.transport.request),reply=yield* native(stored.transport.response)
        calls++
        const actualRequest=yield* json(join(root,`wire-${calls}-request.json`)),actualResponse=yield* json(join(root,`wire-${calls}-response.json`))
        yield* need(stored.prediction===trace.prediction&&r.contextHash(request.assembly)===r.contextHash(h.result.execution.assembly)&&
          request.prompt===wire.messages[0].content&&r.contextHash(wire)===r.contextHash(actualRequest)&&r.contextHash(reply)===r.contextHash(actualResponse.response)&&
          response.prediction===stored.prediction&&r.contextHash(JSON.parse(reply.choices[0].message.content))===r.contextHash(response),"Native execution differs from actual model wire")
        if(Number.isSafeInteger(reply.usage?.total_tokens))tokenSubtotal+=reply.usage.total_tokens;else unknownUsage++
        if(h.result.proposal){const atom=state.atoms.find(a=>r.contextHash(a.key)===r.contextHash(h.result.proposal.policyKey));yield* need(!!atom,"Admitted successor absent")
          yield* need(r.contextHash(yield* native(atom.content))===r.contextHash(h.result.proposal.policy),"Stored W differs from proposal")}
      }
    }).pipe(Effect.provide(layer(r,root,saved.arm)),Effect.provide(r.NodePosixServicesLive))
  }
  const after=yield* io(async()=>[...await inventory(join(root,"frozen")),...await inventory(join(root,"trained"))])
  yield* need(r.contextHash(before)===r.contextHash(after),"Checker changed native store bytes")
  yield* need(calls<=p.maximumCalls&&calls===(yield* io(()=>readdir(root))).filter(n=>/^wire-\d+-request.json$/.test(n)).length,"Call count mismatch")
  return {status:"PASS",rows:rows.length,calls,tokenSubtotal,unknownUsage,nativeFilesUnchanged:before.length,scope:"TERMINAL_OUTCOME_AND_NATIVE_TRACE_INTEGRITY_NOT_INDEPENDENT_W_GRADIENT_PROOF"}
})
const main=args=>{
  if(args.length===0||args[0]==="--help")return Effect.succeed(help)
  const [command,raw,model,usl]=args,root=resolve(raw??"")
  if(command==="inspect-usl")return buildCorpus(root).pipe(Effect.map(nodes=>({status:"LOCAL_CONTEXT_BUILT_NOT_EXECUTED",nodes:nodes.length,
    edges:nodes.reduce((n,x)=>n+x.edges.length,0),contextBytes:nodes.map(n=>({id:n.id,bytes:Buffer.byteLength(JSON.stringify(n.navigation)),roles:n.navigation.links.map(l=>l.participants.map(p=>p.role)),limitsReached:n.navigation.coverage.limitsReached}))})))
  if(command==="prepare")return prepare(root,model,usl)
  if(command==="run")return run(root)
  if(command==="audit")return audit(root)
  if(command==="check")return check(root)
  return Effect.fail(new Error(help))
}
process.exitCode = await runArgvProcessMain({refusalPrefix:"EVIDENCE_STUDY_REFUSED",program:args=>main(args).pipe(Effect.map(value=>typeof value==="string"?value:JSON.stringify(value)+"\n")),describeFailure:String},process.argv.slice(2))
