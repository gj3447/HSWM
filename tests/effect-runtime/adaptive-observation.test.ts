import { createHash } from "node:crypto"
import { Effect, Layer } from "effect"
import { expect, it } from "vitest"
import { type Context, evaluateGuard } from "../../src/hswm/effect-runtime/src/adaptive-domain.js"
import { type AdaptiveHttpClientShape } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { makeAdaptiveRuntime } from "../../src/hswm/effect-runtime/src/adaptive-runtime.js"
import { AdaptiveStore, type AdaptiveAtomRevision, makeAdaptiveStoreSqliteLayer } from "../../src/hswm/effect-runtime/src/adaptive-store.js"
import { NodeBoundedSubprocessLive } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

const eq = (field: string, right: string) => ({ op: "eq", left: { role: "context", field }, right })
const spec = (id: string, measured: boolean) => ({
  schema_version: "hswm-adaptive-program/v1", graph_id: id, root: "root",
  context_domain: { permit: ["yes", "no"], ready: ["yes", "no"], clean: ["yes", "no"] },
  cells: [
    { cell_id: "root", kind: "router", owner: "test", input_type: "task", output_type: "result" },
    measured
      ? { cell_id: "leaf", kind: "command", owner: "test", input_type: "task", output_type: "result", outcome: "exit_code", argv: [process.execPath, "-e", "let raw='';process.stdin.on('data',c=>raw+=c);process.stdin.on('end',()=>{process.stdout.write('checked');process.exit(JSON.parse(raw).task==='ok'?0:1)})"] }
      : { cell_id: "leaf", kind: "llm", owner: "test", input_type: "task", output_type: "result", base_url: "http://local.invalid", model: "mock" }
  ],
  relations: [{ uid: "base", source: "root", members: ["leaf"], reads: ["permit", "ready"], cost_hint: 1, guard: eq("permit", "yes") }]
})
const http: AdaptiveHttpClientShape = { postJson: () => Effect.succeed(Buffer.from('{"choices":[{"message":{"content":"checked"}}],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}}')) }
const run = <A, R>(effect: Effect.Effect<A, unknown, R>) => Effect.runPromise(Effect.scoped(effect.pipe(
  Effect.provide(Layer.mergeAll(makeAdaptiveStoreSqliteLayer(":memory:"), NodeBoundedSubprocessLive))
) as Effect.Effect<A, unknown>))
const data = (atom: AdaptiveAtomRevision) => atom.payload as Record<string, any>
const atoms = (graph: Record<string, unknown>) => graph["atoms"] as AdaptiveAtomRevision[]
const contexts = [["no", "no"], ["no", "yes"], ["yes", "no"], ["yes", "yes"]].map(([ready, clean]) => ({ permit: "yes", ready, clean }) as Context)

it.each([true, false])("preserves parent guard and exact historical pin for measured=%s specialization", async (measured) => {
  const id = `scope-${measured}`
  const result = await run(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec(id, measured), process.cwd(), { httpClient: http })
    const store = yield* AdaptiveStore
    for (const [index, context] of contexts.entries()) {
      yield* runtime.run(index === 3 ? "ok" : "fail", context, { episodeId: `e-${index}`, forceRoute: "base", exploration: 0 })
      if (!measured) yield* runtime.feedback(`e-${index}`, index === 3, "test:explicit-review")
    }
    const graph = yield* runtime.graph()
    const child = atoms(graph).find((atom) => atom.kind === "relation" && data(atom)["parent_relation"] === "relation:base")!
    const pin = data(child)["scope_binding"].parent
    const parent = yield* store.getRevision(id, pin.uid, pin.revision)
    const outside = yield* runtime["plan"]({ permit: "no", ready: "yes", clean: "yes" }, { exploration: 0 })
    const inside = yield* runtime["plan"](contexts[3]!, { exploration: 0 })
    return { child, parent, pin, outside, inside }
  }))
  expect(result.child).toBeDefined()
  expect(result.pin).toEqual({ uid: result.parent.uid, revision: result.parent.revision, digest: result.parent.digest })
  expect(result.parent.revision).toBe(4)
  expect(data(result.child)["members"]).toEqual(data(result.parent)["members"])
  expect(data(result.child)["scope_binding"].mandatory_guard).toEqual(eq("permit", "yes"))
  expect(evaluateGuard(data(result.child)["scope_binding"].selector, { permit: "no", ready: "yes", clean: "yes" })).toBe("TRUE")
  expect(result.outside.status).toBe("WITHHOLD")
  expect(result.outside.rejected.find((item) => item.uid === result.child.uid)?.reason).toBe("GUARD_FALSE")
  expect(result.inside.choices.some((item) => item.uid === result.child.uid)).toBe(true)
})

