import { spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { existsSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Exit } from "effect"

import { admissionPreflightAdapterFacts, type AdmissionPreflightInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-admission-preflight.js"
import { canonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import {
  HSWM_LOCAL_PERMIT_COMMIT_STATUS,
  HSWM_LOCAL_PERMIT_COMMIT_V1,
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitVerifierContext,
  makeVerifiedAdmissionCommitBackend,
  type LocalPermitIssuer,
  type VerifiedAdmissionPreflight
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.js"

const clock = (): Date => new Date("2026-10-07T00:00:00.000Z")
const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const hex = (digit: string): string => digit.repeat(64)
const initial = Uint8Array.from(Buffer.from("admission-preflight:zero"))
const next = Uint8Array.from(Buffer.from("admission-preflight:one"))
const third = Uint8Array.from(Buffer.from("admission-preflight:two"))
const head = (sequence: number, state: Uint8Array, record: string) => ({
  lineageId: "lineage:admission-preflight", sequence, stateDigest: digest(state), recordDigest: hex(record)
})
const minted = (issuer: LocalPermitIssuer): string => {
  const nonce = issuer.mintNonce()
  if (nonce._tag === "Left") throw nonce.left
  return nonce.right.nonceDigest
}
const issue = (issuer: LocalPermitIssuer, prior: ReturnType<typeof head>, post: Uint8Array, suffix: string) =>
  issuer.issue({
    permitId: `permit:admission-preflight-${suffix}`, executionId: `execution:admission-preflight-${suffix}`,
    executionIntentDigest: hex("3"), permitDigest: hex("4"), proposalDigest: hex("5"), transitionInvariantDigest: hex("6"),
    priorHead: prior, expectedNextHead: head(prior.sequence + 1, post, suffix),
    target: { schemaVersion: "schema:admission-preflight", lineageId: "lineage:target", atomUid: "atom:target" },
    expectedRevision: `revision:${prior.sequence}`, candidateRevision: `revision:${prior.sequence + 1}`,
    authorizationRef: "authorization:admission-preflight", scope: "scope:admission-preflight",
    nonceDigest: minted(issuer), linearizationIndex: prior.sequence + 1
  }, 60_000)

const inputOf = (preflight: VerifiedAdmissionPreflight): AdmissionPreflightInput => ({
  view: preflight.view, record: preflight.record, verifiedPermit: preflight.verifiedPermit,
  preState: preflight.preState, postState: preflight.postState
})
const clone = (input: AdmissionPreflightInput): AdmissionPreflightInput => structuredClone(input)
const formalInput = (input: AdmissionPreflightInput): Record<string, unknown> => ({
  contract: "hswm-admission-preflight/v1",
  input: {
    view: input.view,
    record: { ...input.record, contractVersion: HSWM_LOCAL_PERMIT_COMMIT_V1, status: HSWM_LOCAL_PERMIT_COMMIT_STATUS },
    verifiedPermit: input.verifiedPermit, preState: input.preState, postState: input.postState
  }
})
const preflightCli = (): string => join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionPreflightCli")
const kernelCli = (): string => join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
const executeJson = (executable: string, value: unknown): Record<string, unknown> => {
  const encoded = canonicalJsonBytes(value)
  if (encoded._tag === "Left") throw encoded.left
  const result = spawnSync(executable, [], { input: encoded.right, encoding: "utf8", maxBuffer: 256 * 1024, timeout: 10000 })
  expect(result.error).toBeUndefined()
  expect(result.status).toBe(0)
  expect(result.stderr).toBe("")
  return JSON.parse(result.stdout) as Record<string, unknown>
}
const kernelWire = (preflight: VerifiedAdmissionPreflight): Record<string, unknown> => ({
  adapterFacts: preflight.adapterFacts,
  contractVersion: "hswm-verified-admission-wire/v1",
  record: { ...preflight.record, contractVersion: HSWM_LOCAL_PERMIT_COMMIT_V1, status: HSWM_LOCAL_PERMIT_COMMIT_STATUS },
  view: preflight.view
})

it.effect("captures native verified preflights and rejects invalid native Permit or state inputs before the hook", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-admission-preflight-"))
    try {
      const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:admission-preflight", authorizer: "principal:admission-preflight", policyVersion: "policy:admission-preflight", revocationEpoch: 0, clock })
      if (issuer._tag === "Left") throw issuer.left
      const verifier = makeLocalPermitVerifierContext(issuer.right.trustSnapshotBytes)
      if (verifier._tag === "Left") throw verifier.left
      const captured: VerifiedAdmissionPreflight[] = []
      const backend = makeVerifiedAdmissionCommitBackend(root, verifier.right, (preflight, mintApproval) =>
        Effect.sync(() => { captured.push(preflight); return mintApproval() }), clock)
      const first = issue(issuer.right, head(0, initial, "1"), next, "2")
      if (first._tag === "Left") throw first.left
      const firstReceipt = yield* backend.submit({ ...first.right, preStateBytes: initial, postStateBytes: next })
      const second = issue(issuer.right, firstReceipt.receipt.expectedNextHead, third, "3")
      if (second._tag === "Left") throw second.left
      yield* backend.submit({ ...second.right, preStateBytes: next, postStateBytes: third })

      expect(captured).toHaveLength(2)
      expect(captured.map(preflight => preflight.adapterFacts)).toEqual([
        { permitEnvelopeAccepted: true, stateBytesAccepted: true, verificationTimeAccepted: true },
        { permitEnvelopeAccepted: true, stateBytesAccepted: true, verificationTimeAccepted: true }
      ])
      expect(captured.map(preflight => preflight.adapterFacts)).toEqual(captured.map(preflight => admissionPreflightAdapterFacts(inputOf(preflight))))
      expect(captured[0]!.view).toEqual({ head: null, consumedNonces: [] })
      expect(captured[1]!.view).toEqual({ head: firstReceipt.receipt.expectedNextHead, consumedNonces: [firstReceipt.receipt.nonceDigest] })

      const invalidEnvelope = JSON.parse(Buffer.from(first.right.envelopeBytes).toString("utf8")) as { signature: string }
      invalidEnvelope.signature = `${invalidEnvelope.signature.startsWith("A") ? "B" : "A"}${invalidEnvelope.signature.slice(1)}`
      const invalidPermit = canonicalJsonBytes(invalidEnvelope)
      if (invalidPermit._tag === "Left") throw invalidPermit.left
      expect(Exit.isFailure(yield* Effect.exit(backend.submit({ ...first.right, envelopeBytes: invalidPermit.right, preStateBytes: initial, postStateBytes: next })))).toBe(true)
      const thirdPermit = issue(issuer.right, captured[1]!.record.expectedNextHead, initial, "4")
      if (thirdPermit._tag === "Left") throw thirdPermit.left
      expect(Exit.isFailure(yield* Effect.exit(backend.submit({ ...thirdPermit.right, preStateBytes: next, postStateBytes: initial })))).toBe(true)
      expect(captured).toHaveLength(2)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
)

const semantic = process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1" ? it : it.skip
semantic("matches the preflight CLI and existing admission wire on captured production preflights and rejects each binding mutation", () =>
  Effect.runPromise(Effect.gen(function* () {
    expect(existsSync(preflightCli())).toBe(true)
    expect(existsSync(kernelCli())).toBe(true)
    const root = mkdtempSync(join(tmpdir(), "hswm-admission-preflight-semantic-"))
    try {
      const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:admission-preflight-semantic", authorizer: "principal:admission-preflight", policyVersion: "policy:admission-preflight", revocationEpoch: 0, clock })
      if (issuer._tag === "Left") throw issuer.left
      const verifier = makeLocalPermitVerifierContext(issuer.right.trustSnapshotBytes)
      if (verifier._tag === "Left") throw verifier.left
      const captured: VerifiedAdmissionPreflight[] = []
      const backend = makeVerifiedAdmissionCommitBackend(root, verifier.right, (preflight, mintApproval) => Effect.sync(() => {
        captured.push(preflight)
        return mintApproval()
      }), clock)
      const issued = issue(issuer.right, head(0, initial, "a"), next, "b")
      if (issued._tag === "Left") throw issued.left
      const first = yield* backend.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next })
      const second = issue(issuer.right, first.receipt.expectedNextHead, third, "c")
      if (second._tag === "Left") throw second.left
      yield* backend.submit({ ...second.right, preStateBytes: next, postStateBytes: third })
      expect(captured).toHaveLength(2)
      for (const preflight of captured) {
        const nativeInput = inputOf(preflight)
        const expectedFacts = admissionPreflightAdapterFacts(nativeInput)
        const formal = executeJson(preflightCli(), formalInput(nativeInput))
        const kernel = executeJson(kernelCli(), kernelWire(preflight))
        expect(formal).toEqual(expect.objectContaining({ adapterFacts: expectedFacts, decision: "accepted", constructedRecordMatches: true, foreignVerificationProved: false, jsonParserProved: false }))
        expect(formal["successor"]).toEqual(expect.objectContaining({ head: preflight.record.expectedNextHead, consumedNonces: [preflight.record.nonceDigest, ...preflight.view.consumedNonces] }))
        expect(kernel["decision"]).toBe("accepted")
        expect(kernel["successor"]).toEqual(formal["successor"])
      }

      const nativeInput = inputOf(captured[0]!)

      const mutations: ReadonlyArray<AdmissionPreflightInput> = [
        { ...clone(nativeInput), verifiedPermit: { ...nativeInput.verifiedPermit, envelopeDigest: hex("a") } },
        { ...clone(nativeInput), verifiedPermit: { ...nativeInput.verifiedPermit, checkedAt: "2026-10-07T00:00:01.000Z" } },
        { ...clone(nativeInput), preState: { ...nativeInput.preState, byteLength: 0 } },
        { ...clone(nativeInput), postState: { ...nativeInput.postState, sha256: hex("b") } },
        { ...clone(nativeInput), verifiedPermit: { ...nativeInput.verifiedPermit, nonceDigest: hex("c") } },
        { ...clone(nativeInput), verifiedPermit: { ...nativeInput.verifiedPermit, expectedNextHead: { ...nativeInput.verifiedPermit.expectedNextHead, sequence: nativeInput.verifiedPermit.expectedNextHead.sequence + 1 } } },
        { ...clone(nativeInput), record: { ...nativeInput.record, executionIntentDigest: hex("e") } },
        { ...clone(nativeInput), record: { ...nativeInput.record, nonceDigest: hex("e") } },
        { ...clone(nativeInput), record: { ...nativeInput.record, priorHead: { ...nativeInput.record.priorHead, recordDigest: hex("f") } } },
        { ...clone(nativeInput), record: { ...nativeInput.record, committedAt: "2026-10-07T00:00:01.000Z" } },
        { ...clone(nativeInput), record: { ...nativeInput.record, verificationTime: "2026-10-07T00:00:01.000Z" } },
        { ...clone(nativeInput), preState: { ...nativeInput.preState, byteLength: 1_048_577 } },
        { ...clone(nativeInput), postState: { ...nativeInput.postState, byteLength: 0 } },
        { ...clone(nativeInput), preState: { ...nativeInput.preState, sha256: hex("f") } },
        { ...clone(nativeInput), view: { ...nativeInput.view, consumedNonces: [nativeInput.record.nonceDigest] } },
        { ...clone(nativeInput), view: { ...nativeInput.view, head: nativeInput.record.expectedNextHead } }
      ]
      for (const mutation of mutations) {
        const response = executeJson(preflightCli(), formalInput(mutation))
        expect(response).toEqual(expect.objectContaining({ decision: "rejected", successor: null, foreignVerificationProved: false, jsonParserProved: false }))
        expect(response["adapterFacts"]).toEqual(admissionPreflightAdapterFacts(mutation))
      }
      // Internally consistent forged observations still satisfy the decoded
      // model. The projection is not an authenticated verification capability.
      const forged: AdmissionPreflightInput = { ...clone(nativeInput),
        verifiedPermit: { ...nativeInput.verifiedPermit, envelopeDigest: hex("f") },
        record: { ...nativeInput.record, envelopeDigest: hex("f") }
      }
      expect(executeJson(preflightCli(), formalInput(forged))["decision"]).toBe("accepted")
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  }))
)
