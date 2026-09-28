/**
 * A deliberately narrow graph-resident program description.  It is data in
 * the canonical graph, while the only executable opcode remains a fixed,
 * reviewed local semantic-prediction kernel in the host binary.
 */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"

import { parseJson } from "./adaptive-domain.js"
import type { CanonicalAtomV2DurableState } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"

export const HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE =
  "application/vnd.hswm.semantic-program-v1+json" as const
export const HSWM_SEMANTIC_PROGRAM_KIND = "semantic_program" as const
export const HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE =
  "hswm:semantic-program:target" as const
export const HSWM_SEMANTIC_PROGRAM_OPCODE = "LLM_SEMANTIC_PREDICT_V1" as const
export const HSWM_SEMANTIC_PROGRAM_MAX_STEPS = 16 as const
export const HSWM_SEMANTIC_PROGRAM_MAX_BYTES = 32_768 as const

export interface SemanticProgramStep {
  readonly role: string
  readonly event: string
  readonly kernelId: string
  readonly opcode: typeof HSWM_SEMANTIC_PROGRAM_OPCODE
}

export interface SemanticProgramContent {
  readonly contract: "hswm-semantic-program/v1"
  readonly steps: ReadonlyArray<SemanticProgramStep>
}

export interface ResolvedSemanticProgramStep extends SemanticProgramStep {
  readonly target: CanonicalAtomV2Key
}

export interface ResolvedSemanticProgram {
  readonly program: CanonicalAtomV2
  readonly stateRevision: number
  readonly content: SemanticProgramContent
  readonly steps: ReadonlyArray<ResolvedSemanticProgramStep>
}

export class SemanticProgramError extends Data.TaggedError("SemanticProgramError")<{
  readonly code:
    | "AMBIGUOUS_PROGRAM"
    | "CONTENT_INVALID"
    | "CONTENT_MISMATCH"
    | "PROGRAM_MISSING"
    | "PROGRAM_NOT_CURRENT"
    | "PROGRAM_WRONG_KIND"
    | "REFERENCE_INVALID"
    | "TARGET_MISSING"
    | "TARGET_NOT_CURRENT"
    | "TARGET_WRONG_KIND"
  readonly detail: string
}> {}

const fail = (code: SemanticProgramError["code"], detail: string): SemanticProgramError =>
  new SemanticProgramError({ code, detail })

const identifier = (value: unknown): value is string =>
  typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(value)

const eventText = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= 8_192

const sha = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")

export const decodeSemanticProgramContent = (
  bytes: Uint8Array
): Either.Either<SemanticProgramContent, SemanticProgramError> => {
  if (bytes.byteLength < 1 || bytes.byteLength > HSWM_SEMANTIC_PROGRAM_MAX_BYTES) {
    return Either.left(fail("CONTENT_INVALID", "program content is outside its byte bound"))
  }
  let raw: string
  let value: unknown
  try {
    raw = new TextDecoder("utf-8", { fatal: true }).decode(bytes)
  } catch { return Either.left(fail("CONTENT_INVALID", "program content must be UTF-8 JSON")) }
  const parsed = parseJson(raw)
  if (Either.isLeft(parsed)) return Either.left(fail("CONTENT_INVALID", "program JSON has duplicate or malformed keys"))
  value = parsed.right
  if (typeof value !== "object" || value === null || Array.isArray(value)) return Either.left(fail("CONTENT_INVALID", "program must be an object"))
  const record = value as Record<string, unknown>
  if (Object.keys(record).sort().join(",") !== "contract,steps" || record["contract"] !== "hswm-semantic-program/v1" || !Array.isArray(record["steps"]) || record["steps"].length < 1 || record["steps"].length > HSWM_SEMANTIC_PROGRAM_MAX_STEPS) {
    return Either.left(fail("CONTENT_INVALID", "program contract or step bounds are invalid"))
  }
  const roles = new Set<string>()
  const steps: SemanticProgramStep[] = []
  for (const item of record["steps"]) {
    if (typeof item !== "object" || item === null || Array.isArray(item)) return Either.left(fail("CONTENT_INVALID", "step must be an object"))
    const step = item as Record<string, unknown>
    if (Object.keys(step).sort().join(",") !== "event,kernelId,opcode,role" || !identifier(step["role"]) || !eventText(step["event"]) || !identifier(step["kernelId"]) || step["opcode"] !== HSWM_SEMANTIC_PROGRAM_OPCODE || roles.has(step["role"])) {
      return Either.left(fail("CONTENT_INVALID", "step has an unknown opcode or invalid/duplicate role"))
    }
    roles.add(step["role"])
    steps.push(Object.freeze({ role: step["role"], event: step["event"], kernelId: step["kernelId"], opcode: step["opcode"] }))
  }
  return Either.right(Object.freeze({ contract: "hswm-semantic-program/v1", steps: Object.freeze(steps) }))
}

