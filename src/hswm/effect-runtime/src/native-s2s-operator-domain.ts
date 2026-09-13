/** Native deterministic P_CAP18 one-sweep forward projection; no training path. */
import { Data, Either } from "effect";
import { sumNativeS2SContiguousProducts } from "./native-s2s-contiguous-reduction-domain.js";
export const NATIVE_S2S_OPERATOR_SOURCE_SHA256 = "7b16eccc74059c6c6dd537ea219c458d7015eadf070d77e1c34ad75c2c828151" as const;
/** Source-bound architecture commitments used by the training receipt verifier. */
export const NATIVE_S2S_OPERATOR_ARCHITECTURE_RECEIPT_SHA256: Readonly<Record<"P_CAP18" | "T16" | "DS870", string>> = Object.freeze({ P_CAP18: "52bbfd8bcc1a2c6c420b0673c323d81da82e4475222a132d9bbabe8de3288001", T16: "65e6e27379793a7f483e8c34292ba060b60b89824822167e7483e03f7415ad29", DS870: "bff3df025fd4b8bc4e022334b105b63f2833d45a56fac11aeb4b1d0d6282831d" });
export class NativeS2SOperatorError extends Data.TaggedError("NativeS2SOperatorError")<{
    readonly reason: "INPUT_INVALID" | "PARAMETERS_INVALID" | "OUTPUT_INVALID";
    readonly detail: string;
}> {
}
export interface NativeS2SPCap18Parameters {
    readonly phiW: readonly number[];
    readonly psiW: readonly number[];
    readonly unaryW: readonly number[];
    readonly pairW: readonly number[];
    readonly outB: readonly number[];
}
export interface NativeS2ST16Parameters extends NativeS2SPCap18Parameters {
    readonly qW: readonly number[];
}
export interface NativeS2SDs870Parameters {
    readonly etaW: readonly number[];
    readonly etaB: readonly number[];
    readonly hidden1W: readonly number[];
    readonly hidden1B: readonly number[];
    readonly hidden2W: readonly number[];
    readonly hidden2B: readonly number[];
    readonly outW: readonly number[];
    readonly outB: readonly number[];
}
export type NativeS2SPCap18Output = readonly (readonly (readonly [
    number,
    number
])[])[];
const finite = (values: unknown, length: number): values is readonly number[] => Array.isArray(values) &&
    values.length === length &&
    Array.from({ length }, (_, index) => Object.hasOwn(values, index) && Number.isFinite(values[index])).every(Boolean);
const parameterRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fail = (reason: NativeS2SOperatorError["reason"], detail: string): Either.Either<never, NativeS2SOperatorError> => Either.left(new NativeS2SOperatorError({ reason, detail }));
/** Matches Python `_t_or_p_forward` for the P_CAP18 arm using ascending scalar loops. */
export const forwardNativeS2SPCap18 = (input: readonly number[], parameters: NativeS2SPCap18Parameters): Either.Either<NativeS2SPCap18Output, NativeS2SOperatorError> => {
    if (!finite(input, 24))
        return fail("INPUT_INVALID", "presweep must be one finite 3x2x4 tensor");
    if (!parameterRecord(parameters))
        return fail("PARAMETERS_INVALID", "P_CAP18 parameters must be an object of dense finite arrays");
    if (Object.keys(parameters).length !== 5 || !finite(parameters.phiW, 216) || !finite(parameters.psiW, 216) || !finite(parameters.unaryW, 108) || !finite(parameters.pairW, 324) || !finite(parameters.outB, 6))
        return fail("PARAMETERS_INVALID", "P_CAP18 parameter shapes or finite values are invalid");
    const at = (role: number, member: number, dimension: number): number => input[(role * 2 + member) * 4 + dimension]!;
    const dotInput = (weights: readonly number[], role: number, hidden: number): number => { let total = 0; for (let d = 0; d < 4; d += 1)
        total += at(role, member, d) * weights[(role * 4 + d) * 18 + hidden]!; return total; };
    let member = 0;
    const u = Array.from({ length: 3 }, () => Array.from({ length: 2 }, () => Array<number>(18).fill(0)));
    const encoded = Array.from({ length: 3 }, () => Array.from({ length: 2 }, () => Array<number>(18).fill(0)));
    for (let role = 0; role < 3; role += 1)
        for (member = 0; member < 2; member += 1)
            for (let h = 0; h < 18; h += 1) {
                u[role]![member]![h] = dotInput(parameters.phiW, role, h);
                encoded[role]![member]![h] = dotInput(parameters.psiW, role, h);
            }
    const output: (readonly [
        number,
        number
    ])[][] = [];
    for (let role = 0; role < 3; role += 1) {
        const roleRows: (readonly [
            number,
            number
        ])[] = [];
        for (member = 0; member < 2; member += 1) {
            const channels: number[] = [];
            for (let channel = 0; channel < 2; channel += 1) {
                let unary = 0, pair = 0;
                unary = sumNativeS2SContiguousProducts(18, h => u[role]![member]![h]! * parameters.unaryW[(role*2+channel)*18+h]!);
                for (let source = 0; source < 3; source++) pair += sumNativeS2SContiguousProducts(18, h => {
                    const v = source === role ? encoded[source]![1-member]![h]! : encoded[source]![0]![h]! + encoded[source]![1]![h]!;
                    return (u[role]![member]![h]!*v)*parameters.pairW[((role*3+source)*2+channel)*18+h]!;
                });
                const total = (unary + pair) + parameters.outB[role*2+channel]!;
                channels.push(total);
            }
            if (!channels.every(Number.isFinite))
                return fail("OUTPUT_INVALID", "forward produced a non-finite postsweep tensor");
            roleRows.push(Object.freeze([channels[0]!, channels[1]!] as const));
        }
        output.push(roleRows);
    }
    return Either.right(Object.freeze(output.map((row) => Object.freeze(row))));
};
export const forwardNativeS2ST16 = (input: readonly number[], parameters: NativeS2ST16Parameters): Either.Either<NativeS2SPCap18Output, NativeS2SOperatorError> => {
    if (!finite(input, 24))
        return fail("INPUT_INVALID", "presweep must be one finite 3x2x4 tensor");
    if (!parameterRecord(parameters))
        return fail("PARAMETERS_INVALID", "T16 parameters must be an object of dense finite arrays");
    if (Object.keys(parameters).length !== 6 || !finite(parameters.phiW, 192) || !finite(parameters.psiW, 192) || !finite(parameters.unaryW, 96) || !finite(parameters.pairW, 288) || !finite(parameters.qW, 96) || !finite(parameters.outB, 6))
        return fail("PARAMETERS_INVALID", "T16 parameter shapes or finite values are invalid");
    const at = (r: number, m: number, d: number) => input[(r * 2 + m) * 4 + d]!, dot = (weights: readonly number[], r: number, m: number, h: number) => { let x = 0; for (let d = 0; d < 4; d += 1)
        x += at(r, m, d) * weights[(r * 4 + d) * 16 + h]!; return x; };
    const u = Array.from({ length: 3 }, () => Array.from({ length: 2 }, () => Array<number>(16).fill(0))), e = Array.from({ length: 3 }, () => Array.from({ length: 2 }, () => Array<number>(16).fill(0)));
    for (let r = 0; r < 3; r += 1)
        for (let m = 0; m < 2; m += 1)
            for (let h = 0; h < 16; h += 1) {
                u[r]![m]![h] = dot(parameters.phiW, r, m, h);
                e[r]![m]![h] = dot(parameters.psiW, r, m, h);
            }
    const out: (readonly [
        number,
        number
    ])[][] = [];
    for (let r = 0; r < 3; r += 1) {
        const rows: (readonly [
            number,
            number
        ])[] = [];
        for (let m = 0; m < 2; m += 1) {
            const c: number[] = [];
            for (let ch = 0; ch < 2; ch += 1) {
                let unary = 0, pair = 0, q = 0;
                unary = sumNativeS2SContiguousProducts(16, h => u[r]![m]![h]! * parameters.unaryW[(r*2+ch)*16+h]!);
                for (let source = 0; source < 3; source++) pair += sumNativeS2SContiguousProducts(16, h => {
                    const v = source === r ? e[source]![1-m]![h]! : e[source]![0]![h]!+e[source]![1]![h]!;
                    return (u[r]![m]![h]!*v)*parameters.pairW[((r*3+source)*2+ch)*16+h]!;
                });
                q = sumNativeS2SContiguousProducts(16, h => {
                    const vs = [0,1,2].map(source => source === r ? e[source]![1-m]![h]! : e[source]![0]![h]!+e[source]![1]![h]!);
                    return (u[r]![m]![h]!*(vs[0]!*vs[1]!*vs[2]!))*parameters.qW[(r*2+ch)*16+h]!;
                });
                const total = ((unary + pair) + q) + parameters.outB[r*2+ch]!;
                c.push(total);
            }
            if (!c.every(Number.isFinite))
                return fail("OUTPUT_INVALID", "forward produced a non-finite postsweep tensor");
            rows.push(Object.freeze([c[0]!, c[1]!] as const));
        }
        out.push(rows);
    }
    return Either.right(Object.freeze(out.map(r => Object.freeze(r))));
};
export const forwardNativeS2SDs870 = (input: readonly number[], p: NativeS2SDs870Parameters): Either.Either<NativeS2SPCap18Output, NativeS2SOperatorError> => {
    if (!finite(input, 24))
        return fail("INPUT_INVALID", "presweep must be one finite 3x2x4 tensor");
    if (!parameterRecord(p))
        return fail("PARAMETERS_INVALID", "DS870 parameters must be an object of dense finite arrays");
    if (Object.keys(p).length !== 8 || !finite(p.etaW, 48) || !finite(p.etaB, 12) || !finite(p.hidden1W, 420) || !finite(p.hidden1B, 14) || !finite(p.hidden2W, 308) || !finite(p.hidden2B, 22) || !finite(p.outW, 44) || !finite(p.outB, 2))
        return fail("PARAMETERS_INVALID", "DS870 parameter shapes or finite values are invalid");
    const x = (r: number, m: number, d: number) => input[(r * 2 + m) * 4 + d]!, eta = (r: number, m: number, k: number) => { let z = 0; for (let d = 0; d < 4; d += 1)
        z += x(r, m, d) * p.etaW[(r * 4 + d) * 4 + k]!; return Math.tanh(z + p.etaB[r * 4 + k]!); }, out: (readonly [
        number,
        number
    ])[][] = [];
    for (let r = 0; r < 3; r += 1) {
        const rows: (readonly [
            number,
            number
        ])[] = [];
        for (let m = 0; m < 2; m += 1) {
            const f: number[] = [];
            for (let d = 0; d < 4; d += 1)
                f.push(x(r, m, d));
            for (let sr = 0; sr < 3; sr += 1) {
                for (let d = 0; d < 4; d += 1)
                    f.push(x(sr, 0, d) + x(sr, 1, d));
                for (let k = 0; k < 4; k += 1)
                    f.push(eta(sr, 0, k) + eta(sr, 1, k));
            }
            f.push(r === 0 ? 1 : r === 2 ? -1 : 0, r === 1 ? 1 : r === 2 ? -1 : 0);
            const h1 = Array.from({ length: 14 }, (_, h) => Math.tanh(p.hidden1B[h]! + f.reduce((z, v, i) => z + v * p.hidden1W[i * 14 + h]!, 0))), h2 = Array.from({ length: 22 }, (_, h) => Math.tanh(p.hidden2B[h]! + h1.reduce((z, v, i) => z + v * p.hidden2W[i * 22 + h]!, 0))), v: [
                number,
                number
            ] = [p.outB[0]! + h2.reduce((z, a, i) => z + a * p.outW[i * 2]!, 0), p.outB[1]! + h2.reduce((z, a, i) => z + a * p.outW[i * 2 + 1]!, 0)];
            if (!v.every(Number.isFinite))
                return fail("OUTPUT_INVALID", "forward produced a non-finite postsweep tensor");
            rows.push(Object.freeze(v));
        }
        out.push(rows);
    }
    return Either.right(Object.freeze(out.map(r => Object.freeze(r))));
};
