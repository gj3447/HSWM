import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, it } from "@effect/vitest";
import { Either } from "effect";
import { nativeS2SFloatHex } from "../src/native-s2s-dataset-domain.js";
import { sumNativeS2SReferenceLossTerms } from "../src/native-s2s-reference-loss-domain.js";
type VectorSpec = {
    readonly kind: "weighted_terms_affine_v1";
    readonly weights_hex: readonly string[];
} | {
    readonly kind: "alternating_affine_v1";
} | {
    readonly kind: "cycle_hex_v1";
    readonly values_hex: readonly string[];
} | {
    readonly kind: "alternating_signed_zero_v1";
    readonly even_hex: string;
    readonly odd_hex: string;
};
interface VectorCase {
    readonly name: string;
    readonly length: number;
    readonly raw_sha256: string;
    readonly sum_hex: string;
    readonly vector_spec: VectorSpec;
}
interface Fixture {
    readonly numpy_version: string;
    readonly array: {
        readonly dtype: string;
        readonly order: string;
        readonly sum_dtype: string;
        readonly numpy_getbufsize: number;
    };
    readonly cases: readonly VectorCase[];
}
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_reference_loss_v1/sum_vectors.v1.json", import.meta.url), "utf8")) as Fixture;
const floatFromHex = (text: string): number => {
    if (text === "0x0.0p+0")
        return 0;
    if (text === "-0x0.0p+0")
        return -0;
    const match = /^(-?)0x([01])\.([0-9a-f]{13})p([+-][0-9]+)$/.exec(text);
    if (match === null)
        throw new Error(`unexpected fixture float hex: ${text}`);
    const exponent = Number(match[4]);
    const bits = (match[1] === "-" ? 1n << 63n : 0n)
        | (match[2] === "1" ? BigInt(exponent + 1023) << 52n : 0n)
        | BigInt(`0x${match[3]}`);
    const bytes = Buffer.alloc(8);
    bytes.writeBigUInt64LE(bits);
    return bytes.readDoubleLE();
};
const valuesFor = (entry: VectorCase): readonly number[] => {
    const { length, vector_spec: spec } = entry;
    if (spec.kind === "weighted_terms_affine_v1") {
        const weights = spec.weights_hex.map(floatFromHex);
        return Object.freeze(Array.from({ length }, (_, i) => {
            const residual = (((i * 48271 + 12345) % 104729) - 52364) / 65537;
            return residual * residual * weights[i % weights.length]!;
        }));
    }
    if (spec.kind === "alternating_affine_v1")
        return Object.freeze(Array.from({ length }, (_, i) => {
            const magnitude = 1 + ((i * 8191 + 97) % 65537) / 65536;
            return i % 2 === 0 ? magnitude : -magnitude;
        }));
    if (spec.kind === "cycle_hex_v1") {
        const cycle = spec.values_hex.map(floatFromHex);
        return Object.freeze(Array.from({ length }, (_, i) => cycle[i % cycle.length]!));
    }
    const even = floatFromHex(spec.even_hex), odd = floatFromHex(spec.odd_hex);
    return Object.freeze(Array.from({ length }, (_, i) => i % 2 === 0 ? even : odd));
};
const rawSha256 = (values: readonly number[]): string => {
    const bytes = Buffer.alloc(values.length * 8);
    values.forEach((value, index) => bytes.writeDoubleLE(value, index * 8));
    return createHash("sha256").update(bytes).digest("hex");
};
it("replays every pinned NumPy float64 sum vector exactly", () => {
    expect(fixture.numpy_version).toBe("2.5.2");
    expect(fixture.array).toEqual({ dtype: "<f8", order: "C", sum_dtype: "<f8", numpy_getbufsize: 8192 });
    const mismatches: string[] = [];
    for (const entry of fixture.cases) {
        const values = valuesFor(entry);
        expect(rawSha256(values), entry.name).toBe(entry.raw_sha256);
        const result = sumNativeS2SReferenceLossTerms(values);
        expect(Either.isRight(result), entry.name).toBe(true);
        if (Either.isRight(result)) {
            const observed = nativeS2SFloatHex(result.right);
            if (observed !== entry.sum_hex)
                mismatches.push(`${entry.name}: ${observed} !== ${entry.sum_hex}`);
        }
    }
    expect(mismatches).toEqual([]);
}, 60000);
