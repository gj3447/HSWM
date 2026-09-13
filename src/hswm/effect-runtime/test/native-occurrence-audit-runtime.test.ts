import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"
import { createHash } from "node:crypto"
import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import { BoundedSubprocess, type BoundedSubprocessShape, type SubprocessObservation } from "../src/effect-bounded-subprocess.js"
import { PosixFileSystem, type PosixFileSystemShape } from "../src/effect-posix-filesystem.js"
import { NativePinnedVerifier, type NativePinnedVerifierShape } from "../src/native-pinned-verifier-runtime.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { nativeInstantMicroseconds } from "../src/native-instant-domain.js"
import { decodeNativeAuditQualification, NATIVE_OCCURRENCE_QUALIFICATION_PATH, NATIVE_OCCURRENCE_TOOLCHAIN_PATH, nativeQualifiedExternalAuditCanonical, validateNativeTemporalTerminalMaterial, verifyNativeAuditManifest, verifyQualifiedNativeExternalAudit } from "../src/native-occurrence-audit-runtime.js"

const checkout=resolve(import.meta.dirname,"../../../..")

it("refuses the checked-in BLOCKED qualification record", () => {
  const qualification = new Uint8Array(readFileSync(resolve(checkout, "_research/g0_occurrence/HSWM_G0_EXTERNAL_AUDIT_QUALIFICATION.v1.json")))
  const toolchain = new Uint8Array(readFileSync(resolve(checkout, "_research/g0_occurrence/HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json")))
  const result = decodeNativeAuditQualification(qualification, toolchain)
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left.code).toBe("QUALIFICATION_BLOCKED")
})

it("re-decodes raw qualification before any caller-supplied verifier material can run", async () => {
  const digest = "a".repeat(64)
  const result = await Effect.runPromiseExit(verifyQualifiedNativeExternalAudit({ manifestPath: "/manifest", bundlePath: "/bundle", manifestBytes: new Uint8Array(), bundleBytes: new Uint8Array(), rootBytes: new Uint8Array(), licenseBytes: new Uint8Array(), temporalReceiptBytes: new Uint8Array(), temporalHistoryBytes: new Uint8Array(), temporal: { occurrenceUid: "occ-1", candidateReceiptSha256: digest, workflowSha256: digest, workflowEvidenceSha256s: [digest], completionStartedAt: "2026-01-01T00:00:00Z", candidateTerminalAt: "2026-01-01T00:01:00Z", completionTerminalAt: "2026-01-01T00:02:00Z" }, crossBinding: { candidateReceiptSha256: digest, assessmentSha256: digest, assessmentChainSha256: digest, dualAssessmentSha256: digest, dualEvidenceSha256: digest, candidateWorkflowSha256: digest, terminalWorkflowSha256: digest, candidateEvidenceSha256s: [digest], terminalEvidenceSha256s: [digest], completionStartedAt: "2026-01-01T00:00:00Z", completionTerminalAt: "2026-01-01T00:02:00Z", qualificationSha256: digest, temporalHistoryExportSha256: digest, temporalTerminalReceiptSha256: digest }, cwd: process.cwd() }).pipe(Effect.provide(NodePosixServicesLive)))
  expect(result._tag).toBe("Failure")
})

