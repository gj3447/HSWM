import { Effect, Either } from "effect";
import { expect, it } from "vitest";
import { makeNativeF3FetchProvider } from "../src/native-f3-fetch-provider.js";

const request = (overrides: Partial<{ url: string; bodyUtf8: string; timeoutSeconds: number }> = {}) => Object.freeze({
  url: "https://provider.test/chat/completions",
  bodyUtf8: '{"exact":"native-f3-body"}',
  timeoutSeconds: 1,
  ...overrides
});
const run = (provider: ReturnType<typeof makeNativeF3FetchProvider>, value = request()) => Effect.runPromise(Effect.either(provider.post(value)));

it("posts the exact F3 identity URL and UTF-8 body once with JSON and redirects disabled", async () => {
  const observed: Array<readonly [Parameters<typeof fetch>[0], Parameters<typeof fetch>[1]]> = [];
  const fetchImpl: typeof fetch = (input, init) => {
    observed.push([input, init]);
    return Promise.resolve(new Response('{"choices":[]}', { status: 200 }));
  };
  const provider = makeNativeF3FetchProvider({ fetch: fetchImpl });
  const result = await run(provider);
  expect(Either.isRight(result)).toBe(true);
  if (Either.isRight(result)) expect(result.right).toEqual({ choices: [] });
  expect(observed).toHaveLength(1);
  expect(observed[0]).toEqual(["https://provider.test/chat/completions", expect.objectContaining({ method: "POST", body: '{"exact":"native-f3-body"}', redirect: "error", headers: { "content-type": "application/json" } })]);
});

it("rejects malformed local input as NOT_SENT without calling fetch", async () => {
  let calls = 0;
  const fetchImpl: typeof fetch = () => { calls += 1; return Promise.resolve(new Response("{}")); };
  const provider = makeNativeF3FetchProvider({ fetch: fetchImpl });
  const result = await run(provider, request({ url: "file:///not-a-provider" }));
  expect(result).toMatchObject({ _tag: "Left", left: { delivery: "NOT_SENT" } });
  expect(calls).toBe(0);
});

it("keeps dispatch, HTTP, and response failures conservatively UNKNOWN_DELIVERY and never retries", async () => {
  let rejectedCalls = 0;
  const rejectedFetch: typeof fetch = () => { rejectedCalls += 1; return Promise.reject(new Error("socket closed")); };
  const rejected = makeNativeF3FetchProvider({ fetch: rejectedFetch });
  expect(await run(rejected)).toMatchObject({ _tag: "Left", left: { delivery: "UNKNOWN_DELIVERY" } });
  expect(rejectedCalls).toBe(1);
  let statusCalls = 0;
  const statusFetch: typeof fetch = () => { statusCalls += 1; return Promise.resolve(new Response("unavailable", { status: 503 })); };
  const status = makeNativeF3FetchProvider({ fetch: statusFetch });
  expect(await run(status)).toMatchObject({ _tag: "Left", left: { delivery: "UNKNOWN_DELIVERY" } });
  expect(statusCalls).toBe(1);
  const invalidFetch: typeof fetch = () => Promise.resolve(new Response("not json", { status: 200 }));
  const invalid = makeNativeF3FetchProvider({ fetch: invalidFetch });
  expect(await run(invalid)).toMatchObject({ _tag: "Left", left: { delivery: "UNKNOWN_DELIVERY", detail: "response JSON is invalid" } });
});

it("aborts a timed-out dispatch as UNKNOWN_DELIVERY", async () => {
  let aborted = false;
  const fetchImpl: typeof fetch = (_input, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => { aborted = true; reject(new Error("aborted")); });
  });
  const provider = makeNativeF3FetchProvider({ fetch: fetchImpl });
  const result = await run(provider, request({ timeoutSeconds: 1 }));
  expect(result).toMatchObject({ _tag: "Left", left: { delivery: "UNKNOWN_DELIVERY", detail: "HTTP deadline exceeded" } });
  expect(aborted).toBe(true);
}, 3000);

it("rejects a response above one MiB without retrying", async () => {
  let calls = 0;
  const fetchImpl: typeof fetch = () => {
    calls += 1;
    return Promise.resolve(new Response(new Uint8Array(1024 * 1024 + 1), { status: 200 }));
  };
  const provider = makeNativeF3FetchProvider({ fetch: fetchImpl });
  const result = await run(provider);
  expect(result).toMatchObject({ _tag: "Left", left: { delivery: "UNKNOWN_DELIVERY", detail: "response body exceeds bound" } });
  expect(calls).toBe(1);
});
