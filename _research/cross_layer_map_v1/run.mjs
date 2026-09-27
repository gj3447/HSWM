#!/usr/bin/env node
/** Local fixture rehearsal. The transport below never performs network I/O. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Effect, Either, Layer } from '../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js';
import {
  compareToyMappings, makeToyInputPacket, makeToyMapSpec, readToyFire, transitionToyState
} from '../../src/hswm/effect-runtime/dist/cross-layer-map-domain.js';
import {
  createCrossLayerMapSchema, stageCrossLayerMapInput, prepareCrossLayerMapBindingSuccessor,
  readCrossLayerMapFrame, executeCrossLayerMapRelation, CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE
} from '../../src/hswm/effect-runtime/dist/cross-layer-map-runtime.js';
import {
  CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js';
import {
  canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js';
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-schema.js';
import {
  HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, stageLlmSemanticOutcome, learnLlmSemanticRelation
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-runtime.js';
import { makeLlmSemanticGraphLoopAdmission } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-graph-loop-admission.js';
import {
  GraphLoopEngineeringController, makeGraphLoopControlJournalFileLayer,
  makeGraphLoopEngineeringControllerLayer
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-graph-loop-engineering.js';
import { compileCanonicalAtomV2DurableRdfProjection, canonicalAtomV2DurableRdfProjectionBytes } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-rdf-projection.js';
import { queryKgBundle, validateKgShacl } from '../../src/hswm/effect-runtime/dist/native-kg-standards.js';
import { BoundedSubprocess } from '../../src/hswm/effect-runtime/dist/effect-bounded-subprocess.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const utf8 = new TextEncoder();
const sha = value => createHash('sha256').update(value).digest('hex');
const json = value => utf8.encode(JSON.stringify(value));
const right = value => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left));
  return value.right;
};
const check = (condition, message) => { if (!condition) throw new Error(message); };
const usage = 'Usage: node _research/cross_layer_map_v1/run.mjs --output NEW_DIRECTORY\nFixture transport only; no model/network requests. Build the Effect runtime first.\n';
const schemaVersion = 'hswm:cross-layer-map:rehearsal:v1';
const lineageId = 'lineage:cross-layer-map:rehearsal:v1';
const owner = 'owner:cross-layer-map:rehearsal';
const relationUid = 'relation:cross-layer-map:rehearsal';
const authorizationRef = 'authorization:cross-layer-map:local-rehearsal';
const scope = 'scope:cross-layer-map:local-rehearsal';
const decidedAt = '2026-09-27T00:00:00.000Z';
const key = atomUid => ({ schemaVersion, lineageId, atomUid, revisionId: 0 });
const inputKeys = episode => Object.fromEntries(['subject', 'context', 'evidence'].map(role => [role, key(`${role}:${episode}`)]));
const atom = (atomUid, kind, content, references = []) => ({
  _tag: 'CanonicalAtomV2', contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid), kind, responsibilityOwner: owner, content,
  provenance: { mode: 'BOOTSTRAP', evidenceSha256: content.sha256, sourceRef: null },
  lifecycle: 'ADMITTED', references
});
const commitAtoms = (runtime, writes, transitionId) => Effect.gen(function* () {
  const state = yield* runtime.snapshot;
  const bindings = writes.map(value => ({ key: value.key, payload: value.content, envelope: right(describeCanonicalAtomV2Envelope(value)) }));
  return yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: 'CommitCanonicalAtomsV2', contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId, expectedStateRevision: state.canonical.revision, schemaVersion,
    actorClaim: 'fixture:cross-layer-map', authorizationRef, scope, decidedAt, traceRef: null,
    readSet: [], writes, provenanceSha256: sha(json(writes))
  }, bindings));
});

// This is a scripted transport, not an LLM or a performance baseline. It reads
// the supplied frame and demonstrates that changed relation text is consumed.
const revisedText = 'A pulse fires only when inhibition h=0 and refractory r=0.';
const fixtureTransport = requests => ({
  postJson: request => Effect.sync(() => {
    const wire = JSON.parse(new TextDecoder().decode(request.body));
    const payload = JSON.parse(wire.messages[0].content);
    requests.push({ contract: payload.contract, frameSha256: payload.frame.frameSha256 });
    let response;
    if (payload.contract === 'hswm-llm-semantic-learn/v1') {
      check(payload.outcome.observed !== undefined, 'revision must receive bound observation');
      response = {
        semanticText: revisedText, disposition: 'predict the declared one-tick fire readout',
        uncertainty: 'scripted fixture; no calibrated probability',
        exceptionRefs: payload.frame.relation.semantic.exceptionRefs
      };
    } else {
      check(payload.contract === 'hswm-llm-semantic-predict/v1', 'unexpected fixture request');
      const subject = JSON.parse(payload.frame.roles.find(role => role.role === 'subject').contentUtf8).subject;
      const revised = payload.frame.relation.semantic.semanticText === revisedText;
      const fire = subject.requested.action === 'pulse' && subject.observation.h === 0 && (!revised || subject.observation.r === 0);
      response = { prediction: String(Number(fire)), uncertainty: 'scripted fixture; not model evidence' };
    }
    return json({ choices: [{ message: { content: JSON.stringify(response) } }] });
  })
});

const graphInput = (runtime, label, outcome) => Effect.gen(function* () {
  const action = yield* runtime.stageContent('application/json', json({ kind: label, status: 'LOCAL_FIXTURE_ONLY' }));
  const evidence = yield* runtime.stageContent('application/json', json({ check: 'fixture content/trace consistency', causalCredit: 'NOT_ESTABLISHED' }));
  return {
    contract: { runId: `map:${label}`, triggerId: `trigger:${label}`, actorId: owner, verifierId: 'fixture:structural-check', maximumAttempts: 1, maximumActions: 1 },
    transactionId: `map:transaction:${label}`, action,
    verification: { decision: 'ACCEPT', outcome },
    evidence: { sealedTrajectory: evidence, outcome, credit: evidence, authorization: evidence, invariant: evidence, authorizationStatus: 'REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT', conflictPolicy: 'SERIALIZABLE_COMPARE_AND_SWAP' }
  };
});

async function run(output) {
  // Refuse overwrite before creating the durable runtime.
  await mkdir(dirname(output), { recursive: true });
  await mkdir(output);
  const domainPath = 'src/hswm/effect-runtime/src/cross-layer-map-domain.ts';
  const definitionBytes = await readFile(join(root, domainPath), 'utf8');
  const context = makeToyMapSpec(
    { modelRef: `repo:${domainPath}#transitionToyState`, definitionBytes },
    { modelRef: `repo:${domainPath}#mapToyState:preserve_r_h`, definitionBytes },
    'preserve_r_h'
  );
  const schemaBytes = right(canonicalAtomV2SchemaContentBytes(createCrossLayerMapSchema(schemaVersion, owner)));
  const schemaContent = right(decodeCanonicalAtomV2SchemaContent(schemaBytes));
  const grants = [{ authorizationRef, schemaVersion, schemaContentSha256: schemaContent.binding.content.sha256, scopes: [scope] }];
  const layer = () => {
    const runtime = makeCanonicalAtomV2DurableRuntimeFileLayer(join(output, 'state'), 'journal:cross-layer-map:rehearsal', schemaBytes, grants);
    const journal = makeGraphLoopControlJournalFileLayer(join(output, 'control'));
    const controller = makeGraphLoopEngineeringControllerLayer.pipe(Layer.provide([runtime, journal]));
    return Layer.mergeAll(runtime, journal, controller, Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die('fixture must not launch a subprocess') })));
  };
  const requests = [];
  const http = fixtureTransport(requests);
  const cell = { base_url: 'https://fixture.invalid/v1', model: 'cross-layer-scripted-fixture', max_tokens: 256 };
  const initialState = { r: 1, h: 0 };
  const packet0 = right(makeToyInputPacket(context, initialState, 0, 'pulse'));
  const cycle = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime;
    const controller = yield* GraphLoopEngineeringController;
    const staged = yield* stageCrossLayerMapInput(runtime, packet0, inputKeys('first'), owner);
    const exception = atom('exception:finite-domain', 'semantic_participant', yield* runtime.stageContent('application/json', json({ text: 'Only the declared one-tick finite toy; no biological claim.' })));
    const participants = { ...staged.participants, exception };
    const content = yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, json({
      semanticText: 'A pulse fires when inhibition h=0.', disposition: 'predict fire', uncertainty: 'fixture initial hypothesis',
      exceptionRefs: [exception.key.atomUid], trace: null, outcome: null
    }));
    const relation = atom(relationUid, 'semantic_relation', content, ['subject', 'context', 'evidence', 'exception'].map(role => ({ referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role, target: participants[role].key })));
    yield* commitAtoms(runtime, [...Object.values(participants), relation], 'map:seed');
    const trace = yield* executeCrossLayerMapRelation(runtime, relationUid, 'event:first', cell, http);
    const fire = readToyFire(initialState, 'pulse');
    const outcome = yield* stageLlmSemanticOutcome(runtime, trace, String(fire), 'fixture:finite-toy-rh/v1');
    const admission = makeLlmSemanticGraphLoopAdmission(controller, yield* graphInput(runtime, 'meaning-revision', outcome.outcomeContent));
    const learned = yield* learnLlmSemanticRelation(runtime, trace, outcome, cell, http, authorizationRef, scope, decidedAt, admission);
    check(learned.disposition === 'COMMITTED', 'meaning revision must commit');
    const learnedFrame = yield* readCrossLayerMapFrame(runtime, relationUid, 'event:learned');
    const stateAt1 = transitionToyState(initialState, 'pulse');
    const stateAt2 = transitionToyState(stateAt1, 'wait');
    const packet1 = right(makeToyInputPacket(context, stateAt2, 2, 'pulse', [{ sourceRef: 'fixture:first-outcome', digest: outcome.outcomeContent.sha256, observedAt: 1 }]));
    const nextKeys = { ...inputKeys('next'), context: inputKeys('first').context };
    const next = yield* stageCrossLayerMapInput(runtime, packet1, nextKeys, owner);
    // The authored MapSpec remains the same canonical atom. Only the observed
    // subject/evidence are new; bootstrap provenance cannot be reused later.
    yield* commitAtoms(runtime, [next.participants.subject, next.participants.evidence], 'map:next-observation');
    const proposal = yield* prepareCrossLayerMapBindingSuccessor(runtime, { relationUid, ...nextKeys, authorizationRef, scope, decidedAt });
    const input = yield* graphInput(runtime, 'input-binding', next.participants.evidence.content);
    yield* controller.trigger(input.contract);
    yield* controller.sealAction(input.contract.runId, input.action);
    yield* controller.recordVerification(input.contract.runId, input.verification.decision, input.verification.outcome);
    const bound = yield* controller.submitDelta({ runId: input.contract.runId, transactionId: input.transactionId, affectedKeys: proposal.affectedKeys, evidence: input.evidence, candidate: proposal.candidate });
    check(bound.disposition === 'COMMITTED', 'input binding must commit');
    return { firstPrediction: trace.prediction, observed: fire, learnedRevision: learnedFrame.frame.relation.key.revisionId, nextSubject: next.participants.subject.key, outcomeStatus: outcome.status };
  }).pipe(Effect.provide(layer())));

  // Reopen from the durable journal, rather than trusting in-memory objects.
  const query = await readFile(join(root, '_research/cross_layer_map_v1/queries/current-map-roles.rq'), 'utf8');
  const shape = await readFile(join(root, '_research/cross_layer_map_v1/shapes/map-profile.ttl'));
  const reopened = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime;
    const current = yield* readCrossLayerMapFrame(runtime, relationUid, 'event:next');
    check(current.frame.relation.semantic.semanticText === revisedText, 'revised semantics must survive reopen');
    check(current.frame.relation.key.revisionId === 2, 'one learning and one input-binding revision expected');
    check(current.frame.roles.find(role => role.role === 'subject').key.atomUid === cycle.nextSubject.atomUid, 'next observation must be bound');
    const trace = yield* executeCrossLayerMapRelation(runtime, relationUid, 'event:next', cell, http);
    const projection = yield* compileCanonicalAtomV2DurableRdfProjection(runtime);
    const nquads = projection.projection.nquads;
    const view = { nquads, descriptor: { dataset: { sha256: sha(nquads), byteLength: nquads.byteLength } }, provO: new Uint8Array() };
    const rows = yield* queryKgBundle(view, query);
    const shacl = yield* validateKgShacl(view, shape);
    check(Array.isArray(rows) && rows.length === 4, 'current map query must return four roles');
    check(shacl.conforms, 'map RDF profile must conform');
    return { nextPrediction: trace.prediction, relationRevision: current.frame.relation.key.revisionId, projection, rows, shacl };
  }).pipe(Effect.provide(layer())));

  const sourcePaths = [domainPath, 'src/hswm/effect-runtime/src/cross-layer-map-runtime.ts', 'src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.ts', 'src/hswm/effect-runtime/dist/cross-layer-map-domain.js', 'src/hswm/effect-runtime/dist/cross-layer-map-runtime.js', '_research/cross_layer_map_v1/run.mjs', '_research/cross_layer_map_v1/queries/current-map-roles.rq', '_research/cross_layer_map_v1/shapes/map-profile.ttl', 'src/hswm/effect-runtime/package-lock.json'];
  const sources = await Promise.all(sourcePaths.map(async path => ({ path, sha256: sha(await readFile(join(root, path))) })));
  const report = {
    schema: 'hswm-cross-layer-map-rehearsal/v1', status: 'ENGINEERING_FIXTURE_PASSED',
    evidence: 'SCRIPTED_TRANSPORT_NOT_REAL_LLM_IMPROVEMENT', modelCalls: 0, fixtureTransportCalls: requests.length,
    sources, comparison: compareToyMappings(),
    comparisonInterpretation: 'Readout class consistency over the finite domain; unambiguous rows are not prediction accuracy.',
    cycle: { ...cycle, interveningAction: { action: 'wait', window: { start: 1, end: 2 } }, nextPrediction: reopened.nextPrediction, relationRevision: reopened.relationRevision },
    graph: { currentRoles: reopened.rows, shacl: reopened.shacl, mapping: reopened.projection.projection.manifest.mapping, rdfDatasetOmits: reopened.projection.projection.manifest.rdfDatasetOmits, writeBack: 'FORBIDDEN' }
  };
  await writeFile(join(output, 'graph.nq'), reopened.projection.projection.nquads);
  await writeFile(join(output, 'projection.json'), right(canonicalAtomV2DurableRdfProjectionBytes(reopened.projection)));
  await writeFile(join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ status: report.status, report: join(output, 'report.json'), currentRoles: reopened.rows.length, shaclConforms: reopened.shacl.conforms, modelCalls: 0 }, null, 2) + '\n');
}

const args = process.argv.slice(2);
if (args.length === 1 && ['--help', '-h'].includes(args[0])) process.stdout.write(usage);
else if (args.length !== 2 || args[0] !== '--output' || !args[1].trim()) { process.stderr.write(usage); process.exitCode = 2; }
else await run(resolve(args[1])).catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
