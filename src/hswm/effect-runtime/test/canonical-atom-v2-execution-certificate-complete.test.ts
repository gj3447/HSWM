import { createHash, createPrivateKey, createPublicKey, sign as signMessage } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_PERMIT_TRUST_STATUS,
  assembleCanonicalPermitEnvelope,
  canonicalPermitTrustSnapshotBytes,
  type CanonicalPermitClaims,
  type CanonicalPermitTrustSnapshot
} from "../src/canonical-atom-v2-permit-envelope.js"
import {
  HSWM_EXECUTION_CERTIFICATE_WIRE_COMPLETE_CHECK_STATUS,
  HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS,
  HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION,
  HSWM_EXECUTION_INTENT_WIRE_STATUS,
  HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION,
  HSWM_EXECUTION_WIRE_CANONICALIZATION,
  HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS,
  HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION,
  completeExecutionCertificateWireBytes,
  executionIntentWireBytes,
  verifyCompleteExecutionCertificateWire,
  type CompleteExecutionCertificateArtifacts,
  type CompleteExecutionCertificateWire,
  type ExecutionWireArtifactRef,
  type ExecutionWireProposal,
  type SignatureIndependentCommitPlanWire
} from "../src/canonical-atom-v2-execution-certificate-wire.js"

const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const privateKey = createPrivateKey({
  key: Buffer.from(
    "302e020100300506032b6570042204209d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
    "hex"
  ),
  format: "der",
  type: "pkcs8"
})
const publicKey = Buffer.from(
  "302a300506032b6570032100d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
  "hex"
).toString("base64url")
const text = (value: string): Uint8Array => new TextEncoder().encode(value)
const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")
const jsonBytes = (value: unknown): Uint8Array => unwrap(canonicalJsonBytes(value))
const artifact = (
  mediaType: string,
  bytes: Uint8Array
): ExecutionWireArtifactRef => Object.freeze({
  mediaType,
  byteLength: bytes.byteLength,
  digest: sha256(bytes)
})

interface CompleteVector {
  readonly wire: CompleteExecutionCertificateWire
  readonly certificateBytes: Uint8Array
  readonly certificateArtifact: ExecutionWireArtifactRef
  readonly artifacts: CompleteExecutionCertificateArtifacts
  readonly trustSnapshotBytes: Uint8Array
}

