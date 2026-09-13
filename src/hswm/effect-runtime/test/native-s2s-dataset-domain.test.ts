import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import {
  NATIVE_S2S_DATASET_SCIENTIFIC_STATUS,
  NATIVE_S2S_DATASET_SOURCE_SHA256,
  buildNativeS2SStratumLossReceipts,
  compileNativeS2STaskData,
  enumerateNativeS2STaskCases,
  nativeS2SDatasetSha256,
  nativeS2SFloatHex,
  nativeS2SWeightMatrix,
  validateNativeS2SCaseTuple
} from "../src/native-s2s-dataset-domain.js"
import { evaluateNativeS2STaskCase, generateNativeS2STask } from "../src/native-s2s-family-domain.js"

interface OracleReceipt {
  readonly centered_sum_squares_numerator: number
  readonly channel: number
  readonly inverse_variance_weight_hex: string
  readonly receipt_sha256: string
  readonly role: number
  readonly sample_count: number
  readonly target_numerator_sum: number
  readonly target_numerator_sum_squares: number
  readonly schema_version: string
  readonly target_scale_exponent: number
  readonly variance_definition: string
}
interface Oracle {
  readonly all_split_counts: Readonly<Record<string, number>>
  readonly train_dataset_sha256: string
  readonly dev_dataset_sha256: string
  readonly train_x_sha256: string
  readonly train_targets_sha256: string
  readonly dev_x_sha256: string
  readonly dev_targets_sha256: string
  readonly weights_hex: readonly string[]
  readonly strata: readonly OracleReceipt[]
}
interface MultiTaskOracle {
  readonly tasks: readonly {
    readonly draw_index: number
    readonly external_seed_hex: string
    readonly manifest_sha256: string
    readonly train_dataset_sha256: string
    readonly dev_dataset_sha256: string
    readonly weights_hex: readonly string[]
  }[]
}
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_dataset_v1/original_python.json", import.meta.url), "utf8")) as Oracle
const multiTaskOracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_dataset_v1/multi_task_original_python.json", import.meta.url), "utf8")) as MultiTaskOracle
const seed = Uint8Array.from({ length: 32 }, (_, index) => index)
const requireRight = <A>(value: Either.Either<A, unknown>): A => {
  expect(Either.isRight(value)).toBe(true)
  if (Either.isRight(value)) return value.right
  throw new Error("unexpected left")
}
const hashTensor = (values: readonly number[]): string => {
  const bytes = Buffer.alloc(values.length * 8)
  values.forEach((value, index) => bytes.writeDoubleLE(value, index * 8))
  return createHash("sha256").update(bytes).digest("hex")
}
const floatHex = nativeS2SFloatHex

it("replays every finite raw world and exactly compiles the original Python draw-zero datasets", () => {
  expect(NATIVE_S2S_DATASET_SCIENTIFIC_STATUS).toBe("UNJUDGED_ENGINEERING_PARITY_ONLY")
  expect(createHash("sha256").update(readFileSync(new URL("../../../hswm/experiments/swm0w_s2s_training.py", import.meta.url))).digest("hex")).toBe(NATIVE_S2S_DATASET_SOURCE_SHA256)
  const task = requireRight(generateNativeS2STask(seed, 0n))
  const all = requireRight(enumerateNativeS2STaskCases(task))
  expect(all).toHaveLength(15_625)
  for (const split of ["train", "dev", "test"] as const) expect(all.filter((entry) => entry.split === split)).toHaveLength(oracle.all_split_counts[split]!)
  expect(Object.isFrozen(all)).toBe(true)
  const data = requireRight(compileNativeS2STaskData(task))
  expect(data.trainDatasetSha256).toBe(oracle.train_dataset_sha256)
  expect(data.devDatasetSha256).toBe(oracle.dev_dataset_sha256)
  expect(hashTensor(data.trainInput)).toBe(oracle.train_x_sha256)
  expect(hashTensor(data.trainTargets)).toBe(oracle.train_targets_sha256)
  expect(hashTensor(data.devInput)).toBe(oracle.dev_x_sha256)
  expect(hashTensor(data.devTargets)).toBe(oracle.dev_targets_sha256)
  expect(data.weights.map(floatHex)).toEqual(oracle.weights_hex)
  expect(data.strata.map((receipt) => ({
    role: receipt.role, channel: receipt.channel, sample_count: receipt.sampleCount,
    target_numerator_sum: Number(receipt.targetNumeratorSum),
    target_numerator_sum_squares: Number(receipt.targetNumeratorSumSquares),
    centered_sum_squares_numerator: Number(receipt.centeredSumSquaresNumerator),
    inverse_variance_weight_hex: floatHex(receipt.inverseVarianceWeight),
    receipt_sha256: receipt.receiptSha256
  }))).toEqual(oracle.strata.map(({ schema_version: _schema, target_scale_exponent: _scale, variance_definition: _definition, ...receipt }) => receipt))
}, 30_000)

