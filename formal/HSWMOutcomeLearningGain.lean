import Std

/-!
# Outcome-bound semantic-rule elimination witness

This is a finite, realizable version-space construction.  A candidate is an
arbitrary input-to-output semantic rule (it may stand for a local LLM operator,
not a scalar score). `step` reads only the current candidate list and an input.
A later certified external outcome filters candidates; it does not give the
truth rule to `step` or `learn`.

The results are conditional on a fixed finite initial candidate pool and on
outcomes agreeing with a retained truth rule.  They do not show discovery of
new rules/topology, truth of a real-world label, calibration of an LLM, or
runtime equivalence.
-/

namespace HSWM.OutcomeLearningGain

/-- A candidate semantic law, intentionally more general than a scalar weight. -/
structure SemanticLaw (Input Output : Type) where
  run : Input → Output

/-- A version-space state is the surviving finite family of semantic laws. -/
abbrev State (Input Output : Type) := List (SemanticLaw Input Output)

/-- A post-Step outcome with its input; certification is an explicit premise of theorems. -/
structure ExternalExample (Input Output : Type) where
  input : Input
  outcome : Output

/-- The local operational readout chooses the declared representative, if present. -/
def selected? (state : State Input Output) : Option (SemanticLaw Input Output) :=
  state.head?

/-- Step has no truth-rule or external-outcome argument. -/
def step (state : State Input Output) (input : Input) : Option Output :=
  (selected? state).map (fun law => law.run input)

/-- Keep exactly candidates compatible with an externally supplied outcome. -/
def learn [DecidableEq Output] (state : State Input Output)
    (observation : ExternalExample Input Output) : State Input Output :=
  state.filter (fun law => decide (law.run observation.input = observation.outcome))

/-- A truth rule realizes an observation when the externally certified label agrees with it. -/
def Realizes (truth : SemanticLaw Input Output) (observation : ExternalExample Input Output) : Prop :=
  truth.run observation.input = observation.outcome

/-- Step is definitionally independent of any proposed truth rule. -/
theorem step_reads_only_state_and_input (state : State Input Output) (input : Input)
    (_truth : SemanticLaw Input Output) :
    step state input = (selected? state).map (fun law => law.run input) := rfl

/-- A realizable external outcome cannot eliminate the true semantic rule. -/
theorem truth_retained [DecidableEq Output] (truth : SemanticLaw Input Output)
    (state : State Input Output) (observation : ExternalExample Input Output)
    (member : truth ∈ state) (realizes : Realizes truth observation) :
    truth ∈ learn state observation := by
  unfold learn
  apply List.mem_filter.mpr
  constructor
  · exact member
  · simpa [Realizes] using realizes

/-- A mistaken selected head is removed by the outcome-conditioned revision. -/
theorem mistaken_head_removed [DecidableEq Output]
    (head : SemanticLaw Input Output) (tail : State Input Output)
    (observation : ExternalExample Input Output)
    (mistake : head.run observation.input ≠ observation.outcome) :
    head ∉ learn (head :: tail) observation := by
  simp [learn, mistake]

/-- A mistaken selected head causes a strict reduction of the version-space size. -/
theorem mistaken_head_strictly_shrinks [DecidableEq Output]
    (head : SemanticLaw Input Output) (tail : State Input Output)
    (observation : ExternalExample Input Output)
    (mistake : head.run observation.input ≠ observation.outcome) :
    (learn (head :: tail) observation).length < (head :: tail).length := by
  unfold learn
  simp only [List.filter_cons, List.length_cons]
  have rejected : decide (head.run observation.input = observation.outcome) = false := by
    simp [mistake]
  rw [rejected]
  exact Nat.lt_succ_of_le (List.length_filter_le _ tail)

/-- The representative of a nonempty state is its head. -/
theorem step_cons (head : SemanticLaw Input Output) (tail : State Input Output)
    (input : Input) : step (head :: tail) input = some (head.run input) := rfl

/-- A bounded sequence of externally certified outcomes. -/
def learnAll [DecidableEq Output] (state : State Input Output)
    (observations : List (ExternalExample Input Output)) : State Input Output :=
  observations.foldl learn state

/-- Whether the current local representative makes a mistake on this later outcome. -/
def wrong [DecidableEq Output] (state : State Input Output)
    (observation : ExternalExample Input Output) : Bool :=
  match step state observation.input with
  | none => false
  | some prediction => decide (prediction ≠ observation.outcome)

/-- Count mistakes along a finite outcome sequence, revising after each outcome. -/
def mistakeCount [DecidableEq Output] : State Input Output →
    List (ExternalExample Input Output) → Nat
  | _state, [] => 0
  | state, observation :: remaining =>
      (if wrong state observation then 1 else 0) +
        mistakeCount (learn state observation) remaining

/-- Filtering cannot increase the candidate-pool size. -/
theorem learn_length_le [DecidableEq Output] (state : State Input Output)
    (observation : ExternalExample Input Output) :
    (learn state observation).length ≤ state.length := by
  unfold learn
  exact List.length_filter_le _ state

