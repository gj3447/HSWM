import HSWMOutcomeJudgment

/-!
# HSWM head-bound atomic learning admission

This module strengthens the abstract outcome-learning relation with one shared
predecessor head, an owner-bound Permit, an owner-bound transition-invariant
certificate, and one exact commit witness.  It is a protective specification,
not a runtime linearizability, authentication, digest-security, or efficacy
proof.
-/

namespace HSWM.CanonicalLearning.AtomicAdmission

open OutcomeJudgment

structure StateDigest where
  value : String
deriving Repr, DecidableEq

structure RecordDigest where
  value : String
deriving Repr, DecidableEq

/-- One abstract durable lineage position observed at admission. -/
structure HeadSnapshot where
  lineageId : String
  sequence : Nat
  stateDigest : StateDigest
  recordDigest : RecordDigest
deriving Repr, DecidableEq

/-- A Permit record bound to one head and exact revision proposal. -/
structure HeadBoundPermit where
  responsibilityOwner : Principal
  decision : PermitDecision
  head : HeadSnapshot
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  contentDigest : EvidenceDigest
deriving Repr, DecidableEq

def PermitOwnedBy (permit : HeadBoundPermit) (owner : Principal) : Prop :=
  permit.responsibilityOwner = owner

theorem headBoundPermitHasUniqueOwner (permit : HeadBoundPermit) :
    ∃ owner, PermitOwnedBy permit owner ∧
      ∀ other, PermitOwnedBy permit other → other = owner := by
  exact ⟨permit.responsibilityOwner, rfl, fun _ owned => owned.symm⟩

/-- A separately owned certificate for the exact `S`, proposal and `S'`. -/
structure HeadBoundInvariantCertificate where
  responsibilityOwner : Principal
  validator : Principal
  head : HeadSnapshot
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  contentDigest : EvidenceDigest
deriving Repr, DecidableEq

def InvariantCertificateOwnedBy
    (certificate : HeadBoundInvariantCertificate)
    (owner : Principal) : Prop :=
  certificate.responsibilityOwner = owner

theorem invariantCertificateHasUniqueOwner
    (certificate : HeadBoundInvariantCertificate) :
    ∃ owner, InvariantCertificateOwnedBy certificate owner ∧
      ∀ other, InvariantCertificateOwnedBy certificate other →
        other = owner := by
  exact ⟨certificate.responsibilityOwner, rfl,
    fun _ owned => owned.symm⟩

/-- Declared linearization witness consuming the exact two certificate IDs. -/
structure AdmissionCommitWitness where
  predecessorHead : HeadSnapshot
  successorHead : HeadSnapshot
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  consumedPermitDigest : EvidenceDigest
  consumedInvariantDigest : EvidenceDigest
deriving Repr, DecidableEq