it("matches independent Python commitments for a second draw and a distinct external seed", () => {
  for (const expected of multiTaskOracle.tasks) {
    const task = requireRight(generateNativeS2STask(Uint8Array.from(Buffer.from(expected.external_seed_hex, "hex")), BigInt(expected.draw_index)))
    expect(task.manifestSha256).toBe(expected.manifest_sha256)
    const data = requireRight(compileNativeS2STaskData(task))
    expect(data.trainDatasetSha256).toBe(expected.train_dataset_sha256)
    expect(data.devDatasetSha256).toBe(expected.dev_dataset_sha256)
    expect(data.weights.map(floatHex)).toEqual(expected.weights_hex)
  }
}, 30_000)

it("renders Python-compatible binary64 hex including signed zero and subnormals", () => {
  expect(floatHex(1)).toBe("0x1.0000000000000p+0")
  expect(floatHex(1.5)).toBe("0x1.8000000000000p+0")
  expect(floatHex(-0)).toBe("-0x0.0p+0")
  expect(floatHex(Number.MIN_VALUE)).toBe("0x0.0000000000001p-1022")
})

it("rejects incomplete, mutable, duplicated, and cross-split dataset boundaries", () => {
  const task = requireRight(generateNativeS2STask(seed, 0n))
  const train = requireRight(enumerateNativeS2STaskCases(task, "train"))
  expect(Either.isLeft(validateNativeS2SCaseTuple(task, train.slice(1), "train"))).toBe(true)
  expect(Either.isLeft(validateNativeS2SCaseTuple(task, [...train], "train"))).toBe(true)
  expect(Either.isLeft(nativeS2SDatasetSha256(task, Object.freeze([...train.slice(0, -1), train[0]!]), "train"))).toBe(true)
  expect(Either.isLeft(buildNativeS2SStratumLossReceipts(train.slice(0, -1)))).toBe(true)
  const sparse = Array<unknown>(6_250); sparse[0] = train[0]
  expect(Either.isLeft(buildNativeS2SStratumLossReceipts(sparse))).toBe(true)
  expect(Either.isLeft(buildNativeS2SStratumLossReceipts(Object.freeze(Array.from({ length: 6_250 }, () => null))))).toBe(true)
  const otherTask = requireRight(generateNativeS2STask(seed, 1n))
  const otherCase = requireRight(evaluateNativeS2STaskCase(otherTask, train[0]!.rawValues))
  expect(Either.isLeft(validateNativeS2SCaseTuple(task, Object.freeze([otherCase, ...train.slice(1)]), "train"))).toBe(true)
  const receipts = requireRight(buildNativeS2SStratumLossReceipts(train))
  expect(requireRight(nativeS2SWeightMatrix(Object.freeze([...receipts].reverse())))).toEqual(receipts.map((receipt) => receipt.inverseVarianceWeight))
  const sparseReceipts = Array<unknown>(6); sparseReceipts[0] = receipts[0]
  expect(Either.isLeft(nativeS2SWeightMatrix(sparseReceipts))).toBe(true)
})
