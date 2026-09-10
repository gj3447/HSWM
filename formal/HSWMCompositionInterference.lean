import Std

/-!
# A finite composition-interference witness

This contains two finite counterexamples to unqualified composition rules.  The
first is an intentionally limited shared-outcome overwrite example.  The second
has a common objective and shows stale local improvements can jointly decrease
that objective.  It is a model-level obstruction only: it neither refutes HSWM
composition nor supplies a cognitive or performance claim.
-/

namespace HSWMCompositionInterference

/-- The two actions made by the cells in one macro step. -/
abbrev JointAction := Bool × Bool

/-- The macro environment rewards disagreement. -/
def reward : JointAction → Bool
  | (left, right) => left != right

/-- A naive member uses the one shared outcome as its next local action. -/
def overwriteFromSharedOutcome (outcome : Bool) : Bool := outcome

/-- Parallel composition of the two naive local updates. -/
def parallelUpdate (action : JointAction) : JointAction :=
  let outcome := reward action
  (overwriteFromSharedOutcome outcome, overwriteFromSharedOutcome outcome)

/-- In isolation, each cell's action has the expected local outcome. -/
def isolatedReward (action : Bool) : Bool := action

example : isolatedReward false = false := rfl
example : isolatedReward true = true := rfl

/-- The composed update is stuck at the all-false state. -/
theorem allFalse_is_fixed : parallelUpdate (false, false) = (false, false) := by
  rfl

/-- Yet a permitted joint deviation has strictly better macro outcome. -/
theorem allFalse_is_not_macro_optimal :
    reward (false, false) = false ∧ reward (true, false) = true := by
  decide

/-- Hence one parallel shared-outcome update does not reach this improvement. -/
theorem update_misses_available_improvement :
    reward (parallelUpdate (false, false)) = false ∧ reward (true, false) = true := by
  decide

/-- A common macro objective for the stale-local-improvement witness. -/
def commonUtility : JointAction → Nat
  | (false, false) => 1
  | (true, false) => 2
  | (false, true) => 2
  | (true, true) => 0

/-- The two coordinate proposals have disjoint writes. -/
def proposeLeft : JointAction → JointAction
  | (_, right) => (true, right)

def proposeRight : JointAction → JointAction
  | (left, _) => (left, true)

/-- Both updates are strict improvements only relative to the stale state `(0,0)`. -/
theorem stale_unilateral_improvements :
    commonUtility (proposeLeft (false, false)) > commonUtility (false, false) ∧
    commonUtility (proposeRight (false, false)) > commonUtility (false, false) := by
  decide

/-- Their disjoint coordinate writes commute, but their joint meaning is harmful. -/
theorem commuting_writes_have_negative_semantic_interaction :
    proposeRight (proposeLeft (false, false)) =
      proposeLeft (proposeRight (false, false)) ∧
    commonUtility (proposeRight (proposeLeft (false, false))) <
      commonUtility (false, false) := by
  decide

/-- Compare the model's exact tabulated utility; this is not a learned evaluator. -/
def acceptIfStrictlyBetter (current candidate : JointAction) : JointAction :=
  if commonUtility candidate > commonUtility current then candidate else current

/-- Re-evaluate with the same exact utility table after the first accepted update. -/
def serialReevaluate : JointAction → JointAction := fun current =>
  let afterLeft := acceptIfStrictlyBetter current (proposeLeft current)
  acceptIfStrictlyBetter afterLeft (proposeRight afterLeft)

/-- The actual comparison accepts `(1,0)`, rejects the stale second proposal `(1,1)`, and obtains utility two. -/
theorem serial_reevaluation_accepts_then_rejects :
    acceptIfStrictlyBetter (false, false) (proposeLeft (false, false)) = (true, false) ∧
    acceptIfStrictlyBetter (true, false) (proposeRight (true, false)) = (true, false) ∧
    serialReevaluate (false, false) = (true, false) ∧
    commonUtility (serialReevaluate (false, false)) = 2 := by
  decide

/-- The interaction term of a two-by-two common-utility table. -/
def interaction (u00 u10 u01 u11 : Int) : Int :=
  u11 - u10 - u01 + u00

/-- Joint gain decomposes into two stale unilateral gains and interaction. -/
theorem joint_gain_decomposition (u00 u10 u01 u11 : Int) :
    u11 - u00 =
      (u10 - u00) + (u01 - u00) + interaction u00 u10 u01 u11 := by
  simp [interaction]
  omega

/-- In the additive lane, two strict unilateral gains imply a strict joint gain. -/
theorem additive_strict_gains_imply_joint_gain
    (u00 u10 u01 u11 : Int)
    (additive : interaction u00 u10 u01 u11 = 0)
    (leftGain : u10 - u00 > 0)
    (rightGain : u01 - u00 > 0) :
    u11 - u00 > 0 := by
  calc
    u11 - u00 =
        (u10 - u00) + (u01 - u00) + interaction u00 u10 u01 u11 :=
      joint_gain_decomposition u00 u10 u01 u11
    _ > 0 := by rw [additive]; omega

/-- The common-utility countertable has gains one and interaction negative three. -/
theorem countertable_has_negative_interaction :
    interaction 1 2 2 0 = -3 ∧
    2 - 1 = (1 : Int) ∧
    0 - 1 = (-1 : Int) := by
  decide

end HSWMCompositionInterference
