import HSWMLLMSemanticGraph
import HSWMSemanticSoftware

/-!
# One finite integrated canonical graph / local software closed loop

This is a constructed, finite HSWM-shaped witness.  `GraphState` is the only
persistent machine state.  Its stored semantic text is decoded afresh on every
prediction into the executable typed relation.  A trace-bound outcome package
computes a grammar proposal and noisy-cost choice; the true world is used only
by the later score theorem, never by revision.  This is not a proof of a real
LLM, open-world learning, CHU, or full HSWM.
-/

namespace HSWM.IntegratedClosedLoop

open HSWM.LLMSemanticGraph
open HSWM.ConstructiveRelationSynthesis
open HSWM.GeneratedLearningBridge
open HSWM.SemanticSoftware

def baselineCode : String := "hswm-program/input-0"
def conjunctionCode : String := "hswm-program/and-0-1-2"
def refusalCode : String := "hswm-program/refused"

/-- Explicit finite codec: unknown code has a declared baseline fallback; no safety property is proved here. -/
def decodeProgram (text : String) : Graph :=
  if text = conjunctionCode then candidate else baseline

def encodeExpr (program : Expr) : String :=
  if program = conjunction then conjunctionCode else baselineCode

def encodeProgram (program : Graph) : String := encodeExpr program.payload

theorem encode_candidate : encodeProgram candidate = conjunctionCode := by
  rw [computed_candidate_is_conjunction]
  simp [encodeProgram, encodeExpr, graph]

theorem encode_baseline : encodeProgram baseline = baselineCode := by
  unfold encodeProgram encodeExpr baseline
  rw [if_neg (by decide)]

theorem decode_encode_candidate : decodeProgram (encodeProgram candidate) = candidate := by
  rw [encode_candidate]
  simp [decodeProgram]

theorem decode_encode_baseline : decodeProgram (encodeProgram baseline) = baseline := by
  rw [encode_baseline]
  simp [decodeProgram, baselineCode, conjunctionCode]

theorem unknown_code_falls_back (text : String) (unknown : text ≠ conjunctionCode) :
    decodeProgram text = baseline := by simp [decodeProgram, unknown]

/-- The eight explicit local input tokens accepted by the reference execute branch. -/
def decodeInputToken : String → Input
  | "000" => bits false false false
  | "001" => bits false false true
  | "010" => bits false true false
  | "011" => bits false true true
  | "100" => bits true false false
  | "101" => bits true false true
  | "110" => bits true true false
  | "111" => bits true true true
  | _ => bits false false false

def bitToken (value : Bool) : String := if value then "1" else "0"

def encodeInputToken (input : Input) : String :=
  bitToken (input 0) ++ bitToken (input 1) ++ bitToken (input 2)

theorem decode_encode_input_token (input : Input) : decodeInputToken (encodeInputToken input) = input := by
  funext slot
  have cases : slot = 0 ∨ slot = 1 ∨ slot = 2 := by omega
  rcases cases with first | second | third <;> subst slot
  all_goals cases firstBit : input 0 <;> cases secondBit : input 1 <;> cases thirdBit : input 2 <;>
    simp [encodeInputToken, bitToken, decodeInputToken, bits, firstBit, secondBit, thirdBit]

def decodeBitToken : String → Option Bool
  | "1" => some true
  | "0" => some false
  | _ => none

/-- All information supplied to a revision resolver; no `world` field exists here. -/
structure EvidencePackage where
  outcome : Outcome
  synthesis : List Example
  assessment : List (HSWM.NoisyFeedback.Observation Input)
  allowance : Nat
  debit : Nat

/-- Candidate generation and acceptance are computed from the package, not inserted as a target constant. -/
def selectedFromEvidence (current : Graph) (evidence : EvidencePackage) : Graph :=
  HSWM.NoisyFeedback.choose forward current
    (propose current evidence.synthesis) evidence.assessment evidence.allowance evidence.debit

