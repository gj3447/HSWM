import HSWMAtomicAdmission

/-!
# HSWM atomic-admission consistency witness

This finite symbolic model proves that the head-bound atomic-admission
conditions are jointly satisfiable.  It proves specification non-vacuity only;
the strings below are not authenticated principals, runtime records, external
outcomes, causal-credit evidence, or scientific observations.
-/

namespace HSWM.CanonicalLearning.AtomicAdmission.Consistency

open OutcomeJudgment

def actor : Principal := ⟨"principal/actor"⟩
def proposer : Principal := ⟨"principal/proposer"⟩
def targetOwner : Principal := ⟨"principal/target-owner"⟩
def observationOwner : Principal := ⟨"principal/observation-owner"⟩
def evaluator : Principal := ⟨"principal/evaluator"⟩
def judgmentOwner : Principal := ⟨"principal/judgment-owner"⟩
def adjudicator : Principal := ⟨"principal/adjudicator"⟩
def permitOwner : Principal := ⟨"principal/permit-owner"⟩
def authorizer : Principal := ⟨"principal/authorizer"⟩
def invariantOwner : Principal := ⟨"principal/invariant-owner"⟩
def validator : Principal := ⟨"principal/validator"⟩

def target : AtomAddress :=
  { schemaVersion := "schema/example-v1"
    lineageId := "lineage/example"
    atomUid := "atom/example" }

def otherTarget : AtomAddress :=
  { schemaVersion := "schema/example-v1"
    lineageId := "lineage/other"
    atomUid := "atom/other" }

def revision0 : RevisionId := ⟨"revision/0"⟩
def revision1 : RevisionId := ⟨"revision/1"⟩
def trace : TraceId := ⟨"trace/example"⟩
def authorization : AuthorizationRef := ⟨"authorization/example"⟩
def scope : Scope := ⟨"scope/example"⟩

def beforeVersion : AtomVersion :=
  { revisionId := revision0
    responsibilityOwner := targetOwner
    provenanceTrace := none }

def initialState : CanonicalState :=
  { current := fun address =>
      if address = target then some beforeVersion else none
    history := [] }

def trajectory : SealedTrajectory :=
  { traceId := trace
    actor := actor
    sealedBeforeOutcome := true }

def proposal : RevisionProposal :=
  { target := target
    expectedRevision := revision0
    candidateRevision := revision1
    proposer := proposer
    traceId := trace
    authorizationRef := authorization
    scope := scope }

def observation : OutcomeObservation :=
  { observationId := ⟨"observation/example"⟩
    traceId := trace
    responsibilityOwner := observationOwner
    evaluator := evaluator
    value := .observed
    evidenceDigest := ⟨"digest/observation"⟩ }

def judgment : RevisionSupportJudgment :=
  { judgmentId := ⟨"judgment/example"⟩
    traceId := trace
    observationId := observation.observationId
    target := target
    expectedRevision := revision0
    candidateRevision := revision1
    responsibilityOwner := judgmentOwner
    adjudicator := adjudicator
    criterionDigest := ⟨"digest/criterion"⟩
    verdict := .supports
    evidenceDigest := ⟨"digest/judgment"⟩ }

def outcomePackage : OutcomeEvidencePackage :=
  { observation := observation
    judgment := some judgment }

theorem judgmentConditions :
    JudgmentConditions trajectory observation proposal judgment :=
  { proposalTraceMatches := rfl
    observationTraceMatches := rfl
    judgmentTraceMatches := rfl
    judgmentObservationMatches := rfl
    judgmentTargetMatches := rfl
    judgmentExpectedRevisionMatches := rfl
    judgmentCandidateRevisionMatches := rfl
    observationEvaluatorNotActor := by decide
    observationEvaluatorNotProposer := by decide
    observationOwnerNotActor := by decide
    observationOwnerNotProposer := by decide
    adjudicatorNotActor := by decide
    adjudicatorNotProposer := by decide
    judgmentOwnerNotActor := by decide
    judgmentOwnerNotProposer := by decide
    ownersSeparated := by decide
    evaluatorAndAdjudicatorSeparated := by decide
    judgmentSupports := rfl }

