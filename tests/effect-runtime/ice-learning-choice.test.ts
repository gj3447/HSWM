import { readFileSync, mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { fileURLToPath } from "node:url"

import { expect, it } from "vitest"
import { Effect, Layer } from "effect"

import { type Context } from "../../src/hswm/effect-runtime/src/adaptive-domain.js"
import { makeAdaptiveRuntime } from "../../src/hswm/effect-runtime/src/adaptive-runtime.js"
import { makeAdaptiveStoreSqliteLayer } from "../../src/hswm/effect-runtime/src/adaptive-store.js"
import { NodeBoundedSubprocessLive } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

const fixturePath = fileURLToPath(new URL("../../_research/causal_composition/ice_learning_choice_v1/counterexample-choice.v1.json", import.meta.url))
const workspace = fileURLToPath(new URL("../../", import.meta.url))
const program = JSON.parse(readFileSync(fixturePath, "utf8")) as Record<string, unknown>
const context = { evidence: "available", goal: "counterexample", candidate_n: 0 } as Context
const task = "synthetic counterexample investigation"

const durable = <A, R>(path: string, effect: Effect.Effect<A, unknown, R>): Promise<A> => {
  const provided = effect.pipe(Effect.provide(Layer.mergeAll(makeAdaptiveStoreSqliteLayer(path), NodeBoundedSubprocessLive))) as Effect.Effect<A, unknown, never>
  return Effect.runPromise(Effect.scoped(provided))
}

const relationModelN = (graph: Record<string, unknown>, uid: string): number => {
  const atom = (graph["atoms"] as ReadonlyArray<Record<string, unknown>>).find((candidate) => candidate["uid"] === `relation:${uid}`)
  const payload = atom?.["payload"] as Record<string, unknown>
  return (payload["model"] as Record<string, unknown>)["n"] as number
}

const visitedCells = (run: Record<string, unknown>): ReadonlyArray<string> =>
  (run["visits"] as ReadonlyArray<Record<string, unknown>>).map((visit) => visit["cell"] as string)

it("runs both equal-budget counterexample alternatives, then isolates frozen from local learning choice", async () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-ice-choice-"))
  const frozenState = join(directory, "frozen.sqlite")
  const learningState = join(directory, "learning.sqlite")
  try {
    const frozen = await durable(frozenState, Effect.gen(function* () {
      const runtime = yield* makeAdaptiveRuntime(program, workspace)
      const allowed = ["investigate", "check-existing", "construct-new", "complete-investigation"]
      const before = yield* runtime.plan(context, { budget: 1, allowed, exploration: 0 })
      const unavailable = yield* runtime.plan({ evidence: "unavailable", goal: "counterexample", candidate_n: 0 } as Context, { budget: 1, allowed, exploration: 0 })
      const check = yield* runtime.run(task, context, { episodeId: "frozen-check", forceRoute: "check-first", budget: 1, allowed, exploration: 0, learn: false })
      const construct = yield* runtime.run(task, context, { episodeId: "frozen-construct", forceRoute: "construct-first", budget: 1, allowed, exploration: 0, learn: false })
      return { before, unavailable, check, construct, after: yield* runtime.plan(context, { budget: 1, allowed, exploration: 0 }), graph: yield* runtime.graph() }
    }))

    const learned = await durable(learningState, Effect.gen(function* () {
      const runtime = yield* makeAdaptiveRuntime(program, workspace)
      const allowed = ["investigate", "check-existing", "construct-new", "complete-investigation"]
      yield* runtime.run(task, context, { episodeId: "learn-construct-1", forceRoute: "construct-first", budget: 1, allowed, exploration: 0, learn: true })
      yield* runtime.run(task, context, { episodeId: "learn-construct-2", forceRoute: "construct-first", budget: 1, allowed, exploration: 0, learn: true })
      return { plan: yield* runtime.plan(context, { budget: 1, allowed, exploration: 0 }), graph: yield* runtime.graph() }
    }))

    expect(frozen.before.choices.map((choice) => choice.uid)).toEqual(["relation:check-first", "relation:construct-first"])
    expect(frozen.before.rejected).toEqual([])
    expect(frozen.before.selected?.uid).toBe("relation:check-first")
    expect(frozen.unavailable.selected).toBeNull()
    expect(frozen.unavailable.rejected.map((choice) => choice.reason)).toEqual(["GUARD_FALSE", "GUARD_FALSE"])
    expect((frozen.check["result"] as Record<string, unknown>)["success"]).toBe(true)
    expect((frozen.construct["result"] as Record<string, unknown>)["success"]).toBe(true)
    expect(visitedCells(frozen.check)).toEqual(["check-existing", "construct-new", "complete-investigation", "investigate"])
    expect(visitedCells(frozen.construct)).toEqual(["construct-new", "check-existing", "complete-investigation", "investigate"])
    const checkResult = frozen.check["result"] as Record<string, unknown>
    const constructResult = frozen.construct["result"] as Record<string, unknown>
    expect(checkResult["output_digest"]).toMatch(/^[a-f0-9]{64}$/)
    expect(checkResult["output_digest"]).toBe(constructResult["output_digest"])
    expect(JSON.parse(checkResult["output"] as string)).toEqual({
      schema_version: "ice-learning-choice-artifact/v1",
      claim: "n*n>=n+1 for nonnegative integers",
      witnesses: [{ method: "check-existing", n: 0 }, { method: "construct-new", n: 0 }],
      status: "VALIDATED_SYNTHETIC_COUNTEREXAMPLE"
    })
    expect(frozen.after.selected?.uid).toBe("relation:check-first")
    expect(relationModelN(frozen.graph, "check-first")).toBe(0)
    expect(relationModelN(frozen.graph, "construct-first")).toBe(0)
    expect(learned.plan.selected?.uid).toBe("relation:construct-first")
    expect(relationModelN(learned.graph, "check-first")).toBe(0)
    expect(relationModelN(learned.graph, "construct-first")).toBe(2)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
