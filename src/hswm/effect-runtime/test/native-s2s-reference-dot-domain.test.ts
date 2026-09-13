import { readFileSync } from "node:fs";
import { Either } from "effect";
import { describe, expect, it } from "vitest";
import { nativeS2SFusedSquareAdd, nativeS2SReferenceSquaredNorm } from "../src/native-s2s-reference-dot-domain.js";
import { nativeS2SPositiveRatio } from "../src/native-s2s-dataset-domain.js";
interface Row {
    readonly input_hex_bits: string;
    readonly accum_hex_bits: string;
    readonly output_hex_bits: string;
}
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_protocol_score_v1/fma_square_add_oracle.v1.json", import.meta.url), "utf8")) as {
    readonly cases: readonly Row[];
};
const number = (bits: string): number => Buffer.from(bits, "hex").readDoubleBE();
const bits = (value: number): string => { const bytes = Buffer.alloc(8); bytes.writeDoubleBE(value); return bytes.toString("hex"); };
describe("pinned source reduction arithmetic", () => {
    it("replays 1,024 independent libc FMA cases, with typed negative-accumulator and overflow refusals", () => {
        expect(oracle.cases).toHaveLength(1024);
        for (const row of oracle.cases) {
            const actual = nativeS2SFusedSquareAdd(number(row.input_hex_bits), number(row.accum_hex_bits));
            if (number(row.accum_hex_bits) >= 0 && Number.isFinite(number(row.output_hex_bits))) {
                expect(Either.isRight(actual), JSON.stringify(row)).toBe(true);
                if (Either.isRight(actual))
                    expect(bits(actual.right), JSON.stringify(row)).toBe(row.output_hex_bits);
            }
            else
                expect(Either.isLeft(actual)).toBe(true);
        }
    });
    it("rejects sparse/accessor input without reading getters and rejects overflow", () => {
        let reads = 0;
        const values = Array<number>(12500).fill(1);
        Object.defineProperty(values, "0", { get: () => { reads += 1; return 1; } });
        for (const value of [Object.freeze(values), Object.freeze(Array<number>(12500)), Object.freeze(Array<number>(12500).fill(Number.MAX_VALUE))])
            expect(Either.isLeft(nativeS2SReferenceSquaredNorm(value))).toBe(true);
        expect(reads).toBe(0);
        expect(Either.isLeft(nativeS2SFusedSquareAdd(1, -1))).toBe(true);
        expect(Either.isLeft(nativeS2SFusedSquareAdd(NaN, 0))).toBe(true);
    });
    it("rounds exact positive integer ratios once, including ties and subnormal boundaries", () => {
        const cases = [[1n, 1n, 1], [(1n << 53n) + 1n, 1n << 53n, 1], [(1n << 53n) + 3n, 1n << 53n, 1 + 2 ** -51],
            [1n, 1n << 1074n, Number.MIN_VALUE], [3n, 1n << 1075n, 2 * Number.MIN_VALUE],
            [(1n << 53n) - 1n, 1n << 1075n, 2 ** -1022]] as const;
        for (const [numerator, denominator, expected] of cases) {
            const actual = nativeS2SPositiveRatio(numerator, denominator);
            expect(Either.isRight(actual)).toBe(true);
            if (Either.isRight(actual))
                expect(bits(actual.right)).toBe(bits(expected));
        }
        for (const [numerator, denominator] of [[0n, 1n], [1n, 0n], [1n, 1n << 1075n], [1n << 1024n, 1n]])
            expect(Either.isLeft(nativeS2SPositiveRatio(numerator, denominator))).toBe(true);
    });
});
