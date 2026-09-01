import HSWMCanonicalPermitEnvelope

/-!
# HSWM structural execution-certificate wire boundary

This module freezes a decoded-field contract for one future execution-intent
and complete execution-certificate codec. It deliberately separates:

* a syntactically cycle-free decoded-field body layout whose final certificate
  descriptor stays outside the body it names;
* a pure, caller-relative structural checker over exact decoded fields and
  artifact-adapter results; and
* semantic facts that field equality cannot manufacture.

It does not parse JSON, implement canonical encoding or SHA-256, prove
TypeScript/Effect refinement, authenticate a real issuer, or establish that a
runtime/storage occurrence happened. Outcome truth, independent causal
credit, real-LLM improvement, state decoding, transition-invariant semantics,
durable atomicity and `AtomicLearnAdmission` remain unavailable from wire
acceptance alone.

The existing canonical Permit envelope's signing document is used directly.
It is deliberately not projected to the distinct end-to-end
`PermitAuthenticationEvidence` signing syntax in this module.
-/

namespace HSWM.CanonicalLearning.ExecutionCertificateWire

open AtomicAdmission
open OutcomeJudgment
open EndToEndRuntimeRefinement
open CanonicalPermitEnvelope

def executionIntentContractVersion : String :=
  "hswm-execution-intent-wire/v1"

def executionCertificateContractVersion : String :=
  "hswm-execution-certificate-wire/v1"

def executionWireCanonicalization : String :=
  "hswm-canonical-json/v1"

def signatureIndependentCommitPlanContractVersion : String :=
  "hswm-signature-independent-commit-plan/v1"

def executionIntentStatus : String :=
  "PRE_EXECUTION_INTENT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"

def executionCertificateStatus : String :=
  "STRUCTURALLY_BOUND_EXECUTION_CERTIFICATE_NOT_RUNTIME_OCCURRENCE_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING"

def signatureIndependentCommitPlanStatus : String :=
  "SIGNATURE_INDEPENDENT_COMMIT_PLAN_NOT_PERMIT_ENVELOPE_NOT_CERTIFICATE"

/-- A content-addressed artifact named by decoded certificate fields. -/
structure ArtifactRef where
  mediaType : String
  byteLength : Nat
  digest : EvidenceDigest
deriving Repr, DecidableEq

/-!
The typed commit core deliberately has no Permit envelope, signature, intent
digest, final certificate digest, or successor record digest field.  In
particular, including `successorHead.recordDigest` here while also requiring
the digest of these bytes to equal that record digest would create a SHA-256
fixed-point obligation.  The record-independent successor projection prevents
that cycle.  The exact core bytes may therefore be planned before Permit
signing and compared with a recovered core afterward.  Any journal wrapper
carrying a signature remains outside the core named here.
-/
structure RecordIndependentSuccessorHeadWire where
  lineageId : String
  sequence : Nat
  stateDigest : StateDigest
deriving Repr, DecidableEq

def RecordIndependentSuccessorHeadWire.ofHead
    (head : HeadSnapshot) : RecordIndependentSuccessorHeadWire :=
  { lineageId := head.lineageId
    sequence := head.sequence
    stateDigest := head.stateDigest }

/-- Changing the eventual record digest cannot change the planned core. -/
@[simp] theorem successorProjectionIgnoresRecordDigest
    (head : HeadSnapshot)
    (recordDigest : RecordDigest) :
    RecordIndependentSuccessorHeadWire.ofHead
        { head with recordDigest := recordDigest } =
      RecordIndependentSuccessorHeadWire.ofHead head := by
  rfl

structure SignatureIndependentCommitPlanWire where
  contractVersion : String
  status : String
  executionId : RuntimeExecutionId
  predecessorHead : HeadSnapshot
  successor : RecordIndependentSuccessorHeadWire
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  permitContentDigest : EvidenceDigest
  invariantContentDigest : EvidenceDigest
  commitLinearizationIndex : Nat
deriving Repr, DecidableEq

/-!
The intent has no `intentDigest` or final certificate digest field. Both are
computed outside the body. `commitPlan` is a typed signature-independent core,
and `commitPlanArtifact` names its bytes before Permit signing.
-/
structure ExecutionIntentWire where
  contractVersion : String
  canonicalization : String
  status : String
  executionId : RuntimeExecutionId
  permitId : PermitId
  permitContentDigest : EvidenceDigest
  proposalDigest : EvidenceDigest
  expectedSuccessorHead : HeadSnapshot
  authorizer : Principal
  permitResponsibilityOwner : Principal
  invariantResponsibilityOwner : Principal
  invariantValidator : Principal
  permitIssueIndex : Nat
  predecessorHead : HeadSnapshot
  proposal : RevisionProposal
  nonceDigest : NonceDigest
  keyPolicyVersion : String
  revocationEpoch : Nat
  schema : ArtifactRef
  preState : ArtifactRef
  trajectory : ArtifactRef
  outcomePackage : ArtifactRef
  proposalArtifact : ArtifactRef
  authorization : ArtifactRef
  invariantRequest : ArtifactRef
  commitPlan : SignatureIndependentCommitPlanWire
  commitPlanArtifact : ArtifactRef
deriving Repr, DecidableEq

/-- Digest of canonical pre-execution intent bytes, outside the intent body. -/
abbrev IntentDigestOf := ExecutionIntentWire → EvidenceDigest

