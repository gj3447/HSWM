import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import { type AdaptiveHttpClientShape } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { canonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput, canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, type CanonicalAtomV2WriteContentBinding } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { executeCrossLayerMapRelation, createCrossLayerMapSchema, prepareCrossLayerMapBindingSuccessor, stageCrossLayerMapInput, CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE } from "../../src/hswm/effect-runtime/src/cross-layer-map-runtime.js"
import { makeGraphLoopControlJournalFileLayer, makeGraphLoopEngineeringControllerLayer, GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { makeLlmSemanticGraphLoopAdmission } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-graph-loop-admission.js"
import { learnLlmSemanticRelation, readLlmSemanticFrame, stageLlmSemanticOutcome } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type CanonicalAtomV2Key } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"

const encoder = new TextEncoder()
const schemaVersion = "hswm:test:cross-layer-map:v1", lineageId = "lineage:cross-layer-map", owner = "owner:cross-layer-map", authorizationRef = "authorization:cross-layer-map", scope = "scope:cross-layer-map"
const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({ schemaVersion, lineageId, atomUid, revisionId })
const schema = createCrossLayerMapSchema(schemaVersion, owner)
const schemaBytes = canonicalAtomV2SchemaContentBytes(schema)
if (Either.isLeft(schemaBytes)) throw new Error("cross-layer schema")
const schemaContent = decodeCanonicalAtomV2SchemaContent(schemaBytes.right)
if (Either.isLeft(schemaContent)) throw new Error("cross-layer schema content")

const layer = (root: string) => {
  const runtime = makeCanonicalAtomV2DurableRuntimeFileLayer(root, "journal:cross-layer-map", schemaBytes.right, [{ authorizationRef, schemaVersion, schemaContentSha256: schemaContent.right.binding.content.sha256, scopes: [scope] }])
  const journal = makeGraphLoopControlJournalFileLayer(join(root, "loop"))
  return Layer.mergeAll(runtime, journal, makeGraphLoopEngineeringControllerLayer.pipe(Layer.provide([runtime, journal])))
}
const withRoot = <A, E, R>(run: (root: string) => Effect.Effect<A, E, R>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-cross-layer-"))
  return run(root).pipe(Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}
const packet = (eventTime: number, start = eventTime): object => ({
  subject: { observation: { r: 0, h: 0 }, asOf: eventTime - 1, requested: { action: "pulse", horizon: 1, window: { start, end: start + 1 } } },
  context: { schema: "hswm-cross-layer-map/v1", source: { modelRef: "toy:r-h", digest: "a".repeat(64) }, target: { modelRef: "toy:semantic", digest: "b".repeat(64) }, mappingKind: "preserve_r_h", mappingMethod: "authored_deterministic", declaredLosses: [], actionAllowlist: ["pulse"], time: { unit: "tick", horizon: 1 }, supportScope: { world: "finite-toy-rh/v1", contexts: ["fixture"], observableFields: ["r", "h"] } },
  evidence: [{ sourceRef: "fixture:past", digest: "c".repeat(64), observedAt: eventTime - 1 }], eventTime
})
const binding = (atom: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => {
  const envelope = describeCanonicalAtomV2Envelope(atom); if (Either.isLeft(envelope)) throw new Error("envelope")
  return { key: atom.key, payload: atom.content, envelope: envelope.right }
}
const response = (value: unknown): Uint8Array => encoder.encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))
const cell = { base_url: "https://fixture.invalid/v1", model: "fixture", max_tokens: 32 }
const noSubprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die("cross-layer fixture must not launch a subprocess") }))

