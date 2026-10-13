/** One isolated W1 E1 model call. No labels, optimizer, or graph writes. */
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import {
  localSemanticCases, localSemanticModeInstructions, localSemanticModeSchemas,
  parseLocalSemanticOutput, type LocalSemanticInput
} from '../../src/hswm/effect-runtime/src/local-semantic-execution-domain.ts';

type Execution = { base_url: string; model: string; max_tokens: number; timeout_seconds: number; seed: number };
type Renderer = 'legacy' | 'ordered';
type Generation = { temperature: number; top_p: number; top_k: number; min_p: number; thinking: boolean };
type BridgeRequest = { input: LocalSemanticInput; relation_text: string; execution: Execution; renderer?: Renderer; generation?: Generation };
const sha = (text: string) => createHash('sha256').update(text).digest('hex');
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const exact = (v: Record<string, unknown>, keys: string[]) => Object.keys(v).sort().join(',') === keys.sort().join(',');
const nonempty = (v: unknown): v is string => typeof v === 'string' && !!v.trim();
const integer = (v: unknown, low: number, high: number): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= low && v <= high;

export function validateRequest(raw: unknown): BridgeRequest {
  if (!object(raw) || !(['input', 'relation_text', 'execution'].every(key => key in raw) && Object.keys(raw).every(key => ['input', 'relation_text', 'execution', 'renderer', 'generation'].includes(key))) || !nonempty(raw.relation_text) || raw.relation_text.length > 8192)
    throw new Error('Invalid bridge request or relation text');
  const input = raw.input, exec = raw.execution;
  if (!object(input)) throw new Error('Expected local semantic input');
  const relation = input.relation;
  if (!exact(input, ['relation', 'roles', 'priorEvidence', 'fields']) ||
      !object(relation) || !exact(relation, ['semanticText', 'disposition', 'uncertainty', 'exceptionRefs']) ||
      !['semanticText', 'disposition', 'uncertainty'].every(k => nonempty(relation[k])) ||
      !Array.isArray(relation.exceptionRefs) || !relation.exceptionRefs.every(nonempty) ||
      !Array.isArray(input.priorEvidence) || input.priorEvidence.length !== 0 ||
      !Array.isArray(input.roles) || input.roles.length !== 3 || !input.roles.every((role, index) =>
        object(role) && exact(role, ['role','ordinal','referenceType']) && role.role === ['subject','context','exception'][index] &&
        role.ordinal === index && role.referenceType === 'LOCAL_SEMANTIC_INPUT'))
    throw new Error('Expected the existing W1 local semantic input contract');
  const fields = input.fields;
  if (!object(fields) || !exact(fields, ['subject', 'context', 'exception'])) throw new Error('Invalid input fields');
  for (const [role, keys] of [['subject', ['dax','wug','zif']], ['context',['pel']], ['exception',['nub']]] as const) {
    const value = fields[role];
    if (!object(value) || !exact(value, [...keys]) || !keys.every(k => value[k] === 0 || value[k] === 1)) throw new Error('Invalid role fields');
  }
  if (!object(exec) || !exact(exec, ['base_url','model','max_tokens','timeout_seconds','seed']) || !nonempty(exec.base_url) || !nonempty(exec.model) ||
      !integer(exec.max_tokens, 1, 2048) || !integer(exec.timeout_seconds, 1, 120) || !integer(exec.seed, 0, 2147483647)) throw new Error('Invalid execution configuration');
  const url = new URL(exec.base_url);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || !['','/','/v1','/v1/'].includes(url.pathname))
    throw new Error('Expected an HTTP model base URL without credentials');
  if (raw.renderer !== undefined && raw.renderer !== 'legacy' && raw.renderer !== 'ordered') throw new Error('Invalid renderer');
  if (raw.generation !== undefined) {
    const g = raw.generation;
    const fraction = (v: unknown, low: number, high: number): v is number => typeof v === 'number' && Number.isFinite(v) && v >= low && v <= high;
    if (!object(g) || !exact(g, ['temperature', 'top_p', 'top_k', 'min_p', 'thinking']) ||
        !fraction(g.temperature, 0, 2) || !fraction(g.top_p, Number.EPSILON, 1) ||
        !integer(g.top_k, 1, 100) || !fraction(g.min_p, 0, 1) || typeof g.thinking !== 'boolean')
      throw new Error('Invalid generation controls');
  }
  return raw as unknown as BridgeRequest;
}

export function renderCandidate(input: LocalSemanticInput, relationText: string, renderer: Renderer = 'legacy'): string {
  const candidateInput = { ...input, relation: { ...input.relation, semanticText: relationText } };
  if (renderer === 'legacy') return JSON.stringify(candidateInput);
  const r = candidateInput.relation, f = candidateInput.fields;
  // Explicit presentation only: every LocalSemanticInput value is retained.
  return [
    'RELATION', `semanticText=${JSON.stringify(r.semanticText)}`, `disposition=${JSON.stringify(r.disposition)}`,
    `uncertainty=${JSON.stringify(r.uncertainty)}`, `exceptionRefs=${JSON.stringify(r.exceptionRefs)}`,
    'ROLES', ...candidateInput.roles.slice().sort((a, b) => a.ordinal - b.ordinal).map(x => `${x.ordinal}:${x.role}:${x.referenceType}`),
    `PRIOR_EVIDENCE=${JSON.stringify(candidateInput.priorEvidence)}`,
    'SUBJECT', `dax=${f.subject.dax}`, `wug=${f.subject.wug}`, `zif=${f.subject.zif}`,
    'CONTEXT', `pel=${f.context.pel}`, 'EXCEPTION', `nub=${f.exception.nub}`
  ].join('\n');
}