/-- Digest of the exact revision-proposal bytes. -/
abbrev ProposalDigestOf := RevisionProposal → EvidenceDigest

/--
A decoded recovery projection. Its lists are inputs to the checker; `traceOf`
does not manufacture singleton lists. Raw journal/history replay remains an
external adapter obligation.
-/
structure RecoveredExecutionProjection where
  executionId : RuntimeExecutionId
  predecessorHead : HeadSnapshot
  successorHead : HeadSnapshot
  permitIssues : List PermitIssueOccurrence
  successfulCommits : List RuntimeCommitOccurrence
  recoveryIndex : Nat
deriving Repr, DecidableEq

/--
Decoded certificate body. The final certificate descriptor is intentionally
not a field, so the body cannot directly contain the digest of itself.
-/
structure CompleteExecutionCertificateWire where
  contractVersion : String
  canonicalization : String
  status : String
  executionId : RuntimeExecutionId
  intent : ExecutionIntentWire
  permitEnvelope : CanonicalPermitEnvelope
  permit : HeadBoundPermit
  invariantCertificate : HeadBoundInvariantCertificate
  issue : PermitIssueOccurrence
  commit : RuntimeCommitOccurrence
  recovery : RecoveredExecutionProjection
  intentArtifact : ArtifactRef
  permitArtifact : ArtifactRef
  /-- Invariant input/content bytes, not self-digesting certificate bytes. -/
  invariantContentArtifact : ArtifactRef
  commitArtifact : ArtifactRef
  recoveredPreState : ArtifactRef
  recoveredPostState : ArtifactRef
  recoveredCommitCore : SignatureIndependentCommitPlanWire
  recoveredCommitCoreArtifact : ArtifactRef
  recoveryObservation : ArtifactRef
  trajectory : ArtifactRef
deriving Repr, DecidableEq

/-- Digest of final serialized certificate-body bytes, outside that body. -/
abbrev CertificateDigestOf := CompleteExecutionCertificateWire → EvidenceDigest

/--
All byte-to-digest adapters remain parameters. Their inclusion fixes which
typed body or commitment each descriptor must name without pretending Lean
already implements the codecs or cryptographic functions.
-/
structure WireDigestAdapters where
  intentDigestOf : IntentDigestOf
  certificateDigestOf : CertificateDigestOf
  proposalDigestOf : ProposalDigestOf
  permitEnvelopeDigestOf : CanonicalPermitEnvelope → EvidenceDigest
  commitOccurrenceDigestOf : RuntimeCommitOccurrence → EvidenceDigest
  recoveryProjectionDigestOf : RecoveredExecutionProjection → EvidenceDigest
  commitPlanDigestOf : SignatureIndependentCommitPlanWire → EvidenceDigest
  schemaDigestOf : String → EvidenceDigest
  authorizationDigestOf : AuthorizationRef → EvidenceDigest
  stateDigestAsEvidence : StateDigest → EvidenceDigest
  recordDigestAsEvidence : RecordDigest → EvidenceDigest
  trajectoryDigestOf : SealedTrajectory → EvidenceDigest
  outcomePackageDigestOf : OutcomeEvidencePackage → EvidenceDigest

inductive ArtifactRole where
  | certificateBody
  | executionIntent
  | permitEnvelope
  | invariantContent
  | commitOccurrence
  | recoveredPreState
  | recoveredPostState
  | recoveredCommitCore
  | recoveryObservation
  | trajectory
  | schema
  | intentPreState
  | outcomePackage
  | proposal
  | authorization
  | invariantRequest
  | commitPlan
deriving Repr, DecidableEq

/-!
An artifact verifier is explicitly caller-relative. Calling it on an exact
role and descriptor scopes each result; it still does not prove the verifier's
implementation sound or establish provenance, truth, or occurrence.
-/
abbrev ArtifactVerifier := ArtifactRole → ArtifactRef → Bool

def ExternalArtifactsAccepted
    (artifactVerifier : ArtifactVerifier)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) : Prop :=
  artifactVerifier .certificateBody certificateArtifact = true ∧
  artifactVerifier .executionIntent wire.intentArtifact = true ∧
  artifactVerifier .permitEnvelope wire.permitArtifact = true ∧
  artifactVerifier .invariantContent wire.invariantContentArtifact = true ∧
  artifactVerifier .commitOccurrence wire.commitArtifact = true ∧
  artifactVerifier .recoveredPreState wire.recoveredPreState = true ∧
  artifactVerifier .recoveredPostState wire.recoveredPostState = true ∧
  artifactVerifier .recoveredCommitCore wire.recoveredCommitCoreArtifact = true ∧
  artifactVerifier .recoveryObservation wire.recoveryObservation = true ∧
  artifactVerifier .trajectory wire.trajectory = true ∧
  artifactVerifier .schema wire.intent.schema = true ∧
  artifactVerifier .intentPreState wire.intent.preState = true ∧
  artifactVerifier .outcomePackage wire.intent.outcomePackage = true ∧
  artifactVerifier .proposal wire.intent.proposalArtifact = true ∧
  artifactVerifier .authorization wire.intent.authorization = true ∧
  artifactVerifier .invariantRequest wire.intent.invariantRequest = true ∧
  artifactVerifier .commitPlan wire.intent.commitPlanArtifact = true