const makeCompleteVector = (): CompleteVector => {
  const executionId = "execution:complete-vector"
  const authorizer = "principal:authorizer"
  const target = Object.freeze({
    schemaVersion: "schema:complete-v1",
    lineageId: "lineage:target",
    atomUid: "atom:target"
  })
  const proposal: ExecutionWireProposal = Object.freeze({
    target,
    expectedRevision: "revision:1",
    candidateRevision: "revision:2",
    proposer: "principal:proposer",
    traceId: "trace:complete",
    authorizationRef: "authorization:complete",
    scope: "scope:complete"
  })

  const schemaBytes = text(target.schemaVersion)
  const preStateBytes = text("pre-state-bytes")
  const postStateBytes = text("post-state-bytes")
  const trajectoryBytes = text("sealed-trajectory-bytes")
  const outcomePackageBytes = text("outcome-package-bytes")
  const proposalBytes = jsonBytes(proposal)
  const authorizationBytes = text(proposal.authorizationRef)
  const invariantBytes = text("transition-invariant-request-bytes")
  const permitContentBytes = text("head-bound-permit-content-bytes")
  const predecessorRecordBytes = text("predecessor-record-bytes")
  const predecessorHead = Object.freeze({
    lineageId: "lineage:complete",
    sequence: 4,
    stateDigest: sha256(preStateBytes),
    recordDigest: sha256(predecessorRecordBytes)
  })

  const commitPlan: SignatureIndependentCommitPlanWire = Object.freeze({
    contractVersion: HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION,
    status: HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS,
    executionId,
    predecessorHead,
    successor: Object.freeze({
      lineageId: predecessorHead.lineageId,
      sequence: predecessorHead.sequence + 1,
      stateDigest: sha256(postStateBytes)
    }),
    target,
    expectedRevision: proposal.expectedRevision,
    candidateRevision: proposal.candidateRevision,
    permitContentDigest: sha256(permitContentBytes),
    invariantContentDigest: sha256(invariantBytes),
    commitLinearizationIndex: 11
  })
  const commitPlanBytes = jsonBytes(commitPlan)
  const successorHead = Object.freeze({
    ...commitPlan.successor,
    recordDigest: sha256(commitPlanBytes)
  })

  const intent = Object.freeze({
    contractVersion: HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION,
    canonicalization: HSWM_EXECUTION_WIRE_CANONICALIZATION,
    status: HSWM_EXECUTION_INTENT_WIRE_STATUS,
    executionId,
    permitId: "permit:complete-vector",
    permitContentDigest: commitPlan.permitContentDigest,
    proposalDigest: sha256(proposalBytes),
    expectedSuccessorHead: successorHead,
    authorizer,
    permitResponsibilityOwner: "principal:permit-owner",
    invariantResponsibilityOwner: "principal:invariant-owner",
    invariantValidator: "principal:invariant-validator",
    permitIssueIndex: 10,
    predecessorHead,
    proposal,
    nonceDigest: sha256(text("nonce:complete-vector")),
    keyPolicyVersion: "policy:complete-v1",
    revocationEpoch: 3,
    schema: artifact("text/plain", schemaBytes),
    preState: artifact("application/octet-stream", preStateBytes),
    trajectory: artifact("application/octet-stream", trajectoryBytes),
    outcomePackage: artifact("application/octet-stream", outcomePackageBytes),
    proposalArtifact: artifact("application/vnd.hswm.revision-proposal+json", proposalBytes),
    authorization: artifact("text/plain", authorizationBytes),
    invariantRequest: artifact("application/octet-stream", invariantBytes),
    commitPlan,
    commitPlanArtifact: artifact(
      "application/vnd.hswm.signature-independent-commit-plan+json",
      commitPlanBytes
    )
  })
  const intentBytes = unwrap(executionIntentWireBytes(intent))

  const claims: CanonicalPermitClaims = Object.freeze({
    permitId: intent.permitId,
    executionId,
    executionIntentDigest: sha256(intentBytes),
    permitDigest: intent.permitContentDigest,
    proposalDigest: intent.proposalDigest,
    transitionInvariantDigest: intent.invariantRequest.digest,
    priorHead: predecessorHead,
    expectedNextHead: successorHead,
    target,
    expectedRevision: proposal.expectedRevision,
    candidateRevision: proposal.candidateRevision,
    authorizationRef: proposal.authorizationRef,
    authorizer,
    scope: proposal.scope,
    nonceDigest: intent.nonceDigest,
    keyPolicyVersion: intent.keyPolicyVersion,
    revocationEpoch: intent.revocationEpoch,
    linearizationIndex: intent.permitIssueIndex,
    issuedAt: "2026-08-31T10:00:00.000Z",
    notBefore: "2026-08-31T10:00:00.000Z",
    expiresAt: "2026-09-01T10:00:00.000Z"
  })
  const envelope = unwrap(assembleCanonicalPermitEnvelope(
    claims,
    "key:complete-vector",
    (bytes) => Uint8Array.from(signMessage(null, bytes, privateKey))
  ))
  const trust: CanonicalPermitTrustSnapshot = Object.freeze({
    _tag: "CanonicalPermitTrustSnapshot",
    contractVersion: HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
    policyVersion: intent.keyPolicyVersion,
    revocationEpoch: intent.revocationEpoch,
    snapshotAt: "2026-08-31T09:00:00.000Z",
    keys: Object.freeze([Object.freeze({
      keyId: "key:complete-vector",
      algorithm: "Ed25519" as const,
      publicKeySpkiDerBase64Url: publicKey,
      authorizedAuthorizer: authorizer,
      notBefore: "2026-08-01T00:00:00.000Z",
      expiresAt: "2026-10-01T00:00:00.000Z",
      status: "ACTIVE" as const,
      revokedAt: null
    })]),
    status: HSWM_CANONICAL_PERMIT_TRUST_STATUS
  })

  const permit = Object.freeze({
    responsibilityOwner: intent.permitResponsibilityOwner,
    decision: Object.freeze({
      authorizationRef: proposal.authorizationRef,
      authorizer,
      target,
      traceId: proposal.traceId,
      scope: proposal.scope,
      allowed: true,
      activeAtDecision: true
    }),
    head: predecessorHead,
    expectedRevision: proposal.expectedRevision,
    candidateRevision: proposal.candidateRevision,
    contentDigest: intent.permitContentDigest
  })
  const invariantCertificate = Object.freeze({
    responsibilityOwner: intent.invariantResponsibilityOwner,
    validator: intent.invariantValidator,
    head: predecessorHead,
    target,
    expectedRevision: proposal.expectedRevision,
    candidateRevision: proposal.candidateRevision,
    contentDigest: intent.invariantRequest.digest
  })
  const issue = Object.freeze({
    executionId,
    issuer: authorizer,
    permitDigest: permit.contentDigest,
    head: predecessorHead,
    target,
    expectedRevision: proposal.expectedRevision,
    candidateRevision: proposal.candidateRevision,
    authorizationRef: proposal.authorizationRef,
    scope: proposal.scope,
    linearizationIndex: intent.permitIssueIndex
  })
  const commit = Object.freeze({
    executionId,
    witness: Object.freeze({
      predecessorHead,
      successorHead,
      target,
      expectedRevision: proposal.expectedRevision,
      candidateRevision: proposal.candidateRevision,
      consumedPermitDigest: permit.contentDigest,
      consumedInvariantDigest: invariantCertificate.contentDigest
    }),
    recoveredSuccessorHead: successorHead,
    linearizationIndex: commitPlan.commitLinearizationIndex
  })
  const commitBytes = jsonBytes(commit)
  const recovery = Object.freeze({
    executionId,
    predecessorHead,
    successorHead,
    permitIssues: Object.freeze([issue]),
    successfulCommits: Object.freeze([commit]),
    recoveryIndex: 12
  })
  const recoveryBytes = jsonBytes(recovery)

  const wire: CompleteExecutionCertificateWire = Object.freeze({
    contractVersion: HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION,
    canonicalization: HSWM_EXECUTION_WIRE_CANONICALIZATION,
    status: HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS,
    executionId,
    intent,
    permitEnvelope: envelope.envelope,
    permit,
    invariantCertificate,
    issue,
    commit,
    recovery,
    intentArtifact: artifact(
      "application/vnd.hswm.execution-intent+json",
      intentBytes
    ),
    permitArtifact: artifact(
      "application/vnd.hswm.canonical-permit-envelope-v1+json",
      envelope.envelopeBytes
    ),
    invariantContentArtifact: artifact("application/octet-stream", invariantBytes),
    commitArtifact: artifact(
      "application/vnd.hswm.runtime-commit-occurrence+json",
      commitBytes
    ),
    recoveredPreState: intent.preState,
    recoveredPostState: artifact("application/octet-stream", postStateBytes),
    recoveredCommitCore: commitPlan,
    recoveredCommitCoreArtifact: intent.commitPlanArtifact,
    recoveryObservation: artifact(
      "application/vnd.hswm.recovery-projection+json",
      recoveryBytes
    ),
    trajectory: intent.trajectory
  })
  const certificateBytes = unwrap(completeExecutionCertificateWireBytes(wire))
  const artifacts: CompleteExecutionCertificateArtifacts = Object.freeze({
    certificateBody: certificateBytes,
    executionIntent: intentBytes,
    permitEnvelope: envelope.envelopeBytes,
    invariantContent: invariantBytes,
    commitOccurrence: commitBytes,
    recoveredPreState: preStateBytes,
    recoveredPostState: postStateBytes,
    recoveredCommitCore: commitPlanBytes,
    recoveryObservation: recoveryBytes,
    trajectory: trajectoryBytes,
    schema: schemaBytes,
    intentPreState: preStateBytes,
    outcomePackage: outcomePackageBytes,
    proposal: proposalBytes,
    authorization: authorizationBytes,
    invariantRequest: invariantBytes,
    commitPlan: commitPlanBytes
  })
  return Object.freeze({
    wire,
    certificateBytes,
    certificateArtifact: artifact(
      "application/vnd.hswm.execution-certificate+json",
      certificateBytes
    ),
    artifacts,
    trustSnapshotBytes: unwrap(canonicalPermitTrustSnapshotBytes(trust))
  })
}

