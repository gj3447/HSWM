/**
 * Durable, deliberately small graph state used by the semantic-lifecycle
 * wiring experiment.  This is a mechanical fixture: the graph-loop ACCEPT
 * record is not a judgment of meaning, learning, or causal efficacy.
 */
import { createHash } from "node:crypto"
import { join } from "node:path"

import { Data, Effect, Either, Layer } from "effect"

import {
  canonicalAtomV2SchemaContentBytes,
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2WriteContentBinding
} from "./canonical-atom-v2-content-bound.js"
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer
} from "./canonical-atom-v2-durable-runtime.js"
import {
  GraphLoopEngineeringController,
  makeGraphLoopControlJournalFileLayer,
  makeGraphLoopEngineeringControllerLayer
} from "./canonical-atom-v2-graph-loop-engineering.js"
import { makeLlmSemanticGraphLoopAdmission } from "./canonical-atom-v2-llm-semantic-graph-loop-admission.js"
import {
  HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE,
  readLlmSemanticFrame,
  type SemanticOutcome,
  type SemanticTrace
} from "./canonical-atom-v2-llm-semantic-runtime.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"

export const relationUid = "relation:door" as const
export const authorizationRef = "authorization:semantic-lifecycle:fixture" as const
export const scope = "scope:semantic-lifecycle:fixture" as const
export const INITIAL_TEXT = "The door opens exactly when pressed is true." as const
export const SHAM_TEXT = "The door opens precisely if pressed is true." as const
export const REVISED_TEXT = "The door opens if manualRelease is true, or if pressed and power are true and locked is false; otherwise it remains closed." as const

const schemaVersion = "hswm:semantic-lifecycle:v1"
const lineageId = "lineage:semantic-lifecycle:v1"
const journalLineage = "journal:semantic-lifecycle:v1"
const owner = "owner:semantic-lifecycle"
const roleReferenceType = "hswm:semantic:role"
const encoder = new TextEncoder()

export const bytes = (value: string | Readonly<Record<string, unknown>> | ReadonlyArray<unknown>): Uint8Array =>
  encoder.encode(typeof value === "string" ? value : JSON.stringify(value))
export const sha = (value: Uint8Array | string): string => createHash("sha256").update(value).digest("hex")

export class SemanticLifecycleRuntimeError extends Data.TaggedError("SemanticLifecycleRuntimeError")<{
  readonly code: "SCHEMA_INVALID" | "CONTENT_BINDING_INVALID" | "BOOTSTRAP_NOT_COMMITTED"
  readonly detail: string
}> {}

const lifecycleError = (code: SemanticLifecycleRuntimeError["code"], detail: string): SemanticLifecycleRuntimeError =>
  new SemanticLifecycleRuntimeError({ code, detail })

const atomKey = (atomUid: string, revisionId = 0): CanonicalAtomV2Key =>
  Object.freeze({ schemaVersion, lineageId, atomUid, revisionId })

const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Isolated local fixture state; no semantic, causal, or efficacy claim.",
  owners: [{ address: owner, obligation: "Owns bounded semantic fixture revisions." }],
  kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: [owner], minimumArity: 0, referenceContracts: [] },
    {
      kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 4,
      referenceContracts: [
        { referenceType: roleReferenceType, roles: ["subject", "context", "evidence", "exception"].map((role) => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 1 })) },
        { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }
      ]
    }
  ]
}

