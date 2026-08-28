/** Pure DNRD-5 W0 restore/projection byte-identity checker; it performs no recovery. */
import { Data, Either, Schema } from "effect"

import { CanonicalAtomV2ContentDescriptorSchema, makeCanonicalAtomV2ContentDescriptor, sameCanonicalAtomV2ContentDescriptor, type CanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1, resolveDnrd5LocalExperimentalPermit, type Dnrd5LocalExperimentalPermitInput } from "./canonical-atom-v2-dnrd5-permit.js"
import { type Dnrd5ValidatedW0ForkIdentity } from "./canonical-atom-v2-dnrd5-w0.js"

export const DNRD5_RESTORE_PROJECTION_V1 = "hswm-dnrd5-w0-restore-projection/v1" as const
const Identifier = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const BlockId = Schema.String.pipe(Schema.pattern(/^DNRD5-BLOCK-(?:0(?:00[1-9]|0[1-9]\d|[12]\d{2})|0300)$/))
const OpaqueForkId = Schema.String.pipe(Schema.pattern(/^opaque:fork:[a-z0-9][a-z0-9._/-]{0,127}$/))
const Uid = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const Binding = Schema.Struct({ opaqueForkId: OpaqueForkId, w0Id: Identifier, state: CanonicalAtomV2ContentDescriptorSchema, behaviorReadset: CanonicalAtomV2ContentDescriptorSchema, journalHead: CanonicalAtomV2ContentDescriptorSchema, projectionPolicy: CanonicalAtomV2ContentDescriptorSchema })
const Projection = Schema.Struct({ descriptor: CanonicalAtomV2ContentDescriptorSchema, behaviorUids: Schema.Array(Uid), auditOnlyUids: Schema.Array(Uid) })
const Record = Schema.Struct({
  _tag: Schema.Literal("Dnrd5RestoreProjectionRecord"), contractVersion: Schema.Literal(DNRD5_RESTORE_PROJECTION_V1), blockId: BlockId,
  binding: Binding, transition: Schema.Struct({ sourceKind: Schema.Literal("staging_successor"), targetKind: Schema.Literal("macro_disposition"), typedRole: Schema.Literal("restore_transaction") }),
  permitInput: Schema.Unknown, recoveredState: CanonicalAtomV2ContentDescriptorSchema, recoveredBehaviorReadset: CanonicalAtomV2ContentDescriptorSchema,
  restoredJournalReceipt: CanonicalAtomV2ContentDescriptorSchema, behaviorProjection: Projection,
  terminal: Schema.Literal("CALLER_SUPPLIED_BYTES_NOT_DURABLE_RUNTIME_RECOVERY_NOT_NONTRAVERSABILITY_NOT_EXECUTION_OCCURRENCE_OR_SCIENCE")
})
export type Dnrd5RestoreProjectionRecord = Schema.Schema.Type<typeof Record>
export type Dnrd5RestoreProjectionErrorCode = "BYTES_INVALID" | "RECORD_INVALID" | "CONTENT_MISSING" | "DESCRIPTOR_MISMATCH" | "IDENTITY_INVALID" | "PERMIT_INVALID" | "RESTORE_IDENTITY_INVALID" | "PROJECTION_INVALID"
export class Dnrd5RestoreProjectionError extends Data.TaggedError("Dnrd5RestoreProjectionError")<{ readonly code: Dnrd5RestoreProjectionErrorCode; readonly detail: string }> {}
const fail = (code: Dnrd5RestoreProjectionErrorCode, detail: string) => Either.left(new Dnrd5RestoreProjectionError({ code, detail }))
const sameBytes = (a: Uint8Array, b: Uint8Array) => a.byteLength === b.byteLength && a.every((x, i) => x === b[i])
const sameDescriptor = (a: CanonicalAtomV2ContentDescriptor, b: CanonicalAtomV2ContentDescriptor) => sameCanonicalAtomV2ContentDescriptor(a, b)
const sortedUnique = (values: readonly string[]) => values.every((v, i) => i === 0 || values[i - 1]! < v)
const deepSnapshot = <A>(value: A): A => { const copy = structuredClone(value); const freeze = (x: unknown): void => { if (typeof x === "object" && x !== null && !Object.isFrozen(x)) { Object.freeze(x); for (const y of Object.values(x)) freeze(y) } }; freeze(copy); return copy }
const verified = (d: CanonicalAtomV2ContentDescriptor, content: ReadonlyMap<string, Uint8Array>, label: string): Either.Either<Uint8Array, Dnrd5RestoreProjectionError> => {
  const bytes = content.get(d.sha256)
  if (!(bytes instanceof Uint8Array)) return fail("CONTENT_MISSING", `${label} content is absent at its exact SHA-256 key`)
  const actual = makeCanonicalAtomV2ContentDescriptor(d.mediaType, bytes)
  if (Either.isLeft(actual) || !sameDescriptor(d, actual.right)) return fail("DESCRIPTOR_MISMATCH", `${label} bytes do not match descriptor`)
  return Either.right(Uint8Array.from(bytes))
}
const exactCanonicalObject = (bytes: Uint8Array, expected: unknown): boolean => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) return false
  const canonical = canonicalJsonBytes(decoded.right)
  const expectedBytes = canonicalJsonBytes(expected)
  return Either.isRight(canonical) && Either.isRight(expectedBytes) && sameBytes(canonical.right, bytes) && sameBytes(expectedBytes.right, bytes)
}

