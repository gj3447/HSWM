/**
 * Native, pure conditional-task proposal core.  It consumes caller-owned JSON
 * only; it cannot execute a tool, admit a canonical revision, or assign causal
 * credit.  Effects live in native-task-process.ts.
 */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
import { isTaskNumber, taskNumberValue, taskJsonRecord, taskTextCompare, renderNativeTaskJson, sameNativeTaskValue, validNativeTaskJson, type TaskNumber, type TaskJson } from "./native-task-json-domain.js";
export class NativeTaskError extends Data.TaggedError("NativeTaskError")<{
    readonly detail: string;
}> {
}
export type Json = TaskJson;
type Obj = {
    readonly [key: string]: Json;
};
type Key = readonly [
    string,
    string
];
type Domain = ReadonlyMap<string, {
    readonly key: Key;
    readonly values: ReadonlyArray<Json>;
}>;
const fail = <A = never>(detail: string): Either.Either<A, NativeTaskError> => Either.left(new NativeTaskError({ detail }));
const record = taskJsonRecord;
const compare = taskTextCompare;
const same = sameNativeTaskValue;
const canonical = (v: Json): string => renderNativeTaskJson(v);
const relationJson = (v: Json): string => renderNativeTaskJson(v, "relation");
export const nativeTaskDigest = (v: Json): string => createHash("sha256").update(canonical(v), "utf8").digest("hex");
const exact = (v: Json, required: readonly string[], optional: readonly string[] = []): boolean => record(v) && Object.keys(v).every((k) => required.includes(k) || optional.includes(k)) && required.every((k) => Object.hasOwn(v, k));
const text = (v: Json): v is string => typeof v === "string" && v.trim().length > 0;
const retype = <A>(value: Either.Either<unknown, NativeTaskError>): Either.Either<A, NativeTaskError> => Either.isLeft(value) ? Either.left(value.left) : fail("unexpected successful error branch");
const key = (role: Json, field: Json): Either.Either<Key, NativeTaskError> => text(role) && text(field) ? Either.right([role, field]) : fail("expected nonempty text");
const keyId = (k: Key): string => JSON.stringify(k);
const idKey = (id: string): Key => JSON.parse(id) as Key;
const compareIds = (a: string, b: string): number => { const x = idKey(a), y = idKey(b); return compare(x[0], y[0]) || compare(x[1], y[1]); };
const domain = (rows: Json): Either.Either<Domain, NativeTaskError> => {
    if (!Array.isArray(rows) || rows.length === 0)
        return fail("domain");
    const result = new Map<string, {
        key: Key;
        values: readonly Json[];
    }>();
    for (const row of rows) {
        if (!exact(row, ["role", "field", "values"]) || !record(row) || !Array.isArray(row["values"]) || row["values"].length === 0 || !validNativeTaskJson(row["values"]))
            return fail("invalid JSON object fields");
        const parsed = key(row["role"]!, row["field"]!);
        if (Either.isLeft(parsed))
            return retype(parsed);
        const id = keyId(parsed.right);
        if (result.has(id))
            return fail("duplicate role/field");
        result.set(id, Object.freeze({ key: parsed.right, values: Object.freeze([...row["values"]]) }));
    }
    return Either.right(result);
};
const values = (rows: Json, d: Domain): Either.Either<ReadonlyMap<string, Json>, NativeTaskError> => {
    if (!Array.isArray(rows))
        return fail("expected JSON list");
    const result = new Map<string, Json>();
    for (const row of rows) {
        if (!exact(row, ["role", "field", "value"]) || !record(row))
            return fail("invalid JSON object fields");
        const parsed = key(row["role"]!, row["field"]!);
        if (Either.isLeft(parsed))
            return retype(parsed);
        const id = keyId(parsed.right);
        const entry = d.get(id);
        if (entry === undefined || result.has(id))
            return fail(entry === undefined ? "example enum" : "duplicate role/field");
        if (!entry.values.some((item) => same(item, row["value"]!)))
            return fail("example enum");
        result.set(id, row["value"]!);
    }
    return result.size === d.size ? Either.right(result) : fail("incomplete public example");
};
type Ast = {
    readonly op: "eq";
    readonly left: {
        readonly role: string;
        readonly field: string;
    };
    readonly right: Json;
} | {
    readonly op: "all" | "any";
    readonly children: readonly Ast[];
} | {
    readonly op: "not";
    readonly child: Ast;
};
const ast = (v: Json, d: Domain): Either.Either<Ast, NativeTaskError> => {
  let count = 0;
  const visit = (v: Json, depth: number): Either.Either<Ast, NativeTaskError> => {
    count++;
    if (!record(v) || depth > 4 || count > 31)
        return fail("AST bound or type");
    if (v["op"] === "eq" && exact(v, ["op", "left", "right"]) && record(v["left"]!) && exact(v["left"]!, ["role", "field"])) {
        const parsed = key(((v["left"] as Obj)["role"]!), ((v["left"] as Obj)["field"]!));
        if (Either.isLeft(parsed))
            return fail("field reference");
        const entry = d.get(keyId(parsed.right));
        if (entry === undefined || !entry.values.some((item) => same(item, v["right"]!)))
            return fail("undeclared field or non-enum literal");
        return Either.right({ op: "eq", left: { role: parsed.right[0], field: parsed.right[1] }, right: v["right"]! });
    }
    if (v["op"] === "not" && exact(v, ["op", "child"])) return visit(v["child"]!, depth + 1).pipe(Either.map(child => ({ op: "not" as const, child })));
    if ((v["op"] === "all" || v["op"] === "any") && exact(v, ["op", "children"]) && Array.isArray(v["children"]) && v["children"].length > 0) {
        const children: Ast[] = [];
        for (const child of v["children"]) {
            const checked = visit(child, depth + 1);
            if (Either.isLeft(checked))
                return checked;
            children.push(checked.right);
        }
        return Either.right({ op: v["op"], children });
    }
    return fail("AST fields");
  };
  return visit(v, 1);
};
const matches = (node: Ast, assignment: ReadonlyMap<string, Json>): boolean => node.op === "eq" ? same(assignment.get(keyId([node.left.role, node.left.field]))!, node.right) : node.op === "not" ? !matches(node.child, assignment) : node.op === "all" ? node.children.every(child => matches(child, assignment)) : node.children.some(child => matches(child, assignment));
function* combinations<A>(items: readonly A[], width: number, start = 0, prefix: readonly A[] = []): Generator<readonly A[]> {
  if (prefix.length === width) { yield prefix; return; }
  for (let index = start; index < items.length; index++) yield* combinations(items, width, index + 1, [...prefix, items[index]!]);
}
function* candidateGroups<A>(items: readonly A[]): Generator<readonly A[]> { for (const width of [1,2,3]) yield* combinations(items, width); }
/** Exact bounded conjunction candidate contract shared by task CLI and future Effect services. */
export const synthesizeNativeTask = (input: Json): Either.Either<Json, NativeTaskError> => {
    if (!exact(input, ["domain", "examples"], ["parent", "search_budget", "candidate_limit", "resume_cursor"]) || !record(input))
        return fail("invalid JSON object fields");
    const d = domain(input["domain"]!);
    if (Either.isLeft(d))
        return retype(d);
    if (!Array.isArray(input["examples"]) || input["examples"].length === 0 || input["examples"].length > 512)
        return fail("examples or search budget");
    const budget = input["search_budget"] === undefined ? 256 : input["search_budget"];
    const limit = input["candidate_limit"] === undefined ? 8 : input["candidate_limit"];
    if (typeof budget !== "number" || typeof limit !== "number" || !Number.isInteger(budget) || budget < 1 || budget > 4096 || !Number.isInteger(limit) || limit < 1 || limit > 8 || (input["parent"] !== undefined && input["parent"] !== null && !text(input["parent"]!)))
        return fail("examples or search budget");
    const history: {
        values: ReadonlyMap<string, Json>;
        outcome: boolean;
        source: string;
    }[] = [];
    const seen = new Map<string, boolean>();
    for (const row of input["examples"]) {
        if (!exact(row, ["values", "outcome", "source"]) || !record(row) || typeof row["outcome"] !== "boolean" || !text(row["source"]!))
            return fail("public example schema");
        const assignment = values(row["values"]!, d.right);
        if (Either.isLeft(assignment))
            return retype(assignment);
        const encoded = nativeTaskDigest([...assignment.right.entries()].sort(([a], [b]) => compareIds(a, b)).map(([id, value]) => [idKey(id), value]));
        const prior = seen.get(encoded);
        if (prior !== undefined && prior !== row["outcome"])
            return Either.right({ status: "REOPEN", reason: "conflicting_evidence", candidates: [], stop_reason: "CONFLICTING_EVIDENCE", search_complete: false, truncated: false, resume_cursor: null });
        seen.set(encoded, row["outcome"]);
        history.push({ values: assignment.right, outcome: row["outcome"], source: row["source"] });
    }
    const leaves: Ast[] = [...d.right.values()].sort((a, b) => compareIds(keyId(a.key), keyId(b.key))).flatMap((entry) => entry.values.map((right) => ({ op: "eq" as const, left: { role: entry.key[0], field: entry.key[1] }, right })));
    if (d.right.size > 64 || leaves.length > 128)
        return fail("search domain bound");
    const spaceSize = leaves.length + leaves.length * (leaves.length - 1) / 2 + leaves.length * (leaves.length - 1) * (leaves.length - 2) / 6;
    const lineage = nativeTaskDigest(history.map((item) => ({ values: [...item.values.entries()].sort(([a], [b]) => compareIds(a, b)).map(([id, value]) => [idKey(id), value]), outcome: item.outcome, source: item.source })));
    const cursorBinding = nativeTaskDigest({ domain: [...d.right.values()].sort((a, b) => compareIds(keyId(a.key), keyId(b.key))).map((entry) => [[entry.key[0], entry.key[1]], [...entry.values]]), history: lineage, parent: input["parent"] ?? null, grammar: "conjunction-equality-width-1..3/v1" });
    let offset = 0;
    const supplied = input["resume_cursor"];
    if (supplied !== undefined && supplied !== null) {
        if (!exact(supplied, ["version", "binding", "offset", "integrity"]) || !record(supplied) || supplied["version"] !== 1 || supplied["binding"] !== cursorBinding || !Number.isInteger(supplied["offset"]) || (supplied["offset"] as number) < 0 || (supplied["offset"] as number) >= spaceSize || supplied["integrity"] !== nativeTaskDigest({ version: 1, binding: cursorBinding, offset: supplied["offset"]! }))
            return fail("stale or tampered resume cursor");
        offset = supplied["offset"] as number;
    }
    const candidates: Json[] = [];
    let examined = 0;
    let index = offset;
    let stop = "SPACE_EXHAUSTED";
    let skipped = 0;
    for (const group of candidateGroups(leaves)) {
        if (skipped++ < offset) continue;
        if (examined === budget) {
            stop = "SEARCH_BUDGET";
            break;
        }
        ;
        index++;
        examined++;
        const relation: Ast = group.length === 1 ? group[0]! : { op: "all", children: group };
        if (history.every((entry) => matches(relation, entry.values) === entry.outcome)) {
            candidates.push({ relation_ast: relation, parent_revision: input["parent"] ?? null, input_provenance_digest: lineage, status: "PROPOSED_NOT_ADMITTED", origin: "BOUNDED_GRAMMAR_SYNTHESIS", other_remainder: "OPEN", credit: "UNIDENTIFIED_CREDIT" });
            if (candidates.length >= limit && index < spaceSize) {
                stop = "CANDIDATE_LIMIT";
                break;
            }
        }
    }
    const complete = index === spaceSize;
    const cursor = complete ? null : { version: 1, binding: cursorBinding, offset: index, integrity: nativeTaskDigest({ version: 1, binding: cursorBinding, offset: index }) };
    return Either.right({ status: "PROPOSED_NOT_ADMITTED", candidates, examined, input_provenance_digest: lineage, stop_reason: stop, search_complete: complete, truncated: !complete, resume_cursor: cursor, candidate_space_size: spaceSize, search_offset: offset, enumeration_progress: offset + examined });
};
/** Parses a declared relation AST for callers; no effectful action surface exists. */
export const validateNativeTaskRelation = (input: Json): Either.Either<Json, NativeTaskError> => {
    if (!exact(input, ["domain", "ast"]) || !record(input))
        return fail("invalid JSON object fields");
    const d = domain(input["domain"]!);
    if (Either.isLeft(d))
        return retype(d);
    const checked = ast(input["ast"]!, d.right);
    return Either.isLeft(checked) ? retype(checked) : Either.right(checked.right as unknown as Json);
};
const reads = (node: Ast): readonly Key[] => node.op === "eq" ? [[node.left.role, node.left.field]] : node.op === "not" ? reads(node.child) : [...new Map(node.children.flatMap(reads).map((item) => [keyId(item), item])).values()].sort((a, b) => compareIds(keyId(a), keyId(b)));
const truth = (node: Ast, observations: ReadonlyMap<string, {
    readonly value: Json;
    readonly revision: string;
    readonly expires: TaskNumber;
    readonly source: string;
}>, now: TaskNumber, revision: string): "TRUE" | "FALSE" | "UNKNOWN" => {
    if (node.op === "eq") {
        const observed = observations.get(keyId([node.left.role, node.left.field]));
        return observed === undefined || observed.revision !== revision || taskNumberValue(now) >= taskNumberValue(observed.expires) ? "UNKNOWN" : same(observed.value, node.right) ? "TRUE" : "FALSE";
    }
    if (node.op === "not") { const child = truth(node.child, observations, now, revision); return child === "TRUE" ? "FALSE" : child === "FALSE" ? "TRUE" : "UNKNOWN"; }
    const children = node.children.map((child) => truth(child, observations, now, revision));
    const decisive = node.op === "all" ? "FALSE" : "TRUE", neutral = node.op === "all" ? "TRUE" : "FALSE";
    return children.includes(decisive) ? decisive : children.every(child => child === neutral) ? neutral : "UNKNOWN";
};
const parseReads = (input: Json, d: Domain): Either.Either<ReadonlySet<string>, NativeTaskError> => { if (!Array.isArray(input))
    return fail("expected JSON list"); const result = new Set<string>(); for (const row of input) {
    if (!Array.isArray(row) || row.length !== 2) {
        return fail("expected [role, field] reference");
    }
    const parsed = key(row[0]!, row[1]!);
    if (Either.isLeft(parsed))
        return retype(parsed);
    const id = keyId(parsed.right);
    if (!d.has(id) || result.has(id))
        return fail(!d.has(id) ? "undeclared allowed read" : "duplicate read reference");
    result.add(id);
} return Either.right(result); };
/** Pure selected-relation preview: all actions remain proposals and never execute. */
export const previewNativeTask = (input: Json): Either.Either<Json, NativeTaskError> => {
    if (!exact(input, ["domain", "relation", "observations", "action", "checks"]) || !record(input) || !record(input["relation"]!) || !record(input["checks"]!))
        return fail("invalid JSON object fields");
    const d = domain(input["domain"]!);
    if (Either.isLeft(d)) return retype(d);
    const relation = input["relation"]!, checks = input["checks"]!;
    if (!exact(relation, ["uid", "revision", "ast", "source"]) || !text(relation["uid"]!) || !text(relation["revision"]!) || !text(relation["source"]!) || !text(input["action"]!)) return fail("relation structure or provenance");
    const parsed = ast(relation["ast"]!, d.right);
    if (Either.isLeft(parsed)) return retype(parsed);
    if (!exact(checks, ["scope", "expected_scope", "revision", "expected_revision", "now", "allowed_reads", "permitted", "available", "costs", "budget", "source"], ["exited", "conflict"])) return fail("invalid JSON object fields");
    if (!text(checks["source"]!)) return fail("missing input provenance");
    const exited = checks["exited"] ?? false, conflict = checks["conflict"] ?? false;
    if (!finiteNumber(checks["now"]!) || !text(checks["revision"]!) || !text(checks["expected_revision"]!) || !text(checks["scope"]!) || !text(checks["expected_scope"]!) || typeof exited !== "boolean" || typeof conflict !== "boolean" || checks["exited"] === null || checks["conflict"] === null) return fail("current observation context");
    const costs = checks["costs"]!;
    if (!record(costs) || !finiteNumber(checks["budget"]!) || taskNumberValue(checks["budget"]) < 0 || Object.entries(costs).some(([action, cost]) => !text(action) || !finiteNumber(cost) || taskNumberValue(cost) < 0)) return fail("invalid budget or cost");
    if (!Array.isArray(checks["permitted"]) || !Array.isArray(checks["available"]) || !checks["permitted"].every(text) || !checks["available"].every(text)) return fail("invalid action set");
    const permitted = new Set(checks["permitted"]), available = new Set(checks["available"]);
    if (!Array.isArray(input["observations"])) return fail("expected JSON list");
    const allowed = parseReads(checks["allowed_reads"]!, d.right);
    if (Either.isLeft(allowed)) return retype(allowed);
    const observations = new Map<string, {
        value: Json;
        revision: string;
        expires: TaskNumber;
        source: string;
    }>();
    for (const row of input["observations"]) {
        if (!exact(row, ["role", "field", "value", "revision", "expires_at", "source"]) || !record(row))
            return fail("invalid JSON object fields");
        const k = key(row["role"]!, row["field"]!);
        if (Either.isLeft(k))
            return retype(k);
        const entry = d.right.get(keyId(k.right));
        if (entry === undefined || !allowed.right.has(keyId(k.right)) || observations.has(keyId(k.right)) || !entry.values.some((v) => same(v, row["value"]!)) || !text(row["revision"]!) || !text(row["source"]!) || !finiteNumber(row["expires_at"]!))
            return fail("invalid observation value or provenance");
        observations.set(keyId(k.right), { value: row["value"]!, revision: row["revision"]!, expires: row["expires_at"]!, source: row["source"]! });
    }
    const declared = reads(parsed.right);
    if (!declared.every((item) => allowed.right.has(keyId(item))))
        return fail("unauthorized read");
    if (!Object.hasOwn(costs, input["action"]!) || !Object.hasOwn(costs, "OBSERVE")) return fail("undeclared action cost");
    const now = checks["now"] as TaskNumber;
    const observationDigest = (observed: {readonly value: Json; readonly revision: string; readonly expires: TaskNumber; readonly source: string}): string => nativeTaskDigest({ value: observed.value, revision: observed.revision, expires_at: observed.expires, source: observed.source });
    const trace = declared.map(item => { const observed = observations.get(keyId(item)); const fresh = observed !== undefined && observed.revision === checks["revision"] && taskNumberValue(now) < taskNumberValue(observed.expires); return { field: [item[0], item[1]], source: observed?.source ?? null, revision: observed?.revision ?? null, observation_digest: observed === undefined ? null : observationDigest(observed), fresh }; });
    const ref: Json[] = [relation["uid"]!, relation["revision"]!, nativeTaskDigest([relationJson(relation["ast"]!), relation["source"]!])];
    const binding = nativeTaskDigest({ relations: [ref], rules: [{priority: 0, ref, expected: "TRUE", reads: declared, action: input["action"]!, unknown: declared}], domain: [...d.right.values()].sort((a,b) => compareIds(keyId(a.key),keyId(b.key))).map(entry => [entry.key, entry.values]), costs, compiler: "conditional-preview/v1", scope: checks["expected_scope"]!, revision: checks["expected_revision"]!, source: checks["source"]! });
    const stepInputDigest = nativeTaskDigest({preview_uid: binding, scope: checks["scope"]!, expected_scope: checks["expected_scope"]!, revision: checks["revision"]!, expected_revision: checks["expected_revision"]!, now, budget: checks["budget"]!, costs, allowed_reads: [...allowed.right].sort(compareIds).map(id => idKey(id)), permitted: [...permitted].sort(compare), available: [...available].sort(compare), exited, conflict, source: checks["source"]!, observations: [...observations].sort(([a],[b]) => compareIds(a,b)).map(([id, observation]) => ({field: idKey(id), digest: observationDigest(observation)}))});
    const state = exited ? "cell_exit" : checks["scope"] !== checks["expected_scope"] ? "scope_mismatch" : checks["revision"] !== checks["expected_revision"] ? "stale_revision" : conflict ? "conflicting_evidence" : null;
    const observedTruth = state === null ? truth(parsed.right, observations, now, checks["revision"]!) : "UNKNOWN";
    const rule = { priority: 0, relation_ref: ref, truth: observedTruth };
    const base = { status: "DESIGN_ONLY_NO_EXECUTION", preview_uid: binding, step_input_digest: stepInputDigest, hypothetical_read_set: state === null ? trace : [], input_provenance: checks["source"]!, credit: "UNIDENTIFIED_CREDIT", evaluated_rule_provenance: state === null ? [rule] : [], selected_rule_provenance: state === null && observedTruth !== "FALSE" ? rule : null };
    if (state !== null) return Either.right({ ...base, hypothetical_next_step: { kind: "WITHHOLD", reason: state } });
    if (observedTruth === "FALSE") return Either.right({...base, hypothetical_next_step: {kind: "WITHHOLD", reason: "no_applicable_rule"}});
    const action = observedTruth === "UNKNOWN" ? "OBSERVE" : input["action"]!, cost = costs[action] as TaskNumber;
    if (!permitted.has(action) || !available.has(action) || taskNumberValue(cost) > taskNumberValue(checks["budget"]!)) return Either.right({...base, hypothetical_next_step: {kind: "WITHHOLD", reason: observedTruth === "UNKNOWN" ? "missing_prerequisite" : "permission_capability_or_budget"}});
    const nextStep: Json = observedTruth === "UNKNOWN" ? {kind: "OBSERVE", reason: null, observation_refs: trace.filter(row => !row.fresh).map(row => row.field), cost} : {kind: "ACTION_PROPOSAL", reason: null, action_name: action, cost};
    return Either.right({...base, hypothetical_next_step: nextStep});

};
const finiteNumber = isTaskNumber;
/** Pure finite discriminator for caller-supplied contexts. */
export const probeNativeTask = (input: Json): Either.Either<Json, NativeTaskError> => {
    if (!exact(input, ["domain", "candidates", "contexts", "allowed_reads", "allowed_probe_ids", "budget"]) || !record(input))
        return fail("invalid JSON object fields");
    const d = domain(input["domain"]!);
    if (Either.isLeft(d))
        return retype(d);
    if (!Array.isArray(input["candidates"]) || input["candidates"].length < 1 || input["candidates"].length > 8 || !Array.isArray(input["contexts"]) || (input["contexts"].length < 1 || input["contexts"].length > 64) || (!finiteNumber(input["budget"]!) || (taskNumberValue(input["budget"]) < 0 || taskNumberValue(input["budget"]) > Number.MAX_VALUE)))
        return fail("probe candidate or context bound");
    const allowed = parseReads(input["allowed_reads"]!, d.right);
    if (Either.isLeft(allowed) || allowed.right.size !== d.right.size)
        return fail("probe allowed reads");
    if (!Array.isArray(input["allowed_probe_ids"]) || !input["allowed_probe_ids"].every(text)) return fail("allowed probe ids");
    const ids = new Set(input["allowed_probe_ids"]);
    const candidates: Ast[] = [];
    for (const candidate of input["candidates"]) {
        if (!exact(candidate, ["relation_ast", "source"]) || !record(candidate) || !text(candidate["source"]!))
            return fail("probe candidate schema");
        const parsed = ast(candidate["relation_ast"]!, d.right);
        if (Either.isLeft(parsed))
            return retype(parsed);
        candidates.push(parsed.right);
    }
    const evaluated: Json[] = [];
    const feasible: Obj[] = [];
    const seen = new Set<string>();
    for (const row of input["contexts"]) {
        if (!exact(row, ["id", "values", "source", "cost"]) || !record(row) || !text(row["id"]!) || !text(row["source"]!) || (!finiteNumber(row["cost"]!) || (taskNumberValue(row["cost"]) < 0 || taskNumberValue(row["cost"]) > Number.MAX_VALUE)) || seen.has(row["id"]!))
            return fail("probe context schema");
        seen.add(row["id"]!);
        const assignment = values(row["values"]!, d.right);
        if (Either.isLeft(assignment))
            return retype(assignment);
        const observations = new Map([...assignment.right.entries()].map(([id, value]) => [id, { value, revision: `probe-context:${row["id"]}`, expires: 1, source: row["source"] as string }]));
        const predictions = candidates.map((candidate) => truth(candidate, observations, 0, `probe-context:${row["id"]}`));
        let separation = 0;
        for (let i = 0; i < predictions.length; i++)
            for (let j = i + 1; j < predictions.length; j++)
                if (predictions[i] !== predictions[j])
                    separation++;
        const item = { probe_id: row["id"], source: row["source"], cost: row["cost"], predictions: predictions.map((relation_prediction, candidate_index) => ({ candidate_index, relation_prediction })), separation };
        evaluated.push(item);
        if (ids.has(row["id"]!) && finiteNumber(input["budget"]!) && taskNumberValue(row["cost"]!) <= taskNumberValue(input["budget"]) && separation > 0)
            feasible.push(item);
    }
    const sortedDomain = [...d.right.values()].sort((a,b) => compareIds(keyId(a.key),keyId(b.key))).map(entry => [entry.key,entry.values]);
    const contexts: Json[] = [];
    for (const row of input["contexts"]) {
      if (!record(row)) return fail("probe context schema");
      const assignment = values(row["values"]!, d.right);
      if (Either.isLeft(assignment)) return retype(assignment);
      contexts.push({id: row["id"]!, values: [...assignment.right].sort(([a],[b])=>compareIds(a,b)).map(([id,value])=>[idKey(id),value]), source: row["source"]!, cost: row["cost"]!});
    }
    const readSet = [...new Map(candidates.flatMap(reads).map(k => [keyId(k),k])).values()].sort((a,b)=>compareIds(keyId(a),keyId(b)));
    const base = { credit: "UNIDENTIFIED_CREDIT", read_set: readSet, counters: { candidate_count: candidates.length, context_count: evaluated.length, candidates_evaluated: candidates.length * evaluated.length, contexts_evaluated: evaluated.length, feasible_contexts: feasible.length }, proposal_digest: nativeTaskDigest({ candidates: input["candidates"], domain: sortedDomain, contexts, allowed_reads: [...allowed.right].sort(compareIds).map(id=>idKey(id)), allowed_probe_ids: [...ids].sort(compare), budget: input["budget"], evaluated_contexts: evaluated }), evaluated_contexts: evaluated };
    if (feasible.length === 0)
        return Either.right({ status: "WITHHOLD", reason: "no_permitted_budgeted_distinguishing_context", selected_probe: null, ...base });
    const selected = [...feasible].sort((a, b) => -(a["separation"] as number) / (1 + Number(taskNumberValue(a["cost"] as TaskNumber))) + ((b["separation"] as number) / (1 + Number(taskNumberValue(b["cost"] as TaskNumber)))) || Number(taskNumberValue(a["cost"] as TaskNumber)) - Number(taskNumberValue(b["cost"] as TaskNumber)) || (b["separation"] as number) - (a["separation"] as number) || compare(String(a["probe_id"]), String(b["probe_id"])))[0]!;
    return Either.right({ status: "PROBE_PROPOSAL", selected_probe: selected, ...base });
};
/** Authored-fixture replay only. Subsequent feedback is explicitly excluded from initial selection. */
export const replayNativeTaskDemo = (input: Json): Either.Either<Json, NativeTaskError> => {
    if (!exact(input, ["schema_version", "domain", "examples", "initial_relation", "query", "action", "checks", "contexts", "allowed_probe_ids", "probe_budget", "subsequent_outcomes", "outcome_projection"]) || !record(input) || input["schema_version"] !== "hswm-conditional-demo/v1" || !record(input["outcome_projection"]!) || !exact(input["outcome_projection"]!, ["kind", "source"]) || input["outcome_projection"]!["kind"] !== "BOOLEAN_SUCCESS_IS_RELATION_TRUTH" || !text(input["outcome_projection"]!["source"]!))
        return fail("demo schema version");
    const initial = synthesizeNativeTask({ domain: input["domain"]!, examples: input["examples"]! });
    if (Either.isLeft(initial))
        return initial;
    const candidates = (initial.right as Obj)["candidates"];
    if (!Array.isArray(candidates) || !record(input["initial_relation"]!))
        return fail("demo initial relation must be a current candidate");
    const initialAst = input["initial_relation"]!["ast"];
    if (!candidates.some((candidate) => record(candidate) && nativeTaskDigest(candidate["relation_ast"]!) === nativeTaskDigest(initialAst!)))
        return fail("demo initial relation must be a current candidate");
    const beforeInput = { domain: input["domain"]!, relation: input["initial_relation"]!, observations: input["query"]!, action: input["action"]!, checks: input["checks"]! };
    const before = previewNativeTask(beforeInput);
    if (Either.isLeft(before))
        return before;
    const probe = probeNativeTask({ domain: input["domain"]!, candidates: candidates.map((candidate) => record(candidate) ? { relation_ast: candidate["relation_ast"]!, source: candidate["input_provenance_digest"]! } : candidate), contexts: input["contexts"]!, allowed_reads: (input["checks"]! as Obj)["allowed_reads"]!, allowed_probe_ids: input["allowed_probe_ids"]!, budget: input["probe_budget"]! });
    if (Either.isLeft(probe))
        return probe;
    const base: Obj = { status: "AUTHORED_EPISODE_REPLAY_NOT_EFFICACY", input_digest: nativeTaskDigest(input), initial_candidates: initial.right, before: before.right, probe: probe.right, outcome_projection: input["outcome_projection"]!, preview_query: { role: "SAME_SUPPLIED_QUERY_BEFORE_AFTER_RESTORE", digest: nativeTaskDigest(input["query"]!) }, credit: "UNIDENTIFIED_CREDIT", canonical_revision: null };
    const selected = record(probe.right) && record(probe.right["selected_probe"]!) ? probe.right["selected_probe"]!["probe_id"] : null;
    if (typeof selected !== "string")
        return Either.right({ ...base, revised_candidates: null, after: null, reason: "no_probe" });
    if (!Array.isArray(input["subsequent_outcomes"]))
        return fail("expected JSON list");
    const outcomes = new Map<string, Obj>();
    for (const row of input["subsequent_outcomes"]) {
      if (!record(row) || !exact(row, ["probe_id", "outcome", "source"]) || !text(row["probe_id"]!) || typeof row["outcome"] !== "boolean" || !text(row["source"]!) || outcomes.has(row["probe_id"]!)) return fail("duplicate or malformed subsequent outcome");
      outcomes.set(row["probe_id"]!, row);
    }
    const outcome = outcomes.get(selected);
    if (outcome === undefined) return Either.right({ ...base, revised_candidates: null, after: null, reason: "await_public_outcome" });
    const publicOutcome = {...outcome, probe_proposal_digest: (probe.right as Obj)["proposal_digest"]!};
    if (!Array.isArray(input["contexts"]))
        return fail("expected JSON list");
    const context = input["contexts"].find((row) => record(row) && row["id"] === selected);
    if (!record(context))
        return fail("probe context schema");
    const initialRelation = input["initial_relation"]!;
    const revised = synthesizeNativeTask({ domain: input["domain"]!, examples: [...(input["examples"] as ReadonlyArray<Json>), { values: context["values"]!, outcome: outcome["outcome"]!, source: outcome["source"]! }], parent: nativeTaskDigest([initialRelation["uid"]!, initialRelation["revision"]!, nativeTaskDigest([relationJson(initialRelation["ast"]!), initialRelation["source"]!])]) });
    if (Either.isLeft(revised))
        return revised;
    const revisedCandidates = (revised.right as Obj)["candidates"];
    if (!Array.isArray(revisedCandidates) || revisedCandidates.length === 0)
        return Either.right({ ...base, subsequent_public_outcome: publicOutcome, revised_candidates: revised.right, after: null });
    const proposed = revisedCandidates[0]!;
    if (!record(proposed))
        return fail("malformed proposal");
    const after = previewNativeTask({ ...beforeInput, relation: { uid: initialRelation["uid"]!, revision: `demo-proposal:${(revised.right as Obj)["input_provenance_digest"]}`, ast: proposed["relation_ast"]!, source: (revised.right as Obj)["input_provenance_digest"]! } });
    if (Either.isLeft(after))
        return after;
    return Either.right({ ...base, subsequent_public_outcome: publicOutcome, revised_candidates: revised.right, after: after.right, restored: before.right, selection: "FIRST_ENUMERATED_FOR_AUTHORED_DEMO_NOT_ADMITTED" });
};
