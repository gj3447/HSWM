import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { HSWM_HANDOFF_BINDINGS, HSWM_HANDOFF_BOUNDARY, HSWM_HANDOFF_RETURNS, HSWM_HANDOFF_ROLES, HSWM_HANDOFF_SCHEMA, HSWM_HANDOFF_STATUS, nativeHandoffTemplate, validateNativeHandoff } from "../src/native-occurrence-handoff-domain.js"
const candidates=Uint8Array.from(readFileSync(resolve(import.meta.dirname,"../../../../_research/g0_occurrence/HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json")))
const bytes=(v:unknown):Uint8Array=>{const encoded=canonicalJsonBytes(v);if(Either.isLeft(encoded))throw new Error("fixture canonicalization");return encoded.right}
it("matches the full Python template payload and its structural validation report",()=>{
 const template=nativeHandoffTemplate("occ-1",candidates);expect(Either.isRight(template)).toBe(true);if(Either.isLeft(template))return
 const payload=JSON.parse(new TextDecoder().decode(template.right)) as Record<string,unknown>
 expect(payload).toMatchObject({claim_boundary:HSWM_HANDOFF_BOUNDARY,occurrence_uid:"occ-1",schema_version:HSWM_HANDOFF_SCHEMA,status:HSWM_HANDOFF_STATUS,operator_return_checklist:[...HSWM_HANDOFF_RETURNS]})
 expect(Object.keys(payload["role_binding_descriptors"] as object).sort()).toEqual([...HSWM_HANDOFF_ROLES].sort());expect(Object.keys(payload["external_binding_descriptors"] as object).sort()).toEqual([...HSWM_HANDOFF_BINDINGS].sort());expect(Object.keys(payload["operator_return_descriptors"] as object).sort()).toEqual([...HSWM_HANDOFF_RETURNS].sort())
 const report=validateNativeHandoff(template.right,candidates);expect(Either.isRight(report)).toBe(true);if(Either.isRight(report))expect(report.right).toMatchObject({status:"BLOCKED_EXTERNAL",schema_structure_valid:true,descriptor_graph_complete:false,external_independence_proven:false,g0_passed:false,live_execution_ready:false,missing_descriptor_slots:expect.any(Array)})
})
it("refuses extra fields, stale candidate binding, noncanonical bytes, bad slots and descriptors",()=>{
 const template=nativeHandoffTemplate("occ-1",candidates);if(Either.isLeft(template))throw new Error("template failed");const base=JSON.parse(new TextDecoder().decode(template.right)) as Record<string,any>
 expect(Either.isLeft(validateNativeHandoff(bytes({...base,extra:true}),candidates))).toBe(true)
 expect(Either.isLeft(validateNativeHandoff(template.right,Uint8Array.from([...candidates,0])))).toBe(true)
 expect(Either.isLeft(validateNativeHandoff(new TextEncoder().encode(`${JSON.stringify(base)} `),candidates))).toBe(true)
 expect(Either.isLeft(validateNativeHandoff(bytes({...base,operator_return_checklist:[]}),candidates))).toBe(true)
 expect(Either.isLeft(validateNativeHandoff(bytes({...base,role_binding_descriptors:{...base["role_binding_descriptors"],actor:{media_type:"x",byte_length:-1,sha256:"a".repeat(64)}}}),candidates))).toBe(true)
 expect(Either.isLeft(validateNativeHandoff(bytes({...base,external_binding_descriptors:{...base["external_binding_descriptors"],unexpected:null}}),candidates))).toBe(true)
})
