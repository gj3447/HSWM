import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { Effect, Either } from "effect";
import { expect, it } from "vitest";
import { fitNativeProm9ParityFiller, nativeProm9FakeTokenMeter, renderNativeProm9QwenChatPrompt } from "../src/native-prom9-token-meter-domain.js";
import { inspectNativeProm9QwenTokenizerArtifacts, NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS } from "../src/native-prom9-token-meter-runtime.js";
import { loadNativeProm9ExperimentalQwenSdkMeter } from "../src/native-prom9-token-meter-runtime.js";
import { loadNativeProm9DerivedHistoricalQwen2Meter } from "../src/native-prom9-token-meter-runtime.js";
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js";
import { decodeNativeTaskJson, renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js";
type Row = Readonly<{
    name: string;
    system: string;
    payload_json: string;
    cap: number;
    unit: string;
    max_chars: number;
    result: Readonly<{
        accepted: boolean;
        canonical?: string;
    }>;
}>;
const corpus = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_token_meter_v1/original.v1.json", import.meta.url), "utf8")) as Readonly<{
    source_pins: Readonly<Record<string, string>>;
    chat_render: Readonly<{
        system: string;
        user: string;
        value: string;
    }>;
    cases: readonly Row[];
}>;
const decode = (text: string): TaskJson => Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(text)));
it("pins the original token-meter source and chat serialization", () => {
    for (const [path, digest] of Object.entries(corpus.source_pins))
        expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex")).toBe(digest);
    expect(Either.getOrThrow(renderNativeProm9QwenChatPrompt(corpus.chat_render.system, corpus.chat_render.user))).toBe(corpus.chat_render.value);
});
it("replays original FakeMeter parity-filler outcomes", () => {
    const meter = Either.getOrThrow(nativeProm9FakeTokenMeter());
    for (const row of corpus.cases) {
        const actual = fitNativeProm9ParityFiller(meter, row.system, decode(row.payload_json), "parity_filler", row.cap, row.unit, row.max_chars);
        expect(Either.isRight(actual), row.name).toBe(row.result.accepted);
        if (row.result.accepted)
            expect(renderNativeTaskJson(Either.getOrThrow(actual))).toBe(row.result.canonical);
    }
});
it("refuses absent local Qwen artifacts without a download", async () => {
    const result = await Effect.runPromiseExit(inspectNativeProm9QwenTokenizerArtifacts(["/tmp/hswm-no-qwen-tokenizer-artifact"]).pipe(Effect.provide(NodePosixFileSystemLive)));
    expect(result._tag).toBe("Failure");
});
it("rejects unqualified artifact tuples and manifest getters before reads", async () => {
    let reads = 0;
    const getter = Object.defineProperty({ ...NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS }, "vocab.json", { get: () => { reads++; return "0".repeat(64); } });
    for (const raw of [getter, { ...NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS, "vocab.json": "0".repeat(64) }, Object.create(NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS)]) {
        const result = await Effect.runPromise(Effect.either(loadNativeProm9DerivedHistoricalQwen2Meter("/unused-no-read", raw).pipe(Effect.provide(NodePosixFileSystemLive))));
        expect(Either.isLeft(result)).toBe(true);
        if (Either.isLeft(result))
            expect(result.left.detail).toContain("qualified Qwen3.6-27B");
    }
    expect(reads).toBe(0);
    const sparse = new Array(1);
    expect((await Effect.runPromiseExit(inspectNativeProm9QwenTokenizerArtifacts(sparse).pipe(Effect.provide(NodePosixFileSystemLive))))._tag).toBe("Failure");
});
const experimental = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_token_meter_v1/qwen_sdk_experimental.v1.json", import.meta.url), "utf8")) as Readonly<{
    historical_three_file_hashes: Readonly<Record<string, string>>;
    additional_sdk_tokenizer_json_sha256: string;
    counts: readonly Readonly<{
        text: string;
        count: number;
    }>[];
    chat: Readonly<{
        system: string;
        user: string;
        count: number;
    }>;
}>;
const qwenDirectory = process.env["HSWM_QWEN_TOKENIZER_ARTIFACT_DIR"];
it.skipIf(qwenDirectory === undefined || !existsSync(`${qwenDirectory}/tokenizer.json`))("matches original Python counts through the experimental local SDK profile", async () => {
    const expected = { "vocab.json": experimental.historical_three_file_hashes["vocab_sha256"]!, "merges.txt": experimental.historical_three_file_hashes["merges_sha256"]!, "tokenizer_config.json": experimental.historical_three_file_hashes["config_sha256"]!, "tokenizer.json": experimental.additional_sdk_tokenizer_json_sha256 };
    const meter = await Effect.runPromise(loadNativeProm9ExperimentalQwenSdkMeter(qwenDirectory, expected).pipe(Effect.provide(NodePosixFileSystemLive)));
    for (const row of experimental.counts)
        expect(Either.getOrThrow(meter.countText(row.text))).toBe(row.count);
    expect(Either.getOrThrow(meter.countChatPrompt(experimental.chat.system, experimental.chat.user))).toBe(experimental.chat.count);
});
type Full = Readonly<{
    artifacts: Readonly<Record<string, string>>;
    registered_calls: readonly Readonly<{
        system: string;
        user: string;
        count: number;
    }>[];
    fragments: readonly Readonly<{
        text: string;
        count: number;
    }>[];
    sdk_known_divergences: readonly Readonly<{
        text: string;
        historical_python_count: number;
        observed_sdk_count: number;
    }>[];
    filler: Readonly<{
        system: string;
        payload_json: string;
        unit: string;
        max_chars: number;
        cases: readonly Readonly<{
            cap: number;
            result: Readonly<{
                accepted: boolean;
                canonical?: string;
            }>;
        }>[];
    }>;
}>;
const full = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_token_meter_v1/qwen_full_experimental.v1.json", import.meta.url), "utf8")) as Full;
it.skipIf(qwenDirectory === undefined || !existsSync(`${qwenDirectory}/tokenizer.json`))("replays the registered F1 prompts, adversarial fragments, and Qwen filler boundaries", async () => {
    const unmodified = await Effect.runPromise(loadNativeProm9ExperimentalQwenSdkMeter(qwenDirectory, full.artifacts).pipe(Effect.provide(NodePosixFileSystemLive)));
    for (const row of full.sdk_known_divergences) {
        expect(Either.getOrThrow(unmodified.countText(row.text))).toBe(row.observed_sdk_count);
        expect(row.observed_sdk_count).not.toBe(row.historical_python_count);
    }
    const meter = await Effect.runPromise(loadNativeProm9DerivedHistoricalQwen2Meter(qwenDirectory, full.artifacts).pipe(Effect.provide(NodePosixFileSystemLive)));
    for (const row of full.registered_calls)
        expect(Either.getOrThrow(meter.countChatPrompt(row.system, row.user))).toBe(row.count);
    for (const row of full.fragments)
        expect(Either.getOrThrow(meter.countText(row.text))).toBe(row.count);
    const payload = decode(full.filler.payload_json);
    for (const row of full.filler.cases) {
        const actual = fitNativeProm9ParityFiller(meter, full.filler.system, payload, "parity_filler", row.cap, full.filler.unit, full.filler.max_chars);
        expect(Either.isRight(actual), `cap ${row.cap}`).toBe(row.result.accepted);
        if (row.result.accepted)
            expect(renderNativeTaskJson(Either.getOrThrow(actual))).toBe(row.result.canonical);
    }
});
