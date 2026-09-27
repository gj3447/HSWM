/**
 * Minimal durable bootstrap for the semantic-lifecycle research runner.
 * This fixture is mechanically valid only; it makes no model or causal claim.
 */
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { Effect, Either, Layer } from '../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js';
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js';
import {
  canonicalAtomV2SchemaContentBytes,
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js';
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-schema.js';
import {
  HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE,
  readLlmSemanticFrame
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-runtime.js';
import { makeLlmSemanticGraphLoopAdmission } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-llm-semantic-graph-loop-admission.js';
import {
  GraphLoopEngineeringController,
  makeGraphLoopControlJournalFileLayer,
  makeGraphLoopEngineeringControllerLayer
} from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-graph-loop-engineering.js';
import { BoundedSubprocess } from '../../src/hswm/effect-runtime/dist/effect-bounded-subprocess.js';

export const relationUid = 'relation:door';
export const authorizationRef = 'authorization:semantic-lifecycle:fixture';
export const scope = 'scope:semantic-lifecycle:fixture';
export const INITIAL_TEXT = 'The door opens exactly when pressed is true.';
export const SHAM_TEXT = 'The door opens precisely if pressed is true.';
export const REVISED_TEXT = 'The door opens if manualRelease is true, or if pressed and power are true and locked is false; otherwise it remains closed.';

const schemaVersion = 'hswm:semantic-lifecycle:v1';
const lineageId = 'lineage:semantic-lifecycle:v1';
const journalLineage = 'journal:semantic-lifecycle:v1';
const owner = 'owner:semantic-lifecycle';
const roleReferenceType = 'hswm:semantic:role';
const encoder = new TextEncoder();
export const bytes = (value) => encoder.encode(typeof value === 'string' ? value : JSON.stringify(value));
export const sha = (value) => createHash('sha256').update(value).digest('hex');
const right = (value) => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left));
  return value.right;
};
const key = (atomUid, revisionId = 0) => ({ schemaVersion, lineageId, atomUid, revisionId });

const schema = {
  _tag: 'HSWMCanonicalSchemaV2',
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion,
  scientificStatus: 'UNJUDGED',
  bootstrapTrustStatement: 'Isolated local fixture state; no semantic, causal, or efficacy claim.',
  owners: [{ address: owner, obligation: 'Owns bounded semantic fixture revisions.' }],
  kinds: [
    { kind: 'semantic_participant', form: 'ENTITY', revisionPolicy: 'SINGLETON', allowedOwners: [owner], minimumArity: 0, referenceContracts: [] },
    {
      kind: 'semantic_relation', form: 'RELATION', revisionPolicy: 'LINEAR', allowedOwners: [owner], minimumArity: 4,
      referenceContracts: [
        { referenceType: roleReferenceType, roles: ['subject', 'context', 'evidence', 'exception'].map((role) => ({ role, targetKinds: ['semantic_participant'], minimum: 1, maximum: 1 })) },
        { referenceType: 'hswm:reference:supersedes', roles: [{ role: 'hswm:role:predecessor', targetKinds: ['semantic_relation'], minimum: 0, maximum: 1 }] }
      ]
    }
  ]
};
const schemaBytes = right(canonicalAtomV2SchemaContentBytes(schema));
const schemaContent = right(decodeCanonicalAtomV2SchemaContent(schemaBytes));
const grants = [{ authorizationRef, schemaVersion, schemaContentSha256: schemaContent.binding.content.sha256, scopes: [scope] }];

export const fileLayer = (stateRoot) => {
  const runtime = makeCanonicalAtomV2DurableRuntimeFileLayer(stateRoot, journalLineage, schemaBytes, grants);
  const journal = makeGraphLoopControlJournalFileLayer(join(stateRoot, 'semantic-graph-loop'));
  const controller = makeGraphLoopEngineeringControllerLayer.pipe(Layer.provide([runtime, journal]));
  const noSubprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die('semantic lifecycle fixture must not launch subprocesses') }));
  return Layer.mergeAll(runtime, journal, controller, noSubprocess);
};

