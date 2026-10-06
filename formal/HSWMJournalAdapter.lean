import HSWMCanonicalPreservation
import HSWMDurablePreservation

/-!
Concrete decoded adapter for the canonical-v2 journal boundary.  It deliberately
models fields copied by the runtime; parsing, hashing, schema validation and
Permit authentication remain obligations of the surrounding decoder.
-/
namespace HSWM.JournalAdapter

open CanonicalPreservation DurablePreservation

structure Key where
  schemaVersion : String
  lineageId : String
  atomUid : String
  revisionId : Nat
deriving Repr, DecidableEq

def keyId (k : Key) : String :=
  k.schemaVersion ++ "|" ++ k.lineageId ++ "|" ++ k.atomUid ++ "|" ++ toString k.revisionId

def keyLe (a b : Key) : Bool :=
  if a.schemaVersion < b.schemaVersion then true else if b.schemaVersion < a.schemaVersion then false else
  if a.lineageId < b.lineageId then true else if b.lineageId < a.lineageId then false else
  if a.atomUid < b.atomUid then true else if b.atomUid < a.atomUid then false else
  a.revisionId ≤ b.revisionId

structure Atom where
  key : Key
  envelopeUtf8 : String
  content : Descriptor
deriving Repr, DecidableEq

structure State where
  schemaVersion : String
  schemaUtf8 : String
  revision : Nat
  bootstrapClosed : Bool
  atoms : List Atom
  acceptedTransitionIds : List String
deriving Repr, DecidableEq

structure Guard where
  schema : String
  ownerTotality : String
  references : String
  revision : String
  permission : String
deriving Repr, DecidableEq

structure Receipt where
  transitionId : String
  schemaVersion : String
  previousStateRevision : Nat
  nextStateRevision : Nat
  readSet : List Key
  writeSet : List Key
  traceRef : Option Key
  guard : Guard
  actorClaim : String
  authorizationRef : String
  scope : String
  decidedAt : String
  decision : String
  provenanceSha256 : String
deriving Repr, DecidableEq

structure Command where
  transitionId : String
  schemaVersion : String
  expectedStateRevision : Nat
  readSet : List Key
  traceRef : Option Key
  actorClaim : String
  authorizationRef : String
  scope : String
  decidedAt : String
  provenanceSha256 : String
  writes : List Atom
deriving Repr, DecidableEq

def image (a : Atom) : AtomImage := ⟨keyId a.key, a.envelopeUtf8⟩
def native (s : State) : CanonicalPreservation.State :=
  ⟨s.schemaVersion, s.schemaUtf8, s.revision, s.bootstrapClosed, s.atoms.map image, s.acceptedTransitionIds⟩
def nativeCommand (c : Command) : CanonicalPreservation.Command :=
  ⟨c.schemaVersion, c.expectedStateRevision, c.transitionId, c.writes.map image⟩

theorem image_keys (xs : List Atom) : (xs.map image).map AtomImage.key =
    xs.map (fun a => keyId a.key) := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [image, ih]

def sortKeys (ks : List Key) : List Key := ks.mergeSort keyLe
def sortAtoms (xs : List Atom) : List Atom := xs.mergeSort (fun a b => keyLe a.key b.key)

def receiptCommand (r : Receipt) (writes : List Atom) : Command :=
  ⟨r.transitionId, r.schemaVersion, r.previousStateRevision, r.readSet, r.traceRef,
    r.actorClaim, r.authorizationRef, r.scope, r.decidedAt, r.provenanceSha256, writes⟩

def makeReceipt (c : Command) (before after : State) : Receipt :=
  ⟨c.transitionId, c.schemaVersion, before.revision, after.revision, sortKeys c.readSet,
    sortKeys (c.writes.map Atom.key), c.traceRef,
    ⟨"PASSED", "PASSED", "PASSED", "PASSED", "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"⟩,
    c.actorClaim, c.authorizationRef, c.scope, c.decidedAt, "ACCEPTED", c.provenanceSha256⟩

def candidate (before : State) (c : Command) : State :=
  ⟨before.schemaVersion, before.schemaUtf8, before.revision + 1, true,
    sortAtoms (before.atoms ++ c.writes), before.acceptedTransitionIds ++ [c.transitionId]⟩

