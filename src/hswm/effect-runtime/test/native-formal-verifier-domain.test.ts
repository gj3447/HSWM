import { readFileSync } from "node:fs"
import { expect, it } from "@effect/vitest"
import { Either, Schema } from "effect"
import { NativeFormalVerifierError, verifyNativeFormal } from "../src/native-formal-verifier-domain.js"

const root=new URL("../../../..",import.meta.url)
const fixture=JSON.parse(readFileSync(new URL("../../../../tests/fixtures/formal_native_v1/original_python.json",import.meta.url),"utf8")) as {readonly canonical_permit_vector_stdout:string;readonly historical_root_failure:Readonly<Record<string,string>>}
const read=(path:string)=>{try{return Either.right(new Uint8Array(readFileSync(new URL(path,root))))}catch{return Either.left(new NativeFormalVerifierError({detail:`missing source: ${path}`}))}}
it("replays the original fixed vector with the explicitly identified native crypto consumer",()=>{const result=verifyNativeFormal("canonical-permit-vector",read);expect(Either.isRight(result)).toBe(true);if(Either.isRight(result))expect(result.right).toEqual({...JSON.parse(fixture.canonical_permit_vector_stdout),cryptoConsumer:"node:crypto"})})
it("preserves each historical root-path failure without rewriting its manifest",()=>{for(const [kind,path] of Object.entries(fixture.historical_root_failure)){const result=verifyNativeFormal(kind as "cellular-longinus"|"cellular-runtime-longinus"|"durable-runtime-longinus",()=>Either.left(new NativeFormalVerifierError({detail:`missing source: ${path}`})));expect(Either.isLeft(result)).toBe(true);if(Either.isLeft(result))expect(result.left.detail).toBe(`missing source: ${path}`)}})

const contracts=Schema.decodeUnknownSync(Schema.Array(Schema.Struct({kind:Schema.Literal("cellular-longinus","cellular-runtime-longinus","durable-runtime-longinus"),name:Schema.String,files:Schema.Record({key:Schema.String,value:Schema.String}),decision:Schema.Literal("ACCEPT","REJECT"),expected:Schema.Unknown})))(JSON.parse(readFileSync(new URL("../../../../tests/fixtures/formal_native_v1/longinus-contracts.json",import.meta.url),"utf8")))
it.each(contracts)("$kind / $name preserves the full original verifier decision",item=>{
 const observed=verifyNativeFormal(item.kind,path=>Object.hasOwn(item.files,path)?Either.right(new TextEncoder().encode(item.files[path])):Either.left(new NativeFormalVerifierError({detail:`missing source: ${path}`})))
 expect(Either.isRight(observed)?"ACCEPT":"REJECT").toBe(item.decision)
 if(Either.isRight(observed))expect(observed.right).toEqual(item.expected)
})
it("does not accept changed Permit nonclaims, keys or relaxed numeric JSON",()=>{
 const original=readFileSync(new URL("src/hswm/effect-runtime/test/fixtures/canonical-permit-envelope-v1.vector.json",root),"utf8")
 const source:Record<string,unknown>=JSON.parse(original)
 const invalid=[JSON.stringify({...source,expectedVerificationStatus:"AUTHORITATIVE_PERMIT"}),JSON.stringify({...source,publicKeySpkiDerBase64Url:"AAAA"}),original.replace('{','{"ignored":1.0,'),original.replace('{','{"ignored":-0,'),original.replace('{','{"ignored":9007199254740993,')]
 for(const value of invalid)expect(Either.isLeft(verifyNativeFormal("canonical-permit-vector",()=>Either.right(new TextEncoder().encode(value))))).toBe(true)
})
