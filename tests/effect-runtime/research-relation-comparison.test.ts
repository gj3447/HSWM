import { Either } from "effect"
import { expect, it } from "vitest"

import {
  CALIBRATION_PUBLIC_PRIMITIVES,
  buildExecutableProgramConsolidationPrompt,
  buildOpenBookPrompt,
  buildProgramInferencePrompt,
  buildTextLessonInferencePrompt,
  evaluateIndependentProgram,
  parseInferenceResponse,
  parseLessonResponse,
  parseProgramResponse,
  parseUidInferenceResponse,
  serializeCalibrationGraph,
  type CalibrationProgram,
  type CalibrationTarget,
  type CalibrationTrainingExample
} from "../../src/hswm/effect-runtime/src/research-relation-comparison.js"
import { evaluateProgram } from "../../src/hswm/effect-runtime/src/relation-program-research.js"
import { catalogTask } from "../../_research/causal_composition/relation_synthesis_usl_v1/fixtures.mjs"

const graph = {
  relations: [
    { uid: "r:invalidates", meaning: "Declared KG relation: INVALIDATES", participants: [{ role: "change", uid: "change:a" }, { role: "artifact", uid: "artifact:x" }, { role: "context", uid: "scope:a" }] },
    { uid: "r:requires", meaning: "Declared KG relation: REQUIRES", participants: [{ role: "artifact", uid: "artifact:x" }, { role: "requirement", uid: "requirement:x" }, { role: "context", uid: "scope:a" }] },
    { uid: "r:checks", meaning: "Declared KG relation: CHECKS", participants: [{ role: "check", uid: "check:x" }, { role: "requirement", uid: "requirement:x" }, { role: "context", uid: "scope:a" }] },
    { uid: "r:distractor", meaning: "Declared KG relation: CHECKS", participants: [{ role: "check", uid: "check:wrong" }, { role: "requirement", uid: "requirement:other" }, { role: "context", uid: "scope:a" }] }
  ]
} as const

const target: CalibrationTarget = { id: "calibration-401", focus: "change:a", graph }
const training: ReadonlyArray<CalibrationTrainingExample> = [{ id: "catalog-11", focus: "change:a", graph, expectedUids: ["check:x"] }]

const program: CalibrationProgram = {
  tag: "Traverse", meaning: "Declared KG relation: CHECKS", fromRole: "requirement", toRole: "check",
  input: {
    tag: "Traverse", meaning: "Declared KG relation: REQUIRES", fromRole: "artifact", toRole: "requirement",
    input: { tag: "Traverse", meaning: "Declared KG relation: INVALIDATES", fromRole: "change", toRole: "artifact", input: { tag: "Here" } }
  }
}

it("serializes named relation UIDs and ordered participant roles without loss", () => {
  const rendered = serializeCalibrationGraph(graph)
  expect(Either.isRight(rendered)).toBe(true)
  if (Either.isRight(rendered)) {
    const parsed = JSON.parse(rendered.right) as { relations: ReadonlyArray<{ uid: string; participants: ReadonlyArray<{ role: string; uid: string }> }> }
    expect(parsed.relations.map((relation) => relation.uid)).toEqual(["r:invalidates", "r:requires", "r:checks", "r:distractor"])
    expect(parsed.relations[0]!.participants).toEqual([{ role: "change", uid: "change:a" }, { role: "artifact", uid: "artifact:x" }, { role: "context", uid: "scope:a" }])
  }
})