const schemaBytesResult = canonicalAtomV2SchemaContentBytes(schema)
const schemaLayer = (stateRoot: string) =>
  Layer.unwrapEffect(
    Either.match(schemaBytesResult, {
      onLeft: (error) => Effect.fail(lifecycleError("SCHEMA_INVALID", error.detail)),
      onRight: (schemaBytes) => Either.match(decodeCanonicalAtomV2SchemaContent(schemaBytes), {
        onLeft: (error) => Effect.fail(lifecycleError("SCHEMA_INVALID", error.detail)),
        onRight: (content) => {
          const grants = [{ authorizationRef, schemaVersion, schemaContentSha256: content.binding.content.sha256, scopes: [scope] }]
          const runtime = makeCanonicalAtomV2DurableRuntimeFileLayer(stateRoot, journalLineage, schemaBytes, grants)
          const journal = makeGraphLoopControlJournalFileLayer(join(stateRoot, "semantic-graph-loop"))
          const controller = makeGraphLoopEngineeringControllerLayer.pipe(Layer.provide([runtime, journal]))
          const noSubprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die("semantic lifecycle fixture must not launch subprocesses") }))
          return Effect.succeed(Layer.mergeAll(runtime, journal, controller, noSubprocess))
        }
      })
    })
  )

/** The file-backed runtime and graph-loop controller for one isolated arm. */
export const makeSemanticLifecycleFileLayer = (stateRoot: string) => schemaLayer(stateRoot)

const makeAtom = (
  atomUid: string,
  kind: CanonicalAtomV2["kind"],
  content: CanonicalAtomV2["content"],
  references: CanonicalAtomV2["references"] = []
): CanonicalAtomV2 => Object.freeze({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: atomKey(atomUid),
  kind,
  responsibilityOwner: owner,
  content,
  provenance: { mode: "BOOTSTRAP" as const, evidenceSha256: content.sha256, sourceRef: null },
  lifecycle: "ADMITTED",
  references
})

const contentBinding = (value: CanonicalAtomV2): Either.Either<CanonicalAtomV2WriteContentBinding, SemanticLifecycleRuntimeError> =>
  describeCanonicalAtomV2Envelope(value).pipe(
    Either.map((envelope) => Object.freeze({ key: value.key, payload: value.content, envelope })),
    Either.mapLeft((error) => lifecycleError("CONTENT_BINDING_INVALID", error.detail))
  )

/** Bootstrap uses the same graph-loop boundary as later revisions; ACCEPT is mechanical only. */
export const seedSemanticLifecycle = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const controller = yield* GraphLoopEngineeringController
  const descriptions: ReadonlyArray<readonly [string, Readonly<Record<string, unknown>>]> = [
    ["subject", { role: "subject", description: "A door event is the subject of this bounded fixture." }],
    ["context", { role: "context", booleanFields: { pressed: "Whether the press signal is true.", manualRelease: "Whether the manual-release signal is true.", power: "Whether the power signal is true.", locked: "Whether the lock signal is true." } }],
    ["evidence", { role: "evidence", description: "Observations are attached only after an environment event is recorded." }],
    ["exception", { role: "exception", description: "The exception participant preserves the declared door reference." }]
  ]
  const participants = yield* Effect.forEach(descriptions, ([role, payload]) => runtime.stageContent("application/json", bytes(payload)).pipe(
    Effect.map((content) => Object.freeze({ role, atom: makeAtom(`${role}:door`, "semantic_participant", content) }))
  ))
  const semantic = yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, bytes({
    semanticText: INITIAL_TEXT, disposition: "predict declared door state", uncertainty: "fixture hypothesis",
    exceptionRefs: ["exception:door"], trace: null, outcome: null
  }))
  const relation = makeAtom(relationUid, "semantic_relation", semantic, participants.map((participant) => ({
    referenceType: roleReferenceType, role: participant.role, target: participant.atom.key
  })))
  const writes = [...participants.map((participant) => participant.atom), relation]
  const bindings = yield* Either.all(writes.map(contentBinding))
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "seed:semantic-lifecycle", expectedStateRevision: 0, schemaVersion,
    actorClaim: "fixture:semantic-lifecycle", authorizationRef, scope, decidedAt: "2026-09-27T00:00:00.000Z",
    traceRef: null, readSet: [], writes, provenanceSha256: sha(bytes(writes.map((write) => write.key)))
  }, bindings)
  const stage = (value: Readonly<Record<string, unknown>>) => runtime.stageContent("application/json", bytes(value))
  const action = yield* stage({ purpose: "initialize bounded semantic fixture", transitionId: "seed:semantic-lifecycle", writes: writes.map((write) => write.key) })
  const verifier = yield* stage({ decision: "ACCEPT", check: "mechanical schema and content binding only", semanticCorrectness: "NOT_ADJUDICATED", efficacy: "NOT_ADJUDICATED" })
  const evidence = yield* stage({ purpose: "local fixture bootstrap", causalCredit: "NOT_ESTABLISHED", authorization: "LOCAL_FIXTURE_REFERENCE_GRANT_NOT_CANONICAL_PERMIT" })
  const runId = "run:seed:semantic-lifecycle"
  yield* controller.trigger({ runId, triggerId: "trigger:seed:semantic-lifecycle", actorId: "fixture:semantic-lifecycle", verifierId: "fixture:mechanical-controller", maximumAttempts: 1, maximumActions: 1 })
  yield* controller.sealAction(runId, action)
  yield* controller.recordVerification(runId, "ACCEPT", verifier)
  const result = yield* controller.submitDelta({
    runId, transactionId: "seed:semantic-lifecycle",
    affectedKeys: [], // Genesis creates keys; there are no existing match/read keys.
    candidate,
    evidence: { sealedTrajectory: evidence, outcome: verifier, credit: evidence, authorization: evidence, invariant: evidence, authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT", conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP" }
  })
  if (result.disposition !== "COMMITTED" || result.evolution === null) {
    return yield* lifecycleError("BOOTSTRAP_NOT_COMMITTED", `graph-loop bootstrap disposition: ${result.disposition}`)
  }
  return result.evolution
})

