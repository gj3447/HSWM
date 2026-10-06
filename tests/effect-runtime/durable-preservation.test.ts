import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2ContentStore, makeCanonicalAtomV2ContentDescriptor } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content.js"
import { makeCanonicalAtomV2ContentFileStoreLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-file.js"
import { makeCanonicalAtomV2ContentAuthorizer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-runtime.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2DurableRuntime, recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { GraphLoopControlJournal, GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { canonicalAtomV2ExactBytes, canonicalAtomV2JournalPublicationPlan, canonicalAtomV2ReferenceGrantDecision } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-guards.js"
import { CanonicalAtomV2StateJournalStore, type CanonicalAtomV2StateJournalEntry, type CanonicalAtomV2StateJournalPublish } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-store.js"
import { CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST, makeCanonicalAtomV2StateJournalFileStoreLayer, makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-file.js"
import { HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { authorizationRef, scope, seedSemanticLifecycle, makeSemanticLifecycleFileLayer } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

const contract = "hswm-durable-preservation/v1"
const boundaries = { canonicalPermitProved: false, physicalAtomicityProved: false }
const recoveryLimits = { maximumRecords: 64, maximumRecoveredJournalBytes: 4 * 1024 * 1024 }
const utf8 = (text: string) => new TextEncoder().encode(text)
const withRoot = async (use: (root: string) => Promise<void>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-durable-proof-"))
  try { await use(root) } finally { rmSync(root, { recursive: true, force: true }) }
}
const right = <A, E>(either: Either.Either<A, E>): A => {
  if (Either.isLeft(either)) throw new Error(JSON.stringify(either.left))
  return either.right
}
const checkLean = (cases: readonly unknown[]) => JSON.parse(execFileSync(resolve(import.meta.dirname,
  "../../formal/.lake/build/bin/HSWMDurablePreservationCli"), [], {
  input: JSON.stringify(cases), encoding: "utf8", timeout: 15000, stdio: ["pipe", "pipe", "pipe"]
})) as unknown[]
const compareLean = (cases: readonly unknown[], expected: readonly unknown[]) => {
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1") expect(checkLean(cases)).toEqual(expected)
}
const encodeEntry = (entry: CanonicalAtomV2StateJournalEntry) => ({ descriptor: entry.descriptor, bytes: [...entry.bytes] })

// Actual graph-loop admission and persisted payloads, with a read-only recovery
// witness tying the later journal checks to real native records.
const graphExample = (root: string) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const controller = yield* GraphLoopEngineeringController
  const controlJournal = yield* GraphLoopControlJournal
  yield* seedSemanticLifecycle
  const before = yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, recoveryLimits)
  const storedBytes = yield* Effect.forEach(before.state.atomBindings, binding => Effect.gen(function* () {
    return { binding, payload: yield* runtime.readContent(binding.payload), envelope: yield* runtime.readContent(binding.envelope) }
  }))
  const template = before.state.canonical.atoms.find(atom => atom.kind === "semantic_participant")!
  const evidence = yield* runtime.stageContent("text/plain", utf8("mechanical test evidence"))
  const atom = { ...template, key: { ...template.key, atomUid: "atom:durable-proof" },
    provenance: { mode: "DERIVATION" as const, evidenceSha256: evidence.sha256, sourceRef: template.key } }
  const envelope = yield* describeCanonicalAtomV2Envelope(atom)
  const candidate = makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "transition:durable-proof", expectedStateRevision: before.state.canonical.revision,
    schemaVersion: runtime.schema.schemaVersion, actorClaim: "fixture:actor", authorizationRef, scope,
    decidedAt: "2026-10-06T00:00:00.000Z", traceRef: null, readSet: [template.key], writes: [atom], provenanceSha256: evidence.sha256
  }, [{ key: atom.key, payload: atom.content, envelope }])
  const submit = (runId: string, input: typeof candidate) => Effect.gen(function* () {
    yield* controller.trigger({ runId, triggerId: `trigger:${runId}`, actorId: "fixture:actor", verifierId: "fixture:verifier", maximumActions: 1, maximumAttempts: 1 })
    yield* controller.sealAction(runId, evidence)
    yield* controller.recordVerification(runId, "ACCEPT", evidence)
    return yield* controller.submitDelta({ runId, transactionId: `transaction:${runId}`, affectedKeys: [template.key], candidate: input,
      evidence: { sealedTrajectory: evidence, outcome: evidence, credit: evidence, authorization: evidence, invariant: evidence,
        authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT", conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP" } })
  })
  for (const [label, patch, reason] of [
    ["wrong-reference", { authorizationRef: "not:granted" }, "NOT_GRANTED"],
    ["wrong-scope", { scope: "not:granted" }, "SCOPE_DENIED"]] as const) {
    expect((yield* submit(label, { ...candidate, command: { ...candidate.command, ...patch } })).disposition).toBe("REJECTED")
    expect((yield* controlJournal.recover).at(-1)?.event).toMatchObject({ phase: "REJECTED", reason })
    expect(yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, recoveryLimits)).toEqual(before)
  }
  expect((yield* submit("allowed", candidate)).disposition).toBe("COMMITTED")
  const after = yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, recoveryLimits)
  for (const { binding, payload, envelope: original } of storedBytes) {
    expect(yield* runtime.readContent(binding.payload)).toEqual(payload)
    expect(yield* runtime.readContent(binding.envelope)).toEqual(original)
  }
  return { before, after, storedBytes, candidate, active: runtime.schemaContent }
}).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive))

