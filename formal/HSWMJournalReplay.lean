import HSWMDurablePreservation

/-! Exact re-encoding and decoded journal replay. Parsing, snapshot encoding,
SHA-256, envelope validation and native evolution remain adapter obligations.
Witness values are computed by those operations in runtime tests; they do not
certify their producers. Replay is not authorization or storage I/O. -/
namespace HSWM.JournalReplay

/-- Parameterized strict parser/schema decoder; not a verified JSON parser. -/
def decodeExact {α : Type} (parse : DurablePreservation.Bytes → Option α) (encode : α → Option DurablePreservation.Bytes)
    (raw : DurablePreservation.Bytes) : Option α := do
  let value ← parse raw
  let encoded ← encode value
  if DurablePreservation.exactBytes raw encoded then some value else none

theorem decode_exact_binds_bytes (h : decodeExact parse encode raw = some value) :
    parse raw = some value ∧ encode value = some raw := by
  unfold decodeExact at h
  cases hp : parse raw with
  | none => simp [hp] at h
  | some v =>
    cases he : encode v with
    | none => simp [hp, he] at h
    | some bytes =>
      simp [hp, he, DurablePreservation.exactBytes] at h
      rcases h with ⟨equal, same⟩
      subst value
      exact ⟨rfl, by simpa [equal] using he⟩

theorem accepted_representation_unique
    (left : decodeExact parse encode a = some value)
    (right : decodeExact parse encode b = some value) : a = b := by
  have ea := (decode_exact_binds_bytes left).2
  have eb := (decode_exact_binds_bytes right).2
  exact Option.some.inj (ea.symm.trans eb)

theorem exact_roundtrip_under_parser_law
    (encoded : encode value = some raw) (parsed : parse raw = some value) :
    decodeExact parse encode raw = some value := by
  simp [decodeExact, parsed, encoded, DurablePreservation.exactBytes]

theorem parser_failure_rejected (h : parse raw = none) : decodeExact parse encode raw = none := by
  simp [decodeExact, h]

structure SchemaBinding where
  schemaVersion : String
  content : DurablePreservation.Descriptor
deriving Repr, DecidableEq

structure Head where
  native : CanonicalPreservation.State
  descriptor : DurablePreservation.Descriptor
  journalLineageId : String
  schema : SchemaBinding
deriving Repr, DecidableEq

structure ReceiptHeader where
  transitionId : String
  schemaVersion : String
  previousStateRevision : Nat
  nextStateRevision : Nat
  decision : String
  permission : String
deriving Repr, DecidableEq

structure Record where
  journalLineageId : String
  predecessor : DurablePreservation.Descriptor
  stateRevision : Nat
  schema : SchemaBinding
  receipt : ReceiptHeader
  previousStateSha256 : String
  resultingStateSha256 : String
deriving Repr, DecidableEq

def linkMatches (before : Head) (r : Record) : Bool :=
  r.journalLineageId == before.journalLineageId && r.predecessor == before.descriptor &&
  r.stateRevision == before.native.revision + 1

def schemaMatches (expected actual : SchemaBinding) : Bool :=
  expected.schemaVersion == actual.schemaVersion && expected.content == actual.content

def receiptHeaderMatches (previousRevision recordRevision : Nat) (activeVersion : String)
    (receipt : ReceiptHeader) : Bool :=
  receipt.previousStateRevision == previousRevision && receipt.nextStateRevision == recordRevision &&
  receipt.schemaVersion == activeVersion && receipt.decision == "ACCEPTED" &&
  receipt.permission == "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"

theorem link_matches_iff : linkMatches before r = true ↔
    r.journalLineageId = before.journalLineageId ∧ r.predecessor = before.descriptor ∧
    r.stateRevision = before.native.revision + 1 := by
  simp [linkMatches, Bool.and_eq_true, and_assoc]

