import { execFileSync } from "node:child_process"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { executeLlmSemanticRelation, learnLlmSemanticRelation, stageLlmSemanticOutcome } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { admissionForSemanticLifecycle, authorizationRef, makeSemanticLifecycleFileLayer, relationUid, scope, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { reopenSelectedSemanticBranch, selectFrozenSemanticDurableCandidate } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-selected-state.js"
import { projectSemanticLifecycleRefinement, type SemanticLifecycleRefinementInput } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-refinement.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

const cell = { base_url: "https://fixture.invalid/v1", model: "scripted-proof-adapter", max_tokens: 32 }
const http = (value: unknown) => ({ postJson: () => Effect.succeed(new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))) })
const runtimeAt = (path: string) => CanonicalAtomV2DurableRuntime.pipe(Effect.provide(makeSemanticLifecycleFileLayer(path)))
const example = <A>(candidateSelected: boolean, use: (input: SemanticLifecycleRefinementInput) => Effect.Effect<A, unknown, never>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-lean-semantic-"))
  const baselineRoot = join(root, "baseline"), candidateRoot = join(root, "candidate")
  return Effect.gen(function* () {
    yield* seedSemanticLifecycle.pipe(Effect.provide(makeSemanticLifecycleFileLayer(baselineRoot)))
    yield* seedSemanticLifecycle.pipe(Effect.provide(makeSemanticLifecycleFileLayer(candidateRoot)))
    const baselineRuntime = yield* runtimeAt(baselineRoot), candidateRuntime = yield* runtimeAt(candidateRoot)
    const trainingTrace = yield* executeLlmSemanticRelation(candidateRuntime, relationUid, "train", cell, http({ prediction: "p", uncertainty: "u" }))
    const trainingOutcome = yield* stageLlmSemanticOutcome(candidateRuntime, trainingTrace, "external-observation", "authored-fixture")
    const controller = yield* GraphLoopEngineeringController.pipe(Effect.provide(makeSemanticLifecycleFileLayer(candidateRoot)))
    const admission = yield* admissionForSemanticLifecycle(candidateRuntime, controller, trainingTrace, trainingOutcome, "candidate")
    yield* learnLlmSemanticRelation(candidateRuntime, trainingTrace, trainingOutcome, cell,
      http({ semanticText: "changed relation", disposition: "predict", uncertainty: "u", exceptionRefs: ["exception:door"] }), authorizationRef, scope, "2026-09-28T00:00:00.000Z", admission)
    const baseline = { root: baselineRoot, relationUid, runtime: baselineRuntime }, candidate = { root: candidateRoot, relationUid, runtime: candidateRuntime }
    const round = { baseline, candidate, selectionSetId: "frozen-proof-adapter", expectedTraining: { traceSha256: trainingTrace.traceSha256, outcomeSha256: trainingOutcome.outcomeContent.sha256 },
      assumptions: "CALLER_DECLARED_FINITE_CONTAMINATION_ALLOWANCE_AND_COST" as const,
      selection: { observations: [{ inputKey: "x", label: true, mass: 1n }], currentPredictions: { x: !candidateSelected }, candidatePredictions: { x: true }, allowance: 0n, debit: 0n } }
    const selection = yield* selectFrozenSemanticDurableCandidate(round)
    const executed = yield* reopenSelectedSemanticBranch(round, selection, path => runtimeAt(path).pipe(Effect.orDie), (runtime, uid) =>
      executeLlmSemanticRelation(runtime, uid, "fresh-next", cell, http({ prediction: "next", uncertainty: "u" })).pipe(Effect.map(nextTrace => ({ selectedRuntime: runtime, nextTrace })), Effect.orDie))
    return yield* use({ baseline, candidate, selection, trainingTrace, trainingOutcome, ...executed })
  }).pipe(Effect.provide(NodePosixServicesLive), Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}

it("projects actual durable request/response/history and rejects unbound reports or changed bytes", async () => {
  await Effect.runPromise(example(true, input => Effect.gen(function* () {
    const wire = yield* projectSemanticLifecycleRefinement(input)
    expect(wire.after.relation.semantic.semanticText).toBe("changed relation")
    expect(wire.retainedBefore).toEqual(wire.before.relation)
    expect(wire.nextFrame.relationKey).toEqual(wire.after.relation.key)
    const mismatched = yield* projectSemanticLifecycleRefinement({ ...input, trainingTrace: { ...input.trainingTrace, prediction: "forged" } }).pipe(Effect.either)
    expect(mismatched._tag).toBe("Left")
    const changed = { ...input.candidate.runtime, readContent: (descriptor: Parameters<typeof input.candidate.runtime.readContent>[0]) =>
      descriptor.sha256 === input.trainingTrace.traceContent.sha256
        ? Effect.succeed(new TextEncoder().encode("{}")) : input.candidate.runtime.readContent(descriptor) }
    const changedBytes = yield* projectSemanticLifecycleRefinement({ ...input, candidate: { ...input.candidate, runtime: changed } }).pipe(Effect.either)
    expect(changedBytes._tag).toBe("Left")
  })))
})

it.runIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1")("runs the proved Lean checker on real candidate/baseline artifacts and rejects structural mutations", async () => {
  const binary = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMSemanticLifecycleCli")
  const check = (wire: unknown): boolean => JSON.parse(execFileSync(binary, [], { input: JSON.stringify(wire), encoding: "utf8", timeout: 15000 })).accepted
  for (const candidateSelected of [true, false]) {
    await Effect.runPromise(example(candidateSelected, input => Effect.gen(function* () {
      const wire = yield* projectSemanticLifecycleRefinement(input)
      expect(check(wire)).toBe(true)
      const mutations = [
        { ...wire, trace: { ...wire.trace, event: "wrong-event" } },
        { ...wire, outcome: { ...wire.outcome, traceSha256: "0".repeat(64) } },
        { ...wire, after: { ...wire.after, stateRevision: wire.after.stateRevision + 1 } },
        { ...wire, after: { ...wire.after, relation: { ...wire.after.relation, roles: [...wire.after.relation.roles].reverse() } } },
        { ...wire, after: { ...wire.after, relation: { ...wire.after.relation, semantic: { ...wire.after.relation.semantic, exceptionRefs: [] } } } },
        { ...wire, revision: { ...wire.revision, semanticText: "not-the-stored-revision" } },
        { ...wire, retainedBefore: { ...wire.retainedBefore, owner: "another-owner" } },
        { ...wire, afterPredecessorKey: wire.after.relation.key },
        { ...wire, selectedCandidate: !wire.selectedCandidate },
        { ...wire, nextTrace: { ...wire.nextTrace, backendConfigurationSha256: "0".repeat(64) } },
        { ...wire, nextTrace: { ...wire.nextTrace, event: "another-next-event" } }
      ]
      for (const mutation of mutations) expect(check(mutation)).toBe(false)
    })))
  }
}, 30000)
