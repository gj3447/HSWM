import { describe, expect, it } from "vitest"

import { localSemanticCases } from "../../src/hswm/effect-runtime/src/local-semantic-execution-domain.js"
import { label } from "../../_research/jev_principles_v1/support/domain.mjs"
import {
  fullW1Cases,
  fullW1ModeInstructions,
  fullW1RenameBijection,
  fullW1RoleExchangeChangedCount,
  fullW1RoleExchangeChangedInputCount,
  fullW1RoleExchangeChangedIntermediateCount,
  fullW1Schedule,
  fullW1Sentinels,
  fullW1Transforms
} from "../../src/hswm/effect-runtime/src/local-semantic-w1-full-domain.js"

const authoredBaseTables: readonly (readonly (0 | 1)[])[] = [
  [0, 1, 1, 0, 0, 1, 1, 0], [0, 0, 0, 0, 1, 1, 1, 1],
  [0, 0, 0, 1, 0, 0, 0, 1], [0, 0, 0, 1, 1, 0, 1, 1]
]

describe("full W1 frozen transform domain", () => {
  it("expands the original finite census into exactly six complete transform blocks without gold leakage", () => {
    expect(fullW1Transforms).toEqual(["original", "paraphrase-a", "paraphrase-b", "rename", "reorder", "role-exchange"])
    expect(fullW1Cases).toHaveLength(768)
    expect(new Set(fullW1Cases.map(entry => entry.caseId)).size).toBe(768)
    for (const transform of fullW1Transforms) expect(fullW1Cases.filter(entry => entry.transform === transform)).toHaveLength(128)
    for (const entry of fullW1Cases) {
      expect(entry.inputJson).toBe(JSON.stringify(entry.input))
      expect(entry.inputJson).not.toContain("expected")
      expect(entry.inputJson).not.toContain('"answer"')
      expect(entry.inputJson).not.toContain("base\"")
    }
    for (const original of localSemanticCases) {
      const expanded = fullW1Cases.find(entry => entry.caseId === `original:${original.caseId}`)!
      expect(expanded.inputJson).toBe(JSON.stringify(original.input))
      expect(expanded.expected).toEqual(original.expected)
    }
  })

  it("preserves or independently recomputes every six-block truth table", () => {
    for (const entry of fullW1Cases) {
      const base = localSemanticCases.find(candidate => candidate.caseId === entry.baseCaseId)!
      const fields = entry.input.fields
      const subject = fields[entry.transform === "rename" ? "r7" : "subject"]!
      const context = fields[entry.transform === "rename" ? "r3" : "context"]!
      const exception = fields[entry.transform === "rename" ? "r9" : "exception"]!
      const dax = entry.transform === "rename" ? subject["v2"]! : subject["dax"]!
      const wug = entry.transform === "rename" ? subject["v5"]! : subject["wug"]!
      const zif = entry.transform === "rename" ? subject["v8"]! : subject["zif"]!
      const pel = entry.transform === "rename" ? context["v4"]! : context["pel"]!
      const nub = entry.transform === "rename" ? exception["v6"]! : exception["nub"]!
      const threeBitIndex = dax | (wug << 1) | (zif << 2)
      const fiveBitIndex = threeBitIndex | (pel << 3) | (nub << 4)
      expect(entry.expected).toEqual({ base: authoredBaseTables[entry.familyIndex]![threeBitIndex]!, context_flip: pel, exception_flip: nub, answer: label(entry.familyIndex, fiveBitIndex) })
      if (entry.transform !== "role-exchange") expect(entry.expected).toEqual(base.expected)
    }
  })

  it("keeps renaming distinct from role/value binding exchange and makes reorder byte-visible", () => {
    const rename = fullW1Cases.filter(entry => entry.transform === "rename")
    for (const entry of rename) {
      expect(entry.input.relation.semanticText).not.toMatch(/\b(subject|context|exception|dax|wug|zif|pel|nub)\b/i)
      for (const mode of ["E0", "E1", "E2"] as const) {
        const instruction = fullW1ModeInstructions(entry, mode)
        expect(instruction).not.toMatch(/\b(dax|wug|zif|pel|nub)\b/i)
        if (mode === "E2") expect(instruction).toContain("context_flip")
        if (mode === "E2") expect(instruction).toContain("exception_flip")
      }
      const restoredRoles = entry.input.roles.map(role => fullW1RenameBijection.opaqueToSource[role.role as keyof typeof fullW1RenameBijection.opaqueToSource])
      expect(restoredRoles).toEqual(["subject", "context", "exception"])
      const restoredFields = Object.fromEntries(Object.entries(entry.input.fields).map(([role, values]) => [
        fullW1RenameBijection.opaqueToSource[role as keyof typeof fullW1RenameBijection.opaqueToSource],
        Object.fromEntries(Object.entries(values).map(([key, value]) => [fullW1RenameBijection.opaqueToSource[key as keyof typeof fullW1RenameBijection.opaqueToSource], value]))
      ]))
      const original = localSemanticCases.find(candidate => candidate.caseId === entry.baseCaseId)!
      expect(restoredFields).toEqual(original.input.fields)
    }
    for (const original of localSemanticCases) {
      const reorder = fullW1Cases.find(entry => entry.caseId === `reorder:${original.caseId}`)!
      expect(reorder.inputJson).not.toBe(JSON.stringify(original.input))
      expect(reorder.input.roles.map(role => role.ordinal)).toEqual([2, 1, 0])
      expect(reorder.expected).toEqual(original.expected)
      const exchange = fullW1Cases.find(entry => entry.caseId === `role-exchange:${original.caseId}`)!
      expect(exchange.input.fields["subject"]?.["dax"]).toBe(original.input.fields.context.pel)
      expect(exchange.input.fields["context"]?.["pel"]).toBe(original.input.fields.subject.dax)
      expect(exchange.input.roles).toEqual(original.input.roles)
    }
    expect(fullW1RoleExchangeChangedInputCount).toBe(64)
    expect(fullW1RoleExchangeChangedCount).toBe(32)
    expect(fullW1RoleExchangeChangedIntermediateCount).toBe(64)
  })

  it("keeps the original 384 gate first, then schedules five shuffled census blocks and all sentinel repeats", () => {
    expect(fullW1Schedule).toHaveLength(2784)
    expect(fullW1Schedule.map(entry => entry.ordinal)).toEqual(Array.from({ length: 2784 }, (_, ordinal) => ordinal))
    const census = fullW1Schedule.filter(entry => entry.kind === "census")
    const sentinels = fullW1Schedule.filter(entry => entry.kind === "sentinel")
    expect(census).toHaveLength(2304)
    expect(sentinels).toHaveLength(480)
    expect(census.slice(0, 384).map(entry => entry.caseId)).toEqual(localSemanticCases.flatMap(entry => [`original:${entry.caseId}`, `original:${entry.caseId}`, `original:${entry.caseId}`]))
    expect(fullW1Sentinels).toHaveLength(8)
    expect(fullW1Sentinels.map(entry => entry.familyIndex)).toEqual([0, 0, 1, 1, 2, 2, 3, 3])
    for (const familyIndex of [0, 1, 2, 3]) {
      expect(fullW1Sentinels.filter(entry => entry.familyIndex === familyIndex).map(entry =>
        localSemanticCases.find(candidate => candidate.caseId === entry.baseCaseId)!.expected.answer
      ).sort()).toEqual([0, 1])
    }
    for (const sentinel of fullW1Sentinels) {
      const repeats = sentinels.filter(entry => entry.sentinelId === sentinel.sentinelId)
      expect(repeats).toHaveLength(60)
      for (const mode of ["E0", "E1", "E2"] as const) {
        const modeRepeats = repeats.filter(entry => entry.mode === mode)
        expect(modeRepeats.map(entry => entry.repetition)).toEqual(Array.from({ length: 20 }, (_, repetition) => repetition))
        expect(new Set(modeRepeats.map(entry => entry.caseId))).toEqual(new Set([sentinel.caseId]))
      }
    }
    for (let repetition = 0; repetition < 20; repetition += 1) {
      expect(sentinels.slice(repetition * 24, repetition * 24 + 24).map(entry => entry.repetition)).toEqual(Array<number>(24).fill(repetition))
    }
  })
})
