import { Effect, Either } from "effect";
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { invokeNativeProm9Function, NativeProm9ModelPort } from "../src/native-prom9-call-runtime.js";
import { configureNativeProm9OpenAiCompatibleTransport, prepareNativeProm9OpenAiCompatibleRequest } from "../src/native-prom9-json-transport-domain.js";
import { NativeProm9JsonTransportRuntimeError, makeNativeProm9OpenAiCompatibleModelPort, NativeProm9JsonEnvironment, NativeProm9JsonHttp, type NativeProm9JsonHttpResponse } from "../src/native-prom9-json-transport-runtime.js";
import { validNativeTaskJson, taskJsonRecord, type TaskJson } from "../src/native-task-json-domain.js";
const configuration = Either.getOrThrow(configureNativeProm9OpenAiCompatibleTransport("https://model.example/v1/chat/completions", "PROM9_TEST_KEY"));
const call = Object.freeze({ physical_call_id: "p", run_id: "run", arm_id: "arm", item_id: "item", call_index: 1n, function_id: "QF_QUERY_COMPILER", model: "model", model_revision: "revision", system_prompt: "system", input_type: "QueryEnvelopeV1", input_payload: Object.freeze({ request_id: "req", query_text: "question", allowed_evidence_types: Object.freeze(["fact"]), budget: Object.freeze({ max_candidates: 1n, max_evidence_items: 1n, max_input_tokens: 30n, max_output_tokens: 10n }), parity_filler: "" }), output_type: "QueryPlanV1", max_output_tokens: 10n }) as Readonly<Record<string, TaskJson>>;
const response = (value: unknown, status = 200): NativeProm9JsonHttpResponse => Object.freeze({ status, body: new TextEncoder().encode(JSON.stringify(value)) });
const success = Object.freeze({ model: "model", choices: Object.freeze([{ finish_reason: "stop", message: Object.freeze({ content: JSON.stringify({ request_id: "req", objectives: [], required_evidence_types: [], constraints: [], abstain: true }) }) }]), usage: Object.freeze({ prompt_tokens: 12, completion_tokens: 5 }) });
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_json_transport_v1/original.v1.json", import.meta.url), "utf8")) as {
    source_oracle: {
        request_url: string;
        request_method: string;
        request_content_type: string;
        request_body_utf8: string;
        response: unknown;
        result: Record<string, unknown>;
    };
};
it("constructs the source OpenAI-compatible canonical body without exposing the API key", () => {
    const request = Either.getOrThrow(prepareNativeProm9OpenAiCompatibleRequest(configuration, call, "secret"));
    expect(request.url).toBe(oracle.source_oracle.request_url);
    expect(request.headers).toEqual({ "Content-Type": "application/json", Authorization: "Bearer secret" });
    expect(new TextDecoder().decode(request.body)).toBe(oracle.source_oracle.request_body_utf8);
    expect(Either.isLeft(configureNativeProm9OpenAiCompatibleTransport("ftp://no"))).toBe(true);
    expect(Either.isLeft(configureNativeProm9OpenAiCompatibleTransport("https://ok", null, 100, 1))).toBe(true);
    let reads = 0;
    const getter = Object.defineProperty({ ...call }, "model", { get: () => { reads += 1; return "model"; } });
    expect(Either.isLeft(prepareNativeProm9OpenAiCompatibleRequest(configuration, getter, "secret"))).toBe(true);
    expect(reads).toBe(0);
});
it("replays the captured Python request/result through the public call boundary and rejects malformed provider observations", async () => {
    let posts = 0;
    const invoke = (value: NativeProm9JsonHttpResponse) => makeNativeProm9OpenAiCompatibleModelPort(configuration).pipe(Effect.provideService(NativeProm9JsonEnvironment, { read: () => Effect.succeed("secret") }), Effect.provideService(NativeProm9JsonHttp, { post: request => Effect.sync(() => { posts += 1; expect(request.headers["Authorization"]).toBe("Bearer secret"); return value; }) }));
    const port = await Effect.runPromise(invoke(response(oracle.source_oracle.response)));
    const actual = await Effect.runPromise(invokeNativeProm9Function({ run_id: call["run_id"], arm_id: call["arm_id"], item_id: call["item_id"], call_index: call["call_index"], function: { function_id: call["function_id"], model: call["model"], model_revision: call["model_revision"], input_type: call["input_type"], output_type: call["output_type"], prompt: call["system_prompt"], prompt_sha256: "31893474be502887056bdf889c3fddfca80b7dfdd5fd7e21424ac9ace6080a65" }, input_payload: call["input_payload"], max_output_tokens: call["max_output_tokens"] }).pipe(Effect.provideService(NativeProm9ModelPort, port)));
    expect(actual.receipt).toMatchObject({ model: oracle.source_oracle.result["model"], model_revision: oracle.source_oracle.result["model_revision"], input_tokens: 12n, output_tokens: 5n, retries: 0n, cache_status: oracle.source_oracle.result["cache_status"] });
    expect(typeof actual.receipt["latency_ms"]).toBe("bigint");
    for (const bad of [response({ ...success, model: "other" }), response({ ...success, choices: [{ finish_reason: "length", message: { content: "{}" } }] }), response({ ...success, choices: [{ finish_reason: "stop", message: { content: "not-json" } }] }), response(success, 503)]) {
        const candidate = await Effect.runPromise(invoke(bad));
        const result = await Effect.runPromise(Effect.either(candidate.invoke(call)));
        expect(Either.isLeft(result)).toBe(true);
    }
    expect(posts).toBe(5);
});
it("reads the named secret on every call, refuses missing values before POST, and never returns secret text", async () => {
    const values: Array<string | undefined> = ["first", "second", undefined];
    const headers: string[] = [];
    let posts = 0;
    const port = await Effect.runPromise(makeNativeProm9OpenAiCompatibleModelPort(configuration).pipe(Effect.provideService(NativeProm9JsonEnvironment, { read: () => Effect.sync(() => values.shift()) }), Effect.provideService(NativeProm9JsonHttp, { post: request => Effect.sync(() => { posts += 1; headers.push(request.headers["Authorization"]!); return response(success); }) })));
    await Effect.runPromise(port.invoke(call));
    await Effect.runPromise(port.invoke(call));
    const missing = await Effect.runPromise(Effect.either(port.invoke(call)));
    expect(headers).toEqual(["Bearer first", "Bearer second"]);
    expect(posts).toBe(2);
    expect(Either.isLeft(missing)).toBe(true);
    if (Either.isLeft(missing))
        expect(missing.left.detail).not.toContain("second");
});
it("captures call identity before environment and HTTP callbacks and scrubs injected failures", async () => {
    const mutable = { ...call };
    const port = await Effect.runPromise(makeNativeProm9OpenAiCompatibleModelPort(configuration).pipe(Effect.provideService(NativeProm9JsonEnvironment, { read: () => Effect.sync(() => { mutable["model"] = "mutated"; mutable["model_revision"] = "mutated"; return "secret"; }) }), Effect.provideService(NativeProm9JsonHttp, { post: () => Effect.succeed(response(success)) })));
    const result = await Effect.runPromise(port.invoke(mutable));
    if (!validNativeTaskJson(result) || !taskJsonRecord(result))
        return expect.fail("captured result must be JSON data");
    expect(result["model"]).toBe("model");
    expect(result["model_revision"]).toBe("revision");
    const failed = await Effect.runPromise(makeNativeProm9OpenAiCompatibleModelPort(configuration).pipe(Effect.provideService(NativeProm9JsonEnvironment, { read: () => Effect.succeed("secret") }), Effect.provideService(NativeProm9JsonHttp, { post: () => Effect.fail(new NativeProm9JsonTransportRuntimeError({ detail: "Bearer secret" })) })));
    const refused = await Effect.runPromise(Effect.either(failed.invoke(call)));
    expect(Either.isLeft(refused)).toBe(true);
    if (Either.isLeft(refused))
        expect(refused.left.detail).not.toContain("secret");
    let reads = 0;
    const configGetter = Object.defineProperty({ ...configuration }, "endpoint", { get: () => { reads++; return configuration.endpoint; } });
    expect(Either.isLeft(prepareNativeProm9OpenAiCompatibleRequest(configGetter, call, "secret"))).toBe(true);
    expect(reads).toBe(0);
});
