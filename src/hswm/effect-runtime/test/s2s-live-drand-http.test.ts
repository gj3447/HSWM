import { expect, it } from "@effect/vitest"
import { Effect, Either, Fiber } from "effect"

import {
  S2S_DRAND_EXACT_PULSE_MAX_BYTES,
  S2SExactDrandPulseSource,
  type S2SExactDrandPulseRequest
} from "../src/s2s-live-drand.js"
import {
  S2SExactDrandPulseSourceHttpLive,
  makeS2SExactDrandPulseSourceHttpLayer
} from "../src/s2s-live-drand-http.js"
import { S2S_QUICKNET_CHAIN_HASH } from "../src/s2s-quicknet.js"

const ROUND = 1_000
const EXACT_URL =
  `https://api.drand.sh/${S2S_QUICKNET_CHAIN_HASH}/public/${ROUND}` as const
const RESPONSE_BYTES = new TextEncoder().encode(
  '{"round":1000,"randomness":"00","signature":"11"}\n'
)

const exactRequest = (): S2SExactDrandPulseRequest =>
  Object.freeze({
    chainHashHex: S2S_QUICKNET_CHAIN_HASH,
    round: ROUND,
    url: EXACT_URL,
    maximumResponseBytes: S2S_DRAND_EXACT_PULSE_MAX_BYTES
  })

it.effect(
  "performs one unauthenticated GET for only the committed exact-round URL",
  () => {
    const originalFetch = globalThis.fetch
    const responseBacking = new Uint8Array(RESPONSE_BYTES)
    const invocations: Array<{
      readonly url: string
      readonly method: string | undefined
      readonly redirect: RequestInit["redirect"]
      readonly credentials: RequestInit["credentials"]
      readonly referrerPolicy: RequestInit["referrerPolicy"]
      readonly headers: Headers
      readonly signalWasPresent: boolean
      readonly signalWasAborted: boolean
    }> = []

    globalThis.fetch = (async (
      input: string | URL | Request,
      init?: RequestInit
    ) => {
      invocations.push({
        url: String(input),
        method: init?.method,
        redirect: init?.redirect,
        credentials: init?.credentials,
        referrerPolicy: init?.referrerPolicy,
        headers: new Headers(init?.headers),
        signalWasPresent: init?.signal !== undefined && init.signal !== null,
        signalWasAborted: init?.signal?.aborted ?? false
      })
      return new Response(
        new ReadableStream<Uint8Array>({
          start: (controller) => {
            controller.enqueue(responseBacking)
            controller.close()
          }
        }),
        {
          status: 200,
          headers: {
            "content-length": String(responseBacking.byteLength),
            "content-type": "application/json"
          }
        }
      )
    }) as typeof fetch

    return Effect.gen(function* () {
      const source = yield* S2SExactDrandPulseSource
      const body = yield* source.acquireExact(exactRequest())
      responseBacking.fill(0)

      expect(body).toEqual(RESPONSE_BYTES)
      expect(invocations).toHaveLength(1)
      expect(invocations[0]).toMatchObject({
        url: EXACT_URL,
        method: "GET",
        redirect: "manual",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        signalWasPresent: true,
        signalWasAborted: false
      })
      expect(invocations[0]?.headers.get("accept")).toBe("application/json")
      expect(invocations[0]?.headers.get("accept-encoding")).toBe("identity")
      expect(invocations[0]?.headers.get("authorization")).toBeNull()
      expect(invocations[0]?.headers.get("cookie")).toBeNull()
    }).pipe(
      Effect.provide(S2SExactDrandPulseSourceHttpLive),
      Effect.ensuring(
        Effect.sync(() => {
          globalThis.fetch = originalFetch
        })
      )
    )
  }
)

