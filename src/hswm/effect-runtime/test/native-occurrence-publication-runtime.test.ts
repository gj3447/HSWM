import { Effect, Either } from "effect"
import { expect, it } from "@effect/vitest"
import { completeNativeOccurrenceRuntime } from "../src/native-occurrence-completion-runtime.js"
import { publishNativeOccurrenceProjection } from "../src/native-occurrence-publication-runtime.js"
import { validateNativeOccurrenceArtifact } from "../src/native-occurrence-publication.js"
import { qualifiedAuditFixture, qualifiedAuditServices, qualifiedAuditServicesWith, sealedCompletionInput } from "./fixtures/native-occurrence-audit.js"
const artifacts=(()=>{
 const values=qualifiedAuditFixture["artifacts"]
 if(!Array.isArray(values))throw new Error("artifact fixture required")
 return values.map((value:unknown)=>{const result=validateNativeOccurrenceArtifact(value);if(Either.isLeft(result))throw new Error(result.left.detail);return result.right})
})()
it.effect("fresh completion and second audit reproduce the full original SEALED RO-Crate and OpenLineage",()=>Effect.gen(function*(){
 const replay=sealedCompletionInput(),receipt=yield* completeNativeOccurrenceRuntime(replay)
 const result=yield* publishNativeOccurrenceProjection(receipt,replay,artifacts)
 expect(result.roCrate).toEqual(qualifiedAuditFixture["ro_crate"])
 expect([result.openLineage.start,result.openLineage.terminal]).toEqual(qualifiedAuditFixture["openlineage"])
}).pipe(Effect.provide(qualifiedAuditServices)))
it.effect("publication rejects previously valid receipts when fresh audit material changes",()=>Effect.gen(function*(){
 const replay=sealedCompletionInput(),receipt=yield* completeNativeOccurrenceRuntime(replay).pipe(Effect.provide(qualifiedAuditServices))
 const changed=qualifiedAuditServicesWith({bytesForRead:(path,_count,original)=>path.endsWith("audit-manifest.json")?new TextEncoder().encode("{}"):original})
 const result=yield* Effect.either(publishNativeOccurrenceProjection(receipt,replay,artifacts).pipe(Effect.provide(changed)))
 expect(Either.isLeft(result)).toBe(true)
}))
it.effect("the independent second audit observes later material drift after successful completion replay",()=>Effect.gen(function*(){
 const replay=sealedCompletionInput(),receipt=yield* completeNativeOccurrenceRuntime(replay).pipe(Effect.provide(qualifiedAuditServices))
 let manifestReads=0
 const changed=qualifiedAuditServicesWith({bytesForRead:(path,_count,original)=>{if(path.endsWith("audit-manifest.json")){manifestReads+=1;if(manifestReads>1)return new TextEncoder().encode("{}")}return original}})
 const result=yield* Effect.either(publishNativeOccurrenceProjection(receipt,replay,artifacts).pipe(Effect.provide(changed)))
 expect(Either.isLeft(result)).toBe(true);expect(manifestReads).toBeGreaterThan(1)
}))
