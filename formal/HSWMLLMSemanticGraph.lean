import Std

/-!
# LLM-executed semantic hypergraph: structural learning witness

This file makes a deliberately small, executable model of the part of HSWM in
which one LLM interprets a role-bearing relation, emits a revision proposal,
and an outcome-qualified transition installs a new immutable relation version.
The interpreter is an arbitrary pure function, so the proofs establish exact
dataflow, role/provenance preservation, and frame properties for *every* LLM
output.  They do not establish that token text refers to an external object,
that an outcome is true, or that an LLM is calibrated, useful, or causally
effective.

`current` is the operational hypergraph read view.  `history` is not a cache:
each accepted revision prepends the exact prior relation.  A relation has three
distinct n-ary positions (`source`, `recipient`, `context`); they are never
serialized as an unordered collection and a proposal cannot replace them.
-/

namespace HSWM.LLMSemanticGraph

/-- An immutable canonical relation version with role-bearing incidence. -/
structure Relation where
  uid : Nat
  revision : Nat
  owner : Nat
  source : Nat
  recipient : Nat
  context : Nat
  semanticText : String
  disposition : String
  evidenceRefs : List Nat
  extraRoles : List (String × Nat)
deriving DecidableEq, Repr

/-- The operational graph plus all superseded immutable relation versions. -/
structure GraphState where
  current : Nat -> Relation
  history : List Relation

/-- A pre-outcome trajectory. `relationUid` selects exactly one relation read. -/
structure Trace where
  traceUid : Nat
  relationUid : Nat
  inputToken : String
deriving DecidableEq, Repr

/-- A separately supplied post-Step observation; source independence/truth is not proved. -/
structure Outcome where
  traceUid : Nat
  evidenceRef : Nat
  observedToken : String
deriving DecidableEq, Repr

/-- The complete role-sensitive input made available to the LLM interpreter. -/
structure SerializedContext where
  relationUid : Nat
  priorRevision : Nat
  owner : Nat
  source : Nat
  recipient : Nat
  context : Nat
  semanticText : String
  disposition : String
  priorEvidenceRefs : List Nat
  extraRoles : List (String × Nat)
  traceUid : Nat
  inputToken : String
deriving DecidableEq, Repr

/-- Serialize every operationally relevant field; no role is reduced to a bag. -/
def serialize (relation : Relation) (trace : Trace) : SerializedContext where
  relationUid := relation.uid
  priorRevision := relation.revision
  owner := relation.owner
  source := relation.source
  recipient := relation.recipient
  context := relation.context
  semanticText := relation.semanticText
  disposition := relation.disposition
  priorEvidenceRefs := relation.evidenceRefs
  extraRoles := relation.extraRoles
  traceUid := trace.traceUid
  inputToken := trace.inputToken

/-- The LLM can propose semantic content and a transition disposition only. -/
structure Proposal where
  semanticText : String
  disposition : String
deriving DecidableEq, Repr

/-- The same model is used before and after outcome, with the phase in its typed input. -/
inductive InterpreterInput where
  | execute : SerializedContext -> InterpreterInput
  | revise : SerializedContext -> Proposal -> Outcome -> InterpreterInput
deriving DecidableEq, Repr

/-- A frozen or version-pinned LLM realization is modelled as one pure interpreter. -/
abbrev Interpreter := InterpreterInput -> Proposal

/-- The sealed Step output records the exact relation and input seen by the LLM. -/
structure StepReceipt where
  relation : Relation
  trace : Trace
  serialized : SerializedContext
  proposal : Proposal
deriving DecidableEq, Repr

/-- Step reads the selected current relation and lets the same interpreter consume its serialization. -/
def step (interpreter : Interpreter) (state : GraphState)
    (trace : Trace) : StepReceipt :=
  let relation := state.current trace.relationUid
  let serialized := serialize relation trace
  { relation, trace, serialized, proposal := interpreter (.execute serialized) }

/-- One immutable successor; relation roles and old evidence are retained verbatim. -/
def revise (before : Relation) (outcome : Outcome) (proposal : Proposal) : Relation :=
  { uid := before.uid
    revision := before.revision + 1
    owner := before.owner
    source := before.source
    recipient := before.recipient
    context := before.context
    semanticText := proposal.semanticText
    disposition := proposal.disposition
    evidenceRefs := outcome.evidenceRef :: before.evidenceRefs
    extraRoles := before.extraRoles }

/-- The post-outcome LLM call is the candidate actually installed by learning. -/
def revisionProposal (interpreter : Interpreter) (receipt : StepReceipt) (outcome : Outcome) : Proposal :=
  interpreter (.revise receipt.serialized receipt.proposal outcome)

/-- Replace exactly one address in the live read view. -/
def replace (current : Nat -> Relation) (uid : Nat) (next : Relation) : Nat -> Relation :=
  fun other => if other = uid then next else current other

