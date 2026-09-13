import { createHash } from "node:crypto"
import { Either } from "effect"
import { decodeGeneralJsonBytes, decodeGeneralJsonWithNumberLexemesBytes } from "./general-json-domain.js"
import { NativeOccurrenceCliError } from "./native-occurrence-cli-domain.js"

const fail=<A=never>(detail:string):Either.Either<A,NativeOccurrenceCliError>=>Either.left(new NativeOccurrenceCliError({detail}))
const object=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v)
const descriptor=(path:string,bytes:Uint8Array)=>Object.freeze({path,sha256:createHash("sha256").update(bytes).digest("hex"),bytes:bytes.byteLength})
const same=(a:Record<string,unknown>,b:Record<string,unknown>)=>a["path"]===b["path"]&&a["sha256"]===b["sha256"]&&a["bytes"]===b["bytes"]
const timestamp=(value:unknown,name:string):Either.Either<{readonly text:string;readonly microseconds:bigint},NativeOccurrenceCliError>=>{
 if(typeof value!=="string")return fail(`${name} must be an RFC 3339 timestamp`);const match=/^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?(Z|[+-]\d\d:\d\d)$/u.exec(value);if(match===null)return fail(`${name} must be an RFC 3339 timestamp`)
 const [year,month,day,hour,minute,second]=match.slice(1,7).map(Number),fraction=(match[7]??"").padEnd(6,"0"),zone=match[8]!;if(year!<1||(zone!=="Z"&&(Number(zone.slice(1,3))>23||Number(zone.slice(4,6))>59)))return fail(`${name} must be an RFC 3339 timestamp`);const check=new Date(0);check.setUTCFullYear(year!,month!-1,day!);check.setUTCHours(hour!,minute!,second!,0);if(check.getUTCFullYear()!==year||check.getUTCMonth()!==month!-1||check.getUTCDate()!==day||check.getUTCHours()!==hour||check.getUTCMinutes()!==minute||check.getUTCSeconds()!==second)return fail(`${name} must be an RFC 3339 timestamp`)
 const offset=zone==="Z"?0:(Number(zone.slice(1,3))*60+Number(zone.slice(4,6)))*(zone[0]==="+"?1:-1);return Either.right({text:value,microseconds:BigInt(check.getTime()-offset*60_000)*1_000n+BigInt(fraction||"0")})
}
const osf=(value:unknown,kind:"registration"|"file_metadata"|"file_download",id?:string):Either.Either<string,NativeOccurrenceCliError>=>{
 if(typeof value!=="string"||/^(?!https:\/\/)(?:)/u.test(value)||/[?#]/u.test(value)||/@/u.test(value))return fail(`${kind}_url must be an HTTPS canonical OSF URL`)
 const registration=/^https:\/(?:\/api\.osf\.io\/v2\/registrations\/([a-z0-9]{5})\/|\/osf\.io\/([a-z0-9]{5})\/)$/u.exec(value)
 const metadata=/^https:\/\/api\.osf\.io\/v2\/files\/[A-Za-z0-9_-]+\/$/u.test(value)
 const download=/^https:\/\/files\.osf\.io\/v1\/resources\/[A-Za-z0-9_-]+\/providers\/[A-Za-z0-9._-]+\/[A-Za-z0-9._~-]+$/u.test(value)
 if(kind==="registration"){const found=registration?.[1]??registration?.[2];return found===undefined||found!==id?fail("registration_url does not bind the registration identifier"):Either.right(value)}
 return kind==="file_metadata"&&metadata?Either.right(value):kind==="file_download"&&download?Either.right(value):fail(kind==="file_metadata"?"file_metadata_url must be an official OSF API v2 file URL":"file_download_url must be an official OSF WaterButler download URL")
}
export const nativeOsfReadback=(registrationBytes:Uint8Array,fileBytes:Uint8Array,expectedBytes:Uint8Array,readbackBytes:Uint8Array,registeredPath:string,readbackUrl:string,pulse:string):Either.Either<Readonly<Record<string,unknown>>,NativeOccurrenceCliError>=>{
 const registration=decodeGeneralJsonBytes(registrationBytes),file=decodeGeneralJsonWithNumberLexemesBytes(fileBytes)
 if(Either.isLeft(registration)||!object(registration.right)||Either.isLeft(file)||!object(file.right.value)||registeredPath.length===0||registeredPath.trim()!==registeredPath)return fail("OSF readback must be strict JSON objects")
 const rd=registration.right["data"],fd=file.right.value["data"];if(!object(rd)||rd["type"]!=="registrations"||typeof rd["id"]!=="string"||!/^[a-z0-9]{5}$/u.test(rd["id"])||!object(rd["attributes"])||!object(rd["links"]))return fail("OSF registration readback schema is invalid")
 if(!object(fd)||fd["type"]!=="files"||!object(fd["attributes"])||!object(fd["links"])||!object(fd["attributes"]["extra"])||!object((fd["attributes"]["extra"] as Record<string,unknown>)["hashes"]))return fail("OSF file readback schema is invalid")
 const rurl=osf(rd["links"]["self"],"registration",rd["id"]),furl=osf(fd["links"]["self"],"file_metadata"),durl=osf(fd["links"]["download"],"file_download"),observed=osf(readbackUrl,"file_download"),registered=timestamp(rd["attributes"]["date_registered"],"date_registered"),pulseAt=timestamp(pulse,"pulse_timestamp")
 if(Either.isLeft(rurl))return fail("OSF readback URL or timestamp is invalid");if(Either.isLeft(furl))return fail("OSF readback URL or timestamp is invalid");if(Either.isLeft(durl))return fail("OSF readback URL or timestamp is invalid");if(Either.isLeft(observed))return fail("OSF readback URL or timestamp is invalid");if(Either.isLeft(registered))return fail("OSF readback URL or timestamp is invalid");if(Either.isLeft(pulseAt))return fail("OSF readback URL or timestamp is invalid")
 if(durl.right!==observed.right)return fail("read_back_download_url must exactly match OSF file links.download")
 const hashes=(fd["attributes"]["extra"] as Record<string,unknown>)["hashes"] as Record<string,unknown>
 const api=Object.freeze({path:fd["attributes"]["name"],sha256:hashes["sha256"],bytes:fd["attributes"]["size"]})
 if(typeof api.path!=="string"||api.path.length===0||api.path.trim()!==api.path||!/^[0-9a-f]{64}$/u.test(String(api.sha256))||typeof api.bytes!=="number"||!Number.isSafeInteger(api.bytes)||api.bytes<0||!/^\d+$/u.test(file.right.numberLexemes["/data/attributes/size"]??""))return fail("OSF file descriptor is invalid")
 const expected=descriptor(registeredPath,expectedBytes),readback=descriptor(registeredPath,readbackBytes), apiDescriptor=api as Record<string,unknown>
 const withdrawn=rd["attributes"]["withdrawn"];if(typeof withdrawn!=="boolean")return fail("OSF registration readback withdrawn must be boolean")
 const mismatch=!same(expected,readback)||!same(apiDescriptor,readback), late=registered.right.microseconds>=pulseAt.right.microseconds
 const reason=mismatch?"PACKAGE_OR_READBACK_BYTES_DO_NOT_MATCH":withdrawn?"OSF_REGISTRATION_WITHDRAWN":late?"REGISTRATION_NOT_STRICTLY_BEFORE_PULSE":null
 return Either.right(Object.freeze({status:reason===null?"CANDIDATE_FOR_EXTERNAL_AUDIT":"VOID",claim_boundary:"read-only external-registration evidence boundary; not preregistration success, G0 evidence, HSWM canonical state, Permit, outcome authority, or causal-credit path",registration_id:rd["id"],registration_url:rurl.right,file_metadata_url:furl.right,file_download_url:durl.right,read_back_download_url:readbackUrl,registration_timestamp:registered.right.text,pulse_timestamp:pulseAt.right.text,withdrawn,expected_package:expected,api_file:api,read_back_bytes:readback,reason}))
}
