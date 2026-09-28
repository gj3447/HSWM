/** Measured development responses -> frozen choice -> fresh next semantic execution. */
import { createHash } from "node:crypto"
import { join } from "node:path"
import { Effect, Either, Schema } from "effect"
import { canonicalJson } from "./adaptive-domain.js"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE, readLlmSemanticFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { deriveSemanticDurableBranch, reopenSelectedSemanticBranch, selectFrozenSemanticDurableCandidate, type FrozenSemanticCandidateRound } from "./canonical-atom-v2-semantic-selected-state.js"
import { lifecycleFailure, type LifecycleConfig } from "./semantic-lifecycle-domain.js"
import { inspectSemanticLifecycleState, makeSemanticLifecycleFileLayer, relationUid } from "./semantic-lifecycle-runtime.js"
import { actorEvent, assessBatch } from "./semantic-lifecycle-worker.js"

export const SEMANTIC_LIFECYCLE_SELECTED_EXECUTION_V1 = "hswm-semantic-lifecycle-selected-execution/v1" as const
const fail = (detail: string) => lifecycleFailure("SELECTION_BINDING_FAILED", detail)
const sha = (raw: Uint8Array | string): string => createHash("sha256").update(raw).digest("hex")
const same = (left: unknown, right: unknown): boolean => {
  const a = canonicalJson(left), b = canonicalJson(right)
  return Either.isRight(a) && Either.isRight(b) && a.right === b.right
}
const runtimeAt = (root: string) => CanonicalAtomV2DurableRuntime.pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)))
const descriptor = Schema.Struct({ sha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)), mediaType: Schema.String, byteLength: Schema.Number })
const traceSchema = Schema.Struct({ traceSha256: Schema.String, traceContent: descriptor, prediction: Schema.String, predictionSha256: Schema.String, frameSha256: Schema.String, relationKey: Schema.Unknown, event: Schema.String })
const developmentSchema = Schema.Struct({ stage: Schema.Literal("development"), arm: Schema.Literal("frozen", "learned"), before: Schema.Unknown, after: Schema.Unknown, canonicalUnchanged: Schema.Literal(true), trace: Schema.NullOr(traceSchema), assessment: Schema.Unknown })
const trainingSchema = Schema.Struct({ stage: Schema.Literal("train"), arm: Schema.Literal("base"), trace: traceSchema, outcome: Schema.Struct({ outcomeContent: descriptor }) })
const revisionSchema = Schema.Struct({ stage: Schema.Literal("revise"), arm: Schema.Literal("learned"), committed: Schema.Boolean, before: Schema.Unknown, after: Schema.Unknown })
const decode = <A, I>(schema: Schema.Schema<A, I>, input: unknown) => Schema.decodeUnknown(schema)(input).pipe(Effect.mapError(() => fail("malformed lifecycle evidence")))

/** Recompute labels locally and verify the prediction bytes, event and graph actually read. */
const measuredDevelopment = (raw: unknown, arm: "frozen" | "learned", runtime: CanonicalAtomV2DurableRuntime["Type"]) => Effect.gen(function* () {
  const report = yield* decode(developmentSchema, raw)
  const actual = yield* inspectSemanticLifecycleState.pipe(Effect.provideService(CanonicalAtomV2DurableRuntime, runtime))
  if (report.arm !== arm || !same(report.before, actual) || !same(report.after, actual)) return yield* Effect.fail(fail("development graph differs from the recorded canonical state"))
  const trace = report.trace
  if (trace !== null) {
    const event = yield* actorEvent("development")
    const frame = yield* readLlmSemanticFrame(runtime, relationUid, event)
    const bytes = yield* runtime.readContent(trace.traceContent)
    const record = yield* Effect.try({ try: () => JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as Readonly<Record<string, unknown>>, catch: () => fail("invalid stored development trace") })
    if (record === null || typeof record !== "object" || record["contract"] !== "hswm-llm-semantic-trace/v1" || trace.event !== event ||
      trace.traceContent.mediaType !== HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE || bytes.byteLength !== trace.traceContent.byteLength ||
      sha(bytes) !== trace.traceSha256 || trace.traceSha256 !== trace.traceContent.sha256 || sha(trace.prediction) !== trace.predictionSha256 ||
      trace.frameSha256 !== frame.frameSha256 || !same(trace.relationKey, frame.relation.key) ||
      record["prediction"] !== trace.prediction || record["predictionSha256"] !== trace.predictionSha256 ||
      record["frameSha256"] !== frame.frameSha256 || record["event"] !== event || !same(record["relationKey"], frame.relation.key)) {
      return yield* Effect.fail(fail("development prediction is not bound to the stored trace and current read frame"))
    }
  }
  const assessment = yield* assessBatch("development", trace?.prediction ?? null)
  if (!same(report.assessment, assessment)) return yield* Effect.fail(fail("development assessment differs from the actual prediction and authored environment"))
  return Object.freeze({ actual, assessment })
})

export interface LifecycleSelectionEvidence {
  readonly training: unknown
  readonly baselineDevelopment: unknown
  readonly candidateDevelopment: unknown
  readonly candidateRevision: unknown
  readonly allowance: string
  readonly debit: string
}