const verify = (vector: CompleteVector) => verifyCompleteExecutionCertificateWire({
  certificateBytes: vector.certificateBytes,
  certificateArtifact: vector.certificateArtifact,
  artifacts: vector.artifacts,
  trustSnapshotBytes: vector.trustSnapshotBytes,
  verificationTime: "2026-08-31T12:00:00.000Z"
})

const withMutatedWire = (
  vector: CompleteVector,
  wire: CompleteExecutionCertificateWire
): CompleteVector => {
  const certificateBytes = unwrap(completeExecutionCertificateWireBytes(wire))
  return Object.freeze({
    ...vector,
    wire,
    certificateBytes,
    certificateArtifact: artifact(
      "application/vnd.hswm.execution-certificate+json",
      certificateBytes
    ),
    artifacts: Object.freeze({ ...vector.artifacts, certificateBody: certificateBytes })
  })
}

it("accepts one complete raw-byte vector whose record digest is computed without a SHA cycle", () => {
  const vector = makeCompleteVector()
  const accepted = unwrap(verify(vector))
  expect(accepted.status).toBe(HSWM_EXECUTION_CERTIFICATE_WIRE_COMPLETE_CHECK_STATUS)
  expect(createPublicKey(privateKey).export({ format: "der", type: "spki" }).toString("base64url")).toBe(publicKey)
  expect({
    plan: sha256(vector.artifacts.commitPlan),
    intent: sha256(vector.artifacts.executionIntent),
    permitEnvelope: sha256(vector.artifacts.permitEnvelope),
    certificate: sha256(vector.certificateBytes)
  }).toEqual({
    plan: "35b35dc660946db423af3d4b5d1ce8e94620bd4f09abd0b690b251b7f8c073d2",
    intent: "08c635b65494b7f81c49d11b4445a929340c21e905e5dd76c46699f2f57545a4",
    permitEnvelope: "0855c5d5cb21d44862ef6873def54e06154ceea3d6ac437135096a124a7e5002",
    certificate: "1dc209f1b7a3dc15aca9ddf5664c565fef2f38f1312ebc7aa6134d7d72206aa7"
  })
  expect(vector.wire.intent.commitPlan.successor).not.toHaveProperty("recordDigest")
  expect(vector.wire.intent.expectedSuccessorHead.recordDigest).toBe(
    vector.wire.intent.commitPlanArtifact.digest
  )
})

