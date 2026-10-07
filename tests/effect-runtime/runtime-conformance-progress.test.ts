import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { compileKgBundle, kgSha256, type KgBundle, type KgBundleProjection } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../..")
const folder = "ontology/queries/hswm_runtime_conformance_2026-10-07"
const revision = (): string => String(role(load()[0]!, "PROGRESS_VIEW")[0]!.properties["reviewed_revision"])
const primaryPath = "ontology/development/HSWM_RUNTIME_CONFORMANCE_PROGRESS_2026-10-07.v1.json"
const sourcePaths = [
  "ontology/development/HSWM_PROGRESS_PLAN_2026-10-06.v1.json",
  "ontology/development/HSWM_JOURNAL_REPLAY_PROGRESS_2026-10-06.v1.json",
  "ontology/development/HSWM_JOURNAL_ADAPTER_PROGRESS_2026-10-06.v1.json",
  "ontology/development/HSWM_PROGRESS_CONSOLIDATION_2026-10-07.v1.json",
  "ontology/development/HSWM_PREFLIGHT_REFINEMENT_PROGRESS_2026-10-07.v1.json",
] as const
const bytes = (path: string) => readFileSync(resolve(root, path))
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
type Bundle = Mutable<KgBundle>
const load = () => [primaryPath, ...sourcePaths].map(path => JSON.parse(bytes(path).toString()) as Bundle)
const encode = (value: unknown) => Buffer.from(JSON.stringify(value))
const compile = (bundles = load()): KgBundleProjection => {
  const result = compileKgBundle(bundles.map((bundle, index) => ({ sourceId: ["progress", "plan", "replay", "adapter", "consolidation", "preflight"][index]!, rawBytes: encode(bundle) })), "v2")
  if (Either.isLeft(result)) throw result.left
  return result.right
}
const query = async (name: string, bundles = load()) => {
  const result = await Effect.runPromise(queryKgBundle(compile(bundles), bytes(`${folder}/${name}.rq`).toString()))
  if (typeof result === "boolean") throw new Error("expected rows")
  return result.map(row => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, value?.["value"] ?? null])))
}
const role = (bundle: Bundle, name: string) => bundle.nodes.filter(node => node.properties["standard_graph_role"] === name)
const selection = (bundle: Bundle, task: string) => role(bundle, "CURRENT_SELECTION").find(node => node.properties["task_id"] === task)!
const observation = (bundles: Bundle[], task: string) => {
  const uid = selection(bundles[0]!, task).properties["selected_observation_uid"]
  return bundles.flatMap(bundle => bundle.nodes).find(node => node.uid === uid)!
}
const conforms = async (bundles: Bundle[]) => (await Effect.runPromise(validateKgShacl(compile(bundles), bytes(`${folder}/shapes.ttl`)))).conforms

it("selects the source-bound runtime conformance view without changing historical views", async () => {
  const bundles = load(), primary = bundles[0]!
  expect(compile(bundles).descriptor["writeBack"]).toBe("FORBIDDEN")
  expect((await Effect.runPromise(validateKgShacl(compile(bundles), bytes("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")))).conforms).toBe(true)
  expect(await conforms(bundles)).toBe(true)
  const selectors = role(primary, "CURRENT_SELECTION")
  expect(selectors).toHaveLength(9)
  expect(new Set(selectors.map(node => node.properties["task_id"])).size).toBe(9)
  const all = new Map(bundles.flatMap(bundle => bundle.nodes).map(node => [node.uid, node]))
  for (const selector of selectors) {
    const task = all.get(String(selector.properties["task_uid"])), selected = all.get(String(selector.properties["selected_observation_uid"]))
    expect(task?.properties["standard_graph_role"]).toBe("TASK")
    expect(task?.properties["task_id"]).toBe(selector.properties["task_id"])
    expect(selected?.properties["task_id"]).toBe(selector.properties["task_id"])
    expect(primary.relations.some(edge => edge.from_uid === selector.uid && edge.to_uid === task?.uid && edge.type === "REFERENCES")).toBe(true)
    expect(primary.relations.some(edge => edge.from_uid === selector.uid && edge.to_uid === selected?.uid && edge.type === "REFERENCES")).toBe(true)
  }
  expect(observation(bundles, "T1").properties["observation_order"]).toBe(4)
  expect(observation(bundles, "T2").properties["observation_order"]).toBe(2)
}, 30000)

