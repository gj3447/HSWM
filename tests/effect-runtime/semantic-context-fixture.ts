import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect, Either } from "effect"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { type ContextPlan, type ContextSpec } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"

export const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2", contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: "context-test-v1", scientificStatus: "UNJUDGED", bootstrapTrustStatement: "SCRIPTED_TEST_ONLY",
  owners: [{ address: "owner:context-test", obligation: "Test fixture" }],
  kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: ["owner:context-test"], minimumArity: 0, referenceContracts: [] },
    { kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: ["owner:context-test"], minimumArity: 4,
      referenceContracts: [{ referenceType: "hswm:semantic:role", roles: ["subject", "context", "evidence", "exception"].map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 2 })) },
        { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }] }
  ]
}
export const key = (atomUid: string) => ({ schemaVersion: schema.schemaVersion, lineageId: "context-fixture", atomUid, revisionId: 0 })
export const spec: ContextSpec = {
  contract: "hswm-semantic-context-spec/v1", event: "문을 열 수 있는지 예외까지 확인해",
  mandatoryRelationUids: ["relation:mandatory"], candidates: [
    { id: "door", summary: "문 열기: 열쇠와 권한, 파손 예외", relationUids: ["relation:door", "relation:companion"] },
    { id: "calendar", summary: "일정 날짜 계산", relationUids: ["relation:calendar"] }
  ], maximumContextBytes: 65536, minimumConfidence: 0.5, minimumMargin: 0.1
}
export const unwrap = <A, E>(value: Either.Either<A, E>): A => { if (Either.isLeft(value)) throw value.left; return value.right }
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
const schemaBinding = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes))
export const fileLayer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "context-journal", schemaBytes, [{
  authorizationRef: "fixture-auth", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaBinding.binding.content.sha256, scopes: ["fixture"]
}])
export const seedContext = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const writes: CanonicalAtomV2[] = []
  for (const name of ["mandatory", "door", "companion", "calendar"]) {
    const participants: CanonicalAtomV2[] = []
    for (const role of ["subject", "context", "evidence", "exception"]) {
      const content = yield* runtime.stageContent("text/plain", new TextEncoder().encode(`${name} ${role}: complete source — 예외 보존`))
      participants.push({ _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key(`${name}:${role}`), kind: "semantic_participant", responsibilityOwner: "owner:context-test", content,
        provenance: { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }, lifecycle: "ADMITTED", references: [] })
    }
    const payload = { semanticText: name === "door" ? "Allow only with valid key; deny broken key." : `${name} relation`, disposition: "predict", uncertainty: "unknown", exceptionRefs: [`${name}:exception`], trace: null, outcome: null }
    const content = yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", new TextEncoder().encode(JSON.stringify(payload)))
    const relation: CanonicalAtomV2 = { _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: key(`relation:${name}`), kind: "semantic_relation", responsibilityOwner: "owner:context-test", content,
      provenance: { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }, lifecycle: "ADMITTED",
      references: participants.map((p, index) => ({ referenceType: "hswm:semantic:role", role: ["subject", "context", "evidence", "exception"][index] ?? "invalid", target: p.key })) }
    writes.push(...participants, relation)
  }
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, transitionId: "seed-context", expectedStateRevision: 0, schemaVersion: schema.schemaVersion,
    actorClaim: "test-fixture", authorizationRef: "fixture-auth", scope: "fixture", decidedAt: "2026-10-09T00:00:00.000Z", traceRef: null, readSet: [], writes, provenanceSha256: "a".repeat(64)
  }, writes.map(atom => ({ key: atom.key, payload: atom.content, envelope: unwrap(describeCanonicalAtomV2Envelope(atom)) }))))
  return runtime
})
export const withContextFixture = <A, E, R>(use: (runtime: CanonicalAtomV2DurableRuntime["Type"], root: string) => Effect.Effect<A, E, R>) =>
  Effect.acquireUseRelease(Effect.sync(() => mkdtempSync(join(tmpdir(), "hswm-context-"))), root =>
    seedContext.pipe(Effect.flatMap(runtime => use(runtime, root)), Effect.provide(fileLayer(root))),
  root => Effect.sync(() => rmSync(root, { recursive: true, force: true })))

export const decisionFor = (plan: ContextPlan, choice = "door") => {
  const options = [...plan.spec.candidates.map(c => c.id), "NONE", "NEED_MORE"]
  return { schema: "jev-result/v1", backend: "kotoba-open-jev", model: "SCRIPTED_FIXTURE_NOT_MODEL_INFERENCE", revision: "fixture-v1", requestSha256: plan.requestSha256,
    authority: "advisory", weightUpdate: null, officialTypeSafeJev: false, truncated: false, status: "candidate",
    decisions: [{ id: "context", type: "choice", choice, probabilities: Object.fromEntries(options.map(o => [o, o === choice ? 0.85 : 0.15/(options.length-1)])), confidence: 0.85 }] }
}
