/** Full W1 v2 research driver; original pilot gates transformed execution. Private, append-only records; no graph writes. */
import { readFile, writeFile, mkdir, readdir, appendFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, join, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

export const root = fileURLToPath(new URL('../../', import.meta.url));
export const study = '_research/local_semantic_execution_w1_v2';
const dist = resolve(process.env.HSWM_RESEARCH_RUNTIME_DIST ?? join(root, 'src/hswm/effect-runtime/dist'));
export const domain = await import(pathToFileURL(join(dist, 'local-semantic-w1-full-domain.js')).href);
export const originalDomain = await import(pathToFileURL(join(dist, 'local-semantic-execution-domain.js')).href);
export const decision = await import(pathToFileURL(join(dist, 'semantic-decision-domain.js')).href);
import { attest as attestOriginal, protocol as originalProtocol } from '../local_semantic_execution_v1/runner.mts';
import { parseResponse } from '../local_semantic_execution_v1/analyze.mts';
export const protocol = JSON.parse(await readFile(join(root, study, 'protocol.v2.json'), 'utf8'));
export const sha = (bytes: string | Uint8Array) => createHash('sha256').update(bytes).digest('hex');
export const json = (value: unknown) => JSON.stringify(value, null, 2) + '\n';
export const saveNew = (path: string, value: unknown) => writeFile(path, json(value), { flag: 'wx', mode: 0o600 });
export const readJson = async (path: string) => JSON.parse(await readFile(path, 'utf8'));
if (JSON.stringify(protocol.model) !== JSON.stringify(originalProtocol.model)) throw new Error('MODEL_CONTRACT_CHANGED_REQUIRES_VERSIONED_ATTESTOR');
const effectVersion = createRequire(join(dist, 'index.js'))('effect/package.json').version;
const sourcePaths = [
  `${study}/protocol.v2.json`, `${study}/runner.mts`, `${study}/analyze.mts`, `${study}/README.md`, `${study}/launch.sh`,
  'src/hswm/effect-runtime/src/local-semantic-execution-domain.ts',
  'src/hswm/effect-runtime/src/local-semantic-w1-full-domain.ts',
  'tests/effect-runtime/local-semantic-w1-full-domain.test.ts',
  'tests/research/local-semantic-w1-full-analysis.test.mts',
  'tests/research/local-semantic-w1-full-instrument.test.mts',
  '_research/local_semantic_execution_v1/runner.mts',
  '_research/local_semantic_execution_v1/analyze.mts',
  '_research/local_semantic_execution_v1/protocol.v1.json',
  '_research/hswm_deep_research_v1/protocol.v1.json',
  'src/hswm/effect-runtime/src/semantic-decision-domain.ts',
  'tests/effect-runtime/local-semantic-execution-domain.test.ts',
  'tests/research/local-semantic-execution-instrument.test.mts',
  'src/hswm/effect-runtime/package-lock.json',
  '_research/jev_principles_v1/support/domain.mts'
];
export async function sourcePins() {
  for (const inherited of [protocol.inherited_protocol, protocol.design_source]) {
    if (sha(await readFile(join(root, inherited.path))) !== inherited.sha256) throw new Error('INHERITED_PROTOCOL_DRIFT');
  }
  const sources = await Promise.all(sourcePaths.map(async path => ({ path, sha256: sha(await readFile(join(root, path))) })));
  const compiled = await Promise.all(['local-semantic-w1-full-domain.js','local-semantic-execution-domain.js', 'semantic-decision-domain.js'].map(async name => ({ name, sha256: sha(await readFile(join(dist, name))) })));
  return { sources, compiled, node: process.version, effect: effectVersion,
    dependency_identity: 'LOCKFILE_AND_EFFECT_VERSION_NOT_COMPLETE_INSTALLED_DEPENDENCY_TREE' };
}
export function requestFor(item: any) {
  const entry = domain.fullW1Cases.find((c: any) => c.caseId === item.caseId);
  if (!entry) throw new Error('UNKNOWN_SCHEDULE_CASE');
  const mode = item.mode;
  const common = { model: protocol.model.served_name, temperature: protocol.generation.temperature,
    seed: protocol.generation.seed, chat_template_kwargs: { enable_thinking: protocol.generation.enable_thinking },
    messages: [{ role: 'system', content: protocol.system },
      { role: 'user', content: entry.inputJson + '\n' + domain.fullW1ModeInstructions(entry,mode) }],
    max_tokens: protocol.generation.max_tokens[mode] };
  return mode === 'E0' ? { ...common, allowed_token_ids: protocol.model.candidate_token_ids, logprobs: true, top_logprobs: 20 }
    : { ...common, response_format: { type: 'json_schema', json_schema: { name: `w1_${mode}`, strict: true, schema: originalDomain.localSemanticModeSchemas[mode] } } };
}
export function makePlan(pins: any) {
  return {
    schema_version: 'hswm-local-semantic-full-w1-plan/v2', evidence_kind: 'PLANNED_NOT_OBSERVED',
    protocol_sha256: sha(json(protocol)), pins, transform_manifest: domain.fullW1Transforms, rename_bijection: domain.fullW1RenameBijection, role_exchange_sensitivity: { cases: 128, changed_input: domain.fullW1RoleExchangeChangedInputCount, changed_answer: domain.fullW1RoleExchangeChangedCount, changed_intermediate: domain.fullW1RoleExchangeChangedIntermediateCount }, sentinels: domain.fullW1Sentinels, claim_ceiling: protocol.claim_ceiling,
    reference_sha256: sha(json(domain.fullW1Cases.map((c: any) => ({ caseId: c.caseId, expected: c.expected })))),
    frames: domain.fullW1Cases.map((c: any) => ({ caseId: c.caseId, familyIndex: c.familyIndex,
      familyName: c.familyName, baseCaseId: c.baseCaseId, transform: c.transform, input: c.input, inputJson: c.inputJson, frame_sha256: sha(c.inputJson),
      relation_sha256: sha(JSON.stringify(c.input.relation)) })),
    schedule: domain.fullW1Schedule.map((item: any) => ({ ...item, request: requestFor(item), request_sha256: sha(JSON.stringify(requestFor(item))) }))
  };
}
export async function prepare(out: string) {
  if (!isAbsolute(out)) throw new Error('Use an absolute private output directory');
  await mkdir(out, { recursive: true, mode: 0o700 });
  if ((await readdir(out)).length !== 0) throw new Error('PREPARE_REQUIRES_EMPTY_DIRECTORY');
  const plan = makePlan(await sourcePins());
  await saveNew(join(out, 'plan.json'), plan);
  // Evaluator custody: separate file, never sent over HTTP. The original-pilot gate uses the pinned in-memory oracle only for its declared stopping rule.
  await saveNew(join(out, 'reference.json'), domain.fullW1Cases.map((c: any) => ({ caseId: c.caseId, expected: c.expected })));
  return { status: 'PREPARED_NOT_RUN', cases: plan.frames.length, requests: plan.schedule.length, plan_sha256: sha(json(plan)) };
}
export async function verifyPlan(out: string) {
  const plan = await readJson(join(out, 'plan.json'));
  if (json(plan) !== json(makePlan(await sourcePins()))) throw new Error('PLAN_OR_SOURCE_DRIFT: prepare a fresh directory after changes');
  return plan;
}
export const attest = attestOriginal;
async function preflight(baseUrl: string, out: string) {
  const steps = [{ name: 'models', path: '/v1/models', body: null },
    ...['0', '1'].map(bit => ({ name: `token-${bit}`, path: '/tokenize', body: { model: protocol.model.served_name, prompt: bit, add_special_tokens: false } }))];
  const results = [];
  for (const step of steps) {
    const start = performance.now();
    const response = await fetch(new URL(step.path, baseUrl), { method: step.body ? 'POST' : 'GET', redirect: 'error',
      ...(step.body ? { headers: { 'content-type': 'application/json' }, body: JSON.stringify(step.body) } : {}),
      signal: AbortSignal.timeout(protocol.budget.preflight_seconds * 1000) });
    const raw = await response.text();
    await writeFile(join(out, `preflight-${step.name}.json`), raw, { flag: 'wx', mode: 0o600 });
    const value = JSON.parse(raw);
    if (!response.ok) throw new Error(`PREFLIGHT_HTTP_${response.status}`);
    if (step.name === 'models') {
      if (!value.data?.some((m: any) => m.id === protocol.model.served_name)) throw new Error('SERVED_MODEL_NOT_FOUND');
    } else {
      const expected = protocol.model.candidate_token_ids[Number(step.name.at(-1))];
      if (JSON.stringify(value.tokens) !== JSON.stringify([expected])) throw new Error('CANDIDATE_TOKEN_MISMATCH');
    }
    results.push({ name: step.name, status: response.status, elapsed_ms: performance.now() - start, response_sha256: sha(raw) });
  }
  return results;
}
export async function execute(out: string, options: { baseUrl: string; evidenceKind: 'OBSERVED_MODEL_HTTP' | 'FIXTURE_ONLY'; attestation: any; attestationPath?: string; wallMs?: number }) {
  if (!['FIXTURE_ONLY','OBSERVED_MODEL_HTTP'].includes(options.evidenceKind)) throw new Error('UNKNOWN_EVIDENCE_KIND');
  if (options.wallMs !== undefined && (!Number.isFinite(options.wallMs) || options.wallMs < 0)) throw new Error('INVALID_FIXTURE_WALL_BUDGET');
  const plan = await verifyPlan(out);
  const endpoint = new URL(options.baseUrl);
  if (endpoint.protocol !== 'http:' || endpoint.hostname !== '127.0.0.1' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash || endpoint.pathname !== '/') throw new Error('Only explicit loopback transport is supported');
  if (options.evidenceKind === 'OBSERVED_MODEL_HTTP') {
    if (process.env.HSWM_EXECUTION_TIER !== 'dgx-nvme' || resolve(process.env.HSWM_OUTPUT_ROOT ?? '') !== resolve(out)) throw new Error('Use the documented DGX hswm-run output directory');
    if (options.wallMs !== undefined || options.baseUrl !== options.attestation.base_url) throw new Error('OBSERVED_RUN_BUDGET_OR_ENDPOINT_OVERRIDE');
    if (!options.attestationPath || json(await attest(options.attestationPath)) !== json(options.attestation)) throw new Error('ATTESTATION_PATH_OR_VALUE_MISMATCH');
  }
  // wx makes a started or failed run non-resumable. A rerun needs a new directory and remains a separate observation.
  await saveNew(join(out, 'started.json'), { time: new Date().toISOString(), evidence_kind: options.evidenceKind, plan_sha256: sha(json(plan)) });
  // Reserve every receipt sink before the first probe; existing bytes must never be appended to a new run.
  await mkdir(join(out, 'http'), { mode: 0o700 });
  for (const name of ['attempts.jsonl', 'results.jsonl']) await writeFile(join(out, name), '', { flag: 'wx', mode: 0o600 });
  const checks = await preflight(options.baseUrl, out);
  await saveNew(join(out, 'freeze.json'), { evidence_kind: options.evidenceKind, plan_sha256: sha(json(plan)),
    source_pins: plan.pins, attestation: options.attestation, preflight: checks, frozen_at: new Date().toISOString(),
    attestation_boundary: 'Artifact bytes checked locally; live-engine association is operator-declared, not hardware attestation.' });
  const started = performance.now();
  let sent = 0;
  let pilotFailed = false;
  const pilotCorrect: Record<string, number> = { E0: 0, E1: 0, E2: 0 };
  const cases = new Map(domain.fullW1Cases.map((c: any) => [c.caseId,c]));
  for (const item of plan.schedule) {
    if (item.ordinal === 384 && !Object.values(pilotCorrect).some(n => n ===128)) { pilotFailed = true; break; }
    const remaining = (options.wallMs ?? protocol.budget.wall_seconds * 1000) - (performance.now() - started);
    if (remaining <= 0) break;
    const body = JSON.stringify(item.request), name = String(item.ordinal).padStart(4, '0');
    await writeFile(join(out, 'http', `${name}.request.json`), body, { flag: 'wx', mode: 0o600 });
    const start = performance.now();
    // Persist intent before send, so a crash cannot silently remove an attempted request from accounting.
    await appendFile(join(out, 'attempts.jsonl'), JSON.stringify({ ordinal: item.ordinal, caseId: item.caseId, mode: item.mode, request_sha256: sha(body), started_at: new Date().toISOString() }) + '\n', { mode: 0o600 });
    sent++;
    let result: any;
    try {
      const response = await fetch(new URL('/v1/chat/completions', options.baseUrl), {
        method: 'POST', redirect: 'error', headers: { 'content-type': 'application/json' }, body,
        signal: AbortSignal.timeout(Math.max(1, Math.floor(Math.min(protocol.budget.request_seconds * 1000, remaining)))) });
      const raw = await response.text();
      await writeFile(join(out, 'http', `${name}.response.json`), raw, { flag: 'wx', mode: 0o600 });
      result = { status: response.status, response_sha256: sha(raw) };
      if (item.ordinal < 384 && response.ok) {
        try {
          const parsed = parseResponse(item.mode, JSON.parse(raw));
          const expected = (cases.get(item.caseId) as any).expected;
          if (parsed.valid && parsed.output.answer === expected.answer) pilotCorrect[item.mode]++;
        } catch { /* malformed original response cannot pass the pilot */ }
      }
    } catch (error) {
      result = { status: null, response_sha256: null, transport_failure: error instanceof Error ? error.name : 'UNKNOWN_TRANSPORT_ERROR' };
    }
    await appendFile(join(out, 'results.jsonl'), JSON.stringify({ ordinal: item.ordinal, request_sha256: sha(body), ...result, elapsed_ms: performance.now() - start }) + '\n', { mode: 0o600 });
  }
  const completed = { status: pilotFailed ? 'ORIGINAL_PILOT_FAILED' : sent === plan.schedule.length ? 'SCHEDULE_COMPLETED' : 'WALL_BUDGET_STOPPED',
    evidence_kind: options.evidenceKind, attempted: sent, planned: plan.schedule.length, elapsed_ms: performance.now() - started };
  await saveNew(join(out, 'completed.json'), completed);
  return completed;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command, directory, attestationPath] = process.argv.slice(2);
  if (!directory || !isAbsolute(directory)) throw new Error('Usage: node runner.mts prepare ABS_PRIVATE_DIR | run ABS_PRIVATE_DIR ABS_ATTESTATION_JSON');
  if (command === 'prepare') console.log(JSON.stringify(await prepare(directory)));
  else if (command === 'run' && attestationPath) {
    const a = await readJson(resolve(attestationPath));
    console.log(JSON.stringify(await execute(directory, { baseUrl: a.base_url, evidenceKind: 'OBSERVED_MODEL_HTTP', attestation: a, attestationPath: resolve(attestationPath) })));
  } else throw new Error('Unknown command or missing attestation');
}