/-- The deterministic successor selected after all binding checks have passed. -/
def acceptedState (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) : GraphState :=
  { current := replace state.current receipt.trace.relationUid
      (revise receipt.relation outcome (revisionProposal interpreter receipt outcome))
    history := receipt.relation :: state.history }

/-- Learn fails closed unless outcome and receipt bind to the same trace and the read snapshot is current. -/
def learn (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) : Option GraphState :=
  if outcome.traceUid = receipt.trace.traceUid ∧
      state.current receipt.trace.relationUid = receipt.relation ∧
      receipt.serialized = serialize receipt.relation receipt.trace then
    some (acceptedState interpreter state receipt outcome)
  else none

/-- The operational relation readout. -/
def read (state : GraphState) (uid : Nat) : Relation := state.current uid

/-- Schema-relative identity condition for the total current-address representation. -/
def Addressed (state : GraphState) : Prop := forall uid, (state.current uid).uid = uid

theorem serialize_preserves_roles (relation : Relation) (trace : Trace) :
    (serialize relation trace).source = relation.source ∧
    (serialize relation trace).recipient = relation.recipient ∧
    (serialize relation trace).context = relation.context := by
  exact ⟨rfl, rfl, rfl⟩

theorem serialize_preserves_semantic_and_evidence (relation : Relation) (trace : Trace) :
    (serialize relation trace).semanticText = relation.semanticText ∧
    (serialize relation trace).priorEvidenceRefs = relation.evidenceRefs := by
  exact ⟨rfl, rfl⟩

theorem serialize_preserves_extra_role_bindings (relation : Relation) (trace : Trace) :
    (serialize relation trace).extraRoles = relation.extraRoles := rfl

theorem step_uses_current_relation (interpreter : Interpreter) (state : GraphState)
    (trace : Trace) :
    (step interpreter state trace).relation = state.current trace.relationUid := rfl

theorem step_gives_llm_exact_serialization (interpreter : Interpreter) (state : GraphState)
    (trace : Trace) :
    (step interpreter state trace).proposal =
      interpreter (.execute (serialize (state.current trace.relationUid) trace)) := rfl

theorem revise_preserves_roles_and_owner (before : Relation) (outcome : Outcome) (proposal : Proposal) :
    (revise before outcome proposal).owner = before.owner ∧
    (revise before outcome proposal).source = before.source ∧
    (revise before outcome proposal).recipient = before.recipient ∧
    (revise before outcome proposal).context = before.context := by
  exact ⟨rfl, rfl, rfl, rfl⟩

theorem revise_preserves_extra_role_bindings (before : Relation) (outcome : Outcome)
    (proposal : Proposal) : (revise before outcome proposal).extraRoles = before.extraRoles := rfl

theorem revise_binds_outcome_and_increments_version (before : Relation)
    (outcome : Outcome) (proposal : Proposal) :
    (revise before outcome proposal).revision = before.revision + 1 ∧
    (revise before outcome proposal).evidenceRefs = outcome.evidenceRef :: before.evidenceRefs := by
  exact ⟨rfl, rfl⟩

theorem revise_uses_exact_llm_proposal (before : Relation) (outcome : Outcome)
    (proposal : Proposal) :
    (revise before outcome proposal).semanticText = proposal.semanticText ∧
    (revise before outcome proposal).disposition = proposal.disposition := by
  exact ⟨rfl, rfl⟩

/-- The post-outcome call receives the exact Step serialization, prediction, and observation. -/
theorem revision_proposal_receives_exact_outcome (interpreter : Interpreter)
    (receipt : StepReceipt) (outcome : Outcome) :
    revisionProposal interpreter receipt outcome =
      interpreter (.revise receipt.serialized receipt.proposal outcome) := rfl

/-- A concrete interpreter demonstrates that distinct observations can install distinct semantic text. -/
def outcomeSensitiveInterpreter : Interpreter
  | .execute _ => { semanticText := "prediction" , disposition := "predict" }
  | .revise _ _ outcome => { semanticText := outcome.observedToken, disposition := "revise" }

theorem outcome_sensitive_revision_witness (receipt : StepReceipt) (left right : Outcome) :
    (revisionProposal outcomeSensitiveInterpreter receipt left).semanticText = left.observedToken ∧
    (revisionProposal outcomeSensitiveInterpreter receipt right).semanticText = right.observedToken := by
  exact ⟨rfl, rfl⟩

theorem outcome_sensitive_successors_differ (receipt : StepReceipt) (left right : Outcome)
    (different : left.observedToken ≠ right.observedToken) :
    (revise receipt.relation left
      (revisionProposal outcomeSensitiveInterpreter receipt left)).semanticText ≠
    (revise receipt.relation right
      (revisionProposal outcomeSensitiveInterpreter receipt right)).semanticText := by
  simpa [revisionProposal, outcomeSensitiveInterpreter, revise] using different

