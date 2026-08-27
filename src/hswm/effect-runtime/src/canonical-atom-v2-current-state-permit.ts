import { Data, Effect, Either, Schema } from "effect"

import {
  CanonicalAtomV2ContentDescriptorSchema,
  CanonicalAtomV2SchemaContentBindingSchema,
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
  canonicalAtomV2SchemaContentBytes,
  sameCanonicalAtomV2SchemaBinding
} from "./canonical-atom-v2-content-bound.js"
import {
  canonicalAtomV2StateSha256,
  describeCanonicalAtomV2StateJournalRecord,
  CanonicalAtomV2StateJournalRecordDescriptorSchema,
  CanonicalAtomV2StateJournalRecordSchema,
  type CanonicalAtomV2StateJournalRecord,
  type CanonicalAtomV2StateJournalRecordDescriptor
} from "./canonical-atom-v2-state-journal.js"
import {
  validateCanonicalAtomV2State,
  validateHSWMCanonicalSchemaV2,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  CanonicalAtomV2DurableRuntime,
  type CanonicalAtomV2DurableRecoveryFailure
} from "./canonical-atom-v2-durable-runtime.js"
import {
  CanonicalAtomV2KeySchema,
  CanonicalAtomV2Schema,
  HSWMCanonicalSchemaV2Schema,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import {
  CanonicalAtomV2EvidencePrincipalSchema,
  CanonicalAtomV2EvidenceSubjectSchema,
  CanonicalAtomV2TransitionEvidenceBundleSchema,
  classifyCanonicalAtomV2AuthorizationEvidence,
  describeCanonicalAtomV2TransitionEvidenceRecord,
  validateCanonicalAtomV2TransitionEvidenceBundle,
  type CanonicalAtomV2EvidencePrincipal,
  type CanonicalAtomV2EvidenceSubject,
  type CanonicalAtomV2TransitionEvidenceBundle
} from "./canonical-atom-v2-transition-evidence.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"

/**
 * The pure checker evaluates only a caller-supplied snapshot package. The
 * public Effect wrapper first compares that package with one recovered local
 * durable-runtime head. Neither path issues a canonical Permit or reusable
 * commit capability.
 */
export const HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION =
  "hswm-canonical-current-state-permit/v1" as const
export const HSWM_CANONICAL_CURRENT_STATE_PERMIT_INPUT_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-current-state-permit-input-v1+json" as const
export const HSWM_CANONICAL_CURRENT_STATE_PERMIT_RECORD_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-current-state-permit-record-v1+json" as const
export const HSWM_CANONICAL_CURRENT_STATE_PERMIT_RESOLUTION_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-current-state-permit-resolution-v1+json" as const

export const HSWM_CANONICAL_PERMIT_POLICY_V1_KIND =
  "hswm:kind:permit-policy-v1" as const
export const HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND =
  "hswm:kind:authorization-decision-v1" as const
export const HSWM_CANONICAL_CONSENT_DECISION_V1_KIND =
  "hswm:kind:consent-decision-v1" as const
export const HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND =
  "hswm:kind:trajectory-contract-v1" as const

const CANONICAL_ATOM_V2_PERMISSION_BEARING_KINDS = new Set<string>([
  HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
  HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND,
  HSWM_CANONICAL_CONSENT_DECISION_V1_KIND,
  HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND
])

export const HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE =
  "hswm:reference:permit-policy" as const
export const HSWM_CANONICAL_PERMIT_POLICY_ROLE =
  "hswm:role:permit-policy" as const
export const HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE =
  "hswm:reference:permit-subject" as const
export const HSWM_CANONICAL_PERMIT_SUBJECT_ROLE =
  "hswm:role:permit-subject" as const
export const HSWM_CANONICAL_PERMIT_AUTHORIZATION_REFERENCE_TYPE =
  "hswm:reference:permit-authorization" as const
export const HSWM_CANONICAL_PERMIT_AUTHORIZATION_ROLE =
  "hswm:role:permit-authorization" as const

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

export interface CanonicalAtomV2PermitScopeRule {
  readonly scope: string
  readonly purpose: string
  readonly authorizers: ReadonlyArray<CanonicalAtomV2EvidencePrincipal>
  readonly allowedWriteKinds: ReadonlyArray<string>
}

export const CanonicalAtomV2PermitScopeRuleSchema: Schema.Schema<CanonicalAtomV2PermitScopeRule> =
  Schema.Struct({
    scope: Identifier,
    purpose: Identifier,
    authorizers: Schema.Array(CanonicalAtomV2EvidencePrincipalSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    ),
    allowedWriteKinds: Schema.Array(Identifier).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    )
  })

export interface CanonicalAtomV2PermitConsentSlot {
  readonly subject: CanonicalAtomV2EvidenceSubject
  readonly consentLineageId: string
  readonly consentAtomUid: string
  readonly controllers: ReadonlyArray<CanonicalAtomV2EvidencePrincipal>
}

export const CanonicalAtomV2PermitConsentSlotSchema: Schema.Schema<CanonicalAtomV2PermitConsentSlot> =
  Schema.Struct({
    subject: CanonicalAtomV2EvidenceSubjectSchema,
    consentLineageId: Identifier,
    consentAtomUid: Identifier,
    controllers: Schema.Array(CanonicalAtomV2EvidencePrincipalSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    )
  })

export interface CanonicalAtomV2PermitPolicyRecord {
  readonly _tag: "CanonicalAtomV2PermitPolicyRecord"
  readonly contractVersion: typeof HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  readonly policyRef: CanonicalAtomV2Key
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly decision: "ACTIVE" | "SUSPENDED"
  readonly scopeRules: ReadonlyArray<CanonicalAtomV2PermitScopeRule>
  readonly consentSlots: ReadonlyArray<CanonicalAtomV2PermitConsentSlot>
  readonly policyStatus: "REPRESENTED_STATE_POLICY_NOT_CANONICAL_PERMIT"
}

export const CanonicalAtomV2PermitPolicyRecordSchema: Schema.Schema<CanonicalAtomV2PermitPolicyRecord> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2PermitPolicyRecord"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
    ),
    policyRef: CanonicalAtomV2KeySchema,
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    decision: Schema.Literal("ACTIVE", "SUSPENDED"),
    scopeRules: Schema.Array(CanonicalAtomV2PermitScopeRuleSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    ),
    consentSlots: Schema.Array(CanonicalAtomV2PermitConsentSlotSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    ),
    policyStatus: Schema.Literal(
      "REPRESENTED_STATE_POLICY_NOT_CANONICAL_PERMIT"
    )
  })

export interface CanonicalAtomV2AuthorizationDecisionRecord {
  readonly _tag: "CanonicalAtomV2AuthorizationDecisionRecord"
  readonly contractVersion: typeof HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  readonly decisionRef: CanonicalAtomV2Key
  readonly policyRef: CanonicalAtomV2Key
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly authorizationRef: string
  readonly claimant: CanonicalAtomV2EvidencePrincipal
  readonly subjects: ReadonlyArray<CanonicalAtomV2EvidenceSubject>
  readonly authorizer: CanonicalAtomV2EvidencePrincipal
  readonly scope: string
  readonly purpose: string
  readonly decision: "GRANTED" | "DENIED"
  readonly decidedAt: string
  readonly notBefore: string
  readonly expiresAt: string
  readonly authorityEvidence: CanonicalAtomV2ContentDescriptor
  readonly revocationStatus: "CHECKED_NOT_REVOKED" | "REVOKED" | "NOT_CHECKED"
  readonly revocationCheckedAt: string | null
  readonly revokedAt: string | null
  readonly revocationEvidence: CanonicalAtomV2ContentDescriptor | null
  readonly decisionStatus: "REPRESENTED_STATE_AUTHORIZATION_NOT_CANONICAL_PERMIT"
}

