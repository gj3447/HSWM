/** Effect shell: authored baseline calibration, never a G0/G1 occurrence. */
import { createHash } from "node:crypto"
import { createRequire } from "node:module"
import { readFile, writeFile, appendFile, mkdir } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { performance } from "node:perf_hooks"
import { catalogTask } from "../relation_synthesis_usl_v1/fixtures.mjs"
import { observeCalibrationTasks } from "./usl-fixtures.mjs"
import {
  buildOpenBookPrompt, buildTextLessonConsolidationPrompt, buildTextLessonInferencePrompt,
  buildExecutableProgramConsolidationPrompt, buildProgramInferencePrompt,
  parseLessonResponse, parseProgramResponse, parseInferenceResponse, evaluateIndependentProgram,
  type CalibrationTrainingExample, type CalibrationTarget, type CalibrationProgram,
  type CalibrationPrompt
} from "../../../src/hswm/effect-runtime/src/research-relation-comparison.js"
import {
  runPinnedChat, decodePinnedChatConfig, ResearchPinnedChatHttp, ResearchPinnedChatCredentialSource,
  NativeResearchPinnedChatHttp, type PinnedChatConfig
} from "../../../src/hswm/effect-runtime/src/research-pinned-chat.js"
import { AdaptiveExecutorError } from "../../../src/hswm/effect-runtime/src/adaptive-executor.js"

