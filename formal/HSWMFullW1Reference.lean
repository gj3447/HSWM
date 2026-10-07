import Std

/-!
Finite reference evaluator for the authored W1 fixture.  This file proves only
the explicit Boolean/role contracts below; it makes no claim about natural-
language equivalence, model behavior, or efficacy.
-/
namespace HSWMFullW1Reference

abbrev Bit := Bool

structure FieldBits where
  dax : Bit
  wug : Bit
  zif : Bit
  pel : Bit
  nub : Bit
deriving Repr, DecidableEq

structure Output where
  base : Bit
  contextFlip : Bit
  exceptionFlip : Bit
  answer : Bit
deriving Repr, DecidableEq

inductive Family where | f0 | f1 | f2 | f3
deriving Repr, DecidableEq

def reference (family : Family) (x : FieldBits) : Output :=
  let base := match family with
    | .f0 => x.dax.xor x.wug
    | .f1 => x.zif
    | .f2 => x.dax && x.wug
    | .f3 => if x.dax then x.wug else x.zif
  { base, contextFlip := x.pel, exceptionFlip := x.nub,
    answer := base.xor x.pel |>.xor x.nub }

def contextFlip (x : FieldBits) : FieldBits := { x with pel := !x.pel }
def exceptionFlip (x : FieldBits) : FieldBits := { x with nub := !x.nub }

theorem context_flip_xor (f : Family) (x : FieldBits) :
    (reference f (contextFlip x)).answer = !(reference f x).answer := by
  cases f <;> cases x <;> simp [reference, contextFlip]

theorem exception_flip_xor (f : Family) (x : FieldBits) :
    (reference f (exceptionFlip x)).answer = !(reference f x).answer := by
  cases f <;> cases x <;> simp [reference, exceptionFlip]

/- Typed role projection is an abstract field/role contract, not an NLP proof. -/
inductive Role where | subject | context | exception
deriving Repr, DecidableEq

inductive OpaqueRole where | r7 | r3 | r9
deriving Repr, DecidableEq

structure OpaqueFieldBits where
  v2 : Bit
  v5 : Bit
  v8 : Bit
  v4 : Bit
  v6 : Bit
deriving Repr, DecidableEq

def project (r : Role) (x : FieldBits) : List Bit :=
  match r with | .subject => [x.dax, x.wug, x.zif] | .context => [x.pel] | .exception => [x.nub]

def renameRole : Role → OpaqueRole
  | .subject => .r7 | .context => .r3 | .exception => .r9
def encodeOpaque (x : FieldBits) : OpaqueFieldBits := ⟨x.dax, x.wug, x.zif, x.pel, x.nub⟩
def decodeOpaque (x : OpaqueFieldBits) : FieldBits := ⟨x.v2, x.v5, x.v8, x.v4, x.v6⟩
def opaqueProject (r : OpaqueRole) (x : OpaqueFieldBits) : List Bit :=
  match r with | .r7 => [x.v2, x.v5, x.v8] | .r3 => [x.v4] | .r9 => [x.v6]
theorem decode_encode_opaque (x : FieldBits) : decodeOpaque (encodeOpaque x) = x := by cases x <;> rfl
theorem typed_role_rename_invariant (r : Role) (x : FieldBits) :
    opaqueProject (renameRole r) (encodeOpaque x) = project r x := by cases r <;> rfl
theorem opaque_rename_reference_invariant (f : Family) (x : FieldBits) :
    reference f (decodeOpaque (encodeOpaque x)) = reference f x := by rw [decode_encode_opaque]

structure TaggedBinding where
  role : Role
  ordinal : Nat
  payload : List Bit
deriving Repr, DecidableEq

def originalBindings (x : FieldBits) : List TaggedBinding :=
  [{ role := .subject, ordinal := 0, payload := project .subject x },
   { role := .context, ordinal := 1, payload := project .context x },
   { role := .exception, ordinal := 2, payload := project .exception x }]
def reorderedBindings (x : FieldBits) : List TaggedBinding := (originalBindings x).reverse
def lookupBinding (r : Role) (ordinal : Nat) : List TaggedBinding → Option (List Bit)
  | [] => none
  | b :: bs => if b.role = r ∧ b.ordinal = ordinal then some b.payload else lookupBinding r ordinal bs
def roleProjection (r : Role) (ordinal : Nat) (bs : List TaggedBinding) : Option (List Bit) :=
  lookupBinding r ordinal bs
theorem role_projection_reverse_invariant (r : Role) (x : FieldBits) :
    roleProjection r (match r with | .subject => 0 | .context => 1 | .exception => 2) (reorderedBindings x) =
      roleProjection r (match r with | .subject => 0 | .context => 1 | .exception => 2) (originalBindings x) := by
  cases r <;> simp [roleProjection, lookupBinding, reorderedBindings, originalBindings, project]

def reconstructFromBindings (bs : List TaggedBinding) : Option FieldBits :=
  match roleProjection .subject 0 bs, roleProjection .context 1 bs, roleProjection .exception 2 bs with
  | some [dax, wug, zif], some [pel], some [nub] => some ⟨dax, wug, zif, pel, nub⟩
  | _, _, _ => none
theorem reorder_reconstructs_same (x : FieldBits) : reconstructFromBindings (reorderedBindings x) = some x := by
  simp [reconstructFromBindings, roleProjection, lookupBinding, reorderedBindings, originalBindings, project]
