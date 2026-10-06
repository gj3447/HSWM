/** Pure predicates used by native journal replay after strict record decoding.
 * These check linkage, not permission, hash correctness or JSON semantics. */
import { sameCanonicalAtomV2ContentDescriptor, type CanonicalAtomV2SchemaContentBinding } from "./canonical-atom-v2-content.js"
import type { CanonicalAtomV2EffectReceipt } from "./canonical-atom-v2-domain.js"
import type { CanonicalAtomV2StateJournalCommit, CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"

export interface CanonicalAtomV2JournalReplayHead {
  readonly journalLineageId: string
  readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly state: { readonly revision: number }
}

export const canonicalAtomV2JournalLinkMatches = (
  previous: CanonicalAtomV2JournalReplayHead,
  record: Pick<CanonicalAtomV2StateJournalCommit, "journalLineageId" | "predecessor" | "stateRevision">
): boolean => record.journalLineageId === previous.journalLineageId &&
  sameCanonicalAtomV2ContentDescriptor(record.predecessor, previous.descriptor) &&
  record.stateRevision === previous.state.revision + 1

export const canonicalAtomV2JournalSchemaMatches = (
  expected: CanonicalAtomV2SchemaContentBinding,
  actual: CanonicalAtomV2SchemaContentBinding
): boolean => expected.schemaVersion === actual.schemaVersion &&
  sameCanonicalAtomV2ContentDescriptor(expected.content, actual.content)

export const canonicalAtomV2JournalReceiptHeaderMatches = (
  previousRevision: number, recordRevision: number, activeSchemaVersion: string,
  receipt: CanonicalAtomV2EffectReceipt
): boolean => receipt.previousStateRevision === previousRevision &&
  receipt.nextStateRevision === recordRevision && receipt.schemaVersion === activeSchemaVersion &&
  receipt.decision === "ACCEPTED" && receipt.guard.permission === "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"
