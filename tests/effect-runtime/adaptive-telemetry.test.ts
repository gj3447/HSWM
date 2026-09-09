import { expect, it } from "vitest"
import { Effect, Either, Layer, Option, Tracer } from "effect"
import { InMemorySpanExporter } from "../../src/hswm/effect-runtime/node_modules/@opentelemetry/sdk-trace-base/build/esm/export/InMemorySpanExporter.js"
import { SimpleSpanProcessor } from "../../src/hswm/effect-runtime/node_modules/@opentelemetry/sdk-trace-base/build/esm/export/SimpleSpanProcessor.js"

import { AdaptiveHttpClient, executeAdaptiveCell } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { AdaptiveTelemetry, NativeAdaptiveTelemetry, NoopAdaptiveTelemetry } from "../../src/hswm/effect-runtime/src/adaptive-telemetry.js"
import { makeAdaptiveOtlpTelemetryLayer, makeAdaptiveTelemetryLayer, parseAdaptiveOtlpConfiguration } from "../../src/hswm/effect-runtime/src/adaptive-telemetry-otlp.js"
import { NodeBoundedSubprocessLive } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

type CapturedSpan = {
  readonly name: string
  readonly traceId: string
  readonly parentId: string | null
  readonly attributes: ReadonlyMap<string, unknown>
}

const tracer = (captured: CapturedSpan[]) => {
  let sequence = 0
  return Tracer.make({
    context: (evaluate) => evaluate(),
    span: (name, parent, context, links, startTime, kind, options) => {
      const spanId = `span-${sequence++}`
      const span = {
        _tag: "Span" as const, name, spanId,
        traceId: Option.isSome(parent) ? parent.value.traceId : `trace-${spanId}`,
        parent, context, links, startTime, kind, sampled: true,
        status: { _tag: "Started" as const, startTime },
        attributes: new Map(Object.entries(options?.attributes ?? {})),
        end: () => { captured.push({ name, traceId: span.traceId, parentId: Option.isSome(parent) ? parent.value.spanId : null, attributes: new Map(span.attributes) }) },
        attribute: (key: string, value: unknown) => { span.attributes.set(key, value) },
        event: () => undefined,
        addLinks: () => undefined
      }
      return span
    }
  })
}

const command = Object.freeze({
  cell_id: "leaf-secret-should-not-export", kind: "command", owner: "test",
  input_type: "task", output_type: "result",
  argv: [process.execPath, "-e", "process.stdout.write('response-secret')"], outcome: "exit_code"
})

const execute = (telemetry: typeof NativeAdaptiveTelemetry | typeof NoopAdaptiveTelemetry, captured: CapturedSpan[]) =>
  Effect.runPromise(AdaptiveTelemetry.pipe(Effect.flatMap((service) => service.episode(
    { episodeIdentitySha256: "episode-digest" },
    executeAdaptiveCell(command, { prompt: "prompt-secret", api_key: "key-secret" }, process.cwd(), 5_000)
  ))).pipe(
    Effect.provideService(AdaptiveTelemetry, telemetry),
    Effect.provideService(AdaptiveHttpClient, { postJson: () => Effect.die("unexpected HTTP") }),
    Effect.provide(NodeBoundedSubprocessLive),
    Effect.withTracer(tracer(captured))
  ))

it("keeps executor behavior unchanged when optional telemetry is disabled", async () => {
  const withoutTelemetry: CapturedSpan[] = []
  const withTelemetry: CapturedSpan[] = []
  const plain = await execute(NoopAdaptiveTelemetry, withoutTelemetry)
  const traced = await execute(NativeAdaptiveTelemetry, withTelemetry)
  expect({ status: traced.status, success: traced.success, output: traced.output, outputDigest: traced.outputDigest }).toEqual(
    { status: plain.status, success: plain.success, output: plain.output, outputDigest: plain.outputDigest }
  )
  expect(withoutTelemetry).toHaveLength(0)
  expect(withTelemetry).toHaveLength(2)
})

it("creates nested bounded spans without prompt, response, key, owner, or outcome fields", async () => {
  const captured: CapturedSpan[] = []
  await execute(NativeAdaptiveTelemetry, captured)
  const episode = captured.find((span) => span.name === "hswm.adaptive.episode")
  const leaf = captured.find((span) => span.name === "hswm.adaptive.leaf")
  expect(episode?.name).toBe("hswm.adaptive.episode")
  expect(leaf?.name).toBe("hswm.adaptive.leaf")
  expect(leaf?.traceId).toBe(episode?.traceId)
  expect(leaf?.parentId).not.toBeNull()
  const serialized = JSON.stringify(captured.map((span) => Object.fromEntries(span.attributes)))
  for (const forbidden of ["prompt-secret", "response-secret", "key-secret", "leaf-secret-should-not-export", "owner", "success", "outcome", "traceRef", "Permit", "credit"]) expect(serialized).not.toContain(forbidden)
  expect(Object.keys(Object.fromEntries(leaf?.attributes ?? [])).sort()).toEqual([
    "hswm.cell.identity.sha256", "hswm.configuration.sha256", "hswm.execution.duration.seconds",
    "hswm.execution.output.sha256", "hswm.execution.status", "hswm.leaf.kind",
    "hswm.observation.role", "hswm.telemetry.schema", "hswm.tool.identity.sha256"
  ])
})

