import HSWMAtomicAdmissionNonEntailment

/-!
# HSWM end-to-end runtime refinement evidence boundary

This module states a conditional bridge schema from one claimed runtime
certificate to the existing head-bound atomic-learning relation.  It also
separates four facts that no structural record can manufacture:

* a certificate-claimed Permit issue and one declared successful commit;
* authentication relative to a sound signature verifier and active key policy;
* externally true outcome evidence with operationally independent causal credit;
* a strict score improvement on a sealed runtime LLM probe suite.

The bridge is certificate-carrying and conditional on explicit semantic
evidence.  It is not a semantics of TypeScript, Node, Effect, a filesystem, a
cryptographic primitive, a remote evaluator, or an LLM provider.  The
checked-in TypeScript profile remains a proved obstruction, not a positive
refinement witness.
-/

namespace HSWM.CanonicalLearning.EndToEndRuntimeRefinement

open OutcomeJudgment
open AtomicAdmission

structure RuntimeExecutionId where
  value : String
deriving Repr, DecidableEq

structure PublicKey where
  value : String
deriving Repr, DecidableEq

structure Signature where
  value : String
deriving Repr, DecidableEq

structure KeyPolicyContext where
  version : String
  revocationEpoch : Nat
deriving Repr, DecidableEq

/-- Domain-separated message whose signature cannot float to another execution. -/
structure PermitSigningMessage where
  domain : String
  contractVersion : String
  executionId : RuntimeExecutionId
  certificateDigest : EvidenceDigest
  keyPolicyVersion : String
  revocationEpoch : Nat
  permitDigest : EvidenceDigest
  head : HeadSnapshot
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  authorizationRef : AuthorizationRef
  scope : Scope
  linearizationIndex : Nat
deriving Repr, DecidableEq

/-! ## Concrete occurrence certificate -/

/-- One runtime event claiming that an exact head-bound Permit was issued. -/
structure PermitIssueOccurrence where
  executionId : RuntimeExecutionId
  issuer : Principal
  permitDigest : EvidenceDigest
  head : HeadSnapshot
  target : AtomAddress
  expectedRevision : RevisionId
  candidateRevision : RevisionId
  authorizationRef : AuthorizationRef
  scope : Scope
  linearizationIndex : Nat
deriving Repr, DecidableEq

/-- One recovered successful commit occurrence in a concrete execution. -/
structure RuntimeCommitOccurrence where
  executionId : RuntimeExecutionId
  witness : AdmissionCommitWitness
  recoveredSuccessorHead : HeadSnapshot
  linearizationIndex : Nat
deriving Repr, DecidableEq

/-- The bounded event projection carried by one runtime certificate. -/
structure RuntimeExecutionTrace where
  executionId : RuntimeExecutionId
  certificateDigest : EvidenceDigest
  permitIssues : List PermitIssueOccurrence
  successfulCommits : List RuntimeCommitOccurrence
  recoveryIndex : Nat
deriving Repr, DecidableEq

/-- Exact field-level correspondence between an issue occurrence and Permit. -/
def ExactPermitIssue
    (trace : RuntimeExecutionTrace)
    (issue : PermitIssueOccurrence)
    (permit : HeadBoundPermit) : Prop :=
  issue.executionId = trace.executionId ∧
  issue.issuer = permit.decision.authorizer ∧
  issue.permitDigest = permit.contentDigest ∧
  issue.head = permit.head ∧
  issue.target = permit.decision.target ∧
  issue.expectedRevision = permit.expectedRevision ∧
  issue.candidateRevision = permit.candidateRevision ∧
  issue.authorizationRef = permit.decision.authorizationRef ∧
  issue.scope = permit.decision.scope

/-- Exact field-level correspondence between a recovered commit and witness. -/
def ExactRuntimeCommit
    (trace : RuntimeExecutionTrace)
    (occurrence : RuntimeCommitOccurrence)
    (witness : AdmissionCommitWitness)
    (nextHead : HeadSnapshot) : Prop :=
  occurrence.executionId = trace.executionId ∧
  occurrence.witness = witness ∧
  occurrence.recoveredSuccessorHead = nextHead