it("rejects a structurally plausible but incomplete Temporal history and cross-binding forgery", () => {
  const h = (v: Uint8Array) => createHash("sha256").update(v).digest("hex")
  const history = { namespace: "n", workflow_id: "g0-occurrence/occ-1", run_id: "r", server_identity_sha256: "a".repeat(64), signal_authorization_binding_sha256: "b".repeat(64), events: [{}], first_event_id: 1, last_event_id: 1, started_at: "2026-01-01T00:00:00Z", completed_at: "2026-01-01T00:02:00Z" }
  const historyBytes = new TextEncoder().encode(JSON.stringify(history))
  const receipt = { history_export_sha256: h(historyBytes), occurrence_uid: "occ-1", workflow_id: "g0-occurrence/occ-1", workflow_type: "hswm_g0_occurrence_one_shot_workflow", terminal_phase: "SEALED", candidate_receipt_sha256: "c".repeat(64), workflow_sha256: "d".repeat(64), workflow_evidence_sha256s: ["e".repeat(64)], workflow_id_reuse_policy: "REJECT_DUPLICATE", workflow_maximum_attempts: 1, activity_maximum_attempts: 1, replacement_round_allowed: false, namespace: "n", run_id: "r", server_identity_sha256: "a".repeat(64), signal_authorization_binding_sha256: "b".repeat(64), history_event_count: 1, history_first_event_id: 1, history_last_event_id: 1, completed_at: "2026-01-01T00:02:00Z" }
  const input = { occurrenceUid: "occ-1", candidateReceiptSha256: "c".repeat(64), workflowSha256: "d".repeat(64), workflowEvidenceSha256s: ["e".repeat(64)], completionStartedAt: "2026-01-01T00:00:00Z", candidateTerminalAt: "2026-01-01T00:01:00Z", completionTerminalAt: "2026-01-01T00:03:00Z" }
  expect(Either.isLeft(validateNativeTemporalTerminalMaterial(new TextEncoder().encode(JSON.stringify(receipt)), historyBytes, input))).toBe(true)
  expect(Either.isLeft(validateNativeTemporalTerminalMaterial(new TextEncoder().encode(JSON.stringify({ ...receipt, run_id: "forged" })), historyBytes, input))).toBe(true)
})

it("requires byte-exact canonical signed manifests", () => {
  const fields = { a: "x", b: [1, 2] }
  const valid = new TextEncoder().encode('{"a":"x","b":[1,2]}')
  expect(Either.isRight(verifyNativeAuditManifest(fields, valid))).toBe(true)
  expect(Either.isLeft(verifyNativeAuditManifest(fields, new TextEncoder().encode('{"b":[1,2],"a":"x"}')))).toBe(true)
})

const temporalFixture=JSON.parse(readFileSync(resolve(checkout,"tests/fixtures/native_migration/occurrence_completion_v1/temporal-material.json"),"utf8")) as {receipt_json:string;history_json:string;input:import("../src/native-occurrence-audit-runtime.js").NativeTemporalAuditBindingInput;expected:{receiptSha256:string;historySha256:string}}
const canonical=(v:unknown):Uint8Array=>{const result=canonicalJsonBytes(v);if(Either.isLeft(result))throw new Error(result.left.code);return result.right}
const bytes=(v:string)=>new TextEncoder().encode(v)
it("accepts the complete source-pinned Python Temporal material and exact hashes",()=>{
 const result=validateNativeTemporalTerminalMaterial(bytes(temporalFixture.receipt_json),bytes(temporalFixture.history_json),temporalFixture.input)
 expect(Either.isRight(result)).toBe(true);if(Either.isRight(result))expect(result.right).toEqual(temporalFixture.expected)
})
it("rejects bound but malformed Temporal identity, history, and microsecond chronology",()=>{
 const receipt=JSON.parse(temporalFixture.receipt_json) as Record<string,unknown>,history=JSON.parse(temporalFixture.history_json) as Record<string,unknown>
 for(const patch of [{exporter_identity:""},{server_identity_sha256:"invalid"},{workflow_maximum_attempts:2},{replacement_round_allowed:true},{history_event_count:3},{run_id:"not-a-uuid"}])expect(Either.isLeft(validateNativeTemporalTerminalMaterial(canonical({...receipt,...patch}),bytes(temporalFixture.history_json),temporalFixture.input))).toBe(true)
 for(const patch of [{next_page_token:"more"},{retrieved_at:"2026-09-03T00:01:59.999999Z"},{retrieved_at:"2026-02-30T00:02:00Z"},{retrieved_at:"2026-09-03T00:02:00"},{events:[]}]){const changed=canonical({...history,...patch}),r=canonical({...receipt,history_export_sha256:createHash("sha256").update(changed).digest("hex")});expect(Either.isLeft(validateNativeTemporalTerminalMaterial(r,changed,temporalFixture.input))).toBe(true)}
 const late={...temporalFixture.input,candidateTerminalAt:"2026-09-03T00:02:00.000001Z"};expect(Either.isLeft(validateNativeTemporalTerminalMaterial(bytes(temporalFixture.receipt_json),bytes(temporalFixture.history_json),late))).toBe(true)
 const early={...temporalFixture.input,completionTerminalAt:"2026-09-03T00:01:59.999999Z"};expect(Either.isLeft(validateNativeTemporalTerminalMaterial(bytes(temporalFixture.receipt_json),bytes(temporalFixture.history_json),early))).toBe(true)
 expect(Either.isLeft(validateNativeTemporalTerminalMaterial(bytes(temporalFixture.receipt_json+"\n"),bytes(temporalFixture.history_json),temporalFixture.input))).toBe(true)
})
it("compares offset-bearing microseconds without millisecond truncation or calendar rollover",()=>{
 expect(nativeInstantMicroseconds("2026-09-03T00:00:00.000001Z")!-nativeInstantMicroseconds("2026-09-03T00:00:00Z")!).toBe(1n)
 expect(nativeInstantMicroseconds("0001-01-01T01:00:00+01:00")).toBe(nativeInstantMicroseconds("0001-01-01T00:00:00Z"))
 for(const value of ["2026-02-30T00:00:00Z","2026-09-03T00:00:00","0000-01-01T00:00:00Z","2026-09-03T00:00:00+24:00"])expect(nativeInstantMicroseconds(value)).toBe(null)
})

