import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Either } from "effect";
import { expect, it } from "vitest";
import { buildNativeProm9F1Registry } from "../src/native-prom9-f1-registry-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord } from "../src/native-task-json-domain.js";
const decode = (path: string) => Either.getOrThrow(decodeNativeTaskJson(readFileSync(new URL(path, import.meta.url))));
const decodeText = (value: string) => Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(value)));
const corpus = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_registry_v1/original.v1.json", import.meta.url), "utf8")) as {
    source_pins: Record<string, string>;
    cases: {
        name: string;
        protocol_json: string;
        model_json: string;
        revision_json: string;
        overrides_json: string;
        native_boundary?: string;
        result: {
            accepted: boolean;
            canonical?: string;
        };
    }[];
};
it("constructs the current Python registry from the current checked-in protocol", () => {
    const protocol = decode("../../../../prom_search_hswm/prom9_semantic_neural_network.v1.json"), actual = Either.getOrThrow(buildNativeProm9F1Registry(protocol, "qwen3.6-27b", "Qwen/Qwen3.6-27B@server-process-attested-20260724"));
    if (!taskJsonRecord(actual))
        throw new Error("registry");
    expect(actual["protocol_sha256"]).toBe("fbd23e84b1cccf581e6296808570b9b711bd20bc5ec9e876eeee83e8a77470fc");
    expect(actual["registry_sha256"]).toBe("25795ead3c60d98e519787bd41957f70f40789c5f35a84d2f5617f51202d08da");
});
it("refuses protocol violations before registry construction", () => {
    const source = JSON.parse(readFileSync(new URL("../../../../prom_search_hswm/prom9_semantic_neural_network.v1.json", import.meta.url), "utf8")) as Record<string, unknown>;
    for (const changed of [{ ...source, status: "OTHER" }, { ...source, stages: [] }, { ...source, external_governance: { authority: "NONE", prediction_registration_required: true, result_submission_allowed: false } }])
        expect(buildNativeProm9F1Registry(changed, "m", "r")).toMatchObject({ _tag: "Left" });
});
it("pins the original validator sources for the negative corpus", () => {
    for (const [name, digest] of Object.entries(corpus.source_pins))
        expect(createHash("sha256").update(readFileSync(new URL(`../../../../${name}`, import.meta.url))).digest("hex")).toBe(digest);
});
it("replays source-oracle inputs and labels stricter native boundaries", () => {
    for (const row of corpus.cases) {
        const actual = buildNativeProm9F1Registry(decodeText(row.protocol_json), decodeText(row.model_json), decodeText(row.revision_json), decodeText(row.overrides_json));
        const expected = row.native_boundary === undefined && row.result.accepted;
        expect(Either.isRight(actual), row.name).toBe(expected);
        if (expected)
            expect(renderNativeTaskJson(Either.getOrThrow(actual))).toBe(row.result.canonical);
    }
});
it("rejects getters and sparse arrays without reading an accessor", () => {
    let read = false;
    const getter = Object.defineProperty({}, "schema_version", { enumerable: true, get: () => { read = true; return "hswm-prom9-semantic-neural-network/v1"; } });
    expect(buildNativeProm9F1Registry(getter, "model", "revision")).toMatchObject({ _tag: "Left" });
    expect(read).toBe(false);
    const sparse: unknown[] = [];
    sparse[1] = "missing index zero";
    expect(buildNativeProm9F1Registry(sparse, "model", "revision")).toMatchObject({ _tag: "Left" });
    let overrideRead = false;
    const overrides = Object.defineProperty({}, "QF_QUERY_COMPILER", { enumerable: true, get: () => { overrideRead = true; return "prompt"; } });
    expect(buildNativeProm9F1Registry(decode("../../../../prom_search_hswm/prom9_semantic_neural_network.v1.json"), "model", "revision", overrides)).toMatchObject({ _tag: "Left" });
    expect(overrideRead).toBe(false);
});
