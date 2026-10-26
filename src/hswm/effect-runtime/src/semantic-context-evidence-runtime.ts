/** Query-driven local retrieval using the existing native activation, owner admission and W loop. */
import { Effect, Either, Schema } from "effect"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { contextError, contextHash, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { parseJson } from "./adaptive-domain.js"
import { prepareSemanticContext } from "./semantic-context-runtime.js"
import { executeActivationLoop, ActivationAssessmentSchema, type ActivationLoopPorts } from "./semantic-context-loop-runtime.js"
import { ActivationFeaturesSchema, type ActivationFeatures } from "./semantic-context-activation-domain.js"
import { EvidenceStepSchema, inspectEvidenceAction, validateEvidenceNavigation, type EvidenceStep, type EvidenceAction, type VisitedEvidence } from "./semantic-context-evidence-domain.js"
import { AdaptiveExecutorError } from "./adaptive-executor.js"

export const EVIDENCE_STEP_MEDIA = "application/vnd.hswm.evidence-step-v1+json"
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const invalid = (detail: string) => contextError("EVIDENCE_TRAVERSAL_INVALID", detail)
const same = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => canonicalAtomV2KeyId(a) === canonicalAtomV2KeyId(b)
const currentAtom = (runtime: Runtime, key: CanonicalAtomV2Key) => Effect.gen(function* () {
  const state = (yield* runtime.snapshot).canonical
  const versions = state.atoms.filter(a => a.key.schemaVersion === key.schemaVersion && a.key.lineageId === key.lineageId && a.key.atomUid === key.atomUid)
  const atom = versions.find(a => same(a.key, key))
  if (!atom || atom.lifecycle !== "ADMITTED" || versions.some(a => a.key.revisionId > key.revisionId))
    return yield* Effect.fail(invalid("Expected current admitted source/step; historical pins are not silently rebound"))
  return atom
})
export const readEvidenceStep = (runtime: Runtime, key: CanonicalAtomV2Key) => Effect.gen(function* () {
  const atom = yield* currentAtom(runtime, key)
  if (atom.content.mediaType !== EVIDENCE_STEP_MEDIA || atom.content.byteLength > 65536)
    return yield* Effect.fail(invalid("Expected bounded evidence step"))
  const step = yield* Schema.decodeUnknown(EvidenceStepSchema)(yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(atom.content))), { onExcessProperty: "error" })
  const expected = step.edges.map(e => ({ referenceType: "hswm:activation:next", role: e.id, target: e.next }))
  if (contextHash(expected) !== contextHash(atom.references.filter(r => r.referenceType === "hswm:activation:next")))
    return yield* Effect.fail(invalid("Local edge identities differ from native next references"))
  return { atom, step }
})
export interface EvidenceTraversalPorts<E, R> extends ActivationLoopPorts<E, R> {
  readonly features: (plan: ContextPlan, step: EvidenceStep) => Effect.Effect<ActivationFeatures, E, R>
  readonly target: (policyKey: CanonicalAtomV2Key) => unknown
}
export const executeEvidenceTraversal = <E, R>(runtime: Runtime, request: {
  readonly entry: CanonicalAtomV2Key; readonly question: string; readonly mode: "TRAIN" | "AUDIT"; readonly cell: unknown
  readonly maximumHops: number; readonly maximumEvidenceBytes: number; readonly maximumWireBytes: number
}, ports: EvidenceTraversalPorts<E, R>) => Effect.gen(function* () {
  if (!Number.isInteger(request.maximumHops) || request.maximumHops < 1 || request.maximumHops > 8 ||
    !request.question.trim() || request.question.length > 4096 ||
    !Number.isSafeInteger(request.maximumEvidenceBytes) || request.maximumEvidenceBytes < 1 || request.maximumEvidenceBytes > 524288 ||
    !Number.isSafeInteger(request.maximumWireBytes) || request.maximumWireBytes < 1 || request.maximumWireBytes > 8388608)
    return yield* Effect.fail(invalid("Explicit bounded question, hop, unique evidence and cumulative wire budgets required"))
  const hops: Array<{ readonly stepKey: CanonicalAtomV2Key; readonly decision: EvidenceAction | null; readonly rejection: string | null;
    readonly result: Effect.Effect.Success<ReturnType<typeof executeActivationLoop<E, R>>> }> = []
  const visited: Array<VisitedEvidence & { readonly key: CanonicalAtomV2Key }> = []
  const pinned: Array<{ readonly key: CanonicalAtomV2Key; readonly sha256: string }> = []
  let cursor = request.entry, required: ReadonlyArray<string> = [], evidenceBytes = 0, wireBytes = 0
  let expectedResource: string | null = null
  const recheck = () => Effect.forEach(pinned, pin => currentAtom(runtime, pin.key).pipe(Effect.flatMap(atom =>
    atom.content.sha256 === pin.sha256 ? Effect.void : Effect.fail(invalid("Visited binding changed during this traversal")))), { discard: true })
  const finish = (status: "ANSWERED" | "ABSTAINED" | "HELD" | "INVALID_ACTION" | "CYCLE" | "HOP_BUDGET" | "EVIDENCE_BUDGET", answer: string | null = null) => Effect.gen(function* () {
    const record = { contract: "hswm-evidence-traversal/v1", questionSha256: contextHash(request.question), mode: request.mode,
      status, answer, evidenceBytes, wireBytes, maximumHops: request.maximumHops,
      visited: visited.map(({ text: _text, ...v }) => v),
      hops: hops.map(h => ({ stepKey: h.stepKey, decision: h.decision, rejection: h.rejection, trace: h.result.execution.trace?.traceContent ?? null,
        assessment: h.result.assessment, policyBefore: h.result.execution.selection.policyKey, policyAfter: h.result.readback?.atom.key ?? null })) }
    // Reader: consumer checker compares the route, quote bindings and actual native traces.
    const receiptContent = yield* runtime.stageContent("application/vnd.hswm.evidence-traversal-v1+json", new TextEncoder().encode(contextJson(record)))
    return { ...record, hops, receiptContent, grounding: "QUOTE_INTEGRITY_NOT_ENTAILMENT" as const,
      credit: "PER_HOP_EXTERNAL_OUTCOME_NOT_TERMINAL_CAUSAL_CREDIT" as const,
      locality: "VISITED_CONTENT_ONLY;NATIVE_SNAPSHOT_RESTORE_NOT_LOCAL" as const }
  })
  for (let index = 0; index < request.maximumHops; index++) {
    if (hops.some(h => same(h.stepKey, cursor))) return yield* finish("CYCLE")
    yield* recheck()
    const { atom, step } = yield* readEvidenceStep(runtime, cursor)
    if (step.spec.minimumConfidence !== 0 || step.spec.minimumMargin !== 0)
      return yield* Effect.fail(invalid("Native W scores are not calibrated Jev probabilities; probability thresholds cannot be silently ignored"))
    if (expectedResource !== null && step.resource !== expectedResource)
      return yield* Effect.fail(invalid("Native continuation does not represent the selected USL resource"))
    if (required.some(uid => !step.spec.mandatoryRelationUids.includes(uid)))
      return yield* Effect.fail(invalid("Continuation dropped a required rule or its source/exception roles"))
    required = step.spec.mandatoryRelationUids
    const event = contextJson({ question: request.question, hop: index, remainingHops: request.maximumHops - index,
      previous: hops.at(-1)?.result.execution.trace?.traceContent.sha256 ?? null })
    const plan = yield* prepareSemanticContext(runtime, { ...step.spec, event })
    const mandatory = plan.bindings.filter(b => required.includes(b.key.atomUid)).flatMap(b => b.participants)
    if (!mandatory.some(p => same(p.key, cursor)) || !mandatory.some(p => same(p.key, step.navigation)))
      return yield* Effect.fail(invalid("Step and complete USL navigation must be activated as mandatory participants"))
    pinned.push({ key: cursor, sha256: atom.content.sha256 })
    const nav = yield* currentAtom(runtime, step.navigation)
    if (nav.content.byteLength > 65536) return yield* Effect.fail(invalid("Complete local USL context exceeds the step budget"))
    yield* validateEvidenceNavigation(yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(nav.content))), step)
    pinned.push({ key: nav.key, sha256: nav.content.sha256 })
    for (const source of step.evidence) {
      if (!mandatory.some(p => p.role === "evidence" && same(p.key, source.key) && p.content.sha256 === source.sha256))
        return yield* Effect.fail(invalid("Source must be an exact evidence role in a mandatory activated relation"))
      const previous = visited.find(v => v.sourceId === source.sourceId)
      if (previous) {
        if (!same(previous.key, source.key) || previous.sha256 !== source.sha256) return yield* Effect.fail(invalid("Source ID collision"))
        continue
      }
      const sourceAtom = yield* currentAtom(runtime, source.key)
      if (sourceAtom.content.sha256 !== source.sha256) return yield* Effect.fail(invalid("Evidence content pin mismatch"))
      if (evidenceBytes + sourceAtom.content.byteLength > request.maximumEvidenceBytes) return yield* finish("EVIDENCE_BUDGET")
      const bytes = yield* runtime.readContent(sourceAtom.content)
      const sourceText = yield* Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(bytes), catch: () => invalid("Evidence must be complete UTF-8") })
      evidenceBytes += bytes.byteLength
      visited.push({ ...source, text: sourceText }); pinned.push({ key: source.key, sha256: source.sha256 })
    }
    if (plan.bindings.flatMap(b => b.participants).filter(p => p.role === "evidence")
      .some(p => !visited.some(v => same(v.key, p.key) && v.sha256 === p.content.sha256)))
      return yield* Effect.fail(invalid("All candidate evidence must be declared and counted in the evidence budget"))
    const policies = (yield* runtime.snapshot).canonical.atoms.filter(a => a.key.atomUid === step.policyUid)
    if (!policies.length || new Set(policies.map(a => contextJson([a.key.schemaVersion, a.key.lineageId]))).size !== 1)
      return yield* Effect.fail(invalid("Expected one existing policy lineage at this step"))
    const policy = policies.reduce((a, b) => a.key.revisionId > b.key.revisionId ? a : b)
    const features = yield* Schema.decodeUnknown(ActivationFeaturesSchema)(yield* ports.features(plan, step), { onExcessProperty: "error" })
    let decision: EvidenceAction | null = null, rejection: string | null = null
    const result = yield* executeActivationLoop(runtime, plan, { decision: { policyKey: policy.key, features, mode: request.mode === "TRAIN" ? "EXPLORE" : "EXPLOIT" },
      mode: request.mode, target: ports.target(policy.key), cell: request.cell, presentation: "source_evidence_tail" }, {
      ...ports,
      http: { postJson: call => Effect.gen(function* () {
        if (wireBytes + call.body.byteLength > request.maximumWireBytes)
          return yield* Effect.fail(new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: "Cumulative traversal wire budget exceeded before provider call" }))
        wireBytes += call.body.byteLength
        return yield* ports.http.postJson(call)
      }) },
      evaluate: execution => Effect.gen(function* () {
        // No evaluator may turn invalid/unvisited citations into positive native learning credit.
        const checked = inspectEvidenceAction(execution.trace?.prediction ?? "", step, visited)
        decision = Either.isRight(checked) ? checked.right.action : null
        rejection = execution.trace === null ? "NOT_EXECUTED" : Either.isLeft(checked) ? checked.left.code : null
        const external = yield* Schema.decodeUnknown(ActivationAssessmentSchema)(yield* ports.evaluate(execution), { onExcessProperty: "error" })
        yield* recheck()
        const outcome = yield* runtime.stageContent("application/vnd.hswm.evidence-action-outcome-v1+json", new TextEncoder().encode(contextJson({
          external, actionIntegrity: rejection ?? "VALID", trace: execution.trace?.traceContent ?? null, semanticTruth: "EXTERNAL_EVALUATOR_ONLY"
        })))
        return { ...external, reward: rejection && external.reward !== null ? 0 : external.reward,
          continue: rejection ? false : external.continue,
          observed: contextJson({ outcome, actionIntegrity: rejection ?? "VALID" }) }
      })
    })
    hops.push({ stepKey: cursor, decision, rejection, result })
    yield* recheck()
    if (result.execution.trace === null) return yield* finish("HELD")
    // Read the captured result without interpreting a model's uncertainty as success.
    const checked = inspectEvidenceAction(result.execution.trace?.prediction ?? "", step, visited)
    if (Either.isLeft(checked)) return yield* finish("INVALID_ACTION")
    if (!result.assessment.continue) return yield* finish("HELD")
    const action = checked.right.action
    if (action.action === "ANSWER") return yield* finish("ANSWERED", action.answer)
    if (action.action === "ABSTAIN") return yield* finish("ABSTAINED")
    const next = step.edges.find(e => e.id === action.edgeId)
    if (!next) return yield* Effect.fail(invalid("Validated edge disappeared"))
    cursor = next.next; expectedResource = next.resource
  }
  return yield* finish("HOP_BUDGET")
})
