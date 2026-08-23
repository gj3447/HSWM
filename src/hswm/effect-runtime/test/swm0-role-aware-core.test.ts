import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either, Encoding, Schema } from "effect"

import {
  canonicalS2SControlJson,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION,
  SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
  SWM0RoleAwareT16InputSchema,
  SWM0RoleAwareT16ParameterArchiveSchema
} from "../src/swm0-role-aware-core-schema.js"
import {
  SWM0_ROLE_AWARE_T16_EQUIVARIANCE_ABSOLUTE_TOLERANCE,
  SWM0_ROLE_AWARE_T16_EQUIVARIANCE_RELATIVE_TOLERANCE,
  SWM0_ROLE_AWARE_T16_FORWARD_ABSOLUTE_TOLERANCE,
  SWM0_ROLE_AWARE_T16_FORWARD_RELATIVE_TOLERANCE,
  SWM0_ROLE_AWARE_T16_OPERATOR_BINDING_SCHEMA_VERSION,
  SWM0_ROLE_AWARE_T16_PYTHON_ARCHITECTURE_RECEIPT_SHA256,
  SWM0_ROLE_AWARE_T16_ROLE_CYCLES,
  broadcastSWM0RoleAwareT16Result,
  evaluateSWM0RoleAwareT16,
  evaluateSWM0RoleAwareT16RoleCycles,
  makeSWM0RoleAwareT16Operator,
  removeSWM0RoleAwareT16Q,
  restoreSWM0RoleAwareT16Q,
  type SWM0RoleAwareT16Error,
  type SWM0RoleAwareT16Result
} from "../src/swm0-role-aware-core.js"
import * as CoreModule from "../src/swm0-role-aware-core.js"

const NumericRecordSchema = Schema.Struct({
  byte_length: Schema.Number.pipe(Schema.int(), Schema.nonNegative()),
  bytes_base64: Schema.String,
  bytes_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)),
  dtype: Schema.Literal("float64-le"),
  shape: Schema.Array(Schema.Number.pipe(Schema.int(), Schema.positive()))
})

const ComparisonSchema = Schema.Struct({
  max_absolute_error_hex: Schema.String,
  max_relative_error_hex: Schema.String,
  max_ulp_distance: Schema.Number.pipe(Schema.int(), Schema.nonNegative())
})

const OutputPairSchema = Schema.Struct({
  scalar: NumericRecordSchema,
  numpy: NumericRecordSchema,
  comparison: ComparisonSchema,
  scalar_recipient_output_sha256: Schema.String.pipe(
    Schema.pattern(/^[0-9a-f]{64}$/)
  )
})

const WorldSchema = Schema.Struct({
  raw_values: Schema.Tuple(
    Schema.Number,
    Schema.Number,
    Schema.Number,
    Schema.Number,
    Schema.Number,
    Schema.Number
  ),
  input: SWM0RoleAwareT16InputSchema,
  input_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)),
  compiled_input: NumericRecordSchema,
  output: OutputPairSchema
})

const MemberSwapSchema = Schema.Struct({
  mask: Schema.Tuple(
    Schema.Literal(0, 1),
    Schema.Literal(0, 1),
    Schema.Literal(0, 1)
  ),
  input: SWM0RoleAwareT16InputSchema,
  input_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)),
  output: OutputPairSchema
})

const RoleCycleSchema = Schema.Struct({
  cycle: Schema.Union(
    Schema.Tuple(Schema.Literal(1), Schema.Literal(2), Schema.Literal(0)),
    Schema.Tuple(Schema.Literal(2), Schema.Literal(0), Schema.Literal(1))
  ),
  scalar: NumericRecordSchema,
  numpy: NumericRecordSchema,
  comparison: ComparisonSchema,
  scalar_recipient_output_sha256: Schema.String.pipe(
    Schema.pattern(/^[0-9a-f]{64}$/)
  )
})

const ControlsSchema = Schema.Struct({
  world_index: Schema.Literal(1),
  member_swaps: Schema.Array(MemberSwapSchema),
  role_cycles: Schema.Array(RoleCycleSchema),
  q_removed: Schema.Struct({
    parameters_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)),
    numeric_core_state_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    ),
    operator_binding_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    ),
    removed_q_bytes_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    ),
    positive_zero_q_bytes_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    ),
    python_receipt: Schema.Unknown,
    output: OutputPairSchema
  }),
  q_restored: Schema.Struct({
    parameters_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)),
    numeric_core_state_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    ),
    scalar: NumericRecordSchema,
    numpy: NumericRecordSchema
  }),
  broadcast: Schema.Struct({
    source_scalar_bytes_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    ),
    scalar: NumericRecordSchema,
    scalar_recipient_output_sha256: Schema.String.pipe(
      Schema.pattern(/^[0-9a-f]{64}$/)
    )
  })
})

const GenerationSchema = Schema.Struct({
  seed_material: Schema.String,
  external_seed_commitment_sha256: Schema.String.pipe(
    Schema.pattern(/^[0-9a-f]{64}$/)
  ),
  draw_index: Schema.Number.pipe(Schema.int(), Schema.nonNegative()),
  initializer_seed: Schema.Number.pipe(Schema.int(), Schema.nonNegative()),
  learning_rate_hex: Schema.String,
  max_updates: Schema.Literal(1),
  best_update: Schema.Literal(1)
})

