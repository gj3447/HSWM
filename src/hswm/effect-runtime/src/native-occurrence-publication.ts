/** Deterministic, non-promoting RO-Crate 1.3 and OpenLineage projections. */
import { Data, Either } from "effect"
import { createHash } from "node:crypto"
import { canonicalJsonBytes, canonicalJsonSha256 } from "./canonical-atom-v2-json.js"
import { isNativeQualifiedExternalAudit, type NativeQualifiedExternalAudit } from "./native-occurrence-audit-runtime.js"
import { nativeCompletionReceiptCanonical, type NativeIssuedCompletionReceipt } from "./native-occurrence-completion-domain.js"

export const HSWM_NATIVE_OCCURRENCE_PUBLICATION_V1 = "hswm-native-occurrence-publication/v1" as const
export const HSWM_NATIVE_OCCURRENCE_PUBLICATION_CLAIM_CEILING = "PUBLICATION_PROJECTION_ONLY_NOT_CANONICAL_NOT_OUTCOME_TRUTH_NOT_G0_NOT_G1_NOT_PERMIT_NOT_CAUSAL_CREDIT_NOT_LEARNING" as const
export const HSWM_OPENLINEAGE_RUN_EVENT_SCHEMA = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent" as const
export const HSWM_RO_CRATE_VERSION = "1.3" as const
export const HSWM_ARTIFACT_FACET_SCHEMA_URL = "https://raw.githubusercontent.com/gj3447/HSWM/6108410a90f5caf8b367bb1fce5282c96744d24e/schemas/hswm_openlineage_artifact_facet.v1.schema.json" as const
export const HSWM_PUBLICATION_FACET_SCHEMA_URL = "https://raw.githubusercontent.com/gj3447/HSWM/6108410a90f5caf8b367bb1fce5282c96744d24e/schemas/hswm_openlineage_occurrence_publication_facet.v1.schema.json" as const
export const HSWM_PUBLICATION_CLAIM_BOUNDARY = "publication projection only; non-canonical, non-promoting, not an HSWM atom, Permit, outcome owner, evaluator, causal-credit path, or G0 evidence" as const
const TERM = `${HSWM_PUBLICATION_FACET_SCHEMA_URL}#`
const digest = /^[0-9a-f]{64}$/u
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.trim() === v && !v.includes("\0")

export type NativeOccurrenceTerminal = "SEALED" | "VOID"
export interface NativeOccurrenceArtifact { readonly path:string; readonly sha256:string; readonly bytes:number; readonly mediaType?:string; readonly role?:string }
export class NativeOccurrencePublicationError extends Data.TaggedError("NativeOccurrencePublicationError")<{ readonly code:"INPUT_INVALID"|"AUDIT_MISSING"|"AUDIT_FOR_VOID"|"ARTIFACT_INVALID"|"RECEIPT_INVALID"; readonly detail:string }> {}
const fail=<A=never>(code:NativeOccurrencePublicationError["code"],detail:string):Either.Either<A,NativeOccurrencePublicationError>=>Either.left(new NativeOccurrencePublicationError({code,detail}))
export const validateNativeOccurrenceArtifact=(v:unknown):Either.Either<NativeOccurrenceArtifact,NativeOccurrencePublicationError>=>{
 if(typeof v!=="object"||v===null||Array.isArray(v))return fail("ARTIFACT_INVALID","artifact must be an object");const r=v as Record<string,unknown>
 if(!Object.keys(r).every(key=>["path","sha256","bytes","media_type","mediaType","role"].includes(key))||Object.hasOwn(r,"media_type")&&Object.hasOwn(r,"mediaType"))return fail("ARTIFACT_INVALID","artifact fields are not exact")
 const media=r["media_type"]??r["mediaType"];if(!text(r["path"])||r["path"].startsWith("/")||r["path"].startsWith("../")||r["path"].includes("/../")||r["path"]==="."||r["path"]===".."||r["path"].includes("//")||r["path"].includes("\\")||/[\x00-\x1f\x7f]/u.test(r["path"])||typeof r["sha256"]!=="string"||!digest.test(r["sha256"])||typeof r["bytes"]!=="number"||!Number.isSafeInteger(r["bytes"])||r["bytes"]<0||(media!==undefined&&!text(media))||(r["role"]!==undefined&&!text(r["role"])))return fail("ARTIFACT_INVALID","artifact fields are invalid")
 return Either.right(Object.freeze({path:r["path"],sha256:r["sha256"],bytes:r["bytes"],...(media===undefined?{}:{mediaType:media}),...(r["role"]===undefined?{}:{role:r["role"]})}))
}

