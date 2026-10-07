import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle, type KgBundleProjection } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const folder = "ontology/queries/hswm_progress_consolidation_2026-10-07"
const bytes = (p: string) => readFileSync(resolve(root, p))
const contract = JSON.parse(bytes("docs/research/artifacts/hswm_progress_consolidation_2026-10-07/contract.v1.json").toString()) as {
  bundle: string; reviewed_revision: string; sources: { id: string; bundle: string; revision: string; sha256: string; validation_report: string }[]
}
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const load = () => [contract.bundle, ...contract.sources.map(s => s.bundle)].map(path => JSON.parse(bytes(path).toString()) as Bundle)
const encode = (value: unknown) => Buffer.from(JSON.stringify(value))
const compile = (bundles = load()): KgBundleProjection => {
  const result = compileKgBundle(bundles.map((b, i) => ({ sourceId: i === 0 ? "progress" : contract.sources[i - 1]!.id, rawBytes: encode(b) })), "v2")
  if (Either.isLeft(result)) throw result.left
  return result.right
}
const query = async (name: string, bundles = load()) => {
  const result = await Effect.runPromise(queryKgBundle(compile(bundles), bytes(`${folder}/${name}.rq`).toString()))
  if (typeof result === "boolean") throw new Error("expected rows")
  return result.map(row => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, value?.["value"] ?? null])))
}
const ofRole = (b: Bundle, role: string) => b.nodes.filter(n => n.properties["standard_graph_role"] === role)
const selected = (b: Bundle, task: string) => ofRole(b, "CURRENT_SELECTION").find(n => n.properties["task_id"] === task)!
const observation = (b: Bundle, task: string) => b.nodes.find(n => n.uid === selected(b, task).properties["selected_observation_uid"])!
const conforms = async (bundles: Bundle[]) => (await Effect.runPromise(validateKgShacl(compile(bundles), bytes(`${folder}/shapes.ttl`)))).conforms

// Cross-node identity/history laws supplement SHACL Core cardinality. They
// validate this curated snapshot, not canonical runtime admission or efficacy.
const coherentSelection = (bundles: Bundle[]): boolean => {
  const b = bundles[0]!, all = bundles.flatMap(b => b.nodes), nodes = new Map(all.map(n => [n.uid, n]))
  const selectors = ofRole(b, "CURRENT_SELECTION"), observations = ofRole(b, "TASK_STATUS_OBSERVATION")
  if (selectors.length !== 9 || new Set(selectors.map(n => n.properties["task_id"])).size !== 9) return false
  for (const s of selectors) {
    const task = nodes.get(String(s.properties["task_uid"])), o = nodes.get(String(s.properties["selected_observation_uid"]))
    if (!task || !o || task.properties["task_id"] !== s.properties["task_id"] || o.properties["task_id"] !== s.properties["task_id"]) return false
    if (task.properties["standard_graph_role"] !== "TASK" || o.properties["standard_graph_role"] !== "TASK_STATUS_OBSERVATION") return false
    if (!b.relations.some(r => r.from_uid === s.uid && r.to_uid === task.uid && r.type === "REFERENCES")) return false
    if (!b.relations.some(r => r.from_uid === s.uid && r.to_uid === o.uid && r.type === "REFERENCES")) return false
    const history = observations.filter(n => n.properties["task_id"] === s.properties["task_id"])
    const orders = history.map(n => Number(n.properties["observation_order"])).sort((a, b) => a - b)
    if (orders.some((order, i) => order !== i) || o.properties["observation_order"] !== orders.length - 1) return false
    for (const current of history) {
      const order = Number(current.properties["observation_order"]), previousUid = current.properties["previous_observation_uid"]
      if (order === 0) { if (previousUid !== undefined) return false; continue }
      const previous = nodes.get(String(previousUid))
      if (!previous || previous.properties["task_id"] !== current.properties["task_id"] || previous.properties["observation_order"] !== order - 1) return false
      if (!b.relations.some(r => r.from_uid === current.uid && r.to_uid === previous.uid && r.type === "REFERENCES")) return false
    }
  }
  return true
}

