import Std

set_option linter.unusedSimpArgs false

/-!
# A finite, role-sensitive semantic-weight learning witness

This file proves facts about one bounded mathematical construction.  Its
environment is a resettable, deterministic Boolean truth table.  `env` is
called only after `step` emits its trace; no definition of `step` can inspect
`env`.  This is neither an LLM refinement nor a proof of the full HSWM target.

The three named input fields are intentionally not an unordered set.  A table
learner receives all eight predeclared interventions, and learns a genuine
three-way Boolean operator.  The full history may remain a provenance record;
`summary` is only a sufficient read view for this learner.
-/

namespace HSWM.FiniteSemanticLearning

/-- A role-bearing ternary incidence, not an unordered three-element set. -/
structure Input where
  source : Bool
  modulator : Bool
  context : Bool
deriving DecidableEq, Repr

/-- The finite, predeclared intervention domain. -/
def allInputs : List Input :=
  [ ⟨false, false, false⟩, ⟨true, false, false⟩,
    ⟨false, true, false⟩, ⟨true, true, false⟩,
    ⟨false, false, true⟩, ⟨true, false, true⟩,
    ⟨false, true, true⟩, ⟨true, true, true⟩ ]

/-- The external, fixed target relation.  It is not stored in the learner. -/
abbrev Env := Input → Bool

/-- A partial learned disposition table. -/
abbrev Table := Input → Option Bool

def empty : Table := fun _ => none

/-- Learn exactly the observed coordinate, leaving every other coordinate alone. -/
def observe (table : Table) (input : Input) (outcome : Bool) : Table :=
  fun input' => if input' = input then some outcome else table input'

/-- Unknown entries have a fixed, declared fallback rather than an oracle value. -/
def predict (table : Table) (input : Input) : Bool :=
  (table input).getD false

/-- Step can read only the learned table and a role-bearing input. -/
def step (table : Table) (input : Input) : Bool × Input :=
  (predict table input, input)

/-- Env is evaluated after `step` has emitted its pre-outcome trace value. -/
def env (truth : Env) (trace : Bool × Input) : Bool := truth trace.2

structure Record where
  input : Input
  outcome : Bool
deriving DecidableEq, Repr

/-- Learn consumes a post-Step record; it has no argument of type `Env`. -/
def learn (table : Table) (record : Record) : Table :=
  observe table record.input record.outcome

def summary (history : List Record) : Table :=
  history.foldl learn empty

/--
One complete dataflow: Step emits a pre-outcome trace, Env evaluates that trace,
and Learn receives only the resulting record.  This is a mathematical value
flow, not a cryptographic seal, receipt, admission, or I/O enforcement claim.
-/
def episode (table : Table) (input : Input) (truth : Env) : Table :=
  let trace := step table input
  learn table { input := trace.2, outcome := env truth trace }

/-- The eight predeclared interventions query each possible role-bearing input. -/
def train (truth : Env) : Table :=
  allInputs.foldl (fun table input => episode table input truth) empty

theorem observe_here (table : Table) (input : Input) (outcome : Bool) :
    observe table input outcome input = some outcome := by
  simp [observe]

theorem observe_other (table : Table) {input other : Input} (h : other ≠ input)
    (outcome : Bool) : observe table input outcome other = table other := by
  simp [observe, h]

/-- `step` does not depend on an environment truth table. -/
theorem step_reads_only_table_and_input (table : Table) (input : Input) :
    step table input = (predict table input, input) := rfl

/-- One complete intervention sweep exactly reconstructs every Boolean truth table. -/
theorem train_complete (truth : Env) (input : Input) :
    train truth input = some (truth input) := by
  cases input with
  | mk source modulator context =>
    cases source <;> cases modulator <;> cases context <;>
      simp [train, allInputs, episode, learn, step, env, observe]

theorem learned_prediction_exact (truth : Env) (input : Input) :
    predict (train truth) input = truth input := by
  simp [predict, train_complete]

/-- Number of wrong answers over the declared finite intervention domain. -/
def errors (truth : Env) (table : Table) : Nat :=
  (allInputs.filter (fun input => decide (predict table input ≠ truth input))).length

theorem learned_errors_zero (truth : Env) : errors truth (train truth) = 0 := by
  simp [errors, allInputs, learned_prediction_exact]

/-- A genuine third-order target relation. -/
def cubic : Env := fun input => input.source && input.modulator && input.context

theorem cubic_empty_has_one_error : errors cubic empty = 1 := by decide