theorem schema_matches_iff : schemaMatches expected actual = true ↔ expected = actual := by
  cases expected; cases actual
  simp [schemaMatches, Bool.and_eq_true, SchemaBinding.mk.injEq]

theorem receipt_header_matches_iff : receiptHeaderMatches previousRevision recordRevision activeVersion receipt = true ↔
    receipt.previousStateRevision = previousRevision ∧ receipt.nextStateRevision = recordRevision ∧
    receipt.schemaVersion = activeVersion ∧ receipt.decision = "ACCEPTED" ∧
    receipt.permission = "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT" := by
  simp [receiptHeaderMatches, Bool.and_eq_true, and_assoc]

/-- Computed observations. No digest-injectivity assumption. -/
structure Witness where
  after : CanonicalPreservation.State
  writes : List CanonicalPreservation.AtomImage
  previousDigest : String
  resultingDigest : String
  receiptBytes : DurablePreservation.Bytes
  expectedReceiptBytes : DurablePreservation.Bytes
  recordDescriptor : DurablePreservation.Descriptor
deriving Repr, DecidableEq

def receiptCommand (r : Record) (w : Witness) : CanonicalPreservation.Command :=
  ⟨r.receipt.schemaVersion, r.receipt.previousStateRevision, r.receipt.transitionId, w.writes⟩

/-- Necessary decoded boundary, not a replacement admission checker.
Envelope/parser/evolution validation must already have succeeded. -/
def accepted (active : SchemaBinding) (before : Head) (r : Record) (w : Witness) : Bool :=
  linkMatches before r && schemaMatches before.schema r.schema && schemaMatches active r.schema &&
  (w.previousDigest == r.previousStateSha256) &&
  receiptHeaderMatches before.native.revision r.stateRevision active.schemaVersion r.receipt &&
  CanonicalPreservation.preserves before.native w.after (receiptCommand r w) &&
  DurablePreservation.exactBytes w.receiptBytes w.expectedReceiptBytes && (w.resultingDigest == r.resultingStateSha256)

theorem accepted_iff : accepted active before r w = true ↔
    linkMatches before r = true ∧ schemaMatches before.schema r.schema = true ∧
    schemaMatches active r.schema = true ∧ w.previousDigest = r.previousStateSha256 ∧
    receiptHeaderMatches before.native.revision r.stateRevision active.schemaVersion r.receipt = true ∧
    CanonicalPreservation.preserves before.native w.after (receiptCommand r w) = true ∧
    w.receiptBytes = w.expectedReceiptBytes ∧ w.resultingDigest = r.resultingStateSha256 := by
  simp [accepted, Bool.and_eq_true, DurablePreservation.exactBytes, and_assoc]

theorem accepted_receipt_exact (h : accepted active before r w = true) :
    w.receiptBytes = w.expectedReceiptBytes := (accepted_iff.mp h).2.2.2.2.2.2.1

theorem accepted_preserves (h : accepted active before r w = true) :
    CanonicalPreservation.preserves before.native w.after (receiptCommand r w) = true :=
  (accepted_iff.mp h).2.2.2.2.2.1

theorem accepted_receipt_revision (h : accepted active before r w = true) :
    w.after.revision = r.receipt.nextStateRevision := by
  have link := link_matches_iff.mp (accepted_iff.mp h).1
  have receipt := receipt_header_matches_iff.mp (accepted_iff.mp h).2.2.2.2.1
  rw [CanonicalPreservation.revision_increases_once (accepted_preserves h), receipt.2.1, link.2.2]

theorem accepted_transition_history (h : accepted active before r w = true) :
    w.after.acceptedTransitionIds = before.native.acceptedTransitionIds ++ [r.receipt.transitionId] :=
  CanonicalPreservation.history_extends_exactly_once (accepted_preserves h)

theorem accepted_transition_fresh (h : accepted active before r w = true) :
    r.receipt.transitionId ∉ before.native.acceptedTransitionIds :=
  CanonicalPreservation.accepted_id_is_fresh (accepted_preserves h)

