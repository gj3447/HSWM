import { Data, Either, Schema } from "effect"

import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  CanonicalAtomV2ContentDescriptorSchema,
  CanonicalAtomV2SchemaContentBindingSchema,
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  CanonicalAtomV2KeySchema,
  CommitCanonicalAtomsV2CommandSchema,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command
} from "./canonical-atom-v2-schema.js"

/**
 * A bounded vocabulary for preserving transition evidence. It deliberately
 * cannot issue a Permit, establish truth, credit learning, or admit an atom.
 */
export const HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION =
  "hswm-canonical-transition-evidence/v1" as const
export const HSWM_CANONICAL_TRANSITION_EVIDENCE_BUNDLE_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-transition-evidence-v1+json" as const
export const HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-transition-evidence-record-v1+json" as const
export const HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-transition-proposal-v1+json" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const CanonicalInstant = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

export interface CanonicalAtomV2EvidencePrincipal {
  readonly address: string
}

export const CanonicalAtomV2EvidencePrincipalSchema: Schema.Schema<CanonicalAtomV2EvidencePrincipal> =
  Schema.Struct({ address: Identifier })

export interface CanonicalAtomV2EvidenceSubject {
  readonly subject: CanonicalAtomV2Key
  readonly relation: string
}

export const CanonicalAtomV2EvidenceSubjectSchema: Schema.Schema<CanonicalAtomV2EvidenceSubject> =
  Schema.Struct({
    subject: CanonicalAtomV2KeySchema,
    relation: Identifier
  })

export interface CanonicalAtomV2EvidenceCustody {
  readonly custodian: CanonicalAtomV2EvidencePrincipal
  readonly custody: "CONTENT" | "JOURNAL" | "TRACE" | "OUTCOME" | "QUARANTINE"
  readonly object: CanonicalAtomV2ContentDescriptor
  readonly evidence: CanonicalAtomV2ContentDescriptor
}

export const CanonicalAtomV2EvidenceCustodySchema: Schema.Schema<CanonicalAtomV2EvidenceCustody> =
  Schema.Struct({
    custodian: CanonicalAtomV2EvidencePrincipalSchema,
    custody: Schema.Literal("CONTENT", "JOURNAL", "TRACE", "OUTCOME", "QUARANTINE"),
    object: CanonicalAtomV2ContentDescriptorSchema,
    evidence: CanonicalAtomV2ContentDescriptorSchema
  })

export interface CanonicalAtomV2EvidenceOwnerBinding {
  readonly write: CanonicalAtomV2Key
  readonly owner: CanonicalAtomV2EvidencePrincipal
}

export const CanonicalAtomV2EvidenceOwnerBindingSchema: Schema.Schema<CanonicalAtomV2EvidenceOwnerBinding> =
  Schema.Struct({
    write: CanonicalAtomV2KeySchema,
    owner: CanonicalAtomV2EvidencePrincipalSchema
  })

/** Named predicates are deliberately separate even when their addresses match. */
export interface CanonicalAtomV2TransitionRoleBindings {
  readonly owners: ReadonlyArray<CanonicalAtomV2EvidenceOwnerBinding>
  readonly claimant: CanonicalAtomV2EvidencePrincipal
  readonly subjects: ReadonlyArray<CanonicalAtomV2EvidenceSubject>
  readonly custodians: ReadonlyArray<CanonicalAtomV2EvidenceCustody>
  readonly authorizer: CanonicalAtomV2EvidencePrincipal
}

export const CanonicalAtomV2TransitionRoleBindingsSchema: Schema.Schema<CanonicalAtomV2TransitionRoleBindings> =
  Schema.Struct({
    owners: Schema.Array(CanonicalAtomV2EvidenceOwnerBindingSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(64)
    ),
    claimant: CanonicalAtomV2EvidencePrincipalSchema,
    subjects: Schema.Array(CanonicalAtomV2EvidenceSubjectSchema).pipe(Schema.maxItems(256)),
    custodians: Schema.Array(CanonicalAtomV2EvidenceCustodySchema).pipe(Schema.maxItems(64)),
    authorizer: CanonicalAtomV2EvidencePrincipalSchema
  })

/** A represented decision; its label makes it impossible to reinterpret as a current Permit. */
export interface CanonicalAtomV2AuthorizationDecisionEvidence {
  readonly _tag: "CanonicalAtomV2AuthorizationDecisionEvidence"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  readonly authorizationRef: string
  /** A claimed pre-existing read key; state membership needs a later resolver. */
  readonly decisionRef: CanonicalAtomV2Key
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly claimedPredecessor: CanonicalAtomV2ContentDescriptor
  readonly claimedPredecessorStateRevision: number
  readonly proposal: CanonicalAtomV2ContentDescriptor
  readonly claimant: CanonicalAtomV2EvidencePrincipal
  readonly subjects: ReadonlyArray<CanonicalAtomV2EvidenceSubject>
  readonly authorizer: CanonicalAtomV2EvidencePrincipal
  readonly scope: string
  readonly decision: "GRANTED" | "DENIED"
  readonly decidedAt: string
  readonly notBefore: string
  readonly expiresAt: string
  readonly decisionEvidence: CanonicalAtomV2ContentDescriptor
  readonly revocationStatus: "CHECKED_NOT_REVOKED" | "REVOKED" | "NOT_CHECKED"
  readonly revocationCheckedAt: string | null
  readonly revokedAt: string | null
  readonly revocationEvidence: CanonicalAtomV2ContentDescriptor | null
  readonly permitStatus: "REPRESENTED_NOT_CANONICAL_PERMIT"
}

