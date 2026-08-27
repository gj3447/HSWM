import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs"
import { createHash } from "node:crypto"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Effect, Either, Layer } from "effect"
import { expect, it } from "vitest"

import { DNRD_ROUTING_PAYLOAD_V1, makeDnrdOutcomeObservation, type DnrdRoutingPayload } from "../src/canonical-atom-v2-routing-diagnostic.js"
import { DnrdRoutingDiagnosticFile, makeDnrdRoutingDiagnosticFileLayer } from "../src/canonical-atom-v2-routing-diagnostic-file.js"

const hash = (letter: string) => letter.repeat(64)
const payload = (): DnrdRoutingPayload => ({ schemaVersion: DNRD_ROUTING_PAYLOAD_V1, contexts: [
  { contextSha256: hash("a"), stratum: "stratum:one", routes: [{ routeId: "route:a", scoreMicros: 10 }, { routeId: "route:b", scoreMicros: 0 }] },
  { contextSha256: hash("b"), stratum: "stratum:one", routes: [{ routeId: "route:a", scoreMicros: 0 }, { routeId: "route:b", scoreMicros: 10 }] }
], structuralStatus: "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" })

it("DNRD file adapter recovers W0/W1 and only records local structural state", async () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-dnrd-file-"))
  try {
    const layer = makeDnrdRoutingDiagnosticFileLayer(root) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
    const program = Effect.gen(function* () {
      const adapter = yield* DnrdRoutingDiagnosticFile
      yield* adapter.initialize(payload())
      const before = (yield* adapter.project(hash("a"))) as { readonly selection: { readonly routeId: string } }
      const trace = yield* adapter.sealTrainingTrajectory({ episodeId: "episode:file", contextSha256: hash("a"), routeId: "route:b", requestSha256: hash("c"), responseSha256: hash("d") })
      const outcome = makeDnrdOutcomeObservation({ traceId: trace.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 1_000_000, scorerObservationSha256: hash("e") })
      if (Either.isLeft(outcome)) throw outcome.left
      const forged = { ...outcome.right, scorerObservationSha256: hash("f") }
      const forgedResult = yield* Effect.either(adapter.applyOutcome(forged, 100_000, 100_000))
      yield* adapter.applyOutcome(outcome.right, 100_000, 100_000)
      const secondOutcome = makeDnrdOutcomeObservation({ traceId: trace.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 0, scorerObservationSha256: hash("f") })
      if (Either.isLeft(secondOutcome)) throw secondOutcome.left
      const repeatedTraceResult = yield* Effect.either(adapter.applyOutcome(secondOutcome.right, 100_000, 100_000))
      const resealed = yield* adapter.sealTrainingTrajectory({ episodeId: "episode:file", contextSha256: hash("a"), routeId: "route:b", requestSha256: hash("e"), responseSha256: hash("f") })
      const resealedOutcome = makeDnrdOutcomeObservation({ traceId: resealed.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 0, scorerObservationSha256: hash("d") })
      if (Either.isLeft(resealedOutcome)) throw resealedOutcome.left
      const repeatedEpisodeResult = yield* Effect.either(adapter.applyOutcome(resealedOutcome.right, 100_000, 100_000))
      const creditedEpisodeIds = yield* adapter.creditedEpisodeIds
      const after = (yield* adapter.project(hash("a"))) as { readonly selection: { readonly routeId: string }; readonly status: string }
      const deranged = (yield* adapter.project(hash("a"), true)) as { readonly selection: { readonly routeId: string } }
      const recovered = (yield* adapter.recover) as { readonly payloadSha256: string; readonly stateRevision: number; readonly journalHead: { readonly sha256: string } }
      const snapshot = (yield* adapter.snapshot) as { readonly canonical: { readonly atoms: ReadonlyArray<{ readonly kind: string; readonly references: ReadonlyArray<{ readonly role: string }> }> } }
      return { before, after, deranged, forgedResult, repeatedTraceResult, repeatedEpisodeResult, creditedEpisodeIds, recovered, snapshot }
    }).pipe(Effect.provide(layer))
    const result = await Effect.runPromise(program as Effect.Effect<{ readonly before: { readonly selection: { readonly routeId: string } }; readonly after: { readonly selection: { readonly routeId: string }; readonly status: string }; readonly deranged: { readonly selection: { readonly routeId: string } }; readonly forgedResult: Either.Either<unknown, unknown>; readonly repeatedTraceResult: Either.Either<unknown, unknown>; readonly repeatedEpisodeResult: Either.Either<unknown, unknown>; readonly creditedEpisodeIds: ReadonlyArray<string>; readonly recovered: { readonly payloadSha256: string; readonly stateRevision: number; readonly journalHead: { readonly sha256: string } }; readonly snapshot: { readonly canonical: { readonly atoms: ReadonlyArray<{ readonly kind: string; readonly references: ReadonlyArray<{ readonly role: string }> }> } } }, unknown, never>)
    expect(result.before.selection.routeId).toBe("route:a")
    expect(result.after.selection.routeId).toBe("route:b")
    expect(result.deranged.selection.routeId).toBe("route:b")
    expect(result.after.status).toContain("NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING")
    expect(Either.isLeft(result.forgedResult)).toBe(true)
    expect(Either.isLeft(result.repeatedTraceResult)).toBe(true)
    expect(Either.isLeft(result.repeatedEpisodeResult)).toBe(true)
    expect(result.creditedEpisodeIds).toEqual(["episode:file"])
    expect(result.recovered.stateRevision).toBe(4)
    expect(result.recovered.payloadSha256).toHaveLength(64)
    expect(result.recovered.journalHead.sha256).toHaveLength(64)
    expect(result.snapshot.canonical.atoms.map((atom) => atom.kind).sort()).toEqual([
      "dnrd:credit", "dnrd:outcome", "dnrd:routing-disposition", "dnrd:routing-disposition", "dnrd:trajectory", "dnrd:trajectory"
    ])
    const byKind = (kind: string) => result.snapshot.canonical.atoms.filter((atom) => atom.kind === kind)
    expect(byKind("dnrd:outcome")[0]?.references.map((reference) => reference.role)).toEqual(["trajectory"])
    expect(byKind("dnrd:credit")[0]?.references.map((reference) => reference.role)).toEqual(["trajectory", "outcome"])
    expect(byKind("dnrd:routing-disposition").find((atom) => atom.references.length === 2)?.references.map((reference) => reference.role)).toEqual(["credit", "hswm:role:predecessor"])

    const applyReceipt = readdirSync(join(root, "journal-objects"))
      .map((name) => JSON.parse(readFileSync(join(root, "journal-objects", name), "utf8")) as { readonly receipt?: { readonly transitionId?: string; readonly provenanceSha256?: string } })
      .map((record) => record.receipt)
      .find((receipt) => receipt?.transitionId?.startsWith("dnrd:transition:2:dnrd:outcome:"))
    expect(applyReceipt?.provenanceSha256).toMatch(/^[0-9a-f]{64}$/)
    const provenanceBytes = readFileSync(join(root, "objects", applyReceipt!.provenanceSha256!))
    expect(createHash("sha256").update(provenanceBytes).digest("hex")).toBe(applyReceipt!.provenanceSha256)
    expect(JSON.parse(provenanceBytes.toString("utf8"))).toMatchObject({
      contract_version: "hswm-dnrd-local-transition-provenance/v1",
      clock_trust: "UNATTESTED_OS_CLOCK_ORDER_ESTABLISHED_BY_STATE_REVISION_ONLY",
      expected_state_revision: 2,
      writes: expect.any(Array)
    })

    const freshLayer = makeDnrdRoutingDiagnosticFileLayer(root) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
    const fresh = await Effect.runPromise(Effect.gen(function* () {
      const adapter = yield* DnrdRoutingDiagnosticFile
      return yield* adapter.recover
    }).pipe(Effect.provide(freshLayer)) as Effect.Effect<{ readonly stateRevision: number; readonly payload: DnrdRoutingPayload }, unknown, never>)
    expect(fresh.stateRevision).toBe(4)
    expect(fresh.payload.contexts[0]?.routes.find((route) => route.routeId === "route:b")?.scoreMicros).toBe(100_000)
  } finally { rmSync(root, { recursive: true, force: true }) }
})

it("DNRD file adapter refuses a noncanonical W0 payload before staging it", async () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-dnrd-file-invalid-"))
  try {
    const layer = makeDnrdRoutingDiagnosticFileLayer(root) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
    const result = await Effect.runPromise(Effect.gen(function* () {
      const adapter = yield* DnrdRoutingDiagnosticFile
      return yield* Effect.either(adapter.initialize({ ...payload(), contexts: [...payload().contexts].reverse() }))
    }).pipe(Effect.provide(layer)) as Effect.Effect<Either.Either<unknown, unknown>, unknown, never>)
    expect(Either.isLeft(result)).toBe(true)
  } finally { rmSync(root, { recursive: true, force: true }) }
})
