import Std

/-!
# Post-run semantic-lifecycle structural witness

This is a checker for the actual shape used by the TypeScript semantic
lifecycle: a role-bearing canonical relation is read, a trace-bound outcome
produces its immutable next revision, and a later trace reads that revision.
It is deliberately a *post-run witness*, not an admission capability and not
a claim that a SHA string hashes supplied bytes, that JSON was parsed by the
runtime, that a journal survived a crash, or that an LLM output is meaningful.
Those facts must be checked by the adapter before it emits this decoded wire.
-/

namespace HSWM.SemanticLifecycleRefinement

def semanticLifecyclePostRunContractVersion : String :=
  "hswm-semantic-lifecycle-postrun/v1"

structure Key where
  schemaVersion : String
  lineageId : String
  atomUid : String
  revisionId : Nat
deriving Repr, DecidableEq

structure OrderedRole where
  referenceType : String
  role : String
  key : Key
  owner : String
  contentSha256 : String
deriving Repr, DecidableEq

structure SemanticPayload where
  semanticText : String
  disposition : String
  uncertainty : String
  /-- Ordered, exact references: this is not a set. -/
  exceptionRefs : List String
  traceSha256 : Option String
  outcomeSha256 : Option String
  revisionEvidenceSha256 : Option String
deriving Repr, DecidableEq

structure Relation where
  key : Key
  owner : String
  semantic : SemanticPayload
  /-- Ordered role incidence, including type and pinned target revision. -/
  roles : List OrderedRole
deriving Repr, DecidableEq

structure StateView where
  stateRevision : Nat
  relation : Relation
deriving Repr, DecidableEq

structure Frame where
  event : String
  stateRevision : Nat
  relationKey : Key
  owner : String
  semantic : SemanticPayload
  roles : List OrderedRole
  /-- Opaque claimed digest; byte-level hash checking is outside this file. -/
  frameSha256 : String
deriving Repr, DecidableEq

structure Trace where
  traceSha256 : String
  frameSha256 : String
  relationKey : Key
  predictionSha256 : String
  backendConfigurationSha256 : String
  event : String
deriving Repr, DecidableEq

structure Outcome where
  traceSha256 : String
  predictionSha256 : String
  outcomeSha256 : String
  status : String
deriving Repr, DecidableEq

/-- The normalized revision response and its evidence binding as recovered by
the adapter from actual staged content. -/
structure Revision where
  semanticText : String
  disposition : String
  uncertainty : String
  exceptionRefs : List String
  revisionEvidenceSha256 : String
  traceSha256 : String
  outcomeSha256 : String
  backendConfigurationSha256 : String
deriving Repr, DecidableEq

structure PostRunWire where
  contract : String
  before : StateView
  frame : Frame
  trace : Trace
  outcome : Outcome
  revision : Revision
  after : StateView
  /-- The supersedes target decoded from the actual successor atom. -/
  afterPredecessorKey : Key
  /-- The retained old atom decoded from the selected durable branch. -/
  retainedBefore : Relation
  /-- `true` selects `after`; `false` selects the unchanged baseline. -/
  selectedCandidate : Bool
  nextFrame : Frame
  /-- An observed selected-state execution. This record does not prove wall-clock ordering. -/
  nextTrace : Trace
deriving Repr, DecidableEq

def sameAddress (left right : Key) : Bool :=
  left.schemaVersion = right.schemaVersion &&
  left.lineageId = right.lineageId &&
  left.atomUid = right.atomUid

def frameDescribes (state : StateView) (frame : Frame) : Bool :=
  frame.stateRevision = state.stateRevision &&
  frame.relationKey = state.relation.key &&
  frame.owner = state.relation.owner &&
  frame.semantic = state.relation.semantic &&
  frame.roles = state.relation.roles

def revisionBinds (before after : Relation) (trace : Trace) (outcome : Outcome) : Bool :=
  sameAddress before.key after.key &&
  after.key.revisionId = before.key.revisionId + 1 &&
  after.owner = before.owner &&
  after.roles = before.roles &&
  after.semantic.exceptionRefs = before.semantic.exceptionRefs &&
  after.semantic.traceSha256 = some trace.traceSha256 &&
  after.semantic.outcomeSha256 = some outcome.outcomeSha256 &&
  after.semantic.revisionEvidenceSha256.isSome

def revisionConstructsAfter (revision : Revision) (after : Relation) (trace : Trace)
    (outcome : Outcome) : Bool :=
  after.semantic.semanticText = revision.semanticText &&
  after.semantic.disposition = revision.disposition &&
  after.semantic.uncertainty = revision.uncertainty &&
  after.semantic.exceptionRefs = revision.exceptionRefs &&
  after.semantic.revisionEvidenceSha256 = some revision.revisionEvidenceSha256 &&
  after.semantic.traceSha256 = some revision.traceSha256 &&
  after.semantic.outcomeSha256 = some revision.outcomeSha256 &&
  revision.traceSha256 = trace.traceSha256 &&
  revision.outcomeSha256 = outcome.outcomeSha256 &&
  revision.backendConfigurationSha256 = trace.backendConfigurationSha256

