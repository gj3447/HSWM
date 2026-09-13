import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { NATIVE_S2S_INITIALIZATION_NUMPY_VERSION, NATIVE_S2S_INITIALIZATION_SOURCE_SHA256, initializeNativeS2STrainingParameters, nativeS2SInitializationParameterSha256 } from "../src/native-s2s-initialization-domain.js"
import type { NativeS2SParameters } from "../src/native-s2s-training-numeric-domain.js"

type Arm = "P_CAP18" | "T16" | "DS870"
interface ParameterOracle { readonly sha256: string; readonly first: readonly number[]; readonly all_zero: boolean }
interface OracleRow { readonly arm: Arm; readonly seed: string; readonly parameters_sha256: string; readonly parameters: Readonly<Record<string, ParameterOracle>> }
interface Oracle { readonly source_sha256: string; readonly numpy_version: string; readonly rows: readonly OracleRow[] }
interface SourceProvenance { readonly numpy_version: string; readonly resolved_tag_commit: string; readonly numpy_sdist_sha256: string; readonly sources: readonly { readonly raw_url: string; readonly sha256: string }[] }
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_initialization_v1/original_python.json", import.meta.url), "utf8")) as Oracle
const sourceProvenance = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_initialization_v1/official_numpy_source_provenance.json", import.meta.url), "utf8")) as SourceProvenance
const parameterFor = (parameters: NativeS2SParameters, pythonName: string): readonly number[] => {
  if (pythonName === "phi_w" && "phiW" in parameters) return parameters.phiW
  if (pythonName === "psi_w" && "psiW" in parameters) return parameters.psiW
  if (pythonName === "unary_w" && "unaryW" in parameters) return parameters.unaryW
  if (pythonName === "pair_w" && "pairW" in parameters) return parameters.pairW
  if (pythonName === "q_w" && "qW" in parameters) return parameters.qW
  if (pythonName === "eta_w" && "etaW" in parameters) return parameters.etaW
  if (pythonName === "eta_b" && "etaB" in parameters) return parameters.etaB
  if (pythonName === "hidden1_w" && "hidden1W" in parameters) return parameters.hidden1W
  if (pythonName === "hidden1_b" && "hidden1B" in parameters) return parameters.hidden1B
  if (pythonName === "hidden2_w" && "hidden2W" in parameters) return parameters.hidden2W
  if (pythonName === "hidden2_b" && "hidden2B" in parameters) return parameters.hidden2B
  if (pythonName === "out_w" && "outW" in parameters) return parameters.outW
  if (pythonName === "out_b") return parameters.outB
  expect.fail(`missing ${pythonName} in native parameters`)
}
const requireRight = <A>(value: Either.Either<A, unknown>): A => {
  if (Either.isLeft(value)) {
    expect.fail("expected a typed right result")
  }
  return value.right
}

it("binds the locked NumPy 2.5.2 original-training initializer source", () => {
  expect(oracle.source_sha256).toBe(NATIVE_S2S_INITIALIZATION_SOURCE_SHA256)
  expect(oracle.numpy_version).toBe(NATIVE_S2S_INITIALIZATION_NUMPY_VERSION)
  expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_training.py", import.meta.url))).digest("hex")).toBe(oracle.source_sha256)
})

it("pins the official NumPy source files and license boundary used for the port", () => {
  expect(sourceProvenance.numpy_version).toBe(NATIVE_S2S_INITIALIZATION_NUMPY_VERSION)
  expect(sourceProvenance.resolved_tag_commit).toBe("48fecee5453aa1d31e6b79dcb3969dc1a6d1a891")
  expect(sourceProvenance.numpy_sdist_sha256).toBe("d482d171c406ae88c5b19cad3b6a1c4c5209f886ab74bc44c2c865c23f52d860")
  expect(sourceProvenance.sources).toHaveLength(3)
  for (const source of sourceProvenance.sources) {
    expect(source.raw_url).toContain(sourceProvenance.resolved_tag_commit)
    expect(source.sha256).toMatch(/^[0-9a-f]{64}$/)
  }
})

it("replays PCG64 plus SeedSequence initialization byte hashes for every arm and boundary seed", () => {
  for (const row of oracle.rows) {
    const actual = requireRight(initializeNativeS2STrainingParameters(row.arm, BigInt(row.seed)))
    expect(Object.isFrozen(actual)).toBe(true)
    for (const [pythonName, expected] of Object.entries(row.parameters)) {
      const values = parameterFor(actual, pythonName)
      expect(Object.isFrozen(values)).toBe(true)
      expect(requireRight(nativeS2SInitializationParameterSha256(values))).toBe(expected.sha256)
      expect(values.slice(0, 3)).toEqual(expected.first)
      expect(values.every(value => value === 0)).toBe(expected.all_zero)
    }
  }
})

it("rejects unsupported arms and non-uint64 seeds through typed errors", () => {
  expect(Either.isLeft(initializeNativeS2STrainingParameters("UNKNOWN", 0n))).toBe(true)
  expect(Either.isLeft(initializeNativeS2STrainingParameters("T16", -1n))).toBe(true)
  expect(Either.isLeft(initializeNativeS2STrainingParameters("T16", 2n ** 64n))).toBe(true)
  expect(Either.isLeft(initializeNativeS2STrainingParameters("T16", 0))).toBe(true)
})

it("rejects sparse and non-finite arrays before calculating byte digests", () => {
  const sparse: number[] = [0, 1]
  delete sparse[1]
  expect(Either.isLeft(nativeS2SInitializationParameterSha256(sparse))).toBe(true)
  expect(Either.isLeft(nativeS2SInitializationParameterSha256([0, Number.NaN]))).toBe(true)
  expect(Either.isLeft(nativeS2SInitializationParameterSha256([0, Number.POSITIVE_INFINITY]))).toBe(true)
})
