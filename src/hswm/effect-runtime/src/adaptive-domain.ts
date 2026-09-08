/**
 * Bounded, observational local adaptation.  This module proposes routes and
 * guards only; it neither executes an effect nor admits a canonical revision.
 * The score is greedy (with an optional bounded bonus), so it makes no optimal
 * exploration guarantee.
 */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
export const ADAPTIVE_SCHEMA_VERSION = "hswm-adaptive-local/v1" as const;
export const ADAPTIVE_SCOPE = "OBSERVATIONAL_LOCAL_ADAPTATION" as const;
export const PROGRAM_SCHEMA_VERSION = "hswm-adaptive-program/v1" as const;
export const MAX_CONTEXT_FIELDS = 8 as const;
export const MAX_FEATURES = 64 as const;
export const MAX_TRACKED_CONTEXTS = 64 as const;
export const MAX_COEFFICIENT = 6 as const;
export type Scalar = null | boolean | string | number;
export type Context = Readonly<Record<string, Scalar>>;
export type Truth = "TRUE" | "FALSE" | "UNKNOWN";
export type Guard = {
    readonly op: "eq";
    readonly left: {
        readonly role: "context";
        readonly field: string;
    };
    readonly right: Scalar;
} | {
    readonly op: "not";
    readonly child: Guard;
} | {
    readonly op: "all" | "any";
    readonly children: ReadonlyArray<Guard>;
};
export type CellKind = "router" | "command" | "llm";
export interface Cell {
    readonly cell_id: string;
    readonly kind: CellKind;
    readonly owner: string;
    readonly input_type: string;
    readonly output_type: string;
    readonly argv?: ReadonlyArray<string>;
    readonly outcome?: "exit_code";
    readonly base_url?: string;
    readonly model?: string;
    readonly api_key_env?: string;
    readonly max_tokens?: number;
}
export interface Route {
    readonly uid: string;
    readonly source: string;
    readonly members: ReadonlyArray<string>;
    readonly reads: ReadonlyArray<string>;
    readonly cost_hint: number;
    readonly guard?: Guard;
}
export interface Program {
    readonly schema_version: typeof PROGRAM_SCHEMA_VERSION;
    readonly graph_id: string;
    readonly root: string;
    readonly context_domain: Readonly<Record<string, ReadonlyArray<Scalar>>>;
    readonly cells: ReadonlyArray<Cell>;
    readonly relations: ReadonlyArray<Route>;
}
export interface AdaptiveModel {
    readonly schema_version: typeof ADAPTIVE_SCHEMA_VERSION;
    readonly scope: typeof ADAPTIVE_SCOPE;
    readonly n: number;
    readonly cost_mean: number;
    readonly features: Readonly<Record<string, number>>;
    readonly context_attempts: Readonly<Record<string, number>>;
}
export class AdaptiveDomainError extends Data.TaggedError("AdaptiveDomainError")<{
    readonly code: "PROGRAM_INVALID" | "CONTEXT_INVALID" | "MODEL_INVALID" | "SELECTION_INVALID" | "OUTCOME_INVALID" | "FEATURE_BOUND" | "CONTEXT_BOUND" | "GUARD_INVALID";
    readonly detail: string;
}> {
}
const fail = (code: AdaptiveDomainError["code"], detail: string): Either.Either<never, AdaptiveDomainError> => Either.left(new AdaptiveDomainError({ code, detail }));
const retypeError = <A>(error: AdaptiveDomainError): Either.Either<A, AdaptiveDomainError> => Either.left(error);
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const own = (value: Record<string, unknown>, keys: ReadonlyArray<string>): boolean => Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
const text = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= 256;
const featureText = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= 2048;
// `context:` plus at most MAX_FEATURES - 1 validated feature keys, separated
// by `|`; this is an index bound, not a public identifier bound.
const MAX_CONTEXT_ATTEMPT_KEY_CHARS = "context:".length + (MAX_FEATURES - 1) * (2048 + "|".length);
const contextAttemptKeyText = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= MAX_CONTEXT_ATTEMPT_KEY_CHARS;
const scalar = (value: unknown): value is Scalar => value === null || typeof value === "boolean" || typeof value === "string" || (typeof value === "number" && Number.isFinite(value));
const sameScalar = (left: Scalar, right: Scalar): boolean => typeof left === typeof right && Object.is(left, right);
const finiteNonnegative = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0;
const number = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const clamp = (value: number, low: number, high: number): number => Math.max(low, Math.min(high, value));
/** Deterministic JSON for the finite scalar surface. */
export const canonicalJson = (value: unknown): Either.Either<string, AdaptiveDomainError> => {
    const visit = (item: unknown, depth: number): string | null => {
        if (depth > 64 || item === undefined || typeof item === "function" || typeof item === "symbol" || typeof item === "bigint")
            return null;
        if (item === null || typeof item === "boolean" || typeof item === "string")
            return JSON.stringify(item);
        if (typeof item === "number")
            return Number.isFinite(item) && !Object.is(item, -0) ? JSON.stringify(item) : null;
        if (Array.isArray(item)) {
            const values = item.map((child) => visit(child, depth + 1));
            return values.some((child) => child === null) ? null : `[${values.join(",")}]`;
        }
        if (!record(item))
            return null;
        const values: string[] = [];
        for (const key of Object.keys(item).sort()) {
            const child = visit(item[key], depth + 1);
            if (child === null)
                return null;
            values.push(`${JSON.stringify(key)}:${child}`);
        }
        return `{${values.join(",")}}`;
    };
    const encoded = visit(value, 0);
    return encoded === null ? fail("CONTEXT_INVALID", "non-canonical JSON value") : Either.right(encoded);
};
export const digest = (value: unknown): Either.Either<string, AdaptiveDomainError> => {
    const encoded = canonicalJson(value);
    return Either.isLeft(encoded) ? encoded : Either.right(createHash("sha256").update(encoded.right).digest("hex"));
};
/** Strict JSON ingress: rejects duplicate object keys before JSON.parse loses them. */
export const parseJson = (textValue: unknown): Either.Either<unknown, AdaptiveDomainError> => {
    if (typeof textValue !== "string")
        return fail("PROGRAM_INVALID", "JSON text type");
    const stack: Array<Set<string>> = [];
    let index = 0;
    const whitespace = (character: string | undefined): boolean => character === " " || character === "\n" || character === "\r" || character === "\t";
    const stringAt = (): string | null => {
        if (textValue[index] !== "\"")
            return null;
        const start = index;
        index += 1;
        while (index < textValue.length) {
            const character = textValue[index] as string;
            if (character === "\"") {
                index += 1;
                return textValue.slice(start, index);
            }
            if (character === "\\") {
                index += 1;
                if (textValue[index] === undefined)
                    return null;
                index += 1;
                continue;
            }
            if (character.charCodeAt(0) < 32)
                return null;
            index += 1;
        }
        return null;
    };
    while (index < textValue.length) {
        while (whitespace(textValue[index]))
            index += 1;
        const character = textValue[index];
        if (character === "{") {
            stack.push(new Set());
            index += 1;
            continue;
        }
        if (character === "}") {
            stack.pop();
            index += 1;
            continue;
        }
        if (character === "," || character === ":" || character === "[" || character === "]") {
            index += 1;
            continue;
        }
        if (character === "\"") {
            const raw = stringAt();
            if (raw === null)
                return fail("PROGRAM_INVALID", "malformed JSON string");
            let next = index;
            while (whitespace(textValue[next]))
                next += 1;
            if (textValue[next] === ":") {
                const current = stack[stack.length - 1];
                const decoded = Either.try({ try: () => JSON.parse(raw) as string, catch: () => new AdaptiveDomainError({ code: "PROGRAM_INVALID", detail: "malformed JSON key" }) });
                if (Either.isLeft(decoded) || current === undefined)
                    return Either.isLeft(decoded) ? decoded : fail("PROGRAM_INVALID", "JSON key outside object");
                if (current.has(decoded.right))
                    return fail("PROGRAM_INVALID", "duplicate JSON key");
                current.add(decoded.right);
            }
            continue;
        }
        index += 1;
    }
    const parsed = Either.try({ try: () => JSON.parse(textValue) as unknown, catch: () => new AdaptiveDomainError({ code: "PROGRAM_INVALID", detail: "malformed JSON" }) });
    if (Either.isLeft(parsed))
        return parsed;
    const finite = (value: unknown, depth: number): boolean => depth <= 64 && (value === null || typeof value === "boolean" || typeof value === "string" || (typeof value === "number" && Number.isFinite(value)) || (Array.isArray(value) && value.every((item) => finite(item, depth + 1))) || (record(value) && Object.values(value).every((item) => finite(item, depth + 1))));
    return finite(parsed.right, 0) ? parsed : fail("PROGRAM_INVALID", "JSON depth or non-finite number");
};
const parseGuard = (raw: unknown, domain: Readonly<Record<string, ReadonlyArray<Scalar>>>, depth = 1): Either.Either<Guard, AdaptiveDomainError> => {
    if (!record(raw) || depth > 4 || !text(raw["op"]))
        return fail("GUARD_INVALID", "guard grammar or bound");
    const op = raw["op"];
    if (op === "eq") {
        if (!own(raw, ["op", "left", "right"]) || !record(raw["left"]) || !own(raw["left"], ["role", "field"]) || raw["left"]["role"] !== "context" || !text(raw["left"]["field"]) || !scalar(raw["right"]))
            return fail("GUARD_INVALID", "eq shape");
        const field = raw["left"]["field"];
        const values = domain[field];
        return values !== undefined && values.some((item) => sameScalar(item, raw["right"] as Scalar))
            ? Either.right({ op: "eq", left: { role: "context", field }, right: raw["right"] as Scalar })
            : fail("GUARD_INVALID", "undeclared field or enum literal");
    }
    if (op === "not") {
        if (!own(raw, ["op", "child"]))
            return fail("GUARD_INVALID", "not shape");
        const child = parseGuard(raw["child"], domain, depth + 1);
        return Either.isLeft(child) ? child : Either.right({ op: "not", child: child.right });
    }
    if ((op === "all" || op === "any") && own(raw, ["op", "children"]) && Array.isArray(raw["children"]) && raw["children"].length > 0) {
        const children: Guard[] = [];
        for (const child of raw["children"]) {
            const parsed = parseGuard(child, domain, depth + 1);
            if (Either.isLeft(parsed))
                return parsed;
            children.push(parsed.right);
        }
        return Either.right({ op, children });
    }
    return fail("GUARD_INVALID", "guard operator or fields");
};
const guardReads = (guard: Guard): ReadonlyArray<string> => guard.op === "eq" ? [guard.left.field] : guard.op === "not" ? guardReads(guard.child) : guard.children.flatMap(guardReads);
export const parseProgram = (raw: unknown): Either.Either<Program, AdaptiveDomainError> => {
    if (!record(raw) || !own(raw, ["schema_version", "graph_id", "root", "context_domain", "cells", "relations"]) || raw["schema_version"] !== PROGRAM_SCHEMA_VERSION || !text(raw["graph_id"]) || !text(raw["root"]) || !record(raw["context_domain"]) || !Array.isArray(raw["cells"]) || !Array.isArray(raw["relations"]))
        return fail("PROGRAM_INVALID", "program envelope");
    const domainEntries = Object.entries(raw["context_domain"]);
    if (domainEntries.length < 1 || domainEntries.length > MAX_CONTEXT_FIELDS)
        return fail("PROGRAM_INVALID", "context field bound");
    const domain: Record<string, ReadonlyArray<Scalar>> = {};
    for (const [key, values] of domainEntries) {
        if (!text(key) || key.length > 128 || !Array.isArray(values) || values.length < 1 || values.length > 16 || values.some((value) => !scalar(value) || (typeof value === "string" && value.length > 256)))
            return fail("PROGRAM_INVALID", "context enum");
        domain[key] = [...values] as Scalar[];
    }
    if (raw["cells"].length < 1 || raw["cells"].length > 64)
        return fail("PROGRAM_INVALID", "cell bound");
    const cells: Cell[] = [];
    const byId = new Map<string, Cell>();
    for (const rawCell of raw["cells"]) {
        if (!record(rawCell) || !text(rawCell["cell_id"]) || !text(rawCell["owner"]) || !text(rawCell["input_type"]) || !text(rawCell["output_type"]) || !["router", "command", "llm"].includes(String(rawCell["kind"])))
            return fail("PROGRAM_INVALID", "cell");
        const kind = rawCell["kind"] as CellKind;
        const base = { cell_id: rawCell["cell_id"] as string, kind, owner: rawCell["owner"] as string, input_type: rawCell["input_type"] as string, output_type: rawCell["output_type"] as string };
        let cell: Cell;
        if (kind === "router" && own(rawCell, ["cell_id", "kind", "owner", "input_type", "output_type"]))
            cell = base;
        else if (kind === "command" && Object.keys(rawCell).every((key) => ["cell_id", "kind", "owner", "input_type", "output_type", "argv", "outcome"].includes(key)) && Array.isArray(rawCell["argv"]) && rawCell["argv"].length > 0 && rawCell["argv"].every((arg) => typeof arg === "string" && arg.length > 0 && !arg.includes("\0") && arg !== "{input}") && (rawCell["outcome"] === undefined || rawCell["outcome"] === "exit_code"))
            cell = { ...base, argv: rawCell["argv"] as string[], ...(rawCell["outcome"] === "exit_code" ? { outcome: "exit_code" as const } : {}) };
        else if (kind === "llm" && Object.keys(rawCell).every((key) => ["cell_id", "kind", "owner", "input_type", "output_type", "base_url", "model", "api_key_env", "max_tokens"].includes(key)) && text(rawCell["base_url"]) && text(rawCell["model"]) && (rawCell["api_key_env"] === undefined || text(rawCell["api_key_env"])) && (rawCell["max_tokens"] === undefined || (Number.isSafeInteger(rawCell["max_tokens"]) && (rawCell["max_tokens"] as number) > 0)))
            cell = { ...base, base_url: rawCell["base_url"] as string, model: rawCell["model"] as string, ...(rawCell["api_key_env"] !== undefined ? { api_key_env: rawCell["api_key_env"] as string } : {}), ...(rawCell["max_tokens"] !== undefined ? { max_tokens: rawCell["max_tokens"] as number } : {}) };
        else
            return fail("PROGRAM_INVALID", "cell kind fields");
        if (byId.has(cell.cell_id))
            return fail("PROGRAM_INVALID", "duplicate cell");
        byId.set(cell.cell_id, cell);
        cells.push(cell);
    }
    const root = byId.get(raw["root"] as string);
    if (root?.kind !== "router")
        return fail("PROGRAM_INVALID", "root router");
    if (raw["relations"].length < 1 || raw["relations"].length > 128)
        return fail("PROGRAM_INVALID", "route bound");
    const relations: Route[] = [];
    const routeIds = new Set<string>();
    for (const rawRoute of raw["relations"]) {
        if (!record(rawRoute) || !["uid", "source", "members", "reads", "cost_hint"].every((key) => Object.hasOwn(rawRoute, key)) || !Object.keys(rawRoute).every((key) => ["uid", "source", "members", "reads", "cost_hint", "guard"].includes(key)) || !text(rawRoute["uid"]) || routeIds.has(rawRoute["uid"] as string) || !text(rawRoute["source"]) || byId.get(rawRoute["source"] as string)?.kind !== "router" || !Array.isArray(rawRoute["members"]) || rawRoute["members"].length < 1 || rawRoute["members"].length > 8 || !rawRoute["members"].every((member) => typeof member === "string" && byId.has(member)) || !Array.isArray(rawRoute["reads"]) || rawRoute["reads"].length < 1 || new Set(rawRoute["reads"]).size !== rawRoute["reads"].length || !rawRoute["reads"].every((field) => typeof field === "string" && domain[field] !== undefined) || !number(rawRoute["cost_hint"]) || rawRoute["cost_hint"] < 0 || rawRoute["cost_hint"] > 3600)
            return fail("PROGRAM_INVALID", "route");
        const members = rawRoute["members"] as string[];
        const source = byId.get(rawRoute["source"] as string) as Cell;
        const first = byId.get(members[0] as string) as Cell;
        const last = byId.get(members[members.length - 1] as string) as Cell;
        if (source.input_type !== first.input_type || source.output_type !== last.output_type || members.some((member, index) => index > 0 && (byId.get(members[index - 1] as string) as Cell).output_type !== (byId.get(member) as Cell).input_type))
            return fail("PROGRAM_INVALID", "route port boundary");
        let guard: Guard | undefined;
        if (rawRoute["guard"] !== undefined && rawRoute["guard"] !== null) {
            const parsed = parseGuard(rawRoute["guard"], domain);
            if (Either.isLeft(parsed))
                return retypeError(parsed.left);
            if (!guardReads(parsed.right).every((field) => (rawRoute["reads"] as unknown[]).includes(field)))
                return fail("PROGRAM_INVALID", "guard reads");
            guard = parsed.right;
        }
        routeIds.add(rawRoute["uid"] as string);
        relations.push({ uid: rawRoute["uid"] as string, source: rawRoute["source"] as string, members, reads: rawRoute["reads"] as string[], cost_hint: rawRoute["cost_hint"] as number, ...(guard === undefined ? {} : { guard }) });
    }
    return Either.right({ schema_version: PROGRAM_SCHEMA_VERSION, graph_id: raw["graph_id"] as string, root: raw["root"] as string, context_domain: domain, cells, relations });
};
export const validateProgram = parseProgram;
const features = (context: Context): Either.Either<ReadonlyArray<string>, AdaptiveDomainError> => {
    const entries = Object.entries(context);
    if (entries.length < 1 || entries.length > MAX_CONTEXT_FIELDS)
        return fail("CONTEXT_INVALID", "context field bound");
    const result: string[] = [];
    for (const [key, value] of entries.sort(([a], [b]) => a.localeCompare(b))) {
        if (!text(key) || key.length > 128 || !scalar(value) || (typeof value === "string" && value.length > 256))
            return fail("CONTEXT_INVALID", "context scalar");
        const encoded = canonicalJson(value);
        if (Either.isLeft(encoded))
            return retypeError(encoded.left);
        const type = value === null ? "NoneType" : typeof value === "string" ? "str" : typeof value === "boolean" ? "bool" : Number.isSafeInteger(value) ? "int" : "float";
        result.push(`value:${key}:${type}:${encoded.right}`);
    }
    return Either.right(["bias", ...result, ...result.flatMap((left, index) => result.slice(index + 1).map((right) => `pair:${left}&${right}`))]);
};
const validateModel = (model: AdaptiveModel): Either.Either<AdaptiveModel, AdaptiveDomainError> => {
    if (!record(model) || !own(model, ["schema_version", "scope", "n", "cost_mean", "features", "context_attempts"]) || !record(model["features"]) || !record(model["context_attempts"]))
        return fail("MODEL_INVALID", "adaptive model");
    const features = model["features"];
    const attempts = model["context_attempts"];
    if (model["schema_version"] !== ADAPTIVE_SCHEMA_VERSION || model["scope"] !== ADAPTIVE_SCOPE || !Number.isSafeInteger(model["n"]) || model["n"] < 0 || !finiteNonnegative(model["cost_mean"]) || !Object.hasOwn(features, "bias") || Object.keys(features).length > MAX_FEATURES || Object.keys(attempts).length > MAX_TRACKED_CONTEXTS || !Object.entries(features).every(([key, value]) => featureText(key) && number(value) && Math.abs(value) <= MAX_COEFFICIENT) || !Object.entries(attempts).every(([key, value]) => contextAttemptKeyText(key) && Number.isSafeInteger(value) && value >= 0))
        return fail("MODEL_INVALID", "adaptive model");
    return Either.right(model);
};
const probability = (model: AdaptiveModel, values: ReadonlyArray<string>): number => 1 / (1 + Math.exp(-clamp(values.reduce((sum, feature) => sum + (model.features[feature] ?? 0), 0), -MAX_COEFFICIENT, MAX_COEFFICIENT)));
const contextKey = (values: ReadonlyArray<string>): string => `context:${values.slice(1).join("|")}`;
export const initialModel = (): AdaptiveModel => ({ schema_version: ADAPTIVE_SCHEMA_VERSION, scope: ADAPTIVE_SCOPE, n: 0, cost_mean: 0, features: { bias: 0 }, context_attempts: {} });
export const predict = (model: AdaptiveModel, context: Context): Either.Either<number, AdaptiveDomainError> => { const valid = validateModel(model); const valueFeatures = features(context); return Either.isLeft(valid) ? retypeError(valid.left) : Either.isLeft(valueFeatures) ? retypeError(valueFeatures.left) : Either.right(probability(valid.right, valueFeatures.right)); };
export interface SelectionInputs {
    readonly cost_hint: number;
    readonly budget: number;
    readonly exploration?: number;
    readonly total_attempts?: number;
}
export const selectionScore = (model: AdaptiveModel, context: Context, input: SelectionInputs): Either.Either<number, AdaptiveDomainError> => { const valid = validateModel(model); const valueFeatures = features(context); const exploration = input.exploration ?? 0; const attempts = input.total_attempts ?? 0; if (Either.isLeft(valid))
    return retypeError(valid.left); if (Either.isLeft(valueFeatures))
    return retypeError(valueFeatures.left); if (!finiteNonnegative(input.cost_hint) || !finiteNonnegative(input.budget) || !finiteNonnegative(exploration) || exploration > 1 || !Number.isSafeInteger(attempts) || attempts < 0)
    return fail("SELECTION_INVALID", "selection inputs"); const cost = valid.right.n === 0 ? input.cost_hint : valid.right.cost_mean; return Either.right(clamp(probability(valid.right, valueFeatures.right) - Math.min(1, cost / Math.max(1, input.budget)) + exploration / Math.sqrt(1 + attempts + (valid.right.context_attempts[contextKey(valueFeatures.right)] ?? 0)), -1, 1)); };
