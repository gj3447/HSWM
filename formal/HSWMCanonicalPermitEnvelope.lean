import HSWMEndToEndRuntimeRefinement

/-!
# HSWM canonical Permit authentication-envelope checker

This module is a field-binding abstraction of selected checks performed by the
TypeScript `hswm-canonical-permit-envelope/v1` codec.  It is not a parser,
byte-level refinement, or semantic equivalence proof for that codec.  It proves
that acceptance by this modeled checker projects every supplied expected
transition binding and, relative to an explicit verifier-soundness premise,
the declared signature meaning.

It does not parse JSON bytes, prove SHA-256 or Ed25519, establish trusted time
or key custody, consume a nonce, or establish atomic admission or learning.
In particular, its opaque `executionIntentDigest` is not yet connected to
canonical pre-execution intent bytes, and this namespace is not connected to
`PermitAuthenticationEvidence`, `HeadBoundPermit`, or an atomic-admission
certificate.  Those remain visible implementation/refinement obligations.
-/

namespace HSWM.CanonicalLearning.CanonicalPermitEnvelope

open AtomicAdmission
open EndToEndRuntimeRefinement

structure PermitId where
  value : String
deriving Repr, DecidableEq

structure NonceDigest where
  value : String
deriving Repr, DecidableEq

structure CanonicalInstant where
  value : String
deriving Repr, DecidableEq

structure PermitEnvelopeHeader where
  domain : String
  contractVersion : String
  canonicalization : String
  algorithm : String
  keyId : String
  payloadType : String
deriving Repr, DecidableEq

def expectedPermitEnvelopeHeader (keyId : String) : PermitEnvelopeHeader :=
  { domain := "HSWM_CANONICAL_PERMIT_V1"
    contractVersion := "hswm-canonical-permit-envelope/v1"
    canonicalization := "hswm-canonical-json/v1"
    algorithm := "Ed25519"
    keyId := keyId
    payloadType := "application/vnd.hswm.canonical-permit-claims-v1+json" }

structure PermitEnvelopeClaims where
  permitId : PermitId
  executionId : RuntimeExecutionId
  executionIntentDigest : EvidenceDigest
  permitDigest : EvidenceDigest
  proposalDigest : EvidenceDigest
  transitionInvariantDigest : EvidenceDigest
  priorHead : HeadSnapshot
  expectedNextHead : HeadSnapshot
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  authorizationRef : AuthorizationRef
  authorizer : Principal
  scope : Scope
  nonceDigest : NonceDigest
  keyPolicyVersion : String
  revocationEpoch : Nat
  linearizationIndex : Nat
  issuedAt : CanonicalInstant
  notBefore : CanonicalInstant
  expiresAt : CanonicalInstant
deriving Repr, DecidableEq

/--
Supplied field context against which the abstract envelope is checked.

This record is deliberately not yet derived from `HeadBoundPermit`, an
invariant certificate, or a concrete runtime trace.  Equal fields therefore
show only equality to this supplied context, not a refinement to atomic
admission.
-/
structure PermitExpectedBindings where
  permitId : PermitId
  executionId : RuntimeExecutionId
  executionIntentDigest : EvidenceDigest
  permitDigest : EvidenceDigest
  proposalDigest : EvidenceDigest
  transitionInvariantDigest : EvidenceDigest
  priorHead : HeadSnapshot
  expectedNextHead : HeadSnapshot
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  authorizationRef : AuthorizationRef
  authorizer : Principal
  scope : Scope
  nonceDigest : NonceDigest
  keyPolicyVersion : String
  revocationEpoch : Nat
  linearizationIndex : Nat
deriving Repr, DecidableEq

def PermitEnvelopeClaims.expectedBindings
    (claims : PermitEnvelopeClaims) : PermitExpectedBindings :=
  { permitId := claims.permitId
    executionId := claims.executionId
    executionIntentDigest := claims.executionIntentDigest
    permitDigest := claims.permitDigest
    proposalDigest := claims.proposalDigest
    transitionInvariantDigest := claims.transitionInvariantDigest
    priorHead := claims.priorHead
    expectedNextHead := claims.expectedNextHead
    target := claims.target
    expectedRevision := claims.expectedRevision
    candidateRevision := claims.candidateRevision
    authorizationRef := claims.authorizationRef
    authorizer := claims.authorizer
    scope := claims.scope
    nonceDigest := claims.nonceDigest
    keyPolicyVersion := claims.keyPolicyVersion
    revocationEpoch := claims.revocationEpoch
    linearizationIndex := claims.linearizationIndex }

