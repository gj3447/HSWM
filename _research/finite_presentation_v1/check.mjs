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
  same(read(join(out, "started.json")).protocolSha256, sha(readFileSync(join(out, "protocol.json"))), "Protocol changed")
  for (const pin of protocol.sourcePins) need(sha(readFileSync(join(repo, pin.path))) === pin.sha256, `SOURCE_DRIFT: ${pin.path}`)
  for (const item of protocol.sourceFiles) need(sha(readFileSync(join(native, item.path))) === item.sha256, `ORIGINAL_DRIFT: ${item.path}`)
  const object = d => { const bytes = readFileSync(join(native, "objects", d.sha256)); need(bytes.length === d.byteLength && sha(bytes) === d.sha256, "Descriptor mismatch"); return JSON.parse(bytes) }
  const journals = readdirSync(join(native, "journal-objects")).map(n => read(join(native, "journal-objects", n)))
  const atoms = journals.flatMap(j => j.writeBindings ?? []).map(b => object(b.envelope))
  const groups = Object.fromEntries(protocol.presentations.map(p => [p, { total: 0, correct: 0, exceptionViolations: 0, promptBytes: 0, tokens: 0, httpMs: 0 }]))
  let id = 0, wholeAssignments = 0
  const failures = []
  for (const [index, c] of protocol.cases.entries()) for (const presentation of index % 2 ? [...protocol.presentations].reverse() : protocol.presentations) {
    const r = read(join(out, `record-${++id}.json`)), trace = object(r.trace.traceContent), request = object(trace.requestContent)
    const sent = object(trace.transport.request), received = object(trace.transport.response)
    same([r.call, r.presentation, r.case], [id, presentation, c], "Fixed case/order changed")
    same(received, read(join(out, `call-${id}-response.json`)), "Response substituted")
    same(read(join(out, `call-${id}-attempt.json`)).requestSha256, trace.transport.request.sha256, "Attempt/wire mismatch")
    same(sent.messages.map(m => m.content), [request.prompt], "Stored prompt was not sent")
    need(sent.model === protocol.model && sent.max_tokens === 512 && received.model === protocol.model && received.choices[0].finish_reason === "stop", "Model/config/incomplete response")
    const answer = JSON.parse(received.choices[0].message.content)
    same(answer, object(trace.responseContent), "Prediction changed after provider response")
    same(request.assembly, r.assembly, "Assembly mismatch")
    const { assemblySha256, ...assembly } = request.assembly
    need(sha(JSON.stringify(assembly)) === assemblySha256 && trace.assemblySha256 === assemblySha256, "Assembly identity changed")
    same([request.presentation, request.assembly.selection.candidateId], [presentation, c.action], "Presentation/selection changed")
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
    const blocks = presentation === "finite_table_tail" ? request.prompt.split("BEGIN ALLOWED ROWS\n").slice(1) : []
    if (presentation === "finite_table_tail") need(blocks.length === programs.length, "Missing full table")
    for (const [i, p] of programs.entries()) {
      const all = p.variables.reduce((rows, v) => rows.flatMap(row => v.values.map(value => [...row, value])), [[]])
      const rows = all.filter(row => accepted(p, row)); wholeAssignments += all.length
      if (presentation === "finite_table_tail") {
        const text = blocks[i].split("END ALLOWED ROWS")[0].trim(), rendered = text ? text.split("\n").map(line => JSON.parse(line)) : []
        same(rendered, rows, "Table loses or adds satisfying assignments")
      }
    }
    const expected = c.invalid ? "REFUSE" : String(c.action === "identity" ? c.bit : Number(c.bit === 0))
    const feasible = ["0", "1", "REFUSE"].filter(prediction => programs.every(p => accepted(p, p.variables.map(v => ({ bit: String(c.bit), invalid: String(c.invalid), prediction })[v.id]))))
    same(feasible, [expected], "Independent oracle differs from full conjunction")
    same([r.expected, r.correct, r.trace.prediction], [expected, answer.prediction === expected, answer.prediction], "Outcome altered")
    const promptBytes = Buffer.byteLength(request.prompt)
    need(promptBytes === request.promptBytes && promptBytes <= 65536, "Prompt byte budget violated")
    const g = groups[presentation];g.total++;g.correct += Number(r.correct);g.exceptionViolations += Number(c.invalid && !r.correct);g.promptBytes += promptBytes
    need(Number.isFinite(received.usage?.total_tokens), "Provider token usage unknown")
    g.tokens += received.usage.total_tokens;g.httpMs += read(join(out, `call-${id}-cost.json`)).httpMs
    if (!r.correct) failures.push({ call: id, presentation, case: c.id, expected, actual: answer.prediction })
  }
  need(id === 32 && summary.actualProviderCalls === id, "Incomplete cohort")
  need(readdirSync(out).filter(n => /^call-\d+-attempt.json$/.test(n)).length === id, "Unexpected attempted call")
  const beforeJournals = protocol.sourceFiles.filter(p => p.path.startsWith("journal-objects/")).map(p => p.path.split("/").at(-1)).sort()
  same(readdirSync(join(native, "journal-objects")).sort(), beforeJournals, "Native canonical state changed")
  for (const p of protocol.presentations) same(summary.groups[p], { total: groups[p].total, correct: groups[p].correct, exceptionViolations: groups[p].exceptionViolations }, "Summary count mismatch")
  same(summary.status, groups.finite_table_tail.correct === 16 ? "P01_DEVELOPMENT_PASS" : "P01_FAILED", "Gate redefined")
  return { status: "EVIDENCE_VERIFIED", gate: summary.status, actualProviderCalls: id, groups, wholeAssignmentsChecked: wholeAssignments, failures, learningUpdates: 0, topologyUpdates: 0, claim: "Development-exposed authored finite census; assisted table execution, not independent holdout or W efficacy" }
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
  if (process.argv[2] === "--help") console.log("node _research/finite_presentation_v1/check.mjs COMPLETED_OUTPUT\nnode _research/finite_presentation_v1/check.mjs PRIVATE_ROOT CONTENT_ADDRESSED_RECEIPT.json\nRead-only complete-rule, original-role, prompt/wire, response, no-learning and cost audit; receipt mode also locks original artifact bytes. No provider calls.")
  else {
    need(process.argv.length === 3 || process.argv.length === 4, "Expected output or private root + receipt; see --help")
    console.log(JSON.stringify(process.argv.length === 4 ? auditReceipt(resolve(process.argv[2]), resolve(process.argv[3])) : check(resolve(process.argv[2])), null, 2))
  }
} catch (error) { console.error(`FINITE_PRESENTATION_AUDIT_REFUSED: ${String(error)}`);process.exitCode = 1 }
