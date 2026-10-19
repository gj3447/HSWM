#!/usr/bin/env node
/** Frozen authored finite study. --prepare never calls a model; --run requires current scoped registration. */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/dist/effect-posix-services.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { contextHash } from "../../src/hswm/effect-runtime/dist/semantic-context-domain.js"
import { prepareSemanticContext, executeSelectedSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { prepareActivationInitialization, prepareActivationLearning, executeContextActivation } from "../../src/hswm/effect-runtime/dist/semantic-context-activation-runtime.js"
import { proposeContextRetirements, prepareContextTopologyChange, readContextTopology } from "../../src/hswm/effect-runtime/dist/semantic-context-topology-runtime.js"
import { NativeAdaptiveHttpClient } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"
import { HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-schema.js"
import { decodeFiniteProgram, finiteProgramAccepts } from "../../src/hswm/effect-runtime/dist/semantic-context-finite-domain.js"

const help = `node _research/semantic_w_loop_v1/run.mjs --prepare NEW_OUTPUT CELL_JSON
  Freeze two repeated authored finite cohorts, source pins, model and 120-call/30-minute cap. No provider request.
node _research/semantic_w_loop_v1/run.mjs --run PREPARED_OUTPUT CELL_JSON REGISTRATION_JSON
  Requires current owner approval, protocolSha256, fresh successful bounded reachability, and exact cell binding.
  No retry, no resume of a partial cohort, no holdout-based adjustment. Actual bytes and failures stay private.
Internal --child REQUEST_JSON reopens the admitted topology and executes two fresh inputs.
--check validates the authored finite operators exhaustively without a provider or store.
--rehearse NEW_OUTPUT runs the same cohorts through an explicitly scripted finite interpreter; zero provider calls, no efficacy evidence.
Guide: docs/operations/HSWM_SEMANTIC_W_LOOP_2026-10-19.md
`
const sha = x => createHash("sha256").update(x).digest("hex")
const read = p => JSON.parse(readFileSync(p, "utf8"))
const save = (p, x) => writeFileSync(p, JSON.stringify(x, null, 2) + "\n", { flag: "wx", mode: 0o600 })
const unwrap = e => { if (Either.isLeft(e)) throw e.left; return e.right }
const root = resolve(new URL("../..", import.meta.url).pathname)
const owner = "owner:semantic-w-loop-study"
const schemaVersion = "semantic-w-loop-study-v1"
const key = (atomUid, revisionId = 0) => ({ schemaVersion, lineageId: "finite-study", atomUid, revisionId })
const target = (uid, revisionId) => ({ key: key(uid, revisionId), owner, authorizationRef: "study-owner", scope: "authored-finite-study", decidedAt: "2026-10-19T00:00:00.000Z" })
const schema = {
  _tag: "HSWMCanonicalSchemaV2", contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, schemaVersion, scientificStatus: "UNJUDGED", bootstrapTrustStatement: "ISOLATED_AUTHORED_FINITE_STUDY_NOT_PRODUCTION_AUTHORITY",
  owners: [{ address: owner, obligation: "Bounded authored finite experiment" }], kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: [owner], minimumArity: 0, referenceContracts: [] },
    { kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 4, referenceContracts: [
      { referenceType: "hswm:semantic:role", roles: ["subject", "context", "evidence", "exception"].map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 1 })) },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }] },
    { kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 1, referenceContracts: [
      { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }] }
  ]
}
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = path => makeCanonicalAtomV2DurableRuntimeFileLayer(path, "finite-study", schemaBytes, [{ authorizationRef: "study-owner", schemaVersion, schemaContentSha256: schemaHash, scopes: ["authored-finite-study"] }])
const config = { encoderRevision: "authored-sign-signal/v2", featureNames: ["bias", "signal"], alpha: 1 }
const spec = event => ({ contract: "hswm-semantic-context-spec/v1", event: JSON.stringify(event), mandatoryRelationUids: ["rule:mandatory"],
  candidates: [{ id: "identity", summary: "identity finite operator", relationUids: ["rule:identity", "rule:duplicate"] }, { id: "complement", summary: "complement finite operator", relationUids: ["rule:complement"] }], maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 })
const decision = (plan, revision, mode) => ({ policyKey: key("policy:w", revision), features: { encoderRevision: config.encoderRevision, eventSha256: contextHash(plan.spec.event), values: [1, JSON.parse(plan.spec.event).signal] }, mode })
const expected = c => c.invalid ? "REFUSE" : String(c.signal > 0 ? c.bit : 1 - c.bit)

