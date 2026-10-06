import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime, recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { executeLlmSemanticRelation, learnLlmSemanticRelation, stageLlmSemanticOutcome } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { admissionForSemanticLifecycle, authorizationRef, makeSemanticLifecycleFileLayer, relationUid, scope, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { compareCanonicalAtomV2Keys, evolveCanonicalAtomsV2, makeCanonicalAtomV2AcceptedReceipt, makeCanonicalAtomV2CandidateState, type CanonicalAtomV2State, type CanonicalAtomV2EffectReceipt } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import { HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE, canonicalAtomV2EnvelopeBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { canonicalAtomV2PreservationHolds, projectCanonicalAtomV2Preservation } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-preservation.js"
import { canonicalAtomV2ExactBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-guards.js"
import { canonicalAtomV2JournalEnvelopeMatches, canonicalAtomV2JournalReceiptCommand } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-adapter.js"
import { applyCanonicalAtomV2StateJournalGenesis, applyCanonicalAtomV2StateJournalCommit, decodeCanonicalAtomV2StateJournalRecordBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.js"

const contract = "hswm-journal-adapter/v1"
const boundary = { jsonParserProved: false, nativeValidationProved: false, permissionProved: false }
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left))
  return value.right
}
const errorCode = (value: Either.Either<unknown, { readonly code: string }>) => Either.isLeft(value) ? value.left.code : "ACCEPTED"
const utf8 = (value: string) => new TextEncoder().encode(value)
const leanPath = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMJournalAdapterCli")
const compareLean = (cases: readonly unknown[], expected: readonly unknown[]) => {
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1") {
    const result = execFileSync(leanPath, [], { input: JSON.stringify(cases), encoding: "utf8", timeout: 20000, maxBuffer: 16 * 1024 * 1024 })
    expect(JSON.parse(result)).toEqual(expected)
  }
}
const withRoot = async (use: (root: string) => Promise<void>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-adapter-"))
  try { await use(root) } finally { rmSync(root, { recursive: true, force: true }) }
}
const cell = { base_url: "https://fixture.invalid/v1", model: "scripted-adapter-fixture", max_tokens: 32 }
const http = (value: unknown) => ({ postJson: () => Effect.succeed(utf8(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))) })
const example = (root: string) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime, controller = yield* GraphLoopEngineeringController
  yield* seedSemanticLifecycle
  const trace = yield* executeLlmSemanticRelation(runtime, relationUid, "adapter-training", cell, http({ prediction: "p", uncertainty: "u" }))
  const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "fixture-outcome", "authored-not-world-truth")
  const admission = yield* admissionForSemanticLifecycle(runtime, controller, trace, outcome, "candidate")
  yield* learnLlmSemanticRelation(runtime, trace, outcome, cell,
    http({ semanticText: "changed relation", disposition: "predict", uncertainty: "u", exceptionRefs: ["exception:door"] }),
    authorizationRef, scope, "2026-10-06T00:00:00.000Z", admission)
  const recovered = yield* recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, { maximumRecords: 64, maximumRecoveredJournalBytes: 4 * 1024 * 1024 })
  const genesis = right(decodeCanonicalAtomV2StateJournalRecordBytes(recovered.journal[0]!.bytes))
  if (genesis._tag !== "CanonicalAtomV2StateJournalGenesis") throw new Error("expected genesis")
  let previous = { state: right(applyCanonicalAtomV2StateJournalGenesis(runtime.schema, genesis)), descriptor: recovered.journal[0]!.descriptor,
    journalLineageId: genesis.journalLineageId, schema: genesis.schema }
  const frames = []
  for (const entry of recovered.journal.slice(1)) {
    const record = right(decodeCanonicalAtomV2StateJournalRecordBytes(entry.bytes))
    if (record._tag !== "CanonicalAtomV2StateJournalCommit") throw new Error("expected commit")
    const envelopes = yield* Effect.forEach(record.writeBindings, b => runtime.readContent(b.envelope))
    const writes = envelopes.map(b => right(decodeCanonicalJsonBytes(b)) as unknown as CanonicalAtomV2)
    const applied = right(applyCanonicalAtomV2StateJournalCommit(runtime.schema, previous, record, envelopes))
    frames.push({ previous, record, writes, envelopes, applied })
    previous = { ...previous, state: applied.state, descriptor: applied.descriptor }
  }
  expect(previous.state).toEqual(recovered.state.canonical)
  return { schema: runtime.schema, frames }
}).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive))

