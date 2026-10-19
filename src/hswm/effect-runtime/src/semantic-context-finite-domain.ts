/** Finite semantic diagnostics transferred from HSWM_LIKENESS. No state writes or inferred NLP alignment. */
import { createHash } from "node:crypto"
import { Data, Either, Schema } from "effect"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { decodeSemanticFrameRepresentation, encodeSemanticFrameRepresentation } from "./semantic-frame-representation.js"
import type { SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"

export class FiniteSemanticError extends Data.TaggedError("FiniteSemanticError")<{
  readonly code: string
  readonly detail: string
}> {}
const fail = (code: string, detail: string) => Either.left(new FiniteSemanticError({ code, detail }))
const id = Schema.String.pipe(Schema.pattern(/^[A-Za-z][A-Za-z0-9_-]{0,63}$/))
const index = Schema.Number.pipe(Schema.int(), Schema.between(0, 127))
const value = Schema.String.pipe(Schema.minLength(1), Schema.maxLength(128))
const values = Schema.Array(value).pipe(Schema.minItems(1), Schema.maxItems(16), Schema.filter(xs => new Set(xs).size === xs.length))
const Variable = Schema.Struct({ id, roleOrdinal: index, values })
const Expression = Schema.Union(
  Schema.Struct({ op: Schema.Literal("is"), variable: id, value }),
  Schema.Struct({ op: Schema.Literal("not"), arg: index }),
  Schema.Struct({ op: Schema.Literal("and", "or"), left: index, right: index }),
  Schema.Struct({ op: Schema.Literal("unless"), when: index, exception: index, require: index })
)
export const FiniteProgramSchema = Schema.Struct({
  contract: Schema.Literal("hswm-finite-semantic-program/v1"),
  variables: Schema.Array(Variable).pipe(Schema.minItems(1), Schema.maxItems(16)),
  expressions: Schema.Array(Expression).pipe(Schema.minItems(1), Schema.maxItems(128)),
  clauses: Schema.Array(Schema.Struct({ id, expression: index })).pipe(Schema.minItems(1), Schema.maxItems(32))
})
export type FiniteProgram = typeof FiniteProgramSchema.Type
type Expr = typeof Expression.Type
const refs = (e: Expr): readonly number[] => e.op === "is" ? [] : e.op === "not" ? [e.arg] : e.op === "unless" ? [e.when, e.exception, e.require] : [e.left, e.right]
const hash = (s: string | Uint8Array) => createHash("sha256").update(s).digest("hex")
const equalJson = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const unique = (xs: readonly unknown[]) => new Set(xs).size === xs.length
const parse = (text: string) => Either.gen(function* () {
  if (text.length > 8192) return yield* fail("PROGRAM_LIMIT", "Semantic program exceeds 8192 UTF-16 units")
  const raw = yield* decodeGeneralJsonBytes(new TextEncoder().encode(text)).pipe(Either.mapLeft(e => new FiniteSemanticError({ code: "PROGRAM_JSON", detail: e.detail })))
  const program = yield* Schema.decodeUnknownEither(FiniteProgramSchema)(raw, { onExcessProperty: "error" }).pipe(
    Either.mapLeft(() => new FiniteSemanticError({ code: "PROGRAM_INVALID", detail: "Expected explicit bounded variables, ordered expressions and clauses" })))
  if (!unique(program.variables.map(v => v.id)) || !unique(program.variables.map(v => v.roleOrdinal)) || !unique(program.clauses.map(c => c.id))) return yield* fail("IDENTITY_DUPLICATE", "Variables, role occurrences and clause IDs must be unique")
  if (program.variables.some(v => v.values.some(s => /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(s)))) return yield* fail("INVALID_UNICODE", "Domains must contain well-formed Unicode")
  const sizes = program.variables.reduce((n, v) => n * v.values.length, 1)
  if (sizes > 4096) return yield* fail("ASSIGNMENT_LIMIT", "Complete domain product exceeds 4096 assignments; no truncation")
  for (const [i, e] of program.expressions.entries()) {
    if (refs(e).some(r => r >= i)) return yield* fail("EXPRESSION_ORDER", "Expression references must point strictly backward")
    if (e.op === "is" && !program.variables.find(v => v.id === e.variable)?.values.includes(e.value)) return yield* fail("DOMAIN_MISMATCH", "Unknown variable or value")
  }
  if (program.clauses.some(c => c.expression >= program.expressions.length)) return yield* fail("CLAUSE_REFERENCE", "Clause references an absent expression")
  // Every expression contributes to a declared clause: dead nodes cannot conceal lost exceptions.
  const used = new Set(program.clauses.map(c => c.expression))
  for (let i = program.expressions.length - 1; i >= 0; i--) {
    const e = program.expressions[i]
    if (e !== undefined && used.has(i)) refs(e).forEach(r => used.add(r))
  }
  if (used.size !== program.expressions.length) return yield* fail("UNUSED_EXPRESSION", "Unreachable expression nodes are not permitted")
  return program
})

const enumerate = (program: FiniteProgram): readonly (readonly string[])[] => program.variables.reduce<readonly (readonly string[])[]>(
  (rows, v) => rows.flatMap(row => v.values.map(s => [...row, s])), [[]])
const evaluate = (program: FiniteProgram, row: readonly string[]): readonly boolean[] => {
  const computed: boolean[] = []
  for (const e of program.expressions) {
    computed.push(e.op === "is" ? row[program.variables.findIndex(v => v.id === e.variable)] === e.value :
      e.op === "not" ? !computed[e.arg] : e.op === "unless" ? !computed[e.when] || Boolean(computed[e.exception] || computed[e.require]) :
        e.op === "and" ? Boolean(computed[e.left] && computed[e.right]) : Boolean(computed[e.left] || computed[e.right]))
  }
  return program.clauses.map(c => computed[c.expression] === true)
}
const allowed = (program: FiniteProgram, rows: readonly (readonly string[])[]) => rows.filter(row => evaluate(program, row).every(Boolean))
/** Shared finite evaluator; callers must decode the explicit program before comparison. */
export const decodeFiniteProgram = parse
export const finiteProgramAccepts = (program: FiniteProgram, row: readonly string[]) =>
  row.length === program.variables.length && program.variables.every((v, i) => v.values.includes(row[i] ?? "")) && evaluate(program, row).every(Boolean)
const record = (program: FiniteProgram, row: readonly string[] | undefined) => row === undefined ? null : Object.fromEntries(program.variables.map((v, i) => [v.id, row[i]]))
const bind = (frame: SemanticReadFrame, program: FiniteProgram) => Either.gen(function* () {
  if (program.variables.some(v => frame.roles[v.roleOrdinal] === undefined)) return yield* fail("ROLE_MISSING", "Every variable must resolve to one exact frame role occurrence")
  return program.variables.map(v => ({ variable: v.id, roleOrdinal: v.roleOrdinal, participant: frame.roles[v.roleOrdinal] }))
})
export const FiniteReviewOptionsSchema = Schema.Struct({
  proposedSemanticText: Schema.optional(Schema.String.pipe(Schema.maxLength(8192))),
  factorBags: Schema.optional(Schema.Array(Schema.Array(id).pipe(Schema.minItems(1), Schema.maxItems(16))).pipe(Schema.minItems(1), Schema.maxItems(8)))
})
const Request = Schema.Struct({
  contract: Schema.Literal("hswm-finite-semantic-review/v1"),
  representation: Schema.Struct({ kind: Schema.Literal("direct_json", "incidence", "role_table"), payload: Schema.Unknown }),
  ...FiniteReviewOptionsSchema.fields
})

/** Complete enumeration of a declared finite interpretation, not natural-language meaning or learned W. */
export const reviewFiniteSemanticRequest = (raw: unknown) => Either.gen(function* () {
  const request = yield* Schema.decodeUnknownEither(Request)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => new FiniteSemanticError({ code: "REQUEST_INVALID", detail: "Expected a source-bound semantic representation and explicit finite review" })))
  const frame = yield* decodeSemanticFrameRepresentation(request.representation).pipe(Either.mapLeft(e => new FiniteSemanticError(e)))
  const program = yield* parse(frame.relation.semantic.semanticText)
  const bindings = yield* bind(frame, program)
  const source = yield* canonicalJsonBytes(frame).pipe(Either.mapLeft(e => new FiniteSemanticError({ code: "FRAME_CANONICAL", detail: e.detail })))
  const rows = enumerate(program), clauseTruths = rows.map(row => evaluate(program, row))
  const accepted = rows.filter((_, i) => clauseTruths[i]?.every(Boolean)), beforeSet = new Set(accepted.map(row => JSON.stringify(row)))
  const clauseDiagnostics = program.clauses.map((clause, index) => {
    const witness = rows[clauseTruths.findIndex(truths => truths[index] === false && truths.every((truth, i) => i === index || truth))]
    return { clauseId: clause.id, status: accepted.length === 0 ? "INCONSISTENT_BASE_REVIEW_REQUIRED" : witness === undefined ? "REDUNDANT_WITHIN_DECLARED_DOMAIN" : "CONTRIBUTES_CONSTRAINT", removalWitness: record(program, witness) }
  })
  let revision = null
  if (request.proposedSemanticText !== undefined) {
    const next = yield* parse(request.proposedSemanticText)
    if (!equalJson(program.variables, next.variables)) return yield* fail("ALIGNMENT_CHANGED", "Comparison requires identical variables, domains and exact role occurrences")
    const after = allowed(next, rows), afterSet = new Set(after.map(row => JSON.stringify(row)))
    const removed = accepted.filter(row => !afterSet.has(JSON.stringify(row))), added = after.filter(row => !beforeSet.has(JSON.stringify(row)))
    const exceptionVariables = program.variables.filter(v => frame.roles[v.roleOrdinal]?.role === "exception").map(v => v.id)
    const usedBefore = program.expressions.flatMap(e => e.op === "is" ? [e.variable] : [])
    const usedAfter = next.expressions.flatMap(e => e.op === "is" ? [e.variable] : [])
    revision = {
      proposedTextSha256: hash(request.proposedSemanticText), allowedAfter: after.length,
      classification: added.length === 0 ? removed.length === 0 ? "EQUIVALENT" : "STRENGTHENED" : removed.length === 0 ? "WEAKENED" : "INCOMPARABLE",
      addedCount: added.length, removedCount: removed.length, addedWitness: record(program, added[0]), removedWitness: record(program, removed[0]),
      lostExceptionReferences: exceptionVariables.filter(v => usedBefore.includes(v) && !usedAfter.includes(v)),
      interpretation: "SET_INCLUSION_OF_ALLOWED_ASSIGNMENTS_NOT_CONNECTION_STRENGTH_OR_UTILITY"
    }
  }
  let factorization = null
  if (request.factorBags !== undefined) {
    const bags = request.factorBags
    const ids = program.variables.map(v => v.id)
    if (!unique(bags.map(b => JSON.stringify([...b].sort()))) || bags.some(b => !unique(b) || b.some(v => !ids.includes(v))) || ids.some(v => !bags.some(b => b.includes(v)))) return yield* fail("FACTOR_SCOPE", "Distinct bags must cover all variables without unknown or repeated columns")
    const columns = bags.map(b => b.map(v => ids.indexOf(v)))
    const project = (row: readonly string[], indices: readonly number[]) => JSON.stringify(indices.map(i => row[i]))
    const projections = columns.map(indices => new Set(accepted.map(row => project(row, indices))))
    const joined = rows.filter(row => columns.every((indices, i) => projections[i]?.has(project(row, indices))))
    const spurious = joined.filter(row => !beforeSet.has(JSON.stringify(row)))
    factorization = { bags, status: accepted.length === 0 ? "INCONSISTENT_BASE_REVIEW_REQUIRED" : spurious.length === 0 ? "LOSSLESS_WITHIN_DECLARED_DOMAIN" : "LOSSY_ADDS_INTERPRETATIONS", projectionRows: projections.map(p => p.size), joinedRows: joined.length, spuriousCount: spurious.length, spuriousWitness: record(program, spurious[0]), changesApplied: false }
  }
  return {
    contract: "hswm-finite-semantic-review-result/v1" as const,
    source: { frameSha256: frame.frameSha256, canonicalFrameSha256: hash(source), relationKey: frame.relation.key, owner: frame.relation.owner, stateRevision: frame.stateRevision, semanticTextSha256: hash(frame.relation.semantic.semanticText), exceptionRefs: frame.relation.semantic.exceptionRefs, bindings },
    interpretation: "EXPLICIT_FINITE_PROGRAM_NOT_AUTOMATIC_NATURAL_LANGUAGE_ABSTRACTION" as const,
    completeAssignments: rows.length, allowedBefore: accepted.length, clauseDiagnostics, revision, factorization,
    canonicalWrite: false, utility: null, claimCeiling: "FINITE_SEMANTIC_DIAGNOSTIC_NOT_OWNER_ADMISSION_NOT_LEARNING_EFFICACY" as const
  }
})

/** Native callers supply the complete read frame; the CLI accepts the same exact representation. */
export const reviewFiniteSemanticFrame = (frame: SemanticReadFrame, options: typeof FiniteReviewOptionsSchema.Type = {}) =>
  Either.flatMap(encodeSemanticFrameRepresentation(frame, "incidence"), representation => reviewFiniteSemanticRequest({ contract: "hswm-finite-semantic-review/v1", representation: { kind: representation.kind, payload: representation.payload }, ...options }))
