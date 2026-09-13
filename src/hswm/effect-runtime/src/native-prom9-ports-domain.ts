/** Pure PROM-9 ports. These bounded contracts do not qualify the F1 judge. */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { decodeNativeTaskJson, isTaskNumber, renderNativeTaskJson, taskFloatText, taskJsonRecord, taskNumberValue, validNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
export const PROM9_PORT_SCHEMA = "hswm-prom9-typed-port/v2";
export const PROM9_PARITY_FILLER_FIELD = "parity_filler";
export const PROM9_MAX_FILLER_CHARS = 65536;
export type Prom9PortType = "QueryEnvelopeV1" | "QueryPlanV1" | "BondScoringEnvelopeV1" | "BondProposalV1" | "AnswerContextV1" | "AnswerEnvelopeV1";
export type NativeProm9Port = Readonly<Record<string, TaskJson>>;
export class NativeProm9PortError extends Data.TaggedError("NativeProm9PortError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, NativeProm9PortError> => Either.left(new NativeProm9PortError({ detail }));
const record = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value) && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const object = (value: unknown, label: string) => record(value) ? Either.right(value) : fail(`${label} must be an object`);
const keys = (value: Readonly<Record<string, unknown>>, expected: readonly string[], label: string) => Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key)) ? Either.right(undefined) : fail(`${label} keys drifted`);
const pythonBlank = (value: string) => /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/u.test(value);
const text = (value: unknown, label: string, empty = false) => typeof value === "string" && (empty || !pythonBlank(value)) ? Either.right(value) : fail(`${label} must be ${empty ? "text" : "non-empty text"}`);
const boolean = (value: unknown, label: string) => typeof value === "boolean" ? Either.right(value) : fail(`${label} must be boolean`);
const positive = (value: unknown, label: string): Either.Either<number | bigint, NativeProm9PortError> => (typeof value === "bigint" && value > 0n) || (typeof value === "number" && Number.isSafeInteger(value) && value > 0) ? Either.right(value) : fail(`${label} must be a positive integer`);
const dense = (value: unknown): value is readonly unknown[] => Array.isArray(value) && Array.from({ length: value.length }, (_, index) => Object.hasOwn(value, index)).every(Boolean);
const unique = (values: readonly string[], label: string) => new Set(values).size === values.length ? Either.right(undefined) : fail(`${label} must not contain duplicates`);
const list = (value: unknown, label: string) => Either.gen(function* () {
    if (!dense(value))
        return yield* fail(`${label} must be a dense array`);
    const result = yield* Either.all(value.map(item => text(item, `${label} item`)));
    yield* unique(result, label);
    return Object.freeze(result);
});
const filler = (value: unknown) => typeof value === "string" && Array.from(value).length <= PROM9_MAX_FILLER_CHARS ? Either.right(value) : fail("parity_filler must be text within its character ceiling");
const finite = (value: unknown, label: string) => Either.gen(function* () {
    if (!validNativeTaskJson(value) || !isTaskNumber(value))
        return yield* fail(`${label} must be numeric`);
    const number = Number(taskNumberValue(value));
    if (!Number.isFinite(number) || number > 0)
        return yield* fail(`${label} must be finite and <= 0.0`);
    const parsed = decodeNativeTaskJson(new TextEncoder().encode(taskFloatText(number === 0 ? 0 : number)));
    if (Either.isLeft(parsed))
        return yield* fail(`${label} cannot normalize`);
    return parsed.right;
});
const freezeJson = (value: TaskJson): TaskJson => Array.isArray(value) ? Object.freeze(value.map(freezeJson)) : taskJsonRecord(value) ? Object.freeze(Object.fromEntries(Object.entries(value).map(([key, child]) => [key, freezeJson(child)]))) : value;
const json = (value: unknown, label: string): Either.Either<TaskJson, NativeProm9PortError> => validNativeTaskJson(value) ? Either.right(freezeJson(value)) : fail(`${label} is not a JSON value`);
const queryPlan = (value: unknown): Either.Either<NativeProm9Port, NativeProm9PortError> => Either.gen(function* () {
    const v = yield* object(value, "QueryPlanV1");
    yield* keys(v, ["request_id", "objectives", "required_evidence_types", "constraints", "abstain"], "QueryPlanV1");
    return Object.freeze({ request_id: yield* text(v["request_id"], "request_id"), objectives: yield* list(v["objectives"], "objectives"), required_evidence_types: yield* list(v["required_evidence_types"], "required_evidence_types"), constraints: yield* list(v["constraints"], "constraints"), abstain: yield* boolean(v["abstain"], "abstain") });
});
const candidateTable = (value: unknown) => Either.gen(function* () {
    const v = yield* object(value, "candidate_table");
    yield* keys(v, ["constants", "columns", "rows"], "candidate_table");
    const constants = yield* object(v["constants"], "candidate constants");
    const normalizedConstants: (readonly [
        string,
        TaskJson
    ])[] = [];
    for (const [key, raw] of Object.entries(constants))
        normalizedConstants.push([yield* text(key, "constant key"), yield* json(raw, "constant value")]);
    const columns = yield* list(v["columns"], "candidate columns"), bondIndex = columns.indexOf("bond_id"), evidenceIndex = columns.indexOf("evidence_id");
    if (bondIndex < 0 || evidenceIndex < 0)
        return yield* fail("candidate columns must include bond_id and evidence_id");
    const rawRows = v["rows"];
    if (!dense(rawRows) || rawRows.length === 0)
        return yield* fail("candidate rows must be a non-empty dense array");
    const rows: (readonly TaskJson[])[] = [], bonds: string[] = [], evidence: string[] = [];
    for (const raw of rawRows) {
        if (!dense(raw) || raw.length !== columns.length)
            return yield* fail("candidate row must cover every column");
        const row = yield* Either.all(raw.map(cell => json(cell, "candidate cell")));
        bonds.push(yield* text(row[bondIndex], "candidate bond_id"));
        evidence.push(yield* text(row[evidenceIndex], "candidate evidence_id"));
        rows.push(Object.freeze(row));
    }
    yield* unique(bonds, "candidate bond IDs");
    yield* unique(evidence, "candidate evidence IDs");
    return Object.freeze({ constants: Object.freeze(Object.fromEntries(normalizedConstants)), columns, rows: Object.freeze(rows) });
});
export const validateNativeProm9Port = (port: Prom9PortType, value: unknown): Either.Either<NativeProm9Port, NativeProm9PortError> => Either.gen(function* () {
    if (port === "QueryPlanV1")
        return yield* queryPlan(value);
    const v = yield* object(value, port);
    if (port === "QueryEnvelopeV1") {
        yield* keys(v, ["request_id", "query_text", "allowed_evidence_types", "budget", "parity_filler"], port);
        const rawBudget = yield* object(v["budget"], "budget"), budgetNames = ["max_candidates", "max_evidence_items", "max_input_tokens", "max_output_tokens"];
        yield* keys(rawBudget, budgetNames, "budget");
        const budget: (readonly [
            string,
            number | bigint
        ])[] = [];
        for (const key of budgetNames)
            budget.push([key, yield* positive(rawBudget[key], `budget ${key}`)]);
        return Object.freeze({ request_id: yield* text(v["request_id"], "request_id"), query_text: yield* text(v["query_text"], "query_text"), allowed_evidence_types: yield* list(v["allowed_evidence_types"], "allowed_evidence_types"), budget: Object.freeze(Object.fromEntries(budget)), parity_filler: yield* filler(v["parity_filler"]) });
    }
    if (port === "BondScoringEnvelopeV1") {
        yield* keys(v, ["request_id", "query_plan", "candidate_table", "candidate_budget", "parity_filler"], port);
        const table = yield* candidateTable(v["candidate_table"]), budget = yield* positive(v["candidate_budget"], "candidate_budget");
        if (budget > table.rows.length)
            return yield* fail("candidate_budget exceeds supplied candidates");
        return Object.freeze({ request_id: yield* text(v["request_id"], "request_id"), query_plan: yield* queryPlan(v["query_plan"]), candidate_table: table, candidate_budget: budget, parity_filler: yield* filler(v["parity_filler"]) });
    }
    if (port === "BondProposalV1") {
        yield* keys(v, ["request_id", "ordered_bond_ids", "bond_potentials", "evidence_refs", "abstain"], port);
        const ordered = yield* list(v["ordered_bond_ids"], "ordered_bond_ids"), raw = yield* object(v["bond_potentials"], "bond_potentials"), potentials: (readonly [
            string,
            TaskJson
        ])[] = [];
        for (const [key, value] of Object.entries(raw))
            potentials.push([yield* text(key, "bond_potential key"), yield* finite(value, `bond_potential ${key}`)]);
        const normalized = Object.freeze(Object.fromEntries(potentials));
        if (Object.keys(normalized).length !== ordered.length || !ordered.every(key => Object.hasOwn(normalized, key)))
            return yield* fail("bond_potentials must exactly cover ordered_bond_ids");
        return Object.freeze({ request_id: yield* text(v["request_id"], "request_id"), ordered_bond_ids: ordered, bond_potentials: normalized, evidence_refs: yield* list(v["evidence_refs"], "evidence_refs"), abstain: yield* boolean(v["abstain"], "abstain") });
    }
    if (port === "AnswerEnvelopeV1") {
        yield* keys(v, ["request_id", "answer", "supporting_evidence_ids", "uncertainty", "abstain"], port);
        return Object.freeze({ request_id: yield* text(v["request_id"], "request_id"), answer: yield* text(v["answer"], "answer", true), supporting_evidence_ids: yield* list(v["supporting_evidence_ids"], "supporting_evidence_ids"), uncertainty: yield* text(v["uncertainty"], "uncertainty", true), abstain: yield* boolean(v["abstain"], "abstain") });
    }
    if (port !== "AnswerContextV1")
        return yield* fail(`unsupported port type: ${String(port)}`);
    yield* keys(v, ["request_id", "query_text", "query_plan", "selected_evidence", "max_answer_tokens", "parity_filler"], port);
    const evidence = v["selected_evidence"];
    if (!dense(evidence))
        return yield* fail("selected_evidence must be a dense array");
    const selected: Readonly<{
        evidence_id: string;
        content: string;
    }>[] = [];
    for (const raw of evidence) {
        const row = yield* object(raw, "selected evidence");
        yield* keys(row, ["evidence_id", "content"], "selected evidence");
        selected.push(Object.freeze({ evidence_id: yield* text(row["evidence_id"], "evidence id"), content: yield* text(row["content"], "evidence content") }));
    }
    yield* unique(selected.map(row => row.evidence_id), "selected evidence IDs");
    return Object.freeze({ request_id: yield* text(v["request_id"], "request_id"), query_text: yield* text(v["query_text"], "query_text"), query_plan: yield* queryPlan(v["query_plan"]), selected_evidence: Object.freeze(selected), max_answer_tokens: yield* positive(v["max_answer_tokens"], "max_answer_tokens"), parity_filler: yield* filler(v["parity_filler"]) });
});
export const nativeProm9PortDigest = (port: Prom9PortType, value: unknown) => validateNativeProm9Port(port, value).pipe(Either.flatMap(normalized => canonicalNativeProm9Sha256({ schema_version: PROM9_PORT_SCHEMA, port_type: port, value: normalized })));
const wellFormedJson = (value: TaskJson): boolean => typeof value === "string" ? !/[\ud800-\udfff]/u.test(value) : Array.isArray(value) ? value.every(wellFormedJson) : taskJsonRecord(value) ? Object.entries(value).every(([key, child]) => !/[\ud800-\udfff]/u.test(key) && wellFormedJson(child)) : true;
export const canonicalNativeProm9Json = (value: unknown): Either.Either<string, NativeProm9PortError> => !validNativeTaskJson(value) || !wellFormedJson(value) ? fail("value is not UTF-8 canonical JSON") : Either.right(renderNativeTaskJson(value));
export const canonicalNativeProm9Sha256 = (value: unknown) => canonicalNativeProm9Json(value).pipe(Either.map(source => createHash("sha256").update(source, "utf8").digest("hex")));
const stringSchema = Object.freeze({ type: "string", minLength: 1 });
const stringListSchema = Object.freeze({ type: "array", items: stringSchema });
const boolSchema = Object.freeze({ type: "boolean" });
const schema = (properties: Readonly<Record<string, TaskJson>>): TaskJson => freezeJson({ type: "object", additionalProperties: false, required: Object.keys(properties), properties });
const outputSchemas: Readonly<Record<string, TaskJson>> = Object.freeze({
    QueryPlanV1: schema({ request_id: stringSchema, objectives: stringListSchema, required_evidence_types: stringListSchema, constraints: stringListSchema, abstain: boolSchema }),
    BondProposalV1: schema({ request_id: stringSchema, ordered_bond_ids: stringListSchema, bond_potentials: { type: "object", additionalProperties: { type: "number", maximum: 0 } }, evidence_refs: stringListSchema, abstain: boolSchema }),
    AnswerEnvelopeV1: schema({ request_id: stringSchema, answer: { type: "string" }, supporting_evidence_ids: stringListSchema, uncertainty: { type: "string" }, abstain: boolSchema }),
});
export const nativeProm9OutputSchema = (port: string): Either.Either<TaskJson, NativeProm9PortError> => Object.hasOwn(outputSchemas, port) ? Either.right(freezeJson(outputSchemas[port]!)) : fail(`no structured-output schema for port: ${port}`);
export const nativeProm9OutputSchemaSha256 = (port: string) => nativeProm9OutputSchema(port).pipe(Either.flatMap(jsonSchema => canonicalNativeProm9Sha256({ port_schema_version: PROM9_PORT_SCHEMA, port_type: port, json_schema: jsonSchema })));
