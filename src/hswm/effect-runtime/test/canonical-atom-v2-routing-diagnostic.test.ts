import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  DNRD_ROUTING_PAYLOAD_V1,
  applyDnrdCreditUpdate,
  derangeDnrdRoutingBindings,
  dnrdRouteDigest,
  dnrdRouteDigestForContext,
  dnrdScoreNorms,
  makeDnrdCanonicalSchemaV2,
  makeDnrdEligibilityTrace,
  makeDnrdOutcomeObservation,
  selectDnrdRoute,
  selectDnrdRoutes,
  validateDnrdRoutingPayload
} from "../src/canonical-atom-v2-routing-diagnostic.js"
import { validateHSWMCanonicalSchemaV2 } from "../src/canonical-atom-v2-domain.js"

const hash = (letter: string) => letter.repeat(64)
const payload = () => ({
  schemaVersion: DNRD_ROUTING_PAYLOAD_V1,
  contexts: [
    { contextSha256: hash("a"), stratum: "stratum:one", routes: [{ routeId: "route:a", scoreMicros: 100 }, { routeId: "route:b", scoreMicros: 50 }] },
    { contextSha256: hash("b"), stratum: "stratum:one", routes: [{ routeId: "route:a", scoreMicros: -100 }, { routeId: "route:b", scoreMicros: 50 }] },
    { contextSha256: hash("c"), stratum: "stratum:two", routes: [{ routeId: "route:a", scoreMicros: 20 }, { routeId: "route:b", scoreMicros: -20 }] },
    { contextSha256: hash("d"), stratum: "stratum:two", routes: [{ routeId: "route:a", scoreMicros: 10 }, { routeId: "route:b", scoreMicros: 10 }] }
  ],
  structuralStatus: "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const
})

it("DNRD routing uses strict ordering, lexical ties, deterministic digest, and exact norms", () => {
  const selected = selectDnrdRoutes(payload())
  const firstDigest = dnrdRouteDigest(payload())
  const secondDigest = dnrdRouteDigest(payload())
  const norms = dnrdScoreNorms(payload())
  const perContext = dnrdRouteDigestForContext(payload(), hash("a"))
  expect(Either.isRight(selected)).toBe(true)
  expect(Either.isRight(firstDigest)).toBe(true)
  expect(Either.isRight(secondDigest)).toBe(true)
  expect(Either.isRight(norms)).toBe(true)
  expect(Either.isRight(perContext)).toBe(true)
  if (Either.isRight(selected) && Either.isRight(firstDigest) && Either.isRight(secondDigest) && Either.isRight(norms) && Either.isRight(perContext)) {
    expect(selected.right.map(({ routeId }) => routeId)).toEqual(["route:a", "route:b", "route:a", "route:a"])
    expect(firstDigest.right).toEqual(secondDigest.right)
    expect(perContext.right).not.toEqual(firstDigest.right)
    expect(norms.right).toEqual({ l1Micros: 360, l2SquaredMicros: 26000 })
  }
})

it("DNRD rejects duplicate or noncanonical context and route order", () => {
  const unordered = payload()
  unordered.contexts.reverse()
  const duplicateRoute = payload()
  duplicateRoute.contexts[0]!.routes = [{ routeId: "route:a", scoreMicros: 1 }, { routeId: "route:a", scoreMicros: 2 }]
  expect(Either.isLeft(validateDnrdRoutingPayload(unordered))).toBe(true)
  expect(Either.isLeft(validateDnrdRoutingPayload(duplicateRoute))).toBe(true)
})

it("DNRD refuses to durably seal malformed episode or digest identifiers", () => {
  const valid = { payload: payload(), episodeId: "episode:valid", contextSha256: hash("a"), routeId: "route:a", requestSha256: hash("b"), responseSha256: hash("c") }
  expect(Either.isLeft(makeDnrdEligibilityTrace({ ...valid, episodeId: "bad episode" }))).toBe(true)
  expect(Either.isLeft(makeDnrdEligibilityTrace({ ...valid, requestSha256: "not-a-sha" }))).toBe(true)
  expect(Either.isLeft(makeDnrdEligibilityTrace({ ...valid, responseSha256: "f".repeat(63) }))).toBe(true)
})

