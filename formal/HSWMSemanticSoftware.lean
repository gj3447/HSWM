import HSWMGeneratedLearningBridge

/-!
# A finite executable meaning of the user's AI-as-software philosophy

The graph payload is executable syntax, while an internal operator receives
only the payload and its addressed local signals. A computed outcome-driven
revision changes the next execution and has the previously proved strict gain.
The reference operator is an exact program interpreter, not a pretrained LLM.
The last transfer theorem exposes the additional operator-fidelity premise.
This construction is a finite software instance, not all of CHU or HSWM.
-/

namespace HSWM.SemanticSoftware

open HSWM.ConstructiveRelationSynthesis
open HSWM.GeneratedLearningBridge

/-- A fixed deterministic realization at the chosen local read boundary. -/
abbrev LocalOperator := Expr → Input → Bool

/-- The only arguments sent to the operator are program syntax and local signals. -/
def execute (operator : LocalOperator) (state : Graph) (input : Input) : Bool :=
  operator state.payload (fun slot => input ((state.member slot).2))

/-- The executable reference consists of recursively composed binary AND cells. -/
def referenceOperator : LocalOperator := localExecution

theorem addressed_graph_execution (operator : LocalOperator) (program : Expr)
    (input : Input) :
    execute operator (graph program) input = operator program input := by
  unfold execute graph
  have endpoints : (fun slot => input (((relation program).member slot).2)) = input := by
    funext slot
    have h := graph_endpoint program slot
    change ((relation program).member slot).2 = slot at h
    rw [h]
  rw [endpoints]

/-- Execution agrees with the existing Semantic Weight local-read construction. -/
theorem reference_executes_semantic_weight (program : Expr) (input : Input) :
    execute referenceOperator (graph program) input = forward (graph program) input := by
  rw [addressed_graph_execution]
  exact recursive_local_execution_matches_relation program input

/-- Complete candidates are software values; the choice reads observations, not truth. -/
def revise (operator : LocalOperator) (current proposed : Graph)
    (observations : List (HSWM.NoisyFeedback.Observation Input))
    (allowance debit : Nat) : Graph :=
  HSWM.NoisyFeedback.choose (execute operator) current proposed observations allowance debit

/-- The new semantic program is actually synthesized from the four stated outcomes. -/
def computedRevision : Graph :=
  revise referenceOperator baseline (propose baseline separatingExamples)
    assessmentPopulation 1 incrementalDebit

theorem reference_candidate_execution (input : Input) :
    execute referenceOperator candidate input = forward candidate input := by
  rw [computed_candidate_is_conjunction]
  exact reference_executes_semantic_weight conjunction input

/-- The executable choice, rather than a premise of success, computes the candidate. -/
theorem computed_revision_selects_generated_program : computedRevision = candidate := by
  have old : execute referenceOperator baseline = forward baseline := by
    funext input
    exact reference_executes_semantic_weight (.input 0) input
  have proposed : execute referenceOperator candidate = forward candidate := by
    funext input
    exact reference_candidate_execution input
  change HSWM.NoisyFeedback.choose (execute referenceOperator) baseline candidate
    assessmentPopulation 1 incrementalDebit = candidate
  unfold HSWM.NoisyFeedback.choose
  rw [old, proposed, observed_and_true_scores.1, observed_and_true_scores.2.1]
  rfl

/-- Stored graph revision changes this reference program's next output. -/
theorem stored_revision_changes_next_execution :
    execute referenceOperator baseline (bits true false false) = true ∧
    execute referenceOperator computedRevision (bits true false false) = false := by
  rw [computed_revision_selects_generated_program, computed_candidate_is_conjunction]
  constructor <;> decide

/-- Strict net gain for the same program execution and the declared weighted population. -/
theorem outcome_revised_local_program_has_strict_gain :
    HSWM.NoisyFeedback.trueScore (execute referenceOperator baseline)
      world assessmentPopulation + incrementalDebit <
    HSWM.NoisyFeedback.trueScore (execute referenceOperator computedRevision)
      world assessmentPopulation := by
  have old : execute referenceOperator baseline = forward baseline := by
    funext input
    exact reference_executes_semantic_weight (.input 0) input
  have updated : execute referenceOperator computedRevision = forward selected := by
    funext input
    rw [computed_revision_selects_generated_program,
      computed_noisy_cost_guard_accepts_generated_graph]
    exact reference_candidate_execution input
  rw [old, updated]
  exact generated_noisy_cost_update_has_true_gain

