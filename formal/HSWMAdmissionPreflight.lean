import HSWMVerifiedAdmissionKernel

/-!
# HSWM admission preflight

This module computes the three facts consumed by the local admission kernel
from one decoded preflight.  It does not model JSON parsing, SHA-256, Ed25519,
key/trust policy, or a wall clock.  Those foreign operations are represented by
the already-successful verifier projection and observed byte digests supplied at
this boundary.  The executable checks below bind that projection to the exact
local record and recovered view; they do not turn the projection into a proof
that a native verifier was sound.
-/

namespace HSWM.CanonicalLearning.AdmissionPreflight

open AtomicAdmission
open CanonicalPermitEnvelope
open LocalPermitCommit
open VerifiedAdmissionKernel

def admissionPreflightContractVersion : String :=
  "hswm-admission-preflight/v1"

def maxObservedStateBytes : Nat := 1048576

/-- Digest and length observed by the surrounding bounded byte reader. -/
structure ObservedStateBytes where
  byteLength : Nat
  sha256 : StateDigest
deriving Repr, DecidableEq

/--
Projection produced only after the native permit verifier has accepted its
canonical envelope, caller-relative trust snapshot, and supplied verification
time.  It deliberately contains no `Bool` standing for that success.
-/
structure VerifiedPermitProjection where
  envelopeDigest : EvidenceDigest
  checkedAt : String
  executionIntentDigest : EvidenceDigest
  nonceDigest : NonceDigest
  priorHead : HeadSnapshot
  expectedNextHead : HeadSnapshot
deriving Repr, DecidableEq

/-- Complete decoded input to the executable preflight evaluator. -/
structure AdmissionPreflightInput where
  view : RecoveredAdmissionView
  record : LocalPermitCommitRecord
  verifiedPermit : VerifiedPermitProjection
  preState : ObservedStateBytes
  postState : ObservedStateBytes
deriving Repr, DecidableEq

/-- Exact record-to-successful-verifier binding; this is computed, not supplied. -/
def permitEnvelopeAccepted (input : AdmissionPreflightInput) : Bool :=
  decide (input.record.envelopeDigest = input.verifiedPermit.envelopeDigest) &&
  decide (input.record.executionIntentDigest = input.verifiedPermit.executionIntentDigest) &&
  decide (input.record.nonceDigest = input.verifiedPermit.nonceDigest) &&
  decide (input.record.priorHead = input.verifiedPermit.priorHead) &&
  decide (input.record.expectedNextHead = input.verifiedPermit.expectedNextHead)

/-- The local record has exactly the time checked by the foreign verifier. -/
def verificationTimeAccepted (input : AdmissionPreflightInput) : Bool :=
  decide (input.record.committedAt = input.verifiedPermit.checkedAt) &&
  decide (input.record.verificationTime = input.verifiedPermit.checkedAt)

def boundedObservedState (state : ObservedStateBytes) : Bool :=
  0 < state.byteLength && state.byteLength ≤ maxObservedStateBytes

/-- Bounded observed state digests bind directly to the verified Permit heads. -/
def stateBytesAccepted (input : AdmissionPreflightInput) : Bool :=
  boundedObservedState input.preState &&
  boundedObservedState input.postState &&
  decide (input.preState.sha256 = input.verifiedPermit.priorHead.stateDigest) &&
  decide (input.postState.sha256 = input.verifiedPermit.expectedNextHead.stateDigest)

def computedAdapterFacts (input : AdmissionPreflightInput) : VerifiedAdmissionAdapterFacts :=
  { permitEnvelopeAccepted := permitEnvelopeAccepted input
    verificationTimeAccepted := verificationTimeAccepted input
    stateBytesAccepted := stateBytesAccepted input }

/-- The record shape produced by the native success path from its verifier projection. -/
def nativeRecordFromVerified (verifiedPermit : VerifiedPermitProjection) :
    LocalPermitCommitRecord :=
  { contractVersion := localPermitCommitContractVersion
    status := localPermitCommitStatus
    committedAt := verifiedPermit.checkedAt
    verificationTime := verifiedPermit.checkedAt
    envelopeDigest := verifiedPermit.envelopeDigest
    executionIntentDigest := verifiedPermit.executionIntentDigest
    nonceDigest := verifiedPermit.nonceDigest
    priorHead := verifiedPermit.priorHead
    expectedNextHead := verifiedPermit.expectedNextHead }

/-- The complete pure image of the native checked-preflight construction. -/
def constructedPreflight (view : RecoveredAdmissionView)
    (verifiedPermit : VerifiedPermitProjection)
    (preState postState : ObservedStateBytes) : AdmissionPreflightInput :=
  { view := view
    record := nativeRecordFromVerified verifiedPermit
    verifiedPermit := verifiedPermit
    preState := preState
    postState := postState }

