import { resolve } from "node:path"
import { createHash } from "node:crypto"
import { cpSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { verifyNativeEfficacyCheckout } from "../src/native-efficacy-runtime.js"
import { taskJsonRecord } from "../src/native-task-json-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson } from "../src/native-task-json-domain.js"

const checkout=resolve(import.meta.dirname,"../../../..")
const fixture=():string=>{
  const root=mkdtempSync(resolve(tmpdir(),"hswm-native-efficacy-"))
  for(const path of ["results/raw","evidence","prereg","receipts","_research/root_compat"])cpSync(resolve(checkout,path),resolve(root,path),{recursive:true})
  return root
}
const result=async(root:string)=>Effect.runPromise(verifyNativeEfficacyCheckout(root).pipe(Effect.provide(NodePosixFileSystemLive),Effect.either))
const withFixture=async(action:(root:string)=>Promise<void>):Promise<void>=>{const root=fixture();try{await action(root)}finally{rmSync(root,{recursive:true,force:true})}}
const replace=(path:string,from:string,to:string):void=>writeFileSync(path,readFileSync(path,"utf8").replace(from,to),"utf8")
describe("native efficacy verifier",()=>{
  it("projects the checked-in selected-claim ledger without executing Python",async()=>{
    const outcome=await Effect.runPromise(verifyNativeEfficacyCheckout(checkout).pipe(Effect.provide(NodePosixFileSystemLive),Effect.either))
    if(Either.isLeft(outcome))throw new Error(outcome.left.detail)
    const snapshot=outcome.right
    expect(taskJsonRecord(snapshot)).toBe(true)
    if(!taskJsonRecord(snapshot))throw new Error("unreachable")
    expect(snapshot["schema_version"]).toBe("hswm-efficacy-snapshot/v4")
    expect(createHash("sha256").update(`${renderNativeTaskJson(snapshot)}\n`).digest("hex")).toBe("5e7c0f93be9b1e4d06f5c9a5bf813578fff58b1c0af1b4933cadc1e41c72c0be")
    expect(taskJsonRecord(snapshot["p1_closed_macro_weight_loop"] ?? null)).toBe(true)
    expect(taskJsonRecord(snapshot["query_time_traversal"] ?? null)).toBe(true)
  })
  it("refuses a source-bound semantic input that drifts after its receipt was sealed",async()=>withFixture(async root=>{
    const path=resolve(root,"_research/root_compat/semantic_layer_routing.py")
    writeFileSync(path,`${readFileSync(path,"utf8")}\n# hostile drift\n`,"utf8")
    const outcome=await result(root)
    expect(Either.isLeft(outcome)).toBe(true)
    if(Either.isLeft(outcome))expect(outcome.left.detail).toBe("semantic-layer synthetic source binding drifted for semantic_layer_routing.py")
  }))
  it("refuses a resealed-looking receipt when its declared source binding changes",async()=>withFixture(async root=>{
    const path=resolve(root,"results/raw/semantic_layer_result.json")
    const decoded=decodeNativeTaskJson(new Uint8Array(readFileSync(path)))
    if(Either.isLeft(decoded)||!taskJsonRecord(decoded.right))throw new Error("fixture must decode")
    const bindings = decoded.right["source_bindings"]
    if(bindings===undefined||!taskJsonRecord(bindings))throw new Error("fixture source bindings must be an object")
    const changed={...decoded.right,source_bindings:{...bindings,"semantic_layer_routing.py":"0000000000000000000000000000000000000000000000000000000000000000"}}
    const unsigned=Object.fromEntries(Object.entries(changed).filter(([key])=>key!=="result_sha256"))
    writeFileSync(path,renderNativeTaskJson({...unsigned,result_sha256:createHash("sha256").update(renderNativeTaskJson(unsigned)).digest("hex")}),"utf8")
    const outcome=await result(root)
    expect(Either.isLeft(outcome)).toBe(true)
    if(Either.isLeft(outcome))expect(outcome.left.detail).toBe("semantic-layer synthetic source binding drifted for semantic_layer_routing.py")
  }))
  it("refuses headline metric drift",async()=>withFixture(async root=>{
    replace(resolve(root,"results/raw/substrate_bench_results.json"),"\"ndcg10\": 0.8388","\"ndcg10\": 0.8387")
    const outcome=await result(root)
    expect(Either.isLeft(outcome)).toBe(true)
    if(Either.isLeft(outcome))expect(outcome.left.detail).toContain("HSWM nDCG@10 drifted")
  }))
  it("refuses duplicate JSON keys before a ledger can be interpreted",async()=>withFixture(async root=>{
    writeFileSync(resolve(root,"results/raw/qkv_routing_result.json"),"{\"status\":\"PASS\",\"status\":\"FAIL\"}","utf8")
    const outcome=await result(root)
    expect(Either.isLeft(outcome)).toBe(true)
    if(Either.isLeft(outcome))expect(outcome.left.detail).toBe("qkv_routing_result.json must contain a JSON object")
  }))
  it("refuses ambiguous artifact layouts",async()=>withFixture(async root=>{
    cpSync(resolve(root,"results/raw/qkv_routing_result.json"),resolve(root,"_research/root_compat/qkv_routing_result.json"))
    const outcome=await result(root)
    expect(Either.isLeft(outcome)).toBe(true)
    if(Either.isLeft(outcome))expect(outcome.left.detail).toBe("ambiguous artifact layout for qkv_routing_result.json")
  }))
  it("uses the root-compat fallback only when the typed artifact is absent",async()=>withFixture(async root=>{
    const typed=resolve(root,"results/raw/qkv_routing_result.json"),fallback=resolve(root,"_research/root_compat/qkv_routing_result.json")
    cpSync(typed,fallback);unlinkSync(typed)
    const outcome=await result(root)
    expect(Either.isRight(outcome)).toBe(true)
  }))
  it("refuses a missing artifact after every sanctioned fallback is absent",async()=>withFixture(async root=>{
    unlinkSync(resolve(root,"results/raw/qkv_routing_result.json"))
    const outcome=await result(root)
    expect(Either.isLeft(outcome)).toBe(true)
    if(Either.isLeft(outcome))expect(outcome.left.detail).toContain("cannot read qkv_routing_result.json")
  }))
})
