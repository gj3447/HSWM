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
  doesNotValidate: Object.freeze(["PERMIT", "EFFECT_SUBMISSION", "PROVIDER_OR_MODEL_CALL", "OCCURRENCE", "LEARNING", "EFFICACY", "DURABLE_REPLAY_REGISTRY", "FULL_PREDECESSOR_CHAIN_CUSTODY", "RAW_CONTENT_PAYLOAD_BYTES", "RECEIPT_SEAL", "RAW_RECEIPT_CONTENT_TO_RECORD_DESCRIPTOR_BINDING", "RAW_STAGING_RECEIPT_RECORD_OR_PAYLOAD_CUSTODY"])
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
const singletonReferenceTarget = (atom: CanonicalAtomV2, role: string): string | undefined => {
  const targets = atom.references
    .filter((reference) => reference.referenceType === DNRD5_V2_REFERENCE_TYPE && reference.role === `role:dnrd5:v2:${role}`)
    .map((reference) => keyId(reference.target))
  return targets.length === 1 ? targets[0] : undefined
}
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
  readonly usedRecordDescriptorSha256s: ReadonlyArray<string>
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
  const decisionTarget = singletonReferenceTarget(consumption, "decision")
  if (decisionTarget === undefined) return fail("GRAMMAR_INVALID", "consumption must name exactly one decision")
  const preDecision = preState.atoms.find((atom) => keyId(atom.key) === decisionTarget)
  if (preDecision === undefined || preDecision.kind !== `hswm:dnrd5:v2:${decisionRole}`) return fail("GRAMMAR_INVALID", "consumption must name the correct decision branch in preState")
  const effect = disposition ?? restore!
  const effectDecisionRole = disposition === undefined ? "decision" : "revision-admission-decision"
  const effectConsumptionRole = disposition === undefined ? "consumption" : "effect-consumption"
  if (singletonReferenceTarget(effect, effectConsumptionRole) !== keyId(consumption.key)) return fail("GRAMMAR_INVALID", "effect must reference its exact same-batch capability consumption")
  if (singletonReferenceTarget(effect, effectDecisionRole) !== decisionTarget) return fail("GRAMMAR_INVALID", "effect must reference the exact same decision as consumption")
  const singleton = singletonReferenceTarget
  const equal = (left: CanonicalAtomV2, leftRole: string, right: CanonicalAtomV2, rightRole: string): boolean => {
    const leftTarget = singleton(left, leftRole)
    const rightTarget = singleton(right, rightRole)
    return leftTarget !== undefined && leftTarget === rightTarget
  }
  const pointsTo = (atom: CanonicalAtomV2, role: string, target: CanonicalAtomV2): boolean => singleton(atom, role) === keyId(target.key)
  const resolve = (atom: CanonicalAtomV2, role: string, kind: string): CanonicalAtomV2 | undefined => {
    const target = singleton(atom, role)
    const resolved = target === undefined ? undefined : preState.atoms.find((candidate) => keyId(candidate.key) === target)
    return resolved?.kind === `hswm:dnrd5:v2:${kind}` ? resolved : undefined
  }
  const contains = (atom: CanonicalAtomV2, role: string, target: CanonicalAtomV2): boolean => atom.references.some((reference) => reference.referenceType === DNRD5_V2_REFERENCE_TYPE && reference.role === `role:dnrd5:v2:${role}` && keyId(reference.target) === keyId(target.key))
  const targets = (atom: CanonicalAtomV2, role: string): ReadonlyArray<string> => atom.references
    .filter((reference) => reference.referenceType === DNRD5_V2_REFERENCE_TYPE && reference.role === `role:dnrd5:v2:${role}`)
    .map((reference) => keyId(reference.target))
  const sameFour = (left: ReadonlyArray<string>, right: ReadonlyArray<string>): boolean => left.length === 4 && right.length === 4 && new Set(left).size === 4 && new Set(right).size === 4 && left.every((target) => right.includes(target))
  // The batch chronology establishes typed reachability.  These comparisons
  // additionally bind the authority and semantic subject of this particular
  // effect to its one chosen decision, preventing a schema-valid cross-wire.
  if (!equal(consumption, "grant", preDecision, "grant") || !equal(consumption, "capability", preDecision, "capability") || !equal(consumption, "revocation", preDecision, "revocation")) {
    return fail("GRAMMAR_INVALID", "capability consumption authority must exactly equal its chosen decision")
  }
  const grant = resolve(preDecision, "grant", "grant_snapshot")
  const authorization = resolve(preDecision, "authorization", "authorization_decision")
  const capability = resolve(preDecision, "capability", "capability_issuance")
  const revocation = resolve(preDecision, "revocation", "revocation_status")
  const policy = grant === undefined ? undefined : resolve(grant, "policy", "permit_policy")
  if (grant === undefined || authorization === undefined || capability === undefined || revocation === undefined || policy === undefined) return fail("GRAMMAR_INVALID", "decision authority chain must resolve to exact valid preState atoms")
  if (!pointsTo(grant, "authorization", authorization) || !pointsTo(grant, "capability", capability) || !pointsTo(grant, "revocation", revocation) || !pointsTo(capability, "authorization", authorization) || !pointsTo(capability, "policy", policy) || !pointsTo(revocation, "authorization", authorization) || !pointsTo(revocation, "capability", capability) || !pointsTo(authorization, "policy", policy)) {
    return fail("GRAMMAR_INVALID", "decision authority chain is internally cross-wired")
  }
  const restorePolicy = disposition === undefined
    ? resolve(preDecision, "policy", "restore_policy")
    : resolve(disposition, "restore-policy", "restore_policy")
  if (restorePolicy === undefined || !pointsTo(restorePolicy, "policy", policy) || !pointsTo(restorePolicy, "capability", capability)) return fail("GRAMMAR_INVALID", "effect restore policy must bind the exact decision authority chain")
  if (disposition !== undefined) {
    if (!equal(disposition, "proposal", preDecision, "proposal") || !pointsTo(disposition, "revision-admission-decision", preDecision) || !pointsTo(disposition, "effect-consumption", consumption)) {
      return fail("GRAMMAR_INVALID", "admit disposition must exactly bind the decision proposal and same-batch consumption")
    }
    const proposal = resolve(preDecision, "proposal", "revision_proposal")
    const validation = resolve(preDecision, "validation", "candidate_validation")
    const credit = resolve(preDecision, "credit", "credit_decision")
    const block = resolve(preDecision, "block", "block_spec")
    const assignment = resolve(preDecision, "assignment", "block_assignment")
    const fork = resolve(preDecision, "fork", "fork_incidence")
    const forkW0 = fork === undefined ? undefined : resolve(fork, "w0", "w0_snapshot")
    const feedback = proposal === undefined ? undefined : resolve(proposal, "feedback", "feedback_assignment")
    const trajectory = proposal === undefined ? undefined : resolve(proposal, "trajectory", "trajectory_seal")
    const activation = trajectory === undefined ? undefined : resolve(trajectory, "activation", "episode_activation")
    const activationW0 = activation === undefined ? undefined : resolve(activation, "w0", "w0_snapshot")
    const trajectoryW0 = trajectory === undefined ? undefined : resolve(trajectory, "w0", "w0_snapshot")
    const trajectoryContract = trajectory === undefined ? undefined : resolve(trajectory, "contract", "trajectory_contract")
    const activationProbe = activation === undefined ? undefined : resolve(activation, "probe", "probe_commitment")
    const assignmentForks = assignment === undefined ? [] : targets(assignment, "fork")
    const activationForks = activation === undefined ? [] : targets(activation, "fork")
    const assignmentForksShareW0 = assignmentForks.every((forkTarget) => {
      const candidate = preState.atoms.find((atom) => keyId(atom.key) === forkTarget)
      return candidate?.kind === "hswm:dnrd5:v2:fork_incidence" && singleton(candidate, "w0") === (activationW0 === undefined ? undefined : keyId(activationW0.key))
    })
    if (proposal === undefined || validation === undefined || credit === undefined || block === undefined || assignment === undefined || fork === undefined || forkW0 === undefined || feedback === undefined || trajectory === undefined || activation === undefined || activationW0 === undefined || trajectoryW0 === undefined || trajectoryContract === undefined || activationProbe === undefined) return fail("GRAMMAR_INVALID", "admit decision subject chain must resolve to exact valid preState atoms")
    if (!pointsTo(validation, "proposal", proposal) || !pointsTo(credit, "proposal", proposal) || !pointsTo(credit, "grant", grant) || !pointsTo(credit, "feedback", feedback) || !pointsTo(credit, "trajectory", trajectory) || !pointsTo(feedback, "fork", fork) || !pointsTo(feedback, "assignment", assignment) || !equal(credit, "credit-source", feedback, "source") || !pointsTo(assignment, "block-spec", block) || !equal(assignment, "randomness", block, "randomness") || !contains(assignment, "fork", fork) || !pointsTo(forkW0, "block-spec", block) || !pointsTo(trajectoryContract, "activation", activation) || !pointsTo(activation, "block-spec", block) || !pointsTo(activation, "assignment", assignment) || !equal(activation, "evaluator", block, "evaluator") || !pointsTo(activationProbe, "block-spec", block) || !equal(activationProbe, "randomness", block, "randomness") || !pointsTo(activationW0, "block-spec", block) || keyId(trajectoryW0.key) !== keyId(activationW0.key) || keyId(forkW0.key) !== keyId(activationW0.key) || !sameFour(assignmentForks, activationForks) || !assignmentForksShareW0) {
      return fail("GRAMMAR_INVALID", "admit decision subject chain is internally cross-wired")
    }
  } else {
    if (!equal(restore!, "w0", preDecision, "w0") || !equal(restore!, "grant", preDecision, "grant") || !equal(restore!, "policy", preDecision, "policy") || !equal(restore!, "staging-successor", preDecision, "staging-successor") || !pointsTo(restore!, "decision", preDecision) || !pointsTo(restore!, "consumption", consumption)) {
      return fail("GRAMMAR_INVALID", "restore transaction must exactly bind the rollback decision and same-batch consumption")
    }
    const block = resolve(preDecision, "block", "block_spec")
    const assignment = resolve(preDecision, "assignment", "block_assignment")
    const fork = resolve(preDecision, "fork", "fork_incidence")
    const w0 = resolve(preDecision, "w0", "w0_snapshot")
    const stagingSuccessor = resolve(preDecision, "staging-successor", "macro_disposition")
    const stagingReceipt = resolve(preDecision, "staging-receipt", "revision_transition_receipt")
    const stagingDecision = stagingSuccessor === undefined ? undefined : resolve(stagingSuccessor, "revision-admission-decision", "revision_admission_decision")
    const stagingConsumption = stagingSuccessor === undefined ? undefined : resolve(stagingSuccessor, "effect-consumption", "capability_consumption")
    const evidenceConsumption = stagingReceipt === undefined ? undefined : resolve(stagingReceipt, "evidence-consumption", "evidence_seal_consumption")
    if (block === undefined || assignment === undefined || fork === undefined || w0 === undefined || stagingSuccessor === undefined || stagingReceipt === undefined || stagingDecision === undefined || stagingConsumption === undefined || evidenceConsumption === undefined) return fail("GRAMMAR_INVALID", "rollback staging chain must resolve to exact valid preState atoms")
    if (!pointsTo(stagingReceipt, "successor", stagingSuccessor) || !pointsTo(stagingReceipt, "decision", stagingDecision) || !pointsTo(stagingReceipt, "effect-consumption", stagingConsumption) || !pointsTo(stagingConsumption, "decision", stagingDecision) || !pointsTo(evidenceConsumption, "purpose", stagingDecision) || !pointsTo(stagingDecision, "block", block) || !pointsTo(stagingDecision, "assignment", assignment) || !pointsTo(stagingDecision, "fork", fork) || !pointsTo(assignment, "block-spec", block) || !contains(assignment, "fork", fork) || !pointsTo(w0, "block-spec", block) || !pointsTo(fork, "w0", w0)) {
      return fail("GRAMMAR_INVALID", "rollback staging receipt or structural scope is internally cross-wired")
    }
  }
  return Either.right(undefined)
}

