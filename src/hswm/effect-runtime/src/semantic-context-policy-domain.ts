/** Pure native-to-W binding. Exact task/source scope; no unseen-context generalization. */
import { Either, Schema } from "effect"
import { canonicalAtomV2KeyId, CanonicalAtomV2ContentSchema, CanonicalAtomV2KeySchema } from "./canonical-atom-v2-schema.js"
import { contextError, contextHash, type ContextPlan } from "./semantic-context-domain.js"

export const CONTEXT_POLICY_MEDIA = "application/vnd.hswm.context-policy-v1+json"
export const CONTEXT_POLICY_EVIDENCE_MEDIA = "application/vnd.hswm.context-policy-evidence-v1+json"
export const CONTEXT_POLICY_KIND = "semantic_context_policy"
const sha = Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))
const text = Schema.String.pipe(Schema.minLength(1), Schema.maxLength(256))
export const contextScopeHash = (plan: ContextPlan) => contextHash({ spec: plan.spec, bindings: plan.bindings })

export const bindContextLearning = (plan: ContextPlan, baselineCandidateId: string) => Either.gen(function* () {
  if (!plan.spec.candidates.some(c => c.id === baselineCandidateId)) return yield* Either.left(contextError("BASELINE_INVALID", "Baseline must be an exact candidate in this plan"))
  const scopeSha256 = contextScopeHash(plan)
  const sourceAtoms = plan.bindings.flatMap(b => [{ key: b.key, owner: b.owner, content: b.content }, ...b.participants.map(p => ({ key: p.key, owner: p.owner, content: p.content }))])
  const sources = [...new Map(sourceAtoms.map(a => [canonicalAtomV2KeyId(a.key), a])).values()].map(a => ({
    ruleUid: `rule:${contextHash(a.key)}`, evidenceId: `source:${contextHash(a.key)}`, ...a
  }))
  const incidences = plan.bindings.map(b => ({
    relationKey: b.key, owner: b.owner,
    members: [{ ruleUid: `rule:${contextHash(b.key)}`, role: `frame:${contextHash(b.key)}:relation`, ordinal: 0 },
      ...b.participants.map((p, index) => ({ ruleUid: `rule:${contextHash(p.key)}`, role: `frame:${contextHash(b.key)}:role:${contextHash([p.referenceType, p.role])}`, ordinal: index + 1 }))],
    participants: b.participants.map((p, index) => ({ referenceType: p.referenceType, role: p.role, ordinal: index + 1, key: p.key, owner: p.owner, content: p.content }))
  }))
  const actionCandidates = plan.spec.candidates.map(c => ({ actionUid: `action:${scopeSha256}:${c.id}`, candidateId: c.id }))
  const actions = plan.spec.candidates.map((c, index) => ({
    uid: actionCandidates[index]?.actionUid ?? "", revision: scopeSha256,
    members: [...new Set([...plan.spec.mandatoryRelationUids, ...c.relationUids])].flatMap(uid => incidences.filter(i => i.relationKey.atomUid === uid).flatMap(i => i.members))
  }))
  const required = incidences.filter(i => plan.spec.mandatoryRelationUids.includes(i.relationKey.atomUid)).flatMap(i => i.members)
  if (sources.length > 128 || actions.some(a => a.members.length > 64) || new Set(required.map(m => m.role)).size > 64) return yield* Either.left(contextError("LEARNING_BINDING_BUDGET", "Complete incidence/source set exceeds the W v1 contract; no projection truncation"))
  const contextUid = `context:${scopeSha256}`
  const graph = {
    uid: `graph:${scopeSha256}`, revision: scopeSha256,
    rules: sources.map(s => ({ uid: s.ruleUid, revision: s.content.sha256, evidenceId: s.evidenceId, bytes: s.content.byteLength })), actions,
    contexts: [{ uid: contextUid, revision: scopeSha256, allowedActions: actions.map(a => a.uid), requiredRules: [...new Set(required.map(m => m.ruleUid))], requiredRoles: [...new Set(required.map(m => m.role))], maxActiveRules: Math.min(sources.length, 64), maxBytes: plan.spec.maximumContextBytes }],
    placements: [{ uid: `placement:${scopeSha256}`, revision: scopeSha256, contextUid, actionUid: `action:${scopeSha256}:${baselineCandidateId}` }]
  }
  const body = { contract: "hswm-context-learning-binding/v1" as const, scopeSha256, baselineCandidateId, graph, sources, incidences, actionCandidates }
  return { ...body, bindingSha256: contextHash(body) }
})
export type ContextLearningBinding = Either.Either.Right<ReturnType<typeof bindContextLearning>>