export const inspectSemanticLifecycleState = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const snapshot = yield* runtime.snapshot
  const frame = yield* readLlmSemanticFrame(runtime, relationUid, "semantic-lifecycle:inspect")
  return Object.freeze({
    relationKey: frame.relation.key, stateRevision: snapshot.canonical.revision,
    canonicalSha256: sha(JSON.stringify(snapshot.canonical)), semantic: frame.relation.semantic,
    frameSha256: frame.frameSha256,
    roleRefs: frame.roles.map(({ referenceType, role, key, owner: roleOwner, contentSha256 }) => ({ referenceType, role, key, owner: roleOwner, contentSha256 }))
  })
})

/** Mechanical ACCEPT only: its record expressly withholds semantic and causal credit. */
export const admissionForSemanticLifecycle = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  controller: GraphLoopEngineeringController["Type"],
  trace: SemanticTrace,
  outcome: SemanticOutcome,
  label: string
) => Effect.gen(function* () {
  const stage = (value: Readonly<Record<string, unknown>>) => runtime.stageContent("application/json", bytes(value))
  const action = yield* stage({ label, purpose: "bounded semantic revision proposal", traceSha256: trace.traceSha256 })
  const verifier = yield* stage({ label, decision: "ACCEPT", check: "mechanical schema and content binding only", semanticCorrectness: "NOT_ADJUDICATED", efficacy: "NOT_ADJUDICATED" })
  const evidence = yield* stage({ label, traceSha256: trace.traceSha256, outcomeSha256: outcome.outcomeContent.sha256, causalCredit: "NOT_ESTABLISHED", authorization: "LOCAL_FIXTURE_REFERENCE_GRANT_NOT_CANONICAL_PERMIT" })
  return makeLlmSemanticGraphLoopAdmission(controller, {
    contract: { runId: `run:${label}`, triggerId: `trigger:${label}`, actorId: "llm:fixture-operator", verifierId: "fixture:mechanical-controller", maximumAttempts: 1, maximumActions: 1 },
    transactionId: `revision:${label}`, action, verification: { decision: "ACCEPT", outcome: verifier },
    evidence: { sealedTrajectory: evidence, outcome: verifier, credit: evidence, authorization: evidence, invariant: evidence, authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT", conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP" }
  })
})
