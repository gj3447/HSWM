import { describe, expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { Either } from "effect"
import { compileKnowledgeMap, declareKnowledgeMapCatalogPaths, knowledgeMapSourceIndex } from "../src/knowledge-map-domain.js"
import { compileResearchTooling } from "../src/research-tooling-domain.js"

const encoder = new TextEncoder()
const obligations = [...Array.from({ length: 8 }, (_, index) => ({ id: `FCL-${index + 1}`, source_path: "fcl.json", source_pointer: `/${index}`, existing_uid: `sym:Concept:fcl-${index + 1}` })), ...Array.from({ length: 8 }, (_, index) => ({ id: `CR-${index}`, source_path: "cr.json", source_pointer: `/${index}` }))]

describe("knowledge catalog pure domains", () => {
  it("rejects a claimed live unique identity with a different UID", () => {
    const result = compileKnowledgeMap({ topics: { authority: "SECONDARY_AI" }, coverage: { authority: "SECONDARY_AI", obligations }, live: { records: [{ uid: "sym:Concept:a", resolution: "RESOLVED_UNIQUE", matches: [{ uid: "sym:Concept:b" }] }] }, sources: [] })
    expect(Either.isLeft(result)).toBe(true)
  })
  it("rejects an assessment that promotes an unexecuted draft", () => {
    const candidate = { id: "candidate", name: "Candidate", source_ids: ["source"] }
    const result = compileResearchTooling({ inventory: { existing_capabilities: [], requirements: [] }, findings: [{ sources: [{ id: "source" }], candidates: [candidate] }], integrated: { assessments: [{ candidate_id: "candidate", decision: "ADOPTED", qualification: { status: "PROPOSED_NOT_EXECUTED" } }] } })
    expect(Either.isLeft(result)).toBe(true)
  })
  it("builds a deterministic source-bound map when all pointers resolve", () => {
    const result = compileKnowledgeMap({ topics: { authority: "SECONDARY_AI" }, coverage: { authority: "SECONDARY_AI", obligations }, live: { records: [] }, sources: [{ path: "fcl.json", bytes: encoder.encode(JSON.stringify(Array.from({ length: 8 }, (_, index) => ({ uid: `sym:Concept:fcl-${index + 1}` })))) }, { path: "cr.json", bytes: encoder.encode(JSON.stringify(Array.from({ length: 8 }, (_, index) => ({ id: `CR-${index}` })))) }] })
    expect(Either.isRight(result)).toBe(true)
    if (Either.isRight(result)) expect(result.right.bundle["expected_counts"]).toMatchObject({ anchors: 0 })
  })
  it("declares the exact fixed-cut source path set of the published catalog fixture", () => {
    const root = new URL("../../../../", import.meta.url)
    const read = (path: string) => JSON.parse(readFileSync(new URL(path, root), "utf8"))
    const catalog = read("docs/operations/artifacts/hswm_knowledge_map_2026-09-13/source-catalog.json") as { source_commit: string; sources: Array<{ path: string; sha256: string }>; curation_inputs: Array<{ path: string; sha256: string }> }
    const tree = catalog.sources.map((row: { path: string }) => row.path)
    const paths = declareKnowledgeMapCatalogPaths(read("ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json"), read("ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_COVERAGE_2026-09-13.v1.json"), tree)
    expect(Either.isRight(paths)).toBe(true)
    if (Either.isRight(paths)) {
      expect(new Set(paths.right)).toEqual(new Set(tree))
      for (const row of catalog.sources as Array<{ path: string; sha256: string }>) {
        const bytes = execFileSync("git", ["-C", new URL("../../../../", import.meta.url).pathname, "show", `${catalog.source_commit}:${row.path}`])
        expect(createHash("sha256").update(bytes).digest("hex")).toBe(row.sha256)
      }
    }
  })
  it("reconstructs every published knowledge-map node UID, anchor UID, and relation triple", () => {
    const root = new URL("../../../../", import.meta.url)
    const read = (path: string) => JSON.parse(readFileSync(new URL(path, root), "utf8"))
    const catalog = read("docs/operations/artifacts/hswm_knowledge_map_2026-09-13/source-catalog.json") as { source_commit: string; sources: Array<{ path: string; sha256: string }>; curation_inputs: Array<{ path: string; sha256: string }> }
    const sources = (catalog.sources as Array<{ path: string }>).map((row) => ({ path: row.path, bytes: new Uint8Array(execFileSync("git", ["-C", root.pathname, "show", `${catalog.source_commit}:${row.path}`])) }))
    const curationInputs = catalog.curation_inputs
    const curationPrefix = new Set(["ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json", "ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_COVERAGE_2026-09-13.v1.json", "docs/operations/artifacts/hswm_knowledge_map_2026-09-13/live-resolution.json"])
    const curatorCommit = "974c64418c9f29248eb538ffa78912bfa12eb0ea"
    const pinned = (pin: { path: string; sha256: string }) => {
      const bytes = new Uint8Array(execFileSync("git", ["-C", root.pathname, "show", `${curatorCommit}:${pin.path}`]))
      expect(createHash("sha256").update(bytes).digest("hex")).toBe(pin.sha256)
      return { path: pin.path, bytes }
    }
    const rawCurationFiles = curationInputs.filter((pin) => curationPrefix.has(pin.path)).map(pinned)
    const compilerAndQueryPins = curationInputs.filter((pin) => !curationPrefix.has(pin.path)).map(pinned)
    const curation = new Map(rawCurationFiles.map((source) => [source.path, JSON.parse(new TextDecoder().decode(source.bytes))] as const))
    const compiled = compileKnowledgeMap({ topics: curation.get("ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json"), coverage: curation.get("ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_COVERAGE_2026-09-13.v1.json"), live: curation.get("docs/operations/artifacts/hswm_knowledge_map_2026-09-13/live-resolution.json"), sources, rawCurationFiles, compilerAndQueryPins })
    expect(Either.isRight(compiled)).toBe(true)
    if (Either.isRight(compiled)) {
      const golden = read("ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_2026-09-13.v1.json")
      const bundle = compiled.right.bundle as unknown as { nodes: Array<{ uid: string }>; anchors: Array<{ uid: string }>; relations: Array<{ from_uid: string; type: string; to_uid: string }> }
      const triple = (row: { from_uid: string; type: string; to_uid: string }) => `${row.from_uid}:${row.type}:${row.to_uid}`
      expect(new Set(bundle.nodes.map((row) => row.uid))).toEqual(new Set(golden.nodes.map((row: { uid: string }) => row.uid)))
      expect(new Set(bundle.anchors.map((row) => row.uid))).toEqual(new Set(golden.anchors.map((row: { uid: string }) => row.uid)))
      expect(new Set(bundle.relations.map(triple))).toEqual(new Set(golden.relations.map(triple)))
      const properties = new Map(bundle.nodes.map((row) => [row.uid, (row as unknown as { properties: unknown }).properties]))
      for (const row of golden.nodes as Array<{ uid: string; properties: unknown }>) expect(properties.get(row.uid)).toEqual(row.properties)
      expect(compiled.right.bundle).toEqual(golden)
      expect(compiled.right.catalog).toEqual(catalog)
      const index = knowledgeMapSourceIndex(compiled.right.catalog)
      expect(Either.isRight(index)).toBe(true)
      if (Either.isRight(index)) expect(new TextDecoder().decode(index.right)).toBe(readFileSync(new URL("docs/operations/artifacts/hswm_knowledge_map_2026-09-13/source-index.md", root), "utf8"))
    }
  })
})
