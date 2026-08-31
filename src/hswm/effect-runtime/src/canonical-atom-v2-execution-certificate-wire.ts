import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  CanonicalPermitEnvelopeSchema,
  type CanonicalPermitEnvelope,
  type CanonicalPermitExpectedBindings,
  verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext
} from "./canonical-atom-v2-permit-envelope.js"

/**
 * Raw-byte companion to `formal/HSWMExecutionCertificateWire.lean`.
 *
 * Acceptance is intentionally structural and caller-relative. It is not a
 * proof that TypeScript refines Lean, that an execution occurred, that a
 * Permit issuer is authoritative, that storage is atomic, that an outcome is
 * true, that causal credit is independent, or that learning improved an LLM.
 */
export const HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION =
  "hswm-execution-intent-wire/v1" as const
export const HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION =
  "hswm-execution-certificate-wire/v1" as const
export const HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION =
  "hswm-signature-independent-commit-plan/v1" as const
export const HSWM_EXECUTION_WIRE_CANONICALIZATION = "hswm-canonical-json/v1" as const
export const HSWM_EXECUTION_INTENT_WIRE_STATUS =
  "PRE_EXECUTION_INTENT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const
export const HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS =
  "STRUCTURALLY_BOUND_EXECUTION_CERTIFICATE_NOT_RUNTIME_OCCURRENCE_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING" as const
export const HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS =
  "SIGNATURE_INDEPENDENT_COMMIT_PLAN_NOT_PERMIT_ENVELOPE_NOT_CERTIFICATE" as const
export const HSWM_EXECUTION_CERTIFICATE_WIRE_PHASE_A_STATUS =
  "DECODED_FIELD_AND_CALLER_RELATIVE_ENVELOPE_CHECKED_NOT_TS_TO_LEAN_REFINEMENT_NOT_RUNTIME_OCCURRENCE_NOT_ATOMIC_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING" as const
export const HSWM_EXECUTION_CERTIFICATE_WIRE_COMPLETE_CHECK_STATUS =
  "COMPLETE_DECODED_FIELD_AND_RAW_ARTIFACT_CHECKED_NOT_TS_TO_LEAN_REFINEMENT_NOT_RUNTIME_OCCURRENCE_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const MediaType = Schema.String.pipe(
  Schema.pattern(
    /^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/
  ),
  Schema.maxLength(255)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

export interface ExecutionWireArtifactRef {
  readonly mediaType: string
  readonly byteLength: number
  readonly digest: string
}

export const ExecutionWireArtifactRefSchema: Schema.Schema<ExecutionWireArtifactRef> =
  Schema.Struct({ mediaType: MediaType, byteLength: SafeInteger, digest: Sha256 })

export interface ExecutionWireHead {
  readonly lineageId: string
  readonly sequence: number
  readonly stateDigest: string
  readonly recordDigest: string
}

export const ExecutionWireHeadSchema: Schema.Schema<ExecutionWireHead> = Schema.Struct({
  lineageId: Identifier,
  sequence: SafeInteger,
  stateDigest: Sha256,
  recordDigest: Sha256
})

export interface RecordIndependentSuccessorHeadWire {
  readonly lineageId: string
  readonly sequence: number
  readonly stateDigest: string
}

export const RecordIndependentSuccessorHeadWireSchema: Schema.Schema<RecordIndependentSuccessorHeadWire> =
  Schema.Struct({ lineageId: Identifier, sequence: SafeInteger, stateDigest: Sha256 })

export interface ExecutionWireTarget {
  readonly schemaVersion: string
  readonly lineageId: string
  readonly atomUid: string
}

export const ExecutionWireTargetSchema: Schema.Schema<ExecutionWireTarget> = Schema.Struct({
  schemaVersion: Identifier,
  lineageId: Identifier,
  atomUid: Identifier
})

export interface ExecutionWireProposal {
  readonly target: ExecutionWireTarget
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly proposer: string
  readonly traceId: string
  readonly authorizationRef: string
  readonly scope: string
}

export const ExecutionWireProposalSchema: Schema.Schema<ExecutionWireProposal> = Schema.Struct({
  target: ExecutionWireTargetSchema,
  expectedRevision: Identifier,
  candidateRevision: Identifier,
  proposer: Identifier,
  traceId: Identifier,
  authorizationRef: Identifier,
  scope: Identifier
})

export interface SignatureIndependentCommitPlanWire {
  readonly contractVersion: typeof HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION
  readonly status: typeof HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS
  readonly executionId: string
  readonly predecessorHead: ExecutionWireHead
  /** Record digest is deliberately absent, preventing a SHA fixed-point cycle. */
  readonly successor: RecordIndependentSuccessorHeadWire
  readonly target: ExecutionWireTarget
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly permitContentDigest: string
  readonly invariantContentDigest: string
  readonly commitLinearizationIndex: number
}

