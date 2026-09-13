import { readFileSync } from "node:fs"
import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { nativeAssessOccurrenceIntegrity } from "../src/native-occurrence-integrity-domain.js"
import { nativeAssessDualEvaluation } from "../src/native-occurrence-dual-evaluator-domain.js"
import { advanceNativeOccurrence, registeredNativeOccurrence } from "../src/native-occurrence-workflow-domain.js"
import { completeNativeOccurrence, completeNativeOccurrenceWithAudit, nativeCompletionReceiptCanonical, type NativeOccurrenceCompletionInput } from "../src/native-occurrence-completion-domain.js"
import type { TaskJson } from "../src/native-task-json-domain.js"

const unwrap = <A,E>(value: Either.Either<A,E>): A => { if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left)); return value.right }
const json = (name:string):unknown => JSON.parse(readFileSync(new URL(`../../../../tests/fixtures/native_migration/${name}`,import.meta.url),"utf8"))
const integrity = json("occurrence_integrity_v1/original_python.json") as { positive:{input:Record<string,TaskJson>} }
const oracle = json("occurrence_completion_v1/original_python_candidate.json") as {input:{started_at:string;terminal_at:string;judgment_a:Record<string,TaskJson>;judgment_b:Record<string,TaskJson>};expected:{receipt:TaskJson}}
const raw = (value:Record<string,TaskJson>):TaskJson => {const {schema:_schema,...result}=value;return result}
export const completionTestBase = ():NativeOccurrenceCompletionInput => {
  const assessment=unwrap(nativeAssessOccurrenceIntegrity(integrity.positive.input))
  const judgmentA=raw(oracle.input.judgment_a),judgmentB=raw(oracle.input.judgment_b)
  const dualEvaluation=unwrap(nativeAssessDualEvaluation(judgmentA,judgmentB))
  return {assessment,workflow:completionTestWorkflow(assessment.workflowEvidenceSha256s),dualEvaluation,judgmentA,judgmentB,startedAt:oracle.input.started_at,terminalAt:oracle.input.terminal_at}
}
export const completionTestWorkflow=(evidence:readonly string[])=>{
 let state=unwrap(registeredNativeOccurrence("g0-occurrence-1",evidence[0]!))
 for(const [phase,index] of [["CLAIMED",1],["SCHEDULED",2],["PRE_PULSE_SEALED",3],["PULSE_VERIFIED",4],["REVEALED",5],["DUAL_EVALUATED",6]] as const)state=unwrap(advanceNativeOccurrence(state,phase,evidence[index]!,index<=3?"PRE_PULSE":"POST_PULSE"))
 return state
}
const cases=json("occurrence_completion_v1/decisions.original.v1.json") as {cases:readonly {name:string;outcome:string;receipt?:TaskJson;message?:string}[]}
const inputFor=(name:string):NativeOccurrenceCompletionInput=>{
 const base=completionTestBase(),candidate=unwrap(completeNativeOccurrence(base))
 const terminal=unwrap(advanceNativeOccurrence(base.workflow,"SEALED",candidate.receiptSha256,"POST_PULSE"))
 const registered=unwrap(registeredNativeOccurrence("g0-occurrence-1",base.assessment.workflowEvidenceSha256s[0]!))
 const fakeHistory=completionTestWorkflow(Array.from({length:7},(_,i)=>(i+1).toString(16).padStart(64,"0")))
 const voided=unwrap(advanceNativeOccurrence(unwrap(registeredNativeOccurrence("g0-occurrence-1","1".padStart(64,"0"))),"REVEALED","f".repeat(64),"POST_PULSE"))
 const voidInput={...base,workflow:voided},voidReceipt=unwrap(completeNativeOccurrence(voidInput))
 const variants:Readonly<Record<string,Partial<NativeOccurrenceCompletionInput>>>={
  candidate:{},"dual-absent":{dualEvaluation:null},"judgments-absent":{judgmentA:null,judgmentB:null},"judgment-a-absent":{judgmentA:null},
  "dual-blocked":{dualEvaluation:unwrap(nativeAssessDualEvaluation(null,null))},registered:{workflow:registered},"wrong-history":{workflow:fakeHistory},"workflow-void":{workflow:voided},
  "central-blocked":{assessment:unwrap(nativeAssessOccurrenceIntegrity(Object.fromEntries(Object.keys(integrity.positive.input).map(key=>[key,key==="duplicate_seen"||key==="retry_seen"?false:null]))))},
  "early-finalization":{candidateReceipt:candidate},"terminal-no-candidate":{workflow:terminal},
  "terminal-wrong-candidate-extension":{workflow:unwrap(advanceNativeOccurrence(base.workflow,"SEALED","8".repeat(64),"POST_PULSE")),candidateReceipt:candidate},
  "terminal-no-audit":{workflow:terminal,candidateReceipt:candidate},"terminal-before-candidate":{workflow:terminal,candidateReceipt:candidate,terminalAt:"2026-09-03T00:00:59.999999Z"},
  "pending-as-previous":{previousReceipt:candidate},"invalid-calendar":{terminalAt:"2026-02-30T00:01:00Z"},"invalid-no-offset":{terminalAt:"2026-09-03T00:01:00"},
  "micro-before-start":{startedAt:"2026-09-03T00:01:00.000001Z"},"iso-week-offset":{terminalAt:"2026-W36-4T02:00:00+02:00"},
  "void-idempotent":{workflow:voided,previousReceipt:voidReceipt},"void-stale-time":{workflow:voided,previousReceipt:voidReceipt,terminalAt:"2026-09-03T00:02:00Z"}
 }
 if(!Object.hasOwn(variants,name))throw new Error(`unhandled fixture ${name}`)
 return {...base,...variants[name]}
}
for(const row of cases.cases)it(`matches complete original completion result: ${row.name}`,()=>{
 const result=completeNativeOccurrence(inputFor(row.name))
 if(row.outcome==="ERROR")expect(Either.isLeft(result)).toBe(true)
 else expect(unwrap(nativeCompletionReceiptCanonical(unwrap(result)))).toEqual(row.receipt)
})
it("matches original pending receipt with no final-audit claim",()=>{const candidate=unwrap(completeNativeOccurrence(completionTestBase()));expect(unwrap(nativeCompletionReceiptCanonical(candidate))).toEqual(oracle.expected.receipt)})
it("rejects copied assessments, copied workflows and copied receipts without treating shapes as authority",()=>{
 const input=completionTestBase(),candidate=unwrap(completeNativeOccurrence(input))
 expect(Either.isLeft(completeNativeOccurrence({...input,assessment:{...input.assessment}}))).toBe(true)
 expect(Either.isLeft(completeNativeOccurrence({...input,workflow:{...input.workflow}}))).toBe(true)
 expect(Either.isLeft(nativeCompletionReceiptCanonical({...candidate}))).toBe(true)
})
it("reruns audit and refuses a structural fake, preserving the original BLOCKED result",async()=>{
 const base=completionTestBase(),candidate=unwrap(completeNativeOccurrence(base)),workflow=unwrap(advanceNativeOccurrence(base.workflow,"SEALED",candidate.receiptSha256,"POST_PULSE"))
 let calls=0
 const result=await Effect.runPromise(completeNativeOccurrenceWithAudit({...base,workflow,candidateReceipt:candidate,externalAuditMaterial:{fake:true}}, {verify:()=>{calls+=1;return Effect.succeed({verificationSha256:"a".repeat(64)} as never)}}))
 expect(calls).toBe(1);expect(result.terminalStatus).toBe("BLOCKED");expect(result.externalAuditVerificationSha256).toBe(null)
})
