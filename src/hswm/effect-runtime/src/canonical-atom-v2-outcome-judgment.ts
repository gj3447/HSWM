import { Data, Either, Schema } from "effect"

import {
  CanonicalAtomV2ContentDescriptorSchema,
  CanonicalAtomV2SchemaContentBindingSchema,
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  CommitCanonicalAtomsV2CommandSchema,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command
} from "./canonical-atom-v2-schema.js"
import {
  CanonicalAtomV2EvidencePrincipalSchema,
  CanonicalAtomV2SealedTrajectoryEvidenceSchema,
  HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
  describeCanonicalAtomV2TransitionEvidenceRecord,
  validateCanonicalAtomV2TransitionEvidenceRecord,
  type CanonicalAtomV2EvidencePrincipal,
  type CanonicalAtomV2SealedTrajectoryEvidence
} from "./canonical-atom-v2-transition-evidence.js"

/**
 * A typed observation and a revision-support judgment have separate owners.
 * This codec proves structural binding only; it cannot establish truth, causal
 * credit, canonical Permit, admission, or learning.
 */
export const HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION =
  "hswm-canonical-owner-bound-outcome/v1" as const
export const HSWM_CANONICAL_OUTCOME_OBSERVATION_V1_MEDIA_TYPE =
  "application/vnd.hswm.owner-bound-outcome-observation-v1+json" as const
export const HSWM_CANONICAL_REVISION_SUPPORT_JUDGMENT_V1_MEDIA_TYPE =
  "application/vnd.hswm.revision-support-judgment-v1+json" as const
export const HSWM_CANONICAL_OUTCOME_JUDGMENT_BUNDLE_V1_MEDIA_TYPE =
  "application/vnd.hswm.owner-bound-outcome-judgment-bundle-v1+json" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const CanonicalInstant = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
)
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

export interface CanonicalAtomV2LogicalAddress {
  readonly schemaVersion: string
  readonly lineageId: string
  readonly atomUid: string
}

const CanonicalAtomV2LogicalAddressSchema: Schema.Schema<CanonicalAtomV2LogicalAddress> =
  Schema.Struct({
    schemaVersion: Identifier,
    lineageId: Identifier,
    atomUid: Identifier
  })

export interface CanonicalAtomV2OwnerBoundOutcomeObservation {
  readonly _tag: "CanonicalAtomV2OwnerBoundOutcomeObservation"
  readonly contractVersion: typeof HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly observationId: string
  readonly traceId: string
  readonly trajectory: CanonicalAtomV2ContentDescriptor
  readonly responsibilityOwner: CanonicalAtomV2EvidencePrincipal
  readonly evaluator: CanonicalAtomV2EvidencePrincipal
  readonly observedAt: string
  readonly observation: CanonicalAtomV2ContentDescriptor | null
  readonly result: "OBSERVED" | "FAILED" | "UNKNOWN"
  readonly evidence: CanonicalAtomV2ContentDescriptor
  readonly ownerStatus: "REPRESENTED_SINGLE_RESPONSIBILITY_OWNER_NOT_AUTHENTICATED"
  readonly independence: "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
  readonly observationStatus: "REPRESENTED_OBSERVATION_NOT_TRUTH_NOT_REVISION_SUPPORT"
}

export const CanonicalAtomV2OwnerBoundOutcomeObservationSchema: Schema.Schema<CanonicalAtomV2OwnerBoundOutcomeObservation> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2OwnerBoundOutcomeObservation"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
    ),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    observationId: Identifier,
    traceId: Identifier,
    trajectory: CanonicalAtomV2ContentDescriptorSchema,
    responsibilityOwner: CanonicalAtomV2EvidencePrincipalSchema,
    evaluator: CanonicalAtomV2EvidencePrincipalSchema,
    observedAt: CanonicalInstant,
    observation: Schema.NullOr(CanonicalAtomV2ContentDescriptorSchema),
    result: Schema.Literal("OBSERVED", "FAILED", "UNKNOWN"),
    evidence: CanonicalAtomV2ContentDescriptorSchema,
    ownerStatus: Schema.Literal(
      "REPRESENTED_SINGLE_RESPONSIBILITY_OWNER_NOT_AUTHENTICATED"
    ),
    independence: Schema.Literal(
      "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
    ),
    observationStatus: Schema.Literal(
      "REPRESENTED_OBSERVATION_NOT_TRUTH_NOT_REVISION_SUPPORT"
    )
  })

