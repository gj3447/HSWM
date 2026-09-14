import HSWMSemanticWeightDefinition
import HSWMHypergraphRepresentation
import HSWMLocalEnsembleGain
import HSWMOutcomeLearningGain

/-!
# One semantic graph Step/Learn with a derived performance gain

A bounded reference model, not an implementation or correctness proof of a
pretrained LLM. The world below has the fixed Boolean target `true`; three
local signals have an explicitly declared joint law. Each candidate stores an
actual role-bearing four-member relation. Small internal reference operators
read its endpoints and interpret its semantic payload. The same forward map
is used both to predict and to eliminate outcome-inconsistent graph revisions.

The update does not read the truth function or a desired gain. One truthful
observation makes the selected relation change from first-signal selection to
majority. Its accuracy on the entire declared input law then increases by a
previously proved ensemble theorem. The same graph update also inherits the
finite realizable mistake bound. This connects two mechanisms constructively;
it does not establish open-ended learning, topology discovery, generalization
from a dataset to a real population, equal-cost superiority, or full HSWM.
-/

namespace HSWM.SemanticPerformanceBridge


inductive Rule where
  | first | majority | alwaysTrue
deriving DecidableEq, Repr

inductive Role where
  | sourceOne | sourceTwo | sourceThree | recipient
deriving DecidableEq, Repr

abbrev Graph := HSWM.HypergraphRepresentation.NaryRelation Rule Role (Fin 4) 4
abbrev Input := HSWM.LocalEnsembleGain.Votes
abbrev LocalContext := HSWM.SemanticWeightDefinition.RoleContext Role (Fin 4) Input

def roleAt (slot : Fin 4) : Role :=
  if slot = 0 then .sourceOne else if slot = 1 then .sourceTwo
  else if slot = 2 then .sourceThree else .recipient

def graph (rule : Rule) : Graph :=
  { payload := rule, member := fun slot => (roleAt slot, slot) }

def signalAt (input : Input) (vertex : Fin 4) : Bool :=
  if vertex = 0 then input.first else if vertex = 1 then input.second
  else if vertex = 2 then input.third else false

def contextFor (g : Graph) (input : Input) : LocalContext :=
  { incidences := (List.finRange 4).map fun slot =>
      { role := (g.member slot).1, participant := (g.member slot).2 }
    context := input }

/-- Each local reference operator receives only its labelled one-bit signal. -/
def localWeight (slot : Fin 4) :
    HSWM.SemanticWeightDefinition.SemanticWeight Graph (Role × Bool) Role (Fin 4) Input Bool :=
  HSWM.SemanticWeightDefinition.SemanticWeight.fromLlm
    (fun g input => ((g.member slot).1, signalAt input.context (g.member slot).2))
    (fun read _ => read) (fun read => read.2)

def localOutputs (g : Graph) (input : Input) : HSWM.LocalEnsembleGain.Votes :=
  let ctx := contextFor g input
  ⟨HSWM.SemanticWeightDefinition.behavior (localWeight 0) g ctx,
   HSWM.SemanticWeightDefinition.behavior (localWeight 1) g ctx,
   HSWM.SemanticWeightDefinition.behavior (localWeight 2) g ctx⟩

/-- Fixed abstract interpreter; its name does not assert real LLM fidelity. -/
def referenceOperator : Rule × HSWM.LocalEnsembleGain.Votes → Bool
  | (.first, votes) => votes.first
  | (.majority, votes) => HSWM.LocalEnsembleGain.majority votes.first votes.second votes.third
  | (.alwaysTrue, _) => true

/-- The recipient reads one relation's semantic payload and three local outputs. -/
def jointWeight :
    HSWM.SemanticWeightDefinition.SemanticWeight Graph (Rule × HSWM.LocalEnsembleGain.Votes) Role (Fin 4) Input Bool :=
  HSWM.SemanticWeightDefinition.SemanticWeight.fromLlm
    (fun g input => (g.payload, localOutputs g input.context))
    (fun read _ => read) referenceOperator

