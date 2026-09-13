/** Pure verifier for source-bound S2S optimization receipts; it makes no admission claim. */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { compileNativeS2STaskData, nativeS2SDatasetSchemaSha256, nativeS2SFloatHex, type NativeS2SStratumLossReceipt } from "./native-s2s-dataset-domain.js";
import { nativeS2SParameterSha256 } from "./native-s2s-fit-domain.js";
import { initializeNativeS2STrainingParameters } from "./native-s2s-initialization-domain.js";
import { NATIVE_S2S_OPERATOR_ARCHITECTURE_RECEIPT_SHA256 } from "./native-s2s-operator-domain.js";
import { parseNativeS2STaskArchiveEntry } from "./native-s2s-task-archive-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, validNativeTaskJson, nativeTaskSourceKeys, type TaskJson } from "./native-task-json-domain.js";
import { NATIVE_S2S_HISTORY_VERSION, nativeS2SOptimizationHistorySha256, parseNativeS2SOptimizationHistoryEntry, parseNativeS2STrainingConfig } from "./native-s2s-training-receipt-fields-domain.js";
export class NativeS2SOptimizationReceiptError extends Data.TaggedError("NativeS2SOptimizationReceiptError")<{
    readonly detail: string;
}> {
}
export interface NativeS2SOptimizationReceipt {
    readonly canonical: Readonly<Record<string, TaskJson>>;
    readonly receiptSha256: string;
    readonly scientificStatus: "LEARNED_ENGINEERING_ARTIFACT_UNJUDGED";
}
const fail = (detail: string): Either.Either<never, NativeS2SOptimizationReceiptError> => Either.left(new NativeS2SOptimizationReceiptError({ detail }));
const sha = (value: TaskJson | undefined): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
const integer = (value: TaskJson | undefined): value is number | bigint => typeof value === "number" && Number.isSafeInteger(value) || typeof value === "bigint";
const number = (value: number | bigint): number | undefined => { const n = Number(value); return Number.isSafeInteger(n) ? n : undefined; };
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128)
            return false;
        if (value === null || typeof value !== "object")
            return true;
        if (!Reflect.ownKeys(value).every(key => { const d = Object.getOwnPropertyDescriptor(value, key); return d !== undefined && Object.hasOwn(d, "value") && dataOnly(d.value, depth + 1); }))
            return false;
        if (Array.isArray(value))
            return Object.getPrototypeOf(value) === Array.prototype && Object.keys(value).length === value.length && Array.from({ length: value.length }, (_, index) => Object.hasOwn(value, index)).every(Boolean);
        return true;
    }
    catch {
        return false;
    }
};
const safeJson = (value: unknown): value is TaskJson => {
    try {
        if (!dataOnly(value) || !validNativeTaskJson(value))
            return false;
        const sourceOrderValid = (node: TaskJson): boolean => Array.isArray(node) ? node.every(sourceOrderValid) : taskJsonRecord(node) ? (() => { const keys = Object.keys(node), order = nativeTaskSourceKeys(node); return order.length === keys.length && new Set(order).size === keys.length && order.every(key => typeof key === "string" && Object.hasOwn(node, key)) && Object.values(node).every(sourceOrderValid); })() : true;
        return sourceOrderValid(value);
    }
    catch {
        return false;
    }
};
const data = (value: unknown, keys: readonly string[]): value is Readonly<Record<string, TaskJson>> => safeJson(value) && taskJsonRecord(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const strataCanonical = (strata: readonly NativeS2SStratumLossReceipt[]): readonly TaskJson[] => Object.freeze(strata.map(row => Object.freeze({ centered_sum_squares_numerator: row.centeredSumSquaresNumerator, channel: row.channel, inverse_variance_weight_hex: nativeS2SFloatHex(row.inverseVarianceWeight), receipt_sha256: row.receiptSha256, role: row.role, sample_count: row.sampleCount, schema_version: "hswm-swm0w-s2s-stratum-loss/v1", target_numerator_sum: row.targetNumeratorSum, target_numerator_sum_squares: row.targetNumeratorSumSquares, target_scale_exponent: 19, variance_definition: "POPULATION_VARIANCE=(N*SUMSQ-SUM^2)/(N^2*2^(2*SCALE_EXPONENT))" })));
const hash = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex");
const fixed: Readonly<Record<string, string>> = Object.freeze({ dataset_bytes_version: "hswm-swm0w-s2s-dataset-bytes/v1", history_version: NATIVE_S2S_HISTORY_VERSION, initialization_version: "hswm-swm0w-s2s-task-independent-zero-output-initialization/v1", optimizer_version: "hswm-swm0w-s2s-full-batch-adam/v1", receipt_assurance: "SELF_CONSISTENT_COMMITMENT_REQUIRES_DETERMINISTIC_REPLAY", schema_version: "hswm-swm0w-s2s-optimization-receipt/v1", scientific_status: "LEARNED_ENGINEERING_ARTIFACT_UNJUDGED", training_version: "hswm-swm0w-s2s-training/v1" });
const keys = ["arm", "best_dev_loss_hex", "best_parameters_sha256", "best_train_loss_hex", "best_update", "clipped_update_count", "config", "dataset_bytes_version", "dataset_schema_sha256", "dev_case_count", "dev_dataset_sha256", "family_certificate_sha256", "family_definition_sha256", "history", "history_entry_count", "history_sha256", "history_version", "initial_parameters_sha256", "initialization_version", "loss_definition_sha256", "operator_architecture_receipt_sha256", "optimizer_version", "receipt_assurance", "receipt_sha256", "schema_version", "scientific_status", "stopped_update", "stratum_loss_receipts", "structural_target_sha256", "structural_task_sha256", "task_manifest_sha256", "task_spec", "termination_reason", "train_case_count", "train_dataset_sha256", "training_version", "update_count"] as const;
/** Exact structural and deterministic receipt checks, without training replay or model admission. */
export const parseNativeS2SOptimizationReceipt = (raw: unknown): Either.Either<NativeS2SOptimizationReceipt, NativeS2SOptimizationReceiptError> => Either.gen(function* () {
    if (!data(raw, keys))
        return yield* fail("optimization receipt keys disagree with the exact schema");
    const value = snapshotNativeTaskJson(raw) as Readonly<Record<string, TaskJson>>;
    for (const [key, expected] of Object.entries(fixed))
        if (value[key] !== expected)
            return yield* fail("optimization fixed contract drifted");
    if (value["arm"] !== "P_CAP18" && value["arm"] !== "T16" && value["arm"] !== "DS870")
        return yield* fail("optimization arm is unsupported");
    const arm = value["arm"];
    const task = yield* parseNativeS2STaskArchiveEntry(value["task_spec"]).pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail })));
    const config = yield* parseNativeS2STrainingConfig(value["config"]).pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail })));
    for (const key of ["family_definition_sha256", "family_certificate_sha256", "structural_target_sha256", "structural_task_sha256", "task_manifest_sha256", "train_dataset_sha256", "dev_dataset_sha256", "dataset_schema_sha256", "loss_definition_sha256", "operator_architecture_receipt_sha256", "initial_parameters_sha256", "best_parameters_sha256", "history_sha256", "receipt_sha256"] as const)
        if (!sha(value[key]))
            return yield* fail(`${key} must be lowercase SHA-256`);
    if (value["family_definition_sha256"] !== task.familyDefinitionSha256 || value["family_certificate_sha256"] !== task.familyCertificateSha256 || value["structural_target_sha256"] !== task.structuralTargetSha256 || value["structural_task_sha256"] !== task.structuralTaskSha256 || value["task_manifest_sha256"] !== task.manifestSha256)
        return yield* fail("optimization receipt task bindings disagree");
    const schema = yield* nativeS2SDatasetSchemaSha256().pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail })));
    if (value["dataset_schema_sha256"] !== schema)
        return yield* fail("optimization receipt dataset schema drifted");
    if (value["operator_architecture_receipt_sha256"] !== NATIVE_S2S_OPERATOR_ARCHITECTURE_RECEIPT_SHA256[arm])
        return yield* fail("optimization receipt operator architecture drifted");
    const initial = yield* initializeNativeS2STrainingParameters(arm, config.seed).pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail })));
    if (value["initial_parameters_sha256"] !== nativeS2SParameterSha256(initial, arm))
        return yield* fail("optimization receipt deterministic initialization drifted");
    const compiled = yield* compileNativeS2STaskData(task).pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail })));
    const expectedStrata = strataCanonical(compiled.strata);
    if (renderNativeTaskJson(value["stratum_loss_receipts"]!) !== renderNativeTaskJson(expectedStrata) || value["train_dataset_sha256"] !== compiled.trainDatasetSha256 || value["dev_dataset_sha256"] !== compiled.devDatasetSha256)
        return yield* fail("optimization receipt task-derived data drifted");
    const loss = hash({ aggregation: "MEAN_OF_SIX_ROLE_CHANNEL_NORMALIZED_MSE_STRATA", dev_weight_source: "EXACT_COMPLETE_TRAIN_TARGET_NUMERATORS_ONLY", schema_version: "hswm-swm0w-s2s-six-stratum-loss/v1", strata: expectedStrata, target_scale_exponent: 19 });
    if (value["loss_definition_sha256"] !== loss)
        return yield* fail("loss definition hash mismatch");
    if (!Array.isArray(value["history"]) || value["history"].length === 0)
        return yield* fail("history must be a nonempty exact array");
    const parsedHistory = value["history"].map(entry => parseNativeS2SOptimizationHistoryEntry(entry).pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail }))));
    const history = yield* Either.all(parsedHistory);
    const updates = [value["best_update"], value["stopped_update"], value["update_count"], value["clipped_update_count"], value["history_entry_count"], value["train_case_count"], value["dev_case_count"]].map(item => integer(item) ? number(item) : undefined);
    if (updates.some(item => item === undefined))
        return yield* fail("optimization integer fields are invalid");
    const bestUpdate = updates[0]!, stoppedUpdate = updates[1]!, updateCount = updates[2]!, clippedCount = updates[3]!, historyCount = updates[4]!, trainCount = updates[5]!, devCount = updates[6]!;
    if (trainCount !== 6250 || devCount !== 3125 || stoppedUpdate !== updateCount || updateCount > config.maxUpdates || historyCount !== updateCount + 1 || history.length !== historyCount || history.some((entry, index) => entry.update !== index))
        return yield* fail("optimization update or complete-dataset counts are inconsistent");
    const historySha = yield* nativeS2SOptimizationHistorySha256(history).pipe(Either.mapLeft(error => new NativeS2SOptimizationReceiptError({ detail: error.detail })));
    if (value["history_sha256"] !== historySha || history[0]!.parametersSha256 !== value["initial_parameters_sha256"])
        return yield* fail("optimization history binding disagrees");
    let best = history[0]!, stale = 0, patienceAt: number | undefined;
    for (const entry of history.slice(1)) {
        if (entry.gradientNorm === null || entry.clipped !== (entry.gradientNorm > config.gradientClip) || entry.improved !== (entry.devLoss < best.devLoss - config.minDelta))
            return yield* fail("history flags disagree with optimizer semantics");
        if (entry.improved) {
            best = entry;
            stale = 0;
        }
        else {
            stale += 1;
            if (stale >= config.patience) {
                patienceAt = entry.update;
                if (entry.update !== updateCount)
                    return yield* fail("history continues after patience was exhausted");
            }
        }
    }
    if (clippedCount !== history.slice(1).filter(entry => entry.clipped).length || bestUpdate !== best.update || value["best_parameters_sha256"] !== best.parametersSha256)
        return yield* fail("best checkpoint binding disagrees");
    if ((bestUpdate === 0) !== (value["best_parameters_sha256"] === value["initial_parameters_sha256"]))
        return yield* fail("epoch-zero selection and best parameter identity disagree");
    const bestTrain = value["best_train_loss_hex"], bestDev = value["best_dev_loss_hex"];
    if (typeof bestTrain !== "string" || typeof bestDev !== "string" || nativeS2SFloatHex(best.trainLoss) !== bestTrain || nativeS2SFloatHex(best.devLoss) !== bestDev || value["termination_reason"] !== (patienceAt === updateCount ? "PATIENCE" : "MAX_UPDATES") || (patienceAt !== updateCount && updateCount !== config.maxUpdates))
        return yield* fail("best loss or termination binding disagrees");
    const unsigned = Object.fromEntries(keys.filter(key => key !== "receipt_sha256").map(key => [key, value[key]])) as Readonly<Record<string, TaskJson>>;
    if (hash(unsigned) !== value["receipt_sha256"])
        return yield* fail("optimization receipt hash mismatch");
    return Object.freeze({ canonical: snapshotNativeTaskJson({ ...unsigned, receipt_sha256: value["receipt_sha256"] }) as Readonly<Record<string, TaskJson>>, receiptSha256: value["receipt_sha256"]!, scientificStatus: "LEARNED_ENGINEERING_ARTIFACT_UNJUDGED" });
});
export const parseNativeS2SOptimizationReceiptJson = (bytes: Uint8Array) => decodeNativeTaskJson(bytes).pipe(Either.mapLeft(() => new NativeS2SOptimizationReceiptError({ detail: "optimization receipt JSON is invalid" })), Either.flatMap(parseNativeS2SOptimizationReceipt));
