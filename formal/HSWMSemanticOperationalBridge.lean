import HSWMSemanticLifecycleRefinement
import HSWMSemanticQuotient

/-!
# Decoded semantic lifecycle as Step/Learn, and finite-round composition

Provider traces are supplied action data, not outputs predicted by this model.
The state is the selected relation view, not the full store or its journal.
`selected` is an observed branch decision, not a theorem of statistical utility
or a replacement for runtime admission. Adapter byte/JSON checks remain external.
-/

namespace HSWM.SemanticOperationalBridge

open HSWM.SemanticLifecycleRefinement HSWM.SemanticQuotient

structure ReadAction where
  frame : Frame
  trace : Trace

structure LearnEvidence where
  frame : Frame
  trace : Trace
  outcome : Outcome
  revision : Revision
  selected : Bool

def readAllowed (state : StateView) (action : ReadAction) : Bool :=
  frameDescribes state action.frame && traceBindsFrame action.trace action.frame

def learnBound (state : StateView) (evidence : LearnEvidence) : Bool :=
  readAllowed state ⟨evidence.frame, evidence.trace⟩ &&
  outcomeBindsTrace evidence.outcome evidence.trace &&
  evidence.revision.exceptionRefs = state.relation.semantic.exceptionRefs &&
  evidence.revision.traceSha256 = evidence.trace.traceSha256 &&
  evidence.revision.outcomeSha256 = evidence.outcome.outcomeSha256 &&
  evidence.revision.backendConfigurationSha256 = evidence.trace.backendConfigurationSha256

def semanticDynamics : Dynamics StateView ReadAction Trace LearnEvidence where
  stepAllowed := readAllowed
  learnAllowed := fun state evidence => evidence.selected && learnBound state evidence
  step := fun state action => (action.trace, state)
  learn := fun state evidence => semanticSuccessor state evidence.revision

def trainingAction (wire : PostRunWire) : ReadAction := ⟨wire.frame, wire.trace⟩
def nextAction (wire : PostRunWire) : ReadAction := ⟨wire.nextFrame, wire.nextTrace⟩
def learningEvidence (wire : PostRunWire) : LearnEvidence :=
  ⟨wire.frame, wire.trace, wire.outcome, wire.revision, wire.selectedCandidate⟩
def roundEvents (wire : PostRunWire) : List (Event ReadAction LearnEvidence) :=
  [.step (trainingAction wire), .learn (learningEvidence wire), .step (nextAction wire)]

theorem accepted_training_read (h : postRunAccepted wire = true) :
    readAllowed wire.before (trainingAction wire) = true := by
  rcases postRunAccepted_iff.mp h with ⟨_, frame, trace, _⟩
  simp [readAllowed, trainingAction, frame, trace]

theorem accepted_next_read (h : postRunAccepted wire = true) :
    readAllowed (selectedState wire) (nextAction wire) = true := by
  rcases postRunAccepted_iff.mp h with ⟨_, _, _, _, _, _, _, _, _, frame, trace, _⟩
  simp [readAllowed, nextAction, frame, trace]

theorem accepted_learning_bound (h : postRunAccepted wire = true) :
    learnBound wire.before (learningEvidence wire) = true := by
  rcases postRunAccepted_iff.mp h with ⟨_, _, _, outcome, binding, constructed, _⟩
  have exceptions := accepted_preserves_ordered_exceptions h
  have read := accepted_training_read h
  simp only [revisionConstructsAfter, Bool.and_eq_true, decide_eq_true_eq] at constructed
  rcases constructed with ⟨⟨⟨⟨⟨⟨⟨⟨⟨_, _⟩, _⟩, ex⟩, _⟩, _⟩, _⟩, tr⟩, out⟩, backend⟩
  have revExceptions := ex.symm.trans exceptions
  simpa [learnBound, learningEvidence, trainingAction, outcome, revExceptions, tr, out, backend]
    using read

/-- A rejected candidate stays observably rejected, although its proposal was valid. -/
theorem accepted_learning_guard (h : postRunAccepted wire = true) :
    semanticDynamics.learnAllowed wire.before (learningEvidence wire) = wire.selectedCandidate := by
  change (wire.selectedCandidate && learnBound wire.before (learningEvidence wire)) = wire.selectedCandidate
  rw [accepted_learning_bound h]
  simp

theorem accepted_learning_advance (h : postRunAccepted wire = true) :
    advance semanticDynamics wire.before (.learn (learningEvidence wire)) =
      (none, selectedState wire) := by
  have guard := accepted_learning_guard h
  have successor := accepted_after_eq_semanticSuccessor h
  simp only [advance, guard]
  cases selected : wire.selectedCandidate <;>
    simp [selected, selectedState, semanticDynamics, learningEvidence, successor]

/-- The actual projected read/learn/read wire is an instance of the common Dynamics. -/
theorem accepted_round_replays (h : postRunAccepted wire = true) :
    run semanticDynamics wire.before (roundEvents wire) =
      ([some wire.trace, none, some wire.nextTrace], selectedState wire) := by
  have first := accepted_training_read h
  have next := accepted_next_read h
  have learned := accepted_learning_advance h
  simp only [roundEvents, run]
  have stepFirst : advance semanticDynamics wire.before (.step (trainingAction wire)) =
      (some wire.trace, wire.before) := by
    simp only [advance, semanticDynamics]
    rw [first]
    rfl
  have stepNext : advance semanticDynamics (selectedState wire) (.step (nextAction wire)) =
      (some wire.nextTrace, selectedState wire) := by
    simp only [advance, semanticDynamics]
    rw [next]
    rfl
  rw [stepFirst]
  dsimp only
  rw [learned]
  dsimp only
  rw [stepNext]

