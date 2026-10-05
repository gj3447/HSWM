import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { GraphLoopControlError, GraphLoopControlJournal, GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { INITIAL_TEXT, inspectSemanticLifecycleState, makeSemanticLifecycleFileLayer, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

const withRoot = async (use: (root: string) => Promise<void>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-semantic-bootstrap-"))
  try { await use(root) } finally { rmSync(root, { recursive: true, force: true }) }
}

it("admits genesis through a durable graph-loop record, reopens it, and refuses repeated bootstrap", async () => withRoot(async root => {
  const beforeReopen = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const journal = yield* GraphLoopControlJournal
    const evolution = yield* seedSemanticLifecycle
    expect(evolution.state.canonical.revision).toBe(1)
    expect(evolution.state.canonical.atoms).toHaveLength(5)
    const state = yield* inspectSemanticLifecycleState
    expect(state.relationKey.revisionId).toBe(0)
    expect(state.semantic.semanticText).toBe(INITIAL_TEXT)
    expect(state.roleRefs.map(ref => ref.role)).toEqual(["subject", "context", "evidence", "exception"])
    const entries = yield* journal.recover
    expect(entries.map(entry => entry.event.phase)).toEqual(["TRIGGERED", "ACTION_SEALED", "VERIFIED_ACCEPT", "DELTA_INTENT", "COMMITTED"])
    expect(entries.every(entry => entry.event.snapshot.stateRevision === 0)).toBe(true)
    expect(entries[0]!.event.actorId).not.toBe(entries[0]!.event.verifierId)
    expect(entries[4]!.event.transitionId).toBe("seed:semantic-lifecycle")
    const outcome = entries[2]!.event.outcome!
    const verdict = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(outcome)))
    expect(verdict).toMatchObject({ semanticCorrectness: "NOT_ADJUDICATED", efficacy: "NOT_ADJUDICATED" })
    const repeated = yield* seedSemanticLifecycle.pipe(Effect.either)
    expect(repeated).toMatchObject({ _tag: "Left", left: { reason: "RUN_ALREADY_EXISTS" } })
    expect(yield* inspectSemanticLifecycleState).toEqual(state)
    expect(yield* journal.recover).toEqual(entries)
    return { state, entries }
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
  const reopened = await Effect.runPromise(Effect.gen(function* () {
    const journal = yield* GraphLoopControlJournal
    return { state: yield* inspectSemanticLifecycleState, entries: yield* journal.recover }
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
  expect(reopened).toEqual(beforeReopen)
}))

it.each(["trigger", "sealAction", "recordVerification", "submitDelta"] as const)("does not create canonical state when %s fails", async method => withRoot(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const controller = yield* GraphLoopEngineeringController
    const before = yield* runtime.snapshot
    const blocked = { ...controller, [method]: () => Effect.fail(new GraphLoopControlError({ reason: "PHASE_INVALID", detail: "injected admission failure" })) }
    const result = yield* seedSemanticLifecycle.pipe(Effect.provideService(GraphLoopEngineeringController, blocked), Effect.either)
    expect(result).toMatchObject({ _tag: "Left", left: { reason: "PHASE_INVALID" } })
    expect(yield* runtime.snapshot).toEqual(before)
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
}))

it.each(["REJECTED", "QUARANTINED"] as const)("fails bootstrap on %s rather than reporting success", async disposition => withRoot(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const controller = yield* GraphLoopEngineeringController
    const before = yield* runtime.snapshot
    const blocked = { ...controller, submitDelta: () => Effect.succeed({ disposition, evolution: null }) }
    const result = yield* seedSemanticLifecycle.pipe(Effect.provideService(GraphLoopEngineeringController, blocked), Effect.either)
    expect(result).toMatchObject({ _tag: "Left", left: { code: "BOOTSTRAP_NOT_COMMITTED" } })
    expect(yield* runtime.snapshot).toEqual(before)
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
}))
