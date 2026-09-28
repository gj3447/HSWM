/**
 * Post-run projection of actual durable semantic artifacts to the Lean checker.
 * Reading and SHA/JSON checks are Effect adapter obligations, not Lean theorems.
 * This module grants no admission capability and does not mutate graph state.
 */
import { createHash } from "node:crypto"
import { Data, Effect, Either, Schema } from "effect"
import { canonicalJson, parseJson } from "./adaptive-domain.js"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2KeyId, HSWM_SUPERSEDES_REFERENCE_TYPE, HSWM_SUPERSEDES_REFERENCE_ROLE, type CanonicalAtomV2 } from "./canonical-atom-v2-schema.js"
import { readLlmSemanticFrame, type SemanticTrace, type SemanticOutcome, type SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { deriveSemanticDurableBranch, type SemanticDurableBranch, type SelectedSemanticBranch } from "./canonical-atom-v2-semantic-selected-state.js"

const digest = Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))
const natural = Schema.Number.pipe(Schema.int(), Schema.nonNegative(), Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER))
const text = Schema.String.pipe(Schema.minLength(1), Schema.maxLength(524288))
const key = Schema.Struct({ schemaVersion: text, lineageId: text, atomUid: text, revisionId: natural })
const descriptor = Schema.Struct({ sha256: digest, mediaType: text, byteLength: natural })
const status = Schema.Literal("CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED")
const semantic = Schema.Struct({ semanticText: text, disposition: text, uncertainty: text, exceptionRefs: Schema.Array(text),
  trace: Schema.NullOr(descriptor), outcome: Schema.NullOr(Schema.Struct({ sha256: digest, mediaType: text, byteLength: natural, status })),
  revisionEvidence: Schema.optional(descriptor) })
const role = Schema.Struct({ referenceType: text, role: text, key, owner: text, contentSha256: digest, contentUtf8: Schema.String })
const frame = Schema.Struct({ event: text, stateRevision: natural, relation: Schema.Struct({ key, owner: text, semantic }),
  roles: Schema.Array(role), priorEvidence: Schema.NullOr(Schema.Struct({ prediction: text, uncertainty: text, observed: text, source: text, status })), frameSha256: digest })
const storedTrace = Schema.Struct({ contract: Schema.Literal("hswm-llm-semantic-trace/v1"), executionId: text,
  frameSha256: digest, event: text, relationKey: key, prediction: text, predictionSha256: digest, uncertainty: text,
  request: descriptor, response: descriptor, backendConfigurationSha256: digest })
const storedOutcome = Schema.Struct({ contract: Schema.Literal("hswm-llm-semantic-outcome/v1"),
  traceSha256: digest, predictionSha256: digest, observed: text, source: text, status })
const predictionRequest = Schema.Struct({ contract: Schema.Literal("hswm-llm-semantic-predict/v1"), executionId: text, frame })
const predictionResponse = Schema.Struct({ prediction: text, uncertainty: text })
const revisionEvidence = Schema.Struct({ request: descriptor, response: descriptor, trace: descriptor, outcome: descriptor, backendConfigurationSha256: digest })
const revisionRequest = Schema.Struct({ contract: Schema.Literal("hswm-llm-semantic-learn/v1"), frame, trace: storedTrace, outcome: storedOutcome })
const revisionResponse = Schema.Struct({ semanticText: text, disposition: text, uncertainty: text, exceptionRefs: Schema.Array(text) })

export const SemanticRefinementTraceSchema = Schema.Struct({ executionId: text, traceSha256: digest, traceContent: descriptor,
  frameSha256: digest, event: text, relationKey: key, prediction: text, predictionSha256: digest, uncertainty: text, backendConfigurationSha256: digest })
export const SemanticRefinementOutcomeSchema = Schema.Struct({ traceSha256: digest, predictionSha256: digest,
  observed: text, source: text, outcomeContent: descriptor, status })
const branch = Schema.Struct({ root: text, relationUid: text, schemaContentSha256: digest, stateSha256: digest, relationKey: key, owner: text,
  roles: Schema.Array(Schema.Struct({ referenceType: text, role: text, key: text, owner: text, contentSha256: digest })),
  predecessorKey: Schema.NullOr(text), traceSha256: Schema.NullOr(digest), outcomeSha256: Schema.NullOr(digest) })
export const SemanticRefinementSelectionSchema = Schema.Struct({ selected: Schema.Literal("BASELINE", "CANDIDATE"),
  baselineBranch: branch, candidateBranch: branch, selectedBranch: branch })

