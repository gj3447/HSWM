import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import {
  NATIVE_S2S_FAMILY_CERTIFICATE_SHA256,
  NATIVE_S2S_FAMILY_DEFINITION_SHA256,
  NATIVE_S2S_FAMILY_SCIENTIFIC_STATUS,
  NATIVE_S2S_FAMILY_SOURCE_SHA256,
  evaluateNativeS2STaskCase,
  compileNativeS2STaskEvaluator,
  generateNativeS2STask,
  generateNativeS2STaskBatch,
  nativeS2SFamilyCertificatePayload,
  nativeS2SFamilyDefinitionPayload,
  validateNativeS2STask
} from "../src/native-s2s-family-domain.js"
import { renderNativeTaskJson, validNativeTaskJson } from "../src/native-task-json-domain.js"

interface OracleTask { readonly draw_index: number; readonly manifest_sha256: string; readonly structural_target_sha256: string; readonly structural_task_sha256: string }
interface OracleCase { readonly draw_index: number; readonly raw_values: readonly number[]; readonly split: string; readonly target_numerators: readonly (readonly number[])[]; readonly target_floats: readonly (readonly number[])[] }
interface Oracle { readonly source_sha256: string; readonly world_source_sha256: string; readonly family_definition: unknown; readonly family_definition_sha256: string; readonly family_certificate: unknown; readonly family_certificate_sha256: string; readonly tasks: readonly OracleTask[]; readonly cases: readonly OracleCase[]; readonly batch_16: { readonly batch_sha256: string; readonly duplicate_structural_target_draws: readonly (readonly number[])[]; readonly duplicate_structural_task_draws: readonly (readonly number[])[] } }
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_family_v2/original_python.json", import.meta.url), "utf8")) as Oracle
const seed = Uint8Array.from({ length: 32 }, (_, index) => index)
const requireRight = <A>(value: Either.Either<A, unknown>): A => { expect(Either.isRight(value)).toBe(true); if (Either.isRight(value)) return value.right; throw new Error("unreachable") }
const expectDeepFrozen = (value: unknown): void => {
  if (value !== null && typeof value === "object") {
    expect(Object.isFrozen(value)).toBe(true)
    for (const child of Object.values(value)) expectDeepFrozen(child)
  }
}

it("binds the frozen original Python family definition and certificate without an efficacy claim", () => {
  expect(oracle.source_sha256).toBe(NATIVE_S2S_FAMILY_SOURCE_SHA256)
  expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_family.py", import.meta.url))).digest("hex")).toBe(oracle.source_sha256)
  expect(NATIVE_S2S_FAMILY_SCIENTIFIC_STATUS).toBe("UNJUDGED_TASK_FAMILY_ONLY")
  expect(NATIVE_S2S_FAMILY_DEFINITION_SHA256).toBe(oracle.family_definition_sha256)
  expect(NATIVE_S2S_FAMILY_CERTIFICATE_SHA256).toBe(oracle.family_certificate_sha256)
  const definition = nativeS2SFamilyDefinitionPayload(), certificate = nativeS2SFamilyCertificatePayload()
  expect(definition).toHaveProperty("schema_version", "hswm-swm0w-s2s-family-definition/v2")
  expect(certificate).toEqual(oracle.family_certificate)
  expectDeepFrozen(definition)
  expectDeepFrozen(certificate)
  expect(validNativeTaskJson(definition)).toBe(true)
  if (validNativeTaskJson(definition)) expect(createHash("sha256").update(renderNativeTaskJson(definition, "canonical")).digest("hex")).toBe(NATIVE_S2S_FAMILY_DEFINITION_SHA256)
  expect(validNativeTaskJson(certificate)).toBe(true)
  if (validNativeTaskJson(certificate)) expect(createHash("sha256").update(renderNativeTaskJson(certificate, "canonical")).digest("hex")).toBe(NATIVE_S2S_FAMILY_CERTIFICATE_SHA256)
})

