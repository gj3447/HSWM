import HSWMAtomicAdmissionConsistency

/-!
# Atomic admission does not entail efficacy

Countermodels separate the structural admission relation from behavior change,
external truth, causal support, principal authentication and trusted-head
semantics.  They preserve the target while preventing an unsupported claim
promotion from formal admission to scientific efficacy.
-/

namespace HSWM.CanonicalLearning.AtomicAdmission.NonEntailment

open OutcomeJudgment
open Consistency

structure Probe where
  value : String
deriving Repr, DecidableEq

structure Response where
  value : String
deriving Repr, DecidableEq

abbrev BehaviorSemantics := CanonicalState → Probe → Response

def BehaviorChanged
    (behavior : BehaviorSemantics)
    (before after : CanonicalState) : Prop :=
  ∃ probe, behavior before probe ≠ behavior after probe

/-- One interpretation allowed by the structural signature ignores state. -/
def constantBehavior : BehaviorSemantics :=
  fun _state _probe => ⟨"response/constant"⟩

theorem constantBehaviorHasNoChange :
    ¬ BehaviorChanged constantBehavior initialState nextState := by
  intro changed
  rcases changed with ⟨probe, differs⟩
  exact differs rfl

theorem atomicAdmissionCanExistWithoutBehaviorChange :
    AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
      trajectory outcomePackage proposal permit certificate commitWitness
      currentHead nextState nextHead ∧
    ¬ BehaviorChanged constantBehavior initialState nextState := by
  exact ⟨exampleAtomicAdmission, constantBehaviorHasNoChange⟩

abbrev ExternalTruthInterpretation := EvidenceDigest → Prop

def JudgmentEvidenceIsExternallyTrue
    (truth : ExternalTruthInterpretation)
    (support : RevisionSupportJudgment) : Prop :=
  truth support.evidenceDigest

/-- A countermodel interpretation; not a claim about the real evidence. -/
def noEvidenceIsExternallyTrue : ExternalTruthInterpretation :=
  fun _evidence => False

theorem exampleSupportVerdictIsPresent : judgment.verdict = .supports := rfl

theorem supportVerdictDoesNotForceExternalTruth :
    judgment.verdict = .supports ∧
    ¬ JudgmentEvidenceIsExternallyTrue noEvidenceIsExternallyTrue judgment := by
  exact ⟨rfl, by simp [JudgmentEvidenceIsExternallyTrue,
    noEvidenceIsExternallyTrue]⟩

theorem atomicAdmissionCanExistWithoutExternalTruth :
    AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
      trajectory outcomePackage proposal permit certificate commitWitness
      currentHead nextState nextHead ∧
    ¬ JudgmentEvidenceIsExternallyTrue
      noEvidenceIsExternallyTrue judgment := by
  exact ⟨exampleAtomicAdmission,
    (supportVerdictDoesNotForceExternalTruth).2⟩

abbrev CausalSupportInterpretation :=
  RevisionSupportJudgment → RevisionProposal → Prop

def CausallySupports
    (causal : CausalSupportInterpretation)
    (support : RevisionSupportJudgment)
    (candidate : RevisionProposal) : Prop :=
  causal support candidate

/-- Structural support syntax does not select a causal interpretation. -/
def noJudgmentIsCausal : CausalSupportInterpretation :=
  fun _support _candidate => False

theorem supportVerdictDoesNotForceCausalSupport :
    judgment.verdict = .supports ∧
    ¬ CausallySupports noJudgmentIsCausal judgment proposal := by
  exact ⟨rfl, by simp [CausallySupports, noJudgmentIsCausal]⟩

theorem atomicAdmissionCanExistWithoutCausalSupport :
    AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
      trajectory outcomePackage proposal permit certificate commitWitness
      currentHead nextState nextHead ∧
    ¬ CausallySupports noJudgmentIsCausal judgment proposal := by
  exact ⟨exampleAtomicAdmission,
    (supportVerdictDoesNotForceCausalSupport).2⟩

abbrev AuthenticationInterpretation := Principal → Prop

def RequiredRolesAuthenticated
    (authenticated : AuthenticationInterpretation) : Prop :=
  authenticated actor ∧
  authenticated proposer ∧
  authenticated evaluator ∧
  authenticated adjudicator ∧
  authenticated authorizer

/-- Distinct symbolic addresses do not authenticate their bearers. -/
def noPrincipalAuthenticated : AuthenticationInterpretation :=
  fun _principal => False

theorem declaredRoleSeparationDoesNotForceAuthentication :
    ¬ RequiredRolesAuthenticated noPrincipalAuthenticated := by
  simp [RequiredRolesAuthenticated, noPrincipalAuthenticated]

theorem atomicAdmissionCanExistWithoutAuthenticatedRoles :
    AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
      trajectory outcomePackage proposal permit certificate commitWitness
      currentHead nextState nextHead ∧
    ¬ RequiredRolesAuthenticated noPrincipalAuthenticated := by
  exact ⟨exampleAtomicAdmission,
    declaredRoleSeparationDoesNotForceAuthentication⟩

abbrev HeadTrustInterpretation := HeadSnapshot → Prop

def noHeadTrusted : HeadTrustInterpretation := fun _head => False

theorem headBindingDoesNotForceHeadTrust :
    ¬ noHeadTrusted currentHead := by
  simp [noHeadTrusted]

theorem atomicAdmissionCanExistWithoutTrustedHead :
    AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
      trajectory outcomePackage proposal permit certificate commitWitness
      currentHead nextState nextHead ∧
    ¬ noHeadTrusted currentHead := by
  exact ⟨exampleAtomicAdmission, headBindingDoesNotForceHeadTrust⟩

/-- Every external bridge premise that atomic admission intentionally omits. -/
def IntegratedEfficacyBridge
    (behavior : BehaviorSemantics)
    (truth : ExternalTruthInterpretation)
    (causal : CausalSupportInterpretation)
    (authenticated : AuthenticationInterpretation)
    (trustedHead : HeadTrustInterpretation)
    (before after : CanonicalState)
    (support : RevisionSupportJudgment)
    (candidate : RevisionProposal)
    (head : HeadSnapshot) : Prop :=
  BehaviorChanged behavior before after ∧
  JudgmentEvidenceIsExternallyTrue truth support ∧
  CausallySupports causal support candidate ∧
  RequiredRolesAuthenticated authenticated ∧
  trustedHead head

theorem exampleIntegratedEfficacyBridgeFails :
    ¬ IntegratedEfficacyBridge constantBehavior noEvidenceIsExternallyTrue
      noJudgmentIsCausal noPrincipalAuthenticated noHeadTrusted
      initialState nextState judgment proposal currentHead := by
  intro bridge
  exact constantBehaviorHasNoChange bridge.1

theorem atomicAdmissionDoesNotEntailIntegratedEfficacy :
    AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
      trajectory outcomePackage proposal permit certificate commitWitness
      currentHead nextState nextHead ∧
    ¬ IntegratedEfficacyBridge constantBehavior noEvidenceIsExternallyTrue
      noJudgmentIsCausal noPrincipalAuthenticated noHeadTrusted
      initialState nextState judgment proposal currentHead := by
  exact ⟨exampleAtomicAdmission, exampleIntegratedEfficacyBridgeFails⟩

end HSWM.CanonicalLearning.AtomicAdmission.NonEntailment
