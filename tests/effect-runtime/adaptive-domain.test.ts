import { expect, it } from "vitest"
import { Either } from "effect"

import {
  evaluateGuard,
  initialModel,
  parseJson,
  parseProgram,
  plan,
  predict,
  proposeSpecialization,
  selectionScore,
  specializeGuard,
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

it("specialization preserves mandatory parent guards while leaving the selector proposal compatible", () => {
  const parent = { op: "eq" as const, left: { role: "context" as const, field: "mode" }, right: "investigate" }
  const selector = { op: "eq" as const, left: { role: "context" as const, field: "domain" }, right: "declared" }
  const effective = specializeGuard(parent, selector)
  expect(evaluateGuard(effective, { mode: "compute", domain: "declared" })).toBe("FALSE")
  expect(evaluateGuard(effective, { mode: "investigate", domain: "declared" })).toBe("TRUE")
  expect(evaluateGuard(effective, { mode: "investigate" })).toBe("UNKNOWN")
  expect(parent).toEqual({ op: "eq", left: { role: "context", field: "mode" }, right: "investigate" })
  expect(specializeGuard(undefined, selector)).toBe(selector)
})

it("records stable eligibility diagnostics and forced-route tie behavior without changing scores", () => {
  const program = {
    schema_version: "hswm-adaptive-program/v1",
    graph_id: "plan-diagnostics",
    root: "root",
    context_domain: { ready: [false, true], mode: ["investigate", "compute"] },
    cells: [
      { cell_id: "root", kind: "router", owner: "o", input_type: "text", output_type: "text" },
      { cell_id: "other", kind: "router", owner: "o", input_type: "text", output_type: "text" },
      { cell_id: "allowed", kind: "command", owner: "o", input_type: "text", output_type: "text", argv: ["true"] },
      { cell_id: "blocked", kind: "command", owner: "o", input_type: "text", output_type: "text", argv: ["true"] }
    ],
    relations: [
      { uid: "a", source: "root", members: ["allowed"], reads: ["ready"], cost_hint: 1 },
      { uid: "b", source: "root", members: ["allowed"], reads: ["ready"], cost_hint: 1 },
      { uid: "inactive", source: "root", members: ["allowed"], reads: ["ready"], cost_hint: 1 },
      { uid: "budget", source: "root", members: ["allowed"], reads: ["ready"], cost_hint: 9 },
      { uid: "permission", source: "root", members: ["blocked"], reads: ["ready"], cost_hint: 1 },
      { uid: "wrong-source", source: "other", members: ["allowed"], reads: ["ready"], cost_hint: 1 },
      { uid: "guard", source: "root", members: ["allowed"], reads: ["ready", "mode"], cost_hint: 1, guard: { op: "eq", left: { role: "context", field: "mode" }, right: "investigate" } }
    ]
  } as const
  const routes = program.relations.map((route) => ({ route, model: initialModel(), active: route.uid !== "inactive" }))
  const normal = plan(program, routes, { ready: true, mode: "compute" }, { budget: 1, allowed: new Set(["root", "other", "allowed"]) })
  expect(Either.isRight(normal)).toBe(true)
  if (Either.isLeft(normal)) return
  expect(normal.right.selected?.uid).toBe("a")
  expect(normal.right.choices.map((choice) => choice.uid)).toEqual(["a", "b"])
  expect(normal.right.choices[0]?.members).toEqual(["allowed"])
  expect(normal.right.choices[0]?.reads).toEqual(["ready"])
  expect(normal.right.selection).toEqual({ rule: "SCORE_DESC_THEN_UID_ASC", tie_uids: ["a", "b"], highest_score_tie_uids: ["a", "b"] })
  expect(normal.right.rejected).toEqual([
    { uid: "budget", reason: "BUDGET" },
    { uid: "guard", reason: "GUARD_FALSE" },
    { uid: "inactive", reason: "INACTIVE" },
    { uid: "permission", reason: "PERMISSION" },
    { uid: "wrong-source", reason: "SOURCE" }
  ])
  const forced = plan(program, routes, { ready: true, mode: "compute" }, { budget: 1, allowed: new Set(["root", "other", "allowed"]), force_route: "b" })
  expect(Either.isRight(forced)).toBe(true)
  if (Either.isLeft(forced)) return
  expect(forced.right.selected?.uid).toBe("b")
  expect(forced.right.selection).toEqual({ rule: "FORCE_ELIGIBLE_ROUTE", tie_uids: ["a", "b"], highest_score_tie_uids: ["a", "b"] })
  const unknown = plan(program, routes, { ready: true }, { budget: 1, allowed: new Set(["root", "other", "allowed"]) })
  expect(Either.isRight(unknown)).toBe(true)
  if (Either.isRight(unknown))
    expect(unknown.right.rejected).toContainEqual({ uid: "guard", reason: "GUARD_UNKNOWN" })
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

it("keeps bounded long context-attempt indexes reusable without loosening identifiers", () => {
  const context = Object.fromEntries(Array.from({ length: 6 }, (_, index) => [`field_${index}`, `value_${index}`]))
  let model = initialModel()
  const first = updateModel(model, context, { success: true, cost: 1 })
  expect(Either.isRight(first)).toBe(true)
  if (Either.isLeft(first)) return
  const attemptKey = Object.keys(first.right.context_attempts)[0] as string
  expect(attemptKey.length).toBeGreaterThan(256)
  expect(Either.isRight(predict(first.right, context))).toBe(true)
  model = first.right
  for (let index = 0; index < 3; index += 1) {
    const updated = updateModel(model, context, { success: index % 2 === 0, cost: index + 1 })
    expect(Either.isRight(updated)).toBe(true)
    if (Either.isLeft(updated)) return
    model = updated.right
    expect(Either.isRight(predict(model, context))).toBe(true)
  }
  const eightFields = Object.fromEntries(Array.from({ length: 8 }, (_, index) => [`eight_${index}`, index]))
  for (let index = 0; index < 2; index += 1) {
    const eightUpdate = updateModel(model, eightFields, { success: true, cost: 1 })
    expect(Either.isRight(eightUpdate)).toBe(true)
    if (Either.isLeft(eightUpdate)) return
    model = eightUpdate.right
    expect(Either.isRight(predict(model, eightFields))).toBe(true)
  }

  const oversized = {
    ...initialModel(),
    context_attempts: { ["x".repeat("context:".length + 63 * (2048 + "|".length) + 1)]: 0 }
  }
  expect(Either.isLeft(predict(oversized, fast))).toBe(true)
})
