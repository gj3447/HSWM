import HSWMSemanticReadLocality

/-!
# Decoded graph-loop head and read-set preflight

This mirrors the pure predicates called by the TypeScript graph-loop controller.
Head descriptors and canonical key IDs are decoded values: hashing, key encoding,
JSON decoding, grants, evidence, schema validation, atomic CAS and crash recovery
are NOT proved here. In particular, passing preflight is not canonical admission.
The accompanying differential test connects actual runtime snapshots to this
decoder; it is not a proof of all TypeScript executions.
-/

namespace HSWM.GraphLoopPreflight

structure Descriptor where
  sha256 : String
  mediaType : String
  byteLength : Nat
deriving Repr, DecidableEq

structure SchemaBinding where
  schemaVersion : String
  content : Descriptor
deriving Repr, DecidableEq

/-- Exactly the fields tested for freshness; not the compiled RDF projection. -/
structure Head where
  journalLineageId : String
  schema : SchemaBinding
  stateRevision : Nat
  stateSha256 : String
  journalHead : Descriptor
deriving Repr, DecidableEq

structure Candidate where
  schemaContentSha256 : String
  schemaVersion : String
  expectedStateRevision : Nat
  traceAbsent : Bool
  writeCount : Nat
  readKeys : List String
deriving Repr, DecidableEq

def headMatches (expected current : Head) : Bool := decide (expected = current)

def emptyMatchAllowed (revision : Nat) (keys reads affected : List String) : Bool :=
  !affected.isEmpty || (revision == 0 && keys.isEmpty && reads.isEmpty)

def candidateMatches (source : Head) (keys : List String) (c : Candidate)
    (affected : List String) : Bool :=
  c.schemaContentSha256 = source.schema.content.sha256 &&
  c.schemaVersion = source.schema.schemaVersion &&
  c.expectedStateRevision = source.stateRevision && c.traceAbsent &&
  0 < c.writeCount && affected.all (fun k => decide (k ∈ c.readKeys)) &&
  c.readKeys.all (fun k => decide (k ∈ keys))

def preflight (source current : Head) (keys : List String) (c : Candidate)
    (affected : List String) : Bool :=
  headMatches source current && emptyMatchAllowed current.stateRevision keys c.readKeys affected &&
  candidateMatches source keys c affected

theorem headMatches_iff (expected current : Head) :
    headMatches expected current = true ↔ expected = current := by
  simp [headMatches]

theorem candidateMatches_iff : candidateMatches source keys c affected = true ↔
    c.schemaContentSha256 = source.schema.content.sha256 ∧
    c.schemaVersion = source.schema.schemaVersion ∧
    c.expectedStateRevision = source.stateRevision ∧ c.traceAbsent = true ∧
    0 < c.writeCount ∧ (∀ k ∈ affected, k ∈ c.readKeys) ∧
    (∀ k ∈ c.readKeys, k ∈ keys) := by
  simp [candidateMatches, Bool.and_eq_true, decide_eq_true_eq, and_assoc]

theorem preflight_iff : preflight source current keys c affected = true ↔
    source = current ∧ emptyMatchAllowed current.stateRevision keys c.readKeys affected = true ∧
    candidateMatches source keys c affected = true := by
  simp [preflight, headMatches, Bool.and_eq_true, and_assoc]

theorem preflight_requires_exact_head
    (h : preflight source current keys c affected = true) : source = current :=
  (preflight_iff.mp h).1

theorem stale_head_fails (different : source ≠ current) :
    preflight source current keys c affected = false := by
  simp [preflight, headMatches, different]

theorem changed_global_revision_fails (different : source.stateRevision ≠ current.stateRevision) :
    preflight source current keys c affected = false := by
  apply stale_head_fails
  intro same
  exact different (congrArg Head.stateRevision same)

