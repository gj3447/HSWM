import HSWMLocalEnsembleGain

/-!
# Finite correlated reliability boundaries

This module studies a *declared*, task-conditional finite joint mass for three
local Boolean outputs.  It does not estimate a population law from observations.
For an arbitrary joint mass, majority's advantage over the first local output is
exactly the mass of the corrective `(false,true,true)` event minus the mass of
the destructive `(true,false,false)` event.  Thus correlation may help, do
nothing, or hurt; independence is not assumed here.

`actualCorrect` is an output-level correctness indicator for the same finite
outcomes.  Its disagreement mass is enumerated from the joint law, rather than
being postulated as a score error.  The robustness theorem is conditional on a
stated finite forecast mass and a bound on that enumerated disagreement.  It is
not an empirical calibration or a population guarantee.
-/

namespace HSWM.CorrelatedReliability

open HSWM.LocalEnsembleGain

/-- An arbitrary nonnegative finite joint mass for the three local outputs. -/
abbrev JointMass := Votes → Nat

/-- Correctness event of a specified output rule on the common labelled task. -/
def outputMass (joint : JointMass) (correct : Votes → Bool) : Nat :=
  eventMass joint correct

/-- The event in which the two other voters repair the first voter's error. -/
def correctiveEvent (votes : Votes) : Bool :=
  !votes.first && votes.second && votes.third

/-- The event in which the first voter is right but the two others overturn it. -/
def destructiveEvent (votes : Votes) : Bool :=
  votes.first && !votes.second && !votes.third

/-- Exact majority-versus-first balance for every declared finite joint mass. -/
theorem majority_first_balance (joint : JointMass) :
    outputMass joint majorityCorrect + outputMass joint destructiveEvent =
      outputMass joint firstCorrect + outputMass joint correctiveEvent := by
  simp [outputMass, eventMass, allVotes, majorityCorrect, correctCount,
    firstCorrect, correctiveEvent, destructiveEvent]
  omega

/--
Majority strictly improves on the first local output exactly when the declared
corrective event has more mass than the declared destructive event.
-/
theorem majority_strict_gain_iff (joint : JointMass) :
    outputMass joint firstCorrect < outputMass joint majorityCorrect ↔
      outputMass joint destructiveEvent < outputMass joint correctiveEvent := by
  have balance := majority_first_balance joint
  omega

/-- A concrete correlated, non-product witness with a strict majority gain. -/
def correlatedImprovingMass : JointMass
  | ⟨false, true, true⟩ => 3
  | ⟨true, false, false⟩ => 1
  | _ => 0

theorem correlated_improving_mass_events :
    outputMass correlatedImprovingMass correctiveEvent = 3 ∧
      outputMass correlatedImprovingMass destructiveEvent = 1 ∧
      outputMass correlatedImprovingMass firstCorrect = 1 ∧
      outputMass correlatedImprovingMass majorityCorrect = 3 := by
  simp [outputMass, eventMass, allVotes, correlatedImprovingMass,
    correctiveEvent, destructiveEvent, firstCorrect, majorityCorrect, correctCount]

theorem correlated_improving_mass_has_strict_gain :
    outputMass correlatedImprovingMass firstCorrect <
      outputMass correlatedImprovingMass majorityCorrect := by
  rw [majority_strict_gain_iff]
  simp [outputMass, eventMass, allVotes, correlatedImprovingMass,
    correctiveEvent, destructiveEvent]

/-- A concrete correlation pattern where majority loses to the first local output. -/
def correlatedHarmingMass : JointMass
  | ⟨false, true, true⟩ => 1
  | ⟨true, false, false⟩ => 2
  | _ => 0

theorem correlated_harming_mass_has_negative_gain :
    outputMass correlatedHarmingMass majorityCorrect <
      outputMass correlatedHarmingMass firstCorrect := by
  simp [outputMass, eventMass, allVotes, correlatedHarmingMass,
    firstCorrect, majorityCorrect, correctCount]

/-- Perfect correlation preserves the first marginal and gives no majority gain. -/
theorem perfectly_correlated_has_no_gain (good bad : Nat) :
    outputMass (correlatedWeight good bad) firstCorrect =
      outputMass (correlatedWeight good bad) majorityCorrect := by
  have masses := perfectly_correlated_marginal_and_majority_have_same_correct_mass good bad
  exact masses.1.trans masses.2.symm

/-- Per-outcome disagreement between an ideal and an actual output rule. -/
def disagreementEvent (ideal actual : Votes → Bool) (votes : Votes) : Bool :=
  ideal votes != actual votes

