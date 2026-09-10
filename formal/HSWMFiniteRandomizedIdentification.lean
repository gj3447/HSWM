import Std

/-!
# Finite paired randomization identifies a finite potential-outcomes estimand

This is a bounded mathematical model only.  A `PairPotential` fixes each
unit's two potential scores before allocation.  Thus `observedOutcome` is the
consistency equation for this model, and contains no cross-pair or
cross-unit-dependent outcome input (the declared no-interference scope).

The two possible allocations receive equal weight.  We use denominator-cleared
integers: the sum of the two possible observed treated-minus-control contrasts
equals the sum of the two unit treatment effects.  No assertion here produces
randomness, seals an allocation, establishes outcome semantics, or implies a
positive effect.
-/

namespace HSWM.FiniteRandomizedIdentification

/-- The only two legal allocations in one two-unit block. -/
inductive Allocation where
  | firstTreated
  | secondTreated
deriving Repr, DecidableEq

/-- A fixed potential score for every unit and permitted treatment status. -/
structure PairPotential where
  firstControl : Int
  firstTreated : Int
  secondControl : Int
  secondTreated : Int
deriving Repr, DecidableEq

inductive Unit where
  | first
  | second
deriving Repr, DecidableEq

def treated (allocation : Allocation) (unit : Unit) : Bool :=
  match allocation, unit with
  | .firstTreated, .first => true
  | .secondTreated, .second => true
  | _, _ => false

/--
The observed score is selected from a fixed potential-outcome table.  This is
the model's consistency condition; no additional outcome function is supplied.
-/
def observedOutcome (p : PairPotential) (allocation : Allocation)
    (unit : Unit) : Int :=
  match unit, treated allocation unit with
  | .first, true => p.firstTreated
  | .first, false => p.firstControl
  | .second, true => p.secondTreated
  | .second, false => p.secondControl

theorem consistencyFirstTreated (p : PairPotential) :
    observedOutcome p .firstTreated .first = p.firstTreated := rfl

theorem consistencyFirstControl (p : PairPotential) :
    observedOutcome p .secondTreated .first = p.firstControl := rfl

theorem consistencySecondTreated (p : PairPotential) :
    observedOutcome p .secondTreated .second = p.secondTreated := rfl

theorem consistencySecondControl (p : PairPotential) :
    observedOutcome p .firstTreated .second = p.secondControl := rfl

/-- The observed treated-minus-control contrast in a legal allocation. -/
def observedDifference (p : PairPotential) : Allocation → Int
  | .firstTreated =>
      observedOutcome p .firstTreated .first -
        observedOutcome p .firstTreated .second
  | .secondTreated =>
      observedOutcome p .secondTreated .second -
        observedOutcome p .secondTreated .first

/-- Sum of the two individual treatment effects in the pair. -/
def pairEffectNumerator (p : PairPotential) : Int :=
  (p.firstTreated - p.firstControl) + (p.secondTreated - p.secondControl)

/-- Numerator of the uniform expectation over the two legal allocations. -/
def fairExpectationNumerator (p : PairPotential) : Int :=
  observedDifference p .firstTreated + observedDifference p .secondTreated

/--
Exact finite identification.  Dividing both sides by two gives the uniform
randomization expectation and the pair-average treatment effect when such a
division is interpreted in a field; retaining numerators avoids truncating
integer division.
-/
theorem fairPairedRandomizationIdentifiesPairEffect (p : PairPotential) :
    fairExpectationNumerator p = pairEffectNumerator p := by
  simp [fairExpectationNumerator, pairEffectNumerator, observedDifference,
    observedOutcome, treated]
  omega

/-- Aggregate contrast for one common legal allocation in every listed block. -/
def totalObservedDifference (pairs : List PairPotential)
    (allocation : Allocation) : Int :=
  (pairs.map (fun p => observedDifference p allocation)).sum

def totalPairEffectNumerator (pairs : List PairPotential) : Int :=
  (pairs.map pairEffectNumerator).sum

/--
The denominator-cleared uniform expectation identity extends by additivity to
any finite list of fixed two-unit blocks under one common fair allocation coin.
It does not enumerate independently randomized allocation vectors or assert
block independence. It is an algebraic identity, not a claim that a runtime
actually sampled either allocation. Divide by two for the sum of pair-average
effects; divide by twice the nonzero block count for the overall unit average.
-/
theorem fairPairedRandomizationIdentifiesTotalEffect
    (pairs : List PairPotential) :
    totalObservedDifference pairs .firstTreated +
        totalObservedDifference pairs .secondTreated =
      totalPairEffectNumerator pairs := by
  induction pairs with
  | nil => simp [totalObservedDifference, totalPairEffectNumerator]
  | cons p ps ih =>
      simp only [totalObservedDifference, List.map_cons, List.sum_cons,
        totalPairEffectNumerator]
      simp only [totalObservedDifference, totalPairEffectNumerator] at ih
      have hp := fairPairedRandomizationIdentifiesPairEffect p
      simp only [fairExpectationNumerator] at hp
      omega

/-- A deterministic, biased design that always treats the first unit. -/
def biasedFirstAllocation : Allocation := .firstTreated

/--
Selection can reverse the observed contrast despite a positive average effect:
the high-baseline second unit is always control under the biased design.
-/
def signConfoundedPair : PairPotential :=
  { firstControl := 0, firstTreated := 1, secondControl := 100,
    secondTreated := 101 }

theorem signConfoundedPairHasPositiveEffect :
    0 < pairEffectNumerator signConfoundedPair := by decide

theorem biasedAssignmentHasNegativeObservedContrast :
    observedDifference signConfoundedPair biasedFirstAllocation = -99 := by decide

theorem biasedAssignmentReversesSign :
    observedDifference signConfoundedPair biasedFirstAllocation < 0 ∧
      0 < pairEffectNumerator signConfoundedPair := by
  exact ⟨by decide, by decide⟩

/-- A null-effect pair can still have allocation-specific observed contrasts. -/
def nullEffectPair : PairPotential :=
  { firstControl := 0, firstTreated := 0, secondControl := 10,
    secondTreated := 10 }

theorem nullEffectHasNoPositiveEffect :
    pairEffectNumerator nullEffectPair = 0 ∧
      ¬ 0 < pairEffectNumerator nullEffectPair := by
  exact ⟨by decide, by decide⟩

theorem nullEffectFairExpectationIsZero :
    fairExpectationNumerator nullEffectPair = 0 := by decide

theorem nullEffectAssignmentsCanDiffer :
    observedDifference nullEffectPair .firstTreated = -10 ∧
      observedDifference nullEffectPair .secondTreated = 10 := by
  exact ⟨by decide, by decide⟩

end HSWM.FiniteRandomizedIdentification
