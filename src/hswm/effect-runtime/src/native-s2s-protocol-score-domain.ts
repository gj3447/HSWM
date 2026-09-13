/** Full finite test-score arithmetic and canonical projection.
 * Model-state provenance is caller supplied; this does not admit a learned model.
 * Native backend qualification remains necessary before protocol promotion.
 */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { enumerateNativeS2STaskCases, nativeS2SFloatHex, nativeS2SPositiveRatio } from "./native-s2s-dataset-domain.js";
import { validateNativeS2STask } from "./native-s2s-family-domain.js";
import { nativeS2SReferenceSquaredNorm } from "./native-s2s-reference-dot-domain.js";
import { renderNativeTaskJson, snapshotNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export const NATIVE_S2S_PROTOCOL_SCORE_SOURCE_SHA256 = "c0df25e37d0e54c792f0eca9f78d83029e4fedd8f837743096eef2b29a62a2c1" as const;
export type NativeS2SScoreVariant = "T16_BASE" | "P_CAP18_BASE" | "DS870_BASE" | "T16_Q_REMOVED" | "T16_RESTORED" | "T16_BROADCAST" | "T16_CYCLE_120" | "T16_CYCLE_201";
type Arm = "T16" | "P_CAP18" | "DS870";
export interface NativeS2SStratumScore {
    readonly role: number;
    readonly channel: number;
    readonly sampleCount: number;
    readonly targetNumeratorSum: bigint;
    readonly targetNumeratorSumSquares: bigint;
    readonly centeredSumSquaresNumerator: bigint;
    readonly squaredError: number;
    readonly r2: number;
}
export interface NativeS2SSixStratumScore {
    readonly variant: NativeS2SScoreVariant;
    readonly arm: Arm;
    readonly taskManifestSha256: string;
    readonly structuralTaskSha256: string;
    readonly learnedStateSha256: string;
    readonly evaluatedStateSha256: string;
    readonly sourceReceiptSha256: string;
    readonly sourcePredictionTensorSha256: string | null;
    readonly testDatasetSha256: string;
    readonly worldCount: number;
    readonly predictionTensorSha256: string;
    readonly targetTensorSha256: string;
    readonly strata: readonly NativeS2SStratumScore[];
    readonly worstRole: number;
    readonly worstChannel: number;
    readonly worstR2: number;
    readonly receiptSha256: string;
}
export class NativeS2SProtocolScoreError extends Data.TaggedError("NativeS2SProtocolScoreError")<{
    readonly reason: "INPUT_INVALID" | "TASK_INVALID" | "NUMERIC_INVALID";
    readonly detail: string;
}> {
}
const fail = (reason: NativeS2SProtocolScoreError["reason"], detail: string): Either.Either<never, NativeS2SProtocolScoreError> => Either.left(new NativeS2SProtocolScoreError({ reason, detail }));
const sha = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
const arms: Readonly<Record<NativeS2SScoreVariant, Arm>> = Object.freeze({ T16_BASE: "T16", P_CAP18_BASE: "P_CAP18", DS870_BASE: "DS870", T16_Q_REMOVED: "T16", T16_RESTORED: "T16", T16_BROADCAST: "T16", T16_CYCLE_120: "T16", T16_CYCLE_201: "T16" });
const variant = (value: unknown): value is NativeS2SScoreVariant => typeof value === "string" && Object.hasOwn(arms, value);
const keys = Object.freeze(["variant", "arm", "learnedStateSha256", "evaluatedStateSha256", "sourceReceiptSha256", "sourcePredictionTensorSha256", "predictions"]);
const dataRecord = (value: unknown): value is Readonly<Record<string, unknown>> => value !== null && typeof value === "object" && !Array.isArray(value) && Object.isFrozen(value) && [Object.prototype, null].includes(Object.getPrototypeOf(value)) && Reflect.ownKeys(value).length === keys.length && keys.every(key => {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return descriptor !== undefined && Object.hasOwn(descriptor, "value");
});
const predictions = (value: unknown): value is readonly number[] => Array.isArray(value) && Object.getPrototypeOf(value) === Array.prototype && Object.isFrozen(value) && value.length === 75000 && Reflect.ownKeys(value).length === 75001 && Array.from({ length: 75000 }, (_, index) => {
    const descriptor = Object.getOwnPropertyDescriptor(value, index);
    return descriptor !== undefined && Object.hasOwn(descriptor, "value") && typeof descriptor.value === "number" && Number.isFinite(descriptor.value);
}).every(Boolean);
const tensor = (values: readonly number[]): string => {
    const bytes = Buffer.alloc(values.length * 8);
    values.forEach((value, index) => bytes.writeDoubleLE(value, index * 8));
    return createHash("sha256").update(renderNativeTaskJson({ bytes_sha256: createHash("sha256").update(bytes).digest("hex"), dtype: "float64-little-endian", shape: [6250, 3, 2, 2] })).digest("hex");
};
type UnsignedScore = Omit<NativeS2SSixStratumScore, "receiptSha256">;
export const nativeS2SScoreUnsigned = (score: UnsignedScore): TaskJson => snapshotNativeTaskJson({
    arm: score.arm, evaluated_state_sha256: score.evaluatedStateSha256, learned_state_sha256: score.learnedStateSha256,
    prediction_tensor_sha256: score.predictionTensorSha256, reduction_order: "LEXICOGRAPHIC_WORLD_THEN_MEMBER_NUMPY_DOT_FLOAT64",
    schema_version: "hswm-swm0w-s2s-six-stratum-score/v1", scientific_status: "CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED",
    source_prediction_tensor_sha256: score.sourcePredictionTensorSha256, source_receipt_sha256: score.sourceReceiptSha256,
    strata: score.strata.map(row => ({ centered_sum_squares_numerator: row.centeredSumSquaresNumerator, channel: row.channel,
        r2_hex: nativeS2SFloatHex(row.r2), role: row.role, sample_count: row.sampleCount, squared_error_hex: nativeS2SFloatHex(row.squaredError),
        target_numerator_sum: row.targetNumeratorSum, target_numerator_sum_squares: row.targetNumeratorSumSquares })),
    structural_task_sha256: score.structuralTaskSha256, target_scale_exponent: 19, target_tensor_sha256: score.targetTensorSha256,
    task_manifest_sha256: score.taskManifestSha256, test_dataset_sha256: score.testDatasetSha256, variant: score.variant,
    world_count: score.worldCount, worst_channel: score.worstChannel, worst_r2_hex: nativeS2SFloatHex(score.worstR2), worst_role: score.worstRole
});
export const scoreNativeS2SCompleteTestPredictions = (task: unknown, input: unknown): Either.Either<NativeS2SSixStratumScore, NativeS2SProtocolScoreError> => Either.gen(function* () {
    const checked = yield* validateNativeS2STask(task).pipe(Either.mapLeft(error => new NativeS2SProtocolScoreError({ reason: "TASK_INVALID", detail: error.detail })));
    if (!dataRecord(input))
        return yield* fail("INPUT_INVALID", "score input must have exactly the frozen data fields");
    const selectedVariant = input["variant"], arm = input["arm"], prediction = input["predictions"], learned = input["learnedStateSha256"], evaluated = input["evaluatedStateSha256"], source = input["sourceReceiptSha256"], sourcePrediction = input["sourcePredictionTensorSha256"];
    if (!variant(selectedVariant) || arm !== arms[selectedVariant] || !sha(learned) || !sha(evaluated) || !sha(source) || !(sourcePrediction === null || sha(sourcePrediction)) || ((selectedVariant === "T16_BROADCAST") !== (sourcePrediction !== null)) || !predictions(prediction))
        return yield* fail("INPUT_INVALID", "invalid score provenance or complete prediction tensor");
    const cases = yield* enumerateNativeS2STaskCases(checked, "test").pipe(Either.mapLeft(error => new NativeS2SProtocolScoreError({ reason: "TASK_INVALID", detail: error.detail })));
    const targets = Object.freeze(cases.flatMap(entry => entry.targetNumerators.flatMap(row => [row[0] / 2 ** 19, row[1] / 2 ** 19])));
    const strata: NativeS2SStratumScore[] = [];
    for (let role = 0; role < 3; role += 1)
        for (let channel = 0; channel < 2; channel += 1) {
            let sum = 0n, squares = 0n;
            const residuals: number[] = [];
            for (let world = 0; world < 6250; world += 1)
                for (let member = 0; member < 2; member += 1) {
                    const offset = world * 12 + (role * 2 + member) * 2 + channel;
                    const numerator = BigInt(cases[world]!.targetNumerators[role * 2 + member]![channel]!);
                    sum += numerator;
                    squares += numerator * numerator;
                    const residual = targets[offset]! - prediction[offset]!;
                    residuals.push(residual);
                }
            const squaredError = yield* nativeS2SReferenceSquaredNorm(Object.freeze(residuals)).pipe(Either.mapLeft(error => new NativeS2SProtocolScoreError({ reason: "NUMERIC_INVALID", detail: error.detail })));
            const centered = 12500n * squares - sum * sum;
            const denominator = yield* nativeS2SPositiveRatio(centered, 12500n * 2n ** 38n).pipe(Either.mapLeft(error => new NativeS2SProtocolScoreError({ reason: "NUMERIC_INVALID", detail: error.detail })));
            const r2 = 1 - squaredError / denominator;
            if (!Number.isFinite(squaredError) || !Number.isFinite(r2))
                return yield* fail("NUMERIC_INVALID", "nonfinite score reduction");
            strata.push(Object.freeze({ role, channel, sampleCount: 12500, targetNumeratorSum: sum, targetNumeratorSumSquares: squares, centeredSumSquaresNumerator: centered, squaredError: squaredError === 0 ? 0 : squaredError, r2: r2 === 0 ? 0 : r2 }));
        }
    const worst = strata.reduce((left, right) => right.r2 < left.r2 ? right : left);
    const dataset = createHash("sha256").update("hswm-swm0w-s2s-test-dataset/v1\0").update(Buffer.from(checked.structuralTaskSha256, "hex"));
    // The source binds the entire world block before the entire numerator block.
    for (const entry of cases)
        dataset.update(Buffer.from(entry.rawValues));
    for (const entry of cases)
        for (const row of entry.targetNumerators)
            for (const numerator of row) {
                const bytes = Buffer.alloc(8);
                bytes.writeBigInt64BE(BigInt(numerator));
                dataset.update(bytes);
            }
    const score: UnsignedScore = Object.freeze({ variant: selectedVariant, arm: arms[selectedVariant], taskManifestSha256: checked.manifestSha256,
        structuralTaskSha256: checked.structuralTaskSha256, learnedStateSha256: learned, evaluatedStateSha256: evaluated, sourceReceiptSha256: source,
        sourcePredictionTensorSha256: sourcePrediction, testDatasetSha256: dataset.digest("hex"), worldCount: 6250,
        predictionTensorSha256: tensor(prediction), targetTensorSha256: tensor(targets), strata: Object.freeze(strata),
        worstRole: worst.role, worstChannel: worst.channel, worstR2: worst.r2 });
    return Object.freeze({ ...score, receiptSha256: createHash("sha256").update(renderNativeTaskJson(nativeS2SScoreUnsigned(score))).digest("hex") });
});