/-- The disagreement mass is itself an enumerated event of the declared joint law. -/
def disagreementMass (joint : JointMass) (ideal actual : Votes → Bool) : Nat :=
  outputMass joint (disagreementEvent ideal actual)

/-- Direct recursive event mass, used only to prove a pointwise finite-list bound. -/
private def listEventMass (joint : JointMass) (event : Votes → Bool) : List Votes → Nat
  | [] => 0
  | votes :: rest => (if event votes then joint votes else 0) + listEventMass joint event rest

private theorem list_event_mass_not_far_below
    (joint : JointMass) (ideal actual : Votes → Bool) (votes : List Votes) :
    listEventMass joint ideal votes ≤
      listEventMass joint actual votes +
        listEventMass joint (disagreementEvent ideal actual) votes := by
  induction votes with
  | nil => simp [listEventMass]
  | cons vote rest inductionHypothesis =>
    cases hi : ideal vote <;> cases ha : actual vote <;>
      simp [listEventMass, disagreementEvent, hi, ha, inductionHypothesis] <;> omega

private theorem filtered_fold_from
    (joint : JointMass) (event : Votes → Bool) (votes : List Votes) (total : Nat) :
    (votes.filter event).foldl (fun running vote => running + joint vote) total =
      total + listEventMass joint event votes := by
  induction votes generalizing total with
  | nil => simp [listEventMass]
  | cons vote rest inductionHypothesis =>
    cases h : event vote <;>
      simp [List.filter, h, listEventMass, inductionHypothesis, Nat.add_assoc]

private theorem event_mass_eq_list_event_mass
    (joint : JointMass) (event : Votes → Bool) :
    eventMass joint event = listEventMass joint event allVotes := by
  change (allVotes.filter event).foldl (fun total votes => total + joint votes) 0 =
    listEventMass joint event allVotes
  simpa using filtered_fold_from joint event allVotes 0

/--
Changing an ideal output rule on mass at most `delta` can reduce its correct mass
by at most `delta`.  The proof enumerates all eight outcomes and makes no
population or calibration assumption.
-/
theorem actual_mass_not_far_below_ideal
    (joint : JointMass) (actual : Votes → Bool) (delta : Nat)
    (errorBound : disagreementMass joint majorityCorrect actual ≤ delta) :
    outputMass joint majorityCorrect ≤ outputMass joint actual + delta := by
  have localBound := list_event_mass_not_far_below joint majorityCorrect actual allVotes
  rw [← event_mass_eq_list_event_mass joint majorityCorrect,
    ← event_mass_eq_list_event_mass joint actual,
    ← event_mass_eq_list_event_mass joint (disagreementEvent majorityCorrect actual)] at localBound
  change eventMass joint (disagreementEvent majorityCorrect actual) ≤ delta at errorBound
  simpa [outputMass, disagreementMass] using Nat.le_trans localBound
    (Nat.add_le_add_left errorBound _)

/--
If corrective mass exceeds destructive mass plus the enumerated-output error
budget, the actual rule still strictly beats the first local output.
-/
theorem actual_gain_survives_disagreement
    (joint : JointMass) (actual : Votes → Bool) (delta : Nat)
    (errorBound : disagreementMass joint majorityCorrect actual ≤ delta)
    (margin : outputMass joint destructiveEvent + delta <
      outputMass joint correctiveEvent) :
    outputMass joint firstCorrect < outputMass joint actual := by
  have actualBound := actual_mass_not_far_below_ideal joint actual delta errorBound
  have balance := majority_first_balance joint
  omega

/-- A common-denominator integer net score: both candidates use mass units of one joint law. -/
def netMass (correctMass incrementalCost : Nat) : Int :=
  (correctMass : Int) - incrementalCost

/--
With an integer-scaled incremental cost in the same common mass denominator,
the robust accuracy margin also pays for that cost.  It does not compare
unrelated raw costs or assert a universal budget objective.
-/
theorem actual_gain_survives_disagreement_and_cost
    (joint : JointMass) (actual : Votes → Bool) (delta incrementalCost : Nat)
    (errorBound : disagreementMass joint majorityCorrect actual ≤ delta)
    (margin : outputMass joint destructiveEvent + delta + incrementalCost <
      outputMass joint correctiveEvent) :
    netMass (outputMass joint firstCorrect) 0 <
      netMass (outputMass joint actual) incrementalCost := by
  have actualBound := actual_mass_not_far_below_ideal joint actual delta errorBound
  have balance := majority_first_balance joint
  dsimp [netMass]
  omega

end HSWM.CorrelatedReliability
