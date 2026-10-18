#!/usr/bin/env node
/** Bounded, authored Boolean study. All model responses and native revisions are retained locally. */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-schema.js"
import { NativeAdaptiveHttpClient } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
import { contextHash } from "../../src/hswm/effect-runtime/dist/semantic-context-domain.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { prepareActivationInitialization, prepareActivationLearning, executeContextActivation } from "../../src/hswm/effect-runtime/dist/semantic-context-activation-runtime.js"
import { compileCanonicalAtomV2DurableRdfProjection, verifyCanonicalAtomV2DurableRdfProjection } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-rdf-projection.js"

const help = "node _research/local_activation_v1/run.mjs NEW_OUTPUT_DIRECTORY CELL_JSON REGISTRATION_JSON\nRequires a fresh reachable, owner-authorized local transport; max 26 calls, authored Boolean cases only.\nInternal restart: --resume REQUEST_JSON\n"
const unwrap = x => { if (Either.isLeft(x)) throw x.left; return x.right }
const json = x => JSON.stringify(x, null, 2) + "\n"
const sha = x => createHash("sha256").update(x).digest("hex")
// Existing owner vLLM structured-output transport; no answer substitution or oracle in the schema.
const constrained = request => ({ ...request, timeoutMs: Math.min(request.timeoutMs, 30000), body: new TextEncoder().encode(JSON.stringify({
  ...JSON.parse(new TextDecoder().decode(request.body)), max_tokens: 256, temperature: 0.7, top_p: 0.8, top_k: 20, min_p: 0, seed: 17,
  chat_template_kwargs: { enable_thinking: false }, structured_outputs: { json: { type: "object", additionalProperties: false,
    required: ["prediction", "uncertainty"], properties: { prediction: { type: "string" }, uncertainty: { type: "string" } } } }
})) })
const owner = "owner:local-activation-study"
const schemaVersion = "local-activation-study-v1"
const key = (atomUid, revisionId = 0) => ({ schemaVersion, lineageId: "activation-study", atomUid, revisionId })
const schema = {
  _tag: "HSWMCanonicalSchemaV2", contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, schemaVersion,
  scientificStatus: "UNJUDGED", bootstrapTrustStatement: "AUTHORED_BOOLEAN_STUDY_NOT_PRODUCTION_ADMISSION", owners: [{ address: owner, obligation: "Bounded local experiment" }],
  kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: [owner], minimumArity: 0, referenceContracts: [] },
    { kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 4, referenceContracts: [
      { referenceType: "hswm:semantic:role", roles: ["subject", "context", "evidence", "exception"].map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 1 })) },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }
    ] },
    { kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 1, referenceContracts: [
      { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }
    ] }
  ]
}
const config = { encoderRevision: "authored-signal/v1", featureNames: ["bias", "signal"], alpha: 1 }
const target = revisionId => ({ key: key("policy:activation", revisionId), owner, authorizationRef: "local-study-owner", scope: "authored-boolean-study", decidedAt: "2026-10-18T13:34:00.000Z" })
const cases = {
  train: Array.from({ length: 8 }, (_, i) => ({ id: `train-v3-${i}`, signal: i % 2 === 0 ? 1 : -1, bit: Math.floor(i / 2) % 2 })),
  holdout: [0.7, -0.7, 0.4, -0.4].flatMap((signal, i) => [0, 1].map(bit => ({ id: `holdout-v3-${i}-${bit}`, signal, bit }))),
  restart: [{ id: "restart-v3-positive", signal: 0.9, bit: 1 }, { id: "restart-v3-negative", signal: -0.9, bit: 1 }]
}
const expected = c => String(c.signal > 0 ? c.bit : 1 - c.bit)
const specFor = c => ({ contract: "hswm-semantic-context-spec/v1", event: JSON.stringify(c), mandatoryRelationUids: ["rule:mandatory"],
  candidates: [{ id: "identity", summary: "Apply the identity Boolean rule", relationUids: ["rule:identity"] }, { id: "complement", summary: "Apply the complement Boolean rule", relationUids: ["rule:complement"] }],
  maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 })
