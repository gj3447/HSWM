#!/usr/bin/env node
/** Offline verifier for the source-bound next-development plan bundle. */
import { createHash } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve, relative, join } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { createRequire } from "node:module";

const fail = (message) => { throw new Error(message); };
const execFile = promisify(execFileCallback);
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const text = (bytes) => new TextDecoder("utf-8", { fatal: true }).decode(bytes);
const json = async (file) => JSON.parse(text(await readFile(file)));
const fileBinding = async (root, path) => {
  const bytes = await readFile(join(root, path));
  return { path, sha256: digest(bytes), byte_length: bytes.byteLength };
};
const expect = (condition, message) => { if (!condition) fail(message); };
const asMap = (items, key) => new Map(items.map(item => [item[key], item]));
const parseArgs = (args) => {
  const root = resolve(process.cwd());
  const values = { root, bundle: undefined, projection: undefined };
  for (let i = 0; i < args.length; i += 2) {
    const flag = args[i], value = args[i + 1];
    if (!value || !["--root", "--bundle", "--projection"].includes(flag)) fail("usage: verify-plan.mjs [--root PATH] [--bundle PATH] [--projection PATH]");
    values[flag.slice(2)] = resolve(root, value);
  }
  return values;
};

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  const planPath = join(args.root, "_research/native_development_plan_2026-09-13/development-plan.v1.json");
  const catalogPath = join(args.root, "_research/native_development_plan_2026-09-13/source-catalog.v1.json");
  const bundlePath = args.bundle ?? join(args.root, "ontology/development/HSWM_NEXT_DEVELOPMENT_GRAPH_PLAN_2026-09-13.v1.json");
  const projectionRoot = args.projection ?? join(args.root, "ontology/projections/hswm_next_development_plan_2026-09-13");
  const plan = await json(planPath);
  const catalog = await json(catalogPath);
  const bundle = await json(bundlePath);
  const runtimeRoot = join(args.root, "src/hswm/effect-runtime");
  const [{ compileKgBundle, kgSha256 }, { queryKgBundle, validateKgShacl }, { Effect, Either }] = await Promise.all([
    import(pathToFileURL(join(runtimeRoot, "dist/native-kg-bundle-domain.js")).href),
    import(pathToFileURL(join(runtimeRoot, "dist/native-kg-standards.js")).href),
    import(pathToFileURL(join(runtimeRoot, "node_modules/effect/dist/esm/index.js")).href)
  ]);
  const sourceBytes = await readFile(bundlePath);
  const compiled = compileKgBundle([{ sourceId: "plan", rawBytes: sourceBytes, sha256: digest(sourceBytes), byteLength: sourceBytes.byteLength }], "v2");
  expect(Either.isRight(compiled), `bundle compile failed: ${Either.isLeft(compiled) ? compiled.left.detail : "unknown"}`);
  const projection = compiled.right;
  const run = (effect) => Effect.runPromise(effect);
  const knownNativeReportingGaps = [];
  const rawConditionalRefusal = async (candidate, shapeBytes, name, error) => {
    expect(["claimed-output-without-evidence", "satisfied-decision-without-evidence"].includes(name), `${name}: unqualified raw-engine fallback`);
    expect(String(error).includes("Cannot read properties of null") && String(error).includes("termType"), `${name}: different native failure`);
    const requireRuntime = createRequire(join(runtimeRoot, "package.json"));
    const { Parser, Store, DataFactory } = requireRuntime("n3");
    const { loadKgVendorEngines } = await import(pathToFileURL(join(runtimeRoot, "dist/native-kg-vendor.js")).href);
    const { SHACLValidator } = await run(loadKgVendorEngines);
    const quads = new Parser({ format: "N-Quads" }).parse(text(candidate.nquads));
    const dataset = new Store(quads.map(q => DataFactory.quad(q.subject, q.predicate, q.object)));
    const validator = new SHACLValidator(new Store(new Parser({ format: "Turtle" }).parse(text(shapeBytes))), { importGraph: () => Promise.reject(new Error("imports forbidden")) });
    const report = await validator.validate(dataset);
    expect(report.conforms === false && report.results.length === 1, `${name}: raw engine did not reject exactly one conditional violation`);
    const result = report.results[0];
    expect(result.path === null && result.sourceConstraintComponent.value === "http://www.w3.org/ns/shacl#OrConstraintComponent", `${name}: different raw violation`);
    knownNativeReportingGaps.push({ probe: name, native_status: "REPORT_SERIALIZATION_DEFECT", raw_engine: "rdf-validate-shacl@0.6.5", raw_conforms: report.conforms, path: result.path, component: result.sourceConstraintComponent.value });
    return { conforms: false };
  };
  const queryRoot = join(args.root, "ontology/queries/hswm_next_development_plan_2026-09-13");
  const queryFiles = ["Q1_ready_roots.sparql", "Q2_transitive_dependencies.sparql", "Q3_task_contracts.sparql", "Q4_open_decisions.sparql", "Q5_uncovered_requirements.sparql", "Q6_dependency_cycles.sparql", "Q7_premature_complete.sparql", "Q8_research_nonresearch_dependencies.sparql", "Q9_tools_missing_pins.sparql"];
  const queries = new Map(await Promise.all(queryFiles.map(async name => [name.slice(0, 2), text(await readFile(join(queryRoot, name)))])));
  const shapes = await Promise.all(["schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl", "schemas/HSWM_NEXT_DEVELOPMENT_PLAN_SHACL_1_0.v1.ttl"].map(path => readFile(join(args.root, path))));
  const queryResults = new Map(await Promise.all([...queries].map(async ([id, query]) => [id, await run(queryKgBundle(projection, query))])));
  const shapeResults = await Promise.all(shapes.map(bytes => run(validateKgShacl(projection, bytes))));
  expect(shapeResults.every(result => result.conforms), "generic or plan SHACL does not conform");
  for (const id of ["Q5", "Q6", "Q7", "Q8", "Q9"]) expect(Array.isArray(queryResults.get(id)) && queryResults.get(id).length === 0, `${id} expected no rows`);

  const taskById = asMap(plan.tasks, "id"), decisionById = asMap(plan.decisions, "id"), requirementById = asMap(plan.requirements, "id");
  expect(taskById.size === plan.tasks.length && decisionById.size === plan.decisions.length && requirementById.size === plan.requirements.length, "duplicate plan IDs");
  const nodes = asMap(bundle.nodes, "uid");
  const taskNodes = new Map(bundle.nodes.filter(n => n.properties.task_id).map(n => [n.properties.task_id, n]));
  const decisionNodes = new Map(bundle.nodes.filter(n => n.properties.decision_id).map(n => [n.properties.decision_id, n]));
  const requirementNodes = new Map(bundle.nodes.filter(n => n.properties.requirement_id).map(n => [n.properties.requirement_id, n]));
  expect(taskNodes.size === taskById.size && decisionNodes.size === decisionById.size && requirementNodes.size === requirementById.size, "KG ID node counts disagree with plan");
  const rel = (from, type) => bundle.relations.filter(edge => edge.from_uid === from && edge.type === type).map(edge => edge.to_uid);
  for (const [id, task] of taskById) {
    const node = taskNodes.get(id); expect(node, `missing KG task ${id}`);
    for (const key of ["status", "track", "claim_ceiling", "objective", "failure_action", "assignment_status"]) expect(node.properties[key] === task[key], `${id}: ${key} mismatch`);
    expect(rel(node.uid, "EXPECTS_OUTPUT").every(uid => nodes.get(uid)?.properties.status === task.expected_artifact_status), `${id}: output state`);
    expect(rel(node.uid, "HAS_CRITERION").every(uid => nodes.get(uid)?.properties.status === task.validation_state), `${id}: criterion state`);
    for (const [type, value] of [["HAS_RESPONSIBILITY_ROLE", task.responsibility_role], ["USES_INPUT", task.input_contract], ["EXPECTS_OUTPUT", task.output_contract]]) {
      expect(rel(node.uid, type).some(uid => nodes.get(uid)?.properties.contract === value || nodes.get(uid)?.properties.name === value), `${id}: ${type} content missing`);
    }
    expect(JSON.stringify(rel(node.uid, "HAS_CRITERION").map(uid => nodes.get(uid)?.properties.criterion).sort()) === JSON.stringify([...task.acceptance].sort()), `${id}: criterion set`);
    expect(JSON.stringify(rel(node.uid, "HAS_SOURCE").map(uid => nodes.get(uid)?.properties.source_path).sort()) === JSON.stringify([...new Set(task.source_refs.map(source => source.path))].sort()), `${id}: source edge set`);
    expect(JSON.stringify(rel(node.uid, "ADDRESSES").map(uid => nodes.get(uid)?.properties.requirement_id).sort()) === JSON.stringify([...task.addresses].sort()), `${id}: requirement edge set`);
    expect(rel(node.uid, "DEPENDS_ON").map(uid => nodes.get(uid)?.properties.task_id).sort().join("|") === [...task.hard_dependencies].sort().join("|"), `${id}: hard dependency set`);
    expect(rel(node.uid, "REQUIRES_START_DECISION").map(uid => nodes.get(uid)?.properties.decision_id).sort().join("|") === [...(task.required_start_decisions ?? [])].sort().join("|"), `${id}: start-decision edge set`);
    expect(rel(node.uid, "REQUIRES_COMPLETION_DECISION").map(uid => nodes.get(uid)?.properties.decision_id).sort().join("|") === [...(task.required_completion_decisions ?? [])].sort().join("|"), `${id}: completion-decision edge set`);
    expect(rel(node.uid, "RESOLVES").map(uid => nodes.get(uid)?.properties.decision_id).sort().join("|") === [...(task.resolves_decisions ?? [])].sort().join("|"), `${id}: resolves-decision edge set`);
  }
  for (const [id, decision] of decisionById) {
    const node = decisionNodes.get(id); expect(node, `missing KG decision ${id}`);
    expect(node.properties.status === decision.status && node.properties.required_condition === decision.required_condition, `${id}: decision contract`);
    expect(rel(node.uid, "RESOLVED_BY").map(uid => nodes.get(uid)?.properties.task_id).join("|") === decision.resolver, `${id}: resolver edge`);
  }
  const sourceNodes = new Map(bundle.nodes.filter(node => node.properties.standard_graph_role === "ENGINEERING_SOURCE").map(node => [node.properties.source_path, node]));
  const lock = await json(join(runtimeRoot, "package-lock.json"));
  for (const tool of plan.tools) {
    const node = bundle.nodes.find(node => node.properties.package_name === tool.name);
    expect(node, `tool missing: ${tool.name}`);
    for (const [property, expected] of [["package_version", tool.version], ["package_integrity", tool.integrity], ["license", tool.license], ["authority_class", tool.authority_class]]) expect(node.properties[property] === expected, `tool ${tool.name}: ${property}`);
    const installedPin = lock.packages["node_modules/" + tool.name];
    expect(installedPin.version === tool.version && installedPin.integrity === tool.integrity, `tool lock mismatch: ${tool.name}`);
  }
  for (const source of catalog.sources) {
    const node = sourceNodes.get(source.path);
    expect(node && node.properties.sha256 === source.sha256 && node.properties.byte_length === source.byte_length && node.properties.source_revision === source.source_revision, `source catalog node mismatch: ${source.path}`);
  }
  const ready = plan.tasks.filter(task => task.status === "PLANNED" && task.hard_dependencies.every(id => taskById.get(id)?.status === "COMPLETE") && (task.required_start_decisions ?? []).every(id => decisionById.get(id)?.status === "SATISFIED")).map(task => task.id).sort();
  const q1 = queryResults.get("Q1").map(row => row.taskId.value).sort();
  expect(JSON.stringify(ready) === JSON.stringify(q1), "Q1 ready task set disagrees with plan calculation");
  const q4 = queryResults.get("Q4").map(row => row.decisionId.value).sort();
  expect(JSON.stringify(q4) === JSON.stringify(plan.decisions.filter(d => d.status === "OPEN").map(d => d.id).sort()), "Q4 open decisions disagree with plan");
  const expectedClosure = [];
  for (const task of plan.tasks) {
    const visited = new Set(), pending = [...task.hard_dependencies];
    while (pending.length) {
      const id = pending.pop(); if (visited.has(id)) continue;
      expect(taskById.has(id), `unknown dependency ${id}`);
      visited.add(id); pending.push(...taskById.get(id).hard_dependencies);
    }
    expect(!visited.has(task.id), `plan dependency cycle at ${task.id}`);
    expectedClosure.push(...[...visited].map(id => `${task.id}|${id}`));
  }
  const observedClosure = queryResults.get("Q2").map(row => `${row.taskId.value}|${row.dependencyId.value}`);
  expect(JSON.stringify(observedClosure.sort()) === JSON.stringify(expectedClosure.sort()), "Q2 differs from independently traversed dependency closure");
  expect(JSON.stringify([...new Set(queryResults.get("Q3").map(row => row.taskId.value))].sort()) === JSON.stringify([...taskById.keys()].sort()), "Q3 misses task contracts");

  const expectedBindings = [...catalog.sources.map(source => source.path).filter(path => !path.startsWith(".")), relative(args.root, catalogPath)].sort();
  const bindingByPath = asMap(bundle.artifact_bindings, "path");
  expect(JSON.stringify([...bindingByPath.keys()].sort()) === JSON.stringify(expectedBindings), "bundle artifact_bindings do not exactly cover the catalog (leading-dot sources are catalog/source-node only)");
  for (const path of expectedBindings) {
    const actual = await fileBinding(args.root, path);
    expect(bindingByPath.get(path)?.sha256 === actual.sha256, `artifact binding digest mismatch: ${path}`);
  }
  for (const pin of catalog.sources) {
    const actual = await fileBinding(args.root, pin.path);
    expect(actual.sha256 === pin.sha256 && actual.byte_length === pin.byte_length, `current catalog source pin mismatch: ${pin.path}`);
    if (/^[0-9a-f]{40}$/.test(pin.source_revision)) {
      const historical = Buffer.from((await execFile("git", ["show", `${pin.source_revision}:${pin.path}`], { cwd: args.root, encoding: "buffer" })).stdout);
      expect(digest(historical) === pin.sha256 && historical.byteLength === pin.byte_length, `baseline git source pin mismatch: ${pin.path}`);
    }
  }
  const expectedProjection = [{ name: "dataset.nq", bytes: projection.nquads }, { name: "descriptor.json", bytes: new TextEncoder().encode(JSON.stringify(projection.descriptor, null, 2) + "\n") }, { name: "provenance.jsonld", bytes: projection.provO }];
  for (const expected of expectedProjection) {
    const actual = await readFile(join(projectionRoot, expected.name));
    expect(Buffer.compare(actual, expected.bytes) === 0, `projection byte mismatch: ${expected.name}`);
  }

  const recount = candidate => { candidate.expected_counts = { ...candidate.expected_counts, nodes: candidate.nodes.length, anchors: candidate.anchors.length, relations: candidate.relations.length }; };
  const validateProbe = async (name, mutate, expected) => {
    const clone = structuredClone(bundle); mutate(clone);
    recount(clone);
    const bytes = new TextEncoder().encode(JSON.stringify(clone));
    const result = compileKgBundle([{ sourceId: "plan", rawBytes: bytes, sha256: kgSha256(bytes), byteLength: bytes.byteLength }], "v2");
    if (Either.isLeft(result)) { expect(expected === "compile", `${name}: compiler rejected before expected ${expected}`); return name + ":compile"; }
    if (expected === "compile") fail(`${name}: compiler unexpectedly accepted`);
    const candidate = result.right;
    if (expected === "shacl") {
      const reports = await Promise.all(shapes.map(async bytes => {
        try { return await run(validateKgShacl(candidate, bytes)); }
        catch (error) { return await rawConditionalRefusal(candidate, bytes, name, error); }
      }));
      expect(reports.some(report => !report.conforms), `${name}: SHACL unexpectedly conforms`);
      return name + (knownNativeReportingGaps.some(gap => gap.probe === name) ? ":raw-engine-only-native-reporting-gap" : ":native-shacl");
    }
    const rows = await run(queryKgBundle(candidate, queries.get(expected))); expect(rows.length > 0, `${name}: ${expected} unexpectedly empty`);
    if (name === "cycle") expect(JSON.stringify(rows.map(row => row.taskId.value).sort()) === JSON.stringify(["F1-DURABLE-PORT", "F1-LEDGER", "F1-QUALIFY-CUTOVER", "F1-RUN-CLI"]), "cycle must report exactly four source-bound members");
    return name + ":" + expected;
  };
  const taskUid = id => taskNodes.get(id).uid;
  const probes = await Promise.all([
    validateProbe("missing-role", b => { b.relations = b.relations.filter(edge => !(edge.from_uid === taskUid("F1-LEDGER") && edge.type === "HAS_RESPONSIBILITY_ROLE")); }, "shacl"),
    validateProbe("duplicate-role", b => { const task = taskUid("F1-LEDGER"), uid = b.nodes.find(node => node.properties.standard_graph_role === "RESPONSIBILITY_ROLE" && node.uid !== rel(task, "HAS_RESPONSIBILITY_ROLE")[0]).uid; b.relations.push({ from_uid: task, to_uid: uid, type: "HAS_RESPONSIBILITY_ROLE", authority_class: "SECONDARY_AI_TEST", scope: "probe", status: "PLANNED" }); }, "shacl"),
    validateProbe("missing-criterion-source", b => { b.relations = b.relations.filter(edge => !(edge.from_uid === taskUid("F1-LEDGER") && ["HAS_CRITERION", "HAS_SOURCE"].includes(edge.type))); }, "shacl"),
    validateProbe("cycle", b => b.relations.push({ from_uid: taskUid("F1-LEDGER"), to_uid: taskUid("F1-QUALIFY-CUTOVER"), type: "DEPENDS_ON", authority_class: "SECONDARY_AI_TEST", scope: "probe", status: "PLANNED" }), "Q6"),
    validateProbe("premature-complete", b => { const node = b.nodes.find(n => n.properties.task_id === "F1-LEDGER"); node.properties.status = "COMPLETE"; }, "Q7"),
    validateProbe("missing-tool-integrity", b => { const node = b.nodes.find(n => n.properties.standard_graph_role === "TOOL_PROFILE"); delete node.properties.package_integrity; }, "Q9"),
    validateProbe("false-r03-ops04", b => b.relations.push({ from_uid: taskUid("R-03"), to_uid: taskUid("OPS-04"), type: "DEPENDS_ON", authority_class: "SECONDARY_AI_TEST", scope: "probe", status: "PLANNED" }), "Q8"),
    validateProbe("missing-s5-reuse", b => { const uid = requirementNodes.get("s5-navigation-stale").uid; b.relations = b.relations.filter(edge => !(edge.from_uid === uid && edge.type === "REUSES_EVIDENCE")); }, "Q5"),
    validateProbe("claimed-output-without-evidence", b => { b.nodes.find(n => n.properties.standard_graph_role === "EXPECTED_ARTIFACT").properties.status = "ACCEPTED"; }, "shacl"),
    validateProbe("satisfied-decision-without-evidence", b => { b.nodes.find(n => n.properties.decision_id === "D-FIRST-SCALE").properties.status = "SATISFIED"; }, "shacl")
  ]);
  const readinessProbe = async (decision) => {
    const candidate = structuredClone(bundle);
    for (const id of ["R-03", "R-04"]) candidate.nodes.find(node => node.properties.task_id === id).properties.status = "COMPLETE";
    candidate.nodes.find(node => node.properties.decision_id === "D-FIRST-SCALE").properties.status = decision;
    const bytes = new TextEncoder().encode(JSON.stringify(candidate));
    const compiledCandidate = compileKgBundle([{ sourceId: "plan", rawBytes: bytes, sha256: kgSha256(bytes), byteLength: bytes.byteLength }], "v2");
    expect(Either.isRight(compiledCandidate), `readiness ${decision}: compile failed`);
    return (await run(queryKgBundle(compiledCandidate.right, queries.get("Q1")))).map(row => row.taskId.value).includes("R-05");
  };
  expect(!(await readinessProbe("NOT_SATISFIED")), "negative first-scale decision unexpectedly unlocks R-05");
  expect(await readinessProbe("SATISFIED"), "synthetic readiness-only satisfied first-scale decision does not unlock R-05");
  console.log(JSON.stringify({ status: knownNativeReportingGaps.length ? "PLAN_VALIDATED_WITH_KNOWN_NATIVE_REPORTING_GAP" : "PASS", known_native_reporting_gaps: knownNativeReportingGaps.sort((a,b) => a.probe.localeCompare(b.probe)), task_count: taskById.size, decision_count: decisionById.size, requirement_count: requirementById.size, graph_counts: bundle.expected_counts, source_count: catalog.sources.length, artifact_binding_count: bundle.artifact_bindings.length, shacl_conforms: shapeResults.map(result => result.conforms), ready_task_ids: ready, query_counts: Object.fromEntries([...queryResults].map(([id, result]) => [id, Array.isArray(result) ? result.length : result])), probes, claim_ceilings: [...new Set(plan.tasks.map(task => task.claim_ceiling))].sort(), projection_sha256: kgSha256(projection.nquads), readiness_counterfactual: "synthetic readiness only; no evidence or efficacy claim" }));
};
main().catch(error => { console.error(JSON.stringify({ status: "FAIL", error: error instanceof Error ? error.message : String(error) })); process.exitCode = 1; });
