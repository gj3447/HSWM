/** Contextual activation, outcome-bound updates and proposals through the existing owner writer. */
import { Effect, Either, Schema } from "effect"
import { parseJson } from "./adaptive-domain.js"
import { type AdaptiveHttpClientShape } from "./adaptive-executor.js"
import { type CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "./canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2ContentSchema, CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type CanonicalAtomV2Key, type CanonicalAtomV2Content } from "./canonical-atom-v2-schema.js"
import { contextError, contextHash, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { assembleSelectedSemanticContext, checkSemanticContextPlan, executeSelectedSemanticContext } from "./semantic-context-runtime.js"
import { ACTIVATION_MEDIA, NEURAL_ACTIVATION_MEDIA, ActivationFeaturesSchema, ActivationModeSchema, activationScopeHash, chooseActivation, decodeActivationPolicy, initializeActivation, updateActivation, type ActivationPolicy } from "./semantic-context-activation-domain.js"
import { renderVerifiedContextPrompt, ContextPresentationSchema, type ContextPresentation } from "./semantic-context-presentation-domain.js"
import { FiniteExecutionGuardSchema, prepareFiniteExecutionGuard, checkFiniteExecution } from "./semantic-context-finite-execution-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const encode = (x: unknown) => new TextEncoder().encode(contextJson(x))
const invalid = (detail: string) => contextError("ACTIVATION_BINDING_INVALID", detail)
const decode = <A, I>(schema: Schema.Schema<A, I>, raw: unknown) => Schema.decodeUnknownEither(schema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => invalid("Malformed activation request")))
const same = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => canonicalAtomV2KeyId(a) === canonicalAtomV2KeyId(b)
const lineage = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => a.schemaVersion === b.schemaVersion && a.lineageId === b.lineageId && a.atomUid === b.atomUid
export const ActivationDecisionSchema = Schema.Struct({ policyKey: CanonicalAtomV2KeySchema, features: ActivationFeaturesSchema, mode: ActivationModeSchema })
export const ActivationTargetSchema = Schema.Struct({ key: CanonicalAtomV2KeySchema, owner: Schema.NonEmptyString, authorizationRef: Schema.NonEmptyString, scope: Schema.NonEmptyString,
  decidedAt: Schema.String.pipe(Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)) })
const roots = (plan: ContextPlan) => plan.bindings.map(b => ({ referenceType: "hswm:context-policy:scope", role: "candidate-root", target: b.key }))
const readJson = (runtime: Runtime, content: CanonicalAtomV2Content, mediaType: string, maximumBytes: number) => Effect.gen(function* () {
  if (content.mediaType !== mediaType || content.byteLength > maximumBytes) return yield* Effect.fail(invalid("Wrong evidence media type or byte budget"))
  const bytes = yield* runtime.readContent(content)
  return yield* parseJson(new TextDecoder().decode(bytes)).pipe(Either.mapLeft(() => invalid("Stored content is not strict JSON")))
})
export const readActivationPolicy = (runtime: Runtime, plan: ContextPlan, policyKey: CanonicalAtomV2Key) => Effect.gen(function* () {
  yield* checkSemanticContextPlan(runtime, plan)
  const snapshot = yield* runtime.snapshot
  const versions = snapshot.canonical.atoms.filter(a => lineage(a.key, policyKey))
  const atom = versions.find(a => same(a.key, policyKey))
  if (!atom || atom.kind !== "semantic_context_policy" || atom.lifecycle !== "ADMITTED" || versions.some(a => a.key.revisionId > policyKey.revisionId)) return yield* Effect.fail(invalid("Expected exact current admitted activation policy revision"))
  if (![ACTIVATION_MEDIA, NEURAL_ACTIVATION_MEDIA].includes(atom.content.mediaType)) return yield* Effect.fail(invalid("Unsupported activation policy media"))
  const policy = yield* decodeActivationPolicy(yield* readJson(runtime, atom.content, atom.content.mediaType, 262144))
  if (atom.content.mediaType !== (policy.contract === "hswm-context-activation-policy/v2" ? NEURAL_ACTIVATION_MEDIA : ACTIVATION_MEDIA))
    return yield* Effect.fail(invalid("Activation contract and media version differ"))
  if (policy.scopeSha256 !== activationScopeHash(plan) || contextHash(atom.references.filter(r => r.referenceType !== "hswm:reference:supersedes")) !== contextHash(roots(plan))) return yield* Effect.fail(invalid("Rule/source revision, role or activation scope changed"))
  return { atom, policy }
})
export const selectContextActivation = (runtime: Runtime, plan: ContextPlan, raw: unknown) => Effect.gen(function* () {
  const decision = yield* decode(ActivationDecisionSchema, raw)
  const { atom, policy } = yield* readActivationPolicy(runtime, plan, decision.policyKey)
  const selection = yield* chooseActivation(plan, policy, decision.features, decision.mode)
  yield* checkSemanticContextPlan(runtime, plan)
  return { ...selection, policyKey: atom.key, policyContent: atom.content }
})
export const assembleContextActivation = (runtime: Runtime, plan: ContextPlan, raw: unknown) => selectContextActivation(runtime, plan, raw).pipe(
  Effect.flatMap(selection => assembleSelectedSemanticContext(runtime, plan, selection)))
