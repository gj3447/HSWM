import HSWMOperationalAbstraction
import HSWMBehavioralMinimality

/-!
# A guard-observing quotient for deterministic Step/Learn dynamics

The existing output-only behavioral quotient can merge an accepted Learn with
a rejected Learn. Here each event exposes its admission Boolean as well as its
output. Equality of all finite such traces yields the four operational fibre
laws, and therefore an exact abstraction given an explicit representative
section. This is relative to the supplied deterministic Dynamics and interface.
It does not identify the external world, validate an actual HSWM read planner,
preserve undeclared provenance, or establish efficacy or a unique AI architecture.
-/

namespace HSWM.OperationalQuotient

open HSWM.SemanticQuotient HSWM.OperationalAbstraction

universe u

variable {State Action Output Evidence : Type u}

def eventAllowed (dynamics : Dynamics State Action Output Evidence)
    (state : State) : Event Action Evidence → Bool
  | .step action => dynamics.stepAllowed state action
  | .learn evidence => dynamics.learnAllowed state evidence

def observation (dynamics : Dynamics State Action Output Evidence)
    (state : State) (event : Event Action Evidence) : Bool × Option Output :=
  (eventAllowed dynamics state event, (advance dynamics state event).1)

def observedTrace (dynamics : Dynamics State Action Output Evidence) :
    State → List (Event Action Evidence) → List (Bool × Option Output)
  | _, [] => []
  | state, event :: events => observation dynamics state event ::
      observedTrace dynamics (advance dynamics state event).2 events

def OperationallyEquivalent (dynamics : Dynamics State Action Output Evidence)
    (left right : State) : Prop :=
  ∀ events, observedTrace dynamics left events = observedTrace dynamics right events

def operationalSetoid (dynamics : Dynamics State Action Output Evidence) : Setoid State where
  r := OperationallyEquivalent dynamics
  iseqv := ⟨fun _ _ => rfl, fun h events => (h events).symm,
    fun h₁ h₂ events => (h₁ events).trans (h₂ events)⟩

def OperationalClass (dynamics : Dynamics State Action Output Evidence) : Type u :=
  Quotient (operationalSetoid dynamics)

def operationalQuotient (dynamics : Dynamics State Action Output Evidence) :
    State → OperationalClass dynamics := Quotient.mk _

theorem quotient_eq_iff (dynamics : Dynamics State Action Output Evidence)
    {left right : State} :
    operationalQuotient dynamics left = operationalQuotient dynamics right ↔
      OperationallyEquivalent dynamics left right := by
  constructor
  · intro same
    exact Quotient.exact same
  · intro equivalent
    exact Quotient.sound equivalent

theorem equivalent_observation (dynamics : Dynamics State Action Output Evidence)
    {left right : State} (equivalent : OperationallyEquivalent dynamics left right)
    (event : Event Action Evidence) :
    observation dynamics left event = observation dynamics right event := by
  have h := equivalent [event]
  exact (List.cons.inj h).1

theorem equivalent_successor (dynamics : Dynamics State Action Output Evidence)
    {left right : State} (equivalent : OperationallyEquivalent dynamics left right)
    (event : Event Action Evidence) :
    OperationallyEquivalent dynamics (advance dynamics left event).2
      (advance dynamics right event).2 := by
  intro events
  exact (List.cons.inj (equivalent (event :: events))).2

theorem observedTrace_outputs (dynamics : Dynamics State Action Output Evidence)
    (state : State) (events : List (Event Action Evidence)) :
    (observedTrace dynamics state events).map Prod.snd = (run dynamics state events).1 := by
  induction events generalizing state with
  | nil => rfl
  | cons event events ih =>
      simp only [observedTrace, List.map_cons, observation, run, ih]

