import { Data, Either, Schema } from "effect"

import {
  HSWMCoreResponsibilityOntologySchema,
  type HSWMCoreResponsibilityOntology
} from "./hswm-core-ontology-schema.js"
import { canonicalS2SControlSha256 } from "./s2s-canonical.js"
import { parseS2SJsonBytes } from "./s2s-json.js"

export type HSWMCoreOntologyErrorCode =
  | "JSON_INVALID"
  | "SCHEMA_INVALID"
  | "ROLE_SET_INVALID"
  | "UID_DUPLICATE"
  | "OWNER_INVALID"
  | "RELATION_TYPE_INVALID"
  | "RELATION_ENDPOINT_INVALID"
  | "RELATION_DUPLICATE"
  | "RELATION_SET_INVALID"
  | "SEAM_INVALID"
  | "TRANSITION_INVALID"
  | "PROJECTION_INVALID"
  | "INVARIANT_SET_INVALID"
  | "SOURCE_BINDING_INVALID"
  | "CONTENT_DIGEST_INVALID"
  | "NORMAL_FORM_INVALID"

export class HSWMCoreOntologyError extends Data.TaggedError(
  "HSWMCoreOntologyError"
)<{
  readonly code: HSWMCoreOntologyErrorCode
  readonly detail: string
}> {}

const EXPECTED_ROLES = [
  ["hswm:role:H", "H"],
  ["hswm:role:W", "W"],
  ["hswm:role:A", "A"],
  ["hswm:role:F", "F"],
  ["hswm:role:Pi", "Pi"]
] as const

const EXPECTED_BUNDLE_UID = "hswm:ontology:core-responsibility:v1" as const
const EXPECTED_ROOT_UID = "hswm:concept:core-state" as const
const EXPECTED_CANONICAL_CONTENT_SHA256 =
  "c5f11257cd6b17a6c3055dcad772ddcd41149a3779370565728e74ec7d4fc6f2" as const

const EXPECTED_INVARIANTS = [
  ["hswm:invariant:owner-total", "OWNER_TOTAL"],
  ["hswm:invariant:owner-exclusive", "OWNER_EXCLUSIVE"],
  ["hswm:invariant:reference-not-copy", "REFERENCE_NOT_COPY"],
  ["hswm:invariant:unknown-kind-quarantine", "UNKNOWN_KIND_QUARANTINE"],
  ["hswm:invariant:nary-incidence-preserved", "NARY_INCIDENCE_PRESERVED"],
  ["hswm:invariant:h-w-topology-separation", "H_W_TOPOLOGY_SEPARATION"],
  ["hswm:invariant:a-lifetime", "A_EPISODE_LIFETIME"],
  ["hswm:invariant:pi-noncompensable", "PI_DENIAL_NONCOMPENSABLE"],
  ["hswm:invariant:outcome-bound-durability", "OUTCOME_BOUND_DURABILITY"],
  ["hswm:invariant:projection-boundary", "PROJECTION_NOT_COGNITION"],
  ["hswm:invariant:u-is-morphism", "U_IS_MORPHISM_NOT_ROLE"],
  ["hswm:invariant:schema-relative-uniqueness", "SCHEMA_RELATIVE_UNIQUENESS"]
] as const

