import HSWMLLMSemanticGraph
import HSWMStatisticalLearning.Selection
import HSWMStatisticalLearning.Integration

/-!
# Frozen statistical candidates are actual canonical graph successors

The family is frozen before evaluation. Candidate proposals may depend on past
outcomes, but this construction has no access to the fresh evaluation rows.
Every candidate is the result of the existing trace-bound `learn` operation.
Selection returns one of those exact graph states, and subsequent `step` calls
read the selected state's current relation. This is a mathematical connection
to the existing graph model, not TypeScript refinement or real-LLM fidelity.

The pure `Interpreter` and payoff remain declared functions. To apply a later
probability theorem to stochastic LLMs, the sampled task must also carry all
relevant execution randomness/state, or a probabilistic realization must first
be supplied. The truth and independence of the external outcome are not proved.
-/

namespace HSWMStatisticalLearning.CanonicalBridge

noncomputable section

open HSWM.LLMSemanticGraph
open Selection
open MeasureTheory ProbabilityTheory

variable {m n : Nat}

/-- Preserve the frozen execution operator and supply one past-data proposal. -/
def withRevision (operator : Interpreter) (proposal : Proposal) : Interpreter
  | .execute context => operator (.execute context)
  | .revise _ _ _ => proposal

/-- Immutable inputs from before fresh evaluation, including the common predecessor. -/
structure FrozenGraphRound (m : Nat) where
  baseline : GraphState
  operator : Interpreter
  trainingTrace : Trace
  trainingOutcome : Outcome
  outcomeBound : trainingOutcome.traceUid = trainingTrace.traceUid
  proposals : Fin m → Proposal
  cost : Fin m → ℝ

def trainingReceipt (round : FrozenGraphRound m) : StepReceipt :=
  step round.operator round.baseline round.trainingTrace

def candidate (round : FrozenGraphRound m) (k : Fin m) : GraphState :=
  acceptedState (withRevision round.operator (round.proposals k))
    round.baseline (trainingReceipt round) round.trainingOutcome

/-- The candidate family is obtained through the existing checked learning binding. -/
theorem candidate_is_bound_learn (round : FrozenGraphRound m) (k : Fin m) :
    learn (withRevision round.operator (round.proposals k)) round.baseline
      (trainingReceipt round) round.trainingOutcome = some (candidate round k) := by
  apply learn_accepts_exactly_bound_receipt
  · exact round.outcomeBound
  · rfl
  · rfl

theorem candidate_reads_proposed_meaning (round : FrozenGraphRound m) (k : Fin m) :
    (read (candidate round k) round.trainingTrace.relationUid).semanticText =
      (round.proposals k).semanticText := by
  simp [candidate, trainingReceipt, acceptedState, HSWM.LLMSemanticGraph.read, replace, revise,
    revisionProposal, withRevision, step]

theorem candidate_keeps_owner_and_roles (round : FrozenGraphRound m) (k : Fin m) :
    let before := round.baseline.current round.trainingTrace.relationUid
    let after := read (candidate round k) round.trainingTrace.relationUid
    after.owner = before.owner ∧ after.source = before.source ∧
      after.recipient = before.recipient ∧ after.context = before.context ∧
      after.extraRoles = before.extraRoles := by
  simp [candidate, trainingReceipt, acceptedState, HSWM.LLMSemanticGraph.read, replace, revise, step]

theorem candidate_keeps_prior_history (round : FrozenGraphRound m) (k : Fin m) :
    (candidate round k).history =
      round.baseline.current round.trainingTrace.relationUid :: round.baseline.history := rfl

def frozenCandidates (round : FrozenGraphRound m) : FrozenCandidates GraphState m :=
  { payload := candidate round, cost := round.cost }

/-- Mathematical exact-real choice; no claim about extracted floating-point code. -/
noncomputable def commit (round : FrozenGraphRound m)
    (observed : Fin m → Fin n → ℝ) (radius contamination : ℝ) : GraphState :=
  match selectCertified (frozenCandidates round) observed radius contamination with
  | none => round.baseline
  | some k => candidate round k

