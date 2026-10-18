import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { type BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { type PosixFileSystem } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"
import { contextHash, type ContextPlan } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { chooseActivation, initializeActivation, decodeActivationPolicy, updateActivation } from "../../src/hswm/effect-runtime/src/semantic-context-activation-domain.js"
import { prepareActivationInitialization, prepareActivationLearning, selectContextActivation, assembleContextActivation, executeContextActivation } from "../../src/hswm/effect-runtime/src/semantic-context-activation-runtime.js"
import { contextActivationProcess } from "../../src/hswm/effect-runtime/src/semantic-context-activation-process.js"
import { schema, spec, key, seedContext, unwrap } from "./semantic-context-fixture.js"

const policySchema: HSWMCanonicalSchemaV2 = { ...schema, kinds: [...schema.kinds, {
  kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: ["owner:context-test"], minimumArity: 1,
  referenceContracts: [
    { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
    { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }
  ]
}] }
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(policySchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "activation-test-journal", schemaBytes, [{ authorizationRef: "fixture-auth", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["fixture"] }])
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const fixture = <A, E>(use: (runtime: Runtime, root: string) => Effect.Effect<A, E, BoundedSubprocess | PosixFileSystem>) => Effect.runPromise(Effect.acquireUseRelease(
  Effect.sync(() => mkdtempSync(join(tmpdir(), "context-activation-"))),
  root => seedContext.pipe(Effect.flatMap(runtime => use(runtime, root)), Effect.provide(layer(root))),
  root => Effect.sync(() => rmSync(root, { recursive: true, force: true }))
).pipe(Effect.provide(NodePosixServicesLive)))
const config = { encoderRevision: "test-signal/v1", featureNames: ["bias", "signal"], alpha: 1 }
const target = (revisionId: number) => ({ key: { ...key("policy:activation"), revisionId }, owner: "owner:context-test", authorizationRef: "fixture-auth", scope: "fixture", decidedAt: "2026-10-18T00:00:00.000Z" })
const features = (plan: ContextPlan, signal: number) => ({ encoderRevision: config.encoderRevision, eventSha256: contextHash(plan.spec.event), values: [1, signal] })
const decision = (plan: ContextPlan, revision: number, signal: number, mode = "EXPLORE") => ({ policyKey: target(revision).key, features: features(plan, signal), mode })
const cell = { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_NOT_REAL_MODEL", max_tokens: 32 }
const scripted = { postJson: () => Effect.succeed(new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "observed", uncertainty: "scripted" }) } }] }))) }
const initialize = (runtime: Runtime) => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const proposal = yield* prepareActivationInitialization(runtime, plan, config, target(0))
  yield* runtime.submit(proposal.candidate)
  return yield* prepareSemanticContext(runtime, spec)
})

it("matches the ridge solution, learns only the selected arm, and rejects missing or malformed evidence", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const initial = yield* initializeActivation(plan, config)
  const learned = yield* updateActivation(initial, "door", features(plan, 1), 1, "a".repeat(64))
  expect(learned.arms[0]).toMatchObject({ a: [[2, 1], [1, 2]], b: [1, 1], observations: 1 })
  expect(learned.arms[1]).toEqual(initial.arms[1])
  const choice = yield* chooseActivation(plan, learned, features(plan, 1), "EXPLOIT")
  expect(choice.scores[0]?.mean).toBeCloseTo(2 / 3)
  expect(choice.scores[0]?.uncertaintyRadius).toBeCloseTo(Math.sqrt(2 / 3))
  for (const reward of [null, undefined, Number.NaN, -1, 2]) expect(Either.isLeft(updateActivation(initial, "door", features(plan, 1), reward, "b".repeat(64)))).toBe(true)
  for (const values of [[0, 0], [1], [1, Number.NaN], [1, 2]]) expect(Either.isLeft(chooseActivation(plan, learned, { ...features(plan, 1), values }, "EXPLOIT"))).toBe(true)
  expect(Either.isLeft(decodeActivationPolicy({ ...initial, arms: initial.arms.map(a => ({ ...a, observations: 3, a: [[1, 2], [2, 1]] })) }))).toBe(true)
  expect(Either.isLeft(chooseActivation(plan, learned, { ...features(plan, 1), encoderRevision: "changed" }, "EXPLOIT"))).toBe(true)
})))