/-- Revision may consume a package only when every outcome field matches its bound outcome. -/
def resolveEvidence (current : Graph) (evidence : EvidencePackage) (outcome : Outcome) : Option Graph :=
  if outcome = evidence.outcome then some (selectedFromEvidence current evidence) else none

/-- A single frozen interpreter: execute consumes both serialized program text and token; revise consumes bound evidence. -/
def integratedInterpreter (evidence : EvidencePackage) : Interpreter
  | .execute serialized =>
      { semanticText := bitToken (SemanticSoftware.execute referenceOperator
          (decodeProgram serialized.semanticText) (decodeInputToken serialized.inputToken))
        disposition := "executed-local-token" }
  | .revise serialized _ outcome =>
      match resolveEvidence (decodeProgram serialized.semanticText) evidence outcome with
      | some program => { semanticText := encodeProgram program, disposition := "outcome-bound-revision" }
      | none => { semanticText := refusalCode, disposition := "outcome-not-bound" }

def targetUid : Nat := 7

def canonicalRelation (uid : Nat) : Relation :=
  { uid := uid, revision := 0, owner := 11, source := 21, recipient := 22, context := 23
    semanticText := if uid = targetUid then baselineCode else refusalCode
    disposition := "initial", evidenceRefs := [], extraRoles := [("exception", 24)] }

def initialState : GraphState := { current := canonicalRelation, history := [] }

def trace : Trace := { traceUid := 31, relationUid := targetUid, inputToken := "110" }

def boundOutcome : Outcome := { traceUid := 31, evidenceRef := 41, observedToken := "accepted-observation" }

/-- Training inputs overlap synthesis and the old full census; the complementary evaluation is in `HSWMClosedLoopEvaluation`. -/
def trainingPopulation : List (HSWM.NoisyFeedback.Observation Input) :=
  [⟨bits true true true, false, 1⟩,
   ⟨bits true true true, true, 1⟩,
   ⟨bits true true false, false, 2⟩,
   ⟨bits true false true, false, 2⟩,
   ⟨bits false true true, false, 2⟩]

def concreteEvidence : EvidencePackage :=
  { outcome := boundOutcome, synthesis := separatingExamples, assessment := trainingPopulation
    allowance := 1, debit := incrementalDebit }

theorem concrete_evidence_computes_candidate : selectedFromEvidence baseline concreteEvidence = candidate := by
  unfold selectedFromEvidence concreteEvidence trainingPopulation HSWM.NoisyFeedback.choose
  change (if 3 + 2 * 1 + 1 < 7 then candidate else baseline) = candidate
  simp

theorem concrete_resolver_is_bound : resolveEvidence baseline concreteEvidence boundOutcome = some candidate := by
  have sameOutcome : boundOutcome = concreteEvidence.outcome := rfl
  simp [resolveEvidence, sameOutcome, concrete_evidence_computes_candidate]

def mismatchedOutcome : Outcome := { traceUid := 31, evidenceRef := 42, observedToken := "accepted-observation" }

def mismatchedTraceOutcome : Outcome := { traceUid := 32, evidenceRef := 41, observedToken := "accepted-observation" }

theorem mismatched_evidence_is_refused : resolveEvidence baseline concreteEvidence mismatchedOutcome = none := by
  simp [resolveEvidence, concreteEvidence, mismatchedOutcome, boundOutcome]

theorem mismatched_trace_evidence_is_refused : resolveEvidence baseline concreteEvidence mismatchedTraceOutcome = none := by
  simp [resolveEvidence, concreteEvidence, mismatchedTraceOutcome, boundOutcome]

/-- The state itself supplies the executable graph through its actual `step` serialization; no executable graph is persisted separately. -/
def predictionTrace (input : Input) : Trace :=
  { traceUid := 51, relationUid := targetUid, inputToken := encodeInputToken input }

def canonicalPredict (state : GraphState) (input : Input) : Bool :=
  match decodeBitToken (step (integratedInterpreter concreteEvidence) state (predictionTrace input)).proposal.semanticText with
  | some prediction => prediction
  | none => false

