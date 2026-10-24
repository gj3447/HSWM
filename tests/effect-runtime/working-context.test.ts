import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { NodePosixServicesLive, type BoundedSubprocess, type PosixFileSystem } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { workingContextKind, type WorkingMemory } from "../../src/hswm/effect-runtime/src/working-context-domain.js"
import { executeWorkingContextLoop, openWorkingContext, prepareWorkingContextCreation, prepareWorkingContextRefresh, prepareWorkingMemoryUpdate, prepareWorkingContextReconciliation, type WorkingContextPorts } from "../../src/hswm/effect-runtime/src/working-context-runtime.js"
import { workingContextProcess } from "../../src/hswm/effect-runtime/src/working-context-process.js"
import { schema, key, spec, seedContext, unwrap } from "./semantic-context-fixture.js"

const owner = "owner:context-test"
const workingSchema: HSWMCanonicalSchemaV2 = { ...schema, kinds: [...schema.kinds, {
  kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 1,
  referenceContracts: [
    { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
    { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }
  ]
}, workingContextKind([owner])] }
const bytes = unwrap(canonicalAtomV2SchemaContentBytes(workingSchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(bytes)).binding.content.sha256
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "working-context-tests", bytes, [
  { authorizationRef: "fixture-auth", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["fixture"] }
])
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const fixture = <A, E>(use: (runtime: Runtime, root: string) => Effect.Effect<A, E, BoundedSubprocess | PosixFileSystem>) => Effect.runPromise(Effect.acquireUseRelease(
  Effect.sync(() => mkdtempSync(join(tmpdir(), "hswm-working-context-"))),
  root => seedContext.pipe(Effect.flatMap(runtime => use(runtime, root)), Effect.provide(layer(root))),
  root => Effect.sync(() => rmSync(root, { recursive: true, force: true }))
).pipe(Effect.provide(NodePosixServicesLive), Effect.mapError(error => new Error(JSON.stringify(error), { cause: error }))))
const writer = { owner, authorizationRef: "fixture-auth", scope: "fixture", decidedAt: "2026-10-24T00:00:00.000Z" }
const target = (id: string, revisionId = 0) => ({ ...writer, key: { ...key(`working:${id}`), revisionId } })
const memory: WorkingMemory = { goal: "문을 열 수 있는지 판정", constraints: ["파손 예외 보존"], completionCriteria: ["근거와 예외를 포함한 답"], progress: "시작",
  gaps: [{ id: "missing", question: "현재 열쇠가 파손됐는가?", status: "OPEN", evidence: [] }] }
const input = (id: string) => ({ agentId: `agent:${id}`, taskId: `task:${id}`, memory, spec,
  policyFamily: { lineageId: "shared-operators", atomUid: "door-or-calendar", config: { encoderRevision: "bias/v1", featureNames: ["bias"], alpha: 1 } } })
const create = (runtime: Runtime, id: string, changes: Partial<ReturnType<typeof input>> = {}) => Effect.gen(function* () {
  const proposal = yield* prepareWorkingContextCreation(runtime, { ...input(id), ...changes }, target(id))
  yield* runtime.submit(proposal.candidate)
  return yield* openWorkingContext(runtime, proposal.contextKey)
})
const cell = { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_TRANSPORT_NOT_REAL_MODEL", max_tokens: 32 }
const use = (runId: string, mode = "TRAIN") => ({ runId, mode, cell, featureValues: [1], presentation: "execution_tail" })
const ports = (runtime: Runtime, seen: { calls: number }): WorkingContextPorts<Effect.Effect.Error<ReturnType<Runtime["submit"]>>, never> => ({
  http: { postJson: () => Effect.sync(() => { seen.calls++; return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "observed", uncertainty: "SCRIPTED" }) } }] })) }) },
  // A declared deterministic oracle for plumbing tests; never described as real model efficacy.
  evaluate: execution => Effect.succeed({ reward: Number(execution.selection.candidateId === "calendar"), observed: "calendar is the authored target", source: "AUTHORED_TEST_ORACLE", continue: false }),
  admit: proposal => runtime.submit(proposal.candidate)
})
const reviseRelation = (runtime: Runtime, uid: string) => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  const prior = snapshot.canonical.atoms.find(a => a.key.atomUid === uid)
  if (!prior) return yield* Effect.fail(new Error("missing fixture source"))
  const payload = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(prior.content)))
  const content = yield* runtime.stageContent(prior.content.mediaType, new TextEncoder().encode(JSON.stringify({ ...payload, semanticText: "Source corrected: deny access until reviewed." })))
  const atom = { ...prior, key: { ...prior.key, revisionId: prior.key.revisionId + 1 }, content,
    provenance: { mode: "DERIVATION" as const, evidenceSha256: content.sha256, sourceRef: prior.key },
    references: [{ referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: prior.key }, ...prior.references] }
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: `correct:${uid}`,
    expectedStateRevision: snapshot.canonical.revision, schemaVersion: schema.schemaVersion, actorClaim: "source-owner", authorizationRef: writer.authorizationRef, scope: writer.scope,
    decidedAt: writer.decidedAt, traceRef: null, readSet: [prior.key, ...prior.references.map(r => r.target)], writes: [atom], provenanceSha256: content.sha256
  }, [{ key: atom.key, payload: content, envelope: yield* describeCanonicalAtomV2Envelope(atom) }]))
})

