import HSWMCanonicalPreservation

/-!
Reference-grant decisions, exact immutable bytes, and a linearized journal.
Decoded guards mirror production code; decoding, SHA-256 and OS primitives are
external obligations. Atomic publication below is an explicit abstract step,
not a proof that POSIX, fsync, storage hardware or signatures implement it.
-/
namespace HSWM.DurablePreservation

abbrev Bytes := List UInt8

structure Grant where
  authorizationRef : String
  schemaVersion : String
  schemaContentSha256 : String
  scopes : List String
deriving Repr, DecidableEq

structure Request where
  authorizationRef : String
  schemaVersion : String
  schemaContentSha256 : String
  scope : String
deriving Repr, DecidableEq

inductive GrantDecision where
  | allowed | schemaContentMismatch | notGranted | schemaMismatch | scopeDenied
deriving Repr, DecidableEq

def referenceGrants (grants : List Grant) (r : Request) :=
  grants.filter (fun g => g.authorizationRef == r.authorizationRef)
def schemaGrants (grants : List Grant) (r : Request) :=
  (referenceGrants grants r).filter (fun g => g.schemaVersion == r.schemaVersion)
def contentGrants (active : String) (grants : List Grant) (r : Request) :=
  (schemaGrants grants r).filter (fun g => g.schemaContentSha256 == active)

def referenceGrantDecision (active : String) (grants : List Grant) (r : Request) : GrantDecision :=
  if r.schemaContentSha256 != active then .schemaContentMismatch
  else if (referenceGrants grants r).isEmpty then .notGranted
  else if (schemaGrants grants r).isEmpty then .schemaMismatch
  else if (contentGrants active grants r).isEmpty then .schemaContentMismatch
  else if (contentGrants active grants r).any (fun g => r.scope ∈ g.scopes) then .allowed
  else .scopeDenied

theorem allowed_binds_active_schema (h : referenceGrantDecision active grants r = .allowed) :
    r.schemaContentSha256 = active := by
  unfold referenceGrantDecision at h
  split at h <;> simp_all

theorem allowed_has_matching_grant (h : referenceGrantDecision active grants r = .allowed) :
    ∃ g ∈ grants, g.authorizationRef = r.authorizationRef ∧ g.schemaVersion = r.schemaVersion ∧
      g.schemaContentSha256 = active ∧ r.scope ∈ g.scopes := by
  unfold referenceGrantDecision at h
  split at h <;> try contradiction
  split at h <;> try contradiction
  split at h <;> try contradiction
  split at h <;> try contradiction
  split at h <;> try contradiction
  rename_i present
  simp only [List.any_eq_true, decide_eq_true_eq] at present
  rcases present with ⟨g, member, scope⟩
  simp only [contentGrants, schemaGrants, referenceGrants, List.mem_filter, beq_iff_eq] at member
  exact ⟨g, member.1.1.1, member.1.1.2, member.1.2, member.2, scope⟩

theorem matching_grant_allowed (bound : r.schemaContentSha256 = active)
    (member : g ∈ grants) (reference : g.authorizationRef = r.authorizationRef)
    (schema : g.schemaVersion = r.schemaVersion) (content : g.schemaContentSha256 = active)
    (scope : r.scope ∈ g.scopes) : referenceGrantDecision active grants r = .allowed := by
  have hr : g ∈ referenceGrants grants r := by simp [referenceGrants, member, reference]
  have hs : g ∈ schemaGrants grants r := by simp [schemaGrants, hr, schema]
  have hc : g ∈ contentGrants active grants r := by simp [contentGrants, hs, content]
  have ha : (contentGrants active grants r).any (fun g => r.scope ∈ g.scopes) = true := by
    simp only [List.any_eq_true, decide_eq_true_eq]
    exact ⟨g, hc, scope⟩
  have nr : (referenceGrants grants r).isEmpty = false := List.isEmpty_eq_false_iff.mpr (by intro empty; simp [empty] at hr)
  have ns : (schemaGrants grants r).isEmpty = false := List.isEmpty_eq_false_iff.mpr (by intro empty; simp [empty] at hs)
  have nc : (contentGrants active grants r).isEmpty = false := List.isEmpty_eq_false_iff.mpr (by intro empty; simp [empty] at hc)
  simp [referenceGrantDecision, bound, nr, ns, nc, ha]

