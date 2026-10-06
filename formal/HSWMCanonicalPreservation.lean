import Std

/-!
# Canonical v2 preservation as a necessary admission condition

Atom images contain a canonical key and the EXACT normalized native envelope
text, not its digest. Schema text includes all decoded native schema fields.
The adapter sorts native snapshot object keys + JSON.stringify, not canonical-JSON
protocol bytes or RDF serialization. Encoding fidelity,
native schema validation, grants, hashing, I/O and atomic publication are outside
this decoded model. The runtime adapter and file-backed tests bind that boundary.
This is not RDF-only losslessness or a source of canonical Permit authority.
-/
namespace HSWM.CanonicalPreservation

structure AtomImage where
  key : String
  envelopeUtf8 : String
deriving Repr, DecidableEq

structure State where
  schemaVersion : String
  schemaUtf8 : String
  revision : Nat
  bootstrapClosed : Bool
  atoms : List AtomImage
  acceptedTransitionIds : List String
deriving Repr, DecidableEq

structure Command where
  schemaVersion : String
  expectedStateRevision : Nat
  transitionId : String
  writes : List AtomImage
deriving Repr, DecidableEq

def maxSafeInteger : Nat := 9007199254740991

def headerPreserved (before after : State) (c : Command) : Bool :=
  before.revision < maxSafeInteger && after.revision ≤ maxSafeInteger &&
  c.expectedStateRevision ≤ maxSafeInteger && c.expectedStateRevision = before.revision &&
  after.revision = before.revision + 1 && after.bootstrapClosed &&
  before.schemaVersion = after.schemaVersion && before.schemaVersion = c.schemaVersion &&
  before.schemaUtf8 = after.schemaUtf8

def historyPreserved (before after : State) (c : Command) : Bool :=
  decide (c.transitionId ∉ before.acceptedTransitionIds) &&
  decide (after.acceptedTransitionIds = before.acceptedTransitionIds ++ [c.transitionId])

def atomsPreserved (before after : State) (c : Command) : Bool :=
  !c.writes.isEmpty && decide (before.atoms.map AtomImage.key).Nodup &&
  decide (after.atoms.map AtomImage.key).Nodup && decide (c.writes.map AtomImage.key).Nodup &&
  c.writes.all (fun atom => decide (atom.key ∉ before.atoms.map AtomImage.key)) &&
  after.atoms.length = before.atoms.length + c.writes.length &&
  before.atoms.all (fun atom => decide (atom ∈ after.atoms)) &&
  c.writes.all (fun atom => decide (atom ∈ after.atoms))

def preserves (before after : State) (c : Command) : Bool :=
  headerPreserved before after c && historyPreserved before after c && atomsPreserved before after c

theorem headerPreserved_iff : headerPreserved before after c = true ↔
    before.revision < maxSafeInteger ∧ after.revision ≤ maxSafeInteger ∧
    c.expectedStateRevision ≤ maxSafeInteger ∧ c.expectedStateRevision = before.revision ∧
    after.revision = before.revision + 1 ∧ after.bootstrapClosed = true ∧
    before.schemaVersion = after.schemaVersion ∧ before.schemaVersion = c.schemaVersion ∧
    before.schemaUtf8 = after.schemaUtf8 := by
  simp [headerPreserved, Bool.and_eq_true, and_assoc]

theorem historyPreserved_iff : historyPreserved before after c = true ↔
    c.transitionId ∉ before.acceptedTransitionIds ∧
    after.acceptedTransitionIds = before.acceptedTransitionIds ++ [c.transitionId] := by
  simp [historyPreserved, Bool.and_eq_true]

theorem atomsPreserved_iff : atomsPreserved before after c = true ↔
    c.writes ≠ [] ∧ (before.atoms.map AtomImage.key).Nodup ∧
    (after.atoms.map AtomImage.key).Nodup ∧ (c.writes.map AtomImage.key).Nodup ∧
    (∀ atom ∈ c.writes, atom.key ∉ before.atoms.map AtomImage.key) ∧
    after.atoms.length = before.atoms.length + c.writes.length ∧
    (∀ atom ∈ before.atoms, atom ∈ after.atoms) ∧
    (∀ atom ∈ c.writes, atom ∈ after.atoms) := by
  simp [atomsPreserved, Bool.and_eq_true, and_assoc]