it("builds training and inference prompts without putting a hidden target label in a target payload", () => {
  const hiddenTarget = { ...target, expectedUids: ["NEVER-IN-PROMPT"] } as CalibrationTarget & { readonly expectedUids: ReadonlyArray<string> }
  const open = buildOpenBookPrompt(training, hiddenTarget)
  const lesson = buildTextLessonInferencePrompt("follow available relations", hiddenTarget, CALIBRATION_PUBLIC_PRIMITIVES)
  const consolidate = buildExecutableProgramConsolidationPrompt(training, [
    { meaning: "Declared KG relation: INVALIDATES", fromRole: "change", toRole: "artifact" },
    { meaning: "Declared KG relation: REQUIRES", fromRole: "artifact", toRole: "requirement" },
    { meaning: "Declared KG relation: CHECKS", fromRole: "requirement", toRole: "check" }
  ])
  const programInference = buildProgramInferencePrompt(program, hiddenTarget)
  for (const built of [open, lesson, consolidate, programInference]) {
    expect(Either.isRight(built)).toBe(true)
    if (Either.isRight(built)) {
      expect(built.right.containsTargetLabels).toBe(false)
      expect(built.right.text).not.toContain("NEVER-IN-PROMPT")
    }
  }
  if (Either.isRight(open)) expect(open.right.text).toContain("check:x")
  const sharedGrammar = "Here returns the target focus UID. Traverse first evaluates input"
  for (const built of [open, lesson, programInference]) {
    if (Either.isRight(built)) expect(built.right.text).toContain(sharedGrammar)
  }
})

it("accepts only JSON or one json fence and rejects duplicate UIDs, nulls, and extra output keys", () => {
  const direct = parseUidInferenceResponse('{"uids":["b","a"]}')
  const fenced = parseInferenceResponse('```json\n{"program":{"tag":"Here"}}\n```')
  expect(Either.isRight(direct) && direct.right).toEqual(["a", "b"])
  expect(Either.isRight(fenced) && fenced.right).toEqual({ program: { tag: "Here" } })
  expect(Either.isLeft(parseUidInferenceResponse('{"uids":["a","a"]}'))).toBe(true)
  expect(Either.isLeft(parseUidInferenceResponse('{"uids":null}'))).toBe(true)
  expect(Either.isLeft(parseInferenceResponse('{"uids":[],"program":{"tag":"Here"}}'))).toBe(true)
  expect(Either.isLeft(parseInferenceResponse('answer: {"uids":[]}'))).toBe(true)
  expect(Either.isRight(parseLessonResponse('```json\n{"lesson":"a relevant rule"}\n```'))).toBe(true)
  expect(Either.isLeft(parseLessonResponse('{"lesson":""}'))).toBe(true)
  expect(Either.isLeft(parseLessonResponse(JSON.stringify({ lesson: "x".repeat(8193) })))) .toBe(true)
})

it("agrees with the existing bounded evaluator across A and exposed calibration seeds", () => {
  const tasks = [11, 12, 13, 14, 15, 16, 17, 18].map((seed) => catalogTask(seed, 1, 2)).concat(
    [401, 402, 403, 404, 405, 406].map((seed) => catalogTask(seed, 3, 3))
  )
  for (const task of tasks) {
    const established = evaluateProgram(task.graph, task.focus, program)
    const independent = evaluateIndependentProgram(task.graph, task.focus, program)
    expect(Either.isRight(established) && Either.isRight(independent)).toBe(true)
    if (Either.isRight(established) && Either.isRight(independent)) {
      expect(independent.right.uids).toEqual(established.right.uids)
      expect(independent.right.uids).toEqual(task.expected)
    }
  }
})

it("runs the bounded calibration interpreter by exact relation meaning and named roles", () => {
  const result = evaluateIndependentProgram(graph, "change:a", program)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right.uids).toEqual(["check:x"])
    expect(result.right.interpreter).toBe("INDEPENDENT_CALIBRATION_INTERPRETER_V1")
  }
  const wrongRole: CalibrationProgram = { ...program, fromRole: "not-a-declared-role" }
  const wrong = evaluateIndependentProgram(graph, "change:a", wrongRole)
  expect(Either.isRight(wrong) && wrong.right.uids).toEqual([])
})

it("fails closed for malformed ASTs and exhausted independent execution budget", () => {
  expect(Either.isLeft(parseProgramResponse('{"program":{"tag":"Traverse","input":{"tag":"Here"},"meaning":"M","fromRole":"x","toRole":"y","extra":true}}'))).toBe(true)
  expect(Either.isLeft(evaluateIndependentProgram(graph, "change:a", program, 1))).toBe(true)
})
