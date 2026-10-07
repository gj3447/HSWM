import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root=resolve(import.meta.dirname,"../.."), folder="ontology/queries/hswm_w1_full_instrument_2026-10-07"
const primary="ontology/development/HSWM_W1_FULL_INSTRUMENT_PROGRESS_2026-10-07.v1.json"
const sources=["ontology/development/HSWM_RUNTIME_CONFORMANCE_PROGRESS_2026-10-07.v1.json","ontology/development/HSWM_PREFLIGHT_REFINEMENT_PROGRESS_2026-10-07.v1.json","ontology/development/HSWM_PROGRESS_CONSOLIDATION_2026-10-07.v1.json","ontology/development/HSWM_PROGRESS_PLAN_2026-10-06.v1.json","ontology/development/HSWM_JOURNAL_REPLAY_PROGRESS_2026-10-06.v1.json","ontology/development/HSWM_JOURNAL_ADAPTER_PROGRESS_2026-10-06.v1.json"] as const
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type B = Mutable<KgBundle>
const load=()=>[primary,...sources].map(p=>JSON.parse(readFileSync(resolve(root,p),"utf8")) as B)
const compile=(bs=load())=>{const x=compileKgBundle(bs.map((b,i)=>({sourceId:`w1-${i}`,rawBytes:Buffer.from(JSON.stringify(b))})),"v2");if(Either.isLeft(x))throw x.left;return x.right}
const role=(b:B,n:string)=>b.nodes.filter(x=>x.properties["standard_graph_role"]===n)
const obs=(bs:B[],task:string)=>{const s=role(bs[0]!,"CURRENT_SELECTION").find(x=>x.properties["task_id"]===task)!;return bs.flatMap(x=>x.nodes).find(x=>x.uid===s.properties["selected_observation_uid"])!}
const query=async(n:string,bs=load())=>{const x=await Effect.runPromise(queryKgBundle(compile(bs),readFileSync(resolve(root,folder,`${n}.rq`),"utf8")));if(typeof x==="boolean")throw Error("query boolean");return x.map(r=>Object.fromEntries(Object.entries(r).map(([k,v]:any)=>[k,v?.value??null])))}
const conforms=(bs:B[])=>Effect.runPromise(validateKgShacl(compile(bs),readFileSync(resolve(root,folder,"shapes.ttl"))))
const recount = (bs: B[]) => {
 const p = bs[0]!
 p.expected_counts = { ...p.expected_counts, nodes: p.nodes.length, anchors: p.anchors.length, relations: p.relations.length }
 return bs
}
// A published snapshot keeps its own manifest bytes when another writer changes navigation.
// Unpublished candidate snapshots are checked against their candidate checkout instead.
const publicationBytes = (path: string): Buffer => {
 const commit = execFileSync("git", ["log", "-1", "--format=%H", "--", primary], { cwd: root }).toString().trim()
 if (commit) {
  const published = execFileSync("git", ["show", `${commit}:${primary}`], { cwd: root })
  if (kgSha256(published) === kgSha256(readFileSync(resolve(root, primary)))) return execFileSync("git", ["show", `${commit}:${path}`], { cwd: root })
 }
 return readFileSync(resolve(root, path))
}

it("composes seven pinned sources with nine unambiguous selections",async()=>{
 const bs=load(), p=bs[0]!, selectors=role(p,"CURRENT_SELECTION")
 expect((await Effect.runPromise(validateKgShacl(compile(bs),readFileSync(resolve(root,"schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"))))).conforms).toBe(true)
 expect((await conforms(bs)).conforms).toBe(true); expect(selectors).toHaveLength(9);expect(new Set(selectors.map(x=>x.properties["task_id"])).size).toBe(9)
 expect(obs(bs,"T5").properties).toMatchObject({observation_order:2,completion_disposition:"OPEN",work_ready:false,measured_model_requests:0})
 expect(obs(bs,"T1").properties["completion_disposition"]).toBe("COMPLETE");expect(obs(bs,"T4").properties["completion_disposition"]).toBe("COMPLETE")
 expect(await query("current")).toHaveLength(9);expect(await query("history")).toHaveLength(3);expect(await query("bindings")).toHaveLength(9)
 expect(await query("evidence")).toHaveLength(29);expect((await query("next")).map(x=>x["task"])).toEqual([]);expect(await query("blocked")).toHaveLength(5);expect(await query("boundaries")).toHaveLength(6);expect(await query("trace")).toHaveLength(10)
},30000)
it("pins every new artifact to the reviewed commit and preserves the old trace",async()=>{
 const p=load()[0]!, rev=String(role(p,"PROGRESS_VIEW")[0]!.properties["reviewed_revision"])
 for(const a of role(p,"EVIDENCE_ARTIFACT")){const bytes=readFileSync(resolve(root,String(a.properties["source_path"])));expect(kgSha256(bytes)).toBe(a.properties["source_sha256"]);expect(kgSha256(execFileSync("git",["show",`${rev}:${String(a.properties["source_path"])}`],{cwd:root}))).toBe(a.properties["source_sha256"])}
 for(const binding of p.artifact_bindings){expect(kgSha256(publicationBytes(binding.path))).toBe(binding.sha256)}
 expect(await query("trace")).toHaveLength(10)
},30000)
it("rejects selector loss, duplicate selection, and T5 completion promotion",async()=>{
 const missing=load(), p=missing[0]!, s=role(p,"CURRENT_SELECTION")[0]!;p.relations=p.relations.filter(e=>!(e.from_uid===p.bundle_uid&&e.to_uid===s.uid));expect((await conforms(recount(missing))).conforms).toBe(false)
 const duplicate=load(), q=duplicate[0]!, c=structuredClone(role(q,"CURRENT_SELECTION")[0]!);c.uid+="-copy";q.nodes.push(c);q.relations.push({from_uid:q.bundle_uid,to_uid:c.uid,type:"HAS_CONCEPT",authority_class:"SECONDARY_AI",scope:"W1_FULL_PROGRESS",status:"PROPOSED"});expect((await conforms(recount(duplicate))).conforms).toBe(false)
 const promoted=load();obs(promoted,"T5").properties["completion_disposition"]="COMPLETE";expect((await conforms(promoted)).conforms).toBe(false)
 const wrong=load(), selector=role(wrong[0]!,"CURRENT_SELECTION").find(x=>x.properties["task_id"]==="T5")!;selector.properties["selected_observation_uid"]=obs(wrong,"T1").uid;expect((await conforms(wrong)).conforms).toBe(false)
 const detached=load(), ds=role(detached[0]!,"CURRENT_SELECTION").find(x=>x.properties["task_id"]==="T5")!;detached[0]!.relations=detached[0]!.relations.filter(e=>!(e.from_uid===ds.uid&&e.to_uid===obs(detached,"T5").uid));expect((await conforms(recount(detached))).conforms).toBe(false)
 const badHistory=load(), current=obs(badHistory,"T5"), previous=String(current.properties["previous_observation_uid"]);badHistory[0]!.relations=badHistory[0]!.relations.filter(e=>!(e.from_uid===current.uid&&e.to_uid===previous));expect(await query("history",recount(badHistory))).toHaveLength(1)
 const wrongHistory=load(); obs(wrongHistory,"T5").properties["previous_observation_uid"]=obs(wrongHistory,"T1").uid;expect(await query("history",wrongHistory)).toHaveLength(1)
},30000)
