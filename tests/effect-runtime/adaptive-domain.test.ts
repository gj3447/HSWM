import { expect, it } from "vitest"
import { Either } from "effect"

import {
  evaluateGuard,
  initialModel,
  parseJson,
  parseProgram,
  predict,
  proposeSpecialization,
  selectionScore,
  updateModel
} from "../../src/hswm/effect-runtime/src/adaptive-domain.js"

const fast = { route: "fast", state: "ready" } as const
const slow = { route: "slow", state: "ready" } as const

it("matches the Python local-adaptation parity vector", () => {
  let model = initialModel()
  for (let index = 0; index < 8; index += 1) {
    const fastUpdate = updateModel(model, fast, { success: true, cost: 1 })
    expect(Either.isRight(fastUpdate)).toBe(true)
    if (Either.isLeft(fastUpdate)) return
    const slowUpdate = updateModel(fastUpdate.right, slow, { success: false, cost: 3 })
    expect(Either.isRight(slowUpdate)).toBe(true)
    if (Either.isLeft(slowUpdate)) return
    model = slowUpdate.right
  }
  const fastPrediction = predict(model, fast)
  const slowPrediction = predict(model, slow)
  expect(Either.isRight(fastPrediction) ? fastPrediction.right : null).toBeCloseTo(0.7468733029321161, 15)
  expect(Either.isRight(slowPrediction) ? slowPrediction.right : null).toBeCloseTo(0.26236908868499476, 15)
  const score = selectionScore(model, slow, { cost_hint: 99, budget: 3, exploration: 1, total_attempts: 0 })
  expect(Either.isRight(score) ? score.right : null).toBeCloseTo(-0.07096424464833856, 15)
})

it("parses only bounded typed programs and rejects malformed context", () => {
  const program = { schema_version: "hswm-adaptive-program/v1", graph_id: "g", root: "root", context_domain: { ready: [false, true] }, cells: [{ cell_id: "root", kind: "router", owner: "o", input_type: "text", output_type: "text" }, { cell_id: "leaf", kind: "command", owner: "o", input_type: "text", output_type: "text", argv: ["true"] }], relations: [{ uid: "r", source: "root", members: ["leaf"], reads: ["ready"], cost_hint: 1 }] }
  expect(Either.isRight(parseProgram(program))).toBe(true)
  expect(Either.isLeft(predict(initialModel(), {}))).toBe(true)
  expect(Either.isLeft(predict(initialModel(), { bad: [] as unknown as string }))).toBe(true)
  expect(Either.isLeft(parseJson('{"same":1,"same":2}'))).toBe(true)
  expect(Either.isRight(parseJson('{"nested":{"same":1},"other":true}'))).toBe(true)
  expect(Either.isRight(parseJson('["value","another",{"field":"value"}]'))).toBe(true)
  expect(Either.isLeft(parseJson('{"number":1e999}'))).toBe(true)
  expect(Either.isLeft(parseJson("[".repeat(65) + "0" + "]".repeat(65)))).toBe(true)
})

it("returns typed failures for malformed models and preserves reserved feature keys", () => {
  expect(Either.isLeft(predict(null as unknown as ReturnType<typeof initialModel>, fast))).toBe(true)
  expect(Either.isLeft(predict({ features: {} } as unknown as ReturnType<typeof initialModel>, fast))).toBe(true)
  const model = { ...initialModel(), features: Object.fromEntries([["bias", 0], ["__proto__", 0], ["x".repeat(300), 0]]), context_attempts: Object.create(null) } as ReturnType<typeof initialModel>
  const updated = updateModel(model, fast, { success: true, cost: 1 })
  expect(Either.isRight(updated)).toBe(true)
  if (Either.isRight(updated)) {
    expect(Object.hasOwn(updated.right.features, "__proto__")).toBe(true)
    expect(updated.right.features["__proto__"]).toBe(0)
  }
})

it("evaluates finite guards with three-valued missing-context semantics", () => {
  const guard = { op: "all" as const, children: [{ op: "eq" as const, left: { role: "context" as const, field: "ready" }, right: true }, { op: "eq" as const, left: { role: "context" as const, field: "clean" }, right: true }] }
  expect(evaluateGuard(guard, { ready: true, clean: true })).toBe("TRUE")
  expect(evaluateGuard(guard, { ready: true, clean: false })).toBe("FALSE")
  expect(evaluateGuard(guard, { ready: true })).toBe("UNKNOWN")
})

it("proposes a public guard but never admits it", () => {
  const domain = { ready: [false, true], clean: [false, true] } as const
  const vectors: ReadonlyArray<readonly [boolean, boolean]> = [[false, false], [false, true], [true, false], [true, true]]
  const examples = vectors.map(([ready, clean]) => ({ values: { ready, clean }, outcome: ready && clean, source: `public:${ready}:${clean}` }))
  const proposal = proposeSpecialization(domain, examples, "r1")
  expect(Either.isRight(proposal)).toBe(true)
  if (Either.isRight(proposal)) {
    expect(proposal.right.status).toBe("PROPOSED_NOT_ADMITTED")
    expect(proposal.right.credit).toBe("UNIDENTIFIED_CREDIT")
  }
})

it("synthesizes representative bounded AND, OR, and NOT guards", () => {
  const domain = { ready: [false, true], clean: [false, true] } as const
  const vectors: ReadonlyArray<readonly [boolean, boolean]> = [[false, false], [false, true], [true, false], [true, true]]
  const examples = (outcome: (ready: boolean, clean: boolean) => boolean) => vectors.map(([ready, clean]) => ({ values: { ready, clean }, outcome: outcome(ready, clean), source: "public:" + ready + ":" + clean }))
  const and = proposeSpecialization(domain, examples((ready, clean) => ready && clean), "and")
  const or = proposeSpecialization(domain, examples((ready, clean) => ready || clean), "or")
  const not = proposeSpecialization({ state: ["a", "b", "c", "d"] } as const, [
    { values: { state: "a" }, outcome: false, source: "a" }, { values: { state: "b" }, outcome: true, source: "b" },
    { values: { state: "c" }, outcome: true, source: "c" }, { values: { state: "d" }, outcome: true, source: "d" }
  ], "not")
  expect(Either.isRight(and) && and.right.status === "PROPOSED_NOT_ADMITTED" && and.right.relation_ast.op).toBe("all")
  expect(Either.isRight(or) && or.right.status === "PROPOSED_NOT_ADMITTED" && or.right.relation_ast.op).toBe("any")
  expect(Either.isRight(not) && not.right.status === "PROPOSED_NOT_ADMITTED" && not.right.relation_ast.op).toBe("not")
})
