/**
 * Raw-record verifier for the postcommit DNRD-5 v2 receipt seal.
 *
 * It binds a two-write receipt command to raw receipt payload and journal
 * bytes, and to the identity of the immediately preceding validated effect.
 * It is deliberately not a Permit, durable registry/custody, occurrence,
 * learning, or efficacy instrument.
 */
import { Either } from "effect"

import { makeCanonicalAtomV2ContentDescriptor, sameCanonicalAtomV2ContentDescriptor, type CanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import { canonicalAtomV2EnvelopeBytes } from "./canonical-atom-v2-content-bound.js"
import { canonicalAtomV2StateJournalRecordBytes, canonicalAtomV2StateSha256, describeCanonicalAtomV2StateJournalRecord, applyCanonicalAtomV2StateJournalCommit, type CanonicalAtomV2StateJournalCommit, type CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"
import { makeCanonicalAtomV2AcceptedReceipt, type CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CommitCanonicalAtomsV2Command, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { DNRD5_V2_REFERENCE_TYPE, validateDnrd5V2CanonicalSchema } from "./canonical-atom-v2-dnrd5-v2-schema.js"
import { validateDnrd5V2AtomicBatchChronology, type Dnrd5V2AtomicBatchChronology } from "./canonical-atom-v2-dnrd5-v2-batch-chronology.js"
import { deriveDnrd5V2PostcommitReceiptIdentity } from "./canonical-atom-v2-dnrd5-v2-receipt-identity.js"
import { validateDnrd5V2RecordBoundEffect, type Dnrd5V2RecordBoundEffectInput } from "./canonical-atom-v2-dnrd5-v2-record-bound-effect.js"

export const DNRD5_V2_RECEIPT_SEAL_V1 = "hswm-dnrd5-v2-receipt-seal/v1" as const
export const DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE = "application/vnd.hswm.dnrd5-v2.transition-receipt+json" as const
export const DNRD5_V2_RECEIPT_SEAL_BOUNDARY = Object.freeze({
  validates: "RAW_TWO_WRITE_RECEIPT_SEAL_JOURNAL_AND_PRECEDING_EFFECT_IDENTITY_BINDING",
  doesNotValidate: Object.freeze(["PERMIT", "DURABLE_GLOBAL_REPLAY_REGISTRY", "FULL_PREDECESSOR_CHAIN_CUSTODY", "OCCURRENCE", "LEARNING", "EFFICACY"])
} as const)

export interface Dnrd5V2ReceiptPayload {
  readonly contractVersion: typeof DNRD5_V2_RECEIPT_SEAL_V1
  readonly receiptKind: "REVISION" | "ROLLBACK"
  readonly precedingEffectRecordDescriptorSha256: string
  readonly postcommitReceiptIdentity: string
  readonly decisionAtomKeyId: string
  readonly effectConsumptionAtomKeyId: string
  readonly effectAtomKeyId: string
}
export interface Dnrd5V2ReceiptSealInput {
  readonly schema: HSWMCanonicalSchemaV2
  readonly preState: CanonicalAtomV2State
  readonly predecessor: { readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor; readonly journalLineageId: string; readonly schemaContentSha256: string }
  /** Exact raw main-effect evidence; this verifier revalidates it internally. */
  readonly precedingEffect: Dnrd5V2RecordBoundEffectInput
  readonly command: CommitCanonicalAtomsV2Command
  readonly record: CanonicalAtomV2StateJournalCommit
  readonly recordBytes: Uint8Array
  readonly recordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly envelopes: ReadonlyArray<Uint8Array>
  readonly receiptPayloadBytes: Uint8Array
  readonly receiptPayloadDescriptor: CanonicalAtomV2ContentDescriptor
  /** Bounded caller-supplied scope only; a global durable registry is excluded. */
  readonly usedReceiptRecordDescriptorSha256s: ReadonlyArray<string>
}
export type Dnrd5V2ReceiptSealErrorCode = "SCHEMA_INVALID" | "EFFECT_INVALID" | "BATCH_INVALID" | "PREDECESSOR_INVALID" | "PAYLOAD_INVALID" | "GRAMMAR_INVALID" | "RECORD_INVALID" | "DESCRIPTOR_INVALID" | "REPLAY_INVALID" | "IDENTITY_INVALID"
export class Dnrd5V2ReceiptSealError extends Error { constructor(readonly code: Dnrd5V2ReceiptSealErrorCode, detail: string) { super(detail) } }
export interface Dnrd5V2ReceiptSealValidated {
  readonly status: "RAW_RECEIPT_SEAL_VALIDATED_NOT_PERMIT_OR_OCCURRENCE"
  readonly topology: Dnrd5V2AtomicBatchChronology
  readonly nextState: CanonicalAtomV2State
  readonly receiptRecordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly postcommitReceiptIdentity: string
}
const fail = (code: Dnrd5V2ReceiptSealErrorCode, detail: string): Either.Either<never, Dnrd5V2ReceiptSealError> => Either.left(new Dnrd5V2ReceiptSealError(code, detail))
const key = (atom: CanonicalAtomV2) => canonicalAtomV2KeyId(atom.key)
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const bytesSame = (a: Uint8Array, b: Uint8Array) => a.byteLength === b.byteLength && a.every((v, i) => v === b[i])
const descriptorSame = (a: CanonicalAtomV2StateJournalRecordDescriptor, b: CanonicalAtomV2StateJournalRecordDescriptor) => a.mediaType === b.mediaType && a.byteLength === b.byteLength && a.sha256 === b.sha256
const references = (atom: CanonicalAtomV2, role: string) => atom.references.filter((r) => r.referenceType === DNRD5_V2_REFERENCE_TYPE && r.role === `role:dnrd5:v2:${role}`)
const exactlyOneReference = (atom: CanonicalAtomV2, role: string) => {
  const found = references(atom, role)
  return found.length === 1 ? found[0]! : undefined
}

export const canonicalDnrd5V2ReceiptPayloadBytes = (payload: Dnrd5V2ReceiptPayload) => canonicalJsonBytes(payload)

const payloadFrom = (bytes: Uint8Array): Either.Either<Dnrd5V2ReceiptPayload, Dnrd5V2ReceiptSealError> => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded) || typeof decoded.right !== "object" || decoded.right === null || Array.isArray(decoded.right)) return fail("PAYLOAD_INVALID", "receipt payload is not canonical object JSON")
  const value = decoded.right as Record<string, unknown>
  const required = ["contractVersion", "receiptKind", "precedingEffectRecordDescriptorSha256", "postcommitReceiptIdentity", "decisionAtomKeyId", "effectConsumptionAtomKeyId", "effectAtomKeyId"]
  if (Object.keys(value).length !== required.length || required.some((name) => !(name in value)) || value["contractVersion"] !== DNRD5_V2_RECEIPT_SEAL_V1 || (value["receiptKind"] !== "REVISION" && value["receiptKind"] !== "ROLLBACK") || required.slice(2).some((name) => typeof value[name] !== "string")) return fail("PAYLOAD_INVALID", "receipt payload has an invalid exact contract")
  const canonical = canonicalDnrd5V2ReceiptPayloadBytes(value as unknown as Dnrd5V2ReceiptPayload)
  return Either.isLeft(canonical) || !bytesSame(bytes, canonical.right) ? fail("PAYLOAD_INVALID", "receipt payload bytes are not exact canonical bytes") : Either.right(value as unknown as Dnrd5V2ReceiptPayload)
}

