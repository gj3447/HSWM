/** Whole-bundle finite preservation, with exact role identity. No NLP abstraction or graph writes. */
import { Either } from "effect"
import type { SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { contextHash, contextError, contextByteLength, decodeContextSpec, type ContextSpec } from "./semantic-context-domain.js"
import { decodeFiniteProgram, finiteProgramAccepts } from "./semantic-context-finite-domain.js"

const fail = (detail: string) => Either.left(contextError("TOPOLOGY_INVALID", detail))
const same = (a: unknown, b: unknown) => contextHash(a) === contextHash(b)
const roots = (spec: ContextSpec, id: string) => [...new Set([...spec.mandatoryRelationUids, ...(spec.candidates.find(c => c.id === id)?.relationUids ?? [])])]
const roleId = (frame: SemanticReadFrame, ordinal: number) => contextHash({ ordinal, role: frame.roles[ordinal] })

/** Retirement is local candidate incidence only: canonical source atoms and their revisions remain available. */
export const reviewContextRetirement = (before: ContextSpec, rawAfter: unknown, frames: readonly SemanticReadFrame[]) => Either.gen(function* () {
  const after = yield* decodeContextSpec(rawAfter)
  if (!same({ ...before, candidates: null }, { ...after, candidates: null }) ||
    !same(before.candidates.map(c => ({ ...c, relationUids: null })), after.candidates.map(c => ({ ...c, relationUids: null })))) return yield* fail("Only candidate incidence may change; mandatory rules, task, budgets and candidate identity stay fixed")
  if (after.candidates.some(c => c.relationUids.some(uid => !before.candidates.find(old => old.id === c.id)?.relationUids.includes(uid)))) return yield* fail("Retirement cannot introduce or reassign sources")
  const expected = [...new Set([...before.mandatoryRelationUids, ...before.candidates.flatMap(c => c.relationUids)])].sort()
  if (!same(frames.map(f => f.relation.key.atomUid).sort(), expected) || new Set(frames.map(f => f.stateRevision)).size !== 1 || frames.some(f => f.event !== before.event)) return yield* fail("Exact complete source frame set at one task revision is required")
  const rows = []
  for (const candidate of before.candidates) {
    const oldRoots = roots(before, candidate.id), newRoots = roots(after, candidate.id)
    const source = frames.filter(f => oldRoots.includes(f.relation.key.atomUid)), retained = source.filter(f => newRoots.includes(f.relation.key.atomUid))
    const removed = oldRoots.filter(uid => !newRoots.includes(uid))
    if (removed.length === 0) { rows.push({ candidateId: candidate.id, status: "UNCHANGED" as const, removed, assignments: 0, witness: null }); continue }
    const afterRoles = new Set(retained.flatMap(f => f.roles.map((_, i) => roleId(f, i))))
    if (source.some(f => f.roles.some((_, i) => !afterRoles.has(roleId(f, i))))) return yield* fail("Retirement loses an exact participant/owner/content/role occurrence")
    const exceptions = new Set(retained.flatMap(f => f.relation.semantic.exceptionRefs))
    if (source.some(f => f.relation.semantic.exceptionRefs.some(ref => !exceptions.has(ref)))) return yield* fail("Retirement loses a declared exception reference")
    // Unsupported natural language is UNKNOWN, never silently interpreted as a tautology.
    const decoded = yield* Either.all(source.map(f => decodeFiniteProgram(f.relation.semantic.semanticText).pipe(Either.map(program => ({ frame: f, program })),
      Either.mapLeft(e => contextError("TOPOLOGY_UNKNOWN", `Explicit finite meaning unavailable: ${e.code}`)))))
    const columns: Array<{ id: string; values: readonly string[] }> = []
    for (const { frame, program } of decoded) {
      for (const v of program.variables) {
        if (!frame.roles[v.roleOrdinal]) return yield* fail("Finite variable has no exact role")
        const id = roleId(frame, v.roleOrdinal), prior = columns.find(c => c.id === id)
        if (prior && !same(prior.values, v.values)) return yield* fail("Same role has conflicting finite domains")
        if (!prior) columns.push({ id, values: v.values })
      }
    }
    if (columns.length > 16 || columns.reduce((n, c) => n * c.values.length, 1) > 4096) return yield* Either.left(contextError("TOPOLOGY_UNKNOWN", "Whole bundle exceeds 4096 assignments or 16 variables"))
    const assignments = columns.reduce<readonly (readonly string[])[]>((xs, c) => xs.flatMap(x => c.values.map(v => [...x, v])), [[]])
    const evaluate = (uids: readonly string[], row: readonly string[]) => decoded.filter(d => uids.includes(d.frame.relation.key.atomUid)).every(({ frame, program }) =>
      finiteProgramAccepts(program, program.variables.map(v => row[columns.findIndex(c => c.id === roleId(frame, v.roleOrdinal))] ?? "")))
    if (!assignments.some(row => evaluate(oldRoots, row))) return yield* fail("Inconsistent base cannot justify retirement")
    const witness = assignments.find(row => evaluate(oldRoots, row) !== evaluate(newRoots, row))
    const uses = (uids: readonly string[]) => new Set(decoded.filter(d => uids.includes(d.frame.relation.key.atomUid)).flatMap(({ frame, program }) =>
      program.variables.filter(v => frame.roles[v.roleOrdinal]?.role === "exception" && program.expressions.some(e => e.op === "is" && e.variable === v.id)).map(v => roleId(frame, v.roleOrdinal))))
    const afterUses = uses(newRoots)
    if ([...uses(oldRoots)].some(id => !afterUses.has(id))) return yield* fail("Finite exception dependency disappears")
    rows.push({ candidateId: candidate.id, status: witness ? "CHANGED" as const : "PRESERVED" as const, removed, assignments: assignments.length,
      witness: witness ? Object.fromEntries(columns.map((c, i) => [c.id, witness[i]])) : null })
  }
  const changed = rows.some(r => r.removed.length > 0)
  const beforeBytes = before.candidates.map(c => contextByteLength(frames.filter(f => roots(before, c.id).includes(f.relation.key.atomUid))))
  const afterBytes = after.candidates.map(c => contextByteLength(frames.filter(f => roots(after, c.id).includes(f.relation.key.atomUid))))
  return { contract: "hswm-context-retirement-review/v1" as const, beforeSha256: contextHash(before), afterSha256: contextHash(after),
    sourceFramesSha256: contextHash(frames), status: rows.some(r => r.status === "CHANGED") ? "CHANGED" as const : changed ? "PRESERVED" as const : "NO_CHANGE" as const,
    rows, beforeFrameBytes: beforeBytes, afterFrameBytes: afterBytes,
    claimCeiling: "DECLARED_FINITE_CONJUNCTION_AND_ROLE_COVERAGE_NOT_NATURAL_LANGUAGE_OR_FUTURE_LEARNING_EQUIVALENCE" as const }
})
