/** Pure structural normalization of a captured F1 manifest, before BPE admission. */
import { Data, Either } from "effect";
import { validateNativeProm9TokenEnvelope } from "./native-prom9-f1-domain.js";
import { isTaskNumber, snapshotNativeTaskJson, taskJsonRecord, taskNumberIsFloat, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { pythonJsonInt, pythonJsonStrip } from "./native-python-json-semantics-domain.js";
export class NativeProm9F1ManifestError extends Data.TaggedError("NativeProm9F1ManifestError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9F1ManifestError> => Either.left(new NativeProm9F1ManifestError({ detail }));
const arms = ["typed_hswm_three_function_network", "flat_single_llm_three_call_workflow", "vector_memory_three_call_workflow", "typed_network_role_removed_schema_preserving_null", "typed_network_with_role_instructions_shuffled_but_ports_preserved"];
const record = (v: unknown): v is Readonly<Record<string, TaskJson>> => validNativeTaskJson(v) && taskJsonRecord(v);
const dataOnly = (v: unknown): boolean => { try {
    if (v === null || typeof v !== "object")
        return true;
    const descriptors = [...Object.values(Object.getOwnPropertyDescriptors(v)), ...Object.getOwnPropertySymbols(v).map(key => Object.getOwnPropertyDescriptor(v, key)!)];
    return descriptors.every(d => d.get === undefined && d.set === undefined && dataOnly(d.value));
}
catch {
    return false;
} };
const text = (v: TaskJson | undefined) => typeof v === "string" && pythonJsonStrip(v) !== "" ? v : undefined;
const exact = (v: Readonly<Record<string, TaskJson>>, ks: readonly string[]) => Object.keys(v).length === ks.length && ks.every(k => Object.hasOwn(v, k));
const nonnegative = (v: TaskJson | undefined) => { const n = v === undefined || !isTaskNumber(v) || taskNumberIsFloat(v) ? undefined : pythonJsonInt(v); return n !== undefined && n >= 0n; };
const positive = (v: TaskJson | undefined) => { const n = v === undefined || !isTaskNumber(v) || taskNumberIsFloat(v) ? undefined : pythonJsonInt(v); return n !== undefined && n > 0n; };
const sha = (v: TaskJson | undefined) => typeof v === "string" && /^[0-9a-f]{64}$/u.test(v);
export const normalizeNativeProm9F1Manifest = (raw: unknown, registries: unknown): Either.Either<TaskJson, NativeProm9F1ManifestError> => Either.gen(function* () {
    if (!dataOnly(raw) || !dataOnly(registries) || !record(raw) || !record(registries))
        return yield* fail("F1 manifest and registries must be JSON objects");
    const ks = ["schema_version", "run_id", "mode", "model", "model_revision", "token_tolerance", "state_capacity_bytes", "state_bytes_by_arm", "preregistration_receipt_sha256", "token_envelope", "items"];
    if (!exact(raw, ks) || raw["schema_version"] !== "hswm-prom9-f1-manifest/v2")
        return yield* fail("unsupported F1 manifest schema");
    const mode = raw["mode"];
    if (mode !== "development" && mode !== "sealed")
        return yield* fail("manifest mode must be development or sealed");
    if (text(raw["run_id"]) === undefined || text(raw["model"]) === undefined || text(raw["model_revision"]) === undefined || !nonnegative(raw["token_tolerance"]) || !nonnegative(raw["state_capacity_bytes"]))
        return yield* fail("manifest identity or bounds are invalid");
    if (mode === "sealed" ? !sha(raw["preregistration_receipt_sha256"]) : raw["preregistration_receipt_sha256"] !== null && !sha(raw["preregistration_receipt_sha256"]))
        return yield* fail("invalid preregistration receipt");
    const state = raw["state_bytes_by_arm"], capacity = pythonJsonInt(raw["state_capacity_bytes"]);
    if (!record(state) || !exact(state, arms) || capacity === undefined || arms.some(a => { const stateBytes = pythonJsonInt(state[a]); return !nonnegative(state[a]) || stateBytes === undefined || stateBytes > capacity; }))
        return yield* fail("state_bytes_by_arm must exactly cover F1 arms");
    if (!exact(registries, arms))
        return yield* fail("registries must exactly cover F1 arms");
    const items = raw["items"];
    if (!Array.isArray(items) || items.length === 0)
        return yield* fail("manifest items must be non-empty");
    const seen = new Set<string>();
    for (const item of items) {
        if (!record(item) || !exact(item, ["item_id", "query_text", "allowed_evidence_types", "candidates", "max_evidence_items", "max_input_tokens", "max_output_tokens_per_call"]))
            return yield* fail("invalid manifest item");
        const id = text(item["item_id"]), candidates = item["candidates"];
        if (id === undefined || seen.has(id) || text(item["query_text"]) === undefined || !Array.isArray(item["allowed_evidence_types"]) || item["allowed_evidence_types"].length === 0 || item["allowed_evidence_types"].some(x => text(x) === undefined) || !Array.isArray(candidates) || candidates.length === 0 || !positive(item["max_evidence_items"]) || !positive(item["max_input_tokens"]) || !positive(item["max_output_tokens_per_call"]))
            return yield* fail("invalid manifest item");
        const bondIds = new Set<string>(), evidenceIds = new Set<string>();
        for (const candidate of candidates) {
            if (!record(candidate) || !exact(candidate, ["bond_id", "evidence_id", "content", "observable"]))
                return yield* fail("invalid manifest candidate");
            const bondId = text(candidate["bond_id"]), evidenceId = text(candidate["evidence_id"]);
            if (bondId === undefined || evidenceId === undefined || bondIds.has(bondId) || evidenceIds.has(evidenceId) || text(candidate["content"]) === undefined || !record(candidate["observable"]))
                return yield* fail("invalid manifest candidate");
            bondIds.add(bondId);
            evidenceIds.add(evidenceId);
        }
        const maxEvidence = pythonJsonInt(item["max_evidence_items"]);
        if (maxEvidence === undefined || maxEvidence > BigInt(candidates.length))
            return yield* fail("max_evidence_items exceeds candidate count");
        seen.add(id);
    }
    const envelope = yield* validateNativeProm9TokenEnvelope(raw["token_envelope"]).pipe(Either.mapLeft(e => new NativeProm9F1ManifestError({ detail: e.detail })));
    return snapshotNativeTaskJson(Object.freeze({ ...raw, token_envelope: envelope }));
});
