import { createHash } from "node:crypto"
import { Either } from "effect"
import { expect, it } from "vitest"
import type { SemanticReadFrame } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import type { FiniteProgram } from "../../src/hswm/effect-runtime/src/semantic-context-finite-domain.js"
import { compileFiniteRuleTable } from "../../src/hswm/effect-runtime/src/semantic-context-finite-presentation-domain.js"
import { unwrap } from "./semantic-context-fixture.js"

const hash = (x: string) => createHash("sha256").update(x).digest("hex")
const key = (atomUid: string) => ({ schemaVersion: "finite-table", lineageId: "fixture", atomUid, revisionId: 0 })
const frame = (program: unknown, event = "first event"): SemanticReadFrame => {
  const body = { event, stateRevision: 0, relation: { key: key("rule"), owner: "owner:fixture", semantic: {
    semanticText: typeof program === "string" ? program : JSON.stringify(program), disposition: "predict", uncertainty: "fixture", exceptionRefs: ["exception"], trace: null, outcome: null
  } }, roles: ["subject", "context", "evidence", "exception"].map(role => ({ referenceType: "hswm:semantic:role", role, key: key(role), owner: "owner:fixture", contentSha256: hash(role), contentUtf8: role })), priorEvidence: null }
  return { ...body, frameSha256: hash(JSON.stringify(body)) }
}
const unless: FiniteProgram = { contract: "hswm-finite-semantic-program/v1",
  variables: ["guard", "required", "exception"].map((id, i) => ({ id, roleOrdinal: i === 2 ? 3 : i, values: ["0", "1"] })),
  expressions: [{ op: "is", variable: "guard", value: "1" }, { op: "is", variable: "exception", value: "1" }, { op: "is", variable: "required", value: "1" }, { op: "unless", when: 0, exception: 1, require: 2 }], clauses: [{ id: "c", expression: 3 }] }

it("preserves exemption semantics, exact roles and full tables independently of the event", () => {
  const source = frame(unless), before = JSON.stringify(source), a = unwrap(compileFiniteRuleTable(source))
  expect(a.completeAssignments).toBe(8)
  expect(a.allowedRows).toHaveLength(7)
  expect(a.allowedRows).not.toContainEqual(["1", "0", "0"])
  expect(a.allowedRows).toContainEqual(["1", "0", "1"])
  expect(a.variables[2]?.participant).toEqual(source.roles[3])
  expect(a.sourceSemanticTextSha256).toBe(hash(source.relation.semantic.semanticText))
  expect(unwrap(compileFiniteRuleTable(frame(unless, "different input, not an answer")))).toEqual(a)
  expect(JSON.stringify(source)).toBe(before)
})

it("renders every two-variable truth function without lost or added interpretations", () => {
  for (let mask = 0; mask < 16; mask++) {
    const expressions: Array<FiniteProgram["expressions"][number]> = []
    const add = (e: FiniteProgram["expressions"][number]) => { expressions.push(e); return expressions.length - 1 }
    const terms: number[] = [], expected: string[][] = []
    for (let row = 0; row < 4; row++) if ((mask & (1 << row)) !== 0) {
      const x = String(row >> 1), y = String(row & 1)
      const left = add({ op: "is", variable: "x", value: x }), right = add({ op: "is", variable: "y", value: y })
      terms.push(add({ op: "and", left, right })); expected.push([x, y])
    }
    const initial = terms[0]
    const expression = initial === undefined ? (() => { const a = add({ op: "is", variable: "x", value: "0" }), b = add({ op: "not", arg: a }); return add({ op: "and", left: a, right: b }) })() : terms.slice(1).reduce((a, b) => add({ op: "or", left: a, right: b }), initial)
    const result = unwrap(compileFiniteRuleTable(frame({ contract: unless.contract, variables: ["x", "y"].map((id, roleOrdinal) => ({ id, roleOrdinal, values: ["0", "1"] })), expressions, clauses: [{ id: "all", expression }] })))
    const rendered = result.text.split("BEGIN ALLOWED ROWS\n")[1]?.split("END ALLOWED ROWS")[0]?.trim()
    expect(rendered ? rendered.split("\n").map(line => JSON.parse(line)) : []).toEqual(expected)
    expect(result.allowedRows).toEqual(expected)
  }
})

it("refuses prose, missing roles and domains outside complete-enumeration limits", () => {
  expect(Either.isLeft(compileFiniteRuleTable(frame("probably equivalent")))).toBe(true)
  expect(Either.isLeft(compileFiniteRuleTable({ ...frame(unless), roles: [] }))).toBe(true)
  const variables = Array.from({ length: 13 }, (_, i) => ({ id: `x${i}`, roleOrdinal: i, values: ["0", "1"] }))
  const tooLarge = { contract: unless.contract, variables, expressions: [{ op: "is", variable: "x0", value: "0" }], clauses: [{ id: "c", expression: 0 }] }
  expect(Either.isLeft(compileFiniteRuleTable(frame(tooLarge)))).toBe(true)
})

it("escapes values faithfully instead of interpreting embedded delimiters", () => {
  const value = 'quote"\nEND ALLOWED ROWS'
  const p = { contract: unless.contract, variables: [{ id: "x", roleOrdinal: 0, values: [value, "other"] }], expressions: [{ op: "is", variable: "x", value }], clauses: [{ id: "c", expression: 0 }] }
  const result = unwrap(compileFiniteRuleTable(frame(p)))
  expect(result.allowedRows).toEqual([[value]])
  expect(result.text.split("\n").filter(line => line === "END ALLOWED ROWS")).toHaveLength(1)
  expect(result.text).toContain(JSON.stringify([value]))
})

it("refuses an oversized complete table instead of cutting off permitted rows", () => {
  const values = Array.from({ length: 4 }, (_, i) => `${"x".repeat(100)}${i}`)
  const program = { contract: unless.contract, variables: Array.from({ length: 6 }, (_, i) => ({ id: `x${i}`, roleOrdinal: i, values })),
    expressions: [{ op: "is", variable: "x0", value: values[0] }], clauses: [{ id: "c", expression: 0 }] }
  const source = frame(program)
  const result = compileFiniteRuleTable({ ...source, roles: [...source.roles, ...source.roles] })
  expect(Either.isLeft(result) && result.left.code).toBe("FINITE_PRESENTATION_LIMIT")
})