theorem canonical_predict_uses_actual_step (state : GraphState) (input : Input) :
    canonicalPredict state input = SemanticSoftware.execute referenceOperator
      (decodeProgram (read state targetUid).semanticText) input := by
  change (match decodeBitToken (bitToken (SemanticSoftware.execute referenceOperator
    (decodeProgram (state.current targetUid).semanticText) (decodeInputToken (encodeInputToken input)))) with
    | some prediction => prediction
    | none => false) = SemanticSoftware.execute referenceOperator
      (decodeProgram (state.current targetUid).semanticText) input
  rw [decode_encode_input_token]
  cases SemanticSoftware.execute referenceOperator
      (decodeProgram ((state.current targetUid).semanticText)) input <;>
    simp [bitToken, decodeBitToken]

def initialPrediction : Input → Bool := canonicalPredict initialState

def receipt : StepReceipt := step (integratedInterpreter concreteEvidence) initialState trace

theorem receipt_relation_decodes_baseline : decodeProgram receipt.relation.semanticText = baseline := by
  change decodeProgram baselineCode = baseline
  simp [decodeProgram, baselineCode, conjunctionCode]

/-- Failed evidence binding retains the exact canonical state; successful binding delegates commit to `LLMSemanticGraph.learn`. -/
def integratedLearn (state : GraphState) (receipt : StepReceipt) (outcome : Outcome) : Option GraphState :=
  match resolveEvidence (decodeProgram receipt.relation.semanticText) concreteEvidence outcome with
  | none => some state
  | some _ => learn (integratedInterpreter concreteEvidence) state receipt outcome

theorem initial_canonical_state_decodes_baseline :
    decodeProgram (read initialState targetUid).semanticText = baseline := by
  change decodeProgram baselineCode = baseline
  simp [decodeProgram, baselineCode, conjunctionCode]

theorem interpreter_execute_uses_serialized_program_and_token :
    receipt.proposal.semanticText = "1" := by rfl

/-- Execute has no future-outcome package branch: changing future evidence cannot alter this pre-outcome step. -/
theorem pre_outcome_step_does_not_read_future_evidence
    (left right : EvidencePackage) (state : GraphState) (currentTrace : Trace) :
    step (integratedInterpreter left) state currentTrace =
      step (integratedInterpreter right) state currentTrace := rfl

theorem receipt_serialization_is_baseline : receipt.serialized.semanticText = baselineCode := by rfl

theorem bound_outcome_commits_through_llm_learn :
    integratedLearn initialState receipt boundOutcome =
      some (acceptedState (integratedInterpreter concreteEvidence) initialState receipt boundOutcome) := by
  unfold integratedLearn
  rw [receipt_relation_decodes_baseline, concrete_resolver_is_bound]
  exact llm_step_then_bound_outcome_updates (integratedInterpreter concreteEvidence)
    initialState trace boundOutcome rfl

theorem mismatched_outcome_retains_canonical_state :
    integratedLearn initialState receipt mismatchedOutcome = some initialState := by
  rw [integratedLearn, receipt_relation_decodes_baseline, mismatched_evidence_is_refused]

theorem mismatched_trace_retains_canonical_state :
    integratedLearn initialState receipt mismatchedTraceOutcome = some initialState := by
  rw [integratedLearn, receipt_relation_decodes_baseline, mismatched_trace_evidence_is_refused]

def successor : GraphState := acceptedState (integratedInterpreter concreteEvidence) initialState receipt boundOutcome

def revisedPrediction : Input → Bool := canonicalPredict successor

