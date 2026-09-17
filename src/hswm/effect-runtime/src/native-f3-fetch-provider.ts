/**
 * One-shot OpenAI-compatible transport for the durable F3 cache seam.
 *
 * A rejected fetch, non-success HTTP response, redirect failure, timeout, or
 * response-read failure is UNKNOWN_DELIVERY: the request may have reached the
 * provider, so the durable reservation must remain open.  Only local request
 * validation can prove NOT_SENT.
 */
import { Effect, Either } from "effect";
import {
  NativeF3CacheProviderError,
  type NativeF3CacheProviderShape
} from "./native-f3-cache-runtime.js";
import type { NativeF3ChatTransportRequest } from "./native-f3-chat-runtime.js";

const MAXIMUM_RESPONSE_BYTES = 1024 * 1024;

type NativeF3Fetch = typeof globalThis.fetch;

export interface NativeF3FetchProviderOptions {
  readonly fetch: NativeF3Fetch;
}

const notSent = (detail: string) => new NativeF3CacheProviderError({ delivery: "NOT_SENT", detail });
const unknownDelivery = (detail: string) => new NativeF3CacheProviderError({ delivery: "UNKNOWN_DELIVERY", detail });

const validate = (request: NativeF3ChatTransportRequest): Either.Either<NativeF3ChatTransportRequest, NativeF3CacheProviderError> => {
  if (typeof request.url !== "string" || request.url.length === 0 || request.url.length > 1_000_000 || request.url.includes("\u0000")) return Either.left(notSent("request URL is invalid"));
  try {
    const url = new URL(request.url);
    if ((url.protocol !== "http:" && url.protocol !== "https:") || url.username || url.password) return Either.left(notSent("request URL scheme or credentials are invalid"));
  } catch {
    return Either.left(notSent("request URL is invalid"));
  }
  if (typeof request.bodyUtf8 !== "string") return Either.left(notSent("request body is invalid"));
  if (!Number.isFinite(request.timeoutSeconds) || request.timeoutSeconds <= 0 || request.timeoutSeconds > 86_400) return Either.left(notSent("request timeout is invalid"));
  return Either.right(request);
};

const collect = (reader: ReadableStreamDefaultReader<Uint8Array>, chunks: ReadonlyArray<Uint8Array> = [], total = 0): Effect.Effect<Uint8Array, NativeF3CacheProviderError> => Effect.gen(function* () {
  const next = yield* Effect.tryPromise({
    try: () => reader.read(),
    catch: () => unknownDelivery("response read failed")
  });
  if (next.done) {
    const result = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return result;
  }
  if (total + next.value.byteLength > MAXIMUM_RESPONSE_BYTES) return yield* Effect.fail(unknownDelivery("response body exceeds bound"));
  return yield* collect(reader, [...chunks, next.value], total + next.value.byteLength);
});

const dispatch = (fetchImpl: NativeF3Fetch, request: NativeF3ChatTransportRequest): Effect.Effect<unknown, NativeF3CacheProviderError> => Effect.acquireUseRelease(
  Effect.sync(() => new AbortController()),
  controller => Effect.gen(function* () {
    const response = yield* Effect.tryPromise({
      try: () => fetchImpl(request.url, Object.freeze({ method: "POST", headers: Object.freeze({ "content-type": "application/json" }), body: request.bodyUtf8, signal: controller.signal, redirect: "error" })),
      catch: () => unknownDelivery("HTTP dispatch failed after request start")
    });
    if (!response.ok || response.body === null) return yield* Effect.fail(unknownDelivery("HTTP status or response body invalid"));
    const bytes = yield* Effect.acquireUseRelease(
      Effect.sync(() => response.body!.getReader()),
      reader => collect(reader),
      reader => Effect.sync(() => controller.abort()).pipe(Effect.zipRight(
        Effect.tryPromise({ try: () => reader.cancel(), catch: () => unknownDelivery("response cleanup failed") }).pipe(Effect.timeout("1 second"), Effect.ignore)
      ))
    );
    return yield* Effect.try({
      try: () => JSON.parse(new TextDecoder().decode(bytes)) as unknown,
      catch: () => unknownDelivery("response JSON is invalid")
    });
  }).pipe(Effect.timeoutFail({ duration: request.timeoutSeconds * 1000, onTimeout: () => unknownDelivery("HTTP deadline exceeded") })),
  controller => Effect.sync(() => controller.abort())
);

/** Inject fetch in tests; this provider deliberately has no retry policy. */
export const makeNativeF3FetchProvider = (options: NativeF3FetchProviderOptions): NativeF3CacheProviderShape => {
  const fetchImpl: NativeF3Fetch | undefined = typeof options.fetch === "function" ? options.fetch : undefined;
  return Object.freeze({
    post: (request: NativeF3ChatTransportRequest) => {
      const checked = validate(request);
      if (Either.isLeft(checked)) return Effect.fail(checked.left);
      return fetchImpl === undefined ? Effect.fail(notSent("fetch implementation is unavailable")) : dispatch(fetchImpl, checked.right);
    }
  });
};

/** The only live capability is the platform fetch supplied by Node. */
export const NativeF3FetchProviderLive = makeNativeF3FetchProvider(Object.freeze({ fetch: globalThis.fetch }));