export interface Dnrd5V2EffectCommandCandidateValidated {
  readonly status: "EFFECT_COMMAND_CANDIDATE_VALIDATED_NOT_SUBMITTED"
  readonly topology: Dnrd5V2AtomicBatchChronology
}

/**
 * Pure pre-CAS effect grammar check. It shares the exact topology and
 * cross-wire rules used again by the raw-record verifier after publication.
 */
export const validateDnrd5V2EffectCommandCandidate = (
  schema: HSWMCanonicalSchemaV2,
  preState: CanonicalAtomV2State,
  command: CommitCanonicalAtomsV2Command
): Either.Either<Dnrd5V2EffectCommandCandidateValidated, Dnrd5V2RecordBoundEffectError> => {
  if (Either.isLeft(validateDnrd5V2CanonicalSchema(schema))) {
    return fail("SCHEMA_INVALID", "requires exact DNRD-5 successor schema")
  }
  const topology = validateDnrd5V2AtomicBatchChronology(schema, preState, command)
  if (Either.isLeft(topology)) {
    return fail("BATCH_INVALID", `${topology.left.code}: ${topology.left.detail}`)
  }
  const grammar = validateGrammar(preState, command)
  if (Either.isLeft(grammar)) return Either.left(grammar.left)
  return Either.right(Object.freeze({
    status: "EFFECT_COMMAND_CANDIDATE_VALIDATED_NOT_SUBMITTED" as const,
    topology: topology.right
  }))
}

