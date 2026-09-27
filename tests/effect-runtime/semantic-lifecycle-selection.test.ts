import { describe, expect, it } from "vitest"

import { selectLifecycleCandidate } from "../../src/hswm/effect-runtime/src/semantic-lifecycle-selection.js"
import { doorRuleCases } from "../../src/hswm/effect-runtime/src/semantic-rule-environment.js"

const relationKey = (arm: string) => ({ schemaVersion: "hswm:semantic-lifecycle:v1", lineageId: "lineage:semantic-lifecycle:v1", atomUid: "relation:door", revisionId: 1, arm })
const semantic = (trace: unknown = { sha256: "training-trace" }, outcome: unknown = { sha256: "training-outcome" }) => ({ semanticText: "fixture", disposition: "fixture", uncertainty: "fixture", exceptionRefs: ["exception:door"], trace, outcome })
const state = (arm: string, trace: unknown = { sha256: "training-trace" }, outcome: unknown = { sha256: "training-outcome" }) => ({ relationKey: relationKey(arm), canonicalSha256: `canonical-${arm}`, semantic: semantic(trace, outcome), frameSha256: `state-frame-${arm}` })
const development = (arm: "evidence_only" | "learned", predictions: ReadonlyArray<boolean | null>, labels = [true, false, true, true], refusal = false) => {
  const before = state(arm)
  const after = state(arm)
  const trace = refusal ? null : { frameSha256: `execution-frame-${arm}`, relationKey: after.relationKey }
  return {
  stage: "development", arm, before, after, canonicalUnchanged: true, trace, calls: refusal ? [] : [{ frameSha256: trace!.frameSha256, relationKey: after.relationKey }], assessment: {
    split: "development", denominator: 4, correct: predictions.filter((value, index) => value === labels[index]).length, incorrect: predictions.filter((value, index) => value !== labels[index]).length,
    parseFailures: predictions.filter(value => value === null).length, missingPredictions: 0, unknownCaseIds: [],
    observations: doorRuleCases("development").map((entry, index) => ({ caseId: entry.id, split: "development", prediction: predictions[index], observed: labels[index], correct: predictions[index] === labels[index] }))
  }
}}
const revision = (arm: "evidence_only" | "learned", committed = true, trace: unknown = { sha256: "training-trace" }, outcome: unknown = { sha256: "training-outcome" }) => ({ stage: "revise", arm, committed, after: state(arm, trace, outcome) })
const right = <A>(value: { readonly _tag: "Left" | "Right"; readonly right?: A }): A => { if (value._tag === "Left" || value.right === undefined) throw new Error("expected Right"); return value.right }
const leftCode = (value: { readonly _tag: "Left" | "Right"; readonly left?: { readonly code: string } }): string => { if (value._tag === "Right" || value.left === undefined) throw new Error("expected Left"); return value.left.code }

describe("semantic lifecycle noisy-feedback selection adapter", () => {
  it("ports the strict observed guard and serializes exact decimal masses", () => {
    const selected = right(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true]), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))
    expect(selected).toMatchObject({ selectedArm: "learned", applicability: "APPLICABLE", boundAuthority: "CALLER_DECLARED", guard: { currentObservedScore: "3", candidateObservedScore: "4", requiredCandidateObservedScore: "3", observedGuardPasses: true } })
    const retained = right(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true]), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "1" }))
    expect(retained).toMatchObject({ selectedArm: "evidence_only", applicability: "APPLICABLE", reason: "INSUFFICIENT_OBSERVED_MARGIN" })
  })

  it("retains current state without coercing null predictions, refusals, or failed revisions", () => {
    expect(right(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, null, true, true]), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))).toMatchObject({ applicability: "NOT_APPLICABLE", reason: "NULL_PREDICTION_OR_REFUSAL", selectedArm: "evidence_only" })
    expect(right(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true], [true, false, true, true], true), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))).toMatchObject({ applicability: "NOT_APPLICABLE", reason: "NULL_PREDICTION_OR_REFUSAL", selectedArm: "evidence_only" })
    expect(right(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true]), revision("evidence_only", false), revision("learned"), { allowance: "0", debit: "0" }))).toMatchObject({ applicability: "NOT_APPLICABLE", reason: "REVISION_NOT_COMMITTED" })
  })

  it("refuses split, label, and shared-evidence drift", () => {
    const badSplit = development("learned", [true, false, true, true])
    badSplit.assessment.observations[0]!.split = "heldout" as never
    expect(leftCode(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), badSplit, revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))).toBe("SELECTION_REPORT_INVALID")
    expect(leftCode(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true], [false, false, true, true]), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))).toBe("SELECTION_EVIDENCE_MISMATCH")
    expect(leftCode(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true]), revision("evidence_only"), revision("learned", true, { sha256: "other" }), { allowance: "0", debit: "0" }))).toBe("SELECTION_EVIDENCE_MISMATCH")
  })

  it("requires exact unchanged execution state, relation-bound trace receipts, and committed descriptors", () => {
    const changed = development("evidence_only", [true, true, true, true])
    changed.after.canonicalSha256 = "changed" as never
    expect(leftCode(selectLifecycleCandidate(changed, development("learned", [true, false, true, true]), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))).toBe("SELECTION_REPORT_INVALID")
    const wrongReceipt = development("evidence_only", [true, true, true, true])
    wrongReceipt.calls[0]!.frameSha256 = "wrong" as never
    expect(leftCode(selectLifecycleCandidate(wrongReceipt, development("learned", [true, false, true, true]), revision("evidence_only"), revision("learned"), { allowance: "0", debit: "0" }))).toBe("SELECTION_REPORT_INVALID")
    expect(leftCode(selectLifecycleCandidate(development("evidence_only", [true, true, true, true]), development("learned", [true, false, true, true]), revision("evidence_only", true, null), revision("learned"), { allowance: "0", debit: "0" }))).toBe("SELECTION_REVISION_INVALID")
  })
})