export const CanonicalAtomV2AuthorizationDecisionEvidenceSchema: Schema.Schema<CanonicalAtomV2AuthorizationDecisionEvidence> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2AuthorizationDecisionEvidence"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION),
    authorizationRef: Identifier,
    decisionRef: CanonicalAtomV2KeySchema,
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    claimedPredecessor: CanonicalAtomV2ContentDescriptorSchema,
    claimedPredecessorStateRevision: SafeInteger,
    proposal: CanonicalAtomV2ContentDescriptorSchema,
    claimant: CanonicalAtomV2EvidencePrincipalSchema,
    subjects: Schema.Array(CanonicalAtomV2EvidenceSubjectSchema).pipe(
      Schema.maxItems(256)
    ),
    authorizer: CanonicalAtomV2EvidencePrincipalSchema,
    scope: Identifier,
    decision: Schema.Literal("GRANTED", "DENIED"),
    decidedAt: CanonicalInstant,
    notBefore: CanonicalInstant,
    expiresAt: CanonicalInstant,
    decisionEvidence: CanonicalAtomV2ContentDescriptorSchema,
    revocationStatus: Schema.Literal(
      "CHECKED_NOT_REVOKED",
      "REVOKED",
      "NOT_CHECKED"
    ),
    revocationCheckedAt: Schema.NullOr(CanonicalInstant),
    revokedAt: Schema.NullOr(CanonicalInstant),
    revocationEvidence: Schema.NullOr(CanonicalAtomV2ContentDescriptorSchema),
    permitStatus: Schema.Literal("REPRESENTED_NOT_CANONICAL_PERMIT")
  })

export interface CanonicalAtomV2SealedTrajectoryEvent {
  readonly sequence: number
  readonly kind: "INPUT" | "ACTION" | "TOOL_RESULT" | "READOUT"
  readonly content: CanonicalAtomV2ContentDescriptor
}

export const CanonicalAtomV2SealedTrajectoryEventSchema: Schema.Schema<CanonicalAtomV2SealedTrajectoryEvent> =
  Schema.Struct({
    sequence: SafeInteger,
    kind: Schema.Literal("INPUT", "ACTION", "TOOL_RESULT", "READOUT"),
    content: CanonicalAtomV2ContentDescriptorSchema
  })

export interface CanonicalAtomV2ProvenanceClaim {
  readonly collector: CanonicalAtomV2EvidencePrincipal
  readonly method: string
  readonly collectedAt: string
  readonly source: CanonicalAtomV2ContentDescriptor
  readonly status: "CLAIMED_NOT_TRUTH"
}

export const CanonicalAtomV2ProvenanceClaimSchema: Schema.Schema<CanonicalAtomV2ProvenanceClaim> =
  Schema.Struct({
    collector: CanonicalAtomV2EvidencePrincipalSchema,
    method: Identifier,
    collectedAt: CanonicalInstant,
    source: CanonicalAtomV2ContentDescriptorSchema,
    status: Schema.Literal("CLAIMED_NOT_TRUTH")
  })

export interface CanonicalAtomV2SealedTrajectoryEvidence {
  readonly _tag: "CanonicalAtomV2SealedTrajectoryEvidence"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  readonly traceId: string
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly claimedPredecessor: CanonicalAtomV2ContentDescriptor
  readonly claimedPredecessorStateRevision: number
  readonly proposal: CanonicalAtomV2ContentDescriptor
  readonly traceRef: CanonicalAtomV2Key
  readonly claimant: CanonicalAtomV2EvidencePrincipal
  readonly sealer: CanonicalAtomV2EvidencePrincipal
  readonly readSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly writeSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly events: ReadonlyArray<CanonicalAtomV2SealedTrajectoryEvent>
  readonly sealedAt: string
  readonly provenance: CanonicalAtomV2ProvenanceClaim
}

export const CanonicalAtomV2SealedTrajectoryEvidenceSchema: Schema.Schema<CanonicalAtomV2SealedTrajectoryEvidence> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2SealedTrajectoryEvidence"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION),
    traceId: Identifier,
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    claimedPredecessor: CanonicalAtomV2ContentDescriptorSchema,
    claimedPredecessorStateRevision: SafeInteger,
    proposal: CanonicalAtomV2ContentDescriptorSchema,
    traceRef: CanonicalAtomV2KeySchema,
    claimant: CanonicalAtomV2EvidencePrincipalSchema,
    sealer: CanonicalAtomV2EvidencePrincipalSchema,
    readSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.maxItems(512)),
    writeSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.minItems(1), Schema.maxItems(64)),
    events: Schema.Array(CanonicalAtomV2SealedTrajectoryEventSchema).pipe(Schema.minItems(1), Schema.maxItems(4096)),
    sealedAt: CanonicalInstant,
    provenance: CanonicalAtomV2ProvenanceClaimSchema
  })

export interface CanonicalAtomV2TransitionEffectEvidence {
  readonly _tag: "CanonicalAtomV2TransitionEffectEvidence"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly claimedPredecessor: CanonicalAtomV2ContentDescriptor
  readonly claimedPredecessorStateRevision: number
  readonly proposal: CanonicalAtomV2ContentDescriptor
  readonly authorization: CanonicalAtomV2ContentDescriptor
  readonly trajectory: CanonicalAtomV2ContentDescriptor
  readonly referenceReceipt: CanonicalAtomV2ContentDescriptor
  readonly readSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly writeSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly traceRef: CanonicalAtomV2Key
  readonly actorClaim: string
  readonly authorizationRef: string
  readonly scope: string
  readonly decidedAt: string
  readonly decision: "ACCEPTED"
  readonly provenanceSha256: string
  readonly guardStatus: "REFERENCE_RECEIPT_DESCRIPTOR_BOUND_NOT_CANONICAL_PERMIT"
  readonly effectStatus: "REFERENCE_EFFECT_NOT_EXTERNAL_EFFECT"
}

export const CanonicalAtomV2TransitionEffectEvidenceSchema: Schema.Schema<CanonicalAtomV2TransitionEffectEvidence> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2TransitionEffectEvidence"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    claimedPredecessor: CanonicalAtomV2ContentDescriptorSchema,
    claimedPredecessorStateRevision: SafeInteger,
    proposal: CanonicalAtomV2ContentDescriptorSchema,
    authorization: CanonicalAtomV2ContentDescriptorSchema,
    trajectory: CanonicalAtomV2ContentDescriptorSchema,
    referenceReceipt: CanonicalAtomV2ContentDescriptorSchema,
    readSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.maxItems(512)),
    writeSet: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.minItems(1), Schema.maxItems(64)),
    traceRef: CanonicalAtomV2KeySchema,
    actorClaim: Identifier,
    authorizationRef: Identifier,
    scope: Identifier,
    decidedAt: CanonicalInstant,
    decision: Schema.Literal("ACCEPTED"),
    provenanceSha256: Sha256,
    guardStatus: Schema.Literal("REFERENCE_RECEIPT_DESCRIPTOR_BOUND_NOT_CANONICAL_PERMIT"),
    effectStatus: Schema.Literal("REFERENCE_EFFECT_NOT_EXTERNAL_EFFECT")
  })