export interface CanonicalAtomV2RevisionSupportJudgment {
  readonly _tag: "CanonicalAtomV2RevisionSupportJudgment"
  readonly contractVersion: typeof HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly judgmentId: string
  readonly traceId: string
  readonly observationId: string
  readonly proposal: CanonicalAtomV2ContentDescriptor
  readonly trajectory: CanonicalAtomV2ContentDescriptor
  readonly observation: CanonicalAtomV2ContentDescriptor
  readonly target: CanonicalAtomV2LogicalAddress
  readonly expectedRevisionId: number
  readonly candidateRevisionId: number
  readonly responsibilityOwner: CanonicalAtomV2EvidencePrincipal
  readonly adjudicator: CanonicalAtomV2EvidencePrincipal
  readonly criterion: CanonicalAtomV2ContentDescriptor
  readonly criterionCommittedAt: string
  readonly decidedAt: string
  readonly verdict: "SUPPORTS" | "REJECTS" | "INDETERMINATE"
  readonly evidence: CanonicalAtomV2ContentDescriptor
  readonly ownerStatus: "REPRESENTED_SINGLE_RESPONSIBILITY_OWNER_NOT_AUTHENTICATED"
  readonly independence: "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
  readonly judgmentStatus: "REPRESENTED_REVISION_SUPPORT_JUDGMENT_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

export const CanonicalAtomV2RevisionSupportJudgmentSchema: Schema.Schema<CanonicalAtomV2RevisionSupportJudgment> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2RevisionSupportJudgment"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
    ),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    judgmentId: Identifier,
    traceId: Identifier,
    observationId: Identifier,
    proposal: CanonicalAtomV2ContentDescriptorSchema,
    trajectory: CanonicalAtomV2ContentDescriptorSchema,
    observation: CanonicalAtomV2ContentDescriptorSchema,
    target: CanonicalAtomV2LogicalAddressSchema,
    expectedRevisionId: SafeInteger,
    candidateRevisionId: SafeInteger,
    responsibilityOwner: CanonicalAtomV2EvidencePrincipalSchema,
    adjudicator: CanonicalAtomV2EvidencePrincipalSchema,
    criterion: CanonicalAtomV2ContentDescriptorSchema,
    criterionCommittedAt: CanonicalInstant,
    decidedAt: CanonicalInstant,
    verdict: Schema.Literal("SUPPORTS", "REJECTS", "INDETERMINATE"),
    evidence: CanonicalAtomV2ContentDescriptorSchema,
    ownerStatus: Schema.Literal(
      "REPRESENTED_SINGLE_RESPONSIBILITY_OWNER_NOT_AUTHENTICATED"
    ),
    independence: Schema.Literal(
      "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
    ),
    judgmentStatus: Schema.Literal(
      "REPRESENTED_REVISION_SUPPORT_JUDGMENT_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
    )
  })

export type CanonicalAtomV2OwnerBoundOutcomeRecord =
  | CanonicalAtomV2OwnerBoundOutcomeObservation
  | CanonicalAtomV2RevisionSupportJudgment

const CanonicalAtomV2OwnerBoundOutcomeRecordSchema: Schema.Schema<CanonicalAtomV2OwnerBoundOutcomeRecord> =
  Schema.Union(
    CanonicalAtomV2OwnerBoundOutcomeObservationSchema,
    CanonicalAtomV2RevisionSupportJudgmentSchema
  )

export interface CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle {
  readonly _tag: "CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle"
  readonly contractVersion: typeof HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly proposal: CommitCanonicalAtomsV2Command
  readonly proposalDescriptor: CanonicalAtomV2ContentDescriptor
  readonly trajectory: CanonicalAtomV2SealedTrajectoryEvidence
  readonly trajectoryDescriptor: CanonicalAtomV2ContentDescriptor
  readonly observation: CanonicalAtomV2OwnerBoundOutcomeObservation
  readonly observationDescriptor: CanonicalAtomV2ContentDescriptor
  readonly judgment: CanonicalAtomV2RevisionSupportJudgment
  readonly judgmentDescriptor: CanonicalAtomV2ContentDescriptor
  readonly bundleStatus: "STRUCTURALLY_BOUND_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

const CanonicalAtomV2OwnerBoundOutcomeJudgmentBundleSchema: Schema.Schema<CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
    ),
    schema: CanonicalAtomV2SchemaContentBindingSchema,
    proposal: CommitCanonicalAtomsV2CommandSchema,
    proposalDescriptor: CanonicalAtomV2ContentDescriptorSchema,
    trajectory: CanonicalAtomV2SealedTrajectoryEvidenceSchema,
    trajectoryDescriptor: CanonicalAtomV2ContentDescriptorSchema,
    observation: CanonicalAtomV2OwnerBoundOutcomeObservationSchema,
    observationDescriptor: CanonicalAtomV2ContentDescriptorSchema,
    judgment: CanonicalAtomV2RevisionSupportJudgmentSchema,
    judgmentDescriptor: CanonicalAtomV2ContentDescriptorSchema,
    bundleStatus: Schema.Literal(
      "STRUCTURALLY_BOUND_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
    )
  })

