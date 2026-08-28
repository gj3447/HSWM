/**
 * Structural DNRD-5 successor effect/receipt protocol instrument.
 *
 * It consumes explicit, bounded journal-descriptor evidence.  It neither
 * dispatches an effect nor recovers a durable runtime, and is deliberately not
 * evidence of occurrence, custody, learning, or efficacy.
 */
import { Data, Either } from "effect"

import type { Dnrd5V2AtomicBatchChronology } from "./canonical-atom-v2-dnrd5-v2-batch-chronology.js"
import { deriveDnrd5V2PostcommitReceiptIdentity } from "./canonical-atom-v2-dnrd5-v2-receipt-identity.js"

export const DNRD5_V2_EFFECT_PROTOCOL_V1 =
  "hswm-dnrd5-v2-effect-protocol/v1" as const

export const DNRD5_V2_EFFECT_PROTOCOL_BOUNDARY = Object.freeze({
  validates: "CALLER_SUPPLIED_STRUCTURAL_ONE_BLOCK_EFFECT_RECEIPT_PARTIAL_ORDER_AND_DESCRIPTOR_CONSISTENCY",
  doesNotValidate: Object.freeze([
    "PERMIT_DECISION", "EFFECT_SUBMISSION", "DURABLE_RECOVERY_IMPLEMENTATION",
    "BATCH_DAG_RECOMPUTATION_FROM_RAW_COMMAND", "JOURNAL_DESCRIPTOR_RECOMPUTATION_FROM_RAW_BYTES",
    "PROVIDER_OR_MODEL_CALL", "OCCURRENCE", "LEARNING", "EFFICACY",
    "BEHAVIOR_PROJECTION_READINESS", "PROBE_READINESS", "BLOCK_SEAL_READINESS"
  ])
} as const)

export type Dnrd5V2EffectArm =
  | "ACTIVE"
  | "OUTCOME_INDEPENDENT_SHAM"
  | "EXACT_W0_ROLLBACK"

export type Dnrd5V2ProtocolTerminal =
  | "DECLARED_TRACE_CONSISTENT_ONLY"

export interface Dnrd5V2JournalBinding {
  readonly journalLineageId: string
  readonly recordDescriptorSha256: string
  readonly commitIdentity: string
  readonly priorRevision: number
  readonly nextRevision: number
  readonly priorStateSha256: string
  readonly nextStateSha256: string
  readonly journalHeadSha256: string
}

export interface Dnrd5V2EffectBatchWitness {
  /** Output of the independent atomic-batch DAG validator for this command. */
  readonly topology: Dnrd5V2AtomicBatchChronology
  readonly writeAtomKeyIds: ReadonlyArray<string>
  readonly writeKinds: ReadonlyArray<"capability_consumption" | "macro_disposition" | "restore_transaction">
}

export interface Dnrd5V2ReceiptBatchWitness {
  readonly topology: Dnrd5V2AtomicBatchChronology
  readonly writeAtomKeyIds: ReadonlyArray<string>
  readonly writeKinds: ReadonlyArray<"evidence_seal_consumption" | "revision_transition_receipt" | "rollback_transition_receipt">
}

export interface Dnrd5V2EffectReceiptTrace {
  readonly arm: Dnrd5V2EffectArm
  readonly transitionKind: "ADMIT" | "RESTORE"
  readonly blockId: string
  readonly transitionId: string
  readonly decisionAtomKeyId: string
  readonly effectConsumptionAtomKeyId: string
  readonly effectAtomKeyId: string
  readonly effectBatch: Dnrd5V2EffectBatchWitness
  readonly recoveredEffect: Dnrd5V2JournalBinding
  readonly receiptAtomKeyId: string
  /** UID portion of the canonical receipt atom key; key lineage/revision stay explicit elsewhere. */
  readonly receiptAtomUid: string
  readonly evidenceSealConsumptionAtomKeyId: string
  readonly receiptBatch: Dnrd5V2ReceiptBatchWitness
  /** Must name the *preceding effect* record, never its own seal record. */
  readonly receiptEffectRecordDescriptorSha256: string
  readonly receiptEffectCommitIdentity: string
  readonly receiptJournalLineageId: string
  readonly receiptPriorRevision: number
  readonly receiptNextRevision: number
  readonly receiptPriorStateSha256: string
  readonly receiptNextStateSha256: string
  readonly receiptJournalHeadSha256: string
  readonly receiptIdentity: string
}

export interface Dnrd5V2CrashPrefix {
  readonly arm: Dnrd5V2EffectArm
  readonly transitionKind: "ADMIT" | "RESTORE"
  readonly blockId: string
  readonly transitionId: string
  readonly decisionAtomKeyId: string
  readonly effectConsumptionAtomKeyId: string
  readonly effectAtomKeyId: string
  readonly effectBatch: Dnrd5V2EffectBatchWitness
  readonly recoveredEffect: Dnrd5V2JournalBinding
}

