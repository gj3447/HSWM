/**
 * Narrow, pure DNRD routing mechanics.
 *
 * This module is an experimental local structural diagnostic only. It neither
 * issues a canonical Permit nor establishes external-effect occurrence,
 * canonical admission, causal learning, or scientific efficacy.
 */
import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import {
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export const DNRD_ROUTING_PAYLOAD_V1 = "hswm-dnrd-routing-payload/v1" as const
export const DNRD_ELIGIBILITY_TRACE_V1 = "hswm-dnrd-eligibility-trace/v1" as const
export const DNRD_OUTCOME_OBSERVATION_V1 = "hswm-dnrd-outcome-observation/v1" as const
export const DNRD_CREDIT_RECEIPT_V1 = "hswm-dnrd-credit-receipt/v1" as const
/** Keeps 256*256 score squares strictly inside Number.MAX_SAFE_INTEGER. */
export const DNRD_SCORE_MICROS_LIMIT = 100_000
export const DNRD_OUTCOME_MICROS_SCALE = 1_000_000

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const SignedScoreMicros = Schema.Number.pipe(
  Schema.int(),
  Schema.between(-DNRD_SCORE_MICROS_LIMIT, DNRD_SCORE_MICROS_LIMIT)
)
const PositiveMicros = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, DNRD_SCORE_MICROS_LIMIT)
)
const OutcomeScoreMicros = Schema.Literal(-DNRD_OUTCOME_MICROS_SCALE, 0, DNRD_OUTCOME_MICROS_SCALE)

export interface DnrdRouteScore {
  readonly routeId: string
  readonly scoreMicros: number
}

export const DnrdRouteScoreSchema: Schema.Schema<DnrdRouteScore> = Schema.Struct({
  routeId: Identifier,
  scoreMicros: SignedScoreMicros
})

export interface DnrdRoutingContext {
  readonly contextSha256: string
  readonly stratum: string
  readonly routes: ReadonlyArray<DnrdRouteScore>
}

export const DnrdRoutingContextSchema: Schema.Schema<DnrdRoutingContext> = Schema.Struct({
  contextSha256: Sha256,
  stratum: Identifier,
  routes: Schema.Array(DnrdRouteScoreSchema).pipe(Schema.minItems(1), Schema.maxItems(256))
})

