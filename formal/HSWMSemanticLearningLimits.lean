import Std

/-!
# Deterministic limits of fixed-query semantic learning

This file proves two narrow negative facts used by the HSWM constructive
realizability program.

* A learner whose only input is the responses to a fixed finite query list
  cannot be exact at an unqueried point for both the all-false target and the
  target that differs only at that point.
* An identity `Learn` transition preserves every readout for every outcome.

The first theorem is a deterministic fixed-query obstruction.  It is not an
adaptive-query lower bound, a stochastic lower bound, or an impossibility
theorem for HSWM.  The second theorem is only a countermodel for a learning
claim: it does not assign cognitive status to any state machine.
-/

namespace HSWM.SemanticLearningLimits

universe u v w

variable {X : Type u} [DecidableEq X]

/-- A deterministic Boolean target relation over a query domain. -/
abbrev Target (X : Type u) := X -> Bool

/-- The complete response transcript for a fixed, non-adaptive query list. -/
def transcript (target : Target X) (queries : List X) : List (X × Bool) :=
  queries.map (fun query => (query, target query))

/-- A target relation with no positive coordinates. -/
def zero : Target X := fun _ => false

/-- The target relation which differs from `zero` only at the declared point. -/
def spike (point : X) : Target X := fun query =>
  if query = point then true else false

omit [DecidableEq X] in
theorem zero_at (point : X) : zero point = false := rfl

theorem spike_at (point : X) : spike point point = true := by
  simp [spike]

/--
If `point` was not queried, the fixed transcript cannot distinguish `zero`
from `spike point`.
-/
theorem transcript_zero_eq_spike_of_not_mem
    (queries : List X) (point : X) (missing : point ∉ queries) :
    transcript zero queries = transcript (spike point) queries := by
  unfold transcript
  apply List.map_congr_left
  intro query queryMem
  have queryNe : query ≠ point := by
    intro queryEq
    apply missing
    simpa [queryEq] using queryMem
  simp [zero, spike, queryNe]

/--
No decoder seeing only that fixed transcript can be exact at `point` for both
indistinguishable target relations.
-/
theorem no_fixed_transcript_decoder_exact_both
    (learner : List (X × Bool) -> X -> Bool)
    (queries : List X) (point : X) (missing : point ∉ queries) :
    ¬ (learner (transcript zero queries) point = zero point ∧
       learner (transcript (spike point) queries) point = spike point point) := by
  intro exactBoth
  have sameTranscript :
      transcript zero queries = transcript (spike point) queries :=
    transcript_zero_eq_spike_of_not_mem queries point missing
  have samePrediction :
      learner (transcript zero queries) point =
        learner (transcript (spike point) queries) point := by
    rw [sameTranscript]
  have falseEqualsTrue : false = true := by
    calc
      false = zero point := (zero_at point).symm
      _ = learner (transcript zero queries) point := exactBoth.1.symm
      _ = learner (transcript (spike point) queries) point := samePrediction
      _ = spike point point := exactBoth.2
      _ = true := spike_at point
  cases falseEqualsTrue

/-- A frozen learning transition keeps the same state for every outcome. -/
def frozenLearn (State : Type v) (Outcome : Type w) : State -> Outcome -> State :=
  fun state _ => state

theorem frozenLearn_state_unchanged
    {State : Type v} {Outcome : Type w} (state : State) (outcome : Outcome) :
    frozenLearn State Outcome state outcome = state := rfl

/-- Every declared readout remains unchanged after an identity learning transition. -/
theorem frozenLearn_preserves_readout
    {State : Type v} {Outcome : Type w} {Readout : Type u}
    (readout : State -> Readout) (state : State) (outcome : Outcome) :
    readout (frozenLearn State Outcome state outcome) = readout state := rfl

end HSWM.SemanticLearningLimits
