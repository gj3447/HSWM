/** Replay saved HTTP evidence without model calls. Missing attempts never shrink denominators. */
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyPlan, domain, decision, protocol, sha, json, readJson, saveNew } from './runner.mts';

async function lines(path: string) {
  try { return (await readFile(path, 'utf8')).split('\n').filter(Boolean).map(line => JSON.parse(line)); }
  catch (e) { if ((e as NodeJS.ErrnoException).code === 'ENOENT') return []; throw e; }
}
const refusal = (reason: string) => ({ valid: false as const, reason });
const reported = (n: unknown): number | null => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0 ? n : null;
export function parseResponse(mode: string, value: any) {
  if (!value || value.model !== protocol.model.served_name || !Array.isArray(value.choices) || value.choices.length !== 1) return refusal('MODEL_OR_CHOICE_MISMATCH');
  const choice = value.choices[0];
  if (!choice || choice.message?.refusal || choice.message?.tool_calls?.length) return refusal('MODEL_REFUSAL_OR_TOOL_CALL');
  if (mode === 'E0') {
    if (!['stop', 'length'].includes(choice.finish_reason) || !['0', '1'].includes(choice.message?.content) || choice.logprobs?.content?.length !== 1) return refusal('INVALID_ONE_TOKEN_OUTPUT');
    const entries = choice.logprobs.content[0].top_logprobs;
    if (!Array.isArray(entries) || entries.some((e: any) => !e || typeof e.token !== 'string' || typeof e.logprob !== 'number')) return refusal('INVALID_LOGPROB_STRUCTURE');
    const readout = decision.binaryLogprobReadout(entries);
    return readout._tag === 'Left' ? refusal(readout.left.reason) : { valid: true as const, output: { answer: readout.right.bit }, p1: readout.right.p1, emitted_bit: Number(choice.message.content) };
  }
  if (choice.finish_reason !== 'stop' || typeof choice.message?.content !== 'string') return refusal('TRUNCATED_OR_MISSING_OUTPUT');
  const parsed = domain.parseLocalSemanticOutput(mode, choice.message.content);
  return parsed.valid ? parsed : refusal(parsed.refusal.reason);
}
export async function analyze(out: string) {
  const plan = await verifyPlan(out);
  const freeze = await readJson(join(out, 'freeze.json'));
  const started = await readJson(join(out, 'started.json'));
  if (freeze.plan_sha256 !== sha(json(plan)) || json(freeze.source_pins) !== json(plan.pins) || started.plan_sha256 !== freeze.plan_sha256 ||
      started.evidence_kind !== freeze.evidence_kind || !['FIXTURE_ONLY', 'OBSERVED_MODEL_HTTP'].includes(freeze.evidence_kind)) throw new Error('FREEZE_PLAN_MISMATCH');
  const referenceRaw = await readFile(join(out, 'reference.json'), 'utf8');
  if (sha(referenceRaw) !== plan.reference_sha256) throw new Error('REFERENCE_DIGEST_MISMATCH');
  const reference = new Map(JSON.parse(referenceRaw).map((c: any) => [c.caseId, c.expected]));
  const attempts = await lines(join(out, 'attempts.jsonl')), results = await lines(join(out, 'results.jsonl'));
  let terminal: any = null;
  try { terminal = await readJson(join(out, 'completed.json')); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e; }
  if (terminal && (terminal.evidence_kind !== freeze.evidence_kind || terminal.planned !== plan.schedule.length ||
      terminal.attempted !== attempts.length || typeof terminal.elapsed_ms !== 'number' || !Number.isFinite(terminal.elapsed_ms) || terminal.elapsed_ms < 0 ||
      terminal.status !== (attempts.length === plan.schedule.length ? 'SCHEDULE_COMPLETED' : 'WALL_BUDGET_STOPPED'))) throw new Error('TERMINAL_RECEIPT_MISMATCH');
  const index = (rows: any[], name: string) => {
    const m = new Map<number, any>();
    for (const r of rows) {
      const scheduled = plan.schedule[r.ordinal];
      if (!Number.isInteger(r.ordinal) || !scheduled || scheduled.ordinal !== r.ordinal || m.has(r.ordinal) || r.request_sha256 !== scheduled.request_sha256) throw new Error(`INVALID_${name}_ORDINAL_OR_REQUEST`);
      m.set(r.ordinal, r);
    }
    return m;
  };
  const attemptMap = index(attempts, 'ATTEMPT'), resultMap = index(results, 'RESULT');
  const rows: any[] = [];
  for (const item of plan.schedule) {
    const result = resultMap.get(item.ordinal), attempt = attemptMap.get(item.ordinal);
    if (result && !attempt) throw new Error('RESULT_WITHOUT_ATTEMPT');
    const base = { ordinal: item.ordinal, caseId: item.caseId, mode: item.mode,
      familyIndex: plan.frames.find((f: any) => f.caseId === item.caseId).familyIndex,
      attempted: !!attempt, complete: !!result, valid: false, correct: false,
      elapsed_ms: result?.elapsed_ms ?? null, prompt_tokens: null, completion_tokens: null, reasoning_tokens: null };
    if (attempt) {
      if (attempt.caseId !== item.caseId || attempt.mode !== item.mode) throw new Error('ATTEMPT_CASE_OR_MODE_MISMATCH');
      const body = await readFile(join(out, 'http', `${String(item.ordinal).padStart(4, '0')}.request.json`));
      if (sha(body) !== item.request_sha256) throw new Error('REQUEST_BYTES_MISMATCH');
    }
    if (!result) { rows.push({ ...base, reason: attempt ? 'ATTEMPT_WITHOUT_COMPLETION' : 'NOT_ATTEMPTED' }); continue; }
    if (typeof result.elapsed_ms !== 'number' || !Number.isFinite(result.elapsed_ms) || result.elapsed_ms < 0) throw new Error('INVALID_ELAPSED_TIME');
    if (result.response_sha256 === null) { rows.push({ ...base, reason: result.transport_failure ?? 'NO_RESPONSE' }); continue; }
    const raw = await readFile(join(out, 'http', `${String(item.ordinal).padStart(4, '0')}.response.json`), 'utf8');
    if (sha(raw) !== result.response_sha256) throw new Error('RESPONSE_BYTES_MISMATCH');
    let value: any;
    try { value = JSON.parse(raw); } catch { rows.push({ ...base, reason: 'INVALID_HTTP_JSON' }); continue; }
    const cost = { prompt_tokens: reported(value?.usage?.prompt_tokens), completion_tokens: reported(value?.usage?.completion_tokens),
      reasoning_tokens: reported(value?.usage?.completion_tokens_details?.reasoning_tokens) };
    if (!Number.isInteger(result.status) || result.status < 200 || result.status >= 300) { rows.push({ ...base, ...cost, reason: `HTTP_${result.status}` }); continue; }
    const parsed = parseResponse(item.mode, value);
    if (!parsed.valid) { rows.push({ ...base, ...cost, reason: parsed.reason }); continue; }
    const expected: any = reference.get(item.caseId), output = parsed.output;
    rows.push({ ...base, ...cost, valid: true, correct: output.answer === expected.answer,
      ...(item.mode === 'E0' ? { p1: parsed.p1, emitted_bit: parsed.emitted_bit, emitted_readout_agree: parsed.emitted_bit === output.answer } : {}),
      ...(item.mode === 'E2' ? {
        intermediates_correct: ['base', 'context_flip', 'exception_flip'].every(k => output[k] === expected[k]),
        intermediates_consistent: (output.base ^ output.context_flip ^ output.exception_flip) === output.answer
      } : {}) });
  }
  const totals = (subset: any[]) => {
    const n = subset.length, valid = subset.filter(r => r.valid).length, correct = subset.filter(r => r.correct).length;
    const measured = (field: string) => {
      const values = subset.map(r => r[field]).filter(n => n !== null);
      return { sum_reported: values.length ? values.reduce((sum, n) => sum + n, 0) : null,
        reported_records: values.length, unreported_records: n - values.length,
        status: values.length === n ? 'REPORTED_ALL' : values.length ? 'PARTIALLY_REPORTED' : 'UNREPORTED' };
    };
    return { scheduled: n, attempted: subset.filter(r => r.attempted).length, valid, correct,
      invalid: subset.filter(r => r.complete && !r.valid).length, missing: subset.filter(r => !r.complete).length,
      accuracy: correct / n, coverage: valid / n,
      refusals: subset.filter(r => r.reason).reduce((acc, r) => ({ ...acc, [r.reason]: (acc[r.reason] ?? 0) + 1 }), {}),
      e2_intermediates_correct: subset.filter(r => r.intermediates_correct).length,
      e2_intermediates_consistent: subset.filter(r => r.intermediates_consistent).length,
      intermediate_incorrect: subset.filter(r => r.intermediates_correct === false).length,
      e0_emitted_readout_disagreements: subset.filter(r => r.emitted_readout_agree === false).length,
      cost: { request_intents: subset.filter(r => r.attempted).length,
        request_accounting: 'Intent persisted before send; a crash can make actual network submission unknown.',
        elapsed_ms: measured('elapsed_ms'), prompt_tokens: measured('prompt_tokens'), completion_tokens: measured('completion_tokens'), reasoning_tokens: measured('reasoning_tokens'),
        read_tokens: 'UNINSTRUMENTED_COMPONENT_OF_PROMPT', update_tokens: 0, retry_tokens: 0,
        zero_basis: 'No update or retry model calls in this fixed instrument; never imputes missing usage.' } };
  };
  const modes = Object.fromEntries(protocol.modes.map((mode: string) => [mode, totals(rows.filter(r => r.mode === mode))]));
  return { schema_version: 'hswm-local-semantic-analysis/v1', evidence_kind: freeze.evidence_kind,
    status: terminal && results.length === plan.schedule.length ? 'COMPLETE_CENSUS' : 'INCOMPLETE_OR_UNTERMINATED_CENSUS',
    terminal_receipt_present: terminal !== null,
    planned: plan.schedule.length, attempted: attempts.length, completed_records: results.length,
    missing_results: plan.schedule.length - results.length, plan_sha256: sha(json(plan)),
    freeze_sha256: sha(await readFile(join(out, 'freeze.json'))), modes,
    families: Object.fromEntries([0, 1, 2, 3].map(family => [String(family), Object.fromEntries(protocol.modes.map((mode: string) => [mode, totals(rows.filter(r => r.familyIndex === family && r.mode === mode))]))])),
    pairwise_correct_count_delta: { E1_minus_E0: modes.E1.correct - modes.E0.correct, E2_minus_E0: modes.E2.correct - modes.E0.correct, E2_minus_E1: modes.E2.correct - modes.E1.correct },
    preflight: { requests: freeze.preflight.length, elapsed_ms: freeze.preflight.reduce((s: number, r: any) => s + r.elapsed_ms, 0), model_generation_calls: 0 },
    readiness: 'E03_NOT_ASSESSED_ORIGINAL_ONLY', claim_ceiling: protocol.claim_ceiling,
    limitations: ['Finite authored census; no independent-world generalization or causal learning.', 'No transforms or repeatability block.',
      'Artifact-to-live-engine binding is operator-declared; mid-run hot reload is not independently detected.', 'Latencies include server scheduling/cache effects; no GPU utilization or energy attribution.',
      'Token counts are server-reported; absent components remain unreported.'],
    observations: rows };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [out, destination] = process.argv.slice(2);
  if (!out || !destination) throw new Error('Usage: node analyze.mts PRIVATE_RUN_DIR NEW_PRIVATE_ANALYSIS_JSON');
  const result = await analyze(resolve(out));
  await saveNew(resolve(destination), result);
  console.log(JSON.stringify({ status: result.status, evidence_kind: result.evidence_kind, attempted: result.attempted, readiness: result.readiness }));
}
