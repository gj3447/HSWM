/** Offline verifier and judge for the frozen PROM-9 F1 suite.  This is an
 * evidence reader: it neither executes an arm nor makes an efficacy claim. */
import { Data, Either } from "effect";
import { canonicalNativeProm9Sha256 } from "./native-prom9-ports-domain.js";
import { verifyNativeProm9RunReceipt } from "./native-prom9-receipt-domain.js";
import { isTaskNumber, nativeTaskFloat, taskJsonRecord, taskNumberIsFloat, taskNumberValue, snapshotNativeTaskJson, taskTextCompare, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { nativePythonMt19937InitialState, nativePythonRandrange } from "./native-python-mt19937-domain.js";
import { pythonJsonEqual, pythonJsonInt, pythonJsonNormalizeAnswer, pythonJsonStrip } from "./native-python-json-semantics-domain.js";
import { pythonJsonString } from "./native-python-string-domain.js";
export const NATIVE_PROM9_F1_SUITE_SCHEMA = "hswm-prom9-f1-suite/v2" as const;
export const NATIVE_PROM9_F1_GOLD_SCHEMA = "hswm-prom9-f1-gold/v1" as const;
export const NATIVE_PROM9_F1_JUDGMENT_SCHEMA = "hswm-prom9-f1-judgment/v1" as const;
export const NATIVE_PROM9_F1_ARMS = Object.freeze(["typed_hswm_three_function_network", "flat_single_llm_three_call_workflow", "vector_memory_three_call_workflow", "typed_network_role_removed_schema_preserving_null", "typed_network_with_role_instructions_shuffled_but_ports_preserved"] as const);
type Arm = typeof NATIVE_PROM9_F1_ARMS[number];
const FUNCTIONS = Object.freeze(["QF_QUERY_COMPILER", "BF_BOND_PROPOSER", "AF_ANSWER_SYNTHESIZER"] as const);
const sha256 = /^[0-9a-f]{64}$/;
export class NativeProm9F1Error extends Data.TaggedError("NativeProm9F1Error")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9F1Error> => Either.left(new NativeProm9F1Error({ detail }));
const record = (value: unknown): value is Readonly<Record<string, TaskJson>> => validNativeTaskJson(value) && taskJsonRecord(value);
const object = (value: unknown, label: string): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9F1Error> => record(value) ? Either.right(value) : fail(`${label} must be an object`);
const own = (value: Readonly<Record<string, TaskJson>>, key: string): TaskJson | undefined => Object.hasOwn(value, key) ? value[key] : undefined;
const pythonBlank = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/u;
const text = (value: TaskJson | undefined, label: string): Either.Either<string, NativeProm9F1Error> => typeof value === "string" && !pythonBlank.test(value) ? Either.right(value) : fail(`${label} must be non-empty text`);
const integer = (value: TaskJson | undefined, label: string, minimum: number): Either.Either<bigint, NativeProm9F1Error> => {
    if (value === undefined || !isTaskNumber(value) || taskNumberIsFloat(value))
        return fail(`${label} must be an integer`);
    const numeric = taskNumberValue(value);
    if (typeof numeric === "number" && !Number.isSafeInteger(numeric))
        return fail(`${label} must be exact`);
    return BigInt(numeric) >= BigInt(minimum) ? Either.right(BigInt(numeric)) : fail(`${label} must be at least ${minimum}`);
};
const pythonInteger = (value: TaskJson | undefined, label: string): Either.Either<bigint, NativeProm9F1Error> => {
    const parsed = pythonJsonInt(value);
    return parsed === undefined ? fail(`${label} must be Python-int coercible`) : Either.right(parsed);
};
const maxBig = (values: readonly bigint[]): bigint => values.reduce((a, b) => a > b ? a : b);
const minBig = (values: readonly bigint[]): bigint => values.reduce((a, b) => a < b ? a : b);
const exactKeys = (value: Readonly<Record<string, TaskJson>>, keys: readonly string[], label: string): Either.Either<void, NativeProm9F1Error> => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key)) ? Either.right(undefined) : fail(`${label} keys drifted`);
const hash = (value: TaskJson, label: string) => canonicalNativeProm9Sha256(value).pipe(Either.mapLeft(() => new NativeProm9F1Error({ detail: `${label} cannot be canonically hashed` })));
const required = (value: Readonly<Record<string, TaskJson>>, key: string): Either.Either<TaskJson, NativeProm9F1Error> => Object.hasOwn(value, key) ? Either.right(value[key]!) : fail(`missing ${key}`);
const arm = (value: TaskJson | undefined): value is Arm => typeof value === "string" && (NATIVE_PROM9_F1_ARMS as readonly string[]).includes(value);
const number = (value: TaskJson | undefined): number | undefined => value !== undefined && isTaskNumber(value) && typeof taskNumberValue(value) === "number" && Number.isFinite(taskNumberValue(value)) ? taskNumberValue(value) as number : undefined;
/** Structural validator shared by manifest and suite verification. */
export const validateNativeProm9TokenEnvelope = (value: unknown): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9F1Error> => Either.gen(function* () {
    const data = yield* object(value, "token_envelope");
    yield* exactKeys(data, ["schema_version", "tokenizer", "filler", "per_call_input_caps", "per_call_output_caps", "projected_output_tokens_by_arm", "projection_slack_tokens"], "token_envelope");
    if (own(data, "schema_version") !== "hswm-prom9-f1-token-envelope/v1")
        return yield* fail("unsupported token envelope schema");
    const tokenizer = yield* object(own(data, "tokenizer"), "token_envelope tokenizer");
    if (Object.hasOwn(tokenizer, "validation_receipt_sha256") && (typeof own(tokenizer, "validation_receipt_sha256") !== "string" || !sha256.test(own(tokenizer, "validation_receipt_sha256") as string)))
        return yield* fail("tokenizer validation receipt must be a lowercase SHA-256");
    const filler = yield* object(own(data, "filler"), "token_envelope filler");
    yield* exactKeys(filler, ["field", "unit", "max_filler_chars"], "token_envelope filler");
    if (own(filler, "field") !== "parity_filler")
        return yield* fail("filler field must be the canonical parity_filler");
    yield* text(own(filler, "unit"), "filler unit");
    yield* integer(own(filler, "max_filler_chars"), "max filler chars", 0).pipe(Either.flatMap(v => v <= 65536 ? Either.right(v) : fail("max filler chars exceeds the port ceiling")));
    const triplet = (raw: TaskJson | undefined, label: string): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9F1Error> => Either.gen(function* () {
        const t = yield* object(raw, label);
        yield* exactKeys(t, ["1", "2", "3"], label);
        for (const key of ["1", "2", "3"])
            yield* integer(own(t, key), `${label} call ${key}`, 1);
        return t;
    });
    yield* triplet(own(data, "per_call_input_caps"), "per_call_input_caps");
    const outputs = yield* triplet(own(data, "per_call_output_caps"), "per_call_output_caps");
    const projections = yield* object(own(data, "projected_output_tokens_by_arm"), "projected_output_tokens_by_arm");
    yield* exactKeys(projections, NATIVE_PROM9_F1_ARMS, "projected_output_tokens_by_arm");
    for (const name of NATIVE_PROM9_F1_ARMS) {
        const p = yield* triplet(own(projections, name), `projected outputs for ${name}`);
        for (const key of ["1", "2", "3"])
            if ((yield* integer(own(p, key), `projected output ${name}/${key}`, 1)) > (yield* integer(own(outputs, key), `output cap ${key}`, 1)))
                return yield* fail(`projected output for ${name} call ${key} exceeds its output cap`);
    }
    yield* integer(own(data, "projection_slack_tokens"), "projection slack", 0);
    const snapshot = snapshotNativeTaskJson(data);
    return yield* object(snapshot, "token envelope snapshot");
});
const parityRecord = (rows: readonly Readonly<Record<string, TaskJson>>[], tolerance: bigint, envelope: Readonly<Record<string, TaskJson>>): Either.Either<TaskJson, NativeProm9F1Error> => Either.gen(function* () {
    const grouped = new Map<string, Map<Arm, Readonly<Record<string, TaskJson>>>>();
    for (const row of rows) {
        const item = pythonJsonString(yield* required(row, "item_id")), a = own(row, "arm_id");
        if (!arm(a))
            return yield* fail("item run has unsupported arm");
        const arms = grouped.get(item) ?? new Map<Arm, Readonly<Record<string, TaskJson>>>();
        arms.set(a, row);
        grouped.set(item, arms);
    }
    const items: TaskJson[] = [];
    for (const itemId of [...grouped.keys()].sort(taskTextCompare)) {
        const arms = grouped.get(itemId)!;
        if (arms.size !== NATIVE_PROM9_F1_ARMS.length)
            return yield* fail(`item ${itemId} does not cover every F1 arm`);
        const input: Record<string, bigint> = {}, output: Record<string, bigint> = {}, total: Record<string, bigint> = {};
        for (const a of NATIVE_PROM9_F1_ARMS) {
            const row = arms.get(a)!;
            const i = yield* pythonInteger(own(row, "total_input_tokens"), "total input tokens"), o = yield* pythonInteger(own(row, "total_output_tokens"), "total output tokens");
            input[a] = i;
            output[a] = o;
            total[a] = i + o;
        }
        const values = Object.values(total), inputs = Object.values(input);
        const spread = maxBig(values) - minBig(values), inputSpread = maxBig(inputs) - minBig(inputs);
        items.push(Object.freeze({ item_id: itemId, input_tokens_by_arm: Object.freeze(input), output_tokens_by_arm: Object.freeze(output), total_tokens_by_arm: Object.freeze(total), spread, input_spread: inputSpread, within_tolerance: spread <= tolerance }));
    }
    const typedItems = items as readonly Readonly<Record<string, TaskJson>>[];
    return Object.freeze({ per_call_input_caps: own(envelope, "per_call_input_caps")!, per_call_output_caps: own(envelope, "per_call_output_caps")!, input_spread_max: maxBig(typedItems.map(x => x["input_spread"] as bigint)), spread_max: maxBig(typedItems.map(x => x["spread"] as bigint)), all_within_tolerance: typedItems.every(x => x["within_tolerance"] === true), items: Object.freeze(items) });
});
export const verifyNativeProm9F1Suite = (value: unknown): Either.Either<string, NativeProm9F1Error> => Either.gen(function* () {
    const data = yield* object(value, "F1 suite");
    if (own(data, "schema_version") !== NATIVE_PROM9_F1_SUITE_SCHEMA)
        return yield* fail("unsupported F1 suite schema");
    const declared = yield* text(own(data, "suite_receipt_sha256"), "suite_receipt_sha256");
    const unsigned = Object.fromEntries(Object.entries(data).filter(([k]) => k !== "suite_receipt_sha256"));
    if ((yield* hash(unsigned, "F1 suite")) !== declared)
        return yield* fail("F1 suite self-hash drifted");
    if (own(data, "gold_opened") !== false || own(data, "scientific_verdict_emitted") !== false)
        return yield* fail("F1 run phase crossed evaluator authority");
    const registries = yield* object(own(data, "registries"), "F1 suite registries");
    yield* exactKeys(registries, NATIVE_PROM9_F1_ARMS, "F1 suite registries");
    const fn = new Map<Arm, Map<string, Readonly<Record<string, TaskJson>>>>();
    for (const a of NATIVE_PROM9_F1_ARMS) {
        const registry = yield* object(own(registries, a), `registry for ${a}`);
        const registrySha = yield* text(own(registry, "registry_sha256"), `registry hash for ${a}`);
        const u = Object.fromEntries(Object.entries(registry).filter(([k]) => k !== "registry_sha256"));
        if ((yield* hash(u, `registry ${a}`)) !== registrySha)
            return yield* fail(`registry hash drifted for ${a}`);
        const functions = own(registry, "functions");
        if (!Array.isArray(functions) || functions.length !== 3)
            return yield* fail(`registry for ${a} must contain three functions`);
        const indexed = new Map<string, Readonly<Record<string, TaskJson>>>();
        for (const raw of functions) {
            const f = yield* object(raw, `registry function for ${a}`);
            const id = yield* text(own(f, "function_id"), "function_id");
            if ((yield* hash(Object.freeze({ prompt: own(f, "prompt") ?? null }), "prompt")) !== own(f, "prompt_sha256"))
                return yield* fail(`prompt hash drifted for ${a}/${id}`);
            indexed.set(id, f);
        }
        if (FUNCTIONS.some(id => !indexed.has(id)) || indexed.size !== 3)
            return yield* fail(`function set drifted for ${a}`);
        fn.set(a, indexed);
    }
    const rawRows = own(data, "item_runs");
    if (!Array.isArray(rawRows) || rawRows.length === 0)
        return yield* fail("F1 suite has no item runs");
    const rows = yield* Either.all(rawRows.map(row => object(row, "F1 item run")));
    for (const row of rows) {
        yield* verifyNativeProm9RunReceipt(row).pipe(Either.mapLeft(e => new NativeProm9F1Error({ detail: e.detail })));
        const a = own(row, "arm_id");
        if (!arm(a) || own(row, "registry_sha256") !== own((fn.has(a) ? (yield* object(own(registries, a), "registry")) : yield* fail("item run has unsupported arm")), "registry_sha256"))
            return yield* fail("item run is not bound to its arm registry");
        const calls = own(row, "calls");
        if (!Array.isArray(calls))
            return yield* fail("item run calls invalid");
        for (const call of calls) {
            const c = yield* object(call, "call");
            const f = fn.get(a)!.get(String(own(c, "function_id")));
            if (f === undefined || own(c, "prompt_sha256") !== own(f, "prompt_sha256"))
                return yield* fail("call prompt is not bound to the arm registry");
        }
    }
    const audit = own(data, "transport_audit");
    if (audit !== null && audit !== undefined) {
        const v = yield* object(audit, "F1 transport audit"), declaredAudit = yield* text(own(v, "audit_sha256"), "audit sha");
        if ((yield* hash(Object.fromEntries(Object.entries(v).filter(([k]) => k !== "audit_sha256")), "transport audit")) !== declaredAudit)
            return yield* fail("F1 transport audit hash drifted");
        const expected = rows.length * 3;
        if (!pythonJsonEqual(own(v, "call_count") ?? null, expected) || !pythonJsonEqual(own(v, "item_run_count") ?? null, rows.length) || !pythonJsonEqual(own(v, "status_counts") ?? null, { ACCEPTED: expected }))
            return yield* fail("F1 transport audit completeness drifted");
    }
    const envelope = yield* validateNativeProm9TokenEnvelope(own(data, "token_envelope"));
    const parity = yield* object(own(data, "token_parity"), "F1 token parity");
    yield* exactKeys(parity, ["per_call_input_caps", "per_call_output_caps", "input_spread_max", "spread_max", "all_within_tolerance", "items"], "F1 token parity");
    if (!pythonJsonEqual(own(parity, "per_call_input_caps")!, own(envelope, "per_call_input_caps")!) || !pythonJsonEqual(own(parity, "per_call_output_caps")!, own(envelope, "per_call_output_caps")!))
        return yield* fail("token parity caps drifted from the envelope");
    const tolerance = yield* pythonInteger(own(data, "token_tolerance"), "token_tolerance");
    const recomputed = yield* parityRecord(rows, tolerance, envelope);
    if (!pythonJsonEqual(parity, recomputed))
        return yield* fail("token parity record was not computed from the item runs");
    const projection = yield* object(own(data, "envelope_projection"), "F1 suite envelope projection");
    yield* exactKeys(projection, ["projected_total_tokens_by_arm", "projected_spread", "items"], "F1 suite envelope projection record");
    return declared;
});
const bootstrap = (values: readonly number[], reps: number, seed: number): Either.Either<readonly [
    number,
    number
], NativeProm9F1Error> => {
    if (values.length === 0)
        return fail("cannot bootstrap an empty comparison");
    if (!Number.isSafeInteger(reps) || reps < 1 || !Number.isSafeInteger(seed))
        return fail("bootstrap reps and seed must be integers");
    let random = nativePythonMt19937InitialState(BigInt(seed));
    const means: number[] = [];
    for (let r = 0; r < reps; r++) {
        let sum = 0;
        for (let j = 0; j < values.length; j++) {
            const [index, next] = nativePythonRandrange(random, values.length);
            sum += values[index]!;
            random = next;
        }
        means.push(sum / values.length);
    }
    means.sort((a, b) => a - b);
    return Either.right([means[Math.floor(.025 * (reps - 1))]!, means[Math.floor(.975 * (reps - 1))]!]);
};
const normalize = pythonJsonNormalizeAnswer;
export const judgeNativeProm9F1Suite = (suite: unknown, gold: unknown, bootstrapReps = 10000, bootstrapSeed = 20260724): Either.Either<TaskJson, NativeProm9F1Error> => Either.gen(function* () {
    const suiteSha = yield* verifyNativeProm9F1Suite(suite);
    const s = yield* object(suite, "F1 suite"), g = yield* object(gold, "F1 gold");
    yield* exactKeys(g, ["schema_version", "run_id", "evaluator_receipt_sha256", "items"], "F1 gold");
    if (own(g, "schema_version") !== NATIVE_PROM9_F1_GOLD_SCHEMA || !pythonJsonEqual(own(g, "run_id") ?? null, own(s, "run_id") ?? null))
        return yield* fail("gold identity does not match the F1 suite");
    const evaluator = yield* text(own(g, "evaluator_receipt_sha256"), "evaluator receipt");
    if (!sha256.test(evaluator))
        return yield* fail("evaluator receipt must be a lowercase SHA-256");
    const goldRows = own(g, "items");
    if (!Array.isArray(goldRows) || goldRows.length === 0)
        return yield* fail("gold items must be non-empty");
    const answers = new Map<string, Set<string>>();
    for (let i = 0; i < goldRows.length; i++) {
        const r = yield* object(goldRows[i], `gold item ${i}`);
        yield* exactKeys(r, ["item_id", "accepted_answers"], `gold item ${i}`);
        const id = yield* text(own(r, "item_id"), `gold item ${i} id`), aa = own(r, "accepted_answers");
        if (!Array.isArray(aa) || aa.length === 0 || aa.some(x => typeof x !== "string" || pythonJsonStrip(x) === ""))
            return yield* fail(`gold item ${i} accepted answers are invalid`);
        if (answers.has(id))
            return yield* fail(`duplicate gold item: ${id}`);
        answers.set(id, new Set(aa.map(x => normalize(x as string))));
    }
    const indexed = new Map<string, Map<Arm, Readonly<Record<string, TaskJson>>>>();
    const rows = own(s, "item_runs") as readonly TaskJson[];
    for (const raw of rows) {
        const row = yield* object(raw, "item run"), id = pythonJsonString(yield* required(row, "item_id")), a = own(row, "arm_id");
        if (!arm(a))
            return yield* fail("item run has unsupported arm");
        const m = indexed.get(id) ?? new Map<Arm, Readonly<Record<string, TaskJson>>>();
        m.set(a, row);
        indexed.set(id, m);
    }
    if (indexed.size !== answers.size || [...indexed.keys()].some(id => !answers.has(id)))
        return yield* fail("suite/gold item sets differ");
    const tolerance = yield* pythonInteger(own(s, "token_tolerance"), "token_tolerance"), scores = new Map<Arm, number[]>(NATIVE_PROM9_F1_ARMS.map(a => [a, []]));
    const itemScores: TaskJson[] = [];
    const parity: string[] = [];
    for (const id of [...indexed.keys()].sort(taskTextCompare)) {
        const arms = indexed.get(id)!;
        if (arms.size !== 5)
            return yield* fail(`item ${id} does not cover every F1 arm`);
        const rs = [...arms.values()];
        for (const row of rs) {
            yield* required(row, "candidate_universe_sha256");
            for (const call of row["calls"] as readonly TaskJson[]) {
                const c = yield* object(call, "call");
                yield* required(c, "model");
                yield* required(c, "model_revision");
            }
        }
        const universes = new Set(rs.map(r => pythonJsonString(own(r, "candidate_universe_sha256") ?? null))), models = new Set(rs.flatMap(r => (own(r, "calls") as readonly TaskJson[]).map(x => { const c = x as Readonly<Record<string, TaskJson>>; return JSON.stringify([pythonJsonString(own(c, "model") ?? null), pythonJsonString(own(c, "model_revision") ?? null)]); }))), allowed = new Set(yield* Either.all(rs.map(r => pythonInteger(own(r, "total_allowed_output_tokens"), "allowed outputs"))));
        const totals = yield* Either.all(rs.map(r => Either.gen(function* () { return (yield* pythonInteger(own(r, "total_input_tokens"), "input total")) + (yield* pythonInteger(own(r, "total_output_tokens"), "output total")); })));
        if (universes.size !== 1)
            parity.push(`${id}:candidate-universe`);
        if (models.size !== 1)
            parity.push(`${id}:model`);
        if (allowed.size !== 1)
            parity.push(`${id}:allowed-output`);
        const spread = maxBig(totals) - minBig(totals);
        if (spread > tolerance)
            parity.push(`${id}:consumed-token-spread=${spread}`);
        const rowScores: Record<string, TaskJson> = {};
        for (const a of NATIVE_PROM9_F1_ARMS) {
            const answer = yield* object(own(arms.get(a)!, "answer"), "answer"), score = own(answer, "abstain") === false && typeof own(answer, "answer") === "string" && answers.get(id)!.has(normalize(own(answer, "answer") as string)) ? 1 : 0;
            scores.get(a)!.push(score);
            rowScores[a] = nativeTaskFloat(score)!;
        }
        itemScores.push(Object.freeze({ item_id: id, scores: Object.freeze(rowScores) }));
    }
    const metrics: Record<string, TaskJson> = {}, comparisons: Record<string, TaskJson> = {};
    for (const a of NATIVE_PROM9_F1_ARMS) {
        const v = scores.get(a)!;
        metrics[a] = Object.freeze({ success_rate: nativeTaskFloat(v.reduce((x, y) => x + y, 0) / v.length)!, n: v.length });
    }
    for (const a of NATIVE_PROM9_F1_ARMS.slice(1)) {
        const diffs = scores.get(NATIVE_PROM9_F1_ARMS[0])!.map((x, i) => x - scores.get(a)![i]!);
        const mean = diffs.reduce((x, y) => x + y, 0) / diffs.length, ci = yield* bootstrap(diffs, bootstrapReps, bootstrapSeed);
        comparisons[`typed_minus_${a}`] = Object.freeze({ mean: nativeTaskFloat(mean)!, bootstrap95: Object.freeze(ci.map(value => nativeTaskFloat(value)!)) });
    }
    const typedFlat = comparisons[`typed_minus_${NATIVE_PROM9_F1_ARMS[1]}`] as Readonly<Record<string, TaskJson>>, exactCalls = [...indexed.values()].every(as => [...as.values()].every(r => { const calls = own(r, "calls"); return Array.isArray(calls) && calls.length === 3; })), gates = Object.freeze({ exact_three_calls_each: exactCalls, equal_budget: parity.length === 0, typed_beats_flat_lcb_gt_0: (number((typedFlat["bootstrap95"] as readonly TaskJson[])[0]) ?? 0) > 0, typed_beats_vector: (number((comparisons[`typed_minus_${NATIVE_PROM9_F1_ARMS[2]}`] as Readonly<Record<string, TaskJson>>)["mean"]) ?? 0) > 0, removal_loses_effect: (number((comparisons[`typed_minus_${NATIVE_PROM9_F1_ARMS[3]}`] as Readonly<Record<string, TaskJson>>)["mean"]) ?? 0) > 0, shuffle_loses_effect: (number((comparisons[`typed_minus_${NATIVE_PROM9_F1_ARMS[4]}`] as Readonly<Record<string, TaskJson>>)["mean"]) ?? 0) > 0 });
    yield* required(s, "run_id");
    const supported = Object.values(gates).every(Boolean), mode = yield* required(s, "mode"), verdict = mode === "development" ? "DEVELOPMENT_ONLY" : supported ? "F1_SUPPORTED_NARROW" : "REJECTED_OR_NARROWED", claim = mode === "development" ? "No scientific efficacy claim; use this result only to debug and freeze F1." : supported ? "On the registered sealed scope, typed composition beat matched flat/vector controls and lost its effect under role removal/shuffle." : "The sealed F1 result did not satisfy the complete topology-and-budget conjunction.";
    const out: TaskJson = Object.freeze({ schema_version: NATIVE_PROM9_F1_JUDGMENT_SCHEMA, run_id: own(s, "run_id")!, suite_receipt_sha256: suiteSha, evaluator_receipt_sha256: evaluator, mode: mode!, bootstrap: Object.freeze({ reps: bootstrapReps, seed: bootstrapSeed, paired: true }), metrics: Object.freeze(metrics), comparisons: Object.freeze(comparisons), gates, parity_failures: Object.freeze(parity), item_scores: Object.freeze(itemScores), verdict, allowed_claim: claim });
    return snapshotNativeTaskJson({ ...out, judgment_sha256: yield* hash(out, "judgment") });
});