const object = (value: unknown): Readonly<Record<string, unknown>> => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("fixture object required")
  return value as Readonly<Record<string, unknown>>
}
const valueString = (value: Readonly<Record<string, unknown>>, key: string): string => {
  const found = value[key]
  if (typeof found !== "string") throw new Error(`fixture string ${key} required`)
  return found
}
const valueStrings = (value: Readonly<Record<string, unknown>>, key: string): readonly string[] => {
  const found = value[key]
  if (!Array.isArray(found) || !found.every(item => typeof item === "string")) throw new Error(`fixture strings ${key} required`)
  return found
}
const fixture = object(JSON.parse(readFileSync(resolve(checkout, "tests/fixtures/native_migration/occurrence_completion_v1/qualified-audit-original.v2.json"), "utf8")))
const virtualFiles = object(fixture["virtual_files"])
const virtual = (name: string): Uint8Array => new TextEncoder().encode(valueString(virtualFiles, name))
const qualified = object(JSON.parse(valueString(virtualFiles, "qualification.json")))
const cosign = object(qualified["cosign"])
const trustedRoot = object(qualified["trusted_root"])
const expectedAudit = object(fixture["expected"])
const signed = object(JSON.parse(valueString(virtualFiles, "audit-manifest.json")))
const terminalReceipt = object(JSON.parse(valueString(virtualFiles, "temporal-terminal.json")))
const noIo: PosixFileSystemShape = {
  identity: () => Effect.die("unexpected identity"), listDirectory: () => Effect.die("unexpected list"), realpath: () => Effect.die("unexpected realpath"), makeDirectory: () => Effect.die("unexpected mkdir"), syncDirectory: () => Effect.die("unexpected sync directory"), syncRegular: () => Effect.die("unexpected sync file"), writeExclusive: () => Effect.die("unexpected write"), linkNoReplace: () => Effect.die("unexpected link"), chmod: () => Effect.die("unexpected chmod"), unlinkIfPresent: () => Effect.die("unexpected unlink"),
  readRegularBounded: (path) => {
    const files = new Map<string, Uint8Array>([
      [NATIVE_OCCURRENCE_QUALIFICATION_PATH, virtual("qualification.json")], [NATIVE_OCCURRENCE_TOOLCHAIN_PATH, virtual("candidates.json")], [valueString(cosign, "path"), virtual("cosign")], [valueString(cosign, "license_path"), virtual("LICENSE")], [valueString(trustedRoot, "path"), virtual("root.json")], ["/audit-manifest.json", virtual("audit-manifest.json")], ["/bundle.json", virtual("bundle.json")]
    ])
    const bytes = files.get(path)
    return bytes === undefined ? Effect.die(`unexpected read ${path}`) : Effect.succeed({ bytes, device: 1, inode: 1 })
  }
}
const successful = (stdout: string, stderr = ""): SubprocessObservation => ({ exitCode: 0, signal: null, timedOut: false, outputTruncated: false, launchError: null, stdout: new TextEncoder().encode(stdout), stderr: new TextEncoder().encode(stderr) })
const auditSubprocess: BoundedSubprocessShape = { observe: command => Effect.succeed(command.argv.at(1) === "version" ? successful(valueString(cosign, "exact_version_output")) : successful(valueString(fixture, "verifier_stdout"), valueString(fixture, "verifier_stderr"))) }
const auditPinnedVerifier: NativePinnedVerifierShape = { verify: request => Effect.succeed(Object.freeze({ version: successful(request.expectedVersionOutput), verification: successful(valueString(fixture, "verifier_stdout"), valueString(fixture, "verifier_stderr")) })) }
const auditServices = Layer.merge(Layer.merge(Layer.succeed(PosixFileSystem, noIo), Layer.succeed(BoundedSubprocess, auditSubprocess)), Layer.succeed(NativePinnedVerifier, auditPinnedVerifier))