def EnvelopeBinding (a : Atom) (observedEnvelope bindingEnvelope : Descriptor) (bindingKey : Key)
    (payload : Descriptor) : Bool :=
  observedEnvelope.mediaType == "application/vnd.hswm.canonical-atom-v2+json" &&
  observedEnvelope == bindingEnvelope && keyId a.key == keyId bindingKey && a.content == payload

theorem key_id_exact : keyId k =
    k.schemaVersion ++ "|" ++ k.lineageId ++ "|" ++ k.atomUid ++ "|" ++ toString k.revisionId := rfl

theorem sort_keys_perm (ks : List Key) : (sortKeys ks).Perm ks := List.mergeSort_perm _ _
theorem sort_atoms_perm (xs : List Atom) : (sortAtoms xs).Perm xs := List.mergeSort_perm _ _
theorem sort_keys_membership : k ∈ sortKeys ks ↔ k ∈ ks := List.mem_mergeSort
theorem sort_atoms_membership : a ∈ sortAtoms xs ↔ a ∈ xs := List.mem_mergeSort

theorem receipt_command_transition : (receiptCommand r writes).transitionId = r.transitionId := rfl
theorem receipt_command_schema : (receiptCommand r writes).schemaVersion = r.schemaVersion := rfl
theorem receipt_command_revision : (receiptCommand r writes).expectedStateRevision = r.previousStateRevision := rfl
theorem receipt_command_metadata :
    (receiptCommand r writes).actorClaim = r.actorClaim ∧
    (receiptCommand r writes).authorizationRef = r.authorizationRef ∧
    (receiptCommand r writes).scope = r.scope ∧
    (receiptCommand r writes).decidedAt = r.decidedAt ∧
    (receiptCommand r writes).provenanceSha256 = r.provenanceSha256 := by simp [receiptCommand]

theorem receipt_command_authorization_passthrough :
    (receiptCommand r writes).authorizationRef = r.authorizationRef := rfl

theorem recomputed_receipt_writes (c : Command) (before : State) :
    (makeReceipt c before (candidate before c)).writeSet = sortKeys (c.writes.map Atom.key) := rfl

theorem recomputed_receipt_read_set (c : Command) (before : State) :
    (makeReceipt c before (candidate before c)).readSet = sortKeys c.readSet := rfl

theorem recomputed_receipt_metadata (c : Command) (before : State) :
    let r := makeReceipt c before (candidate before c)
    r.actorClaim = c.actorClaim ∧ r.authorizationRef = c.authorizationRef ∧ r.scope = c.scope ∧
    r.decidedAt = c.decidedAt ∧ r.provenanceSha256 = c.provenanceSha256 := by simp [makeReceipt]

theorem recomputed_receipt_permission_label (c : Command) (before : State) :
    (makeReceipt c before (candidate before c)).guard.permission =
      "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT" := rfl

theorem candidate_schema (before : State) (c : Command) :
    (candidate before c).schemaUtf8 = before.schemaUtf8 := rfl
theorem candidate_version (before : State) (c : Command) :
    (candidate before c).schemaVersion = before.schemaVersion := rfl
theorem candidate_revision (before : State) (c : Command) :
    (candidate before c).revision = before.revision + 1 := rfl
theorem candidate_history (before : State) (c : Command) :
    (candidate before c).acceptedTransitionIds = before.acceptedTransitionIds ++ [c.transitionId] := rfl
theorem candidate_atom_membership : a ∈ (candidate before c).atoms ↔ a ∈ before.atoms ∨ a ∈ c.writes := by
  simp [candidate, sort_atoms_membership]
theorem candidate_retains_atoms (member : a ∈ before.atoms) : a ∈ (candidate before c).atoms :=
  candidate_atom_membership.mpr (Or.inl member)
theorem candidate_contains_writes (member : a ∈ c.writes) : a ∈ (candidate before c).atoms :=
  candidate_atom_membership.mpr (Or.inr member)
theorem candidate_no_invented_atom (member : a ∈ (candidate before c).atoms) :
    a ∈ before.atoms ∨ a ∈ c.writes := candidate_atom_membership.mp member

def Fresh (before : State) (c : Command) : Prop :=
  c.writes ≠ [] ∧ ((native before).atoms.map AtomImage.key).Nodup ∧
  ((nativeCommand c).writes.map AtomImage.key).Nodup ∧
  (∀ a ∈ (nativeCommand c).writes, a.key ∉ (native before).atoms.map AtomImage.key) ∧
  c.transitionId ∉ before.acceptedTransitionIds ∧ before.revision < maxSafeInteger
  ∧ c.expectedStateRevision = before.revision ∧ c.schemaVersion = before.schemaVersion

