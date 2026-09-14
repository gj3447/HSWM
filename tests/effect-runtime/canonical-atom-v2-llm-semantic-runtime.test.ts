import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import { type AdaptiveHttpClientShape } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import {
  canonicalAtomV2SchemaContentBytes,
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import {
  executeLlmSemanticRelation,
  learnLlmSemanticRelation,
  readLlmSemanticFrame,
  stageLlmSemanticOutcome,
  type LlmSemanticCell,
  type SemanticOutcome
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CanonicalAtomV2Reference,
  type HSWMCanonicalSchemaV2
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"

const schemaVersion = "hswm:test:llm-semantic-runtime:v1"
const lineageId = "lineage:llm-semantic-runtime:test"
const journalLineage = "journal:llm-semantic-runtime:test"
const authorizationRef = "authorization:llm-semantic-runtime:test"
const scope = "scope:llm-semantic-runtime:test"
const roleReferenceType = "hswm:semantic:role"
const encoder = new TextEncoder()
const decoder = new TextDecoder()

const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key =>
  ({ schemaVersion, lineageId, atomUid, revisionId })

const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "A file-backed, bounded test fixture; no model truth claim.",
  owners: [{ address: "owner:semantic", obligation: "Owns test semantic relation revisions." }],
  kinds: [
    {
      kind: "semantic_participant",
      form: "ENTITY",
      revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:semantic"],
      minimumArity: 0,
      referenceContracts: []
    },
    {
      kind: "semantic_relation",
      form: "RELATION",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:semantic"],
      minimumArity: 4,
      referenceContracts: [{
        referenceType: roleReferenceType,
        roles: ["subject", "context", "evidence", "exception"].map((role) => ({
          role,
          targetKinds: ["semantic_participant"],
          minimum: 1,
          maximum: 1
        }))
      }, {
        referenceType: "hswm:reference:supersedes",
        roles: [{
          role: "hswm:role:predecessor",
          targetKinds: ["semantic_relation"],
          minimum: 0,
          maximum: 1
        }]
      }]
    }
  ]
}

const schemaBytes = canonicalAtomV2SchemaContentBytes(schema)
if (Either.isLeft(schemaBytes)) throw new Error("semantic test schema must be valid")
const schemaContent = decodeCanonicalAtomV2SchemaContent(schemaBytes.right)
if (Either.isLeft(schemaContent)) throw new Error("semantic test schema bytes must bind")

const grants = (): ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> => [{
  authorizationRef,
  schemaVersion,
  schemaContentSha256: schemaContent.right.binding.content.sha256,
  scopes: [scope]
}]

const fileLayer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(
  root,
  journalLineage,
  schemaBytes.right,
  grants()
)

const cell: LlmSemanticCell = {
  base_url: "https://fixture.invalid/v1",
  model: "fixture-semantic-engine",
  max_tokens: 128
}

const noSubprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({
  observe: () => Effect.die("LLM semantic fixture must not launch a subprocess")
}))

const openAiResponse = (content: unknown): Uint8Array => encoder.encode(JSON.stringify({
  choices: [{ message: { content: JSON.stringify(content) } }]
}))

const openAiContent = (content: string): Uint8Array => encoder.encode(JSON.stringify({
  choices: [{ message: { content } }]
}))

const atom = (
  atomUid: string,
  kind: CanonicalAtomV2["kind"],
  content: CanonicalAtomV2["content"],
  references: ReadonlyArray<CanonicalAtomV2Reference> = [],
  revisionId = 0
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid, revisionId),
  kind,
  responsibilityOwner: "owner:semantic",
  content,
  provenance: revisionId === 0
    ? { mode: "BOOTSTRAP", evidenceSha256: "b".repeat(64), sourceRef: null }
    : { mode: "DERIVATION", evidenceSha256: "d".repeat(64), sourceRef: key(atomUid, revisionId - 1) },
  lifecycle: "ADMITTED",
  references
})

