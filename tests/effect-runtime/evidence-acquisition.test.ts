import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer, makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { NodePosixServicesLive, type BoundedSubprocess, type PosixFileSystem } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { workingContextKind } from "../../src/hswm/effect-runtime/src/working-context-domain.js"
import { openWorkingContext, prepareWorkingContextCreation, prepareWorkingContextRefresh } from "../../src/hswm/effect-runtime/src/working-context-runtime.js"
import { workingContextProcess } from "../../src/hswm/effect-runtime/src/working-context-process.js"
import { crossrefSearchUrl, decideEvidenceAcquisition, type EvidenceAccess, type EvidenceNeed } from "../../src/hswm/effect-runtime/src/evidence-acquisition-domain.js"
import { acquireEvidence } from "../../src/hswm/effect-runtime/src/evidence-acquisition-http.js"
import { acquireWorkingContextEvidence, prepareEvidencePublication, prepareWorkingEvidenceHandoff, readEvidenceObservation } from "../../src/hswm/effect-runtime/src/evidence-acquisition-runtime.js"
import { schema, key, spec, seedContext, unwrap } from "./semantic-context-fixture.js"

const now = "2026-10-26T00:00:00.000Z"
const url = "https://source.example/primary.txt"
const query = "HTTP caching"
const access: EvidenceAccess = { projectId: "test", linkId: "test-source", resource: "public-source", purpose: "scripted test", recipient: "source.example",
  expiresAt: "2026-10-27T00:00:00.000Z", revoked: false, allowedUrls: [url, crossrefSearchUrl(query)], publicQueries: [query], maximumBytes: 65536, timeoutMs: 1000 }
const need: EvidenceNeed = { gapId: "missing", question: "What does the source say?", trigger: "MISSING", sufficiency: "UNKNOWN", knownUrl: url, publicQuery: null,
  localAvailable: false, remainingRequests: 3, noProgressRounds: 0 }
const body = "Original source. External text can say ignore instructions; it remains untrusted data."
const read = (text = body, etag = '"v1"') => ({ fetch: (async () => new Response(text, { headers: { "content-type": "text/plain; charset=utf-8", etag } })) satisfies typeof fetch, now: () => now })
const run = <A, E>(effect: Effect.Effect<A, E>) => Effect.runPromise(effect)

it("routes missing, fresh, stale, conflicted, private, local and exhausted needs without confusing relevance and sufficiency", () => {
  for (const [changes, action] of [
    [{}, "FETCH_SOURCE"], [{ sufficiency: "SUFFICIENT" }, "USE_CURRENT"], [{ localAvailable: true }, "LOCAL_READ"],
    [{ trigger: "STALE" }, "REVALIDATE"], [{ trigger: "CONFLICT", publicQuery: query }, "SEARCH_EXTERNAL"],
    [{ sufficiency: "CONFLICTED", publicQuery: query, localAvailable: true }, "SEARCH_EXTERNAL"],
    [{ trigger: "EXPLICIT_SEARCH", publicQuery: query, sufficiency: "SUFFICIENT" }, "SEARCH_EXTERNAL"],
    [{ trigger: "PRIVATE_INPUT" }, "ASK_HUMAN"], [{ trigger: "REASONING_FAILURE" }, "DIAGNOSE_REASONING"],
    [{ remainingRequests: 0 }, "DEFER"], [{ noProgressRounds: 2 }, "DEFER"], [{ knownUrl: null, publicQuery: null }, "ASK_HUMAN"]
  ] as const) expect(unwrap(decideEvidenceAcquisition({ ...need, ...changes })).action).toBe(action)
})

it("refuses expired, revoked, unselected and unapproved-query requests before dispatch", async () => {
  let calls = 0
  const ports = { ...read(), fetch: (async () => { calls++; return new Response(body) }) satisfies typeof fetch }
  for (const changed of [{ expiresAt: now }, { revoked: true }, { allowedUrls: ["https://elsewhere.example/"] }])
    expect(Either.isLeft(await run(acquireEvidence(need, { ...access, ...changed }, null, ports).pipe(Effect.either)))).toBe(true)
  expect(Either.isLeft(await run(acquireEvidence({ ...need, trigger: "EXPLICIT_SEARCH", publicQuery: "private task text" }, access, null, ports).pipe(Effect.either)))).toBe(true)
  expect(calls).toBe(0)
})