const coherentSources = (bundles: Bundle[]): boolean => {
  const b = bundles[0]!, occurrences = ofRole(b, "SOURCE_BINDING_OBSERVATION")
  if (occurrences.length !== bundles.slice(1).reduce((sum, source) => sum + source.artifact_bindings.length, 0)) return false
  for (const [index, source] of contract.sources.entries()) {
    const owned = bundles[index + 1]!, selectedOccurrences = occurrences.filter(n => n.properties["source_id"] === source.id)
    if (selectedOccurrences.length !== owned.artifact_bindings.length) return false
    for (const binding of owned.artifact_bindings) {
      const matches = selectedOccurrences.filter(n => n.properties["source_path"] === binding.path)
      if (matches.length !== 1) return false
      const n = matches[0]!, p = n.properties
      if (p["source_bundle_uid"] !== owned.bundle_uid || p["source_revision"] !== source.revision || p["source_sha256"] !== binding.sha256) return false
      if (!b.relations.some(r => r.from_uid === n.uid && r.to_uid === owned.bundle_uid && r.type === "REFERENCES")) return false
    }
    const reports = ofRole(b, "EVIDENCE_ARTIFACT").filter(n => n.properties["source_path"] === source.validation_report)
    if (reports.length !== 1 || reports[0]!.properties["source_revision"] !== source.revision || reports[0]!.properties["source_sha256"] !== kgSha256(bytes(source.validation_report))) return false
  }
  return true
}

it("compiles all four owned graphs, validates actual SHACL and resolves exact task selection", async () => {
  const bundles = load(), projection = compile(bundles)
  expect(projection.descriptor["nodeCount"]).toBe(130)
  expect(projection.descriptor["writeBack"]).toBe("FORBIDDEN")
  for (const shapes of ["schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl", `${folder}/shapes.ttl`]) {
    expect((await Effect.runPromise(validateKgShacl(projection, bytes(shapes)))).conforms).toBe(true)
  }
  expect(coherentSelection(bundles)).toBe(true)
  expect(coherentSources(bundles)).toBe(true)
  const rows = (await query("current")).sort((a, b) => String(a["task"]).localeCompare(String(b["task"])))
  expect(rows.map(r => [r["task"], r["status"], r["completion"]])).toEqual([
    ["T1", "PARTIAL_PRODUCER_PROVED_REFINEMENT_OPEN", "OPEN"], ["T2", "PLANNED", "OPEN"],
    ["T3", "PLANNED", "OPEN"], ["T4", "WAITING", "OPEN"], ["T5", "PREPARED_NOT_RUN", "OPEN"],
    ["T6", "WAITING", "OPEN"], ["T7", "PLANNED", "OPEN"], ["T8", "WAITING", "OPEN"], ["T9", "WAITING", "OPEN"]
  ])
  const prerequisites = Object.fromEntries(rows.map(r => [r["task"], (r["prerequisites"] ?? "").split(",").filter(Boolean).sort()]))
  expect(prerequisites).toEqual({ T1: [], T2: [], T3: ["T1"], T4: ["T1", "T2", "T3"], T5: [], T6: ["T4", "T5"], T7: ["T6"], T8: ["T6"], T9: ["T7", "T8"] })
  for (const row of rows) {
    const task = ofRole(bundles[1]!, "TASK").find(n => n.properties["task_id"] === row["task"])!
    expect(row["criterion"]).toBe(task.properties["completion_criterion"])
    expect(row["next"]).toBe(observation(bundles[0]!, String(row["task"])).properties["next_action"])
  }
}, 30000)

