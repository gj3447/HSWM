/** Local TypeScript/Effect adaptive lifecycle; this is not a canonical admission or efficacy claim. */
import { createHash } from "node:crypto";
import { Data, Effect, Either } from "effect";
import { type AdaptiveAtom, type AdaptiveAtomRevision, AdaptiveStore, AdaptiveStoreError } from "./adaptive-store.js";
import { type AdaptiveExecution, AdaptiveHttpClient, type AdaptiveHttpClientShape, executeAdaptiveCell, NativeAdaptiveHttpClient } from "./adaptive-executor.js";
import { type AdaptiveModel, type Cell, type Context, type GuardExample, type Plan, type Program, type Route, initialModel, plan as decidePlan, proposeSpecialization, updateModel, parseProgram } from "./adaptive-domain.js";
import { BoundedSubprocess } from "./effect-bounded-subprocess.js";
export const ADAPTIVE_RUNTIME_BACKEND = "typescript-effect" as const;
export class AdaptiveRuntimeError extends Data.TaggedError("AdaptiveRuntimeError")<{
    readonly code: "PROGRAM_INVALID" | "CONTEXT_INVALID" | "REQUEST_INVALID" | "STORE" | "CONFLICT" | "UNRESOLVED";
    readonly detail: string;
}> {
}
const failure = (code: AdaptiveRuntimeError["code"], detail: string) => new AdaptiveRuntimeError({ code, detail });
const now = Effect.clockWith((clock) => clock.currentTimeMillis);
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const stableJson = (value: unknown): string => {
    if (value === null || typeof value === "boolean" || typeof value === "string")
        return JSON.stringify(value);
    if (typeof value === "number")
        return Number.isFinite(value) ? JSON.stringify(value) : "null";
    if (Array.isArray(value))
        return `[${value.map(stableJson).join(",")}]`;
    if (!record(value))
        return JSON.stringify(String(value));
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
};
const sha = (value: unknown): string => createHash("sha256").update(stableJson(value), "utf8").digest("hex");
const atom = (uid: string, kind: string, owner: string, payload: unknown, refs: ReadonlyArray<{
    readonly role: string;
    readonly uid: string;
}> = []): AdaptiveAtom => Object.freeze({ uid, kind, owner, payload, refs: Object.freeze(refs.map((ref) => Object.freeze({ ...ref }))) });
const draft = (value: AdaptiveAtomRevision): AdaptiveAtom => atom(value.uid, value.kind, value.owner, structuredClone(value.payload), structuredClone(value.refs));
const asPayload = (value: AdaptiveAtomRevision): Record<string, unknown> => record(value.payload) ? value.payload : {};
const routePayload = (value: AdaptiveAtomRevision): {
    readonly route: Route;
    readonly active: boolean;
    readonly model: AdaptiveModel;
    readonly examples: ReadonlyArray<GuardExample>;
    readonly parent_relation: string | null;
} | null => {
    const payload = asPayload(value);
    const candidate = record(payload["route"]) ? payload["route"] : payload;
    if (typeof payload["active"] !== "boolean" || !record(payload["model"]) || !Array.isArray(payload["examples"]) || (typeof payload["parent_relation"] !== "string" && payload["parent_relation"] !== null))
        return null;
    if (typeof candidate["uid"] !== "string" || typeof candidate["source"] !== "string" || !Array.isArray(candidate["members"]) || !Array.isArray(candidate["reads"]) || typeof candidate["cost_hint"] !== "number")
        return null;
    const route = { uid: candidate["uid"], source: candidate["source"], members: candidate["members"] as string[], reads: candidate["reads"] as string[], cost_hint: candidate["cost_hint"], ...(record(candidate["guard"]) ? { guard: candidate["guard"] } : {}) } as unknown as Route;
    const examples = payload["examples"].flatMap((example): GuardExample[] => {
        if (!record(example) || typeof example["source"] !== "string")
            return [];
        if (record(example["values"]) && typeof example["outcome"] === "boolean")
            return [{ values: example["values"] as Context, outcome: example["outcome"], source: example["source"] }];
        if (record(example["context"]) && typeof example["success"] === "boolean")
            return [{ values: example["context"] as Context, outcome: example["success"], source: example["source"] }];
        return [];
    });
    return { route, active: payload["active"], model: payload["model"] as unknown as AdaptiveModel, examples, parent_relation: payload["parent_relation"] as string | null };
};
const resultUnknown = (reason: string): AdaptiveExecution => Object.freeze({ status: "UNKNOWN", success: null, durationSeconds: 0, output: "", outputDigest: sha(""), metadata: Object.freeze({ reason }) });
const wireExecution = (value: AdaptiveExecution): Record<string, unknown> => Object.freeze({ status: value.status, success: value.success, duration_seconds: value.durationSeconds, output: value.output, output_digest: value.outputDigest, metadata: value.metadata });
const collectGuardReads = (guard: NonNullable<Route["guard"]>): ReadonlyArray<string> => guard.op === "eq" ? [guard.left.field] : guard.op === "not" ? collectGuardReads(guard.child) : guard.children.flatMap(collectGuardReads);
export interface AdaptiveRuntime {
    readonly plan: (context: Context, options?: {
        readonly cellId?: string;
        readonly budget?: number;
        readonly allowed?: ReadonlyArray<string>;
        readonly exploration?: number;
        readonly forceRoute?: string;
    }) => Effect.Effect<Plan & {
        readonly backend: typeof ADAPTIVE_RUNTIME_BACKEND;
    }, AdaptiveRuntimeError>;
    readonly run: (task: string, context: Context, options: {
        readonly episodeId: string;
        readonly budget?: number;
        readonly maxCalls?: number;
        readonly allowed?: ReadonlyArray<string>;
        readonly learn?: boolean;
        readonly exploration?: number;
        readonly forceRoute?: string;
    }) => Effect.Effect<Record<string, unknown>, AdaptiveRuntimeError, BoundedSubprocess>;
    readonly feedback: (episodeId: string, success: boolean, source: string) => Effect.Effect<Record<string, unknown>, AdaptiveRuntimeError>;
    readonly restore: (uid: string, revision: number, eventId: string) => Effect.Effect<Record<string, unknown>, AdaptiveRuntimeError>;
    readonly graph: () => Effect.Effect<Record<string, unknown>, AdaptiveRuntimeError>;
}
const storeError = <A>(effect: Effect.Effect<A, AdaptiveStoreError>): Effect.Effect<A, AdaptiveRuntimeError> => effect.pipe(Effect.mapError((error) => failure("STORE", `${error.operation}: ${error.detail}`)));
const contextValid = (program: Program, context: Context): boolean => Object.keys(context).length === Object.keys(program.context_domain).length && Object.entries(program.context_domain).every(([field, values]) => Object.hasOwn(context, field) && values.some((value) => Object.is(value, context[field])));
export const makeAdaptiveRuntime = (rawProgram: unknown, workspace: string, options?: {
    readonly httpClient?: AdaptiveHttpClientShape;
}): Effect.Effect<AdaptiveRuntime, AdaptiveRuntimeError, AdaptiveStore> => Effect.gen(function* () {
    const parsed = parseProgram(rawProgram);
    if (Either.isLeft(parsed))
        return yield* Effect.fail(failure("PROGRAM_INVALID", parsed.left.detail));
    if (!workspace)
        return yield* Effect.fail(failure("REQUEST_INVALID", "workspace is required"));
    const program = structuredClone(parsed.right);
    const manifestDigest = sha(rawProgram);
    const store = yield* AdaptiveStore;
    const cells = new Map(program.cells.map((cell) => [cell.cell_id, cell]));
    const root = cells.get(program.root) as Cell;
    const initial: AdaptiveAtom[] = [
        ...program.cells.map((cell) => atom(`cell:${cell.cell_id}`, "cell", cell.owner, cell)),
        ...Object.entries(program.context_domain).map(([name, values]) => atom(`field:${name}`, "context_field", root.owner, { name, values })),
        ...program.relations.map((route) => atom(`relation:${route.uid}`, "relation", (cells.get(route.source) as Cell).owner, { ...route, active: true, model: initialModel(), examples: [], parent_relation: null }, [{ role: "source", uid: `cell:${route.source}` }, ...route.members.map((member, index) => ({ role: `member:${index}`, uid: `cell:${member}` })), ...route.reads.map((field) => ({ role: `input:${field}`, uid: `field:${field}` }))])),
        atom("runtime:lease", "lease", root.owner, { episode: null })
    ];
    yield* storeError(store.initialize(program.graph_id, manifestDigest, initial));
    const withRuntimeLock = <A, R>(use: Effect.Effect<A, AdaptiveRuntimeError, R>): Effect.Effect<A, AdaptiveRuntimeError, R> => Effect.acquireUseRelease(storeError(store.acquireRuntimeLock(program.graph_id)), (_token) => use, (token) => storeError(store.releaseRuntimeLock(program.graph_id, token)).pipe(Effect.orDie));
    const get = (uid: string): Effect.Effect<AdaptiveAtomRevision, AdaptiveRuntimeError> => Effect.gen(function* () {
        const current = yield* storeError(store.head(program.graph_id, uid));
        const revision = yield* storeError(store.getRevision(program.graph_id, uid, current.revision));
        if (revision.uid !== current.uid || revision.revision !== current.revision || revision.kind !== current.kind || revision.owner !== current.owner || revision.digest !== current.digest)
            return yield* Effect.fail(failure("STORE", "head and immutable atom disagree"));
        return revision;
    });
    const optional = (uid: string): Effect.Effect<AdaptiveAtomRevision | null, AdaptiveRuntimeError> => get(uid).pipe(Effect.catchAll((error) => error.code === "STORE" && error.detail === "HEAD: atom head does not exist" ? Effect.succeed(null) : Effect.fail(error)));
    const routesFor = (source: string): Effect.Effect<ReadonlyArray<AdaptiveAtomRevision>, AdaptiveRuntimeError> => Effect.gen(function* () {
        const heads = yield* storeError(store.heads(program.graph_id, "relation"));
        const values = yield* Effect.forEach(heads, (head) => get(head.uid));
        for (const value of values)
            if (routePayload(value) === null)
                return yield* Effect.fail(failure("STORE", `malformed relation payload: ${value.uid}`));
        return values.filter((value) => routePayload(value)!.route.source === source);
    });
    const choose = (context: Context, source: string, budget: number, allowed: ReadonlySet<string>, exploration: number, forceRoute?: string): Effect.Effect<Plan & {
        readonly backend: typeof ADAPTIVE_RUNTIME_BACKEND;
    }, AdaptiveRuntimeError> => Effect.gen(function* () {
        if (!contextValid(program, context))
            return yield* Effect.fail(failure("CONTEXT_INVALID", "complete declared context required"));
        const values = yield* routesFor(source);
        const models = values.flatMap((value) => {
            const payload = routePayload(value);
            return payload === null ? [] : [{ route: { ...payload.route, uid: value.uid }, model: payload.model, active: payload.active }];
        });
        // Domain's public planner is root-oriented; preserve its bounded score for nested routers by a root substitution.
        const local = { ...program, root: source };
        const decided = decidePlan(local, models, context, { budget, allowed, exploration, ...(forceRoute === undefined ? {} : { force_route: forceRoute }) });
        if (Either.isLeft(decided))
            return yield* Effect.fail(failure("REQUEST_INVALID", decided.left.detail));
        return Object.freeze({ ...decided.right, backend: ADAPTIVE_RUNTIME_BACKEND });
    });
    const hasSpecialization = (parentUid: string): Effect.Effect<boolean, AdaptiveRuntimeError> => Effect.gen(function* () {
        const heads = yield* storeError(store.heads(program.graph_id, "relation"));
        const relations = yield* Effect.forEach(heads, (head) => get(head.uid));
        return relations.some((relation) => routePayload(relation)?.parent_relation === parentUid);
    });
    const runtime: AdaptiveRuntime = {
        plan: (context, input = {}) => Effect.gen(function* () {
            const budget = input.budget ?? 60, exploration = input.exploration ?? .1, source = input.cellId ?? program.root;
            if (!Number.isFinite(budget) || budget <= 0 || budget > 3600 || !Number.isFinite(exploration) || exploration < 0 || exploration > 1 || cells.get(source)?.kind !== "router")
                return yield* Effect.fail(failure("REQUEST_INVALID", "plan bounds or router"));
            const allowed = new Set(input.allowed ?? [...cells.keys()]);
            if ([...allowed].some((id) => !cells.has(id)))
                return yield* Effect.fail(failure("REQUEST_INVALID", "allowed cell"));
            return yield* choose(context, source, budget, allowed, exploration, input.forceRoute);
        }),
        run: (task, rawContext, rawInput) => withRuntimeLock(Effect.gen(function* () {
            const context = structuredClone(rawContext);
            const input = structuredClone(rawInput);
            const budget = input.budget ?? 60, maxCalls = input.maxCalls ?? 16, learn = input.learn ?? true, exploration = input.exploration ?? .1;
            if (!task.trim() || !input.episodeId.trim() || !Number.isFinite(budget) || budget <= 0 || budget > 3600 || !Number.isSafeInteger(maxCalls) || maxCalls < 1 || maxCalls > 64)
                return yield* Effect.fail(failure("REQUEST_INVALID", "run request"));
            if (!contextValid(program, context))
                return yield* Effect.fail(failure("CONTEXT_INVALID", "complete declared context required"));
            const allowed = new Set(input.allowed ?? [...cells.keys()]);
            if ([...allowed].some((id) => !cells.has(id)))
                return yield* Effect.fail(failure("REQUEST_INVALID", "allowed cell"));
            if (typeof learn !== "boolean" || !Number.isFinite(exploration) || exploration < 0 || exploration > 1 || task.length > 64000 || input.episodeId.length > 256)
                return yield* Effect.fail(failure("REQUEST_INVALID", "run request"));
            const intent = { task, context: structuredClone(context), workspace, budget, max_calls: maxCalls, allowed: [...allowed].sort(), learn, exploration, force_route: input.forceRoute ?? null, manifest: manifestDigest };
            const episodeUid = `episode:${input.episodeId}`;
            const existing = yield* optional(episodeUid);
            if (existing !== null) {
                const payload = asPayload(existing);
                const historic = record(payload["intent"]) ? payload["intent"] : null;
                if (payload["intent_digest"] !== sha(intent) && (historic === null || stableJson(historic) !== stableJson(intent)))
                    return yield* Effect.fail(failure("CONFLICT", "episode id reused with a different intent"));
                return Object.freeze({ ...payload, replayed: true, backend: ADAPTIVE_RUNTIME_BACKEND });
            }
            const first = yield* choose(context, program.root, budget, allowed, exploration, input.forceRoute);
            const lease = yield* get("runtime:lease");
            if (asPayload(lease)["episode"] !== null)
                return yield* Effect.fail(failure("UNRESOLVED", "another episode is unresolved"));
            const startedEpochSeconds = (yield* now) / 1000;
            const episode = atom(episodeUid, "episode", root.owner, { status: "RUNNING", episode_id: input.episodeId, started_at: startedEpochSeconds, intent_digest: sha(intent), intent, initial_plan: first, backend: ADAPTIVE_RUNTIME_BACKEND }, [{ role: "root", uid: `cell:${program.root}` }]);
            yield* storeError(store.rewrite({ graphId: program.graph_id, eventId: `${input.episodeId}:begin`, expected: { "runtime:lease": lease.revision, [episodeUid]: 0 }, atoms: [atom("runtime:lease", "lease", lease.owner, { episode: input.episodeId }), episode], source: { kind: "RUN_REQUEST", backend: ADAPTIVE_RUNTIME_BACKEND } }));
            const startedAt = yield* now;
            const deadline = startedAt + budget * 1000;
            let counter = 0, leaves = 0;
            const visits: Record<string, unknown>[] = [];
            const call = (cellId: string, payload: Record<string, unknown>, stack: ReadonlyArray<string>, parent?: string): Effect.Effect<AdaptiveExecution, AdaptiveRuntimeError, BoundedSubprocess> => Effect.gen(function* () {
                const currentTime = yield* now;
                const remaining = deadline - currentTime;
                if (remaining <= 0 || stack.length >= 8 || stack.includes(cellId) || leaves >= maxCalls || !allowed.has(cellId))
                    return resultUnknown("budget_depth_cycle_or_permission");
                const cell = cells.get(cellId);
                if (cell === undefined)
                    return resultUnknown("unknown cell");
                const traceUid = `trajectory:${input.episodeId}:${counter++}`;
                let selected: AdaptiveAtomRevision | undefined;
                let planned: Plan & {
                    readonly backend: typeof ADAPTIVE_RUNTIME_BACKEND;
                } | null = null;
                if (cell.kind === "router") {
                    planned = stack.length === 0 ? first : yield* choose(context, cellId, remaining / 1000, allowed, exploration);
                    if (planned.selected !== null)
                        selected = yield* get(planned.selected.uid.startsWith("relation:") ? planned.selected.uid : `relation:${planned.selected.uid}`);
                }
                const trace = atom(traceUid, "trajectory", cell.owner, { status: "RUNNING", episode_id: input.episodeId, input_digest: sha(payload), plan: planned, context }, [{ role: "episode", uid: episodeUid }, { role: "cell", uid: `cell:${cellId}` }, ...(parent === undefined ? [] : [{ role: "parent", uid: parent }]), ...(selected === undefined ? [] : [{ role: "selected_relation", uid: selected.uid }])]);
                yield* storeError(store.rewrite({ graphId: program.graph_id, eventId: `${traceUid}:begin`, expected: { [traceUid]: 0 }, atoms: [trace], source: { kind: "PRE_EFFECT_TRAJECTORY", backend: ADAPTIVE_RUNTIME_BACKEND } }));
                let result: AdaptiveExecution;
                if (cell.kind === "router") {
                    if (selected === undefined)
                        result = Object.freeze({ ...resultUnknown("no_eligible_relation"), status: "WITHHOLD" as const });
                    else {
                        const routerStarted = yield* now;
                        const nested = yield* Effect.gen(function* () {
                            let next: AdaptiveExecution = resultUnknown("empty route");
                            const route = routePayload(selected as AdaptiveAtomRevision)?.route;
                            if (route === undefined)
                                return resultUnknown("malformed route");
                            let current: Record<string, unknown> = { ...payload, context: Object.fromEntries(route.reads.map((field) => [field, context[field]!])) };
                            for (const member of route.members) {
                                next = yield* call(member, current, [...stack, cellId], traceUid);
                                if (next.status !== "SUCCEEDED")
                                    break;
                                current = { ...current, previous_output: next.output, prompt: `${task}\nPrevious cell output:\n${next.output}` };
                            }
                            return next;
                        });
                        const routerEnded = yield* now;
                        result = Object.freeze({ ...nested, durationSeconds: Math.max(0, (routerEnded - routerStarted) / 1000) });
                    }
                }
                else {
                    leaves += 1;
                    const beforeEffect = yield* now;
                    result = yield* executeAdaptiveCell(cell as unknown as Readonly<Record<string, unknown>>, { ...payload, episode_id: input.episodeId, call_id: traceUid }, workspace, Math.max(1, deadline - beforeEffect)).pipe(Effect.provideService(AdaptiveHttpClient, options?.httpClient ?? NativeAdaptiveHttpClient));
                }
                const done = draft((yield* get(traceUid)));
                const donePayload = asPayload(done as AdaptiveAtomRevision);
                donePayload["status"] = result.status;
                donePayload["result"] = wireExecution(result);
                const mutations: AdaptiveAtom[] = [atom(done.uid, done.kind, done.owner, donePayload, done.refs)];
                const expected: Record<string, number> = { [traceUid]: 1 };
                if (selected !== undefined && typeof result.success === "boolean") {
                    const route = routePayload(selected);
                    if (route !== null) {
                        const outcomeUid = `${traceUid}:outcome`;
                        const fact = { success: result.success, duration_seconds: result.durationSeconds, output_digest: result.outputDigest, source: "LOCAL_EXECUTOR_COMPOSITE_RETURN", credit: "UNIDENTIFIED_CAUSAL_CREDIT" };
                        mutations.push(atom(outcomeUid, "outcome", cell.owner, fact, [{ role: "trajectory", uid: traceUid }]));
                        expected[outcomeUid] = 0;
                        if (learn) {
                            const revised = draft(selected);
                            const data = routePayload(selected);
                            const read = Object.fromEntries(data!.route.reads.map((field) => [field, context[field]!])) as Context;
                            const updated = updateModel(data!.model, read, { success: result.success, cost: result.durationSeconds });
                            if (Either.isRight(updated)) {
                                const examples = [...data!.examples, { values: context, outcome: result.success, source: outcomeUid }].slice(-64);
                                mutations.push(atom(revised.uid, revised.kind, revised.owner, { ...asPayload(revised as AdaptiveAtomRevision), model: updated.right, examples, last_outcome: outcomeUid }, [...revised.refs.filter((ref) => ref.role !== "last_outcome"), { role: "last_outcome", uid: outcomeUid }]));
                                expected[revised.uid] = selected.revision;
                                // A bounded proposal is persisted atomically with its evidence and model update.
                                if (data!.parent_relation === null) {
                                    const proposal = proposeSpecialization(program.context_domain, examples, selected.digest);
                                    if (Either.isRight(proposal) && proposal.right.status === "PROPOSED_NOT_ADMITTED" && !(yield* hasSpecialization(selected.uid))) {
                                        const suffix = sha(proposal.right.relation_ast).slice(0, 20);
                                        const specializedUid = `${selected.uid}:specialized:${suffix}`;
                                        const exists = yield* optional(specializedUid);
                                        if (exists === null) {
                                            const conditionUid = `condition:${suffix}:${selected.uid}`;
                                            const guarded: Route = { ...data!.route, uid: specializedUid.replace(/^relation:/, ""), reads: [...new Set([...data!.route.reads, ...collectGuardReads(proposal.right.relation_ast)])].sort(), guard: proposal.right.relation_ast };
                                            mutations.push(atom(conditionUid, "condition", selected.owner, proposal.right, [{ role: "parent", uid: selected.uid }]), atom(specializedUid, "relation", selected.owner, { ...guarded, active: true, model: initialModel(), examples: [], parent_relation: selected.uid }, [{ role: "source", uid: `cell:${guarded.source}` }, { role: "condition", uid: conditionUid }, { role: "parent", uid: selected.uid }, ...guarded.members.map((member, index) => ({ role: `member:${index}`, uid: `cell:${member}` })), ...guarded.reads.map((field) => ({ role: `input:${field}`, uid: `field:${field}` }))]));
                                            expected[conditionUid] = 0;
                                            expected[specializedUid] = 0;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                yield* storeError(store.rewrite({ graphId: program.graph_id, eventId: `${traceUid}:complete`, expected, atoms: mutations, source: { kind: "OBSERVED_EXECUTION_RESULT", backend: ADAPTIVE_RUNTIME_BACKEND } }));
                visits.push({ trajectory: traceUid, cell: cellId, relation: selected?.uid ?? null, status: result.status, success: result.success });
                return result;
            });
            const result = yield* call(program.root, { task, prompt: task, context }, [], undefined).pipe(Effect.catchAll(() => Effect.succeed(resultUnknown("runtime exception"))));
            const current = yield* get(episodeUid);
            const payload = { ...asPayload(current), status: result.status, result: wireExecution(result), visits, leaf_calls: leaves, learning: learn ? "OBSERVATIONAL_LOCAL_ADAPTATION" : "FROZEN", claim: "EXPERIMENTAL_USE_NOT_EFFICACY_PROOF", backend: ADAPTIVE_RUNTIME_BACKEND };
            const endAtoms: AdaptiveAtom[] = [atom(episodeUid, current.kind, current.owner, payload, current.refs)];
            const endExpected: Record<string, number> = { [episodeUid]: current.revision };
            if (result.status !== "UNKNOWN") {
                const latestLease = yield* get("runtime:lease");
                endAtoms.push(atom(latestLease.uid, latestLease.kind, latestLease.owner, { episode: null }, latestLease.refs));
                endExpected[latestLease.uid] = latestLease.revision;
            }
            yield* storeError(store.rewrite({ graphId: program.graph_id, eventId: `${input.episodeId}:complete`, expected: endExpected, atoms: endAtoms, source: { kind: "EPISODE_COMPLETION", backend: ADAPTIVE_RUNTIME_BACKEND } }));
            return Object.freeze(payload);
        })),
        feedback: (episodeId, success, source) => withRuntimeLock(Effect.gen(function* () {
            if (!episodeId.trim() || episodeId.length > 256 || !source.trim() || source.length > 256 || typeof success !== "boolean")
                return yield* Effect.fail(failure("REQUEST_INVALID", "feedback"));
            const episode = yield* get(`episode:${episodeId}`);
            const payload = asPayload(episode);
            if (payload["feedback"] !== undefined && payload["feedback"] !== null) {
                const prior = payload["feedback"];
                if (record(prior) && prior["success"] === success && prior["source"] === source)
                    return Object.freeze(payload);
                return yield* Effect.fail(failure("CONFLICT", "conflicting repeat feedback"));
            }
            const priorResult = record(payload["result"]) ? payload["result"] : {};
            if (typeof priorResult["success"] === "boolean")
                return yield* Effect.fail(failure("CONFLICT", "episode already has a measured outcome"));
            const lease = yield* get("runtime:lease");
            if (asPayload(lease)["episode"] !== null && asPayload(lease)["episode"] !== episodeId)
                return yield* Effect.fail(failure("UNRESOLVED", "resolve other episode before feedback"));
            const updated: Record<string, unknown> = { ...payload, status: "FEEDBACK_RECORDED", feedback: { success, source }, backend: ADAPTIVE_RUNTIME_BACKEND };
            const atoms: AdaptiveAtom[] = [atom(episode.uid, episode.kind, episode.owner, updated, episode.refs)];
            const expected: Record<string, number> = { [episode.uid]: episode.revision };
            const rootTrace = yield* optional(`trajectory:${episodeId}:0`);
            if (rootTrace !== null) {
                const tracePayload = asPayload(rootTrace);
                const plan = record(tracePayload["plan"]) ? tracePayload["plan"] : {};
                const selected = record(plan["selected"]) ? plan["selected"] : null;
                if (selected !== null && typeof selected["uid"] === "string") {
                    const selectedUid = selected["uid"].startsWith("relation:") ? selected["uid"] : `relation:${selected["uid"]}`;
                    const route = yield* get(selectedUid);
                    const data = routePayload(route);
                    if (data !== null) {
                        const outcomeUid = `feedback:${episodeId}`;
                        const duration = typeof priorResult["duration_seconds"] === "number" ? priorResult["duration_seconds"] : 0;
                        atoms.push(atom(outcomeUid, "outcome", route.owner, { success, source, duration_seconds: duration, credit: "CALLER_FEEDBACK_NOT_INDEPENDENT_CAUSAL_CREDIT" }, [{ role: "episode", uid: episode.uid }]));
                        expected[outcomeUid] = 0;
                        const intent = record(payload["intent"]) ? payload["intent"] : {};
                        if (intent["learn"] === true) {
                            const read = Object.fromEntries(data.route.reads.map((field) => [field, (intent["context"] as Context)[field]])) as Context;
                            const revised = updateModel(data.model, read, { success, cost: duration });
                            if (Either.isRight(revised)) {
                                const examples = [...data.examples, { values: intent["context"] as Context, outcome: success, source: outcomeUid }].slice(-64);
                                atoms.push(atom(route.uid, route.kind, route.owner, { ...asPayload(route), model: revised.right, examples, last_outcome: outcomeUid }, [...route.refs.filter((ref) => ref.role !== "last_outcome"), { role: "last_outcome", uid: outcomeUid }]));
                                expected[route.uid] = route.revision;
                                updated["learning_status"] = "WEIGHTS_UPDATED";
                                if (data.parent_relation === null) {
                                    const proposal = proposeSpecialization(program.context_domain, examples, route.digest);
                                    if (Either.isRight(proposal) && proposal.right.status === "PROPOSED_NOT_ADMITTED") {
                                        const suffix = sha(proposal.right.relation_ast).slice(0, 20);
                                        const specializedUid = `${route.uid}:specialized:${suffix}`;
                                        if (!(yield* hasSpecialization(route.uid)) && (yield* optional(specializedUid)) === null) {
                                            const conditionUid = `condition:${suffix}:${route.uid}`;
                                            const guarded: Route = { ...data.route, uid: specializedUid.replace(/^relation:/, ""), reads: [...new Set([...data.route.reads, ...collectGuardReads(proposal.right.relation_ast)])].sort(), guard: proposal.right.relation_ast };
                                            atoms.push(atom(conditionUid, "condition", route.owner, proposal.right, [{ role: "parent", uid: route.uid }]), atom(specializedUid, "relation", route.owner, { ...guarded, active: true, model: initialModel(), examples: [], parent_relation: route.uid }, [{ role: "source", uid: `cell:${guarded.source}` }, { role: "condition", uid: conditionUid }, { role: "parent", uid: route.uid }, ...guarded.members.map((member, index) => ({ role: `member:${index}`, uid: `cell:${member}` })), ...guarded.reads.map((field) => ({ role: `input:${field}`, uid: `field:${field}` }))]));
                                            expected[conditionUid] = 0;
                                            expected[specializedUid] = 0;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            if (asPayload(lease)["episode"] === episodeId) {
                atoms.push(atom(lease.uid, lease.kind, lease.owner, { episode: null }, lease.refs));
                expected[lease.uid] = lease.revision;
            }
            yield* storeError(store.rewrite({ graphId: program.graph_id, eventId: `${episodeId}:feedback`, expected, atoms, source: { kind: "EXPLICIT_CALLER_FEEDBACK", source, backend: ADAPTIVE_RUNTIME_BACKEND } }));
            return Object.freeze(updated);
        })),
        restore: (uid, revision, eventId) => withRuntimeLock(Effect.gen(function* () {
            const prior = yield* storeError(store.getEvent(program.graph_id, eventId)).pipe(Effect.catchAll((error) => error.code === "STORE" && error.detail === "GET_EVENT: event does not exist" ? Effect.succeed(null) : Effect.fail(error)));
            if (prior !== null) {
                const source = prior.source;
                const match = source["kind"] === "EXPLICIT_RESTORE" && source["restored_revision"] === revision && typeof source["restored_digest"] === "string" && prior.produced.length === 1 && prior.produced[0]?.uid === uid;
                if (!match)
                    return yield* Effect.fail(failure("CONFLICT", "event id reused with a different restore"));
                return Object.freeze({ ...prior, backend: ADAPTIVE_RUNTIME_BACKEND });
            }
            const lease = yield* get("runtime:lease");
            if (asPayload(lease)["episode"] !== null)
                return yield* Effect.fail(failure("UNRESOLVED", "cannot restore during unresolved episode"));
            const current = yield* get(uid);
            if (current.kind !== "relation")
                return yield* Effect.fail(failure("REQUEST_INVALID", "only relation restore"));
            const old = yield* storeError(store.getRevision(program.graph_id, uid, revision));
            const event = yield* storeError(store.rewrite({ graphId: program.graph_id, eventId, expected: { [uid]: current.revision }, atoms: [draft(old)], source: { kind: "EXPLICIT_RESTORE", restored_revision: revision, restored_digest: old.digest, backend: ADAPTIVE_RUNTIME_BACKEND } }));
            return Object.freeze({ ...event, backend: ADAPTIVE_RUNTIME_BACKEND });
        })),
        graph: () => Effect.gen(function* () { const heads = yield* storeError(store.heads(program.graph_id)); const atoms = yield* Effect.forEach(heads, (head) => get(head.uid)); const events = yield* storeError(store.events(program.graph_id)); return Object.freeze({ schema_version: "hswm-adaptive-hypergraph/v1", graph_id: program.graph_id, atoms, events, backend: ADAPTIVE_RUNTIME_BACKEND, claim: "LOCAL_RUNTIME_STATE_NOT_REFERENCE_KG" }); })
    };
    return runtime;
});