export const SignatureIndependentCommitPlanWireSchema: Schema.Schema<SignatureIndependentCommitPlanWire> =
  Schema.Struct({
    contractVersion: Schema.Literal(
      HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_V1_CONTRACT_VERSION
    ),
    status: Schema.Literal(HSWM_SIGNATURE_INDEPENDENT_COMMIT_PLAN_STATUS),
    executionId: Identifier,
    predecessorHead: ExecutionWireHeadSchema,
    successor: RecordIndependentSuccessorHeadWireSchema,
    target: ExecutionWireTargetSchema,
    expectedRevision: Identifier,
    candidateRevision: Identifier,
    permitContentDigest: Sha256,
    invariantContentDigest: Sha256,
    commitLinearizationIndex: SafeInteger
  })

export interface ExecutionIntentWire {
  readonly contractVersion: typeof HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION
  readonly canonicalization: typeof HSWM_EXECUTION_WIRE_CANONICALIZATION
  readonly status: typeof HSWM_EXECUTION_INTENT_WIRE_STATUS
  readonly executionId: string
  readonly permitId: string
  readonly permitContentDigest: string
  readonly proposalDigest: string
  readonly expectedSuccessorHead: ExecutionWireHead
  readonly authorizer: string
  /** Signed transitively through the execution-intent digest. */
  readonly permitResponsibilityOwner: string
  /** Signed transitively through the execution-intent digest. */
  readonly invariantResponsibilityOwner: string
  /** Signed transitively through the execution-intent digest. */
  readonly invariantValidator: string
  readonly permitIssueIndex: number
  readonly predecessorHead: ExecutionWireHead
  readonly proposal: ExecutionWireProposal
  readonly nonceDigest: string
  readonly keyPolicyVersion: string
  readonly revocationEpoch: number
  readonly schema: ExecutionWireArtifactRef
  readonly preState: ExecutionWireArtifactRef
  readonly trajectory: ExecutionWireArtifactRef
  readonly outcomePackage: ExecutionWireArtifactRef
  readonly proposalArtifact: ExecutionWireArtifactRef
  readonly authorization: ExecutionWireArtifactRef
  readonly invariantRequest: ExecutionWireArtifactRef
  readonly commitPlan: SignatureIndependentCommitPlanWire
  readonly commitPlanArtifact: ExecutionWireArtifactRef
}

export const ExecutionIntentWireSchema: Schema.Schema<ExecutionIntentWire> = Schema.Struct({
  contractVersion: Schema.Literal(HSWM_EXECUTION_INTENT_WIRE_V1_CONTRACT_VERSION),
  canonicalization: Schema.Literal(HSWM_EXECUTION_WIRE_CANONICALIZATION),
  status: Schema.Literal(HSWM_EXECUTION_INTENT_WIRE_STATUS),
  executionId: Identifier,
  permitId: Identifier,
  permitContentDigest: Sha256,
  proposalDigest: Sha256,
  expectedSuccessorHead: ExecutionWireHeadSchema,
  authorizer: Identifier,
  permitResponsibilityOwner: Identifier,
  invariantResponsibilityOwner: Identifier,
  invariantValidator: Identifier,
  permitIssueIndex: SafeInteger,
  predecessorHead: ExecutionWireHeadSchema,
  proposal: ExecutionWireProposalSchema,
  nonceDigest: Sha256,
  keyPolicyVersion: Identifier,
  revocationEpoch: SafeInteger,
  schema: ExecutionWireArtifactRefSchema,
  preState: ExecutionWireArtifactRefSchema,
  trajectory: ExecutionWireArtifactRefSchema,
  outcomePackage: ExecutionWireArtifactRefSchema,
  proposalArtifact: ExecutionWireArtifactRefSchema,
  authorization: ExecutionWireArtifactRefSchema,
  invariantRequest: ExecutionWireArtifactRefSchema,
  commitPlan: SignatureIndependentCommitPlanWireSchema,
  commitPlanArtifact: ExecutionWireArtifactRefSchema
})

/** A compatibility fragment retained while complete certificate producers are integrated. */
export interface ExecutionCertificateWirePhaseA {
  readonly contractVersion: typeof HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION
  readonly canonicalization: typeof HSWM_EXECUTION_WIRE_CANONICALIZATION
  readonly status: typeof HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS
  readonly executionId: string
  readonly intent: ExecutionIntentWire
  readonly permitEnvelope: CanonicalPermitEnvelope
  readonly intentArtifact: ExecutionWireArtifactRef
  readonly permitArtifact: ExecutionWireArtifactRef
}

