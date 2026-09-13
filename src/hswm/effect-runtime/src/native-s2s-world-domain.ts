/**
 * Native projection of the deterministic SWM-0W S2S V1 finite-world scorer.
 * It is an engineering parity surface only: no fit, efficacy, or protocol
 * outcome is derived here.
 */
import { Data, Either } from "effect";
export const NATIVE_S2S_WORLD_SOURCE_SHA256 = "365a2d57e9988f1223b5ea39e26c9196c0d26400c821acbcd8c62a6f224d4f81" as const;
export const NATIVE_S2S_WORLD_SCIENTIFIC_STATUS = "UNJUDGED_INTEGRITY_ONLY" as const;
export const NATIVE_S2S_TARGET_SCALE_EXPONENT = 15 as const;
const FACTOR_FRAME = Object.freeze([
    Object.freeze([-2, -1, 0, 1, 2]),
    Object.freeze([0, 3, -4, -1, 2]),
    Object.freeze([7, -7, -6, 5, 1]),
    Object.freeze([3, -3, 2, -7, 5])
] as const);
type RawValues = readonly [
    number,
    number,
    number,
    number,
    number,
    number
];
type Contrast = readonly [
    number,
    number,
    number,
    number
];
type TargetRow = readonly [
    number,
    number
];
export type NativeS2SSplit = "train" | "dev" | "test";
export class NativeS2SWorldError extends Data.TaggedError("NativeS2SWorldError")<{
    readonly reason: "CENTERED_CONTRAST_INVALID" | "RAW_VALUES_INVALID";
    readonly detail: string;
}> {
}
const rawError = (): NativeS2SWorldError => new NativeS2SWorldError({
    reason: "RAW_VALUES_INVALID",
    detail: "raw values must be an immutable exact Z5 six-tuple"
});
const validZ5 = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0 && value < 5;
const freezeContrast = (values: readonly number[]): Contrast => Object.freeze([values[0]!, values[1]!, values[2]!, values[3]!] as const);
export const centeredContrasts = (value: unknown): Either.Either<Contrast, NativeS2SWorldError> => validZ5(value)
    ? Either.right(freezeContrast([0, 1, 2, 3].map((q) => Number(value === q) - Number(value === 4))))
    : Either.left(new NativeS2SWorldError({
        reason: "CENTERED_CONTRAST_INVALID",
        detail: "a centered contrast requires an exact Z5 integer"
    }));
export const validateNativeS2SRawValues = (value: unknown): Either.Either<RawValues, NativeS2SWorldError> => Array.isArray(value) && value.length === 6 && [0, 1, 2, 3, 4, 5].every((index) => Object.hasOwn(value, index) && validZ5(value[index]))
    ? Either.right(Object.freeze([
        value[0]!, value[1]!, value[2]!, value[3]!, value[4]!, value[5]!
    ] as const))
    : Either.left(rawError());
const factor = (kind: "P" | "T", role: number, channel: number, rank: number, value: number): number => {
    const offset = (role + channel) % 4;
    const frameIndex = (offset + rank + (kind === "P" ? 2 : 0)) % 4;
    return FACTOR_FRAME[frameIndex]![value]!;
};
const splitForSyndrome = (syndrome: number): NativeS2SSplit => syndrome === 2 ? "dev" : syndrome === 3 || syndrome === 4 ? "test" : "train";
export interface NativeS2SWorldScore {
    readonly rawValues: RawValues;
    readonly syndrome: number;
    readonly split: NativeS2SSplit;
    readonly centeredContrasts: readonly Contrast[];
    readonly targetNumerators: readonly TargetRow[];
    readonly targetFloats: readonly TargetRow[];
    readonly scientificStatus: typeof NATIVE_S2S_WORLD_SCIENTIFIC_STATUS;
}
export const scoreNativeS2SWorld = (candidate: unknown): Either.Either<NativeS2SWorldScore, NativeS2SWorldError> => {
    const validated = validateNativeS2SRawValues(candidate);
    if (Either.isLeft(validated))
        return Either.left(validated.left);
    const rawValues = validated.right;
    const centered = rawValues.map((value) => freezeContrast([0, 1, 2, 3].map((q) => Number(value === q) - Number(value === 4))));
    const targetNumerators: TargetRow[] = [];
    for (let role = 0; role < 3; role += 1) {
        for (let member = 0; member < 2; member += 1) {
            const recipient = rawValues[2 * role + member]!;
            const comember = rawValues[2 * role + 1 - member]!;
            const channels: number[] = [];
            for (let channel = 0; channel < 2; channel += 1) {
                let total = 0;
                for (let rank = 0; rank < 2; rank += 1) {
                    let term = factor("P", role, channel, rank, recipient) * factor("T", role, channel, rank, comember);
                    for (let source = 0; source < 3; source += 1) {
                        if (source !== role)
                            term *= factor("T", source, channel, rank, rawValues[2 * source]!) + factor("T", source, channel, rank, rawValues[2 * source + 1]!);
                    }
                    total += term;
                }
                channels.push(total);
            }
            targetNumerators.push(Object.freeze([channels[0]!, channels[1]!] as const));
        }
    }
    const syndrome = rawValues.reduce((sum, value) => sum + value, 0) % 5;
    const scale = 2 ** NATIVE_S2S_TARGET_SCALE_EXPONENT;
    return Either.right(Object.freeze({
        rawValues,
        syndrome,
        split: splitForSyndrome(syndrome),
        centeredContrasts: Object.freeze(centered),
        targetNumerators: Object.freeze(targetNumerators),
        targetFloats: Object.freeze(targetNumerators.map((row) => Object.freeze([row[0] / scale, row[1] / scale] as const))),
        scientificStatus: NATIVE_S2S_WORLD_SCIENTIFIC_STATUS
    }));
};
