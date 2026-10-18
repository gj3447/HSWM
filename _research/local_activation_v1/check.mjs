#!/usr/bin/env node
/** Read-only recomputation from original provider bytes; no inference, no native writes. */
import { readFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { createHash } from "node:crypto"
import { Effect } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { Parser } from "../../src/hswm/effect-runtime/node_modules/n3/lib/index.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const check = root => Effect.try(() => {
  const read = name => JSON.parse(readFileSync(join(root, name), "utf8"))
  const need = (ok, message) => { if (!ok) throw new Error(message) }
  const hash = bytes => createHash("sha256").update(bytes).digest("hex")
  const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b)
  const lock = JSON.parse(readFileSync(new URL("./evidence-lock.json", import.meta.url), "utf8"))
  for (const [name, digest] of Object.entries(lock.artifacts)) {
    need(hash(readFileSync(join(root, "..", name))) === digest, `Original evidence bytes drifted: ${name}`)
  }
  for (const [name, digest] of Object.entries(lock.sourceFiles)) {
    need(hash(readFileSync(new URL(`../../${name}`, import.meta.url))) === digest, `SOURCE_DRIFT: ${name}; do not refresh historical hashes`)
  }
  const protocol = read("protocol.json"), summary = read("summary.json")
  need(protocol.contract === "hswm-local-activation-study/v3", "Expected the completed frozen v3 cohort")
  need(hash(readFileSync(join(root, "protocol.json"))) === summary.protocolSha256, "Protocol bytes drifted")
  need(hash(readFileSync(join(root, "runner-source.mjs"))) === protocol.frozenSourceSha256, "Frozen runner drifted")
  const stats = new Map(["identity", "complement"].map(id => [id, { candidateId: id, observations: 0, a: [[1, 0], [0, 1]], b: [0, 0] }]))
  const totals = {}, records = []
  let wire = 0, learned = 0, tokens = 0
  for (const phase of ["baseline", "train", "final", "restart"]) {
    const cases = phase === "train" ? protocol.cases.train : phase === "restart" ? protocol.cases.restart : protocol.cases.holdout
    totals[phase] = { correct: 0, total: cases.length }
    for (const c of cases) {
      const name = `${phase}-${c.id}.json`, { record, result } = read(name)
      const prefix = phase === "restart" ? `${c.id}-wire` : `wire-${++wire}`
      const response = read(`${prefix}-response.json`), request = read(`${prefix}-request.json`)
      need(response.model === protocol.model && response.choices[0].finish_reason === "stop", `${name}: incomplete/wrong provider response`)
      const actual = JSON.parse(response.choices[0].message.content)
      need(actual.prediction === record.prediction && actual.prediction === result.trace.prediction, `${name}: model output substituted`)
      const oracle = String(c.signal > 0 ? c.bit : 1 - c.bit)
      need(record.expected === oracle && record.correct === (actual.prediction === oracle), `${name}: incorrect evaluator`)
      need(request.seed === 17 && request.max_tokens === 256 && request.chat_template_kwargs.enable_thinking === false && request.structured_outputs.json.properties.prediction.type === "string", `${name}: inference contract changed`)
      const payload = JSON.parse(request.messages[0].content)
      need(equal(payload, result.assembly.payload), `${name}: selected prompt differs from provider input`)
      need(equal(payload.frames.map(f => f.relation.key.atomUid), ["rule:mandatory", `rule:${record.candidateId}`]), `${name}: activation closure differs`)
      need(payload.frames.every(f => equal(f.roles.map(r => r.role), ["subject", "context", "evidence", "exception"])), `${name}: role loss`)
      need(result.selection.policyKey.revisionId === record.revision, `${name}: policy revision differs`)
      totals[phase].correct += Number(record.correct)
      tokens += response.usage.total_tokens
      records.push(record)
      if (phase === "train") {
        const arm = stats.get(record.candidateId), x = [1, c.signal], reward = Number(actual.prediction === oracle)
        need(arm !== undefined, "Unknown selected arm")
        arm.observations++
        arm.a = arm.a.map((row, i) => row.map((v, j) => v + x[i] * x[j]))
        arm.b = arm.b.map((v, i) => v + reward * x[i])
        const proposal = read(`learn-${++learned}.json`)
        need(equal(proposal.policy.arms, [...stats.values()]) && proposal.policyKey.revisionId === learned, "Stored update differs from actual rewarded execution")
      }
    }
    need(equal(totals[phase], summary[phase]), `${phase}: summary mismatch`)
  }
  need(equal(summary.finalPolicy.arms, [...stats.values()]) && learned === 8, "Final numeric learning state mismatch")
  need(summary.actualModelCalls === wire + 2 && wire + 2 === 26, "Call census mismatch")
  const quads = new Parser({ format: "N-Quads" }).parse(readFileSync(join(root, "native.nq"), "utf8"))
  const complement = records.filter(r => r.candidateId === "complement")
  return JSON.stringify({ status: "VERIFIED", actualModelCalls: 26, totalProviderTokens: tokens, totals,
    improvementPercentagePoints: 100 * (totals.final.correct / totals.final.total - totals.baseline.correct / totals.baseline.total),
    complementExecutions: complement.length, complementRuleFollowed: complement.filter(r => r.prediction === String(1 - r.case.bit)).length,
    learnedRevisions: learned, rdfQuads: quads.length, rdfNamedGraphs: new Set(quads.map(q => q.graph.value)).size,
    scope: "Original provider output, independent A/b arithmetic, exact selected prompt and role closure; no independent truth authentication or full SHACL rerun" }, null, 2) + "\n"
})
if (process.argv[2] === "--help") process.stdout.write("node _research/local_activation_v1/check.mjs COMPLETED_V3_DIRECTORY\nRead-only original-output, reward, numeric-state, prompt and RDF parse verification.\n")
else if (process.argv.length !== 3) process.exitCode = 2
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "ACTIVATION_CHECK_REFUSED", program: () => check(resolve(process.argv[2])), describeFailure: String }, [])
