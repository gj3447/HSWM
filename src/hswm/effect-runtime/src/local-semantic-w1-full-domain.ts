/** Frozen-shape W1 full-census expansion. It does not alter the v1 128/384 instrument. */
import {
  localSemanticCases,
  localSemanticModeInstructions,
  localSemanticModes,
  type LocalSemanticBit,
  type LocalSemanticCase,
  type LocalSemanticMode
} from "./local-semantic-execution-domain.js"

const freeze = <T>(value: T): Readonly<T> => Object.freeze(value)
export type FullW1Transform = "original" | "paraphrase-a" | "paraphrase-b" | "rename" | "reorder" | "role-exchange"
export type FullW1ScheduleKind = "census" | "sentinel"
export interface FullW1Input {
  readonly relation: { readonly semanticText: string; readonly disposition: string; readonly uncertainty: string; readonly exceptionRefs: readonly string[] }
  readonly roles: readonly { readonly role: string; readonly ordinal: number; readonly referenceType: "LOCAL_SEMANTIC_INPUT" }[]
  readonly priorEvidence: readonly []
  readonly fields: Readonly<Record<string, Readonly<Record<string, LocalSemanticBit>>>>
}
export interface FullW1Case {
  readonly caseId: string; readonly baseCaseId: string; readonly familyIndex: 0 | 1 | 2 | 3
  readonly familyName: LocalSemanticCase["familyName"]; readonly transform: FullW1Transform
  readonly input: FullW1Input; readonly inputJson: string
  /** Evaluator-only; never concatenate this object into a model frame. */
  readonly expected: LocalSemanticCase["expected"]
}
export interface FullW1ScheduleEntry {
  readonly ordinal: number; readonly caseId: string; readonly mode: LocalSemanticMode; readonly kind: FullW1ScheduleKind
  readonly repetition: number | null; readonly sentinelId: string | null
}
export interface FullW1Sentinel { readonly sentinelId: string; readonly caseId: string; readonly baseCaseId: string; readonly familyIndex: 0 | 1 | 2 | 3 }

const suffix = " Context flag pel equal to 1 flips that bit, while pel equal to 0 leaves it unchanged. Finally, exception flag nub equal to 1 flips the bit; nub equal to 0 leaves it unchanged."
const paraphraseA = [
  "Compare subject dax with subject wug: begin at 1 when they are different and otherwise begin at 0.",
  "Use subject zif as the starting bit; subject dax and subject wug have no effect on that start.",
  "Begin at 1 only if both subject dax and subject wug are 1; otherwise begin at 0.",
  "Select the starting bit with subject dax: when dax is 1 use subject wug, and when dax is 0 use subject zif."
] as const
const paraphraseB = [
  "Read subject dax and subject wug. Start at 0 when those bits agree, and at 1 otherwise.",
  "Start with subject zif. The starting bit ignores subject dax and subject wug.",
  "Start at 0 unless subject dax and subject wug are both 1; in that one situation start at 1.",
  "Subject dax selects a value: choose subject zif for dax=0 and subject wug for dax=1."
] as const
const suffixB = " After that, toggle the current bit if context pel is 1. Then toggle the resulting bit if exception nub is 1. A zero flag performs no toggle."
export const fullW1RenameBijection = freeze({
  sourceToOpaque: freeze({ subject: "r7", context: "r3", exception: "r9", dax: "v2", wug: "v5", zif: "v8", pel: "v4", nub: "v6" }),
  opaqueToSource: freeze({ r7: "subject", r3: "context", r9: "exception", v2: "dax", v5: "wug", v8: "zif", v4: "pel", v6: "nub" })
})
const renameMap = fullW1RenameBijection.sourceToOpaque
/** Whole identifier replacement deliberately leaves output keys such as context_flip intact. */
const renamed = (text: string): string => text.replace(/\b(subject|context|exception|dax|wug|zif|pel|nub)\b/giu, word => renameMap[word.toLowerCase() as keyof typeof renameMap]!)

