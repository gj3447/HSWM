/**
 * Private, bounded transport for the finite semantic-lifecycle wiring study.
 *
 * This adapter records what it sends and receives, but never records request
 * headers: an API credential is a transport capability, not experiment data.
 * `scripted` is deliberately an authored fixture and establishes no model
 * efficacy.
 */
import { randomUUID } from "node:crypto"
import { join } from "node:path"
import { Data, Effect, Ref } from "effect"
import {
  AdaptiveExecutorError,
  AdaptiveHttpClient,
  type AdaptiveHttpClientShape,
  type AdaptiveHttpRequest
} from "./adaptive-executor.js"
import type { CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { INITIAL_TEXT, REVISED_TEXT, SHAM_TEXT, bytes, sha } from "./semantic-lifecycle-runtime.js"

export const SEMANTIC_LIFECYCLE_TRANSPORT_V1 = "hswm-semantic-lifecycle-transport/v1" as const

const SYSTEM_INSTRUCTIONS = "Use the supplied semantic relation and role context to predict. Return only the JSON object with exactly the keys in requiredOutput. For prediction, return a bit string in event.cases order: 1 means opens, 0 means closed. For learning, propose a concise general semantic relation from the observed training cases, preserve exceptionRefs exactly, and state uncertainty. No tools."
const MAX_TIMEOUT_MS = 30_000

export type SemanticLifecycleTransportMode = "scripted" | "http"

export interface SemanticLifecycleTransportConfig {
  readonly mode: SemanticLifecycleTransportMode
  readonly logRoot: string
  /** An authored semantic-text control. It never invokes the HTTP endpoint. */
  readonly controlText?: string
}

export interface CallReceipt {
  readonly id: string
  readonly contract: typeof SEMANTIC_LIFECYCLE_TRANSPORT_V1
  readonly semanticContract: string
  readonly mode: "scripted" | "http" | "AUTHORED_CONTROL_CONSTRUCTION"
  /** A caller-declared HTTP endpoint is not independently verified as an LLM. */
  readonly httpModelRequest: boolean
  readonly requestSha256: string
  readonly frameSha256: string
  readonly relationKey: CanonicalAtomV2Key
  readonly latencyMs: number
  readonly status: "RESPONSE_RECEIVED" | "TRANSPORT_FAILED"
  readonly responseSha256: string | null
  readonly usage: unknown | null
  readonly reportedModel: string | null
  readonly finishReason: string | null
}

export interface SemanticLifecycleTransport {
  readonly http: AdaptiveHttpClientShape
  readonly calls: Effect.Effect<ReadonlyArray<CallReceipt>>
}

export class LifecycleTransportError extends Data.TaggedError("LifecycleTransportError")<{
  readonly code: "CONFIG_INVALID" | "WIRE_INVALID" | "SCRIPTED_UNSUPPORTED" | "CONTROL_CONTRACT_INVALID" | "PRIVATE_LOG_FAILED"
  readonly detail: string
}> {}

type JsonRecord = Readonly<Record<string, unknown>>
type SemanticFrame = Readonly<{
  readonly frameSha256: string
  readonly relationKey: CanonicalAtomV2Key
  readonly semanticText: string
  readonly disposition: unknown
  readonly uncertainty: unknown
  readonly exceptionRefs: ReadonlyArray<unknown>
}>
type TransportPayload = Readonly<{ readonly contract: string; readonly frame: SemanticFrame; readonly event: string | null }>
type Wire = Readonly<{ readonly messages: ReadonlyArray<JsonRecord>; readonly raw: JsonRecord; readonly payload: TransportPayload }>

const error = (code: LifecycleTransportError["code"], detail: string): LifecycleTransportError => new LifecycleTransportError({ code, detail })
const httpError = (code: AdaptiveExecutorError["code"], detail: string): AdaptiveExecutorError => new AdaptiveExecutorError({ code, detail })
const asRecord = (value: unknown): JsonRecord | null => value !== null && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : null
const text = (value: unknown): string | null => typeof value === "string" && value.length > 0 ? value : null
const unknownJson = (value: unknown): unknown => value === undefined ? null : value
const canonicalKey = (value: unknown): CanonicalAtomV2Key | null => {
  const record = asRecord(value)
  const schemaVersion = record === null ? null : text(record["schemaVersion"])
  const lineageId = record === null ? null : text(record["lineageId"])
  const atomUid = record === null ? null : text(record["atomUid"])
  const revisionId = record === null ? null : record["revisionId"]
  return schemaVersion === null || lineageId === null || atomUid === null || typeof revisionId !== "number" || !Number.isSafeInteger(revisionId) || revisionId < 0
    ? null
    : Object.freeze({ schemaVersion, lineageId, atomUid, revisionId })
}

const decodeJson = (raw: Uint8Array, label: string): Effect.Effect<unknown, LifecycleTransportError> =>
  Effect.try({
    try: () => JSON.parse(new TextDecoder().decode(raw)) as unknown,
    catch: () => error("WIRE_INVALID", `${label} is not valid JSON`)
  })

const encodeJson = (value: unknown, label: string): Effect.Effect<Uint8Array, LifecycleTransportError> =>
  Effect.try({
    try: () => JSON.stringify(value),
    catch: () => error("WIRE_INVALID", `${label} is not JSON serializable`)
  }).pipe(Effect.flatMap((encoded) => typeof encoded === "string"
    ? Effect.succeed(new TextEncoder().encode(encoded))
    : Effect.fail(error("WIRE_INVALID", `${label} has no JSON root representation`))))

const decodeWire = (raw: Uint8Array): Effect.Effect<Wire, LifecycleTransportError> => Effect.gen(function* () {
  const decoded = yield* decodeJson(raw, "HTTP request")
  const root = asRecord(decoded)
  if (root === null) return yield* Effect.fail(error("WIRE_INVALID", "HTTP request must be a JSON object"))
  const suppliedMessages = root["messages"]
  if (!Array.isArray(suppliedMessages) || suppliedMessages.length < 1) return yield* Effect.fail(error("WIRE_INVALID", "HTTP request requires messages"))
  const messages = suppliedMessages.map(asRecord)
  if (messages.some((message) => message === null)) return yield* Effect.fail(error("WIRE_INVALID", "HTTP request messages must be objects"))
  const first = messages[0]
  if (first === undefined || first === null) return yield* Effect.fail(error("WIRE_INVALID", "first HTTP message requires string content"))
  const firstContent = first["content"]
  if (typeof firstContent !== "string") return yield* Effect.fail(error("WIRE_INVALID", "first HTTP message requires string content"))
  const payloadValue = yield* decodeJson(bytes(firstContent), "semantic payload")
  const payloadRoot = asRecord(payloadValue)
  const contract = payloadRoot === null ? null : text(payloadRoot["contract"])
  const frameRoot = payloadRoot === null ? null : asRecord(payloadRoot["frame"])
  const relation = frameRoot === null ? null : asRecord(frameRoot["relation"])
  const semantic = relation === null ? null : asRecord(relation["semantic"])
  const frameSha256 = frameRoot === null ? null : text(frameRoot["frameSha256"])
  const relationKey = relation === null ? null : canonicalKey(relation["key"])
  const semanticText = semantic === null ? null : text(semantic["semanticText"])
  const event = frameRoot === null ? null : text(frameRoot["event"])
  if (contract === null || frameSha256 === null || relationKey === null || semanticText === null || semantic === null) {
    return yield* Effect.fail(error("WIRE_INVALID", "semantic payload lacks contract, frame hash, relation key, or semantic text"))
  }
  return Object.freeze({
    messages: Object.freeze(messages as ReadonlyArray<JsonRecord>), raw: root,
    payload: Object.freeze({
      contract,
      frame: Object.freeze({ frameSha256, relationKey, semanticText, disposition: semantic["disposition"], uncertainty: semantic["uncertainty"], exceptionRefs: Array.isArray(semantic["exceptionRefs"]) ? Object.freeze([...semantic["exceptionRefs"]]) : Object.freeze([]) }),
      event
    })
  })
})

const eventCases = (event: string | null): Effect.Effect<ReadonlyArray<JsonRecord>, LifecycleTransportError> => Effect.gen(function* () {
  if (event === null) return yield* Effect.fail(error("WIRE_INVALID", "prediction payload requires event"))
  const decoded = yield* decodeJson(bytes(event), "semantic event")
  const root = asRecord(decoded)
  const cases = root === null ? null : root["cases"]
  if (!Array.isArray(cases)) return yield* Effect.fail(error("WIRE_INVALID", "semantic event requires cases"))
  const values = cases.map(asRecord)
  if (values.some((value) => value === null)) return yield* Effect.fail(error("WIRE_INVALID", "semantic event cases must be objects"))
  return Object.freeze(values as ReadonlyArray<JsonRecord>)
})

const booleanField = (record: JsonRecord, name: string): Effect.Effect<boolean, LifecycleTransportError> => {
  const value = record[name]
  return typeof value === "boolean"
    ? Effect.succeed(value)
    : Effect.fail(error("WIRE_INVALID", `semantic event case requires boolean input.${name}`))
}

/** Fixed authored outputs deliberately do not constitute learning or model evidence. */
const scriptedResponse = (payload: TransportPayload): Effect.Effect<JsonRecord, LifecycleTransportError> => Effect.gen(function* () {
  if (payload.contract === "hswm-llm-semantic-learn/v1") {
    return Object.freeze({ semanticText: REVISED_TEXT, disposition: payload.frame.disposition, uncertainty: "scripted fixture; no model evidence", exceptionRefs: payload.frame.exceptionRefs })
  }
  if (payload.frame.semanticText !== INITIAL_TEXT && payload.frame.semanticText !== SHAM_TEXT && payload.frame.semanticText !== REVISED_TEXT) {
    return yield* Effect.fail(error("SCRIPTED_UNSUPPORTED", "unknown scripted semantic text"))
  }
  const cases = yield* eventCases(payload.event)
  const prediction = yield* Effect.forEach(cases, (entry) => Effect.gen(function* () {
    const input = asRecord(entry["input"])
    if (input === null) return yield* Effect.fail(error("WIRE_INVALID", "semantic event case requires input"))
    const pressed = yield* booleanField(input, "pressed")
    if (payload.frame.semanticText !== REVISED_TEXT) return pressed ? "1" : "0"
    const manualRelease = yield* booleanField(input, "manualRelease")
    const power = yield* booleanField(input, "power")
    const locked = yield* booleanField(input, "locked")
    return manualRelease || (pressed && power && !locked) ? "1" : "0"
  }))
  return Object.freeze({ prediction: prediction.join(""), uncertainty: "scripted fixture; no calibrated probability" })
})

const responseEnvelope = (content: JsonRecord): Effect.Effect<Uint8Array, LifecycleTransportError> =>
  encodeJson(Object.freeze({ choices: Object.freeze([Object.freeze({ message: Object.freeze({ content: JSON.stringify(content) }) })]) }), "transport response")

const controlResponse = (payload: TransportPayload, controlText: string): Effect.Effect<Uint8Array, LifecycleTransportError> =>
  payload.contract !== "hswm-llm-semantic-learn/v1"
    ? Effect.fail(error("CONTROL_CONTRACT_INVALID", "authored control construction accepts revision only"))
    : responseEnvelope(Object.freeze({ semanticText: controlText, disposition: payload.frame.disposition, uncertainty: payload.frame.uncertainty, exceptionRefs: payload.frame.exceptionRefs }))

const responseMetadata = (raw: Uint8Array): Effect.Effect<Readonly<{ readonly usage: unknown | null; readonly reportedModel: string | null; readonly finishReason: string | null }>> =>
  decodeJson(raw, "HTTP response").pipe(
    Effect.match({
      onFailure: () => Object.freeze({ usage: null, reportedModel: null, finishReason: null }),
      onSuccess: (decoded) => {
        const root = asRecord(decoded)
        const choices = root === null ? null : root["choices"]
        const first = Array.isArray(choices) ? asRecord(choices[0]) : null
        return Object.freeze({ usage: root === null ? null : unknownJson(root["usage"]), reportedModel: root === null ? null : text(root["model"]), finishReason: first === null ? null : text(first["finish_reason"]) })
      }
    })
  )

const privateWrite = (fs: import("./effect-posix-filesystem.js").PosixFileSystemShape, path: string, content: Uint8Array, operation: string): Effect.Effect<void, AdaptiveExecutorError> =>
  fs.writeExclusive(path, content, { mode: 0o600, sync: true, operation }).pipe(Effect.mapError(() => httpError("HTTP_FAILED", "private transport log write failed")))

const redactFailure = (value: AdaptiveExecutorError): AdaptiveExecutorError =>
  new AdaptiveExecutorError({ code: value.code, detail: value.code === "HTTP_FAILED" ? "HTTP transport failed" : value.detail })

export const createSemanticLifecycleTransport = (config: SemanticLifecycleTransportConfig): Effect.Effect<SemanticLifecycleTransport, LifecycleTransportError | AdaptiveExecutorError, PosixFileSystem | AdaptiveHttpClient> => Effect.gen(function* () {
  if (config.mode !== "scripted" && config.mode !== "http") return yield* Effect.fail(error("CONFIG_INVALID", "transport mode must be scripted or http"))
  if (config.logRoot.length === 0 || config.logRoot.includes("\0")) return yield* Effect.fail(error("CONFIG_INVALID", "private log root is invalid"))
  const fs = yield* PosixFileSystem
  const upstreamHttp = yield* AdaptiveHttpClient
  yield* fs.makeDirectory(config.logRoot, { mode: 0o700, recursive: true, operation: "semantic lifecycle private log root" }).pipe(Effect.mapError(() => httpError("HTTP_FAILED", "private transport log root unavailable")))
  yield* fs.chmod(config.logRoot, 0o700, "semantic lifecycle private log root mode").pipe(Effect.mapError(() => httpError("HTTP_FAILED", "private transport log root unavailable")))
  const callRef = yield* Ref.make<ReadonlyArray<CallReceipt>>(Object.freeze([]))
  const append = (receipt: CallReceipt): Effect.Effect<void> => Ref.update(callRef, (calls) => Object.freeze([...calls, receipt]))
  const postJson = (request: AdaptiveHttpRequest): Effect.Effect<Uint8Array, AdaptiveExecutorError> => Effect.gen(function* () {
    const wire = yield* decodeWire(request.body).pipe(Effect.mapError((cause) => httpError("HTTP_INVALID", cause.code)))
    const controlText = config.controlText
    const authoredControl = controlText !== undefined
    const actual = Object.freeze({ ...wire.raw, temperature: 0, messages: Object.freeze([Object.freeze({ role: "system", content: SYSTEM_INSTRUCTIONS }), ...wire.messages]) })
    const actualBytes = yield* encodeJson(actual, "HTTP request").pipe(Effect.mapError((cause) => httpError("HTTP_INVALID", cause.code)))
    const id = yield* Effect.sync(randomUUID)
    const requestPath = join(config.logRoot, `${id}.request.json`)
    const responsePath = join(config.logRoot, `${id}.response.json`)
    const receiptPath = join(config.logRoot, `${id}.receipt.json`)
    yield* privateWrite(fs, requestPath, actualBytes, "semantic lifecycle request receipt")
    const started = yield* Effect.clockWith((clock) => clock.currentTimeMillis)
    const execution: Effect.Effect<Uint8Array, AdaptiveExecutorError> = (controlText === undefined
      ? config.mode === "scripted"
        ? scriptedResponse(wire.payload).pipe(Effect.flatMap(responseEnvelope), Effect.mapError((cause) => httpError("HTTP_INVALID", cause.code)))
        : upstreamHttp.postJson(Object.freeze({ ...request, body: actualBytes, timeoutMs: Math.min(request.timeoutMs, MAX_TIMEOUT_MS) })).pipe(Effect.mapError(redactFailure))
      : controlResponse(wire.payload, controlText).pipe(Effect.mapError((cause) => httpError("HTTP_INVALID", cause.code)))
    )
    const response = yield* execution.pipe(Effect.either)
    const ended = yield* Effect.clockWith((clock) => clock.currentTimeMillis)
    const metadata = response._tag === "Right" ? yield* responseMetadata(response.right) : Object.freeze({ usage: null, reportedModel: null, finishReason: null })
    const receipt: CallReceipt = Object.freeze({
      id, contract: SEMANTIC_LIFECYCLE_TRANSPORT_V1, semanticContract: wire.payload.contract,
      mode: authoredControl ? "AUTHORED_CONTROL_CONSTRUCTION" : config.mode,
      httpModelRequest: !authoredControl && config.mode === "http",
      requestSha256: sha(actualBytes), frameSha256: wire.payload.frame.frameSha256, relationKey: wire.payload.frame.relationKey,
      latencyMs: Math.max(0, ended - started), status: response._tag === "Right" ? "RESPONSE_RECEIVED" : "TRANSPORT_FAILED",
      responseSha256: response._tag === "Right" ? sha(response.right) : null,
      usage: metadata.usage, reportedModel: metadata.reportedModel, finishReason: metadata.finishReason
    })
    if (response._tag === "Right") yield* privateWrite(fs, responsePath, response.right, "semantic lifecycle response receipt")
    yield* append(receipt)
    const receiptBytes = yield* encodeJson(receipt, "transport receipt").pipe(Effect.mapError((cause) => httpError("HTTP_FAILED", cause.code)))
    yield* privateWrite(fs, receiptPath, receiptBytes, "semantic lifecycle call receipt")
    return response._tag === "Right" ? response.right : yield* Effect.fail(response.left)
  })
  return Object.freeze({ http: Object.freeze({ postJson }), calls: Ref.get(callRef) })
})

/** Compatibility name for the lifecycle worker. */
export const createTransport = createSemanticLifecycleTransport
