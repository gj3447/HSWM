import { Effect, Either, Exit } from "effect"
import { Parser } from "n3"
import { expect, it } from "vitest"

import { parseResearchGraph } from "../../src/hswm/effect-runtime/src/research-graph-domain.js"
import { makeResearchGraphProjection, researchGraphPropertyView } from "../../src/hswm/effect-runtime/src/research-graph-projection.js"

const graphInput = Object.freeze({
  manifest: {
    schema: "hswm-research-graph/v1", id: "projection-test", goal: "Bounded local coordination", targetRef: "docs/canon/example.md", maxParallelism: 2,
    sources: [{ id: "source-a", title: "A", locator: "docs/a.md", sha256: "a".repeat(64), authority: "USER_PRIMARY" }],
    hypotheses: [{ id: "candidate", claim: "A candidate claim", scope: "Declared local scope", falsifier: "A refuting observation", sourceIds: ["source-a"], predecessorIds: [] }],
    tasks: [{ id: "explore", hypothesisId: "candidate", role: "EXPLORE", question: "Explore", acceptance: "Record limits", dependsOn: [], budgetTokens: 10 }, { id: "critic", hypothesisId: "candidate", role: "CRITIQUE", question: "Critique", acceptance: "Seek a refutation", dependsOn: ["explore"], budgetTokens: 5 }]
  },
  events: [
    { type: "START", id: "start-explore", taskId: "explore", actor: "agent-a", model: "local", at: "2026-09-09T00:00:00.000Z" },
    { type: "FINISH", id: "finish-explore", taskId: "explore", actor: "agent-a", at: "2026-09-09T00:01:00.000Z", disposition: "REFUTED_IN_SCOPE", summary: "Candidate did not survive the declared control.", sourceIds: ["source-a"], usedTokens: 11 }
  ]
})

const parsed = () => {
  const value = parseResearchGraph(graphInput)
  if (Either.isLeft(value)) throw value.left
  return value.right
}

it("emits deterministic blank-node-free JSON-LD 1.1 RDF and preserves the failed candidate boundary", async () => {
  const left = await Effect.runPromise(makeResearchGraphProjection(parsed()))
  const right = await Effect.runPromise(makeResearchGraphProjection(parsed()))
  expect(left.nquads).toBe(right.nquads)
  expect(left.nquads).not.toContain("_:")
  expect(left.manifest["canonicalGraphSha256"]).toMatch(/^[0-9a-f]{64}$/u)
  expect(left.manifest["nquadsSha256"]).toMatch(/^[0-9a-f]{64}$/u)
  expect(left.manifest["writeBack"]).toBe("FORBIDDEN")
  expect(left.nquads).toContain("REFUTED_IN_SCOPE")
  expect(left.nquads).toContain("refutes")
  expect(left.nquads).not.toContain('> "PROVEN"')
  const quads = new Parser({ format: "N-Quads" }).parse(left.nquads)
  expect(quads.length).toBeGreaterThan(12)
})

it("keeps declared plans distinct from actual activities and preserves endpoint-directed dependencies", async () => {
  const projection = await Effect.runPromise(makeResearchGraphProjection(parsed()))
  expect(projection.nquads).toContain("TaskPlan")
  expect(projection.nquads).toContain("prov#Plan")
  expect(projection.nquads).toContain("prov#Activity")
  const view = researchGraphPropertyView(parsed())
  const sources = view["nodes"] as readonly { readonly uid: string; readonly properties: Record<string, unknown> }[]
  expect(sources.find((source) => source.uid === "source:source-a")?.properties["declaredLocator"]).toBe("docs/a.md")
  expect(sources.every((source) => !Object.hasOwn(source.properties, "locator"))).toBe(true)
  const relationships = view["relations"] as readonly { readonly from_uid: string; readonly to_uid: string; readonly type: string }[]
  expect(relationships).toContainEqual(expect.objectContaining({ from_uid: "task:critic", to_uid: "task:explore", type: "DEPENDS_ON" }))
})

it("scopes resource identifiers by the canonical source graph and rejects a malformed root", async () => {
  const original = await Effect.runPromise(makeResearchGraphProjection(parsed()))
  const changedInput = structuredClone(graphInput)
  changedInput.manifest.goal = "A distinct snapshot"
  const changed = parseResearchGraph(changedInput)
  if (Either.isLeft(changed)) throw changed.left
  const successor = await Effect.runPromise(makeResearchGraphProjection(changed.right))
  expect(original.manifest["canonicalGraphSha256"]).not.toBe(successor.manifest["canonicalGraphSha256"])
  expect(original.nquads).not.toBe(successor.nquads)
  const malformed = await Effect.runPromiseExit(makeResearchGraphProjection({ manifest: {} } as never))
  expect(Exit.isFailure(malformed)).toBe(true)
})

it("does not mistake a caller-authored literal containing blank-node syntax for an RDF blank node", async () => {
  const withLiteral = structuredClone(graphInput)
  withLiteral.events[1]!.summary = "The caller wrote _:marker as ordinary text."
  const checked = parseResearchGraph(withLiteral)
  if (Either.isLeft(checked)) throw checked.left
  const projection = await Effect.runPromise(makeResearchGraphProjection(checked.right))
  expect(projection.nquads).toContain("_:marker")
})

it("preserves unknown usage in the property view and omits unavailable RDF values", async () => {
  const unknownUsage = {
    ...graphInput,
    events: [graphInput.events[0], { ...graphInput.events[1], usedTokens: null }]
  }
  const checked = parseResearchGraph(unknownUsage)
  if (Either.isLeft(checked)) throw checked.left
  const projection = await Effect.runPromise(makeResearchGraphProjection(checked.right))
  expect(projection.nquads).toContain("UNKNOWN")
  expect(projection.nquads).not.toContain("usedTokens")
  expect(projection.nquads).not.toMatch(/task\/explore> <[^>]+\/overBudget>/u)
  const view = researchGraphPropertyView(checked.right)
  const nodes = view["nodes"] as readonly { readonly uid: string; readonly properties: Record<string, unknown> }[]
  expect(nodes.find((node) => node.uid === "result:finish-explore")?.properties).toMatchObject({ usageStatus: "UNKNOWN", usedTokens: null })
  expect(nodes.find((node) => node.uid === "task:explore")?.properties).toMatchObject({ usageStatus: "UNKNOWN", overBudget: null })
})