export const updateModel = (model: AdaptiveModel, context: Context, outcome: {
    readonly success: boolean;
    readonly cost: number;
}): Either.Either<AdaptiveModel, AdaptiveDomainError> => { const valid = validateModel(model); const valueFeatures = features(context); if (Either.isLeft(valid))
    return retypeError(valid.left); if (Either.isLeft(valueFeatures))
    return retypeError(valueFeatures.left); if (typeof outcome.success !== "boolean" || !finiteNonnegative(outcome.cost))
    return fail("OUTCOME_INVALID", "outcome"); const weights = Object.fromEntries(Object.entries(valid.right.features)) as Record<string, number>; const rate = .4 / Math.sqrt(1 + valid.right.n); const error = (outcome.success ? 1 : 0) - probability(valid.right, valueFeatures.right); for (const feature of valueFeatures.right) {
    if (!Object.hasOwn(weights, feature) && Object.keys(weights).length >= MAX_FEATURES)
        return fail("FEATURE_BOUND", "adaptive feature bound");
    weights[feature] = clamp((weights[feature] ?? 0) + rate * error, -MAX_COEFFICIENT, MAX_COEFFICIENT);
} const attempts = Object.fromEntries(Object.entries(valid.right.context_attempts)) as Record<string, number>; const key = contextKey(valueFeatures.right); if (!Object.hasOwn(attempts, key) && Object.keys(attempts).length >= MAX_TRACKED_CONTEXTS)
    return fail("CONTEXT_BOUND", "adaptive context bound"); attempts[key] = (attempts[key] ?? 0) + 1; const n = valid.right.n + 1; return Either.right({ schema_version: ADAPTIVE_SCHEMA_VERSION, scope: ADAPTIVE_SCOPE, n, cost_mean: valid.right.cost_mean + (outcome.cost - valid.right.cost_mean) / n, features: weights, context_attempts: attempts }); };