theorem cubic_learning_strictly_improves :
    errors cubic (train cubic) < errors cubic empty := by
  rw [learned_errors_zero, cubic_empty_has_one_error]
  decide

/-- Boolean addition over GF(2). -/
abbrev xor (left right : Bool) : Bool := left != right

def i000 : Input := ⟨false, false, false⟩
def i100 : Input := ⟨true, false, false⟩
def i010 : Input := ⟨false, true, false⟩
def i110 : Input := ⟨true, true, false⟩
def i001 : Input := ⟨false, false, true⟩
def i101 : Input := ⟨true, false, true⟩
def i011 : Input := ⟨false, true, true⟩
def i111 : Input := ⟨true, true, true⟩

/-- The eight Boolean Möbius/ANF coefficients, in subset order. -/
structure ANF where
  one : Bool
  source : Bool
  modulator : Bool
  sourceModulator : Bool
  context : Bool
  sourceContext : Bool
  modulatorContext : Bool
  sourceModulatorContext : Bool
deriving Repr, DecidableEq

def coefficients (truth : Env) : ANF where
  one := truth i000
  source := xor (truth i100) (truth i000)
  modulator := xor (truth i010) (truth i000)
  sourceModulator := xor (xor (truth i110) (truth i100))
    (xor (truth i010) (truth i000))
  context := xor (truth i001) (truth i000)
  sourceContext := xor (xor (truth i101) (truth i100))
    (xor (truth i001) (truth i000))
  modulatorContext := xor (xor (truth i011) (truth i010))
    (xor (truth i001) (truth i000))
  sourceModulatorContext :=
    xor (xor (xor (truth i111) (truth i110)) (xor (truth i101) (truth i100)))
      (xor (xor (truth i011) (truth i010)) (xor (truth i001) (truth i000)))

/-- Evaluate the role-sensitive Boolean polynomial at an incidence. -/
def evalANF (polynomial : ANF) (input : Input) : Bool :=
  xor polynomial.one <|
  xor (polynomial.source && input.source) <|
  xor (polynomial.modulator && input.modulator) <|
  xor (polynomial.sourceModulator && input.source && input.modulator) <|
  xor (polynomial.context && input.context) <|
  xor (polynomial.sourceContext && input.source && input.context) <|
  xor (polynomial.modulatorContext && input.modulator && input.context)
    (polynomial.sourceModulatorContext && input.source && input.modulator && input.context)

/-- The eight finite Boolean-cube cases used by Möbius inversion. -/
private theorem anf_at_000 (truth : Env) :
    evalANF (coefficients truth) i000 = truth i000 := by
  cases h000 : truth i000 <;>
    unfold evalANF coefficients <;> rw [h000] <;> simp [xor, i000]

private theorem anf_at_100 (truth : Env) :
    evalANF (coefficients truth) i100 = truth i100 := by
  cases h000 : truth i000 <;> cases h100 : truth i100 <;>
    unfold evalANF coefficients <;> rw [h000, h100] <;> simp [xor, i000, i100]

private theorem anf_at_010 (truth : Env) :
    evalANF (coefficients truth) i010 = truth i010 := by
  cases h000 : truth i000 <;> cases h010 : truth i010 <;>
    unfold evalANF coefficients <;> rw [h000, h010] <;> simp [xor, i000, i010]

private theorem anf_at_110 (truth : Env) :
    evalANF (coefficients truth) i110 = truth i110 := by
  cases h000 : truth i000 <;> cases h100 : truth i100 <;>
  cases h010 : truth i010 <;> cases h110 : truth i110 <;>
    unfold evalANF coefficients <;> rw [h000, h100, h010, h110] <;>
    simp [xor, i000, i100, i010, i110]

private theorem anf_at_001 (truth : Env) :
    evalANF (coefficients truth) i001 = truth i001 := by
  cases h000 : truth i000 <;> cases h001 : truth i001 <;>
    unfold evalANF coefficients <;> rw [h000, h001] <;> simp [xor, i000, i001]

private theorem anf_at_101 (truth : Env) :
    evalANF (coefficients truth) i101 = truth i101 := by
  cases h000 : truth i000 <;> cases h100 : truth i100 <;>
  cases h001 : truth i001 <;> cases h101 : truth i101 <;>
    unfold evalANF coefficients <;> rw [h000, h100, h001, h101] <;>
    simp [xor, i000, i100, i001, i101]

private theorem anf_at_011 (truth : Env) :
    evalANF (coefficients truth) i011 = truth i011 := by
  cases h000 : truth i000 <;> cases h010 : truth i010 <;>
  cases h001 : truth i001 <;> cases h011 : truth i011 <;>
    unfold evalANF coefficients <;> rw [h000, h010, h001, h011] <;>
    simp [xor, i000, i010, i001, i011]