it("answers current, fixed T1 history, direct evidence, next work, and boundaries", async () => {
  const current = (await query("current")).sort((a, b) => String(a["task"]).localeCompare(String(b["task"])))
  expect(current.map(row => [row["task"], row["status"], row["completion"]])).toEqual([
    ["T1", "DECODE_REPLAY_ORIGINAL_CRITERION_VALIDATED", "COMPLETE"], ["T2", "SIGNED_PERMIT_ORIGINAL_CRITERION_VALIDATED", "COMPLETE"],
    ["T3", "V2_PROCESS_CRASH_AND_RACE_VALIDATED", "COMPLETE"], ["T4", "SAME_RUN_TRACE_RETAINED_AND_QUERYABLE", "COMPLETE"], ["T5", "NOT_READY_CURRENT_MODEL_BINDING_UNESTABLISHED", "OPEN"],
    ["T6", "WAITING", "OPEN"], ["T7", "PLANNED", "OPEN"], ["T8", "WAITING", "OPEN"], ["T9", "WAITING", "OPEN"],
  ])
  const history = (await query("history")).sort((a, b) => Number(a["order"]) - Number(b["order"]))
  expect(history.map(row => [row["order"], row["status"]])).toEqual([
    ["0", "NEXT"], ["1", "PARTIAL_BOUNDARY_PROVED_REFINEMENT_OPEN"], ["2", "PARTIAL_PRODUCER_PROVED_REFINEMENT_OPEN"], ["3", "PARTIAL_READ_SET_VALIDATION_PROVED_REFINEMENT_OPEN"], ["4", "DECODE_REPLAY_ORIGINAL_CRITERION_VALIDATED"],
  ])
  const bindings = await query("bindings")
  expect(bindings).toHaveLength(13)
  expect(bindings.every(row => row["revision"] === revision())).toBe(true)
  expect(bindings.some(row => row["roleName"] === "VALIDATION_REPORT")).toBe(true)
  const evidence = await query("evidence")
  expect(evidence.filter(row => row["task"] === "T1")).toHaveLength(5)
  expect(evidence.filter(row => row["task"] === "T2")).toHaveLength(6)
  expect(evidence.filter(row => row["task"] === "T3")).toHaveLength(5)
  expect(evidence.filter(row => row["task"] === "T4")).toHaveLength(4)
  expect(evidence.filter(row => row["task"] === "T5")).toHaveLength(2)
  expect((await query("blocked")).map(row => [row["task"], row["prerequisite"]]).sort()).toEqual([
    ["T6", "T5"], ["T7", "T6"], ["T8", "T6"], ["T9", "T7"], ["T9", "T8"]
  ])
  expect((await query("next")).map(row => row["task"])).toEqual([])
  const boundaries = (await query("boundaries")).sort((a, b) => String(a["id"]).localeCompare(String(b["id"])))
  expect(boundaries.map(row => [row["id"], row["evidence"]])).toEqual([
    ["PS-1", "SUPPORTED_IN_SCOPE"], ["PS-2", "SUPPORTED_IN_SCOPE"], ["PS-3", "UNDERDETERMINED"],
    ["PS-4", "SUPPORTED_IN_SCOPE"], ["PS-5", "UNDERDETERMINED"], ["PS-6", "UNDERDETERMINED"],
  ])
  expect(boundaries.find(row => row["id"] === "PS-6")?.["ceiling"]).toBe("INTEGRATED_CLAIM_UNJUDGED")
}, 30000)

it("rejects selector loss, duplicate task selection, completion promotion, and keeps incomplete prerequisites blocked", async () => {
  const missing = load(), primary = missing[0]!, t1 = selection(primary, "T1")
  primary.relations = primary.relations.filter(edge => !(edge.from_uid === primary.bundle_uid && edge.to_uid === t1.uid && edge.type === "HAS_CONCEPT"))
  primary.expected_counts["relations"] = primary.relations.length
  expect(await conforms(missing)).toBe(false)
  const duplicate = load(), duplicatePrimary = duplicate[0]!, copied = structuredClone(selection(duplicatePrimary, "T1"))
  copied.uid += "-copy"; duplicatePrimary.nodes.push(copied)
  duplicatePrimary.relations.push({ from_uid: duplicatePrimary.bundle_uid, to_uid: copied.uid, type: "HAS_CONCEPT", authority_class: "SECONDARY_AI", scope: "TEST_MUTATION", status: "PROPOSED" })
  duplicatePrimary.expected_counts["nodes"] = duplicatePrimary.nodes.length; duplicatePrimary.expected_counts["relations"] = duplicatePrimary.relations.length
  expect(await conforms(duplicate)).toBe(false)
  const promoted = load(); observation(promoted, "T5").properties["completion_disposition"] = "COMPLETE"
  expect(await conforms(promoted)).toBe(false)
  const blocked = load(); observation(blocked, "T6").properties["work_ready"] = true
  // A completed task is never next work even if its readiness flag is corrupted.
  observation(blocked, "T1").properties["work_ready"] = true
  expect((await query("next", blocked)).map(row => row["task"])).toEqual([])
}, 30000)

