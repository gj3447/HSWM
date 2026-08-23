import { createHash } from "node:crypto"
import { isProxy } from "node:util/types"

import { Data, Either, Encoding, Schema } from "effect"

import {
  canonicalS2SControlJson,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION,
  SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
  SWM0_ROLE_AWARE_T16_Q_REMOVAL_SCHEMA_VERSION,
  SWM0RoleAwareT16InputSchema,
  SWM0RoleAwareT16ParameterArchiveSchema,
  SWM0RoleAwareT16QRemovalReceiptSchema,
  type SWM0RoleAwareT16InputDocument,
  type SWM0RoleAwareT16ParameterArchiveDocument,
  type SWM0RoleAwareT16QRemovalReceipt
} from "./swm0-role-aware-core-schema.js"

export const SWM0_ROLE_AWARE_T16_RESULT_SCHEMA_VERSION =
  "hswm-swm0-role-aware-t16-result/v1" as const
export const SWM0_ROLE_AWARE_T16_OPERATOR_BINDING_SCHEMA_VERSION =
  "hswm-swm0-role-aware-t16-operator-binding/v1" as const
export const SWM0_ROLE_AWARE_T16_RECIPIENT_OUTPUT_HASH_VERSION =
  "hswm-swm0-role-aware-t16-recipient-output/v1" as const
export const SWM0_ROLE_AWARE_T16_PYTHON_ARCHITECTURE_RECEIPT_SHA256 =
  "65e6e27379793a7f483e8c34292ba060b60b89824822167e7483e03f7415ad29" as const
export const SWM0_ROLE_AWARE_T16_FORWARD_ABSOLUTE_TOLERANCE = 5e-14
export const SWM0_ROLE_AWARE_T16_FORWARD_RELATIVE_TOLERANCE = 5e-14
export const SWM0_ROLE_AWARE_T16_EQUIVARIANCE_ABSOLUTE_TOLERANCE = 2e-14
export const SWM0_ROLE_AWARE_T16_EQUIVARIANCE_RELATIVE_TOLERANCE = 2e-14

export const SWM0_ROLE_AWARE_T16_ROLES = Object.freeze([
  "r0",
  "r1",
  "r2"
] as const)

const ROLE_CYCLE_120 = Object.freeze([1, 2, 0] as const)
const ROLE_CYCLE_201 = Object.freeze([2, 0, 1] as const)

export const SWM0_ROLE_AWARE_T16_ROLE_CYCLES = Object.freeze([
  ROLE_CYCLE_120,
  ROLE_CYCLE_201
] as const)

const PARAMETER_HASH_DOMAIN = new TextEncoder().encode(
  "hswm-swm0w-s2s-parameters/v1\0"
)
const INPUT_HASH_DOMAIN = new TextEncoder().encode(
  "hswm-swm0-role-aware-t16-input/v1\0"
)
const OUTPUT_HASH_DOMAIN = new TextEncoder().encode(
  "hswm-swm0-role-aware-t16-recipient-output/v1\0"
)

type SWM0Role = (typeof SWM0_ROLE_AWARE_T16_ROLES)[number]
type SWM0MemberSlot = 0 | 1
type SWM0Intervention = "NONE" | "Q_REMOVED"
type SWM0ResultVariant =
  | "BASE"
  | "Q_REMOVED"
  | "WITHIN_ROLE_BROADCAST"
  | "ROLE_CYCLE_120"
  | "ROLE_CYCLE_201"

export class SWM0RoleAwareT16Error extends Data.TaggedError(
  "SWM0RoleAwareT16Error"
)<{
  readonly reason:
    | "ARCHIVE_SCHEMA_INVALID"
    | "ARCHIVE_SURFACE_INVALID"
    | "ARCHIVE_RECEIPT_MISMATCH"
    | "TENSOR_ENCODING_INVALID"
    | "TENSOR_BYTE_LENGTH_MISMATCH"
    | "TENSOR_BYTE_HASH_MISMATCH"
    | "TENSOR_NON_FINITE"
    | "PARAMETER_HASH_MISMATCH"
    | "INPUT_SCHEMA_INVALID"
    | "INPUT_SURFACE_INVALID"
    | "INPUT_ADDRESS_CONFLICT"
    | "INPUT_LAYOUT_INCOMPLETE"
    | "OPERATOR_NOT_AUTHENTIC"
    | "RESULT_NOT_AUTHENTIC"
    | "RESULT_NON_FINITE"
    | "INTERVENTION_NOT_ALLOWED"
    | "Q_RECEIPT_SCHEMA_INVALID"
    | "Q_RECEIPT_SURFACE_INVALID"
    | "Q_RECEIPT_MISMATCH"
    | "CANONICAL_HASH_FAILED"
  readonly phase: "ARCHIVE" | "INPUT" | "EVALUATE" | "CONTROL" | "Q"
  readonly detail: string
}> {}

export interface SWM0RoleAwareT16Operator {
  readonly schemaVersion: typeof SWM0_ROLE_AWARE_T16_OPERATOR_BINDING_SCHEMA_VERSION
  readonly classification: typeof SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION
  readonly claimBoundary: typeof SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY
  readonly arm: "T16"
  readonly roles: typeof SWM0_ROLE_AWARE_T16_ROLES
  readonly parameterCount: 870
  readonly intervention: SWM0Intervention
  readonly parametersSha256: string
  /** Exact Python `S2SOperator(EXTERNAL_UNTRAINED)` state commitment. */
  readonly numericCoreStateSha256: string
  /** TS projection binding that additionally commits the source archive. */
  readonly operatorBindingSha256: string
  readonly archiveReceiptSha256: string
  readonly sourceArchiveReceiptSha256: string
  readonly sourceLearnedStateSha256: string
  readonly structuralTaskSha256: string
  readonly sourceProjectionFittedClaim: true
  readonly sourceProjectionLearnedClaim: true
  readonly numericCoreLearned: false
}

export interface SWM0RoleAwareT16RecipientActivation {
  readonly incidenceId: string
  readonly memberSlot: SWM0MemberSlot
  readonly nodeId: string
  readonly role: SWM0Role
  readonly activation: readonly [number, number]
}