it("binds real grants to exact schema and scope; preserves all earlier payload bytes across commit and reopen", async () => withRoot(async root => {
  const example = await Effect.runPromise(graphExample(root))
  const { active, candidate } = example
  const grant = { authorizationRef, schemaVersion: active.schemaVersion, schemaContentSha256: active.content.sha256, scopes: [scope] as readonly string[] }
  const base = { activeSchemaSha256: active.content.sha256, grants: [grant], input: candidate, expected: "ALLOWED" }
  const cases = [base,
    { ...base, input: { ...candidate, schemaContentSha256: "0".repeat(64) }, expected: "SCHEMA_CONTENT_MISMATCH" },
    { ...base, grants: [], expected: "NOT_GRANTED" },
    { ...base, grants: [{ ...grant, authorizationRef: "other" }], expected: "NOT_GRANTED" },
    { ...base, grants: [{ ...grant, schemaVersion: "other" }], expected: "SCHEMA_MISMATCH" },
    { ...base, grants: [{ ...grant, schemaContentSha256: "0".repeat(64) }], expected: "SCHEMA_CONTENT_MISMATCH" },
    { ...base, grants: [{ ...grant, scopes: ["other"] }], expected: "SCOPE_DENIED" },
    // Fields split across different grants cannot be combined into authority.
    { ...base, grants: [{ ...grant, schemaVersion: "other" }, { ...grant, scopes: ["other"] }], expected: "SCOPE_DENIED" },
    { ...base, grants: [{ ...grant, authorizationRef: "authorization:other" }, grant], expected: "ALLOWED" },
    { ...base, input: { ...candidate, command: { ...candidate.command, actorClaim: "different:claim" } }, expected: "ALLOWED" }
  ]
  for (const test of cases) {
    expect(canonicalAtomV2ReferenceGrantDecision(test.activeSchemaSha256, test.grants, test.input) ?? "ALLOWED").toBe(test.expected)
    const result = await Effect.runPromise(makeCanonicalAtomV2ContentAuthorizer(active, test.grants)(test.input).pipe(Effect.either))
    expect(Either.isRight(result) ? "ALLOWED" : result.left.reason).toBe(test.expected)
  }
  compareLean(cases.map(test => ({ contract, kind: "grant", activeSchemaSha256: test.activeSchemaSha256, grants: test.grants,
    request: { ...test.input.command, schemaContentSha256: test.input.schemaContentSha256 } })),
  cases.map(test => ({ decision: test.expected, ...boundaries })))
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    expect(yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, recoveryLimits)).toEqual(example.after)
    for (const old of example.storedBytes) {
      expect(yield* runtime.readContent(old.binding.payload)).toEqual(old.payload)
      expect(yield* runtime.readContent(old.binding.envelope)).toEqual(old.envelope)
    }
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
}))

