/** Bounded native model fit/verify executable; no final candidate or fit-replay admission. */
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { Data, Effect } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { archiveNativeS2SModel, parseNativeS2SLearnedModelArchiveJson } from "./native-s2s-model-protocol-domain.js";
import { buildNativeS2SOptimizationReceipt } from "./native-s2s-optimization-build-domain.js";
import { parseNativeS2STaskArchiveEntry } from "./native-s2s-task-archive-domain.js";
import { parseNativeS2STrainingConfig } from "./native-s2s-training-receipt-fields-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson } from "./native-task-json-domain.js";
export class NativeS2SModelCliError extends Data.TaggedError("NativeS2SModelCliError")<{
    readonly detail: string;
}> {
}
const error = (value: {
    readonly detail: string;
}) => new NativeS2SModelCliError({ detail: value.detail });
const usage = "usage: hswm-s2s-model verify --archive FILE | fit --task FILE --config FILE --arm T16|P_CAP18|DS870 --output NEW_FILE";
const sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const read = (path: string) => Effect.gen(function* () { const fs = yield* PosixFileSystem; return yield* fs.readRegularBounded(resolve(path), { maximumBytes: 16 * 1024 * 1024, minimumBytes: 1, operation: "read source-bound S2S model input" }).pipe(Effect.mapError(error)); });
export const runNativeS2SModelCli = (argv: readonly string[]): Effect.Effect<string, NativeS2SModelCliError, PosixFileSystem> => Effect.gen(function* () {
    const args = yield* Effect.try({ try: () => parseArgs({ args: [...argv], strict: true, allowPositionals: true, options: { archive: { type: "string" }, task: { type: "string" }, config: { type: "string" }, arm: { type: "string" }, output: { type: "string" }, help: { type: "boolean", short: "h" } } }), catch: () => new NativeS2SModelCliError({ detail: usage }) });
    if (args.values.help)
        return usage + "\nSelf-consistent model/optimization commitments; no deterministic fit replay or scientific outcome admission.\n";
    if (args.positionals.length !== 1)
        return yield* Effect.fail(new NativeS2SModelCliError({ detail: usage }));
    const command = args.positionals[0], v = args.values;
    if (command === "verify" && Object.keys(v).length === 1 && typeof v.archive === "string") {
        const source = yield* read(v.archive), model = yield* parseNativeS2SLearnedModelArchiveJson(source.bytes).pipe(Effect.mapError(error));
        return renderNativeTaskJson({ schema_version: "hswm-native-s2s-model-verification/v1", status: "SOURCE_MODEL_RECONSTRUCTION_VERIFIED", archive_file_sha256: sha(source.bytes), archive_receipt_sha256: model.receiptSha256, learned_state_sha256: model.learnedStateSha256, parameters_sha256: model.parametersSha256, optimization_receipt_sha256: model.optimization.receiptSha256, arm: model.arm, fitted: model.fitted, learned: model.learned, claim_ceiling: "SELF_CONSISTENCY_NOT_FIT_REPLAY_NOT_CANDIDATE_OUTCOME" }) + "\n";
    }
    if (command !== "fit" || Object.keys(v).length !== 4 || typeof v.task !== "string" || typeof v.config !== "string" || typeof v.arm !== "string" || typeof v.output !== "string")
        return yield* Effect.fail(new NativeS2SModelCliError({ detail: usage }));
    const taskSource = yield* read(v.task), configSource = yield* read(v.config);
    const taskJson = yield* decodeNativeTaskJson(taskSource.bytes).pipe(Effect.mapError(error)), configJson = yield* decodeNativeTaskJson(configSource.bytes).pipe(Effect.mapError(error));
    const task = yield* parseNativeS2STaskArchiveEntry(taskJson).pipe(Effect.mapError(error)), config = yield* parseNativeS2STrainingConfig(configJson).pipe(Effect.mapError(error));
    const built = yield* buildNativeS2SOptimizationReceipt(task, v.arm, config).pipe(Effect.mapError(error));
    const archive = yield* archiveNativeS2SModel(v.arm, built.parameters, built.receipt.canonical).pipe(Effect.mapError(error));
    const bytes = new TextEncoder().encode(renderNativeTaskJson(archive.canonical)), fs = yield* PosixFileSystem;
    yield* fs.writeExclusive(resolve(v.output), bytes, { mode: 0o600, sync: true, operation: "write native S2S model archive" }).pipe(Effect.mapError(error));
    return renderNativeTaskJson({ schema_version: "hswm-native-s2s-model-fit/v1", status: "MODEL_ARCHIVE_WRITTEN", archive_file_sha256: sha(bytes), archive_receipt_sha256: archive.receiptSha256, task_input_sha256: sha(taskSource.bytes), config_input_sha256: sha(configSource.bytes), best_update: built.fit.bestUpdate, learned: archive.learned, claim_ceiling: "NATIVE_FIT_ENGINEERING_NOT_ORIGINAL_TRAJECTORY_IDENTITY_NOT_CANDIDATE_OUTCOME" }) + "\n";
});