/--
All bindings required at the one admitted transition.  The old two-argument
`Learn` invariant is instantiated with the exact `next`, yielding the stronger
three-argument transition invariant here.
-/
structure AtomicAdmissionConditions
    (digest : CanonicalState → StateDigest)
    (transitionInvariant :
      CanonicalState → RevisionProposal → CanonicalState → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (package : OutcomeEvidencePackage)
    (proposal : RevisionProposal)
    (permit : HeadBoundPermit)
    (certificate : HeadBoundInvariantCertificate)
    (commitWitness : AdmissionCommitWitness)
    (currentHead : HeadSnapshot)
    (next : CanonicalState)
    (nextHead : HeadSnapshot) where
  currentVersion : AtomVersion
  targetCurrent : state.current proposal.target = some currentVersion
  judgment : RevisionSupportJudgment
  judgmentPresent : package.judgment = some judgment
  outcomeLearning : LearnFromOutcomeEvidence
    (fun pre candidate => transitionInvariant pre candidate next)
    state trajectory package proposal permit.decision next
  stateDigestMatches : digest state = currentHead.stateDigest
  permitHeadMatches : permit.head = currentHead
  invariantHeadMatches : certificate.head = currentHead
  commitPredecessorMatches : commitWitness.predecessorHead = currentHead
  commitSuccessorMatches : commitWitness.successorHead = nextHead
  permitExpectedRevisionMatches :
    permit.expectedRevision = proposal.expectedRevision
  permitCandidateRevisionMatches :
    permit.candidateRevision = proposal.candidateRevision
  invariantTargetMatches : certificate.target = proposal.target
  invariantExpectedRevisionMatches :
    certificate.expectedRevision = proposal.expectedRevision
  invariantCandidateRevisionMatches :
    certificate.candidateRevision = proposal.candidateRevision
  commitTargetMatches : commitWitness.target = proposal.target
  commitExpectedRevisionMatches :
    commitWitness.expectedRevision = proposal.expectedRevision
  commitCandidateRevisionMatches :
    commitWitness.candidateRevision = proposal.candidateRevision
  commitConsumesPermit :
    commitWitness.consumedPermitDigest = permit.contentDigest
  commitConsumesInvariant :
    commitWitness.consumedInvariantDigest = certificate.contentDigest
  successorLineageMatches : nextHead.lineageId = currentHead.lineageId
  successorIsNext : nextHead.sequence = currentHead.sequence + 1
  nextStateDigestMatches : digest next = nextHead.stateDigest
  authorizerNotActor : permit.decision.authorizer ≠ trajectory.actor
  authorizerNotProposer : permit.decision.authorizer ≠ proposal.proposer
  authorizerNotTargetOwner :
    permit.decision.authorizer ≠ currentVersion.responsibilityOwner
  authorizerNotAdjudicator :
    permit.decision.authorizer ≠ judgment.adjudicator
  authorizerNotJudgmentOwner :
    permit.decision.authorizer ≠ judgment.responsibilityOwner
  authorizerNotPermitOwner :
    permit.decision.authorizer ≠ permit.responsibilityOwner

/-- Absence of this one constructor means no atomic canonical admission. -/
inductive AtomicLearnAdmission
    (digest : CanonicalState → StateDigest)
    (transitionInvariant :
      CanonicalState → RevisionProposal → CanonicalState → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (package : OutcomeEvidencePackage)
    (proposal : RevisionProposal)
    (permit : HeadBoundPermit)
    (certificate : HeadBoundInvariantCertificate)
    (commitWitness : AdmissionCommitWitness)
    (currentHead : HeadSnapshot) :
    CanonicalState → HeadSnapshot → Prop where
  | admit
      (conditions : AtomicAdmissionConditions digest transitionInvariant
        state trajectory package proposal permit certificate commitWitness
        currentHead next nextHead) :
      AtomicLearnAdmission digest transitionInvariant state trajectory package
        proposal permit certificate commitWitness currentHead next nextHead

theorem atomicAdmissionRequiresOutcomeLearning
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    LearnFromOutcomeEvidence
      (fun pre candidate => transitionInvariant pre candidate next)
      state trajectory package proposal permit.decision next := by
  cases admitted with
  | admit conditions => exact conditions.outcomeLearning

theorem atomicAdmissionRequiresUnderlyingLearn
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    ∃ judgment,
      package.judgment = some judgment ∧
      Learn (fun pre candidate => transitionInvariant pre candidate next)
        state trajectory (judgmentAsOutcomeReceipt judgment) proposal
        permit.decision next := by
  exact learnFromEvidenceRequiresUnderlyingLearn
    (atomicAdmissionRequiresOutcomeLearning admitted)

theorem atomicAdmissionRequiresSharedHead
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    permit.head = currentHead ∧
    certificate.head = currentHead ∧
    commitWitness.predecessorHead = currentHead := by
  cases admitted with
  | admit conditions =>
      exact ⟨conditions.permitHeadMatches,
        conditions.invariantHeadMatches,
        conditions.commitPredecessorMatches⟩

theorem atomicAdmissionRequiresExactProposalBinding
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    permit.expectedRevision = proposal.expectedRevision ∧
    permit.candidateRevision = proposal.candidateRevision ∧
    certificate.target = proposal.target ∧
    certificate.expectedRevision = proposal.expectedRevision ∧
    certificate.candidateRevision = proposal.candidateRevision ∧
    commitWitness.target = proposal.target ∧
    commitWitness.expectedRevision = proposal.expectedRevision ∧
    commitWitness.candidateRevision = proposal.candidateRevision := by
  cases admitted with
  | admit conditions =>
      exact ⟨conditions.permitExpectedRevisionMatches,
        conditions.permitCandidateRevisionMatches,
        conditions.invariantTargetMatches,
        conditions.invariantExpectedRevisionMatches,
        conditions.invariantCandidateRevisionMatches,
        conditions.commitTargetMatches,
        conditions.commitExpectedRevisionMatches,
        conditions.commitCandidateRevisionMatches⟩

theorem atomicAdmissionRequiresTransitionInvariant
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    transitionInvariant state proposal next := by
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  exact learnRequiresInvariant learned

theorem atomicAdmissionRequiresExactCertificateConsumption
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    commitWitness.consumedPermitDigest = permit.contentDigest ∧
    commitWitness.consumedInvariantDigest = certificate.contentDigest := by
  cases admitted with
  | admit conditions =>
      exact ⟨conditions.commitConsumesPermit,
        conditions.commitConsumesInvariant⟩

theorem atomicAdmissionRequiresLinearSuccessor
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    commitWitness.successorHead = nextHead ∧
    nextHead.lineageId = currentHead.lineageId ∧
    nextHead.sequence = currentHead.sequence + 1 := by
  cases admitted with
  | admit conditions =>
      exact ⟨conditions.commitSuccessorMatches,
        conditions.successorLineageMatches,
        conditions.successorIsNext⟩

theorem atomicAdmissionRequiresStateDigestBinding
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    digest state = currentHead.stateDigest ∧
    digest next = nextHead.stateDigest := by
  cases admitted with
  | admit conditions =>
      exact ⟨conditions.stateDigestMatches,
        conditions.nextStateDigestMatches⟩

theorem atomicAdmissionRequiresAuthorizerSeparation
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    ∃ currentVersion judgment,
      state.current proposal.target = some currentVersion ∧
      package.judgment = some judgment ∧
      permit.decision.authorizer ≠ trajectory.actor ∧
      permit.decision.authorizer ≠ proposal.proposer ∧
      permit.decision.authorizer ≠ currentVersion.responsibilityOwner ∧
      permit.decision.authorizer ≠ judgment.adjudicator ∧
      permit.decision.authorizer ≠ judgment.responsibilityOwner ∧
      permit.decision.authorizer ≠ permit.responsibilityOwner := by
  cases admitted with
  | admit conditions =>
      exact ⟨conditions.currentVersion, conditions.judgment,
        conditions.targetCurrent, conditions.judgmentPresent,
        conditions.authorizerNotActor,
        conditions.authorizerNotProposer,
        conditions.authorizerNotTargetOwner,
        conditions.authorizerNotAdjudicator,
        conditions.authorizerNotJudgmentOwner,
        conditions.authorizerNotPermitOwner⟩

theorem atomicAdmissionPreservesTargetOwner
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    ∃ before after,
      state.current proposal.target = some before ∧
      next.current proposal.target = some after ∧
      after.responsibilityOwner = before.responsibilityOwner := by
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  exact learnPreservesTargetOwner learned

theorem atomicAdmissionChangesOnlyTarget
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead)
    (other : AtomAddress)
    (different : other ≠ proposal.target) :
    next.current other = state.current other := by
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  exact learnChangesOnlyTarget learned other different

theorem atomicAdmissionArchivesPreviousVersion
    (admitted : AtomicLearnAdmission digest transitionInvariant state
      trajectory package proposal permit certificate commitWitness currentHead
      next nextHead) :
    ∃ before,
      state.current proposal.target = some before ∧
      next.history = (proposal.target, before) :: state.history := by
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  exact learnArchivesPreviousVersion learned

theorem stalePermitHeadCannotAdmit
    (stale : permit.head ≠ currentHead) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact stale (atomicAdmissionRequiresSharedHead admitted).1

theorem staleInvariantHeadCannotAdmit
    (stale : certificate.head ≠ currentHead) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact stale (atomicAdmissionRequiresSharedHead admitted).2.1

theorem predecessorDriftCannotAdmit
    (drifted : commitWitness.predecessorHead ≠ currentHead) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact drifted (atomicAdmissionRequiresSharedHead admitted).2.2

theorem predecessorStateDigestMismatchCannotAdmit
    (mismatch : digest state ≠ currentHead.stateDigest) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact mismatch (atomicAdmissionRequiresStateDigestBinding admitted).1

theorem permitCandidateMismatchCannotAdmit
    (mismatch : permit.candidateRevision ≠ proposal.candidateRevision) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact mismatch
    (atomicAdmissionRequiresExactProposalBinding admitted).2.1

theorem invariantCandidateMismatchCannotAdmit
    (mismatch : certificate.candidateRevision ≠ proposal.candidateRevision) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact mismatch
    (atomicAdmissionRequiresExactProposalBinding admitted).2.2.2.2.1

theorem commitCandidateMismatchCannotAdmit
    (mismatch : commitWitness.candidateRevision ≠ proposal.candidateRevision) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact mismatch
    (atomicAdmissionRequiresExactProposalBinding admitted).2.2.2.2.2.2.2

theorem substitutedPermitCertificateCannotAdmit
    (substituted :
      commitWitness.consumedPermitDigest ≠ permit.contentDigest) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact substituted
    (atomicAdmissionRequiresExactCertificateConsumption admitted).1

theorem substitutedInvariantCertificateCannotAdmit
    (substituted :
      commitWitness.consumedInvariantDigest ≠ certificate.contentDigest) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact substituted
    (atomicAdmissionRequiresExactCertificateConsumption admitted).2

theorem invariantFailureCannotAtomicAdmit
    (failed : ¬ transitionInvariant state proposal next) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  exact failed (atomicAdmissionRequiresTransitionInvariant admitted)

theorem deniedPermitCannotAtomicAdmit
    (denied : permit.decision.allowed = false) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  exact deniedPermitCannotLearn denied learned

theorem inactivePermitCannotAtomicAdmit
    (inactive : permit.decision.activeAtDecision = false) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  exact inactivePermitCannotLearn inactive learned

theorem collapsedAuthorizerActorCannotAdmit
    (collapsed : permit.decision.authorizer = trajectory.actor) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  rcases atomicAdmissionRequiresAuthorizerSeparation admitted with
    ⟨_currentVersion, _judgment, _targetCurrent, _judgmentPresent,
      separated, _rest⟩
  exact separated collapsed

theorem collapsedAuthorizerPermitOwnerCannotAdmit
    (collapsed :
      permit.decision.authorizer = permit.responsibilityOwner) :
    ¬ AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  intro admitted
  rcases atomicAdmissionRequiresAuthorizerSeparation admitted with
    ⟨_currentVersion, _judgment, _targetCurrent, _judgmentPresent,
      _notActor, _notProposer, _notTargetOwner, _notAdjudicator,
      _notJudgmentOwner, separated⟩
  exact separated collapsed

/-!
## Checked-in TypeScript composition obstruction

The repository has an owner-bound outcome *shape* and a DNRD-5 two-CAS
historical boundary.  They are not composed into the same transition, and
their explicit statuses do not provide outcome support, canonical Permit, an
exact transition-invariant witness, or a runtime mapping to the relation above.
-/

structure RuntimeAtomicAdmissionProfile where
  ownerBoundOutcomeShapePresent : Bool
  dnrdTwoCasHistoryBoundaryPresent : Bool
  outcomeSupportWitnessPresent : Bool
  canonicalPermitAtLinearizationPresent : Bool
  exactTransitionInvariantWitnessPresent : Bool
  sameTransitionCompositionPresent : Bool
  atomicAdmissionRuntimeMappingPresent : Bool
deriving Repr, DecidableEq

def ReadyForAtomicAdmission
    (profile : RuntimeAtomicAdmissionProfile) : Prop :=
  profile.ownerBoundOutcomeShapePresent = true ∧
  profile.dnrdTwoCasHistoryBoundaryPresent = true ∧
  profile.outcomeSupportWitnessPresent = true ∧
  profile.canonicalPermitAtLinearizationPresent = true ∧
  profile.exactTransitionInvariantWitnessPresent = true ∧
  profile.sameTransitionCompositionPresent = true ∧
  profile.atomicAdmissionRuntimeMappingPresent = true

/-- Exact semantic profile of the checked-in, separately bounded contracts. -/
def checkedInTypeScriptAtomicAdmissionProfile :
    RuntimeAtomicAdmissionProfile :=
  { ownerBoundOutcomeShapePresent := true
    dnrdTwoCasHistoryBoundaryPresent := true
    outcomeSupportWitnessPresent := false
    canonicalPermitAtLinearizationPresent := false
    exactTransitionInvariantWitnessPresent := false
    sameTransitionCompositionPresent := false
    atomicAdmissionRuntimeMappingPresent := false }

theorem missingOutcomeSupportObstructsAtomicRefinement
    (missing : profile.outcomeSupportWitnessPresent = false) :
    ¬ ReadyForAtomicAdmission profile := by
  intro ready
  rcases ready with ⟨_shape, _history, present, _permit,
    _invariant, _composition, _mapping⟩
  simp [missing] at present

theorem missingCanonicalPermitObstructsAtomicRefinement
    (missing : profile.canonicalPermitAtLinearizationPresent = false) :
    ¬ ReadyForAtomicAdmission profile := by
  intro ready
  rcases ready with ⟨_shape, _history, _outcome, present,
    _invariant, _composition, _mapping⟩
  simp [missing] at present

theorem missingTransitionInvariantObstructsAtomicRefinement
    (missing : profile.exactTransitionInvariantWitnessPresent = false) :
    ¬ ReadyForAtomicAdmission profile := by
  intro ready
  rcases ready with ⟨_shape, _history, _outcome, _permit,
    present, _composition, _mapping⟩
  simp [missing] at present

theorem uncomposedBoundariesObstructAtomicRefinement
    (missing : profile.sameTransitionCompositionPresent = false) :
    ¬ ReadyForAtomicAdmission profile := by
  intro ready
  rcases ready with ⟨_shape, _history, _outcome, _permit,
    _invariant, present, _mapping⟩
  simp [missing] at present

theorem missingRuntimeMappingObstructsAtomicRefinement
    (missing : profile.atomicAdmissionRuntimeMappingPresent = false) :
    ¬ ReadyForAtomicAdmission profile := by
  intro ready
  rcases ready with ⟨_shape, _history, _outcome, _permit,
    _invariant, _composition, present⟩
  simp [missing] at present

theorem checkedInTypeScriptCannotRefineAtomicAdmission :
    ¬ ReadyForAtomicAdmission checkedInTypeScriptAtomicAdmissionProfile := by
  simp [ReadyForAtomicAdmission,
    checkedInTypeScriptAtomicAdmissionProfile]

end HSWM.CanonicalLearning.AtomicAdmission
