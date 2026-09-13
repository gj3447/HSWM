/** Pure, source-bound compiler for the HSWM knowledge-map curation inputs.
 * It is navigation metadata only: never a canonical write, learning path, or efficacy claim.
 */
import { createHash } from "node:crypto"
import { Buffer } from "node:buffer"
import { Data, Either } from "effect"

export const KNOWLEDGE_MAP_DOMAIN_V1 = "hswm-knowledge-map-domain/v1" as const
export const KNOWLEDGE_MAP_UID = "sym:AbstractNode:hswm-knowledge-map-2026-09-13" as const
export class KnowledgeMapError extends Data.TaggedError("KnowledgeMapError")<{
  readonly code: "INPUT_INVALID" | "COVERAGE_INVALID" | "SOURCE_MISSING" | "IDENTITY_INVALID"
  readonly detail: string
}> {}
export interface SourceBytes { readonly path: string; readonly bytes: Uint8Array }
export interface KnowledgeMapInput { readonly topics: unknown; readonly coverage: unknown; readonly live: unknown; readonly sources: ReadonlyArray<SourceBytes>; readonly rawCurationFiles?: ReadonlyArray<SourceBytes>; readonly compilerAndQueryPins?: ReadonlyArray<SourceBytes> }
export interface KnowledgeMapCompile { readonly catalog: Readonly<Record<string, unknown>>; readonly bundle: Readonly<Record<string, unknown>> }
const fail = <A = never>(code: KnowledgeMapError["code"], detail: string): Either.Either<A, KnowledgeMapError> => Either.left(new KnowledgeMapError({ code, detail }))
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v)
const list = (v: unknown): readonly unknown[] => Array.isArray(v) ? v : []
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0
const sha = (v: Uint8Array): string => createHash("sha256").update(v).digest("hex")
const sortedJson = (value: unknown): unknown => Array.isArray(value) ? value.map(sortedJson) : object(value) ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedJson(value[key])])) : value
const encodedSortedJson = (value: unknown): Uint8Array => new TextEncoder().encode(`${JSON.stringify(sortedJson(value), null, 2)}\n`)
/** UTF-8 byte order equals Unicode code-point order for valid JSON strings. */
const lexical = (left: string, right: string): number => Buffer.compare(Buffer.from(left, "utf8"), Buffer.from(right, "utf8"))
const sourceUid = (path: string): string => `${KNOWLEDGE_MAP_UID}-source-${createHash("sha256").update(path).digest("hex").slice(0, 16)}`
const json = (bytes: Uint8Array): unknown => JSON.parse(new TextDecoder().decode(bytes)) as unknown
const pointer = (value: unknown, path: string): unknown => path.slice(1).split("/").reduce<unknown>((at, token) => Array.isArray(at) ? at[Number(token)] : object(at) ? at[token] : undefined, value)
const basePath = (value: string): string => value.split("#", 1)[0] ?? value
const node = (uid: string, name: string, role: string, properties: Record<string, unknown>) => Object.freeze({ uid, labels: ["Concept", "AbstractNode"], properties: Object.freeze({ name, description: name, standard_graph_role: role, authority_class: "SECONDARY_AI", ontology_authority_class_v1: "SECONDARY_AI", responsibility_owner: "hswm:knowledge-map:2026-09-13", status: "SOURCE_BOUND_NAVIGATION", claim_boundary: "SOURCE_BOUND_NAVIGATION_NOT_NEW_DESIGN_NOT_CANONICAL_STATE_NOT_LEARNING_NOT_EFFICACY", projection_nonclaim: "SOURCE_BOUND_NAVIGATION_NOT_NEW_DESIGN_NOT_CANONICAL_STATE_NOT_LEARNING_NOT_EFFICACY", source_commit: "5cb22703cf42128dd204966087594ad8561a554d", ...properties }) })
const edge = (from_uid: string, type: string, to_uid: string, scope = "SOURCE_BOUND_NAVIGATION_ONLY") => Object.freeze({ from_uid, type, to_uid, authority_class: "SECONDARY_AI", scope, status: "PROJECTION_ONLY" })