theorem operational_equivalence_implies_output_equivalence
    (dynamics : Dynamics State Action Output Evidence) {left right : State}
    (equivalent : OperationallyEquivalent dynamics left right) :
    HSWM.BehavioralMinimality.BehaviorallyEquivalent dynamics left right := by
  intro events
  simpa only [observedTrace_outputs] using
    congrArg (List.map Prod.snd) (equivalent events)

/-- Closing the gap between output-only minimality and full operational guards.
Raw transitions at rejected events need not be preserved: neither Dynamics.run
nor ExactRefinement exposes them. -/
theorem operational_quotient_fibre_criterion
    (dynamics : Dynamics State Action Output Evidence) :
    FibreCriterion dynamics (operationalQuotient dynamics) := by
  constructor
  · intro left right action same
    exact congrArg Prod.fst (equivalent_observation dynamics
      ((quotient_eq_iff dynamics).mp same) (.step action))
  · intro left right evidence same
    exact congrArg Prod.fst (equivalent_observation dynamics
      ((quotient_eq_iff dynamics).mp same) (.learn evidence))
  · intro left right action same allowed
    have equivalent := (quotient_eq_iff dynamics).mp same
    have obs := equivalent_observation dynamics equivalent (.step action)
    have guards : dynamics.stepAllowed left action = dynamics.stepAllowed right action :=
      congrArg Prod.fst obs
    have rightAllowed : dynamics.stepAllowed right action = true := guards.symm.trans allowed
    constructor
    · have outputs := congrArg Prod.snd obs
      simpa [observation, advance, allowed, rightAllowed] using outputs
    · apply (quotient_eq_iff dynamics).mpr
      simpa [advance, allowed, rightAllowed] using
        equivalent_successor dynamics equivalent (.step action)
  · intro left right evidence same allowed
    have equivalent := (quotient_eq_iff dynamics).mp same
    have guards : dynamics.learnAllowed left evidence = dynamics.learnAllowed right evidence :=
      congrArg Prod.fst (equivalent_observation dynamics equivalent (.learn evidence))
    have rightAllowed : dynamics.learnAllowed right evidence = true := guards.symm.trans allowed
    apply (quotient_eq_iff dynamics).mpr
    simpa [advance, allowed, rightAllowed] using
      equivalent_successor dynamics equivalent (.learn evidence)

/-- Construction is conditional on a supplied section, not an implemented
algorithm for deciding equivalence or finding representatives. -/
theorem operational_quotient_refines (dynamics : Dynamics State Action Output Evidence)
    (representative : OperationalClass dynamics → State)
    (retraction : ∀ layer, operationalQuotient dynamics (representative layer) = layer) :
    ExactRefinement dynamics
      (representativeDynamics dynamics (operationalQuotient dynamics) representative)
      (operationalQuotient dynamics) id :=
  criterion_builds_refinement representative retraction (operational_quotient_fibre_criterion dynamics)

theorem operational_quotient_preserves_run (dynamics : Dynamics State Action Output Evidence)
    (representative : OperationalClass dynamics → State)
    (retraction : ∀ layer, operationalQuotient dynamics (representative layer) = layer)
    (state : State) (events : List (Event Action Evidence)) :
    mapRun (operationalQuotient dynamics) id (run dynamics state events) =
      run (representativeDynamics dynamics (operationalQuotient dynamics) representative)
        (operationalQuotient dynamics state) events :=
  run_refines (operational_quotient_refines dynamics representative retraction) state events

