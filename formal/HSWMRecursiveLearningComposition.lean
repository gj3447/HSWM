import Std
import HSWMOutcomeLearningGain

/-!
# Recursive joint-candidate learning for a semantic tree

This is a finite reference construction for a missing composition obligation.
Every version-space element is an entire recursive semantic tree.  A macro
outcome filters that full candidate, so uncertainty and exception fields stay
attached to their leaves and correlations between leaves are not replaced by a
product of marginal candidate pools.  The result is not a durable runtime,
LLM-refinement proof, topology-discovery method, or scalable cognition claim.
-/

namespace HSWM.RecursiveLearningComposition

/-- A leaf keeps executable meaning together with uncertainty and exceptions. -/
structure LeafCandidate (Input Output : Type) where
  rule : Input → Output
  uncertainty : Nat
  exceptions : List Input

/-- A recursively nested semantic relation tree.  Any finite nonempty fanout is
encoded by a binary bracketing, while leaf order remains explicit. -/
inductive SemanticTree (A : Type) where
  | leaf : A → SemanticTree A
  | branch : SemanticTree A → SemanticTree A → SemanticTree A
deriving Repr

/-- The structural tree used to reconstruct a regrouped flat representation.
`flatten` alone deliberately does not retain this shape; it is external
reconstruction metadata rather than an inferred property of a leaf list. -/
inductive Shape where
  | leaf : Shape
  | branch : Shape → Shape → Shape
deriving Repr

def shape : SemanticTree A → Shape
  | .leaf _ => .leaf
  | .branch left right => .branch (shape left) (shape right)

def flatten : SemanticTree A → List A
  | .leaf value => [value]
  | .branch left right => flatten left ++ flatten right

/-- Consume exactly as many values as a recursive shape declares, returning leftovers. -/
def regroup : Shape → List A → Option (SemanticTree A × List A)
  | .leaf, [] => none
  | .leaf, value :: remaining => some (.leaf value, remaining)
  | .branch left right, values =>
      match regroup left values with
      | none => none
      | some (leftTree, remaining) =>
          match regroup right remaining with
          | none => none
          | some (rightTree, leftovers) => some (.branch leftTree rightTree, leftovers)

theorem regroup_shape_flatten_append (tree : SemanticTree A) (remaining : List A) :
    regroup (shape tree) (flatten tree ++ remaining) = some (tree, remaining) := by
  induction tree generalizing remaining with
  | leaf value => simp [shape, flatten, regroup]
  | branch left right leftIH rightIH =>
    simp only [shape, flatten, regroup]
    rw [List.append_assoc, leftIH (flatten right ++ remaining)]
    simp only
    rw [rightIH remaining]

theorem regroup_shape_flatten (tree : SemanticTree A) :
    regroup (shape tree) (flatten tree) = some (tree, []) := by
  simpa using regroup_shape_flatten_append tree []

/-- Canonically bracket any finite nonempty n-ary member sequence. -/
def bracket (first : A) : List A → SemanticTree A
  | [] => .leaf first
  | next :: remaining => .branch (.leaf first) (bracket next remaining)

theorem flatten_bracket (first : A) (remaining : List A) :
    flatten (bracket first remaining) = first :: remaining := by
  induction remaining generalizing first with
  | nil => rfl
  | cons next remaining ih =>
    simp [bracket, flatten, ih]


/-- A whole candidate tree, rather than a product of independently learned leaves.
The fields are retained records only: this module gives neither uncertainty
calibration nor active exception semantics. -/
abbrev Candidate (Input Output : Type) := SemanticTree (LeafCandidate Input Output)
abbrev State (Input Output : Type) := List (Candidate Input Output)

def leafOutputs (candidate : Candidate Input Output) (input : Input) : List Output :=
  (flatten candidate).map (fun leaf => leaf.rule input)

/-- The aggregation law is declared by the macro relation, not inferred from marginals. -/
def forward (aggregate : List Output → Output) (candidate : Candidate Input Output)
    (input : Input) : Output :=
  aggregate (leafOutputs candidate input)

def flatForward (aggregate : List Output → Output) (leaves : List (LeafCandidate Input Output))
    (input : Input) : Output :=
  aggregate (leaves.map (fun leaf => leaf.rule input))

theorem forward_flatten (aggregate : List Output → Output) (candidate : Candidate Input Output)
    (input : Input) :
    forward aggregate candidate input = flatForward aggregate (flatten candidate) input := rfl

