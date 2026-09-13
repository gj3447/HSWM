/** Source-matched chat serialization and parity-filler search; no BPE implementation. */
import { Data, Either } from "effect";
import { renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export class NativeProm9TokenMeterError extends Data.TaggedError("NativeProm9TokenMeterError")<{
    readonly detail: string;
}> {
}
export type NativeProm9TokenMeter = Readonly<{
    countText: (text: string) => Either.Either<number, NativeProm9TokenMeterError>;
    countChatPrompt: (systemPrompt: string, userText: string) => Either.Either<number, NativeProm9TokenMeterError>;
}>;
const fail = (detail: string): Either.Either<never, NativeProm9TokenMeterError> => Either.left(new NativeProm9TokenMeterError({ detail }));
const textLength = (value: string): number => Array.from(value).length;
const pythonRound = (value: number): number => { const lower = Math.floor(value), fraction = value - lower; return fraction < 0.5 ? lower : fraction > 0.5 ? lower + 1 : lower % 2 === 0 ? lower : lower + 1; };
const record = (value: unknown): value is Readonly<Record<string, TaskJson>> => validNativeTaskJson(value) && taskJsonRecord(value);
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128)
            return false;
        if (value === null || typeof value !== "object")
            return true;
        return Reflect.ownKeys(Object.getOwnPropertyDescriptors(value)).every(key => { const descriptor = Object.getOwnPropertyDescriptor(value, key); return descriptor !== undefined && descriptor.get === undefined && descriptor.set === undefined && dataOnly(descriptor.value, depth + 1); });
    }
    catch {
        return false;
    }
};
const count = (value: unknown): Either.Either<number, NativeProm9TokenMeterError> => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? Either.right(value) : fail("token meter returned an invalid count");
export const renderNativeProm9QwenChatPrompt = (systemPrompt: unknown, userText: unknown): Either.Either<string, NativeProm9TokenMeterError> => typeof systemPrompt !== "string" || typeof userText !== "string" ? fail("chat prompt parts must be strings") : Either.right(`<|im_start|>system\n${systemPrompt}<|im_end|>\n<|im_start|>user\n${userText}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n`);
export const nativeProm9FakeTokenMeter = (charsPerToken: unknown = 4, chatOverheadTokens: unknown = 11): Either.Either<NativeProm9TokenMeter, NativeProm9TokenMeterError> => {
    if (typeof charsPerToken !== "number" || !Number.isSafeInteger(charsPerToken) || charsPerToken < 1 || typeof chatOverheadTokens !== "number" || !Number.isSafeInteger(chatOverheadTokens) || chatOverheadTokens < 0)
        return fail("fake meter configuration is invalid");
    const countText = (text: string): Either.Either<number, NativeProm9TokenMeterError> => typeof text !== "string" ? fail("count_text requires a string") : Either.right(Math.max(1, Math.ceil(textLength(text) / charsPerToken)));
    return Either.right(Object.freeze({ countText, countChatPrompt: (systemPrompt, userText) => Either.gen(function* () { return chatOverheadTokens + (yield* countText(systemPrompt)) + (yield* countText(userText)); }) }));
};
export const fitNativeProm9ParityFiller = (meter: NativeProm9TokenMeter, systemPrompt: unknown, rawPayload: unknown, fillerField: unknown, cap: unknown, unit: unknown, maxChars: unknown): Either.Either<TaskJson, NativeProm9TokenMeterError> => Either.gen(function* () {
    if (typeof systemPrompt !== "string" || !dataOnly(rawPayload) || !record(rawPayload) || typeof fillerField !== "string" || typeof cap !== "number" || !Number.isSafeInteger(cap) || cap < 1 || typeof unit !== "string" || unit === "" || typeof maxChars !== "number" || !Number.isSafeInteger(maxChars) || maxChars < 0)
        return yield* fail("invalid parity-filler contract");
    const base: Record<string, TaskJson> = { ...rawPayload, [fillerField]: "" };
    const countWith = (chars: number): Either.Either<number, NativeProm9TokenMeterError> => meter.countChatPrompt(systemPrompt, renderNativeTaskJson(Object.freeze({ ...base, [fillerField]: unit.repeat(chars) }))).pipe(Either.flatMap(count));
    const natural = yield* countWith(0);
    if (natural > cap)
        return yield* fail(`natural prompt of ${natural} tokens exceeds the registered envelope cap ${cap}`);
    if (natural === cap)
        return snapshotNativeTaskJson(Object.freeze(base));
    const unitTokens = yield* meter.countText(unit).pipe(Either.flatMap(count)), charsPerToken = Math.max(1, pythonRound(textLength(unit) / Math.max(1, unitTokens))), needed = cap - natural;
    let below: readonly [
        number,
        number
    ] | undefined, above: readonly [
        number,
        number
    ] | undefined, current = Math.min(maxChars, needed * charsPerToken);
    for (let attempt = 0; attempt < 8; attempt++) {
        const total = yield* countWith(current);
        if (total === cap)
            return snapshotNativeTaskJson(Object.freeze({ ...base, [fillerField]: unit.repeat(current) }));
        if (total < cap) {
            below = [current, total];
            current += Math.max(1, (cap - total) * charsPerToken);
            if (current > maxChars)
                break;
        }
        else {
            above = [current, total];
            current -= Math.max(1, (total - cap) * charsPerToken);
            if (current < 0)
                break;
        }
        if (below !== undefined && above !== undefined)
            break;
    }
    const low = below?.[0] ?? 0, high = above?.[0] ?? maxChars;
    for (let chars = low; chars <= high; chars++)
        if ((yield* countWith(chars)) === cap)
            return snapshotNativeTaskJson(Object.freeze({ ...base, [fillerField]: unit.repeat(chars) }));
    return yield* fail("no exact parity-filler fit within the declared character ceiling");
});
