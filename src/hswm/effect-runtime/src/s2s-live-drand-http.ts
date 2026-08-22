import { Effect, Layer } from "effect"

import {
  S2S_DRAND_EXACT_PULSE_MAX_BYTES,
  S2SExactDrandPulseSource,
  S2SExactDrandPulseSourceError,
  type S2SExactDrandPulseRequest
} from "./s2s-live-drand.js"
import {
  S2S_QUICKNET_CHAIN_HASH,
  s2sQuicknetRoundTimeUnix
} from "./s2s-quicknet.js"

export const S2S_DRAND_HTTP_ORIGIN = "https://api.drand.sh" as const
export const S2S_DRAND_HTTP_TIMEOUT_MILLIS = 30_000 as const

const MAXIMUM_HTTP_TIMEOUT_MILLIS = 120_000
const MAXIMUM_RESPONSE_CHUNKS = 1_024

interface PreparedExactRequest {
  readonly round: number
  readonly url: string
}

const sourceError = (
  reason: S2SExactDrandPulseSourceError["reason"],
  detail: string
): S2SExactDrandPulseSourceError =>
  new S2SExactDrandPulseSourceError({ reason, detail })

const exactPulsePath = (round: number): string =>
  `/${S2S_QUICKNET_CHAIN_HASH}/public/${round}`

const exactPulseUrl = (round: number): string =>
  `${S2S_DRAND_HTTP_ORIGIN}${exactPulsePath(round)}`

const isPlainRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  (Object.getPrototypeOf(value) === Object.prototype ||
    Object.getPrototypeOf(value) === null)

const snapshotExactRequest = (input: unknown): PreparedExactRequest => {
  if (!isPlainRecord(input)) {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand request must be one plain data record"
    )
  }

  const expectedKeys = [
    "chainHashHex",
    "maximumResponseBytes",
    "round",
    "url"
  ] as const
  const actualKeys = Reflect.ownKeys(input)
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key) => typeof key !== "string") ||
    !actualKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
      .every((key, index) => key === expectedKeys[index])
  ) {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand request keys differ from the fixed HTTP contract"
    )
  }

  const snapshot: Record<string, unknown> = {}
  for (const key of expectedKeys) {
    const descriptor = Object.getOwnPropertyDescriptor(input, key)
    if (
      descriptor === undefined ||
      descriptor.enumerable !== true ||
      !("value" in descriptor)
    ) {
      throw sourceError(
        "SOURCE_FAILED",
        "exact drand request must contain only enumerable data properties"
      )
    }
    snapshot[key] = descriptor.value
  }

  const round = snapshot["round"]
  const url = snapshot["url"]
  if (
    snapshot["chainHashHex"] !== S2S_QUICKNET_CHAIN_HASH ||
    typeof round !== "number" ||
    !Number.isSafeInteger(round) ||
    s2sQuicknetRoundTimeUnix(round) === null ||
    typeof url !== "string" ||
    snapshot["maximumResponseBytes"] !== S2S_DRAND_EXACT_PULSE_MAX_BYTES
  ) {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand request chain, round, URL, or byte bound is invalid"
    )
  }

  const expectedPath = exactPulsePath(round)
  const expectedUrl = exactPulseUrl(round)
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand request URL is not an absolute HTTPS URL"
    )
  }
  if (
    url !== expectedUrl ||
    parsed.href !== expectedUrl ||
    parsed.protocol !== "https:" ||
    parsed.hostname !== "api.drand.sh" ||
    parsed.host !== "api.drand.sh" ||
    parsed.origin !== S2S_DRAND_HTTP_ORIGIN ||
    parsed.pathname !== expectedPath ||
    parsed.search !== "" ||
    parsed.hash !== "" ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    parsed.port !== ""
  ) {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand request is outside the fixed HTTPS host and round path"
    )
  }

  return Object.freeze({ round, url })
}

const cancelUnconsumedBody = async (response: Response): Promise<void> => {
  if (response.body !== null) {
    await response.body.cancel().catch(() => undefined)
  }
}

