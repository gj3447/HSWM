import HSWMLocalPermitCommit

/-!
# HSWM verified admission kernel

This module puts the pure, executable admission decision behind one explicit
boundary.  The kernel itself decides only the local linear-journal transition
specified in `HSWMLocalPermitCommit`.  Its three adapter facts are supplied by
the surrounding runtime: signature/envelope verification, verification-time
checking, and exact recovered-state-byte checking.

Consequently, these theorems establish what an accepted *kernel decision*
means, conditional on those facts.  They do not establish that Node, Effect,
Ed25519, a clock, a byte codec, or a filesystem produced truthful facts, nor
do they give an arbitrary TypeScript process an unforgeable capability.
-/

namespace HSWM.CanonicalLearning.VerifiedAdmissionKernel

open LocalPermitCommit
open AtomicAdmission
open CanonicalPermitEnvelope

def verifiedAdmissionKernelContractVersion : String :=
  "hswm-verified-admission-kernel/v1"

/-! ## Explicit trusted-adapter input -/

/--
The executable outputs of the three runtime adapters.  They are deliberately
separate from the record: a proof can show that admission requires `true`, but
the adapters' real-world soundness remains part of the trusted boundary.
-/
structure VerifiedAdmissionAdapterFacts where
  permitEnvelopeAccepted : Bool
  verificationTimeAccepted : Bool
  stateBytesAccepted : Bool
deriving Repr, DecidableEq

/-- Complete structured input to the pure admission kernel. -/
structure VerifiedAdmissionRequest where
  state : LocalPermitCommitState
  record : LocalPermitCommitRecord
  adapterFacts : VerifiedAdmissionAdapterFacts
deriving Repr, DecidableEq

/--
The part of recovered local state that admission conditions actually inspect.
Historical records are still retained by the durable model, but a recovery
receipt that only exposes a current head and consumed-nonce set can be used
only through this explicit projection.
-/
structure RecoveredAdmissionView where
  head : Option HeadSnapshot
  consumedNonces : List NonceDigest
deriving Repr, DecidableEq

def RecoveredAdmissionView.ofState (state : LocalPermitCommitState) : RecoveredAdmissionView :=
  { head := state.head, consumedNonces := state.consumedNonces }

def RecoveredAdmissionView.asState (view : RecoveredAdmissionView) : LocalPermitCommitState :=
  { head := view.head, consumedNonces := view.consumedNonces, records := [] }

def advanceRecoveredAdmissionView
    (view : RecoveredAdmissionView)
    (command : LocalPermitCommitCommand) : RecoveredAdmissionView :=
  RecoveredAdmissionView.ofState (advanceLocalPermitCommit view.asState command)

/--
Records do not appear in `LocalPermitCommitConditions`; this theorem is the
explicit justification for evaluating a recovery view with `records := []`.
It does *not* say that the historical record list was recovered or durable.
-/
theorem localPermitCommitConditionsDependOnlyOnRecoveredView
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) :
    LocalPermitCommitConditions state command ↔
      LocalPermitCommitConditions (RecoveredAdmissionView.ofState state).asState command := by
  simp [LocalPermitCommitConditions, RecoveredAdmissionView.ofState,
    RecoveredAdmissionView.asState]

theorem advanceRecoveredAdmissionViewSimulatesFullState
    (state : LocalPermitCommitState)
    (command : LocalPermitCommitCommand) :
    RecoveredAdmissionView.ofState (advanceLocalPermitCommit state command) =
      advanceRecoveredAdmissionView (RecoveredAdmissionView.ofState state) command := by
  simp [RecoveredAdmissionView.ofState, RecoveredAdmissionView.asState,
    advanceRecoveredAdmissionView, advanceLocalPermitCommit]

def VerifiedAdmissionRequest.toLocalCommand
    (request : VerifiedAdmissionRequest) : LocalPermitCommitCommand :=
  { record := request.record
    permitEnvelopeAccepted := request.adapterFacts.permitEnvelopeAccepted
    verificationTimeAccepted := request.adapterFacts.verificationTimeAccepted
    stateBytesAccepted := request.adapterFacts.stateBytesAccepted }

/-- A kernel decision either carries its exact successor or names rejection. -/
inductive VerifiedAdmissionDecision where
  | accepted (next : LocalPermitCommitState)
  | rejected (reason : LocalPermitCommitRejection)
deriving Repr, DecidableEq

/--
The total executable decision procedure.  No runtime effect occurs here; a
storage adapter must treat an `accepted` decision as a request for the exact
successor shown, rather than as proof that it has been durably committed.
-/
def verifiedAdmissionKernel
    (request : VerifiedAdmissionRequest) : VerifiedAdmissionDecision :=
  match localPermitCommit request.state request.toLocalCommand with
  | .ok next => .accepted next
  | .error reason => .rejected reason

def VerifiedAdmissionAccepted
    (request : VerifiedAdmissionRequest)
    (next : LocalPermitCommitState) : Prop :=
  verifiedAdmissionKernel request = .accepted next

/-! ## Kernel theorems -/

