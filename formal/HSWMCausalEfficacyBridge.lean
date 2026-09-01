import HSWMExecutionCertificateWire
import HSWMDnrd5ExactSignGate

/-!
# HSWM typed causal-efficacy occurrence bridge

This module connects the existing execution-certificate boundary to the
DNRD-5 four-arm protocol.  It proves exact structural bindings for the
certificate-carrying admissions, nine typed calls, four opaque forks,
chronology, W0 behavioral restoration, analysis rows and exact sign gates.

Real adapter soundness, real randomness, byte/digest meaning, trusted time,
nonce consumption, outcome truth, isolation, rollback occurrence, LCB
arithmetic and causal identification remain explicit semantic premises.
-/

namespace HSWM.CanonicalLearning.CausalEfficacyBridge

open AtomicAdmission
open OutcomeJudgment
open EndToEndRuntimeRefinement
open CanonicalPermitEnvelope
open ExecutionCertificateWire
open HSWM.DNRD5.EfficacyBoundary
open HSWM.DNRD5.ExactSignGate

structure CloneId where
  value : String
deriving Repr, DecidableEq

structure CallId where
  value : String
deriving Repr, DecidableEq

structure ProtocolEventId where
  value : String
deriving Repr, DecidableEq

/-! ## Exact execution-certificate admission binding -/

/--
An admitted arm carries the already checked execution-certificate wire and the
semantic supplement used to construct the existing claimed runtime admission
certificate. Candidate, Permit, transition and runtime identities are derived
from these fields; a caller cannot supply floating aliases for them.
-/
structure RuntimeCertificateAdmissionBinding (RuntimeState : Type) where
  adapters : WireDigestAdapters
  verify : EnvelopeSignatureVerifier
  signedBy : EnvelopeSignatureMeaning
  signatureVerifierSound : EnvelopeSignatureVerifierSound verify signedBy
  key : PublicKey
  expectedKeyId : String
  envelopeChecks : ExternalPermitChecks
  artifactVerifier : ArtifactVerifier
  certificateArtifact : ArtifactRef
  wire : CompleteExecutionCertificateWire
  accepted : completeExecutionCertificateAccepted adapters verify key
    expectedKeyId envelopeChecks artifactVerifier certificateArtifact wire = true
  abstractState : RuntimeState → CanonicalState
  digest : CanonicalState → StateDigest
  transitionInvariant :
    CanonicalState → RevisionProposal → CanonicalState → Prop
  runtimeBefore : RuntimeState
  runtimeAfter : RuntimeState
  supplement : RuntimeSemanticSupplement RuntimeState abstractState digest
    transitionInvariant adapters wire runtimeBefore runtimeAfter accepted

def RuntimeCertificateAdmissionBinding.claimedCertificate
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) :
    ClaimedRuntimeAdmissionCertificate RuntimeState binding.abstractState
      binding.digest binding.transitionInvariant binding.supplement.state
      binding.supplement.trajectory binding.supplement.package
      binding.wire.intent.proposal binding.wire.permit
      binding.wire.invariantCertificate binding.wire.commit.witness
      binding.wire.intent.predecessorHead binding.supplement.next
      binding.wire.commit.recoveredSuccessorHead binding.runtimeBefore
      binding.runtimeAfter :=
  buildClaimedRuntimeAdmissionCertificate binding.accepted binding.supplement

def RuntimeCertificateAdmissionBinding.proposal
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) : RevisionProposal :=
  binding.wire.intent.proposal

def RuntimeCertificateAdmissionBinding.candidateRevision
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) : RevisionId :=
  binding.proposal.candidateRevision

def RuntimeCertificateAdmissionBinding.certificateDigest
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) : EvidenceDigest :=
  binding.certificateArtifact.digest

def RuntimeCertificateAdmissionBinding.executionId
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) : RuntimeExecutionId :=
  binding.wire.executionId

theorem runtimeCertificateBindingYieldsAtomicAdmission
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) :
    AtomicLearnAdmission binding.digest binding.transitionInvariant
      binding.supplement.state binding.supplement.trajectory
      binding.supplement.package binding.proposal binding.wire.permit
      binding.wire.invariantCertificate binding.wire.commit.witness
      binding.wire.intent.predecessorHead binding.supplement.next
      binding.wire.commit.recoveredSuccessorHead :=
  claimedCertificateConditionsYieldAtomicAdmission binding.claimedCertificate

theorem runtimeCertificateBindingYieldsConditionalRefinement
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) :
    ConditionalRuntimeStepRefinesAtomicAdmission RuntimeState
      binding.supplement.runtimeStep
      (buildClaimedConcreteExecutionEvidence binding.accepted).trace
      binding.abstractState binding.digest binding.transitionInvariant
      binding.supplement.state binding.supplement.trajectory
      binding.supplement.package binding.proposal binding.wire.permit
      binding.wire.invariantCertificate binding.wire.commit.witness
      binding.wire.intent.predecessorHead binding.supplement.next
      binding.wire.commit.recoveredSuccessorHead binding.runtimeBefore
      binding.runtimeAfter :=
  acceptedWireAndSupplementYieldConditionalRefinement
    binding.accepted binding.supplement

theorem runtimeCertificateBindingRequiresExactProposalAndConsumption
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) :
    binding.wire.permit.candidateRevision = binding.candidateRevision ∧
    binding.wire.invariantCertificate.candidateRevision =
      binding.candidateRevision ∧
    binding.wire.commit.witness.candidateRevision = binding.candidateRevision ∧
    binding.wire.commit.witness.consumedPermitDigest =
      binding.wire.permit.contentDigest ∧
    binding.wire.commit.witness.consumedInvariantDigest =
      binding.wire.invariantCertificate.contentDigest := by
  have admitted := runtimeCertificateBindingYieldsAtomicAdmission binding
  have exactProposal := atomicAdmissionRequiresExactProposalBinding admitted
  have consumed := atomicAdmissionRequiresExactCertificateConsumption admitted
  exact ⟨exactProposal.2.1, exactProposal.2.2.2.2.1,
    exactProposal.2.2.2.2.2.2.2, consumed.1, consumed.2⟩

