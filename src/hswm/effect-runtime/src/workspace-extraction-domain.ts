/** Exact source extraction is a typed contract, separate from navigation labels and model reward. */
import { Either, Schema } from "effect"
import { contextError, contextHash } from "./semantic-context-domain.js"
import { kgSha256 } from "./native-kg-bundle-domain.js"
import { workspaceSourceUnits } from "./workspace-source-units-domain.js"
import type { WorkspaceActivationSource } from "./workspace-activation-runtime.js"

export const WorkspaceExtractionSchema = Schema.Literal("FIRST_ATX_H1_TEXT_V1")
export type WorkspaceExtraction = typeof WorkspaceExtractionSchema.Type
const invalid = (detail: string) => contextError("WORKSPACE_EXTRACTION_INVALID", detail)
const bytes = (text: string) => new TextEncoder().encode(text)

/** V1 strips the opening marker and surrounding whitespace only; inline markup/closing # stay literal.
 * Uses the existing ATX section profile (not a general CommonMark renderer). No answer enters the prompt. */
export const prepareWorkspaceExtraction = (source: WorkspaceActivationSource, raw: unknown) => Either.gen(function* () {
  const selector = yield* Schema.decodeUnknownEither(WorkspaceExtractionSchema)(raw).pipe(Either.mapLeft(() => invalid("Unknown extraction selector")))
  const document = bytes(source.documentText), active = bytes(source.sourceText), selection = source.binding.selection
  const units = workspaceSourceUnits(source.documentText)
  if (contextHash(source.binding) !== source.sourceId || kgSha256(document) !== source.binding.documentSha256 ||
    document.byteLength !== source.binding.documentBytes || kgSha256(active) !== source.binding.activationSha256 ||
    active.byteLength !== source.binding.activationBytes || contextHash(units) !== contextHash(source.units))
    return yield* Either.left(invalid("Source identity or complete document changed"))
  const selected = units.find(u => u.id === selection.unitId)
  const validSelection = selection.kind === "COMPLETE_DOCUMENT" ? selection.unitId === null && selection.startByte === 0 &&
    selection.endByte === document.byteLength && source.sourceText === source.documentText : selected !== undefined &&
    selected.startByte === selection.startByte && selected.endByte === selection.endByte && selected.text === source.sourceText
  if (!validSelection) return yield* Either.left(invalid("Activated range is not the declared complete source unit"))
  const unit = units.find(u => u.heading?.level === 1)
  if (!unit || !unit.heading?.text) return yield* Either.left(invalid("No nonempty H1 in the supported ATX source profile"))
  const line = /^[^\r\n]*/.exec(unit.text)?.[0] ?? ""
  const opening = /^ {0,3}#[\t ]+/.exec(line)?.[0]
  if (opening === undefined) return yield* Either.left(invalid("Heading has no source span"))
  const remainder = line.slice(opening.length), expected = remainder.trim()
  const prefix = opening + remainder.slice(0, remainder.length - remainder.trimStart().length)
  const startByte = unit.startByte + bytes(prefix).byteLength, endByte = startByte + bytes(expected).byteLength
  if (startByte < selection.startByte || endByte > selection.endByte || expected.length > 8192)
    return yield* Either.left(invalid("First document H1 is outside the active evidence or output budget; explicitly select its unit"))
  return { expected, binding: { contract: "hswm-workspace-extraction/v1" as const, selector, sourceId: source.sourceId,
    documentSha256: source.binding.documentSha256, activationSha256: source.binding.activationSha256, startByte, endByte } }
})
export type PreparedWorkspaceExtraction = Either.Either.Right<ReturnType<typeof prepareWorkspaceExtraction>>
export const verifyWorkspaceExtraction = (prepared: PreparedWorkspaceExtraction, prediction: string | null) => ({
  ...prepared.binding, status: prediction === null ? "NOT_EXECUTED" as const : prediction === prepared.expected ? "MATCH" as const : "MISMATCH" as const,
  expectedSha256: kgSha256(prepared.expected), observedSha256: prediction === null ? null : kgSha256(prediction)
})
