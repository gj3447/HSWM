import { execFileSync } from "node:child_process"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect } from "effect"
import { expect, it } from "vitest"
import { CanonicalAtomV2DurableRuntime } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { GraphLoopEngineeringController } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.js"
import { graphLoopHeadMatches, graphLoopEmptyMatchAllowed, graphLoopCandidateMatches, type GraphLoopHead, type GraphLoopCandidateReadView } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-guards.js"
import { readLlmSemanticFrame } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { canonicalAtomV2StateSha256 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { canonicalAtomV2KeyId, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { authorizationRef, scope, bytes, relationUid, seedSemanticLifecycle, makeSemanticLifecycleFileLayer } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

type Wire = { contract: "hswm-graph-loop-preflight/v1"; source: GraphLoopHead; current: GraphLoopHead; keys: readonly string[]; candidate: GraphLoopCandidateReadView; affected: readonly string[] }
const inspect = (wire: Wire) => {
  const fresh = graphLoopHeadMatches(wire.source, wire.current)
  const emptyMatchAllowed = graphLoopEmptyMatchAllowed(wire.current.stateRevision, wire.keys, wire.candidate.readKeys, wire.affected)
  const candidateMatches = graphLoopCandidateMatches(wire.source, wire.keys, wire.candidate, wire.affected)
  return { fresh, emptyMatchAllowed, candidateMatches, preflight: fresh && emptyMatchAllowed && candidateMatches, admissionProved: false }
}

const actualUnrelatedWrite = () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-preflight-"))
  return Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const controller = yield* GraphLoopEngineeringController
    yield* seedSemanticLifecycle
    const frameBefore = yield* readLlmSemanticFrame(runtime, relationUid, "same-event")
    const before = yield* runtime.snapshot
    const evidence = yield* runtime.stageContent("application/json", bytes({ check: "fixture only", efficacy: "NOT_ADJUDICATED" }))
    const acceptedRun = (runId: string) => Effect.gen(function* () {
      const triggered = yield* controller.trigger({ runId, triggerId: `trigger:${runId}`, actorId: "fixture:actor", verifierId: "fixture:verifier", maximumAttempts: 1, maximumActions: 1 })
      yield* controller.sealAction(runId, evidence)
      yield* controller.recordVerification(runId, "ACCEPT", evidence)
      return triggered.event.snapshot
    })
    const source = yield* acceptedRun("old")
    yield* acceptedRun("unrelated")
    const template = before.canonical.atoms.find(atom => atom.kind === "semantic_participant")!
    const makeRequest = (runId: string, expectedStateRevision: number, uid: string) => Effect.gen(function* () {
      const atom = { ...template, key: { ...template.key, atomUid: uid },
        provenance: { mode: "DERIVATION" as const, evidenceSha256: evidence.sha256, sourceRef: frameBefore.relation.key } }
      const envelope = yield* describeCanonicalAtomV2Envelope(atom)
      return {
        runId, transactionId: `transaction:${runId}`, affectedKeys: [frameBefore.relation.key],
        evidence: { sealedTrajectory: evidence, outcome: evidence, credit: evidence, authorization: evidence, invariant: evidence,
          authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT" as const, conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP" as const },
        candidate: makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
          _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
          transitionId: `transition:${runId}`, expectedStateRevision, schemaVersion: template.key.schemaVersion,
          actorClaim: "fixture:actor", authorizationRef, scope, decidedAt: "2026-10-05T00:00:00.000Z",
          traceRef: null, readSet: [frameBefore.relation.key], writes: [atom], provenanceSha256: evidence.sha256
        }, [{ key: atom.key, payload: atom.content, envelope }])
      }
    })
    const oldRequest = yield* makeRequest("old", before.canonical.revision, "unrelated:old")
    const unrelated = yield* controller.submitDelta(yield* makeRequest("unrelated", before.canonical.revision, "unrelated:new"))
    expect(unrelated.disposition).toBe("COMMITTED")
    const after = yield* runtime.snapshot
    const frameAfter = yield* readLlmSemanticFrame(runtime, relationUid, "same-event")
    const payload = ({ event, relation, roles, priorEvidence }: typeof frameBefore) => ({ event, relation, roles, priorEvidence })
    expect(payload(frameAfter)).toEqual(payload(frameBefore))
    expect(frameAfter.stateRevision).toBe(frameBefore.stateRevision + 1)
    expect(frameAfter.frameSha256).not.toBe(frameBefore.frameSha256)
    expect((yield* controller.submitDelta(oldRequest)).disposition).toBe("QUARANTINED")
    expect(yield* runtime.snapshot).toEqual(after)
    expect((yield* controller.recover).get("old")?.phase).toBe("QUARANTINED")
    const afterDigest = yield* canonicalAtomV2StateSha256(after.canonical)
    const command = oldRequest.candidate.command
    const fresh: Wire = { contract: "hswm-graph-loop-preflight/v1", source, current: source,
      keys: before.canonical.atoms.map(atom => canonicalAtomV2KeyId(atom.key)),
      candidate: { schemaContentSha256: oldRequest.candidate.schemaContentSha256, schemaVersion: command.schemaVersion,
        expectedStateRevision: command.expectedStateRevision, traceAbsent: command.traceRef === null,
        writeCount: command.writes.length, readKeys: command.readSet.map(canonicalAtomV2KeyId) },
      affected: oldRequest.affectedKeys.map(canonicalAtomV2KeyId) }
    const stale: Wire = { ...fresh, keys: after.canonical.atoms.map(atom => canonicalAtomV2KeyId(atom.key)),
      current: { journalLineageId: after.journalLineageId, schema: after.schema, stateRevision: after.canonical.revision,
        stateSha256: afterDigest, journalHead: after.journalHead } }
    expect(inspect(fresh).preflight).toBe(true)
    expect(inspect(stale)).toMatchObject({ fresh: false, candidateMatches: true, preflight: false })
    return { fresh, stale }
  }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)), Effect.provide(NodePosixServicesLive),
    Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true }))))
}