export const CanonicalAtomV2AuthorizationDecisionRecordSchema: Schema.Schema<CanonicalAtomV2AuthorizationDecisionRecord> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2AuthorizationDecisionRecord"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
    ),
    decisionRef: CanonicalAtomV2KeySchema,
    policyRef: CanonicalAtomV2KeySchema,
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    authorizationRef: Identifier,
    claimant: CanonicalAtomV2EvidencePrincipalSchema,
    subjects: Schema.Array(CanonicalAtomV2EvidenceSubjectSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    ),
    authorizer: CanonicalAtomV2EvidencePrincipalSchema,
    scope: Identifier,
    purpose: Identifier,
    decision: Schema.Literal("GRANTED", "DENIED"),
    decidedAt: CanonicalInstant,
    notBefore: CanonicalInstant,
    expiresAt: CanonicalInstant,
    authorityEvidence: CanonicalAtomV2ContentDescriptorSchema,
    revocationStatus: Schema.Literal(
      "CHECKED_NOT_REVOKED",
      "REVOKED",
      "NOT_CHECKED"
    ),
    revocationCheckedAt: Schema.NullOr(CanonicalInstant),
    revokedAt: Schema.NullOr(CanonicalInstant),
    revocationEvidence: Schema.NullOr(CanonicalAtomV2ContentDescriptorSchema),
    decisionStatus: Schema.Literal(
      "REPRESENTED_STATE_AUTHORIZATION_NOT_CANONICAL_PERMIT"
    )
  })

export interface CanonicalAtomV2TrajectoryContractRecord {
  readonly _tag: "CanonicalAtomV2TrajectoryContractRecord"
  readonly contractVersion: typeof HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  readonly traceRef: CanonicalAtomV2Key
  readonly policyRef: CanonicalAtomV2Key
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly claimant: CanonicalAtomV2EvidencePrincipal
  readonly allowedSealers: ReadonlyArray<CanonicalAtomV2EvidencePrincipal>
  readonly scope: string
  readonly purpose: string
  readonly decision: "ACTIVE" | "SUSPENDED"
  readonly contractEvidence: CanonicalAtomV2ContentDescriptor
  readonly trajectoryStatus: "PRE_EXISTING_CONTRACT_NOT_EXECUTION_NOT_OUTCOME"
}

export const CanonicalAtomV2TrajectoryContractRecordSchema: Schema.Schema<CanonicalAtomV2TrajectoryContractRecord> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2TrajectoryContractRecord"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
    ),
    traceRef: CanonicalAtomV2KeySchema,
    policyRef: CanonicalAtomV2KeySchema,
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    claimant: CanonicalAtomV2EvidencePrincipalSchema,
    allowedSealers: Schema.Array(CanonicalAtomV2EvidencePrincipalSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(128)
    ),
    scope: Identifier,
    purpose: Identifier,
    decision: Schema.Literal("ACTIVE", "SUSPENDED"),
    contractEvidence: CanonicalAtomV2ContentDescriptorSchema,
    trajectoryStatus: Schema.Literal(
      "PRE_EXISTING_CONTRACT_NOT_EXECUTION_NOT_OUTCOME"
    )
  })

export interface CanonicalAtomV2ConsentDecisionRecord {
  readonly _tag: "CanonicalAtomV2ConsentDecisionRecord"
  readonly contractVersion: typeof HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  readonly consentRef: CanonicalAtomV2Key
  readonly policyRef: CanonicalAtomV2Key
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly subject: CanonicalAtomV2EvidenceSubject
  readonly consenter: CanonicalAtomV2EvidencePrincipal
  readonly claimant: CanonicalAtomV2EvidencePrincipal
  readonly scope: string
  readonly purpose: string
  readonly decision: "GRANTED" | "WITHDRAWN" | "DENIED"
  readonly decidedAt: string
  readonly notBefore: string
  readonly expiresAt: string
  readonly decisionEvidence: CanonicalAtomV2ContentDescriptor
  readonly revocationStatus: "CHECKED_NOT_REVOKED" | "REVOKED" | "NOT_CHECKED"
  readonly revocationCheckedAt: string | null
  readonly revokedAt: string | null
  readonly revocationEvidence: CanonicalAtomV2ContentDescriptor | null
  readonly consentStatus: "REPRESENTED_STATE_CONSENT_NOT_CANONICAL_PERMIT"
}

export const CanonicalAtomV2ConsentDecisionRecordSchema: Schema.Schema<CanonicalAtomV2ConsentDecisionRecord> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2ConsentDecisionRecord"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
    ),
    consentRef: CanonicalAtomV2KeySchema,
    policyRef: CanonicalAtomV2KeySchema,
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    subject: CanonicalAtomV2EvidenceSubjectSchema,
    consenter: CanonicalAtomV2EvidencePrincipalSchema,
    claimant: CanonicalAtomV2EvidencePrincipalSchema,
    scope: Identifier,
    purpose: Identifier,
    decision: Schema.Literal("GRANTED", "WITHDRAWN", "DENIED"),
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
    consentStatus: Schema.Literal(
      "REPRESENTED_STATE_CONSENT_NOT_CANONICAL_PERMIT"
    )
  })

export type CanonicalAtomV2CurrentStatePermitRecord =
  | CanonicalAtomV2PermitPolicyRecord
  | CanonicalAtomV2AuthorizationDecisionRecord
  | CanonicalAtomV2ConsentDecisionRecord
  | CanonicalAtomV2TrajectoryContractRecord

export const CanonicalAtomV2CurrentStatePermitRecordSchema: Schema.Schema<CanonicalAtomV2CurrentStatePermitRecord> =
  Schema.Union(
    CanonicalAtomV2PermitPolicyRecordSchema,
    CanonicalAtomV2AuthorizationDecisionRecordSchema,
    CanonicalAtomV2ConsentDecisionRecordSchema,
    CanonicalAtomV2TrajectoryContractRecordSchema
  )

const CanonicalAtomV2StateSchema: Schema.Schema<CanonicalAtomV2State> =
  Schema.Struct({
    schemaVersion: Identifier,
    revision: SafeInteger,
    bootstrapClosed: Schema.Boolean,
    atoms: Schema.Array(CanonicalAtomV2Schema).pipe(Schema.maxItems(65_536)),
    acceptedTransitionIds: Schema.Array(Identifier).pipe(
      Schema.maxItems(65_536)
    )
  })

export interface CanonicalAtomV2LocalHeadObservation {
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly journalLineageId: string
  readonly journalHead: CanonicalAtomV2StateJournalRecordDescriptor
  readonly stateRevision: number
  readonly stateSha256: string
  readonly observedAt: string
  readonly clockEvidence: CanonicalAtomV2ContentDescriptor
  readonly freshness: "LOCAL_EXACT_HEAD_OBSERVATION_NOT_MONOTONIC_WITNESS"
}

export const CanonicalAtomV2LocalHeadObservationSchema: Schema.Schema<CanonicalAtomV2LocalHeadObservation> =
  Schema.Struct({
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    journalLineageId: Identifier,
    journalHead: CanonicalAtomV2StateJournalRecordDescriptorSchema,
    stateRevision: SafeInteger,
    stateSha256: Sha256,
    observedAt: CanonicalInstant,
    clockEvidence: CanonicalAtomV2ContentDescriptorSchema,
    freshness: Schema.Literal(
      "LOCAL_EXACT_HEAD_OBSERVATION_NOT_MONOTONIC_WITNESS"
    )
  })

export interface CanonicalAtomV2PermitIntent {
  readonly action: "ADMIT_CANONICAL_ATOM_VERSIONS"
  readonly purpose: string
}

export const CanonicalAtomV2PermitIntentSchema: Schema.Schema<CanonicalAtomV2PermitIntent> =
  Schema.Struct({
    action: Schema.Literal("ADMIT_CANONICAL_ATOM_VERSIONS"),
    purpose: Identifier
  })

