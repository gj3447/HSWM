import { Schema } from "effect"

export const HSWM_CORE_RESPONSIBILITY_ONTOLOGY_SCHEMA_VERSION =
  "hswm-core-responsibility-ontology/v1" as const

const Text = Schema.String.pipe(
  Schema.minLength(1),
  Schema.maxLength(8_192)
)

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)

const SafePath = Schema.String.pipe(
  Schema.maxLength(512),
  Schema.pattern(/^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9._/-]+$/)
)

const Sha256 = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}$/)
)

const RelationType = Schema.String.pipe(
  Schema.pattern(/^[A-Z][A-Z0-9_]*$/)
)

const NonEmptyTextArray = Schema.Array(Text).pipe(
  Schema.minItems(1),
  Schema.maxItems(64)
)

const IdentifierArray = Schema.Array(Identifier).pipe(
  Schema.minItems(1),
  Schema.maxItems(64)
)

const IdentifierList = Schema.Array(Identifier).pipe(
  Schema.maxItems(64)
)

const ScopeSchema = Schema.Struct({
  includes: NonEmptyTextArray,
  excludes: NonEmptyTextArray,
  admission_boundary: Text
})

const NormalFormContractSchema = Schema.Struct({
  name: Text,
  status: Schema.Literal("ENGINEERING_TARGET_NOT_UNIVERSAL_ONTOLOGY_PROOF"),
  role_uids: IdentifierArray.pipe(Schema.minItems(5), Schema.maxItems(5)),
  owner_law: Text,
  state_form: Text,
  raw_boundary: Text,
  presentation_uniqueness: Text,
  continuous_uniqueness: Text,
  schema_evolution: Text
})

export const HSWMCoreRoleSchema = Schema.Struct({
  uid: Identifier,
  symbol: Schema.Literal("H", "W", "A", "F", "Pi"),
  name: Text,
  canonical_meaning: Text,
  owns: NonEmptyTextArray,
  must_not_own: NonEmptyTextArray,
  identity_status: Schema.Literal("CANONICAL_TARGET_IDENTITY"),
  responsibility_detail_status: Schema.Literal(
    "SECONDARY_AI_CONCEPTUAL_CLOSURE_CANDIDATE"
  )
})

export const HSWMCorePrimitiveKindSchema = Schema.Struct({
  uid: Identifier,
  name: Identifier,
  owner_role_uid: Identifier,
  definition: Text,
  lifecycle: Schema.String.pipe(
    Schema.pattern(/^[A-Z][A-Z0-9_]*$/),
    Schema.maxLength(128)
  )
})

const RelationTypeDefinitionSchema = Schema.Struct({
  type: RelationType,
  definition: Text
})

const RelationSchema = Schema.Struct({
  from_uid: Identifier,
  type: RelationType,
  to_uid: Identifier
})

export const HSWMCoreSeamContractSchema = Schema.Struct({
  uid: Identifier,
  left_role_uid: Identifier,
  right_role_uid: Identifier,
  name: Text,
  requirements: NonEmptyTextArray
})

export const HSWMCoreTransitionWriteContractSchema = Schema.Struct({
  target_kind_uid: Identifier,
  effect: Schema.Literal(
    "CREATE_NEW_ATOM_OR_VERSION",
    "CREATE_OR_ADVANCE_EPISODE_LOCAL",
    "SEAL_PRE_OUTCOME",
    "EXPIRE_OR_CLOSE_EPISODE_LOCAL",
    "CREATE_NEW_VERSION",
    "SUPERSEDE_WITH_NEW_VERSION",
    "CONSUME_AND_CLOSE",
    "CREATE_OR_SUPERSEDE_VERSION",
    "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE",
    "AMEND_BY_EXPLICIT_RATIFICATION",
    "RESTORE_AS_NEW_VERSION"
  )
})

export const HSWMCoreTransitionFamilySchema = Schema.Struct({
  uid: Identifier,
  name: Identifier,
  definition: Text,
  reads_role_uids: IdentifierArray,
  writes_role_uids: IdentifierArray,
  write_contracts: Schema.Array(HSWMCoreTransitionWriteContractSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(64)
  ),
  preserves_kind_uids: IdentifierList,
  effect_constraints: NonEmptyTextArray,
  authority_role_uid: Identifier,
  outcome_required: Schema.Boolean,
  requires_pre_outcome_eligibility: Schema.Boolean,
  ratification_required: Schema.Boolean
})

