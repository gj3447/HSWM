/** Source-bound reconstruction; self-consistent archives do not establish fit replay. */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { compileNativeS2STaskData, nativeS2SFloatHex } from "./native-s2s-dataset-domain.js";
import { nativeS2SParameterSchema, nativeS2SParameterSha256 } from "./native-s2s-fit-domain.js";
import { forwardNativeS2SDs870, forwardNativeS2SPCap18, forwardNativeS2ST16, type NativeS2SDs870Parameters, type NativeS2SPCap18Parameters, type NativeS2ST16Parameters } from "./native-s2s-operator-domain.js";
import { parseNativeS2SOptimizationReceipt, type NativeS2SOptimizationReceipt } from "./native-s2s-optimization-receipt-domain.js";
import { lossForNativeS2SReferenceParameters } from "./native-s2s-reference-loss-domain.js";
import { parseNativeS2STaskArchiveEntry } from "./native-s2s-task-archive-domain.js";
import type { NativeS2SParameters, NativeS2STrainingArm } from "./native-s2s-training-numeric-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export const NATIVE_S2S_MODEL_PROTOCOL_SOURCE_SHA256 = "c0df25e37d0e54c792f0eca9f78d83029e4fedd8f837743096eef2b29a62a2c1";
export class NativeS2SModelProtocolError extends Data.TaggedError("NativeS2SModelProtocolError")<{
    readonly detail: string;
}> {
}
export interface NativeS2SVerifiedModel {
    readonly arm: NativeS2STrainingArm;
    readonly parameters: NativeS2SParameters;
    readonly optimization: NativeS2SOptimizationReceipt;
    readonly learned: boolean;
    readonly fitted: true;
    readonly parameterCount: 870;
    readonly parametersSha256: string;
    readonly learnedStateSha256: string;
}
export interface NativeS2SLearnedModelArchive extends NativeS2SVerifiedModel {
    readonly canonical: Readonly<Record<string, TaskJson>>;
    readonly receiptSha256: string;
}
const fail = (detail: string): Either.Either<never, NativeS2SModelProtocolError> => Either.left(new NativeS2SModelProtocolError({ detail }));
const mapError = (error: {
    readonly detail: string;
}) => new NativeS2SModelProtocolError({ detail: error.detail });
const hash = (value: TaskJson) => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex");
const isArm = (value: unknown): value is NativeS2STrainingArm => value === "T16" || value === "P_CAP18" || value === "DS870";
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128)
            return false;
        if (value === null || typeof value !== "object")
            return true;
        if (!Reflect.ownKeys(value).every(key => { const d = Object.getOwnPropertyDescriptor(value, key); return d !== undefined && Object.hasOwn(d, "value") && dataOnly(d.value, depth + 1); }))
            return false;
        return !Array.isArray(value) || Object.getPrototypeOf(value) === Array.prototype && Object.keys(value).length === value.length && Array.from({ length: value.length }, (_, i) => Object.hasOwn(value, i)).every(Boolean);
    }
    catch {
        return false;
    }
};
const captureJson = (value: unknown): TaskJson | undefined => {
    try {
        return dataOnly(value) && validNativeTaskJson(value) ? snapshotNativeTaskJson(value) : undefined;
    }
    catch {
        return undefined;
    }
};
const exact = (value: TaskJson | undefined, keys: readonly string[]): value is Readonly<Record<string, TaskJson>> => value !== undefined && taskJsonRecord(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const sameInteger = (value: TaskJson | undefined, expected: number) => value === expected || value === BigInt(expected);
const bytesSha = (values: readonly number[]) => { const bytes = Buffer.alloc(values.length * 8); values.forEach((value, i) => bytes.writeDoubleLE(value, i * 8)); return createHash("sha256").update(bytes).digest("hex"); };
/** Canonical finite float hex, including source-permitted negative zero. */
export const parseNativeS2SParameterHex = (value: unknown): Either.Either<number, NativeS2SModelProtocolError> => {
    if (value === "0x0.0p+0")
        return Either.right(0);
    if (value === "-0x0.0p+0")
        return Either.right(-0);
    if (typeof value !== "string")
        return fail("parameter value must be canonical finite float hex");
    const match = /^(-?)0x([01])\.([0-9a-f]{13})p([+-][0-9]+)$/.exec(value);
    if (match === null)
        return fail("parameter value must be canonical finite float hex");
    const exponent = Number(match[4]);
    if (!Number.isSafeInteger(exponent) || exponent < -1022 || exponent > 1023 || match[2] === "0" && exponent !== -1022)
        return fail("parameter exponent is invalid");
    const bits = (match[1] === "-" ? 1n << 63n : 0n) | (match[2] === "1" ? BigInt(exponent + 1023) << 52n : 0n) | BigInt("0x" + match[3]);
    const bytes = Buffer.alloc(8);
    bytes.writeBigUInt64LE(bits);
    const result = bytes.readDoubleLE();
    return nativeS2SFloatHex(result) === value ? Either.right(result) : fail("parameter value is not canonical finite float hex");
};
const captureParameters = (arm: NativeS2STrainingArm, raw: unknown): Either.Either<NativeS2SParameters, NativeS2SModelProtocolError> => {
    try {
        const schema = nativeS2SParameterSchema(arm);
        if (raw === null || typeof raw !== "object" || Array.isArray(raw) || ![Object.prototype, null].includes(Object.getPrototypeOf(raw)) || Reflect.ownKeys(raw).length !== schema.length)
            return fail("model parameter schema drifted");
        const entries: [
            string,
            readonly number[]
        ][] = [];
        for (const [key, , shape] of schema) {
            const d = Object.getOwnPropertyDescriptor(raw, key), count = shape.reduce((a, b) => a * b, 1);
            if (d === undefined || !Object.hasOwn(d, "value") || !d.enumerable || !Array.isArray(d.value) || Object.getPrototypeOf(d.value) !== Array.prototype || d.value.length !== count || Reflect.ownKeys(d.value).length !== count + 1)
                return fail("model parameter tensor schema drifted");
            const values: number[] = [];
            for (let i = 0; i < count; i++) {
                const item = Object.getOwnPropertyDescriptor(d.value, i);
                if (item === undefined || !Object.hasOwn(item, "value") || typeof item.value !== "number" || !Number.isFinite(item.value))
                    return fail("model parameters must be dense finite values");
                values.push(item.value);
            }
            entries.push([key, Object.freeze(values)]);
        }
        return Either.right(Object.freeze(Object.fromEntries(entries)) as unknown as NativeS2SParameters);
    }
    catch {
        return fail("model parameters are not inspectable data");
    }
};
/** Recompute complete-data best-state losses; never trust a nominal parsed receipt. */
export const verifyNativeS2SModel = (arm: unknown, parameters: unknown, rawReceipt: unknown): Either.Either<NativeS2SVerifiedModel, NativeS2SModelProtocolError> => Either.gen(function* () {
    if (!isArm(arm))
        return yield* fail("model arm is invalid");
    const captured = yield* captureParameters(arm, parameters);
    const optimization = yield* parseNativeS2SOptimizationReceipt(rawReceipt).pipe(Either.mapLeft(mapError));
    const receipt = optimization.canonical, parametersSha256 = nativeS2SParameterSha256(captured, arm);
    if (receipt["arm"] !== arm || receipt["best_parameters_sha256"] !== parametersSha256)
        return yield* fail("parameters do not bind the best receipt checkpoint");
    const task = yield* parseNativeS2STaskArchiveEntry(receipt["task_spec"]).pipe(Either.mapLeft(mapError));
    const data = yield* compileNativeS2STaskData(task).pipe(Either.mapLeft(mapError));
    const train = yield* lossForNativeS2SReferenceParameters(arm, captured, data.trainInput, data.trainTargets, data.weights).pipe(Either.mapLeft(mapError));
    const dev = yield* lossForNativeS2SReferenceParameters(arm, captured, data.devInput, data.devTargets, data.weights).pipe(Either.mapLeft(mapError));
    if (nativeS2SFloatHex(train) !== receipt["best_train_loss_hex"] || nativeS2SFloatHex(dev) !== receipt["best_dev_loss_hex"])
        return yield* fail("learned best-state losses disagree with bound task and parameters");
    const learned = !sameInteger(receipt["best_update"], 0) && parametersSha256 !== receipt["initial_parameters_sha256"];
    const learnedStateSha256 = hash({ arm, fitted: true, learned, optimization_receipt_sha256: optimization.receiptSha256, parameters_sha256: parametersSha256, receipt_assurance: "SELF_CONSISTENT_COMMITMENT_REQUIRES_DETERMINISTIC_REPLAY", schema_version: "hswm-swm0w-s2s-training/v1", scientific_status: "LEARNED_ENGINEERING_ARTIFACT_UNJUDGED", structural_task_sha256: receipt["structural_task_sha256"]! });
    return Object.freeze({ arm, parameters: captured, optimization, learned, fitted: true, parameterCount: 870, parametersSha256, learnedStateSha256 });
});
export const archiveNativeS2SModel = (arm: unknown, parameters: unknown, rawReceipt: unknown): Either.Either<NativeS2SLearnedModelArchive, NativeS2SModelProtocolError> => Either.gen(function* () {
    const model = yield* verifyNativeS2SModel(arm, parameters, rawReceipt), p = model.parameters as unknown as Readonly<Record<string, readonly number[]>>;
    const tensors = nativeS2SParameterSchema(model.arm).map(([key, name, shape]) => ({ name, shape, values_hex: p[key]!.map(nativeS2SFloatHex), bytes_sha256: bytesSha(p[key]!), dtype: "float64-little-endian", schema_version: "hswm-swm0w-s2s-parameter-tensor/v1" }));
    const unsigned = { arm: model.arm, fitted: true, learned: model.learned, learned_state_sha256: model.learnedStateSha256, optimization_receipt: model.optimization.canonical, parameter_count: 870, parameters_sha256: model.parametersSha256, schema_version: "hswm-swm0w-s2s-learned-archive/v1", scientific_status: "CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED", tensors };
    const receiptSha256 = hash(unsigned), canonical = snapshotNativeTaskJson({ ...unsigned, receipt_sha256: receiptSha256 }) as Readonly<Record<string, TaskJson>>;
    return Object.freeze({ ...model, canonical, receiptSha256 });
});
export const parseNativeS2SLearnedModelArchive = (raw: unknown): Either.Either<NativeS2SLearnedModelArchive, NativeS2SModelProtocolError> => Either.gen(function* () {
    const value = captureJson(raw);
    if (!exact(value, ["arm", "fitted", "learned", "learned_state_sha256", "optimization_receipt", "parameter_count", "parameters_sha256", "schema_version", "scientific_status", "tensors", "receipt_sha256"]))
        return yield* fail("learned archive keys disagree with the exact schema");
    const arm = value["arm"];
    if (!isArm(arm) || value["fitted"] !== true || typeof value["learned"] !== "boolean" || !sameInteger(value["parameter_count"], 870) || value["schema_version"] !== "hswm-swm0w-s2s-learned-archive/v1" || value["scientific_status"] !== "CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED")
        return yield* fail("learned archive fixed contract drifted");
    const schema = nativeS2SParameterSchema(arm), tensors = value["tensors"];
    if (!Array.isArray(tensors) || tensors.length !== schema.length)
        return yield* fail("learned archive tensor schema drifted");
    const parameters: Record<string, readonly number[]> = {};
    for (const [index, [key, name, shape]] of schema.entries()) {
        const tensor = tensors[index];
        if (!exact(tensor, ["bytes_sha256", "dtype", "name", "schema_version", "shape", "values_hex"]) || tensor["name"] !== name || tensor["dtype"] !== "float64-little-endian" || tensor["schema_version"] !== "hswm-swm0w-s2s-parameter-tensor/v1" || renderNativeTaskJson(tensor["shape"]!) !== renderNativeTaskJson(shape))
            return yield* fail("learned archive ordered tensor schema drifted");
        const hex = tensor["values_hex"];
        if (!Array.isArray(hex) || hex.length !== shape.reduce((a, b) => a * b, 1))
            return yield* fail("parameter tensor value count disagrees with shape");
        const values = Object.freeze(yield* Either.all(hex.map(parseNativeS2SParameterHex)));
        if (bytesSha(values) !== tensor["bytes_sha256"])
            return yield* fail("parameter tensor bytes hash mismatch");
        parameters[key] = values;
    }
    const result = yield* archiveNativeS2SModel(arm, Object.freeze(parameters), value["optimization_receipt"]);
    if (renderNativeTaskJson(value) !== renderNativeTaskJson(result.canonical))
        return yield* fail("learned archive model bindings or receipt disagree");
    return result;
});
export const parseNativeS2SLearnedModelArchiveJson = (bytes: Uint8Array) => decodeNativeTaskJson(bytes).pipe(Either.mapLeft(mapError), Either.flatMap(parseNativeS2SLearnedModelArchive));
/** Revalidate public archive before scoring; caller-supplied nominal model objects are not trusted. */
export const scoreNativeS2SLearnedModelArchive = (raw: unknown, input: readonly number[]) => parseNativeS2SLearnedModelArchive(raw).pipe(Either.flatMap(model => {
    const result = model.arm === "T16" ? forwardNativeS2ST16(input, model.parameters as NativeS2ST16Parameters) : model.arm === "P_CAP18" ? forwardNativeS2SPCap18(input, model.parameters as NativeS2SPCap18Parameters) : forwardNativeS2SDs870(input, model.parameters as NativeS2SDs870Parameters);
    return result.pipe(Either.mapLeft(mapError));
}));