/--
Evidence accepted from one canonical runtime certificate.  `successfulCommits`
contains exactly one *declared successful* occurrence; this is not by itself a
filesystem, database, crash-consistency, or distributed-linearizability proof.
-/
structure ClaimedConcreteExecutionEvidence
    (permit : HeadBoundPermit)
    (commitWitness : AdmissionCommitWitness)
    (nextHead : HeadSnapshot) where
  trace : RuntimeExecutionTrace
  issue : PermitIssueOccurrence
  commit : RuntimeCommitOccurrence
  certificateDigestSemantics :
    RuntimeExecutionTrace → EvidenceDigest → Prop
  certificateDigestBindsTrace :
    certificateDigestSemantics trace trace.certificateDigest
  canonicalCertificateBytesAccepted : Bool
  recoveredPostStateAccepted : Bool
  canonicalCertificateBytesWereAccepted :
    canonicalCertificateBytesAccepted = true
  recoveredPostStateWasAccepted : recoveredPostStateAccepted = true
  issuePresent : issue ∈ trace.permitIssues
  issueExact : ExactPermitIssue trace issue permit
  issueUniqueForPermit :
    ∀ other,
      other ∈ trace.permitIssues →
      ExactPermitIssue trace other permit →
      other = issue
  issueBeforeCommit : issue.linearizationIndex < commit.linearizationIndex
  commitBeforeRecovery : commit.linearizationIndex < trace.recoveryIndex
  successfulCommitLog : trace.successfulCommits = [commit]
  commitExact : ExactRuntimeCommit trace commit commitWitness nextHead

theorem claimedEvidenceContainsExactPermitIssue
    (evidence : ClaimedConcreteExecutionEvidence permit commitWitness nextHead) :
    ∃ issue,
      issue ∈ evidence.trace.permitIssues ∧
      ExactPermitIssue evidence.trace issue permit := by
  exact ⟨evidence.issue, evidence.issuePresent, evidence.issueExact⟩

theorem claimedEvidenceHasOneDeclaredSuccessfulCommit
    (evidence : ClaimedConcreteExecutionEvidence permit commitWitness nextHead) :
    evidence.trace.successfulCommits.length = 1 := by
  rw [evidence.successfulCommitLog]
  rfl

theorem claimedEvidenceContainsExactRuntimeCommit
    (evidence : ClaimedConcreteExecutionEvidence permit commitWitness nextHead) :
    ExactRuntimeCommit evidence.trace evidence.commit commitWitness nextHead :=
  evidence.commitExact

theorem claimedSuccessfulCommitIsUnique
    (evidence : ClaimedConcreteExecutionEvidence permit commitWitness nextHead)
    (other : RuntimeCommitOccurrence)
    (present : other ∈ evidence.trace.successfulCommits) :
    other = evidence.commit := by
  rw [evidence.successfulCommitLog] at present
  simpa using present

theorem claimedCertificateChecksWereAccepted
    (evidence : ClaimedConcreteExecutionEvidence permit commitWitness nextHead) :
    evidence.canonicalCertificateBytesAccepted = true ∧
    evidence.recoveredPostStateAccepted = true :=
  ⟨evidence.canonicalCertificateBytesWereAccepted,
    evidence.recoveredPostStateWasAccepted⟩

theorem claimedEvidenceHasOrderedIssueCommitRecovery
    (evidence : ClaimedConcreteExecutionEvidence
      permit commitWitness nextHead) :
    evidence.issue.linearizationIndex < evidence.commit.linearizationIndex ∧
    evidence.commit.linearizationIndex < evidence.trace.recoveryIndex :=
  ⟨evidence.issueBeforeCommit, evidence.commitBeforeRecovery⟩

/-! ## Runtime-state abstraction and atomic refinement -/

