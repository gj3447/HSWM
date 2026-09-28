import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import type { AdaptiveHttpClientShape } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput, type CanonicalAtomV2ContentAuthorizationGrant, type CanonicalAtomV2WriteContentBinding } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, type LlmSemanticCell } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { HSWM_SEMANTIC_PROGRAM_KIND, HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, HSWM_SEMANTIC_PROGRAM_OPCODE, HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-program.js"
import { runSemanticProgram } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-program-runtime.js"
import { HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, HSWM_SUPERSEDES_REFERENCE_ROLE, HSWM_SUPERSEDES_REFERENCE_TYPE, type CanonicalAtomV2, type CanonicalAtomV2Key, type CanonicalAtomV2Reference, type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"

const encoder = new TextEncoder()
const schemaVersion = "hswm:test:semantic-program:v1"
const lineageId = "lineage:semantic-program:test"
const authorizationRef = "authorization:semantic-program:test"
const scope = "scope:semantic-program:test"
const owner = "owner:semantic-program"
const semanticRole = "hswm:semantic:role"
const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({ schemaVersion, lineageId, atomUid, revisionId })

const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2", contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, schemaVersion,
  scientificStatus: "UNJUDGED", bootstrapTrustStatement: "Bounded graph-program test fixture; no learning or efficacy claim.",
  owners: [{ address: owner, obligation: "Owns fixture graph program and relations." }],
  kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: [owner], minimumArity: 0, referenceContracts: [] },
    { kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 3, referenceContracts: [
      { referenceType: semanticRole, roles: ["subject", "context", "evidence"].map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 1 })) },
      { referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, roles: [{ role: HSWM_SUPERSEDES_REFERENCE_ROLE, targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }
    ] },
    { kind: HSWM_SEMANTIC_PROGRAM_KIND, form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 1, referenceContracts: [
      { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, roles: ["a", "b"].map(role => ({ role, targetKinds: ["semantic_relation"], minimum: role === "a" ? 1 : 0, maximum: 1 })) },
      { referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, roles: [{ role: HSWM_SUPERSEDES_REFERENCE_ROLE, targetKinds: [HSWM_SEMANTIC_PROGRAM_KIND], minimum: 0, maximum: 1 }] }
    ] }
  ]
}
const schemaBytes = canonicalAtomV2SchemaContentBytes(schema)
if (Either.isLeft(schemaBytes)) throw new Error("fixture schema invalid")
const schemaContent = decodeCanonicalAtomV2SchemaContent(schemaBytes.right)
if (Either.isLeft(schemaContent)) throw new Error("fixture schema unbound")
const grants = (): ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> => [{ authorizationRef, schemaVersion, schemaContentSha256: schemaContent.right.binding.content.sha256, scopes: [scope] }]
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "journal:semantic-program:test", schemaBytes.right, grants())

const atom = (uid: string, kind: string, content: CanonicalAtomV2["content"], references: ReadonlyArray<CanonicalAtomV2Reference> = [], revisionId = 0, observedAfterBootstrap = false): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key(uid, revisionId), kind,
  responsibilityOwner: owner, content, provenance: revisionId === 0 ? (observedAfterBootstrap ? { mode: "OBSERVATION", evidenceSha256: "a".repeat(64), sourceRef: null } : { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }) : { mode: "DERIVATION", evidenceSha256: "b".repeat(64), sourceRef: key(uid, revisionId - 1) },
  lifecycle: "ADMITTED", references
})
const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => {
  const described = describeCanonicalAtomV2Envelope(value)
  if (Either.isLeft(described)) throw new Error("fixture envelope invalid")
  return { key: value.key, payload: value.content, envelope: described.right }
}
const relationPayload = (label: string) => ({ semanticText: `semantic ${label}`, disposition: "fixture", uncertainty: "unknown", exceptionRefs: [], trace: null, outcome: null })
const semanticRefs = (subject: CanonicalAtomV2, context: CanonicalAtomV2, evidence: CanonicalAtomV2): ReadonlyArray<CanonicalAtomV2Reference> => ["subject", "context", "evidence"].map((role, index) => ({ referenceType: semanticRole, role, target: [subject, context, evidence][index]!.key }))
const programContent = (roles: ReadonlyArray<"a" | "b">) => ({ contract: "hswm-semantic-program/v1", steps: roles.map(role => ({ role, event: `event:${role}`, kernelId: "kernel:fixture", opcode: HSWM_SEMANTIC_PROGRAM_OPCODE })) })

const submit = (runtime: CanonicalAtomV2DurableRuntime["Type"], writes: ReadonlyArray<CanonicalAtomV2>, transitionId: string, readSet: ReadonlyArray<CanonicalAtomV2Key> = []) => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  return yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId,
    expectedStateRevision: snapshot.canonical.revision, schemaVersion, actorClaim: "fixture:semantic-program", authorizationRef, scope,
    decidedAt: "2026-09-28T00:00:00.000Z", traceRef: null, readSet, writes, provenanceSha256: "c".repeat(64)
  }, writes.map(binding)))
})

