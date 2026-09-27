/**
 * Finite v1 domain for a declared cross-layer map. This is deliberately a
 * bounded experiment contract: it does not make a canonical write, execute an
 * LLM, or claim that a map is causal merely because it decodes.
 */
import { Either } from "effect"
import { createHash } from "node:crypto"

export type ToyBit = 0 | 1
export type ToyAction = "wait" | "pulse" | "block" | "unblock"
export type ToyField = "r" | "h"
export type ToyState = Readonly<{ readonly r: ToyBit; readonly h: ToyBit }>
export type ToyMappingKind = "preserve_r_h" | "drop_refractory"
export type ToyMappedState = Readonly<{ readonly r: ToyBit; readonly h: ToyBit }> | Readonly<{ readonly h: ToyBit }>
export type MappingMethod = "authored_deterministic" | "learned_encoder" | "llm_proposed"

export interface ModelRef {
  readonly modelRef: string
  readonly digest: string
}

export interface MapSpec {
  readonly schema: "hswm-cross-layer-map/v1"
  readonly source: ModelRef
  readonly target: ModelRef
  readonly mappingKind: ToyMappingKind
  readonly mappingMethod: MappingMethod
  readonly declaredLosses: readonly string[]
  readonly actionAllowlist: readonly ToyAction[]
  readonly time: Readonly<{ readonly unit: "tick"; readonly horizon: 1 }>
  readonly supportScope: Readonly<{
    readonly world: "finite-toy-rh/v1"
    readonly contexts: readonly string[]
    readonly observableFields: readonly ToyField[]
  }>
}

export interface CrossLayerInputPacket {
  readonly subject: Readonly<{
    readonly observation: Readonly<Partial<ToyState>>
    readonly asOf: number
    readonly requested: Readonly<{ readonly action: ToyAction; readonly horizon: 1; readonly window: Readonly<{ readonly start: number; readonly end: number }> }>
  }>
  readonly context: MapSpec
  readonly evidence: readonly Readonly<{ readonly sourceRef: string; readonly digest: string; readonly observedAt: number }>[]
  readonly eventTime: number
}

export interface CrossLayerMapDecodeError {
  readonly code: "INVALID_SHAPE" | "UNKNOWN_FIELD" | "INVALID_VALUE" | "ACTION_OUTSIDE_ALLOWLIST" | "TIME_ORDER" | "FUTURE_EVIDENCE"
  readonly path: string
  readonly detail: string
}

export type MappingResult<T> =
  | Readonly<{ readonly kind: "mapped"; readonly value: T; readonly lossRefs: readonly string[] }>
  | Readonly<{ readonly kind: "needs_observation"; readonly missing: readonly ToyField[] }>
  | Readonly<{ readonly kind: "outside_domain"; readonly reason: string }>

export interface ToyComparisonRow {
  readonly state: ToyState
  readonly action: ToyAction
  readonly preserveStateCommutes: boolean
  readonly preserveFireCommutes: boolean
  readonly lossyStateCommutes: boolean
  /** A particular readout is not chosen: q(h) admits contradictory fire values. */
  readonly lossyFireReadoutPossible: boolean
}

export interface ToyComparisonSummary {
  readonly rows: readonly ToyComparisonRow[]
  readonly totalRows: 16
  readonly preserve: Readonly<{ readonly stateCommutingRows: number; readonly fireCommutingRows: number }>
  readonly dropRefractory: Readonly<{
    readonly stateCommutingRows: number
    /** Rows whose whole q-fiber has one fire value; this is not prediction accuracy. */
    readonly unambiguousReadoutRows: number
    readonly conflictingReadoutClasses: readonly Readonly<{ readonly mappedState: Readonly<{ readonly h: ToyBit }>; readonly action: ToyAction; readonly fireValues: readonly ToyBit[] }>[]
  }>
}

