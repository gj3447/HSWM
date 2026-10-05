/** Pure preflight predicates shared by the graph-loop controller and its
 * decoded Lean comparison fixture. Passing these checks is NOT admission:
 * decoding, evidence, authorization, schema validation and atomic CAS remain
 * obligations of the existing Effect/runtime boundary. */
import { sameCanonicalAtomV2ContentDescriptor, type CanonicalAtomV2ContentDescriptor, type CanonicalAtomV2SchemaContentBinding } from "./canonical-atom-v2-content.js"

export interface GraphLoopHead {
  readonly journalLineageId: string
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly stateRevision: number
  readonly stateSha256: string
  readonly journalHead: CanonicalAtomV2ContentDescriptor
}

export interface GraphLoopCandidateReadView {
  readonly schemaContentSha256: string
  readonly schemaVersion: string
  readonly expectedStateRevision: number
  readonly traceAbsent: boolean
  readonly writeCount: number
  readonly readKeys: ReadonlyArray<string>
}

/** Equality of every head field used by freshSnapshotMatches. The compiled
 * RDF projection is deliberately not a canonical write/admission authority. */
export const graphLoopHeadMatches = (expected: GraphLoopHead, current: GraphLoopHead): boolean =>
  expected.journalLineageId === current.journalLineageId &&
  expected.stateRevision === current.stateRevision &&
  expected.stateSha256 === current.stateSha256 &&
  sameCanonicalAtomV2ContentDescriptor(expected.journalHead, current.journalHead) &&
  expected.schema.schemaVersion === current.schema.schemaVersion &&
  sameCanonicalAtomV2ContentDescriptor(expected.schema.content, current.schema.content)

export const graphLoopEmptyMatchAllowed = (
  stateRevision: number, stateKeys: ReadonlyArray<string>, readKeys: ReadonlyArray<string>, affectedKeys: ReadonlyArray<string>
): boolean => affectedKeys.length > 0 || (stateRevision === 0 && stateKeys.length === 0 && readKeys.length === 0)

export const graphLoopCandidateMatches = (
  source: GraphLoopHead, stateKeys: ReadonlyArray<string>, candidate: GraphLoopCandidateReadView, affectedKeys: ReadonlyArray<string>
): boolean => {
  const available = new Set(stateKeys), reads = new Set(candidate.readKeys)
  return candidate.schemaContentSha256 === source.schema.content.sha256 &&
    candidate.schemaVersion === source.schema.schemaVersion &&
    candidate.expectedStateRevision === source.stateRevision &&
    candidate.traceAbsent && candidate.writeCount > 0 &&
    affectedKeys.every(key => reads.has(key)) && candidate.readKeys.every(key => available.has(key))
}
