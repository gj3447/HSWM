import { Either } from "effect"
import { expect, it } from "vitest"
import { contextHash } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { prepareFiniteExecutionGuard, checkFiniteExecution } from "../../src/hswm/effect-runtime/src/semantic-context-finite-execution-domain.js"
import type { SemanticReadFrame } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { unwrap } from "./semantic-context-fixture.js"

const key = (atomUid: string) => ({ schemaVersion: "guard-test", lineageId: "fixture", atomUid, revisionId: 0 })
const frame = (uid = "rule"): SemanticReadFrame => {
  const body = { event: "context", stateRevision: 0,
    relation: { key: key(uid), owner: "owner:test", semantic: {
      semanticText: JSON.stringify({ contract: "hswm-finite-semantic-program/v1",
        variables: [{ id: "x", roleOrdinal: 0, values: ["0", "1"] }, { id: "e", roleOrdinal: 3, values: ["0", "1"] }],
        expressions: [{ op: "is", variable: "x", value: "0" }, { op: "is", variable: "e", value: "1" }, { op: "or", left: 0, right: 1 }],
        clauses: [{ id: "zero_unless_exception", expression: 2 }] }),
      disposition: "predict", uncertainty: "fixture", exceptionRefs: ["exception"], trace: null, outcome: null
    } },
    roles: ["subject", "context", "evidence", "exception"].map(role => ({ referenceType: "hswm:semantic:role", role, key: key(role),
      owner: "owner:test", contentSha256: contextHash(role), contentUtf8: role })), priorEvidence: null }
  return { ...body, frameSha256: contextHash(body) }
}
const binding = { relationKey: key("rule"), inputs: [{ variable: "e", eventField: "invalid" }], outputVariable: "x" }
const guard = { contract: "hswm-finite-execution-guard/v1", rules: [binding] }
const payload = (invalid: unknown = 0) => ({ event: JSON.stringify({ invalid }), frames: [frame()] })
it("checks every output against the declared exception without repairing it", () => {
  for (const invalid of [0, 1]) for (const prediction of ["0", "1", "REFUSE"]) {
    const p = payload(invalid), original = JSON.stringify(p)
    const verdict = checkFiniteExecution(unwrap(prepareFiniteExecutionGuard(p, guard)), prediction)
    expect(verdict.status).toBe((prediction === "0" || invalid === 1 && prediction === "1") ? "SATISFIED" : "VIOLATED")
    expect(verdict.prediction).toBe(prediction)
    expect(verdict.checks[0]?.assignment).toEqual({ x: prediction, e: String(invalid) })
    expect(JSON.stringify(p)).toBe(original)
  }
})
it("requires exact full frame and variable coverage, source revisions and roles", () => {
  const bad = [
    { ...guard, rules: [] },
    { ...guard, rules: [binding, binding] },
    { ...guard, rules: [{ ...binding, inputs: [] }] },
    { ...guard, rules: [{ ...binding, inputs: [...binding.inputs, { variable: "x", eventField: "invalid" }] }] },
    { ...guard, rules: [{ ...binding, outputVariable: "unknown" }] },
    { ...guard, rules: [{ ...binding, relationKey: { ...binding.relationKey, revisionId: 1 } }] }
  ]
  for (const g of bad) expect(Either.isLeft(prepareFiniteExecutionGuard(payload(), g))).toBe(true)
  expect(Either.isLeft(prepareFiniteExecutionGuard({ ...payload(), frames: [frame(), frame("mandatory")] }, guard))).toBe(true)
  expect(Either.isLeft(prepareFiniteExecutionGuard({ ...payload(), frames: [{ ...frame(), roles: [] }] }, guard))).toBe(true)
})
it("refuses unknown semantics and missing, null, object or out-of-domain inputs", () => {
  for (const invalid of [null, {}, [], "outside"]) expect(Either.isLeft(prepareFiniteExecutionGuard(payload(invalid), guard))).toBe(true)
  for (const event of ["{}", "[]", "null", "not JSON", '{"invalid":0,"invalid":1}']) expect(Either.isLeft(prepareFiniteExecutionGuard({ ...payload(), event }, guard))).toBe(true)
  const f = frame()
  expect(Either.isLeft(prepareFiniteExecutionGuard({ ...payload(), frames: [{ ...f, relation: { ...f.relation, semantic: { ...f.relation.semantic, semanticText: "roughly similar" } } }] }, guard))).toBe(true)
  expect(checkFiniteExecution(unwrap(prepareFiniteExecutionGuard(payload("1"), guard)), "1").status).toBe("SATISFIED")
  expect(Either.isLeft(prepareFiniteExecutionGuard(payload(), { ...guard, rules: [{ ...binding, inputs: [{ variable: "e", eventField: "toString" }] }] }))).toBe(true)
})
it("checks input-only mandatory rules as well as output rules", () => {
  const mandatory = frame("mandatory")
  const p = { event: JSON.stringify({ invalid: 0, required: 1 }), frames: [mandatory, frame()] }
  const g = { ...guard, rules: [{ relationKey: mandatory.relation.key, outputVariable: null,
    inputs: [{ variable: "x", eventField: "required" }, { variable: "e", eventField: "invalid" }] }, binding] }
  const verdict = checkFiniteExecution(unwrap(prepareFiniteExecutionGuard(p, g)), "0")
  expect(verdict.checks.map(c => c.accepted)).toEqual([false, true])
  expect(verdict.status).toBe("VIOLATED")
})
