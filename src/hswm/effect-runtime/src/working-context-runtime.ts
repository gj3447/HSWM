/** Logical task HSWMs and shared activation policies, using the existing native journal/owner loop. */
import { Effect, Schema } from "effect"
import { parseJson } from "./adaptive-domain.js"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput, type CommitCanonicalAtomsV2ContentBound } from "./canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { contextHash, contextJson, type ContextPlan } from "./semantic-context-domain.js"
import { prepareSemanticContext, stageSemanticContextOutcome } from "./semantic-context-runtime.js"
import { activationScopeHash, chooseActivation, type ActivationFeatures } from "./semantic-context-activation-domain.js"
import { decodeLifecycleCell } from "./semantic-lifecycle-domain.js"
import { ActivationTargetSchema, prepareActivationInitialization, readActivationPolicy } from "./semantic-context-activation-runtime.js"
import { executeActivationLoop, type ActivationLoopPorts, type ActivationProposal } from "./semantic-context-loop-runtime.js"
import { ContextPresentationSchema } from "./semantic-context-presentation-domain.js"
import { FiniteExecutionGuardSchema } from "./semantic-context-finite-execution-domain.js"
import { WORKING_CONTEXT_KIND, WORKING_CONTEXT_MEDIA, WorkingContextInputSchema, WorkingContextSchema, WorkingMemorySchema,
  decodeWorking, latestWorkingAtom, reopenWorkingGaps, sameWorkingKey, workingChanges, workingDependencies, workingError,
  workingReferences, workingSpec, type WorkingContext, type WorkingRun } from "./working-context-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
type Target = typeof ActivationTargetSchema.Type
export interface WorkingContextProposal {
  readonly candidate: CommitCanonicalAtomsV2ContentBound
  readonly contextKey: CanonicalAtomV2Key
  readonly context: WorkingContext
  readonly canonicalWrite: false
}
export interface WorkingContextPorts<E, R> extends Omit<ActivationLoopPorts<E, R>, "admit"> {
  readonly admit: (proposal: WorkingContextProposal) => Effect.Effect<unknown, E, R>
}
const encode = (value: unknown) => new TextEncoder().encode(contextJson(value))
const nextTarget = (key: CanonicalAtomV2Key, writer: Omit<Target, "key">): Target => ({ ...writer, key: { ...key, revisionId: key.revisionId + 1 } })
const readPayload = (runtime: Runtime, atom: CanonicalAtomV2) => Effect.gen(function* () {
  if (atom.kind !== WORKING_CONTEXT_KIND || atom.lifecycle !== "ADMITTED" || atom.content.mediaType !== WORKING_CONTEXT_MEDIA || atom.content.byteLength > 262144)
    return yield* Effect.fail(workingError("INVALID", "Expected a bounded admitted working-context atom"))
  const context = yield* decodeWorking(WorkingContextSchema, yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(atom.content))))
  const prior = atom.references.find(r => r.referenceType === "hswm:reference:supersedes")?.target ?? null
  if (contextHash(atom.references) !== contextHash(workingReferences(context, prior)))
    return yield* Effect.fail(workingError("BINDING_INVALID", "Stored dependencies and policy differ from graph references"))
  return context
})

/** Read an exact current context. Old versions remain in the journal, never silently substituted. */
export const readWorkingContext = (runtime: Runtime, rawKey: unknown) => Effect.gen(function* () {
  const key = yield* decodeWorking(CanonicalAtomV2KeySchema, rawKey)
  const snapshot = yield* runtime.snapshot
  const atom = latestWorkingAtom(snapshot.canonical.atoms, key)
  if (!atom || !sameWorkingKey(atom.key, key)) return yield* Effect.fail(workingError("REVISION_STALE", "Use the exact current working-context revision"))
  const context = yield* readPayload(runtime, atom)
  const changes = workingChanges(context.dependencies, snapshot.canonical.atoms)
  const policy = latestWorkingAtom(snapshot.canonical.atoms, context.policyKey)
  return { atom, context, changes, status: changes.length ? "STALE" as const : "CURRENT" as const,
    policyAdvanced: policy !== undefined && !sameWorkingKey(policy.key, context.policyKey) }
})