export const evaluateGuard = (guard: Guard, context: Context): Truth => { const evaluate = (node: Guard): Truth => node.op === "eq" ? (Object.hasOwn(context, node.left.field) ? (sameScalar(context[node.left.field] as Scalar, node.right) ? "TRUE" : "FALSE") : "UNKNOWN") : node.op === "not" ? ({ TRUE: "FALSE", FALSE: "TRUE", UNKNOWN: "UNKNOWN" } as const)[evaluate(node.child)] : (() => { const values = node.children.map(evaluate); const decisive = node.op === "all" ? "FALSE" : "TRUE"; const neutral = node.op === "all" ? "TRUE" : "FALSE"; return values.includes(decisive) ? decisive : values.every((value) => value === neutral) ? neutral : "UNKNOWN"; })(); return evaluate(guard); };
/**
 * A learned selector may only narrow a parent's mandatory eligibility guard.
 * Parent revision/digest binding and route member preservation are runtime
 * responsibilities; this pure helper preserves the guard semantics.
 */
export const specializeGuard = (parent: Guard | undefined, selector: Guard): Guard => parent === undefined
    ? selector
    : { op: "all", children: [parent, selector] };
export interface RouteModel {
    readonly route: Route;
    readonly model: AdaptiveModel;
    readonly active: boolean;
}
export interface Plan {
    readonly status: "PLANNED" | "WITHHOLD";
    readonly selected: PlanChoice | null;
    readonly choices: ReadonlyArray<PlanChoice>;
    readonly rejected: ReadonlyArray<PlanRejection>;
    readonly selection: PlanSelection;
    readonly claim: "LOCAL_ADAPTATION_NOT_CAUSAL_IDENTIFICATION";
}
export interface PlanChoice {
    readonly uid: string;
    readonly score: number;
    /** Local model output; it is not a calibrated success probability. */
    readonly predicted_success: number;
    readonly reads: ReadonlyArray<string>;
    readonly members: ReadonlyArray<string>;
    readonly observations: number;
}
export interface PlanRejection {
    readonly uid: string;
    /** First applicable reason in this stable precedence: active, source, budget, permission, guard. */
    readonly reason: "INACTIVE" | "SOURCE" | "BUDGET" | "PERMISSION" | "GUARD_FALSE" | "GUARD_UNKNOWN";
}
export interface PlanSelection {
    readonly rule: "SCORE_DESC_THEN_UID_ASC" | "FORCE_ELIGIBLE_ROUTE";
    /** Eligible UIDs tied with the selected route's score. */
    readonly tie_uids: ReadonlyArray<string>;
    /** Top-ranked eligible UIDs tied before an eligible forced route is applied. */
    readonly highest_score_tie_uids: ReadonlyArray<string>;
}
export const plan = (program: Program, routes: ReadonlyArray<RouteModel>, context: Context, input: {
    readonly budget: number;
    readonly allowed?: ReadonlySet<string>;
    readonly exploration?: number;
    readonly force_route?: string;
}): Either.Either<Plan, AdaptiveDomainError> => { const parsed = parseProgram(program); if (Either.isLeft(parsed))
    return retypeError(parsed.left); if (!finiteNonnegative(input.budget) || input.budget <= 0 || input.budget > 3600)
    return fail("SELECTION_INVALID", "budget"); const allowed = input.allowed ?? new Set(parsed.right.cells.map((cell) => cell.cell_id)); const total = routes.reduce((sum, item) => sum + item.model.n, 0); const choices: PlanChoice[] = []; const rejected: PlanRejection[] = []; for (const item of routes) {
    const route = item.route;
    if (!item.active) {
        rejected.push({ uid: route.uid, reason: "INACTIVE" });
        continue;
    }
    if (route.source !== parsed.right.root) {
        rejected.push({ uid: route.uid, reason: "SOURCE" });
        continue;
    }
    if (route.cost_hint > input.budget) {
        rejected.push({ uid: route.uid, reason: "BUDGET" });
        continue;
    }
    if (route.members.some((member) => !allowed.has(member))) {
        rejected.push({ uid: route.uid, reason: "PERMISSION" });
        continue;
    }
    if (route.guard !== undefined) {
        const guard = evaluateGuard(route.guard, context);
        if (guard !== "TRUE") {
            rejected.push({ uid: route.uid, reason: guard === "FALSE" ? "GUARD_FALSE" : "GUARD_UNKNOWN" });
            continue;
        }
    }
    const read = Object.fromEntries(route.reads.map((field) => [field, context[field] as Scalar]));
    const score = selectionScore(item.model, read, { cost_hint: route.cost_hint, budget: input.budget, ...(input.exploration === undefined ? {} : { exploration: input.exploration }), total_attempts: total });
    const predicted = predict(item.model, read);
    if (Either.isLeft(score))
        return retypeError(score.left);
    if (Either.isLeft(predicted))
        return retypeError(predicted.left);
    choices.push({ uid: route.uid, score: score.right, predicted_success: predicted.right, reads: route.reads, members: route.members, observations: item.model.n });
} choices.sort((left, right) => right.score - left.score || left.uid.localeCompare(right.uid)); rejected.sort((left, right) => left.uid.localeCompare(right.uid)); const ranked = choices[0] ?? null; const selected = input.force_route === undefined ? ranked : (choices.find((choice) => choice.uid === input.force_route || choice.uid === `relation:${input.force_route}`) ?? null); if (input.force_route !== undefined && selected === null)
    return fail("SELECTION_INVALID", "forced route is not eligible"); const tied = (choice: PlanChoice | null): ReadonlyArray<string> => choice === null ? [] : choices.filter((candidate) => candidate.score === choice.score).map((candidate) => candidate.uid); return Either.right({ status: selected === null ? "WITHHOLD" : "PLANNED", selected, choices, rejected, selection: { rule: input.force_route === undefined ? "SCORE_DESC_THEN_UID_ASC" : "FORCE_ELIGIBLE_ROUTE", tie_uids: tied(selected), highest_score_tie_uids: tied(ranked) }, claim: "LOCAL_ADAPTATION_NOT_CAUSAL_IDENTIFICATION" }); };