theorem runtimeCertificateBindingRequiresOutcomeLearningAndInvariant
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) :
    LearnFromOutcomeEvidence
      (fun pre candidate =>
        binding.transitionInvariant pre candidate binding.supplement.next)
      binding.supplement.state binding.supplement.trajectory
      binding.supplement.package binding.proposal binding.wire.permit.decision
      binding.supplement.next ∧
    binding.transitionInvariant binding.supplement.state binding.proposal
      binding.supplement.next := by
  have admitted := runtimeCertificateBindingYieldsAtomicAdmission binding
  exact ⟨atomicAdmissionRequiresOutcomeLearning admitted,
    atomicAdmissionRequiresTransitionInvariant admitted⟩

theorem runtimeCertificateBindingProjectsSignedEnvelopeAndSuppliedNonceTimeChecks
    (binding : RuntimeCertificateAdmissionBinding RuntimeState) :
    binding.signedBy binding.key binding.wire.permitEnvelope.document
      binding.wire.permitEnvelope.signature ∧
    binding.wire.permitEnvelope.document.claims.nonceDigest =
      binding.wire.intent.nonceDigest ∧
    binding.envelopeChecks.keyActiveAtVerification = true ∧
    binding.envelopeChecks.permitTimeActive = true := by
  have projected := acceptedWireProjectsStructuralConditions binding.accepted
  have envelopeAccepted := projected.2.1
  rcases acceptedEnvelopeAndSoundVerifierYieldAuthenticatedDocument
      envelopeAccepted binding.signatureVerifierSound with
    ⟨_, _, signed, _, _, _, _, keyActive, timeActive⟩
  rcases acceptedWireProjectsEnvelopeContext binding.accepted with
    ⟨_, _, _, _, _, _, _, nonce⟩
  exact ⟨signed, nonce, keyActive, timeActive⟩

/-! ## Typed four-arm protocol -/

structure BehavioralSnapshot where
  rootDigest : EvidenceDigest
  compiledReadsetDigest : EvidenceDigest
  projectionPolicyDigest : EvidenceDigest
  compilerDigest : EvidenceDigest
deriving Repr, DecidableEq

inductive FeedbackSourceRole where
  | genuineOutcome
  | outcomeIndependentPlacebo
  | creditEscrow
deriving Repr, DecidableEq

def feedbackSourceFor : Arm → FeedbackSourceRole
  | .active => .genuineOutcome
  | .outcomeIndependentSham => .outcomeIndependentPlacebo
  | .delayedNoCredit => .creditEscrow
  | .exactW0Rollback => .genuineOutcome

/-- The arm/source index is structural; real input-byte meaning is external. -/
structure TypedFeedbackAssignment
    (source : FeedbackSourceRole) (clone : CloneId) where
  sourceArtifactDigest : EvidenceDigest
  inputProjectionDigest : EvidenceDigest
  proposalRequestDigest : EvidenceDigest
  assignmentReceiptDigest : EvidenceDigest
deriving Repr, DecidableEq

/-- Four opaque forks plus declared future-randomness context and execution orders. -/
structure ForkAllocation where
  cloneFor : Arm → CloneId
  futureCommitmentDigest : EvidenceDigest
  futureRevealDigest : EvidenceDigest
  derivationDigest : EvidenceDigest
  proposalOrder : List Arm
  probeOrder : List Arm
  clonesNodup : (armUniverse.map cloneFor).Nodup
  proposalOrderPermutes : proposalOrder.Perm armUniverse
  probeOrderPermutes : probeOrder.Perm armUniverse

inductive GenerationRole where
  | trajectory
  | proposal (clone : CloneId)
  | probe (clone : CloneId)
deriving Repr, DecidableEq

structure GenerationCall (role : GenerationRole) where
  callId : CallId
  sequence : Nat
  requestDigest : EvidenceDigest
  responseDigest : EvidenceDigest
  rngReceiptDigest : EvidenceDigest
deriving Repr, DecidableEq

def namedGenerationCallIds
    (allocation : ForkAllocation)
    (trajectory : GenerationCall .trajectory)
    (proposal : (arm : Arm) →
      GenerationCall (.proposal (allocation.cloneFor arm)))
    (probe : (arm : Arm) →
      GenerationCall (.probe (allocation.cloneFor arm))) : List CallId :=
  [trajectory.callId] ++
    armUniverse.map (fun arm => (proposal arm).callId) ++
    armUniverse.map (fun arm => (probe arm).callId)

def namedGenerationSequences
    (allocation : ForkAllocation)
    (trajectory : GenerationCall .trajectory)
    (proposal : (arm : Arm) →
      GenerationCall (.proposal (allocation.cloneFor arm)))
    (probe : (arm : Arm) →
      GenerationCall (.probe (allocation.cloneFor arm))) : List Nat :=
  [trajectory.sequence] ++
    armUniverse.map (fun arm => (proposal arm).sequence) ++
    armUniverse.map (fun arm => (probe arm).sequence)

/-- Exactly one typed trajectory, proposal per clone, and probe per clone. -/
structure GenerationLedger (allocation : ForkAllocation) where
  trajectory : GenerationCall .trajectory
  proposal : (arm : Arm) →
    GenerationCall (.proposal (allocation.cloneFor arm))
  probe : (arm : Arm) →
    GenerationCall (.probe (allocation.cloneFor arm))
  observedCallIds : List CallId
  observedCallIdsExact :
    observedCallIds = namedGenerationCallIds allocation trajectory proposal probe
  callIdsUnique : observedCallIds.Nodup
  sequencesUnique :
    (namedGenerationSequences allocation trajectory proposal probe).Nodup
  proposalOrderStrict : List.Pairwise (fun left right => left < right)
    (allocation.proposalOrder.map fun arm => (proposal arm).sequence)
  probeOrderStrict : List.Pairwise (fun left right => left < right)
    (allocation.probeOrder.map fun arm => (probe arm).sequence)