it("pins source evidence to the code revision and graph files to their immutable publication bytes", () => {
  const primary = load()[0]!
  const artifacts = role(primary, "EVIDENCE_ARTIFACT")
  expect(artifacts).toHaveLength(13)
  for (const artifact of artifacts) {
    const properties = artifact.properties
    expect(properties["source_revision"]).toBe(revision())
    const path = String(properties["source_path"]), historical = execFileSync("git", ["show", `${revision()}:${path}`], { cwd: root, timeout: 20000, maxBuffer: 16 * 1024 * 1024 })
    expect(kgSha256(historical)).toBe(properties["source_sha256"])
    expect(kgSha256(bytes(path))).toBe(properties["source_sha256"])
  }
  for (const binding of primary.artifact_bindings) {
    const published = execFileSync("git", ["show", `b739cc8342ec3314962a9c10d801a1d91ac2af81:${binding.path}`], { cwd: root, timeout: 20000, maxBuffer: 16 * 1024 * 1024 })
    expect(kgSha256(published)).toBe(binding.sha256)
  }
}, 30000)

it("does not cross a mismatched history hop or infer a missing prerequisite as complete", async () => {
  const history = load(), selected = observation(history, "T1")
  const previous = history.flatMap(b => b.nodes).find(n => n.uid === selected.properties["previous_observation_uid"])!
  previous.properties["task_id"] = "T2"
  expect((await query("history", history)).map(row => row["order"])).toEqual(["4"])
  const missing = load(), t6 = selection(missing[0]!, "T6")
  observation(missing, "T7").properties["work_ready"] = true
  missing[0]!.relations = missing[0]!.relations.filter(edge => !(edge.from_uid === missing[0]!.bundle_uid && edge.to_uid === t6.uid))
  missing[0]!.expected_counts["relations"] = missing[0]!.relations.length
  expect((await query("next", missing)).map(row => row["task"])).not.toContain("T7")
  expect((await query("blocked", missing)).find(row => row["task"] === "T7")).toMatchObject({ prerequisiteStatus: "UNOBSERVED" })
  const swapped = load(); selection(swapped[0]!, "T9").properties["task_id"] = "T8"
  expect(await conforms(swapped)).toBe(false)
}, 30000)

it("queries exact retained same-run bytes and refuses a detached trace source", async () => {
  const tracePath = "docs/research/artifacts/hswm_runtime_conformance_2026-10-07/same-run-trace.v1.json"
  const trace = JSON.parse(bytes(tracePath).toString()) as { source_revision: string; source_sha256: Record<string, string> }
  const rows = await query("trace")
  expect(rows).toHaveLength(10)
  const stages = new Map(rows.map(row => [String(row["stage"]), Buffer.from(String(row["bytesBase64"]), "base64")]))
  for (const row of rows) {
    const raw = stages.get(String(row["stage"]))!
    expect(kgSha256(raw)).toBe(row["bytesSha256"])
    expect(raw.byteLength).toBe(Number(row["byteLength"]))
    expect(row["codeRevision"]).toBe(trace.source_revision)
    expect(row["traceSha256"]).toBe(kgSha256(bytes(tracePath)))
    expect(row["leanAccepted"]).toBe("true")
  }
  const response = JSON.parse(stages.get("lean-response")!.toString()) as { decision: string; request: unknown }
  expect(response.decision).toBe("accepted")
  expect(response.request).toEqual(JSON.parse(stages.get("lean-request")!.toString()))
  expect(stages.get("recovered-state")).toEqual(stages.get("post-state"))
  for (const [path, digest] of Object.entries(trace.source_sha256)) {
    const committed = execFileSync("git", ["show", `${trace.source_revision}:${path}`], { cwd: root, timeout: 20000, maxBuffer: 16 * 1024 * 1024 })
    expect(kgSha256(committed)).toBe(digest)
  }
  const detached = load(), run = role(detached[0]!, "EXECUTION_TRACE_RUN")[0]!
  run.properties["trace_artifact_uid"] = "sym:AbstractNode:wrong-trace"
  expect(await query("trace", detached)).toEqual([])
  const missing = load(), run2 = role(missing[0]!, "EXECUTION_TRACE_RUN")[0]!, byte = role(missing[0]!, "TRACE_BYTE_EVIDENCE")[0]!
  missing[0]!.relations = missing[0]!.relations.filter(edge => !(edge.from_uid === run2.uid && edge.to_uid === byte.uid))
  missing[0]!.expected_counts["relations"] = missing[0]!.relations.length
  expect(await conforms(missing)).toBe(false)
}, 30000)