it("uses exact byte equality, defensive copies and no overwrite even at a forged occupied digest name", async () => withRoot(async root => {
  const vectors = [new Uint8Array(), new Uint8Array([0]), new Uint8Array([0, 255, 128]), utf8("한글 payload")]
  const cases: unknown[] = [], expected: unknown[] = []
  for (const proposed of vectors) {
    cases.push({ contract, kind: "bytes", existing: null, proposed: [...proposed] }); expected.push({ decision: "CREATE", ...boundaries })
    for (const existing of vectors) {
      const equal = canonicalAtomV2ExactBytes(existing, proposed)
      cases.push({ contract, kind: "bytes", existing: [...existing], proposed: [...proposed] })
      expected.push({ decision: equal ? "REUSE" : "CONFLICT", ...boundaries })
    }
  }
  await Effect.runPromise(Effect.gen(function* () {
    const store = yield* CanonicalAtomV2ContentStore
    for (const value of vectors) {
      const caller = Uint8Array.from(value), pending = store.put("application/octet-stream", caller)
      caller.fill(7)
      const descriptor = yield* pending
      const read = yield* store.get(descriptor)
      expect(read).toEqual(value)
      read.fill(9)
      expect(yield* store.get(descriptor)).toEqual(value)
      expect(yield* store.put("application/octet-stream", value)).toEqual(descriptor)
    }
    const wanted = utf8("intended"), occupied = utf8("tampered")
    const descriptor = right(makeCanonicalAtomV2ContentDescriptor("application/octet-stream", wanted))
    const path = join(root, "objects", descriptor.sha256)
    writeFileSync(path, occupied, { flag: "wx", mode: 0o400 })
    const result = yield* store.put("application/octet-stream", wanted).pipe(Effect.either)
    expect(result).toMatchObject({ _tag: "Left", left: { reason: "CONTENT_CORRUPT" } })
    expect([...readFileSync(path)]).toEqual([...occupied])
  }).pipe(Effect.provide(makeCanonicalAtomV2ContentFileStoreLayer(root))))
  compareLean(cases, expected)
}))

