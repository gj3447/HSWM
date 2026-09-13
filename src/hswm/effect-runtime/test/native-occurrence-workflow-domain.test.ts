/** Source-bound one-shot cases from infrastructure/occurrence_workflow.py. */
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { advanceNativeOccurrence, nativeOccurrenceWorkflowCanonical, nativeTemporalOneShotLaunchOptions, registeredNativeOccurrence } from "../src/native-occurrence-workflow-domain.js"

const hash = (seed: string): string => seed.repeat(64)
const registered = () => {
  const state = registeredNativeOccurrence("g0-occurrence-1", hash("a"))
  expect(Either.isRight(state)).toBe(true)
  if (Either.isLeft(state)) throw new Error(state.left.detail)
  return state.right
}
it("advances the exact one-shot phase order and freezes evidence", () => {
  let state = registered()
  for (const [phase, timing, seed] of [["CLAIMED", "PRE_PULSE", "b"], ["SCHEDULED", "PRE_PULSE", "c"], ["PRE_PULSE_SEALED", "PRE_PULSE", "d"], ["PULSE_VERIFIED", "POST_PULSE", "e"], ["REVEALED", "POST_PULSE", "f"], ["DUAL_EVALUATED", "POST_PULSE", "1"], ["SEALED", "POST_PULSE", "2"]] as const) {
    const next = advanceNativeOccurrence(state, phase, hash(seed), timing)
    expect(Either.isRight(next)).toBe(true)
    if (Either.isLeft(next)) throw new Error(next.left.detail)
    state = next.right
  }
  expect(state.phase).toBe("SEALED")
  expect(Object.isFrozen(state.evidenceSha256s)).toBe(true)
})
it("voids duplicate, retry/order, late evidence, and terminal reentry", () => {
  const initial = registered()
  const duplicate = advanceNativeOccurrence(initial, "CLAIMED", hash("a"), "POST_PULSE")
  expect(Either.getOrNull(duplicate)?.voidReason).toBe("DUPLICATE_OR_RETRY")
  const late = advanceNativeOccurrence(initial, "PRE_PULSE_SEALED", hash("b"), "POST_PULSE")
  expect(Either.getOrNull(late)?.voidReason).toBe("ORDER")
  const wrongTiming = advanceNativeOccurrence(initial, "CLAIMED", hash("b"), "POST_PULSE")
  expect(Either.getOrNull(wrongTiming)?.voidReason).toBe("LATE")
})
it("emits immutable exact Temporal one-shot options", () => {
  const options = nativeTemporalOneShotLaunchOptions("g0-occurrence-1")
  expect(Either.getOrNull(options)).toMatchObject({ workflow_id: "g0-occurrence/g0-occurrence-1", workflow_id_reuse_policy: "REJECT_DUPLICATE", replacement_round_allowed: false })
})

type OriginalState = Readonly<{
  readonly occurrence_uid: string
  readonly phase: string
  readonly evidence_sha256s: readonly string[]
  readonly void_reason: string | null
  readonly rejected_evidence_sha256: string | null
  readonly schema_version: string
}>
type WorkflowOracle = Readonly<{
  readonly source_pins: Readonly<{ readonly original_python_sha256: string }>
  readonly source_state_pool: readonly OriginalState[]
  readonly full_valid_chain: readonly OriginalState[]
  readonly matrix_dimensions: Readonly<{ readonly next_phases: readonly string[]; readonly timings: readonly string[]; readonly evidence_kinds: readonly string[] }>
  readonly outcomes: readonly (readonly [string, string, boolean, string | null, string | null])[]
  readonly cases: readonly (readonly [number, number, number, number, number])[]
  readonly case_count: number
}>
const workflowOracle = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/native_migration/occurrence_workflow_v1/contracts.json"), "utf8")) as WorkflowOracle
const required = <A>(value: A | undefined, label: string): A => {
  if (value === undefined) throw new Error(`missing fixture ${label}`)
  return value
}
const right = <A>(value: Either.Either<A, { readonly detail: string }>): A => {
  if (Either.isLeft(value)) throw new Error(value.left.detail)
  return value.right
}
const expectedFreshEvidence = (source: OriginalState, phase: string, timing: string): string => createHash("sha256").update(`${source.phase}|${phase}|${timing}|fresh`).digest("hex")
const timingForChainPhase = (phase: string): "PRE_PULSE" | "POST_PULSE" => ["CLAIMED", "SCHEDULED", "PRE_PULSE_SEALED"].includes(phase) ? "PRE_PULSE" : "POST_PULSE"

it("matches all 720 source-pinned original Python workflow transitions", () => {
  expect(workflowOracle.source_pins.original_python_sha256).toBe("28859bc0cbef2d81045daec3080724ec34f6abe265e800eb26d444768ec05c70")
  expect(workflowOracle.case_count).toBe(720)
  expect(workflowOracle.cases).toHaveLength(720)
  for (const [sourceIndex, phaseIndex, timingIndex, evidenceKindIndex, outcomeIndex] of workflowOracle.cases) {
    const source = required(workflowOracle.source_state_pool[sourceIndex], "source state")
    const phase = required(workflowOracle.matrix_dimensions.next_phases[phaseIndex], "next phase")
    const timing = required(workflowOracle.matrix_dimensions.timings[timingIndex], "timing")
    const evidenceKind = required(workflowOracle.matrix_dimensions.evidence_kinds[evidenceKindIndex], "evidence kind")
    const outcome = required(workflowOracle.outcomes[outcomeIndex], "outcome")
    let current = right(registeredNativeOccurrence(source.occurrence_uid, required(source.evidence_sha256s[0], "registration evidence")))
    for (let chainIndex = 1; chainIndex <= sourceIndex; chainIndex += 1) {
      const chain = required(workflowOracle.full_valid_chain[chainIndex], "valid chain state")
      current = right(advanceNativeOccurrence(current, chain.phase, required(chain.evidence_sha256s.at(-1), "chain evidence"), timingForChainPhase(chain.phase)))
    }
    expect(right(nativeOccurrenceWorkflowCanonical(current))).toEqual(source)
    const evidence = evidenceKind === "fresh" ? expectedFreshEvidence(source, phase, timing) : evidenceKind === "duplicate" ? required(source.evidence_sha256s[0], "duplicate evidence") : "not-a-lowercase-sha256"
    const result = right(advanceNativeOccurrence(current, phase, evidence, timing))
    if (outcome[0] === "error_class") throw new Error(`fixture case unexpectedly requires ${outcome[1]}`)
    const expected = {
      occurrence_uid: source.occurrence_uid,
      phase: outcome[1],
      evidence_sha256s: outcome[2] ? [...source.evidence_sha256s, evidence] : [...source.evidence_sha256s],
      void_reason: outcome[3],
      rejected_evidence_sha256: outcome[4] === "input" ? evidence : null,
      schema_version: source.schema_version,
    }
    expect(right(nativeOccurrenceWorkflowCanonical(result))).toEqual(expected)
  }
})
