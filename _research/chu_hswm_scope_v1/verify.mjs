#!/usr/bin/env node
/** Read-only validation of the declared CHU/HSWM software-scope bundle. */
import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const fail = detail => { throw new Error(detail); };
const expect = (value, detail) => { if (!value) fail(detail); };
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
const bundlePath = "ontology/identity/hswm_core/CHU_HSWM_SOFTWARE_SCOPE_ONTOLOGY.v1.json";
const baseShapePath = "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl";
const localShapePath = "_research/chu_hswm_scope_v1/shapes/chu-hswm-scope.ttl";
const queryPaths = { scope: "ontology/queries/chu_hswm_scope_2026-09-27/scope.rq", execution_contracts: "ontology/queries/chu_hswm_scope_2026-09-27/execution_contracts.rq", sources_and_gaps: "ontology/queries/chu_hswm_scope_2026-09-27/sources_and_gaps.rq" };
const rootUid = "sym:AbstractNode:chu-hswm-scope-2026-09-27";
const prefix = "sym:Concept:chu-hswm-2026-09-27-";
const id = suffix => prefix + suffix;
const concepts = ["chu-domain", "hswm-profile", "numeric-world-profile", "llm-kernel", "world-model-capability", "graph-memory", "program", "kernel", "execution", "artifact", "view"].map(id);