export const compileKnowledgeMap = (input: KnowledgeMapInput): Either.Either<KnowledgeMapCompile, KnowledgeMapError> => {
  if (!object(input.topics) || !object(input.coverage) || !object(input.live)) return fail("INPUT_INVALID", "curation inputs must be JSON objects")
  if (input.topics["authority"] !== "SECONDARY_AI" || input.coverage["authority"] !== "SECONDARY_AI") return fail("INPUT_INVALID", "curation authority mismatch")
  const topics = list(input.topics["topics"]), obligations = list(input.coverage["obligations"]), records = list(input.live["records"]), crossLinks = list(input.coverage["cross_links"])
  const expected = new Set([...Array.from({ length: 8 }, (_, i) => `FCL-${i + 1}`), ...Array.from({ length: 8 }, (_, i) => `CR-${i}`)])
  if (obligations.length !== 16 || new Set(obligations.map((x) => object(x) ? x["id"] : "")).size !== 16 || obligations.some((x) => !object(x) || !expected.has(x["id"] as string))) return fail("COVERAGE_INVALID", "FCL/CR coverage must contain exactly FCL-1..8 and CR-0..7")
  for (const observation of records) {
    if (!object(observation) || !text(observation["uid"]) || !Array.isArray(observation["matches"])) return fail("IDENTITY_INVALID", "malformed live identity observation")
    if (observation["resolution"] === "NOT_FOUND" && observation["matches"].length !== 0) return fail("IDENTITY_INVALID", "NOT_FOUND has matches")
    if (observation["resolution"] === "RESOLVED_UNIQUE" && (observation["matches"].length !== 1 || !object(observation["matches"][0]) || observation["matches"][0]["uid"] !== observation["uid"])) return fail("IDENTITY_INVALID", "RESOLVED_UNIQUE requires one identical UID")
    if (observation["resolution"] !== "NOT_FOUND" && observation["resolution"] !== "RESOLVED_UNIQUE") return fail("IDENTITY_INVALID", "unknown live identity resolution")
  }
  const source = new Map(input.sources.map((item) => [item.path, item] as const))
  const parsed = new Map<string, unknown>()
  for (const obligation of obligations) {
    if (!object(obligation) || !text(obligation["source_path"]) || !text(obligation["source_pointer"])) return fail("INPUT_INVALID", "obligation lacks source binding")
    const item = source.get(obligation["source_path"]); if (!item) return fail("SOURCE_MISSING", `source missing: ${obligation["source_path"]}`)
    const document = parsed.get(item.path) ?? json(item.bytes); parsed.set(item.path, document)
    const selected = pointer(document, obligation["source_pointer"])
    if (!object(selected) || (text(obligation["existing_uid"]) && selected["uid"] !== obligation["existing_uid"]) || (String(obligation["id"]).startsWith("CR-") && selected["id"] !== obligation["id"])) return fail("IDENTITY_INVALID", "obligation source pointer mismatch")
  }
  const observations = new Map(records.filter(object).map((x) => [x["uid"] as string, x] as const))
  const anchors = new Map<string, Record<string, unknown>>()
  const reference = (owner: string, target: unknown, relations: Array<ReturnType<typeof edge>>): void => {
    if (!text(target)) return
    const observation = observations.get(target)
    if (observation?.["resolution"] !== "RESOLVED_UNIQUE") return
    const match = list(observation["matches"])[0]
    if (!object(match) || !text(match["name"]) || !Array.isArray(match["labels"])) return
    anchors.set(target, { uid: target, name: match["name"], required_labels: [...match["labels"]].sort(lexical) })
    relations.push(edge(owner, "REFERS_TO", target, "LIVE_IDENTITY_REFERENCE_ONLY_NOT_SOURCE_REVISION_EQUIVALENCE"))
  }
  const entrypoints = new Set(topics.flatMap((topic) => object(topic) ? list(topic["entrypoints"]).flatMap((entry) => object(entry) && text(entry["path"]) ? [basePath(entry["path"])] : []) : []))
  const overrides = new Map(list(input.topics["historical_overrides"]).filter(object).map((row) => [basePath(String(row["path"])), row] as const))
  const sourceRecords: Array<Record<string, unknown>> = []
  const nodes: Array<ReturnType<typeof node>> = [node(KNOWLEDGE_MAP_UID, "HSWM 전체 지식 지도 — 기존 설계·구현·증명·실험·남은 의무", "KNOWLEDGE_MAP", { topic_count: topics.length, obligation_count: 16, source_count: source.size, conceptual_delta: "Connect existing artifacts and distinguish four evidence axes; no new HSWM target or success criterion." })]
  const relations: Array<ReturnType<typeof edge>> = []
  const catalogUid = `${KNOWLEDGE_MAP_UID}-catalog`; nodes.push(node(catalogUid, "Declared-scope complete source catalog", "SOURCE_CATALOG", {})); relations.push(edge(KNOWLEDGE_MAP_UID, "HAS_CONCEPT", catalogUid))
  reference(KNOWLEDGE_MAP_UID, "sym:Concept:hswm", relations)
  for (const item of [...source.values()].sort((a, b) => lexical(a.path, b.path))) {
    const id = sourceUid(item.path); const parsedSource = item.path.endsWith(".json") ? json(item.bytes) : {}; if (item.path.endsWith(".json")) parsed.set(item.path, parsedSource); const bundleUid = object(parsedSource) ? parsedSource["bundle_uid"] : undefined; const observation = text(bundleUid) ? observations.get(bundleUid) : undefined
    const override = overrides.get(item.path); const navigation = override ? (item.path.includes("CORE_RESPONSIBILITY") ? "RETIRED_TARGET_FORMAT" : "HISTORICAL_REFERENCE") : entrypoints.has(item.path) ? "CURRENT_ENTRYPOINT" : "CATALOGUED_SNAPSHOT"
    sourceRecords.push(Object.freeze({ path: item.path, sha256: sha(item.bytes), byte_length: item.bytes.byteLength, source_commit: "5cb22703cf42128dd204966087594ad8561a554d", source_bundle_uid: text(bundleUid) ? bundleUid : null, raw_source_status: object(parsedSource) && text(parsedSource["status"]) ? parsedSource["status"] : "NOT_DECLARED", source_format: object(parsedSource) && Array.isArray(parsedSource["nodes"]) ? "NODE_BUNDLE" : item.path.endsWith(".json") ? "STRUCTURED_JSON" : "DOCUMENT", navigation_status: navigation, live_resolution: observation?.["resolution"] ?? "NOT_CHECKED", ...(override ? { navigation_reason: override["reason"] } : {}) }))
    nodes.push(node(id, item.path.split("/").at(-1) ?? item.path, "SOURCE_SNAPSHOT", { source_path: item.path, source_sha256: sha(item.bytes), source_byte_length: item.bytes.byteLength, source_commit: "5cb22703cf42128dd204966087594ad8561a554d", ...(text(bundleUid) ? { source_bundle_uid: bundleUid } : {}), raw_source_status: object(parsedSource) && text(parsedSource["status"]) ? parsedSource["status"] : "NOT_DECLARED", source_format: object(parsedSource) && Array.isArray(parsedSource["nodes"]) ? "NODE_BUNDLE" : item.path.endsWith(".json") ? "STRUCTURED_JSON" : "DOCUMENT", navigation_status: navigation, live_resolution: observation?.["resolution"] ?? "NOT_CHECKED", ...(override ? { navigation_reason: override["reason"] } : {}) }))
    relations.push(edge(catalogUid, "HAS_SOURCE", id)); if (text(bundleUid)) reference(id, bundleUid, relations)
  }
  for (const topic of topics) {
    if (!object(topic) || !text(topic["id"]) || !text(topic["title"])) return fail("INPUT_INVALID", "invalid knowledge topic")
    const topicUid = `${KNOWLEDGE_MAP_UID}-topic-${topic["id"]}`
    const { id: _id, title: _title, entrypoints: _entrypoints, ...topicProps } = topic
    nodes.push(node(topicUid, topic["title"], "KNOWLEDGE_MAP_TOPIC", { ...topicProps, curation_source_path: "ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json", curation_source_pointer: `/topics/${topics.indexOf(topic)}` }))
    relations.push(edge(KNOWLEDGE_MAP_UID, "HAS_CONCEPT", topicUid))
    for (const entry of list(topic["entrypoints"])) if (object(entry) && text(entry["path"])) { const path = entry["path"].split("#", 1)[0]!; if (source.has(path)) relations.push(edge(topicUid, "HAS_SOURCE", sourceUid(path), `CURATED_ENTRYPOINT: ${String(entry["role"] ?? "existing source")}`)) }
    for (const value of list(topic["existing_uids"])) reference(topicUid, value, relations)
  }
  for (const obligation of obligations) { const row = obligation as Record<string, unknown>; const id = `${KNOWLEDGE_MAP_UID}-obligation-${String(row["id"]).toLowerCase()}`; const { id: _id, title: _title, existing_uid: existingUid, ...obligationProps } = row; nodes.push(node(id, `${row["id"]}: ${row["title"] ?? ""}`, "COVERAGE_OBLIGATION", { obligation_id: row["id"], ...(text(existingUid) ? { existing_uid: existingUid } : {}), ...obligationProps, engineering_status: "SEE_BOUND_IMPLEMENTATION_AND_EVIDENCE_SOURCES", curation_source_path: "ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_COVERAGE_2026-09-13.v1.json" })); relations.push(edge(KNOWLEDGE_MAP_UID, "HAS_CONCEPT", id)); for (const path of [row["source_path"], ...list(row["existing_design_paths"]), ...list(row["evidence_paths"])]) if (text(path) && source.has(basePath(path))) relations.push(edge(id, "HAS_SOURCE", sourceUid(basePath(path)))) }
  for (const obligation of obligations) { const row = obligation as Record<string, unknown>; const owner = `${KNOWLEDGE_MAP_UID}-obligation-${String(row["id"]).toLowerCase()}`; reference(owner, row["existing_uid"], relations); for (const fcl of list(row["mapped_fcl_ids"])) if (text(fcl) && fcl !== row["id"]) relations.push(edge(owner, "REQUIRES", `${KNOWLEDGE_MAP_UID}-obligation-${fcl.toLowerCase()}`, "CURATED_CR_TO_FCL_COVERAGE_NOT_PROOF")) }
  for (const [path, override] of overrides) for (const successor of list(override["successor_paths"])) if (text(successor) && source.has(successor)) relations.push(edge(sourceUid(successor), "PRESERVES", sourceUid(path), "HISTORICAL_REFERENCE_NOT_AUTOMATIC_SUCCESS_OR_EFFICACY"))
  for (let index = 0; index < crossLinks.length; index += 1) { const link = crossLinks[index]; if (!object(link) || !text(link["from_path"]) || !text(link["to_path"]) || !text(link["type"])) return fail("INPUT_INVALID", "invalid cross-link"); const id = `${KNOWLEDGE_MAP_UID}-existing-link-${index + 1}`; const original = text(link["source_path"]) && text(link["source_pointer"]) && parsed.has(link["source_path"]) ? pointer(parsed.get(link["source_path"]), link["source_pointer"]) : undefined; nodes.push(node(id, `Existing ${link["type"]} relation ${index + 1}`, "EXISTING_RELATION_REFERENCE", { original_from_uid: link["from_path"], original_to_uid: link["to_path"], original_relation_type: link["type"], source_path: link["source_path"], source_pointer: link["source_pointer"], description: link["reason"], original_relation_status: object(original) && text(original["status"]) ? original["status"] : "NOT_DECLARED" })); relations.push(edge(KNOWLEDGE_MAP_UID, "HAS_CONCEPT", id)); if (text(link["source_path"]) && source.has(link["source_path"])) relations.push(edge(id, "HAS_SOURCE", sourceUid(link["source_path"]))); reference(id, link["from_path"], relations); reference(id, link["to_path"], relations) }
  const ontologyCount = [...source.keys()].filter((path) => path.startsWith("ontology/") && path.includes("HSWM") && path.endsWith(".json")).length
  const documentCount = [...source.keys()].filter((path) => path.startsWith("docs/") && path.includes("HSWM") && path.endsWith(".md")).length
  const sourceBound = input.rawCurationFiles !== undefined && input.compilerAndQueryPins !== undefined
  const curationInputs = sourceBound ? [...(input.rawCurationFiles ?? []), ...(input.compilerAndQueryPins ?? [])].map((source) => ({ path: source.path, sha256: sha(source.bytes) })) : []
  const catalog = Object.freeze({ schema_version: "hswm-knowledge-map-source-catalog/v1", authority: "SECONDARY_AI", source_commit: "5cb22703cf42128dd204966087594ad8561a554d", scope: { ontology_rule: "tracked ontology/**/*.json containing HSWM in path", ontology_count: ontologyCount, document_rule: "tracked docs/**/*.md containing HSWM in path", document_count: documentCount, additional_sources: "explicit curated entrypoints, coverage references, history successors and repository entrypoints", excluded: ["uncommitted work", "private runtime state and credentials", "external KG payloads", "transitive source payload expansion"], boundary: "Complete inventory for declared path classes; not exhaustive semantic indexing of every repository byte." }, ...(sourceBound ? { curation_inputs: curationInputs } : {}), sources: sourceRecords.sort((a, b) => lexical(String(a["path"]), String(b["path"]))) })
  const relationOrder = (a: ReturnType<typeof edge>, b: ReturnType<typeof edge>): number => lexical(a.from_uid, b.from_uid) || lexical(a.type, b.type) || lexical(a.to_uid, b.to_uid)
  const uniqueRelations = [...new Map(relations.map((relation) => [`${relation.from_uid}:${relation.type}:${relation.to_uid}`, relation] as const)).values()].sort(relationOrder)
  const bundle = Object.freeze({ schema_version: "hswm-knowledge-map-ontology/v1", bundle_uid: KNOWLEDGE_MAP_UID, status: "SOURCE_BOUND_NAVIGATION_NOT_EFFICACY", nonclaim: "SOURCE_BOUND_NAVIGATION_NOT_NEW_DESIGN_NOT_CANONICAL_STATE_NOT_LEARNING_NOT_EFFICACY", authority_boundary: "SECONDARY_AI curation; originals retain their authority; live anchors are identity-only references.", source_accessed_on: "2026-09-13", artifact_bindings: sourceBound ? [{ path: "docs/operations/artifacts/hswm_knowledge_map_2026-09-13/source-catalog.json", sha256: sha(encodedSortedJson(catalog)) }] : [], expected_counts: { nodes: nodes.length, anchors: anchors.size, relations: uniqueRelations.length }, anchors: [...anchors.values()].sort((a, b) => lexical(String(a["uid"]), String(b["uid"]))), nodes: nodes.sort((a, b) => lexical(a.uid, b.uid)), relations: uniqueRelations })
  return Either.right(Object.freeze({ catalog, bundle }))
}