export interface CanonicalAtomV2OutcomeObservationEvidence {
  readonly _tag: "CanonicalAtomV2OutcomeObservationEvidence"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly proposal: CanonicalAtomV2ContentDescriptor
  readonly trajectory: CanonicalAtomV2ContentDescriptor
  readonly effect: CanonicalAtomV2ContentDescriptor
  readonly evaluator: CanonicalAtomV2EvidencePrincipal
  readonly observedAt: string
  readonly observation: CanonicalAtomV2ContentDescriptor | null
  readonly outcome: "OBSERVED" | "FAILED" | "UNKNOWN"
  readonly provenance: CanonicalAtomV2ProvenanceClaim
  readonly independence: "UNKNOWN" | "DECLARED_ROLE_SEPARATION_NOT_PROVEN"
  readonly independenceEvidence: CanonicalAtomV2ContentDescriptor | null
  readonly outcomeStatus: "REPRESENTED_NOT_CAUSAL_CREDIT"
}

export const CanonicalAtomV2OutcomeObservationEvidenceSchema: Schema.Schema<CanonicalAtomV2OutcomeObservationEvidence> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2OutcomeObservationEvidence"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    proposal: CanonicalAtomV2ContentDescriptorSchema,
    trajectory: CanonicalAtomV2ContentDescriptorSchema,
    effect: CanonicalAtomV2ContentDescriptorSchema,
    evaluator: CanonicalAtomV2EvidencePrincipalSchema,
    observedAt: CanonicalInstant,
    observation: Schema.NullOr(CanonicalAtomV2ContentDescriptorSchema),
    outcome: Schema.Literal("OBSERVED", "FAILED", "UNKNOWN"),
    provenance: CanonicalAtomV2ProvenanceClaimSchema,
    independence: Schema.Literal("UNKNOWN", "DECLARED_ROLE_SEPARATION_NOT_PROVEN"),
    independenceEvidence: Schema.NullOr(CanonicalAtomV2ContentDescriptorSchema),
    outcomeStatus: Schema.Literal("REPRESENTED_NOT_CAUSAL_CREDIT")
  })

export interface CanonicalAtomV2TransitionDispositionEvidence {
  readonly _tag: "CanonicalAtomV2TransitionDispositionEvidence"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  readonly disposition: "REJECTED" | "QUARANTINED"
  readonly stage: "INGRESS" | "SCHEMA" | "OWNER" | "PERMIT" | "TRACE" | "EFFECT" | "OUTCOME" | "LEARNING"
  readonly reason: string
  readonly observedAt: string
  readonly candidate: CanonicalAtomV2ContentDescriptor
  readonly evidence: CanonicalAtomV2ContentDescriptor
  readonly decider: CanonicalAtomV2EvidencePrincipal
  readonly custodian: CanonicalAtomV2EvidencePrincipal
  readonly retention: CanonicalAtomV2ContentDescriptor | null
  readonly admissionStatus: "NOT_ADMITTED_NOT_PERMITTED_NOT_LEARNING"
}

export const CanonicalAtomV2TransitionDispositionEvidenceSchema: Schema.Schema<CanonicalAtomV2TransitionDispositionEvidence> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2TransitionDispositionEvidence"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION),
    disposition: Schema.Literal("REJECTED", "QUARANTINED"),
    stage: Schema.Literal(
      "INGRESS",
      "SCHEMA",
      "OWNER",
      "PERMIT",
      "TRACE",
      "EFFECT",
      "OUTCOME",
      "LEARNING"
    ),
    reason: Identifier,
    observedAt: CanonicalInstant,
    candidate: CanonicalAtomV2ContentDescriptorSchema,
    evidence: CanonicalAtomV2ContentDescriptorSchema,
    decider: CanonicalAtomV2EvidencePrincipalSchema,
    custodian: CanonicalAtomV2EvidencePrincipalSchema,
    retention: Schema.NullOr(CanonicalAtomV2ContentDescriptorSchema),
    admissionStatus: Schema.Literal("NOT_ADMITTED_NOT_PERMITTED_NOT_LEARNING")
  })

export type CanonicalAtomV2TransitionEvidenceRecord =
  | CanonicalAtomV2AuthorizationDecisionEvidence
  | CanonicalAtomV2SealedTrajectoryEvidence
  | CanonicalAtomV2TransitionEffectEvidence
  | CanonicalAtomV2OutcomeObservationEvidence
  | CanonicalAtomV2TransitionDispositionEvidence

export const CanonicalAtomV2TransitionEvidenceRecordSchema: Schema.Schema<CanonicalAtomV2TransitionEvidenceRecord> =
  Schema.Union(
    CanonicalAtomV2AuthorizationDecisionEvidenceSchema,
    CanonicalAtomV2SealedTrajectoryEvidenceSchema,
    CanonicalAtomV2TransitionEffectEvidenceSchema,
    CanonicalAtomV2OutcomeObservationEvidenceSchema,
    CanonicalAtomV2TransitionDispositionEvidenceSchema
  )

export interface CanonicalAtomV2TransitionEvidenceBundle {
  readonly _tag: "CanonicalAtomV2TransitionEvidenceBundle"
  readonly contractVersion: typeof HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly claimedPredecessor: CanonicalAtomV2ContentDescriptor
  readonly claimedPredecessorStateRevision: number
  /** The exact existing v2 proposal; it is evidence input, not an admitted transition. */
  readonly proposal: CommitCanonicalAtomsV2Command
  readonly proposalDescriptor: CanonicalAtomV2ContentDescriptor
  readonly roles: CanonicalAtomV2TransitionRoleBindings
  readonly authorization: CanonicalAtomV2AuthorizationDecisionEvidence
  readonly trajectory: CanonicalAtomV2SealedTrajectoryEvidence
  readonly effect: CanonicalAtomV2TransitionEffectEvidence | null
  readonly outcome: CanonicalAtomV2OutcomeObservationEvidence | null
  readonly disposition: CanonicalAtomV2TransitionDispositionEvidence | null
}

