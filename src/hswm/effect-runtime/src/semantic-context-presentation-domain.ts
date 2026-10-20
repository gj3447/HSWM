/** Explicit, deterministic presentation; canonical source frames remain complete. */
import { Either, Schema } from "effect"
import { contextError, contextJson } from "./semantic-context-domain.js"
import type { ContextAssembly } from "./semantic-context-runtime.js"
import { compileFiniteRuleTable } from "./semantic-context-finite-presentation-domain.js"
import type { FiniteExecutionGuard } from "./semantic-context-finite-execution-domain.js"

export const ContextPresentationSchema = Schema.Literal("canonical_json", "execution_tail", "finite_table_tail")
export type ContextPresentation = typeof ContextPresentationSchema.Type
export const renderContextPrompt = (assembly: Pick<ContextAssembly, "payload">, raw: unknown = "canonical_json") => Either.gen(function* () {
  const mode = yield* Schema.decodeUnknownEither(ContextPresentationSchema)(raw).pipe(Either.mapLeft(() => contextError("PRESENTATION_INVALID", "Unknown context presentation")))
  const canonical = contextJson(assembly.payload)
  if (mode === "canonical_json") return canonical
  if (mode === "finite_table_tail") {
    const tables = yield* Either.all(assembly.payload.frames.map(compileFiniteRuleTable))
    return ["Execute the supplied rules on EVENT, preserving mandatory constraints and exceptions. Return only JSON with prediction and uncertainty strings.",
      canonical, "EXECUTE THE EQUIVALENT COMPLETE RULE TABLES BELOW", ...tables.map(t => t.text),
      "Use EVENT values to match input columns; choose an output that satisfies every supplied table. Never choose from rule names.",
      "EVENT TO COMPUTE", assembly.payload.event, "Return only JSON with prediction and uncertainty strings."].join("\n")
  }
  return ["Execute the supplied rules on EVENT, preserving mandatory constraints and exceptions. Return only JSON with prediction and uncertainty strings.",
    canonical, "EXECUTE NOW", ...assembly.payload.frames.map(f => f.relation.semantic.semanticText),
    "EVENT TO COMPUTE", assembly.payload.event, "Apply those rules to this event. Do not infer the answer from rule names."].join("\n")
})

/** The same explicit field mapping is visible to the executor and the verifier. */
export const renderVerifiedContextPrompt = (assembly: Pick<ContextAssembly, "payload">, presentation: ContextPresentation, guard?: FiniteExecutionGuard) =>
  renderContextPrompt(assembly, presentation).pipe(Either.map(prompt => guard === undefined ? prompt :
    [prompt, "EXPLICIT INPUT/OUTPUT BINDINGS", contextJson(guard),
      "Each input reads its named top-level EVENT field as text: JSON strings unchanged; finite numbers and booleans use String(value).",
      "Your prediction string supplies every non-null outputVariable. All bound rules must hold. Return prediction and uncertainty only."].join("\n")))
