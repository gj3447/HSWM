import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { chmodSync, linkSync, mkdtempSync, rmSync, unlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { executeLlmSemanticRelation, learnLlmSemanticRelation, stageLlmSemanticOutcome } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { admissionForSemanticLifecycle, authorizationRef, makeSemanticLifecycleFileLayer, relationUid, scope, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { type CanonicalAtomV2, type CommitCanonicalAtomsV2Command } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { makeCanonicalAtomV2AcceptedReceipt } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import { canonicalAtomV2PreservationHolds, projectCanonicalAtomV2Preservation } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-preservation.js"
import { canonicalAtomV2ExactBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-guards.js"
import { canonicalAtomV2JournalLinkMatches, canonicalAtomV2JournalSchemaMatches, canonicalAtomV2JournalReceiptHeaderMatches } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-replay-guards.js"
import { CanonicalAtomV2StateJournalStore } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-store.js"
import { makeCanonicalAtomV2StateJournalFileStoreLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-file.js"
import { applyCanonicalAtomV2StateJournalGenesis, applyCanonicalAtomV2StateJournalCommit, canonicalAtomV2StateSha256, canonicalAtomV2StateJournalRecordBytes, decodeCanonicalAtomV2StateJournalRecordBytes, type CanonicalAtomV2StateJournalCommit } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.js"

const contract = "hswm-journal-replay/v1"
const boundary = { jsonParserProved: false, nativeEvolutionProved: false, permissionProved: false }
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left))
  return value.right
}
const code = (value: Either.Either<unknown, { readonly code: string }>) => Either.isLeft(value) ? value.left.code : "ACCEPTED"
const utf8 = (s: string) => new TextEncoder().encode(s)
const text = (s: Uint8Array) => new TextDecoder().decode(s)
const lean = (cases: readonly unknown[]) => JSON.parse(execFileSync(resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMJournalReplayCli"), [], {
  input: JSON.stringify(cases), encoding: "utf8", timeout: 20000, maxBuffer: 8 * 1024 * 1024, stdio: ["pipe", "pipe", "pipe"]
})) as unknown[]
const compareLean = (cases: readonly unknown[], expected: readonly unknown[]) => {
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1") expect(lean(cases)).toEqual(expected)
}
const withRoot = async (use: (root: string) => Promise<void>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-replay-"))
  try { await use(root) } finally { rmSync(root, { recursive: true, force: true }) }
}
const limits = { maximumRecords: 64, maximumRecoveredJournalBytes: 4 * 1024 * 1024 }
const cell = { base_url: "https://fixture.invalid/v1", model: "scripted-replay-fixture", max_tokens: 32 }
const http = (value: unknown) => ({ postJson: () => Effect.succeed(utf8(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))) })