const seed = (maliciousSubject = false) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const staged = yield* stageCrossLayerMapInput(runtime, packet(2), { subject: key("subject:0"), context: key("context:map:0"), evidence: key("evidence:0") }, owner)
  const maliciousBytes = canonicalJsonBytes({ subject: { observation: { r: 0, h: 0 }, asOf: 1, requested: { action: "pulse", horizon: 1, window: { start: 2, end: 3 } } }, eventTime: 2, future_target: 1 })
  if (Either.isLeft(maliciousBytes)) throw new Error("malicious fixture canonical bytes")
  const subject = maliciousSubject
    ? { ...staged.participants.subject, content: yield* runtime.stageContent("application/vnd.hswm.cross-layer-map-participant-v1+json", maliciousBytes.right) }
    : staged.participants.subject
  const exceptionContent = yield* runtime.stageContent("application/json", encoder.encode(JSON.stringify({ exception: "none" })))
  const exception: CanonicalAtomV2 = { _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key("exception:fixed"), kind: "semantic_participant", responsibilityOwner: owner, content: exceptionContent, provenance: { mode: "BOOTSTRAP", evidenceSha256: exceptionContent.sha256, sourceRef: null }, lifecycle: "ADMITTED", references: [] }
  const semantic = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", encoder.encode(JSON.stringify({ semanticText: "map r and h under permitted pulse", disposition: "fixture", uncertainty: "unknown", exceptionRefs: ["exception:fixed"], trace: null, outcome: null })))
  const relation: CanonicalAtomV2 = { _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key("relation:map"), kind: "semantic_relation", responsibilityOwner: owner, content: semantic, provenance: { mode: "BOOTSTRAP", evidenceSha256: semantic.sha256, sourceRef: null }, lifecycle: "ADMITTED", references: ["subject", "context", "evidence", "exception"].map((role, index) => ({ referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role, target: [subject, staged.participants.context, staged.participants.evidence, exception][index]!.key })) }
  const writes = [subject, staged.participants.context, staged.participants.evidence, exception, relation]
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, { _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: "seed:cross-layer", expectedStateRevision: 0, schemaVersion, actorClaim: "fixture:seed", authorizationRef, scope, decidedAt: "2026-09-27T00:00:00.000Z", traceRef: null, readSet: [], writes, provenanceSha256: "d".repeat(64) }, writes.map(binding)))
})

it.effect("revises v1 semantic text, then explicitly binds fresh map input for the next read", () =>
  withRoot((root) => seed().pipe(Effect.provide(layer(root)), Effect.andThen(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime, controller = yield* GraphLoopEngineeringController
    let calls = 0
    const http: AdaptiveHttpClientShape = { postJson: () => Effect.succeed(response(++calls === 1 ? { prediction: "fire", uncertainty: "u" } : { semanticText: "revised from observed toy outcome", disposition: "updated", uncertainty: "u", exceptionRefs: ["exception:fixed"] })) }
    const trace = yield* executeCrossLayerMapRelation(runtime, "relation:map", "event:2", cell, http)
    const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "observed:fire", "fixture:toy")
    const action = yield* runtime.stageContent("application/json", encoder.encode("action")), verifier = yield* runtime.stageContent("application/json", encoder.encode("verifier")), evidence = yield* runtime.stageContent("application/json", encoder.encode("evidence"))
    const admission = makeLlmSemanticGraphLoopAdmission(controller, { contract: { runId: "semantic", triggerId: "semantic:trigger", actorId: "fixture:actor", verifierId: "fixture:verifier", maximumAttempts: 1, maximumActions: 2 }, transactionId: "semantic:tx", action, verification: { decision: "ACCEPT", outcome: verifier }, evidence: { sealedTrajectory: evidence, outcome: verifier, credit: evidence, authorization: evidence, invariant: evidence, authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT", conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP" } })
    expect((yield* learnLlmSemanticRelation(runtime, trace, outcome, cell, http, authorizationRef, scope, "2026-09-27T00:00:01.000Z", admission)).disposition).toBe("COMMITTED")
    expect(Either.isLeft(yield* executeCrossLayerMapRelation(runtime, "relation:map", "event:repeat", cell, http).pipe(Effect.either))).toBe(true)
    expect(calls).toBe(2)
    const fresh = yield* stageCrossLayerMapInput(runtime, packet(4), { subject: key("subject:1"), context: key("context:map:0"), evidence: key("evidence:1") }, owner)
    const added = [fresh.participants.subject, fresh.participants.evidence]
    const state = yield* runtime.snapshot
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, { _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: "add:fresh-input", expectedStateRevision: state.canonical.revision, schemaVersion, actorClaim: "fixture:input", authorizationRef, scope, decidedAt: "2026-09-27T00:00:02.000Z", traceRef: null, readSet: [], writes: added, provenanceSha256: "e".repeat(64) }, added.map(binding)))
    const proposal = yield* prepareCrossLayerMapBindingSuccessor(runtime, { relationUid: "relation:map", subject: fresh.participants.subject.key, context: key("context:map:0"), evidence: fresh.participants.evidence.key, authorizationRef, scope, decidedAt: "2026-09-27T00:00:03.000Z" })
    yield* runtime.submit(proposal.candidate)
    const reopened = yield* readLlmSemanticFrame(runtime, "relation:map", "event:3")
    expect(reopened.relation.semantic.semanticText).toBe("revised from observed toy outcome")
    expect(reopened.roles.map((role) => role.key.atomUid)).toEqual(["subject:1", "context:map:0", "evidence:1", "exception:fixed"])
  }).pipe(Effect.provide(layer(root)))))).pipe(Effect.provide(noSubprocess))
)

