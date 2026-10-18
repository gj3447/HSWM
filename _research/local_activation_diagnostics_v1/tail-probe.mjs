#!/usr/bin/env node
/** Four-call follow-up: repeat unescaped original executable rule text at the end; no expected answer in prompt. */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { prepareSemanticContext, assembleSelectedSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { readLlmSemanticFrame } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-runtime.js"
import { NativeAdaptiveHttpClient } from "../../src/hswm/effect-runtime/dist/adaptive-executor.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
import { modes, render } from "./tail-presentation.mjs"

const json = x => JSON.stringify(x, null, 2) + "\n"
const sha = bytes => createHash("sha256").update(bytes).digest("hex")
const unwrap = x => { if (Either.isLeft(x)) throw x.left; return x.right }
const inference = { max_tokens: 128, temperature: 0.7, top_p: 0.8, top_k: 20, min_p: 0, seed: 17,
  chat_template_kwargs: { enable_thinking: false }, structured_outputs: { json: { type: "object", additionalProperties: false,
    required: ["prediction", "uncertainty"], properties: { prediction: { type: "string" }, uncertainty: { type: "string" } } } } }
const specFor = c => ({ contract: "hswm-semantic-context-spec/v1", event: JSON.stringify({ id: c.id, signal: c.signal, bit: c.bit }), mandatoryRelationUids: ["rule:mandatory"],
  candidates: [{ id: "identity", summary: "Apply the identity Boolean rule", relationUids: ["rule:identity"] }, { id: "complement", summary: "Apply the complement Boolean rule", relationUids: ["rule:complement"] }],
  maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 })
const run = (oldRoot, output, cellFile, registrationFile) => Effect.gen(function* () {
  const read = path => Effect.try(() => JSON.parse(readFileSync(path, "utf8")))
  const cell = yield* read(cellFile), registration = yield* read(registrationFile)
  if (Date.parse(registration.expiresAt) <= Date.now() || registration.reachability?.status !== 200 || Date.now() - Date.parse(registration.reachability.observedAt) > 1800000 || registration.maximumProviderCalls !== 64 || !registration.transport.includes(cell.base_url)) return yield* Effect.fail("NOT_READY")
  if (existsSync(output)) return yield* Effect.fail("New output directory required")
  yield* Effect.try(() => mkdirSync(output, { recursive: true, mode: 0o700 }))
  const save = (name, value) => Effect.try(() => writeFileSync(join(output, name), json(value), { flag: "wx", mode: 0o600 }))
  const schema = yield* read(join(oldRoot, "schema.json"))
  const cases = Array.from({ length: 4 }, (_, i) => ({ id: `tail-probe-20261018-${i}`, signal: i % 2 ? -0.58 : 0.58,
    bit: Math.floor(i / 2) % 2, action: i % 2 ? "complement" : "identity" }))
  const protocol = { contract: "hswm-activation-tail-diagnostic/v1", frozenAt: new Date().toISOString(), cases, modes, inference, maximumCalls: 4,
    model: cell.model, order: "One fixed follow-up presentation; four action/bit combinations; exploratory diagnosis after the failed four-mode cohort", concurrency: 1,
    estimands: ["Active operator adherence", "Provider prompt/completion tokens", "Client-observed HTTP wall time", "Graph preparation + HTTP wall time"],
    gpuFlops: "UNMEASURED", queueAndServiceTime: "Only if response.metrics is provided; no server reconfiguration", prefixCaching: "Server default, uncontrolled; repeated prompts may be cached", candidateSelection: "Authored intervention to test operator execution, NOT learned policy accuracy",
    sourceSha256: sha(readFileSync(new URL(import.meta.url))), presentationSha256: sha(readFileSync(new URL("./tail-presentation.mjs", import.meta.url))) }
  yield* save("protocol.json", protocol)
  yield* Effect.try(() => writeFileSync(join(output, "tail-probe-source.mjs"), readFileSync(new URL(import.meta.url)), { flag: "wx" }))
  yield* Effect.try(() => writeFileSync(join(output, "tail-presentation-source.mjs"), readFileSync(new URL("./tail-presentation.mjs", import.meta.url)), { flag: "wx" }))
  const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const initial = yield* runtime.snapshot
    const records = []
    let count = 0
    for (const [index, c] of cases.entries()) for (let position = 0; position < modes.length; position++) {
      const mode = modes[(index + position) % modes.length]
      const start = yield* Effect.sync(() => performance.now())
      const plan = yield* prepareSemanticContext(runtime, specFor(c))
      const selection = { planSha256: plan.planSha256, status: "SELECTED", candidateId: c.action, source: "CONTROLLED_OPERATOR_PROBE" }
      const assembled = yield* assembleSelectedSemanticContext(runtime, plan, selection)
      if (!assembled.assembly) return yield* Effect.fail("Expected assembly")
      const original = assembled.assembly.payload
      const frames = mode === "readable-dense" ? [...original.frames, yield* readLlmSemanticFrame(runtime, `rule:${c.action === "identity" ? "complement" : "identity"}`, plan.spec.event)] : original.frames
      const payload = { ...original, frames }
      const prompt = render(payload, [`rule:${c.action}`], plan.spec.mandatoryRelationUids, mode)
      const preparationMs = (yield* Effect.sync(() => performance.now())) - start
      const request = { model: cell.model, ...inference, messages: [{ role: "user", content: prompt }] }
      const id = `call-${String(++count).padStart(3, "0")}`
      yield* save(`${id}-request.json`, { case: c, mode, position, request, canonicalAssembly: assembled.assembly, presentedPayload: payload })
      const httpStart = yield* Effect.sync(() => performance.now())
      const observed = yield* Effect.either(NativeAdaptiveHttpClient.postJson({ url: `${cell.base_url}/chat/completions`, headers: { "content-type": "application/json" }, body: new TextEncoder().encode(JSON.stringify(request)), timeoutMs: 30000, maximumResponseBytes: 1048576 }))
      const httpMs = (yield* Effect.sync(() => performance.now())) - httpStart
      const raw = Either.isRight(observed) ? JSON.parse(new TextDecoder().decode(observed.right)) : null
      const parsed = yield* Effect.either(Effect.try(() => JSON.parse(raw?.choices?.[0]?.message?.content)))
      const prediction = Either.isRight(parsed) && typeof parsed.right.prediction === "string" ? parsed.right.prediction : null
      const completed = raw?.choices?.[0]?.finish_reason === "stop" && prediction !== null
      const expected = String(c.action === "identity" ? c.bit : 1 - c.bit)
      const record = { id, mode, case: c, position, completed, prediction, expected, correct: completed && prediction === expected,
        promptBytes: Buffer.byteLength(prompt), frameCount: frames.length, roleCount: frames.reduce((n, f) => n + f.roles.length, 0),
        preparationMs, httpMs, preparationPlusHttpMs: preparationMs + httpMs, usage: raw?.usage ?? null, serverMetrics: raw?.metrics ?? null,
        error: Either.isLeft(observed) ? String(observed.left) : null }
      yield* save(`${id}-response.json`, { record, raw })
      records.push(record)
      yield* Effect.sync(() => process.stderr.write(`${id} ${mode} ${c.action} ${c.bit} -> ${prediction} ${record.correct ? "ok" : "wrong"} ${Math.round(httpMs)}ms\n`))
      if (!completed) return yield* Effect.fail("Incomplete response retained; cohort stopped without retry")
    }
    const final = yield* runtime.snapshot
    const summary = { contract: "hswm-activation-diagnostic-result/v1", actualCalls: count, canonicalUnchanged: JSON.stringify(initial.canonical) === JSON.stringify(final.canonical), records,
      protocolSha256: sha(readFileSync(join(output, "protocol.json"))) }
    yield* save("summary.json", summary)
    return json({ actualCalls: count, canonicalUnchanged: summary.canonicalUnchanged })
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(join(oldRoot, "native"), "activation-study-journal", schemaBytes)))
})
if (process.argv[2] === "--help") process.stdout.write("node _research/local_activation_diagnostics_v1/tail-probe.mjs PRIOR_V3_ROOT NEW_OUTPUT CELL REGISTRATION\n4 calls; fixed operator interventions; original state remains unchanged.\n")
else if (process.argv.length !== 6) process.exitCode = 2
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "ACTIVATION_DIAGNOSTIC_REFUSED", program: () => run(...process.argv.slice(2).map(p => resolve(p))), describeFailure: String }, [])
