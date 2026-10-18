#!/usr/bin/env node
import { readFileSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import { Effect } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const analyze = root => Effect.try(() => {
  const read = name => JSON.parse(readFileSync(join(root, name), "utf8"))
  const need = (condition, detail) => { if (!condition) throw new Error(detail) }
  const sha = value => createHash("sha256").update(value).digest("hex")
  const protocol = read("protocol.json"), summary = read("summary.json")
  need(summary.protocolSha256 === sha(readFileSync(join(root, "protocol.json"))) && protocol.sourceSha256 === sha(readFileSync(join(root, "runner-source.mjs"))), "Frozen native protocol/source drift")
  need(summary.canonicalUnchanged && summary.providerCalls === 0 && summary.rows.length === 10, "Unexpected state change or execution count")
  const rows = summary.rows.filter(row => !row.warmup)
  need(rows.length === 8, "Expected eight measured rows after two warmups")
  for (const [i, row] of rows.entries()) {
    need(JSON.stringify(row.case) === JSON.stringify(protocol.cases[Math.floor(i / 2)]), "Frozen case changed")
    need(row.mode === protocol.modes[(Math.floor(i / 2) + i % 2) % 2] && row.position === i % 2, "Mode order changed")
    need(row.stages.map(s => s.name).join() === "prepare,select,local-assembly,present", "Missing stage")
    for (const [j, stage] of row.stages.entries()) for (const metric of ["elapsedMs", "snapshots", "contentReads", "contentBytes"]) {
      need(Number.isFinite(stage[metric]) && stage[metric] >= (j ? row.stages[j - 1][metric] : 0), "Invalid cumulative measurement")
    }
  }
  const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length
  const median = xs => { const ys = [...xs].sort((a, b) => a - b); return (ys[1] + ys[2]) / 2 }
  const groups = Object.fromEntries(protocol.modes.map(mode => {
    const selected = rows.filter(row => row.mode === mode)
    return [mode, { n: selected.length, medianMs: median(selected.map(row => row.stages.at(-1).elapsedMs)),
      ...Object.fromEntries(["snapshots", "contentReads", "contentBytes"].map(metric => [metric, mean(selected.map(row => row.stages.at(-1)[metric]))])),
      frames: mean(selected.map(row => row.frameCount)), roles: mean(selected.map(row => row.roleCount)) }]
  }))
  const paired = rows.filter(row => row.mode === "local").map(local => {
    const dense = rows.find(row => row.mode === "dense" && row.case.id === local.case.id)
    need(dense && dense.selected === local.selected, "Selected operator differs")
    return { id: local.case.id, deltaMs: local.stages.at(-1).elapsedMs - dense.stages.at(-1).elapsedMs }
  })
  return JSON.stringify({ status: "VERIFIED", groups,
    reductions: Object.fromEntries(["medianMs", "snapshots", "contentReads", "contentBytes", "frames", "roles"].map(metric => [metric, 1 - groups.local[metric] / groups.dense[metric]])),
    paired, providerCalls: 0, limitations: ["Four authored case pairs after two warmups", "Logical runtime API counts and returned bytes, not physical I/O or CPU/GPU operations", "Shared-host wall time; dense adds the inactive relation after the same learned local selection", "No model quality equivalence evaluation for execution-tail dense presentation"] }, null, 2) + "\n"
})
if (process.argv[2] === "--help") process.stdout.write("node _research/local_activation_diagnostics_v1/analyze-native-work.mjs NATIVE_WORK_DIRECTORY\nRead-only native counter and timing verification.\n")
else if (process.argv.length !== 3) process.exitCode = 2
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "NATIVE_WORK_ANALYSIS_REFUSED", program: () => analyze(resolve(process.argv[2])), describeFailure: error => String(error?.cause ?? error) }, [])