export const CanonicalAtomV2TransitionEvidenceBundleSchema: Schema.Schema<CanonicalAtomV2TransitionEvidenceBundle> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2TransitionEvidenceBundle"),
    contractVersion: Schema.Literal(HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    claimedPredecessor: CanonicalAtomV2ContentDescriptorSchema,
    claimedPredecessorStateRevision: SafeInteger,
    proposal: CommitCanonicalAtomsV2CommandSchema,
    proposalDescriptor: CanonicalAtomV2ContentDescriptorSchema,
    roles: CanonicalAtomV2TransitionRoleBindingsSchema,
    authorization: CanonicalAtomV2AuthorizationDecisionEvidenceSchema,
    trajectory: CanonicalAtomV2SealedTrajectoryEvidenceSchema,
    effect: Schema.NullOr(CanonicalAtomV2TransitionEffectEvidenceSchema),
    outcome: Schema.NullOr(CanonicalAtomV2OutcomeObservationEvidenceSchema),
    disposition: Schema.NullOr(CanonicalAtomV2TransitionDispositionEvidenceSchema)
  })

export class CanonicalAtomV2TransitionEvidenceError extends Data.TaggedError("CanonicalAtomV2TransitionEvidenceError")<{
  readonly code:
      | "CANONICAL_ENCODING_INVALID"
      | "CROSS_FIELD_MISMATCH"
      | "DESCRIPTOR_INVALID"
      | "DISPOSITION_INVALID"
      | "EVIDENCE_INVALID"
      | "OUTCOME_INVALID"
      | "ROLE_BINDING_INVALID"
      | "TIME_INVALID"
      | "TRACE_INVALID"
  readonly detail: string
}> {}

export type CanonicalAtomV2AuthorizationEvidenceClassification =
  | "EVIDENCE_INVALID_NOT_PERMIT"
  | "EVIDENCE_DECISION_NOT_YET_MADE_NOT_PERMIT"
  | "EVIDENCE_GRANTED_NOT_PERMIT"
  | "EVIDENCE_DENIED_NOT_PERMIT"
  | "EVIDENCE_EXPIRED_NOT_PERMIT"
  | "EVIDENCE_NOT_YET_VALID_NOT_PERMIT"
  | "EVIDENCE_REVOKED_NOT_PERMIT"
  | "EVIDENCE_REVOCATION_CHECK_FUTURE_NOT_PERMIT"
  | "EVIDENCE_REVOCATION_CHECK_STALE_NOT_PERMIT"
  | "EVIDENCE_REVOCATION_UNCHECKED_NOT_PERMIT"

const fail = (code: CanonicalAtomV2TransitionEvidenceError["code"], detail: string) =>
  Either.left(new CanonicalAtomV2TransitionEvidenceError({ code, detail }))

const sameKey = (left: CanonicalAtomV2Key, right: CanonicalAtomV2Key): boolean =>
  canonicalAtomV2KeyId(left) === canonicalAtomV2KeyId(right)
const sameKeys = (
  left: ReadonlyArray<CanonicalAtomV2Key>,
  right: ReadonlyArray<CanonicalAtomV2Key>
): boolean =>
  left.length === right.length &&
  left.every(
    (key, index) => right[index] !== undefined && sameKey(key, right[index]!)
  )
const sameBinding = (
  left: CanonicalAtomV2SchemaContentBinding,
  right: CanonicalAtomV2SchemaContentBinding
): boolean =>
  left.schemaVersion === right.schemaVersion &&
  sameCanonicalAtomV2ContentDescriptor(left.content, right.content)
const validInstant = (value: string): boolean =>
  Number.isFinite(Date.parse(value)) &&
  new Date(Date.parse(value)).toISOString() === value
