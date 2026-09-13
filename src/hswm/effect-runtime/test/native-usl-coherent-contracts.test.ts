import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Either } from "effect"
import { expect,it } from "vitest"
import { projectNativeUsl } from "../src/native-usl-cli-domain.js"
import { decodeNativeTaskJson,renderNativeTaskJson } from "../src/native-task-json-domain.js"
import { nativePythonInstantMicroseconds } from "../src/native-python-instant-domain.js"
const dir=resolve(import.meta.dirname,"../../../../tests/fixtures/native_migration/usl_original_contracts_v1")
interface Case { readonly test:string;readonly request_json:string;readonly expected:{readonly status:"ACCEPT"|"REJECT";readonly projection?:unknown} }
it("matches coherent re-signed plan/report/policy mutations and multi-link order",()=>{
 const corpus=JSON.parse(readFileSync(resolve(dir,"coherent-contracts.json"),"utf8")) as {readonly cases:readonly Case[]}
 for(const row of corpus.cases){const decoded=decodeNativeTaskJson(new TextEncoder().encode(row.request_json));if(Either.isLeft(decoded))throw decoded.left;const result=projectNativeUsl(decoded.right);expect(Either.isRight(result),`${row.test}: ${Either.isLeft(result)?result.left.detail:"ACCEPT"}`).toBe(row.expected.status==="ACCEPT");if(Either.isRight(result))expect(JSON.parse(renderNativeTaskJson(result.right)),row.test).toEqual(row.expected.projection)}
})
it("preserves offset-aware Python calendar validation and microsecond instants",()=>{
 const corpus=JSON.parse(readFileSync(resolve(dir,"instant-contracts.json"),"utf8")) as {readonly cases:readonly {readonly input:string;readonly microseconds:string|null}[]}
 for(const row of corpus.cases)expect(nativePythonInstantMicroseconds(row.input)?.toString()??null,row.input).toBe(row.microseconds)
})