inductive ProtocolEventRole where
  | futureRandomnessCommitment
  | w0Seal
  | forkSeal (clone : CloneId)
  | futureRandomnessReveal
  | assignment
  | trajectorySealed
  | outcomeSealed
  | outcomeEscrowed
  | proposalSealed (clone : CloneId)
  | dispositionSealed (clone : CloneId)
  | probeSealed (clone : CloneId)
  | delayedAuditRelease
  | blockClose
deriving Repr, DecidableEq

structure ProtocolEvent (role : ProtocolEventRole) where
  eventId : ProtocolEventId
  sequence : Nat
  receiptDigest : EvidenceDigest
deriving Repr, DecidableEq

/-- Typed chronology; chronology of real external events remains a premise. -/
structure ProtocolTimeline (allocation : ForkAllocation) where
  futureCommitment : ProtocolEvent .futureRandomnessCommitment
  w0Seal : ProtocolEvent .w0Seal
  forkSeal : (arm : Arm) →
    ProtocolEvent (.forkSeal (allocation.cloneFor arm))
  futureReveal : ProtocolEvent .futureRandomnessReveal
  assignment : ProtocolEvent .assignment
  trajectorySealed : ProtocolEvent .trajectorySealed
  outcomeSealed : ProtocolEvent .outcomeSealed
  outcomeEscrowed : ProtocolEvent .outcomeEscrowed
  proposalSealed : (arm : Arm) →
    ProtocolEvent (.proposalSealed (allocation.cloneFor arm))
  dispositionSealed : (arm : Arm) →
    ProtocolEvent (.dispositionSealed (allocation.cloneFor arm))
  probeSealed : (arm : Arm) →
    ProtocolEvent (.probeSealed (allocation.cloneFor arm))
  delayedAuditRelease : ProtocolEvent .delayedAuditRelease
  blockClose : ProtocolEvent .blockClose
  commitmentBeforeW0 : futureCommitment.sequence < w0Seal.sequence
  w0BeforeEveryFork : ∀ arm, w0Seal.sequence < (forkSeal arm).sequence
  everyForkBeforeReveal : ∀ arm,
    (forkSeal arm).sequence < futureReveal.sequence
  revealBeforeAssignment : futureReveal.sequence < assignment.sequence
  assignmentBeforeTrajectory : assignment.sequence < trajectorySealed.sequence
  trajectoryBeforeOutcome : trajectorySealed.sequence < outcomeSealed.sequence
  outcomeBeforeEscrow : outcomeSealed.sequence < outcomeEscrowed.sequence
  escrowBeforeEveryProposal : ∀ arm,
    outcomeEscrowed.sequence < (proposalSealed arm).sequence
  proposalBeforeDisposition : ∀ arm,
    (proposalSealed arm).sequence < (dispositionSealed arm).sequence
  everyDispositionBeforeEveryProbe : ∀ dispositionArm probeArm,
    (dispositionSealed dispositionArm).sequence <
      (probeSealed probeArm).sequence
  everyProbeBeforeDelayedRelease : ∀ arm,
    (probeSealed arm).sequence < delayedAuditRelease.sequence
  delayedReleaseBeforeClose : delayedAuditRelease.sequence < blockClose.sequence

def protocolEventIds
    (timeline : ProtocolTimeline allocation) : List ProtocolEventId :=
  [timeline.futureCommitment.eventId, timeline.w0Seal.eventId] ++
    armUniverse.map (fun arm => (timeline.forkSeal arm).eventId) ++
    [timeline.futureReveal.eventId, timeline.assignment.eventId,
      timeline.trajectorySealed.eventId, timeline.outcomeSealed.eventId,
      timeline.outcomeEscrowed.eventId] ++
    armUniverse.map (fun arm => (timeline.proposalSealed arm).eventId) ++
    armUniverse.map (fun arm => (timeline.dispositionSealed arm).eventId) ++
    armUniverse.map (fun arm => (timeline.probeSealed arm).eventId) ++
    [timeline.delayedAuditRelease.eventId, timeline.blockClose.eventId]

def protocolEventSequences
    (timeline : ProtocolTimeline allocation) : List Nat :=
  [timeline.futureCommitment.sequence, timeline.w0Seal.sequence] ++
    armUniverse.map (fun arm => (timeline.forkSeal arm).sequence) ++
    [timeline.futureReveal.sequence, timeline.assignment.sequence,
      timeline.trajectorySealed.sequence, timeline.outcomeSealed.sequence,
      timeline.outcomeEscrowed.sequence] ++
    armUniverse.map (fun arm => (timeline.proposalSealed arm).sequence) ++
    armUniverse.map (fun arm => (timeline.dispositionSealed arm).sequence) ++
    armUniverse.map (fun arm => (timeline.probeSealed arm).sequence) ++
    [timeline.delayedAuditRelease.sequence, timeline.blockClose.sequence]

structure SealedProbeArmMeasurement
    (RuntimeState : Type)
    (snapshotOf : RuntimeState → BehavioralSnapshot)
    (clone : CloneId) where
  runtimeState : RuntimeState
  behaviorRevision : RevisionId
  snapshot : BehavioralSnapshot
  snapshotMatchesRuntime : snapshot = snapshotOf runtimeState
  modelConfigDigest : EvidenceDigest
  sealedProbeSuiteDigest : EvidenceDigest
  responseTraceDigest : EvidenceDigest
  sealedScoreReceiptDigest : EvidenceDigest
  score : Bool

inductive StateChangingEffectRole where
  | activeAdmission
  | shamAdmission
  | rollbackStagingAdmission
  | rollbackRestore
deriving Repr, DecidableEq

def StateChangingEffectRole.arm : StateChangingEffectRole → Arm
  | .activeAdmission => .active
  | .shamAdmission => .outcomeIndependentSham
  | .rollbackStagingAdmission => .exactW0Rollback
  | .rollbackRestore => .exactW0Rollback

def stateChangingEffectUniverse : List StateChangingEffectRole :=
  [.activeAdmission, .shamAdmission, .rollbackStagingAdmission,
    .rollbackRestore]

