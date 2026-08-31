import HSWMDnrd5EfficacyBoundary

/-!
# DNRD-5 exact paired sign gate

The exact upper binomial tail and three-way Bonferroni threshold are represented
with natural numbers only.  The asymptotic LCB remains a separate input.
-/

namespace HSWM.DNRD5.ExactSignGate

open EfficacyBoundary

/-- Adjacent sums used to construct the next finite Pascal row. -/
def adjacentSums : List Nat → List Nat
  | first :: second :: rest =>
      (first + second) :: adjacentSums (second :: rest)
  | _ => []

def nextPascalRow (row : List Nat) : List Nat :=
  1 :: (adjacentSums row ++ [1])

/-- Dynamic Pascal rows avoid the exponential naive recursive evaluator. -/
def pascalRow : Nat → List Nat
  | 0 => [1]
  | n + 1 => nextPascalRow (pascalRow n)

def listAtOrZero : List Nat → Nat → Nat
  | [], _ => 0
  | value :: _, 0 => value
  | _ :: rest, index + 1 => listAtOrZero rest index

def natChoose (n k : Nat) : Nat :=
  listAtOrZero (pascalRow n) k

/-- Sum `choose m k` from `start` through `start + remaining`. -/
def binomialTailFrom (m start : Nat) : Nat → Nat
  | 0 => natChoose m start
  | remaining + 1 =>
      natChoose m start + binomialTailFrom m (start + 1) remaining

/-- Inclusive `k >= activeWins` numerator, or zero for invalid `w > m`. -/
def binomialTailNumerator (discordant activeWins : Nat) : Nat :=
  if activeWins ≤ discordant then
    binomialTailFrom discordant activeWins (discordant - activeWins)
  else
    0

theorem thresholdChooseIsIncluded
    (valid : activeWins ≤ discordant) :
    natChoose discordant activeWins ≤
      binomialTailNumerator discordant activeWins := by
  have chooseLeTail : ∀ remaining,
      natChoose discordant activeWins ≤
        binomialTailFrom discordant activeWins remaining := by
    intro remaining
    cases remaining <;> simp [binomialTailFrom]
  simp [binomialTailNumerator, valid, chooseLeTail]

/-- Generic nonnegative fraction comparison by cross multiplication. -/
def FractionAtMost
    (numerator denominator thresholdNumerator thresholdDenominator : Nat) :
    Prop :=
  numerator * thresholdDenominator ≤ thresholdNumerator * denominator

theorem threeWayBonferroniThresholdIsIntegerInequality
    (tail denominator : Nat) :
    FractionAtMost (3 * tail) denominator 1 20 ↔
      60 * tail ≤ denominator := by
  simp [FractionAtMost]
  omega

structure ContrastCounts where
  activeWins : Nat
  controlWins : Nat
  ties : Nat
deriving Repr, DecidableEq

def ContrastCounts.discordant (counts : ContrastCounts) : Nat :=
  counts.activeWins + counts.controlWins

def ContrastCounts.sampleSize (counts : ContrastCounts) : Nat :=
  counts.discordant + counts.ties

def ExactBonferroniCriterion (counts : ContrastCounts) : Prop :=
  counts.activeWins ≤ counts.discordant ∧
  60 * binomialTailNumerator counts.discordant counts.activeWins ≤
    2 ^ counts.discordant

def exactBonferroniPass (counts : ContrastCounts) : Bool :=
  decide (counts.activeWins ≤ counts.discordant) &&
  decide (60 * binomialTailNumerator counts.discordant counts.activeWins ≤
    2 ^ counts.discordant)

theorem exactBonferroniPassTrueIff :
    exactBonferroniPass counts = true ↔
      ExactBonferroniCriterion counts := by
  simp [exactBonferroniPass, ExactBonferroniCriterion]

theorem exactBonferroniPassFalseIff :
    exactBonferroniPass counts = false ↔
      ¬ ExactBonferroniCriterion counts := by
  simp [exactBonferroniPass, ExactBonferroniCriterion]

theorem exactGateDoesNotDependOnTies
    (activeWins controlWins firstTies secondTies : Nat) :
    exactBonferroniPass
      { activeWins := activeWins
        controlWins := controlWins
        ties := firstTies } =
    exactBonferroniPass
      { activeWins := activeWins
        controlWins := controlWins
        ties := secondTies } := by
  rfl

