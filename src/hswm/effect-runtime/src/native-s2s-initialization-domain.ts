/**
 * Source-bound PCG64 initialization parity for SWM-0W S2S training only.
 * Port reference: NumPy 2.5.2 (resolved tag commit 48fecee5453aa1d31e6b79dcb3969dc1a6d1a891),
 * BSD-3-Clause NumPy plus MIT SeedSequence/PCG64 components. The locked sdist
 * is sha256:d482d171c406ae88c5b19cad3b6a1c4c5209f886ab74bc44c2c865c23f52d860.
 */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { renderNativeTaskJson, validNativeTaskJson } from "./native-task-json-domain.js";
import type { NativeS2SParameters } from "./native-s2s-training-numeric-domain.js";
export const NATIVE_S2S_INITIALIZATION_SOURCE_SHA256 = "d84b8336d8bcbe89aeba7f2d2c915fd294b9ee24425e6092505069a74f9cba94" as const;
export const NATIVE_S2S_INITIALIZATION_NUMPY_VERSION = "2.5.2" as const;
export type NativeS2SInitializationArm = "P_CAP18" | "T16" | "DS870";
export class NativeS2SInitializationError extends Data.TaggedError("NativeS2SInitializationError")<{
    readonly reason: "ARM_INVALID" | "CANONICAL_INVALID" | "PARAMETERS_INVALID" | "SEED_INVALID";
    readonly detail: string;
}> {
}
const fail = (reason: NativeS2SInitializationError["reason"], detail: string): Either.Either<never, NativeS2SInitializationError> => Either.left(new NativeS2SInitializationError({ reason, detail }));
const MASK32 = 0xffffffffn, MASK128 = (1n << 128n) - 1n;
const u32 = (value: bigint | number): number => Number(BigInt(value) & MASK32);
const multiply32 = (left: number, right: number): number => u32(BigInt(left) * BigInt(right));
const hashMix = (value: number, state: {
    value: number;
}): number => { let mixed = u32(value ^ state.value); state.value = multiply32(state.value, 0x931e8875); mixed = multiply32(mixed, state.value); return u32(mixed ^ (mixed >>> 16)); };
const mix = (left: number, right: number): number => { const value = u32(BigInt(0xca01f9dd) * BigInt(left) - BigInt(0x4973f715) * BigInt(right)); return u32(value ^ (value >>> 16)); };
const entropyWords = (entropy: bigint): readonly number[] => { const words: number[] = []; let remaining = entropy; do {
    words.push(u32(remaining));
    remaining >>= 32n;
} while (remaining > 0n); return words; };
const seedSequenceState = (entropy: bigint): readonly number[] => {
    const pool = [0, 0, 0, 0], words = entropyWords(entropy), state = { value: 0x43b0d7e5 };
    for (let index = 0; index < pool.length; index += 1)
        pool[index] = hashMix(words[index] ?? 0, state);
    for (let source = 0; source < pool.length; source += 1)
        for (let destination = 0; destination < pool.length; destination += 1)
            if (source !== destination)
                pool[destination] = mix(pool[destination]!, hashMix(pool[source]!, state));
    const output: number[] = [], outputState = { value: 0x8b51f9dd };
    for (let index = 0; index < 8; index += 1) {
        let value = u32(pool[index % pool.length]! ^ outputState.value);
        outputState.value = multiply32(outputState.value, 0x58f38ded);
        value = multiply32(value, outputState.value);
        output.push(u32(value ^ (value >>> 16)));
    }
    return Object.freeze(output);
};
const asUint64 = (words: readonly number[], index: number): bigint => BigInt(words[index]!) + (BigInt(words[index + 1]!) << 32n);
const asUint128BigEndianWords = (words: readonly number[], index: number): bigint => (asUint64(words, index) << 64n) + asUint64(words, index + 2);
const rotateRight64 = (value: bigint, amount: bigint): bigint => ((value >> amount) | (value << ((-amount) & 63n))) & ((1n << 64n) - 1n);
interface Pcg64State {
    readonly state: bigint;
    readonly increment: bigint;
}
const PCG64_MULTIPLIER = (2549297995355413924n << 64n) + 4865540595714422341n;
const pcgStep = (state: Pcg64State): Pcg64State => Object.freeze({ state: (state.state * PCG64_MULTIPLIER + state.increment) & MASK128, increment: state.increment });
const pcg64State = (seed: bigint): Pcg64State => {
    const words = seedSequenceState(seed), initialState = asUint128BigEndianWords(words, 0), sequence = asUint128BigEndianWords(words, 4), increment = ((sequence << 1n) | 1n) & MASK128;
    return pcgStep(Object.freeze({ state: (increment + initialState) & MASK128, increment }));
};
const pcgUniform = (state: Pcg64State): readonly [
    number,
    Pcg64State
] => {
    const next = pcgStep(state), high = next.state >> 64n, low = next.state & ((1n << 64n) - 1n), raw = rotateRight64(high ^ low, high >> 58n);
    return Object.freeze([Number(raw >> 11n) / 9007199254740992, next]);
};
type Schema = readonly (readonly [
    string,
    readonly number[]
])[];
const schemas = {
    P_CAP18: [["phiW", [3, 4, 18]], ["psiW", [3, 4, 18]], ["unaryW", [3, 2, 18]], ["pairW", [3, 3, 2, 18]], ["outB", [3, 2]]],
    T16: [["phiW", [3, 4, 16]], ["psiW", [3, 4, 16]], ["unaryW", [3, 2, 16]], ["pairW", [3, 3, 2, 16]], ["qW", [3, 2, 16]], ["outB", [3, 2]]],
    DS870: [["etaW", [3, 4, 4]], ["etaB", [3, 4]], ["hidden1W", [30, 14]], ["hidden1B", [14]], ["hidden2W", [14, 22]], ["hidden2B", [22]], ["outW", [22, 2]], ["outB", [2]]]
} as const satisfies Record<NativeS2SInitializationArm, Schema>;
const pythonName = (name: string): string => name.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
const size = (shape: readonly number[]): number => shape.reduce((total, dimension) => total * dimension, 1);
const descriptorSeed = (name: string, shape: readonly number[], seed: bigint): Either.Either<bigint, NativeS2SInitializationError> => {
    const payload = { name, schema_version: "hswm-swm0w-s2s-task-independent-zero-output-initialization/v1", seed, shape: [...shape] };
    if (!validNativeTaskJson(payload))
        return fail("CANONICAL_INVALID", "initialization descriptor is not canonical task JSON");
    const descriptor = createHash("sha256").update(renderNativeTaskJson(payload, "canonical"), "utf8").digest("hex");
    const digest = createHash("sha256").update("hswm-swm0w-s2s-training-initialization/v1\0", "utf8").update(descriptor, "ascii").digest();
    return Either.right(digest.readBigUInt64BE(0) << 64n | digest.readBigUInt64BE(8));
};
const randomNames = (arm: NativeS2SInitializationArm): readonly string[] => arm === "DS870" ? ["etaW", "hidden1W", "hidden2W"] : ["phiW", "psiW"];
const typedParameters = (arm: NativeS2SInitializationArm, values: Readonly<Record<string, readonly number[]>>): NativeS2SParameters => {
    const parameter = (name: string): readonly number[] => values[name]!;
    if (arm === "P_CAP18")
        return Object.freeze({ phiW: parameter("phiW"), psiW: parameter("psiW"), unaryW: parameter("unaryW"), pairW: parameter("pairW"), outB: parameter("outB") });
    if (arm === "T16")
        return Object.freeze({ phiW: parameter("phiW"), psiW: parameter("psiW"), unaryW: parameter("unaryW"), pairW: parameter("pairW"), qW: parameter("qW"), outB: parameter("outB") });
    return Object.freeze({ etaW: parameter("etaW"), etaB: parameter("etaB"), hidden1W: parameter("hidden1W"), hidden1B: parameter("hidden1B"), hidden2W: parameter("hidden2W"), hidden2B: parameter("hidden2B"), outW: parameter("outW"), outB: parameter("outB") });
};
export const initializeNativeS2STrainingParameters = (arm: unknown, seed: unknown): Either.Either<NativeS2SParameters, NativeS2SInitializationError> => {
    if (arm !== "P_CAP18" && arm !== "T16" && arm !== "DS870")
        return fail("ARM_INVALID", "unsupported S2S training arm");
    if (typeof seed !== "bigint" || seed < 0n || seed >= 2n ** 64n)
        return fail("SEED_INVALID", "seed must be an exact unsigned 64-bit integer");
    const output: Record<string, readonly number[]> = {}, randomized = randomNames(arm);
    for (const [name, shape] of schemas[arm]) {
        if (!randomized.includes(name)) {
            output[name] = Object.freeze(Array<number>(size(shape)).fill(0));
            continue;
        }
        const derived = descriptorSeed(pythonName(name), shape, seed);
        if (Either.isLeft(derived))
            return Either.left(derived.left);
        let state = pcg64State(derived.right);
        const limit = Math.sqrt(6 / (shape.at(-2)! + shape.at(-1)!));
        const values: number[] = [];
        for (let index = 0; index < size(shape); index += 1) {
            const next = pcgUniform(state);
            values.push(-limit + 2 * limit * next[0]);
            state = next[1];
        }
        output[name] = Object.freeze(values);
    }
    return Either.right(typedParameters(arm, Object.freeze(output)));
};
const validParameterValues = (values: unknown): values is readonly number[] => Array.isArray(values) && Array.from({ length: values.length }, (_, index) => Object.hasOwn(values, index) && typeof values[index] === "number" && Number.isFinite(values[index])).every(Boolean);
const parameterBytes = (values: unknown): Either.Either<Buffer, NativeS2SInitializationError> => {
    if (!validParameterValues(values))
        return fail("PARAMETERS_INVALID", "parameter values must be dense finite number arrays");
    const bytes = Buffer.alloc(values.length * 8);
    values.forEach((value, index) => bytes.writeDoubleLE(value, index * 8));
    return Either.right(bytes);
};
export const nativeS2SInitializationParameterSha256 = (values: unknown): Either.Either<string, NativeS2SInitializationError> => Either.map(parameterBytes(values), bytes => createHash("sha256").update(bytes).digest("hex"));