const atom = (atomUid, kind, content, references = []) => ({
  _tag: 'CanonicalAtomV2', contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid), kind, responsibilityOwner: owner, content,
  provenance: { mode: 'BOOTSTRAP', evidenceSha256: content.sha256, sourceRef: null },
  lifecycle: 'ADMITTED', references
});
const binding = (value) => ({ key: value.key, payload: value.content, envelope: right(describeCanonicalAtomV2Envelope(value)) });

/** Bootstrap is the sole direct submit. All later revisions use graph-loop admission. */
export const seed = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime;
  const descriptions = {
    subject: { role: 'subject', description: 'A door event is the subject of this bounded fixture.' },
    context: { role: 'context', booleanFields: {
      pressed: 'Whether the press signal is true.', manualRelease: 'Whether the manual-release signal is true.',
      power: 'Whether the power signal is true.', locked: 'Whether the lock signal is true.'
    } },
    evidence: { role: 'evidence', description: 'Observations are attached only after an environment event is recorded.' },
    exception: { role: 'exception', description: 'The exception participant preserves the declared door reference.' }
  };
  const participants = [];
  for (const [role, payload] of Object.entries(descriptions)) {
    participants.push(atom(`${role}:door`, 'semantic_participant', yield* runtime.stageContent('application/json', bytes(payload))));
  }
  const semantic = yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, bytes({
    semanticText: INITIAL_TEXT, disposition: 'predict declared door state', uncertainty: 'fixture hypothesis',
    exceptionRefs: ['exception:door'], trace: null, outcome: null
  }));
  const relation = atom(relationUid, 'semantic_relation', semantic,
    participants.map((participant) => ({ referenceType: roleReferenceType, role: participant.key.atomUid.split(':')[0], target: participant.key })));
  const writes = [...participants, relation];
  return yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: 'CommitCanonicalAtomsV2', contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: 'seed:semantic-lifecycle', expectedStateRevision: 0, schemaVersion,
    actorClaim: 'fixture:semantic-lifecycle', authorizationRef, scope, decidedAt: '2026-09-27T00:00:00.000Z',
    traceRef: null, readSet: [], writes, provenanceSha256: sha(bytes(writes.map((write) => write.key)))
  }, writes.map(binding)));
});

export const inspectState = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime;
  const snapshot = yield* runtime.snapshot;
  const frame = yield* readLlmSemanticFrame(runtime, relationUid, 'semantic-lifecycle:inspect');
  return Object.freeze({
    relationKey: frame.relation.key, stateRevision: snapshot.canonical.revision,
    canonicalSha256: sha(JSON.stringify(snapshot.canonical)), semantic: frame.relation.semantic,
    frameSha256: frame.frameSha256,
    roleRefs: frame.roles.map(({ referenceType, role, key: roleKey }) => ({ referenceType, role, key: roleKey }))
  });
});

/** Mechanical ACCEPT admission only; its records explicitly deny causal credit. */
export const admissionFor = (runtime, controller, trace, outcome, label) => Effect.gen(function* () {
  const stage = (value) => runtime.stageContent('application/json', bytes(value));
  const action = yield* stage({ label, purpose: 'bounded semantic revision proposal', traceSha256: trace.traceSha256 });
  const verifier = yield* stage({ label, decision: 'ACCEPT', check: 'mechanical schema and content binding only', semanticCorrectness: 'NOT_ADJUDICATED', efficacy: 'NOT_ADJUDICATED' });
  const evidence = yield* stage({ label, traceSha256: trace.traceSha256, outcomeSha256: outcome.outcomeContent.sha256, causalCredit: 'NOT_ESTABLISHED', authorization: 'LOCAL_FIXTURE_REFERENCE_GRANT_NOT_CANONICAL_PERMIT' });
  return makeLlmSemanticGraphLoopAdmission(controller, {
    contract: { runId: `run:${label}`, triggerId: `trigger:${label}`, actorId: 'llm:fixture-operator', verifierId: 'fixture:mechanical-controller', maximumAttempts: 1, maximumActions: 1 },
    transactionId: `revision:${label}`, action, verification: { decision: 'ACCEPT', outcome: verifier },
    evidence: { sealedTrajectory: evidence, outcome: verifier, credit: evidence, authorization: evidence, invariant: evidence, authorizationStatus: 'REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT', conflictPolicy: 'SERIALIZABLE_COMPARE_AND_SWAP' }
  });
});