it("withholds legacy unbound children without rewriting history", async () => {
  const result = await run(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec("legacy-scope", false), process.cwd(), { httpClient: http })
    const store = yield* AdaptiveStore
    const parent = yield* store.getRevision("legacy-scope", "relation:base", 1)
    const child = { uid: "relation:legacy-child", kind: "relation", owner: parent.owner, refs: [{ role: "parent", uid: parent.uid }], payload: { ...data(parent), uid: "legacy-child", guard: eq("ready", "yes"), parent_relation: parent.uid } }
    yield* store.rewrite({ graphId: "legacy-scope", eventId: "historic-child", expected: { [child.uid]: 0 }, atoms: [child], source: { kind: "TEST_LEGACY_FIXTURE" } })
    const before = yield* store.getRevision("legacy-scope", child.uid, 1)
    const plan = yield* runtime["plan"]({ permit: "no", ready: "yes", clean: "yes" })
    for (const [index, context] of contexts.entries()) {
      yield* runtime.run("task", context, { episodeId: `new-${index}`, forceRoute: "base" })
      yield* runtime.feedback(`new-${index}`, index === 3, "test:review")
    }
    return { plan, before, after: yield* store.getRevision("legacy-scope", child.uid, 1), head: yield* store.head("legacy-scope", child.uid), graph: yield* runtime.graph() }
  }))
  expect(result["plan"].status).toBe("WITHHOLD")
  expect(result["plan"]["observation"]["candidates"]).toEqual(expect.arrayContaining([expect.objectContaining({ scope_status: "LEGACY_UNBOUND_SPECIALIZATION" })]))
  expect(result.head.revision).toBe(1)
  expect(result.before).toEqual(result.after)
  expect(atoms(result.graph).filter((atom) => atom.kind === "relation" && data(atom)["scope_binding"] !== undefined)).toHaveLength(1)
})

it("withholds late child feedback when the parent meaning changed", async () => {
  const result = await run(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec("child-late", false), process.cwd(), { httpClient: http })
    for (const [index, context] of contexts.entries()) {
      yield* runtime.run("task", context, { episodeId: `train-${index}`, forceRoute: "base" })
      yield* runtime.feedback(`train-${index}`, index === 3, "test:review")
    }
    const child = atoms(yield* runtime.graph()).find((atom) => atom.kind === "relation" && data(atom)["scope_binding"] !== undefined)!
    yield* runtime.run("task", contexts[3]!, { episodeId: "selected-child", forceRoute: child.uid })
    const store = yield* AdaptiveStore
    const parentHead = yield* store.head("child-late", "relation:base")
    const parent = yield* store.getRevision("child-late", "relation:base", parentHead.revision)
    yield* store.rewrite({ graphId: "child-late", eventId: "parent-changed", expected: { [parent.uid]: parent.revision }, atoms: [{ uid: parent.uid, kind: parent.kind, owner: parent.owner, refs: parent.refs, payload: { ...data(parent), guard: eq("permit", "no") } }], source: { kind: "TEST_PARENT_CHANGE" } })
    const feedback = yield* runtime.feedback("selected-child", true, "test:late-review")
    return { feedback, head: yield* store.head("child-late", child.uid), plan: yield* runtime.plan(contexts[3]!) }
  }))
  expect(result.feedback["learning_status"]).toBe("SELECTION_SCOPE_INVALID")
  expect(result.head.revision).toBe(1)
  expect(result.plan.status).toBe("WITHHOLD")
})

it("binds occurrence, output, selected version and leaf-only costs while leaving missing costs unknown", async () => {
  const result = await run(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec("observed", false), process.cwd(), { httpClient: http })
    const first = yield* runtime.run("task", contexts[3]!, { episodeId: "first", exploration: 0 })
    yield* runtime.feedback("first", true, "test:review")
    const graph = yield* runtime.graph()
    return { first, graph }
  }))
  const trace = atoms(result.graph).find((atom) => atom.uid === "trajectory:first:0")!
  const leaf = atoms(result.graph).find((atom) => atom.uid === "trajectory:first:1")!
  const relation = atoms(result.graph).find((atom) => atom.uid === "relation:base")!
  expect(data(trace)["observation"]["selected_relation"].revision).toBe(1)
  expect(relation.revision).toBe(2)
  expect(data(trace)["observation"].participants).toEqual([expect.objectContaining({ uid: "cell:leaf", revision: 1, ordinal: 0, role: "member" })])
  expect(data(leaf)["observation"].input_context).toEqual({ permit: "yes", ready: "yes" })
  expect(data(trace)["result"].output_digest).toBe(createHash("sha256").update("checked").digest("hex"))
  const costs = result.first["cost_observation"] as Record<string, unknown>
  expect(costs["leaf_occurrences"]).toEqual(["trajectory:first:1"])
  expect(costs["leaf_execution_seconds"]).toBe(data(leaf)["result"].duration_seconds)
  expect(costs["human_review_seconds"]).toBeNull()
  expect(costs["monetary_cost"]).toBeNull()
  expect(data(trace)["result"].metadata.execution_observation_v1).toBeUndefined()
  expect(data(leaf)["result"].metadata.execution_observation_v1.provider_usage.total_tokens).toBe(5)
  expect(data(trace)["plan"]["observation"].propensity).toBeNull()
})

it("preserves late feedback but withholds weight updates across changed relation meaning", async () => {
  const result = await run(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec("late", false), process.cwd(), { httpClient: http })
    yield* runtime.run("task", contexts[3]!, { episodeId: "first" })
    const store = yield* AdaptiveStore
    const parent = yield* store.getRevision("late", "relation:base", 1)
    yield* store.rewrite({ graphId: "late", eventId: "changed", expected: { [parent.uid]: 1 }, atoms: [{ uid: parent.uid, kind: parent.kind, owner: parent.owner, refs: parent.refs, payload: { ...data(parent), guard: eq("permit", "no") } }], source: { kind: "TEST_MEANING_CHANGE" } })
    const feedback = yield* runtime.feedback("first", true, "test:late-review")
    return { feedback, graph: yield* runtime.graph() }
  }))
  expect(result.feedback["learning_status"]).toBe("SELECTION_MEANING_CHANGED")
  expect(data(atoms(result.graph).find((atom) => atom.uid === "relation:base")!)["model"].n).toBe(0)
  expect(data(atoms(result.graph).find((atom) => atom.uid === "feedback:first")!)["selected_relation"].revision).toBe(1)
})