const expectedFor = (family: 0 | 1 | 2 | 3, dax: LocalSemanticBit, wug: LocalSemanticBit, zif: LocalSemanticBit, pel: LocalSemanticBit, nub: LocalSemanticBit) => {
  const base: LocalSemanticBit = family === 0 ? (dax ^ wug) as LocalSemanticBit : family === 1 ? zif : family === 2 ? (dax & wug) as LocalSemanticBit : dax === 1 ? wug : zif
  return freeze({ base, context_flip: pel, exception_flip: nub, answer: (base ^ pel ^ nub) as LocalSemanticBit })
}
const originalInput = (base: LocalSemanticCase): FullW1Input => base.input
const withRelation = (base: LocalSemanticCase, semanticText: string): FullW1Input => freeze({ ...base.input, relation: freeze({ ...base.input.relation, semanticText }) })
const roleExchange = (base: LocalSemanticCase): FullW1Input => freeze({ ...base.input, fields: freeze({
  subject: freeze({ ...base.input.fields.subject, dax: base.input.fields.context.pel }),
  context: freeze({ ...base.input.fields.context, pel: base.input.fields.subject.dax }), exception: base.input.fields.exception
}) })
const renamedInput = (base: LocalSemanticCase): FullW1Input => freeze({
  relation: freeze({ ...base.input.relation, semanticText: renamed(base.input.relation.semanticText) }),
  roles: freeze(base.input.roles.map(role => freeze({ ...role, role: renameMap[role.role] }))), priorEvidence: base.input.priorEvidence,
  fields: freeze({ r7: freeze({ v2: base.input.fields.subject.dax, v5: base.input.fields.subject.wug, v8: base.input.fields.subject.zif }), r3: freeze({ v4: base.input.fields.context.pel }), r9: freeze({ v6: base.input.fields.exception.nub }) })
})
const reorderedInput = (base: LocalSemanticCase): FullW1Input => freeze({
  fields: freeze({ exception: base.input.fields.exception, context: base.input.fields.context, subject: base.input.fields.subject }),
  priorEvidence: base.input.priorEvidence, roles: freeze([...base.input.roles].reverse()), relation: base.input.relation
})

export const fullW1Transforms: readonly FullW1Transform[] = freeze(["original", "paraphrase-a", "paraphrase-b", "rename", "reorder", "role-exchange"])
const makeCase = (base: LocalSemanticCase, transform: FullW1Transform): FullW1Case => {
  const input = transform === "original" ? originalInput(base)
    : transform === "paraphrase-a" ? withRelation(base, `${paraphraseA[base.familyIndex]}${suffix}`)
    : transform === "paraphrase-b" ? withRelation(base, `${paraphraseB[base.familyIndex]}${suffixB}`)
    : transform === "rename" ? renamedInput(base)
    : transform === "reorder" ? reorderedInput(base)
    : roleExchange(base)
  const subject = input.fields[transform === "rename" ? "r7" : "subject"]!
  const context = input.fields[transform === "rename" ? "r3" : "context"]!
  const exception = input.fields[transform === "rename" ? "r9" : "exception"]!
  const expected = transform === "role-exchange"
    ? expectedFor(base.familyIndex, subject["dax"]!, subject["wug"]!, subject["zif"]!, context["pel"]!, exception["nub"]!)
    : base.expected
  return freeze({ caseId: `${transform}:${base.caseId}`, baseCaseId: base.caseId, familyIndex: base.familyIndex, familyName: base.familyName, transform, input, inputJson: JSON.stringify(input), expected })
}
export const fullW1Cases: readonly FullW1Case[] = freeze(fullW1Transforms.flatMap(transform => localSemanticCases.map(base => makeCase(base, transform))))

