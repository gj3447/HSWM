import { describe, expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { hasForbiddenProofShortcut, parseTheoremAxioms } from "../../src/hswm/effect-runtime/src/semantic-philosophy-proof-process.js"

describe("Lean theorem axiom report completeness", () => {
  const expected = ["Example.identity", "Example.extensional"]

  it("distinguishes existing admission constructors from proof-hole tactics", () => {
    expect(hasForbiddenProofShortcut("inductive Accepted : Prop where\n  | admit\n      (h : True) : Accepted\ntheorem use : Accepted := .admit trivial\ntheorem extract (h : Accepted) : True := by\n  cases h with\n  | admit witness => exact witness\n")).toBe(false)
    for (const source of ["theorem gap : False := by admit", "theorem gap : False := by\n  first\n  | admit\n  | assumption", "theorem gap (h : Accepted) : False := by\n  cases h with\n  | admit witness => admit", "theorem gap : False := by sorry", "axiom gap : False", "theorem gap : True := by native_decide"]) {
      expect(hasForbiddenProofShortcut(source)).toBe(true)
    }
    for (const source of ["HSWMCanonicalLearning", "HSWMOutcomeJudgment", "HSWMAtomicAdmission", "HSWMAtomicAdmissionConsistency", "HSWMEndToEndRuntimeRefinement", "HSWMExecutionCertificateWire"]) {
      expect(hasForbiddenProofShortcut(readFileSync(resolve(import.meta.dirname, `../../formal/${source}.lean`), "utf8")), source).toBe(false)
    }
  })

  it("retains both axiom-free and axiom-dependent theorem reports", () => {
    const result = parseTheoremAxioms(
      "'Example.identity' does not depend on any axioms\n'Example.extensional' depends on axioms: [propext, Quot.sound]\n",
      expected
    )
    expect(result).toEqual([
      { theorem: "Example.extensional", axioms: ["Quot.sound", "propext"] },
      { theorem: "Example.identity", axioms: [] }
    ])
  })

  it("rejects missing, duplicate, and unexpected theorem reports", () => {
    const line = "'Example.identity' does not depend on any axioms\n"
    expect(parseTheoremAxioms(line, expected)).toBeNull()
    expect(parseTheoremAxioms(line + line, expected)).toBeNull()
    expect(parseTheoremAxioms(line + "'Other.theorem' does not depend on any axioms\n", expected)).toBeNull()
  })

  it("preserves forbidden axioms for the caller to reject rather than silently dropping them", () => {
    expect(parseTheoremAxioms("'Example.identity' depends on axioms: [sorryAx]\n", ["Example.identity"]))
      .toEqual([{ theorem: "Example.identity", axioms: ["sorryAx"] }])
  })
})
