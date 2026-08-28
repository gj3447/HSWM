/**
 * DNRD-5 successor schema vocabulary only.
 *
 * This is a design instrument: it names schema-approved atoms and their
 * typed-reference closure.  It cannot dispatch a model, decide Permit,
 * admit an occurrence, or establish learning or a scientific result.
 */
import { Data, Either } from "effect"

import { validateHSWMCanonicalSchemaV2 } from "./canonical-atom-v2-domain.js"
import { DNRD5_V2_SCHEMA_VERSION } from "./canonical-atom-v2-dnrd5-v2-identity.js"
import {
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  snapshotHSWMCanonicalSchemaV2,
  type CanonicalAtomV2KindContract,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export { DNRD5_V2_SCHEMA_VERSION } from "./canonical-atom-v2-dnrd5-v2-identity.js"
export const DNRD5_V2_REFERENCE_TYPE = "hswm:dnrd5:v2:reference" as const
export const DNRD5_V2_SCHEMA_CONTENT_BYTE_LENGTH = 31_298 as const
export const DNRD5_V2_SCHEMA_CONTENT_SHA256 =
  "a921264c5d1b5d9186d291e6a17ddc0282ce4eaa8832b1a599b7237c23d4b357" as const

export type Dnrd5V2CanonicalAtomKind =
  | "study_randomness" | "evaluator_commitment" | "block_spec"
  | "probe_commitment" | "placebo_commitment" | "w0_snapshot"
  | "fork_incidence" | "block_assignment" | "episode_activation"
  | "trajectory_contract" | "trajectory_seal" | "permit_policy"
  | "authorization_decision" | "capability_issuance" | "revocation_status"
  | "evaluator_capability" | "evaluator_release" | "audit_release_capability"
  | "hidden_outcome"
  | "placebo_receipt" | "outcome_credit_escrow" | "feedback_assignment"
  | "grant_snapshot" | "capability_consumption" | "revision_proposal"
  | "candidate_validation" | "credit_decision" | "revision_admission_decision"
  | "rollback_decision" | "evidence_seal_consumption"
  | "revision_transition_receipt" | "rollback_transition_receipt"
  | "restore_policy" | "macro_disposition" | "projection_policy"
  | "restore_transaction" | "behavior_projection" | "probe_trajectory"
  | "probe_outcome" | "audit_release" | "block_evidence_manifest"
  | "block_seal" | "block_analysis" | "study_analysis"

export type Dnrd5V2SchemaErrorCode = "SCHEMA_INVALID"
export class Dnrd5V2SchemaError extends Data.TaggedError("Dnrd5V2SchemaError")<{
  readonly code: Dnrd5V2SchemaErrorCode
  readonly detail: string
}> {}

const kindName = (kind: Dnrd5V2CanonicalAtomKind): string => `hswm:dnrd5:v2:${kind}`
const ownerName = (kind: Dnrd5V2CanonicalAtomKind): string =>
  `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`
type Ref = readonly [string, ReadonlyArray<Dnrd5V2CanonicalAtomKind>, number?, number?]

export const DNRD5_V2_OWNER_ROLE_BY_KIND = Object.freeze({
  study_randomness: "randomness_custodian", evaluator_commitment: "evaluator_commitment_custodian",
  block_spec: "experiment_custodian", probe_commitment: "probe_custodian", placebo_commitment: "placebo_custodian",
  w0_snapshot: "canonical_state_custodian", fork_incidence: "clone_custodian", block_assignment: "assignment_custodian",
  episode_activation: "experiment_custodian", trajectory_contract: "transition_contract_custodian", trajectory_seal: "transition_executor",
  permit_policy: "permit_policy_custodian", authorization_decision: "authorization_decision_custodian", capability_issuance: "capability_custodian",
  revocation_status: "revocation_custodian", evaluator_capability: "evaluator_capability_custodian", evaluator_release: "evaluator_release_custodian",
  audit_release_capability: "audit_release_capability_custodian",
  hidden_outcome: "outcome_evaluator", placebo_receipt: "placebo_custodian", outcome_credit_escrow: "outcome_escrow_custodian",
  feedback_assignment: "credit_adjudicator", grant_snapshot: "grant_custodian", capability_consumption: "capability_consumption_custodian",
  revision_proposal: "revision_proposer", candidate_validation: "revision_validator", credit_decision: "credit_adjudicator",
  revision_admission_decision: "admission_decision_custodian", rollback_decision: "rollback_decision_custodian",
  evidence_seal_consumption: "evidence_seal_consumption_custodian", revision_transition_receipt: "transition_receipt_custodian",
  rollback_transition_receipt: "rollback_receipt_custodian", restore_policy: "restore_policy_custodian",
  macro_disposition: "canonical_state_custodian", projection_policy: "projection_policy_custodian",
  restore_transaction: "restore_custodian", behavior_projection: "projection_custodian", probe_trajectory: "transition_executor",
  probe_outcome: "outcome_evaluator", audit_release: "audit_release_custodian", block_evidence_manifest: "evidence_manifest_custodian",
  block_seal: "occurrence_custodian", block_analysis: "independent_judge", study_analysis: "independent_judge"
} satisfies Record<Dnrd5V2CanonicalAtomKind, string>)

const refs = (...roles: ReadonlyArray<Ref>): ReadonlyArray<CanonicalAtomV2KindContract["referenceContracts"][number]> =>
  roles.length === 0 ? [] : [{ referenceType: DNRD5_V2_REFERENCE_TYPE, roles: roles.map(([role, targets, minimum = 1, maximum = 1]) => ({
    role: `role:dnrd5:v2:${role}`, targetKinds: targets.map(kindName), minimum, maximum
  })) }]
const contract = (kind: Dnrd5V2CanonicalAtomKind, referenceRoles: ReadonlyArray<Ref> = []): CanonicalAtomV2KindContract => ({
  kind: kindName(kind), form: referenceRoles.length === 0 ? "ENTITY" : "RELATION", revisionPolicy: "SINGLETON",
  allowedOwners: [ownerName(kind)], minimumArity: referenceRoles.length === 0 ? 0 : 1, referenceContracts: refs(...referenceRoles)
})

const KINDS: ReadonlyArray<CanonicalAtomV2KindContract> = [
  contract("study_randomness"), contract("evaluator_commitment"),
  contract("block_spec", [["randomness", ["study_randomness"]], ["evaluator", ["evaluator_commitment"]]]),
  contract("probe_commitment", [["block-spec", ["block_spec"]], ["randomness", ["study_randomness"]]]),
  contract("placebo_commitment", [["block-spec", ["block_spec"]], ["randomness", ["study_randomness"]]]),
  contract("w0_snapshot", [["block-spec", ["block_spec"]]]), contract("fork_incidence", [["w0", ["w0_snapshot"]]]),
  contract("block_assignment", [["randomness", ["study_randomness"]], ["block-spec", ["block_spec"]], ["fork", ["fork_incidence"], 4, 4]]),
  contract("episode_activation", [["block-spec", ["block_spec"]], ["probe", ["probe_commitment"]], ["w0", ["w0_snapshot"]], ["fork", ["fork_incidence"], 4, 4], ["assignment", ["block_assignment"]], ["evaluator", ["evaluator_commitment"]]]),
  contract("trajectory_contract", [["activation", ["episode_activation"]]]),
  contract("trajectory_seal", [["activation", ["episode_activation"]], ["contract", ["trajectory_contract"]], ["w0", ["w0_snapshot"]]]),
  contract("permit_policy"), contract("authorization_decision", [["policy", ["permit_policy"]]]),
  contract("capability_issuance", [["authorization", ["authorization_decision"]], ["policy", ["permit_policy"]]]),
  contract("revocation_status", [["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]]]),
  contract("evaluator_capability", [["commitment", ["evaluator_commitment"]], ["capability", ["capability_issuance"]], ["authorization", ["authorization_decision"]], ["revocation", ["revocation_status"]]]),
  contract("evaluator_release", [["trajectory", ["trajectory_seal", "probe_trajectory"]], ["capability", ["evaluator_capability"]], ["authorization", ["authorization_decision"]], ["revocation", ["revocation_status"]]]),
  contract("audit_release_capability", [["block", ["block_spec"]], ["commitment", ["evaluator_commitment"]], ["policy", ["permit_policy"]], ["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]]]),
  contract("hidden_outcome", [["trajectory", ["trajectory_seal"]], ["release", ["evaluator_release"]], ["commitment", ["evaluator_commitment"]]]),
  contract("placebo_receipt", [["commitment", ["placebo_commitment"]], ["randomness", ["study_randomness"]]]),
  contract("outcome_credit_escrow", [["outcome", ["hidden_outcome"]], ["capability", ["capability_issuance"]], ["policy", ["permit_policy"]]]),
  contract("feedback_assignment", [["fork", ["fork_incidence"]], ["assignment", ["block_assignment"]], ["source", ["hidden_outcome", "placebo_receipt", "outcome_credit_escrow"]]]),
  contract("grant_snapshot", [["policy", ["permit_policy"]], ["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]]]),
  contract("revision_proposal", [["trajectory", ["trajectory_seal"]], ["feedback", ["feedback_assignment"]]]),
  contract("candidate_validation", [["proposal", ["revision_proposal"]]]),
  // The union permits the three declared arm evidence sources.  Matching that
  // source to the assigned arm is a semantic/occurrence-validator obligation,
  // not something a generic kind contract can infer from opaque content.
  contract("credit_decision", [["trajectory", ["trajectory_seal"]], ["credit-source", ["hidden_outcome", "placebo_receipt", "outcome_credit_escrow"]], ["feedback", ["feedback_assignment"]], ["proposal", ["revision_proposal"]], ["grant", ["grant_snapshot"]]]),
  // These decisions exist before the effect batch.  Receipts below are post-CAS observations, never admission inputs.
  contract("revision_admission_decision", [["block", ["block_spec"]], ["assignment", ["block_assignment"]], ["fork", ["fork_incidence"]], ["proposal", ["revision_proposal"]], ["validation", ["candidate_validation"]], ["credit", ["credit_decision"]], ["grant", ["grant_snapshot"]], ["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]]]),
  contract("rollback_decision", [["block", ["block_spec"]], ["assignment", ["block_assignment"]], ["fork", ["fork_incidence"]], ["w0", ["w0_snapshot"]], ["grant", ["grant_snapshot"]], ["policy", ["restore_policy"]], ["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]], ["staging-successor", ["macro_disposition"]], ["staging-receipt", ["revision_transition_receipt"]]]),
  // Main-effect consumption is one prestate authority chain plus exactly one
  // decision branch.  The effect atom (not a later receipt) binds this same-CAS
  // consumption to its successor state.
  contract("capability_consumption", [["grant", ["grant_snapshot"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]], ["decision", ["revision_admission_decision", "rollback_decision"]]]),
  // Separate consumption namespace for postcommit observation/sealing commands;
  // it cannot be substituted for the main effect consumption above.
  contract("evidence_seal_consumption", [["grant", ["grant_snapshot"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]], ["purpose", ["revision_admission_decision", "rollback_decision", "audit_release_capability"]]]),
  contract("revision_transition_receipt", [["decision", ["revision_admission_decision"]], ["effect-consumption", ["capability_consumption"]], ["successor", ["macro_disposition"]], ["evidence-consumption", ["evidence_seal_consumption"]]]),
  contract("rollback_transition_receipt", [["decision", ["rollback_decision"]], ["effect-consumption", ["capability_consumption"]], ["restore", ["restore_transaction"]], ["evidence-consumption", ["evidence_seal_consumption"]]]),
  contract("restore_policy", [["policy", ["permit_policy"]], ["capability", ["capability_issuance"]]]),
  contract("macro_disposition", [["proposal", ["revision_proposal"]], ["revision-admission-decision", ["revision_admission_decision"]], ["restore-policy", ["restore_policy"]], ["effect-consumption", ["capability_consumption"]]]),
  contract("projection_policy"), contract("restore_transaction", [["w0", ["w0_snapshot"]], ["grant", ["grant_snapshot"]], ["policy", ["restore_policy"]], ["decision", ["rollback_decision"]], ["consumption", ["capability_consumption"]], ["staging-successor", ["macro_disposition"]]]),
  contract("behavior_projection", [["source", ["macro_disposition", "restore_transaction", "w0_snapshot"]], ["policy", ["projection_policy"]]]),
  contract("probe_trajectory", [["probe", ["probe_commitment"]], ["projection", ["behavior_projection"]]]),
  contract("probe_outcome", [["trajectory", ["probe_trajectory"]], ["release", ["evaluator_release"]], ["probe", ["probe_commitment"]]]),
  contract("audit_release", [["block", ["block_spec"]], ["assignment", ["block_assignment"]], ["outcome", ["hidden_outcome"]], ["escrow", ["outcome_credit_escrow"]], ["probe-trajectory", ["probe_trajectory"], 4, 4], ["probe-outcome", ["probe_outcome"], 4, 4], ["evaluator-capability", ["evaluator_capability"]], ["release-capability", ["audit_release_capability"]], ["evaluator-release", ["evaluator_release"], 4, 4], ["evidence-consumption", ["evidence_seal_consumption"]]]),
  // The rollback arm first has an active-style admission receipt; its later W0
  // restore has a distinct postcommit rollback receipt and restore transaction.
  contract("block_evidence_manifest", [["block", ["block_spec"]], ["assignment", ["block_assignment"]], ["trajectory", ["trajectory_seal"]], ["probe-trajectory", ["probe_trajectory"], 4, 4], ["probe-outcome", ["probe_outcome"], 4, 4], ["audit-release", ["audit_release"]], ["revision-receipt", ["revision_transition_receipt"], 3, 3], ["rollback-receipt", ["rollback_transition_receipt"], 1, 1], ["restore", ["restore_transaction"], 1, 1]]),
  contract("block_seal", [["block", ["block_spec"]], ["assignment", ["block_assignment"]], ["manifest", ["block_evidence_manifest"]], ["audit-release", ["audit_release"]], ["probe-outcome", ["probe_outcome"], 4, 4]]),
  contract("block_analysis", [["seal", ["block_seal"]]]), contract("study_analysis", [["block-analysis", ["block_analysis"], 300, 300]])
]

const CANONICAL_SCHEMA = snapshotHSWMCanonicalSchemaV2({
  _tag: "HSWMCanonicalSchemaV2", contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: DNRD5_V2_SCHEMA_VERSION, scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "DNRD-5 successor schema-only structural contract; not a Permit, admission, occurrence, learning, or result claim.",
  owners: [...new Map(KINDS.map(({ kind, allowedOwners }) => {
    const address = allowedOwners[0]!
    const atomKind = kind.slice("hswm:dnrd5:v2:".length) as Dnrd5V2CanonicalAtomKind
    return [address, { address, obligation: `Schema-relative ${DNRD5_V2_OWNER_ROLE_BY_KIND[atomKind]} owner.` }] as const
  })).values()], kinds: KINDS
})

export const makeDnrd5V2CanonicalSchema = (): HSWMCanonicalSchemaV2 => snapshotHSWMCanonicalSchemaV2(CANONICAL_SCHEMA)
export const validateDnrd5V2CanonicalSchema = (schema: HSWMCanonicalSchemaV2): Either.Either<HSWMCanonicalSchemaV2, Dnrd5V2SchemaError> =>
  Either.isLeft(validateHSWMCanonicalSchemaV2(schema)) || JSON.stringify(schema) !== JSON.stringify(CANONICAL_SCHEMA)
    ? Either.left(new Dnrd5V2SchemaError({ code: "SCHEMA_INVALID", detail: "schema is not the exact immutable DNRD-5 v2 registry" }))
    : Either.right(schema)
