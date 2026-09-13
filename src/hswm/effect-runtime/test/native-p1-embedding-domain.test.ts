import { readFileSync } from "node:fs";
import { Either } from "effect";
import { expect, it } from "vitest";
import { conformNativeP1BertEncoding, NATIVE_P1_EMBEDDING_PROFILE } from "../src/native-p1-embedding-domain.js";
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/p1_native_embedding_v1/source_cpu_token_vector_fixture.json", import.meta.url), "utf8")) as {
    readonly attention_mask: readonly (readonly number[])[];
    readonly input_ids: readonly (readonly number[])[];
    readonly token_type_ids: readonly (readonly number[])[];
};
it("restores the Python terminal SEP contract at the bounded 256-token edge", () => {
    const source = fixture.input_ids[3]!;
    const transformersJsObserved = Object.freeze([...source.slice(0, -1), 19204]);
    const result = conformNativeP1BertEncoding({ attentionMask: fixture.attention_mask[3], inputIds: transformersJsObserved, tokenTypeIds: fixture.token_type_ids[3] });
    expect(Either.isRight(result)).toBe(true);
    if (Either.isLeft(result))
        return;
    const corrected = result.right;
    expect(corrected.inputIds).toEqual(source);
    expect(corrected.inputIds).toHaveLength(NATIVE_P1_EMBEDDING_PROFILE.maxSequenceLength);
});
it("rejects sparse, malformed, and non-BERT rows through a typed error", () => {
    expect(Either.isLeft(conformNativeP1BertEncoding({ attentionMask: [1, 1], inputIds: [101, 102], tokenTypeIds: [0, 1] }))).toBe(true);
    expect(Either.isLeft(conformNativeP1BertEncoding({ attentionMask: [1, 1], inputIds: [101, 102], tokenTypeIds: [0, ,] }))).toBe(true);
    expect(Either.isLeft(conformNativeP1BertEncoding({ attentionMask: [1, 1, 0], inputIds: [101, 19204, 0], tokenTypeIds: [0, 0, 0] }))).toBe(true);
    expect(Either.isLeft(conformNativeP1BertEncoding({ attentionMask: [1, 1], inputIds: [101, NATIVE_P1_EMBEDDING_PROFILE.vocabularySize], tokenTypeIds: [0, 0] }))).toBe(true);
});
it("refuses accessor-backed rows without invoking the getter", () => {
    let reads = 0;
    const row = Object.defineProperty({ attentionMask: [1, 1], tokenTypeIds: [0, 0] }, "inputIds", { enumerable: true, get: () => { reads += 1; return [101, 102]; } });
    expect(Either.isLeft(conformNativeP1BertEncoding(row))).toBe(true);
    expect(reads).toBe(0);
});
