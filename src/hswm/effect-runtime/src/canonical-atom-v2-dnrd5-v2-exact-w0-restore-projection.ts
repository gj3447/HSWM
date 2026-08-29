/**
 * DNRD-5 v2 exact-W0 RESTORE behavioural projection boundary.
 *
 * Target: after a structurally valid append-only RESTORE, the declared probe
 * behavioural root and its compiled readset are the exact W0 bytes.  Restore,
 * staging, outcome, and audit atoms remain in canonical state, but are not a
 * path in that behavioural projection.
 *
 * Current evidence: this verifies caller-supplied canonical records, content,
 * and projection structure only.  Conceptual delta: it neither executes a
 * probe nor establishes an occurrence, learning, efficacy, or scientific
 * result.  It is deliberately a small, pure evidence instrument.
 */
import { Data, Either } from "effect"

import { makeCanonicalAtomV2ContentDescriptor, sameCanonicalAtomV2ContentDescriptor, type CanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import { canonicalAtomV2EnvelopeBytes } from "./canonical-atom-v2-content-bound.js"
import { applyCanonicalAtomV2StateJournalCommit, canonicalAtomV2StateJournalRecordBytes, canonicalAtomV2StateSha256, describeCanonicalAtomV2StateJournalRecord, type CanonicalAtomV2StateJournalCommit, type CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"
import { makeCanonicalAtomV2AcceptedReceipt, validateCanonicalAtomV2State, type CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CommitCanonicalAtomsV2Command, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { DNRD5_V2_REFERENCE_TYPE, DNRD5_V2_OWNER_ROLE_BY_KIND, validateDnrd5V2CanonicalSchema } from "./canonical-atom-v2-dnrd5-v2-schema.js"
import { validateDnrd5V2RecordBoundEffect, type Dnrd5V2RecordBoundEffectInput } from "./canonical-atom-v2-dnrd5-v2-record-bound-effect.js"
import { validateDnrd5V2ReceiptSeal, type Dnrd5V2ReceiptSealInput } from "./canonical-atom-v2-dnrd5-v2-receipt-seal.js"

export const DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1 = "hswm-dnrd5-v2-exact-w0-restore-projection/v1" as const
export const DNRD5_V2_BEHAVIORAL_ROOT_V1 = "hswm-dnrd5-v2-behavioral-root/v1" as const
export const DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1 = "hswm-dnrd5-v2-compiled-behavior-readset/v1" as const
export const DNRD5_V2_EXACT_W0_TARGET_MEDIA_TYPE = "application/vnd.hswm.dnrd5-v2.exact-w0-target+json" as const
export const DNRD5_V2_EXACT_W0_PROJECTION_MEDIA_TYPE = "application/vnd.hswm.dnrd5-v2.exact-w0-projection+json" as const

export interface Dnrd5V2BehavioralRoot {
  readonly _tag: "Dnrd5V2BehavioralRoot"
  readonly contractVersion: typeof DNRD5_V2_BEHAVIORAL_ROOT_V1
  readonly atomKeyIds: ReadonlyArray<string>
}
export interface Dnrd5V2CompiledBehaviorReadset {
  readonly _tag: "Dnrd5V2CompiledBehaviorReadset"
  readonly contractVersion: typeof DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1
  readonly behavioralRootSha256: string
  readonly atomKeyIds: ReadonlyArray<string>
}
export interface Dnrd5V2ExactW0Target {
  readonly _tag: "Dnrd5V2ExactW0Target"
  readonly contractVersion: typeof DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1
  /** Declared historical W0 identity; this boundary does not prove W0 creation custody. */
  readonly declaredW0StateRevision: number
  readonly declaredW0StateSha256: string
  readonly behavioralRoot: CanonicalAtomV2ContentDescriptor
  readonly compiledReadset: CanonicalAtomV2ContentDescriptor
}
export interface Dnrd5V2ExactW0BehaviorProjection {
  readonly _tag: "Dnrd5V2ExactW0BehaviorProjection"
  readonly contractVersion: typeof DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1
  readonly w0SnapshotAtomKeyId: string
  readonly restoreTransactionAtomKeyId: string
  readonly behavioralRoot: CanonicalAtomV2ContentDescriptor
  readonly compiledReadset: CanonicalAtomV2ContentDescriptor
  /** Complete, sorted complement of the compiled readset in the post-R3 state. */
  readonly excludedAtomKeyIds: ReadonlyArray<string>
}
export interface Dnrd5V2ExactW0RestoreProjectionInput {
  readonly schema: HSWMCanonicalSchemaV2
  /** Raw R1; it is replayed here, never trusted as a caller assertion. */
  readonly restoreEffect: Dnrd5V2RecordBoundEffectInput
  /** Raw R2; it is replayed here and must seal the exact R1. */
  readonly rollbackSeal: Dnrd5V2ReceiptSealInput
  /** Deterministic R3 materialization, distinct from RESTORE's R1/R2 effect/receipt pair. */
  readonly projectionCommit: {
    readonly command: CommitCanonicalAtomsV2Command
    readonly record: CanonicalAtomV2StateJournalCommit
    readonly recordBytes: Uint8Array
    readonly recordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
    readonly envelope: Uint8Array
  }
  readonly postProjectionState: CanonicalAtomV2State
  readonly postProjectionStateRevision: number
  readonly postProjectionStateSha256: string
  readonly projection: Dnrd5V2ExactW0BehaviorProjection
  /** Immutable bytes addressed by descriptor SHA-256; no ambient content store. */
  readonly contentBySha256: ReadonlyMap<string, Uint8Array>
}

export type Dnrd5V2ExactW0RestoreProjectionErrorCode =
  | "INPUT_INVALID" | "SCHEMA_INVALID" | "RESTORE_INVALID" | "RECEIPT_INVALID"
  | "STATE_INVALID" | "CONTENT_INVALID" | "PROJECTION_INVALID"
export class Dnrd5V2ExactW0RestoreProjectionError extends Data.TaggedError("Dnrd5V2ExactW0RestoreProjectionError")<{
  readonly code: Dnrd5V2ExactW0RestoreProjectionErrorCode
  readonly detail: string
}> {}
export interface Dnrd5V2ExactW0RestoreProjectionValidated {
  readonly status: "EXACT_W0_RESTORE_BEHAVIOR_PROJECTION_STRUCTURALLY_VALIDATED_NOT_OCCURRENCE_NOT_LEARNING"
  readonly declaredW0StateRevision: number
  readonly declaredW0StateSha256: string
  readonly postProjectionStateRevision: number
  readonly postProjectionStateSha256: string
  readonly behavioralRoot: CanonicalAtomV2ContentDescriptor
  readonly compiledReadset: CanonicalAtomV2ContentDescriptor
  readonly behavioralAtomKeyIds: ReadonlyArray<string>
}

const fail = (code: Dnrd5V2ExactW0RestoreProjectionErrorCode, detail: string) => Either.left(new Dnrd5V2ExactW0RestoreProjectionError({ code, detail }))
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const bytesSame = (a: Uint8Array, b: Uint8Array) => a.byteLength === b.byteLength && a.every((v, i) => v === b[i])
const key = (atom: CanonicalAtomV2) => canonicalAtomV2KeyId(atom.key)
const sha = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value)
const sortedUnique = (values: ReadonlyArray<string>) => values.length > 0 && values.every((v, i) => typeof v === "string" && (i === 0 || values[i - 1]! < v))
const exactKeys = (value: Record<string, unknown>, required: ReadonlyArray<string>) => Object.keys(value).length === required.length && required.every((key) => key in value)
const isDescriptor = (value: unknown): value is CanonicalAtomV2ContentDescriptor => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false
  const candidate = value as Record<string, unknown>
  return exactKeys(candidate, ["mediaType", "byteLength", "sha256"]) &&
    typeof candidate["mediaType"] === "string" &&
    candidate["mediaType"].length > 0 &&
    Number.isSafeInteger(candidate["byteLength"]) &&
    (candidate["byteLength"] as number) >= 0 &&
    sha(candidate["sha256"])
}
const ref = (atom: CanonicalAtomV2, role: string): string | undefined => {
  const found = atom.references.filter((r) => r.referenceType === DNRD5_V2_REFERENCE_TYPE && r.role === `role:dnrd5:v2:${role}`)
  return found.length === 1 ? canonicalAtomV2KeyId(found[0]!.target) : undefined
}
const owner = (kind: keyof typeof DNRD5_V2_OWNER_ROLE_BY_KIND) => `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`
const exactAtom = (state: CanonicalAtomV2State, id: string, kind: keyof typeof DNRD5_V2_OWNER_ROLE_BY_KIND): CanonicalAtomV2 | undefined => {
  const atom = state.atoms.find((candidate) => key(candidate) === id)
  return atom !== undefined && atom.kind === `hswm:dnrd5:v2:${kind}` && atom.responsibilityOwner === owner(kind) ? atom : undefined
}
const content = (descriptor: CanonicalAtomV2ContentDescriptor, mediaType: string, map: ReadonlyMap<string, Uint8Array>): Either.Either<Uint8Array, Dnrd5V2ExactW0RestoreProjectionError> => {
  const bytes = map.get(descriptor.sha256)
  const recomputed = bytes === undefined ? undefined : makeCanonicalAtomV2ContentDescriptor(mediaType, bytes)
  return bytes === undefined || recomputed === undefined || Either.isLeft(recomputed) || !sameCanonicalAtomV2ContentDescriptor(descriptor, recomputed.right)
    ? fail("CONTENT_INVALID", "descriptor does not bind an available exact content byte string") : Either.right(bytes)
}
const parseExact = <T>(bytes: Uint8Array, predicate: (value: Record<string, unknown>) => boolean): Either.Either<T, Dnrd5V2ExactW0RestoreProjectionError> => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded) || typeof decoded.right !== "object" || decoded.right === null || Array.isArray(decoded.right) || !predicate(decoded.right as Record<string, unknown>)) return fail("CONTENT_INVALID", "content is not the exact declared canonical behavioural contract")
  const canonical = canonicalJsonBytes(decoded.right)
  return Either.isLeft(canonical) || !bytesSame(bytes, canonical.right) ? fail("CONTENT_INVALID", "content bytes are noncanonical") : Either.right(decoded.right as T)
}
const projectionForbiddenKinds = new Set<string>([
  "macro_disposition", "restore_transaction", "capability_consumption", "evidence_seal_consumption",
  "revision_transition_receipt", "rollback_transition_receipt", "hidden_outcome", "outcome_credit_escrow",
  "feedback_assignment", "probe_outcome", "audit_release", "block_evidence_manifest", "block_seal", "block_analysis", "study_analysis"
])