export interface DnrdRoutingPayload {
  readonly schemaVersion: typeof DNRD_ROUTING_PAYLOAD_V1
  readonly contexts: ReadonlyArray<DnrdRoutingContext>
  readonly structuralStatus: "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

export const DnrdRoutingPayloadSchema: Schema.Schema<DnrdRoutingPayload> = Schema.Struct({
  schemaVersion: Schema.Literal(DNRD_ROUTING_PAYLOAD_V1),
  contexts: Schema.Array(DnrdRoutingContextSchema).pipe(Schema.minItems(1), Schema.maxItems(256)),
  structuralStatus: Schema.Literal("LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING")
})

export interface DnrdRouteSelection {
  readonly contextSha256: string
  readonly stratum: string
  readonly routeId: string
  readonly scoreMicros: number
}

export interface DnrdEligibilityTrace {
  readonly schemaVersion: typeof DNRD_ELIGIBILITY_TRACE_V1
  readonly traceId: string
  readonly episodeId: string
  readonly routingPayloadSha256: string
  readonly contextSha256: string
  readonly stratum: string
  readonly routeId: string
  readonly preOutcomeScoreMicros: number
  readonly requestSha256: string
  readonly responseSha256: string
  readonly status: "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

export const DnrdEligibilityTraceSchema: Schema.Schema<DnrdEligibilityTrace> = Schema.Struct({
  schemaVersion: Schema.Literal(DNRD_ELIGIBILITY_TRACE_V1),
  traceId: Sha256,
  episodeId: Identifier,
  routingPayloadSha256: Sha256,
  contextSha256: Sha256,
  stratum: Identifier,
  routeId: Identifier,
  preOutcomeScoreMicros: SignedScoreMicros,
  requestSha256: Sha256,
  responseSha256: Sha256,
  status: Schema.Literal("SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING")
})

export interface DnrdOutcomeObservation {
  readonly schemaVersion: typeof DNRD_OUTCOME_OBSERVATION_V1
  readonly outcomeId: string
  readonly traceId: string
  readonly producerAddress: string
  readonly scorerAddress: string
  readonly scorerProvenanceAddress: string
  readonly scorerSourceSha256: string
  readonly outcomeScoreMicros: number
  readonly scorerObservationSha256: string
  readonly independence: "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
  readonly status: "LOCAL_EXPERIMENTAL_OUTCOME_NOT_EXTERNAL_TRUTH_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

export const DnrdOutcomeObservationSchema: Schema.Schema<DnrdOutcomeObservation> = Schema.Struct({
  schemaVersion: Schema.Literal(DNRD_OUTCOME_OBSERVATION_V1),
  outcomeId: Sha256,
  traceId: Sha256,
  producerAddress: Identifier,
  scorerAddress: Identifier,
  scorerProvenanceAddress: Identifier,
  scorerSourceSha256: Sha256,
  outcomeScoreMicros: OutcomeScoreMicros,
  scorerObservationSha256: Sha256,
  independence: Schema.Literal("DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"),
  status: Schema.Literal("LOCAL_EXPERIMENTAL_OUTCOME_NOT_EXTERNAL_TRUTH_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING")
})

export interface DnrdCreditUpdateInput {
  readonly payload: DnrdRoutingPayload
  readonly trace: DnrdEligibilityTrace
  readonly outcome: DnrdOutcomeObservation
  readonly consumedOutcomeIds: ReadonlyArray<string>
  readonly learningRateMicros: number
  readonly scoreLimitMicros: number
}

export const DnrdCreditUpdateInputSchema: Schema.Schema<DnrdCreditUpdateInput> = Schema.Struct({
  payload: DnrdRoutingPayloadSchema,
  trace: DnrdEligibilityTraceSchema,
  outcome: DnrdOutcomeObservationSchema,
  consumedOutcomeIds: Schema.Array(Sha256).pipe(Schema.maxItems(4096)),
  learningRateMicros: PositiveMicros,
  scoreLimitMicros: PositiveMicros
})

export interface DnrdCreditReceipt {
  readonly schemaVersion: typeof DNRD_CREDIT_RECEIPT_V1
  readonly outcomeId: string
  readonly traceId: string
  readonly beforePayloadSha256: string
  readonly afterPayloadSha256: string
  readonly deltaMicros: number
  readonly updatedRouteCount: number
  readonly consumedOutcomeIds: ReadonlyArray<string>
  readonly status: "LOCAL_EXPERIMENTAL_STRUCTURAL_CREDIT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

export class DnrdRoutingDiagnosticError extends Data.TaggedError("DnrdRoutingDiagnosticError")<{
  readonly code:
    | "PAYLOAD_INVALID"
    | "TRACE_INVALID"
    | "OUTCOME_INVALID"
    | "OUTCOME_REUSED"
    | "ROUTE_UNKNOWN"
    | "DERANGEMENT_IMPOSSIBLE"
  readonly detail: string
}> {}

const fail = (code: DnrdRoutingDiagnosticError["code"], detail: string) =>
  Either.left(new DnrdRoutingDiagnosticError({ code, detail }))
const releft = <A>(error: DnrdRoutingDiagnosticError): Either.Either<A, DnrdRoutingDiagnosticError> => Either.left(error)

const compareText = (left: string, right: string) => left < right ? -1 : left > right ? 1 : 0
const sortedUnique = <A>(values: ReadonlyArray<A>, key: (value: A) => string) =>
  values.every((value, index) => index === 0 || compareText(key(values[index - 1]!), key(value)) < 0)
const contextKey = (value: DnrdRoutingContext) => `${value.stratum}\u0000${value.contextSha256}`
const routeKey = (value: DnrdRouteScore) => value.routeId
const sha256 = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")

const exactBytes = (value: unknown): Either.Either<Uint8Array, DnrdRoutingDiagnosticError> => {
  const bytes = canonicalJsonBytes(value)
  return Either.isLeft(bytes)
    ? fail("PAYLOAD_INVALID", "value cannot be represented by canonical JSON/v1")
    : Either.right(Uint8Array.from(bytes.right))
}

export const validateDnrdRoutingPayload = (input: unknown): Either.Either<DnrdRoutingPayload, DnrdRoutingDiagnosticError> => {
  const decoded = Schema.decodeUnknownEither(DnrdRoutingPayloadSchema, { onExcessProperty: "error" })(input)
  if (Either.isLeft(decoded)) return fail("PAYLOAD_INVALID", "payload violates the strict DNRD routing schema")
  const payload = decoded.right
  if (!sortedUnique(payload.contexts, contextKey)) {
    return fail("PAYLOAD_INVALID", "contexts must be strictly sorted and unique by stratum then context SHA-256")
  }
  if (payload.contexts.some((context) => !sortedUnique(context.routes, routeKey))) {
    return fail("PAYLOAD_INVALID", "routes must be strictly sorted and unique by route id")
  }
  return Either.right(payload)
}

export const dnrdRoutingPayloadBytes = (input: unknown): Either.Either<Uint8Array, DnrdRoutingDiagnosticError> => {
  const payload = validateDnrdRoutingPayload(input)
  return Either.isLeft(payload) ? releft(payload.left) : exactBytes(payload.right)
}

export const dnrdRoutingPayloadSha256 = (input: unknown): Either.Either<string, DnrdRoutingDiagnosticError> => {
  const bytes = dnrdRoutingPayloadBytes(input)
  return Either.isLeft(bytes) ? releft(bytes.left) : Either.right(sha256(bytes.right))
}

export const selectDnrdRoutes = (input: unknown): Either.Either<ReadonlyArray<DnrdRouteSelection>, DnrdRoutingDiagnosticError> => {
  const payload = validateDnrdRoutingPayload(input)
  if (Either.isLeft(payload)) return releft(payload.left)
  return Either.right(Object.freeze(payload.right.contexts.map((context) => {
    const selected = [...context.routes].sort((left, right) =>
      right.scoreMicros - left.scoreMicros || compareText(left.routeId, right.routeId)
    )[0]!
    return Object.freeze({ contextSha256: context.contextSha256, stratum: context.stratum, routeId: selected.routeId, scoreMicros: selected.scoreMicros })
  })))
}

/** Deterministic argmax readout; an episode trace may instead record a forced valid route. */
export const selectDnrdRoute = (input: unknown, contextSha256: string): Either.Either<DnrdRouteSelection, DnrdRoutingDiagnosticError> => {
  const payload = validateDnrdRoutingPayload(input)
  if (Either.isLeft(payload)) return releft(payload.left)
  const context = payload.right.contexts.find((candidate) => candidate.contextSha256 === contextSha256)
  if (context === undefined) return fail("ROUTE_UNKNOWN", "context SHA-256 is absent from the routing payload")
  const selected = [...context.routes].sort((left, right) => right.scoreMicros - left.scoreMicros || compareText(left.routeId, right.routeId))[0]!
  return Either.right(Object.freeze({ contextSha256: context.contextSha256, stratum: context.stratum, routeId: selected.routeId, scoreMicros: selected.scoreMicros }))
}

export const dnrdRouteDigest = (input: unknown): Either.Either<string, DnrdRoutingDiagnosticError> => {
  const selections = selectDnrdRoutes(input)
  if (Either.isLeft(selections)) return releft(selections.left)
  const bytes = exactBytes(selections.right)
  return Either.isLeft(bytes) ? releft(bytes.left) : Either.right(sha256(bytes.right))
}

export const dnrdRouteDigestForContext = (input: unknown, contextSha256: string): Either.Either<string, DnrdRoutingDiagnosticError> => {
  const selection = selectDnrdRoute(input, contextSha256)
  if (Either.isLeft(selection)) return releft(selection.left)
  const bytes = exactBytes(selection.right)
  return Either.isLeft(bytes) ? releft(bytes.left) : Either.right(sha256(bytes.right))
}

export const dnrdScoreNorms = (input: unknown): Either.Either<Readonly<{ l1Micros: number; l2SquaredMicros: number }>, DnrdRoutingDiagnosticError> => {
  const payload = validateDnrdRoutingPayload(input)
  if (Either.isLeft(payload)) return releft(payload.left)
  let l1Micros = 0
  let l2SquaredMicros = 0
  for (const context of payload.right.contexts) for (const route of context.routes) {
    l1Micros += Math.abs(route.scoreMicros)
    l2SquaredMicros += route.scoreMicros * route.scoreMicros
    if (!Number.isSafeInteger(l1Micros) || !Number.isSafeInteger(l2SquaredMicros)) return fail("PAYLOAD_INVALID", "routing score norm exceeds exact safe-integer accounting")
  }
  return Either.right(Object.freeze({ l1Micros, l2SquaredMicros }))
}

export const makeDnrdEligibilityTrace = (input: { readonly payload: unknown; readonly episodeId: string; readonly contextSha256: string; readonly routeId: string; readonly requestSha256: string; readonly responseSha256: string }): Either.Either<DnrdEligibilityTrace, DnrdRoutingDiagnosticError> => {
  const payload = validateDnrdRoutingPayload(input.payload)
  if (Either.isLeft(payload)) return releft(payload.left)
  const routingPayloadSha256 = dnrdRoutingPayloadSha256(payload.right)
  const context = payload.right.contexts.find((candidate) => candidate.contextSha256 === input.contextSha256)
  if (Either.isLeft(routingPayloadSha256)) return releft(routingPayloadSha256.left)
  if (context === undefined) return fail("ROUTE_UNKNOWN", "episode trace context is absent from the routing payload")
  const route = context.routes.find((candidate) => candidate.routeId === input.routeId)
  if (route === undefined) return fail("ROUTE_UNKNOWN", "episode trace route is absent from the selected context")
  const unsigned = { schemaVersion: DNRD_ELIGIBILITY_TRACE_V1, episodeId: input.episodeId, routingPayloadSha256: routingPayloadSha256.right, contextSha256: context.contextSha256, stratum: context.stratum, routeId: route.routeId, preOutcomeScoreMicros: route.scoreMicros, requestSha256: input.requestSha256, responseSha256: input.responseSha256, status: "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const }
  const bytes = exactBytes(unsigned)
  if (Either.isLeft(bytes)) return releft(bytes.left)
  const candidate = { ...unsigned, traceId: sha256(bytes.right) }
  const checked = Schema.decodeUnknownEither(DnrdEligibilityTraceSchema, { onExcessProperty: "error" })(candidate)
  return Either.isLeft(checked)
    ? fail("TRACE_INVALID", "trace inputs violate the strict DNRD eligibility schema")
    : Either.right(Object.freeze(checked.right))
}

export const validateDnrdEligibilityTrace = (input: unknown): Either.Either<DnrdEligibilityTrace, DnrdRoutingDiagnosticError> => {
  const decoded = Schema.decodeUnknownEither(DnrdEligibilityTraceSchema, { onExcessProperty: "error" })(input)
  if (Either.isLeft(decoded)) return fail("TRACE_INVALID", "trace violates the strict DNRD schema")
  const trace = decoded.right
  const bytes = exactBytes({ schemaVersion: trace.schemaVersion, episodeId: trace.episodeId, routingPayloadSha256: trace.routingPayloadSha256, contextSha256: trace.contextSha256, stratum: trace.stratum, routeId: trace.routeId, preOutcomeScoreMicros: trace.preOutcomeScoreMicros, requestSha256: trace.requestSha256, responseSha256: trace.responseSha256, status: trace.status })
  if (Either.isLeft(bytes) || trace.traceId !== sha256(bytes.right)) return fail("TRACE_INVALID", "trace id does not bind its exact canonical pre-outcome contents")
  return Either.right(trace)
}

export const makeDnrdOutcomeObservation = (input: Omit<DnrdOutcomeObservation, "schemaVersion" | "outcomeId" | "independence" | "status">): Either.Either<DnrdOutcomeObservation, DnrdRoutingDiagnosticError> => {
  if (input.producerAddress === input.scorerAddress) return fail("OUTCOME_INVALID", "outcome scorer must be declared-role-separated from the producer")
  const unsigned = { schemaVersion: DNRD_OUTCOME_OBSERVATION_V1, traceId: input.traceId, producerAddress: input.producerAddress, scorerAddress: input.scorerAddress, scorerProvenanceAddress: input.scorerProvenanceAddress, scorerSourceSha256: input.scorerSourceSha256, outcomeScoreMicros: input.outcomeScoreMicros, scorerObservationSha256: input.scorerObservationSha256, independence: "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN" as const, status: "LOCAL_EXPERIMENTAL_OUTCOME_NOT_EXTERNAL_TRUTH_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const }
  const bytes = exactBytes(unsigned)
  if (Either.isLeft(bytes)) return releft(bytes.left)
  const outcome = { ...unsigned, outcomeId: sha256(bytes.right) }
  const checked = Schema.decodeUnknownEither(DnrdOutcomeObservationSchema, { onExcessProperty: "error" })(outcome)
  return Either.isLeft(checked) ? fail("OUTCOME_INVALID", "outcome violates the strict DNRD outcome schema") : Either.right(Object.freeze(checked.right))
}

export const validateDnrdOutcomeObservation = (input: unknown): Either.Either<DnrdOutcomeObservation, DnrdRoutingDiagnosticError> => {
  const decoded = Schema.decodeUnknownEither(DnrdOutcomeObservationSchema, { onExcessProperty: "error" })(input)
  if (Either.isLeft(decoded)) return fail("OUTCOME_INVALID", "outcome violates the strict DNRD outcome schema")
  const outcome = decoded.right
  if (outcome.producerAddress === outcome.scorerAddress) return fail("OUTCOME_INVALID", "outcome scorer must be declared-role-separated from the producer")
  const bytes = exactBytes({ schemaVersion: outcome.schemaVersion, traceId: outcome.traceId, producerAddress: outcome.producerAddress, scorerAddress: outcome.scorerAddress, scorerProvenanceAddress: outcome.scorerProvenanceAddress, scorerSourceSha256: outcome.scorerSourceSha256, outcomeScoreMicros: outcome.outcomeScoreMicros, scorerObservationSha256: outcome.scorerObservationSha256, independence: outcome.independence, status: outcome.status })
  if (Either.isLeft(bytes) || outcome.outcomeId !== sha256(bytes.right)) return fail("OUTCOME_INVALID", "outcome id does not bind its exact canonical declared-role-separated contents")
  return Either.right(outcome)
}

export const applyDnrdCreditUpdate = (input: unknown): Either.Either<Readonly<{ payload: DnrdRoutingPayload; receipt: DnrdCreditReceipt }>, DnrdRoutingDiagnosticError> => {
  const decoded = Schema.decodeUnknownEither(DnrdCreditUpdateInputSchema, { onExcessProperty: "error" })(input)
  if (Either.isLeft(decoded)) return fail("PAYLOAD_INVALID", "credit input violates the strict DNRD schema")
  const value = decoded.right
  const payload = validateDnrdRoutingPayload(value.payload)
  if (Either.isLeft(payload)) return releft(payload.left)
  const trace = validateDnrdEligibilityTrace(value.trace)
  const outcome = validateDnrdOutcomeObservation(value.outcome)
  if (Either.isLeft(trace)) return releft(trace.left)
  if (Either.isLeft(outcome)) return releft(outcome.left)
  if (!sortedUnique(value.consumedOutcomeIds, (outcomeId) => outcomeId)) return fail("OUTCOME_REUSED", "consumed outcome ids must be strictly sorted and unique")
  if (value.consumedOutcomeIds.includes(outcome.right.outcomeId)) return fail("OUTCOME_REUSED", "one outcome id may produce at most one local experimental revision")
  const expectedPayloadSha256 = dnrdRoutingPayloadSha256(payload.right)
  if (Either.isLeft(expectedPayloadSha256) || trace.right.routingPayloadSha256 !== expectedPayloadSha256.right) {
    return fail("TRACE_INVALID", "credit requires the exact sealed eligibility trace for the supplied payload")
  }
  if (outcome.right.traceId !== trace.right.traceId) return fail("OUTCOME_INVALID", "outcome does not bind the sealed eligibility trace")
  if (value.scoreLimitMicros > DNRD_SCORE_MICROS_LIMIT) return fail("PAYLOAD_INVALID", "score limit exceeds the frozen DNRD maximum")
  const deltaMicros = Math.trunc((outcome.right.outcomeScoreMicros * value.learningRateMicros) / DNRD_OUTCOME_MICROS_SCALE)
  const traceContext = payload.right.contexts.find((context) => context.contextSha256 === trace.right.contextSha256 && context.stratum === trace.right.stratum)
  const traceRoute = traceContext?.routes.find((route) => route.routeId === trace.right.routeId)
  if (traceContext === undefined || traceRoute === undefined || traceRoute.scoreMicros !== trace.right.preOutcomeScoreMicros) return fail("ROUTE_UNKNOWN", "sealed trace does not name one current payload route with its pre-outcome score")
  const contexts: DnrdRoutingContext[] = []
  let updatedRouteCount = 0
  for (const context of payload.right.contexts) {
    const routeId = context === traceContext ? trace.right.routeId : null
    let sawRoute = false
    const routes = context.routes.map((route) => {
      if (routeId === null || route.routeId !== routeId) return route
      sawRoute = true
      updatedRouteCount += 1
      return Object.freeze({ routeId: route.routeId, scoreMicros: Math.max(-value.scoreLimitMicros, Math.min(value.scoreLimitMicros, route.scoreMicros + deltaMicros)) })
    })
    if (context === traceContext && !sawRoute) return fail("ROUTE_UNKNOWN", "sealed trace selects a route absent from the payload")
    contexts.push(Object.freeze({ ...context, routes: Object.freeze(routes) }))
  }
  const next: DnrdRoutingPayload = Object.freeze({ ...payload.right, contexts: Object.freeze(contexts) })
  const beforePayloadSha256 = dnrdRoutingPayloadSha256(payload.right)
  const afterPayloadSha256 = dnrdRoutingPayloadSha256(next)
  if (Either.isLeft(beforePayloadSha256) || Either.isLeft(afterPayloadSha256)) return fail("PAYLOAD_INVALID", "updated payload cannot be canonically hashed")
  const receipt = Object.freeze({ schemaVersion: DNRD_CREDIT_RECEIPT_V1, outcomeId: outcome.right.outcomeId, traceId: trace.right.traceId, beforePayloadSha256: beforePayloadSha256.right, afterPayloadSha256: afterPayloadSha256.right, deltaMicros, updatedRouteCount, consumedOutcomeIds: Object.freeze([...value.consumedOutcomeIds, outcome.right.outcomeId].sort(compareText)), status: "LOCAL_EXPERIMENTAL_STRUCTURAL_CREDIT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const })
  return Either.right(Object.freeze({ payload: next, receipt }))
}

export const derangeDnrdRoutingBindings = (input: unknown): Either.Either<DnrdRoutingPayload, DnrdRoutingDiagnosticError> => {
  const payload = validateDnrdRoutingPayload(input)
  if (Either.isLeft(payload)) return releft(payload.left)
  const byStratum = new Map<string, DnrdRoutingContext[]>()
  for (const context of payload.right.contexts) byStratum.set(context.stratum, [...(byStratum.get(context.stratum) ?? []), context])
  const contexts: DnrdRoutingContext[] = []
  for (const [stratum, group] of [...byStratum.entries()].sort(([left], [right]) => compareText(left, right))) {
    if (group.length < 2) return fail("DERANGEMENT_IMPOSSIBLE", `stratum ${stratum} has fewer than two context bindings`)
    const support = group[0]!.routes.map(({ routeId }) => routeId)
    if (group.some((context) => context.routes.length !== support.length || context.routes.some((route, index) => route.routeId !== support[index]))) return fail("DERANGEMENT_IMPOSSIBLE", `stratum ${stratum} does not have equal route-ID support`)
    for (let index = 0; index < group.length; index += 1) {
      const receiver = group[index]!
      const donor = group[(index + 1) % group.length]!
      contexts.push(Object.freeze({ ...receiver, routes: Object.freeze(donor.routes.map((route) => Object.freeze({ ...route }))) }))
    }
  }
  const deranged: DnrdRoutingPayload = Object.freeze({ ...payload.right, contexts: Object.freeze(contexts.sort((left, right) => compareText(contextKey(left), contextKey(right)))) })
  const before = dnrdScoreNorms(payload.right)
  const after = dnrdScoreNorms(deranged)
  if (Either.isLeft(before) || Either.isLeft(after) || before.right.l1Micros !== after.right.l1Micros || before.right.l2SquaredMicros !== after.right.l2SquaredMicros) return fail("PAYLOAD_INVALID", "derangement drifted the exact score norms")
  return Either.right(deranged)
}

export const makeDnrdCanonicalSchemaV2 = (): HSWMCanonicalSchemaV2 => Object.freeze({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: "hswm-canonical-schema-contract/v2",
  schemaVersion: "hswm:dnrd:v1",
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "DNRD is local experimental structural validity only; it is not canonical Permit, admission, learning, or scientific efficacy.",
  owners: [
    { address: "owner:dnrd:trajectory", obligation: "Own local experimental trajectory records." },
    { address: "owner:dnrd:outcome", obligation: "Own local experimental declared-role-separated outcome records." },
    { address: "owner:dnrd:credit", obligation: "Own local experimental frozen credit records." },
    { address: "owner:dnrd:routing", obligation: "Own local experimental routing disposition revisions." }
  ],
  kinds: [
    { kind: "dnrd:trajectory", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: ["owner:dnrd:trajectory"], minimumArity: 0, referenceContracts: [] },
    { kind: "dnrd:outcome", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:dnrd:outcome"], minimumArity: 1, referenceContracts: [{ referenceType: "dnrd:reference", roles: [{ role: "trajectory", targetKinds: ["dnrd:trajectory"], minimum: 1, maximum: 1 }] }] },
    { kind: "dnrd:credit", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:dnrd:credit"], minimumArity: 2, referenceContracts: [{ referenceType: "dnrd:reference", roles: [{ role: "trajectory", targetKinds: ["dnrd:trajectory"], minimum: 1, maximum: 1 }, { role: "outcome", targetKinds: ["dnrd:outcome"], minimum: 1, maximum: 1 }] }] },
    // W0 is an entity with no credit. The experiment adapter, not this generic
    // schema, must require exactly one credit reference for every successor.
    { kind: "dnrd:routing-disposition", form: "ENTITY", revisionPolicy: "LINEAR", allowedOwners: ["owner:dnrd:routing"], minimumArity: 0, referenceContracts: [{ referenceType: "dnrd:reference", roles: [{ role: "credit", targetKinds: ["dnrd:credit"], minimum: 0, maximum: 1 }] }, { referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, roles: [{ role: HSWM_SUPERSEDES_REFERENCE_ROLE, targetKinds: ["dnrd:routing-disposition"], minimum: 0, maximum: 1 }] }] }
  ]
} satisfies HSWMCanonicalSchemaV2)
