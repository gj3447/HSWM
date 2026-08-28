/**
 * Record-bound DNRD-5 v2 effect verifier.
 *
 * This is intentionally a verifier, never a dispatcher.  Unlike the older
 * caller-declared protocol projection it replays the generic command, binds
 * exact canonical journal bytes, and returns only a post-commit receipt
 * identity.  It is not a Permit, occurrence, learning, or efficacy claim.
 */
import { Data, Either } from "effect"

import { canonicalAtomV2EnvelopeBytes } from "./canonical-atom-v2-content-bound.js"
import { canonicalAtomV2StateSha256, canonicalAtomV2StateJournalRecordBytes, describeCanonicalAtomV2StateJournalRecord, applyCanonicalAtomV2StateJournalCommit, type CanonicalAtomV2StateJournalCommit, type CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type CommitCanonicalAtomsV2Command, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { makeCanonicalAtomV2AcceptedReceipt, type CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"
import { validateDnrd5V2CanonicalSchema, DNRD5_V2_REFERENCE_TYPE } from "./canonical-atom-v2-dnrd5-v2-schema.js"
import { validateDnrd5V2AtomicBatchChronology, type Dnrd5V2AtomicBatchChronology } from "./canonical-atom-v2-dnrd5-v2-batch-chronology.js"
import { deriveDnrd5V2PostcommitReceiptIdentity } from "./canonical-atom-v2-dnrd5-v2-receipt-identity.js"

export const DNRD5_V2_RECORD_BOUND_EFFECT_V1 = "hswm-dnrd5-v2-record-bound-effect/v1" as const
export const DNRD5_V2_RECORD_BOUND_EFFECT_BOUNDARY = Object.freeze({
  validates: "EXACT_V2_COMMAND_STATE_JOURNAL_RECORD_AND_EFFECT_GRAMMAR",
  doesNotValidate: Object.freeze(["PERMIT", "EFFECT_SUBMISSION", "PROVIDER_OR_MODEL_CALL", "OCCURRENCE", "LEARNING", "EFFICACY", "DURABLE_REPLAY_REGISTRY", "FULL_PREDECESSOR_CHAIN_CUSTODY", "RAW_CONTENT_PAYLOAD_BYTES", "RECEIPT_SEAL", "RAW_RECEIPT_CONTENT_TO_RECORD_DESCRIPTOR_BINDING"])
} as const)

export type Dnrd5V2RecordBoundEffectErrorCode =
  | "SCHEMA_INVALID" | "BATCH_INVALID" | "PREDECESSOR_INVALID" | "STATE_INVALID"
  | "RECEIPT_INVALID" | "RECORD_INVALID" | "DESCRIPTOR_INVALID" | "WRITE_BINDING_INVALID"
  | "GRAMMAR_INVALID" | "REPLAY_INVALID" | "IDENTITY_INVALID"
export class Dnrd5V2RecordBoundEffectError extends Data.TaggedError("Dnrd5V2RecordBoundEffectError")<{
  readonly code: Dnrd5V2RecordBoundEffectErrorCode
  readonly detail: string
}> {}
const fail = (code: Dnrd5V2RecordBoundEffectErrorCode, detail: string) => Either.left(new Dnrd5V2RecordBoundEffectError({ code, detail }))
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const keyId = (key: CanonicalAtomV2Key) => canonicalAtomV2KeyId(key)
const ref = (atom: CanonicalAtomV2, role: string, target: string): boolean => atom.references.some((r) => r.referenceType === DNRD5_V2_REFERENCE_TYPE && r.role === `role:dnrd5:v2:${role}` && keyId(r.target) === target)
const descriptorSame = (a: CanonicalAtomV2StateJournalRecordDescriptor, b: CanonicalAtomV2StateJournalRecordDescriptor) => a.mediaType === b.mediaType && a.byteLength === b.byteLength && a.sha256 === b.sha256

export interface Dnrd5V2RecordBoundEffectInput {
  readonly schema: HSWMCanonicalSchemaV2
  readonly preState: CanonicalAtomV2State
  /** The journal predecessor for preState, including the exact schema bytes it used. */
  readonly predecessor: { readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor; readonly journalLineageId: string; readonly schemaContentSha256: string }
  readonly command: CommitCanonicalAtomsV2Command
  readonly record: CanonicalAtomV2StateJournalCommit
  readonly recordBytes: Uint8Array
  readonly recordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly envelopes: ReadonlyArray<Uint8Array>
  /** Existing descriptors in this scope; prevents accepting the same record as a new effect. */
  readonly usedRecordDescriptorSha256s?: ReadonlyArray<string>
}
export interface Dnrd5V2RecordBoundEffectValidated {
  readonly status: "RECORD_BOUND_EFFECT_VALIDATED_NOT_PERMIT_OR_OCCURRENCE"
  readonly topology: Dnrd5V2AtomicBatchChronology
  readonly nextState: CanonicalAtomV2State
  readonly effectRecordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly deterministicFuturePostcommitReceiptIdentity: string
}

const validateGrammar = (preState: CanonicalAtomV2State, command: CommitCanonicalAtomsV2Command): Either.Either<void, Dnrd5V2RecordBoundEffectError> => {
  if (command.writes.length !== 2) return fail("GRAMMAR_INVALID", "effect command must have exactly two writes")
  const consumption = command.writes.find((a) => a.kind === "hswm:dnrd5:v2:capability_consumption")
  const disposition = command.writes.find((a) => a.kind === "hswm:dnrd5:v2:macro_disposition")
  const restore = command.writes.find((a) => a.kind === "hswm:dnrd5:v2:restore_transaction")
  if (consumption === undefined || (disposition === undefined && restore === undefined) || (disposition !== undefined && restore !== undefined)) return fail("GRAMMAR_INVALID", "effect writes must be {capability_consumption, macro_disposition} or {capability_consumption, restore_transaction}")
  const decisionRole = disposition === undefined ? "rollback_decision" : "revision_admission_decision"
  const decision = consumption.references.find((r) => r.referenceType === DNRD5_V2_REFERENCE_TYPE && r.role === "role:dnrd5:v2:decision")
  if (decision === undefined) return fail("GRAMMAR_INVALID", "consumption must name one decision")
  const preDecision = preState.atoms.find((atom) => keyId(atom.key) === keyId(decision.target))
  if (preDecision === undefined || preDecision.kind !== `hswm:dnrd5:v2:${decisionRole}`) return fail("GRAMMAR_INVALID", "consumption must name the correct decision branch in preState")
  const effect = disposition ?? restore!
  const effectDecisionRole = disposition === undefined ? "decision" : "revision-admission-decision"
  if (!ref(effect, "effect-consumption", keyId(consumption.key)) && !ref(effect, "consumption", keyId(consumption.key))) return fail("GRAMMAR_INVALID", "effect must reference its same-batch capability consumption")
  if (!ref(effect, effectDecisionRole, keyId(decision.target))) return fail("GRAMMAR_INVALID", "effect must reference the same decision as consumption")
  return Either.right(undefined)
}

/** Recomputes a single effect record from actual command, state and journal bytes. */
export const validateDnrd5V2RecordBoundEffect = (input: Dnrd5V2RecordBoundEffectInput): Either.Either<Dnrd5V2RecordBoundEffectValidated, Dnrd5V2RecordBoundEffectError> => {
  if (Either.isLeft(validateDnrd5V2CanonicalSchema(input.schema))) return fail("SCHEMA_INVALID", "requires exact DNRD-5 successor schema")
  if (input.record.schema.schemaVersion !== input.schema.schemaVersion || input.record.schema.content.sha256 !== input.predecessor.schemaContentSha256) return fail("PREDECESSOR_INVALID", "record schema binding differs from the predecessor's exact schema content")
  const topology = validateDnrd5V2AtomicBatchChronology(input.schema, input.preState, input.command)
  if (Either.isLeft(topology)) return fail("BATCH_INVALID", `${topology.left.code}: ${topology.left.detail}`)
  const grammar = validateGrammar(input.preState, input.command)
  if (Either.isLeft(grammar)) return Either.left(grammar.left)
  if (input.record.journalLineageId !== input.predecessor.journalLineageId || !descriptorSame(input.record.predecessor, input.predecessor.descriptor) || input.record.stateRevision !== input.preState.revision + 1) return fail("PREDECESSOR_INVALID", "record does not bind the exact immediate predecessor")
  const before = canonicalAtomV2StateSha256(input.preState)
  if (Either.isLeft(before) || (Either.isRight(before) && input.record.previousStateSha256 !== before.right)) return fail("STATE_INVALID", "record prior state hash does not equal actual preState")
  const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(input.command, input.preState.revision, topology.right.nextState.revision)
  if (!same(input.record.receipt, expectedReceipt)) return fail("RECEIPT_INVALID", "record receipt is not the exact generic accepted receipt")
  const ids = input.command.writes.map((a) => keyId(a.key)).sort()
  const bindingIds = input.record.writeBindings.map((b) => keyId(b.key))
  if (!same(bindingIds, ids)) return fail("WRITE_BINDING_INVALID", "record bindings must be canonical-key sorted and exactly equal command writes")
  if (input.envelopes.length !== input.command.writes.length) return fail("WRITE_BINDING_INVALID", "must supply actual canonical envelope bytes for every write")
  const commandById = new Map(input.command.writes.map((atom) => [keyId(atom.key), atom]))
  for (let index = 0; index < input.record.writeBindings.length; index += 1) {
    const atom = commandById.get(keyId(input.record.writeBindings[index]!.key))!
    const expected = canonicalAtomV2EnvelopeBytes(atom)
    const actual = input.envelopes[index]!
    if (Either.isLeft(expected) || actual.byteLength !== expected.right.byteLength || !actual.every((byte, byteIndex) => byte === expected.right[byteIndex])) return fail("WRITE_BINDING_INVALID", "journal envelope bytes must be the exact command-write envelopes in binding order")
  }
  const applied = applyCanonicalAtomV2StateJournalCommit(input.schema, { state: input.preState, descriptor: input.predecessor.descriptor, journalLineageId: input.predecessor.journalLineageId, schema: input.record.schema }, input.record, input.envelopes)
  if (Either.isLeft(applied)) return fail("RECORD_INVALID", `${applied.left.code}: ${applied.left.detail}`)
  if (!same(applied.right.state, topology.right.nextState)) return fail("STATE_INVALID", "journal replay next state differs from generic batch replay")
  const canonicalBytes = canonicalAtomV2StateJournalRecordBytes(input.record)
  if (Either.isLeft(canonicalBytes) || (Either.isRight(canonicalBytes) && (canonicalBytes.right.byteLength !== input.recordBytes.byteLength || !canonicalBytes.right.every((v, i) => v === input.recordBytes[i])))) return fail("RECORD_INVALID", "supplied record bytes are not exact canonical journal bytes")
  const descriptor = describeCanonicalAtomV2StateJournalRecord(input.record)
  if (Either.isLeft(descriptor) || (Either.isRight(descriptor) && !descriptorSame(descriptor.right, input.recordDescriptor))) return fail("DESCRIPTOR_INVALID", "record descriptor is not recomputed from actual record bytes")
  if (input.usedRecordDescriptorSha256s?.includes(input.recordDescriptor.sha256)) return fail("REPLAY_INVALID", "record descriptor was already used in this effect scope")
  const consumption = input.command.writes.find((a) => a.kind === "hswm:dnrd5:v2:capability_consumption")!
  const effect = input.command.writes.find((a) => a.kind !== "hswm:dnrd5:v2:capability_consumption")!
  const identity = deriveDnrd5V2PostcommitReceiptIdentity({
    effectRecordDescriptorSha256: input.recordDescriptor.sha256,
    journalLineageId: input.record.journalLineageId,
    transitionId: input.command.transitionId,
    decisionAtomKeyId: keyId(consumption.references.find((r) => r.role === "role:dnrd5:v2:decision")!.target),
    effectConsumptionAtomKeyId: keyId(consumption.key),
    effectAtomKeyId: keyId(effect.key)
  })
  if (Either.isLeft(identity)) return fail("IDENTITY_INVALID", identity.left.detail)
  return Either.right(Object.freeze({ status: "RECORD_BOUND_EFFECT_VALIDATED_NOT_PERMIT_OR_OCCURRENCE", topology: topology.right, nextState: applied.right.state, effectRecordDescriptor: descriptor.right, deterministicFuturePostcommitReceiptIdentity: identity.right }))
}
