/** Deterministic emulation of the recorded NumPy 2.5.2 / OpenBLAS 0.3.34
 * SkylakeX, 16-thread, contiguous 12,500-value score reduction. This profile is
 * explicit: it does not claim that arbitrary NumPy builds produce these bytes.
 * Reduction topology derives from OpenBLAS e0166008be8e466242aa76b2ff75ce3f0fbf574a;
 * see assets/licenses/OPENBLAS_NUMERICAL_REFERENCE_NOTICE.txt.
 */
import { Data, Either } from "effect";
export const NATIVE_S2S_SCORE_REDUCTION_PROFILE = "NUMPY_2.5.2_SCIPY_OPENBLAS_0.3.34_SKYLAKEX_16_THREADS_F64_12500" as const;
export class NativeS2SReferenceDotError extends Data.TaggedError("NativeS2SReferenceDotError")<{
    readonly detail: string;
}> {
}
const failure = (detail: string): Either.Either<never, NativeS2SReferenceDotError> => Either.left(new NativeS2SReferenceDotError({ detail }));
const dyadic = (value: number): readonly [
    bigint,
    number
] => {
    const bytes = Buffer.alloc(8);
    bytes.writeDoubleLE(value);
    const bits = bytes.readBigUInt64LE(), exponent = Number((bits >> 52n) & 2047n), fraction = bits & ((1n << 52n) - 1n);
    return [exponent === 0 ? fraction : (1n << 52n) | fraction, exponent === 0 ? -1074 : exponent - 1075];
};
/** Exact nonnegative dyadic rounding, once, to nearest binary64, ties to even. */
const roundDyadic = (significand: bigint, exponent: number): number => {
    if (significand === 0n)
        return 0;
    const power = significand.toString(2).length - 1 + exponent;
    const targetExponent = Math.max(-1074, power - 52), shift = targetExponent - exponent;
    if (shift <= 0)
        return Number(significand << BigInt(-shift)) * 2 ** targetExponent;
    const width = BigInt(shift), quotient = significand >> width, remainder = significand - (quotient << width), half = 1n << (width - 1n);
    const rounded = remainder > half || (remainder === half && (quotient & 1n) === 1n) ? quotient + 1n : quotient;
    return Number(rounded) * 2 ** targetExponent;
};
const squareAdd = (value: number, accumulator: number): number => {
    if (accumulator === Infinity)
        return Infinity;
    const [mantissa, exponent] = dyadic(value), [addend, addendExponent] = dyadic(accumulator);
    const productExponent = 2 * exponent, commonExponent = Math.min(productExponent, addendExponent);
    return roundDyadic((mantissa * mantissa << BigInt(productExponent - commonExponent)) + (addend << BigInt(addendExponent - commonExponent)), commonExponent);
};
/** Bounded FMA operation used by the source score kernel. Overflow is a typed refusal. */
export const nativeS2SFusedSquareAdd = (value: unknown, accumulator: unknown): Either.Either<number, NativeS2SReferenceDotError> => {
    if (typeof value !== "number" || !Number.isFinite(value) || typeof accumulator !== "number" || !Number.isFinite(accumulator) || accumulator < 0)
        return failure("FMA requires a finite value and finite nonnegative accumulator");
    const result = squareAdd(value, accumulator);
    return Number.isFinite(result) ? Either.right(result) : failure("FMA overflow");
};
const worker = (values: readonly number[], start: number, width: number): number => {
    const n16 = width - width % 16, n32 = n16 - n16 % 32;
    // Scratch is local; neither inputs nor returned values expose mutable state.
    const wide: number[] = Array<number>(32).fill(0);
    for (let i = 0; i < n32; i += 32)
        for (let lane = 0; lane < 32; lane += 1)
            wide[lane] = squareAdd(values[start + i + lane]!, wide[lane]!);
    const narrow = Array.from({ length: 16 }, (_, lane) => wide[Math.floor(lane / 4) * 8 + lane % 4]! + wide[Math.floor(lane / 4) * 8 + lane % 4 + 4]!);
    for (let i = n32; i < n16; i += 16)
        for (let lane = 0; lane < 16; lane += 1)
            narrow[lane] = squareAdd(values[start + i + lane]!, narrow[lane]!);
    const lanes = Array.from({ length: 4 }, (_, lane) => ((narrow[lane]! + narrow[lane + 4]!) + narrow[lane + 8]!) + narrow[lane + 12]!);
    let result = (lanes[0]! + lanes[2]!) + (lanes[1]! + lanes[3]!);
    for (let i = n16; i < width; i += 1)
        result = squareAdd(values[start + i]!, result);
    return result;
};
export const nativeS2SReferenceSquaredNorm = (candidate: unknown): Either.Either<number, NativeS2SReferenceDotError> => {
    if (!Array.isArray(candidate) || !Object.isFrozen(candidate) || candidate.length !== 12500 || Reflect.ownKeys(candidate).length !== 12501)
        return failure("reference reduction requires exactly 12,500 dense frozen data values");
    const values: number[] = [];
    for (let i = 0; i < 12500; i += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(candidate, i);
        if (descriptor === undefined || !Object.hasOwn(descriptor, "value") || typeof descriptor.value !== "number" || !Number.isFinite(descriptor.value))
            return failure("reference reduction requires finite data values without accessors");
        values.push(descriptor.value);
    }
    let offset = 0, result = 0;
    for (let thread = 0; thread < 16; thread += 1) {
        const width = Math.ceil((12500 - offset) / (16 - thread));
        result += worker(values, offset, width);
        offset += width;
    }
    return Number.isFinite(result) ? Either.right(result) : failure("reference squared norm overflow");
};
