/** Pure TS compiler for the research-tooling curation records; I/O is outside this module. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"

export class ResearchToolingError extends Data.TaggedError("ResearchToolingError")<{
  readonly code: "INPUT_INVALID" | "REFERENCE_INVALID" | "ASSESSMENT_INVALID" | "SOURCE_MISSING"
  readonly detail: string
}> {}
export interface FixedGitSource { readonly path: string; readonly bytes: Uint8Array }
export interface ResearchToolingInput { readonly inventory: unknown; readonly findings: ReadonlyArray<unknown>; readonly integrated: unknown; readonly fixedGitSources?: ReadonlyArray<FixedGitSource>; readonly rawCurationFiles?: ReadonlyArray<FixedGitSource>; readonly compilerAndQueryPins?: ReadonlyArray<FixedGitSource> }
export interface ResearchToolingCompile { readonly catalog: Readonly<Record<string, unknown>>; readonly bundle: Readonly<Record<string, unknown>> }
const UID = "sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13"
const fail = <A = never>(code: ResearchToolingError["code"], detail: string): Either.Either<A, ResearchToolingError> => Either.left(new ResearchToolingError({ code, detail }))
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v)
const array = (v: unknown): readonly unknown[] => Array.isArray(v) ? v : []
const id = (v: unknown): v is string => typeof v === "string" && v.length > 0
const sha256 = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const uid = (kind: string, scope: string, value: string): string => `sym:AbstractNode:hswm-research-tooling-${kind}-${createHash("sha256").update(`${scope}:${value}`).digest("hex").slice(0, 20)}`
const basePath = (value: string): string => value.split("#", 1)[0] ?? value
const safeProps = (row: Record<string, unknown>): Record<string, unknown> => {
  const reserved = new Set(["name", "description", "status", "authority_class", "standard_graph_role", "responsibility_owner", "claim_boundary", "domain", "kind", "plane", "semantic_roles"])
  return Object.fromEntries(Object.entries(row).flatMap(([key, value]) => typeof value === "string" || typeof value === "number" || typeof value === "boolean" || (Array.isArray(value) && value.every((item) => typeof item === "string" || typeof item === "number" || typeof item === "boolean")) ? [[reserved.has(key) ? `source_${key}` : key, value]] : []))
}
const sortedJson = (value: unknown): unknown => Array.isArray(value) ? value.map(sortedJson) : object(value) ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedJson(value[key])])) : value
const encodedSortedJson = (value: unknown): Uint8Array => new TextEncoder().encode(`${JSON.stringify(sortedJson(value), null, 2)}\n`)
const node = (value: string, name: string, role: string, properties: Record<string, unknown>) => Object.freeze({ uid: value, labels: ["Concept", "AbstractNode"], properties: Object.freeze({ name, description: name, standard_graph_role: role, authority_class: "SECONDARY_AI", ontology_authority_class_v1: "SECONDARY_AI", responsibility_owner: "hswm:research-tooling:2026-09-13", status: "SOURCE_BOUND_RESEARCH_TOOLING", claim_boundary: "TOOLING_PROJECTION_NOT_HSWM_COGNITION_NOT_CAUSAL_EFFICACY", projection_nonclaim: "TOOLING_PROJECTION_NOT_HSWM_COGNITION_NOT_CAUSAL_EFFICACY", ontology_sensitivity_v1: "NORMAL", ontology_record_lifecycle_v1: "ACTIVE", ontology_epistemic_state_v1: "PENDING", ontology_review_required_v1: true, ontology_canonical_scope_v1: "AI_ANALYSIS_NOT_USER_RATIFIED", ontology_domain_v1: "AI", ontology_kind_v1: "CONCEPT", ontology_plane_v1: "RESEARCH_PROJECTION", ontology_semantic_roles_v1: [role], ...properties }) })
const edge = (from_uid: string, type: string, to_uid: string) => Object.freeze({ from_uid, type, to_uid, authority_class: "SECONDARY_AI", scope: "SOURCE_BOUND_RESEARCH_TOOLING", status: "PROJECTION_ONLY" })

export const compileResearchTooling = (input: ResearchToolingInput): Either.Either<ResearchToolingCompile, ResearchToolingError> => {
  if (!object(input.inventory) || !object(input.integrated) || input.findings.some((x) => !object(x))) return fail("INPUT_INVALID", "all curation inputs must be objects")
  const capabilities = array(input.inventory["existing_capabilities"]), requirements = array(input.inventory["requirements"]), assessments = array(input.integrated["assessments"])
  const candidates: Array<{ readonly scope: string; readonly row: Record<string, unknown> }> = []
  const sources = new Map<string, Set<string>>()
  for (let i = 0; i < input.findings.length; i += 1) {
    const finding = input.findings[i]! as Record<string, unknown>; const scope = ["reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json"][i]!; const ids = new Set<string>()
    for (const source of array(finding["sources"])) { if (!object(source) || !id(source["id"]) || ids.has(source["id"])) return fail("REFERENCE_INVALID", "duplicate or invalid scoped source ID"); ids.add(source["id"]) }
    sources.set(scope, ids)
    for (const candidate of array(finding["candidates"])) {
      if (!object(candidate) || !id(candidate["id"]) || !array(candidate["source_ids"]).every(id) || array(candidate["source_ids"]).length === 0 || array(candidate["source_ids"]).some((x) => !ids.has(x as string))) return fail("REFERENCE_INVALID", "candidate has a missing source")
      candidates.push({ scope, row: candidate })
    }
  }
  const candidateIds = new Set(candidates.map((x) => x.row["id"] as string))
  if (assessments.length !== candidates.length || new Set(assessments.map((x) => object(x) ? x["candidate_id"] : "")).size !== candidates.length) return fail("ASSESSMENT_INVALID", "each candidate requires exactly one assessment")
  for (const assessment of assessments) if (!object(assessment) || !id(assessment["candidate_id"]) || !candidateIds.has(assessment["candidate_id"]) || assessment["decision"] === "ADOPTED" || !object(assessment["qualification"]) || assessment["qualification"]["status"] !== "PROPOSED_NOT_EXECUTED") return fail("ASSESSMENT_INVALID", "assessment is invalid or promotes an unexecuted draft")
  const nodes: Array<ReturnType<typeof node>> = [node(UID, "HSWM 과학 연구 도구·최신 표준 — 근거·요구사항·검증 과제", "RESEARCH_TOOLING_ROOT", { source_commit: "c57f39a8c33bb86d19cfcaa40b880b944707e53d", curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/integrated-assessment.json", curation_source_pointer: "/conceptual_delta" })]; const relations: Array<ReturnType<typeof edge>> = [edge(UID, "REFERS_TO", "sym:Concept:hswm"), edge(UID, "REFERS_TO", "sym:AbstractNode:hswm-knowledge-map-discovery-2026-09-13")]
  const fixed = new Map((input.fixedGitSources ?? []).map((source) => [source.path, source.bytes] as const))
  const capNodes = new Map<string, string>()
  const capIndex = new Map<string, number>()
  const reqIndex = new Map<string, number>()
  for (const [index, row] of capabilities.entries()) {
    if (!object(row) || !id(row["id"])) return fail("INPUT_INVALID", "invalid capability")
    capIndex.set(row["id"], index)
  }
  for (const [index, row] of requirements.entries()) {
    if (!object(row) || !id(row["id"]) || !array(row["existing_capability_ids"]).every((value) => id(value) && capIndex.has(value))) return fail("REFERENCE_INVALID", "invalid requirement")
    reqIndex.set(row["id"], index)
  }
  const descriptors = new Map<string, string>()
  const addDescriptor = (path: string, sourcePointer: string): Either.Either<void, ResearchToolingError> => {
    if (descriptors.has(path)) return Either.right(undefined)
    const bytes = fixed.get(path)
    if (!bytes) return fail("SOURCE_MISSING", `fixed Git source missing: ${path}`)
    const value = uid("fixed-git-source", "fixed", path)
    descriptors.set(path, value)
    nodes.push(node(value, `Fixed Git source: ${path}`, "FIXED_GIT_SOURCE_DESCRIPTOR", { source_path: path, source_commit: "c57f39a8c33bb86d19cfcaa40b880b944707e53d", source_sha256: sha256(bytes), source_byte_length: bytes.byteLength, curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/repository-gap-inventory.json", curation_source_pointer: sourcePointer }))
    relations.push(edge(UID, "HAS_SOURCE", value))
    return Either.right(undefined)
  }
  for (const row of capabilities) {
    const capability = row as Record<string, unknown>
    for (const [evidenceIndex, evidence] of array(capability["evidence"]).entries()) {
      if (!object(evidence) || !id(evidence["path"]) || !id(evidence["sha256"])) return fail("INPUT_INVALID", "invalid capability evidence")
      const descriptor = addDescriptor(basePath(evidence["path"]), `/existing_capabilities/${capIndex.get(capability["id"] as string)}/evidence/${evidenceIndex}`)
      if (Either.isLeft(descriptor)) return Either.left(descriptor.left)
      const bytes = fixed.get(basePath(evidence["path"]))
      if (!bytes || sha256(bytes) !== evidence["sha256"]) return fail("SOURCE_MISSING", "inventory evidence hash differs from fixed Git source")
    }
  }
  const requirementNodes = new Map<string, string>()
  for (const row of requirements) {
    const requirement = row as Record<string, unknown>
    for (const reference of array(requirement["source_paths"])) {
      if (!id(reference)) return fail("INPUT_INVALID", "invalid requirement source")
      const descriptor = addDescriptor(basePath(reference), `/requirements/${reqIndex.get(requirement["id"] as string)}/source_paths`)
      if (Either.isLeft(descriptor)) return Either.left(descriptor.left)
    }
  }
  for (const row of capabilities) {
    const capability = row as Record<string, unknown>
    const value = uid("capability", "repository-gap-inventory.json", capability["id"] as string)
    capNodes.set(capability["id"] as string, value)
    nodes.push(node(value, String(capability["capability"]), "EXISTING_CAPABILITY", { source_id: capability["id"], ...safeProps(capability), curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/repository-gap-inventory.json", curation_source_pointer: `/existing_capabilities/${capIndex.get(capability["id"] as string)}` }))
    relations.push(edge(UID, "HAS_CONCEPT", value))
    for (const [evidenceIndex, evidence] of array(capability["evidence"]).entries()) {
      const proof = evidence as Record<string, unknown>
      const evidenceUid = uid("capability-evidence", "repository-gap-inventory.json", `${capability["id"]}:${proof["path"]}`)
      nodes.push(node(evidenceUid, `Evidence: ${capability["id"]}`, "CAPABILITY_EVIDENCE", { ...safeProps(proof), curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/repository-gap-inventory.json", curation_source_pointer: `/existing_capabilities/${capIndex.get(capability["id"] as string)}/evidence/${evidenceIndex}` }))
      relations.push(edge(value, "HAS_SOURCE", evidenceUid), edge(evidenceUid, "HAS_SOURCE", descriptors.get(basePath(proof["path"] as string))!))
    }
  }
  for (const row of requirements) {
    const requirement = row as Record<string, unknown>
    const value = uid("requirement", "repository-gap-inventory.json", requirement["id"] as string)
    requirementNodes.set(requirement["id"] as string, value)
    nodes.push(node(value, String(requirement["need"]), "RESEARCH_REQUIREMENT", { source_id: requirement["id"], ...safeProps(requirement), curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/repository-gap-inventory.json", curation_source_pointer: `/requirements/${reqIndex.get(requirement["id"] as string)}` }))
    relations.push(edge(UID, "HAS_CONCEPT", value))
    for (const capabilityId of array(requirement["existing_capability_ids"])) relations.push(edge(value, "REQUIRES", capNodes.get(capabilityId as string)!))
    for (const reference of new Set(array(requirement["source_paths"]).map((item) => basePath(item as string)))) relations.push(edge(value, "HAS_SOURCE", descriptors.get(reference)!))
  }
  const sourceNodes = new Map<string, string>()
  const sourceIndex = new Map<string, number>()
  const candidateIndex = new Map<string, number>()
  for (const filename of ["reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json"]) {
    let index = 0
    for (const item of input.findings) {
      if (!object(item)) continue
      const matching = ["reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json"][input.findings.indexOf(item)]
      if (matching !== filename) continue
      for (const source of array(item["sources"])) { if (object(source)) sourceIndex.set(`${filename}:${source["id"]}`, index); index += 1 }
    }
    index = 0
    for (const item of candidates) if (item.scope === filename) { candidateIndex.set(`${filename}:${item.row["id"]}`, index); index += 1 }
  }
  for (const item of candidates) {
    const sourceIds = array(item.row["source_ids"])
    const scopedIds = new Set(array((input.findings[["reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json"].indexOf(item.scope)] as Record<string, unknown>)["sources"]).map((source) => object(source) ? source["id"] : undefined))
    if (!sourceIds.every((sourceId) => id(sourceId) && scopedIds.has(sourceId))) return fail("REFERENCE_INVALID", "candidate has a missing source")
  }
  for (let findingIndex = 0; findingIndex < input.findings.length; findingIndex += 1) {
    const finding = input.findings[findingIndex]! as Record<string, unknown>
    const filename = ["reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json"][findingIndex]!
    for (const source of array(finding["sources"])) {
      if (!object(source) || !id(source["id"]) || !id(source["title"]) || !id(source["url"])) return fail("INPUT_INVALID", "invalid research source")
      const path = source["url"].startsWith("https://github.com/gj3447/HSWM/blob/main/") ? source["url"].slice("https://github.com/gj3447/HSWM/blob/main/".length) : undefined
      if (path) {
        const descriptor = addDescriptor(path, `/sources/${sourceIndex.get(`${filename}:${source["id"]}`)}`)
        if (Either.isLeft(descriptor)) return Either.left(descriptor.left)
      }
      const value = uid("research-source", filename, source["id"])
      sourceNodes.set(`${filename}:${source["id"]}`, value)
      nodes.push(node(value, source["title"], "RESEARCH_SOURCE", { source_file: filename, source_id: source["id"], source_scope: path ? "LOCAL_FIXED_GIT" : "EXTERNAL_WEB_OBSERVATION_ONLY", source_cut: path ? "c57f39a8c33bb86d19cfcaa40b880b944707e53d" : "NOT_ARCHIVED_REMOTE_WEBPAGE", ...safeProps(source), curation_source_path: `_research/graph_standards/research_tooling_2026-09-13/${filename}`, curation_source_pointer: `/sources/${sourceIndex.get(`${filename}:${source["id"]}`)}` }))
      relations.push(edge(UID, "HAS_SOURCE", value))
      if (path) relations.push(edge(value, "HAS_SOURCE", descriptors.get(path)!))
    }
  }
  for (const item of candidates) {
    const value = uid("candidate", item.scope, item.row["id"] as string)
    nodes.push(node(value, String(item.row["name"] ?? item.row["id"]), "TOOL_CANDIDATE", { source_file: item.scope, source_id: item.row["id"], ...safeProps(item.row), curation_source_path: `_research/graph_standards/research_tooling_2026-09-13/${item.scope}`, curation_source_pointer: `/candidates/${candidateIndex.get(`${item.scope}:${item.row["id"]}`)}` }))
    relations.push(edge(UID, "HAS_CONCEPT", value))
    for (const sourceId of array(item.row["source_ids"])) relations.push(edge(value, "HAS_SOURCE", sourceNodes.get(`${item.scope}:${sourceId}`)!))
  }
  for (const item of candidates) {
    const assessment = assessments.find((value) => object(value) && value["candidate_id"] === item.row["id"])
    if (!object(assessment)) return fail("ASSESSMENT_INVALID", "candidate has no assessment")
    const evidence = uid("adoption-evidence", item.scope, item.row["id"] as string)
    nodes.push(node(evidence, `Adoption evidence: ${item.row["name"]}`, "ADOPTION_EVIDENCE", { statement: item.row["adoption_evidence"], evidence_class: assessment["adoption_evidence_class"], candidate_id: item.row["id"], curation_source_path: `_research/graph_standards/research_tooling_2026-09-13/${item.scope}`, curation_source_pointer: `/candidates/${candidateIndex.get(`${item.scope}:${item.row["id"]}`)}/adoption_evidence` }))
    const candidate = uid("candidate", item.scope, item.row["id"] as string)
    relations.push(edge(candidate, "HAS_CONCEPT", evidence))
    for (const sourceId of array(item.row["source_ids"])) relations.push(edge(evidence, "HAS_SOURCE", sourceNodes.get(`${item.scope}:${sourceId}`)!))
  }
  const assessmentIndex = new Map<string, number>()
  for (const [index, row] of assessments.entries()) {
    if (!object(row) || !id(row["candidate_id"])) return fail("ASSESSMENT_INVALID", "invalid assessment")
    assessmentIndex.set(row["candidate_id"], index)
  }
  for (const row of assessments) {
    const assessment = row as Record<string, unknown>
    const candidate = candidates.find((item) => item.row["id"] === assessment["candidate_id"])
    if (!candidate) return fail("ASSESSMENT_INVALID", "assessment refers to missing candidate")
    const value = uid("assessment", "integrated-assessment.json", assessment["candidate_id"] as string)
    nodes.push(node(value, `Assessment: ${assessment["candidate_id"]}`, "INTEGRATED_ASSESSMENT", { ...safeProps(assessment), curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/integrated-assessment.json", curation_source_pointer: `/assessments/${assessmentIndex.get(assessment["candidate_id"] as string)}` }))
    relations.push(edge(UID, "HAS_CONCEPT", value), edge(value, "REFERS_TO", uid("candidate", candidate.scope, assessment["candidate_id"] as string)))
    for (const requirementId of array(assessment["requirement_ids"])) relations.push(edge(value, "REQUIRES", requirementNodes.get(requirementId as string)!))
    for (const capabilityId of array(assessment["existing_capability_ids"])) relations.push(edge(value, "PRESERVES", capNodes.get(capabilityId as string)!))
    const qualification = assessment["qualification"]
    if (!object(qualification) || !id(qualification["id"]) || !id(qualification["title"])) return fail("ASSESSMENT_INVALID", "invalid qualification")
    const qualificationUid = uid("qualification", "integrated-assessment.json", qualification["id"])
    nodes.push(node(qualificationUid, qualification["title"], "QUALIFICATION", { ...safeProps(qualification), curation_source_path: "_research/graph_standards/research_tooling_2026-09-13/integrated-assessment.json", curation_source_pointer: `/assessments/${assessmentIndex.get(assessment["candidate_id"] as string)}/qualification` }))
    relations.push(edge(value, "HAS_CONCEPT", qualificationUid))
  }
  const sourceBound = input.rawCurationFiles !== undefined && input.compilerAndQueryPins !== undefined
  const raw = new Map((input.rawCurationFiles ?? []).map((file) => [file.path, file.bytes] as const))
  if (sourceBound && raw.size !== 5) return fail("SOURCE_MISSING", "source-bound catalog requires five raw curation files")
  const researchSources: Array<Record<string, unknown>> = []
  for (const item of candidates) for (const source of array((input.findings[["reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json"].indexOf(item.scope)] as Record<string, unknown>)["sources"])) {
    if (!object(source)) continue
    const path = id(source["url"]) && source["url"].startsWith("https://github.com/gj3447/HSWM/blob/main/") ? source["url"].slice("https://github.com/gj3447/HSWM/blob/main/".length) : undefined
    const record = { source_file: item.scope, source_id: source["id"], title: source["title"], url: source["url"], organization: source["organization"] ?? null, accessed_on: source["accessed_on"] ?? null, source_date: source["source_date"] ?? null, kind: source["kind"] ?? null, finding: source["finding"] ?? null, source_scope: path ? "LOCAL_FIXED_GIT" : "EXTERNAL_WEB_OBSERVATION_ONLY", source_cut: path ? "c57f39a8c33bb86d19cfcaa40b880b944707e53d" : "NOT_ARCHIVED_REMOTE_WEBPAGE", fixed_git_descriptor_uid: path ? descriptors.get(path) ?? null : null }
    if (!researchSources.some((existing) => existing["source_file"] === record.source_file && existing["source_id"] === record.source_id)) researchSources.push(record)
  }
  const lexical = (left: string, right: string): number => left < right ? -1 : left > right ? 1 : 0
  researchSources.sort((left, right) => lexical(`${left["source_file"]}:${left["source_id"]}`, `${right["source_file"]}:${right["source_id"]}`))
  const fixedDescriptors = [...descriptors.entries()].sort(([left], [right]) => lexical(left, right)).map(([path, descriptorUid]) => ({ source_path: path, source_commit: "c57f39a8c33bb86d19cfcaa40b880b944707e53d", sha256: sha256(fixed.get(path)!), descriptor_uid: descriptorUid }))
  const inputs = sourceBound ? [...(input.rawCurationFiles ?? []), ...(input.compilerAndQueryPins ?? [])].map((file) => ({ path: file.path, sha256: sha256(file.bytes) })) : []
  const catalog = Object.freeze(sourceBound ? { schema_version: "hswm-research-tooling-source-catalog/v1", source_commit: "c57f39a8c33bb86d19cfcaa40b880b944707e53d", inputs, candidate_count: candidates.length, assessment_count: assessments.length, research_sources: researchSources, fixed_git_source_descriptors: fixedDescriptors, research_source_counts: { external_web_observation_only: researchSources.filter((row) => row["source_scope"] === "EXTERNAL_WEB_OBSERVATION_ONLY").length, local_fixed_git: researchSources.filter((row) => row["source_scope"] === "LOCAL_FIXED_GIT").length }, observation_boundary: "Remote web pages are recorded as dated observations in findings inputs; their page bytes are not archived or content-hashed by this projection." } : { schema_version: "hswm-research-tooling-source-catalog/v2-ts", capability_count: capabilities.length, requirement_count: requirements.length, candidate_count: candidates.length, assessment_count: assessments.length })
  const uniqueRelations = [...new Map(relations.map((relation) => [`${relation.from_uid}:${relation.type}:${relation.to_uid}`, relation] as const)).values()]
  const bundle = Object.freeze({ schema_version: "hswm-scientific-research-tooling/v1", bundle_uid: UID, status: "SOURCE_BOUND_RESEARCH_TOOLING_NOT_EFFICACY", nonclaim: "TOOLING_PROJECTION_NOT_HSWM_COGNITION_NOT_CAUSAL_EFFICACY", authority_boundary: "SECONDARY_AI source-bound research tooling curation; not an adoption, efficacy, or HSWM cognition claim.", source_accessed_on: "2026-09-13", artifact_bindings: sourceBound ? [{ path: "docs/research/artifacts/hswm_research_tooling_2026-09-13/source-catalog.json", sha256: sha256(encodedSortedJson(catalog)) }, { path: "ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_DISCOVERY_2026-09-13.v1.json", sha256: "f97838782144ba09d290a2e4ce9fc71868fbff0bee8e8aab6bfba9f81eecb589" }] : [], expected_counts: { nodes: nodes.length, anchors: 2, relations: uniqueRelations.length }, anchors: [{ uid: "sym:AbstractNode:hswm-knowledge-map-discovery-2026-09-13", name: "HSWM 전체 지식 지도 — 문서·표준 그래프 질의 진입점", required_labels: ["Concept", "AbstractNode"] }, { uid: "sym:Concept:hswm", name: "HSWM", required_labels: ["Concept"] }], nodes: nodes.sort((a, b) => a.uid.localeCompare(b.uid)), relations: uniqueRelations.sort((a, b) => `${a.from_uid}:${a.type}:${a.to_uid}`.localeCompare(`${b.from_uid}:${b.type}:${b.to_uid}`)) })
  return Either.right(Object.freeze({ catalog, bundle }))
}

export const researchToolingSourceIndex = (catalog: Readonly<Record<string, unknown>>): Either.Either<Uint8Array, ResearchToolingError> => {
  if (!id(catalog["source_commit"]) || !Array.isArray(catalog["research_sources"])) return fail("INPUT_INVALID", "invalid source catalog")
  const compact = (value: unknown): string => String(value ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ")
  const lines = ["# HSWM research-tooling source appendix — 2026-09-13", "", `Fixed Git source cut: \`${catalog["source_commit"]}\`. Remote webpages below are dated input observations; this projection does not archive or hash their page bytes.`, "", "| Scoped ID | Title | URL | Organization | Date | Kind | Source scope | Finding |", "|---|---|---|---|---|---|---|---|"]
  for (const source of catalog["research_sources"]) {
    if (!object(source) || !id(source["source_file"]) || !id(source["source_id"]) || !id(source["title"]) || !id(source["url"])) return fail("INPUT_INVALID", "invalid catalog source")
    const path = source["url"].startsWith("https://github.com/gj3447/HSWM/blob/main/") ? source["url"].slice("https://github.com/gj3447/HSWM/blob/main/".length) : undefined
    const href = source["source_scope"] === "EXTERNAL_WEB_OBSERVATION_ONLY" ? source["url"] : `https://github.com/gj3447/HSWM/blob/${catalog["source_commit"]}/${path}`
    lines.push(`| ${compact(`${source["source_file"]}:${source["source_id"]}`)} | ${compact(source["title"])} | [${compact(source["url"])}](${href}) | ${["organization", "source_date", "kind", "source_scope", "finding"].map((key) => compact(source[key])).join(" | ")} |`)
  }
  return Either.right(new TextEncoder().encode(`${lines.join("\n")}\n`))
}
