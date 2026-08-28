import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import { encodeDnrd5PlanJsonBytes } from "../src/canonical-atom-v2-dnrd5-plan-json.js"
import {
  DNRD5_RANDOMIZATION_TERMINAL,
  deriveDnrd5RandomizationPlan,
  validateDnrd5RandomizationPlan
} from "../src/canonical-atom-v2-dnrd5-randomization.js"

const KAT_URL = new URL(
  "../../../../_research/dnrd5/vectors/plan_json_v1_kat.json",
  import.meta.url
)
const IMPLEMENTATION_URL = new URL(
  "../src/canonical-atom-v2-dnrd5-randomization.ts",
  import.meta.url
)
const KAT_SHA256 = "012dcc2ebf71dd6b54dfceec9aeeb72673961c64830694ab7bb7c678deb6051f"
const KAT = JSON.parse(readFileSync(KAT_URL, "utf8")) as {
  readonly full_plan_known_answers: ReadonlyArray<{
    readonly expected_byte_length: number
    readonly expected_sha256: string
    readonly expected_study_plan_sha256: string
    readonly future_randomness_hex: string
    readonly study_binding_sha256: string
  }>
}

const canonicalSha256 = (value: unknown): string => {
  const bytes = encodeDnrd5PlanJsonBytes(value)
  if (Either.isLeft(bytes)) throw new Error(`${bytes.left.code}: ${bytes.left.detail}`)
  return createHash("sha256").update(bytes.right).digest("hex")
}

it("independently rederives both full 300-block / 2,700-slot KAT plans byte-for-byte", () => {
  const rawKat = readFileSync(KAT_URL)
  expect(createHash("sha256").update(rawKat).digest("hex")).toBe(KAT_SHA256)
  expect(KAT.full_plan_known_answers).toHaveLength(2)
  for (const row of KAT.full_plan_known_answers) {
    const plan = deriveDnrd5RandomizationPlan(row.future_randomness_hex, row.study_binding_sha256)
    expect(Either.isRight(plan)).toBe(true)
    if (Either.isLeft(plan)) throw new Error(`${plan.left.code}: ${plan.left.detail}`)
    const bytes = encodeDnrd5PlanJsonBytes(plan.right)
    expect(Either.isRight(bytes)).toBe(true)
    if (Either.isLeft(bytes)) throw new Error(`${bytes.left.code}: ${bytes.left.detail}`)
    expect(plan.right["block_count"]).toBe(300)
    expect(plan.right["total_call_slots"]).toBe(2700)
    expect((plan.right["blocks"] as ReadonlyArray<unknown>).length).toBe(300)
    expect((plan.right["blocks"] as ReadonlyArray<{ readonly private_call_schedule: ReadonlyArray<unknown> }>).reduce((total, block) => total + block.private_call_schedule.length, 0)).toBe(2700)
    expect(bytes.right.byteLength).toBe(row.expected_byte_length)
    expect(createHash("sha256").update(bytes.right).digest("hex")).toBe(row.expected_sha256)
    expect(plan.right["study_plan_sha256"]).toBe(row.expected_study_plan_sha256)
    expect(validateDnrd5RandomizationPlan(plan.right, row.future_randomness_hex, row.study_binding_sha256)).toEqual(plan)
  }
})

it("fails closed on input drift and an internally rehashed allocation mutation", () => {
  const row = KAT.full_plan_known_answers[0]
  if (row === undefined) throw new Error("missing KAT row")
  expect(Either.isLeft(deriveDnrd5RandomizationPlan("AA".repeat(32), row.study_binding_sha256))).toBe(true)
  expect(Either.isLeft(deriveDnrd5RandomizationPlan(row.future_randomness_hex, "00"))).toBe(true)
  const plan = deriveDnrd5RandomizationPlan(row.future_randomness_hex, row.study_binding_sha256)
  if (Either.isLeft(plan)) throw new Error(plan.left.detail)
  const changed = structuredClone(plan.right) as {
    blocks: Array<{
      assignment_receipt: { assignment_commitment_sha256: string }
      private_assignment: Record<string, string>
    }>
    study_plan_sha256: string
    [key: string]: unknown
  }
  const assignment = changed.blocks[0]?.private_assignment
  if (assignment === undefined) throw new Error("missing first assignment")
  const keys = Object.keys(assignment)
  const first = keys[0]; const second = keys[1]
  if (first === undefined || second === undefined) throw new Error("missing fork assignment")
  const held = assignment[first] as string
  assignment[first] = assignment[second] as string
  assignment[second] = held
  const firstBlock = changed.blocks[0]
  if (firstBlock === undefined) throw new Error("missing first block")
  firstBlock.assignment_receipt.assignment_commitment_sha256 = canonicalSha256(assignment)
  const { study_plan_sha256: _oldPlanSha256, ...payload } = changed
  changed.study_plan_sha256 = canonicalSha256(payload)
  const checked = validateDnrd5RandomizationPlan(changed, row.future_randomness_hex, row.study_binding_sha256)
  expect(Either.isLeft(checked)).toBe(true)
  if (Either.isLeft(checked)) expect(checked.left.code).toBe("PLAN_MISMATCH")
})