theorem delayedArmHasNoStateChangingEffectRole :
    Arm.delayedNoCredit ∉ stateChangingEffectUniverse.map
      StateChangingEffectRole.arm := by
  decide

/-!
The fixed fields are intentionally asymmetric: DELAYED has a quarantined
proposal and no admission slot; ROLLBACK has a staging admission plus a restore
receipt and is measured only after exact W0 behavioral restoration.
-/
structure FourArmBlock
    (RuntimeState : Type)
    (snapshotOf : RuntimeState → BehavioralSnapshot) where
  blockId : BlockId
  allocation : ForkAllocation
  calls : GenerationLedger allocation
  timeline : ProtocolTimeline allocation
  timelineEventIdsUnique : (protocolEventIds timeline).Nodup
  timelineSequencesUnique : (protocolEventSequences timeline).Nodup
  allProtocolSequencesUnique :
    (namedGenerationSequences allocation calls.trajectory calls.proposal
      calls.probe ++ protocolEventSequences timeline).Nodup
  w0Runtime : RuntimeState
  w0Revision : RevisionId
  w0Snapshot : BehavioralSnapshot
  w0SnapshotMatchesRuntime : w0Snapshot = snapshotOf w0Runtime
  forkRuntime : Arm → RuntimeState
  allForksStartAtExactW0 : ∀ arm, snapshotOf (forkRuntime arm) = w0Snapshot
  sharedTrajectory : SealedTrajectory
  genuineOutcomePackage : OutcomeEvidencePackage
  feedbackAssignment : (arm : Arm) →
    TypedFeedbackAssignment (feedbackSourceFor arm) (allocation.cloneFor arm)
  activeAdmission : RuntimeCertificateAdmissionBinding RuntimeState
  shamAdmission : RuntimeCertificateAdmissionBinding RuntimeState
  rollbackStagingAdmission : RuntimeCertificateAdmissionBinding RuntimeState
  admissionExecutionIdsUnique :
    [activeAdmission.executionId, shamAdmission.executionId,
      rollbackStagingAdmission.executionId].Nodup
  activeStartsFromAssignedFork :
    activeAdmission.runtimeBefore = forkRuntime .active
  shamStartsFromAssignedFork :
    shamAdmission.runtimeBefore = forkRuntime .outcomeIndependentSham
  rollbackStartsFromAssignedFork :
    rollbackStagingAdmission.runtimeBefore = forkRuntime .exactW0Rollback
  activeUsesSharedTrajectory :
    activeAdmission.supplement.trajectory = sharedTrajectory
  shamUsesSharedTrajectory :
    shamAdmission.supplement.trajectory = sharedTrajectory
  rollbackUsesSharedTrajectory :
    rollbackStagingAdmission.supplement.trajectory = sharedTrajectory
  activeUsesGenuineOutcome :
    activeAdmission.supplement.package = genuineOutcomePackage
  rollbackUsesGenuineOutcome :
    rollbackStagingAdmission.supplement.package = genuineOutcomePackage
  delayedProposal : RevisionProposal
  delayedProposalDigestOf : ProposalDigestOf
  delayedProposalArtifactDigest : EvidenceDigest
  delayedProposalArtifactMatches :
    delayedProposalArtifactDigest = delayedProposalDigestOf delayedProposal
  delayedQuarantineReceiptDigest : EvidenceDigest
  rollbackRestoreReceiptDigest : EvidenceDigest
  trajectoryCallBindsSharedSeal :
    calls.trajectory.responseDigest =
      activeAdmission.wire.intent.trajectory.digest
  allAdmissionsBindSharedTrajectoryArtifact :
    shamAdmission.wire.intent.trajectory.digest =
      activeAdmission.wire.intent.trajectory.digest ∧
    rollbackStagingAdmission.wire.intent.trajectory.digest =
      activeAdmission.wire.intent.trajectory.digest
  activeFeedbackBindsGenuineOutcomeArtifact :
    (feedbackAssignment .active).sourceArtifactDigest =
      activeAdmission.wire.intent.outcomePackage.digest
  shamFeedbackBindsPlaceboArtifact :
    (feedbackAssignment .outcomeIndependentSham).sourceArtifactDigest =
      shamAdmission.wire.intent.outcomePackage.digest
  delayedFeedbackBindsEscrowArtifact :
    (feedbackAssignment .delayedNoCredit).sourceArtifactDigest =
      timeline.outcomeEscrowed.receiptDigest
  rollbackFeedbackBindsGenuineOutcomeArtifact :
    (feedbackAssignment .exactW0Rollback).sourceArtifactDigest =
      rollbackStagingAdmission.wire.intent.outcomePackage.digest
  everyProposalRequestBindsAssignedFeedback : ∀ arm,
    (calls.proposal arm).requestDigest =
      (feedbackAssignment arm).proposalRequestDigest
  activeProposalCallBindsAdmission :
    (calls.proposal .active).responseDigest =
      activeAdmission.wire.intent.proposalDigest
  shamProposalCallBindsAdmission :
    (calls.proposal .outcomeIndependentSham).responseDigest =
      shamAdmission.wire.intent.proposalDigest
  delayedProposalCallBindsQuarantine :
    (calls.proposal .delayedNoCredit).responseDigest =
      delayedProposalArtifactDigest
  rollbackProposalCallBindsStagingAdmission :
    (calls.proposal .exactW0Rollback).responseDigest =
      rollbackStagingAdmission.wire.intent.proposalDigest
  activeDispositionBindsCertificate :
    (timeline.dispositionSealed .active).receiptDigest =
      activeAdmission.certificateDigest
  shamDispositionBindsCertificate :
    (timeline.dispositionSealed .outcomeIndependentSham).receiptDigest =
      shamAdmission.certificateDigest
  delayedDispositionBindsQuarantine :
    (timeline.dispositionSealed .delayedNoCredit).receiptDigest =
      delayedQuarantineReceiptDigest
  rollbackDispositionBindsRestore :
    (timeline.dispositionSealed .exactW0Rollback).receiptDigest =
      rollbackRestoreReceiptDigest
  active : SealedProbeArmMeasurement RuntimeState snapshotOf
    (allocation.cloneFor .active)
  sham : SealedProbeArmMeasurement RuntimeState snapshotOf
    (allocation.cloneFor .outcomeIndependentSham)
  delayed : SealedProbeArmMeasurement RuntimeState snapshotOf
    (allocation.cloneFor .delayedNoCredit)
  rollback : SealedProbeArmMeasurement RuntimeState snapshotOf
    (allocation.cloneFor .exactW0Rollback)
  activeUsesAdmittedSuccessor :
    active.runtimeState = activeAdmission.runtimeAfter
  activeUsesAdmittedCandidate :
    active.behaviorRevision = activeAdmission.candidateRevision
  shamUsesAdmittedSuccessor : sham.runtimeState = shamAdmission.runtimeAfter
  shamUsesAdmittedCandidate :
    sham.behaviorRevision = shamAdmission.candidateRevision
  delayedUsesUnchangedFork :
    delayed.runtimeState = forkRuntime .delayedNoCredit
  delayedUsesW0Revision : delayed.behaviorRevision = w0Revision
  delayedReadsExactW0 : delayed.snapshot = w0Snapshot
  rollbackUsesW0Revision : rollback.behaviorRevision = w0Revision
  rollbackReadsExactW0 : rollback.snapshot = w0Snapshot
  commonModelConfig :
    sham.modelConfigDigest = active.modelConfigDigest ∧
    delayed.modelConfigDigest = active.modelConfigDigest ∧
    rollback.modelConfigDigest = active.modelConfigDigest
  commonSealedProbeSuite :
    sham.sealedProbeSuiteDigest = active.sealedProbeSuiteDigest ∧
    delayed.sealedProbeSuiteDigest = active.sealedProbeSuiteDigest ∧
    rollback.sealedProbeSuiteDigest = active.sealedProbeSuiteDigest
  activeProbeCallBindsMeasurement :
    (calls.probe .active).responseDigest = active.responseTraceDigest
  shamProbeCallBindsMeasurement :
    (calls.probe .outcomeIndependentSham).responseDigest =
      sham.responseTraceDigest
  delayedProbeCallBindsMeasurement :
    (calls.probe .delayedNoCredit).responseDigest = delayed.responseTraceDigest
  rollbackProbeCallBindsMeasurement :
    (calls.probe .exactW0Rollback).responseDigest =
      rollback.responseTraceDigest
  trajectoryCallBeforeSeal :
    calls.trajectory.sequence < timeline.trajectorySealed.sequence
  escrowBeforeEveryProposalCall : ∀ arm,
    timeline.outcomeEscrowed.sequence < (calls.proposal arm).sequence
  everyProposalCallBeforeItsSeal : ∀ arm,
    (calls.proposal arm).sequence < (timeline.proposalSealed arm).sequence
  everyDispositionBeforeEveryProbeCall : ∀ dispositionArm probeArm,
    (timeline.dispositionSealed dispositionArm).sequence <
      (calls.probe probeArm).sequence
  everyProbeCallBeforeItsSeal : ∀ arm,
    (calls.probe arm).sequence < (timeline.probeSealed arm).sequence

