/** Bounded research composition root. Uses the existing native owner, never edits its interpreter. */
import { createRequire } from "node:module"
import { pathToFileURL, fileURLToPath } from "node:url"
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs"
import { resolve, join, relative } from "node:path"
import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import type { CanonicalAtomV2, CanonicalAtomV2Key, HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import type { CanonicalAtomV2DurableRuntime as RuntimeTag } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import type { AdaptiveHttpClientShape } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { protocol, commands, config, features, parseCommand, evaluate, assess, record, type Task, type Row } from "./domain.mts"

type Runtime = RuntimeTag["Type"]
const root = resolve(fileURLToPath(new URL("../../", import.meta.url)))
const dist = process.env["HSWM_RESEARCH_RUNTIME_DIST"]
if (!dist || !dist.startsWith("/")) throw new Error("Explicit absolute HSWM_RESEARCH_RUNTIME_DIST is required")
const { Effect, Either }: typeof import("effect") = createRequire(join(dist, "index.js"))("effect")
const load = (name: string) => import(pathToFileURL(join(dist, name + ".js")).href)
const durable: typeof import("../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js") = await load("canonical-atom-v2-durable-runtime")
const bound: typeof import("../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js") = await load("canonical-atom-v2-content-bound")
const context: typeof import("../../src/hswm/effect-runtime/src/semantic-context-runtime.js") = await load("semantic-context-runtime")
const activation: typeof import("../../src/hswm/effect-runtime/src/semantic-context-activation-runtime.js") = await load("semantic-context-activation-runtime")
const domain: typeof import("../../src/hswm/effect-runtime/src/semantic-context-domain.js") = await load("semantic-context-domain")
const transport: typeof import("../../src/hswm/effect-runtime/src/adaptive-executor.js") = await load("adaptive-executor")
const rdf: typeof import("../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-rdf-projection.js") = await load("canonical-atom-v2-durable-rdf-projection")
const posix: typeof import("../../src/hswm/effect-runtime/src/effect-posix-services.js") = await load("effect-posix-services")
const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest("hex")
const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value))
const read = (path: string): unknown => JSON.parse(readFileSync(path, "utf8"))
const object = (value: unknown) => { if (!record(value)) throw new Error("Expected JSON object"); return value }
const save = (path: string, value: unknown) => writeFileSync(path, JSON.stringify(value, null, 2) + "\n", { flag: "wx", mode: 0o600 })
const io = <A,>(f: () => A) => Effect.try({ try: f, catch: e => new Error(String(e)) })
const owner = "owner:tool-harness-learning-study"
const schemaVersion = "tool-harness-learning-v1", lineageId = "tool-harness-study"
const scope = "local-tool-harness-learning", authorizationRef = "user-request-tool-harness-learning"
const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({ schemaVersion, lineageId, atomUid, revisionId })
const target = (revisionId: number) => ({ key: key("policy:tool-use", revisionId), owner, authorizationRef, scope, decidedAt: "2026-10-20T00:00:00.000Z" })
const roles = ["subject", "context", "evidence", "exception", "tool", "guide"] as const
const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2", contractVersion: "hswm-canonical-schema-contract/v2", schemaVersion, scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "CALLER_AUTHORIZED_ISOLATED_NATIVE_LEARNING_STUDY_NOT_SHARED_CANON",
  owners: [{ address: owner, obligation: "Own the bounded local tool activation policy and preserve exact source roles" }],
  kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: [owner], minimumArity: 0, referenceContracts: [] },
    { kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 6,
      referenceContracts: [
        { referenceType: "hswm:semantic:role", roles: roles.map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 1 })) },
        { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }
      ] },
    { kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 1,
      referenceContracts: [
        { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
        { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }
      ] }
  ]
}
const schemaBytes = Either.getOrThrowWith(bound.canonicalAtomV2SchemaContentBytes(schema), e => e)
const schemaHash = Either.getOrThrowWith(bound.decodeCanonicalAtomV2SchemaContent(schemaBytes), e => e).binding.content.sha256
const layer = (path: string) => durable.makeCanonicalAtomV2DurableRuntimeFileLayer(path, "tool-harness-study", schemaBytes,
  [{ authorizationRef, schemaVersion, schemaContentSha256: schemaHash, scopes: [scope] }])