def allTiesThreeHundred : ContrastCounts :=
  { activeWins := 0
    controlWins := 0
    ties := 300 }

theorem zeroDiscordanceDoesNotPass :
    exactBonferroniPass allTiesThreeHundred = false := by
  native_decide

def fiveAllActiveWins : ContrastCounts :=
  { activeWins := 5
    controlWins := 0
    ties := 0 }

def sixAllActiveWins : ContrastCounts :=
  { activeWins := 6
    controlWins := 0
    ties := 0 }

theorem fiveAllActiveWinsFailBonferroniThreshold :
    exactBonferroniPass fiveAllActiveWins = false := by
  native_decide

theorem sixAllActiveWinsPassBonferroniThreshold :
    exactBonferroniPass sixAllActiveWins = true := by
  native_decide

/-! Frozen `analysis_v1.json` count projections. -/

def knownSmallTail : ContrastCounts :=
  { activeWins := 2
    controlWins := 1
    ties := 0 }

theorem knownSmallTailNumeratorAndDenominator :
    binomialTailNumerator knownSmallTail.discordant
        knownSmallTail.activeWins = 4 ∧
    2 ^ knownSmallTail.discordant = 8 := by
  native_decide

theorem knownSmallTailDoesNotPassBonferroni :
    exactBonferroniPass knownSmallTail = false := by
  native_decide

def frozenGoCounts : ContrastCounts :=
  { activeWins := 300
    controlWins := 0
    ties := 0 }

theorem frozenGoExactLayerPasses :
    exactBonferroniPass frozenGoCounts = true := by
  native_decide

def frozenMechanismIncompletePrimaryCounts : ContrastCounts :=
  { activeWins := 220
    controlWins := 0
    ties := 80 }

theorem frozenMechanismIncompletePrimaryExactLayerPasses :
    exactBonferroniPass frozenMechanismIncompletePrimaryCounts = true := by
  native_decide

def frozenNontrivialLargeTail : ContrastCounts :=
  { activeWins := 180
    controlWins := 120
    ties := 0 }

theorem frozenNontrivialLargeTailExactLayerPasses :
    exactBonferroniPass frozenNontrivialLargeTail = true := by
  native_decide

def frozenLcbPositiveExactFails : ContrastCounts :=
  { activeWins := 5
    controlWins := 0
    ties := 295 }

theorem frozenLcbPositiveExactLayerStillFails :
    exactBonferroniPass frozenLcbPositiveExactFails = false := by
  native_decide

/-- Preserve the exact arithmetic decision; accept LCB only as another layer. -/
def contrastGateFromCounts
    (counts : ContrastCounts)
    (asymptoticLcbPositive : Bool) : ContrastGate :=
  { adjustedExactPAtMostPointZeroFive := exactBonferroniPass counts
    asymptoticSimultaneousLcbPositive := asymptoticLcbPositive }

theorem contrastGateFromCountsPassesIff :
    (contrastGateFromCounts counts asymptoticLcbPositive).passes = true ↔
      ExactBonferroniCriterion counts ∧ asymptoticLcbPositive = true := by
  simp [contrastGateFromCounts, ContrastGate.passes,
    exactBonferroniPassTrueIff]

def summaryWithPrimaryCounts
    (summary : MarkedOccurrenceSummary)
    (counts : ContrastCounts)
    (asymptoticLcbPositive : Bool) : MarkedOccurrenceSummary :=
  { summary with
    activeVsSham := contrastGateFromCounts counts asymptoticLcbPositive }

theorem primaryExactArithmeticFailurePreventsScientificGo
    (failed : ¬ ExactBonferroniCriterion counts) :
    classify (.marked
      (summaryWithPrimaryCounts summary counts asymptoticLcbPositive)) ≠
        .causalMacroplasticityGo := by
  apply primaryExactLayerFailurePreventsGo
  have exactFalse : exactBonferroniPass counts = false :=
    exactBonferroniPassFalseIff.mpr failed
  simpa [summaryWithPrimaryCounts, contrastGateFromCounts] using exactFalse

end HSWM.DNRD5.ExactSignGate