const PythonArchiveRecordSchema = Schema.Struct({
  byte_length: Schema.Number.pipe(Schema.int(), Schema.positive()),
  canonical_bytes_base64: Schema.String,
  raw_bytes_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)),
  receipt_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
})

const ModelSchema = Schema.Struct({
  label: Schema.Literal("A", "B"),
  generation: GenerationSchema,
  python_learned_archive: PythonArchiveRecordSchema,
  projection: SWM0RoleAwareT16ParameterArchiveSchema,
  expected_numeric_core_state_sha256: Schema.String.pipe(
    Schema.pattern(/^[0-9a-f]{64}$/)
  ),
  expected_operator_binding_sha256: Schema.String.pipe(
    Schema.pattern(/^[0-9a-f]{64}$/)
  ),
  worlds: Schema.Array(WorldSchema),
  controls: ControlsSchema
})

const ArithmeticContractSchema = Schema.Struct({
  scalar_oracle: Schema.Literal("PYTHON_EXPLICIT_ASCENDING_D_H_SOURCE_LOOPS"),
  scalar_typescript_expected: Schema.Literal("EXACT_FLOAT64_BYTES"),
  numpy_einsum_absolute_tolerance_hex: Schema.String,
  numpy_einsum_relative_tolerance_hex: Schema.String,
  member_equivariance_absolute_tolerance_hex: Schema.String,
  member_equivariance_relative_tolerance_hex: Schema.String,
  parameter_and_restore_tolerance: Schema.Literal("EXACT_BYTES_ONLY")
})

const RuntimeRecordSchema = Schema.Struct({
  python_implementation: Schema.String,
  python_version: Schema.String,
  numpy_version: Schema.String,
  byteorder: Schema.Literal("little"),
  threads_per_native_pool: Schema.Literal(1)
})

const WorldValuesSchema = Schema.Array(
  Schema.Tuple(
    Schema.Number,
    Schema.Number,
    Schema.Number,
    Schema.Number,
    Schema.Number,
    Schema.Number
  )
)

const FixtureSchema = Schema.Struct({
  schema_version: Schema.Literal(
    "hswm-swm0-role-aware-t16-python-parity-fixture/v1"
  ),
  classification: Schema.Literal(
    "TEST_ORACLE_ENGINEERING_PARITY_ONLY_NON_AUTHORIZING"
  ),
  claim_boundary: Schema.Literal(
    "NO_NEW_TRAINING_CLAIM_NO_EFFICACY_VERDICT_NO_PROTOCOL_PASS"
  ),
  arithmetic_contract: ArithmeticContractSchema,
  runtime_record: RuntimeRecordSchema,
  world_values: WorldValuesSchema,
  models: Schema.Array(ModelSchema),
  receipt_sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
})

type NumericRecord = Schema.Schema.Type<typeof NumericRecordSchema>
type Archive = Schema.Schema.Type<
  typeof SWM0RoleAwareT16ParameterArchiveSchema
>

const FIXTURE_URL = new URL(
  "../../../../tests/fixtures/swm0_role_aware_core_python_v1.canonical.json",
  import.meta.url
)

const rightOrThrow = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const fixtureRaw = readFileSync(FIXTURE_URL)
const fixtureParsed: unknown = JSON.parse(fixtureRaw.toString("utf8"))
const fixture = Schema.decodeUnknownSync(FixtureSchema, {
  onExcessProperty: "error"
})(fixtureParsed)

const decodeNumericBytes = (record: NumericRecord): Uint8Array => {
  const bytes = rightOrThrow(Encoding.decodeBase64(record.bytes_base64))
  expect(Encoding.encodeBase64(bytes)).toBe(record.bytes_base64)
  expect(bytes.byteLength).toBe(record.byte_length)
  expect(rawS2SFileSha256(bytes)).toBe(record.bytes_sha256)
  return bytes
}

const decodeNumericValues = (record: NumericRecord): Float64Array => {
  const bytes = decodeNumericBytes(record)
  const values = new Float64Array(bytes.byteLength / 8)
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  for (let index = 0; index < values.length; index += 1) {
    values[index] = view.getFloat64(index * 8, true)
  }
  return values
}

const resultBytes = (result: SWM0RoleAwareT16Result): Uint8Array => {
  const bytes = new Uint8Array(12 * 8)
  const view = new DataView(bytes.buffer)
  let index = 0
  for (const recipient of result.recipients) {
    for (const value of recipient.activation) {
      view.setFloat64(index * 8, value, true)
      index += 1
    }
  }
  expect(index).toBe(12)
  return bytes
}

const resultValues = (result: SWM0RoleAwareT16Result): Float64Array => {
  const values = new Float64Array(12)
  let index = 0
  for (const recipient of result.recipients) {
    for (const value of recipient.activation) {
      values[index] = value
      index += 1
    }
  }
  return values
}

const expectClose = (
  actual: Float64Array,
  expected: Float64Array,
  absoluteTolerance: number,
  relativeTolerance: number
): void => {
  expect(actual.length).toBe(expected.length)
  for (let index = 0; index < actual.length; index += 1) {
    const left = actual[index]
    const right = expected[index]
    if (left === undefined || right === undefined) {
      throw new RangeError("numeric comparison index drifted")
    }
    expect(Number.isFinite(left)).toBe(true)
    expect(Number.isFinite(right)).toBe(true)
    expect(Math.abs(left - right)).toBeLessThanOrEqual(
      absoluteTolerance + relativeTolerance * Math.abs(right)
    )
  }
}

