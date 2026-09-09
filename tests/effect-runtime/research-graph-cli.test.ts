import { lstat, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { fileURLToPath } from "node:url"

import { Cause, Effect, Exit, Option } from "effect"
import { afterEach, expect, it } from "vitest"

import { runResearchGraphCli } from "../../src/hswm/effect-runtime/src/research-graph-cli.js"
import { NodePosixFileSystemLive } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"

const checkout = fileURLToPath(new URL("../../", import.meta.url))
const template = join(checkout, "_research/research_coordination/hswm_relation_learning.v1.json")
const roots: string[] = []

const run = (argv: ReadonlyArray<string>) =>
  Effect.runPromise(runResearchGraphCli(argv).pipe(Effect.provide(NodePosixFileSystemLive)))
const failure = async (argv: ReadonlyArray<string>): Promise<string> => {
  const exit = await Effect.runPromise(Effect.exit(runResearchGraphCli(argv).pipe(Effect.provide(NodePosixFileSystemLive))))
  if (Exit.isSuccess(exit)) throw new Error("expected the research graph command to refuse input")
  const error = Option.getOrUndefined(Cause.failureOption(exit.cause))
  return typeof error === "object" && error !== null && "detail" in error && typeof error.detail === "string"
    ? error.detail
    : Cause.pretty(exit.cause)
}
const json = (stdout: string): Record<string, unknown> => JSON.parse(stdout) as Record<string, unknown>
const event = (type: "START" | "FINISH", taskId: string, at: string, disposition = "INCONCLUSIVE") =>
  type === "START"
    ? { type, id: `${taskId}-start`, taskId, actor: `${taskId}-actor`, model: "test-model", at }
    : { type, id: `${taskId}-finish`, taskId, actor: `${taskId}-actor`, at, disposition, summary: `${taskId} result`, sourceIds: ["instrument"], usedTokens: 2 }

const workspace = async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-research-graph-cli-"))
  roots.push(root)
  return root
}
const initialize = async (root: string) => {
  const graph = join(root, "graph.json")
  const result = json((await run(["init", "--template", template, "--out", graph])).stdout)
  return { graph, result }
}
const append = async (graph: string, eventPath: string, output: string, value: unknown, expected?: string) => {
  await writeFile(eventPath, JSON.stringify(value))
  return run(["append", "--graph", graph, "--event", eventPath, "--out", output,
    ...(expected === undefined ? [] : ["--expected-sha256", expected])])
}

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
})

it("initializes a private immutable snapshot and never replaces it", async () => {
  const root = await workspace()
  const { graph, result } = await initialize(root)
  expect(result["status"]).toBe("INITIALIZED")
  expect((result["output"] as Record<string, unknown>)["path"]).toBe(graph)
  expect((await lstat(graph)).mode & 0o777).toBe(0o400)
  const original = await readFile(graph)

  expect(await failure(["init", "--template", template, "--out", graph])).toContain("EEXIST")
  expect(await readFile(graph)).toEqual(original)
})

it("plans ready work, keeps unrelated explorer results out of context, and retains negative findings", async () => {
  const root = await workspace()
  const { graph } = await initialize(root)
  const initialPlan = json((await run(["plan", "--graph", graph])).stdout)
  const initialTasks = initialPlan["tasks"] as Array<Record<string, unknown>>
  expect(initialTasks.filter((entry) => entry["status"] === "READY")).toHaveLength(2)
  expect(initialTasks.filter((entry) => entry["status"] === "WAITING")).toHaveLength(3)

  const start = join(root, "start.json"), first = join(root, "first.json")
  const finish = join(root, "finish.json"), second = join(root, "second.json")
  await append(graph, start, first, event("START", "explore-relation", "2026-09-09T00:00:00.000Z"))
  await append(first, finish, second, event("FINISH", "explore-relation", "2026-09-09T00:00:01.000Z", "REFUTED_IN_SCOPE"))

  const explorerContext = json((await run(["context", "--graph", second, "--task", "explore-baseline"])).stdout)
  const context = explorerContext["context"] as Record<string, unknown>
  expect(context["dependencyResults"]).toEqual([])

  const baselineStart = join(root, "baseline-start.json"), third = join(root, "third.json")
  const baselineFinish = join(root, "baseline-finish.json"), fourth = join(root, "fourth.json")
  await append(second, baselineStart, third, event("START", "explore-baseline", "2026-09-09T00:00:02.000Z"))
  await append(third, baselineFinish, fourth, event("FINISH", "explore-baseline", "2026-09-09T00:00:03.000Z"))
  const critique = json((await run(["context", "--graph", fourth, "--task", "critique"])).stdout)["context"] as Record<string, unknown>
  expect(critique["dependencyResults"]).toEqual(expect.arrayContaining([
    expect.objectContaining({ taskId: "explore-relation", disposition: "REFUTED_IN_SCOPE", negative: true })
  ]))
})

