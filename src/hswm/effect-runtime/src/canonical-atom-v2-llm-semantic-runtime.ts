/**
 * A bounded vertical slice in which an LLM reads canonical, role-bearing
 * relation content and proposes a later relation revision.  The LLM has no
 * write capability: the supplied durable runtime remains the only mutation
 * path.  This is a local construction, not a claim of causal credit or LLM
 * semantic correctness.
 */
import { createHash, randomUUID } from "node:crypto"
import { Data, Effect, Either } from "effect"

import { AdaptiveHttpClient, executeAdaptiveCell, type AdaptiveHttpClientShape } from "./adaptive-executor.js"
import { canonicalJson, parseJson } from "./adaptive-domain.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput, type CanonicalAtomV2WriteContentBinding, type CommitCanonicalAtomsV2ContentBound } from "./canonical-atom-v2-content-bound.js"
import { type CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2KeyId, HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, HSWM_SUPERSEDES_REFERENCE_ROLE, HSWM_SUPERSEDES_REFERENCE_TYPE, type CanonicalAtomV2, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"

export const HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE = "application/vnd.hswm.llm-semantic-relation-v1+json" as const
export const HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE = "application/vnd.hswm.llm-semantic-trace-v1+json" as const
export const HSWM_LLM_SEMANTIC_OUTCOME_MEDIA_TYPE = "application/vnd.hswm.llm-semantic-outcome-v1+json" as const

export class LlmSemanticRuntimeError extends Data.TaggedError("LlmSemanticRuntimeError")<{
  readonly code: "CONTENT_INVALID" | "FRAME_STALE" | "LLM_OUTPUT_INVALID" | "OUTCOME_INVALID" | "RELATION_MISSING" | "ROLE_INVALID"
  readonly detail: string
}> {}

const fail = (code: LlmSemanticRuntimeError["code"], detail: string) => new LlmSemanticRuntimeError({ code, detail })
const sha = (value: Uint8Array | string): string => createHash("sha256").update(value).digest("hex")
const bytes = (value: unknown): Uint8Array => new TextEncoder().encode(JSON.stringify(value))
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 8192
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value)
const sameKey = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key): boolean => canonicalAtomV2KeyId(a) === canonicalAtomV2KeyId(b)
type ContentDescriptor = CanonicalAtomV2["content"]
const outcomeStatus = "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED" as const
const snapshotInput = <A>(value: A): Either.Either<A, LlmSemanticRuntimeError> =>
  canonicalJson(value).pipe(
    Either.flatMap(parseJson),
    Either.map((copy) => copy as A),
    Either.mapLeft(() => fail("CONTENT_INVALID", "input must be bounded JSON data"))
  )
const utf8 = (raw: Uint8Array): Either.Either<string, LlmSemanticRuntimeError> =>
  Either.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(raw), catch: () => fail("CONTENT_INVALID", "content must be valid UTF-8") })
const strictJson = (raw: string): Either.Either<unknown, LlmSemanticRuntimeError> =>
  parseJson(raw).pipe(Either.mapLeft(() => fail("CONTENT_INVALID", "invalid or duplicate-key JSON")))
const descriptor = (value: unknown, mediaType: string): value is ContentDescriptor =>
  record(value) && value["mediaType"] === mediaType &&
  typeof value["sha256"] === "string" && /^[0-9a-f]{64}$/.test(value["sha256"]) &&
  typeof value["byteLength"] === "number" && Number.isSafeInteger(value["byteLength"]) &&
  value["byteLength"] > 0 && value["byteLength"] <= 1_048_576

const readRecord = (runtime: CanonicalAtomV2DurableRuntime["Type"], content: ContentDescriptor, mediaType: string) => Effect.gen(function* () {
  if (!descriptor(content, mediaType)) return yield* Effect.fail(fail("CONTENT_INVALID", "invalid content descriptor"))
  const raw = yield* runtime.readContent(content)
  if (raw.byteLength !== content.byteLength || sha(raw) !== content.sha256) return yield* Effect.fail(fail("CONTENT_INVALID", "content bytes do not match descriptor"))
  const value = yield* utf8(raw).pipe(Either.flatMap(strictJson))
  if (!record(value)) return yield* Effect.fail(fail("CONTENT_INVALID", "record must be a JSON object"))
  return value
})

