#!/usr/bin/env node
/** Regression replay of preserved responses through the production guard. Zero provider calls. */
import { readFileSync, readdirSync, mkdirSync, copyFileSync, linkSync, lstatSync, chmodSync, mkdtempSync, rmSync } from "node:fs"
import { resolve, join } from "node:path"
import { tmpdir } from "node:os"
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/dist/effect-posix-services.js"
import { prepareSemanticContext, executeSelectedSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { FiniteExecutionViolation } from "../../src/hswm/effect-runtime/dist/semantic-context-finite-execution-domain.js"

const read = p => JSON.parse(readFileSync(p, "utf8"))
const sha = b => createHash("sha256").update(b).digest("hex")
const need = (ok, message) => { if (!ok) throw new Error(message) }
const clone = (source, destination, inodes = new Map()) => {
  mkdirSync(destination, { mode: 0o700 })
  for (const e of readdirSync(source, { withFileTypes: true })) {
    need(e.isFile() || e.isDirectory(), "Only regular source files/directories")
    const from = join(source, e.name), to = join(destination, e.name)
    if (e.isDirectory()) clone(from, to, inodes)
    else {
      const stat = lstatSync(from), key = `${stat.dev}:${stat.ino}`, first = inodes.get(key)
      if (first) linkSync(first, to)
      else { copyFileSync(from, to); chmodSync(to, stat.mode & 0o777); inodes.set(key, to) }
    }
  }
}
const replay = (source, native) => Effect.gen(function* () {
  const genesis = readdirSync(join(native, "journal-objects")).map(n => read(join(native, "journal-objects", n))).find(j => j.stateRevision === 0)
  need(genesis, "Missing native genesis")
  const schema = readFileSync(join(native, "objects", genesis.schema.content.sha256))
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const before = yield* runtime.snapshot
    const groups = {}, rejected = []
    let calls = 0
    for (let id = 1; id <= 32; id++) {
      const old = read(join(source, `record-${id}.json`)), c = old.case
      const raw = readFileSync(join(source, `call-${id}-response.json`))
      const prediction = JSON.parse(JSON.parse(raw).choices[0].message.content).prediction
      const plan = yield* prepareSemanticContext(runtime, { contract: "hswm-semantic-context-spec/v1", event: JSON.stringify(c),
        mandatoryRelationUids: ["rule:mandatory"], candidates: [
          { id: "identity", summary: "identity finite operator", relationUids: ["rule:identity", "rule:duplicate"] },
          { id: "complement", summary: "complement finite operator", relationUids: ["rule:complement"] }
        ], maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 })
      const verification = { contract: "hswm-finite-execution-guard/v1", rules: old.assembly.payload.frames.map(f => ({
        relationKey: f.relation.key, inputs: [{ variable: "bit", eventField: "bit" }, { variable: "invalid", eventField: "invalid" }], outputVariable: "prediction"
      })) }
      const result = yield* Effect.either(executeSelectedSemanticContext(runtime, plan, { planSha256: plan.planSha256, status: "SELECTED", candidateId: c.action },
        { base_url: "https://replay.invalid/v1", model: "PRESERVED_RESPONSE_REPLAY_NOT_NEW_INFERENCE", max_tokens: 512 },
        { postJson: () => Effect.sync(() => { calls++; return Uint8Array.from(raw) }) }, old.presentation, verification))
      if (Either.isLeft(result)) need(result.left instanceof FiniteExecutionViolation, String(result.left))
      const descriptor = Either.isLeft(result) ? result.left.traceContent : result.right.trace?.traceContent
      need(descriptor, "Missing retained trace")
      const trace = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(descriptor)))
      need(trace.prediction === prediction && trace.verification.prediction === prediction, "Prediction was changed")
      const expected = c.invalid ? "REFUSE" : String(c.action === "identity" ? c.bit : 1 - c.bit)
      need(Either.isRight(result) === (prediction === expected), "Guard disagrees with independent authored oracle")
      need(sha(yield* runtime.readContent(trace.transport.response)) === sha(raw), "Raw response changed")
      const g = groups[old.presentation] ??= { total: 0, accepted: 0, rejected: 0 }
      g.total++
      if (Either.isLeft(result)) {
        g.rejected++
        rejected.push({ originalCall: id, case: c.id, prediction, expected, violatedRules: trace.verification.checks.filter(x => !x.accepted).map(x => x.relationKey.atomUid) })
      } else g.accepted++
    }
    need(calls === 32 && JSON.stringify(yield* runtime.snapshot) === JSON.stringify(before), "Replay count or canonical state changed")
    return { status: "REGRESSION_REPLAY_PASS", actualProviderCalls: 0, replayedResponses: calls, groups, rejected,
      nativeStateUnchanged: true, claim: "Old responses through new guard; no new model accuracy estimate, corrected answers, automatic retry or W/topology admission" }
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(native, "finite-study", schema, [])))
})
let temporary
try {
  if (process.argv[2] === "--help") console.log("node _research/finite_execution_guard_v1/replay.mjs PRIVATE_ORIGINAL_ROOT BASELINE_CODE_ARCHIVE PRIOR_RECEIPT\nVerify prior bytes with the archived checker, then replay all 32 responses through the current production guard in isolated TMPDIR. Never connects to a provider.")
  else {
    need(process.argv.length === 5, "Expected three arguments; see --help")
    const [root, archive, receipt] = process.argv.slice(2).map(p => resolve(p))
    const audited = JSON.parse(execFileSync(process.execPath, [join(archive, "_research/finite_presentation_v1/check.mjs"), root, receipt], { encoding: "utf8", timeout: 30000, maxBuffer: 1048576 }))
    need(audited.status === "EVIDENCE_VERIFIED" && audited.actualProviderCalls === 32, "Original evidence not verified")
    temporary = mkdtempSync(join(tmpdir(), "finite-execution-replay-"))
    const source = join(root, "experiment-v3"), native = join(temporary, "native")
    clone(join(source, "native"), native)
    console.log(JSON.stringify(await Effect.runPromise(replay(source, native).pipe(Effect.provide(NodePosixServicesLive))), null, 2))
  }
} catch (error) { console.error(`FINITE_EXECUTION_REPLAY_REFUSED: ${String(error)}`); process.exitCode = 1 }
finally { if (temporary) rmSync(temporary, { recursive: true, force: true }) }
