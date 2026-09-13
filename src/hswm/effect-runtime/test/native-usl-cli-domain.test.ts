import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { Either } from "effect"
import { expect, it } from "vitest"
import { previewNativeUsl, projectNativeUsl } from "../src/native-usl-cli-domain.js"

const fixture = async (version: "v1" | "v2"): Promise<Record<string, unknown>> => JSON.parse(await readFile(resolve(import.meta.dirname, `../../../../_research/usl_adapter/examples/preview.${version}.json`), "utf8")) as Record<string, unknown>
const projectRequest = (value: Record<string, unknown>) => { const checks = (value["preview"] as Record<string, Record<string, unknown>>)["checks"]!; return { plan: value["plan"], report: value["report"], policy: value["policy"], allowed_reads: checks["allowed_reads"], now: checks["now"], revision: checks["revision"] } }

it("projects both source-pinned wire versions and preserves the v2 full golden", async () => {
  const v1 = projectNativeUsl(projectRequest(await fixture("v1")) as never)
  expect(Either.isRight(v1)).toBe(true)
  if (Either.isRight(v1)) expect(v1.right).toMatchObject({ schema_version: "hswm-usl-observation-projection/v1", status: "READY", observations: [{ value: true }] })
  const v2 = projectNativeUsl(projectRequest(await fixture("v2")) as never)
  const golden = JSON.parse(await readFile(resolve(import.meta.dirname, "fixtures/native-usl-v2-projection.golden.json"), "utf8")) as { readonly projection: unknown }
  expect(Either.isRight(v2)).toBe(true)
  if (Either.isRight(v2)) expect(v2.right).toEqual(golden.projection)
})

it("reuses the native conditional preview and rejects preview scope or Boolean-domain drift", async () => {
  const value = await fixture("v1"), ready = previewNativeUsl(value as never)
  expect(Either.isRight(ready)).toBe(true)
  if (Either.isRight(ready)) expect(ready.right).toMatchObject({ schema_version: "hswm-usl-preview/v1", adapter: { status: "READY" }, preview: { status: "DESIGN_ONLY_NO_EXECUTION", hypothetical_next_step: { kind: "ACTION_PROPOSAL" } } })
  const scope = structuredClone(value); ((scope["preview"] as Record<string, Record<string, unknown>>)["checks"]!)["scope"] = "wrong"
  expect(Either.isLeft(previewNativeUsl(scope as never))).toBe(true)
  const domain = structuredClone(value); (((domain["preview"] as Record<string, unknown>)["domain"] as Array<Record<string, unknown>>)[0]!)["values"] = [0, 1]
  expect(Either.isLeft(previewNativeUsl(domain as never))).toBe(true)
})