export interface SemanticRelationContent {
  readonly semanticText: string
  readonly disposition: string
  readonly uncertainty: string
  /** These exact role reference IDs must survive a semantic revision. */
  readonly exceptionRefs: ReadonlyArray<string>
  readonly trace: ContentDescriptor | null
  readonly outcome: (ContentDescriptor & { readonly status: typeof outcomeStatus }) | null
  readonly revisionEvidence?: ContentDescriptor
}

export interface SemanticReadFrame {
  readonly event: string
  readonly stateRevision: number
  readonly relation: { readonly key: CanonicalAtomV2Key; readonly owner: string; readonly semantic: SemanticRelationContent }
  /** References are exact pinned revisions, never silently refreshed to heads. */
  readonly roles: ReadonlyArray<{ readonly referenceType: string; readonly role: string; readonly key: CanonicalAtomV2Key; readonly owner: string; readonly contentSha256: string; readonly contentUtf8: string }>
  readonly priorEvidence: { readonly prediction: string; readonly uncertainty: string; readonly observed: string; readonly source: string; readonly status: typeof outcomeStatus } | null
  readonly frameSha256: string
}

export interface SemanticTrace {
  readonly executionId: string
  readonly traceSha256: string
  readonly traceContent: { readonly sha256: string; readonly mediaType: string; readonly byteLength: number }
  readonly frameSha256: string
  readonly event: string
  readonly relationKey: CanonicalAtomV2Key
  readonly prediction: string
  readonly predictionSha256: string
  readonly uncertainty: string
  readonly backendConfigurationSha256: string
}

export interface SemanticOutcome {
  readonly traceSha256: string
  readonly predictionSha256: string
  readonly observed: string
  readonly source: string
  readonly outcomeContent: { readonly sha256: string; readonly mediaType: string; readonly byteLength: number }
  readonly status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"
}

/** A fully content-bound candidate. It has no authority to mutate durable state. */
export interface LlmSemanticRevisionProposal {
  readonly candidate: CommitCanonicalAtomsV2ContentBound
  readonly affectedKeys: ReadonlyArray<CanonicalAtomV2Key>
  readonly revisionEvidence: ContentDescriptor
  readonly trace: SemanticTrace
  readonly outcome: SemanticOutcome
}

/** Explicit capability supplied by an authorized admission owner. */
export interface LlmSemanticRevisionAdmission<R = never, E = never, A = unknown> {
  readonly admit: (proposal: LlmSemanticRevisionProposal) => Effect.Effect<A, E, R>
}

export interface LlmSemanticCell {
  readonly base_url: string
  readonly model: string
  readonly api_key_env?: string
  readonly max_tokens: number
}

const parseSemantic = (raw: Uint8Array): Either.Either<SemanticRelationContent, LlmSemanticRuntimeError> => {
  return Either.gen(function* () {
    const value = yield* utf8(raw).pipe(Either.flatMap(strictJson))
    if (!record(value) || Object.keys(value).filter((key) => key !== "revisionEvidence").sort().join(",") !== "disposition,exceptionRefs,outcome,semanticText,trace,uncertainty" || !text(value["semanticText"]) || !text(value["disposition"]) || !text(value["uncertainty"]) || !Array.isArray(value["exceptionRefs"]) || !value["exceptionRefs"].every(text) || new Set(value["exceptionRefs"]).size !== value["exceptionRefs"].length) return yield* Either.left(fail("CONTENT_INVALID", "semantic relation payload has an invalid or incomplete shape"))
    const trace = value["trace"], outcome = value["outcome"], revisionEvidence = value["revisionEvidence"]
    if ((trace !== null && !descriptor(trace, HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE)) ||
      (outcome !== null && (!descriptor(outcome, HSWM_LLM_SEMANTIC_OUTCOME_MEDIA_TYPE) || !record(outcome) || outcome["status"] !== outcomeStatus)) ||
      (trace === null) !== (outcome === null) ||
      (revisionEvidence !== undefined && !descriptor(revisionEvidence, "application/vnd.hswm.llm-semantic-revision-v1+json"))) return yield* Either.left(fail("CONTENT_INVALID", "semantic relation descriptor is malformed"))
    return Object.freeze({ semanticText: value["semanticText"], disposition: value["disposition"], uncertainty: value["uncertainty"], exceptionRefs: Object.freeze([...value["exceptionRefs"]]), trace, outcome: outcome as SemanticRelationContent["outcome"], ...(revisionEvidence === undefined ? {} : { revisionEvidence }) })
  })
}

