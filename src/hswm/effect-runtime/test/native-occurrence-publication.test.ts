import { readFileSync } from "node:fs"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { completeNativeOccurrence, nativeCompletionReceiptCanonical, nativeCompletionReceiptPayload } from "../src/native-occurrence-completion-domain.js"
import { nativeAssessOccurrenceIntegrity } from "../src/native-occurrence-integrity-domain.js"
import { nativeAssessDualEvaluation } from "../src/native-occurrence-dual-evaluator-domain.js"
import { advanceNativeOccurrence, registeredNativeOccurrence } from "../src/native-occurrence-workflow-domain.js"
import { projectNativeIssuedOccurrencePublication, validateNativeOccurrenceArtifact, type NativeOccurrenceArtifact } from "../src/native-occurrence-publication.js"
import { renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js"
const unwrap=<A,E>(value:Either.Either<A,E>):A=>{if(Either.isLeft(value))throw new Error(JSON.stringify(value.left));return value.right}
const read=(path:string):unknown=>JSON.parse(readFileSync(new URL(`../../../../tests/fixtures/native_migration/${path}`,import.meta.url),"utf8"))
const integrity=read("occurrence_integrity_v1/original_python.json") as {positive:{input:TaskJson}}
const candidate=read("occurrence_completion_v1/original_python_candidate.json") as {input:{judgment_a:Record<string,TaskJson>;judgment_b:Record<string,TaskJson>;started_at:string;terminal_at:string}}
const original=read("occurrence_completion_v1/void-publication.original.v1.json") as {receipt:TaskJson;cases:readonly {name:string;producer:string;artifacts:readonly NativeOccurrenceArtifact[];ro_crate:unknown;openlineage:readonly unknown[]}[]}
const raw=(v:Record<string,TaskJson>)=>{const {schema:_schema,...value}=v;return value}
const issuedVoid=()=>{
 const judgmentA=raw(candidate.input.judgment_a),judgmentB=raw(candidate.input.judgment_b)
 const registered=unwrap(registeredNativeOccurrence("g0-occurrence-1","1".padStart(64,"0")))
 return unwrap(completeNativeOccurrence({assessment:unwrap(nativeAssessOccurrenceIntegrity(integrity.positive.input)),workflow:unwrap(advanceNativeOccurrence(registered,"REVEALED","f".repeat(64),"POST_PULSE")),dualEvaluation:unwrap(nativeAssessDualEvaluation(judgmentA,judgmentB)),judgmentA,judgmentB,startedAt:candidate.input.started_at,terminalAt:candidate.input.terminal_at}))
}
for(const row of original.cases)it(`matches full original VOID RO-Crate and OpenLineage: ${row.name}`,()=>{
 const receipt=issuedVoid();expect(unwrap(nativeCompletionReceiptCanonical(receipt))).toEqual(original.receipt)
 const result=unwrap(projectNativeIssuedOccurrencePublication(receipt,null,row.artifacts,row.producer))
 expect(result.roCrate).toEqual(row.ro_crate);expect([result.openLineage.start,result.openLineage.terminal]).toEqual(row.openlineage)
})
it("does not export a forgeable receipt constructor or arbitrary public issuer",async()=>{
 const module=await import("../src/native-occurrence-publication.js")
 expect("NativeGuardedCompletionReceipt" in module).toBe(false);expect("issueNativeGuardedCompletionReceipt" in module).toBe(false)
 const receipt=issuedVoid();expect(Either.isLeft(projectNativeIssuedOccurrencePublication({...receipt},null,original.cases[0]!.artifacts))).toBe(true)
})
it("requires the exact self-hash-free payload bytes, media type and role once each",()=>{
 const receipt=issuedVoid(),artifacts=original.cases[0]!.artifacts
 expect(new TextEncoder().encode(renderNativeTaskJson(unwrap(nativeCompletionReceiptPayload(receipt)))).byteLength).toBe(artifacts[0]!.bytes)
 for(const changed of [{...artifacts[0]!,bytes:1},{...artifacts[0]!,role:"wrong"},{...artifacts[0]!,media_type:"text/plain"}])expect(Either.isLeft(projectNativeIssuedOccurrencePublication(receipt,null,[changed]))).toBe(true)
 expect(Either.isLeft(projectNativeIssuedOccurrencePublication(receipt,null,[...artifacts,{...artifacts[0]!,path:"duplicate.json"}]))).toBe(true)
 for(const path of ["../secret","/absolute","a/../b","a\\b","a//b"] )expect(Either.isLeft(validateNativeOccurrenceArtifact({...artifacts[0]!,path}))).toBe(true)
})
