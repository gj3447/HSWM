/**
 * Immutable finite-dataset compiler for the native SWM-0W S2S V2 family.
 * This ports the historical training data boundary for engineering parity;
 * it does not establish fit, efficacy, or any scientific outcome.
 */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { compileNativeS2STaskEvaluator, validateNativeS2STask, type NativeS2SCase, type NativeS2SSplit } from "./native-s2s-family-domain.js";
import { renderNativeTaskJson, validNativeTaskJson } from "./native-task-json-domain.js";
export const NATIVE_S2S_DATASET_SOURCE_SHA256 = "d84b8336d8bcbe89aeba7f2d2c915fd294b9ee24425e6092505069a74f9cba94" as const;
export const NATIVE_S2S_DATASET_SCIENTIFIC_STATUS = "UNJUDGED_ENGINEERING_PARITY_ONLY" as const;
export const NATIVE_S2S_DATASET_BYTES_VERSION = "hswm-swm0w-s2s-dataset-bytes/v1" as const;
export const NATIVE_S2S_STRATUM_LOSS_RECEIPT_VERSION = "hswm-swm0w-s2s-stratum-loss/v1" as const;
export const NATIVE_S2S_TARGET_SCALE_EXPONENT = 19 as const;
export const NATIVE_S2S_TRAIN_CASE_COUNT = 6250 as const;
export const NATIVE_S2S_DEV_CASE_COUNT = 3125 as const;
export const NATIVE_S2S_TEST_CASE_COUNT = 6250 as const;
const DATASET_HASH_DOMAIN = Buffer.from("hswm-swm0w-s2s-dataset-bytes/v1\0", "utf8");
const SPLIT_COUNTS: Readonly<Record<NativeS2SSplit, number>> = Object.freeze({ train: NATIVE_S2S_TRAIN_CASE_COUNT, dev: NATIVE_S2S_DEV_CASE_COUNT, test: NATIVE_S2S_TEST_CASE_COUNT });
export class NativeS2SDatasetError extends Data.TaggedError("NativeS2SDatasetError")<{
    readonly reason: "CASES_INVALID" | "CANONICAL_INVALID" | "DATASET_INVALID" | "TASK_INVALID";
    readonly detail: string;
}> {
}
export interface NativeS2SStratumLossReceipt {
    readonly role: number;
    readonly channel: number;
    readonly sampleCount: number;
    readonly targetNumeratorSum: bigint;
    readonly targetNumeratorSumSquares: bigint;
    readonly centeredSumSquaresNumerator: bigint;
    readonly inverseVarianceWeight: number;
    readonly receiptSha256: string;
}
export interface NativeS2SCompiledTaskData {
    readonly trainDatasetSha256: string;
    readonly devDatasetSha256: string;
    readonly strata: readonly NativeS2SStratumLossReceipt[];
    readonly weights: readonly number[];
    readonly trainInput: readonly number[];
    readonly trainTargets: readonly number[];
    readonly devInput: readonly number[];
    readonly devTargets: readonly number[];
    readonly scientificStatus: typeof NATIVE_S2S_DATASET_SCIENTIFIC_STATUS;
}
const fail = (reason: NativeS2SDatasetError["reason"], detail: string): Either.Either<never, NativeS2SDatasetError> => Either.left(new NativeS2SDatasetError({ reason, detail }));
const frozen = <T>(value: T): T => Object.freeze(value);
const rawKey = (raw: readonly number[]): string => raw.join(",");
const dense = (value: unknown, length: number): value is readonly unknown[] => Array.isArray(value) && value.length === length && Array.from({ length }, (_, index) => Object.hasOwn(value, index)).every(Boolean);
const exactInteger = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value);
const exactRow = (value: unknown): value is readonly [
    number,
    number
] => dense(value, 2) && exactInteger(value[0]) && exactInteger(value[1]);
const exactFloatRow = (value: unknown): value is readonly [
    number,
    number
] => dense(value, 2) && typeof value[0] === "number" && Number.isFinite(value[0]) && typeof value[1] === "number" && Number.isFinite(value[1]);
const nativeCase = (value: unknown): value is NativeS2SCase => value !== null && typeof value === "object" && !Array.isArray(value) && Object.isFrozen(value) &&
    typeof (value as {
        readonly taskManifestSha256?: unknown;
    }).taskManifestSha256 === "string" && /^[0-9a-f]{64}$/.test((value as {
    readonly taskManifestSha256: string;
}).taskManifestSha256) &&
    Array.isArray((value as {
        readonly rawValues?: unknown;
    }).rawValues) && Object.isFrozen((value as {
    readonly rawValues: readonly unknown[];
}).rawValues) && dense((value as {
    readonly rawValues?: unknown;
}).rawValues, 6) && (value as {
    readonly rawValues: readonly unknown[];
}).rawValues.every((item) => typeof item === "number" && Number.isInteger(item) && item >= 0 && item < 5) &&
    Array.isArray((value as {
        readonly targetNumerators?: unknown;
    }).targetNumerators) && Object.isFrozen((value as {
    readonly targetNumerators: readonly unknown[];
}).targetNumerators) && dense((value as {
    readonly targetNumerators?: unknown;
}).targetNumerators, 6) && (value as {
    readonly targetNumerators: readonly unknown[];
}).targetNumerators.every((item) => Object.isFrozen(item) && exactRow(item)) &&
    Array.isArray((value as {
        readonly targetFloats?: unknown;
    }).targetFloats) && Object.isFrozen((value as {
    readonly targetFloats: readonly unknown[];
}).targetFloats) && dense((value as {
    readonly targetFloats?: unknown;
}).targetFloats, 6) && (value as {
    readonly targetFloats: readonly unknown[];
}).targetFloats.every((item) => Object.isFrozen(item) && exactFloatRow(item)) &&
    ((value as {
        readonly split?: unknown;
    }).split === "train" || (value as {
        readonly split?: unknown;
    }).split === "dev" || (value as {
        readonly split?: unknown;
    }).split === "test");