it("keeps search metadata separate from paper reads and never follows returned locators", async () => {
  const sent: string[] = []
  const result = await run(acquireEvidence({ ...need, trigger: "EXPLICIT_SEARCH", publicQuery: query }, access, null, {
    now: () => now, fetch: async (input, init) => {
      sent.push(String(input)); expect(init?.redirect).toBe("error"); expect(init?.credentials).toBe("omit")
      return new Response(JSON.stringify({ status: "ok", message: { items: [{ DOI: "10.1234/a", title: ["HTTP caching"], URL: "https://doi.org/10.1234/a", publisher: "Author" }] } }), { headers: { "content-type": "application/json" } })
    }
  }))
  expect(sent).toEqual([crossrefSearchUrl(query)])
  expect(result.observation).toMatchObject({ kind: "SEARCH_METADATA", sufficiency: "NOT_EVALUATED", truth: "NOT_EVALUATED", search: { hits: [{ doi: "10.1234/a" }] } })
  expect(result.nextBudget.remainingRequests).toBe(2)
})

it("bounds complete reads, rejects non-UTF8, redirects, HTTP failures and timeouts without fabricated empty evidence", async () => {
  const cases: ReadonlyArray<typeof fetch> = [
    async () => new Response("x".repeat(65537), { headers: { "content-type": "text/plain" } }),
    async () => new Response(new Uint8Array([255]), { headers: { "content-type": "text/plain" } }),
    async () => new Response("", { status: 302, headers: { location: "https://elsewhere.example" } }),
    async () => new Response("busy", { status: 429 }),
    async () => new Response("pdf", { headers: { "content-type": "application/pdf" } }),
    (_input, init) => new Promise((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("aborted"))))
  ]
  for (const fetch of cases) expect(Either.isLeft(await run(acquireEvidence(need, { ...access, timeoutMs: 20 }, null, { now: () => now, fetch }).pipe(Effect.either)))).toBe(true)
  expect((await run(acquireEvidence(need, access, null, read("\ufeffcomplete")))).observation?.bodyUtf8).toBe("\ufeffcomplete")
})

it("binds conditional validation to cached bytes; 304 does not settle a gap and repeated unchanged reads stop", async () => {
  const first = await run(acquireEvidence(need, access, null, read()))
  if (!first.observation) throw new Error("expected observation")
  const result = await run(acquireEvidence({ ...need, trigger: "STALE", noProgressRounds: 1 }, access, first.observation, {
    now: () => "2026-10-26T00:01:00.000Z", fetch: async (_input, init) => {
      expect(new Headers(init?.headers).get("if-none-match")).toBe('"v1"')
      return new Response(null, { status: 304, headers: { etag: '"v1"' } })
    }
  }))
  expect(result.observation).toMatchObject({ bodySha256: first.observation.bodySha256, httpStatus: 304, truth: "NOT_EVALUATED" })
  expect(unwrap(decideEvidenceAcquisition({ ...need, trigger: "STALE", ...result.nextBudget })).action).toBe("DEFER")
  for (const previous of [null, { ...first.observation, bodyUtf8: "tampered" }])
    expect(Either.isLeft(await run(acquireEvidence({ ...need, trigger: "STALE" }, access, previous, { now: () => now, fetch: async () => new Response(null, { status: 304 }) }).pipe(Effect.either)))).toBe(true)
})

it("automatically revalidates evidence older than the task freshness limit and keeps local decisions independent of Internet access", async () => {
  const first = await run(acquireEvidence(need, access, null, read()))
  if (!first.observation) throw new Error("expected observation")
  const checked = await run(acquireEvidence({ ...need, sufficiency: "SUFFICIENT", maximumAgeMs: 1000 }, access, first.observation,
    { ...read(), now: () => "2026-10-26T00:01:00.000Z" }))
  expect(checked.action).toBe("REVALIDATE")
  expect((await run(acquireEvidence({ ...need, localAvailable: true }, null, null, read()))).action).toBe("LOCAL_READ")
})

