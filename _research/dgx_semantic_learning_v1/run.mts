/** Bounded, synthetic real-model experiment through the native durable semantic runtime. */
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { readFile, writeFile, mkdir, appendFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { arms, models, protocol, task, example, label, score, digest, responseFormat } from './domain.mts';
import { copyTree } from './io.mts';

const base = resolve(fileURLToPath(new URL('../../', import.meta.url)));
const runtimeDist = process.env.HSWM_RESEARCH_RUNTIME_DIST ?? join(base, 'src/hswm/effect-runtime/dist');
const { Effect, Either, Layer } = createRequire(join(runtimeDist, 'index.js'))('effect');
const load = (name: string) => import(pathToFileURL(join(runtimeDist, name + '.js')).href);
const [bound, durable, semantic, admissionModule, engineering, schemaModule, subprocess] = await Promise.all([
  'canonical-atom-v2-content-bound', 'canonical-atom-v2-durable-runtime', 'canonical-atom-v2-llm-semantic-runtime',
  'canonical-atom-v2-llm-semantic-graph-loop-admission', 'canonical-atom-v2-graph-loop-engineering',
  'canonical-atom-v2-schema', 'effect-bounded-subprocess'
].map(load));
const { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } = durable;
const { executeLlmSemanticRelation, learnLlmSemanticRelation, readLlmSemanticFrame, stageLlmSemanticOutcome } = semantic;
const { GraphLoopEngineeringController, makeGraphLoopControlJournalFileLayer, makeGraphLoopEngineeringControllerLayer } = engineering;
const io = <A>(f: () => Promise<A>) => Effect.tryPromise({ try: f, catch: (e: unknown) => e });
const bytes = (v: unknown) => new TextEncoder().encode(JSON.stringify(v));
const unwrap = (e: any) => { if (Either.isLeft(e)) throw new Error(JSON.stringify(e.left)); return e.right; };
const save = (path: string, v: unknown) => writeFile(path, JSON.stringify(v, null, 2) + '\n', { flag: 'wx' });
const schemaVersion = 'hswm:research:dgx-semantic-learning:v1';
const lineageId = 'lineage:dgx-semantic-learning:v1';
const authorizationRef = 'authorization:synthetic-research-owner:v1', scope = 'scope:isolated-synthetic-research:v1';
const key = (atomUid: string, revisionId = 0) => ({ schemaVersion, lineageId, atomUid, revisionId });
const frozenProtocol = JSON.stringify(protocol, null, 2) + '\n';
const protocolSha = digest(frozenProtocol);
export const transport = {
  temperature: 0, chat_template_kwargs: { enable_thinking: false }, response_format: 'contract-derived JSON Schema; shape constraints only',
  system: 'You are the local semantic operator of an isolated research graph. Use the relation, typed roles, context, exceptions and available observed evidence. Return only the JSON object described by requiredOutput, with exactly those keys. For prediction, prediction must be a bit string in event case order, one 0 or 1 per case, with no separators. For learning, infer a concise general relation from the observed training cases; preserve exceptionRefs exactly. Express uncertainty honestly. No tools.'
};
const schema = {
  _tag: 'HSWMCanonicalSchemaV2', contractVersion: schemaModule.HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, schemaVersion,
  scientificStatus: 'UNJUDGED', bootstrapTrustStatement: 'Authored finite synthetic environment; caller-owned observations, no independent causal credit.',
  owners: [{ address: 'owner:semantic', obligation: 'Owns isolated research semantic relations under the declared protocol.' }],
  kinds: [
    { kind: 'semantic_participant', form: 'ENTITY', revisionPolicy: 'SINGLETON', allowedOwners: ['owner:semantic'], minimumArity: 0, referenceContracts: [] },
    { kind: 'semantic_relation', form: 'RELATION', revisionPolicy: 'LINEAR', allowedOwners: ['owner:semantic'], minimumArity: 4,
      referenceContracts: [
        { referenceType: 'hswm:semantic:role', roles: ['subject', 'context', 'evidence', 'exception'].map(role => ({ role, targetKinds: ['semantic_participant'], minimum: 1, maximum: 1 })) },
        { referenceType: 'hswm:reference:supersedes', roles: [{ role: 'hswm:role:predecessor', targetKinds: ['semantic_relation'], minimum: 0, maximum: 1 }] }
      ] }
  ]
};
const schemaBytes = unwrap(bound.canonicalAtomV2SchemaContentBytes(schema));
const schemaBinding = unwrap(bound.decodeCanonicalAtomV2SchemaContent(schemaBytes));
const fileLayer = (root: string) => {
  const rt = makeCanonicalAtomV2DurableRuntimeFileLayer(root, 'journal:dgx-semantic-learning:v1', schemaBytes,
    [{ authorizationRef, schemaVersion, schemaContentSha256: schemaBinding.binding.content.sha256, scopes: [scope] }]);
  const journal = makeGraphLoopControlJournalFileLayer(join(root, 'semantic-graph-loop'));
  const controller = makeGraphLoopEngineeringControllerLayer.pipe(Layer.provide([rt, journal]));
  return Layer.mergeAll(rt, journal, controller,
    Layer.succeed(subprocess.BoundedSubprocess, { observe: () => Effect.die('No model subprocess capability') }));
};
const atom = (uid: string, kind: string, content: any, references: any[] = [], revisionId = 0) => ({
  _tag: 'CanonicalAtomV2', contractVersion: schemaModule.HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(uid, revisionId), kind, responsibilityOwner: 'owner:semantic', content,
  provenance: { mode: revisionId ? 'DERIVATION' : 'BOOTSTRAP', evidenceSha256: protocolSha, sourceRef: revisionId ? key(uid, revisionId - 1) : null },
  lifecycle: 'ADMITTED', references
});
const binding = (a: any) => ({ key: a.key, payload: a.content, envelope: unwrap(bound.describeCanonicalAtomV2Envelope(a)) });
const submit = (rt: any, writes: any[], current: number, reads: any[], id: string) => rt.submit(bound.makeCanonicalAtomV2ContentBoundInput(
  rt.schemaContent.content.sha256,
  { _tag: 'CommitCanonicalAtomsV2', contractVersion: schemaModule.HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: id, expectedStateRevision: current, schemaVersion, actorClaim: 'research:synthetic-owner', authorizationRef, scope,
    decidedAt: new Date().toISOString(), traceRef: null, readSet: reads, writes, provenanceSha256: protocolSha }, writes.map(binding)
));
const seed = (text: string) => Effect.gen(function* () {
  const rt = yield* CanonicalAtomV2DurableRuntime;
  const descriptions = {
    subject: 'Each event case supplies the binary subject fields dax, wug and zif.',
    context: 'Each event case supplies binary context flag pel. Its effect is initially a provisional hypothesis.',
    evidence: 'Initially no observations. Outcome feedback contains only the declared training cases; do not invent observations.',
    exception: 'Each event case supplies binary exception flag nub. Preserve exception:flag reference and handle its stated effect.'
  };
  const participants: any[] = [];
  for (const [role, description] of Object.entries(descriptions)) {
    participants.push(atom(role + ':flag', 'semantic_participant', yield* rt.stageContent('application/json', bytes({ role, description }))));
  }
  const payload = { semanticText: text, disposition: 'predict-binary-output-under-context', uncertainty: 'provisional-context-effect', exceptionRefs: ['exception:flag'], trace: null, outcome: null };
  const relation = atom('relation:rule', 'semantic_relation', yield* rt.stageContent(semantic.HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, bytes(payload)),
    participants.map(a => ({ referenceType: 'hswm:semantic:role', role: a.key.atomUid.split(':')[0], target: a.key })));
  const result = yield* submit(rt, [...participants, relation], 0, [], 'seed:synthetic');
  return result;
});
const state = Effect.gen(function* () {
  const rt = yield* CanonicalAtomV2DurableRuntime;
  const snapshot = yield* rt.snapshot;
  const frame = yield* readLlmSemanticFrame(rt, 'relation:rule', 'state-inspection');
  return { stateRevision: snapshot.canonical.revision, canonicalSha256: digest(JSON.stringify(snapshot.canonical)),
    semanticSha256: digest(JSON.stringify(frame.relation.semantic)), relationRevision: frame.relation.key.revisionId,
    semantic: frame.relation.semantic, priorEvidence: frame.priorEvidence };
});
const httpClient = (logRoot: string) => ({
  postJson: (request: any) => io(async () => {
    const initial = JSON.parse(new TextDecoder().decode(request.body));
    const body = { ...initial, temperature: transport.temperature, chat_template_kwargs: transport.chat_template_kwargs,
      response_format: responseFormat(JSON.parse(initial.messages[0].content)), messages: [{ role: 'system', content: transport.system }, ...initial.messages] };
    const requestText = JSON.stringify(body), id = digest(requestText);
    await mkdir(logRoot, { recursive: true });
    await writeFile(join(logRoot, id + '.request.json'), requestText, { flag: 'wx' });
    const started = performance.now();
    const response = await fetch(request.url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: requestText, signal: AbortSignal.timeout(120000) });
    const raw = await response.text();
    await writeFile(join(logRoot, id + '.response.json'), raw, { flag: 'wx' });
    let envelope: any = {}; try { envelope = JSON.parse(raw); } catch { /* retain original bytes */ }
    await appendFile(join(logRoot, 'calls.jsonl'), JSON.stringify({ requestSha256: id, responseSha256: digest(raw),
      status: response.status, latency_ms: performance.now() - started, model: envelope.model ?? null,
      fingerprint: envelope.system_fingerprint ?? null, finish_reason: envelope.choices?.[0]?.finish_reason ?? null,
      usage: envelope.usage ?? null, transportSha256: digest(JSON.stringify(transport)) }) + '\n');
    if (!response.ok) throw new Error('HTTP ' + response.status + '; no retry');
    return new TextEncoder().encode(raw);
  })
});
const event = (ids: number[]) => JSON.stringify({ instruction: 'Predict one output bit per case, concatenated in the following case order.', cases: ids.map(example) });

