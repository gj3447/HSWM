import Std

/-!
# HSWM canonical outcome-bound learning

This module formalizes a protective-belt relation for schema-relative canonical
learning.  It deliberately does not use the retired fixed H/W/A/F/Pi
decomposition.  A learning transition exists only when a pre-outcome sealed
trajectory, an independently owned and evaluated outcome, one exact revision
proposal, a current Permit, and a schema-relative invariant all agree.

The theorems are necessary-condition and frame results.  They do not prove that
an external outcome is true, that an implementation refines this model, or that
HSWM learning is causally effective.
-/

namespace HSWM.CanonicalLearning

/-- Fork-safe address of an atom lineage before selecting one immutable revision. -/
structure AtomAddress where
  schemaVersion : String
  lineageId : String
  atomUid : String
deriving Repr, DecidableEq

structure RevisionId where
  value : String
deriving Repr, DecidableEq

structure TraceId where
  value : String
deriving Repr, DecidableEq

structure Principal where
  value : String
deriving Repr, DecidableEq

structure EvidenceDigest where
  value : String
deriving Repr, DecidableEq

structure AuthorizationRef where
  value : String
deriving Repr, DecidableEq

structure Scope where
  value : String
deriving Repr, DecidableEq

/-- One current immutable atom version.  Owner is accountability, not authority. -/
structure AtomVersion where
  revisionId : RevisionId
  responsibilityOwner : Principal
  provenanceTrace : Option TraceId
deriving Repr, DecidableEq

/-- Current versions form a partial function; superseded bytes remain in history. -/
structure CanonicalState where
  current : AtomAddress → Option AtomVersion
  history : List (AtomAddress × AtomVersion)

def OwnerOf
    (state : CanonicalState) (address : AtomAddress) (owner : Principal) : Prop :=
  ∃ version,
    state.current address = some version ∧
    version.responsibilityOwner = owner

/-- A present current atom has exactly one schema-relative responsibility owner. -/
theorem currentAtomHasUniqueOwner
    (state : CanonicalState)
    (address : AtomAddress)
    (version : AtomVersion)
    (present : state.current address = some version) :
    ∃ owner, OwnerOf state address owner ∧
      ∀ other, OwnerOf state address other → other = owner := by
  refine ⟨version.responsibilityOwner, ⟨version, present, rfl⟩, ?_⟩
  intro other otherOwner
  rcases otherOwner with ⟨otherVersion, otherPresent, otherOwner⟩
  have sameVersion : otherVersion = version := by
    apply Option.some.inj
    calc
      some otherVersion = state.current address := otherPresent.symm
      _ = some version := present
  rw [sameVersion] at otherOwner
  exact otherOwner.symm

/-- A trajectory is sealed before an evaluator may observe its outcome. -/
structure SealedTrajectory where
  traceId : TraceId
  actor : Principal
  sealedBeforeOutcome : Bool
deriving Repr, DecidableEq

inductive OutcomeVerdict where
  | supports
  | rejects
  | indeterminate
deriving Repr, DecidableEq

/-- Outcome correctness responsibility and evaluation action remain distinct roles. -/
structure OutcomeReceipt where
  traceId : TraceId
  responsibilityOwner : Principal
  evaluator : Principal
  verdict : OutcomeVerdict
  evidenceDigest : EvidenceDigest
deriving Repr, DecidableEq

def OutcomeOwnedBy (outcome : OutcomeReceipt) (owner : Principal) : Prop :=
  outcome.responsibilityOwner = owner

theorem outcomeReceiptHasUniqueOwner (outcome : OutcomeReceipt) :
    ∃ owner, OutcomeOwnedBy outcome owner ∧
      ∀ other, OutcomeOwnedBy outcome other → other = owner := by
  exact ⟨outcome.responsibilityOwner, rfl, fun _ owned => owned.symm⟩

/-- Ordinary learning proposes a new version; it cannot propose an owner migration. -/
structure RevisionProposal where
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  proposer : Principal
  traceId : TraceId
  authorizationRef : AuthorizationRef
  scope : Scope
deriving Repr, DecidableEq

/-- Permit is a current typed decision, not a consequence of atom ownership. -/
structure PermitDecision where
  authorizationRef : AuthorizationRef
  authorizer : Principal
  target : AtomAddress
  traceId : TraceId
  scope : Scope
  allowed : Bool
  activeAtDecision : Bool
deriving Repr, DecidableEq

def revisedVersion
    (before : AtomVersion) (proposal : RevisionProposal) : AtomVersion :=
  { revisionId := proposal.candidateRevision
    responsibilityOwner := before.responsibilityOwner
    provenanceTrace := some proposal.traceId }

/-- Replace one current version and retain the previous immutable version. -/
def CanonicalState.revise
    (state : CanonicalState)
    (before : AtomVersion)
    (proposal : RevisionProposal) : CanonicalState :=
  { current := fun address =>
      if address = proposal.target then
        some (revisedVersion before proposal)
      else
        state.current address
    history := (proposal.target, before) :: state.history }