const validateResponseHeaders = async (response: Response): Promise<void> => {
  if (
    response.status !== 200 ||
    response.redirected ||
    response.headers.get("location") !== null
  ) {
    await cancelUnconsumedBody(response)
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP request did not return one non-redirect HTTP 200 response"
    )
  }

  const contentType = response.headers.get("content-type")
  if (
    contentType === null ||
    contentType.trim().toLowerCase() !== "application/json"
  ) {
    await cancelUnconsumedBody(response)
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP response Content-Type is not exactly application/json"
    )
  }

  const contentEncoding = response.headers.get("content-encoding")
  if (
    contentEncoding !== null &&
    contentEncoding.trim().toLowerCase() !== "identity"
  ) {
    await cancelUnconsumedBody(response)
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP response uses an unsupported content encoding"
    )
  }
}

const declaredResponseLength = (
  response: Response,
  maximumBytes: number
): Promise<number | null> => {
  const contentLength = response.headers.get("content-length")
  return (async () => {
    if (contentLength === null) return null
    if (!/^(0|[1-9][0-9]*)$/.test(contentLength)) {
      await cancelUnconsumedBody(response)
      throw sourceError(
        "SOURCE_FAILED",
        "exact drand HTTP response Content-Length is not a canonical integer"
      )
    }
    const declared = Number(contentLength)
    if (!Number.isSafeInteger(declared) || declared > maximumBytes) {
      await cancelUnconsumedBody(response)
      throw sourceError(
        "SOURCE_FAILED",
        "exact drand HTTP response exceeds the committed byte bound"
      )
    }
    return declared
  })()
}

const readBoundedBody = async (
  response: Response,
  maximumBytes: number,
  requestSignal: AbortSignal,
  timedOut: () => boolean
): Promise<Uint8Array> => {
  const declaredLength = await declaredResponseLength(response, maximumBytes)
  if (response.body === null) {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP response has no body"
    )
  }

  const reader = response.body.getReader()
  const chunks: Array<Uint8Array> = []
  let chunkCount = 0
  let total = 0
  try {
    while (true) {
      if (requestSignal.aborted) {
        await reader.cancel().catch(() => undefined)
        throw sourceError(
          "INTERRUPTED_OR_TIMED_OUT",
          timedOut()
            ? "exact drand HTTP request exceeded its fixed timeout"
            : "exact drand HTTP request was interrupted"
        )
      }
      const result = await reader.read()
      if (requestSignal.aborted) {
        await reader.cancel().catch(() => undefined)
        throw sourceError(
          "INTERRUPTED_OR_TIMED_OUT",
          timedOut()
            ? "exact drand HTTP request exceeded its fixed timeout"
            : "exact drand HTTP request was interrupted"
        )
      }
      if (result.done) break
      chunkCount += 1
      if (
        chunkCount > MAXIMUM_RESPONSE_CHUNKS ||
        result.value.byteLength > maximumBytes - total
      ) {
        await reader.cancel().catch(() => undefined)
        throw sourceError(
          "SOURCE_FAILED",
          "exact drand HTTP response stream exceeds its fixed bounds"
        )
      }
      total += result.value.byteLength
      chunks.push(new Uint8Array(result.value))
    }
  } catch (error: unknown) {
    if (error instanceof S2SExactDrandPulseSourceError) throw error
    if (requestSignal.aborted) {
      throw sourceError(
        "INTERRUPTED_OR_TIMED_OUT",
        timedOut()
          ? "exact drand HTTP request exceeded its fixed timeout"
          : "exact drand HTTP request was interrupted"
      )
    }
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP response stream could not be read to completion"
    )
  } finally {
    reader.releaseLock()
  }

  if (total === 0 || (declaredLength !== null && total !== declaredLength)) {
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP response body length is invalid"
    )
  }

  const body = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) {
    body.set(chunk, offset)
    offset += chunk.byteLength
  }
  return body
}