export const executeContextActivation = (runtime: Runtime, plan: ContextPlan, raw: unknown, cell: unknown, http: AdaptiveHttpClientShape, presentation: ContextPresentation = "canonical_json", verification?: unknown) => selectContextActivation(runtime, plan, raw).pipe(
  Effect.flatMap(selection => executeSelectedSemanticContext(runtime, plan, selection, cell, http, presentation, verification)))

const prepareWrite = (runtime: Runtime, plan: ContextPlan, policy: ActivationPolicy, rawTarget: unknown, priorKey: CanonicalAtomV2Key | null, priorPlan: ContextPlan = plan) => Effect.gen(function* () {
  const target = yield* decode(ActivationTargetSchema, rawTarget)
  yield* checkSemanticContextPlan(runtime, plan)
  const snapshot = yield* runtime.snapshot
  const versions = snapshot.canonical.atoms.filter(a => lineage(a.key, target.key))
  const prior = priorKey === null ? null : (yield* readActivationPolicy(runtime, priorPlan, priorKey)).atom
  if (prior === null ? versions.length !== 0 || target.key.revisionId !== 0 :
    !lineage(prior.key, target.key) || target.key.revisionId !== prior.key.revisionId + 1 || target.owner !== prior.responsibilityOwner) return yield* Effect.fail(invalid("Initialize once or append one revision to the same owner's policy"))
  const first = plan.bindings[0]
  if (!first) return yield* Effect.fail(invalid("No source relation"))
  const content = yield* runtime.stageContent(policy.contract === "hswm-context-activation-policy/v2" ? NEURAL_ACTIVATION_MEDIA : ACTIVATION_MEDIA, encode(policy))
  const atom: CanonicalAtomV2 = { _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: target.key, kind: "semantic_context_policy", responsibilityOwner: target.owner, content, lifecycle: "ADMITTED",
    provenance: { mode: "DERIVATION", sourceRef: prior?.key ?? first.key, evidenceSha256: policy.feedbackSha256 ?? content.sha256 },
    references: [...(prior ? [{ referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: prior.key }] : []), ...roots(plan)] }
  const envelope = yield* describeCanonicalAtomV2Envelope(atom)
  const keys = [...(prior ? [prior.key] : []), ...plan.bindings.flatMap(b => [b.key, ...b.participants.map(p => p.key)])]
  yield* checkSemanticContextPlan(runtime, plan)
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: `context-activation:${contextHash([target, content.sha256, plan.planSha256])}`, expectedStateRevision: plan.stateRevision,
    schemaVersion: target.key.schemaVersion, actorClaim: "context-activation:owner-adapter", authorizationRef: target.authorizationRef,
    scope: target.scope, decidedAt: target.decidedAt, traceRef: null,
    readSet: [...new Map(keys.map(k => [canonicalAtomV2KeyId(k), k])).values()], writes: [atom], provenanceSha256: atom.provenance.evidenceSha256
  }, [{ key: atom.key, payload: content, envelope }])
  return { contract: "hswm-context-activation-proposal/v1" as const, candidate, policy, policyKey: target.key, canonicalWrite: false as const }
})
export const prepareActivationInitialization = (runtime: Runtime, plan: ContextPlan, config: unknown, target: unknown) => Effect.gen(function* () {
  return yield* prepareWrite(runtime, plan, yield* initializeActivation(plan, config), target, null)
})

