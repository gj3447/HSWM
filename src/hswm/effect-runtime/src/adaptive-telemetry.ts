/**
 * Optional execution telemetry. This is a bounded operational projection, not
 * canonical provenance, an outcome judgment, causal credit, or learning input.
 */
import { Context, Effect } from "effect";
import type { AdaptiveExecution } from "./adaptive-executor.js";

export const ADAPTIVE_TELEMETRY_SCHEMA = "hswm-adaptive-telemetry/v1" as const;

type Attributes = Readonly<Record<string, string | number | boolean>>;

export interface AdaptiveEpisodeTelemetryInput {
    readonly episodeIdentitySha256: string;
}

export interface AdaptiveLeafTelemetryInput {
    readonly kind: "command" | "llm" | "unknown";
    readonly cellIdentitySha256: string;
    readonly configurationSha256: string;
    readonly toolIdentitySha256: string;
}

export interface AdaptiveTelemetryShape {
    readonly episode: <A, E, R>(input: AdaptiveEpisodeTelemetryInput, effect: Effect.Effect<A, E, R>) => Effect.Effect<A, E, R>;
    readonly leaf: <E, R>(input: AdaptiveLeafTelemetryInput, effect: Effect.Effect<AdaptiveExecution, E, R>) => Effect.Effect<AdaptiveExecution, E, R>;
}

const episodeAttributes = (input: AdaptiveEpisodeTelemetryInput): Attributes => Object.freeze({
    "hswm.telemetry.schema": ADAPTIVE_TELEMETRY_SCHEMA,
    "hswm.observation.role": "episode",
    "hswm.episode.identity.sha256": input.episodeIdentitySha256
});

const leafAttributes = (input: AdaptiveLeafTelemetryInput): Attributes => Object.freeze({
    "hswm.telemetry.schema": ADAPTIVE_TELEMETRY_SCHEMA,
    "hswm.observation.role": "leaf",
    "hswm.leaf.kind": input.kind,
    "hswm.cell.identity.sha256": input.cellIdentitySha256,
    "hswm.configuration.sha256": input.configurationSha256,
    "hswm.tool.identity.sha256": input.toolIdentitySha256
});

const executionAttributes = (execution: AdaptiveExecution): Attributes => Object.freeze({
    "hswm.execution.status": execution.status,
    "hswm.execution.duration.seconds": execution.durationSeconds,
    "hswm.execution.output.sha256": execution.outputDigest
});

const annotate = (attributes: Attributes) => Effect.currentSpan.pipe(
    Effect.tap((span) => Effect.sync(() => {
        for (const [key, value] of Object.entries(attributes)) span.attribute(key, value);
    })),
    Effect.catchAll(() => Effect.void)
);

const nativeEpisode = <A, E, R>(input: AdaptiveEpisodeTelemetryInput, effect: Effect.Effect<A, E, R>): Effect.Effect<A, E, R> => effect.pipe(
    Effect.withSpan("hswm.adaptive.episode", { attributes: episodeAttributes(input), kind: "internal" })
);
const nativeLeaf = <E, R>(input: AdaptiveLeafTelemetryInput, effect: Effect.Effect<AdaptiveExecution, E, R>): Effect.Effect<AdaptiveExecution, E, R> => effect.pipe(
        Effect.tap((execution) => annotate(executionAttributes(execution))),
        Effect.withSpan("hswm.adaptive.leaf", { attributes: leafAttributes(input), kind: "internal" })
    );
/** Uses Effect's native span stack but does not configure an exporter or network I/O. */
export const NativeAdaptiveTelemetry: AdaptiveTelemetryShape = Object.freeze({
    episode: nativeEpisode,
    leaf: nativeLeaf
});

/** The default preserves execution behavior and produces neither spans nor network traffic. */
const noopEpisode = <A, E, R>(_input: AdaptiveEpisodeTelemetryInput, effect: Effect.Effect<A, E, R>): Effect.Effect<A, E, R> => effect;
const noopLeaf = <E, R>(_input: AdaptiveLeafTelemetryInput, effect: Effect.Effect<AdaptiveExecution, E, R>): Effect.Effect<AdaptiveExecution, E, R> => effect;
export const NoopAdaptiveTelemetry: AdaptiveTelemetryShape = Object.freeze({
    episode: noopEpisode,
    leaf: noopLeaf
});

export class AdaptiveTelemetry extends Context.Reference<AdaptiveTelemetry>()(
    "hswm/AdaptiveTelemetry",
    { defaultValue: () => NoopAdaptiveTelemetry }
) {}