it("DNRD seals an eligible route, clips its frozen credit update, and refuses outcome reuse", () => {
  const trace = makeDnrdEligibilityTrace({ payload: payload(), episodeId: "episode:one", contextSha256: hash("a"), routeId: "route:b", requestSha256: hash("e"), responseSha256: hash("f") })
  expect(Either.isRight(trace)).toBe(true)
  if (Either.isLeft(trace)) return
  const outcome = makeDnrdOutcomeObservation({
    traceId: trace.right.traceId,
    producerAddress: "principal:producer",
    scorerAddress: "principal:scorer",
    scorerProvenanceAddress: "repo:_research/dnrd/scorer.py",
    scorerSourceSha256: hash("e"),
    outcomeScoreMicros: 1_000_000, scorerObservationSha256: hash("a")
  })
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isLeft(outcome)) return
  const applied = applyDnrdCreditUpdate({
    payload: payload(), trace: trace.right, outcome: outcome.right,
    consumedOutcomeIds: [], learningRateMicros: 100_000, scoreLimitMicros: 100
  })
  expect(Either.isRight(applied)).toBe(true)
  if (Either.isRight(applied)) {
    expect(applied.right.payload.contexts[0]!.routes[0]!.scoreMicros).toEqual(100)
    expect(applied.right.payload.contexts[0]!.routes[1]!.scoreMicros).toEqual(100)
    expect(applied.right.payload.contexts[1]!).toEqual(payload().contexts[1]!)
    expect(applied.right.receipt.updatedRouteCount).toEqual(1)
    expect(applied.right.receipt.deltaMicros).toEqual(100_000)
    expect(Either.isLeft(applyDnrdCreditUpdate({
      payload: payload(), trace: trace.right, outcome: outcome.right,
      consumedOutcomeIds: [outcome.right.outcomeId], learningRateMicros: 1, scoreLimitMicros: 100
    }))).toBe(true)
    expect(Either.isLeft(applyDnrdCreditUpdate({
      payload: payload(), trace: trace.right, outcome: outcome.right,
      consumedOutcomeIds: [hash("b"), hash("b")], learningRateMicros: 1, scoreLimitMicros: 100
    }))).toBe(true)
  }
})

it("DNRD accepts only the frozen ±1,000,000 outcome scale and applies signed bounded updates", () => {
  const trace = makeDnrdEligibilityTrace({ payload: payload(), episodeId: "episode:negative", contextSha256: hash("a"), routeId: "route:b", requestSha256: hash("e"), responseSha256: hash("f") })
  if (Either.isLeft(trace)) return
  const negative = makeDnrdOutcomeObservation({ traceId: trace.right.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: -1_000_000, scorerObservationSha256: hash("a") })
  const zero = makeDnrdOutcomeObservation({ traceId: trace.right.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 0, scorerObservationSha256: hash("b") })
  expect(Either.isRight(negative)).toBe(true)
  expect(Either.isRight(zero)).toBe(true)
  expect(Either.isLeft(makeDnrdOutcomeObservation({ traceId: trace.right.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 1, scorerObservationSha256: hash("c") }))).toBe(true)
  if (Either.isRight(negative)) {
    const update = applyDnrdCreditUpdate({ payload: payload(), trace: trace.right, outcome: negative.right, consumedOutcomeIds: [], learningRateMicros: 100_000, scoreLimitMicros: 100_000 })
    expect(Either.isRight(update)).toBe(true)
    if (Either.isRight(update)) {
      expect(update.right.receipt.deltaMicros).toEqual(-100_000)
      expect(update.right.payload.contexts[0]!.routes[1]!.scoreMicros).toEqual(-99_950)
    }
  }
})

