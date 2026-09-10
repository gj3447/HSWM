/**
 * Bounded local research-coordination records. These records preserve claims,
 * negative findings, and provenance; they do not establish HSWM efficacy.
 */
import { Data, Either } from "effect";

export interface ResearchSource {
  readonly id: string; readonly title: string; readonly locator: string;
  readonly sha256: string | null;
  readonly authority: "USER_PRIMARY" | "MIXED_EXPLICIT" | "EXTERNAL_PRIMARY_SOURCE_REPORTED" | "SECONDARY_AI" | "LOCAL_ENGINEERING_EVIDENCE";
}
export interface ResearchHypothesis {
  readonly id: string; readonly claim: string; readonly scope: string; readonly falsifier: string;
  readonly sourceIds: readonly string[]; readonly predecessorIds: readonly string[];
}
export interface ResearchTask {
  readonly id: string; readonly hypothesisId: string;
  readonly role: "EXPLORE" | "CRITIQUE" | "INTEGRATE" | "VERIFY";
  readonly question: string; readonly acceptance: string; readonly dependsOn: readonly string[];
  readonly budgetTokens: number;
}
export interface ResearchManifest {
  readonly schema: "hswm-research-graph/v1"; readonly id: string;
  readonly goal: string; readonly targetRef: string; readonly maxParallelism: number;
  readonly sources: readonly ResearchSource[]; readonly hypotheses: readonly ResearchHypothesis[];
  readonly tasks: readonly ResearchTask[];
}
export type ResearchEvent =
  | { readonly type: "START"; readonly id: string; readonly taskId: string; readonly actor: string; readonly model: string; readonly at: string }
  | { readonly type: "FINISH"; readonly id: string; readonly taskId: string; readonly actor: string; readonly at: string; readonly disposition: "SUPPORTED_IN_SCOPE" | "REFUTED_IN_SCOPE" | "INCONCLUSIVE" | "ENGINEERING_ONLY"; readonly summary: string; readonly sourceIds: readonly string[]; readonly usedTokens: number | null }
  | { readonly type: "EXTEND"; readonly id: string; readonly at: string; readonly sources: readonly ResearchSource[]; readonly hypotheses: readonly ResearchHypothesis[]; readonly tasks: readonly ResearchTask[] };
export interface ResearchGraph { readonly manifest: ResearchManifest; readonly events: readonly ResearchEvent[]; }
export class ResearchGraphError extends Data.TaggedError("ResearchGraphError")<{ readonly code: "INVALID" | "REFERENCE" | "CYCLE" | "EVENT" | "CAPACITY"; readonly detail: string; }> {}

const MAX_ITEMS = 128, MAX_TEXT = 4096, MAX_EVENTS = 1024;
const fail = <A = never>(code: ResearchGraphError["code"], detail: string): Either.Either<A, ResearchGraphError> => Either.left(new ResearchGraphError({ code, detail }));
const retype = <A>(result: Either.Either<unknown, ResearchGraphError>): Either.Either<A, ResearchGraphError> =>
  Either.isLeft(result) ? fail(result.left.code, result.left.detail) : fail("INVALID", "internal decoder result");
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const exact = (v: Record<string, unknown>, keys: readonly string[]): boolean => Object.keys(v).length === keys.length && keys.every((k) => Object.hasOwn(v, k));
const text = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0 && v.length <= MAX_TEXT;
const id = (v: unknown): v is string => text(v) && /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(v);
const safe = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0 && v <= 1_000_000_000_000;
const iso = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString() === v;
const array = (v: unknown, maximum = MAX_ITEMS): v is readonly unknown[] => Array.isArray(v) && v.length <= maximum;
const authorities = ["USER_PRIMARY", "MIXED_EXPLICIT", "EXTERNAL_PRIMARY_SOURCE_REPORTED", "SECONDARY_AI", "LOCAL_ENGINEERING_EVIDENCE"] as const;
const roles = ["EXPLORE", "CRITIQUE", "INTEGRATE", "VERIFY"] as const;
const dispositions = ["SUPPORTED_IN_SCOPE", "REFUTED_IN_SCOPE", "INCONCLUSIVE", "ENGINEERING_ONLY"] as const;
const oneOf = <T extends string>(v: unknown, xs: readonly T[]): v is T => typeof v === "string" && xs.includes(v as T);
const ids = (v: unknown): v is readonly string[] => array(v) && v.every(id) && new Set(v).size === v.length;

