import Std

/-!
# HSWM cellular metaneural core

This module formalizes a protective-belt contract, not an empirical proof that
an implementation is a larger AI.

* A logical LLM cell is a typed, stateful semantic function.
* A semantic synapse is an operator on an n-ary packet list, not merely a scalar.
* A realized HSWM exposes the same stateful-cell interface as one cell.
* Plasticity seals a trace before the outcome enters its typed interface.
* Morphogenesis proposes exactly one mutation class per structural epoch.
-/

namespace HSWM

universe u

/-- Length-aligned relational evidence for heterogeneous tail packets. -/
inductive All2 {Left Right : Type u} (relation : Left -> Right -> Prop) :
    List Left -> List Right -> Prop where
  | nil : All2 relation [] []
  | cons {left right lefts rights} :
      relation left right ->
      All2 relation lefts rights ->
      All2 relation (left :: lefts) (right :: rights)

/-- A logical LLM cell. `modelKey` may be shared by several logical cells;
`role`, ports, local state, and network position distinguish the cells. -/
structure Cell (Packet : Type u) where
  State : Type u
  modelKey : String
  role : String
  accepts : Packet -> Prop
  emits : Packet -> Prop
  step : Packet -> State -> Packet × State
  step_typed : forall (packet : Packet) (state : State),
    accepts packet -> emits (step packet state).1

namespace Cell

/-- Two logical cells may share one frozen foundation-model checkpoint. -/
def sharesMicroWeights {Packet : Type u} (left right : Cell Packet) : Prop :=
  left.modelKey = right.modelKey

/-- Sequential cell composition. Compatibility is an explicit contract rather
than an assumption hidden in a prompt. -/
def thenCell {Packet : Type u} (first second : Cell Packet)
    (compatible : forall packet, first.emits packet -> second.accepts packet) :
    Cell Packet where
  State := first.State × second.State
  modelKey := first.modelKey ++ "+" ++ second.modelKey
  role := first.role ++ ">>" ++ second.role
  accepts := first.accepts
  emits := second.emits
  step := fun packet state =>
    let firstResult := first.step packet state.1
    let secondResult := second.step firstResult.1 state.2
    (secondResult.1, (firstResult.2, secondResult.2))
  step_typed := by
    intro packet state accepted
    dsimp
    have firstEmits := first.step_typed packet state.1 accepted
    have secondAccepts := compatible _ firstEmits
    exact second.step_typed _ _ secondAccepts

theorem thenCell_preserves_output_type {Packet : Type u}
    (first second : Cell Packet)
    (compatible : forall packet, first.emits packet -> second.accepts packet)
    (packet : Packet) (state : (thenCell first second compatible).State)
    (accepted : (thenCell first second compatible).accepts packet) :
    (thenCell first second compatible).emits
      ((thenCell first second compatible).step packet state).1 :=
  (thenCell first second compatible).step_typed packet state accepted

end Cell

/-- An operator-valued macro-synapse. `transform` may jointly interpret any
finite n-ary packet tuple; the remaining fields are contextual functions rather
than one universal similarity scalar. -/
structure SemanticSynapse (Packet Context : Type u) where
  transform : List Packet -> Context -> Packet
  gate : Context -> Bool
  efficacy : Context -> Int
  uncertainty : Context -> Nat
  relation : String

/-- A fixed-epoch HSWM. Cell and edge carriers are types, so every endpoint is
referentially total. `typedSynapse` proves that emitted tail packets become an
accepted packet at the head cell. -/
structure CellularHSWM (CellId Packet Context : Type u) where
  cell : CellId -> Cell Packet
  EdgeId : Type u
  tail : EdgeId -> List CellId
  head : EdgeId -> CellId
  synapse : EdgeId -> SemanticSynapse Packet Context
  tail_nonempty : forall edge, tail edge ≠ []
  typedSynapse : forall (edge : EdgeId) (packets : List Packet) (context : Context),
    All2 (fun cellId packet => (cell cellId).emits packet)
      (tail edge) packets ->
    (cell (head edge)).accepts ((synapse edge).transform packets context)

namespace CellularHSWM

/-- A disabled semantic synapse fails closed. -/
def route {CellId Packet Context : Type u}
    (network : CellularHSWM CellId Packet Context)
    (edge : network.EdgeId) (packets : List Packet) (context : Context) :
    Option Packet :=
  if (network.synapse edge).gate context then
    some ((network.synapse edge).transform packets context)
  else
    none

theorem route_disabled {CellId Packet Context : Type u}
    (network : CellularHSWM CellId Packet Context)
    (edge : network.EdgeId) (packets : List Packet) (context : Context)
    (disabled : (network.synapse edge).gate context = false) :
    network.route edge packets context = none := by
  simp [route, disabled]

theorem route_enabled_is_head_typed {CellId Packet Context : Type u}
    (network : CellularHSWM CellId Packet Context)
    (edge : network.EdgeId) (packets : List Packet) (context : Context)
    (enabled : (network.synapse edge).gate context = true)
    (tailsTyped :
      All2 (fun cellId packet => (network.cell cellId).emits packet)
        (network.tail edge) packets) :
    exists routed,
      network.route edge packets context = some routed ∧
      (network.cell (network.head edge)).accepts routed := by
  refine Exists.intro ((network.synapse edge).transform packets context) ?_
  constructor
  · simp [route, enabled]
  · exact network.typedSynapse edge packets context tailsTyped

