import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import {
  GraphLoopControlError,
  GraphLoopControlJournal,
  GraphLoopControlJournalError,
  GraphLoopEngineeringController,
  HSWM_GRAPH_LOOP_CONTROL_JOURNAL_V1_MEDIA_TYPE,
  makeGraphLoopControlJournalFileLayer,
  makeGraphLoopEngineeringControllerLayer
} from "../src/canonical-atom-v2-graph-loop-engineering.js"
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"
import type { CanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"

const SCHEMA_VERSION = "hswm:test:graph-loop:v2"
const JOURNAL_LINEAGE = "journal:graph-loop:main"
const AUTHORIZATION = "authorization:graph-loop"
const SCOPE = "scope:graph-loop"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const rightOrThrow = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("fixture construction failed")
  return value.right
}

const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId: "lineage:graph-loop",
  atomUid,
  revisionId
})

const schema = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Fixture bootstrap is bounded and non-scientific.",
  owners: [{ address: "owner:graph", obligation: "Own graph atom revisions and provenance." }],
  kinds: ["kind:graph", "kind:trace"].map((kind) => ({
    kind,
    form: "ENTITY" as const,
    revisionPolicy: "LINEAR" as const,
    allowedOwners: ["owner:graph"],
    minimumArity: 0,
    referenceContracts: [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      roles: [{
        role: HSWM_SUPERSEDES_REFERENCE_ROLE,
        targetKinds: [kind],
        minimum: 0,
        maximum: 1
      }]
    }]
  }))
})

const rawSchema = (): Uint8Array => utf8(JSON.stringify(schema()))

const grants = (): ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> => [{
  authorizationRef: AUTHORIZATION,
  schemaVersion: SCHEMA_VERSION,
  schemaContentSha256: rightOrThrow(decodeCanonicalAtomV2SchemaContent(rawSchema())).binding.content.sha256,
  scopes: [SCOPE]
}]

const atom = (
  atomUid: string,
  content: CanonicalAtomV2ContentDescriptor,
  revisionId = 0
): CanonicalAtomV2 => {
  const predecessor = revisionId === 0 ? null : key(atomUid, revisionId - 1)
  return {
    _tag: "CanonicalAtomV2",
    contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: key(atomUid, revisionId),
    kind: atomUid === "trace" ? "kind:trace" : "kind:graph",
    responsibilityOwner: "owner:graph",
    content,
    provenance: predecessor === null
      ? { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }
      : { mode: "DERIVATION", evidenceSha256: "b".repeat(64), sourceRef: predecessor },
    lifecycle: "ADMITTED",
    references: predecessor === null ? [] : [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      role: HSWM_SUPERSEDES_REFERENCE_ROLE,
      target: predecessor
    }]
  }
}

const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({
  key: value.key,
  payload: value.content,
  envelope: rightOrThrow(describeCanonicalAtomV2Envelope(value))
})

const command = (
  transitionId: string,
  expectedStateRevision: number,
  writes: ReadonlyArray<CanonicalAtomV2>,
  readSet: ReadonlyArray<CanonicalAtomV2Key>,
  traceRef: CanonicalAtomV2Key | null
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId,
  expectedStateRevision,
  schemaVersion: SCHEMA_VERSION,
  actorClaim: "actor:graph-loop",
  authorizationRef: AUTHORIZATION,
  scope: SCOPE,
  decidedAt: "2026-09-01T00:00:00.000Z",
  traceRef,
  readSet,
  writes,
  provenanceSha256: "c".repeat(64)
})

const withRoot = <A, E>(use: (root: string) => Effect.Effect<A, E>): Effect.Effect<A, E> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-graph-loop-"))
  return use(root).pipe(Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}

const layer = (root: string) => {
  const runtime = makeCanonicalAtomV2DurableRuntimeFileLayer(
    join(root, "state"), JOURNAL_LINEAGE, rawSchema(), grants()
  )
  const journal = makeGraphLoopControlJournalFileLayer(join(root, "loop"))
  const controller = makeGraphLoopEngineeringControllerLayer.pipe(
    Layer.provide([runtime, journal])
  )
  return Layer.mergeAll(runtime, journal, controller)
}

