import Std

/-!
# Role-bearing hypergraph representation boundary

This bounded construction separates two claims that are often conflated.

* A binary storage/factor graph **can** faithfully encode an n-ary, role-bearing
  hypergraph when it introduces a relation/factor identity and tagged incidence
  records.  The first round-trip theorem is constructive evidence of that fact.
* A clique projection on the original vertices is a different, lossy map.  The
  concrete counterexample below proves that no decoder receiving only that map
  can recover every ternary edge family in this finite domain.

The final calculation concerns only additive unary-and-pairwise potentials on
three observed Boolean variables.  It does not rule out hidden factor nodes,
composed computations, higher-order features, or a binary representation that
retains relation identities and role tags.  None of these theorems establish
external meaning, learning efficacy, or the full HSWM target.
-/

namespace HSWM.HypergraphRepresentation

/-- Four distinct observed vertices for a finite counterexample. -/
inductive Vertex where
  | a | b | c | d
deriving DecidableEq, Repr

/-- Role tags are data: exchanging them is not an unordered-set permutation. -/
inductive Role where
  | subject | context | evidence
deriving DecidableEq, Repr

/-- A role-bearing ternary relation, including a stable relation identity. -/
structure Relation where
  identity : Nat
  subject : Vertex
  context : Vertex
  evidence : Vertex
deriving DecidableEq, Repr

/--
A well-formed binary factor graph for a family indexed by `Fin n`.  A factor
keeps only its relation identity; all role endpoints live in tagged binary
incidences.  The function type expresses the one endpoint for each factor-role
pair guaranteed by this constructive encoding.
-/
structure FactorGraph (n : Nat) where
  factorIdentity : Fin n → Nat
  incidence : Fin n → Role → Vertex

/-- Encode every ternary relation as one identity-bearing factor and three tagged binary incidences. -/
def encode (family : Fin n → Relation) : FactorGraph n where
  factorIdentity index := (family index).identity
  incidence index role :=
    match role with
    | .subject => (family index).subject
    | .context => (family index).context
    | .evidence => (family index).evidence

/-- Rebuild each ternary relation exclusively from factor identity and tagged incidences. -/
def decode (graph : FactorGraph n) : Fin n → Relation :=
  fun index =>
    { identity := graph.factorIdentity index
      subject := graph.incidence index .subject
      context := graph.incidence index .context
      evidence := graph.incidence index .evidence }

/-- Binary factor storage reconstructs every relation identity and every role endpoint exactly. -/
theorem decode_encode (family : Fin n → Relation) : decode (encode family) = family := by
  funext index
  cases h : family index
  simp [decode, encode, h]

/-- The subject endpoint is an explicit tagged binary incidence. -/
theorem encode_retains_subject (family : Fin n → Relation) (index : Fin n) :
    (encode family).incidence index .subject = (family index).subject := rfl

/-- The context endpoint is an explicit tagged binary incidence. -/
theorem encode_retains_context (family : Fin n → Relation) (index : Fin n) :
    (encode family).incidence index .context = (family index).context := rfl

/-- The evidence endpoint is an explicit tagged binary incidence. -/
theorem encode_retains_evidence (family : Fin n → Relation) (index : Fin n) :
    (encode family).incidence index .evidence = (family index).evidence := rfl

/-- A generic finite-arity relation with an explicitly addressed incidence slot. -/
structure NaryRelation (Payload Role Vertex : Type) (arity : Nat) where
  payload : Payload
  member : Fin arity → Role × Vertex

/--
Generic binary factor storage.  Factor addresses are `Fin n`; incidence-slot
addresses are `Fin (arity factor)`.  It stores no full relation family: only
the factor payload and the two components of every tagged binary incidence.
-/
structure NaryFactorGraph (Payload Role Vertex : Type) {n : Nat}
    (arity : Fin n → Nat) where
  factorPayload : (factor : Fin n) → Payload
  roleLabel : (factor : Fin n) → Fin (arity factor) → Role
  endpoint : (factor : Fin n) → Fin (arity factor) → Vertex

/-- Encode each arbitrary finite-arity relation into tagged binary incidences. -/
def encodeNary (arity : Fin n → Nat)
    (family : (factor : Fin n) → NaryRelation Payload Role Vertex (arity factor)) :
    NaryFactorGraph Payload Role Vertex arity where
  factorPayload factor := (family factor).payload
  roleLabel factor slot := ((family factor).member slot).1
  endpoint factor slot := ((family factor).member slot).2

/-- Re-pair each stored role label and endpoint at its original factor and slot address. -/
def decodeNary {n : Nat} {arity : Fin n → Nat}
    (graph : NaryFactorGraph Payload Role Vertex arity) :
    (factor : Fin n) → NaryRelation Payload Role Vertex (arity factor) :=
  fun factor =>
    { payload := graph.factorPayload factor
      member := fun slot => (graph.roleLabel factor slot, graph.endpoint factor slot) }

/-- Exact representation round-trip for every finite arity and arbitrary role/vertex/payload types. -/
theorem decode_encodeNary {n : Nat} (arity : Fin n → Nat)
    (family : (factor : Fin n) → NaryRelation Payload Role Vertex (arity factor)) :
    decodeNary (encodeNary arity family) = family := by
  funext factor
  cases h : family factor
  simp [decodeNary, encodeNary, h]

/-- The four unordered ternary sets over the fixed four-vertex domain. -/
inductive Triple where
  | abc | abd | acd | bcd
deriving DecidableEq, Repr

