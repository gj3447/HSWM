import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { Either } from "effect";
import { parseNativeS2STaskArchiveEntry } from "../src/native-s2s-task-archive-domain.js";
import { renderNativeTaskJson } from "../src/native-task-json-domain.js";
import { nativeS2SFloatHex } from "../src/native-s2s-dataset-domain.js";
import { nativeS2SScoreUnsigned, scoreNativeS2SCompleteTestPredictions } from "../src/native-s2s-protocol-score-domain.js";
interface Oracle {
    readonly task: unknown;
    readonly input: Readonly<Record<string, unknown>>;
    readonly expected: Readonly<Record<string, unknown>>;
    readonly canonical_unsigned?: string;
    readonly expected_canonical_unsigned?: string;
}
const read = (name: string): Oracle => JSON.parse(readFileSync(new URL(`../../../../tests/fixtures/native_migration/s2s_protocol_score_v1/${name}.json`, import.meta.url), "utf8")) as Oracle;
const input = (oracle: Oracle): Readonly<Record<string, unknown>> => Object.freeze({
    variant: oracle.input["variant"], arm: oracle.input["arm"], learnedStateSha256: oracle.input["learned_state_sha256"],
    evaluatedStateSha256: oracle.input["evaluated_state_sha256"], sourceReceiptSha256: oracle.input["source_receipt_sha256"],
    sourcePredictionTensorSha256: oracle.input["source_prediction_tensor_sha256"], predictions: Object.freeze(structuredClone(oracle.input["predictions"]))
});
describe("source-bound complete S2S score arithmetic", () => {
    it.each(["original_python", "original_nonzero_python"])("matches all canonical receipt bytes for %s", name => {
        const oracle = read(name), task = parseNativeS2STaskArchiveEntry(oracle.task);
        expect(Either.isRight(task)).toBe(true);
        if (Either.isLeft(task))
            return;
        const actual = scoreNativeS2SCompleteTestPredictions(task.right, input(oracle));
        if (Either.isLeft(actual))
            expect(actual.left.detail).toBe("successful score");
        expect(Either.isRight(actual)).toBe(true);
        if (Either.isLeft(actual))
            return;
        const expectedBytes = oracle.canonical_unsigned ?? oracle.expected_canonical_unsigned;
        expect(actual.right.strata.map(row => [nativeS2SFloatHex(row.squaredError), nativeS2SFloatHex(row.r2)])).toEqual((oracle.expected["strata"] as readonly Readonly<Record<string, unknown>>[]).map(row => [row["squared_error_hex"], row["r2_hex"]]));
        const actualBytes = renderNativeTaskJson(nativeS2SScoreUnsigned(actual.right));
        expect(actualBytes).toBe(expectedBytes);
        expect(createHash("sha256").update(actualBytes).digest("hex")).toBe(oracle.expected["receipt_sha256"]);
        expect(actual.right.receiptSha256).toBe(oracle.expected["receipt_sha256"]);
    }, 30000);
    it("refuses malformed provenance, sparse tensors, accessors and nonfinite arithmetic", () => {
        const oracle = read("original_python"), task = parseNativeS2STaskArchiveEntry(oracle.task), valid = input(oracle);
        expect(Either.isRight(task)).toBe(true);
        if (Either.isLeft(task))
            return;
        let reads = 0;
        const getter = Object.freeze(Object.defineProperty({ ...valid }, "predictions", { get: () => { reads += 1; return valid["predictions"]; } }));
        const sparse = Object.freeze(Array<number>(75000));
        const cases = [getter, Object.freeze({ ...valid, predictions: sparse }), Object.freeze({ ...valid, variant: "toString" }),
            Object.freeze({ ...valid, arm: "DS870" }), Object.freeze({ ...valid, learnedStateSha256: "unbound" }),
            Object.freeze({ ...valid, variant: "T16_BROADCAST" }), Object.freeze({ ...valid, sourcePredictionTensorSha256: "a".repeat(64) }),
            Object.freeze({ ...valid, extra: 1 }), Object.freeze({ ...valid, predictions: Object.freeze(Array<number>(75000).fill(Number.MAX_VALUE)) })];
        for (const candidate of cases)
            expect(Either.isLeft(scoreNativeS2SCompleteTestPredictions(task.right, candidate))).toBe(true);
        expect(reads).toBe(0);
    }, 30000);
});
