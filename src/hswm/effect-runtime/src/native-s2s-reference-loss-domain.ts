/** NumPy 2.5.2 reference weighted-loss reduction; no tolerance-based admission.
 * Official commit 48fecee5453aa1d31e6b79dcb3969dc1a6d1a891,
 * numpy/_core/src/umath/loops_utils.h.src SHA256
 * ed85d5b99f0b457cb7a316bf8c4acb884034bbbb81a89c5cedb62be80bf7c4f8.
 * See assets/licenses/NUMPY_NUMERICAL_REFERENCE_NOTICE.txt. */
import { Either, Data } from "effect";
import { forwardNativeS2SDs870, forwardNativeS2SPCap18, forwardNativeS2ST16, type NativeS2SDs870Parameters, type NativeS2SPCap18Parameters, type NativeS2ST16Parameters } from "./native-s2s-operator-domain.js";
import type { NativeS2SParameters, NativeS2STrainingArm } from "./native-s2s-training-numeric-domain.js";
export class NativeS2SReferenceLossError extends Data.TaggedError("NativeS2SReferenceLossError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeS2SReferenceLossError> => Either.left(new NativeS2SReferenceLossError({ detail }));
const pair = (v: readonly number[], start: number, n: number): number => {
    if (n < 8) {
        let sum = -0;
        for (let i = 0; i < n; i++)
            sum += v[start + i]!;
        return sum;
    }
    if (n <= 128) {
        const lanes = v.slice(start, start + 8);
        let i = 8;
        for (; i < n - n % 8; i += 8)
            for (let lane = 0; lane < 8; lane++)
                lanes[lane]! += v[start + i + lane]!;
        let sum = ((lanes[0]! + lanes[1]!) + (lanes[2]! + lanes[3]!)) + ((lanes[4]! + lanes[5]!) + (lanes[6]! + lanes[7]!));
        for (; i < n; i++)
            sum += v[start + i]!;
        return sum;
    }
    const half = Math.floor(n / 2), left = half - half % 8;
    return pair(v, start, left) + pair(v, start + left, n - left);
};
const dense = (value: unknown): value is readonly number[] => {
    try {
        return Array.isArray(value) && Object.getPrototypeOf(value) === Array.prototype && Reflect.ownKeys(value).length === value.length + 1 && Array.from({ length: value.length }, (_, i) => { const d = Object.getOwnPropertyDescriptor(value, i); return d !== undefined && Object.hasOwn(d, "value") && typeof d.value === "number" && Number.isFinite(d.value); }).every(Boolean);
    }
    catch {
        return false;
    }
};
const captureParameters = (raw: unknown): NativeS2SParameters | undefined => {
    try {
        if (raw === null || typeof raw !== "object" || Array.isArray(raw) || ![Object.prototype, null].includes(Object.getPrototypeOf(raw)) || Reflect.ownKeys(raw).length > 8)
            return undefined;
        const entries: [
            string,
            readonly number[]
        ][] = [];
        for (const key of Reflect.ownKeys(raw)) {
            if (typeof key !== "string")
                return undefined;
            const d = Object.getOwnPropertyDescriptor(raw, key);
            if (d === undefined || !Object.hasOwn(d, "value") || !d.enumerable || !dense(d.value) || d.value.length > 870)
                return undefined;
            entries.push([key, Object.freeze([...d.value])]);
        }
        return Object.freeze(Object.fromEntries(entries)) as unknown as NativeS2SParameters;
    }
    catch {
        return undefined;
    }
};
/** Contiguous float64 reduction spans the whole array; getbufsize is not a chunk size. */
export const sumNativeS2SReferenceLossTerms = (values: readonly number[]): Either.Either<number, NativeS2SReferenceLossError> => {
    if (!dense(values))
        return fail("reference terms must be dense finite binary64 values");
    const sum = 0 + pair(values, 0, values.length);
    return Number.isFinite(sum) ? Either.right(sum) : fail("reference reduction is nonfinite");
};
export const lossForNativeS2SReferenceParameters = (arm: NativeS2STrainingArm, params: NativeS2SParameters, input: readonly number[], targets: readonly number[], weights: readonly number[]): Either.Either<number, NativeS2SReferenceLossError> => {
    if (!["T16", "P_CAP18", "DS870"].includes(arm) || !dense(input) || !dense(targets) || !dense(weights) || input.length === 0 || input.length % 24 !== 0 || targets.length !== input.length / 2 || weights.length !== 6 || weights.some(v => v <= 0))
        return fail("invalid dense reference tensors");
    const captured = captureParameters(params);
    if (captured === undefined)
        return fail("reference parameters must be plain dense finite data");
    const terms: number[] = [];
    for (let n = 0; n < input.length / 24; n++) {
        const x = input.slice(n * 24, n * 24 + 24);
        const f = arm === "T16" ? forwardNativeS2ST16(x, captured as NativeS2ST16Parameters) : arm === "P_CAP18" ? forwardNativeS2SPCap18(x, captured as NativeS2SPCap18Parameters) : forwardNativeS2SDs870(x, captured as NativeS2SDs870Parameters);
        if (Either.isLeft(f))
            return fail(f.left.detail);
        const out = f.right.flat(2);
        for (let i = 0; i < 12; i++) {
            const e = out[i]! - targets[n * 12 + i]!;
            terms.push(e * e * weights[Math.floor(i / 4) * 2 + i % 2]!);
        }
    }
    return sumNativeS2SReferenceLossTerms(terms).pipe(Either.map(value => value / (12 * (input.length / 24))));
};
