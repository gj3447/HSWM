/**
 * Strict adapter from lifecycle development reports to the finite observed
 * selection guard.  It has no access to an environment truth function.
 */
import { Either } from "effect"

import { lifecycleFailure, type LifecycleError } from "./semantic-lifecycle-domain.js"
import { doorRuleCases } from "./semantic-rule-environment.js"
import { selectSemanticLearningCandidate } from "./semantic-learning-selection-domain.js"

export const SEMANTIC_LIFECYCLE_SELECTION_V1 = "hswm-semantic-lifecycle-selection/v1" as const

export interface LifecycleSelectionInput {
  readonly allowance: string
  readonly debit: string
}

export interface LifecycleSelectionReport {
  readonly contract: typeof SEMANTIC_LIFECYCLE_SELECTION_V1
  readonly selectedArm: "evidence_only" | "learned"
  readonly applicability: "APPLICABLE" | "NOT_APPLICABLE"
  readonly reason: string
  readonly boundAuthority: "CALLER_DECLARED"
  readonly guard: Readonly<{
    readonly allowance: string
    readonly debit: string
    readonly totalMass: string | null
    readonly currentObservedScore: string | null
    readonly candidateObservedScore: string | null
    readonly requiredCandidateObservedScore: string | null
    readonly observedGuardPasses: boolean | null
  }>
  readonly claimCeiling: "FINITE_DECLARED_BOUND_SELECTION_NOT_GENERALIZATION_OR_RUNTIME_REFINEMENT"
}

type JsonRecord = Readonly<Record<string, unknown>>
const exactNatural = (value: unknown): bigint | null =>
  typeof value === "string" && /^(?:0|[1-9][0-9]*)$/.test(value) ? BigInt(value) : null
const record = (value: unknown): JsonRecord | null =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? value as JsonRecord : null
const error = (code: string, detail: string): Either.Either<never, LifecycleError> =>
  Either.left(lifecycleFailure(code, detail))
const same = (left: unknown, right: unknown): boolean => JSON.stringify(left) === JSON.stringify(right)

interface Development {
  readonly predictions: Readonly<Record<string, boolean | null>>
  readonly labels: ReadonlyArray<{ readonly id: string; readonly observed: boolean }>
  readonly state: StateBinding
  readonly hasNullPredictionOrRefusal: boolean
}

interface StateBinding {
  readonly raw: JsonRecord
  readonly relationKey: JsonRecord
  readonly canonicalSha256: string
  readonly semantic: JsonRecord
}
interface Revision {
  readonly committed: boolean
  readonly after: StateBinding
  readonly trace: JsonRecord | null
  readonly outcome: JsonRecord | null
}

const stateBinding = (value: unknown, detail: string): Either.Either<StateBinding, LifecycleError> => {
  const raw = record(value)
  const relationKey = raw === null ? null : record(raw["relationKey"])
  const semantic = raw === null ? null : record(raw["semantic"])
  const canonicalSha256 = raw === null ? null : raw["canonicalSha256"]
  if (raw === null || relationKey === null || semantic === null || typeof canonicalSha256 !== "string") {
    return error("SELECTION_REPORT_INVALID", detail)
  }
  return Either.right(Object.freeze({ raw, relationKey, canonicalSha256, semantic }))
}

const sameStateBinding = (left: StateBinding, right: StateBinding): boolean =>
  left.canonicalSha256 === right.canonicalSha256 && same(left.relationKey, right.relationKey) && same(left.semantic, right.semantic)

