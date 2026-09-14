import Std

/-!
# Exact deterministic quotient for a semantic-weight transition disposition

This is a mathematical auxiliary result.  A state quotient may stand for a
macro view of a role- and context-conditioned transition disposition only if it
preserves both execution and outcome-qualified learning, including the
observable rejected-event behaviour.  The file proves that condition for a
finite trace in a deterministic model; it does not construct an HSWM runtime,
identify a causal effect, give an external grounding semantics, or establish a
learning gain.

There are deliberately no choice principles here.  The barred dynamics are
supplied explicitly, and the refinement record states the fibre laws which a
candidate abstraction must establish.
-/

namespace HSWM.SemanticQuotient

universe u

/-- Execution and outcome-qualified learning share one state carrier. -/
structure Dynamics (State Action Output Evidence : Type u) where
  stepAllowed : State -> Action -> Bool
  learnAllowed : State -> Evidence -> Bool
  step : State -> Action -> Output × State
  learn : State -> Evidence -> State

variable {State Action Output Evidence MacroState MacroOutput MiddleState MiddleOutput : Type u}
variable {source : Dynamics State Action Output Evidence}
variable {middle : Dynamics MiddleState Action MiddleOutput Evidence}
variable {target : Dynamics MacroState Action MacroOutput Evidence}
variable {mapState : State -> MacroState} {mapOutput : Output -> MacroOutput}
variable {firstState : State -> MiddleState} {firstOutput : Output -> MiddleOutput}
variable {secondState : MiddleState -> MacroState}
variable {secondOutput : MiddleOutput -> MacroOutput}

/-- An interleaved, externally visible event. -/
inductive Event (Action Evidence : Type u) where
  | step : Action -> Event Action Evidence
  | learn : Evidence -> Event Action Evidence
deriving Repr

/-- Map one execution output and successor state to a macro view. -/
def mapStep (mapState : State -> MacroState) (mapOutput : Output -> MacroOutput) :
    Output × State -> MacroOutput × MacroState := fun result =>
  (mapOutput result.1, mapState result.2)

/-- Preserve a no-op/rejection as an observable `none` result. -/
def advance (dynamics : Dynamics State Action Output Evidence) :
    State -> Event Action Evidence -> Option Output × State
  | state, .step action =>
      if dynamics.stepAllowed state action then
        let result := dynamics.step state action
        (some result.1, result.2)
      else
        (none, state)
  | state, .learn evidence =>
      if dynamics.learnAllowed state evidence then
        (none, dynamics.learn state evidence)
      else
        (none, state)

/-- Execute a finite interleaving and retain every externally visible result. -/
def run (dynamics : Dynamics State Action Output Evidence) :
    State -> List (Event Action Evidence) -> List (Option Output) × State
  | state, [] => ([], state)
  | state, event :: events =>
      let first := advance dynamics state event
      let rest := run dynamics first.2 events
      (first.1 :: rest.1, rest.2)

/-- Map a complete finite trace to its macro observation. -/
def mapRun (mapState : State -> MacroState) (mapOutput : Output -> MacroOutput) :
    List (Option Output) × State -> List (Option MacroOutput) × MacroState :=
  fun result => (result.1.map (Option.map mapOutput), mapState result.2)

/--
The exact fibre contract.  The first two fields prevent an abstraction from
silently turning an admissible event into a rejected event, or conversely.  The
last two fields are separate because preserving `Step` alone does not preserve
outcome-qualified `Learn`.
-/
structure ExactRefinement
    (source : Dynamics State Action Output Evidence)
    (target : Dynamics MacroState Action MacroOutput Evidence)
    (mapState : State -> MacroState) (mapOutput : Output -> MacroOutput) : Prop where
  stepAllowed_iff : forall state action,
    source.stepAllowed state action = true <-> target.stepAllowed (mapState state) action = true
  learnAllowed_iff : forall state evidence,
    source.learnAllowed state evidence = true <-> target.learnAllowed (mapState state) evidence = true
  step_commutes : forall state action, source.stepAllowed state action = true ->
    mapStep mapState mapOutput (source.step state action) =
      target.step (mapState state) action
  learn_commutes : forall state evidence, source.learnAllowed state evidence = true ->
    mapState (source.learn state evidence) = target.learn (mapState state) evidence

/-- The supplied fibre laws give exact preservation for one observable event. -/
theorem advance_refines
    (refinement : ExactRefinement source target mapState mapOutput)
    (state : State) (event : Event Action Evidence) :
    (Option.map mapOutput (advance source state event).1,
      mapState (advance source state event).2) =
      advance target (mapState state) event := by
  cases event with
  | step action =>
      by_cases allowed : source.stepAllowed state action = true
      · have macroAllowed := (refinement.stepAllowed_iff state action).mp allowed
        have commutes := refinement.step_commutes state action allowed
        dsimp [advance]
        rw [if_pos allowed, if_pos macroAllowed]
        exact congrArg (fun result : MacroOutput × MacroState =>
          (some result.1, result.2)) commutes
      · have macroRejected : target.stepAllowed (mapState state) action ≠ true := by
          intro macroAllowed
          exact allowed ((refinement.stepAllowed_iff state action).mpr macroAllowed)
        dsimp [advance]
        rw [if_neg allowed, if_neg macroRejected]
        rfl
  | learn evidence =>
      by_cases allowed : source.learnAllowed state evidence = true
      · have macroAllowed := (refinement.learnAllowed_iff state evidence).mp allowed
        have commutes := refinement.learn_commutes state evidence allowed
        dsimp [advance]
        rw [if_pos allowed, if_pos macroAllowed, commutes]
        rfl
      · have macroRejected : target.learnAllowed (mapState state) evidence ≠ true := by
          intro macroAllowed
          exact allowed ((refinement.learnAllowed_iff state evidence).mpr macroAllowed)
        dsimp [advance]
        rw [if_neg allowed, if_neg macroRejected]
        rfl

