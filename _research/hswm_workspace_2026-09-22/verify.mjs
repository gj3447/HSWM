#!/usr/bin/env node
/** Offline verification for the read-only workspace occurrence projection. */
import { createHash } from "node:crypto"
import { lstat, readFile, realpath, writeFile } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"
import { pathToFileURL } from "node:url"
import { createRequire } from "node:module"

const root = resolve(process.cwd())
const bundlePath = resolve(root, "ontology/development/HSWM_KG_WORKSPACE_2026-09-22.v1.json")
const inventoryPath = resolve(root, "docs/operations/artifacts/hswm_workspace_2026-09-22/inventory.v1.json")
const queryRoot = resolve(root, "ontology/queries/hswm_workspace_2026-09-22")
const args = process.argv.slice(2)
const requestedOutput = args.length === 0 ? null : args.length === 2 && args[0] === "--output" ? args[1] : (() => { throw new Error("usage: verify.mjs [--output repository-relative-file]") })()
const sha = bytes => createHash("sha256").update(bytes).digest("hex")
const expect = (condition, detail) => { if (!condition) throw new Error(detail) }
const json = async path => JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(await readFile(path)))
const boundBytes = async path => {
  if (isAbsolute(path) || path.includes("\\") || path.split("/").some(part => part === "" || part === "." || part === "..")) throw new Error(`invalid bound path: ${path}`)
  const target = resolve(root, path), before = await lstat(target)
  expect(before.isFile() && !before.isSymbolicLink(), `bound source is not regular: ${path}`)
  const actual = await realpath(target), rel = relative(root, actual)
  expect(rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel), `bound source escapes checkout: ${path}`)
  const bytes = await readFile(actual)
  expect(bytes.byteLength > 0 && bytes.byteLength <= 16 * 1024 * 1024, `bound source bytes outside limit: ${path}`)
  return bytes
}
const require = createRequire(resolve(root, "src/hswm/effect-runtime/package.json"))
const { Effect, Either } = require("effect")
const runtime = resolve(root, "src/hswm/effect-runtime/dist")
const [{ compileKgBundle }, { queryKgBundle, validateKgShacl }, { inspectWorkspaceBundle, summarizeWorkspaceBundles }] = await Promise.all([
  import(pathToFileURL(resolve(runtime, "native-kg-bundle-domain.js")).href),
  import(pathToFileURL(resolve(runtime, "native-kg-standards.js")).href),
  import(pathToFileURL(resolve(runtime, "workspace-catalog-domain.js")).href)
])
const run = effect => Effect.runPromise(effect)

