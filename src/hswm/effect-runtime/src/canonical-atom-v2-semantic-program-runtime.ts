/** Effect shell for the bounded semantic-program data contract. */
import { Effect, Either } from "effect"

import type { AdaptiveHttpClientShape } from "./adaptive-executor.js"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { executeLlmSemanticRelation, LlmSemanticRuntimeError, type LlmSemanticCell, type SemanticTrace } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { HSWM_SEMANTIC_PROGRAM_KIND, HSWM_SEMANTIC_PROGRAM_MAX_BYTES, HSWM_SEMANTIC_PROGRAM_MAX_STEPS, HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE, SemanticProgramError, resolveSemanticProgram, type ResolvedSemanticProgram } from "./canonical-atom-v2-semantic-program.js"

export interface SemanticProgramKernelRegistry {
  readonly [kernelId: string]: LlmSemanticCell | undefined
}

export interface RunSemanticProgramInput {
  readonly programUid: string
  readonly kernels: SemanticProgramKernelRegistry
  readonly http: AdaptiveHttpClientShape
  /** Host policy; graph content cannot request more work than this. */
  readonly maximumSteps: number
}

export interface SemanticProgramExecution {
  readonly programKey: CanonicalAtomV2Key
  readonly programContent: { readonly mediaType: string; readonly byteLength: number; readonly sha256: string }
  readonly stateRevision: number
  readonly traces: ReadonlyArray<Readonly<{ readonly role: string; readonly target: CanonicalAtomV2Key; readonly trace: SemanticTrace }>>
  readonly completion: "ALL_STEPS_EXECUTED_WITHOUT_CANONICAL_STATE_DRIFT"
}

const sameKey = (left: CanonicalAtomV2Key, right: CanonicalAtomV2Key): boolean =>
  canonicalAtomV2KeyId(left) === canonicalAtomV2KeyId(right)
const failure = (code: SemanticProgramError["code"], detail: string) => new SemanticProgramError({ code, detail })

const load = (runtime: CanonicalAtomV2DurableRuntime["Type"], programUid: string) => Effect.gen(function* () {
  const state = yield* runtime.snapshot
  const candidates = state.canonical.atoms.filter(atom => atom.key.atomUid === programUid)
  if (candidates.length === 0) return yield* Effect.fail(failure("PROGRAM_MISSING", `program is absent: ${programUid}`))
  const lines = new Set(candidates.map(atom => JSON.stringify([atom.key.schemaVersion, atom.key.lineageId])))
  if (lines.size > 1) return yield* Effect.fail(failure("AMBIGUOUS_PROGRAM", `atom UID is ambiguous: ${programUid}`))
  const program = candidates.reduce((prior, atom) => atom.key.revisionId > prior.key.revisionId ? atom : prior)
  if (program.kind !== HSWM_SEMANTIC_PROGRAM_KIND || program.content.mediaType !== HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE ||
    program.content.byteLength < 1 || program.content.byteLength > HSWM_SEMANTIC_PROGRAM_MAX_BYTES || !/^[0-9a-f]{64}$/.test(program.content.sha256)) {
    return yield* Effect.fail(failure("CONTENT_INVALID", "program kind or descriptor is outside the bounded contract"))
  }
  const bytes = yield* runtime.readContent(program.content)
  const resolved = resolveSemanticProgram(state, programUid, bytes)
  if (resolved._tag === "Left") return yield* Effect.fail(resolved.left)
  return resolved.right
})

const stable = (runtime: CanonicalAtomV2DurableRuntime["Type"], expected: ResolvedSemanticProgram) =>
  load(runtime, expected.program.key.atomUid).pipe(Effect.flatMap(actual =>
    actual.stateRevision === expected.stateRevision && sameKey(actual.program.key, expected.program.key) &&
    actual.program.content.sha256 === expected.program.content.sha256 &&
    actual.steps.length === expected.steps.length &&
    actual.steps.every((step, index) => sameKey(step.target, expected.steps[index]!.target))
      ? Effect.succeed(actual)
      : Effect.fail(failure("PROGRAM_NOT_CURRENT", "canonical program or a pinned target changed during execution"))))

const snapshotCell = (cell: LlmSemanticCell): LlmSemanticCell => Object.freeze({
  base_url: cell.base_url,
  model: cell.model,
  ...(cell.api_key_env === undefined ? {} : { api_key_env: cell.api_key_env }),
  max_tokens: cell.max_tokens
})

/**
 * Executes only fixed prediction opcodes. It neither learns nor admits graph
 * state; a caller retains those authorities. State is checked before each
 * dispatch and once after the final response.
 */
export const runSemanticProgram = (input: RunSemanticProgramInput) => {
  const captured = Object.freeze({
    programUid: input.programUid,
    maximumSteps: input.maximumSteps,
    http: input.http,
    kernels: Object.freeze(Object.fromEntries(Object.entries(input.kernels).map(([id, cell]) => [id, cell === undefined ? undefined : snapshotCell(cell)]))) as SemanticProgramKernelRegistry
  })
  return Effect.gen(function* () {
  if (!Number.isSafeInteger(captured.maximumSteps) || captured.maximumSteps < 1 || captured.maximumSteps > HSWM_SEMANTIC_PROGRAM_MAX_STEPS) return yield* Effect.fail(failure("CONTENT_INVALID", "host maximumSteps is outside the bounded range"))
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const resolved = yield* load(runtime, captured.programUid)
  if (resolved.steps.length > captured.maximumSteps) return yield* Effect.fail(failure("CONTENT_INVALID", "program exceeds host execution budget"))
  // The graph names a kernel; it never supplies a transport endpoint, secret,
  // or capability. Snapshot caller capability bindings before the first yield.
  const boundSteps = resolved.steps.map(step => {
    const cell = Object.hasOwn(captured.kernels, step.kernelId) ? captured.kernels[step.kernelId] : undefined
    return cell === undefined ? null : Object.freeze({ step, cell: snapshotCell(cell) })
  })
  if (boundSteps.some(binding => binding === null)) return yield* Effect.fail(failure("CONTENT_INVALID", "caller registry lacks one declared kernel"))
  const traces: Array<Readonly<{ readonly role: string; readonly target: CanonicalAtomV2Key; readonly trace: SemanticTrace }>> = []
  for (const binding of boundSteps as ReadonlyArray<{ readonly step: ResolvedSemanticProgram["steps"][number]; readonly cell: LlmSemanticCell }>) {
    const { step, cell } = binding
    yield* stable(runtime, resolved)
    const trace = yield* executeLlmSemanticRelation(runtime, step.target.atomUid, step.event, cell, captured.http, frame => {
      if (sameKey(frame.relation.key, step.target) && frame.stateRevision === resolved.stateRevision) return Either.right(undefined)
      return Either.left(new LlmSemanticRuntimeError({ code: "FRAME_STALE", detail: `target changed before dispatch: ${step.role}` }))
    })
    traces.push(Object.freeze({ role: step.role, target: Object.freeze({ ...step.target }), trace }))
  }
  yield* stable(runtime, resolved)
  return Object.freeze({
    programKey: Object.freeze({ ...resolved.program.key }),
    programContent: Object.freeze({ ...resolved.program.content }),
    stateRevision: resolved.stateRevision,
    traces: Object.freeze(traces),
    completion: "ALL_STEPS_EXECUTED_WITHOUT_CANONICAL_STATE_DRIFT" as const
  }) satisfies SemanticProgramExecution
})
}
