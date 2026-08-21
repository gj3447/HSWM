import { Data, Either } from "effect"

import {
  MAX_LEARNING_RATE,
  SCORE_SCALE,
  type HSWMState,
  type Incidence,
  type SemanticWeight
} from "./contracts.js"
import type { OutcomeCreditCommand } from "./schema.js"

export class RevisionConflict extends Data.TaggedError("RevisionConflict")<{
  readonly expected: number
  readonly actual: number
}> {}

export class RevisionExhausted extends Data.TaggedError("RevisionExhausted")<{
  readonly revision: number
}> {}

export class DuplicateEvent extends Data.TaggedError("DuplicateEvent")<{
  readonly eventId: string
}> {}

export class DuplicateOutcome extends Data.TaggedError("DuplicateOutcome")<{
  readonly outcomeId: string
}> {}

export class PolicyDenied extends Data.TaggedError("PolicyDenied")<{
  readonly reason:
    | "INVALID_COMMAND"
    | "INVALID_INCIDENCE_SET"
    | "INVALID_PROVENANCE"
    | "LEARNING_BUDGET_EXCEEDED"
    | "UNAUTHORIZED_OUTCOME"
}> {}

export class RelationShapeConflict extends Data.TaggedError(
  "RelationShapeConflict"
)<{
  readonly relationId: string
}> {}

export class UnknownRelation extends Data.TaggedError("UnknownRelation")<{
  readonly relationId: string
}> {}

export class UnknownFunctionCell extends Data.TaggedError(
  "UnknownFunctionCell"
)<{
  readonly functionCellId: string
}> {}

export class IneligibleTrajectory extends Data.TaggedError(
  "IneligibleTrajectory"
)<{
  readonly trajectoryId: string
}> {}

export type TransitionError =
  | RevisionConflict
  | RevisionExhausted
  | DuplicateEvent
  | DuplicateOutcome
  | PolicyDenied
  | RelationShapeConflict
  | UnknownRelation
  | UnknownFunctionCell
  | IneligibleTrajectory

const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/

const isIdentifier = (value: unknown): value is string =>
  typeof value === "string" && IDENTIFIER_PATTERN.test(value)

const isSafeIntegerBetween = (
  value: unknown,
  minimum: number,
  maximum: number
): value is number =>
  typeof value === "number" &&
  Number.isSafeInteger(value) &&
  value >= minimum &&
  value <= maximum

const compareText = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0

const compareIncidences = (left: Incidence, right: Incidence): number => {
  const roleOrder = compareText(left.role, right.role)
  return roleOrder === 0 ? compareText(left.nodeId, right.nodeId) : roleOrder
}

const isCanonicalIncidenceSet = (
  incidences: ReadonlyArray<Incidence>
): boolean => {
  if (incidences.length < 2) return false
  const seen: Array<Incidence> = []
  for (let index = 0; index < incidences.length; index += 1) {
    const incidence = incidences[index]
    if (
      incidence === undefined ||
      !isIdentifier(incidence.role) ||
      !isIdentifier(incidence.nodeId)
    ) {
      return false
    }
    if (
      seen.some(
        (prior) =>
          prior.role === incidence.role && prior.nodeId === incidence.nodeId
      )
    ) {
      return false
    }
    seen.push(incidence)
    if (
      index > 0 &&
      compareIncidences(incidences[index - 1] as Incidence, incidence) >= 0
    ) {
      return false
    }
  }
  return true
}

const sameIncidences = (
  left: ReadonlyArray<Incidence>,
  right: ReadonlyArray<Incidence>
): boolean =>
  left.length === right.length &&
  left.every(
    (incidence, index) =>
      incidence.role === right[index]?.role &&
      incidence.nodeId === right[index]?.nodeId
  )

export const evaluatePolicy = (
  command: OutcomeCreditCommand
): Either.Either<void, PolicyDenied> => {
  if (!/^[0-9a-f]{64}$/.test(command.provenanceSha256)) {
    return Either.left(new PolicyDenied({ reason: "INVALID_PROVENANCE" }))
  }
  if (
    !isSafeIntegerBetween(
      command.learningRateMicros,
      1,
      MAX_LEARNING_RATE
    )
  ) {
    return Either.left(
      new PolicyDenied({ reason: "LEARNING_BUDGET_EXCEEDED" })
    )
  }
  if (!isCanonicalIncidenceSet(command.incidences)) {
    return Either.left(new PolicyDenied({ reason: "INVALID_INCIDENCE_SET" }))
  }
  if (
    command._tag !== "ApplyOutcomeCredit" ||
    !isIdentifier(command.eventId) ||
    !isIdentifier(command.outcomeId) ||
    !isSafeIntegerBetween(command.expectedRevision, 0, Number.MAX_SAFE_INTEGER) ||
    !isIdentifier(command.trajectoryId) ||
    !isIdentifier(command.relationId) ||
    !isIdentifier(command.functionCellId) ||
    !isIdentifier(command.capabilityId) ||
    !isSafeIntegerBetween(
      command.outcomeScoreMicros,
      -SCORE_SCALE,
      SCORE_SCALE
    )
  ) {
    return Either.left(new PolicyDenied({ reason: "INVALID_COMMAND" }))
  }
  return Either.right(undefined)
}