it("executes, observes, admits numeric updates and changes activation across unseen inputs after reopening", () => fixture((runtime, root) => Effect.gen(function* () {
  yield* initialize(runtime)
  const sources = (yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")
  for (let revision = 0; revision < 12; revision++) {
    const signal = revision % 2 === 0 ? 1 : -1
    const plan = yield* prepareSemanticContext(runtime, { ...spec, event: `training ${revision}: signal=${signal}` })
    const executed = yield* executeContextActivation(runtime, plan, decision(plan, revision, signal), cell, scripted)
    if (!executed.trace) return yield* Effect.fail("missing trace")
    const expected = signal > 0 ? "door" : "calendar"
    const feedback = { traceContent: executed.trace.traceContent, reward: Number(executed.selection.candidateId === expected), observed: expected, source: "AUTHORED_FIXTURE_NOT_REAL_MODEL" }
    const proposal = yield* prepareActivationLearning(runtime, plan, feedback, target(revision + 1))
    expect((yield* selectContextActivation(runtime, plan, decision(plan, revision, signal))).policyKey.revisionId).toBe(revision)
    yield* runtime.submit(proposal.candidate)
    const fresh = yield* prepareSemanticContext(runtime, plan.spec)
    expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, fresh, feedback, target(revision + 2))))).toBe(true)
  }
  expect((yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")).toEqual(sources)
  yield* Effect.gen(function* () {
    const reopened = yield* CanonicalAtomV2DurableRuntime
    for (const signal of [0.75, -0.75]) {
      const plan = yield* prepareSemanticContext(reopened, { ...spec, event: `unseen signal=${signal}` })
      const assembled = yield* assembleContextActivation(reopened, plan, decision(plan, 12, signal, "EXPLOIT"))
      expect(assembled.selection.candidateId).toBe(signal > 0 ? "door" : "calendar")
      expect(assembled.assembly?.payload.frames.map(f => f.relation.key.atomUid)).toEqual(signal > 0 ? ["relation:mandatory", "relation:door", "relation:companion"] : ["relation:mandatory", "relation:calendar"])
      expect(assembled.assembly?.payload.frames.every(f => f.roles.map(p => p.role).join(",") === "subject,context,evidence,exception")).toBe(true)
      const api = yield* contextActivationProcess({ contract: "hswm-context-activation-cli/v1", action: "select", durableRoot: root,
        journalLineageId: "activation-test-journal", schema: policySchema, spec: plan.spec, expectedPlanSha256: plan.planSha256, decision: decision(plan, 12, signal, "EXPLOIT") })
      expect(api).toEqual(assembled.selection)
    }
  }).pipe(Effect.provide(layer(root)))
})), 120000)

it("rejects changed preservation, wrong event features, unexecuted feedback and unauthorized writes", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* initialize(runtime)
  const wrong = { ...decision(plan, 0, 1), features: { ...features(plan, 1), eventSha256: "a".repeat(64) } }
  expect(Either.isLeft(yield* Effect.either(selectContextActivation(runtime, plan, wrong)))).toBe(true)
  const changed = yield* prepareSemanticContext(runtime, { ...spec, mandatoryRelationUids: [] })
  expect(Either.isLeft(yield* Effect.either(selectContextActivation(runtime, changed, decision(changed, 0, 1))))).toBe(true)
  const fakeTrace = yield* runtime.stageContent("application/vnd.hswm.semantic-context-trace-v1+json", new TextEncoder().encode("{}"))
  expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, plan, { traceContent: fakeTrace, reward: 1, observed: "ok", source: "fake" }, target(1))))).toBe(true)
  const executed = yield* executeContextActivation(runtime, plan, decision(plan, 0, 1), cell, scripted)
  if (!executed.trace) return yield* Effect.fail("missing trace")
  const feedback = { traceContent: executed.trace.traceContent, reward: 1, observed: "ok", source: "test" }
  const proposal = yield* prepareActivationLearning(runtime, plan, feedback, { ...target(1), authorizationRef: "untrusted" })
  expect(Either.isLeft(yield* Effect.either(runtime.submit(proposal.candidate)))).toBe(true)
  expect((yield* selectContextActivation(runtime, plan, decision(plan, 0, 1))).policyKey.revisionId).toBe(0)
  const different = yield* prepareSemanticContext(runtime, { ...spec, event: "different event" })
  expect(Either.isLeft(yield* Effect.either(prepareActivationLearning(runtime, different, feedback, target(1))))).toBe(true)
})))
