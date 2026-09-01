import HSWMVerifiedAdmissionWire

/-!
# HSWM persisted verified-admission entry boundary

This module formalizes a decoded entry which a future durable adapter may
persist after a verified-admission decision.  `Persisted` is only a name for
the supplied decoded entry and its intended recovery prefix: it does not
assert a filesystem write, fsync, crash recovery, SHA-256 binding, POSIX
atomicity, TypeScript/Effect refinement, or any byte-level serialization
fact.  In particular, this is not a pre-commit full-execution-certificate
gate: a complete execution certificate is necessarily assembled after the
commit and recovery it describes.

The positive result is deliberately local.  When the pure checker accepts an
entry, its response has the exact stored request, that request has the exact
stored local record, and its successor is the recovered view of the same
local model transition from the supplied recovery prefix.
-/

namespace HSWM.CanonicalLearning.PersistedVerifiedAdmission

open AtomicAdmission
open CanonicalPermitEnvelope
open LocalPermitCommit
open VerifiedAdmissionKernel
open VerifiedAdmissionWire

def persistedVerifiedAdmissionContractVersion : String :=
  "hswm-verified-admission-commit/v2"

def persistedVerifiedAdmissionStatus : String :=
  "LOCAL_POSIX_ATOMIC_NO_REPLACE_EXACT_PERSISTED_VERIFIED_ADMISSION_WIRE_DECISION_RECOVERY_REVALIDATED_V2_PROCESS_CRASH_NOT_TESTED_CALLER_RELATIVE_PUBLIC_TRUST_AND_TIME_NAMESPACE_LOCAL_NONCE_AND_HEAD_NOT_GLOBAL_NOT_AUTHORITATIVE_NOT_DISTRIBUTED_NOT_TRUSTED_TIME_NOT_PRIVATE_ISSUER_RECOVERY_NOT_POWER_LOSS_NOT_LEAN_REFINEMENT"

/--
One supplied decoded entry and its record projection.  The record is retained
separately so a checker can fail closed if a response/request is paired with a
different locally retained record.
-/
structure PersistedVerifiedAdmissionEntry where
  request : VerifiedAdmissionWireRequest
  response : VerifiedAdmissionWireResponse
  localRecord : LocalPermitCommitRecord
deriving Repr, DecidableEq

/--
Pure exactness checker over a supplied recovery prefix.  It does not inspect
the historical record list except through the recovered view; the explicit
simulation theorem below is what reconnects an accepted entry to that full
local prefix.
-/
def persistedVerifiedAdmissionAccepted
    (recoveryPrefix : LocalPermitCommitState)
    (entry : PersistedVerifiedAdmissionEntry) : Bool :=
  decide (entry.request.view = RecoveredAdmissionView.ofState recoveryPrefix) &&
  (decide (entry.request.record = entry.localRecord) &&
  match verifiedAdmissionKernel entry.request.toKernelRequest with
  | .accepted next =>
      decide (entry.response =
        .accepted entry.request (RecoveredAdmissionView.ofState next))
  | .rejected _ => false)

/-- Extract the exact kernel decision and the two stored bindings from acceptance. -/
theorem acceptedPersistedEntryProjectsExactKernelDecision
    (accepted : persistedVerifiedAdmissionAccepted recoveryPrefix entry = true) :
    entry.request.view = RecoveredAdmissionView.ofState recoveryPrefix ∧
    entry.request.record = entry.localRecord ∧
    ∃ next, VerifiedAdmissionAccepted entry.request.toKernelRequest next ∧
      entry.response = .accepted entry.request (RecoveredAdmissionView.ofState next) := by
  unfold persistedVerifiedAdmissionAccepted at accepted
  simp only [Bool.and_eq_true, decide_eq_true_eq] at accepted
  rcases accepted with ⟨sameView, sameRecord, responseAccepted⟩
  cases decision : verifiedAdmissionKernel entry.request.toKernelRequest with
  | accepted next =>
      simp only [decision, decide_eq_true_eq] at responseAccepted
      exact ⟨sameView, sameRecord, next, decision, responseAccepted⟩
  | rejected reason =>
      simp only [decision, Bool.false_eq_true] at responseAccepted

/--
The decoded accepted response is exactly the recovered successor of the same
full local prefix, not merely of the view with an empty history projection.
-/
theorem acceptedPersistedEntryResponseIsExactRecoveredSuccessor
    (accepted : persistedVerifiedAdmissionAccepted recoveryPrefix entry = true) :
    entry.response = .accepted entry.request
      (RecoveredAdmissionView.ofState
        (advanceLocalPermitCommit recoveryPrefix
          entry.request.toKernelRequest.toLocalCommand)) := by
  rcases acceptedPersistedEntryProjectsExactKernelDecision accepted with
    ⟨sameView, _, next, kernelAccepted, responseExact⟩
  rw [responseExact, verifiedAdmissionKernelAcceptedNextIsAdvance kernelAccepted]
  congr 1
  calc
    RecoveredAdmissionView.ofState
        (advanceLocalPermitCommit entry.request.toKernelRequest.state
          entry.request.toKernelRequest.toLocalCommand) =
        advanceRecoveredAdmissionView
          (RecoveredAdmissionView.ofState entry.request.toKernelRequest.state)
          entry.request.toKernelRequest.toLocalCommand :=
      advanceRecoveredAdmissionViewSimulatesFullState _ _
    _ = advanceRecoveredAdmissionView
          (RecoveredAdmissionView.ofState recoveryPrefix)
          entry.request.toKernelRequest.toLocalCommand := by
      change advanceRecoveredAdmissionView entry.request.view _ =
        advanceRecoveredAdmissionView (RecoveredAdmissionView.ofState recoveryPrefix) _
      rw [sameView]
    _ = RecoveredAdmissionView.ofState
          (advanceLocalPermitCommit recoveryPrefix
            entry.request.toKernelRequest.toLocalCommand) :=
      (advanceRecoveredAdmissionViewSimulatesFullState recoveryPrefix _).symm