export interface CanonicalAtomV2CurrentStatePermitInput {
  readonly _tag: "CanonicalAtomV2CurrentStatePermitInput"
  readonly contractVersion: typeof HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  readonly schema: HSWMCanonicalSchemaV2
  readonly state: CanonicalAtomV2State
  readonly journalHeadRecord: CanonicalAtomV2StateJournalRecord
  readonly headObservation: CanonicalAtomV2LocalHeadObservation
  readonly evaluatedAt: string
  readonly intent: CanonicalAtomV2PermitIntent
  readonly evidence: CanonicalAtomV2TransitionEvidenceBundle
  readonly policy: CanonicalAtomV2PermitPolicyRecord
  readonly authorizationDecision: CanonicalAtomV2AuthorizationDecisionRecord
  readonly consents: ReadonlyArray<CanonicalAtomV2ConsentDecisionRecord>
  readonly trajectoryContract: CanonicalAtomV2TrajectoryContractRecord
}

export const CanonicalAtomV2CurrentStatePermitInputSchema: Schema.Schema<CanonicalAtomV2CurrentStatePermitInput> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2CurrentStatePermitInput"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
    ),
    schema: HSWMCanonicalSchemaV2Schema,
    state: CanonicalAtomV2StateSchema,
    journalHeadRecord: CanonicalAtomV2StateJournalRecordSchema,
    headObservation: CanonicalAtomV2LocalHeadObservationSchema,
    evaluatedAt: CanonicalInstant,
    intent: CanonicalAtomV2PermitIntentSchema,
    evidence: CanonicalAtomV2TransitionEvidenceBundleSchema,
    policy: CanonicalAtomV2PermitPolicyRecordSchema,
    authorizationDecision: CanonicalAtomV2AuthorizationDecisionRecordSchema,
    consents: Schema.Array(CanonicalAtomV2ConsentDecisionRecordSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    ),
    trajectoryContract: CanonicalAtomV2TrajectoryContractRecordSchema
  })

export interface CanonicalAtomV2CurrentStatePermitResolution {
  readonly _tag: "CanonicalAtomV2CurrentStatePermitResolution"
  readonly contractVersion: typeof HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  readonly status:
    | "ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_CANONICAL_PERMIT"
    | "ELIGIBLE_AT_RECOVERED_LOCAL_HEAD_FOR_SUPPLIED_TIME_NOT_CANONICAL_PERMIT"
  readonly snapshotBasis:
    | "SUPPLIED_STATE_AND_HEAD_RECORD_NOT_JOURNAL_REPLAY"
    | "ONE_DURABLE_RUNTIME_RECOVERY_SNAPSHOT"
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly journalLineageId: string
  readonly journalHead: CanonicalAtomV2StateJournalRecordDescriptor
  readonly stateRevision: number
  readonly stateSha256: string
  readonly evaluationInput: CanonicalAtomV2ContentDescriptor
  readonly proposal: CanonicalAtomV2ContentDescriptor
  readonly policy: CanonicalAtomV2ContentDescriptor
  readonly authorizationDecision: CanonicalAtomV2ContentDescriptor
  readonly authorizationEvidence: CanonicalAtomV2ContentDescriptor
  readonly trajectoryContract: CanonicalAtomV2ContentDescriptor
  readonly trajectoryEvidence: CanonicalAtomV2ContentDescriptor
  readonly consents: ReadonlyArray<CanonicalAtomV2ContentDescriptor>
  readonly evaluatedAt: string
  readonly timeBasis: "CALLER_SUPPLIED_INSTANT_NOT_TRUSTED_CURRENT_TIME"
  readonly headFreshness: "LOCAL_OBSERVATION_NOT_ANTI_ROLLBACK_PROOF"
  readonly capability: "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
  readonly admission: "NOT_ADMITTED_BY_THIS_RESOLUTION"
  readonly externalEffect: "NOT_DISPATCHED_NOT_OBSERVED"
  readonly learning: "NOT_CAUSAL_CREDIT_NOT_LEARNING"
}

export const CanonicalAtomV2CurrentStatePermitResolutionSchema: Schema.Schema<CanonicalAtomV2CurrentStatePermitResolution> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2CurrentStatePermitResolution"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
    ),
    status: Schema.Literal(
      "ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_CANONICAL_PERMIT",
      "ELIGIBLE_AT_RECOVERED_LOCAL_HEAD_FOR_SUPPLIED_TIME_NOT_CANONICAL_PERMIT"
    ),
    snapshotBasis: Schema.Literal(
      "SUPPLIED_STATE_AND_HEAD_RECORD_NOT_JOURNAL_REPLAY",
      "ONE_DURABLE_RUNTIME_RECOVERY_SNAPSHOT"
    ),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    journalLineageId: Identifier,
    journalHead: CanonicalAtomV2StateJournalRecordDescriptorSchema,
    stateRevision: SafeInteger,
    stateSha256: Sha256,
    evaluationInput: CanonicalAtomV2ContentDescriptorSchema,
    proposal: CanonicalAtomV2ContentDescriptorSchema,
    policy: CanonicalAtomV2ContentDescriptorSchema,
    authorizationDecision: CanonicalAtomV2ContentDescriptorSchema,
    authorizationEvidence: CanonicalAtomV2ContentDescriptorSchema,
    trajectoryContract: CanonicalAtomV2ContentDescriptorSchema,
    trajectoryEvidence: CanonicalAtomV2ContentDescriptorSchema,
    consents: Schema.Array(CanonicalAtomV2ContentDescriptorSchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(256)
    ),
    evaluatedAt: CanonicalInstant,
    timeBasis: Schema.Literal(
      "CALLER_SUPPLIED_INSTANT_NOT_TRUSTED_CURRENT_TIME"
    ),
    headFreshness: Schema.Literal(
      "LOCAL_OBSERVATION_NOT_ANTI_ROLLBACK_PROOF"
    ),
    capability: Schema.Literal(
      "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
    ),
    admission: Schema.Literal("NOT_ADMITTED_BY_THIS_RESOLUTION"),
    externalEffect: Schema.Literal("NOT_DISPATCHED_NOT_OBSERVED"),
    learning: Schema.Literal("NOT_CAUSAL_CREDIT_NOT_LEARNING")
  })

export type CanonicalAtomV2CurrentStatePermitErrorCode =
  | "AUTHORIZATION_NOT_CURRENT"
  | "AUTHORITY_DENIED"
  | "CANONICAL_ENCODING_INVALID"
  | "CONSENT_DENIED"
  | "CONSENT_MISSING"
  | "CONSENT_NOT_CURRENT"
  | "HEAD_MISMATCH"
  | "INPUT_INVALID"
  | "MEMBERSHIP_CONTENT_MISMATCH"
  | "MEMBERSHIP_MISSING"
  | "MEMBERSHIP_NOT_CURRENT"
  | "PHASE_INVALID"
  | "POLICY_INVALID"
  | "PREDECESSOR_MISMATCH"
  | "PROPOSAL_REPLAY"
  | "REQUIRED_READ_MISSING"
  | "SCHEMA_MISMATCH"
  | "SELF_AUTHORIZATION"
  | "STATE_INVALID"
  | "TIME_INVALID"

export class CanonicalAtomV2CurrentStatePermitError extends Data.TaggedError(
  "CanonicalAtomV2CurrentStatePermitError"
)<{
  readonly code: CanonicalAtomV2CurrentStatePermitErrorCode
  readonly detail: string
  readonly permitStatus: "NOT_CANONICAL_PERMIT"
}> {}

const fail = (
  code: CanonicalAtomV2CurrentStatePermitErrorCode,
  detail: string
): Either.Either<never, CanonicalAtomV2CurrentStatePermitError> =>
  Either.left(
    new CanonicalAtomV2CurrentStatePermitError({
      code,
      detail,
      permitStatus: "NOT_CANONICAL_PERMIT"
    })
  )

const deepFreeze = <A>(value: A): A => {
  if (typeof value === "object" && value !== null && !Object.isFrozen(value)) {
    Object.freeze(value)
    for (const nested of Object.values(value as Record<string, unknown>)) {
      deepFreeze(nested)
    }
  }
  return value
}

const snapshot = <A>(value: A): A => deepFreeze(structuredClone(value))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const validInstant = (value: string): boolean => {
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value
}

