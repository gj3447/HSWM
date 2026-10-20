import { test } from "node:test"
import assert from "node:assert/strict"
import { protocol, evaluate, parseCommand, assess, type Row } from "./domain.mts"
const task = { id: "unit", focus: "structure", bundle: "tool-harness" } as const
const structural = { schema_version: "hswm-workspace-observation/v1", id: task.bundle, conforms: false, structuralIssues: [], shapes: [{}] }
test("reports a genuine negative structural result as sufficient information", () => assert.equal(evaluate(task, 1, structural), true))
test("exit status, response identity and required information are jointly required", () => {
  assert.equal(evaluate(task, null, structural), false)
  assert.equal(evaluate(task, 0, { ...structural, id: "other" }), false)
  assert.equal(evaluate(task, 0, { schema_version: structural.schema_version, id: task.bundle, status: "PASS" }), false)
  assert.equal(evaluate(task, 0, { ...structural, shapes: [] }), false)
})
test("source drift remains useful information; wrong command output earns no credit", () => {
  const sources = { ...task, focus: "sources" } as const
  assert.equal(evaluate(sources, 0, structural), false)
  assert.equal(evaluate(sources, 0, { schema_version: structural.schema_version, id: task.bundle,
    rows: [{ path: "guide.md", sha256: "declared", status: "WORKTREE_DIFFERS" }] }), true)
})
test("argv allowlist rejects flags, substitution, different bundle and shell chaining", () => {
  assert.deepEqual(parseCommand("validate tool-harness", task), ["validate", "tool-harness"])
  for (const invalid of ["validate identity", "validate tool-harness; rm -rf .", "show $(pwd)", "show --help", "show ../tool-harness", "show tool-harness\n"]) {
    assert.equal(parseCommand(invalid, task), null, invalid)
  }
})
const rows = (): Row[] => protocol.conditions.flatMap(phase => protocol.holdout.map(task => {
  const learned = phase === "learned" || phase === "restored"
  const command = learned ? { navigation: "show", structure: "validate", sources: "bindings" }[task.focus] : "show"
  return { phase, task, candidate: command, prediction: `${command} ${task.bundle}`, correct: learned || task.focus === "navigation",
    policyRevision: learned ? 18 : 0, traceSha256: "fixture", outputSha256: "fixture", executionId: `${phase}-${task.id}` }
}))
test("all conditions and paired removal/restoration are necessary", () => {
  assert.equal(assess(rows()).accepted, true)
  assert.equal(assess(rows().filter(r => r.phase !== "observations-only")).accepted, false)
  assert.equal(assess(rows().map(r => r.phase === "restored" ? { ...r, correct: false } : r)).accepted, false)
  assert.equal(assess(rows().map(r => ({ ...r, correct: true }))).accepted, false)
})
test("holdout bundle IDs are absent from training", () => {
  const train = new Set(protocol.train.map(task => task.bundle))
  assert.ok(protocol.holdout.every(task => !train.has(task.bundle)))
})