instance externalArtifactsAcceptedDecidable
    (artifactVerifier : ArtifactVerifier)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) :
    Decidable (ExternalArtifactsAccepted artifactVerifier certificateArtifact wire) := by
  unfold ExternalArtifactsAccepted
  infer_instance

def externalArtifactsAcceptedBool
    (artifactVerifier : ArtifactVerifier)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) : Bool :=
  decide (ExternalArtifactsAccepted artifactVerifier certificateArtifact wire)

theorem externalArtifactsAcceptedProjectsRequiredChecks
    (accepted : ExternalArtifactsAccepted artifactVerifier certificateArtifact wire) :
    artifactVerifier .certificateBody certificateArtifact = true ∧
    artifactVerifier .recoveredPostState wire.recoveredPostState = true := by
  rcases accepted with ⟨certificateBody, _, _, _, _, _, recoveredPostState, _, _, _,
    _, _, _, _, _, _, _⟩
  exact ⟨certificateBody, recoveredPostState⟩

def CompleteExecutionCertificateWire.traceOf
    (adapters : WireDigestAdapters)
    (wire : CompleteExecutionCertificateWire) : RuntimeExecutionTrace :=
  { executionId := wire.executionId
    executionIntentDigest := adapters.intentDigestOf wire.intent
    certificateDigest := adapters.certificateDigestOf wire
    permitIssues := wire.recovery.permitIssues
    successfulCommits := wire.recovery.successfulCommits
    recoveryIndex := wire.recovery.recoveryIndex }

/-!
The expected Permit context is derived from the intent. Exact equality from
the intent to the certificate's Permit, invariant and recovery projection is a
separate structural condition below.
-/
def CompleteExecutionCertificateWire.expectedEnvelopeBindings
    (adapters : WireDigestAdapters)
    (wire : CompleteExecutionCertificateWire) : PermitExpectedBindings :=
  { permitId := wire.intent.permitId
    executionId := wire.intent.executionId
    executionIntentDigest := adapters.intentDigestOf wire.intent
    permitDigest := wire.intent.permitContentDigest
    proposalDigest := wire.intent.proposalDigest
    transitionInvariantDigest := wire.intent.invariantRequest.digest
    priorHead := wire.intent.predecessorHead
    expectedNextHead := wire.intent.expectedSuccessorHead
    target := wire.intent.proposal.target
    expectedRevision := wire.intent.proposal.expectedRevision
    candidateRevision := wire.intent.proposal.candidateRevision
    authorizationRef := wire.intent.proposal.authorizationRef
    authorizer := wire.intent.authorizer
    scope := wire.intent.proposal.scope
    nonceDigest := wire.intent.nonceDigest
    keyPolicyVersion := wire.intent.keyPolicyVersion
    revocationEpoch := wire.intent.revocationEpoch
    linearizationIndex := wire.intent.permitIssueIndex }