/** Exact declared source scope from the v1 Python catalog, expressed without I/O. */
export const declareKnowledgeMapCatalogPaths = (topicsInput: unknown, coverageInput: unknown, fixedCutPaths: ReadonlyArray<string>): Either.Either<ReadonlyArray<string>, KnowledgeMapError> => {
  if (!object(topicsInput) || !object(coverageInput)) return fail("INPUT_INVALID", "topics and coverage must be objects")
  const tracked = new Set(fixedCutPaths)
  const paths = new Set<string>(["README.md", "INDEX.md", "F1_R8_RESULTS_LOG.md", "ontology/identity/hswm_core/README.md"])
  for (const path of fixedCutPaths) if ((path.startsWith("ontology/") && path.includes("HSWM") && path.endsWith(".json")) || (path.startsWith("docs/") && path.includes("HSWM") && path.endsWith(".md"))) paths.add(path)
  for (const topic of list(topicsInput["topics"])) {
    if (!object(topic)) return fail("INPUT_INVALID", "invalid topic")
    for (const entry of list(topic["entrypoints"])) if (object(entry) && text(entry["path"])) paths.add(basePath(entry["path"]))
  }
  for (const obligation of list(coverageInput["obligations"])) {
    if (!object(obligation) || !text(obligation["source_path"])) return fail("INPUT_INVALID", "invalid obligation source")
    for (const path of [obligation["source_path"], ...list(obligation["existing_design_paths"]), ...list(obligation["evidence_paths"])]) if (text(path)) paths.add(basePath(path))
  }
  for (const link of list(coverageInput["cross_links"])) if (object(link) && text(link["source_path"])) paths.add(basePath(link["source_path"]))
  for (const override of list(topicsInput["historical_overrides"])) {
    if (!object(override) || !text(override["path"])) return fail("INPUT_INVALID", "invalid historical override")
    paths.add(basePath(override["path"])); for (const successor of list(override["successor_paths"])) if (text(successor)) paths.add(basePath(successor))
  }
  const absent = [...paths].filter((path) => !tracked.has(path)); if (absent.length > 0) return fail("SOURCE_MISSING", `declared catalog source absent from fixed cut: ${absent.sort().join(",")}`)
  return Either.right(Object.freeze([...paths].sort((a, b) => a.localeCompare(b))))
}