/-- The same accepted entry is an exact successful full local-model transition. -/
theorem acceptedPersistedEntrySimulatesFullLocalCommit
    (accepted : persistedVerifiedAdmissionAccepted recoveryPrefix entry = true) :
    localPermitCommit recoveryPrefix entry.request.toKernelRequest.toLocalCommand =
      .ok (advanceLocalPermitCommit recoveryPrefix
        entry.request.toKernelRequest.toLocalCommand) := by
  rcases acceptedPersistedEntryProjectsExactKernelDecision accepted with
    ⟨sameView, _, next, kernelAccepted, _⟩
  have viewAccepted := verifiedAdmissionKernelSound kernelAccepted
  rw [verifiedAdmissionKernelAcceptedNextIsAdvance kernelAccepted] at viewAccepted
  have viewConditions : LocalPermitCommitConditions
      entry.request.toKernelRequest.state entry.request.toKernelRequest.toLocalCommand :=
    (localPermitCommitAcceptedIff entry.request.toKernelRequest.state
      entry.request.toKernelRequest.toLocalCommand).mp viewAccepted
  have fullConditions : LocalPermitCommitConditions recoveryPrefix
      entry.request.toKernelRequest.toLocalCommand := by
    apply (localPermitCommitConditionsDependOnlyOnRecoveredView recoveryPrefix _).mpr
    simpa [VerifiedAdmissionWireRequest.toKernelRequest, sameView] using viewConditions
  exact (localPermitCommitAcceptedIff recoveryPrefix
    entry.request.toKernelRequest.toLocalCommand).mpr fullConditions

/-- Acceptance projects the response request and separately retained local record exactly. -/
theorem acceptedPersistedEntryBindsExactRequestAndLocalRecord
    (accepted : persistedVerifiedAdmissionAccepted recoveryPrefix entry = true) :
    entry.request.record = entry.localRecord ∧
    ∃ successor, entry.response = .accepted entry.request successor := by
  rcases acceptedPersistedEntryProjectsExactKernelDecision accepted with
    ⟨_, sameRecord, next, _, responseExact⟩
  exact ⟨sameRecord, RecoveredAdmissionView.ofState next, responseExact⟩

/-- Acceptance records the exact request nonce in the recovered successor. -/
theorem acceptedPersistedEntryConsumesExactNonce
    (accepted : persistedVerifiedAdmissionAccepted recoveryPrefix entry = true) :
    entry.request.record.nonceDigest ∈
      (advanceLocalPermitCommit recoveryPrefix
        entry.request.toKernelRequest.toLocalCommand).consumedNonces := by
  exact acceptedLocalCommitConsumesNonce
    (acceptedPersistedEntrySimulatesFullLocalCommit accepted)

/-- Acceptance advances the exact recovered head to the declared successor. -/
theorem acceptedPersistedEntryAdvancesExactHead
    (accepted : persistedVerifiedAdmissionAccepted recoveryPrefix entry = true) :
    (advanceLocalPermitCommit recoveryPrefix
      entry.request.toKernelRequest.toLocalCommand).head =
      some entry.localRecord.expectedNextHead := by
  have sameRecord :=
    (acceptedPersistedEntryProjectsExactKernelDecision accepted).2.1
  rw [← sameRecord]
  exact acceptedLocalCommitPublishesExactSuccessor
    (acceptedPersistedEntrySimulatesFullLocalCommit accepted)

/-- A response not equal to the computed exact accepted response fails closed. -/
theorem wrongStoredResponseCannotBeAccepted
    (wrong : entry.response ≠ .accepted entry.request
      (RecoveredAdmissionView.ofState
        (advanceLocalPermitCommit recoveryPrefix
          entry.request.toKernelRequest.toLocalCommand))) :
    persistedVerifiedAdmissionAccepted recoveryPrefix entry ≠ true := by
  intro accepted
  exact wrong (acceptedPersistedEntryResponseIsExactRecoveredSuccessor accepted)

/-- A stored request paired with the wrong recovered prefix fails closed. -/
theorem wrongStoredRequestViewCannotBeAccepted
    (wrong : entry.request.view ≠ RecoveredAdmissionView.ofState recoveryPrefix) :
    persistedVerifiedAdmissionAccepted recoveryPrefix entry ≠ true := by
  intro accepted
  exact wrong (acceptedPersistedEntryProjectsExactKernelDecision accepted).1

/-- A request paired with a substituted local record fails closed. -/
theorem wrongStoredLocalRecordCannotBeAccepted
    (wrong : entry.request.record ≠ entry.localRecord) :
    persistedVerifiedAdmissionAccepted recoveryPrefix entry ≠ true := by
  intro accepted
  exact wrong (acceptedPersistedEntryProjectsExactKernelDecision accepted).2.1

end HSWM.CanonicalLearning.PersistedVerifiedAdmission