theorem wrong_predecessor_rejected (different : r.predecessor ≠ before.descriptor) :
    accepted active before r w ≠ true := fun h => different (link_matches_iff.mp (accepted_iff.mp h).1).2.1

theorem receipt_substitution_rejected (different : w.receiptBytes ≠ w.expectedReceiptBytes) :
    accepted active before r w ≠ true := fun h => different (accepted_receipt_exact h)

def step (active : SchemaBinding) (before : Head) (r : Record) (w : Witness) : Option Head :=
  if accepted active before r w then
    some ⟨w.after, w.recordDescriptor, before.journalLineageId, before.schema⟩
  else none

theorem step_success (h : step active before r w = some after) :
    accepted active before r w = true ∧
    after = ⟨w.after, w.recordDescriptor, before.journalLineageId, before.schema⟩ := by
  unfold step at h
  split at h
  · exact ⟨by assumption, (Option.some.inj h).symm⟩
  · contradiction

theorem rejected_step_has_no_successor (h : accepted active before r w = false) :
    step active before r w = none := by simp [step, h]

def Extends (before after : Head) : Prop :=
  CanonicalPreservation.ExtendsNative before.native after.native ∧
  before.schema = after.schema ∧ before.journalLineageId = after.journalLineageId

theorem extends_refl (state : Head) : Extends state state := ⟨CanonicalPreservation.extends_native_refl _, rfl, rfl⟩

theorem extends_trans (ab : Extends a b) (bc : Extends b c) : Extends a c :=
  ⟨CanonicalPreservation.extends_native_transitive ab.1 bc.1, ab.2.1.trans bc.2.1, ab.2.2.trans bc.2.2⟩

theorem step_extends (h : step active before r w = some after) : Extends before after := by
  rcases step_success h with ⟨ok, rfl⟩
  exact ⟨CanonicalPreservation.preserved_extends_native (accepted_preserves ok), rfl, rfl⟩

theorem step_revision (h : step active before r w = some after) :
    after.native.revision = before.native.revision + 1 := by
  rcases step_success h with ⟨ok, rfl⟩
  exact CanonicalPreservation.revision_increases_once (accepted_preserves ok)

def replay (active : SchemaBinding) : Head → List (Record × Witness) → Option Head
  | before, [] => some before
  | before, (r, w) :: rest => (step active before r w).bind fun next => replay active next rest

theorem finite_replay_extends (h : replay active before records = some after) : Extends before after := by
  induction records generalizing before with
  | nil => simp only [replay, Option.some.injEq] at h; subst after; exact extends_refl _
  | cons pair rest ih =>
    simp only [replay] at h
    cases hs : step active before pair.1 pair.2 with
    | none => simp [hs] at h
    | some next =>
      simp only [hs, Option.bind_some] at h
      exact extends_trans (step_extends hs) (ih h)

theorem finite_replay_revision (h : replay active before records = some after) :
    after.native.revision = before.native.revision + records.length := by
  induction records generalizing before with
  | nil => simpa [replay] using congrArg (fun h : Head => h.native.revision) (Option.some.inj h).symm
  | cons pair rest ih =>
    simp only [replay] at h
    cases hs : step active before pair.1 pair.2 with
    | none => simp [hs] at h
    | some next =>
      simp only [hs, Option.bind_some] at h
      rw [ih h, step_revision hs]
      simp [List.length_cons, Nat.add_assoc, Nat.add_comm 1]

theorem replay_append : replay active before (xs ++ ys) =
    (replay active before xs).bind (fun middle => replay active middle ys) := by
  induction xs generalizing before with
  | nil => simp [replay]
  | cons pair rest ih =>
    simp only [List.cons_append, replay]
    cases step active before pair.1 pair.2 <;> simp [ih]

theorem failed_prefix_rejects_extension (failed : replay active before xs = none) :
    replay active before (xs ++ ys) = none := by rw [replay_append, failed]; rfl

end HSWM.JournalReplay