export const ExecutionCertificateWirePhaseASchema: Schema.Schema<ExecutionCertificateWirePhaseA> =
  Schema.Struct({
    contractVersion: Schema.Literal(HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION),
    canonicalization: Schema.Literal(HSWM_EXECUTION_WIRE_CANONICALIZATION),
    status: Schema.Literal(HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS),
    executionId: Identifier,
    intent: ExecutionIntentWireSchema,
    permitEnvelope: CanonicalPermitEnvelopeSchema,
    intentArtifact: ExecutionWireArtifactRefSchema,
    permitArtifact: ExecutionWireArtifactRefSchema
  })

export interface HeadBoundPermit {
  readonly responsibilityOwner: string
  readonly decision: {
    readonly authorizationRef: string
    readonly authorizer: string
    readonly target: ExecutionWireTarget
    readonly traceId: string
    readonly scope: string
    readonly allowed: boolean
    readonly activeAtDecision: boolean
  }
  readonly head: ExecutionWireHead
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly contentDigest: string
}

export const HeadBoundPermitSchema: Schema.Schema<HeadBoundPermit> = Schema.Struct({
  responsibilityOwner: Identifier,
  decision: Schema.Struct({
    authorizationRef: Identifier,
    authorizer: Identifier,
    target: ExecutionWireTargetSchema,
    traceId: Identifier,
    scope: Identifier,
    allowed: Schema.Boolean,
    activeAtDecision: Schema.Boolean
  }),
  head: ExecutionWireHeadSchema,
  expectedRevision: Identifier,
  candidateRevision: Identifier,
  contentDigest: Sha256
})

export interface HeadBoundInvariantCertificate {
  readonly responsibilityOwner: string
  readonly validator: string
  readonly head: ExecutionWireHead
  readonly target: ExecutionWireTarget
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly contentDigest: string
}

export const HeadBoundInvariantCertificateSchema: Schema.Schema<HeadBoundInvariantCertificate> =
  Schema.Struct({
    responsibilityOwner: Identifier,
    validator: Identifier,
    head: ExecutionWireHeadSchema,
    target: ExecutionWireTargetSchema,
    expectedRevision: Identifier,
    candidateRevision: Identifier,
    contentDigest: Sha256
  })

export interface PermitIssueOccurrence {
  readonly executionId: string
  readonly issuer: string
  readonly permitDigest: string
  readonly head: ExecutionWireHead
  readonly target: ExecutionWireTarget
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly authorizationRef: string
  readonly scope: string
  readonly linearizationIndex: number
}

export const PermitIssueOccurrenceSchema: Schema.Schema<PermitIssueOccurrence> =
  Schema.Struct({
    executionId: Identifier,
    issuer: Identifier,
    permitDigest: Sha256,
    head: ExecutionWireHeadSchema,
    target: ExecutionWireTargetSchema,
    expectedRevision: Identifier,
    candidateRevision: Identifier,
    authorizationRef: Identifier,
    scope: Identifier,
    linearizationIndex: SafeInteger
  })

export interface AdmissionCommitWitness {
  readonly predecessorHead: ExecutionWireHead
  readonly successorHead: ExecutionWireHead
  readonly target: ExecutionWireTarget
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly consumedPermitDigest: string
  readonly consumedInvariantDigest: string
}

export const AdmissionCommitWitnessSchema: Schema.Schema<AdmissionCommitWitness> =
  Schema.Struct({
    predecessorHead: ExecutionWireHeadSchema,
    successorHead: ExecutionWireHeadSchema,
    target: ExecutionWireTargetSchema,
    expectedRevision: Identifier,
    candidateRevision: Identifier,
    consumedPermitDigest: Sha256,
    consumedInvariantDigest: Sha256
  })

export interface RuntimeCommitOccurrence {
  readonly executionId: string
  readonly witness: AdmissionCommitWitness
  readonly recoveredSuccessorHead: ExecutionWireHead
  readonly linearizationIndex: number
}

export const RuntimeCommitOccurrenceSchema: Schema.Schema<RuntimeCommitOccurrence> =
  Schema.Struct({
    executionId: Identifier,
    witness: AdmissionCommitWitnessSchema,
    recoveredSuccessorHead: ExecutionWireHeadSchema,
    linearizationIndex: SafeInteger
  })

export interface RecoveredExecutionProjection {
  readonly executionId: string
  readonly predecessorHead: ExecutionWireHead
  readonly successorHead: ExecutionWireHead
  readonly permitIssues: ReadonlyArray<PermitIssueOccurrence>
  readonly successfulCommits: ReadonlyArray<RuntimeCommitOccurrence>
  readonly recoveryIndex: number
}

export const RecoveredExecutionProjectionSchema: Schema.Schema<RecoveredExecutionProjection> =
  Schema.Struct({
    executionId: Identifier,
    predecessorHead: ExecutionWireHeadSchema,
    successorHead: ExecutionWireHeadSchema,
    permitIssues: Schema.Array(PermitIssueOccurrenceSchema),
    successfulCommits: Schema.Array(RuntimeCommitOccurrenceSchema),
    recoveryIndex: SafeInteger
  })

