import { createHash } from "node:crypto"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "../src/native-task-json-domain.js"
import { verifyNativeGraphStandardsLock } from "../src/native-graph-standards-domain.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { verifyNativeGraphStandardsCheckout } from "../src/native-graph-standards-runtime.js"

const root=resolve(fileURLToPath(new URL("../../../..",import.meta.url)))
const bytes=(path:string):Uint8Array=>new Uint8Array(readFileSync(path))
const inventory=():Readonly<Record<string,Uint8Array>>=>{const out:Record<string,Uint8Array>={};const visit=(path:string):void=>{for(const name of readdirSync(path)){const child=resolve(path,name),st=statSync(child);if(st.isDirectory())visit(child);else if(st.isFile())out[relative(root,child)]=bytes(child)}};for(const path of ["_research/graph_standards","src/hswm","schemas"]){const full=resolve(root,path);if(statSync(full).isDirectory())visit(full);else out[path]=bytes(full)}return out}
const lock=():TaskJson=>{const parsed=decodeNativeTaskJson(bytes(resolve(root,"_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json")));if(Either.isLeft(parsed))throw new Error("lock fixture malformed");return parsed.right}
describe("native graph standards lock",()=>{
  it("accepts the complete checked-in source-bound lock",()=>expect(Either.isRight(verifyNativeGraphStandardsLock(lock(),inventory()))).toBe(true))
  it("refuses a stable-lane draft standard",()=>{const value=JSON.parse(JSON.stringify(lock())) as {standards:{id:string;lane:string}[]};value.standards.find(x=>x.id==="rdf-1.2-n-quads")!.lane="stable";const result=verifyNativeGraphStandardsLock(value as unknown as TaskJson,inventory());expect(Either.isLeft(result)).toBe(true);if(Either.isLeft(result))expect(result.left.detail).toContain("draft standard")})
  it("refuses an untrusted MCP registry",()=>{const value=JSON.parse(JSON.stringify(lock())) as {mcp:{registry:{auto_install:boolean}}};value.mcp.registry.auto_install=true;const result=verifyNativeGraphStandardsLock(value as unknown as TaskJson,inventory());expect(Either.isLeft(result)).toBe(true);if(Either.isLeft(result))expect(result.left.detail).toBe("MCP Registry boundary drift")})
  it("refuses a rehashed receipt whose source binding differs from its locked suite",()=>{const value=JSON.parse(JSON.stringify(lock())) as {qualification_receipts:{path:string;receipt_sha256:string}[]};const files={...inventory()},record=value.qualification_receipts[0]!,decoded=decodeNativeTaskJson(files[record.path]!);if(Either.isLeft(decoded)||!taskJsonRecord(decoded.right))throw new Error("receipt fixture malformed");const changed={...decoded.right,source:{...(decoded.right["source"] as object),commit:"0000000000000000000000000000000000000000"}} as Record<string,TaskJson>;delete changed["receipt_sha256"];const digest=createHash("sha256").update(renderNativeTaskJson(changed)).digest("hex");files[record.path]=new TextEncoder().encode(renderNativeTaskJson({...changed,receipt_sha256:digest}));record.receipt_sha256=digest;const result=verifyNativeGraphStandardsLock(value as unknown as TaskJson,files);expect(Either.isLeft(result)).toBe(true);if(Either.isLeft(result))expect(result.left.detail).toContain("qualification receipt boundary drift")})
  it("verifies the lock through bounded filesystem I/O from an explicit checkout root",async()=>{const result=await Effect.runPromise(verifyNativeGraphStandardsCheckout(root,resolve(root,"_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json")).pipe(Effect.provide(NodePosixFileSystemLive)));expect(result).toMatchObject({status:"PASS",suite_sources:6,runnable_profiles:6})})
})
