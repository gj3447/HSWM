import { Either } from "effect"
import { expect, it } from "vitest"

import {
  enumerateCandidates,
  evaluateProgram,
  fitProgram,
  type HopPrimitive,
  type RelationGraph
} from "../../src/hswm/effect-runtime/src/relation-program-research.js"

const graph: RelationGraph = {
  relations: [
    { uid: "r:produce", meaning: "PRODUCES", participants: [{ role: "producer", uid: "cell:a" }, { role: "artifact", uid: "artifact:x" }] },
    { uid: "r:require-x", meaning: "REQUIRES", participants: [{ role: "artifact", uid: "artifact:x" }, { role: "requirement", uid: "requirement:lint" }] },
    { uid: "r:require-y", meaning: "REQUIRES", participants: [{ role: "artifact", uid: "artifact:y" }, { role: "requirement", uid: "requirement:test" }] },
    { uid: "r:invalidate", meaning: "INVALIDATES", participants: [{ role: "change", uid: "change:c" }, { role: "artifact", uid: "artifact:x" }] }
  ]
}

const hops: ReadonlyArray<HopPrimitive> = Object.freeze([
  { meaning: "PRODUCES", fromRole: "producer", toRole: "artifact" },
  { meaning: "REQUIRES", fromRole: "artifact", toRole: "requirement" },
  { meaning: "INVALIDATES", fromRole: "change", toRole: "artifact" }
])

it("executes exact-role relational ASTs over native IDs without mutating the graph", () => {
  const ast = {
    tag: "Traverse" as const,
    input: { tag: "Traverse" as const, input: { tag: "Here" as const }, ...hops[0]! },
    ...hops[1]!
  }
  const before = JSON.stringify(graph)
  const result = evaluateProgram(graph, "cell:a", ast)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right.uids).toEqual(["requirement:lint"])
    expect(result.right.counters.programExecutions).toBe(1)
    expect(result.right.counters.nodeSteps).toBeGreaterThan(0)
  }
  expect(JSON.stringify(graph)).toBe(before)
})

it("enumerates a declared bounded subset, preserves stable order, and reports an explicit cap", () => {
  const first = enumerateCandidates(hops, { maxDepth: 2, maxNodes: 5, maxCandidates: 2048 })
  const second = enumerateCandidates([...hops].reverse(), { maxDepth: 2, maxNodes: 5, maxCandidates: 2048 })
  expect(Either.isRight(first) && Either.isRight(second)).toBe(true)
  if (Either.isRight(first) && Either.isRight(second)) {
    expect(first.right.status).toBe("DECLARED_BOUNDED_SUBSET")
    expect(JSON.stringify(first.right.candidates)).toBe(JSON.stringify(second.right.candidates))
    expect(first.right.candidates.some((candidate) => candidate.tag === "Difference")).toBe(true)
  }
  expect(Either.isLeft(enumerateCandidates(hops, { maxCandidates: 1 }))).toBe(true)
})

it("rejects invalid AST roles and finite execution-budget exhaustion", () => {
  const invalid = { tag: "Traverse", input: { tag: "Here" }, meaning: "PRODUCES", fromRole: "", toRole: "artifact" }
  expect(Either.isLeft(evaluateProgram(graph, "cell:a", invalid as never))).toBe(true)
  const valid = { tag: "Traverse" as const, input: { tag: "Here" as const }, ...hops[0]! }
  expect(Either.isLeft(evaluateProgram(graph, "cell:a", valid, 1))).toBe(true)
})

it("rejects cyclic or deeply malformed ASTs and malformed graph rows as typed failures", () => {
  const cyclic: { tag: "Traverse"; input?: unknown; meaning: string; fromRole: string; toRole: string } = {
    tag: "Traverse", meaning: "PRODUCES", fromRole: "producer", toRole: "artifact"
  }
  cyclic.input = cyclic
  expect(Either.isLeft(evaluateProgram(graph, "cell:a", cyclic as never))).toBe(true)

  let deep: unknown = { tag: "Here" }
  for (let index = 0; index < 100; index += 1) {
    deep = { tag: "Traverse", input: deep, meaning: "PRODUCES", fromRole: "producer", toRole: "artifact" }
  }
  expect(Either.isLeft(evaluateProgram(graph, "cell:a", deep as never))).toBe(true)

  const here = { tag: "Here" as const }
  expect(Either.isLeft(evaluateProgram({ relations: [null] } as never, "cell:a", here))).toBe(true)
  expect(Either.isLeft(evaluateProgram({ relations: [
    { uid: "r", meaning: "M", participants: [{ role: "x", uid: "a" }] },
    { uid: "r", meaning: "N", participants: [{ role: "y", uid: "b" }] }
  ] } as never, "cell:a", here))).toBe(true)
  expect(Either.isLeft(evaluateProgram({ relations: [
    { uid: "r", meaning: "M", participants: [{ role: "x", uid: "a" }, { role: "x", uid: "b" }] }
  ] } as never, "cell:a", here))).toBe(true)
})

it("fits only supplied external labels and retains equally minimal competing programs", () => {
  const here = { tag: "Here" as const }
  const equivalent = { tag: "Union" as const, left: here, right: here }
  const fit = fitProgram([here, equivalent], [{ graph, focus: "cell:a", expected: ["cell:a"] }])
  expect(Either.isRight(fit)).toBe(true)
  if (Either.isRight(fit)) {
    expect(fit.right.status).toBe("UNIQUE_BEST")
    expect(fit.right.claim).toBe("INSTRUMENT_QUALIFICATION_ONLY")
    expect(fit.right.counters.programExecutions).toBe(2)
  }
  const ambiguous = fitProgram([
    { tag: "Traverse" as const, input: here, ...hops[1]! },
    { tag: "Traverse" as const, input: here, ...hops[2]! }
  ], [{ graph, focus: "cell:a", expected: [] }])
  expect(Either.isRight(ambiguous) && ambiguous.right.status).toBe("AMBIGUOUS_BEST")
})

it("selects a compositional relation program from supplied training labels", () => {
  const here = { tag: "Here" as const }
  const produced = { tag: "Traverse" as const, input: here, ...hops[0]! }
  const required = { tag: "Traverse" as const, input: produced, ...hops[1]! }
  const fit = fitProgram([here, produced, required], [
    { graph, focus: "cell:a", expected: ["requirement:lint"] }
  ])
  expect(Either.isRight(fit)).toBe(true)
  if (Either.isRight(fit)) {
    expect(fit.right.status).toBe("UNIQUE_BEST")
    expect(fit.right.best).toEqual([required])
    expect(fit.right.minimumErrors).toBe(0)
    expect(fit.right.complexity).toBe(3)
  }
})
