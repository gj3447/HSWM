/** Pure QF -> BF -> AF state transitions. An injected meter is not tokenizer admission. */
import { Either } from "effect";
import { NativeProm9CallError, prepareNativeProm9Call, type NativeProm9CompletedCall } from "./native-prom9-call-domain.js";
import { NATIVE_PROM9_F1_PAYLOAD_ARMS, nativeProm9F1AnswerContextPayload, nativeProm9F1BondScoringPayload, nativeProm9F1QueryEnvelopePayload, nativeProm9F1RequestId, normalizeNativeProm9F1PayloadItem } from "./native-prom9-f1-payload-domain.js";
import { canonicalNativeProm9Sha256 } from "./native-prom9-ports-domain.js";
import { fitNativeProm9ParityFiller, type NativeProm9TokenMeter } from "./native-prom9-token-meter-domain.js";
import { PYTHON_ISALNUM_RANGES } from "./native-python-isalnum-data.js";
import { pythonJsonCasefold } from "./native-python-json-semantics-domain.js";
import { isTaskNumber, renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, taskNumberIsFloat, taskNumberValue, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
type JsonRecord = Readonly<Record<string, TaskJson>>;
const fail = (detail: string): Either.Either<never, NativeProm9CallError> => Either.left(new NativeProm9CallError({ detail }));
const error = (value: {
    readonly detail: string;
}) => new NativeProm9CallError({ detail: value.detail });
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128)
            return false;
        if (value === null || typeof value !== "object")
            return true;
        return Reflect.ownKeys(value).every(key => { const descriptor = Object.getOwnPropertyDescriptor(value, key); return descriptor !== undefined && Object.hasOwn(descriptor, "value") && dataOnly(descriptor.value, depth + 1); });
    }
    catch {
        return false;
    }
};
const record = (value: unknown): value is JsonRecord => dataOnly(value) && validNativeTaskJson(value) && taskJsonRecord(value);
const exact = (value: JsonRecord, keys: readonly string[]): boolean => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const copy = (value: JsonRecord): JsonRecord => snapshotNativeTaskJson(value) as JsonRecord;
const integer = (value: TaskJson | undefined): bigint | undefined => {
    if (value === undefined || !isTaskNumber(value) || taskNumberIsFloat(value))
        return undefined;
    const n = taskNumberValue(value);
    return typeof n === "bigint" ? n : Number.isSafeInteger(n) ? BigInt(n) : undefined;
};
const safeCount = (value: TaskJson | undefined): number | undefined => { const n = integer(value); return n !== undefined && n >= 0n && n <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(n) : undefined; };
const sha = (value: TaskJson | undefined): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
export const nativeProm9PythonIsAlnum = (codepoint: number): boolean => {
    if (!Number.isInteger(codepoint) || codepoint < 0 || codepoint > 0x10ffff)
        return false;
    let low = 0, high = PYTHON_ISALNUM_RANGES.length - 1;
    while (low <= high) {
        const middle = Math.floor((low + high) / 2), range = PYTHON_ISALNUM_RANGES[middle]!;
        if (codepoint < range[0])
            high = middle - 1;
        else if (codepoint > range[1])
            low = middle + 1;
        else
            return true;
    }
    return false;
};
/** Ports have already required text; Python 3.12 / Unicode 15 membership is pinned. */
export const nativeProm9RequestIdMatches = (observed: string, expected: string): boolean => {
    const core = (text: string) => Array.from(pythonJsonCasefold(text)).filter(c => nativeProm9PythonIsAlnum(c.codePointAt(0)!)).join("");
    return core(observed) === core(expected);
};
export interface NativeProm9NetworkStage {
    readonly request: JsonRecord;
    readonly advance: (completed: NativeProm9CompletedCall) => Either.Either<NativeProm9NetworkStage | JsonRecord, NativeProm9CallError>;
}
/** Historical r5 used 20 hex digits; current source uses 8. Never auto-detect from model output. */
export type NativeProm9RequestIdProfile = "CURRENT_8_HEX" | "HISTORICAL_20_HEX";
const captureCompletion = (request: JsonRecord, observed: NativeProm9CompletedCall): Either.Either<NativeProm9CompletedCall, NativeProm9CallError> => Either.gen(function* () {
    if (!record(observed) || !exact(observed, ["output", "receipt"]) || !record(observed["receipt"]))
        return yield* fail("invalid completed call");
    const receipt = observed["receipt"], prepared = yield* prepareNativeProm9Call(request);
    const response = { payload: observed["output"], ...Object.fromEntries(["model", "model_revision", "input_tokens", "output_tokens", "latency_ms", "cache_status", "retries"].map(key => [key, receipt[key]])) };
    const completed = yield* prepared.complete(response);
    if (renderNativeTaskJson(completed.receipt) !== renderNativeTaskJson(receipt))
        return yield* fail("completed call does not bind this network stage");
    return completed;
});
/** Captures all JSON aliases before I/O. Optional v3 identities affect only universe commitment. */
export const prepareNativeProm9Network = (raw: unknown, meter: NativeProm9TokenMeter, requestIdProfile: NativeProm9RequestIdProfile = "CURRENT_8_HEX"): Either.Either<NativeProm9NetworkStage, NativeProm9CallError> => Either.gen(function* () {
    if (requestIdProfile !== "CURRENT_8_HEX" && requestIdProfile !== "HISTORICAL_20_HEX")
        return yield* fail("unsupported request ID source profile");
    if (!record(raw) || !exact(raw, ["run_id", "arm_id", "item", "registry", "envelope", "persistent_state_bytes"]))
        return yield* fail("invalid item-run fields");
    const captured = copy(raw), runId = captured["run_id"], armId = captured["arm_id"], rawItem = captured["item"], registry = captured["registry"], envelope = captured["envelope"], stateBytes = integer(captured["persistent_state_bytes"]);
    if (typeof runId !== "string" || typeof armId !== "string" || !NATIVE_PROM9_F1_PAYLOAD_ARMS.some(arm => arm === armId))
        return yield* fail("unsupported F1 arm or run identity");
    if (stateBytes === undefined || stateBytes < 0n)
        return yield* fail("persistent_state_bytes must be a non-negative integer");
    if (!record(rawItem) || !Array.isArray(rawItem["candidates"]))
        return yield* fail("invalid network item");
    if (rawItem["component_id"] !== undefined && rawItem["component_id"] !== null && !sha(rawItem["component_id"]))
        return yield* fail("invalid component identity");
    const candidates = rawItem["candidates"];
    const identities: TaskJson[] = [];
    for (const candidate of candidates) {
        if (!record(candidate) || candidate["source_entity_id"] !== undefined && candidate["source_entity_id"] !== null && !sha(candidate["source_entity_id"]))
            return yield* fail("invalid candidate source identity");
        const contentSha = yield* canonicalNativeProm9Sha256({ content: candidate["content"] ?? null }).pipe(Either.mapLeft(error));
        identities.push(Object.freeze({ bond_id: candidate["bond_id"] ?? null, evidence_id: candidate["evidence_id"] ?? null, content_sha256: contentSha, ...(candidate["source_entity_id"] === undefined || candidate["source_entity_id"] === null ? {} : { source_entity_id: candidate["source_entity_id"] }) }));
    }
    const payloadItem = Object.freeze({ ...Object.fromEntries(Object.entries(rawItem).filter(([key]) => key !== "component_id")), candidates: Object.freeze(candidates.map(candidate => Object.freeze(Object.fromEntries(Object.entries(candidate as JsonRecord).filter(([key]) => key !== "source_entity_id"))))) });
    const item = yield* normalizeNativeProm9F1PayloadItem(payloadItem).pipe(Either.mapLeft(error));
    const universeSha = yield* canonicalNativeProm9Sha256(identities).pipe(Either.mapLeft(error));
    if (!record(registry) || !exact(registry, ["schema_version", "protocol_sha256", "functions", "registry_sha256"]) || registry["schema_version"] !== "hswm-prom9-function-registry/v1" || !Array.isArray(registry["functions"]) || registry["functions"].length !== 3)
        return yield* fail("invalid registry");
    const functions = registry["functions"];
    if (new Set(functions.map(fn => record(fn) ? fn["function_id"] : null)).size !== 3)
        return yield* fail("registry must contain exactly three unique functions");
    for (const fn of functions) {
        if (!record(fn) || typeof fn["prompt"] !== "string" || fn["prompt_sha256"] !== (yield* canonicalNativeProm9Sha256({ prompt: fn["prompt"] }).pipe(Either.mapLeft(error))))
            return yield* fail("registry prompt hash drifted");
    }
    const registryUnsigned = Object.fromEntries(Object.entries(registry).filter(([key]) => key !== "registry_sha256"));
    if (registry["registry_sha256"] !== (yield* canonicalNativeProm9Sha256(registryUnsigned).pipe(Either.mapLeft(error))))
        return yield* fail("registry hash drifted");
    const find = (id: string): JsonRecord | undefined => functions.find((fn): fn is JsonRecord => record(fn) && fn["function_id"] === id);
    const qf = find("QF_QUERY_COMPILER"), bf = find("BF_BOND_PROPOSER"), af = find("AF_ANSWER_SYNTHESIZER");
    if (qf === undefined || bf === undefined || af === undefined)
        return yield* fail("required network function is absent");
    if (!record(envelope) || !exact(envelope, ["input_caps", "output_caps", "filler_field", "filler_unit", "max_filler_chars"]))
        return yield* fail("invalid call envelope");
    const inputs = envelope["input_caps"], outputs = envelope["output_caps"], maxChars = safeCount(envelope["max_filler_chars"]), fillerField = envelope["filler_field"], unit = envelope["filler_unit"];
    if (!Array.isArray(inputs) || inputs.length !== 3 || !Array.isArray(outputs) || outputs.length !== 3 || [...inputs, ...outputs].some(value => (safeCount(value) ?? 0) < 1) || maxChars === undefined || typeof fillerField !== "string" || typeof unit !== "string" || unit === "")
        return yield* fail("invalid call envelope bounds");
    const requestId = requestIdProfile === "CURRENT_8_HEX" ? yield* nativeProm9F1RequestId(runId, armId, item.itemId).pipe(Either.mapLeft(error)) : `req-${(yield* canonicalNativeProm9Sha256({ run_id: runId, arm_id: armId, item_id: item.itemId }).pipe(Either.mapLeft(error))).slice(0, 20)}`;
    const requestFor = (fn: JsonRecord, payload: TaskJson, index: number): Either.Either<JsonRecord, NativeProm9CallError> => Either.gen(function* () {
        const fitted = yield* fitNativeProm9ParityFiller(meter, fn["prompt"], payload, fillerField, safeCount(inputs[index - 1]), unit, maxChars).pipe(Either.mapLeft(error));
        const request = copy({ run_id: runId, arm_id: armId, item_id: item.itemId, call_index: index, function: fn, input_payload: fitted, max_output_tokens: outputs[index - 1]! });
        yield* prepareNativeProm9Call(request);
        return request;
    });
    const checkRequest = (call: NativeProm9CompletedCall, role: string): Either.Either<void, NativeProm9CallError> => typeof call.output["request_id"] === "string" && nativeProm9RequestIdMatches(call.output["request_id"], requestId) ? Either.right(undefined) : fail(`${role} changed request_id`);
    const query = yield* nativeProm9F1QueryEnvelopePayload(payloadItem, requestId).pipe(Either.mapLeft(error));
    const qfRequest = yield* requestFor(qf, query, 1);
    return Object.freeze({ request: qfRequest, advance: (observed1: NativeProm9CompletedCall) => Either.gen(function* () {
            const call1 = yield* captureCompletion(qfRequest, observed1);
            yield* checkRequest(call1, "QF");
            const scoring = yield* nativeProm9F1BondScoringPayload(payloadItem, armId, requestId, call1.output).pipe(Either.mapLeft(error));
            const bfRequest = yield* requestFor(bf, scoring, 2);
            return Object.freeze({ request: bfRequest, advance: (observed2: NativeProm9CompletedCall) => Either.gen(function* () {
                    const call2 = yield* captureCompletion(bfRequest, observed2);
                    yield* checkRequest(call2, "BF");
                    const proposal = call2.output, ordered = proposal["ordered_bond_ids"], refs = proposal["evidence_refs"];
                    if (!Array.isArray(ordered) || !Array.isArray(refs))
                        return yield* fail("invalid BF proposal");
                    if (ordered.some(bond => !item.candidates.some(candidate => candidate.bondId === bond)))
                        return yield* fail("BF selected a bond outside the supplied universe");
                    if (BigInt(ordered.length) > item.maxEvidenceItems)
                        return yield* fail("BF exceeded the evidence-count budget");
                    const selected = proposal["abstain"] ? [] : ordered.map(bond => item.candidates.find(candidate => candidate.bondId === bond)!);
                    const selectedIds = new Set(selected.map(candidate => candidate.evidenceId));
                    if (refs.some(ref => typeof ref !== "string" || !selectedIds.has(ref)))
                        return yield* fail("BF cited evidence outside its selected bonds");
                    const context = yield* nativeProm9F1AnswerContextPayload(payloadItem, requestId, call1.output, selected.map(candidate => Object.freeze({ evidence_id: candidate.evidenceId, content: candidate.content }))).pipe(Either.mapLeft(error));
                    const afRequest = yield* requestFor(af, context, 3);
                    return Object.freeze({ request: afRequest, advance: (observed3: NativeProm9CompletedCall) => Either.gen(function* () {
                            const call3 = yield* captureCompletion(afRequest, observed3);
                            yield* checkRequest(call3, "AF");
                            const citations = call3.output["supporting_evidence_ids"];
                            if (!Array.isArray(citations) || citations.some(id => typeof id !== "string" || !selectedIds.has(id)))
                                return yield* fail("AF cited evidence outside the frozen selection");
                            const calls = Object.freeze([call1.receipt, call2.receipt, call3.receipt]);
                            const total = (key: string) => calls.reduce((sum, receipt) => sum + integer(receipt[key])!, 0n);
                            if (total("input_tokens") > item.maxInputTokens)
                                return yield* fail("run exceeded the registered total input-token cap");
                            const unsigned = copy({ schema_version: "hswm-prom9-f1-item-run/v1", run_id: runId, arm_id: armId, item_id: item.itemId, registry_sha256: registry["registry_sha256"]!, candidate_universe_sha256: universeSha, calls, answer: call3.output, selected_bond_ids: selected.map(candidate => candidate.bondId), total_input_tokens: total("input_tokens"), total_output_tokens: total("output_tokens"), total_allowed_output_tokens: outputs.reduce<bigint>((sum, value) => sum + integer(value)!, 0n), persistent_state_bytes: stateBytes });
                            const digest = yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(error));
                            return copy({ ...unsigned, run_receipt_sha256: digest });
                        }) });
                }) });
        }) });
});
