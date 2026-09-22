import assert from 'node:assert/strict'
import { createServer, type Server } from 'node:http'
import test from 'node:test'
import { mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const runner = await import('../../_research/local_semantic_execution_v1/runner.mts')
const analyzer = await import('../../_research/local_semantic_execution_v1/analyze.mts')

type FixtureMode = 'E0' | 'E1' | 'E2'
type FixtureCase = { readonly caseId: string; readonly expected: { readonly base: 0 | 1; readonly context_flip: 0 | 1; readonly exception_flip: 0 | 1; readonly answer: 0 | 1 } }

const fixtureCases = new Map<string, FixtureCase>(runner.domain.localSemanticCases.map((entry: FixtureCase) => [entry.caseId, entry]))
const response = (mode: FixtureMode, expected: FixtureCase['expected'], ordinal: number, omitUsage = false) => {
  if (mode === 'E0') {
    const candidates = ordinal === 0
      ? [{ token: '0', logprob: Math.log(0.9) }]
      : expected.answer === 1
        ? [{ token: '0', logprob: Math.log(0.1) }, { token: '1', logprob: Math.log(0.9) }]
        : [{ token: '0', logprob: Math.log(0.9) }, { token: '1', logprob: Math.log(0.1) }]
    return { model: 'qwen3-4b-real', choices: [{ finish_reason: 'stop', message: { content: String(expected.answer) }, logprobs: { content: [{ top_logprobs: candidates }] } }], ...(omitUsage ? {} : { usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }) }
  }
  if (mode === 'E1') {
    return { model: 'qwen3-4b-real', choices: [{ finish_reason: 'stop', message: { content: JSON.stringify({ answer: ordinal === 1 ? true : expected.answer }) } }], ...(omitUsage ? {} : { usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }) }
  }
  return { model: 'qwen3-4b-real', choices: [{ finish_reason: 'stop', message: { content: JSON.stringify({
    base: ordinal === 2 ? (expected.base ^ 1) : expected.base,
    context_flip: expected.context_flip,
    exception_flip: expected.exception_flip,
    answer: expected.answer
  }) } }], ...(omitUsage ? {} : { usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }) }
}

const makeFixtureServer = async (failures: Readonly<{ http500?: number; reset?: number; nonJson?: number; missingUsage?: number }> = {}) => {
  let completionOrdinal = 0
  const server = createServer(async (request, reply) => {
    const chunks: Uint8Array[] = []
    for await (const chunk of request) chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk)
    const body = Buffer.concat(chunks).toString('utf8')
    const send = (status: number, value: unknown) => {
      reply.writeHead(status, { 'content-type': 'application/json' })
      reply.end(JSON.stringify(value))
    }
    if (request.method === 'GET' && request.url === '/v1/models') return send(200, { data: [{ id: 'qwen3-4b-real' }] })
    if (request.method === 'POST' && request.url === '/tokenize') {
      const input = JSON.parse(body) as { prompt: string }
      return send(200, { tokens: input.prompt === '0' ? [15] : input.prompt === '1' ? [16] : [] })
    }
    if (request.method !== 'POST' || request.url !== '/v1/chat/completions') return send(404, { error: 'not found' })
    const schedule = runner.domain.localSemanticSchedule[completionOrdinal]
    assert.ok(schedule, 'fixture server received more than 384 scheduled requests')
    const payload = JSON.parse(body) as { messages?: Array<{ content?: string }> }
    const messageText = payload.messages?.map(message => message.content ?? '').join('\n') ?? ''
    assert.equal(messageText.includes('expected'), false, 'evaluator labels must not enter model messages')
    const expected = fixtureCases.get(schedule.caseId)?.expected
    assert.ok(expected, 'fixture expectation must be selected by schedule, not request contents')
    completionOrdinal += 1
    if (schedule.ordinal === failures.http500) return send(500, { error: 'fixture HTTP failure' })
    if (schedule.ordinal === failures.reset) return reply.destroy()
    if (schedule.ordinal === failures.nonJson) {
      reply.writeHead(200, { 'content-type': 'application/json' })
      return reply.end('not-json')
    }
    return send(200, response(schedule.mode as FixtureMode, expected, schedule.ordinal, schedule.ordinal === failures.missingUsage))
  })
  await new Promise<void>((resolve, reject) => server.listen(0, '127.0.0.1', error => error ? reject(error) : resolve()))
  const address = server.address()
  assert.ok(address && typeof address === 'object')
  return { server, baseUrl: `http://127.0.0.1:${address.port}/`, completionCount: () => completionOrdinal }
}