/** Explicit recovery by stable identity. The returned revision pins subsequent operations. */
export const openWorkingContext = (runtime: Runtime, rawIdentity: unknown) => Effect.gen(function* () {
  const identity = yield* decodeWorking(CanonicalAtomV2KeySchema, rawIdentity)
  const latest = latestWorkingAtom((yield* runtime.snapshot).canonical.atoms, identity)
  if (!latest) return yield* Effect.fail(workingError("MISSING", "Working-context identity is absent"))
  return yield* readWorkingContext(runtime, latest.key)
})

const planFor = (runtime: Runtime, input: typeof WorkingContextInputSchema.Type) => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, yield* workingSpec(input))
  const dependencies = workingDependencies(plan)
  if (workingChanges(dependencies, (yield* runtime.snapshot).canonical.atoms).length)
    return yield* Effect.fail(workingError("SOURCE_REBIND_REQUIRED", "A source relation still points to a superseded participant; its owner must rebind it"))
  for (const gap of input.memory.gaps) {
    if (gap.status === "RESOLVED" && (gap.evidence.length === 0 || gap.evidence.some(key => !dependencies.some(d => sameWorkingKey(d.key, key)))))
      return yield* Effect.fail(workingError("GAP_EVIDENCE_INVALID", "Resolved gaps need exact evidence in this working context"))
  }
  return plan
})
const policyFor = (runtime: Runtime, plan: ContextPlan, input: typeof WorkingContextInputSchema.Type, writer: Target) => Effect.gen(function* () {
  const key = { schemaVersion: writer.key.schemaVersion, lineageId: input.policyFamily.lineageId,
    atomUid: `working-policy:${contextHash({ family: input.policyFamily.atomUid, owner: writer.owner, config: input.policyFamily.config, scope: activationScopeHash(plan) })}`, revisionId: 0 }
  const existing = latestWorkingAtom((yield* runtime.snapshot).canonical.atoms, key)
  if (existing) {
    const checked = yield* readActivationPolicy(runtime, plan, existing.key)
    if (checked.atom.responsibilityOwner !== writer.owner || contextHash(checked.policy.config) !== contextHash(input.policyFamily.config))
      return yield* Effect.fail(workingError("POLICY_INVALID", "Policy owner or encoder differs from the declared family"))
    return { key: existing.key, proposal: null }
  }
  const proposal = yield* prepareActivationInitialization(runtime, plan, input.policyFamily.config, { ...writer, key })
  return { key, proposal }
})

