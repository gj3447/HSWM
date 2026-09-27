import HSWMSemanticQuotient

/-!
# Finite multiscale map simulation witness

This file formalizes only the operational part of the user's `M = Map`
direction: a physical, synaptic, or semantic view can be substituted for
another view over a declared finite trace when it preserves declared event
admission, observations, and transitions.  It does not certify that an agent
is the absolute outermost simulator, that any chosen layer is a brain, or that
this witness establishes HSWM efficacy.

The examples deliberately include both a useful noninjective quotient and a
lossy map that fails.  Thus a layer map need not reconstruct every microstate,
but it must retain the information needed by the declared prediction task.
-/

namespace HSWM.MultiscaleSimulation

open HSWM.SemanticQuotient

abbrev Action := Unit
abbrev Evidence := Bool

/-- A two-component micro state; the second component is unobserved here. -/
abbrev MicroState := Bool × Bool
abbrev SynapticState := Bool × Unit
abbrev SemanticState := Bool

/-- A declared outcome changes the retained bit while preserving hidden state. -/
def microDynamics : Dynamics MicroState Action Bool Evidence where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state.1, (!state.1, state.2))
  learn := fun state evidence => (evidence, state.2)

/-- The intermediate layer has its own carrier, not merely an identity alias. -/
def synapticDynamics : Dynamics SynapticState Action Bool Evidence where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state.1, (!state.1, ()))
  learn := fun _ evidence => (evidence, ())

/-- The semantic layer retains only the bit needed by the declared task. -/
def semanticDynamics : Dynamics SemanticState Action Bool Evidence where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state, !state)
  learn := fun _ evidence => evidence

def microToSynaptic : MicroState -> SynapticState := fun state => (state.1, ())
def synapticToSemantic : SynapticState -> SemanticState := Prod.fst
def outputMap : Bool -> Bool := id

/-- `M = Map` may be noninjective while still preserving this declared task. -/
theorem microToSynaptic_noninjective :
    microToSynaptic (true, false) = microToSynaptic (true, true) ∧
      (true, false) ≠ (true, true) := by decide

/-- The discarded micro component never changes the declared visible dynamics. -/
theorem microToSynapticRefinement :
    ExactRefinement microDynamics synapticDynamics microToSynaptic outputMap where
  stepAllowed_iff := by intro state action; simp [microDynamics, synapticDynamics]
  learnAllowed_iff := by intro state evidence; simp [microDynamics, synapticDynamics]
  step_commutes := by intro state action allowed; cases state <;> simp [microDynamics, synapticDynamics, microToSynaptic, outputMap, mapStep] at *
  learn_commutes := by intro state evidence allowed; cases state <;> cases evidence <;> simp [microDynamics, synapticDynamics, microToSynaptic]

/-- A second abstraction can preserve the same operational meaning. -/
theorem synapticToSemanticRefinement :
    ExactRefinement synapticDynamics semanticDynamics synapticToSemantic outputMap where
  stepAllowed_iff := by intro state action; simp [synapticDynamics, semanticDynamics]
  learnAllowed_iff := by intro state evidence; simp [synapticDynamics, semanticDynamics]
  step_commutes := by intro state action allowed; cases state <;> rfl
  learn_commutes := by intro state evidence allowed; cases state <;> cases evidence <;> rfl

theorem physicalSynapticSemanticRefinement :
    ExactRefinement microDynamics semanticDynamics
      (synapticToSemantic ∘ microToSynaptic) (outputMap ∘ outputMap) :=
  microToSynapticRefinement.compose synapticToSemanticRefinement

/-- Any declared finite Step/Learn interleaving has the same mapped trace. -/
theorem physicalSynapticSemantic_trace_preserved
    (initial : MicroState) (events : List (Event Action Evidence)) :
    mapRun (synapticToSemantic ∘ microToSynaptic) (outputMap ∘ outputMap)
      (run microDynamics initial events) =
      run semanticDynamics ((synapticToSemantic ∘ microToSynaptic) initial) events :=
  run_refines physicalSynapticSemanticRefinement initial events

/-- A concrete non-no-op learning trace; this is a finite model, not a brain claim. -/
theorem concrete_nontrivial_learning_trace :
    mapRun (synapticToSemantic ∘ microToSynaptic) (outputMap ∘ outputMap)
      (run microDynamics (true, false) [.step (), .learn true, .step ()]) =
      run semanticDynamics true [.step (), .learn true, .step ()] :=
  physicalSynapticSemantic_trace_preserved (true, false) [.step (), .learn true, .step ()]

/-- The Learn event changes the post-Step retained bit from false back to true. -/
theorem concrete_nontrivial_learning_trace_evaluates :
    run microDynamics (true, false) [.step (), .learn true, .step ()] =
      ([some true, none, some true], (false, false)) ∧
    run semanticDynamics true [.step (), .learn true, .step ()] =
      ([some true, none, some true], false) := by decide

/-- A map that erases the predictive bit cannot preserve a Bool observation. -/
def erasedStateDynamics : Dynamics Unit Action Bool Evidence where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun _ _ => (false, ())
  learn := fun _ _ => ()

def eraseState : Bool -> Unit := fun _ => ()

def visibleBoolDynamics : Dynamics Bool Action Bool Evidence where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state, state)
  learn := fun state _ => state

/-- The loss is witnessed by a one-event trace, not hidden by the quotient. -/
theorem erasing_predictive_bit_fails :
    ¬ ExactRefinement visibleBoolDynamics erasedStateDynamics eraseState outputMap := by
  intro refinement
  have commutes := refinement.step_commutes true () (by decide)
  simp [visibleBoolDynamics, erasedStateDynamics, eraseState, outputMap, mapStep] at commutes

/-- The same loss is directly observable on a finite trace. -/
theorem erased_predictive_bit_has_loss_trace :
    mapRun eraseState outputMap (run visibleBoolDynamics true [.step ()]) ≠
      run erasedStateDynamics () [.step ()] := by decide

end HSWM.MultiscaleSimulation