export interface Dnrd5V2CompleteEffectProtocol {
  readonly _tag: "Dnrd5V2CompleteEffectProtocol"
  readonly contractVersion: typeof DNRD5_V2_EFFECT_PROTOCOL_V1
  readonly blockId: string
  readonly effects: ReadonlyArray<Dnrd5V2EffectReceiptTrace>
  /** The restore decision must bind the rollback staging admission receipt. */
  readonly rollbackDecisionStagingReceiptAtomKeyId: string
  readonly terminal: Dnrd5V2ProtocolTerminal
}

export interface Dnrd5V2CrashPrefixProtocol {
  readonly _tag: "Dnrd5V2CrashPrefixProtocol"
  readonly contractVersion: typeof DNRD5_V2_EFFECT_PROTOCOL_V1
  readonly prefix: Dnrd5V2CrashPrefix
}

export type Dnrd5V2EffectProtocolErrorCode =
  | "INPUT_INVALID" | "CARDINALITY_INVALID" | "PHASE_INVALID"
  | "BATCH_INVALID" | "BINDING_MISMATCH" | "REPLAY_INVALID"
  | "TERMINAL_FORBIDDEN" | "RECURSIVE_RECEIPT_INVALID"

export class Dnrd5V2EffectProtocolError extends Data.TaggedError("Dnrd5V2EffectProtocolError")<{
  readonly code: Dnrd5V2EffectProtocolErrorCode
  readonly detail: string
}> {}

export interface Dnrd5V2CompleteEffectProtocolValidated {
  readonly status: "DECLARED_TRACE_CONSISTENT_ONLY"
  readonly revisionReceiptCount: 3
  readonly rollbackReceiptCount: 1
}

export interface Dnrd5V2CrashPrefixValidated {
  readonly status: "DECLARED_EFFECT_RECORD_PRESENT_RECEIPT_RECOVERY_ONLY_NOT_DURABILITY_VERIFIED"
  readonly deterministicReceiptIdentity: string
}

const fail = (code: Dnrd5V2EffectProtocolErrorCode, detail: string) =>
  Either.left(new Dnrd5V2EffectProtocolError({ code, detail }))

const isIdentifier = (value: string): boolean => /^[A-Za-z0-9][A-Za-z0-9._:/|-]{0,511}$/.test(value)
const isSha256 = (value: string): boolean => /^[a-f0-9]{64}$/.test(value)
const unique = (values: ReadonlyArray<string>): boolean => new Set(values).size === values.length
const sameSet = (left: ReadonlyArray<string>, right: ReadonlyArray<string>): boolean =>
  left.length === right.length && [...left].sort().every((value, index) => value === [...right].sort()[index])
const canonicalKeyUid = (keyId: string): string | undefined => {
  const parts = keyId.split("|")
  return parts.length === 4 && parts.every((part) => part.length > 0) && /^\d+$/.test(parts[3]!)
    ? parts[2]
    : undefined
}

const receiptIdentity = (input: Pick<Dnrd5V2CrashPrefix, "transitionId" | "decisionAtomKeyId" | "effectConsumptionAtomKeyId" | "effectAtomKeyId" | "recoveredEffect">): Either.Either<string, Dnrd5V2EffectProtocolError> => {
  const hash = deriveDnrd5V2PostcommitReceiptIdentity({
    effectRecordDescriptorSha256: input.recoveredEffect.recordDescriptorSha256,
    journalLineageId: input.recoveredEffect.journalLineageId,
    transitionId: input.transitionId,
    decisionAtomKeyId: input.decisionAtomKeyId,
    effectConsumptionAtomKeyId: input.effectConsumptionAtomKeyId,
    effectAtomKeyId: input.effectAtomKeyId
  })
  return Either.isLeft(hash) ? fail("INPUT_INVALID", hash.left.detail) : Either.right(hash.right)
}

const validateJournal = (binding: Dnrd5V2JournalBinding): Either.Either<void, Dnrd5V2EffectProtocolError> =>
  !isIdentifier(binding.journalLineageId) || !isIdentifier(binding.commitIdentity) ||
  ![binding.recordDescriptorSha256, binding.priorStateSha256, binding.nextStateSha256, binding.journalHeadSha256].every(isSha256) ||
  !Number.isInteger(binding.priorRevision) || !Number.isInteger(binding.nextRevision) || binding.priorRevision < 0 || binding.nextRevision !== binding.priorRevision + 1
    ? fail("INPUT_INVALID", "journal evidence requires canonical identities, SHA-256 descriptors, and one revision step")
    : Either.right(undefined)

