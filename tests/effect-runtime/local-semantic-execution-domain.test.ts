import { describe, expect, it } from "vitest"
import { localSemanticCases, localSemanticModeInstructions, localSemanticModeSchemas, localSemanticModes, localSemanticSchedule, parseLocalSemanticOutput } from "../../src/hswm/effect-runtime/src/local-semantic-execution-domain.js"
import { label, task } from "../../_research/jev_principles_v1/support/domain.mjs"

describe("local semantic execution fixture", () => {
  it("enumerates the existing four-family 128-case truth table without placing expectations in inputs", () => {
    expect(localSemanticCases).toHaveLength(128)
    expect(new Set(localSemanticCases.map(entry => entry.caseId)).size).toBe(128)
    for (const entry of localSemanticCases) {
      const id = (entry.input.fields.subject.dax | entry.input.fields.subject.wug << 1 | entry.input.fields.subject.zif << 2 | entry.input.fields.context.pel << 3 | entry.input.fields.exception.nub << 4)
      expect(entry.expected.answer).toBe(label(entry.familyIndex, id))
      expect(JSON.stringify(entry.input)).not.toContain("expected")
      expect(JSON.stringify(entry.input)).not.toContain("answer")
      expect(entry.input.priorEvidence).toEqual([])
      expect(entry.input.relation.uncertainty).toBe("authored-finite-fixture-reference-not-world-truth")
      expect(entry.input.roles).toEqual([
        { role: "subject", ordinal: 0, referenceType: "LOCAL_SEMANTIC_INPUT" },
        { role: "context", ordinal: 1, referenceType: "LOCAL_SEMANTIC_INPUT" },
        { role: "exception", ordinal: 2, referenceType: "LOCAL_SEMANTIC_INPUT" }
      ])
    }
  })

  it("uses the exact old-fixture oracle text for each family", () => {
    for (const entry of localSemanticCases) {
      expect(entry.input.relation.semanticText).toBe(task(entry.familyIndex, 0).oracle)
    }
  })

  it("creates a serial 384-occurrence schedule with the same case input across all modes and rotating order", () => {
    expect(localSemanticModes).toEqual(["E0", "E1", "E2"])
    expect(localSemanticSchedule).toHaveLength(384)
    expect(localSemanticSchedule.map(entry => entry.ordinal)).toEqual(Array.from({ length: 384 }, (_, index) => index))
    for (let index = 0; index < localSemanticCases.length; index++) {
      const block = localSemanticSchedule.slice(index * 3, index * 3 + 3)
      expect(block.map(entry => entry.caseId)).toEqual([localSemanticCases[index]!.caseId, localSemanticCases[index]!.caseId, localSemanticCases[index]!.caseId])
      expect(new Set(block.map(entry => entry.mode))).toEqual(new Set(localSemanticModes))
      expect(block[0]!.mode).toBe(localSemanticModes[index % 3])
    }
  })

  it("accepts only the stated E1 and E2 JSON contracts", () => {
    expect(parseLocalSemanticOutput("E1", '{"answer":1}')).toEqual({ valid: true, output: { answer: 1 } })
    expect(parseLocalSemanticOutput("E2", '{"base":1,"context_flip":0,"exception_flip":1,"answer":0}')).toEqual({ valid: true, output: { base: 1, context_flip: 0, exception_flip: 1, answer: 0 } })
    for (const [mode, text] of [
      ["E1", "not json"], ["E1", "[0]"], ["E1", '{"answer":true}'], ["E1", '{"answer":0,"extra":0}'],
      ["E1", '{"answer":0,"\\u0061nswer":1}'], ["E2", '{"base":0,"context_flip":0,"exception_flip":0}'], ["E2", '{"base":0,"context_flip":0,"exception_flip":false,"answer":0}'], ["E2", '{"answer":0,"base":0,"context_flip":0,"exception_flip":0,"extra":0}']
    ] as const) expect(parseLocalSemanticOutput(mode, text).valid).toBe(false)
    expect(parseLocalSemanticOutput("E1", '{"answer":0,"\\u0061nswer":1}')).toEqual({ valid: false, refusal: { reason: "DUPLICATE_KEY" } })
  })

  it("exposes answer-free output instructions and schemas", () => {
    expect(localSemanticModeInstructions.E0).toBe("Return only one token: 0 or 1.")
    expect(localSemanticModeInstructions.E1).toContain("sole key answer")
    expect(localSemanticModeInstructions.E2).toContain("base is the initial bit before flips")
    expect(localSemanticModeSchemas.E1).toMatchObject({ type: "object", additionalProperties: false, required: ["answer"] })
    expect(localSemanticModeSchemas.E2).toMatchObject({ type: "object", additionalProperties: false, required: ["base", "context_flip", "exception_flip", "answer"] })
  })
})
