/**
 * DNRD-5 schema-only boundary.
 *
 * This module defines persistent vocabulary and structural invariants only. It
 * does not invoke models, resolve a Permit, submit a transition, or make an
 * occurrence, learning, or scientific-result claim.
 */
import { Data, Either, Schema } from "effect"

import { validateHSWMCanonicalSchemaV2 } from "./canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  CanonicalAtomV2Schema,
  canonicalAtomV2KeyId,
  snapshotHSWMCanonicalSchemaV2,
  type CanonicalAtomV2,
  type CanonicalAtomV2KindContract,
  type CanonicalAtomV2Reference,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export const DNRD5_SCHEMA_VERSION = "hswm:dnrd5:causal-macroplasticity:v1" as const
export const DNRD5_REFERENCE_TYPE = "hswm:dnrd5:reference" as const
export const DNRD5_ARM_LABELS = [
  "ACTIVE",
  "OUTCOME_INDEPENDENT_SHAM",
  "DELAYED_NO_CREDIT",
  "EXACT_W0_ROLLBACK"
] as const

export type Dnrd5ArmLabel = (typeof DNRD5_ARM_LABELS)[number]

/** Structural boundary: V2 eligibility is not an admission capability. */
export const DNRD5_CURRENT_STATE_PERMIT_BOUNDARY = Object.freeze({
  currentStatePermit: "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY",
  admission: "NOT_IMPLEMENTED_BY_DNRD5_SCHEMA_ONLY",
  traceRef: "NULL_REQUIRED_BY_GENERIC_V2",
  trajectoryBinding: "TYPED_ATOM_REFERENCE_OR_CONTENT_BINDING_REQUIRED"
} as const)

export type Dnrd5CanonicalAtomKind =
  | "study_randomness"
  | "evaluator_commitment"
  | "block_spec"
  | "probe_commitment"
  | "placebo_commitment"
  | "w0_snapshot"
  | "fork_incidence"
  | "block_assignment"
  | "episode_activation"
  | "trajectory_contract"
  | "trajectory_seal"
  | "permit_policy"
  | "authorization_decision"
  | "capability_issuance"
  | "revocation_status"
  | "evaluator_capability"
  | "evaluator_release"
  | "hidden_outcome"
  | "placebo_receipt"
  | "outcome_credit_escrow"
  | "feedback_assignment"
  | "grant_snapshot"
  | "capability_consumption"
  | "revision_proposal"
  | "candidate_validation"
  | "credit_decision"
  | "transition_receipt"
  | "restore_policy"
  | "macro_disposition"
  | "projection_policy"
  | "restore_transaction"
  | "behavior_projection"
  | "probe_trajectory"
  | "probe_outcome"
  | "block_seal"
  | "block_analysis"
  | "study_analysis"

export type Dnrd5SchemaErrorCode =
  | "SCHEMA_INVALID"
  | "ATOM_INVALID"
  | "ARM_INVALID"
  | "PRINCIPAL_INVALID"
  | "PRINCIPAL_INEQUALITY"
  | "FORWARD_REFERENCE"
  | "DUPLICATE_ATOM"
  | "REFERENCE_INVALID"
  | "PROVENANCE_INVALID"
  | "REVISION_INVALID"

export class Dnrd5SchemaError extends Data.TaggedError("Dnrd5SchemaError")<{
  readonly code: Dnrd5SchemaErrorCode
  readonly detail: string
}> {}

const fail = (code: Dnrd5SchemaErrorCode, detail: string) =>
  Either.left(new Dnrd5SchemaError({ code, detail }))

const kindName = (kind: Dnrd5CanonicalAtomKind): string =>
  `hswm:dnrd5:${kind}`

