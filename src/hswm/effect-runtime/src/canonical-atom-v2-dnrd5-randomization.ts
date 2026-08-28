/** Independent TypeScript rederivation of the proposed DNRD-5 allocation plan.
 *
 * It consumes only pinned randomness and study-binding hex values.  This is an
 * allocation-integrity instrument: it neither dispatches a model nor proves
 * chronology, isolation, occurrence, or a scientific result.
 */

import { createHash } from "node:crypto"

import { Data, Either } from "effect"

import {
  type Dnrd5PlanJson,
  encodeDnrd5PlanJsonBytes
} from "./canonical-atom-v2-dnrd5-plan-json.js"

export const DNRD5_RANDOMIZATION_SCHEMA = "hswm-dnrd5-randomization/v1" as const
export const DNRD5_RANDOMIZATION_STATUS =
  "RANDOMIZATION_DERIVATION_ONLY_CHRONOLOGY_NOT_ENFORCED_NOT_EXECUTION_NOT_RESULT" as const
export const DNRD5_RANDOMIZATION_TERMINAL =
  "INDEPENDENT_TYPESCRIPT_RANDOMIZATION_ONLY_NOT_SOURCE_BUILD_OR_EVIDENCE_SCHEMA_BOUND_NOT_SOURCE_FREEZE_NOT_CHRONOLOGY_NOT_ISOLATION_NOT_EXECUTION_NOT_EFFICACY_NOT_SCIENTIFIC_RESULT" as const

const BLOCK_COUNT = 300
const CALLS_PER_BLOCK = 9
const ARMS = ["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK"] as const
const HEX_256 = /^[0-9a-f]{64}$/
const utf8 = new TextEncoder()

export class Dnrd5RandomizationError extends Data.TaggedError("Dnrd5RandomizationError")<{
  readonly code: "INPUT_INVALID" | "CODEC_REFUSAL" | "DERIVATION_REFUSAL" | "PLAN_MISMATCH"
  readonly detail: string
}> {}

type JsonObject = { readonly [key: string]: Dnrd5PlanJson }

const fail = (code: Dnrd5RandomizationError["code"], detail: string): Either.Either<never, Dnrd5RandomizationError> =>
  Either.left(new Dnrd5RandomizationError({ code, detail }))

const sha256 = (bytes: Uint8Array): Uint8Array =>
  new Uint8Array(createHash("sha256").update(bytes).digest())

const hex = (bytes: Uint8Array): string => Buffer.from(bytes).toString("hex")

const requireHex256 = (value: string, label: string): Either.Either<Uint8Array, Dnrd5RandomizationError> => {
  if (typeof value !== "string" || !HEX_256.test(value)) return fail("INPUT_INVALID", `${label} must be lowercase SHA-256 hex`)
  return Either.right(new Uint8Array(Buffer.from(value, "hex")))
}

const blockIds = (): ReadonlyArray<string> =>
  Array.from({ length: BLOCK_COUNT }, (_, index) => `DNRD5-BLOCK-${String(index + 1).padStart(4, "0")}`)

const canonicalBytes = (value: unknown): Either.Either<Uint8Array, Dnrd5RandomizationError> => {
  const encoded = encodeDnrd5PlanJsonBytes(value)
  return Either.isLeft(encoded)
    ? fail("CODEC_REFUSAL", encoded.left.detail)
    : Either.right(encoded.right)
}

const canonicalSha256 = (value: unknown): Either.Either<string, Dnrd5RandomizationError> => {
  const encoded = canonicalBytes(value)
  return Either.isLeft(encoded) ? Either.left(encoded.left) : Either.right(hex(sha256(encoded.right)))
}

const u32 = (value: number): Uint8Array => {
  const out = new Uint8Array(4)
  new DataView(out.buffer).setUint32(0, value, false)
  return out
}

const join = (parts: ReadonlyArray<Uint8Array>): Uint8Array => {
  const out = new Uint8Array(parts.reduce((size, part) => size + part.byteLength, 0))
  let offset = 0
  for (const part of parts) { out.set(part, offset); offset += part.byteLength }
  return out
}

