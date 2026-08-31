import Std

/-!
# DNRD-5 four-arm efficacy terminal boundary

This is a mechanism-specific, fail-closed classifier over already judged
evidence flags.  It neither validates those flags nor supplies an observed
occurrence or scientific result.
-/

namespace HSWM.DNRD5.EfficacyBoundary

inductive Arm where
  | active
  | outcomeIndependentSham
  | delayedNoCredit
  | exactW0Rollback
deriving Repr, DecidableEq

def armUniverse : List Arm :=
  [.active, .outcomeIndependentSham, .delayedNoCredit, .exactW0Rollback]

theorem armUniverseHasExactlyFourMembers : armUniverse.length = 4 := rfl

theorem armConstructorsArePairwiseDistinct :
    Arm.active ≠ Arm.outcomeIndependentSham ∧
    Arm.active ≠ Arm.delayedNoCredit ∧
    Arm.active ≠ Arm.exactW0Rollback ∧
    Arm.outcomeIndependentSham ≠ Arm.delayedNoCredit ∧
    Arm.outcomeIndependentSham ≠ Arm.exactW0Rollback ∧
    Arm.delayedNoCredit ≠ Arm.exactW0Rollback := by
  decide

structure BlockId where
  value : String
deriving Repr, DecidableEq

/-- Fixed fields provide exactly one sealed score slot for every typed arm. -/
structure SealedFourArmBlock where
  blockId : BlockId
  activeScore : Bool
  shamScore : Bool
  delayedScore : Bool
  rollbackScore : Bool
  sealedBeforeIndependentJudgment : Bool
deriving Repr, DecidableEq

structure OccurrenceIntegrity where
  sourceAndPreregistrationFrozen : Bool
  exactBlockUniverse : Bool
  exactOpaqueFourArmAssignment : Bool
  exactNineCallLedgerPerBlock : Bool
  activeShamAdmittedShapeMatched : Bool
  delayedOutcomeEscrowedUntilProbeSeals : Bool
  exactW0BehavioralRestore : Bool
  exclusionAndNoLeakage : Bool
  blindOutcomeAndProbeEvaluation : Bool
  independentJudgeReconstruction : Bool
  permitInvariantAdmissionPathBound : Bool
deriving Repr, DecidableEq

def OccurrenceIntegrity.passes (integrity : OccurrenceIntegrity) : Bool :=
  integrity.sourceAndPreregistrationFrozen && (
  integrity.exactBlockUniverse && (
  integrity.exactOpaqueFourArmAssignment && (
  integrity.exactNineCallLedgerPerBlock && (
  integrity.activeShamAdmittedShapeMatched && (
  integrity.delayedOutcomeEscrowedUntilProbeSeals && (
  integrity.exactW0BehavioralRestore && (
  integrity.exclusionAndNoLeakage && (
  integrity.blindOutcomeAndProbeEvaluation && (
  integrity.independentJudgeReconstruction &&
  integrity.permitInvariantAdmissionPathBound)))))))))

theorem integrityPassRequiresEveryCondition
    (integrity : OccurrenceIntegrity)
    (passed : integrity.passes = true) :
    integrity.sourceAndPreregistrationFrozen = true ∧
    integrity.exactBlockUniverse = true ∧
    integrity.exactOpaqueFourArmAssignment = true ∧
    integrity.exactNineCallLedgerPerBlock = true ∧
    integrity.activeShamAdmittedShapeMatched = true ∧
    integrity.delayedOutcomeEscrowedUntilProbeSeals = true ∧
    integrity.exactW0BehavioralRestore = true ∧
    integrity.exclusionAndNoLeakage = true ∧
    integrity.blindOutcomeAndProbeEvaluation = true ∧
    integrity.independentJudgeReconstruction = true ∧
    integrity.permitInvariantAdmissionPathBound = true := by
  simpa [OccurrenceIntegrity.passes] using passed

structure OperationalCompleteness where
  exactThreeHundredBlocks : Bool
  everyBlockHasFourSealedArmOutcomes : Bool
  noMissingProbeOrEvaluatorReceipt : Bool
deriving Repr, DecidableEq

def OperationalCompleteness.passes
    (completeness : OperationalCompleteness) : Bool :=
  completeness.exactThreeHundredBlocks &&
  (completeness.everyBlockHasFourSealedArmOutcomes &&
  completeness.noMissingProbeOrEvaluatorReceipt)

theorem completenessPassRequiresEveryCondition
    (completeness : OperationalCompleteness)
    (passed : completeness.passes = true) :
    completeness.exactThreeHundredBlocks = true ∧
    completeness.everyBlockHasFourSealedArmOutcomes = true ∧
    completeness.noMissingProbeOrEvaluatorReceipt = true := by
  simpa [OperationalCompleteness.passes] using passed

/-- The exact-test decision and asymptotic LCB decision stay separate. -/
structure ContrastGate where
  adjustedExactPAtMostPointZeroFive : Bool
  asymptoticSimultaneousLcbPositive : Bool
