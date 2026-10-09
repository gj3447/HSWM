/** Effect shell: choose against a pinned graph, read exact roles, execute once, retain evidence. */
import { randomUUID } from "node:crypto"
import { Effect, Either, Schema } from "effect"
import { AdaptiveHttpClient, executeAdaptiveCell, type AdaptiveHttpClientShape } from "./adaptive-executor.js"
import { parseJson } from "./adaptive-domain.js"
import { type CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { readLlmSemanticFrame, type SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { decodeLifecycleCell } from "./semantic-lifecycle-domain.js"
import { buildContextPlan, selectContext, contextError, contextHash, contextByteLength, contextJson, type ContextPlan } from "./semantic-context-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const encode = (value: unknown) => new TextEncoder().encode(contextJson(value))
export const prepareSemanticContext = (runtime: Runtime, specification: unknown) => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  return yield* buildContextPlan(specification, snapshot.canonical)
})

/** A new snapshot must reproduce the complete plan, including caller policy and candidate descriptors. */
const checkPlan = (runtime: Runtime, plan: ContextPlan) => Effect.gen(function* () {
  const current = yield* prepareSemanticContext(runtime, plan.spec)
  if (current.planSha256 !== plan.planSha256) return yield* Effect.fail(contextError("PLAN_STALE", "Graph state or candidate binding changed; prepare and decide again"))
})

export const assembleSemanticContext = (runtime: Runtime, plan: ContextPlan, rawDecision: unknown) => Effect.gen(function* () {
  yield* checkPlan(runtime, plan)
  const selection = yield* selectContext(plan, rawDecision)
  if (selection.status !== "SELECTED") return { selection, assembly: null }
  const candidate = plan.spec.candidates.find(c => c.id === selection.candidateId)
  if (candidate === undefined) return yield* Effect.fail(contextError("CANDIDATE_MISSING", "Selected candidate was not in the bound plan"))
  const roots = [...new Set([...plan.spec.mandatoryRelationUids, ...candidate.relationUids])]
  const frames: ReadonlyArray<SemanticReadFrame> = yield* Effect.forEach(roots, uid => readLlmSemanticFrame(runtime, uid, plan.spec.event), { concurrency: 1 })
  yield* checkPlan(runtime, plan)
  if (frames.some(f => f.stateRevision !== plan.stateRevision)) return yield* Effect.fail(contextError("PLAN_STALE", "A frame was read from a different snapshot"))
  const payload = {
    contract: "hswm-semantic-context-predict/v1" as const,
    event: plan.spec.event,
    selectionSha256: contextHash(selection),
    frames,
    requiredOutput: { prediction: "string", uncertainty: "string" }
  }
  const contextBytes = contextByteLength(payload)
  if (contextBytes > plan.spec.maximumContextBytes) return yield* Effect.fail(contextError("CONTEXT_BUDGET_EXCEEDED", "Complete selected roles and mandatory rules exceed the byte budget; no truncation or partial execution"))
  const bound = { contract: "hswm-semantic-context-assembly/v1" as const, planSha256: plan.planSha256, selection, payload, contextBytes }
  return { selection, assembly: { ...bound, assemblySha256: contextHash(bound) } }
})
export type ContextAssembly = NonNullable<Effect.Effect.Success<ReturnType<typeof assembleSemanticContext>>["assembly"]>