export interface CompleteExecutionCertificateWire {
  readonly contractVersion: typeof HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION
  readonly canonicalization: typeof HSWM_EXECUTION_WIRE_CANONICALIZATION
  readonly status: typeof HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS
  readonly executionId: string
  readonly intent: ExecutionIntentWire
  readonly permitEnvelope: CanonicalPermitEnvelope
  readonly permit: HeadBoundPermit
  readonly invariantCertificate: HeadBoundInvariantCertificate
  readonly issue: PermitIssueOccurrence
  readonly commit: RuntimeCommitOccurrence
  readonly recovery: RecoveredExecutionProjection
  readonly intentArtifact: ExecutionWireArtifactRef
  readonly permitArtifact: ExecutionWireArtifactRef
  /** Invariant input/content bytes; not self-digesting certificate bytes. */
  readonly invariantContentArtifact: ExecutionWireArtifactRef
  readonly commitArtifact: ExecutionWireArtifactRef
  readonly recoveredPreState: ExecutionWireArtifactRef
  readonly recoveredPostState: ExecutionWireArtifactRef
  readonly recoveredCommitCore: SignatureIndependentCommitPlanWire
  readonly recoveredCommitCoreArtifact: ExecutionWireArtifactRef
  readonly recoveryObservation: ExecutionWireArtifactRef
  readonly trajectory: ExecutionWireArtifactRef
}

export const CompleteExecutionCertificateWireSchema: Schema.Schema<CompleteExecutionCertificateWire> =
  Schema.Struct({
    contractVersion: Schema.Literal(HSWM_EXECUTION_CERTIFICATE_WIRE_V1_CONTRACT_VERSION),
    canonicalization: Schema.Literal(HSWM_EXECUTION_WIRE_CANONICALIZATION),
    status: Schema.Literal(HSWM_EXECUTION_CERTIFICATE_WIRE_STATUS),
    executionId: Identifier,
    intent: ExecutionIntentWireSchema,
    permitEnvelope: CanonicalPermitEnvelopeSchema,
    permit: HeadBoundPermitSchema,
    invariantCertificate: HeadBoundInvariantCertificateSchema,
    issue: PermitIssueOccurrenceSchema,
    commit: RuntimeCommitOccurrenceSchema,
    recovery: RecoveredExecutionProjectionSchema,
    intentArtifact: ExecutionWireArtifactRefSchema,
    permitArtifact: ExecutionWireArtifactRefSchema,
    invariantContentArtifact: ExecutionWireArtifactRefSchema,
    commitArtifact: ExecutionWireArtifactRefSchema,
    recoveredPreState: ExecutionWireArtifactRefSchema,
    recoveredPostState: ExecutionWireArtifactRefSchema,
    recoveredCommitCore: SignatureIndependentCommitPlanWireSchema,
    recoveredCommitCoreArtifact: ExecutionWireArtifactRefSchema,
    recoveryObservation: ExecutionWireArtifactRefSchema,
    trajectory: ExecutionWireArtifactRefSchema
  })

export type ExecutionCertificateWireErrorCode =
  | "WIRE_INVALID"
  | "WIRE_NONCANONICAL"
  | "ARTIFACT_MISMATCH"
  | "STRUCTURE_MISMATCH"
  | "PERMIT_REJECTED"

export class ExecutionCertificateWireError extends Data.TaggedError(
  "ExecutionCertificateWireError"
)<{
  readonly code: ExecutionCertificateWireErrorCode
  readonly detail: string
}> {}

const fail = (
  code: ExecutionCertificateWireErrorCode,
  detail: string
): Either.Either<never, ExecutionCertificateWireError> =>
  Either.left(new ExecutionCertificateWireError({ code, detail }))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((value, index) => value === right[index])

const digest = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const sameHead = (left: ExecutionWireHead, right: ExecutionWireHead): boolean =>
  left.lineageId === right.lineageId &&
  left.sequence === right.sequence &&
  left.stateDigest === right.stateDigest &&
  left.recordDigest === right.recordDigest

const sameTarget = (
  left: ExecutionWireTarget,
  right: ExecutionWireTarget
): boolean =>
  left.schemaVersion === right.schemaVersion &&
  left.lineageId === right.lineageId &&
  left.atomUid === right.atomUid

const sameArtifactRef = (
  left: ExecutionWireArtifactRef,
  right: ExecutionWireArtifactRef
): boolean =>
  left.mediaType === right.mediaType &&
  left.byteLength === right.byteLength &&
  left.digest === right.digest

const artifactMatches = (
  artifact: ExecutionWireArtifactRef,
  bytes: Uint8Array
): boolean =>
  artifact.byteLength === bytes.byteLength && artifact.digest === digest(bytes)

