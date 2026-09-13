import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"
import { Either } from "effect"
import { nativeS2SFloatHex } from "../src/native-s2s-dataset-domain.js"
import { NATIVE_S2S_PROTOCOL_METRICS_SOURCE_SHA256, NATIVE_S2S_PROTOCOL_METRICS_SCIENTIFIC_STATUS, nativeS2STaskMetricValues, type NativeS2SProtocolScoreR2, type NativeS2SScoreVariant } from "../src/native-s2s-protocol-metrics-domain.js"

type OracleStratum = { readonly role: number; readonly channel: number; readonly r2_hex: string }
type OracleScore = { readonly variant: NativeS2SScoreVariant; readonly strata: readonly OracleStratum[] }
type OracleCase = { readonly name: string; readonly score_variants: readonly OracleScore[]; readonly expected: { readonly q_hex: string; readonly b_hex: string; readonly r_hex: string; readonly c_hex: string } }
type Oracle = { readonly source_sha256: string; readonly cases: readonly OracleCase[]; readonly overflow: { readonly score_variants: readonly OracleScore[]; readonly constructed_from_real_receipt_classes_then_mutated_r2: boolean; readonly raises: string } }
const freeze = <Value>(value: Value): Value => Object.freeze(value)
const floatFromPythonHex = (value: string): number => {
  const parsed = /^(-?)0x([0-9a-f]+)\.([0-9a-f]+)p([+-]\d+)$/.exec(value)
  if (parsed === null) return Number.NaN
  const sign = parsed[1] === "-" ? -1 : 1
  const integer = Number.parseInt(parsed[2]!, 16)
  const fraction = Number.parseInt(parsed[3]!, 16) / 16 ** parsed[3]!.length
  return sign * (integer + fraction) * 2 ** Number.parseInt(parsed[4]!, 10)
}
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_protocol_metrics_v1/original_python.json", import.meta.url), "utf8")) as Oracle
const scoresFrom = (source: readonly OracleScore[]): readonly NativeS2SProtocolScoreR2[] => freeze(source.map((score) => freeze({ variant: score.variant, strata: freeze(score.strata.map((row) => freeze({ role: row.role, channel: row.channel, r2: floatFromPythonHex(row.r2_hex) }))) })) as NativeS2SProtocolScoreR2[])
const scores = scoresFrom(oracle.cases[0]!.score_variants)

describe("native S2S protocol score metrics", () => {
  it("matches the source-pinned Python `_metric_values` oracle", () => {
    expect(oracle.source_sha256).toBe(NATIVE_S2S_PROTOCOL_METRICS_SOURCE_SHA256)
    expect(createHash("sha256").update(readFileSync(new URL("../../experiments/swm0w_s2s_protocol.py", import.meta.url))).digest("hex")).toBe(NATIVE_S2S_PROTOCOL_METRICS_SOURCE_SHA256)
    for (const scenario of oracle.cases) {
      const actual = nativeS2STaskMetricValues(scoresFrom(scenario.score_variants))
      expect(Either.isRight(actual), scenario.name).toBe(true)
      if (Either.isRight(actual)) {
        expect(nativeS2SFloatHex(actual.right.q)).toBe(scenario.expected.q_hex)
        expect(nativeS2SFloatHex(actual.right.b)).toBe(scenario.expected.b_hex)
        expect(nativeS2SFloatHex(actual.right.r)).toBe(scenario.expected.r_hex)
        expect(nativeS2SFloatHex(actual.right.c)).toBe(scenario.expected.c_hex)
        expect(actual.right.scientificStatus).toBe(NATIVE_S2S_PROTOCOL_METRICS_SCIENTIFIC_STATUS)
        expect(Object.isFrozen(actual.right)).toBe(true)
      }
    }
    expect(oracle.overflow.constructed_from_real_receipt_classes_then_mutated_r2).toBe(true)
    expect(oracle.overflow.raises).toBe("numeric reduction produced a non-finite value")
    expect(Either.isLeft(nativeS2STaskMetricValues(scoresFrom(oracle.overflow.score_variants)))).toBe(true)
  })

  it("refuses malformed, sparse, mutable, reordered, and non-finite score rosters", () => {
    const mutable = scores.map((score) => score)
    expect(Either.isLeft(nativeS2STaskMetricValues(mutable))).toBe(true)
    const reordered = freeze([scores[1]!, scores[0]!, ...scores.slice(2)])
    expect(Either.isLeft(nativeS2STaskMetricValues(reordered))).toBe(true)
    const sparse: unknown[] = []
    sparse.length = 8
    expect(Either.isLeft(nativeS2STaskMetricValues(freeze(sparse)))).toBe(true)
    const nonFinite = freeze(scores.map((score, index) => index === 0 ? freeze({ ...score, strata: freeze(score.strata.map((row, rowIndex) => rowIndex === 0 ? freeze({ ...row, r2: Number.NaN }) : row)) }) : score))
    expect(Either.isLeft(nativeS2STaskMetricValues(nonFinite))).toBe(true)
    let reads = 0
    const accessorStratum = Object.freeze(Object.defineProperty({ channel: 0, role: 0 }, "r2", { enumerable: true, get: () => { reads += 1; return 0 } }))
    const accessorScore = Object.freeze({ variant: "T16_BASE", strata: Object.freeze([accessorStratum, ...scores[0]!.strata.slice(1)]) })
    expect(Either.isLeft(nativeS2STaskMetricValues(Object.freeze([accessorScore, ...scores.slice(1)])))).toBe(true)
    expect(reads).toBe(0)
  })
})