const freeze = <T>(value: T): Readonly<T> => Object.freeze(value)
const bit = (value: unknown): value is ToyBit => value === 0 || value === 1
const actions = freeze(["wait", "pulse", "block", "unblock"] as const)
const fields = freeze(["r", "h"] as const)
const digest = /^[a-f0-9]{64}$/u
const nonEmpty = (value: unknown, maximum = 256): value is string => typeof value === "string" && value.length > 0 && value.length <= maximum
const exactKeys = (value: unknown, path: string, expected: readonly string[]): Either.Either<Readonly<Record<string, unknown>>, CrossLayerMapDecodeError> => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return fail("INVALID_SHAPE", path, "must be an object")
  const record = value as Readonly<Record<string, unknown>>
  for (const key of Object.keys(record)) if (!expected.includes(key)) return fail("UNKNOWN_FIELD", `${path}.${key}`, "is not allowed")
  for (const key of expected) if (!(key in record)) return fail("INVALID_SHAPE", `${path}.${key}`, "is required")
  return Either.right(record)
}
const fail = <A = never>(code: CrossLayerMapDecodeError["code"], path: string, detail: string): Either.Either<A, CrossLayerMapDecodeError> => Either.left(freeze({ code, path, detail }))
const retype = <A>(value: { readonly left: CrossLayerMapDecodeError }): Either.Either<A, CrossLayerMapDecodeError> => Either.left(value.left)
const number = (value: unknown, path: string): Either.Either<number, CrossLayerMapDecodeError> => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? Either.right(value) : fail("INVALID_VALUE", path, "must be a non-negative safe integer")
const uniqueStrings = (value: unknown, path: string, maximum: number): Either.Either<readonly string[], CrossLayerMapDecodeError> => {
  if (!Array.isArray(value) || value.length > maximum || !value.every(entry => nonEmpty(entry))) return fail("INVALID_VALUE", path, "must be a bounded string array")
  return new Set(value).size === value.length ? Either.right(freeze([...value])) : fail("INVALID_VALUE", path, "must not repeat entries")
}
const modelRef = (value: unknown, path: string): Either.Either<ModelRef, CrossLayerMapDecodeError> => {
  const object = exactKeys(value, path, ["modelRef", "digest"]); if (Either.isLeft(object)) return retype(object)
  return nonEmpty(object.right["modelRef"]) && typeof object.right["digest"] === "string" && digest.test(object.right["digest"])
    ? Either.right(freeze({ modelRef: object.right["modelRef"], digest: object.right["digest"] }))
    : fail("INVALID_VALUE", path, "requires bounded modelRef and lowercase sha256 digest")
}
const allowedActions = (value: unknown, path: string): Either.Either<readonly ToyAction[], CrossLayerMapDecodeError> => {
  if (!Array.isArray(value) || value.length === 0 || value.length > actions.length || !value.every((entry): entry is ToyAction => actions.includes(entry as ToyAction)) || new Set(value).size !== value.length) return fail("INVALID_VALUE", path, "must be a non-empty unique ToyAction array")
  return Either.right(freeze([...value]))
}
const allowedFields = (value: unknown, path: string): Either.Either<readonly ToyField[], CrossLayerMapDecodeError> => {
  if (!Array.isArray(value) || value.length === 0 || value.length > fields.length || !value.every((entry): entry is ToyField => fields.includes(entry as ToyField)) || new Set(value).size !== value.length) return fail("INVALID_VALUE", path, "must be a non-empty unique ToyField array")
  return Either.right(freeze([...value]))
}