const reportDevelopment = (raw: unknown, arm: "evidence_only" | "learned"): Either.Either<Development, LifecycleError> => {
  const root = record(raw)
  if (root === null || root["stage"] !== "development" || root["arm"] !== arm) return error("SELECTION_REPORT_INVALID", "expected the declared development arm report")
  const assessment = record(root["assessment"])
  const before = stateBinding(root["before"], "development report lacks a complete pre-execution canonical state")
  if (Either.isLeft(before)) return Either.left(before.left)
  const after = stateBinding(root["after"], "development report lacks a complete post-execution canonical state")
  if (Either.isLeft(after)) return Either.left(after.left)
  if (root["canonicalUnchanged"] !== true || !same(before.right.raw, after.right.raw)) return error("SELECTION_REPORT_INVALID", "development execution must retain an exactly unchanged canonical state")
  if (assessment === null || assessment["split"] !== "development" || assessment["denominator"] !== 4) return error("SELECTION_REPORT_INVALID", "development report has an invalid assessment")
  const rawTrace = root["trace"]
  const trace = rawTrace === null ? null : record(rawTrace)
  if (rawTrace !== null && trace === null) return error("SELECTION_REPORT_INVALID", "development trace must be an object or null for a refusal")
  if (trace !== null) {
    if (typeof trace["frameSha256"] !== "string" || !same(trace["relationKey"], after.right.relationKey)) return error("SELECTION_REPORT_INVALID", "development trace is not bound to the executed state relation")
    const calls = root["calls"]
    if (!Array.isArray(calls) || calls.length === 0) return error("SELECTION_REPORT_INVALID", "a non-refused development trace requires transport call receipts")
    for (const call of calls) {
      const receipt = record(call)
      if (receipt === null || receipt["frameSha256"] !== trace["frameSha256"] || !same(receipt["relationKey"], after.right.relationKey)) return error("SELECTION_REPORT_INVALID", "development transport receipt is not bound to its trace frame and relation")
    }
  }
  const observations = assessment["observations"]
  const expected = doorRuleCases("development")
  if (!Array.isArray(observations) || observations.length !== expected.length) return error("SELECTION_REPORT_INVALID", "development report must retain the exact full denominator")
  const predictions: Record<string, boolean | null> = {}
  const labels: Array<{ id: string; observed: boolean }> = []
  let hasNullPrediction = trace === null
  for (let index = 0; index < expected.length; index += 1) {
    const row = record(observations[index])
    const expectedCase = expected[index]
    if (expectedCase === undefined || row === null || row["caseId"] !== expectedCase.id || row["split"] !== "development" || typeof row["observed"] !== "boolean" || (row["prediction"] !== null && typeof row["prediction"] !== "boolean")) return error("SELECTION_REPORT_INVALID", "development observations must have exact ordered case ids, split, labels, and nullable Boolean predictions")
    const prediction = row["prediction"]
    if (row["correct"] !== (prediction === row["observed"])) return error("SELECTION_REPORT_INVALID", "development observation correctness must equal its exact nullable prediction and observed label")
    predictions[expectedCase.id] = prediction
    labels.push({ id: expectedCase.id, observed: row["observed"] })
    hasNullPrediction ||= prediction === null
  }
  const correct = labels.filter(({ id, observed }) => predictions[id] === observed).length
  const parseFailures = Object.values(predictions).filter((value) => value === null).length
  if (assessment["correct"] !== correct || assessment["incorrect"] !== expected.length - correct || assessment["parseFailures"] !== parseFailures || assessment["missingPredictions"] !== 0 || !Array.isArray(assessment["unknownCaseIds"]) || assessment["unknownCaseIds"].length !== 0) return error("SELECTION_REPORT_INVALID", "development assessment totals are inconsistent or include non-development rows")
  return Either.right(Object.freeze({ predictions: Object.freeze(predictions), labels: Object.freeze(labels), state: after.right, hasNullPredictionOrRefusal: hasNullPrediction }))
}

const reportRevision = (raw: unknown, arm: "evidence_only" | "learned"): Either.Either<Revision, LifecycleError> => {
  const root = record(raw)
  if (root === null || root["stage"] !== "revise" || root["arm"] !== arm || typeof root["committed"] !== "boolean") return error("SELECTION_REVISION_INVALID", "expected the declared revision arm report")
  const after = stateBinding(root["after"], "revision report lacks a complete post-revision semantic state")
  if (Either.isLeft(after)) return Either.left(after.left)
  const rawTrace = after.right.semantic["trace"], rawOutcome = after.right.semantic["outcome"]
  const trace = rawTrace === null ? null : record(rawTrace)
  const outcome = rawOutcome === null ? null : record(rawOutcome)
  if ((rawTrace !== null && trace === null) || (rawOutcome !== null && outcome === null)) return error("SELECTION_REVISION_INVALID", "revision evidence descriptors must be objects or null")
  if (root["committed"] === true && (trace === null || outcome === null)) return error("SELECTION_REVISION_INVALID", "a committed revision requires non-null trace and outcome descriptors")
  return Either.right(Object.freeze({ committed: root["committed"], after: after.right, trace, outcome }))
}

const notApplicable = (allowance: bigint, debit: bigint, reason: string): LifecycleSelectionReport => Object.freeze({
  contract: SEMANTIC_LIFECYCLE_SELECTION_V1, selectedArm: "evidence_only", applicability: "NOT_APPLICABLE", reason,
  boundAuthority: "CALLER_DECLARED", guard: Object.freeze({ allowance: allowance.toString(), debit: debit.toString(), totalMass: null, currentObservedScore: null, candidateObservedScore: null, requiredCandidateObservedScore: null, observedGuardPasses: null }),
  claimCeiling: "FINITE_DECLARED_BOUND_SELECTION_NOT_GENERALIZATION_OR_RUNTIME_REFINEMENT"
})

