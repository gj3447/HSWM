#!/usr/bin/env node
/** Logical native read instrumentation, not physical disk I/O, CPU cycles, or model FLOPs. No provider calls. */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { prepareSemanticContext, assembleSelectedSemanticContext } from "../../src/hswm/effect-runtime/dist/semantic-context-runtime.js"
import { selectContextActivation } from "../../src/hswm/effect-runtime/dist/semantic-context-activation-runtime.js"
import { contextHash } from "../../src/hswm/effect-runtime/dist/semantic-context-domain.js"
import { readLlmSemanticFrame } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-runtime.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
import { render } from "./tail-presentation.mjs"

const json = x => JSON.stringify(x, null, 2) + "\n"
const sha = x => createHash("sha256").update(x).digest("hex")
const run = (learning, output) => Effect.gen(function* () {
  const schema = yield* Effect.try(() => JSON.parse(readFileSync(join(learning, "schema.json"), "utf8")))
  const study = yield* Effect.try(() => JSON.parse(readFileSync(join(learning, "protocol.json"), "utf8")))
  const schemaBytes = canonicalAtomV2SchemaContentBytes(schema)
  if (Either.isLeft(schemaBytes)) return yield* Effect.fail(schemaBytes.left)
  if (existsSync(output)) return yield* Effect.fail("New output directory required")
  yield* Effect.try(() => mkdirSync(output, { recursive: true, mode: 0o700 }))
  const save = (name, value) => Effect.try(() => writeFileSync(join(output, name), json(value), { flag: "wx", mode: 0o600 }))
  const cases = study.cases.holdout.slice(0, 4)
  const protocol = { contract: "hswm-native-work-diagnostic/v1", frozenAt: new Date().toISOString(), cases,
    modes: ["local", "dense"], warmups: 2, measuredExecutions: 8, providerCalls: 0,
    order: "Two modes alternate first position across four cases", sourceSha256: sha(readFileSync(new URL(import.meta.url))),
    measurement: "Logical public runtime.snapshot/readContent invocations and returned bytes, plus monotonic wall time; not filesystem I/O, CPU cycles, or GPU FLOPs" }
  yield* save("protocol.json", protocol)
  yield* Effect.try(() => writeFileSync(join(output, "runner-source.mjs"), readFileSync(new URL(import.meta.url)), { flag: "wx" }))
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const before = yield* runtime.snapshot
    const rows = []
    for (let index = -1; index < cases.length; index++) for (let position = 0; position < 2; position++) {
      const c = cases[Math.max(0, index)], mode = protocol.modes[(Math.max(0, index) + position) % 2]
      const counts = { snapshots: 0, contentReads: 0, contentBytes: 0 }
      const measured = { ...runtime,
        snapshot: Effect.gen(function* () { counts.snapshots++; return yield* runtime.snapshot }),
        readContent: descriptor => Effect.gen(function* () {
          const bytes = yield* runtime.readContent(descriptor)
          counts.contentReads++; counts.contentBytes += bytes.length
          return bytes
        }) }
      const stages = [], start = yield* Effect.sync(() => performance.now())
      const mark = name => Effect.sync(() => stages.push({ name, elapsedMs: performance.now() - start, ...counts }))
      const plan = yield* prepareSemanticContext(measured, { contract: "hswm-semantic-context-spec/v1", event: JSON.stringify(c), mandatoryRelationUids: ["rule:mandatory"],
        candidates: [{ id: "identity", summary: "Apply the identity Boolean rule", relationUids: ["rule:identity"] }, { id: "complement", summary: "Apply the complement Boolean rule", relationUids: ["rule:complement"] }],
        maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0 })
      yield* mark("prepare")
      const selection = yield* selectContextActivation(measured, plan, { policyKey: { schemaVersion: schema.schemaVersion, lineageId: "activation-study", atomUid: "policy:activation-execution-tail", revisionId: 8 },
        features: { encoderRevision: study.config.encoderRevision, eventSha256: contextHash(plan.spec.event), values: [1, c.signal] }, mode: "EXPLOIT" })
      yield* mark("select")
      const assembled = yield* assembleSelectedSemanticContext(measured, plan, selection)
      if (!assembled.assembly) return yield* Effect.fail("Missing local assembly")
      yield* mark("local-assembly")
      const payload = assembled.assembly.payload
      const presented = mode === "local" ? payload : { ...payload, frames: [...payload.frames,
        yield* readLlmSemanticFrame(measured, `rule:${selection.candidateId === "identity" ? "complement" : "identity"}`, plan.spec.event)] }
      const prompt = render(presented, [`rule:${selection.candidateId}`], ["rule:mandatory"], "execution-tail-local")
      yield* mark("present")
      rows.push({ warmup: index < 0, case: c, mode, position, selected: selection.candidateId, frameCount: presented.frames.length,
        roleCount: presented.frames.reduce((n, f) => n + f.roles.length, 0), promptBytes: Buffer.byteLength(prompt), stages })
    }
    const after = yield* runtime.snapshot
    const summary = { protocolSha256: sha(readFileSync(join(output, "protocol.json"))), providerCalls: 0,
      canonicalUnchanged: JSON.stringify(before.canonical) === JSON.stringify(after.canonical), rows }
    yield* save("summary.json", summary)
    return json(summary)
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(join(learning, "native"), "activation-study-journal", schemaBytes.right)))
})
if (process.argv[2] === "--help") process.stdout.write("node _research/local_activation_diagnostics_v1/native-work.mjs LEARNING_ROOT NEW_OUTPUT\nZero model calls; 2 warmups + 8 measured native assemblies.\n")
else if (process.argv.length !== 4) process.exitCode = 2
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "NATIVE_WORK_REFUSED", program: () => run(...process.argv.slice(2).map(p => resolve(p))), describeFailure: error => String(error?.cause ?? error) }, [])