theorem reference_grant_allowed_iff : referenceGrantDecision active grants r = .allowed ↔
    r.schemaContentSha256 = active ∧ ∃ g ∈ grants,
      g.authorizationRef = r.authorizationRef ∧ g.schemaVersion = r.schemaVersion ∧
      g.schemaContentSha256 = active ∧ r.scope ∈ g.scopes := by
  constructor
  · intro h; exact ⟨allowed_binds_active_schema h, allowed_has_matching_grant h⟩
  · rintro ⟨bound, g, member, reference, schema, content, scope⟩
    exact matching_grant_allowed bound member reference schema content scope

theorem absent_reference_rejected (h : referenceGrants grants r = []) :
    referenceGrantDecision active grants r ≠ .allowed := by
  by_cases bound : r.schemaContentSha256 = active <;> simp [referenceGrantDecision, h, bound]

def exactBytes (left right : Bytes) : Bool := decide (left = right)

theorem exact_bytes_iff : exactBytes left right = true ↔ left = right := by simp [exactBytes]

inductive ContentDecision where
  | create | reuse | conflict
deriving Repr, DecidableEq

def contentDecision (existing : Option Bytes) (proposed : Bytes) : ContentDecision :=
  match existing with
  | none => .create
  | some bytes => if exactBytes bytes proposed then .reuse else .conflict

theorem reuse_requires_exact_bytes (h : contentDecision (some old) proposed = .reuse) :
    old = proposed := by simpa [contentDecision, exactBytes] using h

theorem different_bytes_conflict (h : old ≠ proposed) :
    contentDecision (some old) proposed = .conflict := by simp [contentDecision, exactBytes, h]

abbrev ContentStore := String → Option Bytes

/-- An occupied key is never overwritten, even if digest names collide. -/
def putImmutable (store : ContentStore) (key : String) (bytes : Bytes) : ContentStore :=
  match store key with
  | some _ => store
  | none => fun query => if query = key then some bytes else store query

def ExtendsContent (before after : ContentStore) : Prop :=
  ∀ key bytes, before key = some bytes → after key = some bytes

theorem put_retains_bytes (store : ContentStore) (key : String) (bytes : Bytes) :
    ExtendsContent store (putImmutable store key bytes) := by
  intro query old present
  cases atKey : store key with
  | some existing => simpa [putImmutable, atKey] using present
  | none => by_cases same : query = key <;> simp_all [putImmutable]

theorem put_new_exact (empty : store key = none) :
    putImmutable store key bytes key = some bytes := by simp [putImmutable, empty]

theorem occupied_put_unchanged (present : store key = some old) :
    putImmutable store key bytes = store := by simp [putImmutable, present]

theorem extends_content_transitive (ab : ExtendsContent a b) (bc : ExtendsContent b c) :
    ExtendsContent a c := fun key bytes present => bc key bytes (ab key bytes present)

def stageAll : ContentStore → List (String × Bytes) → ContentStore
  | store, [] => store
  | store, (key, bytes) :: rest => stageAll (putImmutable store key bytes) rest

theorem finite_staging_retains_bytes (store : ContentStore) (writes : List (String × Bytes)) :
    ExtendsContent store (stageAll store writes) := by
  induction writes generalizing store with
  | nil => intro _ _ present; exact present
  | cons write rest ih => exact extends_content_transitive (put_retains_bytes _ _ _) (ih _)

structure Descriptor where
  mediaType : String
  byteLength : Nat
  sha256 : String
deriving Repr, DecidableEq

structure Entry where
  descriptor : Descriptor
  bytes : Bytes
deriving Repr, DecidableEq

structure Publication where
  revision : Nat
  predecessor : Option Descriptor
  entry : Entry
deriving Repr, DecidableEq

inductive JournalPlan where
  | append | alreadyCommitted | predecessorMismatch | concurrentConflict | revisionConflict
deriving Repr, DecidableEq

def predecessorAt (journal : List Entry) (revision : Nat) : Option Descriptor :=
  if revision = 0 then none else (journal[revision - 1]?).map Entry.descriptor

def tailDescriptor (journal : List Entry) : Option Descriptor := journal.getLast?.map Entry.descriptor

def journalPlan (journal : List Entry) (p : Publication) : JournalPlan :=
  if p.predecessor ≠ predecessorAt journal p.revision then .predecessorMismatch
  else match journal[p.revision]? with
  | some entry => if exactBytes entry.bytes p.entry.bytes then .alreadyCommitted else .concurrentConflict
  | none => if p.revision ≠ journal.length then .revisionConflict
    else if tailDescriptor journal ≠ p.predecessor then .predecessorMismatch
    else .append

theorem append_requires_exact_predecessor (h : journalPlan journal p = .append) :
    p.predecessor = predecessorAt journal p.revision := by
  unfold journalPlan at h
  split at h <;> simp_all