// Image extraction is separately observed from the existing complete-envelope
// preservation adapter. Lean receives neither an after-state nor receipt result.
const comparison = (schema: HSWMCanonicalSchemaV2, before: CanonicalAtomV2State, receipt: CanonicalAtomV2EffectReceipt, writes: readonly CanonicalAtomV2[]) => {
  const command = canonicalAtomV2JournalReceiptCommand(receipt, writes)
  const candidate = makeCanonicalAtomV2CandidateState(before, command)
  const image = projectCanonicalAtomV2Preservation(schema, schema, before, candidate, command)
  const enrich = (atoms: readonly CanonicalAtomV2[], images: readonly { readonly envelopeUtf8: string }[]) => atoms.map((atom, index) =>
    ({ key: atom.key, content: atom.content, envelopeUtf8: images[index]!.envelopeUtf8 }))
  const wireWrites = enrich(writes, image.command.writes)
  const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(command, before.revision, candidate.revision)
  return {
    wire: { contract, kind: "adapter", before: { ...image.before, atoms: enrich(before.atoms, image.before.atoms) }, receipt, writes: wireWrites },
    expected: { command: { ...command, writes: wireWrites }, candidate: { ...image.after, atoms: enrich(candidate.atoms, image.after.atoms) },
      receipt: expectedReceipt, receiptMatches: canonicalAtomV2ExactBytes(right(canonicalJsonBytes(receipt)), right(canonicalJsonBytes(expectedReceipt))),
      preservation: canonicalAtomV2PreservationHolds(image), ...boundary },
    command, candidate
  }
}

it("computes native candidates and full receipts from two real persisted graph-loop transitions", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root))
  const cases = e.frames.map(f => {
    const c = comparison(e.schema, f.previous.state, f.record.receipt, f.writes)
    expect(right(evolveCanonicalAtomsV2(e.schema, f.previous.state, c.command))).toEqual(c.candidate)
    expect(c.candidate).toEqual(f.applied.state)
    expect(c.expected.receipt).toEqual(f.record.receipt)
    expect(c.expected.receiptMatches && c.expected.preservation).toBe(true)
    return c
  })
  expect(cases).toHaveLength(2)
  compareLean(cases.map(c => c.wire), cases.map(c => c.expected))
}), 30000)

it("reconstructs receipt sets, retains native refusal boundaries and does not authenticate copied metadata", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root)), f = e.frames[1]!
  const receipt = f.record.receipt, before = f.previous.state
  const variants = [
    comparison(e.schema, before, { ...receipt, writeSet: [] }, f.writes),
    comparison(e.schema, before, { ...receipt, writeSet: [...receipt.writeSet, receipt.writeSet[0]!] }, f.writes),
    comparison(e.schema, before, { ...receipt, nextStateRevision: receipt.nextStateRevision + 1 }, f.writes),
    comparison(e.schema, before, { ...receipt, previousStateRevision: receipt.previousStateRevision + 1 }, f.writes),
    comparison(e.schema, before, { ...receipt, schemaVersion: "different-schema" }, f.writes),
    comparison(e.schema, before, { ...receipt, readSet: [...receipt.readSet].reverse() }, f.writes),
    comparison(e.schema, before, { ...receipt, readSet: [...receipt.readSet, receipt.readSet[0]!] }, f.writes),
    comparison(e.schema, { ...before, acceptedTransitionIds: [...before.acceptedTransitionIds, receipt.transitionId] }, receipt, f.writes),
    comparison(e.schema, before, receipt, []),
    comparison(e.schema, before, receipt, [before.atoms[0]!]),
    comparison(e.schema, before, receipt, [...f.writes, f.writes[0]!]),
    comparison(e.schema, before, { ...receipt, actorClaim: "different-actor", authorizationRef: "different-reference",
      scope: "different-scope", decidedAt: "2026-10-06T01:00:00.000Z", provenanceSha256: "0".repeat(64) }, f.writes)
  ]
  expect(variants).toHaveLength(12)
  expect(variants[0]!.expected.receiptMatches).toBe(false)
  expect(variants[1]!.expected.receiptMatches).toBe(false)
  expect(variants[2]!.expected.receiptMatches).toBe(false)
  expect(variants[3]!.expected.preservation).toBe(false)
  expect(variants[4]!.expected.preservation).toBe(false)
  expect(receipt.readSet.length).toBeGreaterThan(1)
  expect(variants[5]!.expected.receiptMatches).toBe(false)
  // Candidate construction is deliberately NOT native structural validation.
  expect(variants[6]!.expected.preservation).toBe(true)
  expect(errorCode(evolveCanonicalAtomsV2(e.schema, before, variants[6]!.command))).toBe("READ_SET_INVALID")
  for (const index of [7, 8, 9, 10]) expect(variants[index]!.expected.preservation).toBe(false)
  const metadata = variants[11]!
  expect(metadata.expected.receiptMatches && metadata.expected.preservation).toBe(true)
  expect(right(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous,
    { ...f.record, receipt: metadata.wire.receipt }, f.envelopes)).state).toEqual(f.applied.state)
  compareLean(variants.map(c => c.wire), variants.map(c => c.expected))
}), 30000)

