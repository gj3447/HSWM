#!/usr/bin/env node
/** Frozen paired development diagnosis. No W update, topology mutation or cohort retry. */
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, copyFileSync, chmodSync, lstatSync, linkSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/dist/effect-posix-services.js"
import { prepareSemanticContext, assembleSelectedSemanticContext, executeSelectedSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { FiniteExecutionViolation } from "../../src/hswm/effect-runtime/dist/semantic-context-finite-execution-domain.js"
import { NativeAdaptiveHttpClient } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"

const repo = resolve(new URL("../..", import.meta.url).pathname)
const read = p => JSON.parse(readFileSync(p, "utf8"))
const hash = b => createHash("sha256").update(b).digest("hex")
const save = (p, x) => writeFileSync(p, JSON.stringify(x, null, 2) + "\n", { flag: "wx", mode: 0o600 })
const need = (ok, message) => { if (!ok) throw new Error(message) }
const inventory = (root, relative = "") => readdirSync(join(root, relative), { withFileTypes: true }).flatMap(e => {
  need(e.isDirectory() || e.isFile(), "Only regular files/directories in original store")
  const path = join(relative, e.name)
  return e.isDirectory() ? inventory(root, path) : [{ path, sha256: hash(readFileSync(join(root, path))) }]
}).sort((a, b) => a.path.localeCompare(b.path))
const sourcePaths = ["_research/finite_guard_live_v1/run.mjs", "_research/finite_guard_live_v1/check.mjs", ...["semantic-context-runtime", "semantic-context-presentation-domain", "semantic-context-finite-presentation-domain", "semantic-context-finite-execution-domain", "semantic-context-finite-domain", "adaptive-executor", "canonical-atom-v2-durable-runtime", "canonical-atom-v2-llm-semantic-runtime"].flatMap(n => [`src/hswm/effect-runtime/src/${n}.ts`, `src/hswm/effect-runtime/dist/${n}.js`])]
const spec = event => ({ contract: "hswm-semantic-context-spec/v1", event: JSON.stringify(event), mandatoryRelationUids: ["rule:mandatory"],
  candidates: [{ id: "identity", summary: "identity finite operator", relationUids: ["rule:identity", "rule:duplicate"] }, { id: "complement", summary: "complement finite operator", relationUids: ["rule:complement"] }], maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 })
// Duplicate content into the isolated store, then recreate links only within that copy.
// Native journal slots and content objects must share inode identity as well as bytes.
const cloneNative = (source, destination, inodes = new Map()) => {
  mkdirSync(destination, { mode: 0o700 })
  for (const entry of readdirSync(source, { withFileTypes: true })) {
    const from = join(source, entry.name), to = join(destination, entry.name)
    need(entry.isDirectory() || entry.isFile(), "Only regular files/directories can be cloned")
    if (entry.isDirectory()) cloneNative(from, to, inodes)
    else {
      const stat = lstatSync(from), key = `${stat.dev}:${stat.ino}`, first = inodes.get(key)
      if (first) linkSync(first, to)
      else { copyFileSync(from, to); chmodSync(to, stat.mode & 0o777); inodes.set(key, to) }
    }
  }
}
const nativeLayer = native => {
  const genesis = readdirSync(join(native, "journal-objects")).map(n => read(join(native, "journal-objects", n))).find(j => j.stateRevision === 0)
  need(genesis, "Source genesis missing")
  return makeCanonicalAtomV2DurableRuntimeFileLayer(native, "finite-study", readFileSync(join(native, "objects", genesis.schema.content.sha256)), [])
}
const prepare = async (source, cellPath, out) => {
  need(!existsSync(out), "NEW output required")
  const cell = read(cellPath)
  need(cell.model === "qwen3-4b-real" && cell.max_tokens === 512, "Fixed previous model/max_tokens required")
  const sources = inventory(source)
  const cases = [0, 1].flatMap(repeat => ["identity", "complement"].flatMap(action => [0, 1].flatMap(bit => [0, 1].map(invalid => ({ id: `guard-dev-${repeat}-${action}-${bit}-${invalid}`, repeat, action, bit, invalid, signal: (action === "identity" ? 1 : -1) * (repeat ? 0.29 : 0.71) })))))
  const protocol = { contract: "hswm-finite-guard-development/v1", frozenAt: new Date().toISOString(), model: cell.model, cellSha256: hash(readFileSync(cellPath)),
    sourceFiles: sources, sourcePins: sourcePaths.map(path => ({ path, sha256: hash(readFileSync(join(repo, path))) })),
    maximumProviderCalls: 32, wallLimitMs: 900000, perCallTimeoutMs: 30000, concurrency: 1,
    cases, treatments: ["plain", "guarded"], presentation: "finite_table_tail", order: "Pair order alternates by case index; each repeat covers both rules, both bits and both exception values",
    success: "guarded must return all 16 cases correctly, zero guard violations/disagreements; otherwise P01_FAILED. A guard rejection is not a correct answer. Valid REFUSE is a returned answer.",
    outcome: "Compare raw prediction to invalid ? REFUSE : action=identity ? bit : 1-bit, after execution; no corrected outputs",
    scope: "DEVELOPMENT_EXPOSED_NOT_HOLDOUT; two repeats of four authored inputs per rule, not iid tasks; no W/topology writes",
    semantics: "Both arms retain full canonical AST and event-independent complete satisfying tables. Guarded adds explicit bit/invalid event-field and prediction bindings plus production post-execution validation. This bundles prompt assistance and checking, not an isolated causal estimate of checking. Same authored Boolean family with new IDs/signals; not a new task distribution.",
    costs: "Report full prompt bytes, provider tokens and HTTP wall time separately; no FLOPs claim; remote sampling and weights not independently attested",
    failure: "Stop on transport/parse/store failure; preserve attempted call and all partial responses; no automatic retry or resume. Record semantic errors across the fixed diagnostic census." }
  mkdirSync(out, { recursive: true, mode: 0o700 })
  cloneNative(source, join(out, "native"))
  const snapshot = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    return yield* runtime.snapshot
  }).pipe(Effect.provide(nativeLayer(join(out, "native"))), Effect.provide(NodePosixServicesLive)))
  need(JSON.stringify(inventory(join(out, "native"))) === JSON.stringify(sources), "Preflight altered source content")
  save(join(out, "preflight.json"), { status: "NATIVE_REOPEN_VERIFIED", snapshotSha256: hash(JSON.stringify(snapshot)), providerAttempts: 0 })
  save(join(out, "protocol.json"), protocol)
  return { status: "PREPARED", protocolSha256: hash(readFileSync(join(out, "protocol.json"))), modelCalls: 0 }
}
const ready = (out, cellPath, registrationPath) => {
  const protocol = read(join(out, "protocol.json")), registration = read(registrationPath), cell = read(cellPath)
  for (const pin of protocol.sourcePins) need(hash(readFileSync(join(repo, pin.path))) === pin.sha256, `SOURCE_DRIFT: ${pin.path}`)
  for (const s of protocol.sourceFiles) need(hash(readFileSync(join(out, "native", s.path))) === s.sha256, `ORIGINAL_DRIFT: ${s.path}`)
  need(hash(readFileSync(cellPath)) === protocol.cellSha256, "CELL_DRIFT")
  need(registration.protocolSha256 === hash(readFileSync(join(out, "protocol.json"))) && registration.cellSha256 === protocol.cellSha256 &&
    registration.approved === true && registration.authorization && registration.recipient && registration.revocation && registration.scope === "finite-guard-development" &&
    registration.maximumProviderCalls === 32 && registration.wallLimitMs === 900000 && registration.concurrency === 1 && registration.transport === cell.base_url &&
    Number.isFinite(Date.parse(registration.expiresAt)) && Date.parse(registration.expiresAt) > Date.now() && registration.reachability?.status === 200 &&
    registration.reachability.modelListed === true &&
    Date.parse(registration.reachability.observedAt) <= Date.now() && Date.now() - Date.parse(registration.reachability.observedAt) < 1800000, "NOT_READY: exact current scoped registration/reachability required")
  return { protocol, registration, cell }
}
const run = (out, cellPath, registrationPath) => Effect.gen(function* () {
  const { protocol, registration, cell } = yield* Effect.try(() => ready(out, cellPath, registrationPath))
  need(!existsSync(join(out, "started.json")), "Already started; no retry/resume")
  const started = Date.now(), native = join(out, "native"), records = []
  yield* Effect.try(() => {
    save(join(out, "registration.json"), registration)
    save(join(out, "started.json"), { startedAt: new Date(started).toISOString(), protocolSha256: hash(readFileSync(join(out, "protocol.json"))), registrationSha256: hash(readFileSync(join(out, "registration.json"))) })
  })
  let calls = 0
  const http = { postJson: request => Effect.gen(function* () {
    need(existsSync(registrationPath) && hash(readFileSync(registrationPath)) === hash(readFileSync(join(out, "registration.json"))) &&
      calls < protocol.maximumProviderCalls && Date.now() - started < protocol.wallLimitMs && Date.now() < Date.parse(registration.expiresAt), "Budget/authorization expired or revoked")
    const id = ++calls
    yield* Effect.try(() => save(join(out, `call-${id}-attempt.json`), { id, at: new Date().toISOString(), requestSha256: hash(request.body) }))
    const t = performance.now(), result = yield* NativeAdaptiveHttpClient.postJson({ ...request, timeoutMs: protocol.perCallTimeoutMs })
    yield* Effect.try(() => { writeFileSync(join(out, `call-${id}-response.json`), result, { flag: "wx", mode: 0o600 }); save(join(out, `call-${id}-cost.json`), { httpMs: performance.now() - t }) })
    return result
  }) }
  const layer = nativeLayer(native)
  const result = yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const before = yield* runtime.snapshot
    for (const [index, c] of protocol.cases.entries()) {
      const order = index % 2 ? [...protocol.treatments].reverse() : protocol.treatments
      for (const treatment of order) {
        const plan = yield* prepareSemanticContext(runtime, spec(c))
        const selection = { planSha256: plan.planSha256, status: "SELECTED", candidateId: c.action }
        const prepared = yield* assembleSelectedSemanticContext(runtime, plan, selection)
        need(prepared.assembly, "Missing assembly")
        const verification = treatment === "guarded" ? { contract: "hswm-finite-execution-guard/v1",
          rules: prepared.assembly.payload.frames.map(f => ({ relationKey: f.relation.key,
            inputs: [{ variable: "bit", eventField: "bit" }, { variable: "invalid", eventField: "invalid" }], outputVariable: "prediction" })) } : undefined
        const execution = yield* Effect.either(executeSelectedSemanticContext(runtime, plan, selection, cell, http, protocol.presentation, verification))
        if (Either.isLeft(execution) && !(execution.left instanceof FiniteExecutionViolation)) return yield* Effect.fail(execution.left)
        const rejected = Either.isLeft(execution)
        const descriptor = rejected ? execution.left.traceContent : execution.right.trace?.traceContent
        need(descriptor, "Missing retained trace")
        const trace = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(descriptor)))
        const expected = c.invalid ? "REFUSE" : String(c.action === "identity" ? c.bit : 1 - c.bit)
        const row = { call: calls, treatment, presentation: protocol.presentation, case: c, expected,
          correct: trace.prediction === expected, returned: !rejected,
          errorCode: rejected ? execution.left.code : null, trace: { ...trace, traceContent: descriptor }, assembly: prepared.assembly }
        records.push(row)
        yield* Effect.try(() => save(join(out, `record-${calls}.json`), row))
      }
    }
    const after = yield* runtime.snapshot
    need(hash(JSON.stringify(before)) === hash(JSON.stringify(after)), "Unexpected native state mutation")
    const groups = Object.fromEntries(protocol.treatments.map(p => { const rows = records.filter(r => r.treatment === p); return [p, {
      total: rows.length, correct: rows.filter(r => r.correct).length, returned: rows.filter(r => r.returned).length,
      rejected: rows.filter(r => !r.returned).length, unsafeReturned: rows.filter(r => r.returned && !r.correct).length,
      exceptionViolations: rows.filter(r => r.case.invalid && !r.correct).length,
      guardDisagreements: rows.filter(r => p === "guarded" && r.returned !== r.correct).length }] }))
    return { status: groups.guarded.correct === 16 && groups.guarded.returned === 16 && groups.guarded.guardDisagreements === 0 ? "P01_DEVELOPMENT_PASS" : "P01_FAILED",
      actualProviderCalls: calls, groups, stateRevision: after.canonical.revision, nativeStateUnchanged: true, learningUpdates: 0, topologyUpdates: 0, observedGeneralEfficacy: null }
  }).pipe(Effect.provide(layer))
  yield* Effect.try(() => save(join(out, "summary.json"), result))
  return result
})
try {
  const [mode, ...args] = process.argv.slice(2)
  if (mode === "--help") console.log("node _research/finite_guard_live_v1/run.mjs --prepare ORIGINAL_NATIVE CELL_JSON NEW_OUT\nnode _research/finite_guard_live_v1/run.mjs --run OUT CELL_JSON REGISTRATION_JSON\n32-call frozen paired table/binding/guard development census; raw accuracy and rejections counted separately; no W/topology update, retry or cohort resume.")
  else if (mode === "--prepare" && args.length === 3) console.log(JSON.stringify(await prepare(...args.map(x => resolve(x)))))
  else if (mode === "--run" && args.length === 3) console.log(JSON.stringify(await Effect.runPromise(run(...args.map(x => resolve(x))).pipe(Effect.provide(NodePosixServicesLive))), null, 2))
  else throw new Error("Unknown arguments; see --help")
} catch (error) { console.error(`FINITE_GUARD_LIVE_REFUSED: ${String(error)}`); process.exitCode = 2 }