export const validateDnrd5V2ReceiptSeal = (input: Dnrd5V2ReceiptSealInput): Either.Either<Dnrd5V2ReceiptSealValidated, Dnrd5V2ReceiptSealError> => {
  if (Either.isLeft(validateDnrd5V2CanonicalSchema(input.schema))) return fail("SCHEMA_INVALID", "requires the exact DNRD-5 v2 schema")
  const precedingEffect = validateDnrd5V2RecordBoundEffect(input.precedingEffect)
  if (Either.isLeft(precedingEffect)) return fail("EFFECT_INVALID", `preceding main effect is invalid: ${precedingEffect.left.code}: ${precedingEffect.left.detail}`)
  const actualPreStateSha = canonicalAtomV2StateSha256(input.preState)
  const effectNextStateSha = canonicalAtomV2StateSha256(precedingEffect.right.nextState)
  if (Either.isLeft(actualPreStateSha) || Either.isLeft(effectNextStateSha) || input.record.schema.content.sha256 !== input.predecessor.schemaContentSha256 || input.record.journalLineageId !== input.predecessor.journalLineageId || input.predecessor.journalLineageId !== input.precedingEffect.record.journalLineageId || !descriptorSame(input.record.predecessor, input.predecessor.descriptor) || !descriptorSame(input.predecessor.descriptor, precedingEffect.right.effectRecordDescriptor) || input.preState.revision !== precedingEffect.right.nextState.revision || actualPreStateSha.right !== effectNextStateSha.right || !same(input.preState, precedingEffect.right.nextState) || input.record.stateRevision !== input.preState.revision + 1) return fail("PREDECESSOR_INVALID", "receipt record does not bind the exact preceding revalidated main-effect state")
  const payload = payloadFrom(input.receiptPayloadBytes); if (Either.isLeft(payload)) return Either.left(payload.left)
  const payloadDescriptor = makeCanonicalAtomV2ContentDescriptor(DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE, input.receiptPayloadBytes)
  if (Either.isLeft(payloadDescriptor) || !sameCanonicalAtomV2ContentDescriptor(payloadDescriptor.right, input.receiptPayloadDescriptor)) return fail("PAYLOAD_INVALID", "receipt payload descriptor is not recomputed from supplied bytes")
  const topology = validateDnrd5V2AtomicBatchChronology(input.schema, input.preState, input.command)
  if (Either.isLeft(topology)) return fail("BATCH_INVALID", `${topology.left.code}: ${topology.left.detail}`)
  if (input.command.writes.length !== 2) return fail("GRAMMAR_INVALID", "receipt seal command has exactly two writes")
  const evidence = input.command.writes.find((a) => a.kind === "hswm:dnrd5:v2:evidence_seal_consumption")
  const receipt = input.command.writes.find((a) => a.kind === "hswm:dnrd5:v2:revision_transition_receipt" || a.kind === "hswm:dnrd5:v2:rollback_transition_receipt")
  if (evidence === undefined || receipt === undefined) return fail("GRAMMAR_INVALID", "receipt seal writes must be evidence consumption plus one receipt")
  const kind = receipt.kind.endsWith(":revision_transition_receipt") ? "REVISION" : "ROLLBACK"
  const decision = exactlyOneReference(receipt, "decision"), consumption = exactlyOneReference(receipt, "effect-consumption"), effect = exactlyOneReference(receipt, kind === "REVISION" ? "successor" : "restore"), evidenceRef = exactlyOneReference(receipt, "evidence-consumption")
  const purpose = exactlyOneReference(evidence, "purpose"), evidenceGrant = exactlyOneReference(evidence, "grant"), evidenceCapability = exactlyOneReference(evidence, "capability"), evidenceRevocation = exactlyOneReference(evidence, "revocation")
  if ([decision, consumption, effect, evidenceRef, purpose, evidenceGrant, evidenceCapability, evidenceRevocation].some((r) => r === undefined) || canonicalAtomV2KeyId(evidenceRef!.target) !== key(evidence) || canonicalAtomV2KeyId(purpose!.target) !== canonicalAtomV2KeyId(decision!.target)) return fail("GRAMMAR_INVALID", "receipt/evidence references do not form the exact same-decision seal")
  const decisionAtom = input.preState.atoms.find((atom) => canonicalAtomV2KeyId(atom.key) === canonicalAtomV2KeyId(decision!.target))
  const decisionGrant = decisionAtom === undefined ? undefined : exactlyOneReference(decisionAtom, "grant")
  const decisionCapability = decisionAtom === undefined ? undefined : exactlyOneReference(decisionAtom, "capability")
  const decisionRevocation = decisionAtom === undefined ? undefined : exactlyOneReference(decisionAtom, "revocation")
  if ([decisionGrant, decisionCapability, decisionRevocation].some((r) => r === undefined) || canonicalAtomV2KeyId(evidenceGrant!.target) !== canonicalAtomV2KeyId(decisionGrant!.target) || canonicalAtomV2KeyId(evidenceCapability!.target) !== canonicalAtomV2KeyId(decisionCapability!.target) || canonicalAtomV2KeyId(evidenceRevocation!.target) !== canonicalAtomV2KeyId(decisionRevocation!.target)) return fail("GRAMMAR_INVALID", "evidence authority triple must equal the chosen decision authority triple")
  if (!sameCanonicalAtomV2ContentDescriptor(receipt.content, input.receiptPayloadDescriptor)) return fail("PAYLOAD_INVALID", "receipt atom payload descriptor does not bind supplied raw bytes")
  const recomputedIdentity = deriveDnrd5V2PostcommitReceiptIdentity({ effectRecordDescriptorSha256: precedingEffect.right.effectRecordDescriptor.sha256, journalLineageId: input.predecessor.journalLineageId, transitionId: input.precedingEffect.command.transitionId, decisionAtomKeyId: canonicalAtomV2KeyId(decision!.target), effectConsumptionAtomKeyId: canonicalAtomV2KeyId(consumption!.target), effectAtomKeyId: canonicalAtomV2KeyId(effect!.target) })
  if (Either.isLeft(recomputedIdentity) || receipt.key.atomUid !== `receipt:${recomputedIdentity.right}` || payload.right.receiptKind !== kind || payload.right.precedingEffectRecordDescriptorSha256 !== precedingEffect.right.effectRecordDescriptor.sha256 || payload.right.postcommitReceiptIdentity !== precedingEffect.right.deterministicFuturePostcommitReceiptIdentity || payload.right.postcommitReceiptIdentity !== recomputedIdentity.right || payload.right.decisionAtomKeyId !== canonicalAtomV2KeyId(decision!.target) || payload.right.effectConsumptionAtomKeyId !== canonicalAtomV2KeyId(consumption!.target) || payload.right.effectAtomKeyId !== canonicalAtomV2KeyId(effect!.target)) return fail("IDENTITY_INVALID", "payload or receipt UID does not bind the preceding revalidated effect identity")
  const before = canonicalAtomV2StateSha256(input.preState); const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(input.command, input.preState.revision, topology.right.nextState.revision)
  if (Either.isLeft(before) || input.record.previousStateSha256 !== before.right || !same(input.record.receipt, expectedReceipt)) return fail("RECORD_INVALID", "record does not match raw command/prestate")
  if (input.envelopes.length !== 2 || !input.record.writeBindings.every((binding, i) => { const atom = input.command.writes.find((a) => canonicalAtomV2KeyId(a.key) === canonicalAtomV2KeyId(binding.key)); const encoded = atom === undefined ? undefined : canonicalAtomV2EnvelopeBytes(atom); return encoded !== undefined && Either.isRight(encoded) && bytesSame(encoded.right, input.envelopes[i]!) })) return fail("RECORD_INVALID", "receipt journal envelopes are not exact command envelopes")
  const applied = applyCanonicalAtomV2StateJournalCommit(input.schema, { state: input.preState, descriptor: input.predecessor.descriptor, journalLineageId: input.predecessor.journalLineageId, schema: input.record.schema }, input.record, input.envelopes)
  if (Either.isLeft(applied) || !same(applied.right.state, topology.right.nextState)) return fail("RECORD_INVALID", "receipt journal replay differs from generic batch replay")
  const bytes = canonicalAtomV2StateJournalRecordBytes(input.record); const descriptor = describeCanonicalAtomV2StateJournalRecord(input.record)
  if (Either.isLeft(bytes) || Either.isLeft(descriptor) || !bytesSame(bytes.right, input.recordBytes) || !descriptorSame(descriptor.right, input.recordDescriptor)) return fail("DESCRIPTOR_INVALID", "receipt record bytes or descriptor are not recomputed")
  if (input.usedReceiptRecordDescriptorSha256s.includes(input.recordDescriptor.sha256)) return fail("REPLAY_INVALID", "receipt record descriptor already used in supplied scope")
  return Either.right(Object.freeze({ status: "RAW_RECEIPT_SEAL_VALIDATED_NOT_PERMIT_OR_OCCURRENCE" as const, topology: topology.right, nextState: applied.right.state, receiptRecordDescriptor: descriptor.right, postcommitReceiptIdentity: recomputedIdentity.right }))
}