/-! ## Exact analysis-row derivation -/

structure BlockAnalysisRow where
  blockId : BlockId
  activeScore : Bool
  shamScore : Bool
  delayedScore : Bool
  rollbackScore : Bool
  activeResponseTraceDigest : EvidenceDigest
  shamResponseTraceDigest : EvidenceDigest
  delayedResponseTraceDigest : EvidenceDigest
  rollbackResponseTraceDigest : EvidenceDigest
deriving Repr, DecidableEq

def analysisRowOf
    (block : FourArmBlock RuntimeState snapshotOf) : BlockAnalysisRow :=
  { blockId := block.blockId
    activeScore := block.active.score
    shamScore := block.sham.score
    delayedScore := block.delayed.score
    rollbackScore := block.rollback.score
    activeResponseTraceDigest := block.active.responseTraceDigest
    shamResponseTraceDigest := block.sham.responseTraceDigest
    delayedResponseTraceDigest := block.delayed.responseTraceDigest
    rollbackResponseTraceDigest := block.rollback.responseTraceDigest }

inductive ControlArm where
  | sham
  | delayed
  | rollback
deriving Repr, DecidableEq

def controlScore : ControlArm → BlockAnalysisRow → Bool
  | .sham, row => row.shamScore
  | .delayed, row => row.delayedScore
  | .rollback, row => row.rollbackScore

def contrastCountsOf : List BlockAnalysisRow → ControlArm → ContrastCounts
  | [], _ => { activeWins := 0, controlWins := 0, ties := 0 }
  | row :: rest, control =>
      let tail := contrastCountsOf rest control
      match row.activeScore, controlScore control row with
      | true, false => { tail with activeWins := tail.activeWins + 1 }
      | false, true => { tail with controlWins := tail.controlWins + 1 }
      | _, _ => { tail with ties := tail.ties + 1 }

theorem contrastCountsSampleSizeIsRowCount
    (rows : List BlockAnalysisRow) (control : ControlArm) :
    (contrastCountsOf rows control).sampleSize = rows.length := by
  induction rows with
  | nil => rfl
  | cons head tail inductionHypothesis =>
      have sizeTail := inductionHypothesis
      unfold ContrastCounts.sampleSize ContrastCounts.discordant at sizeTail
      cases active : head.activeScore <;>
      cases controlValue : controlScore control head <;>
      simp [contrastCountsOf, active, controlValue,
        ContrastCounts.sampleSize, ContrastCounts.discordant]
      <;> omega

structure IndependentAnalysisReceipt where
  receiptDigest : EvidenceDigest
  analyst : Principal
  analysisContractDigest : EvidenceDigest
  normalizedRowsDigest : EvidenceDigest
  exactAnalysisProgramDigest : EvidenceDigest
  lcbProgramDigest : EvidenceDigest
  resultDigest : EvidenceDigest
  integrity : OccurrenceIntegrity
  activeVsShamLcbPositive : Bool
  activeVsDelayedLcbPositive : Bool
  activeVsRollbackLcbPositive : Bool
