import { archiveNativeS2SModel } from "../src/native-s2s-model-protocol-domain.js";
import { readFileSync } from "node:fs";
import { expect, it } from "@effect/vitest";
import { Either } from "effect";
import { buildNativeS2SOptimizationReceipt } from "../src/native-s2s-optimization-build-domain.js";
import { parseNativeS2STaskArchiveEntry } from "../src/native-s2s-task-archive-domain.js";
import { parseNativeS2SOptimizationReceipt } from "../src/native-s2s-optimization-receipt-domain.js";
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_optimization_receipt_v1/original.v1.json", import.meta.url), "utf8")) as {
    readonly valid: Readonly<Record<string, Record<string, unknown>>>;
};
const task = fixture.valid["zero"]!["task_spec"];
const right = <A>(v: Either.Either<A, unknown>): A => { expect(Either.isRight(v)).toBe(true); return Either.isRight(v) ? v.right : expect.fail("right"); };
it("builds actual native zero, one-update, and patience fit receipts that reparse", () => {
    for (const config of [{ maxUpdates: 0, seed: 0n, learningRate: .01, beta1: .9, beta2: .999, epsilon: 1e-8, gradientClip: 5, patience: 25, minDelta: 1e-9 }, { maxUpdates: 1, seed: 0n, learningRate: .01, beta1: .9, beta2: .999, epsilon: 1e-8, gradientClip: 5, patience: 25, minDelta: 1e-9 }, { maxUpdates: 5, seed: 0n, learningRate: .01, beta1: .9, beta2: .999, epsilon: 1e-8, gradientClip: 5, patience: 1, minDelta: 1e99 }]) {
        const built = right(buildNativeS2SOptimizationReceipt(right(parseNativeS2STaskArchiveEntry(task)), "T16", config));
        expect(Either.isRight(parseNativeS2SOptimizationReceipt(built.receipt.canonical))).toBe(true);
    }
}, 30000);
it("binds each native arm to its actual fit-state commitment", () => {
    const config = { maxUpdates: 0, seed: 0n, learningRate: .01, beta1: .9, beta2: .999, epsilon: 1e-8, gradientClip: 5, patience: 25, minDelta: 1e-9 };
    for (const arm of ["T16", "P_CAP18", "DS870"] as const)
        expect(Either.isRight(buildNativeS2SOptimizationReceipt(right(parseNativeS2STaskArchiveEntry(task)), arm, config))).toBe(true);
}, 30000);
it("feeds actual native best parameters into source-compatible learned-model reconstruction without refitting", () => {
    const config = { maxUpdates: 3, seed: 0n, learningRate: 0.0001, beta1: .9, beta2: .999, epsilon: 1e-8, gradientClip: 5, patience: 25, minDelta: 1e-9 };
    const built = right(buildNativeS2SOptimizationReceipt(right(parseNativeS2STaskArchiveEntry(task)), "T16", config));
    const archive = right(archiveNativeS2SModel("T16", built.parameters, built.receipt.canonical));
    expect(archive.learned).toBe(true);
    expect(built.fit.bestUpdate).toBe(2);
    expect(archive.parametersSha256).toBe(built.fit.bestParametersSha256);
    expect(archive.optimization.receiptSha256).toBe(built.receipt.receiptSha256);
}, 60000);