it("appends only to a successor, preserves the predecessor, and refuses source drift", async () => {
  const root = await workspace()
  const { graph, result } = await initialize(root)
  const predecessor = await readFile(graph)
  const expected = (result["output"] as Record<string, unknown>)["sha256"] as string
  const eventPath = join(root, "event.json"), next = join(root, "next.json")

  expect(await failure(["append", "--graph", graph, "--event", eventPath, "--out", next, "--expected-sha256", "0".repeat(64)]))
    .toContain("source SHA-256")
  const recorded = json((await append(graph, eventPath, next, event("START", "explore-relation", "2026-09-09T00:00:00.000Z"), expected)).stdout)
  expect(recorded["status"]).toBe("RECORDED")
  expect(await readFile(graph)).toEqual(predecessor)
  expect((await lstat(next)).mode & 0o777).toBe(0o400)
})

it("refuses unsafe inputs and exports actual JSON-LD and N-Quads only from a valid graph", async () => {
  const root = await workspace()
  const { graph } = await initialize(root)
  const duplicate = join(root, "duplicate.json")
  const badEvent = join(root, "bad-event.json")
  const link = join(root, "graph-link.json")
  await writeFile(duplicate, '{"manifest":{},"manifest":{},"events":[]}')
  await writeFile(badEvent, JSON.stringify({ type: "START" }))
  await symlink(graph, link)

  expect(await failure(["plan", "--graph", graph, "--graph", graph])).toContain("duplicate")
  expect(await failure(["unknown", "--graph", graph])).toContain("unexpected")
  expect(await failure(["validate", "--graph", duplicate])).toContain("duplicate object key")
  expect(await failure(["validate", "--graph", link])).toContain("ELOOP")
  expect(await failure(["append", "--graph", graph, "--event", badEvent, "--out", join(root, "bad.json")])).toContain("invalid START event")

  const exported = json((await run(["export", "--graph", graph])).stdout)
  expect(typeof exported["nquads"]).toBe("string")
  expect(exported["nquads"] as string).toContain("http://www.w3.org/ns/prov#")
  const manifest = exported["manifest"] as Record<string, unknown>
  expect(manifest["rdfProfile"]).toBe("RDF_1_1_N_QUADS_BLANK_NODE_FREE_LEXICALLY_SORTED_PROFILE")
  expect(manifest["nquadsSha256"]).toMatch(/^[a-f0-9]{64}$/)
  expect((exported["jsonld"] as Record<string, unknown>)["@graph"]).toBeInstanceOf(Array)
})

it("distinguishes input file bytes from canonical graph content", async () => {
  const root = await workspace()
  const { graph } = await initialize(root)
  const raw = await readFile(graph)
  const pretty = join(root, "pretty.json")
  const prettyBytes = Buffer.from(JSON.stringify(JSON.parse(raw.toString()), null, 2))
  await writeFile(pretty, prettyBytes)
  const a = json((await run(["export", "--graph", graph])).stdout)
  const b = json((await run(["export", "--graph", pretty])).stdout)
  const ma = a["manifest"] as Record<string, unknown>
  const mb = b["manifest"] as Record<string, unknown>
  expect(ma["canonicalGraphSha256"]).toBe(mb["canonicalGraphSha256"])
  expect(a["nquads"]).toBe(b["nquads"])
  expect(ma["sourceFileSha256"]).toBe(createHash("sha256").update(raw).digest("hex"))
  expect(mb["sourceFileSha256"]).toBe(createHash("sha256").update(prettyBytes).digest("hex"))
  expect(ma["sourceFileSha256"]).not.toBe(mb["sourceFileSha256"])
})
