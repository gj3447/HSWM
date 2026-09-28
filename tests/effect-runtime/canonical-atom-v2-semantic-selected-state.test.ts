import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { executeLlmSemanticRelation, learnLlmSemanticRelation, readLlmSemanticFrame, stageLlmSemanticOutcome, type LlmSemanticCell } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { admissionForSemanticLifecycle, authorizationRef, makeSemanticLifecycleFileLayer, relationUid, scope, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { deriveSemanticDurableBranch, reopenSelectedSemanticBranch, selectFrozenSemanticDurableCandidate } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-selected-state.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

const cell: LlmSemanticCell = { base_url: "https://fixture.invalid/v1", model: "fixture", max_tokens: 32 }
const response = (value: unknown) => new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))
const http = (values: ReadonlyArray<unknown>) => { let index = 0; return { postJson: () => Effect.sync(() => response(values[index++])) } }
const root = () => mkdtempSync(join(tmpdir(), "hswm-selected-real-"))
const runtimeAt = (path: string) => Effect.gen(function* () { return yield* CanonicalAtomV2DurableRuntime }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(path)))
const seedAt = (path: string) => seedSemanticLifecycle.pipe(Effect.provide(makeSemanticLifecycleFileLayer(path)))

it("selects a real learned durable branch and fresh-executes its selected semantic relation", async () => {
  const base = root(), candidate = root()
  await Effect.runPromise(Effect.gen(function* () {
    yield* seedAt(base); yield* seedAt(candidate)
    const candidateRuntime = yield* runtimeAt(candidate)
    const trace = yield* executeLlmSemanticRelation(candidateRuntime, relationUid, "train", cell, http([{ prediction: "p", uncertainty: "u" }]))
    const outcome = yield* stageLlmSemanticOutcome(candidateRuntime, trace, "observed", "fixture")
    const controller = yield* GraphLoopEngineeringController.pipe(Effect.provide(makeSemanticLifecycleFileLayer(candidate)))
    const admission = yield* admissionForSemanticLifecycle(candidateRuntime, controller, trace, outcome, "candidate")
    yield* learnLlmSemanticRelation(candidateRuntime, trace, outcome, cell, http([{ semanticText: "revised", disposition: "d", uncertainty: "u", exceptionRefs: ["exception:door"] }]), authorizationRef, scope, "2026-09-28T00:00:00.000Z", admission)
    const round = { baseline: { root: base, relationUid, runtime: yield* runtimeAt(base) }, candidate: { root: candidate, relationUid, runtime: candidateRuntime }, selectionSetId: "frozen-selection", expectedTraining: { traceSha256: trace.traceSha256, outcomeSha256: outcome.outcomeContent.sha256 }, assumptions: "CALLER_DECLARED_FINITE_CONTAMINATION_ALLOWANCE_AND_COST" as const, selection: { observations: [{ inputKey: "x", label: true, mass: 1n }], currentPredictions: { x: false }, candidatePredictions: { x: true }, allowance: 0n, debit: 0n } }
    const decision = yield* selectFrozenSemanticDurableCandidate(round)
    expect(decision.selected).toBe("CANDIDATE")
    const next = yield* reopenSelectedSemanticBranch(round, decision, path => runtimeAt(path).pipe(Effect.orDie), (runtime, uid) => executeLlmSemanticRelation(runtime, uid, "fresh", cell, http([{ prediction: "next", uncertainty: "u" }])).pipe(Effect.orDie))
    expect(next.relationKey.revisionId).toBe(1)
    expect((yield* readLlmSemanticFrame(yield* runtimeAt(base), relationUid, "baseline")).relation.key.revisionId).toBe(0)
    const fallbackRound = { ...round, baseline: { ...round.baseline, runtime: yield* runtimeAt(base) }, selection: { ...round.selection, currentPredictions: { x: true }, candidatePredictions: { x: true } } }
    const fallback = yield* selectFrozenSemanticDurableCandidate(fallbackRound)
    expect(fallback.selected).toBe("BASELINE")
    const fallbackNext = yield* reopenSelectedSemanticBranch(fallbackRound, fallback, path => runtimeAt(path).pipe(Effect.orDie), (runtime, uid) => executeLlmSemanticRelation(runtime, uid, "fallback", cell, http([{ prediction: "fallback", uncertainty: "u" }])).pipe(Effect.orDie))
    expect(fallbackNext.relationKey.revisionId).toBe(0)
    const switched = { ...decision, selected: "BASELINE" as const, selectedBranch: yield* deriveSemanticDurableBranch({ root: base, relationUid, runtime: yield* runtimeAt(base) }) }
    let switchedNextCalled = false
    expect((yield* reopenSelectedSemanticBranch(round, switched, path => runtimeAt(path).pipe(Effect.orDie), () => Effect.sync(() => { switchedNextCalled = true })).pipe(Effect.either))._tag).toBe("Left")
    expect(switchedNextCalled).toBe(false)
    const forged = { ...decision, selectedBranch: { ...decision.selectedBranch, stateSha256: "0".repeat(64) } }
    expect((yield* reopenSelectedSemanticBranch(round, forged, path => runtimeAt(path).pipe(Effect.orDie), (runtime, uid) => readLlmSemanticFrame(runtime, uid, "forged").pipe(Effect.orDie)).pipe(Effect.either))._tag).toBe("Left")
    const roleDrift = { ...decision, candidateBranch: { ...decision.candidateBranch, roles: decision.candidateBranch.roles.map((role, index) => index === 0 ? { ...role, role: "renamed-role" } : role) } }
    expect((yield* reopenSelectedSemanticBranch(round, roleDrift, path => runtimeAt(path).pipe(Effect.orDie), () => Effect.die("must not run")).pipe(Effect.either))._tag).toBe("Left")
    const sameAggregateRows = { ...round, selection: { ...round.selection, observations: [{ inputKey: "other-row", label: true, mass: 1n }], currentPredictions: { "other-row": false }, candidatePredictions: { "other-row": true } } }
    expect((yield* reopenSelectedSemanticBranch(sameAggregateRows, decision, path => runtimeAt(path).pipe(Effect.orDie), () => Effect.die("must not run")).pipe(Effect.either))._tag).toBe("Left")
    const wrongReceiptRound = { ...round, expectedTraining: { traceSha256: "f".repeat(64), outcomeSha256: outcome.outcomeContent.sha256 } }
    expect((yield* selectFrozenSemanticDurableCandidate(wrongReceiptRound).pipe(Effect.either))._tag).toBe("Left")
    const mutationTrace = yield* executeLlmSemanticRelation(candidateRuntime, relationUid, "mutate-after-selection", cell, http([{ prediction: "mutate", uncertainty: "u" }]))
    const mutationOutcome = yield* stageLlmSemanticOutcome(candidateRuntime, mutationTrace, "observed-again", "fixture")
    const mutationAdmission = yield* admissionForSemanticLifecycle(candidateRuntime, controller, mutationTrace, mutationOutcome, "mutation")
    yield* learnLlmSemanticRelation(candidateRuntime, mutationTrace, mutationOutcome, cell, http([{ semanticText: "revised-again", disposition: "d", uncertainty: "u", exceptionRefs: ["exception:door"] }]), authorizationRef, scope, "2026-09-28T00:01:00.000Z", mutationAdmission)
    let mutatedNextCalled = false
    expect((yield* reopenSelectedSemanticBranch(round, decision, path => runtimeAt(path).pipe(Effect.orDie), () => Effect.sync(() => { mutatedNextCalled = true })).pipe(Effect.either))._tag).toBe("Left")
    expect(mutatedNextCalled).toBe(false)
  }).pipe(Effect.provide(NodePosixServicesLive), Effect.ensuring(Effect.sync(() => { rmSync(base, { recursive: true, force: true }); rmSync(candidate, { recursive: true, force: true }) }))))
})
