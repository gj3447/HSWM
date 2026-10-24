/** Incremental native graph traversal. Each visited vertex uses the existing activation/W loop. */
import { Effect, Schema } from "effect"
import { parseJson } from "./adaptive-domain.js"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, type CanonicalAtomV2Key, type CanonicalAtomV2Content } from "./canonical-atom-v2-schema.js"
import { ContextSpecSchema, contextError, contextHash, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { prepareSemanticContext } from "./semantic-context-runtime.js"
import { ActivationFeaturesSchema, type ActivationFeatures } from "./semantic-context-activation-domain.js"
import { executeActivationLoop, type ActivationLoopPorts } from "./semantic-context-loop-runtime.js"
import type { ContextPresentation } from "./semantic-context-presentation-domain.js"

export const ACTIVATION_STEP_MEDIA = "application/vnd.hswm.activation-step-v1+json"
export const ActivationStepSchema = Schema.Struct({
  contract: Schema.Literal("hswm-activation-step/v1"),
  spec: ContextSpecSchema.omit("event"),
  policyUid: Schema.NonEmptyString,
  edges: Schema.Array(Schema.Struct({ candidateId: Schema.NonEmptyString, next: Schema.NullOr(CanonicalAtomV2KeySchema) }))
    .pipe(Schema.minItems(1), Schema.maxItems(8))
})
export type ActivationStep = typeof ActivationStepSchema.Type
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const invalid = (detail: string) => contextError("TRAVERSAL_INVALID", detail)
const same = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => canonicalAtomV2KeyId(a) === canonicalAtomV2KeyId(b)
const lineage = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => a.schemaVersion === b.schemaVersion && a.lineageId === b.lineageId && a.atomUid === b.atomUid

export const readActivationStep = (runtime: Runtime, key: CanonicalAtomV2Key) => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  const atom = snapshot.canonical.atoms.find(a => same(a.key, key))
  if (!atom || atom.lifecycle !== "ADMITTED" || atom.content.mediaType !== ACTIVATION_STEP_MEDIA || atom.content.byteLength > 65536 ||
    snapshot.canonical.atoms.some(a => lineage(a.key, key) && a.key.revisionId > key.revisionId)) {
    return yield* Effect.fail(invalid("Expected one current admitted, bounded step; no global graph discovery"))
  }
  const step = yield* Schema.decodeUnknown(ActivationStepSchema)(yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(atom.content))), { onExcessProperty: "error" })
  if (contextHash(step.edges.map(e => e.candidateId).sort()) !== contextHash(step.spec.candidates.map(c => c.id).sort())) {
    return yield* Effect.fail(invalid("Each local candidate needs exactly one explicit continuation, including terminal null"))
  }
  const declared = step.edges.flatMap(e => e.next === null ? [] : [{ referenceType: "hswm:activation:next", role: e.candidateId, target: e.next }])
  if (contextHash(declared) !== contextHash(atom.references.filter(r => r.referenceType === "hswm:activation:next"))) {
    return yield* Effect.fail(invalid("Next-step roles/versions differ from native references"))
  }
  return { atom, step }
})

