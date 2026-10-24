#!/usr/bin/env node
/** Bounded real-provider integration. Original wire and native state stay local. */
import { readFile, writeFile, mkdir, readdir } from "node:fs/promises"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { NativeAdaptiveHttpClient, AdaptiveExecutorError } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"
import { executeActivationTraversal } from "../../src/hswm/effect-runtime/dist/semantic-context-traversal-runtime.js"
import { seedTraversalExample, traversalExampleSchema, traversalExampleKey, traversalExampleTarget } from "../../src/hswm/effect-runtime/dist/semantic-context-traversal-example.js"
import { contextHash } from "../../src/hswm/effect-runtime/dist/semantic-context-domain.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
const help = `node _research/multihop_activation_v1/run.mjs prepare NEW_ROOT MODEL_ID
node _research/multihop_activation_v1/run.mjs run ROOT
Internal: resume ROOT (exact existing scope; one separate-process AUDIT)
Uses existing loopback http://127.0.0.1:18801/v1 only; no service changes.
Authored five-vertex / three-hop example, up to 42 calls / 45 minutes.
prepare records this user-authorized task scope locally; run checks revocation, exact pins and one bounded reachability probe.
No retries or operational policy promotion. Unknown outcome does not become zero.
Use check.mjs ROOT for replay without provider calls.\n`
const io = f => Effect.tryPromise({ try: f, catch: e => new Error(String(e)) })
const need = (ok, message) => ok ? Effect.void : Effect.fail(new Error(message))
const json = x => JSON.stringify(x, null, 2) + "\n"
const sha = bytes => createHash("sha256").update(bytes).digest("hex")
const read = path => io(() => readFile(path))
const readJson = path => read(path).pipe(Effect.map(bytes => JSON.parse(bytes)))
const save = (path, value) => io(() => writeFile(path, json(value), { flag: "wx", mode: 0o600 }))
const unwrap = value => { if (Either.isLeft(value)) throw value.left; return value.right }
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(traversalExampleSchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = root => makeCanonicalAtomV2DurableRuntimeFileLayer(join(root, "native"), "traversal-example", schemaBytes, [{
  authorizationRef: "traversal-example", schemaVersion: traversalExampleSchema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["isolated-example"]
}])
const sourceFiles = ["semantic-context-traversal-runtime", "semantic-context-loop-runtime", "semantic-context-traversal-example",
  "semantic-context-activation-runtime", "semantic-context-activation-domain", "semantic-context-runtime", "semantic-context-presentation-domain",
  "canonical-atom-v2-durable-runtime", "canonical-atom-v2-llm-semantic-runtime", "adaptive-executor"]
const pins = () => Effect.forEach(sourceFiles, name => Effect.gen(function* () {
  const path = `src/hswm/effect-runtime/dist/${name}.js`
  return { path, sha256: sha(yield* read(path)) }
}))
const checkScope = root => Effect.gen(function* () {
  const plan = yield* readJson(join(root, "plan.json")), access = yield* readJson(join(root, "access.json"))
  yield* need(access.planSha256 === sha(yield* read(join(root, "plan.json"))) && !access.revoked &&
    Date.now() < Date.parse(access.expiresAt) && access.expiresAt === plan.expiresAt &&
    plan.root === root && contextHash(yield* pins()) === contextHash(plan.pins) &&
    sha(yield* read(new URL(import.meta.url))) === plan.runnerSha256, "NOT_READY: exact scope expired, revoked or changed")
  return plan
})
const prepare = (root, model) => Effect.gen(function* () {
  yield* need(typeof model === "string" && model.length > 0 && model.length < 256, "Explicit existing model ID required")
  yield* io(() => mkdir(root, { recursive: false, mode: 0o700 }))
  const createdAt = new Date().toISOString(), expiresAt = new Date(Date.now() + 2700000).toISOString()
  const plan = { contract: "hswm-multihop-integration/v1", root, createdAt, expiresAt, model,
    transport: "http://127.0.0.1:18801/v1", maximumCalls: 42, pins: yield* pins(), runnerSha256: sha(yield* read(new URL(import.meta.url))),
    scope: "AUTHORED_INTEGRATION_NOT_NATURAL_TASK_EFFICACY", cases: {
      baseline: [0.8, -0.8], train: [1, -1, 1, -1, 1, -1, 1, -1], final: [0.8, -0.8], restart: [-0.9], exception: [0.7]
    }, evaluator: "PER_HOP_EXACT_LITERAL_SIGN_SIGNAL_AND_LEAF_REFUSAL/v1", featureNames: ["bias", "signal"],
    inference: { max_tokens: 512, sampling: "PROVIDER_DEFAULT", weightRevision: "NOT_ATTESTED" },
    credit: "Observed per-hop output only; no causal credit for terminal reward", schemaSha256: sha(schemaBytes) }
  yield* save(join(root, "plan.json"), plan)
  yield* save(join(root, "access.json"), { recipient: "designated gj3447 HSWM maintainer (current Codex task)", visibility: "LOCAL_ONLY",
    purpose: "User-requested multi-hop execution/feedback/W/reopen and presentation validation", approvalBasis: "CURRENT_USER_REQUEST",
    mappings: [{ resource: "urn:hswm:repository", workspace: "selected-project", representation: process.cwd(), capability: "SOURCE_READ_AND_ISOLATED_NATIVE_WRITE" },
      { resource: "urn:hswm:existing-model", workspace: "loopback-model", representation: plan.transport, capability: "MODELS_GET_AND_42_COMPLETIONS" }],
    planSha256: sha(yield* read(join(root, "plan.json"))), expiresAt, revoked: false,
    revocation: "Set revoked:true in this exact access.json; checked before every call. No automatic renewal." })
  return { status: "PREPARED", maximumCalls: plan.maximumCalls, expiresAt }
})
const runCase = (runtime, root, plan, phase, index, signal, blocked = false) => Effect.gen(function* () {
  yield* checkScope(root)
  const started = performance.now()
  const http = { postJson: request => Effect.gen(function* () {
    yield* checkScope(root)
    const existing = (yield* io(() => readdir(root))).filter(n => /^wire-\d+-request.json$/.test(n))
    yield* need(existing.length < plan.maximumCalls, "Provider budget exhausted")
    const n = existing.length + 1
    yield* save(join(root, `wire-${n}-request.json`), JSON.parse(new TextDecoder().decode(request.body)))
    const before = performance.now(), response = yield* NativeAdaptiveHttpClient.postJson({ ...request, timeoutMs: Math.min(request.timeoutMs, 30000) })
    yield* save(join(root, `wire-${n}-response.json`), JSON.parse(new TextDecoder().decode(response)))
    yield* save(join(root, `wire-${n}-time.json`), { elapsedMs: performance.now() - before })
    return response
  }).pipe(Effect.mapError(e => new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: String(e) }))) }
  const result = yield* executeActivationTraversal(runtime, {
    entry: traversalExampleKey("step:entry"), event: JSON.stringify({ signal, blocked, unit: `${phase}-${index}` }), maximumHops: 3,
    mode: phase === "train" ? "TRAIN" : "AUDIT", cell: { base_url: plan.transport, model: plan.model, max_tokens: plan.inference.max_tokens }
  }, { http,
    features: (context, _step) => Effect.succeed({ encoderRevision: "authored-signal/v1", eventSha256: contextHash(context.spec.event),
      values: [1, JSON.parse(JSON.parse(context.spec.event).input).signal] }),
    target: key => traversalExampleTarget(key.atomUid, key.revisionId + 1),
    admit: proposal => runtime.submit(proposal.candidate),
    evaluate: execution => Effect.sync(() => {
      const input = JSON.parse(JSON.parse(execution.assembly.payload.event).input)
      const leaf = execution.assembly.payload.frames.some(f => f.relation.key.atomUid.includes("-leaf:required"))
      const expected = leaf && input.blocked ? "REFUSE" : input.signal > 0 ? "L" : "R"
      return { reward: Number(execution.trace.prediction === expected), observed: expected,
        source: plan.evaluator + ":EXPOSED_AUTHORED_REFERENCE", continue: expected !== "REFUSE" }
    })
  })
  const row = { phase, index, signal, blocked, elapsedMs: performance.now() - started, result }
  yield* save(join(root, `${phase}-${index}.json`), row)
  yield* Effect.sync(() => process.stderr.write(`${phase} ${index}: ${result.status}; ${result.hops.map(h => `${h.result.execution.selection.candidateId}:${h.result.execution.trace.prediction}:${h.result.status}`).join(" / ")}\n`))
  return row
})
const resume = root => Effect.gen(function* () {
  const plan = yield* checkScope(root)
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const before = (yield* runtime.snapshot).canonical.revision
    const row = yield* runCase(runtime, root, plan, "restart", 0, plan.cases.restart[0])
    return { stateBefore: before, stateAfter: (yield* runtime.snapshot).canonical.revision,
      policyRevisions: row.result.hops.map(h => h.result.execution.selection.policyKey), separateOsProcess: true }
  }).pipe(Effect.provide(layer(root)))
})
const run = root => Effect.gen(function* () {
  const plan = yield* checkScope(root)
  const response = yield* io(() => fetch(`${plan.transport}/models`, { signal: AbortSignal.timeout(3000) }))
  yield* need(response.ok, "NOT_READY: bounded reachability failed; no retry")
  const models = yield* io(() => response.json())
  yield* need(models.data?.some(m => m.id === plan.model), "NOT_READY: requested model absent")
  yield* save(join(root, "reachability.json"), { status: response.status, model: plan.model, at: new Date().toISOString() })
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seedTraversalExample(runtime)
    const initial = (yield* runtime.snapshot).canonical
    yield* save(join(root, "initial-state.json"), initial)
    for (const phase of ["baseline", "train", "final", "exception"]) {
      for (const [i, signal] of plan.cases[phase].entries()) yield* runCase(runtime, root, plan, phase, i, signal, phase === "exception")
    }
    const reopened = yield* io(() => promisify(execFile)(process.execPath, [new URL(import.meta.url).pathname, "resume", root], { timeout: 180000, maxBuffer: 1048576 }))
    yield* save(join(root, "reopen.json"), JSON.parse(reopened.stdout))
    yield* save(join(root, "final-state.json"), (yield* runtime.snapshot).canonical)
    return { status: "EXECUTED_CHECK_REQUIRED", root }
  }).pipe(Effect.provide(layer(root)))
})
if (process.argv[2] === "--help") process.stdout.write(help)
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "MULTIHOP_REFUSED", program: () => Effect.gen(function* () {
  const [action, rawRoot, model] = process.argv.slice(2)
  yield* need(rawRoot && ["prepare", "run", "resume"].includes(action), help)
  const root = resolve(rawRoot)
  const result = yield* action === "prepare" ? prepare(root, model) : action === "resume" ? resume(root) : run(root)
  return json(result)
}), describeFailure: String }, [])
