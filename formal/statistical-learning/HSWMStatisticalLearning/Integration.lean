import HSWMStatisticalLearning.Concentration
import HSWMStatisticalLearning.Selection

/-!
# Concentration, contamination, and actual finite-candidate selection

The probabilistic statements in this file must derive their failure bound from
the sample assumptions, rather than accept a uniform-error certificate as an
input. Frozen candidate payloads and costs are fixed parameters, outside the
sample point. The deterministic event implication is also exposed for auditing.
No actual LLM, independent outcome source, or runtime numeric refinement is
established by these theorems.
-/

namespace HSWMStatisticalLearning.Integration

noncomputable section

open MeasureTheory ProbabilityTheory
open Selection

variable {Candidate Ω : Type} {m n b : Nat}

theorem centered_sum_eq_scaled_mean (d : Fin m → ℕ → Ω → ℝ)
    (target : Fin m → ℝ) (k : Fin m) (n : Nat) (hn : 0 < n) (ω : Ω) :
    centeredSum d target k n ω =
      (n : ℝ) * (mean n (fun i : Fin n => d k i.val ω) - target k) := by
  have hnreal : (n : ℝ) ≠ 0 := by exact_mod_cast (Nat.ne_of_gt hn)
  simp only [centeredSum, Finset.sum_sub_distrib, Finset.sum_const,
    Finset.card_range, nsmul_eq_mul, mean]
  field_simp
  rw [Fin.sum_univ_eq_sum_range (fun i => d k i ω)]

theorem mean_deviation_implies_centered_deviation (d : Fin m → ℕ → Ω → ℝ)
    (target : Fin m → ℝ) (k : Fin m) (n : Nat) (hn : 0 < n) (ω : Ω)
    (radius : ℝ)
    (h : radius < |mean n (fun i : Fin n => d k i.val ω) - target k|) :
    (n : ℝ) * radius ≤ |centeredSum d target k n ω| := by
  rw [centered_sum_eq_scaled_mean d target k n hn ω, abs_mul,
    abs_of_nonneg (Nat.cast_nonneg n)]
  exact le_of_lt (mul_lt_mul_of_pos_left h (by exact_mod_cast hn))

/-- Soundness and non-vacuous power are asserted on the same sample event. -/
def RoundWorks (frozen : FrozenCandidates Candidate m)
    (observed : Fin m → Fin n → ℝ) (target : Fin m → ℝ)
    (radius : ℝ) (b : Nat) : Prop :=
  (∀ k, selectCertified frozen observed radius ((2 * b : ℝ) / n) = some k →
    0 < target k - frozen.cost k) ∧
  ((∃ k, frozen.cost k + 2 * (radius + (2 * b : ℝ) / n) < target k) →
    (selectCertified frozen observed radius ((2 * b : ℝ) / n)).isSome)

theorem round_works_on_clean_event (frozen : FrozenCandidates Candidate m)
    (clean observed : Fin m → Fin n → ℝ) (target : Fin m → ℝ)
    (radius : ℝ) (hn : 0 < n)
    (bounded : BoundedGains clean observed)
    (replacements : ReplacementWitness clean observed b)
    (good : CleanMeanEvent clean target radius) :
    RoundWorks frozen observed target radius b := by
  constructor
  · intro k selected
    exact selected_sound hn bounded replacements good selected
  · rintro ⟨k, margin⟩
    exact target_margin_forces_selection hn bounded replacements good margin

/-- Any failure of soundness or power implies a clean-sample concentration failure. -/
theorem failure_subset_clean_deviation (frozen : FrozenCandidates Candidate m)
    (clean observed : Ω → Fin m → Fin n → ℝ) (target : Fin m → ℝ)
    (radius : ℝ) (hn : 0 < n)
    (bounded : ∀ ω, BoundedGains (clean ω) (observed ω))
    (replacements : ∀ ω, ReplacementWitness (clean ω) (observed ω) b) :
    {ω | ¬ RoundWorks frozen (observed ω) target radius b} ⊆
      {ω | ∃ k, radius < |mean n (clean ω k) - target k|} := by
  intro ω failure
  by_contra noDeviation
  apply failure
  apply round_works_on_clean_event frozen (clean ω) (observed ω) target radius hn
    (bounded ω) (replacements ω)
  intro k
  exact le_of_not_gt (fun deviation => noDeviation ⟨k, deviation⟩)

/-- Restrict the fresh evaluation stream to the finite rows read by selection. -/
def sampleRows (d : Fin m → ℕ → Ω → ℝ) (n : Nat) (ω : Ω) : Fin m → Fin n → ℝ :=
  fun k i => d k i.val ω

/--
One end-to-end statistical guarantee. The clean expectation is tied to the
actual row integrals; no UniformError, valid confidence bound, or positive
gain is assumed. Candidate payloads/costs are frozen outside `ω`. A per-sample
replacement witness and bounded observed values expose the exact noise model.

