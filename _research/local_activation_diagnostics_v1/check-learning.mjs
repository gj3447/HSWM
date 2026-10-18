#!/usr/bin/env node
/** Read-only recomputation from original provider bytes; no inference, no native writes. */
import { readFileSync, readdirSync } from "node:fs"
import { join, resolve } from "node:path"
import { createHash } from "node:crypto"
import { Effect } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { Parser } from "../../src/hswm/effect-runtime/node_modules/n3/lib/index.js"
import { render } from "./tail-presentation.mjs"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const check = (root, evidenceOnly = false) => Effect.try(() => {
  const read = name => JSON.parse(readFileSync(join(root, name), "utf8"))
  const need = (ok, message) => { if (!ok) throw new Error(message) }
  const hash = bytes => createHash("sha256").update(bytes).digest("hex")
  const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b)
  const nativeJson = descriptor => {
    const bytes = readFileSync(join(root, "native", "objects", descriptor.sha256))
    need(hash(bytes) === descriptor.sha256 && bytes.length === descriptor.byteLength, "Native content binding differs")
    return JSON.parse(bytes.toString("utf8"))
  }
  const commits = readdirSync(join(root, "native", "journal-objects")).map(file => JSON.parse(readFileSync(join(root, "native", "journal-objects", file), "utf8")))
    .filter(row => row._tag === "CanonicalAtomV2StateJournalCommit").sort((a, b) => a.stateRevision - b.stateRevision)
  need(commits.length === 10 && commits[0].stateRevision === 1 && commits[9].stateRevision === 10, "Unexpected native history")
  need(commits[0].writeBindings.length === 15 && commits.slice(1).every(row => row.writeBindings.length === 1 && row.writeBindings[0].key.atomUid === "policy:activation-execution-tail"), "Source rules or roles rewritten")
  const lock = JSON.parse(readFileSync(new URL("./evidence-lock.json", import.meta.url), "utf8"))
  for (const [name, digest] of Object.entries(lock.artifacts)) {
    need(hash(readFileSync(join(root, "..", name))) === digest, `Original evidence bytes drifted: ${name}`)
  }
  const sourceDrift = Object.entries(lock.sourceFiles).flatMap(([name, expectedSha256]) => {
    const actualSha256 = hash(readFileSync(new URL(`../../${name}`, import.meta.url)))
    return actualSha256 === expectedSha256 ? [] : [{ name, expectedSha256, actualSha256 }]
  })
  need(evidenceOnly || sourceDrift.length === 0, `SOURCE_DRIFT: ${sourceDrift.map(x => x.name).join(", ")}; original hashes preserved. Use --evidence-only to verify recorded observations without claiming live-build equality`)
  const protocol = read("protocol.json"), summary = read("summary.json")
  need(protocol.contract === "hswm-local-activation-execution-tail-study/v1", "Expected the completed frozen execution-tail cohort")
  need(hash(readFileSync(join(root, "protocol.json"))) === summary.protocolSha256, "Protocol bytes drifted")
  need(hash(readFileSync(join(root, "runner-source.mjs"))) === protocol.frozenSourceSha256, "Frozen runner drifted")
  need(hash(readFileSync(join(root, "tail-presentation.mjs"))) === protocol.presentationSha256, "Tail presentation drifted")
  need(hash(readFileSync(join(root, "presentation.mjs"))) === protocol.basePresentationSha256, "Base presentation drifted")
  const stats = new Map(["identity", "complement"].map(id => [id, { candidateId: id, observations: 0, a: [[1, 0], [0, 1]], b: [0, 0] }]))
  const totals = {}, records = []
  let wire = 0, learned = 0, tokens = 0, floatingTieSelections = 0
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
      const nativeTrace = nativeJson(record.traceContent)
      need(equal(nativeJson(nativeTrace.responseContent), actual), `${name}: native response differs from actual provider output`)
      need(equal(nativeJson(nativeTrace.requestContent).assembly, result.assembly), `${name}: native request differs from assembly`)
      const oracle = String(c.signal > 0 ? c.bit : 1 - c.bit)
      need(record.expected === oracle && record.correct === (actual.prediction === oracle), `${name}: incorrect evaluator`)
      need(request.seed === 17 && request.max_tokens === 128 && request.chat_template_kwargs.enable_thinking === false && request.structured_outputs.json.properties.prediction.type === "string", `${name}: inference contract changed`)
      const canonicalRequest = read(`${prefix}-canonical-request.json`)
      const payload = JSON.parse(canonicalRequest.messages[0].content)
      need(request.messages[0].content === render(payload, [`rule:${record.candidateId}`], ["rule:mandatory"], "execution-tail-local"), `${name}: actual wire differs from frozen presentation`)
      need(request.temperature === 0.7 && request.top_p === 0.8 && request.top_k === 20 && request.min_p === 0, `${name}: sampler drift`)
      need(equal(payload, result.assembly.payload), `${name}: selected prompt differs from provider input`)
      need(equal(payload.frames.map(f => f.relation.key.atomUid), ["rule:mandatory", `rule:${record.candidateId}`]), `${name}: activation closure differs`)
      need(payload.frames.every(f => equal(f.roles.map(r => r.role), ["subject", "context", "evidence", "exception"])), `${name}: role loss`)
      need(result.selection.policyKey.revisionId === record.revision, `${name}: policy revision differs`)
      need(equal(record.case, c) && payload.event === JSON.stringify(c), `${name}: evaluation case drift`)
      need(equal(result.selection.features.values, [1, c.signal]) && result.selection.mode === (phase === "train" ? "EXPLORE" : "EXPLOIT"), `${name}: activation input differs`)
      // Independent two-dimensional inverse; production uses Cholesky, never this implementation.
      const scores = [...stats.values()].map(arm => {
        const [[a, b], [cc, d]] = arm.a, det = a * d - b * cc
        const inv = [[d / det, -b / det], [-cc / det, a / det]]
        const theta = inv.map(row => row.reduce((s, v, i) => s + v * arm.b[i], 0))
        const x = [1, c.signal], mean = theta[0] + theta[1] * c.signal
        const radius = Math.sqrt(x.reduce((s, v, i) => s + v * inv[i].reduce((ss, vv, j) => ss + vv * x[j], 0), 0))
        return { candidateId: arm.candidateId, score: mean + (phase === "train" ? protocol.config.alpha * radius : 0) }
      })
      const selected = scores.reduce((best, row) => row.score > best.score ? row : best)
      const executedScore = scores.find(row => row.candidateId === record.candidateId)
      need(executedScore && selected.score - executedScore.score < 1e-10, `${name}: selected arm is not a numerical LinUCB maximizer`)
      if (selected.candidateId !== record.candidateId) floatingTieSelections++
      need(result.selection.scores.every((row, i) => Math.abs(row.score - scores[i].score) < 1e-10), `${name}: numeric score differs`)
      need(record.revision === (phase === "baseline" ? 0 : phase === "train" ? learned : 8), `${name}: policy revision is stale`)
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
        const commit = commits.find(row => row.receipt.transitionId === proposal.candidate.command.transitionId)
        need(commit?.receipt.decision === "ACCEPTED" && commit.stateRevision === learned + 2, "Learning proposal was not admitted")
        need(equal(nativeJson(commit.writeBindings[0].payload), proposal.policy), "Admitted numeric policy differs from proposal")
      }
    }
    need(equal(totals[phase], summary[phase]), `${phase}: summary mismatch`)
  }
  need(equal(summary.finalPolicy.arms, [...stats.values()]) && learned === 8, "Final numeric learning state mismatch")
  need(summary.actualModelCalls === wire + 2 && wire + 2 === 26, "Call census mismatch")
  const quads = new Parser({ format: "N-Quads" }).parse(readFileSync(join(root, "native.nq"), "utf8"))
  const complement = records.filter(r => r.candidateId === "complement")
  return JSON.stringify({ status: sourceDrift.length ? "ORIGINAL_EVIDENCE_VERIFIED_LIVE_BUILD_DRIFT" : "VERIFIED", sourceDrift, liveBuildMatches: sourceDrift.length === 0, actualModelCalls: 26, totalProviderTokens: tokens, totals,
    improvementPercentagePoints: 100 * (totals.final.correct / totals.final.total - totals.baseline.correct / totals.baseline.total),
    complementExecutions: complement.length, complementRuleFollowed: complement.filter(r => r.prediction === String(1 - r.case.bit)).length,
    learnedRevisions: learned, floatingTieSelections, scoreVerificationTolerance: 1e-10, rdfQuads: quads.length, rdfNamedGraphs: new Set(quads.map(q => q.graph.value)).size,
    scope: "Original provider output; independently recomputed LinUCB selections and A/b; exact frozen presentation and complete selected role closure; no independent reward authentication or full SHACL rerun" }, null, 2) + "\n"
})
if (process.argv[2] === "--help") process.stdout.write("node _research/local_activation_diagnostics_v1/check-learning.mjs LEARNING_DIRECTORY [--evidence-only]\nRead-only original-output, native admission, numerical state, prompt and RDF verification. Strict mode also requires unchanged live build hashes. Evidence-only mode reports build drift explicitly; it never refreshes original hashes.\n")
else if (process.argv.length !== 3 && !(process.argv.length === 4 && process.argv[3] === "--evidence-only")) process.exitCode = 2
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "ACTIVATION_CHECK_REFUSED", program: () => check(resolve(process.argv[2]), process.argv[3] === "--evidence-only"), describeFailure: error => String(error?.cause ?? error) }, [])
