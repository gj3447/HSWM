import HSWMAdmissionPreflight

/-!
Bridge from an externally successful native Permit verifier to the decoded
preflight model.  The `NativeVerifiedPermit` value is an explicit boundary:
it records what the native verifier returned, but is not a proof of parsing,
hashing, Ed25519, trust policy, or trusted time.
-/
namespace HSWM.CanonicalLearning.VerifiedPermitBridge

open AtomicAdmission CanonicalPermitEnvelope LocalPermitCommit VerifiedAdmissionKernel AdmissionPreflight

def verifiedPermitBridgeContractVersion : String := "hswm-verified-permit-bridge/v1"

structure NativeVerifiedPermit where
  envelopeDigest : EvidenceDigest
  checkedAt : String
  executionIntentDigest : EvidenceDigest
  nonceDigest : NonceDigest
  priorHead : HeadSnapshot
  expectedNextHead : HeadSnapshot
  signingBytesDigest : EvidenceDigest
  expectedBindingsDigest : EvidenceDigest
  trustSnapshotDigest : EvidenceDigest
  publicKeyDigest : EvidenceDigest
  trustPolicyVersion : String
  trustRevocationEpoch : Nat
  trustedKeyId : String
deriving Repr, DecidableEq

/--
An explicitly bounded correspondence supplied by the native verifier boundary.
It does not assert that Lean parsed the signed bytes or ran Ed25519: those
operations remain foreign.  It says only that the native success projection
and the existing decoded Permit model describe the same checked claims.
-/
structure NativeVerifierModelCorrespondence where
  native : NativeVerifiedPermit
  envelope : CanonicalPermitEnvelope
  expected : PermitExpectedBindings
  key : PublicKey
  expectedKeyId : String
  checks : ExternalPermitChecks
  verify : EnvelopeSignatureVerifier
  modelAccepted : canonicalPermitEnvelopeAccepted verify key expectedKeyId expected checks envelope = true
  intentMatches : native.executionIntentDigest = envelope.document.claims.executionIntentDigest
  nonceMatches : native.nonceDigest = envelope.document.claims.nonceDigest
  priorHeadMatches : native.priorHead = envelope.document.claims.priorHead
  nextHeadMatches : native.expectedNextHead = envelope.document.claims.expectedNextHead

def NativeVerifiedPermit.toPreflightProjection (native : NativeVerifiedPermit) :
    VerifiedPermitProjection :=
  { envelopeDigest := native.envelopeDigest, checkedAt := native.checkedAt
    executionIntentDigest := native.executionIntentDigest, nonceDigest := native.nonceDigest
    priorHead := native.priorHead, expectedNextHead := native.expectedNextHead }

def nativeVerifiedPreflight (view : RecoveredAdmissionView) (native : NativeVerifiedPermit)
    (preState postState : ObservedStateBytes) : AdmissionPreflightInput :=
  constructedPreflight view native.toPreflightProjection preState postState

/-- A modeled accepted envelope projects the same five preflight bindings. -/
theorem modeledNativeSuccessProjectsPreflightBindings
    (correspondence : NativeVerifierModelCorrespondence) :
    correspondence.native.toPreflightProjection.executionIntentDigest =
      correspondence.envelope.document.claims.executionIntentDigest ∧
    correspondence.native.toPreflightProjection.nonceDigest =
      correspondence.envelope.document.claims.nonceDigest ∧
    correspondence.native.toPreflightProjection.priorHead =
      correspondence.envelope.document.claims.priorHead ∧
    correspondence.native.toPreflightProjection.expectedNextHead =
      correspondence.envelope.document.claims.expectedNextHead := by
  exact ⟨correspondence.intentMatches, correspondence.nonceMatches,
    correspondence.priorHeadMatches,
    correspondence.nextHeadMatches⟩