const spec = (task: Task) => ({
  contract: "hswm-semantic-context-spec/v1", event: JSON.stringify(task), mandatoryRelationUids: ["rule:mandatory"],
  candidates: commands.map(command => ({ id: command, summary: `Use the owned ${command} instruction`, relationUids: [`rule:${command}`] })),
  maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0
})
const decision = (task: Task, revision: number, mode: "EXPLORE" | "EXPLOIT") => ({
  policyKey: key("policy:tool-use", revision), features: { encoderRevision: config.encoderRevision, eventSha256: domain.contextHash(JSON.stringify(task)), values: features(task) }, mode
})
const graphPath = "ontology/development/HSWM_TOOL_HARNESS_2026-10-20.v1.json"
const sources = ["_research/tool_harness_learning_v1/domain.mts", "_research/tool_harness_learning_v1/run.mts",
  "_research/tool_harness_learning_v1/check.mts", "_research/tool_harness_learning_v1/domain.test.mts",
  graphPath, "docs/agent-rules/CLI.md", "ontology/workspace/HSWM_WORKSPACE.v1.json"]
const files = (directory: string): string[] => readdirSync(directory, { withFileTypes: true }).flatMap(entry =>
  entry.isDirectory() ? files(join(directory, entry.name)) : entry.name.endsWith(".js") ? [join(directory, entry.name)] : [])