it("bounds an unavailable loopback exporter without changing the completed task", async () => {
  const parsed = parseAdaptiveOtlpConfiguration("http://127.0.0.1:1/v1/traces", undefined)
  if (Either.isLeft(parsed) || parsed.right === null) throw new Error("expected explicit telemetry configuration")
  const configuration = parsed.right
  const started = Date.now()
  const result = await Effect.runPromise(Effect.scoped(AdaptiveTelemetry.pipe(Effect.flatMap((service) => service.episode(
    { episodeIdentitySha256: "episode-digest" },
    executeAdaptiveCell(command, { prompt: "prompt-secret" }, process.cwd(), 5_000)
  ))).pipe(Effect.provide(Layer.mergeAll(
    NodeBoundedSubprocessLive,
    Layer.succeed(AdaptiveHttpClient, { postJson: () => Effect.die("unexpected HTTP") }),
    makeAdaptiveOtlpTelemetryLayer(configuration)
  )))))
  expect(result.status).toBe("SUCCEEDED")
  expect(Date.now() - started).toBeLessThan(2_000)
})

it("removes Effect error text, stacks, inherited resource values, and undeclared attributes before SDK export", async () => {
  const priorAttributes = process.env["OTEL_RESOURCE_ATTRIBUTES"]
  const priorService = process.env["OTEL_SERVICE_NAME"]
  process.env["OTEL_RESOURCE_ATTRIBUTES"] = "resource.secret=resource-secret"
  process.env["OTEL_SERVICE_NAME"] = "service-secret"
  try {
  const exporter = new InMemorySpanExporter()
  const retained: ReturnType<typeof exporter.getFinishedSpans> = []
  const exportSpans = exporter.export.bind(exporter)
  exporter.export = (spans, callback) => { retained.push(...spans); exportSpans(spans, callback) }
  const processor = new SimpleSpanProcessor(exporter)
  await Effect.runPromise(Effect.scoped(Effect.exit(AdaptiveTelemetry.pipe(Effect.flatMap((service) => service.episode(
    { episodeIdentitySha256: "episode-digest" },
    Effect.annotateCurrentSpan("undeclared.secret", "attribute-secret").pipe(
      Effect.zipRight(Effect.fail(new Error("failure-secret: prompt-secret key-secret")))
    )
  ))).pipe(Effect.provide(makeAdaptiveTelemetryLayer(processor)))).pipe(
    Effect.zipRight(Effect.promise(() => processor.forceFlush()))
  )))
  const spans = retained
  expect(spans).toHaveLength(1)
  const span = spans[0]!
  const serialized = JSON.stringify(span)
  for (const forbidden of ["failure-secret", "prompt-secret", "key-secret", "attribute-secret", "resource-secret", "service-secret", "exception", "stack", "process.command", "OTEL_"]) expect(serialized).not.toContain(forbidden)
  expect(span.events).toEqual([])
  expect(span.status.message).toBeUndefined()
  expect(Object.keys(span.attributes).sort()).toEqual([
    "hswm.episode.identity.sha256", "hswm.observation.role", "hswm.telemetry.schema"
  ])
  expect(Object.keys(span.resource.attributes).sort()).toEqual([
    "hswm.telemetry.schema", "service.name", "telemetry.sdk.language", "telemetry.sdk.name"
  ])
  } finally {
    if (priorAttributes === undefined) delete process.env["OTEL_RESOURCE_ATTRIBUTES"]
    else process.env["OTEL_RESOURCE_ATTRIBUTES"] = priorAttributes
    if (priorService === undefined) delete process.env["OTEL_SERVICE_NAME"]
    else process.env["OTEL_SERVICE_NAME"] = priorService
  }
})

it("refuses ambient OTLP endpoint and header configuration instead of inheriting it", () => {
  const prior = process.env["OTEL_EXPORTER_OTLP_HEADERS"]
  process.env["OTEL_EXPORTER_OTLP_HEADERS"] = "authorization=ambient-secret"
  try {
    const parsed = parseAdaptiveOtlpConfiguration("http://127.0.0.1:6006/v1/traces", undefined)
    expect(Either.isLeft(parsed) && parsed.left).toBe("AMBIENT_OTLP_CONFIGURATION_FORBIDDEN")
  } finally {
    if (prior === undefined) delete process.env["OTEL_EXPORTER_OTLP_HEADERS"]
    else process.env["OTEL_EXPORTER_OTLP_HEADERS"] = prior
  }
})