const descriptor = (
  value: unknown
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2TransitionEvidenceError> =>
  describeCanonicalAtomV2TransitionEvidenceRecord(value)

const proposalDescriptor = (
  proposal: CommitCanonicalAtomsV2Command
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2TransitionEvidenceError> => {
  const bytes = canonicalJsonBytes(proposal)
  if (Either.isLeft(bytes)) return fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
  const made = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(made) ? fail("DESCRIPTOR_INVALID", made.left.detail) : Either.right(made.right)
}

const strictlyOrdered = <A>(values: ReadonlyArray<A>, id: (value: A) => string): boolean =>
  values.every((value, index) => index === 0 || id(values[index - 1]!) < id(value))
const subjectId = (subject: CanonicalAtomV2EvidenceSubject): string =>
  `${canonicalAtomV2KeyId(subject.subject)}|${subject.relation}`
const custodyId = (custody: CanonicalAtomV2EvidenceCustody): string =>
  [
    custody.custodian.address,
    custody.custody,
    custody.object.mediaType,
    custody.object.byteLength,
    custody.object.sha256,
    custody.evidence.mediaType,
    custody.evidence.byteLength,
    custody.evidence.sha256
  ].join("|")

const revocationClaimIsCoherent = (
  authorization: CanonicalAtomV2AuthorizationDecisionEvidence
): boolean => {
  const {
    revocationStatus,
    revocationCheckedAt,
    revokedAt,
    revocationEvidence
  } = authorization
  if (revocationStatus === "NOT_CHECKED") {
    return (
      revocationCheckedAt === null &&
      revokedAt === null &&
      revocationEvidence === null
    )
  }
  if (
    revocationCheckedAt === null ||
    !validInstant(revocationCheckedAt) ||
    revocationEvidence === null
  ) {
    return false
  }
  if (revocationStatus === "CHECKED_NOT_REVOKED") return revokedAt === null
  return (
    revokedAt !== null &&
    validInstant(revokedAt) &&
    Date.parse(revokedAt) <= Date.parse(revocationCheckedAt)
  )
}

export const snapshotCanonicalAtomV2TransitionEvidenceBundle = (
  value: CanonicalAtomV2TransitionEvidenceBundle
): CanonicalAtomV2TransitionEvidenceBundle => deepFreeze(structuredClone(value))

const deepFreeze = <A>(value: A): A => {
  if (typeof value === "object" && value !== null && !Object.isFrozen(value)) {
    Object.freeze(value)
    for (const nested of Object.values(value as Record<string, unknown>)) deepFreeze(nested)
  }
  return value
}

export const snapshotCanonicalAtomV2TransitionEvidenceRecord = (
  value: CanonicalAtomV2TransitionEvidenceRecord
): CanonicalAtomV2TransitionEvidenceRecord => deepFreeze(structuredClone(value))

export const validateCanonicalAtomV2TransitionEvidenceRecord = (
  input: unknown
): Either.Either<CanonicalAtomV2TransitionEvidenceRecord, CanonicalAtomV2TransitionEvidenceError> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2TransitionEvidenceRecordSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail(
      "EVIDENCE_INVALID",
      "evidence record violates the strict v1 structural contract"
    )
  }
  const record = snapshotCanonicalAtomV2TransitionEvidenceRecord(decoded.right)
  switch (record._tag) {
    case "CanonicalAtomV2AuthorizationDecisionEvidence":
      if (
        !validInstant(record.decidedAt) ||
        !validInstant(record.notBefore) ||
        !validInstant(record.expiresAt) ||
        Date.parse(record.notBefore) >= Date.parse(record.expiresAt) ||
        !revocationClaimIsCoherent(record) ||
        record.decisionRef.schemaVersion !== record.schema.schemaVersion ||
        record.decisionRef.atomUid !== record.authorizationRef ||
        !strictlyOrdered(record.subjects, subjectId) ||
        record.subjects.some(
          ({ subject }) => subject.schemaVersion !== record.schema.schemaVersion
        )
      ) {
        return fail(
          "EVIDENCE_INVALID",
          "authorization record has incoherent time, revocation, identity, subject, or schema claims"
        )
      }
      break
    case "CanonicalAtomV2SealedTrajectoryEvidence":
      if (
        !validInstant(record.sealedAt) ||
        !validInstant(record.provenance.collectedAt) ||
        Date.parse(record.provenance.collectedAt) > Date.parse(record.sealedAt) ||
        record.traceId !== record.traceRef.atomUid ||
        record.traceRef.schemaVersion !== record.schema.schemaVersion ||
        !strictlyOrdered(record.readSet, canonicalAtomV2KeyId) ||
        !strictlyOrdered(record.writeSet, canonicalAtomV2KeyId) ||
        [...record.readSet, ...record.writeSet].some(
          ({ schemaVersion }) => schemaVersion !== record.schema.schemaVersion
        ) ||
        !record.events.every((event, index) => event.sequence === index)
      ) {
        return fail(
          "TRACE_INVALID",
          "trajectory record has incoherent identity, chronology, schema, sets, or event order"
        )
      }
      break
    case "CanonicalAtomV2TransitionEffectEvidence":
      if (
        !validInstant(record.decidedAt) ||
        record.traceRef.schemaVersion !== record.schema.schemaVersion ||
        !strictlyOrdered(record.readSet, canonicalAtomV2KeyId) ||
        !strictlyOrdered(record.writeSet, canonicalAtomV2KeyId) ||
        [...record.readSet, ...record.writeSet].some(
          ({ schemaVersion }) => schemaVersion !== record.schema.schemaVersion
        )
      ) {
        return fail(
          "EVIDENCE_INVALID",
          "effect record has incoherent decision time, schema, trace, or read/write sets"
        )
      }
      break
    case "CanonicalAtomV2OutcomeObservationEvidence":
      if (
        !validInstant(record.observedAt) ||
        !validInstant(record.provenance.collectedAt) ||
        Date.parse(record.provenance.collectedAt) > Date.parse(record.observedAt) ||
        (record.outcome === "UNKNOWN") !== (record.observation === null) ||
        (record.independence === "UNKNOWN") !==
          (record.independenceEvidence === null)
      ) {
        return fail(
          "OUTCOME_INVALID",
          "outcome record has incoherent chronology, observation, or independence claims"
        )
      }
      break
    case "CanonicalAtomV2TransitionDispositionEvidence":
      if (
        !validInstant(record.observedAt) ||
        (record.disposition === "QUARANTINED") !== (record.retention !== null)
      ) {
        return fail(
          "DISPOSITION_INVALID",
          "disposition record has incoherent chronology or retention claims"
        )
      }
      break
  }
  return Either.right(record)
}