const expectErrorReason = (
  value: Either.Either<unknown, SWM0RoleAwareT16Error>,
  reason: SWM0RoleAwareT16Error["reason"]
): void => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isLeft(value)) expect(value.left.reason).toBe(reason)
}

const permutations = <A>(values: ReadonlyArray<A>): Array<Array<A>> => {
  if (values.length === 0) return [[]]
  const result: Array<Array<A>> = []
  for (let index = 0; index < values.length; index += 1) {
    const head = values[index]
    if (head === undefined) throw new RangeError("permutation index drifted")
    const remainder = [...values.slice(0, index), ...values.slice(index + 1)]
    for (const tail of permutations(remainder)) result.push([head, ...tail])
  }
  return result
}

const u64be = (value: number): Uint8Array => {
  const bytes = new Uint8Array(8)
  new DataView(bytes.buffer).setBigUint64(0, BigInt(value), false)
  return bytes
}

const parameterSha256 = (
  tensors: ReadonlyArray<{
    readonly name: string
    readonly shape: ReadonlyArray<number>
    readonly bytes_base64: string
  }>
): string => {
  const digest = createHash("sha256")
  digest.update(new TextEncoder().encode("hswm-swm0w-s2s-parameters/v1\0"))
  const ordered = Array.from(tensors).sort((left, right) =>
    left.name < right.name ? -1 : left.name > right.name ? 1 : 0
  )
  for (const tensor of ordered) {
    const descriptor = rightOrThrow(
      canonicalS2SControlJson({
        dtype: "float64-le",
        name: tensor.name,
        shape: tensor.shape
      })
    )
    const descriptorBytes = new TextEncoder().encode(descriptor)
    const tensorBytes = rightOrThrow(Encoding.decodeBase64(tensor.bytes_base64))
    digest.update(u64be(descriptorBytes.byteLength))
    digest.update(descriptorBytes)
    digest.update(u64be(tensorBytes.byteLength))
    digest.update(tensorBytes)
  }
  return digest.digest("hex")
}

const archiveWithCommitments = (
  base: Archive,
  tensors: ReadonlyArray<{
    readonly schema_version: string
    readonly dtype: string
    readonly name: string
    readonly shape: ReadonlyArray<number>
    readonly byte_length: number
    readonly bytes_base64: string
    readonly bytes_sha256: string
  }>,
  parametersSha256: string
): unknown => {
  const unsigned = {
    schema_version: base.schema_version,
    classification: base.classification,
    claim_boundary: base.claim_boundary,
    arm: base.arm,
    roles: base.roles,
    parameter_count: base.parameter_count,
    parameters_sha256: parametersSha256,
    source: base.source,
    tensors
  }
  return {
    ...unsigned,
    receipt_sha256: rightOrThrow(canonicalS2SControlSha256(unsigned))
  }
}

const fixtureUnsigned = {
  schema_version: fixture.schema_version,
  classification: fixture.classification,
  claim_boundary: fixture.claim_boundary,
  arithmetic_contract: fixture.arithmetic_contract,
  runtime_record: fixture.runtime_record,
  world_values: fixture.world_values,
  models: fixture.models
}

it("loads one canonical, float-free, independently generated parity fixture", () => {
  expect(fixtureRaw.byteLength).toBeLessThanOrEqual(196_608)
  expect(
    rightOrThrow(canonicalS2SControlSha256(fixtureUnsigned))
  ).toBe(fixture.receipt_sha256)
  expect(fixture.models.map((model) => model.label)).toEqual(["A", "B"])
  expect(fixture.models.map((model) => model.worlds.length)).toEqual([6, 6])
  expect(fixture.models.map((model) => model.controls.member_swaps.length)).toEqual([
    8,
    8
  ])
  expect(fixture.models.map((model) => model.controls.role_cycles.length)).toEqual([
    2,
    2
  ])
  expect(fixture.arithmetic_contract.numpy_einsum_absolute_tolerance_hex).toBe(
    "0x1.c25c268497682p-45"
  )
  expect(fixture.arithmetic_contract.numpy_einsum_relative_tolerance_hex).toBe(
    "0x1.c25c268497682p-45"
  )
  expect(fixture.arithmetic_contract.member_equivariance_absolute_tolerance_hex).toBe(
    "0x1.6849b86a12b9bp-46"
  )
  expect(SWM0_ROLE_AWARE_T16_FORWARD_ABSOLUTE_TOLERANCE).toBe(5e-14)
  expect(SWM0_ROLE_AWARE_T16_FORWARD_RELATIVE_TOLERANCE).toBe(5e-14)
})

