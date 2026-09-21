import { mkdir, writeFile } from 'node:fs/promises';
const out = process.env.HSWM_OUTPUT_ROOT;
if (!out || process.env.HSWM_EXECUTION_TIER !== 'dgx-nvme') throw new Error('Use hswm-run');
await mkdir(out, { recursive: true });
const requests = [
  { path: '/tokenize', body: { model: 'qwen3-4b-real', prompt: '0', add_special_tokens: false } },
  { path: '/tokenize', body: { model: 'qwen3-4b-real', prompt: '1', add_special_tokens: false } },
  { path: '/v1/chat/completions', body: { model: 'qwen3-4b-real', temperature: 0, max_tokens: 1,
    logprobs: true, top_logprobs: 20, allowed_token_ids: [15, 16], chat_template_kwargs: { enable_thinking: false },
    messages: [{ role: 'user', content: 'Return 1 if both flags are true, else 0. Flag A is true. Flag B is false. Return only 0 or 1.' }] } }
];
await writeFile(out + '/protocol.json', JSON.stringify({ scope: 'capability probe only; excluded from evaluation', requests }, null, 2), { flag: 'wx' });
for (let i = 0; i < requests.length; i++) {
  const r = requests[i], start = performance.now();
  const response = await fetch('http://127.0.0.1:8001' + r.path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(r.body), signal: AbortSignal.timeout(60000) });
  const body = await response.text();
  await writeFile(out + `/response-${i}.json`, body, { flag: 'wx' });
  console.log(JSON.stringify({ i, status: response.status, latency_ms: performance.now() - start, body: JSON.parse(body) }));
  if (!response.ok) process.exitCode = 1;
}
