import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { contextHash } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { inspectEvidenceAction, validateEvidenceNavigation, type EvidenceStep } from "../../src/hswm/effect-runtime/src/semantic-context-evidence-domain.js"
import { executeEvidenceTraversal } from "../../src/hswm/effect-runtime/src/semantic-context-evidence-runtime.js"
import { evidenceExampleSchema, evidenceExampleKey, evidenceExampleStep, evidenceExampleTarget, evidenceExampleConfig, seedEvidenceExample, type EvidenceExampleNode } from "../../src/hswm/effect-runtime/src/semantic-context-evidence-example.js"
import { prepareActivationLearning } from "../../src/hswm/effect-runtime/src/semantic-context-activation-runtime.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import type { EvidenceAction } from "../../src/hswm/effect-runtime/src/semantic-context-evidence-domain.js"
import type { ActivationLoopPorts } from "../../src/hswm/effect-runtime/src/semantic-context-loop-runtime.js"
import { unwrap } from "./semantic-context-fixture.js"
import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const definitions = [
  { id: "root", ancestors: [], source: "Luma was made by Iven.", next: ["bridge", "decoy"] },
  { id: "bridge", ancestors: ["root"], source: "Iven uses Sola port.", next: ["leaf"] },
  { id: "leaf", ancestors: ["root", "bridge"], source: "Sola port's marker is cyan.", next: [] },
  { id: "decoy", ancestors: ["root"], source: "UNVISITED_SECRET_SENTINEL: Varo uses a magenta marker.", next: [] }
]
const nodes: ReadonlyArray<EvidenceExampleNode> = definitions.map(d => {
  const edges = d.next.map((next, i) => ({ id: i === 0 ? "left" as const : "right" as const, link: `${d.id}_${next}`,
    resource: next, enteredRole: "from", exitedRole: "to", next }))
  return { ...d, edges, navigation: { schema: "usl-agent-context/v1", namespace: "test", planDigest: `sha256:${"a".repeat(64)}`, focus: d.id,
    meanings: [{ name: "next", description: "Local navigation, not factual support", roles: [{ name: "from", kind: "any" }, { name: "to", kind: "any" }, { name: "scope", kind: "any" }] }],
    links: edges.map(e => ({ name: e.link, meaning: "next", participants: [{ role: "from", resource: d.id }, { role: "to", resource: e.next }, { role: "scope", resource: "boundary" }] })),
    paths: edges.map(e => ({ resource: e.next, steps: [{ link: e.link, meaning: "next", from: d.id, to: e.next, enteredRole: "from", exitedRole: "to" }] })),
    resources: [], routes: null, target: null, coverage: { complete: true },
    interpretation: { traversal: "ROLE_INCIDENCE", declarationStatus: "DECLARED", semanticTruth: "NOT_EVALUATED", reachability: "NOT_OBSERVED", execution: "NOT_PLANNED" }
  } }
})
const rootNode = nodes[0]!
const step = evidenceExampleStep(rootNode)
const source = { sourceId: "root", sha256: "a".repeat(64), text: rootNode.source }
const answer = (sourceId = "root", quote = source.text): EvidenceAction => ({ action: "ANSWER", answer: "Iven", citations: [{ sourceId, quote }] })
describe("typed local actions and source integrity", () => {
  it("rejects foreign edges, extra fields, invalid JSON and unvisited/fabricated citations", () => {
    for (const raw of ["not json", JSON.stringify({ action: "FOLLOW", edgeId: "not-local" }),
      JSON.stringify({ action: "FOLLOW", edgeId: "left", permission: "write" }), JSON.stringify(answer("unvisited")),
      JSON.stringify(answer("root", "Luma was made by Varo.")), JSON.stringify(answer("root", " "))]) {
      expect(Either.isLeft(inspectEvidenceAction(raw, step, [source]))).toBe(true)
    }
    expect(unwrap(inspectEvidenceAction(JSON.stringify(answer()), step, [source])).grounding).toBe("EXACT_QUOTE_INTEGRITY_ONLY")
    // A real quote can accompany a false conclusion: integrity must not claim entailment.
    expect(unwrap(inspectEvidenceAction(JSON.stringify({ ...answer(), answer: "Varo" }), step, [source])).grounding).toBe("EXACT_QUOTE_INTEGRITY_ONLY")
  })
  it("preserves n-ary roles and rejects reversed or missing USL witnesses", () => {
    expect(Either.isRight(validateEvidenceNavigation(rootNode.navigation, step))).toBe(true)
    expect(Either.isLeft(validateEvidenceNavigation(rootNode.navigation, { ...step, edges: step.edges.map(e => ({ ...e, enteredRole: "to", exitedRole: "from" })) }))).toBe(true)
    const omitted = JSON.parse(JSON.stringify(rootNode.navigation))
    omitted.links[0].participants.pop()
    expect(Either.isLeft(validateEvidenceNavigation(omitted, step))).toBe(true)
    const noWitness = JSON.parse(JSON.stringify(rootNode.navigation)); noWitness.paths = []
    expect(Either.isLeft(validateEvidenceNavigation(noWitness, step))).toBe(true)
  })
})
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(evidenceExampleSchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = () => makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest("evidence-test", schemaBytes, [{
  authorizationRef: "traversal-example", schemaVersion: evidenceExampleSchema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["isolated-example"]
}])
const fixture = <A, E>(work: (runtime: Runtime) => Effect.Effect<A, E, BoundedSubprocess>, transform?: (step: EvidenceStep, node: EvidenceExampleNode) => EvidenceStep) => Effect.runPromise(
  Effect.gen(function* () { const runtime = yield* CanonicalAtomV2DurableRuntime; yield* seedEvidenceExample(runtime, nodes, transform); return yield* work(runtime) })
    .pipe(Effect.provide(layer()), Effect.provideService(BoundedSubprocess, { observe: () => Effect.die("Memory-only test must not start a process") })))
const request = (mode: "TRAIN" | "AUDIT" = "TRAIN") => ({ entry: evidenceExampleKey("step:root"), question: "What is the marker color at the port used by Luma's maker?",
  mode, maximumHops: 4, maximumEvidenceBytes: 4096, maximumWireBytes: 262144,
  cell: { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_NOT_PROVIDER", max_tokens: 256 } })
const scripted = (runtime: Runtime, calls: string[] = [], choose?: (id: string) => unknown) => ({
  http: { postJson: (call: { readonly body: Uint8Array }) => Effect.sync(() => {
    const raw = new TextDecoder().decode(call.body); calls.push(raw)
    const payload = JSON.parse(JSON.parse(raw).messages[0].content.split("\n")[1])
    const id = payload.frames.at(-1).relation.key.atomUid.split(":")[1] as string
    const action = choose ? choose(id) : id === "leaf" ? { action: "ANSWER", answer: "cyan", citations: definitions.slice(0, 3).map(d => ({ sourceId: d.id, quote: d.source })) } : { action: "FOLLOW", edgeId: "left" }
    return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: JSON.stringify(action), uncertainty: "scripted" }) } }] }))
  }) },
  features: (plan: { spec: { event: string } }, s: EvidenceStep) => Effect.succeed({ encoderRevision: evidenceExampleConfig.encoderRevision,
    eventSha256: contextHash(plan.spec.event), values: [1, 0.1, JSON.parse(plan.spec.event).hop / 8, s.edges.length / 8] }),
  target: (key: { atomUid: string; revisionId: number }) => evidenceExampleTarget(key.atomUid, key.revisionId + 1),
  admit: (p: Parameters<ActivationLoopPorts<never, never>["admit"]>[0]) => runtime.submit(p.candidate),
  evaluate: () => Effect.succeed({ reward: 1, observed: "Scripted deliberately permissive evaluator", source: "SCRIPTED_TEST_ONLY", continue: true })
})
it("chooses each next step from model output, carries source roles, learns native W and rejects duplicate feedback", () => fixture(runtime => Effect.gen(function* () {
  const before = (yield* runtime.snapshot).canonical.atoms.filter(a => a.kind === "semantic_context_policy")
  const calls: string[] = [], reads: string[] = []
  const tracked = { ...runtime, readContent: (c: Parameters<Runtime["readContent"]>[0]) => { reads.push(c.sha256); return runtime.readContent(c) } }
  const result = yield* executeEvidenceTraversal(tracked, request(), scripted(tracked, calls))
  expect(result.status).toBe("ANSWERED"); expect(result.answer).toBe("cyan")
  expect(result.hops.map(h => h.stepKey.atomUid)).toEqual(["step:root", "step:bridge", "step:leaf"])
  expect(result.hops.every(h => h.result.status === "UPDATED")).toBe(true)
  expect(calls.every(c => !c.includes("UNVISITED_SECRET_SENTINEL"))).toBe(true)
  const decoy = (yield* runtime.snapshot).canonical.atoms.find(a => a.key.atomUid === "source:decoy")!
  expect(reads).not.toContain(decoy.content.sha256)
  for (const h of result.hops) expect(h.result.readback?.atom.content.sha256).not.toBe(before.find(a => a.key.atomUid === h.result.readback?.atom.key.atomUid)?.content.sha256)
  const first = result.hops[0]!, plan = yield* prepareSemanticContext(runtime, { ...step.spec, event: first.result.execution.assembly!.payload.event })
  const duplicate = yield* Effect.either(prepareActivationLearning(runtime, plan, { traceContent: first.result.execution.trace!.traceContent,
    reward: first.result.assessment.reward, observed: first.result.assessment.observed, source: first.result.assessment.source }, evidenceExampleTarget(step.policyUid, 2)))
  expect(Either.isLeft(duplicate)).toBe(true)
  const revision = (yield* runtime.snapshot).canonical.revision
  const audit = yield* executeEvidenceTraversal(runtime, request("AUDIT"), scripted(runtime))
  expect(audit.hops.every(h => h.result.execution.selection.policyKey.revisionId === 1)).toBe(true)
  expect((yield* runtime.snapshot).canonical.revision).toBe(revision)
})), 30000)
it("clamps fabricated citations to zero despite positive external reward", () => fixture(runtime => Effect.gen(function* () {
  const result = yield* executeEvidenceTraversal(runtime, request(), scripted(runtime, [], () => answer("decoy", "unread")))
  expect(result.status).toBe("INVALID_ACTION"); expect(result.hops[0]?.result.assessment.reward).toBe(0)
  expect(result.hops[0]?.result.execution.trace?.prediction).toContain("unread")
  expect(result.hops[0]?.result.readback?.atom.key.revisionId).toBe(1)
})), 30000)
it("holds insufficient evidence and does not manufacture a fact at hop/byte limits", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[] = []
  const abstained = yield* executeEvidenceTraversal(runtime, request("AUDIT"), scripted(runtime, calls, () => ({ action: "ABSTAIN", reason: "missing source" })))
  expect(abstained.status).toBe("ABSTAINED")
  const hop = yield* executeEvidenceTraversal(runtime, { ...request("AUDIT"), maximumHops: 1 }, scripted(runtime))
  expect(hop.status).toBe("HOP_BUDGET"); expect(hop.answer).toBeNull()
  const bytes = yield* executeEvidenceTraversal(runtime, { ...request("AUDIT"), maximumEvidenceBytes: 1 }, scripted(runtime, calls))
  expect(bytes.status).toBe("EVIDENCE_BUDGET"); expect(calls).toHaveLength(1)
  const wire = yield* Effect.either(executeEvidenceTraversal(runtime, { ...request("AUDIT"), maximumWireBytes: 1 }, scripted(runtime, calls)))
  expect(Either.isLeft(wire)).toBe(true); expect(calls).toHaveLength(1)
})), 30000)
it("refuses loss of earlier required evidence before executing the next hop", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[] = [], result = yield* Effect.either(executeEvidenceTraversal(runtime, request("AUDIT"), scripted(runtime, calls)))
  expect(Either.isLeft(result)).toBe(true); expect(calls).toHaveLength(1)
}), (s, n) => n.id === "bridge" ? { ...s, spec: { ...s.spec, mandatoryRelationUids: ["rule:bridge:required"] } } : s), 30000)
it("rejects a USL/native destination identity mismatch before the next model call", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[] = [], result = yield* Effect.either(executeEvidenceTraversal(runtime, request("AUDIT"), scripted(runtime, calls)))
  expect(Either.isLeft(result)).toBe(true); expect(calls).toHaveLength(1)
}), (s, n) => n.id === "root" ? { ...s, edges: s.edges.map(e => e.id === "left" ? { ...e, next: evidenceExampleKey("step:decoy") } : e) } : s), 30000)
it("rejects uncounted candidate evidence before any provider call", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[] = [], result = yield* Effect.either(executeEvidenceTraversal(runtime, request("AUDIT"), scripted(runtime, calls)))
  expect(Either.isLeft(result)).toBe(true); expect(calls).toHaveLength(0)
}), (s, n) => n.id === "root" ? { ...s, evidence: [] } : s), 30000)
it("rejects probability thresholds unsupported by the W selector before any call or update", () => fixture(runtime => Effect.gen(function* () {
  const calls: string[] = [], before = (yield* runtime.snapshot).canonical.revision
  const result = yield* Effect.either(executeEvidenceTraversal(runtime, request(), scripted(runtime, calls)))
  expect(Either.isLeft(result)).toBe(true); expect(calls).toHaveLength(0)
  expect((yield* runtime.snapshot).canonical.revision).toBe(before)
}), s => ({ ...s, spec: { ...s.spec, minimumConfidence: 1, minimumMargin: 1 } })), 30000)
