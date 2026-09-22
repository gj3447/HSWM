/** Create-only workspace inventory projection. It observes source occurrences; it never merges them. */
import { createHash } from "node:crypto"
import { execFile as execFileCallback } from "node:child_process"
import { lstat, mkdir, readFile, realpath, writeFile } from "node:fs/promises"
import { createRequire } from "node:module"
import { isAbsolute, relative, resolve, sep } from "node:path"
import { promisify } from "node:util"

const root = await realpath(process.cwd())
const execFile = promisify(execFileCallback)
const require = createRequire(new URL("../../src/hswm/effect-runtime/package.json", import.meta.url))
const { Either } = require("effect") as typeof import("effect")
const { decodeKgBundleSource } = await import("../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js")
const { inspectWorkspaceBundle, summarizeWorkspaceBundles } = await import("../../src/hswm/effect-runtime/dist/workspace-catalog-domain.js")

const outputPath = "ontology/development/HSWM_KG_WORKSPACE_2026-09-22.v1.json"
const inventoryPath = "docs/operations/artifacts/hswm_workspace_2026-09-22/inventory.v1.json"
const manifestPath = "ontology/workspace/HSWM_WORKSPACE.v1.json"
const rootUid = "sym:AbstractNode:hswm-kg-workspace-2026-09-22"
const sha = (value: Uint8Array | string) => createHash("sha256").update(value).digest("hex")
const text = (value: Uint8Array) => new TextDecoder("utf-8", { fatal: true }).decode(value)
const uid = (kind: string, value: string) => `sym:${kind}:hswm-workspace-20260922-${sha(value).slice(0, 20)}`
const canonical = (value: unknown) => JSON.stringify(value, null, 2) + "\n"
const requirePath = async (path: string) => {
  if (isAbsolute(path) || path.includes("\\") || path.split("/").some(part => part === "" || part === "." || part === "..")) throw new Error(`invalid repository-relative source path: ${path}`)
  const target = resolve(root, path)
  const before = await lstat(target)
  if (!before.isFile() || before.isSymbolicLink()) throw new Error(`bound source is not a regular non-symlink file: ${path}`)
  const actual = await realpath(target)
  const rel = relative(root, actual)
  if (rel === ".." || rel.startsWith(`..${sep}`) || isAbsolute(rel)) throw new Error(`bound source resolves outside checkout: ${path}`)
  const bytes = await readFile(actual)
  if (bytes.byteLength > 16 * 1024 * 1024) throw new Error(`bound source exceeds 16 MiB: ${path}`)
  if (bytes.byteLength === 0) throw new Error(`empty bound source: ${path}`)
  return bytes
}
const tracked = async () => (await execFile("git", ["ls-files", "-z"], { cwd: root, encoding: "buffer" })).stdout.toString("utf8").split("\0").filter(Boolean).sort()

