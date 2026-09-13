import { readFileSync } from "node:fs"
import { createHash } from "node:crypto"
import { Either } from "effect"
import { expect, it } from "vitest"
import { decodeNativeTaskJson, renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js"
import { nativeProm9PortDigest, nativeProm9OutputSchema, nativeProm9OutputSchemaSha256, validateNativeProm9Port, type Prom9PortType } from "../src/native-prom9-ports-domain.js"
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_ports_v1/original.v1.json", import.meta.url), "utf8")) as {source_sha256: string; cases: readonly {name: string; port: Prom9PortType; input_json: string; accepted: boolean; canonical?: string; digest?: string}[]; schemas: Readonly<Record<string, {value: TaskJson; sha256: string}>>}
it("matches every original port acceptance/refusal, normalized value and digest", () => {
 expect(createHash("sha256").update(readFileSync(new URL("../../../../prom_search_hswm/hswm_typed_ports.py", import.meta.url))).digest("hex")).toBe(fixture.source_sha256)
 expect(fixture.cases).toHaveLength(343)
 for(const row of fixture.cases){
  const input=Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(row.input_json),{maximumBytes:2_000_000})),result=validateNativeProm9Port(row.port,input)
  expect(Either.isRight(result),row.name).toBe(row.accepted)
  if(Either.isRight(result)){expect(renderNativeTaskJson(result.right),row.name).toBe(row.canonical);expect(nativeProm9PortDigest(row.port,input),row.name).toMatchObject({_tag:"Right",right:row.digest})}
 }
})
it("reproduces every structured-output schema and digest",()=>{
 for(const [port, expected]of Object.entries(fixture.schemas)){
  expect(nativeProm9OutputSchema(port)).toMatchObject({_tag:"Right",right:expected.value})
  expect(nativeProm9OutputSchemaSha256(port)).toMatchObject({_tag:"Right",right:expected.sha256})
 }
 expect(nativeProm9OutputSchema("__proto__")).toMatchObject({_tag:"Left"})
})
it("refuses sparse/nonfinite JS values and releases immutable independent results",()=>{
 const valid={request_id:"r",ordered_bond_ids:["b"],bond_potentials:{b:0},evidence_refs:["e"],abstain:false}
 for(const value of [{...valid,extra:true},{...valid,abstain:0},{...valid,ordered_bond_ids:["b","b"]},{...valid,ordered_bond_ids:Object.assign(["b"],{2:"x",length:3})},{...valid,bond_potentials:{b:NaN}},{...valid,bond_potentials:{b:true}}])expect(validateNativeProm9Port("BondProposalV1",value)).toMatchObject({_tag:"Left"})
 const output=Either.getOrThrow(validateNativeProm9Port("BondProposalV1",valid));valid.ordered_bond_ids.push("mutated");expect(output["ordered_bond_ids"]).toEqual(["b"]);expect(Object.isFrozen(output)).toBe(true)
 expect(nativeProm9PortDigest("BondProposalV1",{...valid,ordered_bond_ids:["b"],request_id:"\ud800"})).toMatchObject({_tag:"Left"})
})