export interface GuardExample {
    readonly values: Context;
    readonly outcome: boolean;
    readonly source: string;
}
export type GuardProposal = {
    readonly status: "WITHHOLD";
    readonly reason: string;
    readonly credit: "UNIDENTIFIED_CREDIT";
} | {
    readonly status: "PROPOSED_NOT_ADMITTED";
    readonly relation_ast: Guard;
    readonly parent_revision: string | null;
    readonly proposal_source: string;
    readonly origin: "BOUNDED_GRAMMAR_SYNTHESIS";
    readonly credit: "UNIDENTIFIED_CREDIT";
};
/** A bounded finite grammar synthesizer; a proposal is never admission. */
export const proposeSpecialization = (domain: Readonly<Record<string, ReadonlyArray<Scalar>>>, examples: ReadonlyArray<GuardExample>, parent: string | null = null): Either.Either<GuardProposal, AdaptiveDomainError> => {
    if (examples.length < 4 || examples.length > 512 || !examples.some((example) => example.outcome) || !examples.some((example) => !example.outcome))
        return Either.right({ status: "WITHHOLD", reason: "insufficient_mixed_public_contexts", credit: "UNIDENTIFIED_CREDIT" });
    const distinct = new Map<string, boolean>();
    for (const example of examples) {
        if (!record(example.values) || !text(example.source) || typeof example.outcome !== "boolean" || Object.keys(example.values).length !== Object.keys(domain).length || Object.entries(domain).some(([key, values]) => !values.some((value) => sameScalar(value, example.values[key] as Scalar))))
            return fail("GUARD_INVALID", "public examples");
        const encoded = canonicalJson(example.values);
        if (Either.isLeft(encoded))
            return retypeError(encoded.left);
        const prior = distinct.get(encoded.right);
        if (prior !== undefined && prior !== example.outcome)
            return Either.right({ status: "WITHHOLD", reason: "conflicting_evidence", credit: "UNIDENTIFIED_CREDIT" });
        distinct.set(encoded.right, example.outcome);
    }
    if (distinct.size < 4)
        return Either.right({ status: "WITHHOLD", reason: "insufficient_mixed_public_contexts", credit: "UNIDENTIFIED_CREDIT" });
    const leaves = Object.entries(domain).sort(([left], [right]) => left.localeCompare(right)).flatMap(([field, values]) => values.map((right) => ({ op: "eq" as const, left: { role: "context" as const, field }, right })));
    if (leaves.length > 128)
        return fail("GUARD_INVALID", "search domain bound");
    const negated = leaves.map((child) => ({ op: "not" as const, child }));
    const pairs = (op: "all" | "any") => leaves.flatMap((left, index) => leaves.slice(index + 1).map((right) => ({ op, children: [left, right] } as Guard)));
    const candidates: ReadonlyArray<Guard> = [...leaves, ...negated, ...pairs("all"), ...pairs("any")];
    const matches: Guard[] = [];
    for (const candidate of candidates.slice(0, 256)) {
        if (examples.every((example) => (evaluateGuard(candidate, example.values) === "TRUE") === example.outcome))
            matches.push(candidate);
        if (matches.length === 8)
            break;
    }
    const candidate = matches[0];
    if (candidate === undefined)
        return Either.right({ status: "WITHHOLD", reason: "no_nonconstant_bounded_candidate", credit: "UNIDENTIFIED_CREDIT" });
    const source = digest(examples);
    return Either.isLeft(source) ? retypeError(source.left) : Either.right({ status: "PROPOSED_NOT_ADMITTED", relation_ast: candidate, parent_revision: parent, proposal_source: source.right, origin: "BOUNDED_GRAMMAR_SYNTHESIS", credit: "UNIDENTIFIED_CREDIT" });
};