/-- Declared Boolean conjunction for an actual recursive internal-node computation. -/
def allTrue : List Bool → Bool
  | [] => true
  | value :: remaining => value && allTrue remaining

theorem allTrue_append (left right : List Bool) :
    allTrue (left ++ right) = (allTrue left && allTrue right) := by
  induction left with
  | nil => simp [allTrue]
  | cons value remaining ih =>
    cases value <;> simp [allTrue, ih]

/-- Unlike generic `forward`, this evaluator executes an AND at every tree branch. -/
def recursiveAnd (candidate : Candidate Input Bool) (input : Input) : Bool :=
  match candidate with
  | .leaf leaf => leaf.rule input
  | .branch left right => recursiveAnd left input && recursiveAnd right input

theorem recursiveAnd_flatten (candidate : Candidate Input Bool) (input : Input) :
    recursiveAnd candidate input = allTrue (leafOutputs candidate input) := by
  induction candidate with
  | leaf leaf => simp [recursiveAnd, leafOutputs, flatten, allTrue]
  | branch left right leftIH rightIH =>
    calc
      recursiveAnd (.branch left right) input =
          (allTrue (leafOutputs left input) && allTrue (leafOutputs right input)) := by
        change (recursiveAnd left input && recursiveAnd right input) = _
        rw [leftIH, rightIH]
      _ = allTrue (leafOutputs left input ++ leafOutputs right input) :=
        (allTrue_append _ _).symm
      _ = allTrue (leafOutputs (.branch left right) input) := by
        simp [leafOutputs, flatten, List.map_append]

theorem recursiveAnd_is_forward (candidate : Candidate Input Bool) (input : Input) :
    recursiveAnd candidate input = forward allTrue candidate input :=
  recursiveAnd_flatten candidate input

/-- A later macro observation, supplied separately from the earlier prediction. -/
abbrev Observation (Input Output : Type) := HSWM.OutcomeLearningGain.ExternalExample Input Output

/-- Filter whole recursive configurations using one observed macro output. -/
def learn [DecidableEq Output] (aggregate : List Output → Output) (state : State Input Output)
    (observation : Observation Input Output) : State Input Output :=
  state.filter (fun candidate => decide (forward aggregate candidate observation.input = observation.outcome))

def flatLearn [DecidableEq Output] (aggregate : List Output → Output)
    (state : List (List (LeafCandidate Input Output))) (observation : Observation Input Output) :
    List (List (LeafCandidate Input Output)) :=
  state.filter (fun leaves => decide (flatForward aggregate leaves observation.input = observation.outcome))

/-- Whole-outcome learning using the recursively evaluated AND, not a factored leaf update. -/
def andLearn (state : State Input Bool) (observation : Observation Input Bool) : State Input Bool :=
  state.filter (fun candidate => decide (recursiveAnd candidate observation.input = observation.outcome))

theorem andLearn_eq_learn (state : State Input Bool) (observation : Observation Input Bool) :
    andLearn state observation = learn allTrue state observation := by
  induction state with
  | nil => rfl
  | cons candidate rest ih =>
    have same : decide (recursiveAnd candidate observation.input = observation.outcome) =
        decide (forward allTrue candidate observation.input = observation.outcome) := by
      rw [recursiveAnd_is_forward]
    have restEq : List.filter
        (fun tree => decide (recursiveAnd tree observation.input = observation.outcome)) rest =
        List.filter (fun tree => decide (forward allTrue tree observation.input = observation.outcome)) rest := by
      simpa [andLearn, learn] using ih
    simp only [andLearn, learn, List.filter_cons]
    rw [same]
    split <;> simp [restEq]

/-- Flattening does not factorize a joint posterior: it commutes with the same whole-outcome filter. -/
theorem flatten_learn [DecidableEq Output] (aggregate : List Output → Output)
    (state : State Input Output) (observation : Observation Input Output) :
    (learn aggregate state observation).map flatten =
      flatLearn aggregate (state.map flatten) observation := by
  induction state with
  | nil => rfl
  | cons candidate rest ih =>
    by_cases accepted : flatForward aggregate (flatten candidate) observation.input = observation.outcome
    · have original : forward aggregate candidate observation.input = observation.outcome := by
        rwa [forward_flatten]
      simp [learn, flatLearn, accepted, original]
      simpa [learn, flatLearn] using ih
    · have original : ¬ forward aggregate candidate observation.input = observation.outcome := by
        rwa [forward_flatten]
      simp [learn, flatLearn, accepted, original]
      simpa [learn, flatLearn] using ih

