import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, it } from "@effect/vitest";
import { Either } from "effect";
import { decodeNativeTaskJson } from "../src/native-task-json-domain.js";
import { NATIVE_S2S_TRAINING_RECEIPT_FIELDS_SOURCE_SHA256, createNativeS2SOptimizationHistoryEntry, createNativeS2STrainingConfig, nativeS2SOptimizationHistoryEntryCanonical, nativeS2SOptimizationHistorySha256, nativeS2STrainingConfigCanonical, parseNativeS2SOptimizationHistoryEntryJson, parseNativeS2SOptimizationHistoryEntryRaw, parseNativeS2STrainingConfigJson, parseNativeS2STrainingConfigRaw } from "../src/native-s2s-training-receipt-fields-domain.js";
interface Accepted {
    readonly accepted: true;
    readonly canonical: Readonly<Record<string, unknown>>;
}
interface Refused {
    readonly accepted: false;
    readonly error: string;
}
interface Oracle {
    readonly source_sha256: string;
    readonly configs: Readonly<Record<string, Accepted | Refused>>;
    readonly entries: Readonly<Record<string, Accepted | Refused>>;
    readonly history: {
        readonly sha256: string;
    };
}
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_training_receipt_fields_v1/original_python.json", import.meta.url), "utf8")) as Oracle;
const right = <A>(value: Either.Either<A, unknown>): A => {
    expect(Either.isRight(value)).toBe(true);
    return Either.isRight(value) ? value.right : expect.fail("expected a typed right result");
};
const configInputs: Readonly<Record<string, unknown>> = Object.freeze({
    default: {}, custom: { seed: 2n ** 64n - 1n, maxUpdates: 0, learningRate: 1.5, beta1: 0.5, beta2: 0.75, epsilon: Number.MIN_VALUE, gradientClip: 3.25, patience: 1, minDelta: 0 },
    negative_zero_min_delta: { minDelta: -0 }, bad_seed_bool: { seed: true }, bad_max_bool: { maxUpdates: true }, bad_patience: { patience: 0 }, nonfinite: { learningRate: Infinity }, negative_lr: { learningRate: -0 }, bad_beta: { beta1: 1 }
});
const entryInputs: Readonly<Record<string, unknown>> = Object.freeze({
    zero: { update: 0, trainLoss: 0, devLoss: 1.5, gradientNorm: null, clipped: false, improved: true, parametersSha256: "a".repeat(64) },
    one: { update: 1, trainLoss: Number.MIN_VALUE, devLoss: 3.5, gradientNorm: 4.25, clipped: true, improved: false, parametersSha256: "b".repeat(64) },
    negativezero_loss: { update: 1, trainLoss: -0, devLoss: 0, gradientNorm: 0, clipped: false, improved: false, parametersSha256: "a".repeat(64) },
    zero_wrong: { update: 0, trainLoss: 0, devLoss: 0, gradientNorm: 0, clipped: false, improved: true, parametersSha256: "a".repeat(64) },
    one_missing_gradient: { update: 1, trainLoss: 0, devLoss: 0, gradientNorm: null, clipped: false, improved: false, parametersSha256: "a".repeat(64) },
    flags_int: { update: 1, trainLoss: 0, devLoss: 0, gradientNorm: 0, clipped: 0, improved: false, parametersSha256: "a".repeat(64) },
    bad_sha: { update: 1, trainLoss: 0, devLoss: 0, gradientNorm: 0, clipped: false, improved: false, parametersSha256: "A".repeat(64) }
});
it("binds the original Python source and its config canonical bytes", () => {
    expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_training.py", import.meta.url))).digest("hex")).toBe(NATIVE_S2S_TRAINING_RECEIPT_FIELDS_SOURCE_SHA256);
    expect(oracle.source_sha256).toBe(NATIVE_S2S_TRAINING_RECEIPT_FIELDS_SOURCE_SHA256);
    for (const [name, expected] of Object.entries(oracle.configs)) {
        if (name === "integer_float")
            continue;
        const actual = createNativeS2STrainingConfig(configInputs[name]);
        expect(Either.isRight(actual)).toBe(expected.accepted);
        if (expected.accepted) {
            const canonical = right(nativeS2STrainingConfigCanonical(configInputs[name]));
            const expectedSeed = name === "custom" ? "18446744073709551615" : String(expected.canonical["seed"]);
            expect({ ...canonical, seed: canonical["seed"]!.toString() }).toEqual({ ...expected.canonical, seed: expectedSeed });
        }
        else if (Either.isLeft(actual))
            expect(actual.left.detail).toBe(expected.error);
    }
});
it("replays immutable history entry validation, canonicalization, and history hash", () => {
    for (const [name, expected] of Object.entries(oracle.entries)) {
        const actual = createNativeS2SOptimizationHistoryEntry(entryInputs[name]);
        expect(Either.isRight(actual)).toBe(expected.accepted);
        if (expected.accepted)
            expect(right(nativeS2SOptimizationHistoryEntryCanonical(entryInputs[name]))).toEqual(expected.canonical);
        else if (Either.isLeft(actual))
            expect(actual.left.detail).toBe(expected.error);
    }
    const history = Object.freeze([right(createNativeS2SOptimizationHistoryEntry(entryInputs["zero"])), right(createNativeS2SOptimizationHistoryEntry(entryInputs["one"]))]);
    expect(nativeS2SOptimizationHistorySha256(history)).toEqual(Either.right(oracle.history.sha256));
    expect(Either.isLeft(nativeS2SOptimizationHistorySha256([history[0], null]))).toBe(true);
});
it("preserves nested Python JSON integer, bool, and float lexemes", () => {
    const config = new TextEncoder().encode('{"seed":1,"max_updates":0,"learning_rate":1.5,"beta1":0.5,"beta2":0.75,"epsilon":5e-324,"gradient_clip":3.25,"patience":1,"min_delta":0.0}');
    expect(right(parseNativeS2STrainingConfigRaw(rightJson(config))).seed).toBe(1n);
    const integerFloat = new TextEncoder().encode('{"seed":0,"max_updates":0,"learning_rate":1,"beta1":0.5,"beta2":0.75,"epsilon":1.0,"gradient_clip":1.0,"patience":1,"min_delta":0.0}');
    expect(Either.isLeft(parseNativeS2STrainingConfigRaw(rightJson(integerFloat)))).toBe(true);
    const entry = new TextEncoder().encode('{"update":1,"train_loss":5e-324,"dev_loss":3.5,"gradient_norm":4.25,"clipped":true,"improved":false,"parameters_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}');
    expect(right(parseNativeS2SOptimizationHistoryEntryRaw(rightJson(entry))).trainLoss).toBe(Number.MIN_VALUE);
    const boolAsInteger = new TextEncoder().encode('{"update":1,"train_loss":0.0,"dev_loss":0.0,"gradient_norm":0.0,"clipped":0,"improved":false,"parameters_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}');
    expect(Either.isLeft(parseNativeS2SOptimizationHistoryEntryRaw(rightJson(boolAsInteger)))).toBe(true);
});
const rightJson = (bytes: Uint8Array): unknown => right(decodeNativeTaskJson(bytes));
it("reseals exact protocol config and history representations", () => {
    const config = new TextEncoder().encode('{"beta1_hex":"0x1.0000000000000p-1","beta2_hex":"0x1.8000000000000p-1","epsilon_hex":"0x0.0000000000001p-1022","gradient_clip_hex":"0x1.a000000000000p+1","learning_rate_hex":"0x1.8000000000000p+0","max_updates":0,"min_delta_hex":"0x0.0p+0","patience":1,"seed":18446744073709551615}');
    expect(right(parseNativeS2STrainingConfigJson(config)).seed).toBe(2n ** 64n - 1n);
    const noncanonicalConfig = new TextEncoder().encode(new TextDecoder().decode(config).replace("0x1.0000000000000p-1", "0x1.0p-1"));
    expect(Either.isLeft(parseNativeS2STrainingConfigJson(noncanonicalConfig))).toBe(true);
    const entry = new TextEncoder().encode('{"clipped":true,"dev_loss_hex":"0x1.c000000000000p+1","gradient_norm_hex":"0x1.1000000000000p+2","improved":false,"parameters_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","schema_version":"hswm-swm0w-s2s-optimization-history-entry/v1","train_loss_hex":"0x0.0000000000001p-1022","update":1}');
    expect(right(parseNativeS2SOptimizationHistoryEntryJson(entry)).devLoss).toBe(3.5);
    const negativeZero = new TextEncoder().encode(new TextDecoder().decode(entry).replace("0x1.1000000000000p+2", "-0x0.0p+0"));
    expect(Either.isLeft(parseNativeS2SOptimizationHistoryEntryJson(negativeZero))).toBe(true);
});
it("refuses accessors, non-plain prototypes, sparse histories, and bounded hostile JSON", () => {
    const getterConfig: Record<string, unknown> = {};
    Object.defineProperty(getterConfig, "seed", { enumerable: true, get: () => { expect.fail("getter must not run"); } });
    expect(Either.isLeft(createNativeS2STrainingConfig(getterConfig))).toBe(true);
    const entry = right(createNativeS2SOptimizationHistoryEntry(entryInputs["zero"]));
    const getterEntry: Record<string, unknown> = Object.assign({}, entryInputs["zero"] as Record<string, unknown>);
    Object.defineProperty(getterEntry, "update", { enumerable: true, get: () => { expect.fail("getter must not run"); } });
    expect(Either.isLeft(createNativeS2SOptimizationHistoryEntry(getterEntry))).toBe(true);
    expect(Either.isLeft(createNativeS2STrainingConfig(Object.assign(Object.create(null), { seed: 0n })))).toBe(true);
    const sparse = Array<unknown>(2);
    sparse[0] = entry;
    expect(Either.isLeft(nativeS2SOptimizationHistorySha256(sparse))).toBe(true);
    expect(Either.isLeft(nativeS2SOptimizationHistorySha256(Object.setPrototypeOf([entry], null)))).toBe(true);
    expect(Either.isLeft(parseNativeS2STrainingConfigJson(new Uint8Array(1048577)))).toBe(true);
    expect(Either.isLeft(parseNativeS2STrainingConfigJson(new TextEncoder().encode("[".repeat(130) + "]".repeat(130))))).toBe(true);
});