/** Replays R1/R2 and proves the declared behavioural byte projection is W0 exactly. */
export const validateDnrd5V2ExactW0RestoreProjection = (input: Dnrd5V2ExactW0RestoreProjectionInput): Either.Either<Dnrd5V2ExactW0RestoreProjectionValidated, Dnrd5V2ExactW0RestoreProjectionError> => {
  try {
    if (Either.isLeft(validateDnrd5V2CanonicalSchema(input.schema))) return fail("SCHEMA_INVALID", "requires the exact DNRD-5 v2 schema")
    const r1 = validateDnrd5V2RecordBoundEffect(input.restoreEffect)
    if (Either.isLeft(r1) || !r1.right.nextState.atoms.some((atom) => atom.kind === "hswm:dnrd5:v2:restore_transaction")) return fail("RESTORE_INVALID", "R1 is not an exact rollback RESTORE record")
    const r2 = validateDnrd5V2ReceiptSeal(input.rollbackSeal)
    if (Either.isLeft(r2) || r2.right.status !== "RAW_RECEIPT_SEAL_VALIDATED_NOT_PERMIT_OR_OCCURRENCE" || !same(input.rollbackSeal.precedingEffect.recordDescriptor, input.restoreEffect.recordDescriptor)) return fail("RECEIPT_INVALID", "R2 does not seal the exact replayed R1")
    const r2State = r2.right.nextState
    const r2Sha = canonicalAtomV2StateSha256(r2State)
    const r3 = input.projectionCommit
    const projectionAtom = r3.command.writes.length === 1 ? r3.command.writes[0] : undefined
    const projectionReadIds = projectionAtom === undefined ? [] : [ref(projectionAtom, "source"), ref(projectionAtom, "policy")]
    const exactProjectionReadIds = projectionReadIds.every((id): id is string => id !== undefined) ? [...projectionReadIds].sort() : []
    const commandReadIds = r3.command.readSet.map(canonicalAtomV2KeyId).sort()
    const envelope = projectionAtom === undefined ? undefined : canonicalAtomV2EnvelopeBytes(projectionAtom)
    const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(r3.command, r2State.revision, r2State.revision + 1)
    const canonicalRecord = canonicalAtomV2StateJournalRecordBytes(r3.record)
    const descriptor = describeCanonicalAtomV2StateJournalRecord(r3.record)
    if (Either.isLeft(r2Sha) || projectionAtom === undefined || projectionAtom.kind !== "hswm:dnrd5:v2:behavior_projection" || r3.command.writes.length !== 1 || !same(commandReadIds, exactProjectionReadIds) || r3.command.expectedStateRevision !== r2State.revision || r3.record.journalLineageId !== input.rollbackSeal.record.journalLineageId || !same(r3.record.predecessor, r2.right.receiptRecordDescriptor) || r3.record.schema.content.sha256 !== input.rollbackSeal.record.schema.content.sha256 || r3.record.stateRevision !== r2State.revision + 1 || r3.record.previousStateSha256 !== r2Sha.right || !same(r3.record.receipt, expectedReceipt) || envelope === undefined || Either.isLeft(envelope) || !bytesSame(envelope.right, r3.envelope) || Either.isLeft(canonicalRecord) || !bytesSame(canonicalRecord.right, r3.recordBytes) || Either.isLeft(descriptor) || !same(descriptor.right, r3.recordDescriptor)) return fail("STATE_INVALID", "R3 is not the exact one-write projection materialization after R2")
    const appliedR3 = applyCanonicalAtomV2StateJournalCommit(input.schema, { state: r2State, descriptor: r2.right.receiptRecordDescriptor, journalLineageId: input.rollbackSeal.record.journalLineageId, schema: r3.record.schema }, r3.record, [r3.envelope])
    const stateOk = validateCanonicalAtomV2State(input.schema, input.postProjectionState)
    const stateSha = canonicalAtomV2StateSha256(input.postProjectionState)
    if (Either.isLeft(appliedR3) || !same(appliedR3.right.state, input.postProjectionState) || input.postProjectionState.revision !== input.postProjectionStateRevision || Either.isLeft(stateOk) || Either.isLeft(stateSha) || stateSha.right !== input.postProjectionStateSha256) return fail("STATE_INVALID", "declared post-projection state differs from exact R3 replay or hash")

    const restore = input.restoreEffect.command.writes.find((atom) => atom.kind === "hswm:dnrd5:v2:restore_transaction")
    const consumption = input.restoreEffect.command.writes.find((atom) => atom.kind === "hswm:dnrd5:v2:capability_consumption")
    if (restore === undefined || consumption === undefined) return fail("RESTORE_INVALID", "R1 must contain exactly the restore transaction and main consumption")
    const decisionId = ref(restore, "decision")
    const w0Id = ref(restore, "w0")
    const stagingId = ref(restore, "staging-successor")
    const decision = decisionId === undefined ? undefined : exactAtom(input.restoreEffect.preState, decisionId, "rollback_decision")
    const w0 = w0Id === undefined ? undefined : exactAtom(input.restoreEffect.preState, w0Id, "w0_snapshot")
    if (decision === undefined || w0 === undefined || stagingId === undefined || ref(decision, "w0") !== w0Id || ref(decision, "staging-successor") !== stagingId || ref(restore, "consumption") !== key(consumption)) return fail("RESTORE_INVALID", "RESTORE decision, W0, staging, and provenance bindings are not exact")

    const targetBytes = content(w0.content, DNRD5_V2_EXACT_W0_TARGET_MEDIA_TYPE, input.contentBySha256)
    if (Either.isLeft(targetBytes)) return Either.left(targetBytes.left)
    const target = parseExact<Dnrd5V2ExactW0Target>(targetBytes.right, (v) => exactKeys(v, ["_tag", "contractVersion", "declaredW0StateRevision", "declaredW0StateSha256", "behavioralRoot", "compiledReadset"]) && v["_tag"] === "Dnrd5V2ExactW0Target" && v["contractVersion"] === DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1 && Number.isSafeInteger(v["declaredW0StateRevision"]) && (v["declaredW0StateRevision"] as number) >= 0 && sha(v["declaredW0StateSha256"]) && isDescriptor(v["behavioralRoot"]) && isDescriptor(v["compiledReadset"]))
    if (Either.isLeft(target)) return Either.left(target.left)
    if (projectionAtom.responsibilityOwner !== owner("behavior_projection") || ref(projectionAtom, "source") !== key(restore) || ref(projectionAtom, "policy") === undefined || input.projection.w0SnapshotAtomKeyId !== key(w0) || input.projection.restoreTransactionAtomKeyId !== key(restore) || projectionAtom.provenance.mode !== "DERIVATION" || canonicalAtomV2KeyId(projectionAtom.provenance.sourceRef!) !== key(restore)) return fail("PROJECTION_INVALID", "R3 projection lacks one owner and typed RESTORE/policy/provenance binding")
    const projectedBytes = content(projectionAtom.content, DNRD5_V2_EXACT_W0_PROJECTION_MEDIA_TYPE, input.contentBySha256)
    if (Either.isLeft(projectedBytes)) return Either.left(projectedBytes.left)
    const projected = parseExact<Dnrd5V2ExactW0BehaviorProjection>(projectedBytes.right, (v) => exactKeys(v, ["_tag", "contractVersion", "w0SnapshotAtomKeyId", "restoreTransactionAtomKeyId", "behavioralRoot", "compiledReadset", "excludedAtomKeyIds"]) && v["_tag"] === "Dnrd5V2ExactW0BehaviorProjection" && v["contractVersion"] === DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1 && typeof v["w0SnapshotAtomKeyId"] === "string" && typeof v["restoreTransactionAtomKeyId"] === "string" && isDescriptor(v["behavioralRoot"]) && isDescriptor(v["compiledReadset"]) && Array.isArray(v["excludedAtomKeyIds"]) && sortedUnique(v["excludedAtomKeyIds"] as string[]))
    const declaredProjectionBytes = canonicalJsonBytes(input.projection)
    if (Either.isLeft(projected) || Either.isLeft(declaredProjectionBytes) || !bytesSame(projectedBytes.right, declaredProjectionBytes.right)) return fail("PROJECTION_INVALID", "actual projection payload differs from declared exact projection")
    if (!sameCanonicalAtomV2ContentDescriptor(target.right.behavioralRoot, input.projection.behavioralRoot) || !sameCanonicalAtomV2ContentDescriptor(target.right.compiledReadset, input.projection.compiledReadset)) return fail("PROJECTION_INVALID", "post-RESTORE behavioural descriptors are not W0 descriptors")

    const rootBytes = content(target.right.behavioralRoot, "application/json", input.contentBySha256)
    const readsetBytes = content(target.right.compiledReadset, "application/json", input.contentBySha256)
    if (Either.isLeft(rootBytes)) return Either.left(rootBytes.left)
    if (Either.isLeft(readsetBytes)) return Either.left(readsetBytes.left)
    const root = parseExact<Dnrd5V2BehavioralRoot>(rootBytes.right, (v) => exactKeys(v, ["_tag", "contractVersion", "atomKeyIds"]) && v["_tag"] === "Dnrd5V2BehavioralRoot" && v["contractVersion"] === DNRD5_V2_BEHAVIORAL_ROOT_V1 && Array.isArray(v["atomKeyIds"]) && sortedUnique(v["atomKeyIds"] as string[]))
    const readset = parseExact<Dnrd5V2CompiledBehaviorReadset>(readsetBytes.right, (v) => exactKeys(v, ["_tag", "contractVersion", "behavioralRootSha256", "atomKeyIds"]) && v["_tag"] === "Dnrd5V2CompiledBehaviorReadset" && v["contractVersion"] === DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1 && sha(v["behavioralRootSha256"]) && Array.isArray(v["atomKeyIds"]) && sortedUnique(v["atomKeyIds"] as string[]))
    if (Either.isLeft(root) || Either.isLeft(readset) || readset.right.behavioralRootSha256 !== target.right.behavioralRoot.sha256 || !same(root.right.atomKeyIds, readset.right.atomKeyIds)) return fail("PROJECTION_INVALID", "compiled readset does not exactly compile the declared behavioural root")
    const selected = readset.right.atomKeyIds
    const all = input.postProjectionState.atoms.map(key).sort()
    const excluded = all.filter((id) => !selected.includes(id))
    if (!same(excluded, input.projection.excludedAtomKeyIds) || selected.some((id) => !all.includes(id))) return fail("PROJECTION_INVALID", "readset has duplicate, missing, or surplus state membership")
    const byId = new Map(input.postProjectionState.atoms.map((atom) => [key(atom), atom]))
    const visit = (id: string, seen = new Set<string>()): boolean => {
      if (seen.has(id)) return true
      seen.add(id)
      const atom = byId.get(id)
      if (atom === undefined || projectionForbiddenKinds.has(atom.kind.slice("hswm:dnrd5:v2:".length))) return false
      const targets = [...atom.references.filter((r) => r.referenceType === DNRD5_V2_REFERENCE_TYPE).map((r) => canonicalAtomV2KeyId(r.target)), ...(atom.provenance.sourceRef === null ? [] : [canonicalAtomV2KeyId(atom.provenance.sourceRef)])]
      return targets.every((target) => selected.includes(target) && visit(target, seen))
    }
    if (!selected.every((id) => visit(id))) return fail("PROJECTION_INVALID", "behavioural projection reaches staging, outcome, audit, or an excluded atom")
    return Either.right(Object.freeze({ status: "EXACT_W0_RESTORE_BEHAVIOR_PROJECTION_STRUCTURALLY_VALIDATED_NOT_OCCURRENCE_NOT_LEARNING" as const, declaredW0StateRevision: target.right.declaredW0StateRevision, declaredW0StateSha256: target.right.declaredW0StateSha256, postProjectionStateRevision: input.postProjectionStateRevision, postProjectionStateSha256: input.postProjectionStateSha256, behavioralRoot: Object.freeze({ ...target.right.behavioralRoot }), compiledReadset: Object.freeze({ ...target.right.compiledReadset }), behavioralAtomKeyIds: Object.freeze([...selected]) }))
  } catch {
    return fail("INPUT_INVALID", "untrusted exact-W0 RESTORE projection input could not be safely inspected")
  }
}
