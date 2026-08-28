import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { validateDnrd5NineCallManifestBytes } from "../src/canonical-atom-v2-dnrd5-nine-call.js"
const desc = (b: Uint8Array) => ({ mediaType: "application/octet-stream", byteLength: b.byteLength, sha256: createHash("sha256").update(b).digest("hex") })
const utf8 = (s: string) => new TextEncoder().encode(s)
const json = (value: unknown) => { const result = canonicalJsonBytes(value); if (Either.isLeft(result)) throw new Error("fixture json"); return result.right }
const fixture = () => {
  const content: Record<string, Uint8Array> = {}; const blockId = "DNRD5-BLOCK-0001"
  const calls = ["PRE_OUTCOME_TRAJECTORY", ...Array(4).fill("REVISION_PROPOSAL"), ...Array(4).fill("FRESH_PROBE")].map((callClass, i) => {
    const callId = `call:${i}`, sessionId = `session:${i}`, workerId = `worker:${i}`, allowedFiles = utf8(`files:${i}`)
    const rng = utf8(`rng:${i}`), model = utf8(`model:${i}`), runtime = utf8(`runtime:${i}`), instruction = utf8(`instruction:${i}`)
    const inputs = callClass === "PRE_OUTCOME_TRAJECTORY" ? { publicTask: utf8(`task:${i}`), behaviorProjection: utf8(`behavior:${i}`) } : callClass === "REVISION_PROPOSAL" ? { sealedTrajectory: utf8(`trajectory:${i}`), assignedFeedback: utf8(`feedback:${i}`), revisionRequest: utf8(`revision:${i}`) } : { behaviorProjection: utf8(`behavior:${i}`), freshProbe: utf8(`fresh:${i}`) }
    const allowedBundle = json({ _tag: "Dnrd5AllowedInputBundle", callClass, ...Object.fromEntries(Object.entries(inputs).map(([key, value]) => [key, desc(value)])) })
    const projection = json({ _tag: "Dnrd5ModelRequestProjection", allowedInputBundle: desc(allowedBundle), blockId, callClass, callId, instruction: desc(instruction), model: desc(model), rng: desc(rng), runtime: desc(runtime), status: "MODEL_REQUEST_PROJECTION_ONLY" })
    const isolation = json({ allowedFileManifest: desc(allowedFiles), blockId, callClass, callId, freshSession: true, freshWorker: true, network: "DENIED", prefixCache: "DISABLED", previousSessionId: null, previousWorkerId: null, providerCache: "DISABLED", sessionId, undeclaredFiles: "DENIED", workerId })
    const roles = { rng, model, runtime, allowedBundle, instruction, request: projection, projection, response: utf8(`response:${i}`), isolation, allowedFiles, ...Object.fromEntries(Object.entries(inputs).map(([key, value]) => [`input:${key}`, value])) }
    for (const [key, value] of Object.entries(roles)) content[`${callId}:${key}`] = value
    return { callId, callClass, sessionId, workerId, privateBindingSha256: i.toString(16).padStart(64, "a"), rng: desc(rng), model: desc(model), runtime: desc(runtime), allowedInputBundle: desc(allowedBundle), instruction: desc(instruction), request: desc(projection), modelRequestProjection: desc(projection), response: desc(roles.response), isolation: desc(isolation), allowedFiles: desc(allowedFiles), retry: "NONE", resumed: false, cacheSubstitution: "DISABLED" }
  })
  const manifest: any = { _tag: "Dnrd5NineCallManifest", blockId, calls, contractVersion: "hswm-dnrd5-nine-call-integrity/v1", custodianScope: "PRIVATE_FORK_CALL_SLOT_BINDINGS", terminal: "CALLER_SUPPLIED_ATTESTATION_AND_CONTENT_NOT_OS_OR_PROVIDER_PROOF" }
  return { manifest, bytes: json(manifest), content }
}
it("accounts exact nine content-bound calls without claiming execution", () => { const x = fixture(); const result = validateDnrd5NineCallManifestBytes(x.bytes, x.content); expect(Either.isRight(result)).toBe(true); if (Either.isRight(result)) expect(result.right.status).toContain("NOT_EXECUTION") })
it("fails closed for ledger, retry/identity/RNG/request-response/leakage/isolation/content mutations", () => { const mutations: Array<(x:any)=>void> = [x=>x.manifest.calls.pop(), x=>x.manifest.calls.push(x.manifest.calls[0]), x=>x.manifest.calls[1].sessionId=x.manifest.calls[0].sessionId, x=>x.manifest.calls[1].retry="RETRY", x=>x.manifest.calls[1].rng=x.manifest.calls[2].rng, x=>x.manifest.calls[1].request=x.manifest.calls[2].response, x=>x.content["call:1:request"]=utf8("ACTIVE"), x=>x.content["call:1:isolation"]=utf8("{}"), x=>x.manifest.extra=true]; for (const mutate of mutations) { const x=fixture(); mutate(x); const b=canonicalJsonBytes(x.manifest); if (Either.isRight(b)) expect(Either.isLeft(validateDnrd5NineCallManifestBytes(b.right,x.content))).toBe(true) } })
it("rejects descriptor corruption, missing content, and noncanonical manifest bytes", () => { const x=fixture(); x.manifest.calls[0].response.sha256="0".repeat(64); let b=canonicalJsonBytes(x.manifest); if (Either.isRight(b)) expect(Either.isLeft(validateDnrd5NineCallManifestBytes(b.right,x.content))).toBe(true); const y=fixture(); delete y.content["call:0:model"]; expect(Either.isLeft(validateDnrd5NineCallManifestBytes(y.bytes,y.content))).toBe(true); expect(Either.isLeft(validateDnrd5NineCallManifestBytes(utf8(" {}"),y.content))).toBe(true) })
it("rejects exact sequence/private RNG/block/projection/bundle/isolation drift and freezes output", () => {
  const mutations: Array<(x: any) => void> = [
    x => { [x.manifest.calls[1], x.manifest.calls[5]] = [x.manifest.calls[5], x.manifest.calls[1]] },
    x => { x.manifest.blockId = "DNRD5-BLOCK-0000" },
    x => { x.manifest.calls[1].privateBindingSha256 = x.manifest.calls[0].privateBindingSha256 },
    x => { x.manifest.calls[1].rng = x.manifest.calls[0].rng },
    x => { x.content["call:1:projection"] = utf8("{}") },
    x => { x.content["call:1:allowedBundle"] = utf8(" {}") },
    x => { x.content["call:1:isolation"] = json({}) },
    x => { delete x.content["call:1:input:sealedTrajectory"] },
    x => { x.content["call:1:input:hiddenOutcome"] = utf8("forbidden") },
    x => { x.content["call:1:input:sealedTrajectory"] = x.content["call:2:input:sealedTrajectory"] },
    x => { x.content["unknown:input:hiddenOutcome"] = utf8("forbidden") },
    x => { x.manifest.calls[1].callId = `${x.manifest.calls[0].callId}:nested` }
  ]
  for (const mutate of mutations) { const x = fixture(); mutate(x); expect(Either.isLeft(validateDnrd5NineCallManifestBytes(json(x.manifest), x.content))).toBe(true) }
  const x = fixture(); const result = validateDnrd5NineCallManifestBytes(x.bytes, x.content)
  if (Either.isRight(result)) { x.manifest.calls[0].callId = "changed"; expect(result.right.manifest.calls[0]?.callId).toBe("call:0"); expect(Object.isFrozen(result.right.manifest.calls[0])).toBe(true) } else throw new Error("valid fixture rejected")

  const inherited = fixture()
  const inheritedContent = Object.create({ "hidden:outcome": utf8("forbidden") }) as Record<string, Uint8Array>
  Object.assign(inheritedContent, inherited.content)
  expect(Either.isLeft(validateDnrd5NineCallManifestBytes(inherited.bytes, inheritedContent))).toBe(true)

  const accessor = fixture()
  Object.defineProperty(accessor.content, "call:1:model", {
    enumerable: true,
    get: () => { throw new Error("validator must not invoke content accessors") }
  })
  expect(Either.isLeft(validateDnrd5NineCallManifestBytes(accessor.bytes, accessor.content))).toBe(true)
})
