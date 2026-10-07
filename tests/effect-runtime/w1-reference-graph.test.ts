import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const primary = "ontology/development/HSWM_W1_REFERENCE_LEAN_2026-10-07.v1.json"
const folder = "ontology/queries/hswm_w1_reference_2026-10-07"
const reportPath = "docs/research/artifacts/hswm_w1_reference_2026-10-07/verification.v1.json"
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const read = (path: string) => readFileSync(resolve(root, path))
const load = (): Bundle => JSON.parse(read(primary).toString())
const byRole = (bundle: Bundle, role: string) => bundle.nodes.filter(node => node.properties["standard_graph_role"] === role)
const compile = (bundle: Bundle) => {
  const result = compileKgBundle([{ sourceId: "w1-reference", rawBytes: Buffer.from(JSON.stringify(bundle)) }], "v2")
  if (Either.isLeft(result)) throw result.left
  return result.right
}
const conforms = (bundle: Bundle) => Effect.runPromise(validateKgShacl(compile(bundle), read(`${folder}/shapes.ttl`)))
const query = async (name: string, bundle = load()) => {
  const result = await Effect.runPromise(queryKgBundle(compile(bundle), read(`${folder}/${name}.rq`).toString()))
  if (typeof result === "boolean") throw new Error("Expected SELECT rows")
  return result
}
const recount = (bundle: Bundle) => {
  bundle.expected_counts = { nodes: bundle.nodes.length, anchors: bundle.anchors.length, relations: bundle.relations.length }
  return bundle
}

it("binds every named theorem and comparison to evidence through standard RDF and SHACL", async () => {
  const bundle = load(), report = JSON.parse(read(reportPath).toString())
  expect((await Effect.runPromise(validateKgShacl(compile(bundle), read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")))).conforms).toBe(true)
  expect((await conforms(bundle)).conforms).toBe(true)
  expect(byRole(bundle, "W1_REFERENCE_THEOREM").map(node => ({ theorem: node.properties["theorem"], axioms: JSON.parse(String(node.properties["axioms_json"])) })).sort((a, b) => String(a.theorem).localeCompare(String(b.theorem)))).toEqual(report.kernel.sources[0].theorem_axioms)
  expect(await query("proofs")).toHaveLength(22)
  expect(await query("comparison")).toHaveLength(6)
  expect(await query("bindings")).toHaveLength(8)
  expect(await query("boundaries")).toHaveLength(4)
  expect(await query("lineage")).toHaveLength(1)
}, 30000)

it("retains exact source-cut hashes, a content-addressed receipt, and unchanged progress selection", () => {
  const bundle = load(), auditRoot = bundle.nodes.find(node => node.uid === bundle.bundle_uid)!
  const revision = String(auditRoot.properties["reviewed_revision"])
  const historical = (path: string) => execFileSync("git", ["show", `${revision}:${path}`], { cwd: root })
  for (const source of byRole(bundle, "EVIDENCE_ARTIFACT")) {
    expect(source.properties["source_revision"]).toBe(revision)
    expect(kgSha256(historical(String(source.properties["source_path"])))).toBe(source.properties["source_sha256"])
  }
  for (const binding of bundle.artifact_bindings) expect(kgSha256(read(binding.path))).toBe(binding.sha256)
  const report = JSON.parse(read(reportPath).toString())
  for (const source of report.source_bindings) expect(kgSha256(historical(source.path))).toBe(source.sha256)
  expect(read(`evidence/hswm_w1_reference_2026-10-07/${kgSha256(read(reportPath))}.json`)).toEqual(read(reportPath))
  const manifest = JSON.parse(read("ontology/workspace/HSWM_WORKSPACE.v1.json").toString())
  expect(manifest.entries.find((entry: { id: string }) => entry.id === "w1-reference").bundle).toBe(primary)
  expect(manifest.entries.find((entry: { id: string }) => entry.id === "progress").bundle).toBe("ontology/development/HSWM_W1_FULL_INSTRUMENT_PROGRESS_2026-10-07.v1.json")
})

it("rejects absent proof evidence and false theorem names", async () => {
  const detached = load(), theorem = byRole(detached, "W1_REFERENCE_THEOREM")[0]!
  detached.relations = detached.relations.filter(edge => !(edge.from_uid === theorem.uid && edge.type === "HAS_SOURCE"))
  expect((await conforms(recount(detached))).conforms).toBe(false)
  expect(await query("proofs", detached)).toHaveLength(21)
  const renamed = load()
  byRole(renamed, "W1_REFERENCE_THEOREM")[0]!.properties["theorem"] = "HSWMFullW1Reference.unproved"
  expect((await conforms(renamed)).conforms).toBe(false)
}, 30000)

it("rejects model, language, parser, and whole-system proof promotion", async () => {
  for (const [key, value] of [["whole_hswm_proved", true], ["natural_language_semantics_proved", true], ["json_parser_proved", true], ["actual_model_requests", 1], ["t5_disposition", "COMPLETE"]] as const) {
    const mutated = load()
    mutated.nodes.find(node => node.uid === mutated.bundle_uid)!.properties[key] = value
    expect((await conforms(mutated)).conforms).toBe(false)
  }
}, 30000)

it("rejects changed comparison coverage and detached assumption boundaries", async () => {
  const changed = load()
  byRole(changed, "W1_REFERENCE_COMPARISON")[0]!.properties["matched_rows"] = 127
  expect((await conforms(changed)).conforms).toBe(false)
  const detached = load(), boundary = byRole(detached, "W1_REFERENCE_BOUNDARY")[0]!
  detached.relations = detached.relations.filter(edge => !(edge.from_uid === boundary.uid && edge.type === "CONSTRAINS"))
  expect((await conforms(recount(detached))).conforms).toBe(false)
  expect(await query("boundaries", detached)).toHaveLength(3)
}, 30000)