private theorem anf_at_111 (truth : Env) :
    evalANF (coefficients truth) i111 = truth i111 := by
  cases h000 : truth i000 <;> cases h100 : truth i100 <;>
  cases h010 : truth i010 <;> cases h110 : truth i110 <;>
  cases h001 : truth i001 <;> cases h101 : truth i101 <;>
  cases h011 : truth i011 <;> cases h111 : truth i111 <;>
    unfold evalANF coefficients <;>
    rw [h000, h100, h010, h110, h001, h101, h011, h111] <;>
    simp [xor, i000, i100, i010, i110, i001, i101, i011, i111]

/-- Exact Boolean Möbius inversion on the eight-point ternary cube. -/
theorem anf_reconstructs (truth : Env) (input : Input) :
    evalANF (coefficients truth) input = truth input := by
  rcases input with ⟨source, modulator, context⟩
  cases source <;> cases modulator <;> cases context
  · exact anf_at_000 truth
  · exact anf_at_001 truth
  · exact anf_at_010 truth
  · exact anf_at_011 truth
  · exact anf_at_100 truth
  · exact anf_at_101 truth
  · exact anf_at_110 truth
  · exact anf_at_111 truth

/-- The learned table and its derived ANF denote the same relation after training. -/
theorem learned_anf_exact (truth : Env) (input : Input) :
    evalANF (coefficients fun x => predict (train truth) x) input = truth input := by
  rw [anf_reconstructs]
  exact learned_prediction_exact truth input

/-- The polynomial realization reads exactly the same partial learned table as direct Step. -/
def semanticStep (table : Table) (input : Input) : Bool :=
  evalANF (coefficients fun x => predict table x) input

theorem semanticStep_eq_step (table : Table) (input : Input) :
    semanticStep table input = (step table input).1 := by
  unfold semanticStep step
  rw [anf_reconstructs]

theorem cubic_has_pure_triple_coefficient :
    let p := coefficients cubic
    p.one = false ∧ p.source = false ∧ p.modulator = false ∧
      p.sourceModulator = false ∧ p.context = false ∧
      p.sourceContext = false ∧ p.modulatorContext = false ∧
      p.sourceModulatorContext = true := by
  decide

/-- A role-specific relation: source has a different semantic effect from modulator. -/
def sourceOnly : Env := fun input => input.source

theorem source_role_is_not_modulator_role :
    sourceOnly ⟨true, false, false⟩ = true ∧
      sourceOnly ⟨false, true, false⟩ = false := by decide

/-- Learning after a history extension is precisely an observation of its summary. -/
theorem summary_append (history : List Record) (record : Record) :
    summary (history ++ [record]) = learn (summary history) record := by
  simp [summary, List.foldl_append]

def duplicate : Record := ⟨i000, true⟩

/-- The execution summary is non-injective: duplicate evidence has the same table. -/
theorem summary_noninjective :
    [duplicate] ≠ [duplicate, duplicate] ∧
      summary [duplicate] = summary [duplicate, duplicate] := by
  constructor
  · decide
  · funext input
    by_cases h : input = i000
    · subst input
      simp [summary, duplicate, learn, observe, empty]
    · simp [summary, duplicate, learn, observe, empty, h]

/-- A same-class parent Boolean operator may consume a learned child output. -/
def plugSource (parent : Env) (child : Table) (input : Input) : Bool :=
  parent ⟨predict child input, input.modulator, input.context⟩

/-- Exact child learning is preserved by every Boolean parent under typed substitution. -/
theorem substitution_preserves_learned_output (parent truth : Env) (input : Input) :
    plugSource parent (train truth) input =
      parent ⟨truth input, input.modulator, input.context⟩ := by
  simp [plugSource, learned_prediction_exact]

/-- Composition executed through two learned tables, rather than a truth table executor. -/
def composeSemanticSteps (parent child : Table) (input : Input) : Bool :=
  semanticStep parent
    ⟨semanticStep child input, input.modulator, input.context⟩

theorem both_learned_substitution (parentTruth childTruth : Env) (input : Input) :
    composeSemanticSteps (train parentTruth) (train childTruth) input =
      parentTruth ⟨childTruth input, input.modulator, input.context⟩ := by
  unfold composeSemanticSteps
  rw [semanticStep_eq_step, semanticStep_eq_step]
  simp [step, learned_prediction_exact]

end HSWM.FiniteSemanticLearning
