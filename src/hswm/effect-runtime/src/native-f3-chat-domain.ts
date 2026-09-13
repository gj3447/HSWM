/** Source-bound cache identity and miss-only budget transition for F3v2 chat. */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
export const NATIVE_F3_CHAT_SOURCE_SHA256 = "1cf1518cf0cd9172b560c662b52c4261bc3cdcb57e7a6c8e34b80c7c55f58691" as const;
export const NATIVE_F3_RUN_EXPERIENCE_SOURCE_SHA256 = "19848eb4d3b7f6377d28793324652f4a45631dc74f16ba91b7d5e3636d991915" as const;
export class NativeF3ChatError extends Data.TaggedError("NativeF3ChatError")<{
    readonly reason: "INPUT_INVALID" | "BUDGET_EXHAUSTED";
    readonly detail: string;
}> {
}
export type NativeF3ChatRequest = Readonly<{
    readonly endpoint: string;
    readonly model: string;
    readonly system: string;
    readonly user: string;
    readonly seed: number;
    readonly maxTokens: number;
}>;
export type NativeF3ChatIdentity = Readonly<{
    readonly endpoint: string;
    readonly requestBody: string;
    readonly transportBody: string;
    readonly requestSha256: string;
    readonly cacheFilename: string;
}>;
export type NativeF3ChatState = Readonly<{
    readonly maxCalls: number;
    readonly used: number;
    readonly hits: number;
    readonly misses: number;
}>;
export type NativeF3CachePresence = "HIT" | "MISS";
export type NativeF3ChatTransition = Readonly<{
    readonly cache: NativeF3CachePresence;
    readonly state: NativeF3ChatState;
}>;
export interface NativeF3JsonArray extends ReadonlyArray<NativeF3Json> {
}
export interface NativeF3JsonObject {
    readonly [key: string]: NativeF3Json;
}
export type NativeF3Json = null | boolean | number | string | NativeF3JsonArray | NativeF3JsonObject;
export type NativeF3CachedMeta = Readonly<Record<string, NativeF3Json>>;
export type NativeF3OpenAiMeta = Readonly<{
    readonly text: NativeF3Json;
    readonly finish_reason: NativeF3Json;
    readonly response_model: NativeF3Json;
    readonly usage: Readonly<{
        readonly prompt_tokens: NativeF3Json;
        readonly completion_tokens: NativeF3Json;
    }>;
    readonly request_sha256: string;
}>;
const fail = (reason: NativeF3ChatError["reason"], detail: string): Either.Either<never, NativeF3ChatError> => Either.left(new NativeF3ChatError({ reason, detail }));
const ownData = (value: unknown, names: readonly string[]): value is Readonly<Record<string, unknown>> => {
    if (typeof value !== "object" || value === null || Array.isArray(value))
        return false;
    try {
        const descriptors = Object.getOwnPropertyDescriptors(value);
        return Reflect.ownKeys(descriptors).length === names.length && names.every(name => {
            const descriptor = descriptors[name];
            return descriptor !== undefined && descriptor.get === undefined && descriptor.set === undefined && Object.hasOwn(descriptors, name);
        });
    }
    catch {
        return false;
    }
};
const validText = (value: unknown): value is string => typeof value === "string" && value.length <= 1000000 && !value.includes("\u0000");
const natural = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const pythonString = (value: string): string => {
    let encoded = '"';
    for (let index = 0; index < value.length; index += 1) {
        const code = value.charCodeAt(index);
        if (code === 34)
            encoded += '\\"';
        else if (code === 92)
            encoded += "\\\\";
        else if (code === 8)
            encoded += "\\b";
        else if (code === 9)
            encoded += "\\t";
        else if (code === 10)
            encoded += "\\n";
        else if (code === 12)
            encoded += "\\f";
        else if (code === 13)
            encoded += "\\r";
        else if (code < 32 || code > 126)
            encoded += `\\u${code.toString(16).padStart(4, "0")}`;
        else
            encoded += String.fromCharCode(code);
    }
    return `${encoded}\"`;
};
const normalizedEndpoint = (endpoint: string): string => endpoint.replace(/\/+$/u, "");
const json = (value: unknown, depth = 0): value is NativeF3Json => {
    if (depth > 128)
        return false;
    if (value === null || typeof value === "boolean" || typeof value === "string")
        return true;
    if (typeof value === "number")
        return Number.isFinite(value);
    if (typeof value !== "object")
        return false;
    try {
        if (Array.isArray(value)) {
            if (Object.getPrototypeOf(value) !== Array.prototype)
                return false;
            const descriptors = Object.getOwnPropertyDescriptors(value), length = value.length, lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
            if (Reflect.ownKeys(descriptors).length !== length + 1 || lengthDescriptor?.value !== length)
                return false;
            for (let index = 0; index < length; index += 1) {
                const descriptor = descriptors[String(index)];
                if (descriptor === undefined || descriptor.get !== undefined || descriptor.set !== undefined || !json(descriptor.value, depth + 1))
                    return false;
            }
            return true;
        }
        if (Object.getPrototypeOf(value) !== Object.prototype)
            return false;
        return Reflect.ownKeys(Object.getOwnPropertyDescriptors(value)).every(key => {
            if (typeof key !== "string")
                return false;
            const descriptor = Object.getOwnPropertyDescriptor(value, key);
            return descriptor !== undefined && descriptor.enumerable && descriptor.get === undefined && descriptor.set === undefined && json(descriptor.value, depth + 1);
        });
    }
    catch {
        return false;
    }
};
const dataRecord = (value: unknown): value is Readonly<Record<string, NativeF3Json>> => typeof value === "object" && value !== null && !Array.isArray(value) && json(value);
const frozenJson = (value: NativeF3Json): NativeF3Json => Array.isArray(value) ? Object.freeze(value.map(frozenJson)) : value !== null && typeof value === "object" ? Object.freeze(Object.fromEntries(Object.entries(value).map(([key, item]) => [key, frozenJson(item)]))) : value;
const nullable = (value: unknown): NativeF3Json => value === undefined ? null : json(value) ? frozenJson(value) : null;
/**
 * This accepts the source's ordinary scalar call shape and deliberately refuses
 * hostile values (getters, NUL text, non-safe integers) the Python harness did
 * not validate at its untyped boundary.
 */
