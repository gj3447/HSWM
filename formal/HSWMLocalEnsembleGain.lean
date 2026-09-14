import Std

set_option linter.unusedSimpArgs false

/-!
# A finite local-ensemble gain and its correlation boundary

This file proves an exact statement about three binary local operators on one
common labelled input.  Their joint law is declared by an explicit product
weight over all eight Boolean triples; it is not inferred from an observed
model run.  Thus the result is a primitive finite mechanism, not a claim that
an HSWM, an LLM, or a real ensemble improves.

The positive theorem needs a common independent product law, positive good and
bad masses, and `bad < good`.  A perfectly correlated countermodel has the
same individual marginal correct mass but no majority gain.  A separate finite
cost witness records why accuracy alone is not a monotone budget objective.
-/

namespace HSWM.LocalEnsembleGain

/-- Three labelled local outputs for one common task/input. -/
structure Votes where
  first : Bool
  second : Bool
  third : Bool
deriving DecidableEq, Repr

def allVotes : List Votes :=
  [ ⟨false, false, false⟩, ⟨true, false, false⟩,
    ⟨false, true, false⟩, ⟨true, true, false⟩,
    ⟨false, false, true⟩, ⟨true, false, true⟩,
    ⟨false, true, true⟩, ⟨true, true, true⟩ ]

def correctCount (votes : Votes) : Nat :=
  (if votes.first then 1 else 0) +
  (if votes.second then 1 else 0) +
  (if votes.third then 1 else 0)

def majorityCorrect (votes : Votes) : Bool := decide (2 ≤ correctCount votes)

/-- Stable three-local-operator Boolean vote, evaluated on one common task input. -/
def majority (first second third : Bool) : Bool :=
  majorityCorrect ⟨first, second, third⟩

/-- Independent product mass: each correct local output has mass `good`, otherwise `bad`. -/
def iidWeight (good bad : Nat) (votes : Votes) : Nat :=
  (if votes.first then good else bad) *
  (if votes.second then good else bad) *
  (if votes.third then good else bad)

/-- Stable name for the declared task-conditional IID product mass. -/
abbrev productMass := iidWeight

def eventMass (weight : Votes → Nat) (event : Votes → Bool) : Nat :=
  (allVotes.filter event).foldl (fun total votes => total + weight votes) 0

/-- A finite exact score/mass of an event under one declared joint law. -/
abbrev scoreMass := eventMass

def iidMajorityMass (good bad : Nat) : Nat :=
  eventMass (iidWeight good bad) majorityCorrect

/-- One local operator's matched-denominator correct mass. -/
def iidSingleMass (good bad : Nat) : Nat := good * (good + bad) ^ 2

/-- Event that the first labelled local operator is correct. -/
def firstCorrect (votes : Votes) : Bool := votes.first

private theorem twice (value : Nat) : value + value = 2 * value := by omega

private theorem thrice (value : Nat) : value + value + value = 3 * value := by omega

/-- Enumerating the eight declared product-weight outcomes gives this exact majority mass. -/
theorem iid_majority_mass_enumerates_product_joint_law (good bad : Nat) :
    iidMajorityMass good bad = good ^ 3 + 3 * good ^ 2 * bad := by
  simp [iidMajorityMass, eventMass, allVotes, majorityCorrect, correctCount, iidWeight]
  rw [show good ^ 3 = good * good * good by simp [Nat.pow_succ],
    show good ^ 2 = good * good by simp [Nat.pow_succ],
    ← thrice (good * good)]
  simp only [Nat.add_mul]
  ac_rfl

/-- The common product-law total is the cube of one local operator's total mass. -/
theorem iid_total_mass_enumerates_product_joint_law (good bad : Nat) :
    eventMass (iidWeight good bad) (fun _ => true) = (good + bad) ^ 3 := by
  simp [eventMass, allVotes, iidWeight]
  simp [Nat.pow_succ, Nat.mul_add, Nat.add_mul, Nat.mul_assoc, Nat.mul_comm,
    Nat.mul_left_comm] <;> ac_rfl

private theorem baseline_expansion (good bad : Nat) :
    iidSingleMass good bad = good ^ 3 + 2 * (good ^ 2 * bad) + good * bad ^ 2 := by
  simp [iidSingleMass, Nat.pow_succ, Nat.mul_add, Nat.add_mul]
  rw [← twice (good * good * bad)]
  ac_rfl

/-- Enumerating the product law gives the matched-denominator first-voter mass. -/
theorem iid_first_correct_mass_enumerates_product_joint_law (good bad : Nat) :
    eventMass (iidWeight good bad) firstCorrect = iidSingleMass good bad := by
  simp [eventMass, allVotes, iidWeight, firstCorrect, iidSingleMass,
    Nat.pow_succ, Nat.mul_add, Nat.add_mul]
  ac_rfl

