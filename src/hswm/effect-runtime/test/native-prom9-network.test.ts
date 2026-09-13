import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { Effect, Either } from "effect";
import { describe, expect, it } from "vitest";
import { NativeProm9CallError } from "../src/native-prom9-call-domain.js";
import { NativeProm9ModelPort } from "../src/native-prom9-call-runtime.js";
import { nativeProm9PythonIsAlnum, nativeProm9RequestIdMatches, prepareNativeProm9Network } from "../src/native-prom9-network-domain.js";
import { NativeProm9NetworkMeter, runNativeProm9Item } from "../src/native-prom9-network-runtime.js";
import { nativeProm9FakeTokenMeter } from "../src/native-prom9-token-meter-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js";
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_network_v1/original.v1.json", import.meta.url), "utf8")) as {
    readonly cases: readonly {
        readonly name: string;
        readonly request_json: string;
        readonly calls_json: string;
        readonly responses_json: string;
        readonly call_receipts_json: string;
        readonly events: readonly string[];
        readonly canonical?: string;
        readonly error?: string;
    }[];
};
const unicode = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_network_v1/unicode_isalnum.v1.json", import.meta.url), "utf8")) as {
    readonly membership_sha256: string;
    readonly cases: readonly {
        readonly observed: string;
        readonly expected: string;
        readonly matches: boolean;
    }[];
};
const decode = (text: string): TaskJson => Either.getOrThrow(decodeNativeTaskJson(Buffer.from(text)));
type JsonRecord = Readonly<Record<string, TaskJson>>;
const meter = Either.getOrThrow(nativeProm9FakeTokenMeter());
describe("native three-call PROM-9 network", () => {
    it("matches original full run bytes and ordered sink/refusal boundaries for every arm", async () => {
        for (const row of fixture.cases) {
            const calls = decode(row.calls_json) as readonly JsonRecord[], responses = decode(row.responses_json) as readonly JsonRecord[], receipts = decode(row.call_receipts_json) as readonly JsonRecord[];
            const events: string[] = [];
            let index = 0;
            const result = await Effect.runPromise(Effect.either(runNativeProm9Item(decode(row.request_json)).pipe(Effect.provideService(NativeProm9NetworkMeter, meter), Effect.provideService(NativeProm9ModelPort, {
                invoke: call => Effect.sync(() => { events.push(`call:${index + 1}`); expect(renderNativeTaskJson(call), row.name).toBe(renderNativeTaskJson(calls[index]!)); return responses[index++]!; }),
                acceptCallReceipt: receipt => Effect.sync(() => { events.push(`accept_call:${index}`); expect(renderNativeTaskJson(receipt), row.name).toBe(renderNativeTaskJson(receipts[index - 1]!)); }),
                acceptItemRun: () => Effect.sync(() => { events.push("accept_item"); }).pipe(Effect.zipRight(row.name === "sink_failure" ? Effect.fail(new NativeProm9CallError({ detail: "sinkboom" })) : Effect.void))
            }))));
            expect(events, row.name).toEqual(row.events);
            expect(Either.isLeft(result), row.name).toBe(row.error !== undefined);
            if (Either.isRight(result))
                expect(renderNativeTaskJson(result.right), row.name).toBe(row.canonical);
        }
    });
    it("pins alphanumeric membership across every Unicode codepoint and request formatting cases", () => {
        const membership = Uint8Array.from({ length: 0x110000 }, (_, index) => Number(nativeProm9PythonIsAlnum(index)));
        expect(createHash("sha256").update(membership).digest("hex")).toBe(unicode.membership_sha256);
        for (const row of unicode.cases)
            expect(nativeProm9RequestIdMatches(row.observed, row.expected), row.observed).toBe(row.matches);
    });
    it("rejects registry/budget/getter corruption before model I/O and snapshots caller aliases", async () => {
        const raw = decode(fixture.cases[0]!.request_json) as JsonRecord;
        let calls = 0, reads = 0;
        const registry = raw["registry"] as JsonRecord;
        const getter = Object.defineProperty({ ...raw }, "item", { get: () => { reads += 1; return {}; } });
        for (const bad of [getter, { ...raw, registry: { ...registry, registry_sha256: "0".repeat(64) } }, { ...raw, persistent_state_bytes: true }, { ...raw, persistent_state_bytes: decode("1.0") }]) {
            const result = await Effect.runPromise(Effect.either(runNativeProm9Item(bad).pipe(Effect.provideService(NativeProm9NetworkMeter, meter), Effect.provideService(NativeProm9ModelPort, { invoke: () => Effect.sync(() => { calls += 1; return {}; }) }))));
            expect(Either.isLeft(result)).toBe(true);
        }
        expect(calls).toBe(0);
        expect(reads).toBe(0);
        const input = { ...raw }, prepared = Either.getOrThrow(prepareNativeProm9Network(input, meter));
        input["run_id"] = "mutation";
        expect(prepared.request["run_id"]).toBe("run");
    });
});
