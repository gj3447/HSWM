/** Explicit, deterministic presentation; canonical source frames remain complete. */
import { Either, Schema } from "effect"
import { contextError, contextJson } from "./semantic-context-domain.js"
import type { ContextAssembly } from "./semantic-context-runtime.js"

export const ContextPresentationSchema = Schema.Literal("canonical_json", "execution_tail")
export const renderContextPrompt = (assembly: Pick<ContextAssembly, "payload">, raw: unknown = "canonical_json") => Either.gen(function* () {
  const mode = yield* Schema.decodeUnknownEither(ContextPresentationSchema)(raw).pipe(Either.mapLeft(() => contextError("PRESENTATION_INVALID", "Unknown context presentation")))
  const canonical = contextJson(assembly.payload)
  if (mode === "canonical_json") return canonical
  return ["Execute the supplied rules on EVENT, preserving mandatory constraints and exceptions. Return only JSON with prediction and uncertainty strings.",
    canonical, "EXECUTE NOW", ...assembly.payload.frames.map(f => f.relation.semantic.semanticText),
    "EVENT TO COMPUTE", assembly.payload.event, "Apply those rules to this event. Do not infer the answer from rule names."].join("\n")
})
