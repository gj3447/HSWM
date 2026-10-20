import { existsSync, readFileSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const primary = "ontology/development/HSWM_TOOL_HARNESS_2026-10-20.v1.json"
const folder = "ontology/queries/hswm_tool_harness_2026-10-20"
const prefix = "sym:Concept:hswm-tool-harness-2026-10-20-"
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const read = (path: string) => readFileSync(resolve(root, path))
const load = (): Bundle => JSON.parse(read(primary).toString())
const node = (b: Bundle, id: string) => b.nodes.find(n => n.uid === prefix + id)!
const compile = (b: Bundle) => Either.getOrThrowWith(compileKgBundle([
  { sourceId: "tool-harness", rawBytes: Buffer.from(JSON.stringify(b)) }
], "v2"), error => error)
const conforms = (b: Bundle) => Effect.runPromise(validateKgShacl(compile(b), read(`${folder}/shapes.ttl`)))
const query = async (alias: string) => {
  const rows = await Effect.runPromise(queryKgBundle(compile(load()), read(`${folder}/${alias}.rq`).toString()))
  if (typeof rows === "boolean") throw new Error("Expected SELECT rows")
  return rows
}
const values = (rows: Awaited<ReturnType<typeof query>>, key: string) => rows.map(r => r[key]?.["value"])

it("validates the declared design and retrieves exact stages, roles, original targets and boundaries", async () => {
  const b = load()
  expect((await Effect.runPromise(validateKgShacl(compile(b), read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")))).conforms).toBe(true)
  expect((await conforms(b)).conforms).toBe(true)
  const flow = await query("flow")
  expect(Object.fromEntries(flow.map(r => [r["id"]!["value"], r["next"]!["value"]]))).toEqual({
    S1: "S2", S2: "S3", S3: "S4", S4: "S5", S5: "S6", S6: "S2"
  })
  expect(values(flow, "status").every(s => s === "NOT_RUN")).toBe(true)
  const activation = await query("activation")
  expect(Object.fromEntries(activation.map(r => [r["participant"]!["value"], r["target"]!["value"]]))).toEqual({
    task: prefix + "S3", condition: prefix + "condition", rule: prefix + "rule",
    tool: prefix + "tool", guide: prefix + "guide", verification: prefix + "verification"
  })
  expect(activation.find(r => r["participant"]!["value"] === "tool")!["command"]!["value"]).toBe("src/hswm/effect-runtime/bin/hswm-workspace")
  expect(activation.find(r => r["participant"]!["value"] === "guide")!["guide"]!["value"]).toBe("workspace-usage")
  expect(values(activation, "enforcement").every(s => s === "EXAMPLE_NOT_RUNTIME_ENFORCED")).toBe(true)
  expect(values(await query("boundaries"), "id").sort()).toEqual(["B1", "B2", "B3"])
})

it("binds the original user excerpts and owned CLI guide to source bytes, without upgrading the AI design", () => {
  const b = load()
  const revision = execFileSync("git", ["log", "-1", "--format=%H", "--", primary], { cwd: root, encoding: "utf8" }).trim()
  const published = revision && kgSha256(execFileSync("git", ["show", `${revision}:${primary}`], { cwd: root })) === kgSha256(read(primary))
  const source = (path: string) => published ? execFileSync("git", ["show", `${revision}:${path}`], { cwd: root }) : read(path)
  for (const binding of b.artifact_bindings) expect(kgSha256(source(binding.path)), binding.path).toBe(binding.sha256)
  for (const n of b.nodes) expect(b.artifact_bindings.find(a => a.path === n.properties["source_path"])?.sha256).toBe(n.properties["source_sha256"])
  const user = node(b, "user").properties
  const section = source(String(user["source_path"])).toString().split("### 사용자 방향과 해석의 출처")[1]!.split("### 같은 상태")[0]!
  const quotes = [...section.matchAll(/^> (.+)$/gm)].map(m => m[1]).join("\n\n")
  expect(user["utterance_verbatim"]).toBe(quotes)
  expect(user["utterance_sha256"]).toBe(kgSha256(quotes))
  expect(b.nodes.filter(n => n.properties["authority_class"] === "USER_PRIMARY").map(n => n.uid)).toEqual([prefix + "user"])
  expect(source(String(node(b, "tool").properties["command"])).length).toBeGreaterThan(0)
  expect(source(String(node(b, "guide").properties["source_path"])).toString()).toContain("## Workspace usage")
})

const uslGraphModule = new URL("../../../USL/dist/src/integrations/resource-graph.js", import.meta.url)
const uslNavigationModule = new URL("../../../USL/dist/src/language/navigation.js", import.meta.url)
it.skipIf(!existsSync(uslGraphModule) || !existsSync(uslNavigationModule))("recovers all six incidence roles through the optional local USL build without resolving locators", async () => {
  const { adaptResourceGraph } = await import(uslGraphModule.href)
  const { agentContext } = await import(uslNavigationModule.href)
  const b = load()
  const contract = node(b, "activation")
  const participants = b.relations.filter(r => r.from_uid === contract.uid && r.type === "HAS_PARTICIPATION").map(r => {
    const part = b.nodes.find(n => n.uid === r.to_uid)!
    const target = b.relations.find(e => e.from_uid === part.uid && e.scope === "PARTICIPANT_TARGET")!
    return { role: String(part.properties["participant_role"]), resource: target.to_uid }
  })
  // Ephemeral projection: original UIDs and the full n-ary binding remain intact.
  // kg:// names are local logical references, not registered remote access.
  const graph = { schema: "usl-resource-graph/v1",
    resources: b.nodes.map(n => ({ id: n.uid, types: ["urn:hswm:tool-harness:type:" + n.properties["standard_graph_role"]],
      locator: "kg://hswm-tool-harness-local/" + n.uid, metadata: n.properties })),
    meanings: [{ id: "urn:hswm:tool-harness:activation", description: "Declared task/condition/rule/tool/guide/verification binding; not runtime enforcement." }],
    links: [{ id: contract.uid, meaning: "urn:hswm:tool-harness:activation", participants, metadata: contract.properties }]
  }
  const adapted = Either.getOrThrowWith<any, unknown>(adaptResourceGraph(JSON.stringify(graph), { namespace: "hswm.tool-harness.v1" }), e => e)
  const context = Either.getOrThrowWith<any, unknown>(agentContext(adapted.plan, {
    focus: adapted.identities.resources[prefix + "S3"], target: adapted.identities.resources[prefix + "tool"],
    maxHops: 1, maxResources: 12, maxLinks: 16, maxVisits: 64
  }), e => e)
  expect(context.target?.status).toBe("FOUND")
  expect(context.links.some((l: { name: string }) => l.name === adapted.identities.links[contract.uid])).toBe(true)
  const found = new Set(context.resources.map((r: { name: string }) => r.name))
  for (const p of participants) expect(found.has(adapted.identities.resources[p.resource]), p.role).toBe(true)
  expect(found.has(adapted.identities.resources[prefix + "S1"])).toBe(false)
})

const mutations: Array<[string, (b: Bundle) => void]> = [
  ["missing condition participant", b => { b.relations = b.relations.filter(r => !(r.type === "HAS_PARTICIPATION" && r.to_uid === prefix + "part-condition")) }],
  ["tool/guide role confusion", b => { b.relations.find(r => r.from_uid === prefix + "part-tool" && r.scope === "PARTICIPANT_TARGET")!.to_uid = prefix + "guide" }],
  ["duplicate participant role", b => { node(b, "part-guide").properties["participant_role"] = "tool" }],
  ["duplicate participant order", b => { node(b, "part-guide").properties["ordinal"] = 3 }],
  ["lost owned usage", b => { b.relations = b.relations.filter(r => r.scope !== "OWNED_USAGE") }],
  ["lost next-use stage", b => { b.relations = b.relations.filter(r => !(r.type === "HAS_CONCEPT" && r.to_uid === prefix + "S6")) }],
  ["unexpected next stage", b => { b.relations.find(r => r.from_uid === prefix + "S5" && r.scope === "NEXT_STAGE")!.to_uid = prefix + "S2" }],
  ["promoted enforcement", b => { node(b, "activation").properties["enforcement_status"] = "ENFORCED" }],
  ["promoted learning", b => { b.nodes.find(n => n.uid === b.bundle_uid)!.properties["learning_status"] = "COMPLETE" }],
  ["AI design promoted to user authority", b => { node(b, "rule").properties["authority_class"] = "USER_PRIMARY" }],
  ["relationship scope changed", b => { b.relations.find(r => r.scope === "PARTICIPANT_TARGET")!.scope = "NEXT_STAGE" }],
  ["missing source digest", b => { delete node(b, "guide").properties["source_sha256"] }]
]
it.each(mutations)("rejects %s", async (_name, mutate) => {
  const b = load()
  mutate(b)
  b.expected_counts["relations"] = b.relations.length
  expect((await conforms(b)).conforms).toBe(false)
})