export interface SWM0RoleAwareT16Result {
  readonly schemaVersion: typeof SWM0_ROLE_AWARE_T16_RESULT_SCHEMA_VERSION
  readonly classification: "ENGINEERING_ONE_SWEEP_RESULT_NON_AUTHORIZING"
  readonly claimBoundary: typeof SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY
  readonly hyperedgeId: string
  readonly variant: SWM0ResultVariant
  readonly intervention: SWM0Intervention
  readonly roleCycle: readonly [number, number, number] | null
  readonly operatorSweepsExecuted: 0 | 1
  readonly sourceRecipientOutputSha256: string | null
  readonly recipientCount: 6
  readonly channelCount: 2
  readonly inputSha256: string
  readonly parametersSha256: string
  readonly numericCoreStateSha256: string
  readonly operatorBindingSha256: string
  readonly archiveReceiptSha256: string
  readonly sourceArchiveReceiptSha256: string
  readonly sourceLearnedStateSha256: string
  readonly structuralTaskSha256: string
  readonly recipientOutputSha256: string
  readonly recipients: ReadonlyArray<SWM0RoleAwareT16RecipientActivation>
  readonly authorizationClaimed: false
  readonly scientificPassClaimed: false
  readonly typescriptTrainingClaimed: false
  readonly causalUpdateClaimed: false
  readonly receiptSha256: string
}

export interface SWM0RoleAwareT16QRemoval {
  readonly operator: SWM0RoleAwareT16Operator
  readonly receipt: SWM0RoleAwareT16QRemovalReceipt
}

export interface SWM0RoleAwareT16RoleCycleResult {
  readonly cycle: readonly [number, number, number]
  readonly result: SWM0RoleAwareT16Result
}

interface EncodedTensorDocument {
  readonly name: string
  readonly shape: ReadonlyArray<number>
  readonly byte_length: number
  readonly bytes_base64: string
  readonly bytes_sha256: string
}

interface TensorSnapshot {
  readonly name: string
  readonly shape: ReadonlyArray<number>
  readonly bytes: Uint8Array
  readonly values: Float64Array
}

interface ParameterSnapshot {
  readonly phiW: TensorSnapshot
  readonly psiW: TensorSnapshot
  readonly unaryW: TensorSnapshot
  readonly pairW: TensorSnapshot
  readonly qW: TensorSnapshot
  readonly outB: TensorSnapshot
}

interface SourceProjectionSnapshot {
  readonly sourceArchiveReceiptSha256: string
  readonly learnedStateSha256: string
  readonly structuralTaskSha256: string
}

interface OperatorSnapshot {
  readonly parameters: ParameterSnapshot
  readonly source: SourceProjectionSnapshot
  readonly archiveReceiptSha256: string
  readonly qRestoration: QRestorationSnapshot | null
}

interface QRestorationSnapshot {
  readonly qW: TensorSnapshot
  readonly baseParametersSha256: string
  readonly baseCoreStateSha256: string
  readonly baseOperatorBindingSha256: string
  readonly removedQBytesSha256: string
}

interface RecipientAddress {
  readonly incidenceId: string
  readonly memberSlot: SWM0MemberSlot
  readonly nodeId: string
  readonly role: SWM0Role
}

interface CompiledInput {
  readonly hyperedgeId: string
  readonly values: Float64Array
  readonly recipients: ReadonlyArray<RecipientAddress>
  readonly inputSha256: string
}

interface ResultSnapshot {
  readonly operator: SWM0RoleAwareT16Operator
  readonly input: CompiledInput
  readonly output: Float64Array
  readonly variant: SWM0ResultVariant
  readonly roleCycle: readonly [number, number, number] | null
}

const OPERATORS = new WeakMap<SWM0RoleAwareT16Operator, OperatorSnapshot>()
const RESULTS = new WeakMap<SWM0RoleAwareT16Result, ResultSnapshot>()

const failure = (
  reason: SWM0RoleAwareT16Error["reason"],
  phase: SWM0RoleAwareT16Error["phase"],
  detail: string
): SWM0RoleAwareT16Error =>
  new SWM0RoleAwareT16Error({ reason, phase, detail })

interface SurfaceBudget {
  nodes: number
  stringCharacters: number
}

/** Inspect JSON-like data without invoking accessors or proxy traps. */
const isPlainDataSurface = (
  value: unknown,
  budget: SurfaceBudget,
  depth = 0
): boolean => {
  if (
    value === null ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return true
  }
  if (typeof value === "string") {
    if (value.length > 4_096) return false
    budget.stringCharacters += value.length
    return budget.stringCharacters <= 16_384
  }
  if (typeof value !== "object" || isProxy(value) || depth > 12) return false
  budget.nodes += 1
  if (budget.nodes > 512) return false
  try {
    if (Array.isArray(value)) {
      if (value.length > 128) return false
      const keys = Reflect.ownKeys(value)
      if (keys.length !== value.length + 1) return false
      for (let index = 0; index < value.length; index += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
        if (
          descriptor === undefined ||
          !descriptor.enumerable ||
          !("value" in descriptor) ||
          !isPlainDataSurface(descriptor.value, budget, depth + 1)
        ) {
          return false
        }
      }
      return keys.every(
        (key) =>
          key === "length" ||
          (typeof key === "string" &&
            Number.isSafeInteger(Number(key)) &&
            String(Number(key)) === key &&
            Number(key) >= 0 &&
            Number(key) < value.length)
      )
    }
    if (Object.getPrototypeOf(value) !== Object.prototype) return false
    const keys = Reflect.ownKeys(value)
    if (keys.length > 64 || keys.some((key) => typeof key !== "string")) {
      return false
    }
    for (const key of keys) {
      if (typeof key !== "string") return false
      if (key.length > 256) return false
      budget.stringCharacters += key.length
      if (budget.stringCharacters > 16_384) return false
      const descriptor = Object.getOwnPropertyDescriptor(value, key)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor) ||
        !isPlainDataSurface(descriptor.value, budget, depth + 1)
      ) {
        return false
      }
    }
    return true
  } catch {
    return false
  }
}

const hasPlainDataSurface = (value: unknown): boolean =>
  isPlainDataSurface(value, { nodes: 0, stringCharacters: 0 })

const canonicalHash = (
  value: unknown,
  phase: SWM0RoleAwareT16Error["phase"]
): Either.Either<string, SWM0RoleAwareT16Error> => {
  const hashed = canonicalS2SControlSha256(value)
  return Either.isLeft(hashed)
    ? Either.left(
        failure(
          "CANONICAL_HASH_FAILED",
          phase,
          `canonical control hash rejected ${hashed.left.reason} at ${hashed.left.path}`
        )
      )
    : Either.right(hashed.right)
}

const u64be = (value: number): Uint8Array => {
  const bytes = new Uint8Array(8)
  new DataView(bytes.buffer).setBigUint64(0, BigInt(value), false)
  return bytes
}

const updateSegment = (
  digest: ReturnType<typeof createHash>,
  bytes: Uint8Array
): void => {
  digest.update(u64be(bytes.byteLength))
  digest.update(bytes)
}

const numberAt = (values: Float64Array, index: number): number => {
  const value = values[index]
  if (value === undefined) {
    throw new RangeError(`internal numeric index ${index} is out of range`)
  }
  return value
}

const itemAt = <A>(values: ReadonlyArray<A>, index: number): A => {
  const value = values[index]
  if (value === undefined) {
    throw new RangeError(`internal array index ${index} is out of range`)
  }
  return value
}

