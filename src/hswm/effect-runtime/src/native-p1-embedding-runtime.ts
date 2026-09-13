/** Scoped local-only Transformers.js inference, with unknown vendor values
 * validated at the boundary. The pinned SDK's declarations are incompatible
 * with strict NodeNext; dynamic loading does not weaken application checks.
 */
import { Data, Effect, Either } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { captureNativeP1ArtifactSnapshot } from "./native-p1-artifact-snapshot-runtime.js";
import { conformNativeP1BertBatch, poolNativeP1F32 } from "./native-p1-embedding-domain.js";
export class NativeP1EmbeddingRuntimeError extends Data.TaggedError("NativeP1EmbeddingRuntimeError")<{
    readonly detail: string;
    readonly reason: "ARTIFACT_INVALID" | "BACKEND_FAILURE" | "INPUT_INVALID";
}> {
}
const fail = (reason: NativeP1EmbeddingRuntimeError["reason"], detail: string) => new NativeP1EmbeddingRuntimeError({ reason, detail });
const message = (error: unknown): string => error instanceof Error ? error.message : "local P1 vendor operation failed";
export const NATIVE_P1_ONNX_ARTIFACTS = Object.freeze({
    "config.json": "4e1ca650eedb9f844c7124385f7f65e909bfb2c501aad513288b43286753daea",
    "onnx/model.onnx": "ea6b0527a417daa76f86e4d8a4c3bea8e0b33ae86fcca69609992d59108d7185",
    "special_tokens_map.json": "5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a",
    "tokenizer.json": "da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0",
    "tokenizer_config.json": "ccb4eb21a03e1442ee5c3f85431b9c307960a04579942537d74778dc8080a48c",
    "vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"
});
export const NATIVE_P1_EMBEDDING_BACKEND_PROVENANCE = Object.freeze({
    schema_version: "hswm-p1-native-embedding-backend/v1",
    transformers_js: "4.2.0", onnxruntime_node: "1.24.3",
    source_model_revision: "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    source_weights_sha256: "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db",
    artifacts: NATIVE_P1_ONNX_ARTIFACTS, device: "cpu", model_dtype: "fp32", vector_dtype: "float32_promoted_to_float64",
    batch_size: 64, maximum_sequence_length: 256, intra_op_threads: 2, inter_op_threads: 1,
    pooling: "MASKED_MEAN_F64_SUM_F32_MEAN_L2_F64_NORM_F32_VECTOR",
    truncation: "BERT_FULL_256_WINDOW_TERMINAL_SEP_CORRECTION",
    claim_ceiling: "PINNED_NATIVE_BACKEND_NOT_HISTORICAL_VECTOR_BYTE_IDENTITY"
});
type VendorFunction = (...args: readonly unknown[]) => unknown;
const callable = (value: unknown): value is VendorFunction => typeof value === "function";
const bag = (value: unknown): value is Record<string, unknown> => value !== null && (typeof value === "object" || typeof value === "function");
const field = (value: unknown, name: string): unknown => bag(value) ? value[name] : undefined;
const method = (value: unknown, name: string): Effect.Effect<VendorFunction, NativeP1EmbeddingRuntimeError> => {
    const member = field(value, name);
    return callable(member) ? Effect.succeed(member) : Effect.fail(fail("BACKEND_FAILURE", `P1 vendor method missing: ${name}`));
};
const invoke = (fn: VendorFunction, receiver: unknown, args: readonly unknown[]): Effect.Effect<unknown, NativeP1EmbeddingRuntimeError> => Effect.tryPromise({
    try: (): Promise<unknown> => Promise.resolve().then((): unknown => Reflect.apply(fn, receiver, args)), catch: error => fail("BACKEND_FAILURE", message(error))
});
const lift = <A>(value: Either.Either<A, {
    readonly detail: string;
}>): Effect.Effect<A, NativeP1EmbeddingRuntimeError> => Either.isLeft(value) ? Effect.fail(fail("INPUT_INVALID", value.left.detail)) : Effect.succeed(value.right);
const integerRows = (value: unknown): Either.Either<readonly (readonly number[])[], NativeP1EmbeddingRuntimeError> => {
    if (!Array.isArray(value))
        return Either.left(fail("BACKEND_FAILURE", "tokenizer did not return rows"));
    const output: (readonly number[])[] = [];
    for (const row of value) {
        if (!Array.isArray(row))
            return Either.left(fail("BACKEND_FAILURE", "tokenizer row is not an array"));
        const numbers: number[] = [];
        for (const number of row) {
            if ((typeof number !== "bigint" && typeof number !== "number") || !Number.isSafeInteger(Number(number)))
                return Either.left(fail("BACKEND_FAILURE", "tokenizer row is not exact integers"));
            numbers.push(Number(number));
        }
        output.push(Object.freeze(numbers));
    }
    return Either.right(Object.freeze(output));
};
const tokenRows = (encoded: unknown, key: string) => Effect.gen(function* () {
    const tensor = field(encoded, key), tolist = yield* method(tensor, "tolist");
    return yield* lift(integerRows(yield* invoke(tolist, tensor, [])));
});
// A variable specifier deliberately keeps the vendor module's incompatible
// declarations outside this typed application boundary; all outputs are unknown.
const vendorPackage: string = "@huggingface/transformers";
export const embedNativeP1Texts = (artifactDirectory: string, texts: readonly string[]): Effect.Effect<readonly (readonly number[])[], NativeP1EmbeddingRuntimeError, PosixFileSystem> => Effect.scoped(Effect.gen(function* () {
    if (!Array.isArray(texts) || !Object.isFrozen(texts) || texts.length === 0 || Reflect.ownKeys(texts).length !== texts.length + 1)
        return yield* Effect.fail(fail("INPUT_INVALID", "P1 inputs must be a frozen dense non-empty text array"));
    for (let i = 0; i < texts.length; i += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(texts, i);
        if (descriptor === undefined || !Object.hasOwn(descriptor, "value") || typeof descriptor.value !== "string")
            return yield* Effect.fail(fail("INPUT_INVALID", "P1 inputs must contain text data without accessors"));
    }
    const snapshot = yield* captureNativeP1ArtifactSnapshot(artifactDirectory, NATIVE_P1_ONNX_ARTIFACTS).pipe(Effect.mapError(error => fail("ARTIFACT_INVALID", error.detail)));
    const vendor: unknown = yield* Effect.tryPromise({ try: (): Promise<unknown> => import(vendorPackage), catch: error => fail("BACKEND_FAILURE", message(error)) });
    const env = field(vendor, "env"), tokenizerFactory = field(vendor, "AutoTokenizer"), modelFactory = field(vendor, "AutoModel"), Tensor = field(vendor, "Tensor");
    if (!bag(env) || !callable(Tensor))
        return yield* Effect.fail(fail("BACKEND_FAILURE", "P1 vendor module shape drifted"));
    env["allowLocalModels"] = true;
    env["allowRemoteModels"] = false;
    env["localModelPath"] = "";
    const makeTokenizer = yield* method(tokenizerFactory, "from_pretrained"), makeModel = yield* method(modelFactory, "from_pretrained");
    const tokenizer = yield* invoke(makeTokenizer, tokenizerFactory, [snapshot.directory, { local_files_only: true }]);
    if (!callable(tokenizer))
        return yield* Effect.fail(fail("BACKEND_FAILURE", "P1 tokenizer is not callable"));
    const model = yield* Effect.acquireRelease(invoke(makeModel, modelFactory, [snapshot.directory, { device: "cpu", dtype: "fp32", local_files_only: true, session_options: { intraOpNumThreads: 2, interOpNumThreads: 1 } }]), loaded => method(loaded, "dispose").pipe(Effect.flatMap(dispose => invoke(dispose, loaded, [])), Effect.asVoid, Effect.orDie));
    if (!callable(model))
        return yield* Effect.fail(fail("BACKEND_FAILURE", "P1 model is not callable"));
    const output: (readonly number[])[] = [];
    for (let start = 0; start < texts.length; start += 64) {
        const encoded = yield* invoke(tokenizer, undefined, [texts.slice(start, start + 64), { max_length: 256, padding: true, truncation: true }]);
        const ids = yield* tokenRows(encoded, "input_ids"), masks = yield* tokenRows(encoded, "attention_mask"), types = yield* tokenRows(encoded, "token_type_ids");
        const conformed = yield* lift(conformNativeP1BertBatch(ids, masks, types));
        if (conformed.length !== Math.min(64, texts.length - start))
            return yield* Effect.fail(fail("BACKEND_FAILURE", "P1 tokenizer batch size drifted"));
        const width = conformed[0]!.inputIds.length;
        const make = (key: "inputIds" | "attentionMask" | "tokenTypeIds"): Effect.Effect<unknown, NativeP1EmbeddingRuntimeError> => Effect.try({
            try: (): unknown => Reflect.construct(Tensor, ["int64", BigInt64Array.from(conformed.flatMap(row => row[key]), BigInt), [conformed.length, width]]),
            catch: error => fail("BACKEND_FAILURE", message(error))
        });
        const input_ids = yield* make("inputIds"), attention_mask = yield* make("attentionMask"), token_type_ids = yield* make("tokenTypeIds");
        const result = yield* invoke(model, undefined, [{ input_ids, attention_mask, token_type_ids }]);
        const hidden = field(result, "last_hidden_state"), dims = field(hidden, "dims");
        if (!Array.isArray(dims) || dims.length !== 3 || dims[0] !== conformed.length || dims[1] !== width || dims[2] !== 384)
            return yield* Effect.fail(fail("BACKEND_FAILURE", "P1 hidden-state dimensions drifted"));
        output.push(...yield* lift(poolNativeP1F32(field(hidden, "data"), conformed)));
    }
    return Object.freeze(output);
}));