it("matches both learned Python projections and all six recipient outputs exactly", () => {
  for (const model of fixture.models) {
    const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
    expect(operator.parametersSha256).toBe(model.projection.parameters_sha256)
    expect(operator.numericCoreStateSha256).toBe(
      model.expected_numeric_core_state_sha256
    )
    expect(operator.operatorBindingSha256).toBe(
      model.expected_operator_binding_sha256
    )
    expect(operator.sourceProjectionLearnedClaim).toBe(true)
    expect(operator.numericCoreLearned).toBe(false)
    expect(operator.sourceLearnedStateSha256).toBe(
      model.projection.source.learned_state_sha256
    )
    expect(Object.isFrozen(operator)).toBe(true)

    for (const world of model.worlds) {
      const result = rightOrThrow(
        evaluateSWM0RoleAwareT16(operator, world.input)
      )
      expect(result.inputSha256).toBe(world.input_sha256)
      expect(resultBytes(result)).toEqual(decodeNumericBytes(world.output.scalar))
      expect(result.recipientOutputSha256).toBe(
        world.output.scalar_recipient_output_sha256
      )
      expectClose(
        resultValues(result),
        decodeNumericValues(world.output.numpy),
        SWM0_ROLE_AWARE_T16_FORWARD_ABSOLUTE_TOLERANCE,
        SWM0_ROLE_AWARE_T16_FORWARD_RELATIVE_TOLERANCE
      )
      expect(result.recipients).toHaveLength(6)
      expect(result.recipients.every(Object.isFrozen)).toBe(true)
      expect(result.recipients.every((row) => Object.isFrozen(row.activation))).toBe(
        true
      )
      expect(result.operatorSweepsExecuted).toBe(1)
      expect(result.authorizationClaimed).toBe(false)
      expect(result.scientificPassClaimed).toBe(false)
      expect(result.typescriptTrainingClaimed).toBe(false)
      expect(result.causalUpdateClaimed).toBe(false)
      expect(result.sourceLearnedStateSha256).toBe(
        model.projection.source.learned_state_sha256
      )

      const shuffledInput = {
        ...world.input,
        incidences: Array.from(world.input.incidences).reverse()
      }
      const shuffled = rightOrThrow(
        evaluateSWM0RoleAwareT16(operator, shuffledInput)
      )
      expect(shuffled.inputSha256).toBe(result.inputSha256)
      expect(shuffled.recipientOutputSha256).toBe(result.recipientOutputSha256)
      expect(shuffled.recipients).toEqual(result.recipients)
    }
  }
})

it("ignores all 720 incidence enumeration orders", () => {
  const model = fixture.models[0]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const world = model.worlds[1]
  if (world === undefined) throw new RangeError("fixture world is absent")
  const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
  const baseline = rightOrThrow(
    evaluateSWM0RoleAwareT16(operator, world.input)
  )
  const orders = permutations(world.input.incidences)
  expect(orders).toHaveLength(720)
  for (const incidences of orders) {
    const result = rightOrThrow(
      evaluateSWM0RoleAwareT16(operator, { ...world.input, incidences })
    )
    expect(result.inputSha256).toBe(baseline.inputSha256)
    expect(result.recipientOutputSha256).toBe(baseline.recipientOutputSha256)
    expect(result.recipients).toEqual(baseline.recipients)
  }
})

it("preserves all S2^3 member actions by physical recipient address", () => {
  for (const model of fixture.models) {
    const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
    const baseWorld = model.worlds[model.controls.world_index]
    if (baseWorld === undefined) throw new RangeError("control world is absent")
    const base = rightOrThrow(evaluateSWM0RoleAwareT16(operator, baseWorld.input))
    const baseByNode = new Map(
      base.recipients.map((row) => [row.nodeId, row.activation] as const)
    )
    for (const swap of model.controls.member_swaps) {
      const result = rightOrThrow(evaluateSWM0RoleAwareT16(operator, swap.input))
      expect(result.inputSha256).toBe(swap.input_sha256)
      expect(resultBytes(result)).toEqual(decodeNumericBytes(swap.output.scalar))
      expectClose(
        resultValues(result),
        decodeNumericValues(swap.output.numpy),
        SWM0_ROLE_AWARE_T16_FORWARD_ABSOLUTE_TOLERANCE,
        SWM0_ROLE_AWARE_T16_FORWARD_RELATIVE_TOLERANCE
      )
      for (const recipient of result.recipients) {
        const expected = baseByNode.get(recipient.nodeId)
        if (expected === undefined) throw new Error("physical node address drifted")
        expectClose(
          new Float64Array(recipient.activation),
          new Float64Array(expected),
          SWM0_ROLE_AWARE_T16_EQUIVARIANCE_ABSOLUTE_TOLERANCE,
          SWM0_ROLE_AWARE_T16_EQUIVARIANCE_RELATIVE_TOLERANCE
        )
      }
    }
  }
})

it("treats both registered role cycles as perturbations, never invariances", () => {
  expect(SWM0_ROLE_AWARE_T16_ROLE_CYCLES).toEqual([
    [1, 2, 0],
    [2, 0, 1]
  ])
  for (const model of fixture.models) {
    const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
    const baseWorld = model.worlds[model.controls.world_index]
    if (baseWorld === undefined) throw new RangeError("control world is absent")
    const base = rightOrThrow(evaluateSWM0RoleAwareT16(operator, baseWorld.input))
    const controls = rightOrThrow(
      evaluateSWM0RoleAwareT16RoleCycles(operator, baseWorld.input)
    )
    expect(controls).toHaveLength(2)
    for (let index = 0; index < controls.length; index += 1) {
      const actual = controls[index]
      const expected = model.controls.role_cycles[index]
      if (actual === undefined || expected === undefined) {
        throw new RangeError("role-cycle fixture drifted")
      }
      expect(actual.cycle).toEqual(expected.cycle)
      expect(resultBytes(actual.result)).toEqual(decodeNumericBytes(expected.scalar))
      expect(actual.result.recipientOutputSha256).toBe(
        expected.scalar_recipient_output_sha256
      )
      expectClose(
        resultValues(actual.result),
        decodeNumericValues(expected.numpy),
        SWM0_ROLE_AWARE_T16_FORWARD_ABSOLUTE_TOLERANCE,
        SWM0_ROLE_AWARE_T16_FORWARD_RELATIVE_TOLERANCE
      )
      expect(actual.result.recipientOutputSha256).not.toBe(
        base.recipientOutputSha256
      )
    }
  }
})

