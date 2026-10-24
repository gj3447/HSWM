#!/usr/bin/env node
/** Independent arithmetic and outcome checker. No provider calls or policy writes. */
import assert from "node:assert/strict"
import { readFile, readdir } from "node:fs/promises"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { traversalExampleSchema } from "../../src/hswm/effect-runtime/dist/semantic-context-traversal-example.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
const io = f => Effect.tryPromise({ try: f, catch: e => new Error(String(e)) })
const checked = f => Effect.try({ try: f, catch: e => new Error(String(e)) })
const read = path => io(() => readFile(path))
const json = path => read(path).pipe(Effect.map(b => JSON.parse(b)))
const hash = x => createHash("sha256").update(x).digest("hex")
const digest = x => hash(JSON.stringify(x))
const fresh = () => ({ left: { a: [[1, 0], [0, 1]], b: [0, 0], observations: 0 }, right: { a: [[1, 0], [0, 1]], b: [0, 0], observations: 0 } })
// Independent 2x2 inversion, not the native LinUCB implementation.
const score = (arm, x, explore) => {
  const [[a,b],[c,d]] = arm.a, det = a*d-b*c
  const inverse = [[d/det,-b/det],[-c/det,a/det]]
  const theta = inverse.map(row => row[0]*arm.b[0]+row[1]*arm.b[1])
  return x[0]*theta[0]+x[1]*theta[1]+(explore ? Math.sqrt(x[0]*(inverse[0][0]*x[0]+inverse[0][1]*x[1])+x[1]*(inverse[1][0]*x[0]+inverse[1][1]*x[1])) : 0)
}
const inspectRow = (row, policies) => {
  assert.equal(row.result.hops.length, 3)
  assert.equal(row.result.status, row.blocked ? "HELD" : "COMPLETED")
  let next = "entry", previous = null, required = []
  for (const [i,h] of row.result.hops.entries()) {
    assert.equal(h.stepKey.atomUid, `step:${next}`)
    const r = h.result, s = r.execution.selection, payload = r.execution.assembly.payload
    assert.equal(s.policyKey.atomUid, `policy:${next}`)
    const event = JSON.parse(payload.event), input = JSON.parse(event.input)
    assert.equal(input.signal, row.signal); assert.equal(input.blocked, row.blocked)
    assert.deepEqual(event.previous, previous)
    const state = policies[next] ??= { revision: 0, arms: fresh() }
    assert.equal(s.policyKey.revisionId, state.revision)
    const x = [1, row.signal], trained = row.phase === "train"
    const scores = ["left", "right"].map(id => score(state.arms[id], x, trained))
    const chosen = s.candidateId
    assert(["left", "right"].includes(chosen))
    // Independent inversion and native Cholesky may differ at floating ties.
    assert(scores[chosen === "left" ? 0 : 1] >= Math.max(...scores) - 1e-10)
    required = [...required, `rule:${next}:required`]
    assert.deepEqual(payload.frames.map(f => f.relation.key.atomUid), [...required, `rule:${next}:${chosen}`])
    assert(payload.frames.every(f => f.roles.map(p => p.role).join() === "subject,context,evidence,exception"))
    const expected = i === 2 && row.blocked ? "REFUSE" : row.signal > 0 ? "L" : "R"
    const reward = Number(r.execution.trace.prediction === expected)
    assert.equal(r.assessment.reward, reward); assert.equal(r.assessment.observed, expected)
    assert.equal(r.assessment.continue, expected !== "REFUSE")
    if (trained) {
      state.revision++
      const arm = state.arms[chosen]
      for (let a = 0; a < 2; a++) { arm.b[a] += reward*x[a]; for (let b = 0; b < 2; b++) arm.a[a][b] += x[a]*x[b] }
      arm.observations++
      assert.equal(r.status, "UPDATED")
      assert.equal(r.proposal.policyKey.revisionId, state.revision)
      for (const stored of r.proposal.policy.arms) {
        const expectedArm = state.arms[stored.candidateId]
        assert.deepEqual(stored.a, expectedArm.a); assert.deepEqual(stored.b, expectedArm.b)
        assert.equal(stored.observations, expectedArm.observations)
      }
      assert.deepEqual(r.readback.policy, r.proposal.policy)
    } else { assert.equal(r.status, "AUDITED"); assert.equal(r.proposal, null); assert.equal(r.readback, null) }
    previous = { prediction: r.execution.trace.prediction, traceSha256: r.execution.trace.traceContent.sha256 }
    next = i === 0 ? chosen : `${next}-leaf`
  }
}
const main = root => Effect.gen(function* () {
  const plan = yield* json(join(root, "plan.json"))
  for (const pin of plan.pins) {
    const actual = hash(yield* read(pin.path))
    yield* checked(() => assert.equal(actual, pin.sha256, `Implementation drift: ${pin.path}`))
  }
  const rows = []
  for (const phase of ["baseline", "train", "final", "exception", "restart"]) {
    for (const [index, signal] of plan.cases[phase].entries()) {
      const row = yield* json(join(root, `${phase}-${index}.json`))
      yield* checked(() => { assert.equal(row.signal, signal); assert.equal(row.phase, phase); assert.equal(row.blocked, phase === "exception") })
      rows.push(row)
    }
  }
  const policies = {}
  yield* checked(() => rows.forEach(row => inspectRow(row, policies)))
  const initial = yield* json(join(root, "initial-state.json")), final = yield* json(join(root, "final-state.json")), reopened = yield* json(join(root, "reopen.json"))
  yield* checked(() => {
    assert.deepEqual(initial.atoms.filter(a => a.kind !== "semantic_context_policy"), final.atoms.filter(a => a.kind !== "semantic_context_policy"))
    assert.equal(final.revision - initial.revision, 24)
    assert.equal(reopened.stateBefore, final.revision); assert.equal(reopened.stateAfter, final.revision)
    assert.equal(reopened.separateOsProcess, true); assert.equal(reopened.policyRevisions[0].revisionId, 8)
  })
  const schema = canonicalAtomV2SchemaContentBytes(traversalExampleSchema)
  if (Either.isLeft(schema)) return yield* Effect.fail(schema.left)
  const evidence = yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const state = yield* runtime.snapshot
    yield* checked(() => assert.deepEqual(state.canonical, final))
    const nativeJson = content => runtime.readContent(content).pipe(Effect.map(b => JSON.parse(new TextDecoder().decode(b))))
    let calls = 0, totalTokens = 0, unknownUsage = 0, logicalPromptBytes = 0
    for (const row of rows) {
      const receipt = yield* nativeJson(row.result.receiptContent)
      yield* checked(() => { assert.equal(receipt.status, row.result.status); assert.equal(receipt.hops.length, 3) })
      for (const [index,h] of row.result.hops.entries()) {
        calls++
        const trace = yield* nativeJson(h.result.execution.trace.traceContent)
        const request = yield* nativeJson(trace.requestContent)
        const response = yield* nativeJson(trace.responseContent)
        const wireRequest = yield* nativeJson(trace.transport.request), wireResponse = yield* nativeJson(trace.transport.response)
        const diskRequest = yield* json(join(root, `wire-${calls}-request.json`)), diskResponse = yield* json(join(root, `wire-${calls}-response.json`))
        const step = yield* nativeJson(h.stepContent)
        yield* checked(() => {
          assert.equal(trace.prediction, h.result.execution.trace.prediction)
          assert.deepEqual(request.assembly, h.result.execution.assembly)
          assert.equal(request.prompt, wireRequest.messages[0].content)
          assert.deepEqual(wireRequest, diskRequest); assert.deepEqual(wireResponse, diskResponse)
          assert.deepEqual(JSON.parse(wireResponse.choices[0].message.content), response)
          assert.equal(response.prediction, trace.prediction)
          assert.equal(request.promptBytes, Buffer.byteLength(request.prompt))
          assert(request.promptBytes <= step.spec.maximumContextBytes)
          assert.deepEqual(receipt.hops[index].traceContent, h.result.execution.trace.traceContent)
          assert.equal(receipt.hops[index].assessment.reward, h.result.assessment.reward)
        })
        logicalPromptBytes += request.promptBytes
        if (Number.isSafeInteger(wireResponse.usage?.total_tokens)) totalTokens += wireResponse.usage.total_tokens
        else unknownUsage++
        if (h.result.proposal) {
          const key = h.result.proposal.policyKey
          const atom = state.canonical.atoms.find(a => digest(a.key) === digest(key))
          yield* checked(() => assert(atom, "Stored owner successor absent"))
          const stored = yield* nativeJson(atom.content)
          yield* checked(() => assert.deepEqual(stored, h.result.proposal.policy))
        }
      }
    }
    return { calls, totalTokens: unknownUsage ? null : totalTokens, knownTokenSubtotal: totalTokens, unknownUsage, logicalPromptBytes }
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(join(root, "native"), "traversal-example", schema.right)))
  const files = yield* io(() => readdir(root))
  yield* checked(() => { assert.equal(files.filter(n => /^wire-\d+-request.json$/.test(n)).length, 42); assert.equal(evidence.calls, 42) })
  const mutations = [row => { row.result.hops[0].result.assessment.reward = 0 },
    row => { row.result.hops[1].result.execution.assembly.payload.frames.shift() },
    row => { row.result.hops[0].result.execution.selection.policyKey.revisionId = 99 }]
  for (const mutate of mutations) yield* checked(() => { const changed = structuredClone(rows[0]); mutate(changed); assert.throws(() => inspectRow(changed, {})) })
  const phase = name => { const hops = rows.filter(r => r.phase === name).flatMap(r => r.result.hops); return { correct: hops.filter(h => h.result.assessment.reward === 1).length, total: hops.length } }
  return { status: "PASS", ...evidence, baseline: phase("baseline"), final: phase("final"), restart: phase("restart"), exception: phase("exception"),
    nativeUpdates: final.revision-initial.revision, rootPolicyRevision: policies.entry.revision, separateProcessReused: reopened.policyRevisions,
    duplicateFeedback: "COVERED_BY_RUNTIME_TEST", mutationChecks: mutations.length, rulesPreserved: true,
    scope: "AUTHORED_INTEGRATION_ONLY", modelWeightTraining: false, physicalStoreLocality: false }
})
if (process.argv[2] === "--help") process.stdout.write("node _research/multihop_activation_v1/check.mjs ROOT\nRead-only native/wire/outcome/ridge/reopen verification; stdout report, no model calls.\n")
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "MULTIHOP_CHECK_REFUSED", program: () => main(resolve(process.argv[2] ?? "")).pipe(Effect.map(r => JSON.stringify(r, null, 2)+"\n")), describeFailure: String }, [])
