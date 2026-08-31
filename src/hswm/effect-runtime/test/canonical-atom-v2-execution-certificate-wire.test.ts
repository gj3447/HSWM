import { createHash, createPrivateKey, sign as signMessage } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_PERMIT_TRUST_STATUS,
  assembleCanonicalPermitEnvelope,
  canonicalPermitTrustSnapshotBytes,
  type CanonicalPermitClaims,
  type CanonicalPermitTrustSnapshot
} from "../src/canonical-atom-v2-permit-envelope.js"
import {
  HSWM_EXECUTION_CERTIFICATE_WIRE_PHASE_A_STATUS,
  HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS,
  HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION,
  HSWM_EXECUTION_INTENT_WIRE_STATUS,
  HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION,
  HSWM_EXECUTION_WIRE_CANONICALIZATION,
  HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS,
  HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION,
  executionCertificateWirePhaseABytes,
  executionIntentWireBytes,
  verifyExecutionCertificateWirePhaseA,
  type ExecutionIntentWire
} from "../src/canonical-atom-v2-execution-certificate-wire.js"

const unwrap = <A, E>(value: Either.Either<A, E>): A => { if (Either.isLeft(value)) throw value.left; return value.right }
const sha = (n: number): string => n.toString(16).padStart(2, "0").repeat(32)
const artifact = (n: number) => ({ mediaType: "application/test", byteLength: n, digest: sha(n) })
const privateKey = createPrivateKey({ key: Buffer.from("302e020100300506032b6570042204209d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60", "hex"), format: "der", type: "pkcs8" })
const publicKey = Buffer.from("302a300506032b6570032100d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "hex").toString("base64url")

it("checks canonical raw intent/certificate bytes and derives Permit bindings from intent", () => {
  const intent: ExecutionIntentWire = {
    contractVersion: HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION, canonicalization: HSWM_EXECUTION_WIRE_CANONICALIZATION, status: HSWM_EXECUTION_INTENT_WIRE_STATUS,
    executionId: "execution:phase-a", permitId: "permit:phase-a", permitContentDigest: sha(2), proposalDigest: sha(3), expectedSuccessorHead: { lineageId: "lineage:test", sequence: 2, stateDigest: sha(7), recordDigest: sha(8) }, authorizer: "principal:issuer", permitResponsibilityOwner: "principal:permit-owner", invariantResponsibilityOwner: "principal:invariant-owner", invariantValidator: "principal:invariant-validator", permitIssueIndex: 10, predecessorHead: { lineageId: "lineage:test", sequence: 1, stateDigest: sha(5), recordDigest: sha(6) }, proposal: { target: { schemaVersion: "schema:test", lineageId: "lineage:atom", atomUid: "atom:test" }, expectedRevision: "revision:1", candidateRevision: "revision:2", proposer: "principal:proposer", authorizationRef: "authorization:test", scope: "scope:test", traceId: "trace:test" }, nonceDigest: sha(9), keyPolicyVersion: "policy:test", revocationEpoch: 1,
    schema: artifact(11), preState: artifact(12), trajectory: artifact(13), outcomePackage: artifact(14), proposalArtifact: artifact(15), authorization: artifact(16), invariantRequest: artifact(17), commitPlan: { contractVersion: HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION, status: HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS, executionId: "execution:phase-a", predecessorHead: { lineageId: "lineage:test", sequence: 1, stateDigest: sha(5), recordDigest: sha(6) }, successor: { lineageId: "lineage:test", sequence: 2, stateDigest: sha(7) }, target: { schemaVersion: "schema:test", lineageId: "lineage:atom", atomUid: "atom:test" }, expectedRevision: "revision:1", candidateRevision: "revision:2", permitContentDigest: sha(2), invariantContentDigest: sha(17), commitLinearizationIndex: 11 }, commitPlanArtifact: artifact(18)
  }
  const intentBytes = unwrap(executionIntentWireBytes(intent))
  const claims: CanonicalPermitClaims = { permitId: intent.permitId, executionId: intent.executionId, executionIntentDigest: awaitDigest(intentBytes), permitDigest: intent.permitContentDigest, proposalDigest: intent.proposalDigest, transitionInvariantDigest: intent.invariantRequest.digest, priorHead: intent.predecessorHead, expectedNextHead: intent.expectedSuccessorHead, target: intent.proposal.target, expectedRevision: intent.proposal.expectedRevision, candidateRevision: intent.proposal.candidateRevision, authorizationRef: intent.proposal.authorizationRef, authorizer: intent.authorizer, scope: intent.proposal.scope, nonceDigest: intent.nonceDigest, keyPolicyVersion: intent.keyPolicyVersion, revocationEpoch: intent.revocationEpoch, linearizationIndex: intent.permitIssueIndex, issuedAt: "2026-08-31T10:00:00.000Z", notBefore: "2026-08-31T10:00:01.000Z", expiresAt: "2026-09-01T10:00:00.000Z" }
  const envelope = unwrap(assembleCanonicalPermitEnvelope(claims, "key:test", bytes => Uint8Array.from(signMessage(null, bytes, privateKey))))
  const trust: CanonicalPermitTrustSnapshot = { _tag: "CanonicalPermitTrustSnapshot", contractVersion: HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION, policyVersion: intent.keyPolicyVersion, revocationEpoch: 1, snapshotAt: "2026-08-31T09:00:00.000Z", keys: [{ keyId: "key:test", algorithm: "Ed25519", publicKeySpkiDerBase64Url: publicKey, authorizedAuthorizer: intent.authorizer, notBefore: "2026-08-01T00:00:00.000Z", expiresAt: "2026-10-01T00:00:00.000Z", status: "ACTIVE", revokedAt: null }], status: HSWM_CANONICAL_PERMIT_TRUST_STATUS }
  const wire = { contractVersion: HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION, canonicalization: HSWM_EXECUTION_WIRE_CANONICALIZATION, status: HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS, executionId: intent.executionId, intent, permitEnvelope: envelope.envelope, intentArtifact: { mediaType: "application/test", byteLength: intentBytes.byteLength, digest: awaitDigest(intentBytes) }, permitArtifact: { mediaType: "application/test", byteLength: envelope.envelopeBytes.byteLength, digest: awaitDigest(envelope.envelopeBytes) } } as const
  const certificateBytes = unwrap(executionCertificateWirePhaseABytes(wire))
  const result = verifyExecutionCertificateWirePhaseA({ certificateBytes, intentBytes, permitEnvelopeBytes: envelope.envelopeBytes, certificateArtifact: { mediaType: "application/test", byteLength: certificateBytes.byteLength, digest: awaitDigest(certificateBytes) }, trustSnapshotBytes: unwrap(canonicalPermitTrustSnapshotBytes(trust)), verificationTime: "2026-08-31T12:00:00.000Z" })
  expect(unwrap(result).status).toBe(HSWM_EXECUTION_CERTIFICATE_WIRE_PHASE_A_STATUS)
  const tampered = Uint8Array.from(intentBytes); tampered[tampered.byteLength - 2] = 49
  expect(Either.isLeft(verifyExecutionCertificateWirePhaseA({ certificateBytes, intentBytes: tampered, permitEnvelopeBytes: envelope.envelopeBytes, certificateArtifact: { mediaType: "application/test", byteLength: certificateBytes.byteLength, digest: awaitDigest(certificateBytes) }, trustSnapshotBytes: unwrap(canonicalPermitTrustSnapshotBytes(trust)), verificationTime: "2026-08-31T12:00:00.000Z" }))).toBe(true)
})

const awaitDigest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