const seed = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const subject = atom("subject", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("subject")))
  const context = atom("context", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("context")))
  const evidence = atom("evidence", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("evidence")))
  const a = atom("relation:a", "semantic_relation", yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, encoder.encode(JSON.stringify(relationPayload("a")))), semanticRefs(subject, context, evidence))
  const b = atom("relation:b", "semantic_relation", yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, encoder.encode(JSON.stringify(relationPayload("b")))), semanticRefs(subject, context, evidence))
  const program = atom("program:order", HSWM_SEMANTIC_PROGRAM_KIND, yield* runtime.stageContent(HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, encoder.encode(JSON.stringify(programContent(["a", "b"])))), [
    { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "a", target: a.key },
    { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "b", target: b.key }
  ])
  yield* submit(runtime, [subject, context, evidence, a, b, program], "seed:semantic-program")
})

const cell: LlmSemanticCell = { base_url: "https://fixture.invalid/v1", model: "fixture", max_tokens: 64 }
const noSubprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die("fixture does not launch subprocesses") }))
const response = () => encoder.encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "fixture", uncertainty: "fixture" }) } }] }))
const withRoot = <A, E, R>(use: (root: string) => Effect.Effect<A, E, R>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-semantic-program-"))
  return use(root).pipe(Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}

it.effect("uses a durable program revision to change invocation order after reopen without changing host code", () => withRoot(root => {
  const events: string[] = []
  const models: string[] = []
  const liveCell = { ...cell }
  const http: AdaptiveHttpClientShape = { postJson: request => Effect.sync(() => {
    const outer = JSON.parse(new TextDecoder().decode(request.body)) as { messages: Array<{ content: string }> }
    const prompt = JSON.parse(outer.messages[0]!.content) as { frame: { event: string } }
    events.push(prompt.frame.event)
    models.push((outer as { model?: string }).model ?? "")
    if (events.length === 1) liveCell.model = "mutated-after-first-request"
    return response()
  }) }
  const run = () => runSemanticProgram({ programUid: "program:order", maximumSteps: 2, http, kernels: { "kernel:fixture": liveCell } })
  return seed.pipe(
    Effect.provide(layer(root)),
    Effect.andThen(Effect.gen(function* () {
      const first = yield* run()
      expect(first.traces.map(row => row.role)).toEqual(["a", "b"])
      expect(first.programKey.revisionId).toBe(0)
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const state = yield* runtime.snapshot
      const previous = state.canonical.atoms.find(value => value.key.atomUid === "program:order" && value.key.revisionId === 0)!
      const a = state.canonical.atoms.find(value => value.key.atomUid === "relation:a")!
      const b = state.canonical.atoms.find(value => value.key.atomUid === "relation:b")!
      const revised = atom("program:order", HSWM_SEMANTIC_PROGRAM_KIND, yield* runtime.stageContent(HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, encoder.encode(JSON.stringify(programContent(["b", "a"])))), [
        { referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, role: HSWM_SUPERSEDES_REFERENCE_ROLE, target: previous.key },
        { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "b", target: b.key },
        { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "a", target: a.key }
      ], 1)
      yield* submit(runtime, [revised], "revise:semantic-program", [previous.key, a.key, b.key])
    }).pipe(Effect.provide(layer(root)))),
    Effect.andThen(run().pipe(Effect.provide(layer(root)))),
    Effect.tap(second => Effect.sync(() => {
      expect(second.programKey.revisionId).toBe(1)
      expect(second.traces.map(row => row.role)).toEqual(["b", "a"])
      expect(events).toEqual(["event:a", "event:b", "event:b", "event:a"])
      expect(models.slice(0, 2)).toEqual(["fixture", "fixture"])
    }))
  )
}).pipe(Effect.provide(noSubprocess)))

it.effect("rejects invalid program content before a network call and stops before a later dispatch when graph state drifts", () => withRoot(root => {
  let calls = 0
  const http: AdaptiveHttpClientShape = { postJson: () => Effect.sync(() => { calls += 1; return response() }) }
  return seed.pipe(Effect.provide(layer(root)), Effect.andThen(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const invalid = yield* runtime.stageContent(HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, encoder.encode(JSON.stringify({ contract: "hswm-semantic-program/v1", steps: [{ role: "a", event: "e", kernelId: "kernel:fixture", opcode: "UNKNOWN" }, { role: "b", event: "e", kernelId: "kernel:fixture", opcode: HSWM_SEMANTIC_PROGRAM_OPCODE }] })))
    const a = (yield* runtime.snapshot).canonical.atoms.find(value => value.key.atomUid === "relation:a")!
    const b = (yield* runtime.snapshot).canonical.atoms.find(value => value.key.atomUid === "relation:b")!
    const bad = atom("program:bad", HSWM_SEMANTIC_PROGRAM_KIND, invalid, [
      { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "a", target: a.key },
      { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "b", target: b.key }
    ], 0, true)
    yield* submit(runtime, [bad], "seed:bad-program", [a.key, b.key])
    const outOfOrder = atom("program:out-of-order", HSWM_SEMANTIC_PROGRAM_KIND, yield* runtime.stageContent(HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, encoder.encode(JSON.stringify(programContent(["a", "b"])))), [
      { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "b", target: b.key },
      { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "a", target: a.key }
    ], 0, true)
    yield* submit(runtime, [outOfOrder], "seed:out-of-order-program", [a.key, b.key])
    const rejected = yield* runSemanticProgram({ programUid: "program:bad", maximumSteps: 2, http, kernels: { "kernel:fixture": cell } }).pipe(Effect.either)
    const rejectedOrder = yield* runSemanticProgram({ programUid: "program:out-of-order", maximumSteps: 2, http, kernels: { "kernel:fixture": cell } }).pipe(Effect.either)
    expect(Either.isLeft(rejected)).toBe(true)
    expect(Either.isLeft(rejectedOrder)).toBe(true)
    expect(calls).toBe(0)
    let drifted = false
    const driftingHttp: AdaptiveHttpClientShape = { postJson: () => Effect.gen(function* () {
      calls += 1
      if (!drifted) {
        drifted = true
        const current = yield* runtime.snapshot.pipe(Effect.orDie)
        const prior = current.canonical.atoms.find(value => value.key.atomUid === "relation:a")!
        const successor = atom("relation:a", "semantic_relation", yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, encoder.encode(JSON.stringify(relationPayload("drift")))).pipe(Effect.orDie), [
          { referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, role: HSWM_SUPERSEDES_REFERENCE_ROLE, target: prior.key },
          ...prior.references.filter(ref => ref.referenceType !== HSWM_SUPERSEDES_REFERENCE_TYPE)
        ], 1)
        yield* submit(runtime, [successor], "drift:relation", [prior.key, ...prior.references.map(ref => ref.target)]).pipe(Effect.orDie)
      }
      return response()
    }) }
    const stopped = yield* runSemanticProgram({ programUid: "program:order", maximumSteps: 2, http: driftingHttp, kernels: { "kernel:fixture": cell } }).pipe(Effect.either)
    expect(Either.isLeft(stopped)).toBe(true)
    expect(calls).toBe(1)
    const stale = yield* runSemanticProgram({ programUid: "program:order", maximumSteps: 2, http, kernels: { "kernel:fixture": cell } }).pipe(Effect.either)
    expect(Either.isLeft(stale)).toBe(true)
    expect(calls).toBe(1)

    const afterDrift = (yield* runtime.snapshot).canonical.atoms.find(value => value.key.atomUid === "relation:a" && value.key.revisionId === 1)!
    const finalProgram = atom("program:final", HSWM_SEMANTIC_PROGRAM_KIND, yield* runtime.stageContent(HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, encoder.encode(JSON.stringify(programContent(["a"])))), [
      { referenceType: HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE, role: "a", target: afterDrift.key }
    ], 0, true)
    yield* submit(runtime, [finalProgram], "seed:final-program", [afterDrift.key])
    let finalCalls = 0
    const finalDriftHttp: AdaptiveHttpClientShape = { postJson: () => Effect.gen(function* () {
      finalCalls += 1
      const current = yield* runtime.snapshot.pipe(Effect.orDie)
      const prior = current.canonical.atoms.find(value => value.key.atomUid === "relation:a" && value.key.revisionId === 1)!
      const successor = atom("relation:a", "semantic_relation", yield* runtime.stageContent(HSWM_LLM_SEMANTIC_RELATION_MEDIA_TYPE, encoder.encode(JSON.stringify(relationPayload("final-drift")))).pipe(Effect.orDie), [
        { referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, role: HSWM_SUPERSEDES_REFERENCE_ROLE, target: prior.key },
        ...prior.references.filter(ref => ref.referenceType !== HSWM_SUPERSEDES_REFERENCE_TYPE)
      ], 2)
      yield* submit(runtime, [successor], "drift:final-relation", [prior.key, ...prior.references.map(ref => ref.target)]).pipe(Effect.orDie)
      return response()
    }) }
    const finalStopped = yield* runSemanticProgram({ programUid: "program:final", maximumSteps: 1, http: finalDriftHttp, kernels: { "kernel:fixture": cell } }).pipe(Effect.either)
    expect(Either.isLeft(finalStopped)).toBe(true)
    expect(finalCalls).toBe(1)
  }).pipe(Effect.provide(layer(root)))))
}).pipe(Effect.provide(noSubprocess)))
