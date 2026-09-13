import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { NATIVE_S2S_WORLD_SOURCE_SHA256, centeredContrasts, scoreNativeS2SWorld } from "../src/native-s2s-world-domain.js"

interface FixtureCase { readonly raw_values: readonly number[]; readonly syndrome: number; readonly split: string; readonly centered_contrasts: readonly (readonly number[])[]; readonly target_numerators: readonly (readonly number[])[]; readonly target_floats: readonly (readonly number[])[] }
interface Fixture { readonly source_sha256: string; readonly cases: readonly FixtureCase[]; readonly negative: readonly { readonly case: string; readonly message: string }[] }
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_world_v1/original_python.json", import.meta.url), "utf8")) as Fixture
const fullDomainFixture = Object.fromEntries(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_world_v1/full-domain.original.txt", import.meta.url), "utf8").trim().split("\n").map((line) => line.split("=", 2)))

it("replays original Python finite-world scorer vectors without an efficacy claim", () => {
  expect(fixture.source_sha256).toBe(NATIVE_S2S_WORLD_SOURCE_SHA256)
  expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_worlds.py", import.meta.url))).digest("hex")).toBe(fixture.source_sha256)
  for (const item of fixture.cases) {
    const result = scoreNativeS2SWorld(item.raw_values)
    expect(Either.isRight(result)).toBe(true)
    if (Either.isRight(result)) {
      expect(result.right.syndrome).toBe(item.syndrome)
      expect(result.right.split).toBe(item.split)
      expect(result.right.centeredContrasts).toEqual(item.centered_contrasts)
      expect(result.right.targetNumerators).toEqual(item.target_numerators)
      expect(result.right.targetFloats).toEqual(item.target_floats)
      expect(result.right.scientificStatus).toBe("UNJUDGED_INTEGRITY_ONLY")
    }
  }
})

it("matches the original lexicographically ordered 5^6 target contract", () => {
  const targets: number[][][] = []
  for (let a0 = 0; a0 < 5; a0 += 1) for (let a1 = 0; a1 < 5; a1 += 1) for (let a2 = 0; a2 < 5; a2 += 1) for (let a3 = 0; a3 < 5; a3 += 1) for (let a4 = 0; a4 < 5; a4 += 1) for (let a5 = 0; a5 < 5; a5 += 1) {
    const result = scoreNativeS2SWorld([a0, a1, a2, a3, a4, a5])
    expect(Either.isRight(result)).toBe(true)
    if (Either.isRight(result)) targets.push(result.right.targetNumerators.map((row) => [...row]))
  }
  const canonical = JSON.stringify({ ordered_raw_values_lexicographic_base5: true, target_numerators: targets })
  expect(createHash("sha256").update(canonical).digest("hex")).toBe(fullDomainFixture.canonical_contract_sha256)
})

it("retains original Python malformed-world rejections", () => {
  const sparse = [0, 1, 2, 3, 4, 0] as unknown[]
  delete sparse[3]
  const invalid: Readonly<Record<string, unknown>> = { short: [0, 1, 2, 3, 4], boolean: [true, 1, 2, 3, 4, 0], out_of_field: [0, 1, 2, 3, 4, 5], sparse }
  for (const item of fixture.negative) {
    const result: Either.Either<unknown, {readonly detail: string}> = item.case === "centered_boolean" ? centeredContrasts(true) : scoreNativeS2SWorld(invalid[item.case])
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.detail).toBe(item.message)
  }
  expect(Either.isLeft(scoreNativeS2SWorld(invalid["sparse"]))).toBe(true)
})
