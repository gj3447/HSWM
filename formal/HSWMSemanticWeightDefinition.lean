import Std

/-!
# Semantic Weight as a local LLM-realized joint transition disposition

This is a parametric operational definition, not a scalar score, count table,
or a claim that any LLM is correct about an external referent.  `State` may be
the whole evolving semantic hypergraph.  A small `Read` is only the declared
local view supplied to an internal LLM operator; it is not a second canonical
state or a replacement for the hypergraph.

`Law` is deliberately abstract.  It may be a finite PMF, a deterministic
joint message, or another explicitly defined output-law object.  This file
does not assume probability axioms, normalization, calibration, grounding,
causal identification, outcome truth, or full HSWM realization.
-/

namespace HSWM.SemanticWeightDefinition

/-- One typed, labelled member of a finite role-bearing hyperedge incidence. -/
structure RoleIncidence (Role Participant : Type) where
  role : Role
  participant : Participant
deriving DecidableEq, Repr

/-- A finite n-ary incidence plus the permitted context supplied to a relation. -/
structure RoleContext (Role Participant Context : Type) where
  incidences : List (RoleIncidence Role Participant)
  context : Context
deriving DecidableEq, Repr

/-- A deterministic instance of a typed joint recipient transition. -/
structure JointRecipientTransition (Recipient Message : Type) where
  messages : Recipient → Message

/-- A dependent typed joint message; no independence factorization is implied. -/
abbrev JointMessage (Recipient : Type) (Message : Recipient → Type) :=
  (recipient : Recipient) → Message recipient

/--
The Semantic Weight of a relation family: a role/context-conditioned joint
transition disposition.  `Law` is one object for all recipients jointly, so
this definition does not silently impose an independence product over children.
-/
structure SemanticWeight (State Read Role Participant Context Law : Type) where
  localRead : State → RoleContext Role Participant Context → Read
  disposition : Read → RoleContext Role Participant Context → Law

/-- The declared behavior of a Semantic Weight at one complete local input. -/
def behavior {State Read Role Participant Context Law : Type}
    (weight : SemanticWeight State Read Role Participant Context Law)
    (state : State) (input : RoleContext Role Participant Context) : Law :=
  weight.disposition (weight.localRead state input) input

/--
Coordinates that must remain distinct from Semantic Weight itself.  No field
is used by `behavior` unless a separate Step contract explicitly chooses it.
-/
structure NonSemanticCoordinates (State Role Participant Context Score Evidence : Type) where
  readScore : State → RoleContext Role Participant Context → Score
  evidence : Evidence

/-- Equal declared local reads force equal declared joint behavior. -/
theorem equal_local_reads_equal_behavior
    {State Read Role Participant Context Law : Type}
    (weight : SemanticWeight State Read Role Participant Context Law)
    (left right : State) (input : RoleContext Role Participant Context)
    (sameRead : weight.localRead left input = weight.localRead right input) :
    behavior weight left input = behavior weight right input := by
  simp [behavior, sameRead]

/-!
If an *independent target law* differs on a collision of a proposed read map,
no decoder using only that read and input can reproduce both.  The target is
not required to be the current `SemanticWeight`; otherwise equal-read behavior
would make the premises contradictory.  This is the exact loss-of-distinction
condition; it does not forbid scalar encodings which are injective for their
declared task.
-/
theorem no_read_only_decoder_for_lost_distinction
    {State Read Role Participant Context Law : Type}
    (read : State → RoleContext Role Participant Context → Read)
    (target : State → RoleContext Role Participant Context → Law)
    (left right : State) (input : RoleContext Role Participant Context)
    (sameRead : read left input = read right input)
    (differentLaw : target left input ≠ target right input) :
    ¬ ∃ decoder : Read → RoleContext Role Participant Context → Law,
      decoder (read left input) input = target left input ∧
      decoder (read right input) input = target right input := by
  intro existsDecoder
  rcases existsDecoder with ⟨decoder, leftExact, rightExact⟩
  apply differentLaw
  calc
    target left input = decoder (read left input) input := leftExact.symm
    _ = decoder (read right input) input := by rw [sameRead]
    _ = target right input := rightExact

/-- A finite nonvacuous collision witness: a constant local read loses one Boolean target bit. -/
theorem constant_read_cannot_decode_boolean_target :
    ¬ ∃ decoder : Unit → RoleContext Unit Unit Unit → Bool,
      decoder () { incidences := [], context := () } = false ∧
      decoder () { incidences := [], context := () } = true := by
  exact no_read_only_decoder_for_lost_distinction
    (fun _ : Bool => fun _ : RoleContext Unit Unit Unit => ())
    (fun state : Bool => fun _ : RoleContext Unit Unit Unit => state)
    false true { incidences := [], context := () } rfl (by decide)

