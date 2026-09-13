/** Read-only ports of the historical formal verifier contracts. */
import { createHash, verify } from "node:crypto"
import { Data, Either } from "effect"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { decodeGeneralJsonBytes, type GeneralJson } from "./general-json-domain.js"

export type NativeFormalVerifier = "canonical-permit-vector"|"cellular-longinus"|"cellular-runtime-longinus"|"durable-runtime-longinus"
export class NativeFormalVerifierError extends Data.TaggedError("NativeFormalVerifierError")<{readonly detail:string}>{}
export type NativeFormalRead = (path:string)=>Either.Either<Uint8Array,NativeFormalVerifierError>
const fail=<A=never>(detail:string):Either.Either<A,NativeFormalVerifierError>=>Either.left(new NativeFormalVerifierError({detail}))
const sha=(bytes:Uint8Array):string=>createHash("sha256").update(bytes).digest("hex")
const text=(bytes:Uint8Array):Either.Either<string,NativeFormalVerifierError>=>{try{return Either.right(new TextDecoder("utf-8",{fatal:true}).decode(bytes))}catch{return fail("input is not strict UTF-8")}}
const json=(bytes:Uint8Array):Either.Either<GeneralJson,NativeFormalVerifierError>=>{const out=decodeGeneralJsonBytes(bytes);return Either.isLeft(out)?fail(out.left.detail):Either.right(out.right)}
const record=(v:GeneralJson|undefined):v is Readonly<Record<string,GeneralJson>>=>typeof v==="object"&&v!==null&&!Array.isArray(v)
const list=(v:GeneralJson|undefined):ReadonlyArray<GeneralJson>|null=>Array.isArray(v)?v:null
const string=(v:GeneralJson|undefined):string|null=>typeof v==="string"?v:null
const REQUIRED_LAYERS: readonly string[] = Object.freeze(["KG_NODE","CONTRACT_BINDING","CODE_SYMBOL","FILE_LINE","LINE_RANGE","SHA256","CRATE_SCRIPT"])
const parseRange=(raw:string):Either.Either<readonly[number,number],NativeFormalVerifierError>=>{const parts=raw.split("-");if(parts.length!==2||!/^\d+$/.test(parts[0]!)||!/^\d+$/.test(parts[1]!))return fail(`invalid line_range: ${raw}`);const start=Number(parts[0]),end=Number(parts[1]);return start<1||end<start?fail(`invalid line_range: ${raw}`):Either.right([start,end])}
const base64url=(value:GeneralJson|undefined,field:string):Either.Either<Uint8Array,NativeFormalVerifierError>=>{const raw=string(value);if(raw===null||!/^[A-Za-z0-9_-]+$/.test(raw))return fail(`${field} is not unpadded base64url`);try{const decoded=Buffer.from(raw,"base64url");return decoded.toString("base64url")!==raw?fail(`${field} is not minimally encoded`):Either.right(decoded)}catch{return fail(`${field} is not unpadded base64url`)}}
const pythonSplitLines = (value: string): readonly string[] => {
 const parts=value.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/u)
 return parts.at(-1)===""?parts.slice(0,-1):parts
}
export const FORMAL_RUNTIME_SYMBOL_PAIRS = Object.freeze([
 ["requestCellStep","class RequestCellStep"],["recordCellOutput","class RecordCellOutput"],
 ["cellStepRequested","class CellStepRequested"],["cellStepCompleted","class CellStepCompleted"],
 ["invokeCell","class InvokeCellEffect"],["staleVersion","STALE_VERSION"],
 ["budgetExhausted","BUDGET_EXHAUSTED"],["duplicateActivation","DUPLICATE_ACTIVATION"],
 ["unknownCell","UNKNOWN_CELL"],["inputTypeMismatch","INPUT_TYPE_MISMATCH"],
 ["unknownActivation","UNKNOWN_ACTIVATION"],["outputTypeMismatch","OUTPUT_TYPE_MISMATCH"],
 ["def decide","def decide("],["def evolve","def evolve("],["def effects","def effects("],["def replay","def replay("]
] as const)
export const FORMAL_OUTBOX_PARITY = Object.freeze([
 ["pending","PENDING","pending"],["inFlight","IN_FLIGHT","in_flight"],
 ["unknownOutcome","UNKNOWN_OUTCOME","unknown_outcome"],["succeeded","SUCCEEDED","succeeded"],
 ["failedPermanent","FAILED_PERMANENT","failed_permanent"]
] as const)
export const FORMAL_FAULT_GATES: readonly string[] = Object.freeze([
 "atomic_request_event_and_outbox","pending_outbox_recovers_after_reopen","single_claim_under_competition",
 "unknown_outcome_is_not_auto_retried","completion_event_and_outbox_success_are_atomic","exact_command_retry_adds_no_event",
 "same_key_different_intent_is_rejected","same_history_has_stable_digest","typed_cell_port_completes"
])
export const FORMAL_DURABLE_PREREG="_research/hswm_cellular_runtime/PREREG_HSWM_CELLULAR_DURABLE_RUNTIME_V2_2026-07-26.json"
export const FORMAL_DURABLE_RECEIPT="receipts/HSWM_CELLULAR_DURABLE_RUNTIME_VALIDATION_20260726.json"
export const FORMAL_EXTRA_PATHS: Readonly<Record<NativeFormalVerifier,readonly string[]>> = Object.freeze({
 "canonical-permit-vector":Object.freeze([]),"cellular-longinus":Object.freeze([]),
 "cellular-runtime-longinus":Object.freeze(["formal/HSWMRuntime.lean","hswm_cellular_runtime.py"]),
 "durable-runtime-longinus":Object.freeze(["formal/HSWMDurableRuntime.lean","hswm_cellular_store.py","_research/hswm_cellular_runtime/outbox_fsm.v1.json",FORMAL_DURABLE_PREREG,FORMAL_DURABLE_RECEIPT])
})
const truthy=(value:GeneralJson|undefined):boolean=>value!==undefined&&value!==null&&value!==false&&value!==0&&value!==""&&(!Array.isArray(value)||value.length>0)&&(!record(value)||Object.keys(value).length>0)
const validateLonginusExecutionContracts=(kind:"cellular-runtime-longinus"|"durable-runtime-longinus",read:NativeFormalRead):Either.Either<Readonly<Record<string,GeneralJson>>,NativeFormalVerifierError>=>Either.gen(function*(){
 const readText=(path:string)=>Either.flatMap(read(path),text)
 const readJson=(path:string)=>Either.flatMap(read(path),json)
 if(kind==="cellular-runtime-longinus"){
  const lean=yield* readText("formal/HSWMRuntime.lean"),python=yield* readText("hswm_cellular_runtime.py")
  for(const [lt,pt]of FORMAL_RUNTIME_SYMBOL_PAIRS){if(!lean.includes(lt))return yield* fail(`Lean parity token missing: ${JSON.stringify(lt)}`);if(!python.includes(pt))return yield* fail(`Python parity token missing: ${JSON.stringify(pt)}`)}
  return {schema:"hswm-cellular-runtime-longinus-verification/v1",symbol_pairs_checked:FORMAL_RUNTIME_SYMBOL_PAIRS.length,claim_boundary:"Local hashes, ranges, symbols, and layer declarations only; not a KG write or scientific verdict."}
 }
 const lean=yield* readText("formal/HSWMDurableRuntime.lean"),python=yield* readText("hswm_cellular_store.py"),fsm=yield* readJson("_research/hswm_cellular_runtime/outbox_fsm.v1.json")
 const fsmText=JSON.stringify(fsm)
 for(const [lt,pt,ft]of FORMAL_OUTBOX_PARITY){if(!lean.includes(lt))return yield* fail(`Lean outbox token missing: ${JSON.stringify(lt)}`);if(!python.includes(pt))return yield* fail(`Python outbox token missing: ${JSON.stringify(pt)}`);if(!fsmText.includes(ft))return yield* fail(`FSM outbox token missing: ${JSON.stringify(ft)}`)}
 const prereg=yield* readJson(FORMAL_DURABLE_PREREG)
 if(!record(prereg)||prereg["registered_before_implementation"]!==true)return yield* fail("preregistration ordering claim is absent")
 const judge=prereg["locked_judge"]
 if(!record(judge)||typeof judge["path"]!=="string"||sha(yield* read(judge["path"]))!==judge["sha256"])return yield* fail("locked judge SHA-256 drift")
 const receipt=yield* readJson(FORMAL_DURABLE_RECEIPT)
 if(!record(receipt)||receipt["schema"]!==judge["receipt_schema"])return yield* fail("receipt schema does not match preregistration")
 const gates=receipt["fault_gates"]
 if(!record(gates)||Object.keys(gates).length!==FORMAL_FAULT_GATES.length||!FORMAL_FAULT_GATES.every(key=>Object.hasOwn(gates,key)))return yield* fail("receipt fault-gate field set drift")
 if(!Object.values(gates).every(truthy))return yield* fail("one or more preregistered fault gates failed")
 const probes=prereg["allowed_model_probe"]
 if(!Array.isArray(probes)||!probes.includes(receipt["model_probe"]??null))return yield* fail("receipt model probe is not preregistered")
 if(receipt["scientific_status"]!=="UNJUDGED")return yield* fail("engineering receipt overclaims scientific status")
 return {schema:"hswm-cellular-durable-runtime-longinus-verification/v1",outbox_symbol_pairs_checked:FORMAL_OUTBOX_PARITY.length,fault_gates_checked:FORMAL_FAULT_GATES.length,scientific_status:"UNJUDGED",claim_boundary:"Local hashes, ranges, contracts, symbols, preregistration, and receipt only; not a KG write or HSWM scientific verdict."}
})
const canonicalPermit=(read:NativeFormalRead):Either.Either<Readonly<Record<string,GeneralJson>>,NativeFormalVerifierError>=>{
 const raw=read("src/hswm/effect-runtime/test/fixtures/canonical-permit-envelope-v1.vector.json");if(Either.isLeft(raw))return fail(raw.left.detail)
 const v=decodeCanonicalJsonBytes(raw.right);if(Either.isLeft(v)||!record(v.right))return fail("vector root is not a restricted canonical JSON object")
 const vector=v.right, signing=base64url(vector["signingDocumentCanonicalBase64Url"],"signingDocumentCanonicalBase64Url"), envelope=base64url(vector["envelopeCanonicalBase64Url"],"envelopeCanonicalBase64Url"), key=base64url(vector["publicKeySpkiDerBase64Url"],"publicKeySpkiDerBase64Url")
 if(Either.isLeft(signing))return fail(signing.left.detail);if(Either.isLeft(envelope))return fail(envelope.left.detail);if(Either.isLeft(key))return fail(key.left.detail)
 if(vector["schema"]!=="hswm-canonical-permit-envelope-test-vector/v1"||string(vector["signingDocumentSha256"])!=="985d0156c0687de5d3e2a908c93c9aa098932afda9673925e5478dde4ff59c80"||string(vector["envelopeSha256"])!=="66af55c2437da2394450bc985f2979176cf44c6b6443a1886c8ed142bc83ed9a")return fail("unexpected or unpinned vector")
 if(vector["publicKeySpkiDerBase64Url"]!=="MCowBQYDK2VwAyEA11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"||vector["expectedVerificationStatus"]!=="CALLER_RELATIVE_BINDINGS_TRUST_AND_TIME_ENVELOPE_VERIFIED_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_LEARNING")return fail("vector public key or nonclaim differs from the fixed vector")
 if(sha(signing.right)!==vector["signingDocumentSha256"]||sha(envelope.right)!==vector["envelopeSha256"])return fail("pinned SHA-256 mismatch")
 const sd=json(signing.right),ev=json(envelope.right);if(Either.isLeft(sd)||Either.isLeft(ev)||!record(ev.right))return fail("canonical document is not JSON object")
 const sc=canonicalJsonBytes(sd.right),ec=canonicalJsonBytes(ev.right);if(Either.isLeft(sc)||Either.isLeft(ec)||!Buffer.from(sc.right).equals(signing.right)||!Buffer.from(ec.right).equals(envelope.right))return fail("document is not independently canonical")
 const {signature,...unsigned}=ev.right;const sig=base64url(signature,"signature");if(Either.isLeft(sig)||sig.right.byteLength!==64)return fail("Ed25519 signature is not 64 bytes");const uc=canonicalJsonBytes(unsigned);if(Either.isLeft(uc)||!Buffer.from(uc.right).equals(signing.right))return fail("envelope does not reconstruct the pinned signing document")
 const verified=Either.try({try:()=>verify(null,signing.right,{key:Buffer.from(key.right),format:"der",type:"spki"},sig.right),catch:()=>new NativeFormalVerifierError({detail:"Ed25519 verification failed"})});if(Either.isLeft(verified))return fail(verified.left.detail);if(!verified.right)return fail("Ed25519 rejected")
 return Either.right({cryptoConsumer:"node:crypto",envelopeSha256:sha(envelope.right),schema:"hswm-canonical-permit-envelope-fixed-vector-replay/v1",scope:"FIXED_VECTOR_BYTES_SIGNATURE_AND_RESTRICTED_CANONICAL_JSON_ONLY",signatureAlgorithm:"Ed25519",signingDocumentSha256:sha(signing.right),status:"FIXED_VECTOR_REPLAY_PASSED_NOT_GENERAL_SCHEMA_PERMIT_ADMISSION_OR_LEARNING_VERIFIER"})
}
const longinus=(kind:Exclude<NativeFormalVerifier,"canonical-permit-vector">,read:NativeFormalRead):Either.Either<Readonly<Record<string,GeneralJson>>,NativeFormalVerifierError>=>{
 const names={"cellular-longinus":"LONGINUS_HSWM_CELLULAR_DEFINITION_BINDING_2026-07-26.json","cellular-runtime-longinus":"LONGINUS_HSWM_CELLULAR_RUNTIME_BINDING_2026-07-26.json","durable-runtime-longinus":"LONGINUS_HSWM_DURABLE_RUNTIME_BINDING_2026-07-26.json"} as const
 const raw=read(names[kind]);if(Either.isLeft(raw))return fail(raw.left.detail);const parsed=json(raw.right);if(Either.isLeft(parsed)||!record(parsed.right))return fail("manifest is not an object");const m=parsed.right
 const layers=list(m["layers"]);if(layers===null||new Set(layers).size!==REQUIRED_LAYERS.length||!layers.every(x=>typeof x==="string"&&REQUIRED_LAYERS.includes(x)))return fail(kind==="cellular-longinus"?"seven-layer contract is incomplete or changed":"seven-layer declaration is incomplete or changed")
 const kg=m["kg"];if(!record(kg)||kg["write_state"]!=="NOT_AUTHORIZED_NOT_WRITTEN")return fail("local verifier refuses a manifest claiming a KG write")
 const bindings=list(m["bindings"]);if(bindings===null)return fail("bindings missing");const ids:string[]=[];const states=new Map<string,number>();const files=new Set<string>()
 for(const item of bindings){if(!record(item))return fail("binding is not an object");const id=string(item["sourceId"]),path=string(item["source_path"]),expected=string(item["sha256_baseline"]),declared=string(item["sha256"]),range=string(item["line_range"]),token=string(item["symbol_token"]);if(id===null||path===null||expected===null||declared===null||range===null||token===null)return fail("binding fields missing");if(ids.includes(id))return fail(`duplicate sourceId values: ${JSON.stringify([id])}`);ids.push(id);const source=read(path);if(Either.isLeft(source))return fail(`missing source: ${path}`);const actual=sha(source.right);if(actual!==expected||declared!==expected)return fail(`sha256 drift: ${id} expected=${expected} actual=${actual}`);const sourceText=text(source.right);if(Either.isLeft(sourceText))return fail(sourceText.left.detail);const r=parseRange(range);if(Either.isLeft(r))return fail(r.left.detail);const lines=pythonSplitLines(sourceText.right);if(r.right[1]>lines.length)return fail(`line range outside file: ${id} end=${r.right[1]} lines=${lines.length}`);if(!lines.slice(r.right[0]-1,r.right[1]).join("\n").includes(token))return fail(`symbol token absent${kind==="cellular-longinus"?" from bound range":""}: ${id} token=${JSON.stringify(token)}`);const state=string(item["binding_state"]);if(state!==null)states.set(state,(states.get(state)??0)+1);files.add(path)}
 const required=kind==="cellular-longinus"?["EXACT","STRUCTURAL_EXACT","PARTIAL_MATERIALIZATION","CONFOUNDED_EVIDENCE","UNPROVEN_CONDITION"]:["EXACT","STRUCTURAL_EXACT","PARTIAL_MATERIALIZATION","ENGINEERING_ONLY"];if(!required.every(s=>states.has(s)))return fail(kind==="cellular-longinus"?"binding states fail to expose all definition/runtime gaps":"required binding-state diversity missing")
 const result:Record<string,GeneralJson>={binding_id:m["binding_id"]??null,kg_write_state:"NOT_AUTHORIZED_NOT_WRITTEN",layers:layers.length,status:"PASS",states:Object.fromEntries([...states.entries()].sort(([a],[b])=>a.localeCompare(b)))}
 if(kind==="cellular-longinus")return Either.right({...result,schema:"hswm-cellular-longinus-verification/v1",checked:ids.length})
 const detail=validateLonginusExecutionContracts(kind,read);return Either.isLeft(detail)?fail(detail.left.detail):Either.right({...result,...detail.right,bindings_checked:ids.length,files_checked:files.size})
}
export const verifyNativeFormal=(kind:NativeFormalVerifier,read:NativeFormalRead):Either.Either<Readonly<Record<string,GeneralJson>>,NativeFormalVerifierError>=>kind==="canonical-permit-vector"?canonicalPermit(read):longinus(kind,read)
