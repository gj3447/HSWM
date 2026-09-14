import HSWMConstructiveRelationSynthesis
import HSWMNoisyFeedback
import HSWMCorrelatedReliability
import HSWMSemanticWeightDefinition
import HSWMHypergraphRepresentation
import HSWMRecursiveLearningComposition

/-!
# Generated semantic relation, correlated inputs, noisy assessment and cost

One bounded construction connects an actual grammar-generated relation to the
existing SemanticWeight local-read definition and a corrupt-feedback guard.
The nonconstant target is ternary conjunction. The initial graph reads one
feature; the target program is absent from the initial primitive pool. Four
separating examples drive synthesis. A separately declared weighted population
contains every Boolean input with mass two and one unit of corrupt label mass.

The computed guard accepts the generated graph even after charging one unit of
incremental cost. A unit is explicitly 1/16 of the reward for a correct answer;
it is not a measured token/currency cost. The same population induces correlated
primitive errors on which ordinary majority ties the baseline. Thus this model's
gain comes from the generated relation's meaning, not simply more votes.

All operators are exact reference functions. No model, grounding oracle,
estimated population distribution or durable runtime is certified here.
-/

namespace HSWM.GeneratedLearningBridge

open HSWM.ConstructiveRelationSynthesis

abbrev Graph := HSWM.HypergraphRepresentation.NaryRelation Expr Role (Fin 3) 3
abbrev Context := HSWM.SemanticWeightDefinition.RoleContext Role (Fin 3) Input

def graph (program : Expr) : Graph :=
  { payload := program, member := (relation program).member }

theorem graph_endpoint (program : Expr) (slot : Fin 3) :
    ((graph program).member slot).2 = slot := by
  have choices : slot = 0 ∨ slot = 1 ∨ slot = 2 := by omega
  rcases choices with h | h | h <;> subst slot <;> rfl

/-- A bounded relation read, containing its program and three addressed signals. -/
def weight : HSWM.SemanticWeightDefinition.SemanticWeight
    Graph (Expr × Input) Role (Fin 3) Input Bool :=
  HSWM.SemanticWeightDefinition.SemanticWeight.fromLlm
    (fun g context => (g.payload, fun slot => context.context (g.member slot).2))
    (fun read _ => read) (fun read => eval read.1 read.2)

def forward (g : Graph) (input : Input) : Bool :=
  HSWM.SemanticWeightDefinition.behavior weight g
    { incidences := (List.finRange 3).map fun slot =>
        { role := (g.member slot).1, participant := (g.member slot).2 }
      context := input }

theorem graph_forward_is_generated_semantics (program : Expr) (input : Input) :
    forward (graph program) input = eval program input := by
  change eval program (fun slot => input ((graph program).member slot).2) = _
  simp [graph_endpoint]

/-- Reference local binary neural operation; no pretrained-LLM fidelity is assumed. -/
def localAnd (left right : Bool) : Bool := left && right

def localExecution : Expr → Input → Bool
  | .input slot, input => input slot
  | .and left right, input => localAnd (localExecution left input) (localExecution right input)

theorem recursive_local_execution_matches_relation (program : Expr) (input : Input) :
    localExecution program input = forward (graph program) input := by
  rw [graph_forward_is_generated_semantics]
  induction program with
  | input slot => rfl
  | and left right ihLeft ihRight => simp [localExecution, localAnd, eval, ihLeft, ihRight]

def baseline : Graph := graph (.input 0)

/-- This executable update consumes observations and synthesizes a new candidate program. -/
def propose (current : Graph) (observations : List Example) : Graph :=
  match synthesize 2 observations with
  | none => current
  | some program => graph program

def candidate : Graph := propose baseline separatingExamples

theorem computed_candidate_is_conjunction : candidate = graph conjunction := by rfl

/-- A fixed, nonconstant reference world, used only for evaluation theorems. -/
def world (input : Input) : Bool := input 0 && (input 1 && input 2)

theorem generated_candidate_correct_for_every_input (input : Input) :
    forward candidate input = world input := by
  rw [computed_candidate_is_conjunction, graph_forward_is_generated_semantics]
  rfl