theorem replace_here (current : Nat -> Relation) (uid : Nat) (next : Relation) :
    replace current uid next uid = next := by simp [replace]

theorem replace_other (current : Nat -> Relation) (uid other : Nat) (next : Relation)
    (different : other ≠ uid) : replace current uid next other = current other := by
  simp [replace, different]

theorem learn_rejects_mismatched_trace (state : GraphState) (receipt : StepReceipt)
    (interpreter : Interpreter) (outcome : Outcome)
    (mismatch : outcome.traceUid ≠ receipt.trace.traceUid) :
    learn interpreter state receipt outcome = none := by
  simp [learn, mismatch]

theorem learn_rejects_stale_snapshot (state : GraphState) (receipt : StepReceipt)
    (interpreter : Interpreter) (outcome : Outcome)
    (stale : state.current receipt.trace.relationUid ≠ receipt.relation) :
    learn interpreter state receipt outcome = none := by
  simp [learn, stale]

theorem learn_rejects_malformed_serialization (state : GraphState) (receipt : StepReceipt)
    (interpreter : Interpreter) (outcome : Outcome)
    (malformed : receipt.serialized ≠ serialize receipt.relation receipt.trace) :
    learn interpreter state receipt outcome = none := by
  simp [learn, malformed]

theorem learn_accepts_exactly_bound_receipt (state : GraphState) (receipt : StepReceipt)
    (interpreter : Interpreter) (outcome : Outcome) (first : outcome.traceUid = receipt.trace.traceUid)
    (current : state.current receipt.trace.relationUid = receipt.relation)
    (serialized : receipt.serialized = serialize receipt.relation receipt.trace) :
    learn interpreter state receipt outcome = some (acceptedState interpreter state receipt outcome) := by
  simp [learn, first, current, serialized]

/-- One LLM Step followed by a trace-bound outcome reaches the explicit successor. -/
theorem llm_step_then_bound_outcome_updates (interpreter : Interpreter) (state : GraphState)
    (trace : Trace) (outcome : Outcome) (bound : outcome.traceUid = trace.traceUid) :
    learn interpreter state (step interpreter state trace) outcome =
      some (acceptedState interpreter state (step interpreter state trace) outcome) := by
  apply learn_accepts_exactly_bound_receipt
  · exact bound
  · rfl
  · rfl

theorem accepted_learn_readout_is_new_relation (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) :
    read (acceptedState interpreter state receipt outcome) receipt.trace.relationUid =
      revise receipt.relation outcome (revisionProposal interpreter receipt outcome) := by
  simp [read, acceptedState, replace]

theorem accepted_learn_retains_prior_history (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) :
    receipt.relation ∈
      (acceptedState interpreter state receipt outcome).history := by
  simp [acceptedState]

theorem accepted_learn_frames_unrelated_relation (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) (other : Nat) (different : other ≠ receipt.trace.relationUid) :
    read (acceptedState interpreter state receipt outcome) other = read state other := by
  simp [read, acceptedState, replace, different]

theorem accepted_learn_preserves_addresses (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) (addressed : Addressed state)
    (current : state.current receipt.trace.relationUid = receipt.relation) :
    Addressed (acceptedState interpreter state receipt outcome) := by
  intro uid
  by_cases selected : uid = receipt.trace.relationUid
  · subst uid
    have receiptAddress : receipt.relation.uid = receipt.trace.relationUid := by
      rw [← current]
      exact addressed receipt.trace.relationUid
    simp [acceptedState, replace, revise, receiptAddress]
  · rw [show (acceptedState interpreter state receipt outcome).current uid = state.current uid by
      simp [acceptedState, replace, selected]]
    exact addressed uid

/-- A composable two-member cell is a joint view, not a scalar aggregate. -/
structure JointCell where
  left : Nat
  right : Nat

def jointRead (state : GraphState) (cell : JointCell) : Relation × Relation :=
  (read state cell.left, read state cell.right)

theorem joint_cell_preserves_unrevised_member (interpreter : Interpreter) (state : GraphState) (receipt : StepReceipt)
    (outcome : Outcome) (cell : JointCell) (leftSelected : cell.left = receipt.trace.relationUid)
    (rightDifferent : cell.right ≠ receipt.trace.relationUid) :
    jointRead (acceptedState interpreter state receipt outcome) cell =
      (revise receipt.relation outcome (revisionProposal interpreter receipt outcome), read state cell.right) := by
  rcases cell with ⟨left, right⟩
  dsimp at leftSelected rightDifferent ⊢
  subst left
  simp [jointRead, read, acceptedState, replace, rightDifferent]

end HSWM.LLMSemanticGraph