const sourcePaths = () => {
  const paths = new Set(sources)
  const manifest = object(read(join(root, "ontology/workspace/HSWM_WORKSPACE.v1.json")))
  const ids = new Set([...protocol.train, ...protocol.holdout].map(task => task.bundle))
  if (!Array.isArray(manifest["entries"])) throw new Error("Workspace manifest entries missing")
  for (const raw of manifest["entries"]) {
    const entry = object(raw)
    if (!ids.has(String(entry["id"]))) continue
    const bundlePath = String(entry["bundle"])
    paths.add(bundlePath)
    if (Array.isArray(entry["shapes"])) for (const shape of entry["shapes"]) paths.add(String(shape))
    const bundle = object(read(join(root, bundlePath)))
    if (Array.isArray(bundle["artifact_bindings"])) for (const item of bundle["artifact_bindings"]) paths.add(String(object(item)["path"]))
  }
  return [...paths].sort()
}
const pins = () => ({
  repository: sourcePaths().map(path => ({ path, sha256: existsSync(join(root, path)) ? hash(readFileSync(join(root, path))) : null })),
  runtime: files(dist).sort().map(path => ({ path: relative(dist, path), sha256: hash(readFileSync(path)) }))
})
const seed = (runtime: Runtime, frozenHash: string) => Effect.gen(function* () {
  const graph = readFileSync(join(root, graphPath), "utf8")
  const guide = readFileSync(join(root, "docs/agent-rules/CLI.md"), "utf8")
  const descriptions = {
    subject: "Execute the ONE activated CLI rule on EVENT.bundle. EVENT.focus is used by the learned selector, not permission to switch the selected rule.",
    context: "Bounded read-only HSWM workspace use. The rule outputs command arguments; the host executes the allowlisted CLI separately.",
    evidence: JSON.stringify({ sourceGraph: graphPath, sha256: hash(graph), sourceRootUid: "sym:AbstractNode:hswm-tool-harness-2026-10-20-root",
      roleMapping: { subject: "task", context: "condition", semantic_relation: "rule", tool: "tool", guide: "guide", evidence: "verification" } }),
    exception: "Only show, validate or bindings with the exact EVENT.bundle. No shell, flags, paths, writes, model-judged success or invented command.",
    tool: "src/hswm/effect-runtime/bin/hswm-workspace: read-only show ID, validate ID, bindings ID. This is a source-bound CLI usage relation.",
    guide
  }
  const writes: CanonicalAtomV2[] = []
  for (const role of roles) writes.push({
    _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(`role:${role}`), kind: "semantic_participant",
    responsibilityOwner: owner, lifecycle: "ADMITTED", references: [],
    content: yield* runtime.stageContent("text/plain", new TextEncoder().encode(descriptions[role])),
    provenance: { mode: "BOOTSTRAP", sourceRef: null, evidenceSha256: frozenHash }
  })
  const rules = [
    { id: "mandatory", text: "/no_think Return only JSON with prediction and uncertainty strings. Execute the one supplied command rule exactly; do not choose a different command based on focus. No explanation, tools or markdown." },
    ...commands.map(command => ({ id: command, text: `The activated command is ${command}. Set prediction to the literal text "${command} " followed by the exact value of EVENT.bundle. Keep the separating space. This rule is mandatory for this invocation.` }))
  ]
  for (const rule of rules) writes.push({
    _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(`rule:${rule.id}`), kind: "semantic_relation",
    responsibilityOwner: owner, lifecycle: "ADMITTED",
    content: yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", bytes({
      semanticText: rule.text, disposition: "render-selected-read-only-cli-arguments", uncertainty: "Declared usage rule; utility is learned only from observed output",
      exceptionRefs: ["role:exception"], trace: null, outcome: null
    })),
    references: roles.map(role => ({ referenceType: "hswm:semantic:role", role, target: key(`role:${role}`) })),
    provenance: { mode: "BOOTSTRAP", sourceRef: null, evidenceSha256: frozenHash }
  })
  yield* runtime.submit(bound.makeCanonicalAtomV2ContentBoundInput(schemaHash, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: "seed-tool-harness-learning",
    expectedStateRevision: 0, schemaVersion, actorClaim: owner, authorizationRef, scope, decidedAt: target(0).decidedAt,
    traceRef: null, readSet: [], writes, provenanceSha256: frozenHash
  }, writes.map(atom => ({ key: atom.key, payload: atom.content, envelope: Either.getOrThrowWith(bound.describeCanonicalAtomV2Envelope(atom), e => e) }))))
  const first = protocol.train[0]
  if (!first) return yield* Effect.fail(new Error("Empty training cohort"))
  const plan = yield* context.prepareSemanticContext(runtime, spec(first))
  yield* runtime.submit((yield* activation.prepareActivationInitialization(runtime, plan, config, target(0))).candidate)
})
const copy = (from: string, to: string) => {
  if (existsSync(to)) throw new Error("Copy destination already exists")
  const child = spawnSync("cp", ["-a", from, to], { encoding: "utf8", timeout: 30_000 })
  if (child.status !== 0) throw new Error("Native journal copy failed: " + child.stderr)
}
interface Settings { readonly output: string; readonly cellPath: string; readonly registrationPath: string; readonly checkout: string }
const settings = (raw: unknown): Settings => {
  const v = object(raw)
  for (const name of ["output", "cellPath", "registrationPath", "checkout"]) if (typeof v[name] !== "string" || !v[name].startsWith("/")) throw new Error("Explicit absolute setting required: " + name)
  return { output: String(v["output"]), cellPath: String(v["cellPath"]), registrationPath: String(v["registrationPath"]), checkout: String(v["checkout"]) }
}
const prepared = (s: Settings) => {
  const frozen = object(read(join(s.output, "protocol.json")))
  if (JSON.stringify(frozen["protocol"]) !== JSON.stringify(protocol) || JSON.stringify(frozen["pins"]) !== JSON.stringify(pins()) ||
    frozen["cellSha256"] !== hash(readFileSync(s.cellPath))) throw new Error("Frozen protocol/source/model drift")
  const registration = object(read(s.registrationPath))
  const reachability = object(registration["reachability"])
  if (registration["approved"] !== true || registration["scope"] !== scope || registration["protocolSha256"] !== hash(readFileSync(join(s.output, "protocol.json"))) ||
    registration["maximumProviderCalls"] !== protocol.maximumProviderCalls || !Number.isFinite(Date.parse(String(registration["expiresAt"]))) ||
    Date.parse(String(registration["expiresAt"])) <= Date.now() || !registration["recipient"] || !registration["authorization"] ||
    !registration["revocation"] || reachability["status"] !== 200 || Date.now() - Date.parse(String(reachability["observedAt"])) > protocol.wallLimitMs ||
    Date.parse(String(reachability["observedAt"])) > Date.now()) throw new Error("NOT_READY: current scoped registration and bounded reachability required")
  const cell = object(read(s.cellPath))
  if (registration["transport"] !== cell["base_url"] || registration["cellSha256"] !== frozen["cellSha256"]) throw new Error("Transport/cell mismatch")
  return { frozen, cell, registration }
}
const counter = (s: Settings) => object(read(join(s.output, "counter.json")))
// The coordinator has one writer; workers run sequentially and share the same global ledger.
const http = (s: Settings): AdaptiveHttpClientShape => ({
  postJson: request => Effect.gen(function* () {
    const id = yield* io(() => {
      const state = counter(s), ready = prepared(s)
      const calls = Number(state["calls"]) + 1
      if (calls > protocol.maximumProviderCalls || Date.now() - Number(state["started"]) >= protocol.wallLimitMs ||
        Date.now() >= Date.parse(String(ready.registration["expiresAt"]))) throw new Error("Provider or wall budget exhausted")
      writeFileSync(join(s.output, "counter.json"), JSON.stringify({ ...state, calls }), { mode: 0o600 })
      return calls
    })
    const body = yield* io(() => ({
      ...object(JSON.parse(new TextDecoder().decode(request.body))),
      temperature: 0, seed: 17, chat_template_kwargs: { enable_thinking: false },
      structured_outputs: { json: { type: "object", additionalProperties: false, required: ["prediction", "uncertainty"],
        properties: { prediction: { type: "string" }, uncertainty: { type: "string" } } } }
    }))
    yield* io(() => save(join(s.output, `wire-${id}-request.json`), body))
    const started = performance.now()
    const response = yield* transport.NativeAdaptiveHttpClient.postJson({ ...request, body: bytes(body), timeoutMs: protocol.perCallTimeoutMs })
    yield* io(() => {
      writeFileSync(join(s.output, `wire-${id}-response.json`), response, { flag: "wx", mode: 0o600 })
      save(join(s.output, `wire-${id}-timing.json`), { httpMs: performance.now() - started })
    })
    return response
  }).pipe(Effect.mapError(e => new transport.AdaptiveExecutorError({ code: "HTTP_FAILED", detail: String(e) })))
})
const execute = (runtime: Runtime, s: Settings, phase: string, task: Task, revision: number, mode: "EXPLORE" | "EXPLOIT", forced?: string) => Effect.gen(function* () {
  const plan = yield* context.prepareSemanticContext(runtime, spec(task))
  const cell = yield* io(() => prepared(s).cell)
  const result = forced ? yield* context.executeSelectedSemanticContext(runtime, plan, {
    planSha256: plan.planSha256, status: "SELECTED", candidateId: forced
  }, cell, http(s), "execution_tail") : yield* activation.executeContextActivation(runtime, plan, decision(task, revision, mode), cell, http(s), "execution_tail")
  if (!result.trace) return yield* Effect.fail(new Error("Missing actual trace"))
  const trace = result.trace
  const argv = parseCommand(trace.prediction, task)
  const tool = yield* io(() => {
    if (!argv) return { exitCode: null, stdout: "", stderr: "COMMAND_REJECTED", value: null as unknown }
    const observed = spawnSync(process.execPath, [join(dist, "workspace-process.js"), ...argv], {
      cwd: s.checkout, encoding: "utf8", timeout: protocol.maximumCommandMs, maxBuffer: protocol.maximumOutputBytes
    })
    let value: unknown = null
    try { value = JSON.parse(observed.stdout ?? "") } catch { /* Original bytes and error remain evidence. */ }
    return { exitCode: observed.status, stdout: observed.stdout ?? "", stderr: observed.stderr ?? String(observed.error ?? ""), value }
  })
  const output = yield* runtime.stageContent("application/vnd.hswm.tool-harness-command-observation+json", bytes({
    task, args: argv, exitCode: tool.exitCode, stdout: tool.stdout, stderr: tool.stderr, executionId: trace.executionId
  }))
  const row: Row = { phase, task, candidate: result.selection.candidateId, prediction: trace.prediction,
    correct: evaluate(task, tool.exitCode, tool.value), policyRevision: revision, traceSha256: trace.traceContent.sha256,
    outputSha256: output.sha256, executionId: trace.executionId }
  yield* io(() => {
    save(join(s.output, `${phase}-${task.id}.json`), { row, traceContent: trace.traceContent, outputContent: output })
    process.stderr.write(`${phase} ${task.id}: ${trace.prediction} -> ${row.correct ? "sufficient" : "insufficient"}\n`)
  })
  if (trace.prediction !== `${result.selection.candidateId} ${task.bundle}`) {
    return yield* Effect.fail(new Error("RULE_EXECUTION_VIOLATION: selected rule was not executed; original response retained"))
  }
  return { row, plan, trace, output, tool }
})
const policyState = (runtime: Runtime, task: Task, revision: number) => Effect.gen(function* () {
  const plan = yield* context.prepareSemanticContext(runtime, spec(task))
  return yield* activation.readActivationPolicy(runtime, plan, key("policy:tool-use", revision))
})
const worker = (s: Settings, phase: string, native: string, revision: number) => Effect.gen(function* () {
  yield* io(() => prepared(s))
  const runtime = yield* durable.CanonicalAtomV2DurableRuntime
  const rows: Row[] = []
  for (const task of protocol.holdout) rows.push((yield* execute(runtime, s, phase, task, revision, "EXPLOIT")).row)
  const first = protocol.holdout[0]
  if (!first) return yield* Effect.fail(new Error("Empty holdout"))
  const state = yield* policyState(runtime, first, revision)
  yield* io(() => save(join(s.output, `${phase}-worker.json`), {
    pid: process.pid, native, rows, policyKey: state.atom.key, policyContent: state.atom.content, policy: state.policy
  }))
  return rows
})
const run = (s: Settings) => Effect.gen(function* () {
  const ready = yield* io(() => prepared(s))
  yield* io(() => save(join(s.output, "started.json"), { startedAt: new Date().toISOString() }))
  yield* io(() => save(join(s.output, "counter.json"), { started: Date.now(), calls: 0 }))
  const runtime = yield* durable.CanonicalAtomV2DurableRuntime
  const frozenHash = hash(readFileSync(join(s.output, "protocol.json")))
  yield* seed(runtime, frozenHash)
  const initial = yield* runtime.snapshot
  yield* io(() => copy(join(s.output, "native"), join(s.output, "initial")))
  for (const command of commands) {
    const task: Task = { id: `dev-${command}`, focus: "navigation", bundle: "tool-harness" }
    const got = yield* execute(runtime, s, "dev", task, 0, "EXPLOIT", command)
    if (got.row.prediction !== `${command} tool-harness` || got.tool.exitCode !== 0) return yield* Effect.fail(new Error("P01_FAILED: command fidelity"))
  }
  const rows: Row[] = []
  for (const task of protocol.holdout) rows.push((yield* execute(runtime, s, "baseline", task, 0, "EXPLOIT")).row)
  let revision = 0
  const feedbacks: unknown[] = []
  for (const task of protocol.train) {
    const got = yield* execute(runtime, s, "train", task, revision, "EXPLORE")
    rows.push(got.row)
    // A tool result is evaluated by the fixed host contract, never by the LLM's confidence.
    const feedback = { traceContent: got.trace.traceContent, reward: Number(got.row.correct),
      observed: JSON.stringify({ task, outputContent: got.output, exitCode: got.tool.exitCode, sufficient: got.row.correct }),
      source: "workspace-information-contract/v1; agent-authored evaluator over actual CLI bytes" }
    const learned = yield* activation.prepareActivationLearning(runtime, got.plan, feedback, target(revision + 1))
    yield* runtime.submit(learned.candidate)
    revision++
    const repeated = yield* Effect.either(activation.prepareActivationLearning(runtime, got.plan, feedback, target(revision + 1)))
    if (Either.isRight(repeated)) return yield* Effect.fail(new Error("Duplicate feedback accepted"))
    feedbacks.push({ feedback, outcomeContent: learned.outcomeContent, policyKey: learned.policyKey, policy: learned.policy })
    yield* io(() => save(join(s.output, `learn-${revision}.json`), feedbacks.at(-1)))
  }
  const final = yield* runtime.snapshot
  const nonPolicy = (atoms: readonly CanonicalAtomV2[]) => atoms.filter(a => a.kind !== "semantic_context_policy")
  if (domain.contextHash(nonPolicy(initial.canonical.atoms)) !== domain.contextHash(nonPolicy(final.canonical.atoms))) return yield* Effect.fail(new Error("Source/role atoms changed"))
  yield* io(() => {
    copy(join(s.output, "native"), join(s.output, "learned-snapshot"))
    copy(join(s.output, "initial"), join(s.output, "observations-only"))
    copy(join(s.output, "initial"), join(s.output, "removed"))
    copy(join(s.output, "learned-snapshot"), join(s.output, "restored"))
  })
  // Retain the same observations in the control's content store, but admit no policy update.
  yield* Effect.gen(function* () {
    const control = yield* durable.CanonicalAtomV2DurableRuntime
    for (const feedback of feedbacks) yield* control.stageContent("application/vnd.hswm.tool-harness-control-feedback+json", bytes(feedback))
  }).pipe(Effect.provide(layer(join(s.output, "observations-only"))))
  const runWorker = (phase: string, native: string, selectedRevision: number) => io(() => {
    const path = join(s.output, `${phase}-input.json`)
    save(path, { settings: s, phase, native, revision: selectedRevision })
    const result = spawnSync(process.execPath, [fileURLToPath(import.meta.url), "--worker", path], {
      encoding: "utf8", timeout: 600_000, maxBuffer: 2_097_152, env: process.env
    })
    process.stderr.write(result.stderr ?? "")
    if (result.status !== 0) throw new Error(`Worker ${phase} incomplete: ${result.stderr}`)
    const value = object(read(join(s.output, `${phase}-worker.json`)))
    if (value["pid"] === process.pid) throw new Error("Worker did not restart")
    return value["rows"] as Row[]
  })
  for (const [phase, native, selectedRevision] of [
    ["learned", "native", revision], ["observations-only", "observations-only", 0],
    ["removed", "removed", 0], ["restored", "restored", revision]
  ] as const) rows.push(...yield* runWorker(phase, join(s.output, native), selectedRevision))
  const projection = yield* rdf.compileCanonicalAtomV2DurableRdfProjection(runtime)
  yield* rdf.verifyCanonicalAtomV2DurableRdfProjection(runtime, projection)
  yield* io(() => {
    writeFileSync(join(s.output, "native.nq"), projection.projection.nquads, { flag: "wx", mode: 0o600 })
    save(join(s.output, "native-rdf-manifest.json"), projection.manifest)
  })
  const count = counter(s)
  const assessment = assess(rows)
  const summary = { ...assessment, rows, policyRevision: revision, actualProviderCalls: count["calls"],
    protocolSha256: frozenHash, policyUpdates: feedbacks.length, duplicateFeedbackRejected: true,
    sourceRoleAtomsPreserved: true, nativeStateRevision: final.canonical.revision,
    cellSha256: ready.frozen["cellSha256"], claimCeiling: protocol.scope }
  yield* io(() => save(join(s.output, "summary.json"), summary))
  if (count["calls"] !== protocol.expectedProviderCalls || !assessment.accepted) return yield* Effect.fail(new Error("Frozen acceptance criteria not met; all evidence retained"))
  return summary
})

