/** Native task → complete train/dev data → seeded initialization → Adam.
 * This engineering result has no protocol-admission or final-candidate authority. */
import { Data, Either } from "effect";
import { validateNativeS2STask } from "./native-s2s-family-domain.js";
import { compileNativeS2STaskData, type NativeS2SStratumLossReceipt } from "./native-s2s-dataset-domain.js";
import { initializeNativeS2STrainingParameters } from "./native-s2s-initialization-domain.js";
import { fitNativeS2SCompiledArrays, validateNativeS2SFitConfig, type NativeS2SFitResult } from "./native-s2s-fit-domain.js";
export class NativeS2STaskFitError extends Data.TaggedError("NativeS2STaskFitError")<{
    readonly detail: string;
}> {
}
const mapError = (error: {
    readonly detail: string;
}) => new NativeS2STaskFitError({ detail: error.detail });
export interface NativeS2STaskFitResult {
    readonly schemaVersion: "hswm-native-s2s-task-fit-engineering/v1";
    readonly taskManifestSha256: string;
    readonly trainDatasetSha256: string;
    readonly devDatasetSha256: string;
    readonly strata: readonly NativeS2SStratumLossReceipt[];
    readonly fit: NativeS2SFitResult;
    readonly protocolReceiptStatus: "NOT_ISSUED_NATIVE_BACKEND_QUALIFICATION_REQUIRED";
}
export const fitNativeS2STask = (task: unknown, arm: unknown, config: unknown): Either.Either<NativeS2STaskFitResult, NativeS2STaskFitError> => Either.gen(function* () {
    const checkedTask = yield* validateNativeS2STask(task).pipe(Either.mapLeft(mapError));
    const checkedConfig = yield* validateNativeS2SFitConfig(config).pipe(Either.mapLeft(mapError));
    if (arm !== "T16" && arm !== "P_CAP18" && arm !== "DS870")
        return yield* Either.left(new NativeS2STaskFitError({ detail: "unsupported S2S arm" }));
    const initial = yield* initializeNativeS2STrainingParameters(arm, BigInt(checkedConfig.seed)).pipe(Either.mapLeft(mapError));
    const data = yield* compileNativeS2STaskData(checkedTask).pipe(Either.mapLeft(mapError));
    const fit = yield* fitNativeS2SCompiledArrays(arm, initial, data.trainInput, data.trainTargets, data.devInput, data.devTargets, data.weights, checkedConfig).pipe(Either.mapLeft(mapError));
    return Object.freeze({ schemaVersion: "hswm-native-s2s-task-fit-engineering/v1", taskManifestSha256: checkedTask.manifestSha256,
        trainDatasetSha256: data.trainDatasetSha256, devDatasetSha256: data.devDatasetSha256,
        strata: data.strata, fit, protocolReceiptStatus: "NOT_ISSUED_NATIVE_BACKEND_QUALIFICATION_REQUIRED" });
});