end CellularHSWM

/-- Operational semantics for one bounded recurrent realization of a network.
Scheduling, stopping, and budgets live here rather than being smuggled into the
static hypergraph. -/
structure Realization {CellId Packet Context : Type u}
    (network : CellularHSWM CellId Packet Context) where
  GlobalState : Type u
  accepts : Packet -> Prop
  emits : Packet -> Prop
  run : Packet -> GlobalState -> Packet × GlobalState
  run_typed : forall (packet : Packet) (state : GlobalState),
    accepts packet -> emits (run packet state).1

namespace Realization

/-- Self-similar closure: after hiding internal state, a realized HSWM has the
same typed stateful-function interface as a logical cell. -/
def asCell {CellId Packet Context : Type u}
    {network : CellularHSWM CellId Packet Context}
    (realization : Realization network) : Cell Packet where
  State := realization.GlobalState
  modelKey := "HSWM/MACRO"
  role := "self-similar-open-system"
  accepts := realization.accepts
  emits := realization.emits
  step := realization.run
  step_typed := realization.run_typed

@[simp] theorem asCell_step_is_run {CellId Packet Context : Type u}
    {network : CellularHSWM CellId Packet Context}
    (realization : Realization network) :
    realization.asCell.step = realization.run := rfl

theorem asCell_preserves_type {CellId Packet Context : Type u}
    {network : CellularHSWM CellId Packet Context}
    (realization : Realization network)
    (packet : Packet) (state : realization.GlobalState)
    (accepted : realization.accepts packet) :
    realization.asCell.emits (realization.asCell.step packet state).1 :=
  realization.run_typed packet state accepted

end Realization

/-- Three-factor plasticity interface. Crucially, `seal` cannot inspect an
`Outcome`: the outcome only enters the later `credit` function. -/
structure PlasticityClock
    (Trajectory Trace Outcome Weight Delta : Type u) where
  sealTrace : Trajectory -> Trace
  credit : Trace -> Outcome -> Delta
  applyDelta : Weight -> Delta -> Weight
  rollback : Weight -> Delta -> Weight
  rollback_apply : forall weight delta,
    rollback (applyDelta weight delta) delta = weight

namespace PlasticityClock

theorem candidate_is_reversible
    {Trajectory Trace Outcome Weight Delta : Type u}
    (clock : PlasticityClock Trajectory Trace Outcome Weight Delta)
    (weight : Weight) (delta : Delta) :
    clock.rollback (clock.applyDelta weight delta) delta = weight :=
  clock.rollback_apply weight delta

end PlasticityClock

inductive MutationClass where
  | cell
  | synapse
  | topology
  | interface
  deriving DecidableEq, Repr

/-- One proposal carries exactly one mutation class. This encodes the
single-mutation-class structural-epoch rule. -/
structure MutationProposal (Network : Type u) where
  candidate : Network
  kind : MutationClass
  evidenceDigest : String

structure MorphogenesisClock (Network Evidence : Type u) where
  propose : Network -> Evidence -> MutationProposal Network
  accept : Evidence -> MutationProposal Network -> Bool

namespace MorphogenesisClock

def step {Network Evidence : Type u}
    (clock : MorphogenesisClock Network Evidence)
    (network : Network) (evidence : Evidence) : Network :=
  let proposal := clock.propose network evidence
  if clock.accept evidence proposal then proposal.candidate else network

theorem rejected_proposal_is_noop {Network Evidence : Type u}
    (clock : MorphogenesisClock Network Evidence)
    (network : Network) (evidence : Evidence)
    (rejected : clock.accept evidence (clock.propose network evidence) = false) :
    clock.step network evidence = network := by
  simp [step, rejected]

end MorphogenesisClock

/-- Empirical obligations. Lean can preserve their logical separation but does
not manufacture evidence that a runtime satisfies them. -/
structure ScientificConditions where
  persistentMacroState : Prop
  closedOutcomeCredit : Prop
  semanticWeightMediation : Prop
  topologyMediation : Prop
  transferBeyondTranscript : Prop
  beatsStrongestCellControl : Prop
  retentionAndRollback : Prop

def LargerAIConditions (conditions : ScientificConditions) : Prop :=
  conditions.persistentMacroState ∧
  conditions.closedOutcomeCredit ∧
  conditions.semanticWeightMediation ∧
  conditions.topologyMediation ∧
  conditions.transferBeyondTranscript ∧
  conditions.beatsStrongestCellControl ∧
  conditions.retentionAndRollback

/-- Merely wiring cells together is deliberately not enough. -/
def connectedOnlyConditions : ScientificConditions where
  persistentMacroState := True
  closedOutcomeCredit := False
  semanticWeightMediation := False
  topologyMediation := False
  transferBeyondTranscript := False
  beatsStrongestCellControl := False
  retentionAndRollback := False

theorem connection_alone_is_not_larger_ai :
    Not (LargerAIConditions connectedOnlyConditions) := by
  simp [LargerAIConditions, connectedOnlyConditions]

theorem larger_ai_requires_semantic_weight_mediation
    (conditions : ScientificConditions)
    (satisfies : LargerAIConditions conditions) :
    conditions.semanticWeightMediation :=
  satisfies.2.2.1

end HSWM
