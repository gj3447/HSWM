/** Bounded one-shot native HTTP capability, without automatic retries or redirects. */
import type { NativeProm9JsonTransportRequest } from "./native-prom9-json-transport-domain.js";
import { Effect } from "effect";
import { NativeProm9JsonTransportRuntimeError, type NativeProm9JsonHttpShape, type NativeProm9JsonEnvironmentShape } from "./native-prom9-json-transport-runtime.js";
const failure = (detail: string) => new NativeProm9JsonTransportRuntimeError({ detail });
const maximumBytes = 16 * 1024 * 1024;
const collect = (reader: ReadableStreamDefaultReader<Uint8Array>, chunks: readonly Uint8Array[] = [], total = 0): Effect.Effect<Uint8Array, NativeProm9JsonTransportRuntimeError> => Effect.gen(function* () {
    const chunk = yield* Effect.tryPromise({ try: () => reader.read(), catch: () => failure("response read failed") });
    if (chunk.done) {
        const result = new Uint8Array(total);
        let offset = 0;
        for (const item of chunks) {
            result.set(item, offset);
            offset += item.length;
        }
        return result;
    }
    if (total + chunk.value.byteLength > maximumBytes)
        return yield* Effect.fail(failure("response byte bound exceeded"));
    return yield* collect(reader, [...chunks, chunk.value], total + chunk.value.byteLength);
});
export const NativeProm9JsonHttpLive: NativeProm9JsonHttpShape = Object.freeze({ post: (request: NativeProm9JsonTransportRequest) => Effect.acquireUseRelease(Effect.sync(() => new AbortController()), controller => Effect.gen(function* () {
        const response = yield* Effect.tryPromise({ try: () => fetch(request.url, { method: "POST", headers: request.headers, body: new Uint8Array(request.body), signal: controller.signal, redirect: "error" }), catch: () => failure("HTTP POST failed") });
        if (!response.ok || response.body === null)
            return yield* Effect.fail(failure("HTTP status or response body invalid"));
        const body = yield* Effect.acquireUseRelease(Effect.sync(() => response.body!.getReader()), reader => collect(reader), reader => Effect.tryPromise({ try: () => reader.cancel(), catch: () => failure("response cleanup failed") }).pipe(Effect.orDie));
        return Object.freeze({ status: response.status, body });
    }).pipe(Effect.timeoutFail({ duration: request.timeoutMilliseconds, onTimeout: () => failure("HTTP deadline exceeded") })), controller => Effect.sync(() => controller.abort())) });
export const NativeProm9JsonEnvironmentLive: NativeProm9JsonEnvironmentShape = Object.freeze({ read: (name: string) => Effect.sync(() => process.env[name]) });
