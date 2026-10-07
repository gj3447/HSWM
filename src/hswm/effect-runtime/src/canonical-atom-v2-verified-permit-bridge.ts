import type { CallerRelativeCanonicalPermitEnvelopeVerification } from "./canonical-atom-v2-permit-envelope.js"
import type { AdmissionPreflightInput } from "./canonical-atom-v2-admission-preflight.js"

/**
 * Projection of a successful native caller-relative Permit verification.  This
 * is evidence supplied by the native verifier, not a substitute verifier or a
 * capability: JSON decoding, SHA-256, Ed25519, key/trust policy and checked
 * time remain outside this pure bridge.
 */
export interface VerifiedPermitBridgeProjection {
  readonly verifiedPermit: AdmissionPreflightInput["verifiedPermit"]
  readonly envelopeBytesSha256: string
  readonly signingBytesSha256: string
  readonly expectedBindingsSha256: string
  readonly trustSnapshotSha256: string
  readonly publicKeySpkiSha256: string
  readonly trustPolicyVersion: string
  readonly trustRevocationEpoch: number
  readonly trustedKeyId: string
  readonly verificationStatus: string
  readonly trustStatus: string
}

export const verifiedPermitBridgeProjection = (
  verification: CallerRelativeCanonicalPermitEnvelopeVerification
): VerifiedPermitBridgeProjection => Object.freeze({
  verifiedPermit: Object.freeze({
    envelopeDigest: verification.envelopeBytesSha256,
    checkedAt: verification.callerSuppliedVerificationTime,
    executionIntentDigest: verification.envelope.claims.executionIntentDigest,
    nonceDigest: verification.envelope.claims.nonceDigest,
    priorHead: Object.freeze({ ...verification.envelope.claims.priorHead }),
    expectedNextHead: Object.freeze({ ...verification.envelope.claims.expectedNextHead })
  }),
  envelopeBytesSha256: verification.envelopeBytesSha256,
  signingBytesSha256: verification.signingBytesSha256,
  expectedBindingsSha256: verification.callerSuppliedExpectedBindingsSha256,
  trustSnapshotSha256: verification.callerSuppliedTrustSnapshotSha256,
  publicKeySpkiSha256: verification.callerSuppliedPublicKeySpkiSha256,
  trustPolicyVersion: verification.callerSuppliedTrustPolicyVersion,
  trustRevocationEpoch: verification.callerSuppliedTrustRevocationEpoch,
  trustedKeyId: verification.callerSuppliedTrustedKeyId,
  verificationStatus: verification.status,
  trustStatus: verification.trustStatus
})