const float64Bytes = (values: Float64Array): Uint8Array => {
  const bytes = new Uint8Array(values.length * 8)
  const view = new DataView(bytes.buffer)
  for (let index = 0; index < values.length; index += 1) {
    view.setFloat64(index * 8, numberAt(values, index), true)
  }
  return bytes
}

const valuesFromFloat64Bytes = (
  bytes: Uint8Array,
  phase: "ARCHIVE" | "Q"
): Either.Either<Float64Array, SWM0RoleAwareT16Error> => {
  const values = new Float64Array(bytes.byteLength / 8)
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  for (let index = 0; index < values.length; index += 1) {
    const value = view.getFloat64(index * 8, true)
    if (!Number.isFinite(value)) {
      return Either.left(
        failure(
          "TENSOR_NON_FINITE",
          phase,
          `tensor value ${index} is not finite`
        )
      )
    }
    values[index] = value
  }
  return Either.right(values)
}

const decodeTensor = (
  document: EncodedTensorDocument,
  phase: "ARCHIVE" | "Q" = "ARCHIVE"
): Either.Either<TensorSnapshot, SWM0RoleAwareT16Error> => {
  const decoded = Encoding.decodeBase64(document.bytes_base64)
  if (Either.isLeft(decoded)) {
    return Either.left(
      failure(
        "TENSOR_ENCODING_INVALID",
        phase,
        `${document.name} is not valid RFC 4648 base64`
      )
    )
  }
  const bytes = new Uint8Array(decoded.right)
  if (Encoding.encodeBase64(bytes) !== document.bytes_base64) {
    return Either.left(
      failure(
        "TENSOR_ENCODING_INVALID",
        phase,
        `${document.name} base64 is not canonical`
      )
    )
  }
  if (bytes.byteLength !== document.byte_length) {
    return Either.left(
      failure(
        "TENSOR_BYTE_LENGTH_MISMATCH",
        phase,
        `${document.name} byte length does not match its exact shape`
      )
    )
  }
  if (rawS2SFileSha256(bytes) !== document.bytes_sha256) {
    return Either.left(
      failure(
        "TENSOR_BYTE_HASH_MISMATCH",
        phase,
        `${document.name} raw byte hash mismatch`
      )
    )
  }
  const values = valuesFromFloat64Bytes(bytes, phase)
  if (Either.isLeft(values)) return Either.left(values.left)
  return Either.right(
    Object.freeze({
      name: document.name,
      shape: Object.freeze(Array.from(document.shape)),
      bytes,
      values: values.right
    })
  )
}

const parameterTensors = (
  parameters: ParameterSnapshot
): ReadonlyArray<TensorSnapshot> => [
  parameters.phiW,
  parameters.psiW,
  parameters.unaryW,
  parameters.pairW,
  parameters.qW,
  parameters.outB
]

const parameterSha256 = (
  parameters: ParameterSnapshot
): Either.Either<string, SWM0RoleAwareT16Error> => {
  const digest = createHash("sha256")
  digest.update(PARAMETER_HASH_DOMAIN)
  const tensors = Array.from(parameterTensors(parameters)).sort((left, right) =>
    left.name < right.name ? -1 : left.name > right.name ? 1 : 0
  )
  for (const tensor of tensors) {
    const descriptor = canonicalS2SControlJson({
      dtype: "float64-le",
      name: tensor.name,
      shape: tensor.shape
    })
    if (Either.isLeft(descriptor)) {
      return Either.left(
        failure(
          "CANONICAL_HASH_FAILED",
          "ARCHIVE",
          `parameter descriptor for ${tensor.name} was not canonical`
        )
      )
    }
    const descriptorBytes = new TextEncoder().encode(descriptor.right)
    updateSegment(digest, descriptorBytes)
    updateSegment(digest, tensor.bytes)
  }
  return Either.right(digest.digest("hex"))
}

const archiveUnsigned = (
  document: SWM0RoleAwareT16ParameterArchiveDocument
): unknown => ({
  schema_version: document.schema_version,
  classification: document.classification,
  claim_boundary: document.claim_boundary,
  arm: document.arm,
  roles: document.roles,
  parameter_count: document.parameter_count,
  parameters_sha256: document.parameters_sha256,
  source: document.source,
  tensors: document.tensors,
})

const numericCoreStateSha256 = (
  parametersSha256: string,
  intervention: SWM0Intervention
): Either.Either<string, SWM0RoleAwareT16Error> =>
  canonicalHash(
    {
      architecture_receipt_sha256:
        SWM0_ROLE_AWARE_T16_PYTHON_ARCHITECTURE_RECEIPT_SHA256,
      arm: "T16",
      evaluator_family_sha256: null,
      initialization_seed: null,
      intervention: intervention === "NONE" ? null : "Q_REMOVED",
      learned: false,
      origin: "EXTERNAL_UNTRAINED",
      parameters_sha256: parametersSha256,
      schema_version: "hswm-swm0w-s2s-operator/v1",
      scientific_status: "ENGINEERING_CORE_ONLY_UNJUDGED"
    },
    "ARCHIVE"
  )

const operatorBindingSha256 = (
  input: {
    readonly archiveReceiptSha256: string
    readonly numericCoreStateSha256: string
    readonly parametersSha256: string
    readonly source: SourceProjectionSnapshot
    readonly intervention: SWM0Intervention
  }
): Either.Either<string, SWM0RoleAwareT16Error> =>
  canonicalHash(
    {
      archive_receipt_sha256: input.archiveReceiptSha256,
      arm: "T16",
      classification: SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION,
      claim_boundary: SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
      intervention: input.intervention,
      numeric_core_learned: false,
      numeric_core_state_sha256: input.numericCoreStateSha256,
      parameter_count: 870,
      parameters_sha256: input.parametersSha256,
      roles: SWM0_ROLE_AWARE_T16_ROLES,
      schema_version: SWM0_ROLE_AWARE_T16_OPERATOR_BINDING_SCHEMA_VERSION,
      source_archive_receipt_sha256:
        input.source.sourceArchiveReceiptSha256,
      source_learned_state_sha256: input.source.learnedStateSha256,
      source_projection_fitted_claim: true,
      source_projection_learned_claim: true,
      structural_task_sha256: input.source.structuralTaskSha256
    },
    "ARCHIVE"
  )