const source = (v: unknown): Either.Either<ResearchSource, ResearchGraphError> => {
  if (!object(v) || !exact(v, ["id", "title", "locator", "sha256", "authority"])) return fail("INVALID", "invalid research source");
  const sha256 = v["sha256"];
  if (!id(v["id"]) || !text(v["title"]) || !text(v["locator"]) || !(sha256 === null || (typeof sha256 === "string" && /^[a-f0-9]{64}$/.test(sha256))) || !oneOf(v["authority"], authorities)) return fail("INVALID", "invalid research source");
  return Either.right(Object.freeze({ id: v["id"], title: v["title"], locator: v["locator"], sha256, authority: v["authority"] }));
};
const hypothesis = (v: unknown): Either.Either<ResearchHypothesis, ResearchGraphError> => {
  if (!object(v) || !exact(v, ["id", "claim", "scope", "falsifier", "sourceIds", "predecessorIds"]) || !id(v["id"]) || !text(v["claim"]) || !text(v["scope"]) || !text(v["falsifier"]) || !ids(v["sourceIds"]) || !ids(v["predecessorIds"])) return fail("INVALID", "invalid research hypothesis");
  return Either.right(Object.freeze({ id: v["id"], claim: v["claim"], scope: v["scope"], falsifier: v["falsifier"], sourceIds: Object.freeze([...v["sourceIds"]]), predecessorIds: Object.freeze([...v["predecessorIds"]]) }));
};
const task = (v: unknown): Either.Either<ResearchTask, ResearchGraphError> => {
  if (!object(v) || !exact(v, ["id", "hypothesisId", "role", "question", "acceptance", "dependsOn", "budgetTokens"]) || !id(v["id"]) || !id(v["hypothesisId"]) || !oneOf(v["role"], roles) || !text(v["question"]) || !text(v["acceptance"]) || !ids(v["dependsOn"]) || !safe(v["budgetTokens"]) || v["budgetTokens"] < 1) return fail("INVALID", "invalid research task");
  return Either.right(Object.freeze({ id: v["id"], hypothesisId: v["hypothesisId"], role: v["role"], question: v["question"], acceptance: v["acceptance"], dependsOn: Object.freeze([...v["dependsOn"]]), budgetTokens: v["budgetTokens"] }));
};
const decodeList = <A>(
  v: unknown,
  decoder: (x: unknown) => Either.Either<A, ResearchGraphError>,
  label: string,
  maximum = MAX_ITEMS,
): Either.Either<readonly A[], ResearchGraphError> => {
  if (!array(v, maximum)) return fail("INVALID", `${label} must be a bounded array`);
  const result: A[] = [];
  for (const item of v) {
    const parsed = decoder(item);
    if (Either.isLeft(parsed)) return retype(parsed);
    result.push(parsed.right);
  }
  return Either.right(Object.freeze(result));
};
const manifest = (v: unknown): Either.Either<ResearchManifest, ResearchGraphError> => {
  if (!object(v) || !exact(v, ["schema", "id", "goal", "targetRef", "maxParallelism", "sources", "hypotheses", "tasks"]) || v["schema"] !== "hswm-research-graph/v1" || !id(v["id"]) || !text(v["goal"]) || !text(v["targetRef"])) return fail("INVALID", "invalid research manifest");
  const maxParallelism = v["maxParallelism"];
  if (typeof maxParallelism !== "number" || !Number.isSafeInteger(maxParallelism) || maxParallelism < 1 || maxParallelism > 4) return fail("INVALID", "invalid max parallelism");
  const ss = decodeList(v["sources"], source, "sources"), hs = decodeList(v["hypotheses"], hypothesis, "hypotheses"), ts = decodeList(v["tasks"], task, "tasks");
  if (Either.isLeft(ss)) return retype(ss); if (Either.isLeft(hs)) return retype(hs); if (Either.isLeft(ts)) return retype(ts);
  const result: ResearchManifest = Object.freeze({ schema: v["schema"], id: v["id"], goal: v["goal"], targetRef: v["targetRef"], maxParallelism, sources: ss.right, hypotheses: hs.right, tasks: ts.right });
  const valid = validateManifest(result); return Either.isLeft(valid) ? retype(valid) : Either.right(result);
};
const unique = (values: readonly { readonly id: string }[], label: string): Either.Either<void, ResearchGraphError> => new Set(values.map((v) => v["id"])).size === values.length ? Either.right(undefined) : fail("REFERENCE", `duplicate ${label} id`);
const dag = (items: readonly { readonly id: string; readonly refs: readonly string[] }[], label: string): Either.Either<void, ResearchGraphError> => {
  const byId = new Map(items.map((x) => [x.id, x]));
  for (const item of items) if (item.refs.some((ref) => !byId.has(ref))) return fail("REFERENCE", `${label} reference missing`);
  const visiting = new Set<string>(), done = new Set<string>();
  const visit = (key: string): boolean => { if (done.has(key)) return true; if (visiting.has(key)) return false; visiting.add(key); const ok = byId.get(key)!.refs.every(visit); visiting.delete(key); done.add(key); return ok; };
  return items.every((x) => visit(x.id)) ? Either.right(undefined) : fail("CYCLE", `${label} must be acyclic`);
};
const validateManifest = (m: ResearchManifest): Either.Either<void, ResearchGraphError> => {
  if (m.sources.length > MAX_ITEMS || m.hypotheses.length > MAX_ITEMS || m.tasks.length > MAX_ITEMS)
    return fail("INVALID", "effective extension exceeds item bound");
  const a = unique(m.sources, "source"), b = unique(m.hypotheses, "hypothesis"), c = unique(m.tasks, "task"); if (Either.isLeft(a)) return a; if (Either.isLeft(b)) return b; if (Either.isLeft(c)) return c;
  const sources = new Set(m.sources.map((x) => x.id)), hypotheses = new Set(m.hypotheses.map((x) => x.id));
  if (m.hypotheses.some((x) => x.sourceIds.some((ref) => !sources.has(ref)))) return fail("REFERENCE", "hypothesis source reference missing");
  if (m.tasks.some((x) => !hypotheses.has(x.hypothesisId))) return fail("REFERENCE", "task hypothesis reference missing");
  const h = dag(m.hypotheses.map((x) => ({ id: x.id, refs: x.predecessorIds })), "hypothesis predecessor"); if (Either.isLeft(h)) return h;
  return dag(m.tasks.map((x) => ({ id: x.id, refs: x.dependsOn })), "task dependency");
};
const event = (v: unknown): Either.Either<ResearchEvent, ResearchGraphError> => {
  if (!object(v) || !text(v["type"])) return fail("INVALID", "invalid research event");
  if (v["type"] === "START") { if (!exact(v, ["type", "id", "taskId", "actor", "model", "at"]) || !id(v["id"]) || !id(v["taskId"]) || !text(v["actor"]) || !text(v["model"]) || !iso(v["at"])) return fail("INVALID", "invalid START event"); return Either.right(Object.freeze({ type: "START", id: v["id"], taskId: v["taskId"], actor: v["actor"], model: v["model"], at: v["at"] })); }
  if (v["type"] === "FINISH") { if (!exact(v, ["type", "id", "taskId", "actor", "at", "disposition", "summary", "sourceIds", "usedTokens"]) || !id(v["id"]) || !id(v["taskId"]) || !text(v["actor"]) || !iso(v["at"]) || !oneOf(v["disposition"], dispositions) || !text(v["summary"]) || !ids(v["sourceIds"]) || !(v["usedTokens"] === null || safe(v["usedTokens"]))) return fail("INVALID", "invalid FINISH event"); return Either.right(Object.freeze({ type: "FINISH", id: v["id"], taskId: v["taskId"], actor: v["actor"], at: v["at"], disposition: v["disposition"], summary: v["summary"], sourceIds: Object.freeze([...v["sourceIds"]]), usedTokens: v["usedTokens"] })); }
  if (v["type"] === "EXTEND") { if (!exact(v, ["type", "id", "at", "sources", "hypotheses", "tasks"]) || !id(v["id"]) || !iso(v["at"])) return fail("INVALID", "invalid EXTEND event"); const ss = decodeList(v["sources"], source, "extension sources"), hs = decodeList(v["hypotheses"], hypothesis, "extension hypotheses"), ts = decodeList(v["tasks"], task, "extension tasks"); if (Either.isLeft(ss)) return retype(ss); if (Either.isLeft(hs)) return retype(hs); if (Either.isLeft(ts)) return retype(ts); return Either.right(Object.freeze({ type: "EXTEND", id: v["id"], at: v["at"], sources: ss.right, hypotheses: hs.right, tasks: ts.right })); }
  return fail("INVALID", "unknown event type");
};
const extended = (base: ResearchManifest, events: readonly ResearchEvent[]): ResearchManifest =>
  Object.freeze({
    ...base,
    sources: Object.freeze([...base.sources, ...events.flatMap((x) => x.type === "EXTEND" ? x.sources : [])]),
    hypotheses: Object.freeze([...base.hypotheses, ...events.flatMap((x) => x.type === "EXTEND" ? x.hypotheses : [])]),
    tasks: Object.freeze([...base.tasks, ...events.flatMap((x) => x.type === "EXTEND" ? x.tasks : [])]),
  });