const sameRow = (left: readonly number[], right: readonly number[]): boolean => left.length === right.length && left.every((value, index) => value === right[index]);
const sameCase = (left: NativeS2SCase, right: NativeS2SCase): boolean => left.split === right.split && sameRow(left.rawValues, right.rawValues) &&
    left.targetNumerators.length === right.targetNumerators.length && left.targetNumerators.every((row, index) => sameRow(row, right.targetNumerators[index]!)) &&
    left.targetFloats.length === right.targetFloats.length && left.targetFloats.every((row, index) => sameRow(row, right.targetFloats[index]!));
const rawValues = (a: number, b: number, c: number, d: number, e: number, f: number): readonly [
    number,
    number,
    number,
    number,
    number,
    number
] => frozen([a, b, c, d, e, f] as const);
const allRawValues = (): readonly (readonly [
    number,
    number,
    number,
    number,
    number,
    number
])[] => {
    const rows: (readonly [
        number,
        number,
        number,
        number,
        number,
        number
    ])[] = [];
    for (let a = 0; a < 5; a += 1)
        for (let b = 0; b < 5; b += 1)
            for (let c = 0; c < 5; c += 1)
                for (let d = 0; d < 5; d += 1)
                    for (let e = 0; e < 5; e += 1)
                        for (let f = 0; f < 5; f += 1)
                            rows.push(rawValues(a, b, c, d, e, f));
    return frozen(rows);
};
const allRows = allRawValues();
const canonicalSha = (value: unknown): Either.Either<string, NativeS2SDatasetError> => validNativeTaskJson(value)
    ? Either.right(createHash("sha256").update(renderNativeTaskJson(value, "canonical"), "utf8").digest("hex"))
    : fail("CANONICAL_INVALID", "canonical receipt payload contains an unsupported value");
