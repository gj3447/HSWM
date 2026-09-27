import { describe, expect, it } from "vitest"
import { Either } from "effect"
import {
  DOOR_RULE_CENSUS,
  assessDoorRulePredictions,
  doorRuleActorView,
  doorRuleCases,
  observeDoorRulePrediction
} from "../../src/hswm/effect-runtime/src/semantic-rule-environment.js"

const expected = (input: { power: boolean; locked: boolean; pressed: boolean; manualRelease: boolean }) =>
  input.manualRelease || (input.pressed && input.power && !input.locked)

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("expected right")
  return value.right
}
const actorJson = (id: string) => JSON.stringify(right(doorRuleActorView(id)))

describe("semantic rule environment", () => {
  it("covers the fixed 16-case authored door truth table", () => {
    expect(DOOR_RULE_CENSUS).toHaveLength(16)
    for (const testCase of DOOR_RULE_CENSUS) {
      const observation = right(observeDoorRulePrediction(testCase.id, expected(testCase.input)))
      expect(observation.observed).toBe(expected(testCase.input))
      expect(observation.correct).toBe(true)
    }
  })

  it("has immutable, disjoint declared splits with positive and negative cases", () => {
    expect(Object.isFrozen(DOOR_RULE_CENSUS)).toBe(true)
    const seen = new Set<string>()
    for (const split of ["train", "development", "heldout"] as const) {
      const cases = doorRuleCases(split)
      expect(Object.isFrozen(cases)).toBe(true)
      expect(cases.every((testCase) => testCase.split === split)).toBe(true)
      expect(cases.some((testCase) => expected(testCase.input))).toBe(true)
      expect(cases.some((testCase) => !expected(testCase.input))).toBe(true)
      for (const testCase of cases) {
        expect(Object.isFrozen(testCase)).toBe(true)
        expect(Object.isFrozen(testCase.input)).toBe(true)
        expect(seen.has(testCase.id)).toBe(false)
        seen.add(testCase.id)
      }
    }
    expect(seen.size).toBe(16)
    expect(doorRuleCases("train")).toHaveLength(8)
    expect(doorRuleCases("development")).toHaveLength(4)
    expect(doorRuleCases("heldout")).toHaveLength(4)
  })

  it("keeps evaluator labels, identities, and splits out of actor-visible views", () => {
    for (const testCase of DOOR_RULE_CENSUS) {
      const view = right(doorRuleActorView(testCase.id))
      expect(Object.keys(view).sort()).toEqual(["context", "input"])
      expect(Object.isFrozen(view)).toBe(true)
      expect(Object.isFrozen(view.input)).toBe(true)
      expect(actorJson(testCase.id)).not.toContain(testCase.id)
      expect(actorJson(testCase.id)).not.toContain(testCase.split)
      expect(actorJson(testCase.id)).not.toContain("\"observed\"")
      expect(actorJson(testCase.id)).not.toContain("\"opens\"")
      expect(actorJson(testCase.id)).not.toContain("\"oracle\"")
    }
  })

  it("makes every omitted-condition rule fail on a declared training counterexample", () => {
    const train = doorRuleCases("train")
    const wrongRules = [
      (input: typeof train[number]["input"]) => input.pressed && input.power && !input.locked,
      (input: typeof train[number]["input"]) => input.manualRelease || (input.pressed && !input.locked),
      (input: typeof train[number]["input"]) => input.manualRelease || (input.pressed && input.power),
      (input: typeof train[number]["input"]) => input.manualRelease || (input.power && !input.locked)
    ]
    for (const rule of wrongRules) {
      expect(train.some((testCase) => rule(testCase.input) !== expected(testCase.input))).toBe(true)
    }
  })

  it("rejects duplicate and cross-split predictions before scoring", () => {
    const train = doorRuleCases("train")[0]!
    const heldout = doorRuleCases("heldout")[0]!
    const duplicate = assessDoorRulePredictions("train", [
      { caseId: train.id, prediction: true },
      { caseId: train.id, prediction: false }
    ])
    expect(Either.isLeft(duplicate) && duplicate.left.code).toBe("DUPLICATE_PREDICTION")
    const crossSplit = assessDoorRulePredictions("train", [{ caseId: heldout.id, prediction: true }])
    expect(Either.isLeft(crossSplit) && crossSplit.left.code).toBe("CROSS_SPLIT_PREDICTION")
    const invalid = assessDoorRulePredictions("train", [{ caseId: heldout.id, prediction: "invalid" as never }])
    expect(Either.isLeft(invalid) && invalid.left.code).toBe("INVALID_PREDICTION")
  })

  it("retains null and missing outputs in the evaluation denominator", () => {
    const heldout = doorRuleCases("heldout")
    const assessment = right(assessDoorRulePredictions("heldout", [
      { caseId: heldout[0]!.id, prediction: expected(heldout[0]!.input) },
      { caseId: heldout[1]!.id, prediction: null },
      { caseId: "unknown-case", prediction: true }
    ]))
    expect(assessment.denominator).toBe(4)
    expect(assessment.correct).toBe(1)
    expect(assessment.parseFailures).toBe(3)
    expect(assessment.missingPredictions).toBe(2)
    expect(assessment.unknownCaseIds).toEqual(["unknown-case"])
  })
})
