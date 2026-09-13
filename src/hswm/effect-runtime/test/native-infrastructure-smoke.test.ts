import { Layer, Effect, Either } from "effect"
import { readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"
import { completeResearchFabricSmoke } from "../src/native-infrastructure-smoke-domain.js"
import { ResearchFabricTemporal, ResearchFabricTrace, runResearchFabricSmoke } from "../src/native-infrastructure-smoke-runtime.js"
import { validatePhoenixViewerProbe } from "../src/native-infrastructure-smoke-phoenix.js"

const runId = "fixed-run-01"
const temporal = { workflow_id: `hswm-infra-smoke-${runId}`, result: { run_id: runId, status: "PASS" as const, claim_boundary: "infrastructure smoke only" as const } }
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/infrastructure_smoke_v1/research-fabric-fake-vendor.original.v1.json", import.meta.url), "utf8")) as { readonly phoenix_result_sha256: string }
describe("native infrastructure smoke contracts", () => {
  it("reproduces the deterministic fake-vendor seam and emits only the bounded trace result", async () => {
    const expected = completeResearchFabricSmoke(runId, temporal); expect(Either.isRight(expected)).toBe(true)
    const emitted: unknown[] = []
    const output = await Effect.runPromise(runResearchFabricSmoke(runId).pipe(Effect.provide(Layer.merge(Layer.succeed(ResearchFabricTemporal, { execute: () => Effect.succeed(temporal) }), Layer.succeed(ResearchFabricTrace, { emit: value => Effect.sync(() => { emitted.push(value) }) })))))
    expect(output).toEqual(Either.getOrThrow(expected)); expect(output.phoenix_result_sha256).toBe(fixture.phoenix_result_sha256); expect(emitted).toEqual([output])
  })
  it("refuses mismatched Temporal identity before trace emission", () => expect(Either.isLeft(completeResearchFabricSmoke(runId, { ...temporal, workflow_id: "other" }))).toBe(true))
  it("requires the exact read-only Phoenix MCP allowlist and unsafe SQL refusal", () => {
    expect(Either.isRight(validatePhoenixViewerProbe({ tools: [{ name: "executeSql", readOnlyHint: true }, { name: "getProjects", readOnlyHint: true }, { name: "getProject", readOnlyHint: true }, { name: "describeSqlSchema", readOnlyHint: true }], readRows: [[1]], readIsError: false, unsafeError: "not_read_only", unsafeIsError: false }))).toBe(true)
    expect(Either.isLeft(validatePhoenixViewerProbe({ tools: [], readRows: [[1]], readIsError: false, unsafeError: "not_read_only", unsafeIsError: false }))).toBe(true)
  })
})