const main = Effect.gen(function* () {
  const [mode, path] = process.argv.slice(2)
  if (mode === "--help") return "run.mts --prepare SETTINGS.json | --run SETTINGS.json\nExplicit pinned runtime dist; prepare performs no model call. Run requires current registration and reachability. No retries or resume."
  if (!path) return yield* Effect.fail(new Error("Settings path required"))
  if (mode === "--worker") {
    const request = yield* io(() => object(read(path)))
    const s = settings(request["settings"])
    return yield* worker(s, String(request["phase"]), String(request["native"]), Number(request["revision"])).pipe(Effect.provide(layer(String(request["native"]))))
  }
  const s = yield* io(() => settings(read(path)))
  if (mode === "--prepare") return yield* io(() => {
    if (existsSync(s.output)) throw new Error("New output required")
    mkdirSync(s.output, { recursive: true, mode: 0o700 })
    const cell = object(read(s.cellPath))
    if (cell["model"] !== "qwen3-4b-real" || cell["max_tokens"] !== 128 || cell["api_key_env"] !== undefined) throw new Error("This first fixed protocol requires the existing owner Qwen cell, 128 tokens, no credential")
    save(join(s.output, "protocol.json"), { protocol, config, pins: pins(), cellSha256: hash(readFileSync(s.cellPath)),
      frozenAt: new Date().toISOString(), inference: { temperature: 0, seed: 17, enableThinking: false, structuredJson: true } })
    return { status: "PREPARED", protocolSha256: hash(readFileSync(join(s.output, "protocol.json"))) }
  })
  if (mode !== "--run") return yield* Effect.fail(new Error("Unknown mode"))
  return yield* run(s).pipe(Effect.provide(layer(join(s.output, "native"))))
})
const outcome = await Effect.runPromise(Effect.either(main.pipe(Effect.provide(posix.NodePosixServicesLive))))
if (Either.isLeft(outcome)) { process.stderr.write(JSON.stringify({ status: "INCOMPLETE", error: String(outcome.left) }) + "\n"); process.exitCode = 1 }
else process.stdout.write(JSON.stringify(outcome.right) + "\n")