it("recovers goals, open gaps and source revisions from the native journal and uses memory in the next prompt", () => fixture((runtime, root) => Effect.gen(function* () {
  const created = yield* create(runtime, "a")
  const edited = yield* prepareWorkingMemoryUpdate(runtime, created.atom.key, { ...memory, progress: "현장 확인 대기" }, target("a", 1))
  yield* runtime.submit(edited.candidate)
  const recovered = yield* Effect.gen(function* () {
    const reopened = yield* CanonicalAtomV2DurableRuntime
    const current = yield* openWorkingContext(reopened, target("a").key)
    expect(current.context.memory).toEqual({ ...memory, progress: "현장 확인 대기" })
    expect(current.context.dependencies).toEqual(created.context.dependencies)
    return current
  }).pipe(Effect.provide(layer(root)))
  const selected = yield* workingContextProcess({ contract: "hswm-working-context-cli/v1", action: "select", durableRoot: root,
    journalLineageId: "working-context-tests", schema: workingSchema, contextKey: recovered.atom.key, featureValues: [1] }).pipe(Effect.provide(NodePosixServicesLive))
  expect(JSON.stringify(selected)).toContain("현장 확인 대기")
  expect(JSON.stringify(selected)).toContain("파손 예외 보존")
})))

it("refreshes only dependent tasks, reopens affected resolved gaps and preserves old policy history", () => fixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a", { spec: { ...spec, mandatoryRelationUids: [], candidates: spec.candidates.filter(c => c.id === "door") },
    memory: { ...memory, gaps: [{ id: "source", question: "문 규칙?", status: "RESOLVED", evidence: [key("relation:door")] }] } })
  const b = yield* create(runtime, "b", { spec: { ...spec, mandatoryRelationUids: [], candidates: spec.candidates.filter(c => c.id === "calendar") } })
  yield* reviseRelation(runtime, "relation:door")
  expect((yield* openWorkingContext(runtime, a.atom.key)).status).toBe("STALE")
  expect((yield* openWorkingContext(runtime, b.atom.key)).status).toBe("CURRENT")
  expect(yield* prepareWorkingContextRefresh(runtime, b.atom.key, target("b", 1))).toBeNull()
  const refresh = yield* prepareWorkingContextRefresh(runtime, a.atom.key, target("a", 1))
  if (!refresh) return yield* Effect.fail(new Error("expected refresh"))
  yield* runtime.submit(refresh.candidate)
  const updated = yield* openWorkingContext(runtime, a.atom.key)
  expect(updated.status).toBe("CURRENT")
  expect(updated.context.dependencies.find(d => d.key.atomUid === "relation:door")?.key.revisionId).toBe(1)
  expect(updated.context.memory.gaps[0]).toMatchObject({ status: "OPEN", evidence: [] })
  expect(updated.context.policyKey.atomUid).not.toBe(a.context.policyKey.atomUid)
  expect((yield* runtime.snapshot).canonical.atoms.some(atom => atom.key.atomUid === a.context.policyKey.atomUid)).toBe(true)
  expect((yield* openWorkingContext(runtime, b.atom.key)).atom.key).toEqual(b.atom.key)
})))