const main = async () => {
  const manifest = JSON.parse(text(await requirePath(manifestPath))) as any
  if (!Array.isArray(manifest.entries) || manifest.entries.length !== 21 || !Array.isArray(manifest.workflows) || manifest.workflows.length !== 12) {
    throw new Error("workspace manifest does not have its declared 21 entries and 12 workflows")
  }
  const trackedPaths = await tracked()
  // The generated projection is deliberately excluded from its frozen input
  // set so a later Git tracking operation cannot make the build self-referential.
  const ontologyPaths = trackedPaths.filter(path => path.startsWith("ontology/") && path.endsWith(".json") && path !== outputPath)
  const inspections = [] as any[]
  for (const path of ontologyPaths) {
    const bytes = await requirePath(path)
    const inspected = inspectWorkspaceBundle({ path, bytes })
    if (Either.isLeft(inspected)) inspections.push({ path, item: null, error: inspected.left.detail })
    else inspections.push({ path, item: inspected.right, error: null })
  }
  const bundles = inspections.flatMap(row => row.item === null ? [] : [row.item])
  const summary = summarizeWorkspaceBundles(bundles)
  if (ontologyPaths.length !== 212 || bundles.length !== 101 || summary.nodeOccurrenceCount !== 6216 || summary.duplicateUidCount !== 48) {
    throw new Error("frozen workspace inventory cardinality differs from the reviewed input set")
  }
  const sourceBundlePaths = new Set(bundles.map(item => item.path))
  for (const entry of manifest.entries) if (!sourceBundlePaths.has(entry.bundle)) throw new Error(`manifest entry is not a recognized tracked bundle: ${entry.id}`)

  const queryPaths = ["entrypoints.rq", "bundle_binding_summaries.rq", "duplicate_uid_occurrences.rq", "command_surfaces.rq", "unresolved_drift_observations.rq"]
    .map(name => `ontology/queries/hswm_workspace_2026-09-22/${name}`)
  const shapePath = "ontology/queries/hswm_workspace_2026-09-22/workspace-root-shape.ttl"
  const curatedPaths = [
    ...manifest.entries.flatMap((entry: any) => [entry.document, ...entry.queries.map((query: any) => query.path), ...entry.shapes])
  ]
  // The native v2 artifact-binding path profile deliberately refuses leading
  // dots. Keep that one checkout source exact in a source node rather than
  // normalizing its path or pretending it is a historical binding.
  const supplementalSourcePaths = [".vscode/tasks.json"]
  const ownPaths = [
    "_research/hswm_workspace_2026-09-22/build.mts",
    "_research/hswm_workspace_2026-09-22/verify.mjs",
    manifestPath,
    "docs/operations/HSWM_KG_WORKSPACE_2026-09-22.md",
    "src/hswm/effect-runtime/src/workspace-catalog-domain.ts",
    "src/hswm/effect-runtime/src/workspace-manifest-domain.ts",
    "src/hswm/effect-runtime/src/workspace-cli.ts",
    "src/hswm/effect-runtime/src/workspace-process.ts",
    "src/hswm/effect-runtime/bin/hswm-workspace",
    "src/hswm/effect-runtime/src/native-kg-standards.ts",
    "src/hswm/effect-runtime/package-lock.json",
    "ontology/README.md",
    ...queryPaths, shapePath, ...curatedPaths
  ]
  const sourcePaths = [...new Set([...bundles.map(item => item.path), ...ownPaths])].sort()
  const bindingBytes = new Map(await Promise.all(sourcePaths.map(async path => [path, await requirePath(path)] as const)))
  const supplementalBytes = new Map(await Promise.all(supplementalSourcePaths.map(async path => [path, await requirePath(path)] as const)))
  const bindings = sourcePaths.map(path => ({ path, sha256: sha(bindingBytes.get(path)!) }))
  const bindingByPath = new Map(bindings.map(binding => [binding.path, binding]))

  const nodes: any[] = [], relations: any[] = []
  const add = (id: string, label: string, role: string, name: string, description: string, properties: Record<string, unknown> = {}) => {
    const sourceRef = typeof properties.source_ref === "string" ? properties.source_ref : undefined
    if (sourceRef !== undefined && !bindingByPath.has(sourceRef)) throw new Error(`unbound local source reference: ${sourceRef}`)
    nodes.push({ uid: id, labels: label === "AbstractNode" ? ["Concept", "AbstractNode"] : [label], properties: {
      name, description, standard_graph_role: role, authority_class: "SECONDARY_AI", ontology_authority_class_v1: "SECONDARY_AI",
      ontology_kind_v1: label === "Reference" ? "DOCUMENT" : "CONCEPT", ontology_domain_v1: "ENGINEERING", ontology_plane_v1: "READ_ONLY_WORKSPACE_PROJECTION",
      ontology_canonical_scope_v1: "SOURCE_BOUND_OBSERVATION", ontology_epistemic_state_v1: "OBSERVED", ontology_record_lifecycle_v1: "ACTIVE",
      ontology_review_required_v1: true, ontology_sensitivity_v1: "NORMAL", responsibility_owner: "workspace_catalog_research_2026_09_22",
      cr_fcl_promotion: false, claim_boundary: "WORKSPACE_NAVIGATION_AND_SOURCE_OCCURRENCE_METADATA_ONLY_NOT_HSWM_COGNITION_OR_EFFICACY", projection_nonclaim: "WORKSPACE_NAVIGATION_AND_SOURCE_OCCURRENCE_METADATA_ONLY_NOT_HSWM_COGNITION_OR_EFFICACY",
      ...properties, ...(sourceRef === undefined ? {} : { source_sha256: bindingByPath.get(sourceRef)!.sha256 })
    } })
    return id
  }
  const link = (from_uid: string, type: string, to_uid: string, scope = "READ_ONLY_WORKSPACE_OBSERVATION") => relations.push({ from_uid, type, to_uid, authority_class: "SECONDARY_AI", scope, status: "SOURCE_BOUND_OBSERVATION" })
  const sourceNodes = new Map<string, string>()
  const source = (path: string) => {
    const existing = sourceNodes.get(path)
    if (existing) return existing
    const binding = bindingByPath.get(path)
    const supplemental = supplementalBytes.get(path)
    if (!binding && !supplemental) throw new Error(`source node has no source binding: ${path}`)
    const id = add(uid("Reference", path), "Reference", "ENGINEERING_SOURCE", path, "Exact local source bytes bound to this workspace observation.", binding
      ? { source_ref: path, source_path: path, source_sha256: binding.sha256 }
      : { source_path: path, source_sha256: sha(supplemental!), source_binding_profile: "DOT_PREFIXED_PATH_OUTSIDE_NATIVE_ARTIFACT_BINDING_PROFILE" })
    sourceNodes.set(path, id)
    return id
  }
  const workspaceRoot = add(rootUid, "AbstractNode", "WORKSPACE_ROOT", "HSWM KG workspace 2026-09-22", "Read-only curated navigation and source-occurrence inventory. It does not merge source graph nodes, choose an owner, or implement HSWM cognition.", { source_ref: manifestPath, status: "SOURCE_BOUND_WORKSPACE_OBSERVATION", claim_ceiling: "NAVIGATION_AND_ENGINEERING_METADATA_NOT_HSWM_EFFICACY" })
  for (const path of [...sourcePaths, ...supplementalSourcePaths]) link(workspaceRoot, "HAS_SOURCE", source(path))

  const occurrenceIds = new Map<string, string>()
  const bindingObservations: any[] = []
  for (const item of bundles) {
    const id = add(uid("BundleOccurrence", item.path), "BundleOccurrence", "BUNDLE_OCCURRENCE", item.path, "One source-bound bundle occurrence. Its contained nodes are not imported or unioned here.", {
      source_ref: item.path, path: item.path, bundle_uid: item.bundleUid ?? "UNDECLARED", source_sha256: item.sha256,
      byte_length: item.byteLength, node_count: item.nodeCount, anchor_count: item.anchorCount, relation_count: item.relationCount,
      structural_issues: item.issues.join(" | "), binding_match_count: 0, binding_worktree_differs_count: 0, binding_not_tracked_not_read_count: 0,
      binding_no_expected_digest_count: 0, binding_unavailable_count: 0, status: "SOURCE_BUNDLE_OCCURRENCE_NOT_NODE_UNION"
    })
    occurrenceIds.set(item.path, id)
    link(workspaceRoot, "HAS_CONCEPT", id)
    link(id, "DERIVED_FROM", source(item.path))
    for (const binding of item.bindings) {
      let status: string, actual: string | null = null
      if (!trackedPaths.includes(binding.path)) status = "NOT_TRACKED_NOT_READ"
      else if (binding.sha256 === null) status = "NO_EXPECTED_DIGEST"
      else {
        try { actual = sha(await requirePath(binding.path)); status = actual === binding.sha256 ? "MATCH" : "WORKTREE_DIFFERS" }
        catch { status = "UNAVAILABLE" }
      }
      const property = `binding_${status.toLowerCase()}_count`
      const occurrence = nodes.find(node => node.uid === id)!
      occurrence.properties[property] = Number(occurrence.properties[property] ?? 0) + 1
      if (status !== "MATCH") bindingObservations.push({ bundle: item.path, binding, status, actual })
    }
  }
  for (const entry of manifest.entries) {
    const id = add(uid("WorkspaceEntry", entry.id), "WorkspaceEntry", "WORKSPACE_ENTRY", entry.title, entry.reading, {
      source_ref: manifestPath, entry_id: entry.id, lane: entry.lane, document_path: entry.document, query_alias_count: entry.queries.length, shape_count: entry.shapes.length,
      status: "CURATED_NAVIGATION_ENTRY", projection_profile: entry.projection_profile ?? "NATIVE_V2", ...(entry.projection_reason === undefined ? {} : { projection_reason: entry.projection_reason })
    })
    const documentId = add(uid("DocumentSource", entry.document), "Reference", "DOCUMENT_SOURCE", entry.document, "Curated workspace document reference, bound as bytes without asserting its contents as a new claim.", { source_ref: entry.document, document_path: entry.document, status: "CURATED_DOCUMENT_REFERENCE" })
    link(workspaceRoot, "HAS_CONCEPT", id); link(id, "DERIVED_FROM", source(manifestPath)); link(id, "HAS_BUNDLE_OCCURRENCE", occurrenceIds.get(entry.bundle)!); link(id, "HAS_DOCUMENT_SOURCE", documentId); link(documentId, "DERIVED_FROM", source(entry.document))
    for (const query of entry.queries) {
      const queryId = add(uid("QueryAlias", `${entry.id}|${query.id}`), "Reference", "QUERY_ALIAS", query.id, "Curated read-only query alias. Its byte binding is explicit; it is not executed by this projection.", { source_ref: query.path, entry_id: entry.id, query_id: query.id, query_path: query.path, status: "CURATED_QUERY_ALIAS_NOT_EXECUTED" })
      link(id, "HAS_QUERY_ALIAS", queryId); link(queryId, "DERIVED_FROM", source(query.path))
    }
    for (const shape of entry.shapes) {
      const shapeId = add(uid("ShapeReference", `${entry.id}|${shape}`), "Reference", "SHAPE_REFERENCE", shape, "Curated SHACL shape reference, bound as bytes without a new conformance assertion.", { source_ref: shape, entry_id: entry.id, shape_path: shape, status: "CURATED_SHAPE_REFERENCE" })
      link(id, "HAS_SHAPE_REFERENCE", shapeId); link(shapeId, "DERIVED_FROM", source(shape))
    }
  }
  for (const workflow of manifest.workflows) {
    const id = add(uid("Workflow", workflow.id), "Workflow", "DOCUMENTED_WORKFLOW", workflow.title, "Documented command surface only; no command is executed by this projection.", {
      source_ref: manifestPath, workflow_id: workflow.id, surface: workflow.surface, argv: workflow.argv.join(" "), writes: workflow.writes, network: workflow.network, status: "DOCUMENTED_NOT_EXECUTED"
    })
    link(workspaceRoot, "HAS_CONCEPT", id); link(id, "DERIVED_FROM", source(manifestPath))
  }
  for (const observation of bindingObservations) {
    const id = add(uid("BindingObservation", `${observation.bundle}|${observation.binding.path}`), "BindingObservation", "BINDING_OBSERVATION", `${observation.status}: ${observation.binding.path}`, "Current worktree comparison only. A non-match neither repairs nor corrupts the historical expected digest.", {
      source_ref: observation.bundle, binding_path: observation.binding.path, binding_status: observation.status, expected_sha256: observation.binding.sha256 ?? "UNDECLARED", ...(observation.actual === null ? {} : { actual_sha256: observation.actual }),
      status: "WORKTREE_COMPARISON_NOT_HISTORICAL_RECONSTRUCTION"
    })
    link(occurrenceIds.get(observation.bundle)!, "HAS_BINDING_OBSERVATION", id); link(id, "ABOUT", occurrenceIds.get(observation.bundle)!); link(id, "DERIVED_FROM", source(observation.bundle))
  }
  for (const duplicate of summary.duplicateUids) {
    const id = add(uid("DuplicateUid", duplicate.uid), "Concept", "DUPLICATE_UID_OBSERVATION", duplicate.uid, "Repeated source-local UID observation. Occurrences remain separate and do not imply node identity or owner selection.", { source_ref: manifestPath, uid: duplicate.uid, occurrence_count: duplicate.occurrences.length, status: "SOURCE_SCOPED_UID_COLLISION_OBSERVATION" })
    link(workspaceRoot, "HAS_CONCEPT", id); link(id, "DERIVED_FROM", source(manifestPath))
    for (const [index, occurrence] of duplicate.occurrences.entries()) {
      const occurrenceId = add(uid("UidOccurrence", `${duplicate.uid}|${occurrence.path}|${index}`), "Concept", "UID_OCCURRENCE", `${duplicate.uid} @ ${occurrence.path}`, "One occurrence of a repeated UID in its original source bundle occurrence.", { source_ref: occurrence.path, uid: duplicate.uid, path: occurrence.path, bundle_uid: occurrence.bundleUid ?? "UNDECLARED", status: "NOT_MERGED" })
      link(id, "HAS_UID_OCCURRENCE", occurrenceId); link(occurrenceId, "OCCURS_IN", occurrenceIds.get(occurrence.path)!)
    }
  }
  const bundle = {
    schema_version: "hswm-kg-bundle/v1", bundle_uid: rootUid, status: "SOURCE_BOUND_WORKSPACE_OBSERVATION", nonclaim: "READ_ONLY_WORKSPACE_METADATA_NOT_CANONICAL_STATE_NOT_HSWM_COGNITION_NOT_ROUTING_NOT_LEARNING_NOT_EFFICACY",
    source_accessed_on: "2026-09-22", authority_boundary: "SECONDARY_AI navigation and worktree observation; authority remains in each source occurrence.", artifact_bindings: bindings,
    expected_counts: { nodes: nodes.length, anchors: 0, relations: relations.length }, anchors: [], nodes, relations
  }
  const inventory = {
    schema_version: "hswm-workspace-inventory/v1", scope: "READ_ONLY_TRACKED_ONTOLOGY_JSON_OCCURRENCES", claim_ceiling: "NAVIGATION_AND_ENGINEERING_METADATA_NOT_HSWM_EFFICACY",
    manifest: { path: manifestPath, sha256: bindingByPath.get(manifestPath)!.sha256, entries: manifest.entries.length, query_aliases: manifest.entries.reduce((count: number, entry: any) => count + entry.queries.length, 0), workflows: manifest.workflows.length },
    captured_ontology_json_paths: ontologyPaths, tracked_ontology_json_count: ontologyPaths.length, recognized_bundle_count: bundles.length, non_bundle_json_count: ontologyPaths.length - bundles.length,
    inspection_errors: inspections.filter(row => row.error !== null).map(row => ({ path: row.path, error: row.error })), summary,
    bundle_occurrences: bundles.map(item => ({ ...item, binding_observations: bindingObservations.filter(observation => observation.bundle === item.path).map(observation => ({ path: observation.binding.path, expected_sha256: observation.binding.sha256, actual_sha256: observation.actual, status: observation.status })) })),
    interpretation: "Occurrences are source scoped. This inventory does not union nodes, select a canonical owner, repair old digests, or represent HSWM cognition."
  }
  const bundleBytes = Buffer.from(canonical(bundle));
  Either.getOrThrowWith(decodeKgBundleSource({ sourceId: "workspace", rawBytes: bundleBytes }, "v2"), error => error)
  await mkdir("docs/operations/artifacts/hswm_workspace_2026-09-22", { recursive: true })
  await writeFile(outputPath, bundleBytes, { flag: "wx" })
  await writeFile(inventoryPath, canonical(inventory), { flag: "wx" })
  console.log(JSON.stringify({ path: outputPath, sha256: sha(bundleBytes), inventory: inventoryPath, tracked_ontology_json: ontologyPaths.length, recognized_bundles: bundles.length, ...bundle.expected_counts }))
}
await main()
