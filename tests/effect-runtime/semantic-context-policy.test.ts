import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { type BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { type PosixFileSystem } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"
import { type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { contextHash, type ContextPlan } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { bindContextLearning, validateContextPolicyEvidence } from "../../src/hswm/effect-runtime/src/semantic-context-policy-domain.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { assembleContextPolicy, executeContextPolicy, prepareBaselineContextPolicy, prepareLearnedContextPolicy, prepareContextPolicyRestore, selectContextPolicy } from "../../src/hswm/effect-runtime/src/semantic-context-policy-runtime.js"
import { semanticContextProcess } from "../../src/hswm/effect-runtime/src/semantic-context-process.js"
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
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "context-policy-journal", schemaBytes, [{ authorizationRef: "fixture-auth", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["fixture"] }])
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const fixture = <A, E>(use: (runtime: Runtime, root: string) => Effect.Effect<A, E, BoundedSubprocess | PosixFileSystem>) => Effect.runPromise(Effect.acquireUseRelease(
  Effect.sync(() => mkdtempSync(join(tmpdir(), "context-policy-"))),
  root => seedContext.pipe(Effect.flatMap(runtime => use(runtime, root)), Effect.provide(layer(root))),
  root => Effect.sync(() => rmSync(root, { recursive: true, force: true }))
).pipe(Effect.provide(NodePosixServicesLive)))
const target = (revisionId: number) => ({ key: { ...key("policy:context"), revisionId }, owner: "owner:context-test", authorizationRef: "fixture-auth", scope: "fixture", decidedAt: "2026-10-11T00:00:00.000Z" })
const decision = (revisionId: number) => ({ contract: "hswm-context-policy-decision/v1", policyKey: target(revisionId).key })

// Native trust-boundary fixture; actual W recomputation is covered by the cross-repository executable.
const evidenceFor = (plan: ContextPlan) => {
  const binding = unwrap(bindContextLearning(plan, "calendar"))
  const baseline = binding.graph.placements[0]?.actionUid
  const chosen = binding.actionCandidates.find(a => a.candidateId === "door")?.actionUid
  const contextUid = binding.graph.contexts[0]?.uid
  const report = { schema: "hswm-w-report/v1", inputDigest: "a".repeat(64), provenance: { dataKind: "SYNTHETIC", observedOperationalEfficacy: null },
    policy: { trainDigest: "b".repeat(64), contexts: [{ uid: "policy:external", contextUid, contextRevision: binding.scopeSha256, baselineActionUid: baseline, chosenActionUid: chosen, status: "LEARNED_CANDIDATE" }] },
    evaluations: [{ uid: "evaluation:external", contextUid, policyUid: "policy:external", status: "READY_FOR_OWNER_REVIEW", requiredCoverageViolations: 0 }],
    proposals: [{ contextUid, status: "READY_FOR_OWNER_REVIEW", expectedGraphDigest: contextHash(binding.graph), readSet: { policyUid: "policy:external", evaluationUid: "evaluation:external" }, before: { actionUid: baseline }, after: { actionUid: chosen } }] }
  return { contract: "hswm-context-policy-evidence/v1", bindingSha256: binding.bindingSha256, graphSha256: contextHash(binding.graph), baselineCandidateId: "calendar", selectedCandidateId: "door", reportSha256: contextHash(report), report, authority: "SECONDARY_AI_EXTERNAL_EVALUATION_NOT_ADMISSION", observedOperationalEfficacy: null }
}
const initialize = (runtime: Runtime) => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const proposal = yield* prepareBaselineContextPolicy(runtime, plan, "calendar", target(0))
  yield* runtime.submit(proposal.candidate)
  return yield* prepareSemanticContext(runtime, spec)
})

it("binds complete multi-frame incidence and source descriptors without parsing/re-encoding originals", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const binding = yield* bindContextLearning(plan, "calendar")
  expect(binding.sources).toHaveLength(20)
  expect(binding.graph.actions.map(a => a.members.length)).toEqual([15, 10])
  expect(binding.graph.contexts[0]?.requiredRules).toHaveLength(5)
  expect(binding.incidences.every(i => i.participants.map(p => p.role).join(",") === "subject,context,evidence,exception")).toBe(true)
  for (const source of binding.sources) expect((yield* runtime.readContent(source.content)).length).toBe(source.content.byteLength)
  const { bindingSha256, ...body } = binding
  expect(contextHash(body)).toBe(bindingSha256)
})))

