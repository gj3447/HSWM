import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Effect, Either } from "effect";
import { expect, it } from "vitest";
import { enforceNativeProm9F1Envelope, projectNativeProm9F1Envelope } from "../src/native-prom9-f1-envelope-domain.js";
import { loadNativeProm9DerivedHistoricalQwen2Meter } from "../src/native-prom9-token-meter-runtime.js";
import { loadNativeProm9F1HistoricalEnvelope } from "../src/native-prom9-f1-envelope-runtime.js";
import { nativeProm9FakeTokenMeter } from "../src/native-prom9-token-meter-domain.js";
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js";
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord } from "../src/native-task-json-domain.js";
const decode = (path: string) => Either.getOrThrow(decodeNativeTaskJson(readFileSync(new URL(path, import.meta.url))));
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_f1_envelope_v1/original.v1.json", import.meta.url), "utf8")) as {
    projection: {
        items: unknown;
    };
    source_pins: Readonly<Record<string, string>>;
};
const refusals = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_f1_envelope_v1/refusals.v1.json", import.meta.url), "utf8")) as {
    cases: readonly {
        readonly envelope: unknown;
    }[];
};
it("pins the Python oracle source bytes", () => {
    for (const [path, expected] of Object.entries(fixture.source_pins))
        expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex")).toBe(expected);
});
const manifestForPure = () => {
    const value = decode("../../../../_research/prom9_runs/f1-2wiki-dev-r5-envelope/manifest.v2.json"), suite = decode("../../../../_research/prom9_runs/f1-2wiki-dev-r5-live/suite.json");
    if (!taskJsonRecord(value) || !taskJsonRecord(suite) || !taskJsonRecord(value["token_envelope"]!))
        throw new Error("fixture");
    return { value, suite, envelope: value["token_envelope"] };
};
it("replays original FakeMeter projections and enforcement without local tokenizer artifacts", () => { const { value, suite, envelope } = manifestForPure(), meter = Either.getOrThrow(nativeProm9FakeTokenMeter()); const original = decode("../../../../tests/fixtures/native_migration/prom9_f1_envelope_v1/fake_original.v1.json"); if (!taskJsonRecord(original))
    throw new Error("fixture"); const result = Either.getOrThrow(projectNativeProm9F1Envelope(value["run_id"], value["items"], suite["registries"], meter, envelope["projected_output_tokens_by_arm"], envelope["projection_slack_tokens"], envelope["per_call_input_caps"])); expect(renderNativeTaskJson(result)).toBe(renderNativeTaskJson(original["projection"]!)); expect(Either.isLeft(enforceNativeProm9F1Envelope(value["run_id"], value["items"], suite["registries"], meter, envelope, value["token_tolerance"]))).toBe(true); });
it("refuses descriptor traps, sparse items, and invalid meter counts without invoking getters", () => { let reads = 0; const getter = Object.defineProperty({}, "x", { enumerable: true, get() { reads += 1; return 1; } }), sparse = [,]; const meter = Either.getOrThrow(nativeProm9FakeTokenMeter()), { value, suite, envelope } = manifestForPure(); expect(Either.isLeft(projectNativeProm9F1Envelope(value["run_id"], getter, suite["registries"], meter, envelope["projected_output_tokens_by_arm"], envelope["projection_slack_tokens"], envelope["per_call_input_caps"]))).toBe(true); expect(reads).toBe(0); expect(Either.isLeft(projectNativeProm9F1Envelope(value["run_id"], sparse, suite["registries"], meter, envelope["projected_output_tokens_by_arm"], envelope["projection_slack_tokens"], envelope["per_call_input_caps"]))).toBe(true); const bad = { countText: () => Either.right(-1), countChatPrompt: () => Either.right(1.5) }; expect(Either.isLeft(projectNativeProm9F1Envelope(value["run_id"], value["items"], suite["registries"], bad, envelope["projected_output_tokens_by_arm"], envelope["projection_slack_tokens"], envelope["per_call_input_caps"]))).toBe(true); });
it.skipIf(process.env["HSWM_QWEN_TOKENIZER_ARTIFACT_DIR"] === undefined)("replays original Qwen per-item envelope projections", async () => {
    const manifest = decode("../../../../_research/prom9_runs/f1-2wiki-dev-r5-envelope/manifest.v2.json"), suite = decode("../../../../_research/prom9_runs/f1-2wiki-dev-r5-live/suite.json"), expected = Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(JSON.stringify(fixture.projection))));
    if (!taskJsonRecord(manifest) || !taskJsonRecord(suite))
        throw new Error("fixture");
    const directory = process.env["HSWM_QWEN_TOKENIZER_ARTIFACT_DIR"]!, hashes = { "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003", "merges.txt": "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d", "tokenizer_config.json": "5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b", "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42" };
    const meter = await Effect.runPromise(loadNativeProm9DerivedHistoricalQwen2Meter(directory, hashes).pipe(Effect.provide(NodePosixFileSystemLive)));
    const envelope = taskJsonRecord(manifest["token_envelope"]!) ? manifest["token_envelope"] : undefined;
    if (envelope === undefined)
        throw new Error("envelope");
    const actual = Either.getOrThrow(projectNativeProm9F1Envelope(manifest["run_id"], manifest["items"], suite["registries"], meter, envelope["projected_output_tokens_by_arm"], envelope["projection_slack_tokens"], envelope["per_call_input_caps"]));
    expect(renderNativeTaskJson(actual)).toBe(renderNativeTaskJson(expected));
    for (const refusal of refusals.cases) {
        expect(Either.isLeft(enforceNativeProm9F1Envelope(manifest["run_id"], manifest["items"], suite["registries"], meter, refusal.envelope, manifest["token_tolerance"]))).toBe(true);
    }
});
it.skipIf(process.env["HSWM_QWEN_TOKENIZER_ARTIFACT_DIR"] === undefined)("requires the declared historical tokenizer identity before local envelope replay", async () => {
    const { value, suite, envelope } = manifestForPure(), directory = process.env["HSWM_QWEN_TOKENIZER_ARTIFACT_DIR"]!, hashes = { "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003", "merges.txt": "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d", "tokenizer_config.json": "5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b", "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42" };
    if (!taskJsonRecord(envelope))
        throw new Error("envelope");
    const accepted = await Effect.runPromise(loadNativeProm9F1HistoricalEnvelope(directory, hashes, value, suite["registries"]).pipe(Effect.provide(NodePosixFileSystemLive)));
    expect(renderNativeTaskJson(accepted.projection)).toBe(renderNativeTaskJson(Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(JSON.stringify(fixture.projection))))));
    const bad = await Effect.runPromiseExit(loadNativeProm9F1HistoricalEnvelope(directory, hashes, { ...value, token_envelope: { ...envelope, tokenizer: { kind: "attacker", validation_receipt_sha256: "a".repeat(64) } } }, suite["registries"]).pipe(Effect.provide(NodePosixFileSystemLive)));
    expect(bad._tag).toBe("Failure");
});
