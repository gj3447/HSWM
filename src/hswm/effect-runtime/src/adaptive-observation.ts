/** Versioned local observations; digests identify values, never truth or causal credit. */
import { createHash } from "node:crypto";
import { type Guard, type Route, specializeGuard } from "./adaptive-domain.js";
import { type AdaptiveAtomRevision } from "./adaptive-store.js";

export const OBSERVATION_SCHEMA = "hswm-adaptive-observation/v1" as const;
export const SCOPE_SCHEMA = "hswm-adaptive-specialization-scope/v1" as const;
const ordered = (value: unknown): unknown => Array.isArray(value) ? value.map(ordered)
    : typeof value === "object" && value !== null
        ? Object.fromEntries(Object.entries(value).sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0).map(([key, item]) => [key, ordered(item)]))
        : value;
/** Only for already validated JSON values; this is not an untrusted JSON validator. */
export const observationDigest = (value: unknown): string => createHash("sha256").update(JSON.stringify(ordered(value)), "utf8").digest("hex");
export const revisionPin = (value: AdaptiveAtomRevision) => Object.freeze({
    uid: value.uid, revision: value.revision, digest: value.digest
});
export const routeMeaning = (route: Route) => ({
    source: route.source, members: route.members, reads: route.reads,
    cost_hint: route.cost_hint, guard: route.guard ?? null
});
export const guardReads = (guard: Guard): ReadonlyArray<string> => guard.op === "eq"
    ? [guard.left.field] : guard.op === "not" ? guardReads(guard.child) : guard.children.flatMap(guardReads);
export const boundSpecialization = (parent: AdaptiveAtomRevision, route: Route, selector: Guard) => {
    const guard = specializeGuard(route.guard, selector);
    const scope = {
        schema_version: SCOPE_SCHEMA, parent: revisionPin(parent),
        parent_meaning_digest: observationDigest(routeMeaning(route)),
        mandatory_guard: route.guard ?? null, selector, effective_guard: guard
    };
    const suffix = observationDigest(scope).slice(0, 20);
    const uid = `${parent.uid}:specialized:${suffix}`;
    const child: Route = {
        ...route, uid: uid.replace(/^relation:/, ""),
        reads: [...new Set([...route.reads, ...guardReads(guard)])].sort(), guard
    };
    return { uid, conditionUid: `condition:${suffix}:${parent.uid}`, route: child, scope };
};

/** Inclusive router times are deliberately excluded from leaf execution totals. */
export const episodeCosts = (leaves: ReadonlyArray<{ readonly trajectory: string; readonly durationSeconds: number }>, wallSeconds: number) => ({
    schema_version: OBSERVATION_SCHEMA,
    wall_seconds_before_completion_write: wallSeconds,
    leaf_execution_seconds: leaves.reduce((sum, leaf) => sum + leaf.durationSeconds, 0),
    leaf_occurrences: leaves.map((leaf) => leaf.trajectory),
    aggregation: "LEAF_OCCURRENCES_ONCE_NO_ROUTER_SUM",
    initial_integration_seconds: null, human_review_seconds: null,
    human_repair_seconds: null, human_explanation_seconds: null,
    monetary_cost: null, retry_cost: null,
    missing_costs: "NOT_MEASURED_NOT_ZERO",
    claim: "EXECUTION_OBSERVATION_NOT_NET_UTILITY"
});
