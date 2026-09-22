/**
 * Finite, authored W1 execution fixture.  This is an instrument input and
 * evaluator-side reference table, not a model result or a learning mechanism.
 */

export type LocalSemanticBit = 0 | 1
export type LocalSemanticMode = "E0" | "E1" | "E2"
export type LocalSemanticOutputMode = Exclude<LocalSemanticMode, "E0">

export interface LocalSemanticInput {
  readonly relation: {
    readonly semanticText: string
    readonly disposition: string
    readonly uncertainty: string
    readonly exceptionRefs: readonly string[]
  }
  readonly roles: readonly {
    readonly role: "subject" | "context" | "exception"
    readonly ordinal: 0 | 1 | 2
    readonly referenceType: "LOCAL_SEMANTIC_INPUT"
  }[]
  readonly priorEvidence: readonly []
  readonly fields: {
    readonly subject: { readonly dax: LocalSemanticBit; readonly wug: LocalSemanticBit; readonly zif: LocalSemanticBit }
    readonly context: { readonly pel: LocalSemanticBit }
    readonly exception: { readonly nub: LocalSemanticBit }
  }
}

export interface LocalSemanticCase {
  readonly caseId: string
  readonly familyIndex: 0 | 1 | 2 | 3
  readonly familyName: "xor" | "role_selection" | "conjunction" | "conditional"
  readonly input: LocalSemanticInput
  /** Evaluator-only: never serialize this member into the model-visible input. */
  readonly expected: {
    readonly base: LocalSemanticBit
    readonly context_flip: LocalSemanticBit
    readonly exception_flip: LocalSemanticBit
    readonly answer: LocalSemanticBit
  }
}

export interface LocalSemanticScheduleEntry {
  readonly ordinal: number
  readonly caseId: string
  readonly mode: LocalSemanticMode
}

export type LocalSemanticOutputRefusalReason =
  | "INVALID_JSON"
  | "DUPLICATE_KEY"
  | "NOT_OBJECT"
  | "UNEXPECTED_KEYS"
  | "INVALID_ANSWER"
  | "INVALID_INTERMEDIATE"

export type LocalSemanticOutputParse =
  | { readonly valid: true; readonly output: Readonly<{ readonly answer: LocalSemanticBit; readonly base?: LocalSemanticBit; readonly context_flip?: LocalSemanticBit; readonly exception_flip?: LocalSemanticBit }> }
  | { readonly valid: false; readonly refusal: Readonly<{ readonly reason: LocalSemanticOutputRefusalReason }> }

const frozen = <T>(value: T): Readonly<T> => Object.freeze(value)
const bit = (value: unknown): value is LocalSemanticBit => value === 0 || value === 1
const refusal = (reason: LocalSemanticOutputRefusalReason): LocalSemanticOutputParse => frozen({ valid: false, refusal: frozen({ reason }) })

const familyDefinitions = frozen([
  frozen({ name: "xor" as const, base: "The initial bit is 1 exactly when subject fields dax and wug differ." }),
  frozen({ name: "role_selection" as const, base: "The initial bit is the value of subject field zif; dax and wug do not determine it." }),
  frozen({ name: "conjunction" as const, base: "The initial bit is 1 exactly when both subject fields dax and wug are 1." }),
  frozen({ name: "conditional" as const, base: "If subject field dax is 1, the initial bit is wug; otherwise it is zif." })
] as const)

const relationText = (familyIndex: 0 | 1 | 2 | 3): string => `${familyDefinitions[familyIndex].base} Context flag pel equal to 1 flips that bit, while pel equal to 0 leaves it unchanged. Finally, exception flag nub equal to 1 flips the bit; nub equal to 0 leaves it unchanged.`

const roles = frozen([
  frozen({ role: "subject" as const, ordinal: 0 as const, referenceType: "LOCAL_SEMANTIC_INPUT" as const }),
  frozen({ role: "context" as const, ordinal: 1 as const, referenceType: "LOCAL_SEMANTIC_INPUT" as const }),
  frozen({ role: "exception" as const, ordinal: 2 as const, referenceType: "LOCAL_SEMANTIC_INPUT" as const })
])
const priorEvidence: readonly [] = frozen([]) as readonly []

const base = (family: 0 | 1 | 2 | 3, dax: LocalSemanticBit, wug: LocalSemanticBit, zif: LocalSemanticBit): LocalSemanticBit => {
  if (family === 0) return (dax ^ wug) as LocalSemanticBit
  if (family === 1) return zif
  if (family === 2) return (dax & wug) as LocalSemanticBit
  return dax === 1 ? wug : zif
}

const caseFor = (familyIndex: 0 | 1 | 2 | 3, index: number): LocalSemanticCase => {
  const dax = (index & 1) as LocalSemanticBit
  const wug = ((index >> 1) & 1) as LocalSemanticBit
  const zif = ((index >> 2) & 1) as LocalSemanticBit
  const pel = ((index >> 3) & 1) as LocalSemanticBit
  const nub = ((index >> 4) & 1) as LocalSemanticBit
  const initial = base(familyIndex, dax, wug, zif)
  const expected = frozen({ base: initial, context_flip: pel, exception_flip: nub, answer: (initial ^ pel ^ nub) as LocalSemanticBit })
  const input = frozen({
    relation: frozen({ semanticText: relationText(familyIndex), disposition: "predict-binary-output-under-context", uncertainty: "authored-finite-fixture-reference-not-world-truth", exceptionRefs: frozen([]) }),
    roles,
    priorEvidence,
    fields: frozen({ subject: frozen({ dax, wug, zif }), context: frozen({ pel }), exception: frozen({ nub }) })
  })
  return frozen({ caseId: `local-semantic-f${familyIndex}-i${String(index).padStart(2, "0")}`, familyIndex, familyName: familyDefinitions[familyIndex].name, input, expected })
}