it("replays indexed SHAKE draws, manifests, split assignment, and target polynomials", () => {
  for (const expected of oracle.tasks.slice(0, 3)) {
    const task = requireRight(generateNativeS2STask(seed, BigInt(expected.draw_index)))
    expect(task.manifestSha256).toBe(expected.manifest_sha256)
    expect(task.structuralTargetSha256).toBe(expected.structural_target_sha256)
    expect(task.structuralTaskSha256).toBe(expected.structural_task_sha256)
    expect(Object.isFrozen(task)).toBe(true)
    for (const sample of oracle.cases.filter(value => value.draw_index === expected.draw_index)) {
      const actual = requireRight(evaluateNativeS2STaskCase(task, sample.raw_values))
      expect(actual.split).toBe(sample.split)
      expect(actual.targetNumerators).toEqual(sample.target_numerators)
      expect(actual.targetFloats).toEqual(sample.target_floats)
      expect(Object.isFrozen(actual.targetNumerators)).toBe(true)
    }
  }
  const terminal = requireRight(generateNativeS2STask(seed, 2n ** 64n - 1n))
  expect(terminal.manifestSha256).toBe(oracle.tasks[3]!.manifest_sha256)
})

it("retains every draw and records duplicate relationships in its bounded batch manifest", () => {
  const batch = requireRight(generateNativeS2STaskBatch(seed, 16))
  expect(batch.batchSha256).toBe(oracle.batch_16.batch_sha256)
  expect(batch.duplicateStructuralTargetDraws).toEqual(oracle.batch_16.duplicate_structural_target_draws)
  expect(batch.duplicateStructuralTaskDraws).toEqual(oracle.batch_16.duplicate_structural_task_draws)
  expect(batch.tasks).toHaveLength(16)
  expect(Object.isFrozen(batch.tasks)).toBe(true)
})

it("returns typed failures for malformed seed, draw, batch, and world values", () => {
  expect(Either.isLeft(generateNativeS2STask(new Uint8Array(31), 0n))).toBe(true)
  expect(Either.isLeft(generateNativeS2STask(seed, -1n))).toBe(true)
  expect(Either.isLeft(generateNativeS2STask(seed, 2n ** 64n))).toBe(true)
  expect(Either.isLeft(generateNativeS2STaskBatch(seed, 0))).toBe(true)
  const task = requireRight(generateNativeS2STask(seed, 0n))
  expect(Either.isLeft(evaluateNativeS2STaskCase(task, [0, 1, 2, 3, 4]))).toBe(true)
  expect(Either.isLeft(evaluateNativeS2STaskCase(task, [0, true, 2, 3, 4, 0]))).toBe(true)
})

it("rejects null, mutable, and commitment-forged tasks before task evaluation", () => {
  const task = requireRight(generateNativeS2STask(seed, 0n))
  const forged = Object.freeze({ ...task, manifestSha256: "0".repeat(64) })
  const mutable = { ...task }
  expect(Either.isLeft(validateNativeS2STask(null))).toBe(true)
  expect(Either.isLeft(validateNativeS2STask(mutable))).toBe(true)
  expect(Either.isLeft(validateNativeS2STask(forged))).toBe(true)
  expect(() => evaluateNativeS2STaskCase(null, [0, 0, 0, 0, 0, 0])).not.toThrow()
  expect(Either.isLeft(evaluateNativeS2STaskCase(null, [0, 0, 0, 0, 0, 0]))).toBe(true)
  expect(Either.isLeft(evaluateNativeS2STaskCase(forged, [0, 0, 0, 0, 0, 0]))).toBe(true)
  let reads = 0
  const accessor = Object.freeze({ ...task, get rankGains() { reads += 1; return task.rankGains } })
  expect(Either.isLeft(compileNativeS2STaskEvaluator(accessor))).toBe(true)
  expect(reads).toBe(0)
  const compiled = requireRight(compileNativeS2STaskEvaluator(task))
  expect(compiled([0, 0, 0, 0, 0, 0])).toEqual(evaluateNativeS2STaskCase(task, [0, 0, 0, 0, 0, 0]))
  for (const field of ["rankGains", "splitCoefficients", "splitResidues"] as const) {
    const sparse = Object.freeze({ ...task, [field]: Object.freeze(Array(task[field].length)) })
    expect(Either.isLeft(compileNativeS2STaskEvaluator(sparse))).toBe(true)
  }
})