/-!
Every field below is decidable decoded-field structure. Digest-adapter
equalities name exact artifacts but do not assert those adapters implement
SHA-256 or canonical JSON.
-/
def WireHeaderConditions (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.contractVersion = executionCertificateContractVersion ∧
  wire.canonicalization = executionWireCanonicalization ∧
  wire.status = executionCertificateStatus ∧
  wire.intent.contractVersion = executionIntentContractVersion ∧
  wire.intent.canonicalization = executionWireCanonicalization ∧
  wire.intent.status = executionIntentStatus ∧
  wire.executionId = wire.intent.executionId

def WireRecoveryConditions (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.recovery.executionId = wire.executionId ∧
  wire.recovery.predecessorHead = wire.intent.predecessorHead ∧
  wire.recovery.successorHead = wire.commit.recoveredSuccessorHead ∧
  wire.recovery.permitIssues = [wire.issue] ∧
  wire.recovery.successfulCommits = [wire.commit]

def WireIssueConditions (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.issue.executionId = wire.executionId ∧
  wire.issue.issuer = wire.permit.decision.authorizer ∧
  wire.issue.permitDigest = wire.permit.contentDigest ∧
  wire.issue.head = wire.permit.head ∧
  wire.issue.target = wire.permit.decision.target ∧
  wire.issue.expectedRevision = wire.permit.expectedRevision ∧
  wire.issue.candidateRevision = wire.permit.candidateRevision ∧
  wire.issue.authorizationRef = wire.permit.decision.authorizationRef ∧
  wire.issue.scope = wire.permit.decision.scope

def WireHeadCommitConditions (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.commit.executionId = wire.executionId ∧
  wire.permit.head = wire.intent.predecessorHead ∧
  wire.invariantCertificate.head = wire.intent.predecessorHead ∧
  wire.commit.witness.predecessorHead = wire.intent.predecessorHead ∧
  wire.commit.witness.successorHead = wire.commit.recoveredSuccessorHead ∧
  wire.commit.recoveredSuccessorHead = wire.intent.expectedSuccessorHead ∧
  wire.commit.recoveredSuccessorHead.lineageId =
    wire.intent.predecessorHead.lineageId ∧
  wire.commit.recoveredSuccessorHead.sequence =
    wire.intent.predecessorHead.sequence + 1 ∧
  wire.commit.witness.target = wire.intent.proposal.target ∧
  wire.commit.witness.expectedRevision = wire.intent.proposal.expectedRevision ∧
  wire.commit.witness.candidateRevision = wire.intent.proposal.candidateRevision ∧
  wire.commit.witness.consumedPermitDigest = wire.permit.contentDigest ∧
  wire.commit.witness.consumedInvariantDigest =
    wire.invariantCertificate.contentDigest

def WirePermitInvariantConditions
    (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.intent.permitContentDigest = wire.permit.contentDigest ∧
  wire.intent.invariantRequest.digest = wire.invariantCertificate.contentDigest ∧
  wire.permit.decision.authorizer = wire.intent.authorizer ∧
  wire.issue.linearizationIndex = wire.intent.permitIssueIndex ∧
  wire.permit.responsibilityOwner = wire.intent.permitResponsibilityOwner ∧
  wire.invariantCertificate.responsibilityOwner =
    wire.intent.invariantResponsibilityOwner ∧
  wire.invariantCertificate.validator = wire.intent.invariantValidator ∧
  wire.permit.decision.target = wire.intent.proposal.target ∧
  wire.permit.decision.traceId = wire.intent.proposal.traceId ∧
  wire.permit.decision.authorizationRef = wire.intent.proposal.authorizationRef ∧
  wire.permit.decision.scope = wire.intent.proposal.scope ∧
  wire.permit.decision.allowed = true ∧
  wire.permit.decision.activeAtDecision = true ∧
  wire.permit.expectedRevision = wire.intent.proposal.expectedRevision ∧
  wire.permit.candidateRevision = wire.intent.proposal.candidateRevision ∧
  wire.invariantCertificate.target = wire.intent.proposal.target ∧
  wire.invariantCertificate.expectedRevision =
    wire.intent.proposal.expectedRevision ∧
  wire.invariantCertificate.candidateRevision =
    wire.intent.proposal.candidateRevision

def WireCommitPlanConditions (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.intent.commitPlan.contractVersion =
    signatureIndependentCommitPlanContractVersion ∧
  wire.intent.commitPlan.status = signatureIndependentCommitPlanStatus ∧
  wire.intent.commitPlan.executionId = wire.intent.executionId ∧
  wire.intent.commitPlan.predecessorHead = wire.intent.predecessorHead ∧
  wire.intent.commitPlan.successor.lineageId =
    wire.intent.expectedSuccessorHead.lineageId ∧
  wire.intent.commitPlan.successor.sequence =
    wire.intent.expectedSuccessorHead.sequence ∧
  wire.intent.commitPlan.successor.stateDigest =
    wire.intent.expectedSuccessorHead.stateDigest ∧
  wire.intent.commitPlan.target = wire.intent.proposal.target ∧
  wire.intent.commitPlan.expectedRevision = wire.intent.proposal.expectedRevision ∧
  wire.intent.commitPlan.candidateRevision = wire.intent.proposal.candidateRevision ∧
  wire.intent.commitPlan.permitContentDigest = wire.intent.permitContentDigest ∧
  wire.intent.commitPlan.invariantContentDigest =
    wire.intent.invariantRequest.digest ∧
  wire.intent.commitPlan.commitLinearizationIndex = wire.commit.linearizationIndex ∧
  wire.recoveredCommitCore = wire.intent.commitPlan

def WireArtifactBindingConditions
    (adapters : WireDigestAdapters)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) : Prop :=
  certificateArtifact.digest = adapters.certificateDigestOf wire ∧
  wire.intentArtifact.digest = adapters.intentDigestOf wire.intent ∧
  wire.intent.proposalArtifact.digest =
    adapters.proposalDigestOf wire.intent.proposal ∧
  wire.intent.proposalDigest = adapters.proposalDigestOf wire.intent.proposal ∧
  wire.permitArtifact.digest =
    adapters.permitEnvelopeDigestOf wire.permitEnvelope ∧
  wire.invariantContentArtifact.digest =
    wire.invariantCertificate.contentDigest ∧
  wire.invariantContentArtifact = wire.intent.invariantRequest ∧
  wire.commitArtifact.digest = adapters.commitOccurrenceDigestOf wire.commit ∧
  wire.recoveryObservation.digest =
    adapters.recoveryProjectionDigestOf wire.recovery ∧
  wire.intent.schema.digest =
    adapters.schemaDigestOf wire.intent.proposal.target.schemaVersion ∧
  wire.intent.authorization.digest =
    adapters.authorizationDigestOf wire.intent.proposal.authorizationRef ∧
  wire.recoveredPreState.digest =
    adapters.stateDigestAsEvidence wire.intent.predecessorHead.stateDigest ∧
  wire.recoveredPostState.digest =
    adapters.stateDigestAsEvidence wire.commit.recoveredSuccessorHead.stateDigest ∧
  wire.intent.preState = wire.recoveredPreState ∧
  wire.trajectory = wire.intent.trajectory ∧
  wire.intent.commitPlanArtifact.digest =
    adapters.commitPlanDigestOf wire.intent.commitPlan ∧
  wire.recoveredCommitCoreArtifact.digest =
    adapters.commitPlanDigestOf wire.recoveredCommitCore ∧
  wire.recoveredCommitCoreArtifact = wire.intent.commitPlanArtifact ∧
  wire.intent.commitPlanArtifact.digest =
    adapters.recordDigestAsEvidence wire.intent.expectedSuccessorHead.recordDigest ∧
  wire.recoveredCommitCoreArtifact.digest =
    adapters.recordDigestAsEvidence wire.commit.recoveredSuccessorHead.recordDigest

def WireChronologyConditions (wire : CompleteExecutionCertificateWire) : Prop :=
  wire.issue.linearizationIndex < wire.commit.linearizationIndex ∧
  wire.commit.linearizationIndex < wire.recovery.recoveryIndex

def WireStructuralConditions
    (adapters : WireDigestAdapters)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) : Prop :=
  WireHeaderConditions wire ∧
  WireRecoveryConditions wire ∧
  WireIssueConditions wire ∧
  WireHeadCommitConditions wire ∧
  WirePermitInvariantConditions wire ∧
  WireCommitPlanConditions wire ∧
  WireArtifactBindingConditions adapters certificateArtifact wire ∧
  WireChronologyConditions wire

instance wireHeaderConditionsDecidable (wire : CompleteExecutionCertificateWire) :
    Decidable (WireHeaderConditions wire) := by
  unfold WireHeaderConditions
  infer_instance

instance wireRecoveryConditionsDecidable (wire : CompleteExecutionCertificateWire) :
    Decidable (WireRecoveryConditions wire) := by
  unfold WireRecoveryConditions
  infer_instance

instance wireIssueConditionsDecidable (wire : CompleteExecutionCertificateWire) :
    Decidable (WireIssueConditions wire) := by
  unfold WireIssueConditions
  infer_instance

instance wireHeadCommitConditionsDecidable
    (wire : CompleteExecutionCertificateWire) :
    Decidable (WireHeadCommitConditions wire) := by
  unfold WireHeadCommitConditions
  infer_instance

instance wirePermitInvariantConditionsDecidable
    (wire : CompleteExecutionCertificateWire) :
    Decidable (WirePermitInvariantConditions wire) := by
  unfold WirePermitInvariantConditions
  infer_instance

instance wireCommitPlanConditionsDecidable
    (wire : CompleteExecutionCertificateWire) :
    Decidable (WireCommitPlanConditions wire) := by
  unfold WireCommitPlanConditions
  infer_instance

instance wireArtifactBindingConditionsDecidable
    (adapters : WireDigestAdapters)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) :
    Decidable (WireArtifactBindingConditions adapters certificateArtifact wire) := by
  unfold WireArtifactBindingConditions
  infer_instance

instance wireChronologyConditionsDecidable
    (wire : CompleteExecutionCertificateWire) :
    Decidable (WireChronologyConditions wire) := by
  unfold WireChronologyConditions
  infer_instance

instance wireStructuralConditionsDecidable
    (adapters : WireDigestAdapters)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) :
    Decidable (WireStructuralConditions adapters certificateArtifact wire) := by
  unfold WireStructuralConditions
  infer_instance

def wireStructuralBool
    (adapters : WireDigestAdapters)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) : Bool :=
  decide (WireStructuralConditions adapters certificateArtifact wire)

/-!
Pure decoded-field checker. The three adapters are explicit inputs: artifact
verification, Permit-envelope checking and digest projection. Their soundness
with respect to real bytes, keys, clocks or storage is not assumed here.
-/
def completeExecutionCertificateAccepted
    (adapters : WireDigestAdapters)
    (verify : EnvelopeSignatureVerifier)
    (key : PublicKey)
    (expectedKeyId : String)
    (envelopeChecks : ExternalPermitChecks)
    (artifactVerifier : ArtifactVerifier)
    (certificateArtifact : ArtifactRef)
    (wire : CompleteExecutionCertificateWire) : Bool :=
  externalArtifactsAcceptedBool artifactVerifier certificateArtifact wire &&
  canonicalPermitEnvelopeAccepted verify key expectedKeyId
    (wire.expectedEnvelopeBindings adapters) envelopeChecks wire.permitEnvelope &&
  wireStructuralBool adapters certificateArtifact wire

theorem acceptedWireProjectsStructuralConditions
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    ExternalArtifactsAccepted artifactVerifier certificateArtifact wire ∧
    canonicalPermitEnvelopeAccepted verify key expectedKeyId
      (wire.expectedEnvelopeBindings adapters) envelopeChecks
        wire.permitEnvelope = true ∧
    WireStructuralConditions adapters certificateArtifact wire := by
  simp only [completeExecutionCertificateAccepted, Bool.and_eq_true,
    externalArtifactsAcceptedBool, wireStructuralBool, decide_eq_true_eq] at accepted
  rcases accepted with ⟨⟨artifacts, envelope⟩, structural⟩
  exact ⟨artifacts, envelope, structural⟩

theorem acceptedWireProjectsEnvelopeContext
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    wire.permitEnvelope.document.claims.executionId = wire.intent.executionId ∧
    wire.permitEnvelope.document.claims.executionIntentDigest =
      adapters.intentDigestOf wire.intent ∧
    wire.permitEnvelope.document.claims.permitDigest =
      wire.intent.permitContentDigest ∧
    wire.permitEnvelope.document.claims.proposalDigest =
      wire.intent.proposalDigest ∧
    wire.permitEnvelope.document.claims.transitionInvariantDigest =
      wire.intent.invariantRequest.digest ∧
    wire.permitEnvelope.document.claims.priorHead =
      wire.intent.predecessorHead ∧
    wire.permitEnvelope.document.claims.expectedNextHead =
      wire.intent.expectedSuccessorHead ∧
    wire.permitEnvelope.document.claims.nonceDigest = wire.intent.nonceDigest := by
  have envelopeAccepted := (acceptedWireProjectsStructuralConditions accepted).2.1
  have bindings :=
    (acceptedEnvelopeProjectsEveryCheckedBinding envelopeAccepted).2.2.2.1
  change wire.permitEnvelope.document.claims.expectedBindings =
    wire.expectedEnvelopeBindings adapters at bindings
  have executionId := congrArg PermitExpectedBindings.executionId bindings
  have intentDigest :=
    congrArg PermitExpectedBindings.executionIntentDigest bindings
  have permitDigest := congrArg PermitExpectedBindings.permitDigest bindings
  have proposalDigest := congrArg PermitExpectedBindings.proposalDigest bindings
  have invariantDigest :=
    congrArg PermitExpectedBindings.transitionInvariantDigest bindings
  have priorHead := congrArg PermitExpectedBindings.priorHead bindings
  have expectedNextHead :=
    congrArg PermitExpectedBindings.expectedNextHead bindings
  have nonceDigest := congrArg PermitExpectedBindings.nonceDigest bindings
  change wire.permitEnvelope.document.claims.executionId =
    wire.intent.executionId at executionId
  change wire.permitEnvelope.document.claims.executionIntentDigest =
    adapters.intentDigestOf wire.intent at intentDigest
  change wire.permitEnvelope.document.claims.permitDigest =
    wire.intent.permitContentDigest at permitDigest
  change wire.permitEnvelope.document.claims.proposalDigest =
    wire.intent.proposalDigest at proposalDigest
  change wire.permitEnvelope.document.claims.transitionInvariantDigest =
    wire.intent.invariantRequest.digest at invariantDigest
  change wire.permitEnvelope.document.claims.priorHead =
    wire.intent.predecessorHead at priorHead
  change wire.permitEnvelope.document.claims.expectedNextHead =
    wire.intent.expectedSuccessorHead at expectedNextHead
  change wire.permitEnvelope.document.claims.nonceDigest =
    wire.intent.nonceDigest at nonceDigest
  exact ⟨executionId, intentDigest, permitDigest, proposalDigest, invariantDigest,
    priorHead, expectedNextHead, nonceDigest⟩

theorem acceptedWireProjectsLinearSuccessor
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    wire.commit.recoveredSuccessorHead.lineageId =
      wire.intent.predecessorHead.lineageId ∧
    wire.commit.recoveredSuccessorHead.sequence =
      wire.intent.predecessorHead.sequence + 1 := by
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, headCommit, _, _, _, _⟩
  rcases headCommit with ⟨_, _, _, _, _, _, lineage, sequence, _, _, _, _, _⟩
  exact ⟨lineage, sequence⟩

/-- Owner and validator identities are committed inside the signed intent. -/
theorem acceptedWireBindsResponsibilityOwners
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    wire.permit.responsibilityOwner = wire.intent.permitResponsibilityOwner ∧
    wire.invariantCertificate.responsibilityOwner =
      wire.intent.invariantResponsibilityOwner ∧
    wire.invariantCertificate.validator = wire.intent.invariantValidator := by
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, _, permitInvariant, _, _, _⟩
  rcases permitInvariant with ⟨_, _, _, _, permitOwner, invariantOwner,
    invariantValidator, _⟩
  exact ⟨permitOwner, invariantOwner, invariantValidator⟩

theorem acceptedWireBindsExternalCertificateDigest
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    artifactVerifier .certificateBody certificateArtifact = true ∧
    certificateArtifact.digest = adapters.certificateDigestOf wire := by
  have projected := acceptedWireProjectsStructuralConditions accepted
  have requiredChecks := externalArtifactsAcceptedProjectsRequiredChecks projected.1
  rcases projected.2.2 with ⟨_, _, _, _, _, _, artifactBindings, _⟩
  exact ⟨requiredChecks.1, artifactBindings.1⟩

/-!
This relation is only a declared decoded-field binding. Its name and shape do
not assert that `certificateDigestOf` implements SHA-256 over canonical bytes.
-/
def DeclaredCertificateDigestBinding
    (adapters : WireDigestAdapters)
    (wire : CompleteExecutionCertificateWire) :
    RuntimeExecutionTrace → EvidenceDigest → Prop :=
  fun trace digest =>
    trace = wire.traceOf adapters ∧
    digest = adapters.certificateDigestOf wire

/-!
Builds the exact claimed structural evidence from checker projections. Its
trace lists come from the accepted recovery projection. This remains a
declared trace, not proof that the journal or storage occurrence was real.
-/
def buildClaimedConcreteExecutionEvidence
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    ClaimedConcreteExecutionEvidence wire.permit wire.commit.witness
      wire.commit.recoveredSuccessorHead := by
  have projected := acceptedWireProjectsStructuralConditions accepted
  have artifacts := projected.1
  have structural := projected.2.2
  have requiredChecks := externalArtifactsAcceptedProjectsRequiredChecks artifacts
  rcases structural with ⟨_, recovery, issueFacts, headCommit, _, _, _, chronology⟩
  rcases recovery with ⟨_, _, _, recoveredPermitIssues, recoveredCommits⟩
  rcases issueFacts with ⟨issueExecution, issueIssuer, issueDigest, issueHead,
    issueTarget, issueExpected, issueCandidate, issueAuthorization, issueScope⟩
  rcases headCommit with ⟨commitExecution, _, _, _, _, _, _, _, _, _, _, _, _⟩
  rcases chronology with ⟨issueBeforeCommit, commitBeforeRecovery⟩
  refine
    { trace := wire.traceOf adapters
      issue := wire.issue
      commit := wire.commit
      certificateDigestSemantics := DeclaredCertificateDigestBinding adapters wire
      certificateDigestBindsTrace := ⟨rfl, rfl⟩
      canonicalCertificateBytesAccepted :=
        artifactVerifier .certificateBody certificateArtifact
      recoveredPostStateAccepted :=
        artifactVerifier .recoveredPostState wire.recoveredPostState
      canonicalCertificateBytesWereAccepted := requiredChecks.1
      recoveredPostStateWasAccepted := requiredChecks.2
      issuePresent := by
        change wire.issue ∈ wire.recovery.permitIssues
        rw [recoveredPermitIssues]
        simp
      issueExact := ⟨issueExecution, issueIssuer, issueDigest, issueHead,
        issueTarget, issueExpected, issueCandidate, issueAuthorization, issueScope⟩
      issueUniqueForPermit := by
        intro other present _exact
        change other ∈ wire.recovery.permitIssues at present
        rw [recoveredPermitIssues] at present
        simpa using present
      issueBeforeCommit := issueBeforeCommit
      commitBeforeRecovery := commitBeforeRecovery
      successfulCommitLog := by
        change wire.recovery.successfulCommits = [wire.commit]
        exact recoveredCommits
      commitExact := ⟨commitExecution, rfl, rfl⟩ }

theorem acceptedWireYieldsClaimedConcreteExecutionEvidence
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    Nonempty (ClaimedConcreteExecutionEvidence wire.permit wire.commit.witness
      wire.commit.recoveredSuccessorHead) :=
  ⟨buildClaimedConcreteExecutionEvidence accepted⟩

theorem acceptedWireYieldsExactClaimedIssueCommitAndSingletonLog
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) :
    ∃ evidence : ClaimedConcreteExecutionEvidence wire.permit wire.commit.witness
        wire.commit.recoveredSuccessorHead,
      ExactPermitIssue evidence.trace evidence.issue wire.permit ∧
      ExactRuntimeCommit evidence.trace evidence.commit wire.commit.witness
        wire.commit.recoveredSuccessorHead ∧
      evidence.trace.successfulCommits.length = 1 := by
  let evidence := buildClaimedConcreteExecutionEvidence accepted
  exact ⟨evidence, evidence.issueExact, evidence.commitExact,
    claimedEvidenceHasOneDeclaredSuccessfulCommit evidence⟩

