import Std

/-!
# Finite evidence updates for competing semantic relation candidates

This file checks a small arithmetic layer which an LLM-executed semantic
hypergraph could use *after* an external outcome has been recorded.  A
candidate may be an LLM-interpreted relation kernel, but this construction does
not formalize that interpretation or the LLM.  Natural-number masses are kept
unnormalized on purpose: the theorems are denominator-free identities.

It proves neither calibrated probabilities, log-loss optimality, causal
identification, truth of an LLM semantic interpretation, nor an HSWM runtime
refinement.  Positive likelihood factors are an explicit assumption, rather
than an assertion about any real observation process.
-/

namespace HSWM.SemanticEvidence

/-- An unnormalized nonnegative evidence mass for each candidate. -/
abbrev Mass (Hypothesis : Type) := Hypothesis → Nat

/-- A nonnegative evidence factor supplied for a candidate and an observation. -/
abbrev Likelihood (Hypothesis Evidence : Type) := Hypothesis → Evidence → Nat

/-- Multiplicative update; it does not normalize or assign a posterior meaning. -/
def update {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) (evidence : Evidence) : Mass Hypothesis :=
  fun hypothesis => mass hypothesis * likelihood hypothesis evidence

/-- Process a finite outcome sequence in its recorded order. -/
def run {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) : List Evidence → Mass Hypothesis
  | [] => mass
  | evidence :: tail => run (update mass likelihood evidence) likelihood tail

/-- Product of the same factors, collected before applying the initial mass. -/
def aggregateLikelihood {Hypothesis Evidence : Type}
    (likelihood : Likelihood Hypothesis Evidence) : List Evidence → Hypothesis → Nat
  | [] => fun _ => 1
  | evidence :: tail => fun hypothesis =>
      likelihood hypothesis evidence * aggregateLikelihood likelihood tail hypothesis

/-- Sequential update equals multiplication by the aggregate evidence factor. -/
theorem run_eq_aggregate {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) (evidence : List Evidence)
    (hypothesis : Hypothesis) :
    run mass likelihood evidence hypothesis =
      mass hypothesis * aggregateLikelihood likelihood evidence hypothesis := by
  induction evidence generalizing mass with
  | nil => simp [run, aggregateLikelihood]
  | cons observation tail inductionHypothesis =>
      simp only [run, aggregateLikelihood]
      rw [inductionHypothesis]
      simp [update, Nat.mul_assoc]

/-- A positive mass stays positive after a positive factor. -/
theorem update_positive {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) (evidence : Evidence)
    (hypothesis : Hypothesis) (massPositive : 0 < mass hypothesis)
    (factorPositive : 0 < likelihood hypothesis evidence) :
    0 < update mass likelihood evidence hypothesis := by
  exact Nat.mul_pos massPositive factorPositive

/-- Positivity survives any finite record whose factors are all positive. -/
theorem run_positive {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) (evidence : List Evidence)
    (hypothesis : Hypothesis) (massPositive : 0 < mass hypothesis)
    (factorsPositive : ∀ item ∈ evidence, 0 < likelihood hypothesis item) :
    0 < run mass likelihood evidence hypothesis := by
  induction evidence generalizing mass with
  | nil => simpa [run] using massPositive
  | cons observation tail inductionHypothesis =>
      apply inductionHypothesis (update mass likelihood observation)
      · exact update_positive mass likelihood observation hypothesis massPositive
          (factorsPositive observation (by simp))
      · intro later laterInTail
        exact factorsPositive later (by simp [laterInTail])

/-- Relative evidence dominance is comparison of the two unnormalized updates. -/
def dominates {Hypothesis : Type} (mass : Mass Hypothesis)
    (left right : Hypothesis) : Prop := mass left > mass right

/-- One observation changes relative dominance exactly by its two evidence factors. -/
theorem update_dominance_iff {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) (evidence : Evidence)
    (left right : Hypothesis) :
    dominates (update mass likelihood evidence) left right ↔
      mass left * likelihood left evidence > mass right * likelihood right evidence := by
  rfl

/-- The same denominator-free relation holds for a complete finite record. -/
theorem run_dominance_iff {Hypothesis Evidence : Type} (mass : Mass Hypothesis)
    (likelihood : Likelihood Hypothesis Evidence) (evidence : List Evidence)
    (left right : Hypothesis) :
    dominates (run mass likelihood evidence) left right ↔
      mass left * aggregateLikelihood likelihood evidence left >
        mass right * aggregateLikelihood likelihood evidence right := by
  simp only [dominates, run_eq_aggregate]