theorem append_requires_next_revision (h : journalPlan journal p = .append) :
    p.revision = journal.length := by
  unfold journalPlan at h
  split at h <;> try contradiction
  split at h
  · split at h <;> contradiction
  · split at h <;> simp_all

theorem retry_requires_exact_bytes (h : journalPlan journal p = .alreadyCommitted) :
    ∃ entry, journal[p.revision]? = some entry ∧ entry.bytes = p.entry.bytes := by
  unfold journalPlan at h
  split at h <;> try contradiction
  split at h
  · rename_i entry present
    split at h
    · rename_i exact; exact ⟨entry, present, exact_bytes_iff.mp exact⟩
    · contradiction
  · split at h <;> try contradiction
    split at h <;> contradiction

theorem occupied_different_record_rejected
    (predecessor : p.predecessor = predecessorAt journal p.revision)
    (present : journal[p.revision]? = some entry) (different : entry.bytes ≠ p.entry.bytes) :
    journalPlan journal p = .concurrentConflict := by
  simp [journalPlan, predecessor, present, exactBytes, different]

/-- Linearization model of one no-replace slot publication. The native preflight
may run earlier; POSIX must supply this atomic step and verified recovery. -/
def publishAtomic (journal : List Entry) (p : Publication) : List Entry :=
  if journalPlan journal p = .append then journal ++ [p.entry] else journal

def ExtendsJournal (before after : List Entry) : Prop := ∃ suffix, after = before ++ suffix

theorem publication_preserves_prefix (journal : List Entry) (p : Publication) :
    ExtendsJournal journal (publishAtomic journal p) := by
  unfold publishAtomic
  split
  · exact ⟨[p.entry], rfl⟩
  · exact ⟨[], by simp⟩

theorem publication_old_or_exact_successor (journal : List Entry) (p : Publication) :
    publishAtomic journal p = journal ∨ publishAtomic journal p = journal ++ [p.entry] := by
  unfold publishAtomic
  split <;> simp

theorem rejected_publication_unchanged (h : journalPlan journal p ≠ .append) :
    publishAtomic journal p = journal := by simp [publishAtomic, h]

theorem occupied_slot_cannot_append (present : journal[p.revision]? = some entry) :
    publishAtomic journal p = journal := by
  unfold publishAtomic journalPlan
  split <;> simp_all
  split <;> simp

theorem competing_publication_cannot_overwrite (journal : List Entry) (winner : Entry)
    (loser : Publication) (sameSlot : loser.revision = journal.length) :
    publishAtomic (journal ++ [winner]) loser = journal ++ [winner] := by
  apply occupied_slot_cannot_append (entry := winner)
  simp [sameSlot]

theorem journal_extension_transitive (ab : ExtendsJournal a b) (bc : ExtendsJournal b c) :
    ExtendsJournal a c := by
  rcases ab with ⟨left, rfl⟩
  rcases bc with ⟨right, rfl⟩
  exact ⟨left ++ right, by simp [List.append_assoc]⟩

def publishAll : List Entry → List Publication → List Entry
  | journal, [] => journal
  | journal, p :: rest => publishAll (publishAtomic journal p) rest

theorem finite_publication_preserves_prefix (journal : List Entry) (publications : List Publication) :
    ExtendsJournal journal (publishAll journal publications) := by
  induction publications generalizing journal with
  | nil => exact ⟨[], by simp [publishAll]⟩
  | cons p rest ih => exact journal_extension_transitive (publication_preserves_prefix _ _) (ih _)

/-- A crash observation may precede or follow the slot linearization. No partial
record is an allowed observation; real storage must justify this assumption. -/
def crashObservation (linked : Bool) (journal : List Entry) (p : Publication) : List Entry :=
  if linked then publishAtomic journal p else journal

theorem crash_observes_old_or_exact_successor (linked : Bool) (journal : List Entry) (p : Publication) :
    crashObservation linked journal p = journal ∨
      crashObservation linked journal p = journal ++ [p.entry] := by
  cases linked
  · simp [crashObservation]
  · exact publication_old_or_exact_successor journal p

theorem retained_atom_keeps_payload
    (native : CanonicalPreservation.RetainsAtoms beforeNative afterNative)
    (content : ExtendsContent beforeContent afterContent)
    (payloadKey : CanonicalPreservation.AtomImage → String)
    (present : atom ∈ beforeNative.atoms) (bound : beforeContent (payloadKey atom) = some bytes) :
    atom ∈ afterNative.atoms ∧ afterContent (payloadKey atom) = some bytes :=
  ⟨native atom present, content _ _ bound⟩