export const nativeS2SFloatHex = (value: number): string => {
    if (!Number.isFinite(value))
        return value === Infinity ? "inf" : value === -Infinity ? "-inf" : "nan";
    if (value === 0)
        return Object.is(value, -0) ? "-0x0.0p+0" : "0x0.0p+0";
    const bytes = Buffer.alloc(8);
    bytes.writeDoubleLE(value);
    const bits = bytes.readBigUInt64LE();
    const sign = (bits >> 63n) === 1n ? "-" : "";
    const exponent = Number((bits >> 52n) & 0x7ffn);
    const fraction = bits & ((1n << 52n) - 1n);
    if (exponent === 0)
        return `${sign}0x0.${fraction.toString(16).padStart(13, "0")}p-1022`;
    const digits = fraction.toString(16).padStart(13, "0");
    const power = exponent - 1023;
    return `${sign}0x1.${digits}p${power >= 0 ? "+" : ""}${power}`;
};
const bitLength = (value: bigint): number => value.toString(2).length;
const floorLog2Ratio = (numerator: bigint, denominator: bigint): number => {
    let power = bitLength(numerator) - bitLength(denominator);
    const scaledNumerator = power < 0 ? numerator << BigInt(-power) : numerator;
    const scaledDenominator = power > 0 ? denominator << BigInt(power) : denominator;
    if (scaledNumerator < scaledDenominator)
        power -= 1;
    return power;
};
const divideRoundEven = (numerator: bigint, denominator: bigint): bigint => {
    const quotient = numerator / denominator, remainder = numerator % denominator, doubled = remainder * 2n;
    return doubled > denominator || (doubled === denominator && (quotient & 1n) === 1n) ? quotient + 1n : quotient;
};
const rationalToFloat64 = (numerator: bigint, denominator: bigint): number => {
    const power = Math.max(-1022, floorLog2Ratio(numerator, denominator));
    if (power > 1023)
        return Infinity;
    const scaledNumerator = power <= 52 ? numerator << BigInt(52 - power) : numerator;
    const scaledDenominator = power <= 52 ? denominator : denominator << BigInt(power - 52);
    let significand = divideRoundEven(scaledNumerator, scaledDenominator);
    let exponent = power;
    if (significand === 1n << 53n) {
        significand >>= 1n;
        exponent += 1;
    }
    if (exponent > 1023)
        return Infinity;
    const bits = exponent === -1022 && significand < 1n << 52n ? significand : BigInt(exponent + 1023) << 52n | (significand & ((1n << 52n) - 1n));
    const bytes = Buffer.alloc(8);
    bytes.writeBigUInt64LE(bits);
    return bytes.readDoubleLE();
};
const f64Bytes = (values: readonly number[]): Buffer => {
    const result = Buffer.alloc(values.length * 8);
    values.forEach((value, index) => result.writeDoubleLE(value, index * 8));
    return result;
};
const inputTensor = (cases: readonly NativeS2SCase[]): readonly number[] => frozen(cases.flatMap((entry) => entry.rawValues.flatMap((value) => [Number(value === 0) - Number(value === 4), Number(value === 1) - Number(value === 4), Number(value === 2) - Number(value === 4), Number(value === 3) - Number(value === 4)])));
const targetTensor = (cases: readonly NativeS2SCase[]): readonly number[] => frozen(cases.flatMap((entry) => entry.targetNumerators.flatMap((row) => [row[0]! / 2 ** NATIVE_S2S_TARGET_SCALE_EXPONENT, row[1]! / 2 ** NATIVE_S2S_TARGET_SCALE_EXPONENT])));
const datasetSchemaSha256 = (): Either.Either<string, NativeS2SDatasetError> => canonicalSha({
    canonical_order: "LEXICOGRAPHIC_RAW_VALUES_ASCENDING",
    case_bytes: [{ dtype: "uint8", field: "raw_values", shape: [6] }, { byte_order: "big", dtype: "int64", field: "target_numerators", shape: [6, 2] }],
    compiled_model_input: { byte_order: "little", dtype: "float64", order: "C", shape: ["N", 3, 2, 4] },
    compiled_target: { byte_order: "little", dtype: "float64", order: "C", shape: ["N", 3, 2, 2], source: "target_numerators/2^19" },
    hash_segment_order: ["domain", "dataset_schema_sha256", "structural_task_sha256", "split_length_and_ascii", "case_count_uint64_big", "lexicographic_case_bytes", "compiled_model_input_length_and_bytes", "compiled_target_length_and_bytes"],
    schema_version: NATIVE_S2S_DATASET_BYTES_VERSION,
    task_binding: "structural_task_sha256_raw_32_bytes"
});
export const enumerateNativeS2STaskCases = (task: unknown, split?: NativeS2SSplit): Either.Either<readonly NativeS2SCase[], NativeS2SDatasetError> => {
    if (split !== undefined && split !== "train" && split !== "dev" && split !== "test")
        return fail("CASES_INVALID", "split must be train, dev, test, or absent");
    const checked = validateNativeS2STask(task);
    if (Either.isLeft(checked))
        return fail("TASK_INVALID", checked.left.detail);
    const evaluator = compileNativeS2STaskEvaluator(checked.right);
    if (Either.isLeft(evaluator))
        return fail("TASK_INVALID", evaluator.left.detail);
    const cases: NativeS2SCase[] = [];
    for (const raw of allRows) {
        const evaluated = evaluator.right(raw);
        if (Either.isLeft(evaluated))
            return fail("TASK_INVALID", evaluated.left.detail);
        if (split === undefined || evaluated.right.split === split)
            cases.push(evaluated.right);
    }
    return Either.right(frozen(cases));
};
export const validateNativeS2SCaseTuple = (task: unknown, candidate: unknown, split: NativeS2SSplit): Either.Either<readonly NativeS2SCase[], NativeS2SDatasetError> => {
    const checked = validateNativeS2STask(task);
    if (Either.isLeft(checked))
        return fail("TASK_INVALID", checked.left.detail);
    const evaluator = compileNativeS2STaskEvaluator(checked.right);
    if (Either.isLeft(evaluator))
        return fail("TASK_INVALID", evaluator.left.detail);
    if (!Array.isArray(candidate) || !Object.isFrozen(candidate) || candidate.length !== SPLIT_COUNTS[split])
        return fail("CASES_INVALID", `${split} cases must contain the complete ${SPLIT_COUNTS[split]}-world immutable split`);
    const byRaw = new Map<string, NativeS2SCase>();
    for (const entry of candidate) {
        if (!nativeCase(entry))
            return fail("CASES_INVALID", `${split} case must be a dense immutable native case`);
        const evaluated = evaluator.right(entry.rawValues);
        if (entry.taskManifestSha256 !== checked.right.manifestSha256 || Either.isLeft(evaluated) || evaluated.right.split !== split || !sameCase(entry, evaluated.right))
            return fail("CASES_INVALID", `${split} case is malformed, leaked, or belongs to another task`);
        const key = rawKey(evaluated.right.rawValues);
        if (byRaw.has(key))
            return fail("CASES_INVALID", `${split} cases contain a duplicate world`);
        byRaw.set(key, evaluated.right);
    }
    return Either.right(frozen([...byRaw.values()].sort((left, right) => rawKey(left.rawValues).localeCompare(rawKey(right.rawValues)))));
};
export const nativeS2SDatasetSha256 = (task: unknown, candidate: unknown, split: NativeS2SSplit): Either.Either<string, NativeS2SDatasetError> => {
    const checked = validateNativeS2STask(task);
    if (Either.isLeft(checked))
        return fail("TASK_INVALID", checked.left.detail);
    const cases = validateNativeS2SCaseTuple(checked.right, candidate, split);
    if (Either.isLeft(cases))
        return Either.left(cases.left);
    const schema = datasetSchemaSha256();
    if (Either.isLeft(schema))
        return Either.left(schema.left);
    const hash = createHash("sha256").update(DATASET_HASH_DOMAIN).update(Buffer.from(schema.right, "hex")).update(Buffer.from(checked.right.structuralTaskSha256, "hex"));
    const splitBytes = Buffer.from(split, "ascii"), count = Buffer.alloc(8);
    count.writeBigUInt64BE(BigInt(cases.right.length));
    hash.update(Buffer.from([splitBytes.length])).update(splitBytes).update(count);
    for (const entry of cases.right) {
        hash.update(Buffer.from(entry.rawValues));
        for (const row of entry.targetNumerators)
            for (const value of row) {
                const bytes = Buffer.alloc(8);
                bytes.writeBigInt64BE(BigInt(value));
                hash.update(bytes);
            }
    }
    for (const tensor of [inputTensor(cases.right), targetTensor(cases.right)]) {
        const bytes = f64Bytes(tensor), length = Buffer.alloc(8);
        length.writeBigUInt64BE(BigInt(bytes.length));
        hash.update(length).update(bytes);
    }
    return Either.right(hash.digest("hex"));
};
const receiptPayload = (role: number, channel: number, count: bigint, sum: bigint, squares: bigint, centered: bigint, weight: number) => ({
    centered_sum_squares_numerator: centered,
    channel,
    inverse_variance_weight_hex: nativeS2SFloatHex(weight),
    role,
    sample_count: Number(count),
    schema_version: NATIVE_S2S_STRATUM_LOSS_RECEIPT_VERSION,
    target_numerator_sum: sum,
    target_numerator_sum_squares: squares,
    target_scale_exponent: NATIVE_S2S_TARGET_SCALE_EXPONENT,
    variance_definition: "POPULATION_VARIANCE=(N*SUMSQ-SUM^2)/(N^2*2^(2*SCALE_EXPONENT))"
});
/** Python integer true division rounds the exact rational once to Float64. */
export const nativeS2SPositiveRatio = (numerator: unknown, denominator: unknown): Either.Either<number, NativeS2SDatasetError> => {
    if (typeof numerator !== "bigint" || numerator <= 0n || typeof denominator !== "bigint" || denominator <= 0n)
        return fail("DATASET_INVALID", "ratio requires positive exact integers");
    const result = rationalToFloat64(numerator, denominator);
    return Number.isFinite(result) && result > 0 ? Either.right(result) : fail("DATASET_INVALID", "ratio must round to a finite positive Float64");
};
export const buildNativeS2SStratumLossReceipts = (candidate: unknown): Either.Either<readonly NativeS2SStratumLossReceipt[], NativeS2SDatasetError> => {
    if (!dense(candidate, NATIVE_S2S_TRAIN_CASE_COUNT) || !candidate.every(nativeCase))
        return fail("CASES_INVALID", "stratum receipts require dense immutable native train cases");
    const cases = candidate;
    const output: NativeS2SStratumLossReceipt[] = [];
    for (let role = 0; role < 3; role += 1)
        for (let channel = 0; channel < 2; channel += 1) {
            const values = cases.flatMap((entry) => [entry.targetNumerators[2 * role]![channel]!, entry.targetNumerators[2 * role + 1]![channel]!]);
            const count = BigInt(values.length), sum = values.reduce((total, value) => total + BigInt(value), 0n), squares = values.reduce((total, value) => total + BigInt(value) * BigInt(value), 0n), centered = count * squares - sum * sum;
            if (centered <= 0n)
                return fail("DATASET_INVALID", "stratum variance must be positive");
            const weight = rationalToFloat64(count * count * (2n ** BigInt(2 * NATIVE_S2S_TARGET_SCALE_EXPONENT)), centered);
            if (!Number.isFinite(weight) || weight <= 0)
                return fail("DATASET_INVALID", "loss weights must be finite and positive");
            const receipt = canonicalSha(receiptPayload(role, channel, count, sum, squares, centered, weight));
            if (Either.isLeft(receipt))
                return Either.left(receipt.left);
            output.push(frozen({ role, channel, sampleCount: Number(count), targetNumeratorSum: sum, targetNumeratorSumSquares: squares, centeredSumSquaresNumerator: centered, inverseVarianceWeight: weight, receiptSha256: receipt.right }));
        }
    return Either.right(frozen(output));
};
export const nativeS2SWeightMatrix = (candidate: unknown): Either.Either<readonly number[], NativeS2SDatasetError> => {
    if (!dense(candidate, 6))
        return fail("DATASET_INVALID", "weight matrix requires six dense stratum receipts");
    const values: number[] = Array<number>(6).fill(0);
    for (const receipt of candidate) {
        if (receipt === null || typeof receipt !== "object")
            return fail("DATASET_INVALID", "weight receipts must be records");
        const item = receipt as NativeS2SStratumLossReceipt;
        if (!Number.isInteger(item.role) || !Number.isInteger(item.channel) || item.role < 0 || item.role > 2 || item.channel < 0 || item.channel > 1 || !Number.isFinite(item.inverseVarianceWeight) || item.inverseVarianceWeight <= 0)
            return fail("DATASET_INVALID", "loss weights must be finite and indexed by role and channel");
        const index = item.role * 2 + item.channel;
        if (values[index]! !== 0)
            return fail("DATASET_INVALID", "loss receipts must contain each role/channel once");
        values[index] = item.inverseVarianceWeight;
    }
    return Either.right(frozen(values));
};
export const compileNativeS2STaskData = (task: unknown): Either.Either<NativeS2SCompiledTaskData, NativeS2SDatasetError> => {
    const train = enumerateNativeS2STaskCases(task, "train"), dev = enumerateNativeS2STaskCases(task, "dev");
    if (Either.isLeft(train))
        return Either.left(train.left);
    if (Either.isLeft(dev))
        return Either.left(dev.left);
    const strata = buildNativeS2SStratumLossReceipts(train.right);
    if (Either.isLeft(strata))
        return Either.left(strata.left);
    const weights = nativeS2SWeightMatrix(strata.right);
    if (Either.isLeft(weights))
        return Either.left(weights.left);
    const trainHash = nativeS2SDatasetSha256(task, train.right, "train"), devHash = nativeS2SDatasetSha256(task, dev.right, "dev");
    if (Either.isLeft(trainHash))
        return Either.left(trainHash.left);
    if (Either.isLeft(devHash))
        return Either.left(devHash.left);
    return Either.right(frozen({ trainDatasetSha256: trainHash.right, devDatasetSha256: devHash.right, strata: strata.right, weights: weights.right, trainInput: inputTensor(train.right), trainTargets: targetTensor(train.right), devInput: inputTensor(dev.right), devTargets: targetTensor(dev.right), scientificStatus: NATIVE_S2S_DATASET_SCIENTIFIC_STATUS }));
};
