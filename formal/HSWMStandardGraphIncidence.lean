import HSWMSemanticQuotient

/-!
# Dynamic HSWM metadata through typed incidence graphs

This is the normalized, decoded view of the existing RDF projection, not an
RDF parser or a replacement canonical store. Keys are opaque canonical-key
strings. Metadata contains exactly the selected fields exported by that view;
raw payloads, lifecycle, schema rules, journal and admission are not encoded.
Rows are normalized by their explicit ordinal, NEVER by RDF statement order.
Unlike the earlier fixed `Fin n` encoding, keys and arities may change at every
Step/Learn. Finite runtime snapshots are instances of the functional store.
-/
namespace HSWM.StandardGraphIncidence

structure Metadata where
  kind : String
  kindForm : String
  responsibilityOwner : String
  contentMediaType : String
  contentByteLength : Nat
  contentSha256 : String
  provenanceMode : String
  evidenceSha256 : String
  provenanceSource : Option String
deriving Repr, DecidableEq

structure Reference where
  referenceType : String
  role : String
  target : String
deriving Repr, DecidableEq

structure Atom where
  metadata : Metadata
  references : List Reference
deriving Repr, DecidableEq

abbrev Store := String → Option Atom

structure Participation where
  source : String
  ordinal : Nat
  reference : Reference
deriving Repr, DecidableEq

/-- Function keys give unique atom identity. A wire adapter must reject duplicate
headers before constructing this view; the type does not validate raw input. -/
structure Graph where
  headers : String → Option Metadata
  rows : String → List Participation

theorem graph_ext (left right : Graph) (heads : left.headers = right.headers)
    (rows : left.rows = right.rows) : left = right := by
  cases left
  cases right
  cases heads
  cases rows
  rfl

def enumerate (source : String) : Nat → List Reference → List Participation
  | _, [] => []
  | ordinal, reference :: rest =>
      ⟨source, ordinal, reference⟩ :: enumerate source (ordinal + 1) rest

def RowsAt (source : String) : Nat → List Participation → Prop
  | _, [] => True
  | ordinal, row :: rest =>
      row.source = source ∧ row.ordinal = ordinal ∧ RowsAt source (ordinal + 1) rest

def WellFormed (g : Graph) : Prop := ∀ key,
  match g.headers key with
  | none => g.rows key = []
  | some _ => RowsAt key 0 (g.rows key)

def rowsValid (source : String) : Nat → List Participation → Bool
  | _, [] => true
  | ordinal, row :: rest =>
      row.source == source && row.ordinal == ordinal && rowsValid source (ordinal + 1) rest

theorem rowsValid_iff (source : String) (start : Nat) (rows : List Participation) :
    rowsValid source start rows = true ↔ RowsAt source start rows := by
  induction rows generalizing start with
  | nil => simp [rowsValid, RowsAt]
  | cons row rest ih => simp [rowsValid, RowsAt, Bool.and_eq_true, ih, and_assoc]

def encode (s : Store) : Graph where
  headers key := (s key).map Atom.metadata
  rows key := match s key with
    | none => []
    | some atom => enumerate key 0 atom.references

def decode (g : Graph) : Store := fun key =>
  (g.headers key).map (fun metadata => ⟨metadata, (g.rows key).map Participation.reference⟩)

theorem enumerate_references (key : String) (start : Nat) (refs : List Reference) :
    (enumerate key start refs).map Participation.reference = refs := by
  induction refs generalizing start with
  | nil => rfl
  | cons ref rest ih => simp [enumerate, ih]

theorem enumerate_length (key : String) (start : Nat) (refs : List Reference) :
    (enumerate key start refs).length = refs.length := by
  induction refs generalizing start with
  | nil => rfl
  | cons ref rest ih => simp [enumerate, ih]

theorem enumerate_rowsAt (key : String) (start : Nat) (refs : List Reference) :
    RowsAt key start (enumerate key start refs) := by
  induction refs generalizing start with
  | nil => trivial
  | cons ref rest ih => exact ⟨rfl, rfl, ih _⟩

theorem rowsAt_reconstruct (key : String) (start : Nat) (rows : List Participation)
    (h : RowsAt key start rows) :
    enumerate key start (rows.map Participation.reference) = rows := by
  induction rows generalizing start with
  | nil => rfl
  | cons row rest ih =>
    rcases h with ⟨source, ordinal, tail⟩
    cases row
    simp_all [enumerate]

