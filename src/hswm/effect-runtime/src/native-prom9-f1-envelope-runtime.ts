/** Local source replay of an historical envelope with a separately identified native meter. */
import { Data, Effect, Either } from "effect";
import { enforceNativeProm9F1Envelope } from "./native-prom9-f1-envelope-domain.js";
import { normalizeNativeProm9F1Manifest } from "./native-prom9-f1-manifest-domain.js";
import { loadNativeProm9DerivedHistoricalQwen2Meter, NATIVE_PROM9_HISTORICAL_QWEN36_IDENTITY, NATIVE_PROM9_DERIVED_QWEN36_PROFILE, NativeProm9TokenMeterRuntimeError } from "./native-prom9-token-meter-runtime.js";
import { type NativeProm9TokenMeter } from "./native-prom9-token-meter-domain.js";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { snapshotNativeTaskJson, taskJsonRecord, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export class NativeProm9F1EnvelopeRuntimeError extends Data.TaggedError("NativeProm9F1EnvelopeRuntimeError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string) => new NativeProm9F1EnvelopeRuntimeError({ detail });
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128 || value === null || typeof value !== "object")
            return depth <= 128;
        return Reflect.ownKeys(Object.getOwnPropertyDescriptors(value)).every(key => { const descriptor = Object.getOwnPropertyDescriptor(value, key); return descriptor !== undefined && Object.hasOwn(descriptor, "value") && dataOnly(descriptor.value, depth + 1); });
    }
    catch {
        return false;
    }
};
const record = (value: unknown): value is Readonly<Record<string, TaskJson>> => dataOnly(value) && validNativeTaskJson(value) && taskJsonRecord(value);
const historicalIdentity = (declared: unknown): boolean => record(declared) && Object.keys(declared).length === Object.keys(NATIVE_PROM9_HISTORICAL_QWEN36_IDENTITY).length + 1 && Object.entries(NATIVE_PROM9_HISTORICAL_QWEN36_IDENTITY).every(([key, expected]) => declared[key] === expected) && typeof declared["validation_receipt_sha256"] === "string" && /^[0-9a-f]{64}$/.test(declared["validation_receipt_sha256"]);
/**
 * This is deliberately local-artifact-only. The derived no-NFC adapter remains
 * a qualified historical profile; this function does not promote it to live-run admission.
 */
export const loadNativeProm9F1HistoricalEnvelope = (directory: unknown, artifactHashes: unknown, rawManifest: unknown, rawRegistries: unknown): Effect.Effect<Readonly<{
    readonly manifest: TaskJson;
    readonly projection: TaskJson;
    readonly meter: NativeProm9TokenMeter;
    readonly executionProfile: typeof NATIVE_PROM9_DERIVED_QWEN36_PROFILE;
}>, NativeProm9F1EnvelopeRuntimeError, PosixFileSystem> => Effect.gen(function* () {
    if (!record(rawRegistries))
        return yield* Effect.fail(fail("registries are invalid"));
    const registries = snapshotNativeTaskJson(rawRegistries);
    const manifest = yield* Either.match(normalizeNativeProm9F1Manifest(rawManifest, registries), { onLeft: error => Effect.fail(fail(error.detail)), onRight: Effect.succeed });
    if (!record(manifest) || !record(manifest["token_envelope"]))
        return yield* Effect.fail(fail("normalized token envelope is invalid"));
    const envelope = manifest["token_envelope"];
    if (!historicalIdentity(envelope["tokenizer"]))
        return yield* Effect.fail(fail("tokenizer identity drifted from the qualified historical artifact profile"));
    const meter = yield* loadNativeProm9DerivedHistoricalQwen2Meter(directory, artifactHashes).pipe(Effect.mapError((error: NativeProm9TokenMeterRuntimeError) => fail(error.detail)));
    const projection = yield* Either.match(enforceNativeProm9F1Envelope(manifest["run_id"], manifest["items"], registries, meter, envelope, manifest["token_tolerance"]), { onLeft: error => Effect.fail(fail(error.detail)), onRight: Effect.succeed });
    return Object.freeze({ manifest: snapshotNativeTaskJson(manifest), projection: snapshotNativeTaskJson(projection), meter, executionProfile: NATIVE_PROM9_DERIVED_QWEN36_PROFILE });
});