/** Atom and optional policy successor are admitted atomically by the caller's existing owner. */
const prepareWrite = (runtime: Runtime, rawContext: WorkingContext, rawTarget: unknown,
  prior: CanonicalAtomV2 | null, policyProposal: { readonly candidate: CommitCanonicalAtomsV2ContentBound } | null = null, reconciliation = false) => Effect.gen(function* () {
  const context = yield* decodeWorking(WorkingContextSchema, rawContext)
  const target = yield* decodeWorking(ActivationTargetSchema, rawTarget)
  const snapshot = yield* runtime.snapshot
  const latest = latestWorkingAtom(snapshot.canonical.atoms, target.key)
  if (target.key.schemaVersion !== runtime.schema.schemaVersion || (prior === null
    ? latest !== undefined || target.key.revisionId !== 0
    : !latest || !sameWorkingKey(latest.key, prior.key) || prior.responsibilityOwner !== target.owner ||
      !sameWorkingKey(target.key, { ...prior.key, revisionId: prior.key.revisionId + 1 })))
    return yield* Effect.fail(workingError("REVISION_STALE", "Create once or append one revision under the same owner"))
  if (!reconciliation && workingChanges(context.dependencies, snapshot.canonical.atoms).length)
    return yield* Effect.fail(workingError("DEPENDENCY_STALE", "A dependency changed before the write"))
  const source = prior?.key ?? context.dependencies[0]?.key
  if (!source) return yield* Effect.fail(workingError("INVALID", "Working context requires source provenance"))
  const content = yield* runtime.stageContent(WORKING_CONTEXT_MEDIA, encode(context))
  const atom: CanonicalAtomV2 = { _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: target.key, kind: WORKING_CONTEXT_KIND, responsibilityOwner: target.owner, content, lifecycle: "ADMITTED",
    provenance: { mode: "DERIVATION", evidenceSha256: content.sha256, sourceRef: source }, references: workingReferences(context, prior?.key ?? null) }
  const policyCandidate = policyProposal?.candidate
  if (policyCandidate && (policyCandidate.command.expectedStateRevision !== snapshot.canonical.revision || policyCandidate.command.authorizationRef !== target.authorizationRef || policyCandidate.command.scope !== target.scope))
    return yield* Effect.fail(workingError("ATOMIC_SCOPE_MISMATCH", "One owner transaction must cover the exact policy and working state"))
  const policyExists = snapshot.canonical.atoms.some(a => sameWorkingKey(a.key, context.policyKey))
  if (!policyExists && !policyCandidate?.command.writes.some(a => sameWorkingKey(a.key, context.policyKey)))
    return yield* Effect.fail(workingError("POLICY_MISSING", "Policy must already exist or be included in this atomic write"))
  const keys = [...context.dependencies.map(d => d.key), ...(prior ? [prior.key] : []), ...(policyExists ? [context.policyKey] : []), ...(policyCandidate?.command.readSet ?? [])]
  const writes = [...(policyCandidate?.command.writes ?? []), atom]
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: `working-context:${contextHash([target, content.sha256, policyCandidate?.command.transitionId ?? null])}`,
    expectedStateRevision: snapshot.canonical.revision, schemaVersion: target.key.schemaVersion, actorClaim: "working-context:owner-adapter",
    authorizationRef: target.authorizationRef, scope: target.scope, decidedAt: target.decidedAt, traceRef: null,
    readSet: [...new Map(keys.map(key => [canonicalAtomV2KeyId(key), key])).values()], writes, provenanceSha256: content.sha256
  }, [...(policyCandidate?.writeBindings ?? []), { key: atom.key, payload: content, envelope: yield* describeCanonicalAtomV2Envelope(atom) }])
  return { candidate, contextKey: atom.key, context, canonicalWrite: false as const }
})

export const prepareWorkingContextCreation = (runtime: Runtime, rawInput: unknown, rawTarget: unknown) => Effect.gen(function* () {
  const input = yield* decodeWorking(WorkingContextInputSchema, rawInput)
  const target = yield* decodeWorking(ActivationTargetSchema, rawTarget)
  const plan = yield* planFor(runtime, input)
  const policy = yield* policyFor(runtime, plan, input, target)
  return yield* prepareWrite(runtime, { contract: "hswm-working-context/v1", ...input,
    dependencies: workingDependencies(plan), policyKey: policy.key, lastRun: null }, target, null, policy.proposal)
})

/** Called at execution boundaries; unchanged contexts are a no-op, unrelated tasks are never rewritten. */
export const prepareWorkingContextRefresh = (runtime: Runtime, key: unknown, target: unknown) => Effect.gen(function* () {
  const current = yield* readWorkingContext(runtime, key)
  if (current.context.lastRun?.status === "PENDING") return yield* Effect.fail(workingError("PENDING", "Reconcile the pending external operation before refreshing"))
  const writer = yield* decodeWorking(ActivationTargetSchema, target)
  const input = { ...current.context, memory: reopenWorkingGaps(current.context.memory, current.changes.map(c => c.before)) }
  const plan = yield* planFor(runtime, input)
  const policy = yield* policyFor(runtime, plan, input, writer)
  const context = { ...input, dependencies: workingDependencies(plan), policyKey: policy.key }
  if (contextHash(context) === contextHash(current.context)) return null
  return yield* prepareWrite(runtime, context, writer, current.atom, policy.proposal)
})