it("removes Q to positive-zero bytes and restores the exact model and output", () => {
  for (const model of fixture.models) {
    const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
    const baseWorld = model.worlds[model.controls.world_index]
    if (baseWorld === undefined) throw new RangeError("control world is absent")
    const baseline = rightOrThrow(
      evaluateSWM0RoleAwareT16(operator, baseWorld.input)
    )
    const removal = rightOrThrow(removeSWM0RoleAwareT16Q(operator))
    expect(removal.operator.parametersSha256).toBe(
      model.controls.q_removed.parameters_sha256
    )
    expect(removal.operator.numericCoreStateSha256).toBe(
      model.controls.q_removed.numeric_core_state_sha256
    )
    expect(removal.operator.operatorBindingSha256).toBe(
      model.controls.q_removed.operator_binding_sha256
    )
    expect(removal.receipt.removed_q_bytes_sha256).toBe(
      model.controls.q_removed.removed_q_bytes_sha256
    )
    const ablated = rightOrThrow(
      evaluateSWM0RoleAwareT16(removal.operator, baseWorld.input)
    )
    expect(ablated.variant).toBe("Q_REMOVED")
    expect(resultBytes(ablated)).toEqual(
      decodeNumericBytes(model.controls.q_removed.output.scalar)
    )
    expect(ablated.recipientOutputSha256).not.toBe(
      baseline.recipientOutputSha256
    )

    const restored = rightOrThrow(
      restoreSWM0RoleAwareT16Q(removal.operator, removal.receipt)
    )
    expect(restored.parametersSha256).toBe(operator.parametersSha256)
    expect(restored.numericCoreStateSha256).toBe(operator.numericCoreStateSha256)
    expect(restored.operatorBindingSha256).toBe(operator.operatorBindingSha256)
    const replay = rightOrThrow(
      evaluateSWM0RoleAwareT16(restored, baseWorld.input)
    )
    expect(resultBytes(replay)).toEqual(resultBytes(baseline))
    expect(replay.recipientOutputSha256).toBe(baseline.recipientOutputSha256)

    expectErrorReason(
      removeSWM0RoleAwareT16Q(removal.operator),
      "INTERVENTION_NOT_ALLOWED"
    )
    expectErrorReason(
      restoreSWM0RoleAwareT16Q(operator, removal.receipt),
      "Q_RECEIPT_MISMATCH"
    )
    expectErrorReason(
      restoreSWM0RoleAwareT16Q(removal.operator, {
        ...removal.receipt,
        removed_q_bytes_sha256: "0".repeat(64)
      }),
      "Q_RECEIPT_MISMATCH"
    )
  }
})

it("rejects a self-consistent forged Q receipt without its private base binding", () => {
  const model = fixture.models[0]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
  const removal = rightOrThrow(removeSWM0RoleAwareT16Q(operator))
  const forgedQBytes = new Uint8Array(768)
  const forgedQBytesSha256 = rawS2SFileSha256(forgedQBytes)
  expect(forgedQBytesSha256).not.toBe(removal.receipt.removed_q_bytes_sha256)

  const forgedBaseParametersSha256 = removal.operator.parametersSha256
  const forgedBaseCoreStateSha256 = rightOrThrow(
    canonicalS2SControlSha256({
      architecture_receipt_sha256:
        SWM0_ROLE_AWARE_T16_PYTHON_ARCHITECTURE_RECEIPT_SHA256,
      arm: "T16",
      evaluator_family_sha256: null,
      initialization_seed: null,
      intervention: null,
      learned: false,
      origin: "EXTERNAL_UNTRAINED",
      parameters_sha256: forgedBaseParametersSha256,
      schema_version: "hswm-swm0w-s2s-operator/v1",
      scientific_status: "ENGINEERING_CORE_ONLY_UNJUDGED"
    })
  )
  const forgedBaseOperatorBindingSha256 = rightOrThrow(
    canonicalS2SControlSha256({
      archive_receipt_sha256: removal.operator.archiveReceiptSha256,
      arm: "T16",
      classification: SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION,
      claim_boundary: SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
      intervention: "NONE",
      numeric_core_learned: false,
      numeric_core_state_sha256: forgedBaseCoreStateSha256,
      parameter_count: 870,
      parameters_sha256: forgedBaseParametersSha256,
      roles: removal.operator.roles,
      schema_version: SWM0_ROLE_AWARE_T16_OPERATOR_BINDING_SCHEMA_VERSION,
      source_archive_receipt_sha256:
        removal.operator.sourceArchiveReceiptSha256,
      source_learned_state_sha256: removal.operator.sourceLearnedStateSha256,
      source_projection_fitted_claim: true,
      source_projection_learned_claim: true,
      structural_task_sha256: removal.operator.structuralTaskSha256
    })
  )
  const forgedUnsigned = {
    schema_version: removal.receipt.schema_version,
    classification: removal.receipt.classification,
    intervention: removal.receipt.intervention,
    archive_receipt_sha256: removal.receipt.archive_receipt_sha256,
    base_core_state_sha256: forgedBaseCoreStateSha256,
    base_operator_binding_sha256: forgedBaseOperatorBindingSha256,
    base_parameters_sha256: forgedBaseParametersSha256,
    ablated_core_state_sha256: removal.receipt.ablated_core_state_sha256,
    ablated_operator_binding_sha256:
      removal.receipt.ablated_operator_binding_sha256,
    ablated_parameters_sha256: removal.receipt.ablated_parameters_sha256,
    removed_q_byte_length: removal.receipt.removed_q_byte_length,
    removed_q_value_count: removal.receipt.removed_q_value_count,
    removed_q_bytes_base64: Encoding.encodeBase64(forgedQBytes),
    removed_q_bytes_sha256: forgedQBytesSha256
  }
  const forged = {
    ...forgedUnsigned,
    receipt_sha256: rightOrThrow(
      canonicalS2SControlSha256(forgedUnsigned)
    )
  }

  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removal.operator, forged),
    "Q_RECEIPT_MISMATCH"
  )
})