export const localSemanticCases: readonly LocalSemanticCase[] = frozen(
  familyDefinitions.flatMap((_, family) => Array.from({ length: 32 }, (_, index) => caseFor(family as 0 | 1 | 2 | 3, index)))
)

export const localSemanticModes: readonly LocalSemanticMode[] = frozen(["E0", "E1", "E2"])

export const localSemanticSchedule: readonly LocalSemanticScheduleEntry[] = frozen(
  localSemanticCases.flatMap((entry, caseIndex) => localSemanticModes.map((_, modeIndex) => frozen({ ordinal: caseIndex * localSemanticModes.length + modeIndex, caseId: entry.caseId, mode: localSemanticModes[(caseIndex + modeIndex) % localSemanticModes.length]! })))
)

export const localSemanticModeInstructions: Readonly<Record<LocalSemanticMode, string>> = frozen({
  E0: "Return only one token: 0 or 1.",
  E1: "Use the supplied relation, ordered roles, fields, and empty prior evidence. Return exactly one JSON object with the sole key answer and an integer value 0 or 1.",
  E2: "Use the supplied relation, ordered roles, fields, and empty prior evidence. Return exactly one JSON object with integer values 0 or 1: base is the initial bit before flips, context_flip is the applied pel flag value, exception_flip is the applied nub flag value, and answer is the final bit after both flips."
})

export const localSemanticModeSchemas: Readonly<Record<LocalSemanticOutputMode, Readonly<Record<string, unknown>>>> = frozen({
  E1: frozen({ type: "object", additionalProperties: false, required: frozen(["answer"]), properties: frozen({ answer: frozen({ type: "integer", enum: frozen([0, 1]) }) }) }),
  E2: frozen({ type: "object", additionalProperties: false, required: frozen(["base", "context_flip", "exception_flip", "answer"]), properties: frozen({ base: frozen({ type: "integer", enum: frozen([0, 1]) }), context_flip: frozen({ type: "integer", enum: frozen([0, 1]) }), exception_flip: frozen({ type: "integer", enum: frozen([0, 1]) }), answer: frozen({ type: "integer", enum: frozen([0, 1]) }) }) })
})

/**
 * JSON.parse deliberately applies last-key-wins. Model output contracts cannot:
 * the raw top-level spelling must therefore be scanned before validation.
 */
const topLevelObjectKeys = (text: string): readonly string[] | null => {
  let cursor = 0
  const space = (): void => { while (/\s/u.test(text[cursor] ?? "")) cursor += 1 }
  const string = (): string | null => {
    if (text[cursor] !== "\"") return null
    const start = cursor
    cursor += 1
    let escaped = false
    while (cursor < text.length) {
      const character = text[cursor++]!
      if (escaped) escaped = false
      else if (character === "\\") escaped = true
      else if (character === "\"") {
        try {
          const decoded: unknown = JSON.parse(text.slice(start, cursor))
          return typeof decoded === "string" ? decoded : null
        } catch { return null }
      }
    }
    return null
  }
  const valueEnd = (): "comma" | "close" | null => {
    let depth = 0
    let quoted = false
    let escaped = false
    while (cursor < text.length) {
      const character = text[cursor++]!
      if (quoted) {
        if (escaped) escaped = false
        else if (character === "\\") escaped = true
        else if (character === "\"") quoted = false
        continue
      }
      if (character === "\"") { quoted = true; continue }
      if (character === "{" || character === "[") { depth += 1; continue }
      if (character === "}" || character === "]") {
        if (depth === 0) return character === "}" ? "close" : null
        depth -= 1
        continue
      }
      if (character === "," && depth === 0) return "comma"
    }
    return null
  }
  space()
  if (text[cursor++] !== "{") return null
  const keys: string[] = []
  space()
  if (text[cursor] === "}") {
    cursor += 1
    space()
    return cursor === text.length ? frozen(keys) : null
  }
  while (cursor < text.length) {
    space()
    const key = string()
    if (key === null) return null
    keys.push(key)
    space()
    if (text[cursor++] !== ":") return null
    const ending = valueEnd()
    if (ending === null) return null
    if (ending === "close") {
      space()
      return cursor === text.length ? frozen(keys) : null
    }
    space()
  }
  return null
}

/** Strictly parse model text.  A refusal stays a refusal; callers retain it in their denominator. */
export const parseLocalSemanticOutput = (mode: LocalSemanticOutputMode, text: string): LocalSemanticOutputParse => {
  let parsed: unknown
  try { parsed = JSON.parse(text) } catch { return refusal("INVALID_JSON") }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return refusal("NOT_OBJECT")
  const record = parsed as Record<string, unknown>
  const rawKeys = topLevelObjectKeys(text)
  if (rawKeys === null) return refusal("INVALID_JSON")
  if (new Set(rawKeys).size !== rawKeys.length) return refusal("DUPLICATE_KEY")
  const keys = Object.keys(record).sort()
  const expectedKeys = mode === "E1" ? ["answer"] : ["answer", "base", "context_flip", "exception_flip"]
  if (keys.length !== expectedKeys.length || keys.some((key, index) => key !== expectedKeys[index])) return refusal("UNEXPECTED_KEYS")
  if (!bit(record["answer"])) return refusal("INVALID_ANSWER")
  if (mode === "E1") return frozen({ valid: true, output: frozen({ answer: record["answer"] }) })
  if (!bit(record["base"]) || !bit(record["context_flip"]) || !bit(record["exception_flip"])) return refusal("INVALID_INTERMEDIATE")
  return frozen({ valid: true, output: frozen({ answer: record["answer"], base: record["base"], context_flip: record["context_flip"], exception_flip: record["exception_flip"] }) })
}