/-- The real recursive AND computation and its whole-outcome filter commute with flattening. -/
theorem recursiveAnd_learn_flatten (state : State Input Bool) (observation : Observation Input Bool) :
    (andLearn state observation).map flatten =
      flatLearn allTrue (state.map flatten) observation := by
  rw [andLearn_eq_learn]
  exact flatten_learn allTrue state observation

/-- Regrouping a flattened candidate recovers its executable behaviour exactly. -/
theorem regroup_preserves_forward (aggregate : List Output → Output)
    (candidate : Candidate Input Output) (input : Input) :
    match regroup (shape candidate) (flatten candidate) with
    | some (recovered, []) => forward aggregate recovered input = forward aggregate candidate input
    | _ => False := by
  rw [regroup_shape_flatten]

def toLaw (aggregate : List Output → Output) (candidate : Candidate Input Output) :
    HSWM.OutcomeLearningGain.SemanticLaw Input Output := ⟨forward aggregate candidate⟩

def toLaws (aggregate : List Output → Output) (state : State Input Output) :
    HSWM.OutcomeLearningGain.State Input Output := state.map (toLaw aggregate)

theorem learn_projection [DecidableEq Output] (aggregate : List Output → Output)
    (state : State Input Output) (observation : Observation Input Output) :
    toLaws aggregate (learn aggregate state observation) =
      HSWM.OutcomeLearningGain.learn (toLaws aggregate state) observation := by
  induction state with
  | nil => rfl
  | cons candidate rest ih =>
    by_cases accepted : forward aggregate candidate observation.input = observation.outcome
    · simp only [learn, List.filter_cons, toLaws, List.map_cons,
        HSWM.OutcomeLearningGain.learn]
      simp [accepted, toLaw]
      simpa [learn, toLaws, HSWM.OutcomeLearningGain.learn, toLaw] using ih
    · simp only [learn, List.filter_cons, toLaws, List.map_cons,
        HSWM.OutcomeLearningGain.learn]
      simp [accepted, toLaw]
      simpa [learn, toLaws, HSWM.OutcomeLearningGain.learn, toLaw] using ih

def step (aggregate : List Output → Output) (state : State Input Output) (input : Input) :
    Option Output := state.head?.map (fun candidate => forward aggregate candidate input)

theorem step_projection (aggregate : List Output → Output) (state : State Input Output) (input : Input) :
    step aggregate state input = HSWM.OutcomeLearningGain.step (toLaws aggregate state) input := by
  cases state <;> rfl

/-- Count a prediction before each subsequent whole-tree outcome filter. -/
def mistakeCount [DecidableEq Output] (aggregate : List Output → Output) :
    State Input Output → List (Observation Input Output) → Nat
  | _state, [] => 0
  | state, observation :: remaining =>
      (if (step aggregate state observation.input).isSome &&
          decide (step aggregate state observation.input ≠ some observation.outcome)
       then 1 else 0) +
        mistakeCount aggregate (learn aggregate state observation) remaining

theorem mistakeCount_projection [DecidableEq Output] (aggregate : List Output → Output)
    (state : State Input Output) (observations : List (Observation Input Output)) :
    mistakeCount aggregate state observations =
      HSWM.OutcomeLearningGain.mistakeCount (toLaws aggregate state) observations := by
  induction observations generalizing state with
  | nil => rfl
  | cons observation remaining ih =>
    simp only [mistakeCount, HSWM.OutcomeLearningGain.mistakeCount, ih, learn_projection]
    congr 1
    rw [step_projection]
    unfold HSWM.OutcomeLearningGain.wrong
    cases HSWM.OutcomeLearningGain.step (toLaws aggregate state) observation.input <;> simp

inductive Event (Input Output : Type) where
  | step : Input → Event Input Output
  | learn : Observation Input Output → Event Input Output

def advance [DecidableEq Output] (aggregate : List Output → Output) :
    State Input Output → Event Input Output → Option Output × State Input Output
  | state, .step input => (step aggregate state input, state)
  | state, .learn observation => (none, learn aggregate state observation)