`μ.real` on a general set is the real-valued outer measure. Thus the failure
bound remains valid even without assuming that the corruption mechanism is
measurable; for a measurable observation/selection process this is its ordinary
failure probability. Rows may differ in law if they share the stated means.
-/
theorem statistical_selection_failure_bound [MeasurableSpace Ω]
    (μ : Measure Ω) [IsProbabilityMeasure μ]
    (frozen : FrozenCandidates Candidate m)
    (d : Fin m → ℕ → Ω → ℝ) (observed : Ω → Fin m → Fin n → ℝ)
    (target : Fin m → ℝ) (radius : ℝ) (hn : 0 < n) (hradius : 0 ≤ radius)
    (independent : ∀ k, iIndepFun (d k) μ)
    (measurable : ∀ k i, i < n → AEMeasurable (d k i) μ)
    (expectation : ∀ k i, i < n → (∫ ω, d k i ω ∂μ) = target k)
    (bounded : ∀ ω, BoundedGains (sampleRows d n ω) (observed ω))
    (replacements : ∀ ω, ReplacementWitness (sampleRows d n ω) (observed ω) b) :
    μ.real {ω | ¬ RoundWorks frozen (observed ω) target radius b} ≤
      2 * (m : ℝ) * Real.exp (-(n : ℝ) * radius ^ 2 / 2) := by
  have hbound (k : Fin m) (i : ℕ) (hi : i < n) :
      ∀ᵐ ω ∂μ, d k i ω ∈ Set.Icc (-1 : ℝ) 1 :=
    Filter.Eventually.of_forall (fun ω => (bounded ω).1 k ⟨i, hi⟩)
  have hmean (k : Fin m) (i : ℕ) (hi : i < n) :
      (∫ ω, d k i ω - target k ∂μ) = 0 := by
    rw [integral_sub (Integrable.of_mem_Icc (-1) 1 (measurable k i hi) (hbound k i hi))
      (integrable_const _), integral_const]
    simp [expectation k i hi]
  have subset : {ω | ¬ RoundWorks frozen (observed ω) target radius b} ⊆
      {ω | ∃ k ∈ (Finset.univ : Finset (Fin m)),
        (n : ℝ) * radius ≤ |centeredSum d target k n ω|} := by
    intro ω failure
    obtain ⟨k, deviation⟩ := failure_subset_clean_deviation frozen (sampleRows d n)
      observed target radius hn bounded replacements failure
    exact ⟨k, Finset.mem_univ k,
      mean_deviation_implies_centered_deviation d target k n hn ω radius deviation⟩
  calc
    _ ≤ μ.real {ω | ∃ k ∈ (Finset.univ : Finset (Fin m)),
        (n : ℝ) * radius ≤ |centeredSum d target k n ω|} := measureReal_mono subset
    _ ≤ 2 * ((Finset.univ : Finset (Fin m)).card : ℝ) *
        Real.exp (-((n : ℝ) * radius) ^ 2 / (2 * (n : ℝ))) :=
      simultaneous_centeredSum_abs_tail_card d target Finset.univ n
        (fun k _ => independent k) (fun k _ => measurable k)
        (fun k _ => hbound k) (fun k _ => hmean k) hradius
    _ = 2 * (m : ℝ) * Real.exp (-(n : ℝ) * radius ^ 2 / 2) := by
      have hnreal : (n : ℝ) ≠ 0 := by exact_mod_cast (Nat.ne_of_gt hn)
      simp only [Finset.card_univ, Fintype.card_fin]
      congr 2
      field_simp

/-- The calibrated radius normalizes the integrated exponential bound to `δ`. -/
theorem calibrated_failure_eq_delta {δ : ℝ}
    (hm : 0 < m) (hn : 0 < n) (hδ0 : 0 < δ) (hδ1 : δ < 1) :
    2 * (m : ℝ) * Real.exp (-(n : ℝ) * calibratedRadius m n δ ^ 2 / 2) = δ := by
  have hnreal : (n : ℝ) ≠ 0 := by exact_mod_cast (Nat.ne_of_gt hn)
  have exponent : -(n : ℝ) * calibratedRadius m n δ ^ 2 / 2 =
      -((n : ℝ) * calibratedRadius m n δ) ^ 2 / (2 * (n : ℝ)) := by
    field_simp
  rw [exponent]
  exact calibratedRadius_failure_eq_delta hm hn hδ0 hδ1

/-- A user-specified failure budget, derived from the fresh row assumptions. -/
theorem statistical_selection_failure_le_delta [MeasurableSpace Ω]
    (μ : Measure Ω) [IsProbabilityMeasure μ]
    (frozen : FrozenCandidates Candidate m)
    (d : Fin m → ℕ → Ω → ℝ) (observed : Ω → Fin m → Fin n → ℝ)
    (target : Fin m → ℝ) (δ : ℝ)
    (hm : 0 < m) (hn : 0 < n) (hδ0 : 0 < δ) (hδ1 : δ < 1)
    (independent : ∀ k, iIndepFun (d k) μ)
    (measurable : ∀ k i, i < n → AEMeasurable (d k i) μ)
    (expectation : ∀ k i, i < n → (∫ ω, d k i ω ∂μ) = target k)
    (bounded : ∀ ω, BoundedGains (sampleRows d n ω) (observed ω))
    (replacements : ∀ ω, ReplacementWitness (sampleRows d n ω) (observed ω) b) :
    μ.real {ω | ¬ RoundWorks frozen (observed ω) target (calibratedRadius m n δ) b} ≤ δ := by
  have bound := statistical_selection_failure_bound μ frozen d observed target
    (calibratedRadius m n δ) hn (calibratedRadius_nonneg m n δ)
    independent measurable expectation bounded replacements
  rwa [calibrated_failure_eq_delta hm hn hδ0 hδ1] at bound

end
end HSWMStatisticalLearning.Integration