const validateBatch = (
  witness: Dnrd5V2EffectBatchWitness | Dnrd5V2ReceiptBatchWitness,
  expectedKinds: ReadonlyArray<string>, expectedKeys: ReadonlyArray<string>
): Either.Either<void, Dnrd5V2EffectProtocolError> => {
  if (!sameSet(witness.writeKinds, expectedKinds) || !sameSet(witness.writeAtomKeyIds, expectedKeys) || !unique(witness.writeAtomKeyIds)) {
    return fail("BATCH_INVALID", "command write keys/kinds do not equal the exact protocol grammar")
  }
  if (!sameSet(witness.topology.topologyAtomKeyIds, witness.writeAtomKeyIds) || !isSha256(witness.topology.topologySha256)) {
    return fail("BATCH_INVALID", "batch witness is not a two-write DAG result for these exact atom keys")
  }
  return Either.right(undefined)
}

const validateEffect = (trace: Dnrd5V2EffectReceiptTrace, blockId: string): Either.Either<void, Dnrd5V2EffectProtocolError> => {
  const identifiers = [trace.arm, trace.blockId, trace.transitionId, trace.receiptAtomUid]
  const atomKeys = [trace.decisionAtomKeyId, trace.effectConsumptionAtomKeyId, trace.effectAtomKeyId, trace.receiptAtomKeyId, trace.evidenceSealConsumptionAtomKeyId]
  if (trace.blockId !== blockId || !identifiers.every(isIdentifier) || !atomKeys.every((keyId) => canonicalKeyUid(keyId) !== undefined) || trace.effectAtomKeyId === trace.effectConsumptionAtomKeyId || trace.receiptAtomKeyId === trace.evidenceSealConsumptionAtomKeyId) return fail("INPUT_INVALID", "effect trace identities or block scope are invalid")
  if ((trace.transitionKind === "ADMIT" && trace.effectBatch.writeKinds.includes("restore_transaction")) || (trace.transitionKind === "RESTORE" && trace.effectBatch.writeKinds.includes("macro_disposition"))) return fail("PHASE_INVALID", "effect kind does not match admission/restore phase")
  const effectKinds = trace.transitionKind === "ADMIT" ? ["capability_consumption", "macro_disposition"] : ["capability_consumption", "restore_transaction"]
  const receiptKinds = trace.transitionKind === "ADMIT" ? ["evidence_seal_consumption", "revision_transition_receipt"] : ["evidence_seal_consumption", "rollback_transition_receipt"]
  const batch = validateBatch(trace.effectBatch, effectKinds, [trace.effectConsumptionAtomKeyId, trace.effectAtomKeyId])
  if (Either.isLeft(batch)) return batch
  const seal = validateBatch(trace.receiptBatch, receiptKinds, [trace.evidenceSealConsumptionAtomKeyId, trace.receiptAtomKeyId])
  if (Either.isLeft(seal)) return seal
  const journal = validateJournal(trace.recoveredEffect)
  if (Either.isLeft(journal)) return journal
  if (trace.recoveredEffect.commitIdentity !== trace.transitionId || trace.receiptAtomKeyId === trace.effectAtomKeyId || trace.receiptEffectRecordDescriptorSha256 !== trace.recoveredEffect.recordDescriptorSha256 || trace.receiptEffectCommitIdentity !== trace.recoveredEffect.commitIdentity || trace.receiptJournalLineageId !== trace.recoveredEffect.journalLineageId || trace.receiptPriorRevision !== trace.recoveredEffect.priorRevision || trace.receiptNextRevision !== trace.recoveredEffect.nextRevision || trace.receiptPriorStateSha256 !== trace.recoveredEffect.priorStateSha256 || trace.receiptNextStateSha256 !== trace.recoveredEffect.nextStateSha256 || trace.receiptJournalHeadSha256 !== trace.recoveredEffect.journalHeadSha256) return fail("BINDING_MISMATCH", "postcommit receipt must bind the preceding effect record and exact journal lineage")
  const expectedIdentity = receiptIdentity(trace)
  if (Either.isLeft(expectedIdentity)) return expectedIdentity
  return trace.receiptIdentity === expectedIdentity.right && trace.receiptAtomUid === `receipt:${expectedIdentity.right}` && canonicalKeyUid(trace.receiptAtomKeyId) === trace.receiptAtomUid
    ? Either.right(undefined)
    : fail("BINDING_MISMATCH", "receipt identity/key is not deterministically bound to recovered effect evidence")
}

/**
 * Validates the declared four-CAS shape; DELAYED is absent by construction.
 * Readiness remains blocked: raw commands/pre-state and journal bytes must be
 * independently rederived by a later actual-byte judge.
 */
