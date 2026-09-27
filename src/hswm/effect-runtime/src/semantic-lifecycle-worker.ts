/** Process-isolated stages for the finite semantic-lifecycle diagnostic. */
import { join } from "node:path"

import { Effect, Either, Schema } from "effect"

import {
  assessDoorRulePredictions,
  doorRuleActorView,
  doorRuleCases,
  type DoorRuleAssessment,
  type DoorRuleSplit
} from "./semantic-rule-environment.js"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { GraphLoopEngineeringController } from "./canonical-atom-v2-graph-loop-engineering.js"
import {
  executeLlmSemanticRelation,
  learnLlmSemanticRelation,
  stageLlmSemanticOutcome,
  type SemanticOutcome,
  type SemanticTrace
} from "./canonical-atom-v2-llm-semantic-runtime.js"
import {
  LifecycleArmSchema,
  LifecycleStageSchema,
  lifecycleFailure,
  type LifecycleArm,
  type LifecycleConfig,
  type LifecycleStage
} from "./semantic-lifecycle-domain.js"
import { readLifecycleConfig, readLifecycleJson, writeLifecycleJson } from "./semantic-lifecycle-io.js"
import {
  INITIAL_TEXT,
  SHAM_TEXT,
  admissionForSemanticLifecycle,
  authorizationRef,
  inspectSemanticLifecycleState,
  makeSemanticLifecycleFileLayer,
  relationUid,
  scope,
  seedSemanticLifecycle
} from "./semantic-lifecycle-runtime.js"
import { createSemanticLifecycleTransport, type CallReceipt } from "./semantic-lifecycle-transport.js"

export const SEMANTIC_LIFECYCLE_WORKER_V1 = "hswm-semantic-lifecycle-worker/v1" as const

export interface LifecycleActorEvent {
  readonly instruction: string
  readonly cases: ReadonlyArray<unknown>
}

export interface LifecycleWorkerReport {
  readonly contract: typeof SEMANTIC_LIFECYCLE_WORKER_V1
  readonly stage: LifecycleStage
  readonly arm: LifecycleArm
  readonly processId: number
  readonly parentProcessId: number
  readonly calls: ReadonlyArray<CallReceipt>
  readonly [field: string]: unknown
}

const workerFailure = (code: string, detail: string) => lifecycleFailure(code, detail)

const right = <A>(value: Either.Either<A, { readonly code: string; readonly detail: string }>) =>
  Either.mapLeft(value, (error) => workerFailure(error.code, error.detail))

/** Model-visible event payload has neither split label, case id, nor oracle result. */
export const actorEvent = (split: DoorRuleSplit): Either.Either<string, ReturnType<typeof workerFailure>> => {
  const views = Either.all(doorRuleCases(split).map((entry) => right(doorRuleActorView(entry.id))))
  return Either.map(views, (cases) => JSON.stringify({
    instruction: "Predict a bit per case in the given order. Use the supplied relation as the current hypothesis.",
    cases
  }))
}

/** Invalid or refused output is represented as null for every expected row. */
export const assessBatch = (split: DoorRuleSplit, output: string | null): Either.Either<DoorRuleAssessment, ReturnType<typeof workerFailure>> => {
  const cases = doorRuleCases(split)
  const valid = typeof output === "string" && new RegExp(`^[01]{${cases.length}}$`).test(output)
  return right(assessDoorRulePredictions(split, cases.map((entry, index) => ({
    caseId: entry.id,
    prediction: valid ? output[index] === "1" : null
  }))))
}

