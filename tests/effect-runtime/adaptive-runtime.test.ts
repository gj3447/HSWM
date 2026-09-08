import { createServer } from "node:http"
import type { AddressInfo } from "node:net"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

import { expect, it } from "vitest"
import { Effect, Fiber, Layer } from "effect"

import { type Context } from "../../src/hswm/effect-runtime/src/adaptive-domain.js"
import { type AdaptiveHttpClientShape, executeAdaptiveCell } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { makeAdaptiveRuntime } from "../../src/hswm/effect-runtime/src/adaptive-runtime.js"
import { makeAdaptiveStoreSqliteLayer } from "../../src/hswm/effect-runtime/src/adaptive-store.js"
import { NodeBoundedSubprocessLive } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

const program = (graphId: string, cells: ReadonlyArray<Record<string, unknown>>, relations: ReadonlyArray<Record<string, unknown>>, domain: Record<string, ReadonlyArray<string | boolean>> = { mode: ["a", "b"] }) => ({
  schema_version: "hswm-adaptive-program/v1", graph_id: graphId, root: "root", context_domain: domain, cells, relations
})
const router = { cell_id: "root", kind: "router", owner: "test", input_type: "task", output_type: "result" }
const llm = (id: string, baseUrl = "http://local.invalid") => ({ cell_id: id, kind: "llm", owner: "test", input_type: "task", output_type: "result", base_url: baseUrl, model: "test" })
const command = (id: string, code: string, outcome: "exit_code" | undefined = "exit_code") => ({ cell_id: id, kind: "command", owner: "test", input_type: "task", output_type: "result", argv: [process.execPath, "-e", code], ...(outcome === undefined ? {} : { outcome }) })
const relation = (uid: string, members: ReadonlyArray<string>, reads: ReadonlyArray<string> = ["mode"], cost_hint = 1) => ({ uid, source: "root", members, reads, cost_hint })
const live = <A, R>(effect: Effect.Effect<A, unknown, R>) => {
  const provided = effect.pipe(Effect.provide(Layer.mergeAll(makeAdaptiveStoreSqliteLayer(":memory:"), NodeBoundedSubprocessLive))) as Effect.Effect<A, unknown, never>
  return Effect.runPromise(Effect.scoped(provided))
}
const durable = <A, R>(path: string, effect: Effect.Effect<A, unknown, R>) => {
  const provided = effect.pipe(Effect.provide(Layer.mergeAll(makeAdaptiveStoreSqliteLayer(path), NodeBoundedSubprocessLive))) as Effect.Effect<A, unknown, never>
  return Effect.runPromise(Effect.scoped(provided))
}
const payload = (graph: Record<string, unknown>, uid: string): Record<string, unknown> => {
  const atom = (graph["atoms"] as ReadonlyArray<Record<string, unknown>>).find((value) => value["uid"] === uid)
  return atom?.["payload"] as Record<string, unknown>
}

it("calls a local HTTP LLM, persists explicit feedback, and uses it for the next route choice", async () => {
  let calls = 0
  let requestBody = ""
  const server = createServer((request, response) => {
    calls += 1
    expect(request.url).toBe("/v1/chat/completions")
    request.on("data", (chunk: Buffer) => { requestBody += chunk.toString("utf8") })
    request.on("end", () => { response.setHeader("content-type", "application/json"); response.end('{"choices":[{"message":{"content":"observed"}}]}') })
  })
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
  const directory = mkdtempSync(join(tmpdir(), "hswm-adaptive-runtime-"))
  const database = join(directory, "runtime.sqlite")
  try {
    const spec = program("feedback-choice", [router, llm("left", baseUrl), llm("right", baseUrl)], [relation("left", ["left"]), relation("right", ["right"])])
    await durable(database, Effect.gen(function* () {
      const runtime = yield* makeAdaptiveRuntime(spec, process.cwd())
      yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "left", forceRoute: "left", exploration: 0, learn: true })
      return yield* runtime.feedback("left", false, "test:caller")
    }))
    const result = await durable(database, Effect.gen(function* () {
      const runtime = yield* makeAdaptiveRuntime(spec, process.cwd())
      return { graph: yield* runtime.graph(), plan: yield* runtime.plan({ mode: "a" } as Context, { exploration: 0 }) }
    }))
    expect(calls).toBe(1)
    expect(requestBody).toContain('"content":"task"')
    expect((payload(result.graph, "relation:left")["model"] as Record<string, unknown>)["n"]).toBe(1)
    expect(result.plan.selected?.uid).toBe("relation:right")
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error === undefined ? resolve() : reject(error)))
    rmSync(directory, { recursive: true, force: true })
  }
})

