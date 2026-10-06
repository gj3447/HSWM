import { execFileSync } from "node:child_process"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect } from "effect"
import { expect, it, vi } from "vitest"
import { CanonicalAtomV2DurableRuntime, type CanonicalAtomV2DurableReceipt, type CanonicalAtomV2DurableState } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { GraphLoopControlJournal, GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { executeLlmSemanticRelation, learnLlmSemanticRelation, stageLlmSemanticOutcome } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { admissionForSemanticLifecycle, authorizationRef, makeSemanticLifecycleFileLayer, relationUid, scope, seedSemanticLifecycle } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type HSWMCanonicalSchemaV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import * as preservation from "../../src/hswm/effect-runtime/src/canonical-atom-v2-preservation.js"

type Wire = preservation.CanonicalAtomV2PreservationInput
type Mutable<A> = { -readonly [K in keyof A]: Mutable<A[K]> }
const mutable = (wire: Wire): Mutable<Wire> => structuredClone(wire) as Mutable<Wire>
const cell = { base_url: "https://fixture.invalid/v1", model: "scripted-proof-adapter", max_tokens: 32 }
const http = (value: unknown) => ({ postJson: () => Effect.succeed(new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value) } }] }))) })
const withRoot = async (use: (root: string) => Promise<void>) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-preservation-"))
  try { await use(root) } finally { rmSync(root, { recursive: true, force: true }) }
}

// Reconstruct writes from independently stored envelope bytes and the accepted
// receipt, rather than copying candidate-state atoms into the expected writes.
const projectCommit = (runtime: CanonicalAtomV2DurableRuntime["Type"], before: CanonicalAtomV2DurableState,
  after: CanonicalAtomV2DurableState, durable: CanonicalAtomV2DurableReceipt) => Effect.gen(function* () {
  const { receipt, writeBindings } = durable.commit
  const writes = yield* Effect.forEach(writeBindings, binding => runtime.readContent(binding.envelope).pipe(
    Effect.map(bytes => JSON.parse(new TextDecoder().decode(bytes)) as CanonicalAtomV2)))
  const command = { _tag: "CommitCanonicalAtomsV2" as const, contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    schemaVersion: receipt.schemaVersion, transitionId: receipt.transitionId, expectedStateRevision: receipt.previousStateRevision,
    actorClaim: receipt.actorClaim, authorizationRef: receipt.authorizationRef, scope: receipt.scope, decidedAt: receipt.decidedAt,
    traceRef: receipt.traceRef, readSet: receipt.readSet, provenanceSha256: receipt.provenanceSha256, writes }
  expect(durable.commit.predecessor).toEqual(before.journalHead)
  expect(durable.record).toEqual(after.journalHead)
  expect(after.schema).toEqual(before.schema)
  expect(after.journalLineageId).toBe(before.journalLineageId)
  const storedSchema = JSON.parse(new TextDecoder().decode(yield* runtime.readContent(after.schema.content))) as HSWMCanonicalSchemaV2
  return preservation.projectCanonicalAtomV2Preservation(runtime.schema, storedSchema, before.canonical, after.canonical, command)
})

const committedExample = (root: string) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const controller = yield* GraphLoopEngineeringController
  const initial = yield* runtime.snapshot
  const seeded = yield* seedSemanticLifecycle
  const trace = yield* executeLlmSemanticRelation(runtime, relationUid, "train", cell, http({ prediction: "p", uncertainty: "u" }))
  const outcome = yield* stageLlmSemanticOutcome(runtime, trace, "external-observation", "authored-fixture")
  const admission = yield* admissionForSemanticLifecycle(runtime, controller, trace, outcome, "candidate")
  yield* learnLlmSemanticRelation(runtime, trace, outcome, cell,
    http({ semanticText: "changed relation", disposition: "predict", uncertainty: "u", exceptionRefs: ["exception:door"] }),
    authorizationRef, scope, "2026-10-06T00:00:00.000Z", admission)
  const after = yield* runtime.snapshot
  const history = yield* runtime.history
  return { after, history, frames: [
    yield* projectCommit(runtime, initial, seeded.state, seeded.receipt),
    yield* projectCommit(runtime, seeded.state, after, history[history.length - 1]!)
  ] }
}).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive))

