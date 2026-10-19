/** Event-independent finite relation compilation. No answer oracle or source mutation. */
import { Either } from "effect"
import { createHash } from "node:crypto"
import { decodeFiniteProgram, finiteProgramAccepts } from "./semantic-context-finite-domain.js"
import { contextError, contextHash } from "./semantic-context-domain.js"
import type { SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"

export const compileFiniteRuleTable = (frame: SemanticReadFrame) => Either.gen(function* () {
  const program = yield* decodeFiniteProgram(frame.relation.semantic.semanticText).pipe(
    Either.mapLeft(e => contextError("FINITE_PRESENTATION_UNKNOWN", e.detail)))
  if (program.variables.some(v => frame.roles[v.roleOrdinal] === undefined)) return yield* Either.left(contextError("FINITE_PRESENTATION_ROLE", "Every variable needs its exact role occurrence"))
  const rows = program.variables.reduce<readonly (readonly string[])[]>((acc, v) => acc.flatMap(row => v.values.map(value => [...row, value])), [[]])
  const allowedRows = rows.filter(row => finiteProgramAccepts(program, row))
  const body = {
    contract: "hswm-finite-rule-table/v1" as const,
    sourceSemanticTextSha256: createHash("sha256").update(frame.relation.semantic.semanticText).digest("hex"),
    relationKey: frame.relation.key, owner: frame.relation.owner, exceptionRefs: frame.relation.semantic.exceptionRefs,
    variables: program.variables.map(v => ({ ...v, participant: frame.roles[v.roleOrdinal] })),
    clauses: program.clauses, completeAssignments: rows.length, allowedRows,
    interpretation: "COMPLETE_CONJUNCTION_EXTENSION_NOT_EVENT_ANSWER_NOT_NATURAL_LANGUAGE_ABSTRACTION" as const
  }
  // JSON strings retain escaping and column identity; empty extension remains explicitly impossible.
  const text = [
    `RULE ${JSON.stringify(frame.relation.key.atomUid)}: all its clauses hold exactly for the following rows.`,
    `Columns, in order: ${JSON.stringify(program.variables.map(v => v.id))}.`,
    ...program.variables.map(v => `Column ${JSON.stringify(v.id)} uses role occurrence ${v.roleOrdinal}; domain ${JSON.stringify(v.values)}.`),
    "BEGIN ALLOWED ROWS", ...allowedRows.map(row => JSON.stringify(row)), "END ALLOWED ROWS",
    "No other row is allowed. All supplied RULE tables must hold together. This table is independent of EVENT."
  ].join("\n")
  if (new TextEncoder().encode(text).byteLength > 65536) return yield* Either.left(contextError("FINITE_PRESENTATION_LIMIT", "Complete readable table exceeds 65536 bytes; no partial table"))
  return { ...body, tableSha256: contextHash(body), text }
})
