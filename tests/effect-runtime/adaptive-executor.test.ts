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
