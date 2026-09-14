import Std

/-!
# A computed proposal guard with bounded corrupt external feedback

Unlike an assumed uniform score-error certificate, the score bound below is
derived from the actual mass of corrupted labels. Errors may be adversarially
correlated. The guard reads only observed labels, candidate predictions and a
declared corruption allowance. The truth function occurs only in theorem
statements and verification metrics; the guard cannot access it.

This is a deterministic finite evidence/population result. When observations
are only a sample, it is not a fresh-population guarantee or a method for
certifying the declared corruption allowance. Cost debit is expressed in the
same utility-mass units as correct predictions, not unspecified currency.
-/

namespace HSWM.NoisyFeedback

structure Observation (Input : Type) where
  input : Input
  label : Bool
  mass : Nat

def score (predictor : Input → Bool) : List (Observation Input) → Nat
  | [] => 0
  | obs :: rest => (if predictor obs.input = obs.label then obs.mass else 0) +
      score predictor rest

def trueScore (predictor truth : Input → Bool) : List (Observation Input) → Nat
  | [] => 0
  | obs :: rest => (if predictor obs.input = truth obs.input then obs.mass else 0) +
      trueScore predictor truth rest

def corruptionMass (truth : Input → Bool) : List (Observation Input) → Nat
  | [] => 0
  | obs :: rest => (if truth obs.input = obs.label then 0 else obs.mass) +
      corruptionMass truth rest

def totalMass : List (Observation Input) → Nat
  | [] => 0
  | obs :: rest => obs.mass + totalMass rest

/-- Both score errors are bounded by label corruption, without independence. -/
theorem score_error_bounded_by_actual_corruption (predictor truth : Input → Bool)
    (observations : List (Observation Input)) :
    score predictor observations ≤ trueScore predictor truth observations +
      corruptionMass truth observations ∧
    trueScore predictor truth observations ≤ score predictor observations +
      corruptionMass truth observations := by
  induction observations with
  | nil => simp [score, trueScore, corruptionMass]
  | cons obs rest ih =>
    rcases obs with ⟨input, label, mass⟩
    cases hp : predictor input <;> cases ht : truth input <;> cases label <;>
      simp_all [score, trueScore, corruptionMass] <;> omega

/-- The candidate object can be a complete semantic relation or composite graph. -/
def choose (forward : State → Input → Bool) (current candidate : State)
    (observations : List (Observation Input)) (allowance debit : Nat) : State :=
  if score (forward current) observations + 2 * allowance + debit <
      score (forward candidate) observations then candidate else current

/-- A passing observed guard yields actual utility-mass gain above its cost debit. -/
theorem guarded_true_gain (forward : State → Input → Bool)
    (current candidate : State) (truth : Input → Bool)
    (observations : List (Observation Input)) (allowance debit : Nat)
    (bounded : corruptionMass truth observations ≤ allowance)
    (passes : score (forward current) observations + 2 * allowance + debit <
      score (forward candidate) observations) :
    trueScore (forward current) truth observations + debit <
      trueScore (forward candidate) truth observations := by
  have hc := score_error_bounded_by_actual_corruption (forward current) truth observations
  have hn := score_error_bounded_by_actual_corruption (forward candidate) truth observations
  omega

/-- The actual computed guard cannot reduce true score within its declared scope. -/
theorem choose_nondecreases_true_score (forward : State → Input → Bool)
    (current candidate : State) (truth : Input → Bool)
    (observations : List (Observation Input)) (allowance debit : Nat)
    (bounded : corruptionMass truth observations ≤ allowance) :
    trueScore (forward current) truth observations ≤
      trueScore (forward (choose forward current candidate observations allowance debit))
        truth observations := by
  unfold choose
  split
  · have h := guarded_true_gain forward current candidate truth observations
      allowance debit bounded (by assumption)
    omega
  · exact Nat.le_refl _

/-- A sufficiently large true margin forces the executable guard to accept. -/
theorem large_true_margin_forces_acceptance (forward : State → Input → Bool)
    (current candidate : State) (truth : Input → Bool)
    (observations : List (Observation Input)) (allowance debit : Nat)
    (bounded : corruptionMass truth observations ≤ allowance)
    (margin : trueScore (forward current) truth observations + 4 * allowance + debit <
      trueScore (forward candidate) truth observations) :
    choose forward current candidate observations allowance debit = candidate := by
  have hc := score_error_bounded_by_actual_corruption (forward current) truth observations
  have hn := score_error_bounded_by_actual_corruption (forward candidate) truth observations
  have passes : score (forward current) observations + 2 * allowance + debit <
      score (forward candidate) observations := by omega
  simp [choose, passes]

/-- A proposal is rejected when its observed margin cannot cover noise and debit. -/
theorem insufficient_observed_margin_preserves_current
    (forward : State → Input → Bool) (current candidate : State)
    (observations : List (Observation Input)) (allowance debit : Nat)
    (margin : score (forward candidate) observations ≤
      score (forward current) observations + 2 * allowance + debit) :
    choose forward current candidate observations allowance debit = current := by
  simp [choose, Nat.not_lt.mpr margin]

def wrongObservation : List (Observation Unit) := [⟨(), false, 1⟩]

/-- Understating corruption can make the actual guard choose a worse rule. -/
theorem false_noise_allowance_can_accept_degradation :
    choose (fun value : Bool => fun _ : Unit => value) true false
      wrongObservation 0 0 = false ∧
    trueScore (fun _ : Unit => false) (fun _ => true) wrongObservation <
      trueScore (fun _ : Unit => true) (fun _ => true) wrongObservation ∧
    corruptionMass (fun _ : Unit => true) wrongObservation = 1 := by decide

end HSWM.NoisyFeedback