/** User corrections/progress remain attributed task state; a change does not promote a source assertion. */
export const prepareWorkingMemoryUpdate = (runtime: Runtime, key: unknown, memory: unknown, target: unknown) => Effect.gen(function* () {
  const current = yield* readWorkingContext(runtime, key)
  if (current.context.lastRun?.status === "PENDING") return yield* Effect.fail(workingError("PENDING", "Reconcile the pending operation before editing memory"))
  const context = { ...current.context, memory: yield* decodeWorking(WorkingMemorySchema, memory) }
  yield* planFor(runtime, context)
  return yield* prepareWrite(runtime, context, target, current.atom)
})

const WorkingUseSchema = Schema.Struct({
  runId: Schema.NonEmptyString.pipe(Schema.maxLength(256)), mode: Schema.Literal("TRAIN", "AUDIT"), cell: Schema.Unknown,
  featureValues: Schema.Array(Schema.Number.pipe(Schema.finite(), Schema.between(-1, 1))).pipe(Schema.minItems(1), Schema.maxItems(16)),
  presentation: Schema.optional(ContextPresentationSchema), verification: Schema.optional(FiniteExecutionGuardSchema)
})

const admitted = <E, R>(runtime: Runtime, proposal: WorkingContextProposal, ports: Pick<WorkingContextPorts<E, R>, "admit">) => Effect.gen(function* () {
  yield* ports.admit(proposal)
  const checked = yield* readWorkingContext(runtime, proposal.contextKey)
  if (contextHash(checked.context) !== contextHash(proposal.context)) return yield* Effect.fail(workingError("READBACK_MISMATCH", "Owner did not persist the exact working-state successor"))
  return checked
})

