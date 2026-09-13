/** Runtime artifact boundary. It never downloads a tokenizer or invokes a model. */
import { createHash } from "node:crypto";
import { Data, Effect, Either } from "effect";
import { renderNativeProm9QwenChatPrompt, type NativeProm9TokenMeter, NativeProm9TokenMeterError } from "./native-prom9-token-meter-domain.js";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
export class NativeProm9TokenMeterRuntimeError extends Data.TaggedError("NativeProm9TokenMeterRuntimeError")<{
    readonly detail: string;
}> {
}
export const inspectNativeProm9QwenTokenizerArtifacts = (paths: unknown): Effect.Effect<readonly string[], NativeProm9TokenMeterRuntimeError, PosixFileSystem> => {
    const copied = capturePaths(paths);
    if (copied === undefined)
        return Effect.fail(new NativeProm9TokenMeterRuntimeError({ detail: "tokenizer artifact paths must be non-empty text" }));
    return Effect.gen(function* () {
        const fs = yield* PosixFileSystem;
        for (const path of copied)
            yield* fs.identity(path, "inspect Qwen tokenizer artifact").pipe(Effect.mapError(() => new NativeProm9TokenMeterRuntimeError({ detail: "pinned local Qwen tokenizer artifacts are unavailable; BPE counting is not admitted" })));
        return copied;
    });
};
type VendorConstructor = new (tokenizerJson: unknown, tokenizerConfig: unknown) => {
    encode: (text: string) => unknown;
};
const vendorPackage: string = "@huggingface/tokenizers";
const artifactNames = Object.freeze(["vocab.json", "merges.txt", "tokenizer_config.json", "tokenizer.json"]);
/** Qwen/Qwen3.6-27B @ 6a9e13bd6fc8f0983b9b99948120bc37f49c13e9, Apache-2.0. */
export const NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS: Readonly<Record<string, string>> = Object.freeze({
    "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
    "merges.txt": "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d",
    "tokenizer_config.json": "5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b",
    "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"
});
export const NATIVE_PROM9_HISTORICAL_QWEN36_IDENTITY: Readonly<Record<string, string>> = Object.freeze({
    kind: "qwen2-bpe-local-files/v1",
    chat_template_id: "qwen3-im-start-system-user-think-disabled/v1",
    source: "https://huggingface.co/Qwen/Qwen3.6-27B (vocab.json, merges.txt, tokenizer_config.json)",
    vocab_sha256: NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS["vocab.json"]!,
    merges_sha256: NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS["merges.txt"]!,
    config_sha256: NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS["tokenizer_config.json"]!
});
/** Actual native implementation identity, kept distinct from the historical manifest. */
export const NATIVE_PROM9_DERIVED_QWEN36_PROFILE = Object.freeze({
    kind: "hswm-derived-qwen2-no-nfc/v1", sdk: "@huggingface/tokenizers", sdk_version: "0.1.3",
    repository: "Qwen/Qwen3.6-27B", revision: "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9",
    artifacts: NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS,
    mapping_delta: "IN_MEMORY_TOKENIZER_JSON_NORMALIZER_NFC_TO_NULL",
    historical_source_sha256: "5149473c7ca3efea865d97cee324ff2c9ccca5d4d637c66a049f34eae15da274",
    claim_ceiling: "LOCAL_SOURCE_REPLAY_NOT_LIVE_TOKENIZER_ADMISSION"
});
const invalid = (detail: string) => new NativeProm9TokenMeterRuntimeError({ detail });
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const capturePaths = (value: unknown): readonly string[] | undefined => {
    try {
        if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype || value.length === 0)
            return undefined;
        const copied: string[] = [];
        for (let index = 0; index < value.length; index++) {
            const d = Object.getOwnPropertyDescriptor(value, index);
            if (d === undefined || !Object.hasOwn(d, "value") || typeof d.value !== "string" || d.value === "")
                return undefined;
            copied.push(d.value);
        }
        return Object.freeze(copied);
    }
    catch {
        return undefined;
    }
};
const captureManifest = (value: unknown): Readonly<Record<string, string>> | undefined => {
    try {
        if (!record(value) || Object.getPrototypeOf(value) !== Object.prototype || Reflect.ownKeys(value).length !== artifactNames.length)
            return undefined;
        const entries: (readonly [
            string,
            string
        ])[] = [];
        for (const name of artifactNames) {
            const d = Object.getOwnPropertyDescriptor(value, name);
            if (d === undefined || !Object.hasOwn(d, "value") || !d.enumerable || typeof d.value !== "string" || d.value !== NATIVE_PROM9_QWEN36_TOKENIZER_ARTIFACTS[name])
                return undefined;
            entries.push([name, d.value]);
        }
        return Object.freeze(Object.fromEntries(entries));
    }
    catch {
        return undefined;
    }
};
const encoder = (value: unknown): ((text: string) => unknown) | undefined => value !== null && typeof value === "object" && typeof Reflect.get(value, "encode") === "function" ? Reflect.get(value, "encode") as (text: string) => unknown : undefined;
const count = (value: unknown): number | undefined => {
    if (!record(value))
        return undefined;
    const ids: unknown = Reflect.get(value, "ids");
    if (!Array.isArray(ids))
        return undefined;
    for (let index = 0; index < ids.length; index++) {
        const id: unknown = ids[index];
        if (!Object.hasOwn(ids, index) || typeof id !== "number" || !Number.isSafeInteger(id) || id < 0)
            return undefined;
    }
    return ids.length;
};
/** Experimental SDK profile: tokenizer.json is additional to the historical three-file envelope. */
const loadNativeProm9QwenMeter = (directory: unknown, expectedSha256: unknown, historicalNoNfc: boolean): Effect.Effect<NativeProm9TokenMeter, NativeProm9TokenMeterRuntimeError, PosixFileSystem> => Effect.gen(function* () {
    if (typeof directory !== "string" || directory === "")
        return yield* Effect.fail(invalid("experimental tokenizer input is invalid"));
    const expected = captureManifest(expectedSha256);
    if (expected === undefined)
        return yield* Effect.fail(invalid("tokenizer hash manifest must bind the qualified Qwen3.6-27B artifact tuple"));
    const fs = yield* PosixFileSystem;
    const files = yield* Effect.forEach(artifactNames, name => fs.readRegularBounded(`${directory}/${name}`, { maximumBytes: 32 * 1024 * 1024, minimumBytes: 1, operation: `read Qwen tokenizer ${name}` }).pipe(Effect.mapError(() => invalid("pinned local Qwen tokenizer artifacts are unavailable; BPE counting is not admitted"))), { concurrency: 1 });
    for (let index = 0; index < artifactNames.length; index++)
        if (createHash("sha256").update(files[index]!.bytes).digest("hex") !== expected[artifactNames[index]!]!)
            return yield* Effect.fail(invalid("experimental tokenizer artifact hash drifted"));
    const text = (index: number): Effect.Effect<string, NativeProm9TokenMeterRuntimeError> => Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(files[index]!.bytes), catch: () => invalid("experimental tokenizer artifact is not strict UTF-8") });
    const configText = yield* text(2), tokenizerText = yield* text(3);
    const vendor: unknown = yield* Effect.tryPromise({ try: (): Promise<unknown> => import(vendorPackage), catch: () => invalid("official tokenizer SDK is unavailable") });
    const Tokenizer = vendor !== null && typeof vendor === "object" ? Reflect.get(vendor, "Tokenizer") : undefined;
    if (typeof Tokenizer !== "function")
        return yield* Effect.fail(invalid("official tokenizer SDK shape drifted"));
    const tokenizerJson = yield* Effect.try({ try: () => JSON.parse(tokenizerText), catch: () => invalid("official tokenizer JSON is invalid") });
    if (!record(tokenizerJson))
        return yield* Effect.fail(invalid("official tokenizer JSON shape drifted"));
    const sourceNormalizer = tokenizerJson["normalizer"];
    if (historicalNoNfc && (!record(sourceNormalizer) || sourceNormalizer["type"] !== "NFC"))
        return yield* Effect.fail(invalid("cannot derive historical Qwen2 pipeline from this SDK normalizer"));
    const configuredTokenizerJson = historicalNoNfc ? Object.freeze({ ...tokenizerJson, normalizer: null }) : tokenizerJson;
    const tokenizer = yield* Effect.try({ try: () => Reflect.construct(Tokenizer as VendorConstructor, [configuredTokenizerJson, JSON.parse(configText)]), catch: () => invalid("official tokenizer SDK refused local artifacts") });
    const encode = encoder(tokenizer);
    if (encode === undefined)
        return yield* Effect.fail(invalid("official tokenizer SDK shape drifted"));
    const countText = (text: string): Either.Either<number, NativeProm9TokenMeterError> => {
        try {
            if (typeof text !== "string")
                return Either.left(new NativeProm9TokenMeterError({ detail: "count_text requires a string" }));
            const tokens = count(Reflect.apply(encode, tokenizer, [text]));
            return tokens === undefined ? Either.left(new NativeProm9TokenMeterError({ detail: "official tokenizer SDK returned invalid token ids" })) : Either.right(tokens);
        }
        catch {
            return Either.left(new NativeProm9TokenMeterError({ detail: "official tokenizer SDK encoding failed" }));
        }
    };
    return Object.freeze({ countText, countChatPrompt: (system, user) => renderNativeProm9QwenChatPrompt(system, user).pipe(Either.flatMap(countText)) });
});
/** SDK tokenizer.json retains NFC; historical QwenBpeMeter's pinned slow pipeline does not. */
export const loadNativeProm9DerivedHistoricalQwen2Meter = (directory: unknown, expectedSha256: unknown): Effect.Effect<NativeProm9TokenMeter, NativeProm9TokenMeterRuntimeError, PosixFileSystem> => loadNativeProm9QwenMeter(directory, expectedSha256, true);
/** Experimental unmodified tokenizer.json profile, kept separate from historical admission. */
export const loadNativeProm9ExperimentalQwenSdkMeter = (directory: unknown, expectedSha256: unknown): Effect.Effect<NativeProm9TokenMeter, NativeProm9TokenMeterRuntimeError, PosixFileSystem> => loadNativeProm9QwenMeter(directory, expectedSha256, false);
