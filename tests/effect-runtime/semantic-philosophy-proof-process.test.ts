import { describe, expect, it } from "vitest"
import { parseTheoremAxioms } from "../../src/hswm/effect-runtime/src/semantic-philosophy-proof-process.js"

describe("Lean theorem axiom report completeness", () => {
  const expected = ["Example.identity", "Example.extensional"]

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
