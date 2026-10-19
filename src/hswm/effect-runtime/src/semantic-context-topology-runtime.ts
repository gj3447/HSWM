/** Outcome-backed local incidence retirement and atomic policy reset through the existing owner writer. */
import { Effect, Either, Schema } from "effect"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { CanonicalAtomV2ContentSchema, CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "./canonical-atom-v2-content-bound.js"
import { readLlmSemanticFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { parseJson } from "./adaptive-domain.js"
import { ContextSpecSchema, contextHash, contextError, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { checkSemanticContextPlan, prepareSemanticContext } from "./semantic-context-runtime.js"
import { ActivationTargetSchema, prepareActivationRebinding, readActivationPolicy } from "./semantic-context-activation-runtime.js"
import { reviewContextRetirement } from "./semantic-context-topology-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
export const TOPOLOGY_MEDIA = "application/vnd.hswm.context-topology-v1+json"
const invalid = (detail: string) => contextError("TOPOLOGY_BINDING_INVALID", detail)
const decode = <A, I>(s: Schema.Schema<A, I>, raw: unknown) => Schema.decodeUnknownEither(s)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => invalid("Malformed topology request")))
const same = (a: unknown, b: unknown) => contextHash(a) === contextHash(b)
const sameLineage = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => a.atomUid === b.atomUid && a.schemaVersion === b.schemaVersion && a.lineageId === b.lineageId
const currentAtom = (runtime: Runtime, key: CanonicalAtomV2Key) => Effect.gen(function* () {
  const versions = (yield* runtime.snapshot).canonical.atoms.filter(a => sameLineage(a.key, key))
  const atom = versions.find(a => same(a.key, key))
  if (!atom || versions.some(a => a.key.revisionId > key.revisionId) || atom.kind !== "semantic_context_policy") return yield* Effect.fail(invalid("Expected exact current policy revision"))
  return atom
})
const framesFor = (runtime: Runtime, plan: ContextPlan) => Effect.gen(function* () {
  yield* checkSemanticContextPlan(runtime, plan)
  const frames = yield* Effect.forEach(plan.bindings, b => readLlmSemanticFrame(runtime, b.key.atomUid, plan.spec.event), { concurrency: 1 })
  yield* checkSemanticContextPlan(runtime, plan)
  if (frames.some(f => f.stateRevision !== plan.stateRevision)) return yield* Effect.fail(invalid("Mixed source revisions"))
  return frames
})
const BasisSchema = Schema.Struct({ policyKey: CanonicalAtomV2KeySchema, feedbackContent: CanonicalAtomV2ContentSchema,
  partition: Schema.Literal("TRAIN"), minimumObservations: Schema.Number.pipe(Schema.int(), Schema.between(1, 1000000)) })
const readBasis = (runtime: Runtime, plan: ContextPlan, raw: unknown) => Effect.gen(function* () {
  const basis = yield* decode(BasisSchema, raw)
  const { atom, policy } = yield* readActivationPolicy(runtime, plan, basis.policyKey)
  if (basis.feedbackContent.mediaType !== "application/vnd.hswm.context-activation-feedback-v1+json" || basis.feedbackContent.byteLength > 65536 ||
    policy.feedbackSha256 !== basis.feedbackContent.sha256 || policy.arms.reduce((n, a) => n + a.observations, 0) < basis.minimumObservations) return yield* Effect.fail(invalid("An admitted learned policy and its exact outcome are required"))
  const rawFeedback = yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(basis.feedbackContent)))
  const feedback = yield* Schema.decodeUnknownEither(Schema.Struct({ contract: Schema.Literal("hswm-context-activation-feedback/v1"),
    traceContent: CanonicalAtomV2ContentSchema, policyKey: CanonicalAtomV2KeySchema, candidateId: Schema.NonEmptyString,
    reward: Schema.Number.pipe(Schema.finite(), Schema.between(0, 1)), source: Schema.NonEmptyString }))(rawFeedback)
  if (!sameLineage(feedback.policyKey, basis.policyKey) || feedback.policyKey.revisionId + 1 !== basis.policyKey.revisionId || !policy.arms.some(a => a.candidateId === feedback.candidateId)) return yield* Effect.fail(invalid("Outcome predecessor does not identify this policy"))
  yield* runtime.readContent(feedback.traceContent)
  return { basis, atom, policy, feedback }
})