export interface Dnrd5ValidatedRestoreProjection {
  readonly record: Dnrd5RestoreProjectionRecord
  readonly status: "CALLER_SUPPLIED_BYTE_IDENTITY_NOT_DURABLE_RECOVERY_OR_PERMIT_ISSUANCE"
  readonly terminal: "NOT_NONTRAVERSABILITY_NOT_EXECUTION_NOT_OCCURRENCE_NOT_SCIENTIFIC_RESULT"
}

export const validateDnrd5RestoreProjectionBytes = (recordBytes: Uint8Array, identity: Dnrd5ValidatedW0ForkIdentity, content: ReadonlyMap<string, Uint8Array>): Either.Either<Dnrd5ValidatedRestoreProjection, Dnrd5RestoreProjectionError> => {
  if (!(recordBytes instanceof Uint8Array) || !(content instanceof Map)) return fail("BYTES_INVALID", "record must be Uint8Array and content must be a Map")
  const parsed = decodeCanonicalJsonBytes(recordBytes)
  if (Either.isLeft(parsed)) return fail("BYTES_INVALID", "record is not strict canonical JSON")
  const canonical = canonicalJsonBytes(parsed.right)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, recordBytes)) return fail("BYTES_INVALID", "record bytes are not exact compact canonical JSON")
  const decoded = Schema.decodeUnknownEither(Record, { onExcessProperty: "error" })(parsed.right)
  if (Either.isLeft(decoded)) return fail("RECORD_INVALID", "record has missing, extra, or malformed fields")
  const record = decoded.right
  const fork = identity.manifest.forks.find((candidate) => candidate.opaqueForkId === record.binding.opaqueForkId)
  if (record.blockId !== identity.manifest.blockId || fork === undefined || record.binding.w0Id !== identity.manifest.w0.w0Id || !sameDescriptor(record.binding.state, fork.state) || !sameDescriptor(record.binding.behaviorReadset, fork.behaviorReadset) || !sameDescriptor(record.binding.journalHead, identity.manifest.w0.journalHead) || !sameDescriptor(record.binding.projectionPolicy, identity.manifest.w0.projectionPolicy)) return fail("IDENTITY_INVALID", "record must bind one exact validated W0 fork, block, state/readset, journal, and policy")
  const permit = resolveDnrd5LocalExperimentalPermit(record.permitInput)
  if (Either.isLeft(permit) || permit.right.contractVersion !== DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1 || permit.right.effect !== "RESTORE_W0") return fail("PERMIT_INVALID", "caller-supplied pure Permit input is not eligible for RESTORE_W0")
  const suppliedPermit = record.permitInput as Dnrd5LocalExperimentalPermitInput
  if (!sameDescriptor(record.binding.state, suppliedPermit.restore!.w0Snapshot) || record.binding.state.sha256 !== suppliedPermit.snapshot.stateSha256 || record.binding.state.sha256 !== suppliedPermit.restore!.expectedRootSha256 || record.binding.behaviorReadset.sha256 !== suppliedPermit.restore!.expectedReadsetSha256 || !sameDescriptor(record.binding.projectionPolicy, suppliedPermit.restore!.restorePolicy)) return fail("PERMIT_INVALID", "caller-supplied Permit/grant restore bindings do not match exact W0 identity")
  const state = verified(record.recoveredState, content, "recovered state"); const readset = verified(record.recoveredBehaviorReadset, content, "recovered behavior readset"); const receipt = verified(record.restoredJournalReceipt, content, "restored journal receipt"); const projectionBytes = verified(record.behaviorProjection.descriptor, content, "behavior projection")
  if (Either.isLeft(state)) return Either.left(state.left)
  if (Either.isLeft(readset)) return Either.left(readset.left)
  if (Either.isLeft(receipt)) return Either.left(receipt.left)
  if (Either.isLeft(projectionBytes)) return Either.left(projectionBytes.left)
  const w0State = verified(identity.manifest.w0.state, content, "W0 state"); const w0Readset = verified(identity.manifest.w0.behaviorReadset, content, "W0 behavior readset")
  if (Either.isLeft(w0State)) return Either.left(w0State.left)
  if (Either.isLeft(w0Readset)) return Either.left(w0Readset.left)
  if (!sameDescriptor(record.recoveredState, identity.manifest.w0.state) || !sameDescriptor(record.recoveredBehaviorReadset, identity.manifest.w0.behaviorReadset) || !sameBytes(state.right, w0State.right) || !sameBytes(readset.right, w0Readset.right)) return fail("RESTORE_IDENTITY_INVALID", "recovered state and readset must be exact W0 descriptors and bytes")
  if (sameDescriptor(record.restoredJournalReceipt, identity.manifest.w0.journalHead) || !exactCanonicalObject(receipt.right, { _tag: "Dnrd5RestoreJournalReceipt", blockId: record.blockId, opaqueForkId: record.binding.opaqueForkId, w0Id: record.binding.w0Id, w0JournalHeadSha256: record.binding.journalHead.sha256, w0StateSha256: record.binding.state.sha256, w0BehaviorReadsetSha256: record.binding.behaviorReadset.sha256, projectionPolicySha256: record.binding.projectionPolicy.sha256, grantSnapshotSha256: suppliedPermit.grantSnapshot.snapshotSha256, permitResolutionSha256: permit.right.resolutionCoreSha256, terminal: "CALLER_SUPPLIED_RESTORE_AUDIT_RECEIPT_NOT_DURABLE_RECOVERY_PROOF" })) return fail("RESTORE_IDENTITY_INVALID", "restore audit receipt must be a new exact canonical binding after the W0 journal head")
  if (!sortedUnique(record.behaviorProjection.behaviorUids) || !sortedUnique(record.behaviorProjection.auditOnlyUids) || new Set(record.behaviorProjection.behaviorUids).size !== record.behaviorProjection.behaviorUids.length || new Set(record.behaviorProjection.auditOnlyUids).size !== record.behaviorProjection.auditOnlyUids.length || record.behaviorProjection.behaviorUids.some((uid) => record.behaviorProjection.auditOnlyUids.includes(uid))) return fail("PROJECTION_INVALID", "behavior and audit-only UIDs must be sorted, unique, and disjoint")
  if (!exactCanonicalObject(projectionBytes.right, { _tag: "Dnrd5BehaviorProjection", blockId: record.blockId, sourceStateSha256: record.binding.state.sha256, projectionPolicySha256: record.binding.projectionPolicy.sha256, behaviorUids: record.behaviorProjection.behaviorUids, auditOnlyUids: record.behaviorProjection.auditOnlyUids, terminal: "CALLER_SUPPLIED_PROJECTION_NOT_NONTRAVERSABILITY_PROOF" })) return fail("PROJECTION_INVALID", "projection bytes must canonically bind exact block, source state, policy, and declared UIDs")
  return Either.right(deepSnapshot({ record, status: "CALLER_SUPPLIED_BYTE_IDENTITY_NOT_DURABLE_RECOVERY_OR_PERMIT_ISSUANCE", terminal: "NOT_NONTRAVERSABILITY_NOT_EXECUTION_NOT_OCCURRENCE_NOT_SCIENTIFIC_RESULT" }))
}
