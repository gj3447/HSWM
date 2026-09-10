import Std

/-!
  A finite, exact-arithmetic boundary for §5 of the constructive-realizability
  program.  An `Int` is an integer number of fixed rational-grid units; choosing
  the grid denominator is outside this file.  There is deliberately no
  probability, Hoeffding, or fresh-draw assertion here.
-/

namespace HSWMFiniteSelection

structure Candidate where
  index : Nat
  empirical : Int
deriving DecidableEq, Repr

/-- The deterministic empirical maximizer. `List.maxOn?` is left-leaning on ties. -/
def select (candidates : List Candidate) : Option Candidate :=
  candidates.maxOn? Candidate.empirical

/-- The strictly-more-than-two-error-units acceptance rule. -/
abbrev accepted (chosen baseline : Candidate) (epsilon : Int) : Prop :=
  epsilon + epsilon < chosen.empirical - baseline.empirical

/-- Retain the baseline when the empirically best candidate is not accepted. -/
def update (candidates : List Candidate) (baseline : Candidate) (epsilon : Int) : Candidate :=
  match select candidates with
  | some chosen => if accepted chosen baseline epsilon then chosen else baseline
  | none => baseline

/-- `select` is an actual argmax: every listed score is no larger than its score. -/
theorem select_argmax {candidates : List Candidate} {chosen : Candidate}
    (hchosen : select candidates = some chosen) {x : Candidate} (hx : x ∈ candidates) :
    x.empirical ≤ chosen.empirical := by
  unfold select at hchosen
  have h := List.le_apply_get_maxOn?_of_mem (f := Candidate.empirical) hx
  simpa [hchosen] using h

/-- A selected candidate is one of the fixed finite candidates. -/
theorem select_member {candidates : List Candidate} {chosen : Candidate}
    (hchosen : select candidates = some chosen) : chosen ∈ candidates := by
  exact List.maxOn?_mem hchosen

/-- Every nonempty fixed candidate list computes a selected candidate. -/
theorem select_exists {candidates : List Candidate} (hnil : candidates ≠ []) :
    ∃ chosen, select candidates = some chosen := by
  have hs : (select candidates).isSome := by
    unfold select
    exact List.isSome_maxOn?_iff.mpr hnil
  exact Option.isSome_iff_exists.mp hs

/-- Uniform error on the fixed integer grid, written as its two exact bounds. -/
abbrev UniformError (truth : Candidate → Int) (epsilon : Int) (candidates : List Candidate) : Prop :=
  ∀ x ∈ candidates,
    truth x - epsilon ≤ x.empirical ∧ x.empirical ≤ truth x + epsilon

/-- On the uniform-error event, an accepted selected update has positive true gain. -/
theorem accepted_has_true_gain (truth : Candidate → Int) {candidates : List Candidate} {chosen baseline : Candidate}
    {epsilon : Int} (hchosen : select candidates = some chosen)
    (hbase : baseline ∈ candidates) (herr : UniformError truth epsilon candidates)
    (haccept : accepted chosen baseline epsilon) :
    0 < truth chosen - truth baseline := by
  unfold accepted at haccept
  have hc :=
    herr chosen (select_member hchosen)
  have hb := herr baseline hbase
  have hbase : truth baseline ≤ baseline.empirical + epsilon := by
    calc
      truth baseline = (truth baseline - epsilon) + epsilon :=
        (Int.sub_add_cancel _ _).symm
      _ ≤ baseline.empirical + epsilon := Int.add_le_add_right hb.1 _
  have hbase' : truth baseline + epsilon ≤
      baseline.empirical + (epsilon + epsilon) := by
    simpa [Int.add_assoc] using Int.add_le_add_right hbase epsilon
  have haccept' : baseline.empirical + (epsilon + epsilon) < chosen.empirical := by
    have h := Int.add_lt_add_left haccept baseline.empirical
    calc
      baseline.empirical + (epsilon + epsilon) <
          baseline.empirical + (chosen.empirical - baseline.empirical) := h
      _ = chosen.empirical := by
        rw [Int.add_comm baseline.empirical, Int.sub_add_cancel]
  have h : truth baseline + epsilon < truth chosen + epsilon :=
    Int.lt_of_le_of_lt hbase' (Int.lt_of_lt_of_le haccept' hc.2)
  exact Int.sub_pos.mpr ((Int.add_lt_add_iff_right epsilon).mp h)