export const knowledgeMapSourceIndex = (catalog: Readonly<Record<string, unknown>>): Either.Either<Uint8Array, KnowledgeMapError> => {
  const rows = list(catalog["sources"]); if (!text(catalog["source_commit"]) || rows.some((row) => !object(row) || !text(row["path"]) || !text(row["navigation_status"]) || !text(row["source_format"]))) return fail("INPUT_INVALID", "invalid source catalog for index")
  const lines = ["# HSWM 원문 목록 — 2026-09-13", "", `고정 Git source cut: \`${catalog["source_commit"]}\`. 아래 링크는 이 commit의 원문을 가리킵니다.`, "", "전체 목록의 범위는 source-catalog.json에 명시합니다. CURRENT_ENTRYPOINT는 읽기 진입점이며 효능 판정이 아닙니다.", "", "| 원문 | 탐색 상태 | 원문 형식 |", "|---|---|---|"]
  for (const row of rows) {
    if (!object(row)) return fail("INPUT_INVALID", "invalid catalog source record")
    lines.push(`| [${row["path"]}](https://github.com/gj3447/HSWM/blob/${catalog["source_commit"]}/${row["path"]}) | ${row["navigation_status"]} | ${row["source_format"]} |`)
  }
  return Either.right(new TextEncoder().encode(`${lines.join("\n")}\n`))
}
