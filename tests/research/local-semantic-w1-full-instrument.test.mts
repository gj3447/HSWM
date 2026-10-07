import assert from 'node:assert/strict'
import { createServer, type Server } from 'node:http'
import test from 'node:test'
import { mkdtemp, readFile, rm, writeFile, unlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import * as runner from '../../_research/local_semantic_execution_w1_v2/runner.mts'
import { analyze } from '../../_research/local_semantic_execution_w1_v2/analyze.mts'
import { requestFor as originalRequest } from '../../_research/local_semantic_execution_v1/runner.mts'

const response = (mode: string, expected: any, wrong = false, omitUsage = false) => {
  const answer = wrong ? expected.answer ^ 1 : expected.answer
  const message = mode === 'E0' ? String(answer) : JSON.stringify(mode === 'E1' ? { answer } : { ...expected, answer })
  return { model: runner.protocol.model.served_name,
    choices: [{ finish_reason: 'stop', message: { content: message }, ...(mode === 'E0' ? { logprobs: { content: [{ top_logprobs: [
      { token: '0', logprob: Math.log(answer === 0 ? 0.9 : 0.1) }, { token: '1', logprob: Math.log(answer === 1 ? 0.9 : 0.1) }
    ] }] } } : {}) }], ...(omitUsage ? {} : { usage: { prompt_tokens: 7, completion_tokens: 1 } }) }
}
async function fixture(options: { originalFailure?: boolean; laterFailures?: boolean } = {}) {
  let calls = 0, probes = 0
  const cases = new Map(runner.domain.fullW1Cases.map((entry: any) => [entry.caseId, entry]))
  const server = createServer(async (request, reply) => {
    const parts = []; for await (const part of request) parts.push(part)
    const raw = Buffer.concat(parts).toString('utf8')
    const send = (status: number, value: unknown) => { reply.writeHead(status, { 'content-type': 'application/json' }); reply.end(JSON.stringify(value)) }
    if (request.method === 'GET' && request.url === '/v1/models') { probes++; return send(200, { data: [{ id: runner.protocol.model.served_name }] }) }
    if (request.method === 'POST' && request.url === '/tokenize') { probes++; return send(200, { tokens: JSON.parse(raw).prompt === '0' ? [15] : [16] }) }
    if (request.method !== 'POST' || request.url !== '/v1/chat/completions') return send(404, {})
    const scheduled = runner.domain.fullW1Schedule[calls++]
    assert.ok(scheduled, 'no unscheduled request is allowed')
    assert.equal(raw, JSON.stringify(runner.requestFor(scheduled)), 'HTTP body must equal the frozen request')
    const payload = JSON.parse(raw)
    const frame = JSON.parse(payload.messages[1].content.split('\n')[0])
    assert.equal(JSON.stringify(frame).includes('expected'), false)
    assert.equal(JSON.stringify(frame).includes('caseId'), false)
    const entry: any = cases.get(scheduled.caseId)
    if (options.laterFailures && scheduled.ordinal === 384) return send(500, { error: 'fixture' })
    if (options.laterFailures && scheduled.ordinal === 385) return reply.destroy()
    if (options.laterFailures && scheduled.ordinal === 386) { reply.writeHead(200); return reply.end('not-json') }
    return send(200, response(scheduled.mode, entry.expected,
      options.originalFailure === true && scheduled.ordinal < 3,
      options.laterFailures === true && scheduled.ordinal === 387))
  })
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const address = server.address(); assert.ok(address && typeof address === 'object')
  return { server, baseUrl: `http://127.0.0.1:${address.port}/`, calls: () => calls, probes: () => probes }
}
const close = (server: Server) => new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
const executeFixture = (out: string, f: Awaited<ReturnType<typeof fixture>>, wallMs?: number) => runner.execute(out, {
  baseUrl: f.baseUrl, evidenceKind: 'FIXTURE_ONLY', attestation: { fixture: true }, ...(wallMs === undefined ? {} : { wallMs })
})

test('new runs reject pre-existing receipt sinks before any HTTP probe', async () => {
  const out = await mkdtemp(join(tmpdir(), 'hswm-w1-full-existing-')), f = await fixture()
  try {
    const path = join(out, 'attempts.jsonl')
    await writeFile(path, 'prior receipt\n')
    await assert.rejects(() => runner.prepare(out), /PREPARE_REQUIRES_EMPTY_DIRECTORY/)
    assert.equal(await readFile(path, 'utf8'), 'prior receipt\n')
    await unlink(path)
    await runner.prepare(out)
    await writeFile(path, 'inserted after preparation\n')
    await assert.rejects(() => executeFixture(out, f), /EEXIST/)
    assert.equal(await readFile(path, 'utf8'), 'inserted after preparation\n')
    assert.equal(f.probes(), 0); assert.equal(f.calls(), 0)
  } finally { await close(f.server); await rm(out, { recursive: true, force: true }) }
})

test('full loopback census preserves original request bytes, exact sentinel bodies, and fixture-only evidence', async () => {
  const out = await mkdtemp(join(tmpdir(), 'hswm-w1-full-http-')), f = await fixture()
  try {
    const prepared = await runner.prepare(out)
    assert.equal(prepared.cases, 768); assert.equal(prepared.requests, 2784)
    const plan = await runner.verifyPlan(out)
    for (const item of plan.schedule.slice(0, 384)) {
      const frame = plan.frames.find((entry: any) => entry.caseId === item.caseId)
      assert.equal(JSON.stringify(item.request), JSON.stringify(originalRequest({ caseId: frame.baseCaseId, mode: item.mode })))
    }
    for (const item of plan.schedule.filter((entry: any) => entry.kind === 'sentinel')) {
      const baseline = plan.schedule.find((entry: any) => entry.kind === 'census' && entry.caseId === item.caseId && entry.mode === item.mode)
      assert.equal(item.request_sha256, baseline.request_sha256)
    }
    assert.equal((await executeFixture(out, f)).status, 'SCHEDULE_COMPLETED')
    assert.equal(f.calls(), 2784); assert.equal(f.probes(), 3)
    const summary: any = await analyze(out)
    assert.equal(summary.status, 'COMPLETE_CENSUS')
    assert.equal(summary.evidence_kind, 'FIXTURE_ONLY')
    assert.equal(summary.readiness, 'FIXTURE_ONLY_NOT_MODEL_READINESS')
    for (const mode of ['E0', 'E1', 'E2']) {
      assert.equal(summary.arms[mode].all.scheduled, 928)
      assert.equal(summary.arms[mode].all.correct, 928)
      assert.equal(summary.arms[mode].all.missing, 0)
      assert.equal(summary.by_family_transform[mode].original['0'].scheduled, 32)
      assert.equal(summary.role_exchange[mode].changed_input.scheduled, 64)
      assert.equal(summary.role_exchange[mode].changed_answer.scheduled, 32)
      assert.equal(summary.role_exchange[mode].changed_intermediate.scheduled, 64)
    }
    assert.deepEqual(summary.readiness_eligible_arms, ['E0', 'E1', 'E2'])
    // These are new synthetic ledgers made from the fixture, never model evidence.
    // One bad arm must not disqualify another; E2 diagnostics are not a new answer gate.
    const resultPath = join(out, 'results.jsonl')
    const receipts = (await readFile(resultPath, 'utf8')).trim().split('\n').map(line => JSON.parse(line))
    const replaceOutput = async (item: any, value: any) => {
      const raw = JSON.stringify(value)
      await writeFile(join(out, 'http', `${String(item.ordinal).padStart(4, '0')}.response.json`), raw)
      receipts[item.ordinal].response_sha256 = runner.sha(raw)
      await writeFile(resultPath, receipts.map(row => JSON.stringify(row)).join('\n') + '\n')
    }
    const transformedE0 = plan.schedule.find((item: any) => item.ordinal >= 384 && item.kind === 'census' && item.mode === 'E0')
    const originalE2 = plan.schedule.find((item: any) => item.mode === 'E2')
    const expectedFor = (item: any) => runner.domain.fullW1Cases.find((entry: any) => entry.caseId === item.caseId).expected
    await replaceOutput(transformedE0, response('E0', expectedFor(transformedE0), true))
    const e2 = expectedFor(originalE2)
    await replaceOutput(originalE2, response('E2', { ...e2, base: e2.base ^ 1 }))
    const mixed: any = await analyze(out)
    assert.deepEqual(mixed.readiness_eligible_arms, ['E1', 'E2'])
    assert.equal(mixed.arms.E2.all.intermediate_incorrect, 1)
    assert.equal(mixed.readiness, 'FIXTURE_ONLY_NOT_MODEL_READINESS')
    const sentinelE1 = plan.schedule.find((item: any) => item.kind === 'sentinel' && item.mode === 'E1')
    await replaceOutput(sentinelE1, response('E1', expectedFor(sentinelE1), true))
    const unstable: any = await analyze(out)
    assert.deepEqual(unstable.readiness_eligible_arms, ['E2'])
    assert.equal(unstable.sentinel_stability[`E1:${sentinelE1.sentinelId}`].bit_instability, true)
    await assert.rejects(() => executeFixture(out, f), /EEXIST/)
    const terminal = join(out, 'completed.json'); await unlink(terminal)
    assert.equal((await analyze(out) as any).status, 'INCOMPLETE_OR_UNTERMINATED_CENSUS')
  } finally { await close(f.server); await rm(out, { recursive: true, force: true }) }
})

test('an original pilot failure stops before transforms while all planned denominators stay visible', async () => {
  const out = await mkdtemp(join(tmpdir(), 'hswm-w1-full-stop-')), f = await fixture({ originalFailure: true })
  try {
    await runner.prepare(out)
    const result = await executeFixture(out, f)
    assert.equal(result.status, 'ORIGINAL_PILOT_FAILED'); assert.equal(f.calls(), 384)
    const summary: any = await analyze(out)
    assert.equal(summary.planned, 2784); assert.equal(summary.attempted, 384)
    assert.equal(summary.missing_results, 2400)
    for (const mode of ['E0', 'E1', 'E2']) {
      assert.equal(summary.arms[mode].all.scheduled, 928)
      assert.equal(summary.arms[mode].all.missing, 800)
      assert.equal(summary.arms[mode].all.correct, 127)
    }
    const terminal = await runner.readJson(join(out, 'completed.json'))
    await writeFile(join(out, 'completed.json'), runner.json({ ...terminal, status: 'SCHEDULE_COMPLETED' }))
    await assert.rejects(() => analyze(out), /TERMINAL/)
  } finally { await close(f.server); await rm(out, { recursive: true, force: true }) }
})

test('later HTTP, reset, malformed JSON and missing usage remain visible; real execution needs its existing setup', async () => {
  const out = await mkdtemp(join(tmpdir(), 'hswm-w1-full-failures-')), zero = await mkdtemp(join(tmpdir(), 'hswm-w1-full-zero-'))
  const f = await fixture({ laterFailures: true })
  try {
    await runner.prepare(out)
    await assert.rejects(() => runner.execute(out, { baseUrl: f.baseUrl, evidenceKind: 'OBSERVED_MODEL_HTTP', attestation: {} }), /DGX/)
    assert.equal(f.probes(), 0); assert.equal(f.calls(), 0)
    assert.equal((await executeFixture(out, f)).status, 'SCHEDULE_COMPLETED')
    const summary: any = await analyze(out)
    assert.equal(summary.completed_records, 2784)
    assert.equal(summary.observations.filter((row: any) => row.complete && !row.valid).length, 3)
    assert.equal(summary.observations[387].prompt_tokens, null)
    assert.ok(summary.observations.every((row: any) => row.reasoning_tokens === null))
    const bytesPath = join(out, 'http/0400.response.json'), saved = await readFile(bytesPath)
    await writeFile(bytesPath, Buffer.concat([saved, Buffer.from(' ')]))
    await assert.rejects(() => analyze(out), /RESPONSE_BYTES/)
    await runner.prepare(zero)
    assert.equal((await executeFixture(zero, f, 0)).attempted, 0)
    const empty: any = await analyze(zero)
    assert.equal(empty.missing_results, 2784)
    assert.equal(empty.arms.E0.all.cost.prompt_tokens.sum_reported, null)
  } finally { await close(f.server); await Promise.all([rm(out, { recursive: true, force: true }), rm(zero, { recursive: true, force: true })]) }
})