/** Strict decoder: unrecognized target/outcome/prediction/future fields fail as unknown fields. */
export const decodeMapSpec = (value: unknown): Either.Either<MapSpec, CrossLayerMapDecodeError> => {
  const root = exactKeys(value, "$", ["schema", "source", "target", "mappingKind", "mappingMethod", "declaredLosses", "actionAllowlist", "time", "supportScope"]); if (Either.isLeft(root)) return retype(root)
  if (root.right["schema"] !== "hswm-cross-layer-map/v1") return fail("INVALID_VALUE", "$.schema", "must be hswm-cross-layer-map/v1")
  if (root.right["mappingMethod"] !== "authored_deterministic" && root.right["mappingMethod"] !== "learned_encoder" && root.right["mappingMethod"] !== "llm_proposed") return fail("INVALID_VALUE", "$.mappingMethod", "is unsupported")
  if (root.right["mappingKind"] !== "preserve_r_h" && root.right["mappingKind"] !== "drop_refractory") return fail("INVALID_VALUE", "$.mappingKind", "is unsupported")
  const source = modelRef(root.right["source"], "$.source"), target = modelRef(root.right["target"], "$.target"), losses = uniqueStrings(root.right["declaredLosses"], "$.declaredLosses", 16), actionAllowlist = allowedActions(root.right["actionAllowlist"], "$.actionAllowlist")
  if (Either.isLeft(source)) return retype(source); if (Either.isLeft(target)) return retype(target); if (Either.isLeft(losses)) return retype(losses); if (Either.isLeft(actionAllowlist)) return retype(actionAllowlist)
  const time = exactKeys(root.right["time"], "$.time", ["unit", "horizon"]); if (Either.isLeft(time)) return retype(time)
  if (time.right["unit"] !== "tick" || time.right["horizon"] !== 1) return fail("INVALID_VALUE", "$.time", "v1 supports tick horizon 1 only")
  const scope = exactKeys(root.right["supportScope"], "$.supportScope", ["world", "contexts", "observableFields"]); if (Either.isLeft(scope)) return retype(scope)
  const contexts = uniqueStrings(scope.right["contexts"], "$.supportScope.contexts", 16), observableFields = allowedFields(scope.right["observableFields"], "$.supportScope.observableFields")
  if (Either.isLeft(contexts)) return retype(contexts); if (Either.isLeft(observableFields)) return retype(observableFields)
  if (scope.right["world"] !== "finite-toy-rh/v1") return fail("INVALID_VALUE", "$.supportScope.world", "v1 supports finite-toy-rh/v1 only")
  if (root.right["mappingKind"] === "preserve_r_h" && (losses.right.length !== 0 || observableFields.right.length !== 2)) return fail("INVALID_VALUE", "$.declaredLosses", "preserve_r_h has no declared loss and requires r,h observations")
  if (root.right["mappingKind"] === "drop_refractory" && (!losses.right.includes("refractory-state-r") || observableFields.right.length !== 1 || observableFields.right[0] !== "h")) return fail("INVALID_VALUE", "$.supportScope", "drop_refractory must declare refractory-state-r and expose h only")
  return Either.right(freeze({ schema: "hswm-cross-layer-map/v1", source: source.right, target: target.right, mappingKind: root.right["mappingKind"], mappingMethod: root.right["mappingMethod"], declaredLosses: losses.right, actionAllowlist: actionAllowlist.right, time: freeze({ unit: "tick", horizon: 1 }), supportScope: freeze({ world: "finite-toy-rh/v1", contexts: contexts.right, observableFields: observableFields.right }) }))
}

export const decodeCrossLayerInputPacket = (value: unknown): Either.Either<CrossLayerInputPacket, CrossLayerMapDecodeError> => {
  const root = exactKeys(value, "$", ["subject", "context", "evidence", "eventTime"]); if (Either.isLeft(root)) return retype(root)
  const context = decodeMapSpec(root.right["context"]); if (Either.isLeft(context)) return retype(context)
  const eventTime = number(root.right["eventTime"], "$.eventTime"); if (Either.isLeft(eventTime)) return retype(eventTime)
  const subject = exactKeys(root.right["subject"], "$.subject", ["observation", "asOf", "requested"]); if (Either.isLeft(subject)) return retype(subject)
  if (subject.right["observation"] === null || typeof subject.right["observation"] !== "object" || Array.isArray(subject.right["observation"])) return fail("INVALID_SHAPE", "$.subject.observation", "must be an object")
  const observationRecord = subject.right["observation"] as Readonly<Record<string, unknown>>
  if (Object.keys(observationRecord).some(key => !fields.includes(key as ToyField))) return fail("UNKNOWN_FIELD", "$.subject.observation", "only r and h are allowed")
  if (Object.keys(observationRecord).length === 0 || Object.keys(observationRecord).some(key => !bit(observationRecord[key]))) return fail("INVALID_VALUE", "$.subject.observation", "requires at least one bit observation")
  if (Object.keys(observationRecord).some(key => !context.right.supportScope.observableFields.includes(key as ToyField))) return fail("INVALID_VALUE", "$.subject.observation", "contains a field outside context supportScope.observableFields")
  const asOf = number(subject.right["asOf"], "$.subject.asOf"); if (Either.isLeft(asOf)) return retype(asOf)
  if (asOf.right > eventTime.right) return fail("TIME_ORDER", "$.subject.asOf", "must not be after eventTime")
  const requested = exactKeys(subject.right["requested"], "$.subject.requested", ["action", "horizon", "window"]); if (Either.isLeft(requested)) return retype(requested)
  if (!actions.includes(requested.right["action"] as ToyAction) || requested.right["horizon"] !== 1) return fail("INVALID_VALUE", "$.subject.requested", "requires a ToyAction and horizon 1")
  const window = exactKeys(requested.right["window"], "$.subject.requested.window", ["start", "end"]); if (Either.isLeft(window)) return retype(window)
  const start = number(window.right["start"], "$.subject.requested.window.start"), end = number(window.right["end"], "$.subject.requested.window.end")
  if (Either.isLeft(start)) return retype(start); if (Either.isLeft(end)) return retype(end)
  if (start.right < eventTime.right || end.right - start.right !== 1) return fail("TIME_ORDER", "$.subject.requested.window", "must be a future one-tick request window")
  if (!context.right.actionAllowlist.includes(requested.right["action"] as ToyAction)) return fail("ACTION_OUTSIDE_ALLOWLIST", "$.subject.requested.action", "is outside context actionAllowlist")
  const evidence = root.right["evidence"]
  if (!Array.isArray(evidence) || evidence.length > 32) return fail("INVALID_VALUE", "$.evidence", "must be a bounded array")
  const decodedEvidence: { sourceRef: string; digest: string; observedAt: number }[] = []
  for (let index = 0; index < evidence.length; index += 1) {
    const item = exactKeys(evidence[index], `$.evidence[${index}]`, ["sourceRef", "digest", "observedAt"]); if (Either.isLeft(item)) return retype(item)
    const observedAt = number(item.right["observedAt"], `$.evidence[${index}].observedAt`); if (Either.isLeft(observedAt)) return retype(observedAt)
    if (!nonEmpty(item.right["sourceRef"]) || typeof item.right["digest"] !== "string" || !digest.test(item.right["digest"])) return fail("INVALID_VALUE", `$.evidence[${index}]`, "requires sourceRef and lowercase sha256 digest")
    if (observedAt.right >= eventTime.right || observedAt.right > asOf.right) return fail("FUTURE_EVIDENCE", `$.evidence[${index}].observedAt`, "must be before eventTime and no later than subject.asOf")
    decodedEvidence.push(freeze({ sourceRef: item.right["sourceRef"], digest: item.right["digest"], observedAt: observedAt.right }))
  }
  return Either.right(freeze({ subject: freeze({ observation: freeze({ ...(bit(observationRecord["r"]) ? { r: observationRecord["r"] } : {}), ...(bit(observationRecord["h"]) ? { h: observationRecord["h"] } : {}) }), asOf: asOf.right, requested: freeze({ action: requested.right["action"] as ToyAction, horizon: 1, window: freeze({ start: start.right, end: end.right }) }) }), context: context.right, evidence: freeze(decodedEvidence), eventTime: eventTime.right }))
}

