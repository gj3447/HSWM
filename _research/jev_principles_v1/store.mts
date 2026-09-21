/** Bounded, synthetic real-model experiment through the native durable semantic runtime. */
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { readFile, writeFile, mkdir, appendFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { arms, models, protocol, task, example, label, score, digest, responseFormat } from './support/domain.mts';
import { copyTree } from './support/io.mts';

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
    semantic: frame.relation.semantic, roles: frame.roles, priorEvidence: frame.priorEvidence };
});

// Read a fresh native canonical store in a separate process, or bootstrap its oracle.
const config = JSON.parse(await readFile(process.argv[3], 'utf8'));
const arm = process.argv[4], root = join(config.root, arm);
const run = (effect: any) => Effect.runPromise(effect.pipe(Effect.provide(fileLayer(root))));
if (process.argv[2] === 'oracle') await run(seed(task(config.family, config.seed).oracle));
const observed = await run(state);
await save(process.argv[5], observed);
