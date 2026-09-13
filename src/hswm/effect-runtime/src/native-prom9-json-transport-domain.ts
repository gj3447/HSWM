/** Source-matched OpenAI-compatible request construction. Secrets stay outside this value. */
import { Data, Either } from "effect";
import { canonicalNativeProm9Json, nativeProm9OutputSchema } from "./native-prom9-ports-domain.js";
import { isTaskNumber, snapshotNativeTaskJson, taskJsonRecord, taskNumberIsFloat, taskNumberValue, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export class NativeProm9JsonTransportError extends Data.TaggedError("NativeProm9JsonTransportError")<{
    readonly detail: string;
}> {
}
export type NativeProm9JsonTransportConfiguration = Readonly<{
    readonly endpoint: string;
    readonly apiKeyEnvironment: string | null;
    readonly timeoutMilliseconds: number;
}>;
export type NativeProm9JsonTransportRequest = Readonly<{
    readonly url: string;
    readonly headers: Readonly<Record<string, string>>;
    readonly body: Uint8Array;
    readonly timeoutMilliseconds: number;
}>;
const fail = (detail: string): Either.Either<never, NativeProm9JsonTransportError> => Either.left(new NativeProm9JsonTransportError({ detail }));
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128)
            return false;
        if (value === null || typeof value !== "object")
            return true;
        return Reflect.ownKeys(value).every(key => { const descriptor = Object.getOwnPropertyDescriptor(value, key); return descriptor !== undefined && Object.hasOwn(descriptor, "value") && dataOnly(descriptor.value, depth + 1); });
    }
    catch {
        return false;
    }
};
const integer = (value: TaskJson | undefined): number | undefined => {
    if (value === undefined || !isTaskNumber(value) || taskNumberIsFloat(value))
        return undefined;
    const number = taskNumberValue(value);
    return typeof number === "number" && Number.isSafeInteger(number) ? number : typeof number === "bigint" && number <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(number) : undefined;
};
/** This accepts configuration only; its inspectable result cannot contain an API key. */
export const configureNativeProm9OpenAiCompatibleTransport = (endpoint: unknown, apiKeyEnvironment: unknown = null, timeoutMilliseconds: unknown = 180000, maxRetries: unknown = 0): Either.Either<NativeProm9JsonTransportConfiguration, NativeProm9JsonTransportError> => {
    if (typeof endpoint !== "string" || !(endpoint.startsWith("http://") || endpoint.startsWith("https://")))
        return fail("endpoint must be HTTP(S)");
    if (apiKeyEnvironment !== null && (typeof apiKeyEnvironment !== "string" || apiKeyEnvironment === ""))
        return fail("API key environment name is invalid");
    if (typeof timeoutMilliseconds !== "number" || !Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds < 1)
        return fail("timeout must be a positive integer");
    if (maxRetries !== 0)
        return fail("automatic POST retries are forbidden without a durable result spool");
    return Either.right(Object.freeze({ endpoint, apiKeyEnvironment, timeoutMilliseconds }));
};
/** Re-captures even a nominal configuration supplied across an untrusted boundary. */
export const captureNativeProm9OpenAiCompatibleTransportConfiguration = (value: unknown): Either.Either<NativeProm9JsonTransportConfiguration, NativeProm9JsonTransportError> => {
    if (!dataOnly(value) || !validNativeTaskJson(value) || !taskJsonRecord(value) || Object.keys(value).length !== 3 || !Object.hasOwn(value, "endpoint") || !Object.hasOwn(value, "apiKeyEnvironment") || !Object.hasOwn(value, "timeoutMilliseconds"))
        return fail("transport configuration is invalid");
    return configureNativeProm9OpenAiCompatibleTransport(value["endpoint"], value["apiKeyEnvironment"], value["timeoutMilliseconds"]);
};
/** Data snapshot before any injected environment or transport callback. */
export const captureNativeProm9JsonCall = (call: unknown): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9JsonTransportError> => {
    if (!dataOnly(call) || !validNativeTaskJson(call) || !taskJsonRecord(call))
        return fail("model call is invalid");
    return Either.right(snapshotNativeTaskJson(call) as Readonly<Record<string, TaskJson>>);
};
/** Byte-exact canonical JSON request body from the original one-shot Python port. */
export const prepareNativeProm9OpenAiCompatibleRequest = (configuration: NativeProm9JsonTransportConfiguration, call: unknown, apiKey: unknown): Either.Either<NativeProm9JsonTransportRequest, NativeProm9JsonTransportError> => Either.gen(function* () {
    const checkedConfiguration = yield* captureNativeProm9OpenAiCompatibleTransportConfiguration(configuration);
    const captured = yield* captureNativeProm9JsonCall(call);
    const model = captured["model"], prompt = captured["system_prompt"], input = captured["input_payload"], outputType = captured["output_type"], maxTokens = integer(captured["max_output_tokens"]);
    if (typeof model !== "string" || typeof prompt !== "string" || input === undefined || !taskJsonRecord(input) || typeof outputType !== "string" || maxTokens === undefined || maxTokens < 1)
        return yield* fail("model call is invalid");
    if (checkedConfiguration.apiKeyEnvironment !== null && (typeof apiKey !== "string" || apiKey === ""))
        return yield* fail(`missing API key environment: ${checkedConfiguration.apiKeyEnvironment}`);
    const schema = yield* nativeProm9OutputSchema(outputType).pipe(Either.mapLeft(error => new NativeProm9JsonTransportError({ detail: error.detail })));
    const user = yield* canonicalNativeProm9Json(input!).pipe(Either.mapLeft(error => new NativeProm9JsonTransportError({ detail: error.detail })));
    const body = yield* canonicalNativeProm9Json(Object.freeze({ model, messages: Object.freeze([Object.freeze({ role: "system", content: prompt }), Object.freeze({ role: "user", content: user })]), temperature: 0, top_p: 1, max_tokens: maxTokens, response_format: Object.freeze({ type: "json_schema", json_schema: Object.freeze({ name: outputType, strict: true, schema }) }), chat_template_kwargs: Object.freeze({ enable_thinking: false }) })).pipe(Either.mapLeft(error => new NativeProm9JsonTransportError({ detail: error.detail })));
    return Object.freeze({ url: checkedConfiguration.endpoint, headers: Object.freeze({ "Content-Type": "application/json", ...(checkedConfiguration.apiKeyEnvironment === null ? {} : { Authorization: `Bearer ${apiKey}` }) }), body: new TextEncoder().encode(body), timeoutMilliseconds: checkedConfiguration.timeoutMilliseconds });
});