/-- All independent facts required before one canonical revision may be learned. -/
structure AdmissionConditions
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (outcome : OutcomeReceipt)
    (proposal : RevisionProposal)
    (permit : PermitDecision)
    (invariant : CanonicalState → RevisionProposal → Prop) where
  currentVersion : AtomVersion
  targetCurrent : state.current proposal.target = some currentVersion
  expectedRevisionMatches : proposal.expectedRevision = currentVersion.revisionId
  candidateRevisionIsNew : proposal.candidateRevision ≠ currentVersion.revisionId
  trajectoryWasSealed : trajectory.sealedBeforeOutcome = true
  proposalTraceMatches : proposal.traceId = trajectory.traceId
  outcomeTraceMatches : outcome.traceId = trajectory.traceId
  evaluatorNotActor : outcome.evaluator ≠ trajectory.actor
  evaluatorNotProposer : outcome.evaluator ≠ proposal.proposer
  outcomeOwnerNotActor : outcome.responsibilityOwner ≠ trajectory.actor
  outcomeOwnerNotProposer : outcome.responsibilityOwner ≠ proposal.proposer
  outcomeSupportsRevision : outcome.verdict = .supports
  permitAuthorizationMatches : permit.authorizationRef = proposal.authorizationRef
  permitTargetMatches : permit.target = proposal.target
  permitTraceMatches : permit.traceId = trajectory.traceId
  permitScopeMatches : permit.scope = proposal.scope
  permitAllows : permit.allowed = true
  permitIsActive : permit.activeAtDecision = true
  invariantHolds : invariant state proposal

