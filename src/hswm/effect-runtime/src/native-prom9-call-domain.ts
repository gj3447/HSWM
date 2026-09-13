/** Pure call preparation and response/receipt construction for PROM-9.
 * A response receipt is a supplied transport observation, not model efficacy.
 */
import { Data, Either } from "effect";
import { canonicalNativeProm9Sha256, nativeProm9PortDigest, validateNativeProm9Port, type Prom9PortType } from "./native-prom9-ports-domain.js";
import { isTaskNumber, snapshotNativeTaskJson, taskJsonRecord, taskNumberIsFloat, taskNumberValue, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export class NativeProm9CallError extends Data.TaggedError("NativeProm9CallError")<{
    readonly detail: string;
}> {
}
type JsonRecord = Readonly<Record<string, TaskJson>>;
const fail = (detail: string): Either.Either<never, NativeProm9CallError> => Either.left(new NativeProm9CallError({ detail }));
const mapError = (error: {
    readonly detail: string;
}) => new NativeProm9CallError({ detail: error.detail });
const dataOnly = (value: unknown, depth = 0): boolean => {
    try {
        if (depth > 128)
            return false;
        if (value === null || typeof value !== "object")
            return true;
        return Reflect.ownKeys(value).every(key => {
            const descriptor = Object.getOwnPropertyDescriptor(value, key);
            return descriptor !== undefined && Object.hasOwn(descriptor, "value") && dataOnly(descriptor.value, depth + 1);
        });
    }
    catch {
        return false;
    }
};
const record = (value: unknown): value is JsonRecord => dataOnly(value) && validNativeTaskJson(value) && taskJsonRecord(value);
const exact = (value: JsonRecord, keys: readonly string[]): boolean => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const integer = (value: TaskJson | undefined): bigint | undefined => {
    if (value === undefined || !isTaskNumber(value) || taskNumberIsFloat(value))
        return undefined;
    const number = taskNumberValue(value);
    return typeof number === "bigint" ? number : Number.isSafeInteger(number) ? BigInt(number) : undefined;
};
const portTypes: readonly Prom9PortType[] = Object.freeze(["QueryEnvelopeV1", "QueryPlanV1", "BondScoringEnvelopeV1", "BondProposalV1", "AnswerContextV1", "AnswerEnvelopeV1"]);
const portType = (value: TaskJson | undefined): value is Prom9PortType => typeof value === "string" && portTypes.some(port => port === value);
const copyRecord = (value: JsonRecord): JsonRecord => snapshotNativeTaskJson(value) as JsonRecord;
export interface NativeProm9CompletedCall {
    readonly output: JsonRecord;
    readonly receipt: JsonRecord;
}
export interface NativeProm9PreparedCall {
    readonly modelCall: JsonRecord;
    readonly complete: (response: unknown) => Either.Either<NativeProm9CompletedCall, NativeProm9CallError>;
}
/** Strict JSON data boundary. Registry verification belongs to its owner. */
export const prepareNativeProm9Call = (raw: unknown): Either.Either<NativeProm9PreparedCall, NativeProm9CallError> => Either.gen(function* () {
    if (!record(raw) || !exact(raw, ["run_id", "arm_id", "item_id", "call_index", "function", "input_payload", "max_output_tokens"]))
        return yield* fail("invalid function invocation fields");
    const request = copyRecord(raw), spec = request["function"];
    if (!record(spec) || !exact(spec, ["function_id", "model", "model_revision", "input_type", "output_type", "prompt", "prompt_sha256"]) || Object.values(spec).some(value => typeof value !== "string"))
        return yield* fail("invalid captured function specification");
    // The native exported JSON boundary is stricter than the source dataclass call helper.
    if (spec["prompt_sha256"] !== (yield* canonicalNativeProm9Sha256({ prompt: spec["prompt"]! }).pipe(Either.mapLeft(mapError))))
        return yield* fail("function prompt hash drifted");
    if (!["run_id", "arm_id", "item_id"].every(key => typeof request[key] === "string"))
        return yield* fail("call identities must be text");
    const index = integer(request["call_index"]), allowed = integer(request["max_output_tokens"]), inputType = spec["input_type"], outputType = spec["output_type"];
    if (index === undefined || index < 1n || index > 3n)
        return yield* fail("call_index must be 1, 2, or 3");
    if (allowed === undefined || allowed < 1n)
        return yield* fail("max_output_tokens must be positive");
    if (!portType(inputType) || !portType(outputType))
        return yield* fail("unsupported function port");
    const input = yield* validateNativeProm9Port(inputType, request["input_payload"]).pipe(Either.mapLeft(mapError));
    const inputSha = yield* nativeProm9PortDigest(inputType, input).pipe(Either.mapLeft(mapError));
    const identity = Object.freeze({ run_id: request["run_id"]!, arm_id: request["arm_id"]!, item_id: request["item_id"]!, call_index: index, function_id: spec["function_id"]!, registry_prompt_sha256: spec["prompt_sha256"]!, input_port_sha256: inputSha });
    const physicalId = yield* canonicalNativeProm9Sha256(identity).pipe(Either.mapLeft(mapError));
    const modelCall = copyRecord(Object.freeze({ physical_call_id: physicalId, run_id: identity.run_id, arm_id: identity.arm_id, item_id: identity.item_id, call_index: index,
        function_id: identity.function_id, model: spec["model"]!, model_revision: spec["model_revision"]!, system_prompt: spec["prompt"]!, input_type: inputType,
        input_payload: input, output_type: outputType, max_output_tokens: allowed }));
    const complete = (rawResponse: unknown): Either.Either<NativeProm9CompletedCall, NativeProm9CallError> => Either.gen(function* () {
        if (!record(rawResponse) || !["payload", "model", "model_revision", "input_tokens", "output_tokens", "latency_ms"].every(key => Object.hasOwn(rawResponse, key)) || Object.keys(rawResponse).some(key => !["payload", "model", "model_revision", "input_tokens", "output_tokens", "latency_ms", "cache_status", "retries"].includes(key)))
            return yield* fail("model port returned an unsupported response");
        const response = copyRecord(rawResponse);
        if (response["model"] !== spec["model"] || response["model_revision"] !== spec["model_revision"])
            return yield* fail("model identity drifted at the call boundary");
        const output = yield* validateNativeProm9Port(outputType, response["payload"]).pipe(Either.mapLeft(mapError));
        const inputs = integer(response["input_tokens"]), outputs = integer(response["output_tokens"]), latency = integer(response["latency_ms"]), retries = integer(Object.hasOwn(response, "retries") ? response["retries"] : 0);
        if (inputs === undefined || inputs < 0n || outputs === undefined || outputs < 0n || latency === undefined || latency < 0n || retries === undefined || retries < 0n)
            return yield* fail("response usage, latency and retries must be non-negative integers");
        if (outputs > allowed)
            return yield* fail("model exceeded the registered output-token cap");
        const cache = Object.hasOwn(response, "cache_status") ? response["cache_status"] : "miss";
        if (cache !== "miss" && cache !== "hit" && cache !== "provider-unknown")
            return yield* fail("unknown cache status");
        const outputSha = yield* nativeProm9PortDigest(outputType, output).pipe(Either.mapLeft(mapError));
        const unsigned = Object.freeze({ schema_version: "hswm-prom9-call-receipt/v1", physical_call_id: physicalId, run_id: identity.run_id, arm_id: identity.arm_id, item_id: identity.item_id,
            call_index: index, function_id: identity.function_id, model: spec["model"]!, model_revision: spec["model_revision"]!, prompt_sha256: spec["prompt_sha256"]!, input_type: inputType,
            input_port_sha256: inputSha, input_payload: input, output_type: outputType, output_port_sha256: outputSha, output_payload: output, allowed_output_tokens: allowed,
            input_tokens: inputs, output_tokens: outputs, latency_ms: latency, cache_status: cache, retries });
        const digest = yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(mapError));
        return Object.freeze({ output: copyRecord(output), receipt: copyRecord(Object.freeze({ ...unsigned, receipt_sha256: digest })) });
    });
    return Object.freeze({ modelCall, complete });
});