theorem encode_wellFormed (s : Store) : WellFormed (encode s) := by
  intro key
  cases h : s key with
  | none => simp [encode, h]
  | some atom => simpa [encode, h] using enumerate_rowsAt key 0 atom.references

theorem decode_encode (s : Store) : decode (encode s) = s := by
  funext key
  cases h : s key with
  | none => simp [decode, encode, h]
  | some atom => simp [decode, encode, h, enumerate_references]

/-- The reverse round trip needs source/ordinal consistency and no orphan rows. -/
theorem encode_decode (g : Graph) (h : WellFormed g) : encode (decode g) = g := by
  have heads : (encode (decode g)).headers = g.headers := by
    funext key
    cases found : g.headers key <;> simp [encode, decode, found]
  have rows : (encode (decode g)).rows = g.rows := by
    funext key
    have atKey := h key
    cases found : g.headers key with
    | none =>
      have absent : g.rows key = [] := by simpa [found] using atKey
      simp [encode, decode, found, absent]
    | some metadata =>
      simp only [found] at atKey
      simpa [encode, decode, found] using rowsAt_reconstruct key 0 (g.rows key) atKey
  exact graph_ext _ _ heads rows

theorem encoding_injective {left right : Store} (h : encode left = encode right) :
    left = right := by
  have := congrArg decode h
  simpa only [decode_encode] using this

/-- The executable comparison is only about this explicitly selected view. -/
def checkAt (s : Store) (g : Graph) (key : String) : Bool :=
  (match g.headers key with
  | none => (g.rows key).isEmpty
  | some _ => rowsValid key 0 (g.rows key)) && decide (decode g key = s key)