def bits (a b c : Bool) : Input := fun slot =>
  if slot = 0 then a else if slot = 1 then b else c

theorem reference_world_is_nonconstant :
    world (bits false false false) = false ∧ world (bits true true true) = true := by decide

/-- A weighted census, not nine IID observations. The split 000 entries total two. -/
def assessmentPopulation : List (HSWM.NoisyFeedback.Observation Input) :=
  [⟨bits false false false, true, 1⟩,
   ⟨bits false false false, false, 1⟩,
   ⟨bits false false true, false, 2⟩,
   ⟨bits false true false, false, 2⟩,
   ⟨bits false true true, false, 2⟩,
   ⟨bits true false false, false, 2⟩,
   ⟨bits true false true, false, 2⟩,
   ⟨bits true true false, false, 2⟩,
   ⟨bits true true true, true, 2⟩]

def signature (input : Input) : HSWM.LocalEnsembleGain.Votes :=
  ⟨input 0, input 1, input 2⟩

def inputMass (votes : HSWM.LocalEnsembleGain.Votes) : Nat :=
  (assessmentPopulation.filter (fun obs => signature obs.input == votes)).foldl
    (fun mass obs => mass + obs.mass) 0

theorem every_boolean_triple_has_mass_two (votes : HSWM.LocalEnsembleGain.Votes) :
    inputMass votes = 2 := by
  rcases votes with ⟨a, b, c⟩
  cases a <;> cases b <;> cases c <;> decide

/-- Common normalization and the exact nonzero corruption allowance. -/
theorem assessmentPopulation_mass_and_noise :
    HSWM.NoisyFeedback.totalMass assessmentPopulation = 16 ∧
    0 < HSWM.NoisyFeedback.totalMass assessmentPopulation ∧
    HSWM.NoisyFeedback.corruptionMass world assessmentPopulation = 1 := by decide

theorem observed_and_true_scores :
    HSWM.NoisyFeedback.score (forward baseline) assessmentPopulation = 9 ∧
    HSWM.NoisyFeedback.score (forward candidate) assessmentPopulation = 15 ∧
    HSWM.NoisyFeedback.trueScore (forward baseline) world assessmentPopulation = 10 ∧
    HSWM.NoisyFeedback.trueScore (forward candidate) world assessmentPopulation = 16 := by decide

/-- One debit unit is 1/16 of a correct-answer reward on this declared population. -/
def incrementalDebit : Nat := 1

def selected : Graph :=
  HSWM.NoisyFeedback.choose forward baseline candidate assessmentPopulation 1 incrementalDebit

theorem computed_noisy_cost_guard_accepts_generated_graph : selected = candidate := by
  unfold selected HSWM.NoisyFeedback.choose
  rw [observed_and_true_scores.1, observed_and_true_scores.2.1]
  rfl

/-- The independently proved noisy-feedback rule establishes strict net gain. -/
theorem generated_noisy_cost_update_has_true_gain :
    HSWM.NoisyFeedback.trueScore (forward baseline) world assessmentPopulation + incrementalDebit <
      HSWM.NoisyFeedback.trueScore (forward selected) world assessmentPopulation := by
  rw [computed_noisy_cost_guard_accepts_generated_graph]
  apply HSWM.NoisyFeedback.guarded_true_gain forward baseline candidate world
    assessmentPopulation 1 incrementalDebit
  · rw [assessmentPopulation_mass_and_noise.2.2]
    exact Nat.le_refl 1
  · rw [observed_and_true_scores.1, observed_and_true_scores.2.1]
    decide

/-- The same world's primitive correctness law may be correlated. -/
def primitiveCorrectness (input : Input) : HSWM.LocalEnsembleGain.Votes :=
  ⟨decide (input 0 = world input), decide (input 1 = world input),
   decide (input 2 = world input)⟩

def jointMass (votes : HSWM.LocalEnsembleGain.Votes) : Nat :=
  (assessmentPopulation.filter (fun obs => primitiveCorrectness obs.input == votes)).foldl
    (fun mass obs => mass + obs.mass) 0