theorem selected_commit_is_exact_candidate (round : FrozenGraphRound m)
    (observed : Fin m → Fin n → ℝ) (radius contamination : ℝ) (k : Fin m)
    (selected : selectCertified (frozenCandidates round) observed radius contamination = some k) :
    commit round observed radius contamination = candidate round k := by
  simp [commit, selected]

theorem rejected_commit_is_exact_baseline (round : FrozenGraphRound m)
    (observed : Fin m → Fin n → ℝ) (radius contamination : ℝ)
    (rejected : selectCertified (frozenCandidates round) observed radius contamination = none) :
    commit round observed radius contamination = round.baseline := by
  simp [commit, rejected]

/-- Future execution consumes the selected canonical state, rather than a shadow score. -/
theorem future_step_reads_selected_graph (round : FrozenGraphRound m)
    (observed : Fin m → Fin n → ℝ) (radius contamination : ℝ) (k : Fin m)
    (selected : selectCertified (frozenCandidates round) observed radius contamination = some k)
    (futureTrace : Trace) :
    (step round.operator (commit round observed radius contamination) futureTrace).serialized =
      serialize ((candidate round k).current futureTrace.relationUid) futureTrace := by
  rw [selected_commit_is_exact_candidate round observed radius contamination k selected]
  rfl

/-- Utility difference is evaluated on the actual existing canonical Step outputs. -/
def graphGain {Task : Type} (round : FrozenGraphRound m)
    (trace : Task → Trace) (payoff : Task → StepReceipt → ℝ) (k : Fin m) (task : Task) : ℝ :=
  payoff task (step round.operator (candidate round k) (trace task)) -
    payoff task (step round.operator round.baseline (trace task))

theorem graph_gain_bounded {Task : Type} (round : FrozenGraphRound m)
    (trace : Task → Trace) (payoff : Task → StepReceipt → ℝ)
    (bounded : ∀ task receipt, 0 ≤ payoff task receipt ∧ payoff task receipt ≤ 1)
    (k : Fin m) (task : Task) :
    -1 ≤ graphGain round trace payoff k task ∧ graphGain round trace payoff k task ≤ 1 := by
  have hb := bounded task (step round.operator round.baseline (trace task))
  have hc := bounded task (step round.operator (candidate round k) (trace task))
  unfold graphGain
  constructor <;> linarith

theorem selected_commit_gain_is_graph_gain {Task : Type} (round : FrozenGraphRound m)
    (trace : Task → Trace) (payoff : Task → StepReceipt → ℝ)
    (observed : Fin m → Fin n → ℝ) (radius contamination : ℝ) (k : Fin m)
    (selected : selectCertified (frozenCandidates round) observed radius contamination = some k)
    (task : Task) :
    payoff task (step round.operator (commit round observed radius contamination) (trace task)) -
      payoff task (step round.operator round.baseline (trace task)) =
        graphGain round trace payoff k task := by
  rw [selected_commit_is_exact_candidate round observed radius contamination k selected]
  rfl

/-- Population gain is the expectation of the actual canonical Step difference. -/
def expectedGraphGain {Task Ω : Type} [MeasurableSpace Ω]
    (μ : Measure Ω) (round : FrozenGraphRound m) (trace : Task → Trace)
    (payoff : Task → StepReceipt → ℝ) (samples : ℕ → Ω → Task) : Fin m → ℝ :=
  fun k => ∫ ω, graphGain round trace payoff k (samples 0 ω) ∂μ