const sameKey = (left: CanonicalAtomV2Key, right: CanonicalAtomV2Key): boolean =>
  canonicalAtomV2KeyId(left) === canonicalAtomV2KeyId(right)

const logicalKeyId = (key: CanonicalAtomV2Key): string =>
  `${key.schemaVersion}|${key.lineageId}|${key.atomUid}`

const sameJournalDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor,
  right: CanonicalAtomV2ContentDescriptor
): boolean =>
  left.mediaType === right.mediaType &&
  left.byteLength === right.byteLength &&
  left.sha256 === right.sha256

const sameNullableDescriptor = (
  left: CanonicalAtomV2ContentDescriptor | null,
  right: CanonicalAtomV2ContentDescriptor | null
): boolean =>
  left === null
    ? right === null
    : right !== null && sameCanonicalAtomV2ContentDescriptor(left, right)

const subjectId = (subject: CanonicalAtomV2EvidenceSubject): string =>
  `${canonicalAtomV2KeyId(subject.subject)}|${subject.relation}`

const strictlyAscending = <A>(
  values: ReadonlyArray<A>,
  id: (value: A) => string
): boolean =>
  values.every(
    (value, index) => index === 0 || id(values[index - 1]!) < id(value)
  )

const coherentRevocation = (value: {
  readonly revocationStatus: "CHECKED_NOT_REVOKED" | "REVOKED" | "NOT_CHECKED"
  readonly revocationCheckedAt: string | null
  readonly revokedAt: string | null
  readonly revocationEvidence: CanonicalAtomV2ContentDescriptor | null
}): boolean => {
  if (value.revocationStatus === "NOT_CHECKED") {
    return (
      value.revocationCheckedAt === null &&
      value.revokedAt === null &&
      value.revocationEvidence === null
    )
  }
  if (
    value.revocationCheckedAt === null ||
    !validInstant(value.revocationCheckedAt) ||
    value.revocationEvidence === null
  ) {
    return false
  }
  if (value.revocationStatus === "CHECKED_NOT_REVOKED") {
    return value.revokedAt === null
  }
  return (
    value.revokedAt !== null &&
    validInstant(value.revokedAt) &&
    Date.parse(value.revokedAt) <= Date.parse(value.revocationCheckedAt)
  )
}

const validatePolicy = (
  input: unknown
): Either.Either<CanonicalAtomV2PermitPolicyRecord, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2PermitPolicyRecordSchema, {
    onExcessProperty: "error"
  })(input)
  if (Either.isLeft(decoded)) {
    return fail("POLICY_INVALID", "policy violates the strict v1 structural contract")
  }
  const policy = snapshot(decoded.right)
  const orderedScopes = strictlyAscending(
    policy.scopeRules,
    ({ scope, purpose }) => `${scope}|${purpose}`
  )
  const orderedSlots = strictlyAscending(policy.consentSlots, ({ subject }) =>
    subjectId(subject)
  )
  const orderedPrincipals =
    policy.scopeRules.every(({ authorizers }) =>
      strictlyAscending(authorizers, ({ address }) => address)
    ) &&
    policy.consentSlots.every(({ controllers }) =>
      strictlyAscending(controllers, ({ address }) => address)
    )
  const orderedWriteKinds = policy.scopeRules.every(({ allowedWriteKinds }) =>
    strictlyAscending(allowedWriteKinds, (kind) => kind)
  )
  const delegatesPermissionGovernance = policy.scopeRules.some(
    ({ allowedWriteKinds }) =>
      allowedWriteKinds.some((kind) =>
        CANONICAL_ATOM_V2_PERMISSION_BEARING_KINDS.has(kind)
      )
  )
  if (
    !orderedScopes ||
    !orderedSlots ||
    !orderedPrincipals ||
    !orderedWriteKinds ||
    delegatesPermissionGovernance ||
    policy.policyRef.schemaVersion !== policy.schema.schemaVersion ||
    policy.consentSlots.some(
      ({ subject }) =>
        subject.subject.schemaVersion !== policy.schema.schemaVersion
    )
  ) {
    return fail(
      "POLICY_INVALID",
      "policy sets must be exact ascending sets in one schema domain and cannot delegate v1 permission governance"
    )
  }
  const consentSlotIds = policy.consentSlots.map(
    ({ consentLineageId, consentAtomUid }) =>
      `${policy.schema.schemaVersion}|${consentLineageId}|${consentAtomUid}`
  )
  if (new Set(consentSlotIds).size !== consentSlotIds.length) {
    return fail("POLICY_INVALID", "one logical consent slot cannot control multiple subjects")
  }
  return Either.right(policy)
}

const validateAuthorizationDecision = (
  input: unknown
): Either.Either<CanonicalAtomV2AuthorizationDecisionRecord, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2AuthorizationDecisionRecordSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail(
      "AUTHORIZATION_NOT_CURRENT",
      "authorization decision violates the strict v1 structural contract"
    )
  }
  const decision = snapshot(decoded.right)
  if (
    !validInstant(decision.decidedAt) ||
    !validInstant(decision.notBefore) ||
    !validInstant(decision.expiresAt) ||
    Date.parse(decision.notBefore) >= Date.parse(decision.expiresAt) ||
    !coherentRevocation(decision) ||
    !strictlyAscending(decision.subjects, subjectId) ||
    decision.decisionRef.schemaVersion !== decision.schema.schemaVersion ||
    decision.policyRef.schemaVersion !== decision.schema.schemaVersion ||
    decision.decisionRef.atomUid !== decision.authorizationRef ||
    decision.subjects.some(
      ({ subject }) => subject.schemaVersion !== decision.schema.schemaVersion
    )
  ) {
    return fail(
      "AUTHORIZATION_NOT_CURRENT",
      "authorization decision has incoherent schema, identity, time, subject or revocation fields"
    )
  }
  return Either.right(decision)
}

const validateTrajectoryContract = (
  input: unknown
): Either.Either<CanonicalAtomV2TrajectoryContractRecord, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2TrajectoryContractRecordSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail(
      "POLICY_INVALID",
      "trajectory contract violates the strict v1 structural contract"
    )
  }
  const contract = snapshot(decoded.right)
  if (
    contract.traceRef.schemaVersion !== contract.schema.schemaVersion ||
    contract.policyRef.schemaVersion !== contract.schema.schemaVersion ||
    !strictlyAscending(contract.allowedSealers, ({ address }) => address)
  ) {
    return fail(
      "POLICY_INVALID",
      "trajectory contract must be one-schema and use an exact sealer set"
    )
  }
  return Either.right(contract)
}

const validateConsent = (
  input: unknown
): Either.Either<CanonicalAtomV2ConsentDecisionRecord, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2ConsentDecisionRecordSchema, {
    onExcessProperty: "error"
  })(input)
  if (Either.isLeft(decoded)) {
    return fail("CONSENT_DENIED", "consent violates the strict v1 structural contract")
  }
  const consent = snapshot(decoded.right)
  if (
    !validInstant(consent.decidedAt) ||
    !validInstant(consent.notBefore) ||
    !validInstant(consent.expiresAt) ||
    Date.parse(consent.notBefore) >= Date.parse(consent.expiresAt) ||
    !coherentRevocation(consent) ||
    consent.consentRef.schemaVersion !== consent.schema.schemaVersion ||
    consent.policyRef.schemaVersion !== consent.schema.schemaVersion ||
    consent.subject.subject.schemaVersion !== consent.schema.schemaVersion
  ) {
    return fail(
      "CONSENT_DENIED",
      "consent has incoherent schema, time, subject or revocation fields"
    )
  }
  return Either.right(consent)
}