const features = plan => ({ encoderRevision: config.encoderRevision, eventSha256: contextHash(plan.spec.event), values: [1, JSON.parse(plan.spec.event).signal] })
const decision = (plan, revision, mode) => ({ policyKey: key("policy:activation", revision), features: features(plan), mode })
const seed = runtime => Effect.gen(function* () {
  const writes = []
  const semantics = { mandatory: '/no_think Return only JSON with prediction and uncertainty strings. Apply the one supplied Boolean rule to event.bit. The signal field is for routing, not an extra operand. If bit is not 0 or 1, prediction must be REFUSE. No tools, no explanations.',
    identity: 'Identity Boolean rule: prediction is event.bit unchanged, formatted as "0" or "1".',
    complement: 'Complement Boolean rule: prediction is 1 minus event.bit, formatted as "0" or "1".' }
  for (const [name, semanticText] of Object.entries(semantics)) {
    const participants = []
    for (const role of ["subject", "context", "evidence", "exception"]) {
      const content = yield* runtime.stageContent("text/plain", new TextEncoder().encode(role === "exception" ? "Invalid bit must produce REFUSE." : `${name}: ${role}; authored Boolean study v1`))
      participants.push({ _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key(`${name}:${role}`), kind: "semantic_participant", responsibilityOwner: owner, content,
        provenance: { mode: "BOOTSTRAP", evidenceSha256: contextHash(semantics), sourceRef: null }, lifecycle: "ADMITTED", references: [] })
    }
    const content = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", new TextEncoder().encode(JSON.stringify({ semanticText, disposition: "predict", uncertainty: "authored rule", exceptionRefs: [`${name}:exception`], trace: null, outcome: null })))
    writes.push(...participants, { _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key(`rule:${name}`), kind: "semantic_relation", responsibilityOwner: owner, content,
      provenance: { mode: "BOOTSTRAP", evidenceSha256: contextHash(semantics), sourceRef: null }, lifecycle: "ADMITTED",
      references: participants.map((p, i) => ({ referenceType: "hswm:semantic:role", role: ["subject", "context", "evidence", "exception"][i], target: p.key })) })
  }
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: "seed-activation-study", expectedStateRevision: 0, schemaVersion,
    actorClaim: "local-study-owner", authorizationRef: "local-study-owner", scope: "authored-boolean-study", decidedAt: target(0).decidedAt, traceRef: null, readSet: [], writes, provenanceSha256: contextHash(semantics)
  }, writes.map(atom => ({ key: atom.key, payload: atom.content, envelope: unwrap(describeCanonicalAtomV2Envelope(atom)) }))))
})