/-- The remaining state-byte checks that native code establishes before construction. -/
def NativeStateByteConditions (verifiedPermit : VerifiedPermitProjection)
    (preState postState : ObservedStateBytes) : Prop :=
  0 < preState.byteLength ∧ preState.byteLength ≤ maxObservedStateBytes ∧
  0 < postState.byteLength ∧ postState.byteLength ≤ maxObservedStateBytes ∧
  preState.sha256 = verifiedPermit.priorHead.stateDigest ∧
  postState.sha256 = verifiedPermit.expectedNextHead.stateDigest

/-- Native journal facts left after verifier and byte-image checks. -/
def NativeLocalAdmissionConditions (view : RecoveredAdmissionView)
    (verifiedPermit : VerifiedPermitProjection) : Prop :=
  verifiedPermit.nonceDigest ∉ view.consumedNonces ∧
  ((view.head = none ∧ verifiedPermit.priorHead.sequence = 0) ∨
    view.head = some verifiedPermit.priorHead) ∧
  verifiedPermit.expectedNextHead.lineageId = verifiedPermit.priorHead.lineageId ∧
  verifiedPermit.expectedNextHead.sequence = verifiedPermit.priorHead.sequence + 1

def AdmissionPreflightInput.toKernelRequest (input : AdmissionPreflightInput) :
    VerifiedAdmissionRequest :=
  { state := input.view.asState
    record := input.record
    adapterFacts := computedAdapterFacts input }

/-- The gate is the existing kernel applied to facts computed above. -/
def evaluateAdmissionPreflight (input : AdmissionPreflightInput) : VerifiedAdmissionDecision :=
  verifiedAdmissionKernel input.toKernelRequest

def AdmissionPreflightAccepted (input : AdmissionPreflightInput)
    (next : LocalPermitCommitState) : Prop :=
  evaluateAdmissionPreflight input = .accepted next

theorem constructedPreflightPermitFact :
    permitEnvelopeAccepted (constructedPreflight view verifiedPermit preState postState) = true := by
  simp [constructedPreflight, nativeRecordFromVerified, permitEnvelopeAccepted]

theorem constructedPreflightTimeFact :
    verificationTimeAccepted (constructedPreflight view verifiedPermit preState postState) = true := by
  simp [constructedPreflight, nativeRecordFromVerified, verificationTimeAccepted]

theorem constructedPreflightStateFact
    (checked : NativeStateByteConditions verifiedPermit preState postState) :
    stateBytesAccepted (constructedPreflight view verifiedPermit preState postState) = true := by
  rcases checked with ⟨preNonempty, preBounded, postNonempty, postBounded,
    preDigest, postDigest⟩
  simp [constructedPreflight, stateBytesAccepted, boundedObservedState,
    preNonempty, preBounded, postNonempty, postBounded, preDigest, postDigest]

theorem constructedPreflightComputesFacts
    (checked : NativeStateByteConditions verifiedPermit preState postState) :
    computedAdapterFacts (constructedPreflight view verifiedPermit preState postState) =
      { permitEnvelopeAccepted := true, verificationTimeAccepted := true,
        stateBytesAccepted := true } := by
  rcases checked with ⟨preNonempty, preBounded, postNonempty, postBounded,
    preDigest, postDigest⟩
  simp [computedAdapterFacts, constructedPreflight, nativeRecordFromVerified,
    permitEnvelopeAccepted, verificationTimeAccepted, stateBytesAccepted,
    boundedObservedState, preNonempty, preBounded, postNonempty, postBounded,
    preDigest, postDigest]

theorem constructedPreflightKernelAccepts
    (bytesChecked : NativeStateByteConditions verifiedPermit preState postState)
    (journalChecked : NativeLocalAdmissionConditions view verifiedPermit) :
    AdmissionPreflightAccepted
      (constructedPreflight view verifiedPermit preState postState)
      (advanceLocalPermitCommit
        (constructedPreflight view verifiedPermit preState postState).view.asState
        (constructedPreflight view verifiedPermit preState postState).toKernelRequest.toLocalCommand) := by
  unfold AdmissionPreflightAccepted evaluateAdmissionPreflight
  apply (verifiedAdmissionKernelAcceptedIff _).mpr
  rcases bytesChecked with ⟨preNonempty, preBounded, postNonempty, postBounded,
    preDigest, postDigest⟩
  rcases journalChecked with ⟨nonceFresh, predecessor, lineage, sequence⟩
  change LocalPermitCommitConditions view.asState
    (constructedPreflight view verifiedPermit preState postState).toKernelRequest.toLocalCommand
  simp only [LocalPermitCommitConditions, AdmissionPreflightInput.toKernelRequest,
    VerifiedAdmissionRequest.toLocalCommand]
  have permit := constructedPreflightPermitFact
    (view := view) (verifiedPermit := verifiedPermit) (preState := preState)
    (postState := postState)
  have time := constructedPreflightTimeFact
    (view := view) (verifiedPermit := verifiedPermit) (preState := preState)
    (postState := postState)
  have state := constructedPreflightStateFact
    (view := view) (verifiedPermit := verifiedPermit) (preState := preState)
    (postState := postState)
    ⟨preNonempty, preBounded, postNonempty, postBounded, preDigest, postDigest⟩
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · rfl
  · rfl
  · rfl
  · exact permit
  · exact time
  · exact state
  · simpa [constructedPreflight, nativeRecordFromVerified,
      RecoveredAdmissionView.asState] using nonceFresh
  · simpa [constructedPreflight, nativeRecordFromVerified,
      RecoveredAdmissionView.asState] using predecessor
  · simpa [constructedPreflight, nativeRecordFromVerified] using lineage
  · simpa [constructedPreflight, nativeRecordFromVerified] using sequence