/-- The proof's exact reference gain is 10/16 to 16/16, with a debit of 1/16. -/
theorem reference_software_scores :
    HSWM.NoisyFeedback.trueScore (execute referenceOperator baseline)
      world assessmentPopulation = 10 ∧
    HSWM.NoisyFeedback.trueScore (execute referenceOperator computedRevision)
      world assessmentPopulation = 16 := by
  rw [computed_revision_selects_generated_program, computed_candidate_is_conjunction]
  constructor <;> decide

/-- An inert decoder proves that storing a different program alone is insufficient. -/
theorem ignored_program_cannot_change_execution (left right : Graph) (input : Input) :
    execute (fun _ _ => false) left input = execute (fun _ _ => false) right input := rfl

/-- The sufficient real-operator obligation is explicit; it is not proved here. -/
def Faithful (operator : LocalOperator) : Prop :=
  ∀ program input, operator program input = localExecution program input

theorem faithful_operator_preserves_execution (operator : LocalOperator)
    (faithful : Faithful operator) (state : Graph) (input : Input) :
    execute operator state input = execute referenceOperator state input :=
  faithful state.payload (fun slot => input ((state.member slot).2))

/-- Exact local fidelity transports the computed update and its gain to that operator. -/
theorem faithful_operator_inherits_computed_gain (operator : LocalOperator)
    (faithful : Faithful operator) :
    HSWM.NoisyFeedback.trueScore (execute operator baseline) world assessmentPopulation +
      incrementalDebit <
    HSWM.NoisyFeedback.trueScore
      (execute operator (revise operator baseline (propose baseline separatingExamples)
        assessmentPopulation 1 incrementalDebit)) world assessmentPopulation := by
  have execution : execute operator = execute referenceOperator := by
    funext state input
    exact faithful_operator_preserves_execution operator faithful state input
  simpa only [revise, execution, computedRevision] using
    outcome_revised_local_program_has_strict_gain

/-!
A tiny executable envelope witnesses the intended *scope inclusion*: a
semantic-graph machine and a non-neural world simulator can share a software
interface. This two-variant model is not a definition or realization of all CHU.
-/

inductive BoundedEnvelope where
  | semantic (state : Graph)
  | flipWorld (state : Bool)

/-- Both variants have explicit computations; the world variant does not call the operator. -/
def envelopeStep (operator : LocalOperator) (state : BoundedEnvelope) (input : Input) :
    Bool × BoundedEnvelope :=
  match state with
  | .semantic graphState => (execute operator graphState input, .semantic graphState)
  | .flipWorld worldState => (!worldState, .flipWorld (!worldState))

def envelopeRevision (operator : LocalOperator) (state : BoundedEnvelope)
    (proposed : Graph) (observations : List (HSWM.NoisyFeedback.Observation Input))
    (allowance debit : Nat) : BoundedEnvelope :=
  match state with
  | .semantic graphState => .semantic (revise operator graphState proposed observations allowance debit)
  | .flipWorld worldState => .flipWorld worldState

theorem embedding_preserves_semantic_execution (operator : LocalOperator)
    (state : Graph) (input : Input) :
    envelopeStep operator (.semantic state) input =
      (execute operator state input, .semantic state) := rfl

theorem embedding_preserves_semantic_revision (operator : LocalOperator)
    (state proposed : Graph) (observations : List (HSWM.NoisyFeedback.Observation Input))
    (allowance debit : Nat) :
    envelopeRevision operator (.semantic state) proposed observations allowance debit =
      .semantic (revise operator state proposed observations allowance debit) := rfl

theorem broader_envelope_has_a_nonsemantic_world :
    ¬ ∃ state : Graph, BoundedEnvelope.semantic state = .flipWorld false := by
  intro h
  rcases h with ⟨state, impossible⟩
  cases impossible

theorem world_variant_really_executes (operator : LocalOperator) (input : Input) :
    envelopeStep operator (.flipWorld false) input = (true, .flipWorld true) := rfl

end HSWM.SemanticSoftware