it("rejects oversized archive and Q strings before schema hashing or decode", () => {
  const model = fixture.models[0]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const oversized = "A".repeat(4_097)
  expectErrorReason(
    makeSWM0RoleAwareT16Operator({
      ...model.projection,
      tensors: [
        { ...model.projection.tensors[0], bytes_base64: oversized },
        ...model.projection.tensors.slice(1)
      ]
    }),
    "ARCHIVE_SURFACE_INVALID"
  )
  const oversizedKeyArchive = structuredClone(model.projection)
  Reflect.set(oversizedKeyArchive, "x".repeat(257), true)
  expectErrorReason(
    makeSWM0RoleAwareT16Operator(oversizedKeyArchive),
    "ARCHIVE_SURFACE_INVALID"
  )

  const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
  const removal = rightOrThrow(removeSWM0RoleAwareT16Q(operator))
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removal.operator, {
      ...removal.receipt,
      removed_q_bytes_base64: oversized
    }),
    "Q_RECEIPT_SURFACE_INVALID"
  )
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removal.operator, {
      ...removal.receipt,
      removed_q_bytes_base64: "A".repeat(1_020)
    }),
    "Q_RECEIPT_SCHEMA_INVALID"
  )
})

it("fails closed on malformed, exotic, and cross-model Q receipts", () => {
  const modelA = fixture.models[0]
  const modelB = fixture.models[1]
  if (modelA === undefined || modelB === undefined) {
    throw new RangeError("fixture model is absent")
  }
  const removalA = rightOrThrow(
    removeSWM0RoleAwareT16Q(
      rightOrThrow(makeSWM0RoleAwareT16Operator(modelA.projection))
    )
  )
  const removalB = rightOrThrow(
    removeSWM0RoleAwareT16Q(
      rightOrThrow(makeSWM0RoleAwareT16Operator(modelB.projection))
    )
  )
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removalB.operator, removalA.receipt),
    "Q_RECEIPT_MISMATCH"
  )
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removalA.operator, {
      ...removalA.receipt,
      excess: true
    }),
    "Q_RECEIPT_SCHEMA_INVALID"
  )

  const missing = structuredClone(removalA.receipt)
  Reflect.deleteProperty(missing, "base_parameters_sha256")
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removalA.operator, missing),
    "Q_RECEIPT_SCHEMA_INVALID"
  )
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removalA.operator, {
      ...removalA.receipt,
      removed_q_bytes_base64: `!${removalA.receipt.removed_q_bytes_base64.slice(1)}`
    }),
    "Q_RECEIPT_SCHEMA_INVALID"
  )

  let accessorReads = 0
  const accessorReceipt = structuredClone(removalA.receipt)
  Reflect.deleteProperty(accessorReceipt, "receipt_sha256")
  Object.defineProperty(accessorReceipt, "receipt_sha256", {
    enumerable: true,
    get: () => {
      accessorReads += 1
      return removalA.receipt.receipt_sha256
    }
  })
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removalA.operator, accessorReceipt),
    "Q_RECEIPT_SURFACE_INVALID"
  )
  expect(accessorReads).toBe(0)

  let proxyReads = 0
  const proxiedReceipt = new Proxy(structuredClone(removalA.receipt), {
    get: (target, property, receiver) => {
      proxyReads += 1
      return Reflect.get(target, property, receiver)
    }
  })
  expectErrorReason(
    restoreSWM0RoleAwareT16Q(removalA.operator, proxiedReceipt),
    "Q_RECEIPT_SURFACE_INVALID"
  )
  expect(proxyReads).toBe(0)
})

it("broadcasts only an authentic frozen baseline without another operator sweep", () => {
  for (const model of fixture.models) {
    const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
    const baseWorld = model.worlds[model.controls.world_index]
    if (baseWorld === undefined) throw new RangeError("control world is absent")
    const baseline = rightOrThrow(
      evaluateSWM0RoleAwareT16(operator, baseWorld.input)
    )
    const broadcast = rightOrThrow(broadcastSWM0RoleAwareT16Result(baseline))
    expect(broadcast.operatorSweepsExecuted).toBe(0)
    expect(broadcast.sourceRecipientOutputSha256).toBe(
      baseline.recipientOutputSha256
    )
    expect(resultBytes(broadcast)).toEqual(
      decodeNumericBytes(model.controls.broadcast.scalar)
    )
    expect(broadcast.recipientOutputSha256).toBe(
      model.controls.broadcast.scalar_recipient_output_sha256
    )
    for (let role = 0; role < 3; role += 1) {
      expect(broadcast.recipients[2 * role]?.activation).toEqual(
        broadcast.recipients[2 * role + 1]?.activation
      )
    }
    expectErrorReason(
      broadcastSWM0RoleAwareT16Result({ ...baseline }),
      "RESULT_NOT_AUTHENTIC"
    )
    expectErrorReason(
      broadcastSWM0RoleAwareT16Result(broadcast),
      "INTERVENTION_NOT_ALLOWED"
    )
  }
})

