/** Pure F1 prompt-payload construction, excluding token fitting and model I/O. */
import { Data, Either } from "effect";
import { canonicalNativeProm9Sha256 } from "./native-prom9-ports-domain.js";
import { isTaskNumber, renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, taskNumberIsFloat, taskNumberValue, taskTextCompare, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { pythonJsonStrip } from "./native-python-json-semantics-domain.js";
export class NativeProm9F1PayloadError extends Data.TaggedError("NativeProm9F1PayloadError")<{
    readonly detail: string;
}> {
}
export const NATIVE_PROM9_F1_PAYLOAD_ARMS = Object.freeze(["typed_hswm_three_function_network", "flat_single_llm_three_call_workflow", "vector_memory_three_call_workflow", "typed_network_role_removed_schema_preserving_null", "typed_network_with_role_instructions_shuffled_but_ports_preserved"] as const);
type RecordJson = Readonly<Record<string, TaskJson>>;
type Candidate = Readonly<{
    bondId: string;
    evidenceId: string;
    content: string;
    observable: RecordJson;
}>;
export type NativeProm9F1PayloadItem = Readonly<{
    itemId: string;
    queryText: string;
    allowedEvidenceTypes: readonly string[];
    candidates: readonly Candidate[];
    maxEvidenceItems: bigint;
    maxInputTokens: bigint;
    maxOutputTokensPerCall: bigint;
}>;
const fail = (detail: string): Either.Either<never, NativeProm9F1PayloadError> => Either.left(new NativeProm9F1PayloadError({ detail }));
const dataOnly = (value: unknown, depth = 0): boolean => { try {
    if (depth > 128)
        return false;
    if (value === null || typeof value !== "object")
        return true;
    return Reflect.ownKeys(Object.getOwnPropertyDescriptors(value)).every(key => { const descriptor = Object.getOwnPropertyDescriptor(value, key); return descriptor !== undefined && descriptor.get === undefined && descriptor.set === undefined && dataOnly(descriptor.value, depth + 1); });
}
catch {
    return false;
} };
const record = (value: unknown): value is RecordJson => validNativeTaskJson(value) && taskJsonRecord(value);
const text = (value: TaskJson | undefined): string | undefined => typeof value === "string" && pythonJsonStrip(value) !== "" ? value : undefined;
const positive = (value: TaskJson | undefined): bigint | undefined => { if (value === undefined || !isTaskNumber(value) || taskNumberIsFloat(value))
    return undefined; const numeric = taskNumberValue(value); return typeof numeric === "bigint" ? numeric > 0n ? numeric : undefined : Number.isSafeInteger(numeric) && numeric > 0 ? BigInt(numeric) : undefined; };
const exact = (value: RecordJson, keys: readonly string[]): boolean => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const snapshotRecord = (value: TaskJson): RecordJson | undefined => { const copied = snapshotNativeTaskJson(value); return record(copied) ? copied : undefined; };
export const normalizeNativeProm9F1PayloadItem = (raw: unknown): Either.Either<NativeProm9F1PayloadItem, NativeProm9F1PayloadError> => Either.gen(function* () {
    if (!dataOnly(raw) || !record(raw) || !exact(raw, ["item_id", "query_text", "allowed_evidence_types", "candidates", "max_evidence_items", "max_input_tokens", "max_output_tokens_per_call"]))
        return yield* fail("payload item is invalid");
    const itemId = text(raw["item_id"]), queryText = text(raw["query_text"]), evidenceTypes = raw["allowed_evidence_types"], candidates = raw["candidates"], maxEvidenceItems = positive(raw["max_evidence_items"]), maxInputTokens = positive(raw["max_input_tokens"]), maxOutputTokensPerCall = positive(raw["max_output_tokens_per_call"]);
    if (itemId === undefined || queryText === undefined || !Array.isArray(evidenceTypes) || evidenceTypes.length === 0 || evidenceTypes.some(value => text(value) === undefined) || !Array.isArray(candidates) || candidates.length === 0 || maxEvidenceItems === undefined || maxInputTokens === undefined || maxOutputTokensPerCall === undefined || maxEvidenceItems > BigInt(candidates.length))
        return yield* fail("payload item is invalid");
    const seenBonds = new Set<string>(), seenEvidence = new Set<string>();
    const normalized: Candidate[] = [];
    for (const rawCandidate of candidates) {
        if (!record(rawCandidate) || !exact(rawCandidate, ["bond_id", "evidence_id", "content", "observable"]))
            return yield* fail("payload candidate is invalid");
        const bondId = text(rawCandidate["bond_id"]), evidenceId = text(rawCandidate["evidence_id"]), content = text(rawCandidate["content"]), rawObservable = rawCandidate["observable"], observable = rawObservable === undefined ? undefined : snapshotRecord(rawObservable);
        if (bondId === undefined || evidenceId === undefined || content === undefined || observable === undefined || seenBonds.has(bondId) || seenEvidence.has(evidenceId))
            return yield* fail("payload candidate is invalid");
        seenBonds.add(bondId);
        seenEvidence.add(evidenceId);
        normalized.push(Object.freeze({ bondId, evidenceId, content, observable }));
    }
    return Object.freeze({ itemId, queryText, allowedEvidenceTypes: Object.freeze([...evidenceTypes] as string[]), candidates: Object.freeze(normalized), maxEvidenceItems, maxInputTokens, maxOutputTokensPerCall });
});
export const nativeProm9F1RequestId = (runId: unknown, armId: unknown, itemId: unknown): Either.Either<string, NativeProm9F1PayloadError> => Either.gen(function* () {
    if (typeof runId !== "string" || typeof armId !== "string" || typeof itemId !== "string")
        return yield* fail("request identity must be text");
    const digest = yield* canonicalNativeProm9Sha256(Object.freeze({ run_id: runId, arm_id: armId, item_id: itemId })).pipe(Either.mapLeft(error => new NativeProm9F1PayloadError({ detail: error.detail })));
    return `req-${digest.slice(0, 8)}`;
});
export const nativeProm9F1ObservableForArm = (armId: unknown, raw: unknown): Either.Either<TaskJson, NativeProm9F1PayloadError> => Either.gen(function* () {
    if (!dataOnly(raw) || !record(raw))
        return yield* fail("candidate observable must be a JSON object");
    const allowed = armId === "flat_single_llm_three_call_workflow" ? new Set(["flat_position", "source_type", "flat_score"]) : armId === "vector_memory_three_call_workflow" ? new Set(["vector_score", "source_type"]) : undefined;
    const entries = Object.keys(raw).filter(key => allowed === undefined || allowed.has(key)).sort(taskTextCompare).map(key => [key, snapshotNativeTaskJson(raw[key]!)] as const);
    return snapshotNativeTaskJson(Object.freeze(Object.fromEntries(entries)));
});
export const nativeProm9F1CandidateTableForArm = (armId: unknown, rawCandidates: unknown): Either.Either<TaskJson, NativeProm9F1PayloadError> => Either.gen(function* () {
    if (!dataOnly(rawCandidates) || !Array.isArray(rawCandidates) || rawCandidates.length === 0)
        return yield* fail("candidates must be a non-empty dense JSON array");
    const candidates: Candidate[] = [];
    for (const raw of rawCandidates) {
        const item = yield* normalizeNativeProm9F1PayloadItem({ item_id: "item", query_text: "query", allowed_evidence_types: ["evidence"], candidates: [raw], max_evidence_items: 1, max_input_tokens: 1, max_output_tokens_per_call: 1 });
        candidates.push(item.candidates[0]!);
    }
    const observables = yield* Either.all(candidates.map(candidate => nativeProm9F1ObservableForArm(armId, candidate.observable)));
    const observableRecords: RecordJson[] = [];
    for (const observable of observables) {
        const value = snapshotRecord(observable);
        if (value === undefined)
            return yield* fail("candidate observable is invalid");
        observableRecords.push(value);
    }
    const keySets = observableRecords.map(value => renderNativeTaskJson(Object.freeze(Object.keys(value).sort(taskTextCompare))));
    if (new Set(keySets).size !== 1)
        return yield* fail("candidate observable key sets must be uniform");
    const allKeys = Object.keys(observableRecords[0]!).sort(taskTextCompare), constants: Record<string, TaskJson> = {}, varying: string[] = [];
    for (const key of allKeys) {
        const values = observableRecords.map(value => value[key]!);
        if (new Set(values.map(value => renderNativeTaskJson(snapshotNativeTaskJson(value)))).size === 1)
            constants[key] = snapshotNativeTaskJson(values[0]!);
        else
            varying.push(key);
    }
    const rows = candidates.map((candidate, index) => Object.freeze([candidate.bondId, candidate.evidenceId, ...varying.map(key => snapshotNativeTaskJson(observableRecords[index]![key]!))]));
    return snapshotNativeTaskJson(Object.freeze({ constants: Object.freeze(constants), columns: Object.freeze(["bond_id", "evidence_id", ...varying]), rows: Object.freeze(rows) }));
});
export const nativeProm9F1QueryEnvelopePayload = (rawItem: unknown, requestId: unknown, parityFiller: unknown = ""): Either.Either<TaskJson, NativeProm9F1PayloadError> => Either.gen(function* () { const item = yield* normalizeNativeProm9F1PayloadItem(rawItem); if (typeof requestId !== "string" || typeof parityFiller !== "string")
    return yield* fail("payload request_id and parity_filler must be text"); return snapshotNativeTaskJson(Object.freeze({ request_id: requestId, query_text: item.queryText, allowed_evidence_types: Object.freeze([...item.allowedEvidenceTypes]), budget: Object.freeze({ max_candidates: BigInt(item.candidates.length), max_evidence_items: item.maxEvidenceItems, max_input_tokens: item.maxInputTokens, max_output_tokens: item.maxOutputTokensPerCall }), parity_filler: parityFiller })); });
export const nativeProm9F1BondScoringPayload = (rawItem: unknown, armId: unknown, requestId: unknown, queryPlan: unknown, parityFiller: unknown = ""): Either.Either<TaskJson, NativeProm9F1PayloadError> => Either.gen(function* () { const item = yield* normalizeNativeProm9F1PayloadItem(rawItem); if (typeof requestId !== "string" || typeof parityFiller !== "string" || !dataOnly(queryPlan) || !record(queryPlan))
    return yield* fail("bond payload inputs are invalid"); const table = yield* nativeProm9F1CandidateTableForArm(armId, item.candidates.map(candidate => Object.freeze({ bond_id: candidate.bondId, evidence_id: candidate.evidenceId, content: candidate.content, observable: candidate.observable }))); return snapshotNativeTaskJson(Object.freeze({ request_id: requestId, query_plan: snapshotNativeTaskJson(queryPlan), candidate_table: table, candidate_budget: item.maxEvidenceItems, parity_filler: parityFiller })); });
export const nativeProm9F1AnswerContextPayload = (rawItem: unknown, requestId: unknown, queryPlan: unknown, rawSelected: unknown, parityFiller: unknown = ""): Either.Either<TaskJson, NativeProm9F1PayloadError> => Either.gen(function* () { const item = yield* normalizeNativeProm9F1PayloadItem(rawItem); if (typeof requestId !== "string" || typeof parityFiller !== "string" || !dataOnly(queryPlan) || !record(queryPlan) || !dataOnly(rawSelected) || !Array.isArray(rawSelected))
    return yield* fail("answer payload inputs are invalid"); const selected: TaskJson[] = []; for (const raw of rawSelected) {
    if (!record(raw) || text(raw["evidence_id"]) === undefined || text(raw["content"]) === undefined)
        return yield* fail("selected candidate is invalid");
    selected.push(Object.freeze({ evidence_id: raw["evidence_id"]!, content: raw["content"]! }));
} return snapshotNativeTaskJson(Object.freeze({ request_id: requestId, query_text: item.queryText, query_plan: snapshotNativeTaskJson(queryPlan), selected_evidence: Object.freeze(selected), max_answer_tokens: item.maxOutputTokensPerCall, parity_filler: parityFiller })); });