const ancestors = (taskId: string, m: ResearchManifest): readonly string[] => { const lookup = new Map(m.tasks.map((x) => [x.id, x])); const out = new Set<string>(); const visit = (x: string): void => { for (const dep of lookup.get(x)!.dependsOn) if (!out.has(dep)) { out.add(dep); visit(dep); } }; visit(taskId); return [...out]; };
const validateHistory = (m: ResearchManifest, events: readonly ResearchEvent[]): Either.Either<void, ResearchGraphError> => {
  let prior = ""; const idsSeen = new Set<string>(), starts = new Map<string, Extract<ResearchEvent, { type: "START" }>>(), finishes = new Set<string>();
  for (let index = 0; index < events.length; index++) {
    const e = events[index]!; if (idsSeen.has(e.id)) return fail("EVENT", "duplicate event id"); idsSeen.add(e.id); if (prior > e.at) return fail("EVENT", "event timestamps must be chronological"); prior = e.at;
    const current = extended(m, events.slice(0, index + (e.type === "EXTEND" ? 1 : 0))); const valid = validateManifest(current); if (Either.isLeft(valid)) return valid;
    if (e.type === "EXTEND") continue;
    const t = current.tasks.find((x) => x.id === e.taskId); if (!t) return fail("REFERENCE", "event task missing");
    if (e.type === "START") { if (starts.has(t.id) || finishes.has(t.id)) return fail("EVENT", "task has already started; reruns require a new task id"); if (t.dependsOn.some((dep) => !finishes.has(dep))) return fail("EVENT", "task dependencies are incomplete"); if ([...starts.keys()].filter((key) => !finishes.has(key)).length >= current.maxParallelism) return fail("CAPACITY", "max parallelism reached"); if (["CRITIQUE", "VERIFY"].includes(t.role)) { const contributorActors = ancestors(t.id, current).map((x) => starts.get(x)?.actor).filter((x): x is string => x !== undefined); if (contributorActors.includes(e.actor)) return fail("EVENT", "critic or verifier actor matches an upstream contributor"); } starts.set(t.id, e); }
    else { const started = starts.get(t.id); if (!started || finishes.has(t.id)) return fail("EVENT", "finish requires exactly one unfinished START"); if (started.actor !== e.actor) return fail("EVENT", "finish actor must match assigned START actor"); if (e.sourceIds.some((ref) => !current.sources.some((s) => s.id === ref))) return fail("REFERENCE", "finish source reference missing"); finishes.add(t.id); }
  }
  return Either.right(undefined);
};
export const parseResearchGraph = (input: unknown): Either.Either<ResearchGraph, ResearchGraphError> => {
  if (!object(input) || !exact(input, ["manifest", "events"]))
    return fail("INVALID", "graph must contain only manifest and events");
  const m = manifest(input["manifest"]);
  const es = decodeList(input["events"], event, "events", MAX_EVENTS);
  if (Either.isLeft(m)) return retype(m);
  if (Either.isLeft(es)) return retype(es);
  const history = validateHistory(m.right, es.right);
  if (Either.isLeft(history)) return retype(history);
  return Either.right(Object.freeze({ manifest: m.right, events: es.right }));
};
export const appendResearchEvent = (
  graph: ResearchGraph,
  input: unknown,
): Either.Either<ResearchGraph, ResearchGraphError> => {
  const checked = parseResearchGraph(graph);
  const next = event(input);
  if (Either.isLeft(checked)) return retype(checked);
  if (Either.isLeft(next)) return retype(next);
  if (checked.right.events.length >= MAX_EVENTS) return fail("INVALID", "too many events");
  return parseResearchGraph({
    manifest: checked.right.manifest,
    events: [...checked.right.events, next.right],
  });
};
export const researchGraphState = (graph: ResearchGraph) => {
  const m = extended(graph.manifest, graph.events);
  const startBy = new Map<string, Extract<ResearchEvent, { type: "START" }>>();
  const finishBy = new Map<string, Extract<ResearchEvent, { type: "FINISH" }>>();
  for (const entry of graph.events) {
    if (entry.type === "START") startBy.set(entry.taskId, entry);
    if (entry.type === "FINISH") finishBy.set(entry.taskId, entry);
  }
  const tasks = m.tasks.map((task) => {
    const start = startBy.get(task.id) ?? null;
    const finish = finishBy.get(task.id) ?? null;
    const status = finish ? "COMPLETE" : start ? "RUNNING" : task.dependsOn.some((dependency) => !finishBy.has(dependency)) ? "WAITING" : "READY";
    const usageStatus = finish === null ? null : finish.usedTokens === null ? "UNKNOWN" : "REPORTED";
    const overBudget = finish === null ? false : finish.usedTokens === null ? null : finish.usedTokens > task.budgetTokens;
    return Object.freeze({ task, status, start, finish, usageStatus, overBudget });
  });
  const active = tasks.filter((entry) => entry.status === "RUNNING").length;
  return Object.freeze({ manifest: m, tasks: Object.freeze(tasks), active, remainingSlots: m.maxParallelism - active });
};
export const researchTaskContext = (graph: ResearchGraph, taskId: string): Either.Either<Record<string, unknown>, ResearchGraphError> => {
  const parsed = parseResearchGraph(graph);
  if (Either.isLeft(parsed)) return retype(parsed);
  const state = researchGraphState(parsed.right);
  const entry = state.tasks.find((item) => item.task.id === taskId);
  if (!entry) return fail("REFERENCE", "task missing");
  const hypothesis = state.manifest.hypotheses.find((item) => item.id === entry.task.hypothesisId)!;
  const declaredSources = hypothesis.sourceIds.map((id) => state.manifest.sources.find((source) => source.id === id)!);
  const ancestorIds = new Set(ancestors(taskId, state.manifest));
  const dependencyResults = state.tasks
    .filter((item) => ancestorIds.has(item.task.id) && item.finish !== null)
    .map((item) => Object.freeze({ taskId: item.task.id, actor: item.finish!.actor, model: item.start!.model, disposition: item.finish!.disposition, summary: item.finish!.summary, sourceIds: item.finish!.sourceIds, usedTokens: item.finish!.usedTokens, usageStatus: item.usageStatus, overBudget: item.overBudget, negative: item.finish!.disposition === "REFUTED_IN_SCOPE" }));
  const handoffSourceIds = new Set(dependencyResults.flatMap((result) => result.sourceIds));
  const handoffSources = state.manifest.sources.filter((source) => handoffSourceIds.has(source.id));
  return Either.right(Object.freeze({
    goal: state.manifest.goal,
    target: state.manifest.targetRef,
    hypothesis,
    task: entry.task,
    declaredSources: Object.freeze(declaredSources),
    dependencyResults: Object.freeze(dependencyResults),
    handoffSources: Object.freeze(handoffSources),
    overBudget: entry.overBudget,
  }));
};