/** No heldout record is accepted by this interface. Values are captured before I/O. */
export const prepareLifecycleSelection = (config: LifecycleConfig, input: LifecycleSelectionEvidence) => Effect.gen(function* () {
  const evidence = yield* Effect.try({ try: () => JSON.parse(JSON.stringify(input)) as LifecycleSelectionEvidence, catch: () => fail("selection evidence must be JSON") })
  if (!/^(?:0|[1-9][0-9]*)$/.test(evidence.allowance) || !/^(?:0|[1-9][0-9]*)$/.test(evidence.debit)) return yield* Effect.fail(fail("selection bounds must be exact naturals"))
  const root = config.root
  const baselineRoot = join(root, "states", "frozen"), candidateRoot = join(root, "states", "learned")
  const baselineRuntime = yield* runtimeAt(baselineRoot), candidateRuntime = yield* runtimeAt(candidateRoot)
  const baseline = { root: baselineRoot, relationUid, runtime: baselineRuntime }
  const candidate = { root: candidateRoot, relationUid, runtime: candidateRuntime }
  const baselineBinding = yield* deriveSemanticDurableBranch(baseline)
  const training = yield* decode(trainingSchema, evidence.training)
  const revision = yield* decode(revisionSchema, evidence.candidateRevision)
  const current = yield* measuredDevelopment(evidence.baselineDevelopment, "frozen", baselineRuntime)
  const proposed = yield* measuredDevelopment(evidence.candidateDevelopment, "learned", candidateRuntime)
  if (!same(revision.before, current.actual) || !same(revision.after, proposed.actual) || !same(training.trace.relationKey, current.actual.relationKey)) {
    return yield* Effect.fail(fail("revision and training lineage do not agree with evaluated graphs"))
  }
  const noOp = same(
    [current.actual.semantic.semanticText, current.actual.semantic.disposition, current.actual.semantic.uncertainty, current.actual.semantic.exceptionRefs],
    [proposed.actual.semantic.semanticText, proposed.actual.semantic.disposition, proposed.actual.semantic.uncertainty, proposed.actual.semantic.exceptionRefs]
  )
  const unavailable = !revision.committed ? "CANDIDATE_NOT_COMMITTED" : noOp ? "UNCHANGED_SEMANTIC_FIELDS" :
    current.assessment.parseFailures > 0 || proposed.assessment.parseFailures > 0 ? "INCOMPLETE_DEVELOPMENT_PREDICTIONS" : null
  const predictions = (assessment: typeof current.assessment) => Object.freeze(Object.fromEntries(assessment.observations.flatMap(row => row.prediction === null ? [] : [[row.caseId, row.prediction]])))
  const round: FrozenSemanticCandidateRound = Object.freeze({
    baseline, candidate,
    selectionSetId: `development:${config.environmentSha256}`,
    expectedTraining: { traceSha256: training.trace.traceSha256, outcomeSha256: training.outcome.outcomeContent.sha256 },
    assumptions: "CALLER_DECLARED_FINITE_CONTAMINATION_ALLOWANCE_AND_COST",
    selection: {
      observations: current.assessment.observations.map(row => ({ inputKey: row.caseId, label: row.observed, mass: 1n })),
      currentPredictions: predictions(current.assessment), candidatePredictions: predictions(proposed.assessment),
      allowance: BigInt(evidence.allowance), debit: BigInt(evidence.debit)
    }
  })
  const decision = unavailable === null ? yield* selectFrozenSemanticDurableCandidate(round) : null
  const selectedArm = decision?.selected === "CANDIDATE" ? "learned" as const : "frozen" as const
  const report = Object.freeze({
    contract: SEMANTIC_LIFECYCLE_SELECTED_EXECUTION_V1,
    selectedArm, reason: unavailable ?? decision!.guard.reason,
    selectionSplit: "development", heldoutUsed: false,
    denominator: current.assessment.denominator, baselineCorrect: current.assessment.correct, candidateCorrect: proposed.assessment.correct,
    allowance: evidence.allowance, debit: evidence.debit,
    baselineBinding, candidateBinding: yield* deriveSemanticDurableBranch(candidate),
    decision: decision === null ? null : JSON.parse(JSON.stringify(decision, (_key, value: unknown) => typeof value === "bigint" ? value.toString() : value)) as unknown,
    developmentEvidenceSha256: sha(JSON.stringify([evidence.baselineDevelopment, evidence.candidateDevelopment])),
    outcomeAuthority: "AUTHORED_ENVIRONMENT_NOT_INDEPENDENT_REAL_WORLD_TRUTH",
    claimCeiling: "MEASURED_FINITE_DEVELOPMENT_SELECTION_AND_NEXT_READ_NOT_GENERALIZATION_OR_CAUSAL_EFFICACY"
  })
  const executeNext = <A, E, R>(next: (runtime: CanonicalAtomV2DurableRuntime["Type"], uid: string) => Effect.Effect<A, E, R>) =>
    decision !== null ? reopenSelectedSemanticBranch<R | Effect.Effect.Context<ReturnType<typeof runtimeAt>>, E | Effect.Effect.Error<ReturnType<typeof runtimeAt>>, A>(round, decision, runtimeAt, next) : Effect.gen(function* () {
      const runtime = yield* runtimeAt(baselineRoot)
      const rebound = yield* deriveSemanticDurableBranch({ root: baselineRoot, relationUid, runtime })
      if (!same(rebound, baselineBinding)) return yield* Effect.fail(fail("fallback baseline changed before next execution"))
      return yield* next(runtime, relationUid)
    })
  return Object.freeze({ selectedArm, report, executeNext })
})