const close = async (server: Server) => new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
const summaryOf = async (out: string) => analyzer.analyze(out) as Promise<{ status: string; evidence_kind: string; terminal_receipt_present: boolean; planned: number; attempted: number; completed_records: number; missing_results: number; modes: Record<FixtureMode, Record<string, any>> }>

await test('records full fixture-only census, preserves denominators, and rejects byte drift', async () => {
  const out = await mkdtemp(join(tmpdir(), 'hswm-local-semantic-fixture-'))
  const fixture = await makeFixtureServer()
  try {
    const prepared = await runner.prepare(out)
    assert.deepEqual({ cases: prepared.cases, requests: prepared.requests }, { cases: 128, requests: 384 })
    const plan = await runner.verifyPlan(out)
    assert.equal(plan.frames.length, 128)
    for (const frame of plan.frames) assert.equal(JSON.stringify(frame.input).includes('expected'), false)
    for (const caseId of fixtureCases.keys()) {
      const frames = plan.frames.filter((frame: { caseId: string }) => frame.caseId === caseId)
      assert.equal(frames.length, 1)
      const scheduled = plan.schedule.filter((entry: { caseId: string }) => entry.caseId === caseId)
      assert.equal(scheduled.length, 3)
      const frameInputs = scheduled.map((entry: { request: { messages: Array<{ content: string }> } }) => entry.request.messages[1]!.content.split('\n')[0])
      assert.equal(new Set(frameInputs).size, 1, 'all E0/E1/E2 calls for a case receive the same serialized frame input')
    }
    const completed = await runner.execute(out, { baseUrl: fixture.baseUrl, evidenceKind: 'FIXTURE_ONLY', attestation: { fixture: true } })
    assert.equal(completed.status, 'SCHEDULE_COMPLETED')
    assert.equal(fixture.completionCount(), 384)
    const summary = await summaryOf(out)
    assert.equal(summary.evidence_kind, 'FIXTURE_ONLY')
    assert.equal(summary.planned, 384)
    assert.equal(summary.attempted, 384)
    assert.equal(summary.completed_records, 384)
    assert.equal(summary.missing_results, 0)
    for (const mode of ['E0', 'E1', 'E2'] as const) assert.equal(summary.modes[mode].scheduled, 128)
    assert.equal(summary.modes.E0.missing, 0)
    assert.equal(summary.modes.E1.missing, 0)
    assert.equal(summary.modes.E2.missing, 0)
    assert.equal(summary.modes.E0.valid, 127)
    assert.equal(summary.modes.E0.correct, 127)
    assert.equal(summary.modes.E0.invalid, 1, 'E0 missing candidate remains an invalid denominator member')
    assert.equal(summary.modes.E1.valid, 127)
    assert.equal(summary.modes.E1.correct, 127)
    assert.equal(summary.modes.E1.invalid, 1, 'E1 invalid boolean remains an invalid denominator member')
    assert.equal(summary.modes.E2.correct, 128, 'E2 final answer remains correct despite one incorrect intermediate')
    assert.equal(summary.modes.E2.e2_intermediates_correct, 127, 'one E2 intermediate is wrong while its final answer remains correct')
    assert.equal(summary.modes.E2.intermediate_incorrect, 1)

    const requestPath = join(out, 'http', '0000.request.json')
    const originalRequest = await readFile(requestPath, 'utf8')
    await writeFile(requestPath, `${originalRequest} `)
    await assert.rejects(() => summaryOf(out), /REQUEST|DRIFT|HASH/i)
    await writeFile(requestPath, originalRequest)
    const responsePath = join(out, 'http', '0000.response.json')
    const originalResponse = await readFile(responsePath, 'utf8')
    await writeFile(responsePath, `${originalResponse} `)
    await assert.rejects(() => summaryOf(out), /RESPONSE|DRIFT|HASH/i)
    await writeFile(responsePath, originalResponse)
    const completedPath = join(out, 'completed.json')
    const originalCompleted = await readFile(completedPath, 'utf8')
    await unlink(completedPath)
    const unterminated = await summaryOf(out)
    assert.equal(unterminated.status, 'INCOMPLETE_OR_UNTERMINATED_CENSUS')
    assert.equal(unterminated.terminal_receipt_present, false)
    assert.equal(unterminated.completed_records, 384, 'all result records remain present when only the terminal receipt is absent')
    assert.equal(unterminated.missing_results, 0)
    await writeFile(completedPath, originalCompleted)
    const alteredTerminal = JSON.parse(originalCompleted) as { attempted: number }
    alteredTerminal.attempted = 383
    await writeFile(completedPath, JSON.stringify(alteredTerminal, null, 2) + '\n')
    await assert.rejects(() => summaryOf(out), /TERMINAL_RECEIPT_MISMATCH/)
    await writeFile(completedPath, originalCompleted)
    await assert.rejects(() => runner.execute(out, { baseUrl: fixture.baseUrl, evidenceKind: 'FIXTURE_ONLY', attestation: { fixture: true } }), /EEXIST|exist/i)
  } finally {
    await close(fixture.server)
    await rm(out, { recursive: true, force: true })
  }
})

