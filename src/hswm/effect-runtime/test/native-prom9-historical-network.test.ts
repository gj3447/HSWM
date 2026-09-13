import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Effect, Either } from "effect";
import { expect, it } from "vitest";
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js";
import { NativeProm9ModelPort } from "../src/native-prom9-call-runtime.js";
import { loadNativeProm9F1HistoricalEnvelope } from "../src/native-prom9-f1-envelope-runtime.js";
import { NativeProm9NetworkMeter, runNativeProm9Item } from "../src/native-prom9-network-runtime.js";
import { NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS } from "../src/native-prom9-token-meter-runtime.js";
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "../src/native-task-json-domain.js";
type JsonRecord = Readonly<Record<string, TaskJson>>;
const decode = (path: string): JsonRecord => {
    const value = Either.getOrThrow(decodeNativeTaskJson(readFileSync(new URL(path, import.meta.url))));
    if (!taskJsonRecord(value))
        throw new Error("historical fixture is not an object");
    return value;
};
const directory = process.env["HSWM_QWEN_TOKENIZER_ARTIFACT_DIR"];
it("pins the current and historical replay sources without changing their bytes", () => {
    const profile = decode("../../../../tests/fixtures/native_migration/prom9_network_v1/historical_profile.v1.json");
    for (const [path, digest] of Object.entries(profile["source_pins"] as JsonRecord))
        expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex")).toBe(digest);
    expect(profile["current_request_id_hex_chars"]).toBe(8);
    expect(profile["historical_request_id_hex_chars"]).toBe(20);
});
it.skipIf(directory === undefined)("replays the entire historical 20-item-arm / 60-call suite through the native network and actual local tokenizer", async () => {
    const manifest = decode("../../../../_research/prom9_runs/f1-2wiki-dev-r5-envelope/manifest.v2.json");
    const suite = decode("../../../../_research/prom9_runs/f1-2wiki-dev-r5-live/suite.json");
    const loaded = await Effect.runPromise(loadNativeProm9F1HistoricalEnvelope(directory, NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS, manifest, suite["registries"]).pipe(Effect.provide(NodePosixFileSystemLive)));
    expect(loaded.executionProfile.claim_ceiling).toBe("LOCAL_SOURCE_REPLAY_NOT_LIVE_TOKENIZER_ADMISSION");
    const items = manifest["items"] as readonly JsonRecord[], runs = suite["item_runs"] as readonly JsonRecord[], registries = suite["registries"] as JsonRecord;
    const envelope = manifest["token_envelope"] as JsonRecord, filler = envelope["filler"] as JsonRecord, inputCaps = envelope["per_call_input_caps"] as JsonRecord, outputCaps = envelope["per_call_output_caps"] as JsonRecord;
    let physicalCalls = 0, acceptedRuns = 0;
    for (const row of runs) {
        const armId = row["arm_id"] as string, item = items.find(item => item["item_id"] === row["item_id"]);
        expect(item).toBeDefined();
        const calls = row["calls"] as readonly JsonRecord[];
        let index = 0;
        const result = await Effect.runPromise(runNativeProm9Item({
            run_id: row["run_id"], arm_id: armId, item, registry: registries[armId], persistent_state_bytes: row["persistent_state_bytes"],
            envelope: { input_caps: [inputCaps["1"], inputCaps["2"], inputCaps["3"]], output_caps: [outputCaps["1"], outputCaps["2"], outputCaps["3"]], filler_field: filler["field"], filler_unit: filler["unit"], max_filler_chars: filler["max_filler_chars"] }
        }, "HISTORICAL_20_HEX").pipe(Effect.provideService(NativeProm9NetworkMeter, loaded.meter), Effect.provideService(NativeProm9ModelPort, {
            invoke: actual => Effect.sync(() => {
                const call = calls[index++]!;
                physicalCalls++;
                const actualPayload = actual["input_payload"] as JsonRecord, expectedPayload = call["input_payload"] as JsonRecord;
                const delta = Object.keys(actualPayload).filter(key => renderNativeTaskJson(actualPayload[key]!) !== renderNativeTaskJson(expectedPayload[key]!)).map(key => ({ key, actual: renderNativeTaskJson(actualPayload[key]!).slice(0, 220), expected: renderNativeTaskJson(expectedPayload[key]!).slice(0, 220), actual_length: renderNativeTaskJson(actualPayload[key]!).length, expected_length: renderNativeTaskJson(expectedPayload[key]!).length }));
                expect(delta, JSON.stringify(delta)).toEqual([]);
                expect(actual["physical_call_id"]).toBe(call["physical_call_id"]);
                expect(renderNativeTaskJson(actual["input_payload"]!)).toBe(renderNativeTaskJson(call["input_payload"]!));
                return { payload: call["output_payload"], ...Object.fromEntries(["model", "model_revision", "input_tokens", "output_tokens", "latency_ms", "cache_status", "retries"].map(key => [key, call[key]])) };
            }),
            acceptCallReceipt: receipt => Effect.sync(() => { expect(renderNativeTaskJson(receipt)).toBe(renderNativeTaskJson(calls[index - 1]!)); }),
            acceptItemRun: receipt => Effect.sync(() => { acceptedRuns++; expect(renderNativeTaskJson(receipt)).toBe(renderNativeTaskJson(row)); })
        })));
        expect(renderNativeTaskJson(result)).toBe(renderNativeTaskJson(row));
    }
    expect(physicalCalls).toBe(60);
    expect(acceptedRuns).toBe(20);
}, 60000);