const rejectedMutations = (original: Wire) => {
  const cases: { name: string; wire: Wire }[] = []
  const mutate = (name: string, change: (wire: Mutable<Wire>) => void) => {
    const wire = mutable(original); change(wire); cases.push({ name, wire })
  }
  mutate("schema constraint", w => {
    const schema = JSON.parse(w.after.schemaUtf8); schema.kinds[0].minimumArity++
    w.after.schemaUtf8 = JSON.stringify(schema)
  })
  mutate("schema owner", w => {
    const schema = JSON.parse(w.after.schemaUtf8); schema.owners[0].obligation = "changed"
    w.after.schemaUtf8 = JSON.stringify(schema)
  })
  mutate("state schema version", w => { w.after.schemaVersion = "another" })
  mutate("command schema version", w => { w.command.schemaVersion = "another" })
  mutate("stale expected revision", w => { w.command.expectedStateRevision++ })
  mutate("skipped revision", w => { w.after.revision++ })
  mutate("unsafe revision", w => { w.before.revision = Number.MAX_SAFE_INTEGER; w.command.expectedStateRevision = w.before.revision; w.after.revision = w.before.revision + 1 })
  mutate("reopened bootstrap", w => { w.after.bootstrapClosed = false })
  mutate("lost history", w => { w.after.acceptedTransitionIds.shift() })
  mutate("reordered history", w => { w.after.acceptedTransitionIds.reverse() })
  mutate("duplicate transition", w => { w.command.transitionId = w.before.acceptedTransitionIds[0]!; w.after.acceptedTransitionIds[w.after.acceptedTransitionIds.length - 1] = w.command.transitionId })
  const envelope = (name: string, change: (atom: Mutable<CanonicalAtomV2>) => void) => mutate(name, w => {
    const key = w.before.atoms.find(image => (JSON.parse(image.envelopeUtf8) as CanonicalAtomV2).references.length > 1)!.key
    const image = w.after.atoms.find(image => image.key === key)!
    const atom = JSON.parse(image.envelopeUtf8) as Mutable<CanonicalAtomV2>; change(atom); image.envelopeUtf8 = JSON.stringify(atom)
  })
  envelope("lifecycle", atom => { Object.assign(atom, { lifecycle: "RETIRED" }) })
  envelope("owner", atom => { atom.responsibilityOwner = "owner:changed" })
  envelope("provenance", atom => { atom.provenance.evidenceSha256 = "0".repeat(64) })
  envelope("payload descriptor", atom => { atom.content.byteLength++ })
  envelope("reference order", atom => { atom.references.reverse() })
  envelope("reference role", atom => { atom.references[0]!.role = "changed" })
  envelope("reference target", atom => { atom.references[0]!.target.atomUid = "changed" })
  envelope("native key", atom => { atom.key.atomUid = "changed" })
  mutate("missing old envelope", w => { w.after.atoms = w.after.atoms.filter(atom => atom.key !== w.before.atoms[0]!.key) })
  mutate("missing write", w => { w.after.atoms = w.after.atoms.filter(atom => atom.key !== w.command.writes[0]!.key) })
  mutate("altered write", w => { w.command.writes[0]!.envelopeUtf8 += " " })
  mutate("foreign atom", w => { w.after.atoms.push({ key: "foreign", envelopeUtf8: "{}" }) })
  mutate("duplicate before key", w => { w.before.atoms.push(w.before.atoms[0]!) })
  mutate("duplicate after key", w => { w.after.atoms.push(w.after.atoms[0]!) })
  mutate("duplicate write key", w => { w.command.writes.push(w.command.writes[0]!) })
  mutate("overwritten old key", w => { w.command.writes[0] = w.before.atoms[0]! })
  mutate("empty writes", w => { w.command.writes = [] })
  return cases
}