deriving Repr, DecidableEq

structure CausalEfficacyOccurrenceWitness
    (RuntimeState : Type)
    (snapshotOf : RuntimeState → BehavioralSnapshot) where
  blocks : List (FourArmBlock RuntimeState snapshotOf)
  analysisReceipt : IndependentAnalysisReceipt
  analysisRows : List BlockAnalysisRow
  exactlyThreeHundredBlocks : blocks.length = 300
  blockIdsUnique : (blocks.map fun block => block.blockId).Nodup
  analysisRowsAreExact : analysisRows = blocks.map analysisRowOf
  globalCallIdsUnique :
    (blocks.flatMap fun block => block.calls.observedCallIds).Nodup
  globalProtocolEventIdsUnique :
    (blocks.flatMap fun block => protocolEventIds block.timeline).Nodup

def exactStructuralCompleteness : OperationalCompleteness :=
  { exactThreeHundredBlocks := true
    everyBlockHasFourSealedArmOutcomes := true
    noMissingProbeOrEvaluatorReceipt := true }

def derivedSummary
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf) :
    MarkedOccurrenceSummary :=
  { integrity := occurrence.analysisReceipt.integrity
    completeness := exactStructuralCompleteness
    activeVsSham := contrastGateFromCounts
      (contrastCountsOf occurrence.analysisRows .sham)
      occurrence.analysisReceipt.activeVsShamLcbPositive
    activeVsDelayed := contrastGateFromCounts
      (contrastCountsOf occurrence.analysisRows .delayed)
      occurrence.analysisReceipt.activeVsDelayedLcbPositive
    activeVsRollback := contrastGateFromCounts
      (contrastCountsOf occurrence.analysisRows .rollback)
      occurrence.analysisReceipt.activeVsRollbackLcbPositive }

theorem witnessAnalysisRowsAndEveryContrastHaveSampleSizeThreeHundred
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf) :
    occurrence.analysisRows.length = 300 ∧
    (contrastCountsOf occurrence.analysisRows .sham).sampleSize = 300 ∧
    (contrastCountsOf occurrence.analysisRows .delayed).sampleSize = 300 ∧
    (contrastCountsOf occurrence.analysisRows .rollback).sampleSize = 300 := by
  have rowsLength : occurrence.analysisRows.length = 300 := by
    rw [occurrence.analysisRowsAreExact, List.length_map,
      occurrence.exactlyThreeHundredBlocks]
  exact ⟨rowsLength,
    (contrastCountsSampleSizeIsRowCount occurrence.analysisRows .sham).trans
      rowsLength,
    (contrastCountsSampleSizeIsRowCount occurrence.analysisRows .delayed).trans
      rowsLength,
    (contrastCountsSampleSizeIsRowCount occurrence.analysisRows .rollback).trans
      rowsLength⟩

theorem derivedExactDecisionsComeOnlyFromExactRows
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf) :
    (derivedSummary occurrence).activeVsSham.adjustedExactPAtMostPointZeroFive =
      exactBonferroniPass (contrastCountsOf occurrence.analysisRows .sham) ∧
    (derivedSummary occurrence).activeVsDelayed.adjustedExactPAtMostPointZeroFive =
      exactBonferroniPass (contrastCountsOf occurrence.analysisRows .delayed) ∧
    (derivedSummary occurrence).activeVsRollback.adjustedExactPAtMostPointZeroFive =
      exactBonferroniPass
        (contrastCountsOf occurrence.analysisRows .rollback) := by
  simp [derivedSummary, contrastGateFromCounts]

/-! ## Structural projections -/

theorem allocationHasFourDistinctClonesAndCompleteOrders
    (allocation : ForkAllocation) :
    (armUniverse.map allocation.cloneFor).length = 4 ∧
    (armUniverse.map allocation.cloneFor).Nodup ∧
    allocation.proposalOrder.length = 4 ∧
    allocation.probeOrder.length = 4 := by
  have proposalLength := List.Perm.length_eq allocation.proposalOrderPermutes
  have probeLength := List.Perm.length_eq allocation.probeOrderPermutes
  constructor
  · rfl
  constructor
  · exact allocation.clonesNodup
  constructor
  · calc
      allocation.proposalOrder.length = armUniverse.length := proposalLength
      _ = 4 := rfl
  · calc
      allocation.probeOrder.length = armUniverse.length := probeLength
      _ = 4 := rfl

theorem ledgerHasExactlyOneTrajectoryFourProposalsAndFourProbes
    (ledger : GenerationLedger allocation) :
    ledger.observedCallIds.length = 9 ∧ ledger.observedCallIds.Nodup := by
  constructor
  · rw [ledger.observedCallIdsExact]
    simp [namedGenerationCallIds, armUniverse]
  · exact ledger.callIdsUnique

theorem protocolTimelineHasExactlyTwentyFiveTypedEvents
    (timeline : ProtocolTimeline allocation) :
    (protocolEventIds timeline).length = 25 := by
  simp [protocolEventIds, armUniverse]

theorem extraOrReplacedGenerationCallFailsClosed
    (ledger : GenerationLedger allocation)
    (mismatch : ledger.observedCallIds ≠
      namedGenerationCallIds allocation ledger.trajectory ledger.proposal
        ledger.probe) : False :=
  mismatch ledger.observedCallIdsExact

theorem mismatchedRollbackBehavioralSnapshotFailsClosed
    (block : FourArmBlock RuntimeState snapshotOf)
    (mismatch : block.rollback.snapshot ≠ block.w0Snapshot) : False :=
  mismatch block.rollbackReadsExactW0

theorem prematureDelayedReleaseFailsClosed
    (block : FourArmBlock RuntimeState snapshotOf)
    (arm : Arm)
    (premature : ¬ (block.timeline.probeSealed arm).sequence <
      block.timeline.delayedAuditRelease.sequence) : False :=
  premature (block.timeline.everyProbeBeforeDelayedRelease arm)

