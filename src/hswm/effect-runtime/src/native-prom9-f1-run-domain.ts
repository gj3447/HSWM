/** Pure receipt-derived token-parity assembly for already executed F1 runs. */
import { Data, Either } from "effect";
import { NATIVE_PROM9_F1_ARMS, validateNativeProm9TokenEnvelope } from "./native-prom9-f1-domain.js";
import { pythonJsonInt } from "./native-python-json-semantics-domain.js";
import { snapshotNativeTaskJson, taskJsonRecord, taskTextCompare, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { verifyNativeProm9RunReceipt } from "./native-prom9-receipt-domain.js";
import { canonicalNativeProm9Sha256 } from "./native-prom9-ports-domain.js";
type Arm = typeof NATIVE_PROM9_F1_ARMS[number];
type RecordJson = Readonly<Record<string, TaskJson>>;
const record = (value: unknown): value is RecordJson => validNativeTaskJson(value) && taskJsonRecord(value);
const dataOnly = (value: unknown, depth = 0): boolean => {
    if (depth > 128)
        return false;
    if (value === null || typeof value !== "object")
        return true;
    const descriptors = Object.getOwnPropertyDescriptors(value);
    return Reflect.ownKeys(descriptors).every(key => {
        const descriptor = Reflect.get(descriptors, key) as PropertyDescriptor;
        return Object.hasOwn(descriptor, "value") && dataOnly(descriptor.value, depth + 1);
    });
};
const safeRecord = (value: unknown): value is RecordJson => dataOnly(value) && record(value);
const own = (value: RecordJson, key: string): TaskJson | undefined => value[key];
const text = (value: TaskJson | undefined): string | undefined => typeof value === "string" && value.trim() !== "" ? value : undefined;
const arm = (value: TaskJson | undefined): value is Arm => typeof value === "string" && (NATIVE_PROM9_F1_ARMS as readonly string[]).includes(value);
const integer = (value: TaskJson | undefined): bigint | undefined => value === undefined ? undefined : pythonJsonInt(value);
export class NativeProm9F1RunProjectionError extends Data.TaggedError("NativeProm9F1RunProjectionError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9F1RunProjectionError> => Either.left(new NativeProm9F1RunProjectionError({ detail }));
/** Rebuild the Python `_token_parity_record` from sealed item-run receipts. */
export const assembleNativeProm9F1TokenParity = (rawRows: unknown, rawEnvelope: unknown, tolerance: unknown): Either.Either<TaskJson, NativeProm9F1RunProjectionError> => Either.gen(function* () {
    if (typeof tolerance !== "bigint" || tolerance < 0n)
        return yield* fail("token tolerance must be a non-negative bigint");
    if (!dataOnly(rawRows) || !Array.isArray(rawRows) || !validNativeTaskJson(rawRows))
        return yield* fail("item runs must be a dense JSON array");
    if (!dataOnly(rawEnvelope))
        return yield* fail("token envelope must contain data properties only");
    const envelope = yield* validateNativeProm9TokenEnvelope(rawEnvelope).pipe(Either.mapLeft(error => new NativeProm9F1RunProjectionError({ detail: error.detail })));
    const grouped = new Map<string, Map<Arm, RecordJson>>();
    for (const raw of rawRows) {
        if (!record(raw))
            return yield* fail("item run must be an object");
        yield* verifyNativeProm9RunReceipt(raw).pipe(Either.mapLeft(error => new NativeProm9F1RunProjectionError({ detail: error.detail })));
        const itemId = text(own(raw, "item_id")), armId = own(raw, "arm_id");
        if (itemId === undefined || !arm(armId))
            return yield* fail("item run identity is invalid");
        const arms = grouped.get(itemId) ?? new Map<Arm, RecordJson>();
        if (arms.has(armId))
            return yield* fail(`duplicate item-arm receipt: ${itemId}/${armId}`);
        arms.set(armId, raw);
        grouped.set(itemId, arms);
    }
    if (grouped.size === 0)
        return yield* fail("item runs must be non-empty");
    const items: {
        readonly item_id: string;
        readonly input_tokens_by_arm: Readonly<Record<string, bigint>>;
        readonly output_tokens_by_arm: Readonly<Record<string, bigint>>;
        readonly total_tokens_by_arm: Readonly<Record<string, bigint>>;
        readonly spread: bigint;
        readonly input_spread: bigint;
        readonly within_tolerance: boolean;
    }[] = [];
    for (const itemId of [...grouped.keys()].sort(taskTextCompare)) {
        const arms = grouped.get(itemId)!;
        if (arms.size !== NATIVE_PROM9_F1_ARMS.length)
            return yield* fail(`item ${itemId} does not cover every F1 arm`);
        const input: Record<string, bigint> = {}, output: Record<string, bigint> = {}, total: Record<string, bigint> = {};
        for (const armId of NATIVE_PROM9_F1_ARMS) {
            const row = arms.get(armId);
            if (row === undefined)
                return yield* fail(`item ${itemId} does not cover every F1 arm`);
            const inTokens = integer(own(row, "total_input_tokens")), outTokens = integer(own(row, "total_output_tokens"));
            if (inTokens === undefined || outTokens === undefined)
                return yield* fail("item run token totals are not Python integers");
            input[armId] = inTokens;
            output[armId] = outTokens;
            total[armId] = inTokens + outTokens;
        }
        const inputs = Object.values(input), totals = Object.values(total);
        const inputSpread = (inputs.reduce((left, right) => left > right ? left : right) - inputs.reduce((left, right) => left < right ? left : right));
        const spread = (totals.reduce((left, right) => left > right ? left : right) - totals.reduce((left, right) => left < right ? left : right));
        items.push(Object.freeze({ item_id: itemId, input_tokens_by_arm: Object.freeze(input), output_tokens_by_arm: Object.freeze(output), total_tokens_by_arm: Object.freeze(total), spread, input_spread: inputSpread, within_tolerance: spread <= tolerance }));
    }
    const inputSpreadMax = items.map(item => item.input_spread).reduce((left, right) => left > right ? left : right);
    const spreadMax = items.map(item => item.spread).reduce((left, right) => left > right ? left : right);
    return Object.freeze({ per_call_input_caps: own(envelope, "per_call_input_caps")!, per_call_output_caps: own(envelope, "per_call_output_caps")!, input_spread_max: inputSpreadMax, spread_max: spreadMax, all_within_tolerance: items.every(item => item.within_tolerance), items: Object.freeze(items) });
});
/** Inputs supplied after execution; registry construction and BPE projection remain external. */
export type NativeProm9F1SuiteAssemblyInput = Readonly<{
    readonly run_id: string;
    readonly mode: "development" | "sealed";
    readonly manifest_sha256: string;
    readonly model: string;
    readonly model_revision: string;
    readonly token_tolerance: bigint;
    readonly state_capacity_bytes: bigint;
    readonly preregistration_receipt_sha256: TaskJson;
    readonly token_envelope: TaskJson;
    readonly envelope_projection: TaskJson;
    readonly max_workers: bigint;
    readonly registries: TaskJson;
    readonly transport_audit?: TaskJson;
    readonly item_runs: readonly TaskJson[];
}>;
const sha = (value: TaskJson | undefined): value is string => typeof value === "string" && /^[0-9a-f]{64}$/u.test(value);
const exact = (value: RecordJson, names: readonly string[]): boolean => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
/** Assemble the Python `run_suite` receipt without invoking a model, spool, or tokenizer. */
export const assembleNativeProm9F1SuiteReceipt = (raw: unknown): Either.Either<TaskJson, NativeProm9F1RunProjectionError> => Either.gen(function* () {
    if (!safeRecord(raw))
        return yield* fail("suite assembly input must be a JSON object");
    const runId = text(own(raw, "run_id")), mode = own(raw, "mode"), manifest = own(raw, "manifest_sha256"), model = text(own(raw, "model")), revision = text(own(raw, "model_revision")), tolerance = integer(own(raw, "token_tolerance")), capacity = integer(own(raw, "state_capacity_bytes")), workers = integer(own(raw, "max_workers")), itemRuns = own(raw, "item_runs");
    if (runId === undefined || (mode !== "development" && mode !== "sealed") || !sha(manifest) || model === undefined || revision === undefined || tolerance === undefined || capacity === undefined || workers === undefined || !Array.isArray(itemRuns) || !validNativeTaskJson(itemRuns))
        return yield* fail("suite assembly input fields are invalid");
    const rawEnvelope = own(raw, "token_envelope"), projection = own(raw, "envelope_projection"), registries = own(raw, "registries"), preregistration = own(raw, "preregistration_receipt_sha256");
    if (rawEnvelope === undefined || projection === undefined || registries === undefined || preregistration === undefined)
        return yield* fail("suite assembly input is incomplete");
    const frozenRuns = snapshotNativeTaskJson(itemRuns);
    if (!Array.isArray(frozenRuns))
        return yield* fail("item_runs must be a dense JSON array");
    const input: NativeProm9F1SuiteAssemblyInput = Object.freeze({ run_id: runId, mode, manifest_sha256: manifest, model, model_revision: revision, token_tolerance: tolerance, state_capacity_bytes: capacity, preregistration_receipt_sha256: snapshotNativeTaskJson(preregistration), token_envelope: snapshotNativeTaskJson(rawEnvelope), envelope_projection: snapshotNativeTaskJson(projection), max_workers: workers, registries: snapshotNativeTaskJson(registries), ...(own(raw, "transport_audit") === undefined ? {} : { transport_audit: snapshotNativeTaskJson(own(raw, "transport_audit")!) }), item_runs: frozenRuns });
    if (input.run_id.trim() === "" || input.model.trim() === "" || input.model_revision.trim() === "")
        return yield* fail("suite identity text must be non-empty");
    if (input.token_tolerance < 0n || input.state_capacity_bytes < 0n || input.max_workers < 1n || input.max_workers > 8n)
        return yield* fail("suite numeric bounds are invalid");
    if (!sha(input.manifest_sha256))
        return yield* fail("manifest_sha256 must be a lowercase SHA-256");
    if (input.mode === "sealed" && !sha(input.preregistration_receipt_sha256))
        return yield* fail("sealed preregistration receipt must be a lowercase SHA-256");
    const envelope = yield* validateNativeProm9TokenEnvelope(input.token_envelope).pipe(Either.mapLeft(error => new NativeProm9F1RunProjectionError({ detail: error.detail })));
    if (!record(input.registries) || !exact(input.registries, NATIVE_PROM9_F1_ARMS))
        return yield* fail("registries must exactly cover F1 arms");
    for (const armId of NATIVE_PROM9_F1_ARMS) {
        const registry = own(input.registries, armId);
        if (!record(registry) || !sha(own(registry, "registry_sha256")))
            return yield* fail(`registry for ${armId} is invalid`);
        const unsigned = Object.fromEntries(Object.entries(registry).filter(([key]) => key !== "registry_sha256"));
        if ((yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(error => new NativeProm9F1RunProjectionError({ detail: error.detail })))) !== own(registry, "registry_sha256"))
            return yield* fail(`registry hash drifted for ${armId}`);
    }
    if (!record(input.envelope_projection) || !exact(input.envelope_projection, ["projected_total_tokens_by_arm", "projected_spread", "items"]))
        return yield* fail("envelope projection record drifted");
    const parity = yield* assembleNativeProm9F1TokenParity(input.item_runs, envelope, input.token_tolerance);
    if (input.transport_audit === null || input.transport_audit === undefined) {
        if (input.mode === "sealed")
            return yield* fail("sealed F1 requires a durable transport audit");
    }
    else {
        if (!record(input.transport_audit) || !sha(own(input.transport_audit, "audit_sha256")))
            return yield* fail("transport audit is invalid");
        const unsigned = Object.fromEntries(Object.entries(input.transport_audit).filter(([key]) => key !== "audit_sha256"));
        if ((yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(error => new NativeProm9F1RunProjectionError({ detail: error.detail })))) !== own(input.transport_audit, "audit_sha256"))
            return yield* fail("transport audit hash drifted");
        const expected = BigInt(input.item_runs.length * 3);
        const statuses = own(input.transport_audit, "status_counts");
        if (integer(own(input.transport_audit, "call_count")) !== expected || integer(own(input.transport_audit, "item_run_count")) !== BigInt(input.item_runs.length) || !record(statuses) || !exact(statuses, ["ACCEPTED"]) || integer(own(statuses, "ACCEPTED")) !== expected)
            return yield* fail("transport audit completeness drifted");
    }
    const unsigned: Record<string, TaskJson> = { schema_version: "hswm-prom9-f1-suite/v2", run_id: input.run_id, mode: input.mode, manifest_sha256: input.manifest_sha256, model: input.model, model_revision: input.model_revision, token_tolerance: input.token_tolerance, state_capacity_bytes: input.state_capacity_bytes, preregistration_receipt_sha256: input.preregistration_receipt_sha256, token_envelope: envelope, envelope_projection: input.envelope_projection, token_parity: parity, max_workers: input.max_workers, registries: input.registries, ...(input.transport_audit === undefined ? {} : { transport_audit: input.transport_audit }), item_runs: Object.freeze([...input.item_runs]), gold_opened: false, scientific_verdict_emitted: false };
    const sealed = Object.freeze({ ...unsigned, suite_receipt_sha256: yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(error => new NativeProm9F1RunProjectionError({ detail: error.detail }))) });
    return snapshotNativeTaskJson(sealed);
});
