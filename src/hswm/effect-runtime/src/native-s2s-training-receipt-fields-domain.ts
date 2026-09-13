/** Immutable receipt-field constructors for the historical S2S optimizer. */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { nativeS2SFloatHex } from "./native-s2s-dataset-domain.js";
import { decodeNativeTaskJson, isTaskNumber, renderNativeTaskJson, taskNumberIsFloat, taskNumberValue, type TaskJson } from "./native-task-json-domain.js";
export const NATIVE_S2S_TRAINING_RECEIPT_FIELDS_SOURCE_SHA256 = "d84b8336d8bcbe89aeba7f2d2c915fd294b9ee24425e6092505069a74f9cba94" as const;
export const NATIVE_S2S_HISTORY_VERSION = "hswm-swm0w-s2s-optimization-history/v1" as const;
export const NATIVE_S2S_HISTORY_ENTRY_VERSION = "hswm-swm0w-s2s-optimization-history-entry/v1" as const;
export class NativeS2STrainingReceiptFieldsError extends Data.TaggedError("NativeS2STrainingReceiptFieldsError")<{
    readonly reason: "CONFIG_INVALID" | "HISTORY_INVALID" | "JSON_INVALID";
    readonly detail: string;
}> {
}
export interface NativeS2STrainingConfig {
    readonly seed: bigint;
    readonly maxUpdates: number;
    readonly learningRate: number;
    readonly beta1: number;
    readonly beta2: number;
    readonly epsilon: number;
    readonly gradientClip: number;
    readonly patience: number;
    readonly minDelta: number;
}
export interface NativeS2SOptimizationHistoryEntry {
    readonly update: number;
    readonly trainLoss: number;
    readonly devLoss: number;
    readonly gradientNorm: number | null;
    readonly clipped: boolean;
    readonly improved: boolean;
    readonly parametersSha256: string;
}
type ErrorReason = NativeS2STrainingReceiptFieldsError["reason"];
const fail = (reason: ErrorReason, detail: string): Either.Either<never, NativeS2STrainingReceiptFieldsError> => Either.left(new NativeS2STrainingReceiptFieldsError({ reason, detail }));
const frozen = <T>(value: T): T => Object.freeze(value);
const sha256 = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value);
const unsigned64 = (value: unknown): bigint | undefined => typeof value === "bigint" && value >= 0n && value < 2n ** 64n ? value : integer(value) && value >= 0 ? BigInt(value) : undefined;
const finiteFloat = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const record = (value: unknown): value is Readonly<Record<string, unknown>> => value !== null && typeof value === "object" && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
const exactKeys = (value: object, keys: readonly string[]): boolean => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const ownData = (value: object, keys: readonly string[]): value is Readonly<Record<string, unknown>> => record(value) && Reflect.ownKeys(value).length === Object.keys(value).length && exactKeys(value, keys) && keys.every(key => {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return descriptor !== undefined && Object.hasOwn(descriptor, "value") && descriptor.enumerable;
});
const configKeys = ["seed", "maxUpdates", "learningRate", "beta1", "beta2", "epsilon", "gradientClip", "patience", "minDelta"] as const;
const historyKeys = ["update", "trainLoss", "devLoss", "gradientNorm", "clipped", "improved", "parametersSha256"] as const;
const defaultConfig: NativeS2STrainingConfig = frozen({ seed: 0n, maxUpdates: 200, learningRate: 0.01, beta1: 0.9, beta2: 0.999, epsilon: 1e-8, gradientClip: 5, patience: 25, minDelta: 1e-9 });
const configError = (detail: string): Either.Either<never, NativeS2STrainingReceiptFieldsError> => fail("CONFIG_INVALID", detail);
const historyError = (detail: string): Either.Either<never, NativeS2STrainingReceiptFieldsError> => fail("HISTORY_INVALID", detail);
/** Recreates the Python dataclass constructor, including its default values. */
export const createNativeS2STrainingConfig = (candidate: unknown = {}): Either.Either<NativeS2STrainingConfig, NativeS2STrainingReceiptFieldsError> => {
    if (!record(candidate))
        return configError("config must be an exact plain object");
    const candidateKeys = Object.keys(candidate);
    if (!ownData(candidate, candidateKeys) || !candidateKeys.every(key => configKeys.includes(key as typeof configKeys[number])))
        return configError("config contains non-data or unknown fields");
    const value = { ...defaultConfig, ...Object.fromEntries(candidateKeys.map(key => [key, Object.getOwnPropertyDescriptor(candidate, key)!.value])) };
    const seed = unsigned64(value.seed);
    if (seed === undefined)
        return configError("seed must be an exact unsigned 64-bit integer");
    if (!integer(value.maxUpdates) || value.maxUpdates < 0)
        return configError("max_updates must be a non-negative integer");
    if (!integer(value.patience) || value.patience <= 0)
        return configError("patience must be a positive integer");
    const fields: readonly [
        string,
        unknown
    ][] = [["learning_rate", value.learningRate], ["beta1", value.beta1], ["beta2", value.beta2], ["epsilon", value.epsilon], ["gradient_clip", value.gradientClip], ["min_delta", value.minDelta]];
    for (const [name, field] of fields)
        if (!finiteFloat(field))
            return configError(`${name} must be an exact finite float`);
    if (value.learningRate <= 0)
        return configError("learning_rate must be positive");
    if (!(value.beta1 > 0 && value.beta1 < 1 && value.beta2 > 0 && value.beta2 < 1))
        return configError("Adam beta values must lie strictly in (0, 1)");
    if (value.epsilon <= 0 || value.gradientClip <= 0)
        return configError("epsilon and gradient_clip must be positive");
    if (value.minDelta < 0 || Object.is(value.minDelta, -0))
        return configError("min_delta must be non-negative");
    return Either.right(frozen({ seed, maxUpdates: value.maxUpdates, learningRate: value.learningRate, beta1: value.beta1, beta2: value.beta2, epsilon: value.epsilon, gradientClip: value.gradientClip, patience: value.patience, minDelta: value.minDelta }));
};
export const nativeS2STrainingConfigCanonical = (config: unknown): Either.Either<Readonly<Record<string, TaskJson>>, NativeS2STrainingReceiptFieldsError> => createNativeS2STrainingConfig(config).pipe(Either.map(value => frozen({ beta1_hex: nativeS2SFloatHex(value.beta1), beta2_hex: nativeS2SFloatHex(value.beta2), epsilon_hex: nativeS2SFloatHex(value.epsilon), gradient_clip_hex: nativeS2SFloatHex(value.gradientClip), learning_rate_hex: nativeS2SFloatHex(value.learningRate), max_updates: value.maxUpdates, min_delta_hex: nativeS2SFloatHex(value.minDelta), patience: value.patience, seed: value.seed })));
/** Recreates one frozen Python OptimizationHistoryEntry. */
export const createNativeS2SOptimizationHistoryEntry = (candidate: unknown): Either.Either<NativeS2SOptimizationHistoryEntry, NativeS2STrainingReceiptFieldsError> => {
    if (!record(candidate) || !ownData(candidate, historyKeys))
        return historyError("history entry must have exactly the required own data fields");
    const update = candidate["update"], trainLoss = candidate["trainLoss"], devLoss = candidate["devLoss"], gradientNorm = candidate["gradientNorm"], clipped = candidate["clipped"], improved = candidate["improved"], parametersSha256 = candidate["parametersSha256"];
    if (!integer(update) || update < 0)
        return historyError("history update must be non-negative integer");
    if (!finiteFloat(trainLoss) || trainLoss < 0 || Object.is(trainLoss, -0))
        return historyError("history train loss must be an exact finite non-negative float");
    if (!finiteFloat(devLoss) || devLoss < 0 || Object.is(devLoss, -0))
        return historyError("history dev loss must be an exact finite non-negative float");
    if (typeof clipped !== "boolean" || typeof improved !== "boolean")
        return historyError("history flags must be exact bools");
    if (!sha256(parametersSha256))
        return historyError("history parameter SHA must be a lowercase SHA-256");
    if (update === 0) {
        if (gradientNorm !== null || clipped || !improved)
            return historyError("epoch-zero history must be improved, unclipped, and gradient-free");
    }
    else {
        if (gradientNorm === null)
            return historyError("post-update history requires a global gradient norm");
        if (!finiteFloat(gradientNorm) || gradientNorm < 0 || Object.is(gradientNorm, -0))
            return historyError("history gradient norm must be an exact finite non-negative float");
    }
    return Either.right(frozen({ update, trainLoss, devLoss, gradientNorm: gradientNorm as number | null, clipped, improved, parametersSha256 }));
};
export const nativeS2SOptimizationHistoryEntryCanonical = (entry: unknown): Either.Either<Readonly<Record<string, TaskJson>>, NativeS2STrainingReceiptFieldsError> => createNativeS2SOptimizationHistoryEntry(entry).pipe(Either.map(value => frozen({ clipped: value.clipped, dev_loss_hex: nativeS2SFloatHex(value.devLoss), gradient_norm_hex: value.gradientNorm === null ? null : nativeS2SFloatHex(value.gradientNorm), improved: value.improved, parameters_sha256: value.parametersSha256, schema_version: NATIVE_S2S_HISTORY_ENTRY_VERSION, train_loss_hex: nativeS2SFloatHex(value.trainLoss), update: value.update })));
export const nativeS2SOptimizationHistorySha256 = (history: unknown): Either.Either<string, NativeS2STrainingReceiptFieldsError> => {
    if (!Array.isArray(history) || Object.getPrototypeOf(history) !== Array.prototype || Reflect.ownKeys(history).length !== history.length + 1 || !Array.from({ length: history.length }, (_, index) => {
        const descriptor = Object.getOwnPropertyDescriptor(history, String(index));
        return descriptor !== undefined && Object.hasOwn(descriptor, "value") && descriptor.enumerable;
    }).every(Boolean))
        return historyError("history must be a dense own-data array");
    const canonical = Either.all(history.map(nativeS2SOptimizationHistoryEntryCanonical));
    if (Either.isLeft(canonical))
        return Either.left(canonical.left);
    return Either.right(createHash("sha256").update(renderNativeTaskJson({ entries: canonical.right, schema_version: NATIVE_S2S_HISTORY_VERSION }), "utf8").digest("hex"));
};
const parsedInteger = (value: TaskJson | undefined): number | bigint | undefined => value !== undefined && isTaskNumber(value) && !taskNumberIsFloat(value) ? taskNumberValue(value) : undefined;
const parsedFloat = (value: TaskJson | undefined): number | undefined => {
    if (value === undefined || !isTaskNumber(value) || !taskNumberIsFloat(value))
        return undefined;
    const parsed = taskNumberValue(value);
    return typeof parsed === "number" ? parsed : undefined;
};
const protocolData = (value: unknown, keys: readonly string[]): value is Readonly<Record<string, TaskJson>> => {
    if (value === null || typeof value !== "object" || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype || Object.keys(value).length !== keys.length || !keys.every(key => Object.hasOwn(value, key)))
        return false;
    return Reflect.ownKeys(value).every(key => {
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        if (descriptor === undefined || !Object.hasOwn(descriptor, "value"))
            return false;
        return typeof key === "symbol" ? !descriptor.enumerable : typeof key === "string" && descriptor.enumerable;
    });
};
const canonicalHex = (value: unknown, name: string, mode: "positive" | "nonnegative"): Either.Either<number, NativeS2STrainingReceiptFieldsError> => {
    if (typeof value !== "string")
        return fail("JSON_INVALID", `${name} must be canonical float hex`);
    let parsed: number | undefined;
    if (value === "0x0.0p+0")
        parsed = 0;
    else if (value === "-0x0.0p+0")
        parsed = -0;
    else {
        const match = /^(-?)0x([01])\.([0-9a-f]{13})p([+-][0-9]+)$/.exec(value);
        if (match !== null) {
            const sign = match[1] === "-" ? -1 : 1, lead = match[2]!, fraction = BigInt(`0x${match[3]!}`), exponent = Number(match[4]!);
            if (Number.isFinite(exponent))
                parsed = sign * (lead === "0" ? Number(fraction) * 2 ** -1074 : (Number(0x10000000000000n + fraction) * 2 ** (exponent - 52)));
        }
    }
    if (parsed === undefined || !Number.isFinite(parsed) || nativeS2SFloatHex(parsed) !== value)
        return fail("JSON_INVALID", `${name} must be canonical finite float hex`);
    if (Object.is(parsed, -0))
        return fail("JSON_INVALID", `${name} may not encode negative zero`);
    if (mode === "positive" && parsed <= 0)
        return fail("JSON_INVALID", `${name} must be positive`);
    if (mode === "nonnegative" && parsed < 0)
        return fail("JSON_INVALID", `${name} must be non-negative`);
    return Either.right(parsed);
};
/** Parses raw training kwargs; protocol receipt inputs use parseNativeS2STrainingConfig. */
export const parseNativeS2STrainingConfigRaw = (value: unknown): Either.Either<NativeS2STrainingConfig, NativeS2STrainingReceiptFieldsError> => {
    if (!protocolData(value, ["seed", "max_updates", "learning_rate", "beta1", "beta2", "epsilon", "gradient_clip", "patience", "min_delta"]))
        return configError("training config JSON fields are invalid");
    const seed = parsedInteger(value["seed"]), maxUpdates = parsedInteger(value["max_updates"]), learningRate = parsedFloat(value["learning_rate"]), beta1 = parsedFloat(value["beta1"]), beta2 = parsedFloat(value["beta2"]), epsilon = parsedFloat(value["epsilon"]), gradientClip = parsedFloat(value["gradient_clip"]), patience = parsedInteger(value["patience"]), minDelta = parsedFloat(value["min_delta"]);
    return createNativeS2STrainingConfig({ seed, maxUpdates, learningRate, beta1, beta2, epsilon, gradientClip, patience, minDelta });
};
/** Parses raw history kwargs; protocol receipt inputs use parseNativeS2SOptimizationHistoryEntry. */
export const parseNativeS2SOptimizationHistoryEntryRaw = (value: unknown): Either.Either<NativeS2SOptimizationHistoryEntry, NativeS2STrainingReceiptFieldsError> => {
    if (!protocolData(value, ["update", "train_loss", "dev_loss", "gradient_norm", "clipped", "improved", "parameters_sha256"]))
        return historyError("history entry JSON fields are invalid");
    const gradient = value["gradient_norm"] === null ? null : parsedFloat(value["gradient_norm"]);
    return createNativeS2SOptimizationHistoryEntry({ update: parsedInteger(value["update"]), trainLoss: parsedFloat(value["train_loss"]), devLoss: parsedFloat(value["dev_loss"]), gradientNorm: gradient, clipped: value["clipped"], improved: value["improved"], parametersSha256: value["parameters_sha256"] });
};
/** Parses parse_training_config's canonical nested representation and reseals it. */
export const parseNativeS2STrainingConfig = (value: unknown): Either.Either<NativeS2STrainingConfig, NativeS2STrainingReceiptFieldsError> => Either.gen(function* () {
    const keys = ["beta1_hex", "beta2_hex", "epsilon_hex", "gradient_clip_hex", "learning_rate_hex", "max_updates", "min_delta_hex", "patience", "seed"] as const;
    if (!protocolData(value, keys))
        return yield* configError("training config keys disagree with the exact schema");
    const beta1 = yield* canonicalHex(value["beta1_hex"], "beta1", "positive"), beta2 = yield* canonicalHex(value["beta2_hex"], "beta2", "positive"), epsilon = yield* canonicalHex(value["epsilon_hex"], "epsilon", "positive"), gradientClip = yield* canonicalHex(value["gradient_clip_hex"], "gradient clip", "positive"), learningRate = yield* canonicalHex(value["learning_rate_hex"], "learning rate", "positive"), minDelta = yield* canonicalHex(value["min_delta_hex"], "min delta", "nonnegative");
    const result = yield* createNativeS2STrainingConfig({ seed: parsedInteger(value["seed"]), maxUpdates: parsedInteger(value["max_updates"]), learningRate, beta1, beta2, epsilon, gradientClip, patience: parsedInteger(value["patience"]), minDelta });
    const canonical = yield* nativeS2STrainingConfigCanonical(result);
    return renderNativeTaskJson(value) === renderNativeTaskJson(canonical) ? result : yield* configError("training config is not its exact canonical representation");
});
/** Parses _parse_history_entry's canonical nested representation and reseals it. */
export const parseNativeS2SOptimizationHistoryEntry = (value: unknown): Either.Either<NativeS2SOptimizationHistoryEntry, NativeS2STrainingReceiptFieldsError> => Either.gen(function* () {
    const keys = ["clipped", "dev_loss_hex", "gradient_norm_hex", "improved", "parameters_sha256", "schema_version", "train_loss_hex", "update"] as const;
    if (!protocolData(value, keys))
        return yield* historyError("optimization history entry keys disagree with the exact schema");
    if (value["schema_version"] !== NATIVE_S2S_HISTORY_ENTRY_VERSION)
        return yield* historyError("history-entry schema drifted");
    const trainLoss = yield* canonicalHex(value["train_loss_hex"], "train loss", "nonnegative"), devLoss = yield* canonicalHex(value["dev_loss_hex"], "dev loss", "nonnegative");
    const gradientNorm = value["gradient_norm_hex"] === null ? null : yield* canonicalHex(value["gradient_norm_hex"], "gradient norm", "nonnegative");
    const result = yield* createNativeS2SOptimizationHistoryEntry({ update: parsedInteger(value["update"]), trainLoss, devLoss, gradientNorm, clipped: value["clipped"], improved: value["improved"], parametersSha256: value["parameters_sha256"] });
    const canonical = yield* nativeS2SOptimizationHistoryEntryCanonical(result);
    return renderNativeTaskJson(value) === renderNativeTaskJson(canonical) ? result : yield* historyError("optimization history entry is not its exact canonical representation");
});
export const parseNativeS2STrainingConfigJson = (bytes: Uint8Array): Either.Either<NativeS2STrainingConfig, NativeS2STrainingReceiptFieldsError> => decodeNativeTaskJson(bytes).pipe(Either.mapLeft(() => new NativeS2STrainingReceiptFieldsError({ reason: "JSON_INVALID", detail: "training config JSON is invalid" })), Either.flatMap(parseNativeS2STrainingConfig));
export const parseNativeS2SOptimizationHistoryEntryJson = (bytes: Uint8Array): Either.Either<NativeS2SOptimizationHistoryEntry, NativeS2STrainingReceiptFieldsError> => decodeNativeTaskJson(bytes).pipe(Either.mapLeft(() => new NativeS2STrainingReceiptFieldsError({ reason: "JSON_INVALID", detail: "history entry JSON is invalid" })), Either.flatMap(parseNativeS2SOptimizationHistoryEntry));
