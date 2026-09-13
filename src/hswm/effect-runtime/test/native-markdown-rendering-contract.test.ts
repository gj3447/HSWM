import { readFileSync, readdirSync } from "node:fs"
import { join, relative, resolve } from "node:path"
import { Either } from "effect"
import { describe, expect, it } from "vitest"
import { compilePortableMarkdownMath } from "../src/native-markdown-math-domain.js"

const root = resolve(import.meta.dirname, "../../../..")
const codePointOrder = (first: string, second: string): number => {
  const left = Array.from(first), right = Array.from(second), length = Math.min(left.length, right.length)
  for (let index = 0; index < length; index += 1) {
    const a = left[index]!.codePointAt(0)!, b = right[index]!.codePointAt(0)!
    if (a !== b) return a - b
  }
  return left.length - right.length
}
const markdown = (directory: string): ReadonlyArray<string> => {
  const found: string[] = []
  const visit = (current: string): void => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const candidate = join(current, entry.name)
      if (entry.isDirectory()) visit(candidate)
      else if (entry.isFile() && candidate.endsWith(".md")) found.push(candidate)
    }
  }
  visit(directory)
  return found.sort(codePointOrder)
}
const publicMathDocuments = Object.freeze([join(root, "README.md"), join(root, "INDEX.md"), ...markdown(join(root, "ontology"))])
const compilableMathDocuments = Object.freeze([...publicMathDocuments, ...markdown(join(root, "docs/canon")), ...markdown(join(root, "docs/research"))])
const legacyOperatornameBudget: Readonly<Record<string, number>> = Object.freeze({
  "docs/canon/HSWM_CONSTITUTION_2026-08-20.md": 3,
  "docs/canon/HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md": 1,
  "docs/canon/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md": 5,
  "docs/canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md": 1,
  "docs/canon/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md": 2,
  "docs/canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md": 6,
  "docs/canon/USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md": 1,
  "docs/research/HSWM_OCCAM_CORE_2026-08-20.md": 5,
  "docs/research/HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md": 2,
  "docs/research/HSWM_SWM0W_S2S_GATE_2026-08-20.md": 1,
  "docs/research/HSWM_UNIFIED_MEANING_MAP_2026-08-16.md": 1,
  "docs/research/PROM_12_HSWM_CAUSAL_LOAD_BEARING_RESOLUTION_2026-07-26.md": 1,
  "docs/research/PROM_16_HSWM_HOLISTIC_SCIENTIFIC_ARCHITECTURE_2026-07-26.md": 1,
  "docs/research/PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md": 2,
  "docs/research/PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md": 4
})
const source = (path: string): string => readFileSync(path, "utf8")
const displayDelimiter = (text: string): boolean => text.split(/\r?\n/).some(line => line.trim() === "\\[" || line.trim() === "\\]")

describe("native portable Markdown rendering contract", () => {
  it("keeps public math surfaces on portable GitHub syntax", () => {
    for (const path of publicMathDocuments) {
      const text = source(path)
      expect(text, relative(root, path)).not.toContain("\\operatorname")
      expect(displayDelimiter(text), relative(root, path)).toBe(false)
    }
  })

  it("projects every canon, research, ontology, and public Markdown document", () => {
    for (const path of compilableMathDocuments) {
      const compiled = compilePortableMarkdownMath(source(path))
      expect(Either.isRight(compiled), relative(root, path)).toBe(true)
      if (Either.isRight(compiled)) {
        expect(compiled.right.text, relative(root, path)).not.toContain("\\operatorname")
        expect(displayDelimiter(compiled.right.text), relative(root, path)).toBe(false)
      }
    }
  })

  it("allows renderer-incompatible operator macros only in the frozen legacy budget", () => {
    for (const path of compilableMathDocuments) {
      const key = relative(root, path)
      const observed = source(path).split("\\operatorname").length - 1
      expect(observed, key).toBeLessThanOrEqual(legacyOperatornameBudget[key] ?? 0)
    }
  })
})