def run [DecidableEq Output] (aggregate : List Output → Output) :
    State Input Output → List (Event Input Output) → List (Option Output) × State Input Output
  | state, [] => ([], state)
  | state, event :: events =>
      let first := advance aggregate state event
      let remaining := run aggregate first.2 events
      (first.1 :: remaining.1, remaining.2)

def flatAdvance [DecidableEq Output] (aggregate : List Output → Output) :
    List (List (LeafCandidate Input Output)) → Event Input Output →
      Option Output × List (List (LeafCandidate Input Output))
  | state, .step input => (state.head?.map (fun leaves => flatForward aggregate leaves input), state)
  | state, .learn observation => (none, flatLearn aggregate state observation)

def flatRun [DecidableEq Output] (aggregate : List Output → Output) :
    List (List (LeafCandidate Input Output)) → List (Event Input Output) →
      List (Option Output) × List (List (LeafCandidate Input Output))
  | state, [] => ([], state)
  | state, event :: events =>
      let first := flatAdvance aggregate state event
      let remaining := flatRun aggregate first.2 events
      (first.1 :: remaining.1, remaining.2)

theorem advance_flatten [DecidableEq Output] (aggregate : List Output → Output)
    (state : State Input Output) (event : Event Input Output) :
    (advance aggregate state event).1 = (flatAdvance aggregate (state.map flatten) event).1 ∧
    (advance aggregate state event).2.map flatten =
      (flatAdvance aggregate (state.map flatten) event).2 := by
  cases event with
  | step input =>
    cases state with
    | nil => constructor <;> rfl
    | cons candidate rest =>
      simp [advance, flatAdvance, step, forward_flatten]
  | learn observation =>
    exact ⟨rfl, flatten_learn aggregate state observation⟩

/-- Any nested regrouping has the same Step/Learn trace after flattening. -/
theorem run_flatten [DecidableEq Output] (aggregate : List Output → Output)
    (state : State Input Output) (events : List (Event Input Output)) :
    (run aggregate state events).1 = (flatRun aggregate (state.map flatten) events).1 ∧
    (run aggregate state events).2.map flatten =
      (flatRun aggregate (state.map flatten) events).2 := by
  induction events generalizing state with
  | nil => exact ⟨rfl, rfl⟩
  | cons event events ih =>
    simp only [run, flatRun]
    have first := advance_flatten aggregate state event
    rcases sourceAdvance : advance aggregate state event with ⟨output, next⟩
    have targetAdvance : flatAdvance aggregate (state.map flatten) event =
        (output, next.map flatten) := by
      rcases first with ⟨outputs, states⟩
      rw [sourceAdvance] at outputs states
      exact Prod.ext outputs.symm states.symm
    simp only [targetAdvance]
    have remaining := ih next
    rcases sourceRemaining : run aggregate next events with ⟨outputs, finalState⟩
    rw [sourceRemaining] at remaining
    rcases targetRemaining : flatRun aggregate (next.map flatten) events with
      ⟨flatOutputs, flatFinalState⟩
    rw [targetRemaining] at remaining
    exact ⟨by simpa using congrArg (List.cons output) remaining.1, remaining.2⟩

def toObservationLaw (aggregate : List Output → Output) (candidate : Candidate Input Output) :=
  toLaw aggregate candidate

/-- The ordinary realizable finite mistake bound transfers to full tree candidates. -/
theorem joint_tree_mistake_bound [DecidableEq Output] (aggregate : List Output → Output)
    (truth : Candidate Input Output) (state : State Input Output)
    (observations : List (Observation Input Output)) (member : truth ∈ state)
    (realizes : ∀ observation ∈ observations,
      forward aggregate truth observation.input = observation.outcome) :
    HSWM.OutcomeLearningGain.mistakeCount (toLaws aggregate state) observations ≤ state.length - 1 := by
  have truthMember : toLaw aggregate truth ∈ toLaws aggregate state :=
    List.mem_map.mpr ⟨truth, member, rfl⟩
  simpa [toLaws] using
    HSWM.OutcomeLearningGain.mistakeCount_le_initial_sub_one (toLaw aggregate truth)
      (toLaws aggregate state) observations truthMember realizes