it("fails closed on malformed topology, finite overflow, and exotic surfaces", () => {
  const model = fixture.models[0]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const world = model.worlds[0]
  if (world === undefined) throw new RangeError("fixture world is absent")
  const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(model.projection))
  const incidences = Array.from(world.input.incidences)
  const first = incidences[0]
  const second = incidences[1]
  if (first === undefined || second === undefined) {
    throw new RangeError("fixture incidence is absent")
  }

  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: [{ ...first, role: "wrong" }, ...incidences.slice(1)]
    }),
    "INPUT_SCHEMA_INVALID"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: [
        first,
        { ...second, role: first.role, member_slot: first.member_slot },
        ...incidences.slice(2)
      ]
    }),
    "INPUT_ADDRESS_CONFLICT"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: [first, { ...second, node_id: first.node_id }, ...incidences.slice(2)]
    }),
    "INPUT_ADDRESS_CONFLICT"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: [
        first,
        { ...second, incidence_id: first.incidence_id },
        ...incidences.slice(2)
      ]
    }),
    "INPUT_ADDRESS_CONFLICT"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: incidences.slice(0, 5)
    }),
    "INPUT_SCHEMA_INVALID"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: [...incidences, { ...first, incidence_id: "extra.inc" }]
    }),
    "INPUT_SCHEMA_INVALID"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: [
        { ...first, activation: [Number.NaN, 0, 0, 0] },
        ...incidences.slice(1)
      ]
    }),
    "INPUT_SCHEMA_INVALID"
  )
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, { ...world.input, excess: true }),
    "INPUT_SCHEMA_INVALID"
  )

  const hugeActivation = [Number.MAX_VALUE, Number.MAX_VALUE, 0, 0]
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: incidences.map((row) => ({
        ...row,
        activation: hugeActivation
      }))
    }),
    "RESULT_NON_FINITE"
  )

  let accessorReads = 0
  const accessorInput = structuredClone(world.input)
  Reflect.deleteProperty(accessorInput, "hyperedge_id")
  Object.defineProperty(accessorInput, "hyperedge_id", {
    enumerable: true,
    get: () => {
      accessorReads += 1
      return "forbidden"
    }
  })
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, accessorInput),
    "INPUT_SURFACE_INVALID"
  )
  expect(accessorReads).toBe(0)

  let proxyReads = 0
  const proxied = new Proxy(structuredClone(world.input), {
    get: (target, property, receiver) => {
      proxyReads += 1
      return Reflect.get(target, property, receiver)
    }
  })
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, proxied),
    "INPUT_SURFACE_INVALID"
  )
  expect(proxyReads).toBe(0)

  const sparseIncidences = new Array<unknown>(6)
  sparseIncidences[0] = first
  expectErrorReason(
    evaluateSWM0RoleAwareT16(operator, {
      ...world.input,
      incidences: sparseIncidences
    }),
    "INPUT_SURFACE_INVALID"
  )

  const repeated = rightOrThrow(evaluateSWM0RoleAwareT16(operator, world.input))
  const sourceMutation = structuredClone(world.input)
  const issued = rightOrThrow(evaluateSWM0RoleAwareT16(operator, sourceMutation))
  const mutableIncidences = sourceMutation.incidences
  Reflect.set(mutableIncidences[0] ?? {}, "activation", [999, 999, 999, 999])
  expect(resultBytes(issued)).toEqual(resultBytes(repeated))
})

