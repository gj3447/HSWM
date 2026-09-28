import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Finset.Max
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

/-!
# Deterministic finite-candidate admission after a frozen evaluation round

This module deliberately contains no probability theorem.  A concentration
module must establish `CleanMeanEvent` from conditionally fresh samples.  Here
we prove what follows from that event and a concrete, bounded row-replacement
witness.  The executable selector reads `observed`, never `clean` or `truth`.

All gains and costs use one declared utility unit.  A caller must freeze the
candidate payloads, baseline, evaluator, costs, and radius before collecting
the rows; that causal/time binding is an integration obligation, not encoded by
these finite real arrays. `selectCertified` is a pure mathematical finite
selector over exact reals; it is not a claim of a TS-executable numeric
certificate. A later refinement needs conservative rounding and exact input
bindings.
-/

namespace HSWMStatisticalLearning.Selection

variable {Candidate : Type} {m n : Nat}

/-- A finite candidate family retains its actual payload at its stable index. -/
structure FrozenCandidates (Candidate : Type) (m : Nat) where
  payload : Fin m → Candidate
  cost : Fin m → ℝ

/-- Average over a nonempty finite evaluation row. -/
noncomputable def mean (n : Nat) (values : Fin n → ℝ) : ℝ :=
  (∑ i : Fin n, values i) / n

/-- The event supplied by the probabilistic layer for all frozen candidates. -/
def CleanMeanEvent (clean : Fin m → Fin n → ℝ) (target : Fin m → ℝ)
    (radius : ℝ) : Prop :=
  ∀ k, |mean n (clean k) - target k| ≤ radius

/-- At most `b` complete gain rows for a candidate may be replaced. -/
structure ReplacementWitness (clean observed : Fin m → Fin n → ℝ) (b : Nat) where
  bad : Fin m → Finset (Fin n)
  card_le : ∀ k, (bad k).card ≤ b
  agrees_outside : ∀ k i, i ∉ bad k → observed k i = clean k i

/-- Proposition-level availability of a concrete replacement witness. -/
def HasReplacementWitness (clean observed : Fin m → Fin n → ℝ) (b : Nat) : Prop :=
  Nonempty (ReplacementWitness clean observed b)

/-- Both the clean counterfactual gain and guard-visible observed gain are normalized. -/
def BoundedGains (clean observed : Fin m → Fin n → ℝ) : Prop :=
  (∀ k i, -1 ≤ clean k i ∧ clean k i ≤ 1) ∧
  (∀ k i, -1 ≤ observed k i ∧ observed k i ≤ 1)

/-- The deterministic change in a mean caused by at most `b` whole gain-row replacements. -/
theorem mean_replacement_bound {clean observed : Fin m → Fin n → ℝ} {b : Nat}
    (hn : 0 < n) (hbounded : BoundedGains clean observed)
    (hreplaced : ReplacementWitness clean observed b) (k : Fin m) :
    |mean n (observed k) - mean n (clean k)| ≤ (2 * b : ℝ) / n := by
  rcases hbounded with ⟨hclean, hobserved⟩
  let bad := hreplaced.bad k
  have hdiff_bound (i : Fin n) : |observed k i - clean k i| ≤ 2 := by
    rcases hclean k i with ⟨hclo, hchi⟩
    rcases hobserved k i with ⟨holo, hohi⟩
    rw [abs_le]
    constructor <;> linarith
  have hdiff_zero (i : Fin n) (hi : i ∉ bad) : |observed k i - clean k i| = 0 := by
    have hsame := hreplaced.agrees_outside k i hi
    rw [hsame]
    simp
  have hsum_restrict :
      (∑ i : Fin n, |observed k i - clean k i|) = ∑ i ∈ bad, |observed k i - clean k i| := by
    symm
    apply Finset.sum_subset
    · exact Finset.subset_univ bad
    · intro i _ hi
      exact hdiff_zero i hi
  have hsum_bad : (∑ i ∈ bad, |observed k i - clean k i|) ≤ ∑ _i ∈ bad, (2 : ℝ) := by
    apply Finset.sum_le_sum
    intro i hi
    exact hdiff_bound i
  have hsum_card : (∑ _i ∈ bad, (2 : ℝ)) = (2 * bad.card : ℝ) := by
    simp [mul_comm]
  have hsum : (∑ i : Fin n, |observed k i - clean k i|) ≤ (2 * b : ℝ) := by
    rw [hsum_restrict]
    calc
      (∑ i ∈ bad, |observed k i - clean k i|) ≤ ∑ _i ∈ bad, (2 : ℝ) := hsum_bad
      _ = (2 * bad.card : ℝ) := hsum_card
      _ ≤ 2 * b := by
        exact_mod_cast (Nat.mul_le_mul_left 2 (hreplaced.card_le k))
  have hdenom : (0 : ℝ) < n := by exact_mod_cast hn
  have hmean : mean n (observed k) - mean n (clean k) =
      (∑ x, (observed k x - clean k x)) / n := by
    unfold mean
    rw [← sub_div, ← Finset.sum_sub_distrib]
  rw [hmean, abs_div, abs_of_nonneg (le_of_lt hdenom)]
  calc
    |(∑ x, (observed k x - clean k x))| / ↑n ≤
        (∑ x, |observed k x - clean k x|) / ↑n := by
          exact div_le_div_of_nonneg_right
            (Finset.abs_sum_le_sum_abs _ Finset.univ) (le_of_lt hdenom)
    _ ≤ (2 * b : ℝ) / n := by
          exact div_le_div_of_nonneg_right hsum (le_of_lt hdenom)

