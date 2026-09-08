import { expect, it } from "vitest"
import { Effect, Layer } from "effect"
import { createServer, type IncomingMessage, type ServerResponse } from "node:http"

import { AdaptiveHttpClient, executeAdaptiveCell, NativeAdaptiveHttpClient } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

const localServer = async (handler: (request: IncomingMessage, response: ServerResponse) => void) => {
  const server = createServer(handler)
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const address = server.address()
  if (address === null || typeof address === "string") throw new Error("local server did not bind")
  return { server, url: `http://127.0.0.1:${address.port}` }
}
const close = (server: ReturnType<typeof createServer>) => new Promise<void>((resolve, reject) => server.close((error) => error === undefined ? resolve() : reject(error)))

it("never converts a truncated command observation into a measured success", async () => {
  const subprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({
    observe: () => Effect.succeed({ exitCode: 0, signal: null, timedOut: false, outputTruncated: true, launchError: null, stdout: new TextEncoder().encode("partial"), stderr: new Uint8Array() })
  }))
  const http = Layer.succeed(AdaptiveHttpClient, AdaptiveHttpClient.of({ postJson: () => Effect.die("must not call HTTP") }))
  const result = await Effect.runPromise(executeAdaptiveCell(
    { kind: "command", argv: ["ignored"], outcome: "exit_code" }, { task: "x" }, process.cwd(), 1_000
  ).pipe(Effect.provide(Layer.merge(subprocess, http))))
  expect(result.status).toBe("UNKNOWN")
  expect(result.success).toBeNull()
})

it("contains a cyclic structured payload as a failed execution", async () => {
  const payload: Record<string, unknown> = {}
  payload["self"] = payload
  const subprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({
    observe: () => Effect.die("must not launch")
  }))
  const http = Layer.succeed(AdaptiveHttpClient, AdaptiveHttpClient.of({ postJson: () => Effect.die("must not call HTTP") }))
  const exit = await Effect.runPromise(Effect.exit(executeAdaptiveCell(
    { kind: "command", argv: ["ignored"] }, payload, process.cwd(), 1_000
  ).pipe(Effect.provide(Layer.merge(subprocess, http)))))
  expect(exit._tag).toBe("Success")
})

it("aborts a request that never returns headers within its bound", async () => {
  let aborted = false
  const { server, url } = await localServer((request) => { request.on("aborted", () => { aborted = true }) })
  try {
    const exit = await Effect.runPromise(Effect.exit(NativeAdaptiveHttpClient.postJson({ url, headers: {}, body: new Uint8Array(), timeoutMs: 30, maximumResponseBytes: 128 })))
    expect(exit._tag).toBe("Failure")
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(aborted).toBe(true)
  } finally { await close(server) }
})

it("rejects oversized streams and malformed HTTP 200 model payloads", async () => {
  const { server, url } = await localServer((_request, response) => { response.writeHead(200, { "content-type": "application/json" }); response.end("x".repeat(512)) })
  try {
    const oversized = await Effect.runPromise(Effect.exit(NativeAdaptiveHttpClient.postJson({ url, headers: {}, body: new Uint8Array(), timeoutMs: 1_000, maximumResponseBytes: 32 })))
    expect(oversized._tag).toBe("Failure")
    const subprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die("must not launch") }))
    const http = Layer.succeed(AdaptiveHttpClient, NativeAdaptiveHttpClient)
    const result = await Effect.runPromise(executeAdaptiveCell({ kind: "llm", base_url: url, model: "local" }, { prompt: "x" }, process.cwd(), 1_000).pipe(Effect.provide(Layer.merge(subprocess, http))))
    expect(result.status).toBe("FAILED")
  } finally { await close(server) }
})

it("records only strictly validated provider usage and never promotes it to success", async () => {
  const subprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die("must not launch") }))
  const response = new TextEncoder().encode(JSON.stringify({ model: "provider-model-2026", usage: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 10 }, choices: [{ message: { content: "answer" } }] }))
  const http = Layer.succeed(AdaptiveHttpClient, AdaptiveHttpClient.of({ postJson: () => Effect.succeed(response) }))
  const result = await Effect.runPromise(executeAdaptiveCell(
    { kind: "llm", cell_id: "leaf", base_url: "https://provider.example/v1", model: "configured-model", api_key_env: "ADAPTIVE_TEST_SECRET" }, { prompt: "x" }, process.cwd(), 1_000
  ).pipe(Effect.provide(Layer.merge(subprocess, http))))
  expect(result.status).toBe("SUCCEEDED")
  expect(result.success).toBeNull()
  const observation = result.metadata["execution_observation_v1"] as Record<string, unknown>
  expect(observation["schema_version"]).toBe("hswm-adaptive-execution-observation/v1")
  expect(observation["configured_model"]).toBe("configured-model")
  expect(observation["output_digest"]).toBe(result.outputDigest)
  expect(observation["provider_usage"]).toEqual({ status: "REPORTED", prompt_tokens: 7, completion_tokens: 3, total_tokens: 10, reported_model: "provider-model-2026" })
  expect(JSON.stringify(observation)).not.toContain("ADAPTIVE_TEST_SECRET")
  expect(JSON.stringify(observation)).not.toContain("Bearer ")
})

it("marks missing or malformed provider usage as null rather than zero", async () => {
  const subprocess = Layer.succeed(BoundedSubprocess, BoundedSubprocess.of({ observe: () => Effect.die("must not launch") }))
  for (const [raw, status] of [
    [{ choices: [{ message: { content: "answer" } }] }, "UNAVAILABLE"],
    [{ usage: { prompt_tokens: 2, completion_tokens: 1, total_tokens: 99 }, choices: [{ message: { content: "answer" } }] }, "INVALID"]
  ] as const) {
    const http = Layer.succeed(AdaptiveHttpClient, AdaptiveHttpClient.of({ postJson: () => Effect.succeed(new TextEncoder().encode(JSON.stringify(raw))) }))
    const result = await Effect.runPromise(executeAdaptiveCell({ kind: "llm", base_url: "https://provider.example", model: "configured" }, { prompt: "x" }, process.cwd(), 1_000).pipe(Effect.provide(Layer.merge(subprocess, http))))
    const usage = (result.metadata["execution_observation_v1"] as { provider_usage: Record<string, unknown> }).provider_usage
    expect(usage["status"]).toBe(status)
    expect(usage["prompt_tokens"]).toBeNull()
    expect(usage["completion_tokens"]).toBeNull()
    expect(usage["total_tokens"]).toBeNull()
  }
})
