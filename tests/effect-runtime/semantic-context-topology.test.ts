import { mkdtempSync, rmSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { type CanonicalAtomV2, type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { readLlmSemanticFrame, type SemanticReadFrame } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { prepareSemanticContext, executeSelectedSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { contextHash, type ContextPlan, type ContextSpec } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { prepareActivationInitialization, executeContextActivation, prepareActivationLearning, selectContextActivation } from "../../src/hswm/effect-runtime/src/semantic-context-activation-runtime.js"
import { proposeContextRetirements, prepareContextTopologyChange, readContextTopology } from "../../src/hswm/effect-runtime/src/semantic-context-topology-runtime.js"
import { reviewContextRetirement } from "../../src/hswm/effect-runtime/src/semantic-context-topology-domain.js"
import { compileCanonicalAtomV2DurableRdfProjection, verifyCanonicalAtomV2DurableRdfProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-rdf-projection.js"
import { FiniteExecutionViolation } from "../../src/hswm/effect-runtime/src/semantic-context-finite-execution-domain.js"
import { contextActivationProcess } from "../../src/hswm/effect-runtime/src/semantic-context-activation-process.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/src/effect-process-main.js"
import { schema as sourceSchema, unwrap } from "./semantic-context-fixture.js"

const schema: HSWMCanonicalSchemaV2 = { ...sourceSchema, kinds: [...sourceSchema.kinds, { kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: ["owner:context-test"], minimumArity: 1,
  referenceContracts: [{ referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
    { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }] }] }
const key = (atomUid: string, revisionId = 0) => ({ schemaVersion: schema.schemaVersion, lineageId: "finite-loop", atomUid, revisionId })
const target = (uid: string, revision = 0) => ({ key: key(uid, revision), owner: "owner:context-test", authorizationRef: "loop-test", scope: "loop-test", decidedAt: "2026-10-19T00:00:00.000Z" })
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "loop-test", schemaBytes, [{ authorizationRef: "loop-test", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["loop-test"] }])
const spec: ContextSpec = { contract: "hswm-semantic-context-spec/v1", event: "test-event", mandatoryRelationUids: ["rule:mandatory"], candidates: [
  { id: "a", summary: "x or exception", relationUids: ["rule:a", "rule:duplicate", "rule:mandatory"] },
  { id: "b", summary: "not x or exception", relationUids: ["rule:b"] }
], maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 }
const config = { encoderRevision: "fixture/v1", featureNames: ["bias"], alpha: 1 }
const decision = (plan: ContextPlan, revision: number) => ({ policyKey: key("policy:w", revision), features: { encoderRevision: config.encoderRevision, eventSha256: contextHash(plan.spec.event), values: [1] }, mode: "EXPLORE" })
const program = (kind: string) => JSON.stringify({ contract: "hswm-finite-semantic-program/v1",
  variables: [{ id: "x", roleOrdinal: 0, values: ["0", "1"] }, { id: "e", roleOrdinal: 3, values: ["0", "1"] }],
  expressions: kind === "mandatory" ? [{ op: "is", variable: "x", value: "1" }, { op: "not", arg: 0 }, { op: "or", left: 0, right: 1 },
    { op: "is", variable: "e", value: "1" }, { op: "not", arg: 3 }, { op: "or", left: 3, right: 4 }, { op: "and", left: 2, right: 5 }] :
    [{ op: "is", variable: "x", value: kind === "b" ? "0" : "1" }, { op: "is", variable: "e", value: "1" }, { op: "or", left: 0, right: 1 }], clauses: [{ id: "c", expression: kind === "mandatory" ? 6 : 2 }] })
const fixture = <A, E, R>(body: (runtime: CanonicalAtomV2DurableRuntime["Type"], root: string) => Effect.Effect<A, E, R>) => Effect.acquireUseRelease(
  Effect.sync(() => mkdtempSync(join(tmpdir(), "hswm-topology-"))), root => Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const writes: CanonicalAtomV2[] = []
    for (const role of ["subject", "context", "evidence", "exception"]) {
      writes.push({ _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(`shared:${role}`), kind: "semantic_participant", responsibilityOwner: target("x").owner,
        content: yield* runtime.stageContent("text/plain", new TextEncoder().encode(`shared source ${role}`)), lifecycle: "ADMITTED", references: [], provenance: { mode: "BOOTSTRAP", sourceRef: null, evidenceSha256: "a".repeat(64) } })
    }
    for (const name of ["mandatory", "a", "duplicate", "b"]) {
      const content = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", new TextEncoder().encode(JSON.stringify({ semanticText: program(name), disposition: "predict", uncertainty: "finite authored scope", exceptionRefs: ["shared:exception"], trace: null, outcome: null })))
      writes.push({ _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(`rule:${name}`), kind: "semantic_relation", responsibilityOwner: target("x").owner,
        content, lifecycle: "ADMITTED", provenance: { mode: "BOOTSTRAP", sourceRef: null, evidenceSha256: "a".repeat(64) },
        references: ["subject", "context", "evidence", "exception"].map(role => ({ referenceType: "hswm:semantic:role", role, target: key(`shared:${role}`) })) })
    }
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(schemaHash, { _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: "seed-loop", expectedStateRevision: 0,
      schemaVersion: schema.schemaVersion, actorClaim: "test-fixture", authorizationRef: "loop-test", scope: "loop-test", decidedAt: target("x").decidedAt,
      traceRef: null, readSet: [], writes, provenanceSha256: "a".repeat(64) }, writes.map(a => ({ key: a.key, payload: a.content, envelope: unwrap(describeCanonicalAtomV2Envelope(a)) }))))
    return yield* body(runtime, root)
  }).pipe(Effect.provide(layer(root))), root => Effect.sync(() => rmSync(root, { recursive: true, force: true })))
const run = <A, E>(e: Effect.Effect<A, E, import("../../src/hswm/effect-runtime/src/effect-posix-filesystem.js").PosixFileSystem | import("../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js").BoundedSubprocess>) => Effect.runPromise(e.pipe(Effect.provide(NodePosixServicesLive)))
const afterSpec = { ...spec, candidates: spec.candidates.map(c => c.id === "a" ? { ...c, relationUids: ["rule:a", "rule:mandatory"] } : c) }
const frames = (runtime: CanonicalAtomV2DurableRuntime["Type"]) => Effect.forEach(["rule:mandatory", "rule:a", "rule:duplicate", "rule:b"], uid => readLlmSemanticFrame(runtime, uid, spec.event))

it.each(["canonical_json", "execution_tail", "finite_table_tail"] as const)("guards %s, preserves failed evidence, rejects positive credit and reopens zero-reward learning", presentation => run(fixture((runtime, root) => Effect.gen(function* () {
  const guardedSpec = { ...spec, event: '{"exception":0}' }
  let plan = yield* prepareSemanticContext(runtime, guardedSpec)
  yield* runtime.submit((yield* prepareActivationInitialization(runtime, plan, config, target("policy:w"))).candidate)
  plan = yield* prepareSemanticContext(runtime, guardedSpec)
  const guard = { contract: "hswm-finite-execution-guard/v1", rules: ["mandatory", "a", "duplicate"].map(name => ({
    relationKey: key(`rule:${name}`), inputs: [{ variable: "e", eventField: "exception" }], outputVariable: "x"
  })) }
  const cell = { base_url: "https://fixture.invalid/v1", model: "SCRIPTED", max_tokens: 32 }
  let calls = 0
  const http = (prediction: string) => ({ postJson: () => Effect.sync(() => {
    calls++
    return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction, uncertainty: "SCRIPTED_GUARD_TEST" }) } }] }))
  }) })
  const before = yield* runtime.snapshot
  const invalid = yield* Effect.either(contextActivationProcess({ contract: "hswm-context-activation-cli/v1", action: "execute", durableRoot: root,
    journalLineageId: "loop-test", schema, spec: guardedSpec, expectedPlanSha256: plan.planSha256, decision: decision(plan, 0), cell, presentation,
    verification: { ...guard, rules: [] } }))
  expect(Either.isLeft(invalid)).toBe(true)
  const missing = yield* Effect.either(executeContextActivation(runtime, plan, decision(plan, 0), cell, http("1"), presentation,
    { ...guard, rules: guard.rules.slice(1) }))
  expect(Either.isLeft(missing) && "code" in missing.left && missing.left.code).toBe("FINITE_BINDING_INVALID")
  expect(calls).toBe(0)
  const failed = yield* Effect.either(executeContextActivation(runtime, plan, decision(plan, 0), cell, http("0"), presentation, guard))
  if (Either.isRight(failed) || !(failed.left instanceof FiniteExecutionViolation)) return yield* Effect.fail("Expected explicit constraint failure")
  const violation = failed.left
  expect(calls).toBe(1)
  expect(violation.verification.status).toBe("VIOLATED")
  expect(violation.verification.prediction).toBe("0")
  expect(yield* runtime.snapshot).toEqual(before)
  const trace = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(violation.traceContent)))
  const request = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(trace.requestContent)))
  expect(trace.requestContent.mediaType).toBe("application/vnd.hswm.semantic-context-request-v3+json")
  expect(request.verification).toEqual(guard)
  expect(request.prompt).toContain("EXPLICIT INPUT/OUTPUT BINDINGS")
  const bounded = yield* prepareSemanticContext(runtime, { ...guardedSpec, maximumContextBytes: request.promptBytes - 1 })
  const overBudget = yield* Effect.either(executeSelectedSemanticContext(runtime, bounded,
    { planSha256: bounded.planSha256, status: "SELECTED", candidateId: "a" }, cell, http("1"), presentation, guard))
  expect(Either.isLeft(overBudget) && "code" in overBudget.left && overBudget.left.code).toBe("CONTEXT_BUDGET_EXCEEDED")
  expect(calls).toBe(1)
  expect(JSON.parse(new TextDecoder().decode(yield* runtime.readContent(trace.responseContent))).prediction).toBe("0")
  const stderr: string[] = [], stdout: string[] = []
  const code = yield* Effect.promise(() => runArgvProcessMain({ refusalPrefix: "HSWM_ACTIVATION_REFUSED",
    program: () => Effect.fail(violation), describeFailure: error => String(error) }, [],
    { readStdin: () => Effect.succeed(""), writeStdout: x => Effect.sync(() => { stdout.push(x) }), writeStderr: x => Effect.sync(() => { stderr.push(x) }) }))
  expect(code).toBe(2); expect(stdout).toEqual([]); expect(stderr.join("")).toContain(violation.traceContent.sha256)
  const feedback = { traceContent: violation.traceContent, reward: 1, observed: "constraint violation", source: "SCRIPTED_GUARD_TEST" }
  const positive = yield* Effect.either(prepareActivationLearning(runtime, plan, feedback, target("policy:w", 1)))
  expect(Either.isLeft(positive) && "code" in positive.left && positive.left.code).toBe("FINITE_REWARD_INVALID")
  const forged = yield* runtime.stageContent(violation.traceContent.mediaType, new TextEncoder().encode(JSON.stringify({ ...trace, verification: { ...trace.verification, status: "SATISFIED" } })))
  expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, plan, { ...feedback, traceContent: forged, reward: 0 }, target("policy:w", 1))))).toBe(true)
  const accepted = yield* executeContextActivation(runtime, plan, decision(plan, 0), cell, http("1"), presentation, guard)
  if (!accepted.trace) return yield* Effect.fail("Missing successful trace")
  expect(accepted.trace.verification?.status).toBe("SATISFIED")
  const success = yield* prepareActivationLearning(runtime, plan, { ...feedback, traceContent: accepted.trace.traceContent }, target("policy:w", 1))
  expect(success.policy.arms[0]?.b).toEqual([1])
  // Admit only the failure observation: unsuccessful execution remains useful negative feedback.
  const zero = yield* prepareActivationLearning(runtime, plan, { ...feedback, reward: 0 }, target("policy:w", 1))
  expect(zero.policy.arms[0]).toMatchObject({ observations: 1, a: [[2]], b: [0] })
  yield* runtime.submit(zero.candidate)
  yield* Effect.gen(function* () {
    const reopened = yield* CanonicalAtomV2DurableRuntime
    const fresh = yield* prepareSemanticContext(reopened, guardedSpec)
    const selected = yield* selectContextActivation(reopened, fresh, decision(fresh, 1))
    expect(selected.policyKey.revisionId).toBe(1)
    expect(selected.candidateId).toBe("b")
    expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(reopened, fresh, { ...feedback, reward: 0 }, target("policy:w", 2))))).toBe(true)
  }).pipe(Effect.provide(layer(root)))
  expect(calls).toBe(2)
}))))