/--
Cross multiplication expresses unchanged pairwise odds without choosing a
normalizing denominator.  If a later layer normalizes all positive masses by
one common total, this is exactly the corresponding ratio invariant.
-/
def preservesRelativeOdds {Hypothesis : Type} (before after : Mass Hypothesis)
    (left right : Hypothesis) : Prop :=
  before left * after right = after left * before right

/-- An observation with the same factor for two candidates leaves their relative odds unchanged. -/
theorem equal_factor_preserves_relative_odds {Hypothesis Evidence : Type}
    (mass : Mass Hypothesis) (likelihood : Likelihood Hypothesis Evidence)
    (evidence : Evidence) (left right : Hypothesis)
    (sameFactor : likelihood left evidence = likelihood right evidence) :
    preservesRelativeOdds mass (update mass likelihood evidence) left right := by
  simp [preservesRelativeOdds, update, sameFactor, Nat.mul_comm,
    Nat.mul_left_comm]

/-- A common strictly positive factor preserves strict relative evidence ordering. -/
theorem equal_positive_factor_preserves_dominance_iff {Hypothesis Evidence : Type}
    (mass : Mass Hypothesis) (likelihood : Likelihood Hypothesis Evidence)
    (evidence : Evidence) (left right : Hypothesis)
    (sameFactor : likelihood left evidence = likelihood right evidence)
    (positiveFactor : 0 < likelihood right evidence) :
    dominates (update mass likelihood evidence) left right ↔ dominates mass left right := by
  change mass left * likelihood left evidence > mass right * likelihood right evidence ↔
    mass left > mass right
  rw [sameFactor]
  exact Nat.mul_lt_mul_right positiveFactor

/-- Two finite competing relation candidates.  The names carry no truth claim. -/
abbrev Candidate := Bool

/-- A bounded external record: an input at which an outcome was observed. -/
structure Observation where
  input : Bool
  outcome : Bool
deriving DecidableEq, Repr

/-- A semantic kernel is deliberately separate from its evidence mass. -/
abbrev SemanticKernel := Candidate → Bool → Bool

/-- Candidate `false` says every input has outcome true; `true` says outcome equals input. -/
def exampleKernel : SemanticKernel := fun candidate input =>
  if candidate then input else true

/-- A positive, smoothed exact-match factor for the concrete finite witness. -/
def exampleLikelihood : Likelihood Candidate Observation := fun candidate observation =>
  if exampleKernel candidate observation.input = observation.outcome then 2 else 1

def equalPrior : Mass Candidate := fun _ => 1

def falseOutcomeAtFalse : Observation := ⟨false, false⟩

/-- The recorded experiment observes only one of the two declared inputs. -/
def witnessObservedInputs : List Bool := [false]

theorem true_input_is_unobserved : true ∉ witnessObservedInputs := by decide

/-- One external outcome flips equal prior support toward the matching relation candidate. -/
theorem external_outcome_flips_preference_without_full_input_sweep :
    dominates (run equalPrior exampleLikelihood [falseOutcomeAtFalse]) true false ∧
    run equalPrior exampleLikelihood [falseOutcomeAtFalse] true = 2 ∧
    run equalPrior exampleLikelihood [falseOutcomeAtFalse] false = 1 ∧
    true ∉ witnessObservedInputs := by
  simp [dominates, run, update, equalPrior, exampleLikelihood, exampleKernel,
    falseOutcomeAtFalse, witnessObservedInputs]

/-- A joint count table; its entries are unnormalized finite masses. -/
abbrev JointMass := Bool → Bool → Nat

def independentJoint : JointMass := fun _ _ => 1

/-- Equal child marginals can instead arise from perfectly shared child values. -/
def sharedJoint : JointMass
  | false, false => 2
  | true, true => 2
  | _, _ => 0

def leftMarginal (joint : JointMass) (left : Bool) : Nat :=
  joint left false + joint left true

def rightMarginal (joint : JointMass) (right : Bool) : Nat :=
  joint false right + joint true right

def xorMass (joint : JointMass) : Nat := joint false true + joint true false

/-- Marginals agree, but the coupled joint law has a different XOR event mass. -/
theorem equal_marginals_do_not_determine_joint_xor :
    (∀ bit, leftMarginal independentJoint bit = leftMarginal sharedJoint bit) ∧
    (∀ bit, rightMarginal independentJoint bit = rightMarginal sharedJoint bit) ∧
    xorMass independentJoint = 2 ∧ xorMass sharedJoint = 0 := by
  decide

end HSWM.SemanticEvidence