it("binds observed exact envelope descriptors, keys and payloads and refuses wire substitutions", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root)), f = e.frames[0]!, atom = f.writes[0]!, raw = f.envelopes[0]!
  const binding = f.record.writeBindings[0]!
  const envelope = { mediaType: HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE, byteLength: raw.byteLength,
    sha256: createHash("sha256").update(raw).digest("hex") }
  expect([...right(canonicalAtomV2EnvelopeBytes(atom))]).toEqual([...raw])
  const wireAtom = comparison(e.schema, f.previous.state, f.record.receipt, f.writes).wire.writes[0]!
  const variants = [binding,
    { ...binding, envelope: { ...binding.envelope, mediaType: "application/other" } },
    { ...binding, envelope: { ...binding.envelope, byteLength: binding.envelope.byteLength + 1 } },
    { ...binding, envelope: { ...binding.envelope, sha256: "0".repeat(64) } },
    { ...binding, key: { ...binding.key, revisionId: binding.key.revisionId + 1 } },
    { ...binding, key: { ...binding.key, atomUid: binding.key.atomUid + "x" } },
    { ...binding, key: { ...binding.key, lineageId: binding.key.lineageId + "x" } },
    { ...binding, key: { ...binding.key, schemaVersion: binding.key.schemaVersion + "x" } },
    { ...binding, payload: { ...binding.payload, mediaType: "application/other" } },
    { ...binding, payload: { ...binding.payload, byteLength: binding.payload.byteLength + 1 } },
    { ...binding, payload: { ...binding.payload, sha256: "0".repeat(64) } }
  ]
  const cases = variants.map(binding => ({ contract, kind: "envelope", atom: wireAtom, envelope, binding }))
  const expected = variants.map(binding => ({ matches: canonicalAtomV2JournalEnvelopeMatches(atom, envelope, binding), ...boundary }))
  expect(expected.map(e => e.matches)).toEqual([true, ...Array<boolean>(10).fill(false)])
  for (const changed of variants.slice(1)) {
    expect(errorCode(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous,
      { ...f.record, writeBindings: [changed, ...f.record.writeBindings.slice(1)] }, f.envelopes))).toBe("ENVELOPE_INVALID")
  }
  const noncanonical = utf8(new TextDecoder().decode(raw) + "\n")
  const duplicateField = utf8(new TextDecoder().decode(raw).replace('{', '{"_tag":"CanonicalAtomV2",'))
  for (const changed of [noncanonical, duplicateField, utf8("{"), utf8('{"extra":true}')]) {
    expect(errorCode(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous, f.record,
      [changed, ...f.envelopes.slice(1)]))).toBe("ENVELOPE_INVALID")
  }
  expect(errorCode(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous, f.record, f.envelopes.slice(1)))).toBe("ENVELOPE_INVALID")
  expect(errorCode(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous, f.record, [...f.envelopes].reverse()))).toBe("ENVELOPE_INVALID")
  expect(right(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous, f.record, f.writes))).toEqual(f.applied)
  compareLean(cases, expected)
}), 30000)