it("fails closed on every full-certificate structural mutation", () => {
  const vector = makeCompleteVector()
  const mutations: ReadonlyArray<
    (wire: CompleteExecutionCertificateWire) => CompleteExecutionCertificateWire
  > = [
    (wire) => ({ ...wire, recovery: { ...wire.recovery, permitIssues: [] } }),
    (wire) => ({
      ...wire,
      commit: {
        ...wire.commit,
        witness: { ...wire.commit.witness, consumedPermitDigest: "0".repeat(64) }
      }
    }),
    (wire) => ({
      ...wire,
      recovery: { ...wire.recovery, recoveryIndex: wire.commit.linearizationIndex }
    }),
    (wire) => ({
      ...wire,
      recoveredCommitCore: {
        ...wire.recoveredCommitCore,
        candidateRevision: "revision:unexpected"
      }
    }),
    (wire) => ({
      ...wire,
      commitArtifact: { ...wire.commitArtifact, digest: "f".repeat(64) }
    }),
    (wire) => ({
      ...wire,
      commit: {
        ...wire.commit,
        recoveredSuccessorHead: {
          ...wire.commit.recoveredSuccessorHead,
          sequence: wire.commit.recoveredSuccessorHead.sequence + 1
        }
      }
    }),
    (wire) => ({
      ...wire,
      permit: { ...wire.permit, responsibilityOwner: "principal:changed-permit-owner" }
    }),
    (wire) => ({
      ...wire,
      invariantCertificate: {
        ...wire.invariantCertificate,
        responsibilityOwner: "principal:changed-invariant-owner"
      }
    }),
    (wire) => ({
      ...wire,
      invariantCertificate: {
        ...wire.invariantCertificate,
        validator: "principal:changed-invariant-validator"
      }
    })
  ]
  for (const mutate of mutations) {
    expect(Either.isLeft(verify(withMutatedWire(vector, mutate(vector.wire))))).toBe(true)
  }
})

it("rejects noncanonical intent bytes even when their descriptor is recomputed", () => {
  const vector = makeCompleteVector()
  const noncanonicalIntent = Uint8Array.from([
    ...vector.artifacts.executionIntent,
    0x0a
  ])
  const wire: CompleteExecutionCertificateWire = {
    ...vector.wire,
    intentArtifact: artifact(
      vector.wire.intentArtifact.mediaType,
      noncanonicalIntent
    )
  }
  const mutated = withMutatedWire(vector, wire)
  const input: CompleteVector = Object.freeze({
    ...mutated,
    artifacts: Object.freeze({
      ...mutated.artifacts,
      executionIntent: noncanonicalIntent
    })
  })
  expect(Either.isLeft(verify(input))).toBe(true)
})

it("rejects changed invariant content even when its role descriptor is recomputed", () => {
  const vector = makeCompleteVector()
  const changedInvariantContent = text("changed-invariant-content-bytes")
  const wire: CompleteExecutionCertificateWire = {
    ...vector.wire,
    invariantContentArtifact: artifact("application/octet-stream", changedInvariantContent)
  }
  const mutated = withMutatedWire(vector, wire)
  const input: CompleteVector = Object.freeze({
    ...mutated,
    artifacts: Object.freeze({
      ...mutated.artifacts,
      invariantContent: changedInvariantContent
    })
  })
  expect(Either.isLeft(verify(input))).toBe(true)
})
