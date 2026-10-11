/** Owner-scoped policy revisions; canonical admission remains at the existing writer boundary. */
import { Effect, Either, Schema } from "effect"
import { type AdaptiveHttpClientShape } from "./adaptive-executor.js"
import { parseJson } from "./adaptive-domain.js"
import { type CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "./canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { contextError, contextHash, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { assembleSelectedSemanticContext, checkSemanticContextPlan, executeSelectedSemanticContext } from "./semantic-context-runtime.js"
import { bindContextLearning, contextScopeHash, decodeContextPolicy, validateContextPolicyEvidence, ContextPolicyDecisionSchema, CONTEXT_POLICY_MEDIA, CONTEXT_POLICY_EVIDENCE_MEDIA, CONTEXT_POLICY_KIND, type ContextPolicy } from "./semantic-context-policy-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const encode = (x: unknown) => new TextEncoder().encode(contextJson(x))
const sameKey = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => canonicalAtomV2KeyId(a) === canonicalAtomV2KeyId(b)
const sameLineage = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => a.schemaVersion === b.schemaVersion && a.lineageId === b.lineageId && a.atomUid === b.atomUid
const TargetSchema = Schema.Struct({
  key: CanonicalAtomV2KeySchema, owner: Schema.NonEmptyString,
  authorizationRef: Schema.NonEmptyString, scope: Schema.NonEmptyString,
  decidedAt: Schema.String.pipe(Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/))
})
const readPolicyPayload = (runtime: Runtime, atom: CanonicalAtomV2, plan: ContextPlan) => Effect.gen(function* () {
  if (atom.kind !== CONTEXT_POLICY_KIND || atom.content.mediaType !== CONTEXT_POLICY_MEDIA) return yield* Effect.fail(contextError("POLICY_INVALID", "Policy requires its schema-admitted kind and media type"))
  const bytes = yield* runtime.readContent(atom.content)
  if (bytes.byteLength > 65536) return yield* Effect.fail(contextError("POLICY_INVALID", "Policy payload exceeds 64 KiB"))
  const raw = yield* parseJson(new TextDecoder().decode(bytes)).pipe(Either.mapLeft(() => contextError("POLICY_INVALID", "Policy is not strict JSON")))
  const policy = yield* decodeContextPolicy(raw)
  const binding = yield* bindContextLearning(plan, policy.baselineCandidateId)
  const expectedReferences = plan.bindings.map(b => ({ referenceType: "hswm:context-policy:scope", role: "candidate-root", target: b.key }))
  const scopeReferences = atom.references.filter(r => r.referenceType !== "hswm:reference:supersedes")
  if (policy.scopeSha256 !== contextScopeHash(plan) || policy.bindingSha256 !== binding.bindingSha256 ||
    !plan.spec.candidates.some(c => c.id === policy.selectedCandidateId) || contextHash(scopeReferences) !== contextHash(expectedReferences)) {
    return yield* Effect.fail(contextError("POLICY_SCOPE_STALE", "Task, source revision, role, candidate or preservation contract changed"))
  }
  if (policy.mode === "BASELINE") {
    if (policy.evidence !== null || policy.selectedCandidateId !== policy.baselineCandidateId) return yield* Effect.fail(contextError("POLICY_INVALID", "Baseline must not impersonate a learned selection"))
  } else {
    if (policy.evidence === null || policy.evidence.mediaType !== CONTEXT_POLICY_EVIDENCE_MEDIA || policy.evidence.byteLength > 2097152) return yield* Effect.fail(contextError("POLICY_INVALID", "Learned policy needs bounded external evidence"))
    const source = yield* runtime.readContent(policy.evidence)
    const evidence = yield* parseJson(new TextDecoder().decode(source)).pipe(Either.mapLeft(() => contextError("POLICY_EVIDENCE_INVALID", "External evidence is not JSON")))
    const validated = yield* validateContextPolicyEvidence(binding, evidence)
    if (validated.evidence.selectedCandidateId !== policy.selectedCandidateId) return yield* Effect.fail(contextError("POLICY_BINDING_MISMATCH", "Policy differs from its stored assessment"))
  }
  return policy
})