/** Reads selected exact references, and refuses dangling/missing required roles. */
export const readLlmSemanticFrame = (runtime: CanonicalAtomV2DurableRuntime["Type"], relationUid: string, event = "unspecified") => Effect.gen(function* () {
  if (!text(event)) return yield* Effect.fail(fail("CONTENT_INVALID", "an execution event is required"))
  const state = yield* runtime.snapshot
  const matching = state.canonical.atoms.filter((atom) => atom.key.atomUid === relationUid)
  if (new Set(matching.map((atom) => JSON.stringify([atom.key.schemaVersion, atom.key.lineageId]))).size > 1) return yield* Effect.fail(fail("RELATION_MISSING", "relation UID is ambiguous across schema/lineage; use a scoped runtime"))
  const current = matching.reduce<CanonicalAtomV2 | undefined>((prior, atom) =>
    prior === undefined || atom.key.revisionId > prior.key.revisionId ? atom : prior, undefined)
  if (current === undefined) return yield* Effect.fail(fail("RELATION_MISSING", `no current relation ${relationUid}`))
  if (current.kind !== "semantic_relation") return yield* Effect.fail(fail("RELATION_MISSING", "target is not a semantic_relation"))
  const semanticBytes = yield* runtime.readContent(current.content)
  if (semanticBytes.byteLength > 65_536 || semanticBytes.byteLength !== current.content.byteLength || sha(semanticBytes) !== current.content.sha256 || current.content.mediaType !== HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE) return yield* Effect.fail(fail("CONTENT_INVALID", "semantic relation bytes exceed bound or mismatch descriptor"))
  const semantic = parseSemantic(semanticBytes)
  if (Either.isLeft(semantic)) return yield* Effect.fail(semantic.left)
  const exact: ReadonlyMap<string, CanonicalAtomV2> = new Map(state.canonical.atoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom]))
  const roles = yield* Effect.forEach(
    current.references.filter((reference) => reference.referenceType !== HSWM_SUPERSEDES_REFERENCE_TYPE),
    (reference) => Effect.gen(function* () {
      const target = exact.get(canonicalAtomV2KeyId(reference.target))
      if (target === undefined) return yield* Effect.fail(fail("ROLE_INVALID", `pinned role target is absent: ${reference.role}`))
      const targetBytes = yield* runtime.readContent(target.content)
      if (targetBytes.byteLength !== target.content.byteLength || sha(targetBytes) !== target.content.sha256 || targetBytes.byteLength > 65_536) return yield* Effect.fail(fail("ROLE_INVALID", `role content is absent, mismatched, or exceeds bound: ${reference.role}`))
      const contentUtf8 = yield* utf8(targetBytes)
      return Object.freeze({ referenceType: reference.referenceType, role: reference.role, key: target.key, owner: target.responsibilityOwner, contentSha256: target.content.sha256, contentUtf8 })
    })
  )
  if (!roles.some((role) => role.role === "subject") || !roles.some((role) => role.role === "context") || !roles.some((role) => role.role === "evidence")) return yield* Effect.fail(fail("ROLE_INVALID", "subject, context, and evidence roles are all required"))
  const exceptionTargets = new Set(roles.filter((role) => role.role === "exception").map((role) => role.key.atomUid))
  if (semantic.right.exceptionRefs.some((reference) => !exceptionTargets.has(reference))) return yield* Effect.fail(fail("ROLE_INVALID", "every exception reference must name an exact exception-role atom"))
  const priorEvidence = yield* Effect.gen(function* () {
    if (semantic.right.trace === null || semantic.right.outcome === null) return null
    const trace = yield* readRecord(runtime, semantic.right.trace, HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE)
    const outcome = yield* readRecord(runtime, semantic.right.outcome, HSWM_LLM_SEMANTIC_OUTCOME_MEDIA_TYPE)
    if (trace["contract"] !== "hswm-llm-semantic-trace/v1" || outcome["contract"] !== "hswm-llm-semantic-outcome/v1" || outcome["traceSha256"] !== semantic.right.trace.sha256 || outcome["predictionSha256"] !== trace["predictionSha256"] || outcome["status"] !== outcomeStatus || !text(trace["prediction"]) || !text(trace["uncertainty"]) || !text(outcome["observed"]) || !text(outcome["source"]) || sha(trace["prediction"]) !== trace["predictionSha256"]) return yield* Effect.fail(fail("CONTENT_INVALID", "prior observation and prediction are not bound"))
    return { prediction: trace["prediction"], uncertainty: trace["uncertainty"], observed: outcome["observed"], source: outcome["source"], status: outcomeStatus }
  })
  const bare = { event, stateRevision: state.canonical.revision, relation: { key: current.key, owner: current.responsibilityOwner, semantic: semantic.right }, roles: Object.freeze(roles), priorEvidence }
  if (bytes(bare).byteLength > 524_288) return yield* Effect.fail(fail("CONTENT_INVALID", "semantic frame exceeds total bound"))
  return Object.freeze({ ...bare, frameSha256: sha(bytes(bare)) }) satisfies SemanticReadFrame
})