async function worker(mode: string, configPath: string, arm: string) {
  const config = JSON.parse(await readFile(configPath, 'utf8'));
  const t = task(config.family, config.seed), root = join(config.root, arm);
  const cell = { base_url: `http://127.0.0.1:${config.model.port}/v1`, model: config.model.id, max_tokens: protocol.max_output_tokens };
  const run = (effect: any) => Effect.runPromise(effect.pipe(Effect.provide(fileLayer(root))));
  const http = httpClient(join(config.root, 'http', mode + '-' + arm));
  let result: any;
  if (mode === 'train') {
    await run(seed(t.initial));
    await copyTree(root, join(config.root, 'frozen'));
    result = await run(Effect.gen(function* () {
      const rt = yield* CanonicalAtomV2DurableRuntime;
      const trace = yield* executeLlmSemanticRelation(rt, 'relation:rule', event(t.train), cell, http);
      const observed = JSON.stringify({ cases: t.train.map(id => ({ ...example(id), observed: label(t.family, id) })),
        correctPrediction: t.train.map(id => label(t.family, id)).join(''), source: 'authored finite environment; training cases only' });
      const outcome = yield* stageLlmSemanticOutcome(rt, trace, observed, 'research:authored-training-environment:' + protocolSha);
      const stage = (v: unknown) => rt.stageContent('application/json', bytes(v));
      const action = yield* stage({ trace, outcome, protocolSha256: protocolSha, purpose: 'propose bounded semantic revision' });
      const verifierOutcome = yield* stage({ decision: 'ACCEPT', check: 'native schema, source binding and exception preservation',
        caveat: 'Research owner accepts mechanically valid proposal; no semantic correctness or efficacy adjudication.' });
      const evidence = yield* stage({ protocolSha256: protocolSha, traceSha256: trace.traceSha256, outcomeSha256: outcome.outcomeContent.sha256,
        authority: 'CALLER_OWNED_SYNTHETIC_RESEARCH', causalCredit: 'NOT_ESTABLISHED', invariant: 'native content-bound linear revision',
        authorization: 'isolated file runtime reference grant, not canonical Permit' });
      const controller = yield* GraphLoopEngineeringController;
      const admission = admissionModule.makeLlmSemanticGraphLoopAdmission(controller, {
        contract: { runId: 'run:' + t.id, triggerId: 'training-outcome', actorId: 'llm:semantic-engine', verifierId: 'research:mechanical-owner', maximumAttempts: 1, maximumActions: 1 },
        transactionId: 'learn:' + t.id, action, verification: { decision: 'ACCEPT', outcome: verifierOutcome },
        evidence: { sealedTrajectory: evidence, outcome: verifierOutcome, credit: evidence, authorization: evidence, invariant: evidence,
          authorizationStatus: 'REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT', conflictPolicy: 'SERIALIZABLE_COMPARE_AND_SWAP' }
      });
      const committed = yield* learnLlmSemanticRelation(rt, trace, outcome, cell, http, authorizationRef, scope, new Date().toISOString(), admission);
      if (committed.disposition !== 'COMMITTED') throw new Error('Proposal did not commit: ' + JSON.stringify(committed));
      return { trace, outcome, committedDisposition: committed.disposition, trainingScore: score(trace.prediction, t.family, t.train) };
    }));
    result.state = await run(state);
  } else if (mode === 'oracle') {
    await run(seed(t.oracle)); result = await run(state);
  } else if (mode === 'control') {
    await run(Effect.gen(function* () {
      const rt = yield* CanonicalAtomV2DurableRuntime;
      const frame = yield* readLlmSemanticFrame(rt, 'relation:rule', 'feedback-only-control');
      const snapshot = yield* rt.snapshot;
      const payload = { ...frame.relation.semantic, semanticText: t.initial, disposition: 'predict-binary-output-under-context', uncertainty: 'provisional-context-effect' };
      const successor = atom('relation:rule', 'semantic_relation', yield* rt.stageContent(semantic.HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, bytes(payload)),
        [{ referenceType: 'hswm:reference:supersedes', role: 'hswm:role:predecessor', target: frame.relation.key },
          ...frame.roles.map((r: any) => ({ referenceType: r.referenceType, role: r.role, target: r.key }))], frame.relation.key.revisionId + 1);
      yield* submit(rt, [successor], snapshot.canonical.revision, [frame.relation.key, ...frame.roles.map((r: any) => r.key)], 'research:feedback-only-control');
    }));
    result = await run(state);
  } else if (mode === 'eval') {
    const before = await run(state);
    const trace = await run(Effect.gen(function* () { const rt = yield* CanonicalAtomV2DurableRuntime;
      return yield* executeLlmSemanticRelation(rt, 'relation:rule', event(t.heldout), cell, http); }));
    const after = await run(state);
    if (before.canonicalSha256 !== after.canonicalSha256) throw new Error('Prediction mutated canonical state');
    result = { arm, ...score(trace.prediction, t.family, t.heldout), prediction: trace.prediction, trace,
      state: before, canonicalUnchanged: true, processId: process.pid };
  } else throw new Error('Unknown worker mode');
  await save(join(config.root, `${mode}-${arm}.json`), result);
}