/-- An exact refinement preserves the additional admission observations too. -/
theorem exact_refinement_preserves_observedTrace
    {Layer : Type u} {source : Dynamics State Action Output Evidence}
    {target : Dynamics Layer Action Output Evidence} {q : State → Layer}
    (refinement : ExactRefinement source target q id)
    (state : State) (events : List (Event Action Evidence)) :
    observedTrace source state events = observedTrace target (q state) events := by
  induction events generalizing state with
  | nil => rfl
  | cons event events ih =>
      have advanced := advance_refines refinement state event
      have outputs : (advance source state event).1 = (advance target (q state) event).1 := by
        simpa using congrArg Prod.fst advanced
      have successors : q (advance source state event).2 = (advance target (q state) event).2 :=
        congrArg Prod.snd advanced
      have guards : eventAllowed source state event = eventAllowed target (q state) event := by
        cases event with
        | step action =>
            exact Bool.eq_iff_iff.mpr (refinement.stepAllowed_iff state action)
        | learn evidence =>
            exact Bool.eq_iff_iff.mpr (refinement.learnAllowed_iff state evidence)
      simp only [observedTrace, observation, guards, outputs]
      rw [ih, successors]

theorem exact_refinement_collision_is_operationally_equivalent
    {Layer : Type u} {source : Dynamics State Action Output Evidence}
    {target : Dynamics Layer Action Output Evidence} {q : State → Layer}
    (refinement : ExactRefinement source target q id) {left right : State}
    (same : q left = q right) : OperationallyEquivalent source left right := by
  intro events
  rw [exact_refinement_preserves_observedTrace refinement,
    exact_refinement_preserves_observedTrace refinement, same]

/-- A finite distinguishing trace refutes every exact target for this map. -/
theorem distinguishing_trace_refutes_exact_abstraction
    {Layer : Type u} (source : Dynamics State Action Output Evidence) (q : State → Layer)
    {left right : State} (same : q left = q right) (events : List (Event Action Evidence))
    (different : observedTrace source left events ≠ observedTrace source right events) :
    ¬ ∃ target : Dynamics Layer Action Output Evidence, ExactRefinement source target q id := by
  rintro ⟨target, refinement⟩
  exact different (exact_refinement_collision_is_operationally_equivalent refinement same events)

/-- Every exact operational abstraction has a well-defined map from its
reachable codes onto these observational classes. -/
def refinementFactor {Layer : Type u} (source : Dynamics State Action Output Evidence)
    (decode : Layer → State) : Layer → OperationalClass source :=
  fun layer => operationalQuotient source (decode layer)

theorem refinementFactor_on_source {Layer : Type u}
    {source : Dynamics State Action Output Evidence} {target : Dynamics Layer Action Output Evidence}
    {q : State → Layer} (refinement : ExactRefinement source target q id)
    (decode : Layer → State) (retraction : ∀ state, q (decode (q state)) = q state) (state : State) :
    refinementFactor source decode (q state) = operationalQuotient source state := by
  apply (quotient_eq_iff source).mpr
  exact exact_refinement_collision_is_operationally_equivalent refinement (retraction state)

/-- The old output-only quotient really loses admission information. -/
theorem output_equivalence_does_not_imply_operational_equivalence :
    HSWM.BehavioralMinimality.BehaviorallyEquivalent
      HSWM.BehavioralMinimality.guardOnlyDynamics false true ∧
    ¬ OperationallyEquivalent HSWM.BehavioralMinimality.guardOnlyDynamics false true := by
  constructor
  · exact HSWM.BehavioralMinimality.guard_only_states_are_output_behaviorally_equivalent
  · intro equivalent
    have guards := congrArg Prod.fst (equivalent_observation _ equivalent (.learn true))
    simp [observation, eventAllowed, HSWM.BehavioralMinimality.guardOnlyDynamics] at guards

/-- Keeping only the currently visible bit cannot support exact learning. -/
theorem visible_bit_has_no_exact_learning_abstraction :
    ¬ ∃ target : Dynamics Bool Unit Bool Bool,
      ExactRefinement HSWM.BehavioralMinimality.learnSensitiveDynamics target Prod.fst id := by
  apply distinguishing_trace_refutes_exact_abstraction
    HSWM.BehavioralMinimality.learnSensitiveDynamics Prod.fst
    (left := (false, false)) (right := (false, true)) rfl [.learn true, .step ()]
  decide

end HSWM.OperationalQuotient