export const validateCanonicalAtomV2CurrentStatePermitRecord = (
  input: unknown
): Either.Either<CanonicalAtomV2CurrentStatePermitRecord, CanonicalAtomV2CurrentStatePermitError> => {
  if (
    typeof input !== "object" ||
    input === null ||
    !("_tag" in input)
  ) {
    return fail("INPUT_INVALID", "permit record must be a tagged object")
  }
  const tag = (input as { readonly _tag?: unknown })._tag
  if (tag === "CanonicalAtomV2PermitPolicyRecord") return validatePolicy(input)
  if (tag === "CanonicalAtomV2AuthorizationDecisionRecord") {
    return validateAuthorizationDecision(input)
  }
  if (tag === "CanonicalAtomV2ConsentDecisionRecord") return validateConsent(input)
  if (tag === "CanonicalAtomV2TrajectoryContractRecord") {
    return validateTrajectoryContract(input)
  }
  return fail("INPUT_INVALID", "unknown current-state Permit record tag")
}

export const canonicalAtomV2CurrentStatePermitRecordBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2CurrentStatePermitError> => {
  const record = validateCanonicalAtomV2CurrentStatePermitRecord(input)
  if (Either.isLeft(record)) return Either.left(record.left)
  const bytes = canonicalJsonBytes(record.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const describeCanonicalAtomV2CurrentStatePermitRecord = (
  input: unknown
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2CurrentStatePermitError> => {
  const bytes = canonicalAtomV2CurrentStatePermitRecordBytes(input)
  if (Either.isLeft(bytes)) return Either.left(bytes.left)
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_RECORD_V1_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(descriptor)
    ? fail("CANONICAL_ENCODING_INVALID", descriptor.left.detail)
    : Either.right(descriptor.right)
}

export const decodeCanonicalAtomV2CurrentStatePermitRecordBytes = (
  input: Uint8Array
): Either.Either<CanonicalAtomV2CurrentStatePermitRecord, CanonicalAtomV2CurrentStatePermitError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const record = validateCanonicalAtomV2CurrentStatePermitRecord(parsed.right)
  if (Either.isLeft(record)) return Either.left(record.left)
  const canonical = canonicalAtomV2CurrentStatePermitRecordBytes(record.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return sameBytes(input, canonical.right)
    ? Either.right(record.right)
    : fail("CANONICAL_ENCODING_INVALID", "permit record bytes are not exact canonical JSON/v1")
}

const decodeInput = (
  input: unknown
): Either.Either<CanonicalAtomV2CurrentStatePermitInput, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2CurrentStatePermitInputSchema, {
    onExcessProperty: "error"
  })(input)
  if (Either.isLeft(decoded)) {
    return fail("INPUT_INVALID", "Permit input violates the strict v1 structural contract")
  }
  return Either.right(snapshot(decoded.right))
}

const schemaBindingFor = (
  schema: HSWMCanonicalSchemaV2
): Either.Either<CanonicalAtomV2SchemaContentBinding, CanonicalAtomV2CurrentStatePermitError> => {
  const bytes = canonicalAtomV2SchemaContentBytes(schema)
  if (Either.isLeft(bytes)) {
    return fail("SCHEMA_MISMATCH", "active schema has no exact canonical encoding")
  }
  const content = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(content)
    ? fail("SCHEMA_MISMATCH", content.left.detail)
    : Either.right(
        Object.freeze({
          schemaVersion: schema.schemaVersion,
          content: content.right
        })
      )
}

const requireSameSchemaBinding = (
  expected: CanonicalAtomV2SchemaContentBinding,
  actual: CanonicalAtomV2SchemaContentBinding,
  detail: string
): Either.Either<void, CanonicalAtomV2CurrentStatePermitError> =>
  sameCanonicalAtomV2SchemaBinding(expected, actual)
    ? Either.right(undefined)
    : fail("SCHEMA_MISMATCH", detail)

const hasExactReference = (
  atom: CanonicalAtomV2,
  referenceType: string,
  role: string,
  target: CanonicalAtomV2Key
): boolean =>
  atom.references.some(
    (reference) =>
      reference.referenceType === referenceType &&
      reference.role === role &&
      sameKey(reference.target, target)
  )

const latestAtom = (
  atoms: ReadonlyArray<CanonicalAtomV2>,
  key: CanonicalAtomV2Key
): CanonicalAtomV2 | undefined =>
  atoms
    .filter((atom) => logicalKeyId(atom.key) === logicalKeyId(key))
    .sort((left, right) => right.key.revisionId - left.key.revisionId)[0]

const requireAdmittedRecord = (
  state: CanonicalAtomV2State,
  key: CanonicalAtomV2Key,
  kind: string,
  descriptor: CanonicalAtomV2ContentDescriptor,
  current: boolean
): Either.Either<CanonicalAtomV2, CanonicalAtomV2CurrentStatePermitError> => {
  const atom = state.atoms.find(({ key: candidate }) => sameKey(candidate, key))
  if (atom === undefined) {
    return fail("MEMBERSHIP_MISSING", `required atom ${canonicalAtomV2KeyId(key)} is not admitted`)
  }
  if (atom.kind !== kind) {
    return fail("MEMBERSHIP_CONTENT_MISMATCH", `required atom ${key.atomUid} has the wrong semantic kind`)
  }
  if (!sameCanonicalAtomV2ContentDescriptor(atom.content, descriptor)) {
    return fail("MEMBERSHIP_CONTENT_MISMATCH", `required atom ${key.atomUid} does not bind the exact record bytes`)
  }
  if (current && !sameKey(latestAtom(state.atoms, key)?.key ?? key, key)) {
    return fail("MEMBERSHIP_NOT_CURRENT", `required atom ${key.atomUid} is not its latest admitted logical version`)
  }
  return Either.right(atom)
}

const requirePreExistingRead = (
  evidence: CanonicalAtomV2TransitionEvidenceBundle,
  key: CanonicalAtomV2Key
): Either.Either<void, CanonicalAtomV2CurrentStatePermitError> => {
  const read = evidence.proposal.readSet.some((candidate) => sameKey(candidate, key))
  const written = evidence.proposal.writes.some(({ key: candidate }) =>
    sameKey(candidate, key)
  )
  if (written) {
    return fail("SELF_AUTHORIZATION", `permission input ${key.atomUid} is manufactured by the candidate transition`)
  }
  return read
    ? Either.right(undefined)
    : fail("REQUIRED_READ_MISSING", `permission input ${key.atomUid} is absent from the proposal read set`)
}

const consentIsCurrent = (
  consent: CanonicalAtomV2ConsentDecisionRecord,
  evaluatedAt: string
): boolean =>
  consent.decision === "GRANTED" &&
  Date.parse(consent.decidedAt) <= Date.parse(evaluatedAt) &&
  Date.parse(consent.notBefore) <= Date.parse(evaluatedAt) &&
  Date.parse(evaluatedAt) < Date.parse(consent.expiresAt) &&
  consent.revocationStatus === "CHECKED_NOT_REVOKED" &&
  consent.revocationCheckedAt === evaluatedAt &&
  consent.revokedAt === null &&
  consent.revocationEvidence !== null

export const validateCanonicalAtomV2CurrentStatePermitInput = (
  input: unknown
): Either.Either<CanonicalAtomV2CurrentStatePermitInput, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = decodeInput(input)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const value = decoded.right

  if (!validInstant(value.evaluatedAt) || !validInstant(value.headObservation.observedAt)) {
    return fail("TIME_INVALID", "evaluation and head-observation instants must be real canonical instants")
  }
  if (
    value.evaluatedAt !== value.headObservation.observedAt ||
    value.evaluatedAt !== value.evidence.proposal.decidedAt
  ) {
    return fail("TIME_INVALID", "local head observation, proposal decision and evaluation must share one exact instant")
  }

  const schema = validateHSWMCanonicalSchemaV2(value.schema)
  if (Either.isLeft(schema)) return fail("SCHEMA_MISMATCH", schema.left.detail)
  const exactSchema = schemaBindingFor(schema.right)
  if (Either.isLeft(exactSchema)) return Either.left(exactSchema.left)
  for (const [binding, detail] of [
    [value.headObservation.schema, "head observation does not bind the exact active schema bytes"],
    [value.evidence.schema, "transition evidence does not bind the exact active schema bytes"],
    [value.policy.schema, "Permit policy does not bind the exact active schema bytes"],
    [value.authorizationDecision.schema, "authorization decision does not bind the exact active schema bytes"],
    [value.trajectoryContract.schema, "trajectory contract does not bind the exact active schema bytes"]
  ] as const) {
    const match = requireSameSchemaBinding(exactSchema.right, binding, detail)
    if (Either.isLeft(match)) return Either.left(match.left)
  }

  const policy = validatePolicy(value.policy)
  if (Either.isLeft(policy)) return Either.left(policy.left)
  const schemaKinds = new Set(schema.right.kinds.map(({ kind }) => kind))
  if (
    policy.right.scopeRules.some(({ allowedWriteKinds }) =>
      allowedWriteKinds.some((kind) => !schemaKinds.has(kind))
    )
  ) {
    return fail(
      "POLICY_INVALID",
      "policy allowed-write kinds must be declared by the exact active schema"
    )
  }
  const currentAuthorization = validateAuthorizationDecision(
    value.authorizationDecision
  )
  if (Either.isLeft(currentAuthorization)) {
    return Either.left(currentAuthorization.left)
  }
  const trajectoryContract = validateTrajectoryContract(
    value.trajectoryContract
  )
  if (Either.isLeft(trajectoryContract)) {
    return Either.left(trajectoryContract.left)
  }
  for (const consentInput of value.consents) {
    const consent = validateConsent(consentInput)
    if (Either.isLeft(consent)) return Either.left(consent.left)
    const match = requireSameSchemaBinding(
      exactSchema.right,
      consent.right.schema,
      "consent does not bind the exact active schema bytes"
    )
    if (Either.isLeft(match)) return Either.left(match.left)
  }

  const state = validateCanonicalAtomV2State(schema.right, value.state)
  if (Either.isLeft(state)) return fail("STATE_INVALID", state.left.detail)
  const stateSha = canonicalAtomV2StateSha256(state.right)
  if (Either.isLeft(stateSha)) return fail("STATE_INVALID", stateSha.left.detail)
  const headDescriptor = describeCanonicalAtomV2StateJournalRecord(value.journalHeadRecord)
  if (Either.isLeft(headDescriptor)) return fail("HEAD_MISMATCH", headDescriptor.left.detail)
  const head = value.journalHeadRecord
  if (
    head.journalLineageId !== value.headObservation.journalLineageId ||
    head.stateRevision !== state.right.revision ||
    head.resultingStateSha256 !== stateSha.right ||
    !sameCanonicalAtomV2SchemaBinding(head.schema, exactSchema.right) ||
    value.headObservation.stateRevision !== state.right.revision ||
    value.headObservation.stateSha256 !== stateSha.right ||
    !sameJournalDescriptor(headDescriptor.right, value.headObservation.journalHead)
  ) {
    return fail("HEAD_MISMATCH", "journal record, observation and validated state do not form one exact local head")
  }

  const evidence = validateCanonicalAtomV2TransitionEvidenceBundle(value.evidence)
  if (Either.isLeft(evidence)) return fail("INPUT_INVALID", evidence.left.detail)
  if (
    evidence.right.effect !== null ||
    evidence.right.outcome !== null ||
    evidence.right.disposition !== null
  ) {
    return fail("PHASE_INVALID", "Permit eligibility accepts only pre-effect evidence")
  }
  if (
    !sameJournalDescriptor(headDescriptor.right, evidence.right.claimedPredecessor) ||
    evidence.right.claimedPredecessorStateRevision !== state.right.revision ||
    evidence.right.proposal.expectedStateRevision !== state.right.revision
  ) {
    return fail("PREDECESSOR_MISMATCH", "proposal and evidence do not name the exact validated local head")
  }
  if (state.right.acceptedTransitionIds.includes(evidence.right.proposal.transitionId)) {
    return fail("PROPOSAL_REPLAY", "transition id already occurs in the accepted state history")
  }
  const stateKeys = new Set(state.right.atoms.map(({ key }) => canonicalAtomV2KeyId(key)))
  if (evidence.right.proposal.readSet.some((key) => !stateKeys.has(canonicalAtomV2KeyId(key)))) {
    return fail("MEMBERSHIP_MISSING", "proposal read set contains a key outside the exact canonical state")
  }
  if (evidence.right.proposal.writes.some(({ key }) => stateKeys.has(canonicalAtomV2KeyId(key)))) {
    return fail("SELF_AUTHORIZATION", "proposal attempts to overwrite an admitted canonical key")
  }
  const permissionLineages = new Set(
    state.right.atoms
      .filter(({ kind }) =>
        CANONICAL_ATOM_V2_PERMISSION_BEARING_KINDS.has(kind)
      )
      .map(({ key }) => logicalKeyId(key))
  )
  if (
    evidence.right.proposal.writes.some(
      ({ key, kind }) =>
        CANONICAL_ATOM_V2_PERMISSION_BEARING_KINDS.has(kind) ||
        permissionLineages.has(logicalKeyId(key))
    )
  ) {
    return fail(
      "SELF_AUTHORIZATION",
      "v1 candidate transition cannot create or revise permission-bearing records"
    )
  }

  const policyDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(policy.right)
  const authorizationDecisionDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(
    currentAuthorization.right
  )
  const authorizationEvidenceDescriptor = describeCanonicalAtomV2TransitionEvidenceRecord(
    evidence.right.authorization
  )
  const trajectoryContractDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(
    trajectoryContract.right
  )
  const trajectoryEvidenceDescriptor = describeCanonicalAtomV2TransitionEvidenceRecord(
    evidence.right.trajectory
  )
  if (
    Either.isLeft(policyDescriptor) ||
    Either.isLeft(authorizationDecisionDescriptor) ||
    Either.isLeft(authorizationEvidenceDescriptor) ||
    Either.isLeft(trajectoryContractDescriptor) ||
    Either.isLeft(trajectoryEvidenceDescriptor)
  ) {
    return fail("CANONICAL_ENCODING_INVALID", "required evidence records have no exact canonical descriptors")
  }

  const policyRead = requirePreExistingRead(evidence.right, policy.right.policyRef)
  if (Either.isLeft(policyRead)) return Either.left(policyRead.left)
  const admittedPolicy = requireAdmittedRecord(
    state.right,
    policy.right.policyRef,
    HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
    policyDescriptor.right,
    true
  )
  if (Either.isLeft(admittedPolicy)) return Either.left(admittedPolicy.left)

  const authorizationRead = requirePreExistingRead(
    evidence.right,
    evidence.right.authorization.decisionRef
  )
  if (Either.isLeft(authorizationRead)) return Either.left(authorizationRead.left)
  const admittedAuthorization = requireAdmittedRecord(
    state.right,
    currentAuthorization.right.decisionRef,
    HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND,
    authorizationDecisionDescriptor.right,
    true
  )
  if (Either.isLeft(admittedAuthorization)) return Either.left(admittedAuthorization.left)

  const trajectoryRead = requirePreExistingRead(
    evidence.right,
    evidence.right.trajectory.traceRef
  )
  if (Either.isLeft(trajectoryRead)) return Either.left(trajectoryRead.left)
  const admittedTrajectory = requireAdmittedRecord(
    state.right,
    trajectoryContract.right.traceRef,
    HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND,
    trajectoryContractDescriptor.right,
    true
  )
  if (Either.isLeft(admittedTrajectory)) return Either.left(admittedTrajectory.left)

  if (
    !hasExactReference(
      admittedAuthorization.right,
      HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
      HSWM_CANONICAL_PERMIT_POLICY_ROLE,
      policy.right.policyRef
    ) ||
    evidence.right.authorization.subjects.some(
      ({ subject }) =>
        !hasExactReference(
          admittedAuthorization.right,
          HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
          subject
        )
    ) ||
    !hasExactReference(
      admittedTrajectory.right,
      HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
      HSWM_CANONICAL_PERMIT_POLICY_ROLE,
      policy.right.policyRef
    ) ||
    !hasExactReference(
      admittedTrajectory.right,
      HSWM_CANONICAL_PERMIT_AUTHORIZATION_REFERENCE_TYPE,
      HSWM_CANONICAL_PERMIT_AUTHORIZATION_ROLE,
      evidence.right.authorization.decisionRef
    )
  ) {
    return fail("MEMBERSHIP_CONTENT_MISMATCH", "admitted authorization or trajectory lacks its exact typed policy/subject relation")
  }

  const representedAuthorization = evidence.right.authorization
  const authorizationSubjectsMatch =
    currentAuthorization.right.subjects.length ===
      representedAuthorization.subjects.length &&
    currentAuthorization.right.subjects.every(
      (subject, index) =>
        representedAuthorization.subjects[index] !== undefined &&
        subjectId(subject) ===
          subjectId(representedAuthorization.subjects[index]!)
    )
  if (
    !sameKey(
      currentAuthorization.right.decisionRef,
      representedAuthorization.decisionRef
    ) ||
    !sameKey(currentAuthorization.right.policyRef, policy.right.policyRef) ||
    currentAuthorization.right.authorizationRef !==
      representedAuthorization.authorizationRef ||
    currentAuthorization.right.claimant.address !==
      representedAuthorization.claimant.address ||
    !authorizationSubjectsMatch ||
    currentAuthorization.right.authorizer.address !==
      representedAuthorization.authorizer.address ||
    currentAuthorization.right.scope !== representedAuthorization.scope ||
    currentAuthorization.right.purpose !== value.intent.purpose ||
    currentAuthorization.right.decision !== representedAuthorization.decision ||
    currentAuthorization.right.decidedAt !== representedAuthorization.decidedAt ||
    currentAuthorization.right.notBefore !== representedAuthorization.notBefore ||
    currentAuthorization.right.expiresAt !== representedAuthorization.expiresAt ||
    currentAuthorization.right.revocationStatus !==
      representedAuthorization.revocationStatus ||
    currentAuthorization.right.revocationCheckedAt !==
      representedAuthorization.revocationCheckedAt ||
    currentAuthorization.right.revokedAt !== representedAuthorization.revokedAt ||
    !sameNullableDescriptor(
      currentAuthorization.right.revocationEvidence,
      representedAuthorization.revocationEvidence
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      representedAuthorization.decisionEvidence,
      authorizationDecisionDescriptor.right
    )
  ) {
    return fail(
      "AUTHORIZATION_NOT_CURRENT",
      "represented transition authorization does not exactly mirror the admitted decision record"
    )
  }

  if (
    !sameKey(trajectoryContract.right.traceRef, evidence.right.trajectory.traceRef) ||
    !sameKey(trajectoryContract.right.policyRef, policy.right.policyRef) ||
    trajectoryContract.right.claimant.address !==
      evidence.right.trajectory.claimant.address ||
    trajectoryContract.right.scope !== evidence.right.proposal.scope ||
    trajectoryContract.right.purpose !== value.intent.purpose ||
    trajectoryContract.right.decision !== "ACTIVE" ||
    !trajectoryContract.right.allowedSealers.some(
      ({ address }) => address === evidence.right.trajectory.sealer.address
    )
  ) {
    return fail(
      "POLICY_INVALID",
      "trajectory evidence does not satisfy the admitted pre-existing trajectory contract"
    )
  }

  if (policy.right.decision !== "ACTIVE") {
    return fail("AUTHORITY_DENIED", "current Permit policy is suspended")
  }
  const scopeRule = policy.right.scopeRules.find(
    ({ scope, purpose }) =>
      scope === evidence.right.proposal.scope &&
      purpose === value.intent.purpose
  )
  if (
    scopeRule === undefined ||
    !scopeRule.authorizers.some(
      ({ address }) => address === evidence.right.authorization.authorizer.address
    ) ||
    evidence.right.proposal.writes.some(
      ({ kind }) => !scopeRule.allowedWriteKinds.includes(kind)
    )
  ) {
    return fail("AUTHORITY_DENIED", "no exact scope/purpose rule authorizes this authorizer and every candidate write kind")
  }
  if (
    classifyCanonicalAtomV2AuthorizationEvidence(
      evidence.right.authorization,
      value.evaluatedAt
    ) !== "EVIDENCE_GRANTED_NOT_PERMIT"
  ) {
    return fail("AUTHORIZATION_NOT_CURRENT", "authorization is not a coherent grant at the exact evaluation instant")
  }
  if (Date.parse(evidence.right.trajectory.sealedAt) > Date.parse(value.evaluatedAt)) {
    return fail("TIME_INVALID", "trajectory cannot be sealed after the Permit evaluation instant")
  }

  const consentBySubject = new Map(
    value.consents.map((consent) => [subjectId(consent.subject), consent] as const)
  )
  if (
    consentBySubject.size !== value.consents.length ||
    value.consents.length !== evidence.right.authorization.subjects.length
  ) {
    return fail("CONSENT_MISSING", "evaluation requires exactly one consent record per affected subject relation")
  }
  for (const subject of evidence.right.authorization.subjects) {
    const slot = policy.right.consentSlots.find(
      ({ subject: candidate }) => subjectId(candidate) === subjectId(subject)
    )
    const consent = consentBySubject.get(subjectId(subject))
    if (slot === undefined || consent === undefined) {
      return fail("CONSENT_MISSING", "affected subject has no exact policy-selected consent slot")
    }
    if (
      consent.consentRef.lineageId !== slot.consentLineageId ||
      consent.consentRef.atomUid !== slot.consentAtomUid ||
      !sameKey(consent.policyRef, policy.right.policyRef) ||
      consent.claimant.address !== evidence.right.proposal.actorClaim ||
      consent.scope !== evidence.right.proposal.scope ||
      consent.purpose !== value.intent.purpose ||
      !slot.controllers.some(
        ({ address }) => address === consent.consenter.address
      )
    ) {
      return fail("CONSENT_DENIED", "consent slot, controller, claimant, scope or purpose differs from policy and proposal")
    }
    if (!consentIsCurrent(consent, value.evaluatedAt)) {
      return fail("CONSENT_NOT_CURRENT", "consent is denied, withdrawn, outside its window, revoked or not checked at evaluation")
    }
    const consentRead = requirePreExistingRead(evidence.right, consent.consentRef)
    if (Either.isLeft(consentRead)) return Either.left(consentRead.left)
    const consentDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(consent)
    if (Either.isLeft(consentDescriptor)) return Either.left(consentDescriptor.left)
    const admittedConsent = requireAdmittedRecord(
      state.right,
      consent.consentRef,
      HSWM_CANONICAL_CONSENT_DECISION_V1_KIND,
      consentDescriptor.right,
      true
    )
    if (Either.isLeft(admittedConsent)) return Either.left(admittedConsent.left)
    if (
      !hasExactReference(
        admittedConsent.right,
        HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
        HSWM_CANONICAL_PERMIT_POLICY_ROLE,
        policy.right.policyRef
      ) ||
      !hasExactReference(
        admittedConsent.right,
        HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
        HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
        subject.subject
      )
    ) {
      return fail("MEMBERSHIP_CONTENT_MISMATCH", "admitted consent lacks its exact typed policy/subject relation")
    }
  }

  return Either.right(value)
}