def forward (g : Graph) (input : Input) : Bool :=
  HSWM.SemanticWeightDefinition.behavior jointWeight g (contextFor g input)

theorem forward_is_local_semantic_weight (g : Graph) (input : Input) :
    forward g input = referenceOperator (g.payload, localOutputs g input) := rfl

theorem labelled_local_outputs (rule : Rule) (input : Input) :
    localOutputs (graph rule) input = input := by
  cases input
  rfl

theorem forward_first (input : Input) : forward (graph .first) input = input.first := by
  rw [forward_is_local_semantic_weight, labelled_local_outputs]
  rfl

theorem forward_majority (input : Input) :
    forward (graph .majority) input = HSWM.LocalEnsembleGain.majorityCorrect input := by
  rw [forward_is_local_semantic_weight, labelled_local_outputs]
  rfl

theorem forward_truth (input : Input) : forward (graph .alwaysTrue) input = true := rfl

/-- Finite alternative revisions retain the whole relation, including incidences. -/
abbrev State := List Graph
abbrev Observation := HSWM.OutcomeLearningGain.ExternalExample Input Bool

def step (state : State) (input : Input) : Option Bool :=
  state.head?.map (fun g => forward g input)

def learn (state : State) (observation : Observation) : State :=
  state.filter (fun g => decide (forward g observation.input = observation.outcome))

def toLaw (g : Graph) : HSWM.OutcomeLearningGain.SemanticLaw Input Bool := ⟨forward g⟩
def toLaws (state : State) : HSWM.OutcomeLearningGain.State Input Bool := state.map toLaw

theorem step_projection (state : State) (input : Input) :
    step state input = HSWM.OutcomeLearningGain.step (toLaws state) input := by
  cases state <;> rfl

theorem learn_projection (state : State) (observation : Observation) :
    toLaws (learn state observation) = HSWM.OutcomeLearningGain.learn (toLaws state) observation := by
  induction state with
  | nil => rfl
  | cons g rest ih =>
    simp only [learn, List.filter_cons, toLaws, List.map_cons, HSWM.OutcomeLearningGain.learn] at *
    change (if decide (forward g observation.input = observation.outcome)
      then g :: rest.filter _ else rest.filter _).map toLaw = _
    by_cases h : forward g observation.input = observation.outcome
    · simpa [h, toLaw] using congrArg (List.cons (toLaw g)) ih
    · simpa [h, toLaw] using ih

def mistakeCount : State → List Observation → Nat
  | _, [] => 0
  | state, observation :: rest =>
      (if (step state observation.input).isSome &&
          decide (step state observation.input ≠ some observation.outcome)
       then 1 else 0) + mistakeCount (learn state observation) rest

theorem mistake_count_projection (state : State) (observations : List Observation) :
    mistakeCount state observations = HSWM.OutcomeLearningGain.mistakeCount (toLaws state) observations := by
  induction observations generalizing state with
  | nil => rfl
  | cons observation rest ih =>
    simp only [mistakeCount, HSWM.OutcomeLearningGain.mistakeCount, ih, learn_projection]
    congr 1
    rw [step_projection]
    unfold HSWM.OutcomeLearningGain.wrong
    cases HSWM.OutcomeLearningGain.step (toLaws state) observation.input <;> simp

/-- The generic finite bound transfers to these actual graph revisions and Step. -/
theorem graph_mistake_bound (truth : Graph) (state : State)
    (observations : List Observation) (member : truth ∈ state)
    (realizes : ∀ obs ∈ observations, forward truth obs.input = obs.outcome) :
    mistakeCount state observations ≤ state.length - 1 := by
  rw [mistake_count_projection]
  have m : toLaw truth ∈ toLaws state := List.mem_map.mpr ⟨truth, member, rfl⟩
  have bound := HSWM.OutcomeLearningGain.mistakeCount_le_initial_sub_one (toLaw truth) (toLaws state)
    observations m realizes
  simpa [toLaws] using bound

