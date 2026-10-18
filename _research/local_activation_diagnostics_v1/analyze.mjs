#!/usr/bin/env node
/** Read-only checks and descriptive paired timing summaries; no population inference from eight cases. */
import { readFileSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"
import { render, modes } from "./presentation.mjs"
import { render as renderTail } from "./tail-presentation.mjs"

const analyze = root => Effect.try(() => {
  const read = name => JSON.parse(readFileSync(join(root, name), "utf8"))
  const need = (yes, detail) => { if (!yes) throw new Error(detail) }
  const hash = bytes => createHash("sha256").update(bytes).digest("hex")
  const protocol = read("protocol.json"), summary = read("summary.json")
  const isTail = protocol.contract === "hswm-activation-tail-diagnostic/v1"
  const expectedModes = isTail ? ["execution-tail-local"] : modes
  const renderer = isTail ? renderTail : render
  need(JSON.stringify(protocol.modes) === JSON.stringify(expectedModes), "Unknown presentation set")
  need(summary.protocolSha256 === hash(readFileSync(join(root, "protocol.json"))), "Frozen protocol drift")
  need(protocol.sourceSha256 === hash(readFileSync(join(root, isTail ? "tail-probe-source.mjs" : "probe-source.mjs"))), "Frozen runner drift")
  need(protocol.presentationSha256 === hash(readFileSync(join(root, isTail ? "tail-presentation-source.mjs" : "presentation-source.mjs"))), "Frozen renderer drift")
  const expectedCalls = isTail ? 4 : 32
  need(summary.actualCalls === expectedCalls && summary.records.length === expectedCalls && summary.canonicalUnchanged, "Incomplete or mutating cohort")
  const rows = summary.records
  for (const [i, row] of rows.entries()) {
    const input = read(`${row.id}-request.json`), output = read(`${row.id}-response.json`)
    need(JSON.stringify(row) === JSON.stringify(output.record), "Record changed")
    const observed = JSON.parse(output.raw.choices[0].message.content)
    const expected = String(row.case.action === "identity" ? row.case.bit : 1 - row.case.bit)
    need(row.completed && row.prediction === observed.prediction && row.correct === (observed.prediction === expected), "Outcome mismatch")
    need(output.raw.model === protocol.model && output.raw.choices[0].finish_reason === "stop", "Wrong model/incomplete result")
    const width = expectedModes.length, caseIndex = Math.floor(i / width)
    need(row.position === i % width && row.mode === expectedModes[(caseIndex + i % width) % width], "Unbalanced order")
    need(JSON.stringify(row.case) === JSON.stringify(protocol.cases[caseIndex]) && JSON.stringify(input.case) === JSON.stringify(row.case), "Frozen case changed")
    need(input.request.messages[0].content === renderer(input.presentedPayload, [`rule:${row.case.action}`], ["rule:mandatory"], row.mode), "Presentation mismatch")
    for (const [key, value] of Object.entries(protocol.inference)) need(JSON.stringify(input.request[key]) === JSON.stringify(value), "Inference settings changed")
    need(JSON.stringify(input.presentedPayload.frames.slice(0, 2)) === JSON.stringify(input.canonicalAssembly.payload.frames), "Selected sources or roles changed")
    need(row.frameCount === input.presentedPayload.frames.length && row.roleCount === input.presentedPayload.frames.reduce((n, f) => n + f.roles.length, 0), "Graph counts differ")
    need(row.promptBytes === Buffer.byteLength(input.request.messages[0].content), "Prompt byte count differs")
    need(Number.isFinite(row.httpMs) && row.httpMs > 0 && row.preparationMs >= 0 && row.preparationPlusHttpMs === row.preparationMs + row.httpMs, "Invalid timing")
    need(row.usage.prompt_tokens === output.raw.usage.prompt_tokens && row.usage.completion_tokens === output.raw.usage.completion_tokens, "Usage mismatch")
  }
  const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length
  const median = xs => { const ys = [...xs].sort((a, b) => a - b); return (ys[(ys.length - 1) >> 1] + ys[ys.length >> 1]) / 2 }
  const group = mode => rows.filter(r => r.mode === mode)
  const aggregate = rs => ({ correct: rs.filter(r => r.correct).length, total: rs.length,
    identityCorrect: rs.filter(r => r.case.action === "identity" && r.correct).length, complementCorrect: rs.filter(r => r.case.action === "complement" && r.correct).length,
    meanPromptTokens: mean(rs.map(r => r.usage.prompt_tokens)), meanOutputTokens: mean(rs.map(r => r.usage.completion_tokens)), meanTotalTokens: mean(rs.map(r => r.usage.total_tokens)),
    medianHttpMs: median(rs.map(r => r.httpMs)), meanHttpMs: mean(rs.map(r => r.httpMs)), medianPreparationMs: median(rs.map(r => r.preparationMs)), medianPreparationPlusHttpMs: median(rs.map(r => r.preparationPlusHttpMs)),
    frames: rs[0].frameCount, roles: rs[0].roleCount })
  const compare = (baseline, candidate) => {
    const a = group(baseline), b = group(candidate)
    const paired = a.map(x => { const y = b.find(r => r.case.id === x.case.id); need(y, "Missing pair"); return { id: x.case.id, httpMsDelta: y.httpMs - x.httpMs, promptTokenDelta: y.usage.prompt_tokens - x.usage.prompt_tokens } })
    const aa = aggregate(a), bb = aggregate(b)
    return { baseline, candidate, promptTokenReductionFraction: 1 - bb.meanPromptTokens / aa.meanPromptTokens,
      totalTokenReductionFraction: 1 - bb.meanTotalTokens / aa.meanTotalTokens,
      medianHttpReductionFraction: 1 - bb.medianHttpMs / aa.medianHttpMs,
      medianPreparationPlusHttpReductionFraction: 1 - bb.medianPreparationPlusHttpMs / aa.medianPreparationPlusHttpMs,
      meanPairedHttpDeltaMs: mean(paired.map(x => x.httpMsDelta)), pairedHttpDeltaRangeMs: [Math.min(...paired.map(x => x.httpMsDelta)), Math.max(...paired.map(x => x.httpMsDelta))], paired }
  }
  return JSON.stringify({ status: "VERIFIED", groups: Object.fromEntries(expectedModes.map(m => [m, aggregate(group(m))])), comparisons: isTail ? [] : [compare("raw-local", "instructed-local"), compare("raw-local", "readable-local"), compare("readable-dense", "readable-local")],
    totalCalls: rows.length, totalProviderTokens: rows.reduce((n, r) => n + r.usage.total_tokens, 0),
    serverMetricsAvailable: rows.filter(r => r.serverMetrics !== null).length, gpuFlops: null, gpuEnergy: null,
    limitations: [isTail ? "Four exploratory follow-up cases; no contemporaneous comparator" : "Eight fixed authored cases per mode, four unique action/bit combinations repeated twice", "Shared server, cache and queue uncontrolled", "Client HTTP wall time includes queue, network, prefill and decoding", "Token and graph-operation counts are not measured GPU FLOPs", "Operator adherence is not learned routing accuracy"] }, null, 2) + "\n"
})
if (process.argv[2] === "--help") process.stdout.write("node _research/local_activation_diagnostics_v1/analyze.mjs PROBE_DIRECTORY\nRecompute outcomes and paired descriptive token/timing comparisons from original responses.\n")
else if (process.argv.length !== 3) process.exitCode = 2
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "ACTIVATION_ANALYSIS_REFUSED", program: () => analyze(resolve(process.argv[2])), describeFailure: String }, [])