/-- The guard-visible lower confidence bound; no hidden clean target is read here. -/
noncomputable def lowerBound (observed : Fin m → Fin n → ℝ) (radius contamination : ℝ)
    (k : Fin m) : ℝ :=
  mean n (observed k) - radius - contamination

/-- Candidates whose computed lower bound strictly covers their frozen cost. -/
noncomputable def certified (frozen : FrozenCandidates Candidate m) (observed : Fin m → Fin n → ℝ)
    (radius contamination : ℝ) : Finset (Fin m) :=
  Finset.univ.filter (fun k => frozen.cost k < lowerBound observed radius contamination k)

/-- The actual finite selector returns a payload-indexed certified candidate. -/
noncomputable def selectCertified (frozen : FrozenCandidates Candidate m) (observed : Fin m → Fin n → ℝ)
    (radius contamination : ℝ) : Option (Fin m) :=
  if h : (certified frozen observed radius contamination).Nonempty then
    some ((certified frozen observed radius contamination).min' h)
  else none

theorem selected_is_certified {frozen : FrozenCandidates Candidate m}
    {observed : Fin m → Fin n → ℝ} {radius contamination : ℝ} {k : Fin m}
    (hselected : selectCertified frozen observed radius contamination = some k) :
    k ∈ certified frozen observed radius contamination := by
  classical
  unfold selectCertified at hselected
  split at hselected
  · have heq : (certified frozen observed radius contamination).min' _ = k :=
      Option.some.inj hselected
    rw [← heq]
    exact Finset.min'_mem _ _
  · simp at hselected

/-- Fresh-sample concentration plus replacements gives a simultaneous observed error bound. -/
theorem observed_mean_error_bound {clean observed : Fin m → Fin n → ℝ}
    {target : Fin m → ℝ} {radius : ℝ} {b : Nat}
    (hn : 0 < n) (hbounded : BoundedGains clean observed)
    (hreplaced : ReplacementWitness clean observed b)
    (hclean : CleanMeanEvent clean target radius) (k : Fin m) :
    |mean n (observed k) - target k| ≤ radius + (2 * b : ℝ) / n := by
  have hreplace := mean_replacement_bound hn hbounded hreplaced k
  have hconcentration := hclean k
  calc
    |mean n (observed k) - target k| =
        |(mean n (observed k) - mean n (clean k)) +
          (mean n (clean k) - target k)| := by ring_nf
    _ ≤ |mean n (observed k) - mean n (clean k)| +
          |mean n (clean k) - target k| := abs_add_le _ _
    _ ≤ radius + (2 * b : ℝ) / n := by linarith

/-- A selected frozen candidate has positive true net gain on the supplied good event. -/
theorem selected_sound {frozen : FrozenCandidates Candidate m}
    {clean observed : Fin m → Fin n → ℝ} {target : Fin m → ℝ} {radius : ℝ} {b : Nat}
    (hn : 0 < n) (hbounded : BoundedGains clean observed)
    (hreplaced : ReplacementWitness clean observed b)
    (hclean : CleanMeanEvent clean target radius) {k : Fin m}
    (hselected : selectCertified frozen observed radius ((2 * b : ℝ) / n) = some k) :
    0 < target k - frozen.cost k := by
  have hmember := selected_is_certified hselected
  simp only [certified, Finset.mem_filter, Finset.mem_univ, true_and] at hmember
  have herror := observed_mean_error_bound hn hbounded hreplaced hclean k
  have hupper := (abs_le.mp herror).2
  unfold lowerBound at hmember
  linarith

/-- A candidate whose target margin exceeds both error directions is certified. -/
theorem target_margin_certifies {frozen : FrozenCandidates Candidate m}
    {clean observed : Fin m → Fin n → ℝ} {target : Fin m → ℝ} {radius : ℝ} {b : Nat}
    (hn : 0 < n) (hbounded : BoundedGains clean observed)
    (hreplaced : ReplacementWitness clean observed b)
    (hclean : CleanMeanEvent clean target radius) {k : Fin m}
    (hmargin : frozen.cost k + 2 * (radius + (2 * b : ℝ) / n) < target k) :
    k ∈ certified frozen observed radius ((2 * b : ℝ) / n) := by
  simp only [certified, Finset.mem_filter, Finset.mem_univ, true_and]
  have herror := observed_mean_error_bound hn hbounded hreplaced hclean k
  have hlower := (abs_le.mp herror).1
  unfold lowerBound
  linarith

/-- A sufficient target margin makes the executable finite selector nonempty. -/
theorem target_margin_forces_selection {frozen : FrozenCandidates Candidate m}
    {clean observed : Fin m → Fin n → ℝ} {target : Fin m → ℝ} {radius : ℝ} {b : Nat}
    (hn : 0 < n) (hbounded : BoundedGains clean observed)
    (hreplaced : ReplacementWitness clean observed b)
    (hclean : CleanMeanEvent clean target radius) {k : Fin m}
    (hmargin : frozen.cost k + 2 * (radius + (2 * b : ℝ) / n) < target k) :
    (selectCertified frozen observed radius ((2 * b : ℝ) / n)).isSome := by
  classical
  have hmember := target_margin_certifies hn hbounded hreplaced hclean hmargin
  unfold selectCertified
  split
  · simp
  · rename_i hnone
    exact False.elim (hnone ⟨k, hmember⟩)

/-- A one-candidate, one-row exact-real witness: a positive clean gain is certifiable. -/
noncomputable def witnessFrozen : FrozenCandidates Unit 1 where
  payload := fun _ => ()
  cost := fun _ => 0

noncomputable def witnessClean : Fin 1 → Fin 1 → ℝ := fun _ _ => 1
noncomputable def witnessObserved : Fin 1 → Fin 1 → ℝ := fun _ _ => 1
noncomputable def witnessTarget : Fin 1 → ℝ := fun _ => 1

def witnessNoReplacement : ReplacementWitness witnessClean witnessObserved 0 where
  bad := fun _ => ∅
  card_le := by intro; simp
  agrees_outside := by intro k i hi; rfl

theorem witness_selection_is_nonvacuous :
    selectCertified witnessFrozen witnessObserved (1 / 4 : ℝ) 0 = some 0 := by
  norm_num [selectCertified, certified, lowerBound, mean, witnessFrozen, witnessObserved]

/-- Without a valid replacement witness, a dirty row can select a truly harmful candidate. -/
noncomputable def dirtyClean : Fin 1 → Fin 1 → ℝ := fun _ _ => -1
noncomputable def dirtyObserved : Fin 1 → Fin 1 → ℝ := fun _ _ => 1
noncomputable def dirtyTarget : Fin 1 → ℝ := fun _ => -1

theorem understated_replacement_allowance_can_select_degradation :
    selectCertified witnessFrozen dirtyObserved (1 / 4 : ℝ) 0 = some 0 ∧
      dirtyTarget 0 - witnessFrozen.cost 0 < 0 := by
  constructor
  · norm_num [selectCertified, certified, lowerBound, mean, witnessFrozen, dirtyObserved]
  · norm_num [dirtyTarget, witnessFrozen]

/-- The dirty counterexample cannot satisfy a zero-row replacement certificate. -/
theorem dirty_row_has_no_zero_replacement_witness :
    ¬ HasReplacementWitness dirtyClean dirtyObserved 0 := by
  intro h
  rcases h with ⟨h⟩
  have hcard := h.card_le 0
  have hempty : h.bad 0 = ∅ := Finset.card_eq_zero.mp (by simpa using hcard)
  have hagree := h.agrees_outside 0 0 (by simp [hempty])
  norm_num [dirtyClean, dirtyObserved] at hagree

end HSWMStatisticalLearning.Selection
