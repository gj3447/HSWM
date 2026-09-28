import HSWMSemanticQuotient

/-!
# Operational abstraction from local fibre laws

This is a task-relative criterion for a layer map.  It constructs an abstract
`Dynamics` only when guards, allowed step outputs/successors, and allowed learn
successors are constant on every fibre of the map.  The representative is an
explicit section; no choice principle or claim about real LLMs is used.
-/

namespace HSWM.OperationalAbstraction

open HSWM.SemanticQuotient

universe u

variable {State Layer Action Output Evidence : Type u}

/-- The operational information that must not vary within a proposed layer
map's fibres.  Step output preservation uses the identity output map; a typed
output translation can be composed outside this criterion. -/
structure FibreCriterion (source : Dynamics State Action Output Evidence)
    (q : State → Layer) : Prop where
  step_guard : ∀ s t a, q s = q t → source.stepAllowed s a = source.stepAllowed t a
  learn_guard : ∀ s t e, q s = q t → source.learnAllowed s e = source.learnAllowed t e
  step_result : ∀ s t a, q s = q t → source.stepAllowed s a = true →
    (source.step s a).1 = (source.step t a).1 ∧
      q (source.step s a).2 = q (source.step t a).2
  learn_result : ∀ s t e, q s = q t → source.learnAllowed s e = true →
    q (source.learn s e) = q (source.learn t e)

/-- Build the layer dynamics by reading a chosen concrete representative for
each layer state.  The section law below is what makes this representative
construction cover every mapped concrete state. -/
def representativeDynamics (source : Dynamics State Action Output Evidence)
    (q : State → Layer) (representative : Layer → State) :
    Dynamics Layer Action Output Evidence where
  stepAllowed := fun layer action => source.stepAllowed (representative layer) action
  learnAllowed := fun layer evidence => source.learnAllowed (representative layer) evidence
  step := fun layer action =>
    let result := source.step (representative layer) action
    (result.1, q result.2)
  learn := fun layer evidence => q (source.learn (representative layer) evidence)

/-- Fibre constancy is sufficient: an explicit representative section produces
an exact operational abstraction. -/
theorem criterion_builds_refinement
    {source : Dynamics State Action Output Evidence} {q : State → Layer}
    (representative : Layer → State) (retraction : ∀ layer, q (representative layer) = layer)
    (criterion : FibreCriterion source q) :
    ExactRefinement source (representativeDynamics source q representative) q id := by
  constructor
  · intro state action
    change source.stepAllowed state action = true ↔
      source.stepAllowed (representative (q state)) action = true
    rw [criterion.step_guard state (representative (q state)) action (retraction (q state)).symm]
  · intro state evidence
    change source.learnAllowed state evidence = true ↔
      source.learnAllowed (representative (q state)) evidence = true
    rw [criterion.learn_guard state (representative (q state)) evidence (retraction (q state)).symm]
  · intro state action allowed
    change mapStep q id (source.step state action) =
      (representativeDynamics source q representative).step (q state) action
    rcases criterion.step_result state (representative (q state)) action (retraction (q state)).symm allowed
      with ⟨output_eq, successor_eq⟩
    simp [representativeDynamics, mapStep, output_eq, successor_eq]
  · intro state evidence allowed
    change q (source.learn state evidence) =
      (representativeDynamics source q representative).learn (q state) evidence
    exact criterion.learn_result state (representative (q state)) evidence (retraction (q state)).symm allowed