export function buildRequest(input: LocalSemanticInput, relationText: string, execution: Execution, renderer: Renderer = 'legacy', generation?: Generation) {
  const request = {
    model: execution.model, temperature: generation?.temperature ?? 0, seed: execution.seed, max_tokens: execution.max_tokens,
    chat_template_kwargs: { enable_thinking: generation?.thinking ?? false },
    messages: [
      { role: 'system', content: 'Execute the supplied local semantic relation using its ordered roles, context and exceptions. Return only the required JSON output.' },
      { role: 'user', content: renderCandidate(input, relationText, renderer) + '\n' + localSemanticModeInstructions.E1 }
    ],
    response_format: { type: 'json_schema', json_schema: { name: 'hswm_w1_e1', strict: true, schema: localSemanticModeSchemas.E1 } }
  };
  return generation ? { ...request, top_p: generation.top_p, top_k: generation.top_k, min_p: generation.min_p } : request;
}

export async function evaluate(raw: unknown) {
  const { input, relation_text, execution, renderer = 'legacy', generation } = validateRequest(raw);
  const request = buildRequest(input, relation_text, execution, renderer, generation);
  const requestText = JSON.stringify(request), started = performance.now();
  let responseText: string | null = null;
  let usage: { input_tokens: number; output_tokens: number; total_tokens: number } | null = null;
  let reasoning: string | null = null, reasoning_field: string | null = null, finish_reason: string | null = null;
  const result = (valid: boolean, answer: string | null, error_kind: string | null) => ({
    valid, answer, error_kind, request_sha256: sha(requestText), response_sha256: responseText === null ? null : sha(responseText),
    model: execution.model, usage, latency_ms: performance.now() - started, model_calls: 1,
    request, raw_response: responseText, reasoning, reasoning_field, finish_reason,
    evidence_kind: 'LOCAL_RELATION_TEXT_EXECUTION_NOT_CANONICAL_REVISION'
  });
  try {
    const root = execution.base_url.replace(/\/v1\/?$/, '').replace(/\/$/, '');
    const response = await fetch(root + '/v1/chat/completions', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: requestText,
      signal: AbortSignal.timeout(execution.timeout_seconds * 1000), redirect: 'error'
    });
    responseText = await response.text();
    if (!response.ok) return result(false, null, `HTTP_${response.status}`);
    let envelope: unknown;
    try { envelope = JSON.parse(responseText); } catch { return result(false, null, 'INVALID_ENVELOPE'); }
    if (!object(envelope) || envelope.model !== execution.model) return result(false, null, 'MODEL_ID_MISMATCH');
    const observed = envelope.usage;
    if (object(observed) && integer(observed.prompt_tokens, 0, Number.MAX_SAFE_INTEGER) && integer(observed.completion_tokens, 0, Number.MAX_SAFE_INTEGER) &&
        integer(observed.total_tokens, 0, Number.MAX_SAFE_INTEGER) && observed.total_tokens === observed.prompt_tokens + observed.completion_tokens)
      usage = { input_tokens: observed.prompt_tokens, output_tokens: observed.completion_tokens, total_tokens: observed.total_tokens };
    const choices = envelope.choices;
    if (Array.isArray(choices) && choices.length === 1 && object(choices[0])) {
      finish_reason = typeof choices[0].finish_reason === 'string' ? choices[0].finish_reason : null;
      const message = choices[0].message;
      if (object(message)) {
        for (const field of ['reasoning', 'reasoning_content']) {
          if (typeof message[field] === 'string' && message[field].trim()) {
            if (reasoning !== null && reasoning !== message[field]) return result(false, null, 'AMBIGUOUS_REASONING_CHANNEL');
            reasoning = message[field]; reasoning_field = field;
          }
        }
      }
    }
    if (!Array.isArray(choices) || choices.length !== 1 || !object(choices[0]) || choices[0].finish_reason !== 'stop' ||
        !object(choices[0].message) || typeof choices[0].message.content !== 'string') return result(false, null, 'INCOMPLETE_OUTPUT');
    if (generation?.thinking && reasoning === null) return result(false, null, 'MISSING_REASONING_CHANNEL');
    const parsed = parseLocalSemanticOutput('E1', choices[0].message.content);
    return parsed.valid ? result(true, String(parsed.output.answer), null) : result(false, null, parsed.refusal.reason);
  } catch (error) {
    return result(false, null, error instanceof Error && ['AbortError','TimeoutError'].includes(error.name) ? 'TIMEOUT' : 'TRANSPORT_ERROR');
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    if (process.argv[2] === '--fixture') {
      // References stay in evaluator custody; the model call accepts input only.
      process.stdout.write(JSON.stringify(localSemanticCases) + '\n');
    } else {
      let input = '';
      for await (const chunk of process.stdin) {
        input += chunk;
        if (Buffer.byteLength(input) > 65536) throw new Error('Bridge request exceeds 64 KiB');
      }
      process.stdout.write(JSON.stringify(await evaluate(JSON.parse(input))) + '\n');
    }
  } catch (error) {
    process.stderr.write((error instanceof Error ? error.message : 'Bridge configuration error') + '\n');
    process.exitCode = 1;
  }
}