/**
 * Applies Lean's observed-score guard only to exact, bound development rows.
 * A malformed report is refused; a refused prediction or failed revision is a
 * valid non-applicable outcome that retains the current evidence-only state.
 */
export const selectLifecycleCandidate = (
  currentReport: unknown,
  candidateReport: unknown,
  currentRevision: unknown,
  candidateRevision: unknown,
  selection: LifecycleSelectionInput
): Either.Either<LifecycleSelectionReport, LifecycleError> => {
  const allowance = exactNatural(selection.allowance), debit = exactNatural(selection.debit)
  if (allowance === null || debit === null) return error("SELECTION_BOUND_INVALID", "selection allowance and debit must be exact nonnegative decimal integers")
  const current = reportDevelopment(currentReport, "evidence_only")
  if (Either.isLeft(current)) return Either.left(current.left)
  const candidate = reportDevelopment(candidateReport, "learned")
  if (Either.isLeft(candidate)) return Either.left(candidate.left)
  if (!same(current.right.labels, candidate.right.labels)) return error("SELECTION_EVIDENCE_MISMATCH", "development reports do not bind the same ordered observed evidence")
  const currentRevisionValue = reportRevision(currentRevision, "evidence_only")
  if (Either.isLeft(currentRevisionValue)) return Either.left(currentRevisionValue.left)
  const candidateRevisionValue = reportRevision(candidateRevision, "learned")
  if (Either.isLeft(candidateRevisionValue)) return Either.left(candidateRevisionValue.left)
  if (!currentRevisionValue.right.committed || !candidateRevisionValue.right.committed) return Either.right(notApplicable(allowance, debit, "REVISION_NOT_COMMITTED"))
  if (!sameStateBinding(current.right.state, currentRevisionValue.right.after) || !sameStateBinding(candidate.right.state, candidateRevisionValue.right.after)) return error("SELECTION_EVIDENCE_MISMATCH", "development state does not equal its revision post-state canonical binding")
  if (currentRevisionValue.right.trace === null || currentRevisionValue.right.outcome === null || candidateRevisionValue.right.trace === null || candidateRevisionValue.right.outcome === null) return error("SELECTION_REVISION_INVALID", "committed revisions require non-null trace and outcome descriptors")
  if (!same(currentRevisionValue.right.trace, candidateRevisionValue.right.trace) || !same(currentRevisionValue.right.outcome, candidateRevisionValue.right.outcome)) return error("SELECTION_EVIDENCE_MISMATCH", "revision reports do not bind the same trace and outcome evidence")
  if (current.right.hasNullPredictionOrRefusal || candidate.right.hasNullPredictionOrRefusal) return Either.right(notApplicable(allowance, debit, "NULL_PREDICTION_OR_REFUSAL"))
  const selected = selectSemanticLearningCandidate({
    observations: current.right.labels.map(({ id, observed }) => ({ inputKey: id, label: observed, mass: 1n })),
    currentPredictions: Object.fromEntries(Object.entries(current.right.predictions).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean")),
    candidatePredictions: Object.fromEntries(Object.entries(candidate.right.predictions).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean")),
    allowance, debit
  })
  if (Either.isLeft(selected)) return error("SELECTION_GUARD_INVALID", selected.left.code)
  return Either.right(Object.freeze({
    contract: SEMANTIC_LIFECYCLE_SELECTION_V1, selectedArm: selected.right.selection === "CANDIDATE" ? "learned" : "evidence_only", applicability: "APPLICABLE", reason: selected.right.reason,
    boundAuthority: "CALLER_DECLARED", guard: Object.freeze({ allowance: selected.right.allowance.toString(), debit: selected.right.debit.toString(), totalMass: selected.right.totalMass.toString(), currentObservedScore: selected.right.currentObservedScore.toString(), candidateObservedScore: selected.right.candidateObservedScore.toString(), requiredCandidateObservedScore: selected.right.requiredCandidateObservedScore.toString(), observedGuardPasses: selected.right.observedGuardPasses }),
    claimCeiling: "FINITE_DECLARED_BOUND_SELECTION_NOT_GENERALIZATION_OR_RUNTIME_REFINEMENT"
  }))
}