it("keeps numeric candidate order distinct from journal binding order and snapshots atom data", async () => withRoot(async root => {
  const e = await Effect.runPromise(example(root)), f = e.frames[0]!
  // Synthetic decoded inputs exercise the producer, without claiming that
  // non-genesis revisions pass the native bootstrap/provenance validator.
  const writes = [10, 2, 0].map(revisionId => ({ ...structuredClone(f.writes[0]!), key: { ...f.writes[0]!.key, revisionId } }))
  const variants = [writes, [...writes].reverse(), [writes[1]!, writes[0]!, writes[2]!]].map(atoms =>
    comparison(e.schema, f.previous.state, f.record.receipt, atoms))
  for (const c of variants) {
    expect(c.candidate.atoms.map(a => a.key.revisionId)).toEqual([0, 2, 10])
    expect(c.expected.preservation).toBe(true)
    expect(errorCode(evolveCanonicalAtomsV2(e.schema, f.previous.state, c.command))).not.toBe("ACCEPTED")
  }
  expect(variants[0]!.candidate).toEqual(variants[1]!.candidate)
  compareLean(variants.map(c => c.wire), variants.map(c => c.expected))
  const candidate = variants[0]!.candidate, snapshot = JSON.stringify(candidate)
  expect(candidate.atoms.find(a => a.key.revisionId === 10)).not.toBe(writes[0])
  writes[0]!.key = { ...writes[0]!.key, atomUid: "changed-after-construction" }
  expect(JSON.stringify(candidate)).toBe(snapshot)
  expect(Object.isFrozen(candidate.atoms[0]!.key)).toBe(true)
  const numericAtoms = [2, 10].map(revisionId => ({ ...f.writes[0]!, key: { ...f.writes[0]!.key, revisionId } }))
  const envelopes = numericAtoms.map(atom => right(canonicalAtomV2EnvelopeBytes(atom)))
  const bindings = numericAtoms.map((atom, i) => ({ key: atom.key, payload: atom.content,
    envelope: { mediaType: HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE, byteLength: envelopes[i]!.byteLength,
      sha256: createHash("sha256").update(envelopes[i]!).digest("hex") } }))
  expect(errorCode(applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous,
    { ...f.record, writeBindings: bindings }, envelopes))).toBe("WRITE_BINDING_INVALID")
  const lexical = applyCanonicalAtomV2StateJournalCommit(e.schema, f.previous,
    { ...f.record, writeBindings: [...bindings].reverse() }, [...envelopes].reverse())
  expect(errorCode(lexical)).not.toBe("WRITE_BINDING_INVALID")
  expect(errorCode(lexical)).not.toBe("ACCEPTED")
}), 30000)

it("orders native key components and numeric revisions including the safe integer boundary", () => {
  const base: CanonicalAtomV2Key = { schemaVersion: "s", lineageId: "l", atomUid: "a", revisionId: 0 }
  const keys = [0, 1, 2, 9, 10, 99, Number.MAX_SAFE_INTEGER].map(revisionId => ({ ...base, revisionId }))
  const text = ["A", "Z", "a", "a-", "a.", "a/", "a0", "a:", "a_", "z"]
  for (const field of ["schemaVersion", "lineageId", "atomUid"] as const) for (const value of text) keys.push({ ...base, [field]: value })
  const pairs = keys.flatMap(left => keys.map(right => ({ contract, kind: "comparator", left, right })))
  expect(pairs).toHaveLength(1369)
  expect(compareCanonicalAtomV2Keys({ ...base, revisionId: 2 }, { ...base, revisionId: 10 })).toBeLessThan(0)
  expect(canonicalAtomV2KeyId({ ...base, revisionId: 2 }) > canonicalAtomV2KeyId({ ...base, revisionId: 10 })).toBe(true)
  compareLean(pairs, pairs.map(p => ({ order: Math.sign(compareCanonicalAtomV2Keys(p.left, p.right)), ...boundary })))
})

it("rejects unsafe or negative key revisions at the Lean wire boundary", () => {
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] !== "1") return
  const key = { schemaVersion: "s", lineageId: "l", atomUid: "a", revisionId: 0 }
  for (const revisionId of [-1, Number.MAX_SAFE_INTEGER + 1, 0.5]) {
    expect(() => execFileSync(leanPath, [], { input: JSON.stringify([{ contract, kind: "comparator", left: key, right: { ...key, revisionId } }]),
      stdio: ["pipe", "pipe", "pipe"] })).toThrow()
  }
})