const decodeExact = <A>(
  schema: Schema.Schema<A>,
  bytes: Uint8Array
): Either.Either<A, ExecutionCertificateWireError> => {
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed)) return fail("WIRE_INVALID", parsed.left.detail)
  const decoded = Schema.decodeUnknownEither(schema, { onExcessProperty: "error" })(
    parsed.right
  )
  if (Either.isLeft(decoded)) {
    return fail("WIRE_INVALID", "decoded wire does not satisfy the exact schema")
  }
  const canonical = canonicalJsonBytes(decoded.right)
  if (Either.isLeft(canonical) || !sameBytes(bytes, canonical.right)) {
    return fail("WIRE_NONCANONICAL", "wire bytes are not exact hswm-canonical-json/v1")
  }
  return Either.right(decoded.right)
}

const encodeExact = <A>(
  schema: Schema.Schema<A>,
  value: A,
  label: string
): Either.Either<Uint8Array, ExecutionCertificateWireError> => {
  const checked = Schema.decodeUnknownEither(schema, { onExcessProperty: "error" })(value)
  if (Either.isLeft(checked)) return fail("WIRE_INVALID", `${label} violates its exact schema`)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("WIRE_INVALID", bytes.left.detail)
    : Either.right(bytes.right)
}

const valuesMatch = <A>(schema: Schema.Schema<A>, left: A, right: A): boolean => {
  const leftBytes = encodeExact(schema, left, "left value")
  const rightBytes = encodeExact(schema, right, "right value")
  return Either.isRight(leftBytes) &&
    Either.isRight(rightBytes) &&
    sameBytes(leftBytes.right, rightBytes.right)
}

const rawValueMatches = <A>(
  schema: Schema.Schema<A>,
  expected: A,
  bytes: Uint8Array
): boolean => {
  const decoded = decodeExact(schema, bytes)
  return Either.isRight(decoded) && valuesMatch(schema, expected, decoded.right)
}

export const executionIntentWireBytes = (
  intent: ExecutionIntentWire
): Either.Either<Uint8Array, ExecutionCertificateWireError> =>
  encodeExact(ExecutionIntentWireSchema, intent, "execution intent")

export const decodeExecutionIntentWireBytes = (
  bytes: Uint8Array
): Either.Either<ExecutionIntentWire, ExecutionCertificateWireError> =>
  decodeExact(ExecutionIntentWireSchema, bytes)

export const executionCertificateWirePhaseABytes = (
  wire: ExecutionCertificateWirePhaseA
): Either.Either<Uint8Array, ExecutionCertificateWireError> =>
  encodeExact(ExecutionCertificateWirePhaseASchema, wire, "Phase-A certificate")

export const completeExecutionCertificateWireBytes = (
  wire: CompleteExecutionCertificateWire
): Either.Either<Uint8Array, ExecutionCertificateWireError> =>
  encodeExact(CompleteExecutionCertificateWireSchema, wire, "complete certificate")

export type CompleteExecutionCertificateArtifactRole =
  | "certificateBody"
  | "executionIntent"
  | "permitEnvelope"
  | "invariantContent"
  | "commitOccurrence"
  | "recoveredPreState"
  | "recoveredPostState"
  | "recoveredCommitCore"
  | "recoveryObservation"
  | "trajectory"
  | "schema"
  | "intentPreState"
  | "outcomePackage"
  | "proposal"
  | "authorization"
  | "invariantRequest"
  | "commitPlan"

export type CompleteExecutionCertificateArtifacts = Readonly<
  Record<CompleteExecutionCertificateArtifactRole, Uint8Array>
>

export interface CompleteExecutionCertificateVerification {
  readonly wire: CompleteExecutionCertificateWire
  readonly certificateArtifact: ExecutionWireArtifactRef
  readonly status: typeof HSWM_EXECUTION_CERTIFICATE_WIRE_COMPLETE_CHECK_STATUS
}

export interface ExecutionCertificateWirePhaseAVerification {
  readonly wire: ExecutionCertificateWirePhaseA
  readonly certificateArtifact: ExecutionWireArtifactRef
  readonly status: typeof HSWM_EXECUTION_CERTIFICATE_WIRE_PHASE_A_STATUS
}

const expectedPermitBindings = (
  intent: ExecutionIntentWire,
  intentBytes: Uint8Array
): CanonicalPermitExpectedBindings => ({
  permitId: intent.permitId,
  executionId: intent.executionId,
  executionIntentDigest: digest(intentBytes),
  permitDigest: intent.permitContentDigest,
  proposalDigest: intent.proposalDigest,
  transitionInvariantDigest: intent.invariantRequest.digest,
  priorHead: intent.predecessorHead,
  expectedNextHead: intent.expectedSuccessorHead,
  target: intent.proposal.target,
  expectedRevision: intent.proposal.expectedRevision,
  candidateRevision: intent.proposal.candidateRevision,
  authorizationRef: intent.proposal.authorizationRef,
  authorizer: intent.authorizer,
  scope: intent.proposal.scope,
  nonceDigest: intent.nonceDigest,
  keyPolicyVersion: intent.keyPolicyVersion,
  revocationEpoch: intent.revocationEpoch,
  linearizationIndex: intent.permitIssueIndex
})