export class SemanticLifecycleRefinementError extends Data.TaggedError("SemanticLifecycleRefinementError")<{
  readonly code: "ARTIFACT_INVALID" | "ARTIFACT_MISMATCH" | "STATE_CHANGED"
  readonly detail: string
}> {}
const fail = (detail: string, code: SemanticLifecycleRefinementError["code"] = "ARTIFACT_MISMATCH") => new SemanticLifecycleRefinementError({ code, detail })
const sha = (value: Uint8Array | string): string => createHash("sha256").update(value).digest("hex")
const same = (left: unknown, right: unknown): boolean => {
  const a = canonicalJson(left), b = canonicalJson(right)
  return Either.isRight(a) && Either.isRight(b) && a.right === b.right
}
const requireEqual = (left: unknown, right: unknown, label: string) =>
  same(left, right) ? Effect.void : Effect.fail(fail(label))
const decode = <A, I>(schema: Schema.Schema<A, I>, raw: unknown, label: string) =>
  Schema.decodeUnknown(schema)(raw).pipe(Effect.mapError(() => fail(label, "ARTIFACT_INVALID")))
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
type Descriptor = Schema.Schema.Type<typeof descriptor>

const readArtifact = <A, I>(runtime: Runtime, content: Descriptor, schema: Schema.Schema<A, I>, mediaType: string) => Effect.gen(function* () {
  const bound = yield* decode(descriptor, content, "invalid content descriptor")
  if (bound.mediaType !== mediaType || bound.byteLength === 0 || bound.byteLength > 1_048_576) return yield* Effect.fail(fail("unexpected artifact media type or size"))
  const raw = yield* runtime.readContent(bound)
  if (raw.byteLength !== bound.byteLength || sha(raw) !== bound.sha256) return yield* Effect.fail(fail("content bytes do not match descriptor"))
  const utf8 = yield* Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(raw), catch: () => fail("invalid UTF-8", "ARTIFACT_INVALID") })
  const json = yield* parseJson(utf8).pipe(Either.mapLeft(() => fail("invalid or duplicate-key JSON", "ARTIFACT_INVALID")))
  return yield* decode(schema, json, "stored artifact has an invalid shape")
})

const normalizedSemantic = (value: Schema.Schema.Type<typeof semantic>) => Object.freeze({
  semanticText: value.semanticText, disposition: value.disposition, uncertainty: value.uncertainty,
  exceptionRefs: Object.freeze([...value.exceptionRefs]), traceSha256: value.trace?.sha256 ?? null,
  outcomeSha256: value.outcome?.sha256 ?? null, revisionEvidenceSha256: value.revisionEvidence?.sha256 ?? null
})
const normalizedRoles = (roles: SemanticReadFrame["roles"]) => Object.freeze(roles.map(value => Object.freeze({
  referenceType: value.referenceType, role: value.role, key: Object.freeze({ ...value.key }), owner: value.owner, contentSha256: value.contentSha256
})))
const normalizedRelation = (value: SemanticReadFrame) => Object.freeze({
  key: Object.freeze({ ...value.relation.key }), owner: value.relation.owner,
  semantic: normalizedSemantic(value.relation.semantic), roles: normalizedRoles(value.roles)
})
const normalizedFrame = (value: SemanticReadFrame) => Object.freeze({
  event: value.event, stateRevision: value.stateRevision, relationKey: Object.freeze({ ...value.relation.key }),
  owner: value.relation.owner, semantic: normalizedSemantic(value.relation.semantic), roles: normalizedRoles(value.roles), frameSha256: value.frameSha256
})
const normalizedTrace = (value: SemanticTrace) => Object.freeze({ traceSha256: value.traceSha256,
  frameSha256: value.frameSha256, relationKey: Object.freeze({ ...value.relationKey }), predictionSha256: value.predictionSha256,
  backendConfigurationSha256: value.backendConfigurationSha256, event: value.event })

