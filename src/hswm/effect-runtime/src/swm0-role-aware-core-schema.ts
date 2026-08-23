import { Schema } from "effect"

export const SWM0_ROLE_AWARE_T16_ARCHIVE_SCHEMA_VERSION =
  "hswm-swm0-role-aware-t16-parameter-archive/v1" as const
export const SWM0_ROLE_AWARE_T16_TENSOR_SCHEMA_VERSION =
  "hswm-swm0-role-aware-t16-parameter-tensor/v1" as const
export const SWM0_ROLE_AWARE_T16_INPUT_SCHEMA_VERSION =
  "hswm-swm0-role-aware-t16-input/v1" as const
export const SWM0_ROLE_AWARE_T16_Q_REMOVAL_SCHEMA_VERSION =
  "hswm-swm0-role-aware-t16-q-removal/v1" as const
export const SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION =
  "ENGINEERING_CORE_PARAMETER_ARCHIVE_NON_AUTHORIZING" as const
export const SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY =
  "NUMERIC_PARAMETER_PROJECTION_ONLY_NO_TRAINING_OR_EFFICACY_AUTHORIZATION" as const

const IdentifierSchema = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)

const Sha256Schema = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}$/)
)

const canonicalBase64Schema = (encodedLength: number) =>
  Schema.String.pipe(
    Schema.length(encodedLength),
    Schema.pattern(
      /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/
    )
  )

const FiniteNumberSchema = Schema.Number.pipe(Schema.finite())

const ActivationSchema = Schema.Tuple(
  FiniteNumberSchema,
  FiniteNumberSchema,
  FiniteNumberSchema,
  FiniteNumberSchema
)

export const SWM0RoleAwareT16IncidenceSchema = Schema.Struct({
  incidence_id: IdentifierSchema,
  member_slot: Schema.Literal(0, 1),
  node_id: IdentifierSchema,
  role: Schema.Literal("r0", "r1", "r2"),
  activation: ActivationSchema
})

export const SWM0RoleAwareT16InputSchema = Schema.Struct({
  schema_version: Schema.Literal(SWM0_ROLE_AWARE_T16_INPUT_SCHEMA_VERSION),
  hyperedge_id: IdentifierSchema,
  incidences: Schema.Array(SWM0RoleAwareT16IncidenceSchema).pipe(
    Schema.minItems(6),
    Schema.maxItems(6)
  )
})

const parameterTensorBase = (encodedLength: number) => ({
  schema_version: Schema.Literal(
    SWM0_ROLE_AWARE_T16_TENSOR_SCHEMA_VERSION
  ),
  dtype: Schema.Literal("float64-le"),
  bytes_base64: canonicalBase64Schema(encodedLength),
  bytes_sha256: Sha256Schema
})

const PhiTensorSchema = Schema.Struct({
  ...parameterTensorBase(2_048),
  name: Schema.Literal("phi_w"),
  shape: Schema.Tuple(
    Schema.Literal(3),
    Schema.Literal(4),
    Schema.Literal(16)
  ),
  byte_length: Schema.Literal(1_536)
})

const PsiTensorSchema = Schema.Struct({
  ...parameterTensorBase(2_048),
  name: Schema.Literal("psi_w"),
  shape: Schema.Tuple(
    Schema.Literal(3),
    Schema.Literal(4),
    Schema.Literal(16)
  ),
  byte_length: Schema.Literal(1_536)
})

const UnaryTensorSchema = Schema.Struct({
  ...parameterTensorBase(1_024),
  name: Schema.Literal("unary_w"),
  shape: Schema.Tuple(
    Schema.Literal(3),
    Schema.Literal(2),
    Schema.Literal(16)
  ),
  byte_length: Schema.Literal(768)
})

const PairTensorSchema = Schema.Struct({
  ...parameterTensorBase(3_072),
  name: Schema.Literal("pair_w"),
  shape: Schema.Tuple(
    Schema.Literal(3),
    Schema.Literal(3),
    Schema.Literal(2),
    Schema.Literal(16)
  ),
  byte_length: Schema.Literal(2_304)
})

