/** Exact task and batch archive boundary of the original S2S protocol. */
import { Data, Either } from "effect";
import { createHash } from "node:crypto";
import { renderNativeTaskJson, taskJsonRecord, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { assembleNativeS2STaskBatch, nativeS2STaskManifestPayload, validateNativeS2STask, type NativeS2STask } from "./native-s2s-family-domain.js";
export const NATIVE_S2S_TASK_ARCHIVE_SCHEMA = "hswm-swm0w-s2s-task-batch-archive/v1";
export class NativeS2STaskArchiveError extends Data.TaggedError("NativeS2STaskArchiveError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeS2STaskArchiveError> => Either.left(new NativeS2STaskArchiveError({ detail }));
const mapError = (error: {
    readonly detail: string;
}) => new NativeS2STaskArchiveError({ detail: error.detail });
const record = (value: unknown, keys: readonly string[]): Either.Either<Readonly<Record<string, TaskJson>>, NativeS2STaskArchiveError> => validNativeTaskJson(value) && taskJsonRecord(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key)) ? Either.right(value) : fail("archive object fields drifted");
const list = (value: TaskJson | undefined, length?: number): Either.Either<readonly TaskJson[], NativeS2STaskArchiveError> => Array.isArray(value) && (length === undefined || value.length === length) ? Either.right(value) : fail("archive array shape drifted");
const integer = (value: TaskJson | undefined): value is number | bigint => typeof value === "bigint" || typeof value === "number" && Number.isSafeInteger(value);
const digest = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value)).digest("hex");
const same = (a: TaskJson, b: TaskJson): boolean => renderNativeTaskJson(a) === renderNativeTaskJson(b);
export const parseNativeS2STaskArchiveEntry = (value: unknown): Either.Either<NativeS2STask, NativeS2STaskArchiveError> => Either.gen(function* () {
    const data = yield* record(value, ["draw_index", "family_certificate_sha256", "family_definition_sha256", "manifest_sha256", "rank_gains", "schema_version", "seed_commitment_sha256", "split", "structural_target_sha256", "structural_task_sha256"]);
    if (data["schema_version"] !== "hswm-swm0w-s2s-task/v2" || !integer(data["draw_index"]))
        return yield* fail("task schema or draw index drifted");
    const gainRows = yield* list(data["rank_gains"], 12);
    const gains = yield* Either.all(gainRows.map((row, index) => Either.gen(function* () {
        const entry = yield* record(row, ["channel", "gain", "rank", "role"]);
        if (entry["role"] !== `r${Math.floor(index / 4)}` || entry["channel"] !== `c${Math.floor(index / 2) % 2}` || !integer(entry["rank"]) || BigInt(entry["rank"]) !== BigInt(index % 2) || !integer(entry["gain"]))
            return yield* fail("rank gains are not in canonical typed order");
        return Number(entry["gain"]);
    })));
    const split = yield* record(data["split"], ["coefficients", "residues"]);
    const coefficients = yield* list(split["coefficients"], 3);
    if (!coefficients.every(integer))
        return yield* fail("split coefficients require exact integers");
    const residueMap = yield* record(split["residues"], ["train", "dev", "test"]);
    const residues = yield* Either.all((["train", "dev", "test"] as const).map(name => Either.gen(function* () {
        const values = yield* list(residueMap[name]);
        if (!values.every(integer))
            return yield* fail("split residues require exact integers");
        return Object.freeze([name, Object.freeze(values.map(Number))] as const);
    })));
    const task = yield* validateNativeS2STask(Object.freeze({
        seedCommitmentSha256: data["seed_commitment_sha256"], drawIndex: BigInt(data["draw_index"]),
        rankGains: Object.freeze(gains), splitCoefficients: Object.freeze(coefficients.map(Number)), splitResidues: Object.freeze(residues),
        familyDefinitionSha256: data["family_definition_sha256"], familyCertificateSha256: data["family_certificate_sha256"],
        structuralTargetSha256: data["structural_target_sha256"], structuralTaskSha256: data["structural_task_sha256"], manifestSha256: data["manifest_sha256"],
    })).pipe(Either.mapLeft(mapError));
    const payload = yield* nativeS2STaskManifestPayload(task).pipe(Either.mapLeft(mapError));
    if (!same(data, { ...payload, manifest_sha256: task.manifestSha256 }))
        return yield* fail("task canonical encoding drifted");
    return task;
});
export const serializeNativeS2STaskArchive = (tasks: unknown) => Either.gen(function* () {
    const batch = yield* assembleNativeS2STaskBatch(tasks).pipe(Either.mapLeft(mapError));
    const taskPayloads = yield* Either.all(batch.tasks.map(task => nativeS2STaskManifestPayload(task).pipe(Either.mapLeft(mapError), Either.map(payload => Object.freeze({ ...payload, manifest_sha256: task.manifestSha256 })))));
    const batchPayload = Object.freeze({
        duplicate_structural_target_draws: batch.duplicateStructuralTargetDraws,
        duplicate_structural_task_draws: batch.duplicateStructuralTaskDraws,
        requested_count: batch.requestedCount, schema_version: "hswm-swm0w-s2s-task-batch/v2",
        seed_commitment_sha256: batch.seedCommitmentSha256,
        task_manifest_sha256s: Object.freeze(batch.tasks.map(task => task.manifestSha256)), batch_sha256: batch.batchSha256,
    });
    const unsigned = Object.freeze({ batch: batchPayload, schema_version: NATIVE_S2S_TASK_ARCHIVE_SCHEMA, tasks: Object.freeze(taskPayloads) });
    return Object.freeze({ ...unsigned, archive_sha256: digest(unsigned) });
});
export const parseNativeS2STaskArchive = (value: unknown) => Either.gen(function* () {
    const data = yield* record(value, ["archive_sha256", "batch", "schema_version", "tasks"]);
    if (data["schema_version"] !== NATIVE_S2S_TASK_ARCHIVE_SCHEMA)
        return yield* fail("task-batch archive schema drifted");
    const rows = yield* list(data["tasks"]);
    const tasks = yield* Either.all(rows.map(parseNativeS2STaskArchiveEntry));
    const reconstructed = yield* serializeNativeS2STaskArchive(tasks);
    if (!same(data, reconstructed))
        return yield* fail("task-batch archive binding, duplicate record or canonical encoding drifted");
    return yield* assembleNativeS2STaskBatch(tasks).pipe(Either.mapLeft(mapError));
});