theorem successor_canonical_text_is_computed_candidate :
    (read successor targetUid).semanticText = conjunctionCode := by
  change (read successor receipt.trace.relationUid).semanticText = conjunctionCode
  unfold successor
  rw [accepted_learn_readout_is_new_relation]
  change (LLMSemanticGraph.revise receipt.relation boundOutcome
    (revisionProposal (integratedInterpreter concreteEvidence) receipt boundOutcome)).semanticText = conjunctionCode
  rw [show boundOutcome = concreteEvidence.outcome by rfl]
  simp only [revisionProposal, integratedInterpreter, resolveEvidence]
  rw [receipt_serialization_is_baseline]
  change (LLMSemanticGraph.revise receipt.relation concreteEvidence.outcome
    (match resolveEvidence (decodeProgram baselineCode) concreteEvidence concreteEvidence.outcome with
    | some program => { semanticText := encodeProgram program, disposition := "outcome-bound-revision" }
    | none => { semanticText := refusalCode, disposition := "outcome-not-bound" })).semanticText = conjunctionCode
  rw [show decodeProgram baselineCode = baseline by simp [decodeProgram, baselineCode, conjunctionCode]]
  have resolved : resolveEvidence baseline concreteEvidence concreteEvidence.outcome = some candidate := by
    simpa [concreteEvidence] using concrete_resolver_is_bound
  rw [resolved]
  exact encode_candidate

theorem successor_decodes_same_computed_revision :
    decodeProgram (read successor targetUid).semanticText = computedRevision := by
  rw [successor_canonical_text_is_computed_candidate]
  change decodeProgram conjunctionCode = computedRevision
  rw [computed_revision_selects_generated_program]
  simp [decodeProgram]

theorem initialPrediction_eq_forward_baseline : initialPrediction = forward baseline := by
  funext input
  change canonicalPredict initialState input = forward baseline input
  rw [canonical_predict_uses_actual_step, initial_canonical_state_decodes_baseline]
  exact reference_executes_semantic_weight (.input 0) input

theorem revisedPrediction_eq_forward_candidate : revisedPrediction = forward candidate := by
  funext input
  change canonicalPredict successor input = forward candidate input
  rw [canonical_predict_uses_actual_step, successor_decodes_same_computed_revision]
  rw [computed_revision_selects_generated_program]
  exact reference_candidate_execution input

theorem successor_preserves_owner_roles_and_history :
    (read successor targetUid).owner = (read initialState targetUid).owner ∧
    (read successor targetUid).source = (read initialState targetUid).source ∧
    (read successor targetUid).recipient = (read initialState targetUid).recipient ∧
    (read successor targetUid).context = (read initialState targetUid).context ∧
    (read successor targetUid).extraRoles = (read initialState targetUid).extraRoles ∧
    (read initialState targetUid) ∈ successor.history := by
  change (read successor receipt.trace.relationUid).owner = (read initialState targetUid).owner ∧
    (read successor receipt.trace.relationUid).source = (read initialState targetUid).source ∧
    (read successor receipt.trace.relationUid).recipient = (read initialState targetUid).recipient ∧
    (read successor receipt.trace.relationUid).context = (read initialState targetUid).context ∧
    (read successor receipt.trace.relationUid).extraRoles = (read initialState targetUid).extraRoles ∧
    (read initialState targetUid) ∈ successor.history
  unfold successor
  rw [accepted_learn_readout_is_new_relation]
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  constructor
  · rfl
  exact accepted_learn_retains_prior_history _ _ _ _

theorem successor_frames_unrelated_relation (other : Nat) (different : other ≠ targetUid) :
    read successor other = read initialState other := by
  unfold successor
  apply accepted_learn_frames_unrelated_relation
  change other ≠ targetUid
  exact different

theorem bound_revision_changes_next_execution :
    canonicalPredict initialState (bits true false false) = true ∧
    canonicalPredict successor (bits true false false) = false := by
  rw [show canonicalPredict initialState = SemanticSoftware.execute referenceOperator baseline by
    funext input; rw [canonical_predict_uses_actual_step, initial_canonical_state_decodes_baseline]]
  rw [show canonicalPredict successor = SemanticSoftware.execute referenceOperator computedRevision by
    funext input; rw [canonical_predict_uses_actual_step, successor_decodes_same_computed_revision]]
  exact stored_revision_changes_next_execution