/** At most eight inspected single-incidence candidates. No per-edge causal reward is inferred. */
export const proposeContextRetirements = (runtime: Runtime, plan: ContextPlan, rawBasis: unknown, maximumCandidates: unknown) => Effect.gen(function* () {
  const limit = yield* decode(Schema.Number.pipe(Schema.int(), Schema.between(1, 8)), maximumCandidates)
  const basis = yield* readBasis(runtime, plan, rawBasis)
  const frames = yield* framesFor(runtime, plan)
  const options = plan.spec.candidates.flatMap(c => c.relationUids.filter(uid => c.relationUids.length > 1 && !plan.spec.mandatoryRelationUids.includes(uid)).map(uid => ({ candidateId: c.id, uid }))).slice(0, limit)
  const candidates = options.map(option => {
    if ((basis.policy.arms.find(a => a.candidateId === option.candidateId)?.observations ?? 0) < basis.basis.minimumObservations) return {
      ...option, status: "UNKNOWN" as const, reason: "Affected bundle has insufficient executed support", after: null, review: null }
    const after = { ...plan.spec, candidates: plan.spec.candidates.map(c => c.id !== option.candidateId ? c : { ...c, relationUids: c.relationUids.filter(uid => uid !== option.uid) }) }
    const review = reviewContextRetirement(plan.spec, after, frames)
    return Either.isLeft(review) ? { ...option, status: review.left.code === "TOPOLOGY_UNKNOWN" ? "UNKNOWN" as const : "REJECTED" as const, reason: review.left.detail, after: null, review: null } :
      { ...option, status: review.right.status === "PRESERVED" ? "CANDIDATE" as const : "REJECTED" as const, reason: review.right.claimCeiling, after, review: review.right }
  })
  return { contract: "hswm-context-retirement-candidates/v1" as const, planSha256: plan.planSha256, policyKey: basis.atom.key,
    outcome: basis.basis.feedbackContent, partition: "CALLER_DECLARED_TRAIN_NOT_AUTHENTICATED" as const, candidates,
    claimCeiling: "LEARNED_BUNDLE_EVIDENCE_PLUS_FINITE_PRESERVATION_NOT_CAUSAL_EDGE_CREDIT" as const }
})

const RecordSchema = Schema.Struct({ contract: Schema.Literal("hswm-context-topology/v1"), spec: ContextSpecSchema, previousSpec: ContextSpecSchema,
  activationKey: CanonicalAtomV2KeySchema, reviewContent: CanonicalAtomV2ContentSchema, sourceFramesSha256: Schema.String,
  operation: Schema.Literal("RETIRE", "RESTORE"), basis: Schema.NullOr(BasisSchema) })
const readTopologyRecord = (runtime: Runtime, key: CanonicalAtomV2Key) => Effect.gen(function* () {
  const atom = yield* currentAtom(runtime, key)
  if (atom.content.mediaType !== TOPOLOGY_MEDIA || atom.content.byteLength > 262144) return yield* Effect.fail(invalid("Expected bounded topology content"))
  const record = yield* decode(RecordSchema, yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(atom.content))))
  yield* runtime.readContent(record.reviewContent)
  return { atom, record }
})

/** Reopening reads the stored scope and the latest learned policy, never an in-memory candidate. */
export const readContextTopology = (runtime: Runtime, key: CanonicalAtomV2Key, event: string) => Effect.gen(function* () {
  const { atom, record } = yield* readTopologyRecord(runtime, key)
  const plan = yield* prepareSemanticContext(runtime, { ...record.spec, event })
  const refs = plan.bindings.map(b => ({ referenceType: "hswm:context-policy:scope", role: "candidate-root", target: b.key }))
  if (!same(refs, atom.references.filter(r => r.referenceType !== "hswm:reference:supersedes"))) return yield* Effect.fail(invalid("Topology source bindings drifted"))
  const versions = (yield* runtime.snapshot).canonical.atoms.filter(a => sameLineage(a.key, record.activationKey))
  const latest = versions.reduce<CanonicalAtomV2 | undefined>((best, a) => !best || a.key.revisionId > best.key.revisionId ? a : best, undefined)
  if (!latest || latest.key.revisionId < record.activationKey.revisionId) return yield* Effect.fail(invalid("Reset policy missing"))
  yield* readActivationPolicy(runtime, plan, latest.key)
  return { plan, policyKey: latest.key, topologyKey: atom.key }
})

export const TopologyChangeSchema = Schema.Struct({ operation: Schema.Literal("RETIRE", "RESTORE"), afterSpec: ContextSpecSchema,
  policyKey: CanonicalAtomV2KeySchema, basis: Schema.NullOr(BasisSchema), priorTopologyKey: Schema.NullOr(CanonicalAtomV2KeySchema),
  topologyTarget: ActivationTargetSchema, activationTarget: ActivationTargetSchema })
