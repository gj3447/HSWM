#!/usr/bin/env node
/** One real source/model use, restart, shared learning and selective refresh. Private local journal only. */
import { readFile, writeFile, mkdir } from "node:fs/promises"
import { resolve, join } from "node:path"
import { execFile } from "node:child_process"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { NativeAdaptiveHttpClient, AdaptiveExecutorError } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"
import { contextHash } from "../../src/hswm/effect-runtime/dist/semantic-context-domain.js"
import { decodeLifecycleCell } from "../../src/hswm/effect-runtime/dist/semantic-lifecycle-domain.js"
import { workingContextKind } from "../../src/hswm/effect-runtime/dist/working-context-domain.js"
import { prepareWorkingContextCreation, prepareWorkingContextRefresh, executeWorkingContextLoop, openWorkingContext } from "../../src/hswm/effect-runtime/dist/working-context-runtime.js"
import { workspaceActivationSchema, workspaceActivationConfig, workspaceActivationSpec, workspaceActivationKey, readWorkspaceActivationSource, selectWorkspaceSourceUnit, seedWorkspaceActivation } from "../../src/hswm/effect-runtime/dist/workspace-activation-runtime.js"
import { decodeWorkspaceManifest } from "../../src/hswm/effect-runtime/dist/workspace-manifest-domain.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const help = `node _research/agent_working_context_v1/run.mjs prepare NEW_PRIVATE_ROOT PRIVATE_CELL_JSON
node _research/agent_working_context_v1/run.mjs run ROOT
node _research/agent_working_context_v1/run.mjs check ROOT
prepare creates an isolated native journal, three task contexts and an unapproved access proposal; no network.
PRIVATE_CELL_JSON supplies the existing vLLM base_url, model and max_tokens; keep actual connection details private.
run requires owner-approved access.json: one /models GET, one /tokenize and one completion through that existing provider.
Only the selected complete identity-document section, authored task memory, native role frames and output contract leave the process.
Maximum one generation, no retries, 2-hour expiry, local private evidence; revoke via access.json approved:false or user stop.
run checks reachability, performs TRAIN, reopens another task in a new OS process, checks duplicate suppression and selectively refreshes a local source correction.
check independently rereads the journal, feedback and selection through a fresh process. Source integration only, not general intelligence/efficacy.
Guide: docs/operations/HSWM_AGENT_WORKING_CONTEXT.md
`
const owner = "owner:workspace-source-operator"
const schema = { ...workspaceActivationSchema, kinds: [...workspaceActivationSchema.kinds, workingContextKind([owner])] }
const unwrap = value => { if (Either.isLeft(value)) throw value.left; return value.right }
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const io = thunk => Effect.tryPromise({ try: thunk, catch: cause => new Error(String(cause)) })
const need = (condition, message) => condition ? Effect.void : Effect.fail(new Error(message))
const json = path => io(async () => JSON.parse(await readFile(path, "utf8")))
const save = (path, value) => io(() => writeFile(path, JSON.stringify(value, null, 2) + "\n", { flag: "wx", mode: 0o600 }))
const layer = root => makeCanonicalAtomV2DurableRuntimeFileLayer(join(root, "native"), "agent-working-context", schemaBytes,
  [{ authorizationRef: "workspace-source-operator", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["read-reason-source"] }])
const writer = () => ({ owner, authorizationRef: "workspace-source-operator", scope: "read-reason-source", decidedAt: new Date().toISOString() })
const target = (key, revisionId = key.revisionId + 1) => ({ ...writer(), key: { ...key, revisionId } })
const observeChild = (root, key, action = "select") => io(async () => {
  const request = { contract: "hswm-working-context-cli/v1", action, durableRoot: join(root, "native"), journalLineageId: "agent-working-context",
    schema, contextKey: key, ...(action === "select" ? { featureValues: [1, 0, 0.1] } : {}) }
  return await new Promise((resolveResult, reject) => {
    const child = execFile(process.execPath, [resolve("src/hswm/effect-runtime/dist/working-context-process.js")], { timeout: 60000, maxBuffer: 2097152 }, (error, stdout, stderr) => {
      if (error) reject(new Error(`Fresh process failed: ${stderr || error.message}`))
      else { try { resolveResult({ pid: child.pid, result: JSON.parse(stdout) }) } catch (cause) { reject(cause) } }
    })
    child.stdin.end(JSON.stringify(request))
  })
})

const prepare = (root, cellPath) => Effect.gen(function* () {
  const cell = yield* decodeLifecycleCell(yield* json(cellPath))
  yield* need(cell.api_key_env === undefined, "This bounded diagnostic uses an existing provider without credential forwarding; authenticated transports belong in the consumer adapter")
  yield* io(() => mkdir(root, { mode: 0o700 }))
  yield* io(() => mkdir(join(root, "native"), { mode: 0o700 }))
  const manifest = yield* decodeWorkspaceManifest(yield* json("ontology/workspace/HSWM_WORKSPACE.v1.json"))
  const whole = yield* readWorkspaceActivationSource(manifest, "identity", path => io(() => readFile(path)))
  const unit = whole.units.find(unit => unit.heading?.level === 1)
  yield* need(unit !== undefined, "Complete heading section is absent")
  const source = yield* selectWorkspaceSourceUnit(whole, unit.id)
  const expected = /^#\s+(.+)$/m.exec(source.sourceText)?.[1]?.trim()
  yield* need(typeof expected === "string", "Source heading absent; no invented oracle")
  const memory = { goal: "Read the exact source heading and retain this task across restart", constraints: ["Preserve original characters", "Keep uncertain evidence explicit"],
    completionCriteria: ["Exact heading observed", "Shared policy used after restart"], progress: "Source selected; waiting for one observed model result",
    gaps: [{ id: "future-change", question: "Has a later human correction changed this source?", status: "OPEN", evidence: [] }] }
  const spec = workspaceActivationSpec("Return the exact first Markdown level-one heading in the evidence, excluding # and surrounding whitespace. Do not translate or explain. Output only that heading in prediction.")
  const keys = Object.fromEntries(["worker", "peer", "unrelated"].map(id => [id, workspaceActivationKey(source.sourceId, `working:${id}`)]))
  yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seedWorkspaceActivation(runtime, source)
    for (const id of Object.keys(keys)) {
      const proposal = yield* prepareWorkingContextCreation(runtime, { agentId: `agent:${id}`, taskId: `task:${id}`, memory,
        spec: id === "unrelated" ? { ...spec, candidates: spec.candidates.filter(c => c.id === "explain") } : spec,
        policyFamily: { lineageId: "shared-heading-operators", atomUid: "heading", config: workspaceActivationConfig } }, target(keys[id], 0))
      yield* runtime.submit(proposal.candidate)
    }
  }).pipe(Effect.provide(layer(root)))
  const createdAt = new Date().toISOString()
  const plan = { root, createdAt, expiresAt: new Date(Date.now() + 7200000).toISOString(), schemaHash, sourceId: source.sourceId,
    source: source.binding, keys, memory, expected, transport: cell.base_url, model: cell.model, maxTokens: cell.max_tokens, maximumCalls: 1 }
  yield* save(join(root, "plan.json"), plan)
  yield* save(join(root, "access.json"), { approved: false, planSha256: contextHash(plan), expiresAt: plan.expiresAt,
    recipient: "designated gj3447 HSWM operator and existing owner model endpoint", visibility: "PRIVATE_EXISTING_OWNER_TRANSPORT",
    purpose: "One working-context/source activation integration check", mappings: [{ resource: "urn:hswm:agent-working-context", workspace: "selected-HSWM-project", representation: root },
      { resource: "urn:hswm:existing-model", workspace: "existing-loopback-model", representation: plan.transport }],
    fields: ["complete selected identity-document section", "authored task goal, constraints, open gap and progress", "native role frames and source identifiers", "prediction/uncertainty output contract"],
    maximumCalls: 1, revocation: "Set approved:false or user stop; no automatic renewal or retries" })
  return { status: "PREPARED_NO_NETWORK", root, expiresAt: plan.expiresAt, maximumCalls: 1 }
})
const permitted = (root, plan) => Effect.gen(function* () {
  const access = yield* json(join(root, "access.json"))
  yield* need(access.approved === true && access.planSha256 === contextHash(plan) && access.expiresAt === plan.expiresAt && Date.now() < Date.parse(access.expiresAt), "NOT_READY: owner approval absent, revoked, changed or expired")
})
const run = root => Effect.gen(function* () {
  const plan = yield* json(join(root, "plan.json"))
  yield* permitted(root, plan)
  const models = yield* io(async () => { const response = await fetch(plan.transport + "/models", { signal: AbortSignal.timeout(5000) }); if (!response.ok) throw new Error(`models status ${response.status}`); return response.json() })
  yield* need(models.data?.some(model => model.id === plan.model), "NOT_READY: registered model unreachable")
  yield* save(join(root, "reachability.json"), { observedAt: new Date().toISOString(), method: "GET /models", model: plan.model, reachable: true })
  const result = yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const original = yield* openWorkingContext(runtime, plan.keys.worker)
    const use = { runId: "one-source-heading", mode: "TRAIN", cell: { base_url: plan.transport, model: plan.model, max_tokens: plan.maxTokens ?? 384 }, featureValues: [1, 0, 0.1], presentation: "execution_tail" }
    const http = { postJson: request => Effect.gen(function* () {
      yield* permitted(root, plan)
      const wire = JSON.parse(new TextDecoder().decode(request.body))
      yield* save(join(root, "wire-request.json"), wire) // exclusive slot reserves the only permitted provider call
      const tokens = yield* io(async () => { const response = await fetch(new URL("../tokenize", plan.transport.replace(/\/$/, "") + "/"), { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: wire.model, messages: wire.messages }), signal: AbortSignal.timeout(10000) }); if (!response.ok) throw new Error(`tokenize status ${response.status}`); return response.json() })
      yield* need(Number.isSafeInteger(tokens.count) && tokens.count + wire.max_tokens <= tokens.max_model_len, "Complete task/source prompt exceeds actual model context; no truncation")
      const response = yield* NativeAdaptiveHttpClient.postJson({ ...request, timeoutMs: 30000 })
      yield* save(join(root, "wire-response.json"), JSON.parse(new TextDecoder().decode(response)))
      return response
    }).pipe(Effect.mapError(error => new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: String(error) }))) }
    const ports = { http, admit: proposal => runtime.submit(proposal.candidate), evaluate: execution => Effect.succeed({
      reward: execution.trace === null ? null : Number(execution.trace.prediction === plan.expected), observed: plan.expected, source: "EXACT_SOURCE_HEADING_ORACLE_NOT_GENERAL_EFFICACY", continue: false }) }
    const executed = yield* executeWorkingContextLoop(runtime, original.atom.key, use, writer(), ports)
    yield* need(executed.status === "UPDATED", "No admitted outcome-bound update")
    const peer = yield* openWorkingContext(runtime, plan.keys.peer)
    const peerRefresh = yield* prepareWorkingContextRefresh(runtime, peer.atom.key, target(peer.atom.key))
    yield* need(peerRefresh !== null, "Shared policy was not visible to the other task")
    yield* runtime.submit(peerRefresh.candidate)
    const reopened = yield* observeChild(root, plan.keys.peer)
    yield* need(reopened.result.selection.policyKey.revisionId === executed.run.policyKey.revisionId, "New process did not select the learned revision")
    const revisionBeforeReplay = (yield* runtime.snapshot).canonical.revision
    const duplicate = yield* executeWorkingContextLoop(runtime, original.atom.key, use, writer(), ports)
    yield* need(duplicate.status === "REPLAYED" && (yield* runtime.snapshot).canonical.revision === revisionBeforeReplay, "Duplicate changed state")
    const state = yield* runtime.snapshot
    const prior = state.canonical.atoms.find(atom => atom.key.atomUid === "rule:extract")
    yield* need(prior !== undefined, "Source rule missing")
    const payload = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(prior.content)))
    const content = yield* runtime.stageContent(prior.content.mediaType, new TextEncoder().encode(JSON.stringify({ ...payload, semanticText: payload.semanticText + " Preserve the exact heading punctuation." })))
    const atom = { ...prior, key: { ...prior.key, revisionId: 1 }, content, provenance: { mode: "DERIVATION", sourceRef: prior.key, evidenceSha256: content.sha256 },
      references: [{ referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: prior.key }, ...prior.references] }
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(schemaHash, { _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2",
      transitionId: "local-source-correction", expectedStateRevision: state.canonical.revision, schemaVersion: schema.schemaVersion,
      actorClaim: "isolated-source-owner", authorizationRef: "workspace-source-operator", scope: "read-reason-source", decidedAt: writer().decidedAt,
      traceRef: null, readSet: [prior.key, ...prior.references.map(ref => ref.target)], writes: [atom], provenanceSha256: content.sha256
    }, [{ key: atom.key, payload: content, envelope: yield* describeCanonicalAtomV2Envelope(atom) }]))
    const affected = yield* openWorkingContext(runtime, plan.keys.worker)
    const unrelated = yield* openWorkingContext(runtime, plan.keys.unrelated)
    yield* need(affected.status === "STALE" && unrelated.status === "CURRENT", "Selective invalidation failed")
    const refresh = yield* prepareWorkingContextRefresh(runtime, affected.atom.key, target(affected.atom.key))
    yield* need(refresh !== null, "Affected context did not refresh")
    yield* runtime.submit(refresh.candidate)
    const restored = yield* observeChild(root, plan.keys.worker, "open")
    yield* need(contextHash(restored.result.context.memory) === contextHash(plan.memory) && restored.result.status === "CURRENT", "Restart lost memory or dependency refresh")
    return { status: "VERIFIED_LOCAL_INTEGRATION", realModelCalls: 1, prediction: executed.execution.trace.prediction, expected: plan.expected, reward: executed.assessment.reward,
      traceContent: executed.run.traceContent, outcomeContent: executed.run.outcomeContent, learnedPolicyKey: executed.run.policyKey,
      selectedAfterRestart: reopened.result.selection, separateProcessPid: reopened.pid, memoryRecovered: true,
      affectedRefreshed: restored.result.atom.key, unrelatedUnchanged: unrelated.atom.key, duplicateStatus: duplicate.status,
      boundary: "ISOLATED_NATIVE_CONTEXT_SHARED_POLICY_INTEGRATION_NOT_CANONICAL_PROMOTION_OR_GENERAL_EFFICACY" }
  }).pipe(Effect.provide(layer(root)))
  yield* save(join(root, "result.json"), result)
  return result
})
const check = root => Effect.gen(function* () {
  const plan = yield* json(join(root, "plan.json")), result = yield* json(join(root, "result.json"))
  const reopened = yield* observeChild(root, plan.keys.worker, "open")
  yield* need(reopened.result.status === "CURRENT" && contextHash(reopened.result.context.memory) === contextHash(plan.memory), "Restart memory/dependency mismatch")
  const learning = yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const feedback = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(result.outcomeContent)))
    const trace = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(result.traceContent)))
    const atoms = (yield* runtime.snapshot).canonical.atoms
    const learned = atoms.find(atom => contextHash(atom.key) === contextHash(result.learnedPolicyKey))
    yield* need(learned !== undefined, "Learned policy absent")
    const policy = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(learned.content)))
    const predecessorKey = learned.references.find(ref => ref.referenceType === "hswm:reference:supersedes")?.target
    const predecessor = atoms.find(atom => contextHash(atom.key) === contextHash(predecessorKey))
    yield* need(predecessor !== undefined, "Learning predecessor absent")
    const before = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(predecessor.content)))
    yield* need(contextHash(before.network) !== contextHash(policy.network), "No observed neural parameter change; do not report W update")
    // Independent forward calculation from persisted bytes, without importing the training/selection code.
    const forward = network => {
      const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0)
      const hidden = network.hidden.map(row => Math.tanh(dot(row, [...result.selectedAfterRestart.features.values, 1])))
      return network.outputs.map(row => 1 / (1 + Math.exp(-dot(row, [...hidden, 1]))))
    }
    const meansBefore = forward(before.network), meansAfter = forward(policy.network)
    yield* need(result.selectedAfterRestart.scores.every((score, index) => Math.abs(score.mean - meansAfter[index]) < 1e-12), "Restart selection scores do not use the persisted learned network")
    yield* need(policy.feedbackSha256 === result.outcomeContent.sha256 && feedback.traceContent.sha256 === result.traceContent.sha256 &&
      feedback.executionId === trace.executionId && trace.prediction === result.prediction && feedback.observed === plan.expected &&
      feedback.reward === Number(trace.prediction === plan.expected), "Feedback, actual output, oracle and shared policy do not agree")
    yield* need(atoms.filter(atom => atom.key.atomUid === "working:unrelated").length === 1, "Unrelated working context was rewritten")
    return { policyRevision: learned.key.revisionId, meansBefore, meansAfter }
  }).pipe(Effect.provide(layer(root)))
  return { status: "CHECKED", realModelCalls: result.realModelCalls, reward: result.reward, memoryRecovered: true, selectiveRefresh: true, sharedLearning: true, separateOsProcess: true, learning }
})
const main = args => {
  if (args.length === 1 && args[0] === "--help") return Effect.succeed(help)
  if (args[0] === "prepare" && args.length === 3) return prepare(resolve(args[1]), resolve(args[2])).pipe(Effect.map(result => JSON.stringify(result) + "\n"))
  if (args.length !== 2 || !["run", "check"].includes(args[0])) return Effect.fail(new Error("Use --help"))
  return ({ run, check }[args[0]])(resolve(args[1])).pipe(Effect.map(result => JSON.stringify(result) + "\n"))
}
process.exitCode = await runArgvProcessMain({ refusalPrefix: "AGENT_WORKING_CONTEXT_REFUSED", program: () => main(process.argv.slice(2)), describeFailure: error => error.detail ?? error.message ?? String(error) }, [])
