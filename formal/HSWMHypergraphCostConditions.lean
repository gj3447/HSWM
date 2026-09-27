import HSWMHypergraphRepresentation

/-!
# Conditional storage-cost statements for typed n-ary relations

This module makes a narrow part of the minimum-cost hypergraph hypothesis
precise.  A role-bearing n-ary relation may be stored directly as a typed
hyperedge record, or losslessly as one factor identity plus tagged binary
incidences.  The existing representation module proves the latter round trip;
the cost functions below count only *declared abstract storage units*.  They do
not measure bytes, compression, indexing, query planning, inference, learning,
Transformer architecture, ZFC, or physical-world description.

Consequently, the positive comparison theorem is explicitly conditional on a
storage model's per-field costs.  Concrete witnesses show both cost directions,
so representation alone cannot establish universal hypergraph cost dominance.
-/

namespace HSWM.HypergraphCostConditions

open HSWM.HypergraphRepresentation

/-- A direct typed hyperedge stores one relation header and one typed member slot per participant. -/
def directTypedHyperedgeCost (payloadUnits headerUnits typedSlotUnits arity : Nat) : Nat :=
  payloadUnits + headerUnits + arity * typedSlotUnits

/--
A lossless binary factor encoding stores one factor identity and, for every
participant, a role tag plus endpoint.  This is an abstract unit model, not a
claim about an RDF, database, or wire-format implementation.
-/
def taggedIncidenceFactorCost
    (payloadUnits factorIdentityUnits roleTagUnits endpointUnits arity : Nat) : Nat :=
  payloadUnits + factorIdentityUnits + arity * (roleTagUnits + endpointUnits)

/--
The tagged incidence encoding retains payload, factor identity, every role
label, and every endpoint exactly.  It is therefore a lossless competing
representation, not a lossy pair-only clique projection.
-/
theorem tagged_incidence_is_lossless {n : Nat} (arity : Fin n → Nat)
    (family : (factor : Fin n) → NaryRelation Payload Role Vertex (arity factor)) :
    decodeNary (encodeNary arity family) = family :=
  decode_encodeNary arity family

/--
Under this declared additive model, a direct typed hyperedge costs no more than
the lossless tagged-incidence factor representation when its relation-header
and each typed slot are no more expensive than their competing fields.

The inequalities are premises about a chosen storage model; they are not facts
about hypergraphs in general.
-/
theorem direct_typed_no_more_expensive_under_field_costs
    (payloadUnits headerUnits typedSlotUnits factorIdentityUnits roleTagUnits endpointUnits arity : Nat)
    (headerBound : headerUnits ≤ factorIdentityUnits)
    (slotBound : typedSlotUnits ≤ roleTagUnits + endpointUnits) :
    directTypedHyperedgeCost payloadUnits headerUnits typedSlotUnits arity ≤
      taggedIncidenceFactorCost payloadUnits factorIdentityUnits roleTagUnits endpointUnits arity := by
  unfold directTypedHyperedgeCost taggedIncidenceFactorCost
  have slots : arity * typedSlotUnits ≤ arity * (roleTagUnits + endpointUnits) :=
    Nat.mul_le_mul_left arity slotBound
  omega

/--
If a direct header is strictly cheaper while the per-slot cost is no larger,
the direct typed hyperedge is strictly cheaper.  This is a sufficient condition
for an optimum over exactly these two lossless representations and this cost
function; it does not compare every possible encoding.
-/
theorem direct_typed_strictly_cheaper_under_header_advantage
    (payloadUnits headerUnits typedSlotUnits factorIdentityUnits roleTagUnits endpointUnits arity : Nat)
    (headerAdvantage : headerUnits < factorIdentityUnits)
    (slotBound : typedSlotUnits ≤ roleTagUnits + endpointUnits) :
    directTypedHyperedgeCost payloadUnits headerUnits typedSlotUnits arity <
      taggedIncidenceFactorCost payloadUnits factorIdentityUnits roleTagUnits endpointUnits arity := by
  unfold directTypedHyperedgeCost taggedIncidenceFactorCost
  have slots : arity * typedSlotUnits ≤ arity * (roleTagUnits + endpointUnits) :=
    Nat.mul_le_mul_left arity slotBound
  omega