it.effect("refuses an already-admitted subject wrapper carrying a future target before HTTP", () =>
  withRoot((root) => seed(true).pipe(Effect.provide(layer(root)), Effect.andThen(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    let calls = 0
    const http: AdaptiveHttpClientShape = { postJson: () => { calls += 1; return Effect.die("must not transport") } }
    expect(Either.isLeft(yield* executeCrossLayerMapRelation(runtime, "relation:map", "event:malicious", cell, http).pipe(Effect.either))).toBe(true)
    expect(calls).toBe(0)
  }).pipe(Effect.provide(layer(root)))))).pipe(Effect.provide(noSubprocess))
)

it.effect("rejects future evidence before any model HTTP call", () =>
  withRoot((root) => Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const invalid = { ...packet(2), evidence: [{ sourceRef: "fixture:future", digest: "c".repeat(64), observedAt: 2 }] }
    const result = yield* stageCrossLayerMapInput(runtime, invalid, { subject: key("bad:subject"), context: key("bad:context"), evidence: key("bad:evidence") }, owner).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
  }).pipe(Effect.provide(layer(root))))
)

it.effect("rejects a prepared binding candidate after a later canonical commit", () =>
  withRoot((root) => seed().pipe(Effect.provide(layer(root)), Effect.andThen(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const first = yield* stageCrossLayerMapInput(runtime, packet(3), { subject: key("stale:subject:1"), context: key("context:map:0"), evidence: key("stale:evidence:1") }, owner)
    const firstWrites = [first.participants.subject, first.participants.evidence]
    let state = yield* runtime.snapshot
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, { _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: "stale:add:first", expectedStateRevision: state.canonical.revision, schemaVersion, actorClaim: "fixture:input", authorizationRef, scope, decidedAt: "2026-09-27T00:00:02.000Z", traceRef: null, readSet: [], writes: firstWrites, provenanceSha256: "e".repeat(64) }, firstWrites.map(binding)))
    const proposal = yield* prepareCrossLayerMapBindingSuccessor(runtime, { relationUid: "relation:map", subject: first.participants.subject.key, context: key("context:map:0"), evidence: first.participants.evidence.key, authorizationRef, scope, decidedAt: "2026-09-27T00:00:03.000Z" })
    const later = yield* stageCrossLayerMapInput(runtime, packet(4), { subject: key("stale:subject:2"), context: key("context:map:0"), evidence: key("stale:evidence:2") }, owner)
    state = yield* runtime.snapshot
    yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, { _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: "stale:add:later", expectedStateRevision: state.canonical.revision, schemaVersion, actorClaim: "fixture:input", authorizationRef, scope, decidedAt: "2026-09-27T00:00:04.000Z", traceRef: null, readSet: [], writes: [later.participants.subject], provenanceSha256: "f".repeat(64) }, [binding(later.participants.subject)]))
    expect(Either.isLeft(yield* runtime.submit(proposal.candidate).pipe(Effect.either))).toBe(true)
  }).pipe(Effect.provide(layer(root))))))
)
