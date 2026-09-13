/** One POST OpenAI-compatible adapter. It is a bounded transport capability, never a receipt store. */
import { Context, Data, Effect, Either, Layer } from "effect";
import { NativeProm9ModelPort, type NativeProm9ModelPortShape } from "./native-prom9-call-runtime.js";
import { NativeProm9CallError } from "./native-prom9-call-domain.js";
import { captureNativeProm9JsonCall, captureNativeProm9OpenAiCompatibleTransportConfiguration, configureNativeProm9OpenAiCompatibleTransport, prepareNativeProm9OpenAiCompatibleRequest, type NativeProm9JsonTransportConfiguration, type NativeProm9JsonTransportRequest } from "./native-prom9-json-transport-domain.js";
import { decodeNativeTaskJson, isTaskNumber, taskJsonRecord, taskNumberIsFloat, taskNumberValue, type TaskJson } from "./native-task-json-domain.js";
export class NativeProm9JsonTransportRuntimeError extends Data.TaggedError("NativeProm9JsonTransportRuntimeError")<{
    readonly detail: string;
}> {
}
export type NativeProm9JsonHttpResponse = Readonly<{
    readonly status: number;
    readonly body: Uint8Array;
}>;
export interface NativeProm9JsonHttpShape {
    readonly post: (request: NativeProm9JsonTransportRequest) => Effect.Effect<NativeProm9JsonHttpResponse, NativeProm9JsonTransportRuntimeError>;
}
export class NativeProm9JsonHttp extends Context.Tag("hswm/NativeProm9JsonHttp")<NativeProm9JsonHttp, NativeProm9JsonHttpShape>() {
}
export interface NativeProm9JsonEnvironmentShape {
    readonly read: (name: string) => Effect.Effect<string | undefined, NativeProm9JsonTransportRuntimeError>;
}
export class NativeProm9JsonEnvironment extends Context.Tag("hswm/NativeProm9JsonEnvironment")<NativeProm9JsonEnvironment, NativeProm9JsonEnvironmentShape>() {
}
const callError = (detail: string) => new NativeProm9CallError({ detail });
const MAX_RESPONSE_BYTES = 16 * 1024 * 1024;
const integer = (value: TaskJson | undefined): number | undefined => {
    if (value === undefined || !isTaskNumber(value) || taskNumberIsFloat(value))
        return undefined;
    const number = taskNumberValue(value);
    return typeof number === "number" && Number.isSafeInteger(number) && number >= 0 ? number : typeof number === "bigint" && number >= 0n && number <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(number) : undefined;
};
const parse = (bytes: Uint8Array): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9CallError> => Either.gen(function* () {
    const envelope = yield* decodeNativeTaskJson(bytes).pipe(Either.mapLeft(() => callError("model transport failed without retry: JSONDecodeError")));
    if (!taskJsonRecord(envelope) || typeof envelope["model"] !== "string" || !Array.isArray(envelope["choices"]) || !Object.hasOwn(envelope["choices"], 0))
        return yield* Either.left(callError("model transport failed without retry: malformed response envelope"));
    const choice = envelope["choices"]![0]!;
    const rawMessage = taskJsonRecord(choice) ? choice["message"] : undefined;
    if (!taskJsonRecord(choice) || choice["finish_reason"] !== "stop" || rawMessage === undefined || !taskJsonRecord(rawMessage) || typeof rawMessage["content"] !== "string")
        return yield* Either.left(callError("model finish_reason must be stop"));
    const message = choice["message"] as Readonly<Record<string, TaskJson>>;
    const payload = yield* decodeNativeTaskJson(new TextEncoder().encode(message["content"] as string)).pipe(Either.mapLeft(() => callError("model transport failed without retry: JSONDecodeError")));
    const usage = envelope["usage"];
    if (!taskJsonRecord(payload))
        return yield* Either.left(callError("model content must be one JSON object"));
    if (usage === undefined || !taskJsonRecord(usage) || integer(usage["prompt_tokens"]) === undefined || integer(usage["completion_tokens"]) === undefined)
        return yield* Either.left(callError("model transport failed without retry: malformed usage"));
    return Object.freeze({ payload, model: envelope["model"], input_tokens: integer(usage["prompt_tokens"])!, output_tokens: integer(usage["completion_tokens"])! });
});
/** Creates the existing NativeProm9ModelPort service; call receipts remain owned by its caller. */
export const makeNativeProm9OpenAiCompatibleModelPort = (configuration: NativeProm9JsonTransportConfiguration): Effect.Effect<NativeProm9ModelPortShape, NativeProm9CallError, NativeProm9JsonHttp | NativeProm9JsonEnvironment> => Effect.gen(function* () {
    const captured = yield* Either.match(captureNativeProm9OpenAiCompatibleTransportConfiguration(configuration), { onLeft: error => Effect.fail(callError(error.detail)), onRight: Effect.succeed });
    const http = yield* NativeProm9JsonHttp;
    const environment = yield* NativeProm9JsonEnvironment;
    return Object.freeze({ invoke: (call: Readonly<Record<string, TaskJson>>) => Effect.gen(function* () {
            const capturedCall = yield* Either.match(captureNativeProm9JsonCall(call), { onLeft: error => Effect.fail(callError(error.detail)), onRight: Effect.succeed });
            const apiKey = captured.apiKeyEnvironment === null ? undefined : yield* environment.read(captured.apiKeyEnvironment).pipe(Effect.mapError(() => callError("API key environment read failed")));
            const request = yield* Either.match(prepareNativeProm9OpenAiCompatibleRequest(captured, capturedCall, apiKey), { onLeft: error => Effect.fail(callError(error.detail)), onRight: Effect.succeed });
            const started = yield* Effect.clockWith(clock => clock.currentTimeNanos);
            const response = yield* http.post(request).pipe(Effect.mapError(() => callError("model transport failed without retry")));
            if (!response || !Number.isInteger(response.status) || response.status < 200 || response.status > 299)
                return yield* Effect.fail(callError(`model transport failed without retry: HTTP_${response?.status}`));
            if (!(response.body instanceof Uint8Array) || response.body.byteLength > MAX_RESPONSE_BYTES)
                return yield* Effect.fail(callError("model transport failed without retry: malformed response body"));
            const decoded = yield* Either.match(parse(response.body), { onLeft: Effect.fail, onRight: Effect.succeed });
            if (decoded["model"] !== capturedCall["model"])
                return yield* Effect.fail(callError("served model identity drifted"));
            const ended = yield* Effect.clockWith(clock => clock.currentTimeNanos);
            return Object.freeze({ payload: decoded["payload"]!, model: capturedCall["model"]!, model_revision: capturedCall["model_revision"]!, input_tokens: decoded["input_tokens"]!, output_tokens: decoded["output_tokens"]!, latency_ms: Number((ended - started) / 1000000n), retries: 0, cache_status: "provider-unknown" });
        }) });
});
/** Supply this layer to `runNativeProm9Item` for the source-compatible one-shot transport. */
export const nativeProm9OpenAiCompatibleModelPortLayer = (configuration: NativeProm9JsonTransportConfiguration) => Layer.effect(NativeProm9ModelPort, makeNativeProm9OpenAiCompatibleModelPort(configuration));
export const configureNativeProm9OpenAiCompatibleModelPort = (endpoint: unknown, apiKeyEnvironment: unknown = null, timeoutMilliseconds: unknown = 180000, maxRetries: unknown = 0) => configureNativeProm9OpenAiCompatibleTransport(endpoint, apiKeyEnvironment, timeoutMilliseconds, maxRetries);
