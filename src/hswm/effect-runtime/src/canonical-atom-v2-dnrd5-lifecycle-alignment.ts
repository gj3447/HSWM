/**
 * Independent checker for the DNRD-5 lifecycle/atom alignment vector.
 *
 * This is deliberately a structural, source-free rehearsal: lifecycle rows are
 * descriptors, never admitted canonical atoms or evidence of occurrence.
 */
import { createHash } from "node:crypto"

import { Data, Either } from "effect"

import { canonicalAtomV2SchemaContentBytes } from "./canonical-atom-v2-content-bound.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import {
  DNRD5_OWNER_ROLE_BY_KIND,
  DNRD5_SCHEMA_VERSION,
  makeDnrd5CanonicalSchemaV2,
  type Dnrd5CanonicalAtomKind
} from "./canonical-atom-v2-dnrd5-schema.js"
import {
  DNRD5_LIFECYCLE_CONTRACT_VERSION,
  validateDnrd5SealedBlockLifecycle
} from "./canonical-atom-v2-dnrd5-lifecycle.js"

export const DNRD5_LIFECYCLE_ATOM_ALIGNMENT_VERSION =
  "hswm-dnrd5-lifecycle-atom-alignment/v1" as const

export type Dnrd5LifecycleAtomAlignmentErrorCode =
  | "BYTES_INVALID"
  | "ROOT_INVALID"
  | "LIFECYCLE_INVALID"
  | "COUNT_INVALID"
  | "SCHEMA_INVALID"
  | "MAPPING_INVALID"
  | "AUTHORITY_INVALID"
  | "NONCLAIM_INVALID"

export class Dnrd5LifecycleAtomAlignmentError extends Data.TaggedError("Dnrd5LifecycleAtomAlignmentError")<{
  readonly code: Dnrd5LifecycleAtomAlignmentErrorCode
  readonly detail: string
}> {}

const fail = (code: Dnrd5LifecycleAtomAlignmentErrorCode, detail: string) =>
  Either.left(new Dnrd5LifecycleAtomAlignmentError({ code, detail }))
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const keys = (value: object): string[] => Object.keys(value).sort()
const sameKeys = (value: object, expected: ReadonlyArray<string>): boolean =>
  JSON.stringify(keys(value)) === JSON.stringify([...expected].sort())
const asRecord = (value: unknown): Record<string, unknown> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
const same = (actual: unknown, expected: unknown): boolean => JSON.stringify(actual) === JSON.stringify(expected)

const artifactKinds = [
  "STUDY_RANDOMNESS", "BLOCK_SPEC", "EVALUATOR_COMMITMENT", "PROBE_COMMITMENT", "PLACEBO_COMMITMENT", "W0_SNAPSHOT", "FORK_INCIDENCE", "ARM_ASSIGNMENT", "EPISODE_ACTIVATION", "TRAJECTORY_CONTRACT", "TRAJECTORY_SEAL", "EVALUATOR_RELEASE", "HIDDEN_OUTCOME", "OUTCOME_CREDIT_ESCROW", "PLACEBO_RECEIPT", "FEEDBACK_ASSIGNMENT", "REVISION_PROPOSAL", "CANDIDATE_VALIDATION", "CREDIT_DECISION", "ARM_TRANSITION", "TRANSITION_RECEIPT", "RESTORE_TRANSACTION", "BEHAVIOR_PROJECTION", "PROBE_RESPONSE_SEAL", "PROBE_OUTCOME", "DELAYED_AUDIT_RELEASE", "BLOCK_SEAL"
] as const