it.effect("rejects every non-canonical chain, round, URL, or bound before fetch", () => {
  const originalFetch = globalThis.fetch
  let fetchCount = 0
  let accessorRead = false
  globalThis.fetch = (async () => {
    fetchCount += 1
    throw new Error("invalid requests must not reach fetch")
  }) as typeof fetch

  const accessorRequest: Record<string, unknown> = {
    chainHashHex: S2S_QUICKNET_CHAIN_HASH,
    round: ROUND,
    maximumResponseBytes: S2S_DRAND_EXACT_PULSE_MAX_BYTES
  }
  Object.defineProperty(accessorRequest, "url", {
    enumerable: true,
    get: () => {
      accessorRead = true
      return EXACT_URL
    }
  })

  const invalidRequests: ReadonlyArray<unknown> = [
    { ...exactRequest(), chainHashHex: "00".repeat(32) },
    { ...exactRequest(), round: 0, url: exactRequest().url.replace("1000", "0") },
    { ...exactRequest(), url: "https://api.drand.sh/public/latest" },
    { ...exactRequest(), url: EXACT_URL.replace("/1000", "/1001") },
    { ...exactRequest(), url: EXACT_URL.replace("https:", "http:") },
    { ...exactRequest(), url: EXACT_URL.replace("api.drand.sh", "api2.drand.sh") },
    { ...exactRequest(), url: `${EXACT_URL}?round=1000` },
    {
      ...exactRequest(),
      maximumResponseBytes: S2S_DRAND_EXACT_PULSE_MAX_BYTES - 1
    },
    { ...exactRequest(), extra: true },
    accessorRequest
  ]

  return Effect.gen(function* () {
    const source = yield* S2SExactDrandPulseSource
    const outcomes = yield* Effect.forEach(
      invalidRequests,
      (request) =>
        source
          .acquireExact(request as S2SExactDrandPulseRequest)
          .pipe(Effect.either),
      { concurrency: 1 }
    )
    expect(outcomes.every(Either.isLeft)).toBe(true)
    for (const outcome of outcomes) {
      if (Either.isLeft(outcome)) expect(outcome.left.reason).toBe("SOURCE_FAILED")
    }
    expect(fetchCount).toBe(0)
    expect(accessorRead).toBe(false)
  }).pipe(
    Effect.provide(S2SExactDrandPulseSourceHttpLive),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("rejects redirects, non-200 statuses, and non-exact media types without retry", () => {
  const originalFetch = globalThis.fetch
  let fetchCount = 0
  const responses = [
    () =>
      new Response(null, {
        status: 302,
        headers: { location: "https://api2.drand.sh/public/latest" }
      }),
    () =>
      new Response(RESPONSE_BYTES, {
        status: 503,
        headers: { "content-type": "application/json" }
      }),
    () =>
      new Response(RESPONSE_BYTES, {
        status: 200,
        headers: { "content-type": "text/plain" }
      }),
    () =>
      new Response(RESPONSE_BYTES, {
        status: 200,
        headers: { "content-type": "application/json; charset=utf-8" }
      })
  ]
  globalThis.fetch = (async () => {
    const response = responses[fetchCount]?.()
    fetchCount += 1
    if (response === undefined) throw new Error("unexpected retry")
    return response
  }) as typeof fetch

  return Effect.gen(function* () {
    const source = yield* S2SExactDrandPulseSource
    for (const expectedCount of [1, 2, 3, 4]) {
      const outcome = yield* source.acquireExact(exactRequest()).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) expect(outcome.left.reason).toBe("SOURCE_FAILED")
      expect(fetchCount).toBe(expectedCount)
    }
  }).pipe(
    Effect.provide(S2SExactDrandPulseSourceHttpLive),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("cancels a streamed body that crosses the committed byte bound", () => {
  const originalFetch = globalThis.fetch
  let cancelled = false
  globalThis.fetch = (async () => {
    let emitted = false
    return new Response(
      new ReadableStream<Uint8Array>({
        pull: (controller) => {
          if (!emitted) {
            emitted = true
            controller.enqueue(
              new Uint8Array(S2S_DRAND_EXACT_PULSE_MAX_BYTES)
            )
          } else {
            controller.enqueue(Uint8Array.of(0))
          }
        },
        cancel: () => {
          cancelled = true
        }
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" }
      }
    )
  }) as typeof fetch

  return Effect.gen(function* () {
    const source = yield* S2SExactDrandPulseSource
    const outcome = yield* source.acquireExact(exactRequest()).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) expect(outcome.left.reason).toBe("SOURCE_FAILED")
    expect(cancelled).toBe(true)
  }).pipe(
    Effect.provide(S2SExactDrandPulseSourceHttpLive),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("aborts a stalled request at the configured bounded timeout", () => {
  const originalFetch = globalThis.fetch
  let aborted = false
  globalThis.fetch = ((_input: string | URL | Request, init?: RequestInit) =>
    new Promise<Response>(() => {
      const signal = init?.signal
      if (signal === null || signal === undefined) {
        throw new Error("missing AbortSignal")
      }
      const onAbort = (): void => {
        aborted = true
      }
      if (signal.aborted) onAbort()
      else signal.addEventListener("abort", onAbort, { once: true })
    })) as typeof fetch

  return Effect.gen(function* () {
    const source = yield* S2SExactDrandPulseSource
    const outcome = yield* source.acquireExact(exactRequest()).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("INTERRUPTED_OR_TIMED_OUT")
    }
    expect(aborted).toBe(true)
  }).pipe(
    Effect.provide(makeS2SExactDrandPulseSourceHttpLayer(20)),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("propagates Effect interruption to the in-flight fetch AbortSignal", () => {
  const originalFetch = globalThis.fetch
  let aborted = false
  globalThis.fetch = ((_input: string | URL | Request, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal
      if (signal === null || signal === undefined) {
        reject(new Error("missing AbortSignal"))
        return
      }
      const onAbort = (): void => {
        aborted = true
        reject(new Error("aborted"))
      }
      if (signal.aborted) onAbort()
      else signal.addEventListener("abort", onAbort, { once: true })
    })) as typeof fetch

  return Effect.gen(function* () {
    const source = yield* S2SExactDrandPulseSource
    const fiber = yield* Effect.fork(source.acquireExact(exactRequest()))
    yield* Effect.promise(
      () => new Promise<void>((resolve) => setImmediate(resolve))
    )
    yield* Fiber.interrupt(fiber)
    expect(aborted).toBe(true)
  }).pipe(
    Effect.provide(S2SExactDrandPulseSourceHttpLive),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})