/-- A recovered snapshot. Binding journal bytes to native replay is an adapter
obligation; this model does not decode JSON records or verify their hashes. -/
structure Snapshot where
  native : CanonicalPreservation.State
  content : ContentStore
  journal : List Entry

structure CommitProposal where
  request : Request
  after : CanonicalPreservation.State
  command : CanonicalPreservation.Command
  publication : Publication
  structurallyValid : Bool

def commitReady (active : String) (grants : List Grant) (s : Snapshot) (c : CommitProposal) : Bool :=
  decide (referenceGrantDecision active grants c.request = .allowed) && c.structurallyValid &&
  CanonicalPreservation.preserves s.native c.after c.command &&
  decide (journalPlan s.journal c.publication = .append) &&
  decide (c.request.schemaVersion = c.command.schemaVersion) &&
  decide (c.publication.revision = c.after.revision)

theorem commit_ready_iff : commitReady active grants s c = true ↔
    referenceGrantDecision active grants c.request = .allowed ∧ c.structurallyValid = true ∧
    CanonicalPreservation.preserves s.native c.after c.command = true ∧
    journalPlan s.journal c.publication = .append ∧
    c.request.schemaVersion = c.command.schemaVersion ∧ c.publication.revision = c.after.revision := by
  simp [commitReady, Bool.and_eq_true, and_assoc]

/-- Conditional logical commit: native state is the replay of the winning
journal prefix. Physical realization and record decoding are not assumed proved. -/
def conditionalCommit (active : String) (grants : List Grant) (s : Snapshot) (c : CommitProposal) : Snapshot :=
  if commitReady active grants s c then
    { s with native := c.after, journal := publishAtomic s.journal c.publication }
  else s

theorem denied_grant_keeps_snapshot (denied : referenceGrantDecision active grants c.request ≠ .allowed) :
    conditionalCommit active grants s c = s := by simp [conditionalCommit, commitReady, denied]

theorem ready_has_exact_grant (h : commitReady active grants s c = true) :
    c.request.schemaContentSha256 = active ∧ ∃ g ∈ grants,
      g.authorizationRef = c.request.authorizationRef ∧ g.schemaVersion = c.command.schemaVersion ∧
      g.schemaContentSha256 = active ∧ c.request.scope ∈ g.scopes := by
  have facts := commit_ready_iff.mp h
  rcases reference_grant_allowed_iff.mp facts.1 with ⟨bound, g, member, reference, schema, content, scope⟩
  exact ⟨bound, g, member, reference, schema.trans facts.2.2.2.2.1, content, scope⟩

def ExtendsSnapshot (before after : Snapshot) : Prop :=
  CanonicalPreservation.ExtendsNative before.native after.native ∧
  ExtendsContent before.content after.content ∧ ExtendsJournal before.journal after.journal

theorem conditional_commit_preserves_snapshot (active : String) (grants : List Grant)
    (s : Snapshot) (c : CommitProposal) : ExtendsSnapshot s (conditionalCommit active grants s c) := by
  by_cases ready : commitReady active grants s c = true
  · simp only [conditionalCommit, ready, ↓reduceIte]
    exact ⟨CanonicalPreservation.preserved_extends_native (commit_ready_iff.mp ready).2.2.1,
      fun _ _ h => h, publication_preserves_prefix _ _⟩
  · simp only [conditionalCommit, ready, Bool.false_eq_true, ↓reduceIte]
    exact ⟨CanonicalPreservation.extends_native_refl _, fun _ _ h => h, [], by simp⟩

theorem snapshot_extension_transitive (ab : ExtendsSnapshot a b) (bc : ExtendsSnapshot b c) :
    ExtendsSnapshot a c :=
  ⟨CanonicalPreservation.extends_native_transitive ab.1 bc.1,
    extends_content_transitive ab.2.1 bc.2.1, journal_extension_transitive ab.2.2 bc.2.2⟩

def commitAll (active : String) (grants : List Grant) : Snapshot → List CommitProposal → Snapshot
  | s, [] => s
  | s, c :: rest => commitAll active grants (conditionalCommit active grants s c) rest

theorem finite_conditional_commits_preserve_snapshot (active : String) (grants : List Grant)
    (s : Snapshot) (commands : List CommitProposal) : ExtendsSnapshot s (commitAll active grants s commands) := by
  induction commands generalizing s with
  | nil => exact ⟨CanonicalPreservation.extends_native_refl _, fun _ _ h => h, [], by simp [commitAll]⟩
  | cons c rest ih => exact snapshot_extension_transitive (conditional_commit_preserves_snapshot _ _ _ _) (ih _)

end HSWM.DurablePreservation
