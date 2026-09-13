import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Either } from "effect";
import { decodeNativeTaskJson, renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js";
import { canonicalNativeProm9Sha256 } from "../src/native-prom9-ports-domain.js";
import { PYTHON_JSON_DECIMAL_ZEROS, pythonJsonInt, pythonJsonNormalizeAnswer } from "../src/native-python-json-semantics-domain.js";
import { verifyNativeProm9CallReceipt, verifyNativeProm9CallReceiptJson, verifyNativeProm9RunReceipt, verifyNativeProm9RunReceiptJson } from "../src/native-prom9-receipt-domain.js";

type FixtureCase = Readonly<{ readonly name: string; readonly kind: "call" | "run"; readonly input_json: string; readonly accepted: boolean; readonly digest?: string }>;
type Fixture = Readonly<{ readonly source_pins: Readonly<Record<string, string>>; readonly cases: readonly FixtureCase[] }>;
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_receipts_v1/original.v1.json", import.meta.url), "utf8")) as Fixture;
const semantics = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_receipts_v1/semantics.original.v1.json", import.meta.url), "utf8")) as Fixture & { readonly decimal_zero_codepoints: readonly number[] };
const decode = (source: string): TaskJson => Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(source)));
const clone = (value: TaskJson): TaskJson => decode(renderNativeTaskJson(value));
const hashRun = (run: Record<string, TaskJson>): void => {
  const unsigned = Object.fromEntries(Object.entries(run).filter(([key]) => key !== "run_receipt_sha256"));
  run["run_receipt_sha256"] = Either.getOrThrow(canonicalNativeProm9Sha256(unsigned));
};

describe("native PROM-9 receipt verification", () => {
  it("matches the source-pinned original valid and invalid corpus without a Python test dependency", () => {
    for (const [name, digest] of Object.entries(fixture.source_pins)) expect(createHash("sha256").update(readFileSync(new URL(`../../../../prom_search_hswm/${name}`, import.meta.url))).digest("hex")).toBe(digest);
    for (const row of [...fixture.cases, ...semantics.cases]) {
      const value = decode(row.input_json);
      const result = row.kind === "call" ? verifyNativeProm9CallReceipt(value) : verifyNativeProm9RunReceipt(value);
      expect(Either.isRight(result), row.name).toBe(row.accepted);
      if (Either.isRight(result)) expect(result.right).toBe(row.digest);
    }
  });

  it("rejects changed bindings with correctly recomputed enclosing hashes", () => {
    const valid = clone(decode(fixture.cases.find(row => row.name === "valid-run")!.input_json)) as Record<string, TaskJson>;
    const cases: readonly [string, (run: Record<string, TaskJson>) => void][] = [
      ["call count", run => { run["calls"] = (run["calls"] as TaskJson[]).slice(0, 2); }],
      ["call order", run => { const calls = run["calls"] as Record<string, TaskJson>[]; [calls[0], calls[1]] = [calls[1]!, calls[0]!]; }],
      ["call self hash", run => { ((run["calls"] as Record<string, TaskJson>[])[0]!)["receipt_sha256"] = "0".repeat(64); }],
      ["input digest", run => { ((run["calls"] as Record<string, TaskJson>[])[0]!)["input_port_sha256"] = "0".repeat(64); }],
      ["answer", run => { run["answer"] = { ...(run["answer"] as Record<string, TaskJson>), answer: "changed" }; }],
      ["input total", run => { run["total_input_tokens"] = 99; }],
    ];
    for (const [name, mutate] of cases) {
      const candidate = clone(valid) as Record<string, TaskJson>; mutate(candidate);
      if (name === "input digest") {
        const call = (candidate["calls"] as Record<string, TaskJson>[])[0]!;
        call["receipt_sha256"] = Either.getOrThrow(canonicalNativeProm9Sha256(Object.fromEntries(Object.entries(call).filter(([key]) => key !== "receipt_sha256"))));
      }
      hashRun(candidate);
      expect(verifyNativeProm9RunReceipt(candidate), name).toMatchObject({ _tag: "Left" });
      if (name === "input digest") expect(verifyNativeProm9RunReceipt(candidate)).toMatchObject({ left: { detail: "call receipt input port drifted" } });
    }
  });

  it("pins the original Unicode decimal alphabet and preserves its integer conversion limit", () => {
    expect(PYTHON_JSON_DECIMAL_ZEROS).toEqual(semantics.decimal_zero_codepoints);
    for (const zero of semantics.decimal_zero_codepoints) {
      expect(pythonJsonInt(String.fromCodePoint(zero + 1, zero + 2))).toBe(12n);
    }
    expect(pythonJsonInt("1".repeat(4300))).toBe(BigInt("1".repeat(4300)));
    expect(pythonJsonInt("1".repeat(4301))).toBeUndefined();
    expect(pythonJsonInt("\u001c1")).toBeUndefined();
    expect(pythonJsonInt("\uFEFF1")).toBeUndefined();
  });

  it("uses the complete source Python casefold table and whitespace semantics", () => {
    const expected = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_receipts_v1/casefold.original.v1.json", import.meta.url), "utf8")) as { readonly mapping_sha256: string; readonly cases: readonly { readonly source: string; readonly normalized: string }[] };
    expect(createHash("sha256").update(readFileSync(new URL("../src/native-python-casefold-data.ts", import.meta.url))).digest("hex")).toBe(expected.mapping_sha256);
    for (const row of expected.cases) expect(pythonJsonNormalizeAnswer(row.source)).toBe(row.normalized);
  });

  it("accepts raw JSON through the number-lexeme decoder and rejects malformed runtime inputs", () => {
    const call = fixture.cases.find(row => row.name === "valid-call")!;
    const run = fixture.cases.find(row => row.name === "valid-run")!;
    expect(verifyNativeProm9CallReceiptJson(new TextEncoder().encode(call.input_json))).toMatchObject({ _tag: "Right", right: call.digest });
    expect(verifyNativeProm9RunReceiptJson(new TextEncoder().encode(run.input_json))).toMatchObject({ _tag: "Right", right: run.digest });
    expect(verifyNativeProm9CallReceipt(null)).toMatchObject({ _tag: "Left" });
    expect(verifyNativeProm9RunReceiptJson(new TextEncoder().encode("{bad"))).toMatchObject({ _tag: "Left" });
  });
});