const originalByBase: Readonly<Record<string, LocalSemanticCase>> = freeze(Object.fromEntries(localSemanticCases.map(entry => [entry.caseId, entry])))
const fullByTransformAndBase: Readonly<Record<string, FullW1Case>> = freeze(Object.fromEntries(fullW1Cases.map(entry => [`${entry.transform}:${entry.baseCaseId}`, entry])))
const seededShuffle = <T>(values: readonly T[], seed: number): T[] => {
  let state = seed >>> 0; const out = [...values]
  for (let i = out.length - 1; i > 0; i -= 1) { state = (state * 1664525 + 1013904223) >>> 0; const j = state % (i + 1); const value = out[i]!; out[i] = out[j]!; out[j] = value }
  return out
}
const modesFor = (caseIndex: number): readonly LocalSemanticMode[] => localSemanticModes.map((_, modeIndex) => localSemanticModes[(caseIndex + modeIndex) % localSemanticModes.length]!)
const censusCases = (): readonly FullW1Case[] => {
  const original = localSemanticCases.map(base => fullByTransformAndBase[`original:${base.caseId}`]!)
  const rest = seededShuffle(fullW1Transforms.filter(t => t !== "original"), 20261007).flatMap((transform, transformIndex) =>
    seededShuffle(localSemanticCases, 20261007 + transformIndex + 1).map(base => fullByTransformAndBase[`${transform}:${base.caseId}`]!))
  return [...original, ...rest]
}
const sentinelSpecs = freeze([[0, 0], [0, 1], [1, 0], [1, 4], [2, 0], [2, 3], [3, 0], [3, 3]] as const)
export const fullW1Sentinels: readonly FullW1Sentinel[] = freeze(sentinelSpecs.map(([family, index]) => {
  const baseCaseId = `local-semantic-f${family}-i${String(index).padStart(2, "0")}`
  const entry = fullByTransformAndBase[`original:${baseCaseId}`]!
  return freeze({ sentinelId: `sentinel-f${family}-i${String(index).padStart(2, "0")}`, caseId: entry.caseId, baseCaseId, familyIndex: family })
}))
export const fullW1Schedule: readonly FullW1ScheduleEntry[] = freeze((() => {
  const schedule: FullW1ScheduleEntry[] = []
  for (const [caseIndex, entry] of censusCases().entries()) for (const mode of modesFor(caseIndex % 128)) schedule.push(freeze({ ordinal: schedule.length, caseId: entry.caseId, mode, kind: "census", repetition: null, sentinelId: null }))
  for (let repetition = 0; repetition < 20; repetition += 1) for (const sentinel of fullW1Sentinels) for (const mode of modesFor(originalByBase[sentinel.baseCaseId]!.familyIndex)) schedule.push(freeze({ ordinal: schedule.length, caseId: sentinel.caseId, mode, kind: "sentinel", repetition, sentinelId: sentinel.sentinelId }))
  return schedule
})())

/** Model-visible instruction paired to a transformed frame; it never includes evaluator gold. */
export const fullW1ModeInstructions = (entry: FullW1Case, mode: LocalSemanticMode): string => entry.transform === "rename"
  ? renamed(localSemanticModeInstructions[mode])
  : localSemanticModeInstructions[mode]

export const fullW1RoleExchangeChangedCount = fullW1Cases.filter(entry => entry.transform === "role-exchange" && entry.expected.answer !== originalByBase[entry.baseCaseId]!.expected.answer).length
export const fullW1RoleExchangeChangedInputCount = fullW1Cases.filter(entry => entry.transform === "role-exchange" && entry.inputJson !== JSON.stringify(originalByBase[entry.baseCaseId]!.input)).length
export const fullW1RoleExchangeChangedIntermediateCount = fullW1Cases.filter(entry => {
  if (entry.transform !== "role-exchange") return false
  const original = originalByBase[entry.baseCaseId]!.expected
  return entry.expected.base !== original.base || entry.expected.context_flip !== original.context_flip || entry.expected.exception_flip !== original.exception_flip
}).length