/** Policy payload is integer-only canonical data. Statistical evidence stays in a separate byte-bound artifact. */
export const ContextPolicySchema = Schema.Struct({
  contract: Schema.Literal("hswm-context-policy/v1"), scopeSha256: sha, bindingSha256: sha,
  baselineCandidateId: text, selectedCandidateId: text,
  mode: Schema.Literal("BASELINE", "LEARNED"), evidence: Schema.NullOr(CanonicalAtomV2ContentSchema),
  restoredFrom: Schema.optional(CanonicalAtomV2KeySchema),
  authority: Schema.Literal("OWNER_ADMITTED_EXTERNAL_ASSESSMENT_NOT_AUTHENTICATED"),
  observedOperationalEfficacy: Schema.Null
})
export type ContextPolicy = typeof ContextPolicySchema.Type
export const decodeContextPolicy = (raw: unknown) => Schema.decodeUnknownEither(ContextPolicySchema)(raw, { onExcessProperty: "error" }).pipe(
  Either.mapLeft(() => contextError("POLICY_INVALID", "Expected a byte-bound scoped context policy")))

// Decode only consumed report fields; preserve/hash the complete external report, including estimates and provenance.
const reportSchema = Schema.Struct({
  schema: Schema.Literal("hswm-w-report/v1"), inputDigest: sha,
  provenance: Schema.Struct({ dataKind: Schema.Literal("SYNTHETIC", "OPERATIONAL"), observedOperationalEfficacy: Schema.Null }),
  policy: Schema.Struct({ trainDigest: sha, contexts: Schema.Array(Schema.Struct({ uid: text, contextUid: text, contextRevision: text, baselineActionUid: text, chosenActionUid: text, status: Schema.Literal("LEARNED_CANDIDATE") })).pipe(Schema.itemsCount(1)) }),
  evaluations: Schema.Array(Schema.Struct({ uid: text, contextUid: text, policyUid: text, status: Schema.Literal("READY_FOR_OWNER_REVIEW"), requiredCoverageViolations: Schema.Literal(0) })).pipe(Schema.itemsCount(1)),
  proposals: Schema.Array(Schema.Struct({ contextUid: text, status: Schema.Literal("READY_FOR_OWNER_REVIEW"), expectedGraphDigest: sha, readSet: Schema.Struct({ policyUid: text, evaluationUid: text }), before: Schema.Struct({ actionUid: text }), after: Schema.Struct({ actionUid: text }) })).pipe(Schema.itemsCount(1))
})
const EvidenceSchema = Schema.Struct({
  contract: Schema.Literal("hswm-context-policy-evidence/v1"), bindingSha256: sha, graphSha256: sha,
  baselineCandidateId: text, selectedCandidateId: text, reportSha256: sha, report: Schema.Unknown,
  authority: Schema.Literal("SECONDARY_AI_EXTERNAL_EVALUATION_NOT_ADMISSION"), observedOperationalEfficacy: Schema.Null
})
export const validateContextPolicyEvidence = (binding: ContextLearningBinding, raw: unknown) => Either.gen(function* () {
  const evidence = yield* Schema.decodeUnknownEither(EvidenceSchema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => contextError("POLICY_EVIDENCE_INVALID", "Expected W context-policy export, not a Jev score or free-text outcome")))
  const report = yield* Schema.decodeUnknownEither(reportSchema)(evidence.report).pipe(Either.mapLeft(() => contextError("POLICY_NOT_READY", "A single context requires supported training and READY held-out evaluation")))
  const policy = report.policy.contexts[0], evaluation = report.evaluations[0], proposal = report.proposals[0]
  const chosen = binding.actionCandidates.find(a => a.candidateId === evidence.selectedCandidateId)
  const baseline = binding.actionCandidates.find(a => a.candidateId === binding.baselineCandidateId)
  if (!policy || !evaluation || !proposal || !chosen || !baseline ||
    evidence.bindingSha256 !== binding.bindingSha256 || evidence.graphSha256 !== contextHash(binding.graph) || evidence.reportSha256 !== contextHash(evidence.report) ||
    evidence.baselineCandidateId !== binding.baselineCandidateId || chosen.actionUid === baseline.actionUid ||
    policy.contextUid !== binding.graph.contexts[0]?.uid || policy.contextRevision !== binding.scopeSha256 || policy.baselineActionUid !== baseline.actionUid || policy.chosenActionUid !== chosen.actionUid ||
    evaluation.contextUid !== policy.contextUid || evaluation.policyUid !== policy.uid || proposal.contextUid !== policy.contextUid ||
    proposal.expectedGraphDigest !== evidence.graphSha256 || proposal.readSet.policyUid !== policy.uid || proposal.readSet.evaluationUid !== evaluation.uid ||
    proposal.before.actionUid !== baseline.actionUid || proposal.after.actionUid !== chosen.actionUid) {
    return yield* Either.left(contextError("POLICY_BINDING_MISMATCH", "Evidence must bind the complete current sources, roles, candidates, baseline and held-out decision"))
  }
  return { evidence, dataKind: report.provenance.dataKind }
})

export const ContextPolicyDecisionSchema = Schema.Struct({ contract: Schema.Literal("hswm-context-policy-decision/v1"), policyKey: CanonicalAtomV2KeySchema })
