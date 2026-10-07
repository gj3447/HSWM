import HSWMJournalAdapter
import HSWMJournalReplay

/-! Model after the runtime has decoded bounded duplicate-free JSON and strict
schemas. Parser, hashes, TypeScript execution, storage and authority remain
explicit trusted boundaries. -/
namespace HSWM.JournalDecode
open HSWM HSWM.DurablePreservation HSWM.JournalReplay

structure DecodedWrite where
  atom : JournalAdapter.Atom
  observedEnvelope : Descriptor
  bindingEnvelope : Descriptor
  bindingKey : JournalAdapter.Key
  payload : Descriptor
  raw : Bytes
  canonical : Bytes
deriving Repr, DecidableEq

def writeMatches (w : DecodedWrite) : Bool :=
  exactBytes w.raw w.canonical &&
  JournalAdapter.EnvelopeBinding w.atom w.observedEnvelope w.bindingEnvelope w.bindingKey w.payload
def writesMatch : List DecodedWrite → Bool
  | [] => true
  | w :: rest => writeMatches w && writesMatch rest

theorem write_matches_iff : writeMatches w = true ↔
    w.raw = w.canonical ∧ w.observedEnvelope.mediaType = "application/vnd.hswm.canonical-atom-v2+json" ∧
    w.observedEnvelope = w.bindingEnvelope ∧ JournalAdapter.keyId w.atom.key = JournalAdapter.keyId w.bindingKey ∧
    w.atom.content = w.payload := by
  simp [writeMatches, exactBytes, JournalAdapter.envelope_binding_iff, Bool.and_eq_true]

theorem writes_match_each (h : writesMatch ws = true) (member : w ∈ ws) : writeMatches w = true := by
  induction ws with
  | nil => simp at member
  | cons head tail ih =>
    simp only [writesMatch, Bool.and_eq_true] at h
    simp only [List.mem_cons] at member
    rcases member with equal | member
    · simpa [equal] using h.1
    · exact ih h.2 member

theorem descriptor_substitution_rejected (different : w.observedEnvelope ≠ w.bindingEnvelope) : writeMatches w ≠ true :=
  fun accepted => different (write_matches_iff.mp accepted).2.2.1

def accepted (active : SchemaBinding) (before : Head) (r : Record) (decoded : List DecodedWrite) (w : Witness) : Bool :=
  writesMatch decoded && decoded.map (fun d => JournalAdapter.image d.atom) == w.writes && JournalReplay.accepted active before r w

theorem accepted_iff : accepted active before r decoded w = true ↔
    writesMatch decoded = true ∧ decoded.map (fun d => JournalAdapter.image d.atom) = w.writes ∧ JournalReplay.accepted active before r w = true := by
  simp [accepted, Bool.and_eq_true, and_assoc]
theorem accepted_receipt_exact (h : accepted active before r decoded w = true) : w.receiptBytes = w.expectedReceiptBytes :=
  JournalReplay.accepted_receipt_exact (accepted_iff.mp h).2.2
theorem accepted_preserves (h : accepted active before r decoded w = true) :
    CanonicalPreservation.preserves before.native w.after (receiptCommand r w) = true :=
  JournalReplay.accepted_preserves (accepted_iff.mp h).2.2
theorem accepted_write_binding (h : accepted active before r decoded w = true) (member : d ∈ decoded) :
    d.raw = d.canonical ∧ d.observedEnvelope = d.bindingEnvelope ∧ d.atom.content = d.payload := by
  have full := write_matches_iff.mp (writes_match_each (accepted_iff.mp h).1 member)
  exact ⟨full.1, full.2.2.1, full.2.2.2.2⟩
theorem accepted_forward (h : accepted active before r decoded w = true) :
    ∃ after, JournalReplay.step active before r w = some after ∧ JournalReplay.Extends before after := by
  let after : Head := ⟨w.after, w.recordDescriptor, before.journalLineageId, before.schema⟩
  have ok : JournalReplay.accepted active before r w = true := (accepted_iff.mp h).2.2
  have stepped : JournalReplay.step active before r w = some after := by
    simp [JournalReplay.step, after, ok]
  exact ⟨after, stepped, JournalReplay.step_extends stepped⟩
