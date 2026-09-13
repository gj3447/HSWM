/** Pure F1 natural-prompt feasibility projection; meter and registries are injected. */
import { Data, Either } from "effect";
import { NATIVE_PROM9_F1_PAYLOAD_ARMS, nativeProm9F1AnswerContextPayload, nativeProm9F1BondScoringPayload, nativeProm9F1QueryEnvelopePayload, nativeProm9F1RequestId, normalizeNativeProm9F1PayloadItem, } from "./native-prom9-f1-payload-domain.js";
import { renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { type NativeProm9TokenMeter } from "./native-prom9-token-meter-domain.js";
export class NativeProm9F1EnvelopeProjectionError extends Data.TaggedError("NativeProm9F1EnvelopeProjectionError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9F1EnvelopeProjectionError> => Either.left(new NativeProm9F1EnvelopeProjectionError({ detail }));
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128 || value === null || typeof value !== "object")
            return depth <= 128;
        const descriptors = Object.getOwnPropertyDescriptors(value);
        return Reflect.ownKeys(descriptors).every((key) => {
            const descriptor = Reflect.get(descriptors, key) as PropertyDescriptor;
            return Object.hasOwn(descriptor, "value") && dataOnly(descriptor.value, depth + 1);
        });
    }
    catch {
        return false;
    }
};
const record = (value: unknown): value is Readonly<Record<string, TaskJson>> => dataOnly(value) && validNativeTaskJson(value) && taskJsonRecord(value);
const integer = (value: unknown): bigint | undefined => typeof value === "bigint" && value >= 0n ? value : typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? BigInt(value) : undefined;
const tokenCount = (value: number): Either.Either<number, NativeProm9F1EnvelopeProjectionError> => Number.isSafeInteger(value) && value >= 0 ? Either.right(value) : fail("token meter returned an invalid count");
const prompt = (registries: Readonly<Record<string, TaskJson>>, arm: string, id: string): string | undefined => {
    const registry = registries[arm];
    if (!record(registry) || !Array.isArray(registry["functions"]))
        return undefined;
    const found = registry["functions"].find((value) => record(value) && value["function_id"] === id);
    return record(found) && typeof found["prompt"] === "string" ? found["prompt"] : undefined;
};
const plan = (requestId: string): TaskJson => Object.freeze({ request_id: requestId, objectives: Object.freeze([]), required_evidence_types: Object.freeze([]), constraints: Object.freeze([]), abstain: true });
/** Mirrors original `project_item_call_upper_bounds` after validated inputs are supplied. */
export const projectNativeProm9F1Envelope = (runId: unknown, rawItems: unknown, registries: unknown, meter: NativeProm9TokenMeter, projectedOutputs: unknown, slack: unknown, inputCaps: unknown): Either.Either<TaskJson, NativeProm9F1EnvelopeProjectionError> => Either.gen(function* () {
    const slackValue = integer(slack);
    if (typeof runId !== "string" || !dataOnly(rawItems) || !Array.isArray(rawItems) || rawItems.length === 0 || !record(registries) || !record(projectedOutputs) || !record(inputCaps) || slackValue === undefined)
        return yield* fail("projection inputs are invalid");
    const items = snapshotNativeTaskJson(rawItems);
    const registrySnapshot = snapshotNativeTaskJson(registries);
    const outputSnapshot = snapshotNativeTaskJson(projectedOutputs);
    const inputSnapshot = snapshotNativeTaskJson(inputCaps);
    if (!Array.isArray(items) || !record(registrySnapshot) || !record(outputSnapshot) || !record(inputSnapshot))
        return yield* fail("projection inputs are invalid");
    const inputOne = integer(inputSnapshot["1"]), inputTwo = integer(inputSnapshot["2"]), inputThree = integer(inputSnapshot["3"]);
    if (inputOne === undefined || inputTwo === undefined || inputThree === undefined || inputOne < 1n || inputTwo < 1n || inputThree < 1n)
        return yield* fail("input caps are invalid");
    const totalInputCaps = inputOne + inputTwo + inputThree;
    const rows: TaskJson[] = [];
    for (const rawItem of items) {
        const item = yield* normalizeNativeProm9F1PayloadItem(rawItem).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })));
        const rawItemRecord = record(rawItem) ? rawItem : undefined;
        if (rawItemRecord === undefined)
            return yield* fail("projection item is invalid");
        const candidates = rawItemRecord["candidates"];
        if (!Array.isArray(candidates))
            return yield* fail("projection candidates are invalid");
        const ranked: {
            readonly candidate: TaskJson;
            readonly tokens: number;
        }[] = [];
        for (const candidate of candidates) {
            if (!record(candidate) || typeof candidate["content"] !== "string")
                return yield* fail("projection candidate is invalid");
            const tokens = yield* meter.countText(candidate["content"]).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })), Either.flatMap(tokenCount));
            ranked.push(Object.freeze({ candidate, tokens }));
        }
        const ordered = [...ranked].sort((left, right) => right.tokens - left.tokens).slice(0, Number(item.maxEvidenceItems)).map((value) => value.candidate);
        const perArm: Record<string, TaskJson> = {};
        for (const arm of NATIVE_PROM9_F1_PAYLOAD_ARMS) {
            const projection = outputSnapshot[arm];
            const planTokens = record(projection) ? integer(projection["1"]) : undefined;
            if (planTokens === undefined)
                return yield* fail("projected outputs are invalid");
            const request = yield* nativeProm9F1RequestId(runId, arm, item.itemId).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })));
            const query = yield* nativeProm9F1QueryEnvelopePayload(rawItemRecord, request).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })));
            const bond = yield* nativeProm9F1BondScoringPayload(rawItemRecord, arm, request, plan(request)).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })));
            const answer = yield* nativeProm9F1AnswerContextPayload(rawItemRecord, request, plan(request), ordered).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })));
            const queryPrompt = prompt(registrySnapshot, arm, "QF_QUERY_COMPILER"), bondPrompt = prompt(registrySnapshot, arm, "BF_BOND_PROPOSER"), answerPrompt = prompt(registrySnapshot, arm, "AF_ANSWER_SYNTHESIZER");
            if (queryPrompt === undefined || bondPrompt === undefined || answerPrompt === undefined)
                return yield* fail("registry prompt is invalid");
            const one = yield* meter.countChatPrompt(queryPrompt, renderNativeTaskJson(query)).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })), Either.flatMap(tokenCount));
            const twoPrompt = yield* meter.countChatPrompt(bondPrompt, renderNativeTaskJson(bond)).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })), Either.flatMap(tokenCount));
            const threePrompt = yield* meter.countChatPrompt(answerPrompt, renderNativeTaskJson(answer)).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })), Either.flatMap(tokenCount));
            perArm[arm] = Object.freeze([BigInt(one), BigInt(twoPrompt) + planTokens + slackValue, BigInt(threePrompt) + planTokens + slackValue]);
        }
        rows.push(Object.freeze({ item_id: item.itemId, projected_upper_bounds: Object.freeze(perArm) }));
    }
    const totals: Record<string, TaskJson> = {};
    for (const arm of NATIVE_PROM9_F1_PAYLOAD_ARMS) {
        const projection = outputSnapshot[arm];
        if (!record(projection))
            return yield* fail("projected outputs are invalid");
        const one = integer(projection["1"]), two = integer(projection["2"]), three = integer(projection["3"]);
        if (one === undefined || two === undefined || three === undefined)
            return yield* fail("projected outputs are invalid");
        totals[arm] = totalInputCaps + one + two + three;
    }
    const values = Object.values(totals).map((value) => value as bigint);
    const spread = values.reduce((left, right) => left > right ? left : right) - values.reduce((left, right) => left < right ? left : right);
    return Object.freeze({ projected_total_tokens_by_arm: Object.freeze(totals), projected_spread: spread, items: Object.freeze(rows) });
});
/** Applies the original envelope's caps and tolerance to a projected cohort. */
export const enforceNativeProm9F1Envelope = (runId: unknown, rawItems: unknown, registries: unknown, meter: NativeProm9TokenMeter, rawEnvelope: unknown, tolerance: unknown): Either.Either<TaskJson, NativeProm9F1EnvelopeProjectionError> => Either.gen(function* () {
    if (!record(rawEnvelope) || !dataOnly(rawItems) || !validNativeTaskJson(rawItems) || !Array.isArray(rawItems) || rawItems.length === 0)
        return yield* fail("token envelope is invalid");
    const envelope = snapshotNativeTaskJson(rawEnvelope) as Readonly<Record<string, TaskJson>>;
    const items = snapshotNativeTaskJson(rawItems) as readonly TaskJson[];
    const inputCaps = envelope["per_call_input_caps"];
    const outputCaps = envelope["per_call_output_caps"];
    const outputs = envelope["projected_output_tokens_by_arm"];
    const slack = envelope["projection_slack_tokens"];
    const toleranceValue = integer(tolerance);
    if (!record(inputCaps) || !record(outputCaps) || toleranceValue === undefined)
        return yield* fail("token envelope is invalid");
    const projection = yield* projectNativeProm9F1Envelope(runId, items, registries, meter, outputs, slack, inputCaps);
    if (!record(projection))
        return yield* fail("projection is invalid");
    const totalInput = integer(inputCaps["1"]);
    const inputTwo = integer(inputCaps["2"]);
    const inputThree = integer(inputCaps["3"]);
    const outputOne = integer(outputCaps["1"]);
    const outputTwo = integer(outputCaps["2"]);
    const outputThree = integer(outputCaps["3"]);
    if (totalInput === undefined || inputTwo === undefined || inputThree === undefined || outputOne === undefined || outputTwo === undefined || outputThree === undefined || totalInput < 1n || inputTwo < 1n || inputThree < 1n || outputOne < 1n || outputTwo < 1n || outputThree < 1n)
        return yield* fail("token envelope caps are invalid");
    const totalInputCaps = totalInput + inputTwo + inputThree;
    const rows = projection["items"];
    if (!Array.isArray(rows))
        return yield* fail("projection is invalid");
    for (let index = 0; index < items.length; index += 1) {
        const item = yield* normalizeNativeProm9F1PayloadItem(items[index]).pipe(Either.mapLeft((error) => new NativeProm9F1EnvelopeProjectionError({ detail: error.detail })));
        if (totalInputCaps > item.maxInputTokens)
            return yield* fail(`item ${item.itemId}: registered input caps exceed the item input budget`);
        if (outputOne > item.maxOutputTokensPerCall || outputTwo > item.maxOutputTokensPerCall || outputThree > item.maxOutputTokensPerCall)
            return yield* fail(`item ${item.itemId}: output cap exceeds the item output budget`);
        const row = rows[index];
        if (!record(row) || !record(row["projected_upper_bounds"]))
            return yield* fail("projection is invalid");
        for (const arm of NATIVE_PROM9_F1_PAYLOAD_ARMS) {
            const bounds = row["projected_upper_bounds"][arm];
            if (!Array.isArray(bounds) || bounds.length !== 3)
                return yield* fail("projection is invalid");
            const caps = [totalInput, inputTwo, inputThree];
            for (let call = 0; call < 3; call += 1) {
                const bound = integer(bounds[call]);
                if (bound === undefined || bound > caps[call]!)
                    return yield* fail(`item ${item.itemId} arm ${arm} call ${call + 1}: projected natural prompt exceeds the registered input cap`);
            }
        }
    }
    const spread = integer(projection["projected_spread"]);
    if (spread === undefined || spread > toleranceValue)
        return yield* fail("declared per-arm output projections exceed the registered tolerance");
    return projection;
});