const strictPrediction = (raw: string): Either.Either<{ prediction: string; uncertainty: string }, LlmSemanticRuntimeError> => {
  const parsed = strictJson(raw)
  if (Either.isLeft(parsed)) return Either.left(fail("LLM_OUTPUT_INVALID", parsed.left.detail))
  const value = parsed.right
  return record(value) && Object.keys(value).sort().join(",") === "prediction,uncertainty" && text(value["prediction"]) && text(value["uncertainty"])
    ? Either.right({ prediction: value["prediction"], uncertainty: value["uncertainty"] })
    : Either.left(fail("LLM_OUTPUT_INVALID", "prediction must contain exactly prediction and uncertainty"))
}
const strictRevision = (raw: string, prior: SemanticRelationContent): Either.Either<Pick<SemanticRelationContent, "semanticText" | "disposition" | "uncertainty" | "exceptionRefs">, LlmSemanticRuntimeError> => {
  const parsed = strictJson(raw)
  if (Either.isLeft(parsed)) return Either.left(fail("LLM_OUTPUT_INVALID", parsed.left.detail))
  const value = parsed.right
  if (!record(value) || Object.keys(value).sort().join(",") !== "disposition,exceptionRefs,semanticText,uncertainty" || !text(value["semanticText"]) || !text(value["disposition"]) || !text(value["uncertainty"]) || !Array.isArray(value["exceptionRefs"]) || !value["exceptionRefs"].every(text) || JSON.stringify(value["exceptionRefs"]) !== JSON.stringify(prior.exceptionRefs)) return Either.left(fail("LLM_OUTPUT_INVALID", "revision must preserve every exception reference exactly"))
  return Either.right({ semanticText: value["semanticText"], disposition: value["disposition"], uncertainty: value["uncertainty"], exceptionRefs: Object.freeze([...value["exceptionRefs"]]) })
}