const { Effect, Either, Ref } = createRequire(new URL("../../../src/hswm/effect-runtime/package.json", import.meta.url))("effect") as typeof import("effect")
const directory = dirname(fileURLToPath(import.meta.url))
const root = resolve(directory, "../../..")
const argument = (name:string):string|undefined => {
  const index = process.argv.indexOf(name)
  return index < 0 ? undefined : process.argv[index+1]
}
const sha = (bytes:string|Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const io = <A,>(run:()=>Promise<A>) => Effect.tryPromise({try:run,catch:()=>new Error("RESEARCH_FILE_IO_FAILED")})
const assert = (condition:boolean,code:string) => condition ? Effect.void : Effect.fail(new Error(code))
const unwrap = <A,E>(value:import("effect").Either.Either<A,E>) => Either.isLeft(value) ? Effect.fail(new Error("CALIBRATION_INPUT_INVALID")) : Effect.succeed(value.right)
const arms = ["ALL_TRAINING_HISTORY","CONSOLIDATED_TEXT_LESSON","EXECUTABLE_PROGRAM_LIBRARY"] as const
type Arm = typeof arms[number]
type Prediction = Readonly<{arm:Arm;task:string;uids:ReadonlyArray<string>;invalid:boolean;programSteps:number}>
const sourcePaths = [
  "_research/causal_composition/relation_llm_comparison_v1/run.mts",
  "_research/causal_composition/relation_llm_comparison_v1/usl-fixtures.mts",
  "_research/causal_composition/relation_llm_comparison_v1/protocol.v1.json",
  "_research/causal_composition/relation_llm_comparison_v1/tsconfig.json",
  "_research/causal_composition/relation_synthesis_usl_v1/fixtures.mts",
  "_research/causal_composition/relation_synthesis_usl_v1/protocol.v1.json",
  "_research/causal_composition/relation_synthesis_usl_v1/source-pins.v4.json",
  "src/hswm/effect-runtime/src/research-relation-comparison.ts",
  "src/hswm/effect-runtime/src/research-pinned-chat.ts",
  "src/hswm/effect-runtime/src/usl-native-snapshot.ts",
  "src/hswm/effect-runtime/src/adaptive-executor.ts",
  "src/hswm/effect-runtime/src/effect-bounded-subprocess.ts",
  "src/hswm/effect-runtime/package.json",
  "src/hswm/effect-runtime/package-lock.json"
] as const

const main = Effect.gen(function*(){
  const started = performance.now()
  const outputArgument = argument("--output")
  yield* assert(outputArgument !== undefined,"FRESH_OUTPUT_REQUIRED")
  const output = resolve(outputArgument!)
  yield* io(()=>mkdir(dirname(output),{recursive:true}))
  // Claim output and journal before any observation or request. Never reuse a run.
  yield* io(()=>writeFile(output,JSON.stringify({status:"STARTED",claim:"NO_RESULT_YET"})+"\n",{flag:"wx",mode:0o600}))
  const journal = output+".events.jsonl"
  yield* io(()=>writeFile(journal,"",{flag:"wx",mode:0o600}))
  const chain = yield* Ref.make({sequence:0,previous:"0".repeat(64)})
  const calls = yield* Ref.make({issued:0,completed:0,promptTokens:0,completionTokens:0,totalTokens:0,unknownUsage:0})
  const costs = yield* Ref.make<ReadonlyArray<unknown>>([])
  const sourceBindings = yield* Ref.make<ReadonlyArray<{path:string;sha256:string}>>([])
  const event = (kind:string,data:unknown) => Effect.gen(function*(){
    const prior = yield* Ref.get(chain)
    const body = JSON.stringify({sequence:prior.sequence,previous:prior.previous,kind,data})
    const digest = sha(body)
    yield* io(()=>appendFile(journal,JSON.stringify({body:JSON.parse(body),sha256:digest})+"\n"))
    yield* Ref.set(chain,{sequence:prior.sequence+1,previous:digest})
  })
  const run = Effect.gen(function*(){
    const protocolBytes = yield* io(()=>readFile(resolve(directory,"protocol.v1.json"),"utf8"))
    const protocol = JSON.parse(protocolBytes) as {training:{seeds:number[],affected_artifacts:number,role_arity:number};calibration:{seeds:number[],affected_artifacts:number,role_arity:number};scientific_status:unknown}
    const bindings = yield* Effect.forEach(sourcePaths,path=>Effect.gen(function*(){
      const bytes = yield* io(()=>readFile(resolve(root,path)))
      return {path,sha256:sha(bytes)}
    }))
    yield* Ref.set(sourceBindings,bindings)
    yield* event("SOURCE_AND_PROTOCOL_SEAL",{protocolSha256:sha(protocolBytes),bindings,claim:"LOCAL_PRE_REQUEST_SEAL_NOT_EXTERNAL_CHRONOLOGY_WITNESS"})
    const uslRoot = argument("--usl-root")
    yield* assert(uslRoot !== undefined,"EXACT_PINNED_USL_SOURCE_REQUIRED")
    const a = protocol.training, b = protocol.calibration
    const trainTasks = a.seeds.map(seed=>catalogTask(seed,a.affected_artifacts,a.role_arity))
    const calibrationTasks = b.seeds.map(seed=>catalogTask(seed,b.affected_artifacts,b.role_arity))
    const observed = yield* observeCalibrationTasks(resolve(uslRoot!),[...trainTasks,...calibrationTasks])
    const training:ReadonlyArray<CalibrationTrainingExample> = observed.rows.slice(0,trainTasks.length).map(row=>({id:row.task.id,focus:row.task.focus,graph:row.graph,expectedUids:row.task.expected}))
    const targets:ReadonlyArray<CalibrationTarget> = observed.rows.slice(trainTasks.length).map(row=>({id:row.task.id,focus:row.task.focus,graph:row.graph}))
    const primitives = JSON.parse(yield* io(()=>readFile(new URL("../relation_synthesis_usl_v1/protocol.v1.json",import.meta.url),"utf8"))).primitive_roles
    // No target labels enter this durable actor input. Oracle labels remain in the
    // authored fixture process and are compared only after predictions are sealed.
    const actorInput = {training,targets,snapshots:observed.rows.map(row=>({task:row.task.id,native:row.snapshot.native,snapshotSha256:sha(JSON.stringify(row.snapshot))}))}
    yield* io(()=>writeFile(output+".actor-input.json",JSON.stringify(actorInput,null,2)+"\n",{flag:"wx",mode:0o600}))
    yield* event("ACTOR_INPUT_SEAL",{sha256:sha(JSON.stringify(actorInput)),uslSourcePins:observed.sourcePins,counts:observed.counts,outcomeCustody:"SAME_AUTHOR_PROCESS_NOT_INDEPENDENT"})
    const promptPreview = yield* unwrap(buildOpenBookPrompt(training,targets[0]!))
    yield* assert(Buffer.byteLength(promptPreview.text)<=196608,"PROMPT_BUDGET_EXCEEDED")
    if(!process.argv.includes("--run")) return {
      status:"PREPARED_NO_MODEL_CALLS",scope:"ENGINEERING_READINESS_ONLY",modelCalls:0,
      trainingTasks:training.length,calibrationTasks:targets.length,observations:observed.counts,
      largestPreviewBytes:Buffer.byteLength(promptPreview.text),scientificStatus:protocol.scientific_status,
      requiredNextInput:"Reachable model endpoint, exact model id, credential environment name, and explicit identity tier. Configuration must be sealed before --run."
    }
    const configFile = argument("--config")
    yield* assert(configFile !== undefined,"MODEL_CONFIGURATION_REQUIRED")
    const configBytes = yield* io(()=>readFile(resolve(configFile!),"utf8"))
    const config: PinnedChatConfig = yield* unwrap(decodePinnedChatConfig(JSON.parse(configBytes)))
    yield* assert(config.tokenLimit.value<=2048 && config.timeoutMs<=60000,"PROTOCOL_CALL_BUDGET_INVALID")
    // This native adapter implements POST only. A separate trusted transport is
    // required for GET preflight or endpoint-bound deployment attestation.
    yield* assert(config.preflight==="NONE" && config.identityProof.level!=="VERIFIED_DEPLOYMENT_DIGEST","NATIVE_RUNNER_PREFLIGHT_UNSUPPORTED")
    const fixtureMode=process.argv.includes("--transport-fixture")
    yield* assert(fixtureMode ? config.modelId==="transport-fixture" && ["127.0.0.1","localhost","[::1]"].includes(new URL(config.endpoint).hostname) : config.modelId!=="transport-fixture","TRANSPORT_FIXTURE_MODE_MISMATCH")
    yield* event("MODEL_CONFIGURATION_SEAL",{sha256:sha(configBytes),modelId:config.modelId,identityProof:config.identityProof,decoding:config.decoding,tokenLimit:config.tokenLimit,endpointSha256:sha(config.endpoint),researchMode:config.researchMode})
    const http = {
      postJson:(request:Parameters<typeof NativeResearchPinnedChatHttp.postJson>[0])=>Effect.gen(function*(){
        const count = yield* Ref.get(calls)
        if(count.issued>=20) return yield* Effect.fail(new AdaptiveExecutorError({code:"HTTP_INVALID",detail:"CALIBRATION_CALL_CAP"}))
        // The exact request body is sealed before issuing the HTTP operation.
        yield* event("HTTP_REQUEST_SEALED",{requestSha256:sha(request.body),bodyUtf8:Buffer.from(request.body).toString("utf8")}).pipe(Effect.mapError(()=>new AdaptiveExecutorError({code:"HTTP_FAILED",detail:"SEAL_FAILED"})))
        yield* Ref.update(calls,c=>({...c,issued:c.issued+1}))
        const response = yield* NativeResearchPinnedChatHttp.postJson(request)
        yield* event("HTTP_RESPONSE_RECEIVED",{responseSha256:sha(response),rawBase64:Buffer.from(response).toString("base64")}).pipe(Effect.mapError(()=>new AdaptiveExecutorError({code:"HTTP_FAILED",detail:"SEAL_FAILED"})))
        return response
      })
    }
    const call = (arm:Arm,phase:"consolidation"|"inference",task:string,prompt:CalibrationPrompt)=>Effect.gen(function*(){
      const bytes = Buffer.byteLength(prompt.text)
      yield* assert(bytes<=196608,"PROMPT_BUDGET_EXCEEDED")
      yield* event("MODEL_CALL_INTENT",{arm,phase,task,promptSha256:sha(prompt.text),promptBytes:bytes})
      const before = performance.now()
      const attempted = yield* runPinnedChat(config,prompt.text).pipe(
        Effect.provideService(ResearchPinnedChatHttp,http),
        Effect.provideService(ResearchPinnedChatCredentialSource,{resolve:name=>Effect.sync(()=>process.env[name])}),
        Effect.either
      )
      if(Either.isLeft(attempted)){
        const failure={arm,phase,task,promptBytes:bytes,wallSeconds:(performance.now()-before)/1000,errorCode:attempted.left.code,usage:{status:"UNAVAILABLE",promptTokens:null,completionTokens:null,totalTokens:null}}
        yield* Ref.update(costs,c=>[...c,failure])
        yield* event("MODEL_CALL_FAILED",failure)
        return yield* Effect.fail(attempted.left)
      }
      const response=attempted.right
      const usage=response.usage
      yield* Ref.update(calls,c=>({...c,completed:c.completed+1,promptTokens:c.promptTokens+(usage.promptTokens??0),completionTokens:c.completionTokens+(usage.completionTokens??0),totalTokens:c.totalTokens+(usage.totalTokens??0),unknownUsage:c.unknownUsage+(usage.status==="REPORTED"?0:1)}))
      const cost={arm,phase,task,promptBytes:bytes,wallSeconds:(performance.now()-before)/1000,usage}
      yield* Ref.update(costs,c=>[...c,cost])
      yield* event("MODEL_CALL_OBSERVED",{arm,phase,task,...response,cost,claim:"PROVIDER_OBSERVATION_NOT_OUTCOME"})
      return response.content
    })
    const lessonPrompt = yield* unwrap(buildTextLessonConsolidationPrompt(training))
    const lesson = parseLessonResponse(yield* call("CONSOLIDATED_TEXT_LESSON","consolidation","A",lessonPrompt))
    const programPrompt = yield* unwrap(buildExecutableProgramConsolidationPrompt(training,primitives))
    const program = parseProgramResponse(yield* call("EXECUTABLE_PROGRAM_LIBRARY","consolidation","A",programPrompt))
    const memories={lesson:Either.isRight(lesson)?lesson.right:null,program:Either.isRight(program)?program.right:null}
    const memoryBytes=JSON.stringify(memories)
    yield* io(()=>writeFile(output+".memories.json",memoryBytes,{flag:"wx",mode:0o600}))
    yield* assert((yield* io(()=>readFile(output+".memories.json","utf8")))===memoryBytes,"MEMORY_RELOAD_MISMATCH")
    yield* event("MEMORY_FROZEN",{sha256:sha(memoryBytes),lessonValid:Either.isRight(lesson),programValid:Either.isRight(program),canonicalAdmission:"NOT_REQUESTED",causalCredit:"NOT_IDENTIFIED"})
    // Inference uses reloaded frozen bytes, not an unstored conversational state.
    const frozen = JSON.parse(yield* io(()=>readFile(output+".memories.json","utf8"))) as {lesson:string|null,program:CalibrationProgram|null}
    const results: Array<Prediction & {correct:boolean;expected:ReadonlyArray<string>}> = []
    for(const [index,target] of targets.entries()){
      const predictions:Prediction[]=[]
      const order=[...arms.slice(index%3),...arms.slice(0,index%3)]
      for(const arm of order){
        const prompt = arm==="ALL_TRAINING_HISTORY" ? buildOpenBookPrompt(training,target) : arm==="CONSOLIDATED_TEXT_LESSON" ? (frozen.lesson===null?null:buildTextLessonInferencePrompt(frozen.lesson,target)) : (frozen.program===null?null:buildProgramInferencePrompt(frozen.program,target))
        let prediction:Prediction={arm,task:target.id,uids:[],invalid:true,programSteps:0}
        if(prompt!==null){
          const content = yield* call(arm,"inference",target.id,yield* unwrap(prompt))
          const parsed = parseInferenceResponse(content)
          if(Either.isRight(parsed)){
            if("uids" in parsed.right) prediction={...prediction,uids:parsed.right.uids,invalid:false}
            else {
              const evaluated=evaluateIndependentProgram(target.graph,target.focus,parsed.right.program,4096)
              if(Either.isRight(evaluated)) prediction={...prediction,uids:evaluated.right.uids,invalid:false,programSteps:evaluated.right.nodeSteps}
            }
          }
        }
        yield* event("PREDICTION_SEALED",prediction)
        predictions.push(prediction)
      }
      const expected=calibrationTasks[index]!.expected
      const scores=predictions.map(p=>({...p,expected,correct:!p.invalid&&JSON.stringify([...p.uids].sort())===JSON.stringify([...expected].sort())}))
      yield* event("OUTCOME_OBSERVED_AFTER_PREDICTIONS",{task:target.id,scores,source:"AUTHORED_CATALOG_TABLE_JOIN_NOT_INDEPENDENT_CUSTODY"})
      results.push(...scores)
    }
    const summary=arms.map(arm=>({arm,correct:results.filter(r=>r.arm===arm&&r.correct).length,total:targets.length,invalid:results.filter(r=>r.arm===arm&&r.invalid).length}))
    const decision=summary.some(r=>r.correct===r.total)?"SATURATED_FOR_INCREMENTAL_SUCCESS_TEST":summary.every(r=>r.correct===0)?"FLOOR_OR_INVALID":"PARTIAL_HEADROOM_REQUIRES_NEW_INDEPENDENT_FAMILY"
    return {status:fixtureMode?"COMPLETED_TRANSPORT_FIXTURE_NO_LLM":"COMPLETED_EXPLORATORY_BASELINE_CALIBRATION",claim:fixtureMode?"ENGINEERING_FIXTURE_NOT_MODEL_OR_SCIENTIFIC_RESULT":"NO_HSWM_EFFICACY_ESTIMATE",summary,decision:fixtureMode?"NOT_APPLICABLE_TRANSPORT_FIXTURE":decision,results,scientificStatus:protocol.scientific_status}
  })
  const result = yield* run.pipe(Effect.catchAll(error=>Effect.succeed({status:"INSTRUMENT_ERROR",errorCode:error instanceof Error && /^[A-Z0-9_:./-]+$/.test(error.message)?error.message:("code" in error?String(error.code):"RESEARCH_RUN_FAILED"),claim:"NO_EFFICACY_VERDICT"})))
  // Always rehash, including a failed dispatched request. Keep both failures if
  // source drift and an independent provider/instrument error coincide.
  const boundSources=yield* Ref.get(sourceBindings)
  const sourceIntegrity=yield* Effect.forEach(boundSources,binding=>Effect.gen(function*(){
    const bytes=yield* io(()=>readFile(resolve(root,binding.path)))
    return {path:binding.path,matches:sha(bytes)===binding.sha256}
  })).pipe(Effect.either)
  const sourceValid=boundSources.length>0 && Either.isRight(sourceIntegrity) && sourceIntegrity.right.every(row=>row.matches)
  const count=yield* Ref.get(calls)
  const terminal={...result,...(sourceValid?{}:{status:"INSTRUMENT_ERROR",precedingStatus:result.status,sourceError:"SOURCE_DRIFT_OR_UNREADABLE",claim:"NO_EFFICACY_VERDICT"}),sourceIntegrity:sourceValid?"ALL_BOUND_HSWM_SOURCES_MATCH":"FAILED_OR_NOT_SEALED",accounting:{...count,issuedWithoutValidatedCompletion:count.issued-count.completed,unknownUsageIssuedCalls:count.unknownUsage+count.issued-count.completed,tokenTotalsSemantics:"SUM_OF_KNOWN_USAGE_ONLY_UNKNOWN_IS_NOT_ZERO",humanMinutes:null,monetaryCost:null,perCall:yield* Ref.get(costs)}}
  yield* event("TERMINAL",terminal)
  const final={...terminal,journalHead:yield* Ref.get(chain),wallSeconds:(performance.now()-started)/1000}
  yield* io(()=>writeFile(output,JSON.stringify(final,null,2)+"\n"))
  return final
})

Effect.runPromise(main).then(result=>{
  process.stdout.write(JSON.stringify({status:result.status,output:argument("--output")})+"\n")
  if(result.status==="INSTRUMENT_ERROR") process.exitCode=1
}).catch(()=>{process.stderr.write("RESEARCH_START_FAILED\n");process.exitCode=1})