it("preserves exact per-block fork, arm, receipt, and one-plus-four-plus-four semantics", () => {
  const row = KAT.full_plan_known_answers[0]
  if (row === undefined) throw new Error("missing KAT row")
  const plan = deriveDnrd5RandomizationPlan(row.future_randomness_hex, row.study_binding_sha256)
  if (Either.isLeft(plan)) throw new Error(plan.left.detail)
  const blocks = plan.right["blocks"] as ReadonlyArray<{
    readonly block_id: string
    readonly sealed_fork_projection: {
      readonly forks: ReadonlyArray<{
        readonly fork_id: string
        readonly probe_seed_sha256: string
        readonly proposal_seed_sha256: string
      }>
    }
    readonly assignment_receipt: { readonly assignment_commitment_sha256: string; readonly sealed_fork_projection_sha256: string }
    readonly private_assignment: Readonly<Record<string, string>>
    readonly call_schedule_receipt: { readonly call_schedule_commitment_sha256: string; readonly sealed_fork_projection_sha256: string }
    readonly private_call_schedule: ReadonlyArray<{
      readonly call_class: string
      readonly call_id: string
      readonly fork_id: string
      readonly rng_seed_sha256: string
    }>
  }>
  for (const index of [0, 149, 299]) {
    const block = blocks[index]
    if (block === undefined) throw new Error(`missing block ${index}`)
    expect(block.block_id).toBe(`DNRD5-BLOCK-${String(index + 1).padStart(4, "0")}`)
    const forks = block.sealed_fork_projection.forks
    const forkIds = forks.map((fork) => fork.fork_id)
    expect(new Set(forkIds).size).toBe(4)
    expect(Object.keys(block.private_assignment).sort()).toEqual([...forkIds].sort())
    expect(new Set(Object.values(block.private_assignment))).toEqual(new Set([
      "ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK"
    ]))
    expect(block.assignment_receipt.assignment_commitment_sha256).toBe(canonicalSha256(block.private_assignment))
    expect(block.assignment_receipt.sealed_fork_projection_sha256).toBe(canonicalSha256(block.sealed_fork_projection))
    expect(block.call_schedule_receipt.sealed_fork_projection_sha256).toBe(canonicalSha256(block.sealed_fork_projection))
    expect(block.call_schedule_receipt.call_schedule_commitment_sha256).toBe(canonicalSha256(block.private_call_schedule))
    expect(block.private_call_schedule.map((call) => call.call_class)).toEqual([
      "PRE_OUTCOME_TRAJECTORY",
      "REVISION_PROPOSAL", "REVISION_PROPOSAL", "REVISION_PROPOSAL", "REVISION_PROPOSAL",
      "FRESH_PROBE", "FRESH_PROBE", "FRESH_PROBE", "FRESH_PROBE"
    ])
    expect(block.private_call_schedule.map((call) => call.call_id)).toEqual([
      `${block.block_id}:TRAJECTORY:0`,
      ...Array.from({ length: 4 }, (_, offset) => `${block.block_id}:PROPOSAL:${offset + 1}`),
      ...Array.from({ length: 4 }, (_, offset) => `${block.block_id}:PROBE:${offset + 1}`)
    ])
    const proposalCalls = block.private_call_schedule.slice(1, 5)
    const probeCalls = block.private_call_schedule.slice(5, 9)
    expect(new Set(proposalCalls.map((call) => call.fork_id))).toEqual(new Set(forkIds))
    expect(new Set(probeCalls.map((call) => call.fork_id))).toEqual(new Set(forkIds))
    const forkById = new Map(forks.map((fork) => [fork.fork_id, fork]))
    for (const call of proposalCalls) expect(call.rng_seed_sha256).toBe(forkById.get(call.fork_id)?.proposal_seed_sha256)
    for (const call of probeCalls) expect(call.rng_seed_sha256).toBe(forkById.get(call.fork_id)?.probe_seed_sha256)
  }
})

it("states the allocation-only boundary", () => {
  expect(DNRD5_RANDOMIZATION_TERMINAL).toContain("NOT_SOURCE_BUILD_OR_EVIDENCE_SCHEMA_BOUND")
  expect(DNRD5_RANDOMIZATION_TERMINAL).toContain("NOT_SOURCE_FREEZE")
  expect(DNRD5_RANDOMIZATION_TERMINAL).toContain("NOT_CHRONOLOGY")
  expect(DNRD5_RANDOMIZATION_TERMINAL).toContain("NOT_EXECUTION")
  expect(DNRD5_RANDOMIZATION_TERMINAL).toContain("NOT_EFFICACY")
  expect(DNRD5_RANDOMIZATION_TERMINAL).toContain("NOT_SCIENTIFIC_RESULT")
})

it("keeps the TypeScript rederiver independent of Python and process execution", () => {
  const source = readFileSync(IMPLEMENTATION_URL, "utf8")
  const imports = [...source.matchAll(/from\s+"([^"]+)"/g)].map((match) => match[1])
  expect(imports).toEqual([
    "node:crypto",
    "effect",
    "./canonical-atom-v2-dnrd5-plan-json.js"
  ])
  expect(source).not.toContain("child_process")
  expect(source).not.toContain("_research")
  expect(source).not.toContain("randomization.py")
})