const decodeRequest = (input: unknown): Either.Either<NativeF3ChatRequest, NativeF3ChatError> => {
    if (!ownData(input, ["endpoint", "model", "system", "user", "seed", "maxTokens"]) || !validText(input["endpoint"]) || input["endpoint"] === "" || !validText(input["model"]) || input["model"] === "" || !validText(input["system"]) || !validText(input["user"]) || !natural(input["seed"]) || !natural(input["maxTokens"]) || input["maxTokens"] < 1)
        return fail("INPUT_INVALID", "request must contain ordinary source-compatible scalar values");
    return Either.right(Object.freeze({ endpoint: input["endpoint"], model: input["model"], system: input["system"], user: input["user"], seed: input["seed"], maxTokens: input["maxTokens"] }));
};
export const nativeF3ChatRequestIdentity = (input: unknown): Either.Either<NativeF3ChatIdentity, NativeF3ChatError> => Either.gen(function* () {
    const request = yield* decodeRequest(input), endpoint = normalizedEndpoint(request.endpoint);
    const body = `{${pythonString("chat_template_kwargs")}: {${pythonString("enable_thinking")}: false}, ${pythonString("max_tokens")}: ${request.maxTokens}, ${pythonString("messages")}: [{${pythonString("content")}: ${pythonString(request.system)}, ${pythonString("role")}: ${pythonString("system")}}, {${pythonString("content")}: ${pythonString(request.user)}, ${pythonString("role")}: ${pythonString("user")}}], ${pythonString("model")}: ${pythonString(request.model)}, ${pythonString("response_format")}: {${pythonString("type")}: ${pythonString("json_object")}}, ${pythonString("seed")}: ${request.seed}, ${pythonString("temperature")}: 0, ${pythonString("top_p")}: 1.0}`;
    const identityJson = `{${pythonString("backend")}: ${pythonString("openai-compat-v1")}, ${pythonString("body")}: ${body}, ${pythonString("endpoint")}: ${pythonString(endpoint)}, ${pythonString("model")}: ${pythonString(request.model)}}`;
    const requestSha256 = createHash("sha256").update(identityJson, "utf8").digest("hex");
    const transportBody = `{${pythonString("model")}: ${pythonString(request.model)}, ${pythonString("messages")}: [{${pythonString("role")}: ${pythonString("system")}, ${pythonString("content")}: ${pythonString(request.system)}}, {${pythonString("role")}: ${pythonString("user")}, ${pythonString("content")}: ${pythonString(request.user)}}], ${pythonString("temperature")}: 0, ${pythonString("top_p")}: 1.0, ${pythonString("seed")}: ${request.seed}, ${pythonString("max_tokens")}: ${request.maxTokens}, ${pythonString("response_format")}: {${pythonString("type")}: ${pythonString("json_object")}}, ${pythonString("chat_template_kwargs")}: {${pythonString("enable_thinking")}: false}}`;
    return Object.freeze({ endpoint, requestBody: body, transportBody, requestSha256, cacheFilename: `${requestSha256}.json` });
});
export const nativeF3DecodeChatState = (input: unknown): Either.Either<NativeF3ChatState, NativeF3ChatError> => {
    if (!ownData(input, ["maxCalls", "used", "hits", "misses"]) || !natural(input["maxCalls"]) || !natural(input["used"]) || !natural(input["hits"]) || !natural(input["misses"]) || input["used"] > input["maxCalls"])
        return fail("INPUT_INVALID", "state must contain non-negative safe counters within its budget");
    return Either.right(Object.freeze({ maxCalls: input["maxCalls"], used: input["used"], hits: input["hits"], misses: input["misses"] }));
};
/** Mirrors CachedOpenAIChat.chat: lookup is resolved before Budget.take(). */
export const nativeF3ChatCacheTransition = (stateInput: unknown, cache: unknown): Either.Either<NativeF3ChatTransition, NativeF3ChatError> => Either.gen(function* () {
    const state = yield* nativeF3DecodeChatState(stateInput);
    if (cache !== "HIT" && cache !== "MISS")
        return yield* fail("INPUT_INVALID", "cache presence must be HIT or MISS");
    if (cache === "HIT") {
        if (state.hits === Number.MAX_SAFE_INTEGER)
            return yield* fail("INPUT_INVALID", "bounded native counter would overflow on cache hit");
        return Object.freeze({ cache, state: Object.freeze({ ...state, hits: state.hits + 1 }) });
    }
    if (state.used >= state.maxCalls)
        return yield* fail("BUDGET_EXHAUSTED", `LLM call budget ${state.maxCalls} exhausted`);
    if (state.used === Number.MAX_SAFE_INTEGER || state.misses === Number.MAX_SAFE_INTEGER)
        return yield* fail("INPUT_INVALID", "bounded native counter would overflow on cache miss");
    return Object.freeze({ cache, state: Object.freeze({ ...state, used: state.used + 1, misses: state.misses + 1 }) });
});
/** Matches `_cache_read`: a cache hit only requires a JSON object at response_meta. */
export const nativeF3DecodeCachedMeta = (document: unknown): Either.Either<NativeF3CachedMeta, NativeF3ChatError> => {
    if (!dataRecord(document) || !dataRecord(document["response_meta"]))
        return fail("INPUT_INVALID", "cache document has no object response_meta");
    return Either.right(frozenJson(document["response_meta"]) as NativeF3CachedMeta);
};
/** Matches the source's guarded OpenAI response extraction, including default token counts. */
export const nativeF3ExtractOpenAiMeta = (raw: unknown, requestSha256: unknown): Either.Either<NativeF3OpenAiMeta, NativeF3ChatError> => {
    if (typeof requestSha256 !== "string" || !/^[0-9a-f]{64}$/u.test(requestSha256))
        return fail("INPUT_INVALID", "request SHA-256 is invalid");
    if (!dataRecord(raw) || !Array.isArray(raw["choices"]))
        return fail("INPUT_INVALID", "OpenAI response schema mismatch");
    const choice = raw["choices"][0];
    if (!dataRecord(choice))
        return fail("INPUT_INVALID", "OpenAI response schema mismatch");
    const message = choice["message"], rawUsage = raw["usage"];
    const pythonTruthy = (value: NativeF3Json | undefined): boolean => value !== undefined && value !== null && value !== false && value !== 0 && value !== "" && (!Array.isArray(value) || value.length > 0) && (!(typeof value === "object" && !Array.isArray(value)) || Object.keys(value).length > 0);
    const usage = pythonTruthy(rawUsage) ? rawUsage : {};
    if (!dataRecord(message) || !dataRecord(usage) || !Object.hasOwn(message, "content"))
        return fail("INPUT_INVALID", "OpenAI response schema mismatch");
    const usageValue = (field: "prompt_tokens" | "completion_tokens"): NativeF3Json => Object.hasOwn(usage, field) ? nullable(usage[field]) : 0;
    return Either.right(Object.freeze({ text: nullable(message["content"]), finish_reason: nullable(choice["finish_reason"]), response_model: nullable(raw["model"]), usage: Object.freeze({ prompt_tokens: usageValue("prompt_tokens"), completion_tokens: usageValue("completion_tokens") }), request_sha256: requestSha256 }));
};