// All positive frames originate in one real file-backed graph-loop history.
// Each witness is recomputed from recovered record bytes + stored envelopes,
// not from a hand-authored target state or caller-supplied validity booleans.
const example = (root: string) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const controller = yield* GraphLoopEngineeringController
  yield* seedSemanticLifecycle
  const trace = yield* executeLlmSemanticRelation(runtime, relationUid, "replay-training", cell, http({ prediction: "p", uncertainty: "u" }))
  const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "fixture-outcome", "authored-not-world-truth")
  const admission = yield* admissionForSemanticLifecycle(runtime, controller, trace, outcome, "candidate")
  yield* learnLlmSemanticRelation(runtime, trace, outcome, cell,
    http({ semanticText: "changed relation", disposition: "predict", uncertainty: "u", exceptionRefs: ["exception:door"] }),
    authorizationRef, scope, "2026-10-06T00:00:00.000Z", admission)
  const recovered = yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, limits)
  const genesis = right(decodeCanonicalAtomV2StateJournalRecordBytes(recovered.journal[0]!.bytes))
  if (genesis._tag !== "CanonicalAtomV2StateJournalGenesis") throw new Error("expected genesis")
  let previous = { state: right(applyCanonicalAtomV2StateJournalGenesis(runtime.schema, genesis)),
    descriptor: recovered.journal[0]!.descriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }
  const frames = []
  for (const entry of recovered.journal.slice(1)) {
    const record = right(decodeCanonicalAtomV2StateJournalRecordBytes(entry.bytes))
    if (record._tag !== "CanonicalAtomV2StateJournalCommit") throw new Error("expected commit")
    const envelopes = yield* Effect.forEach(record.writeBindings, b => runtime.readContent(b.envelope))
    const writes = envelopes.map(b => right(decodeCanonicalJsonBytes(b)) as unknown as CanonicalAtomV2)
    const receipt = record.receipt
    const command: CommitCanonicalAtomsV2Command = { _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2",
      schemaVersion: receipt.schemaVersion, transitionId: receipt.transitionId, expectedStateRevision: receipt.previousStateRevision,
      actorClaim: receipt.actorClaim, authorizationRef: receipt.authorizationRef, scope: receipt.scope, decidedAt: receipt.decidedAt,
      traceRef: receipt.traceRef, readSet: receipt.readSet, provenanceSha256: receipt.provenanceSha256, writes }
    const applied = right(applyCanonicalAtomV2StateJournalCommit(runtime.schema, previous, record, envelopes))
    expect(applied.descriptor).toEqual(entry.descriptor)
    const projected = projectCanonicalAtomV2Preservation(runtime.schema, runtime.schema, previous.state, applied.state, command)
    const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(command, previous.state.revision, applied.state.revision)
    const wire = { contract, kind: "step", active: runtime.schemaContent,
      before: { native: projected.before, descriptor: previous.descriptor, journalLineageId: previous.journalLineageId, schema: previous.schema }, record,
      witness: { after: projected.after, writes: projected.command.writes, previousDigest: right(canonicalAtomV2StateSha256(previous.state)),
        resultingDigest: right(canonicalAtomV2StateSha256(applied.state)), receiptBytes: [...right(canonicalJsonBytes(receipt))],
        expectedReceiptBytes: [...right(canonicalJsonBytes(expectedReceipt))], recordDescriptor: applied.descriptor } }
    frames.push({ wire, previous, envelopes, raw: entry.bytes })
    previous = { ...previous, state: applied.state, descriptor: applied.descriptor }
  }
  expect(previous.state).toEqual(recovered.state.canonical)
  return { schema: runtime.schema, recovered, frames }
}).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive))

type Example = Effect.Effect.Success<ReturnType<typeof example>>
type Wire = Example["frames"][number]["wire"]
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
const mutate = (wire: Wire, change: (copy: Mutable<Wire>) => void): Wire => {
  const copy = structuredClone(wire) as Mutable<Wire>; change(copy); return copy
}
const guards = (w: Wire) => ({ link: canonicalAtomV2JournalLinkMatches({ ...w.before, state: w.before.native }, w.record),
  schema: canonicalAtomV2JournalSchemaMatches(w.before.schema, w.record.schema),
  receipt: canonicalAtomV2JournalReceiptHeaderMatches(w.before.native.revision, w.record.stateRevision, w.active.schemaVersion, w.record.receipt) })
const inspected = (w: Wire) => {
  const g = guards(w), r = w.record, v = w.witness
  const accepted = g.link && g.schema && canonicalAtomV2JournalSchemaMatches(w.active, r.schema) && v.previousDigest === r.previousStateSha256 &&
    g.receipt && canonicalAtomV2PreservationHolds({ contract: "hswm-canonical-preservation/v1", before: w.before.native, after: v.after,
      command: { schemaVersion: r.receipt.schemaVersion, expectedStateRevision: r.receipt.previousStateRevision, transitionId: r.receipt.transitionId, writes: v.writes } }) &&
    canonicalAtomV2ExactBytes(Uint8Array.from(v.receiptBytes), Uint8Array.from(v.expectedReceiptBytes)) && v.resultingDigest === r.resultingStateSha256
  return { ...g, accepted, state: accepted ? v.after : null, ...boundary }
}