/-- Relational learning law.  Absence of a constructor means no canonical change. -/
inductive Learn
    (invariant : CanonicalState → RevisionProposal → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (outcome : OutcomeReceipt)
    (proposal : RevisionProposal)
    (permit : PermitDecision) : CanonicalState → Prop where
  | admit (conditions : AdmissionConditions
      state trajectory outcome proposal permit invariant) :
      Learn invariant state trajectory outcome proposal permit
        (state.revise conditions.currentVersion proposal)

theorem learnRequiresIndependentEvaluator
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    outcome.evaluator ≠ trajectory.actor ∧
    outcome.evaluator ≠ proposal.proposer := by
  cases learned with
  | admit conditions =>
      exact ⟨conditions.evaluatorNotActor, conditions.evaluatorNotProposer⟩

theorem learnRequiresIndependentOutcomeOwner
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    outcome.responsibilityOwner ≠ trajectory.actor ∧
    outcome.responsibilityOwner ≠ proposal.proposer := by
  cases learned with
  | admit conditions =>
      exact ⟨conditions.outcomeOwnerNotActor, conditions.outcomeOwnerNotProposer⟩

theorem learnRequiresTraceBinding
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    trajectory.sealedBeforeOutcome = true ∧
    proposal.traceId = trajectory.traceId ∧
    outcome.traceId = trajectory.traceId ∧
    permit.traceId = trajectory.traceId := by
  cases learned with
  | admit conditions =>
      exact ⟨conditions.trajectoryWasSealed,
        conditions.proposalTraceMatches,
        conditions.outcomeTraceMatches,
        conditions.permitTraceMatches⟩

theorem learnRequiresSupportedOutcome
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    outcome.verdict = .supports := by
  cases learned with
  | admit conditions => exact conditions.outcomeSupportsRevision

theorem learnRequiresCurrentPermit
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    permit.authorizationRef = proposal.authorizationRef ∧
    permit.target = proposal.target ∧
    permit.scope = proposal.scope ∧
    permit.allowed = true ∧
    permit.activeAtDecision = true := by
  cases learned with
  | admit conditions =>
      exact ⟨conditions.permitAuthorizationMatches,
        conditions.permitTargetMatches,
        conditions.permitScopeMatches,
        conditions.permitAllows,
        conditions.permitIsActive⟩

theorem learnRequiresInvariant
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    invariant state proposal := by
  cases learned with
  | admit conditions => exact conditions.invariantHolds

theorem learnRequiresExactCurrentRevision
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    ∃ currentVersion,
      state.current proposal.target = some currentVersion ∧
      proposal.expectedRevision = currentVersion.revisionId ∧
      proposal.candidateRevision ≠ currentVersion.revisionId := by
  cases learned with
  | admit conditions =>
      exact ⟨conditions.currentVersion,
        conditions.targetCurrent,
        conditions.expectedRevisionMatches,
        conditions.candidateRevisionIsNew⟩

theorem learnPreservesTargetOwner
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    ∃ before after,
      state.current proposal.target = some before ∧
      next.current proposal.target = some after ∧
      after.responsibilityOwner = before.responsibilityOwner := by
  cases learned with
  | admit conditions =>
      refine ⟨conditions.currentVersion,
        revisedVersion conditions.currentVersion proposal,
        conditions.targetCurrent, ?_, rfl⟩
      simp [CanonicalState.revise]

theorem learnChangesOnlyTarget
    (learned : Learn invariant state trajectory outcome proposal permit next)
    (other : AtomAddress)
    (different : other ≠ proposal.target) :
    next.current other = state.current other := by
  cases learned with
  | admit conditions =>
      simp [CanonicalState.revise, different]

theorem learnArchivesPreviousVersion
    (learned : Learn invariant state trajectory outcome proposal permit next) :
    ∃ before,
      state.current proposal.target = some before ∧
      next.history = (proposal.target, before) :: state.history := by
  cases learned with
  | admit conditions =>
      exact ⟨conditions.currentVersion, conditions.targetCurrent, rfl⟩

theorem selfEvaluationCannotLearn
    (selfEvaluated : outcome.evaluator = trajectory.actor) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact (learnRequiresIndependentEvaluator learned).1 selfEvaluated

theorem proposerEvaluationCannotLearn
    (selfEvaluated : outcome.evaluator = proposal.proposer) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact (learnRequiresIndependentEvaluator learned).2 selfEvaluated

theorem actorOwnedOutcomeCannotLearn
    (selfOwned : outcome.responsibilityOwner = trajectory.actor) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact (learnRequiresIndependentOutcomeOwner learned).1 selfOwned

theorem proposerOwnedOutcomeCannotLearn
    (selfOwned : outcome.responsibilityOwner = proposal.proposer) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact (learnRequiresIndependentOutcomeOwner learned).2 selfOwned

theorem unsealedTrajectoryCannotLearn
    (unsealed : trajectory.sealedBeforeOutcome = false) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  have sealed := (learnRequiresTraceBinding learned).1
  simp [unsealed] at sealed

theorem proposalTraceMismatchCannotLearn
    (mismatch : proposal.traceId ≠ trajectory.traceId) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact mismatch (learnRequiresTraceBinding learned).2.1

theorem outcomeTraceMismatchCannotLearn
    (mismatch : outcome.traceId ≠ trajectory.traceId) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact mismatch (learnRequiresTraceBinding learned).2.2.1

theorem permitTraceMismatchCannotLearn
    (mismatch : permit.traceId ≠ trajectory.traceId) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact mismatch (learnRequiresTraceBinding learned).2.2.2

theorem unsupportedOutcomeCannotLearn
    (unsupported : outcome.verdict ≠ .supports) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact unsupported (learnRequiresSupportedOutcome learned)

theorem deniedPermitCannotLearn
    (denied : permit.allowed = false) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  have allowed := (learnRequiresCurrentPermit learned).2.2.2.1
  simp [denied] at allowed

theorem inactivePermitCannotLearn
    (inactive : permit.activeAtDecision = false) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  have active := (learnRequiresCurrentPermit learned).2.2.2.2
  simp [inactive] at active

theorem permitAuthorizationMismatchCannotLearn
    (mismatch : permit.authorizationRef ≠ proposal.authorizationRef) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact mismatch (learnRequiresCurrentPermit learned).1

theorem permitTargetMismatchCannotLearn
    (mismatch : permit.target ≠ proposal.target) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact mismatch (learnRequiresCurrentPermit learned).2.1

theorem permitScopeMismatchCannotLearn
    (mismatch : permit.scope ≠ proposal.scope) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact mismatch (learnRequiresCurrentPermit learned).2.2.1

theorem invariantFailureCannotLearn
    (failed : ¬ invariant state proposal) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  exact failed (learnRequiresInvariant learned)

theorem missingCurrentAtomCannotLearn
    (missing : state.current proposal.target = none) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  rcases learnRequiresExactCurrentRevision learned with
    ⟨currentVersion, present, _expected, _fresh⟩
  rw [missing] at present
  contradiction

/-- Even a principal occupying both roles cannot turn an explicit denial into Permit. -/
theorem ownerAuthorizerIdentityDoesNotOverrideDenial
    (currentVersion : AtomVersion)
    (_present : state.current proposal.target = some currentVersion)
    (_samePrincipal : currentVersion.responsibilityOwner = permit.authorizer)
    (denied : permit.allowed = false) :
    ¬ Learn invariant state trajectory outcome proposal permit next :=
  deniedPermitCannotLearn denied

theorem staleRevisionCannotLearn
    (currentVersion : AtomVersion)
    (present : state.current proposal.target = some currentVersion)
    (stale : proposal.expectedRevision ≠ currentVersion.revisionId) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  cases learned with
  | admit conditions =>
      have sameVersion : currentVersion = conditions.currentVersion := by
        apply Option.some.inj
        calc
          some currentVersion = state.current proposal.target := present.symm
          _ = some conditions.currentVersion := conditions.targetCurrent
      apply stale
      simpa [sameVersion] using conditions.expectedRevisionMatches

theorem reusedRevisionCannotLearn
    (currentVersion : AtomVersion)
    (present : state.current proposal.target = some currentVersion)
    (reused : proposal.candidateRevision = currentVersion.revisionId) :
    ¬ Learn invariant state trajectory outcome proposal permit next := by
  intro learned
  rcases learnRequiresExactCurrentRevision learned with
    ⟨learnedVersion, learnedPresent, _expected, fresh⟩
  have sameVersion : learnedVersion = currentVersion := by
    apply Option.some.inj
    calc
      some learnedVersion = state.current proposal.target := learnedPresent.symm
      _ = some currentVersion := present
  apply fresh
  simpa [sameVersion] using reused

end HSWM.CanonicalLearning
