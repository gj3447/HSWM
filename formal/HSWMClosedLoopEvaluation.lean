import HSWMIntegratedClosedLoop

/-!
# Disjoint finite evaluation and an indistinguishable-world limitation

The four evaluation inputs below occur in neither synthesis nor the guarded
training population used by the integrated model. They form a constructed
finite split, not a sampled future-world guarantee. A second world agrees on
all training inputs and reverses the evaluation gain, making the remaining
world-identification assumption explicit.
-/

namespace HSWM.ClosedLoopEvaluation

open HSWM.ConstructiveRelationSynthesis
open HSWM.GeneratedLearningBridge
open HSWM.NoisyFeedback
open HSWM.IntegratedClosedLoop

/-- Exactly the complementary four inputs; two declared reward units per input. -/
def evaluationPopulation : List (Observation Input) :=
  [⟨bits false false false, false, 2⟩,
   ⟨bits false false true, false, 2⟩,
   ⟨bits false true false, false, 2⟩,
   ⟨bits true false false, false, 2⟩]

/-- The fixed synthesis region contains at least two true input bits. -/
def trainingRegion (input : Input) : Bool :=
  (input 0 && input 1) || (input 0 && input 2) || (input 1 && input 2)

theorem evaluation_outside_training_region (observation : Observation Input)
    (member : observation ∈ evaluationPopulation) :
    trainingRegion observation.input = false := by
  simp only [evaluationPopulation, List.mem_cons, List.not_mem_nil, or_false] at member
  rcases member with rfl | rfl | rfl | rfl <;> decide

theorem synthesis_inside_training_region (sample : Example)
    (member : sample ∈ separatingExamples) :
    trainingRegion sample.input = true := by
  simp only [separatingExamples, List.mem_cons, List.not_mem_nil, or_false] at member
  rcases member with rfl | rfl | rfl | rfl <;> decide

theorem evaluation_inputs_disjoint_from_synthesis (observation : Observation Input)
    (member : observation ∈ evaluationPopulation) (sample : Example)
    (used : sample ∈ separatingExamples) : observation.input ≠ sample.input := by
  intro same
  have outside := evaluation_outside_training_region observation member
  have inside := synthesis_inside_training_region sample used
  rw [same, inside] at outside
  contradiction

theorem evaluation_mass_and_reference_scores :
    totalMass evaluationPopulation = 8 ∧
    trueScore (forward baseline) world evaluationPopulation = 6 ∧
    trueScore (forward candidate) world evaluationPopulation = 8 := by decide

/-- This alternative agrees on the observed region and differs outside it. -/
def alternativeWorld (input : Input) : Bool :=
  if trainingRegion input then world input else input 0

theorem alternative_agrees_on_training_region (input : Input)
    (inside : trainingRegion input = true) : alternativeWorld input = world input := by
  simp [alternativeWorld, inside]

theorem alternative_agrees_on_synthesis (sample : Example)
    (member : sample ∈ separatingExamples) :
    alternativeWorld sample.input = world sample.input :=
  alternative_agrees_on_training_region sample.input (synthesis_inside_training_region sample member)

theorem alternative_world_is_distinct :
    alternativeWorld (bits true false false) ≠ world (bits true false false) := by decide

/-- Exact reference execution alone does not identify the unseen world. -/
theorem alternative_reverses_evaluation_scores :
    trueScore (forward baseline) alternativeWorld evaluationPopulation = 8 ∧
    trueScore (forward candidate) alternativeWorld evaluationPopulation = 6 := by decide

theorem assessment_inside_training_region (observation : Observation Input)
    (member : observation ∈ trainingPopulation) :
    trainingRegion observation.input = true := by
  simp only [trainingPopulation, List.mem_cons, List.not_mem_nil, or_false] at member
  rcases member with rfl | rfl | rfl | rfl | rfl <;> decide