it("replays actual canonical bytes and receipts across a finite history and a fresh runtime", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root)); expect(e.frames).toHaveLength(2)
  const wires = e.frames.map(f => f.wire)
  const expected = wires.map(inspected); expect(expected.every(v => v.accepted)).toBe(true)
  compareLean(wires, expected)
  const initial = wires[0]!, records = wires.map(({ record, witness }) => ({ record, witness }))
  const chain = { contract, kind: "replay", active: initial.active, before: initial.before, records }
  compareLean([chain, { ...chain, records: [] }, { ...chain, records: records.slice(1) },
    { ...chain, records: [...records].reverse() }, { ...chain, records: [...records, records[1]] }],
    [wires[1]!.witness.after, initial.before.native, null, null, null].map(state => ({ state, ...boundary })))
  const reopened = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    return yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, limits)
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
  expect(reopened).toEqual(e.recovered)
}), 30000)

it.each(["receipt", "state-digest", "wire-spelling"] as const)("fresh runtime refuses re-addressed %s corruption after raw storage recovery succeeds", async kind => withRoot(async root => {
  const e = await Effect.runPromise(example(root)), frame = e.frames[1]!
  const changed = structuredClone(frame.wire.record) as Mutable<CanonicalAtomV2StateJournalCommit>
  if (kind === "receipt") changed.receipt.writeSet[0]!.atomUid += "x"
  if (kind === "state-digest") changed.resultingStateSha256 = "0".repeat(64)
  const encoded = right(canonicalAtomV2StateJournalRecordBytes(changed))
  const altered = kind === "wire-spelling" ? utf8(text(encoded) + "\n") : encoded
  const digest = createHash("sha256").update(altered).digest("hex")
  const oldObject = join(root, "journal-objects", frame.wire.witness.recordDescriptor.sha256)
  // Fault injection is confined to this test-owned temporary file store.
  // Re-addressing preserves raw hard-link/hash consistency, forcing native
  // decode/receipt/replay validation (rather than raw storage) to catch it.
  chmodSync(oldObject, 0o600); writeFileSync(oldObject, altered); chmodSync(oldObject, 0o400)
  linkSync(oldObject, join(root, "journal-objects", digest)); unlinkSync(oldObject)
  const raw = await Effect.runPromise(Effect.gen(function* () {
    const store = yield* CanonicalAtomV2StateJournalStore
    return yield* store.recover
  }).pipe(Effect.provide(makeCanonicalAtomV2StateJournalFileStoreLayer(root, frame.wire.before.journalLineageId, frame.wire.active.content.sha256)), Effect.provide(NodePosixServicesLive)))
  expect(raw).toHaveLength(3); expect(raw[2]!.descriptor.sha256).toBe(digest)
  const reopened = await Effect.runPromise(Effect.gen(function* () { return yield* CanonicalAtomV2DurableRuntime }).pipe(
    Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive), Effect.either))
  expect(Either.isLeft(reopened)).toBe(true)
  if (Either.isLeft(reopened)) expect(reopened.left).toMatchObject({ code: kind === "receipt" ? "RECEIPT_INVALID" : kind === "state-digest" ? "STATE_DIGEST_INVALID" : "RECORD_NOT_CANONICAL" })
}), 30000)