const EXPECTED_PRIMITIVE_KINDS = [
  ["hswm:kind:H:stable-entity-version", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:event-record", "hswm:role:H", "DURABLE_APPEND_OR_SUPERSEDE"],
  ["hswm:kind:H:claim-record", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:evidence-record", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:judgment-record", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:outcome-record", "hswm:role:H", "DURABLE_APPEND_OR_SUPERSEDE"],
  ["hswm:kind:H:provenance-link", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:hyperedge-version", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:incidence-version", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:H:artifact-identity", "hswm:role:H", "DURABLE_VERSIONED"],
  ["hswm:kind:W:operator-family", "hswm:role:W", "DURABLE_LEARNED_VERSIONED"],
  ["hswm:kind:W:semantic-transport-state", "hswm:role:W", "DURABLE_LEARNED_VERSIONED"],
  ["hswm:kind:W:causal-efficacy-state", "hswm:role:W", "DURABLE_LEARNED_VERSIONED"],
  ["hswm:kind:W:topology-propensity", "hswm:role:W", "DURABLE_LEARNED_VERSIONED"],
  ["hswm:kind:A:activation-packet", "hswm:role:A", "EPISODE_LOCAL"],
  ["hswm:kind:A:episode-frontier", "hswm:role:A", "EPISODE_LOCAL"],
  ["hswm:kind:A:route-decision", "hswm:role:A", "EPISODE_LOCAL"],
  ["hswm:kind:A:function-cell-invocation", "hswm:role:A", "EPISODE_LOCAL"],
  ["hswm:kind:A:eligibility-seal", "hswm:role:A", "EPISODE_LOCAL_THEN_ARCHIVABLE_AS_NEW_H_RECORD"],
  ["hswm:kind:A:compiled-active-cut", "hswm:role:A", "EPISODE_LOCAL_DERIVED"],
  ["hswm:kind:F:function-cell-definition", "hswm:role:F", "DURABLE_VERSIONED_REPLACEABLE"],
  ["hswm:kind:F:port-contract", "hswm:role:F", "DURABLE_VERSIONED_REPLACEABLE"],
  ["hswm:kind:F:semantic-parser-contract", "hswm:role:F", "DURABLE_VERSIONED_REPLACEABLE"],
  ["hswm:kind:F:function-cell-configuration", "hswm:role:F", "DURABLE_VERSIONED_REPLACEABLE"],
  ["hswm:kind:Pi:constitutional-boundary", "hswm:role:Pi", "IDENTITY_BEARING_VERSIONED"],
  ["hswm:kind:Pi:operational-policy", "hswm:role:Pi", "DURABLE_VERSIONED_REVOCABLE"],
  ["hswm:kind:Pi:authority-grant", "hswm:role:Pi", "DURABLE_VERSIONED_REVOCABLE"],
  ["hswm:kind:Pi:consent-grant", "hswm:role:Pi", "DURABLE_VERSIONED_REVOCABLE"],
  ["hswm:kind:Pi:capability-grant", "hswm:role:Pi", "DURABLE_VERSIONED_REVOCABLE"],
  ["hswm:kind:Pi:budget-lease", "hswm:role:Pi", "DURABLE_VERSIONED_EXPIRING"],
  ["hswm:kind:Pi:transaction-policy", "hswm:role:Pi", "DURABLE_VERSIONED"],
  ["hswm:kind:Pi:rollback-policy", "hswm:role:Pi", "DURABLE_VERSIONED"],
  ["hswm:kind:Pi:opaque-permit", "hswm:role:Pi", "EPHEMERAL_OR_SINGLE_USE"]
] as const

const EXPECTED_RELATION_TYPES = [
  "HAS_INCIDENCE",
  "BINDS_ENTITY",
  "REFERENCES_KIND",
  "DERIVED_FROM",
  "BINDS_OUTCOME",
  "AUTHORIZED_BY",
  "READS_ROLE",
  "WRITES_ROLE",
  "COMPILES_TO",
  "CANNOT_COMMIT_BACK_TO"
] as const

const EXPECTED_RELATIONS = [
  ["hswm:kind:H:hyperedge-version", "HAS_INCIDENCE", "hswm:kind:H:incidence-version"],
  ["hswm:kind:H:incidence-version", "BINDS_ENTITY", "hswm:kind:H:stable-entity-version"],
  ["hswm:kind:W:semantic-transport-state", "REFERENCES_KIND", "hswm:kind:H:hyperedge-version"],
  ["hswm:kind:W:causal-efficacy-state", "REFERENCES_KIND", "hswm:kind:H:outcome-record"],
  ["hswm:kind:W:topology-propensity", "REFERENCES_KIND", "hswm:kind:H:hyperedge-version"],
  ["hswm:kind:A:route-decision", "REFERENCES_KIND", "hswm:kind:H:hyperedge-version"],
  ["hswm:kind:A:route-decision", "REFERENCES_KIND", "hswm:kind:W:semantic-transport-state"],
  ["hswm:kind:A:function-cell-invocation", "REFERENCES_KIND", "hswm:kind:F:function-cell-definition"],
  ["hswm:kind:A:function-cell-invocation", "REFERENCES_KIND", "hswm:kind:Pi:opaque-permit"],
  ["hswm:kind:A:eligibility-seal", "DERIVED_FROM", "hswm:kind:A:route-decision"],
  ["hswm:kind:H:outcome-record", "BINDS_OUTCOME", "hswm:kind:A:eligibility-seal"],
  ["hswm:kind:H:event-record", "DERIVED_FROM", "hswm:kind:A:function-cell-invocation"],
  ["hswm:kind:F:function-cell-definition", "REFERENCES_KIND", "hswm:kind:H:artifact-identity"],
  ["hswm:kind:F:function-cell-configuration", "REFERENCES_KIND", "hswm:kind:H:artifact-identity"],
  ["hswm:transition:ingress-admission", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:episode-step", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:episode-close", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:outcome-bound-learning", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:topology-rewrite", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:function-cell-lifecycle", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:operational-policy-lifecycle", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:constitutional-amendment", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:transition:rollback", "AUTHORIZED_BY", "hswm:role:Pi"],
  ["hswm:concept:core-state", "COMPILES_TO", "hswm:projection:typed-incidence"],
  ["hswm:concept:core-state", "COMPILES_TO", "hswm:projection:compiled-active-cut"],
  ["hswm:concept:core-state", "COMPILES_TO", "hswm:projection:readout"],
  ["hswm:concept:core-state", "COMPILES_TO", "hswm:projection:retrieval-index"],
  ["hswm:projection:typed-incidence", "CANNOT_COMMIT_BACK_TO", "hswm:concept:core-state"],
  ["hswm:projection:compiled-active-cut", "CANNOT_COMMIT_BACK_TO", "hswm:concept:core-state"],
  ["hswm:projection:readout", "CANNOT_COMMIT_BACK_TO", "hswm:concept:core-state"],
  ["hswm:projection:retrieval-index", "CANNOT_COMMIT_BACK_TO", "hswm:concept:core-state"],
  ["hswm:projection:repository-ontology", "CANNOT_COMMIT_BACK_TO", "hswm:concept:core-state"]
] as const

const EXPECTED_SEAMS = [
  ["hswm:seam:H-W", "hswm:role:H", "hswm:role:W"],
  ["hswm:seam:H-A", "hswm:role:H", "hswm:role:A"],
  ["hswm:seam:W-A", "hswm:role:W", "hswm:role:A"],
  ["hswm:seam:F-A", "hswm:role:F", "hswm:role:A"],
  ["hswm:seam:H-F", "hswm:role:H", "hswm:role:F"],
  ["hswm:seam:W-F", "hswm:role:W", "hswm:role:F"],
  ["hswm:seam:Pi-A", "hswm:role:Pi", "hswm:role:A"],
  ["hswm:seam:Pi-H", "hswm:role:Pi", "hswm:role:H"],
  ["hswm:seam:Pi-W", "hswm:role:Pi", "hswm:role:W"],
  ["hswm:seam:Pi-F", "hswm:role:Pi", "hswm:role:F"]
] as const

interface ExpectedTransition {
  readonly uid: string
  readonly reads: ReadonlyArray<string>
  readonly writes: ReadonlyArray<string>
  readonly writeContracts: ReadonlyArray<readonly [string, string]>
  readonly preserves: ReadonlyArray<string>
  readonly outcomeRequired: boolean
  readonly preOutcomeEligibilityRequired: boolean
  readonly ratificationRequired: boolean
}

const EXPECTED_TRANSITIONS: ReadonlyArray<ExpectedTransition> = [
  {
    uid: "hswm:transition:ingress-admission",
    reads: ["hswm:role:Pi"],
    writes: ["hswm:role:H", "hswm:role:A"],
    writeContracts: [
      ["hswm:kind:H:stable-entity-version", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:event-record", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:claim-record", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:evidence-record", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:judgment-record", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:outcome-record", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:provenance-link", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:H:artifact-identity", "CREATE_NEW_ATOM_OR_VERSION"],
      ["hswm:kind:A:activation-packet", "CREATE_OR_ADVANCE_EPISODE_LOCAL"],
      ["hswm:kind:A:episode-frontier", "CREATE_OR_ADVANCE_EPISODE_LOCAL"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:episode-step",
    reads: ["hswm:role:H", "hswm:role:W", "hswm:role:A", "hswm:role:F", "hswm:role:Pi"],
    writes: ["hswm:role:A"],
    writeContracts: [
      ["hswm:kind:A:activation-packet", "CREATE_OR_ADVANCE_EPISODE_LOCAL"],
      ["hswm:kind:A:episode-frontier", "CREATE_OR_ADVANCE_EPISODE_LOCAL"],
      ["hswm:kind:A:route-decision", "CREATE_OR_ADVANCE_EPISODE_LOCAL"],
      ["hswm:kind:A:function-cell-invocation", "CREATE_OR_ADVANCE_EPISODE_LOCAL"],
      ["hswm:kind:A:eligibility-seal", "SEAL_PRE_OUTCOME"],
      ["hswm:kind:A:compiled-active-cut", "CREATE_OR_ADVANCE_EPISODE_LOCAL"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:episode-close",
    reads: ["hswm:role:A", "hswm:role:Pi"],
    writes: ["hswm:role:A"],
    writeContracts: [
      ["hswm:kind:A:activation-packet", "EXPIRE_OR_CLOSE_EPISODE_LOCAL"],
      ["hswm:kind:A:episode-frontier", "EXPIRE_OR_CLOSE_EPISODE_LOCAL"],
      ["hswm:kind:A:route-decision", "EXPIRE_OR_CLOSE_EPISODE_LOCAL"],
      ["hswm:kind:A:function-cell-invocation", "EXPIRE_OR_CLOSE_EPISODE_LOCAL"],
      ["hswm:kind:A:eligibility-seal", "EXPIRE_OR_CLOSE_EPISODE_LOCAL"],
      ["hswm:kind:A:compiled-active-cut", "EXPIRE_OR_CLOSE_EPISODE_LOCAL"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:outcome-bound-learning",
    reads: ["hswm:role:H", "hswm:role:W", "hswm:role:A", "hswm:role:F", "hswm:role:Pi"],
    writes: ["hswm:role:H", "hswm:role:W", "hswm:role:A"],
    writeContracts: [
      ["hswm:kind:H:event-record", "CREATE_NEW_VERSION"],
      ["hswm:kind:H:judgment-record", "CREATE_NEW_VERSION"],
      ["hswm:kind:H:provenance-link", "CREATE_NEW_VERSION"],
      ["hswm:kind:W:operator-family", "SUPERSEDE_WITH_NEW_VERSION"],
      ["hswm:kind:W:semantic-transport-state", "SUPERSEDE_WITH_NEW_VERSION"],
      ["hswm:kind:W:causal-efficacy-state", "SUPERSEDE_WITH_NEW_VERSION"],
      ["hswm:kind:W:topology-propensity", "SUPERSEDE_WITH_NEW_VERSION"],
      ["hswm:kind:A:eligibility-seal", "CONSUME_AND_CLOSE"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: true,
    preOutcomeEligibilityRequired: true,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:topology-rewrite",
    reads: ["hswm:role:H", "hswm:role:W", "hswm:role:A", "hswm:role:Pi"],
    writes: ["hswm:role:H"],
    writeContracts: [
      ["hswm:kind:H:event-record", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:H:provenance-link", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:H:hyperedge-version", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:H:incidence-version", "CREATE_OR_SUPERSEDE_VERSION"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: true,
    preOutcomeEligibilityRequired: true,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:function-cell-lifecycle",
    reads: ["hswm:role:H", "hswm:role:F", "hswm:role:Pi"],
    writes: ["hswm:role:H", "hswm:role:F"],
    writeContracts: [
      ["hswm:kind:H:event-record", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:H:provenance-link", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:H:artifact-identity", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:F:function-cell-definition", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:F:port-contract", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:F:semantic-parser-contract", "CREATE_OR_SUPERSEDE_VERSION"],
      ["hswm:kind:F:function-cell-configuration", "CREATE_OR_SUPERSEDE_VERSION"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:operational-policy-lifecycle",
    reads: ["hswm:role:H", "hswm:role:Pi"],
    writes: ["hswm:role:H", "hswm:role:Pi"],
    writeContracts: [
      ["hswm:kind:H:event-record", "CREATE_NEW_VERSION"],
      ["hswm:kind:H:provenance-link", "CREATE_NEW_VERSION"],
      ["hswm:kind:Pi:operational-policy", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:authority-grant", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:consent-grant", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:capability-grant", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:budget-lease", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:transaction-policy", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:rollback-policy", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"],
      ["hswm:kind:Pi:opaque-permit", "ISSUE_SUPERSEDE_REVOKE_OR_EXPIRE"]
    ],
    preserves: ["hswm:kind:Pi:constitutional-boundary"],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: false
  },
  {
    uid: "hswm:transition:constitutional-amendment",
    reads: ["hswm:role:H", "hswm:role:Pi"],
    writes: ["hswm:role:H", "hswm:role:Pi"],
    writeContracts: [
      ["hswm:kind:H:event-record", "CREATE_NEW_VERSION"],
      ["hswm:kind:H:provenance-link", "CREATE_NEW_VERSION"],
      ["hswm:kind:Pi:constitutional-boundary", "AMEND_BY_EXPLICIT_RATIFICATION"]
    ],
    preserves: [],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: true
  },
  {
    uid: "hswm:transition:rollback",
    reads: ["hswm:role:H", "hswm:role:W", "hswm:role:F", "hswm:role:Pi"],
    writes: ["hswm:role:H", "hswm:role:W", "hswm:role:F"],
    writeContracts: [
      ["hswm:kind:H:stable-entity-version", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:event-record", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:claim-record", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:evidence-record", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:judgment-record", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:outcome-record", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:provenance-link", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:hyperedge-version", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:incidence-version", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:H:artifact-identity", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:W:operator-family", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:W:semantic-transport-state", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:W:causal-efficacy-state", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:W:topology-propensity", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:F:function-cell-definition", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:F:port-contract", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:F:semantic-parser-contract", "RESTORE_AS_NEW_VERSION"],
      ["hswm:kind:F:function-cell-configuration", "RESTORE_AS_NEW_VERSION"]
    ],
    preserves: [
      "hswm:kind:Pi:constitutional-boundary",
      "hswm:kind:Pi:operational-policy",
      "hswm:kind:Pi:authority-grant",
      "hswm:kind:Pi:consent-grant",
      "hswm:kind:Pi:capability-grant",
      "hswm:kind:Pi:budget-lease",
      "hswm:kind:Pi:transaction-policy",
      "hswm:kind:Pi:rollback-policy",
      "hswm:kind:Pi:opaque-permit"
    ],
    outcomeRequired: false,
    preOutcomeEligibilityRequired: false,
    ratificationRequired: false
  }
]

const EXPECTED_PROJECTIONS = [
  ["hswm:projection:typed-incidence", "LOSSLESS_IF_ROUNDTRIP_VERIFIED"],
  ["hswm:projection:compiled-active-cut", "LOSSLESS_IF_ROUNDTRIP_VERIFIED"],
  ["hswm:projection:readout", "LOSSY_DECLARED"],
  ["hswm:projection:retrieval-index", "LOSSY_DECLARED"],
  ["hswm:projection:repository-ontology", "NAVIGATION_ONLY"]
] as const

const EXTERNAL_ANCHOR_BUNDLE =
  "ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json" as const
const EXTERNAL_ANCHOR_BUNDLE_SHA256 =
  "4b7bd2574491c0c6f17f00226db53811311e993e6f995b6e3e076e8f1d457238" as const

const EXPECTED_EXTERNAL_ANCHORS = [
  [
    "sym:Concept:hswm-token-hypergraph-semantic-weight-map-core",
    "USER_PRIMARY",
    "USER_RATIFIED_CANON"
  ],
  [
    "sym:Concept:hswm-relational-ontology",
    "SECONDARY_AI",
    "UNSPECIFIED"
  ],
  [
    "sym:Concept:hswm-occam-minimization-direction",
    "USER_PRIMARY",
    "USER_RATIFIED_CANON"
  ],
  [
    "sym:Concept:hswm-computational-constitutional-irreducibility",
    "SECONDARY_AI",
    "UNSPECIFIED"
  ]
] as const

const EXPECTED_SOURCE_BINDINGS = [
  [
    "docs/canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md",
    "bd53702672368f2445b07138c7aaa4bc2757ad325cc75a60e65c85df0bb92a06",
    "MIXED_EXPLICIT",
    "role-bearing n-ary H, operator-valued W, derived z/U channels, dual planes"
  ],
  [
    "docs/canon/HSWM_MATH_DEFINITION_UNIFIED_2026-07-26.md",
    "b4bb79620682b5b37cd2b5fe3ec08d9e90aca19156fa2a1995b11abd41fa3663",
    "SECONDARY_AI",
    "current L0 evidence and open L1 target boundary"
  ]
] as const

const EXPECTED_NODE_COLLECTIONS = [
  "roles",
  "primitive_kinds",
  "seam_contracts",
  "transition_families",
  "projection_classes",
  "invariants"
] as const

const EXPECTED_DERIVED_EDGES = [
  "primitive_kinds.owner_role_uid -> OWNED_BY",
  "transition_families.reads_role_uids -> READS_ROLE",
  "transition_families.writes_role_uids -> WRITES_ROLE",
  "transition_families.write_contracts.target_kind_uid/effect -> WRITES_KIND_WITH_EFFECT",
  "transition_families.preserves_kind_uids -> PRESERVES_KIND",
  "transition_families.authority_role_uid -> AUTHORIZED_BY",
  "seam_contracts.left_role_uid/right_role_uid -> CONNECTS_ROLE"
] as const

const EXPECTED_NONCLAIMS = [
  "This ontology is not the HSWM runtime graph or cognitive state.",
  "The repository ontology and MCPs are not HSWM routing or learning.",
  "H/W/A/F/Pi are not five independent subsystems.",
  "This v1 taxonomy does not prove a universal or natural five-part ontology.",
  "Canonical labeling does not remove continuous W/F gauge freedom.",
  "A graph projection, prompt, transcript, or stored token is not durable learning by itself.",
  "No current checked-in evidence establishes integrated L1 HSWM causal macro-learning.",
  "No remote KG write or schema-registry mutation is authorized by this bundle."
] as const

const failure = (
  code: HSWMCoreOntologyErrorCode,
  detail: string
): Either.Either<never, HSWMCoreOntologyError> =>
  Either.left(new HSWMCoreOntologyError({ code, detail }))

const duplicatesOf = (values: ReadonlyArray<string>): ReadonlyArray<string> => {
  const seen = new Set<string>()
  const duplicates = new Set<string>()
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value)
    seen.add(value)
  }
  return [...duplicates].sort()
}

const sameSequence = (
  left: ReadonlyArray<string>,
  right: ReadonlyArray<string>
): boolean =>
  left.length === right.length &&
  left.every((value, index) => value === right[index])

const deepFreeze = <A>(value: A): A => {
  const visited = new WeakSet<object>()
  const freeze = (current: unknown): void => {
    if (typeof current !== "object" || current === null || visited.has(current)) {
      return
    }
    visited.add(current)
    for (const key of Reflect.ownKeys(current)) {
      const descriptor = Object.getOwnPropertyDescriptor(current, key)
      if (descriptor !== undefined && "value" in descriptor) {
        freeze(descriptor.value)
      }
    }
    Object.freeze(current)
  }
  freeze(value)
  return value
}

const validateIdentityEnvelope = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  if (
    ontology.bundle_uid !== EXPECTED_BUNDLE_UID ||
    ontology.root_uid !== EXPECTED_ROOT_UID
  ) {
    return failure(
      "NORMAL_FORM_INVALID",
      "the v1 bundle and root UIDs are stable identity, not renameable labels"
    )
  }
  if (
    !sameSequence(
      ontology.kg_projection_policy.node_collections,
      EXPECTED_NODE_COLLECTIONS
    ) ||
    !sameSequence(
      ontology.kg_projection_policy.derived_edges,
      EXPECTED_DERIVED_EDGES
    )
  ) {
    return failure(
      "PROJECTION_INVALID",
      "the v1 KG node collections and derived edge rules are closed"
    )
  }
  if (!sameSequence(ontology.nonclaims, EXPECTED_NONCLAIMS)) {
    return failure(
      "NORMAL_FORM_INVALID",
      "the v1 claim boundary is closed; changing it requires an explicit schema revision"
    )
  }
  return Either.right(undefined)
}

const validateCanonicalContent = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const digest = canonicalS2SControlSha256(ontology)
  if (Either.isLeft(digest)) {
    return failure(
      "CONTENT_DIGEST_INVALID",
      `the v1 ontology cannot be canonicalized: ${digest.left.reason}`
    )
  }
  if (digest.right !== EXPECTED_CANONICAL_CONTENT_SHA256) {
    return failure(
      "CONTENT_DIGEST_INVALID",
      `the complete v1 semantic content drifted: ${digest.right}`
    )
  }
  return Either.right(undefined)
}

const validateRoleSet = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const expectedUids = EXPECTED_ROLES.map(([uid]) => uid)
  const expectedSymbols = EXPECTED_ROLES.map(([, symbol]) => symbol)
  const actualUids = ontology.roles.map((role) => role.uid)
  const actualSymbols = ontology.roles.map((role) => role.symbol)

  if (
    !sameSequence(actualUids, expectedUids) ||
    !sameSequence(actualSymbols, expectedSymbols)
  ) {
    return failure(
      "ROLE_SET_INVALID",
      "role order and symbols must be exactly H/W/A/F/Pi"
    )
  }
  if (!sameSequence(ontology.normal_form_contract.role_uids, expectedUids)) {
    return failure(
      "NORMAL_FORM_INVALID",
      "normal-form role_uids must exactly match the five canonical roles"
    )
  }
  return Either.right(undefined)
}

const validatePrimitiveOwnership = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const roleUids = new Set(ontology.roles.map((role) => role.uid))
  const uidDuplicates = duplicatesOf(
    ontology.primitive_kinds.map((kind) => kind.uid)
  )
  const nameDuplicates = duplicatesOf(
    ontology.primitive_kinds.map((kind) => kind.name)
  )
  if (uidDuplicates.length > 0 || nameDuplicates.length > 0) {
    return failure(
      "UID_DUPLICATE",
      `primitive kind duplicates: uids=${uidDuplicates.join(",")}; names=${nameDuplicates.join(",")}`
    )
  }

  if (ontology.primitive_kinds.length !== EXPECTED_PRIMITIVE_KINDS.length) {
    return failure(
      "OWNER_INVALID",
      "the v1 primitive registry is closed; adding or removing a kind requires a new schema version"
    )
  }

  for (let index = 0; index < EXPECTED_PRIMITIVE_KINDS.length; index += 1) {
    const expected = EXPECTED_PRIMITIVE_KINDS[index]
    const actual = ontology.primitive_kinds[index]
    if (
      expected === undefined ||
      actual === undefined ||
      actual.uid !== expected[0] ||
      actual.owner_role_uid !== expected[1] ||
      actual.lifecycle !== expected[2]
    ) {
      return failure(
        "OWNER_INVALID",
        `primitive registry drift at index ${index}; v1 uid/owner/lifecycle mappings are immutable`
      )
    }
  }

  const ownerCounts = new Map<string, number>(
    ontology.roles.map((role) => [role.uid, 0])
  )
  for (const kind of ontology.primitive_kinds) {
    if (!roleUids.has(kind.owner_role_uid)) {
      return failure(
        "OWNER_INVALID",
        `primitive ${kind.uid} has unknown owner ${kind.owner_role_uid}`
      )
    }
    const owner = ontology.roles.find((role) => role.uid === kind.owner_role_uid)
    if (owner === undefined || !kind.uid.startsWith(`hswm:kind:${owner.symbol}:`)) {
      return failure(
        "OWNER_INVALID",
        `primitive ${kind.uid} does not match owner namespace ${kind.owner_role_uid}`
      )
    }
    ownerCounts.set(kind.owner_role_uid, (ownerCounts.get(kind.owner_role_uid) ?? 0) + 1)
  }
  for (const [roleUid, count] of ownerCounts) {
    if (count === 0) {
      return failure("OWNER_INVALID", `role ${roleUid} owns no primitive kind`)
    }
  }
  return Either.right(undefined)
}

const validateRelations = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const typeNames = ontology.relation_types.map((relation) => relation.type)
  const typeDuplicates = duplicatesOf(typeNames)
  if (typeDuplicates.length > 0) {
    return failure(
      "RELATION_TYPE_INVALID",
      `duplicate relation types: ${typeDuplicates.join(",")}`
    )
  }
  if (!sameSequence(typeNames, EXPECTED_RELATION_TYPES)) {
    return failure(
      "RELATION_TYPE_INVALID",
      "the v1 relation vocabulary is closed and order-stable"
    )
  }
  const knownTypes = new Set(typeNames)
  const endpoints = new Set([
    ontology.root_uid,
    ...ontology.roles.map((role) => role.uid),
    ...ontology.primitive_kinds.map((kind) => kind.uid),
    ...ontology.transition_families.map((transition) => transition.uid),
    ...ontology.projection_classes.map((projection) => projection.uid),
    ...ontology.seam_contracts.map((seam) => seam.uid),
    ...ontology.invariants.map((invariant) => invariant.uid)
  ])
  const relationKeys: Array<string> = []
  for (const relation of ontology.relations) {
    if (!knownTypes.has(relation.type)) {
      return failure(
        "RELATION_TYPE_INVALID",
        `relation uses undeclared type ${relation.type}`
      )
    }
    if (!endpoints.has(relation.from_uid) || !endpoints.has(relation.to_uid)) {
      return failure(
        "RELATION_ENDPOINT_INVALID",
        `relation has unknown endpoint: ${relation.from_uid} ${relation.type} ${relation.to_uid}`
      )
    }
    relationKeys.push(`${relation.from_uid}\u0000${relation.type}\u0000${relation.to_uid}`)
  }
  const relationDuplicates = duplicatesOf(relationKeys)
  if (relationDuplicates.length > 0) {
    return failure(
      "RELATION_DUPLICATE",
      "duplicate relation triples are forbidden"
    )
  }
  const expectedRelationKeys = EXPECTED_RELATIONS.map(
    ([fromUid, type, toUid]) => `${fromUid}\u0000${type}\u0000${toUid}`
  )
  if (!sameSequence(relationKeys, expectedRelationKeys)) {
    return failure(
      "RELATION_SET_INVALID",
      "the v1 explicit relation set is closed and order-stable"
    )
  }
  return Either.right(undefined)
}

const validateSeamsAndTransitions = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const roleUids = new Set(ontology.roles.map((role) => role.uid))
  const kindOwners = new Map(
    ontology.primitive_kinds.map((kind) => [kind.uid, kind.owner_role_uid])
  )
  const seamDuplicates = duplicatesOf(
    ontology.seam_contracts.map((seam) => seam.uid)
  )
  if (seamDuplicates.length > 0) {
    return failure("SEAM_INVALID", `duplicate seams: ${seamDuplicates.join(",")}`)
  }
  if (ontology.seam_contracts.length !== EXPECTED_SEAMS.length) {
    return failure("SEAM_INVALID", "the v1 seam registry is incomplete")
  }
  for (let index = 0; index < ontology.seam_contracts.length; index += 1) {
    const seam = ontology.seam_contracts[index]
    const expected = EXPECTED_SEAMS[index]
    if (seam === undefined || expected === undefined) {
      return failure("SEAM_INVALID", `missing seam at index ${index}`)
    }
    if (
      !roleUids.has(seam.left_role_uid) ||
      !roleUids.has(seam.right_role_uid) ||
      seam.left_role_uid === seam.right_role_uid ||
      seam.uid !== expected[0] ||
      seam.left_role_uid !== expected[1] ||
      seam.right_role_uid !== expected[2]
    ) {
      return failure("SEAM_INVALID", `invalid role seam ${seam.uid}`)
    }
  }

  const transitionDuplicates = duplicatesOf(
    ontology.transition_families.map((transition) => transition.uid)
  )
  if (transitionDuplicates.length > 0) {
    return failure(
      "TRANSITION_INVALID",
      `duplicate transitions: ${transitionDuplicates.join(",")}`
    )
  }
  if (ontology.transition_families.length !== EXPECTED_TRANSITIONS.length) {
    return failure(
      "TRANSITION_INVALID",
      "the v1 transition family registry is closed"
    )
  }
  for (let index = 0; index < ontology.transition_families.length; index += 1) {
    const transition = ontology.transition_families[index]
    const expected = EXPECTED_TRANSITIONS[index]
    if (transition === undefined || expected === undefined) {
      return failure("TRANSITION_INVALID", `missing transition at index ${index}`)
    }
    const dependencies = [
      ...transition.reads_role_uids,
      ...transition.writes_role_uids,
      transition.authority_role_uid
    ]
    if (dependencies.some((roleUid) => !roleUids.has(roleUid))) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} references an unknown role`
      )
    }
    if (
      duplicatesOf(transition.reads_role_uids).length > 0 ||
      duplicatesOf(transition.writes_role_uids).length > 0 ||
      transition.authority_role_uid !== "hswm:role:Pi"
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} has duplicate dependencies or non-Pi authority`
      )
    }
    const writeTargetUids = transition.write_contracts.map(
      (contract) => contract.target_kind_uid
    )
    if (
      duplicatesOf(writeTargetUids).length > 0 ||
      duplicatesOf(transition.preserves_kind_uids).length > 0
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} duplicates a write or preservation target`
      )
    }
    if (
      [...writeTargetUids, ...transition.preserves_kind_uids].some(
        (kindUid) => !kindOwners.has(kindUid)
      )
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} references an unknown primitive kind`
      )
    }
    if (
      transition.preserves_kind_uids.some((kindUid) =>
        writeTargetUids.includes(kindUid)
      )
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} cannot both preserve and write one kind`
      )
    }
    const writeOwnerSet = new Set(
      writeTargetUids.flatMap((kindUid) => {
        const owner = kindOwners.get(kindUid)
        return owner === undefined ? [] : [owner]
      })
    )
    const derivedWriteRoles = EXPECTED_ROLES.map(([uid]) => uid).filter(
      (roleUid) => writeOwnerSet.has(roleUid)
    )
    if (!sameSequence(transition.writes_role_uids, derivedWriteRoles)) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} role writes do not equal its kind-level write owners`
      )
    }
    const writeContractKeys = transition.write_contracts.map(
      (contract) => `${contract.target_kind_uid}\u0000${contract.effect}`
    )
    const expectedWriteContractKeys = expected.writeContracts.map(
      ([kindUid, effect]) => `${kindUid}\u0000${effect}`
    )
    if (
      transition.uid !== expected.uid ||
      !sameSequence(transition.reads_role_uids, expected.reads) ||
      !sameSequence(transition.writes_role_uids, expected.writes) ||
      !sameSequence(writeContractKeys, expectedWriteContractKeys) ||
      !sameSequence(transition.preserves_kind_uids, expected.preserves) ||
      transition.outcome_required !== expected.outcomeRequired ||
      transition.requires_pre_outcome_eligibility !==
        expected.preOutcomeEligibilityRequired ||
      transition.ratification_required !== expected.ratificationRequired
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} violates the closed v1 kind/effect contract`
      )
    }
    const writesPiStar = writeTargetUids.includes(
      "hswm:kind:Pi:constitutional-boundary"
    )
    if (
      writesPiStar !==
        (transition.uid === "hswm:transition:constitutional-amendment") ||
      writesPiStar !== transition.ratification_required
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} violates the exclusive Pi-star amendment law`
      )
    }
    if (
      !writesPiStar &&
      !transition.preserves_kind_uids.includes(
        "hswm:kind:Pi:constitutional-boundary"
      )
    ) {
      return failure(
        "TRANSITION_INVALID",
        `transition ${transition.uid} must explicitly preserve Pi-star`
      )
    }
  }
  const learning = ontology.transition_families.find(
    (transition) => transition.uid === "hswm:transition:outcome-bound-learning"
  )
  if (
    learning === undefined ||
    !learning.outcome_required ||
    !learning.requires_pre_outcome_eligibility ||
    learning.write_contracts.filter(
      (contract) => kindOwners.get(contract.target_kind_uid) === "hswm:role:A"
    ).length !== 1 ||
    !learning.write_contracts.some(
      (contract) =>
        contract.target_kind_uid === "hswm:kind:A:eligibility-seal" &&
        contract.effect === "CONSUME_AND_CLOSE"
    )
  ) {
    return failure(
      "TRANSITION_INVALID",
      "outcome-bound learning must require prior eligibility and only consume its A seal"
    )
  }
  const rollback = ontology.transition_families.find(
    (transition) => transition.uid === "hswm:transition:rollback"
  )
  const piKinds = ontology.primitive_kinds
    .filter((kind) => kind.owner_role_uid === "hswm:role:Pi")
    .map((kind) => kind.uid)
  if (
    rollback === undefined ||
    rollback.reads_role_uids.includes("hswm:role:A") ||
    rollback.write_contracts.some((contract) => {
      const owner = kindOwners.get(contract.target_kind_uid)
      return owner === "hswm:role:A" || owner === "hswm:role:Pi"
    }) ||
    !sameSequence(rollback.preserves_kind_uids, piKinds)
  ) {
    return failure(
      "TRANSITION_INVALID",
      "rollback must preserve every Pi kind and never read, revive, retag, or write A"
    )
  }
  const coveredKinds = new Set(
    ontology.transition_families.flatMap((transition) =>
      transition.write_contracts.map((contract) => contract.target_kind_uid)
    )
  )
  const uncoveredKinds = ontology.primitive_kinds
    .map((kind) => kind.uid)
    .filter((kindUid) => !coveredKinds.has(kindUid))
  if (uncoveredKinds.length > 0) {
    return failure(
      "TRANSITION_INVALID",
      `primitive kinds lack an authorized lifecycle transition: ${uncoveredKinds.join(",")}`
    )
  }
  return Either.right(undefined)
}

const validateProjectionsAndInvariants = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const projectionDuplicates = duplicatesOf(
    ontology.projection_classes.map((projection) => projection.uid)
  )
  if (
    projectionDuplicates.length > 0 ||
    ontology.projection_classes.some(
      (projection) => projection.direct_commit_back_allowed
    )
  ) {
    return failure(
      "PROJECTION_INVALID",
      "projection UIDs must be unique and direct commit-back must remain disabled"
    )
  }
  if (ontology.projection_classes.length !== EXPECTED_PROJECTIONS.length) {
    return failure("PROJECTION_INVALID", "the v1 projection registry is closed")
  }
  for (let index = 0; index < ontology.projection_classes.length; index += 1) {
    const projection = ontology.projection_classes[index]
    const expected = EXPECTED_PROJECTIONS[index]
    if (
      projection === undefined ||
      expected === undefined ||
      projection.uid !== expected[0] ||
      projection.fidelity !== expected[1]
    ) {
      return failure(
        "PROJECTION_INVALID",
        `projection registry drift at index ${index}`
      )
    }
  }

  const invariantCodes = ontology.invariants.map((invariant) => invariant.code)
  const invariantDuplicates = duplicatesOf(invariantCodes)
  const invariantUidDuplicates = duplicatesOf(
    ontology.invariants.map((invariant) => invariant.uid)
  )
  if (invariantDuplicates.length > 0 || invariantUidDuplicates.length > 0) {
    return failure(
      "INVARIANT_SET_INVALID",
      `duplicate invariant codes or UIDs: codes=${invariantDuplicates.join(",")}; uids=${invariantUidDuplicates.join(",")}`
    )
  }
  if (ontology.invariants.length !== EXPECTED_INVARIANTS.length) {
    return failure(
      "INVARIANT_SET_INVALID",
      "the v1 invariant registry is closed"
    )
  }
  for (let index = 0; index < EXPECTED_INVARIANTS.length; index += 1) {
    const invariant = ontology.invariants[index]
    const expected = EXPECTED_INVARIANTS[index]
    if (
      invariant === undefined ||
      expected === undefined ||
      invariant.uid !== expected[0] ||
      invariant.code !== expected[1]
    ) {
      return failure(
        "INVARIANT_SET_INVALID",
        `invariant registry drift at index ${index}`
      )
    }
  }
  return Either.right(undefined)
}

