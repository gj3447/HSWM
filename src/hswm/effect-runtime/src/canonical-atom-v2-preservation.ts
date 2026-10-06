/** Pure, decoded postcondition for an already structurally validated v2
 * transition. Complete normalized native envelope/schema text is retained,
 * not a hash. Sorted object keys + JSON.stringify defines this local view;
 * it is neither the canonical-JSON byte protocol nor an RDF serialization.
 * This is necessary for admission, never a permission or schema validator. */
import { canonicalAtomV2KeyId, snapshotCanonicalAtomV2, snapshotHSWMCanonicalSchemaV2, type CanonicalAtomV2, type CommitCanonicalAtomsV2Command, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import type { CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"

export interface CanonicalAtomV2Image {
  readonly key: string
  readonly envelopeUtf8: string
}
export interface CanonicalAtomV2PreservationState {
  readonly schemaVersion: string
  readonly schemaUtf8: string
  readonly revision: number
  readonly bootstrapClosed: boolean
  readonly atoms: ReadonlyArray<CanonicalAtomV2Image>
  readonly acceptedTransitionIds: ReadonlyArray<string>
}
export interface CanonicalAtomV2PreservationCommand {
  readonly schemaVersion: string
  readonly expectedStateRevision: number
  readonly transitionId: string
  readonly writes: ReadonlyArray<CanonicalAtomV2Image>
}
export interface CanonicalAtomV2PreservationInput {
  readonly contract: "hswm-canonical-preservation/v1"
  readonly before: CanonicalAtomV2PreservationState
  readonly after: CanonicalAtomV2PreservationState
  readonly command: CanonicalAtomV2PreservationCommand
}

// Validated native snapshots contain JSON values only. Sort every nested
// object's keys; retain array order. This local view adds no protocol byte cap.
const normalizedText = (value: unknown): string => JSON.stringify(value, (_key, entry: unknown) =>
  entry !== null && typeof entry === "object" && !Array.isArray(entry)
    ? Object.fromEntries(Object.entries(entry).sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0))
    : entry)
const atomImage = (atom: CanonicalAtomV2): CanonicalAtomV2Image =>
  Object.freeze({ key: canonicalAtomV2KeyId(atom.key), envelopeUtf8: normalizedText(snapshotCanonicalAtomV2(atom)) })
const stateImage = (schema: HSWMCanonicalSchemaV2, state: CanonicalAtomV2State): CanonicalAtomV2PreservationState =>
  Object.freeze({ schemaVersion: state.schemaVersion, schemaUtf8: normalizedText(snapshotHSWMCanonicalSchemaV2(schema)),
    revision: state.revision, bootstrapClosed: state.bootstrapClosed,
    atoms: Object.freeze(state.atoms.map(atomImage)),
    acceptedTransitionIds: Object.freeze([...state.acceptedTransitionIds]) })

/** The caller must use validated native values. JSON/key encoding fidelity is
 * an adapter obligation, not something the decoded Lean theorem proves. */
export const projectCanonicalAtomV2Preservation = (
  beforeSchema: HSWMCanonicalSchemaV2, afterSchema: HSWMCanonicalSchemaV2,
  before: CanonicalAtomV2State, after: CanonicalAtomV2State, command: CommitCanonicalAtomsV2Command
): CanonicalAtomV2PreservationInput => {
  return Object.freeze({ contract: "hswm-canonical-preservation/v1" as const,
    before: stateImage(beforeSchema, before), after: stateImage(afterSchema, after),
    command: Object.freeze({ schemaVersion: command.schemaVersion, expectedStateRevision: command.expectedStateRevision,
      transitionId: command.transitionId, writes: Object.freeze(command.writes.map(atomImage)) }) })
}

const uniqueKeys = (atoms: ReadonlyArray<CanonicalAtomV2Image>): boolean => new Set(atoms.map(atom => atom.key)).size === atoms.length
const natural = (value: number): boolean => Number.isSafeInteger(value) && value >= 0

/** Atom array storage order is not authority. Exact ordered role/reference
 * arrays live INSIDE each envelope and therefore must remain unchanged. */
export const canonicalAtomV2PreservationHolds = ({ before, after, command }: CanonicalAtomV2PreservationInput): boolean => {
  const oldKeys = new Set(before.atoms.map(atom => atom.key))
  const nextByKey = new Map(after.atoms.map(atom => [atom.key, atom.envelopeUtf8] as const))
  return natural(before.revision) && before.revision < Number.MAX_SAFE_INTEGER && natural(after.revision) &&
    natural(command.expectedStateRevision) && command.expectedStateRevision === before.revision &&
    after.revision === before.revision + 1 && after.bootstrapClosed &&
    before.schemaVersion === after.schemaVersion && before.schemaVersion === command.schemaVersion &&
    before.schemaUtf8 === after.schemaUtf8 &&
    !before.acceptedTransitionIds.includes(command.transitionId) &&
    after.acceptedTransitionIds.length === before.acceptedTransitionIds.length + 1 &&
    before.acceptedTransitionIds.every((id, index) => after.acceptedTransitionIds[index] === id) &&
    after.acceptedTransitionIds[before.acceptedTransitionIds.length] === command.transitionId &&
    command.writes.length > 0 && uniqueKeys(before.atoms) && uniqueKeys(after.atoms) && uniqueKeys(command.writes) &&
    command.writes.every(atom => !oldKeys.has(atom.key)) &&
    after.atoms.length === before.atoms.length + command.writes.length &&
    before.atoms.every(atom => nextByKey.get(atom.key) === atom.envelopeUtf8) &&
    command.writes.every(atom => nextByKey.get(atom.key) === atom.envelopeUtf8)
}

export const verifyCanonicalAtomV2Preservation = (
  schema: HSWMCanonicalSchemaV2, before: CanonicalAtomV2State, after: CanonicalAtomV2State,
  command: CommitCanonicalAtomsV2Command
): boolean => {
  const projected = projectCanonicalAtomV2Preservation(schema, schema, before, after, command)
  return canonicalAtomV2PreservationHolds(projected)
}