theorem mismatchedAnalysisRowsFailClosed
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf)
    (mismatch : occurrence.analysisRows ≠
      occurrence.blocks.map analysisRowOf) : False :=
  mismatch occurrence.analysisRowsAreExact

theorem blockProjectsExactW0AndDelayedReleaseBoundary
    (block : FourArmBlock RuntimeState snapshotOf) :
    (∀ arm, snapshotOf (block.forkRuntime arm) = block.w0Snapshot) ∧
    block.delayed.snapshot = block.w0Snapshot ∧
    block.rollback.snapshot = block.w0Snapshot ∧
    (∀ arm, (block.timeline.probeSealed arm).sequence <
      block.timeline.delayedAuditRelease.sequence) :=
  ⟨block.allForksStartAtExactW0, block.delayedReadsExactW0,
    block.rollbackReadsExactW0,
    block.timeline.everyProbeBeforeDelayedRelease⟩

theorem blockProjectsTypedCallToAdmissionAndMeasurementBindings
    (block : FourArmBlock RuntimeState snapshotOf) :
    (block.calls.proposal .active).responseDigest =
      block.activeAdmission.wire.intent.proposalDigest ∧
    (block.calls.proposal .outcomeIndependentSham).responseDigest =
      block.shamAdmission.wire.intent.proposalDigest ∧
    (block.calls.proposal .delayedNoCredit).responseDigest =
      block.delayedProposalArtifactDigest ∧
    (block.calls.proposal .exactW0Rollback).responseDigest =
      block.rollbackStagingAdmission.wire.intent.proposalDigest ∧
    (block.calls.probe .active).responseDigest =
      block.active.responseTraceDigest ∧
    (block.calls.probe .outcomeIndependentSham).responseDigest =
      block.sham.responseTraceDigest ∧
    (block.calls.probe .delayedNoCredit).responseDigest =
      block.delayed.responseTraceDigest ∧
    (block.calls.probe .exactW0Rollback).responseDigest =
      block.rollback.responseTraceDigest :=
  ⟨block.activeProposalCallBindsAdmission,
    block.shamProposalCallBindsAdmission,
    block.delayedProposalCallBindsQuarantine,
    block.rollbackProposalCallBindsStagingAdmission,
    block.activeProbeCallBindsMeasurement,
    block.shamProbeCallBindsMeasurement,
    block.delayedProbeCallBindsMeasurement,
    block.rollbackProbeCallBindsMeasurement⟩

theorem witnessHasTwoThousandSevenHundredUniqueTypedCalls
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf) :
    (occurrence.blocks.flatMap fun block =>
      block.calls.observedCallIds).length = 2700 ∧
    (occurrence.blocks.flatMap fun block =>
      block.calls.observedCallIds).Nodup := by
  have eachBlockHasNine : ∀ block ∈ occurrence.blocks,
      block.calls.observedCallIds.length = 9 := by
    intro block _
    exact (ledgerHasExactlyOneTrajectoryFourProposalsAndFourProbes
      block.calls).1
  have flattenedLength : ∀ blocks : List (FourArmBlock RuntimeState snapshotOf),
      (∀ block ∈ blocks, block.calls.observedCallIds.length = 9) →
      (blocks.flatMap fun block => block.calls.observedCallIds).length =
        blocks.length * 9 := by
    intro blocks allNine
    induction blocks with
    | nil => simp
    | cons head tail inductionHypothesis =>
        have headNine : head.calls.observedCallIds.length = 9 :=
          allNine head (by simp)
        have tailNine : ∀ block ∈ tail,
            block.calls.observedCallIds.length = 9 := by
          intro block present
          exact allNine block (by simp [present])
        rw [List.flatMap_cons, List.length_append,
          inductionHypothesis tailNine, headNine]
        simp only [List.length_cons]
        omega
  constructor
  · rw [flattenedLength occurrence.blocks eachBlockHasNine,
      occurrence.exactlyThreeHundredBlocks]
  · exact occurrence.globalCallIdsUnique

/-! ## Explicit real-world semantic boundary -/

/--
Every predicate below has exact typed arguments, but its real-world meaning is
not manufactured by Lean. A deployment qualification must supply these
semantics for the concrete adapters and occurrence.
-/
structure CausalEfficacyInterpretation
    (RuntimeState : Type)
    (snapshotOf : RuntimeState → BehavioralSnapshot) where
  runtimeAdapterSound : RuntimeCertificateAdmissionBinding RuntimeState → Prop
  keyTimeNonceSound : RuntimeCertificateAdmissionBinding RuntimeState → Prop
  providerLedgerRealizes :
    (allocation : ForkAllocation) → GenerationLedger allocation → Prop
  futureRandomAssignment : ForkAllocation → Prop
  protocolTimelineRealizes :
    (allocation : ForkAllocation) → ProtocolTimeline allocation → Prop
  feedbackAssignmentsRealizeExactModelInputs :
    FourArmBlock RuntimeState snapshotOf → Prop
  projectionDigestSound : RuntimeState → BehavioralSnapshot → Prop
  genuineOutcomeTruth :
    RuntimeCertificateAdmissionBinding RuntimeState → Prop
  independentCausalCredit :
    RuntimeCertificateAdmissionBinding RuntimeState → Prop
  shamOutcomeIndependent :
    OutcomeEvidencePackage → OutcomeEvidencePackage → Prop
  activeShamAdmittedShapeMatched :
    FourArmBlock RuntimeState snapshotOf → Prop
  delayedNoAdmissionAndEscrow : FourArmBlock RuntimeState snapshotOf → Prop
  informationFlowAndIsolation : FourArmBlock RuntimeState snapshotOf → Prop
  rollbackRestoreOccurred : FourArmBlock RuntimeState snapshotOf → Prop
  activeStateMediatesBehavior :
    RuntimeCertificateAdmissionBinding RuntimeState → BehavioralSnapshot →
      RuntimeState → BehavioralSnapshot → CallId →
      EvidenceDigest → EvidenceDigest → Bool → Prop
  analysisReceiptRealizes :
    IndependentAnalysisReceipt → List BlockAnalysisRow → Prop
  independentAnalysisReimplementation : IndependentAnalysisReceipt → Prop
  causalIdentification :
    CausalEfficacyOccurrenceWitness RuntimeState snapshotOf → Prop