export class CanonicalAtomV2OutcomeJudgmentError extends Data.TaggedError(
  "CanonicalAtomV2OutcomeJudgmentError"
)<{
  readonly code:
    | "BINDING_MISMATCH"
    | "CANONICAL_ENCODING_INVALID"
    | "CHRONOLOGY_INVALID"
    | "DESCRIPTOR_MISMATCH"
    | "INPUT_INVALID"
    | "REVISION_INVALID"
    | "ROLE_SEPARATION_INVALID"
    | "VERDICT_INVALID"
  readonly detail: string
}> {}

const fail = (
  code: CanonicalAtomV2OutcomeJudgmentError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2OutcomeJudgmentError> =>
  Either.left(new CanonicalAtomV2OutcomeJudgmentError({ code, detail }))

const validInstant = (value: string): boolean => {
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value
}

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameSchemaBinding = (
  left: CanonicalAtomV2SchemaContentBinding,
  right: CanonicalAtomV2SchemaContentBinding
): boolean =>
  left.schemaVersion === right.schemaVersion &&
  sameCanonicalAtomV2ContentDescriptor(left.content, right.content)

const sameLogicalAddress = (
  address: CanonicalAtomV2LogicalAddress,
  key: CanonicalAtomV2Key
): boolean =>
  address.schemaVersion === key.schemaVersion &&
  address.lineageId === key.lineageId &&
  address.atomUid === key.atomUid

const sameKeys = (
  left: ReadonlyArray<CanonicalAtomV2Key>,
  right: ReadonlyArray<CanonicalAtomV2Key>
): boolean =>
  left.length === right.length &&
  left.every(
    (key, index) =>
      right[index] !== undefined &&
      canonicalAtomV2KeyId(key) === canonicalAtomV2KeyId(right[index]!)
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

const describeValue = (
  mediaType: string,
  value: unknown
): Either.Either<
  CanonicalAtomV2ContentDescriptor,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const bytes = canonicalJsonBytes(value)
  if (Either.isLeft(bytes)) {
    return fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
  }
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    mediaType,
    bytes.right
  )
  return Either.isLeft(descriptor)
    ? fail("DESCRIPTOR_MISMATCH", descriptor.left.detail)
    : Either.right(descriptor.right)
}

const validateRecord = (
  input: unknown
): Either.Either<
  CanonicalAtomV2OwnerBoundOutcomeRecord,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2OwnerBoundOutcomeRecordSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail("INPUT_INVALID", "outcome record violates its strict v1 schema")
  }
  const record = decoded.right
  if (
    !validInstant(
      record._tag === "CanonicalAtomV2OwnerBoundOutcomeObservation"
        ? record.observedAt
        : record.criterionCommittedAt
    ) ||
    (record._tag === "CanonicalAtomV2RevisionSupportJudgment" &&
      !validInstant(record.decidedAt))
  ) {
    return fail("CHRONOLOGY_INVALID", "record contains a noncanonical instant")
  }
  if (
    record._tag === "CanonicalAtomV2OwnerBoundOutcomeObservation" &&
    record.result === "OBSERVED" &&
    record.observation === null
  ) {
    return fail("VERDICT_INVALID", "OBSERVED requires exact observation content")
  }
  if (
    record._tag === "CanonicalAtomV2RevisionSupportJudgment" &&
    Date.parse(record.criterionCommittedAt) > Date.parse(record.decidedAt)
  ) {
    return fail("CHRONOLOGY_INVALID", "criterion cannot be committed after judgment")
  }
  return Either.right(snapshot(record))
}

export const validateCanonicalAtomV2OwnerBoundOutcomeRecord = validateRecord

export const describeCanonicalAtomV2OwnerBoundOutcomeRecord = (
  input: unknown
): Either.Either<
  CanonicalAtomV2ContentDescriptor,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const checked = validateRecord(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  return describeValue(
    checked.right._tag === "CanonicalAtomV2OwnerBoundOutcomeObservation"
      ? HSWM_CANONICAL_OUTCOME_OBSERVATION_V1_MEDIA_TYPE
      : HSWM_CANONICAL_REVISION_SUPPORT_JUDGMENT_V1_MEDIA_TYPE,
    checked.right
  )
}

