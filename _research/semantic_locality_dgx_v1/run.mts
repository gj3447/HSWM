/** Bounded inference experiment; no canonical writes, retries or learned revisions. */
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, appendFile } from 'node:fs/promises';
import { join } from 'node:path';
const { Effect } = createRequire(new URL('../../src/hswm/effect-runtime/package.json', import.meta.url))('effect');
const sha = (x: string) => createHash('sha256').update(x).digest('hex');
const arms = ['full', 'reordered', 'role_swap', 'meaning_removed', 'restored'] as const;
const relation = 'Permit the transfer only when the sender is cleared and the recipient is ready. During maintenance, recipient readiness is not required; sender clearance is still required. An active quarantine blocks every transfer, including during maintenance.';
const system = 'Interpret only the supplied local relation and facts. Return JSON with decision (permit or deny) and confidence (a number from 0 to 1 estimating whether your decision is correct). No commentary. When information is missing, still choose one decision and express uncertainty. No tools.';
const tasks = Array.from({ length: 16 }, (_, id) => {
  const sender = Boolean(id & 1), recipient = Boolean(id & 2), quarantine = Boolean(id & 4), maintenance = Boolean(id & 8);
  const expected = sender && !quarantine && (maintenance || recipient) ? 'permit' : 'deny';
  return arms.map(arm => {
    let roles = [
      { role: 'sender', type: 'endpoint', id: 'node-k', facts: { cleared: arm === 'role_swap' ? recipient : sender } },
      { role: 'recipient', type: 'endpoint', id: 'node-z', facts: { ready: arm === 'role_swap' ? sender : recipient } }
    ];
    if (arm === 'reordered') roles = roles.toReversed();
    const input = JSON.stringify({ relation_uid: 'transfer-rule', revision: 1,
      meaning: arm === 'meaning_removed' ? 'No relation meaning is supplied.' : relation,
      roles, context: { mode: maintenance ? 'maintenance' : 'normal' }, exception: { active_quarantine: quarantine } });
    return { id, arm, expected, input, request_sha256: sha(system + '\n' + input) };
  });
}).flat().sort((a, b) => sha('fixed-order-20260920:' + a.id + ':' + a.arm).localeCompare(sha('fixed-order-20260920:' + b.id + ':' + b.arm)));
const protocol = {
  schema_version: 'hswm-local-semantic-probe/v1', model: 'qwen3.6-35b-a3b', cases: 16, requests: 80,
  seed: 'fixed-order-20260920', arms, temperature: 0, max_tokens: 100, thinking: false,
  truth_rule: 'sender_cleared && !quarantine && (maintenance || recipient_ready)',
  outcome: 'Exhaustive finite authored truth table, computed before inference; not environmental ground truth.',
  estimand: 'Descriptive agreement with the original rule, per intervention; role_swap changes accessible facts, meaning_removed changes information and token count.',
  limits: ['Not equal-cost causal efficacy', 'Not an HSWM runtime integration or learning test', 'Restored is identical prompt re-input, not durable revision rollback', 'No Jev execution or Hyperon comparison', 'Confidence is verbalized correctness confidence, not Jev concentration', 'Small exhaustive synthetic family, no population calibration claim'],
  system, tasks
};
const io = <A>(f: () => Promise<A>) => Effect.tryPromise({ try: f, catch: (e: unknown) => e });
const main = Effect.gen(function* () {
  if (process.argv.includes('--protocol')) { console.log(JSON.stringify(protocol, null, 2)); return; }
  const out = process.env.HSWM_OUTPUT_ROOT;
  if (!out || process.env.HSWM_EXECUTION_TIER !== 'dgx-nvme') throw new Error('Run only with DGX hswm-run');
  yield* io(() => mkdir(out, { recursive: true }));
  const frozen = JSON.stringify(protocol, null, 2) + '\n';
  yield* io(() => writeFile(join(out, 'protocol.json'), frozen, { flag: 'wx' }));
  const runnerBytes = yield* io(() => readFile(new URL(import.meta.url), 'utf8'));
  const results: any[] = [];
  const start = new Date().toISOString();
  for (const t of tasks) {
    const begun = performance.now();
    const response = yield* io(() => fetch('http://127.0.0.1:8000/v1/chat/completions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(120000),
      body: JSON.stringify({ model: protocol.model, temperature: 0, max_tokens: protocol.max_tokens,
        chat_template_kwargs: { enable_thinking: false }, response_format: { type: 'json_object' },
        messages: [{ role: 'system', content: system }, { role: 'user', content: t.input }] })
    }));
    const raw = yield* io(() => response.text());
    yield* io(() => writeFile(join(out, `response-${t.id}-${t.arm}.json`), raw, { flag: 'wx' }));
    if (!response.ok) throw new Error(`HTTP ${response.status}; no automatic retry`);
    const envelope = JSON.parse(raw), content = envelope.choices?.[0]?.message?.content;
    let prediction: any = null;
    try { prediction = JSON.parse(content); } catch { /* invalid output is a measured failure */ }
    const valid = ['permit', 'deny'].includes(prediction?.decision) && typeof prediction?.confidence === 'number' && prediction.confidence >= 0 && prediction.confidence <= 1;
    const row = { id: t.id, arm: t.arm, expected: t.expected, request_sha256: t.request_sha256,
      response_sha256: sha(raw), valid, decision: prediction?.decision ?? null, confidence: valid ? prediction.confidence : null,
      correct: valid && prediction.decision === t.expected, latency_ms: performance.now() - begun,
      model_reported: envelope.model ?? null, fingerprint_reported: envelope.system_fingerprint ?? null,
      finish_reason: envelope.choices?.[0]?.finish_reason ?? null, usage: envelope.usage ?? null };
    results.push(row);
    yield* io(() => appendFile(join(out, 'observations.jsonl'), JSON.stringify(row) + '\n'));
    if (results.length % 10 === 0) console.log(JSON.stringify({ completed: results.length, total: tasks.length }));
  }
  const summary = { schema_version: 'hswm-local-semantic-probe-result/v1', start, finished: new Date().toISOString(),
    protocol_sha256: sha(frozen), runner_sha256: sha(runnerBytes), requests: results.length,
    arms: arms.map(arm => { const rows = results.filter(r => r.arm === arm); return { arm, n: rows.length,
      valid: rows.filter(r => r.valid).length, correct: rows.filter(r => r.correct).length,
      brier_correctness: rows.every(r => r.valid) ? rows.reduce((s, r) => s + (r.confidence - Number(r.correct)) ** 2, 0) / rows.length : null,
      prompt_tokens: rows.reduce((s, r) => s + (r.usage?.prompt_tokens ?? 0), 0), completion_tokens: rows.reduce((s, r) => s + (r.usage?.completion_tokens ?? 0), 0),
      usage_complete: rows.every(r => Number.isInteger(r.usage?.prompt_tokens) && Number.isInteger(r.usage?.completion_tokens)),
      mean_latency_ms: rows.reduce((s, r) => s + r.latency_ms, 0) / rows.length }; }),
    restored_disagreements: results.filter(r => r.arm === 'full').filter(r => r.decision !== results.find(x => x.arm === 'restored' && x.id === r.id)?.decision).length,
    claim_ceiling: 'FINITE_SYNTHETIC_LOCAL_INTERPRETATION_ONLY_NO_CR_FCL_PROMOTION' };
  yield* io(() => writeFile(join(out, 'summary.json'), JSON.stringify(summary, null, 2) + '\n', { flag: 'wx' }));
  console.log(JSON.stringify(summary));
});
Effect.runPromise(main).catch((e: unknown) => { console.error(String(e)); process.exitCode = 1; });