const counts: Readonly<Record<string, number>> = {
  STUDY_RANDOMNESS: 1, BLOCK_SPEC: 1, EVALUATOR_COMMITMENT: 1, PROBE_COMMITMENT: 1, PLACEBO_COMMITMENT: 1,
  W0_SNAPSHOT: 1, FORK_INCIDENCE: 4, ARM_ASSIGNMENT: 4, EPISODE_ACTIVATION: 1, TRAJECTORY_CONTRACT: 1,
  TRAJECTORY_SEAL: 1, EVALUATOR_RELEASE: 1, HIDDEN_OUTCOME: 1, OUTCOME_CREDIT_ESCROW: 1, PLACEBO_RECEIPT: 1,
  FEEDBACK_ASSIGNMENT: 4, REVISION_PROPOSAL: 4, CANDIDATE_VALIDATION: 4, CREDIT_DECISION: 4, ARM_TRANSITION: 4,
  TRANSITION_RECEIPT: 3, RESTORE_TRANSACTION: 1, BEHAVIOR_PROJECTION: 4, PROBE_RESPONSE_SEAL: 4,
  PROBE_OUTCOME: 4, DELAYED_AUDIT_RELEASE: 1, BLOCK_SEAL: 1
}

const canonicalKinds: ReadonlyArray<Dnrd5CanonicalAtomKind> = [
  "study_randomness", "evaluator_commitment", "block_spec", "probe_commitment", "placebo_commitment", "w0_snapshot", "fork_incidence", "block_assignment", "episode_activation", "trajectory_contract", "trajectory_seal", "permit_policy", "authorization_decision", "capability_issuance", "revocation_status", "evaluator_capability", "evaluator_release", "hidden_outcome", "placebo_receipt", "outcome_credit_escrow", "feedback_assignment", "grant_snapshot", "revision_proposal", "candidate_validation", "credit_decision", "capability_consumption", "transition_receipt", "restore_policy", "macro_disposition", "projection_policy", "restore_transaction", "behavior_projection", "probe_trajectory", "probe_outcome", "block_seal", "block_analysis", "study_analysis"
]
const supportKinds = ["permit_policy", "authorization_decision", "capability_issuance", "revocation_status", "evaluator_capability", "grant_snapshot", "capability_consumption", "restore_policy", "macro_disposition", "projection_policy"]
const nonclaims = [
  "NO_CANONICAL_ATOM_UID_OWNER_PROVENANCE_OR_TYPED_REFERENCE_IS_BOUND",
  "NO_ACTUAL_PRODUCTION_BYTES_OR_PROVIDER_CALL_IS_PRESENT",
  "NO_PERMIT_ADMISSION_OCCURRENCE_CAUSAL_LEARNING_OR_SCIENTIFIC_RESULT_IS_ESTABLISHED",
  "LIFECYCLE_AND_KG_PROJECTIONS_ARE_NOT_HSWM_COGNITION_OR_LEARNING"
]
const direct = (canonicalKind: string, count: number) => ({ canonicalKind, canonicalAtomCount: count, projectionCount: count, mappingMode: "DIRECT_NONAUTHORITATIVE_PROJECTION", gapCode: "ATOM_KEY_OWNER_PROVENANCE_TYPED_REFS_UNBOUND", sourceCanonicalKinds: [canonicalKind] })
const mappingExpectations: Readonly<Record<string, Record<string, unknown>>> = {
  STUDY_RANDOMNESS: direct("study_randomness", 1), BLOCK_SPEC: direct("block_spec", 1), EVALUATOR_COMMITMENT: direct("evaluator_commitment", 1), PROBE_COMMITMENT: direct("probe_commitment", 1), PLACEBO_COMMITMENT: direct("placebo_commitment", 1), W0_SNAPSHOT: direct("w0_snapshot", 1), FORK_INCIDENCE: direct("fork_incidence", 4),
  ARM_ASSIGNMENT: { canonicalKind: "block_assignment", canonicalAtomCount: 1, projectionCount: 4, mappingMode: "FOUR_SLOT_PROJECTION_OF_ONE_ATOM", gapCode: "FOUR_ROWS_LACK_ONE_ASSIGNMENT_REF_AND_FOUR_DISTINCT_FORK_REFS", sourceCanonicalKinds: ["study_randomness", "block_spec", "fork_incidence", "block_assignment"] },
  EPISODE_ACTIVATION: direct("episode_activation", 1), TRAJECTORY_CONTRACT: direct("trajectory_contract", 1), TRAJECTORY_SEAL: direct("trajectory_seal", 1), EVALUATOR_RELEASE: direct("evaluator_release", 1), HIDDEN_OUTCOME: direct("hidden_outcome", 1), OUTCOME_CREDIT_ESCROW: direct("outcome_credit_escrow", 1), PLACEBO_RECEIPT: direct("placebo_receipt", 1), FEEDBACK_ASSIGNMENT: direct("feedback_assignment", 4), REVISION_PROPOSAL: direct("revision_proposal", 4), CANDIDATE_VALIDATION: direct("candidate_validation", 4), CREDIT_DECISION: direct("credit_decision", 4),
  ARM_TRANSITION: { canonicalKind: null, canonicalAtomCount: null, projectionCount: 4, mappingMode: "DERIVED_MULTI_ATOM_PROJECTION", gapCode: "ARM_DEPENDENT_SOURCE_ATOM_BINDING_CONTRACT_ABSENT", sourceCanonicalKinds: ["candidate_validation", "credit_decision", "capability_consumption", "transition_receipt", "macro_disposition", "restore_transaction"] },
  TRANSITION_RECEIPT: direct("transition_receipt", 3), RESTORE_TRANSACTION: direct("restore_transaction", 1), BEHAVIOR_PROJECTION: direct("behavior_projection", 4),
  PROBE_RESPONSE_SEAL: { canonicalKind: "probe_trajectory", canonicalAtomCount: 4, projectionCount: 4, mappingMode: "SEMANTIC_ADAPTER_REQUIRED", gapCode: "RESPONSE_SEAL_BYTES_NOT_EQUIVALENT_TO_PROBE_TRAJECTORY_ATOM", sourceCanonicalKinds: ["probe_commitment", "behavior_projection", "probe_trajectory"] },
  PROBE_OUTCOME: direct("probe_outcome", 4), DELAYED_AUDIT_RELEASE: { canonicalKind: null, canonicalAtomCount: null, projectionCount: 1, mappingMode: "CANONICAL_KIND_MISSING", gapCode: "AUDIT_RELEASE_REQUIRES_SUCCESSOR_SCHEMA_KIND_OWNER_AND_AUTHORITY_REFS", sourceCanonicalKinds: [] }, BLOCK_SEAL: direct("block_seal", 1)
}
const armProfiles = [
  { arm: "ACTIVE", effectStatus: "ADMITTED_GENUINE_OUTCOME_SUCCESSOR", requiredSourceCanonicalKinds: ["candidate_validation", "credit_decision", "capability_consumption", "transition_receipt", "macro_disposition"] },
  { arm: "OUTCOME_INDEPENDENT_SHAM", effectStatus: "ADMITTED_MATCHED_PLACEBO_SUCCESSOR", requiredSourceCanonicalKinds: ["candidate_validation", "credit_decision", "capability_consumption", "transition_receipt", "macro_disposition"] },
  { arm: "DELAYED_NO_CREDIT", effectStatus: "QUARANTINED_NO_ADMISSION", requiredSourceCanonicalKinds: ["candidate_validation", "credit_decision"] },
  { arm: "EXACT_W0_ROLLBACK", effectStatus: "ADMITTED_THEN_RESTORED_EXACT_W0", requiredSourceCanonicalKinds: ["candidate_validation", "credit_decision", "capability_consumption", "transition_receipt", "macro_disposition", "restore_transaction"] }
]