const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => {
  const envelope = describeCanonicalAtomV2Envelope(value)
  if (Either.isLeft(envelope)) throw new Error("fixture atom envelope must be valid")
  return { key: value.key, payload: value.content, envelope: envelope.right }
}

const role = (name: string, target: CanonicalAtomV2): CanonicalAtomV2Reference => ({
  referenceType: roleReferenceType,
  role: name,
  target: target.key
})

const semanticPayload = (semanticText: string, exceptionRefs = ["exception:irreversible"]) => ({
  semanticText,
  disposition: "predict-under-context",
  uncertainty: "declared-unknown",
  exceptionRefs,
  trace: null,
  outcome: null
})

const seed = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const subject = atom("subject:sample", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("subject-content")))
  const context = atom("context:sample", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("context-content")))
  const evidence = atom("evidence:sample", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("evidence-content")))
  const exception = atom("exception:irreversible", "semantic_participant", yield* runtime.stageContent("application/json", encoder.encode("exception-content")))
  const relation = atom(
    "relation:sample",
    "semantic_relation",
    yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", encoder.encode(JSON.stringify(semanticPayload("initial semantic text")))),
    [role("subject", subject), role("context", context), role("evidence", evidence), role("exception", exception)]
  )
  const writes = [subject, context, evidence, exception, relation]
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(
    runtime.schemaContent.content.sha256,
    {
      _tag: "CommitCanonicalAtomsV2",
      contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
      transitionId: "seed:llm-semantic-runtime",
      expectedStateRevision: 0,
      schemaVersion,
      actorClaim: "fixture:seed",
      authorizationRef,
      scope,
      decidedAt: "2026-09-14T00:00:00.000Z",
      traceRef: null,
      readSet: [],
      writes,
      provenanceSha256: "a".repeat(64)
    },
    writes.map(binding)
  ))
})

const commitConcurrentRelationRevision = (runtime: CanonicalAtomV2DurableRuntime["Type"]) => Effect.gen(function* () {
  const frame = yield* readLlmSemanticFrame(runtime, "relation:sample", "event:stale")
  const current = yield* runtime.snapshot
  const successor = atom(
    "relation:sample",
    "semantic_relation",
    yield* runtime.stageContent("application/vnd.hswm.llm-semantic-relation-v1+json", encoder.encode(JSON.stringify(semanticPayload("concurrent semantic text")))),
    [
      { referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: frame.relation.key },
      ...frame.roles.map(({ referenceType, role: name, key: target }) => ({ referenceType, role: name, target }))
    ],
    frame.relation.key.revisionId + 1
  )
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(
    runtime.schemaContent.content.sha256,
    {
      _tag: "CommitCanonicalAtomsV2",
      contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
      transitionId: "concurrent:llm-semantic-runtime",
      expectedStateRevision: current.canonical.revision,
      schemaVersion,
      actorClaim: "fixture:concurrent-writer",
      authorizationRef,
      scope,
      decidedAt: "2026-09-14T00:02:00.000Z",
      traceRef: null,
      readSet: [frame.relation.key, ...frame.roles.map(({ key: roleKey }) => roleKey)],
      writes: [successor],
      provenanceSha256: "c".repeat(64)
    },
    [binding(successor)]
  ))
})