def initial : State := [graph .first, graph .majority, graph .alwaysTrue]
def feedback : Observation := ⟨⟨false, true, true⟩, true⟩

theorem update_changes_semantic_relation :
    learn initial feedback = [graph .majority, graph .alwaysTrue] := rfl

theorem feedback_follows_mistaken_prediction :
    step initial feedback.input = some false ∧ feedback.outcome = true := by decide

/-- Accuracy mass over ALL eight inputs under a fixed, independently declared law. -/
def correctMass (good bad : Nat) (state : State) : Nat :=
  HSWM.LocalEnsembleGain.eventMass (HSWM.LocalEnsembleGain.iidWeight good bad) (fun input =>
    decide (step state input = some true))

theorem initial_correct_mass (good bad : Nat) :
    correctMass good bad initial = HSWM.LocalEnsembleGain.iidSingleMass good bad := by
  have same : (fun input => decide (step initial input = some true)) = HSWM.LocalEnsembleGain.firstCorrect := by
    funext input
    simp [step, initial, forward_first, HSWM.LocalEnsembleGain.firstCorrect]
  unfold correctMass
  rw [same, HSWM.LocalEnsembleGain.iid_first_correct_mass_enumerates_product_joint_law]

theorem learned_correct_mass (good bad : Nat) :
    correctMass good bad (learn initial feedback) = HSWM.LocalEnsembleGain.iidMajorityMass good bad := by
  rw [update_changes_semantic_relation]
  have same : (fun input => decide
      (step [graph .majority, graph .alwaysTrue] input = some true)) =
      HSWM.LocalEnsembleGain.majorityCorrect := by
    funext input
    simp [step, forward_majority]
  unfold correctMass
  rw [same]
  rfl

/-- Gain is derived from the computed update, not assumed as an acceptance condition. -/
theorem computed_semantic_update_strictly_improves
    (good bad : Nat) (goodPositive : 0 < good) (badPositive : 0 < bad)
    (moreGood : bad < good) :
    correctMass good bad initial < correctMass good bad (learn initial feedback) := by
  rw [initial_correct_mass, learned_correct_mass]
  exact HSWM.LocalEnsembleGain.iid_majority_strictly_beats_single good bad goodPositive badPositive moreGood

/-- Exact finite expectation witness, NOT a measured LLM benchmark. -/
theorem concrete_accuracy_mass_gain :
    correctMass 2 1 initial = 18 ∧
    correctMass 2 1 (learn initial feedback) = 20 ∧
    HSWM.LocalEnsembleGain.eventMass (HSWM.LocalEnsembleGain.iidWeight 2 1) (fun _ => true) = 27 := by decide

/-- All truthful first observations, not only the displayed witness, are checked. -/
theorem any_truthful_initial_update_nondecreases (input : Input) :
    correctMass 2 1 initial ≤ correctMass 2 1 (learn initial ⟨input, true⟩) := by
  rcases input with ⟨a, b, c⟩
  cases a <;> cases b <;> cases c <;> decide

/-- Every initial mistake improves whole-law accuracy in this particular model. -/
theorem any_initial_mistake_strictly_improves (second third : Bool) :
    correctMass 2 1 initial <
      correctMass 2 1 (learn initial ⟨⟨false, second, third⟩, true⟩) := by
  cases second <;> cases third <;> decide

/-- The same update admits at most two mistakes on any truthful outcome sequence. -/
theorem same_graph_dynamics_at_most_two_mistakes (observations : List Observation)
    (truthful : ∀ obs ∈ observations, obs.outcome = true) :
    mistakeCount initial observations ≤ 2 := by
  have m : graph .alwaysTrue ∈ initial := by simp [initial]
  have h := graph_mistake_bound (graph .alwaysTrue) initial observations m
    (fun obs mem => (forward_truth obs.input).trans (truthful obs mem).symm)
  simpa [initial] using h

end HSWM.SemanticPerformanceBridge
