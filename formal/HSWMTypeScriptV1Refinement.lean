import HSWMCanonicalLearning

/-!
# HSWM TypeScript v1 refinement obstruction

The checked-in TypeScript v1 boundary exposes exact local-head eligibility that
is explicitly not canonical Permit and outcome evidence that is explicitly not
causal credit.  This module proves that its honest semantic profile cannot
supply a refinement witness for `CanonicalLearning.Learn`.

This is a negative cross-language specification result.  It is not a formal
semantics of TypeScript and does not prove runtime execution correct.
-/

namespace HSWM.CanonicalLearning.TypeScriptV1

inductive RuntimePermitStrength where
  | canonicalPermit
  | localEligibilityNotCanonicalPermit
deriving Repr, DecidableEq

inductive RuntimeOutcomeStrength where
  | supportsRevision
  | representedNotCausalCredit
deriving Repr, DecidableEq

/-- Obligations a runtime projection must supply before refining `Learn`. -/
structure RuntimeRefinementProfile where
  exactOneTargetCurrentRevision : Bool
  preOutcomeTraceBinding : Bool
  evaluatorRoleSeparated : Bool
  outcomeResponsibilityOwnerPresent : Bool
  outcomeStrength : RuntimeOutcomeStrength
  permitStrength : RuntimePermitStrength
  invariantWitnessPresent : Bool
  atomicAdmissionPresent : Bool
  trustedCurrentHeadWitness : Bool
deriving Repr, DecidableEq

/-- Necessary runtime evidence for a positive refinement into the Lean law. -/
def ReadyForCanonicalLearn (profile : RuntimeRefinementProfile) : Prop :=
  profile.exactOneTargetCurrentRevision = true ∧
  profile.preOutcomeTraceBinding = true ∧
  profile.evaluatorRoleSeparated = true ∧
  profile.outcomeResponsibilityOwnerPresent = true ∧
  profile.outcomeStrength = .supportsRevision ∧
  profile.permitStrength = .canonicalPermit ∧
  profile.invariantWitnessPresent = true ∧
  profile.atomicAdmissionPresent = true ∧
  profile.trustedCurrentHeadWitness = true

/-- Exact honest capability ceiling of the checked-in TypeScript v1 contracts. -/
def currentV1Profile : RuntimeRefinementProfile :=
  { exactOneTargetCurrentRevision := false
    preOutcomeTraceBinding := true
    evaluatorRoleSeparated := false
    outcomeResponsibilityOwnerPresent := false
    outcomeStrength := .representedNotCausalCredit
    permitStrength := .localEligibilityNotCanonicalPermit
    invariantWitnessPresent := false
    atomicAdmissionPresent := false
    trustedCurrentHeadWitness := false }

theorem localEligibilityCannotSupplyCanonicalPermit
    (profile : RuntimeRefinementProfile)
    (localOnly :
      profile.permitStrength = .localEligibilityNotCanonicalPermit) :
    ¬ ReadyForCanonicalLearn profile := by
  intro ready
  have canonical : profile.permitStrength = .canonicalPermit :=
    ready.2.2.2.2.2.1
  rw [localOnly] at canonical
  contradiction

theorem representedOutcomeCannotSupplyRevisionSupport
    (profile : RuntimeRefinementProfile)
    (representedOnly :
      profile.outcomeStrength = .representedNotCausalCredit) :
    ¬ ReadyForCanonicalLearn profile := by
  intro ready
  have supports : profile.outcomeStrength = .supportsRevision :=
    ready.2.2.2.2.1
  rw [representedOnly] at supports
  contradiction

theorem missingOutcomeOwnerObstructsRefinement
    (profile : RuntimeRefinementProfile)
    (missing : profile.outcomeResponsibilityOwnerPresent = false) :
    ¬ ReadyForCanonicalLearn profile := by
  intro ready
  have present := ready.2.2.2.1
  simp [missing] at present

theorem missingInvariantObstructsRefinement
    (profile : RuntimeRefinementProfile)
    (missing : profile.invariantWitnessPresent = false) :
    ¬ ReadyForCanonicalLearn profile := by
  intro ready
  have present := ready.2.2.2.2.2.2.1
  simp [missing] at present

theorem missingAtomicAdmissionObstructsRefinement
    (profile : RuntimeRefinementProfile)
    (missing : profile.atomicAdmissionPresent = false) :
    ¬ ReadyForCanonicalLearn profile := by
  intro ready
  have present := ready.2.2.2.2.2.2.2.1
  simp [missing] at present

theorem missingTrustedCurrentHeadObstructsRefinement
    (profile : RuntimeRefinementProfile)
    (missing : profile.trustedCurrentHeadWitness = false) :
    ¬ ReadyForCanonicalLearn profile := by
  intro ready
  have present := ready.2.2.2.2.2.2.2.2
  simp [missing] at present

theorem currentV1NotReadyForCanonicalLearn :
    ¬ ReadyForCanonicalLearn currentV1Profile := by
  exact localEligibilityCannotSupplyCanonicalPermit currentV1Profile rfl

/-- A sound positive bridge must carry both runtime readiness and a Lean step. -/
structure RefinesLearn
    (profile : RuntimeRefinementProfile)
    (invariant : CanonicalState → RevisionProposal → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (outcome : OutcomeReceipt)
    (proposal : RevisionProposal)
    (permit : PermitDecision)
    (next : CanonicalState) : Prop where
  runtimeReady : ReadyForCanonicalLearn profile
  leanTransition : Learn invariant state trajectory outcome proposal permit next

/-- No checked-in TypeScript v1 artifact can honestly witness the Lean relation. -/
theorem currentV1CannotRefineLearn :
    ¬ RefinesLearn currentV1Profile
      invariant state trajectory outcome proposal permit next := by
  intro refinement
  exact currentV1NotReadyForCanonicalLearn refinement.runtimeReady

end HSWM.CanonicalLearning.TypeScriptV1