it("replays the full original qualified-audit service result and its canonical publication payload", async () => {
  const result = await Effect.runPromise(verifyQualifiedNativeExternalAudit({
    manifestPath: "/audit-manifest.json", bundlePath: "/bundle.json", manifestBytes: virtual("audit-manifest.json"), bundleBytes: virtual("bundle.json"), rootBytes: virtual("root.json"), licenseBytes: virtual("LICENSE"), temporalReceiptBytes: virtual("temporal-terminal.json"), temporalHistoryBytes: virtual("temporal-history-export.json"), cwd: "/",
    temporal: { occurrenceUid: valueString(terminalReceipt, "occurrence_uid"), candidateReceiptSha256: valueString(signed, "candidate_receipt_sha256"), workflowSha256: valueString(signed, "terminal_workflow_sha256"), workflowEvidenceSha256s: valueStrings(signed, "terminal_workflow_evidence_sha256s"), completionStartedAt: valueString(signed, "completion_started_at"), candidateTerminalAt: "2026-09-03T00:01:00Z", completionTerminalAt: valueString(signed, "completion_terminal_at") },
    crossBinding: { candidateReceiptSha256: valueString(signed, "candidate_receipt_sha256"), assessmentSha256: valueString(signed, "assessment_sha256"), assessmentChainSha256: valueString(signed, "assessment_chain_sha256"), dualAssessmentSha256: valueString(signed, "dual_assessment_sha256"), dualEvidenceSha256: valueString(signed, "dual_evidence_sha256"), candidateWorkflowSha256: valueString(signed, "candidate_workflow_sha256"), terminalWorkflowSha256: valueString(signed, "terminal_workflow_sha256"), candidateEvidenceSha256s: valueStrings(signed, "candidate_workflow_evidence_sha256s"), terminalEvidenceSha256s: valueStrings(signed, "terminal_workflow_evidence_sha256s"), completionStartedAt: valueString(signed, "completion_started_at"), completionTerminalAt: valueString(signed, "completion_terminal_at"), qualificationSha256: valueString(signed, "qualification_sha256"), temporalHistoryExportSha256: valueString(signed, "temporal_history_export_sha256"), temporalTerminalReceiptSha256: valueString(signed, "temporal_terminal_receipt_sha256") }
  }).pipe(Effect.provide(auditServices)))
  const canonical = nativeQualifiedExternalAuditCanonical(result)
  expect(Either.isRight(canonical)).toBe(true)
  if (Either.isRight(canonical)) expect(canonical.right).toEqual(expectedAudit)
  expect(result.verificationSha256).toBe(valueString(expectedAudit, "verification_sha256"))
  expect(result.publicationArtifact).toEqual({ path: "external-audit-verification.json", sha256: valueString(expectedAudit, "verification_sha256"), bytes: canonicalJsonBytes(result.canonicalPayload).pipe(Either.getOrThrow).byteLength, mediaType: "application/json", role: "external-audit-verification" })
})