def chainAcceptedFrom : StateView → List PostRunWire → Bool
  | _, [] => true
  | initial, wire :: rest =>
    (wire.before = initial) && postRunAccepted wire &&
      chainAcceptedFrom (selectedState wire) rest

def chainContract : String := "hswm-semantic-lifecycle-chain/v1"
def chainAccepted (wires : List PostRunWire) : Bool :=
  match wires with
  | [] => false
  | wire :: _ => chainAcceptedFrom wire.before wires

def finalState : StateView → List PostRunWire → StateView
  | initial, [] => initial
  | _, wire :: rest => finalState (selectedState wire) rest

def chainEvents (wires : List PostRunWire) := wires.flatMap roundEvents
def chainOutputs (wires : List PostRunWire) : List (Option Trace) :=
  wires.flatMap (fun w => [some w.trace, none, some w.nextTrace])

theorem run_append (state : StateView) (left right : List (Event ReadAction LearnEvidence)) :
    run semanticDynamics state (left ++ right) =
      let first := run semanticDynamics state left
      let second := run semanticDynamics first.2 right
      (first.1 ++ second.1, second.2) := by
  induction left generalizing state with
  | nil => simp [run]
  | cons event rest ih => simp [run, ih]

/-- Every finite accepted chain preserves all Step outputs and the selected final state. -/
theorem accepted_chain_replays (h : chainAcceptedFrom initial wires = true) :
    run semanticDynamics initial (chainEvents wires) =
      (chainOutputs wires, finalState initial wires) := by
  induction wires generalizing initial with
  | nil => rfl
  | cons wire rest ih =>
    simp only [chainAcceptedFrom, Bool.and_eq_true, decide_eq_true_eq] at h
    rcases h with ⟨⟨same, accepted⟩, tail⟩
    subst initial
    simp only [chainEvents, List.flatMap_cons, run_append]
    rw [accepted_round_replays accepted]
    dsimp only
    rw [show run semanticDynamics (selectedState wire) (rest.flatMap roundEvents) =
      (chainOutputs rest, finalState (selectedState wire) rest) from ih tail]
    rfl

theorem accepted_selected_invariants (h : postRunAccepted wire = true) :
    (selectedState wire).relation.owner = wire.before.relation.owner ∧
    (selectedState wire).relation.roles = wire.before.relation.roles ∧
    (selectedState wire).relation.semantic.exceptionRefs = wire.before.relation.semantic.exceptionRefs := by
  have successor := accepted_after_eq_semanticSuccessor h
  have roles := accepted_preserves_ordered_roles h
  have exceptions := accepted_preserves_ordered_exceptions h
  cases selected : wire.selectedCandidate <;>
    simp [selectedState, selected, successor, semanticSuccessor] at *
  exact exceptions

/-- Relation owner, ordered roles and ordered exception references survive every selected round. -/
theorem accepted_chain_preserves_invariants (h : chainAcceptedFrom initial wires = true) :
    (finalState initial wires).relation.owner = initial.relation.owner ∧
    (finalState initial wires).relation.roles = initial.relation.roles ∧
    (finalState initial wires).relation.semantic.exceptionRefs = initial.relation.semantic.exceptionRefs := by
  induction wires generalizing initial with
  | nil => exact ⟨rfl, rfl, rfl⟩
  | cons wire rest ih =>
    simp only [chainAcceptedFrom, Bool.and_eq_true, decide_eq_true_eq] at h
    rcases h with ⟨⟨same, accepted⟩, tail⟩
    subst initial
    have one := accepted_selected_invariants accepted
    have more := ih tail
    exact ⟨more.1.trans one.1, more.2.1.trans one.2.1, more.2.2.trans one.2.2⟩

theorem stale_round_rejected (initial : StateView) (wire : PostRunWire) (rest : List PostRunWire)
    (stale : wire.before ≠ initial) : chainAcceptedFrom initial (wire :: rest) = false := by
  simp [chainAcceptedFrom, stale]

theorem empty_chain_not_evidence : chainAccepted [] = false := rfl

def selectedCount (wires : List PostRunWire) : Nat :=
  (wires.map (fun wire => wire.selectedCandidate.toNat)).sum

theorem accepted_selected_revision (h : postRunAccepted wire = true) :
    (selectedState wire).stateRevision = wire.before.stateRevision + wire.selectedCandidate.toNat := by
  have successor := accepted_after_eq_semanticSuccessor h
  cases selected : wire.selectedCandidate <;>
    simp [selectedState, selected, successor, semanticSuccessor]

/-- Rejected proposals cannot silently count as committed selected revisions. -/
theorem accepted_chain_revision_count (h : chainAcceptedFrom initial wires = true) :
    (finalState initial wires).stateRevision = initial.stateRevision + selectedCount wires := by
  induction wires generalizing initial with
  | nil => simp [finalState, selectedCount]
  | cons wire rest ih =>
    simp only [chainAcceptedFrom, Bool.and_eq_true, decide_eq_true_eq] at h
    rcases h with ⟨⟨same, accepted⟩, tail⟩
    subst initial
    simpa [finalState, selectedCount, accepted_selected_revision accepted, Nat.add_assoc] using ih tail

end HSWM.SemanticOperationalBridge
