import { expect, it } from "vitest";
import { Either } from "effect";

import {
  appendResearchEvent,
  parseResearchGraph,
  researchGraphState,
  researchTaskContext,
} from "../../src/hswm/effect-runtime/src/research-graph-domain.js";

const source = { id: "openai-report", title: "Reported result", locator: "https://example.test/report", sha256: null, authority: "EXTERNAL_PRIMARY_SOURCE_REPORTED" } as const;
const manifest = {
  schema: "hswm-research-graph/v1",
  id: "local-research",
  goal: "Test a bounded relation-learning route.",
  targetRef: "docs/canon/HSWM_CONSTITUTION_2026-08-20.md",
  maxParallelism: 2,
  sources: [source],
  hypotheses: [
    { id: "route", claim: "A relation can improve a held-out task.", scope: "local benchmark only", falsifier: "No held-out difference", sourceIds: [source.id], predecessorIds: [] },
  ],
  tasks: [
    { id: "explore-a", hypothesisId: "route", role: "EXPLORE", question: "Find an intervention.", acceptance: "Report outcome.", dependsOn: [], budgetTokens: 10 },
    { id: "explore-b", hypothesisId: "route", role: "EXPLORE", question: "Find a counterexample.", acceptance: "Report outcome.", dependsOn: [], budgetTokens: 10 },
    { id: "critic", hypothesisId: "route", role: "CRITIQUE", question: "Critique both results.", acceptance: "Name confounds.", dependsOn: ["explore-a", "explore-b"], budgetTokens: 10 },
    { id: "integrate", hypothesisId: "route", role: "INTEGRATE", question: "Specify test.", acceptance: "Publish protocol.", dependsOn: ["critic"], budgetTokens: 10 },
    { id: "verify", hypothesisId: "route", role: "VERIFY", question: "Reproduce test.", acceptance: "Report result.", dependsOn: ["integrate"], budgetTokens: 10 },
  ],
} as const;
const at = (seconds: number) => `2026-09-09T00:00:${String(seconds).padStart(2, "0")}.000Z`;
const parsed = () => parseResearchGraph({ manifest, events: [] });
const right = <A>(value: Either.Either<A, unknown>): A => {
  expect(Either.isRight(value)).toBe(true);
  if (Either.isLeft(value)) throw value.left;
  return value.right;
};
const event = (graph: ReturnType<typeof parsed> extends Either.Either<infer A, unknown> ? A : never, value: Record<string, unknown>) => right(appendResearchEvent(graph, value));

it("coordinates two explorations through independent critique, integration, and verification", () => {
  let graph = right(parsed());
  expect(researchGraphState(graph).tasks.filter((item) => item.status === "READY").map((item) => item.task.id)).toEqual(["explore-a", "explore-b"]);
  graph = event(graph, { type: "START", id: "s-a", taskId: "explore-a", actor: "astra-a", model: "astra", at: at(1) });
  graph = event(graph, { type: "START", id: "s-b", taskId: "explore-b", actor: "astra-b", model: "astra", at: at(2) });
  graph = event(graph, { type: "FINISH", id: "f-a", taskId: "explore-a", actor: "astra-a", at: at(3), disposition: "REFUTED_IN_SCOPE", summary: "baseline did not improve", sourceIds: [source.id], usedTokens: 12 });
  graph = event(graph, { type: "FINISH", id: "f-b", taskId: "explore-b", actor: "astra-b", at: at(4), disposition: "INCONCLUSIVE", summary: "confounded result", sourceIds: [source.id], usedTokens: 4 });
  graph = event(graph, { type: "START", id: "s-c", taskId: "critic", actor: "astra-c", model: "astra", at: at(5) });
  graph = event(graph, { type: "FINISH", id: "f-c", taskId: "critic", actor: "astra-c", at: at(6), disposition: "ENGINEERING_ONLY", summary: "add an ablation", sourceIds: [source.id], usedTokens: 6 });
  graph = event(graph, { type: "START", id: "s-i", taskId: "integrate", actor: "astra-a", model: "astra", at: at(7) });
  graph = event(graph, { type: "FINISH", id: "f-i", taskId: "integrate", actor: "astra-a", at: at(8), disposition: "INCONCLUSIVE", summary: "protocol only", sourceIds: [source.id], usedTokens: 3 });
  graph = event(graph, { type: "START", id: "s-v", taskId: "verify", actor: "astra-v", model: "astra", at: at(9) });
  const state = researchGraphState(graph);
  expect(state.active).toBe(1);
  expect(state.tasks.find((item) => item.task.id === "explore-a")?.overBudget).toBe(true);
  const context = right(researchTaskContext(graph, "verify"));
  expect(context["dependencyResults"]).toEqual(expect.arrayContaining([expect.objectContaining({ taskId: "explore-a", negative: true })]));
  expect(context["dependencyResults"]).toEqual(expect.arrayContaining([expect.objectContaining({ taskId: "explore-a", actor: "astra-a", model: "astra", usedTokens: 12, overBudget: true, usageStatus: "REPORTED" })]));
});