const DescriptorSchema = Schema.Struct({ sha256: Schema.String, mediaType: Schema.String, byteLength: Schema.Number })
const RelationKeySchema = Schema.Struct({ schemaVersion: Schema.String, lineageId: Schema.String, atomUid: Schema.String, revisionId: Schema.Number })
const SemanticTraceSchema = Schema.Struct({
  executionId: Schema.String, traceSha256: Schema.String, traceContent: DescriptorSchema, frameSha256: Schema.String,
  event: Schema.String, relationKey: RelationKeySchema, prediction: Schema.String, predictionSha256: Schema.String,
  uncertainty: Schema.String, backendConfigurationSha256: Schema.String
})
const SemanticOutcomeSchema = Schema.Struct({
  traceSha256: Schema.String, predictionSha256: Schema.String, observed: Schema.String, source: Schema.String,
  outcomeContent: DescriptorSchema, status: Schema.Literal("CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED")
})
const TrainingReportSchema = Schema.Struct({ trace: SemanticTraceSchema, outcome: SemanticOutcomeSchema })

const readTraining = (path: string): Effect.Effect<Readonly<{ readonly trace: SemanticTrace; readonly outcome: SemanticOutcome }>, ReturnType<typeof workerFailure>, import("./effect-posix-filesystem.js").PosixFileSystem> =>
  readLifecycleJson(path).pipe(
    Effect.flatMap(Schema.decodeUnknown(TrainingReportSchema)),
    Effect.mapError(() => workerFailure("TRAINING_REPORT_INVALID", "Stored training report has an invalid semantic trace or outcome")),
    Effect.map((value) => Object.freeze({ trace: value.trace, outcome: value.outcome }))
  )

const controls = (stage: LifecycleStage, arm: LifecycleArm): string | undefined =>
  stage === "revise" && arm !== "learned" ? arm === "sham" ? SHAM_TEXT : INITIAL_TEXT : undefined

const semanticCell = (config: LifecycleConfig) => config.cell.api_key_env === undefined
  ? Object.freeze({ base_url: config.cell.base_url, model: config.cell.model, max_tokens: config.cell.max_tokens })
  : config.cell

const validateStageArm = (stage: string, arm: string, config: LifecycleConfig): Effect.Effect<Readonly<{ readonly stage: LifecycleStage; readonly arm: LifecycleArm }>, ReturnType<typeof workerFailure>> =>
  Effect.gen(function* () {
    const decodedStage = yield* Schema.decodeUnknown(LifecycleStageSchema)(stage).pipe(Effect.mapError(() => workerFailure("WORKER_INVALID", "Invalid lifecycle stage")))
    const decodedArm = yield* Schema.decodeUnknown(LifecycleArmSchema)(arm).pipe(Effect.mapError(() => workerFailure("WORKER_INVALID", "Invalid lifecycle arm")))
    if (decodedStage === "train" && decodedArm !== "base") return yield* Effect.fail(workerFailure("WORKER_INVALID", "Training requires the base arm"))
    if (decodedStage !== "train" && (decodedArm === "base" || !config.arms.includes(decodedArm))) return yield* Effect.fail(workerFailure("WORKER_INVALID", "Stage requires a configured experimental arm"))
    return Object.freeze({ stage: decodedStage, arm: decodedArm })
  })

const train = (config: LifecycleConfig, http: import("./adaptive-executor.js").AdaptiveHttpClientShape) => Effect.gen(function* () {
  yield* seedSemanticLifecycle
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const event = yield* actorEvent("train")
  const trace = yield* executeLlmSemanticRelation(runtime, relationUid, event, semanticCell(config), http)
  const assessment = yield* assessBatch("train", trace.prediction)
  const observedCases = yield* Either.all(assessment.observations.map((observation) => right(doorRuleActorView(observation.caseId)).pipe(
    Either.map((view) => Object.freeze({ ...view, observed: observation.observed }))
  )))
  const outcome = yield* stageLlmSemanticOutcome(runtime, trace, JSON.stringify({ cases: observedCases, observationKind: "AUTHORED_FINITE_ENVIRONMENT" }), `authored-door-environment:sha256:${config.environmentSha256}`)
  return Object.freeze({ trace, outcome, assessment, state: yield* inspectSemanticLifecycleState })
})