def permitDecision : PermitDecision :=
  { authorizationRef := authorization
    authorizer := authorizer
    target := target
    traceId := trace
    scope := scope
    allowed := true
    activeAtDecision := true }

def nextState : CanonicalState :=
  initialState.revise beforeVersion proposal

/-- A nontrivial exact single-target transition invariant, not constant `True`. -/
def ExactSingleTargetInvariant
    (state : CanonicalState)
    (candidate : RevisionProposal)
    (next : CanonicalState) : Prop :=
  ∃ currentVersion,
    state.current candidate.target = some currentVersion ∧
    next = state.revise currentVersion candidate

theorem initialTargetIsCurrent :
    initialState.current target = some beforeVersion := by
  simp [initialState]

theorem exactInvariantHolds :
    ExactSingleTargetInvariant initialState proposal nextState := by
  exact ⟨beforeVersion, initialTargetIsCurrent, rfl⟩

def abstractAdmissionConditions : AdmissionConditions
    initialState trajectory (judgmentAsOutcomeReceipt judgment) proposal
    permitDecision
    (fun pre candidate => ExactSingleTargetInvariant pre candidate nextState) :=
  { currentVersion := beforeVersion
    targetCurrent := initialTargetIsCurrent
    expectedRevisionMatches := rfl
    candidateRevisionIsNew := by decide
    trajectoryWasSealed := rfl
    proposalTraceMatches := rfl
    outcomeTraceMatches := rfl
    evaluatorNotActor := by decide
    evaluatorNotProposer := by decide
    outcomeOwnerNotActor := by decide
    outcomeOwnerNotProposer := by decide
    outcomeSupportsRevision := rfl
    permitAuthorizationMatches := rfl
    permitTargetMatches := rfl
    permitTraceMatches := rfl
    permitScopeMatches := rfl
    permitAllows := rfl
    permitIsActive := rfl
    invariantHolds := exactInvariantHolds }

theorem abstractLearn : Learn
    (fun pre candidate => ExactSingleTargetInvariant pre candidate nextState)
    initialState trajectory (judgmentAsOutcomeReceipt judgment) proposal
    permitDecision nextState :=
  .admit abstractAdmissionConditions

theorem outcomeLearning : LearnFromOutcomeEvidence
    (fun pre candidate => ExactSingleTargetInvariant pre candidate nextState)
    initialState trajectory outcomePackage proposal permitDecision nextState :=
  .admit judgment rfl judgmentConditions abstractLearn

def stateDigest0 : StateDigest := ⟨"state-digest/0"⟩
def stateDigest1 : StateDigest := ⟨"state-digest/1"⟩

/-- Distinguishes this example's predecessor from its exact revised state. -/
def exampleDigest (state : CanonicalState) : StateDigest :=
  if state.current target = some beforeVersion then stateDigest0
  else stateDigest1

theorem initialDigestMatches : exampleDigest initialState = stateDigest0 := by
  simp [exampleDigest, initialTargetIsCurrent]

theorem revisedVersionDiffers :
    revisedVersion beforeVersion proposal ≠ beforeVersion := by
  decide

theorem nextTargetIsRevised :
    nextState.current target = some (revisedVersion beforeVersion proposal) := by
  simp [nextState, CanonicalState.revise, proposal]

theorem nextDigestMatches : exampleDigest nextState = stateDigest1 := by
  simp [exampleDigest, nextTargetIsRevised, revisedVersionDiffers]

def currentHead : HeadSnapshot :=
  { lineageId := "journal/example"
    sequence := 0
    stateDigest := stateDigest0
    recordDigest := ⟨"record/genesis"⟩ }

