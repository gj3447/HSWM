import HSWMStatisticalLearning.Integration

/-!
# Conditional fresh-round bounds and finite alpha spending

`Integration.statistical_selection_failure_bound` proves one frozen evaluation
round under one probability measure.  A continuous learner chooses its next
frozen round from a past transcript, so the appropriate premise is a
history-wise bound for the fresh evaluation randomness *conditional on that
transcript*.  This file records the finite-partition calculation which turns
such a premise into an unconditional bound, then spends a finite sequence of
round budgets.

The conditional premise below is deliberately expressed without division:
the failure mass inside each history cell is at most `α` times the mass of that
cell.  On a positive-mass cell, this is exactly the usual conditional
probability inequality.  Establishing it for HSWM requires instantiating the
single-round concentration theorem on the fresh evaluation kernel for each
past transcript.  `kernelwise_statistical_selection_failure_le_delta` performs
that invocation for a finite family of history-indexed kernels.  This file does
not establish that an operational transcript supplies those kernels,
conditional independence/freshness, usefulness of generated proposals, a
confidence sequence, or a TypeScript numeric refinement.
-/

namespace HSWMStatisticalLearning.AdaptiveRounds

noncomputable section

open MeasureTheory ProbabilityTheory

variable {Ω : Type}

/--
The division-free form of a conditional round-failure bound on a finite
partition of possible past transcripts.  `history i` is fixed before this
round's fresh evaluation rows are drawn.
-/
def HistoryConditionalFailureBound [MeasurableSpace Ω] (μ : Measure Ω) {h : Nat}
    (history : Fin h → Set Ω) (failure : Set Ω) (α : ℝ) : Prop :=
  ∀ i, μ.real (failure ∩ history i) ≤ α * μ.real (history i)

/--
Apply the existing frozen-round theorem separately to every possible finite
past transcript.  The `frozen q` payload is an argument outside the fresh
sample point of `μ q`; it may differ between histories, but it cannot inspect
that history's fresh rows.  Thus this is the concrete source of a conditional
round bound, rather than a hypothesis that simply postulates one.
-/
theorem kernelwise_statistical_selection_failure_le_delta
    {History Candidate : Type} {m n b : Nat} [Fintype History]
    [MeasurableSpace Ω]
    (μ : History → Measure Ω) (probability : ∀ q, IsProbabilityMeasure (μ q))
    (frozen : History → Selection.FrozenCandidates Candidate m)
    (d : History → Fin m → ℕ → Ω → ℝ)
    (observed : History → Ω → Fin m → Fin n → ℝ)
    (target : History → Fin m → ℝ) (δ : ℝ)
    (hm : 0 < m) (hn : 0 < n) (hδ0 : 0 < δ) (hδ1 : δ < 1)
    (independent : ∀ (q : History) (k : Fin m), iIndepFun (d q k) (μ q))
    (measurable : ∀ (q : History) (k : Fin m) i, i < n → AEMeasurable (d q k i) (μ q))
    (expectation : ∀ (q : History) (k : Fin m) i, i < n →
      (∫ ω, d q k i ω ∂(μ q)) = target q k)
    (bounded : ∀ (q : History) (ω : Ω), Selection.BoundedGains
      (Integration.sampleRows (d q) n ω) (observed q ω))
    (replacements : ∀ (q : History) (ω : Ω), Selection.ReplacementWitness
      (Integration.sampleRows (d q) n ω) (observed q ω) b) :
    ∀ q, (μ q).real {ω | ¬ Integration.RoundWorks (frozen q) (observed q ω)
      (target q) (calibratedRadius m n δ) b} ≤ δ := by
  intro q
  letI : IsProbabilityMeasure (μ q) := probability q
  exact Integration.statistical_selection_failure_le_delta (μ q) (frozen q)
    (d q) (observed q) (target q) δ hm hn hδ0 hδ1
    (independent q) (measurable q) (expectation q) (bounded q) (replacements q)