/-!
Semantic facts that certificate field equality cannot reconstruct. Even the
runtime-state, trajectory and outcome-package digest functions remain explicit
and are bound to the signed intent's descriptors here rather than silently
identified with real bytes.
-/
structure RuntimeSemanticSupplement
    (RuntimeState : Type)
    (abstractState : RuntimeState → CanonicalState)
    (digest : CanonicalState → StateDigest)
    (transitionInvariant :
      CanonicalState → RevisionProposal → CanonicalState → Prop)
    (adapters : WireDigestAdapters)
    (wire : CompleteExecutionCertificateWire)
    (runtimeBefore runtimeAfter : RuntimeState)
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true) where
  state : CanonicalState
  next : CanonicalState
  trajectory : SealedTrajectory
  package : OutcomeEvidencePackage
  runtimeStep : RuntimeState → RuntimeExecutionTrace → RuntimeState → Prop
  executionOccurred : runtimeStep runtimeBefore
    (buildClaimedConcreteExecutionEvidence accepted).trace runtimeAfter
  beforeMapsExactly : abstractState runtimeBefore = state
  afterMapsExactly : abstractState runtimeAfter = next
  runtimeStateDigestOf : RuntimeState → EvidenceDigest
  runtimeBeforeArtifactMatches :
    wire.recoveredPreState.digest = runtimeStateDigestOf runtimeBefore
  runtimeAfterArtifactMatches :
    wire.recoveredPostState.digest = runtimeStateDigestOf runtimeAfter
  trajectoryArtifactMatches :
    wire.intent.trajectory.digest = adapters.trajectoryDigestOf trajectory
  outcomePackageArtifactMatches :
    wire.intent.outcomePackage.digest = adapters.outcomePackageDigestOf package
  admissionConditions : AtomicAdmissionConditions digest transitionInvariant
    state trajectory package wire.intent.proposal wire.permit
    wire.invariantCertificate wire.commit.witness wire.intent.predecessorHead
    next wire.commit.recoveredSuccessorHead