const sortedBy = <A>(
  values: ReadonlyArray<A>,
  compare: (left: A, right: A) => number
): ReadonlyArray<A> => [...values].sort(compare)

const validateRelation = (
  state: HSWMState,
  command: OutcomeCreditCommand
): Either.Either<void, UnknownRelation | RelationShapeConflict> => {
  const existing = state.H.hyperedges.find(
    (edge) => edge.relationId === command.relationId
  )
  if (existing !== undefined) {
    return sameIncidences(existing.incidences, command.incidences)
      ? Either.right(undefined)
      : Either.left(
          new RelationShapeConflict({ relationId: command.relationId })
        )
  }
  return Either.left(new UnknownRelation({ relationId: command.relationId }))
}

const validateTrajectory = (
  state: HSWMState,
  command: OutcomeCreditCommand
): Either.Either<number, IneligibleTrajectory> => {
  const index = state.A.trajectories.findIndex(
    (trajectory) => trajectory.trajectoryId === command.trajectoryId
  )
  const trajectory = state.A.trajectories[index]
  if (
    index < 0 ||
    trajectory === undefined ||
    trajectory.status !== "ELIGIBLE" ||
    trajectory.relationId !== command.relationId ||
    trajectory.functionCellId !== command.functionCellId
  ) {
    return Either.left(
      new IneligibleTrajectory({ trajectoryId: command.trajectoryId })
    )
  }
  return Either.right(index)
}

const updateSemanticWeights = (
  state: HSWMState,
  command: OutcomeCreditCommand
): ReadonlyArray<SemanticWeight> => {
  const existingIndex = state.W.semanticWeights.findIndex(
    (weight) =>
      weight.relationId === command.relationId &&
      weight.functionCellId === command.functionCellId
  )
  const previous =
    existingIndex < 0
      ? 0
      : (state.W.semanticWeights[existingIndex]?.scoreMicros ?? 0)
  const evidenceCount =
    existingIndex < 0
      ? 0
      : (state.W.semanticWeights[existingIndex]?.evidenceCount ?? 0)
  const delta = Math.trunc(
    ((command.outcomeScoreMicros - previous) * command.learningRateMicros) /
      SCORE_SCALE
  )
  const nextWeight: SemanticWeight = {
    relationId: command.relationId,
    functionCellId: command.functionCellId,
    scoreMicros: Math.max(
      -SCORE_SCALE,
      Math.min(SCORE_SCALE, previous + delta)
    ),
    evidenceCount: evidenceCount + 1
  }
  const withoutPrevious = state.W.semanticWeights.filter(
    (_, index) => index !== existingIndex
  )
  return sortedBy([...withoutPrevious, nextWeight], (left, right) => {
    const relationOrder = compareText(left.relationId, right.relationId)
    return relationOrder === 0
      ? compareText(left.functionCellId, right.functionCellId)
      : relationOrder
  })
}

export const evolve = (
  state: HSWMState,
  command: OutcomeCreditCommand
): Either.Either<HSWMState, TransitionError> => {
  if (command.expectedRevision !== state.revision) {
    return Either.left(
      new RevisionConflict({
        expected: command.expectedRevision,
        actual: state.revision
      })
    )
  }
  if (state.revision >= Number.MAX_SAFE_INTEGER) {
    return Either.left(new RevisionExhausted({ revision: state.revision }))
  }
  if (state.acceptedEventIds.includes(command.eventId)) {
    return Either.left(new DuplicateEvent({ eventId: command.eventId }))
  }
  if (state.creditedOutcomeIds.includes(command.outcomeId)) {
    return Either.left(new DuplicateOutcome({ outcomeId: command.outcomeId }))
  }
  const policyDecision = evaluatePolicy(command)
  if (Either.isLeft(policyDecision)) return Either.left(policyDecision.left)

  const relation = validateRelation(state, command)
  if (Either.isLeft(relation)) return Either.left(relation.left)
  if (!state.F.functionCellIds.includes(command.functionCellId)) {
    return Either.left(
      new UnknownFunctionCell({ functionCellId: command.functionCellId })
    )
  }
  const trajectory = validateTrajectory(state, command)
  if (Either.isLeft(trajectory)) return Either.left(trajectory.left)

  const trajectories = state.A.trajectories.map((current, index) =>
    index === trajectory.right
      ? {
          ...current,
          status: "CREDITED" as const,
          creditedOutcomeId: command.outcomeId
        }
      : current
  )

  return Either.right({
    revision: state.revision + 1,
    H: state.H,
    W: { semanticWeights: updateSemanticWeights(state, command) },
    A: { trajectories },
    F: state.F,
    acceptedEventIds: [...state.acceptedEventIds, command.eventId],
    creditedOutcomeIds: [...state.creditedOutcomeIds, command.outcomeId]
  })
}