it("matches actual native journal records, exact retries and every interrupted publication checkpoint with Lean", async () => withRoot(async root => {
  const example = await Effect.runPromise(graphExample(join(root, "source")))
  const before = example.before.journal, after = example.after.journal, added = after[after.length - 1]!
  const input: CanonicalAtomV2StateJournalPublish = { stateRevision: before.length, expectedPredecessor: before[before.length - 1]!.descriptor, bytes: added.bytes }
  const cases: unknown[] = [], expected: unknown[] = []
  const wire = (journal: readonly CanonicalAtomV2StateJournalEntry[], proposed: CanonicalAtomV2StateJournalPublish) => ({
    contract, kind: "journal", journal: journal.map(encodeEntry), publication: {
      ...proposed, descriptor: right(makeCanonicalAtomV2ContentDescriptor(added.descriptor.mediaType, proposed.bytes)), bytes: [...proposed.bytes]
    }
  })
  const variants = [
    { journal: before, proposed: input, decision: "APPEND" },
    { journal: after, proposed: input, decision: "ALREADY_COMMITTED" },
    { journal: after, proposed: { stateRevision: 0, expectedPredecessor: null, bytes: before[0]!.bytes }, decision: "ALREADY_COMMITTED" },
    { journal: before, proposed: { ...input, stateRevision: before.length + 1, expectedPredecessor: null }, decision: "REVISION_CONFLICT" },
    { journal: before, proposed: { ...input, expectedPredecessor: null }, decision: "PREDECESSOR_MISMATCH" },
    { journal: after, proposed: { ...input, bytes: utf8("different") }, decision: "CONCURRENT_PUBLICATION_CONFLICT" },
    ...(["sha256", "byteLength", "mediaType"] as const).map(field => ({ journal: before, proposed: { ...input,
      expectedPredecessor: { ...input.expectedPredecessor!, [field]: field === "byteLength" ? input.expectedPredecessor!.byteLength + 1 : "different" }
    }, decision: "PREDECESSOR_MISMATCH" }))
  ]
  for (const [index, variant] of variants.entries()) {
    const plan = canonicalAtomV2JournalPublicationPlan(variant.journal, variant.proposed)
    expect(plan._tag === "REJECTED" ? plan.reason : plan._tag).toBe(variant.decision)
    cases.push(wire(variant.journal, variant.proposed))
    expected.push({ decision: variant.decision, recovered: (variant.decision === "APPEND" ? after : variant.journal).map(encodeEntry), ...boundaries })
    await Effect.runPromise(Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      for (const [revision, entry] of variant.journal.entries()) yield* store.publish({ stateRevision: revision,
        expectedPredecessor: revision === 0 ? null : variant.journal[revision - 1]!.descriptor, bytes: entry.bytes })
      const observed = yield* store.publish(variant.proposed).pipe(Effect.either)
      expect(Either.isRight(observed) ? (observed.right._tag === "Committed" ? "APPEND" : "ALREADY_COMMITTED") : observed.left.reason).toBe(variant.decision)
      expect(yield* store.recover).toEqual(variant.decision === "APPEND" ? after : variant.journal)
    }).pipe(Effect.provide(makeCanonicalAtomV2StateJournalFileStoreLayer(join(root, `plan-${index}`),
      example.before.state.journalLineageId, example.active.content.sha256))))
  }
  const linkedCheckpoints = new Set(["slot-link:after", "slot-directory-fsync:before", "slot-directory-fsync:after", "journal-readback:before", "journal-readback:after"])
  for (const [index, checkpoint] of CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST.entries()) {
    const path = join(root, `interrupted-${index}`), lineage = example.before.state.journalLineageId, schema = example.active.content.sha256
    const normal = makeCanonicalAtomV2StateJournalFileStoreLayer(path, lineage, schema)
    await Effect.runPromise(Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      for (const [revision, entry] of before.entries()) yield* store.publish({ stateRevision: revision,
        expectedPredecessor: revision === 0 ? null : before[revision - 1]!.descriptor, bytes: entry.bytes })
    }).pipe(Effect.provide(normal)))
    const result = await Effect.runPromise(CanonicalAtomV2StateJournalStore.pipe(Effect.flatMap(store => store.publish(input)),
      Effect.provide(makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest(path, lineage, schema, checkpoint)), Effect.either))
    const linked = linkedCheckpoints.has(checkpoint)
    expect(result).toMatchObject({ _tag: "Left", left: { reason: linked ? "PUBLICATION_OUTCOME_UNKNOWN" : "IO_FAILED" } })
    const recovered = await Effect.runPromise(CanonicalAtomV2StateJournalStore.pipe(Effect.flatMap(store => store.recover), Effect.provide(normal)))
    expect(recovered).toEqual(linked ? after : before)
    cases.push({ ...wire(before, input), kind: "crash", linked })
    expected.push({ decision: "APPEND", recovered: recovered.map(encodeEntry), ...boundaries })
    const retry = await Effect.runPromise(CanonicalAtomV2StateJournalStore.pipe(Effect.flatMap(store => store.publish(input)), Effect.provide(normal)))
    expect(retry._tag).toBe(linked ? "AlreadyCommitted" : "Committed")
    expect(retry.recovery).toEqual(after)
  }
  compareLean(cases, expected)
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1") {
    expect(() => checkLean([{ contract, kind: "bytes", existing: null, proposed: [256] }])).toThrow()
    expect(() => checkLean([{ ...wire(before, input), publication: { ...wire(before, input).publication, stateRevision: -1 } }])).toThrow()
  }
}), 30000)
