import { isAbsolute, relative, resolve } from "node:path"
import { parseArgs } from "node:util"
import { Data, Effect, Either } from "effect"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { decodeGeneralJsonBytes, type GeneralJson } from "./general-json-domain.js"
import { verifyNativeFormalOpenSslEd25519 } from "./native-formal-crypto-runtime.js"
import { FORMAL_DURABLE_PREREG, FORMAL_EXTRA_PATHS, NativeFormalVerifierError, verifyNativeFormal, type NativeFormalVerifier } from "./native-formal-verifier-domain.js"
export class NativeFormalVerifyCliError extends Data.TaggedError("NativeFormalVerifyCliError")<{readonly detail:string}>{}
const usage="usage: hswm-formal-verify <canonical-permit-vector|cellular-longinus|cellular-runtime-longinus|durable-runtime-longinus> [--repo-root ROOT]"
const fail=(detail:string)=>new NativeFormalVerifyCliError({detail})
const known=(v:string):v is NativeFormalVerifier=>["canonical-permit-vector","cellular-longinus","cellular-runtime-longinus","durable-runtime-longinus"].includes(v)
const record=(value:GeneralJson|undefined):value is Readonly<Record<string,GeneralJson>>=>typeof value==="object"&&value!==null&&!Array.isArray(value)
const safeRelative=(path:string):boolean=>path.length>0&&path.length<=512&&!isAbsolute(path)&&path.split("/").every(segment=>segment.length>0&&segment!=="."&&segment!=="..")
const base64url=(value:GeneralJson|undefined):Uint8Array|null=>{
 if(typeof value!=="string"||!/^[A-Za-z0-9_-]+$/.test(value))return null
 const bytes=Buffer.from(value,"base64url")
 return bytes.toString("base64url")===value?bytes:null
}
export const runNativeFormalVerifyCli=(argv:readonly string[]):Effect.Effect<{readonly stdout:string;readonly exitCode:number},NativeFormalVerifyCliError,PosixFileSystem|BoundedSubprocess>=>Effect.gen(function*(){
 const parsed=yield* Effect.try({try:()=>parseArgs({args:[...argv],allowPositionals:true,strict:true,options:{"repo-root":{type:"string"},help:{type:"boolean"}}}),catch:()=>fail(usage)})
 if(parsed.values.help)return{stdout:`${usage}\n`,exitCode:0};if(parsed.positionals.length!==1||!known(parsed.positionals[0]!))return yield* Effect.fail(fail(usage))
 const kind=parsed.positionals[0]!,root=resolve(parsed.values["repo-root"]??process.cwd()),fs=yield* PosixFileSystem,cache=new Map<string,Uint8Array>()
 const load=(path:string):Effect.Effect<Uint8Array,NativeFormalVerifyCliError>=>{
  if(!safeRelative(path))return Effect.fail(fail("source path is outside repository root"))
  const target=resolve(root,path),rel=relative(root,target)
  if(rel===""||isAbsolute(rel)||rel===".."||rel.startsWith("../"))return Effect.fail(fail("source path is outside repository root"))
  const cached=cache.get(path)
  if(cached!==undefined)return Effect.succeed(cached)
  return fs.readRegularBounded(target,{maximumBytes:16*1024*1024,minimumBytes:0,operation:"native-formal-verifier"}).pipe(Effect.mapError(()=>fail(`missing source: ${path}`)),Effect.map(x=>{cache.set(path,x.bytes);return x.bytes}))
 }
 const manifest={"cellular-longinus":"LONGINUS_HSWM_CELLULAR_DEFINITION_BINDING_2026-07-26.json","cellular-runtime-longinus":"LONGINUS_HSWM_CELLULAR_RUNTIME_BINDING_2026-07-26.json","durable-runtime-longinus":"LONGINUS_HSWM_DURABLE_RUNTIME_BINDING_2026-07-26.json"} as const
 if(kind==="canonical-permit-vector")yield* load("src/hswm/effect-runtime/test/fixtures/canonical-permit-envelope-v1.vector.json")
 else {const raw=yield* load(manifest[kind]);const decoded=decodeGeneralJsonBytes(raw);if(Either.isRight(decoded)&&record(decoded.right)){const bindings=decoded.right["bindings"];if(Array.isArray(bindings))for(const binding of bindings)if(record(binding)){const path=binding["source_path"];if(typeof path==="string")yield* load(path)}
  for(const path of FORMAL_EXTRA_PATHS[kind])yield* load(path)
  if(kind==="durable-runtime-longinus"){const preregRaw=cache.get(FORMAL_DURABLE_PREREG);if(preregRaw===undefined)return yield* Effect.fail(fail("missing preregistration"));const prereg=decodeGeneralJsonBytes(preregRaw);if(Either.isRight(prereg)&&prereg.right!==undefined&&record(prereg.right)){const judge=prereg.right["locked_judge"];if(record(judge)&&typeof judge["path"]==="string")yield* load(judge["path"])}
 }}
 }
 const read=(path:string)=>{const value=cache.get(path);return value===undefined?Either.left(new NativeFormalVerifierError({detail:`missing source: ${path}`})):Either.right(value)}
 const out=verifyNativeFormal(kind,read);if(Either.isLeft(out))return yield* Effect.fail(fail(out.left.detail))
 if(kind==="canonical-permit-vector"){
  const vector=cache.get("src/hswm/effect-runtime/test/fixtures/canonical-permit-envelope-v1.vector.json")
  if(vector===undefined)return yield* Effect.fail(fail("missing fixed vector"))
  const parsedVector=decodeCanonicalJsonBytes(vector)
  if(Either.isLeft(parsedVector)||!record(parsedVector.right))return yield* Effect.fail(fail("fixed vector cannot be decoded"))
  const document=base64url(parsedVector.right["signingDocumentCanonicalBase64Url"]),key=base64url(parsedVector.right["publicKeySpkiDerBase64Url"]),envelope=base64url(parsedVector.right["envelopeCanonicalBase64Url"])
  if(document===null||key===null||envelope===null)return yield* Effect.fail(fail("fixed vector bytes are invalid"))
  const parsedEnvelope=decodeCanonicalJsonBytes(envelope)
  if(Either.isLeft(parsedEnvelope)||parsedEnvelope.right===undefined||!record(parsedEnvelope.right))return yield* Effect.fail(fail("fixed envelope cannot be decoded"))
  const signature=base64url(parsedEnvelope.right["signature"])
  if(signature===null)return yield* Effect.fail(fail("fixed vector signature is invalid"))
  yield* verifyNativeFormalOpenSslEd25519({signingDocument:document,publicKeySpkiDer:key,signature}).pipe(Effect.mapError(error=>fail(error.detail)))
  const encoded=canonicalJsonBytes({...out.right,cryptoConsumer:"openssl-pkeyutl"})
  if(Either.isLeft(encoded))return yield* Effect.fail(fail(encoded.left.code))
  return{stdout:`${new TextDecoder().decode(encoded.right)}\n`,exitCode:0}
 }
 const encoded=canonicalJsonBytes(out.right);if(Either.isLeft(encoded))return yield* Effect.fail(fail(encoded.left.code));return{stdout:`${new TextDecoder().decode(encoded.right)}\n`,exitCode:0}
})