const revise = (config: LifecycleConfig, arm: LifecycleArm, http: import("./adaptive-executor.js").AdaptiveHttpClientShape) => Effect.gen(function* () {
  const training = yield* readTraining(join(config.root, "train-base.json"))
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const controller = yield* GraphLoopEngineeringController
  const before = yield* inspectSemanticLifecycleState
  const admission = yield* admissionForSemanticLifecycle(runtime, controller, training.trace, training.outcome, arm)
  const decidedAt = yield* Effect.clockWith((clock) => clock.currentTimeMillis).pipe(Effect.map((millis) => new Date(millis).toISOString()))
  const attempted = yield* learnLlmSemanticRelation(runtime, training.trace, training.outcome, semanticCell(config), http, authorizationRef, scope, decidedAt, admission).pipe(Effect.either)
  const after = yield* inspectSemanticLifecycleState
  const committed = Either.isRight(attempted) && attempted.right.disposition === "COMMITTED"
  return Object.freeze({
    committed,
    disposition: Either.isRight(attempted) ? attempted.right.disposition : "PROPOSAL_FAILED",
    errorCode: Either.isLeft(attempted) ? "code" in attempted.left ? attempted.left.code : "UNCLASSIFIED" : null,
    before, after,
    semanticFieldsChanged: (["semanticText", "disposition", "uncertainty"] as const).filter((key) => before.semantic[key] !== after.semantic[key]),
    outcomeSha256: training.outcome.outcomeContent.sha256
  })
})

const evaluate = (config: LifecycleConfig, stage: Exclude<LifecycleStage, "train" | "revise">, http: import("./adaptive-executor.js").AdaptiveHttpClientShape) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const before = yield* inspectSemanticLifecycleState
  const event = yield* actorEvent(stage)
  const attempted = yield* executeLlmSemanticRelation(runtime, relationUid, event, semanticCell(config), http).pipe(Effect.either)
  const after = yield* inspectSemanticLifecycleState
  if (before.canonicalSha256 !== after.canonicalSha256) return yield* Effect.fail(workerFailure("EVALUATION_MUTATED_CANONICAL", "Evaluation changed canonical state"))
  const trace = Either.isRight(attempted) ? attempted.right : null
  const assessment = yield* assessBatch(stage, trace === null ? null : trace.prediction)
  return Object.freeze({ before, after, canonicalUnchanged: true, trace, assessment, errorCode: Either.isLeft(attempted) ? "code" in attempted.left ? attempted.left.code : "UNCLASSIFIED" : null })
})

/**
 * One child-process stage. This function performs no unsafe execution itself;
 * callers provide the POSIX and HTTP services at the executable boundary.
 */
export const runLifecycleWorker = (stageInput: string, configPath: string, armInput: string) => Effect.gen(function* () {
  const config = yield* readLifecycleConfig(configPath)
  const { stage, arm } = yield* validateStageArm(stageInput, armInput, config)
  const processInfo = yield* Effect.sync(() => Object.freeze({ processId: process.pid, parentProcessId: process.ppid }))
  const controlText = controls(stage, arm)
  const transport = yield* createSemanticLifecycleTransport(controlText === undefined
    ? { mode: config.transport, logRoot: join(config.root, "http", `${stage}-${arm}`) }
    : { mode: config.transport, logRoot: join(config.root, "http", `${stage}-${arm}`), controlText })
  const finish = <A extends object>(result: A) => Effect.gen(function* () {
    const report: LifecycleWorkerReport = Object.freeze({ contract: SEMANTIC_LIFECYCLE_WORKER_V1, stage, arm, ...processInfo, ...result, calls: yield* transport.calls })
    yield* writeLifecycleJson(join(config.root, `${stage}-${arm}.json`), report)
    return report
  })
  const layer = makeSemanticLifecycleFileLayer(join(config.root, "states", arm))
  if (stage === "train") return yield* train(config, transport.http).pipe(Effect.provide(layer), Effect.flatMap(finish))
  if (stage === "revise") return yield* revise(config, arm, transport.http).pipe(Effect.provide(layer), Effect.flatMap(finish))
  return yield* evaluate(config, stage, transport.http).pipe(Effect.provide(layer), Effect.flatMap(finish))
})