// The model receives explicit operator constraints, never the sign-to-rule routing oracle.
const program = kind => {
  const expressions = [], alternatives = []
  const add = expression => (expressions.push(expression), expressions.length - 1)
  for (const bit of [0, 1]) for (const invalid of [0, 1]) for (const prediction of ["0", "1", "REFUSE"]) {
    const allowed = invalid ? prediction === "REFUSE" : kind === "mandatory" ? prediction !== "REFUSE" : prediction === String(kind === "complement" ? 1 - bit : bit)
    if (!allowed) continue
    const x = add({ op: "is", variable: "bit", value: String(bit) }), e = add({ op: "is", variable: "invalid", value: String(invalid) }), y = add({ op: "is", variable: "prediction", value: prediction })
    alternatives.push(add({ op: "and", left: add({ op: "and", left: x, right: e }), right: y }))
  }
  const expression = alternatives.reduce((a, b) => add({ op: "or", left: a, right: b }))
  return JSON.stringify({ contract: "hswm-finite-semantic-program/v1", variables: [
    { id: "bit", roleOrdinal: 0, values: ["0", "1"] }, { id: "prediction", roleOrdinal: 1, values: ["0", "1", "REFUSE"] }, { id: "invalid", roleOrdinal: 3, values: ["0", "1"] }
  ], expressions, clauses: [{ id: "operator", expression }] })
}
const seed = runtime => Effect.gen(function* () {
  const writes = []
  const roles = {
    subject: "Input event.bit is 0 or 1. event.signal is only a routing feature, never an operator operand.",
    context: "/no_think Each semanticText is a finite constraint program. Evaluate ordered expressions: is compares variable/value strings; and/or/not combine earlier indexed expressions. All clauses must hold. Bind bit and invalid to event values and choose the unique satisfying prediction. Return only JSON with prediction and uncertainty strings.",
    evidence: "Authored finite study. All supplied constraints apply together; duplicated constraints do not change their conjunction.",
    exception: "event.invalid is 0 or 1. The invalid=1 exception requires prediction REFUSE and must not be removed."
  }
  for (const [role, text] of Object.entries(roles)) writes.push({ _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(`shared:${role}`), kind: "semantic_participant", responsibilityOwner: owner,
    content: yield* runtime.stageContent("text/plain", new TextEncoder().encode(text)), lifecycle: "ADMITTED", references: [], provenance: { mode: "BOOTSTRAP", sourceRef: null, evidenceSha256: contextHash(roles) } })
  for (const name of ["mandatory", "identity", "duplicate", "complement"]) writes.push({ _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(`rule:${name}`), kind: "semantic_relation", responsibilityOwner: owner,
    content: yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", new TextEncoder().encode(JSON.stringify({ semanticText: program(name), disposition: "predict", uncertainty: "authored finite operator", exceptionRefs: ["shared:exception"], trace: null, outcome: null }))),
    lifecycle: "ADMITTED", provenance: { mode: "BOOTSTRAP", sourceRef: null, evidenceSha256: contextHash(roles) },
    references: Object.keys(roles).map(role => ({ referenceType: "hswm:semantic:role", role, target: key(`shared:${role}`) })) })
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(schemaHash, { _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: "seed-finite-study", expectedStateRevision: 0,
    schemaVersion, actorClaim: "study-owner", authorizationRef: "study-owner", scope: "authored-finite-study", decidedAt: target("x", 0).decidedAt, traceRef: null, readSet: [], writes, provenanceSha256: contextHash(roles) }, writes.map(a => ({ key: a.key, payload: a.content, envelope: unwrap(describeCanonicalAtomV2Envelope(a)) }))))
})
const sourcePaths = ["_research/semantic_w_loop_v1/run.mjs", ...["semantic-context-runtime", "semantic-context-activation-domain", "semantic-context-activation-runtime", "semantic-context-topology-domain", "semantic-context-topology-runtime", "semantic-context-presentation-domain", "semantic-context-finite-domain"].flatMap(n => [`src/hswm/effect-runtime/src/${n}.ts`, `src/hswm/effect-runtime/dist/${n}.js`])]
const prepare = (output, cellPath, backend = "OWNER_MODEL") => {
  if (existsSync(output)) throw new Error("NEW output directory required")
  const cell = read(cellPath)
  if (cell.model !== "qwen3-4b-real" || cell.max_tokens !== 512) throw new Error("This protocol requires qwen3-4b-real, max_tokens=512; use an explicitly prepared cell")
  mkdirSync(output, { recursive: true, mode: 0o700 })
  const protocol = { contract: "hswm-semantic-w-loop-study/v1", backend, frozenAt: new Date().toISOString(), model: backend === "OWNER_MODEL" ? cell.model : "SCRIPTED_FINITE_INTERPRETER_NOT_MODEL", cellSha256: sha(readFileSync(cellPath)), config,
    maximumProviderCalls: 120, expectedProviderCalls: 116, wallLimitMs: 1800000, concurrency: 1, perCallTimeoutMs: 30000, sourcePins: sourcePaths.map(path => ({ path, sha256: sha(readFileSync(join(root, path))) })),
    cohorts: [0, 1].map(n => ({ id: `repeat-${n}`, dev: ["identity", "complement"].flatMap(action => [0, 1].flatMap(bit => [0, 1].map(invalid => ({ id: `dev-${n}-${action}-${bit}-${invalid}`, action, bit, invalid, signal: action === "identity" ? 0.91 : -0.91 })))),
      train: Array.from({ length: 8 }, (_, i) => ({ id: `train-${n}-${i}`, signal: i % 2 === 0 ? 1 : -1, bit: Math.floor(i / 2) % 2, invalid: 0 })),
      holdout: [0.61 + n * 0.02, -0.61 - n * 0.02, 0.22 + n * 0.02, -0.22 - n * 0.02].flatMap((signal, i) => [0, 1].map(bit => ({ id: `holdout-${n}-${i}-${bit}`, signal, bit, invalid: i >= 2 ? 1 : 0 }))),
      restart: [{ id: `restart-${n}-0`, bit: 0, invalid: 0, signal: 0.93 }, { id: `restart-${n}-1`, bit: 1, invalid: 1, signal: -0.93 }] })),
    comparisons: "B0 original/untrained, B1 original/learned, B2 retired/reset-untrained, B3 retired/relearned; presentation fixed throughout",
    topology: "Remove rule:duplicate from identity only; train support >=1; whole finite meaning and roles must be preserved",
    reward: "Exact observed prediction vs invalid ? REFUSE : signal>0 ? bit : 1-bit. No confidence reward.",
    criteria: { devViolations: 0, heldoutExceptionViolations: 0, minimumAccuracyGainForW: 0, minimumAccuracyGainForWComparison: "STRICTLY_GREATER", structureAccuracyTolerance: 0, minimumFrameByteSaving: "STRICTLY_POSITIVE", failedOrMissing: "INCOMPLETE" },
    uncertainty: "Two repeated authored finite cohorts, not independent natural tasks or a population confidence interval; provider sampling/weight revision NOT_ATTESTED.",
    cost: "Record actual trace prompt bytes, canonical context bytes, full provider usage when present and HTTP wall time separately; all training, review and restart costs belong to total budget.",
    selection: "LinUCB deterministic; no IPS export. Frozen holdout reused across conditions, never used for updates or candidate tuning. B2 topology is preregistered, not selected by holdout." }
  save(join(output, "protocol.json"), protocol)
  return { status: "PREPARED_NOT_EXECUTED", protocolSha256: sha(readFileSync(join(output, "protocol.json"))), calls: 0 }
}
const ready = (output, cellPath, registrationPath) => {
  const p = read(join(output, "protocol.json")), cell = read(cellPath)
  for (const s of p.sourcePins) if (sha(readFileSync(join(root, s.path))) !== s.sha256) throw new Error(`SOURCE_DRIFT: ${s.path}`)
  if (p.cellSha256 !== sha(readFileSync(cellPath))) throw new Error("CELL_DRIFT")
  if (p.backend === "SCRIPTED_FINITE_INTERPRETER") return { protocol: p, cell, registration: { expiresAt: new Date(Date.parse(p.frozenAt) + p.wallLimitMs).toISOString() } }
  if (p.backend !== "OWNER_MODEL") throw new Error("Unknown execution backend")
  const registration = read(registrationPath)
  if (registration.protocolSha256 !== sha(readFileSync(join(output, "protocol.json"))) || registration.cellSha256 !== sha(readFileSync(cellPath)) || p.cellSha256 !== registration.cellSha256 ||
    registration.maximumProviderCalls !== p.maximumProviderCalls || Date.parse(registration.expiresAt) <= Date.now() || !Number.isFinite(Date.parse(registration.expiresAt)) ||
    registration.approved !== true || registration.resource !== "hswm/semantic-w-loop-study/v1" || registration.scope !== "authored-finite-study" ||
    !registration.authorization || !registration.recipient || !registration.revocation || registration.reachability?.status !== 200 ||
    !Number.isFinite(Date.parse(registration.reachability.observedAt)) || Date.now() - Date.parse(registration.reachability.observedAt) > 1800000 ||
    Date.parse(registration.reachability.observedAt) > Date.now() || registration.transport !== cell.base_url) throw new Error("NOT_READY: exact current owner registration and bounded reachability required")
  return { protocol: p, cell, registration }
}
const post = (protocol, request) => protocol.backend !== "SCRIPTED_FINITE_INTERPRETER" ? NativeAdaptiveHttpClient.postJson(request) : Effect.try(() => {
  const body = JSON.parse(new TextDecoder().decode(request.body)), payload = JSON.parse(body.messages[0].content.split("\n")[1]), event = JSON.parse(payload.event)
  const programs = payload.frames.map(f => unwrap(decodeFiniteProgram(f.relation.semantic.semanticText)))
  const answers = ["0", "1", "REFUSE"].filter(prediction => programs.every(p => finiteProgramAccepts(p, [String(event.bit), prediction, String(event.invalid)])))
  if (answers.length !== 1) throw new Error("Scripted finite interpreter requires one satisfying prediction")
  return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: answers[0], uncertainty: "SCRIPTED_FINITE_INTERPRETER_NOT_MODEL" }) } }] }))
})
const run = (output, cellPath, registrationPath) => Effect.gen(function* () {
  const { protocol, cell, registration } = yield* Effect.try(() => ready(output, cellPath, registrationPath))
  if (existsSync(join(output, "started.json"))) return yield* Effect.fail("Already started; no automatic resume or retry")
  const started = Date.now()
  yield* Effect.try(() => save(join(output, "started.json"), { startedAt: new Date(started).toISOString(), protocolSha256: sha(readFileSync(join(output, "protocol.json"))) }))
  let calls = 0
  const wire = { postJson: request => Effect.gen(function* () {
    if (calls >= protocol.maximumProviderCalls || Date.now() - started >= protocol.wallLimitMs || Date.now() >= Date.parse(registration.expiresAt)) return yield* Effect.fail(new Error("Budget or authorization expired"))
    const id = ++calls, t = performance.now()
    const bytes = yield* post(protocol, { ...request, timeoutMs: protocol.perCallTimeoutMs })
    yield* Effect.try(() => save(join(output, `call-${id}.json`), { httpMs: performance.now() - t, response: JSON.parse(new TextDecoder().decode(bytes)) }))
    return bytes
  }) }
  const summaries = []
  for (const cohort of protocol.cohorts) {
    const directory = join(output, cohort.id)
    yield* Effect.try(() => mkdirSync(directory, { mode: 0o700 }))
    const summary = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      yield* seed(runtime)
      let plan = yield* prepareSemanticContext(runtime, spec(cohort.train[0]))
      yield* runtime.submit((yield* prepareActivationInitialization(runtime, plan, config, target("policy:w", 0))).candidate)
      let revision = 0, topology = null, lastOutcome = null
      const records = []
      const execute = (phase, c, mode) => Effect.gen(function* () {
        const p = topology ? (yield* readContextTopology(runtime, topology, JSON.stringify(c))).plan : yield* prepareSemanticContext(runtime, spec(c))
        const execution = phase === "dev" ? yield* executeSelectedSemanticContext(runtime, p, { planSha256: p.planSha256, status: "SELECTED", candidateId: c.action }, cell, wire, "execution_tail") :
          yield* executeContextActivation(runtime, p, decision(p, revision, mode), cell, wire, "execution_tail")
        if (!execution.trace || !execution.assembly) return yield* Effect.fail("Missing actual execution")
        const row = { phase, id: c.id, candidateId: execution.selection.candidateId, prediction: execution.trace.prediction, expected: expected(c), correct: execution.trace.prediction === expected(c), invalid: c.invalid,
          policyRevision: revision, traceContent: execution.trace.traceContent, contextBytes: execution.assembly.contextBytes }
        records.push(row)
        yield* Effect.try(() => save(join(directory, `${phase}-${c.id}.json`), row))
        if (phase === "train" || phase === "retrain") {
          const learned = yield* prepareActivationLearning(runtime, p, { traceContent: execution.trace.traceContent, reward: Number(row.correct), observed: JSON.stringify({ expected: row.expected, actual: row.prediction }), source: "authored-finite-sign-signal-evaluator/v1" }, target("policy:w", revision + 1))
          yield* runtime.submit(learned.candidate); revision++; lastOutcome = learned.outcomeContent
        }
        return row
      })
      for (const c of cohort.dev) if (!(yield* execute("dev", c, "EXPLOIT")).correct) return yield* Effect.fail("P01_FAILED: dev violation; stop before improvement comparison")
      for (const c of cohort.holdout) yield* execute("B0", c, "EXPLOIT")
      for (const c of cohort.train) yield* execute("train", c, "EXPLORE")
      for (const c of cohort.holdout) yield* execute("B1", c, "EXPLOIT")
      plan = yield* prepareSemanticContext(runtime, spec(cohort.train[0]))
      const basis = { policyKey: key("policy:w", revision), feedbackContent: lastOutcome, partition: "TRAIN", minimumObservations: 1 }
      const proposed = yield* proposeContextRetirements(runtime, plan, basis, 8)
      const selected = proposed.candidates.find(c => c.uid === "rule:duplicate" && c.status === "CANDIDATE")
      if (!selected?.after) return yield* Effect.fail("No supported meaning-preserving preregistered retirement")
      const change = yield* prepareContextTopologyChange(runtime, plan, { operation: "RETIRE", afterSpec: selected.after, policyKey: key("policy:w", revision), basis, priorTopologyKey: null,
        topologyTarget: target("policy:topology", 0), activationTarget: target("policy:w", revision + 1) })
      yield* runtime.submit(change.candidate); revision++; topology = change.topologyKey
      yield* Effect.try(() => save(join(directory, "topology-change.json"), change))
      for (const c of cohort.holdout) yield* execute("B2", c, "EXPLOIT")
      for (const c of cohort.train) yield* execute("retrain", { ...c, id: `re${c.id}` }, "EXPLORE")
      for (const c of cohort.holdout) yield* execute("B3", c, "EXPLOIT")
      const childPath = join(directory, "child-input.json")
      yield* Effect.try(() => save(childPath, { output, cellPath, registrationPath, directory, topology, cases: cohort.restart, started, calls }))
      const child = yield* Effect.try(() => {
        const result = spawnSync(process.execPath, [new URL(import.meta.url).pathname, "--child", childPath], { encoding: "utf8", timeout: 120000, maxBuffer: 1048576 })
        if (result.error || result.status !== 0) throw new Error(`Child incomplete: ${result.error ?? result.stderr}`)
        return JSON.parse(result.stdout)
      })
      calls += child.calls
      const counts = Object.fromEntries(["B0", "B1", "B2", "B3"].map(phase => { const rs = records.filter(r => r.phase === phase); return [phase, { correct: rs.filter(r => r.correct).length, total: rs.length, exceptionViolations: rs.filter(r => r.invalid && !r.correct).length, contextBytes: rs.reduce((n, r) => n + r.contextBytes, 0) }] }))
      const result = { cohort: cohort.id, counts, restart: child, policyRevision: revision, efficacy: "FINITE_REPEATED_OBSERVATION_NOT_GENERAL_EFFICACY",
        WGainOriginal: counts.B1.correct - counts.B0.correct, WGainRetired: counts.B3.correct - counts.B2.correct,
        structureAtInitialW: { accuracyDelta: counts.B2.correct - counts.B0.correct, exceptionViolations: counts.B2.exceptionViolations, contextByteDelta: counts.B2.contextBytes - counts.B0.contextBytes },
        structureAfterLearning: { accuracyDelta: counts.B3.correct - counts.B1.correct, exceptionViolations: counts.B3.exceptionViolations, contextByteDelta: counts.B3.contextBytes - counts.B1.contextBytes },
        accuracyInteraction: (counts.B3.correct - counts.B2.correct) - (counts.B1.correct - counts.B0.correct) }
      yield* Effect.try(() => save(join(directory, "summary.json"), result))
      return result
    }).pipe(Effect.provide(layer(join(directory, "native"))))
    summaries.push(summary)
  }
  if (calls !== protocol.expectedProviderCalls) return yield* Effect.fail("Incomplete declared cohort; cannot publish a complete summary")
  const result = { status: protocol.backend === "OWNER_MODEL" ? "COMPLETED_COHORTS_NOT_GENERAL_EFFICACY" : "SCRIPTED_REHEARSAL_NOT_MODEL_EVIDENCE", actualProviderCalls: protocol.backend === "OWNER_MODEL" ? calls : 0, adapterCalls: calls, summaries }
  yield* Effect.try(() => save(join(output, "summary.json"), result))
  return result
})
const child = path => Effect.gen(function* () {
  const input = yield* Effect.try(() => read(path))
  const { protocol, cell, registration } = yield* Effect.try(() => ready(input.output, input.cellPath, input.registrationPath))
  let calls = 0
  const http = { postJson: request => Effect.gen(function* () {
    if (input.calls + calls >= protocol.maximumProviderCalls || Date.now() - input.started >= protocol.wallLimitMs || Date.now() >= Date.parse(registration.expiresAt)) return yield* Effect.fail(new Error("Child budget expired"))
    calls++
    return yield* post(protocol, { ...request, timeoutMs: protocol.perCallTimeoutMs })
  }) }
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime, results = []
    for (const c of input.cases) {
      const opened = yield* readContextTopology(runtime, input.topology, JSON.stringify(c))
      const executed = yield* executeContextActivation(runtime, opened.plan, decision(opened.plan, opened.policyKey.revisionId, "EXPLOIT"), cell, http, "execution_tail")
      results.push({ id: c.id, policyKey: opened.policyKey, trace: executed.trace, correct: executed.trace?.prediction === expected(c) })
    }
    const result = { calls, results }
    yield* Effect.try(() => save(join(input.directory, "child-result.json"), result))
    return result
  }).pipe(Effect.provide(layer(join(input.directory, "native"))))
})
try {
  const [mode, ...args] = process.argv.slice(2)
  if (mode === "--help") process.stdout.write(help)
  else if (mode === "--rehearse" && args.length === 1) {
    const output = resolve(args[0])
    if (existsSync(output)) throw new Error("NEW rehearsal output required")
    mkdirSync(output, { recursive: true, mode: 0o700 })
    const cellPath = join(output, "cell.json"), runPath = join(output, "run")
    save(cellPath, { base_url: "https://scripted.invalid/v1", model: "qwen3-4b-real", max_tokens: 512 })
    prepare(runPath, cellPath, "SCRIPTED_FINITE_INTERPRETER")
    console.log(JSON.stringify(await Effect.runPromise(run(runPath, cellPath, "NO_REMOTE_REGISTRATION_FOR_SCRIPTED_BACKEND").pipe(Effect.provide(NodePosixServicesLive)))))
  }
  else if (mode === "--check" && args.length === 0) {
    let assignments = 0
    for (const kind of ["mandatory", "identity", "duplicate", "complement"]) {
      const p = unwrap(decodeFiniteProgram(program(kind)))
      for (const bit of [0, 1]) for (const invalid of [0, 1]) for (const prediction of ["0", "1", "REFUSE"]) {
        const wanted = invalid === 1 ? prediction === "REFUSE" : kind === "mandatory" ? prediction === "0" || prediction === "1" :
          prediction === (kind === "complement" ? ["1", "0"][bit] : ["0", "1"][bit])
        if (finiteProgramAccepts(p, [String(bit), prediction, String(invalid)]) !== wanted) throw new Error("Finite operator/oracle mismatch")
        assignments++
      }
    }
    console.log(JSON.stringify({ status: "FINITE_INPUT_CHECKED", assignments, providerCalls: 0 }))
  }
  else if (mode === "--prepare" && args.length === 2) console.log(JSON.stringify(prepare(...args.map(p => resolve(p)))))
  else if (mode === "--run" && args.length === 3) console.log(JSON.stringify(await Effect.runPromise(run(...args.map(p => resolve(p))).pipe(Effect.provide(NodePosixServicesLive)))))
  else if (mode === "--child" && args.length === 1) console.log(JSON.stringify(await Effect.runPromise(child(resolve(args[0])).pipe(Effect.provide(NodePosixServicesLive)))))
  else { process.stderr.write(help); process.exitCode = 2 }
} catch (error) { process.stderr.write(`FINITE_LOOP_REFUSED: ${String(error)}\n`); process.exitCode = 2 }