/-- The unconditional failure mass of a finite mixture of history-indexed
fresh kernels.  This is the finite law-of-total-probability expression used
below; each `μ q` is a normalized fresh law and `weight q` is the probability
of reaching transcript `q`. -/
def finiteMixtureFailure {History : Type} [Fintype History]
    [MeasurableSpace Ω] (weight : History → ℝ) (μ : History → Measure Ω)
    (failure : History → Set Ω) : ℝ :=
  ∑ q, weight q * (μ q).real (failure q)

/-- A finite mixture of history-wise bounds has the same common bound. -/
theorem finite_mixture_failure_le {History : Type} [Fintype History]
    [MeasurableSpace Ω] (weight : History → ℝ) (μ : History → Measure Ω)
    (failure : History → Set Ω) (δ : ℝ)
    (weight_nonneg : ∀ q, 0 ≤ weight q)
    (weight_sum : ∑ q, weight q = 1)
    (kernel_bound : ∀ q, (μ q).real (failure q) ≤ δ) :
    finiteMixtureFailure weight μ failure ≤ δ := by
  unfold finiteMixtureFailure
  calc
    (∑ q, weight q * (μ q).real (failure q)) ≤ ∑ q, weight q * δ := by
      exact Finset.sum_le_sum fun q _ =>
        mul_le_mul_of_nonneg_left (kernel_bound q) (weight_nonneg q)
    _ = δ * ∑ q, weight q := by
      rw [Finset.mul_sum]
      exact Finset.sum_congr rfl (fun q _ => mul_comm _ _)
    _ = δ := by rw [weight_sum, mul_one]

/--
The existing frozen-round concentration theorem therefore yields a failure
bound after any finite distribution of past transcripts.  It preserves both
soundness and the sufficient-margin power clause because its failure event is
the existing `Integration.RoundWorks` negation.
-/
theorem kernelwise_statistical_selection_mixture_failure_le_delta
    {History Candidate : Type} {m n b : Nat} [Fintype History]
    [MeasurableSpace Ω]
    (weight : History → ℝ) (weight_nonneg : ∀ q, 0 ≤ weight q)
    (weight_sum : ∑ q, weight q = 1)
    (μ : History → Measure Ω) (probability : ∀ q, IsProbabilityMeasure (μ q))
    (frozen : History → Selection.FrozenCandidates Candidate m)
    (d : History → Fin m → ℕ → Ω → ℝ)
    (observed : History → Ω → Fin m → Fin n → ℝ)
    (target : History → Fin m → ℝ) (δ : ℝ)
    (hm : 0 < m) (hn : 0 < n) (hδ0 : 0 < δ) (hδ1 : δ < 1)
    (independent : ∀ (q : History) (k : Fin m), iIndepFun (d q k) (μ q))
    (measurable : ∀ (q : History) (k : Fin m) i, i < n → AEMeasurable (d q k i) (μ q))
    (expectation : ∀ (q : History) (k : Fin m) i, i < n →
      (∫ ω, d q k i ω ∂(μ q)) = target q k)
    (bounded : ∀ (q : History) (ω : Ω), Selection.BoundedGains
      (Integration.sampleRows (d q) n ω) (observed q ω))
    (replacements : ∀ (q : History) (ω : Ω), Selection.ReplacementWitness
      (Integration.sampleRows (d q) n ω) (observed q ω) b) :
    finiteMixtureFailure weight μ
      (fun q => {ω | ¬ Integration.RoundWorks (frozen q) (observed q ω)
        (target q) (calibratedRadius m n δ) b}) ≤ δ := by
  apply finite_mixture_failure_le weight μ _ δ weight_nonneg weight_sum
  exact kernelwise_statistical_selection_failure_le_delta μ probability frozen d observed target
    δ hm hn hδ0 hδ1 independent measurable expectation bounded replacements

