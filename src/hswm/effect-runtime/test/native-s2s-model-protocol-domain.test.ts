import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { Either } from "effect";
import { expect, it } from "vitest";
import { archiveNativeS2SModel, parseNativeS2SLearnedModelArchive, parseNativeS2SLearnedModelArchiveJson, parseNativeS2SParameterHex, verifyNativeS2SModel } from "../src/native-s2s-model-protocol-domain.js";
import { renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js";
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_learned_model_v1/original.v1.json", import.meta.url), "utf8")) as {
    archives: Readonly<Record<string, Record<string, TaskJson>>>;
    sources: unknown;
    resealed_forged: Readonly<Record<string, {
        archive: unknown;
        source_result: {
            accepted: boolean;
        };
    }>>;
};
const right = <A>(value: Either.Either<A, {
    readonly detail: string;
}>): A => {
    if (Either.isLeft(value))
        return expect.fail(value.left.detail);
    return value.right;
};
it("reconstructs all original archives byte-exactly including actual nonzero best-state losses", () => {
    for (const [name, raw] of Object.entries(fixture.archives)) {
        const model = right(parseNativeS2SLearnedModelArchive(raw));
        expect(renderNativeTaskJson(model.canonical), name).toBe(renderNativeTaskJson(raw));
        expect(model.learned).toBe(name === "T16_nonzero");
        expect(model.learnedStateSha256).toBe(raw["learned_state_sha256"]);
        expect(Object.isFrozen(model.parameters)).toBe(true);
        for (const values of Object.values(model.parameters))
            expect(Object.isFrozen(values)).toBe(true);
    }
}, 60000);
it("replays source refusals for fully resealed archive forgeries", () => {
    for (const [name, row] of Object.entries(fixture.resealed_forged)) {
        expect(row.source_result.accepted, name).toBe(false);
        expect(Either.isLeft(parseNativeS2SLearnedModelArchive(row.archive)), name).toBe(true);
    }
}, 60000);
it("preserves decoder roundtrips and captures parameters before callers can mutate them", () => {
    const raw = fixture.archives["T16_zero"]!, model = right(parseNativeS2SLearnedModelArchiveJson(new TextEncoder().encode(renderNativeTaskJson(raw))));
    const mutable = Object.fromEntries(Object.entries(model.parameters).map(([key, values]) => [key, [...values as readonly number[]]]));
    const rebuilt = right(archiveNativeS2SModel(model.arm, mutable, model.optimization.canonical));
    mutable["outB"]![0] = 999;
    expect(rebuilt.receiptSha256).toBe(model.receiptSha256);
    expect((rebuilt.parameters as {
        readonly outB: readonly number[];
    }).outB[0]).toBe(0);
    expect(Either.isLeft(verifyNativeS2SModel(model.arm, mutable, model.optimization.canonical))).toBe(true);
    let reads = 0;
    const getter = Object.defineProperty({ ...raw }, "tensors", { get: () => { reads++; return raw["tensors"]; } });
    expect(Either.isLeft(parseNativeS2SLearnedModelArchive(getter))).toBe(true);
    expect(reads).toBe(0);
    const badParameters = Object.defineProperty({ ...model.parameters }, "outB", { get: () => { reads++; return []; } });
    expect(Either.isLeft(verifyNativeS2SModel(model.arm, badParameters, model.optimization.canonical))).toBe(true);
    expect(reads).toBe(0);
    expect(Either.isLeft(verifyNativeS2SModel(model.arm, model.parameters, { ...model.optimization, receiptSha256: "0".repeat(64) }))).toBe(true);
}, 60000);
it("preserves signed zero and finite binary64 extremes while refusing alternate hex encodings", () => {
    expect(Object.is(right(parseNativeS2SParameterHex("-0x0.0p+0")), -0)).toBe(true);
    expect(right(parseNativeS2SParameterHex("0x0.0000000000001p-1022"))).toBe(Number.MIN_VALUE);
    expect(right(parseNativeS2SParameterHex("0x1.fffffffffffffp+1023"))).toBe(Number.MAX_VALUE);
    for (const invalid of ["nan", "inf", "0x1.0p+0", "0x1.0000000000000p+00", "0x0.0000000000001p-1021", "0x1.0000000000000p+1024"])
        expect(Either.isLeft(parseNativeS2SParameterHex(invalid))).toBe(true);
    expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_protocol.py", import.meta.url))).digest("hex")).toBe("c0df25e37d0e54c792f0eca9f78d83029e4fedd8f837743096eef2b29a62a2c1");
});
it("rejects altered best losses even after the entire optimization history and receipt are consistently resealed", () => {
    const evidence = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_learned_model_loss_forge_v1/original.v1.json", import.meta.url), "utf8")) as {
        forged_archive: unknown;
        optimization_parse: {
            accepted: boolean;
        };
        learned_archive_parse: {
            accepted: boolean;
        };
    };
    expect(evidence.optimization_parse.accepted).toBe(true);
    expect(evidence.learned_archive_parse.accepted).toBe(false);
    const result = parseNativeS2SLearnedModelArchive(evidence.forged_archive);
    expect(Either.isLeft(result)).toBe(true);
    if (Either.isLeft(result))
        expect(result.left.detail).toBe("learned best-state losses disagree with bound task and parameters");
}, 30000);
