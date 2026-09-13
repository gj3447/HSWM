/** Pure registry constructor from a captured, schema-locked PROM-9 protocol. */
import { Data, Either } from "effect";
import { canonicalNativeProm9Sha256 } from "./native-prom9-ports-domain.js";
import { isTaskNumber, snapshotNativeTaskJson, taskJsonRecord, taskNumberIsFloat, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
import { pythonJsonInt, pythonJsonStrip } from "./native-python-json-semantics-domain.js";
export class NativeProm9F1RegistryError extends Data.TaggedError("NativeProm9F1RegistryError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9F1RegistryError> => Either.left(new NativeProm9F1RegistryError({ detail }));
const ids = ["QF_QUERY_COMPILER", "BF_BOND_PROPOSER", "AF_ANSWER_SYNTHESIZER"] as const;
const record = (v: unknown): v is Readonly<Record<string, TaskJson>> => validNativeTaskJson(v) && taskJsonRecord(v);
const dataOnly = (value: unknown): boolean => { try {
    if (value === null || typeof value !== "object")
        return true;
    const descriptors = [...Object.values(Object.getOwnPropertyDescriptors(value)), ...Object.getOwnPropertySymbols(value).map(key => Object.getOwnPropertyDescriptor(value, key)!)];
    return descriptors.every(descriptor => descriptor.get === undefined && descriptor.set === undefined && dataOnly(descriptor.value));
}
catch {
    return false;
} };
const text = (v: TaskJson | undefined): string | undefined => typeof v === "string" && pythonJsonStrip(v) !== "" ? v : undefined;
const exact = (v: Readonly<Record<string, TaskJson>>, ks: readonly string[]) => Object.keys(v).length === ks.length && ks.every(k => Object.hasOwn(v, k));
const list = (v: TaskJson | undefined, min = 1): readonly string[] | undefined => Array.isArray(v) && v.length >= min && v.every(x => typeof x === "string" && pythonJsonStrip(x) !== "") && new Set(v).size === v.length ? v as readonly string[] : undefined;
const positive = (v: TaskJson | undefined) => { const n = v === undefined || !isTaskNumber(v) || taskNumberIsFloat(v) ? undefined : pythonJsonInt(v); return n !== undefined && n > 0n; };
const stageIds = ["F1_TYPED_FUNCTION_NETWORK", "G0_REAL_PACKS", "P1V5_FAST_TO_SLOW_PLASTICITY", "P2_FROZEN_AGENT_TRANSFER"];
const protocolKeys = ["schema_version", "programme", "status", "claim_boundary", "question", "execution_model", "stages", "llm_functions", "arm_matrix", "budget_contract", "evaluation", "conclusion_rules", "kill_conditions", "external_governance"];
const validateProtocol = (raw: unknown): Either.Either<Readonly<Record<string, TaskJson>>, NativeProm9F1RegistryError> => Either.gen(function* () {
    if (!dataOnly(raw) || !record(raw) || !exact(raw, protocolKeys) || raw["schema_version"] !== "hswm-prom9-semantic-neural-network/v1" || raw["status"] !== "DESIGN_LOCKED_NOT_PREREGISTERED")
        return yield* fail("invalid protocol preimage");
    for (const k of ["programme", "claim_boundary", "question"]) {
        if (text(raw[k]) === undefined)
            return yield* fail("invalid protocol preimage");
    }
    const execution = raw["execution_model"];
    if (!record(execution) || !exact(execution, ["node_equation", "forward_path", "learning_path", "durable_state", "non_learning_state", "evaluator"]))
        return yield* fail("invalid protocol preimage");
    for (const k of ["node_equation", "forward_path", "learning_path", "evaluator"])
        if (text(execution[k]) === undefined)
            return yield* fail("invalid protocol preimage");
    if (list(execution["durable_state"]) === undefined || list(execution["non_learning_state"]) === undefined || !String(execution["evaluator"]).toLowerCase().includes("external"))
        return yield* fail("invalid protocol preimage");
    const stages = raw["stages"];
    if (!Array.isArray(stages) || stages.length !== 4)
        return yield* fail("invalid protocol preimage");
    const seen = new Set<string>();
    for (let i = 0; i < stages.length; i++) {
        const s = stages[i];
        if (!record(s) || !exact(s, ["id", "order", "lane", "status_gate", "depends_on", "purpose", "permitted_actions", "forbidden_actions", "required_inputs", "exit_evidence"]) || s["id"] !== stageIds[i] || !positive(s["order"]))
            return yield* fail("invalid protocol preimage");
        for (const k of ["lane", "status_gate", "purpose"])
            if (text(s[k]) === undefined)
                return yield* fail("invalid protocol preimage");
        const deps = list(s["depends_on"], 0);
        if (deps === undefined || deps.some(d => !seen.has(d)))
            return yield* fail("invalid protocol preimage");
        for (const k of ["permitted_actions", "forbidden_actions", "required_inputs", "exit_evidence"])
            if (list(s[k]) === undefined)
                return yield* fail("invalid protocol preimage");
        seen.add(stageIds[i]!);
    }
    const functions = raw["llm_functions"];
    if (!Array.isArray(functions) || functions.length !== 3)
        return yield* fail("invalid protocol preimage");
    const outputs = new Set<string>();
    for (let i = 0; i < functions.length; i++) {
        const f = functions[i];
        if (!record(f) || !exact(f, ["id", "role", "model_policy", "input_type", "output_type", "reads", "writes", "prompt", "abstention", "forbidden"]) || f["id"] !== ids[i])
            return yield* fail("invalid protocol preimage");
        for (const k of ["role", "model_policy", "input_type", "output_type", "prompt", "abstention"])
            if (text(f[k]) === undefined)
                return yield* fail("invalid protocol preimage");
        for (const k of ["reads", "writes", "forbidden"])
            if (list(f[k]) === undefined)
                return yield* fail("invalid protocol preimage");
        if (!String(f["prompt"]).includes("JSON") || !String(f["prompt"]).includes("scientific verdict"))
            return yield* fail("invalid protocol preimage");
        outputs.add(String(f["output_type"]));
    }
    if (outputs.size !== 3)
        return yield* fail("invalid protocol preimage");
    const arms = raw["arm_matrix"];
    if (!record(arms) || !exact(arms, ["F1", "P1V5", "P2"]))
        return yield* fail("invalid protocol preimage");
    for (const k of ["F1", "P1V5", "P2"])
        if (list(arms[k], 5) === undefined)
            return yield* fail("invalid protocol preimage");
    if (!(list(arms["F1"]) ?? []).some(x => x.includes("role_removed")) || !(list(arms["F1"]) ?? []).some(x => x.includes("role_instructions_shuffled")) || !(list(arms["P1V5"]) ?? []).some(x => x.includes("causal_removal")))
        return yield* fail("invalid protocol preimage");
    const budget = raw["budget_contract"];
    if (!record(budget) || !exact(budget, ["llm_calls_per_item", "call_parity", "token_parity", "retrieval_parity", "state_parity", "cost_ledger"]) || !positive(budget["llm_calls_per_item"]) || pythonJsonInt(budget["llm_calls_per_item"]) !== 3n)
        return yield* fail("invalid protocol preimage");
    for (const k of ["call_parity", "token_parity", "retrieval_parity", "state_parity", "cost_ledger"])
        if (text(budget[k]) === undefined)
            return yield* fail("invalid protocol preimage");
    const evaluation = raw["evaluation"];
    if (!record(evaluation) || !exact(evaluation, ["split_contract", "primary_metrics", "promotion_gates", "reporting"]) || text(evaluation["split_contract"]) === undefined || text(evaluation["reporting"]) === undefined || list(evaluation["promotion_gates"]) === undefined)
        return yield* fail("invalid protocol preimage");
    const metrics = evaluation["primary_metrics"];
    if (!record(metrics) || !exact(metrics, ["F1", "P1V5", "P2"]))
        return yield* fail("invalid protocol preimage");
    for (const k of ["F1", "P1V5", "P2"])
        if (text(metrics[k]) === undefined)
            return yield* fail("invalid protocol preimage");
    if (list(raw["conclusion_rules"], 6) === undefined || list(raw["kill_conditions"], 6) === undefined)
        return yield* fail("invalid protocol preimage");
    const gov = raw["external_governance"];
    if (!record(gov) || !exact(gov, ["authority", "prediction_registration_required", "result_submission_allowed"]) || gov["authority"] !== "NONE" || gov["prediction_registration_required"] !== false || gov["result_submission_allowed"] !== false)
        return yield* fail("invalid protocol preimage");
    const normalized = snapshotNativeTaskJson(raw);
    if (!record(normalized))
        return yield* fail("invalid protocol preimage");
    return normalized;
});
export const buildNativeProm9F1Registry = (raw: unknown, model: unknown, revision: unknown, rawOverrides: unknown = {}): Either.Either<TaskJson, NativeProm9F1RegistryError> => Either.gen(function* () {
    const protocol = yield* validateProtocol(raw);
    const m = text(dataOnly(model) && validNativeTaskJson(model) ? model : undefined), r = text(dataOnly(revision) && validNativeTaskJson(revision) ? revision : undefined);
    if (m === undefined || r === undefined)
        return yield* fail("model and model_revision must be non-empty");
    const functions = protocol["llm_functions"];
    if (!Array.isArray(functions) || functions.length !== 3)
        return yield* fail("protocol function set drifted");
    if (rawOverrides === null)
        rawOverrides = {};
    if (!dataOnly(rawOverrides) || !record(rawOverrides))
        return yield* fail("prompt overrides must be a JSON object");
    const overrides: Record<string, string> = {};
    for (const [key, value] of Object.entries(rawOverrides)) {
        if (!ids.includes(key as typeof ids[number]) || typeof value !== "string" || pythonJsonStrip(value) === "")
            return yield* fail("prompt override names unknown functions");
        overrides[key] = value;
    }
    const output: TaskJson[] = [];
    for (let index = 0; index < ids.length; index++) {
        const id = ids[index];
        const fn = functions[index];
        if (id === undefined || !record(fn) || fn["id"] !== id)
            return yield* fail("protocol function set drifted");
        const prompt = overrides[id] ?? text(fn["prompt"]);
        const input = text(fn["input_type"]), out = text(fn["output_type"]);
        if (prompt === undefined || pythonJsonStrip(prompt) === "" || input === undefined || out === undefined)
            return yield* fail(`invalid function ${id}`);
        const promptSha = yield* canonicalNativeProm9Sha256(Object.freeze({ prompt })).pipe(Either.mapLeft(e => new NativeProm9F1RegistryError({ detail: e.detail })));
        output.push(Object.freeze({ function_id: id, model: m, model_revision: r, input_type: input, output_type: out, prompt, prompt_sha256: promptSha }));
    }
    const protocolSha = yield* canonicalNativeProm9Sha256(protocol).pipe(Either.mapLeft(e => new NativeProm9F1RegistryError({ detail: e.detail }))), unsigned = Object.freeze({ schema_version: "hswm-prom9-function-registry/v1", protocol_sha256: protocolSha, functions: Object.freeze(output) }), registrySha = yield* canonicalNativeProm9Sha256(unsigned).pipe(Either.mapLeft(e => new NativeProm9F1RegistryError({ detail: e.detail })));
    return snapshotNativeTaskJson(Object.freeze({ ...unsigned, registry_sha256: registrySha }));
});