const withTemporaryRoot = <A, E, R>(use: (root: string) => Effect.Effect<A, E, R>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-llm-semantic-runtime-"))
  return use(root).pipe(Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}

it.effect("reopens a role-bearing semantic relation and feeds its outcome-conditioned revision back to the next LLM frame", () =>
  withTemporaryRoot((root) => {
    const prompts: unknown[] = []
    const responses = [
      { prediction: "initial prediction", uncertainty: "uncertain" },
      { semanticText: "revised after observed outcome", disposition: "updated-disposition", uncertainty: "less-uncertain", exceptionRefs: ["exception:irreversible"] },
      { prediction: "next prediction", uncertainty: "uncertain" }
    ]
    const http: AdaptiveHttpClientShape = {
      postJson: (request) => Effect.sync(() => {
        prompts.push(JSON.parse(decoder.decode(request.body)))
        return openAiResponse(responses.shift())
      })
    }
    return seed.pipe(
      Effect.provide(fileLayer(root)),
      Effect.andThen(Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const trace = yield* executeLlmSemanticRelation(runtime, "relation:sample", "event:initial", cell, http)
        const firstPrompt = JSON.stringify(prompts[0])
        expect(firstPrompt).toContain("event:initial")
        expect(firstPrompt).toContain("subject-content")
        expect(firstPrompt).toContain("context-content")
        expect(firstPrompt).toContain("evidence-content")
        expect(firstPrompt).toContain("exception-content")
        expect(firstPrompt).toContain("priorEvidence")
        expect(firstPrompt).not.toContain("observed outcome")
        const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "observed outcome", "fixture:outcome")
        yield* learnLlmSemanticRelation(runtime, trace, outcome, cell, http, authorizationRef, scope, "2026-09-14T00:01:00.000Z")
        return { trace, outcome }
      }).pipe(Effect.provide(fileLayer(root)))),
      Effect.flatMap(({ trace, outcome }) => Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const reopened = yield* readLlmSemanticFrame(runtime, "relation:sample", "event:reopened")
        expect(reopened.relation.key.revisionId).toBe(1)
        expect(reopened.relation.semantic.semanticText).toBe("revised after observed outcome")
        expect(reopened.relation.semantic.exceptionRefs).toEqual(["exception:irreversible"])
        expect(reopened.priorEvidence).toEqual({
          prediction: "initial prediction",
          uncertainty: "uncertain",
          observed: "observed outcome",
          source: "fixture:outcome",
          status: "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"
        })
        expect(reopened.roles.map(({ role }) => role).sort()).toEqual(["context", "evidence", "exception", "subject"])
        const secondTrace = yield* executeLlmSemanticRelation(runtime, "relation:sample", "event:reopened", cell, http)
        expect(secondTrace.relationKey.revisionId).toBe(1)
        const nextPrompt = JSON.stringify(prompts[2])
        expect(nextPrompt).toContain("revised after observed outcome")
        expect(nextPrompt).toContain("exception:irreversible")
        expect(nextPrompt).toContain("subject-content")
        expect(nextPrompt).toContain("observed outcome")
        expect(trace.traceSha256).toBe(outcome.traceSha256)
      }).pipe(Effect.provide(fileLayer(root))))
    )
  }).pipe(Effect.provide(noSubprocess))
)

it.effect("rejects forged outcomes and LLM revisions that delete or duplicate exception references", () =>
  withTemporaryRoot((root) => {
    const response = (revision: unknown): AdaptiveHttpClientShape => ({
      postJson: () => Effect.succeed(openAiResponse(revision))
    })
    return seed.pipe(
      Effect.provide(fileLayer(root)),
      Effect.andThen(Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const duplicatePrediction: AdaptiveHttpClientShape = {
          postJson: () => Effect.succeed(openAiContent('{"prediction":"first","prediction":"second","uncertainty":"unknown"}'))
        }
        expect(Either.isLeft(yield* executeLlmSemanticRelation(runtime, "relation:sample", "event:duplicate-prediction", cell, duplicatePrediction).pipe(Effect.either))).toBe(true)
        const trace = yield* executeLlmSemanticRelation(runtime, "relation:sample", "event:negative", cell, response({ prediction: "prediction", uncertainty: "unknown" }))
        const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "observed", "fixture:outcome")
        const forged: SemanticOutcome = { ...outcome, outcomeContent: { sha256: "0".repeat(64), mediaType: outcome.outcomeContent.mediaType, byteLength: outcome.outcomeContent.byteLength } }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, trace, forged, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const forgedCallerOutcome: SemanticOutcome = { ...outcome, observed: "forged observed", source: "forged source" }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, trace, forgedCallerOutcome, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const forgedCallerTrace = { ...trace, prediction: "forged prediction" }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, forgedCallerTrace, outcome, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const forgedUncertainty = { ...trace, uncertainty: "forged uncertainty" }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, forgedUncertainty, outcome, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const forgedBackend = { ...trace, backendConfigurationSha256: "1".repeat(64) }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, forgedBackend, outcome, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const wrongTrace: SemanticOutcome = { ...outcome, traceSha256: "f".repeat(64) }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, trace, wrongTrace, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const badStatus = { ...outcome, status: "FORGED" } as unknown as SemanticOutcome
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, trace, badStatus, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs: ["exception:irreversible"] }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        const duplicateRevision: AdaptiveHttpClientShape = {
          postJson: () => Effect.succeed(openAiContent('{"semanticText":"one","semanticText":"two","disposition":"x","uncertainty":"x","exceptionRefs":["exception:irreversible"]}'))
        }
        expect(Either.isLeft(yield* learnLlmSemanticRelation(runtime, trace, outcome, cell, duplicateRevision, authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either))).toBe(true)
        for (const exceptionRefs of [[], ["exception:irreversible", "exception:irreversible"]]) {
          const rejected = yield* learnLlmSemanticRelation(runtime, trace, outcome, cell, response({ semanticText: "x", disposition: "x", uncertainty: "x", exceptionRefs }), authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either)
          expect(Either.isLeft(rejected)).toBe(true)
        }
      }).pipe(Effect.provide(fileLayer(root))))
    )
  }).pipe(Effect.provide(noSubprocess))
)