export const validateDnrd5V2CompleteEffectProtocol = (input: Dnrd5V2CompleteEffectProtocol): Either.Either<Dnrd5V2CompleteEffectProtocolValidated, Dnrd5V2EffectProtocolError> => {
  if (input._tag !== "Dnrd5V2CompleteEffectProtocol" || input.contractVersion !== DNRD5_V2_EFFECT_PROTOCOL_V1 || !isIdentifier(input.blockId) || input.effects.length !== 4) return fail("CARDINALITY_INVALID", "complete block requires exactly four durable effects")
  const admissions = input.effects.filter(({ transitionKind }) => transitionKind === "ADMIT")
  const restores = input.effects.filter(({ transitionKind }) => transitionKind === "RESTORE")
  if (admissions.length !== 3 || restores.length !== 1 || !sameSet(admissions.map(({ arm }) => arm), ["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "EXACT_W0_ROLLBACK"]) || restores[0]?.arm !== "EXACT_W0_ROLLBACK") return fail("CARDINALITY_INVALID", "requires ACTIVE/SHAM/ROLLBACK admissions and one rollback restore; DELAYED has no effect")
  const noReplay = [
    ...input.effects.map(({ transitionId }) => transitionId),
    ...input.effects.map(({ decisionAtomKeyId }) => decisionAtomKeyId),
    ...input.effects.map(({ receiptAtomKeyId }) => receiptAtomKeyId),
    ...input.effects.map(({ recoveredEffect }) => recoveredEffect.recordDescriptorSha256),
    ...input.effects.map(({ effectConsumptionAtomKeyId }) => effectConsumptionAtomKeyId),
    ...input.effects.map(({ effectAtomKeyId }) => effectAtomKeyId),
    ...input.effects.map(({ evidenceSealConsumptionAtomKeyId }) => evidenceSealConsumptionAtomKeyId)
  ]
  if (!unique(noReplay)) return fail("REPLAY_INVALID", "transition, decision, effect, consumption, receipt, or recovered effect record is replayed")
  for (const effect of input.effects) {
    const valid = validateEffect(effect, input.blockId)
    if (Either.isLeft(valid)) return Either.left(valid.left)
  }
  const rollbackAdmission = admissions.find(({ arm }) => arm === "EXACT_W0_ROLLBACK")!
  const restore = restores[0]!
  if (restore.decisionAtomKeyId === rollbackAdmission.decisionAtomKeyId || input.rollbackDecisionStagingReceiptAtomKeyId !== rollbackAdmission.receiptAtomKeyId) return fail("PHASE_INVALID", "restore must follow and bind the rollback staging admission receipt")
  if (input.terminal !== "DECLARED_TRACE_CONSISTENT_ONLY") return fail("TERMINAL_FORBIDDEN", "this consistency instrument cannot emit effect-sealed, behavior, probe, or block-seal readiness")
  return Either.right(Object.freeze({ status: "DECLARED_TRACE_CONSISTENT_ONLY", revisionReceiptCount: 3, rollbackReceiptCount: 1 }))
}

/** Classifies only the crash prefix; it never retries or submits a command. */
export const classifyDnrd5V2CrashPrefix = (input: Dnrd5V2CrashPrefixProtocol): Either.Either<Dnrd5V2CrashPrefixValidated, Dnrd5V2EffectProtocolError> => {
  const prefix = input.prefix
  if (input._tag !== "Dnrd5V2CrashPrefixProtocol" || input.contractVersion !== DNRD5_V2_EFFECT_PROTOCOL_V1 || !["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "EXACT_W0_ROLLBACK"].includes(prefix.arm) || !isIdentifier(prefix.blockId) || !isIdentifier(prefix.transitionId) || ![prefix.decisionAtomKeyId, prefix.effectConsumptionAtomKeyId, prefix.effectAtomKeyId].every((keyId) => canonicalKeyUid(keyId) !== undefined)) return fail("INPUT_INVALID", "invalid declared effect-record crash prefix")
  const effectKinds = prefix.transitionKind === "ADMIT" ? ["capability_consumption", "macro_disposition"] : ["capability_consumption", "restore_transaction"]
  const batch = validateBatch(prefix.effectBatch, effectKinds, [prefix.effectConsumptionAtomKeyId, prefix.effectAtomKeyId])
  if (Either.isLeft(batch)) return Either.left(batch.left)
  const journal = validateJournal(prefix.recoveredEffect)
  if (Either.isLeft(journal)) return Either.left(journal.left)
  if (prefix.recoveredEffect.commitIdentity !== prefix.transitionId) {
    return fail("BINDING_MISMATCH", "recovered effect commit identity must equal the declared transition identity")
  }
  const identity = receiptIdentity(prefix)
  return Either.isLeft(identity)
    ? Either.left(identity.left)
    : Either.right(Object.freeze({ status: "DECLARED_EFFECT_RECORD_PRESENT_RECEIPT_RECOVERY_ONLY_NOT_DURABILITY_VERIFIED", deterministicReceiptIdentity: identity.right }))
}