theorem evaluation_inputs_disjoint_from_guard (observation : Observation Input)
    (member : observation ∈ evaluationPopulation) (used : Observation Input)
    (usedMember : used ∈ trainingPopulation) : observation.input ≠ used.input := by
  intro same
  have outside := evaluation_outside_training_region observation member
  have inside := assessment_inside_training_region used usedMember
  rw [same, inside] at outside
  contradiction

theorem alternative_agrees_on_every_guard_input (observation : Observation Input)
    (member : observation ∈ trainingPopulation) :
    alternativeWorld observation.input = world observation.input :=
  alternative_agrees_on_training_region observation.input
    (assessment_inside_training_region observation member)

theorem identical_training_corruption_in_both_worlds :
    totalMass trainingPopulation = 8 ∧
    corruptionMass world trainingPopulation = 1 ∧
    corruptionMass alternativeWorld trainingPopulation = 1 := by decide

theorem canonical_training_scores :
    score initialPrediction trainingPopulation = 3 ∧
    score revisedPrediction trainingPopulation = 7 ∧
    trueScore initialPrediction world trainingPopulation = 4 ∧
    trueScore revisedPrediction world trainingPopulation = 8 := by
  rw [initialPrediction_eq_forward_baseline, revisedPrediction_eq_forward_candidate]
  decide

/-- These are the actual canonical Step readouts, not a separate predictor. -/
theorem canonical_execution_evaluation_scores :
    trueScore initialPrediction world evaluationPopulation = 6 ∧
    trueScore revisedPrediction world evaluationPopulation = 8 := by
  rw [initialPrediction_eq_forward_baseline, revisedPrediction_eq_forward_candidate]
  exact evaluation_mass_and_reference_scores.2

/-- One same-state witness links bound commit to the disjoint evaluation gain. -/
theorem constructed_canonical_loop_has_disjoint_gain :
    ∃ updated : HSWM.LLMSemanticGraph.GraphState,
      integratedLearn initialState receipt boundOutcome = some updated ∧
      trueScore (canonicalPredict initialState) world evaluationPopulation = 6 ∧
      trueScore (canonicalPredict updated) world evaluationPopulation = 8 ∧
      trueScore (canonicalPredict initialState) world evaluationPopulation + incrementalDebit <
        trueScore (canonicalPredict updated) world evaluationPopulation := by
  refine ⟨successor, bound_outcome_commits_through_llm_learn, ?_⟩
  have scores := canonical_execution_evaluation_scores
  change trueScore initialPrediction world evaluationPopulation = 6 ∧
    trueScore revisedPrediction world evaluationPopulation = 8 ∧
    trueScore initialPrediction world evaluationPopulation + incrementalDebit <
      trueScore revisedPrediction world evaluationPopulation
  exact ⟨scores.1, scores.2, by rw [scores.1, scores.2]; decide⟩

/-- The identical computed canonical successor loses on an observationally indistinguishable world. -/
theorem same_canonical_update_can_harm_unseen_world :
    trueScore initialPrediction alternativeWorld evaluationPopulation = 8 ∧
    trueScore revisedPrediction alternativeWorld evaluationPopulation = 6 := by
  rw [initialPrediction_eq_forward_baseline, revisedPrediction_eq_forward_candidate]
  exact alternative_reverses_evaluation_scores

/-- Training-region agreement alone cannot entail nondecreasing unseen-world accuracy. -/
theorem training_agreement_is_insufficient_for_universal_improvement :
    ¬ ∀ truth : Input → Bool,
      (∀ input, trainingRegion input = true → truth input = world input) →
      trueScore initialPrediction truth evaluationPopulation ≤
        trueScore revisedPrediction truth evaluationPopulation := by
  intro universal
  have wrong := universal alternativeWorld alternative_agrees_on_training_region
  rw [same_canonical_update_can_harm_unseen_world.1,
    same_canonical_update_can_harm_unseen_world.2] at wrong
  omega

end HSWM.ClosedLoopEvaluation
