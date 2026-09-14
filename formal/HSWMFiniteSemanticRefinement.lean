import HSWMSemanticQuotient
import HSWMFiniteSemanticLearning

/-!
# Finite semantic-learning refinement witness

This file instantiates the exact deterministic refinement theorem with the
finite role-sensitive table learner.  The source state retains an
observation-record history; the target state is its table-valued read summary.
A Step emits a prediction and its role-bearing input before a later Learn
consumes a record.  Both models accept every label in this deliberately bounded
toy domain.

The arbitrary-event theorem is only an exact temporal law over supplied
records: it does not authenticate a record, bind it to a Permit, or establish
that it is a causally valid observation.  A separate concrete `fullEpisode`
below supplies the record by this learner's own Step -> Env -> Learn value flow.
That value flow is still pure mathematics with a fixed `Env`, not I/O isolation,
cryptographic sealing, runtime enforcement, external grounding, performance
gain, or a full HSWM witness.
-/

namespace HSWM.FiniteSemanticRefinement

open HSWM.SemanticQuotient
open HSWM.FiniteSemanticLearning

/-- An observation-record history: all supplied post-Step records remain present. -/
def fullHistoryDynamics : Dynamics (List Record) Input (Bool × Input) Record where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun history input =>
    let output := (semanticStep (summary history) input, input)
    (output, history)
  learn := fun history record => history ++ [record]

/-- The sufficient table view used by the same finite learner. -/
def tableDynamics : Dynamics Table Input (Bool × Input) Record where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun table input =>
    let output := (semanticStep table input, input)
    (output, table)
  learn := HSWM.FiniteSemanticLearning.learn

/-- The history-to-table view is an exact deterministic refinement for this learner. -/
theorem fullHistory_refines_table :
    ExactRefinement fullHistoryDynamics tableDynamics summary id where
  stepAllowed_iff := by
    intro history input
    rfl
  learnAllowed_iff := by
    intro history record
    rfl
  step_commutes := by
    intro history input _
    rfl
  learn_commutes := by
    intro history record _
    exact summary_append history record

/--
Every finite interleaving of predeclared inputs and supplied records preserves
all emitted role-bearing outputs and the final learned table under `summary`.
-/
theorem fullHistory_trace_refines_table
    (initialHistory : List Record) (events : List (Event Input Record)) :
    mapRun summary id (run fullHistoryDynamics initialHistory events) =
      run tableDynamics (summary initialHistory) events :=
  run_refines fullHistory_refines_table initialHistory events

/--
One concrete source-side episode.  Its record is derived from this learner's
semantic Step trace and the fixed environment value, rather than supplied as an
arbitrary `Event.learn` payload.
-/
def fullEpisode (history : List Record) (input : Input) (truth : Env) : List Record :=
  let trace := (semanticStep (summary history) input, input)
  history ++ [{ input := trace.2, outcome := env truth trace }]

/-- The concrete full-history episode and table episode have the same summary. -/
theorem summary_fullEpisode (history : List Record) (input : Input) (truth : Env) :
    summary (fullEpisode history input truth) = episode (summary history) input truth := by
  unfold fullEpisode episode
  rw [summary_append, semanticStep_eq_step]
  rfl

/-- Repeated concrete source-side Step -> Env -> Learn value flow. -/
def fullSweep (inputs : List Input) (truth : Env) (history : List Record) : List Record :=
  inputs.foldl (fun current input => fullEpisode current input truth) history

/-- The corresponding repeated table-side episode. -/
def tableSweep (inputs : List Input) (truth : Env) (table : Table) : Table :=
  inputs.foldl (fun current input => episode current input truth) table

/-- The history summary commutes with every finite concrete episode sweep. -/
theorem summary_fullSweep (inputs : List Input) (truth : Env) (history : List Record) :
    summary (fullSweep inputs truth history) = tableSweep inputs truth (summary history) := by
  induction inputs generalizing history with
  | nil => rfl
  | cons input inputs inductionHypothesis =>
      simp only [fullSweep, tableSweep, List.foldl_cons]
      change
        summary (fullSweep inputs truth (fullEpisode history input truth)) =
          tableSweep inputs truth (episode (summary history) input truth)
      rw [inductionHypothesis (fullEpisode history input truth), summary_fullEpisode]

/-- A complete concrete sweep produces exactly the learner's declared training table. -/
theorem summary_fullSweep_allInputs (truth : Env) :
    summary (fullSweep allInputs truth []) = train truth := by
  simpa [tableSweep, train, summary, empty] using summary_fullSweep allInputs truth []

/-- The concrete source-side sweep predicts every predeclared intervention exactly. -/
theorem fullSweep_prediction_exact (truth : Env) (input : Input) :
    predict (summary (fullSweep allInputs truth [])) input = truth input := by
  rw [summary_fullSweep_allInputs]
  exact learned_prediction_exact truth input

/-- The same concrete sweep executes the learned polynomial, with exact output. -/
theorem fullSweep_semantic_prediction_exact (truth : Env) (input : Input) :
    semanticStep (summary (fullSweep allInputs truth [])) input = truth input := by
  rw [semanticStep_eq_step]
  exact fullSweep_prediction_exact truth input

/-- In the cubic environment the concrete record-generating sweep lowers errors. -/
theorem fullSweep_cubic_strict_gain :
    errors cubic (summary (fullSweep allInputs cubic [])) < errors cubic empty := by
  rw [summary_fullSweep_allInputs]
  exact cubic_learning_strictly_improves

end HSWM.FiniteSemanticRefinement
