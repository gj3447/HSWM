import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { expect, it } from "vitest"
import { canonicalAtomV2ReadSetDecision } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-validation-guards.js"

const contract = "hswm-journal-validation/v1"
const leanPath = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMJournalValidationCli")
const boundary = { readSetValidationProved: true, nativeValidationProved: false, jsonParserProved: false }

it("preserves native read-set duplicate-before-missing decision order", () => {
  const cases = [
    { existing: [], readSet: [] },
    { existing: ["a", "b"], readSet: ["a", "b"] },
    { existing: ["a"], readSet: ["a", "a"] },
    { existing: ["a", "a"], readSet: ["missing", "missing"] },
    { existing: ["a"], readSet: ["missing"] },
    { existing: ["a"], readSet: ["missing", "missing"] },
    { existing: ["a", "b"], readSet: ["a", "missing"] }
  ] as const
  const expected = cases.map(({ existing, readSet }) => ({
    decision: canonicalAtomV2ReadSetDecision(existing, readSet), ...boundary
  }))
  expect(expected.map(({ decision }) => decision)).toEqual([
    "PASSED", "PASSED", "READ_SET_DUPLICATE", "STATE_KEY_DUPLICATE", "READ_SET_MISSING", "READ_SET_DUPLICATE", "READ_SET_MISSING"
  ])
  if (process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1") {
    const input = cases.map(value => ({ contract, kind: "read-set", ...value }))
    const output = execFileSync(leanPath, [], { input: JSON.stringify(input), encoding: "utf8" })
    expect(JSON.parse(output)).toEqual(expected)
  }
})