const performExactFetch = async (
  request: PreparedExactRequest,
  maximumBytes: number,
  timeoutMillis: number,
  interruptSignal: AbortSignal
): Promise<Uint8Array> => {
  const controller = new AbortController()
  let didTimeOut = false
  const abortFromInterruption = (): void => controller.abort()
  if (interruptSignal.aborted) controller.abort()
  interruptSignal.addEventListener("abort", abortFromInterruption, {
    once: true
  })
  let timeout: ReturnType<typeof setTimeout> | null = null

  try {
    const deadline = new Promise<never>((_resolve, reject) => {
      timeout = setTimeout(() => {
        didTimeOut = true
        controller.abort()
        reject(
          sourceError(
            "INTERRUPTED_OR_TIMED_OUT",
            "exact drand HTTP request exceeded its fixed timeout"
          )
        )
      }, timeoutMillis)
    })
    const operation = (async (): Promise<Uint8Array> => {
      const response = await fetch(request.url, {
        method: "GET",
        headers: Object.freeze({
          Accept: "application/json",
          "Accept-Encoding": "identity",
          "User-Agent": "hswm-s2s-effect-runtime"
        }),
        credentials: "omit",
        redirect: "manual",
        referrerPolicy: "no-referrer",
        signal: controller.signal
      })
      if (controller.signal.aborted) {
        await cancelUnconsumedBody(response)
        throw sourceError(
          "INTERRUPTED_OR_TIMED_OUT",
          didTimeOut
            ? "exact drand HTTP request exceeded its fixed timeout"
            : "exact drand HTTP request was interrupted"
        )
      }
      await validateResponseHeaders(response)
      const body = await readBoundedBody(
        response,
        maximumBytes,
        controller.signal,
        () => didTimeOut
      )
      return new Uint8Array(body)
    })()
    return await Promise.race([operation, deadline])
  } catch (error: unknown) {
    if (error instanceof S2SExactDrandPulseSourceError) throw error
    if (controller.signal.aborted) {
      throw sourceError(
        "INTERRUPTED_OR_TIMED_OUT",
        didTimeOut
          ? "exact drand HTTP request exceeded its fixed timeout"
          : "exact drand HTTP request was interrupted"
      )
    }
    throw sourceError(
      "SOURCE_FAILED",
      "exact drand HTTP request failed before a complete bounded response was observed"
    )
  } finally {
    if (timeout !== null) clearTimeout(timeout)
    interruptSignal.removeEventListener("abort", abortFromInterruption)
    controller.abort()
  }
}

/**
 * Read-only production adapter for the exact-round source port. The optional
 * timeout argument exists for deterministic adapter tests and remains capped;
 * it grants no URL, host, chain, round-selection, retry, or credential authority.
 */
export const makeS2SExactDrandPulseSourceHttpLayer = (
  timeoutMillis: number = S2S_DRAND_HTTP_TIMEOUT_MILLIS
) => {
  const validTimeout =
    Number.isSafeInteger(timeoutMillis) &&
    timeoutMillis >= 1 &&
    timeoutMillis <= MAXIMUM_HTTP_TIMEOUT_MILLIS

  return Layer.succeed(
    S2SExactDrandPulseSource,
    S2SExactDrandPulseSource.of({
      acquireExact: (request: S2SExactDrandPulseRequest) =>
        Effect.tryPromise({
          try: async (signal) => {
            if (!validTimeout) {
              throw sourceError(
                "SOURCE_FAILED",
                "exact drand HTTP timeout configuration is invalid"
              )
            }
            const prepared = snapshotExactRequest(request)
            return performExactFetch(
              prepared,
              S2S_DRAND_EXACT_PULSE_MAX_BYTES,
              timeoutMillis,
              signal
            )
          },
          catch: (error: unknown) =>
            error instanceof S2SExactDrandPulseSourceError
              ? error
              : sourceError(
                  "SOURCE_FAILED",
                  "exact drand HTTP source failed closed"
                )
        })
    })
  )
}

export const S2SExactDrandPulseSourceHttpLive =
  makeS2SExactDrandPulseSourceHttpLayer()