export const DNRD5_OWNER_ROLE_BY_KIND = Object.freeze({
  study_randomness: "randomness_custodian", evaluator_commitment: "evaluator_commitment_custodian",
  block_spec: "experiment_custodian", probe_commitment: "probe_custodian", placebo_commitment: "placebo_custodian",
  w0_snapshot: "canonical_state_custodian", fork_incidence: "clone_custodian", block_assignment: "assignment_custodian",
  episode_activation: "experiment_custodian", trajectory_contract: "transition_contract_custodian", trajectory_seal: "transition_executor",
  permit_policy: "permit_policy_custodian", authorization_decision: "authorization_decision_custodian", capability_issuance: "capability_custodian",
  revocation_status: "revocation_custodian", evaluator_capability: "evaluator_capability_custodian", evaluator_release: "evaluator_release_custodian",
  hidden_outcome: "outcome_evaluator", placebo_receipt: "placebo_custodian", outcome_credit_escrow: "outcome_escrow_custodian",
  feedback_assignment: "credit_adjudicator", grant_snapshot: "grant_custodian", revision_proposal: "revision_proposer",
  capability_consumption: "capability_consumption_custodian",
  candidate_validation: "revision_validator", credit_decision: "credit_adjudicator", transition_receipt: "transition_receipt_custodian",
  restore_policy: "restore_policy_custodian", macro_disposition: "canonical_state_custodian", projection_policy: "projection_policy_custodian",
  restore_transaction: "restore_custodian", behavior_projection: "projection_custodian", probe_trajectory: "transition_executor",
  probe_outcome: "outcome_evaluator", block_seal: "occurrence_custodian", block_analysis: "independent_judge", study_analysis: "independent_judge"
} satisfies Record<Dnrd5CanonicalAtomKind, string>)

const ownerName = (kind: Dnrd5CanonicalAtomKind): string =>
  `owner:dnrd5:${DNRD5_OWNER_ROLE_BY_KIND[kind]}`

type Ref = readonly [role: string, targets: ReadonlyArray<Dnrd5CanonicalAtomKind>, minimum?: number, maximum?: number]

const refs = (...roles: ReadonlyArray<Ref>): ReadonlyArray<CanonicalAtomV2KindContract["referenceContracts"][number]> =>
  roles.length === 0
    ? []
    : [{
        referenceType: DNRD5_REFERENCE_TYPE,
        roles: roles.map(([role, targets, minimum = 1, maximum = 1]) => ({
          role: `role:dnrd5:${role}`,
          targetKinds: targets.map(kindName),
          minimum,
          maximum
        }))
      }]

const contract = (
  kind: Dnrd5CanonicalAtomKind,
  referenceRoles: ReadonlyArray<Ref> = []
): CanonicalAtomV2KindContract => ({
  kind: kindName(kind),
  form: referenceRoles.length === 0 ? "ENTITY" : "RELATION",
  revisionPolicy: "SINGLETON",
  allowedOwners: [ownerName(kind)],
  minimumArity: referenceRoles.length === 0 ? 0 : 1,
  referenceContracts: refs(...referenceRoles)
})