interface PublicationReceipt extends NativeIssuedCompletionReceipt { readonly externalAudit: NativeQualifiedExternalAudit | null; readonly receiptArtifact: NativeOccurrenceArtifact }

export interface NativeOccurrencePublication { readonly claimCeiling:typeof HSWM_NATIVE_OCCURRENCE_PUBLICATION_CLAIM_CEILING;readonly scopeSha256:string;readonly roCrate:Readonly<Record<string,unknown>>;readonly openLineage:Readonly<{readonly start:Readonly<Record<string,unknown>>;readonly terminal:Readonly<Record<string,unknown>>}> }
const compareCodePoints=(left:string,right:string):number=>{const a=Array.from(left),b=Array.from(right);for(let i=0;i<Math.min(a.length,b.length);i++){const x=a[i]!.codePointAt(0)!,y=b[i]!.codePointAt(0)!;if(x!==y)return x-y}return a.length-b.length}
const exactRequired=(artifacts:ReadonlyArray<NativeOccurrenceArtifact>,expected:ReadonlyArray<NativeOccurrenceArtifact>):Either.Either<ReadonlyArray<NativeOccurrenceArtifact>,NativeOccurrencePublicationError>=>{
 const normalized:NativeOccurrenceArtifact[]=[];for(const item of artifacts){const checked=validateNativeOccurrenceArtifact(item);if(Either.isLeft(checked))return Either.left(checked.left);normalized.push(checked.right)}
 if(normalized.length===0||new Set(normalized.map((x)=>x.path)).size!==normalized.length)return fail("ARTIFACT_INVALID","artifact paths must be unique and non-empty")
 for(const wanted of expected){const matches=normalized.filter((x)=>x.sha256===wanted.sha256);if(matches.length!==1||matches[0]?.bytes!==wanted.bytes||matches[0]?.mediaType!==wanted.mediaType||matches[0]?.role!==wanted.role)return fail("ARTIFACT_INVALID","replay-verified artifact descriptor differs from exact bytes")}
 return Either.right(Object.freeze([...normalized].sort((a,b)=>compareCodePoints(a.path,b.path))))
}
const runId=(uidValue:string,receipt:string):string=>{
 const namespace=Uint8Array.from([0x6b,0xa7,0xb8,0x11,0x9d,0xad,0x11,0xd1,0x80,0xb4,0x00,0xc0,0x4f,0xd4,0x30,0xc8])
 const bytes=Buffer.from(createHash("sha1").update(namespace).update(`${uidValue}\0${receipt}`,"utf8").digest().subarray(0,16));bytes[6]=(bytes[6]!&0x0f)|0x50;bytes[8]=(bytes[8]!&0x3f)|0x80
 const hex=bytes.toString("hex");return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
const projectNativeOccurrencePublication=(receipt:PublicationReceipt,artifacts:ReadonlyArray<NativeOccurrenceArtifact>,producer="https://github.com/gj3447/HSWM"):Either.Either<NativeOccurrencePublication,NativeOccurrencePublicationError>=>{
 if(!text(producer)||!/^https:\/\/[^/?#@]+(?:\/[^?#]*)?$/u.test(producer))return fail("INPUT_INVALID","producer must be credential-free HTTPS URI")
 const expected=receipt.externalAudit===null?[receipt.receiptArtifact]:[receipt.receiptArtifact,receipt.externalAudit.publicationArtifact]
 const entries=exactRequired(artifacts,expected);if(Either.isLeft(entries))return Either.left(entries.left)
 const terminalReceipt={occurrence_uid:receipt.occurrenceUid,terminal_status:receipt.terminalStatus,started_at:receipt.startedAt,terminal_at:receipt.terminalAt,receipt_sha256:receipt.receiptSha256,external_audit_verification_sha256:receipt.externalAudit?.verificationSha256??null}
 const scopeArtifacts=entries.right.map(item=>Object.freeze({path:item.path,sha256:item.sha256,bytes:item.bytes,...(item.mediaType===undefined?{}:{media_type:item.mediaType}),...(item.role===undefined?{}:{role:item.role})}))
 const scope=canonicalJsonSha256({artifacts:scopeArtifacts,terminalReceipt});if(Either.isLeft(scope))return fail("INPUT_INVALID","publication scope cannot canonicalize")
 const scopeSha256=scope.right
 const root={"@id":"./","@type":"Dataset",conformsTo:{"@id":"https://w3id.org/ro/crate/1.3"},hasPart:entries.right.map((x)=>({"@id":x.path})),[`${TERM}claimBoundary`]:HSWM_PUBLICATION_CLAIM_BOUNDARY,[`${TERM}occurrenceUid`]:receipt.occurrenceUid,[`${TERM}receiptSha256`]:receipt.receiptSha256,[`${TERM}externalAuditVerificationSha256`]:terminalReceipt.external_audit_verification_sha256,[`${TERM}scopeSha256`]:scopeSha256,[`${TERM}terminalStatus`]:receipt.terminalStatus,datePublished:receipt.terminalAt,description:"Terminal HSWM occurrence publication projection; its explicit receipt and artifact scope is identified by scopeSha256.",license:"No license is granted by this projection; the distributor must verify and declare the governing license for every artifact before public release.",name:`HSWM occurrence publication: ${receipt.occurrenceUid}`}
 const roCrate=Object.freeze({"@context":"https://w3id.org/ro/crate/1.3/context","@graph":[root,{"@id":"ro-crate-metadata.json","@type":"CreativeWork",about:{"@id":"./"},conformsTo:{"@id":"https://w3id.org/ro/crate/1.3"}},...entries.right.map((x)=>({"@id":x.path,"@type":"File",contentSize:String(x.bytes),[`${HSWM_ARTIFACT_FACET_SCHEMA_URL}#sha256`]:x.sha256,...(x.mediaType===undefined?{}:{encodingFormat:x.mediaType}),...(x.role===undefined?{}:{[`${HSWM_ARTIFACT_FACET_SCHEMA_URL}#artifactRole`]:x.role})}))]})
 const inputs=entries.right.map((x)=>({namespace:"hswm.artifact.sha256",name:x.sha256,facets:{hswmArtifact:{_producer:producer,_schemaURL:HSWM_ARTIFACT_FACET_SCHEMA_URL,bytes:x.bytes,path:x.path,sha256:x.sha256}}}))
 const common={schemaURL:HSWM_OPENLINEAGE_RUN_EVENT_SCHEMA,producer,job:{namespace:"hswm.occurrence.publication",name:receipt.occurrenceUid},inputs,outputs:[],run:{runId:runId(receipt.occurrenceUid,receipt.receiptSha256),facets:{hswmPublication:{_producer:producer,_schemaURL:HSWM_PUBLICATION_FACET_SCHEMA_URL,claimBoundary:HSWM_PUBLICATION_CLAIM_BOUNDARY,externalAuditVerificationSha256:terminalReceipt.external_audit_verification_sha256,receiptSha256:receipt.receiptSha256,terminalStatus:receipt.terminalStatus}}}}
 return Either.right(Object.freeze({claimCeiling:HSWM_NATIVE_OCCURRENCE_PUBLICATION_CLAIM_CEILING,scopeSha256,roCrate,openLineage:Object.freeze({start:Object.freeze({eventType:"START",eventTime:receipt.startedAt,...common}),terminal:Object.freeze({eventType:receipt.terminalStatus==="SEALED"?"COMPLETE":"FAIL",eventTime:receipt.terminalAt,...common})})}))
}

/** Pure projection over a completion-factory-issued value; replay authority stays above this boundary. */
export const projectNativeIssuedOccurrencePublication=(receipt:NativeIssuedCompletionReceipt,audit:NativeQualifiedExternalAudit|null,artifacts:ReadonlyArray<NativeOccurrenceArtifact>,producer="https://github.com/gj3447/HSWM"):Either.Either<NativeOccurrencePublication,NativeOccurrencePublicationError>=>{
 const canonical=nativeCompletionReceiptCanonical(receipt);if(Either.isLeft(canonical))return fail("RECEIPT_INVALID","publication requires completion-factory-issued receipt")
 if(receipt.terminalStatus!=="SEALED"&&receipt.terminalStatus!=="VOID")return fail("RECEIPT_INVALID","terminal_status must be SEALED or VOID")
 if(receipt.terminalStatus==="SEALED"&&(audit===null||!isNativeQualifiedExternalAudit(audit)||receipt.externalAuditVerificationSha256!==audit.verificationSha256))return fail("AUDIT_MISSING","SEALED receipt requires its verifier-issued audit")
 if(receipt.terminalStatus==="VOID"&&audit!==null)return fail("AUDIT_FOR_VOID","VOID receipt cannot claim external audit")
 const {receipt_sha256:_receiptSha256,...payload}=canonical.right;const bytes=canonicalJsonBytes(payload);if(Either.isLeft(bytes))return fail("RECEIPT_INVALID","receipt payload cannot canonicalize")
 const artifact:NativeOccurrenceArtifact=Object.freeze({path:"occurrence-terminal-receipt.payload.json",sha256:receipt.receiptSha256,bytes:bytes.right.byteLength,mediaType:"application/json",role:"terminal-receipt-payload"})
 return projectNativeOccurrencePublication(Object.freeze({...receipt,externalAudit:audit,receiptArtifact:artifact}),artifacts,producer)
}
