/** Immutable, scalar reverse-mode port of swm0w_s2s_training.py (UNJUDGED engineering parity). */
import { Data, Either } from "effect";
import { nativeP1AccurateSum } from "./native-p1-gate-domain.js";
import type { NativeS2SDs870Parameters, NativeS2SPCap18Parameters, NativeS2ST16Parameters } from "./native-s2s-operator-domain.js";
import { forwardNativeS2SDs870, forwardNativeS2SPCap18, forwardNativeS2ST16 } from "./native-s2s-operator-domain.js";
export const NATIVE_S2S_TRAINING_SOURCE_SHA256 = "d84b8336d8bcbe89aeba7f2d2c915fd294b9ee24425e6092505069a74f9cba94" as const;
export const NATIVE_S2S_TRAINING_SCIENTIFIC_STATUS = "UNJUDGED_ENGINEERING_PARITY_ONLY" as const;
export type NativeS2STrainingArm = "P_CAP18" | "T16" | "DS870";
export type NativeS2SParameters = NativeS2SPCap18Parameters | NativeS2ST16Parameters | NativeS2SDs870Parameters;
export class NativeS2STrainingError extends Data.TaggedError("NativeS2STrainingError")<{
    readonly reason: "INPUT_INVALID" | "PARAMETERS_INVALID" | "NUMERIC_INVALID";
    readonly detail: string;
}> {
}
export interface NativeS2STrainingResult {
    readonly loss: number;
    readonly gradients: Readonly<Record<string, readonly number[]>>;
    readonly scientificStatus: typeof NATIVE_S2S_TRAINING_SCIENTIFIC_STATUS;
}
const left = (reason: NativeS2STrainingError["reason"], detail: string): Either.Either<never, NativeS2STrainingError> => Either.left(new NativeS2STrainingError({ reason, detail }));
const valid = (a: unknown, n: number): a is readonly number[] => Array.isArray(a) && a.length === n && Array.from({ length: n }, (_, i) => Object.hasOwn(a, i) && Number.isFinite(a[i])).every(Boolean);
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const shape = (arm: NativeS2STrainingArm): Readonly<Record<string, number>> => arm === "P_CAP18" ? { phiW: 216, psiW: 216, unaryW: 108, pairW: 324, outB: 6 } : arm === "T16" ? { phiW: 192, psiW: 192, unaryW: 96, pairW: 288, qW: 96, outB: 6 } : { etaW: 48, etaB: 12, hidden1W: 420, hidden1B: 14, hidden2W: 308, hidden2B: 22, outW: 44, outB: 2 };
type ParameterArrays = Readonly<Record<string, readonly number[]>>;
type GradientArrays = Record<string, number[]>;
const frozen = (x: number[]): readonly number[] => Object.freeze(x);
/** Calculates loss and handwritten reverse-mode gradients for flat N×3×2×4 tensors. */
export const lossAndGradientsNativeS2S = (arm: NativeS2STrainingArm, parameters: NativeS2SParameters, input: readonly number[], targets: readonly number[], weights: readonly number[]): Either.Either<NativeS2STrainingResult, NativeS2STrainingError> => {
    if (arm !== "P_CAP18" && arm !== "T16" && arm !== "DS870")
        return left("INPUT_INVALID", "arm must be P_CAP18, T16, or DS870");
    if (!Array.isArray(input) || !Array.isArray(targets) || !Array.isArray(weights) || !record(parameters))
        return left("INPUT_INVALID", "input, targets, weights, and parameters must be arrays or an object");
    const dims = shape(arm), p = parameters as ParameterArrays;
    if (input.length === 0 || input.length % 24 !== 0 || !valid(input, input.length) || !valid(targets, input.length / 2) || !valid(weights, 6) || weights.some(x => x <= 0))
        return left("INPUT_INVALID", "input, targets, and positive weights must be dense finite flat tensors");
    if (Object.keys(parameters).length !== Object.keys(dims).length || Object.entries(dims).some(([k, n]) => !valid(p[k], n)))
        return left("PARAMETERS_INVALID", "parameter schema, tensor shapes, or finite values are invalid");
    const g: GradientArrays = {};
    for (const [k, n] of Object.entries(dims))
        g[k] = Array<number>(n).fill(0);
    const N = input.length / 24;
    let weightedSquares = 0;
    const x = (n: number, r: number, m: number, d: number) => input[((n * 3 + r) * 2 + m) * 4 + d]!;
    for (let n = 0; n < N; n += 1) {
        const pred = Array<number>(12).fill(0), du = Array<number>(arm === "DS870" ? 0 : 3 * 2 * (arm === "P_CAP18" ? 18 : 16)).fill(0), de = Array<number>(du.length).fill(0);
        if (arm !== "DS870") {
            const h = arm === "P_CAP18" ? 18 : 16, get = (a: readonly number[], r: number, m: number, k: number) => a[(r * 2 + m) * h + k]!, u = (r: number, m: number, k: number) => get(du, r, m, k), e = (r: number, m: number, k: number) => get(de, r, m, k);
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let k = 0; k < h; k++)
                        for (let d = 0; d < 4; d++) {
                            du[(r * 2 + m) * h + k]! += x(n, r, m, d) * p["phiW"]![(r * 4 + d) * h + k]!;
                            de[(r * 2 + m) * h + k]! += x(n, r, m, d) * p["psiW"]![(r * 4 + d) * h + k]!;
                        }
            const gu = Array<number>(du.length).fill(0), ge = Array<number>(du.length).fill(0);
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let c = 0; c < 2; c++) {
                        const oi = (r * 2 + m) * 2 + c;
                        let z = p["outB"]![r * 2 + c]!;
                        for (let k = 0; k < h; k++) {
                            const uh = u(r, m, k);
                            z += uh * p["unaryW"]![(r * 2 + c) * h + k]!;
                            for (let s = 0; s < 3; s++) {
                                const v = s === r ? e(s, 1 - m, k) : e(s, 0, k) + e(s, 1, k);
                                z += uh * v * p["pairW"]![((r * 3 + s) * 2 + c) * h + k]!;
                            }
                        }
                        pred[oi] = z;
                    }
            if (arm === "T16")
                for (let r = 0; r < 3; r++)
                    for (let m = 0; m < 2; m++)
                        for (let c = 0; c < 2; c++)
                            for (let k = 0; k < h; k++) {
                                const vs = [0, 1, 2].map(s => s === r ? e(s, 1 - m, k) : e(s, 0, k) + e(s, 1, k));
                                pred[(r * 2 + m) * 2 + c]! += u(r, m, k) * vs[0]! * vs[1]! * vs[2]! * p["qW"]![(r * 2 + c) * h + k]!;
                            }
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let c = 0; c < 2; c++) {
                        const oi = (r * 2 + m) * 2 + c, der = (pred[oi]! - targets[n * 12 + oi]!) * weights[r * 2 + c]! / (6 * N);
                        weightedSquares += (pred[oi]! - targets[n * 12 + oi]!) * (pred[oi]! - targets[n * 12 + oi]!) * weights[r * 2 + c]!;
                        g["outB"]![r * 2 + c]! += der;
                        for (let k = 0; k < h; k++) {
                            const uh = u(r, m, k);
                            g["unaryW"]![(r * 2 + c) * h + k]! += der * uh;
                            gu[(r * 2 + m) * h + k]! += der * p["unaryW"]![(r * 2 + c) * h + k]!;
                            for (let s = 0; s < 3; s++) {
                                const v = s === r ? e(s, 1 - m, k) : e(s, 0, k) + e(s, 1, k), wi = ((r * 3 + s) * 2 + c) * h + k;
                                g["pairW"]![wi]! += der * uh * v;
                                gu[(r * 2 + m) * h + k]! += der * p["pairW"]![wi]! * v;
                                const q = der * p["pairW"]![wi]! * uh;
                                if (s === r)
                                    ge[(s * 2 + 1 - m) * h + k]! += q;
                                else {
                                    ge[(s * 2) * h + k]! += q;
                                    ge[(s * 2 + 1) * h + k]! += q;
                                }
                            }
                            if (arm === "T16") {
                                const vs = [0, 1, 2].map(s => s === r ? e(s, 1 - m, k) : e(s, 0, k) + e(s, 1, k)), wi = (r * 2 + c) * h + k, w = der * p["qW"]![wi]!;
                                g["qW"]![wi]! += der * uh * vs[0]! * vs[1]! * vs[2]!;
                                gu[(r * 2 + m) * h + k]! += w * vs[0]! * vs[1]! * vs[2]!;
                                for (let s = 0; s < 3; s++) {
                                    const q = w * uh * vs.filter((_, j) => j !== s).reduce((a, b) => a * b, 1);
                                    if (s === r)
                                        ge[(s * 2 + 1 - m) * h + k]! += q;
                                    else {
                                        ge[(s * 2) * h + k]! += q;
                                        ge[(s * 2 + 1) * h + k]! += q;
                                    }
                                }
                            }
                        }
                    }
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let k = 0; k < h; k++)
                        for (let d = 0; d < 4; d++) {
                            g["phiW"]![(r * 4 + d) * h + k]! += x(n, r, m, d) * gu[(r * 2 + m) * h + k]!;
                            g["psiW"]![(r * 4 + d) * h + k]! += x(n, r, m, d) * ge[(r * 2 + m) * h + k]!;
                        }
        }
        else {
            const eta = Array<number>(24).fill(0), dec = Array<number>(6 * 30).fill(0), h1 = Array<number>(6 * 14).fill(0), h2 = Array<number>(6 * 22).fill(0);
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let k = 0; k < 4; k++) {
                        let z = p["etaB"]![r * 4 + k]!;
                        for (let d = 0; d < 4; d++)
                            z += x(n, r, m, d) * p["etaW"]![(r * 4 + d) * 4 + k]!;
                        eta[(r * 2 + m) * 4 + k] = Math.tanh(z);
                    }
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++) {
                    const row = r * 2 + m;
                    for (let d = 0; d < 4; d++)
                        dec[row * 30 + d] = x(n, r, m, d);
                    for (let s = 0; s < 3; s++)
                        for (let f = 0; f < 8; f++)
                            dec[row * 30 + 4 + s * 8 + f] = (f < 4 ? x(n, s, 0, f) + x(n, s, 1, f) : eta[s * 8 + f - 4]! + eta[s * 8 + 4 + f - 4]!);
                    dec[row * 30 + 28] = r === 0 ? 1 : r === 2 ? -1 : 0;
                    dec[row * 30 + 29] = r === 1 ? 1 : r === 2 ? -1 : 0;
                    for (let j = 0; j < 14; j++) {
                        let z = p["hidden1B"]![j]!;
                        for (let f = 0; f < 30; f++)
                            z += dec[row * 30 + f]! * p["hidden1W"]![f * 14 + j]!;
                        h1[row * 14 + j] = Math.tanh(z);
                    }
                    for (let j = 0; j < 22; j++) {
                        let z = p["hidden2B"]![j]!;
                        for (let f = 0; f < 14; f++)
                            z += h1[row * 14 + f]! * p["hidden2W"]![f * 22 + j]!;
                        h2[row * 22 + j] = Math.tanh(z);
                    }
                    for (let c = 0; c < 2; c++) {
                        let z = p["outB"]![c]!;
                        for (let j = 0; j < 22; j++)
                            z += h2[row * 22 + j]! * p["outW"]![j * 2 + c]!;
                        pred[row * 2 + c] = z;
                    }
                }
            const gd = Array<number>(180).fill(0), gh1 = Array<number>(84).fill(0), gh2 = Array<number>(132).fill(0);
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let c = 0; c < 2; c++) {
                        const row = r * 2 + m, oi = row * 2 + c, res = pred[oi]! - targets[n * 12 + oi]!, der = res * weights[r * 2 + c]! / (6 * N);
                        weightedSquares += res * res * weights[r * 2 + c]!;
                        g["outB"]![c]! += der;
                        for (let j = 0; j < 22; j++) {
                            g["outW"]![j * 2 + c]! += h2[row * 22 + j]! * der;
                            gh2[row * 22 + j]! += der * p["outW"]![j * 2 + c]!;
                        }
                    }
            for (let row = 0; row < 6; row++)
                for (let j = 0; j < 22; j++) {
                    const z = gh2[row * 22 + j]! * (1 - h2[row * 22 + j]! * h2[row * 22 + j]!);
                    g["hidden2B"]![j]! += z;
                    for (let f = 0; f < 14; f++) {
                        g["hidden2W"]![f * 22 + j]! += h1[row * 14 + f]! * z;
                        gh1[row * 14 + f]! += z * p["hidden2W"]![f * 22 + j]!;
                    }
                }
            for (let row = 0; row < 6; row++)
                for (let j = 0; j < 14; j++) {
                    const z = gh1[row * 14 + j]! * (1 - h1[row * 14 + j]! * h1[row * 14 + j]!);
                    g["hidden1B"]![j]! += z;
                    for (let f = 0; f < 30; f++) {
                        g["hidden1W"]![f * 14 + j]! += dec[row * 30 + f]! * z;
                        gd[row * 30 + f]! += z * p["hidden1W"]![f * 14 + j]!;
                    }
                }
            for (let r = 0; r < 3; r++)
                for (let m = 0; m < 2; m++)
                    for (let k = 0; k < 4; k++) {
                        let q = 0;
                        for (let rr = 0; rr < 3; rr++)
                            for (let mm = 0; mm < 2; mm++)
                                q += gd[(rr * 2 + mm) * 30 + 4 + r * 8 + 4 + k]!;
                        q *= 1 - eta[(r * 2 + m) * 4 + k]! ** 2;
                        g["etaB"]![r * 4 + k]! += q;
                        for (let d = 0; d < 4; d++)
                            g["etaW"]![(r * 4 + d) * 4 + k]! += x(n, r, m, d) * q;
                    }
        }
    }
    const loss = weightedSquares / (12 * N);
    if (!Number.isFinite(loss) || Object.values(g).flat().some(v => !Number.isFinite(v)))
        return left("NUMERIC_INVALID", "loss or analytic gradient is non-finite");
    return Either.right(Object.freeze({ loss, gradients: Object.freeze(Object.fromEntries(Object.entries(g).map(([k, v]) => [k, frozen(v)]))), scientificStatus: NATIVE_S2S_TRAINING_SCIENTIFIC_STATUS }));
};
export const clipNativeS2SGradients = (gradients: Readonly<Record<string, readonly number[]>>, threshold: number): Either.Either<{
    readonly gradients: Readonly<Record<string, readonly number[]>>;
    readonly norm: number;
    readonly clipped: boolean;
}, NativeS2STrainingError> => {
    if (!record(gradients) || !Number.isFinite(threshold) || threshold <= 0 || Object.values(gradients).some(a => !Array.isArray(a) || !valid(a, a.length)))
        return left("INPUT_INVALID", "gradients and positive clipping threshold must be finite");
    const norm = Math.sqrt(nativeP1AccurateSum(Object.values(gradients).map(tensor => tensor.reduce((sum, value) => sum + value * value, 0))));
    if (!Number.isFinite(norm))
        return left("NUMERIC_INVALID", "global gradient norm is non-finite");
    const scale = norm > threshold ? threshold / norm : 1;
    return Either.right(Object.freeze({ gradients: Object.freeze(Object.fromEntries(Object.entries(gradients).map(([k, a]) => [k, frozen(a.map(v => v * scale))]))), norm, clipped: norm > threshold }));
};
/** Loss-only counterpart of Python `_loss_for_parameters`; gradients remain internal. */
export const lossForNativeS2SParameters = (arm: NativeS2STrainingArm, parameters: NativeS2SParameters, input: readonly number[], targets: readonly number[], weights: readonly number[]): Either.Either<number, NativeS2STrainingError> => {
    if (arm !== "P_CAP18" && arm !== "T16" && arm !== "DS870")
        return left("INPUT_INVALID", "arm must be P_CAP18, T16, or DS870");
    if (!Array.isArray(input) || !Array.isArray(targets) || !Array.isArray(weights) || !record(parameters))
        return left("INPUT_INVALID", "input, targets, weights, and parameters must be arrays or an object");
    const dims = shape(arm), p = parameters as ParameterArrays;
    if (input.length === 0 || input.length % 24 !== 0 || !valid(input, input.length) || !valid(targets, input.length / 2) || !valid(weights, 6) || weights.some(value => value <= 0) || Object.keys(parameters).length !== Object.keys(dims).length || Object.entries(dims).some(([key, length]) => !valid(p[key], length)))
        return left("INPUT_INVALID", "loss inputs must be dense finite tensors with a valid parameter schema");
    const count = input.length / 24;
    let weightedSquares = 0;
    for (let sample = 0; sample < count; sample += 1) {
        const presweep = input.slice(sample * 24, (sample + 1) * 24);
        const forward = arm === "P_CAP18" ? forwardNativeS2SPCap18(presweep, parameters as NativeS2SPCap18Parameters) : arm === "T16" ? forwardNativeS2ST16(presweep, parameters as NativeS2ST16Parameters) : forwardNativeS2SDs870(presweep, parameters as NativeS2SDs870Parameters);
        if (Either.isLeft(forward))
            return left(forward.left.reason === "OUTPUT_INVALID" ? "NUMERIC_INVALID" : forward.left.reason, "forward loss evaluation failed: " + forward.left.detail);
        for (let role = 0; role < 3; role += 1)
            for (let member = 0; member < 2; member += 1)
                for (let channel = 0; channel < 2; channel += 1) {
                    const residual = forward.right[role]![member]![channel]! - targets[sample * 12 + (role * 2 + member) * 2 + channel]!, term = residual * residual * weights[role * 2 + channel]!;
                    if (!Number.isFinite(term))
                        return left("NUMERIC_INVALID", "weighted loss is non-finite");
                    weightedSquares += term;
                }
    }
    const loss = weightedSquares / (12 * count);
    return Number.isFinite(loss) ? Either.right(loss) : left("NUMERIC_INVALID", "weighted loss is non-finite");
};