export const canonicalAtomV2TransitionEvidenceRecordBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2TransitionEvidenceError> => {
  const checked = validateCanonicalAtomV2TransitionEvidenceRecord(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const describeCanonicalAtomV2TransitionEvidenceRecord = (
  input: unknown
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2TransitionEvidenceError> => {
  const bytes = canonicalAtomV2TransitionEvidenceRecordBytes(input)
  if (Either.isLeft(bytes)) return Either.left(bytes.left)
  const made = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(made)
    ? fail("DESCRIPTOR_INVALID", made.left.detail)
    : Either.right(made.right)
}

export const decodeCanonicalAtomV2TransitionEvidenceRecordBytes = (
  input: Uint8Array
): Either.Either<CanonicalAtomV2TransitionEvidenceRecord, CanonicalAtomV2TransitionEvidenceError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = validateCanonicalAtomV2TransitionEvidenceRecord(parsed.right)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const canonical = canonicalAtomV2TransitionEvidenceRecordBytes(checked.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  if (
    canonical.right.byteLength !== input.byteLength ||
    !canonical.right.every((byte, index) => byte === input[index])
  ) {
    return fail(
      "CANONICAL_ENCODING_INVALID",
      "evidence record bytes are not the exact canonical v1 encoding"
    )
  }
  return Either.right(checked.right)
}

export const validateCanonicalAtomV2TransitionEvidenceBundle = (
  input: unknown
): Either.Either<CanonicalAtomV2TransitionEvidenceBundle, CanonicalAtomV2TransitionEvidenceError> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2TransitionEvidenceBundleSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail(
      "EVIDENCE_INVALID",
      "evidence bundle violates the strict v1 structural contract"
    )
  }
  const bundle = snapshotCanonicalAtomV2TransitionEvidenceBundle(decoded.right)
  const { roles, authorization, trajectory, effect, outcome, disposition } = bundle
  const roleSetsAreOrdered =
    strictlyOrdered(roles.owners, ({ write }) => canonicalAtomV2KeyId(write)) &&
    strictlyOrdered(roles.subjects, subjectId) &&
    strictlyOrdered(roles.custodians, custodyId)
  if (!roleSetsAreOrdered) {
    return fail(
      "ROLE_BINDING_INVALID",
      "role collections must be duplicate-free ascending canonical sets"
    )
  }
  const trajectorySetsAreOrdered =
    strictlyOrdered(trajectory.readSet, canonicalAtomV2KeyId) &&
    strictlyOrdered(trajectory.writeSet, canonicalAtomV2KeyId)
  if (!trajectorySetsAreOrdered) {
    return fail(
      "TRACE_INVALID",
      "trace read and write sets must be duplicate-free ascending canonical sets"
    )
  }
  if (!trajectory.events.every((event, index) => event.sequence === index)) {
    return fail(
      "TRACE_INVALID",
      "trajectory events must be exactly contiguous from sequence zero"
    )
  }
  const timestampsAreCanonical =
    validInstant(authorization.decidedAt) &&
    validInstant(authorization.notBefore) &&
    validInstant(authorization.expiresAt) &&
    validInstant(trajectory.sealedAt) &&
    validInstant(trajectory.provenance.collectedAt) &&
    (disposition === null || validInstant(disposition.observedAt)) &&
    (effect === null || validInstant(effect.decidedAt)) &&
    (outcome === null ||
      (validInstant(outcome.observedAt) &&
        validInstant(outcome.provenance.collectedAt)))
  if (!timestampsAreCanonical) {
    return fail("TIME_INVALID", "evidence timestamps must be real canonical instants")
  }
  if (Date.parse(authorization.notBefore) >= Date.parse(authorization.expiresAt)) {
    return fail(
      "TIME_INVALID",
      "authorization validity interval must be non-empty"
    )
  }
  if (!revocationClaimIsCoherent(authorization)) {
    return fail(
      "TIME_INVALID",
      "revocation evidence fields are not coherent with their claimed status"
    )
  }
  const exactProposal = proposalDescriptor(bundle.proposal)
  if (Either.isLeft(exactProposal)) return Either.left(exactProposal.left)
  if (
    !sameCanonicalAtomV2ContentDescriptor(
      bundle.proposalDescriptor,
      exactProposal.right
    )
  ) {
    return fail(
      "DESCRIPTOR_INVALID",
      "proposal descriptor does not match exact canonical proposal bytes"
    )
  }
  const proposalIdentityMatches =
    bundle.proposal.schemaVersion === bundle.schema.schemaVersion &&
    bundle.proposal.actorClaim === roles.claimant.address &&
    bundle.proposal.authorizationRef === authorization.authorizationRef &&
    bundle.proposal.scope === authorization.scope &&
    bundle.proposal.traceRef !== null &&
    sameKey(bundle.proposal.traceRef, trajectory.traceRef)
  if (!proposalIdentityMatches) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "proposal schema, claimant, authorization, scope, or trace binding differs"
    )
  }
  const schemaBindingsMatch =
    sameBinding(bundle.schema, authorization.schema) &&
    sameBinding(bundle.schema, trajectory.schema) &&
    (effect === null || sameBinding(bundle.schema, effect.schema)) &&
    (outcome === null || sameBinding(bundle.schema, outcome.schema))
  if (!schemaBindingsMatch) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "all evidence components must bind the exact active schema bytes"
    )
  }
  const predecessorDescriptorsMatch =
    sameCanonicalAtomV2ContentDescriptor(
      bundle.claimedPredecessor,
      authorization.claimedPredecessor
    ) &&
    sameCanonicalAtomV2ContentDescriptor(
      bundle.claimedPredecessor,
      trajectory.claimedPredecessor
    ) &&
    (effect === null ||
      sameCanonicalAtomV2ContentDescriptor(
        bundle.claimedPredecessor,
        effect.claimedPredecessor
      ))
  if (!predecessorDescriptorsMatch) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "authorization, trace, and effect must bind one claimed predecessor descriptor"
    )
  }
  const predecessorRevisionsMatch =
    bundle.claimedPredecessorStateRevision ===
      bundle.proposal.expectedStateRevision &&
    authorization.claimedPredecessorStateRevision ===
      bundle.claimedPredecessorStateRevision &&
    trajectory.claimedPredecessorStateRevision ===
      bundle.claimedPredecessorStateRevision &&
    (effect === null ||
      effect.claimedPredecessorStateRevision ===
        bundle.claimedPredecessorStateRevision)
  if (!predecessorRevisionsMatch) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "all records must bind the proposal's claimed predecessor state revision"
    )
  }
  const candidateDescriptorsMatch =
    sameCanonicalAtomV2ContentDescriptor(
      bundle.proposalDescriptor,
      authorization.proposal
    ) &&
    sameCanonicalAtomV2ContentDescriptor(
      bundle.proposalDescriptor,
      trajectory.proposal
    ) &&
    (disposition === null ||
      sameCanonicalAtomV2ContentDescriptor(
        bundle.proposalDescriptor,
        disposition.candidate
      )) &&
    (effect === null ||
      sameCanonicalAtomV2ContentDescriptor(
        bundle.proposalDescriptor,
        effect.proposal
      )) &&
    (outcome === null ||
      sameCanonicalAtomV2ContentDescriptor(
        bundle.proposalDescriptor,
        outcome.proposal
      ))
  if (!candidateDescriptorsMatch) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "all components must bind one candidate proposal descriptor"
    )
  }
  const namedRolesMatch =
    roles.claimant.address === authorization.claimant.address &&
    roles.claimant.address === trajectory.claimant.address &&
    roles.authorizer.address === authorization.authorizer.address &&
    sameSubjects(roles.subjects, authorization.subjects)
  if (!namedRolesMatch) {
    return fail(
      "ROLE_BINDING_INVALID",
      "named role bindings differ across the bundle"
    )
  }
  const proposalWrites = bundle.proposal.writes.map(({ key }) => key)
  const activeSchemaKeys = [
    ...bundle.proposal.readSet,
    ...proposalWrites,
    ...roles.subjects.map(({ subject }) => subject),
    authorization.decisionRef,
    trajectory.traceRef
  ]
  if (
    activeSchemaKeys.some(
      ({ schemaVersion }) => schemaVersion !== bundle.schema.schemaVersion
    )
  ) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "all evidence keys must belong to the declared active schema version"
    )
  }
  const decisionIsDeclaredRead = bundle.proposal.readSet.some((key) =>
    sameKey(key, authorization.decisionRef)
  )
  const traceIsDeclaredRead = bundle.proposal.readSet.some((key) =>
    sameKey(key, trajectory.traceRef)
  )
  const subjectsAreDeclaredReads = roles.subjects.every(({ subject }) =>
    bundle.proposal.readSet.some((key) => sameKey(key, subject))
  )
  const requiredReadsAreNotWrites = proposalWrites.every(
    (key) =>
      !sameKey(key, authorization.decisionRef) &&
      !sameKey(key, trajectory.traceRef)
  )
  const referencesAreCoherent =
    authorization.decisionRef.atomUid === authorization.authorizationRef &&
    trajectory.traceId === trajectory.traceRef.atomUid &&
    !sameKey(authorization.decisionRef, trajectory.traceRef) &&
    decisionIsDeclaredRead &&
    traceIsDeclaredRead &&
    subjectsAreDeclaredReads &&
    requiredReadsAreNotWrites
  if (!referencesAreCoherent) {
    return fail(
      "CROSS_FIELD_MISMATCH",
      "authorization decision and trace references must be distinct declared pre-existing proposal reads"
    )
  }
  const traceSetsAndOwnersMatch =
    sameKeys(
      roles.owners.map(({ write }) => write),
      trajectory.writeSet
    ) &&
    sameKeys(trajectory.readSet, bundle.proposal.readSet) &&
    sameKeys(trajectory.writeSet, proposalWrites)
  if (!traceSetsAndOwnersMatch) {
    return fail(
      "ROLE_BINDING_INVALID",
      "owner bindings and trace sets must exactly match the proposal"
    )
  }
  const ownerAddressesMatch = roles.owners.every(
    ({ write, owner }) =>
      bundle.proposal.writes.find(({ key }) => sameKey(key, write))
        ?.responsibilityOwner === owner.address
  )
  if (!ownerAddressesMatch) {
    return fail(
      "ROLE_BINDING_INVALID",
      "each named owner must exactly equal the proposal write responsibility owner"
    )
  }
  const authorizationDescriptor = descriptor(authorization)
  const trajectoryDescriptor = descriptor(trajectory)
  if (Either.isLeft(authorizationDescriptor)) return Either.left(authorizationDescriptor.left)
  if (Either.isLeft(trajectoryDescriptor)) return Either.left(trajectoryDescriptor.left)
  const preOutcomeChronologyMatches =
    Date.parse(authorization.decidedAt) <= Date.parse(trajectory.sealedAt) &&
    Date.parse(trajectory.provenance.collectedAt) <=
      Date.parse(trajectory.sealedAt) &&
    Date.parse(trajectory.sealedAt) <= Date.parse(bundle.proposal.decidedAt)
  if (!preOutcomeChronologyMatches) {
    return fail(
      "TIME_INVALID",
      "decision and provenance must not postdate sealing, and sealing must not postdate the proposal decision"
    )
  }
  if (effect === null && outcome !== null) {
    return fail("OUTCOME_INVALID", "outcome observation requires effect evidence")
  }
  if (effect !== null) {
    const effectMatches =
      sameCanonicalAtomV2ContentDescriptor(
        effect.authorization,
        authorizationDescriptor.right
      ) &&
      sameCanonicalAtomV2ContentDescriptor(
        effect.trajectory,
        trajectoryDescriptor.right
      ) &&
      sameKeys(effect.readSet, trajectory.readSet) &&
      sameKeys(effect.writeSet, trajectory.writeSet) &&
      sameKey(effect.traceRef, trajectory.traceRef) &&
      effect.actorClaim === bundle.proposal.actorClaim &&
      effect.authorizationRef === bundle.proposal.authorizationRef &&
      effect.scope === bundle.proposal.scope &&
      effect.decidedAt === bundle.proposal.decidedAt &&
      effect.provenanceSha256 === bundle.proposal.provenanceSha256
    if (!effectMatches) {
      return fail(
        "CROSS_FIELD_MISMATCH",
        "effect must exactly bind authorization, trace, receipt fields, and read/write sets"
      )
    }
  }
  if (outcome !== null) {
    const effectDescriptor = descriptor(effect!)
    if (Either.isLeft(effectDescriptor)) return Either.left(effectDescriptor.left)
    const outcomeBindingsAndChronologyMatch =
      sameCanonicalAtomV2ContentDescriptor(
        outcome.trajectory,
        trajectoryDescriptor.right
      ) &&
      sameCanonicalAtomV2ContentDescriptor(
        outcome.effect,
        effectDescriptor.right
      ) &&
      Date.parse(outcome.observedAt) > Date.parse(trajectory.sealedAt) &&
      Date.parse(outcome.observedAt) > Date.parse(bundle.proposal.decidedAt) &&
      Date.parse(outcome.provenance.collectedAt) <=
        Date.parse(outcome.observedAt)
    if (!outcomeBindingsAndChronologyMatch) {
      return fail(
        "OUTCOME_INVALID",
        "outcome must bind the sealed trace/effect and follow the proposal decision and its provenance collection"
      )
    }
    if ((outcome.outcome === "UNKNOWN") !== (outcome.observation === null)) {
      return fail(
        "OUTCOME_INVALID",
        "unknown outcomes omit an observation payload; observed and failed outcomes retain one"
      )
    }
    if (
      (outcome.independence === "UNKNOWN") !==
      (outcome.independenceEvidence === null)
    ) {
      return fail(
        "OUTCOME_INVALID",
        "independence evidence must agree with the declared independence mode"
      )
    }
    const evaluatorReusesForbiddenRole =
      outcome.evaluator.address === roles.claimant.address ||
      outcome.evaluator.address === roles.authorizer.address ||
      outcome.evaluator.address === trajectory.sealer.address ||
      roles.custodians.some(
        ({ custodian }) => custodian.address === outcome.evaluator.address
      ) ||
      roles.owners.some(
        ({ owner }) => owner.address === outcome.evaluator.address
      )
    if (
      outcome.independence === "DECLARED_ROLE_SEPARATION_NOT_PROVEN" &&
      evaluatorReusesForbiddenRole
    ) {
      return fail(
        "OUTCOME_INVALID",
        "declared role separation cannot reuse claimant, authorizer, sealer, owner, or custodian text"
      )
    }
  }
  if (disposition !== null) {
    if (
      disposition.disposition !== "REJECTED" &&
      disposition.disposition !== "QUARANTINED"
    ) {
      return fail(
        "DISPOSITION_INVALID",
        "only rejected or quarantined candidates are representable"
      )
    }
    if (
      (disposition.disposition === "QUARANTINED") !==
      (disposition.retention !== null)
    ) {
      return fail(
        "DISPOSITION_INVALID",
        "only quarantined candidates carry a retention descriptor"
      )
    }
    const expectedCustodyObject =
      disposition.disposition === "QUARANTINED"
        ? disposition.candidate
        : disposition.evidence
    const matchingCustodies = roles.custodians.filter(
      ({ custodian, object }) =>
        custodian.address === disposition.custodian.address &&
        sameCanonicalAtomV2ContentDescriptor(object, expectedCustodyObject)
    )
    if (
      matchingCustodies.length === 0 ||
      (disposition.disposition === "QUARANTINED" &&
        !matchingCustodies.some(({ custody }) => custody === "QUARANTINE"))
    ) {
      return fail(
        "ROLE_BINDING_INVALID",
        "disposition custody must bind its exact object, and quarantine requires a quarantine custody claim"
      )
    }
    const dispositionFollowsEvidence =
      Date.parse(disposition.observedAt) >= Date.parse(trajectory.sealedAt) &&
      (outcome === null ||
        Date.parse(disposition.observedAt) >= Date.parse(outcome.observedAt))
    if (!dispositionFollowsEvidence) {
      return fail(
        "TIME_INVALID",
        "disposition must not predate its sealed trace or represented outcome"
      )
    }
  }
  return Either.right(bundle)
}

