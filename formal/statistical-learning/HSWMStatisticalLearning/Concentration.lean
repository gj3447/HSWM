import Mathlib.Probability.Moments.SubGaussian

/-!
# Concentration for frozen HSWM revision candidates

This module proves a concentration inequality from Mathlib's Hoeffding lemma;
it does not assume a pre-packaged uniform-error event. A candidate index is
kept arbitrary, so no independence is imposed between different candidates.
Only the rows belonging to one fixed candidate are independent.
-/

open MeasureTheory ProbabilityTheory Real
open scoped BigOperators ENNReal NNReal Topology

namespace HSWMStatisticalLearning

variable {Ω K : Type*} [MeasurableSpace Ω] {μ : Measure Ω}

/-- The sum of a candidate's observed utility differences after centering at
its declared clean-population mean. -/
def centeredSum (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (k : K) (n : ℕ) : Ω → ℝ :=
  fun ω => ∑ i ∈ Finset.range n, (d k i ω - mean k)

/-- The negative of `centeredSum`, written with the same bounded rows. -/
def negativeCenteredSum (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (k : K) (n : ℕ) : Ω → ℝ :=
  fun ω => ∑ i ∈ Finset.range n, (mean k - d k i ω)

omit [MeasurableSpace Ω] in
lemma negativeCenteredSum_eq_neg (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (k : K) (n : ℕ) :
    negativeCenteredSum d mean k n = -centeredSum d mean k n := by
  funext ω
  simp [negativeCenteredSum, centeredSum]

/-- A direct bridge from an equal clean expectation to the centered-zero
premise used by Hoeffding. Boundedness supplies the needed integrability; it
is not silently assumed. -/
lemma centered_integral_zero_of_integral_eq
    [IsProbabilityMeasure μ]
    (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (k : K) (i : ℕ)
    (measurable : AEMeasurable (d k i) μ)
    (bounded : ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1)
    (integral_eq : μ[d k i] = mean k) :
    μ[fun ω => d k i ω - mean k] = 0 := by
  rw [integral_sub (Integrable.of_mem_Icc (-1) 1 measurable bounded) (integrable_const _),
    integral_eq]
  simp

/--
One-sided Hoeffding bound for one frozen candidate. The rows need only be
independent for this candidate; no condition relates rows for distinct
candidates. `mean_zero` is normally obtained from iid rows with mean `mean k`,
but is stated directly so the result also covers the weaker,
heterogeneous-but-equal-mean case.

The exact denominator is retained because it is the expression returned by
Mathlib's verified Hoeffding theorem. For `0 < n`, it simplifies to the
familiar `exp (- n * ε^2 / 2)` form.
-/
theorem centeredSum_upper_tail
    [IsProbabilityMeasure μ]
    (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (k : K) (n : ℕ)
    (independent : iIndepFun (d k) μ)
    (measurable : ∀ i < n, AEMeasurable (d k i) μ)
    (bounded : ∀ i < n, ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1)
    (mean_zero : ∀ i < n, μ[fun ω => d k i ω - mean k] = 0)
    {ε : ℝ} (nonnegative : 0 ≤ ε) :
    μ.real {ω | (n : ℝ) * ε ≤ centeredSum d mean k n ω} ≤
      exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
  let X : ℕ → Ω → ℝ := fun i ω => d k i ω - mean k
  have independentX : iIndepFun X μ := by
    change iIndepFun (fun i => (fun x : ℝ => x - mean k) ∘ d k i) μ
    exact independent.comp (fun _ x => x - mean k) (fun _ => measurable_id.sub measurable_const)
  have subgaussian : ∀ i < n, HasSubgaussianMGF (X i) (1 : ℝ≥0) μ := by
    intro i hi
    have h := hasSubgaussianMGF_of_mem_Icc_of_integral_eq_zero
      (X := X i) (a := -1 - mean k) (b := 1 - mean k)
      ((measurable i hi).sub_const _)
      (by
        filter_upwards [bounded i hi] with ω hω
        simpa [X] using hω)
      (mean_zero i hi)
    norm_num at h ⊢
    exact h
  have h := HasSubgaussianMGF.measure_sum_range_ge_le_of_iIndepFun (X := X) independentX
    (c := (1 : ℝ≥0)) subgaussian (ε := (n : ℝ) * ε) (mul_nonneg (Nat.cast_nonneg _) nonnegative)
  simpa [centeredSum, X, mul_assoc] using h

/-- Lower-tail counterpart of `centeredSum_upper_tail`, proved by applying the
same Hoeffding derivation to `mean - d`. -/
theorem centeredSum_lower_tail
    [IsProbabilityMeasure μ]
    (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (k : K) (n : ℕ)
    (independent : iIndepFun (d k) μ)
    (measurable : ∀ i < n, AEMeasurable (d k i) μ)
    (bounded : ∀ i < n, ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1)
    (mean_zero : ∀ i < n, μ[fun ω => mean k - d k i ω] = 0)
    {ε : ℝ} (nonnegative : 0 ≤ ε) :
    μ.real {ω | (n : ℝ) * ε ≤ negativeCenteredSum d mean k n ω} ≤
      exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
  let X : ℕ → Ω → ℝ := fun i ω => mean k - d k i ω
  have independentX : iIndepFun X μ := by
    change iIndepFun (fun i => (fun x : ℝ => mean k - x) ∘ d k i) μ
    exact independent.comp (fun _ x => mean k - x) (fun _ => measurable_const.sub measurable_id)
  have subgaussian : ∀ i < n, HasSubgaussianMGF (X i) (1 : ℝ≥0) μ := by
    intro i hi
    have h := hasSubgaussianMGF_of_mem_Icc_of_integral_eq_zero
      (X := X i) (a := mean k - 1) (b := mean k - -1)
      (by simpa [X] using (measurable i hi).const_sub (mean k))
      (by
        filter_upwards [bounded i hi] with ω hω
        constructor <;> linarith [hω.1, hω.2])
      (mean_zero i hi)
    norm_num at h ⊢
    exact h
  have h := HasSubgaussianMGF.measure_sum_range_ge_le_of_iIndepFun (X := X) independentX
    (c := (1 : ℝ≥0)) subgaussian (ε := (n : ℝ) * ε) (mul_nonneg (Nat.cast_nonneg _) nonnegative)
  simpa [negativeCenteredSum, X, mul_assoc] using h

/-- A finite union bound for real-valued measures. This is the only step that
combines candidates, and therefore does not require candidate independence. -/
theorem measureReal_iUnion_finset_le (s : Finset K) (event : K → Set Ω) :
    μ.real (⋃ k ∈ s, event k) ≤ ∑ k ∈ s, μ.real (event k) := by
  classical
  induction s using Finset.induction_on with
  | empty => simp
  | insert k s hk ih =>
    rw [Finset.sum_insert hk]
    simpa [Finset.mem_insert, hk] using
      (MeasureTheory.measureReal_union_le (event k) (⋃ j ∈ s, event j)).trans
        (add_le_add_right ih _)

/-- Simultaneous one-sided concentration for a finite frozen candidate set.
Different candidates may share every random source; the proof only applies the
per-candidate result followed by a finite union bound. -/
theorem simultaneous_centeredSum_upper_tail
    [IsProbabilityMeasure μ]
    (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (candidates : Finset K) (n : ℕ)
    (independent : ∀ k ∈ candidates, iIndepFun (d k) μ)
    (measurable : ∀ k ∈ candidates, ∀ i < n, AEMeasurable (d k i) μ)
    (bounded : ∀ k ∈ candidates, ∀ i < n, ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1)
    (mean_zero : ∀ k ∈ candidates, ∀ i < n, μ[fun ω => d k i ω - mean k] = 0)
    {ε : ℝ} (nonnegative : 0 ≤ ε) :
    μ.real {ω | ∃ k ∈ candidates, (n : ℝ) * ε ≤ centeredSum d mean k n ω} ≤
      ∑ _k ∈ candidates, exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
  let event : K → Set Ω := fun k => {ω | (n : ℝ) * ε ≤ centeredSum d mean k n ω}
  calc
    μ.real {ω | ∃ k ∈ candidates, (n : ℝ) * ε ≤ centeredSum d mean k n ω}
        = μ.real (⋃ k ∈ candidates, event k) := by
          congr 1
          ext ω
          simp [event]
    _ ≤ ∑ k ∈ candidates, μ.real (event k) := measureReal_iUnion_finset_le candidates event
    _ ≤ ∑ k ∈ candidates, exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
      gcongr with k hk
      exact centeredSum_upper_tail d mean k n (independent k hk) (measurable k hk)
        (bounded k hk) (mean_zero k hk) nonnegative

/-- Cardinality form of the simultaneous one-sided bound. -/
theorem simultaneous_centeredSum_upper_tail_card
    [IsProbabilityMeasure μ]
    (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (candidates : Finset K) (n : ℕ)
    (independent : ∀ k ∈ candidates, iIndepFun (d k) μ)
    (measurable : ∀ k ∈ candidates, ∀ i < n, AEMeasurable (d k i) μ)
    (bounded : ∀ k ∈ candidates, ∀ i < n, ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1)
    (mean_zero : ∀ k ∈ candidates, ∀ i < n, μ[fun ω => d k i ω - mean k] = 0)
    {ε : ℝ} (nonnegative : 0 ≤ ε) :
    μ.real {ω | ∃ k ∈ candidates, (n : ℝ) * ε ≤ centeredSum d mean k n ω} ≤
      (candidates.card : ℝ) * exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
  calc
    _ ≤ ∑ _k ∈ candidates, exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) :=
      simultaneous_centeredSum_upper_tail d mean candidates n independent measurable bounded mean_zero
        nonnegative
    _ = _ := by simp [mul_comm]

/-- Simultaneous two-sided concentration for a frozen finite candidate set.
The factor two is the positive/negative tail union; the candidate factor is a
finite union bound, so no candidate-to-candidate independence is assumed. -/
theorem simultaneous_centeredSum_abs_tail_card
    [IsProbabilityMeasure μ]
    (d : K → ℕ → Ω → ℝ) (mean : K → ℝ) (candidates : Finset K) (n : ℕ)
    (independent : ∀ k ∈ candidates, iIndepFun (d k) μ)
    (measurable : ∀ k ∈ candidates, ∀ i < n, AEMeasurable (d k i) μ)
    (bounded : ∀ k ∈ candidates, ∀ i < n, ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1)
    (mean_zero : ∀ k ∈ candidates, ∀ i < n, μ[fun ω => d k i ω - mean k] = 0)
    {ε : ℝ} (nonnegative : 0 ≤ ε) :
    μ.real {ω | ∃ k ∈ candidates, (n : ℝ) * ε ≤ |centeredSum d mean k n ω|} ≤
      2 * (candidates.card : ℝ) * exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
  let plus : K → Set Ω := fun k => {ω | (n : ℝ) * ε ≤ centeredSum d mean k n ω}
  let minus : K → Set Ω := fun k => {ω | (n : ℝ) * ε ≤ negativeCenteredSum d mean k n ω}
  have hsubset : {ω | ∃ k ∈ candidates, (n : ℝ) * ε ≤ |centeredSum d mean k n ω|} ⊆
      (⋃ k ∈ candidates, plus k) ∪ (⋃ k ∈ candidates, minus k) := by
    rintro ω ⟨k, hk, hω⟩
    by_cases hs : 0 ≤ centeredSum d mean k n ω
    · left
      simp only [Set.mem_iUnion]
      exact ⟨k, hk, by simpa [plus, abs_of_nonneg hs] using hω⟩
    · right
      simp only [Set.mem_iUnion]
      have hn : centeredSum d mean k n ω < 0 := lt_of_not_ge hs
      refine ⟨k, hk, ?_⟩
      change (n : ℝ) * ε ≤ negativeCenteredSum d mean k n ω
      rw [negativeCenteredSum_eq_neg]
      simpa [minus, abs_of_neg hn] using hω
  have hplus : μ.real (⋃ k ∈ candidates, plus k) ≤
      (candidates.card : ℝ) * exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
    have h := simultaneous_centeredSum_upper_tail_card d mean candidates n independent
      measurable bounded mean_zero nonnegative
    have heq : {ω | ∃ k ∈ candidates, (n : ℝ) * ε ≤ centeredSum d mean k n ω} =
        ⋃ k ∈ candidates, plus k := by
      ext ω
      simp [plus]
    rw [← heq]
    exact h
  have lower_zero : ∀ k ∈ candidates, ∀ i < n, μ[fun ω => mean k - d k i ω] = 0 := by
    intro k hk i hi
    have hneg : (fun ω : Ω => mean k - d k i ω) = fun ω : Ω => -(d k i ω - mean k) := by
      funext ω
      ring
    calc
      ∫ ω, (mean k - d k i ω) ∂μ = ∫ ω, -(d k i ω - mean k) ∂μ := by rw [hneg]
      _ = -(∫ ω, (d k i ω - mean k) ∂μ) := integral_neg _
      _ = 0 := by rw [mean_zero k hk i hi]; simp
  have hminus : μ.real (⋃ k ∈ candidates, minus k) ≤
      (candidates.card : ℝ) * exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
    calc
      _ ≤ ∑ k ∈ candidates, μ.real (minus k) := measureReal_iUnion_finset_le candidates minus
      _ ≤ ∑ _k ∈ candidates, exp (-((n : ℝ) * ε) ^ 2 / (2 * (n : ℝ))) := by
        gcongr with k hk
        exact centeredSum_lower_tail d mean k n (independent k hk) (measurable k hk)
          (bounded k hk) (lower_zero k hk) nonnegative
      _ = _ := by simp [mul_comm]
  calc
    _ ≤ μ.real ((⋃ k ∈ candidates, plus k) ∪ (⋃ k ∈ candidates, minus k)) :=
      MeasureTheory.measureReal_mono hsubset
    _ ≤ μ.real (⋃ k ∈ candidates, plus k) + μ.real (⋃ k ∈ candidates, minus k) :=
      MeasureTheory.measureReal_union_le _ _
    _ ≤ _ := by linarith

/-- Radius obtained by solving the two-sided finite-candidate Hoeffding bound
at failure budget `δ`. -/
noncomputable def calibratedRadius (m n : ℕ) (δ : ℝ) : ℝ :=
  sqrt (2 * log (2 * (m : ℝ) / δ) / (n : ℝ))

lemma calibratedRadius_nonneg (m n : ℕ) (δ : ℝ) : 0 ≤ calibratedRadius m n δ :=
  sqrt_nonneg _

/-- Algebraic calibration of the raw two-sided tail bound. The conditions are
kept explicit: this is a radius identity, not a claim that data are iid. -/
lemma calibratedRadius_failure_eq_delta {m n : ℕ} {δ : ℝ}
    (hm : 0 < m) (hn : 0 < n) (hδ0 : 0 < δ) (hδ1 : δ < 1) :
    2 * (m : ℝ) * exp (-((n : ℝ) * calibratedRadius m n δ) ^ 2 / (2 * (n : ℝ))) = δ := by
  have hmR : 0 < (m : ℝ) := by exact_mod_cast hm
  have hm1 : (1 : ℝ) ≤ (m : ℝ) := by
    exact_mod_cast (Nat.succ_le_iff.mpr hm)
  have hnR : 0 < (n : ℝ) := by exact_mod_cast hn
  have ha : 0 < 2 * (m : ℝ) / δ := by positivity
  have ha1 : 1 < 2 * (m : ℝ) / δ := by
    rw [lt_div_iff₀ hδ0]
    nlinarith
  have hlog : 0 ≤ log (2 * (m : ℝ) / δ) := (Real.log_pos ha1).le
  have hinside : 0 ≤ 2 * log (2 * (m : ℝ) / δ) / (n : ℝ) := by positivity
  have hsq : calibratedRadius m n δ ^ 2 = 2 * log (2 * (m : ℝ) / δ) / (n : ℝ) := by
    unfold calibratedRadius
    exact sq_sqrt hinside
  have hexp : -((n : ℝ) * calibratedRadius m n δ) ^ 2 / (2 * (n : ℝ)) =
      -log (2 * (m : ℝ) / δ) := by
    rw [mul_pow, hsq]
    field_simp
  rw [hexp, exp_neg, exp_log ha]
  field_simp

end HSWMStatisticalLearning