theorem native_candidate_preserves (h : Fresh before c) :
    CanonicalPreservation.preserves (native before) (native (candidate before c)) (nativeCommand c) = true := by
  rcases h with ⟨nonempty, beforeUnique, writesUnique, fresh, transitionFresh, revisionSafe, revisionMatches, schemaMatches⟩
  have atomPerm : (native (candidate before c)).atoms.Perm
      ((native before).atoms ++ (nativeCommand c).writes) := by
    simpa [native, candidate, nativeCommand, sortAtoms] using (sort_atoms_perm (before.atoms ++ c.writes)).map image
  apply CanonicalPreservation.preserves_iff.mpr
  refine ⟨CanonicalPreservation.headerPreserved_iff.mpr ?_, CanonicalPreservation.historyPreserved_iff.mpr ?_,
    CanonicalPreservation.atomsPreserved_iff.mpr ?_⟩
  · simp [native, candidate, nativeCommand, revisionSafe, Nat.succ_le_of_lt revisionSafe,
      Nat.le_of_lt revisionSafe, revisionMatches, schemaMatches]
  · simp [native, candidate, nativeCommand, transitionFresh]
  · refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
    · simpa [nativeCommand] using nonempty
    · exact beforeUnique
    · have keyPerm := atomPerm.map AtomImage.key
      apply keyPerm.nodup_iff.mpr
      simp only [List.map_append, List.nodup_append]
      refine ⟨beforeUnique, writesUnique, ?_⟩
      intro x inBefore y inWrites equal
      rcases List.mem_map.mp inWrites with ⟨write, writeMember, writeKey⟩
      apply fresh write writeMember
      rw [writeKey, ← equal]
      exact inBefore
    · exact writesUnique
    · intro atom member
      exact fresh atom member
    · simpa only [List.length_append] using atomPerm.length_eq
    · intro atom member
      have inAll : atom ∈ (native before).atoms ++ (nativeCommand c).writes := by simp [member]
      exact atomPerm.mem_iff.mpr inAll
    · intro atom member
      have inAll : atom ∈ (native before).atoms ++ (nativeCommand c).writes := by simp [member]
      exact atomPerm.mem_iff.mpr inAll

theorem candidate_preserves_fixed_fields (h : Fresh before c) :
    CanonicalPreservation.ExtendsNative (native before) (native (candidate before c)) :=
  CanonicalPreservation.preserved_extends_native (native_candidate_preserves h)

theorem envelope_binding_iff : EnvelopeBinding a observed bindingEnvelope bindingKey payload = true ↔
    observed.mediaType = "application/vnd.hswm.canonical-atom-v2+json" ∧
    observed = bindingEnvelope ∧ keyId a.key = keyId bindingKey ∧ a.content = payload := by
  simp [EnvelopeBinding, Bool.and_eq_true, and_assoc]

theorem wrong_envelope_rejected (h : observed ≠ bindingEnvelope) :
    EnvelopeBinding a observed bindingEnvelope key payload ≠ true :=
  fun accepted => h (envelope_binding_iff.mp accepted).2.1
theorem wrong_binding_key_rejected (h : keyId a.key ≠ keyId key) :
    EnvelopeBinding a observed bindingEnvelope key payload ≠ true :=
  fun accepted => h (envelope_binding_iff.mp accepted).2.2.1
theorem wrong_payload_rejected (h : a.content ≠ payload) :
    EnvelopeBinding a observed bindingEnvelope key payload ≠ true :=
  fun accepted => h (envelope_binding_iff.mp accepted).2.2.2

theorem exact_receipt_forces_actual_writes (matched : supplied = makeReceipt c before (candidate before c)) :
    supplied.writeSet = sortKeys (c.writes.map Atom.key) := by
  rw [matched, recomputed_receipt_writes]

theorem exact_receipt_metadata_passthrough (matched : supplied = makeReceipt c before (candidate before c)) :
    supplied.actorClaim = c.actorClaim ∧ supplied.authorizationRef = c.authorizationRef ∧
    supplied.scope = c.scope ∧ supplied.decidedAt = c.decidedAt := by
  rw [matched]
  simp [makeReceipt]

end HSWM.JournalAdapter
