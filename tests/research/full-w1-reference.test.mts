import assert from 'node:assert/strict'
import test from 'node:test'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { assertReferenceMatches, validateW1Structure, verifyReference } from '../../_research/local_semantic_execution_w1_v2/verify-reference.mts'
import { domain, requestFor } from '../../_research/local_semantic_execution_w1_v2/runner.mts'

test('audits fresh Lean source and compares every actual transformed TS frame with the finite reference', async () => {
  const parent = await mkdtemp(join(tmpdir(), 'hswm-w1-reference-'))
  try {
    const output = join(parent, 'audit'), report = await verifyReference(output)
    assert.equal(report.comparison.rows, 768)
    assert.deepEqual(report.comparison.transforms.map(entry => entry.matched), [128, 128, 128, 128, 128, 128])
    assert.equal(report.refused_cases.length, 9)
    assert.equal(report.kernel.sources[0].theorem_axioms.length, report.kernel.sources[0].named_theorem_count)
    assert.ok(report.kernel.sources[0].theorem_axioms.every((entry: any) => entry.axioms.every((axiom: string) => ['propext', 'Quot.sound', 'Classical.choice'].includes(axiom))))
    assert.equal(report.actual_model_requests, 0)
    assert.equal(report.experiment_protocol_changed, false)
    assert.equal(report.comparison.relation_text_bindings.length, 24)
    assert.ok(report.comparison.relation_text_bindings.every((entry: any) => entry.interpretation === 'AUTHOR_DECLARED_NOT_NLP_SEMANTICS_PROOF'))
    assert.equal(report.comparison.structure.schedule_rows, 2784)
    assert.equal(report.comparison.model_visible_request_bindings.length, 2784)
    assert.equal(report.comparison.structure.order_claim, 'ORDINAL_AND_PARTITION_CHECKED_NOT_LEAN_ORDER_EQUIVALENCE_PROOF')
    assert.ok(report.limitations.some((entry: string) => entry.includes('authored bytes only')))
    await assert.rejects(() => verifyReference(output), /EEXIST/)
  } finally { await rm(parent, { recursive: true, force: true }) }
})

test('structure binding rejects byte, census, and sentinel mutations before any Lean or HTTP work', () => {
  const { fullW1Cases, fullW1Schedule, fullW1Sentinels } = domain
  const valid = () => validateW1Structure({ cases: fullW1Cases, schedule: fullW1Schedule, sentinels: fullW1Sentinels, requestFor })
  assert.equal(valid().request_bindings.length, 2784)
  const duplicateCases = structuredClone(fullW1Cases) as any[]
  duplicateCases[1] = structuredClone(duplicateCases[0])
  assert.throws(() => validateW1Structure({ cases: duplicateCases, schedule: fullW1Schedule, sentinels: fullW1Sentinels }), /CASE_ID_COVERAGE_MISMATCH/)
  const corruptJson = structuredClone(fullW1Cases) as any[]
  corruptJson[0].inputJson = '{}'
  assert.throws(() => validateW1Structure({ cases: corruptJson, schedule: fullW1Schedule, sentinels: fullW1Sentinels }), /INPUT_JSON_MISMATCH/)
  const corruptSentinels = structuredClone(fullW1Sentinels) as any[]
  corruptSentinels[0].caseId = corruptSentinels[1].caseId
  assert.throws(() => validateW1Structure({ cases: fullW1Cases, schedule: fullW1Schedule, sentinels: corruptSentinels }), /SENTINEL_MAPPING_MISMATCH/)
  const duplicateSchedule = structuredClone(fullW1Schedule) as any[]
  duplicateSchedule[1] = structuredClone(duplicateSchedule[0])
  duplicateSchedule[1].ordinal = 1
  assert.throws(() => validateW1Structure({ cases: fullW1Cases, schedule: duplicateSchedule, sentinels: fullW1Sentinels }), /CENSUS_ARM_COVERAGE_MISMATCH/)
})

test('finite conformance rejects a changed oracle value or row identity', () => {
  const expected = { base: 0, context_flip: 1, exception_flip: 0, answer: 1 }
  const cases = [{ caseId: 'case', expected }]
  assertReferenceMatches(cases, { cases: [{ caseId: 'case', accepted: true, output: { answer: 1, exception_flip: 0, base: 0, context_flip: 1 } }] })
  for (const row of [{ caseId: 'case', accepted: true, output: { ...expected, answer: 0 } }, { caseId: 'other', accepted: true, output: expected }, { caseId: 'case', accepted: false, output: expected }]) {
    assert.throws(() => assertReferenceMatches(cases, { cases: [row] }), /REFERENCE_OUTPUT_MISMATCH/)
  }
})