def ExactPermitBindings
    (claims : PermitEnvelopeClaims)
    (expected : PermitExpectedBindings) : Prop :=
  claims.expectedBindings = expected

def PermitTransitionWellFormed (claims : PermitEnvelopeClaims) : Prop :=
  claims.expectedRevision ≠ claims.candidateRevision ∧
  claims.priorHead.lineageId = claims.expectedNextHead.lineageId ∧
  claims.expectedNextHead.sequence = claims.priorHead.sequence + 1

structure PermitSigningDocument where
  header : PermitEnvelopeHeader
  claims : PermitEnvelopeClaims
  status : String
deriving Repr, DecidableEq

structure CanonicalPermitEnvelope where
  document : PermitSigningDocument
  signature : Signature
deriving Repr, DecidableEq

/--
Boolean results supplied by byte, trust-policy and trusted-time adapters.

They model accepted adapter outcomes; they neither represent TypeScript's full
schema/time/key-lifecycle algorithms nor prove that an external adapter has
the claimed semantics.
-/
structure ExternalPermitChecks where
  canonicalBytesAccepted : Bool
  trustSnapshotAccepted : Bool
  keyPolicyAndEpochMatched : Bool
  keyAuthorizedForAuthorizer : Bool
  keyActiveAtVerification : Bool
  permitTimeActive : Bool
deriving Repr, DecidableEq

abbrev EnvelopeSignatureVerifier :=
  PublicKey → PermitSigningDocument → Signature → Bool

abbrev EnvelopeSignatureMeaning :=
  PublicKey → PermitSigningDocument → Signature → Prop

def EnvelopeSignatureVerifierSound
    (verify : EnvelopeSignatureVerifier)
    (signedBy : EnvelopeSignatureMeaning) : Prop :=
  ∀ key document signature,
    verify key document signature = true →
      signedBy key document signature

/--
An abstract field-binding checker, not the TypeScript checker itself.

It omits byte parsing/canonicalization, the TypeScript `_tag`, identifier and
SHA schemas, instant chronology, trust-snapshot lookup, and the key-ID to
public-key relation.  Those operations are represented only by the supplied
values and adapter booleans below.
-/
def canonicalPermitEnvelopeAccepted
    (verify : EnvelopeSignatureVerifier)
    (key : PublicKey)
    (expectedKeyId : String)
    (expected : PermitExpectedBindings)
    (checks : ExternalPermitChecks)
    (envelope : CanonicalPermitEnvelope) : Bool :=
  decide (envelope.document.header =
    expectedPermitEnvelopeHeader expectedKeyId) &&
  (decide (envelope.document.status =
    "SIGNED_AUTHORIZATION_ENVELOPE_NOT_ATOMIC_ADMISSION_NOT_LEARNING") &&
  (decide (envelope.document.claims.expectedBindings = expected) &&
  (decide (
    envelope.document.claims.expectedRevision ≠
      envelope.document.claims.candidateRevision ∧
    envelope.document.claims.priorHead.lineageId =
      envelope.document.claims.expectedNextHead.lineageId ∧
    envelope.document.claims.expectedNextHead.sequence =
      envelope.document.claims.priorHead.sequence + 1) &&
  (checks.canonicalBytesAccepted &&
  (checks.trustSnapshotAccepted &&
  (checks.keyPolicyAndEpochMatched &&
  (checks.keyAuthorizedForAuthorizer &&
  (checks.keyActiveAtVerification &&
  (checks.permitTimeActive &&
    verify key envelope.document envelope.signature)))))))))