it("publishes outcome-bound policy and task completion atomically; another task uses the learned revision and retries do not learn twice", () => fixture((runtime, root) => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const b = yield* create(runtime, "b")
  expect(a.context.policyKey).toEqual(b.context.policyKey)
  const seen = { calls: 0 }
  const commits: string[][] = []
  const p = { ...ports(runtime, seen), admit: (proposal: Parameters<WorkingContextPorts<never, never>["admit"]>[0]) =>
    runtime.submit(proposal.candidate).pipe(Effect.tap(() => Effect.sync(() => commits.push(proposal.candidate.command.writes.map(a => a.kind))))) }
  const first = yield* executeWorkingContextLoop(runtime, a.atom.key, use("run:1"), writer, p)
  expect(first.status).toBe("UPDATED")
  const second = yield* executeWorkingContextLoop(runtime, first.contextKey, use("run:2"), writer, p)
  expect(second.status).toBe("UPDATED")
  const after = (yield* runtime.snapshot).canonical.revision
  const replay = yield* executeWorkingContextLoop(runtime, first.contextKey, use("run:2"), writer, p)
  expect(replay.status).toBe("REPLAYED")
  expect(seen.calls).toBe(2)
  expect((yield* runtime.snapshot).canonical.revision).toBe(after)
  expect(Either.isLeft(yield* Effect.either(executeWorkingContextLoop(runtime, first.contextKey, { ...use("run:2"), featureValues: [-1] }, writer, p)))).toBe(true)
  const refresh = yield* prepareWorkingContextRefresh(runtime, b.atom.key, target("b", 1))
  if (!refresh) return yield* Effect.fail(new Error("expected shared policy notification"))
  yield* runtime.submit(refresh.candidate)
  const selected = yield* workingContextProcess({ contract: "hswm-working-context-cli/v1", action: "select", durableRoot: root,
    journalLineageId: "working-context-tests", schema: workingSchema, contextKey: target("b").key, featureValues: [1] }).pipe(Effect.provide(NodePosixServicesLive))
  expect(selected).toMatchObject({ selection: { candidateId: "calendar", policyKey: { revisionId: 2 } } })
  const updated = yield* openWorkingContext(runtime, second.contextKey)
  expect(updated.context.lastRun).toMatchObject({ id: "run:2", status: "UPDATED", policyKey: { revisionId: 2 } })
  expect(commits.filter(kinds => kinds.includes("semantic_context_policy"))).toEqual([
    ["semantic_context_policy", "working_context"], ["semantic_context_policy", "working_context"]
  ])
})), 120000)