theorem preflightAcceptedIsKernelAccepted
    (accepted : AdmissionPreflightAccepted input next) :
    VerifiedAdmissionAccepted input.toKernelRequest next := accepted

theorem preflightAcceptedRequiresComputedFacts
    (accepted : AdmissionPreflightAccepted input next) :
    permitEnvelopeAccepted input = true ∧
    verificationTimeAccepted input = true ∧
    stateBytesAccepted input = true := by
  have facts := verifiedAdmissionKernelRequiresForeignChecks
    (preflightAcceptedIsKernelAccepted accepted)
  exact facts

theorem preflightAcceptedBindsExactVerifiedPermit
    (accepted : AdmissionPreflightAccepted input next) :
    input.record.envelopeDigest = input.verifiedPermit.envelopeDigest ∧
    input.record.executionIntentDigest = input.verifiedPermit.executionIntentDigest ∧
    input.record.nonceDigest = input.verifiedPermit.nonceDigest ∧
    input.record.priorHead = input.verifiedPermit.priorHead ∧
    input.record.expectedNextHead = input.verifiedPermit.expectedNextHead := by
  have bound := (preflightAcceptedRequiresComputedFacts accepted).1
  simp only [permitEnvelopeAccepted, Bool.and_eq_true, decide_eq_true_eq] at bound
  rcases bound with ⟨⟨⟨⟨envelope, intent⟩, nonce⟩, prior⟩, nextHead⟩
  exact ⟨envelope, intent, nonce, prior, nextHead⟩

theorem preflightAcceptedBindsExactVerificationTime
    (accepted : AdmissionPreflightAccepted input next) :
    input.record.committedAt = input.verifiedPermit.checkedAt ∧
    input.record.verificationTime = input.verifiedPermit.checkedAt := by
  exact (by
    simpa [verificationTimeAccepted] using
      (preflightAcceptedRequiresComputedFacts accepted).2.1)

theorem preflightAcceptedBindsBoundedStateDigests
    (accepted : AdmissionPreflightAccepted input next) :
    0 < input.preState.byteLength ∧ input.preState.byteLength ≤ maxObservedStateBytes ∧
    0 < input.postState.byteLength ∧ input.postState.byteLength ≤ maxObservedStateBytes ∧
    input.preState.sha256 = input.verifiedPermit.priorHead.stateDigest ∧
    input.postState.sha256 = input.verifiedPermit.expectedNextHead.stateDigest := by
  have bound := (preflightAcceptedRequiresComputedFacts accepted).2.2
  simp only [stateBytesAccepted, boundedObservedState, Bool.and_eq_true,
    decide_eq_true_eq] at bound
  rcases bound with
    ⟨⟨⟨⟨preNonempty, preBounded⟩, ⟨postNonempty, postBounded⟩⟩,
      preDigest⟩, postDigest⟩
  exact ⟨preNonempty, preBounded, postNonempty, postBounded, preDigest, postDigest⟩

theorem preflightAcceptedYieldsBoundedRefinement
    (accepted : AdmissionPreflightAccepted input next) :
    LocalPermitCommitRefinesLinearJournal input.view.asState
      input.toKernelRequest.toLocalCommand next := by
  exact verifiedAdmissionKernelYieldsBoundedRefinement
    (preflightAcceptedIsKernelAccepted accepted)

theorem preflightAcceptedPublishesExactSuccessor
    (accepted : AdmissionPreflightAccepted input next) :
    next.head = some input.record.expectedNextHead := by
  exact verifiedAdmissionKernelPublishesExactSuccessor
    (preflightAcceptedIsKernelAccepted accepted)

theorem preflightAcceptedConsumesExactNonce
    (accepted : AdmissionPreflightAccepted input next) :
    input.record.nonceDigest ∈ next.consumedNonces := by
  exact verifiedAdmissionKernelConsumesNonce
    (preflightAcceptedIsKernelAccepted accepted)

end HSWM.CanonicalLearning.AdmissionPreflight