it("uses an LLM observation as typed command input, learns its checked outcome, then plans again", async () => {
  let calls = 0
  const server = createServer((request, response) => {
    calls += 1
    expect(request.url).toBe("/v1/chat/completions")
    request.resume()
    request.on("end", () => { response.setHeader("content-type", "application/json"); response.end('{"choices":[{"message":{"content":"42"}}]}') })
  })
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
  try {
    const candidate = { ...llm("candidate", baseUrl), output_type: "task" }
    const check = command("check", "let raw='';process.stdin.on('data', chunk => raw += chunk);process.stdin.on('end', () => process.exit(JSON.parse(raw).previous_output === '42' ? 0 : 1))")
    const spec = program("llm-command-learning", [router, candidate, check], [relation("base", ["candidate", "check"])])
    const result = await live(Effect.gen(function* () {
      const runtime = yield* makeAdaptiveRuntime(spec, process.cwd())
      const run = yield* runtime.run("answer", { mode: "a" } as Context, { episodeId: "observed", forceRoute: "base", learn: true, exploration: 0 })
      return { run, graph: yield* runtime.graph(), plan: yield* runtime.plan({ mode: "a" } as Context, { exploration: 0 }) }
    }))
    expect(calls).toBe(1)
    expect(((result.run["result"] as Record<string, unknown>)["success"])).toBe(true)
    expect((payload(result.graph, "relation:base")["model"] as Record<string, unknown>)["n"]).toBe(1)
    expect(result.plan.selected?.uid).toBe("relation:base")
  } finally { await new Promise<void>((resolve, reject) => server.close((error) => error === undefined ? resolve() : reject(error))) }
})

it("replays an identical episode without a second effect", async () => {
  let calls = 0
  const http: AdaptiveHttpClientShape = { postJson: () => Effect.sync(() => { calls += 1; return Buffer.from('{"choices":[{"message":{"content":"ok"}}]}') }) }
  const spec = program("replay", [router, llm("leaf")], [relation("base", ["leaf"])])
  const result = await live(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec, process.cwd(), { httpClient: http })
    yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "same", forceRoute: "base" })
    return yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "same", forceRoute: "base" })
  }))
  expect(calls).toBe(1)
  expect(result["replayed"]).toBe(true)
})

it("records router cost across every sequential member", async () => {
  const http: AdaptiveHttpClientShape = { postJson: () => Effect.sleep("35 millis").pipe(Effect.as(Buffer.from('{"choices":[{"message":{"content":"ok"}}]}'))) }
  const first = { ...llm("first"), output_type: "task" }
  const spec = program("composite-duration", [router, first, llm("second")], [relation("base", ["first", "second"])])
  const result = await live(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec, process.cwd(), { httpClient: http })
    return yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "chain", forceRoute: "base", learn: false })
  }))
  expect(((result["result"] as Record<string, unknown>)["duration_seconds"] as number)).toBeGreaterThanOrEqual(0.06)
})

