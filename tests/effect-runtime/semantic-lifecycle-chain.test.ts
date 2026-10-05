import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { executeLlmSemanticRelation, learnLlmSemanticRelation, stageLlmSemanticOutcome } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { admissionForSemanticLifecycle, authorizationRef, makeSemanticLifecycleFileLayer, relationUid, scope, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { reopenSelectedSemanticBranch, selectFrozenSemanticDurableCandidate } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-selected-state.js"
import { projectSemanticLifecycleRefinement } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-refinement.js"
import { assembleSemanticLifecycleChain, type SemanticLifecycleWire } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-chain.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

const cell = { base_url: "https://fixture.invalid/v1", model: "scripted-chain-adapter", max_tokens: 32 }
const http = (value: unknown) => ({ postJson: () => Effect.succeed(new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))) })
const runtimeAt = (path: string) => CanonicalAtomV2DurableRuntime.pipe(Effect.provide(makeSemanticLifecycleFileLayer(path)))

/** Real file-store revisions, frozen branch copies and fresh reopen per round. */
const runRounds = (decisions: readonly boolean[]) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-chain-"))
  return Effect.gen(function* () {
    let selectedRoot = join(root, "seed")
    yield* seedSemanticLifecycle.pipe(Effect.provide(makeSemanticLifecycleFileLayer(selectedRoot)))
    const wires: SemanticLifecycleWire[] = []
    for (const [i, chooseCandidate] of decisions.entries()) {
      const baselineRoot = join(root, `baseline-${i}`), candidateRoot = join(root, `candidate-${i}`)
      // Preserve journal hard links, as the native lifecycle runner does.
      yield* Effect.sync(() => {
        execFileSync("cp", ["-a", "--", selectedRoot, baselineRoot])
        execFileSync("cp", ["-a", "--", selectedRoot, candidateRoot])
      })
      const baselineRuntime = yield* runtimeAt(baselineRoot), candidateRuntime = yield* runtimeAt(candidateRoot)
      const trainingTrace = yield* executeLlmSemanticRelation(candidateRuntime, relationUid, `train-${i}`, cell, http({ prediction: `p-${i}`, uncertainty: "u" }))
      const trainingOutcome = yield* stageLlmSemanticOutcome(candidateRuntime, trainingTrace, `observation-${i}`, "authored-fixture")
      const controller = yield* GraphLoopEngineeringController.pipe(Effect.provide(makeSemanticLifecycleFileLayer(candidateRoot)))
      const admission = yield* admissionForSemanticLifecycle(candidateRuntime, controller, trainingTrace, trainingOutcome, `round-${i}`)
      yield* learnLlmSemanticRelation(candidateRuntime, trainingTrace, trainingOutcome, cell,
        http({ semanticText: `revision from round ${i}`, disposition: "predict", uncertainty: "u", exceptionRefs: ["exception:door"] }),
        authorizationRef, scope, "2026-10-05T00:00:00.000Z", admission)
      const baseline = { root: baselineRoot, relationUid, runtime: baselineRuntime }, candidate = { root: candidateRoot, relationUid, runtime: candidateRuntime }
      const round = { baseline, candidate, selectionSetId: `authored-round-${i}`,
        expectedTraining: { traceSha256: trainingTrace.traceSha256, outcomeSha256: trainingOutcome.outcomeContent.sha256 },
        assumptions: "CALLER_DECLARED_FINITE_CONTAMINATION_ALLOWANCE_AND_COST" as const,
        selection: { observations: [{ inputKey: "x", label: true, mass: 1n }], currentPredictions: { x: !chooseCandidate }, candidatePredictions: { x: true }, allowance: 0n, debit: 0n } }
      const selection = yield* selectFrozenSemanticDurableCandidate(round)
      expect(selection.selected).toBe(chooseCandidate ? "CANDIDATE" : "BASELINE")
      const executed = yield* reopenSelectedSemanticBranch(round, selection, path => runtimeAt(path).pipe(Effect.orDie), (runtime, uid) =>
        executeLlmSemanticRelation(runtime, uid, `next-${i}`, cell, http({ prediction: `next-${i}`, uncertainty: "u" })).pipe(
          Effect.map(nextTrace => ({ selectedRuntime: runtime, nextTrace })), Effect.orDie))
      wires.push(yield* projectSemanticLifecycleRefinement({ baseline, candidate, selection, trainingTrace, trainingOutcome, ...executed }))
      selectedRoot = chooseCandidate ? candidateRoot : baselineRoot
    }
    return wires
  }).pipe(Effect.provide(NodePosixServicesLive), Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}

