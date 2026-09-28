import HSWMSemanticQuotient

/-!
# Behavioral minimality for exact local operational encodings

For a declared `Dynamics`, two states are behaviorally equivalent precisely
when no finite interleaving of observable Step and outcome-qualified Learn
events distinguishes their output traces.  The quotient is therefore a
mathematical minimal information object for this declared observation contract.

This does not produce an executable finite minimizer, establish a byte/token
cost optimum, or assert that the declared events/readouts are sufficient for an
external world.  It applies only to an encoding that explicitly reconstructs
every finite observable trace.  This file observes `run` outputs only.
Admission/rejection guards, provenance, permissions, lineage, and other
canonical fields must be included in the observable trace before this quotient
can be used to minimize them; output equivalence alone is not the full
operational/canonical-state fibre criterion.
-/

namespace HSWM.BehavioralMinimality

open HSWM.SemanticQuotient

universe u

variable {State Action Output Evidence : Type u}

/-- Equality of every finite observable Step/Learn trace. -/
def BehaviorallyEquivalent (dynamics : Dynamics State Action Output Evidence)
    (left right : State) : Prop :=
  ∀ events : List (Event Action Evidence),
    (run dynamics left events).1 = (run dynamics right events).1

theorem behavioral_refl (dynamics : Dynamics State Action Output Evidence) (state : State) :
    BehaviorallyEquivalent dynamics state state := by
  intro events
  rfl

theorem behavioral_symm (dynamics : Dynamics State Action Output Evidence) {left right : State}
    (equivalent : BehaviorallyEquivalent dynamics left right) :
    BehaviorallyEquivalent dynamics right left := by
  intro events
  exact (equivalent events).symm

theorem behavioral_trans (dynamics : Dynamics State Action Output Evidence) {first second third : State}
    (left : BehaviorallyEquivalent dynamics first second)
    (right : BehaviorallyEquivalent dynamics second third) :
    BehaviorallyEquivalent dynamics first third := by
  intro events
  exact (left events).trans (right events)

def behavioralSetoid (dynamics : Dynamics State Action Output Evidence) : Setoid State where
  r := BehaviorallyEquivalent dynamics
  iseqv := ⟨behavioral_refl dynamics, behavioral_symm dynamics, behavioral_trans dynamics⟩

/-- The coarsest quotient for the declared finite-trace observation interface. -/
def BehaviorClass (dynamics : Dynamics State Action Output Evidence) : Type u :=
  Quotient (behavioralSetoid dynamics)

def behavioralQuotient (dynamics : Dynamics State Action Output Evidence) : State → BehaviorClass dynamics :=
  Quotient.mk _

theorem behavioralQuotient_eq_iff (dynamics : Dynamics State Action Output Evidence)
    {left right : State} :
    behavioralQuotient dynamics left = behavioralQuotient dynamics right ↔
      BehaviorallyEquivalent dynamics left right := by
  constructor
  · intro equal
    exact Quotient.exact equal
  · intro equivalent
    exact Quotient.sound equivalent

/-- Equivalent states give the same immediately visible event result. -/
theorem behavioral_advance_output_congruent (dynamics : Dynamics State Action Output Evidence)
    {left right : State} (equivalent : BehaviorallyEquivalent dynamics left right)
    (event : Event Action Evidence) :
    (advance dynamics left event).1 = (advance dynamics right event).1 := by
  have trace := equivalent [event]
  simpa [run] using congrArg List.head? trace

/-- Behavioral equivalence is closed under every declared Step or Learn successor. -/
theorem behavioral_advance_successor_congruent (dynamics : Dynamics State Action Output Evidence)
    {left right : State} (equivalent : BehaviorallyEquivalent dynamics left right)
    (event : Event Action Evidence) :
    BehaviorallyEquivalent dynamics (advance dynamics left event).2 (advance dynamics right event).2 := by
  intro events
  have trace := equivalent (event :: events)
  change (advance dynamics left event).1 :: (run dynamics (advance dynamics left event).2 events).1 =
    (advance dynamics right event).1 :: (run dynamics (advance dynamics right event).2 events).1 at trace
  exact (List.cons.inj trace).2

/-- An encoding is exact only when decoding its code reproduces every finite observable trace. -/
def ExactOperationalEncoding (dynamics : Dynamics State Action Output Evidence)
    {Code : Type u} (encode : State → Code) (decode : Code → State) : Prop :=
  ∀ state events,
    (run dynamics (decode (encode state)) events).1 = (run dynamics state events).1