it("rejects noncanonical or malformed wire representations before replay", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root)); const raw = e.frames[1]!.raw, s = text(raw)
  const entries: { bytes: Uint8Array; expected: string }[] = e.recovered.journal.map(j => ({ bytes: j.bytes, expected: "ACCEPTED" }))
  const invalid = [s.slice(0, -1), s + "{}", '{"stateRevision":2,' + s.slice(1), '{"state\\u0052evision":2,' + s.slice(1),
    s.replace('"stateRevision":2', '"stateRevision":9007199254740992'), s.replace('"stateRevision":2', '"stateRevision":-1'),
    s.replace('"stateRevision":2', '"stateRevision":2.0'), s.replace('"stateRevision":2', '"stateRevision":2e0'),
    s.replace('"stateRevision":2', '"stateRevision":-0'), s.replace('"stateRevision":2', '"stateRevision":"2"'),
    '{"foreign":1,' + s.slice(1), s.replace('"decision":"ACCEPTED"', '"decision":"REJECTED"'),
    s.replace('"decision":"ACCEPTED"', '"decision":"ACCEPTED","decision":"ACCEPTED"')]
  expect(new Set(invalid).size).toBe(invalid.length); expect(invalid.every(v => v !== s)).toBe(true)
  entries.push(...invalid.map(v => ({ bytes: utf8(v), expected: "RECORD_INVALID" })), { bytes: Uint8Array.from([0xff]), expected: "RECORD_INVALID" },
    { bytes: utf8('"' + "x".repeat(1_048_576) + '"'), expected: "RECORD_INVALID" },
    ...[s + "\n", " " + s, JSON.stringify(JSON.parse(s), null, 2), s.replace('"stateRevision"', '"state\\u0052evision"')].map(v => ({ bytes: utf8(v), expected: "RECORD_NOT_CANONICAL" })))
  const codecCases = entries.map(({ bytes, expected }) => {
    expect(code(decodeCanonicalAtomV2StateJournalRecordBytes(bytes))).toBe(expected)
    // Only supply a canonical encoding after the actual native record encoder accepts the parsed value.
    const parsed = decodeCanonicalJsonBytes(bytes)
    const canonical = Either.isRight(parsed) ? canonicalAtomV2StateJournalRecordBytes(parsed.right as unknown as CanonicalAtomV2StateJournalCommit) : null
    return { contract, kind: "codec", raw: [...bytes], parsed: canonical !== null && Either.isRight(canonical),
      canonical: canonical !== null && Either.isRight(canonical) ? [...canonical.right] : null }
  })
  compareLean(codecCases, entries.map(e => ({ accepted: e.expected === "ACCEPTED", ...boundary })))
}), 30000)