const run = (output, cellPath, registrationPath) => Effect.gen(function* () {
  const cell = yield* Effect.try(() => JSON.parse(readFileSync(cellPath, "utf8")))
  const registration = yield* Effect.try(() => JSON.parse(readFileSync(registrationPath, "utf8")))
  if (registration.maximumProviderCalls !== 26 || Date.parse(registration.expiresAt) <= Date.now() || registration.reachability?.status !== 200 || Date.now() - Date.parse(registration.reachability.observedAt) > 1800000 || !registration.transport.includes(cell.base_url)) return yield* Effect.fail("NOT_READY: registration or fresh reachability mismatch")
  if (existsSync(output)) return yield* Effect.fail("NEW output directory required")
  yield* Effect.try(() => mkdirSync(output, { recursive: true, mode: 0o700 }))
  const save = (name, value) => Effect.try(() => writeFileSync(join(output, name), json(value), { flag: "wx", mode: 0o600 }))
  const protocol = { contract: "hswm-local-activation-study/v3", frozenAt: new Date().toISOString(), config, cases, maximumCalls: 26,
    model: cell.model, evaluator: "EXACT_STRING_SIGN_SIGNAL_BOOLEAN_V1", reward: "signal>0 ? bit : 1-bit; exact real prediction string", baseline: "untrained deterministic first arm", evaluationMode: "EXPLOIT", trainingMode: "EXPLORE",
    claimScope: "AUTHORED_BOOLEAN_CONTEXT_GENERALIZATION_ONLY", independentNaturalTasks: false, seed: null,
    previousIncompleteAttemptCalls: 3, repair: "Existing owner vLLM structured JSON and nonthinking transport uniformly across phases; new heldout signal values; 8 train calls to stay within the original total 30-call budget",
    inference: { max_tokens: 256, thinking: false, temperature: 0.7, top_p: 0.8, top_k: 20, min_p: 0, seed: 17, structuredJson: true, timeoutMs: 30000 },
    expectedCalls: { baseline: 8, train: 8, final: 8, restart: 2 }, frozenSourceSha256: sha(readFileSync(new URL(import.meta.url))) }
  yield* save("protocol.json", protocol)
  yield* Effect.try(() => writeFileSync(join(output, "runner-source.mjs"), readFileSync(new URL(import.meta.url)), { flag: "wx", mode: 0o600 }))
  yield* save("schema.json", schema)
  const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
  const binding = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding
  const root = join(output, "native")
  const layer = makeCanonicalAtomV2DurableRuntimeFileLayer(root, "activation-study-journal", schemaBytes, [{ authorizationRef: "local-study-owner", schemaVersion, schemaContentSha256: binding.content.sha256, scopes: ["authored-boolean-study"] }])
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seed(runtime)
    const start = yield* prepareSemanticContext(runtime, specFor(cases.train[0]))
    const init = yield* prepareActivationInitialization(runtime, start, config, target(0))
    yield* runtime.submit(init.candidate)
    const sourceBefore = (yield* runtime.snapshot).canonical.atoms.filter(a => a.kind !== "semantic_context_policy")
    let calls = 0
    const http = { postJson: request => Effect.gen(function* () {
      if (++calls > 24) return yield* Effect.fail("Provider budget exceeded before restart")
      const actual = constrained(request)
      yield* save(`wire-${calls}-request.json`, JSON.parse(new TextDecoder().decode(actual.body)))
      const bytes = yield* NativeAdaptiveHttpClient.postJson(actual)
      yield* save(`wire-${calls}-response.json`, JSON.parse(new TextDecoder().decode(bytes)))
      return bytes
    }) }
    const records = []
    const execute = (phase, c, revision, mode) => Effect.gen(function* () {
      const plan = yield* prepareSemanticContext(runtime, specFor(c))
      const result = yield* executeContextActivation(runtime, plan, decision(plan, revision, mode), cell, http)
      if (!result.trace) return yield* Effect.fail("Missing execution trace")
      const record = { phase, case: c, revision, prediction: result.trace.prediction, expected: expected(c), correct: result.trace.prediction === expected(c), candidateId: result.selection.candidateId, traceContent: result.trace.traceContent }
      records.push(record)
      yield* save(`${phase}-${c.id}.json`, { record, result })
      yield* Effect.sync(() => process.stderr.write(`${phase} ${c.id} ${record.correct ? "correct" : "wrong"} ${record.candidateId}\n`))
      return { plan, result, record }
    })
    for (const c of cases.holdout) yield* execute("baseline", c, 0, "EXPLOIT")
    let revision = 0
    for (const c of cases.train) {
      const executed = yield* execute("train", c, revision, "EXPLORE")
      const proposal = yield* prepareActivationLearning(runtime, executed.plan, { traceContent: executed.result.trace.traceContent, reward: Number(executed.record.correct), observed: JSON.stringify({ prediction: executed.record.prediction, expected: expected(c) }), source: "authored-sign-signal-exact-string-evaluator/v1" }, target(revision + 1))
      yield* runtime.submit(proposal.candidate)
      yield* save(`learn-${revision + 1}.json`, proposal)
      revision++
    }
    for (const c of cases.holdout) yield* execute("final", c, revision, "EXPLOIT")
    const snapshot = yield* runtime.snapshot
    const preserved = contextHash(sourceBefore) === contextHash(snapshot.canonical.atoms.filter(a => a.kind !== "semantic_context_policy"))
    const projection = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
    yield* verifyCanonicalAtomV2DurableRdfProjection(runtime, projection)
    yield* Effect.try(() => writeFileSync(join(output, "native.nq"), projection.projection.nquads, { flag: "wx" }))
    yield* save("native-rdf-manifest.json", projection.manifest)
    // Fresh OS process: public native runtime, same recorded structured transport, no in-memory state.
    for (const c of cases.restart) {
      const input = { durableRoot: root, schema, spec: specFor(c), revision, cell, output, id: c.id }
      yield* save(`${c.id}-input.json`, input)
      const result = yield* Effect.try(() => {
        const child = spawnSync(process.execPath, [new URL(import.meta.url).pathname, "--resume", join(output, `${c.id}-input.json`)], { encoding: "utf8", timeout: 150000, maxBuffer: 1048576 })
        if (child.error || child.status !== 0) throw new Error(`restart failed: ${child.error ?? child.stderr}`)
        return JSON.parse(child.stdout)
      })
      const record = { phase: "restart", case: c, revision, prediction: result.trace?.prediction ?? null, expected: expected(c), correct: result.trace?.prediction === expected(c), candidateId: result.selection.candidateId, traceContent: result.trace?.traceContent ?? null }
      records.push(record)
      yield* save(`restart-${c.id}.json`, { record, result })
    }
    const score = phase => { const rows = records.filter(r => r.phase === phase); return { correct: rows.filter(r => r.correct).length, total: rows.length } }
    const summary = { contract: "hswm-local-activation-result/v1", protocolSha256: sha(readFileSync(join(output, "protocol.json"))), baseline: score("baseline"), train: score("train"), final: score("final"), restart: score("restart"),
      actualModelCalls: calls + 2, finalPolicyRevision: revision, rulesAndRolesPreserved: preserved, canonicalStateRevision: snapshot.canonical.revision,
      modelWeightsUpdated: false, activationStatisticsUpdated: true, scope: protocol.claimScope, modelRevision: "NOT_ATTESTED", registrationSha256: sha(readFileSync(registrationPath)),
      finalPolicy: JSON.parse(new TextDecoder().decode(yield* runtime.readContent(snapshot.canonical.atoms.find(a => a.key.atomUid === "policy:activation" && a.key.revisionId === revision).content))) }
    yield* save("summary.json", summary)
    return json(summary)
  }).pipe(Effect.provide(layer))
})
const resume = path => Effect.gen(function* () {
  const input = yield* Effect.try(() => JSON.parse(readFileSync(path, "utf8")))
  const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(input.schema))
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const plan = yield* prepareSemanticContext(runtime, input.spec)
    const http = { postJson: request => Effect.gen(function* () {
      const actual = constrained(request)
      yield* Effect.try(() => writeFileSync(join(input.output, `${input.id}-wire-request.json`), actual.body, { flag: "wx", mode: 0o600 }))
      const bytes = yield* NativeAdaptiveHttpClient.postJson(actual)
      yield* Effect.try(() => writeFileSync(join(input.output, `${input.id}-wire-response.json`), bytes, { flag: "wx", mode: 0o600 }))
      return bytes
    }) }
    return json(yield* executeContextActivation(runtime, plan, decision(plan, input.revision, "EXPLOIT"), input.cell, http))
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(input.durableRoot, "activation-study-journal", schemaBytes)))
})
if (process.argv[2] === "--help") process.stdout.write(help)
else if (process.argv.length === 4 && process.argv[2] === "--resume") process.exitCode = await runArgvProcessMain({ refusalPrefix: "ACTIVATION_RESUME_REFUSED", program: () => resume(resolve(process.argv[3])), describeFailure: String }, [])
else if (process.argv.length !== 5) { process.stderr.write(help); process.exitCode = 2 }
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "ACTIVATION_STUDY_REFUSED", program: () => run(...process.argv.slice(2).map(p => resolve(p))), describeFailure: String }, [])