/** Full raw-artifact and decoded-field checker mirroring Lean `Wire*Conditions`. */
export const verifyCompleteExecutionCertificateWire = (input: {
  readonly certificateBytes: Uint8Array
  readonly certificateArtifact: ExecutionWireArtifactRef
  readonly artifacts: CompleteExecutionCertificateArtifacts
  readonly trustSnapshotBytes: Uint8Array
  readonly verificationTime: string
}): Either.Either<CompleteExecutionCertificateVerification, ExecutionCertificateWireError> => {
  const decoded = decodeExact(CompleteExecutionCertificateWireSchema, input.certificateBytes)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const wire = decoded.right
  const intent = wire.intent
  const artifacts = input.artifacts

  if (
    !sameBytes(artifacts.certificateBody, input.certificateBytes) ||
    !artifactMatches(input.certificateArtifact, input.certificateBytes) ||
    !artifactMatches(wire.intentArtifact, artifacts.executionIntent) ||
    !artifactMatches(wire.permitArtifact, artifacts.permitEnvelope) ||
    !artifactMatches(wire.invariantContentArtifact, artifacts.invariantContent) ||
    !artifactMatches(wire.commitArtifact, artifacts.commitOccurrence) ||
    !artifactMatches(wire.recoveredPreState, artifacts.recoveredPreState) ||
    !artifactMatches(wire.recoveredPostState, artifacts.recoveredPostState) ||
    !artifactMatches(wire.recoveredCommitCoreArtifact, artifacts.recoveredCommitCore) ||
    !artifactMatches(wire.recoveryObservation, artifacts.recoveryObservation) ||
    !artifactMatches(wire.trajectory, artifacts.trajectory) ||
    !artifactMatches(intent.schema, artifacts.schema) ||
    !artifactMatches(intent.preState, artifacts.intentPreState) ||
    !artifactMatches(intent.outcomePackage, artifacts.outcomePackage) ||
    !artifactMatches(intent.proposalArtifact, artifacts.proposal) ||
    !artifactMatches(intent.authorization, artifacts.authorization) ||
    !artifactMatches(intent.invariantRequest, artifacts.invariantRequest) ||
    !artifactMatches(intent.commitPlanArtifact, artifacts.commitPlan)
  ) {
    return fail("ARTIFACT_MISMATCH", "one or more role-scoped raw artifacts fail digest or length binding")
  }

  if (
    !rawValueMatches(ExecutionIntentWireSchema, intent, artifacts.executionIntent) ||
    !rawValueMatches(RuntimeCommitOccurrenceSchema, wire.commit, artifacts.commitOccurrence) ||
    !rawValueMatches(RecoveredExecutionProjectionSchema, wire.recovery, artifacts.recoveryObservation) ||
    !rawValueMatches(
      SignatureIndependentCommitPlanWireSchema,
      intent.commitPlan,
      artifacts.commitPlan
    ) ||
    !rawValueMatches(
      SignatureIndependentCommitPlanWireSchema,
      wire.recoveredCommitCore,
      artifacts.recoveredCommitCore
    ) ||
    !rawValueMatches(ExecutionWireProposalSchema, intent.proposal, artifacts.proposal)
  ) {
    return fail("ARTIFACT_MISMATCH", "a typed raw artifact differs from its decoded certificate field")
  }

  if (
    !sameBytes(artifacts.schema, new TextEncoder().encode(intent.proposal.target.schemaVersion)) ||
    !sameBytes(artifacts.authorization, new TextEncoder().encode(intent.proposal.authorizationRef)) ||
    intent.proposalDigest !== intent.proposalArtifact.digest ||
    wire.invariantContentArtifact.digest !== wire.invariantCertificate.contentDigest ||
    !sameArtifactRef(wire.invariantContentArtifact, intent.invariantRequest) ||
    wire.recoveredPreState.digest !== intent.predecessorHead.stateDigest ||
    wire.recoveredPostState.digest !== wire.commit.recoveredSuccessorHead.stateDigest ||
    !sameArtifactRef(intent.preState, wire.recoveredPreState) ||
    !sameArtifactRef(intent.trajectory, wire.trajectory) ||
    !sameArtifactRef(intent.commitPlanArtifact, wire.recoveredCommitCoreArtifact) ||
    intent.commitPlanArtifact.digest !== intent.expectedSuccessorHead.recordDigest ||
    wire.recoveredCommitCoreArtifact.digest !== wire.commit.recoveredSuccessorHead.recordDigest
  ) {
    return fail("STRUCTURE_MISMATCH", "artifact adapter bindings fail")
  }

  if (
    wire.executionId !== intent.executionId ||
    wire.recovery.executionId !== wire.executionId ||
    !sameHead(wire.recovery.predecessorHead, intent.predecessorHead) ||
    !sameHead(wire.recovery.successorHead, wire.commit.recoveredSuccessorHead) ||
    wire.recovery.permitIssues.length !== 1 ||
    wire.recovery.successfulCommits.length !== 1 ||
    !valuesMatch(PermitIssueOccurrenceSchema, wire.recovery.permitIssues[0]!, wire.issue) ||
    !valuesMatch(RuntimeCommitOccurrenceSchema, wire.recovery.successfulCommits[0]!, wire.commit)
  ) {
    return fail("STRUCTURE_MISMATCH", "header or recovery singleton conditions fail")
  }

  if (
    wire.issue.executionId !== wire.executionId ||
    wire.issue.issuer !== wire.permit.decision.authorizer ||
    wire.issue.permitDigest !== wire.permit.contentDigest ||
    !sameHead(wire.issue.head, wire.permit.head) ||
    !sameTarget(wire.issue.target, wire.permit.decision.target) ||
    wire.issue.expectedRevision !== wire.permit.expectedRevision ||
    wire.issue.candidateRevision !== wire.permit.candidateRevision ||
    wire.issue.authorizationRef !== wire.permit.decision.authorizationRef ||
    wire.issue.scope !== wire.permit.decision.scope
  ) {
    return fail("STRUCTURE_MISMATCH", "Permit issue conditions fail")
  }

  if (
    wire.commit.executionId !== wire.executionId ||
    !sameHead(wire.permit.head, intent.predecessorHead) ||
    !sameHead(wire.invariantCertificate.head, intent.predecessorHead) ||
    !sameHead(wire.commit.witness.predecessorHead, intent.predecessorHead) ||
    !sameHead(wire.commit.witness.successorHead, wire.commit.recoveredSuccessorHead) ||
    !sameHead(wire.commit.recoveredSuccessorHead, intent.expectedSuccessorHead) ||
    wire.commit.recoveredSuccessorHead.lineageId !== intent.predecessorHead.lineageId ||
    wire.commit.recoveredSuccessorHead.sequence !== intent.predecessorHead.sequence + 1 ||
    !sameTarget(wire.commit.witness.target, intent.proposal.target) ||
    wire.commit.witness.expectedRevision !== intent.proposal.expectedRevision ||
    wire.commit.witness.candidateRevision !== intent.proposal.candidateRevision ||
    wire.commit.witness.consumedPermitDigest !== wire.permit.contentDigest ||
    wire.commit.witness.consumedInvariantDigest !== wire.invariantCertificate.contentDigest
  ) {
    return fail("STRUCTURE_MISMATCH", "head or commit conditions fail")
  }

  if (
    intent.permitContentDigest !== wire.permit.contentDigest ||
    intent.invariantRequest.digest !== wire.invariantCertificate.contentDigest ||
    wire.permit.decision.authorizer !== intent.authorizer ||
    wire.issue.linearizationIndex !== intent.permitIssueIndex ||
    wire.permit.responsibilityOwner !== intent.permitResponsibilityOwner ||
    wire.invariantCertificate.responsibilityOwner !== intent.invariantResponsibilityOwner ||
    wire.invariantCertificate.validator !== intent.invariantValidator ||
    !sameTarget(wire.permit.decision.target, intent.proposal.target) ||
    wire.permit.decision.traceId !== intent.proposal.traceId ||
    wire.permit.decision.authorizationRef !== intent.proposal.authorizationRef ||
    wire.permit.decision.scope !== intent.proposal.scope ||
    !wire.permit.decision.allowed ||
    !wire.permit.decision.activeAtDecision ||
    wire.permit.expectedRevision !== intent.proposal.expectedRevision ||
    wire.permit.candidateRevision !== intent.proposal.candidateRevision ||
    !sameTarget(wire.invariantCertificate.target, intent.proposal.target) ||
    wire.invariantCertificate.expectedRevision !== intent.proposal.expectedRevision ||
    wire.invariantCertificate.candidateRevision !== intent.proposal.candidateRevision
  ) {
    return fail("STRUCTURE_MISMATCH", "Permit or invariant conditions fail")
  }

  const plan = intent.commitPlan
  if (
    !valuesMatch(SignatureIndependentCommitPlanWireSchema, plan, wire.recoveredCommitCore) ||
    plan.executionId !== intent.executionId ||
    !sameHead(plan.predecessorHead, intent.predecessorHead) ||
    plan.successor.lineageId !== intent.expectedSuccessorHead.lineageId ||
    plan.successor.sequence !== intent.expectedSuccessorHead.sequence ||
    plan.successor.stateDigest !== intent.expectedSuccessorHead.stateDigest ||
    !sameTarget(plan.target, intent.proposal.target) ||
    plan.expectedRevision !== intent.proposal.expectedRevision ||
    plan.candidateRevision !== intent.proposal.candidateRevision ||
    plan.permitContentDigest !== intent.permitContentDigest ||
    plan.invariantContentDigest !== intent.invariantRequest.digest ||
    plan.commitLinearizationIndex !== wire.commit.linearizationIndex
  ) {
    return fail("STRUCTURE_MISMATCH", "signature-independent commit-plan conditions fail")
  }

  if (!(
    wire.issue.linearizationIndex < wire.commit.linearizationIndex &&
    wire.commit.linearizationIndex < wire.recovery.recoveryIndex
  )) {
    return fail("STRUCTURE_MISMATCH", "issue, commit, and recovery chronology fails")
  }

  const permit = verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
    artifacts.permitEnvelope,
    expectedPermitBindings(intent, artifacts.executionIntent),
    input.trustSnapshotBytes,
    input.verificationTime
  )
  if (Either.isLeft(permit)) return fail("PERMIT_REJECTED", permit.left.code)
  if (!valuesMatch(CanonicalPermitEnvelopeSchema, wire.permitEnvelope, permit.right.envelope)) {
    return fail("PERMIT_REJECTED", "certificate envelope differs from verified raw bytes")
  }

  return Either.right(Object.freeze({
    wire,
    certificateArtifact: Object.freeze({ ...input.certificateArtifact }),
    status: HSWM_EXECUTION_CERTIFICATE_WIRE_COMPLETE_CHECK_STATUS
  }))
}