/-- The direct representation is the minimum of this explicitly restricted two-choice candidate set. -/
theorem direct_is_two_choice_minimum
    (payloadUnits headerUnits typedSlotUnits factorIdentityUnits roleTagUnits endpointUnits arity : Nat)
    (headerBound : headerUnits ≤ factorIdentityUnits)
    (slotBound : typedSlotUnits ≤ roleTagUnits + endpointUnits) :
    directTypedHyperedgeCost payloadUnits headerUnits typedSlotUnits arity =
      min (directTypedHyperedgeCost payloadUnits headerUnits typedSlotUnits arity)
        (taggedIncidenceFactorCost payloadUnits factorIdentityUnits roleTagUnits endpointUnits arity) := by
  exact Eq.symm (Nat.min_eq_left (direct_typed_no_more_expensive_under_field_costs
    payloadUnits headerUnits typedSlotUnits factorIdentityUnits roleTagUnits endpointUnits arity
    headerBound slotBound))

/--
When the shared header agrees exactly and one direct typed slot costs exactly a
role tag plus endpoint, the two lossless encodings tie in this storage model.
-/
theorem direct_and_factor_tie_when_fields_match
    (payloadUnits sharedHeaderUnits roleTagUnits endpointUnits arity : Nat) :
    directTypedHyperedgeCost payloadUnits sharedHeaderUnits (roleTagUnits + endpointUnits) arity =
      taggedIncidenceFactorCost payloadUnits sharedHeaderUnits roleTagUnits endpointUnits arity := rfl

/-- A concrete positive-field, nonzero-arity storage model where the direct typed hyperedge is cheaper. -/
theorem direct_cost_direction_witness :
    directTypedHyperedgeCost 1 1 1 3 < taggedIncidenceFactorCost 1 1 1 1 3 := by decide

/--
A concrete countermodel where a factor identity is cheaper than a high-overhead
direct record.  Every counted field has strictly positive cost, so this does
not rely on a free/implicit field convention.
-/
theorem factor_cost_direction_witness :
    taggedIncidenceFactorCost 1 1 1 1 3 < directTypedHyperedgeCost 1 5 3 3 := by decide

/-- Direct typed hyperedges are not no-more-expensive under every nonnegative field-cost model. -/
theorem not_direct_no_more_expensive_for_every_field_cost_model :
    ¬ ∀ (payloadUnits headerUnits typedSlotUnits factorIdentityUnits roleTagUnits endpointUnits arity : Nat),
      directTypedHyperedgeCost payloadUnits headerUnits typedSlotUnits arity ≤
        taggedIncidenceFactorCost payloadUnits factorIdentityUnits roleTagUnits endpointUnits arity := by
  intro claimed
  have wrongDirection := claimed 1 5 3 1 1 1 3
  exact (Nat.not_le_of_lt factor_cost_direction_witness) wrongDirection

/-- Tagged factor incidences are not no-more-expensive under every nonnegative field-cost model. -/
theorem not_factor_no_more_expensive_for_every_field_cost_model :
    ¬ ∀ (payloadUnits headerUnits typedSlotUnits factorIdentityUnits roleTagUnits endpointUnits arity : Nat),
      taggedIncidenceFactorCost payloadUnits factorIdentityUnits roleTagUnits endpointUnits arity ≤
        directTypedHyperedgeCost payloadUnits headerUnits typedSlotUnits arity := by
  intro claimed
  have wrongDirection := claimed 1 1 1 1 1 1 3
  exact (Nat.not_le_of_lt direct_cost_direction_witness) wrongDirection

/--
Both cost directions occur among nonnegative declared field-cost models.  Thus
lossless typed n-ary representation by itself entails neither universal direct
hyperedge optimality nor universal factor-graph optimality.
-/
theorem no_universal_cost_direction_from_representation_alone :
    (directTypedHyperedgeCost 1 1 1 3 < taggedIncidenceFactorCost 1 1 1 1 3) ∧
    (taggedIncidenceFactorCost 1 1 1 1 3 < directTypedHyperedgeCost 1 5 3 3) := by
  exact ⟨direct_cost_direction_witness, factor_cost_direction_witness⟩

end HSWM.HypergraphCostConditions