deriving Repr, DecidableEq

def ContrastGate.passes (gate : ContrastGate) : Bool :=
  gate.adjustedExactPAtMostPointZeroFive &&
  gate.asymptoticSimultaneousLcbPositive

theorem contrastPassRequiresBothStatisticalLayers
    (gate : ContrastGate)
    (passed : gate.passes = true) :
    gate.adjustedExactPAtMostPointZeroFive = true ∧
    gate.asymptoticSimultaneousLcbPositive = true := by
  simpa [ContrastGate.passes] using passed

structure MarkedOccurrenceSummary where
  integrity : OccurrenceIntegrity
  completeness : OperationalCompleteness
  activeVsSham : ContrastGate
  activeVsDelayed : ContrastGate
  activeVsRollback : ContrastGate
deriving Repr, DecidableEq

inductive OccurrenceEvidence where
  | premarkerRefusal
  | marked (summary : MarkedOccurrenceSummary)
deriving Repr, DecidableEq

inductive Terminal where
  | premarkerRefusal
  | voidProtocol
  | inconclusiveOccurrence
  | causalMacroplasticityGo
  | primarySignalMechanismIncomplete
  | validCausalNoGo
deriving Repr, DecidableEq

/-- Total precedence: integrity and completeness dominate all statistics. -/
def classify : OccurrenceEvidence → Terminal
  | .premarkerRefusal => .premarkerRefusal
  | .marked summary =>
      match summary.integrity.passes,
          summary.completeness.passes,
          summary.activeVsSham.passes,
          summary.activeVsDelayed.passes,
          summary.activeVsRollback.passes with
      | false, _, _, _, _ => .voidProtocol
      | true, false, _, _, _ => .inconclusiveOccurrence
      | true, true, true, true, true => .causalMacroplasticityGo
      | true, true, true, false, false =>
          .primarySignalMechanismIncomplete
      | true, true, _, _, _ => .validCausalNoGo

theorem premarkerRefusalCannotBeGo :
    classify .premarkerRefusal ≠ .causalMacroplasticityGo := by
  decide

theorem integrityFailureIsVoid
    (failed : summary.integrity.passes = false) :
    classify (.marked summary) = .voidProtocol := by
  simp [classify, failed]

theorem validMissingnessIsInconclusive
    (integrity : summary.integrity.passes = true)
    (incomplete : summary.completeness.passes = false) :
    classify (.marked summary) = .inconclusiveOccurrence := by
  simp [classify, integrity, incomplete]

structure ScientificGoConditions
    (summary : MarkedOccurrenceSummary) : Prop where
  integrityPassed : summary.integrity.passes = true
  operationallyComplete : summary.completeness.passes = true
  primaryPassed : summary.activeVsSham.passes = true
  delayedMechanismPassed : summary.activeVsDelayed.passes = true
  rollbackMechanismPassed : summary.activeVsRollback.passes = true

theorem goRequiresIntegrityCompletenessAndAllContrasts
    (classified :
      classify (.marked summary) = .causalMacroplasticityGo) :
    ScientificGoConditions summary := by
  have integrityPassed : summary.integrity.passes = true := by
    cases integrity : summary.integrity.passes
    · simp [classify, integrity] at classified
    · rfl
  have complete : summary.completeness.passes = true := by
    cases complete : summary.completeness.passes
    · simp [classify, integrityPassed, complete] at classified
    · rfl
  have primary : summary.activeVsSham.passes = true := by
    cases primary : summary.activeVsSham.passes
    · simp [classify, integrityPassed, complete, primary] at classified
    · rfl
  have delayed : summary.activeVsDelayed.passes = true := by
    cases delayed : summary.activeVsDelayed.passes
    · cases rollback : summary.activeVsRollback.passes <;>
        simp [classify, integrityPassed, complete, primary, delayed,
          rollback] at classified
    · rfl
  have rollback : summary.activeVsRollback.passes = true := by
    cases rollback : summary.activeVsRollback.passes
    · simp [classify, integrityPassed, complete, primary, delayed,
        rollback] at classified
    · rfl
  exact ⟨integrityPassed, complete, primary, delayed, rollback⟩

theorem allThreeCompleteGatesProduceGo
    (conditions : ScientificGoConditions summary) :
    classify (.marked summary) = .causalMacroplasticityGo := by
  simp [classify, conditions.integrityPassed,
    conditions.operationallyComplete, conditions.primaryPassed,
    conditions.delayedMechanismPassed,
    conditions.rollbackMechanismPassed]

theorem primaryExactLayerFailurePreventsGo
    (failed :
      summary.activeVsSham.adjustedExactPAtMostPointZeroFive = false) :
    classify (.marked summary) ≠ .causalMacroplasticityGo := by
  intro classified
  have primary :=
    (goRequiresIntegrityCompletenessAndAllContrasts classified).primaryPassed
  simp [ContrastGate.passes, failed] at primary

