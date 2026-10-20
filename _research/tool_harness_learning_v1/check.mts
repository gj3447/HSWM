/** Independent byte/trace/outcome/statistics reconstruction. No provider calls or state writes. */
import { readFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { createHash } from "node:crypto"
import assert from "node:assert/strict"

type Obj = Record<string, unknown>
const obj = (v: unknown): Obj => { assert.ok(v !== null && typeof v === "object" && !Array.isArray(v)); return v as Obj }
const array = (v: unknown): unknown[] => { assert.ok(Array.isArray(v)); return v }
const json = (path: string): Obj => obj(JSON.parse(readFileSync(path, "utf8")))
const sha = (v: string | Uint8Array) => createHash("sha256").update(v).digest("hex")
const directory = resolve(process.argv[2] ?? "")
assert.ok(process.argv[2], "Explicit run directory required")
const frozen = json(join(directory, "protocol.json")), p = obj(frozen["protocol"])
const summary = json(join(directory, "summary.json"))
assert.equal(summary["protocolSha256"], sha(readFileSync(join(directory, "protocol.json"))))
const content = (native: string, descriptor: unknown) => {
  const d = obj(descriptor)
  assert.match(String(d["sha256"]), /^[0-9a-f]{64}$/)
  const raw = readFileSync(join(directory, native, "objects", String(d["sha256"])))
  assert.equal(raw.length, d["byteLength"])
  assert.equal(sha(raw), d["sha256"])
  return obj(JSON.parse(raw.toString()))
}
const holdout = array(p["holdout"]).map(obj), train = array(p["train"]).map(obj)
const phases = ["baseline", "learned", "observations-only", "removed", "restored"]
const ordered = [
  ...["show", "validate", "bindings"].map(command => ({ phase: "dev", task: { id: `dev-${command}`, focus: "navigation", bundle: "tool-harness" } })),
  ...holdout.map(task => ({ phase: "baseline", task })),
  ...train.map(task => ({ phase: "train", task })),
  ...phases.slice(1).flatMap(phase => holdout.map(task => ({ phase, task })))
]
assert.equal(ordered.length, p["expectedProviderCalls"])
const scores = Object.fromEntries(phases.map(phase => [phase, 0]))
const commandsByPhase: Record<string, string[]> = Object.fromEntries(phases.map(phase => [phase, []]))
const stats = ["show", "validate", "bindings"].map(candidateId => ({ candidateId, observations: 0,
  a: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], b: [0, 0, 0] }))
