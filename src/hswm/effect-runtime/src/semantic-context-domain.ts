/** Pure, bounded context selection. Scores are observations, never Semantic Weight. */
import { createHash } from "node:crypto"
import { Data, Either, Schema } from "effect"
import { canonicalAtomV2KeyId } from "./canonical-atom-v2-schema.js"
import { type CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"

export class SemanticContextError extends Data.TaggedError("SemanticContextError")<{
  readonly code: string
  readonly detail: string
}> {}
export const contextError = (code: string, detail: string) => new SemanticContextError({ code, detail })
export const contextJson = (value: unknown): string => JSON.stringify(value)
export const contextHash = (value: unknown): string => createHash("sha256").update(contextJson(value)).digest("hex")
export const contextByteLength = (value: unknown): number => new TextEncoder().encode(contextJson(value)).byteLength
const boundedText = (max: number) => Schema.String.pipe(Schema.minLength(1), Schema.maxLength(max), Schema.filter(s => s.trim().length > 0))
const identifiers = Schema.Array(boundedText(512)).pipe(Schema.maxItems(8), Schema.filter(xs => new Set(xs).size === xs.length))
const probability = Schema.Number.pipe(Schema.filter(n => Number.isFinite(n) && n >= 0 && n <= 1))
export const ContextSpecSchema = Schema.Struct({
  contract: Schema.Literal("hswm-semantic-context-spec/v1"),
  event: boundedText(8192),
  mandatoryRelationUids: identifiers,
  candidates: Schema.Array(Schema.Struct({
    id: Schema.String.pipe(Schema.pattern(/^[a-z][a-z0-9_-]{0,47}$/)),
    summary: boundedText(240),
    relationUids: identifiers.pipe(Schema.minItems(1))
  })).pipe(Schema.minItems(1), Schema.maxItems(8), Schema.filter(xs => new Set(xs.map(x => x.id)).size === xs.length)),
  maximumContextBytes: Schema.Number.pipe(Schema.int(), Schema.between(1, 524288)),
  minimumConfidence: probability,
  minimumMargin: probability
})
export type ContextSpec = typeof ContextSpecSchema.Type
export const decodeContextSpec = (raw: unknown) => Schema.decodeUnknownEither(ContextSpecSchema)(raw, { onExcessProperty: "error" }).pipe(
  Either.mapLeft(() => contextError("SPEC_INVALID", "Expected bounded task, distinct candidates, exact roots and explicit byte/decision policy")))

export const buildContextPlan = (raw: unknown, state: CanonicalAtomV2State) => Either.gen(function* () {
  const spec = yield* decodeContextSpec(raw)
  const roots = [...new Set([...spec.mandatoryRelationUids, ...spec.candidates.flatMap(c => c.relationUids)])].sort()
  const bindings = []
  for (const root of roots) {
    const versions = state.atoms.filter(a => a.key.atomUid === root)
    if (versions.length === 0 || new Set(versions.map(a => contextJson([a.key.schemaVersion, a.key.lineageId]))).size !== 1) {
      return yield* Either.left(contextError("ROOT_UNRESOLVED", "Every root must resolve uniquely within schema and lineage"))
    }
    const current = versions.reduce((latest, a) => a.key.revisionId > latest.key.revisionId ? a : latest)
    if (current.kind !== "semantic_relation" || current.lifecycle !== "ADMITTED") return yield* Either.left(contextError("ROOT_INVALID", "Context roots must be admitted semantic relations"))
    const participants = []
    for (const reference of current.references.filter(r => r.referenceType !== "hswm:reference:supersedes")) {
      const matches = state.atoms.filter(a => canonicalAtomV2KeyId(a.key) === canonicalAtomV2KeyId(reference.target))
      const target = matches[0]
      if (matches.length !== 1 || target === undefined || target.lifecycle !== "ADMITTED") return yield* Either.left(contextError("ROLE_UNRESOLVED", "Every role must bind one admitted exact participant version"))
      participants.push({ referenceType: reference.referenceType, role: reference.role, key: target.key, owner: target.responsibilityOwner, content: target.content })
    }
    bindings.push({ key: current.key, owner: current.responsibilityOwner, content: current.content, participants })
  }
  const bound = { contract: "hswm-semantic-context-plan/v1" as const, spec, stateRevision: state.revision, bindings }
  const planSha256 = contextHash(bound)
  // Only a caller-authored MAP goes to Jev. It is not asserted to be sufficient or true.
  const request = {
    schema: "jev-request/v1" as const,
    state: contextJson({ task: spec.event, candidates: spec.candidates.map(c => ({ id: c.id, summary: c.summary })), planSha256 }),
    questions: [{ id: "context", type: "choice" as const, instructions: "Choose the context bundle relevant to this task. NONE if no bundle applies. NEED_MORE if descriptions cannot decide. This is relevance, not success or permission.", options: [...spec.candidates.map(c => c.id), "NONE", "NEED_MORE"] }]
  }
  return { ...bound, planSha256, request, requestSha256: contextHash(request), scope: "CALLER_SCOPED_CANDIDATES_NOT_EXHAUSTIVE_GRAPH_SEARCH" as const }
})
export type ContextPlan = Either.Either.Right<ReturnType<typeof buildContextPlan>>

const DecisionSchema = Schema.Struct({
  id: Schema.Literal("context"), type: Schema.Literal("choice"), choice: boundedText(48),
  probabilities: Schema.Record({ key: Schema.String, value: probability }), confidence: probability
})
// Known worker metadata is decoded; additional timing/usage fields stay in the original receipt hash.
const JevResultSchema = Schema.Struct({
  schema: Schema.Literal("jev-result/v1"), backend: Schema.Literal("kotoba-open-jev"),
  model: boundedText(256), revision: boundedText(128), requestSha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)),
  authority: Schema.Literal("advisory"), weightUpdate: Schema.Null, officialTypeSafeJev: Schema.Literal(false), truncated: Schema.Literal(false),
  status: Schema.Literal("candidate", "needs_original_selection"), decisions: Schema.Array(DecisionSchema).pipe(Schema.maxItems(1))
})
export const selectContext = (plan: ContextPlan, raw: unknown) => Either.gen(function* () {
  const receipt = yield* Schema.decodeUnknownEither(JevResultSchema)(raw).pipe(Either.mapLeft(() => contextError("JEV_RECEIPT_INVALID", "Expected a nontruncated advisory open-jev receipt")))
  if (receipt.requestSha256 !== plan.requestSha256) return yield* Either.left(contextError("REQUEST_MISMATCH", "Jev receipt belongs to a different request or graph plan"))
  const base = { contract: "hswm-semantic-context-selection/v1" as const, planSha256: plan.planSha256, requestSha256: plan.requestSha256, receiptSha256: contextHash(raw), backend: receipt.backend, model: receipt.model, revision: receipt.revision, authority: "CALLER_SUPPLIED_RECEIPT_NOT_MODEL_ATTESTATION" as const }
  if (receipt.status === "needs_original_selection") {
    if (receipt.decisions.length !== 0) return yield* Either.left(contextError("JEV_RECEIPT_INVALID", "Oversized input cannot carry a decision"))
    return { ...base, status: "NEED_MORE" as const, reason: "BACKEND_INPUT_LIMIT", candidateId: null, confidence: null, margin: null }
  }
  const decision = receipt.decisions[0]
  const options = [...plan.spec.candidates.map(c => c.id), "NONE", "NEED_MORE"]
  if (decision === undefined || contextJson(Object.keys(decision.probabilities).sort()) !== contextJson([...options].sort())) return yield* Either.left(contextError("OPTION_SET_MISMATCH", "Probabilities must cover the exact candidate set including abstention"))
  const p = decision.probabilities[decision.choice]
  const values = Object.values(decision.probabilities)
  const highest = Math.max(...values)
  if (p === undefined || Math.abs(values.reduce((a,b) => a+b, 0)-1) > 1e-5 || Math.abs(p-highest) > 1e-5 || Math.abs(decision.confidence-highest) > 1e-5) return yield* Either.left(contextError("PROBABILITIES_INVALID", "Invalid probability mass, confidence or winning option"))
  const margin = p-Math.max(...options.filter(o => o !== decision.choice).map(o => decision.probabilities[o] ?? 0))
  if (decision.choice === "NONE" || decision.choice === "NEED_MORE") return { ...base, status: decision.choice, reason: "MODEL_ABSTENTION", candidateId: null, confidence: p, margin }
  if (p < plan.spec.minimumConfidence || margin <= 1e-5 || margin < plan.spec.minimumMargin) return { ...base, status: "NEED_MORE" as const, reason: "UNCERTAIN_SELECTION", candidateId: null, confidence: p, margin }
  return { ...base, status: "SELECTED" as const, reason: "ADVISORY_CANDIDATE", candidateId: decision.choice, confidence: p, margin }
})
export type ContextSelection = Either.Either.Right<ReturnType<typeof selectContext>>