it("times out commands, keeps frozen models unchanged, and restores relation history", async () => {
  const spec = program("frozen-restore", [router, command("slow", "setTimeout(() => process.exit(0), 2000)"), command("ok", "process.exit(0)")], [relation("slow", ["slow"]), relation("ok", ["ok"])])
  const result = await live(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec, process.cwd())
    const timed = yield* executeAdaptiveCell(command("direct", "setTimeout(() => process.exit(0), 2000)"), {}, process.cwd(), 20)
    const exactBudget = yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "frozen", forceRoute: "ok", budget: 1, learn: false })
    yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "learned", forceRoute: "ok", learn: true })
    const restored = yield* runtime.restore("relation:ok", 1, "restore-ok")
    const replayedRestore = yield* runtime.restore("relation:ok", 1, "restore-ok")
    const conflictingRestore = yield* Effect.exit(runtime.restore("relation:ok", 2, "restore-ok"))
    return { timed, exactBudget, restored, replayedRestore, conflictingRestore, graph: yield* runtime.graph() }
  }))
  expect(result.timed.status).toBe("UNKNOWN")
  expect((result.exactBudget["result"] as Record<string, unknown>)["status"]).toBe("SUCCEEDED")
  expect(result.replayedRestore["eventId"]).toBe(result.restored["eventId"])
  expect(result.conflictingRestore._tag).toBe("Failure")
  expect((payload(result.graph, "relation:ok")["model"] as Record<string, unknown>)["n"]).toBe(0)
})

it("rejects feedback while a local effect holds the runtime lock", async () => {
  const slowHttp: AdaptiveHttpClientShape = { postJson: () => Effect.sleep("100 millis").pipe(Effect.as(Buffer.from('{"choices":[{"message":{"content":"ok"}}]}'))) }
  const spec = program("lock", [router, llm("leaf")], [relation("base", ["leaf"])])
  const result = await live(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec, process.cwd(), { httpClient: slowHttp })
    const running = yield* Effect.fork(runtime.run("task", { mode: "a" } as Context, { episodeId: "running", forceRoute: "base" }))
    yield* Effect.sleep("10 millis")
    const blocked = yield* Effect.exit(runtime.feedback("running", true, "test:early"))
    yield* Fiber.join(running)
    return blocked
  }))
  expect(result._tag).toBe("Failure")
})

it("keeps a timed-out episode unresolved until feedback, then recovers without replaying it", async () => {
  const spec = program("timeout-recovery", [router, command("slow", "setTimeout(() => process.exit(0), 2000)"), command("ok", "process.exit(0)")], [relation("slow", ["slow"]), relation("ok", ["ok"])])
  const result = await live(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec, process.cwd())
    const timeout = yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "timeout", forceRoute: "slow", budget: 1 })
    const blocked = yield* Effect.exit(runtime.run("task", { mode: "a" } as Context, { episodeId: "blocked", forceRoute: "ok" }))
    yield* runtime.feedback("timeout", false, "test:timeout")
    const recovered = yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "recovered", forceRoute: "ok" })
    const replay = yield* runtime.run("task", { mode: "a" } as Context, { episodeId: "timeout", forceRoute: "slow", budget: 1 })
    return { timeout, blocked, recovered, replay }
  }))
  expect((result.timeout["result"] as Record<string, unknown>)["status"]).toBe("UNKNOWN")
  expect(result.blocked._tag).toBe("Failure")
  expect((result.recovered["result"] as Record<string, unknown>)["status"]).toBe("SUCCEEDED")
  expect(result.replay["replayed"]).toBe(true)
})

it("creates one bounded specialization after mixed observed contexts", async () => {
  const taskOutcome = "let raw='';process.stdin.on('data', c => raw += c);process.stdin.on('end', () => process.exit(JSON.parse(raw).task === 'ok' ? 0 : 1))"
  const spec = program("specialize", [router, command("leaf", taskOutcome)], [relation("base", ["leaf"], ["ready"])], { ready: ["no", "yes"], clean: ["no", "yes"] })
  const result = await live(Effect.gen(function* () {
    const runtime = yield* makeAdaptiveRuntime(spec, process.cwd())
    for (const [index, context] of [["no", "no"], ["no", "yes"], ["yes", "no"], ["yes", "yes"]].entries()) {
      yield* runtime.run(index === 3 ? "ok" : "fail", { ready: context[0], clean: context[1] } as Context, { episodeId: `s-${index}`, forceRoute: "base", exploration: 0 })
    }
    return yield* runtime.graph()
  }))
  const specialized = (result["atoms"] as ReadonlyArray<Record<string, unknown>>).filter((atom) => atom["kind"] === "relation" && payload({ atoms: [atom] }, atom["uid"] as string)["parent_relation"] === "relation:base")
  expect(specialized).toHaveLength(1)
})
