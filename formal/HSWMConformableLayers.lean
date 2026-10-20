import HSWMSemanticQuotient

/-!
# Onion layers and conformability (Gell-Mann, 1996)

Gell-Mann's "Nature conformable to herself" (Complexity 1(4), 1996) makes two
separate claims about physical theory: nature is layered like an onion, and the
mathematics found useful at one layer suggests the mathematics of the next.
This file formalizes only their operational shape over finite traces:

* `OnionTower`: every deeper layer exactly refines the layer outside it, so any
  depth can be peeled to any outer layer (`refines_many`, `run_peels_many`).
* `FaithfulConformance`: one parametric template describes a layer exactly and
  without discarding layer state.  Then the template plus the layer parameter
  predicts that layer's whole observable trace and final state.
* Non-entailment: a deeper layer can refine its outer layer while no faithful
  description by the outer layer's template exists.  Conformability is an
  additional premise, not a consequence of layering.

It does not claim that physical layers, brains or real LLMs satisfy these
premises, and it does not prove a universal minimum-cost or beauty criterion.
-/

namespace HSWM.ConformableLayers

open HSWM.SemanticQuotient

universe u

variable {State Output Shape ShapeOutput Param Action Evidence : Type u}

/-- Identity is an exact refinement; peeling zero layers changes nothing. -/
theorem refinement_id (dynamics : Dynamics State Action Output Evidence) :
    ExactRefinement dynamics dynamics id id where
  stepAllowed_iff := fun _ _ => Iff.rfl
  learnAllowed_iff := fun _ _ => Iff.rfl
  step_commutes := fun _ _ _ => rfl
  learn_commutes := fun _ _ _ => rfl

/-- Layer `n + 1` lies inside layer `n`; `peel` is the declared layer Map. -/
structure OnionTower (Action Evidence : Type u) where
  State : Nat → Type u
  Output : Nat → Type u
  dyn : (n : Nat) → Dynamics (State n) Action (Output n) Evidence
  peel : (n : Nat) → State (n + 1) → State n
  peelOutput : (n : Nat) → Output (n + 1) → Output n
  refines : ∀ n, ExactRefinement (dyn (n + 1)) (dyn n) (peel n) (peelOutput n)

namespace OnionTower

/-- Peel `k` skins from layer `n + k` back to layer `n`. -/
def peelMany (tower : OnionTower Action Evidence) (n : Nat) :
    (k : Nat) → tower.State (n + k) → tower.State n
  | 0 => id
  | k + 1 => peelMany tower n k ∘ tower.peel (n + k)

def peelOutputMany (tower : OnionTower Action Evidence) (n : Nat) :
    (k : Nat) → tower.Output (n + k) → tower.Output n
  | 0 => id
  | k + 1 => peelOutputMany tower n k ∘ tower.peelOutput (n + k)

variable (tower : OnionTower Action Evidence)

/-- Any deeper layer exactly refines any outer layer: one may start the
simulation at whichever skin the task needs. -/
theorem refines_many (n : Nat) : (k : Nat) →
    ExactRefinement (tower.dyn (n + k)) (tower.dyn n)
      (tower.peelMany n k) (tower.peelOutputMany n k)
  | 0 => refinement_id (tower.dyn n)
  | k + 1 => (tower.refines (n + k)).compose (refines_many n k)

theorem run_peels_many (n k : Nat) (initial : tower.State (n + k))
    (events : List (Event Action Evidence)) :
    mapRun (tower.peelMany n k) (tower.peelOutputMany n k)
        (run (tower.dyn (n + k)) initial events) =
      run (tower.dyn n) (tower.peelMany n k initial) events :=
  run_refines (tower.refines_many n k) initial events

end OnionTower

/-- One template instance describes the layer exactly, and the encoding keeps
every layer state distinct ("the same mathematics", not only its shadow). -/
structure FaithfulConformance
    (layer : Dynamics State Action Output Evidence)
    (template : Param → Dynamics Shape Action ShapeOutput Evidence) (param : Param)
    (encode : State → Shape) (encodeOutput : Output → ShapeOutput) : Prop where
  injective : ∀ a b, encode a = encode b → a = b
  refinement : ExactRefinement layer (template param) encode encodeOutput

section Conformance