const stage = (runtime: CanonicalAtomV2DurableRuntime["Type"], value: string) =>
  runtime.stageContent("application/json", utf8(value))

it.effect("GE-2 commits only after a bounded independently-verifiable loop and restores exact graph payload", () =>
  withRoot((root) => Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const controller = yield* GraphLoopEngineeringController
    const original = yield* stage(runtime, "original-graph")
    const seedGraph = atom("graph", original)
    const schemaContent = rightOrThrow(decodeCanonicalAtomV2SchemaContent(rawSchema())).binding.content.sha256
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(
      schemaContent,
      command("transition:seed", 0, [seedGraph], [], null),
      [binding(seedGraph)]
    ))
    yield* controller.trigger({
      runId: "run:stale",
      triggerId: "trigger:research",
      actorId: "actor:stale",
      verifierId: "verifier:stale",
      maximumAttempts: 1,
      maximumActions: 1
    })
    const staleAction = yield* stage(runtime, "sealed-stale-action")
    const staleOutcome = yield* stage(runtime, "independent-stale-outcome")
    yield* controller.sealAction("run:stale", staleAction)
    yield* controller.recordVerification("run:stale", "ACCEPT", staleOutcome)
    const staleCandidatePayload = yield* stage(runtime, "stale-replacement-graph")
    const externalPayload = yield* stage(runtime, "external-replacement-graph")
    const externalGraph = atom("graph", externalPayload, 1)
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(
      schemaContent,
      command("transition:external", 1, [externalGraph], [key("graph")], null),
      [binding(externalGraph)]
    ))
    const staleGraph = atom("graph", staleCandidatePayload, 1)
    const staleEvidence = yield* stage(runtime, "stale-evidence")
    const quarantined = yield* controller.submitDelta({
      runId: "run:stale",
      transactionId: "transaction:stale",
      affectedKeys: [key("graph")],
      evidence: {
        sealedTrajectory: staleAction,
        outcome: staleOutcome,
        credit: staleEvidence,
        authorization: staleEvidence,
        invariant: staleEvidence,
        authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT",
        conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP"
      },
      candidate: makeCanonicalAtomV2ContentBoundInput(
        schemaContent,
        command("transition:stale", 1, [staleGraph], [key("graph")], null),
        [binding(staleGraph)]
      )
    })
    expect(quarantined.disposition).toBe("QUARANTINED")
    yield* controller.trigger({
      runId: "run:one",
      triggerId: "trigger:research",
      actorId: "actor:one",
      verifierId: "verifier:independent",
      maximumAttempts: 2,
      maximumActions: 2
    })
    const sealedAction = yield* stage(runtime, "sealed-action")
    const outcome = yield* stage(runtime, "independent-outcome")
    yield* controller.sealAction("run:one", sealedAction)
    yield* controller.recordVerification("run:one", "ACCEPT", outcome)
    const replacement = yield* stage(runtime, "replacement-graph")
    const graphV1 = atom("graph", replacement, 2)
    const candidate = makeCanonicalAtomV2ContentBoundInput(
      schemaContent,
      command("transition:replace", 2, [graphV1], [key("graph", 1)], null),
      [binding(graphV1)]
    )
    const evidenceDescriptor = yield* stage(runtime, "evidence")
    const committed = yield* controller.submitDelta({
      runId: "run:one",
      transactionId: "transaction:replace",
      affectedKeys: [key("graph", 1)],
      evidence: {
        sealedTrajectory: sealedAction,
        outcome,
        credit: evidenceDescriptor,
        authorization: evidenceDescriptor,
        invariant: evidenceDescriptor,
        authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT",
        conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP"
      },
      candidate
    })
    if (committed.disposition !== "COMMITTED") {
      const journal = yield* GraphLoopControlJournal
      const events = yield* journal.recover
      return yield* Effect.fail(new Error(`graph transaction rejected: ${events.at(-1)?.event.reason}`))
    }
    expect(committed.disposition).toBe("COMMITTED")
    const restoredGraph = atom("graph", original, 3)
    const restored = yield* controller.restore({
      runId: "run:one",
      transactionId: "transaction:replace",
      sourceKeys: [key("graph")],
      candidate: makeCanonicalAtomV2ContentBoundInput(
        schemaContent,
        command("transition:restore", 3, [restoredGraph], [key("graph"), key("graph", 1), key("graph", 2)], null),
        [binding(restoredGraph)]
      )
    })
    expect(restored.disposition).toBe("COMMITTED")
    yield* controller.stop("run:one", "RESTORE_CONFIRMED")
    const state = yield* controller.recover
    expect(state.get("run:one")?.phase).toBe("STOPPED")
    const graph = yield* runtime.snapshot
    expect(graph.canonical.revision).toBe(4)
    expect(graph.canonical.atoms.find((item) => item.key.atomUid === "graph" && item.key.revisionId === 3)?.content.sha256).toBe(original.sha256)
  }).pipe(Effect.provide(layer(root))))
)