await test('refuses a changed prepared plan and marks a zero-wall run incomplete with all scheduled denominators missing', async () => {
  const driftOut = await mkdtemp(join(tmpdir(), 'hswm-local-semantic-drift-'))
  const zeroOut = await mkdtemp(join(tmpdir(), 'hswm-local-semantic-zero-'))
  const observedOut = await mkdtemp(join(tmpdir(), 'hswm-local-semantic-observed-'))
  const fixture = await makeFixtureServer()
  try {
    await runner.prepare(driftOut)
    const planPath = join(driftOut, 'plan.json')
    const plan = JSON.parse(await readFile(planPath, 'utf8')) as { protocol_sha256: string }
    plan.protocol_sha256 = '0'.repeat(64)
    await writeFile(planPath, JSON.stringify(plan, null, 2) + '\n')
    await assert.rejects(() => runner.verifyPlan(driftOut), /PLAN_OR_SOURCE_DRIFT/)

    await runner.prepare(observedOut)
    await assert.rejects(
      () => runner.execute(observedOut, {
        baseUrl: fixture.baseUrl,
        evidenceKind: 'OBSERVED_MODEL_HTTP',
        attestation: { base_url: fixture.baseUrl },
        wallMs: 0
      }),
      /Use the documented DGX hswm-run output directory/
    )
    await assert.rejects(() => readFile(join(observedOut, 'started.json')), { code: 'ENOENT' })

    await runner.prepare(zeroOut)
    const completed = await runner.execute(zeroOut, { baseUrl: fixture.baseUrl, evidenceKind: 'FIXTURE_ONLY', attestation: { fixture: true }, wallMs: 0 })
    assert.equal(completed.status, 'WALL_BUDGET_STOPPED')
    assert.equal(completed.attempted, 0)
    assert.equal(fixture.completionCount(), 0)
    const summary = await summaryOf(zeroOut)
    assert.notEqual(summary.status, 'SUCCESS')
    assert.equal(summary.planned, 384)
    assert.equal(summary.attempted, 0)
    assert.equal(summary.missing_results, 384)
    for (const mode of ['E0', 'E1', 'E2'] as const) {
      assert.equal(summary.modes[mode].scheduled, 128)
      assert.equal(summary.modes[mode].missing, 128)
      assert.equal(summary.modes[mode].accuracy, 0)
    }
  } finally {
    await close(fixture.server)
    await Promise.all([rm(driftOut, { recursive: true, force: true }), rm(zeroOut, { recursive: true, force: true }), rm(observedOut, { recursive: true, force: true })])
  }
})

await test('keeps HTTP, transport, malformed-body, and absent-usage failures visible in the fixture census', async () => {
  const out = await mkdtemp(join(tmpdir(), 'hswm-local-semantic-failure-fixture-'))
  const fixture = await makeFixtureServer({ http500: 0, reset: 1, nonJson: 2, missingUsage: 3 })
  try {
    await runner.prepare(out)
    const completed = await runner.execute(out, { baseUrl: fixture.baseUrl, evidenceKind: 'FIXTURE_ONLY', attestation: { fixture: true } })
    assert.equal(completed.status, 'SCHEDULE_COMPLETED')
    assert.equal(fixture.completionCount(), 384)
    const summary = await summaryOf(out)
    assert.equal(summary.planned, 384)
    assert.equal(summary.attempted, 384)
    assert.equal(summary.completed_records, 384)
    assert.equal(summary.missing_results, 0)
    assert.equal(summary.modes.E0.invalid, 1, 'HTTP 500 stays in E0 denominator')
    assert.equal(summary.modes.E1.invalid, 1, 'transport reset stays in E1 denominator')
    assert.equal(summary.modes.E2.invalid, 1, 'non-JSON body stays in E2 denominator')
    assert.equal(summary.modes.E1.cost.prompt_tokens.unreported_records, 2, 'reset and valid missing-usage response are not silently reported as zero')
    assert.equal(summary.modes.E1.cost.completion_tokens.unreported_records, 2)
  } finally {
    await close(fixture.server)
    await rm(out, { recursive: true, force: true })
  }
})
