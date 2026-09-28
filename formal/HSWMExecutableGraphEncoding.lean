import HSWMSemanticQuotient
import HSWMSemanticSoftware

/-!
# Executable n-ary state across lossless storage representations

The same arbitrary finite family of typed semantic relations can be stored as
hyperedges or tagged binary incidences. This module constructs the encoded
Step/Learn dynamics and proves both directions of the operational translation,
including rejected events and every finite interleaving. It is stronger than
a snapshot round trip, but is still a deterministic software semantics: it
does not assert that a pretrained LLM faithfully realizes any interpreter.

No byte, query, token, or physical cost optimum follows from the equivalence.
Relation arities and addresses are fixed within this representation contract.
-/

namespace HSWM.ExecutableGraphEncoding

open HSWM.HypergraphRepresentation
open HSWM.SemanticQuotient

variable {Payload Tag Endpoint Action Output Evidence : Type} {n : Nat}
variable {arity : Fin n → Nat}

abbrev Family (Payload Tag Endpoint : Type) {n : Nat} (arity : Fin n → Nat) :=
  (factor : Fin n) → NaryRelation Payload Tag Endpoint (arity factor)

/-- Explicit type parameters avoid the fixed `Role`/`Vertex` names in the
legacy encoder's namespace. No complete family is hidden in a payload. -/
def encode (family : Family Payload Tag Endpoint arity) :
    NaryFactorGraph Payload Tag Endpoint arity where
  factorPayload factor := (family factor).payload
  roleLabel factor slot := ((family factor).member slot).1
  endpoint factor slot := ((family factor).member slot).2

def decode (stored : NaryFactorGraph Payload Tag Endpoint arity) :
    Family Payload Tag Endpoint arity := fun factor =>
  { payload := stored.factorPayload factor
    member := fun slot => (stored.roleLabel factor slot, stored.endpoint factor slot) }

theorem decode_encode (family : Family Payload Tag Endpoint arity) :
    decode (encode family) = family := by
  funext factor
  cases h : family factor
  simp [decode, encode, h]

/-- The inverse direction holds for every well-typed incidence value. -/
theorem encode_decode (stored : NaryFactorGraph Payload Tag Endpoint arity) :
    encode (decode stored) = stored := by
  cases stored
  rfl

/-- Translate the supplied software dynamics, rather than merely its snapshot. -/
def encodedDynamics
    (source : Dynamics (Family Payload Tag Endpoint arity) Action Output Evidence) :
    Dynamics (NaryFactorGraph Payload Tag Endpoint arity) Action Output Evidence where
  stepAllowed stored action := source.stepAllowed (decode stored) action
  learnAllowed stored evidence := source.learnAllowed (decode stored) evidence
  step stored action :=
    let result := source.step (decode stored) action
    (result.1, encode result.2)
  learn stored evidence := encode (source.learn (decode stored) evidence)

/-- Storage translation preserves guards, Step and Learn for any source dynamics. -/
theorem encode_refines
    (source : Dynamics (Family Payload Tag Endpoint arity) Action Output Evidence) :
    ExactRefinement source (encodedDynamics source) encode id where
  stepAllowed_iff := by intro state action; simp [encodedDynamics, decode_encode]
  learnAllowed_iff := by intro state evidence; simp [encodedDynamics, decode_encode]
  step_commutes := by intro state action _; simp [mapStep, encodedDynamics, decode_encode]
  learn_commutes := by intro state evidence _; simp [encodedDynamics, decode_encode]

/-- Decoding is also an operational refinement, not just a read-only view. -/
theorem decode_refines
    (source : Dynamics (Family Payload Tag Endpoint arity) Action Output Evidence) :
    ExactRefinement (encodedDynamics source) source decode id where
  stepAllowed_iff := by intro state action; rfl
  learnAllowed_iff := by intro state evidence; rfl
  step_commutes := by intro state action _; simp [mapStep, encodedDynamics, decode_encode]
  learn_commutes := by intro state evidence _; simp [encodedDynamics, decode_encode]

/-- Every finite mixed execution/learning trace commutes with the encoding. -/
theorem all_interleavings_preserved
    (source : Dynamics (Family Payload Tag Endpoint arity) Action Output Evidence)
    (state : Family Payload Tag Endpoint arity) (events : List (Event Action Evidence)) :
    mapRun encode id (run source state events) =
      run (encodedDynamics source) (encode state) events :=
  run_refines (encode_refines source) state events

/-- In particular the observable outputs cannot identify which storage was used. -/
theorem encoded_observations_equal
    (source : Dynamics (Family Payload Tag Endpoint arity) Action Output Evidence)
    (state : Family Payload Tag Endpoint arity) (events : List (Event Action Evidence)) :
    (run (encodedDynamics source) (encode state) events).1 =
      (run source state events).1 := by
  have h := congrArg Prod.fst (all_interleavings_preserved source state events)
  simpa [mapRun] using h.symm

open HSWM.ConstructiveRelationSynthesis
open HSWM.GeneratedLearningBridge

/-- One stored program relation; role and endpoint fields remain distinct. -/
def storeProgram (state : Graph) :
    NaryFactorGraph Expr HSWM.ConstructiveRelationSynthesis.Role (Fin 3) (fun _ : Fin 1 => 3) :=
  encode (fun _ => state)

/-- The local operator executes the program recovered from incidence storage. -/
def executeStored (operator : HSWM.SemanticSoftware.LocalOperator)
    (stored : NaryFactorGraph Expr HSWM.ConstructiveRelationSynthesis.Role (Fin 3) (fun _ : Fin 1 => 3))
    (input : Input) : Bool :=
  HSWM.SemanticSoftware.execute operator (decode stored 0) input

theorem stored_local_execution_equal (operator : HSWM.SemanticSoftware.LocalOperator)
    (state : Graph) (input : Input) :
    executeStored operator (storeProgram state) input =
      HSWM.SemanticSoftware.execute operator state input := by
  simp [executeStored, storeProgram, decode_encode]

/-- The same computed outcome revision changes the next stored-program execution. -/
theorem stored_computed_revision_changes_next_execution :
    executeStored HSWM.SemanticSoftware.referenceOperator (storeProgram baseline)
      (bits true false false) = true ∧
    executeStored HSWM.SemanticSoftware.referenceOperator
      (storeProgram HSWM.SemanticSoftware.computedRevision)
      (bits true false false) = false := by
  simp only [stored_local_execution_equal]
  exact HSWM.SemanticSoftware.stored_revision_changes_next_execution

end HSWM.ExecutableGraphEncoding
