/** Explicit open-jev CLI adapter. Never called by preparation or offline receipt import. */
import { Effect, Either, Schema } from "effect"
import { parseJson } from "./adaptive-domain.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { contextError, contextJson, type ContextPlan } from "./semantic-context-domain.js"

export const requestOpenJevContext = (plan: ContextPlan, executable: string, cwd: string, environment: Readonly<Record<string, string>>) => Effect.gen(function* () {
  const subprocess = yield* BoundedSubprocess
  const result = yield* subprocess.observe({
    argv: [executable, "decide", "-"], cwd, environment,
    stdin: new TextEncoder().encode(contextJson(plan.request)),
    timeoutMs: 240_000, maximumOutputBytes: 131072, killProcessGroup: true
  })
  if (result.timedOut || result.outputTruncated || result.launchError !== null || result.signal !== null || ![0, 2].includes(result.exitCode ?? -1)) {
    return yield* Effect.fail(contextError("JEV_TRANSPORT_FAILED", "Jev did not return a complete bounded response; no semantic fallback inferred"))
  }
  const parsed = parseJson(new TextDecoder().decode(result.stdout))
  if (parsed._tag === "Left") return yield* Effect.fail(contextError("JEV_RECEIPT_INVALID", "Jev returned invalid JSON"))
  // Exit 2 is only a usable observation for the documented token-limit status.
  if (result.exitCode === 2 && Either.isLeft(Schema.decodeUnknownEither(Schema.Struct({ status: Schema.Literal("needs_original_selection") }))(parsed.right))) {
    return yield* Effect.fail(contextError("JEV_TRANSPORT_FAILED", "Jev exited with a validation or infrastructure refusal"))
  }
  return parsed.right
})
