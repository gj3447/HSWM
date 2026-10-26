#!/usr/bin/env node
/** Bounded public research -> native evidence -> two task contexts -> fresh-process recovery. */
import { readFile, writeFile, mkdir } from "node:fs/promises"
import { resolve, join } from "node:path"
import { execFile } from "node:child_process"
import { Effect, Either } from "../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent } from "../../src/hswm/effect-runtime/dist/canonical-atom-v2-content-bound.js"
import { workspaceActivationSchema } from "../../src/hswm/effect-runtime/dist/workspace-activation-runtime.js"
import { workingContextKind } from "../../src/hswm/effect-runtime/dist/working-context-domain.js"
import { prepareWorkingContextCreation, prepareWorkingContextRefresh, openWorkingContext } from "../../src/hswm/effect-runtime/dist/working-context-runtime.js"
import { crossrefSearchUrl } from "../../src/hswm/effect-runtime/dist/evidence-acquisition-domain.js"
import { acquireEvidence } from "../../src/hswm/effect-runtime/dist/evidence-acquisition-http.js"
import { acquireWorkingContextEvidence, prepareEvidencePublication, prepareWorkingEvidenceHandoff, readEvidenceObservation } from "../../src/hswm/effect-runtime/dist/evidence-acquisition-runtime.js"
import { runArgvProcessMain } from "../../src/hswm/effect-runtime/dist/effect-process-main.js"

const help = `node _research/agent_working_context_v1/evidence.mjs run NEW_PRIVATE_ROOT
node _research/agent_working_context_v1/evidence.mjs check PRIVATE_ROOT
run makes at most three public GETs: one Crossref scholarly search, one RFC Editor
source read, one conditional source revalidation. No private source or task text
leaves the process. No model call, background subscription, remote peer or W update.
It creates an isolated native journal, shares original evidence IDs between two
task contexts, rejects duplicate promotion and reopens a peer in a fresh process.
check reads existing evidence and task state; it makes no network requests.
Run under the managed runner after building the Effect runtime. Do not bypass a
storage-admission refusal. Guide: docs/operations/HSWM_AGENT_WORKING_CONTEXT.md
`
const owner = "owner:public-evidence-integration"
const schema = { ...workspaceActivationSchema, schemaVersion: "public-evidence-context-v1",
  bootstrapTrustStatement: "PUBLIC_HTTP_OBSERVATIONS_AND_AUTHORED_INTEGRATION_TASK_NOT_SOURCE_TRUTH_OR_MODEL_EFFICACY",
  owners: [{ address: owner, obligation: "Bounded public-source observation and local task-state writer" }],
  kinds: [...workspaceActivationSchema.kinds.filter(kind => kind.kind !== "source_catalog").map(kind => ({ ...kind, allowedOwners: [owner] })), workingContextKind([owner])] }
const unwrap = value => { if (Either.isLeft(value)) throw value.left; return value.right }
const bytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(bytes)).binding.content.sha256
const layer = root => makeCanonicalAtomV2DurableRuntimeFileLayer(join(root, "native"), "public-evidence-context", bytes,
  [{ authorizationRef: "public-evidence-integration", schemaVersion: schema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["local-public-evidence"] }])
const writer = () => ({ owner, authorizationRef: "public-evidence-integration", scope: "local-public-evidence", decidedAt: new Date().toISOString(), lineageId: "public-evidence" })
const target = (key, revisionId) => { const { lineageId: _lineageId, ...fields } = writer(); return { ...fields, key: { ...key, revisionId } } }
const key = id => ({ schemaVersion: schema.schemaVersion, lineageId: "public-tasks", atomUid: `working:${id}`, revisionId: 0 })
const io = thunk => Effect.tryPromise({ try: thunk, catch: cause => new Error(String(cause)) })
const ensure = (condition, message) => condition ? Effect.void : Effect.fail(new Error(message))
const save = (path, value) => io(() => writeFile(path, JSON.stringify(value, null, 2) + "\n", { flag: "wx", mode: 0o600 }))
const json = path => io(async () => JSON.parse(await readFile(path, "utf8")))
const query = "HTTP Cache-Control Extensions for Stale Content"
const sourceUrl = "https://www.rfc-editor.org/rfc/rfc5861.txt"
const need = { gapId: "source", question: "Which original RFC defines these stale-content extensions?", trigger: "MISSING", sufficiency: "UNKNOWN",
  knownUrl: sourceUrl, publicQuery: null, localAvailable: false, remainingRequests: 3, noProgressRounds: 0 }
