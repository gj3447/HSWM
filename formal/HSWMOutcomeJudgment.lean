import HSWMCanonicalLearning

/-!
# HSWM owner-bound outcome judgment

An outcome observation and a revision-support judgment have different
schema-relative responsibility owners and lifecycles.  Observation alone never
constructs the support evidence consumed by canonical learning.

The role inequalities below are typed address separation.  They do not prove
identity authentication, real organizational independence, outcome truth,
criterion validity, causal credit, Permit, or HSWM efficacy.
-/

namespace HSWM.CanonicalLearning.OutcomeJudgment

structure ObservationId where
  value : String
deriving Repr, DecidableEq

structure JudgmentId where
  value : String
deriving Repr, DecidableEq

structure CriterionDigest where
  value : String
deriving Repr, DecidableEq

inductive ObservedOutcome where
  | observed
  | failed
  | unknown
deriving Repr, DecidableEq

/-- An evaluator-owned observation does not itself judge a revision proposal. -/
structure OutcomeObservation where
  observationId : ObservationId
  traceId : TraceId
  responsibilityOwner : Principal
  evaluator : Principal
  value : ObservedOutcome
  evidenceDigest : EvidenceDigest
deriving Repr, DecidableEq

def ObservationOwnedBy
    (observation : OutcomeObservation) (owner : Principal) : Prop :=
  observation.responsibilityOwner = owner

theorem observationHasUniqueOwner (observation : OutcomeObservation) :
    ∃ owner, ObservationOwnedBy observation owner ∧
      ∀ other, ObservationOwnedBy observation other → other = owner := by
  exact ⟨observation.responsibilityOwner, rfl,
    fun _ owned => owned.symm⟩

/-- A separately owned judgment binds one observation to one exact proposal. -/
structure RevisionSupportJudgment where
  judgmentId : JudgmentId
  traceId : TraceId
  observationId : ObservationId
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  responsibilityOwner : Principal
  adjudicator : Principal
  criterionDigest : CriterionDigest
  verdict : OutcomeVerdict
  evidenceDigest : EvidenceDigest
deriving Repr, DecidableEq

def JudgmentOwnedBy
    (judgment : RevisionSupportJudgment) (owner : Principal) : Prop :=
  judgment.responsibilityOwner = owner

theorem judgmentHasUniqueOwner (judgment : RevisionSupportJudgment) :
    ∃ owner, JudgmentOwnedBy judgment owner ∧
      ∀ other, JudgmentOwnedBy judgment other → other = owner := by
  exact ⟨judgment.responsibilityOwner, rfl,
    fun _ owned => owned.symm⟩

/-- Observation may exist before a separately owned judgment is available. -/
structure OutcomeEvidencePackage where
  observation : OutcomeObservation
  judgment : Option RevisionSupportJudgment
deriving Repr, DecidableEq

/-- Exact bindings and bounded role separation required of a support judgment. -/
structure JudgmentConditions
    (trajectory : SealedTrajectory)
    (observation : OutcomeObservation)
    (proposal : RevisionProposal)
    (judgment : RevisionSupportJudgment) : Prop where
  proposalTraceMatches : proposal.traceId = trajectory.traceId
  observationTraceMatches : observation.traceId = trajectory.traceId
  judgmentTraceMatches : judgment.traceId = trajectory.traceId
  judgmentObservationMatches : judgment.observationId = observation.observationId
  judgmentTargetMatches : judgment.target = proposal.target
  judgmentExpectedRevisionMatches :
    judgment.expectedRevision = proposal.expectedRevision
  judgmentCandidateRevisionMatches :
    judgment.candidateRevision = proposal.candidateRevision
  observationEvaluatorNotActor : observation.evaluator ≠ trajectory.actor
  observationEvaluatorNotProposer : observation.evaluator ≠ proposal.proposer
  observationOwnerNotActor :
    observation.responsibilityOwner ≠ trajectory.actor
  observationOwnerNotProposer :
    observation.responsibilityOwner ≠ proposal.proposer
  adjudicatorNotActor : judgment.adjudicator ≠ trajectory.actor
  adjudicatorNotProposer : judgment.adjudicator ≠ proposal.proposer
  judgmentOwnerNotActor : judgment.responsibilityOwner ≠ trajectory.actor
  judgmentOwnerNotProposer :
    judgment.responsibilityOwner ≠ proposal.proposer
  ownersSeparated :
    judgment.responsibilityOwner ≠ observation.responsibilityOwner
  evaluatorAndAdjudicatorSeparated :
    judgment.adjudicator ≠ observation.evaluator
  judgmentSupports : judgment.verdict = .supports

/-- Project the explicit credit judgment into the earlier abstract outcome. -/
def judgmentAsOutcomeReceipt
    (judgment : RevisionSupportJudgment) : OutcomeReceipt :=
  { traceId := judgment.traceId
    responsibilityOwner := judgment.responsibilityOwner
    evaluator := judgment.adjudicator
    verdict := judgment.verdict
    evidenceDigest := judgment.evidenceDigest }