it("binds replay headers, full receipt bytes, write envelopes and resulting state to the same transition", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root)); const frame = e.frames[1]!, base = frame.wire
  const cases: { wire: Wire; expected: string }[] = [{ wire: base, expected: "ACCEPTED" }]
  const change = (expected: string, fn: (v: Mutable<Wire>) => void) => cases.push({ wire: mutate(base, fn), expected })
  change("PREDECESSOR_INVALID", w => { w.record.journalLineageId += "x" })
  change("PREDECESSOR_INVALID", w => { w.record.predecessor.sha256 = "0".repeat(64) })
  change("PREDECESSOR_INVALID", w => { w.record.predecessor.byteLength++ })
  change("PREDECESSOR_INVALID", w => { w.record.stateRevision++ })
  change("SCHEMA_BINDING_INVALID", w => { w.record.schema.schemaVersion += "x" })
  change("SCHEMA_BINDING_INVALID", w => { w.record.schema.content.sha256 = "0".repeat(64) })
  change("SCHEMA_BINDING_INVALID", w => { w.record.schema.content.byteLength++ })
  change("SCHEMA_BINDING_INVALID", w => { w.record.schema.content.mediaType = "text/plain" })
  change("STATE_DIGEST_INVALID", w => { w.record.previousStateSha256 = "0".repeat(64) })
  change("RECEIPT_INVALID", w => { w.record.receipt.previousStateRevision++ })
  change("RECEIPT_INVALID", w => { w.record.receipt.nextStateRevision++ })
  change("RECEIPT_INVALID", w => { w.record.receipt.schemaVersion += "x" })
  change("STATE_DIGEST_INVALID", w => { w.record.resultingStateSha256 = "0".repeat(64) })
  for (const { wire, expected } of cases) {
    const decoded = right(decodeCanonicalAtomV2StateJournalRecordBytes(right(canonicalAtomV2StateJournalRecordBytes(wire.record))))
    if (decoded._tag !== "CanonicalAtomV2StateJournalCommit") throw new Error("expected commit")
    expect(code(applyCanonicalAtomV2StateJournalCommit(e.schema, frame.previous, decoded, frame.envelopes))).toBe(expected)
    expect(inspected(wire).accepted).toBe(expected === "ACCEPTED")
  }
  compareLean(cases.map(c => c.wire), cases.map(c => inspected(c.wire)))
  // Full receipt reconstruction catches write-set substitution even when header guards pass.
  const forged = mutate(base, w => { w.record.receipt.writeSet[0]!.atomUid += "x" })
  expect(Object.values(guards(forged)).every(Boolean)).toBe(true)
  expect(code(applyCanonicalAtomV2StateJournalCommit(e.schema, frame.previous, forged.record, frame.envelopes))).toBe("RECEIPT_INVALID")
  forged.witness.receiptBytes = [...right(canonicalJsonBytes(forged.record.receipt))]
  const nativeCases = [forged, mutate(base, w => { w.witness.after.atoms.shift() }),
    mutate(base, w => { w.witness.after.acceptedTransitionIds.reverse() }), mutate(base, w => { w.witness.writes[0]!.envelopeUtf8 += " " })]
  expect(nativeCases.every(w => !inspected(w).accepted)).toBe(true)
  compareLean(nativeCases, nativeCases.map(inspected))
  // Recovery is non-authorizing: coherently changing an unauthenticated actor
  // claim still reconstructs a valid receipt. Do not call this a signature proof.
  const actorChange = mutate(base, w => { w.record.receipt.actorClaim = "fixture:other-actor" })
  const actorApplied = right(applyCanonicalAtomV2StateJournalCommit(e.schema, frame.previous, actorChange.record, frame.envelopes))
  expect(actorApplied.state).toEqual(right(applyCanonicalAtomV2StateJournalCommit(e.schema, frame.previous, base.record, frame.envelopes)).state)
  actorChange.witness.receiptBytes = [...right(canonicalJsonBytes(actorChange.record.receipt))]
  actorChange.witness.expectedReceiptBytes = [...right(canonicalJsonBytes(actorApplied.record.receipt))]
  actorChange.witness.recordDescriptor = actorApplied.descriptor
  expect(inspected(actorChange).accepted).toBe(true)
  compareLean([actorChange], [inspected(actorChange)])
  for (const envelopes of [frame.envelopes.slice(1), [utf8("{}"), ...frame.envelopes.slice(1)],
    [utf8(text(frame.envelopes[0]!) + " "), ...frame.envelopes.slice(1)]]) {
    expect(code(applyCanonicalAtomV2StateJournalCommit(e.schema, frame.previous, base.record, envelopes))).toBe("ENVELOPE_INVALID")
  }
  const extra = [{ ...base, kind: "guards", record: { ...base.record, receipt: { ...base.record.receipt, decision: "REJECTED" } } },
    { ...base, kind: "guards", record: { ...base.record, receipt: { ...base.record.receipt, guard: { ...base.record.receipt.guard, permission: "CANONICAL_PERMIT" } } } }]
  compareLean(extra, extra.map(w => ({ ...guards(w as Wire), ...boundary })))
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1") {
    expect(() => lean([{ ...base, before: { ...base.before, native: { ...base.before.native, revision: -1 } } }])).toThrow()
    expect(() => lean([{ contract, kind: "codec", raw: [256], canonical: [256], parsed: true }])).toThrow()
  }
}), 30000)