export const selectContextPolicy = (runtime: Runtime, plan: ContextPlan, raw: unknown) => Effect.gen(function* () {
  const decision = yield* Schema.decodeUnknownEither(ContextPolicyDecisionSchema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => contextError("POLICY_DECISION_INVALID", "Select an exact policy key; this is not a Jev receipt")))
  yield* checkSemanticContextPlan(runtime, plan)
  const snapshot = yield* runtime.snapshot
  const versions = snapshot.canonical.atoms.filter(a => sameLineage(a.key, decision.policyKey))
  const atom = versions.find(a => sameKey(a.key, decision.policyKey))
  if (!atom || versions.some(a => a.key.revisionId > decision.policyKey.revisionId)) return yield* Effect.fail(contextError("POLICY_REVISION_STALE", "Expected the currently admitted policy revision; no silent latest-version substitution"))
  const policy = yield* readPolicyPayload(runtime, atom, plan)
  yield* checkSemanticContextPlan(runtime, plan)
  return {
    contract: "hswm-context-policy-selection/v1" as const, planSha256: plan.planSha256,
    status: "SELECTED" as const, candidateId: policy.selectedCandidateId, policyKey: atom.key, policyContent: atom.content,
    mode: policy.mode, policyEvidence: policy.evidence,
    selectionProbability: 1 as const, distribution: plan.spec.candidates.map(c => ({ candidateId: c.id, probability: c.id === policy.selectedCandidateId ? 1 : 0 })),
    confidence: null, reason: "EXACT_OWNER_ADMITTED_POLICY" as const,
    authority: policy.authority, observedOperationalEfficacy: null
  }
})
export const assembleContextPolicy = (runtime: Runtime, plan: ContextPlan, raw: unknown) => selectContextPolicy(runtime, plan, raw).pipe(
  Effect.flatMap(selection => assembleSelectedSemanticContext(runtime, plan, selection)))
export const executeContextPolicy = (runtime: Runtime, plan: ContextPlan, raw: unknown, cell: unknown, http: AdaptiveHttpClientShape) => selectContextPolicy(runtime, plan, raw).pipe(
  Effect.flatMap(selection => executeSelectedSemanticContext(runtime, plan, selection, cell, http)))

const prepareWrite = (runtime: Runtime, plan: ContextPlan, policy: ContextPolicy, rawTarget: unknown, mode: "initialize" | "learn" | "restore") => Effect.gen(function* () {
  const target = yield* Schema.decodeUnknownEither(TargetSchema)(rawTarget, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => contextError("POLICY_TARGET_INVALID", "Expected explicit next key, owner and existing admission context")))
  yield* checkSemanticContextPlan(runtime, plan)
  const snapshot = yield* runtime.snapshot
  const versions = snapshot.canonical.atoms.filter(a => sameLineage(a.key, target.key))
  const prior = versions.reduce<CanonicalAtomV2 | undefined>((best, a) => !best || a.key.revisionId > best.key.revisionId ? a : best, undefined)
  if ((mode === "initialize" && (prior !== undefined || target.key.revisionId !== 0)) ||
    (mode !== "initialize" && (!prior || target.key.revisionId !== prior.key.revisionId + 1 || prior.responsibilityOwner !== target.owner))) return yield* Effect.fail(contextError("POLICY_TARGET_STALE", "Initialize once or append exactly one revision under the same owner"))
  if (prior) {
    const before = yield* readPolicyPayload(runtime, prior, plan)
    if (mode === "learn" && before.selectedCandidateId !== policy.baselineCandidateId) return yield* Effect.fail(contextError("POLICY_BASELINE_STALE", "Learning baseline must be the currently admitted behavior"))
  }
  const first = plan.bindings[0]
  if (!first) return yield* Effect.fail(contextError("POLICY_SCOPE_STALE", "No admitted source for policy derivation"))
  const content = yield* runtime.stageContent(CONTEXT_POLICY_MEDIA, encode(policy))
  const roots = plan.bindings.map(b => ({ referenceType: "hswm:context-policy:scope", role: "candidate-root", target: b.key }))
  const atom: CanonicalAtomV2 = {
    _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: target.key,
    kind: CONTEXT_POLICY_KIND, responsibilityOwner: target.owner, content, lifecycle: "ADMITTED",
    provenance: { mode: "DERIVATION", evidenceSha256: policy.evidence?.sha256 ?? content.sha256, sourceRef: prior?.key ?? first.key },
    references: [...(prior ? [{ referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: prior.key }] : []), ...roots]
  }
  const keys = [...(prior ? [prior.key] : []), ...(policy.restoredFrom ? [policy.restoredFrom] : []), ...plan.bindings.flatMap(b => [b.key, ...b.participants.map(p => p.key)])]
  const envelope = yield* describeCanonicalAtomV2Envelope(atom)
  yield* checkSemanticContextPlan(runtime, plan)
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: `context-policy:${contextHash([target, content.sha256, plan.planSha256])}`, expectedStateRevision: plan.stateRevision,
    schemaVersion: target.key.schemaVersion, actorClaim: "context-policy:owner-adapter", authorizationRef: target.authorizationRef, scope: target.scope,
    decidedAt: target.decidedAt, traceRef: null, readSet: [...new Map(keys.map(k => [canonicalAtomV2KeyId(k), k])).values()], writes: [atom], provenanceSha256: atom.provenance.evidenceSha256
  }, [{ key: atom.key, payload: content, envelope }])
  return { contract: "hswm-context-policy-proposal/v1" as const, candidate, policy, policyKey: target.key, canonicalWrite: false as const }
})