def selectedState (wire : PostRunWire) : StateView :=
  if wire.selectedCandidate then wire.after else wire.before

/-- The single immutable semantic successor prescribed by a decoded revision.
It is structural only: it neither validates source bytes nor interprets LLM text. -/
def semanticSuccessor (before : StateView) (revision : Revision) : StateView :=
  { stateRevision := before.stateRevision + 1
    relation :=
      { key := { schemaVersion := before.relation.key.schemaVersion
                 lineageId := before.relation.key.lineageId
                 atomUid := before.relation.key.atomUid
                 revisionId := before.relation.key.revisionId + 1 }
        owner := before.relation.owner
        semantic := { semanticText := revision.semanticText
                      disposition := revision.disposition
                      uncertainty := revision.uncertainty
                      exceptionRefs := revision.exceptionRefs
                      traceSha256 := some revision.traceSha256
                      outcomeSha256 := some revision.outcomeSha256
                      revisionEvidenceSha256 := some revision.revisionEvidenceSha256 }
        roles := before.relation.roles } }

theorem key_ext (a b : Key)
    (schema : a.schemaVersion = b.schemaVersion) (lineage : a.lineageId = b.lineageId)
    (uid : a.atomUid = b.atomUid) (revision : a.revisionId = b.revisionId) : a = b := by
  cases a; cases b; simp_all

theorem semantic_ext (a b : SemanticPayload)
    (text : a.semanticText = b.semanticText) (disposition : a.disposition = b.disposition)
    (uncertainty : a.uncertainty = b.uncertainty) (exceptions : a.exceptionRefs = b.exceptionRefs)
    (trace : a.traceSha256 = b.traceSha256) (outcome : a.outcomeSha256 = b.outcomeSha256)
    (evidence : a.revisionEvidenceSha256 = b.revisionEvidenceSha256) : a = b := by
  cases a; cases b; simp_all

theorem relation_ext (a b : Relation) (key : a.key = b.key) (owner : a.owner = b.owner)
    (semantic : a.semantic = b.semantic) (roles : a.roles = b.roles) : a = b := by
  cases a; cases b; simp_all

theorem state_ext (a b : StateView) (revision : a.stateRevision = b.stateRevision)
    (relation : a.relation = b.relation) : a = b := by
  cases a; cases b; simp_all

def traceBindsFrame (trace : Trace) (frame : Frame) : Bool :=
  trace.frameSha256 = frame.frameSha256 && trace.relationKey = frame.relationKey &&
  trace.event = frame.event

def outcomeBindsTrace (outcome : Outcome) (trace : Trace) : Bool :=
  outcome.traceSha256 = trace.traceSha256 &&
  outcome.predictionSha256 = trace.predictionSha256 &&
  outcome.status = "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"

/--
The pure post-run structural checker.  Its successful result means exactly the
listed decoded fields agree.  It does not promote any opaque digest, content
byte, provider response, or outcome source to a theorem premise or result.
-/
def postRunAccepted (wire : PostRunWire) : Bool :=
  wire.contract = semanticLifecyclePostRunContractVersion &&
  frameDescribes wire.before wire.frame &&
  traceBindsFrame wire.trace wire.frame &&
  outcomeBindsTrace wire.outcome wire.trace &&
  revisionBinds wire.before.relation wire.after.relation wire.trace wire.outcome &&
  revisionConstructsAfter wire.revision wire.after.relation wire.trace wire.outcome &&
  wire.after.stateRevision = wire.before.stateRevision + 1 &&
  wire.afterPredecessorKey = wire.before.relation.key &&
  wire.retainedBefore = wire.before.relation &&
  frameDescribes (selectedState wire) wire.nextFrame &&
  traceBindsFrame wire.nextTrace wire.nextFrame &&
  wire.nextTrace.backendConfigurationSha256 = wire.trace.backendConfigurationSha256

theorem postRunAccepted_iff : postRunAccepted wire = true ↔
    wire.contract = semanticLifecyclePostRunContractVersion ∧
    frameDescribes wire.before wire.frame = true ∧
    traceBindsFrame wire.trace wire.frame = true ∧
    outcomeBindsTrace wire.outcome wire.trace = true ∧
    revisionBinds wire.before.relation wire.after.relation wire.trace wire.outcome = true ∧
    revisionConstructsAfter wire.revision wire.after.relation wire.trace wire.outcome = true ∧
    wire.after.stateRevision = wire.before.stateRevision + 1 ∧
    wire.afterPredecessorKey = wire.before.relation.key ∧
    wire.retainedBefore = wire.before.relation ∧
    frameDescribes (selectedState wire) wire.nextFrame = true ∧
    traceBindsFrame wire.nextTrace wire.nextFrame = true ∧
    wire.nextTrace.backendConfigurationSha256 = wire.trace.backendConfigurationSha256 := by
  simp [postRunAccepted, Bool.and_eq_true, decide_eq_true_eq, and_assoc]

