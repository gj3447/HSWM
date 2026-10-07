import { spawnSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { Either } from "effect"
import { expect, it } from "vitest"

import {
  HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_PERMIT_TRUST_STATUS,
  canonicalPermitTrustSnapshotBytes,
  decodeCanonicalPermitEnvelopeBytes,
  verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext,
  type CanonicalPermitExpectedBindings,
  type CanonicalPermitTrustSnapshot
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-permit-envelope.js"

const vector = JSON.parse(readFileSync(new URL(
  "../../src/hswm/effect-runtime/test/fixtures/canonical-permit-envelope-v1.vector.json", import.meta.url
), "utf8")) as { readonly envelopeCanonicalBase64Url: string; readonly publicKeySpkiDerBase64Url: string }
const envelopeBytes = Uint8Array.from(Buffer.from(vector.envelopeCanonicalBase64Url, "base64url"))
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}
const envelope = right(decodeCanonicalPermitEnvelopeBytes(envelopeBytes))
const expected: CanonicalPermitExpectedBindings = Object.freeze({
  permitId: envelope.claims.permitId, executionId: envelope.claims.executionId,
  executionIntentDigest: envelope.claims.executionIntentDigest, permitDigest: envelope.claims.permitDigest,
  proposalDigest: envelope.claims.proposalDigest, transitionInvariantDigest: envelope.claims.transitionInvariantDigest,
  priorHead: envelope.claims.priorHead, expectedNextHead: envelope.claims.expectedNextHead, target: envelope.claims.target,
  expectedRevision: envelope.claims.expectedRevision, candidateRevision: envelope.claims.candidateRevision,
  authorizationRef: envelope.claims.authorizationRef, authorizer: envelope.claims.authorizer, scope: envelope.claims.scope,
  nonceDigest: envelope.claims.nonceDigest, keyPolicyVersion: envelope.claims.keyPolicyVersion,
  revocationEpoch: envelope.claims.revocationEpoch, linearizationIndex: envelope.claims.linearizationIndex
})
const trust: CanonicalPermitTrustSnapshot = Object.freeze({
  _tag: "CanonicalPermitTrustSnapshot", contractVersion: HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  policyVersion: expected.keyPolicyVersion, revocationEpoch: expected.revocationEpoch,
  snapshotAt: "2026-08-31T09:00:00.000Z",
  keys: Object.freeze([Object.freeze({ keyId: envelope.header.keyId, algorithm: "Ed25519", publicKeySpkiDerBase64Url: vector.publicKeySpkiDerBase64Url,
    authorizedAuthorizer: expected.authorizer, notBefore: "2026-08-01T00:00:00.000Z", expiresAt: "2026-10-01T00:00:00.000Z", status: "ACTIVE", revokedAt: null })]),
  status: HSWM_CANONICAL_PERMIT_TRUST_STATUS
})
const trustBytes = right(canonicalPermitTrustSnapshotBytes(trust))
const nativeAccepted = (value: CanonicalPermitExpectedBindings): boolean => Either.isRight(
  verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(envelopeBytes, value, trustBytes, "2026-08-31T12:00:00.000Z")
)
const cli = (): string => resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMVerifiedPermitBridgeCli")
const externalObservations = Object.freeze({ canonicalBytesAccepted: true, trustSnapshotAccepted: true, keyPolicyAndEpochMatched: true,
  keyAuthorizedForAuthorizer: true, keyActiveAtVerification: true, permitTimeActive: true, signatureAccepted: true })
const modeled = (value: CanonicalPermitExpectedBindings, observations = externalObservations): Record<string, unknown> => {
  const result = spawnSync(cli(), [], { input: JSON.stringify({ contract: "hswm-verified-permit-bridge/v1", key: vector.publicKeySpkiDerBase64Url,
    expectedKeyId: envelope.header.keyId, envelope, expectedBindings: value, externalObservations: observations }), encoding: "utf8", timeout: 10000, maxBuffer: 1024 * 1024 })
  expect(result.error).toBeUndefined()
  expect(result.status).toBe(0)
  expect(result.stderr).toBe("")
  return JSON.parse(result.stdout) as Record<string, unknown>
}

const mutations: ReadonlyArray<readonly [string, CanonicalPermitExpectedBindings]> = [
  ["execution intent", { ...expected, executionIntentDigest: "a".repeat(64) }],
  ["nonce", { ...expected, nonceDigest: "b".repeat(64) }],
  ["scope", { ...expected, scope: "scope:mutated" }],
  ["prior head", { ...expected, priorHead: { ...expected.priorHead, sequence: 39 } }],
  ["next head", { ...expected, expectedNextHead: { ...expected.expectedNextHead, recordDigest: "c".repeat(64) } }],
  ["target", { ...expected, target: { ...expected.target, atomUid: "atom:mutated" } }],
  ["expected revision", { ...expected, expectedRevision: "revision:mutated" }],
  ["candidate revision", { ...expected, candidateRevision: "revision:mutated" }],
  ["authorization", { ...expected, authorizationRef: "authorization:mutated" }],
  ["authorizer", { ...expected, authorizer: "principal:mutated" }],
  ["policy", { ...expected, keyPolicyVersion: "key-policy:mutated" }],
  ["epoch", { ...expected, revocationEpoch: expected.revocationEpoch + 1 }],
  ["linearization", { ...expected, linearizationIndex: expected.linearizationIndex + 1 }]
]

it("the native caller-relative verifier accepts the public signed vector and rejects every expected-binding substitution", () => {
  expect(nativeAccepted(expected)).toBe(true)
  for (const [, mutation] of mutations) expect(nativeAccepted(mutation)).toBe(false)
})

it.skipIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] !== "1")("computes the detailed permit model against native expected-binding decisions", () => {
  const valid = modeled(expected)
  expect(valid["modeledPermitAccepted"]).toBe(true)
  expect(valid["checkedScope"]).toMatchObject({ executionIntentDigest: expected.executionIntentDigest, nonceDigest: expected.nonceDigest,
    scope: expected.scope, priorHead: expected.priorHead, expectedNextHead: expected.expectedNextHead })
  expect(valid["signatureProved"]).toBe(false)
  for (const [name, mutation] of mutations) {
    expect(nativeAccepted(mutation), name).toBe(false)
    expect(modeled(mutation)["modeledPermitAccepted"], name).toBe(false)
  }
  for (const field of Object.keys(externalObservations)) {
    const rejected = modeled(expected, { ...externalObservations, [field]: false })
    expect(rejected["modeledPermitAccepted"], field).toBe(false)
  }
})
