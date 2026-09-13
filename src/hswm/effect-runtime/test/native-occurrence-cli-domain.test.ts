import { createHash } from "node:crypto"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { describeNativeOccurrenceBytes, nativeCosignAttestArgv, nativeInTotoStatement, nativeRfcQueryArgv, nativeRfcVerifyArgv, nativeWorkflowOptions, nativeWormCommand, parseNativeDsse } from "../src/native-occurrence-cli-domain.js"

const encoder=new TextEncoder(), sha=(v:Uint8Array)=>createHash("sha256").update(v).digest("hex")
it("goldens describe, one-shot workflow options, and an in-toto statement",()=>{
 const bytes=encoder.encode("abc"),describe=describeNativeOccurrenceBytes(bytes,"text/plain"),workflow=nativeWorkflowOptions("occ-1"),statement=nativeInTotoStatement(bytes,"subject.txt","text/plain","https://example.test/predicate",encoder.encode('{"ok":true}'))
 expect(describe).toEqual(Either.right({byte_length:3,media_type:"text/plain",sha256:sha(bytes)}))
 expect(workflow).toEqual(Either.right({claim_boundary:"one-shot Temporal launch contract only; not execution, outcome truth, Permit, canonical admission, learning, or G0 evidence",workflow_id:"g0-occurrence/occ-1",workflow_id_reuse_policy:"REJECT_DUPLICATE",workflow_maximum_attempts:1,activity_maximum_attempts:1,replacement_round_allowed:false}))
 expect(Either.isRight(statement)).toBe(true);if(Either.isRight(statement))expect(statement.right).toEqual({_type:"https://in-toto.io/Statement/v1",predicate:{ok:true},predicateType:"https://example.test/predicate",subject:[{digest:{sha256:sha(bytes)},name:"subject.txt"}]})
})
it("goldens parse-dsse without claiming cryptographic verification",()=>{
 const payload=encoder.encode(`{"_type":"https://in-toto.io/Statement/v1","predicate":{},"predicateType":"p","subject":[{"digest":{"sha256":"${"a".repeat(64)}"},"name":"x"}]}`),envelope=encoder.encode(JSON.stringify({payloadType:"application/vnd.in-toto+json",payload:Buffer.from(payload).toString("base64"),signatures:[{keyid:"kid",sig:"AQ=="}]})),parsed=parseNativeDsse(envelope)
 expect(Either.isRight(parsed)).toBe(true);if(Either.isRight(parsed))expect(parsed.right).toMatchObject({cryptographically_verified:false,payload_sha256:sha(payload),predicate_type:"p",signature_count:1,signature_keyids:["kid"],subject_name:"x",subject_sha256:"a".repeat(64)})
})
it("rejects malformed predicate, noncanonical base64, duplicate signature keyids, and malformed descriptors",()=>{
 expect(Either.isLeft(nativeInTotoStatement(encoder.encode("x"),"n","text/plain","p",encoder.encode("[]")))).toBe(true)
 const bad=(payload:string,signatures:unknown[])=>parseNativeDsse(encoder.encode(JSON.stringify({payloadType:"application/vnd.in-toto+json",payload,signatures})))
 expect(Either.isLeft(bad("A",[{keyid:"k",sig:"AQ=="}]))).toBe(true)
 const payload=Buffer.from(`{"_type":"https://in-toto.io/Statement/v1","predicate":{},"predicateType":"p","subject":[{"digest":{"sha256":"${"a".repeat(64)}"},"name":"x"}]}`).toString("base64")
 expect(Either.isLeft(bad(payload,[{keyid:"k",sig:"AQ=="},{keyid:"k",sig:"AQ=="}]))).toBe(true)
 expect(Either.isLeft(describeNativeOccurrenceBytes(encoder.encode("x"),""))).toBe(true)
})
it("matches Python non-executing WORM, Cosign, and RFC3161 argv contracts",()=>{
 const worm=nativeWormCommand(encoder.encode('{"x":1}'),"/tmp/claim.json","hswm-occurrence.example","occurrence-001","2027-09-03T00:00:00Z","111111111111","222222222222")
 expect(Either.isRight(worm)).toBe(true);if(Either.isRight(worm))expect(worm.right["argv"]).toEqual(["aws","s3api","put-object","--bucket","hswm-occurrence.example","--key","occurrences/occurrence-001/claim.json","--body","/tmp/claim.json","--if-none-match","*","--checksum-algorithm","SHA256","--checksum-sha256",Buffer.from(sha(encoder.encode('{"x":1}')),"hex").toString("base64"),"--object-lock-mode","COMPLIANCE","--object-lock-retain-until-date","2027-09-03T00:00:00Z","--expected-bucket-owner","222222222222","--no-cli-pager"])
 expect(nativeCosignAttestArgv("cosign","/b","/s","/o")).toEqual(Either.right(["cosign","attest-blob","--statement","/s","--bundle","/o","--yes","/b"]))
 expect(nativeRfcQueryArgv("openssl","/b","/r")).toEqual(Either.right(["openssl","ts","-query","-data","/b","-sha256","-cert","-out","/r"]))
 expect(nativeRfcVerifyArgv("openssl","/r","/p","/ca","/u")).toEqual(Either.right(["openssl","ts","-verify","-queryfile","/r","-in","/p","-CAfile","/ca","-untrusted","/u"]))
 expect(Either.isLeft(nativeWormCommand(encoder.encode("x"),"x","bad","uid","x","1","1"))).toBe(true)
})
