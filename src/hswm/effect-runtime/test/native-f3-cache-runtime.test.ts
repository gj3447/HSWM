import { Effect } from "effect";
import { expect, it } from "vitest";
import { type NativeF3ChatTransportRequest } from "../src/native-f3-chat-runtime.js";
import { NativeF3CachePersistenceError, NativeF3CacheProviderError, makeNativeF3PersistentChat, type NativeF3CacheAcquire, type NativeF3CachePersistenceShape, type NativeF3CacheProviderShape } from "../src/native-f3-cache-runtime.js";

const request = Object.freeze({ endpoint: "https://provider.test", model: "m", system: "s", user: "u", seed: 0, maxTokens: 8 });
const state = Object.freeze({ maxCalls: 2, used: 1, hits: 0, misses: 1 });
const providerFailure = (delivery: "NOT_SENT" | "UNKNOWN_DELIVERY", detail: string) => new NativeF3CacheProviderError({ delivery, detail });
const run = (acquire: NativeF3CacheAcquire, provider: NativeF3CacheProviderShape, completed: Array<unknown> = [], failed: Array<unknown> = []) => {
  const persistence: NativeF3CachePersistenceShape = {
    acquire: () => Effect.succeed(acquire),
    complete: (input) => Effect.sync(() => { completed.push(input) }),
    failKnown: (input) => Effect.sync(() => { failed.push(input) })
  };
  return Effect.runPromise(makeNativeF3PersistentChat(persistence, provider)(request, "answerer"));
};
it("returns an atomically recorded cache hit without provider dispatch", async () => {
  const result = await run(
    { terminal: "CACHE_HIT", state: { ...state, hits: 1 }, document: { response_meta: { text: "cached" } } },
    { post: () => Effect.die("provider must not run") }
  );
  expect(result).toMatchObject({ terminal: "CACHE_HIT", state: { used: 1, misses: 1, hits: 1 }, meta: { text: "cached", cached: true } });
});
it("uses a pre-reserved miss exactly once and commits source-shaped response metadata", async () => {
  const completed: unknown[] = [];
  let sent = 0;
  const result = await run(
    { terminal: "MISS_RESERVED", state, reservation: { reservationId: "r1" } },
    { post: (value: NativeF3ChatTransportRequest) => Effect.sync(() => { sent += 1; expect(value.url).toBe("https://provider.test/chat/completions"); return { choices: [{ message: { content: "answer" }, finish_reason: "stop" }], usage: { prompt_tokens: 2, completion_tokens: 3 } }; }) },
    completed
  );
  expect(sent).toBe(1);
  expect(result).toMatchObject({ terminal: "COMPLETED", state, meta: { text: "answer", cached: false } });
  expect(completed).toHaveLength(1);
  expect(completed[0]).toMatchObject({ reservation: { reservationId: "r1" }, document: { response_meta: { request_sha256: expect.stringMatching(/^[0-9a-f]{64}$/) } } });
});
it("does not resend an already ambiguous durable reservation", async () => {
  const result = await run(
    { terminal: "UNRESOLVED_DISPATCH", state, detail: "crash after reserve" },
    { post: () => Effect.die("provider must not resend") }
  );
  expect(result).toMatchObject({ terminal: "UNRESOLVED_DISPATCH", state });
});
it("closes a reservation only when the provider proves it was not sent", async () => {
  const failed: unknown[] = [];
  const result = await run(
    { terminal: "MISS_RESERVED", state, reservation: { reservationId: "r2" } },
    { post: () => Effect.fail(providerFailure("NOT_SENT", "local validation refused request")) },
    [], failed
  );
  expect(result).toMatchObject({ terminal: "TRANSPORT_ERROR", state });
  expect(failed).toEqual([{ reservation: { reservationId: "r2" }, terminal: "TRANSPORT_ERROR", delivery: "NOT_SENT", detail: "local validation refused request" }]);
});
it("keeps an unknown-delivery reservation open so a later call cannot resend", async () => {
  let sent = 0, pending = false, failed = 0;
  const persistence: NativeF3CachePersistenceShape = {
    acquire: () => Effect.sync(() => {
      if (pending) return { terminal: "UNRESOLVED_DISPATCH" as const, state, detail: "response lost" };
      pending = true;
      return { terminal: "MISS_RESERVED" as const, state, reservation: { reservationId: "r3" } };
    }),
    complete: () => Effect.void,
    failKnown: () => Effect.sync(() => { failed += 1 })
  };
  const provider: NativeF3CacheProviderShape = { post: () => Effect.sync(() => { sent += 1 }).pipe(Effect.zipRight(Effect.fail(providerFailure("UNKNOWN_DELIVERY", "socket closed after write")))) };
  const execute = makeNativeF3PersistentChat(persistence, provider);
  const first = await Effect.runPromise(execute(request, "answerer"));
  const second = await Effect.runPromise(execute(request, "answerer"));
  expect(first).toMatchObject({ terminal: "TRANSPORT_UNCERTAIN", state });
  expect(second).toMatchObject({ terminal: "UNRESOLVED_DISPATCH", state });
  expect(sent).toBe(1);
  expect(failed).toBe(0);
});
it("reports unknown state when acquire itself fails", async () => {
  const persistence: NativeF3CachePersistenceShape = {
    acquire: () => Effect.fail(new NativeF3CachePersistenceError({ operation: "ACQUIRE", detail: "database unavailable" })),
    complete: () => Effect.void, failKnown: () => Effect.void
  };
  const result = await Effect.runPromise(makeNativeF3PersistentChat(persistence, { post: () => Effect.die("must not post") })(request, "answerer"));
  expect(result).toEqual(expect.objectContaining({ terminal: "PERSISTENCE_ERROR", state: null, detail: "database unavailable" }));
});