/** Scope changes reset sufficient statistics. History remains in the predecessor; no unproved transfer. */
export const prepareActivationRebinding = (runtime: Runtime, before: ContextPlan, after: ContextPlan, priorKey: CanonicalAtomV2Key, target: unknown) => Effect.gen(function* () {
  const { policy } = yield* readActivationPolicy(runtime, before, priorKey)
  if (activationScopeHash(before) === activationScopeHash(after)) return yield* Effect.fail(invalid("Rebinding requires a changed source/candidate scope"))
  return yield* prepareWrite(runtime, after, yield* initializeActivation(after, policy.config), target, priorKey, before)
})

export const ActivationFeedbackSchema = Schema.Struct({ traceContent: CanonicalAtomV2ContentSchema,
  reward: Schema.Number.pipe(Schema.finite(), Schema.between(0, 1)), observed: Schema.NonEmptyString.pipe(Schema.maxLength(8192)),
  source: Schema.NonEmptyString.pipe(Schema.maxLength(2048)) })
/** A current executed decision is required; stale/duplicate feedback cannot update a successor. */
export const prepareActivationLearning = (runtime: Runtime, plan: ContextPlan, rawFeedback: unknown, target: unknown) => Effect.gen(function* () {
  const feedback = yield* decode(ActivationFeedbackSchema, rawFeedback)
  const traceRaw = yield* readJson(runtime, feedback.traceContent, "application/vnd.hswm.semantic-context-trace-v1+json", 65536)
  const trace = yield* Schema.decodeUnknownEither(Schema.Struct({ contract: Schema.Literal("hswm-semantic-context-trace/v1"), executionId: Schema.NonEmptyString,
    planSha256: Schema.String, selectionSha256: Schema.String, assemblySha256: Schema.String, requestContent: CanonicalAtomV2ContentSchema,
    responseContent: CanonicalAtomV2ContentSchema, prediction: Schema.String, uncertainty: Schema.String, observedStatus: Schema.Literal("PREDICTION_ONLY"), canonicalWrite: Schema.Literal(false) }))(traceRaw)
  const v3 = trace.requestContent.mediaType === "application/vnd.hswm.semantic-context-request-v3+json"
  const v2 = v3 || trace.requestContent.mediaType === "application/vnd.hswm.semantic-context-request-v2+json"
  const requestRaw = yield* readJson(runtime, trace.requestContent, v3 ? "application/vnd.hswm.semantic-context-request-v3+json" : v2 ? "application/vnd.hswm.semantic-context-request-v2+json" : "application/vnd.hswm.semantic-context-request-v1+json", 1048576)
  const request = yield* v3 ? decode(Schema.Struct({ executionId: Schema.NonEmptyString, assembly: Schema.Unknown,
    presentation: ContextPresentationSchema, prompt: Schema.String, promptBytes: Schema.Number, verification: FiniteExecutionGuardSchema }), requestRaw) : v2 ? decode(Schema.Struct({ executionId: Schema.NonEmptyString, assembly: Schema.Unknown,
    presentation: ContextPresentationSchema, prompt: Schema.String, promptBytes: Schema.Number }), requestRaw) :
    decode(Schema.Struct({ executionId: Schema.NonEmptyString, assembly: Schema.Unknown }), requestRaw)
  const assembly = yield* Schema.decodeUnknownEither(Schema.Struct({ selection: Schema.Unknown }))(request.assembly)
  const decision = yield* Schema.decodeUnknownEither(ActivationDecisionSchema)(assembly.selection)
  const prepared = yield* assembleContextActivation(runtime, plan, decision)
  const guarded = v3 ? yield* Schema.decodeUnknownEither(Schema.Struct({ verification: FiniteExecutionGuardSchema }))(requestRaw) : null
  if (v2) {
    const presented = yield* Schema.decodeUnknownEither(Schema.Struct({ presentation: ContextPresentationSchema, prompt: Schema.String, promptBytes: Schema.Number }))(requestRaw)
    if (!prepared.assembly || presented.prompt !== (yield* renderVerifiedContextPrompt(prepared.assembly, presented.presentation, guarded?.verification)) ||
      presented.promptBytes !== new TextEncoder().encode(presented.prompt).byteLength || presented.promptBytes > plan.spec.maximumContextBytes) return yield* Effect.fail(invalid("Stored presentation does not reproduce the complete bounded prompt"))
    const wire = yield* Schema.decodeUnknownEither(Schema.Struct({ transport: Schema.Struct({ request: CanonicalAtomV2ContentSchema, response: CanonicalAtomV2ContentSchema }) }))(traceRaw)
    const sent = yield* readJson(runtime, wire.transport.request, "application/vnd.hswm.context-wire-request-v1+json", 1048576)
    const received = yield* readJson(runtime, wire.transport.response, "application/vnd.hswm.context-wire-response-v1+json", 65536)
    const requestBody = yield* Schema.decodeUnknownEither(Schema.Struct({ messages: Schema.Array(Schema.Struct({ role: Schema.Literal("user"), content: Schema.String })).pipe(Schema.itemsCount(1)) }))(sent)
    const responseBody = yield* Schema.decodeUnknownEither(Schema.Struct({ choices: Schema.Array(Schema.Struct({ message: Schema.Struct({ content: Schema.String }) })).pipe(Schema.minItems(1)) }))(received)
    const actual = yield* parseJson(responseBody.choices[0]?.message.content ?? "")
    const actualPrediction = yield* decode(Schema.Struct({ prediction: Schema.String, uncertainty: Schema.String }), actual)
    if (requestBody.messages[0]?.content !== presented.prompt || actualPrediction.prediction !== trace.prediction || actualPrediction.uncertainty !== trace.uncertainty) return yield* Effect.fail(invalid("Wire request/response differs from the bound execution"))
  }
  if (!prepared.assembly || request.executionId !== trace.executionId || trace.planSha256 !== plan.planSha256 ||
    contextHash(assembly.selection) !== contextHash(prepared.selection) || trace.selectionSha256 !== contextHash(prepared.selection) ||
    contextHash(request.assembly) !== contextHash(prepared.assembly) || trace.assemblySha256 !== prepared.assembly.assemblySha256) return yield* Effect.fail(invalid("Feedback trace/request does not reproduce the current executed activation"))
  const responseRaw = yield* readJson(runtime, trace.responseContent, "application/vnd.hswm.semantic-context-response-v1+json", 65536)
  const response = yield* decode(Schema.Struct({ prediction: Schema.String, uncertainty: Schema.String }), responseRaw)
  if (response.prediction !== trace.prediction || response.uncertainty !== trace.uncertainty) return yield* Effect.fail(invalid("Trace prediction differs from stored response"))
  const verification = guarded ? checkFiniteExecution(yield* prepareFiniteExecutionGuard(prepared.assembly.payload, guarded.verification), response.prediction) : null
  if (verification) {
    const stored = yield* Schema.decodeUnknownEither(Schema.Struct({ verification: Schema.Unknown }))(traceRaw)
    if (contextHash(stored.verification) !== contextHash(verification)) return yield* Effect.fail(invalid("Stored finite verdict does not reproduce the source/event/prediction"))
    if (verification.status === "VIOLATED" && feedback.reward > 0) return yield* Effect.fail(contextError("FINITE_REWARD_INVALID", "A verified constraint violation cannot receive positive reward; retain the failure or submit explicit zero reward"))
  }
  const { policy } = yield* readActivationPolicy(runtime, plan, decision.policyKey)
  const outcome = { contract: "hswm-context-activation-feedback/v1", ...feedback, executionId: trace.executionId,
    policyKey: decision.policyKey, candidateId: prepared.selection.candidateId, selectionSha256: trace.selectionSha256,
    status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED", ...(verification ? { verification } : {}) }
  const outcomeContent = yield* runtime.stageContent("application/vnd.hswm.context-activation-feedback-v1+json", encode(outcome))
  const learned = yield* updateActivation(policy, prepared.selection.candidateId, decision.features, feedback.reward, outcomeContent.sha256)
  const proposal = yield* prepareWrite(runtime, plan, learned, target, decision.policyKey)
  return { ...proposal, outcomeContent }
})

/** Owner callbacks retain native schema, authorization, read-set and journal checks. */
export const admitActivationProposal = <A, E, R>(proposal: Effect.Effect.Success<ReturnType<typeof prepareActivationInitialization>>, admission: {
  readonly admit: (p: typeof proposal) => Effect.Effect<A, E, R>
}) => admission.admit(proposal)
