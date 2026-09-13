import { expect, it } from "@effect/vitest"
import { readFileSync } from "node:fs"
import { sumNativeS2SContiguousProducts } from "../src/native-s2s-contiguous-reduction-domain.js"

interface DotCase {
  readonly name: string
  readonly left: readonly number[]
  readonly right: readonly number[]
  readonly expected_hex: string
}
interface Fixture {
  readonly schema_version: string
  readonly claim_ceiling: string
  readonly numpy_version: string
  readonly numpy_commit: string
  readonly einsum_sumprod_source_sha256: string
  readonly platform: { readonly machine: string; readonly system: string; readonly numpy_simd_baseline: readonly string[]; readonly numpy_simd_found: readonly string[] }
  readonly dot_cases: readonly DotCase[]
  readonly repeated_source_dots_16: { readonly parts: readonly DotCase[]; readonly expected_hex: string }
}
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_reduction_v1/original_numpy_x86_v2.json", import.meta.url), "utf8")) as Fixture
const float64Hex = (value: number): string => {
  if (value === 0) return Object.is(value, -0) ? "-0x0.0p+0" : "0x0.0p+0"
  const bytes = new ArrayBuffer(8), view = new DataView(bytes)
  view.setFloat64(0, value, false)
  const bits = view.getBigUint64(0, false), sign = (bits >> 63n) === 0n ? "" : "-", exponent = Number((bits >> 52n) & 0x7ffn), fraction = (bits & ((1n << 52n) - 1n)).toString(16).padStart(13, "0")
  if (exponent === 0) return `${sign}0x0.${fraction}p-1022`
  return `${sign}0x1.${fraction}p${exponent - 1023 >= 0 ? "+" : ""}${exponent - 1023}`
}
const reduced = (entry: DotCase): number => sumNativeS2SContiguousProducts(entry.left.length as 16 | 18, index => entry.left[index]! * entry.right[index]!)

it("replays the source-pinned NumPy X86_V2 contiguous-product observations", () => {
  expect(fixture.schema_version).toBe("hswm-native-s2s-reduction-observation/v1")
  expect(fixture.claim_ceiling).toBe("PINNED_NUMPY_X86_V2_OBSERVATION_NOT_UNIVERSAL_NUMERICAL_BACKEND")
  expect(fixture.numpy_version).toBe("2.5.2")
  expect(fixture.numpy_commit).toBe("48fecee5453aa1d31e6b79dcb3969dc1a6d1a891")
  expect(fixture.einsum_sumprod_source_sha256).toBe("d1c8e05b55eb31561169558bda7ddfd05e7ab4d7fac27a4123f33a3a494a220b")
  expect(fixture.platform.numpy_simd_baseline).toEqual(["X86_V2"])
  for (const entry of fixture.dot_cases) expect(float64Hex(reduced(entry))).toBe(entry.expected_hex)
})

it("preserves source-order accumulation across repeated contiguous source dots", () => {
  let total = 0
  for (const part of fixture.repeated_source_dots_16.parts) total += reduced(part)
  expect(float64Hex(total)).toBe(fixture.repeated_source_dots_16.expected_hex)
})