theorem preflight_requires_canonical_reads
    (h : preflight source current keys c affected = true) :
    ∀ k ∈ c.readKeys, k ∈ keys :=
  (candidateMatches_iff.mp (preflight_iff.mp h).2.2).2.2.2.2.2.2

theorem preflight_requires_affected_reads
    (h : preflight source current keys c affected = true) :
    ∀ k ∈ affected, k ∈ c.readKeys :=
  (candidateMatches_iff.mp (preflight_iff.mp h).2.2).2.2.2.2.2.1

theorem preflight_requires_write
    (h : preflight source current keys c affected = true) : 0 < c.writeCount :=
  (candidateMatches_iff.mp (preflight_iff.mp h).2.2).2.2.2.2.1

theorem empty_match_requires_genesis
    (h : preflight source current keys c [] = true) :
    current.stateRevision = 0 ∧ keys = [] ∧ c.readKeys = [] := by
  have empty := (preflight_iff.mp h).2.1
  simpa [emptyMatchAllowed, Bool.and_eq_true, and_assoc] using empty

theorem missing_read_fails (missing : k ∈ c.readKeys) (absent : k ∉ keys) :
    preflight source current keys c affected ≠ true := by
  intro h
  exact absent (preflight_requires_canonical_reads h k missing)

theorem affected_without_read_fails (affectedKey : k ∈ affected) (absent : k ∉ c.readKeys) :
    preflight source current keys c affected ≠ true := by
  intro h
  exact absent (preflight_requires_affected_reads h k affectedKey)

/-- The declared graph-read part and approval-relevant part are separate. -/
structure ObservedStore where
  head : Head
  canonicalKeys : List String
  bodies : SemanticReadLocality.GraphStore

def read (store : ObservedStore) (event : String)
    (relation : SemanticLifecycleRefinement.Relation) :=
  SemanticReadLocality.readPlan store.bodies event relation

/-- Sufficient conditions for BOTH local payload and preflight preservation.
The canonical key list is a conservative condition, not a claimed minimum. -/
theorem read_and_preflight_preserved (left right : ObservedStore)
    (sameHead : left.head = right.head) (sameKeys : left.canonicalKeys = right.canonicalKeys)
    (sameBodies : SemanticReadLocality.StoresAgreeOn left.bodies right.bodies relation.roles) :
    read left event relation = read right event relation ∧
    preflight source left.head left.canonicalKeys c affected =
      preflight source right.head right.canonicalKeys c affected := by
  constructor
  · exact SemanticReadLocality.readPlan_locality _ _ _ _ sameBodies
  · rw [sameHead, sameKeys]

def exampleDescriptor : Descriptor := ⟨"opaque-digest", "application/json", 10⟩
def exampleHead : Head := ⟨"journal", ⟨"v2", exampleDescriptor⟩, 1, "state", exampleDescriptor⟩
def exampleCandidate : Candidate := ⟨"opaque-digest", "v2", 1, true, 1, ["relation"]⟩
def exampleStore : ObservedStore := ⟨exampleHead, ["relation"], fun _ => none⟩
def advancedStore : ObservedStore :=
  { exampleStore with head := { exampleHead with stateRevision := 2 } }

/-- An inhabited successful local read can be identical while preflight differs.
This is a decoded-state counterexample; actual disjoint-write evidence belongs
to the controller integration test. It does not assume hash collisions. -/
theorem read_projection_alone_does_not_preserve_preflight :
    read exampleStore "event" (SemanticReadLocality.sampleRelation [] []) =
      read advancedStore "event" (SemanticReadLocality.sampleRelation [] []) ∧
    (read exampleStore "event" (SemanticReadLocality.sampleRelation [] [])).isSome = true ∧
    preflight exampleHead exampleStore.head exampleStore.canonicalKeys exampleCandidate ["relation"] = true ∧
    preflight exampleHead advancedStore.head advancedStore.canonicalKeys exampleCandidate ["relation"] = false := by
  decide

end HSWM.GraphLoopPreflight