it("fails closed on archive roster, byte, aggregate hash, and float drift", () => {
  const model = fixture.models[0]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const base = model.projection
  const first = base.tensors[0]
  if (first === undefined) throw new RangeError("fixture tensor is absent")

  expectErrorReason(
    makeSWM0RoleAwareT16Operator({ ...base, excess: true }),
    "ARCHIVE_SCHEMA_INVALID"
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator({
      ...base,
      tensors: [base.tensors[1], base.tensors[0], ...base.tensors.slice(2)]
    }),
    "ARCHIVE_SCHEMA_INVALID"
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator({
      ...base,
      tensors: base.tensors.slice(0, 5)
    }),
    "ARCHIVE_SCHEMA_INVALID"
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator({
      ...base,
      tensors: [...base.tensors, base.tensors[5]]
    }),
    "ARCHIVE_SCHEMA_INVALID"
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator({
      ...base,
      tensors: [{ ...first, shape: [3, 4, 15] }, ...base.tensors.slice(1)]
    }),
    "ARCHIVE_SCHEMA_INVALID"
  )

  const driftBytes = new Uint8Array(
    rightOrThrow(Encoding.decodeBase64(first.bytes_base64))
  )
  const driftFirst = driftBytes[0]
  if (driftFirst === undefined) throw new RangeError("tensor byte is absent")
  driftBytes[0] = driftFirst ^ 1
  const tensorHashDrift = {
    ...first,
    bytes_base64: Encoding.encodeBase64(driftBytes)
  }
  const tensorHashDriftArchive = archiveWithCommitments(
    base,
    [tensorHashDrift, ...base.tensors.slice(1)],
    base.parameters_sha256
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator(tensorHashDriftArchive),
    "TENSOR_BYTE_HASH_MISMATCH"
  )

  const finiteDrift = {
    ...tensorHashDrift,
    bytes_sha256: rawS2SFileSha256(driftBytes)
  }
  const finiteTensors = [finiteDrift, ...base.tensors.slice(1)]
  const aggregateDriftArchive = archiveWithCommitments(
    base,
    finiteTensors,
    base.parameters_sha256
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator(aggregateDriftArchive),
    "PARAMETER_HASH_MISMATCH"
  )

  const nanBytes = new Uint8Array(
    rightOrThrow(Encoding.decodeBase64(first.bytes_base64))
  )
  new DataView(nanBytes.buffer).setFloat64(0, Number.NaN, true)
  const nanTensor = {
    ...first,
    bytes_base64: Encoding.encodeBase64(nanBytes),
    bytes_sha256: rawS2SFileSha256(nanBytes)
  }
  const nanTensors = [nanTensor, ...base.tensors.slice(1)]
  const nanArchive = archiveWithCommitments(
    base,
    nanTensors,
    parameterSha256(nanTensors)
  )
  expectErrorReason(
    makeSWM0RoleAwareT16Operator(nanArchive),
    "TENSOR_NON_FINITE"
  )

  let accessorReads = 0
  const accessorArchive = structuredClone(base)
  Reflect.deleteProperty(accessorArchive, "arm")
  Object.defineProperty(accessorArchive, "arm", {
    enumerable: true,
    get: () => {
      accessorReads += 1
      return "T16"
    }
  })
  expectErrorReason(
    makeSWM0RoleAwareT16Operator(accessorArchive),
    "ARCHIVE_SURFACE_INVALID"
  )
  expect(accessorReads).toBe(0)

  let proxyReads = 0
  const proxiedArchive = new Proxy(structuredClone(base), {
    get: (target, property, receiver) => {
      proxyReads += 1
      return Reflect.get(target, property, receiver)
    }
  })
  expectErrorReason(
    makeSWM0RoleAwareT16Operator(proxiedArchive),
    "ARCHIVE_SURFACE_INVALID"
  )
  expect(proxyReads).toBe(0)

  const sparseTensors = new Array<unknown>(6)
  sparseTensors[0] = first
  expectErrorReason(
    makeSWM0RoleAwareT16Operator({ ...base, tensors: sparseTensors }),
    "ARCHIVE_SURFACE_INVALID"
  )

  const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(base))
  expectErrorReason(
    evaluateSWM0RoleAwareT16({ ...operator }, model.worlds[0]?.input),
    "OPERATOR_NOT_AUTHENTIC"
  )
})

it("snapshots archive bytes and returns deterministic results under reuse", async () => {
  const model = fixture.models[1]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const world = model.worlds[2]
  if (world === undefined) throw new RangeError("fixture world is absent")
  const mutableArchive = structuredClone(model.projection)
  const operator = rightOrThrow(makeSWM0RoleAwareT16Operator(mutableArchive))
  Reflect.set(mutableArchive.tensors[0] ?? {}, "bytes_base64", "AAAA")

  const results = await Promise.all(
    Array.from({ length: 16 }, async () =>
      rightOrThrow(evaluateSWM0RoleAwareT16(operator, world.input))
    )
  )
  const expected = results[0]
  if (expected === undefined) throw new RangeError("parallel result is absent")
  for (const result of results) {
    expect(result.receiptSha256).toBe(expected.receiptSha256)
    expect(resultBytes(result)).toEqual(resultBytes(expected))
  }
})

it("does not reinterpret scalar SemanticWeight or expose recurrence/update APIs", () => {
  const model = fixture.models[0]
  if (model === undefined) throw new RangeError("fixture model is absent")
  const input = model.worlds[0]?.input
  const scalarWeight = Object.freeze({
    relationId: "r",
    functionCellId: "f",
    scoreMicros: 1,
    evidenceCount: 1,
    lastOutcomeId: "o"
  })
  const attempted = Reflect.apply(evaluateSWM0RoleAwareT16, undefined, [
    scalarWeight,
    input
  ])
  expectErrorReason(attempted, "OPERATOR_NOT_AUTHENTIC")
  expect("optimizer" in makeSWM0RoleAwareT16Operator).toBe(false)
  expect("recur" in evaluateSWM0RoleAwareT16).toBe(false)
  expect("applyOutcomeCredit" in evaluateSWM0RoleAwareT16).toBe(false)
  expect("mutateTopology" in evaluateSWM0RoleAwareT16).toBe(false)
  expect("optimizer" in CoreModule).toBe(false)
  expect("recur" in CoreModule).toBe(false)
  expect("applyOutcomeCredit" in CoreModule).toBe(false)
  expect("mutateTopology" in CoreModule).toBe(false)
  expect(SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION).toBe(
    "ENGINEERING_CORE_PARAMETER_ARCHIVE_NON_AUTHORIZING"
  )
  expect(SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY).toContain("NO_TRAINING")
})