export const canonicalAtomV2CurrentStatePermitInputBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2CurrentStatePermitError> => {
  const checked = validateCanonicalAtomV2CurrentStatePermitInput(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const decodeCanonicalAtomV2CurrentStatePermitInputBytes = (
  input: Uint8Array
): Either.Either<CanonicalAtomV2CurrentStatePermitInput, CanonicalAtomV2CurrentStatePermitError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  const checked = validateCanonicalAtomV2CurrentStatePermitInput(parsed.right)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const canonical = canonicalAtomV2CurrentStatePermitInputBytes(checked.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return sameBytes(input, canonical.right)
    ? Either.right(checked.right)
    : fail("CANONICAL_ENCODING_INVALID", "Permit input bytes are not exact canonical JSON/v1")
}

export const describeCanonicalAtomV2CurrentStatePermitInput = (
  input: unknown
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2CurrentStatePermitError> => {
  const bytes = canonicalAtomV2CurrentStatePermitInputBytes(input)
  if (Either.isLeft(bytes)) return Either.left(bytes.left)
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_INPUT_V1_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(descriptor)
    ? fail("CANONICAL_ENCODING_INVALID", descriptor.left.detail)
    : Either.right(descriptor.right)
}

export const resolveCanonicalAtomV2CurrentStatePermitEligibility = (
  input: unknown
): Either.Either<CanonicalAtomV2CurrentStatePermitResolution, CanonicalAtomV2CurrentStatePermitError> => {
  const checked = validateCanonicalAtomV2CurrentStatePermitInput(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const value = checked.right
  const inputDescriptor = describeCanonicalAtomV2CurrentStatePermitInput(value)
  const policyDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(value.policy)
  const authorizationDecisionDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(
    value.authorizationDecision
  )
  const authorizationEvidenceDescriptor = describeCanonicalAtomV2TransitionEvidenceRecord(
    value.evidence.authorization
  )
  const trajectoryContractDescriptor = describeCanonicalAtomV2CurrentStatePermitRecord(
    value.trajectoryContract
  )
  const trajectoryEvidenceDescriptor = describeCanonicalAtomV2TransitionEvidenceRecord(
    value.evidence.trajectory
  )
  const consentDescriptors = value.consents.map(
    describeCanonicalAtomV2CurrentStatePermitRecord
  )
  const exactConsentDescriptors: Array<CanonicalAtomV2ContentDescriptor> = []
  for (const descriptor of consentDescriptors) {
    if (Either.isLeft(descriptor)) {
      return fail(
        "CANONICAL_ENCODING_INVALID",
        "validated consent lost its exact descriptor"
      )
    }
    exactConsentDescriptors.push(descriptor.right)
  }
  if (
    Either.isLeft(inputDescriptor) ||
    Either.isLeft(policyDescriptor) ||
    Either.isLeft(authorizationDecisionDescriptor) ||
    Either.isLeft(authorizationEvidenceDescriptor) ||
    Either.isLeft(trajectoryContractDescriptor) ||
    Either.isLeft(trajectoryEvidenceDescriptor)
  ) {
    return fail("CANONICAL_ENCODING_INVALID", "validated Permit inputs lost their exact descriptors")
  }
  return Either.right(
    snapshot({
      _tag: "CanonicalAtomV2CurrentStatePermitResolution",
      contractVersion: HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
      status: "ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_CANONICAL_PERMIT",
      snapshotBasis: "SUPPLIED_STATE_AND_HEAD_RECORD_NOT_JOURNAL_REPLAY",
      schema: value.headObservation.schema,
      journalLineageId: value.headObservation.journalLineageId,
      journalHead: value.headObservation.journalHead,
      stateRevision: value.headObservation.stateRevision,
      stateSha256: value.headObservation.stateSha256,
      evaluationInput: inputDescriptor.right,
      proposal: value.evidence.proposalDescriptor,
      policy: policyDescriptor.right,
      authorizationDecision: authorizationDecisionDescriptor.right,
      authorizationEvidence: authorizationEvidenceDescriptor.right,
      trajectoryContract: trajectoryContractDescriptor.right,
      trajectoryEvidence: trajectoryEvidenceDescriptor.right,
      consents: exactConsentDescriptors,
      evaluatedAt: value.evaluatedAt,
      timeBasis: "CALLER_SUPPLIED_INSTANT_NOT_TRUSTED_CURRENT_TIME",
      headFreshness: "LOCAL_OBSERVATION_NOT_ANTI_ROLLBACK_PROOF",
      capability: "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY",
      admission: "NOT_ADMITTED_BY_THIS_RESOLUTION",
      externalEffect: "NOT_DISPATCHED_NOT_OBSERVED",
      learning: "NOT_CAUSAL_CREDIT_NOT_LEARNING"
    } satisfies CanonicalAtomV2CurrentStatePermitResolution)
  )
}

export type CanonicalAtomV2CurrentStatePermitResolutionFailure =
  | CanonicalAtomV2CurrentStatePermitError
  | CanonicalAtomV2DurableRecoveryFailure

/**
 * Resolves against exactly one recovered durable-runtime snapshot. The result
 * remains local-head-relative and cannot be passed back as a submit capability.
 */
export const resolveCanonicalAtomV2CurrentStatePermitEligibilityAtDurableRuntime = (
  input: unknown
): Effect.Effect<
  CanonicalAtomV2CurrentStatePermitResolution,
  CanonicalAtomV2CurrentStatePermitResolutionFailure,
  CanonicalAtomV2DurableRuntime
> =>
  Effect.gen(function* () {
    const retained = decodeInput(input)
    if (Either.isLeft(retained)) return yield* retained.left
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const observed = yield* runtime.snapshot
    const suppliedStateBytes = canonicalJsonBytes(retained.right.state)
    const observedStateBytes = canonicalJsonBytes(observed.canonical)
    if (
      retained.right.schema.schemaVersion !== runtime.schema.schemaVersion ||
      !sameCanonicalAtomV2SchemaBinding(
        retained.right.headObservation.schema,
        runtime.schemaContent
      ) ||
      retained.right.headObservation.journalLineageId !==
        observed.journalLineageId ||
      !sameJournalDescriptor(
        observed.journalHead,
        retained.right.headObservation.journalHead
      ) ||
      retained.right.headObservation.stateRevision !==
        observed.canonical.revision ||
      Either.isLeft(suppliedStateBytes) ||
      Either.isLeft(observedStateBytes) ||
      !sameBytes(suppliedStateBytes.right, observedStateBytes.right)
    ) {
      return yield* new CanonicalAtomV2CurrentStatePermitError({
        code: "HEAD_MISMATCH",
        detail:
          "Permit input does not describe the one recovered durable-runtime snapshot",
        permitStatus: "NOT_CANONICAL_PERMIT"
      })
    }
    const resolution = resolveCanonicalAtomV2CurrentStatePermitEligibility(
      retained.right
    )
    return Either.isLeft(resolution)
      ? yield* resolution.left
      : snapshot({
          ...resolution.right,
          status:
            "ELIGIBLE_AT_RECOVERED_LOCAL_HEAD_FOR_SUPPLIED_TIME_NOT_CANONICAL_PERMIT",
          snapshotBasis: "ONE_DURABLE_RUNTIME_RECOVERY_SNAPSHOT"
        } satisfies CanonicalAtomV2CurrentStatePermitResolution)
  })

export const canonicalAtomV2CurrentStatePermitResolutionBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2CurrentStatePermitError> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2CurrentStatePermitResolutionSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail("INPUT_INVALID", "Permit resolution violates its strict read-only contract")
  }
  const bytes = canonicalJsonBytes(decoded.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const describeCanonicalAtomV2CurrentStatePermitResolution = (
  input: unknown
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2CurrentStatePermitError> => {
  const bytes = canonicalAtomV2CurrentStatePermitResolutionBytes(input)
  if (Either.isLeft(bytes)) return Either.left(bytes.left)
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_RESOLUTION_V1_MEDIA_TYPE,
    bytes.right
  )
  return Either.isLeft(descriptor)
    ? fail("CANONICAL_ENCODING_INVALID", descriptor.left.detail)
    : Either.right(descriptor.right)
}

export const decodeCanonicalAtomV2CurrentStatePermitResolutionBytes = (
  input: Uint8Array
): Either.Either<CanonicalAtomV2CurrentStatePermitResolution, CanonicalAtomV2CurrentStatePermitError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2CurrentStatePermitResolutionSchema,
    { onExcessProperty: "error" }
  )(parsed.right)
  if (Either.isLeft(decoded)) {
    return fail("INPUT_INVALID", "Permit resolution violates its strict read-only contract")
  }
  const canonical = canonicalAtomV2CurrentStatePermitResolutionBytes(decoded.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return sameBytes(input, canonical.right)
    ? Either.right(snapshot(decoded.right))
    : fail("CANONICAL_ENCODING_INVALID", "Permit resolution bytes are not exact canonical JSON/v1")
}