structure CausalEfficacySemanticPremises
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf)
    (interpretation : CausalEfficacyInterpretation RuntimeState snapshotOf) : Prop where
  perBlock : ∀ block, block ∈ occurrence.blocks →
    interpretation.runtimeAdapterSound block.activeAdmission ∧
    interpretation.runtimeAdapterSound block.shamAdmission ∧
    interpretation.runtimeAdapterSound block.rollbackStagingAdmission ∧
    interpretation.keyTimeNonceSound block.activeAdmission ∧
    interpretation.keyTimeNonceSound block.shamAdmission ∧
    interpretation.keyTimeNonceSound block.rollbackStagingAdmission ∧
    interpretation.providerLedgerRealizes block.allocation block.calls ∧
    interpretation.futureRandomAssignment block.allocation ∧
    interpretation.protocolTimelineRealizes block.allocation block.timeline ∧
    interpretation.feedbackAssignmentsRealizeExactModelInputs block ∧
    interpretation.projectionDigestSound block.w0Runtime block.w0Snapshot ∧
    (∀ arm, interpretation.projectionDigestSound (block.forkRuntime arm)
      block.w0Snapshot) ∧
    interpretation.projectionDigestSound block.active.runtimeState
      block.active.snapshot ∧
    interpretation.projectionDigestSound block.sham.runtimeState
      block.sham.snapshot ∧
    interpretation.projectionDigestSound block.delayed.runtimeState
      block.delayed.snapshot ∧
    interpretation.projectionDigestSound block.rollback.runtimeState
      block.rollback.snapshot ∧
    interpretation.genuineOutcomeTruth block.activeAdmission ∧
    interpretation.genuineOutcomeTruth block.rollbackStagingAdmission ∧
    interpretation.independentCausalCredit
      block.activeAdmission ∧
    interpretation.independentCausalCredit
      block.rollbackStagingAdmission ∧
    interpretation.shamOutcomeIndependent
      block.shamAdmission.supplement.package block.genuineOutcomePackage ∧
    interpretation.activeShamAdmittedShapeMatched block ∧
    interpretation.delayedNoAdmissionAndEscrow block ∧
    interpretation.informationFlowAndIsolation block ∧
    interpretation.rollbackRestoreOccurred block ∧
    interpretation.activeStateMediatesBehavior block.activeAdmission
      block.w0Snapshot block.active.runtimeState block.active.snapshot
      (block.calls.probe .active).callId block.active.responseTraceDigest
      block.active.sealedScoreReceiptDigest block.active.score
  analysisReceiptBound : interpretation.analysisReceiptRealizes
    occurrence.analysisReceipt occurrence.analysisRows
  analysisWasIndependentlyReimplemented :
    interpretation.independentAnalysisReimplementation
      occurrence.analysisReceipt
  causallyIdentified : interpretation.causalIdentification occurrence

def AssumptionRelativeBoundedCausalEfficacyClaim
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf)
    (interpretation : CausalEfficacyInterpretation RuntimeState snapshotOf) : Prop :=
  CausalEfficacySemanticPremises occurrence interpretation ∧
  ScientificGoConditions (derivedSummary occurrence)

/-- GO is composed with every real-world semantic premise, never substituted for it. -/
theorem typedOccurrenceAndDerivedGoYieldBoundedCausalEfficacy
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf)
    (interpretation : CausalEfficacyInterpretation RuntimeState snapshotOf)
    (semantics : CausalEfficacySemanticPremises occurrence interpretation)
    (go : ScientificGoConditions (derivedSummary occurrence)) :
    AssumptionRelativeBoundedCausalEfficacyClaim occurrence interpretation ∧
    classify (.marked (derivedSummary occurrence)) =
      .causalMacroplasticityGo :=
  ⟨⟨semantics, go⟩, allThreeCompleteGatesProduceGo go⟩

theorem derivedGoWithMissingRuntimeAdapterCannotYieldCausalClaim
    (occurrence : CausalEfficacyOccurrenceWitness RuntimeState snapshotOf)
    (interpretation : CausalEfficacyInterpretation RuntimeState snapshotOf)
    (block : FourArmBlock RuntimeState snapshotOf)
    (present : block ∈ occurrence.blocks)
    (go : ScientificGoConditions (derivedSummary occurrence))
    (missing : ¬ interpretation.runtimeAdapterSound block.activeAdmission) :
    classify (.marked (derivedSummary occurrence)) =
        .causalMacroplasticityGo ∧
      ¬ AssumptionRelativeBoundedCausalEfficacyClaim occurrence interpretation := by
  constructor
  · exact allThreeCompleteGatesProduceGo go
  · intro claim
    exact missing (claim.1.perBlock block present).1

/-- Existing atomic admission still has a countermodel with no behavior change. -/
theorem atomicAdmissionAloneDoesNotEntailBehaviorChange :
    AtomicLearnAdmission AtomicAdmission.Consistency.exampleDigest
      AtomicAdmission.Consistency.ExactSingleTargetInvariant
      AtomicAdmission.Consistency.initialState
      AtomicAdmission.Consistency.trajectory
      AtomicAdmission.Consistency.outcomePackage
      AtomicAdmission.Consistency.proposal
      AtomicAdmission.Consistency.permit
      AtomicAdmission.Consistency.certificate
      AtomicAdmission.Consistency.commitWitness
      AtomicAdmission.Consistency.currentHead
      AtomicAdmission.Consistency.nextState
      AtomicAdmission.Consistency.nextHead ∧
    ¬ AtomicAdmission.NonEntailment.BehaviorChanged
      AtomicAdmission.NonEntailment.constantBehavior
      AtomicAdmission.Consistency.initialState
      AtomicAdmission.Consistency.nextState :=
  AtomicAdmission.NonEntailment.atomicAdmissionCanExistWithoutBehaviorChange

end HSWM.CanonicalLearning.CausalEfficacyBridge
