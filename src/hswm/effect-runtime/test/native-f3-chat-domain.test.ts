import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { Effect, Either } from "effect";
import { expect, it } from "vitest";
import { NATIVE_F3_CHAT_SOURCE_SHA256, NATIVE_F3_RUN_EXPERIENCE_SOURCE_SHA256, nativeF3ChatCacheTransition, nativeF3ChatRequestIdentity, nativeF3DecodeCachedMeta, nativeF3ExtractOpenAiMeta } from "../src/native-f3-chat-domain.js";
import { NativeF3ChatIo, NativeF3ChatIoError, executeNativeF3Chat, type NativeF3ChatIoShape, type NativeF3ChatTransportRequest } from "../src/native-f3-chat-runtime.js";
type Identity = Readonly<{
    readonly name: string;
    readonly request: unknown;
    readonly request_sha256: string;
    readonly cache_filename: string;
    readonly endpoint_after_rstrip: string;
    readonly state_after_first_miss: unknown;
}>;
type Execution = Readonly<{
    readonly name: string;
    readonly events: readonly string[];
    readonly state: Readonly<{
        readonly budget_used: number;
        readonly hits: number;
        readonly misses: number;
    }>;
    readonly result: Readonly<{
        readonly meta?: Readonly<Record<string, unknown>>;
        readonly error_type?: string;
    }>;
}>;
type Fixture = Readonly<{
    readonly source_pins: Readonly<Record<string, string>>;
    readonly identities: readonly Identity[];
    readonly transitions: Readonly<{
        readonly miss_then_hit: Readonly<{
            readonly first: unknown;
            readonly second: unknown;
        }>;
        readonly exhausted_miss: Readonly<{
            readonly error: string;
            readonly state: unknown;
        }>;
    }>;
    readonly execution: readonly Execution[];
}>;
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/f3_chat_v1/original.v1.json", import.meta.url), "utf8")) as Fixture;
it("pins the active F3v2 injection seam and replays original cache identities", () => {
    expect(fixture.source_pins["_research/f_series/f2_delta_w_credit.py"]).toBe(NATIVE_F3_CHAT_SOURCE_SHA256);
    expect(fixture.source_pins["_research/f_series/f3v2_arms.py"]).toBe(NATIVE_F3_RUN_EXPERIENCE_SOURCE_SHA256);
    for (const [path, digest] of Object.entries(fixture.source_pins))
        expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex")).toBe(digest);
    for (const row of fixture.identities) {
        const identity = Either.getOrThrow(nativeF3ChatRequestIdentity(row.request));
        expect(identity.requestSha256, row.name).toBe(row.request_sha256);
        expect(identity.cacheFilename).toBe(row.cache_filename);
        expect(identity.endpoint).toBe(row.endpoint_after_rstrip);
        expect(Either.getOrThrow(nativeF3ChatCacheTransition({ maxCalls: 3, used: 0, hits: 0, misses: 0 }, "MISS")).state).toEqual(row.state_after_first_miss);
    }
});
it("takes budget only on a cache miss and preserves source exhaustion", () => {
    const first = Either.getOrThrow(nativeF3ChatCacheTransition({ maxCalls: 1, used: 0, hits: 0, misses: 0 }, "MISS"));
    expect(first).toEqual(fixture.transitions.miss_then_hit.first);
    const second = Either.getOrThrow(nativeF3ChatCacheTransition(first.state, "HIT"));
    expect(second).toEqual(fixture.transitions.miss_then_hit.second);
    const exhausted = nativeF3ChatCacheTransition(fixture.transitions.exhausted_miss.state, "MISS");
    expect(Either.isLeft(exhausted)).toBe(true);
    if (Either.isLeft(exhausted))
        expect(exhausted.left.detail).toBe(fixture.transitions.exhausted_miss.error);
});
it("refuses hostile input more strictly than the historical untyped boundary", () => {
    const getter = Object.defineProperty({ endpoint: "https://example.test", model: "m", system: "s", user: "u", seed: 0, maxTokens: 1 }, "model", { get: () => "m" });
    for (const input of [getter, { endpoint: "", model: "m", system: "s", user: "u", seed: 0, maxTokens: 1 }, { endpoint: "https://example.test", model: "m", system: "s", user: "u", seed: 0.5, maxTokens: 1 }])
        expect(Either.isLeft(nativeF3ChatRequestIdentity(input))).toBe(true);
});
it("accepts only dense descriptor-safe JSON snapshots at the injected boundary", () => {
    let getterReads = 0;
    const getter = Object.defineProperty({}, "response_meta", { enumerable: true, get: () => { getterReads += 1; return {}; } });
    const sparse: unknown[] = [];
    sparse[1] = { message: { content: "answer" } };
    const nested: Record<string, unknown> = {};
    let cursor = nested;
    for (let index = 0; index < 129; index += 1) {
        const next: Record<string, unknown> = {};
        cursor["next"] = next;
        cursor = next;
    }
    expect(Either.isLeft(nativeF3DecodeCachedMeta(getter))).toBe(true);
    expect(getterReads).toBe(0);
    for (const raw of [{ response_meta: new Date() }, { choices: sparse }, nested])
        expect(Either.isLeft(nativeF3ExtractOpenAiMeta(raw, "a".repeat(64)))).toBe(true);
});
it("orchestrates the real cache-read, miss-budget, transport, and cache-write order", async () => {
    const request = { endpoint: "https://example.test", model: "m", system: "s", user: "u", seed: 0, maxTokens: 1 };
    const events: string[] = [];
    const io: NativeF3ChatIoShape = { read: () => Effect.sync(() => { events.push("read"); return undefined; }), post: (value: NativeF3ChatTransportRequest) => Effect.sync(() => { events.push("post"); expect(value.url).toBe("https://example.test/chat/completions"); return { choices: [{ message: { content: "answer" }, finish_reason: "stop" }], model: "served", usage: { prompt_tokens: 7, completion_tokens: 3 } }; }), write: (_identity, document) => Effect.sync(() => { events.push("write"); expect(document.response_meta.usage).toEqual({ prompt_tokens: 7, completion_tokens: 3 }); }) };
    const completed = await Effect.runPromise(executeNativeF3Chat(request, { maxCalls: 1, used: 0, hits: 0, misses: 0 }).pipe(Effect.provideService(NativeF3ChatIo, io)));
    expect(events).toEqual(["read", "post", "write"]);
    expect(completed).toMatchObject({ terminal: "COMPLETED", state: { maxCalls: 1, used: 1, hits: 0, misses: 1 }, meta: { text: "answer", cached: false } });
});
it("preserves source terminal state across cache, transport, and cache-write failures", async () => {
    const request = { endpoint: "https://example.test", model: "m", system: "s", user: "u", seed: 0, maxTokens: 1 };
    const failure = (operation: "CACHE_READ" | "TRANSPORT" | "CACHE_WRITE") => new NativeF3ChatIoError({ operation, detail: operation.toLowerCase() });
    const run = (io: NativeF3ChatIoShape) => Effect.runPromise(executeNativeF3Chat(request, { maxCalls: 1, used: 0, hits: 0, misses: 0 }).pipe(Effect.provideService(NativeF3ChatIo, io)));
    const corrupt = await run({ read: () => Effect.succeed({ nope: true }), post: () => Effect.die("unreached"), write: () => Effect.die("unreached") });
    expect(corrupt).toMatchObject({ terminal: "CACHE_READ_ERROR", state: { used: 0, hits: 0, misses: 0 } });
    const transport = await run({ read: () => Effect.succeed(undefined), post: () => Effect.fail(failure("TRANSPORT")), write: () => Effect.die("unreached") });
    expect(transport).toMatchObject({ terminal: "TRANSPORT_ERROR", state: { used: 1, hits: 0, misses: 1 } });
    const write = await run({ read: () => Effect.succeed(undefined), post: () => Effect.succeed({ choices: [{ message: { content: "a" } }] }), write: () => Effect.fail(failure("CACHE_WRITE")) });
    expect(write).toMatchObject({ terminal: "CACHE_WRITE_ERROR", state: { used: 1, hits: 0, misses: 1 } });
    const hit = await run({ read: () => Effect.succeed({ response_meta: { response_model: "served" } }), post: () => Effect.die("unreached"), write: () => Effect.die("unreached") });
    expect(hit).toMatchObject({ terminal: "CACHE_HIT", state: { used: 0, hits: 1, misses: 0 }, meta: { response_model: "served", cached: true } });
});
it("replays every persisted source execution row through injected local effects", async () => {
    const request = { endpoint: "https://runtime.test", model: "m", system: "s", user: "u", seed: 0, maxTokens: 1 };
    const raw = (name: string): unknown => name === "miss" || name === "cache_write_error" || name === "transport_error" ? { choices: [{ message: { content: "answer" }, finish_reason: "stop" }], model: "served", usage: { prompt_tokens: 7, completion_tokens: 3 } } : { choices: [{ message: { content: "answer" } }], usage: name === "usage_null" ? null : name === "usage_false" ? false : name === "usage_empty_array" ? [] : { prompt_tokens: null, completion_tokens: null } };
    for (const row of fixture.execution) {
        const events: string[] = [];
        const io: NativeF3ChatIoShape = {
            read: () => Effect.sync(() => {
                events.push("read");
                if (row.name === "hit_without_content")
                    return { response_meta: { response_model: "served", cached: true } };
                if (row.name === "corrupt_cache")
                    return { no_response_meta: true };
                return undefined;
            }),
            post: () => row.name === "transport_error" ? Effect.sync(() => { events.push("transport"); }).pipe(Effect.zipRight(Effect.fail(new NativeF3ChatIoError({ operation: "TRANSPORT", detail: "down" })))) : Effect.sync(() => { events.push("transport"); return raw(row.name); }),
            write: () => row.name === "cache_write_error" ? Effect.sync(() => { events.push("write"); }).pipe(Effect.zipRight(Effect.fail(new NativeF3ChatIoError({ operation: "CACHE_WRITE", detail: "disk" })))) : Effect.sync(() => { events.push("write"); })
        };
        const actual = await Effect.runPromise(executeNativeF3Chat(request, { maxCalls: row.name === "exhausted_miss" ? 0 : 1, used: 0, hits: 0, misses: 0 }).pipe(Effect.provideService(NativeF3ChatIo, io)));
        expect(events, row.name).toEqual(row.events);
        expect(actual.state, row.name).toMatchObject({ used: row.state.budget_used, hits: row.state.hits, misses: row.state.misses });
        if (row.result.meta !== undefined && (actual.terminal === "CACHE_HIT" || actual.terminal === "COMPLETED"))
            expect(actual.meta, row.name).toMatchObject(row.result.meta);
        if (row.result.error_type !== undefined)
            expect(actual.terminal, row.name).toMatch(/ERROR|EXHAUSTED/);
    }
});