/** Full structured equality is checked too; a supplied frame digest alone is insufficient. */
const boundExecution = (runtime: Runtime, trace: SemanticTrace, expected: SemanticReadFrame) => Effect.gen(function* () {
  if (trace.traceSha256 !== trace.traceContent.sha256 || sha(trace.prediction) !== trace.predictionSha256) return yield* Effect.fail(fail("trace descriptor or prediction digest mismatch"))
  const stored = yield* readArtifact(runtime, trace.traceContent, storedTrace, "application/vnd.hswm.llm-semantic-trace-v1+json")
  yield* requireEqual({ executionId: stored.executionId, frameSha256: stored.frameSha256, event: stored.event, relationKey: stored.relationKey,
    prediction: stored.prediction, predictionSha256: stored.predictionSha256, uncertainty: stored.uncertainty, backendConfigurationSha256: stored.backendConfigurationSha256 },
  { executionId: trace.executionId, frameSha256: trace.frameSha256, event: trace.event, relationKey: trace.relationKey,
    prediction: trace.prediction, predictionSha256: trace.predictionSha256, uncertainty: trace.uncertainty, backendConfigurationSha256: trace.backendConfigurationSha256 }, "trace report differs from durable bytes")
  const request = yield* readArtifact(runtime, stored.request, predictionRequest, "application/vnd.hswm.llm-semantic-request-v1+json")
  const response = yield* readArtifact(runtime, stored.response, predictionResponse, "application/vnd.hswm.llm-semantic-response-v1+json")
  yield* requireEqual(request.executionId, trace.executionId, "execution ID changed")
  yield* requireEqual(request.frame, expected, "request did not use the recovered exact frame")
  yield* requireEqual(response, { prediction: trace.prediction, uncertainty: trace.uncertainty }, "response differs from trace")
  return stored
})

export interface SemanticLifecycleRefinementInput {
  readonly baseline: SemanticDurableBranch
  readonly candidate: SemanticDurableBranch
  readonly selectedRuntime: Runtime
  readonly selection: Pick<SelectedSemanticBranch, "selected" | "baselineBranch" | "candidateBranch" | "selectedBranch">
  readonly trainingTrace: SemanticTrace
  readonly trainingOutcome: SemanticOutcome
  readonly nextTrace: SemanticTrace
}