it("preserves a full local payload after a disjoint write but quarantines the stale approved candidate", async () => {
  await Effect.runPromise(actualUnrelatedWrite())
})

it.runIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1")("compares actual heads, all guard fields and read-set mutations with Lean", async () => {
  const { fresh, stale } = await Effect.runPromise(actualUnrelatedWrite())
  const mutate = (change: (wire: Wire) => Wire) => change(structuredClone(fresh))
  const bad: Wire[] = [stale]
  for (const field of ["journalLineageId", "stateSha256"] as const) bad.push(mutate(w => ({ ...w, current: { ...w.current, [field]: "different" } })))
  bad.push(mutate(w => ({ ...w, current: { ...w.current, stateRevision: w.current.stateRevision + 1 } })))
  bad.push(mutate(w => ({ ...w, current: { ...w.current, schema: { ...w.current.schema, schemaVersion: "different" } } })))
  for (const part of ["schema", "journalHead"] as const) {
    for (const field of ["sha256", "mediaType", "byteLength"] as const) bad.push(mutate(w => {
      const original = part === "schema" ? w.current.schema.content : w.current.journalHead
      const descriptor = { ...original, [field]: field === "byteLength" ? original.byteLength + 1 : "different" }
      return { ...w, current: part === "schema" ? { ...w.current, schema: { ...w.current.schema, content: descriptor } } : { ...w.current, journalHead: descriptor } }
    }))
  }
  for (const update of [{ schemaContentSha256: "different" }, { schemaVersion: "different" }, { expectedStateRevision: 99 }, { traceAbsent: false }, { writeCount: 0 }, { readKeys: ["absent"] }] as const) bad.push(mutate(w => ({ ...w, candidate: { ...w.candidate, ...update } })))
  bad.push(mutate(w => ({ ...w, affected: ["unread"] })), mutate(w => ({ ...w, keys: [] })), mutate(w => ({ ...w, affected: [] })))
  expect(bad.every(wire => !inspect(wire).preflight)).toBe(true)
  const genesisHead = { ...fresh.source, stateRevision: 0 }
  const genesis: Wire = { ...fresh, source: genesisHead, current: genesisHead, keys: [], affected: [], candidate: { ...fresh.candidate, expectedStateRevision: 0, readKeys: [] } }
  const cases = [fresh, genesis, ...bad, { ...genesis, keys: ["unexpected"] }, { ...genesis, candidate: { ...genesis.candidate, readKeys: ["unexpected"] } }]
  expect(inspect(genesis).preflight).toBe(true)
  const binary = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMGraphLoopPreflightCli")
  const checked = JSON.parse(execFileSync(binary, [], { input: JSON.stringify(cases), encoding: "utf8", timeout: 15000 }))
  expect(checked).toEqual(cases.map(inspect))
  expect(checked.filter((value: { preflight: boolean }) => value.preflight)).toHaveLength(2)
  expect(() => execFileSync(binary, [], { input: JSON.stringify([{ ...genesis, candidate: { ...genesis.candidate, writeCount: -1 } }]), stdio: ["pipe", "pipe", "pipe"] })).toThrow()
}, 30000)
