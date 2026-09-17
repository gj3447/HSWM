/**
 * Durable cache/budget orchestration boundary for F3 chat.
 *
 * The persistence port is intentionally transport-agnostic.  A production
 * implementation must make acquire atomic in its durable database; this file
 * neither selects a database nor provides an in-memory authority.
 */
import { Context, Data, Effect, Either } from "effect";
import { type NativeF3ChatTransportRequest } from "./native-f3-chat-runtime.js";
import { NativeF3ChatError, nativeF3ChatRequestIdentity, nativeF3DecodeCachedMeta, nativeF3DecodeChatState, nativeF3ExtractOpenAiMeta, type NativeF3CachedMeta, type NativeF3ChatIdentity, type NativeF3ChatRequest, type NativeF3ChatState, type NativeF3OpenAiMeta } from "./native-f3-chat-domain.js";

export class NativeF3CachePersistenceError extends Data.TaggedError("NativeF3CachePersistenceError")<{
    readonly operation: "ACQUIRE" | "COMPLETE" | "FAIL_KNOWN";
    readonly detail: string;
}> {
}
export type NativeF3CacheReservation = Readonly<{ readonly reservationId: string }>;
export type NativeF3CacheAcquire = Readonly<{
    readonly terminal: "CACHE_HIT";
    /** The persisted state is after its atomic hit-counter increment. */
    readonly state: NativeF3ChatState;
    /** Source-shaped document: { response_meta: ... }, without cached=true. */
    readonly document: unknown;
}> | Readonly<{
    readonly terminal: "MISS_RESERVED";
    /** The persisted state is after its atomic shared-budget/miss increment. */
    readonly state: NativeF3ChatState;
    readonly reservation: NativeF3CacheReservation;
}> | Readonly<{
    readonly terminal: "BUDGET_EXHAUSTED" | "UNRESOLVED_DISPATCH" | "CACHE_CORRUPT";
    readonly state: NativeF3ChatState;
    readonly detail: string;
}>;
export interface NativeF3CachePersistenceShape {
    /**
     * Must inspect a completed cache document before consuming budget.  The
     * cache-hit/miss transition and returned state are one durable operation.
     */
    readonly acquire: (input: Readonly<{ readonly clientId: string; readonly identity: NativeF3ChatIdentity }>) => Effect.Effect<NativeF3CacheAcquire, NativeF3CachePersistenceError>;
    /** Atomically publish the source-shaped document and close the reservation. */
    readonly complete: (input: Readonly<{ readonly reservation: NativeF3CacheReservation; readonly identity: NativeF3ChatIdentity; readonly document: Readonly<{ readonly response_meta: NativeF3OpenAiMeta }> }>) => Effect.Effect<void, NativeF3CachePersistenceError>;
    /** Retains a consumed miss after a known provider/schema failure. */
    readonly failKnown: (input: Readonly<{ readonly reservation: NativeF3CacheReservation; readonly terminal: "TRANSPORT_ERROR" | "RESPONSE_SCHEMA_ERROR"; readonly delivery: "NOT_SENT" | "RESPONSE_RECEIVED"; readonly detail: string }>) => Effect.Effect<void, NativeF3CachePersistenceError>;
}
export class NativeF3CachePersistence extends Context.Tag("hswm/NativeF3CachePersistence")<NativeF3CachePersistence, NativeF3CachePersistenceShape>() {
}
export class NativeF3CacheProviderError extends Data.TaggedError("NativeF3CacheProviderError")<{
    /** NOT_SENT is required before a reservation may be closed after transport failure. */
    readonly delivery: "NOT_SENT" | "UNKNOWN_DELIVERY";
    readonly detail: string;
}> {
}
export interface NativeF3CacheProviderShape {
    readonly post: (request: NativeF3ChatTransportRequest) => Effect.Effect<unknown, NativeF3CacheProviderError>;
}
export class NativeF3CacheProvider extends Context.Tag("hswm/NativeF3CacheProvider")<NativeF3CacheProvider, NativeF3CacheProviderShape>() {
}
export type NativeF3PersistentChatExecution = Readonly<{
    readonly terminal: "CACHE_HIT";
    readonly identity: NativeF3ChatIdentity;
    readonly state: NativeF3ChatState;
    readonly meta: NativeF3CachedMeta & Readonly<{ readonly cached: true }>;
}> | Readonly<{
    readonly terminal: "COMPLETED";
    readonly identity: NativeF3ChatIdentity;
    readonly state: NativeF3ChatState;
    readonly meta: NativeF3OpenAiMeta & Readonly<{ readonly cached: false }>;
}> | Readonly<{
    readonly terminal: "BUDGET_EXHAUSTED" | "CACHE_READ_ERROR" | "TRANSPORT_ERROR" | "TRANSPORT_UNCERTAIN" | "RESPONSE_SCHEMA_ERROR" | "CACHE_WRITE_ERROR" | "UNRESOLVED_DISPATCH";
    readonly identity: NativeF3ChatIdentity;
    readonly state: NativeF3ChatState;
    readonly detail: string;
}> | Readonly<{
    /** Persistence did not provide a trustworthy state observation. */
    readonly terminal: "PERSISTENCE_ERROR";
    readonly identity: NativeF3ChatIdentity;
    readonly state: null;
    readonly detail: string;
}>;
type StateTerminal = Exclude<Extract<NativeF3PersistentChatExecution, Readonly<{ readonly detail: string }>>["terminal"], "PERSISTENCE_ERROR">;
const terminal = (identity: NativeF3ChatIdentity, state: NativeF3ChatState, kind: StateTerminal, detail: string): NativeF3PersistentChatExecution => Object.freeze({ terminal: kind, identity, state, detail });
const persistenceError = (identity: NativeF3ChatIdentity, detail: string): NativeF3PersistentChatExecution => Object.freeze({ terminal: "PERSISTENCE_ERROR", identity, state: null, detail });
const sourceMeta = <A extends Readonly<Record<string, unknown>>>(meta: A, cached: boolean): A & Readonly<{ readonly cached: boolean }> => Object.freeze({ ...meta, cached });
const lift = <A>(value: Either.Either<A, NativeF3ChatError>): Effect.Effect<A, NativeF3ChatError> => Either.isLeft(value) ? Effect.fail(value.left) : Effect.succeed(value.right);
const validClientId = (value: string): boolean => value.length > 0 && value.length <= 256 && !value.includes("\u0000");
const persistedState = (identity: NativeF3ChatIdentity, input: unknown): NativeF3PersistentChatExecution | NativeF3ChatState => {
    const decoded = nativeF3DecodeChatState(input);
    return Either.isRight(decoded) ? decoded.right : persistenceError(identity, "persistence returned an invalid counter state");
};
const settleKnown = (persistence: NativeF3CachePersistenceShape, reservation: NativeF3CacheReservation, kind: "TRANSPORT_ERROR" | "RESPONSE_SCHEMA_ERROR", identity: NativeF3ChatIdentity, state: NativeF3ChatState, detail: string): Effect.Effect<NativeF3PersistentChatExecution, never> => persistence.failKnown(Object.freeze({ reservation, terminal: kind, delivery: kind === "TRANSPORT_ERROR" ? "NOT_SENT" : "RESPONSE_RECEIVED", detail })).pipe(Effect.either, Effect.map((settled) => Either.isLeft(settled) ? persistenceError(identity, settled.left.detail) : terminal(identity, state, kind, detail)));