it("retains the exact history, distinguishes evidence roles and preserves negative boundaries", async () => {
  const history = (await query("history")).sort((a, b) => Number(a["order"]) - Number(b["order"]))
  expect(history.map(r => [r["order"], r["status"], r["completion"]])).toEqual([
    ["0", "NEXT", "OPEN"], ["1", "PARTIAL_BOUNDARY_PROVED_REFINEMENT_OPEN", "OPEN"], ["2", "PARTIAL_PRODUCER_PROVED_REFINEMENT_OPEN", "OPEN"]
  ])
  expect(history.map(r => r["revision"])).toEqual(contract.sources.map(s => s.revision))
  const bindings = await query("bindings")
  expect(bindings).toHaveLength(39)
  expect(bindings.filter(r => r["bindingState"] === "CURRENT_MATCH")).toHaveLength(35)
  expect(bindings.filter(r => r["bindingState"] === "HISTORICAL_PIN_DRIFT").map(r => `${r["sourceId"]}:${r["path"]}`).sort()).toEqual([
    "plan:src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.ts", "replay:formal/lakefile.toml",
    "replay:src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.ts", "replay:src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts"
  ])
  for (const r of bindings) {
    expect(r["observedRevision"]).toBe(contract.reviewed_revision)
    expect(r["execution"]).toBe("HISTORICAL_SOURCE_RECORD_NOT_REEXECUTED")
    expect(r["bindingState"]).toBe(r["expectedSha256"] === r["observedSha256"] ? "CURRENT_MATCH" : "HISTORICAL_PIN_DRIFT")
  }
  const evidence = await query("evidence")
  expect(evidence).toHaveLength(13)
  expect(evidence.map(r => r["path"]).sort()).toEqual(load()[3]!.artifact_bindings.slice(0, 13).map(b => b.path).sort())
  expect(evidence.some(r => r["roleName"] === "INSPECTION_ONLY")).toBe(false)
  expect(bindings.filter(r => r["roleName"] === "INSPECTION_ONLY")).toHaveLength(4)
  const boundaries = (await query("boundaries")).sort((a, b) => String(a["id"]).localeCompare(String(b["id"])))
  expect(boundaries.map(r => [r["id"], r["evidence"]])).toEqual([
    ["PS-1", "SUPPORTED_IN_SCOPE"], ["PS-2", "SUPPORTED_IN_SCOPE"], ["PS-3", "UNDERDETERMINED"],
    ["PS-4", "SUPPORTED_IN_SCOPE"], ["PS-5", "UNDERDETERMINED"], ["PS-6", "UNDERDETERMINED"]
  ])
  expect(boundaries.find(r => r["id"] === "PS-6")).toMatchObject({ ceiling: "INTEGRATED_CLAIM_UNJUDGED", negativeSource: "results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md" })
}, 30000)

it.runIf(process.env["HSWM_VERIFY_PROGRESS_HISTORY"] === "1")("verifies all 39 historical artifact occurrences against their exact Git revisions", () => {
  const cache = new Map<string, Buffer>()
  const historical = (revision: string, path: string) => {
    const key = `${revision}:${path}`
    if (!cache.has(key)) cache.set(key, execFileSync("git", ["show", key], { cwd: root, maxBuffer: 16 * 1024 * 1024, timeout: 20000 }))
    return cache.get(key)!
  }
  for (const source of contract.sources) {
    expect(kgSha256(bytes(source.bundle))).toBe(source.sha256)
    expect(historical(source.revision, source.bundle)).toEqual(bytes(source.bundle))
    expect(historical(source.revision, source.validation_report)).toEqual(bytes(source.validation_report))
  }
  for (const n of ofRole(load()[0]!, "SOURCE_BINDING_OBSERVATION")) {
    const p = n.properties
    expect(kgSha256(historical(String(p["source_revision"]), String(p["source_path"])))).toBe(p["source_sha256"])
    expect(kgSha256(historical(String(p["observed_revision"]), String(p["source_path"])))).toBe(p["observed_sha256"])
  }
})

it("refuses missing or duplicate current selection, false completion and efficacy promotion", async () => {
  const missing = load(), primary = missing[0]!, selector = selected(primary, "T1")
  primary.relations = primary.relations.filter(r => !(r.to_uid === selector.uid && r.type === "HAS_CONCEPT"))
  primary.expected_counts["relations"] = primary.relations.length
  expect(await conforms(missing)).toBe(false)
  const duplicate = load(), copied = structuredClone(selected(duplicate[0]!, "T1")); copied.uid += "-copy"
  duplicate[0]!.nodes.push(copied)
  duplicate[0]!.relations.push({ from_uid: duplicate[0]!.bundle_uid, to_uid: copied.uid, type: "HAS_CONCEPT", authority_class: "SECONDARY_AI", scope: "TEST_MUTATION", status: "PROPOSED" })
  duplicate[0]!.expected_counts["nodes"] = duplicate[0]!.nodes.length; duplicate[0]!.expected_counts["relations"] = duplicate[0]!.relations.length
  expect(await conforms(duplicate)).toBe(false)
  const completed = load(); observation(completed[0]!, "T1").properties["completion_disposition"] = "COMPLETE"
  expect(await conforms(completed)).toBe(false)
  const efficacy = load(); efficacy[1]!.nodes.find(n => n.properties["assesses_claim_uid"] === "sym:Concept:hswm-progress-ps-6-2026-10-06-v1")!.properties["evidence_disposition"] = "SUPPORTED_IN_SCOPE"
  expect(await conforms(efficacy)).toBe(false)
}, 30000)