it("preserves complete native values across actual graph-loop commits and file reopen; rejects lost or rewritten fields", async () => withRoot(async root => {
  const { after, history, frames } = await Effect.runPromise(committedExample(root))
  expect(frames.map(preservation.canonicalAtomV2PreservationHolds)).toEqual([true, true])
  expect(after.canonical.revision).toBe(2)
  const reopened = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    return { after: yield* runtime.snapshot, history: yield* runtime.history }
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
  expect(reopened).toEqual({ after, history })
  for (const { name, wire } of rejectedMutations(frames[1]!)) expect(preservation.canonicalAtomV2PreservationHolds(wire), name).toBe(false)
  const reordered = mutable(frames[1]!); reordered.after.atoms.reverse()
  expect(preservation.canonicalAtomV2PreservationHolds(reordered)).toBe(true)
}))

it("refuses canonical publication when the mandatory preservation postcondition fails", async () => withRoot(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const journal = yield* GraphLoopControlJournal
    const before = yield* runtime.snapshot
    const history = yield* runtime.history
    const guard = vi.spyOn(preservation, "verifyCanonicalAtomV2Preservation").mockReturnValue(false)
    try {
      const result = yield* seedSemanticLifecycle.pipe(Effect.either)
      expect(guard).toHaveBeenCalled()
      expect(result).toMatchObject({ _tag: "Left", left: { code: "BOOTSTRAP_NOT_COMMITTED" } })
      expect(yield* runtime.snapshot).toEqual(before)
      expect(yield* runtime.history).toEqual(history)
      const entries = yield* journal.recover
      expect(entries[entries.length - 1]!.event).toMatchObject({ phase: "REJECTED", reason: "STATE_PRESERVATION_FAILED" })
    } finally { guard.mockRestore() }
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive)))
}))

it.runIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1")("agrees with Lean on stored artifacts, corruptions and conditional admission", async () => withRoot(async root => {
  const { frames } = await Effect.runPromise(committedExample(root))
  const reordered = mutable(frames[1]!); reordered.after.atoms.reverse()
  const good = [...frames, reordered]
  const bad = rejectedMutations(frames[1]!).map(({ wire }) => wire)
  const cases = [...good, ...bad].map(wire => ({ ...wire, authorized: true, structurallyValid: true }))
  cases.push({ ...frames[1]!, authorized: false, structurallyValid: true }, { ...frames[1]!, authorized: true, structurallyValid: false })
  const binary = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMCanonicalPreservationCli")
  const check = (input: unknown) => JSON.parse(execFileSync(binary, [], { input: JSON.stringify(input), encoding: "utf8", timeout: 15000, stdio: ["pipe", "pipe", "pipe"] })) as {
    preserves: boolean; approvedUnderSuppliedFlags: boolean; unchanged: boolean; permissionProved: boolean; physicalAtomicityProved: boolean
  }[]
  const results = check(cases)
  expect(results).toHaveLength(cases.length)
  for (const [index, wire] of cases.entries()) {
    const holds = preservation.canonicalAtomV2PreservationHolds(wire)
    expect(results[index]).toEqual({ preserves: holds, approvedUnderSuppliedFlags: wire.authorized && wire.structurallyValid && holds,
      unchanged: !(wire.authorized && wire.structurallyValid && holds), permissionProved: false, physicalAtomicityProved: false })
  }
  expect(results.slice(0, good.length).every(result => result.preserves)).toBe(true)
  expect(results.slice(good.length, good.length + bad.length).every(result => !result.preserves)).toBe(true)
  const negative = { ...cases[0]!, before: { ...cases[0]!.before, revision: -1 } }
  expect(() => check([negative])).toThrow()
}), 30000)