export const HSWMCoreProjectionClassSchema = Schema.Struct({
  uid: Identifier,
  name: Identifier,
  fidelity: Schema.Literal(
    "LOSSLESS_IF_ROUNDTRIP_VERIFIED",
    "LOSSY_DECLARED",
    "NAVIGATION_ONLY"
  ),
  direct_commit_back_allowed: Schema.Boolean,
  definition: Text
})

export const HSWMCoreInvariantSchema = Schema.Struct({
  uid: Identifier,
  code: RelationType,
  statement: Text,
  validation: Text
})

const ExternalAnchorSchema = Schema.Struct({
  uid: Identifier,
  source_bundle: SafePath,
  source_bundle_sha256: Sha256,
  expected_authority_class: Schema.Literal(
    "USER_PRIMARY",
    "SECONDARY_AI",
    "MIXED_EXPLICIT",
    "SYSTEM_DERIVED"
  ),
  expected_canonical_scope: Schema.Literal(
    "USER_RATIFIED_CANON",
    "UNSPECIFIED"
  ),
  use: Text
})

const SourceBindingSchema = Schema.Struct({
  path: SafePath,
  sha256: Sha256,
  authority_class: Schema.Literal(
    "USER_PRIMARY",
    "SECONDARY_AI",
    "MIXED_EXPLICIT",
    "SYSTEM_DERIVED"
  ),
  binding_scope: Text
})

const KGProjectionPolicySchema = Schema.Struct({
  representation: Schema.Literal(
    "LOCAL_JSON_TYPED_PROPERTY_GRAPH_ONTOLOGY"
  ),
  remote_publication: Schema.Literal("NOT_AUTHORIZED"),
  node_collections: NonEmptyTextArray,
  explicit_edge_collection: Schema.Literal("relations"),
  derived_edges: NonEmptyTextArray,
  hypergraph_encoding: Text,
  future_publisher_gate: Text
})

export const HSWMCoreResponsibilityOntologySchema = Schema.Struct({
  schema_version: Schema.Literal(
    HSWM_CORE_RESPONSIBILITY_ONTOLOGY_SCHEMA_VERSION
  ),
  status: Schema.Literal(
    "CANONICAL_TARGET_IDENTITY_PROJECTION_WITH_SECONDARY_AI_RESPONSIBILITY_NORMAL_FORM_CANDIDATE"
  ),
  created_at: Schema.String.pipe(
    Schema.pattern(/^\d{4}-\d{2}-\d{2}$/)
  ),
  bundle_uid: Identifier,
  root_uid: Identifier,
  title: Text,
  authority_boundary: Text,
  scientific_status: Schema.Literal("UNJUDGED"),
  scope: ScopeSchema,
  normal_form_contract: NormalFormContractSchema,
  roles: Schema.Array(HSWMCoreRoleSchema).pipe(
    Schema.minItems(5),
    Schema.maxItems(5)
  ),
  primitive_kinds: Schema.Array(HSWMCorePrimitiveKindSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(256)
  ),
  relation_types: Schema.Array(RelationTypeDefinitionSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(128)
  ),
  relations: Schema.Array(RelationSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(512)
  ),
  seam_contracts: Schema.Array(HSWMCoreSeamContractSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(64)
  ),
  transition_families: Schema.Array(HSWMCoreTransitionFamilySchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(64)
  ),
  projection_classes: Schema.Array(HSWMCoreProjectionClassSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(64)
  ),
  invariants: Schema.Array(HSWMCoreInvariantSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(128)
  ),
  external_anchors: Schema.Array(ExternalAnchorSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(64)
  ),
  source_bindings: Schema.Array(SourceBindingSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(64)
  ),
  kg_projection_policy: KGProjectionPolicySchema,
  nonclaims: NonEmptyTextArray
})

export type HSWMCoreResponsibilityOntology = Schema.Schema.Type<
  typeof HSWMCoreResponsibilityOntologySchema
>