export const prepareContextTopologyChange = (runtime: Runtime, before: ContextPlan, raw: unknown) => Effect.gen(function* () {
  const input = yield* decode(TopologyChangeSchema, raw)
  const prior = input.priorTopologyKey === null ? null : yield* readTopologyRecord(runtime, input.priorTopologyKey)
  const t = input.topologyTarget, w = input.activationTarget
  if (t.owner !== w.owner || t.scope !== w.scope || t.authorizationRef !== w.authorizationRef || t.decidedAt !== w.decidedAt || sameLineage(t.key, w.key)) return yield* Effect.fail(invalid("One owner transaction must use distinct topology and activation lineages"))
  if (prior ? !sameLineage(prior.atom.key, t.key) || prior.atom.key.revisionId + 1 !== t.key.revisionId || prior.atom.responsibilityOwner !== t.owner ||
    !same({ ...prior.record.spec, event: before.spec.event }, before.spec) : t.key.revisionId !== 0 || (yield* runtime.snapshot).canonical.atoms.some(a => sameLineage(a.key, t.key))) return yield* Effect.fail(invalid("Topology must initialize once or append to the current owner's scope"))
  if (prior) {
    const current = yield* readContextTopology(runtime, prior.atom.key, before.spec.event)
    if (!same(current.policyKey, input.policyKey)) return yield* Effect.fail(invalid("Current topology and activation policy differ"))
  }
  const after = yield* prepareSemanticContext(runtime, input.afterSpec)
  let review
  if (input.operation === "RESTORE") {
    if (!prior || input.basis !== null || !same({ ...prior.record.previousSpec, event: before.spec.event }, after.spec)) return yield* Effect.fail(invalid("Restore must use the exact predecessor scope; no arbitrary expansion"))
    review = yield* reviewContextRetirement(after.spec, before.spec, yield* framesFor(runtime, after))
  } else {
    const basis = yield* readBasis(runtime, before, input.basis)
    if (!same(basis.atom.key, input.policyKey)) return yield* Effect.fail(invalid("Outcome belongs to a different activation policy"))
    if (after.spec.candidates.some(c => !same(c.relationUids, before.spec.candidates.find(b => b.id === c.id)?.relationUids) &&
      (basis.policy.arms.find(a => a.candidateId === c.id)?.observations ?? 0) < basis.basis.minimumObservations)) return yield* Effect.fail(invalid("Each changed bundle needs declared executed support"))
    review = yield* reviewContextRetirement(before.spec, after.spec, yield* framesFor(runtime, before))
  }
  if (review.status !== "PRESERVED") return yield* Effect.fail(invalid("Whole changed scope must preserve declared finite meaning"))
  if (before.bindings.some(b => b.owner !== t.owner)) return yield* Effect.fail(invalid("First implementation is limited to a single declared source owner"))
  const reset = yield* prepareActivationRebinding(runtime, before, after, input.policyKey, w)
  const reviewContent = yield* runtime.stageContent("application/vnd.hswm.context-retirement-review-v1+json", new TextEncoder().encode(contextJson(review)))
  const record = { contract: "hswm-context-topology/v1" as const, spec: after.spec, previousSpec: before.spec, activationKey: reset.policyKey,
    reviewContent, sourceFramesSha256: review.sourceFramesSha256, operation: input.operation, basis: input.basis }
  const content = yield* runtime.stageContent(TOPOLOGY_MEDIA, new TextEncoder().encode(contextJson(record)))
  const atom: CanonicalAtomV2 = { _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: t.key,
    kind: "semantic_context_policy", responsibilityOwner: t.owner, content, lifecycle: "ADMITTED",
    provenance: { mode: "DERIVATION", sourceRef: prior?.atom.key ?? input.policyKey, evidenceSha256: reviewContent.sha256 },
    references: [...(prior ? [{ referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: prior.atom.key }] : []),
      ...after.bindings.map(b => ({ referenceType: "hswm:context-policy:scope", role: "candidate-root", target: b.key }))] }
  const envelope = yield* describeCanonicalAtomV2Envelope(atom)
  const keys = [...reset.candidate.command.readSet, ...before.bindings.flatMap(b => [b.key, ...b.participants.map(p => p.key)]), ...(prior ? [prior.atom.key] : [])]
  yield* checkSemanticContextPlan(runtime, before)
  yield* checkSemanticContextPlan(runtime, after)
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, { ...reset.candidate.command,
    transitionId: `context-topology:${contextHash([t, content, reset.policyKey])}`,
    readSet: [...new Map(keys.map(k => [canonicalAtomV2KeyId(k), k])).values()], writes: [...reset.candidate.command.writes, atom] },
    [...reset.candidate.writeBindings, { key: atom.key, payload: atom.content, envelope }])
  return { contract: "hswm-context-topology-proposal/v1" as const, candidate, topologyKey: atom.key, policyKey: reset.policyKey, review,
    statistics: "RESET_NOT_TRANSFERRED" as const, canonicalWrite: false as const }
})
