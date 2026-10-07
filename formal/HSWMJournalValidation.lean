import HSWMJournalAdapter
namespace HSWM.JournalValidation

inductive ReadSetDecision where | passed | stateDuplicate | duplicate | missing
deriving Repr, DecidableEq

def hasDuplicate (xs : List String) : Bool := decide (¬ xs.Nodup)
def readSetDecision (existing readSet : List String) : ReadSetDecision :=
  if hasDuplicate existing then .stateDuplicate
  else if hasDuplicate readSet then .duplicate
  else if readSet.any (fun key => !(key ∈ existing)) then .missing else .passed

theorem has_duplicate_iff : hasDuplicate xs = true ↔ ¬ xs.Nodup := by simp [hasDuplicate]
theorem state_duplicate_iff : readSetDecision existing readSet = .stateDuplicate ↔ ¬ existing.Nodup := by
  by_cases unique : existing.Nodup
  · unfold readSetDecision
    simp [hasDuplicate, unique]
    by_cases readUnique : readSet.Nodup
    · by_cases missing : ∃ key ∈ readSet, key ∉ existing <;>
        simp [readUnique, missing]
    · simp [readUnique]
  · simp [readSetDecision, hasDuplicate, unique]
theorem duplicate_iff (existingUnique : existing.Nodup) :
    readSetDecision existing readSet = .duplicate ↔ ¬ readSet.Nodup := by
  by_cases unique : readSet.Nodup
  · unfold readSetDecision
    simp [hasDuplicate, existingUnique, unique]
    split <;> simp
  · simp [readSetDecision, hasDuplicate, existingUnique, unique]
theorem missing_iff (existingUnique : existing.Nodup) (readUnique : readSet.Nodup) :
    readSetDecision existing readSet = .missing ↔ ∃ key ∈ readSet, key ∉ existing := by
  constructor
  · intro h
    simp [readSetDecision, hasDuplicate, existingUnique, readUnique] at h
    exact h
  · rintro ⟨key, member, absent⟩
    simp [readSetDecision, hasDuplicate, existingUnique, readUnique]
    exact ⟨key, member, by simpa using absent⟩
theorem passed_iff : readSetDecision existing readSet = .passed ↔
    existing.Nodup ∧ readSet.Nodup ∧ ∀ key ∈ readSet, key ∈ existing := by
  constructor
  · intro h
    have existingUnique : existing.Nodup := by
      by_cases unique : existing.Nodup
      · exact unique
      · rw [state_duplicate_iff.mpr unique] at h; cases h
    have readUnique : readSet.Nodup := by
      by_cases unique : readSet.Nodup
      · exact unique
      · rw [duplicate_iff existingUnique |>.mpr unique] at h; cases h
    refine ⟨existingUnique, readUnique, ?_⟩
    intro key member
    by_cases present : key ∈ existing
    · exact present
    · rw [missing_iff existingUnique readUnique |>.mpr ⟨key, member, present⟩] at h; cases h
  · rintro ⟨existingUnique, readUnique, contained⟩
    have noMissing : ¬ ∃ key ∈ readSet, key ∉ existing := by
      rintro ⟨key, member, absent⟩; exact absent (contained key member)
    simp [readSetDecision, hasDuplicate, existingUnique, readUnique, List.any_eq_true, noMissing]
theorem state_duplicate_precedes_read_failure (duplicate : ¬ existing.Nodup) :
    readSetDecision existing readSet = .stateDuplicate := state_duplicate_iff.mpr duplicate
theorem read_duplicate_precedes_missing (existingUnique : existing.Nodup) (duplicate : ¬ readSet.Nodup) :
    readSetDecision existing readSet = .duplicate := duplicate_iff existingUnique |>.mpr duplicate
theorem passed_existing_unique (passed : readSetDecision existing readSet = .passed) : existing.Nodup :=
  (passed_iff.mp passed).1
theorem passed_read_unique (passed : readSetDecision existing readSet = .passed) : readSet.Nodup :=
  (passed_iff.mp passed).2.1
theorem passed_resolves_every_key (passed : readSetDecision existing readSet = .passed)
    (member : key ∈ readSet) : key ∈ existing := (passed_iff.mp passed).2.2 key member
theorem empty_read_set_passes (existingUnique : existing.Nodup) : readSetDecision existing [] = .passed := by
  simp [readSetDecision, hasDuplicate, existingUnique]
theorem duplicate_existing_rejected (duplicate : ¬ existing.Nodup) : readSetDecision existing readSet ≠ .passed := by
  simp [state_duplicate_precedes_read_failure duplicate]
theorem missing_rejected (existingUnique : existing.Nodup) (readUnique : readSet.Nodup)
    (member : key ∈ readSet) (absent : key ∉ existing) : readSetDecision existing readSet ≠ .passed := by
  simp [missing_iff existingUnique readUnique |>.mpr ⟨key, member, absent⟩]

/-- This is the direct bridge to JournalAdapter's input-only preservation
premise. It adds read-set uniqueness/resolution, but does not claim the whole
native atom, schema, provenance, JSON or Permit validation. -/
theorem adapter_fresh_and_resolved_passes (fresh : HSWM.JournalAdapter.Fresh before command)
    (readUnique : (command.readSet.map HSWM.JournalAdapter.keyId).Nodup)
    (resolved : ∀ key ∈ command.readSet.map HSWM.JournalAdapter.keyId,
      key ∈ (HSWM.JournalAdapter.native before).atoms.map HSWM.CanonicalPreservation.AtomImage.key) :
    readSetDecision ((HSWM.JournalAdapter.native before).atoms.map HSWM.CanonicalPreservation.AtomImage.key)
      (command.readSet.map HSWM.JournalAdapter.keyId) = .passed :=
  passed_iff.mpr ⟨fresh.2.1, readUnique, resolved⟩
end HSWM.JournalValidation