/-- Empirical maximization loses at most two error units against any fixed candidate. -/
theorem selected_near_any_candidate (truth : Candidate → Int) {candidates : List Candidate} {chosen x : Candidate}
    {epsilon : Int} (hchosen : select candidates = some chosen) (hx : x ∈ candidates)
    (herr : UniformError truth epsilon candidates) :
    truth x ≤ truth chosen + 2 * epsilon := by
  have hmax := select_argmax hchosen hx
  have hc :=
    herr chosen (select_member hchosen)
  have hxerr := herr x hx
  have hxbound : truth x ≤ x.empirical + epsilon := by
    calc
      truth x = (truth x - epsilon) + epsilon := (Int.sub_add_cancel _ _).symm
      _ ≤ x.empirical + epsilon := Int.add_le_add_right hxerr.1 _
  calc
    truth x ≤ x.empirical + epsilon := hxbound
    _ ≤ chosen.empirical + epsilon := Int.add_le_add_right hmax _
    _ ≤ truth chosen + (epsilon + epsilon) := by
      simpa [Int.add_assoc] using Int.add_le_add_right hc.2 epsilon
    _ = truth chosen + 2 * epsilon := by rw [Int.two_mul]

/-- A true candidate gap above four error units forces acceptance of the selected update. -/
theorem gap_forces_acceptance (truth : Candidate → Int) {candidates : List Candidate} {chosen baseline improving : Candidate}
    {epsilon : Int} (hchosen : select candidates = some chosen)
    (hbase : baseline ∈ candidates) (himproving : improving ∈ candidates)
    (herr : UniformError truth epsilon candidates)
    (hgap : epsilon + epsilon + epsilon + epsilon < truth improving - truth baseline) :
    accepted chosen baseline epsilon := by
  have hmax := select_argmax hchosen himproving
  have hc :=
    herr chosen (select_member hchosen)
  have hb := herr baseline hbase
  have hi := herr improving himproving
  have hbaseplus : baseline.empirical + (epsilon + epsilon + epsilon) ≤
      truth baseline + (epsilon + epsilon + epsilon + epsilon) := by
    have h := Int.add_le_add_right hb.2 (epsilon + epsilon + epsilon)
    simpa [Int.add_assoc] using h
  have hgap' : truth baseline + (epsilon + epsilon + epsilon + epsilon) <
      truth improving := by
    have h := Int.add_lt_add_left hgap (truth baseline)
    calc
      truth baseline + (epsilon + epsilon + epsilon + epsilon) <
          truth baseline + (truth improving - truth baseline) := h
      _ = truth improving := by
        rw [Int.add_comm (truth baseline), Int.sub_add_cancel]
  have himproving : truth improving ≤ improving.empirical + epsilon := by
    calc
      truth improving = (truth improving - epsilon) + epsilon :=
        (Int.sub_add_cancel _ _).symm
      _ ≤ improving.empirical + epsilon := Int.add_le_add_right hi.1 _
  have hthree : baseline.empirical + (epsilon + epsilon + epsilon) <
      improving.empirical + epsilon :=
    Int.lt_of_le_of_lt hbaseplus (Int.lt_of_lt_of_le hgap' himproving)
  have htwo : baseline.empirical + (epsilon + epsilon) < improving.empirical := by
    apply (Int.add_lt_add_iff_right epsilon).mp
    simpa [Int.add_assoc] using hthree
  unfold accepted
  apply (Int.add_lt_add_iff_left baseline.empirical).mp
  calc
    baseline.empirical + (epsilon + epsilon) < improving.empirical := htwo
    _ ≤ chosen.empirical := hmax
    _ = baseline.empirical + (chosen.empirical - baseline.empirical) := by
      rw [Int.add_comm baseline.empirical, Int.sub_add_cancel]

/-- The computed update itself is improving when the finite true-score gap exceeds four errors. -/
theorem gap_forces_improving_update (truth : Candidate → Int) {candidates : List Candidate}
    {chosen baseline improving : Candidate} {epsilon : Int}
    (hchosen : select candidates = some chosen) (hbase : baseline ∈ candidates)
    (himproving : improving ∈ candidates) (herr : UniformError truth epsilon candidates)
    (hgap : epsilon + epsilon + epsilon + epsilon < truth improving - truth baseline) :
    update candidates baseline epsilon = chosen ∧ 0 < truth chosen - truth baseline := by
  have ha := gap_forces_acceptance truth hchosen hbase himproving herr hgap
  constructor
  · simp [update, hchosen, ha]
  · exact accepted_has_true_gain truth hchosen hbase herr ha

/-- A caller need not supply a chosen witness: the executable update improves. -/
theorem available_gap_improves_computed_update (truth : Candidate → Int)
    {candidates : List Candidate} {baseline improving : Candidate} {epsilon : Int}
    (hbase : baseline ∈ candidates) (himproving : improving ∈ candidates)
    (herr : UniformError truth epsilon candidates)
    (hgap : epsilon + epsilon + epsilon + epsilon < truth improving - truth baseline) :
    0 < truth (update candidates baseline epsilon) - truth baseline := by
  have hnonempty : candidates ≠ [] := by
    intro hnil
    simp [hnil] at hbase
  obtain ⟨chosen, hchosen⟩ := select_exists hnonempty
  obtain ⟨hupdate, hgain⟩ :=
    gap_forces_improving_update truth hchosen hbase himproving herr hgap
  simpa only [hupdate] using hgain

/-- An ordinary text/program learner using exactly this rule makes exactly this choice. -/
def ordinarySameRule (candidates : List Candidate) : Option Candidate := select candidates

theorem ordinary_same_rule_equivalence (candidates : List Candidate) :
    ordinarySameRule candidates = select candidates := rfl

/-- Computable non-vacuity witness: baseline score 1, alternative score 3, zero error. -/
def witnessBaseline : Candidate := ⟨0, 1⟩
def witnessImproving : Candidate := ⟨1, 3⟩
def witnessCandidates : List Candidate := [witnessBaseline, witnessImproving]
def witnessTruth : Candidate → Int := fun c => if c.index = 0 then 1 else 3

example : select witnessCandidates = some witnessImproving := by rfl
example : UniformError witnessTruth 0 witnessCandidates := by decide
example : accepted witnessImproving witnessBaseline 0 := by decide
example : 0 < witnessTruth witnessImproving - witnessTruth witnessBaseline := by decide
theorem witness_update_improves :
    update witnessCandidates witnessBaseline 0 = witnessImproving ∧
      0 < witnessTruth witnessImproving - witnessTruth witnessBaseline := by decide

/-- Equal-score counterexample: the leftmost tied candidate is selected and no update is accepted. -/
def equalBaseline : Candidate := ⟨0, 7⟩
def equalOther : Candidate := ⟨1, 7⟩
def equalCandidates : List Candidate := [equalBaseline, equalOther]
def equalTruth : Candidate → Int := fun _ => 7

example : select equalCandidates = some equalBaseline := by rfl
example : ¬ accepted equalBaseline equalBaseline 0 := by decide
example : update equalCandidates equalBaseline 0 = equalBaseline := by rfl
theorem equal_score_no_gain_counterexample :
    update equalCandidates equalBaseline 0 = equalBaseline ∧
      ¬ (0 < equalTruth equalOther - equalTruth equalBaseline) := by decide

end HSWMFiniteSelection
