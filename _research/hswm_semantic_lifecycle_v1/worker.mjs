/** Child-process stages. Importing this module has no execution side effect. */
import { readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Effect, Either } from '../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js';
import { CanonicalAtomV2DurableRuntime } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js';
import { GraphLoopEngineeringController } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-graph-loop-engineering.js';
import { executeLlmSemanticRelation, stageLlmSemanticOutcome, learnLlmSemanticRelation } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-runtime.js';
import { doorRuleCases, doorRuleActorView, assessDoorRulePredictions } from '../../src/hswm/effect-runtime/dist/semantic-rule-environment.js';
import { fileLayer, seed, inspectState, admissionFor, relationUid, authorizationRef, scope, INITIAL_TEXT, SHAM_TEXT, bytes } from './runtime.mjs';
import { createTransport } from './transport.mjs';

const save = (path, value) => writeFile(path, bytes(value), { flag: 'wx', mode: 0o600 });
const right = value => { if (Either.isLeft(value)) throw new Error(value.left.code); return value.right; };
export const actorEvent = split => JSON.stringify({
  instruction: 'Predict a bit per case in the given order. Use the supplied relation as the current hypothesis.',
  cases: doorRuleCases(split).map(c => right(doorRuleActorView(c.id)))
});

/** An invalid batch is all-null; it never loses rows from the denominator. */
export const assessBatch = (split, output) => {
  const cases = doorRuleCases(split);
  const valid = typeof output === 'string' && new RegExp(`^[01]{${cases.length}}$`).test(output);
  return right(assessDoorRulePredictions(split, cases.map((c, i) => ({ caseId: c.id, prediction: valid ? output[i] === '1' : null }))));
};

export async function runWorker(stage, configPath, arm) {
  const config = JSON.parse(await readFile(configPath, 'utf8'));
  if (!['train', 'revise', 'development', 'heldout'].includes(stage) || !['base', ...config.arms].includes(arm)) throw new Error('Invalid worker stage or arm');
  const root = join(config.root, 'states', arm);
  const run = effect => Effect.runPromise(effect.pipe(Effect.provide(fileLayer(root))));
  const controlText = stage === 'revise' && arm !== 'learned' ? (arm === 'sham' ? SHAM_TEXT : INITIAL_TEXT) : null;
  const transport = createTransport({ mode: config.transport, logRoot: join(config.root, 'http', `${stage}-${arm}`), controlText });
  let result;
  if (stage === 'train') {
    await run(seed);
    result = await run(Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime;
      const trace = yield* executeLlmSemanticRelation(runtime, relationUid, actorEvent('train'), config.cell, transport.http);
      const assessment = assessBatch('train', trace.prediction);
      const observed = JSON.stringify({
        cases: assessment.observations.map(o => ({ ...right(doorRuleActorView(o.caseId)), observed: o.observed })),
        observationKind: 'AUTHORED_FINITE_ENVIRONMENT'
      });
      const outcome = yield* stageLlmSemanticOutcome(runtime, trace, observed, `authored-door-environment:sha256:${config.environmentSha256}`);
      return { trace, outcome, assessment, state: yield* inspectState };
    }));
  } else if (stage === 'revise') {
    const training = JSON.parse(await readFile(join(config.root, 'train-base.json'), 'utf8'));
    result = await run(Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime;
      const controller = yield* GraphLoopEngineeringController;
      const before = yield* inspectState;
      const admission = yield* admissionFor(runtime, controller, training.trace, training.outcome, arm);
      const attempted = yield* learnLlmSemanticRelation(runtime, training.trace, training.outcome, config.cell,
        transport.http, authorizationRef, scope, new Date().toISOString(), admission).pipe(Effect.either);
      const after = yield* inspectState;
      const committed = attempted._tag === 'Right' && attempted.right.disposition === 'COMMITTED';
      return {
        committed, disposition: attempted._tag === 'Right' ? attempted.right.disposition : 'PROPOSAL_FAILED',
        errorCode: attempted._tag === 'Left' ? attempted.left.code ?? attempted.left.reason ?? 'UNCLASSIFIED' : null,
        before, after, semanticFieldsChanged: ['semanticText', 'disposition', 'uncertainty'].filter(k => before.semantic[k] !== after.semantic[k]),
        outcomeSha256: training.outcome.outcomeContent.sha256
      };
    }));
  } else {
    result = await run(Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime;
      const before = yield* inspectState;
      const attempted = yield* executeLlmSemanticRelation(runtime, relationUid, actorEvent(stage), config.cell, transport.http).pipe(Effect.either);
      const after = yield* inspectState;
      if (before.canonicalSha256 !== after.canonicalSha256) throw new Error('Evaluation changed canonical state');
      const trace = attempted._tag === 'Right' ? attempted.right : null;
      return { before, after, canonicalUnchanged: true, trace, assessment: assessBatch(stage, trace?.prediction ?? null),
        errorCode: attempted._tag === 'Left' ? attempted.left.code ?? 'UNCLASSIFIED' : null };
    }));
  }
  const report = { stage, arm, processId: process.pid, parentProcessId: process.ppid, ...result, calls: transport.calls };
  await save(join(config.root, `${stage}-${arm}.json`), report);
  return report;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runWorker(process.argv[2], process.argv[3], process.argv[4]).catch(error => {
    process.stderr.write(`SEMANTIC_LIFECYCLE_WORKER_FAILED: ${String(error).slice(0, 3000)}\n`);
    process.exitCode = 1;
  });
}
