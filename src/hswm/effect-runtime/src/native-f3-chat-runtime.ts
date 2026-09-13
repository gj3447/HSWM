/** Injected cache and transport orchestration for the source-bound F3v2 chat seam. */
import { Context, Data, Effect, Either } from "effect";
import { NativeF3ChatError, nativeF3ChatCacheTransition, nativeF3ChatRequestIdentity, nativeF3DecodeCachedMeta, nativeF3DecodeChatState, nativeF3ExtractOpenAiMeta, type NativeF3CachedMeta, type NativeF3ChatIdentity, type NativeF3ChatRequest, type NativeF3ChatState, type NativeF3OpenAiMeta } from "./native-f3-chat-domain.js";
export class NativeF3ChatIoError extends Data.TaggedError("NativeF3ChatIoError")<{
    readonly operation: "CACHE_READ" | "TRANSPORT" | "CACHE_WRITE";
    readonly detail: string;
}> {
}
export type NativeF3ChatTransportRequest = Readonly<{
    readonly url: string;
    readonly bodyUtf8: string;
    readonly timeoutSeconds: number;
}>;
export interface NativeF3ChatIoShape {
    readonly read: (identity: NativeF3ChatIdentity) => Effect.Effect<unknown | undefined, NativeF3ChatIoError>;
    readonly post: (request: NativeF3ChatTransportRequest) => Effect.Effect<unknown, NativeF3ChatIoError>;
    readonly write: (identity: NativeF3ChatIdentity, document: Readonly<{
        readonly response_meta: NativeF3OpenAiMeta;
    }>) => Effect.Effect<void, NativeF3ChatIoError>;
}
export class NativeF3ChatIo extends Context.Tag("hswm/NativeF3ChatIo")<NativeF3ChatIo, NativeF3ChatIoShape>() {
}
export type NativeF3ChatExecution = Readonly<{
    readonly terminal: "CACHE_HIT";
    readonly identity: NativeF3ChatIdentity;
    readonly state: NativeF3ChatState;
    readonly meta: NativeF3CachedMeta & Readonly<{
        readonly cached: true;
    }>;
}> | Readonly<{
    readonly terminal: "COMPLETED";
    readonly identity: NativeF3ChatIdentity;
    readonly state: NativeF3ChatState;
    readonly meta: NativeF3OpenAiMeta & Readonly<{
        readonly cached: false;
    }>;
}> | Readonly<{
    readonly terminal: "CACHE_READ_ERROR" | "BUDGET_EXHAUSTED" | "TRANSPORT_ERROR" | "RESPONSE_SCHEMA_ERROR" | "CACHE_WRITE_ERROR" | "COUNTER_OVERFLOW";
    readonly identity: NativeF3ChatIdentity;
    readonly state: NativeF3ChatState;
    readonly detail: string;
}>;
const lift = <A>(value: Either.Either<A, NativeF3ChatError>): Effect.Effect<A, NativeF3ChatError> => Either.isLeft(value) ? Effect.fail(value.left) : Effect.succeed(value.right);
const terminal = (identity: NativeF3ChatIdentity, state: NativeF3ChatState, kind: Extract<NativeF3ChatExecution, Readonly<{
    readonly detail: string;
}>>["terminal"], detail: string): NativeF3ChatExecution => Object.freeze({ terminal: kind, identity, state, detail });
const sourceMeta = <A extends Readonly<Record<string, unknown>>>(meta: A, cached: boolean): A & Readonly<{
    readonly cached: boolean;
}> => Object.freeze({ ...meta, cached });
const transition = (identity: NativeF3ChatIdentity, state: NativeF3ChatState, cache: "HIT" | "MISS"): NativeF3ChatExecution | Readonly<{
    readonly state: NativeF3ChatState;
}> => {
    const next = nativeF3ChatCacheTransition(state, cache);
    if (Either.isRight(next))
        return Object.freeze({ state: next.right.state });
    return terminal(identity, state, next.left.reason === "BUDGET_EXHAUSTED" ? "BUDGET_EXHAUSTED" : "COUNTER_OVERFLOW", next.left.detail);
};
const state = nativeF3DecodeChatState;
/** Mirrors CachedOpenAIChat.chat ordering; miss budget remains consumed on later failures. */
export const executeNativeF3Chat = (request: NativeF3ChatRequest, stateInput: unknown, timeoutSeconds = 240): Effect.Effect<NativeF3ChatExecution, NativeF3ChatError, NativeF3ChatIo> => Effect.gen(function* () {
    const identity = yield* lift(nativeF3ChatRequestIdentity(request)), initial = yield* lift(state(stateInput));
    if (typeof timeoutSeconds !== "number" || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0)
        return yield* lift(Either.left(new NativeF3ChatError({ reason: "INPUT_INVALID", detail: "timeoutSeconds must be finite and positive" })));
    const io = yield* NativeF3ChatIo;
    const read = yield* Effect.either(io.read(identity));
    if (Either.isLeft(read))
        return terminal(identity, initial, "CACHE_READ_ERROR", read.left.detail);
    if (read.right !== undefined) {
        const cached = nativeF3DecodeCachedMeta(read.right);
        if (Either.isLeft(cached))
            return terminal(identity, initial, "CACHE_READ_ERROR", cached.left.detail);
        const hit = transition(identity, initial, "HIT");
        if ("terminal" in hit)
            return hit;
        return Object.freeze({ terminal: "CACHE_HIT", identity, state: hit.state, meta: sourceMeta(cached.right, true) as NativeF3CachedMeta & Readonly<{
                readonly cached: true;
            }> });
    }
    const miss = transition(identity, initial, "MISS");
    if ("terminal" in miss)
        return miss;
    const posted = yield* Effect.either(io.post(Object.freeze({ url: `${identity.endpoint}/chat/completions`, bodyUtf8: identity.transportBody, timeoutSeconds })));
    if (Either.isLeft(posted))
        return terminal(identity, miss.state, "TRANSPORT_ERROR", posted.left.detail);
    const meta = nativeF3ExtractOpenAiMeta(posted.right, identity.requestSha256);
    if (Either.isLeft(meta))
        return terminal(identity, miss.state, "RESPONSE_SCHEMA_ERROR", meta.left.detail);
    const written = yield* Effect.either(io.write(identity, Object.freeze({ response_meta: meta.right })));
    if (Either.isLeft(written))
        return terminal(identity, miss.state, "CACHE_WRITE_ERROR", written.left.detail);
    return Object.freeze({ terminal: "COMPLETED", identity, state: miss.state, meta: sourceMeta(meta.right, false) as NativeF3OpenAiMeta & Readonly<{
            readonly cached: false;
        }> });
});
