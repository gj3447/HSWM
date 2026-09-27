import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';
import { localSemanticCases } from '../../src/hswm/effect-runtime/src/local-semantic-execution-domain.ts';
import { evaluate, validateRequest } from '../../_research/inspect_comparison_v1/hswm_bridge.mts';

test('native E1 HTTP path retains invalid outputs, omits labels, and records usage', async () => {
  let reply = '{"answer":1}', count = 0, captured: any;
  const server = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    captured = JSON.parse(body); count++;
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ model: 'fixture-model', choices: [{ finish_reason: 'stop', message: { content: reply } }],
      usage: { prompt_tokens: 8, completion_tokens: 4, total_tokens: 12 } }));
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const address = server.address(); assert(address && typeof address === 'object');
    const request = { input: localSemanticCases[0]!.input, relation_text: 'Changed relation only',
      execution: { base_url: `http://127.0.0.1:${address.port}`, model: 'fixture-model', max_tokens: 32, timeout_seconds: 5, seed: 0 } };
    const good = await evaluate(request);
    assert.equal(good.valid, true); assert.equal(good.answer, '1'); assert.equal(count, 1); assert.equal(good.usage?.total_tokens, 12);
    const input = JSON.parse(captured.messages[1].content.split('\n')[0]);
    assert.deepEqual(input, { ...request.input, relation: { ...request.input.relation, semanticText: request.relation_text } });
    assert(!JSON.stringify(captured).includes('expected')); assert(!JSON.stringify(captured).includes('caseId'));
    reply = '{"answer":0,"answer":1}';
    const bad = await evaluate(request);
    assert.equal(bad.valid, false); assert.equal(bad.error_kind, 'DUPLICATE_KEY'); assert.equal(count, 2);
    assert.throws(() => validateRequest({ ...request, target: '1' })); assert.equal(count, 2);
    assert.throws(() => validateRequest({ ...request, execution: { ...request.execution, max_tokens: 0 } }));
  } finally { server.close(); }
});

test('fixture export keeps heldout disjoint and oracle meaning out of optimizer inputs', async () => {
  const root = await mkdtemp(join(tmpdir(), 'hswm-inspect-fixture-'));
  const destination = join(root, 'new-run');
  try {
    execFileSync(process.execPath, ['_research/inspect_comparison_v1/prepare_fixture.mts', destination], { stdio: 'pipe' });
    const baseline = (await readFile(join(destination, 'baseline.txt'), 'utf8')).trim();
    const records = async (name: string) => (await readFile(join(destination, name), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const train = await records('train.jsonl'), heldout = await records('heldout.jsonl');
    assert.equal(train.length, 12); assert.equal(heldout.length, 20);
    assert(train.every(row => row.split === 'train'));
    assert(heldout.every(row => row.split === 'heldout' && !train.some(t => t.id === row.id)));
    assert([...train, ...heldout].every(row => row.input.relation.semanticText === baseline));
    assert.notEqual(baseline, localSemanticCases[0]!.input.relation.semanticText);
    assert.throws(() => execFileSync(process.execPath, ['_research/inspect_comparison_v1/prepare_fixture.mts', destination], { stdio: 'pipe' }));
  } finally { await rm(root, { recursive: true }); }
});