export interface ActivationTraversalPorts<E, R> extends ActivationLoopPorts<E, R> {
  readonly features: (plan: ContextPlan, step: ActivationStep) => Effect.Effect<ActivationFeatures, E, R>
  readonly target: (policyKey: CanonicalAtomV2Key) => unknown
}
export const executeActivationTraversal = <E, R>(runtime: Runtime, request: {
  readonly entry: CanonicalAtomV2Key; readonly event: string; readonly maximumHops: number
  readonly mode: "TRAIN" | "AUDIT"; readonly cell: unknown; readonly presentation?: ContextPresentation
}, ports: ActivationTraversalPorts<E, R>) => Effect.gen(function* () {
  if (!Number.isInteger(request.maximumHops) || request.maximumHops < 1 || request.maximumHops > 32 ||
    request.event.length === 0 || request.event.length > 4096) return yield* Effect.fail(invalid("Explicit hop budget 1..32 and bounded original event required"))
  const hops: Array<{ readonly stepKey: CanonicalAtomV2Key; readonly stepContent: CanonicalAtomV2Content;
    readonly planSha256: string; readonly result: Effect.Effect.Success<ReturnType<typeof executeActivationLoop<E, R>>> }> = []
  let cursor = request.entry
  let previous: { readonly prediction: string; readonly traceSha256: string } | null = null
  let required: ReadonlyArray<string> = []
  const finish = (status: "COMPLETED" | "HELD" | "CYCLE" | "HOP_BUDGET") => Effect.gen(function* () {
    const result = { contract: "hswm-activation-traversal/v1" as const, status, hops,
      locality: "VISITED_STEP_AND_LOCAL_CANDIDATES;NATIVE_SNAPSHOT_RESTORE_NOT_LOCAL" as const,
      credit: "PER_HOP_EXTERNAL_OUTCOME_NOT_TERMINAL_CAUSAL_CREDIT" as const }
    const receiptContent = yield* runtime.stageContent("application/vnd.hswm.activation-traversal-v1+json", new TextEncoder().encode(contextJson({
      ...result, eventSha256: contextHash(request.event), mode: request.mode, maximumHops: request.maximumHops,
      hops: hops.map(h => ({ stepKey: h.stepKey, stepContent: h.stepContent, planSha256: h.planSha256,
        traceContent: h.result.execution.trace?.traceContent ?? null, status: h.result.status,
        assessment: h.result.assessment, outcomeContent: h.result.proposal?.outcomeContent ?? null,
        policyBefore: h.result.execution.selection.policyKey, policyAfter: h.result.readback?.atom.key ?? null }))
    })))
    return { ...result, receiptContent }
  })
  for (let index = 0; index < request.maximumHops; index++) {
    if (hops.some(h => same(h.stepKey, cursor))) return yield* finish("CYCLE")
    const opened = yield* readActivationStep(runtime, cursor)
    if (required.some(uid => !opened.step.spec.mandatoryRelationUids.includes(uid))) {
      return yield* Effect.fail(invalid("Continuation dropped a previously required rule; no model call at this hop"))
    }
    required = opened.step.spec.mandatoryRelationUids
    const event = contextJson({ input: request.event, previous })
    const plan = yield* prepareSemanticContext(runtime, { ...opened.step.spec, event })
    // The step's bytes, roles and outgoing edges must participate in W scope and actual prompt.
    if (!plan.bindings.some(b => required.includes(b.key.atomUid) && b.participants.some(p => same(p.key, cursor)))) {
      return yield* Effect.fail(invalid("Step must be a participant of a mandatory relation, binding route semantics to execution and W"))
    }
    const snapshot = yield* runtime.snapshot
    const policies = snapshot.canonical.atoms.filter(a => a.key.atomUid === opened.step.policyUid)
    if (policies.length === 0 || new Set(policies.map(a => contextJson([a.key.schemaVersion, a.key.lineageId]))).size !== 1) {
      return yield* Effect.fail(invalid("One existing policy lineage must resolve at this visited step"))
    }
    const latest = policies.reduce((a, b) => a.key.revisionId > b.key.revisionId ? a : b)
    const features = yield* Schema.decodeUnknown(ActivationFeaturesSchema)(yield* ports.features(plan, opened.step), { onExcessProperty: "error" })
    const result = yield* executeActivationLoop(runtime, plan, {
      decision: { policyKey: latest.key, features, mode: request.mode === "TRAIN" ? "EXPLORE" : "EXPLOIT" },
      mode: request.mode, target: ports.target(latest.key), cell: request.cell, presentation: request.presentation ?? "execution_tail"
    }, ports)
    hops.push({ stepKey: cursor, stepContent: opened.atom.content, planSha256: plan.planSha256, result })
    if (!result.assessment.continue || result.execution.trace === null) return yield* finish("HELD")
    const edge = opened.step.edges.find(e => e.candidateId === result.execution.selection.candidateId)
    if (!edge) return yield* Effect.fail(invalid("Selected continuation missing"))
    // Reject drift even during AUDIT/evaluation; owner updates to policy alone are allowed.
    const rechecked = yield* readActivationStep(runtime, cursor)
    if (rechecked.atom.content.sha256 !== opened.atom.content.sha256) return yield* Effect.fail(invalid("Step changed during execution"))
    if (edge.next === null) return yield* finish("COMPLETED")
    previous = { prediction: result.execution.trace.prediction, traceSha256: result.execution.trace.traceContent.sha256 }
    cursor = edge.next
  }
  return yield* finish("HOP_BUDGET")
})
