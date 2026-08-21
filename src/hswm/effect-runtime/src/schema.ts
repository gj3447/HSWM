import { Schema } from "effect"

import {
  MAX_LEARNING_RATE,
  SCORE_SCALE,
  type Incidence
} from "./contracts.js"

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)

const Sha256 = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}$/)
)

const SafeRevision = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative()
)

const ScoreMicros = Schema.Number.pipe(
  Schema.int(),
  Schema.between(-SCORE_SCALE, SCORE_SCALE)
)

const LearningRateMicros = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, MAX_LEARNING_RATE)
)

export const IncidenceSchema: Schema.Schema<Incidence> = Schema.Struct({
  role: Identifier,
  nodeId: Identifier
})

export interface OutcomeCreditCommand {
  readonly _tag: "ApplyOutcomeCredit"
  readonly eventId: string
  readonly outcomeId: string
  readonly expectedRevision: number
  readonly trajectoryId: string
  readonly relationId: string
  readonly incidences: ReadonlyArray<Incidence>
  readonly functionCellId: string
  readonly outcomeScoreMicros: number
  readonly learningRateMicros: number
  readonly capabilityId: string
  readonly provenanceSha256: string
}

export const OutcomeCreditCommandSchema: Schema.Schema<OutcomeCreditCommand> =
  Schema.Struct({
    _tag: Schema.Literal("ApplyOutcomeCredit"),
    eventId: Identifier,
    outcomeId: Identifier,
    expectedRevision: SafeRevision,
    trajectoryId: Identifier,
    relationId: Identifier,
    incidences: Schema.Array(IncidenceSchema).pipe(Schema.minItems(2)),
    functionCellId: Identifier,
    outcomeScoreMicros: ScoreMicros,
    learningRateMicros: LearningRateMicros,
    capabilityId: Identifier,
    provenanceSha256: Sha256
  })

export const decodeOutcomeCreditCommand = Schema.decodeUnknown(
  OutcomeCreditCommandSchema,
  { onExcessProperty: "error" }
)

export const snapshotOutcomeCreditCommand = (
  command: OutcomeCreditCommand
): OutcomeCreditCommand =>
  Object.freeze({
    ...command,
    incidences: Object.freeze(
      command.incidences.map((incidence) => Object.freeze({ ...incidence }))
    )
  })