it("changes the next assembled/executed context only after owner admission, survives reopening and restores by successor", () => fixture((runtime, root) => Effect.gen(function* () {
  const plan = yield* initialize(runtime)
  const before = yield* assembleContextPolicy(runtime, plan, decision(0))
  expect(before.assembly?.payload.frames.map(f => f.relation.key.atomUid)).toEqual(["relation:mandatory", "relation:calendar"])
  const proposal = yield* prepareLearnedContextPolicy(runtime, plan, "calendar", evidenceFor(plan), target(1))
  expect((yield* selectContextPolicy(runtime, plan, decision(0))).candidateId).toBe("calendar")
  const beforeAtoms = (yield* runtime.snapshot).canonical.atoms
  yield* runtime.submit(proposal.candidate)
  const changed = yield* prepareSemanticContext(runtime, spec)
  expect((yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")).toEqual(beforeAtoms.filter(a => a.kind !== "semantic_context_policy"))
  let calls = 0
  const executed = yield* executeContextPolicy(runtime, changed, decision(1), { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_NOT_REAL_MODEL", max_tokens: 32 }, {
    postJson: request => Effect.sync(() => {
      calls += 1
      const body = new TextDecoder().decode(request.body)
      expect(body).toContain("door:exception")
      expect(body).toContain("relation:companion")
      expect(body).not.toContain("calendar:subject")
      return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "deny", uncertainty: "synthetic" }) } }] }))
    })
  })
  expect(calls).toBe(1)
  expect(executed.selection).toMatchObject({ candidateId: "door", selectionProbability: 1, confidence: null, policyKey: target(1).key })
  expect(executed.selection.distribution.map(p => p.probability)).toEqual([1, 0])
  expect(executed.trace).not.toBeNull()
  const reopened = yield* Effect.gen(function* () {
    const fresh = yield* CanonicalAtomV2DurableRuntime
    return yield* selectContextPolicy(fresh, yield* prepareSemanticContext(fresh, spec), decision(1))
  }).pipe(Effect.provide(layer(root)))
  expect(reopened.policyContent).toEqual(executed.selection.policyContent)
  const restore = yield* prepareContextPolicyRestore(runtime, changed, target(0).key, target(2))
  yield* runtime.submit(restore.candidate)
  const restored = yield* selectContextPolicy(runtime, yield* prepareSemanticContext(runtime, spec), decision(2))
  expect(restored.candidateId).toBe("calendar")
  expect((yield* runtime.snapshot).canonical.atoms.filter(a => a.kind === "semantic_context_policy")).toHaveLength(3)
})))

it("rejects stale policy keys, changed task/roles/budget and stale admission targets", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* initialize(runtime)
  const proposal = yield* prepareLearnedContextPolicy(runtime, plan, "calendar", evidenceFor(plan), target(1))
  yield* runtime.submit(proposal.candidate)
  const current = yield* prepareSemanticContext(runtime, spec)
  expect(Either.isLeft(yield* Effect.either(selectContextPolicy(runtime, current, decision(0))))).toBe(true)
  for (const changedSpec of [{ ...spec, event: "a different task" }, { ...spec, maximumContextBytes: 200 }, { ...spec, mandatoryRelationUids: [] }]) {
    const changed = yield* prepareSemanticContext(runtime, changedSpec)
    const result = yield* Effect.either(selectContextPolicy(runtime, changed, decision(1)))
    expect(Either.isLeft(result) && "code" in result.left && result.left.code).toBe("POLICY_SCOPE_STALE")
  }
  const snapshot = yield* runtime.snapshot
  const reordered = { ...runtime, snapshot: Effect.succeed({ ...snapshot, canonical: { ...snapshot.canonical,
    atoms: snapshot.canonical.atoms.map(a => a.key.atomUid === "relation:door" ? { ...a, references: [...a.references].reverse() } : a)
  } }) }
  const reorderedPlan = yield* prepareSemanticContext(reordered, spec)
  const reorderedRead = yield* Effect.either(selectContextPolicy(reordered, reorderedPlan, decision(1)))
  expect(Either.isLeft(reorderedRead) && "code" in reorderedRead.left && reorderedRead.left.code).toBe("POLICY_SCOPE_STALE")
  expect(Either.isLeft(yield* Effect.either(prepareLearnedContextPolicy(runtime, current, "calendar", evidenceFor(current), target(2))))).toBe(true)
  expect(Either.isLeft(yield* Effect.either(prepareBaselineContextPolicy(runtime, current, "calendar", target(0))))).toBe(true)
})))

it("rejects unsupported/foreign/tampered external evidence and unauthorized admission", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* initialize(runtime)
  const binding = yield* bindContextLearning(plan, "calendar")
  const evidence = evidenceFor(plan)
  for (const bad of [{ ...evidence, selectedCandidateId: "missing" }, { ...evidence, bindingSha256: "0".repeat(64) }, { ...evidence, reportSha256: "0".repeat(64) }, { ...evidence, observedOperationalEfficacy: 1 }, { confidence: 0.99 }]) {
    expect(Either.isLeft(validateContextPolicyEvidence(binding, bad))).toBe(true)
  }
  const unknown = { ...evidence.report, evaluations: evidence.report.evaluations.map(e => ({ ...e, status: "UNKNOWN" })) }
  expect(Either.isLeft(validateContextPolicyEvidence(binding, { ...evidence, report: unknown, reportSha256: contextHash(unknown) }))).toBe(true)
  const proposal = yield* prepareLearnedContextPolicy(runtime, plan, "calendar", evidence, { ...target(1), authorizationRef: "untrusted" })
  expect(Either.isLeft(yield* Effect.either(runtime.submit(proposal.candidate)))).toBe(true)
  expect((yield* selectContextPolicy(runtime, plan, decision(0))).candidateId).toBe("calendar")
})))

it("serves exact bindings and admitted policy selections through the existing CLI contract", () => fixture((runtime, root) => Effect.gen(function* () {
  const plan = yield* initialize(runtime)
  const common = { contract: "hswm-semantic-context-cli/v1", durableRoot: root, journalLineageId: "context-policy-journal", schema: policySchema, spec, expectedPlanSha256: plan.planSha256 }
  expect(yield* semanticContextProcess({ ...common, action: "learning-binding", baselineCandidateId: "calendar" })).toEqual(unwrap(bindContextLearning(plan, "calendar")))
  expect(yield* semanticContextProcess({ ...common, action: "policy-select", decision: decision(0) })).toMatchObject({ candidateId: "calendar", confidence: null })
  expect(Either.isLeft(yield* Effect.either(semanticContextProcess({ ...common, action: "assemble", decision: decision(0) })))).toBe(true)
  expect(Either.isLeft(yield* Effect.either(semanticContextProcess({ ...common, action: "policy-select", decision: decision(0), policyEvidence: {} })))).toBe(true)
})))
