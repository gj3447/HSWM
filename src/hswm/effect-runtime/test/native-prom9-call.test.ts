import { readFileSync } from "node:fs";
import { Effect, Either } from "effect";
import { describe, expect, it } from "vitest";
import { NativeProm9CallError, prepareNativeProm9Call } from "../src/native-prom9-call-domain.js";
import { invokeNativeProm9Function, NativeProm9ModelPort, type NativeProm9ModelPortShape } from "../src/native-prom9-call-runtime.js";
import { decodeNativeTaskJson, renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js";
type RecordJson = Readonly<Record<string, TaskJson>>;
interface Oracle {
    readonly call: RecordJson;
    readonly receipt: RecordJson;
    readonly normalized_output: RecordJson;
    readonly input_payload: RecordJson;
}
const decode = (text: string): TaskJson => Either.getOrThrow(decodeNativeTaskJson(Buffer.from(text)));
const fixture = decode(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_invoke_function_v1/original.v1.json", import.meta.url), "utf8")) as unknown as {
    readonly cases: readonly Oracle[];
};
const boundaries = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_invoke_function_v1/original-boundaries.v1.json", import.meta.url), "utf8")) as {
    readonly cases: readonly {
        readonly name: string;
        readonly request_json: string;
        readonly response_json: string;
        readonly events: readonly string[];
        readonly error?: string;
        readonly receipt?: RecordJson;
        readonly output?: RecordJson;
    }[];
};
const request = (row: Oracle): RecordJson => ({
    run_id: row.call["run_id"]!, arm_id: row.call["arm_id"]!, item_id: row.call["item_id"]!, call_index: row.call["call_index"]!,
    function: { function_id: row.call["function_id"]!, model: row.call["model"]!, model_revision: row.call["model_revision"]!, input_type: row.call["input_type"]!,
        output_type: row.call["output_type"]!, prompt: row.call["system_prompt"]!, prompt_sha256: row.receipt["prompt_sha256"]! },
    input_payload: row.input_payload, max_output_tokens: row.call["max_output_tokens"]!
});
const response = (row: Oracle): RecordJson => ({ payload: row.normalized_output, model: row.receipt["model"]!, model_revision: row.receipt["model_revision"]!,
    input_tokens: row.receipt["input_tokens"]!, output_tokens: row.receipt["output_tokens"]!, latency_ms: row.receipt["latency_ms"]!,
    cache_status: row.receipt["cache_status"]!, retries: row.receipt["retries"]! });