/--
The same frozen graph family supplies candidate payloads, actual Step gains,
and the state selected for later execution. Fresh task draws are independent;
all candidates may use the same draws, so their errors can be correlated.
Equal row expectations are the population assumption (iid implies it), not an
assumption that revision improves anything. Candidate generation, outcome
truth, and real-LLM realization remain outside this mathematical theorem.
-/
theorem canonical_graph_selection_failure_bound {Task Ω : Type}
    [MeasurableSpace Ω] [MeasurableSpace Task]
    (μ : Measure Ω) [IsProbabilityMeasure μ]
    (round : FrozenGraphRound m) (trace : Task → Trace)
    (payoff : Task → StepReceipt → ℝ) (samples : ℕ → Ω → Task)
    (observed : Ω → Fin m → Fin n → ℝ) (radius : ℝ) (b : Nat)
    (hn : 0 < n) (hradius : 0 ≤ radius)
    (independent : iIndepFun samples μ)
    (sampleMeasurable : ∀ i, i < n → AEMeasurable (samples i) μ)
    (gainMeasurable : ∀ k, Measurable (graphGain round trace payoff k))
    (payoffBounded : ∀ task receipt, 0 ≤ payoff task receipt ∧ payoff task receipt ≤ 1)
    (commonMean : ∀ k i, i < n →
      (∫ ω, graphGain round trace payoff k (samples i ω) ∂μ) =
        expectedGraphGain μ round trace payoff samples k)
    (observedBounded : ∀ ω k i, -1 ≤ observed ω k i ∧ observed ω k i ≤ 1)
    (replacements : ∀ ω, ReplacementWitness
      (fun k (i : Fin n) => graphGain round trace payoff k (samples i.val ω)) (observed ω) b) :
    μ.real {ω | ¬ Integration.RoundWorks (frozenCandidates round) (observed ω)
      (expectedGraphGain μ round trace payoff samples) radius b} ≤
        2 * (m : ℝ) * Real.exp (-(n : ℝ) * radius ^ 2 / 2) := by
  apply Integration.statistical_selection_failure_bound μ (frozenCandidates round)
    (fun k i ω => graphGain round trace payoff k (samples i ω)) observed
    (expectedGraphGain μ round trace payoff samples) radius hn hradius
  · intro k
    exact independent.comp (fun _ => graphGain round trace payoff k) (fun _ => gainMeasurable k)
  · intro k i hi
    exact (gainMeasurable k).comp_aemeasurable (sampleMeasurable i hi)
  · exact commonMean
  · intro ω
    constructor
    · intro k i
      exact graph_gain_bounded round trace payoff payoffBounded k (samples i.val ω)
    · exact observedBounded ω
  · exact replacements

/-- The canonical graph selection theorem at an explicit confidence budget. -/
theorem canonical_graph_selection_failure_le_delta {Task Ω : Type}
    [MeasurableSpace Ω] [MeasurableSpace Task]
    (μ : Measure Ω) [IsProbabilityMeasure μ]
    (round : FrozenGraphRound m) (trace : Task → Trace)
    (payoff : Task → StepReceipt → ℝ) (samples : ℕ → Ω → Task)
    (observed : Ω → Fin m → Fin n → ℝ) (δ : ℝ) (b : Nat)
    (hm : 0 < m) (hn : 0 < n) (hδ0 : 0 < δ) (hδ1 : δ < 1)
    (independent : iIndepFun samples μ)
    (sampleMeasurable : ∀ i, i < n → AEMeasurable (samples i) μ)
    (gainMeasurable : ∀ k, Measurable (graphGain round trace payoff k))
    (payoffBounded : ∀ task receipt, 0 ≤ payoff task receipt ∧ payoff task receipt ≤ 1)
    (commonMean : ∀ k i, i < n →
      (∫ ω, graphGain round trace payoff k (samples i ω) ∂μ) =
        expectedGraphGain μ round trace payoff samples k)
    (observedBounded : ∀ ω k i, -1 ≤ observed ω k i ∧ observed ω k i ≤ 1)
    (replacements : ∀ ω, ReplacementWitness
      (fun k (i : Fin n) => graphGain round trace payoff k (samples i.val ω)) (observed ω) b) :
    μ.real {ω | ¬ Integration.RoundWorks (frozenCandidates round) (observed ω)
      (expectedGraphGain μ round trace payoff samples) (calibratedRadius m n δ) b} ≤ δ := by
  have bound := canonical_graph_selection_failure_bound μ round trace payoff samples observed
    (calibratedRadius m n δ) b hn (calibratedRadius_nonneg m n δ)
    independent sampleMeasurable gainMeasurable payoffBounded commonMean observedBounded replacements
  rwa [Integration.calibrated_failure_eq_delta hm hn hδ0 hδ1] at bound

end
end HSWMStatisticalLearning.CanonicalBridge
