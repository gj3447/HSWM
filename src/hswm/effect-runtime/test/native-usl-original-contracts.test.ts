import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { Either } from "effect"
import { expect, it } from "vitest"
import { projectNativeUsl } from "../src/native-usl-cli-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson } from "../src/native-task-json-domain.js"

interface Contract { readonly test: string; readonly request_json: string; readonly expected: { readonly status: "ACCEPT" | "REJECT"; readonly projection?: unknown } }
const corpus = async (): Promise<readonly Contract[]> => (JSON.parse(await readFile(resolve(import.meta.dirname, "../../../../tests/fixtures/native_migration/usl_original_contracts_v1/contracts.json"), "utf8")) as { readonly cases: readonly Contract[] }).cases
it("matches each source-pinned original USL adapter acceptance boundary", async () => {
  for (const row of await corpus()) {
    const decoded = decodeNativeTaskJson(new TextEncoder().encode(row.request_json))
    if (Either.isLeft(decoded)) throw decoded.left
    const result = projectNativeUsl(decoded.right)
    if (Either.isLeft(result) && row.expected.status === "ACCEPT") throw new Error(`${row.test}: ${result.left.detail}`)
    expect(Either.isRight(result), row.test).toBe(row.expected.status === "ACCEPT")
    if (row.expected.status === "ACCEPT" && Either.isRight(result)) expect(JSON.parse(renderNativeTaskJson(result.right)), row.test).toEqual(row.expected.projection)
  }
})
