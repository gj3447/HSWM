import { readFileSync } from "node:fs";
import { expect, it } from "@effect/vitest";
import { Either } from "effect";
import { parseNativeS2SOptimizationReceipt, parseNativeS2SOptimizationReceiptJson } from "../src/native-s2s-optimization-receipt-domain.js";
import { renderNativeTaskJson } from "../src/native-task-json-domain.js";
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_fit_v1/original_full_task_three_updates.json", import.meta.url), "utf8")) as {
    readonly results: Readonly<Record<string, {
        readonly optimization: unknown;
    }>>;
};
const receipt = fixture.results["0"]!.optimization as Record<string, unknown>;
const original = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_optimization_receipt_v1/original.v1.json", import.meta.url), "utf8")) as {
    readonly valid: Readonly<Record<string, Record<string, unknown>>>;
    readonly resealed_invalid: Readonly<Record<string, {
        readonly receipt: Record<string, unknown>;
        readonly source_result: {
            readonly accepted: boolean;
        };
    }>>;
};
it("replays every original full-task arm and nonzero best checkpoint, refusing a history mutation", () => {
    for (const row of Object.values(fixture.results))
        expect(Either.isRight(parseNativeS2SOptimizationReceipt(row.optimization))).toBe(true);
    const parsed = parseNativeS2SOptimizationReceipt(receipt);
    expect(Either.isRight(parsed)).toBe(true);
    if (Either.isRight(parsed))
        expect(parsed.right.receiptSha256).toBe(receipt["receipt_sha256"]);
    const changed = { ...receipt, history_sha256: "0".repeat(64) };
    expect(Either.isLeft(parseNativeS2SOptimizationReceipt(changed))).toBe(true);
});
it("rejects source-refused nonzero best update claiming the epoch-zero parameter state even with valid hashes", () => {
    const forged = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_optimization_receipt_v1/epoch_zero_identity.v1.json", import.meta.url), "utf8")) as {
        readonly receipt: unknown;
        readonly source_result: {
            readonly accepted: boolean;
        };
    };
    expect(forged.source_result.accepted).toBe(false);
    const result = parseNativeS2SOptimizationReceipt(forged.receipt);
    expect(Either.isLeft(result)).toBe(true);
    if (Either.isLeft(result))
        expect(result.left.detail).toBe("epoch-zero selection and best parameter identity disagree");
});
it("replays every persisted original zero, one-update, and patience receipt plus resealed refusals", () => {
    for (const receipt of Object.values(original.valid)) {
        const direct = Either.getOrThrow(parseNativeS2SOptimizationReceipt(receipt));
        const bytes = Either.getOrThrow(parseNativeS2SOptimizationReceiptJson(Buffer.from(JSON.stringify(receipt))));
        expect(renderNativeTaskJson(bytes.canonical)).toBe(renderNativeTaskJson(direct.canonical));
        expect(bytes.receiptSha256).toBe(receipt["receipt_sha256"]);
    }
    for (const row of Object.values(original.resealed_invalid)) {
        expect(row.source_result.accepted).toBe(false);
        expect(Either.isLeft(parseNativeS2SOptimizationReceipt(row.receipt))).toBe(true);
    }
}, 30000);
it("fails closed before the outer hash for every independently bound receipt field", () => {
    const mutate = (change: Record<string, unknown>): void => expect(Either.isLeft(parseNativeS2SOptimizationReceipt({ ...receipt, ...change }))).toBe(true);
    mutate({ schema_version: "bad" });
    mutate({ operator_architecture_receipt_sha256: "0".repeat(64) });
    mutate({ dataset_schema_sha256: "0".repeat(64) });
    mutate({ train_dataset_sha256: "0".repeat(64) });
    mutate({ initial_parameters_sha256: "0".repeat(64) });
    mutate({ task_manifest_sha256: "0".repeat(64) });
    mutate({ update_count: 4 });
    mutate({ best_update: 99 });
    mutate({ termination_reason: "PATIENCE" });
    const history = receipt["history"] as readonly Record<string, unknown>[];
    mutate({ history: [...history.slice(0, 1), { ...history[1]!, update: 9 }] });
    mutate({ history: [...history, history.at(-1)!] });
    mutate({ history: history.map((entry, index) => index === 1 ? { ...entry, clipped: !entry["clipped"] } : entry) });
    mutate({ history: history.map((entry, index) => index === 1 ? { ...entry, improved: !entry["improved"] } : entry) });
    mutate({ history: history.map((entry, index) => index === 1 ? { ...entry, gradient_norm_hex: "-0x0.0p+0" } : entry) });
    mutate({ best_train_loss_hex: "0x1.0p+0" });
}, 30000);
it("never reads hostile accessors and snapshots caller-owned receipt trees", () => {
    let deep: unknown = null;
    for (let depth = 0; depth < 140; depth++)
        deep = { nested: deep };
    for (const raw of [null, undefined, false, "text", 1, { ...receipt, task_spec: deep }, new Proxy({}, { ownKeys: () => { throw new Error("hostile reflection"); } })])
        expect(Either.isLeft(parseNativeS2SOptimizationReceipt(raw))).toBe(true);
    const getter = { ...receipt } as Record<string, unknown>;
    Object.defineProperty(getter, "history", { enumerable: true, get: () => { expect.fail("receipt getter must not run"); } });
    expect(Either.isLeft(parseNativeS2SOptimizationReceipt(getter))).toBe(true);
    const sparse = { ...receipt, history: (() => { const rows = [...receipt["history"] as readonly unknown[]]; delete rows[1]; return rows; })() };
    expect(Either.isLeft(parseNativeS2SOptimizationReceipt(sparse))).toBe(true);
    const owned = { ...receipt, config: { ...(receipt["config"] as Record<string, unknown>) }, history: [...receipt["history"] as readonly unknown[]] };
    const parsed = parseNativeS2SOptimizationReceipt(owned);
    expect(Either.isRight(parsed)).toBe(true);
    if (Either.isRight(parsed)) {
        (owned.config as Record<string, unknown>)["seed"] = 7;
        expect((parsed.right.canonical["config"] as Record<string, unknown>)["seed"]).toBe(receipt["config"] && (receipt["config"] as Record<string, unknown>)["seed"]);
    }
});
