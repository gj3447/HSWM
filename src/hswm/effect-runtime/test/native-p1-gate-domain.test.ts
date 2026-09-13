import { createHash } from "node:crypto"
import { DatabaseSync } from "node:sqlite"
import { readFileSync } from "node:fs"
import { mkdtemp, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { bootstrapLowerPython, decideFreshGate, P1_POSTHOC_STATUS } from "../src/native-p1-gate-domain.js"
import { decodeNativeP1Npy } from "../src/native-p1-npy-domain.js"
import { buildNativeP1Graph, nativeP1Cosine, nativeP1Walk, type NativeP1Graph } from "../src/native-p1-retrieval-domain.js"
import { nativeP1SnapshotWeightMap, parseNativeP1Snapshot } from "../src/native-p1-snapshot-domain.js"
import { decodeNativeP1GateCommand, loadNativeP1GateCandidates } from "../src/native-p1-gate-runtime.js"
import { runNativeP1GateCli } from "../src/native-p1-gate-cli.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"

const root=resolve(fileURLToPath(new URL("../../../..",import.meta.url)))
const right=<T>(value:Either.Either<T,unknown>):T=>{if(Either.isLeft(value))throw value.left;return value.right}

describe("native P1 post-hoc gate arithmetic",()=>{
 it("pins the original P1 diagnostic source and preserves the non-promoting status",()=>{
  const source=readFileSync(resolve(root,"src/hswm/diagnostics/p1_gate.py"))
  expect(createHash("sha256").update(source).digest("hex")).toBe("e4b401bdaa92eedb3cdc0792f8a2a5913c70413ec97cb6373f86f0452b6d9ac0")
  expect(P1_POSTHOC_STATUS).toBe("POSTHOC_DIAGNOSTIC_NOT_A_NEW_ARM_OUTCOME")
 })
 it("accepts the successful threshold only when the confidence lower bound is strictly positive",()=>{
  expect(right(decideFreshGate(.01,.0000001))).toMatchObject({fresh_gate_pass:true})
  expect(right(decideFreshGate(.01,0))).toMatchObject({fresh_gate_pass:false})
  expect(right(decideFreshGate(.009999999,1))).toMatchObject({fresh_gate_pass:false})
 })
 it("matches frozen Python bootstrap draws for source-compatible integer seeds",()=>{
  expect(right(bootstrapLowerPython([0,1,-.25,.5],9173n))).toBe(-.125)
  expect(right(bootstrapLowerPython([.02,.01,.03],0x0123456789abcdefn))).toBe(.01)
  expect(right(bootstrapLowerPython(Array.from({length:38},()=>0),1n))).toBe(0)
 })
})
describe("native P1 cached NumPy inputs",()=>{
 it("decodes the non-pickle C-order float64 payload used by the frozen embedding cache",()=>{
  const header="{'descr': '<f8', 'fortran_order': False, 'shape': (2,), }\n",prefix=new Uint8Array([0x93,78,85,77,80,89,1,0,header.length&255,header.length>>>8,...new TextEncoder().encode(header)]),data=new Uint8Array(16),view=new DataView(data.buffer);view.setFloat64(0,.25,true);view.setFloat64(8,-.5,true)
  const parsed=decodeNativeP1Npy(new Uint8Array([...prefix,...data]));expect(Either.isRight(parsed)).toBe(true);if(Either.isRight(parsed))expect(parsed.right).toMatchObject({dtype:"f8",shape:[2],values:[.25,-.5]})
 })
})
describe("native P1 strict retrieval replay",()=>{
 it("uses cached cosine seeds and only boosts a target through its bound weighted arc",()=>{
  const cosine=nativeP1Cosine([1,0,0,1],[1,0],2);expect(Either.isRight(cosine)).toBe(true);if(Either.isRight(cosine))expect(cosine.right).toEqual([1,0])
 const graph:NativeP1Graph={targetIds:["a","b"],arcs:[{arcId:"arc:one",join:"person:b",source:0,sourceClaim:"claim:a:0",sourcePredicate:"friend",target:1,targetClaim:"claim:b:0",targetId:"b"}]}
  const replay=nativeP1Walk([1,0],graph,[0],{"arc:one":0},"who is a friend");expect(Either.isRight(replay)).toBe(true);if(Either.isRight(replay))expect(replay.right[1]).toBeCloseTo(.1)
  const ingested=buildNativeP1Graph([{title:"Ada",article:"Ada's friend is Bea.",facts:['friend("Ada", "Bea").']},{title:"Bea",article:"Bea's friend is Ada.",facts:['friend("Bea", "Ada").']}]);expect(Either.isRight(ingested)).toBe(true);if(Either.isRight(ingested))expect(ingested.right.arcs).toHaveLength(2)
 })
})
describe("native P1 snapshot parser",()=>{
 const fixture='{"epoch":0,"parent_snapshot_id":"0000000000000000000000000000000000000000000000000000000000000000","provenance_root_sha256":"2222222222222222222222222222222222222222222222222222222222222222","schema_version":"hswm-weight-snapshot/v1","snapshot_id":"8d293d2b858dc9372ef4604c8aaa4b81d7c7af59efa88205646ade40ab7eafd1","topology_sha256":"1111111111111111111111111111111111111111111111111111111111111111","weights":[{"edge_id":"edge:a","log_salience":-0.5},{"edge_id":"edge:b","log_salience":-0.25}]}'
 it("accepts the original Python positive snapshot bytes and normalizes its readonly map",()=>{const parsed=parseNativeP1Snapshot(new TextEncoder().encode(fixture));expect(Either.isRight(parsed)).toBe(true);if(Either.isRight(parsed))expect(nativeP1SnapshotWeightMap(parsed.right)).toEqual({"edge:a":-.5,"edge:b":-.25})})
 it.each([fixture.replace('"log_salience":-0.25','"log_salience":0.1'),fixture.replace('edge:b','edge:a'),fixture.replace('8d293d2b858dc9372ef4604c8aaa4b81d7c7af59efa88205646ade40ab7eafd1','0'.repeat(64)),"[]"])("rejects malformed oracle vectors",raw=>expect(Either.isLeft(parseNativeP1Snapshot(new TextEncoder().encode(raw)))).toBe(true))
})
describe("native P1 readonly SQLite inputs",()=>{
 const snapshot='{"epoch":0,"parent_snapshot_id":"0000000000000000000000000000000000000000000000000000000000000000","provenance_root_sha256":"2222222222222222222222222222222222222222222222222222222222222222","schema_version":"hswm-weight-snapshot/v1","snapshot_id":"8d293d2b858dc9372ef4604c8aaa4b81d7c7af59efa88205646ade40ab7eafd1","topology_sha256":"1111111111111111111111111111111111111111111111111111111111111111","weights":[{"edge_id":"edge:a","log_salience":-0.5},{"edge_id":"edge:b","log_salience":-0.25}]}'
 it("loads the original two-table snapshot shape with bound candidate linkage",async()=>{const directory=await mkdtemp(join(tmpdir(),"native-p1-sqlite-")),arm="A1",arms=join(directory,"arms");try{await (await import("node:fs/promises")).mkdir(arms);const database=new DatabaseSync(join(arms,`${arm}.weights.sqlite3`));database.exec("CREATE TABLE weight_snapshots(snapshot_id TEXT, canonical_snapshot BLOB); CREATE TABLE staged_weight_candidates(candidate_id TEXT, snapshot_id TEXT)");database.prepare("INSERT INTO weight_snapshots VALUES (?,?)").run("8d293d2b858dc9372ef4604c8aaa4b81d7c7af59efa88205646ade40ab7eafd1",new TextEncoder().encode(snapshot));database.prepare("INSERT INTO staged_weight_candidates VALUES (?,?)").run("candidate","8d293d2b858dc9372ef4604c8aaa4b81d7c7af59efa88205646ade40ab7eafd1");database.close();const evidence=join(directory,"evidence.json");await writeFile(evidence,JSON.stringify({experiment_receipt:{arms:[{arm_id:arm,episodes:[{candidate_id:"candidate",base_snapshot_id:"8d293d2b858dc9372ef4604c8aaa4b81d7c7af59efa88205646ade40ab7eafd1",episode_index:1,fsm_final_state:"rejected"}]}]}}));const rows=await Effect.runPromise(loadNativeP1GateCandidates(evidence,directory).pipe(Effect.provide(NodePosixFileSystemLive)));expect(rows).toHaveLength(1);expect(rows[0]).toMatchObject({armId:arm,candidateId:"candidate",episodeIndex:1})}finally{await (await import("node:fs/promises")).rm(directory,{recursive:true,force:true})}})
 it("requires the complete offline CLI argument surface",()=>expect(Either.isRight(decodeNativeP1GateCommand(["--evidence","a","--dataset-root","b","--experiment-directory","c","--embedding-cache-folder","d","--output","e"]))).toBe(true))
})
describe("native P1 full synthetic engineering oracle",()=>{
 it("replays exact original input bytes with native services and reproduces the entire diagnostic",async()=>{
  const directory=await mkdtemp(join(tmpdir(),"native-p1-replay-"))
  try {
   const fixture=resolve(root,"tests/fixtures/native_migration/p1_gate_v1")
   const input=JSON.parse(readFileSync(join(fixture,"replay-files.original.v1.json"),"utf8")) as {files:readonly {path:string;data:string;sha256:string}[]}
   const fs=await import("node:fs/promises"),path=await import("node:path")
   for(const file of input.files){const bytes=Buffer.from(file.data,"base64");expect(createHash("sha256").update(bytes).digest("hex")).toBe(file.sha256);const destination=join(directory,file.path);await fs.mkdir(path.dirname(destination),{recursive:true});await fs.writeFile(destination,bytes)}
   const output=join(directory,"native.json")
   const result=await Effect.runPromise(Effect.either(runNativeP1GateCli(["--evidence",join(directory,"evidence.json"),"--dataset-root",join(directory,"dataset"),"--experiment-directory",join(directory,"experiment"),"--embedding-cache-folder",join(directory,"cache"),"--output",output]).pipe(Effect.provide(NodePosixFileSystemLive))))
   if(Either.isLeft(result))throw new Error(JSON.stringify(result.left))
   expect(readFileSync(output,"utf8")).toBe(readFileSync(join(fixture,"expected.json"),"utf8"))
   expect(result.right).toBe('{\n  "candidates": 1,\n  "fresh_gate_passes": 0,\n  "nonzero_unseen_delta": 0\n}\n')
  } finally {await (await import("node:fs/promises")).rm(directory,{recursive:true,force:true})}
 })
})

describe("native P1 full nonzero original engineering oracles", () => {
 it.each(["positive", "negative"])("reproduces the entire %s original diagnostic and stdout", async scenario => {
  const fixture=JSON.parse(readFileSync(resolve(root,`tests/fixtures/native_migration/p1_gate_v1/nonzero-${scenario}.original.v1.json`),"utf8")) as {files:readonly {path:string;sha256:string;data:string}[]; expected:string;stdout:string}
  const directory=await mkdtemp(join(tmpdir(),`native-p1-${scenario}-`)),fs=await import("node:fs/promises"),path=await import("node:path")
  try {
   for(const file of fixture.files){const bytes=Buffer.from(file.data,"base64");expect(createHash("sha256").update(bytes).digest("hex")).toBe(file.sha256);const destination=join(directory,file.path);await fs.mkdir(path.dirname(destination),{recursive:true});await fs.writeFile(destination,bytes)}
   const output=join(directory,"native.json")
   const result=await Effect.runPromise(Effect.either(runNativeP1GateCli(["--evidence",join(directory,"evidence.json"),"--dataset-root",join(directory,"dataset"),"--experiment-directory",join(directory,"experiment"),"--embedding-cache-folder",join(directory,"cache"),"--output",output]).pipe(Effect.provide(NodePosixFileSystemLive))))
   if(Either.isLeft(result))throw new Error(JSON.stringify(result.left))
   expect(readFileSync(output,"utf8")).toBe(fixture.expected)
   expect(result.right).toBe(fixture.stdout)
  } finally {await fs.rm(directory,{recursive:true,force:true})}
 })
})
