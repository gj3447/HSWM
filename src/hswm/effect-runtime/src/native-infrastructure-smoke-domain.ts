/** Contracts for infrastructure checks only; these results never establish HSWM efficacy. */
import { createHash } from "node:crypto";
import { Data, Either } from "effect";
export const RESEARCH_FABRIC_SMOKE_CLAIM_BOUNDARY = "infrastructure smoke; not HSWM cognition, learning, or efficacy" as const;
export const RESEARCH_FABRIC_SMOKE_SCHEMA = "hswm-research-fabric-smoke/v1" as const;
export class NativeInfrastructureSmokeError extends Data.TaggedError("NativeInfrastructureSmokeError")<{
    readonly code: "RUN_ID_INVALID" | "TEMPORAL_INVALID" | "TRACE_REFUSED" | "SECRET_INVALID" | "USAGE";
    readonly detail: string;
}> {
}
export interface TemporalSmokeResult {
    readonly workflow_id: string;
    readonly result: {
        readonly run_id: string;
        readonly status: "PASS";
        readonly claim_boundary: "infrastructure smoke only";
    };
}
export interface ResearchFabricSmokeResult {
    readonly schema: typeof RESEARCH_FABRIC_SMOKE_SCHEMA;
    readonly claim_boundary: typeof RESEARCH_FABRIC_SMOKE_CLAIM_BOUNDARY;
    readonly run_id: string;
    readonly temporal: TemporalSmokeResult;
    readonly phoenix_result_sha256: string;
    readonly status: "PASS";
}
const fail = <A = never>(code: NativeInfrastructureSmokeError["code"], detail: string): Either.Either<A, NativeInfrastructureSmokeError> => Either.left(new NativeInfrastructureSmokeError({ code, detail }));
const sortJson = (value: unknown): unknown => Array.isArray(value) ? value.map(sortJson) : typeof value === "object" && value !== null ? Object.fromEntries(Object.keys(value).sort().map(key => [key, sortJson((value as Record<string, unknown>)[key])])) : value;
const canonical = (value: unknown): string => JSON.stringify(sortJson(value));
const digest = (value: unknown): string => createHash("sha256").update(canonical(value)).digest("hex");
export const validateResearchFabricRunId = (runId: string): Either.Either<string, NativeInfrastructureSmokeError> => typeof runId === "string" && runId.length > 0 && /^[A-Za-z0-9-]+$/.test(runId) ? Either.right(runId) : fail("RUN_ID_INVALID", "run_id must be nonempty ASCII alphanumeric and hyphen");
const isRecord = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value);
export const completeResearchFabricSmoke = (runId: string, temporal: unknown): Either.Either<ResearchFabricSmokeResult, NativeInfrastructureSmokeError> => {
    const valid = validateResearchFabricRunId(runId);
    if (Either.isLeft(valid))
        return Either.left(valid.left);
    if (!isRecord(temporal) || Object.keys(temporal).length !== 2 || temporal["workflow_id"] !== `hswm-infra-smoke-${runId}` || !isRecord(temporal["result"]))
        return fail("TEMPORAL_INVALID", "Temporal result does not satisfy the smoke contract");
    const value = temporal["result"];
    if (Object.keys(value).length !== 3 || value["run_id"] !== runId || value["status"] !== "PASS" || value["claim_boundary"] !== "infrastructure smoke only")
        return fail("TEMPORAL_INVALID", "Temporal result does not satisfy the smoke contract");
    const verified: TemporalSmokeResult = Object.freeze({ workflow_id: `hswm-infra-smoke-${runId}`, result: Object.freeze({ run_id: runId, status: "PASS", claim_boundary: "infrastructure smoke only" }) });
    return Either.right(Object.freeze({ schema: RESEARCH_FABRIC_SMOKE_SCHEMA, claim_boundary: RESEARCH_FABRIC_SMOKE_CLAIM_BOUNDARY, run_id: runId, temporal: verified, phoenix_result_sha256: digest(verified), status: "PASS" }));
};
export const NATIVE_RESEARCH_FABRIC_SMOKE_WORKFLOW = "hswm_research_fabric_smoke_workflow" as const;
export const NATIVE_RESEARCH_FABRIC_SMOKE_ACTIVITY = "hswm_research_fabric_smoke_activity" as const;
