import type { CanonicalPermitHeadBinding } from "./canonical-atom-v2-permit-envelope.js"

/** Decoded observations at the native verifier/Lean boundary, not a capability.
 * `verifiedPermit` must come from a successful caller-relative native verifier.
 * Hash computation, JSON decoding, crypto, key trust and time are external to
 * this pure projection. Structural copies cannot establish that provenance.
 */
export interface AdmissionPreflightInput {
  readonly view: { readonly head: CanonicalPermitHeadBinding | null; readonly consumedNonces: ReadonlyArray<string> }
  readonly record: {
    readonly committedAt: string; readonly verificationTime: string; readonly envelopeDigest: string
    readonly executionIntentDigest: string; readonly nonceDigest: string
    readonly priorHead: CanonicalPermitHeadBinding; readonly expectedNextHead: CanonicalPermitHeadBinding
  }
  readonly verifiedPermit: {
    readonly envelopeDigest: string; readonly checkedAt: string
    readonly executionIntentDigest: string; readonly nonceDigest: string
    readonly priorHead: CanonicalPermitHeadBinding; readonly expectedNextHead: CanonicalPermitHeadBinding
  }
  readonly preState: { readonly byteLength: number; readonly sha256: string }
  readonly postState: { readonly byteLength: number; readonly sha256: string }
}

export interface AdmissionPreflightAdapterFacts {
  readonly permitEnvelopeAccepted: boolean
  readonly stateBytesAccepted: boolean
  readonly verificationTimeAccepted: boolean
}

const sameHead = (left: CanonicalPermitHeadBinding, right: CanonicalPermitHeadBinding): boolean =>
  left.lineageId === right.lineageId && left.sequence === right.sequence &&
  left.stateDigest === right.stateDigest && left.recordDigest === right.recordDigest

const boundedLength = (length: number): boolean =>
  Number.isSafeInteger(length) && length > 0 && length <= 1_048_576

/** Bind the record to actual observed verifier output and bounded byte images.
 * This does not repeat signature verification or decide head/nonce admission;
 * the existing Lean kernel retains those transition conditions.
 */
export const admissionPreflightAdapterFacts = (input: AdmissionPreflightInput): AdmissionPreflightAdapterFacts => {
  const { record, verifiedPermit, preState, postState } = input
  return Object.freeze({
    permitEnvelopeAccepted: record.envelopeDigest === verifiedPermit.envelopeDigest &&
      record.executionIntentDigest === verifiedPermit.executionIntentDigest &&
      record.nonceDigest === verifiedPermit.nonceDigest &&
      sameHead(record.priorHead, verifiedPermit.priorHead) &&
      sameHead(record.expectedNextHead, verifiedPermit.expectedNextHead),
    stateBytesAccepted: boundedLength(preState.byteLength) && boundedLength(postState.byteLength) &&
      preState.sha256 === verifiedPermit.priorHead.stateDigest &&
      postState.sha256 === verifiedPermit.expectedNextHead.stateDigest,
    verificationTimeAccepted: record.committedAt === verifiedPermit.checkedAt &&
      record.verificationTime === verifiedPermit.checkedAt
  })
}