/-- The six possible unordered observed-vertex pairs. -/
inductive Pair where
  | ab | ac | ad | bc | bd | cd
deriving DecidableEq, Repr

/-- Clique pairs induced by each ternary edge. -/
def pairs : Triple → List Pair
  | .abc => [.ab, .ac, .bc]
  | .abd => [.ab, .ad, .bd]
  | .acd => [.ac, .ad, .cd]
  | .bcd => [.bc, .bd, .cd]

/-- The pair-only clique projection; it omits edge identity and ternary grouping. -/
def cliqueProjection (family : List Triple) : Pair → Bool :=
  fun pair => family.any fun edge => (pairs edge).contains pair

/-- All four ternary edges. -/
def fourTriples : List Triple := [.abc, .abd, .acd, .bcd]

/-- A different ternary family that already covers every observed pair. -/
def threeTriples : List Triple := [.abc, .abd, .acd]

/-- The two distinct families induce exactly the same pair-only observation. -/
theorem same_clique_projection : cliqueProjection fourTriples = cliqueProjection threeTriples := by
  funext pair
  cases pair <;> decide

/-- The family difference is real: `bcd` is discarded by the common projection. -/
theorem ternary_families_differ : fourTriples ≠ threeTriples := by decide

/-- A relation-sensitive response that asks whether this exact ternary edge is present. -/
def relationResponse (family : List Triple) (query : Triple) : Bool :=
  family.contains query

/-- The common pair graph cannot determine the answer for the discarded `bcd` triple. -/
theorem bcd_response_differs :
    relationResponse fourTriples .bcd ≠ relationResponse threeTriples .bcd := by
  decide

/--
No decoder that sees only pair projection can correctly recover both concrete
families.  This is conditional necessity for retaining a hyperedge/factor
identity (or equally rich information), not a claim that binary storage is
impossible.
-/
theorem no_pair_projection_decoder
    (decoder : (Pair → Bool) → List Triple) :
    ¬ (decoder (cliqueProjection fourTriples) = fourTriples ∧
       decoder (cliqueProjection threeTriples) = threeTriples) := by
  intro recovered
  have equalDecoded : decoder (cliqueProjection fourTriples) =
      decoder (cliqueProjection threeTriples) := by
    rw [same_clique_projection]
  apply ternary_families_differ
  rw [← recovered.1, ← recovered.2]
  exact equalDecoded

/--
Even a decoder asked only for this relation-sensitive response cannot be correct
on both families when its input is restricted to pair-only clique projection.
-/
theorem no_pair_projection_response_decoder
    (decoder : (Pair → Bool) → Triple → Bool) :
    ¬ (decoder (cliqueProjection fourTriples) .bcd = relationResponse fourTriples .bcd ∧
       decoder (cliqueProjection threeTriples) .bcd = relationResponse threeTriples .bcd) := by
  intro answers
  apply bcd_response_differs
  rw [← answers.1, ← answers.2, same_clique_projection]

/-- The alternating third difference on three observed Boolean coordinates. -/
def mixedThird (f : Bool → Bool → Bool → Int) : Int :=
  f true true true - f false true true - f true false true - f true true false +
    f false false true + f false true false + f true false false - f false false false

/-- A model restricted to unary and pairwise potentials over the observed vertices. -/
def unaryPairwise
    (u₁ u₂ u₃ : Bool → Int)
    (p₁₂ p₁₃ p₂₃ : Bool → Bool → Int) : Bool → Bool → Bool → Int :=
  fun x y z => u₁ x + u₂ y + u₃ z + p₁₂ x y + p₁₃ x z + p₂₃ y z

/-- Such a restricted model has no pure third-order mixed difference. -/
theorem mixedThird_unaryPairwise
    (u₁ u₂ u₃ : Bool → Int)
    (p₁₂ p₁₃ p₂₃ : Bool → Bool → Int) :
    mixedThird (unaryPairwise u₁ u₂ u₃ p₁₂ p₁₃ p₂₃) = 0 := by
  simp [mixedThird, unaryPairwise]
  omega

/-- The Boolean cubic has a nonzero ternary interaction. -/
def cubicInteraction : Bool → Bool → Bool → Int :=
  fun x y z => if x && y && z then 1 else 0

/-- A binary connective can compose to calculate this ternary function. -/
def binaryAnd (left right : Bool) : Bool := left && right

/--
This prevents an overclaim: the additive-potential limitation does not prohibit
binary computational composition.  It concerns only the stated additive model.
-/
theorem cubic_has_binary_composition (x y z : Bool) :
    (if binaryAnd (binaryAnd x y) z then 1 else 0) = cubicInteraction x y z := by
  cases x <;> cases y <;> cases z <;> rfl

/-- Its mixed third difference is one. -/
theorem mixedThird_cubicInteraction : mixedThird cubicInteraction = 1 := by
  decide

/--
Therefore the cubic interaction cannot equal any sum of unary and pairwise
potentials on these three original observed vertices.
-/
theorem cubic_not_unaryPairwise
    (u₁ u₂ u₃ : Bool → Int)
    (p₁₂ p₁₃ p₂₃ : Bool → Bool → Int) :
    cubicInteraction ≠ unaryPairwise u₁ u₂ u₃ p₁₂ p₁₃ p₂₃ := by
  intro equalModel
  have equalDifference := congrArg mixedThird equalModel
  rw [mixedThird_cubicInteraction, mixedThird_unaryPairwise] at equalDifference
  omega

end HSWM.HypergraphRepresentation
