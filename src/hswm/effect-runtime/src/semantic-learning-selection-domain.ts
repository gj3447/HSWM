/**
 * Pure finite observed-population selection rule ported from
 * `formal/HSWMNoisyFeedback.lean`.
 *
 * This evaluates only supplied labels and deterministic prediction tables.  A
 * truth function and a bound on label corruption are deliberately absent: the
 * Lean true-gain theorem is conditional on those external premises.  Therefore
 * a successful selection here is not evidence of real-model learning.
 */
import { Either } from "effect"

export const SEMANTIC_LEARNING_SELECTION_V1 = "hswm-semantic-learning-selection/v1" as const

export interface ObservedSemanticOutcome {
  readonly inputKey: string
  readonly label: boolean
  /** A nonnegative exact integer mass, corresponding to Lean `Nat`. */
  readonly mass: bigint
}

/** One total Boolean output per input key for each candidate relation. */
export type DeterministicPredictionTable = Readonly<Record<string, boolean>>

export interface SemanticLearningSelectionRequest {
  readonly observations: ReadonlyArray<ObservedSemanticOutcome>
  readonly currentPredictions: DeterministicPredictionTable
  readonly candidatePredictions: DeterministicPredictionTable
  /** Declared upper bound, in the same population-mass unit, on corrupt labels. */
  readonly allowance: bigint
  /** Declared incremental cost in the same population-mass unit. */
  readonly debit: bigint
}

export interface SemanticLearningSelectionError {
  readonly code:
    | "INVALID_INPUT_KEY"
    | "INVALID_LABEL"
    | "INVALID_MASS"
    | "NEGATIVE_MASS"
    | "INVALID_ALLOWANCE"
    | "INVALID_DEBIT"
    | "MISSING_CURRENT_PREDICTION"
    | "MISSING_CANDIDATE_PREDICTION"
    | "INVALID_CURRENT_PREDICTION"
    | "INVALID_CANDIDATE_PREDICTION"
  readonly detail: string
}

export type SemanticLearningSelection = "CURRENT" | "CANDIDATE"
export type SemanticLearningSelectionReason = "EMPTY_OR_ZERO_MASS" | "INSUFFICIENT_OBSERVED_MARGIN" | "STRICT_OBSERVED_MARGIN"

export interface SemanticLearningSelectionResult {
  readonly schemaVersion: typeof SEMANTIC_LEARNING_SELECTION_V1
  readonly selection: SemanticLearningSelection
  readonly reason: SemanticLearningSelectionReason
  readonly observationCount: number
  readonly totalMass: bigint
  readonly currentObservedScore: bigint
  readonly candidateObservedScore: bigint
  /** `currentObservedScore + 2 * allowance + debit`, exactly as in Lean `choose`. */
  readonly requiredCandidateObservedScore: bigint
  readonly allowance: bigint
  readonly debit: bigint
  readonly observedGuardPasses: boolean
  readonly claimCeiling: "CONDITIONAL_FINITE_OBSERVED_POPULATION_NOT_REAL_LLM_PROOF"
}

const error = (code: SemanticLearningSelectionError["code"], detail: string): SemanticLearningSelectionError =>
  Object.freeze({ code, detail })

const isRecord = (value: unknown): value is Readonly<Record<string, unknown>> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const predictionFor = (
  table: unknown,
  inputKey: string,
  side: "current" | "candidate"
): Either.Either<boolean, SemanticLearningSelectionError> => {
  if (!isRecord(table) || !Object.prototype.hasOwnProperty.call(table, inputKey)) {
    return Either.left(error(
      side === "current" ? "MISSING_CURRENT_PREDICTION" : "MISSING_CANDIDATE_PREDICTION",
      `${side} prediction table is missing input key: ${inputKey}`
    ))
  }
  const prediction = table[inputKey]
  if (typeof prediction !== "boolean") {
    return Either.left(error(
      side === "current" ? "INVALID_CURRENT_PREDICTION" : "INVALID_CANDIDATE_PREDICTION",
      `${side} prediction for input key ${inputKey} must be boolean`
    ))
  }
  return Either.right(prediction)
}

const validNonnegativeMass = (
  value: unknown,
  invalid: "INVALID_MASS" | "INVALID_ALLOWANCE" | "INVALID_DEBIT",
  negativeDetail: string
): Either.Either<bigint, SemanticLearningSelectionError> => {
  if (typeof value !== "bigint") return Either.left(error(invalid, `${invalid.toLowerCase()} must be bigint`))
  return value < 0n ? Either.left(error("NEGATIVE_MASS", negativeDetail)) : Either.right(value)
}

/**
 * Computes Lean's executable `choose` guard using exact bigint mass. Repeated
 * rows are intentionally retained, including contradictory labels for one
 * input key; they are distinct observed-population mass, as in the formal
 * assessment population.
 */
export const selectSemanticLearningCandidate = (
  request: SemanticLearningSelectionRequest
): Either.Either<SemanticLearningSelectionResult, SemanticLearningSelectionError> => {
  const allowance = validNonnegativeMass(request.allowance, "INVALID_ALLOWANCE", "allowance must be nonnegative")
  if (Either.isLeft(allowance)) return Either.left(allowance.left)
  const debit = validNonnegativeMass(request.debit, "INVALID_DEBIT", "debit must be nonnegative")
  if (Either.isLeft(debit)) return Either.left(debit.left)

  let totalMass = 0n
  let currentObservedScore = 0n
  let candidateObservedScore = 0n
  for (const observation of request.observations) {
    if (typeof observation.inputKey !== "string" || observation.inputKey.length === 0) {
      return Either.left(error("INVALID_INPUT_KEY", "observation inputKey must be a nonempty string"))
    }
    if (typeof observation.label !== "boolean") {
      return Either.left(error("INVALID_LABEL", `observation label for ${observation.inputKey} must be boolean`))
    }
    const mass = validNonnegativeMass(observation.mass, "INVALID_MASS", `mass for ${observation.inputKey} must be nonnegative`)
    if (Either.isLeft(mass)) return Either.left(mass.left)
    const current = predictionFor(request.currentPredictions, observation.inputKey, "current")
    if (Either.isLeft(current)) return Either.left(current.left)
    const candidate = predictionFor(request.candidatePredictions, observation.inputKey, "candidate")
    if (Either.isLeft(candidate)) return Either.left(candidate.left)
    totalMass += mass.right
    if (current.right === observation.label) currentObservedScore += mass.right
    if (candidate.right === observation.label) candidateObservedScore += mass.right
  }

  const requiredCandidateObservedScore = currentObservedScore + 2n * allowance.right + debit.right
  const observedGuardPasses = totalMass > 0n && requiredCandidateObservedScore < candidateObservedScore
  const reason: SemanticLearningSelectionReason = totalMass === 0n
    ? "EMPTY_OR_ZERO_MASS"
    : observedGuardPasses ? "STRICT_OBSERVED_MARGIN" : "INSUFFICIENT_OBSERVED_MARGIN"
  return Either.right(Object.freeze({
    schemaVersion: SEMANTIC_LEARNING_SELECTION_V1,
    selection: observedGuardPasses ? "CANDIDATE" : "CURRENT",
    reason,
    observationCount: request.observations.length,
    totalMass,
    currentObservedScore,
    candidateObservedScore,
    requiredCandidateObservedScore,
    allowance: allowance.right,
    debit: debit.right,
    observedGuardPasses,
    claimCeiling: "CONDITIONAL_FINITE_OBSERVED_POPULATION_NOT_REAL_LLM_PROOF"
  }))
}
