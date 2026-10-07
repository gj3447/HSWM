import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Effect, Either } from "effect"
import { beforeAll, expect, it } from "vitest"
import { compileKgBundle, type KgBundle, type KgBundleProjection } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = fileURLToPath(new URL("../../", import.meta.url))
const queryRoot = "ontology/queries/hswm_optimization_rules_2026-10-07"
const artifactRoot = "docs/canon/artifacts/hswm_optimization_rules_2026-10-07"
const bundlePath = "ontology/identity/hswm_core/HSWM_OPTIMIZATION_RULES_ONTOLOGY.v1.json"
const read = (path: string) => readFile(resolve(root, path))
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const role = (value: string) => bundle.nodes.filter(n => n.properties["standard_graph_role"] === value)
let bundle: KgBundle
let projection: KgBundleProjection

beforeAll(async () => {
  const bytes = await read(bundlePath)
  bundle = JSON.parse(bytes.toString()) as KgBundle
  const result = compileKgBundle([{ sourceId: "optimization-rules", rawBytes: bytes }], "v2")
  if (Either.isLeft(result)) throw result.left
  projection = result.right
})

const rows = async (name: string) => {
  const result = await Effect.runPromise(queryKgBundle(projection, (await read(`${queryRoot}/${name}.rq`)).toString()))
  if (typeof result === "boolean") throw new Error("expected SELECT rows")
  return result.map(row => Object.fromEntries(Object.entries(row).map(([key, term]) => [key, term?.["value"] ?? null])))
}

it("keeps every source byte binding and exact user utterance, separate from AI rule names", async () => {
  for (const binding of bundle.artifact_bindings) expect(hash(await read(binding.path)), binding.path).toBe(binding.sha256)
  for (const node of bundle.nodes) {
    const source = String(node.properties["source_path"])
    expect(bundle.artifact_bindings.some(b => b.path === source)).toBe(true)
    expect(hash(await read(source))).toBe(node.properties["source_sha256"])
  }
  expect(role("USER_SOURCE")).toHaveLength(3)
  for (const source of role("USER_SOURCE")) {
    expect(source.properties["utterance_verbatim"]).toBe((await read(String(source.properties["source_path"]))).toString().replace(/\n$/, ""))
    expect(source.properties["authority_class"]).toBe("USER_PRIMARY")
  }
  expect(role("OPTIMIZATION_RULE").every(n => n.properties["authority_class"] === "SECONDARY_AI")).toBe(true)
})