it.effect("rejects a relation revision that becomes stale while its LLM revision call is pending", () =>
  withTemporaryRoot((root) => {
    const predictionHttp: AdaptiveHttpClientShape = { postJson: () => Effect.succeed(openAiResponse({ prediction: "prediction", uncertainty: "unknown" })) }
    return seed.pipe(
      Effect.provide(fileLayer(root)),
      Effect.andThen(Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const trace = yield* executeLlmSemanticRelation(runtime, "relation:sample", "event:stale", cell, predictionHttp)
        const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "observed", "fixture:outcome")
        const staleHttp: AdaptiveHttpClientShape = {
          postJson: () => commitConcurrentRelationRevision(runtime).pipe(Effect.orDie, Effect.andThen(openAiResponse({ semanticText: "late", disposition: "late", uncertainty: "late", exceptionRefs: ["exception:irreversible"] })))
        }
        const rejected = yield* learnLlmSemanticRelation(runtime, trace, outcome, cell, staleHttp, authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either)
        expect(Either.isLeft(rejected)).toBe(true)
        if (Either.isLeft(rejected)) expect(rejected.left).toMatchObject({ code: "FRAME_STALE" })
      }).pipe(Effect.provide(fileLayer(root))))
    )
  }).pipe(Effect.provide(noSubprocess))
)

it.effect("keeps repeated identical predictions as distinct executions and rejects cross-execution outcomes", () =>
  withTemporaryRoot((root) => seed.pipe(
    Effect.provide(fileLayer(root)),
    Effect.andThen(Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const http: AdaptiveHttpClientShape = {
        postJson: () => Effect.succeed(openAiResponse({ prediction: "same prediction", uncertainty: "unknown" }))
      }
      const first = yield* executeLlmSemanticRelation(runtime, "relation:sample", "same event", cell, http)
      const second = yield* executeLlmSemanticRelation(runtime, "relation:sample", "same event", cell, http)
      expect(first.frameSha256).toBe(second.frameSha256)
      expect(first.predictionSha256).toBe(second.predictionSha256)
      expect(first.executionId).not.toBe(second.executionId)
      expect(first.traceSha256).not.toBe(second.traceSha256)
      const outcome = yield* stageLlmSemanticOutcome(runtime, first, "observed", "fixture:outcome")
      const result = yield* learnLlmSemanticRelation(runtime, second, outcome, cell, http, authorizationRef, scope, "2026-09-14T00:01:00.000Z").pipe(Effect.either)
      expect(Either.isLeft(result)).toBe(true)
    }).pipe(Effect.provide(fileLayer(root))))
  )).pipe(Effect.provide(noSubprocess))
)