variable {layer : Dynamics State Action Output Evidence}
  {template : Param → Dynamics Shape Action ShapeOutput Evidence} {param : Param}
  {encode : State → Shape} {encodeOutput : Output → ShapeOutput}

/-- The template and the layer parameter predict the layer's observable trace. -/
theorem template_predicts_trace
    (conformance : FaithfulConformance layer template param encode encodeOutput)
    (initial : State) (events : List (Event Action Evidence)) :
    mapRun encode encodeOutput (run layer initial events) =
      run (template param) (encode initial) events :=
  run_refines conformance.refinement initial events

/-- Faithfulness additionally pins the layer's own final state. -/
theorem template_determines_final_state
    (conformance : FaithfulConformance layer template param encode encodeOutput)
    (initial : State) (events : List (Event Action Evidence)) (candidate : State)
    (predicted : encode candidate = (run (template param) (encode initial) events).2) :
    candidate = (run layer initial events).2 := by
  apply conformance.injective
  rw [predicted, ← template_predicts_trace conformance initial events]
  rfl

end Conformance

/-! ## Finite witnesses -/

/-- One shared template; the parameter selects static or flipping dynamics. -/
def template (flip : Bool) : Dynamics Bool Unit Bool Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state, if flip then !state else state)
  learn := fun _ evidence => evidence

/-- A layer with its own carrier, unrelated to `Bool` by definition. -/
inductive Spin where
  | up
  | down
deriving DecidableEq, Repr

def Spin.flip : Spin → Spin
  | .up => .down
  | .down => .up

def Spin.toBool : Spin → Bool
  | .up => true
  | .down => false

def spinLayer : Dynamics Spin Unit Bool Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state.toBool, state.flip)
  learn := fun _ evidence => if evidence then .up else .down

/-- A different carrier obeys the same template with a different parameter. -/
theorem spin_conforms : FaithfulConformance spinLayer template true Spin.toBool id where
  injective := by intro a b; cases a <;> cases b <;> decide
  refinement := {
    stepAllowed_iff := by intro _ _; simp [spinLayer, template]
    learnAllowed_iff := by intro _ _; simp [spinLayer, template]
    step_commutes := by
      intro state _ _; cases state <;> rfl
    learn_commutes := by
      intro _ evidence _; cases evidence <;> rfl }

theorem bool_static_conforms :
    FaithfulConformance (template false) template false id id where
  injective := fun _ _ h => h
  refinement := refinement_id (template false)

/-- The predicted trace for the spin layer, computed from the template alone. -/
theorem spin_trace_from_template :
    run (template true) (Spin.toBool .up) [.step (), .step (), .learn false, .step ()] =
      ([some true, some false, none, some false], true) := by decide

/-- A deeper layer with one extra hidden bit. -/
def innerLayer : Dynamics (Bool × Bool) Unit Bool Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state.1, (state.1, !state.2))
  learn := fun state evidence => (evidence, state.2)

/-- Layering holds: the inner layer exactly refines the outer static layer. -/
theorem inner_refines_outer : ExactRefinement innerLayer (template false) Prod.fst id where
  stepAllowed_iff := by intro _ _; simp [innerLayer, template]
  learnAllowed_iff := by intro _ _; simp [innerLayer, template]
  step_commutes := by intro state _ _; cases state; rfl
  learn_commutes := fun _ _ _ => rfl

/-- Four inner states cannot be kept distinct inside the outer template's carrier. -/
theorem no_faithful_bool_encoding (encode : Bool × Bool → Bool) :
    ¬ ∀ a b, encode a = encode b → a = b := by
  intro injective
  cases h1 : encode (false, false) <;> cases h2 : encode (false, true) <;>
    cases h3 : encode (true, false)
  all_goals first
    | exact absurd (injective _ _ (h1.trans h2.symm)) (by decide)
    | exact absurd (injective _ _ (h1.trans h3.symm)) (by decide)
    | exact absurd (injective _ _ (h2.trans h3.symm)) (by decide)

/-- Onion layering does not entail conformability to the outer template. -/
theorem onion_does_not_entail_conformance (flip : Bool)
    (encode : Bool × Bool → Bool) (encodeOutput : Bool → Bool) :
    ¬ FaithfulConformance innerLayer template flip encode encodeOutput :=
  fun conformance => no_faithful_bool_encoding encode conformance.injective

end HSWM.ConformableLayers