def nextHead : HeadSnapshot :=
  { lineageId := "journal/example"
    sequence := 1
    stateDigest := stateDigest1
    recordDigest := ⟨"record/revision-1"⟩ }

def permit : HeadBoundPermit :=
  { responsibilityOwner := permitOwner
    decision := permitDecision
    head := currentHead
    expectedRevision := revision0
    candidateRevision := revision1
    contentDigest := ⟨"digest/permit"⟩ }

def certificate : HeadBoundInvariantCertificate :=
  { responsibilityOwner := invariantOwner
    validator := validator
    head := currentHead
    target := target
    expectedRevision := revision0
    candidateRevision := revision1
    contentDigest := ⟨"digest/invariant"⟩ }

def commitWitness : AdmissionCommitWitness :=
  { predecessorHead := currentHead
    successorHead := nextHead
    target := target
    expectedRevision := revision0
    candidateRevision := revision1
    consumedPermitDigest := permit.contentDigest
    consumedInvariantDigest := certificate.contentDigest }

def atomicConditions : AtomicAdmissionConditions
    exampleDigest ExactSingleTargetInvariant initialState trajectory
    outcomePackage proposal permit certificate commitWitness currentHead
    nextState nextHead :=
  { currentVersion := beforeVersion
    targetCurrent := initialTargetIsCurrent
    judgment := judgment
    judgmentPresent := rfl
    outcomeLearning := outcomeLearning
    stateDigestMatches := by
      simpa [currentHead] using initialDigestMatches
    permitHeadMatches := rfl
    invariantHeadMatches := rfl
    commitPredecessorMatches := rfl
    commitSuccessorMatches := rfl
    permitExpectedRevisionMatches := rfl
    permitCandidateRevisionMatches := rfl
    invariantTargetMatches := rfl
    invariantExpectedRevisionMatches := rfl
    invariantCandidateRevisionMatches := rfl
    commitTargetMatches := rfl
    commitExpectedRevisionMatches := rfl
    commitCandidateRevisionMatches := rfl
    commitConsumesPermit := rfl
    commitConsumesInvariant := rfl
    successorLineageMatches := rfl
    successorIsNext := rfl
    nextStateDigestMatches := by
      simpa [nextHead] using nextDigestMatches
    authorizerNotActor := by decide
    authorizerNotProposer := by decide
    authorizerNotTargetOwner := by decide
    authorizerNotAdjudicator := by decide
    authorizerNotJudgmentOwner := by decide
    authorizerNotPermitOwner := by decide }

theorem exampleAtomicAdmission : AtomicLearnAdmission
    exampleDigest ExactSingleTargetInvariant initialState trajectory
    outcomePackage proposal permit certificate commitWitness currentHead
    nextState nextHead :=
  .admit atomicConditions

/-- The specification relation is inhabited by one fully bound finite model. -/
theorem atomicAdmissionRelationIsNonempty :
    ∃ next nextHead,
      AtomicLearnAdmission exampleDigest ExactSingleTargetInvariant initialState
        trajectory outcomePackage proposal permit certificate commitWitness
        currentHead next nextHead := by
  exact ⟨nextState, nextHead, exampleAtomicAdmission⟩

theorem exampleHasExactRevisionOwnerAndHistory :
    nextState.current target =
        some (revisedVersion beforeVersion proposal) ∧
    (revisedVersion beforeVersion proposal).revisionId = revision1 ∧
    (revisedVersion beforeVersion proposal).responsibilityOwner = targetOwner ∧
    nextState.history = (target, beforeVersion) :: initialState.history := by
  exact ⟨nextTargetIsRevised, rfl, rfl, rfl⟩

theorem examplePreservesOtherTarget :
    nextState.current otherTarget = initialState.current otherTarget := by
  exact atomicAdmissionChangesOnlyTarget exampleAtomicAdmission otherTarget
    (by decide)

end HSWM.CanonicalLearning.AtomicAdmission.Consistency