/** Recomputes a single effect record from actual command, state and journal bytes. */
export const validateDnrd5V2RecordBoundEffect = (input: Dnrd5V2RecordBoundEffectInput): Either.Either<Dnrd5V2RecordBoundEffectValidated, Dnrd5V2RecordBoundEffectError> => {
  const candidate = validateDnrd5V2EffectCommandCandidate(
    input.schema,
    input.preState,
    input.command
  )
  if (Either.isLeft(candidate)) return Either.left(candidate.left)
  if (input.record.schema.schemaVersion !== input.schema.schemaVersion || input.record.schema.content.sha256 !== input.predecessor.schemaContentSha256) return fail("PREDECESSOR_INVALID", "record schema binding differs from the predecessor's exact schema content")
  if (input.record.journalLineageId !== input.predecessor.journalLineageId || !descriptorSame(input.record.predecessor, input.predecessor.descriptor) || input.record.stateRevision !== input.preState.revision + 1) return fail("PREDECESSOR_INVALID", "record does not bind the exact immediate predecessor")
  const before = canonicalAtomV2StateSha256(input.preState)
  if (Either.isLeft(before) || (Either.isRight(before) && input.record.previousStateSha256 !== before.right)) return fail("STATE_INVALID", "record prior state hash does not equal actual preState")
  const expectedReceipt = makeCanonicalAtomV2AcceptedReceipt(input.command, input.preState.revision, candidate.right.topology.nextState.revision)
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
  if (!same(applied.right.state, candidate.right.topology.nextState)) return fail("STATE_INVALID", "journal replay next state differs from generic batch replay")
  const canonicalBytes = canonicalAtomV2StateJournalRecordBytes(input.record)
  if (Either.isLeft(canonicalBytes) || (Either.isRight(canonicalBytes) && (canonicalBytes.right.byteLength !== input.recordBytes.byteLength || !canonicalBytes.right.every((v, i) => v === input.recordBytes[i])))) return fail("RECORD_INVALID", "supplied record bytes are not exact canonical journal bytes")
  const descriptor = describeCanonicalAtomV2StateJournalRecord(input.record)
  if (Either.isLeft(descriptor) || (Either.isRight(descriptor) && !descriptorSame(descriptor.right, input.recordDescriptor))) return fail("DESCRIPTOR_INVALID", "record descriptor is not recomputed from actual record bytes")
  if (input.usedRecordDescriptorSha256s.includes(input.recordDescriptor.sha256)) return fail("REPLAY_INVALID", "record descriptor was already used in this effect scope")
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
  return Either.right(Object.freeze({ status: "RECORD_BOUND_EFFECT_VALIDATED_NOT_PERMIT_OR_OCCURRENCE", topology: candidate.right.topology, nextState: applied.right.state, effectRecordDescriptor: descriptor.right, deterministicFuturePostcommitReceiptIdentity: identity.right }))
}
