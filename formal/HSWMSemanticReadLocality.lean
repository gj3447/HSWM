import HSWMSemanticLifecycleRefinement

/-!
# Graph-local semantic reads

`HSWMSemanticLifecycleRefinement.Frame` is a normalized runtime projection. Its
`frameSha256` is an opaque claimed digest and `stateRevision` is global metadata:
either can change after an unrelated graph write. This file proves locality for
the invocation payload, rather than equality of those whole runtime frames.

This read-plan component is built from one selected relation, its ordered pinned role keys,
and bodies resolved at exactly those keys. It includes the complete semantic
payload (including ordered exception references) and fails closed when an
exception has no exact exception-role path or a requested pinned body is
missing. A fixed interpreter may be applied afterwards; arbitrary LLM
determinism, truth, calibration, and benefit are not assumed. This is not a
refinement of the entire runtime request: expanded prior trace/outcome content,
global metadata, the prompt wrapper, and autonomous task-to-plan selection
require their own bindings before making a full-request locality claim.
-/

namespace HSWM.SemanticReadLocality

open HSWM.SemanticLifecycleRefinement

structure RoleResolvedBody where
  key : Key
  owner : String
  contentSha256 : String
  contentUtf8 : String
deriving Repr, DecidableEq

abbrev GraphStore := Key → Option RoleResolvedBody

structure ResolvedRole where
  referenceType : String
  role : String
  body : RoleResolvedBody
deriving Repr, DecidableEq

/-- Graph-dependent content sent to the local operator. `event` is a task
input; global state revision and opaque whole-frame hash are intentionally not
treated as local graph content. -/
structure LocalInvocationPayload where
  event : String
  relationKey : Key
  owner : String
  semantic : SemanticPayload
  roles : List ResolvedRole
deriving Repr, DecidableEq

def resolves (role : OrderedRole) (body : RoleResolvedBody) : Bool :=
  body.key = role.key && body.owner = role.owner && body.contentSha256 = role.contentSha256

/-- Resolve exact pinned references, preserving incidence order. -/
def resolveRoles (store : GraphStore) : List OrderedRole → Option (List ResolvedRole)
  | [] => some []
  | role :: rest => do
    let body ← store role.key
    if resolves role body then
      let resolved ← resolveRoles store rest
      some ({ referenceType := role.referenceType, role := role.role, body } :: resolved)
    else none

def exceptionRoleMatches (role : OrderedRole) (exceptionRef : String) : Bool :=
  role.role = "exception" && role.key.atomUid = exceptionRef

/-- Every declared exception must name a pinned `exception` role. -/
def exceptionRefsBound (roles : List OrderedRole) : List String → Bool
  | [] => true
  | exceptionRef :: rest =>
    roles.any (fun role => exceptionRoleMatches role exceptionRef) &&
      exceptionRefsBound roles rest

def readPlan (store : GraphStore) (event : String) (relation : Relation) :
    Option LocalInvocationPayload :=
  if exceptionRefsBound relation.roles relation.semantic.exceptionRefs then
    match resolveRoles store relation.roles with
    | some roles => some (LocalInvocationPayload.mk event relation.key relation.owner
        relation.semantic roles)
    | none => none
  else none

/-- The stores agree only on this relation's role-key read set; all other
global graph atoms may differ. -/
def StoresAgreeOn (left right : GraphStore) : List OrderedRole → Prop
  | [] => True
  | role :: rest => left role.key = right role.key ∧ StoresAgreeOn left right rest

theorem resolveRoles_locality (left right : GraphStore) (roles : List OrderedRole)
    (agreement : StoresAgreeOn left right roles) :
    resolveRoles left roles = resolveRoles right roles := by
  induction roles generalizing left right with
  | nil => rfl
  | cons role rest inductionHypothesis =>
    rcases agreement with ⟨head, tail⟩
    cases found : right role.key with
    | none => simp [resolveRoles, head, found]
    | some body =>
      by_cases valid : resolves role body = true
      · simp [resolveRoles, head, found, valid,
          inductionHypothesis left right tail]
      · simp [resolveRoles, head, found, valid]