theorem same_canonical_runtime_has_strict_net_gain :
    HSWM.NoisyFeedback.trueScore (canonicalPredict initialState) world assessmentPopulation + incrementalDebit <
      HSWM.NoisyFeedback.trueScore (canonicalPredict successor) world assessmentPopulation := by
  rw [show canonicalPredict initialState = SemanticSoftware.execute referenceOperator baseline by
    funext input; rw [canonical_predict_uses_actual_step, initial_canonical_state_decodes_baseline]]
  rw [show canonicalPredict successor = SemanticSoftware.execute referenceOperator computedRevision by
    funext input; rw [canonical_predict_uses_actual_step, successor_decodes_same_computed_revision]]
  exact outcome_revised_local_program_has_strict_gain

theorem exact_constructed_gain_is_ten_to_sixteen :
    HSWM.NoisyFeedback.trueScore (canonicalPredict initialState) world assessmentPopulation = 10 ∧
    HSWM.NoisyFeedback.trueScore (canonicalPredict successor) world assessmentPopulation = 16 := by
  rw [show canonicalPredict initialState = SemanticSoftware.execute referenceOperator baseline by
    funext input; rw [canonical_predict_uses_actual_step, initial_canonical_state_decodes_baseline]]
  rw [show canonicalPredict successor = SemanticSoftware.execute referenceOperator computedRevision by
    funext input; rw [canonical_predict_uses_actual_step, successor_decodes_same_computed_revision]]
  exact reference_software_scores

theorem successor_preserves_extra_roles_and_binds_version_evidence :
    (read successor targetUid).extraRoles = (read initialState targetUid).extraRoles ∧
    (read successor targetUid).uid = targetUid ∧
    (read successor targetUid).revision = (read initialState targetUid).revision + 1 ∧
    (read successor targetUid).evidenceRefs =
      boundOutcome.evidenceRef :: (read initialState targetUid).evidenceRefs := by
  exact ⟨rfl, rfl, rfl, rfl⟩

theorem successor_preserves_address_identity : Addressed successor := by
  apply accepted_learn_preserves_addresses
  · intro uid
    rfl
  · rfl

theorem replaying_old_receipt_is_rejected :
    integratedLearn successor receipt boundOutcome = none := by
  unfold integratedLearn
  rw [receipt_relation_decodes_baseline, concrete_resolver_is_bound]
  apply learn_rejects_stale_snapshot
  intro same
  have revisions := congrArg Relation.revision same
  change 1 = 0 at revisions
  contradiction

def wrongTraceReceipt : StepReceipt :=
  { receipt with trace := { trace with traceUid := 32 } }

theorem wrong_trace_receipt_is_rejected :
    integratedLearn initialState wrongTraceReceipt boundOutcome = none := by
  unfold integratedLearn
  change (match resolveEvidence (decodeProgram receipt.relation.semanticText)
    concreteEvidence boundOutcome with
      | none => some initialState
      | some _ => learn (integratedInterpreter concreteEvidence) initialState wrongTraceReceipt boundOutcome) = none
  rw [receipt_relation_decodes_baseline, concrete_resolver_is_bound]
  apply learn_rejects_mismatched_trace
  decide

def malformedReceipt : StepReceipt :=
  { receipt with serialized := { receipt.serialized with owner := 99 } }

theorem malformed_serialization_is_rejected :
    integratedLearn initialState malformedReceipt boundOutcome = none := by
  unfold integratedLearn
  change (match resolveEvidence (decodeProgram receipt.relation.semanticText)
    concreteEvidence boundOutcome with
      | none => some initialState
      | some _ => learn (integratedInterpreter concreteEvidence) initialState malformedReceipt boundOutcome) = none
  rw [receipt_relation_decodes_baseline, concrete_resolver_is_bound]
  apply learn_rejects_malformed_serialization
  intro same
  have owners := congrArg SerializedContext.owner same
  change 99 = 11 at owners
  contradiction

end HSWM.IntegratedClosedLoop