theorem same_population_majority_corrective_destructive_balance :
    HSWM.CorrelatedReliability.outputMass jointMass HSWM.CorrelatedReliability.correctiveEvent = 2 ∧
    HSWM.CorrelatedReliability.outputMass jointMass HSWM.CorrelatedReliability.destructiveEvent = 2 ∧
    HSWM.CorrelatedReliability.outputMass jointMass HSWM.LocalEnsembleGain.firstCorrect = 10 := by decide

/-- On exactly this population, adding majority votes yields no gain. -/
theorem majority_ties_baseline_on_same_world :
    HSWM.CorrelatedReliability.outputMass jointMass HSWM.LocalEnsembleGain.majorityCorrect =
      HSWM.NoisyFeedback.trueScore (forward baseline) world assessmentPopulation := by
  have balance := HSWM.CorrelatedReliability.majority_first_balance jointMass
  rcases same_population_majority_corrective_destructive_balance with ⟨corrective, destructive, first⟩
  rw [corrective, destructive, first] at balance
  rw [observed_and_true_scores.2.2.1]
  omega

/-- Compile the generated program to actual recursively executing local cells. -/
def toTree : Expr → HSWM.RecursiveLearningComposition.Candidate Input Bool
  | .input slot => .leaf ⟨fun input => input slot, 0, []⟩
  | .and left right => .branch (toTree left) (toTree right)

theorem generated_tree_executes_same_relation (program : Expr) (input : Input) :
    HSWM.RecursiveLearningComposition.recursiveAnd (toTree program) input =
      forward (graph program) input := by
  rw [graph_forward_is_generated_semantics]
  induction program with
  | input slot => rfl
  | and left right ihLeft ihRight =>
    simp [toTree, HSWM.RecursiveLearningComposition.recursiveAnd, eval, ihLeft, ihRight]

/-- Semantic candidate filtering before or after recursive compilation is identical. -/
theorem generated_tree_learning_commutes (programs : List Expr)
    (observation : HSWM.RecursiveLearningComposition.Observation Input Bool) :
    (programs.filter (fun program =>
      decide (forward (graph program) observation.input = observation.outcome))).map toTree =
      HSWM.RecursiveLearningComposition.andLearn (programs.map toTree) observation := by
  induction programs with
  | nil => rfl
  | cons program rest ih =>
    simp only [List.filter_cons, List.map_cons, HSWM.RecursiveLearningComposition.andLearn]
    by_cases agrees : forward (graph program) observation.input = observation.outcome
    · simpa [HSWM.RecursiveLearningComposition.andLearn, generated_tree_executes_same_relation, agrees] using
        congrArg (List.cons (toTree program)) ih
    · simpa [HSWM.RecursiveLearningComposition.andLearn, generated_tree_executes_same_relation, agrees] using ih

/-- The generated candidate's performance survives recursive local execution. -/
theorem synthesized_recursive_tree_correct (input : Input) :
    HSWM.RecursiveLearningComposition.recursiveAnd (toTree candidate.payload) input =
      world input := by
  rw [computed_candidate_is_conjunction]
  exact (generated_tree_executes_same_relation conjunction input).trans (by
    rw [graph_forward_is_generated_semantics]
    rfl)

/-- The noise/cost guard also makes the same decision on compiled recursive graphs. -/
theorem noisy_selection_preserved_by_recursive_execution :
    HSWM.NoisyFeedback.choose HSWM.RecursiveLearningComposition.recursiveAnd
      (toTree baseline.payload) (toTree candidate.payload) assessmentPopulation 1 incrementalDebit =
      toTree candidate.payload := by
  unfold HSWM.NoisyFeedback.choose
  have base : HSWM.RecursiveLearningComposition.recursiveAnd (toTree baseline.payload) =
      forward baseline := by
    funext input
    exact generated_tree_executes_same_relation (.input 0) input
  have proposed : HSWM.RecursiveLearningComposition.recursiveAnd (toTree candidate.payload) =
      forward candidate := by
    funext input
    rw [computed_candidate_is_conjunction]
    exact generated_tree_executes_same_relation conjunction input
  rw [base, proposed, observed_and_true_scores.1, observed_and_true_scores.2.1]
  rfl

end HSWM.GeneratedLearningBridge