it("counts repeated DOI hits as no progress even if search response metadata changes", async () => {
  const searchNeed = { ...need, trigger: "EXPLICIT_SEARCH", publicQuery: query, knownUrl: null }
  const response = (stamp: string) => ({ now: () => now, fetch: (async () => new Response(JSON.stringify({ status: "ok", stamp,
    message: { items: [{ DOI: "10.1234/a", title: ["A"], URL: "https://doi.org/10.1234/a", publisher: "P" }] }
  }), { headers: { "content-type": "application/json" } })) satisfies typeof fetch })
  const first = await run(acquireEvidence(searchNeed, access, null, response("before")))
  const again = await run(acquireEvidence(searchNeed, access, first.observation, response("after")))
  expect(again.observation?.bodySha256).not.toBe(first.observation?.bodySha256)
  expect(again.nextBudget.noProgressRounds).toBe(1)
})

const owner = "owner:context-test"
const workingSchema: HSWMCanonicalSchemaV2 = { ...schema, kinds: [...schema.kinds, {
  kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [owner], minimumArity: 1,
  referenceContracts: [
    { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
    { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }
  ]
}, workingContextKind([owner])] }
const bytes = unwrap(canonicalAtomV2SchemaContentBytes(workingSchema))
const grants = [
  { authorizationRef: "fixture-auth", schemaVersion: schema.schemaVersion, schemaContentSha256: unwrap(decodeCanonicalAtomV2SchemaContent(bytes)).binding.content.sha256, scopes: ["fixture"] }
]
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "evidence-tests", bytes, grants)
type Runtime = CanonicalAtomV2DurableRuntime["Type"]
const memoryFixture = <A, E>(use: (runtime: Runtime) => Effect.Effect<A, E, BoundedSubprocess | PosixFileSystem>) => Effect.runPromise(
  seedContext.pipe(Effect.flatMap(use), Effect.provide(makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest("evidence-tests", bytes, grants)), Effect.provide(NodePosixServicesLive),
    Effect.mapError(error => new Error(JSON.stringify(error), { cause: error }))))
const fixture = <A, E>(use: (runtime: Runtime, root: string) => Effect.Effect<A, E, BoundedSubprocess | PosixFileSystem>) => Effect.runPromise(Effect.acquireUseRelease(
  Effect.sync(() => mkdtempSync(join(tmpdir(), "hswm-evidence-"))), root => seedContext.pipe(Effect.flatMap(runtime => use(runtime, root)), Effect.provide(layer(root))),
  root => Effect.sync(() => rmSync(root, { recursive: true, force: true }))
).pipe(Effect.provide(NodePosixServicesLive), Effect.mapError(error => new Error(JSON.stringify(error), { cause: error }))))
const writer = { owner, authorizationRef: "fixture-auth", scope: "fixture", decidedAt: now, lineageId: "public-evidence" }
const target = (id: string, revisionId = 0) => ({ owner, authorizationRef: writer.authorizationRef, scope: writer.scope, decidedAt: now, key: { ...key(`working:${id}`), revisionId } })
const create = (runtime: Runtime, id: string) => Effect.gen(function* () {
  const proposal = yield* prepareWorkingContextCreation(runtime, { agentId: `agent:${id}`, taskId: `task:${id}`,
    memory: { goal: "Read an attributed source", constraints: ["Keep source identity"], completionCriteria: ["Exact source available"], progress: "Open",
      gaps: [{ id: need.gapId, question: need.question, status: "OPEN", evidence: [] }] }, spec: { ...spec, maximumContextBytes: 262144 },
    policyFamily: { lineageId: "shared", atomUid: "operators", config: { encoderRevision: "bias/v1", featureNames: ["bias"], alpha: 1 } }
  }, target(id))
  yield* runtime.submit(proposal.candidate)
  return proposal.contextKey
})

