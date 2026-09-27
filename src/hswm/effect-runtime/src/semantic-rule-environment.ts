/**
 * A finite authored rule environment for wiring experiments.  It is a
 * deterministic simulator, not an observation of a physical door or world.
 * Its finite split is a lifecycle diagnostic, not a broad generalization measure.
 * The actor view deliberately contains no case identity, split, or oracle.
 */
import { Either } from "effect"

export const DOOR_RULE_ENVIRONMENT_V1 = "hswm-semantic-door-rule-environment/v1" as const

export type DoorRuleSplit = "train" | "development" | "heldout"

export interface DoorRuleInput {
  readonly power: boolean
  readonly locked: boolean
  readonly pressed: boolean
  readonly manualRelease: boolean
}

/** Runner/evaluator metadata. Do not serialize this object into model input. */
export interface DoorRuleCase {
  readonly id: string
  readonly split: DoorRuleSplit
  readonly input: DoorRuleInput
}

/** The complete model-visible payload for one actor call. */
export interface DoorRuleActorView {
  readonly input: DoorRuleInput
  readonly context: Readonly<{
    readonly domain: "authored-door-rule"
    readonly task: "predict-whether-door-opens"
  }>
}

/** Evaluator-only result; `prediction: null` represents an unparsable/refused actor result. */
export interface DoorRuleObservation {
  readonly caseId: string
  readonly split: DoorRuleSplit
  readonly prediction: boolean | null
  readonly observed: boolean
  readonly correct: boolean
}

export interface DoorRulePrediction {
  readonly caseId: string
  readonly prediction: boolean | null
}

export interface DoorRuleEnvironmentError {
  readonly code: "UNKNOWN_CASE" | "INVALID_PREDICTION" | "CROSS_SPLIT_PREDICTION" | "DUPLICATE_PREDICTION"
  readonly detail: string
}

export interface DoorRuleAssessment {
  readonly split: DoorRuleSplit
  readonly denominator: number
  readonly correct: number
  readonly incorrect: number
  readonly parseFailures: number
  readonly missingPredictions: number
  readonly unknownCaseIds: ReadonlyArray<string>
  readonly observations: ReadonlyArray<DoorRuleObservation>
}

type InternalDoorRuleCase = DoorRuleCase & { readonly opens: boolean }

const freezeInput = (input: DoorRuleInput): DoorRuleInput => Object.freeze({ ...input })
const opensFor = (input: DoorRuleInput): boolean =>
  input.manualRelease || (input.pressed && input.power && !input.locked)

const entry = (bits: string, split: DoorRuleSplit): InternalDoorRuleCase => {
  const [power, locked, pressed, manualRelease] = [...bits].map((value) => value === "1")
  const input = freezeInput({ power: power!, locked: locked!, pressed: pressed!, manualRelease: manualRelease! })
  return Object.freeze({ id: `door-${bits}`, split, input, opens: opensFor(input) })
}

// Train contains counterexamples for omitting manual release, power, lock, or press.
const internalCensus = Object.freeze([
  entry("0000", "train"), entry("0001", "train"), entry("0010", "train"), entry("0100", "train"),
  entry("1000", "train"), entry("1010", "train"), entry("1101", "train"), entry("1110", "train"),
  entry("0011", "development"), entry("0110", "development"), entry("1011", "development"), entry("1111", "development"),
  entry("0101", "heldout"), entry("0111", "heldout"), entry("1001", "heldout"), entry("1100", "heldout")
] as const)

const publicCase = (value: InternalDoorRuleCase): DoorRuleCase => Object.freeze({
  id: value.id,
  split: value.split,
  input: freezeInput(value.input)
})

/** All runner-visible cases; no oracle label is exposed. */
export const DOOR_RULE_CENSUS: ReadonlyArray<DoorRuleCase> = Object.freeze(internalCensus.map(publicCase))

