import { describe, expect, it } from "vitest"
import { Either } from "effect"
import {
  selectSemanticLearningCandidate,
  type SemanticLearningSelectionRequest
} from "../../src/hswm/effect-runtime/src/semantic-learning-selection-domain.js"

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("expected right")
  return value.right
}

const bridgePopulation: SemanticLearningSelectionRequest = {
  // Lean's weighted assessment population: 000 deliberately occurs twice with conflicting labels.
  observations: [
    { inputKey: "000", label: true, mass: 1n },
    { inputKey: "000", label: false, mass: 1n },
    { inputKey: "001", label: false, mass: 2n },
    { inputKey: "010", label: false, mass: 2n },
    { inputKey: "011", label: false, mass: 2n },
    { inputKey: "100", label: false, mass: 2n },
    { inputKey: "101", label: false, mass: 2n },
    { inputKey: "110", label: false, mass: 2n },
    { inputKey: "111", label: true, mass: 2n }
  ],
  currentPredictions: { "000": false, "001": false, "010": false, "011": false, "100": true, "101": true, "110": true, "111": true },
  candidatePredictions: { "000": false, "001": false, "010": false, "011": false, "100": false, "101": false, "110": false, "111": true },
  allowance: 1n,
  debit: 1n
}

describe("semantic learning selection domain", () => {
  it("reproduces the generated Lean bridge observed scores and strict selection", () => {
    const result = right(selectSemanticLearningCandidate(bridgePopulation))
    expect(result.totalMass).toBe(16n)
    expect(result.currentObservedScore).toBe(9n)
    expect(result.candidateObservedScore).toBe(15n)
    expect(result.requiredCandidateObservedScore).toBe(12n)
    expect(result.selection).toBe("CANDIDATE")
    expect(result.reason).toBe("STRICT_OBSERVED_MARGIN")
  })

  it("requires a strict margin, retaining the parent on a tie", () => {
    const result = right(selectSemanticLearningCandidate({
      observations: [{ inputKey: "x", label: true, mass: 5n }],
      currentPredictions: { x: true }, candidatePredictions: { x: true }, allowance: 0n, debit: 0n
    }))
    expect(result.requiredCandidateObservedScore).toBe(5n)
    expect(result.candidateObservedScore).toBe(5n)
    expect(result.selection).toBe("CURRENT")
  })

  it("uses exact bigint arithmetic above Number.MAX_SAFE_INTEGER", () => {
    const mass = 9_007_199_254_740_993n
    const result = right(selectSemanticLearningCandidate({
      observations: [{ inputKey: "x", label: true, mass }],
      currentPredictions: { x: false }, candidatePredictions: { x: true }, allowance: 0n, debit: 0n
    }))
    expect(result.totalMass).toBe(mass)
    expect(result.candidateObservedScore).toBe(mass)
    expect(result.selection).toBe("CANDIDATE")
  })

  it("keeps current for empty or zero-mass populations", () => {
    const empty = right(selectSemanticLearningCandidate({
      observations: [], currentPredictions: {}, candidatePredictions: {}, allowance: 0n, debit: 0n
    }))
    const zero = right(selectSemanticLearningCandidate({
      observations: [{ inputKey: "x", label: true, mass: 0n }],
      currentPredictions: { x: false }, candidatePredictions: { x: true }, allowance: 0n, debit: 0n
    }))
    expect(empty.reason).toBe("EMPTY_OR_ZERO_MASS")
    expect(zero.reason).toBe("EMPTY_OR_ZERO_MASS")
    expect(empty.selection).toBe("CURRENT")
    expect(zero.selection).toBe("CURRENT")
  })

  it("retains the Lean false-noise-allowance degradation counterexample as a guard limitation", () => {
    const result = right(selectSemanticLearningCandidate({
      observations: [{ inputKey: "unit", label: false, mass: 1n }],
      currentPredictions: { unit: true }, candidatePredictions: { unit: false }, allowance: 0n, debit: 0n
    }))
    expect(result.selection).toBe("CANDIDATE")
    expect(result.claimCeiling).toContain("NOT_REAL_LLM_PROOF")
  })

  it("returns typed failures for invalid masses and incomplete or invalid prediction tables", () => {
    const negative = selectSemanticLearningCandidate({ ...bridgePopulation, allowance: -1n })
    expect(Either.isLeft(negative) && negative.left.code).toBe("NEGATIVE_MASS")
    const missing = selectSemanticLearningCandidate({ ...bridgePopulation, currentPredictions: { "000": false } })
    expect(Either.isLeft(missing) && missing.left.code).toBe("MISSING_CURRENT_PREDICTION")
    const invalidMass = selectSemanticLearningCandidate({
      ...bridgePopulation,
      observations: [{ inputKey: "000", label: false, mass: -1n }]
    })
    expect(Either.isLeft(invalidMass) && invalidMass.left.code).toBe("NEGATIVE_MASS")
    const invalidPrediction = selectSemanticLearningCandidate({
      ...bridgePopulation,
      currentPredictions: { ...bridgePopulation.currentPredictions, "000": "not-boolean" as never }
    })
    expect(Either.isLeft(invalidPrediction) && invalidPrediction.left.code).toBe("INVALID_CURRENT_PREDICTION")
  })
})
