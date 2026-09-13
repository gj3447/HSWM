import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { Either } from "effect"
import { describe, expect, it } from "vitest"
import { compileResearchTooling, researchToolingSourceIndex } from "../src/research-tooling-domain.js"

const root = new URL("../../../../", import.meta.url)
const read = (path: string): unknown => JSON.parse(readFileSync(new URL(path, root), "utf8")) as unknown
describe("research tooling fixed-source projection", () => {
  it("matches the published descriptor, capability, evidence, and requirement records", () => {
    const inventory = read("_research/graph_standards/research_tooling_2026-09-13/repository-gap-inventory.json")
    const findings = [read("_research/graph_standards/research_tooling_2026-09-13/reproducibility-findings.json"), read("_research/graph_standards/research_tooling_2026-09-13/evaluation-formal-findings.json"), read("_research/graph_standards/research_tooling_2026-09-13/graph-standards-findings.json")]
    const integrated = read("_research/graph_standards/research_tooling_2026-09-13/integrated-assessment.json")
    const golden = read("ontology/research_tooling/HSWM_SCIENTIFIC_RESEARCH_TOOLING_2026-09-13.v1.json") as { nodes: Array<{ uid: string; properties: { standard_graph_role: string } }>; relations: unknown[] }
    const catalog = read("docs/research/artifacts/hswm_research_tooling_2026-09-13/source-catalog.json") as { source_commit: string; inputs: Array<{ path: string; sha256: string }>; fixed_git_source_descriptors: Array<{ source_path: string }> }
    const fixedGitSources = catalog.fixed_git_source_descriptors.map(({ source_path }) => ({ path: source_path, bytes: new Uint8Array(execFileSync("git", ["-C", root.pathname, "show", catalog.source_commit + ":" + source_path])) }))
    const curationPrefix = "_research/graph_standards/research_tooling_2026-09-13/"
    const pinnedCuratorBytes = (pin: {path: string; sha256: string}) => {
      const bytes = new Uint8Array(execFileSync("git", ["-C", root.pathname, "show", "974c64418c9f29248eb538ffa78912bfa12eb0ea:" + pin.path]));
      expect(createHash("sha256").update(bytes).digest("hex"), pin.path).toBe(pin.sha256);
      return {path: pin.path, bytes};
    };
    const rawCurationFiles = catalog.inputs.filter(pin => pin.path.startsWith(curationPrefix)).map(pinnedCuratorBytes);
    const compilerAndQueryPins = catalog.inputs.filter(pin => !pin.path.startsWith(curationPrefix)).map(pinnedCuratorBytes);
    const result = compileResearchTooling({ inventory, findings, integrated, fixedGitSources, rawCurationFiles, compilerAndQueryPins })
    expect(Either.isRight(result)).toBe(true)
    if (Either.isRight(result)) {
      expect(result.right.bundle).toEqual(golden);
      expect(result.right.bundle["nodes"]).toEqual(golden.nodes)
      expect(result.right.bundle["anchors"]).toEqual((golden as unknown as { anchors: unknown }).anchors)
      expect(result.right.bundle["relations"]).toEqual(golden.relations)
      expect(result.right.bundle["expected_counts"]).toEqual((golden as unknown as { expected_counts: unknown }).expected_counts)
      expect(result.right.bundle["artifact_bindings"]).toEqual((golden as unknown as { artifact_bindings: unknown }).artifact_bindings)
      expect(result.right.catalog).toEqual(catalog)
      const index = researchToolingSourceIndex(result.right.catalog)
      expect(Either.isRight(index)).toBe(true)
      if (Either.isRight(index)) expect(new TextDecoder().decode(index.right)).toBe(readFileSync(new URL("docs/research/artifacts/hswm_research_tooling_2026-09-13/source-index.md", root), "utf8"))
    }
  })
})