const PredictionSchema = Schema.Struct({
  prediction: Schema.String.pipe(Schema.minLength(1), Schema.maxLength(8192)),
  uncertainty: Schema.String.pipe(Schema.minLength(1), Schema.maxLength(8192))
})
/** This call stages immutable evidence only. It has no canonical submit or W-update path. */
export const executeSemanticContext = (runtime: Runtime, plan: ContextPlan, rawDecision: unknown, rawCell: unknown, http: AdaptiveHttpClientShape) => Effect.gen(function* () {
  const cell = yield* decodeLifecycleCell(rawCell)
  const prepared = yield* assembleSemanticContext(runtime, plan, rawDecision)
  if (prepared.assembly === null) return { ...prepared, trace: null }
  const assembly = prepared.assembly
  const executionId = yield* Effect.sync(randomUUID)
  const requestContent = yield* runtime.stageContent("application/vnd.hswm.semantic-context-request-v1+json", encode({ executionId, assembly }))
  yield* checkPlan(runtime, plan)
  const response = yield* executeAdaptiveCell({ kind: "llm", cell_id: "semantic-context", ...cell }, { prompt: contextJson(assembly.payload) }, process.cwd(), 120_000).pipe(Effect.provideService(AdaptiveHttpClient, http))
  if (response.status !== "SUCCEEDED") return yield* Effect.fail(contextError("CONTEXT_EXECUTION_FAILED", "LLM transport did not complete; no retry or outcome fabricated"))
  yield* checkPlan(runtime, plan)
  const decoded = yield* parseJson(response.output).pipe(Either.mapLeft(() => contextError("PREDICTION_INVALID", "Expected strict prediction JSON")))
  const prediction = yield* Schema.decodeUnknownEither(PredictionSchema)(decoded, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => contextError("PREDICTION_INVALID", "Expected prediction and uncertainty only")))
  const responseContent = yield* runtime.stageContent("application/vnd.hswm.semantic-context-response-v1+json", new TextEncoder().encode(response.output))
  const trace = {
    contract: "hswm-semantic-context-trace/v1" as const, executionId,
    planSha256: plan.planSha256, selectionSha256: contextHash(prepared.selection), assemblySha256: assembly.assemblySha256,
    requestContent, responseContent, prediction: prediction.prediction, uncertainty: prediction.uncertainty,
    backendConfigurationSha256: contextHash(cell), observedStatus: "PREDICTION_ONLY" as const,
    modelUsage: "UNREPORTED_BY_THIS_ADAPTER" as const, canonicalWrite: false as const
  }
  const traceContent = yield* runtime.stageContent("application/vnd.hswm.semantic-context-trace-v1+json", encode(trace))
  return { ...prepared, trace: { ...trace, traceContent } }
})

const Descriptor = Schema.Struct({
  mediaType: Schema.Literal("application/vnd.hswm.semantic-context-trace-v1+json"),
  byteLength: Schema.Number.pipe(Schema.int(), Schema.between(1, 1048576)),
  sha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))
})
const OutcomeInput = Schema.Struct({
  traceContent: Descriptor,
  observed: Schema.String.pipe(Schema.minLength(1), Schema.maxLength(8192)),
  source: Schema.String.pipe(Schema.minLength(1), Schema.maxLength(2048))
})
/** Observation attribution is explicit; a caller's label is not independent validation or causal credit. */
export const stageSemanticContextOutcome = (runtime: Runtime, raw: unknown) => Effect.gen(function* () {
  const input = yield* Schema.decodeUnknownEither(OutcomeInput)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => contextError("OUTCOME_INVALID", "Outcome requires a stored trace descriptor and an identified source")))
  const bytes = yield* runtime.readContent(input.traceContent)
  const trace = yield* parseJson(new TextDecoder().decode(bytes)).pipe(Either.mapLeft(() => contextError("TRACE_INVALID", "Stored trace is not strict JSON")))
  // readContent verifies the descriptor; decode the attribution fields before linking them.
  const TraceLink = Schema.Struct({
    contract: Schema.Literal("hswm-semantic-context-trace/v1"), executionId: Schema.String,
    planSha256: Schema.String, selectionSha256: Schema.String, assemblySha256: Schema.String,
    prediction: Schema.String, observedStatus: Schema.Literal("PREDICTION_ONLY"), canonicalWrite: Schema.Literal(false)
  })
  const linked = yield* Schema.decodeUnknownEither(TraceLink)(trace).pipe(Either.mapLeft(() => contextError("TRACE_INVALID", "Wrong evidence type for context outcome")))
  const outcome = { contract: "hswm-semantic-context-outcome/v1" as const, ...input, executionId: linked.executionId,
    planSha256: linked.planSha256, selectionSha256: linked.selectionSha256, assemblySha256: linked.assemblySha256,
    status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED" as const, weightUpdate: null, canonicalWrite: false as const }
  const outcomeContent = yield* runtime.stageContent("application/vnd.hswm.semantic-context-outcome-v1+json", encode(outcome))
  return { ...outcome, outcomeContent }
})
