/** Explicit finite input/output binding and post-execution validation; never repairs predictions. */
import { Data, Either, Schema } from "effect"
import { CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, type CanonicalAtomV2Content } from "./canonical-atom-v2-schema.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { decodeFiniteProgram, finiteProgramAccepts } from "./semantic-context-finite-domain.js"
import { contextError, contextHash } from "./semantic-context-domain.js"
import type { SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"

const name = Schema.String.pipe(Schema.pattern(/^[A-Za-z][A-Za-z0-9_-]{0,63}$/))
export const FiniteExecutionGuardSchema = Schema.Struct({
  contract: Schema.Literal("hswm-finite-execution-guard/v1"),
  rules: Schema.Array(Schema.Struct({
    relationKey: CanonicalAtomV2KeySchema,
    inputs: Schema.Array(Schema.Struct({ variable: name, eventField: Schema.NonEmptyString.pipe(Schema.maxLength(128)) })).pipe(Schema.maxItems(16)),
    outputVariable: Schema.NullOr(name)
  })).pipe(Schema.minItems(1), Schema.maxItems(16))
})
export type FiniteExecutionGuard = typeof FiniteExecutionGuardSchema.Type
const invalid = (detail: string) => contextError("FINITE_BINDING_INVALID", detail)
const scalarText = (value: unknown) => typeof value === "string" || typeof value === "boolean" || typeof value === "number" && Number.isFinite(value)
  ? Either.right(String(value)) : Either.left(invalid("Event inputs must be JSON strings, finite numbers or booleans; no missing/null/object coercion"))

export const prepareFiniteExecutionGuard = (payload: { readonly event: string; readonly frames: readonly SemanticReadFrame[] }, raw: unknown) => Either.gen(function* () {
  const guard = yield* Schema.decodeUnknownEither(FiniteExecutionGuardSchema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => invalid("Expected explicit finite rule bindings")))
  if (payload.event.length > 8192) return yield* Either.left(invalid("Event exceeds the existing context limit"))
  const parsed = yield* decodeGeneralJsonBytes(new TextEncoder().encode(payload.event)).pipe(Either.mapLeft(() => invalid("Event must be strict JSON")))
  const event = yield* Schema.decodeUnknownEither(Schema.Record({ key: Schema.String, value: Schema.Unknown }))(parsed).pipe(Either.mapLeft(() => invalid("Event must be a JSON object")))
  const keys = guard.rules.map(r => canonicalAtomV2KeyId(r.relationKey))
  if (new Set(keys).size !== keys.length || guard.rules.length !== payload.frames.length ||
    payload.frames.some((f, i) => keys[i] !== canonicalAtomV2KeyId(f.relation.key)) || !guard.rules.some(r => r.outputVariable !== null)) return yield* Either.left(invalid("Bind every selected and mandatory frame exactly once, in frame order, with at least one output"))
  const rules = []
  for (const [i, binding] of guard.rules.entries()) {
    const frame = payload.frames[i]
    if (!frame) return yield* Either.left(invalid("Missing frame"))
    const program = yield* decodeFiniteProgram(frame.relation.semantic.semanticText).pipe(Either.mapLeft(e => invalid(e.detail)))
    const names = [...binding.inputs.map(b => b.variable), ...(binding.outputVariable === null ? [] : [binding.outputVariable])]
    if (new Set(names).size !== names.length || names.length !== program.variables.length ||
      program.variables.some(v => !names.includes(v.id) || frame.roles[v.roleOrdinal] === undefined)) return yield* Either.left(invalid("Each variable needs exactly one source and its original role occurrence"))
    const inputs = []
    for (const input of binding.inputs) {
      if (!Object.hasOwn(event, input.eventField)) return yield* Either.left(invalid("Missing event field"))
      const value = yield* scalarText(event[input.eventField])
      if (!program.variables.find(v => v.id === input.variable)?.values.includes(value)) return yield* Either.left(invalid("Event value lies outside the declared domain"))
      inputs.push({ variable: input.variable, value })
    }
    rules.push({ frameSha256: frame.frameSha256, relationKey: frame.relation.key, program, inputs, outputVariable: binding.outputVariable })
  }
  return { guard, eventSha256: contextHash(payload.event), rules }
})
export type PreparedFiniteExecution = Either.Either.Right<ReturnType<typeof prepareFiniteExecutionGuard>>
export const checkFiniteExecution = (prepared: PreparedFiniteExecution, prediction: string) => {
  const checks = prepared.rules.map(rule => {
    const row = rule.program.variables.map(v => v.id === rule.outputVariable ? prediction : rule.inputs.find(i => i.variable === v.id)?.value ?? "")
    return { relationKey: rule.relationKey, frameSha256: rule.frameSha256,
      assignment: Object.fromEntries(rule.program.variables.map((v, i) => [v.id, row[i]])), accepted: finiteProgramAccepts(rule.program, row) }
  })
  return { contract: "hswm-finite-execution-verdict/v1" as const, guardSha256: contextHash(prepared.guard), eventSha256: prepared.eventSha256,
    prediction, status: checks.every(c => c.accepted) ? "SATISFIED" as const : "VIOLATED" as const, checks,
    claimCeiling: "DECLARED_FINITE_CONSTRAINTS_ONLY_NOT_TASK_UTILITY_OR_MODEL_EFFICACY" as const }
}
export type FiniteExecutionVerdict = ReturnType<typeof checkFiniteExecution>
export class FiniteExecutionViolation extends Data.TaggedError("FiniteExecutionViolation")<{
  readonly code: "FINITE_EXECUTION_VIOLATION"
  readonly traceContent: CanonicalAtomV2Content
  readonly verification: FiniteExecutionVerdict
  readonly message: string
}> {}
