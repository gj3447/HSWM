import { readFileSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const primary = "ontology/identity/hswm_core/HSWM_OPTIMIZATION_CONTRACT_ONTOLOGY.v1.json"
const folder = "ontology/queries/hswm_optimization_contract_2026-10-07"
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const read = (path: string) => readFileSync(resolve(root, path))
// Preserve published evidence when live routing later gains more rules.
const publishedSource = (path: string): Buffer => {
  const revision = execFileSync("git", ["log", "-1", "--format=%H", "--", primary], { cwd: root, encoding: "utf8" }).trim()
  if (revision) {
    const published = execFileSync("git", ["show", `${revision}:${primary}`], { cwd: root })
    if (kgSha256(published) === kgSha256(read(primary))) return execFileSync("git", ["show", `${revision}:${path}`], { cwd: root })
  }
  return read(path)
}
const load = (): Bundle => JSON.parse(read(primary).toString())
const compile = (bundle: Bundle) => { const result = compileKgBundle([{ sourceId: "optimization-contract", rawBytes: Buffer.from(JSON.stringify(bundle)) }], "v2"); if (Either.isLeft(result)) throw result.left; return result.right }
const query = async (name: string) => { const result = await Effect.runPromise(queryKgBundle(compile(load()), read(`${folder}/${name}.rq`).toString())); if (typeof result === "boolean") throw new Error("Expected SELECT rows"); return result }
const values = (rows: Awaited<ReturnType<typeof query>>, key: string) => rows.map(row => row[key]?.["value"] ?? null)

it("models the six augmentations, independent evaluation contracts, and unknown bottlenecks", async () => {
  const bundle = load()
  expect((await Effect.runPromise(validateKgShacl(compile(bundle), read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")))).conforms).toBe(true)
  expect((await Effect.runPromise(validateKgShacl(compile(bundle), read(`${folder}/shapes.ttl`)))).conforms).toBe(true)
  const rules = await query("rules")
  expect(values(rules, "id")).toEqual(["R1", "R2", "R3", "R4", "R5", "R6"])
  expect(values(rules, "baseRuleUid")).toEqual([1, 2, 3, 4, 5, 6].map(id => `sym:Concept:hswm-optimization-r${id}-2026-10-07`))
  expect(values(await query("contracts"), "id")).toEqual([
    "LEARNING_EFFICACY_OUTCOME", "RESOURCE_TASK_BUDGET", "END_TO_END_BOTTLENECK_TRADEOFF", "REPRESENTATION_OBSERVATION_ADMISSION"
  ])
  const bottlenecks = await query("bottlenecks")
  expect(bottlenecks).toHaveLength(6)
  expect(values(bottlenecks, "stage")).toEqual(["GRAPH_COMMIT", "INPUT_ASSEMBLY", "LEARNING_EVALUATION", "LLM_INFERENCE", "RETRIEVAL_ROUTING", "TOOL_IO"])
  expect(bottlenecks.every(row => row["value"]?.["value"] === "unknown" && row["status"]?.["value"] === "NOT_MEASURED")).toBe(true)
})

it("keeps formal references source-bound and leaves goal and efficacy unpromoted", async () => {
  const bundle = load(), rootNode = bundle.nodes.find(node => node.uid === bundle.bundle_uid)!
  expect(rootNode.properties["runtime_w_learning_proved"]).toBe(false)
  expect(rootNode.properties["global_optimality_proved"]).toBe(false)
  expect(rootNode.properties["measured_efficacy"]).toBe(false)
  for (const binding of bundle.artifact_bindings) expect(kgSha256(publishedSource(binding.path)), binding.path).toBe(binding.sha256)
  const userSource = bundle.nodes.find(node => node.properties["standard_graph_role"] === "USER_SOURCE")!
  expect(userSource.properties["utterance_verbatim"]).toBe(read(String(userSource.properties["source_path"])).toString())
  const goal = bundle.nodes.find(node => node.properties["standard_graph_role"] === "USER_GOAL")!
  expect(goal.properties["achievement_value"]).toBe("UNKNOWN")
  expect(goal.properties["description_origin"]).toBe("SECONDARY_AI_RESTATEMENT_OF_USER_SOURCE")
  expect(values(await query("proofs"), "theorem")).toEqual([
    "HSWM.OperationalQuotient.output_equivalence_does_not_imply_operational_equivalence",
    "HSWM.OperationalQuotient.visible_bit_has_no_exact_learning_abstraction"
  ])
  const leanSource = read("formal/HSWMOperationalQuotient.lean").toString()
  expect(leanSource).toContain("namespace HSWM.OperationalQuotient")
  expect(leanSource).toContain("theorem output_equivalence_does_not_imply_operational_equivalence")
  expect(leanSource).toContain("theorem visible_bit_has_no_exact_learning_abstraction")
  expect(values(await query("boundaries"), "id")).toEqual([
    "SCOPED_IMPROVEMENT_NOT_GLOBAL_OPTIMALITY", "USER_GOAL_NOT_MEASUREMENT", "LOCAL_DOCUMENT_GRAPH_NOT_RUNTIME_W"
  ])
})
