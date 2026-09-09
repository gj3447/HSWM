/** Optional loopback-only OTLP wiring for the bounded adaptive telemetry projection. */
import { NodeSdk, Resource, Tracer } from "@effect/opentelemetry";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import type { Context as OtelContext } from "@opentelemetry/api";
import { BatchSpanProcessor, type ReadableSpan, type Span, type SpanProcessor } from "@opentelemetry/sdk-trace-base";
import { Either, Layer } from "effect";
import { AdaptiveTelemetry, NativeAdaptiveTelemetry } from "./adaptive-telemetry.js";

export const ADAPTIVE_OTLP_EXPORT_TIMEOUT_MS = 500;

const ALLOWED_ATTRIBUTES = Object.freeze([
    "hswm.telemetry.schema", "hswm.observation.role", "hswm.episode.identity.sha256",
    "hswm.leaf.kind", "hswm.cell.identity.sha256", "hswm.configuration.sha256",
    "hswm.tool.identity.sha256", "hswm.execution.status", "hswm.execution.duration.seconds",
    "hswm.execution.output.sha256"
]);

/**
 * Limits the standard SDK export surface after Effect has completed a span.
 * Effect's default error conversion may add exception messages and stacks, so
 * those events and status messages are intentionally removed here.
 */
class BoundedSpanProcessor implements SpanProcessor {
    constructor(readonly delegate: SpanProcessor) {}
    forceFlush = (): Promise<void> => this.delegate.forceFlush();
    shutdown = (): Promise<void> => this.delegate.shutdown();
    onStart = (span: Span, parentContext: OtelContext): void => this.delegate.onStart(span, parentContext);
    onEnd = (span: ReadableSpan): void => {
        const attributes = Object.fromEntries(Object.entries(span.attributes).filter(([key]) => ALLOWED_ATTRIBUTES.includes(key)));
        const bounded = Object.freeze(Object.assign(Object.create(span), {
            attributes: Object.freeze(attributes), events: Object.freeze([]),
            links: Object.freeze([]), status: Object.freeze({ code: span.status.code })
        })) as ReadableSpan;
        this.delegate.onEnd(bounded);
    };
}

export interface AdaptiveOtlpConfiguration {
    readonly endpoint: string;
    readonly bearerToken: string | null;
}

const validLoopbackEndpoint = (value: string): boolean => {
    try {
        const url = new URL(value);
        return url.protocol === "http:" && url.hostname === "127.0.0.1" && url.username === "" && url.password === ""
            && url.search === "" && url.hash === "" && url.pathname === "/v1/traces";
    }
    catch { return false; }
};

/** Validates an explicitly enabled local collector; it never discovers a collector or exports by default. */
export const parseAdaptiveOtlpConfiguration = (endpoint: string | undefined, bearerToken: string | undefined): Either.Either<AdaptiveOtlpConfiguration | null, "ENDPOINT_INVALID" | "TOKEN_INVALID" | "AMBIENT_OTLP_CONFIGURATION_FORBIDDEN"> => {
    if (endpoint === undefined || endpoint === "") return Either.right(null);
    if (Object.keys(process.env).some((key) => key === "OTEL_EXPORTER_OTLP" || key.startsWith("OTEL_EXPORTER_OTLP_"))) return Either.left("AMBIENT_OTLP_CONFIGURATION_FORBIDDEN");
    if (!validLoopbackEndpoint(endpoint)) return Either.left("ENDPOINT_INVALID");
    if (bearerToken !== undefined && (bearerToken.length < 1 || bearerToken.length > 4096)) return Either.left("TOKEN_INVALID");
    return Either.right(Object.freeze({ endpoint, bearerToken: bearerToken ?? null }));
};

/**
 * Native Effect-to-OTLP layer. Batching makes exporter work asynchronous, and
 * its bounded timeout prevents shutdown from becoming an unbounded task path.
 */
/** Does not read OTEL resource or exporter environment variables. */
export const makeAdaptiveTelemetryLayer = (processor: SpanProcessor) => Layer.merge(
    Layer.provide(
        Tracer.layer,
        (() => {
            const resource = Resource.layer({ serviceName: "hswm-adaptive-runtime", attributes: { "hswm.telemetry.schema": "hswm-adaptive-telemetry/v1" } });
            const provider = Layer.provide(NodeSdk.layerTracerProvider(new BoundedSpanProcessor(processor), { shutdownTimeout: ADAPTIVE_OTLP_EXPORT_TIMEOUT_MS }), resource);
            return Layer.merge(resource, provider);
        })()
    ),
    Layer.succeed(AdaptiveTelemetry, NativeAdaptiveTelemetry)
);

export const makeAdaptiveOtlpTelemetryLayer = (configuration: AdaptiveOtlpConfiguration) => makeAdaptiveTelemetryLayer(
    new BatchSpanProcessor(new OTLPTraceExporter({
            url: configuration.endpoint,
            timeoutMillis: ADAPTIVE_OTLP_EXPORT_TIMEOUT_MS,
            ...(configuration.bearerToken === null ? {} : { headers: { authorization: `Bearer ${configuration.bearerToken}` } })
        }), { scheduledDelayMillis: 200, exportTimeoutMillis: ADAPTIVE_OTLP_EXPORT_TIMEOUT_MS, maxQueueSize: 256, maxExportBatchSize: 64 })
);