theorem verifiedAdmissionKernelAcceptedIff
    (request : VerifiedAdmissionRequest) :
    VerifiedAdmissionAccepted request
        (advanceLocalPermitCommit request.state request.toLocalCommand) ↔
      LocalPermitCommitConditions request.state request.toLocalCommand := by
  constructor
  · intro accepted
    unfold VerifiedAdmissionAccepted verifiedAdmissionKernel at accepted
    cases committed : localPermitCommit request.state request.toLocalCommand with
    | ok next =>
        simp only [committed] at accepted
        cases accepted
        exact (localPermitCommitAcceptedIff request.state request.toLocalCommand).mp committed
    | error reason =>
        simp only [committed] at accepted
        nomatch accepted
  · intro conditions
    have committed :
        localPermitCommit request.state request.toLocalCommand =
          .ok (advanceLocalPermitCommit request.state request.toLocalCommand) :=
      (localPermitCommitAcceptedIff request.state request.toLocalCommand).mpr conditions
    unfold VerifiedAdmissionAccepted verifiedAdmissionKernel
    simp [committed]

/-- Soundness: every accepted decision is exactly a model transition. -/
theorem verifiedAdmissionKernelSound
    (accepted : VerifiedAdmissionAccepted request next) :
    localPermitCommit request.state request.toLocalCommand = .ok next := by
  unfold VerifiedAdmissionAccepted verifiedAdmissionKernel at accepted
  cases committed : localPermitCommit request.state request.toLocalCommand with
  | ok actualNext =>
      simp only [committed] at accepted
      cases accepted
      rfl
  | error reason =>
      simp only [committed] at accepted
      contradiction

/-- Completeness: every model transition becomes an accepted decision. -/
theorem verifiedAdmissionKernelComplete
    (accepted : localPermitCommit request.state request.toLocalCommand = .ok next) :
    VerifiedAdmissionAccepted request next := by
  unfold VerifiedAdmissionAccepted verifiedAdmissionKernel
  simp [accepted]

/-- An accepted decision carries the deterministic successor, not an arbitrary state. -/
theorem verifiedAdmissionKernelAcceptedNextIsAdvance
    (accepted : VerifiedAdmissionAccepted request next) :
    next = advanceLocalPermitCommit request.state request.toLocalCommand := by
  have committed := verifiedAdmissionKernelSound accepted
  unfold localPermitCommit at committed
  split at committed
  · rename_i conditions
    cases committed
    rfl
  · contradiction

/-- An accepted decision requires all three supplied adapter facts to be true. -/
theorem verifiedAdmissionKernelRequiresForeignChecks
    (accepted : VerifiedAdmissionAccepted request next) :
    request.adapterFacts.permitEnvelopeAccepted = true ∧
    request.adapterFacts.verificationTimeAccepted = true ∧
    request.adapterFacts.stateBytesAccepted = true := by
  have nextIsAdvance := verifiedAdmissionKernelAcceptedNextIsAdvance accepted
  subst next
  have localAccepted :
      localPermitCommit request.state request.toLocalCommand =
        .ok (advanceLocalPermitCommit request.state request.toLocalCommand) :=
    verifiedAdmissionKernelSound accepted
  simpa [VerifiedAdmissionRequest.toLocalCommand] using
    (acceptedLocalCommitRequiresForeignChecks localAccepted)

/-- An accepted decision publishes precisely the declared successor. -/
theorem verifiedAdmissionKernelPublishesExactSuccessor
    (accepted : VerifiedAdmissionAccepted request next) :
    next.head = some request.record.expectedNextHead := by
  simpa [VerifiedAdmissionRequest.toLocalCommand] using
    (acceptedLocalCommitPublishesExactSuccessor
      (verifiedAdmissionKernelSound accepted))

/-- An accepted decision consumes the request nonce. -/
theorem verifiedAdmissionKernelConsumesNonce
    (accepted : VerifiedAdmissionAccepted request next) :
    request.record.nonceDigest ∈ next.consumedNonces := by
  simpa [VerifiedAdmissionRequest.toLocalCommand] using
    (acceptedLocalCommitConsumesNonce
      (verifiedAdmissionKernelSound accepted))

/-- Replaying the same request after its admitted successor is rejected. -/
theorem verifiedAdmissionKernelRejectsSameNonceReplay
    (request : VerifiedAdmissionRequest) :
    verifiedAdmissionKernel
        { request with state :=
          advanceLocalPermitCommit request.state request.toLocalCommand } =
      .rejected .conditionsRejected := by
  unfold verifiedAdmissionKernel
  simp only [VerifiedAdmissionRequest.toLocalCommand]
  rw [advancedLocalCommitRejectsSameNonceReplay]

/-- Acceptance refines the bounded linear-journal model, no more and no less. -/
theorem verifiedAdmissionKernelYieldsBoundedRefinement
    (accepted : VerifiedAdmissionAccepted request next) :
    LocalPermitCommitRefinesLinearJournal
      request.state request.toLocalCommand next := by
  apply acceptedLocalCommitYieldsBoundedRefinement
  exact verifiedAdmissionKernelSound accepted

end HSWM.CanonicalLearning.VerifiedAdmissionKernel