const validateGlobalUids = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const uids = [
    ontology.bundle_uid,
    ontology.root_uid,
    ...ontology.roles.map((role) => role.uid),
    ...ontology.primitive_kinds.map((kind) => kind.uid),
    ...ontology.seam_contracts.map((seam) => seam.uid),
    ...ontology.transition_families.map((transition) => transition.uid),
    ...ontology.projection_classes.map((projection) => projection.uid),
    ...ontology.invariants.map((invariant) => invariant.uid)
  ]
  const duplicates = duplicatesOf(uids)
  if (duplicates.length > 0) {
    return failure(
      "UID_DUPLICATE",
      `ontology node UIDs collide across collections: ${duplicates.join(",")}`
    )
  }
  return Either.right(undefined)
}

const validateSources = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<void, HSWMCoreOntologyError> => {
  const duplicatePaths = duplicatesOf(
    ontology.source_bindings.map((source) => source.path)
  )
  const duplicateAnchors = duplicatesOf(
    ontology.external_anchors.map((anchor) => anchor.uid)
  )
  if (duplicatePaths.length > 0 || duplicateAnchors.length > 0) {
    return failure(
      "SOURCE_BINDING_INVALID",
      `duplicate sources or anchors: paths=${duplicatePaths.join(",")}; anchors=${duplicateAnchors.join(",")}`
    )
  }
  if (ontology.source_bindings.length !== EXPECTED_SOURCE_BINDINGS.length) {
    return failure(
      "SOURCE_BINDING_INVALID",
      "the v1 source binding registry is closed"
    )
  }
  for (let index = 0; index < EXPECTED_SOURCE_BINDINGS.length; index += 1) {
    const source = ontology.source_bindings[index]
    const expected = EXPECTED_SOURCE_BINDINGS[index]
    if (
      source === undefined ||
      expected === undefined ||
      source.path !== expected[0] ||
      source.sha256 !== expected[1] ||
      source.authority_class !== expected[2] ||
      source.binding_scope !== expected[3]
    ) {
      return failure(
        "SOURCE_BINDING_INVALID",
        `source binding registry drift at index ${index}`
      )
    }
  }
  if (ontology.external_anchors.length !== EXPECTED_EXTERNAL_ANCHORS.length) {
    return failure(
      "SOURCE_BINDING_INVALID",
      "the v1 external anchor registry is closed"
    )
  }
  for (let index = 0; index < ontology.external_anchors.length; index += 1) {
    const anchor = ontology.external_anchors[index]
    const expected = EXPECTED_EXTERNAL_ANCHORS[index]
    if (
      anchor === undefined ||
      expected === undefined ||
      anchor.uid !== expected[0] ||
      anchor.source_bundle !== EXTERNAL_ANCHOR_BUNDLE ||
      anchor.source_bundle_sha256 !== EXTERNAL_ANCHOR_BUNDLE_SHA256 ||
      anchor.expected_authority_class !== expected[1] ||
      anchor.expected_canonical_scope !== expected[2]
    ) {
      return failure(
        "SOURCE_BINDING_INVALID",
        `external anchor registry drift at index ${index}`
      )
    }
  }
  if (ontology.kg_projection_policy.remote_publication !== "NOT_AUTHORIZED") {
    return failure(
      "PROJECTION_INVALID",
      "the v1 ontology must not authorize remote KG publication"
    )
  }
  return Either.right(undefined)
}