/-- An exact encoding cannot identify two behaviorally distinct source states. -/
theorem exact_encoding_collision_is_behaviorally_equivalent
    (dynamics : Dynamics State Action Output Evidence) {Code : Type u}
    (encode : State → Code) (decode : Code → State)
    (exact : ExactOperationalEncoding dynamics encode decode) {left right : State}
    (sameCode : encode left = encode right) :
    BehaviorallyEquivalent dynamics left right := by
  intro events
  calc
    (run dynamics left events).1 = (run dynamics (decode (encode left)) events).1 :=
      (exact left events).symm
    _ = (run dynamics (decode (encode right)) events).1 := by rw [sameCode]
    _ = (run dynamics right events).1 := exact right events

/-- Only codes actually reached from source states are relevant to the universal property. -/
def ReachableCode {Code : Type u} (encode : State → Code) : Type u :=
  { code : Code // ∃ state, encode state = code }

/-- Every exact encoding factors through the behavioral quotient on its reachable image. -/
def quotientFactor (dynamics : Dynamics State Action Output Evidence)
    {Code : Type u} (encode : State → Code) (decode : Code → State) :
    ReachableCode encode → BehaviorClass dynamics := fun reachable =>
  behavioralQuotient dynamics (decode reachable.1)

theorem quotientFactor_on_source (dynamics : Dynamics State Action Output Evidence)
    {Code : Type u} (encode : State → Code) (decode : Code → State)
    (exact : ExactOperationalEncoding dynamics encode decode) (state : State) :
    quotientFactor dynamics encode decode ⟨encode state, ⟨state, rfl⟩⟩ =
      behavioralQuotient dynamics state := by
  unfold quotientFactor
  apply (behavioralQuotient_eq_iff dynamics).mpr
  exact exact state

/-- The reachable image of an exact encoding covers every behavioral class. -/
theorem quotientFactor_surjective (dynamics : Dynamics State Action Output Evidence)
    {Code : Type u} (encode : State → Code) (decode : Code → State)
    (exact : ExactOperationalEncoding dynamics encode decode) :
    Function.Surjective (quotientFactor dynamics encode decode) := by
  intro targetClass
  refine Quotient.inductionOn targetClass ?_
  intro state
  exact ⟨⟨encode state, ⟨state, rfl⟩⟩,
    quotientFactor_on_source dynamics encode decode exact state⟩

/-- The factor is forced on every reachable code: exact encodings cannot retain less behavior. -/
theorem quotientFactor_unique_on_reachable (dynamics : Dynamics State Action Output Evidence)
    {Code : Type u} (encode : State → Code) (decode : Code → State)
    (exact : ExactOperationalEncoding dynamics encode decode)
    (factor : ReachableCode encode → BehaviorClass dynamics)
    (agrees : ∀ state, factor ⟨encode state, ⟨state, rfl⟩⟩ = behavioralQuotient dynamics state)
    (reachable : ReachableCode encode) :
    factor reachable = quotientFactor dynamics encode decode reachable := by
  rcases reachable with ⟨code, state, encoded⟩
  subst code
  rw [agrees state, quotientFactor_on_source dynamics encode decode exact state]

/-- A finite Step-only merge can fail once Learn makes a hidden bit behaviorally visible. -/
def learnSensitiveDynamics : Dynamics (Bool × Bool) Unit Bool Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => (state.1, state)
  learn := fun state evidence => (state.2 != evidence, state.2)

def firstBitRead : Bool × Bool → Bool := Prod.fst

theorem same_step_read_not_behaviorally_sufficient_after_learn :
    firstBitRead (false, false) = firstBitRead (false, true) ∧
    ¬ BehaviorallyEquivalent learnSensitiveDynamics (false, false) (false, true) := by
  constructor
  · rfl
  · intro equivalent
    have trace := equivalent [.learn true, .step ()]
    simp [learnSensitiveDynamics, run, advance] at trace

/-- A guard can differ while output-only traces remain identical. -/
def guardOnlyDynamics : Dynamics Bool Unit Bool Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun state _ => state
  step := fun state _ => (false, state)
  learn := fun state _ => state

theorem guard_only_states_are_output_behaviorally_equivalent :
    BehaviorallyEquivalent guardOnlyDynamics false true := by
  intro events
  induction events with
  | nil => rfl
  | cons event events ih =>
      cases event with
      | step action =>
          simpa [run, advance, guardOnlyDynamics] using congrArg (List.cons (some false)) ih
      | learn evidence =>
          simpa [run, advance, guardOnlyDynamics] using congrArg (List.cons none) ih

/-- Therefore output-only minimality must not be mistaken for guard preservation. -/
theorem output_behavioral_equivalence_does_not_preserve_learn_guard :
    BehaviorallyEquivalent guardOnlyDynamics false true ∧
      guardOnlyDynamics.learnAllowed false true = false ∧
      guardOnlyDynamics.learnAllowed true true = true := by
  exact ⟨guard_only_states_are_output_behaviorally_equivalent, rfl, rfl⟩

end HSWM.BehavioralMinimality
