import assert from 'node:assert/strict'
import test from 'node:test'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { analyze, summarizeRows } from '../../_research/local_semantic_execution_w1_v2/analyze.mts'
import { makePlan, sourcePins, domain, json, sha } from '../../_research/local_semantic_execution_w1_v2/runner.mts'

async function fixture(options: { corruptPreflight?: boolean; terminal?: any } = {}) {
  const out = await mkdtemp(join(tmpdir(), 'hswm-w1-analysis-')), plan = makePlan(await sourcePins())
  const preflight = [{ name: 'models', file: 'preflight-models.json', body: { data: [{ id: 'qwen3-4b-real' }] } }, { name: 'token-0', file: 'preflight-token-0.json', body: { tokens: [15] } }, { name: 'token-1', file: 'preflight-token-1.json', body: { tokens: [16] } }]
  await mkdir(join(out, 'http')); await writeFile(join(out, 'plan.json'), json(plan)); await writeFile(join(out, 'reference.json'), json(domain.fullW1Cases.map((entry: any) => ({ caseId: entry.caseId, expected: entry.expected }))))
  const receipts: any[] = []; for (const item of preflight) { const raw = json(item.body); await writeFile(join(out, item.file), options.corruptPreflight && item.name === 'models' ? json({ data: [] }) : raw); receipts.push({ name: item.name, status: 200, elapsed_ms: 1, response_sha256: sha(raw) }) }
  await writeFile(join(out, 'started.json'), json({ evidence_kind: 'FIXTURE_ONLY', plan_sha256: sha(json(plan)) }))
  await writeFile(join(out, 'freeze.json'), json({ evidence_kind: 'FIXTURE_ONLY', plan_sha256: sha(json(plan)), source_pins: plan.pins, preflight: receipts, attestation: { fixture: true } }))
  if (options.terminal) await writeFile(join(out, 'completed.json'), json(options.terminal))
  return out
}

test('missing terminal preserves all scheduled W1 rows and fixture evidence cannot become model-ready', async () => {
  const out = await fixture()
  try { const result = await analyze(out); assert.equal(result.status, 'INCOMPLETE_OR_UNTERMINATED_CENSUS'); assert.equal(result.planned, 2784); assert.equal(result.missing_results, 2784); assert.equal(result.readiness, 'FIXTURE_ONLY_NOT_MODEL_READINESS'); assert.equal(result.arms.E0.all.scheduled, 928) } finally { await rm(out, { recursive: true }) }
})

test('preflight receipt hashes bind the captured semantic response body', async () => {
  const out = await fixture({ corruptPreflight: true })
  try { await assert.rejects(analyze(out), /PREFLIGHT_RESPONSE_BYTES_MISMATCH/) } finally { await rm(out, { recursive: true }) }
})

test('changing an evidence label cannot promote fixture metadata to an observed serving binding', async () => {
  const out = await fixture()
  try {
    for (const name of ['started.json', 'freeze.json']) {
      const path = join(out, name), value = JSON.parse(await readFile(path, 'utf8'))
      await writeFile(path, json({ ...value, evidence_kind: 'OBSERVED_MODEL_HTTP' }))
    }
    await assert.rejects(analyze(out), /SERVING_PIN_MISMATCH/)
  } finally { await rm(out, { recursive: true }) }
})

test('a terminal receipt cannot claim wall stop with an uncompleted attempted request', async () => {
  const out = await fixture({ terminal: { status: 'WALL_BUDGET_STOPPED', evidence_kind: 'FIXTURE_ONLY', planned: 2784, attempted: 1, elapsed_ms: 1 } })
  try { await writeFile(join(out, 'attempts.jsonl'), JSON.stringify({ ordinal: 0, caseId: (makePlan(await sourcePins())).schedule[0].caseId, mode: (makePlan(await sourcePins())).schedule[0].mode, request_sha256: (makePlan(await sourcePins())).schedule[0].request_sha256 }) + '\n'); const plan = JSON.parse(await readFile(join(out, 'plan.json'), 'utf8')); await writeFile(join(out, 'http', '0000.request.json'), JSON.stringify(plan.schedule[0].request)); await assert.rejects(analyze(out), /TERMINAL_RECEIPT_MISMATCH/) } finally { await rm(out, { recursive: true }) }
})

test('summary accounting retains missing and unreported usage', () => {
  const summary = summarizeRows([{ attempted: true, complete: true, valid: true, correct: true, elapsed_ms: 2, prompt_tokens: 3, completion_tokens: null, reasoning_tokens: null }, { attempted: true, complete: false, valid: false, correct: false, elapsed_ms: null, prompt_tokens: null, completion_tokens: null, reasoning_tokens: null, reason: 'ATTEMPT_WITHOUT_COMPLETION' }])
  assert.equal(summary.missing, 1); assert.equal(summary.cost.completion_tokens.sum_reported, null); assert.equal(summary.cost.prompt_tokens.unreported_records, 1)
})