const byId: ReadonlyMap<string, InternalDoorRuleCase> = new Map(internalCensus.map((value) => [value.id, value] as const))
const actorContext = Object.freeze({ domain: "authored-door-rule" as const, task: "predict-whether-door-opens" as const })

const failure = (code: DoorRuleEnvironmentError["code"], detail: string): DoorRuleEnvironmentError =>
  Object.freeze({ code, detail })

const knownCase = (caseId: string): Either.Either<InternalDoorRuleCase, DoorRuleEnvironmentError> => {
  const value = byId.get(caseId)
  return value === undefined
    ? Either.left(failure("UNKNOWN_CASE", `unknown door-rule case: ${caseId}`))
    : Either.right(value)
}

export const doorRuleCases = (split: DoorRuleSplit): ReadonlyArray<DoorRuleCase> =>
  Object.freeze(DOOR_RULE_CENSUS.filter((value) => value.split === split))

export const doorRuleActorView = (caseId: string): Either.Either<DoorRuleActorView, DoorRuleEnvironmentError> => {
  const value = knownCase(caseId)
  return Either.isLeft(value)
    ? Either.left(value.left)
    : Either.right(Object.freeze({ input: freezeInput(value.right.input), context: actorContext }))
}

/** The evaluator alone resolves the authored rule against a bound case id. */
export const observeDoorRulePrediction = (caseId: string, prediction: boolean | null): Either.Either<DoorRuleObservation, DoorRuleEnvironmentError> => {
  const value = knownCase(caseId)
  if (Either.isLeft(value)) return Either.left(value.left)
  if (prediction !== null && typeof prediction !== "boolean") {
    return Either.left(failure("INVALID_PREDICTION", "door-rule prediction must be boolean or null"))
  }
  return Either.right(Object.freeze({
    caseId: value.right.id,
    split: value.right.split,
    prediction,
    observed: value.right.opens,
    correct: prediction === value.right.opens
  }))
}

/**
 * Scores every case in a declared split. Missing or null predictions remain in
 * the denominator, preventing a parser/refusal from disappearing from results.
 */
export const assessDoorRulePredictions = (
  split: DoorRuleSplit,
  predictions: ReadonlyArray<DoorRulePrediction>
): Either.Either<DoorRuleAssessment, DoorRuleEnvironmentError> => {
  const expected = internalCensus.filter((value) => value.split === split)
  const supplied = new Map<string, boolean | null>()
  const unknown = new Set<string>()
  for (const prediction of predictions) {
    const known = byId.get(prediction.caseId)
    if (known === undefined) {
      unknown.add(prediction.caseId)
      continue
    }
    if (prediction.prediction !== null && typeof prediction.prediction !== "boolean") {
      return Either.left(failure("INVALID_PREDICTION", "door-rule prediction must be boolean or null"))
    }
    if (known.split !== split) {
      return Either.left(failure("CROSS_SPLIT_PREDICTION", `door-rule case ${prediction.caseId} belongs to ${known.split}, not ${split}`))
    }
    if (supplied.has(prediction.caseId)) {
      return Either.left(failure("DUPLICATE_PREDICTION", `duplicate door-rule prediction: ${prediction.caseId}`))
    }
    supplied.set(prediction.caseId, prediction.prediction)
  }
  const observations = Either.all(expected.map((value) => observeDoorRulePrediction(value.id, supplied.get(value.id) ?? null)))
  if (Either.isLeft(observations)) return Either.left(observations.left)
  const correct = observations.right.filter((value) => value.correct).length
  const parseFailures = observations.right.filter((value) => value.prediction === null).length
  return Either.right(Object.freeze({
    split,
    denominator: observations.right.length,
    correct,
    incorrect: observations.right.length - correct,
    parseFailures,
    missingPredictions: expected.filter((value) => !supplied.has(value.id)).length,
    unknownCaseIds: Object.freeze([...unknown].sort()),
    observations: Object.freeze(observations.right)
  }))
}
