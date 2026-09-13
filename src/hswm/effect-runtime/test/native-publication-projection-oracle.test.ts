import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import { runKnowledgeCatalogCli } from "../src/knowledge-catalog-cli.js"
import { compileKnowledgeMap } from "../src/knowledge-map-domain.js"
import { compileResearchTooling } from "../src/research-tooling-domain.js"

interface Pin { readonly path: string; readonly sha256: string }
interface Oracle { readonly source_pins: ReadonlyArray<Pin>; readonly positive: Record<string, { readonly command: string; readonly result: Readonly<Record<string, unknown>> }>; readonly negative: Record<string, string> }
const root = new URL("../../../../", import.meta.url)
const oracle = JSON.parse(readFileSync(new URL("tests/fixtures/native_migration/publication_compilers_v1/original-python-oracle.v1.json", root), "utf8")) as Oracle
const runNative = (command: "knowledge-map" | "research-tooling") => Effect.runPromise(runKnowledgeCatalogCli([command, "--checkout", root.pathname]).pipe(Effect.provide(NodePosixServicesLive)))

describe("native publication projection original-Python oracle", () => {
  it("pins the original compiler bytes and matches its frozen positive results through the native CLI", async () => {
    for (const pin of oracle.source_pins) expect(createHash("sha256").update(readFileSync(new URL(pin.path, root))).digest("hex")).toBe(pin.sha256)
    const research = JSON.parse((await runNative("research-tooling")).stdout) as { readonly catalog: { readonly source_commit: unknown }; readonly bundle: { readonly expected_counts: unknown } }
    const map = JSON.parse((await runNative("knowledge-map")).stdout) as { readonly catalog: { readonly source_commit: unknown }; readonly bundle: { readonly expected_counts: unknown } }
    expect(research.bundle.expected_counts).toEqual(oracle.positive["research_tooling"]!.result["counts"])
    expect(research.catalog.source_commit).toBe(oracle.positive["research_tooling"]!.result["source_commit"])
    expect(map.bundle.expected_counts).toEqual(oracle.positive["knowledge_map"]!.result["counts"])
    expect(map.catalog.source_commit).toBe(oracle.positive["knowledge_map"]!.result["source_commit"])
  }, 30_000)

  it("rejects malformed source-bound inputs in the native compilers", () => {
    const map = compileKnowledgeMap({ topics: { authority: "SECONDARY_AI" }, coverage: { authority: "SECONDARY_AI", obligations: [] }, live: { records: [] }, sources: [] })
    const research = compileResearchTooling({ inventory: { existing_capabilities: [], requirements: [] }, findings: [], integrated: { assessments: [{ candidate_id: "missing", decision: "ADOPTED", qualification: { status: "PROPOSED_NOT_EXECUTED" } }] } })
    expect(Either.isLeft(map) && map.left.code).toBe("COVERAGE_INVALID")
    expect(Either.isLeft(research) && research.left.code).toBe("ASSESSMENT_INVALID")
    expect(Object.keys(oracle.negative)).toHaveLength(4)
  })
})
