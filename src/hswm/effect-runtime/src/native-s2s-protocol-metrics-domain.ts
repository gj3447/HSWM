/**
 * Immutable score-to-metric reduction from the historical SWM-0W S2S protocol.
 * This is engineering parity for the bounded receipt reduction only; it makes
 * no fit, integrity, bootstrap, or scientific claim.
 */
import { Data, Either } from "effect";
export const NATIVE_S2S_PROTOCOL_METRICS_SOURCE_SHA256 = "c0df25e37d0e54c792f0eca9f78d83029e4fedd8f837743096eef2b29a62a2c1" as const;
export const NATIVE_S2S_PROTOCOL_METRICS_SCIENTIFIC_STATUS = "CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED" as const;
export const NATIVE_S2S_SCORE_VARIANTS = Object.freeze([
    "T16_BASE", "P_CAP18_BASE", "DS870_BASE", "T16_Q_REMOVED",
    "T16_RESTORED", "T16_BROADCAST", "T16_CYCLE_120", "T16_CYCLE_201"
] as const);
export type NativeS2SScoreVariant = typeof NATIVE_S2S_SCORE_VARIANTS[number];
export interface NativeS2SProtocolStratumR2 {
    readonly role: number;
    readonly channel: number;
    readonly r2: number;
}
export interface NativeS2SProtocolScoreR2 {
    readonly variant: NativeS2SScoreVariant;
    readonly strata: readonly NativeS2SProtocolStratumR2[];
}
export interface NativeS2STaskMetricValues {
    readonly q: number;
    readonly b: number;
    readonly r: number;
    readonly c: number;
    readonly scientificStatus: typeof NATIVE_S2S_PROTOCOL_METRICS_SCIENTIFIC_STATUS;
}
export class NativeS2SProtocolMetricsError extends Data.TaggedError("NativeS2SProtocolMetricsError")<{
    readonly reason: "SCORES_INVALID" | "NUMERIC_INVALID";
    readonly detail: string;
}> {
}
const fail = (reason: NativeS2SProtocolMetricsError["reason"], detail: string): Either.Either<never, NativeS2SProtocolMetricsError> => Either.left(new NativeS2SProtocolMetricsError({ reason, detail }));
const frozen = <Value>(value: Value): Value => Object.freeze(value);
const safeFrozen = (value: object): boolean => { try {
    return Object.isFrozen(value);
}
catch {
    return false;
} };
const ownNames = (value: object): readonly string[] | undefined => { try {
    return Object.getOwnPropertyNames(value).sort();
}
catch {
    return undefined;
} };
const data = (value: object, key: string): unknown | undefined => {
    try {
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        return descriptor !== undefined && Object.hasOwn(descriptor, "value") ? descriptor.value : undefined;
    }
    catch {
        return undefined;
    }
};
const sameKeys = (actual: readonly string[] | undefined, expected: readonly string[]): boolean => actual !== undefined && actual.length === expected.length && actual.every((key, index) => key === expected[index]);
const exactArray = (value: unknown, length: number): readonly unknown[] | undefined => {
    if (!Array.isArray(value) || !safeFrozen(value))
        return undefined;
    const keys = Object.freeze([...Array.from({ length }, (_, index) => String(index)), "length"].sort());
    if (!sameKeys(ownNames(value), keys) || data(value, "length") !== length)
        return undefined;
    const entries = Array.from({ length }, (_, index) => data(value, String(index)));
    return entries.every((entry) => entry !== undefined) ? frozen(entries) : undefined;
};
const exactObject = (value: unknown, keys: readonly string[]): readonly unknown[] | undefined => {
    if (value === null || typeof value !== "object" || Array.isArray(value) || !safeFrozen(value) || !sameKeys(ownNames(value), keys))
        return undefined;
    const entries = keys.map((key) => data(value, key));
    return entries.every((entry) => entry !== undefined) ? frozen(entries) : undefined;
};
const finiteNonNegativeZero = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && !Object.is(value, -0);
const expectedStrata = Object.freeze(Array.from({ length: 6 }, (_, index) => frozen([Math.floor(index / 2), index % 2] as const)));
const scoreKeys = Object.freeze(["strata", "variant"]);
const stratumKeys = Object.freeze(["channel", "r2", "role"]);
const scoreMatrices = (candidate: unknown): Either.Either<readonly (readonly number[])[], NativeS2SProtocolMetricsError> => {
    const roster = exactArray(candidate, NATIVE_S2S_SCORE_VARIANTS.length);
    if (roster === undefined)
        return fail("SCORES_INVALID", "task metrics require an immutable dense score-variant roster");
    const matrices: (readonly number[])[] = [];
    for (let scoreIndex = 0; scoreIndex < roster.length; scoreIndex += 1) {
        const score = exactObject(roster[scoreIndex], scoreKeys);
        if (score === undefined || score[1] !== NATIVE_S2S_SCORE_VARIANTS[scoreIndex])
            return fail("SCORES_INVALID", "score variant order or data-object shape is invalid");
        const strata = exactArray(score[0], 6);
        if (strata === undefined)
            return fail("SCORES_INVALID", "score strata must be an immutable dense six-row array");
        const values: number[] = [];
        for (let stratumIndex = 0; stratumIndex < strata.length; stratumIndex += 1) {
            const stratum = exactObject(strata[stratumIndex], stratumKeys);
            const expected = expectedStrata[stratumIndex]!;
            if (stratum === undefined || stratum[0] !== expected[1] || !finiteNonNegativeZero(stratum[1]) || stratum[2] !== expected[0])
                return fail("SCORES_INVALID", "score stratum order, data-object shape, or R2 is invalid");
            values.push(stratum[1]);
        }
        matrices.push(frozen(values));
    }
    return Either.right(frozen(matrices));
};
const clean = (value: number): Either.Either<number, NativeS2SProtocolMetricsError> => Number.isFinite(value)
    ? Either.right(value === 0 ? 0 : value)
    : fail("NUMERIC_INVALID", "numeric reduction produced a non-finite value");