it("requires a nonempty bounded chain", () => {
  expect(assembleSemanticLifecycleChain([])._tag).toBe("Left")
})

it.runIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1")("replays mixed selected/rejected durable rounds and rejects state splices and changed evidence", async () => {
  const binary = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMSemanticLifecycleCli")
  const check = (wire: unknown): boolean => JSON.parse(execFileSync(binary, [], { input: JSON.stringify(wire), encoding: "utf8", timeout: 15000 })).accepted
  const observations = []
  for (const decisions of [[true, false, true], [false, true, false]]) {
    const rounds = await Effect.runPromise(runRounds(decisions))
    const composed = assembleSemanticLifecycleChain(rounds)
    if (Either.isLeft(composed)) throw composed.left
    const chain = composed.right
    expect(check(chain)).toBe(true)
    for (const round of rounds) expect(check(round)).toBe(true)
    expect(Object.isFrozen(chain.rounds[0]?.before.relation.semantic)).toBe(true)
    const last = rounds.at(-1)!
    const final = last.selectedCandidate ? last.after : last.before
    expect(final.stateRevision).toBe(rounds[0]!.before.stateRevision + decisions.filter(Boolean).length)
    expect(final.relation.roles).toEqual(rounds[0]!.before.relation.roles)
    const mutations: [string, unknown][] = [
      ["empty", { ...chain, rounds: [] }],
      ["swapped_rounds", { ...chain, rounds: [rounds[1], rounds[0], rounds[2]] }],
      ["replayed_old_round", { ...chain, rounds: [rounds[0], rounds[0], rounds[2]] }],
      ["wrong_middle_state", { ...chain, rounds: rounds.map((r, i) => i === 1 ? { ...r, before: { ...r.before, stateRevision: 999 } } : r) }],
      ["wrong_middle_outcome", { ...chain, rounds: rounds.map((r, i) => i === 1 ? { ...r, outcome: { ...r.outcome, traceSha256: "0".repeat(64) } } : r) }],
      ["flipped_selection", { ...chain, rounds: rounds.map((r, i) => i === 1 ? { ...r, selectedCandidate: !r.selectedCandidate } : r) }],
      ["removed_exception", { ...chain, rounds: rounds.map((r, i) => i === 1 ? { ...r, after: { ...r.after, relation: { ...r.after.relation, semantic: { ...r.after.relation.semantic, exceptionRefs: [] } } } } : r) }]
    ]
    for (const [name, mutation] of mutations) expect(check(mutation), name).toBe(false)
    const splice = rounds.map((r, i) => i === 1 ? { ...r, before: { ...r.before, stateRevision: 999 } } : r)
    expect(assembleSemanticLifecycleChain(splice)._tag).toBe("Left")
    // The assembler copies, but does not certify, each round. The Lean checker
    // independently rejects a field corruption with unchanged state joins.
    const corrupt = rounds.map((r, i) => i === 1 ? { ...r, outcome: { ...r.outcome, traceSha256: "0".repeat(64) } } : r)
    const unverified = assembleSemanticLifecycleChain(corrupt)
    expect(unverified._tag).toBe("Right")
    if (Either.isRight(unverified)) expect(check(unverified.right)).toBe(false)
    observations.push({ decisions, initialRevision: rounds[0]!.before.stateRevision, finalRevision: final.stateRevision,
      singleRoundChecks: rounds.length, accepted: true, rejectedMutations: mutations.map(([name]) => name), chain })
  }
  const output = process.env["HSWM_SEMANTIC_CHAIN_ARTIFACT_DIR"]
  if (output !== undefined) {
    mkdirSync(output, { recursive: false, mode: 0o700 })
    writeFileSync(join(output, "runtime-verification.v1.json"), JSON.stringify({ schema_version: "hswm-semantic-chain-runtime-verification/v1",
      status: "PASS_SCRIPTED_DURABLE_CHAIN_NOT_EFFICACY", observedAt: new Date().toISOString(),
      checkerBinarySha256: createHash("sha256").update(readFileSync(binary)).digest("hex"), observations,
      realModelCalls: 0, fullStoreRefinementProved: false, externalOutcomeTruthVerified: false }, null, 2) + "\n", { flag: "wx", mode: 0o600 })
  }
}, 60_000)
