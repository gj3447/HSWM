import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { describe, expect, it } from "vitest"
import { Effect } from "effect"
import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import { runKnowledgeCatalogCli } from "../src/knowledge-catalog-cli.js"

const checkout = new URL("../../../../", import.meta.url).pathname
const run = <A>(effect: Effect.Effect<A, unknown, never>) => Effect.runPromise(effect)

describe("native knowledge catalog reproduction", () => {
  it("reproduces both published catalogs from their fixed Git cuts and writes only new output directories", async () => {
    const output = await mkdtemp(join(tmpdir(), "hswm-knowledge-catalog-"))
    try {
      const map = await run(runKnowledgeCatalogCli(["knowledge-map", "--checkout", checkout, "--output-dir", join(output, "map")]).pipe(Effect.provide(NodePosixServicesLive)))
      const research = await run(runKnowledgeCatalogCli(["research-tooling", "--checkout", checkout, "--output-dir", join(output, "research")]).pipe(Effect.provide(NodePosixServicesLive)))
      expect(map.exitCode).toBe(0)
      expect(research.exitCode).toBe(0)
      const root = new URL("../../../../", import.meta.url)
      await expect(readFile(join(output, "map", "source-catalog.json"), "utf8")).resolves.toBe(await readFile(new URL("docs/operations/artifacts/hswm_knowledge_map_2026-09-13/source-catalog.json", root), "utf8"))
      await expect(readFile(join(output, "map", "bundle.json"), "utf8")).resolves.toBe(await readFile(new URL("ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_2026-09-13.v1.json", root), "utf8"))
      await expect(readFile(join(output, "map", "source-index.md"), "utf8")).resolves.toBe(await readFile(new URL("docs/operations/artifacts/hswm_knowledge_map_2026-09-13/source-index.md", root), "utf8"))
      await expect(readFile(join(output, "research", "source-catalog.json"), "utf8")).resolves.toBe(await readFile(new URL("docs/research/artifacts/hswm_research_tooling_2026-09-13/source-catalog.json", root), "utf8"))
      await expect(readFile(join(output, "research", "bundle.json"), "utf8")).resolves.toBe(await readFile(new URL("ontology/research_tooling/HSWM_SCIENTIFIC_RESEARCH_TOOLING_2026-09-13.v1.json", root), "utf8"))
      await expect(readFile(join(output, "research", "source-index.md"), "utf8")).resolves.toBe(await readFile(new URL("docs/research/artifacts/hswm_research_tooling_2026-09-13/source-index.md", root), "utf8"))
      await expect(run(runKnowledgeCatalogCli(["knowledge-map", "--checkout", checkout, "--output-dir", join(output, "map")]).pipe(Effect.provide(NodePosixServicesLive)))).rejects.toThrow()
    } finally { await rm(output, { recursive: true, force: true }) }
  }, 120_000)
})
