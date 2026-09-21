/** Bounded, pure full-batch Adam port for already compiled S2S arrays. */
import { createHash } from "node:crypto";
import { lossForNativeS2SReferenceParameters as lossForNativeS2SParameters } from "./native-s2s-reference-loss-domain.js";
import { Data, Either } from "effect";
import { NATIVE_S2S_TRAINING_SCIENTIFIC_STATUS, clipNativeS2SGradients, lossAndGradientsNativeS2S } from "./native-s2s-training-numeric-domain.js";
import type { NativeS2SParameters, NativeS2STrainingArm, NativeS2STrainingError } from "./native-s2s-training-numeric-domain.js";
export const NATIVE_S2S_FIT_SOURCE_SHA256 = "d84b8336d8bcbe89aeba7f2d2c915fd294b9ee24425e6092505069a74f9cba94" as const;
export class NativeS2SFitError extends Data.TaggedError("NativeS2SFitError")<{
    readonly reason: "CONFIG_INVALID" | "INPUT_INVALID" | "NUMERIC_INVALID";
    readonly detail: string;
}> {
}
export interface NativeS2SFitConfig {
    /** Recorded initialization metadata; this API consumes caller-supplied initial parameters. */
    readonly seed: number | bigint;
    readonly maxUpdates: number;
    readonly learningRate: number;
    readonly beta1: number;
    readonly beta2: number;
    readonly epsilon: number;
    readonly gradientClip: number;
    readonly patience: number;
    readonly minDelta: number;
}
export interface NativeS2SFitHistoryEntry {
    readonly update: number;
    readonly trainLoss: number;
    readonly devLoss: number;
    readonly gradientNorm: number | null;
    readonly clipped: boolean;
    readonly improved: boolean;
    readonly parametersSha256: string;
}
export interface NativeS2SFitResult {
    readonly arm: NativeS2STrainingArm;
    readonly config: Readonly<NativeS2SFitConfig>;
    readonly parameters: NativeS2SParameters;
    readonly initialParametersSha256: string;
    readonly bestParametersSha256: string;
    readonly bestUpdate: number;
    readonly stoppedUpdate: number;
    readonly bestTrainLoss: number;
    readonly bestDevLoss: number;
    readonly updateCount: number;
    readonly clippedUpdateCount: number;
    readonly history: readonly NativeS2SFitHistoryEntry[];
    readonly terminationReason: "MAX_UPDATES" | "PATIENCE";
    readonly scientificStatus: typeof NATIVE_S2S_TRAINING_SCIENTIFIC_STATUS;
}
const fail = (reason: NativeS2SFitError["reason"], detail: string): Either.Either<never, NativeS2SFitError> => Either.left(new NativeS2SFitError({ reason, detail }));
const names = (arm: NativeS2STrainingArm): readonly (readonly [
    string,
    string,
    readonly number[]
])[] => arm === "P_CAP18" ? [["phiW", "phi_w", [3, 4, 18]], ["psiW", "psi_w", [3, 4, 18]], ["unaryW", "unary_w", [3, 2, 18]], ["pairW", "pair_w", [3, 3, 2, 18]], ["outB", "out_b", [3, 2]]] : arm === "T16" ? [["phiW", "phi_w", [3, 4, 16]], ["psiW", "psi_w", [3, 4, 16]], ["unaryW", "unary_w", [3, 2, 16]], ["pairW", "pair_w", [3, 3, 2, 16]], ["qW", "q_w", [3, 2, 16]], ["outB", "out_b", [3, 2]]] : [["etaW", "eta_w", [3, 4, 4]], ["etaB", "eta_b", [3, 4]], ["hidden1W", "hidden1_w", [30, 14]], ["hidden1B", "hidden1_b", [14]], ["hidden2W", "hidden2_w", [14, 22]], ["hidden2B", "hidden2_b", [22]], ["outW", "out_w", [22, 2]], ["outB", "out_b", [2]]];
const parameterRecord = (value: NativeS2SParameters): Record<string, readonly number[]> => value as unknown as Record<string, readonly number[]>;
/** Original ordered native key, archive name and tensor shape schema. */
export const nativeS2SParameterSchema = names;
const copy = (parameters: NativeS2SParameters, arm: NativeS2STrainingArm): NativeS2SParameters => Object.freeze(Object.fromEntries(names(arm).map(([key]) => [key, Object.freeze([...parameterRecord(parameters)[key]!])])) as unknown as NativeS2SParameters);
export const nativeS2SParameterSha256 = (parameters: NativeS2SParameters, arm: NativeS2STrainingArm): string => {
    const hash = createHash("sha256").update("hswm-swm0w-s2s-parameters/v1\0");
    const record = parameterRecord(parameters);
    for (const [key, pythonName, shape] of [...names(arm)].sort((left, right) => left[1].localeCompare(right[1]))) {
        const descriptor = Buffer.from(JSON.stringify({ dtype: "float64-le", name: pythonName, shape }));
        const bytes = Buffer.allocUnsafe(record[key]!.length * 8);
        for (let index = 0; index < record[key]!.length; index += 1)
            bytes.writeDoubleLE(record[key]![index]!, index * 8);
        const length = Buffer.allocUnsafe(8);
        length.writeBigUInt64BE(BigInt(descriptor.length));
        hash.update(length).update(descriptor);
        length.writeBigUInt64BE(BigInt(bytes.length));
        hash.update(length).update(bytes);
    }
    return hash.digest("hex");
};
const parameterSha256 = nativeS2SParameterSha256;
const uint64 = (value: unknown): boolean => (typeof value === "bigint" && value >= 0n && value < 2n ** 64n) || (typeof value === "number" && Number.isSafeInteger(value) && value >= 0);
const configKeys = ["seed", "maxUpdates", "learningRate", "beta1", "beta2", "epsilon", "gradientClip", "patience", "minDelta"] as const;
type ConfigKey = (typeof configKeys)[number];
const configInvalid = (): Either.Either<never, NativeS2SFitError> => fail("CONFIG_INVALID", "configuration must contain exactly the finite full-batch Adam data fields");
const finiteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const validConfigValues = (config: Readonly<Record<ConfigKey, unknown>>): config is Readonly<NativeS2SFitConfig> => uint64(config.seed) && typeof config.maxUpdates === "number" && Number.isSafeInteger(config.maxUpdates) && config.maxUpdates >= 0 && typeof config.patience === "number" && Number.isSafeInteger(config.patience) && config.patience > 0 && finiteNumber(config.learningRate) && finiteNumber(config.beta1) && finiteNumber(config.beta2) && finiteNumber(config.epsilon) && finiteNumber(config.gradientClip) && finiteNumber(config.minDelta) && config.learningRate > 0 && config.beta1 > 0 && config.beta1 < 1 && config.beta2 > 0 && config.beta2 < 1 && config.epsilon > 0 && config.gradientClip > 0 && config.minDelta >= 0 && !Object.is(config.minDelta, -0);
/** Decodes only own data descriptors: accessors and failed reflection are invalid input. */
export const validateNativeS2SFitConfig = (config: unknown): Either.Either<Readonly<NativeS2SFitConfig>, NativeS2SFitError> => {
    if (typeof config !== "object" || config === null)
        return configInvalid();
    try {
        if (Array.isArray(config))
            return configInvalid();
        const record = config as Record<PropertyKey, unknown>, ownKeys = Reflect.ownKeys(record);
        if (ownKeys.length !== configKeys.length || !configKeys.every(key => ownKeys.includes(key)))
            return configInvalid();
        const values: Partial<Record<ConfigKey, unknown>> = {};
        for (const key of configKeys) {
            const descriptor = Object.getOwnPropertyDescriptor(record, key);
            if (descriptor === undefined || !("value" in descriptor))
                return configInvalid();
            values[key] = descriptor.value;
        }
        const candidate = values as Readonly<Record<ConfigKey, unknown>>;
        if (!validConfigValues(candidate))
            return configInvalid();
        return Either.right(Object.freeze({ seed: candidate.seed, maxUpdates: candidate.maxUpdates, learningRate: candidate.learningRate, beta1: candidate.beta1, beta2: candidate.beta2, epsilon: candidate.epsilon, gradientClip: candidate.gradientClip, patience: candidate.patience, minDelta: candidate.minDelta }));
    }
    catch {
        return configInvalid();
    }
};
const trainingFailure = (error: NativeS2STrainingError | {
    readonly detail: string;
    readonly reason?: undefined;
}): Either.Either<never, NativeS2SFitError> => fail(error.reason === "NUMERIC_INVALID" ? "NUMERIC_INVALID" : "INPUT_INVALID", error.detail);
/** Fits only numeric arrays supplied by the caller; it does not construct task or receipt claims. */
export const fitNativeS2SCompiledArrays = (arm: NativeS2STrainingArm, initialParameters: NativeS2SParameters, trainInput: readonly number[], trainTargets: readonly number[], devInput: readonly number[], devTargets: readonly number[], weights: readonly number[], config: NativeS2SFitConfig): Either.Either<NativeS2SFitResult, NativeS2SFitError> => {
    const decodedConfig = validateNativeS2SFitConfig(config);
    if (Either.isLeft(decodedConfig))
        return Either.left(decodedConfig.left);
    const safeConfig = decodedConfig.right;
    if (arm !== "P_CAP18" && arm !== "T16" && arm !== "DS870")
        return fail("INPUT_INVALID", "arm must be P_CAP18, T16, or DS870");
    const initialTrain = lossForNativeS2SParameters(arm, initialParameters, trainInput, trainTargets, weights), initialDev = lossForNativeS2SParameters(arm, initialParameters, devInput, devTargets, weights);
    if (Either.isLeft(initialTrain))
        return trainingFailure(initialTrain.left);
    if (Either.isLeft(initialDev))
        return trainingFailure(initialDev.left);
    let parameters = copy(initialParameters, arm), bestParameters = copy(initialParameters, arm), bestTrainLoss = initialTrain.right, bestDevLoss = initialDev.right, bestUpdate = 0, stale = 0, clippedUpdates = 0, stoppedUpdate = 0, termination: "MAX_UPDATES" | "PATIENCE" = "MAX_UPDATES";
    const moments: Record<string, number[]> = Object.fromEntries(names(arm).map(([key]) => [key, Array<number>(parameterRecord(parameters)[key]!.length).fill(0)])), variances: Record<string, number[]> = Object.fromEntries(names(arm).map(([key]) => [key, Array<number>(parameterRecord(parameters)[key]!.length).fill(0)])), initialParametersSha256 = parameterSha256(parameters, arm);
    const history: NativeS2SFitHistoryEntry[] = [Object.freeze({ update: 0, trainLoss: bestTrainLoss, devLoss: bestDevLoss, gradientNorm: null, clipped: false, improved: true, parametersSha256: initialParametersSha256 })];
    for (let update = 1; update <= safeConfig.maxUpdates; update += 1) {
        const differentiated = lossAndGradientsNativeS2S(arm, parameters, trainInput, trainTargets, weights);
        if (Either.isLeft(differentiated))
            return trainingFailure(differentiated.left);
        const clipped = clipNativeS2SGradients(differentiated.right.gradients, safeConfig.gradientClip);
        if (Either.isLeft(clipped))
            return trainingFailure(clipped.left);
        clippedUpdates += clipped.right.clipped ? 1 : 0;
        stoppedUpdate = update;
        const updated: Record<string, readonly number[]> = {};
        for (const [key] of names(arm)) {
            const values = parameterRecord(parameters)[key]!, gradient = clipped.right.gradients[key]!, next = Array<number>(values.length);
            for (let index = 0; index < values.length; index += 1) {
                const moment = safeConfig.beta1 * moments[key]![index]! + (1 - safeConfig.beta1) * gradient[index]!, variance = safeConfig.beta2 * variances[key]![index]! + (1 - safeConfig.beta2) * gradient[index]! * gradient[index]!, value = values[index]! - safeConfig.learningRate * (moment / (1 - safeConfig.beta1 ** update)) / (Math.sqrt(variance / (1 - safeConfig.beta2 ** update)) + safeConfig.epsilon);
                if (!Number.isFinite(moment) || !Number.isFinite(variance) || !Number.isFinite(value))
                    return fail("NUMERIC_INVALID", "Adam produced a non-finite state");
                moments[key]![index] = moment;
                variances[key]![index] = variance;
                next[index] = value;
            }
            updated[key] = Object.freeze(next);
        }
        parameters = Object.freeze(updated) as unknown as NativeS2SParameters;
        const trainLoss = lossForNativeS2SParameters(arm, parameters, trainInput, trainTargets, weights), devLoss = lossForNativeS2SParameters(arm, parameters, devInput, devTargets, weights);
        if (Either.isLeft(trainLoss))
            return trainingFailure(trainLoss.left);
        if (Either.isLeft(devLoss))
            return trainingFailure(devLoss.left);
        const improved = devLoss.right < bestDevLoss - safeConfig.minDelta, parametersSha256 = parameterSha256(parameters, arm);
        history.push(Object.freeze({ update, trainLoss: trainLoss.right, devLoss: devLoss.right, gradientNorm: clipped.right.norm, clipped: clipped.right.clipped, improved, parametersSha256 }));
        if (improved) {
            bestTrainLoss = trainLoss.right;
            bestDevLoss = devLoss.right;
            bestParameters = copy(parameters, arm);
            bestUpdate = update;
            stale = 0;
        }
        else {
            stale += 1;
            if (stale >= safeConfig.patience) {
                termination = "PATIENCE";
                break;
            }
        }
    }
    return Either.right(Object.freeze({ arm, config: safeConfig, parameters: bestParameters, initialParametersSha256, bestParametersSha256: parameterSha256(bestParameters, arm), bestUpdate, stoppedUpdate, bestTrainLoss, bestDevLoss, updateCount: stoppedUpdate, clippedUpdateCount: clippedUpdates, history: Object.freeze(history), terminationReason: termination, scientificStatus: NATIVE_S2S_TRAINING_SCIENTIFIC_STATUS }));
};