export const canonicalAtomV2OwnerBoundOutcomeRecordBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2OutcomeJudgmentError> => {
  const checked = validateRecord(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const decodeCanonicalAtomV2OwnerBoundOutcomeRecordBytes = (
  input: Uint8Array
): Either.Either<
  CanonicalAtomV2OwnerBoundOutcomeRecord,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = validateRecord(parsed.right)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const canonical = canonicalAtomV2OwnerBoundOutcomeRecordBytes(checked.right)
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return sameBytes(input, canonical.right)
    ? checked
    : fail("CANONICAL_ENCODING_INVALID", "outcome record bytes are not exact canonical JSON/v1")
}

const proposalDescriptor = (
  proposal: CommitCanonicalAtomsV2Command
): Either.Either<
  CanonicalAtomV2ContentDescriptor,
  CanonicalAtomV2OutcomeJudgmentError
> => describeValue(HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE, proposal)

const exactPredecessor = (
  proposal: CommitCanonicalAtomsV2Command,
  candidateKey: CanonicalAtomV2Key
): CanonicalAtomV2Key | undefined => {
  const write = proposal.writes[0]
  if (write === undefined) return undefined
  const supersedes = write.references.filter(
    ({ referenceType, role }) =>
      referenceType === HSWM_SUPERSEDES_REFERENCE_TYPE &&
      role === HSWM_SUPERSEDES_REFERENCE_ROLE
  )
  if (supersedes.length !== 1) return undefined
  const predecessor = supersedes[0]?.target
  if (
    predecessor === undefined ||
    predecessor.schemaVersion !== candidateKey.schemaVersion ||
    predecessor.lineageId !== candidateKey.lineageId ||
    predecessor.atomUid !== candidateKey.atomUid ||
    !proposal.readSet.some(
      (key) => canonicalAtomV2KeyId(key) === canonicalAtomV2KeyId(predecessor)
    )
  ) {
    return undefined
  }
  return predecessor
}

export const validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle = (
  input: unknown
): Either.Either<
  CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const decoded = Schema.decodeUnknownEither(
    CanonicalAtomV2OwnerBoundOutcomeJudgmentBundleSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail("INPUT_INVALID", "outcome bundle violates its strict v1 schema")
  }
  const bundle = decoded.right
  const trajectory = validateCanonicalAtomV2TransitionEvidenceRecord(
    bundle.trajectory
  )
  if (
    Either.isLeft(trajectory) ||
    trajectory.right._tag !== "CanonicalAtomV2SealedTrajectoryEvidence"
  ) {
    return fail("INPUT_INVALID", "bundle trajectory is not valid sealed-trajectory evidence")
  }
  const observation = validateRecord(bundle.observation)
  const judgment = validateRecord(bundle.judgment)
  if (
    Either.isLeft(observation) ||
    observation.right._tag !== "CanonicalAtomV2OwnerBoundOutcomeObservation" ||
    Either.isLeft(judgment) ||
    judgment.right._tag !== "CanonicalAtomV2RevisionSupportJudgment"
  ) {
    return fail("INPUT_INVALID", "bundle records do not retain observation and judgment roles")
  }
  const exactProposal = proposalDescriptor(bundle.proposal)
  const exactTrajectory = describeCanonicalAtomV2TransitionEvidenceRecord(
    trajectory.right
  )
  const exactObservation = describeCanonicalAtomV2OwnerBoundOutcomeRecord(
    observation.right
  )
  const exactJudgment = describeCanonicalAtomV2OwnerBoundOutcomeRecord(
    judgment.right
  )
  if (
    Either.isLeft(exactProposal) ||
    Either.isLeft(exactTrajectory) ||
    Either.isLeft(exactObservation) ||
    Either.isLeft(exactJudgment)
  ) {
    return fail("DESCRIPTOR_MISMATCH", "bundle component descriptor could not be recomputed")
  }
  if (
    !sameCanonicalAtomV2ContentDescriptor(
      bundle.proposalDescriptor,
      exactProposal.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      bundle.trajectoryDescriptor,
      exactTrajectory.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      bundle.observationDescriptor,
      exactObservation.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      bundle.judgmentDescriptor,
      exactJudgment.right
    )
  ) {
    return fail("DESCRIPTOR_MISMATCH", "bundle descriptor differs from exact record bytes")
  }
  if (
    !sameSchemaBinding(bundle.schema, trajectory.right.schema) ||
    !sameSchemaBinding(bundle.schema, observation.right.schema) ||
    !sameSchemaBinding(bundle.schema, judgment.right.schema) ||
    bundle.proposal.schemaVersion !== bundle.schema.schemaVersion
  ) {
    return fail("BINDING_MISMATCH", "bundle components do not bind one exact schema")
  }
  if (
    !sameCanonicalAtomV2ContentDescriptor(
      trajectory.right.proposal,
      exactProposal.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      observation.right.trajectory,
      exactTrajectory.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      judgment.right.proposal,
      exactProposal.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      judgment.right.trajectory,
      exactTrajectory.right
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      judgment.right.observation,
      exactObservation.right
    ) ||
    observation.right.traceId !== trajectory.right.traceId ||
    judgment.right.traceId !== trajectory.right.traceId ||
    judgment.right.observationId !== observation.right.observationId ||
    bundle.proposal.traceRef === null ||
    canonicalAtomV2KeyId(bundle.proposal.traceRef) !==
      canonicalAtomV2KeyId(trajectory.right.traceRef) ||
    trajectory.right.traceId !== trajectory.right.traceRef.atomUid ||
    trajectory.right.claimant.address !== bundle.proposal.actorClaim ||
    trajectory.right.claimedPredecessorStateRevision !==
      bundle.proposal.expectedStateRevision ||
    !sameKeys(trajectory.right.readSet, bundle.proposal.readSet) ||
    !sameKeys(
      trajectory.right.writeSet,
      bundle.proposal.writes.map(({ key }) => key)
    )
  ) {
    return fail("BINDING_MISMATCH", "proposal, trace, observation and judgment are not exactly cross-bound")
  }
  if (bundle.proposal.writes.length !== 1) {
    return fail("REVISION_INVALID", "bounded v1 requires exactly one proposal write")
  }
  const candidate = bundle.proposal.writes[0]!
  const predecessor = exactPredecessor(bundle.proposal, candidate.key)
  if (
    predecessor === undefined ||
    !sameLogicalAddress(judgment.right.target, candidate.key) ||
    judgment.right.expectedRevisionId !== predecessor.revisionId ||
    judgment.right.candidateRevisionId !== candidate.key.revisionId ||
    candidate.key.revisionId !== predecessor.revisionId + 1
  ) {
    return fail("REVISION_INVALID", "judgment does not bind one exact linear successor proposal")
  }
  const actor = bundle.proposal.actorClaim
  if (
    observation.right.responsibilityOwner.address === actor ||
    observation.right.evaluator.address === actor ||
    judgment.right.responsibilityOwner.address === actor ||
    judgment.right.adjudicator.address === actor ||
    judgment.right.responsibilityOwner.address ===
      observation.right.responsibilityOwner.address ||
    judgment.right.adjudicator.address === observation.right.evaluator.address
  ) {
    return fail("ROLE_SEPARATION_INVALID", "actor, outcome and judgment role addresses must satisfy bounded separation")
  }
  if (
    Date.parse(judgment.right.criterionCommittedAt) >
      Date.parse(trajectory.right.sealedAt) ||
    Date.parse(trajectory.right.sealedAt) >
      Date.parse(observation.right.observedAt) ||
    Date.parse(observation.right.observedAt) > Date.parse(judgment.right.decidedAt)
  ) {
    return fail("CHRONOLOGY_INVALID", "criterion, seal, observation and judgment chronology is inverted")
  }
  if (
    judgment.right.verdict === "SUPPORTS" &&
    (observation.right.result !== "OBSERVED" ||
      observation.right.observation === null)
  ) {
    return fail("VERDICT_INVALID", "SUPPORTS requires a represented observed outcome")
  }
  return Either.right(snapshot(bundle))
}

export const describeCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle = (
  input: unknown
): Either.Either<
  CanonicalAtomV2ContentDescriptor,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const checked = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  return describeValue(
    HSWM_CANONICAL_OUTCOME_JUDGMENT_BUNDLE_V1_MEDIA_TYPE,
    checked.right
  )
}

export const canonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes = (
  input: unknown
): Either.Either<Uint8Array, CanonicalAtomV2OutcomeJudgmentError> => {
  const checked = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Uint8Array.from(bytes.right))
}

export const decodeCanonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes = (
  input: Uint8Array
): Either.Either<
  CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle,
  CanonicalAtomV2OutcomeJudgmentError
> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(
    parsed.right
  )
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const canonical = canonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes(
    checked.right
  )
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return sameBytes(input, canonical.right)
    ? checked
    : fail("CANONICAL_ENCODING_INVALID", "outcome bundle bytes are not exact canonical JSON/v1")
}
