import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Either } from "effect";
import { expect, it } from "vitest";
import { normalizeNativeProm9F1Manifest } from "../src/native-prom9-f1-manifest-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord } from "../src/native-task-json-domain.js";
const load = (path: string) => Either.getOrThrow(decodeNativeTaskJson(readFileSync(new URL(path, import.meta.url))));
const corpus = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_manifest_v1/original.v1.json", import.meta.url), "utf8")) as {
    source_pins: Record<string, string>;
    cases: {
        name: string;
        input_json: string;
        result: {
            accepted: boolean;
            normalized_canonical?: string;
        };
    }[];
};
it("normalizes the source development manifest and rejects bounded malformed cases", () => {
    const manifest = load("../../../../_research/prom9_runs/f1-2wiki-dev-r5-envelope/manifest.v2.json"), suite = load("../../../../_research/prom9_runs/f1-2wiki-dev-r5-live/suite.json");
    if (!taskJsonRecord(suite))
        throw new Error("suite");
    const registries = suite["registries"]!;
    expect(normalizeNativeProm9F1Manifest(manifest, registries)).toMatchObject({ _tag: "Right" });
    for (const [raw, regs] of [[null, registries], [manifest, {}]] as const)
        expect(normalizeNativeProm9F1Manifest(raw, regs)).toMatchObject({ _tag: "Left" });
    let read = false;
    const getter = Object.defineProperty({}, "schema_version", { enumerable: true, get: () => { read = true; return "hswm-prom9-f1-manifest/v2"; } });
    expect(normalizeNativeProm9F1Manifest(getter, registries)).toMatchObject({ _tag: "Left" });
    expect(read).toBe(false);
    const sparse: unknown[] = [];
    sparse[1] = "missing index zero";
    expect(normalizeNativeProm9F1Manifest(sparse, registries)).toMatchObject({ _tag: "Left" });
});
it("replays all source-generated manifest inputs", () => {
    const suite = load("../../../../_research/prom9_runs/f1-2wiki-dev-r5-live/suite.json");
    if (!taskJsonRecord(suite))
        throw new Error("suite");
    const registries = suite["registries"]!;
    expect(createHash("sha256").update(readFileSync(new URL("../../../../prom_search_hswm/prom_f1_function_network.py", import.meta.url))).digest("hex")).toBe(corpus.source_pins["prom_f1_function_network.py"]);
    for (const row of corpus.cases) {
        const decoded = Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(row.input_json)));
        const actual = normalizeNativeProm9F1Manifest(decoded, registries);
        expect(Either.isRight(actual), row.name).toBe(row.result.accepted);
        if (row.result.accepted)
            expect(renderNativeTaskJson(Either.getOrThrow(actual))).toBe(row.result.normalized_canonical);
    }
});