const QTensorSchema = Schema.Struct({
  ...parameterTensorBase(1_024),
  name: Schema.Literal("q_w"),
  shape: Schema.Tuple(
    Schema.Literal(3),
    Schema.Literal(2),
    Schema.Literal(16)
  ),
  byte_length: Schema.Literal(768)
})

const OutputBiasTensorSchema = Schema.Struct({
  ...parameterTensorBase(64),
  name: Schema.Literal("out_b"),
  shape: Schema.Tuple(Schema.Literal(3), Schema.Literal(2)),
  byte_length: Schema.Literal(48)
})

const SourceProjectionSchema = Schema.Struct({
  kind: Schema.Literal("PYTHON_LEARNED_MODEL_ARCHIVE_PROJECTION"),
  source_archive_schema_version: Schema.Literal(
    "hswm-swm0w-s2s-learned-archive/v1"
  ),
  source_archive_receipt_sha256: Sha256Schema,
  learned_state_sha256: Sha256Schema,
  structural_task_sha256: Sha256Schema,
  fitted: Schema.Literal(true),
  learned: Schema.Literal(true),
  assurance: Schema.Literal(
    "SOURCE_ARCHIVE_RECEIPT_PIN_ONLY_NOT_REVALIDATED_BY_TYPESCRIPT"
  )
})

/**
 * Float values are carried only as canonical little-endian byte strings. The
 * fixed tuple order is an archive rule; tensor lookup never depends on a
 * caller-controlled object enumeration order.
 */
export const SWM0RoleAwareT16ParameterArchiveSchema = Schema.Struct({
  schema_version: Schema.Literal(
    SWM0_ROLE_AWARE_T16_ARCHIVE_SCHEMA_VERSION
  ),
  classification: Schema.Literal(
    SWM0_ROLE_AWARE_T16_ARCHIVE_CLASSIFICATION
  ),
  claim_boundary: Schema.Literal(SWM0_ROLE_AWARE_T16_CLAIM_BOUNDARY),
  arm: Schema.Literal("T16"),
  roles: Schema.Tuple(
    Schema.Literal("r0"),
    Schema.Literal("r1"),
    Schema.Literal("r2")
  ),
  parameter_count: Schema.Literal(870),
  parameters_sha256: Sha256Schema,
  source: SourceProjectionSchema,
  tensors: Schema.Tuple(
    PhiTensorSchema,
    PsiTensorSchema,
    UnaryTensorSchema,
    PairTensorSchema,
    QTensorSchema,
    OutputBiasTensorSchema
  ),
  receipt_sha256: Sha256Schema
})

export const SWM0RoleAwareT16QRemovalReceiptSchema = Schema.Struct({
  schema_version: Schema.Literal(
    SWM0_ROLE_AWARE_T16_Q_REMOVAL_SCHEMA_VERSION
  ),
  classification: Schema.Literal("ENGINEERING_INTERVENTION_NON_AUTHORIZING"),
  intervention: Schema.Literal("FROZEN_Q_REMOVE_EXACT_BYTES_RESTORE"),
  archive_receipt_sha256: Sha256Schema,
  base_core_state_sha256: Sha256Schema,
  base_operator_binding_sha256: Sha256Schema,
  base_parameters_sha256: Sha256Schema,
  ablated_core_state_sha256: Sha256Schema,
  ablated_operator_binding_sha256: Sha256Schema,
  ablated_parameters_sha256: Sha256Schema,
  removed_q_byte_length: Schema.Literal(768),
  removed_q_value_count: Schema.Literal(96),
  removed_q_bytes_base64: canonicalBase64Schema(1_024),
  removed_q_bytes_sha256: Sha256Schema,
  receipt_sha256: Sha256Schema
})

export type SWM0RoleAwareT16IncidenceDocument = Schema.Schema.Type<
  typeof SWM0RoleAwareT16IncidenceSchema
>
export type SWM0RoleAwareT16InputDocument = Schema.Schema.Type<
  typeof SWM0RoleAwareT16InputSchema
>
export type SWM0RoleAwareT16ParameterArchiveDocument = Schema.Schema.Type<
  typeof SWM0RoleAwareT16ParameterArchiveSchema
>
export type SWM0RoleAwareT16QRemovalReceipt = Schema.Schema.Type<
  typeof SWM0RoleAwareT16QRemovalReceiptSchema
>