/-- The bound applies to the concrete recursive Step-before-Learn counter. -/
theorem recursive_tree_mistake_bound [DecidableEq Output] (aggregate : List Output → Output)
    (truth : Candidate Input Output) (state : State Input Output)
    (observations : List (Observation Input Output)) (member : truth ∈ state)
    (realizes : ∀ observation ∈ observations,
      forward aggregate truth observation.input = observation.outcome) :
    mistakeCount aggregate state observations ≤ state.length - 1 := by
  rw [mistakeCount_projection]
  exact joint_tree_mistake_bound aggregate truth state observations member realizes

/-- A two-leaf XOR fixture for why the state must retain joint configurations. -/
def constantLeaf (value : Bool) : LeafCandidate Bool Bool :=
  ⟨fun _ => value, if value then 1 else 2, [true]⟩

def xorAggregate : List Bool → Bool
  | [left, right] => left != right
  | _ => false

def xorCandidate (left right : Bool) : Candidate Bool Bool :=
  .branch (.leaf (constantLeaf left)) (.leaf (constantLeaf right))

def xorInitial : State Bool Bool :=
  [xorCandidate false false, xorCandidate false true,
   xorCandidate true false, xorCandidate true true]

def xorOutcome : Observation Bool Bool := ⟨false, true⟩

theorem xor_joint_filter_keeps_only_correlated_pairs :
    learn xorAggregate xorInitial xorOutcome =
      [xorCandidate false true, xorCandidate true false] := by
  simp [learn, xorInitial, xorOutcome, forward, leafOutputs, flatten,
    xorCandidate, constantLeaf, xorAggregate]

def recombine (lefts rights : List Bool) : List (Bool × Bool) :=
  lefts.flatMap (fun left => rights.map (fun right => (left, right)))

/-- Read the two ordered leaf values from retained whole candidates only. -/
def boolPair? : List Bool → Option (Bool × Bool)
  | [left, right] => some (left, right)
  | _ => none

def xorPosteriorPairs : List (Bool × Bool) :=
  (learn xorAggregate xorInitial xorOutcome).filterMap
    (fun candidate => boolPair? (leafOutputs candidate false))

def xorLeftMarginal : List Bool := xorPosteriorPairs.map Prod.fst
def xorRightMarginal : List Bool := xorPosteriorPairs.map Prod.snd

theorem xor_posterior_pairs_are_derived_from_joint_filter :
    xorPosteriorPairs = [(false, true), (true, false)] := by
  unfold xorPosteriorPairs
  rw [xor_joint_filter_keeps_only_correlated_pairs]
  rfl

theorem xor_marginals_are_derived_not_supplied :
    xorLeftMarginal = [false, true] ∧ xorRightMarginal = [true, false] := by
  unfold xorLeftMarginal xorRightMarginal
  rw [xor_posterior_pairs_are_derived_from_joint_filter]
  constructor <;> rfl

/-- Marginalizing then recombining creates pairs rejected by the joint posterior. -/
theorem recombining_xor_marginals_admits_invalid_pairs :
    (false, false) ∈ recombine xorLeftMarginal xorRightMarginal ∧
    (true, true) ∈ recombine xorLeftMarginal xorRightMarginal := by
  decide

theorem invalid_pairs_are_absent_from_joint_xor_posterior :
    xorCandidate false false ∉ learn xorAggregate xorInitial xorOutcome ∧
    xorCandidate true true ∉ learn xorAggregate xorInitial xorOutcome := by
  rw [xor_joint_filter_keeps_only_correlated_pairs]
  constructor
  · intro member
    simp only [List.mem_cons, List.not_mem_nil, or_false] at member
    rcases member with same | same
    · have observed := congrArg (fun candidate => forward xorAggregate candidate false) same
      simp [forward, leafOutputs, flatten, xorCandidate, constantLeaf, xorAggregate] at observed
    · have observed := congrArg (fun candidate => forward xorAggregate candidate false) same
      simp [forward, leafOutputs, flatten, xorCandidate, constantLeaf, xorAggregate] at observed
  · intro member
    simp only [List.mem_cons, List.not_mem_nil, or_false] at member
    rcases member with same | same
    · have observed := congrArg (fun candidate => forward xorAggregate candidate false) same
      simp [forward, leafOutputs, flatten, xorCandidate, constantLeaf, xorAggregate] at observed
    · have observed := congrArg (fun candidate => forward xorAggregate candidate false) same
      simp [forward, leafOutputs, flatten, xorCandidate, constantLeaf, xorAggregate] at observed

end HSWM.RecursiveLearningComposition