theorem preserves_iff : preserves before after c = true ↔
    headerPreserved before after c = true ∧ historyPreserved before after c = true ∧
    atomsPreserved before after c = true := by
  simp [preserves, Bool.and_eq_true, and_assoc]

theorem full_schema_preserved (h : preserves before after c = true) :
    before.schemaUtf8 = after.schemaUtf8 :=
  (headerPreserved_iff.mp (preserves_iff.mp h).1).2.2.2.2.2.2.2.2

theorem revision_increases_once (h : preserves before after c = true) :
    after.revision = before.revision + 1 :=
  (headerPreserved_iff.mp (preserves_iff.mp h).1).2.2.2.2.1

theorem bootstrap_is_closed (h : preserves before after c = true) :
    after.bootstrapClosed = true :=
  (headerPreserved_iff.mp (preserves_iff.mp h).1).2.2.2.2.2.1

theorem history_extends_exactly_once (h : preserves before after c = true) :
    after.acceptedTransitionIds = before.acceptedTransitionIds ++ [c.transitionId] :=
  (historyPreserved_iff.mp (preserves_iff.mp h).2.1).2

theorem accepted_id_is_fresh (h : preserves before after c = true) :
    c.transitionId ∉ before.acceptedTransitionIds :=
  (historyPreserved_iff.mp (preserves_iff.mp h).2.1).1

def RetainsAtoms (before after : State) : Prop :=
  ∀ atom ∈ before.atoms, atom ∈ after.atoms

theorem old_envelopes_retained (h : preserves before after c = true) : RetainsAtoms before after :=
  (atomsPreserved_iff.mp (preserves_iff.mp h).2.2).2.2.2.2.2.2.1

theorem writes_present (h : preserves before after c = true) :
    ∀ atom ∈ c.writes, atom ∈ after.atoms :=
  (atomsPreserved_iff.mp (preserves_iff.mp h).2.2).2.2.2.2.2.2.2

theorem no_existing_key_overwrite (h : preserves before after c = true) :
    ∀ atom ∈ c.writes, atom.key ∉ before.atoms.map AtomImage.key :=
  (atomsPreserved_iff.mp (preserves_iff.mp h).2.2).2.2.2.2.1

theorem atom_count_exact (h : preserves before after c = true) :
    after.atoms.length = before.atoms.length + c.writes.length :=
  (atomsPreserved_iff.mp (preserves_iff.mp h).2.2).2.2.2.2.2.1

/-- Any fixed graph decoder/readout sees the same retained envelope. This says
nothing about fidelity of the supplied decoder or omitted RDF-only fields. -/
theorem retained_projection {View : Type} (project : AtomImage → View)
    (h : preserves before after c = true) (present : atom ∈ before.atoms) :
    ∃ retained ∈ after.atoms, retained = atom ∧ project retained = project atom :=
  ⟨atom, old_envelopes_retained h atom present, rfl, rfl⟩

theorem changed_schema_rejected (different : before.schemaUtf8 ≠ after.schemaUtf8) :
    preserves before after c ≠ true := fun h => different (full_schema_preserved h)

theorem removed_envelope_rejected (old : atom ∈ before.atoms) (missing : atom ∉ after.atoms) :
    preserves before after c ≠ true := fun h => missing (old_envelopes_retained h atom old)

theorem repeated_transition_rejected (old : c.transitionId ∈ before.acceptedTransitionIds) :
    preserves before after c ≠ true := fun h => accepted_id_is_fresh h old

/-- Authorization and structural validity are supplied obligations of the
existing caller. A preservation check cannot establish either one. -/
def approved (authorized structurallyValid : Bool) (before after : State) (c : Command) : Bool :=
  authorized && structurallyValid && preserves before after c

def applyIfApproved (authorized structurallyValid : Bool) (before after : State) (c : Command) : State :=
  if approved authorized structurallyValid before after c then after else before

theorem approval_requires_all : approved authorized valid before after c = true ↔
    authorized = true ∧ valid = true ∧ preserves before after c = true := by
  simp [approved, Bool.and_eq_true, and_assoc]

theorem no_authority_no_change (valid : Bool) (before after : State) (c : Command) :
    applyIfApproved false valid before after c = before := by simp [applyIfApproved, approved]