/**
 * Composes the source-bound identity/meta decoder with a durable reservation
 * port.  It deliberately does not retry or resolve a prior ambiguous dispatch.
 */
export const executeNativeF3PersistentChat = (request: NativeF3ChatRequest, clientId: string, timeoutSeconds = 240): Effect.Effect<NativeF3PersistentChatExecution, NativeF3ChatError, NativeF3CachePersistence | NativeF3CacheProvider> => Effect.gen(function* () {
    const identity = yield* lift(nativeF3ChatRequestIdentity(request));
    if (!validClientId(clientId) || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0)
        return yield* lift(Either.left(new NativeF3ChatError({ reason: "INPUT_INVALID", detail: "clientId and timeoutSeconds must be valid" })));
    const persistence = yield* NativeF3CachePersistence;
    const acquired = yield* Effect.either(persistence.acquire(Object.freeze({ clientId, identity })));
    if (Either.isLeft(acquired))
        return persistenceError(identity, acquired.left.detail);
    const state = persistedState(identity, acquired.right.state);
    if ("terminal" in state)
        return state;
    if (acquired.right.terminal === "BUDGET_EXHAUSTED")
        return terminal(identity, state, "BUDGET_EXHAUSTED", acquired.right.detail);
    if (acquired.right.terminal === "UNRESOLVED_DISPATCH")
        return terminal(identity, state, "UNRESOLVED_DISPATCH", acquired.right.detail);
    if (acquired.right.terminal === "CACHE_CORRUPT")
        return terminal(identity, state, "CACHE_READ_ERROR", acquired.right.detail);
    if (acquired.right.terminal === "CACHE_HIT") {
        const meta = nativeF3DecodeCachedMeta(acquired.right.document);
        return Either.isLeft(meta)
            ? persistenceError(identity, "persistence classified an invalid document as a cache hit")
            : Object.freeze({ terminal: "CACHE_HIT", identity, state, meta: sourceMeta(meta.right, true) as NativeF3CachedMeta & Readonly<{ readonly cached: true }> });
    }
    if (acquired.right.terminal !== "MISS_RESERVED")
        return persistenceError(identity, "persistence returned an unsupported acquire terminal");
    const reservation = acquired.right.reservation;
    const provider = yield* NativeF3CacheProvider;
    const posted = yield* Effect.either(provider.post(Object.freeze({ url: `${identity.endpoint}/chat/completions`, bodyUtf8: identity.transportBody, timeoutSeconds })));
    if (Either.isLeft(posted))
        return posted.left.delivery === "NOT_SENT"
            ? yield* settleKnown(persistence, reservation, "TRANSPORT_ERROR", identity, state, posted.left.detail)
            : terminal(identity, state, "TRANSPORT_UNCERTAIN", posted.left.detail);
    const meta = nativeF3ExtractOpenAiMeta(posted.right, identity.requestSha256);
    if (Either.isLeft(meta))
        return yield* settleKnown(persistence, reservation, "RESPONSE_SCHEMA_ERROR", identity, state, meta.left.detail);
    const completed = yield* Effect.either(persistence.complete(Object.freeze({ reservation, identity, document: Object.freeze({ response_meta: meta.right }) })));
    return Either.isLeft(completed)
        ? terminal(identity, state, "CACHE_WRITE_ERROR", completed.left.detail)
        : Object.freeze({ terminal: "COMPLETED", identity, state, meta: sourceMeta(meta.right, false) as NativeF3OpenAiMeta & Readonly<{ readonly cached: false }> });
});
/** Factory form lets a PG layer compose the same orchestration without globals. */
export const makeNativeF3PersistentChat = (persistence: NativeF3CachePersistenceShape, provider: NativeF3CacheProviderShape) => (request: NativeF3ChatRequest, clientId: string, timeoutSeconds = 240) => executeNativeF3PersistentChat(request, clientId, timeoutSeconds).pipe(Effect.provideService(NativeF3CachePersistence, persistence), Effect.provideService(NativeF3CacheProvider, provider));
