import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import type { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import type { PosixFileSystem } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"
import { contextHash } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { executeActivationTraversal, type ActivationStep } from "../../src/hswm/effect-runtime/src/semantic-context-traversal-runtime.js"
import { type ActivationLoopPorts } from "../../src/hswm/effect-runtime/src/semantic-context-loop-runtime.js"
import { seedTraversalExample, traversalExampleSchema, traversalExampleTarget, traversalExampleKey } from "../../src/hswm/effect-runtime/src/semantic-context-traversal-example.js"
import { prepareActivationLearning } from "../../src/hswm/effect-runtime/src/semantic-context-activation-runtime.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { unwrap } from "./semantic-context-fixture.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(traversalExampleSchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "traversal-example", schemaBytes, [{
  authorizationRef: "traversal-example", schemaVersion: traversalExampleSchema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["isolated-example"]
}])
const fixture = <A, E>(work: (runtime: Runtime, root: string) => Effect.Effect<A, E, BoundedSubprocess | PosixFileSystem>, transform?: (name: string, step: ActivationStep) => ActivationStep) =>
  Effect.runPromise(Effect.acquireUseRelease(Effect.sync(() => mkdtempSync(join(tmpdir(), "traversal-"))), root =>
    Effect.gen(function* () { const runtime = yield* CanonicalAtomV2DurableRuntime; yield* seedTraversalExample(runtime, transform); return yield* work(runtime, root) }).pipe(Effect.provide(layer(root))),
  root => Effect.sync(() => rmSync(root, { recursive: true, force: true }))
  ).pipe(Effect.provide(NodePosixServicesLive)))
const request = (signal = 1, mode: "TRAIN" | "AUDIT" = "TRAIN", blocked = false, maximumHops = 3) => ({
  entry: traversalExampleKey("step:entry"), event: JSON.stringify({ signal, blocked }), maximumHops, mode,
  cell: { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_TEST_NOT_PROVIDER", max_tokens: 64 }
})
const ports = (runtime: Runtime, calls: string[][] = [], unknown = false) => ({
  http: { postJson: (request: { readonly body: Uint8Array }) => Effect.sync(() => {
    const body = JSON.parse(new TextDecoder().decode(request.body))
    const payload = JSON.parse(body.messages[0].content.split("\n")[1])
    const names: string[] = payload.frames.map((f: { relation: { key: { atomUid: string } } }) => f.relation.key.atomUid)
    calls.push(names)
    const input = JSON.parse(JSON.parse(payload.event).input)
    const leaf = names.some(n => n.includes("-leaf:required"))
    const prediction = leaf && input.blocked ? "REFUSE" : names.at(-1)?.endsWith(":left") ? "L" : "R"
    return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction, uncertainty: "scripted" }) } }] }))
  }) },
  features: (plan: { spec: { event: string } }) => Effect.succeed({ encoderRevision: "authored-signal/v1",
    eventSha256: contextHash(plan.spec.event), values: [1, JSON.parse(JSON.parse(plan.spec.event).input).signal] }),
  target: (key: { atomUid: string; revisionId: number }) => traversalExampleTarget(key.atomUid, key.revisionId + 1),
  admit: (p: Parameters<ActivationLoopPorts<never, never>["admit"]>[0]) => runtime.submit(p.candidate),
  evaluate: (execution: Parameters<ActivationLoopPorts<never, never>["evaluate"]>[0]) => Effect.sync(() => {
    const input = JSON.parse(JSON.parse(execution.assembly?.payload.event ?? "{}").input)
    const leaf = execution.assembly?.payload.frames.some(f => f.relation.key.atomUid.includes("-leaf:required"))
    const expected = leaf && input.blocked ? "REFUSE" : input.signal > 0 ? "L" : "R"
    return { reward: unknown ? null : Number(execution.trace?.prediction === expected), observed: expected,
      source: "AUTHORED_REFERENCE_NOT_INDEPENDENT_EFFICACY", continue: expected !== "REFUSE" }
  })
})