theorem wrong_revision_rejected (different : r.stateRevision ≠ before.native.revision + 1) : accepted active before r decoded w ≠ true := fun ok =>
  different (link_matches_iff.mp (JournalReplay.accepted_iff.mp (accepted_iff.mp ok).2.2).1).2.2
theorem receipt_bytes_substitution_rejected (different : w.receiptBytes ≠ w.expectedReceiptBytes) : accepted active before r decoded w ≠ true :=
  fun ok => different (accepted_receipt_exact ok)
/-- The concrete record producer's decoded fields. Digests and receipt encoding
are observations supplied by the native boundary; this does not compute hashes. -/
def producedHead (active : SchemaBinding) (before : JournalAdapter.State)
    (priorDescriptor : Descriptor) (lineage : String) : Head :=
  ⟨JournalAdapter.native before, priorDescriptor, lineage, active⟩
def producedRecord (active : SchemaBinding) (before : JournalAdapter.State)
    (command : JournalAdapter.Command) (priorDescriptor : Descriptor)
    (lineage previousDigest resultingDigest : String) : Record :=
  ⟨lineage, priorDescriptor, before.revision + 1, active,
    ⟨command.transitionId, command.schemaVersion, before.revision, before.revision + 1,
      "ACCEPTED", "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"⟩,
    previousDigest, resultingDigest⟩
def producedWitness (before : JournalAdapter.State) (command : JournalAdapter.Command)
    (previousDigest resultingDigest : String) (receiptEncoding : Bytes)
    (recordDescriptor : Descriptor) : Witness :=
  ⟨JournalAdapter.native (JournalAdapter.candidate before command),
    command.writes.map JournalAdapter.image, previousDigest, resultingDigest,
    receiptEncoding, receiptEncoding, recordDescriptor⟩

/-- Forward producer theorem: freshness and schema equality imply acceptance
of the constructed replay fields, without assuming a successful replay. -/
theorem produced_replay_accepted
    (fresh : JournalAdapter.Fresh before command)
    (schema : active.schemaVersion = before.schemaVersion) :
    JournalReplay.accepted active (producedHead active before prior lineage)
      (producedRecord active before command prior lineage previousDigest resultingDigest)
      (producedWitness before command previousDigest resultingDigest receiptEncoding descriptor) = true := by
  have revision := fresh.2.2.2.2.2.2.1
  have version := fresh.2.2.2.2.2.2.2
  have preserves := JournalAdapter.native_candidate_preserves fresh
  apply JournalReplay.accepted_iff.mpr
  refine ⟨?_, ?_, ?_, rfl, ?_, ?_, rfl, rfl⟩
  · simp [linkMatches, producedHead, producedRecord, JournalAdapter.native]
  · simp [schemaMatches, producedHead, producedRecord]
  · simp [schemaMatches, producedRecord]
  · simp [receiptHeaderMatches, producedHead, producedRecord, JournalAdapter.native, version, schema]
  · simpa [producedHead, producedRecord, producedWitness, receiptCommand,
      JournalAdapter.nativeCommand, revision] using preserves

/-- The same producer composes with actual decoded envelope images. These are
input byte/binding conditions, not an assumption that journal replay succeeded. -/
theorem produced_decoded_commit_accepted
    (fresh : JournalAdapter.Fresh before command)
    (schema : active.schemaVersion = before.schemaVersion)
    (envelopes : writesMatch decoded = true)
    (images : decoded.map (fun d => JournalAdapter.image d.atom) = command.writes.map JournalAdapter.image) :
    accepted active (producedHead active before prior lineage)
      (producedRecord active before command prior lineage previousDigest resultingDigest)
      decoded (producedWitness before command previousDigest resultingDigest receiptEncoding descriptor) = true :=
  accepted_iff.mpr ⟨envelopes, images, produced_replay_accepted fresh schema⟩

/-- Constructor for one already-parsed canonical envelope, with every binding
copied from its observed value and every byte kept. -/
def boundDecodedWrite (atom : JournalAdapter.Atom) (observed : Descriptor) (raw : Bytes) : DecodedWrite :=
  ⟨atom, observed, observed, atom.key, atom.content, raw, raw⟩
theorem bound_write_matches
    (media : observed.mediaType = "application/vnd.hswm.canonical-atom-v2+json") :
    writeMatches (boundDecodedWrite atom observed raw) = true := by
  simp [write_matches_iff, boundDecodedWrite, media]

end HSWM.JournalDecode