export const verifyChuHswmScope = async (cwd = process.cwd()) => {
  const root = await realpath(cwd);
  const require = createRequire(new URL("../../src/hswm/effect-runtime/package.json", import.meta.url));
  const { Effect, Either } = require("effect");
  const { compileKgBundle } = await import("../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js");
  const { queryKgBundle, validateKgShacl } = await import("../../src/hswm/effect-runtime/dist/native-kg-standards.js");
  const bounded = async path => {
    expect(!isAbsolute(path) && !path.includes("\\\\") && !path.split("/").some(part => ["", ".", ".."].includes(part)), "unsafe repository-relative path");
    const file = resolve(root, path), stat = await lstat(file), actual = await realpath(file), rel = relative(root, actual);
    expect(stat.isFile() && !stat.isSymbolicLink() && !isAbsolute(rel) && rel !== ".." && !rel.startsWith(`..${sep}`), "source escapes checkout or is not a regular file");
    expect(stat.size > 0 && stat.size <= 16 * 1024 * 1024, "source outside bounded size"); return readFile(actual);
  };
  const bundleBytes = await bounded(bundlePath);
  const bundle = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bundleBytes));
  expect(bundle.bundle_uid === rootUid, "unexpected CHU/HSWM bundle UID");
  expect(bundle.nodes.length === bundle.expected_counts.nodes && bundle.relations.length === bundle.expected_counts.relations && bundle.anchors.length === bundle.expected_counts.anchors, "declared expected counts differ");
  for (const binding of bundle.artifact_bindings) expect(sha256(await bounded(binding.path)) === binding.sha256, `artifact binding differs: ${binding.path}`);
  const sourceBoundNodes = bundle.nodes.filter(item => item.properties.source_path !== undefined || item.properties.source_sha256 !== undefined);
  for (const item of sourceBoundNodes) {
    const { source_path: path, source_sha256: digest } = item.properties;
    expect(typeof path === "string" && typeof digest === "string" && /^[0-9a-f]{64}$/.test(digest), `${item.uid}: incomplete source binding`);
    expect(sha256(await bounded(path)) === digest, `${item.uid}: source binding differs: ${path}`);
  }
  const nodes = new Map(bundle.nodes.map(item => [item.uid, item]));
  const node = uid => { const value = nodes.get(uid); expect(value, `missing node ${uid}`); return value; };
  for (const uid of [rootUid, ...concepts]) node(uid);
  const outgoing = (from, type) => bundle.relations.filter(edge => edge.from_uid === from && edge.type === type).map(edge => edge.to_uid);
  const property = (uid, key) => node(uid).properties[key];
  expect(property(rootUid, "standard_graph_role") === "SYNTHESIS_BUNDLE", "root role differs");
  expect(property(id("chu-domain"), "standard_graph_role") === "CHU_ABSTRACT_DOMAIN" && property(id("chu-domain"), "llm_required") === false, "CHU domain role or LLM boundary differs");
  expect(concepts.every(uid => outgoing(rootUid, "HAS_CONCEPT").includes(uid)), "root does not include each required concept");
  expect(property(id("hswm-profile"), "standard_graph_role") === "HSWM_EXECUTION_PROFILE" && property(id("hswm-profile"), "llm_required") === true, "HSWM execution profile differs");
  expect(property(id("numeric-world-profile"), "standard_graph_role") === "NON_LLM_WORLD_MODEL_PROFILE" && property(id("numeric-world-profile"), "llm_required") === false && property(id("numeric-world-profile"), "status") === "ILLUSTRATIVE_NOT_INTEGRATED", "non-LLM profile differs");
  for (const profile of [id("hswm-profile"), id("numeric-world-profile")]) {
    expect(outgoing(profile, "SPECIALIZES_SCOPE").includes(id("chu-domain")), `${profile}: missing CHU specialization`);
    expect(outgoing(profile, "HAVE_TARGET_CAPABILITY").includes(id("world-model-capability")), `${profile}: missing shared target capability`);
  }
  expect(outgoing(id("chu-domain"), "CONCEPTUALLY_INCLUDES").includes(id("hswm-profile")) && outgoing(id("chu-domain"), "CONCEPTUALLY_INCLUDES").includes(id("numeric-world-profile")), "CHU containment differs");
  expect(outgoing(id("hswm-profile"), "REQUIRES_KERNEL").includes(id("llm-kernel")), "HSWM requires LLM kernel edge absent");
  expect(property(id("llm-kernel"), "standard_graph_role") === "COMPUTATIONAL_KERNEL", "LLM kernel role differs");
  const contracts = bundle.nodes.filter(item => item.properties.standard_graph_role === "COMPUTATIONAL_CONTRACT");
  expect(contracts.length > 0 && contracts.every(item => typeof item.properties.existing_path === "string" && item.properties.existing_path.length > 0 && typeof item.properties.status === "string" && item.properties.status.length > 0), "computational contract mapping is incomplete");
  for (const contract of contracts) await bounded(contract.properties.existing_path);
  const literature = bundle.nodes.filter(item => item.properties.standard_graph_role === "LITERATURE_CONNECTION");
  expect(literature.length > 0 && literature.every(item => typeof item.properties.external_url === "string" && typeof item.properties.source_authority === "string"), "literature connection lacks source metadata");
  const gaps = bundle.nodes.filter(item => item.properties.standard_graph_role === "OPEN_RESEARCH_GAP"); expect(gaps.length > 0, "no open research gaps declared");
  const compile = value => {
    const bytes = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value));
    const result = compileKgBundle([{ sourceId: "chu-hswm-scope", rawBytes: bytes, sha256: sha256(bytes), byteLength: bytes.byteLength }], "v2");
    expect(Either.isRight(result), `native v2 compilation failed: ${Either.isLeft(result) ? result.left.detail : "unknown"}`); return result.right;
  };
  const projection = compile(bundleBytes);
  const [baseShape, localShape, queryText] = await Promise.all([bounded(baseShapePath), bounded(localShapePath), Promise.all(Object.entries(queryPaths).map(async ([name, path]) => [name, new TextDecoder("utf-8", { fatal: true }).decode(await bounded(path))]))]);
  const validate = (candidate, shape) => Effect.runPromise(validateKgShacl(candidate, shape));
  const query = (candidate, text) => Effect.runPromise(queryKgBundle(candidate, text));
  const [baseReport, localReport, rows] = await Promise.all([validate(projection, baseShape), validate(projection, localShape), Promise.all(queryText.map(async ([name, text]) => [name, await query(projection, text)]))]);
  expect(baseReport.conforms && localReport.conforms, "base or CHU/HSWM scope SHACL did not conform");
  const rowMap = new Map(rows), scopeRows = rowMap.get("scope");
  expect(Array.isArray(scopeRows) && scopeRows.length === 2, "scope query must return exactly two profiles");
  const scope = new Map(scopeRows.map(row => [row.role.value, row]));
  for (const [role, required] of [["HSWM_EXECUTION_PROFILE", "true"], ["NON_LLM_WORLD_MODEL_PROFILE", "false"]]) {
    const row = scope.get(role); expect(row && row.llm_required.value === required && row.capability?.value === property(id("world-model-capability"), "name"), `scope query differs: ${role}`);
  }
  for (const name of ["execution_contracts", "sources_and_gaps"]) expect(Array.isArray(rowMap.get(name)) && rowMap.get(name).length > 0, `query returned no rows: ${name}`);
  const mutations = [
    ["missing_hswm_llm_kernel", value => { value.relations = value.relations.filter(edge => !(edge.from_uid === id("hswm-profile") && edge.type === "REQUIRES_KERNEL" && edge.to_uid === id("llm-kernel"))); }],
    ["chu_erroneously_llm_required", value => { value.nodes.find(item => item.uid === id("chu-domain")).properties.llm_required = true; }],
    ["missing_hswm_world_model_capability", value => { value.relations = value.relations.filter(edge => !(edge.from_uid === id("hswm-profile") && edge.type === "HAVE_TARGET_CAPABILITY" && edge.to_uid === id("world-model-capability"))); }]
  ];
  const negative = [];
  for (const [name, mutate] of mutations) {
    const candidate = structuredClone(bundle); mutate(candidate); candidate.expected_counts.relations = candidate.relations.length;
    const report = await validate(compile(candidate), localShape); expect(!report.conforms, `negative mutation was accepted: ${name}`); negative.push(name);
  }
  return { schema_version: "chu-hswm-scope-check/v1", status: "PASS", bundle: { path: bundlePath, sha256: sha256(bundleBytes), counts: bundle.expected_counts }, artifact_bindings_recomputed: bundle.artifact_bindings.length, node_source_bindings_recomputed: sourceBoundNodes.length, shacl: { base_conforms: true, scope_conforms: true }, query_rows: Object.fromEntries(rows.map(([name, result]) => [name, result.length])), contracts: contracts.length, literature_connections: literature.length, open_research_gaps: gaps.length, negative_rejections: negative, actual_runtime_execution: false, claim_ceiling: "DECLARED_SCOPE_AND_READ_ONLY_KG_STRUCTURE_ONLY_NOT_WORLD_MODEL_EFFICACY_NOT_CANONICAL_WRITE_NOT_LLM_RUNTIME_EXECUTION" };
};

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  if (process.argv.length !== 2) throw new Error("usage: verify.mjs");
  console.log(JSON.stringify(await verifyChuHswmScope()));
}
