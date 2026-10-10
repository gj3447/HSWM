import { readFileSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const primary = "ontology/development/HSWM_CORE_SELECTION_LEARNING_BRIDGE_2026-10-10.v1.json"
const folder = "ontology/queries/hswm_core_learning_bridge_2026-10-10"
const artifacts = "docs/operations/artifacts/core_learning_bridge_2026-10-10"
const prefix = "sym:Concept:hswm-core-learning-2026-10-10-"
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const read = (path: string) => readFileSync(resolve(root, path))
const load = (): Bundle => JSON.parse(read(primary).toString())
const node = (bundle: Bundle, id: string) => bundle.nodes.find(n => n.uid === prefix + id)!
const compile = (bundle: Bundle) => {
  const result = compileKgBundle([{ sourceId: "core-learning", rawBytes: Buffer.from(JSON.stringify(bundle)) }], "v2")
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
// This dated source review must keep referring to the published bytes when live code evolves.
const publishedSource = (path: string): Buffer => {
  const revision = execFileSync("git", ["log", "-1", "--format=%H", "--", primary], { cwd: root, encoding: "utf8" }).trim()
  if (revision) {
    const published = execFileSync("git", ["show", `${revision}:${primary}`], { cwd: root })
    if (kgSha256(published) === kgSha256(read(primary))) return execFileSync("git", ["show", `${revision}:${path}`], { cwd: root })
  }
  return read(path)
}

it("validates the common and domain SHACL profiles and retrieves exactly six AI elements with canon sources", async () => {
  const bundle = load()
  expect((await Effect.runPromise(validateKgShacl(compile(bundle), read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")))).conforms).toBe(true)
  expect((await conforms(bundle)).conforms).toBe(true)
  const rows = await query("elements")
  // The native export canonically orders bindings independently of SPARQL ORDER BY.
  expect(values(rows, "id").sort()).toEqual(["E1", "E2", "E3", "E4", "E5", "E6"])
  expect(values(rows, "authority")).toEqual(Array(6).fill("SECONDARY_AI"))
  expect(values(rows, "origin")).toEqual(Array(6).fill(`${artifacts}/conversation-sources.v1.json`))
  expect(values(rows, "canonSource").every(path => path?.startsWith("docs/canon/"))).toBe(true)
  expect(node(bundle, "E6").properties["name"]).toBe("CHU의 정체성과 선의 공리")
})

it("retrieves seven ordered unconnected stages, reusable source capabilities and all eight blocking gaps", async () => {
  const rows = await query("bridge")
  expect([...new Set(values(rows, "id"))].sort()).toEqual(["B1", "B2", "B3", "B4", "B5", "B6", "B7"])
  for (const row of rows) {
    expect(row["status"]?.["value"]).toBe("PROPOSED_NOT_CONNECTED")
    const ordinal = Number(String(row["id"]?.["value"] ?? "").slice(1))
    expect(row["previous"]?.["value"] ?? null).toBe(ordinal === 1 ? null : `B${ordinal - 1}`)
    expect(row["implementation"]?.["value"]?.length ?? 0).toBeGreaterThan(0)
    expect(row["source"]?.["value"]?.length ?? 0).toBeGreaterThan(0)
  }
  const gaps = await query("gaps")
  expect([...new Set(values(gaps, "id"))].sort()).toEqual(["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
  const design = JSON.parse(read(`${artifacts}/design.v1.json`).toString())
  for (const gap of design.gaps) {
    expect(gaps.filter(row => row["id"]?.["value"] === gap.id).map(row => row["blockedStage"]?.["value"]).sort()).toEqual([...gap.blocks].sort())
  }
  expect(values(gaps, "status").every(status => status === "OPEN")).toBe(true)
})

it("preserves two E2/E4 role occurrences, two distinct learning targets and scoped relation contracts", () => {
  const bundle = load()
  for (const [role, target, ordinal] of [["selection", "E2", 0], ["learning", "E4", 1]] as const) {
    expect(node(bundle, role).properties["ordinal"]).toBe(ordinal)
    expect(bundle.relations.filter(r => r.from_uid === prefix + role && r.scope === "ROLE_TARGET").map(r => r.to_uid)).toEqual([prefix + target])
  }
  expect(node(bundle, "L1").properties["target"]).toBe("CONTEXT_CONDITIONED_ACTIVATION_POLICY")
  expect(node(bundle, "L2").properties["target"]).toBe("CANONICAL_RELATION_SEMANTIC_REVISION")
  const contracts = JSON.parse(read(`${artifacts}/graph-contract.v1.json`).toString()).relations as Array<{ predicate: string; scope: string; domain: string[]; range: string[] }>
  const roleOf = (uid: string) => bundle.nodes.find(n => n.uid === uid)?.properties["standard_graph_role"] ?? "ANCHOR"
  for (const relation of bundle.relations) {
    const contract = contracts.find(c => c.scope === relation.scope && c.predicate === relation.type)
    expect(contract, relation.scope).toBeDefined()
    expect(contract!.domain).toContain(roleOf(relation.from_uid))
    expect(contract!.range).toContain(roleOf(relation.to_uid))
    expect(relation.authority_class).toBe("SECONDARY_AI")
  }
})

it("binds every source and keeps the user request separate from AI interpretation and external observations", async () => {
  const bundle = load()
  for (const binding of bundle.artifact_bindings) expect(kgSha256(publishedSource(binding.path)), binding.path).toBe(binding.sha256)
  for (const n of bundle.nodes) {
    const binding = bundle.artifact_bindings.find(b => b.path === n.properties["source_path"])
    expect(binding?.sha256, n.uid).toBe(n.properties["source_sha256"])
  }
  const conversation = JSON.parse(read(`${artifacts}/conversation-sources.v1.json`).toString())
  expect(node(bundle, "U1").properties["utterance_verbatim"]).toBe(conversation.userRequest.verbatim)
  expect(node(bundle, "U1").properties["authority_class"]).toBe("PRIMARY_USER_UTTERANCE")
  expect(conversation.assistantElements.authority).toBe("SECONDARY_AI_SUMMARY")
  const sources = await query("sources")
  expect(sources).toHaveLength(7)
  expect(values(sources, "sourceAuthority").filter(a => a === "PRIMARY_USER_UTTERANCE")).toHaveLength(1)
  const review = JSON.parse(read(`${artifacts}/source-review.v1.json`).toString())
  expect(review.gitRevision).toMatch(/^[a-f0-9]{40}$/)
  expect(review.repository).toBe("HSWM_LIKENESS")
  expect(review.files.every((f: { path: string; sha256: string }) => !f.path.startsWith("/") && /^[a-f0-9]{64}$/.test(f.sha256))).toBe(true)
})

it("retains the learning design's unknowns, full-cohort boundary and distinct probability and byte-budget meanings", () => {
  const design = JSON.parse(read(`${artifacts}/design.v1.json`).toString())
  expect(design.status).toBe("PROPOSED_NOT_CONNECTED")
  expect(design.probabilityContract.jev).toBe("ADVISORY_RELEVANCE")
  expect(design.probabilityContract.logging).toBe("ACTUAL_FIXED_RANDOMIZED_ACTION_PROBABILITY")
  expect(design.probabilityContract.unsupportedPropensity).toBeNull()
  expect(design.measurementContract.unknown).toBeNull()
  expect(design.measurementContract.export).toBe("BLOCK_WHOLE_COHORT_IF_ANY_ATTEMPT_INELIGIBLE")
  expect(design.measurementContract.actualModelCalls).toBe(0)
  expect(design.measurementContract.efficacy).toBe("UNMEASURED")
  expect(design.budgetContract.nativeContext.unit).not.toBe(design.budgetContract.likenessContext.unit)
  expect(design.budgetContract.unknownTokens).toBeNull()
  expect(design.budgetContract.overflow).toBe("REJECT_WITHOUT_TRUNCATION")
  expect(design.lanes[1].boundary).toContain("Multi-frame context trace is incompatible")
})

const mutations: Array<[string, (b: Bundle) => void]> = [
  ["lost bridge role", b => { b.relations = b.relations.filter(r => !(r.scope === "BRIDGE_ROLE" && r.to_uid === prefix + "learning")) }],
  ["selection retargeted to learning", b => { b.relations.find(r => r.from_uid === prefix + "selection" && r.scope === "ROLE_TARGET")!.to_uid = prefix + "E4" }],
  ["lost immediate prerequisite", b => { b.relations = b.relations.filter(r => !(r.from_uid === prefix + "B4" && r.scope === "PREREQUISITE")) }],
  ["proposal promoted to implementation", b => { node(b, "B7").properties["status"] = "IMPLEMENTED" }],
  ["AI element promoted to user canon", b => { node(b, "E4").properties["authority_class"] = "PRIMARY_USER_UTTERANCE" }],
  ["lost element provenance", b => { b.relations = b.relations.filter(r => !(r.from_uid === prefix + "E2" && r.scope === "AI_ELEMENT_ORIGIN")) }],
  ["lost CLI usage", b => { b.relations = b.relations.filter(r => r.scope !== "OWNED_USAGE") }],
]
it.each(mutations)("rejects %s", async (_name, mutate) => {
  const bundle = load()
  mutate(bundle)
  bundle.expected_counts["relations"] = bundle.relations.length
  expect((await conforms(bundle)).conforms).toBe(false)
})