it.effect("LE-0 rejects self-verification, exhausts bounded retries, and recovers a tamper-evident control journal", () =>
  withRoot((root) => Effect.gen(function* () {
    const controller = yield* GraphLoopEngineeringController
    const denied = yield* controller.trigger({
      runId: "run:self",
      triggerId: "trigger:research",
      actorId: "same:principal",
      verifierId: "same:principal",
      maximumAttempts: 1,
      maximumActions: 1
    }).pipe(Effect.flip)
    expect(denied).toBeInstanceOf(GraphLoopControlError)
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* controller.trigger({
      runId: "run:retry",
      triggerId: "trigger:retry",
      actorId: "actor:retry",
      verifierId: "verifier:retry",
      maximumAttempts: 1,
      maximumActions: 1
    })
    const action = yield* stage(runtime, "action")
    const outcome = yield* stage(runtime, "outcome")
    yield* controller.sealAction("run:retry", action)
    yield* controller.recordVerification("run:retry", "RETRY", outcome)
    const exhausted = yield* controller.scheduleRetry("run:retry", "NEED_FRESH_INPUT").pipe(Effect.flip)
    expect(exhausted).toBeInstanceOf(GraphLoopControlError)
    const events = yield* GraphLoopControlJournal
    const recovered = yield* events.recover
    expect(recovered.map(({ event }) => event.phase)).toEqual(["TRIGGERED", "ACTION_SEALED", "VERIFIED_RETRY"])
    expect(recovered[0]?.bytes).toBeInstanceOf(Uint8Array)
  }).pipe(Effect.provide(layer(root))))
)

it.effect("control-journal byte tampering fails closed on recovery", () =>
  withRoot((root) => Effect.gen(function* () {
    const journal = yield* GraphLoopControlJournal
    const snapshot = {
      journalLineageId: "journal:tamper",
      schema: { schemaVersion: "schema:tamper", content: { mediaType: "application/json", byteLength: 1, sha256: "a".repeat(64) } },
      stateRevision: 0,
      stateSha256: "b".repeat(64),
      journalHead: { mediaType: "application/json", byteLength: 1, sha256: "c".repeat(64) },
      compiledProjection: { mediaType: HSWM_GRAPH_LOOP_CONTROL_JOURNAL_V1_MEDIA_TYPE, byteLength: 1, sha256: "d".repeat(64) }
    }
    yield* journal.append({
      runId: "run:tamper", triggerId: "trigger:tamper", actorId: "actor:tamper", verifierId: "verifier:tamper",
      maximumAttempts: 1, maximumActions: 1, attempt: 1, phase: "TRIGGERED", snapshot,
      action: null, outcome: null, verification: "NONE", transactionId: null, transitionId: null, keyIds: [], reason: null
    })
    const eventPath = join(root, "loop", "graph-loop-event-0001.json")
    chmodSync(eventPath, 0o600)
    writeFileSync(eventPath, utf8("{}"))
    const failed = yield* journal.recover.pipe(Effect.flip)
    expect(failed).toBeInstanceOf(GraphLoopControlJournalError)
  }).pipe(Effect.provide(layer(root))))
)