let totalTokens: number | null = 0, totalHttpMs = 0
for (const [index, entry] of ordered.entries()) {
  const stored = json(join(directory, `${entry.phase}-${entry.task["id"]}.json`)), row = obj(stored["row"])
  assert.deepEqual(row["task"], entry.task)
  const native = ["observations-only", "removed", "restored"].includes(entry.phase) ? entry.phase : "native"
  const trace = content(native, stored["traceContent"]), observation = content(native, stored["outputContent"])
  const request = content(native, trace["requestContent"])
  assert.equal(row["executionId"], trace["executionId"])
  assert.equal(observation["executionId"], trace["executionId"])
  assert.equal(row["traceSha256"], obj(stored["traceContent"])["sha256"])
  assert.equal(row["outputSha256"], obj(stored["outputContent"])["sha256"])
  const wire = json(join(directory, `wire-${index + 1}-request.json`))
  const response = json(join(directory, `wire-${index + 1}-response.json`))
  assert.equal(obj(array(wire["messages"])[0])["content"], request["prompt"])
  const prediction = obj(JSON.parse(String(obj(obj(array(response["choices"])[0])["message"])["content"])))
  assert.equal(prediction["prediction"], trace["prediction"])
  assert.equal(row["prediction"], trace["prediction"])
  const args = array(observation["args"])
  assert.equal(args.join(" "), trace["prediction"])
  assert.equal(args[1], entry.task["bundle"])
  const output = obj(JSON.parse(String(observation["stdout"])))
  assert.equal(output["schema_version"], "hswm-workspace-observation/v1")
  const focus = entry.task["focus"]
  const completed = observation["exitCode"] === 0 || (focus === "structure" && observation["exitCode"] === 1 && output["conforms"] === false)
  const sufficient = completed && (focus === "navigation"
    ? typeof output["entry"] === "object" && obj(output["entry"])["id"] === entry.task["bundle"] && Array.isArray(obj(output["entry"])["queries"])
    : output["id"] === entry.task["bundle"] && (focus === "structure"
      ? typeof output["conforms"] === "boolean" && Array.isArray(output["shapes"]) && output["shapes"].length > 0
      : Array.isArray(output["rows"]) && output["rows"].length > 0 && output["rows"].every(v => typeof obj(v)["path"] === "string" && typeof obj(v)["status"] === "string")))
  assert.equal(row["correct"], sufficient)
  if (entry.phase in scores) {
    scores[entry.phase] = (scores[entry.phase] ?? 0) + Number(sufficient)
    commandsByPhase[entry.phase]?.push(String(trace["prediction"]))
  }
  const usage = response["usage"]
  totalTokens = totalTokens !== null && typeof usage === "object" && usage !== null &&
    typeof obj(usage)["total_tokens"] === "number" ? totalTokens + Number(obj(usage)["total_tokens"]) : null
  totalHttpMs += Number(json(join(directory, `wire-${index + 1}-timing.json`))["httpMs"])
  if (entry.phase === "train") {
    const selection = obj(obj(request["assembly"])["selection"])
    const arm = stats.find(s => s.candidateId === selection["candidateId"])
    assert.ok(arm)
    const x = array(obj(selection["features"])["values"]).map(Number)
    arm.observations++
    arm.a = arm.a.map((r, i) => r.map((v, j) => v + Number(x[i]) * Number(x[j])))
    arm.b = arm.b.map((v, i) => v + Number(sufficient) * Number(x[i]))
    const learned = json(join(directory, `learn-${Number(row["policyRevision"]) + 1}.json`))
    const feedback = obj(learned["feedback"])
    assert.equal(feedback["reward"], Number(sufficient))
    assert.deepEqual(feedback["traceContent"], stored["traceContent"])
    const outcome = content("native", learned["outcomeContent"])
    assert.equal(outcome["executionId"], trace["executionId"])
    assert.equal(obj(learned["policy"])["feedbackSha256"], obj(learned["outcomeContent"])["sha256"])
  }
}
assert.equal(summary["actualProviderCalls"], ordered.length)
assert.equal(json(join(directory, "counter.json"))["calls"], ordered.length)
for (const phase of phases.slice(1)) {
  const worker = json(join(directory, `${phase}-worker.json`))
  const expectedRevision = phase === "learned" || phase === "restored" ? train.length : 0
  assert.equal(obj(worker["policyKey"])["revisionId"], expectedRevision)
  const native = phase === "learned" ? "native" : phase
  const policy = content(native, worker["policyContent"])
  assert.deepEqual(policy, worker["policy"])
  if (expectedRevision > 0) assert.deepEqual(policy["arms"], stats)
  else assert.ok(array(policy["arms"]).every(v => obj(v)["observations"] === 0))
}
assert.equal(scores["learned"], holdout.length)
assert.ok(Number(scores["learned"]) > Number(scores["baseline"]))
assert.ok(Number(scores["learned"]) > Number(scores["observations-only"]))
assert.deepEqual(commandsByPhase["removed"], commandsByPhase["baseline"])
assert.deepEqual(commandsByPhase["restored"], commandsByPhase["learned"])
console.log(JSON.stringify({ status: "VERIFIED_BOUNDED_NATIVE_POLICY_LEARNING", calls: ordered.length, scores,
  totalTokens, totalHttpMs, learnedPolicyRevision: train.length, statisticsReconstructed: true,
  limitation: "Declared intent features and authored retrieval contract; no independent population generalization or semantic-text learning claim" }, null, 2))