/-!
Only checker acceptance plus the explicit semantic supplement constructs the
existing claimed admission certificate. `executionOccurred` is a supplied
fact for a supplied relation; this is not a TS/Effect occurrence theorem.
-/
def buildClaimedRuntimeAdmissionCertificate
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true)
    (supplement : RuntimeSemanticSupplement RuntimeState abstractState digest
      transitionInvariant adapters wire runtimeBefore runtimeAfter accepted) :
    ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant supplement.state supplement.trajectory supplement.package
      wire.intent.proposal wire.permit wire.invariantCertificate wire.commit.witness
      wire.intent.predecessorHead supplement.next wire.commit.recoveredSuccessorHead
      runtimeBefore runtimeAfter :=
  { execution := buildClaimedConcreteExecutionEvidence accepted
    concreteRuntimeStep := supplement.runtimeStep
    executionOccurred := supplement.executionOccurred
    beforeMapsExactly := supplement.beforeMapsExactly
    afterMapsExactly := supplement.afterMapsExactly
    admissionConditions := supplement.admissionConditions }

theorem acceptedWireAndSupplementYieldClaimedRuntimeAdmissionCertificate
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true)
    (supplement : RuntimeSemanticSupplement RuntimeState abstractState digest
      transitionInvariant adapters wire runtimeBefore runtimeAfter accepted) :
    Nonempty (ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant supplement.state supplement.trajectory supplement.package
      wire.intent.proposal wire.permit wire.invariantCertificate wire.commit.witness
      wire.intent.predecessorHead supplement.next wire.commit.recoveredSuccessorHead
      runtimeBefore runtimeAfter) :=
  ⟨buildClaimedRuntimeAdmissionCertificate accepted supplement⟩