/--
Acceptance cannot float to a different supplied execution, head, revision or
nonce context.  This is not yet a claim that that context came from a runtime
execution or canonical atomic-admission inputs.
-/
theorem acceptedEnvelopeProjectsEveryCheckedBinding
    (accepted : canonicalPermitEnvelopeAccepted verify key expectedKeyId
      expected checks envelope = true) :
    envelope.document.header = expectedPermitEnvelopeHeader expectedKeyId ∧
    envelope.document.status =
      "SIGNED_AUTHORIZATION_ENVELOPE_NOT_ATOMIC_ADMISSION_NOT_LEARNING" ∧
    ExactPermitBindings envelope.document.claims expected ∧
    PermitTransitionWellFormed envelope.document.claims ∧
    checks.canonicalBytesAccepted = true ∧
    checks.trustSnapshotAccepted = true ∧
    checks.keyPolicyAndEpochMatched = true ∧
    checks.keyAuthorizedForAuthorizer = true ∧
    checks.keyActiveAtVerification = true ∧
    checks.permitTimeActive = true ∧
    verify key envelope.document envelope.signature = true := by
  simpa [canonicalPermitEnvelopeAccepted, ExactPermitBindings,
    PermitTransitionWellFormed] using accepted

theorem acceptedEnvelopeProjectsSuppliedExecutionContext
    (accepted : canonicalPermitEnvelopeAccepted verify key expectedKeyId
      expected checks envelope = true) :
    envelope.document.claims.executionId = expected.executionId ∧
    envelope.document.claims.executionIntentDigest =
      expected.executionIntentDigest ∧
    envelope.document.claims.priorHead = expected.priorHead ∧
    envelope.document.claims.expectedNextHead = expected.expectedNextHead ∧
    envelope.document.claims.proposalDigest = expected.proposalDigest ∧
    envelope.document.claims.transitionInvariantDigest =
      expected.transitionInvariantDigest ∧
    envelope.document.claims.nonceDigest = expected.nonceDigest := by
  have bindings :=
    (acceptedEnvelopeProjectsEveryCheckedBinding accepted).2.2.1
  have exact : envelope.document.claims.expectedBindings = expected := bindings
  cases exact
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/--
Cryptographic meaning follows only relative to a sound verifier premise; the
field bindings and all external check outcomes remain separately visible.  The
theorem does not connect the document to Node Ed25519, raw signing bytes, or
the end-to-end `PermitAuthenticationEvidence` relation.
-/
theorem acceptedEnvelopeAndSoundVerifierYieldAuthenticatedDocument
    (accepted : canonicalPermitEnvelopeAccepted verify key expectedKeyId
      expected checks envelope = true)
    (sound : EnvelopeSignatureVerifierSound verify signedBy) :
    ExactPermitBindings envelope.document.claims expected ∧
    PermitTransitionWellFormed envelope.document.claims ∧
    signedBy key envelope.document envelope.signature ∧
    checks.canonicalBytesAccepted = true ∧
    checks.trustSnapshotAccepted = true ∧
    checks.keyPolicyAndEpochMatched = true ∧
    checks.keyAuthorizedForAuthorizer = true ∧
    checks.keyActiveAtVerification = true ∧
    checks.permitTimeActive = true := by
  have projected := acceptedEnvelopeProjectsEveryCheckedBinding accepted
  exact ⟨projected.2.2.1,
    projected.2.2.2.1,
    sound key envelope.document envelope.signature
      projected.2.2.2.2.2.2.2.2.2.2,
    projected.2.2.2.2.1,
    projected.2.2.2.2.2.1,
    projected.2.2.2.2.2.2.1,
    projected.2.2.2.2.2.2.2.1,
    projected.2.2.2.2.2.2.2.2.1,
    projected.2.2.2.2.2.2.2.2.2.1⟩

/-- A field change cannot be hidden behind checker acceptance. -/
theorem changedExecutionIntentDigestCannotBeAccepted
    (changed : envelope.document.claims.executionIntentDigest ≠
      expected.executionIntentDigest) :
    canonicalPermitEnvelopeAccepted verify key expectedKeyId expected checks
      envelope ≠ true := by
  intro accepted
  exact changed
    (acceptedEnvelopeProjectsSuppliedExecutionContext accepted).2.1

theorem changedNonceCannotBeAccepted
    (changed : envelope.document.claims.nonceDigest ≠ expected.nonceDigest) :
    canonicalPermitEnvelopeAccepted verify key expectedKeyId expected checks
      envelope ≠ true := by
  intro accepted
  exact changed
    (acceptedEnvelopeProjectsSuppliedExecutionContext accepted).2.2.2.2.2.2

end HSWM.CanonicalLearning.CanonicalPermitEnvelope