const derive = (root: Uint8Array, purpose: string, ...parts: ReadonlyArray<string>): Uint8Array => {
  const encodedParts = [purpose, ...parts].map((part) => utf8.encode(part))
  return sha256(join([
    utf8.encode(DNRD5_RANDOMIZATION_SCHEMA),
    ...encodedParts.flatMap((part) => [u32(part.byteLength), part]),
    u32(root.byteLength), root
  ]))
}

const uniformBelow = (root: Uint8Array, purpose: string, upper: number, initialCounter: number): readonly [number, number] => {
  const modulus = 1n << 256n
  const bound = BigInt(upper)
  const cutoff = modulus - (modulus % bound)
  let counter = initialCounter
  while (true) {
    const candidate = BigInt(`0x${hex(derive(root, purpose, String(counter)))}`)
    counter += 1
    if (candidate < cutoff) return [Number(candidate % bound), counter]
  }
}

const permutation = <T>(items: ReadonlyArray<T>, root: Uint8Array, purpose: string): ReadonlyArray<T> => {
  const result = [...items]
  let counter = 0
  for (let index = result.length - 1; index > 0; index -= 1) {
    const [chosen, next] = uniformBelow(root, purpose, index + 1, counter)
    counter = next
    const held = result[index] as T
    result[index] = result[chosen] as T
    result[chosen] = held
  }
  return result
}

const deriveBlock = (root: Uint8Array, binding: string, block: string): Either.Either<JsonObject, Dnrd5RandomizationError> => {
  const blockRoot = derive(root, "block-root", binding, block)
  const clones: Array<JsonObject> = []
  for (let index = 0; index < 4; index += 1) {
    const fork = `fork-${hex(derive(blockRoot, "opaque-fork", String(index))).slice(0, 32)}`
    const proposal = derive(blockRoot, "proposal-seed", fork)
    const probe = derive(blockRoot, "probe-seed", fork)
    clones.push({ fork_id: fork, proposal_seed_sha256: hex(sha256(proposal)), probe_seed_sha256: hex(sha256(probe)) })
  }
  const forkIds = clones.map((row) => row["fork_id"] as string)
  if (new Set(forkIds).size !== 4) return fail("DERIVATION_REFUSAL", "derived fork identifiers collided")
  const forkListHash = canonicalSha256(forkIds)
  if (Either.isLeft(forkListHash)) return Either.left(forkListHash.left)
  const forks: JsonObject = { schema_version: DNRD5_RANDOMIZATION_SCHEMA, block_id: block, forks: clones }
  const forkDigest = canonicalSha256(forks)
  if (Either.isLeft(forkDigest)) return Either.left(forkDigest.left)
  const assignmentRoot = derive(root, "arm-assignment", binding, block, forkListHash.right)
  const assignment: Record<string, Dnrd5PlanJson> = Object.create(null)
  const armOrder = permutation(ARMS, assignmentRoot, "arm-permutation")
  for (const [index, fork] of forkIds.entries()) assignment[fork] = armOrder[index] as string
  const scheduleRoot = derive(root, "call-schedule", binding, block, forkListHash.right)
  const byFork = new Map(clones.map((row) => [row["fork_id"] as string, row]))
  const schedule: Array<JsonObject> = [{
    call_id: `${block}:TRAJECTORY:0`, call_class: "PRE_OUTCOME_TRAJECTORY", fork_id: "SHARED_W0",
    rng_seed_sha256: hex(sha256(derive(blockRoot, "trajectory-seed")))
  }]
  for (const [index, fork] of permutation(forkIds, scheduleRoot, "proposal-order").entries()) {
    schedule.push({ call_id: `${block}:PROPOSAL:${index + 1}`, call_class: "REVISION_PROPOSAL", fork_id: fork, rng_seed_sha256: byFork.get(fork)?.["proposal_seed_sha256"] as string })
  }
  for (const [index, fork] of permutation(forkIds, scheduleRoot, "probe-order").entries()) {
    schedule.push({ call_id: `${block}:PROBE:${index + 1}`, call_class: "FRESH_PROBE", fork_id: fork, rng_seed_sha256: byFork.get(fork)?.["probe_seed_sha256"] as string })
  }
  const assignmentDigest = canonicalSha256(assignment)
  const scheduleDigest = canonicalSha256(schedule)
  if (Either.isLeft(assignmentDigest)) return Either.left(assignmentDigest.left)
  if (Either.isLeft(scheduleDigest)) return Either.left(scheduleDigest.left)
  return Either.right({
    schema_version: DNRD5_RANDOMIZATION_SCHEMA,
    block_id: block,
    canonical_json_encoding: "hswm-dnrd5-plan-json/v1",
    randomization_binding: { derivation_version: DNRD5_RANDOMIZATION_SCHEMA, future_randomness_sha256: hex(sha256(root)), study_binding_sha256: binding },
    sealed_fork_projection: forks,
    assignment_receipt: { schema_version: DNRD5_RANDOMIZATION_SCHEMA, block_id: block, sealed_fork_projection_sha256: forkDigest.right, assignment_commitment_sha256: assignmentDigest.right },
    private_assignment: assignment,
    call_schedule_receipt: { schema_version: DNRD5_RANDOMIZATION_SCHEMA, block_id: block, sealed_fork_projection_sha256: forkDigest.right, call_schedule_commitment_sha256: scheduleDigest.right },
    private_call_schedule: schedule,
    model_visible_randomization_projection: { schema_version: DNRD5_RANDOMIZATION_SCHEMA, block_id: block, call_budget: CALLS_PER_BLOCK, projection_status: "RANDOMIZATION_METADATA_EXCLUSION_TEMPLATE_ONLY" },
    scientific_status: DNRD5_RANDOMIZATION_STATUS
  })
}