theorem acceptedWireAndSupplementYieldConditionalRefinement
    (accepted : completeExecutionCertificateAccepted adapters verify key
      expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true)
    (supplement : RuntimeSemanticSupplement RuntimeState abstractState digest
      transitionInvariant adapters wire runtimeBefore runtimeAfter accepted) :
    ConditionalRuntimeStepRefinesAtomicAdmission RuntimeState supplement.runtimeStep
      (buildClaimedConcreteExecutionEvidence accepted).trace
      abstractState digest transitionInvariant
      supplement.state supplement.trajectory supplement.package wire.intent.proposal
      wire.permit wire.invariantCertificate wire.commit.witness
      wire.intent.predecessorHead supplement.next wire.commit.recoveredSuccessorHead
      runtimeBefore runtimeAfter := by
  exact ⟨supplement.executionOccurred, supplement.beforeMapsExactly,
    supplement.afterMapsExactly, .admit supplement.admissionConditions⟩

theorem changedIntentDigestRejected
    (changed : wire.permitEnvelope.document.claims.executionIntentDigest ≠
      adapters.intentDigestOf wire.intent) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  exact changed (acceptedWireProjectsEnvelopeContext accepted).2.1

theorem changedExternalCertificateDigestRejected
    (changed : certificateArtifact.digest ≠ adapters.certificateDigestOf wire) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, _, _, _, artifactBindings, _⟩
  exact changed artifactBindings.1

