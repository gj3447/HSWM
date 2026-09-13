import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { Either } from "effect"
import { expect, it } from "vitest"
import { adaptNativeUslV2, validateNativeUslV2Wire } from "../src/native-usl-v2-wire-domain.js"

const fixture = async (): Promise<Record<string, unknown>> => JSON.parse(await readFile(resolve(import.meta.dirname, "../../../../_research/usl_adapter/examples/preview.v2.json"), "utf8")) as Record<string, unknown>
const golden = async (): Promise<Record<string, unknown>> => JSON.parse(await readFile(resolve(import.meta.dirname, "fixtures/native-usl-v2-projection.golden.json"), "utf8")) as Record<string, unknown>
const request = (value: Record<string, unknown>) => ({ plan: value["plan"], report: value["report"], policy: value["policy"] })

it("accepts the source-pinned v2 fixture", async () => {
  const result = validateNativeUslV2Wire(request(await fixture()) as never)
  expect(Either.isRight(result), Either.isLeft(result) ? result.left.detail : "").toBe(true)
})

it("projects the source-bound v2 fixture to the complete Python golden output", async () => {
  const value = await fixture(); const checks = (value["preview"] as Record<string, Record<string, unknown>>)["checks"]
  if (checks === undefined) throw new Error("source-pinned fixture is missing preview checks")
  const result = adaptNativeUslV2({ ...request(value), allowed_reads: checks["allowed_reads"], now: checks["now"], revision: checks["revision"] } as never)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) expect(result.right).toEqual((await golden())["projection"])
})

it("rejects a tampered observation digest", async () => {
  const value = await fixture(); (value["report"] as Record<string, unknown>)["observationDigest"] = `sha256:${"0".repeat(64)}`
  expect(Either.isLeft(validateNativeUslV2Wire(request(value) as never))).toBe(true)
})

it("rejects an unsupported read-scope locator spelling", async () => {
  const value = await fixture(); const scope = (value["report"] as Record<string, unknown>)["readScope"] as Record<string, unknown>
  ;(scope["allowedLocators"] as string[])[0] = "https://EXAMPLE.invalid/"
  expect(Either.isLeft(validateNativeUslV2Wire(request(value) as never))).toBe(true)
})