export const deriveDnrd5RandomizationPlan = (
  futureRandomnessHex: string,
  studyBindingSha256: string
): Either.Either<JsonObject, Dnrd5RandomizationError> => {
  const root = requireHex256(futureRandomnessHex, "future_randomness_hex")
  if (Either.isLeft(root)) return Either.left(root.left)
  if (!HEX_256.test(studyBindingSha256)) return fail("INPUT_INVALID", "study_binding_sha256 must be lowercase SHA-256 hex")
  const blocks: Array<JsonObject> = []
  for (const block of blockIds()) {
    const derived = deriveBlock(root.right, studyBindingSha256, block)
    if (Either.isLeft(derived)) return Either.left(derived.left)
    blocks.push(derived.right)
  }
  const idsHash = canonicalSha256(blockIds())
  if (Either.isLeft(idsHash)) return Either.left(idsHash.left)
  const payload: JsonObject = {
    schema_version: DNRD5_RANDOMIZATION_SCHEMA,
    block_ids_sha256: idsHash.right,
    blocks,
    block_count: BLOCK_COUNT,
    total_call_slots: BLOCK_COUNT * CALLS_PER_BLOCK,
    scientific_status: DNRD5_RANDOMIZATION_STATUS
  }
  const planHash = canonicalSha256(payload)
  return Either.isLeft(planHash)
    ? Either.left(planHash.left)
    : Either.right({ ...payload, study_plan_sha256: planHash.right })
}

/** Fail closed by exact independent rederivation; this is semantic allocation
 * integrity for the frozen inputs, not an occurrence or execution validator. */
export const validateDnrd5RandomizationPlan = (
  candidate: unknown,
  futureRandomnessHex: string,
  studyBindingSha256: string
): Either.Either<JsonObject, Dnrd5RandomizationError> => {
  const expected = deriveDnrd5RandomizationPlan(futureRandomnessHex, studyBindingSha256)
  if (Either.isLeft(expected)) return expected
  const candidateBytes = canonicalBytes(candidate)
  if (Either.isLeft(candidateBytes)) return Either.left(candidateBytes.left)
  const expectedBytes = canonicalBytes(expected.right)
  if (Either.isLeft(expectedBytes)) return Either.left(expectedBytes.left)
  if (candidateBytes.right.byteLength !== expectedBytes.right.byteLength || !candidateBytes.right.every((byte, index) => byte === expectedBytes.right[index])) {
    return fail("PLAN_MISMATCH", "candidate does not exactly rederive from pinned randomization inputs")
  }
  return expected
}