it("returns six bounded full rule sections that the actual instruction graph selects", async () => {
  const rules = await rows("rules")
  expect(rules.map(r => r["id"]).sort()).toEqual(["R1", "R2", "R3", "R4", "R5", "R6"])
  const routes = JSON.parse((await read("docs/agent-rules/routes.json")).toString()) as {
    nodes: { id: string; path?: string; section?: string }[]
    edges: { from: string; type: string; to: string }[]
  }
  for (const rule of rules) {
    const source = routes.nodes.find(n => n.id === `owner:optimization-${String(rule["id"]).toLowerCase()}`)!
    expect([source.path, source.section]).toEqual([rule["source"], rule["section"]])
    const sections = (await read(source.path!)).toString().split(/(?=^## )/m).map(s => s.trimEnd())
    expect(sections).toContain(rule["directive"])
    const requiredBy = routes.edges.filter(e => e.type === "REQUIRES" && e.to === source.id)
    expect(requiredBy.map(e => e.from)).toEqual([`task:hswm-rule-${["R2", "R3"].includes(String(rule["id"])) ? "cli" : "context"}`])
  }
  const usage = routes.nodes.find(n => n.id === "owner:usage")!
  expect([usage.path, usage.section]).toEqual(["docs/agent-rules/CLI.md", "hswm-cli-entry/@intro"])
  expect((await read("AGENTS.md")).toString()).not.toContain("## R1 task activation")
})

it("joins task inheritance to exactly the applicable rules, agreeing with all three router client probes", async () => {
  const expected: Record<string, number[]> = { base: [], docs: [], kg: [], cli: [2,3], graph: [1,4,5,6], instructions: [1,2,3,4,5,6] }
  const activation = await rows("activation")
  expect(activation).toHaveLength(12)
  for (const [task, ids] of Object.entries(expected)) {
    expect(activation.filter(r => r["task"] === task).map(r => r["rule"]).sort()).toEqual(ids.map(i => `R${i}`))
  }
  const observation = JSON.parse((await read(`${artifactRoot}/routing-observation.v1.json`)).toString()) as {
    after: { client: string; task: string; issues: unknown[]; sources: { id: string; chars: number }[] }[]
  }
  expect(observation.after).toHaveLength(18)
  for (const probe of observation.after) {
    expect(probe.issues).toEqual([])
    expect(probe.sources.filter(s => s.id.startsWith("owner:optimization-")).map(s => s.id)).toEqual(expected[probe.task]!.map(i => `owner:optimization-r${i}`))
  }
})

it("resolves CLI graph links to complete owned usage and installed launcher help", async () => {
  const commands = await rows("cli")
  expect(commands.map(c => c["command"]).sort()).toEqual(["hswm-kg-bundle", "hswm-workspace"])
  for (const command of commands) {
    const text = (await read(String(command["guide"]))).toString()
    expect(text).toContain(String(command["usage"]))
    expect(command["help"]).toBe(`${command["launcher"]} --help`)
    const help = execFileSync(resolve(root, String(command["launcher"])), ["--help"], { cwd: root, encoding: "utf8", timeout: 15_000 })
    expect(help).toContain(command["command"])
    expect(help).toContain("query")
    expect(help).toContain("validate")
  }
})

it("retains seven historical roles and their prior status, with only five proposed correspondences", async () => {
  const historical = role("HISTORICAL_ROLE")
  expect(historical).toHaveLength(7)
  expect(historical.filter(n => n.properties["historical_status"] === "USER_CLAIM_2026_07_23")).toHaveLength(4)
  const source = (await read("docs/research/HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md")).toString()
  for (const node of historical) expect(source).toContain(String(node.properties["historical_row_verbatim"]))
  const legion = await rows("legion")
  const included: Record<string, string[]> = {
    "롱기누스": ["R3", "R5"], "재배맨": ["R1", "R4", "R5"], "오캄": ["R4", "R6"],
    "유레카": ["R4", "R5", "R6"], "하네스=하데스": ["R2", "R3"]
  }
  for (const [name, ids] of Object.entries(included)) expect(legion.filter(r => r["commander"] === name).map(r => r["rule"]).sort()).toEqual(ids)
  const excluded = legion.filter(r => r["disposition"] === "EXCLUDED_THIS_APPLICATION")
  expect(excluded.map(r => r["reason"]).sort()).toEqual(["ADVERSARIAL_VALIDATION", "WEB_SEARCH"])
  expect(excluded.every(r => r["rule"] === undefined || r["rule"] === null)).toBe(true)
  for (const node of historical) {
    const outgoing = bundle.relations.filter(r => r.from_uid === node.uid && r.type === "REFERENCES")
    expect(outgoing.every(r => r.scope === "HISTORICAL_ANALOGY_ONLY" && r.status === "PROPOSED")).toBe(true)
  }
})

it("keeps typed relationship endpoints within the declared graph contract", async () => {
  const nodes = new Map(bundle.nodes.map(n => [n.uid, n]))
  const contract = JSON.parse((await read(`${artifactRoot}/graph-contract.v1.json`)).toString()) as {
    relation_contracts: { predicate: string; domain_roles: string[]; range_roles: string[] }[]
  }
  expect(bundle.expected_counts).toEqual({ nodes: 27, anchors: 0, relations: 55 })
  for (const edge of bundle.relations) {
    const rule = contract.relation_contracts.find(r => r.predicate === edge.type)!
    expect(rule.domain_roles).toContain(nodes.get(edge.from_uid)?.properties["standard_graph_role"])
    expect(rule.range_roles).toContain(nodes.get(edge.to_uid)?.properties["standard_graph_role"])
    expect(edge.authority_class).toBe("SECONDARY_AI")
  }
})

it("conforms to the existing RDF v2 and scoped rule/CLI/history SHACL profiles", async () => {
  for (const path of ["schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl", `${queryRoot}/shapes.ttl`]) {
    const result = await Effect.runPromise(validateKgShacl(projection, await read(path)))
    expect(result.results).toEqual([])
    expect(result.conforms).toBe(true)
  }
})

it("registers every competency query and shape in the existing workspace", async () => {
  const manifest = JSON.parse((await read("ontology/workspace/HSWM_WORKSPACE.v1.json")).toString()) as {
    entries: { id: string; bundle: string; queries: { id: string; path: string }[]; shapes: string[] }[]
  }
  const entry = manifest.entries.find(e => e.id === "optimization-rules")!
  expect(entry.bundle).toBe(bundlePath)
  expect(entry.queries.map(q => q.id)).toEqual(["rules", "activation", "cli", "legion"])
  expect(entry.shapes).toContain(`${queryRoot}/shapes.ttl`)
  for (const query of entry.queries) expect((await read(query.path)).length).toBeGreaterThan(0)
})