it("records unavailable FINISH usage without declaring a budget outcome", () => {
  let graph = right(parsed());
  graph = event(graph, { type: "START", id: "unknown-start", taskId: "explore-a", actor: "telemetryless", model: "astra", at: at(1) });
  graph = event(graph, { type: "FINISH", id: "unknown-finish", taskId: "explore-a", actor: "telemetryless", at: at(2), disposition: "INCONCLUSIVE", summary: "No token telemetry was supplied.", sourceIds: [source.id], usedTokens: null });
  const entry = researchGraphState(graph).tasks.find((item) => item.task.id === "explore-a");
  expect(entry?.usageStatus).toBe("UNKNOWN");
  expect(entry?.overBudget).toBeNull();
  const context = right(researchTaskContext(graph, "critic"));
  expect(context["dependencyResults"]).toEqual(expect.arrayContaining([expect.objectContaining({ taskId: "explore-a", usedTokens: null, overBudget: null, usageStatus: "UNKNOWN", actor: "telemetryless", model: "astra" })]));
});

it("rejects premature, cyclic, same-actor verification, and hostile input", () => {
  const graph = right(parsed());
  expect(Either.isLeft(appendResearchEvent(graph, { type: "START", id: "bad", taskId: "critic", actor: "x", model: "astra", at: at(1) }))).toBe(true);
  expect(Either.isLeft(parseResearchGraph({ manifest: { ...manifest, tasks: [{ ...manifest.tasks[0], dependsOn: ["explore-a"] }] }, events: [] }))).toBe(true);
  const tooLong = "x".repeat(4097);
  expect(Either.isLeft(parseResearchGraph({ manifest: { ...manifest, goal: tooLong }, events: [] }))).toBe(true);
  let progressed = event(graph, { type: "START", id: "s", taskId: "explore-a", actor: "same", model: "astra", at: at(1) });
  progressed = event(progressed, { type: "FINISH", id: "f", taskId: "explore-a", actor: "same", at: at(2), disposition: "REFUTED_IN_SCOPE", summary: "negative kept", sourceIds: [source.id], usedTokens: 1 });
  const modified = { ...manifest, tasks: [manifest.tasks[0], { ...manifest.tasks[4], dependsOn: ["explore-a"] }] };
  const reduced = right(parseResearchGraph({ manifest: modified, events: progressed.events }));
  expect(Either.isLeft(appendResearchEvent(reduced, { type: "START", id: "same-verifier", taskId: "verify", actor: "same", model: "astra", at: at(3) }))).toBe(true);
});

it("keeps inputs unchanged and adds follow-up work through EXTEND", () => {
  const raw = { manifest, events: [] as unknown[] };
  Object.freeze(raw.manifest); Object.freeze(raw.events); Object.freeze(raw);
  const graph = right(parseResearchGraph(raw));
  const next = event(graph, { type: "EXTEND", id: "route-change", at: at(1), sources: [], hypotheses: [], tasks: [{ id: "follow-up", hypothesisId: "route", role: "EXPLORE", question: "Test a replacement.", acceptance: "Record result.", dependsOn: [], budgetTokens: 2 }] });
  expect(raw.events).toEqual([]);
  expect(researchGraphState(next).tasks.map((item) => item.task.id)).toContain("follow-up");
  expect(graph.events).toEqual([]);
});

it("bounds the complete event history and cumulative extension surface", () => {
  const extensions = Array.from({ length: 129 }, (_, index) => ({
    type: "EXTEND" as const,
    id: `extension-${index}`,
    at: new Date(Date.UTC(2026, 8, 9, 0, 0, index)).toISOString(),
    sources: [], hypotheses: [], tasks: [],
  }));
  expect(Either.isRight(parseResearchGraph({ manifest, events: extensions }))).toBe(true);
  expect(Either.isLeft(parseResearchGraph({ manifest, events: Array.from({ length: 1025 }, (_, index) => ({ ...extensions[0], id: `many-${index}`, at: new Date(Date.UTC(2026, 8, 9, 0, 0, index)).toISOString() })) }))).toBe(true);
  const additions = (from: number, count: number) => Array.from({ length: count }, (_, index) => ({ id: `route-${from + index}`, hypothesisId: "route", role: "EXPLORE" as const, question: "Try a route.", acceptance: "Keep result.", dependsOn: [], budgetTokens: 1 }));
  expect(Either.isLeft(parseResearchGraph({ manifest, events: [
    { type: "EXTEND", id: "first", at: at(1), sources: [], hypotheses: [], tasks: additions(0, 100) },
    { type: "EXTEND", id: "second", at: at(2), sources: [], hypotheses: [], tasks: additions(100, 24) },
  ] }))).toBe(true);
});

it("hands completed evidence sources to dependents and freezes decoded records", () => {
  const evidence = { id: "negative-evidence", title: "Negative result", locator: "file:negative", sha256: null, authority: "LOCAL_ENGINEERING_EVIDENCE" as const };
  let graph = right(parseResearchGraph({ manifest: { ...manifest, sources: [source, evidence] }, events: [] }));
  expect(Object.isFrozen(graph.manifest.sources[0])).toBe(true);
  graph = event(graph, { type: "START", id: "start", taskId: "explore-a", actor: "a", model: "astra", at: at(1) });
  graph = event(graph, { type: "FINISH", id: "finish", taskId: "explore-a", actor: "a", at: at(2), disposition: "REFUTED_IN_SCOPE", summary: "negative retained", sourceIds: [evidence.id], usedTokens: 1 });
  const context = right(researchTaskContext(graph, "critic"));
  expect(context["handoffSources"]).toEqual([evidence]);
  expect(Object.isFrozen(context["handoffSources"])).toBe(true);
});
