/** Source-bound P1 BERT input contract for the locally exported MiniLM graph. */
import { Context, Data, Either } from "effect";
export const NATIVE_P1_EMBEDDING_PROFILE = Object.freeze({
    clsTokenId: 101,
    maxSequenceLength: 256,
    padTokenId: 0,
    sepTokenId: 102,
    vocabularySize: 30522,
    vectorDimension: 384,
});
export class NativeP1EmbeddingError extends Data.TaggedError("NativeP1EmbeddingError")<{
    readonly detail: string;
    readonly reason: "ENCODING_INVALID" | "MODEL_FAILURE" | "VECTOR_INVALID";
}> {
}
const failure = (reason: NativeP1EmbeddingError["reason"], detail: string): Either.Either<never, NativeP1EmbeddingError> => Either.left(new NativeP1EmbeddingError({ detail, reason }));
const data = (value: object, key: string): unknown | undefined => { const d = Object.getOwnPropertyDescriptor(value, key); return d !== undefined && Object.hasOwn(d, "value") ? d.value : undefined; };
const denseNumbers = (value: unknown): value is readonly number[] => Array.isArray(value) && Array.from({ length: value.length }, (_, index) => { const entry = data(value, String(index)); return typeof entry === "number" && Number.isSafeInteger(entry); }).every(Boolean);
export interface NativeP1BertEncoding {
    readonly attentionMask: readonly number[];
    readonly inputIds: readonly number[];
    readonly tokenTypeIds: readonly number[];
}
/**
 * Corrects the observed Transformers.js 4.2.0 full-window truncation behavior:
 * its tokenizer retains a 255th content token where the source Python BERT
 * tokenizer retains SEP. The row must otherwise already be a padded BERT row.
 */
export const conformNativeP1BertEncoding = (value: unknown): Either.Either<NativeP1BertEncoding, NativeP1EmbeddingError> => {
    if (value === null || typeof value !== "object")
        return failure("ENCODING_INVALID", "BERT encoding must be an object");
    const inputIds = data(value, "inputIds"), attentionMask = data(value, "attentionMask"), tokenTypeIds = data(value, "tokenTypeIds");
    if (!denseNumbers(inputIds) || !denseNumbers(attentionMask) || !denseNumbers(tokenTypeIds))
        return failure("ENCODING_INVALID", "BERT encoding arrays must be dense integer arrays");
    if (inputIds.length === 0 || inputIds.length > NATIVE_P1_EMBEDDING_PROFILE.maxSequenceLength || attentionMask.length !== inputIds.length || tokenTypeIds.length !== inputIds.length)
        return failure("ENCODING_INVALID", "BERT encoding lengths drift from the bounded profile");
    const visible = attentionMask.reduce((count, entry, index) => entry === 1 && index === count ? count + 1 : count, 0);
    if (visible < 2 || attentionMask.some((entry, index) => entry !== (index < visible ? 1 : 0)) || tokenTypeIds.some(entry => entry !== 0) || inputIds.some(entry => entry < 0 || entry >= NATIVE_P1_EMBEDDING_PROFILE.vocabularySize) || inputIds[0] !== NATIVE_P1_EMBEDDING_PROFILE.clsTokenId || inputIds.slice(visible).some(entry => entry !== NATIVE_P1_EMBEDDING_PROFILE.padTokenId))
        return failure("ENCODING_INVALID", "BERT special-token, vocabulary, mask, or padding invariants are invalid");
    if (visible < NATIVE_P1_EMBEDDING_PROFILE.maxSequenceLength && inputIds[visible - 1] !== NATIVE_P1_EMBEDDING_PROFILE.sepTokenId)
        return failure("ENCODING_INVALID", "short BERT row is missing terminal SEP");
    const corrected = Object.freeze(inputIds.map((entry, index) => visible === NATIVE_P1_EMBEDDING_PROFILE.maxSequenceLength && index === visible - 1 ? NATIVE_P1_EMBEDDING_PROFILE.sepTokenId : entry));
    return Either.right(Object.freeze({ attentionMask: Object.freeze([...attentionMask]), inputIds: corrected, tokenTypeIds: Object.freeze([...tokenTypeIds]) }));
};
export interface NativeP1EmbeddingBackend {
    readonly embedEncoded: (encoding: NativeP1BertEncoding) => Either.Either<readonly number[], NativeP1EmbeddingError>;
}
export const conformNativeP1BertBatch = (inputIds: unknown, attentionMasks: unknown, tokenTypeIds: unknown): Either.Either<readonly NativeP1BertEncoding[], NativeP1EmbeddingError> => {
    if (!Array.isArray(inputIds) || !Array.isArray(attentionMasks) || !Array.isArray(tokenTypeIds) || inputIds.length === 0 || inputIds.length !== attentionMasks.length || inputIds.length !== tokenTypeIds.length)
        return failure("ENCODING_INVALID", "BERT batch rows are invalid");
    const rows: NativeP1BertEncoding[] = [];
    for (let index = 0; index < inputIds.length; index += 1) {
        const row = conformNativeP1BertEncoding({ attentionMask: attentionMasks[index], inputIds: inputIds[index], tokenTypeIds: tokenTypeIds[index] });
        if (Either.isLeft(row))
            return Either.left(row.left);
        rows.push(row.right);
    }
    return Either.right(Object.freeze(rows));
};
export const poolNativeP1F32 = (hidden: unknown, encodings: readonly NativeP1BertEncoding[]): Either.Either<readonly (readonly number[])[], NativeP1EmbeddingError> => {
    if (!(hidden instanceof Float32Array) || encodings.length === 0)
        return failure("VECTOR_INVALID", "P1 hidden-state output is invalid");
    const width = encodings[0]!.inputIds.length;
    if (encodings.some(row => row.inputIds.length !== width) || hidden.length !== encodings.length * width * NATIVE_P1_EMBEDDING_PROFILE.vectorDimension)
        return failure("VECTOR_INVALID", "P1 hidden-state shape drift");
    const output: (readonly number[])[] = [];
    for (let batch = 0; batch < encodings.length; batch += 1) {
        const mask = encodings[batch]!.attentionMask, count = mask.reduce((sum, value) => sum + value, 0), mean = Array.from({ length: NATIVE_P1_EMBEDDING_PROFILE.vectorDimension }, (_, column) => Math.fround(mask.reduce((sum, value, token) => sum + hidden[(batch * width * NATIVE_P1_EMBEDDING_PROFILE.vectorDimension) + token * NATIVE_P1_EMBEDDING_PROFILE.vectorDimension + column]! * value, 0) / count)), norm = Math.sqrt(mean.reduce((sum, value) => sum + value * value, 0));
        if (!Number.isFinite(norm) || norm <= 0)
            return failure("VECTOR_INVALID", "P1 vector norm is invalid");
        const vector = Object.freeze(mean.map(value => Math.fround(value / norm)));
        if (vector.some(value => !Number.isFinite(value)))
            return failure("VECTOR_INVALID", "P1 vector contains a non-finite value");
        output.push(vector);
    }
    return Either.right(Object.freeze(output));
};
export class NativeP1EmbeddingBackendService extends Context.Tag("NativeP1EmbeddingBackendService")<NativeP1EmbeddingBackendService, NativeP1EmbeddingBackend>() {
}