/-- Learning from outcome evidence requires both the explicit judgment and `Learn`. -/
inductive LearnFromOutcomeEvidence
    (invariant : CanonicalState → RevisionProposal → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (package : OutcomeEvidencePackage)
    (proposal : RevisionProposal)
    (permit : PermitDecision)
    (next : CanonicalState) : Prop where
  | admit
      (judgment : RevisionSupportJudgment)
      (present : package.judgment = some judgment)
      (conditions : JudgmentConditions
        trajectory package.observation proposal judgment)
      (learned : Learn invariant state trajectory
        (judgmentAsOutcomeReceipt judgment) proposal permit next) :
      LearnFromOutcomeEvidence
        invariant state trajectory package proposal permit next

theorem supportJudgmentProjectsAbstractOutcome
    (conditions : JudgmentConditions trajectory observation proposal judgment) :
    (judgmentAsOutcomeReceipt judgment).traceId = trajectory.traceId ∧
    (judgmentAsOutcomeReceipt judgment).verdict = .supports ∧
    (judgmentAsOutcomeReceipt judgment).responsibilityOwner ≠ trajectory.actor ∧
    (judgmentAsOutcomeReceipt judgment).responsibilityOwner ≠ proposal.proposer ∧
    (judgmentAsOutcomeReceipt judgment).evaluator ≠ trajectory.actor ∧
    (judgmentAsOutcomeReceipt judgment).evaluator ≠ proposal.proposer := by
  exact ⟨conditions.judgmentTraceMatches,
    conditions.judgmentSupports,
    conditions.judgmentOwnerNotActor,
    conditions.judgmentOwnerNotProposer,
    conditions.adjudicatorNotActor,
    conditions.adjudicatorNotProposer⟩

theorem learnFromEvidenceRequiresExactJudgment
    (learned : LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next) :
    ∃ judgment,
      package.judgment = some judgment ∧
      JudgmentConditions trajectory package.observation proposal judgment := by
  cases learned with
  | admit judgment present conditions _ =>
      exact ⟨judgment, present, conditions⟩

theorem learnFromEvidenceRequiresUnderlyingLearn
    (learned : LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next) :
    ∃ judgment,
      package.judgment = some judgment ∧
      Learn invariant state trajectory
        (judgmentAsOutcomeReceipt judgment) proposal permit next := by
  cases learned with
  | admit judgment present _ underlying =>
      exact ⟨judgment, present, underlying⟩

theorem observationAloneCannotLearn
    (missing : package.judgment = none) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  cases learned with
  | admit _ present _ _ =>
      rw [missing] at present
      contradiction

theorem nonSupportingJudgmentCannotLearn
    (present : package.judgment = some judgment)
    (notSupports : judgment.verdict ≠ .supports) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  cases learned with
  | admit learnedJudgment learnedPresent conditions _ =>
      have sameJudgment : learnedJudgment = judgment := by
        apply Option.some.inj
        calc
          some learnedJudgment = package.judgment := learnedPresent.symm
          _ = some judgment := present
      have supports := conditions.judgmentSupports
      rw [sameJudgment] at supports
      exact notSupports supports

theorem actorOwnedObservationCannotLearn
    (actorOwned : package.observation.responsibilityOwner = trajectory.actor) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  rcases learnFromEvidenceRequiresExactJudgment learned with
    ⟨_judgment, _present, conditions⟩
  exact conditions.observationOwnerNotActor actorOwned

theorem proposerEvaluatedObservationCannotLearn
    (selfEvaluated : package.observation.evaluator = proposal.proposer) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  rcases learnFromEvidenceRequiresExactJudgment learned with
    ⟨_judgment, _present, conditions⟩
  exact conditions.observationEvaluatorNotProposer selfEvaluated

theorem collapsedOwnerRolesCannotLearn
    (present : package.judgment = some judgment)
    (collapsed :
      judgment.responsibilityOwner = package.observation.responsibilityOwner) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  rcases learnFromEvidenceRequiresExactJudgment learned with
    ⟨learnedJudgment, learnedPresent, conditions⟩
  have sameJudgment : learnedJudgment = judgment := by
    apply Option.some.inj
    calc
      some learnedJudgment = package.judgment := learnedPresent.symm
      _ = some judgment := present
  have separated := conditions.ownersSeparated
  rw [sameJudgment] at separated
  exact separated collapsed

theorem collapsedEvaluatorAdjudicatorCannotLearn
    (present : package.judgment = some judgment)
    (collapsed : judgment.adjudicator = package.observation.evaluator) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  rcases learnFromEvidenceRequiresExactJudgment learned with
    ⟨learnedJudgment, learnedPresent, conditions⟩
  have sameJudgment : learnedJudgment = judgment := by
    apply Option.some.inj
    calc
      some learnedJudgment = package.judgment := learnedPresent.symm
      _ = some judgment := present
  have separated := conditions.evaluatorAndAdjudicatorSeparated
  rw [sameJudgment] at separated
  exact separated collapsed

theorem judgmentCandidateMismatchCannotLearn
    (present : package.judgment = some judgment)
    (mismatch : judgment.candidateRevision ≠ proposal.candidateRevision) :
    ¬ LearnFromOutcomeEvidence
      invariant state trajectory package proposal permit next := by
  intro learned
  rcases learnFromEvidenceRequiresExactJudgment learned with
    ⟨learnedJudgment, learnedPresent, conditions⟩
  have sameJudgment : learnedJudgment = judgment := by
    apply Option.some.inj
    calc
      some learnedJudgment = package.judgment := learnedPresent.symm
      _ = some judgment := present
  have revisionMatches := conditions.judgmentCandidateRevisionMatches
  rw [sameJudgment] at revisionMatches
  exact mismatch revisionMatches

end HSWM.CanonicalLearning.OutcomeJudgment
