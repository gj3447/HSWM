/** Native verification of the frozen PROM-9 F1 call and item-run receipts. */
import { Data, Either } from "effect";
import { decodeNativeTaskJson, taskJsonRecord, type TaskJson, validNativeTaskJson } from "./native-task-json-domain.js";
import { canonicalNativeProm9Sha256, nativeProm9PortDigest, validateNativeProm9Port, type Prom9PortType } from "./native-prom9-ports-domain.js";
import { pythonJsonEqual, pythonJsonInt } from "./native-python-json-semantics-domain.js";
export const NATIVE_PROM9_CALL_RECEIPT_SCHEMA = "hswm-prom9-call-receipt/v1";
export const NATIVE_PROM9_RUN_SCHEMA = "hswm-prom9-f1-item-run/v1";
export class NativeProm9ReceiptError extends Data.TaggedError("NativeProm9ReceiptError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9ReceiptError> => Either.left(new NativeProm9ReceiptError({ detail }));
const record = (value: unknown): value is Readonly<Record<string, TaskJson>> => validNativeTaskJson(value) && taskJsonRecord(value);
const jsonRecord = (value: unknown, label: string): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9ReceiptError> => record(value) ? Either.right(value) : fail(`${label} must be an object`);
const own = (value: Readonly<Record<string, TaskJson>>, key: string): TaskJson | undefined => Object.hasOwn(value, key) ? value[key] : undefined;
const text = (value: TaskJson | undefined, label: string): Either.Either<string, NativeProm9ReceiptError> => typeof value === "string" ? Either.right(value) : fail(`${label} must be text`);
const port = (value: TaskJson | undefined, label: string): Either.Either<Prom9PortType, NativeProm9ReceiptError> => {
    const names: readonly Prom9PortType[] = ["QueryEnvelopeV1", "QueryPlanV1", "BondScoringEnvelopeV1", "BondProposalV1", "AnswerContextV1", "AnswerEnvelopeV1"];
    return typeof value === "string" && names.includes(value as Prom9PortType) ? Either.right(value as Prom9PortType) : fail(`${label} is not a PROM-9 port type`);
};
const digest = (portType: Prom9PortType, payload: TaskJson | undefined, label: string) => nativeProm9PortDigest(portType, payload).pipe(Either.mapLeft(() => new NativeProm9ReceiptError({ detail: `${label} is invalid` })));
export const verifyNativeProm9CallReceipt = (value: unknown): Either.Either<string, NativeProm9ReceiptError> => Either.gen(function* () {
    const data = yield* jsonRecord(value, "call receipt");
    if (own(data, "schema_version") !== NATIVE_PROM9_CALL_RECEIPT_SCHEMA)
        return yield* fail("unsupported call receipt schema");
    const declared = yield* text(own(data, "receipt_sha256"), "receipt_sha256");
    const unsigned = Object.fromEntries(Object.entries(data).filter(([key]) => key !== "receipt_sha256"));
    const actual = yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(() => new NativeProm9ReceiptError({ detail: "call receipt cannot be canonically hashed" })));
    if (actual !== declared)
        return yield* fail("call receipt self-hash drifted");
    const inputType = yield* port(own(data, "input_type"), "input_type");
    const outputType = yield* port(own(data, "output_type"), "output_type");
    const inputDigest = yield* digest(inputType, own(data, "input_payload"), "call receipt input payload");
    const outputDigest = yield* digest(outputType, own(data, "output_payload"), "call receipt output payload");
    if (own(data, "input_port_sha256") !== inputDigest)
        return yield* fail("call receipt input port drifted");
    if (own(data, "output_port_sha256") !== outputDigest)
        return yield* fail("call receipt output port drifted");
    return declared;
});
export const verifyNativeProm9RunReceipt = (value: unknown): Either.Either<string, NativeProm9ReceiptError> => Either.gen(function* () {
    const data = yield* jsonRecord(value, "item run");
    if (own(data, "schema_version") !== NATIVE_PROM9_RUN_SCHEMA)
        return yield* fail("unsupported item-run schema");
    const declared = yield* text(own(data, "run_receipt_sha256"), "run_receipt_sha256");
    const unsigned = Object.fromEntries(Object.entries(data).filter(([key]) => key !== "run_receipt_sha256"));
    const actual = yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(() => new NativeProm9ReceiptError({ detail: "item run cannot be canonically hashed" })));
    if (actual !== declared)
        return yield* fail("item-run receipt self-hash drifted");
    const calls = own(data, "calls");
    if (!Array.isArray(calls) || calls.length !== 3 || !Array.from({ length: calls.length }, (_, index) => Object.hasOwn(calls, index)).every(Boolean))
        return yield* fail("item run must contain exactly three calls");
    const callRecords = yield* Either.all(calls.map((call, index) => jsonRecord(call, `call ${index + 1}`)));
    if (!callRecords.every((call, index) => pythonJsonEqual(own(call, "call_index") ?? null, index + 1)))
        return yield* fail("item call order drifted");
    for (const call of callRecords) {
        yield* verifyNativeProm9CallReceipt(call);
        if (!["run_id", "arm_id", "item_id"].every(key => pythonJsonEqual(own(call, key) ?? null, own(data, key) ?? null)))
            return yield* fail("item-run call identity drifted");
    }
    const answer = yield* validateNativeProm9Port("AnswerEnvelopeV1", own(data, "answer")).pipe(Either.mapLeft(() => new NativeProm9ReceiptError({ detail: "item-run answer is invalid" })));
    const thirdOutput = own(callRecords[2]!, "output_payload");
    if (thirdOutput === undefined || !pythonJsonEqual(answer, thirdOutput))
        return yield* fail("item-run answer differs from the third call output");
    const totals = ["input_tokens", "output_tokens", "allowed_output_tokens"] as const;
    const totalKeys = ["total_input_tokens", "total_output_tokens", "total_allowed_output_tokens"] as const;
    for (let index = 0; index < totals.length; index += 1) {
        const expected = callRecords.reduce<bigint | undefined>((sum, call) => {
            const value = own(call, totals[index]!);
            const next = pythonJsonInt(value === undefined ? -1 : value);
            return sum === undefined || next === undefined ? undefined : sum + next;
        }, 0n);
        const declaredTotal = own(data, totalKeys[index]!);
        if (expected === undefined || declaredTotal === undefined || !pythonJsonEqual(declaredTotal, expected))
            return yield* fail("item-run token totals differ from call receipts");
    }
    return declared;
});
export const verifyNativeProm9CallReceiptJson = (bytes: Uint8Array) => decodeNativeTaskJson(bytes).pipe(Either.mapLeft(() => new NativeProm9ReceiptError({ detail: "call receipt JSON is invalid" })), Either.flatMap(verifyNativeProm9CallReceipt));
export const verifyNativeProm9RunReceiptJson = (bytes: Uint8Array) => decodeNativeTaskJson(bytes).pipe(Either.mapLeft(() => new NativeProm9ReceiptError({ detail: "item-run JSON is invalid" })), Either.flatMap(verifyNativeProm9RunReceipt));
