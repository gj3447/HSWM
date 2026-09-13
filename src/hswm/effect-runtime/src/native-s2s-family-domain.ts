/**
 * Native deterministic projection of the SWM-0W S2S V2 task family.
 * This is source-bound engineering parity only; it establishes neither a fit
 * nor an efficacy, bootstrap, or causal claim.
 */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { renderNativeTaskJson, validNativeTaskJson } from "./native-task-json-domain.js";
export const NATIVE_S2S_FAMILY_SOURCE_SHA256 = "e00a3365e89592038b66820f57655d28e908425e3586385fd2be1e407944e93a" as const;
export const NATIVE_S2S_FAMILY_SCIENTIFIC_STATUS = "UNJUDGED_TASK_FAMILY_ONLY" as const;
export const NATIVE_S2S_FAMILY_DEFINITION_VERSION = "hswm-swm0w-s2s-family-definition/v2" as const;
export const NATIVE_S2S_FAMILY_CERTIFICATE_VERSION = "hswm-swm0w-s2s-family-certificate/v2" as const;
export const NATIVE_S2S_STRUCTURAL_TARGET_VERSION = "hswm-swm0w-s2s-structural-target/v2" as const;
export const NATIVE_S2S_STRUCTURAL_TASK_VERSION = "hswm-swm0w-s2s-structural-task/v2" as const;
export const NATIVE_S2S_TASK_MANIFEST_VERSION = "hswm-swm0w-s2s-task/v2" as const;
export const NATIVE_S2S_TASK_BATCH_VERSION = "hswm-swm0w-s2s-task-batch/v2" as const;
export const NATIVE_S2S_TARGET_SCALE_EXPONENT = 19 as const;
export const NATIVE_S2S_ANALYTIC_NUMERATOR_BOUND = 288120 as const;
export const NATIVE_S2S_MAX_TASK_BATCH_SIZE = 4096 as const;
const FIELD_ORDER = 5;
const GAIN_LEVELS = Object.freeze([8, 9, 10, 11, 12, 13, 14, 15] as const);
const GAIN_ORDER: readonly (readonly [
    number,
    number,
    number
])[] = Object.freeze(Array.from({ length: 3 }, (_, role) => Array.from({ length: 2 }, (_, channel) => Array.from({ length: 2 }, (_, rank) => Object.freeze([role, channel, rank] as const))).flat()).flat());
const FACTOR_FRAME = Object.freeze([Object.freeze([-2, -1, 0, 1, 2]), Object.freeze([0, 3, -4, -1, 2]), Object.freeze([7, -7, -6, 5, 1]), Object.freeze([3, -3, 2, -7, 5])]);
const ROLE_CYCLES = Object.freeze([Object.freeze([1, 2, 0]), Object.freeze([2, 0, 1])]);
const DOMAIN = Object.freeze({
    seed: "hswm-swm0w-s2s-family-external-seed/v2\0",
    gain: "hswm-swm0w-s2s-family-gain-draw/v2\0",
    splitQ: "hswm-swm0w-s2s-family-split-q-draw/v2\0",
    allocation: "hswm-swm0w-s2s-family-split-allocation-draw/v2\0"
} as const);
export type NativeS2SSplit = "train" | "dev" | "test";
export type NativeS2SRawValues = readonly [
    number,
    number,
    number,
    number,
    number,
    number
];
export type NativeS2SFamilyErrorReason = "BATCH_INVALID" | "CANONICAL_INVALID" | "DRAW_INDEX_INVALID" | "RAW_VALUES_INVALID" | "SEED_INVALID" | "TASK_INVALID";
export class NativeS2SFamilyError extends Data.TaggedError("NativeS2SFamilyError")<{
    readonly reason: NativeS2SFamilyErrorReason;
    readonly detail: string;
}> {
}
const fail = (reason: NativeS2SFamilyErrorReason, detail: string): Either.Either<never, NativeS2SFamilyError> => Either.left(new NativeS2SFamilyError({ reason, detail }));
const frozen = <T>(value: T): T => Object.freeze(value);
type DeepReadonly<T> = T extends object ? {
    readonly [Key in keyof T]: DeepReadonly<T[Key]>;
} : T;
const deepFrozen = <T>(value: T): DeepReadonly<T> => {
    if (value !== null && typeof value === "object") {
        for (const child of Object.values(value))
            deepFrozen(child);
        Object.freeze(value);
    }
    return value as DeepReadonly<T>;
};
const validZ5 = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0 && value < FIELD_ORDER;
const validRaw = (value: unknown): value is NativeS2SRawValues => Array.isArray(value) && value.length === 6 && Array.from({ length: 6 }, (_, index) => Object.hasOwn(value, index) && validZ5(value[index])).every(Boolean);
const sha = (value: unknown): Either.Either<string, NativeS2SFamilyError> => validNativeTaskJson(value)
    ? Either.right(createHash("sha256").update(renderNativeTaskJson(value, "canonical"), "utf8").digest("hex"))
    : fail("CANONICAL_INVALID", "canonical task-family payload contains an unsupported value");