const validateHSWMCoreResponsibilityOntology = (
  ontology: HSWMCoreResponsibilityOntology
): Either.Either<HSWMCoreResponsibilityOntology, HSWMCoreOntologyError> => {
  const validations = [
    validateIdentityEnvelope(ontology),
    validateRoleSet(ontology),
    validatePrimitiveOwnership(ontology),
    validateGlobalUids(ontology),
    validateRelations(ontology),
    validateSeamsAndTransitions(ontology),
    validateProjectionsAndInvariants(ontology),
    validateSources(ontology),
    validateCanonicalContent(ontology)
  ]
  for (const validation of validations) {
    if (Either.isLeft(validation)) return Either.left(validation.left)
  }
  return Either.right(ontology)
}

export const decodeHSWMCoreResponsibilityOntology = (
  input: unknown
): Either.Either<HSWMCoreResponsibilityOntology, HSWMCoreOntologyError> => {
  const decoded = Schema.decodeUnknownEither(
    HSWMCoreResponsibilityOntologySchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return failure(
      "SCHEMA_INVALID",
      "ontology failed the strict Effect Schema boundary"
    )
  }
  return Either.map(
    validateHSWMCoreResponsibilityOntology(decoded.right),
    deepFreeze
  )
}

export const decodeHSWMCoreResponsibilityOntologyBytes = (
  input: unknown
): Either.Either<HSWMCoreResponsibilityOntology, HSWMCoreOntologyError> => {
  const parsed = parseS2SJsonBytes(input, 1_048_576)
  if (Either.isLeft(parsed)) {
    return failure(
      "JSON_INVALID",
      `ontology JSON bytes failed closed: ${parsed.left.reason}`
    )
  }
  return decodeHSWMCoreResponsibilityOntology(parsed.right)
}