const KINDS: ReadonlyArray<CanonicalAtomV2KindContract> = [
  contract("study_randomness"),
  contract("evaluator_commitment"),
  contract("block_spec", [["randomness", ["study_randomness"]], ["evaluator", ["evaluator_commitment"]]]),
  contract("probe_commitment", [["block-spec", ["block_spec"]], ["randomness", ["study_randomness"]]]),
  contract("placebo_commitment", [["block-spec", ["block_spec"]], ["randomness", ["study_randomness"]]]),
  contract("w0_snapshot", [["block-spec", ["block_spec"]]]),
  contract("fork_incidence", [["w0", ["w0_snapshot"]]]),
  contract("block_assignment", [["randomness", ["study_randomness"]], ["block-spec", ["block_spec"]], ["fork", ["fork_incidence"], 4, 4]]),
  contract("episode_activation", [["block-spec", ["block_spec"]], ["probe", ["probe_commitment"]], ["w0", ["w0_snapshot"]], ["fork", ["fork_incidence"], 4, 4], ["assignment", ["block_assignment"]], ["evaluator", ["evaluator_commitment"]]]),
  contract("trajectory_contract", [["activation", ["episode_activation"]]]),
  contract("trajectory_seal", [["activation", ["episode_activation"]], ["contract", ["trajectory_contract"]], ["w0", ["w0_snapshot"]]]),
  contract("permit_policy"),
  contract("authorization_decision", [["policy", ["permit_policy"]]]),
  contract("capability_issuance", [["authorization", ["authorization_decision"]], ["policy", ["permit_policy"]]]),
  contract("revocation_status", [["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]]]),
  contract("evaluator_capability", [["commitment", ["evaluator_commitment"]], ["capability", ["capability_issuance"]], ["authorization", ["authorization_decision"]], ["revocation", ["revocation_status"]]]),
  contract("evaluator_release", [["trajectory", ["trajectory_seal", "probe_trajectory"]], ["capability", ["evaluator_capability"]], ["authorization", ["authorization_decision"]], ["revocation", ["revocation_status"]]]),
  contract("hidden_outcome", [["trajectory", ["trajectory_seal"]], ["release", ["evaluator_release"]], ["commitment", ["evaluator_commitment"]]]),
  contract("placebo_receipt", [["commitment", ["placebo_commitment"]], ["randomness", ["study_randomness"]]]),
  contract("outcome_credit_escrow", [["outcome", ["hidden_outcome"]], ["capability", ["capability_issuance"]], ["policy", ["permit_policy"]]]),
  contract("feedback_assignment", [["fork", ["fork_incidence"]], ["assignment", ["block_assignment"]], ["source", ["hidden_outcome", "placebo_receipt", "outcome_credit_escrow"]]]),
  contract("grant_snapshot", [["policy", ["permit_policy"]], ["authorization", ["authorization_decision"]], ["capability", ["capability_issuance"]], ["revocation", ["revocation_status"]]]),
  contract("revision_proposal", [["trajectory", ["trajectory_seal"]], ["feedback", ["feedback_assignment"]]]),
  contract("candidate_validation", [["proposal", ["revision_proposal"]]]),
  contract("credit_decision", [["trajectory", ["trajectory_seal"]], ["outcome", ["hidden_outcome"]], ["feedback", ["feedback_assignment"]], ["proposal", ["revision_proposal"]], ["grant", ["grant_snapshot"]]]),
  contract("capability_consumption", [
    ["grant", ["grant_snapshot"]],
    ["capability", ["capability_issuance"]],
    ["revocation", ["revocation_status"]],
    ["credit", ["credit_decision"], 0, 1],
    ["validation", ["candidate_validation"], 0, 1],
    ["restore-policy", ["restore_policy"], 0, 1],
    ["staging-successor", ["macro_disposition"], 0, 1],
    ["w0", ["w0_snapshot"], 0, 1]
  ]),
  contract("transition_receipt", [["credit", ["credit_decision"]], ["validation", ["candidate_validation"]], ["grant", ["grant_snapshot"]]]),
  contract("restore_policy", [["policy", ["permit_policy"]], ["capability", ["capability_issuance"]]]),
  contract("macro_disposition", [["proposal", ["revision_proposal"]], ["receipt", ["transition_receipt"]], ["restore-policy", ["restore_policy"]]]),
  contract("projection_policy"),
  contract("restore_transaction", [["w0", ["w0_snapshot"]], ["grant", ["grant_snapshot"]], ["policy", ["restore_policy"]], ["staging-successor", ["macro_disposition"]]]),
  contract("behavior_projection", [["source", ["macro_disposition", "restore_transaction", "w0_snapshot"]], ["policy", ["projection_policy"]]]),
  contract("probe_trajectory", [["probe", ["probe_commitment"]], ["projection", ["behavior_projection"]]]),
  contract("probe_outcome", [["trajectory", ["probe_trajectory"]], ["release", ["evaluator_release"]], ["probe", ["probe_commitment"]]]),
  // Full per-block atom/call-ledger closure belongs to a later lifecycle/content
  // contract; this schema-only slice deliberately does not claim to prove it.
  contract("block_seal", [["block", ["block_spec"]], ["assignment", ["block_assignment"]], ["probe-outcome", ["probe_outcome"], 4, 4]]),
  contract("block_analysis", [["seal", ["block_seal"]]]),
  contract("study_analysis", [["block-analysis", ["block_analysis"], 300, 300]])
]

const CANONICAL_SCHEMA = snapshotHSWMCanonicalSchemaV2({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: DNRD5_SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "DNRD-5 schema-only structural contract; not a Permit, admission, occurrence, learning, or result claim.",
  owners: [...new Map(KINDS.map(({ kind, allowedOwners }) => {
    const address = allowedOwners[0]!
    const atomKind = kind.slice("hswm:dnrd5:".length) as Dnrd5CanonicalAtomKind
    return [address, { address, obligation: `Schema-relative ${DNRD5_OWNER_ROLE_BY_KIND[atomKind]} owner.` }] as const
  })).values()],
  kinds: KINDS
})

/** Returns a fresh deep snapshot; caller mutation cannot alter the registry. */
export const makeDnrd5CanonicalSchemaV2 = (): HSWMCanonicalSchemaV2 =>
  snapshotHSWMCanonicalSchemaV2(CANONICAL_SCHEMA)

export const validateDnrd5CanonicalSchemaV2 = (
  schema: HSWMCanonicalSchemaV2
): Either.Either<HSWMCanonicalSchemaV2, Dnrd5SchemaError> => {
  if (Either.isLeft(validateHSWMCanonicalSchemaV2(schema))) {
    return fail("SCHEMA_INVALID", "schema fails the generic canonical-v2 structural contract")
  }
  if (JSON.stringify(schema) !== JSON.stringify(CANONICAL_SCHEMA)) {
    return fail("SCHEMA_INVALID", "schema is not the exact immutable DNRD-5 schema-only registry")
  }
  return Either.right(schema)
}

export const validateDnrd5ArmLabel = (
  arm: string
): Either.Either<Dnrd5ArmLabel, Dnrd5SchemaError> =>
  (DNRD5_ARM_LABELS as ReadonlyArray<string>).includes(arm)
    ? Either.right(arm as Dnrd5ArmLabel)
    : fail("ARM_INVALID", `unknown or alias DNRD-5 arm label ${arm}`)

export interface Dnrd5StateChangePrincipals {
  readonly actorClaim: string
  readonly authorizer: string
  readonly canonicalStateCustodian: string
  readonly restoreCustodian: string
  readonly creditAdjudicator: string
  readonly authorizationDecisionRecordCustodian: string
}

export const validateDnrd5StateChangePrincipals = (
  principals: Dnrd5StateChangePrincipals
): Either.Either<Dnrd5StateChangePrincipals, Dnrd5SchemaError> => {
  if (Object.keys(principals).length !== 6 || !["actorClaim", "authorizer", "canonicalStateCustodian", "restoreCustodian", "creditAdjudicator", "authorizationDecisionRecordCustodian"].every((key) => Object.prototype.hasOwnProperty.call(principals, key))) {
    return fail("PRINCIPAL_INVALID", "state-change principals must have the exact runtime key set")
  }
  const principalPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
  if (Object.values(principals).some((principal) =>
    typeof principal !== "string" || !principalPattern.test(principal)
  )) {
    return fail("PRINCIPAL_INVALID", "state-change principals must be canonical nonempty identifiers")
  }
  const prohibited = [
    principals.actorClaim,
    principals.canonicalStateCustodian,
    principals.restoreCustodian,
    principals.creditAdjudicator,
    principals.authorizationDecisionRecordCustodian
  ]
  return prohibited.includes(principals.authorizer)
    ? fail("PRINCIPAL_INEQUALITY", "authorizer principal must differ from actor, state/restore custodians, credit adjudicator, and authorization-record custodian")
    : Either.right(principals)
}

const matchesRole = (
  atom: CanonicalAtomV2,
  reference: CanonicalAtomV2Reference,
  contract: CanonicalAtomV2KindContract
): boolean => contract.referenceContracts.some(({ referenceType, roles }) =>
  reference.referenceType === referenceType && roles.some(({ role, targetKinds }) =>
    reference.role === role && targetKinds.includes(atom.kind)
  )
)

/**
 * Enforces a supplied chronology of already-materialized atoms. A reference may
 * only point to a preceding atom, so same-batch/future references fail closed.
 */
export const validateDnrd5ChronologicalAtoms = (
  schema: HSWMCanonicalSchemaV2,
  atoms: ReadonlyArray<unknown>
): Either.Either<ReadonlyArray<CanonicalAtomV2>, Dnrd5SchemaError> => {
  if (Either.isLeft(validateDnrd5CanonicalSchemaV2(schema))) {
    return fail("SCHEMA_INVALID", "chronology requires the exact DNRD-5 schema-only registry")
  }
  const seen = new Map<string, CanonicalAtomV2>()
  const logicalIds = new Set<string>()
  const decodedAtoms: CanonicalAtomV2[] = []
  for (const candidate of atoms) {
    const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
      onExcessProperty: "error"
    })(candidate)
    if (Either.isLeft(decoded)) {
      return fail("ATOM_INVALID", "atom fails strict canonical-v2 structural decoding")
    }
    const atom = decoded.right
    const atomId = canonicalAtomV2KeyId(atom.key)
    if (seen.has(atomId)) return fail("DUPLICATE_ATOM", `duplicate atom ${atomId}`)
    const logicalId = `${atom.key.schemaVersion}|${atom.key.lineageId}|${atom.key.atomUid}`
    if (logicalIds.has(logicalId)) return fail("DUPLICATE_ATOM", `duplicate logical atom ${logicalId}`)
    const contract = CANONICAL_SCHEMA.kinds.find(({ kind }) => kind === atom.kind)
    if (atom.key.schemaVersion !== DNRD5_SCHEMA_VERSION || contract === undefined || atom.responsibilityOwner !== contract.allowedOwners[0]) {
      return fail("ATOM_INVALID", `atom ${atom.key.atomUid} has unknown kind, alias, schema, or owner mismatch`)
    }
    if (atom.key.revisionId !== 0) {
      return fail("REVISION_INVALID", `singleton atom ${atom.key.atomUid} must be revision 0`)
    }
    const isRelation = contract.form === "RELATION"
    if (atom.provenance.mode === "MIGRATION" ||
      (!isRelation && (atom.provenance.mode !== "BOOTSTRAP" || atom.provenance.sourceRef !== null)) ||
      (isRelation && (atom.provenance.mode !== "DERIVATION" || atom.provenance.sourceRef === null))) {
      return fail("PROVENANCE_INVALID", `atom ${atom.key.atomUid} has invalid DNRD-5 provenance`)
    }
    if (
      atom.provenance.sourceRef !== null &&
      !seen.has(canonicalAtomV2KeyId(atom.provenance.sourceRef))
    ) {
      return fail("FORWARD_REFERENCE", `atom ${atom.key.atomUid} has a missing or forward provenance predecessor`)
    }
    const referenceIds = new Set<string>()
    for (const reference of atom.references) {
      const referenceId = `${reference.referenceType}|${reference.role}|${canonicalAtomV2KeyId(reference.target)}`
      if (referenceIds.has(referenceId)) {
        return fail("REFERENCE_INVALID", `atom ${atom.key.atomUid} repeats a typed reference`)
      }
      referenceIds.add(referenceId)
      const target = seen.get(canonicalAtomV2KeyId(reference.target))
      if (target === undefined) return fail("FORWARD_REFERENCE", `atom ${atom.key.atomUid} references a missing, same-batch, or future atom`)
      if (!matchesRole(target, reference, contract)) return fail("ATOM_INVALID", `atom ${atom.key.atomUid} has an undeclared typed reference`)
    }
    if (isRelation && atom.provenance.sourceRef !== null && !atom.references.some((reference) =>
      canonicalAtomV2KeyId(reference.target) === canonicalAtomV2KeyId(atom.provenance.sourceRef!)
    )) return fail("PROVENANCE_INVALID", `atom ${atom.key.atomUid} provenance must be a declared typed-reference target`)
    for (const referenceContract of contract.referenceContracts) {
      for (const role of referenceContract.roles) {
        const count = atom.references.filter((reference) => reference.referenceType === referenceContract.referenceType && reference.role === role.role).length
        if (count < role.minimum || count > role.maximum) return fail("ATOM_INVALID", `atom ${atom.key.atomUid} violates ${referenceContract.referenceType}/${role.role} cardinality`)
      }
    }
    seen.set(atomId, atom)
    logicalIds.add(logicalId)
    decodedAtoms.push(atom)
  }
  const freeze = (value: unknown): unknown => {
    if (value !== null && typeof value === "object") {
      for (const child of Object.values(value as Record<string, unknown>)) freeze(child)
      Object.freeze(value)
    }
    return value
  }
  return Either.right(freeze(JSON.parse(JSON.stringify(decodedAtoms))) as typeof decodedAtoms)
}
