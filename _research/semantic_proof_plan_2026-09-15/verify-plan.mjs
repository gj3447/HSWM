#!/usr/bin/env node
// Read-only verification of this research plan, using the existing native KG tools.
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const root = process.cwd();
const read = (p) => readFile(resolve(root, p));
const digest = (b) => createHash("sha256").update(b).digest("hex");
const json = async (p) => JSON.parse((await read(p)).toString("utf8"));
const check = (ok, message) => { if (!ok) throw new Error(message); };
const sorted = (xs) => [...xs].sort();
const same = (a, b, message) => check(JSON.stringify(sorted(a)) === JSON.stringify(sorted(b)), message);
const planPath = "_research/semantic_proof_plan_2026-09-15/plan.v1.json";
const bundlePath = "ontology/development/HSWM_SEMANTIC_PROOF_WORK_PLAN_2026-09-15.v1.json";
const docPath = "docs/operations/HSWM_SEMANTIC_PROOF_WORK_PLAN_2026-09-15.md";
const rt = "src/hswm/effect-runtime/";
const moduleAt = (p) => import(pathToFileURL(resolve(root, p)).href);
const [{ compileKgBundle }, { queryKgBundle, validateKgShacl }, { Effect, Either }] = await Promise.all([
  moduleAt(rt + "dist/native-kg-bundle-domain.js"),
  moduleAt(rt + "dist/native-kg-standards.js"),
  moduleAt(rt + "node_modules/effect/dist/esm/index.js"),
]);
const run = (e) => Effect.runPromise(e);
const [plan, bundle] = await Promise.all([json(planPath), json(bundlePath)]);
const compile = (value) => {
  const bytes = Buffer.from(JSON.stringify(value));
  const result = compileKgBundle([{ sourceId: "plan", rawBytes: bytes, sha256: digest(bytes), byteLength: bytes.length }], "v2");
  check(Either.isRight(result), "native KG compiler rejection");
  return result.right;
};
const projection = compile(bundle);
const genericShape = await read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl");
const workShape = await read("schemas/HSWM_NEXT_DEVELOPMENT_PLAN_SHACL_1_0.v1.ttl");
for (const shape of [genericShape, workShape]) check((await run(validateKgShacl(projection, shape))).conforms, "SHACL mismatch");
const verifyBindings = async (candidate) => {
  for (const b of candidate.artifact_bindings) check(digest(await read(b.path)) === b.sha256, "source hash mismatch: " + b.path);
};
await verifyBindings(bundle);
const nodes = new Map(bundle.nodes.map(n => [n.uid, n]));
check(nodes.size === bundle.nodes.length, "duplicate UID");
const taskNodes = new Map(bundle.nodes.filter(n => n.properties.standard_graph_role === "WORK_PACKAGE").map(n => [n.properties.task_id, n]));
const rel = (uid, type) => bundle.relations.filter(r => r.from_uid === uid && r.type === type).map(r => r.to_uid);
same([...taskNodes.keys()], plan.tasks.map(t => t.id), "task inventory mismatch");
const decisions = new Map(plan.decisions.map(d => [d.id, d]));
const tasks = new Map(plan.tasks.map(t => [t.id, t]));
const assumed = new Map(plan.assumptions.map(a => [a.id, a]));
for (const t of plan.tasks) {
  const n = taskNodes.get(t.id), p = n.properties;
  for (const k of ["status", "result_status", "track", "task_kind", "failure_action", "verification_method", "planned_output_area", "resource_policy"])
    check(p[k] === t[k], t.id + ": " + k);
  check(p.responsibility_owner === "hswm:research-role:" + t.responsibility_role, t.id + ": owner");
  same(rel(n.uid, "HAS_RESPONSIBILITY_ROLE").map(u => nodes.get(u).properties.name), [t.responsibility_role], t.id + ": role");
  same(rel(n.uid, "USES_INPUT").map(u => nodes.get(u).properties.contract), [t.input_contract], t.id + ": input");
  same(rel(n.uid, "EXPECTS_OUTPUT").map(u => nodes.get(u).properties.contract), [t.output_contract], t.id + ": output");
  same(rel(n.uid, "HAS_CRITERION").map(u => nodes.get(u).properties.criterion), t.acceptance, t.id + ": criteria");
  check(rel(n.uid, "EXPECTS_OUTPUT").every(u => nodes.get(u).properties.status === t.expected_artifact_status), t.id + ": output status");
  check(rel(n.uid, "HAS_CRITERION").every(u => nodes.get(u).properties.status === t.validation_state), t.id + ": criterion status");
  same(rel(n.uid, "DEPENDS_ON").map(u => nodes.get(u).properties.task_id), t.hard_dependencies, t.id + ": dependencies");
  same(rel(n.uid, "HAS_SOURCE").map(u => nodes.get(u).properties.source_path), t.source_refs.map(s => s.path), t.id + ": sources");
  for (const s of t.source_refs) check(digest(await read(s.path)) === s.sha256, t.id + ": input source hash");
  same(rel(n.uid, "ADDRESSES").map(u => nodes.get(u).properties.requirement_id), [t.track], t.id + ": N mapping");
  same(rel(n.uid, "REQUIRES_ASSUMPTION").map(u => nodes.get(u).properties.assumption_id), t.assumptions, t.id + ": assumptions");
  same(rel(n.uid, "REQUIRES_START_DECISION").map(u => nodes.get(u).properties.decision_id), t.required_start_decisions, t.id + ": start conditions");
  same(rel(n.uid, "RESOLVES").map(u => nodes.get(u).properties.decision_id), t.resolves_decisions, t.id + ": resolver");
  same(rel(n.uid, "ADDRESSES_OBLIGATION").map(u => Number(u.split("-CR-").at(-1))), t.cr, t.id + ": CR mapping");
  check(rel(n.uid, "PRESERVES_FRACTAL_LAW").length === t.fcl.length, t.id + ": FCL count");
  check(t.status === "PLANNED" && t.actual_evidence.length === 0 && t.result_status === "NOT_ASSESSED", t.id + ": false progress");
}
for (const n of bundle.nodes.filter(n => n.properties.standard_graph_role === "RESEARCH_ASSUMPTION")) {
  const a = assumed.get(n.properties.assumption_id);
  check(a && n.properties.contract === a.contract && n.properties.status === a.status, "assumption contract mismatch");
  same(rel(n.uid, "RESOLVED_BY").map(u => nodes.get(u).properties.task_id), [a.resolver], "assumption resolver mismatch");
}
for (const n of bundle.nodes.filter(n => n.properties.standard_graph_role === "PLAN_DECISION")) {
  const d = decisions.get(n.properties.decision_id);
  check(d && n.properties.status === d.status && n.properties.required_condition === d.required_condition, "decision contract mismatch");
  same(rel(n.uid, "RESOLVED_BY").map(u => nodes.get(u).properties.task_id), [d.resolver], "decision resolver mismatch");
}
const ownerNodes = new Map();
for (const b of bundle.artifact_bindings.filter(b => b.path.startsWith("ontology/") && b.path.endsWith(".json"))) {
  const d = await json(b.path);
  for (const n of d.nodes ?? []) ownerNodes.set(n.uid, [...(ownerNodes.get(n.uid) ?? []), n]);
}
for (const a of bundle.anchors) {
  const found = ownerNodes.get(a.uid) ?? [];
  check(found.length === 1, "anchor owner ambiguity: " + a.uid);
  check(a.required_labels.every(l => found[0].labels.includes(l)), "anchor labels: " + a.uid);
}
for (const t of plan.tasks) {
  const n = taskNodes.get(t.id);
  same(rel(n.uid, "PRESERVES_FRACTAL_LAW").map(u => Number(ownerNodes.get(u)[0].properties.name.match(/^FCL-(\d+)/)[1])), t.fcl, t.id + ": FCL mapping");
}
const reached = new Set([bundle.bundle_uid]);
for (let size = -1; size !== reached.size;) {
  size = reached.size;
  for (const r of bundle.relations) if (reached.has(r.from_uid)) reached.add(r.to_uid);
}
same([...reached], [...nodes.keys(), ...bundle.anchors.map(a => a.uid)], "unreachable node");
const closure = [];
for (const t of plan.tasks) {
  const seen = new Set(), pending = [...t.hard_dependencies];
  while (pending.length) {
    const id = pending.pop(); check(tasks.has(id), "unknown dependency");
    if (seen.has(id)) continue;
    seen.add(id); pending.push(...tasks.get(id).hard_dependencies);
  }
  check(!seen.has(t.id), "dependency cycle");
  closure.push(...[...seen].map(id => t.id + "|" + id));
}
const qRoot = "ontology/queries/hswm_next_development_plan_2026-09-13/";
const names = ["Q1_ready_roots", "Q2_transitive_dependencies", "Q3_task_contracts", "Q4_open_decisions", "Q5_uncovered_requirements", "Q6_dependency_cycles", "Q7_premature_complete"];
const queries = new Map(await Promise.all(names.map(async n => [n.slice(0, 2), (await read(qRoot + n + ".sparql")).toString()])));
const results = new Map(await Promise.all([...queries].map(async ([id, q]) => [id, await run(queryKgBundle(projection, q))])));
same(results.get("Q1").map(r => r.taskId.value), plan.initial_ready_tasks, "ready work mismatch");
same(results.get("Q2").map(r => r.taskId.value + "|" + r.dependencyId.value), closure, "transitive dependency mismatch");
same(new Set(results.get("Q3").map(r => r.taskId.value)), tasks.keys(), "task contract query missing work");
same(results.get("Q4").map(r => r.decisionId.value), decisions.keys(), "open decisions mismatch");
for (const id of ["Q5", "Q6", "Q7"]) check(results.get(id).length === 0, id + ": plan violation");
const assumptionRows = await run(queryKgBundle(projection, (await read("ontology/queries/hswm_semantic_proof_plan_2026-09-15/task_assumptions.rq")).toString()));
check(assumptionRows.length === plan.tasks.reduce((n, t) => n + t.assumptions.length, 0), "assumption query missing edges");
const clone = () => structuredClone(bundle);
const badHash = clone(); badHash.artifact_bindings[0].sha256 = "0".repeat(64);
let hashRejected = false;
try { await verifyBindings(badHash); } catch { hashRejected = true; }
check(hashRejected, "corrupt source binding accepted");
const missingRole = clone();
missingRole.relations = missingRole.relations.filter(r => !(r.from_uid === taskNodes.get("P00").uid && r.type === "HAS_RESPONSIBILITY_ROLE"));
missingRole.expected_counts.relations = missingRole.relations.length;
check(!(await run(validateKgShacl(compile(missingRole), workShape))).conforms, "missing role accepted");
const cycle = clone();
cycle.relations.push({ from_uid: taskNodes.get("P00").uid, to_uid: taskNodes.get("K01").uid, type: "DEPENDS_ON", authority_class: "SECONDARY_AI", scope: "IN_MEMORY_NEGATIVE_PROBE", status: "INVALID" });
cycle.expected_counts.relations = cycle.relations.length;
check((await run(queryKgBundle(compile(cycle), queries.get("Q6")))).length >= 2, "injected cycle missed");
const premature = clone(); premature.nodes.find(n => n.uid === taskNodes.get("P00").uid).properties.status = "COMPLETE";
check((await run(queryKgBundle(compile(premature), queries.get("Q7")))).some(r => r.taskId.value === "P00"), "premature completion missed");
const lock = await json(rt + "package-lock.json");
for (const t of plan.tools) {
  const p = lock.packages["node_modules/" + t.name];
  check(p.version === t.version && p.integrity === t.integrity && p.license === t.license, "tool pin mismatch");
}
const doc = (await read(docPath)).toString();
for (const t of plan.tasks) check(doc.includes("| " + t.id + " · " + t.title + " | " + t.output_contract + " | " + (t.hard_dependencies.join(", ") || "없음") + " |"), "document task mismatch");
for (const target of [...doc.matchAll(/\]\(([^)]+)\)/g)].map(m => m[1]).filter(t => !t.includes("://"))) await read("docs/operations/" + target.split("#")[0]);
const oldProof = await json("_research/semantic_frontier_proof_v1/lean-verification.v1.json");
check(!oldProof.full_hswm_proved && !oldProof.real_llm_refinement_proved && !plan.full_hswm_proved, "claim ceiling changed");
console.log(JSON.stringify({ schema_version: "hswm-semantic-proof-plan-validation/v1", status: "PASS", checked_on: "2026-09-15", source_bindings: await Promise.all([planPath, bundlePath, docPath, "_research/semantic_proof_plan_2026-09-15/verify-plan.mjs"].map(async path => ({ path, sha256: digest(await read(path)) }))), counts: bundle.expected_counts, source_bindings_checked: bundle.artifact_bindings.length, shacl: ["GENERIC_V2_PASS", "EXISTING_WORK_PLAN_CORE_PASS"], queries: Object.fromEntries([...results].map(([k, v]) => [k, v.length])), assumption_query_rows: assumptionRows.length, initial_ready_tasks: plan.initial_ready_tasks, negative_probes: ["CORRUPT_SOURCE_HASH_REJECTED", "MISSING_ROLE_REJECTED", "CYCLE_DETECTED", "PREMATURE_COMPLETE_DETECTED"], new_lean_proofs: false, real_model_experiments: false, claim_ceiling: "PLAN_STRUCTURE_SOURCE_BINDINGS_AND_QUERY_VALIDATION_ONLY" }, null, 2));