const current = (atoms: ReadonlyArray<CanonicalAtomV2>, uid: string): Either.Either<CanonicalAtomV2, SemanticProgramError> => {
  const matches = atoms.filter(atom => atom.key.atomUid === uid)
  const lineages = new Set(matches.map(atom => JSON.stringify([atom.key.schemaVersion, atom.key.lineageId])))
  if (lineages.size > 1) return Either.left(fail("AMBIGUOUS_PROGRAM", `atom UID is ambiguous: ${uid}`))
  if (matches.length === 0) return Either.left(fail("PROGRAM_MISSING", `program is absent: ${uid}`))
  return Either.right(matches.reduce((prior, atom) => atom.key.revisionId > prior.key.revisionId ? atom : prior))
}

const exact = (atoms: ReadonlyArray<CanonicalAtomV2>, key: CanonicalAtomV2Key): CanonicalAtomV2 | undefined =>
  atoms.find(atom => canonicalAtomV2KeyId(atom.key) === canonicalAtomV2KeyId(key))

/** Resolves every target against one immutable durable-state snapshot. */
export const resolveSemanticProgram = (
  state: CanonicalAtomV2DurableState,
  programUid: string,
  programBytes: Uint8Array
): Either.Either<ResolvedSemanticProgram, SemanticProgramError> => {
  if (!identifier(programUid)) return Either.left(fail("PROGRAM_MISSING", "program UID is invalid"))
  const program = current(state.canonical.atoms, programUid)
  if (Either.isLeft(program)) return Either.left(program.left)
  if (program.right.kind !== HSWM_SEMANTIC_PROGRAM_KIND) return Either.left(fail("PROGRAM_WRONG_KIND", "selected atom is not a semantic program"))
  if (program.right.content.mediaType !== HSWM_SEMANTIC_PROGRAM_MEDIA_TYPE) return Either.left(fail("CONTENT_INVALID", "program media type is invalid"))
  if (program.right.content.byteLength !== programBytes.byteLength || program.right.content.sha256 !== sha(programBytes)) return Either.left(fail("CONTENT_MISMATCH", "program content descriptor does not bind its bytes"))
  const content = decodeSemanticProgramContent(programBytes)
  if (Either.isLeft(content)) return Either.left(content.left)
  const refs = program.right.references.filter(ref => ref.referenceType !== "hswm:reference:supersedes")
  if (refs.length !== content.right.steps.length || refs.some((ref, index) =>
    ref.referenceType !== HSWM_SEMANTIC_PROGRAM_TARGET_REFERENCE || ref.role !== content.right.steps[index]!.role)) {
    return Either.left(fail("REFERENCE_INVALID", "ordered target references differ from declared step roles"))
  }
  const byRole = new Map<string, CanonicalAtomV2Key>()
  for (const ref of refs) {
    if (byRole.has(ref.role)) return Either.left(fail("REFERENCE_INVALID", `duplicate target role: ${ref.role}`))
    byRole.set(ref.role, ref.target)
  }
  const steps: ResolvedSemanticProgramStep[] = []
  for (const step of content.right.steps) {
    const target = byRole.get(step.role)
    if (target === undefined) return Either.left(fail("REFERENCE_INVALID", `missing target role: ${step.role}`))
    const atom = exact(state.canonical.atoms, target)
    if (atom === undefined) return Either.left(fail("TARGET_MISSING", `target is absent: ${step.role}`))
    if (atom.kind !== "semantic_relation") return Either.left(fail("TARGET_WRONG_KIND", `target is not semantic_relation: ${step.role}`))
    const latest = current(state.canonical.atoms, target.atomUid)
    if (Either.isLeft(latest) || canonicalAtomV2KeyId(latest.right.key) !== canonicalAtomV2KeyId(target)) return Either.left(fail("TARGET_NOT_CURRENT", `target revision is stale: ${step.role}`))
    steps.push(Object.freeze({ ...step, target: Object.freeze({ ...target }) }))
  }
  return Either.right(Object.freeze({ program: program.right, stateRevision: state.canonical.revision, content: content.right, steps: Object.freeze(steps) }))
}