theorem checkAt_reconstruction (s : Store) (g : Graph) (key : String)
    (h : checkAt s g key = true) : decode g key = s key := by
  simp only [checkAt, Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.2

theorem checked_graph_wellFormed (s : Store) (g : Graph)
    (h : ∀ key, checkAt s g key = true) : WellFormed g := by
  intro key
  have checked := h key
  simp only [checkAt, Bool.and_eq_true] at checked
  have valid := checked.1
  cases found : g.headers key with
  | none => simpa [found] using valid
  | some metadata => simpa [found, rowsValid_iff] using valid

theorem checked_graph_exact (s : Store) (g : Graph)
    (h : ∀ key, checkAt s g key = true) : decode g = s ∧ encode s = g := by
  have same : decode g = s := funext (fun key => checkAt_reconstruction s g key (h key))
  exact ⟨same, same ▸ encode_decode g (checked_graph_wellFormed s g h)⟩

/-- A finite checker covers the whole functional view when its key universe
contains all source atoms, headers AND row sources. Wire normalization must
establish the outside premises and reject duplicate header/source identities. -/
theorem finite_check_covers_view (keys : List String) (s : Store) (g : Graph)
    (checked : keys.all (checkAt s g) = true)
    (sourceOutside : ∀ key, key ∉ keys → s key = none)
    (headerOutside : ∀ key, key ∉ keys → g.headers key = none)
    (rowsOutside : ∀ key, key ∉ keys → g.rows key = []) :
    decode g = s ∧ encode s = g := by
  apply checked_graph_exact
  intro key
  by_cases inside : key ∈ keys
  · exact List.all_eq_true.mp checked key inside
  · simp [checkAt, decode, sourceOutside key inside, headerOutside key inside,
      rowsOutside key inside]

def SupportedOn (keys : List String) (s : Store) : Prop :=
  ∀ key, key ∉ keys → s key = none

theorem finite_support_preserved (keys : List String) (s : Store)
    (h : SupportedOn keys s) : ∀ key, key ∉ keys → (encode s).headers key = none := by
  intro key outside
  simp [encode, h key outside]

/-- A schema-selected domain/range obligation; this is not full SHACL semantics. -/
def TypedEndpoints (allowed : String → String → String → String → Prop) (s : Store) : Prop :=
  ∀ key atom, s key = some atom → ∀ ref ∈ atom.references,
    ∃ target, s ref.target = some target ∧
      allowed atom.metadata.kind ref.referenceType ref.role target.metadata.kind

theorem typed_endpoints_preserved (allowed : String → String → String → String → Prop)
    (s : Store) : TypedEndpoints allowed (decode (encode s)) ↔ TypedEndpoints allowed s := by
  rw [decode_encode]

/-- One normalized row is addressed by source AND slot, not just target. -/
theorem distinct_slots_keep_repeated_targets (key : String) (ref : Reference)
    (i j : Nat) (different : i ≠ j) :
    Participation.mk key i ref ≠ Participation.mk key j ref := by
  intro same
  exact different (congrArg Participation.ordinal same)

/-- A mathematical state update, NOT a canonical admission operation. -/
def put (s : Store) (key : String) (value : Option Atom) : Store :=
  fun other => if other = key then value else s other

def putGraph (g : Graph) (key : String) (value : Option Atom) : Graph where
  headers other := if other = key then value.map Atom.metadata else g.headers other
  rows other := if other = key then
      match value with
      | none => []
      | some atom => enumerate key 0 atom.references
    else g.rows other

theorem update_commutes (s : Store) (key : String) (value : Option Atom) :
    encode (put s key value) = putGraph (encode s) key value := by
  have headers : (encode (put s key value)).headers = (putGraph (encode s) key value).headers := by
    funext other
    by_cases same : other = key <;> simp [encode, put, putGraph, same]
  have rows : (encode (put s key value)).rows = (putGraph (encode s) key value).rows := by
    funext other
    by_cases same : other = key <;> simp [encode, put, putGraph, same]
  exact graph_ext _ _ headers rows

theorem other_key_unchanged (s : Store) (key other : String) (value : Option Atom)
    (different : other ≠ key) : put s key value other = s other := by
  simp [put, different]

open HSWM.SemanticQuotient

/-- Transport supplied Step/Learn dynamics across the decoded view. This
constructs a mathematical interpreter, not the production RDF write path. -/
def encodedDynamics (d : Dynamics Store Action Output Evidence) :
    Dynamics Graph Action Output Evidence where
  stepAllowed g a := d.stepAllowed (decode g) a
  learnAllowed g e := d.learnAllowed (decode g) e
  step g a := let result := d.step (decode g) a; (result.1, encode result.2)
  learn g e := encode (d.learn (decode g) e)

theorem encode_refines (d : Dynamics Store Action Output Evidence) :
    ExactRefinement d (encodedDynamics d) encode id where
  stepAllowed_iff := by intro s a; simp [encodedDynamics, decode_encode]
  learnAllowed_iff := by intro s e; simp [encodedDynamics, decode_encode]
  step_commutes := by intro s a _; simp [mapStep, encodedDynamics, decode_encode]
  learn_commutes := by intro s e _; simp [encodedDynamics, decode_encode]

theorem decode_refines (d : Dynamics Store Action Output Evidence) :
    ExactRefinement (encodedDynamics d) d decode id where
  stepAllowed_iff := by intro s a; rfl
  learnAllowed_iff := by intro s e; rfl
  step_commutes := by intro s a _; simp [mapStep, encodedDynamics, decode_encode]
  learn_commutes := by intro s e _; simp [encodedDynamics, decode_encode]

/-- Includes rejected events, new keys and arbitrary arity changes at each step. -/
theorem all_dynamic_interleavings_preserved (d : Dynamics Store Action Output Evidence)
    (s : Store) (events : List (Event Action Evidence)) :
    mapRun encode id (run d s events) = run (encodedDynamics d) (encode s) events :=
  run_refines (encode_refines d) s events

theorem dynamic_observations_equal (d : Dynamics Store Action Output Evidence)
    (s : Store) (events : List (Event Action Evidence)) :
    (run (encodedDynamics d) (encode s) events).1 = (run d s events).1 := by
  have h := congrArg Prod.fst (all_dynamic_interleavings_preserved d s events)
  simpa [mapRun] using h.symm

theorem dynamic_final_graph_wellFormed (d : Dynamics Store Action Output Evidence)
    (s : Store) (events : List (Event Action Evidence)) :
    WellFormed (run (encodedDynamics d) (encode s) events).2 := by
  have h := congrArg Prod.snd (all_dynamic_interleavings_preserved d s events)
  change encode (run d s events).2 = _ at h
  rw [← h]
  exact encode_wellFormed _

end HSWM.StandardGraphIncidence
