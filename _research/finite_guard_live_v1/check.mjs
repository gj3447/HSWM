#!/usr/bin/env node
/** Independent read-only finite truth/transport/cost audit; never invokes the model or producer evaluator. */
import { readFileSync, readdirSync, existsSync } from "node:fs"
import { resolve, join, basename } from "node:path"
import { createHash } from "node:crypto"
import { isDeepStrictEqual } from "node:util"
const sha = b => createHash("sha256").update(b).digest("hex")
const read = p => JSON.parse(readFileSync(p, "utf8"))
const need = (ok, message) => { if (!ok) throw new Error(message) }
const same = (a, b, message) => need(isDeepStrictEqual(a, b), message)
const repo = resolve(new URL("../..", import.meta.url).pathname)
const accepted = (p, row) => {
  need(p.contract === "hswm-finite-semantic-program/v1", "Unknown finite program")
  const assignment = Object.fromEntries(p.variables.map((v, i) => [v.id, row[i]])), values = []
  for (const e of p.expressions) {
    const earlier = i => { need(Number.isInteger(i) && i >= 0 && i < values.length, "Invalid expression index"); return values[i] }
    if (e.op === "is") values.push(assignment[e.variable] === e.value)
    else if (e.op === "and") values.push(earlier(e.left) && earlier(e.right))
    else if (e.op === "or") values.push(earlier(e.left) || earlier(e.right))
    else if (e.op === "not") values.push(!earlier(e.arg))
    else if (e.op === "unless") values.push(!earlier(e.when) || earlier(e.exception) || earlier(e.require))
    else throw new Error("Unknown operator")
  }
  return p.clauses.every(c => values[c.expression] === true)
}
const check = out => {
  need(existsSync(join(out, "summary.json")), "NOT_HYDRATED_OR_INCOMPLETE: no complete cohort summary")
  const protocol = read(join(out, "protocol.json")), summary = read(join(out, "summary.json")), native = join(out, "native")
  const started = read(join(out, "started.json")), registration = read(join(out, "registration.json"))
  same(started.protocolSha256, sha(readFileSync(join(out, "protocol.json"))), "Protocol changed")
  same(started.registrationSha256, sha(readFileSync(join(out, "registration.json"))), "Registration changed")
  need(protocol.contract === "hswm-finite-guard-development/v1" && protocol.maximumProviderCalls === 32 && protocol.wallLimitMs === 900000 &&
    protocol.concurrency === 1 && protocol.perCallTimeoutMs === 30000 && protocol.presentation === "finite_table_tail", "Protocol limits changed")
  same(protocol.treatments, ["plain", "guarded"], "Treatments changed")
  const cases = [0, 1].flatMap(repeat => ["identity", "complement"].flatMap(action => [0, 1].flatMap(bit => [0, 1].map(invalid =>
    ({ id: `guard-dev-${repeat}-${action}-${bit}-${invalid}`, repeat, action, bit, invalid, signal: (action === "identity" ? 1 : -1) * (repeat ? 0.29 : 0.71) })))))
  same(protocol.cases, cases, "Frozen case census changed")
  need(registration.approved === true && registration.scope === "finite-guard-development" && registration.protocolSha256 === started.protocolSha256 &&
    registration.cellSha256 === protocol.cellSha256 && registration.reachability.status === 200 && registration.reachability.modelListed === true &&
    Date.parse(registration.reachability.observedAt) <= Date.parse(started.startedAt) &&
    Date.parse(started.startedAt) - Date.parse(registration.reachability.observedAt) < 1800000, "Missing current scoped registration/reachability")
  for (const pin of protocol.sourcePins) need(sha(readFileSync(join(repo, pin.path))) === pin.sha256, `SOURCE_DRIFT: ${pin.path}`)
  for (const item of protocol.sourceFiles) need(sha(readFileSync(join(native, item.path))) === item.sha256, `ORIGINAL_DRIFT: ${item.path}`)
  const object = d => { const bytes = readFileSync(join(native, "objects", d.sha256)); need(bytes.length === d.byteLength && sha(bytes) === d.sha256, "Descriptor mismatch"); return JSON.parse(bytes) }
  const journals = readdirSync(join(native, "journal-objects")).map(n => read(join(native, "journal-objects", n)))
  const atoms = journals.flatMap(j => j.writeBindings ?? []).map(b => object(b.envelope))
  const groups = Object.fromEntries(protocol.treatments.map(p => [p, { total: 0, correct: 0, returned: 0, rejected: 0,
    unsafeReturned: 0, exceptionViolations: 0, guardDisagreements: 0, promptBytes: 0, tokens: 0, httpMs: 0 }]))
  let id = 0, wholeAssignments = 0
  const failures = []
  for (const [index, c] of protocol.cases.entries()) for (const treatment of index % 2 ? [...protocol.treatments].reverse() : protocol.treatments) {
    const r = read(join(out, `record-${++id}.json`)), trace = object(r.trace.traceContent), request = object(trace.requestContent)
    const sent = object(trace.transport.request), received = object(trace.transport.response)
    same([r.call, r.treatment, r.presentation, r.case], [id, treatment, "finite_table_tail", c], "Fixed case/order changed")
    const attempt = read(join(out, `call-${id}-attempt.json`))
    need(attempt.id === id && Date.parse(attempt.at) >= Date.parse(started.startedAt) &&
      Date.parse(attempt.at) - Date.parse(started.startedAt) < protocol.wallLimitMs &&
      Date.parse(attempt.at) < Date.parse(registration.expiresAt), "Attempt outside registered limits")
    same(received, read(join(out, `call-${id}-response.json`)), "Response substituted")
    same(attempt.requestSha256, trace.transport.request.sha256, "Attempt/wire mismatch")
    same(sha(readFileSync(join(out, `call-${id}-response.json`))), trace.transport.response.sha256, "Raw response bytes changed")
    same(sent.messages.map(m => m.content), [request.prompt], "Stored prompt was not sent")
    need(sent.model === protocol.model && sent.max_tokens === 512 && received.model === protocol.model && received.choices[0].finish_reason === "stop", "Model/config/incomplete response")
    const answer = JSON.parse(received.choices[0].message.content)
    same(answer, object(trace.responseContent), "Prediction changed after provider response")
    same(request.assembly, r.assembly, "Assembly mismatch")
    const { assemblySha256, ...assembly } = request.assembly
    need(sha(JSON.stringify(assembly)) === assemblySha256 && trace.assemblySha256 === assemblySha256, "Assembly identity changed")
    same([request.presentation, request.assembly.selection.candidateId], ["finite_table_tail", c.action], "Presentation/selection changed")
    const payload = request.assembly.payload
    same(JSON.parse(request.prompt.split("\n")[1]), payload, "Canonical frames missing from prompt")
    same(JSON.parse(payload.event), c, "Wrong event")
    same(payload.frames.map(f => f.relation.key.atomUid), ["rule:mandatory", `rule:${c.action}`, ...(c.action === "identity" ? ["rule:duplicate"] : [])], "Wrong rule closure")
    const programs = payload.frames.map(f => {
      const atom = atoms.find(a => isDeepStrictEqual(a.key, f.relation.key))
      need(atom && atom.responsibilityOwner === f.relation.owner, "Relation identity/owner changed")
      same(f.relation.semantic, object(atom.content), "Original semantics changed")
      same(f.roles.map(r => r.role), ["subject", "context", "evidence", "exception"], "Role order changed")
      f.roles.forEach((role, ordinal) => {
        same(atom.references[ordinal], { referenceType: role.referenceType, role: role.role, target: role.key }, "Incidence changed")
        const participant = atoms.find(a => isDeepStrictEqual(a.key, role.key))
        need(participant && participant.responsibilityOwner === role.owner && participant.content.sha256 === sha(role.contentUtf8) && role.contentSha256 === sha(readFileSync(join(native, "objects", participant.content.sha256))), "Participant identity/content changed")
      })
      const { frameSha256, ...body } = f
      need(frameSha256 === sha(JSON.stringify(body)), "Frame digest mismatch")
      return JSON.parse(f.relation.semantic.semanticText)
    })
    const blocks = request.prompt.split("BEGIN ALLOWED ROWS\n").slice(1)
    need(blocks.length === programs.length, "Missing full table")
    for (const [i, p] of programs.entries()) {
      const all = p.variables.reduce((rows, v) => rows.flatMap(row => v.values.map(value => [...row, value])), [[]])
      const rows = all.filter(row => accepted(p, row)); wholeAssignments += all.length
      const text = blocks[i].split("END ALLOWED ROWS")[0].trim(), rendered = text ? text.split("\n").map(line => JSON.parse(line)) : []
      same(rendered, rows, "Table loses or adds satisfying assignments")
    }
    const expected = c.invalid ? "REFUSE" : String(c.action === "identity" ? c.bit : Number(c.bit === 0))
    const feasible = ["0", "1", "REFUSE"].filter(prediction => programs.every(p => accepted(p, p.variables.map(v => ({ bit: String(c.bit), invalid: String(c.invalid), prediction })[v.id]))))
    same(feasible, [expected], "Independent oracle differs from full conjunction")
    same([r.expected, r.correct, r.trace.prediction], [expected, answer.prediction === expected, answer.prediction], "Outcome altered")
    const { traceContent, ...recordedTrace } = r.trace
    same(recordedTrace, trace, "Recorded trace differs from content")
    need(trace.prediction === answer.prediction && trace.uncertainty === answer.uncertainty &&
      trace.canonicalWrite === false && trace.observedStatus === "PREDICTION_ONLY" &&
      trace.executionId === request.executionId && trace.planSha256 === assembly.planSha256 &&
      trace.selectionSha256 === sha(JSON.stringify(assembly.selection)), "Trace identity or original prediction changed")
    if (treatment === "guarded") {
      const bindings = { contract: "hswm-finite-execution-guard/v1", rules: payload.frames.map(f => ({ relationKey: f.relation.key,
        inputs: [{ variable: "bit", eventField: "bit" }, { variable: "invalid", eventField: "invalid" }], outputVariable: "prediction" })) }
      same(request.verification, bindings, "Bindings changed")
      need(trace.requestContent.mediaType === "application/vnd.hswm.semantic-context-request-v3+json", "Wrong guarded request version")
      same(JSON.parse(request.prompt.split("EXPLICIT INPUT/OUTPUT BINDINGS\n")[1]?.split("\n")[0] ?? "null"), bindings, "Model did not receive explicit bindings")
      const checks = programs.map((p, i) => {
        const assignment = Object.fromEntries(p.variables.map(v => [v.id, ({ bit: String(c.bit), invalid: String(c.invalid), prediction: answer.prediction })[v.id]]))
        return { relationKey: payload.frames[i].relation.key, frameSha256: payload.frames[i].frameSha256,
          assignment, accepted: p.variables.every(v => v.values.includes(assignment[v.id])) && accepted(p, p.variables.map(v => assignment[v.id])) }
      })
      const satisfied = checks.every(x => x.accepted)
      same(trace.verification, { contract: "hswm-finite-execution-verdict/v1",
        guardSha256: sha(JSON.stringify(bindings)), eventSha256: sha(JSON.stringify(payload.event)),
        prediction: answer.prediction, status: satisfied ? "SATISFIED" : "VIOLATED", checks,
        claimCeiling: "DECLARED_FINITE_CONSTRAINTS_ONLY_NOT_TASK_UTILITY_OR_MODEL_EFFICACY" }, "Guard verdict disagrees with independent evaluation")
      same([r.returned, r.errorCode], [satisfied, satisfied ? null : "FINITE_EXECUTION_VIOLATION"], "Guard return/error mismatch")
    } else {
      need(!Object.hasOwn(request, "verification") && !Object.hasOwn(trace, "verification") &&
        !request.prompt.includes("EXPLICIT INPUT/OUTPUT BINDINGS") &&
        trace.requestContent.mediaType === "application/vnd.hswm.semantic-context-request-v2+json", "Plain arm gained guard")
      same([r.returned, r.errorCode], [true, null], "Unexpected plain rejection")
    }
    const promptBytes = Buffer.byteLength(request.prompt)
    need(promptBytes === request.promptBytes && promptBytes <= 65536, "Prompt byte budget violated")
    const g = groups[treatment];g.total++;g.correct += Number(r.correct);g.exceptionViolations += Number(c.invalid && !r.correct);g.promptBytes += promptBytes
    g.returned += Number(r.returned);g.rejected += Number(!r.returned);g.unsafeReturned += Number(r.returned && !r.correct)
    g.guardDisagreements += Number(treatment === "guarded" && r.returned !== r.correct)
    need(Number.isFinite(received.usage?.total_tokens), "Provider token usage unknown")
    g.tokens += received.usage.total_tokens;g.httpMs += read(join(out, `call-${id}-cost.json`)).httpMs
    if (!r.correct) failures.push({ call: id, treatment, case: c.id, expected, actual: answer.prediction, returned: r.returned })
  }
  need(id === 32 && summary.actualProviderCalls === id, "Incomplete cohort")
  need(readdirSync(out).filter(n => /^call-\d+-attempt.json$/.test(n)).length === id, "Unexpected attempted call")
  const beforeJournals = protocol.sourceFiles.filter(p => p.path.startsWith("journal-objects/")).map(p => p.path.split("/").at(-1)).sort()
  same(readdirSync(join(native, "journal-objects")).sort(), beforeJournals, "Native canonical state changed")
  for (const p of protocol.treatments) {
    const { promptBytes, tokens, httpMs, ...counts } = groups[p]
    same(summary.groups[p], counts, "Summary count mismatch")
  }
  need(summary.learningUpdates === 0 && summary.topologyUpdates === 0 && summary.nativeStateUnchanged === true &&
    summary.stateRevision === Math.max(...journals.map(j => j.stateRevision)) && summary.observedGeneralEfficacy === null, "No-learning summary changed")
  same(summary.status, groups.guarded.correct === 16 && groups.guarded.returned === 16 && groups.guarded.guardDisagreements === 0 ? "P01_DEVELOPMENT_PASS" : "P01_FAILED", "Gate redefined")
  return { status: "EVIDENCE_VERIFIED", gate: summary.status, actualProviderCalls: id, groups, wholeAssignmentsChecked: wholeAssignments, failures,
    learningUpdates: 0, topologyUpdates: 0, claim: "Development-exposed authored finite census; table plus explicit bindings and checking. Guard rejection is not correct execution; no independent holdout or W efficacy." }
}
const auditReceipt = (root, receiptPath) => {
  const bytes = readFileSync(receiptPath), receipt = JSON.parse(bytes)
  need(basename(receiptPath) === `${sha(bytes)}.json`, "Receipt address mismatch")
  const local = path => { need(typeof path === "string" && path.length > 0 && !path.startsWith("/") && !path.split("/").includes(".."), "Nonlocal evidence path"); return join(root, path) }
  need(existsSync(local(receipt.artifactManifest.path)), "NOT_HYDRATED: private manifest")
  const manifest = readFileSync(local(receipt.artifactManifest.path))
  need(sha(manifest) === receipt.artifactManifest.sha256, "Manifest changed")
  for (const a of JSON.parse(manifest).artifacts) {
    need(existsSync(local(a.path)), `NOT_HYDRATED: ${a.path}`)
    const bytes = readFileSync(local(a.path))
    need(bytes.length === a.bytes && sha(bytes) === a.sha256, `EVIDENCE_DRIFT: ${a.path}`)
  }
  for (const pin of receipt.sources) need(sha(readFileSync(join(repo, pin.path))) === pin.sha256, `SOURCE_DRIFT: ${pin.path}`)
  const result = check(local(receipt.experiment))
  same(result, receipt.observations, "Receipt disagrees with original evidence")
  const nodes = receipt.graph["@graph"], ids = new Set(nodes.map(n => n["@id"]))
  need(ids.size === nodes.length, "Duplicate provenance identity")
  for (const n of nodes) for (const p of ["prov:used", "prov:wasGeneratedBy", "prov:wasDerivedFrom"]) for (const ref of n[p] ?? []) need(ids.has(ref["@id"]), "Dangling provenance link")
  need(nodes.some(n => n["prov:value"] === JSON.stringify(result)), "Graph result differs from observation")
  return result
}
try {
  if (process.argv[2] === "--help") console.log("node _research/finite_guard_live_v1/check.mjs COMPLETED_OUTPUT\nnode _research/finite_guard_live_v1/check.mjs PRIVATE_ROOT CONTENT_ADDRESSED_RECEIPT.json\nIndependent finite AST, original roles, full tables, bindings, exact wire/raw answer, guard verdict, return/error, no-learning, limits and cost audit. Receipt mode locks original bytes; never calls provider.")
  else {
    need(process.argv.length === 3 || process.argv.length === 4, "Expected output or private root + receipt; see --help")
    console.log(JSON.stringify(process.argv.length === 4 ? auditReceipt(resolve(process.argv[2]), resolve(process.argv[3])) : check(resolve(process.argv[2])), null, 2))
  }
} catch (error) { console.error(`FINITE_GUARD_LIVE_AUDIT_REFUSED: ${String(error)}`);process.exitCode = 1 }