/-- The accepted decoded model binds the native projection to its supplied scope,
key-policy, revision and digest context through `expected`. -/
theorem modeledNativeSuccessProjectsExpectedContext
    (correspondence : NativeVerifierModelCorrespondence) :
    correspondence.native.executionIntentDigest = correspondence.expected.executionIntentDigest ∧
    correspondence.native.nonceDigest = correspondence.expected.nonceDigest ∧
    correspondence.native.priorHead = correspondence.expected.priorHead ∧
    correspondence.native.expectedNextHead = correspondence.expected.expectedNextHead := by
  have projected := acceptedEnvelopeProjectsSuppliedExecutionContext
    correspondence.modelAccepted
  rcases projected with ⟨_, intent, prior, nextHead, _, _, nonce⟩
  exact ⟨correspondence.intentMatches.trans intent,
    correspondence.nonceMatches.trans nonce,
    correspondence.priorHeadMatches.trans prior,
    correspondence.nextHeadMatches.trans nextHead⟩

/-- Only recovery facts not established by the accepted Permit model. -/
def NativeRecoveryConditions (view : RecoveredAdmissionView)
    (native : NativeVerifiedPermit) : Prop :=
  native.nonceDigest ∉ view.consumedNonces ∧
  ((view.head = none ∧ native.priorHead.sequence = 0) ∨
    view.head = some native.priorHead)

theorem modeledNativeSuccessJournalConditions
    (correspondence : NativeVerifierModelCorrespondence)
    (recovery : NativeRecoveryConditions view correspondence.native) :
    NativeLocalAdmissionConditions view correspondence.native.toPreflightProjection := by
  rcases recovery with ⟨fresh, predecessor⟩
  have transition := (acceptedEnvelopeProjectsEveryCheckedBinding
    correspondence.modelAccepted).2.2.2.2.1
  rcases transition with ⟨_, lineage, sequence⟩
  refine ⟨fresh, predecessor, ?_, ?_⟩
  · change correspondence.native.expectedNextHead.lineageId = correspondence.native.priorHead.lineageId
    rw [correspondence.nextHeadMatches, correspondence.priorHeadMatches]
    exact lineage.symm
  · change correspondence.native.expectedNextHead.sequence = correspondence.native.priorHead.sequence + 1
    rw [correspondence.nextHeadMatches, correspondence.priorHeadMatches]
    exact sequence

/--
Composition theorem: the decoded signed-Permit model, a native-success
projection correspondence, bounded observed bytes, and journal facts imply
the existing kernel acceptance.  The correspondence is intentionally a
premise, so this theorem makes no crypto/parser/trust/time soundness claim.
-/
theorem modeledNativeSuccessKernelAccepts
    (correspondence : NativeVerifierModelCorrespondence)
    (bytesChecked : NativeStateByteConditions correspondence.native.toPreflightProjection preState postState)
    (recovery : NativeRecoveryConditions view correspondence.native) :
    AdmissionPreflightAccepted
      (nativeVerifiedPreflight view correspondence.native preState postState)
      (advanceLocalPermitCommit
        (nativeVerifiedPreflight view correspondence.native preState postState).view.asState
        (nativeVerifiedPreflight view correspondence.native preState postState).toKernelRequest.toLocalCommand) := by
  exact constructedPreflightKernelAccepts bytesChecked
    (modeledNativeSuccessJournalConditions correspondence recovery)

theorem nativeVerifiedPreflightComputesFacts
    (checked : NativeStateByteConditions native.toPreflightProjection preState postState) :
    computedAdapterFacts (nativeVerifiedPreflight view native preState postState) =
      { permitEnvelopeAccepted := true, verificationTimeAccepted := true,
        stateBytesAccepted := true } :=
  constructedPreflightComputesFacts checked

theorem nativeVerifiedPreflightKernelAccepts
    (bytesChecked : NativeStateByteConditions native.toPreflightProjection preState postState)
    (journalChecked : NativeLocalAdmissionConditions view native.toPreflightProjection) :
    AdmissionPreflightAccepted (nativeVerifiedPreflight view native preState postState)
      (advanceLocalPermitCommit (nativeVerifiedPreflight view native preState postState).view.asState
        (nativeVerifiedPreflight view native preState postState).toKernelRequest.toLocalCommand) :=
  constructedPreflightKernelAccepts bytesChecked journalChecked

end HSWM.CanonicalLearning.VerifiedPermitBridge