theorem invalid_structure_no_change (authorized : Bool) (before after : State) (c : Command) :
    applyIfApproved authorized false before after c = before := by simp [applyIfApproved, approved]

theorem failed_preservation_no_change (h : preserves before after c = false) :
    applyIfApproved authorized valid before after c = before := by simp [applyIfApproved, approved, h]

theorem admitted_old_envelopes_retained (authorized valid : Bool) (before after : State) (c : Command) :
    RetainsAtoms before (applyIfApproved authorized valid before after c) := by
  by_cases h : approved authorized valid before after c = true
  · simpa [applyIfApproved, h] using old_envelopes_retained (approval_requires_all.mp h).2.2
  · simp [applyIfApproved, h, RetainsAtoms]

theorem retained_atoms_transitive (first : RetainsAtoms a b) (second : RetainsAtoms b c) :
    RetainsAtoms a c := fun atom member => second atom (first atom member)

structure Proposal where
  authorized : Bool
  structurallyValid : Bool
  after : State
  command : Command

def run : State → List Proposal → State
  | state, [] => state
  | state, proposal :: rest =>
      run (applyIfApproved proposal.authorized proposal.structurallyValid state proposal.after proposal.command) rest

/-- Every finite sequence preserves all previously stored envelopes, including
rejections. The physical journal/CAS implementation is not proved by this law. -/
theorem finite_run_retains_initial_atoms (state : State) (proposals : List Proposal) :
    RetainsAtoms state (run state proposals) := by
  induction proposals generalizing state with
  | nil => intro atom member; exact member
  | cons proposal rest ih =>
    exact retained_atoms_transitive (admitted_old_envelopes_retained _ _ _ _ _) (ih _)

/-- Fields that may grow do so monotonically; fixed fields remain exact. -/
def ExtendsNative (before after : State) : Prop :=
  before.schemaUtf8 = after.schemaUtf8 ∧ before.schemaVersion = after.schemaVersion ∧
  RetainsAtoms before after ∧ before.revision ≤ after.revision ∧
  (before.bootstrapClosed = true → after.bootstrapClosed = true) ∧
  ∃ suffix, after.acceptedTransitionIds = before.acceptedTransitionIds ++ suffix

theorem extends_native_refl (state : State) : ExtendsNative state state := by
  exact ⟨rfl, rfl, fun _ h => h, Nat.le_refl _, id, [], by simp⟩

theorem preserved_extends_native (h : preserves before after c = true) :
    ExtendsNative before after := by
  have header := headerPreserved_iff.mp (preserves_iff.mp h).1
  refine ⟨full_schema_preserved h, header.2.2.2.2.2.2.1, old_envelopes_retained h,
    ?_, fun _ => bootstrap_is_closed h, [c.transitionId], history_extends_exactly_once h⟩
  rw [revision_increases_once h]
  exact Nat.le_succ _

theorem approved_extends_native (authorized valid : Bool) (before after : State) (c : Command) :
    ExtendsNative before (applyIfApproved authorized valid before after c) := by
  by_cases h : approved authorized valid before after c = true
  · simpa [applyIfApproved, h] using preserved_extends_native (approval_requires_all.mp h).2.2
  · simpa [applyIfApproved, h] using extends_native_refl before

theorem extends_native_transitive (first : ExtendsNative a b) (second : ExtendsNative b c) :
    ExtendsNative a c := by
  rcases first with ⟨schema₁, version₁, atoms₁, rev₁, closed₁, suffix₁, history₁⟩
  rcases second with ⟨schema₂, version₂, atoms₂, rev₂, closed₂, suffix₂, history₂⟩
  refine ⟨schema₁.trans schema₂, version₁.trans version₂, retained_atoms_transitive atoms₁ atoms₂,
    Nat.le_trans rev₁ rev₂, fun h => closed₂ (closed₁ h), suffix₁ ++ suffix₂, ?_⟩
  rw [history₂, history₁, List.append_assoc]

theorem finite_run_extends_native (state : State) (proposals : List Proposal) :
    ExtendsNative state (run state proposals) := by
  induction proposals generalizing state with
  | nil => exact extends_native_refl state
  | cons proposal rest ih =>
    exact extends_native_transitive (approved_extends_native _ _ _ _ _) (ih _)

end HSWM.CanonicalPreservation