/--
An LLM realization is an internal neural operator over the declared local
input.  The equality is a representation/factorization contract only: it has
no premise that the LLM's law is true, calibrated, useful, or causal.
-/
structure LlmRealization (State Read Role Participant Context Law LlmInput : Type)
    (weight : SemanticWeight State Read Role Participant Context Law) where
  encode : Read → RoleContext Role Participant Context → LlmInput
  operator : LlmInput → Law
  realizes : ∀ read input, operator (encode read input) = weight.disposition read input

/-- The LLM factorization computes exactly the declared disposition. -/
theorem llm_realization_factors_declared_behavior
    {State Read Role Participant Context Law LlmInput : Type}
    (weight : SemanticWeight State Read Role Participant Context Law)
    (realization : LlmRealization State Read Role Participant Context Law LlmInput weight)
    (state : State) (input : RoleContext Role Participant Context) :
    realization.operator (realization.encode (weight.localRead state input) input) =
      behavior weight state input := by
  simpa [behavior] using realization.realizes (weight.localRead state input) input

/-- Build a Semantic Weight directly from a local LLM encoder and operator. -/
def SemanticWeight.fromLlm {State Read Role Participant Context Law LlmInput : Type}
    (localRead : State → RoleContext Role Participant Context → Read)
    (encode : Read → RoleContext Role Participant Context → LlmInput)
    (operator : LlmInput → Law) :
    SemanticWeight State Read Role Participant Context Law where
  localRead := localRead
  disposition := fun read input => operator (encode read input)

/-- This construction factors by definition; no model-correctness premise is used. -/
theorem from_llm_behavior_is_operator
    {State Read Role Participant Context Law LlmInput : Type}
    (localRead : State → RoleContext Role Participant Context → Read)
    (encode : Read → RoleContext Role Participant Context → LlmInput)
    (operator : LlmInput → Law)
    (state : State) (input : RoleContext Role Participant Context) :
    behavior (SemanticWeight.fromLlm localRead encode operator) state input =
      operator (encode (localRead state input) input) := rfl

/--
Immediate behavioral equivalence alone does not preserve the next update:
the declared Learn map must separately be congruent on the chosen read/view.
This finite witness has identical behavior but different successor states.
-/
def learnCounterexampleWeight : SemanticWeight (Bool × Bool) Bool Unit Unit Unit Bool where
  localRead := fun state _ => state.1
  disposition := fun read _ => read

/-- The next prediction is determined by a hidden coordinate and the outcome. -/
def counterexampleLearn (state : Bool × Bool) (outcome : Bool) : Bool × Bool :=
  (state.2 != outcome, state.2)

theorem same_behavior_does_not_imply_same_learned_successor :
    behavior learnCounterexampleWeight (false, false) { incidences := [], context := () } =
      behavior learnCounterexampleWeight (false, true) { incidences := [], context := () } ∧
    behavior learnCounterexampleWeight (counterexampleLearn (false, false) true)
      { incidences := [], context := () } ≠
    behavior learnCounterexampleWeight (counterexampleLearn (false, true) true)
      { incidences := [], context := () } := by
  decide

/-- Two labelled roles used only for a finite role-order witness. -/
inductive DemoRole where
  | source
  | recipient
deriving DecidableEq, Repr

abbrev DemoInput := RoleContext DemoRole Bool Unit

def demoIncidence (role : DemoRole) (participant : Bool) : RoleIncidence DemoRole Bool :=
  { role, participant }

def demoInput : DemoInput :=
  { incidences := [demoIncidence .source true, demoIncidence .recipient false], context := () }

/-- A presentation reindex changes only list order, retaining every labelled incidence. -/
def presentationReindex (input : DemoInput) : DemoInput :=
  { incidences := input.incidences.reverse, context := input.context }

/-- Role exchange is a semantic transformation, not a presentation reindex. -/
def swapRoles (input : DemoInput) : DemoInput :=
  { incidences := input.incidences.map fun incidence =>
      { role := match incidence.role with | .source => .recipient | .recipient => .source
        participant := incidence.participant }
    context := input.context }

def sourceParticipant (input : DemoInput) : Option Bool :=
  (input.incidences.find? fun incidence => incidence.role = .source).map RoleIncidence.participant

/-- Reordering a presentation leaves this labelled-role behavior unchanged. -/
theorem presentation_reindex_preserves_labelled_role_behavior :
    sourceParticipant (presentationReindex demoInput) = sourceParticipant demoInput := by
  decide

/-- Exchanging source and recipient changes the declared directed-role behavior. -/
theorem role_swap_is_not_presentation_reindex :
    sourceParticipant (swapRoles demoInput) ≠ sourceParticipant demoInput := by
  decide

end HSWM.SemanticWeightDefinition