const hex = (value: string): string => Buffer.from(value, "utf8").toString("hex");
const xof = (domain: string, seed: Uint8Array, index: bigint, outputLength: number): Uint8Array => {
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(seed.length));
    const draw = Buffer.alloc(8);
    draw.writeBigUInt64BE(index);
    return createHash("shake256", { outputLength }).update(domain).update(length).update(seed).update(draw).digest();
};
type Allocation = readonly (readonly [
    NativeS2SSplit,
    readonly number[]
])[];
const allocationTable = (): readonly Allocation[] => {
    const entries: Allocation[] = [];
    for (let dev = 0; dev < FIELD_ORDER; dev += 1) {
        const remaining = Array.from({ length: FIELD_ORDER }, (_, value) => value).filter(value => value !== dev);
        for (let first = 0; first < remaining.length; first += 1)
            for (let second = first + 1; second < remaining.length; second += 1) {
                const train = frozen([remaining[first]!, remaining[second]!]);
                entries.push(frozen([frozen(["train", train]), frozen(["dev", frozen([dev])]), frozen(["test", frozen(remaining.filter(value => !train.includes(value)))])]));
            }
    }
    return frozen(entries);
};
export const NATIVE_S2S_SPLIT_ALLOCATIONS = allocationTable();
export const NATIVE_S2S_SPLIT_COEFFICIENTS: readonly (readonly [
    number,
    number,
    number
])[] = frozen(Array.from({ length: 4 }, (_, q1) => Array.from({ length: 4 }, (_, q2) => frozen([1, q1 + 1, q2 + 1] as const))).flat() as readonly (readonly [
    number,
    number,
    number
])[]);
type Gains = readonly [
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number
];
export interface NativeS2STask {
    readonly seedCommitmentSha256: string;
    readonly drawIndex: bigint;
    readonly rankGains: Gains;
    readonly splitCoefficients: readonly [
        number,
        number,
        number
    ];
    readonly splitResidues: Allocation;
    readonly familyDefinitionSha256: string;
    readonly familyCertificateSha256: string;
    readonly structuralTargetSha256: string;
    readonly structuralTaskSha256: string;
    readonly manifestSha256: string;
}
export interface NativeS2SCase {
    readonly taskManifestSha256: string;
    readonly split: NativeS2SSplit;
    readonly targetNumerators: readonly (readonly [
        number,
        number
    ])[];
    readonly targetFloats: readonly (readonly [
        number,
        number
    ])[];
    readonly rawValues: NativeS2SRawValues;
}
export interface NativeS2STaskBatch {
    readonly seedCommitmentSha256: string;
    readonly requestedCount: number;
    readonly tasks: readonly NativeS2STask[];
    readonly duplicateStructuralTargetDraws: readonly (readonly [
        number,
        number
    ])[];
    readonly duplicateStructuralTaskDraws: readonly (readonly [
        number,
        number
    ])[];
    readonly batchSha256: string;
}
const factor = (kind: "P" | "T", role: number, channel: number, rank: number, value: number): number => FACTOR_FRAME[((role + channel + rank + (kind === "P" ? 2 : 0)) % 4)]![value]!;
const gainEntries = (gains: Gains): readonly {
    readonly channel: string;
    readonly gain: number;
    readonly rank: number;
    readonly role: string;
}[] => frozen(GAIN_ORDER.map(([role, channel, rank], index) => frozen({ channel: `c${channel}`, gain: gains[index]!, rank, role: `r${role}` })));
const splitPayload = (coefficients: readonly number[], residues: Allocation) => ({ coefficients: [...coefficients], residues: Object.fromEntries(residues.map(([split, values]) => [split, [...values]])) });
const baseFactorTables = () => {
    const entries: {
        readonly key: string;
        readonly values: readonly number[];
    }[] = [];
    for (const kind of ["P", "T"] as const)
        for (let role = 0; role < 3; role += 1)
            for (let channel = 0; channel < 2; channel += 1)
                for (let rank = 0; rank < 2; rank += 1)
                    entries.push({ key: kind + ":r" + role + ":c" + channel + ":k" + rank, values: [...FACTOR_FRAME[(role + channel + rank + (kind === "P" ? 2 : 0)) % 4]!] });
    return entries;
};
const familyDefinitionPayload = () => ({ analytic_numerator_bound: NATIVE_S2S_ANALYTIC_NUMERATOR_BOUND, base_factor_tables: baseFactorTables(), factor_frame: FACTOR_FRAME.map(row => [...row]), factor_gram_diagonal: [10, 30, 160, 96], gain_domain: { gain_order: GAIN_ORDER.map(value => [...value]), reference_gain: 8, reference_gain_index: 0, remaining_gain_levels: [...GAIN_LEVELS], target_population_size: 8 ** 11 }, inference_boundary: "TASK_BOOTSTRAP_IS_PROTOCOL_LEVEL_AND_CONDITIONAL_ON_THIS_GENERATOR", sampling_scope: "INDEXED_PSEUDORANDOM_WITH_REPLACEMENT_FROM_ONE_FIXED_FEATURE_FRAME", schema_version: NATIVE_S2S_FAMILY_DEFINITION_VERSION, seed_generator: { allocation_draw: { accepted_byte_range: [0, 239], domain_hex: hex(DOMAIN.allocation), mapping: "ACCEPTED_BYTE_MOD_30", rejection_byte_budget: 4096, rejected_byte_range: [240, 255], xof: "SHAKE256" }, behavior_vectors: { draws: [{ allocation_index: 2, draw_index: 0, rank_gains: [8, 10, 14, 13, 15, 12, 13, 8, 12, 13, 15, 12], split_coefficients: [1, 2, 2] }, { allocation_index: 22, draw_index: 1, rank_gains: [8, 10, 14, 9, 13, 8, 11, 10, 9, 14, 15, 8], split_coefficients: [1, 4, 3] }, { allocation_index: 6, draw_index: 18446744073709551615n, rank_gains: [8, 15, 13, 9, 11, 11, 14, 13, 9, 8, 10, 10], split_coefficients: [1, 3, 1] }], external_seed_hex: "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f", seed_commitment_sha256: "f67ce7e55e476ffd428ce1bfd27a7dc03fe37edb2d2d2655258f34e15e7b52f5" }, duplicate_semantics: { comparison_keys: ["structural_target_sha256", "structural_task_sha256"], record: "(LATER_DRAW_INDEX,FIRST_EARLIER_EQUAL_DRAW_INDEX)", sampling_action: "RETAIN_DRAW_NEVER_SKIP_NEVER_REROLL" }, gain_draw: { domain_hex: hex(DOMAIN.gain), mapping: "FIRST_33_OF_40_XOF_BITS_AS_ELEVEN_MSB_FIRST_BASE8_DIGITS", xof: "SHAKE256" }, indexed_draw_preimage_framing: ["LITERAL_DOMAIN_BYTES", "UINT64_BE_EXTERNAL_SEED_LENGTH", "EXTERNAL_SEED_BYTES", "UINT64_BE_DRAW_INDEX"], maximum_batch_size: 4096, minimum_external_seed_bytes: 32, seed_commitment: { domain_hex: hex(DOMAIN.seed), hash: "SHA256", preimage_framing: ["LITERAL_DOMAIN_BYTES", "UINT64_BE_EXTERNAL_SEED_LENGTH", "EXTERNAL_SEED_BYTES"] }, split_allocation_table_ordered: NATIVE_S2S_SPLIT_ALLOCATIONS.map(allocation => allocation.map(([split, values]) => [split, [...values]])), split_coefficient_draw: { domain_hex: hex(DOMAIN.splitQ), mapping: "FIRST_4_XOF_BITS_AS_TWO_MSB_FIRST_BASE4_DIGITS_PLUS_ONE", xof: "SHAKE256" }, split_coefficient_table_ordered: NATIVE_S2S_SPLIT_COEFFICIENTS.map(values => [...values]), with_replacement: true }, scientific_status: NATIVE_S2S_FAMILY_SCIENTIFIC_STATUS, split_domain: { allocation_count: 30, coefficient_count: 16, coefficient_rule: "q=(1,q1,q2), q1,q2 in F5\\{0}", population_size: 480, residue_cardinalities: { dev: 1, test: 2, train: 2 } }, symmetry: "WITHIN_ROLE_MEMBER_GROUP_S2_CUBED", target_formula: "RECIPIENT_CONDITIONED_SET_FACTORIZED_RANK_2_WITH_GAIN_ON_P", target_rank: 2, target_scale_exponent: 19 });
export const NATIVE_S2S_FAMILY_DEFINITION_SHA256 = "9eea937e0a40511b1fd035e048a6ce6ce4c97898a5eafb86176f4d67059a413b" as const;
const familyCertificatePayload = () => ({ analytic_numerator_bound: 288120, broadcast_damage_minimum: { denominator: 4509001, numerator: 2027528 }, certified_broadcast_floor: { denominator: 5, numerator: 2 }, certified_role_cycle_floor: { denominator: 5, numerator: 4 }, checks: ["CENTERING", "EXACT_RANK_2", "S2_CUBED_EQUIVARIANCE", "RECIPIENT_STAR_ORTHOGONALITY", "ONE_TO_FIVE_COORDINATE_SPLIT_BALANCE", "BROADCAST_AND_BOTH_ROLE_CYCLE_DAMAGE"], exact_minima_scope: "PRECOMPUTED_EXACT_FAMILY_MATH_AUDIT_CONSTANTS", family_definition_sha256: NATIVE_S2S_FAMILY_DEFINITION_SHA256, role_cycle_damage_minima: [{ cycle: [...ROLE_CYCLES[0]!], denominator: 416884981, numerator: 420960389 }, { cycle: [...ROLE_CYCLES[1]!], denominator: 16617375, numerator: 17109007 }], schema_version: NATIVE_S2S_FAMILY_CERTIFICATE_VERSION, scientific_status: NATIVE_S2S_FAMILY_SCIENTIFIC_STATUS, universal_floor_proof: "EXACT_INTEGER_SYLVESTER_5N_MINUS_4D_POSITIVE_DEFINITE" });
export const NATIVE_S2S_FAMILY_CERTIFICATE_SHA256 = "a27049ad345be37007dc3099aafa58f957ee851619f9de55aaac69b3589c2329" as const;
export const nativeS2SFamilyDefinitionPayload = () => deepFrozen(familyDefinitionPayload());
export const nativeS2SFamilyCertificatePayload = () => deepFrozen(familyCertificatePayload());
const seedCommitment = (seed: Uint8Array): string => { const length = Buffer.alloc(8); length.writeBigUInt64BE(BigInt(seed.length)); return createHash("sha256").update(DOMAIN.seed).update(length).update(seed).digest("hex"); };
const deriveGains = (seed: Uint8Array, index: bigint): Gains => { const value = BigInt(`0x${Buffer.from(xof(DOMAIN.gain, seed, index, 5)).toString("hex")}`) >> 7n; return frozen([8, ...Array.from({ length: 11 }, (_, shift) => 8 + Number((value >> BigInt(3 * (10 - shift))) & 7n))] as unknown as Gains); };
const deriveCoefficients = (seed: Uint8Array, index: bigint): readonly [
    number,
    number,
    number
] => { const value = xof(DOMAIN.splitQ, seed, index, 1)[0]! >> 4; return frozen([1, 1 + (value >> 2), 1 + (value & 3)] as const); };
const deriveAllocation = (seed: Uint8Array, index: bigint): Either.Either<Allocation, NativeS2SFamilyError> => {
    for (let offset = 0; offset < 4096; offset += 1) {
        const candidate = xof(DOMAIN.allocation, seed, index, offset + 1)[offset]!;
        if (candidate < 240)
            return Either.right(NATIVE_S2S_SPLIT_ALLOCATIONS[candidate % 30]!);
    }
    return fail("TASK_INVALID", "allocation XOF rejection budget exhausted");
};
const structuralTargetPayload = (gains: Gains) => ({ family_definition_sha256: NATIVE_S2S_FAMILY_DEFINITION_SHA256, rank_gains: gainEntries(gains), schema_version: NATIVE_S2S_STRUCTURAL_TARGET_VERSION });
const structuralTaskPayload = (target: string, coefficients: readonly number[], residues: Allocation) => ({ schema_version: NATIVE_S2S_STRUCTURAL_TASK_VERSION, split: splitPayload(coefficients, residues), structural_target_sha256: target });
const manifestPayload = (task: Omit<NativeS2STask, "manifestSha256">) => ({ draw_index: task.drawIndex, family_certificate_sha256: NATIVE_S2S_FAMILY_CERTIFICATE_SHA256, family_definition_sha256: NATIVE_S2S_FAMILY_DEFINITION_SHA256, rank_gains: gainEntries(task.rankGains), schema_version: NATIVE_S2S_TASK_MANIFEST_VERSION, seed_commitment_sha256: task.seedCommitmentSha256, split: splitPayload(task.splitCoefficients, task.splitResidues), structural_target_sha256: task.structuralTargetSha256, structural_task_sha256: task.structuralTaskSha256 });
export const nativeS2STaskManifestPayload = (task: unknown) => validateNativeS2STask(task).pipe(Either.map(value => deepFrozen(manifestPayload(value))));
const exactSha256 = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
const dense = (value: readonly unknown[]): boolean => Array.from({ length: value.length }, (_, index) => Object.hasOwn(value, index)).every(Boolean);
const sameNumbers = (left: unknown, right: readonly number[]): boolean => Array.isArray(left) && dense(left) && left.length === right.length && left.every((value, index) => typeof value === "number" && Number.isInteger(value) && value === right[index]);
const sameAllocation = (candidate: unknown): candidate is Allocation => Array.isArray(candidate) && dense(candidate) && NATIVE_S2S_SPLIT_ALLOCATIONS.some(allocation => candidate.length === allocation.length && candidate.every((entry, index) => Array.isArray(entry) && dense(entry) && entry.length === 2 && entry[0] === allocation[index]![0] && sameNumbers(entry[1], allocation[index]![1])));
const immutableData = (value: unknown, depth = 0): boolean => {
    if (value === null || typeof value !== "object")
        return ["string", "number", "bigint", "boolean"].includes(typeof value);
    if (depth > 8 || !Object.isFrozen(value) || (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value))))
        return false;
    return Object.values(Object.getOwnPropertyDescriptors(value)).every(descriptor => Object.hasOwn(descriptor, "value") && immutableData(descriptor.value, depth + 1));
};
export const validateNativeS2STask = (candidate: unknown): Either.Either<NativeS2STask, NativeS2SFamilyError> => {
    if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate) || !immutableData(candidate))
        return fail("TASK_INVALID", "task requires one immutable exact native task record");
    const record = candidate as Readonly<Record<string, unknown>>;
    const keys = Object.keys(record).sort();
    const expectedKeys = ["drawIndex", "familyCertificateSha256", "familyDefinitionSha256", "manifestSha256", "rankGains", "seedCommitmentSha256", "splitCoefficients", "splitResidues", "structuralTargetSha256", "structuralTaskSha256"];
    if (keys.length !== expectedKeys.length || keys.some((key, index) => key !== expectedKeys[index]))
        return fail("TASK_INVALID", "task requires exactly the native task fields");
    if (!exactSha256(record["seedCommitmentSha256"]) || !exactSha256(record["familyDefinitionSha256"]) || !exactSha256(record["familyCertificateSha256"]) || !exactSha256(record["structuralTargetSha256"]) || !exactSha256(record["structuralTaskSha256"]) || !exactSha256(record["manifestSha256"]) || typeof record["drawIndex"] !== "bigint" || record["drawIndex"] < 0n || record["drawIndex"] >= 2n ** 64n)
        return fail("TASK_INVALID", "task field types are invalid");
    if (!Array.isArray(record["rankGains"]) || !dense(record["rankGains"]) || !Object.isFrozen(record["rankGains"]) || record["rankGains"].length !== 12 || record["rankGains"][0] !== 8 || record["rankGains"].some((gain, index) => typeof gain !== "number" || !Number.isInteger(gain) || (index > 0 && (gain < 8 || gain > 15))))
        return fail("TASK_INVALID", "rank gains require fixed leading 8 and eleven exact integers in 8..15");
    if (!Array.isArray(record["splitCoefficients"]) || !Object.isFrozen(record["splitCoefficients"]) || !NATIVE_S2S_SPLIT_COEFFICIENTS.some(coefficients => sameNumbers(record["splitCoefficients"], coefficients)))
        return fail("TASK_INVALID", "split coefficients must be one normalized family member");
    if (!sameAllocation(record["splitResidues"]) || !Object.isFrozen(record["splitResidues"]) || record["splitResidues"].some(entry => !Object.isFrozen(entry) || !Object.isFrozen(entry[1])))
        return fail("TASK_INVALID", "split residues must be one canonical labeled allocation");
    const task = record as unknown as NativeS2STask;
    if (task.familyDefinitionSha256 !== NATIVE_S2S_FAMILY_DEFINITION_SHA256 || task.familyCertificateSha256 !== NATIVE_S2S_FAMILY_CERTIFICATE_SHA256)
        return fail("TASK_INVALID", "task family commitment drifted");
    const target = sha(structuralTargetPayload(task.rankGains));
    if (Either.isLeft(target) || task.structuralTargetSha256 !== target.right)
        return fail("TASK_INVALID", "structural target SHA does not match");
    const structural = sha(structuralTaskPayload(target.right, task.splitCoefficients, task.splitResidues));
    if (Either.isLeft(structural) || task.structuralTaskSha256 !== structural.right)
        return fail("TASK_INVALID", "structural task SHA does not match");
    const manifest = sha(manifestPayload(task));
    if (Either.isLeft(manifest) || task.manifestSha256 !== manifest.right)
        return fail("TASK_INVALID", "task manifest SHA does not match");
    return Either.right(task);
};
export const generateNativeS2STask = (seed: unknown, drawIndex: unknown = 0n): Either.Either<NativeS2STask, NativeS2SFamilyError> => {
    if (!(seed instanceof Uint8Array) || seed.length < 32)
        return fail("SEED_INVALID", "external seed must be exact bytes with at least 32 bytes");
    if (typeof drawIndex !== "bigint" || drawIndex < 0n || drawIndex >= 2n ** 64n)
        return fail("DRAW_INDEX_INVALID", "draw index must be an exact unsigned 64-bit integer");
    const gains = deriveGains(seed, drawIndex), coefficients = deriveCoefficients(seed, drawIndex), allocation = deriveAllocation(seed, drawIndex);
    if (Either.isLeft(allocation))
        return Either.left(allocation.left);
    const residues = allocation.right;
    const target = sha(structuralTargetPayload(gains));
    if (Either.isLeft(target))
        return Either.left(target.left);
    const task = sha(structuralTaskPayload(target.right, coefficients, residues));
    if (Either.isLeft(task))
        return Either.left(task.left);
    const unsigned = frozen({ seedCommitmentSha256: seedCommitment(seed), drawIndex, rankGains: gains, splitCoefficients: coefficients, splitResidues: residues, familyDefinitionSha256: NATIVE_S2S_FAMILY_DEFINITION_SHA256, familyCertificateSha256: NATIVE_S2S_FAMILY_CERTIFICATE_SHA256, structuralTargetSha256: target.right, structuralTaskSha256: task.right });
    const manifest = sha(manifestPayload(unsigned));
    return Either.isLeft(manifest) ? Either.left(manifest.left) : Either.right(frozen({ ...unsigned, manifestSha256: manifest.right }));
};
/** Compile once only after the entire immutable task and its hashes validate. */
export const compileNativeS2STaskEvaluator = (task: unknown) => validateNativeS2STask(task).pipe(Either.map(validTask => (candidate: unknown) => evaluateCaseForValidatedTask(validTask, candidate)));
export const evaluateNativeS2STaskCase = (task: unknown, candidate: unknown): Either.Either<NativeS2SCase, NativeS2SFamilyError> => compileNativeS2STaskEvaluator(task).pipe(Either.flatMap(evaluate => evaluate(candidate)));
const evaluateCaseForValidatedTask = (validTask: NativeS2STask, candidate: unknown): Either.Either<NativeS2SCase, NativeS2SFamilyError> => {
    if (!validRaw(candidate))
        return fail("RAW_VALUES_INVALID", "raw values must be an immutable exact Z5 six-tuple");
    const rawValues = frozen([...candidate] as unknown as NativeS2SRawValues), syndrome = rawValues.reduce((total, value, index) => total + validTask.splitCoefficients[Math.floor(index / 2)]! * value, 0) % 5;
    const found = validTask.splitResidues.find(([, residues]) => residues.includes(syndrome));
    if (found === undefined)
        return fail("TASK_INVALID", "canonical split residues must partition F5");
    const rows: (readonly [
        number,
        number
    ])[] = [];
    for (let role = 0; role < 3; role += 1)
        for (let member = 0; member < 2; member += 1) {
            const values: number[] = [];
            for (let channel = 0; channel < 2; channel += 1) {
                let total = 0;
                for (let rank = 0; rank < 2; rank += 1) {
                    let value = validTask.rankGains[4 * role + 2 * channel + rank]! * factor("P", role, channel, rank, rawValues[2 * role + member]!) * factor("T", role, channel, rank, rawValues[2 * role + 1 - member]!);
                    for (let source = 0; source < 3; source += 1)
                        if (source !== role)
                            value *= factor("T", source, channel, rank, rawValues[2 * source]!) + factor("T", source, channel, rank, rawValues[2 * source + 1]!);
                    total += value;
                }
                values.push(total);
            }
            rows.push(frozen([values[0]!, values[1]!] as const));
        }
    if (rows.some(row => row.some(value => Math.abs(value) > NATIVE_S2S_ANALYTIC_NUMERATOR_BOUND)))
        return fail("TASK_INVALID", "case target exceeds the analytic bound");
    return Either.right(frozen({ taskManifestSha256: validTask.manifestSha256, rawValues, split: found[0], targetNumerators: frozen(rows), targetFloats: frozen(rows.map(row => frozen([row[0] / 2 ** 19, row[1] / 2 ** 19] as const))) }));
};
const duplicates = (tasks: readonly NativeS2STask[], key: "structuralTargetSha256" | "structuralTaskSha256"): readonly (readonly [
    number,
    number
])[] => {
    const seen = new Map<string, number>(), output: (readonly [
        number,
        number
    ])[] = [];
    tasks.forEach((task, index) => {
        const prior = seen.get(task[key]);
        if (prior === undefined)
            seen.set(task[key], index);
        else
            output.push(frozen([index, prior] as const));
    });
    return frozen(output);
};
export const generateNativeS2STaskBatch = (seed: unknown, count: unknown): Either.Either<NativeS2STaskBatch, NativeS2SFamilyError> => {
    if (typeof count !== "number" || !Number.isInteger(count) || count < 1 || count > NATIVE_S2S_MAX_TASK_BATCH_SIZE)
        return fail("BATCH_INVALID", "count must be a positive exact integer at most 4096");
    const tasks: NativeS2STask[] = [];
    for (let index = 0; index < count; index += 1) {
        const task = generateNativeS2STask(seed, BigInt(index));
        if (Either.isLeft(task))
            return Either.left(task.left);
        tasks.push(task.right);
    }
    return assembleNativeS2STaskBatch(tasks);
};
/** Structural batch admission; a seed commitment alone does not prove a seed draw. */
export const assembleNativeS2STaskBatch = (candidate: unknown): Either.Either<NativeS2STaskBatch, NativeS2SFamilyError> => {
    if (!Array.isArray(candidate) || !dense(candidate) || candidate.length < 1 || candidate.length > NATIVE_S2S_MAX_TASK_BATCH_SIZE)
        return fail("BATCH_INVALID", "batch must retain 1..4096 indexed tasks");
    const validated = Either.all(candidate.map(validateNativeS2STask));
    if (Either.isLeft(validated))
        return Either.left(validated.left);
    const tasks = validated.right, count = tasks.length;
    if (tasks.some((task, index) => task.drawIndex !== BigInt(index) || task.seedCommitmentSha256 !== tasks[0]!.seedCommitmentSha256))
        return fail("BATCH_INVALID", "batch tasks must preserve their indices and seed commitment");
    const targetDuplicates = duplicates(tasks, "structuralTargetSha256"), taskDuplicates = duplicates(tasks, "structuralTaskSha256"), commitment = tasks[0]!.seedCommitmentSha256;
    const payload = { duplicate_structural_target_draws: targetDuplicates.map(pair => [...pair]), duplicate_structural_task_draws: taskDuplicates.map(pair => [...pair]), requested_count: count, schema_version: NATIVE_S2S_TASK_BATCH_VERSION, seed_commitment_sha256: commitment, task_manifest_sha256s: tasks.map(task => task.manifestSha256) };
    const batch = sha(payload);
    return Either.isLeft(batch) ? Either.left(batch.left) : Either.right(frozen({ seedCommitmentSha256: commitment, requestedCount: count, tasks: frozen(tasks), duplicateStructuralTargetDraws: targetDuplicates, duplicateStructuralTaskDraws: taskDuplicates, batchSha256: batch.right }));
};