private theorem majority_expansion (good bad : Nat) :
    good ^ 3 + 3 * good ^ 2 * bad = good ^ 3 + 3 * (good ^ 2 * bad) := by
  simp [Nat.mul_assoc, Nat.mul_comm, Nat.mul_left_comm] <;> ac_rfl

/--
Under a declared IID finite pool with `good > bad > 0`, joint majority mass is
strictly greater than a single local operator's matched-denominator mass.
-/
theorem iid_majority_strictly_beats_single
    (good bad : Nat) (goodPositive : 0 < good) (badPositive : 0 < bad)
    (moreGood : bad < good) :
    iidSingleMass good bad < iidMajorityMass good bad := by
  have goodTimesBad_lt_goodSquared : good * bad < good * good :=
    (Nat.mul_lt_mul_left goodPositive).mpr moreGood
  have raw : (good * bad) * bad < (good * good) * bad :=
    (Nat.mul_lt_mul_right badPositive).mpr goodTimesBad_lt_goodSquared
  have smallerTerm : good * bad ^ 2 < good ^ 2 * bad := by
    calc
      good * bad ^ 2 = (good * bad) * bad := by
        simp [Nat.pow_succ, Nat.mul_assoc]
      _ < (good * good) * bad := raw
      _ = good ^ 2 * bad := by simp [Nat.pow_succ]
  have middle : 2 * (good ^ 2 * bad) + good * bad ^ 2 <
      2 * (good ^ 2 * bad) + good ^ 2 * bad :=
    Nat.add_lt_add_left smallerTerm _
  rw [iid_majority_mass_enumerates_product_joint_law, baseline_expansion,
    majority_expansion]
  calc
    good ^ 3 + 2 * (good ^ 2 * bad) + good * bad ^ 2 =
        good ^ 3 + (2 * (good ^ 2 * bad) + good * bad ^ 2) := by omega
    _ < good ^ 3 + (2 * (good ^ 2 * bad) + good ^ 2 * bad) :=
      Nat.add_lt_add_left middle _
    _ = good ^ 3 + 3 * (good ^ 2 * bad) := by omega

/--
Perfect correlation: either all three are correct together (mass `good`) or
all are wrong together (mass `bad`).  Its unnormalized mass has a different
denominator from IID; the cross-product theorem below states equality of the
normalized single-voter marginal, without introducing division.
-/
def correlatedWeight (good bad : Nat) : Votes → Nat
  | ⟨true, true, true⟩ => good
  | ⟨false, false, false⟩ => bad
  | _ => 0

theorem perfectly_correlated_marginal_and_majority_have_same_correct_mass
    (good bad : Nat) :
    eventMass (correlatedWeight good bad) firstCorrect = good ∧
    eventMass (correlatedWeight good bad) majorityCorrect = good := by
  simp [eventMass, allVotes, correlatedWeight, firstCorrect, majorityCorrect, correctCount]

theorem perfectly_correlated_total_mass (good bad : Nat) :
    eventMass (correlatedWeight good bad) (fun _ => true) = good + bad := by
  simp [eventMass, allVotes, correlatedWeight]
  omega

/-- A positive finite pool gives a nonzero denominator for the normalized comparison. -/
theorem correlated_total_positive (good bad : Nat) (goodPositive : 0 < good) :
    0 < eventMass (correlatedWeight good bad) (fun _ => true) := by
  rw [perfectly_correlated_total_mass]
  omega

/--
IID and perfect correlation have equal *normalized* single-voter marginal
correctness.  The equality is denominator-cleared: each numerator is multiplied
by the other joint law's total mass.  Their majority events still differ.
-/
theorem iid_and_correlated_single_marginal_cross_product (good bad : Nat) :
    eventMass (iidWeight good bad) firstCorrect *
        eventMass (correlatedWeight good bad) (fun _ => true) =
      eventMass (correlatedWeight good bad) firstCorrect *
        eventMass (iidWeight good bad) (fun _ => true) := by
  rw [iid_first_correct_mass_enumerates_product_joint_law,
    perfectly_correlated_total_mass,
    (perfectly_correlated_marginal_and_majority_have_same_correct_mass good bad).1,
    iid_total_mass_enumerates_product_joint_law]
  simp [iidSingleMass, Nat.pow_succ, Nat.mul_assoc, Nat.mul_comm, Nat.mul_left_comm]

/-- A finite net-value witness: extra correct mass can still lose after extra cost. -/
def budgetValue (correctMass cost : Nat) : Int := (correctMass : Int) - cost

theorem accuracy_is_not_monotone_in_budget_value :
    budgetValue 2 3 < budgetValue 1 0 := by decide

end HSWM.LocalEnsembleGain