/-- Every exact abstraction forces all four fibre laws.  This is the necessity
direction; it holds for an arbitrary target dynamics, not only the constructed
representative one. -/
theorem refinement_implies_criterion
    {source : Dynamics State Action Output Evidence} {target : Dynamics Layer Action Output Evidence}
    {q : State → Layer} (refinement : ExactRefinement source target q id) :
    FibreCriterion source q := by
  constructor
  · intro s t a hq
    by_cases hs : source.stepAllowed s a = true
    · have ht : source.stepAllowed t a = true := by
        have htarget := (refinement.stepAllowed_iff s a).mp hs
        exact (refinement.stepAllowed_iff t a).mpr (by simpa [hq] using htarget)
      simp [hs, ht]
    · have ht : source.stepAllowed t a ≠ true := by
        intro ht
        have : source.stepAllowed s a = true :=
          (refinement.stepAllowed_iff s a).mpr
            (hq ▸ (refinement.stepAllowed_iff t a).mp ht)
        exact hs this
      simp [hs, ht]
  · intro s t e hq
    by_cases hs : source.learnAllowed s e = true
    · have ht : source.learnAllowed t e = true := by
        have htarget := (refinement.learnAllowed_iff s e).mp hs
        exact (refinement.learnAllowed_iff t e).mpr (by simpa [hq] using htarget)
      simp [hs, ht]
    · have ht : source.learnAllowed t e ≠ true := by
        intro ht
        exact hs ((refinement.learnAllowed_iff s e).mpr
          (hq ▸ (refinement.learnAllowed_iff t e).mp ht))
      simp [hs, ht]
  · intro s t a hq allowed
    have left := refinement.step_commutes s a allowed
    have target_allowed : target.stepAllowed (q t) a = true := by
      have htarget := (refinement.stepAllowed_iff s a).mp allowed
      simpa [hq] using htarget
    have right := refinement.step_commutes t a
      ((refinement.stepAllowed_iff t a).mpr target_allowed)
    rw [hq] at left
    have pairs : mapStep q id (source.step s a) = mapStep q id (source.step t a) :=
      left.trans right.symm
    exact ⟨by simpa [mapStep] using congrArg Prod.fst pairs,
      by simpa [mapStep] using congrArg Prod.snd pairs⟩
  · intro s t e hq allowed
    have left := refinement.learn_commutes s e allowed
    have target_allowed : target.learnAllowed (q t) e = true := by
      have htarget := (refinement.learnAllowed_iff s e).mp allowed
      simpa [hq] using htarget
    have right := refinement.learn_commutes t e
      ((refinement.learnAllowed_iff t e).mpr target_allowed)
    rw [hq] at left
    exact left.trans right.symm

/-- The fibre criterion is exactly equivalent to the existence of some
same-output layer dynamics.  Sufficiency is constructive from the explicit
representative section; necessity does not use that representative. -/
theorem criterion_iff_exists_refinement
    {source : Dynamics State Action Output Evidence} {q : State → Layer}
    (representative : Layer → State) (retraction : ∀ layer, q (representative layer) = layer) :
    FibreCriterion source q ↔
      ∃ target : Dynamics Layer Action Output Evidence, ExactRefinement source target q id := by
  constructor
  · intro criterion
    exact ⟨representativeDynamics source q representative,
      criterion_builds_refinement representative retraction criterion⟩
  · rintro ⟨target, refinement⟩
    exact refinement_implies_criterion refinement

/-- Once the criterion is met, existing trace refinement transports every
finite interleaving of Step and outcome-qualified Learn events. -/
theorem criterion_preserves_run
    {source : Dynamics State Action Output Evidence} {q : State → Layer}
    (representative : Layer → State) (retraction : ∀ layer, q (representative layer) = layer)
    (criterion : FibreCriterion source q) (initial : State) (events : List (Event Action Evidence)) :
    mapRun q id (run source initial events) =
      run (representativeDynamics source q representative) (q initial) events :=
  run_refines (criterion_builds_refinement representative retraction criterion) initial events

/-- A Step-only agreement can still fail on the next Learn transition. -/
def stepOnlySource : Dynamics Bool Unit Unit Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => ((), state)
  learn := fun _ evidence => evidence

def stepOnlyTarget : Dynamics Bool Unit Unit Bool where
  stepAllowed := fun _ _ => true
  learnAllowed := fun _ _ => true
  step := fun state _ => ((), state)
  learn := fun state _ => state

theorem step_only_agreement :
    (∀ s a, stepOnlySource.stepAllowed s a = stepOnlyTarget.stepAllowed s a) ∧
    (∀ s a, stepOnlySource.step s a = stepOnlyTarget.step s a) := by
  constructor <;> intro s a <;> cases s <;> cases a <;> rfl

theorem step_only_agreement_does_not_refine_learning :
    ¬ ExactRefinement stepOnlySource stepOnlyTarget id id := by
  intro refinement
  have h := refinement.learn_commutes false true (by decide)
  simp [stepOnlySource, stepOnlyTarget] at h

end HSWM.OperationalAbstraction