export const prepareBaselineContextPolicy = (runtime: Runtime, plan: ContextPlan, baselineCandidateId: string, target: unknown) => Effect.gen(function* () {
  const binding = yield* bindContextLearning(plan, baselineCandidateId)
  return yield* prepareWrite(runtime, plan, { contract: "hswm-context-policy/v1", mode: "BASELINE", scopeSha256: binding.scopeSha256, bindingSha256: binding.bindingSha256,
    baselineCandidateId, selectedCandidateId: baselineCandidateId, evidence: null, authority: "OWNER_ADMITTED_EXTERNAL_ASSESSMENT_NOT_AUTHENTICATED", observedOperationalEfficacy: null }, target, "initialize")
})
export const prepareLearnedContextPolicy = (runtime: Runtime, plan: ContextPlan, baselineCandidateId: string, rawEvidence: unknown, target: unknown) => Effect.gen(function* () {
  const binding = yield* bindContextLearning(plan, baselineCandidateId)
  const checked = yield* validateContextPolicyEvidence(binding, rawEvidence)
  const bytes = encode(rawEvidence)
  if (bytes.byteLength > 2097152) return yield* Effect.fail(contextError("POLICY_EVIDENCE_INVALID", "Evidence exceeds 2 MiB"))
  const evidence = yield* runtime.stageContent(CONTEXT_POLICY_EVIDENCE_MEDIA, bytes)
  return yield* prepareWrite(runtime, plan, { contract: "hswm-context-policy/v1", mode: "LEARNED", scopeSha256: binding.scopeSha256, bindingSha256: binding.bindingSha256,
    baselineCandidateId, selectedCandidateId: checked.evidence.selectedCandidateId, evidence, authority: "OWNER_ADMITTED_EXTERNAL_ASSESSMENT_NOT_AUTHENTICATED", observedOperationalEfficacy: null }, target, "learn")
})
export const prepareContextPolicyRestore = (runtime: Runtime, plan: ContextPlan, rawSourceKey: unknown, target: unknown) => Effect.gen(function* () {
  const sourceKey = yield* Schema.decodeUnknownEither(CanonicalAtomV2KeySchema)(rawSourceKey, { onExcessProperty: "error" })
  const decodedTarget = yield* Schema.decodeUnknownEither(TargetSchema)(target, { onExcessProperty: "error" })
  if (!sameLineage(sourceKey, decodedTarget.key) || sourceKey.revisionId >= decodedTarget.key.revisionId - 1) return yield* Effect.fail(contextError("POLICY_RESTORE_INVALID", "Restore an older revision of this policy with a new successor; never rewind the journal"))
  const snapshot = yield* runtime.snapshot
  const atom = snapshot.canonical.atoms.find(a => sameKey(a.key, sourceKey))
  if (!atom || atom.responsibilityOwner !== decodedTarget.owner) return yield* Effect.fail(contextError("POLICY_RESTORE_INVALID", "Restore source must exist under the same owner"))
  const policy = yield* readPolicyPayload(runtime, atom, plan)
  return yield* prepareWrite(runtime, plan, { ...policy, restoredFrom: sourceKey }, target, "restore")
})

/** Same callback boundary as semantic relation learning: only the supplied owner admits the proposal. */
export const admitContextPolicyProposal = <A, E, R>(proposal: Effect.Effect.Success<ReturnType<typeof prepareLearnedContextPolicy>>, admission: { readonly admit: (p: typeof proposal) => Effect.Effect<A, E, R> }) => admission.admit(proposal)