/-- Exact preservation of every output and the final learned state of a finite trace. -/
theorem run_refines
    (refinement : ExactRefinement source target mapState mapOutput)
    (initial : State) (events : List (Event Action Evidence)) :
    mapRun mapState mapOutput (run source initial events) =
      run target (mapState initial) events := by
  induction events generalizing initial with
  | nil => rfl
  | cons event events inductionHypothesis =>
      simp only [run]
      have first := advance_refines refinement initial event
      rcases firstState : advance source initial event with ⟨sourceOutput, sourceNext⟩
      have macroFirst :
          advance target (mapState initial) event =
            (Option.map mapOutput sourceOutput, mapState sourceNext) := by
        rw [← first, firstState]
      have tail := inductionHypothesis sourceNext
      rcases tailResult : run source sourceNext events with ⟨tailOutputs, tailState⟩
      rw [tailResult] at tail
      rcases targetTail : run target (mapState sourceNext) events with
        ⟨macroOutputs, macroState⟩
      rw [targetTail] at tail
      injection tail with outputEquality stateEquality
      rw [macroFirst]
      dsimp [mapRun]
      rw [targetTail]
      rw [outputEquality, stateEquality]

/-- The execution part of a refinement is a necessary projection of the contract. -/
theorem refinement_requires_step_commutation
    (refinement : ExactRefinement source target mapState mapOutput)
    (state : State) (action : Action) (allowed : source.stepAllowed state action = true) :
    mapStep mapState mapOutput (source.step state action) =
      target.step (mapState state) action :=
  refinement.step_commutes state action allowed

/-- The learning part is independently necessary: a `Step` theorem alone cannot supply it. -/
theorem refinement_requires_learn_commutation
    (refinement : ExactRefinement source target mapState mapOutput)
    (state : State) (evidence : Evidence) (allowed : source.learnAllowed state evidence = true) :
    mapState (source.learn state evidence) = target.learn (mapState state) evidence :=
  refinement.learn_commutes state evidence allowed

/-- Mapping one result in two stages equals mapping it through the composite map. -/
theorem mapStep_composes
    (firstState : State -> MiddleState) (secondState : MiddleState -> MacroState)
    (firstOutput : Output -> MiddleOutput) (secondOutput : MiddleOutput -> MacroOutput)
    (result : Output × State) :
    mapStep (secondState ∘ firstState) (secondOutput ∘ firstOutput) result =
      mapStep secondState secondOutput (mapStep firstState firstOutput result) := by
  cases result
  rfl

/-- Exact refinements compose; no new semantic or learning premise is inserted. -/
theorem ExactRefinement.compose
    (first : ExactRefinement source middle firstState firstOutput)
    (second : ExactRefinement middle target secondState secondOutput) :
    ExactRefinement source target (secondState ∘ firstState) (secondOutput ∘ firstOutput) where
  stepAllowed_iff := by
    intro state action
    exact (first.stepAllowed_iff state action).trans
      (second.stepAllowed_iff (firstState state) action)
  learnAllowed_iff := by
    intro state evidence
    exact (first.learnAllowed_iff state evidence).trans
      (second.learnAllowed_iff (firstState state) evidence)
  step_commutes := by
    intro state action allowed
    calc
      mapStep (secondState ∘ firstState) (secondOutput ∘ firstOutput)
          (source.step state action) =
          mapStep secondState secondOutput
            (mapStep firstState firstOutput (source.step state action)) :=
        mapStep_composes firstState secondState firstOutput secondOutput _
      _ = mapStep secondState secondOutput (middle.step (firstState state) action) := by
        rw [first.step_commutes state action allowed]
      _ = target.step (secondState (firstState state)) action :=
        second.step_commutes (firstState state) action
          ((first.stepAllowed_iff state action).mp allowed)
  learn_commutes := by
    intro state evidence allowed
    calc
      (secondState ∘ firstState) (source.learn state evidence) =
          secondState (firstState (source.learn state evidence)) := rfl
      _ = secondState (middle.learn (firstState state) evidence) := by
        rw [first.learn_commutes state evidence allowed]
      _ = target.learn (secondState (firstState state)) evidence :=
        second.learn_commutes (firstState state) evidence
          ((first.learnAllowed_iff state evidence).mp allowed)

/-- Finite-trace preservation is stable under two exact abstraction steps. -/
theorem run_refines_composed
    (first : ExactRefinement source middle firstState firstOutput)
    (second : ExactRefinement middle target secondState secondOutput)
    (initial : State) (events : List (Event Action Evidence)) :
    mapRun (secondState ∘ firstState) (secondOutput ∘ firstOutput)
      (run source initial events) =
      run target (secondState (firstState initial)) events :=
  run_refines (first.compose second) initial events

end HSWM.SemanticQuotient