const makeOperator = (
  parameters: ParameterSnapshot,
  source: SourceProjectionSnapshot,
  archiveReceiptSha256: string,
  intervention: SWM0Intervention,
  qRestoration: QRestorationSnapshot | null = null
): Either.Either<SWM0RoleAwareT16Operator, SWM0RoleAwareT16Error> => {
  const parametersHash = parameterSha256(parameters)
  if (Either.isLeft(parametersHash)) return Either.left(parametersHash.left)
  const coreState = numericCoreStateSha256(parametersHash.right, intervention)
  if (Either.isLeft(coreState)) return Either.left(coreState.left)
  const binding = operatorBindingSha256({
    archiveReceiptSha256,
    numericCoreStateSha256: coreState.right,
    parametersSha256: parametersHash.right,
    source,
    intervention
  })
  if (Either.isLeft(binding)) return Either.left(binding.left)
  const operator: SWM0RoleAwareT16Operator = Object.freeze({
    schemaVersion: SWM0_ROLE_AWARE_T16_OPERATOR_BINDING_SCHEMA_VERSION,
    classification: SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION,
    claimBoundary: SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
    arm: "T16",
    roles: SWM0_ROLE_AWARE_T16_ROLES,
    parameterCount: 870,
    intervention,
    parametersSha256: parametersHash.right,
    numericCoreStateSha256: coreState.right,
    operatorBindingSha256: binding.right,
    archiveReceiptSha256,
    sourceArchiveReceiptSha256: source.sourceArchiveReceiptSha256,
    sourceLearnedStateSha256: source.learnedStateSha256,
    structuralTaskSha256: source.structuralTaskSha256,
    sourceProjectionFittedClaim: true,
    sourceProjectionLearnedClaim: true,
    numericCoreLearned: false
  })
  OPERATORS.set(
    operator,
    Object.freeze({
      parameters,
      source,
      archiveReceiptSha256,
      qRestoration
    })
  )
  return Either.right(operator)
}

/**
 * Decode and snapshot the exact numeric projection of a Python learned archive.
 * This verifies internal byte/hash consistency, not source provenance, the
 * Python training event, or an efficacy claim.
 */