const memory = { goal: "Retain an original public source and its provenance across agent context handoff", constraints: ["Metadata is not the original source", "Transport success does not settle source truth"],
  completionCriteria: ["Complete source available to both contexts with the same origin", "Fresh process reads the exact shared revision"], progress: "Awaiting source assessment",
  gaps: [{ id: need.gapId, question: need.question, status: "OPEN", evidence: [] }] }
const childRead = (root, contextKey) => io(() => new Promise((resolveResult, reject) => {
  const child = execFile(process.execPath, [resolve("src/hswm/effect-runtime/dist/working-context-process.js")], { timeout: 60000, maxBuffer: 2097152 }, (error, stdout, stderr) => {
    if (error) reject(new Error(stderr || error.message))
    else { try { resolveResult({ pid: child.pid, selected: JSON.parse(stdout) }) } catch (cause) { reject(cause) } }
  })
  child.stdin.end(JSON.stringify({ contract: "hswm-working-context-cli/v1", action: "select", durableRoot: join(root, "native"), journalLineageId: "public-evidence-context",
    schema, contextKey, featureValues: [1] }))
}))

const run = root => Effect.gen(function* () {
  yield* io(() => mkdir(root, { mode: 0o700 }))
  yield* io(() => mkdir(join(root, "native"), { mode: 0o700 }))
  const access = { projectId: "HSWM", linkId: "public-evidence-integration", resource: "urn:hswm:public-http-evidence",
    purpose: "User-requested public-source research and local context integration", recipient: "Crossref API and RFC Editor",
    expiresAt: new Date(Date.now() + 600000).toISOString(), revoked: false,
    allowedUrls: [crossrefSearchUrl(query), sourceUrl], publicQueries: [query], maximumBytes: 65536, timeoutMs: 30000 }
  yield* save(join(root, "access.json"), { access, authority: "USER_REQUESTED_PUBLIC_RESEARCH_ONLY", fieldsSent: ["fixed public query", "RFC URL", "HTTP validator"],
    mappings: [{ link: access.linkId, project: access.projectId, resource: access.resource, locators: access.allowedUrls }], maximumRequests: 3 })
  const count = { requests: 0 }
  const ports = { now: () => new Date().toISOString(), fetch: (input, init) => {
    count.requests++
    if (count.requests > 3) return Promise.reject(new Error("request budget exceeded"))
    return globalThis.fetch(input, init)
  } }
  const result = yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const search = yield* acquireEvidence({ ...need, trigger: "EXPLICIT_SEARCH", publicQuery: query, knownUrl: null }, access, null, ports)
    yield* ensure(search.observation?.search?.hits.some(hit => hit.doi.toLowerCase() === "10.17487/rfc5861"), "Live search did not return the expected DOI; no invented fallback")
    const publishedSearch = yield* prepareEvidencePublication(runtime, search.observation, writer())
    yield* ensure(publishedSearch.candidate !== null, "Fresh journal expected")
    yield* runtime.submit(publishedSearch.candidate)
    const spec = { contract: "hswm-semantic-context-spec/v1", event: "Inspect source provenance and unresolved claims", mandatoryRelationUids: [],
      candidates: [{ id: "read", summary: "Read complete source roles with provenance and exceptions", relationUids: [publishedSearch.relationKey.atomUid] }],
      maximumContextBytes: 262144, minimumConfidence: 0, minimumMargin: 0 }
    for (const id of ["worker", "peer", "unrelated"]) {
      const created = yield* prepareWorkingContextCreation(runtime, { agentId: `agent:${id}`, taskId: `task:${id}`, memory, spec,
        policyFamily: { lineageId: "public-evidence-policies", atomUid: "source-reading", config: { encoderRevision: "bias/v1", featureNames: ["bias"], alpha: 1 } }
      }, target(key(id), 0))
      yield* runtime.submit(created.candidate)
    }
    const fetched = yield* acquireWorkingContextEvidence(runtime, key("worker"), { ...need, ...search.nextBudget }, access, null, writer(), { ...ports, admit: candidate => runtime.submit(candidate) })
    yield* ensure(fetched.evidenceKey && fetched.observation?.bodyUtf8.includes("RFC 5861"), "Complete RFC source missing")
    const handoff = yield* prepareWorkingEvidenceHandoff(runtime, fetched.contextKey, key("peer"), fetched.evidenceKey, target(key("peer"), 1))
    yield* ensure(handoff !== null, "Peer handoff missing")
    yield* runtime.submit(handoff.candidate)
    const child = yield* childRead(root, handoff.contextKey)
    yield* ensure(child.pid !== process.pid && JSON.stringify(child.selected).includes(fetched.evidenceKey.atomUid), "Fresh process did not consume the original source")
    const before = (yield* runtime.snapshot).canonical.revision
    yield* ensure((yield* prepareEvidencePublication(runtime, fetched.observation, writer())).status === "REUSED", "Repeated source was promoted twice")
    yield* ensure((yield* prepareWorkingEvidenceHandoff(runtime, fetched.contextKey, handoff.contextKey, fetched.evidenceKey, target(key("peer"), 2))) === null, "Repeated handoff was not a no-op")
    yield* ensure((yield* runtime.snapshot).canonical.revision === before, "Replay changed the journal")
    const revalidated = yield* acquireWorkingContextEvidence(runtime, fetched.contextKey, { ...need, trigger: "STALE", ...fetched.nextBudget }, access, fetched.evidenceKey, writer(), { ...ports, admit: candidate => runtime.submit(candidate) })
    yield* ensure(revalidated.observation?.bodySha256 === fetched.observation.bodySha256, "Source changed during this unchanged-content check; inspect it instead of claiming revalidation")
    yield* ensure((yield* openWorkingContext(runtime, key("peer"))).status === "STALE" && (yield* openWorkingContext(runtime, key("unrelated"))).status === "CURRENT", "Observation revision did not invalidate only dependents")
    const refreshed = yield* prepareWorkingContextRefresh(runtime, handoff.contextKey, target(key("peer"), 2))
    yield* ensure(refreshed !== null, "Peer refresh missing")
    yield* runtime.submit(refreshed.candidate)
    yield* ensure((yield* prepareWorkingEvidenceHandoff(runtime, refreshed.contextKey, revalidated.contextKey, revalidated.evidenceKey, target(key("worker"), revalidated.contextKey.revisionId + 1))) === null, "Return handoff duplicated the original source")
    return { contract: "hswm-public-evidence-integration/v1", observedAt: new Date().toISOString(), requests: count.requests,
      searchKey: publishedSearch.relationKey, evidenceKey: revalidated.evidenceKey, sourceId: fetched.observation.sourceId, bodySha256: fetched.observation.bodySha256,
      bodyBytes: Buffer.byteLength(fetched.observation.bodyUtf8), revalidationStatus: revalidated.observation.httpStatus,
      workerKey: revalidated.contextKey, peerKey: refreshed.contextKey, unrelatedKey: key("unrelated"), freshProcessPid: child.pid,
      duplicateAdmission: false, gapsResolvedByTransport: false, modelCalls: 0, weightUpdates: 0, separateHostTransport: false }
  }).pipe(Effect.provide(layer(root)))
  yield* save(join(root, "result.json"), result)
  return result
})
const check = root => Effect.gen(function* () {
  const result = yield* json(join(root, "result.json"))
  yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const stored = yield* readEvidenceObservation(runtime, result.evidenceKey)
    yield* ensure(stored.observation.bodySha256 === result.bodySha256 && stored.observation.sourceId === result.sourceId, "Stored source differs from the observed receipt")
    for (const key of [result.workerKey, result.peerKey]) {
      const context = yield* openWorkingContext(runtime, key)
      yield* ensure(context.status === "CURRENT" && context.context.memory.gaps.every(gap => gap.status === "OPEN") &&
        context.context.dependencies.some(d => JSON.stringify(d.key) === JSON.stringify(result.evidenceKey)), "Context lost source identity or invented gap resolution")
    }
  }).pipe(Effect.provide(layer(root)))
  const child = yield* childRead(root, result.peerKey)
  yield* ensure(JSON.stringify(child.selected).includes(result.evidenceKey.atomUid), "Fresh selection lacks the source")
  return { ...result, independentRead: "PASS", checkProcessPid: child.pid }
})
if (process.argv[2] === "--help") process.stdout.write(help)
else process.exitCode = await runArgvProcessMain({ refusalPrefix: "HSWM_PUBLIC_EVIDENCE_REFUSED", program: args => {
  const [command, path] = args
  if (!["run", "check"].includes(command) || !path || args.length !== 2) return Effect.fail(new Error(help))
  return (command === "run" ? run(resolve(path)) : check(resolve(path))).pipe(Effect.map(value => `${JSON.stringify(value, null, 2)}\n`))
}, describeFailure: error => String(error) }, process.argv.slice(2))