const invoke = (cell: LlmSemanticCell, prompt: unknown, http: AdaptiveHttpClientShape) => executeAdaptiveCell({ kind: "llm", cell_id: "semantic-engine", ...cell }, { prompt: JSON.stringify(prompt) }, process.cwd(), 120_000).pipe(Effect.provideService(AdaptiveHttpClient, http), Effect.flatMap((result) => result.status === "SUCCEEDED" ? Effect.succeed(result.output) : Effect.fail(fail("LLM_OUTPUT_INVALID", "LLM transport did not return a completed response"))))

export const executeLlmSemanticRelation = (runtime: CanonicalAtomV2DurableRuntime["Type"], relationUid: string, event: string, cellInput: LlmSemanticCell, http: AdaptiveHttpClientShape) => Effect.gen(function* () {
  const cell = yield* snapshotInput(cellInput)
  const executionId = yield* Effect.sync(randomUUID)
  const frame = yield* readLlmSemanticFrame(runtime, relationUid, event)
  const request = { contract: "hswm-llm-semantic-predict/v1", executionId, frame, requiredOutput: { prediction: "string", uncertainty: "string" } }
  const requestContent = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-request-v1+json", bytes(request))
  const output = yield* invoke(cell, request, http)
  const prediction = strictPrediction(output); if (Either.isLeft(prediction)) return yield* Effect.fail(prediction.left)
  const responseContent = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-response-v1+json", new TextEncoder().encode(output))
  const backendConfigurationSha256 = sha(bytes({ baseUrl: cell.base_url, model: cell.model, apiKeyEnvironment: cell.api_key_env ?? null, maxTokens: cell.max_tokens }))
  const tracePayload = { contract: "hswm-llm-semantic-trace/v1", executionId, frameSha256: frame.frameSha256, event: frame.event, relationKey: frame.relation.key, prediction: prediction.right.prediction, predictionSha256: sha(prediction.right.prediction), uncertainty: prediction.right.uncertainty, request: requestContent, response: responseContent, backendConfigurationSha256 }
  const staged = yield* runtime.stageContent(HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE, bytes(tracePayload))
  return Object.freeze({ executionId, traceSha256: staged.sha256, traceContent: { sha256: staged.sha256, mediaType: staged.mediaType, byteLength: staged.byteLength }, frameSha256: frame.frameSha256, event: frame.event, relationKey: frame.relation.key, prediction: prediction.right.prediction, predictionSha256: tracePayload.predictionSha256, uncertainty: prediction.right.uncertainty, backendConfigurationSha256 }) satisfies SemanticTrace
})