it("rejects stale selectors and cyclic observation history while permitting ordinary graph cycles", () => {
  const stale = load(), b = stale[0]!, sel = selected(b, "T1"), old = ofRole(b, "TASK_STATUS_OBSERVATION").find(n => n.properties["task_id"] === "T1" && n.properties["observation_order"] === 1)!
  const current = sel.properties["selected_observation_uid"]
  sel.properties["selected_observation_uid"] = old.uid
  b.relations.find(r => r.from_uid === sel.uid && r.to_uid === current)!.to_uid = old.uid
  expect(coherentSelection(stale)).toBe(false)
  const cyclic = load(), c = cyclic[0]!, first = ofRole(c, "TASK_STATUS_OBSERVATION").find(n => n.properties["task_id"] === "T1" && n.properties["observation_order"] === 0)!
  first.properties["previous_observation_uid"] = observation(c, "T1").uid
  expect(coherentSelection(cyclic)).toBe(false)
  expect(coherentSelection(load())).toBe(true) // Claim/Decision cycles are intentional.
})

it("binds exact task identity, declared source ownership and only the selected T1 history", async () => {
  const wrongTask = load(), b = wrongTask[0]!
  selected(b, "T1").properties["task_uid"] = observation(b, "T1").uid
  expect(coherentSelection(wrongTask)).toBe(false)
  expect((await query("current", wrongTask)).some(r => r["task"] === "T1")).toBe(false)
  expect((await query("next", wrongTask)).some(r => r["task"] === "T1")).toBe(false)
  observation(b, "T1").properties["completion_disposition"] = "COMPLETE"
  observation(b, "T3").properties["work_ready"] = true
  expect((await query("next", wrongTask)).some(r => r["task"] === "T3")).toBe(false)
  const wrongSource = load()
  const plan = ofRole(wrongSource[0]!, "SOURCE_BINDING_OBSERVATION").find(n => n.properties["source_id"] === "plan")!
  const adapter = ofRole(wrongSource[0]!, "SOURCE_BINDING_OBSERVATION").find(n => n.properties["source_id"] === "adapter")!
  plan.properties["source_id"] = "adapter"; adapter.properties["source_id"] = "plan"
  expect(coherentSources(wrongSource)).toBe(false)
  const unrelated = load(), copy = structuredClone(observation(unrelated[0]!, "T1")); copy.uid += "-unrelated"
  unrelated[0]!.nodes.push(copy); unrelated[0]!.expected_counts["nodes"] = unrelated[0]!.nodes.length
  expect(await query("history", unrelated)).toEqual(await query("history"))
}, 30000)

it("selects only scoped ready work and never treats missing prerequisite evidence as completion", async () => {
  expect((await query("next")).map(r => r["task"])).toEqual(["T1", "T2"])
  const blocked = load(); observation(blocked[0]!, "T4").properties["work_ready"] = true
  expect((await query("next", blocked)).map(r => r["task"])).toEqual(["T1", "T2"])
  // T3 has only T1 as a prerequisite: its absence alone must block admission.
  observation(blocked[0]!, "T3").properties["work_ready"] = true
  const s = selected(blocked[0]!, "T1")
  blocked[0]!.relations = blocked[0]!.relations.filter(r => !(r.to_uid === s.uid && r.type === "HAS_CONCEPT"))
  blocked[0]!.expected_counts["relations"] = blocked[0]!.relations.length
  expect((await query("next", blocked)).map(r => r["task"])).toEqual(["T2"])
  const cycle = await Effect.runPromise(queryKgBundle(compile(), "PREFIX r:<https://hswm.invalid/kg-bundle-rdf/v1/rel/> ASK { ?task r:REQUIRES+ ?task }"))
  expect(cycle).toBe(false)
}, 30000)
