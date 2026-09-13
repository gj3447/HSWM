import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { gunzipSync } from "node:zlib"
import { Either } from "effect"
import { expect, it } from "vitest"
import { projectNativeUsl } from "../src/native-usl-cli-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson } from "../src/native-task-json-domain.js"

interface Case { readonly test: string; readonly request_json: string; readonly expected: { readonly status: "ACCEPT" | "REJECT"; readonly projection?: unknown } }
it("matches the deterministic Python USL mutation corpus",async()=>{const corpus=JSON.parse(gunzipSync(await readFile(resolve(import.meta.dirname,"../../../../tests/fixtures/native_migration/usl_original_contracts_v1/differential-contracts.json.gz"))).toString("utf8")) as {readonly cases:readonly Case[]};for(const row of corpus.cases){const input=decodeNativeTaskJson(new TextEncoder().encode(row.request_json));if(Either.isLeft(input))throw input.left;const result=projectNativeUsl(input.right);if(Either.isLeft(result)&&row.expected.status==="ACCEPT")throw new Error(`${row.test}: ${result.left.detail}`);expect(Either.isRight(result),row.test).toBe(row.expected.status==="ACCEPT");if(row.expected.status==="ACCEPT"&&Either.isRight(result))expect(JSON.parse(renderNativeTaskJson(result.right)),row.test).toEqual(row.expected.projection)}})