theorem primaryLcbFailurePreventsGo
    (failed :
      summary.activeVsSham.asymptoticSimultaneousLcbPositive = false) :
    classify (.marked summary) ≠ .causalMacroplasticityGo := by
  intro classified
  have primary :=
    (goRequiresIntegrityCompletenessAndAllContrasts classified).primaryPassed
  simp [ContrastGate.passes, failed] at primary

theorem delayedExactLayerFailurePreventsGo
    (failed :
      summary.activeVsDelayed.adjustedExactPAtMostPointZeroFive = false) :
    classify (.marked summary) ≠ .causalMacroplasticityGo := by
  intro classified
  have delayed :=
    (goRequiresIntegrityCompletenessAndAllContrasts classified).delayedMechanismPassed
  simp [ContrastGate.passes, failed] at delayed

theorem delayedLcbFailurePreventsGo
    (failed :
      summary.activeVsDelayed.asymptoticSimultaneousLcbPositive = false) :
    classify (.marked summary) ≠ .causalMacroplasticityGo := by
  intro classified
  have delayed :=
    (goRequiresIntegrityCompletenessAndAllContrasts classified).delayedMechanismPassed
  simp [ContrastGate.passes, failed] at delayed

theorem rollbackExactLayerFailurePreventsGo
    (failed :
      summary.activeVsRollback.adjustedExactPAtMostPointZeroFive = false) :
    classify (.marked summary) ≠ .causalMacroplasticityGo := by
  intro classified
  have rollback :=
    (goRequiresIntegrityCompletenessAndAllContrasts classified).rollbackMechanismPassed
  simp [ContrastGate.passes, failed] at rollback

theorem rollbackLcbFailurePreventsGo
    (failed :
      summary.activeVsRollback.asymptoticSimultaneousLcbPositive = false) :
    classify (.marked summary) ≠ .causalMacroplasticityGo := by
  intro classified
  have rollback :=
    (goRequiresIntegrityCompletenessAndAllContrasts classified).rollbackMechanismPassed
  simp [ContrastGate.passes, failed] at rollback

theorem primaryOnlyIsMechanismIncomplete
    (integrity : summary.integrity.passes = true)
    (complete : summary.completeness.passes = true)
    (primary : summary.activeVsSham.passes = true)
    (delayed : summary.activeVsDelayed.passes = false)
    (rollback : summary.activeVsRollback.passes = false) :
    classify (.marked summary) = .primarySignalMechanismIncomplete := by
  simp [classify, integrity, complete, primary, delayed, rollback]

theorem validCompletePrimaryFailureIsNoGo
    (integrity : summary.integrity.passes = true)
    (complete : summary.completeness.passes = true)
    (primary : summary.activeVsSham.passes = false) :
    classify (.marked summary) = .validCausalNoGo := by
  simp [classify, integrity, complete, primary]

theorem validCompletePartialMechanismPatternIsNoGo
    (integrity : summary.integrity.passes = true)
    (complete : summary.completeness.passes = true)
    (primary : summary.activeVsSham.passes = true)
    (delayed : summary.activeVsDelayed.passes = true)
    (rollback : summary.activeVsRollback.passes = false) :
    classify (.marked summary) = .validCausalNoGo := by
  simp [classify, integrity, complete, primary, delayed, rollback]

structure CheckedInReadinessProfile where
  designContractPresent : Bool
  diagnosticQualificationPresent : Bool
  preregisteredEfficacyOccurrencePresent : Bool
  sealedFourArmOutcomeSetPresent : Bool
  independentScientificJudgmentPresent : Bool
deriving Repr, DecidableEq

def ReadyForScientificTerminal
    (profile : CheckedInReadinessProfile) : Prop :=
  profile.designContractPresent = true ∧
  profile.diagnosticQualificationPresent = true ∧
  profile.preregisteredEfficacyOccurrencePresent = true ∧
  profile.sealedFourArmOutcomeSetPresent = true ∧
  profile.independentScientificJudgmentPresent = true

def checkedInReadinessProfile : CheckedInReadinessProfile :=
  { designContractPresent := true
    diagnosticQualificationPresent := true
    preregisteredEfficacyOccurrencePresent := false
    sealedFourArmOutcomeSetPresent := false
    independentScientificJudgmentPresent := false }

theorem checkedInEvidenceCannotIssueScientificTerminal :
    ¬ ReadyForScientificTerminal checkedInReadinessProfile := by
  simp [ReadyForScientificTerminal, checkedInReadinessProfile]

theorem diagnosticQualificationAloneCannotIssueScientificTerminal
    (noOccurrence :
      profile.preregisteredEfficacyOccurrencePresent = false) :
    ¬ ReadyForScientificTerminal profile := by
  intro ready
  rcases ready with ⟨_design, _diagnostic, occurrence,
    _outcomes, _judgment⟩
  simp [noOccurrence] at occurrence

end HSWM.DNRD5.EfficacyBoundary
