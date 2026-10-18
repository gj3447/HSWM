import { readFileSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const primary = "ontology/development/HSWM_SEMANTIC_W_OPTIMIZATION_PLAN_2026-10-18.v1.json"
const folder = "ontology/queries/hswm_semantic_w_plan_2026-10-18"
const prefix = "sym:Concept:hswm-semantic-w-plan-2026-10-18-"
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const read = (path: string) => readFileSync(resolve(root, path))
const load = (): Bundle => JSON.parse(read(primary).toString())
const node = (b: Bundle, id: string) => b.nodes.find(n => n.uid === prefix + id)!
const planRoot = (b: Bundle) => b.nodes.find(n => n.properties["standard_graph_role"] === "W_PLAN_ROOT")!
const compile = (bundle: Bundle) => {
  const result = compileKgBundle([{ sourceId: "semantic-w-plan", rawBytes: Buffer.from(JSON.stringify(bundle)) }], "v2")
  if (Either.isLeft(result)) throw result.left
  return result.right
}
const query = async (name: string) => {
  const rows = await Effect.runPromise(queryKgBundle(compile(load()), read(`${folder}/${name}.rq`).toString()))
  if (typeof rows === "boolean") throw new Error("Expected SELECT rows")
  return rows
}
const values = (rows: Awaited<ReturnType<typeof query>>, key: string) => rows.map(row => row[key]?.["value"] ?? null)
const conforms = (bundle: Bundle) => Effect.runPromise(validateKgShacl(compile(bundle), read(`${folder}/shapes.ttl`)))

it("validates native RDF and SHACL, retaining planned work and both failure and bounded-gain reports", async () => {
  const b = load()
  expect((await Effect.runPromise(validateKgShacl(compile(b), read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")))).conforms).toBe(true)
  expect((await conforms(b)).conforms).toBe(true)
  expect(planRoot(b).properties).toMatchObject({ status: "PLANNED", execution_status: "NOT_RUN_THIS_PLAN", new_model_calls: 0, efficacy_status: "NOT_EVALUATED_THIS_PLAN" })
  const sources = await query("sources")
  expect(values(sources, "id").sort()).toEqual(["S1", "S2", "S3", "S4", "S5", "S6"])
  const activation = sources.find(row => row["id"]?.["value"] === "S1")!
  expect(activation["status"]?.["value"]).toBe("EXISTING_IMPLEMENTATION_REPORTED_NO_GAIN")
  expect(activation["observation"]?.["value"]).toContain("4/8→4/8")
  expect(activation["path"]?.["value"]).toBe("docs/operations/HSWM_LOCAL_ACTIVATION_2026-10-18.md")
  const diagnosis = sources.find(row => row["id"]?.["value"] === "S6")!
  expect(diagnosis["status"]?.["value"]).toBe("EXISTING_RESEARCH_ADAPTER_REPORTED_BOUNDED_GAIN")
  expect(diagnosis["observation"]?.["value"]).toContain("4/8→8/8")
  expect(diagnosis["limit"]?.["value"]).toContain("not default CLI integration")
})

it("answers the eight-task roadmap, including the two independent branches and their join", async () => {
  const rows = await query("roadmap")
  const expected: Record<string, string[]> = { P00: [], P01: ["P00"], P02: ["P01"], P03: ["P00"], P04: ["P02", "P03"], P05: ["P04"], P06: ["P05"], P07: ["P06"] }
  expect([...new Set(values(rows, "id"))].sort()).toEqual(Object.keys(expected))
  for (const [id, prerequisites] of Object.entries(expected)) {
    const selected = rows.filter(row => row["id"]?.["value"] === id)
    expect(values(selected, "prerequisite").filter(x => x !== null).sort()).toEqual(prerequisites)
    for (const row of selected) {
      expect(row["status"]?.["value"]).toBe("PLANNED")
      for (const key of ["inputs", "outputs", "acceptance", "responsible", "target"]) expect(row[key]?.["value"]?.length).toBeGreaterThan(0)
    }
  }
  expect(values(await query("next"), "id")).toEqual(["P00"])
})

it("retrieves owned CLI usage and binds every node to its exact dated source bytes", async () => {
  // A published dated plan keeps its sources even when the live implementation evolves.
  const revision = execFileSync("git", ["log", "-1", "--format=%H", "--", primary], { cwd: root, encoding: "utf8" }).trim()
  const published = revision && kgSha256(execFileSync("git", ["show", `${revision}:${primary}`], { cwd: root })) === kgSha256(read(primary))
  const source = (path: string) => published ? execFileSync("git", ["show", `${revision}:${path}`], { cwd: root }) : read(path)
  const b = load()
  for (const binding of b.artifact_bindings) expect(kgSha256(source(binding.path)), binding.path).toBe(binding.sha256)
  for (const n of b.nodes) {
    expect(b.artifact_bindings.find(a => a.path === n.properties["source_path"])?.sha256, n.uid).toBe(n.properties["source_sha256"])
  }
  const rows = await query("cli")
  expect(values(rows, "id").sort()).toEqual(["activation", "finite", "workspace"])
  for (const row of rows) {
    const command = row["command"]?.["value"] ?? ""
    expect(command).toMatch(/^src\/hswm\/effect-runtime\/bin\/hswm-/)
    expect(row["help"]?.["value"]).toBe(`${command} --help`)
    expect(b.artifact_bindings.some(a => a.path === command)).toBe(true)
    expect(source(row["guide"]?.["value"] ?? "").length).toBeGreaterThan(0)
    expect(row["fragment"]?.["value"]?.length).toBeGreaterThan(0)
  }
})

const mutations: Array<[string, (b: Bundle) => void]> = [
  ["missing acceptance criterion", b => { delete node(b, "P05").properties["acceptance"] }],
  ["missing preservation prerequisite", b => { b.relations = b.relations.filter(r => !(r.from_uid === prefix + "P04" && r.to_uid === prefix + "P03")) }],
  ["dependency cycle", b => { b.relations.find(r => r.from_uid === prefix + "P01" && r.scope === "PREREQUISITE")!.to_uid = prefix + "P02" }],
  ["duplicate task identity", b => { node(b, "P03").properties["task_id"] = "P01" }],
  ["dependency relabeled as usage", b => { b.relations.find(r => r.scope === "PREREQUISITE")!.scope = "USES_CLI" }],
  ["plan promoted to completed work", b => { node(b, "P07").properties["status"] = "COMPLETED" }],
  ["plan promoted to measured efficacy", b => { planRoot(b).properties["efficacy_status"] = "PROVEN" }],
  ["invented new model call", b => { planRoot(b).properties["new_model_calls"] = 1 }],
  ["AI interpretation promoted to user canon", b => { node(b, "R4").properties["authority_class"] = "PRIMARY_USER_UTTERANCE" }],
  ["lost source bytes", b => { delete node(b, "S1").properties["source_sha256"] }],
  ["lost task evidence", b => { b.relations = b.relations.filter(r => !(r.from_uid === prefix + "P01" && r.type === "HAS_SOURCE")) }],
  ["lost owned CLI guide", b => { b.relations = b.relations.filter(r => !(r.from_uid === prefix + "cli-activation" && r.scope === "OWNED_USAGE")) }],
]
it.each(mutations)("rejects %s", async (_name, mutate) => {
  const b = load()
  mutate(b)
  b.expected_counts["relations"] = b.relations.length
  expect((await conforms(b)).conforms).toBe(false)
})