theorem ordinal_preserving_permutation_invariant (f : Family) (x : FieldBits) :
    Option.map (reference f) (reconstructFromBindings (reorderedBindings x)) = some (reference f x) := by
  rw [reorder_reconstructs_same]
  rfl

def exchangeSubjectDaxContextPel (x : FieldBits) : FieldBits :=
  { x with dax := x.pel, pel := x.dax }

theorem exchange_involutive (x : FieldBits) :
    exchangeSubjectDaxContextPel (exchangeSubjectDaxContextPel x) = x := by cases x <;> rfl
theorem exchange_eq_self_iff (x : FieldBits) :
    exchangeSubjectDaxContextPel x = x ↔ x.dax = x.pel := by
  constructor
  · intro h
    cases x
    simpa [exchangeSubjectDaxContextPel] using (congrArg FieldBits.dax h).symm
  · intro h
    cases x
    cases h
    rfl
theorem reference_answer_from_intermediates (f : Family) (x : FieldBits) :
    (reference f x).answer = ((reference f x).base.xor (reference f x).contextFlip).xor (reference f x).exceptionFlip := by
  cases f <;> cases x <;> rfl

def allBits : List Bit := [false, true]
def allInputs : List FieldBits :=
  allBits.flatMap fun dax => allBits.flatMap fun wug => allBits.flatMap fun zif =>
  allBits.flatMap fun pel => allBits.map fun nub => ⟨dax, wug, zif, pel, nub⟩
def allFamilies : List Family := [.f0, .f1, .f2, .f3]
def allOriginalCases : List (Family × FieldBits) :=
  allFamilies.flatMap fun f => allInputs.map fun x => (f, x)

def changedInput (x : FieldBits) : Bool := decide (exchangeSubjectDaxContextPel x ≠ x)
def changedAnswer (f : Family) (x : FieldBits) : Bool :=
  decide ((reference f (exchangeSubjectDaxContextPel x)).answer ≠ (reference f x).answer)
def intermediates (o : Output) : Bit × Bit × Bit := (o.base, o.contextFlip, o.exceptionFlip)
def changedIntermediate (f : Family) (x : FieldBits) : Bool :=
  decide (intermediates (reference f (exchangeSubjectDaxContextPel x)) ≠ intermediates (reference f x))
def countWhere {α} (xs : List α) (p : α → Bool) : Nat := (xs.filter p).length

theorem all_inputs_nodup : allInputs.Nodup := by decide
theorem all_inputs_complete (x : FieldBits) : x ∈ allInputs := by
  cases x
  rename_i dax wug zif pel nub
  cases dax <;> cases wug <;> cases zif <;> cases pel <;> cases nub <;> simp [allInputs, allBits]
theorem all_inputs_length : allInputs.length = 32 := by decide
theorem all_original_cases_length : allOriginalCases.length = 128 := by
  simp only [allOriginalCases, List.length_flatMap, List.length_map]
  simp [allFamilies, all_inputs_length]
theorem role_exchange_changed_input_count :
    allFamilies.length * countWhere allInputs changedInput = 64 := by decide
theorem role_exchange_changed_answer_count :
    (countWhere allInputs (changedAnswer .f0) + countWhere allInputs (changedAnswer .f1) +
      countWhere allInputs (changedAnswer .f2) + countWhere allInputs (changedAnswer .f3)) = 32 := by decide
theorem role_exchange_changed_intermediate_count :
    (countWhere allInputs (changedIntermediate .f0) + countWhere allInputs (changedIntermediate .f1) +
      countWhere allInputs (changedIntermediate .f2) + countWhere allInputs (changedIntermediate .f3)) = 64 := by decide

def variants : List Nat := [0, 1, 2, 3, 4, 5]
def evaluateVariant (variant : Nat) (family : Family) (x : FieldBits) : Output :=
  reference family (if variant = 5 then exchangeSubjectDaxContextPel x else x)
/- Stable wire surface for the parent CLI: all 768 transformed reference rows. -/
def evaluatorRows : List (Nat × Family × FieldBits × Output) :=
  variants.flatMap fun variant => allOriginalCases.map fun p =>
    (variant, p.1, p.2, evaluateVariant variant p.1 p.2)
def censusRequests : List (Nat × Nat × Family × FieldBits × Output) :=
  [0, 1, 2].flatMap fun arm => evaluatorRows.map fun row => (arm, row.1, row.2.1, row.2.2.1, row.2.2.2)
def sentinelRequestIndices : List (Nat × Nat × Nat) :=
  (List.range 20).flatMap fun repetition =>
    (List.range 8).flatMap fun sentinel =>
      (List.range 3).map fun arm => (repetition, sentinel, arm)
theorem evaluator_rows_count : evaluatorRows.length = 768 := by
  simp only [evaluatorRows, List.length_flatMap, List.length_map]
  simp [variants, all_original_cases_length]
theorem census_requests_count : censusRequests.length = 2304 := by
  simp only [censusRequests, List.length_flatMap, List.length_map]
  simp [evaluator_rows_count]
theorem sentinel_requests_count : sentinelRequestIndices.length = 480 := by
  simp only [sentinelRequestIndices, List.length_flatMap, List.length_map, List.length_range]
  decide
theorem schedule_cardinality : censusRequests.length + sentinelRequestIndices.length = 2784 := by
  rw [census_requests_count, sentinel_requests_count]

end HSWMFullW1Reference