const refs = (kind: string): ReadonlyArray<unknown> => {
  const schema = makeDnrd5CanonicalSchemaV2()
  return schema.kinds.find((candidate) => candidate.kind === `hswm:dnrd5:${kind}`)?.referenceContracts[0]?.roles ?? []
}
const expectedRefs = (rows: ReadonlyArray<readonly [string, ReadonlyArray<string>, number, number]>): ReadonlyArray<unknown> =>
  rows.map(([role, targetKinds, minimum, maximum]) => ({ role: `role:dnrd5:${role}`, targetKinds: targetKinds.map((kind) => `hswm:dnrd5:${kind}`), minimum, maximum }))

export interface Dnrd5LifecycleAtomAlignmentValidation {
  readonly eventCount: 15
  readonly artifactCount: 59
  readonly artifactKindCount: 27
  readonly generationCallCount: 9
  readonly claimFlags: Readonly<{
    readonly canonicalAtomsBound: false
    readonly actualProductionBytesPresent: false
    readonly providerCallPresent: false
    readonly permitAdmissionOccurrenceLearningOrResult: false
  }>
}

/** Validates the exact canonical bytes of both shared vectors. */
export const validateDnrd5LifecycleAtomAlignment = (
  alignmentBytes: Uint8Array,
  lifecycleVectorBytes: Uint8Array
): Either.Either<Dnrd5LifecycleAtomAlignmentValidation, Dnrd5LifecycleAtomAlignmentError> => {
  const decodedLifecycle = decodeCanonicalJsonBytes(lifecycleVectorBytes)
  if (Either.isLeft(decodedLifecycle)) return fail("BYTES_INVALID", "lifecycle bytes are not strict canonical JSON")
  const reencodedLifecycle = canonicalJsonBytes(decodedLifecycle.right)
  if (Either.isLeft(reencodedLifecycle) || !same([...reencodedLifecycle.right], [...lifecycleVectorBytes])) return fail("BYTES_INVALID", "lifecycle bytes are not exact canonical JSON")

  const decodedAlignment = decodeCanonicalJsonBytes(alignmentBytes)
  if (Either.isLeft(decodedAlignment)) return fail("BYTES_INVALID", "alignment bytes are not strict canonical JSON")
  const reencodedAlignment = canonicalJsonBytes(decodedAlignment.right)
  if (Either.isLeft(reencodedAlignment) || !same([...reencodedAlignment.right], [...alignmentBytes])) return fail("BYTES_INVALID", "alignment bytes are not exact canonical JSON")

  const lifecycleVector = decodedLifecycle.right
  const alignment = asRecord(decodedAlignment.right)
  const lifecycleRoot = asRecord(lifecycleVector)
  if (alignment === null || lifecycleRoot === null) return fail("ROOT_INVALID", "both vectors must be JSON objects")
  if (!sameKeys(alignment, ["_tag", "armTransitionProfiles", "blockSealCurrentContract", "canonicalJsonVersion", "canonicalSchemaSha256", "contractVersion", "expectedTerminal", "hardNonclaims", "kindMappings", "lifecycleContractVersion", "lifecycleVectorSha256", "observedLifecycle", "postBlockCanonicalKinds", "requiredCanonicalSupport", "schemaVersion", "scope", "status"])) return fail("ROOT_INVALID", "alignment root keys drifted")
  if (!sameKeys(lifecycleRoot, ["_tag", "artifactContents", "canonicalJsonVersion", "contractVersion", "expectedTerminal", "fixtureScope", "lifecycle"])) return fail("ROOT_INVALID", "lifecycle vector root keys drifted")
  if (alignment["_tag"] !== "Dnrd5LifecycleAtomAlignment" || alignment["contractVersion"] !== DNRD5_LIFECYCLE_ATOM_ALIGNMENT_VERSION || alignment["lifecycleContractVersion"] !== DNRD5_LIFECYCLE_CONTRACT_VERSION || alignment["schemaVersion"] !== DNRD5_SCHEMA_VERSION || alignment["canonicalJsonVersion"] !== "hswm-canonical-json/v1" || alignment["scope"] !== "KIND_CARDINALITY_AND_PROJECTION_BOUNDARY_ONLY" || alignment["status"] !== "STRUCTURAL_ALIGNMENT_GAPS_EXPOSED_NOT_ATOM_CLOSURE") return fail("ROOT_INVALID", "alignment identity fields drifted")
  if (lifecycleRoot["_tag"] !== "Dnrd5LifecycleCrossLanguageVector" || lifecycleRoot["contractVersion"] !== "hswm-dnrd5-lifecycle-cross-language-vector/v1" || lifecycleRoot["canonicalJsonVersion"] !== "hswm-canonical-json/v1" || lifecycleRoot["fixtureScope"] !== "ONE_SYNTHETIC_BLOCK_DESCRIPTOR_REHEARSAL_ONLY") return fail("ROOT_INVALID", "lifecycle vector identity fields drifted")
  if (alignment["lifecycleVectorSha256"] !== sha256(lifecycleVectorBytes)) return fail("BYTES_INVALID", "alignment does not bind exact lifecycle vector bytes")
  const lifecycle = lifecycleRoot["lifecycle"]
  const lifecycleValidated = validateDnrd5SealedBlockLifecycle(lifecycle)
  if (Either.isLeft(lifecycleValidated)) return fail("LIFECYCLE_INVALID", lifecycleValidated.left.detail)
  const events = lifecycleValidated.right.events
  const actualCounts: Record<string, number> = {}
  const actualCalls = events.reduce((total, event) => total + event.generationCallCount, 0)
  for (const event of events) for (const artifact of event.artifacts) actualCounts[artifact.kind] = (actualCounts[artifact.kind] ?? 0) + 1
  if (events.length !== 15 || Object.keys(actualCounts).length !== 27 || Object.values(actualCounts).reduce((a, b) => a + b, 0) !== 59 || actualCalls !== 9 || !same(actualCounts, counts)) return fail("COUNT_INVALID", "independently derived lifecycle 15/59/27/9 or kind counts drifted")
  const observed = asRecord(alignment["observedLifecycle"])
  const rows = Array.isArray(observed?.["kindCounts"]) ? observed["kindCounts"] : null
  if (observed === null || observed["eventCount"] !== 15 || observed["artifactCount"] !== 59 || observed["artifactKindCount"] !== 27 || observed["generationCallCount"] !== 9 || rows === null || !same(rows, artifactKinds.map((artifactKind) => ({ artifactKind, count: counts[artifactKind] })))) return fail("COUNT_INVALID", "declared lifecycle counts/order drifted")
  const schemaBytes = canonicalAtomV2SchemaContentBytes(makeDnrd5CanonicalSchemaV2())
  if (Either.isLeft(schemaBytes) || alignment["canonicalSchemaSha256"] !== sha256(schemaBytes.right)) return fail("SCHEMA_INVALID", "alignment does not bind the exact current canonical schema bytes")
  const schema = makeDnrd5CanonicalSchemaV2()
  if (schema.kinds.length !== 37 || !same(schema.kinds.map((kind) => kind.kind), canonicalKinds.map((kind) => `hswm:dnrd5:${kind}`))) return fail("SCHEMA_INVALID", "live schema kind universe drifted")
  for (const kind of canonicalKinds) {
    const contract = schema.kinds.find((candidate) => candidate.kind === `hswm:dnrd5:${kind}`)
    if (contract === undefined || contract.allowedOwners.length !== 1 || contract.allowedOwners[0] !== `owner:dnrd5:${DNRD5_OWNER_ROLE_BY_KIND[kind]}`) return fail("SCHEMA_INVALID", `schema owner is not sole/exact for ${kind}`)
  }
  if (!same(refs("block_assignment"), expectedRefs([["randomness", ["study_randomness"], 1, 1], ["block-spec", ["block_spec"], 1, 1], ["fork", ["fork_incidence"], 4, 4]])) || !same(refs("block_seal"), expectedRefs([["block", ["block_spec"], 1, 1], ["assignment", ["block_assignment"], 1, 1], ["probe-outcome", ["probe_outcome"], 4, 4]]))) return fail("SCHEMA_INVALID", "special canonical typed references drifted")
  const support = Array.isArray(alignment["requiredCanonicalSupport"]) ? alignment["requiredCanonicalSupport"] : []
  if (!same(support.map((row) => asRecord(row)?.["canonicalKind"]), supportKinds) || support.some((row) => asRecord(row)?.["lifecycleArtifactPresent"] !== false)) return fail("MAPPING_INVALID", "required non-lifecycle support kinds drifted")
  const mappings = Array.isArray(alignment["kindMappings"]) ? alignment["kindMappings"].map(asRecord) : []
  if (mappings.length !== 27 || !same(mappings.map((row) => row?.["artifactKind"]), artifactKinds)) return fail("MAPPING_INVALID", "kind mapping coverage/order drifted")
  if (mappings.some((row) => row === null || row["authorityBoundary"] !== "NON_AUTHORITATIVE_LIFECYCLE_PROJECTION_ONLY" || row["closureReady"] !== false)) return fail("AUTHORITY_INVALID", "a lifecycle row was promoted to authoritative or closure-ready")
  for (const row of mappings) {
    if (row === null || !sameKeys(row, ["artifactKind", "authorityBoundary", "canonicalAtomCount", "canonicalKind", "closureReady", "gapCode", "mappingMode", "projectionCount", "sourceCanonicalKinds"]) || !same(Object.fromEntries(["canonicalKind", "canonicalAtomCount", "projectionCount", "mappingMode", "gapCode", "sourceCanonicalKinds"].map((key) => [key, row[key]])), mappingExpectations[String(row["artifactKind"])])) return fail("MAPPING_INVALID", "an exact lifecycle mapping row drifted")
  }
  const mapping = (artifactKind: string) => mappings.find((row) => row?.["artifactKind"] === artifactKind)
  const assignment = mapping("ARM_ASSIGNMENT")
  const transition = mapping("ARM_TRANSITION")
  const probe = mapping("PROBE_RESPONSE_SEAL")
  const audit = mapping("DELAYED_AUDIT_RELEASE")
  if (assignment?.["mappingMode"] !== "FOUR_SLOT_PROJECTION_OF_ONE_ATOM" || assignment["projectionCount"] !== 4 || assignment["canonicalAtomCount"] !== 1 || assignment["canonicalKind"] !== "block_assignment" || !same(assignment["sourceCanonicalKinds"], ["study_randomness", "block_spec", "fork_incidence", "block_assignment"]) || transition?.["mappingMode"] !== "DERIVED_MULTI_ATOM_PROJECTION" || transition["canonicalKind"] !== null || transition["canonicalAtomCount"] !== null || transition["projectionCount"] !== 4 || probe?.["mappingMode"] !== "SEMANTIC_ADAPTER_REQUIRED" || probe["canonicalKind"] !== "probe_trajectory" || probe["projectionCount"] !== 4 || audit?.["mappingMode"] !== "CANONICAL_KIND_MISSING" || audit["canonicalKind"] !== null || audit["projectionCount"] !== 1 || audit["canonicalAtomCount"] !== null) return fail("MAPPING_INVALID", "special assignment/transition/probe/audit mapping drifted")
  if (!same(alignment["armTransitionProfiles"], armProfiles)) return fail("MAPPING_INVALID", "exact arm-transition profiles drifted")
  const blockSeal = alignment["blockSealCurrentContract"]
  if (!same(blockSeal, { canonicalKind: "block_seal", closureStatus: "INSUFFICIENT_FOR_PRODUCTION_BLOCK_CLOSURE", missingBindings: ["ADMITTED_BLOCK_ATOM_SET", "COMPLETE_NINE_CALL_LEDGER", "FIFTEEN_EVENT_CHRONOLOGY", "ACTUAL_CONTENT_BYTES", "PROVIDER_GATEWAY_LEDGER", "LIFECYCLE_PROJECTION_TO_CANONICAL_ATOM_BINDINGS", "DELAYED_AUDIT_RELEASE_CANONICAL_KIND_AND_AUTHORITY"], typedReferences: [{ maximum: 1, minimum: 1, role: "block", targetKinds: ["block_spec"] }, { maximum: 1, minimum: 1, role: "assignment", targetKinds: ["block_assignment"] }, { maximum: 4, minimum: 4, role: "probe-outcome", targetKinds: ["probe_outcome"] }] })) return fail("MAPPING_INVALID", "current underclosed block-seal contract drifted")
  if (!same(alignment["hardNonclaims"], nonclaims) || !same(alignment["postBlockCanonicalKinds"], ["block_analysis", "study_analysis"]) || alignment["expectedTerminal"] !== "ALIGNMENT_CONTRACT_VALIDATED_ACTUAL_ATOM_AND_BYTE_CLOSURE_REQUIRED_SOURCE_A_FORBIDDEN") return fail("NONCLAIM_INVALID", "bounded nonclaim or terminal fields drifted")
  return Either.right(Object.freeze({ eventCount: 15, artifactCount: 59, artifactKindCount: 27, generationCallCount: 9, claimFlags: Object.freeze({ canonicalAtomsBound: false, actualProductionBytesPresent: false, providerCallPresent: false, permitAdmissionOccurrenceLearningOrResult: false }) }))
}