const main = async () => {
  const [bundleBytes, inventoryBytes, bundle, inventory, manifest] = await Promise.all([
    readFile(bundlePath), readFile(inventoryPath), json(bundlePath), json(inventoryPath), json(resolve(root, "ontology/workspace/HSWM_WORKSPACE.v1.json"))
  ])
  expect(bundle.bundle_uid === "sym:AbstractNode:hswm-kg-workspace-2026-09-22", "unexpected workspace root UID")
  expect(bundle.expected_counts.nodes === bundle.nodes.length && bundle.expected_counts.anchors === bundle.anchors.length && bundle.expected_counts.relations === bundle.relations.length, "bundle expected counts disagree")
  expect(bundle.anchors.length === 0, "workspace metadata has no external node anchors")
  const bindingByPath = new Map(bundle.artifact_bindings.map(binding => [binding.path, binding.sha256]))
  for (const [path, expected] of bindingByPath) expect(sha(await boundBytes(path)) === expected, `artifact binding differs: ${path}`)
  const dotSource = bundle.nodes.find(node => node.properties.source_path === ".vscode/tasks.json")
  expect(dotSource?.properties.source_binding_profile === "DOT_PREFIXED_PATH_OUTSIDE_NATIVE_ARTIFACT_BINDING_PROFILE", "dot-prefixed source profile is absent")
  expect(dotSource.properties.source_sha256 === sha(await boundBytes(".vscode/tasks.json")), "dot-prefixed source digest differs")
  expect(Array.isArray(inventory.captured_ontology_json_paths) && inventory.captured_ontology_json_paths.length === inventory.tracked_ontology_json_count, "inventory lacks its captured source paths")
  const capturedInspections = []
  for (const path of inventory.captured_ontology_json_paths) {
    const result = inspectWorkspaceBundle({ path, bytes: await boundBytes(path) })
    expect(Either.isRight(result), `captured inventory input does not decode: ${path}`)
    capturedInspections.push({ path, item: result.right })
  }
  const capturedBundles = capturedInspections.flatMap(row => row.item === null ? [] : [row.item])
  const capturedSummary = summarizeWorkspaceBundles(capturedBundles)
  expect(capturedBundles.length === inventory.recognized_bundle_count && inventory.captured_ontology_json_paths.length - capturedBundles.length === inventory.non_bundle_json_count, "captured inventory counts differ")
  expect(JSON.stringify(capturedSummary) === JSON.stringify(inventory.summary), "captured inventory UID occurrence summary differs")
  const capturedByPath = new Map(capturedBundles.map(item => [item.path, item]))
  expect(capturedByPath.size === inventory.bundle_occurrences.length, "captured bundle occurrence count differs")
  for (const item of inventory.bundle_occurrences) {
    const recomputed = capturedByPath.get(item.path)
    expect(recomputed !== undefined && JSON.stringify({ ...recomputed }) === JSON.stringify({ path: item.path, sha256: item.sha256, byteLength: item.byteLength, bundleUid: item.bundleUid, nodeCount: item.nodeCount, anchorCount: item.anchorCount, relationCount: item.relationCount, nodeUids: item.nodeUids, bindings: item.bindings, sourceCut: item.sourceCut, issues: item.issues }), `captured bundle descriptor differs: ${item.path}`)
  }
  const graphOccurrences = new Map(bundle.nodes.filter(node => node.properties.standard_graph_role === "BUNDLE_OCCURRENCE").map(node => [node.properties.path, node]))
  expect(graphOccurrences.size === capturedByPath.size, "graph bundle occurrence count differs")
  for (const item of capturedBundles) {
    const node = graphOccurrences.get(item.path)
    expect(node?.properties.source_sha256 === item.sha256 && node.properties.byte_length === item.byteLength && node.properties.node_count === item.nodeCount && node.properties.anchor_count === item.anchorCount && node.properties.relation_count === item.relationCount && node.properties.bundle_uid === (item.bundleUid ?? "UNDECLARED"), `graph bundle descriptor differs: ${item.path}`)
  }
  const expectedUidOccurrences = inventory.summary.duplicateUids.flatMap(item => item.occurrences.map(occurrence => `${item.uid}|${occurrence.path}|${occurrence.bundleUid ?? "UNDECLARED"}`)).sort()
  const observedUidOccurrences = bundle.nodes.filter(node => node.properties.standard_graph_role === "UID_OCCURRENCE").map(node => `${node.properties.uid}|${node.properties.path}|${node.properties.bundle_uid}`).sort()
  expect(JSON.stringify(observedUidOccurrences) === JSON.stringify(expectedUidOccurrences), "graph UID occurrences differ from captured inventory")
  const compiled = compileKgBundle([{ sourceId: "workspace", rawBytes: bundleBytes, sha256: sha(bundleBytes), byteLength: bundleBytes.byteLength }], "v2")
  expect(Either.isRight(compiled), `native v2 compile rejected: ${Either.isLeft(compiled) ? compiled.left.detail : "unknown"}`)
  const projection = compiled.right
  const queries = ["entrypoints.rq", "bundle_binding_summaries.rq", "duplicate_uid_occurrences.rq", "command_surfaces.rq", "unresolved_drift_observations.rq"]
  const results = Object.fromEntries(await Promise.all(queries.map(async name => [name, await run(queryKgBundle(projection, await readFile(resolve(queryRoot, name), "utf8")))])))
  const rows = name => results[name]
  expect(Array.isArray(rows("entrypoints.rq")) && rows("entrypoints.rq").length === 21, "entrypoint query does not return 21 entries")
  expect(Array.isArray(rows("command_surfaces.rq")) && rows("command_surfaces.rq").length === 12, "command query does not return 12 workflows")
  const entryIds = rows("entrypoints.rq").map(row => row.id.value).sort()
  expect(JSON.stringify(entryIds) === JSON.stringify(manifest.entries.map(entry => entry.id).sort()), "entrypoint IDs differ from manifest")
  const commandIds = rows("command_surfaces.rq").map(row => row.id.value).sort()
  expect(JSON.stringify(commandIds) === JSON.stringify(manifest.workflows.map(workflow => workflow.id).sort()), "workflow IDs differ from manifest")
  const expectedQueryAliases = manifest.entries.flatMap(entry => entry.queries.map(query => `${entry.id}|${query.id}`)).sort()
  const observedQueryAliases = bundle.nodes.filter(node => node.properties.standard_graph_role === "QUERY_ALIAS").map(node => `${node.properties.entry_id}|${node.properties.query_id}`).sort()
  expect(expectedQueryAliases.length === 45 && JSON.stringify(observedQueryAliases) === JSON.stringify(expectedQueryAliases), "query alias targets differ from manifest")
  const expectedDocuments = [...new Set(manifest.entries.map(entry => entry.document))].sort()
  const observedDocuments = [...new Set(bundle.nodes.filter(node => node.properties.standard_graph_role === "DOCUMENT_SOURCE").map(node => node.properties.document_path))].sort()
  expect(JSON.stringify(observedDocuments) === JSON.stringify(expectedDocuments), "document targets differ from manifest")
  const expectedShapes = [...new Set(manifest.entries.flatMap(entry => entry.shapes))].sort()
  const observedShapes = [...new Set(bundle.nodes.filter(node => node.properties.standard_graph_role === "SHAPE_REFERENCE").map(node => node.properties.shape_path))].sort()
  expect(JSON.stringify(observedShapes) === JSON.stringify(expectedShapes), "shape targets differ from manifest")
  const relations = (from, type) => bundle.relations.filter(edge => edge.from_uid === from && edge.type === type).map(edge => edge.to_uid).sort()
  const nodeByUid = new Map(bundle.nodes.map(node => [node.uid, node]))
  const entryNodes = new Map(bundle.nodes.filter(node => node.properties.standard_graph_role === "WORKSPACE_ENTRY").map(node => [node.properties.entry_id, node]))
  for (const entry of manifest.entries) {
    const entryNode = entryNodes.get(entry.id)
    expect(entryNode !== undefined && entryNode.properties.projection_profile === (entry.projection_profile ?? "NATIVE_V2") && entryNode.properties.projection_reason === entry.projection_reason, `entry profile differs: ${entry.id}`)
    const bundleTargets = relations(entryNode.uid, "HAS_BUNDLE_OCCURRENCE").map(uid => nodeByUid.get(uid)?.properties.path)
    expect(JSON.stringify(bundleTargets) === JSON.stringify([entry.bundle]), `entry bundle edge differs: ${entry.id}`)
    const documentTargets = relations(entryNode.uid, "HAS_DOCUMENT_SOURCE").map(uid => nodeByUid.get(uid))
    expect(documentTargets.length === 1 && documentTargets[0].properties.document_path === entry.document && documentTargets[0].properties.source_ref === entry.document && documentTargets[0].properties.source_sha256 === sha(await boundBytes(entry.document)), `entry document edge differs: ${entry.id}`)
    const queryTargets = relations(entryNode.uid, "HAS_QUERY_ALIAS").map(uid => nodeByUid.get(uid)).sort((left, right) => String(left.properties.query_id).localeCompare(String(right.properties.query_id)))
    expect(queryTargets.length === entry.queries.length, `entry query edge count differs: ${entry.id}`)
    for (const [index, query] of [...entry.queries].sort((left, right) => left.id.localeCompare(right.id)).entries()) {
      const node = queryTargets[index]
      expect(node?.properties.query_id === query.id && node.properties.query_path === query.path && node.properties.source_ref === query.path && node.properties.source_sha256 === sha(await boundBytes(query.path)), `entry query target differs: ${entry.id}|${query.id}`)
    }
    const shapeTargets = relations(entryNode.uid, "HAS_SHAPE_REFERENCE").map(uid => nodeByUid.get(uid)).sort((left, right) => String(left.properties.shape_path).localeCompare(String(right.properties.shape_path)))
    expect(shapeTargets.length === entry.shapes.length, `entry shape edge count differs: ${entry.id}`)
    for (const [index, path] of [...entry.shapes].sort().entries()) {
      const node = shapeTargets[index]
      expect(node?.properties.shape_path === path && node.properties.source_ref === path && node.properties.source_sha256 === sha(await boundBytes(path)), `entry shape target differs: ${entry.id}|${path}`)
    }
  }
  expect(Array.isArray(rows("bundle_binding_summaries.rq")) && rows("bundle_binding_summaries.rq").length === inventory.recognized_bundle_count, "bundle summary query differs from inventory")
  const duplicateRows = rows("duplicate_uid_occurrences.rq")
  expect(Array.isArray(duplicateRows) && duplicateRows.length === inventory.summary.duplicateUids.reduce((total, item) => total + item.occurrences.length, 0), "duplicate UID query loses or merges occurrences")
  const roles = new Set(bundle.nodes.map(node => node.properties.standard_graph_role))
  expect(!roles.has("IMPORTED_SOURCE_NODE") && !roles.has("CANONICAL_OWNER_SELECTION"), "projection claims an underlying-node union or owner choice")
  const baseShape = await readFile(resolve(root, "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"))
  const rootShape = await readFile(resolve(queryRoot, "workspace-root-shape.ttl"))
  const shapeReports = await Promise.all([baseShape, rootShape].map(bytes => run(validateKgShacl(projection, bytes))))
  expect(shapeReports.every(report => report.conforms), "base or nonvacuous root SHACL did not conform")
  const mutation = structuredClone(bundle)
  mutation.nodes.find(node => node.uid === mutation.bundle_uid).properties.standard_graph_role = "UNRELATED_ROOT"
  mutation.expected_counts = { nodes: mutation.nodes.length, anchors: mutation.anchors.length, relations: mutation.relations.length }
  const mutatedBytes = new TextEncoder().encode(JSON.stringify(mutation))
  const mutated = compileKgBundle([{ sourceId: "root-negative", rawBytes: mutatedBytes, sha256: sha(mutatedBytes), byteLength: mutatedBytes.byteLength }], "v2")
  expect(Either.isRight(mutated), "root negative mutation did not compile")
  const negativeShape = await run(validateKgShacl(mutated.right, rootShape))
  expect(!negativeShape.conforms, "nonvacuous root SHACL accepted a root with the wrong role")
  const output = {
    schema_version: "hswm-workspace-graph-validation/v1", status: "PASS", bundle: { path: "ontology/development/HSWM_KG_WORKSPACE_2026-09-22.v1.json", sha256: sha(bundleBytes), counts: bundle.expected_counts },
    inventory: { path: "docs/operations/artifacts/hswm_workspace_2026-09-22/inventory.v1.json", sha256: sha(inventoryBytes), captured_ontology_json_count: inventory.captured_ontology_json_paths.length, recognized_bundle_count: inventory.recognized_bundle_count, duplicate_uid_groups: inventory.summary.duplicateUidCount, uid_occurrences: inventory.summary.nodeOccurrenceCount },
    bindings_recomputed: bindingByPath.size, supplemental_source_hashes_recomputed: 1, navigation_targets: { entries: entryIds.length, query_aliases: observedQueryAliases.length, documents: observedDocuments.length, shapes: observedShapes.length, workflows: commandIds.length }, query_rows: Object.fromEntries(Object.entries(results).map(([name, value]) => [name, Array.isArray(value) ? value.length : value])),
    shacl: shapeReports.map(report => ({ conforms: report.conforms, engine: report.engine, profile: report.profile })),
    negative_probes: [{ name: "wrong-root-role", conforms: negativeShape.conforms }],
    limitation: "This validates the new metadata projection and current bound bytes. It does not execute every legacy bundle query or reconstruct historical worktrees."
  }
  if (requestedOutput !== null) {
    if (isAbsolute(requestedOutput) || requestedOutput.includes("\\") || requestedOutput.split("/").some(part => part === "" || part === "." || part === "..")) throw new Error("output must be a repository-relative file path")
    await writeFile(resolve(root, requestedOutput), `${JSON.stringify(output, null, 2)}\n`, { flag: "wx" })
  }
  console.log(JSON.stringify(output))
}
await main()