it("leaves uncertain execution pending, prevents automatic repeats and records explicit reconciliation without W", () => fixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const seen = { calls: 0 }
  const p = ports(runtime, seen)
  const failed = yield* Effect.either(executeWorkingContextLoop(runtime, a.atom.key, use("uncertain"), writer,
    { ...p, evaluate: () => Effect.fail(new Error("outcome unavailable")) }))
  expect(Either.isLeft(failed)).toBe(true)
  const pending = yield* openWorkingContext(runtime, a.atom.key)
  expect(pending.context.lastRun?.status).toBe("PENDING")
  expect(pending.context.policyKey.revisionId).toBe(0)
  expect(Either.isLeft(yield* Effect.either(executeWorkingContextLoop(runtime, a.atom.key, use("uncertain"), writer, p)))).toBe(true)
  expect(seen.calls).toBe(1)
  yield* reviseRelation(runtime, "relation:door")
  const resolution = yield* prepareWorkingContextReconciliation(runtime, pending.atom.key, { observed: "External outcome unknown; do not replay", source: "test operator" }, target("a", pending.atom.key.revisionId + 1))
  yield* runtime.submit(resolution.candidate)
  expect((yield* openWorkingContext(runtime, a.atom.key)).context.lastRun?.status).toBe("UNKNOWN")
  expect((yield* openWorkingContext(runtime, a.atom.key)).context.policyKey.revisionId).toBe(0)
  expect((yield* openWorkingContext(runtime, a.atom.key)).status).toBe("STALE")
})))

it("does not partially publish learning when the joint policy/context admission is rejected", () => fixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const seen = { calls: 0 }
  const p = ports(runtime, seen)
  const result = yield* Effect.either(executeWorkingContextLoop(runtime, a.atom.key, use("rejected"), writer, {
    ...p, admit: proposal => proposal.candidate.command.writes.some(atom => atom.kind === "semantic_context_policy")
      ? Effect.fail(new Error("joint write rejected")) : runtime.submit(proposal.candidate)
  }))
  expect(Either.isLeft(result)).toBe(true)
  expect(seen.calls).toBe(1)
  const current = yield* openWorkingContext(runtime, a.atom.key)
  expect(current.context.lastRun?.status).toBe("PENDING")
  expect((yield* runtime.snapshot).canonical.atoms.filter(atom => atom.key.atomUid === a.context.policyKey.atomUid)).toHaveLength(1)
})))

it("keeps AUDIT and unknown rewards non-learning and rejects false gap resolution", () => fixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const seen = { calls: 0 }
  const p = ports(runtime, seen)
  const audited = yield* executeWorkingContextLoop(runtime, a.atom.key, use("audit", "AUDIT"), writer, p)
  expect(audited.status).toBe("AUDITED")
  const unknown = yield* executeWorkingContextLoop(runtime, audited.contextKey, use("unknown"), writer, { ...p,
    evaluate: () => Effect.succeed({ reward: null, observed: "No external outcome", source: "AUTHORED_TEST", continue: false }) })
  expect(unknown.status).toBe("NO_UPDATE")
  const current = yield* openWorkingContext(runtime, unknown.contextKey)
  expect(current.context.policyKey.revisionId).toBe(0)
  expect(Either.isLeft(yield* Effect.either(prepareWorkingMemoryUpdate(runtime, current.atom.key,
    { ...memory, gaps: [{ id: "fake", question: "resolved?", status: "RESOLVED", evidence: [] }] }, target("a", current.atom.key.revisionId + 1))))).toBe(true)
})))

it("refuses stale competing memory updates and unauthorized admission without overwriting another writer", () => fixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const first = yield* prepareWorkingMemoryUpdate(runtime, a.atom.key, { ...memory, progress: "first writer" }, target("a", 1))
  const second = yield* prepareWorkingMemoryUpdate(runtime, a.atom.key, { ...memory, progress: "second writer" }, target("a", 1))
  yield* runtime.submit(first.candidate)
  expect(Either.isLeft(yield* Effect.either(runtime.submit(second.candidate)))).toBe(true)
  const current = yield* openWorkingContext(runtime, a.atom.key)
  expect(current.context.memory.progress).toBe("first writer")
  const unauthorized = yield* prepareWorkingMemoryUpdate(runtime, current.atom.key, { ...memory, progress: "untrusted" }, { ...target("a", 2), authorizationRef: "untrusted" })
  expect(Either.isLeft(yield* Effect.either(runtime.submit(unauthorized.candidate)))).toBe(true)
  expect((yield* openWorkingContext(runtime, a.atom.key)).atom.key).toEqual(current.atom.key)
})))