async function child(mode: string, config: string, arm: string) {
  await new Promise<void>((ok, fail) => {
    const p = spawn(process.execPath, [fileURLToPath(import.meta.url), 'worker', mode, config, arm], { stdio: ['ignore', 'pipe', 'pipe'], env: process.env });
    let output = ''; p.stdout.on('data', b => { output += b; }); p.stderr.on('data', b => { output += b; });
    const timer = setTimeout(() => p.kill('SIGTERM'), 300000);
    p.on('error', e => { clearTimeout(timer); fail(e); });
    p.on('exit', code => { clearTimeout(timer); code === 0 ? ok() : fail(new Error(`${mode}/${arm} exit ${code}: ${output.slice(-6000)}`)); });
  });
}

async function main() {
  const out = process.env.HSWM_OUTPUT_ROOT;
  if (!out || process.env.HSWM_EXECUTION_TIER !== 'dgx-nvme') throw new Error('Use DGX hswm-run');
  await mkdir(out, { recursive: true }); await writeFile(join(out, 'protocol.json'), frozenProtocol, { flag: 'wx' });
  await save(join(out, 'transport.json'), transport);
  const start = Date.now(), jobs = models.flatMap(model => protocol.tasks.map(t => ({ model, family: t.family, seed: t.seed })));
  let next = 0; const results: any[] = [];
  async function consumer() {
    while (next < jobs.length && Date.now() - start < protocol.maximum_wall_seconds * 1000) {
      const job = jobs[next++], t = task(job.family, job.seed), id = job.model.id + '-' + t.id;
      const root = join(out!, 'trials', id); await mkdir(root, { recursive: true });
      const config = join(root, 'config.json'); await save(config, { ...job, root });
      const result: any = { id, ...job, heldout: t.heldout, arms: [], status: 'PENDING' };
      try {
        await child('train', config, 'learned');
        for (const [src, dst] of [['learned', 'restored'], ['learned', 'evidence_only'], ['frozen', 'removed']])
          await copyTree(join(root, src), join(root, dst));
        await child('control', config, 'evidence_only'); await child('oracle', config, 'oracle');
        for (const arm of arms) {
          try { await child('eval', config, arm); result.arms.push(JSON.parse(await readFile(join(root, `eval-${arm}.json`), 'utf8'))); }
          catch (e) { result.arms.push({ arm, valid: false, correct: 0, total: t.heldout.length, error: String(e) }); }
        }
        const get = (arm: string) => result.arms.find((r: any) => r.arm === arm);
        result.restorationExact = get('learned').state?.canonicalSha256 === get('restored').state?.canonicalSha256 && Boolean(get('learned').state);
        result.removalExact = get('frozen').state?.canonicalSha256 === get('removed').state?.canonicalSha256 && Boolean(get('frozen').state);
        result.feedbackEqual = JSON.stringify(get('learned').state?.priorEvidence) === JSON.stringify(get('evidence_only').state?.priorEvidence) && Boolean(get('learned').state?.priorEvidence);
        result.status = result.arms.every((r: any) => !r.error) && result.restorationExact && result.removalExact && result.feedbackEqual ? 'COMPLETE' : 'CONTROL_OR_EXECUTION_FAILURE';
      } catch (e) { result.status = 'TRAIN_OR_SETUP_FAILURE'; result.error = String(e); }
      results.push(result); await save(join(root, 'result.json'), result);
      await appendFile(join(out!, 'trials.jsonl'), JSON.stringify(result) + '\n');
      console.log(JSON.stringify({ completed: results.length, total: jobs.length, id, status: result.status,
        arms: result.arms.map((r: any) => ({ arm: r.arm, correct: r.correct, total: r.total, valid: r.valid })) }));
    }
  }
  await Promise.all(Array.from({ length: protocol.trial_concurrency }, consumer));
  await save(join(out, 'summary.json'), { protocolSha256: protocolSha, started: new Date(start).toISOString(), finished: new Date().toISOString(),
    plannedTrials: jobs.length, attemptedTrials: results.length, completeTrials: results.filter(r => r.status === 'COMPLETE').length,
    skippedTrials: jobs.length - results.length, results, claimCeiling: protocol.claim_ceiling });
  if (results.length !== jobs.length || results.some(r => r.status !== 'COMPLETE')) process.exitCode = 1;
}
try {
  if (process.argv[2] === '--protocol') console.log(frozenProtocol.trimEnd());
  else if (process.argv[2] === 'worker') await worker(process.argv[3], process.argv[4], process.argv[5]);
  else await main();
} catch (e) { console.error(e); process.exitCode = 1; }