export const stageLlmSemanticOutcome = (runtime: CanonicalAtomV2DurableRuntime["Type"], traceInput: SemanticTrace, observed: string, source: string) => Effect.gen(function* () {
  const trace = yield* snapshotInput(traceInput)
  if (!text(observed) || !text(source)) return yield* Effect.fail(fail("OUTCOME_INVALID", "outcome and source are required"))
  const payload = { contract: "hswm-llm-semantic-outcome/v1", traceSha256: trace.traceSha256, predictionSha256: trace.predictionSha256, observed, source, status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED" as const }
  const staged = yield* runtime.stageContent(HSWM_LLM_SEMANTIC_OUTCOME_MEDIA_TYPE, bytes(payload))
  return Object.freeze({ traceSha256: trace.traceSha256, predictionSha256: trace.predictionSha256, observed, source, outcomeContent: { sha256: staged.sha256, mediaType: staged.mediaType, byteLength: staged.byteLength }, status: payload.status }) satisfies SemanticOutcome
})

/** Rechecks pinned reads after the remote call and prepares one content-bound successor for admission. */
export const prepareLlmSemanticRelationRevision = (runtime: CanonicalAtomV2DurableRuntime["Type"], traceInput: SemanticTrace, outcomeInput: SemanticOutcome, cellInput: LlmSemanticCell, http: AdaptiveHttpClientShape, authorizationRef: string, scope: string, decidedAt: string) => Effect.gen(function* () {
  const trace = yield* snapshotInput(traceInput)
  const outcome = yield* snapshotInput(outcomeInput)
  const cell = yield* snapshotInput(cellInput)
  if (trace.traceSha256 !== outcome.traceSha256 || trace.predictionSha256 !== outcome.predictionSha256) return yield* Effect.fail(fail("OUTCOME_INVALID", "outcome does not bind the exact trace and prediction"))
  const backendConfigurationSha256 = sha(bytes({ baseUrl: cell.base_url, model: cell.model, apiKeyEnvironment: cell.api_key_env ?? null, maxTokens: cell.max_tokens }))
  if (trace.backendConfigurationSha256 !== backendConfigurationSha256) return yield* Effect.fail(fail("FRAME_STALE", "learning must use the declared execution backend configuration"))
  if (trace.traceSha256 !== trace.traceContent.sha256 || outcome.status !== outcomeStatus) return yield* Effect.fail(fail("OUTCOME_INVALID", "receipt descriptor or observation status mismatch"))
  const traceRecord = yield* readRecord(runtime, trace.traceContent, HSWM_LLM_SEMANTIC_TRACE_MEDIA_TYPE)
  const outcomeRecord = yield* readRecord(runtime, outcome.outcomeContent, HSWM_LLM_SEMANTIC_OUTCOME_MEDIA_TYPE)
  const relationKey = canonicalJson(traceRecord["relationKey"])
  const expectedKey = canonicalJson(trace.relationKey)
  if (traceRecord["contract"] !== "hswm-llm-semantic-trace/v1" ||
    traceRecord["executionId"] !== trace.executionId || !text(trace.executionId) ||
    traceRecord["frameSha256"] !== trace.frameSha256 || traceRecord["event"] !== trace.event ||
    traceRecord["predictionSha256"] !== trace.predictionSha256 || traceRecord["prediction"] !== trace.prediction ||
    traceRecord["uncertainty"] !== trace.uncertainty || traceRecord["backendConfigurationSha256"] !== backendConfigurationSha256 ||
    !text(trace.prediction) || !text(trace.uncertainty) || sha(trace.prediction) !== trace.predictionSha256 ||
    Either.isLeft(relationKey) || Either.isLeft(expectedKey) || relationKey.right !== expectedKey.right ||
    outcomeRecord["contract"] !== "hswm-llm-semantic-outcome/v1" || outcomeRecord["traceSha256"] !== trace.traceSha256 ||
    outcomeRecord["predictionSha256"] !== trace.predictionSha256 || outcomeRecord["observed"] !== outcome.observed ||
    outcomeRecord["source"] !== outcome.source || outcomeRecord["status"] !== outcomeStatus || !text(outcome.observed) || !text(outcome.source)) {
    return yield* Effect.fail(fail("OUTCOME_INVALID", "caller receipts differ from their durably recorded prediction, observation or backend"))
  }
  const frame = yield* readLlmSemanticFrame(runtime, trace.relationKey.atomUid, trace.event)
  if (!sameKey(frame.relation.key, trace.relationKey)) return yield* Effect.fail(fail("FRAME_STALE", "relation revision changed after prediction"))
  if (frame.frameSha256 !== trace.frameSha256) return yield* Effect.fail(fail("FRAME_STALE", "one pinned participant or semantic read changed after prediction"))
  const request = { contract: "hswm-llm-semantic-learn/v1", frame, trace: traceRecord, outcome: outcomeRecord, requiredOutput: { semanticText: "string", disposition: "string", uncertainty: "string", exceptionRefs: "exact-input-array" } }
  const requestContent = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-request-v1+json", bytes(request))
  const output = yield* invoke(cell, request, http)
  const proposed = strictRevision(output, frame.relation.semantic); if (Either.isLeft(proposed)) return yield* Effect.fail(proposed.left)
  const afterCall = yield* readLlmSemanticFrame(runtime, trace.relationKey.atomUid, trace.event)
  if (!sameKey(afterCall.relation.key, trace.relationKey) || afterCall.frameSha256 !== trace.frameSha256) return yield* Effect.fail(fail("FRAME_STALE", "relation or a pinned role changed while the revision call was pending"))
  const current = yield* runtime.snapshot
  if (current.canonical.revision !== afterCall.stateRevision) return yield* Effect.fail(fail("FRAME_STALE", "durable state changed after the final read-frame snapshot"))
  const nextKey = { ...frame.relation.key, revisionId: frame.relation.key.revisionId + 1 }
  const responseContent = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-response-v1+json", new TextEncoder().encode(output))
  const revisionEvidence = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-revision-v1+json", bytes({ request: requestContent, response: responseContent, trace: trace.traceContent, outcome: outcome.outcomeContent, backendConfigurationSha256 }))
  const payload = Object.freeze({ ...proposed.right, trace: trace.traceContent, outcome: { ...outcome.outcomeContent, status: outcome.status }, revisionEvidence })
  const nextFrame = { event: frame.event, stateRevision: afterCall.stateRevision + 1, relation: { key: nextKey, owner: frame.relation.owner, semantic: payload }, roles: frame.roles, priorEvidence: { prediction: trace.prediction, uncertainty: trace.uncertainty, observed: outcome.observed, source: outcome.source, status: outcomeStatus } }
  if (bytes(payload).byteLength > 65_536 || bytes(nextFrame).byteLength > 524_288) return yield* Effect.fail(fail("CONTENT_INVALID", "revised relation would exceed the next read frame bounds"))
  const content = yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, bytes(payload))
  const atom: CanonicalAtomV2 = Object.freeze({ _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: nextKey, kind: "semantic_relation", responsibilityOwner: frame.relation.owner, content, provenance: { mode: "DERIVATION" as const, evidenceSha256: outcome.outcomeContent.sha256, sourceRef: frame.relation.key }, lifecycle: "ADMITTED", references: Object.freeze([{ referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, role: HSWM_SUPERSEDES_REFERENCE_ROLE, target: frame.relation.key }, ...frame.roles.map((role) => ({ referenceType: role.referenceType, role: role.role, target: role.key }))]) })
  const envelope = describeCanonicalAtomV2Envelope(atom); if (Either.isLeft(envelope)) return yield* Effect.fail(fail("CONTENT_INVALID", "cannot bind semantic successor envelope"))
  const binding: CanonicalAtomV2WriteContentBinding = { key: atom.key, payload: content, envelope: envelope.right }
  const command = { _tag: "CommitCanonicalAtomsV2" as const, contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: `semantic-learn:${trace.traceSha256}`, expectedStateRevision: afterCall.stateRevision, schemaVersion: frame.relation.key.schemaVersion, actorClaim: "llm:semantic-engine", authorizationRef, scope, decidedAt, traceRef: null, readSet: [frame.relation.key, ...frame.roles.map((role) => role.key)], writes: [atom], provenanceSha256: outcome.outcomeContent.sha256 }
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, command, [binding])
  return Object.freeze({
    candidate,
    affectedKeys: Object.freeze([frame.relation.key, ...frame.roles.map((role) => role.key)]),
    revisionEvidence,
    trace,
    outcome
  }) satisfies LlmSemanticRevisionProposal
})

/**
 * Performs semantic proposal construction, then delegates the actual mutation
 * to an explicitly supplied admission owner. This module never submits a
 * durable mutation itself.
 */
export const learnLlmSemanticRelation = <R, E, A>(runtime: CanonicalAtomV2DurableRuntime["Type"], traceInput: SemanticTrace, outcomeInput: SemanticOutcome, cellInput: LlmSemanticCell, http: AdaptiveHttpClientShape, authorizationRef: string, scope: string, decidedAt: string, admission: LlmSemanticRevisionAdmission<R, E, A>) =>
  prepareLlmSemanticRelationRevision(runtime, traceInput, outcomeInput, cellInput, http, authorizationRef, scope, decidedAt).pipe(
    Effect.flatMap((proposal) => admission.admit(proposal))
  )