export const makeSWM0RoleAwareT16Operator = (
  input: unknown
): Either.Either<SWM0RoleAwareT16Operator, SWM0RoleAwareT16Error> => {
  if (!hasPlainDataSurface(input)) {
    return Either.left(
      failure(
        "ARCHIVE_SURFACE_INVALID",
        "ARCHIVE",
        "archive must be bounded dense plain data without proxies or accessors"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(
    SWM0RoleAwareT16ParameterArchiveSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return Either.left(
      failure(
        "ARCHIVE_SCHEMA_INVALID",
        "ARCHIVE",
        "archive failed the strict Effect Schema boundary"
      )
    )
  }
  const document = decoded.right
  const receipt = canonicalHash(archiveUnsigned(document), "ARCHIVE")
  if (
    Either.isLeft(receipt) ||
    receipt.right !== document.receipt_sha256
  ) {
    return Either.left(
      failure(
        "ARCHIVE_RECEIPT_MISMATCH",
        "ARCHIVE",
        "archive self-receipt does not bind the strict projection"
      )
    )
  }

  const phiW = decodeTensor(document.tensors[0])
  if (Either.isLeft(phiW)) return Either.left(phiW.left)
  const psiW = decodeTensor(document.tensors[1])
  if (Either.isLeft(psiW)) return Either.left(psiW.left)
  const unaryW = decodeTensor(document.tensors[2])
  if (Either.isLeft(unaryW)) return Either.left(unaryW.left)
  const pairW = decodeTensor(document.tensors[3])
  if (Either.isLeft(pairW)) return Either.left(pairW.left)
  const qW = decodeTensor(document.tensors[4])
  if (Either.isLeft(qW)) return Either.left(qW.left)
  const outB = decodeTensor(document.tensors[5])
  if (Either.isLeft(outB)) return Either.left(outB.left)

  const parameters: ParameterSnapshot = Object.freeze({
    phiW: phiW.right,
    psiW: psiW.right,
    unaryW: unaryW.right,
    pairW: pairW.right,
    qW: qW.right,
    outB: outB.right
  })
  const parametersHash = parameterSha256(parameters)
  if (
    Either.isLeft(parametersHash) ||
    parametersHash.right !== document.parameters_sha256
  ) {
    return Either.left(
      failure(
        "PARAMETER_HASH_MISMATCH",
        "ARCHIVE",
        "Python-compatible aggregate parameter hash mismatch"
      )
    )
  }
  const source: SourceProjectionSnapshot = Object.freeze({
    sourceArchiveReceiptSha256:
      document.source.source_archive_receipt_sha256,
    learnedStateSha256: document.source.learned_state_sha256,
    structuralTaskSha256: document.source.structural_task_sha256
  })
  return makeOperator(
    parameters,
    source,
    document.receipt_sha256,
    "NONE"
  )
}

const roleIndex = (role: SWM0Role): number =>
  role === "r0" ? 0 : role === "r1" ? 1 : 2

const inputIndex = (
  role: number,
  member: number,
  channel: number
): number => (role * 2 + member) * 4 + channel

const outputIndex = (
  role: number,
  member: number,
  channel: number
): number => (role * 2 + member) * 2 + channel

const hiddenIndex = (role: number, member: number, hidden: number): number =>
  (role * 2 + member) * 16 + hidden

const roleHiddenIndex = (role: number, hidden: number): number =>
  role * 16 + hidden

const phiIndex = (role: number, channel: number, hidden: number): number =>
  (role * 4 + channel) * 16 + hidden

const headIndex = (role: number, channel: number, hidden: number): number =>
  (role * 2 + channel) * 16 + hidden

const pairIndex = (
  role: number,
  sourceRole: number,
  channel: number,
  hidden: number
): number => ((role * 3 + sourceRole) * 2 + channel) * 16 + hidden

const hashInput = (
  hyperedgeId: string,
  recipients: ReadonlyArray<RecipientAddress>,
  values: Float64Array
): Either.Either<string, SWM0RoleAwareT16Error> => {
  const digest = createHash("sha256")
  digest.update(INPUT_HASH_DOMAIN)
  updateSegment(digest, new TextEncoder().encode(hyperedgeId))
  for (let index = 0; index < recipients.length; index += 1) {
    const recipient = itemAt(recipients, index)
    const metadata = canonicalS2SControlJson({
      incidence_id: recipient.incidenceId,
      member_slot: recipient.memberSlot,
      node_id: recipient.nodeId,
      role: recipient.role
    })
    if (Either.isLeft(metadata)) {
      return Either.left(
        failure(
          "CANONICAL_HASH_FAILED",
          "INPUT",
          "recipient address was not canonical"
        )
      )
    }
    updateSegment(digest, new TextEncoder().encode(metadata.right))
    const role = Math.floor(index / 2)
    const member = index % 2
    const activation = new Float64Array(4)
    for (let channel = 0; channel < 4; channel += 1) {
      activation[channel] = numberAt(
        values,
        inputIndex(role, member, channel)
      )
    }
    updateSegment(digest, float64Bytes(activation))
  }
  return Either.right(digest.digest("hex"))
}

const compileInput = (
  input: unknown
): Either.Either<CompiledInput, SWM0RoleAwareT16Error> => {
  if (!hasPlainDataSurface(input)) {
    return Either.left(
      failure(
        "INPUT_SURFACE_INVALID",
        "INPUT",
        "input must be bounded dense plain data without proxies or accessors"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(SWM0RoleAwareT16InputSchema, {
    onExcessProperty: "error"
  })(input)
  if (Either.isLeft(decoded)) {
    return Either.left(
      failure(
        "INPUT_SCHEMA_INVALID",
        "INPUT",
        "input failed the strict Effect Schema boundary"
      )
    )
  }
  const document: SWM0RoleAwareT16InputDocument = decoded.right
  const slots: Array<(typeof document.incidences)[number] | undefined> =
    Array.from({ length: 6 }, () => undefined)
  const incidenceIds = new Set<string>()
  const nodeIds = new Set<string>()
  for (const incidence of document.incidences) {
    const index = roleIndex(incidence.role) * 2 + incidence.member_slot
    if (
      slots[index] !== undefined ||
      incidenceIds.has(incidence.incidence_id) ||
      nodeIds.has(incidence.node_id)
    ) {
      return Either.left(
        failure(
          "INPUT_ADDRESS_CONFLICT",
          "INPUT",
          "role/member, incidence, and node addresses must all be unique"
        )
      )
    }
    slots[index] = incidence
    incidenceIds.add(incidence.incidence_id)
    nodeIds.add(incidence.node_id)
  }

  const values = new Float64Array(24)
  const recipients: Array<RecipientAddress> = []
  for (let index = 0; index < slots.length; index += 1) {
    const incidence = slots[index]
    if (incidence === undefined) {
      return Either.left(
        failure(
          "INPUT_LAYOUT_INCOMPLETE",
          "INPUT",
          "every fixed role/member slot must occur exactly once"
        )
      )
    }
    const role = Math.floor(index / 2)
    const member = index % 2
    for (let channel = 0; channel < 4; channel += 1) {
      const activation = incidence.activation[channel]
      if (activation === undefined) {
        return Either.left(
          failure(
            "INPUT_LAYOUT_INCOMPLETE",
            "INPUT",
            "every incidence requires four activation channels"
          )
        )
      }
      values[inputIndex(role, member, channel)] = activation
    }
    recipients.push(
      Object.freeze({
        incidenceId: incidence.incidence_id,
        memberSlot: incidence.member_slot,
        nodeId: incidence.node_id,
        role: incidence.role
      })
    )
  }
  const frozenRecipients = Object.freeze(recipients)
  const inputHash = hashInput(document.hyperedge_id, frozenRecipients, values)
  if (Either.isLeft(inputHash)) return Either.left(inputHash.left)
  return Either.right(
    Object.freeze({
      hyperedgeId: document.hyperedge_id,
      values,
      recipients: frozenRecipients,
      inputSha256: inputHash.right
    })
  )
}

const sourceValue = (
  encoded: Float64Array,
  roleSums: Float64Array,
  recipientRole: number,
  recipientMember: number,
  sourceRole: number,
  hidden: number
): number =>
  sourceRole === recipientRole
    ? numberAt(
        encoded,
        hiddenIndex(recipientRole, 1 - recipientMember, hidden)
      )
    : numberAt(roleSums, roleHiddenIndex(sourceRole, hidden))

/** Pure, bounded, one-sweep T16 arithmetic center. */
const forwardOneSweep = (
  parameters: ParameterSnapshot,
  presweep: Float64Array
): Either.Either<Float64Array, SWM0RoleAwareT16Error> => {
  const u = new Float64Array(96)
  const encoded = new Float64Array(96)
  const roleSums = new Float64Array(48)
  for (let role = 0; role < 3; role += 1) {
    for (let member = 0; member < 2; member += 1) {
      for (let hidden = 0; hidden < 16; hidden += 1) {
        let uSum = 0.0
        let encodedSum = 0.0
        for (let channel = 0; channel < 4; channel += 1) {
          const activation = numberAt(
            presweep,
            inputIndex(role, member, channel)
          )
          uSum +=
            activation *
            numberAt(parameters.phiW.values, phiIndex(role, channel, hidden))
          encodedSum +=
            activation *
            numberAt(parameters.psiW.values, phiIndex(role, channel, hidden))
        }
        u[hiddenIndex(role, member, hidden)] = uSum
        encoded[hiddenIndex(role, member, hidden)] = encodedSum
      }
    }
    for (let hidden = 0; hidden < 16; hidden += 1) {
      let sum = 0.0
      sum += numberAt(encoded, hiddenIndex(role, 0, hidden))
      sum += numberAt(encoded, hiddenIndex(role, 1, hidden))
      roleSums[roleHiddenIndex(role, hidden)] = sum
    }
  }

  const output = new Float64Array(12)
  for (let role = 0; role < 3; role += 1) {
    for (let member = 0; member < 2; member += 1) {
      for (let channel = 0; channel < 2; channel += 1) {
        let unary = 0.0
        for (let hidden = 0; hidden < 16; hidden += 1) {
          unary +=
            numberAt(u, hiddenIndex(role, member, hidden)) *
            numberAt(parameters.unaryW.values, headIndex(role, channel, hidden))
        }

        let pair = 0.0
        for (let sourceRole = 0; sourceRole < 3; sourceRole += 1) {
          for (let hidden = 0; hidden < 16; hidden += 1) {
            const pairFeature =
              numberAt(u, hiddenIndex(role, member, hidden)) *
              sourceValue(
                encoded,
                roleSums,
                role,
                member,
                sourceRole,
                hidden
              )
            pair +=
              pairFeature *
              numberAt(
                parameters.pairW.values,
                pairIndex(role, sourceRole, channel, hidden)
              )
          }
        }

        let q = 0.0
        for (let hidden = 0; hidden < 16; hidden += 1) {
          let product = 1.0
          for (let sourceRole = 0; sourceRole < 3; sourceRole += 1) {
            product *= sourceValue(
              encoded,
              roleSums,
              role,
              member,
              sourceRole,
              hidden
            )
          }
          const qFeature =
            numberAt(u, hiddenIndex(role, member, hidden)) * product
          q +=
            qFeature *
            numberAt(parameters.qW.values, headIndex(role, channel, hidden))
        }

        let prediction = unary
        prediction += pair
        prediction += q
        prediction += numberAt(parameters.outB.values, role * 2 + channel)
        if (!Number.isFinite(prediction)) {
          return Either.left(
            failure(
              "RESULT_NON_FINITE",
              "EVALUATE",
              "finite inputs and parameters overflowed during one sweep"
            )
          )
        }
        output[outputIndex(role, member, channel)] = prediction
      }
    }
  }
  return Either.right(output)
}

const hashRecipientOutput = (
  input: CompiledInput,
  output: Float64Array
): Either.Either<string, SWM0RoleAwareT16Error> => {
  const digest = createHash("sha256")
  digest.update(OUTPUT_HASH_DOMAIN)
  updateSegment(digest, new TextEncoder().encode(input.hyperedgeId))
  for (let index = 0; index < input.recipients.length; index += 1) {
    const recipient = itemAt(input.recipients, index)
    const metadata = canonicalS2SControlJson({
      incidence_id: recipient.incidenceId,
      member_slot: recipient.memberSlot,
      node_id: recipient.nodeId,
      role: recipient.role
    })
    if (Either.isLeft(metadata)) {
      return Either.left(
        failure(
          "CANONICAL_HASH_FAILED",
          "EVALUATE",
          "recipient output address was not canonical"
        )
      )
    }
    updateSegment(digest, new TextEncoder().encode(metadata.right))
    const role = Math.floor(index / 2)
    const member = index % 2
    const activation = new Float64Array([
      numberAt(output, outputIndex(role, member, 0)),
      numberAt(output, outputIndex(role, member, 1))
    ])
    updateSegment(digest, float64Bytes(activation))
  }
  return Either.right(digest.digest("hex"))
}

const makeResult = (
  operator: SWM0RoleAwareT16Operator,
  input: CompiledInput,
  output: Float64Array,
  variant: SWM0ResultVariant,
  roleCycle: readonly [number, number, number] | null,
  operatorSweepsExecuted: 0 | 1,
  sourceRecipientOutputSha256: string | null
): Either.Either<SWM0RoleAwareT16Result, SWM0RoleAwareT16Error> => {
  const outputHash = hashRecipientOutput(input, output)
  if (Either.isLeft(outputHash)) return Either.left(outputHash.left)
  const recipients: Array<SWM0RoleAwareT16RecipientActivation> = []
  const receiptAddresses: Array<{
    readonly incidence_id: string
    readonly member_slot: SWM0MemberSlot
    readonly node_id: string
    readonly role: SWM0Role
  }> = []
  for (let index = 0; index < input.recipients.length; index += 1) {
    const address = itemAt(input.recipients, index)
    const role = Math.floor(index / 2)
    const member = index % 2
    const activation = Object.freeze([
      numberAt(output, outputIndex(role, member, 0)),
      numberAt(output, outputIndex(role, member, 1))
    ] as [number, number])
    recipients.push(
      Object.freeze({
        incidenceId: address.incidenceId,
        memberSlot: address.memberSlot,
        nodeId: address.nodeId,
        role: address.role,
        activation
      })
    )
    receiptAddresses.push(
      Object.freeze({
        incidence_id: address.incidenceId,
        member_slot: address.memberSlot,
        node_id: address.nodeId,
        role: address.role
      })
    )
  }
  const frozenRecipients = Object.freeze(recipients)
  const unsigned = {
    schema_version: SWM0_ROLE_AWARE_T16_RESULT_SCHEMA_VERSION,
    classification: "ENGINEERING_ONE_SWEEP_RESULT_NON_AUTHORIZING",
    claim_boundary: SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
    hyperedge_id: input.hyperedgeId,
    variant,
    intervention: operator.intervention,
    role_cycle: roleCycle,
    operator_sweeps_executed: operatorSweepsExecuted,
    source_recipient_output_sha256: sourceRecipientOutputSha256,
    recipient_count: 6,
    channel_count: 2,
    input_sha256: input.inputSha256,
    parameters_sha256: operator.parametersSha256,
    numeric_core_state_sha256: operator.numericCoreStateSha256,
    operator_binding_sha256: operator.operatorBindingSha256,
    archive_receipt_sha256: operator.archiveReceiptSha256,
    source_archive_receipt_sha256: operator.sourceArchiveReceiptSha256,
    source_learned_state_sha256: operator.sourceLearnedStateSha256,
    structural_task_sha256: operator.structuralTaskSha256,
    recipient_output_sha256: outputHash.right,
    recipient_addresses: receiptAddresses,
    authority_scope: "NON_AUTHORIZING_ENGINEERING_RECEIPT",
    authorization_claimed: false,
    scientific_pass_claimed: false,
    typescript_training_claimed: false,
    causal_update_claimed: false
  }
  const receipt = canonicalHash(unsigned, "EVALUATE")
  if (Either.isLeft(receipt)) return Either.left(receipt.left)
  const result: SWM0RoleAwareT16Result = Object.freeze({
    schemaVersion: SWM0_ROLE_AWARE_T16_RESULT_SCHEMA_VERSION,
    classification: "ENGINEERING_ONE_SWEEP_RESULT_NON_AUTHORIZING",
    claimBoundary: SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY,
    hyperedgeId: input.hyperedgeId,
    variant,
    intervention: operator.intervention,
    roleCycle,
    operatorSweepsExecuted,
    sourceRecipientOutputSha256,
    recipientCount: 6,
    channelCount: 2,
    inputSha256: input.inputSha256,
    parametersSha256: operator.parametersSha256,
    numericCoreStateSha256: operator.numericCoreStateSha256,
    operatorBindingSha256: operator.operatorBindingSha256,
    archiveReceiptSha256: operator.archiveReceiptSha256,
    sourceArchiveReceiptSha256: operator.sourceArchiveReceiptSha256,
    sourceLearnedStateSha256: operator.sourceLearnedStateSha256,
    structuralTaskSha256: operator.structuralTaskSha256,
    recipientOutputSha256: outputHash.right,
    recipients: frozenRecipients,
    authorizationClaimed: false,
    scientificPassClaimed: false,
    typescriptTrainingClaimed: false,
    causalUpdateClaimed: false,
    receiptSha256: receipt.right
  })
  RESULTS.set(
    result,
    Object.freeze({ operator, input, output, variant, roleCycle })
  )
  return Either.right(result)
}

export const evaluateSWM0RoleAwareT16 = (
  operator: SWM0RoleAwareT16Operator,
  input: unknown
): Either.Either<SWM0RoleAwareT16Result, SWM0RoleAwareT16Error> => {
  const snapshot = OPERATORS.get(operator)
  if (snapshot === undefined) {
    return Either.left(
      failure(
        "OPERATOR_NOT_AUTHENTIC",
        "EVALUATE",
        "operator is not a module-issued immutable handle"
      )
    )
  }
  const compiled = compileInput(input)
  if (Either.isLeft(compiled)) return Either.left(compiled.left)
  const output = forwardOneSweep(snapshot.parameters, compiled.right.values)
  if (Either.isLeft(output)) return Either.left(output.left)
  return makeResult(
    operator,
    compiled.right,
    output.right,
    operator.intervention === "NONE" ? "BASE" : "Q_REMOVED",
    null,
    1,
    null
  )
}

const qReceiptUnsigned = (
  receipt: Omit<SWM0RoleAwareT16QRemovalReceipt, "receipt_sha256">
): unknown => ({
  schema_version: receipt.schema_version,
  classification: receipt.classification,
  intervention: receipt.intervention,
  archive_receipt_sha256: receipt.archive_receipt_sha256,
  base_core_state_sha256: receipt.base_core_state_sha256,
  base_operator_binding_sha256: receipt.base_operator_binding_sha256,
  base_parameters_sha256: receipt.base_parameters_sha256,
  ablated_core_state_sha256: receipt.ablated_core_state_sha256,
  ablated_operator_binding_sha256: receipt.ablated_operator_binding_sha256,
  ablated_parameters_sha256: receipt.ablated_parameters_sha256,
  removed_q_byte_length: receipt.removed_q_byte_length,
  removed_q_value_count: receipt.removed_q_value_count,
  removed_q_bytes_base64: receipt.removed_q_bytes_base64,
  removed_q_bytes_sha256: receipt.removed_q_bytes_sha256
})

const qTensorFromBytes = (
  bytes: Uint8Array,
  bytesSha256: string
): Either.Either<TensorSnapshot, SWM0RoleAwareT16Error> =>
  decodeTensor(
    {
      name: "q_w",
      shape: [3, 2, 16],
      byte_length: 768,
      bytes_base64: Encoding.encodeBase64(bytes),
      bytes_sha256: bytesSha256
    },
    "Q"
  )

export const removeSWM0RoleAwareT16Q = (
  operator: SWM0RoleAwareT16Operator
): Either.Either<SWM0RoleAwareT16QRemoval, SWM0RoleAwareT16Error> => {
  const snapshot = OPERATORS.get(operator)
  if (snapshot === undefined) {
    return Either.left(
      failure(
        "OPERATOR_NOT_AUTHENTIC",
        "Q",
        "Q removal requires a module-issued operator"
      )
    )
  }
  if (operator.intervention !== "NONE") {
    return Either.left(
      failure(
        "INTERVENTION_NOT_ALLOWED",
        "Q",
        "Q removal accepts only an unintervened T16 operator"
      )
    )
  }
  const zeroBytes = new Uint8Array(768)
  const zeroQ = qTensorFromBytes(zeroBytes, rawS2SFileSha256(zeroBytes))
  if (Either.isLeft(zeroQ)) return Either.left(zeroQ.left)
  const parameters: ParameterSnapshot = Object.freeze({
    ...snapshot.parameters,
    qW: zeroQ.right
  })
  const ablated = makeOperator(
    parameters,
    snapshot.source,
    snapshot.archiveReceiptSha256,
    "Q_REMOVED",
    Object.freeze({
      qW: snapshot.parameters.qW,
      baseParametersSha256: operator.parametersSha256,
      baseCoreStateSha256: operator.numericCoreStateSha256,
      baseOperatorBindingSha256: operator.operatorBindingSha256,
      removedQBytesSha256: rawS2SFileSha256(snapshot.parameters.qW.bytes)
    })
  )
  if (Either.isLeft(ablated)) return Either.left(ablated.left)
  const unsigned = {
    schema_version: SWM0_ROLE_AWARE_T16_Q_REMOVAL_SCHEMA_VERSION,
    classification: "ENGINEERING_INTERVENTION_NON_AUTHORIZING" as const,
    intervention: "FROZEN_Q_REMOVE_EXACT_BYTES_RESTORE" as const,
    archive_receipt_sha256: snapshot.archiveReceiptSha256,
    base_core_state_sha256: operator.numericCoreStateSha256,
    base_operator_binding_sha256: operator.operatorBindingSha256,
    base_parameters_sha256: operator.parametersSha256,
    ablated_core_state_sha256: ablated.right.numericCoreStateSha256,
    ablated_operator_binding_sha256: ablated.right.operatorBindingSha256,
    ablated_parameters_sha256: ablated.right.parametersSha256,
    removed_q_byte_length: 768 as const,
    removed_q_value_count: 96 as const,
    removed_q_bytes_base64: Encoding.encodeBase64(snapshot.parameters.qW.bytes),
    removed_q_bytes_sha256: rawS2SFileSha256(snapshot.parameters.qW.bytes)
  }
  const receiptHash = canonicalHash(unsigned, "Q")
  if (Either.isLeft(receiptHash)) return Either.left(receiptHash.left)
  const receipt: SWM0RoleAwareT16QRemovalReceipt = Object.freeze({
    ...unsigned,
    receipt_sha256: receiptHash.right
  })
  return Either.right(
    Object.freeze({ operator: ablated.right, receipt })
  )
}

export const restoreSWM0RoleAwareT16Q = (
  operator: SWM0RoleAwareT16Operator,
  receiptInput: unknown
): Either.Either<SWM0RoleAwareT16Operator, SWM0RoleAwareT16Error> => {
  const snapshot = OPERATORS.get(operator)
  if (snapshot === undefined) {
    return Either.left(
      failure(
        "OPERATOR_NOT_AUTHENTIC",
        "Q",
        "Q restoration requires a module-issued operator"
      )
    )
  }
  if (!hasPlainDataSurface(receiptInput)) {
    return Either.left(
      failure(
        "Q_RECEIPT_SURFACE_INVALID",
        "Q",
        "Q receipt must be bounded dense plain data without proxies or accessors"
      )
    )
  }
  const decoded = Schema.decodeUnknownEither(
    SWM0RoleAwareT16QRemovalReceiptSchema,
    { onExcessProperty: "error" }
  )(receiptInput)
  if (Either.isLeft(decoded)) {
    return Either.left(
      failure(
        "Q_RECEIPT_SCHEMA_INVALID",
        "Q",
        "Q receipt failed the strict Effect Schema boundary"
      )
    )
  }
  const receipt = decoded.right
  const restoration = snapshot.qRestoration
  const expectedReceipt = canonicalHash(
    qReceiptUnsigned(receipt),
    "Q"
  )
  if (
    Either.isLeft(expectedReceipt) ||
    expectedReceipt.right !== receipt.receipt_sha256 ||
    restoration === null ||
    operator.intervention !== "Q_REMOVED" ||
    operator.archiveReceiptSha256 !== receipt.archive_receipt_sha256 ||
    operator.numericCoreStateSha256 !== receipt.ablated_core_state_sha256 ||
    operator.operatorBindingSha256 !==
      receipt.ablated_operator_binding_sha256 ||
    operator.parametersSha256 !== receipt.ablated_parameters_sha256 ||
    receipt.base_parameters_sha256 !==
      restoration?.baseParametersSha256 ||
    receipt.base_core_state_sha256 !== restoration?.baseCoreStateSha256 ||
    receipt.base_operator_binding_sha256 !==
      restoration?.baseOperatorBindingSha256 ||
    receipt.removed_q_bytes_sha256 !== restoration?.removedQBytesSha256 ||
    snapshot.parameters.qW.bytes.some((byte) => byte !== 0)
  ) {
    return Either.left(
      failure(
        "Q_RECEIPT_MISMATCH",
        "Q",
        "Q receipt does not bind this exact positive-zero ablation"
      )
    )
  }
  const restoredBytes = Encoding.decodeBase64(receipt.removed_q_bytes_base64)
  if (Either.isLeft(restoredBytes)) {
    return Either.left(
      failure(
        "Q_RECEIPT_MISMATCH",
        "Q",
        "removed Q bytes are not valid base64"
      )
    )
  }
  const qBytes = new Uint8Array(restoredBytes.right)
  if (
    Encoding.encodeBase64(qBytes) !== receipt.removed_q_bytes_base64 ||
    qBytes.byteLength !== 768 ||
    rawS2SFileSha256(qBytes) !== receipt.removed_q_bytes_sha256 ||
    restoration === null ||
    qBytes.some((byte, index) => byte !== restoration.qW.bytes[index])
  ) {
    return Either.left(
      failure(
        "Q_RECEIPT_MISMATCH",
        "Q",
        "removed Q byte commitment is malformed"
      )
    )
  }
  const parameters: ParameterSnapshot = Object.freeze({
    ...snapshot.parameters,
    qW: restoration.qW
  })
  const restored = makeOperator(
    parameters,
    snapshot.source,
    snapshot.archiveReceiptSha256,
    "NONE"
  )
  if (Either.isLeft(restored)) return restored
  if (
    restored.right.numericCoreStateSha256 !== receipt.base_core_state_sha256 ||
    restored.right.operatorBindingSha256 !==
      receipt.base_operator_binding_sha256 ||
    restored.right.parametersSha256 !== receipt.base_parameters_sha256 ||
    restored.right.numericCoreStateSha256 !==
      restoration.baseCoreStateSha256 ||
    restored.right.operatorBindingSha256 !==
      restoration.baseOperatorBindingSha256 ||
    restored.right.parametersSha256 !== restoration.baseParametersSha256
  ) {
    return Either.left(
      failure(
        "Q_RECEIPT_MISMATCH",
        "Q",
        "restored Q bytes do not recover the bound base operator"
      )
    )
  }
  return restored
}

export const broadcastSWM0RoleAwareT16Result = (
  result: SWM0RoleAwareT16Result
): Either.Either<SWM0RoleAwareT16Result, SWM0RoleAwareT16Error> => {
  const snapshot = RESULTS.get(result)
  if (snapshot === undefined) {
    return Either.left(
      failure(
        "RESULT_NOT_AUTHENTIC",
        "CONTROL",
        "broadcast requires a module-issued frozen result"
      )
    )
  }
  if (snapshot.variant !== "BASE" || snapshot.operator.intervention !== "NONE") {
    return Either.left(
      failure(
        "INTERVENTION_NOT_ALLOWED",
        "CONTROL",
        "broadcast accepts only a frozen unintervened baseline"
      )
    )
  }
  const broadcast = new Float64Array(12)
  for (let role = 0; role < 3; role += 1) {
    for (let channel = 0; channel < 2; channel += 1) {
      const pooled =
        0.5 * numberAt(snapshot.output, outputIndex(role, 0, channel)) +
        0.5 * numberAt(snapshot.output, outputIndex(role, 1, channel))
      if (!Number.isFinite(pooled)) {
        return Either.left(
          failure(
            "RESULT_NON_FINITE",
            "CONTROL",
            "broadcast produced a non-finite activation"
          )
        )
      }
      broadcast[outputIndex(role, 0, channel)] = pooled
      broadcast[outputIndex(role, 1, channel)] = pooled
    }
  }
  return makeResult(
    snapshot.operator,
    snapshot.input,
    broadcast,
    "WITHIN_ROLE_BROADCAST",
    null,
    0,
    result.recipientOutputSha256
  )
}

const cycleInput = (
  values: Float64Array,
  cycle: readonly [number, number, number]
): Float64Array => {
  const moved = new Float64Array(24)
  for (let sourceRole = 0; sourceRole < 3; sourceRole += 1) {
    const destinationRole = itemAt(cycle, sourceRole)
    for (let member = 0; member < 2; member += 1) {
      for (let channel = 0; channel < 4; channel += 1) {
        moved[inputIndex(destinationRole, member, channel)] = numberAt(
          values,
          inputIndex(sourceRole, member, channel)
        )
      }
    }
  }
  return moved
}

const inverseCycleOutput = (
  values: Float64Array,
  cycle: readonly [number, number, number]
): Float64Array => {
  const restored = new Float64Array(12)
  for (let sourceRole = 0; sourceRole < 3; sourceRole += 1) {
    const destinationRole = itemAt(cycle, sourceRole)
    for (let member = 0; member < 2; member += 1) {
      for (let channel = 0; channel < 2; channel += 1) {
        restored[outputIndex(sourceRole, member, channel)] = numberAt(
          values,
          outputIndex(destinationRole, member, channel)
        )
      }
    }
  }
  return restored
}

export const evaluateSWM0RoleAwareT16RoleCycles = (
  operator: SWM0RoleAwareT16Operator,
  input: unknown
): Either.Either<
  ReadonlyArray<SWM0RoleAwareT16RoleCycleResult>,
  SWM0RoleAwareT16Error
> => {
  const snapshot = OPERATORS.get(operator)
  if (snapshot === undefined) {
    return Either.left(
      failure(
        "OPERATOR_NOT_AUTHENTIC",
        "CONTROL",
        "role-cycle control requires a module-issued operator"
      )
    )
  }
  if (operator.intervention !== "NONE") {
    return Either.left(
      failure(
        "INTERVENTION_NOT_ALLOWED",
        "CONTROL",
        "role-cycle control accepts only an unintervened operator"
      )
    )
  }
  const compiled = compileInput(input)
  if (Either.isLeft(compiled)) return Either.left(compiled.left)
  const results: Array<SWM0RoleAwareT16RoleCycleResult> = []
  for (const cycle of SWM0_ROLE_AWARE_T16_ROLE_CYCLES) {
    const moved = cycleInput(compiled.right.values, cycle)
    const evaluated = forwardOneSweep(snapshot.parameters, moved)
    if (Either.isLeft(evaluated)) return Either.left(evaluated.left)
    const restored = inverseCycleOutput(evaluated.right, cycle)
    const variant = cycle === ROLE_CYCLE_120
      ? "ROLE_CYCLE_120"
      : "ROLE_CYCLE_201"
    const result = makeResult(
      operator,
      compiled.right,
      restored,
      variant,
      cycle,
      1,
      null
    )
    if (Either.isLeft(result)) return Either.left(result.left)
    results.push(Object.freeze({ cycle, result: result.right }))
  }
  return Either.right(Object.freeze(results))
}
