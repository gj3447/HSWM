#!/usr/bin/env node
/** Read-only audit of the stopped P01 cohort and the separate likeness bridge witness. */
import { readFileSync, readdirSync, existsSync } from "node:fs"
import { resolve, join, basename } from "node:path"
import { createHash } from "node:crypto"
import { isDeepStrictEqual } from "node:util"

const sha = x => createHash("sha256").update(x).digest("hex")
const read = path => JSON.parse(readFileSync(path, "utf8"))
const need = (ok, message) => { if (!ok) throw new Error(message) }
const same = (a, b, message) => need(isDeepStrictEqual(a, b), message)
const hashJson = x => sha(JSON.stringify(x))
const repo = resolve(new URL("../..", import.meta.url).pathname)
// Independent evaluator: do not import the producer's operator or its expected() function.
const accepts = (program, assignment) => {
  need(program.contract === "hswm-finite-semantic-program/v1", "Unknown finite program")
  const values = []
  for (const e of program.expressions) {
    const prior = i => { need(Number.isInteger(i) && i >= 0 && i < values.length, "Non-prior expression"); return values[i] }
    if (e.op === "is") values.push(assignment[e.variable] === e.value)
    else if (e.op === "and") values.push(prior(e.left) && prior(e.right))
    else if (e.op === "or") values.push(prior(e.left) || prior(e.right))
    else if (e.op === "not") values.push(!prior(e.arg))
    else throw new Error("Unknown finite operator")
  }
  return program.clauses.every(c => values[c.expression] === true)
}
const audit = (root, receiptPath) => {
  const receiptBytes = readFileSync(receiptPath), receipt = JSON.parse(receiptBytes)
  need(basename(receiptPath) === `${sha(receiptBytes)}.json`, "Receipt address mismatch")
  need(existsSync(join(root, receipt.artifactManifest.path)), "NOT_HYDRATED: private evidence manifest")
  const manifestBytes = readFileSync(join(root, receipt.artifactManifest.path))
  need(sha(manifestBytes) === receipt.artifactManifest.sha256, "Evidence manifest changed")
  const artifacts = JSON.parse(manifestBytes).artifacts
  for (const item of artifacts) {
    need(!item.path.startsWith("/") && !item.path.split("/").includes(".."), "Nonlocal artifact")
    const path = join(root, item.path)
    need(existsSync(path), `NOT_HYDRATED: ${item.path}`)
    const bytes = readFileSync(path)
    need(bytes.length === item.bytes && sha(bytes) === item.sha256, `EVIDENCE_DRIFT: ${item.path}`)
  }
  for (const item of receipt.sources) need(sha(readFileSync(join(repo, item.path))) === item.sha256, `SOURCE_DRIFT: ${item.path}`)
  const out = join(root, "prepared"), protocol = read(join(out, "protocol.json"))
  same(read(join(out, "started.json")).protocolSha256, sha(readFileSync(join(out, "protocol.json"))), "Protocol changed after start")
  for (const pin of protocol.sourcePins) need(sha(readFileSync(join(repo, pin.path))) === pin.sha256, `SOURCE_DRIFT: ${pin.path}`)
  need(protocol.backend === "OWNER_MODEL" && protocol.criteria.devViolations === 0, "Wrong cohort or stop rule")
  need(!existsSync(join(out, "summary.json")) && !existsSync(join(out, "repeat-1")), "Stopped cohort was continued")
  const local = join(out, "repeat-0"), native = join(local, "native"), objects = join(native, "objects")
  const object = d => {
    const bytes = readFileSync(join(objects, d.sha256))
    need(bytes.length === d.byteLength && sha(bytes) === d.sha256, "Native content mismatch")
    return JSON.parse(bytes)
  }
  const commits = readdirSync(join(native, "journal-objects")).map(name => {
    const bytes = readFileSync(join(native, "journal-objects", name)); need(sha(bytes) === name, "Journal address mismatch"); return JSON.parse(bytes)
  }).sort((a, b) => a.stateRevision - b.stateRevision)
  same(commits.map(c => c.stateRevision), [0, 1, 2], "Unexpected learning or topology write")
  const atoms = commits.flatMap(c => c.writeBindings ?? []).map(b => object(b.envelope))
  const policies = atoms.filter(a => a.kind === "semantic_context_policy")
  need(policies.length === 1 && policies[0].key.atomUid === "policy:w" && policies[0].key.revisionId === 0, "Policy advanced after failure")
  const policy = object(policies[0].content)
  for (const arm of policy.arms) same([arm.observations, arm.a, arm.b], [0, [[1, 0], [0, 1]], [0, 0]], "Unexecuted learning statistics")
  const rows = [], seenRequests = [], seenResponses = []
  let tokens = 0, elapsed = 0, stopped = false
  for (const c of protocol.cohorts[0].dev) {
    const path = join(local, `dev-${c.id}.json`)
    if (!existsSync(path)) { need(stopped, "Unexplained missing development row"); continue }
    need(!stopped, "Execution continued after a development failure")
    const r = read(path), trace = object(r.traceContent), request = object(trace.requestContent), wire = object(trace.transport.request), response = object(trace.transport.response)
    const { assemblySha256, ...assembly } = request.assembly
    need(hashJson(assembly) === assemblySha256 && trace.assemblySha256 === assemblySha256, "Assembly substitution")
    const payload = assembly.payload
    same(JSON.parse(payload.event), c, "Wrong frozen development event")
    same(payload.frames.map(f => f.relation.key.atomUid), ["rule:mandatory", `rule:${c.action}`, ...(c.action === "identity" ? ["rule:duplicate"] : [])], "Wrong selected closure")
    same([r.candidateId, assembly.selection.candidateId, r.policyRevision], [c.action, c.action, 0], "Selection or policy changed")
    const prompt = ["Execute the supplied rules on EVENT, preserving mandatory constraints and exceptions. Return only JSON with prediction and uncertainty strings.", JSON.stringify(payload), "EXECUTE NOW", ...payload.frames.map(f => f.relation.semantic.semanticText), "EVENT TO COMPUTE", payload.event, "Apply those rules to this event. Do not infer the answer from rule names."].join("\n")
    same(request.prompt, prompt, "Presented source differs from canonical frames")
    same(wire.messages.map(m => m.content), [prompt], "Wire prompt substituted")
    need(request.promptBytes === Buffer.byteLength(prompt) && request.promptBytes <= 65536, "Prompt budget mismatch")
    const programs = payload.frames.map(frame => {
      const atom = atoms.find(a => isDeepStrictEqual(a.key, frame.relation.key))
      need(atom && frame.relation.owner === atom.responsibilityOwner, "Source identity/owner missing")
      same(frame.relation.semantic, object(atom.content), "Source semantics changed")
      same(frame.roles.map(r => r.role), ["subject", "context", "evidence", "exception"], "Role loss")
      frame.roles.forEach((role, ordinal) => {
        const participant = atoms.find(a => isDeepStrictEqual(a.key, role.key))
        same(atom.references[ordinal], { referenceType: role.referenceType, role: role.role, target: role.key }, "Incidence changed")
        need(participant && participant.responsibilityOwner === role.owner && participant.content.sha256 === sha(role.contentUtf8), "Participant content/owner changed")
        need(sha(readFileSync(join(objects, participant.content.sha256))) === role.contentSha256, "Participant bytes missing")
      })
      const { frameSha256, ...body } = frame; need(hashJson(body) === frameSha256, "Frame digest mismatch")
      return JSON.parse(frame.relation.semantic.semanticText)
    })
    const possible = ["0", "1", "REFUSE"].filter(prediction => programs.every(p => accepts(p, { bit: String(c.bit), invalid: String(c.invalid), prediction })))
    const expected = c.invalid === 1 ? "REFUSE" : String(c.action === "identity" ? c.bit : Number(c.bit === 0))
    same(possible, [expected], "Finite semantics differ from independent operator oracle")
    need(response.model === protocol.model && response.choices.length === 1 && response.choices[0].finish_reason === "stop", "Incomplete or wrong model response")
    const prediction = JSON.parse(response.choices[0].message.content)
    same(prediction, object(trace.responseContent), "Decoded output substituted")
    same([r.prediction, trace.prediction, r.expected, r.correct], [prediction.prediction, prediction.prediction, expected, prediction.prediction === expected], "Outcome mismatch")
    const call = read(join(out, `call-${rows.length + 1}.json`)); same(call.response, response, "Observed response mismatch")
    need(Number.isFinite(response.usage?.total_tokens) && Number.isFinite(call.httpMs), "Unreported cost")
    tokens += response.usage.total_tokens; elapsed += call.httpMs
    seenRequests.push(trace.transport.request.sha256); seenResponses.push(trace.transport.response.sha256)
    rows.push({ id: c.id, action: c.action, expected, observed: prediction.prediction, correct: r.correct, trace: r.traceContent.sha256 })
    stopped = !r.correct
  }
  need(stopped && rows.length === 5, "Expected the preserved five-call P01 stop")
  same(readdirSync(out).filter(n => /^call-\d+\.json$/.test(n)).sort(), rows.map((_, i) => `call-${i + 1}.json`).sort(), "Call census mismatch")
  same(readdirSync(local).filter(n => n.endsWith(".json")).sort(), rows.map(r => `dev-${r.id}.json`).sort(), "Unexpected training/holdout/restart")
  const allNative = readdirSync(objects).flatMap(name => { try { return [{ name, value: read(join(objects, name)) }] } catch { return [] } })
  same(allNative.filter(x => x.value.messages && x.value.model).map(x => x.name).sort(), seenRequests.sort(), "Unaccounted wire request")
  same(allNative.filter(x => x.value.choices && x.value.model).map(x => x.name).sort(), seenResponses.sort(), "Unaccounted response")
  const bridge = join(root, "likeness-bridge"), input = read(join(bridge, "input.json")), evidence = read(join(bridge, "policy-evidence.json")), binding = read(join(bridge, "binding.json")), witness = read(join(bridge, "validation.json"))
  input.evidence.forEach(e => need(sha(readFileSync(join(bridge, e.path))) === e.sha256, "Likeness original evidence mismatch"))
  same(input.graph, binding.graph, "Native/likeness binding mismatch")
  need(hashJson(evidence.report) === evidence.reportSha256 && evidence.reportSha256 === witness.reportSha256, "Likeness report mismatch")
  const before = read(join(bridge, "before.json")), after = read(join(bridge, "after.json")), reopened = read(join(bridge, "restarted.json")), restored = read(join(bridge, "restored.json"))
  same([before.selection.candidateId, after.selection.candidateId, reopened.candidateId, restored.selection.candidateId], ["calendar", "door", "door", "calendar"], "Cross-process bridge/restore mismatch")
  same([reopened.policyKey.revisionId, restored.selection.policyKey.revisionId], [1, 2], "Bridge revision mismatch")
  need(input.dataKind === "SYNTHETIC" && witness.realProviderCalls === 0 && witness.observedOperationalEfficacy === null, "Synthetic efficacy promotion")
  const result = { status: "P01_FAILED", actualProviderCalls: rows.length, developmentCorrect: rows.filter(r => r.correct).length, providerTokens: tokens, policyRevision: 0, learningUpdates: 0, holdoutExecutions: 0, topologyUpdates: 0, bridge: "SYNTHETIC_CLI_OWNER_REOPEN_RESTORE_PASS" }
  same(result, receipt.observations, "Receipt observations differ from original evidence")
  const ids = new Set(receipt.graph["@graph"].map(n => n["@id"]))
  need(ids.size === receipt.graph["@graph"].length, "Duplicate provenance identity")
  for (const n of receipt.graph["@graph"]) for (const p of ["prov:used", "prov:wasGeneratedBy", "prov:wasDerivedFrom"]) for (const ref of n[p] ?? []) need(ids.has(ref["@id"]), "Dangling provenance link")
  need(receipt.graph["@graph"].some(n => n["prov:value"] === JSON.stringify(result)), "Graph result disagrees with receipt")
  return { ...result, httpTotalMs: elapsed, failedCase: rows.at(-1), artifactCount: artifacts.length, claim: "One stopped authored development prefix; no W efficacy estimate. Bridge witness uses independent synthetic observations." }
}
if (process.argv[2] === "--help") console.log("node _research/semantic_w_loop_v1/check.mjs PRIVATE_ROOT CONTENT_ADDRESSED_RECEIPT.json\nRead-only original-byte, source, whole finite-constraint, prompt/wire, outcome, no-learning and likeness-bridge verification; no provider call.")
else try {
  need(process.argv.length === 4, "Expected PRIVATE_ROOT and RECEIPT; see --help")
  console.log(JSON.stringify(audit(resolve(process.argv[2]), resolve(process.argv[3])), null, 2))
} catch (error) { console.error(`SEMANTIC_W_AUDIT_REFUSED: ${String(error)}`); process.exitCode = 1 }