/** Classification is deliberately evidence-only: no branch denotes a current Permit. */
export const classifyCanonicalAtomV2AuthorizationEvidence = (
  authorization: CanonicalAtomV2AuthorizationDecisionEvidence,
  evaluatedAt: string
): CanonicalAtomV2AuthorizationEvidenceClassification => {
  if (!validInstant(evaluatedAt)) return "EVIDENCE_INVALID_NOT_PERMIT"
  const checked = validateCanonicalAtomV2TransitionEvidenceRecord(authorization)
  if (
    Either.isLeft(checked) ||
    checked.right._tag !== "CanonicalAtomV2AuthorizationDecisionEvidence"
  ) {
    return "EVIDENCE_INVALID_NOT_PERMIT"
  }
  const represented = checked.right
  if (Date.parse(evaluatedAt) < Date.parse(represented.decidedAt)) {
    return "EVIDENCE_DECISION_NOT_YET_MADE_NOT_PERMIT"
  }
  if (represented.decision === "DENIED") return "EVIDENCE_DENIED_NOT_PERMIT"
  if (Date.parse(evaluatedAt) < Date.parse(represented.notBefore)) {
    return "EVIDENCE_NOT_YET_VALID_NOT_PERMIT"
  }
  if (Date.parse(evaluatedAt) >= Date.parse(represented.expiresAt)) {
    return "EVIDENCE_EXPIRED_NOT_PERMIT"
  }
  if (represented.revocationStatus === "NOT_CHECKED") {
    return "EVIDENCE_REVOCATION_UNCHECKED_NOT_PERMIT"
  }
  if (
    represented.revocationCheckedAt !== null &&
    Date.parse(represented.revocationCheckedAt) > Date.parse(evaluatedAt)
  ) {
    return "EVIDENCE_REVOCATION_CHECK_FUTURE_NOT_PERMIT"
  }
  if (
    represented.revocationStatus === "REVOKED" &&
    represented.revokedAt !== null &&
    Date.parse(evaluatedAt) >= Date.parse(represented.revokedAt)
  ) {
    return "EVIDENCE_REVOKED_NOT_PERMIT"
  }
  if (
    represented.revocationCheckedAt === null ||
    Date.parse(represented.revocationCheckedAt) < Date.parse(evaluatedAt)
  ) {
    return "EVIDENCE_REVOCATION_CHECK_STALE_NOT_PERMIT"
  }
  return "EVIDENCE_GRANTED_NOT_PERMIT"
}