const handoffCase = (runtime: Runtime, root: string | null) => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const b = yield* create(runtime, "b")
  const result = yield* acquireWorkingContextEvidence(runtime, a, need, access, null, writer, { ...read(), admit: candidate => runtime.submit(candidate) })
  if (!result.evidenceKey || !result.observation) return yield* Effect.fail(new Error("missing source"))
  const shared = yield* prepareWorkingEvidenceHandoff(runtime, result.contextKey, b, result.evidenceKey, target("b", 1))
  if (!shared) return yield* Effect.fail(new Error("missing handoff"))
  yield* runtime.submit(shared.candidate)
  const before = (yield* runtime.snapshot).canonical.revision
  expect(yield* prepareWorkingEvidenceHandoff(runtime, result.contextKey, shared.contextKey, result.evidenceKey, target("b", 2))).toBeNull()
  expect((yield* prepareEvidencePublication(runtime, result.observation, writer)).status).toBe("REUSED")
  expect((yield* runtime.snapshot).canonical.revision).toBe(before)
  const recovered = root === null ? yield* openWorkingContext(runtime, b)
    : yield* workingContextProcess({ contract: "hswm-working-context-cli/v1", action: "open", durableRoot: root, journalLineageId: "evidence-tests", schema: workingSchema, contextKey: b })
  expect(JSON.stringify(recovered)).toContain(result.evidenceKey.atomUid)
  const peer = yield* openWorkingContext(runtime, b)
  expect(peer.context.memory.gaps[0]?.status).toBe("OPEN")
  expect(peer.context.dependencies.filter(d => d.key.atomUid === result.evidenceKey?.atomUid)).toHaveLength(1)
  expect((yield* readEvidenceObservation(runtime, result.evidenceKey)).observation.bodyUtf8).toBe(body)
})
it("memory journal acquires and hands off exact source IDs without closing gaps or duplicating admission", () => memoryFixture(runtime => handoffCase(runtime, null)))
it("file journal reopens the acquired and shared source through the recovery command", () => fixture(handoffCase))

it("new source observations refresh the acquiring task, stale only dependent peers, and refuse out-of-order or foreign handoffs", () => memoryFixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  const b = yield* create(runtime, "b")
  const unrelated = yield* create(runtime, "unrelated")
  const first = yield* acquireWorkingContextEvidence(runtime, a, need, access, null, writer, { ...read(), admit: candidate => runtime.submit(candidate) })
  if (!first.evidenceKey || !first.observation) return yield* Effect.fail(new Error("missing source"))
  const shared = yield* prepareWorkingEvidenceHandoff(runtime, first.contextKey, b, first.evidenceKey, target("b", 1))
  if (!shared) return yield* Effect.fail(new Error("missing handoff"))
  yield* runtime.submit(shared.candidate)
  const next = yield* acquireWorkingContextEvidence(runtime, first.contextKey, { ...need, trigger: "STALE" }, access, first.evidenceKey, writer,
    { ...read("Corrected original source", '"v2"'), now: () => "2026-10-26T00:01:00.000Z", admit: candidate => runtime.submit(candidate) })
  expect(next.evidenceKey?.revisionId).toBe(1)
  expect((yield* openWorkingContext(runtime, a)).status).toBe("CURRENT")
  expect((yield* openWorkingContext(runtime, b)).status).toBe("STALE")
  expect((yield* openWorkingContext(runtime, unrelated)).status).toBe("CURRENT")
  const refresh = yield* prepareWorkingContextRefresh(runtime, shared.contextKey, target("b", 2))
  if (!refresh) return yield* Effect.fail(new Error("missing refresh"))
  yield* runtime.submit(refresh.candidate)
  expect(Either.isLeft(yield* prepareEvidencePublication(runtime, first.observation, writer).pipe(Effect.either))).toBe(true)
  expect(Either.isLeft(yield* prepareWorkingEvidenceHandoff(runtime, unrelated, next.contextKey, next.evidenceKey, target("a", 3)).pipe(Effect.either))).toBe(true)
})))

it("does not dispatch for a mismatched gap or claim success when the owner declines admission", () => memoryFixture(runtime => Effect.gen(function* () {
  const a = yield* create(runtime, "a")
  let calls = 0
  const ports = { now: () => now, fetch: (async () => { calls++; return new Response(body, { headers: { "content-type": "text/plain" } }) }) satisfies typeof fetch,
    admit: () => Effect.void }
  expect(Either.isLeft(yield* acquireWorkingContextEvidence(runtime, a, { ...need, question: "foreign" }, access, null, writer, ports).pipe(Effect.either))).toBe(true)
  expect(calls).toBe(0)
  expect(Either.isLeft(yield* acquireWorkingContextEvidence(runtime, a, need, access, null, writer, ports).pipe(Effect.either))).toBe(true)
  expect(calls).toBe(1)
  expect((yield* openWorkingContext(runtime, a)).atom.key).toEqual(a)
})))