theorem accepted_projects_exact_revision_binding
    (accepted : postRunAccepted wire = true) :
    revisionBinds wire.before.relation wire.after.relation wire.trace wire.outcome = true := by
  rcases postRunAccepted_iff.mp accepted with ⟨_, _, _, _, bound, _, _, _, _, _, _, _⟩
  exact bound

theorem accepted_after_eq_semanticSuccessor
    (accepted : postRunAccepted wire = true) :
    wire.after = semanticSuccessor wire.before wire.revision := by
  rcases postRunAccepted_iff.mp accepted with
    ⟨_, _, _, _, binding, constructed, stateIncrement, _, _, _, _, _⟩
  simp only [revisionBinds, revisionConstructsAfter, Bool.and_eq_true,
    decide_eq_true_eq] at binding constructed
  apply state_ext
  · simpa [semanticSuccessor] using stateIncrement
  · apply relation_ext
    · apply key_ext
      · have h := binding.1.1.1.1.1.1.1
        simp [sameAddress, Bool.and_eq_true, decide_eq_true_eq] at h
        exact h.1.1.symm
      · have h := binding.1.1.1.1.1.1.1
        simp [sameAddress, Bool.and_eq_true, decide_eq_true_eq] at h
        exact h.1.2.symm
      · have h := binding.1.1.1.1.1.1.1
        simp [sameAddress, Bool.and_eq_true, decide_eq_true_eq] at h
        exact h.2.symm
      · simpa [semanticSuccessor] using binding.1.1.1.1.1.1.2
    · simpa [semanticSuccessor] using binding.1.1.1.1.1.2
    · apply semantic_ext
      · simpa [semanticSuccessor] using constructed.1.1.1.1.1.1.1.1.1
      · simpa [semanticSuccessor] using constructed.1.1.1.1.1.1.1.1.2
      · simpa [semanticSuccessor] using constructed.1.1.1.1.1.1.1.2
      · simpa [semanticSuccessor] using constructed.1.1.1.1.1.1.2
      · simpa [semanticSuccessor] using constructed.1.1.1.1.right
      · simpa [semanticSuccessor] using constructed.1.1.1.right
      · simpa [semanticSuccessor] using constructed.1.1.1.1.1.right
    · simpa [semanticSuccessor] using binding.1.1.1.1.2


theorem accepted_projects_next_trace_reads_selected_state
    (accepted : postRunAccepted wire = true) :
    wire.nextTrace.relationKey = (selectedState wire).relation.key := by
  rcases postRunAccepted_iff.mp accepted with ⟨_, _, _, _, _, _, _, _, _, frame, trace, _⟩
  simp only [traceBindsFrame, Bool.and_eq_true, decide_eq_true_eq] at trace
  simp only [frameDescribes, Bool.and_eq_true, decide_eq_true_eq] at frame
  exact trace.1.2.trans frame.1.1.1.right

theorem accepted_preserves_ordered_roles
    (accepted : postRunAccepted wire = true) :
    wire.after.relation.roles = wire.before.relation.roles := by
  have bound := accepted_projects_exact_revision_binding accepted
  simp only [revisionBinds, Bool.and_eq_true, decide_eq_true_eq] at bound
  exact bound.1.1.1.1.2

theorem accepted_preserves_ordered_exceptions
    (accepted : postRunAccepted wire = true) :
    wire.after.relation.semantic.exceptionRefs = wire.before.relation.semantic.exceptionRefs := by
  have bound := accepted_projects_exact_revision_binding accepted
  simp only [revisionBinds, Bool.and_eq_true, decide_eq_true_eq] at bound
  exact bound.1.1.1.2

theorem accepted_retains_exact_predecessor
    (accepted : postRunAccepted wire = true) :
    wire.afterPredecessorKey = wire.before.relation.key ∧
    wire.retainedBefore = wire.before.relation := by
  rcases postRunAccepted_iff.mp accepted with ⟨_, _, _, _, _, _, _, predecessor, retained, _, _, _⟩
  exact ⟨predecessor, retained⟩

theorem changed_trace_cannot_be_accepted (wire : PostRunWire) (outcome : Outcome)
    (changed : outcome.traceSha256 ≠ wire.trace.traceSha256) :
    postRunAccepted { wire with outcome := outcome } ≠ true := by
  intro accepted
  rcases postRunAccepted_iff.mp accepted with ⟨_, _, _, bound, _, _, _, _, _, _, _, _⟩
  simp only [outcomeBindsTrace, Bool.and_eq_true, decide_eq_true_eq] at bound
  exact changed bound.1.1

end HSWM.SemanticLifecycleRefinement
