/** Recorded transport for this finite study. Scripted mode is never model evidence. */
import { randomUUID } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { Effect } from '../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js';
import { NativeAdaptiveHttpClient } from '../../src/hswm/effect-runtime/dist/adaptive-executor.js';
import { INITIAL_TEXT, SHAM_TEXT, REVISED_TEXT, bytes, sha } from './runtime.mjs';

export const TRANSPORT_CONTRACT = 'hswm-semantic-lifecycle-transport/v1';
const instructions = 'Use the supplied semantic relation and role context to predict. Return only the JSON object with exactly the keys in requiredOutput. For prediction, return a bit string in event.cases order: 1 means opens, 0 means closed. For learning, propose a concise general semantic relation from the observed training cases, preserve exceptionRefs exactly, and state uncertainty. No tools.';
const io = f => Effect.tryPromise({ try: f, catch: e => e });
const save = (path, raw) => writeFile(path, raw, { flag: 'wx', mode: 0o600 });

/** Fixed scripted responses deliberately use authored logic, not learned inference. */
const scripted = payload => {
  if (payload.contract === 'hswm-llm-semantic-learn/v1') return {
    semanticText: REVISED_TEXT, disposition: payload.frame.relation.semantic.disposition,
    uncertainty: 'scripted fixture; no model evidence', exceptionRefs: payload.frame.relation.semantic.exceptionRefs
  };
  const text = payload.frame.relation.semantic.semanticText;
  if (![INITIAL_TEXT, SHAM_TEXT, REVISED_TEXT].includes(text)) throw new Error('Unknown scripted semantic text');
  const cases = JSON.parse(payload.frame.event).cases;
  const prediction = cases.map(({ input: x }) => Number(text === REVISED_TEXT
    ? x.manualRelease || (x.pressed && x.power && !x.locked) : x.pressed)).join('');
  return { prediction, uncertainty: 'scripted fixture; no calibrated probability' };
};

export const createTransport = ({ mode, logRoot, controlText = null }) => {
  const calls = [];
  const http = {
    postJson: request => Effect.gen(function* () {
      const wire = JSON.parse(new TextDecoder().decode(request.body));
      const payload = JSON.parse(wire.messages[0].content);
      const construction = controlText !== null;
      if (construction && payload.contract !== 'hswm-llm-semantic-learn/v1') throw new Error('Control construction accepts revision only');
      const actual = { ...wire, temperature: 0, messages: [{ role: 'system', content: instructions }, ...wire.messages] };
      const actualBytes = bytes(actual);
      const id = randomUUID();
      yield* io(() => mkdir(logRoot, { recursive: true, mode: 0o700 }));
      yield* io(() => save(join(logRoot, `${id}.request.json`), actualBytes));
      const started = Date.now();
      const result = yield* (construction || mode === 'scripted'
        ? Effect.sync(() => {
          const content = construction
            ? { semanticText: controlText, disposition: payload.frame.relation.semantic.disposition,
              uncertainty: payload.frame.relation.semantic.uncertainty, exceptionRefs: payload.frame.relation.semantic.exceptionRefs }
            : scripted(payload);
          return bytes({ choices: [{ message: { content: JSON.stringify(content) } }] });
        })
        : NativeAdaptiveHttpClient.postJson({ ...request, body: actualBytes, timeoutMs: Math.min(request.timeoutMs, 30_000) })
      ).pipe(Effect.either);
      const record = {
        id, contract: TRANSPORT_CONTRACT, semanticContract: payload.contract,
        mode: construction ? 'AUTHORED_CONTROL_CONSTRUCTION' : mode,
        httpModelRequest: !construction && mode === 'http', requestSha256: sha(actualBytes),
        frameSha256: payload.frame.frameSha256, relationKey: payload.frame.relation.key,
        latencyMs: Date.now() - started, status: result._tag === 'Right' ? 'RESPONSE_RECEIVED' : 'TRANSPORT_FAILED',
        responseSha256: result._tag === 'Right' ? sha(result.right) : null,
        usage: null, reportedModel: null, finishReason: null
      };
      if (result._tag === 'Right') {
        yield* io(() => save(join(logRoot, `${id}.response.json`), result.right));
        try {
          const body = JSON.parse(new TextDecoder().decode(result.right));
          record.usage = body.usage ?? null;
          record.reportedModel = body.model ?? null;
          record.finishReason = body.choices?.[0]?.finish_reason ?? null;
        } catch { /* Preserve raw bytes; the native semantic parser handles refusal. */ }
      }
      calls.push(Object.freeze(record));
      yield* io(() => save(join(logRoot, `${id}.receipt.json`), bytes(record)));
      if (result._tag === 'Left') return yield* Effect.fail(result.left);
      return result.right;
    })
  };
  return { http, calls };
};
