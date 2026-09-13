/** Official Temporal and OTLP adapters for the bounded infrastructure smoke. */
import { Context, Effect } from "effect";
import { Connection, WorkflowClient } from "@temporalio/client";
import { NativeConnection, Worker } from "@temporalio/worker";
import { SearchAttributeType, TypedSearchAttributes, defineSearchAttributeKey } from "@temporalio/common";
import { BasicTracerProvider, SimpleSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { completeResearchFabricSmoke, NativeInfrastructureSmokeError, validateResearchFabricRunId, NATIVE_RESEARCH_FABRIC_SMOKE_ACTIVITY, NATIVE_RESEARCH_FABRIC_SMOKE_WORKFLOW, type ResearchFabricSmokeResult, type TemporalSmokeResult, } from "./native-infrastructure-smoke-domain.js";
export interface ResearchFabricTemporalShape {
    readonly execute: (runId: string) => Effect.Effect<TemporalSmokeResult, NativeInfrastructureSmokeError>;
}
export class ResearchFabricTemporal extends Context.Tag("hswm/ResearchFabricTemporal")<ResearchFabricTemporal, ResearchFabricTemporalShape>() {
}
export interface ResearchFabricTraceShape {
    readonly emit: (result: ResearchFabricSmokeResult) => Effect.Effect<void, NativeInfrastructureSmokeError>;
}
export class ResearchFabricTrace extends Context.Tag("hswm/ResearchFabricTrace")<ResearchFabricTrace, ResearchFabricTraceShape>() {
}
const failure = (code: NativeInfrastructureSmokeError["code"], detail: string) => new NativeInfrastructureSmokeError({ code, detail });
const attempt = <A>(code: NativeInfrastructureSmokeError["code"], detail: string, run: () => Promise<A>) => Effect.tryPromise({ try: run, catch: () => failure(code, detail) });
const release = (close: () => Promise<unknown>) => attempt("TEMPORAL_INVALID", "infrastructure resource cleanup failed", close).pipe(Effect.timeoutOption("5 seconds"), Effect.ignore);
export const runResearchFabricSmoke = (runId: string): Effect.Effect<ResearchFabricSmokeResult, NativeInfrastructureSmokeError, ResearchFabricTemporal | ResearchFabricTrace> => Effect.gen(function* () {
    yield* validateResearchFabricRunId(runId);
    const temporal = yield* ResearchFabricTemporal;
    const trace = yield* ResearchFabricTrace;
    const result = yield* completeResearchFabricSmoke(runId, yield* temporal.execute(runId));
    yield* trace.emit(result);
    return result;
});
export const smokeSearchAttributes = (runId: string): TypedSearchAttributes => new TypedSearchAttributes([
    { key: defineSearchAttributeKey("HswmRunId", SearchAttributeType.KEYWORD), value: runId },
    { key: defineSearchAttributeKey("HswmSchemaVersion", SearchAttributeType.KEYWORD), value: "none-infrastructure-smoke" },
    { key: defineSearchAttributeKey("HswmOutcome", SearchAttributeType.KEYWORD), value: "PASS" },
]);
const executeTemporal = (client: WorkflowClient, runId: string): Promise<TemporalSmokeResult> => client.execute<(value: {
    readonly run_id: string;
}) => Promise<TemporalSmokeResult["result"]>>(NATIVE_RESEARCH_FABRIC_SMOKE_WORKFLOW, {
    args: [{ run_id: runId }], taskQueue: "hswm-research-fabric-smoke", workflowId: `hswm-infra-smoke-${runId}`,
    workflowExecutionTimeout: 30000, memo: { claim_boundary: "infrastructure smoke only" }, typedSearchAttributes: smokeSearchAttributes(runId),
}).then(result => Object.freeze({ workflow_id: `hswm-infra-smoke-${runId}`, result }));
export const makeResearchFabricTemporal = (client: WorkflowClient): ResearchFabricTemporalShape => Object.freeze({
    execute: (runId: string) => attempt("TEMPORAL_INVALID", "Temporal smoke workflow failed", () => executeTemporal(client, runId)),
});
export const hswm_research_fabric_smoke_activity = (value: {
    readonly run_id: string;
}): Promise<TemporalSmokeResult["result"]> => Promise.resolve(Object.freeze({ run_id: value.run_id, status: "PASS", claim_boundary: "infrastructure smoke only" }));
/** Worker and client have their own official connection types, each with a scoped finalizer. */
export const runResearchFabricTemporalLifecycle = (runId: string, workflowsPath: string): Effect.Effect<TemporalSmokeResult, NativeInfrastructureSmokeError> => Effect.acquireUseRelease(attempt("TEMPORAL_INVALID", "Temporal worker connection failed", () => NativeConnection.connect({ address: "127.0.0.1:7233" })), workerConnection => Effect.acquireUseRelease(attempt("TEMPORAL_INVALID", "Temporal client connection failed", () => Connection.connect({ address: "127.0.0.1:7233", connectTimeout: "10 seconds" })), clientConnection => Effect.acquireUseRelease(attempt("TEMPORAL_INVALID", "Temporal smoke worker creation failed", () => Worker.create({ connection: workerConnection, namespace: "hswm-dev", taskQueue: "hswm-research-fabric-smoke", workflowsPath, shutdownGraceTime: "1 second", activities: { [NATIVE_RESEARCH_FABRIC_SMOKE_ACTIVITY]: hswm_research_fabric_smoke_activity } })).pipe(Effect.map(worker => ({ worker, execution: { promise: null as Promise<TemporalSmokeResult> | null } }))), ({ worker, execution }) => attempt("TEMPORAL_INVALID", "Temporal smoke workflow failed", () => {
    const client = new WorkflowClient({ connection: clientConnection, namespace: "hswm-dev" });
    execution.promise = worker.runUntil(() => executeTemporal(client, runId));
    return execution.promise;
}).pipe(Effect.timeoutFail({ duration: "45 seconds", onTimeout: () => failure("TEMPORAL_INVALID", "Temporal smoke exceeded its deadline") })), ({ worker, execution }) => release(() => { if (worker.getState() === "RUNNING")
    worker.shutdown(); return execution.promise === null ? Promise.resolve() : execution.promise.then(() => undefined, () => undefined); })), connection => release(() => connection.close())), connection => release(() => connection.close()));
/** A real SDK span carries the original five attributes and is flushed before success. */
export const emitResearchFabricTrace = (result: ResearchFabricSmokeResult, secret: string): Effect.Effect<void, NativeInfrastructureSmokeError> => Effect.acquireUseRelease(Effect.sync(() => {
    const outcomes: number[] = [];
    const exporter = new OTLPTraceExporter({ url: "http://127.0.0.1:6006/v1/traces", headers: { Authorization: `Bearer ${secret}` }, timeoutMillis: 10000 });
    const processor = new SimpleSpanProcessor({
        export: (spans, callback) => exporter.export(spans, outcome => { outcomes.push(outcome.code); callback(outcome); }),
        shutdown: () => exporter.shutdown(),
        forceFlush: () => exporter.forceFlush(),
    });
    return { outcomes, provider: new BasicTracerProvider({ resource: resourceFromAttributes({ "openinference.project.name": "hswm-research-fabric-smoke" }), spanProcessors: [processor] }) };
}), ({ provider, outcomes }) => Effect.gen(function* () {
    yield* Effect.sync(() => {
        const span = provider.getTracer("hswm.infrastructure.research_fabric").startSpan("hswm.infrastructure.smoke");
        span.setAttributes({ "hswm.run.id": result.run_id, "hswm.projection.kind": "infrastructure_smoke", "hswm.claim.boundary": "infrastructure smoke only", "hswm.temporal.workflow_id": result.temporal.workflow_id, "hswm.temporal.result_sha256": result.phoenix_result_sha256 });
        span.end();
    });
    yield* attempt("TRACE_REFUSED", "OTLP smoke flush failed", () => provider.forceFlush()).pipe(Effect.timeoutFail({ duration: "12 seconds", onTimeout: () => failure("TRACE_REFUSED", "OTLP smoke flush exceeded its deadline") }));
    if (outcomes.length !== 1 || outcomes[0] !== 0)
        return yield* Effect.fail(failure("TRACE_REFUSED", "OTLP smoke export was not acknowledged"));
}), ({ provider }) => release(() => provider.shutdown()));