/** Checks only the compatibility fragment and cannot return an admission verdict. */
export const verifyExecutionCertificateWirePhaseA = (input: {
  readonly certificateBytes: Uint8Array
  readonly intentBytes: Uint8Array
  readonly permitEnvelopeBytes: Uint8Array
  readonly certificateArtifact: ExecutionWireArtifactRef
  readonly trustSnapshotBytes: Uint8Array
  readonly verificationTime: string
}): Either.Either<ExecutionCertificateWirePhaseAVerification, ExecutionCertificateWireError> => {
  const wire = decodeExact(ExecutionCertificateWirePhaseASchema, input.certificateBytes)
  if (Either.isLeft(wire)) return Either.left(wire.left)
  const intent = decodeExecutionIntentWireBytes(input.intentBytes)
  if (Either.isLeft(intent)) return Either.left(intent.left)
  if (
    !valuesMatch(ExecutionIntentWireSchema, wire.right.intent, intent.right) ||
    wire.right.executionId !== intent.right.executionId ||
    !artifactMatches(input.certificateArtifact, input.certificateBytes) ||
    !artifactMatches(wire.right.intentArtifact, input.intentBytes) ||
    !artifactMatches(wire.right.permitArtifact, input.permitEnvelopeBytes)
  ) {
    return fail("STRUCTURE_MISMATCH", "external bytes or execution identity do not match Phase-A fields")
  }
  const plan = intent.right.commitPlan
  if (
    !sameHead(plan.predecessorHead, intent.right.predecessorHead) ||
    plan.successor.lineageId !== intent.right.expectedSuccessorHead.lineageId ||
    plan.successor.sequence !== intent.right.expectedSuccessorHead.sequence ||
    plan.successor.stateDigest !== intent.right.expectedSuccessorHead.stateDigest ||
    !sameTarget(plan.target, intent.right.proposal.target) ||
    plan.executionId !== intent.right.executionId ||
    plan.expectedRevision !== intent.right.proposal.expectedRevision ||
    plan.candidateRevision !== intent.right.proposal.candidateRevision ||
    plan.permitContentDigest !== intent.right.permitContentDigest ||
    plan.invariantContentDigest !== intent.right.invariantRequest.digest
  ) {
    return fail("STRUCTURE_MISMATCH", "signature-independent commit plan is not bound to intent")
  }
  const permit = verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
    input.permitEnvelopeBytes,
    expectedPermitBindings(intent.right, input.intentBytes),
    input.trustSnapshotBytes,
    input.verificationTime
  )
  if (Either.isLeft(permit)) return fail("PERMIT_REJECTED", permit.left.code)
  if (!valuesMatch(CanonicalPermitEnvelopeSchema, wire.right.permitEnvelope, permit.right.envelope)) {
    return fail("STRUCTURE_MISMATCH", "certificate envelope differs from verified raw envelope")
  }
  return Either.right(Object.freeze({
    wire: wire.right,
    certificateArtifact: Object.freeze({ ...input.certificateArtifact }),
    status: HSWM_EXECUTION_CERTIFICATE_WIRE_PHASE_A_STATUS
  }))
}