/-- **Frame law.** Same selected relation and event plus equality of every
selected role body's value gives the same invocation payload. It deliberately
does not claim that full frames match if global metadata differs. -/
theorem readPlan_locality (left right : GraphStore) (event : String) (relation : Relation)
    (agreement : StoresAgreeOn left right relation.roles) :
    readPlan left event relation = readPlan right event relation := by
  unfold readPlan
  split <;> simp only [resolveRoles_locality left right relation.roles agreement]

theorem readPlan_fails_when_exception_path_is_absent
    (store : GraphStore) (event : String) (relation : Relation)
    (unbound : exceptionRefsBound relation.roles relation.semantic.exceptionRefs = false) :
    readPlan store event relation = none := by
  unfold readPlan
  rw [unbound]
  simp

theorem readPlan_fails_when_pinned_role_is_missing
    (store : GraphStore) (event : String) (relation : Relation) (role : OrderedRole)
    (tail : List OrderedRole)
    (exceptionsBound : exceptionRefsBound relation.roles relation.semantic.exceptionRefs = true)
    (roles : relation.roles = role :: tail) (missing : store role.key = none) :
    readPlan store event relation = none := by
  unfold readPlan
  rw [roles]
  rw [roles] at exceptionsBound
  rw [exceptionsBound]
  simp [resolveRoles, missing]

abbrev SpecifiedInterpreter (Output : Type) := LocalInvocationPayload → Output

theorem equal_local_payload_gives_equal_specified_invocation {Output : Type}
    (interpreter : SpecifiedInterpreter Output) (left right : LocalInvocationPayload)
    (same : left = right) : interpreter left = interpreter right := by
  cases same
  rfl

/-- String/key witnesses use the same schema as the actual decoded wire. -/
def sampleKey (atomUid : String) : Key :=
  { schemaVersion := "v2", lineageId := "lineage", atomUid, revisionId := 1 }

def sampleRole (name atomUid : String) : OrderedRole :=
  { referenceType := "uses", role := name, key := sampleKey atomUid,
    owner := "owner", contentSha256 := "sha" ++ atomUid }

def sampleSemantic (exceptions : List String) : SemanticPayload :=
  { semanticText := "semantic", disposition := "predict", uncertainty := "unknown",
    exceptionRefs := exceptions, traceSha256 := none, outcomeSha256 := none,
    revisionEvidenceSha256 := none }

def sampleRelation (exceptions : List String) (roles : List OrderedRole) : Relation :=
  { key := sampleKey "relation", owner := "owner", semantic := sampleSemantic exceptions, roles }

def eraseExceptionRefs (relation : Relation) : Relation :=
  { relation with semantic := { relation.semantic with exceptionRefs := [] } }

def exceptionRoles : List OrderedRole := [sampleRole "exception" "x", sampleRole "exception" "y"]
def exceptionLeft : Relation := sampleRelation ["x"] exceptionRoles
def exceptionRight : Relation := sampleRelation ["y"] exceptionRoles

theorem erasing_exception_references_loses_a_possible_local_distinction :
    eraseExceptionRefs exceptionLeft = eraseExceptionRefs exceptionRight ∧
    (sampleSemantic ["x"]).exceptionRefs.headD "" ≠
      (sampleSemantic ["y"]).exceptionRefs.headD "" := by
  decide

def orderedLeft : List OrderedRole := [sampleRole "subject" "a", sampleRole "context" "b"]
def orderedRight : List OrderedRole := [sampleRole "context" "b", sampleRole "subject" "a"]

def firstRoleAtomUid (roles : List OrderedRole) : String :=
  (roles.map (fun role => role.key.atomUid)).headD ""

theorem role_order_is_observable_by_a_local_read :
    firstRoleAtomUid orderedLeft ≠ firstRoleAtomUid orderedRight := by
  decide

end HSWM.SemanticReadLocality