/** Execute once per context/run ID. Pending/uncertain effects are never retried automatically. */
export const executeWorkingContextLoop = <E, R>(runtime: Runtime, rawKey: unknown, rawUse: unknown,
  writer: Omit<Target, "key">, ports: WorkingContextPorts<E, R>) => Effect.gen(function* () {
  const requestedKey = yield* decodeWorking(CanonicalAtomV2KeySchema, rawKey)
  const use = yield* decodeWorking(WorkingUseSchema, rawUse)
  yield* decodeLifecycleCell(use.cell)
  const requestSha256 = contextHash({ key: requestedKey, use })
  const history = (yield* runtime.snapshot).canonical.atoms.filter(a => a.kind === WORKING_CONTEXT_KIND &&
    a.key.schemaVersion === requestedKey.schemaVersion && a.key.lineageId === requestedKey.lineageId && a.key.atomUid === requestedKey.atomUid)
  for (const atom of [...history].sort((a, b) => b.key.revisionId - a.key.revisionId)) {
    const context = yield* readPayload(runtime, atom)
    const run = context.lastRun
    if (run?.id !== use.runId) continue
    if (run.requestSha256 !== requestSha256) return yield* Effect.fail(workingError("RUN_CONFLICT", "Run ID already binds a different request"))
    if (run.status === "PENDING" || run.status === "UNKNOWN") return yield* Effect.fail(workingError("PENDING", "Prior operation needs explicit reconciliation; no automatic repeat"))
    return { status: "REPLAYED" as const, contextKey: atom.key, run }
  }
  const current = yield* readWorkingContext(runtime, requestedKey)
  if (current.context.lastRun?.status === "PENDING") return yield* Effect.fail(workingError("PENDING", "One pending operation already owns this context"))
  const refresh = yield* prepareWorkingContextRefresh(runtime, current.atom.key, nextTarget(current.atom.key, writer))
  const ready = refresh === null ? current : yield* admitted(runtime, refresh, ports)
  const preflight = yield* planFor(runtime, ready.context)
  const policy = yield* readActivationPolicy(runtime, preflight, ready.context.policyKey)
  yield* chooseActivation(preflight, policy.policy, { encoderRevision: ready.context.policyFamily.config.encoderRevision,
    eventSha256: contextHash(preflight.spec.event), values: use.featureValues }, use.mode === "TRAIN" ? "EXPLORE" : "EXPLOIT")
  const pending: WorkingRun = { id: use.runId, requestSha256, status: "PENDING", traceContent: null, outcomeContent: null, policyKey: ready.context.policyKey }
  const reservation = yield* prepareWrite(runtime, { ...ready.context, lastRun: pending }, nextTarget(ready.atom.key, writer), ready.atom)
  const reserved = yield* admitted(runtime, reservation, ports)
  const plan = yield* planFor(runtime, reserved.context)
  const features: ActivationFeatures = { encoderRevision: reserved.context.policyFamily.config.encoderRevision,
    eventSha256: contextHash(plan.spec.event), values: use.featureValues }
  const finish = (run: WorkingRun, policy: ActivationProposal | null) => prepareWrite(runtime,
    { ...reserved.context, policyKey: run.policyKey, lastRun: run }, nextTarget(reserved.atom.key, writer), reserved.atom, policy)
  const result = yield* executeActivationLoop(runtime, plan, {
    decision: { policyKey: reserved.context.policyKey, features, mode: use.mode === "TRAIN" ? "EXPLORE" : "EXPLOIT" },
    mode: use.mode, cell: use.cell, target: nextTarget(reserved.context.policyKey, writer),
    ...(use.presentation === undefined ? {} : { presentation: use.presentation }),
    ...(use.verification === undefined ? {} : { verification: use.verification })
  }, { http: ports.http, evaluate: ports.evaluate,
    admit: proposal => Effect.gen(function* () {
      // Read the actual feedback bound by the existing loop; never manufacture a trace from a prediction.
      const feedback = yield* Schema.decodeUnknown(Schema.Struct({ traceContent: Schema.Struct({ mediaType: Schema.String, byteLength: Schema.Number, sha256: Schema.String }) }))(
        yield* parseJson(new TextDecoder().decode(yield* runtime.readContent(proposal.outcomeContent))))
      const run: WorkingRun = { ...pending, status: "UPDATED", traceContent: feedback.traceContent, outcomeContent: proposal.outcomeContent, policyKey: proposal.policyKey }
      yield* admitted(runtime, yield* finish(run, proposal), ports)
    })
  })
  if (result.status !== "UPDATED") {
    const outcome = result.execution.trace === null ? null : yield* stageSemanticContextOutcome(runtime, {
      traceContent: result.execution.trace.traceContent, observed: result.assessment.observed, source: result.assessment.source })
    yield* admitted(runtime, yield* finish({ ...pending, status: result.status,
      traceContent: result.execution.trace?.traceContent ?? null, outcomeContent: outcome?.outcomeContent ?? null }, null), ports)
  }
  const completed = yield* readWorkingContext(runtime, { ...reserved.atom.key, revisionId: reserved.atom.key.revisionId + 1 })
  return { ...result, contextKey: completed.atom.key, run: completed.context.lastRun }
})

/** Explicitly close an uncertain attempt. This records uncertainty, never a success or a W update. */
export const prepareWorkingContextReconciliation = (runtime: Runtime, key: unknown, observation: { readonly observed: string; readonly source: string }, target: unknown) => Effect.gen(function* () {
  const current = yield* readWorkingContext(runtime, key)
  if (current.context.lastRun?.status !== "PENDING") return yield* Effect.fail(workingError("NOT_PENDING", "Only a pending operation can be reconciled"))
  const evidence = yield* Schema.decodeUnknown(Schema.Struct({ observed: Schema.NonEmptyString.pipe(Schema.maxLength(8192)), source: Schema.NonEmptyString.pipe(Schema.maxLength(2048)) }))(observation)
  const outcomeContent = yield* runtime.stageContent("application/vnd.hswm.working-context-unknown-v1+json", encode({ ...evidence,
    runId: current.context.lastRun.id, requestSha256: current.context.lastRun.requestSha256, status: "UNKNOWN" }))
  return yield* prepareWrite(runtime, { ...current.context, lastRun: { ...current.context.lastRun, status: "UNKNOWN", outcomeContent } }, target, current.atom, null, true)
})