describe("native PROM-9 one-call boundary", () => {
    it("replays source boundary acceptance, refusals and sink ordering without losing float lexemes", async () => {
        for (const row of boundaries.cases) {
            const events: string[] = [];
            const service = {
                invoke: () => Effect.sync(() => { events.push("call"); return decode(row.response_json); }),
                acceptCallReceipt: row.name === "noncallable_sink" ? 17 : () => Effect.sync(() => { events.push("accept"); }).pipe(Effect.zipRight(row.name === "throwing_sink" ? Effect.fail(new NativeProm9CallError({ detail: "sinkboom" })) : Effect.void))
            } as unknown as NativeProm9ModelPortShape;
            const raw = { ...(decode(row.request_json) as RecordJson), function: request(fixture.cases[0]!)["function"]! };
            const result = await Effect.runPromise(Effect.either(invokeNativeProm9Function(raw).pipe(Effect.provideService(NativeProm9ModelPort, service))));
            expect(events, row.name).toEqual(row.events);
            expect(Either.isLeft(result), row.name).toBe(row.error !== undefined);
            if (Either.isRight(result)) {
                expect(renderNativeTaskJson(result.right.receipt), row.name).toBe(renderNativeTaskJson(row.receipt!));
                expect(renderNativeTaskJson(result.right.output), row.name).toBe(renderNativeTaskJson(row.output!));
            }
        }
        const original = response(fixture.cases[0]!);
        const defaults = Object.fromEntries(Object.entries(original).filter(([key]) => key !== "cache_status" && key !== "retries"));
        const prepared = Either.getOrThrow(prepareNativeProm9Call(request(fixture.cases[0]!)));
        expect(renderNativeTaskJson(Either.getOrThrow(prepared.complete(defaults)).receipt)).toBe(renderNativeTaskJson(fixture.cases[0]!.receipt));
    });
    it("replays all original QF/BF/AF call and receipt bytes, accepting only after validation", async () => {
        for (const row of fixture.cases) {
            const events: string[] = [];
            const actual = await Effect.runPromise(invokeNativeProm9Function(request(row)).pipe(Effect.provideService(NativeProm9ModelPort, {
                invoke: call => Effect.sync(() => { events.push("invoke"); expect(renderNativeTaskJson(call)).toBe(renderNativeTaskJson(row.call)); expect(Object.isFrozen(call)).toBe(true); return response(row); }),
                acceptCallReceipt: receipt => Effect.sync(() => { events.push("accept"); expect(renderNativeTaskJson(receipt)).toBe(renderNativeTaskJson(row.receipt)); })
            })));
            expect(renderNativeTaskJson(actual.receipt)).toBe(renderNativeTaskJson(row.receipt));
            expect(renderNativeTaskJson(actual.output)).toBe(renderNativeTaskJson(row.normalized_output));
            expect(events).toEqual(["invoke", "accept"]);
            expect(Object.isFrozen(actual.output)).toBe(true);
        }
    });
    it("refuses invalid preparation before I/O and response failures before acceptance", async () => {
        const row = fixture.cases[0]!;
        let calls = 0, accepts = 0, getterReads = 0;
        const invalid = Object.defineProperty({ ...request(row) }, "function", { get: () => { getterReads += 1; return {}; } });
        const wrongPrompt = { ...(request(row)["function"] as RecordJson), prompt: "changed after registration" };
        for (const raw of [invalid, { ...request(row), function: wrongPrompt }, { ...request(row), call_index: true }, { ...request(row), call_index: "1" }, { ...request(row), max_output_tokens: 0 }]) {
            const result = await Effect.runPromise(Effect.either(invokeNativeProm9Function(raw).pipe(Effect.provideService(NativeProm9ModelPort, { invoke: () => Effect.sync(() => { calls += 1; return response(row); }) }))));
            expect(Either.isLeft(result)).toBe(true);
        }
        expect(calls).toBe(0);
        expect(getterReads).toBe(0);
        for (const bad of [{ ...response(row), model_revision: "drift" }, { ...response(row), cache_status: null }, { ...response(row), retries: null }, { ...response(row), output_tokens: 1000000000 }, { ...response(row), latency_ms: true }]) {
            const result = await Effect.runPromise(Effect.either(invokeNativeProm9Function(request(row)).pipe(Effect.provideService(NativeProm9ModelPort, {
                invoke: () => Effect.sync(() => { calls += 1; return bad; }), acceptCallReceipt: () => Effect.sync(() => { accepts += 1; })
            }))));
            expect(Either.isLeft(result)).toBe(true);
        }
        expect(calls).toBe(5);
        expect(accepts).toBe(0);
    });
    it("propagates model and sink failures without retrying and captures input aliases", async () => {
        const row = fixture.cases[0]!, raw = structuredClone(request(row));
        const prepared = prepareNativeProm9Call(raw);
        expect(Either.isRight(prepared)).toBe(true);
        Object.assign(raw, { run_id: "later mutation" });
        if (Either.isRight(prepared))
            expect(prepared.right.modelCall["run_id"]).toBe(row.call["run_id"]);
        const events: string[] = [];
        const failure = new NativeProm9CallError({ detail: "synthetic sink failure" });
        const result = await Effect.runPromise(Effect.either(invokeNativeProm9Function(request(row)).pipe(Effect.provideService(NativeProm9ModelPort, {
            invoke: () => Effect.sync(() => { events.push("invoke"); return response(row); }),
            acceptCallReceipt: () => Effect.sync(() => { events.push("accept"); }).pipe(Effect.zipRight(Effect.fail(failure)))
        }))));
        expect(Either.isLeft(result)).toBe(true);
        expect(events).toEqual(["invoke", "accept"]);
        const modelFailure = await Effect.runPromise(Effect.either(invokeNativeProm9Function(request(row)).pipe(Effect.provideService(NativeProm9ModelPort, {
            invoke: () => Effect.sync(() => { events.push("failed-invoke"); }).pipe(Effect.zipRight(Effect.fail(failure)))
        }))));
        expect(Either.isLeft(modelFailure)).toBe(true);
        expect(events).toEqual(["invoke", "accept", "failed-invoke"]);
    });
});