const sameSubjects = (
  left: ReadonlyArray<CanonicalAtomV2EvidenceSubject>,
  right: ReadonlyArray<CanonicalAtomV2EvidenceSubject>
): boolean =>
  left.length === right.length &&
  left.every(
    (subject, index) =>
      right[index] !== undefined &&
      subjectId(subject) === subjectId(right[index]!)
  )

export const canonicalAtomV2TransitionEvidenceBundleBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2TransitionEvidenceError> => {
  const checked = validateCanonicalAtomV2TransitionEvidenceBundle(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const describeCanonicalAtomV2TransitionEvidenceBundle = (
  input: unknown
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2TransitionEvidenceError> => {
  const bytes = canonicalAtomV2TransitionEvidenceBundleBytes(input)
  if (Either.isLeft(bytes)) return Either.left(bytes.left)
  const made = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_TRANSITION_EVIDENCE_BUNDLE_V1_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(made)
    ? fail("DESCRIPTOR_INVALID", made.left.detail)
    : Either.right(made.right)
}

export const decodeCanonicalAtomV2TransitionEvidenceBundleBytes = (
  input: Uint8Array
): Either.Either<CanonicalAtomV2TransitionEvidenceBundle, CanonicalAtomV2TransitionEvidenceError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = validateCanonicalAtomV2TransitionEvidenceBundle(parsed.right)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const canonical = canonicalAtomV2TransitionEvidenceBundleBytes(checked.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  if (
    canonical.right.byteLength !== input.byteLength ||
    !canonical.right.every((byte, index) => byte === input[index])
  ) {
    return fail(
      "CANONICAL_ENCODING_INVALID",
      "evidence bytes are not the exact canonical v1 encoding"
    )
  }
  return Either.right(checked.right)
}