/** Capture reports before the first durable read; branches must be quiescent during audit. */
export const projectSemanticLifecycleRefinement = (supplied: SemanticLifecycleRefinementInput) => Effect.gen(function* () {
  const captured = yield* Effect.try({ try: () => structuredClone({ selection: supplied.selection,
    trainingTrace: supplied.trainingTrace, trainingOutcome: supplied.trainingOutcome, nextTrace: supplied.nextTrace }),
  catch: () => fail("reports must be cloneable data", "ARTIFACT_INVALID") })
  const input = Object.freeze({ ...captured, baseline: Object.freeze({ ...supplied.baseline }),
    candidate: Object.freeze({ ...supplied.candidate }), selectedRuntime: supplied.selectedRuntime })
  const baseline = yield* deriveSemanticDurableBranch(input.baseline)
  const candidate = yield* deriveSemanticDurableBranch(input.candidate)
  yield* requireEqual(baseline, input.selection.baselineBranch, "baseline changed since selection")
  yield* requireEqual(candidate, input.selection.candidateBranch, "candidate changed since selection")
  const selectedCandidate = input.selection.selected === "CANDIDATE"
  const selectedBranch = selectedCandidate ? candidate : baseline
  yield* requireEqual(input.selection.selectedBranch, selectedBranch, "selected branch does not match decision")
  const before = yield* readLlmSemanticFrame(input.baseline.runtime, baseline.relationUid, input.trainingTrace.event)
  const after = yield* readLlmSemanticFrame(input.candidate.runtime, candidate.relationUid, input.trainingTrace.event)
  const next = yield* readLlmSemanticFrame(input.selectedRuntime, selectedBranch.relationUid, input.nextTrace.event)
  const train = yield* boundExecution(input.candidate.runtime, input.trainingTrace, before)
  const outcome = yield* readArtifact(input.candidate.runtime, input.trainingOutcome.outcomeContent, storedOutcome, "application/vnd.hswm.llm-semantic-outcome-v1+json")
  yield* requireEqual(outcome, { contract: "hswm-llm-semantic-outcome/v1", traceSha256: input.trainingOutcome.traceSha256,
    predictionSha256: input.trainingOutcome.predictionSha256, observed: input.trainingOutcome.observed,
    source: input.trainingOutcome.source, status: input.trainingOutcome.status }, "outcome report differs from durable bytes")
  const evidenceRef = after.relation.semantic.revisionEvidence
  if (evidenceRef === undefined) return yield* Effect.fail(fail("candidate has no revision evidence"))
  const evidence = yield* readArtifact(input.candidate.runtime, evidenceRef, revisionEvidence, "application/vnd.hswm.llm-semantic-revision-v1+json")
  yield* requireEqual(evidence.trace, input.trainingTrace.traceContent, "revision refers to another trace")
  yield* requireEqual(evidence.outcome, input.trainingOutcome.outcomeContent, "revision refers to another outcome")
  const request = yield* readArtifact(input.candidate.runtime, evidence.request, revisionRequest, "application/vnd.hswm.llm-semantic-request-v1+json")
  const response = yield* readArtifact(input.candidate.runtime, evidence.response, revisionResponse, "application/vnd.hswm.llm-semantic-response-v1+json")
  yield* requireEqual(request.frame, before, "revision request uses another read frame")
  yield* requireEqual(request.trace, train, "revision request uses another prediction")
  yield* requireEqual(request.outcome, outcome, "revision request uses another outcome")
  yield* boundExecution(input.selectedRuntime, input.nextTrace, next)
  const snapshot = yield* input.candidate.runtime.snapshot
  const priorAtom = snapshot.canonical.atoms.find(atom => canonicalAtomV2KeyId(atom.key) === canonicalAtomV2KeyId(before.relation.key))
  const nextAtom = snapshot.canonical.atoms.find(atom => canonicalAtomV2KeyId(atom.key) === canonicalAtomV2KeyId(after.relation.key))
  if (priorAtom === undefined || nextAtom === undefined) return yield* Effect.fail(fail("candidate history or current atom is missing"))
  const retainedSemantic = yield* readArtifact(input.candidate.runtime, priorAtom.content, semantic, "application/vnd.hswm.llm-semantic-relation-v1+json")
  const checkRoles = (atom: CanonicalAtomV2, expected: SemanticReadFrame) => requireEqual(
    atom.references.filter(ref => ref.referenceType !== HSWM_SUPERSEDES_REFERENCE_TYPE),
    expected.roles.map(value => ({ referenceType: value.referenceType, role: value.role, target: value.key })), "durable role references changed")
  yield* checkRoles(priorAtom, before)
  yield* checkRoles(nextAtom, after)
  const predecessors = nextAtom.references.filter(ref => ref.referenceType === HSWM_SUPERSEDES_REFERENCE_TYPE)
  const predecessor = predecessors[0]
  if (predecessors.length !== 1 || predecessor?.role !== HSWM_SUPERSEDES_REFERENCE_ROLE) return yield* Effect.fail(fail("candidate must have one typed predecessor"))
  yield* requireEqual(nextAtom.provenance, { mode: "DERIVATION", evidenceSha256: input.trainingOutcome.outcomeContent.sha256, sourceRef: before.relation.key }, "successor provenance changed")
  const wire = Object.freeze({ contract: "hswm-semantic-lifecycle-postrun/v1" as const,
    before: { stateRevision: before.stateRevision, relation: normalizedRelation(before) }, frame: normalizedFrame(before),
    trace: normalizedTrace(input.trainingTrace),
    outcome: { traceSha256: outcome.traceSha256, predictionSha256: outcome.predictionSha256,
      outcomeSha256: input.trainingOutcome.outcomeContent.sha256, status: outcome.status },
    revision: { ...response, revisionEvidenceSha256: evidenceRef.sha256, traceSha256: evidence.trace.sha256,
      outcomeSha256: evidence.outcome.sha256, backendConfigurationSha256: evidence.backendConfigurationSha256 },
    after: { stateRevision: after.stateRevision, relation: normalizedRelation(after) }, afterPredecessorKey: predecessor.target,
    retainedBefore: { key: priorAtom.key, owner: priorAtom.responsibilityOwner, semantic: normalizedSemantic(retainedSemantic), roles: normalizedRoles(before.roles) },
    selectedCandidate, nextFrame: normalizedFrame(next), nextTrace: normalizedTrace(input.nextTrace)
  })
  yield* requireEqual(yield* deriveSemanticDurableBranch(input.baseline), baseline, "baseline drifted during audit")
  yield* requireEqual(yield* deriveSemanticDurableBranch(input.candidate), candidate, "candidate drifted during audit")
  const reopened = yield* deriveSemanticDurableBranch({ root: selectedBranch.root, relationUid: selectedBranch.relationUid, runtime: input.selectedRuntime })
  yield* requireEqual(reopened, selectedBranch, "selected runtime differs from selected durable state")
  return wire
})