it("learns at visited vertices, preserves roles, follows changed choices and reopens durable W", () => fixture((runtime, root) => Effect.gen(function* () {
  const original = (yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")
  for (let i = 0; i < 4; i++) {
    const run = yield* executeActivationTraversal(runtime, request(i % 2 ? -1 : 1), ports(runtime))
    expect(run.status).toBe("COMPLETED")
    expect(run.hops).toHaveLength(3)
    expect(run.hops.every(h => h.result.status === "UPDATED")).toBe(true)
    expect(run.hops.every(h => h.result.execution.assembly?.payload.frames.every(f => f.roles.map(r => r.role).join() === "subject,context,evidence,exception"))).toBe(true)
  }
  expect((yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")).toEqual(original)
  yield* Effect.gen(function* () {
    const reopened = yield* CanonicalAtomV2DurableRuntime
    const reads: string[] = [], calls: string[][] = []
    const tracked = { ...reopened, readContent: (content: Parameters<Runtime["readContent"]>[0]) => { reads.push(content.sha256); return reopened.readContent(content) } }
    const before = (yield* reopened.snapshot).canonical.revision
    const run = yield* executeActivationTraversal(tracked, request(-0.9, "AUDIT"), ports(tracked, calls))
    expect(run.hops.map(h => h.stepKey.atomUid)).toEqual(["step:entry", "step:right", "step:right-leaf"])
    expect(run.hops[0]?.result.execution.trace?.prediction).toBe("R")
    expect(run.hops[0]?.result.execution.selection.policyKey.revisionId).toBe(4)
    expect((yield* reopened.snapshot).canonical.revision).toBe(before)
    const unrelated = original.find(a => a.key.atomUid === "step:left-leaf")
    expect(reads).not.toContain(unrelated?.content.sha256)
    expect(calls.every(ns => ns.every(n => !n.includes(":left:") && !n.includes(":left-leaf:")))).toBe(true)
    const second = JSON.parse(run.hops[1]?.result.execution.assembly?.payload.event ?? "{}")
    expect(second.previous.traceSha256).toBe(run.hops[0]?.result.execution.trace?.traceContent.sha256)
  }).pipe(Effect.provide(layer(root)))
})), 240000)

it("unknown outcomes and AUDIT never call the owner writer", () => fixture(runtime => Effect.gen(function* () {
  const before = (yield* runtime.snapshot).canonical.revision
  const forbidden = { ...ports(runtime, [], true), admit: () => Effect.die("writer must not run") }
  const unknown = yield* executeActivationTraversal(runtime, request(), forbidden)
  expect(unknown.hops.every(h => h.result.status === "NO_UPDATE")).toBe(true)
  yield* executeActivationTraversal(runtime, request(1, "AUDIT"), { ...ports(runtime), admit: forbidden.admit })
  expect((yield* runtime.snapshot).canonical.revision).toBe(before)
})), 60000)

it("learns a correctly executed late exception and holds the traversal", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[][] = []
  const run = yield* executeActivationTraversal(runtime, request(1, "TRAIN", true), ports(runtime, calls))
  expect(run.status).toBe("HELD")
  expect(run.hops).toHaveLength(3)
  expect(run.hops[2]?.result.execution.trace?.prediction).toBe("REFUSE")
  expect(run.hops[2]?.result.assessment.reward).toBe(1)
  expect(calls[2]).toContain("rule:entry:required")
  expect(calls[2]).toContain("rule:left:required")
  expect(calls[2]).toContain("rule:left-leaf:required")
})), 60000)

it("refuses dropped mandatory rules before the next model call", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[][] = []
  const result = yield* Effect.either(executeActivationTraversal(runtime, request(), ports(runtime, calls)))
  expect(Either.isLeft(result)).toBe(true)
  expect(calls).toHaveLength(1)
}), (name, step) => name === "left" ? { ...step, spec: { ...step.spec, mandatoryRelationUids: ["rule:left:required"] } } : step), 60000)

it("reports exhaustion instead of no relation, and detects cycles without another call", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[][] = []
  const run = yield* executeActivationTraversal(runtime, request(1, "AUDIT", false, 1), ports(runtime, calls))
  expect(run.status).toBe("HOP_BUDGET")
  expect(calls).toHaveLength(1)
})), 60000)

it("detects a repeated exact step", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[][] = []
  const run = yield* executeActivationTraversal(runtime, request(1, "AUDIT"), ports(runtime, calls))
  expect(run.status).toBe("CYCLE")
  expect(calls).toHaveLength(1)
}), (name, step) => name === "entry" ? { ...step, edges: step.edges.map(e => ({ ...e, next: traversalExampleKey("step:entry") })) } : step), 60000)

it("preserves failure evidence on rejected admission and rejects repeated feedback", () => fixture(runtime => Effect.gen(function* () {
  const before = (yield* runtime.snapshot).canonical.revision
  const calls: string[][] = []
  const failed = yield* Effect.either(executeActivationTraversal(runtime, request(), { ...ports(runtime, calls), admit: () => Effect.fail("owner refused") }))
  expect(Either.isLeft(failed)).toBe(true)
  expect(calls).toHaveLength(1)
  expect((yield* runtime.snapshot).canonical.revision).toBe(before)
  const falseAck = yield* Effect.either(executeActivationTraversal(runtime, request(), { ...ports(runtime, calls), admit: () => Effect.void }))
  expect(Either.isLeft(falseAck)).toBe(true)
  expect(calls).toHaveLength(2)
  expect((yield* runtime.snapshot).canonical.revision).toBe(before)
  const run = yield* executeActivationTraversal(runtime, request(1, "TRAIN", false, 1), ports(runtime))
  const first = run.hops[0]?.result
  expect(first?.proposal).not.toBeNull()
  if (!first?.execution.assembly || !first.execution.trace) return yield* Effect.fail("missing evidence")
  const step = JSON.parse(first.execution.assembly.payload.frames[0]?.roles.find(r => r.role === "context")?.contentUtf8 ?? "{}")
  const fresh = yield* prepareSemanticContext(runtime, { ...step.spec, event: first.execution.assembly.payload.event })
  const duplicate = yield* Effect.either(prepareActivationLearning(runtime, fresh, { traceContent: first.execution.trace.traceContent,
    reward: 1, observed: "L", source: "duplicate" }, traversalExampleTarget("policy:entry", 2)))
  expect(Either.isLeft(duplicate)).toBe(true)
})), 60000)

it("refuses incomplete local continuations before any provider call", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[][] = []
  const run = yield* Effect.either(executeActivationTraversal(runtime, request(), ports(runtime, calls)))
  expect(Either.isLeft(run)).toBe(true)
  expect(calls).toHaveLength(0)
}), (name, step) => name === "entry" ? { ...step, edges: step.edges.slice(0, 1) } : step), 60000)

it("refuses a routing source absent from mandatory execution context", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[][] = []
  const run = yield* Effect.either(executeActivationTraversal(runtime, request(), ports(runtime, calls)))
  expect(Either.isLeft(run)).toBe(true)
  expect(calls).toHaveLength(0)
}), (name, step) => name === "entry" ? { ...step, spec: { ...step.spec, mandatoryRelationUids: [] } } : step), 60000)