export const transitionToyState = (state: ToyState, action: ToyAction): ToyState => {
  const h: ToyBit = action === "block" ? 1 : action === "unblock" ? 0 : state.h
  const r: ToyBit = action === "pulse" && state.r === 0 && h === 0 ? 1 : 0
  return freeze({ r, h })
}
export const readToyFire = (state: ToyState, action: ToyAction): ToyBit => transitionToyState(state, action).r
export const mapToyState = (kind: ToyMappingKind, observation: Readonly<Partial<ToyState>>): MappingResult<ToyMappedState> => {
  if (kind === "preserve_r_h") {
    const missing = fields.filter(field => !bit(observation[field]))
    return missing.length > 0 ? freeze({ kind: "needs_observation", missing: freeze(missing) }) : freeze({ kind: "mapped", value: freeze({ r: observation.r!, h: observation.h! }), lossRefs: freeze([]) })
  }
  return !bit(observation.h) ? freeze({ kind: "needs_observation", missing: freeze(["h"]) }) : freeze({ kind: "mapped", value: freeze({ h: observation.h }), lossRefs: freeze(["refractory-state-r"]) })
}

export interface ToyModelDefinition {
  readonly modelRef: string
  readonly definitionBytes: string
}

/** Binds the digest to the exact fixture-definition bytes; it is not a model-result receipt. */
export const makeToyModelRef = (definition: ToyModelDefinition): ModelRef => freeze({
  modelRef: definition.modelRef,
  digest: createHash("sha256").update(definition.definitionBytes, "utf8").digest("hex")
})

export const makeToyMapSpec = (source: ToyModelDefinition, target: ToyModelDefinition, mappingKind: ToyMappingKind): MapSpec => freeze({
  schema: "hswm-cross-layer-map/v1",
  source: makeToyModelRef(source),
  target: makeToyModelRef(target),
  mappingKind,
  mappingMethod: "authored_deterministic",
  declaredLosses: freeze(mappingKind === "drop_refractory" ? ["refractory-state-r"] : []),
  actionAllowlist: actions,
  time: freeze({ unit: "tick", horizon: 1 }),
  supportScope: freeze({ world: "finite-toy-rh/v1", contexts: freeze(["baseline"]), observableFields: freeze(mappingKind === "drop_refractory" ? ["h"] : ["r", "h"]) })
})