/-- A finite transcript partition converts a history-conditional round bound
into its ordinary, unconditional failure probability bound. -/
theorem history_conditional_failure_le {h : Nat}
    [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    (history : Fin h → Set Ω) (failure : Set Ω) (α : ℝ)
    (history_measurable : ∀ i, MeasurableSet (history i))
    (failure_measurable : MeasurableSet failure)
    (history_disjoint : Pairwise fun i j => Disjoint (history i) (history j))
    (history_cover : (⋃ i, history i) = Set.univ)
    (conditional_bound : HistoryConditionalFailureBound μ history failure α) :
    μ.real failure ≤ α := by
  have restricted_disjoint : Pairwise fun i j =>
      Disjoint (failure ∩ history i) (failure ∩ history j) := by
    intro i j hij
    refine Set.disjoint_left.2 ?_
    intro ω hleft hright
    exact (Set.disjoint_left.1 (history_disjoint hij)) hleft.2 hright.2
  have restricted_measurable : ∀ i, MeasurableSet (failure ∩ history i) := by
    intro i
    exact failure_measurable.inter (history_measurable i)
  have history_measure : μ.real (⋃ i, history i) = ∑ i, μ.real (history i) :=
    measureReal_iUnion_fintype history_disjoint history_measurable
  calc
    μ.real failure = μ.real (⋃ i, failure ∩ history i) := by
      congr 1
      ext ω
      simp only [Set.mem_iUnion, Set.mem_inter_iff]
      constructor
      · intro hfailure
        obtain ⟨i, hi⟩ : ∃ i, ω ∈ history i := by
          have : ω ∈ ⋃ i, history i := by
            rw [history_cover]
            exact Set.mem_univ _
          exact Set.mem_iUnion.1 this
        exact ⟨i, hfailure, hi⟩
      · rintro ⟨i, hfailure, _⟩
        exact hfailure
    _ = ∑ i, μ.real (failure ∩ history i) :=
      measureReal_iUnion_fintype restricted_disjoint restricted_measurable
    _ ≤ ∑ i, α * μ.real (history i) := by
      exact Finset.sum_le_sum (fun i _ => conditional_bound i)
    _ = α * ∑ i, μ.real (history i) := by
      rw [Finset.mul_sum]
    _ = α * μ.real (⋃ i, history i) := by rw [history_measure]
    _ = α := by simp [history_cover]

/-- A finite family of already-controlled round failures obeys the sum of its
declared failure budgets.  No independence between different rounds is used. -/
theorem finite_alpha_spending_failure_le {rounds : Nat}
    [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    (failure : Fin rounds → Set Ω) (α : Fin rounds → ℝ)
    (round_bound : ∀ r, μ.real (failure r) ≤ α r) :
    μ.real (⋃ r, failure r) ≤ ∑ r, α r := by
  calc
    μ.real (⋃ r, failure r) ≤ ∑ r, μ.real (failure r) :=
      measureReal_iUnion_fintype_le failure
    _ ≤ ∑ r, α r := by
      exact Finset.sum_le_sum (fun r _ => round_bound r)

/-- The event that a failing round was actually reached by a data-dependent
stopping policy.  Each `enabled r` may depend on the entire earlier transcript. -/
def stoppedFailure {rounds : Nat} (failure enabled : Fin rounds → Set Ω) : Set Ω :=
  ⋃ r, failure r ∩ enabled r

/-- Stopping may remove scheduled rounds, but it cannot increase the union of
their failure events. -/
theorem stopped_failure_subset {rounds : Nat}
    (failure enabled : Fin rounds → Set Ω) :
    stoppedFailure failure enabled ⊆ ⋃ r, failure r := by
  intro ω hω
  simp only [stoppedFailure, Set.mem_iUnion, Set.mem_inter_iff] at hω
  rcases hω with ⟨r, hfailure, _⟩
  exact Set.mem_iUnion.2 ⟨r, hfailure⟩

/-- Finite alpha spending remains valid for a data-dependent finite stopping
prefix, provided the round bounds already cover the corresponding fresh
evaluation experiment. -/
theorem stopped_failure_le_alpha_spending {rounds : Nat}
    [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    (failure enabled : Fin rounds → Set Ω) (α : Fin rounds → ℝ)
    (round_bound : ∀ r, μ.real (failure r) ≤ α r) :
    μ.real (stoppedFailure failure enabled) ≤ ∑ r, α r := by
  calc
    μ.real (stoppedFailure failure enabled) ≤ μ.real (⋃ r, failure r) :=
      measureReal_mono (stopped_failure_subset failure enabled)
    _ ≤ ∑ r, α r := finite_alpha_spending_failure_le μ failure α round_bound

end
end HSWMStatisticalLearning.AdaptiveRounds