/--
A claimed runtime certificate maps exact concrete pre/post snapshots to the
Lean states and carries every dependent condition needed by atomic admission.
The theorem below projects those carried conditions; it does not verify a
TypeScript checker. Producing this object soundly is the obligation of a future
independent certificate checker, and a status literal is not such an object.
-/
structure ClaimedRuntimeAdmissionCertificate
    (RuntimeState : Type)
    (abstractState : RuntimeState → CanonicalState)
    (digest : CanonicalState → StateDigest)
    (transitionInvariant :
      CanonicalState → RevisionProposal → CanonicalState → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (package : OutcomeEvidencePackage)
    (proposal : RevisionProposal)
    (permit : HeadBoundPermit)
    (certificate : HeadBoundInvariantCertificate)
    (commitWitness : AdmissionCommitWitness)
    (currentHead : HeadSnapshot)
    (next : CanonicalState)
    (nextHead : HeadSnapshot)
    (runtimeBefore runtimeAfter : RuntimeState) where
  execution : ClaimedConcreteExecutionEvidence permit commitWitness nextHead
  concreteRuntimeStep :
    RuntimeState → RuntimeExecutionTrace → RuntimeState → Prop
  executionOccurred :
    concreteRuntimeStep runtimeBefore execution.trace runtimeAfter
  beforeMapsExactly : abstractState runtimeBefore = state
  afterMapsExactly : abstractState runtimeAfter = next
  admissionConditions : AtomicAdmissionConditions digest transitionInvariant
    state trajectory package proposal permit certificate commitWitness
    currentHead next nextHead

/-- Conditional simulation claim for one supplied runtime-step semantics. -/
def ConditionalRuntimeStepRefinesAtomicAdmission
    (RuntimeState : Type)
    (runtimeStep :
      RuntimeState → RuntimeExecutionTrace → RuntimeState → Prop)
    (trace : RuntimeExecutionTrace)
    (abstractState : RuntimeState → CanonicalState)
    (digest : CanonicalState → StateDigest)
    (transitionInvariant :
      CanonicalState → RevisionProposal → CanonicalState → Prop)
    (state : CanonicalState)
    (trajectory : SealedTrajectory)
    (package : OutcomeEvidencePackage)
    (proposal : RevisionProposal)
    (permit : HeadBoundPermit)
    (certificate : HeadBoundInvariantCertificate)
    (commitWitness : AdmissionCommitWitness)
    (currentHead : HeadSnapshot)
    (next : CanonicalState)
    (nextHead : HeadSnapshot)
    (runtimeBefore runtimeAfter : RuntimeState) : Prop :=
  runtimeStep runtimeBefore trace runtimeAfter ∧
  abstractState runtimeBefore = state ∧
  abstractState runtimeAfter = next ∧
  AtomicLearnAdmission digest transitionInvariant state trajectory package
    proposal permit certificate commitWitness currentHead next nextHead

theorem claimedCertificateConditionsYieldAtomicAdmission
    (accepted : ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter) :
    AtomicLearnAdmission digest transitionInvariant state trajectory package
      proposal permit certificate commitWitness currentHead next nextHead := by
  exact .admit accepted.admissionConditions

theorem claimedCertificateBridgeYieldsConditionalRefinement
    (accepted : ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter) :
    ConditionalRuntimeStepRefinesAtomicAdmission RuntimeState
      accepted.concreteRuntimeStep accepted.execution.trace abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter := by
  exact ⟨accepted.executionOccurred, accepted.beforeMapsExactly,
    accepted.afterMapsExactly,
    claimedCertificateConditionsYieldAtomicAdmission accepted⟩

theorem claimedCertificateHasUniqueDeclaredSuccessfulCommit
    (accepted : ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter)
    (other : RuntimeCommitOccurrence)
    (present : other ∈ accepted.execution.trace.successfulCommits) :
    other = accepted.execution.commit :=
  claimedSuccessfulCommitIsUnique accepted.execution other present

/-! ## Permit authentication relative to an explicit trust model -/

def permitSigningMessage
    (trace : RuntimeExecutionTrace)
    (policyContext : KeyPolicyContext)
    (permit : HeadBoundPermit)
    (issue : PermitIssueOccurrence) : PermitSigningMessage :=
  { domain := "HSWM_CANONICAL_PERMIT_V1"
    contractVersion := "hswm-canonical-permit-signing-message/v1"
    executionId := trace.executionId
    certificateDigest := trace.certificateDigest
    keyPolicyVersion := policyContext.version
    revocationEpoch := policyContext.revocationEpoch
    permitDigest := permit.contentDigest
    head := permit.head
    target := permit.decision.target
    expectedRevision := permit.expectedRevision
    candidateRevision := permit.candidateRevision
    authorizationRef := permit.decision.authorizationRef
    scope := permit.decision.scope
    linearizationIndex := issue.linearizationIndex }

abbrev SignatureVerifier :=
  PublicKey → PermitSigningMessage → Signature → Bool
abbrev SignatureMeaning :=
  PublicKey → PermitSigningMessage → Signature → Prop
abbrev KeyAuthorization :=
  KeyPolicyContext → Principal → PublicKey → Prop
abbrev KeyActiveAt :=
  KeyPolicyContext → PublicKey → Nat → Prop

/-- The cryptographic trusted-computing-base premise remains visible. -/
def SignatureVerifierSound
    (verify : SignatureVerifier)
    (signedBy : SignatureMeaning) : Prop :=
  ∀ key message signature,
    verify key message signature = true → signedBy key message signature

/-- Concrete verifier/key evidence for the exact Permit digest. -/
structure PermitAuthenticationEvidence
    (verify : SignatureVerifier)
    (authorized : KeyAuthorization)
    (activeAt : KeyActiveAt)
    (trace : RuntimeExecutionTrace)
    (policyContext : KeyPolicyContext)
    (permit : HeadBoundPermit)
    (issue : PermitIssueOccurrence) where
  key : PublicKey
  signature : Signature
  verifierAccepted :
    verify key (permitSigningMessage trace policyContext permit issue)
      signature = true
  keyAuthorizedForAuthorizer :
    authorized policyContext permit.decision.authorizer key
  keyActiveAtIssue :
    activeAt policyContext key issue.linearizationIndex

/-- Authentication conclusion relative to signature, key and time semantics. -/
def AuthenticatedPermitAt
    (signedBy : SignatureMeaning)
    (authorized : KeyAuthorization)
    (activeAt : KeyActiveAt)
    (trace : RuntimeExecutionTrace)
    (policyContext : KeyPolicyContext)
    (permit : HeadBoundPermit)
    (issue : PermitIssueOccurrence)
    (key : PublicKey)
    (signature : Signature) : Prop :=
  ExactPermitIssue trace issue permit ∧
  signedBy key (permitSigningMessage trace policyContext permit issue)
    signature ∧
  authorized policyContext permit.decision.authorizer key ∧
  activeAt policyContext key issue.linearizationIndex ∧
  permit.decision.allowed = true ∧
  permit.decision.activeAtDecision = true

theorem soundVerifierAndKeyPolicyYieldPermitAuthentication
    (accepted : ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter)
    (authentication : PermitAuthenticationEvidence
      verify authorized activeAt accepted.execution.trace policyContext permit
        accepted.execution.issue)
    (sound : SignatureVerifierSound verify signedBy) :
    ∃ key signature,
      AuthenticatedPermitAt signedBy authorized activeAt
        accepted.execution.trace policyContext permit accepted.execution.issue
        key signature := by
  have admitted := claimedCertificateConditionsYieldAtomicAdmission accepted
  rcases atomicAdmissionRequiresUnderlyingLearn admitted with
    ⟨_judgment, _present, learned⟩
  have currentPermit := learnRequiresCurrentPermit learned
  exact ⟨authentication.key, authentication.signature,
    accepted.execution.issueExact,
    sound authentication.key
      (permitSigningMessage accepted.execution.trace policyContext permit
        accepted.execution.issue)
      authentication.signature
      authentication.verifierAccepted,
    authentication.keyAuthorizedForAuthorizer,
    authentication.keyActiveAtIssue,
    currentPermit.2.2.2.1,
    currentPermit.2.2.2.2⟩

/-! ## External truth and independent causal-credit semantics -/

abbrev OutcomeTruth := OutcomeObservation → Prop
abbrev OperationalIndependence := Principal → Principal → Prop
abbrev CausalCredit :=
  RevisionSupportJudgment → RevisionProposal → Prop

/--
Causal credit is independent only when the two evaluative roles are
operationally independent of actor/proposer and of one another.  Principal
inequality alone does not inhabit this predicate.
-/
def IndependentCausalCredit
    (independent : OperationalIndependence)
    (causal : CausalCredit)
    (trajectory : SealedTrajectory)
    (observation : OutcomeObservation)
    (judgment : RevisionSupportJudgment)
    (proposal : RevisionProposal) : Prop :=
  independent observation.evaluator trajectory.actor ∧
  independent observation.evaluator proposal.proposer ∧
  independent judgment.adjudicator trajectory.actor ∧
  independent judgment.adjudicator proposal.proposer ∧
  independent observation.evaluator judgment.adjudicator ∧
  causal judgment proposal

/--
Semantic evidence supplied by an external observation/identification checker.
The first three Bool fields record instrument acceptance; the truth,
independence and causal propositions remain explicit semantic witnesses.
-/
structure ExternalOutcomeSemanticWitness
    (truth : OutcomeTruth)
    (independent : OperationalIndependence)
    (causal : CausalCredit)
    (trajectory : SealedTrajectory)
    (package : OutcomeEvidencePackage)
    (proposal : RevisionProposal) where
  judgment : RevisionSupportJudgment
  judgmentPresent : package.judgment = some judgment
  worldEvidenceAccepted : Bool
  criterionPreregistered : Bool
  causalDesignAccepted : Bool
  worldEvidenceWasAccepted : worldEvidenceAccepted = true
  criterionWasPreregistered : criterionPreregistered = true
  causalDesignWasAccepted : causalDesignAccepted = true
  observationTrue : truth package.observation
  evaluatorIndependentFromActor :
    independent package.observation.evaluator trajectory.actor
  evaluatorIndependentFromProposer :
    independent package.observation.evaluator proposal.proposer
  adjudicatorIndependentFromActor :
    independent judgment.adjudicator trajectory.actor
  adjudicatorIndependentFromProposer :
    independent judgment.adjudicator proposal.proposer
  evaluatorIndependentFromAdjudicator :
    independent package.observation.evaluator judgment.adjudicator
  judgmentCausallySupportsProposal : causal judgment proposal

theorem externalOutcomeWitnessProjectsTruthAndCausalCredit
    (verified : ExternalOutcomeSemanticWitness truth independent causal
      trajectory package proposal) :
    truth package.observation ∧
    IndependentCausalCredit independent causal trajectory package.observation
      verified.judgment proposal := by
  exact ⟨verified.observationTrue,
    verified.evaluatorIndependentFromActor,
    verified.evaluatorIndependentFromProposer,
    verified.adjudicatorIndependentFromActor,
    verified.adjudicatorIndependentFromProposer,
    verified.evaluatorIndependentFromAdjudicator,
    verified.judgmentCausallySupportsProposal⟩

def OutcomeInstrumentAccepted
    (verified : ExternalOutcomeSemanticWitness truth independent causal
      trajectory package proposal) : Prop :=
  verified.worldEvidenceAccepted = true ∧
  verified.criterionPreregistered = true ∧
  verified.causalDesignAccepted = true

theorem externalOutcomeWitnessCarriesInstrumentAcceptance
    (verified : ExternalOutcomeSemanticWitness truth independent causal
      trajectory package proposal) :
    OutcomeInstrumentAccepted verified := by
  exact ⟨verified.worldEvidenceWasAccepted,
    verified.criterionWasPreregistered,
    verified.causalDesignWasAccepted⟩

theorem externalOutcomeWitnessMatchesClaimedAdmissionJudgment
    (accepted : ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter)
    (verified : ExternalOutcomeSemanticWitness truth independent causal
      trajectory package proposal) :
    verified.judgment = accepted.admissionConditions.judgment := by
  apply Option.some.inj
  calc
    some verified.judgment = package.judgment :=
      verified.judgmentPresent.symm
    _ = some accepted.admissionConditions.judgment :=
      accepted.admissionConditions.judgmentPresent

/-! ## Measured runtime LLM behavior improvement -/

structure LLMProbe where
  value : String
deriving Repr, DecidableEq

structure LLMResponse where
  value : String
deriving Repr, DecidableEq

abbrev RuntimeLLMBehavior (RuntimeState : Type) :=
  RuntimeState → LLMProbe → LLMResponse

abbrev BehaviorScore := LLMResponse → Nat

def RuntimeResponseTrace
    (behavior : RuntimeLLMBehavior RuntimeState)
    (runtimeState : RuntimeState)
    (sealedSuite : List LLMProbe) : List LLMResponse :=
  sealedSuite.map (behavior runtimeState)

def SuiteScore
    (behavior : RuntimeLLMBehavior RuntimeState)
    (score : BehaviorScore)
    (runtimeState : RuntimeState)
    (sealedSuite : List LLMProbe) : Nat :=
  (sealedSuite.map fun probe => score (behavior runtimeState probe)).sum

/-- Strict aggregate improvement on one nonempty frozen probe suite. -/
def BoundedBehaviorImprovement
    (behavior : RuntimeLLMBehavior RuntimeState)
    (score : BehaviorScore)
    (runtimeBefore runtimeAfter : RuntimeState)
    (sealedSuite : List LLMProbe) : Prop :=
  sealedSuite ≠ [] ∧
  SuiteScore behavior score runtimeBefore sealedSuite <
    SuiteScore behavior score runtimeAfter sealedSuite

abbrev RevisionBehaviorAttribution (RuntimeState : Type) :=
  RevisionProposal → RuntimeState → RuntimeState → List LLMProbe → Prop

/-- Exact aggregate before/after evaluation record for one sealed suite. -/
structure BehaviorEvaluationReceipt where
  suiteDigest : EvidenceDigest
  beforeModelConfigDigest : EvidenceDigest
  afterModelConfigDigest : EvidenceDigest
  beforeResponsesDigest : EvidenceDigest
  afterResponsesDigest : EvidenceDigest
  beforeStateDigest : StateDigest
  afterStateDigest : StateDigest
  evaluator : Principal
  suiteSize : Nat
  beforeSuiteScore : Nat
  afterSuiteScore : Nat
  sealedBeforeEvaluation : Bool
deriving Repr, DecidableEq

/--
Correspondence between an evaluation receipt and declared runtime invocation
semantics.  A future provider/evaluator adapter must supply these equalities;
Lean does not infer them from response bytes or a test label.
-/
structure RuntimeBehaviorMeasurementWitness
    (RuntimeState : Type)
    (abstractState : RuntimeState → CanonicalState)
    (digest : CanonicalState → StateDigest)
    (suiteDigestOf : List LLMProbe → EvidenceDigest)
    (modelConfigDigestOf : RuntimeState → EvidenceDigest)
    (responseTraceDigestOf : List LLMResponse → EvidenceDigest)
    (behavior : RuntimeLLMBehavior RuntimeState)
    (score : BehaviorScore)
    (trajectory : SealedTrajectory)
    (proposal : RevisionProposal)
    (runtimeBefore runtimeAfter : RuntimeState)
    (sealedSuite : List LLMProbe)
    (receipt : BehaviorEvaluationReceipt) where
  suiteWasSealed : receipt.sealedBeforeEvaluation = true
  suiteNonempty : sealedSuite ≠ []
  suiteDigestMatches : receipt.suiteDigest = suiteDigestOf sealedSuite
  suiteSizeMatches : receipt.suiteSize = sealedSuite.length
  beforeModelConfigMatches :
    receipt.beforeModelConfigDigest = modelConfigDigestOf runtimeBefore
  afterModelConfigMatches :
    receipt.afterModelConfigDigest = modelConfigDigestOf runtimeAfter
  modelConfigurationHeldFixed :
    receipt.beforeModelConfigDigest = receipt.afterModelConfigDigest
  beforeResponsesMatch :
    receipt.beforeResponsesDigest = responseTraceDigestOf
      (RuntimeResponseTrace behavior runtimeBefore sealedSuite)
  afterResponsesMatch :
    receipt.afterResponsesDigest = responseTraceDigestOf
      (RuntimeResponseTrace behavior runtimeAfter sealedSuite)
  beforeStateMatches :
    receipt.beforeStateDigest = digest (abstractState runtimeBefore)
  afterStateMatches :
    receipt.afterStateDigest = digest (abstractState runtimeAfter)
  beforeScoreMatches :
    receipt.beforeSuiteScore =
      SuiteScore behavior score runtimeBefore sealedSuite
  afterScoreMatches :
    receipt.afterSuiteScore =
      SuiteScore behavior score runtimeAfter sealedSuite
  strictAggregateGain :
    receipt.beforeSuiteScore < receipt.afterSuiteScore
  evaluatorNotActor : receipt.evaluator ≠ trajectory.actor
  evaluatorNotProposer : receipt.evaluator ≠ proposal.proposer

theorem matchingSuiteMeasurementYieldsBoundedScoreGain
    (measured : RuntimeBehaviorMeasurementWitness RuntimeState abstractState
      digest suiteDigestOf modelConfigDigestOf responseTraceDigestOf behavior
      score trajectory proposal runtimeBefore runtimeAfter sealedSuite receipt) :
    BoundedBehaviorImprovement behavior score runtimeBefore runtimeAfter
      sealedSuite := by
  refine ⟨measured.suiteNonempty, ?_⟩
  rw [← measured.beforeScoreMatches, ← measured.afterScoreMatches]
  exact measured.strictAggregateGain

theorem equalRuntimeResponsesGiveEqualSuiteScore
    (same : ∀ probe,
      probe ∈ sealedSuite →
      behavior runtimeBefore probe = behavior runtimeAfter probe) :
    SuiteScore behavior score runtimeBefore sealedSuite =
      SuiteScore behavior score runtimeAfter sealedSuite := by
  induction sealedSuite with
  | nil => simp [SuiteScore]
  | cons head tail inductionHypothesis =>
      have headSame :
          behavior runtimeBefore head = behavior runtimeAfter head :=
        same head (by simp)
      have tailSame : ∀ probe,
          probe ∈ tail →
          behavior runtimeBefore probe = behavior runtimeAfter probe := by
        intro probe present
        exact same probe (by simp [present])
      simpa [SuiteScore, headSame] using inductionHypothesis tailSame

theorem boundedImprovementImpliesBehaviorChange
    (improved : BoundedBehaviorImprovement behavior score
      runtimeBefore runtimeAfter sealedSuite) :
    ∃ probe,
      probe ∈ sealedSuite ∧
      behavior runtimeBefore probe ≠ behavior runtimeAfter probe := by
  apply Classical.byContradiction
  intro absent
  have same : ∀ probe,
      probe ∈ sealedSuite →
      behavior runtimeBefore probe = behavior runtimeAfter probe := by
    intro probe present
    apply Classical.byContradiction
    intro differs
    exact absent ⟨probe, present, differs⟩
  have equalScore := equalRuntimeResponsesGiveEqualSuiteScore
    (behavior := behavior) (score := score)
    (runtimeBefore := runtimeBefore) (runtimeAfter := runtimeAfter)
    (sealedSuite := sealedSuite) same
  exact (Nat.ne_of_lt improved.2) equalScore

/-! ## Integrated positive theorem and checked-in obstruction -/

/--
This conditional theorem composes all four assumption-carrying witness classes.
Its conclusion is bounded to the claimed execution certificate, exact outcome
package and sealed aggregate probe suite named by the premises.
-/
theorem conditionalEvidenceBundleYieldsBoundedClaim
    (accepted : ClaimedRuntimeAdmissionCertificate RuntimeState abstractState digest
      transitionInvariant state trajectory package proposal permit certificate
      commitWitness currentHead next nextHead runtimeBefore runtimeAfter)
    (authentication : PermitAuthenticationEvidence
      verify authorized activeAt accepted.execution.trace policyContext permit
        accepted.execution.issue)
    (signatureSound : SignatureVerifierSound verify signedBy)
    (verifiedOutcome : ExternalOutcomeSemanticWitness truth independent causal
      trajectory package proposal)
    (measuredBehavior : RuntimeBehaviorMeasurementWitness RuntimeState
      abstractState digest suiteDigestOf modelConfigDigestOf
      responseTraceDigestOf behavior score trajectory proposal runtimeBefore
      runtimeAfter sealedSuite receipt)
    (revisionAttribution : RevisionBehaviorAttribution RuntimeState)
    (attributed : revisionAttribution proposal runtimeBefore runtimeAfter
      sealedSuite) :
    ConditionalRuntimeStepRefinesAtomicAdmission RuntimeState
        accepted.concreteRuntimeStep accepted.execution.trace abstractState digest
        transitionInvariant state trajectory package proposal permit certificate
        commitWitness currentHead next nextHead runtimeBefore runtimeAfter ∧
    accepted.execution.certificateDigestSemantics accepted.execution.trace
      accepted.execution.trace.certificateDigest ∧
    (accepted.execution.canonicalCertificateBytesAccepted = true ∧
      accepted.execution.recoveredPostStateAccepted = true) ∧
    (∃ issue,
      issue ∈ accepted.execution.trace.permitIssues ∧
      ExactPermitIssue accepted.execution.trace issue permit) ∧
    (∃ key signature,
      AuthenticatedPermitAt signedBy authorized activeAt
        accepted.execution.trace policyContext permit accepted.execution.issue
        key signature) ∧
    accepted.execution.trace.successfulCommits.length = 1 ∧
    ExactRuntimeCommit accepted.execution.trace accepted.execution.commit
      commitWitness nextHead ∧
    (accepted.execution.issue.linearizationIndex <
      accepted.execution.commit.linearizationIndex ∧
      accepted.execution.commit.linearizationIndex <
        accepted.execution.trace.recoveryIndex) ∧
    OutcomeInstrumentAccepted verifiedOutcome ∧
    truth package.observation ∧
    verifiedOutcome.judgment = accepted.admissionConditions.judgment ∧
    IndependentCausalCredit independent causal trajectory package.observation
      verifiedOutcome.judgment proposal ∧
    revisionAttribution proposal runtimeBefore runtimeAfter sealedSuite ∧
    BoundedBehaviorImprovement behavior score runtimeBefore runtimeAfter
      sealedSuite := by
  have outcomeFacts :=
    externalOutcomeWitnessProjectsTruthAndCausalCredit verifiedOutcome
  exact ⟨claimedCertificateBridgeYieldsConditionalRefinement accepted,
    accepted.execution.certificateDigestBindsTrace,
    claimedCertificateChecksWereAccepted accepted.execution,
    claimedEvidenceContainsExactPermitIssue accepted.execution,
    soundVerifierAndKeyPolicyYieldPermitAuthentication
      accepted authentication signatureSound,
    claimedEvidenceHasOneDeclaredSuccessfulCommit accepted.execution,
    claimedEvidenceContainsExactRuntimeCommit accepted.execution,
    claimedEvidenceHasOrderedIssueCommitRecovery accepted.execution,
    externalOutcomeWitnessCarriesInstrumentAcceptance verifiedOutcome,
    outcomeFacts.1,
    externalOutcomeWitnessMatchesClaimedAdmissionJudgment
      accepted verifiedOutcome,
    outcomeFacts.2,
    attributed,
    matchingSuiteMeasurementYieldsBoundedScoreGain measuredBehavior⟩

/-- Exact readiness dimensions for the currently requested positive claim. -/
structure EndToEndReadinessProfile where
  failClosedObstructionPublished : Bool
  runtimeStateAbstractionPresent : Bool
  canonicalPermitIssueOccurrencePresent : Bool
  permitAuthenticationPresent : Bool
  oneCanonicalCommitOccurrencePresent : Bool
  externallyTrueOutcomeEvidencePresent : Bool
  independentCausalCreditPresent : Bool
  llmBehaviorImprovementEvidencePresent : Bool
deriving Repr, DecidableEq

def ReadyForEndToEndRuntimeRefinement
    (profile : EndToEndReadinessProfile) : Prop :=
  profile.runtimeStateAbstractionPresent = true ∧
  profile.canonicalPermitIssueOccurrencePresent = true ∧
  profile.permitAuthenticationPresent = true ∧
  profile.oneCanonicalCommitOccurrencePresent = true ∧
  profile.externallyTrueOutcomeEvidencePresent = true ∧
  profile.independentCausalCreditPresent = true ∧
  profile.llmBehaviorImprovementEvidencePresent = true

/--
Declared audit projection of the checked-in TypeScript/Effect ceiling.  This
definition is not extracted from, nor a semantics of, the TypeScript source.
-/
def checkedInTypeScriptEndToEndProfile : EndToEndReadinessProfile :=
  { failClosedObstructionPublished := true
    runtimeStateAbstractionPresent := false
    canonicalPermitIssueOccurrencePresent := false
    permitAuthenticationPresent := false
    oneCanonicalCommitOccurrencePresent := false
    externallyTrueOutcomeEvidencePresent := false
    independentCausalCreditPresent := false
    llmBehaviorImprovementEvidencePresent := false }

theorem checkedInTypeScriptPublishesOnlyObstruction :
    checkedInTypeScriptEndToEndProfile.failClosedObstructionPublished = true ∧
    checkedInTypeScriptEndToEndProfile.runtimeStateAbstractionPresent = false ∧
    checkedInTypeScriptEndToEndProfile.canonicalPermitIssueOccurrencePresent = false ∧
    checkedInTypeScriptEndToEndProfile.permitAuthenticationPresent = false ∧
    checkedInTypeScriptEndToEndProfile.oneCanonicalCommitOccurrencePresent = false ∧
    checkedInTypeScriptEndToEndProfile.externallyTrueOutcomeEvidencePresent = false ∧
    checkedInTypeScriptEndToEndProfile.independentCausalCreditPresent = false ∧
    checkedInTypeScriptEndToEndProfile.llmBehaviorImprovementEvidencePresent = false := by
  decide

theorem checkedInTypeScriptNotReadyForEndToEndRefinement :
    ¬ ReadyForEndToEndRuntimeRefinement
      checkedInTypeScriptEndToEndProfile := by
  simp [ReadyForEndToEndRuntimeRefinement,
    checkedInTypeScriptEndToEndProfile]

/-- Even all-true metadata is not a runtime or admission proof object. -/
def allTrueEndToEndReadinessProfile : EndToEndReadinessProfile :=
  { failClosedObstructionPublished := true
    runtimeStateAbstractionPresent := true
    canonicalPermitIssueOccurrencePresent := true
    permitAuthenticationPresent := true
    oneCanonicalCommitOccurrencePresent := true
    externallyTrueOutcomeEvidencePresent := true
    independentCausalCreditPresent := true
    llmBehaviorImprovementEvidencePresent := true }

def symbolicallyDeniedPermitDecision : PermitDecision :=
  { AtomicAdmission.Consistency.permitDecision with allowed := false }

def symbolicallyDeniedPermit : HeadBoundPermit :=
  { AtomicAdmission.Consistency.permit with
    decision := symbolicallyDeniedPermitDecision }

theorem booleanReadinessDoesNotEntailAtomicAdmission :
    ReadyForEndToEndRuntimeRefinement allTrueEndToEndReadinessProfile ∧
    ¬ AtomicLearnAdmission
      AtomicAdmission.Consistency.exampleDigest
      AtomicAdmission.Consistency.ExactSingleTargetInvariant
      AtomicAdmission.Consistency.initialState
      AtomicAdmission.Consistency.trajectory
      AtomicAdmission.Consistency.outcomePackage
      AtomicAdmission.Consistency.proposal
      symbolicallyDeniedPermit
      AtomicAdmission.Consistency.certificate
      AtomicAdmission.Consistency.commitWitness
      AtomicAdmission.Consistency.currentHead
      AtomicAdmission.Consistency.nextState
      AtomicAdmission.Consistency.nextHead := by
  constructor
  · simp [ReadyForEndToEndRuntimeRefinement,
      allTrueEndToEndReadinessProfile]
  · apply deniedPermitCannotAtomicAdmit
    rfl

end HSWM.CanonicalLearning.EndToEndRuntimeRefinement