theorem changedProposalDigestRejected
    (changed : wire.intent.proposalDigest ≠
      adapters.proposalDigestOf wire.intent.proposal) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, _, _, _, artifactBindings, _⟩
  exact changed artifactBindings.2.2.2.1

theorem changedConsumedPermitDigestRejected
    (changed : wire.commit.witness.consumedPermitDigest ≠
      wire.permit.contentDigest) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, headCommit, _, _, _, _⟩
  rcases headCommit with ⟨_, _, _, _, _, _, _, _, _, _, _, consumedPermit, _⟩
  exact changed consumedPermit

theorem changedConsumedInvariantDigestRejected
    (changed : wire.commit.witness.consumedInvariantDigest ≠
      wire.invariantCertificate.contentDigest) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, headCommit, _, _, _, _⟩
  rcases headCommit with ⟨_, _, _, _, _, _, _, _, _, _, _, _, consumedInvariant⟩
  exact changed consumedInvariant

theorem changedRecoveredCommitCoreRejected
    (changed : wire.recoveredCommitCore ≠ wire.intent.commitPlan) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, _, _, commitPlan, _, _⟩
  rcases commitPlan with ⟨_, _, _, _, _, _, _, _, _, _, _, _, _, recoveredCore⟩
  exact changed recoveredCore

theorem alteredRecoveredCommitLogRejected
    (changed : wire.recovery.successfulCommits ≠ [wire.commit]) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, recovery, _, _, _, _, _, _⟩
  exact changed recovery.2.2.2.2

theorem invalidSuccessorRejected
    (invalid : ¬ (
      wire.commit.recoveredSuccessorHead.lineageId =
        wire.intent.predecessorHead.lineageId ∧
      wire.commit.recoveredSuccessorHead.sequence =
        wire.intent.predecessorHead.sequence + 1)) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  exact invalid (acceptedWireProjectsLinearSuccessor accepted)

theorem invalidIssueCommitRecoveryChronologyRejected
    (invalid : ¬ (wire.issue.linearizationIndex < wire.commit.linearizationIndex ∧
      wire.commit.linearizationIndex < wire.recovery.recoveryIndex)) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have structural := (acceptedWireProjectsStructuralConditions accepted).2.2
  rcases structural with ⟨_, _, _, _, _, _, _, chronology⟩
  exact invalid chronology

theorem rejectedCertificateArtifactCannotBeAccepted
    (rejected : artifactVerifier .certificateBody certificateArtifact = false) :
    completeExecutionCertificateAccepted adapters verify key expectedKeyId
      envelopeChecks artifactVerifier certificateArtifact wire ≠ true := by
  intro accepted
  have external := (acceptedWireProjectsStructuralConditions accepted).1
  have wasAccepted := (externalArtifactsAcceptedProjectsRequiredChecks external).1
  rw [rejected] at wasAccepted
  contradiction

end HSWM.CanonicalLearning.ExecutionCertificateWire
