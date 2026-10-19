/** Effect shell: choose against a pinned graph, read exact roles, execute once, retain evidence. */
import { randomUUID } from "node:crypto"
import { Effect, Either, Ref, Schema } from "effect"
import { AdaptiveHttpClient, AdaptiveExecutorError, executeAdaptiveCell, type AdaptiveHttpClientShape } from "./adaptive-executor.js"
import type { CanonicalAtomV2Content } from "./canonical-atom-v2-schema.js"
import { parseJson } from "./adaptive-domain.js"
import { type CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { readLlmSemanticFrame, type SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { decodeLifecycleCell } from "./semantic-lifecycle-domain.js"
import { buildContextPlan, selectContext, contextError, contextHash, contextByteLength, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { renderContextPrompt, type ContextPresentation } from "./semantic-context-presentation-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const encode = (value: unknown) => new TextEncoder().encode(contextJson(value))
export const prepareSemanticContext = (runtime: Runtime, specification: unknown) => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  return yield* buildContextPlan(specification, snapshot.canonical)
})

/** A new snapshot must reproduce the complete plan, including caller policy and candidate descriptors. */
export const checkSemanticContextPlan = (runtime: Runtime, plan: ContextPlan) => Effect.gen(function* () {
  const current = yield* prepareSemanticContext(runtime, plan.spec)
  if (current.planSha256 !== plan.planSha256) return yield* Effect.fail(contextError("PLAN_STALE", "Graph state or candidate binding changed; prepare and decide again"))
})

type BoundSelection = { readonly planSha256: string; readonly status: string; readonly candidateId: string | null }
/** Explicit typed selection boundary shared by Jev and owner-admitted policy readers. It confers no write authority. */
export const assembleSelectedSemanticContext = <S extends BoundSelection>(runtime: Runtime, plan: ContextPlan, selection: S) => Effect.gen(function* () {
  yield* checkSemanticContextPlan(runtime, plan)
  if (!["SELECTED", "NONE", "NEED_MORE"].includes(selection.status)) return yield* Effect.fail(contextError("SELECTION_INVALID", "Unknown context selection status"))
  if (selection.planSha256 !== plan.planSha256) return yield* Effect.fail(contextError("REQUEST_MISMATCH", "Selection belongs to a different plan"))
  if (selection.status !== "SELECTED") return { selection, assembly: null }
  const candidate = plan.spec.candidates.find(c => c.id === selection.candidateId)
  if (candidate === undefined) return yield* Effect.fail(contextError("CANDIDATE_MISSING", "Selected candidate was not in the bound plan"))
  const roots = [...new Set([...plan.spec.mandatoryRelationUids, ...candidate.relationUids])]
  const frames: ReadonlyArray<SemanticReadFrame> = yield* Effect.forEach(roots, uid => readLlmSemanticFrame(runtime, uid, plan.spec.event), { concurrency: 1 })
  yield* checkSemanticContextPlan(runtime, plan)
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
export const assembleSemanticContext = (runtime: Runtime, plan: ContextPlan, rawDecision: unknown) =>
  selectContext(plan, rawDecision).pipe(Effect.flatMap(selection => assembleSelectedSemanticContext(runtime, plan, selection)))
export type ContextAssembly = NonNullable<Effect.Effect.Success<ReturnType<typeof assembleSemanticContext>>["assembly"]>

const PredictionSchema = Schema.Struct({
  prediction: Schema.String.pipe(Schema.minLength(1), Schema.maxLength(8192)),
  uncertainty: Schema.String.pipe(Schema.minLength(1), Schema.maxLength(8192))
})
/** This call stages immutable evidence only. It has no canonical submit or W-update path. */
export const executeSelectedSemanticContext = <S extends BoundSelection>(runtime: Runtime, plan: ContextPlan, selection: S, rawCell: unknown, http: AdaptiveHttpClientShape, presentation: ContextPresentation = "canonical_json") => Effect.gen(function* () {
  const cell = yield* decodeLifecycleCell(rawCell)
  const prepared = yield* assembleSelectedSemanticContext(runtime, plan, selection)
  if (prepared.assembly === null) return { ...prepared, trace: null }
  const assembly = prepared.assembly
  const prompt = yield* renderContextPrompt(assembly, presentation)
  const promptBytes = new TextEncoder().encode(prompt).byteLength
  if (promptBytes > plan.spec.maximumContextBytes) return yield* Effect.fail(contextError("CONTEXT_BUDGET_EXCEEDED", "Complete presented prompt exceeds the budget; no truncation"))
  const executionId = yield* Effect.sync(randomUUID)
  // Existing v1 evidence is unchanged; new presentation bytes have an explicit v2 contract.
  const requestContent = yield* runtime.stageContent(presentation === "canonical_json" ? "application/vnd.hswm.semantic-context-request-v1+json" : "application/vnd.hswm.semantic-context-request-v2+json",
    encode(presentation === "canonical_json" ? { executionId, assembly } : { executionId, assembly, presentation, prompt, promptBytes }))
  const observedWire = yield* Ref.make<{ readonly request: CanonicalAtomV2Content; readonly response: CanonicalAtomV2Content } | null>(null)
  const observedHttp: AdaptiveHttpClientShape = presentation === "canonical_json" ? http : { postJson: request => Effect.gen(function* () {
    // Observe exact bodies at the injected transport boundary; never persist headers or credentials.
    const sent = yield* runtime.stageContent("application/vnd.hswm.context-wire-request-v1+json", request.body)
    const received = yield* http.postJson(request)
    const response = yield* runtime.stageContent("application/vnd.hswm.context-wire-response-v1+json", received)
    yield* Ref.set(observedWire, { request: sent, response })
    return received
  }).pipe(Effect.mapError(() => new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: "Transport or exact wire evidence failed; no automatic retry" }))) }
  yield* checkSemanticContextPlan(runtime, plan)
  const response = yield* executeAdaptiveCell({ kind: "llm", cell_id: "semantic-context", ...cell }, { prompt }, process.cwd(), 120_000).pipe(Effect.provideService(AdaptiveHttpClient, observedHttp))
  if (response.status !== "SUCCEEDED") return yield* Effect.fail(contextError("CONTEXT_EXECUTION_FAILED", "LLM transport did not complete; no retry or outcome fabricated"))
  yield* checkSemanticContextPlan(runtime, plan)
  const decoded = yield* parseJson(response.output).pipe(Either.mapLeft(() => contextError("PREDICTION_INVALID", "Expected strict prediction JSON")))
  const prediction = yield* Schema.decodeUnknownEither(PredictionSchema)(decoded, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => contextError("PREDICTION_INVALID", "Expected prediction and uncertainty only")))
  const responseContent = yield* runtime.stageContent("application/vnd.hswm.semantic-context-response-v1+json", new TextEncoder().encode(response.output))
  const trace = {
    contract: "hswm-semantic-context-trace/v1" as const, executionId,
    planSha256: plan.planSha256, selectionSha256: contextHash(prepared.selection), assemblySha256: assembly.assemblySha256,
    requestContent, responseContent, prediction: prediction.prediction, uncertainty: prediction.uncertainty,
    backendConfigurationSha256: contextHash(cell), observedStatus: "PREDICTION_ONLY" as const,
    ...(presentation !== "canonical_json" ? { transport: yield* Ref.get(observedWire) } : {}),
    modelUsage: "UNREPORTED_BY_THIS_ADAPTER" as const, canonicalWrite: false as const
  }
  const traceContent = yield* runtime.stageContent("application/vnd.hswm.semantic-context-trace-v1+json", encode(trace))
  return { ...prepared, trace: { ...trace, traceContent } }
})
export const executeSemanticContext = (runtime: Runtime, plan: ContextPlan, rawDecision: unknown, rawCell: unknown, http: AdaptiveHttpClientShape) =>
  selectContext(plan, rawDecision).pipe(Effect.flatMap(selection => executeSelectedSemanticContext(runtime, plan, selection, rawCell, http)))

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
