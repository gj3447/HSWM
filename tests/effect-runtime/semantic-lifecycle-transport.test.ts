import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { describe, expect, it } from "vitest"
import { AdaptiveExecutorError, AdaptiveHttpClient } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import type { AdaptiveHttpRequest } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { Effect, Layer } from "effect"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { INITIAL_TEXT } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"
import { createSemanticLifecycleTransport } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-transport.js"

const layer = (postJson: (request: unknown) => Effect.Effect<Uint8Array, AdaptiveExecutorError>) =>
  Layer.merge(NodePosixServicesLive, Layer.succeed(AdaptiveHttpClient, { postJson }))

const request = (headers: Readonly<Record<string, string>>) => Object.freeze({
  url: "https://private.example/v1",
  headers,
  timeoutMs: 60_000,
  maximumResponseBytes: 8_192,
  body: new TextEncoder().encode(JSON.stringify({ messages: [{ role: "user", content: JSON.stringify({
    contract: "hswm-llm-semantic-predict/v1",
    frame: {
      frameSha256: "a".repeat(64),
      event: JSON.stringify({ cases: [{ input: { power: true, locked: false, pressed: true, manualRelease: false } }] }),
      relation: {
        key: { schemaVersion: "v1", lineageId: "l1", atomUid: "relation:door", revisionId: 0 },
        semantic: { semanticText: INITIAL_TEXT, disposition: "predict", uncertainty: "fixture", exceptionRefs: [] }
      }
    }
  }) }] }))
})

describe("semantic lifecycle transport", () => {
  it("records a bounded failed HTTP attempt without persisting headers or credential values", async () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-semantic-lifecycle-transport-"))
    const secret = "Bearer do-not-persist-this-token"
    const seen: Array<AdaptiveHttpRequest> = []
    try {
      const program = Effect.gen(function* () {
        const transport = yield* createSemanticLifecycleTransport({ mode: "http", logRoot: root })
        const attempted = yield* transport.http.postJson(request({ authorization: secret, "x-private-key": "also-secret" })).pipe(Effect.either)
        return { attempted, calls: yield* transport.calls }
      }).pipe(Effect.provide(layer((upstreamRequest) => {
        seen.push(upstreamRequest as AdaptiveHttpRequest)
        return Effect.fail(new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: `upstream rejected ${secret}` }))
      })))
      const result = await Effect.runPromise(program)

      expect(result.attempted._tag).toBe("Left")
      if (result.attempted._tag === "Left") {
        expect(result.attempted.left.code).toBe("HTTP_FAILED")
        expect(result.attempted.left.detail).toBe("HTTP transport failed")
      }
      expect(result.calls).toHaveLength(1)
      expect(result.calls[0]).toMatchObject({ httpModelRequest: true, status: "TRANSPORT_FAILED", responseSha256: null })
      expect(seen).toHaveLength(1)
      expect(seen[0]?.timeoutMs).toBe(30_000)
      expect(seen[0]?.headers).toEqual({ authorization: secret, "x-private-key": "also-secret" })
      expect(statSync(root).mode & 0o777).toBe(0o700)
      for (const file of readdirSync(root)) {
        const path = join(root, file)
        expect(statSync(path).mode & 0o777).toBe(0o600)
        const saved = readFileSync(path, "utf8")
        expect(saved).not.toContain(secret)
        expect(saved).not.toContain("also-secret")
        expect(saved).not.toContain('"headers"')
      }
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
})