export const makeToyInputPacket = (context: MapSpec, observation: Readonly<Partial<ToyState>>, asOf: number, action: ToyAction, evidence: CrossLayerInputPacket["evidence"] = freeze([])): Either.Either<CrossLayerInputPacket, CrossLayerMapDecodeError> =>
  decodeCrossLayerInputPacket({ subject: { observation, asOf, requested: { action, horizon: 1, window: { start: asOf, end: asOf + 1 } } }, context, evidence, eventTime: asOf })

const transitionPreserved = (state: Readonly<{ readonly r: ToyBit; readonly h: ToyBit }>, action: ToyAction): Readonly<{ readonly r: ToyBit; readonly h: ToyBit }> => transitionToyState(state, action)
const transitionLossy = (state: Readonly<{ readonly h: ToyBit }>, action: ToyAction): Readonly<{ readonly h: ToyBit }> => freeze({ h: action === "block" ? 1 : action === "unblock" ? 0 : state.h })
const sameState = (left: ToyMappedState, right: ToyMappedState): boolean => "r" in left === "r" in right && left.h === right.h && (!("r" in left) || ("r" in right && left.r === right.r))

/** Enumerates all 4 states × 4 actions. State-only q(h) commutes, while no fire readout g(h, action) can. */
export const compareToyMappings = (): ToyComparisonSummary => {
  const states: readonly ToyState[] = freeze([freeze({ r: 0, h: 0 }), freeze({ r: 0, h: 1 }), freeze({ r: 1, h: 0 }), freeze({ r: 1, h: 1 })])
  const rows: ToyComparisonRow[] = []
  for (const state of states) for (const action of actions) {
    const next = transitionToyState(state, action)
    const preservedBefore = mapToyState("preserve_r_h", state) as Extract<MappingResult<ToyMappedState>, { readonly kind: "mapped" }>
    const preservedAfter = mapToyState("preserve_r_h", next) as Extract<MappingResult<ToyMappedState>, { readonly kind: "mapped" }>
    const lossyBefore = mapToyState("drop_refractory", state) as Extract<MappingResult<ToyMappedState>, { readonly kind: "mapped" }>
    const lossyAfter = mapToyState("drop_refractory", next) as Extract<MappingResult<ToyMappedState>, { readonly kind: "mapped" }>
    rows.push(freeze({ state, action, preserveStateCommutes: sameState(preservedAfter.value, transitionPreserved(preservedBefore.value as ToyState, action)), preserveFireCommutes: readToyFire(state, action) === readToyFire(preservedBefore.value as ToyState, action), lossyStateCommutes: sameState(lossyAfter.value, transitionLossy(lossyBefore.value as Readonly<{ readonly h: ToyBit }>, action)), lossyFireReadoutPossible: true }))
  }
  const grouped = new Map<string, { readonly mappedState: Readonly<{ readonly h: ToyBit }>; readonly action: ToyAction; readonly fireValues: Set<ToyBit> }>()
  for (const row of rows) {
    const mapped = mapToyState("drop_refractory", row.state) as Extract<MappingResult<ToyMappedState>, { readonly kind: "mapped" }>
    const state = mapped.value as Readonly<{ readonly h: ToyBit }>
    const key = `${state.h}:${row.action}`
    const existing = grouped.get(key) ?? { mappedState: freeze({ h: state.h }), action: row.action, fireValues: new Set<ToyBit>() }
    existing.fireValues.add(readToyFire(row.state, row.action)); grouped.set(key, existing)
  }
  const conflicts = freeze([...grouped.values()].filter(entry => entry.fireValues.size > 1).map(entry => freeze({ mappedState: entry.mappedState, action: entry.action, fireValues: freeze([...entry.fireValues].sort()) })))
  const finalizedRows = freeze(rows.map(row => freeze({ ...row, lossyFireReadoutPossible: !conflicts.some(conflict => conflict.mappedState.h === row.state.h && conflict.action === row.action) })))
  return freeze({ rows: finalizedRows, totalRows: 16, preserve: freeze({ stateCommutingRows: finalizedRows.filter(row => row.preserveStateCommutes).length, fireCommutingRows: finalizedRows.filter(row => row.preserveFireCommutes).length }), dropRefractory: freeze({ stateCommutingRows: finalizedRows.filter(row => row.lossyStateCommutes).length, unambiguousReadoutRows: finalizedRows.filter(row => row.lossyFireReadoutPossible).length, conflictingReadoutClasses: conflicts }) })
}