it("checks whole conjunctions: individual redundancy does not justify simultaneous deletion", () => run(fixture(runtime => Effect.gen(function* () {
  const source = yield* frames(runtime)
  expect((yield* reviewContextRetirement(spec, afterSpec, source)).status).toBe("PRESERVED")
  expect(Either.isLeft(reviewContextRetirement(spec, { ...afterSpec, mandatoryRelationUids: [] }, source))).toBe(true)
  const both = { ...spec, candidates: spec.candidates.map(c => c.id === "a" ? { ...c, relationUids: ["rule:mandatory"] } : c) }
  const rejected = yield* reviewContextRetirement(spec, both, source)
  expect(rejected.status).toBe("CHANGED")
  expect(rejected.rows[0]?.witness).not.toBeNull()
  expect(rejected.rows[1]?.status).toBe("UNCHANGED")
}))))

const mutations: Array<[string, (fs: readonly SemanticReadFrame[]) => readonly SemanticReadFrame[]]> = [
  ["unique role source", fs => fs.map(f => f.relation.key.atomUid !== "rule:duplicate" ? f : { ...f, roles: f.roles.map((r, i) => i === 0 ? { ...r, owner: "different-owner" } : r) })],
  ["unique exception", fs => fs.map(f => f.relation.key.atomUid !== "rule:duplicate" ? f : { ...f, relation: { ...f.relation, semantic: { ...f.relation.semantic, exceptionRefs: ["unique:exception"] } } })],
  ["natural language", fs => fs.map(f => f.relation.key.atomUid !== "rule:duplicate" ? f : { ...f, relation: { ...f.relation, semantic: { ...f.relation.semantic, semanticText: "probably equivalent" } } })],
  ["mixed revision", fs => fs.map((f, i) => i === 0 ? { ...f, stateRevision: 500 } : f)]
]
it.each(mutations)("refuses %s instead of treating unknown semantics as preservation", (_name, change) => run(fixture(runtime => Effect.gen(function* () {
  expect(Either.isLeft(reviewContextRetirement(spec, afterSpec, change(yield* frames(runtime))))).toBe(true)
}))))