/-- Realizability holds throughout a fold: the true law remains available after every outcome. -/
theorem truth_retained_learnAll [DecidableEq Output]
    (truth : SemanticLaw Input Output) (state : State Input Output)
    (observations : List (ExternalExample Input Output))
    (member : truth ∈ state)
    (realizes : ∀ observation ∈ observations, Realizes truth observation) :
    truth ∈ learnAll state observations := by
  induction observations generalizing state with
  | nil => simpa [learnAll] using member
  | cons observation rest inductionHypothesis =>
    simp only [learnAll, List.foldl_cons]
    apply inductionHypothesis
    · exact truth_retained truth state observation member (realizes observation (by simp))
    · intro later laterMember
      exact realizes later (by simp [laterMember])

/-- A truth rule in the state guarantees the learned version space is nonempty. -/
theorem learnAll_nonempty_of_truth [DecidableEq Output]
    (truth : SemanticLaw Input Output) (state : State Input Output)
    (observations : List (ExternalExample Input Output))
    (member : truth ∈ state)
    (realizes : ∀ observation ∈ observations, Realizes truth observation) :
    learnAll state observations ≠ [] := by
  intro empty
  have retained := truth_retained_learnAll truth state observations member realizes
  simp [empty] at retained

/--
Under realizable external outcomes, every counted mistake removes the selected
rule while the true rule remains.  Thus a finite initial pool of `N` candidates
admits at most `N - 1` mistakes.  Correct outcomes may remove additional rules;
they never weaken this bound.
-/
theorem mistakeCount_le_initial_sub_one [DecidableEq Output]
    (truth : SemanticLaw Input Output) (state : State Input Output)
    (observations : List (ExternalExample Input Output))
    (member : truth ∈ state)
    (realizes : ∀ observation ∈ observations, Realizes truth observation) :
    mistakeCount state observations ≤ state.length - 1 := by
  induction observations generalizing state with
  | nil => simp [mistakeCount]
  | cons observation remaining inductionHypothesis =>
    cases state with
    | nil => simp at member
    | cons head tail =>
      have retained : truth ∈ learn (head :: tail) observation :=
        truth_retained truth (head :: tail) observation member
          (realizes observation (by simp))
      have remainingRealizes : ∀ later ∈ remaining, Realizes truth later := by
        intro later laterMember
        exact realizes later (by simp [laterMember])
      have laterBound := inductionHypothesis (learn (head :: tail) observation)
        retained remainingRealizes
      have nonincrease : (learn (head :: tail) observation).length ≤ (head :: tail).length :=
        learn_length_le _ _
      have nonincrease' : (learn (head :: tail) observation).length ≤ tail.length + 1 := by
        simpa using nonincrease
      have learnedNonempty : learn (head :: tail) observation ≠ [] := by
        intro empty
        simp [empty] at retained
      have learnedPositive : 0 < (learn (head :: tail) observation).length :=
        List.length_pos_iff.mpr learnedNonempty
      simp only [mistakeCount]
      change (if wrong (head :: tail) observation then 1 else 0) +
          mistakeCount (learn (head :: tail) observation) remaining ≤ tail.length
      cases hwrong : wrong (head :: tail) observation with
      | false =>
        simp
        omega
      | true =>
        simp only [ite_true]
        have mistake : head.run observation.input ≠ observation.outcome := by
          simpa [wrong, step, selected?] using hwrong
        have strict : (learn (head :: tail) observation).length < (head :: tail).length :=
          mistaken_head_strictly_shrinks head tail observation mistake
        have strict' : (learn (head :: tail) observation).length ≤ tail.length := by
          apply Nat.lt_succ_iff.mp
          simpa using strict
        omega

/-- A concrete inconsistent-feedback counterobservation domain. -/
def alwaysTrue : SemanticLaw Bool Bool := ⟨fun _ => true⟩
def alwaysFalse : SemanticLaw Bool Bool := ⟨fun _ => false⟩
def initialBits : State Bool Bool := [alwaysTrue, alwaysFalse]
def badFeedback : ExternalExample Bool Bool := ⟨false, false⟩

/-- The self-generated/inconsistent false label removes the actual true rule. -/
theorem inconsistent_feedback_removes_truth :
    alwaysTrue ∉ learn initialBits badFeedback := by
  change alwaysTrue ∉ [alwaysFalse]
  intro same
  simp only [List.mem_cons, List.not_mem_nil, or_false] at same
  have observed := congrArg (fun law : SemanticLaw Bool Bool => law.run false) same
  simp [alwaysTrue, alwaysFalse] at observed

/-- Before that bad feedback, the selected prediction agrees with the actual true rule. -/
theorem before_bad_feedback_prediction_correct :
    step initialBits false = some (alwaysTrue.run false) := by rfl

/-- After it, the surviving selected prediction is false and disagrees with the actual rule. -/
theorem inconsistent_feedback_can_degrade :
    step (learn initialBits badFeedback) false ≠ some (alwaysTrue.run false) := by
  decide

end HSWM.OutcomeLearningGain
