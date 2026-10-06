/** Pure adapters for already strictly decoded journal values. Hashing, JSON
 * decoding and native validation stay at the existing caller boundary. These
 * functions neither grant authority nor authenticate receipt metadata. */
import { sameCanonicalAtomV2ContentDescriptor, type CanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import { HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE, type CanonicalAtomV2WriteContentBinding } from "./canonical-atom-v2-content-bound.js"
import type { CanonicalAtomV2EffectReceipt } from "./canonical-atom-v2-domain.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CommitCanonicalAtomsV2Command } from "./canonical-atom-v2-schema.js"

/** `envelope` is computed from the exact canonical bytes by the caller. */
export const canonicalAtomV2JournalEnvelopeMatches = (
  atom: CanonicalAtomV2,
  envelope: CanonicalAtomV2ContentDescriptor,
  binding: CanonicalAtomV2WriteContentBinding
): boolean =>
  envelope.mediaType === HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE &&
  sameCanonicalAtomV2ContentDescriptor(envelope, binding.envelope) &&
  canonicalAtomV2KeyId(atom.key) === canonicalAtomV2KeyId(binding.key) &&
  sameCanonicalAtomV2ContentDescriptor(atom.content, binding.payload)

export const canonicalAtomV2JournalReceiptCommand = (
  receipt: CanonicalAtomV2EffectReceipt,
  writes: ReadonlyArray<CanonicalAtomV2>
): CommitCanonicalAtomsV2Command =>
  Object.freeze({
    _tag: "CommitCanonicalAtomsV2" as const,
    contractVersion: "hswm-canonical-transition/v2" as const,
    transitionId: receipt.transitionId,
    expectedStateRevision: receipt.previousStateRevision,
    schemaVersion: receipt.schemaVersion,
    actorClaim: receipt.actorClaim,
    authorizationRef: receipt.authorizationRef,
    scope: receipt.scope,
    decidedAt: receipt.decidedAt,
    traceRef: receipt.traceRef,
    readSet: receipt.readSet,
    writes,
    provenanceSha256: receipt.provenanceSha256
  })