it.each(["execution_tail", "finite_table_tail"] as const)("binds %s execution to learning, atomic retirement, reopen and restore", presentation => run(fixture((runtime, root) => Effect.gen(function* () {
  const original = (yield* runtime.snapshot).canonical.atoms
  let plan = yield* prepareSemanticContext(runtime, spec)
  yield* runtime.submit((yield* prepareActivationInitialization(runtime, plan, config, target("policy:w"))).candidate)
  plan = yield* prepareSemanticContext(runtime, spec)
  const calls: string[] = []
  const http = { postJson: (request: { body: Uint8Array }) => Effect.sync(() => {
    const body = JSON.parse(new TextDecoder().decode(request.body))
    calls.push(body.messages[0].content)
    return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "1", uncertainty: "SCRIPTED_TEST_NOT_REAL_MODEL" }) } }] }))
  }) }
  const execution = yield* executeContextActivation(runtime, plan, decision(plan, 0), { base_url: "https://fixture.invalid/v1", model: "SCRIPTED", max_tokens: 32 }, http, presentation)
  if (!execution.trace) return yield* Effect.fail("missing trace")
  expect(calls).toHaveLength(1)
  expect(calls[0]).toContain(presentation === "execution_tail" ? "EXECUTE NOW" : "BEGIN ALLOWED ROWS")
  expect(calls[0]).toContain(presentation === "execution_tail" ? program("a") : 'Columns, in order: ["x","e"]')
  const feedback = { traceContent: execution.trace.traceContent, reward: Number(execution.trace.prediction === "1"), observed: "exact observed fixture result", source: "SCRIPTED_FIXTURE_EVALUATOR" }
  const trace = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(execution.trace.traceContent)))
  const presented = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(trace.requestContent)))
  const forgedRequest = yield* runtime.stageContent(trace.requestContent.mediaType, new TextEncoder().encode(JSON.stringify({ ...presented, prompt: "Changed instruction" })))
  const forgedTrace = yield* runtime.stageContent(execution.trace.traceContent.mediaType, new TextEncoder().encode(JSON.stringify({ ...trace, requestContent: forgedRequest })))
  expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, plan, { ...feedback, traceContent: forgedTrace }, target("policy:w", 1))))).toBe(true)
  const changedWire = yield* runtime.stageContent(trace.transport.request.mediaType, new TextEncoder().encode(JSON.stringify({ messages: [{ role: "user", content: "Changed wire" }] })))
  const forgedWireTrace = yield* runtime.stageContent(execution.trace.traceContent.mediaType, new TextEncoder().encode(JSON.stringify({ ...trace, transport: { ...trace.transport, request: changedWire } })))
  expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, plan, { ...feedback, traceContent: forgedWireTrace }, target("policy:w", 1))))).toBe(true)
  const bounded = yield* prepareSemanticContext(runtime, { ...spec, maximumContextBytes: execution.assembly?.contextBytes })
  expect(Either.isLeft(yield* Effect.either(executeSelectedSemanticContext(runtime, bounded, { planSha256: bounded.planSha256, status: "SELECTED", candidateId: "a" },
    { base_url: "https://fixture.invalid/v1", model: "SCRIPTED", max_tokens: 32 }, http, presentation)))).toBe(true)
  expect(calls).toHaveLength(1)
  const learned = yield* prepareActivationLearning(runtime, plan, feedback, target("policy:w", 1))
  expect(learned.policy.arms[0]?.a).toEqual([[2]])
  expect(learned.policy.arms[0]?.b).toEqual([1])
  yield* runtime.submit(learned.candidate)
  plan = yield* prepareSemanticContext(runtime, spec)
  const basis = { policyKey: key("policy:w", 1), feedbackContent: learned.outcomeContent, partition: "TRAIN", minimumObservations: 1 }
  const candidates = yield* proposeContextRetirements(runtime, plan, basis, 8)
  expect(candidates.candidates.filter(c => c.status === "CANDIDATE")).toHaveLength(2)
  expect(Either.isLeft(yield* Effect.either(proposeContextRetirements(runtime, plan, { ...basis, partition: "HOLDOUT" }, 8)))).toBe(true)
  expect(Either.isLeft(yield* Effect.either(proposeContextRetirements(runtime, plan, { ...basis, minimumObservations: 2 }, 8)))).toBe(true)
  const change = { operation: "RETIRE", afterSpec, policyKey: key("policy:w", 1), basis, priorTopologyKey: null,
    topologyTarget: target("policy:topology"), activationTarget: target("policy:w", 2) }
  const proposed = yield* prepareContextTopologyChange(runtime, plan, change)
  expect(proposed.candidate.command.writes).toHaveLength(2)
  const stripped = { ...afterSpec, candidates: afterSpec.candidates.map(c => c.id === "a" ? { ...c, relationUids: ["rule:mandatory"] } : c) }
  expect(Either.isLeft(yield* Effect.either(prepareContextTopologyChange(runtime, plan, { ...change, afterSpec: stripped })))).toBe(true)
  const denied = { ...proposed.candidate, command: { ...proposed.candidate.command, authorizationRef: "wrong" } }
  expect(Either.isLeft(yield* Effect.either(runtime.submit(denied)))).toBe(true)
  expect((yield* selectContextActivation(runtime, plan, decision(plan, 1))).policyKey.revisionId).toBe(1)
  yield* runtime.submit(proposed.candidate)
  expect(Either.isLeft(yield* Effect.either(prepareContextTopologyChange(runtime, plan, change)))).toBe(true)
  const current = yield* readContextTopology(runtime, key("policy:topology"), "new event")
  expect(current.plan.spec.candidates[0]?.relationUids).toEqual(["rule:a", "rule:mandatory"])
  expect(current.policyKey.revisionId).toBe(2)
  const changedScope = yield* prepareSemanticContext(runtime, afterSpec)
  expect(Either.isLeft(yield* Effect.either(selectContextActivation(runtime, changedScope, decision(changedScope, 1))))).toBe(true)
  expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, current.plan, feedback, target("policy:w", 3))))).toBe(true)
  const reset = (yield* runtime.snapshot).canonical.atoms.find(a => a.key.atomUid === "policy:w" && a.key.revisionId === 2)!
  expect(JSON.parse(new TextDecoder().decode(yield* runtime.readContent(reset.content))).arms.map((a: { observations: number }) => a.observations)).toEqual([0, 0])
  const cwd = resolve(import.meta.dirname, "../../src/hswm/effect-runtime")
  const cliRead = yield* Effect.try(() => JSON.parse(execFileSync(join(cwd, "bin/hswm-activation"), [], { cwd, encoding: "utf8", timeout: 60000, maxBuffer: 1048576,
    input: JSON.stringify({ contract: "hswm-context-activation-cli/v1", action: "topology-read", durableRoot: root, journalLineageId: "loop-test", schema, spec, topologyKey: key("policy:topology") }) })))
  expect(cliRead.policyKey.revisionId).toBe(2)
  expect(cliRead.plan.spec.candidates[0].relationUids).toEqual(["rule:a", "rule:mandatory"])
  const script = `import { Effect } from 'effect';
import { makeCanonicalAtomV2DurableRuntimeFileLayer, CanonicalAtomV2DurableRuntime } from './dist/canonical-atom-v2-durable-runtime.js';
import { NodePosixServicesLive } from './dist/effect-posix-services.js';
import { readContextTopology } from './dist/semantic-context-topology-runtime.js';
import { executeContextActivation } from './dist/semantic-context-activation-runtime.js';
import { contextHash } from './dist/semantic-context-domain.js';
const input=JSON.parse(process.argv[1]);
const result=await Effect.runPromise(Effect.gen(function*(){const r=yield* CanonicalAtomV2DurableRuntime; const opened=yield* readContextTopology(r,input.key,'child event');
const executed=yield* executeContextActivation(r,opened.plan,{policyKey:opened.policyKey,features:{encoderRevision:'fixture/v1',eventSha256:contextHash('child event'),values:[1]},mode:'EXPLOIT'},
{base_url:'https://fixture.invalid/v1',model:'SCRIPTED',max_tokens:32},{postJson:()=>Effect.succeed(new TextEncoder().encode(JSON.stringify({choices:[{message:{content:JSON.stringify({prediction:'1',uncertainty:'SCRIPTED_CHILD'})}}]})))},input.presentation);
return {revision:opened.policyKey.revisionId,roots:executed.assembly.payload.frames.map(f=>f.relation.key.atomUid),prediction:executed.trace.prediction};
}).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(input.root,'loop-test',new TextEncoder().encode(JSON.stringify(input.schema)))),Effect.provide(NodePosixServicesLive))); console.log(JSON.stringify(result));`
  const child = yield* Effect.try(() => JSON.parse(execFileSync(process.execPath, ["--input-type=module", "-e", script, JSON.stringify({ root, schema, key: key("policy:topology"), presentation })], { cwd, encoding: "utf8", timeout: 60000, maxBuffer: 1048576 })))
  expect(child).toEqual({ revision: 2, roots: ["rule:mandatory", "rule:a"], prediction: "1" })
  const restoreBefore = yield* prepareSemanticContext(runtime, afterSpec)
  const restore = yield* prepareContextTopologyChange(runtime, restoreBefore, { operation: "RESTORE", afterSpec: spec, policyKey: key("policy:w", 2), basis: null, priorTopologyKey: key("policy:topology"),
    topologyTarget: target("policy:topology", 1), activationTarget: target("policy:w", 3) })
  yield* runtime.submit(restore.candidate)
  expect((yield* readContextTopology(runtime, key("policy:topology", 1), spec.event)).plan.spec).toEqual(spec)
  expect((yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")).toEqual(original)
  const projection = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
  yield* verifyCanonicalAtomV2DurableRdfProjection(runtime, projection)
}))), 120000)
