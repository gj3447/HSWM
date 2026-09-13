import { DataFactory, Parser, Store } from "n3"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { normalizedShaclReport } from "../src/native-kg-qualification.js"
import { loadKgVendorEngines } from "../src/native-kg-vendor.js"

const head = `@prefix sh: <http://www.w3.org/ns/shacl#>. @prefix x: <urn:test:>. `
const base = `x:report a sh:ValidationReport; sh:conforms false; sh:result [a sh:ValidationResult; sh:focusNode x:focus; sh:resultPath x:path; sh:resultSeverity sh:Violation; sh:sourceConstraintComponent sh:ClassConstraintComponent; sh:sourceShape x:shape; sh:value x:value].`
const normalized = (ttl: string) => normalizedShaclReport(new Store(new Parser().parse(head + ttl)), DataFactory.namedNode("urn:test:report"), [])
const signature = async (ttl: string) => {
  const result = normalized(ttl)
  if (Either.isLeft(result)) throw result.left
  const {canonize} = await Effect.runPromise(loadKgVendorEngines)
  return canonize(result.right, {algorithm: "RDFC-1.0", inputFormat: "application/n-quads", format: "application/n-quads", maxWorkFactor: 4})
}
it("uses official optional-detail and message normalization without hiding normative differences", async () => {
  const optional = base.replace("sh:value x:value", "sh:detail [a sh:ValidationResult; sh:focusNode x:other]; sh:resultMessage \"extra engine message\"; sh:value x:value")
  expect(await signature(optional)).toBe(await signature(base))
  expect(await signature(base.replace("sh:value x:value", "sh:value x:wrong"))).not.toBe(await signature(base))
  expect(await signature(base.replace("sh:sourceShape x:shape; ", ""))).not.toBe(await signature(base))
})
it("refuses missing report/result types and noncanonical or duplicate conforms", () => {
  for (const bad of [base.replace("a sh:ValidationReport; ", ""), base.replace("a sh:ValidationResult; ", ""), base.replace("sh:conforms false", 'sh:conforms "false"'), base.replace("sh:conforms false", "sh:conforms false, true")]) expect(Either.isLeft(normalized(bad))).toBe(true)
})
it("clones structured paths independently and refuses cyclic path graphs", async () => {
  const a = base.replace("sh:resultPath x:path", "sh:resultPath [sh:inversePath x:path]")
  const b = base.replace("sh:resultPath x:path", "sh:resultPath _:shared") + " _:shared sh:inversePath x:path; sh:message \"irrelevant\"."
  expect(await signature(a)).toBe(await signature(b))
  expect(Either.isLeft(normalized(base.replace("sh:resultPath x:path", "sh:resultPath _:cycle") + " _:cycle sh:inversePath _:cycle."))).toBe(true)
})
