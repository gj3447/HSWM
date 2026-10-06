/** Pure decisions on already validated inputs. These are reference grants and
 * recovered journal preconditions, not cryptographic Permit or POSIX proofs. */
import type { CanonicalAtomV2ContentAuthorizationGrant, CommitCanonicalAtomsV2ContentBound } from "./canonical-atom-v2-content-bound.js"
import type { CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"
import type { CanonicalAtomV2StateJournalEntry, CanonicalAtomV2StateJournalPublish } from "./canonical-atom-v2-state-journal-store.js"

export const canonicalAtomV2ExactBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((byte, index) => byte === right[index])

export type CanonicalAtomV2ReferenceGrantDenial =
  | "SCHEMA_CONTENT_MISMATCH" | "NOT_GRANTED" | "SCHEMA_MISMATCH" | "SCOPE_DENIED"

export const canonicalAtomV2ReferenceGrantDecision = (
  activeSchemaSha256: string, grants: ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant>,
  input: Pick<CommitCanonicalAtomsV2ContentBound, "schemaContentSha256"> & {
    readonly command: Pick<CommitCanonicalAtomsV2ContentBound["command"], "authorizationRef" | "schemaVersion" | "scope">
  }
): CanonicalAtomV2ReferenceGrantDenial | null => {
  if (input.schemaContentSha256 !== activeSchemaSha256) return "SCHEMA_CONTENT_MISMATCH"
  const matchingReference = grants.filter(grant => grant.authorizationRef === input.command.authorizationRef)
  if (matchingReference.length === 0) return "NOT_GRANTED"
  const matchingSchema = matchingReference.filter(grant => grant.schemaVersion === input.command.schemaVersion)
  if (matchingSchema.length === 0) return "SCHEMA_MISMATCH"
  const matchingContent = matchingSchema.filter(grant => grant.schemaContentSha256 === activeSchemaSha256)
  if (matchingContent.length === 0) return "SCHEMA_CONTENT_MISMATCH"
  if (!matchingContent.some(grant => grant.scopes.includes(input.command.scope))) return "SCOPE_DENIED"
  return null
}

const sameDescriptor = (left: CanonicalAtomV2StateJournalRecordDescriptor | null,
  right: CanonicalAtomV2StateJournalRecordDescriptor | null): boolean =>
  left === null || right === null ? left === right : left.mediaType === right.mediaType &&
    left.byteLength === right.byteLength && left.sha256 === right.sha256

export type CanonicalAtomV2JournalPlan =
  | { readonly _tag: "APPEND" | "ALREADY_COMMITTED" }
  | { readonly _tag: "REJECTED"; readonly reason: "PREDECESSOR_MISMATCH" | "CONCURRENT_PUBLICATION_CONFLICT" | "REVISION_CONFLICT"; readonly detail: string }

/** Preflight only: concurrent publication still requires linkNoReplace and
 * recovery. In particular an exact retry of an older occupied slot is valid. */
export const canonicalAtomV2JournalPublicationPlan = (
  before: ReadonlyArray<CanonicalAtomV2StateJournalEntry>, input: CanonicalAtomV2StateJournalPublish
): CanonicalAtomV2JournalPlan => {
  const predecessor = input.stateRevision === 0 ? null : before[input.stateRevision - 1]?.descriptor ?? null
  if (!sameDescriptor(input.expectedPredecessor, predecessor)) return Object.freeze({ _tag: "REJECTED",
    reason: "PREDECESSOR_MISMATCH", detail: "journal predecessor does not match the exact preceding record descriptor" })
  const existing = before[input.stateRevision]
  if (existing !== undefined) return canonicalAtomV2ExactBytes(existing.bytes, input.bytes)
    ? Object.freeze({ _tag: "ALREADY_COMMITTED" })
    : Object.freeze({ _tag: "REJECTED", reason: "CONCURRENT_PUBLICATION_CONFLICT", detail: "journal revision is occupied by different bytes" })
  if (input.stateRevision !== before.length) return Object.freeze({ _tag: "REJECTED",
    reason: "REVISION_CONFLICT", detail: "journal revision is not next contiguous slot" })
  if (!sameDescriptor(before.at(-1)?.descriptor ?? null, input.expectedPredecessor)) return Object.freeze({ _tag: "REJECTED",
    reason: "PREDECESSOR_MISMATCH", detail: "journal predecessor does not match recovered tail" })
  return Object.freeze({ _tag: "APPEND" })
}