it("DNRD rejects same-principal outcomes and forged/unknown route traces", () => {
  const trace = makeDnrdEligibilityTrace({ payload: payload(), episodeId: "episode:two", contextSha256: hash("a"), routeId: "route:a", requestSha256: hash("e"), responseSha256: hash("f") })
  expect(Either.isRight(makeDnrdOutcomeObservation({ traceId: hash("a"), producerAddress: "principal:same", scorerAddress: "principal:same", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 1, scorerObservationSha256: hash("a") }))).toBe(false)
  if (Either.isLeft(trace)) return
  const outcome = makeDnrdOutcomeObservation({ traceId: trace.right.traceId, producerAddress: "principal:producer", scorerAddress: "principal:scorer", scorerProvenanceAddress: "repo:_research/dnrd/scorer.py", scorerSourceSha256: hash("e"), outcomeScoreMicros: 0, scorerObservationSha256: hash("a") })
  if (Either.isLeft(outcome)) return
  const forged = { ...trace.right, routeId: "route:unknown" }
  const applied = applyDnrdCreditUpdate({ payload: payload(), trace: forged, outcome: outcome.right, consumedOutcomeIds: [], learningRateMicros: 1, scoreLimitMicros: 100 })
  expect(Either.isLeft(applied)).toBe(true)
})

it("DNRD fixed-point-free derangement preserves score norms and fails closed for a one-context stratum", () => {
  const before = dnrdScoreNorms(payload())
  const deranged = derangeDnrdRoutingBindings(payload())
  expect(Either.isRight(before)).toBe(true)
  expect(Either.isRight(deranged)).toBe(true)
  if (Either.isRight(before) && Either.isRight(deranged)) {
    const after = dnrdScoreNorms(deranged.right)
    expect(Either.isRight(after)).toBe(true)
    if (Either.isRight(after)) expect(after.right).toEqual(before.right)
    expect(deranged.right.contexts[0]!.routes).toEqual(payload().contexts[1]!.routes)
  }
  const impossible = payload()
  impossible.contexts = impossible.contexts.slice(0, 3)
  expect(Either.isLeft(derangeDnrdRoutingBindings(impossible))).toBe(true)
  const unequalSupport = payload()
  unequalSupport.contexts[1]!.routes = [{ routeId: "route:a", scoreMicros: 1 }, { routeId: "route:c", scoreMicros: 2 }]
  expect(Either.isLeft(derangeDnrdRoutingBindings(unequalSupport))).toBe(true)
})

it("DNRD permits a W0 routing entity and records a forced non-argmax route without collateral updates", () => {
  const argmax = selectDnrdRoute(payload(), hash("a"))
  const forced = makeDnrdEligibilityTrace({ payload: payload(), episodeId: "episode:forced", contextSha256: hash("a"), routeId: "route:b", requestSha256: hash("e"), responseSha256: hash("f") })
  expect(Either.isRight(argmax)).toBe(true)
  expect(Either.isRight(forced)).toBe(true)
  if (Either.isRight(argmax) && Either.isRight(forced)) {
    expect(argmax.right.routeId).toEqual("route:a")
    expect(forced.right.routeId).toEqual("route:b")
    expect(forced.right.preOutcomeScoreMicros).toEqual(50)
  }
  const routing = makeDnrdCanonicalSchemaV2().kinds[3]!
  expect(routing.form).toEqual("ENTITY")
  expect(routing.minimumArity).toEqual(0)
  expect(routing.referenceContracts[0]!.roles[0]!.minimum).toEqual(0)
})

it("DNRD V2 fixture has one schema-allowed owner per kind and typed causal spine references", () => {
  const schema = makeDnrdCanonicalSchemaV2()
  const valid = validateHSWMCanonicalSchemaV2(schema)
  expect(Either.isRight(valid)).toBe(true)
  expect(schema.kinds.map((kind) => kind.allowedOwners.length)).toEqual([1, 1, 1, 1])
  expect(schema.kinds[3]!.referenceContracts.map(({ referenceType }) => referenceType)).toEqual(["dnrd:reference", "hswm:reference:supersedes"])
})