const minimum = (values: readonly number[]): Either.Either<number, NativeS2SProtocolMetricsError> => values.length === 0
    ? fail("SCORES_INVALID", "metric reduction requires non-empty strata")
    : clean(Math.min(...values));
/** Ports `_metric_values`; callers supply only the already validated score R2 rows. */
export const nativeS2STaskMetricValues = (candidate: unknown): Either.Either<NativeS2STaskMetricValues, NativeS2SProtocolMetricsError> => {
    const matrices = scoreMatrices(candidate);
    if (Either.isLeft(matrices))
        return fail(matrices.left.reason, matrices.left.detail);
    const base = matrices.right[0]!;
    const broadcast = matrices.right[5]!;
    const cycle120 = matrices.right[6]!;
    const cycle201 = matrices.right[7]!;
    const ds870 = matrices.right[2]!;
    const q = minimum(base);
    if (Either.isLeft(q))
        return fail(q.left.reason, q.left.detail);
    const b = minimum(base.map((value, index) => value - broadcast[index]!));
    if (Either.isLeft(b))
        return fail(b.left.reason, b.left.detail);
    const r = minimum([...base.map((value, index) => value - cycle120[index]!), ...base.map((value, index) => value - cycle201[index]!)]);
    if (Either.isLeft(r))
        return fail(r.left.reason, r.left.detail);
    const baseMinimum = minimum(base);
    if (Either.isLeft(baseMinimum))
        return fail(baseMinimum.left.reason, baseMinimum.left.detail);
    const ds870Minimum = minimum(ds870);
    if (Either.isLeft(ds870Minimum))
        return fail(ds870Minimum.left.reason, ds870Minimum.left.detail);
    const c = clean(baseMinimum.right - ds870Minimum.right);
    if (Either.isLeft(c))
        return fail(c.left.reason, c.left.detail);
    return Either.right(frozen({ q: q.right, b: b.right, r: r.right, c: c.right, scientificStatus: NATIVE_S2S_PROTOCOL_METRICS_SCIENTIFIC_STATUS }));
};
