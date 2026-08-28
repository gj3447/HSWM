/**
 * Structural adapter from the immutable v1 lifecycle projection to the DNRD-5
 * v2 vocabulary.  The values here are adapter handles, not CanonicalAtomV2s:
 * they deliberately cannot stand in for content bytes, a journal, Permit, a
 * provider occurrence, or a scientific result.
 */
import { createHash } from "node:crypto"

import { Data, Either } from "effect"

import { canonicalAtomV2SchemaContentBytes } from "./canonical-atom-v2-content-bound.js"
import { decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { validateDnrd5LifecycleAtomAlignment } from "./canonical-atom-v2-dnrd5-lifecycle-alignment.js"
import {
  DNRD5_V2_SCHEMA_CONTENT_SHA256,
  makeDnrd5V2CanonicalSchema,
  type Dnrd5V2CanonicalAtomKind
} from "./canonical-atom-v2-dnrd5-v2-schema.js"

export const DNRD5_V2_LIFECYCLE_ADAPTER_VERSION =
  "hswm-dnrd5-v2-lifecycle-adapter/v1" as const
export const DNRD5_V1_LIFECYCLE_VECTOR_SHA256 =
  "179225541585267214a6cc5b358551c39597c66e546adf46bebad121550763cc" as const
export const DNRD5_V1_ALIGNMENT_VECTOR_SHA256 =
  "0e3ba180d8a3be3c2ed83ffe932965f8500862e02bdb07d953bf67a483f5c807" as const

export type Dnrd5V2LifecycleAdapterErrorCode =
  | "INPUT_BYTES_INVALID"
  | "SOURCE_VECTOR_INVALID"
  | "SCHEMA_INVALID"
  | "CONTRACT_INVALID"
  | "DIRECT_PROJECTION_INVALID"
  | "ASSIGNMENT_ADAPTER_INVALID"
  | "ARM_ADAPTER_INVALID"
  | "PROBE_ADAPTER_INVALID"
  | "AUDIT_ADAPTER_INVALID"
  | "SUPPORT_KIND_INVALID"
  | "NONCLAIM_INVALID"

export class Dnrd5V2LifecycleAdapterError extends Data.TaggedError("Dnrd5V2LifecycleAdapterError")<{
  readonly code: Dnrd5V2LifecycleAdapterErrorCode
  readonly detail: string
}> {}

const fail = (code: Dnrd5V2LifecycleAdapterErrorCode, detail: string) =>
  Either.left(new Dnrd5V2LifecycleAdapterError({ code, detail }))
const sha256 = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const nonempty = (value: unknown): value is string => typeof value === "string" && value.length > 0
const unique = (values: ReadonlyArray<string>) => new Set(values).size === values.length
const asRecord = (value: unknown): Record<string, unknown> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null

type Arm = "ACTIVE" | "OUTCOME_INDEPENDENT_SHAM" | "DELAYED_NO_CREDIT" | "EXACT_W0_ROLLBACK"
const ARMS: ReadonlyArray<Arm> = ["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK"]
const SPECIAL_KINDS = new Set(["ARM_ASSIGNMENT", "ARM_TRANSITION", "PROBE_RESPONSE_SEAL", "DELAYED_AUDIT_RELEASE"])
const SUPPORT_KINDS: ReadonlyArray<Dnrd5V2CanonicalAtomKind> = [
  "permit_policy", "authorization_decision", "capability_issuance", "revocation_status",
  "evaluator_capability", "audit_release_capability", "grant_snapshot", "revision_admission_decision",
  "rollback_decision", "capability_consumption", "evidence_seal_consumption",
  "rollback_transition_receipt", "restore_policy", "macro_disposition", "projection_policy",
  "block_evidence_manifest"
]

export interface Dnrd5V2DirectProjection {
  readonly lifecycleArtifactId: string
  readonly v2Kind: Dnrd5V2CanonicalAtomKind
  /** A future atom binding handle; this contract does not admit or resolve it. */
  readonly adapterRef: string
}
export interface Dnrd5V2AssignmentSlotAdapter {
  readonly arm: Arm
  readonly lifecycleArtifactId: string
  readonly assignmentAdapterRef: string
  readonly forkAdapterRef: string
}
export interface Dnrd5V2ArmTransitionAdapter {
  readonly arm: Arm
  readonly lifecycleArtifactId: string
  readonly validationAdapterRef: string
  readonly creditAdapterRef: string
  readonly stagingMainConsumptionAdapterRef: string | null
  readonly macroDispositionAdapterRef: string | null
  readonly revisionReceiptAdapterRef: string | null
  readonly restoreTransactionAdapterRef: string | null
  readonly restoreMainConsumptionAdapterRef: string | null
  readonly rollbackReceiptAdapterRef: string | null
}
export interface Dnrd5V2ProbeResponseAdapter {
  readonly arm: Arm
  readonly lifecycleArtifactId: string
  readonly behaviorProjectionAdapterRef: string
  readonly probeTrajectoryAdapterRef: string
}
export interface Dnrd5V2AuditReleaseAdapter {
  readonly lifecycleArtifactId: string
  readonly auditReleaseAdapterRef: string
  readonly hiddenOutcomeAdapterRef: string
  readonly escrowAdapterRef: string
  readonly probeTrajectoryAdapterRefs: ReadonlyArray<string>
  readonly probeOutcomeAdapterRefs: ReadonlyArray<string>
}
export interface Dnrd5V2LifecycleAdapterContract {
  readonly contractVersion: typeof DNRD5_V2_LIFECYCLE_ADAPTER_VERSION
  readonly lifecycleVectorSha256: typeof DNRD5_V1_LIFECYCLE_VECTOR_SHA256
  readonly alignmentVectorSha256: typeof DNRD5_V1_ALIGNMENT_VECTOR_SHA256
  readonly schemaContentSha256: typeof DNRD5_V2_SCHEMA_CONTENT_SHA256
  readonly directProjections: ReadonlyArray<Dnrd5V2DirectProjection>
  readonly assignmentSlots: ReadonlyArray<Dnrd5V2AssignmentSlotAdapter>
  readonly armTransitions: ReadonlyArray<Dnrd5V2ArmTransitionAdapter>
  readonly probeResponses: ReadonlyArray<Dnrd5V2ProbeResponseAdapter>
  readonly auditRelease: Dnrd5V2AuditReleaseAdapter
  readonly supportKinds: ReadonlyArray<Dnrd5V2CanonicalAtomKind>
  readonly hardNonclaims: ReadonlyArray<string>
}

const NONCLAIMS = [
  "NO_CANONICAL_ATOMS_OR_CONTENT_BYTES_ARE_PRESENT",
  "NO_RAW_PROVIDER_REQUEST_RESPONSE_OR_OCCURRENCE_IS_ESTABLISHED",
  "NO_PERMIT_ADMISSION_DURABILITY_CUSTODY_OR_RECEIPT_SEAL_IS_ESTABLISHED",
  "NO_CAUSAL_LEARNING_EFFICACY_OR_SCIENTIFIC_RESULT_IS_ESTABLISHED",
  "LIFECYCLE_AND_ADAPTER_HANDLES_ARE_BOUNDED_PROJECTIONS_NOT_HSWM_COGNITION"
]

type LifecycleArtifact = { readonly artifactId: string; readonly kind: string; readonly arm: Arm | null }
const sourceArtifacts = (bytes: Uint8Array): Either.Either<ReadonlyArray<LifecycleArtifact>, Dnrd5V2LifecycleAdapterError> => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) return fail("INPUT_BYTES_INVALID", "lifecycle vector is not strict canonical JSON")
  const root = asRecord(decoded.right)
  const lifecycle = asRecord(root?.["lifecycle"])
  const events = Array.isArray(lifecycle?.["events"]) ? lifecycle["events"] : null
  if (events === null) return fail("SOURCE_VECTOR_INVALID", "lifecycle event list is absent")
  const artifacts: LifecycleArtifact[] = []
  for (const event of events) {
    const rows = asRecord(event)
    const eventArtifacts = Array.isArray(rows?.["artifacts"]) ? rows["artifacts"] : null
    if (eventArtifacts === null) return fail("SOURCE_VECTOR_INVALID", "an event artifact list is absent")
    for (const raw of eventArtifacts) {
      const row = asRecord(raw)
      if (row === null || !nonempty(row["artifactId"]) || !nonempty(row["kind"]) || (row["arm"] !== null && !ARMS.includes(row["arm"] as Arm))) return fail("SOURCE_VECTOR_INVALID", "an artifact row is malformed")
      artifacts.push({ artifactId: row["artifactId"], kind: row["kind"], arm: row["arm"] as Arm | null })
    }
  }
  return artifacts.length === 59 ? Either.right(artifacts) : fail("SOURCE_VECTOR_INVALID", "v1 vector no longer has exactly 59 artifact rows")
}
const v2KindForDirect = (kind: string): Dnrd5V2CanonicalAtomKind =>
  (kind === "TRANSITION_RECEIPT" ? "revision_transition_receipt" : kind.toLowerCase()) as Dnrd5V2CanonicalAtomKind
const idsFor = (artifacts: ReadonlyArray<LifecycleArtifact>, kind: string): ReadonlyArray<LifecycleArtifact> => artifacts.filter((row) => row.kind === kind)
const exactArmRows = <T extends { readonly arm: Arm }>(rows: ReadonlyArray<T>) =>
  rows.length === 4 && equal(rows.map((row) => row.arm), ARMS)
const countHandles = (handles: ReadonlyArray<string>): ReadonlyMap<string, number> =>
  handles.reduce<Map<string, number>>((counts, handle) => {
    counts.set(handle, (counts.get(handle) ?? 0) + 1)
    return counts
  }, new Map())

/**
 * Checks only a complete structural v1-to-v2 projection contract.  It does not
 * decode a CanonicalAtomV2, obtain raw bytes, call a provider, or decide Permit.
 */
export const validateDnrd5V2LifecycleAdapter = (
  contract: Dnrd5V2LifecycleAdapterContract,
  alignmentBytes: Uint8Array,
  lifecycleBytes: Uint8Array
): Either.Either<{ readonly directProjectionCount: 46; readonly status: "STRUCTURAL_ADAPTER_VALIDATED_NOT_OCCURRENCE" }, Dnrd5V2LifecycleAdapterError> => {
  if (sha256(alignmentBytes) !== DNRD5_V1_ALIGNMENT_VECTOR_SHA256 || sha256(lifecycleBytes) !== DNRD5_V1_LIFECYCLE_VECTOR_SHA256) return fail("INPUT_BYTES_INVALID", "the immutable v1 source bytes do not match their pinned hashes")
  if (Either.isLeft(validateDnrd5LifecycleAtomAlignment(alignmentBytes, lifecycleBytes))) return fail("SOURCE_VECTOR_INVALID", "v1 lifecycle/alignment evidence no longer validates")
  const schemaBytes = canonicalAtomV2SchemaContentBytes(makeDnrd5V2CanonicalSchema())
  if (Either.isLeft(schemaBytes) || sha256(schemaBytes.right) !== DNRD5_V2_SCHEMA_CONTENT_SHA256) return fail("SCHEMA_INVALID", "the exact v2 schema bytes do not validate")
  if (contract.contractVersion !== DNRD5_V2_LIFECYCLE_ADAPTER_VERSION || contract.lifecycleVectorSha256 !== DNRD5_V1_LIFECYCLE_VECTOR_SHA256 || contract.alignmentVectorSha256 !== DNRD5_V1_ALIGNMENT_VECTOR_SHA256 || contract.schemaContentSha256 !== DNRD5_V2_SCHEMA_CONTENT_SHA256) return fail("CONTRACT_INVALID", "contract identity/hash binding drifted")
  const artifacts = sourceArtifacts(lifecycleBytes)
  if (Either.isLeft(artifacts)) return fail(artifacts.left.code, artifacts.left.detail)
  const directExpected = artifacts.right.filter((row) => !SPECIAL_KINDS.has(row.kind))
  if (contract.directProjections.length !== 46 || !equal(contract.directProjections.map(({ lifecycleArtifactId, v2Kind }) => ({ lifecycleArtifactId, v2Kind })), directExpected.map((row) => ({ lifecycleArtifactId: row.artifactId, v2Kind: v2KindForDirect(row.kind) }))) || !contract.directProjections.every(({ adapterRef }) => nonempty(adapterRef)) || !unique(contract.directProjections.map(({ adapterRef }) => adapterRef))) return fail("DIRECT_PROJECTION_INVALID", "the exact 46 direct v1 rows are not projected once to their v2 kinds")
  const directRef = (kind: string, arm?: Arm | null): string | undefined => {
    const row = directExpected.find((candidate) => candidate.kind === kind && (arm === undefined || candidate.arm === arm))
    return row === undefined ? undefined : contract.directProjections.find(({ lifecycleArtifactId }) => lifecycleArtifactId === row.artifactId)?.adapterRef
  }
  const assignmentRows = idsFor(artifacts.right, "ARM_ASSIGNMENT")
  const forkRows = idsFor(artifacts.right, "FORK_INCIDENCE")
  const directRefByArtifactId = new Map(contract.directProjections.map(({ lifecycleArtifactId, adapterRef }) => [lifecycleArtifactId, adapterRef]))
  if (!exactArmRows(contract.assignmentSlots) || !equal(contract.assignmentSlots.map(({ lifecycleArtifactId, arm }) => ({ lifecycleArtifactId, arm })), assignmentRows.map(({ artifactId, arm }) => ({ lifecycleArtifactId: artifactId, arm }))) || !contract.assignmentSlots.every(({ assignmentAdapterRef, forkAdapterRef }) => nonempty(assignmentAdapterRef) && nonempty(forkAdapterRef)) || !unique(contract.assignmentSlots.map(({ forkAdapterRef }) => forkAdapterRef)) || contract.assignmentSlots[0]?.assignmentAdapterRef !== contract.assignmentSlots[1]?.assignmentAdapterRef || contract.assignmentSlots[1]?.assignmentAdapterRef !== contract.assignmentSlots[2]?.assignmentAdapterRef || contract.assignmentSlots[2]?.assignmentAdapterRef !== contract.assignmentSlots[3]?.assignmentAdapterRef || !equal(contract.assignmentSlots.map(({ forkAdapterRef }) => forkAdapterRef), forkRows.map(({ artifactId }) => directRefByArtifactId.get(artifactId)))) return fail("ASSIGNMENT_ADAPTER_INVALID", "four slots must bind one assignment handle and their four direct fork projections")
  const armRows = idsFor(artifacts.right, "ARM_TRANSITION")
  if (!exactArmRows(contract.armTransitions) || !equal(contract.armTransitions.map(({ lifecycleArtifactId, arm }) => ({ lifecycleArtifactId, arm })), armRows.map(({ artifactId, arm }) => ({ lifecycleArtifactId: artifactId, arm })))) return fail("ARM_ADAPTER_INVALID", "four arm transition rows/arms drifted")
  const validArm = (row: Dnrd5V2ArmTransitionAdapter): boolean => {
    if (!nonempty(row.validationAdapterRef) || !nonempty(row.creditAdapterRef)) return false
    if (row.arm === "DELAYED_NO_CREDIT") return [row.stagingMainConsumptionAdapterRef, row.macroDispositionAdapterRef, row.revisionReceiptAdapterRef, row.restoreTransactionAdapterRef, row.restoreMainConsumptionAdapterRef, row.rollbackReceiptAdapterRef].every((value) => value === null)
    if (row.arm !== "EXACT_W0_ROLLBACK") return nonempty(row.stagingMainConsumptionAdapterRef) && nonempty(row.macroDispositionAdapterRef) && nonempty(row.revisionReceiptAdapterRef) && row.restoreTransactionAdapterRef === null && row.restoreMainConsumptionAdapterRef === null && row.rollbackReceiptAdapterRef === null
    return [row.stagingMainConsumptionAdapterRef, row.macroDispositionAdapterRef, row.revisionReceiptAdapterRef, row.restoreTransactionAdapterRef, row.restoreMainConsumptionAdapterRef, row.rollbackReceiptAdapterRef].every(nonempty)
  }
  const revisionReceipts = contract.armTransitions.flatMap((row) => row.revisionReceiptAdapterRef === null ? [] : [row.revisionReceiptAdapterRef])
  if (!contract.armTransitions.every(validArm) || revisionReceipts.length !== 3 || !unique(revisionReceipts) || !contract.armTransitions.every((row) => row.validationAdapterRef === directRef("CANDIDATE_VALIDATION", row.arm) && row.creditAdapterRef === directRef("CREDIT_DECISION", row.arm) && (row.arm === "DELAYED_NO_CREDIT" || row.revisionReceiptAdapterRef === directRef("TRANSITION_RECEIPT", row.arm))) || contract.armTransitions.find(({ arm }) => arm === "EXACT_W0_ROLLBACK")?.restoreTransactionAdapterRef !== directRef("RESTORE_TRANSACTION") || !unique(contract.armTransitions.filter(({ arm }) => arm === "EXACT_W0_ROLLBACK").flatMap((row) => [row.restoreTransactionAdapterRef!, row.restoreMainConsumptionAdapterRef!, row.rollbackReceiptAdapterRef!]))) return fail("ARM_ADAPTER_INVALID", "arm adapters must cross-link direct validation/credit/receipt/restore projections and preserve the rollback adapter")
  const probeRows = idsFor(artifacts.right, "PROBE_RESPONSE_SEAL")
  if (!exactArmRows(contract.probeResponses) || !equal(contract.probeResponses.map(({ lifecycleArtifactId, arm }) => ({ lifecycleArtifactId, arm })), probeRows.map(({ artifactId, arm }) => ({ lifecycleArtifactId: artifactId, arm }))) || !contract.probeResponses.every(({ arm, behaviorProjectionAdapterRef, probeTrajectoryAdapterRef }) => nonempty(behaviorProjectionAdapterRef) && nonempty(probeTrajectoryAdapterRef) && behaviorProjectionAdapterRef === directRef("BEHAVIOR_PROJECTION", arm)) || !unique(contract.probeResponses.map(({ probeTrajectoryAdapterRef }) => probeTrajectoryAdapterRef))) return fail("PROBE_ADAPTER_INVALID", "four probe responses must cross-link direct behavior projections and distinct probe trajectories")
  const auditRows = idsFor(artifacts.right, "DELAYED_AUDIT_RELEASE")
  const audit = contract.auditRelease
  if (auditRows.length !== 1 || audit.lifecycleArtifactId !== auditRows[0]?.artifactId || ![audit.auditReleaseAdapterRef, audit.hiddenOutcomeAdapterRef, audit.escrowAdapterRef].every(nonempty) || audit.hiddenOutcomeAdapterRef !== directRef("HIDDEN_OUTCOME") || audit.escrowAdapterRef !== directRef("OUTCOME_CREDIT_ESCROW") || audit.probeTrajectoryAdapterRefs.length !== 4 || audit.probeOutcomeAdapterRefs.length !== 4 || !audit.probeTrajectoryAdapterRefs.every(nonempty) || !audit.probeOutcomeAdapterRefs.every(nonempty) || !unique(audit.probeTrajectoryAdapterRefs) || !unique(audit.probeOutcomeAdapterRefs) || !equal(audit.probeTrajectoryAdapterRefs, contract.probeResponses.map(({ probeTrajectoryAdapterRef }) => probeTrajectoryAdapterRef)) || !equal(audit.probeOutcomeAdapterRefs, ARMS.map((arm) => directRef("PROBE_OUTCOME", arm)))) return fail("AUDIT_ADAPTER_INVALID", "audit release must cross-link direct outcome/escrow/probe-outcome and all adapted probes")
  const derivedSupportKinds = makeDnrd5V2CanonicalSchema().kinds
    .map(({ kind }) => kind.slice("hswm:dnrd5:v2:".length) as Dnrd5V2CanonicalAtomKind)
    .filter((kind) => !new Set([...contract.directProjections.map(({ v2Kind }) => v2Kind), "block_assignment", "probe_trajectory", "audit_release", "block_analysis", "study_analysis"]).has(kind))
  if (!equal(derivedSupportKinds, SUPPORT_KINDS) || !equal(contract.supportKinds, derivedSupportKinds)) return fail("SUPPORT_KIND_INVALID", "support kinds must be derived exactly from the v2 schema closure, not merely listed")
  const logicalHandles = [
    ...contract.directProjections.map(({ adapterRef }) => adapterRef),
    ...contract.assignmentSlots.flatMap(({ assignmentAdapterRef, forkAdapterRef }) => [assignmentAdapterRef, forkAdapterRef]),
    ...contract.armTransitions.flatMap((row) => [row.validationAdapterRef, row.creditAdapterRef, row.stagingMainConsumptionAdapterRef, row.macroDispositionAdapterRef, row.revisionReceiptAdapterRef, row.restoreTransactionAdapterRef, row.restoreMainConsumptionAdapterRef, row.rollbackReceiptAdapterRef].filter(nonempty)),
    ...contract.probeResponses.flatMap(({ behaviorProjectionAdapterRef, probeTrajectoryAdapterRef }) => [behaviorProjectionAdapterRef, probeTrajectoryAdapterRef]),
    audit.auditReleaseAdapterRef, audit.hiddenOutcomeAdapterRef, audit.escrowAdapterRef, ...audit.probeTrajectoryAdapterRefs, ...audit.probeOutcomeAdapterRefs
  ]
  const expectedCounts = new Map(logicalHandles.map((handle) => [handle, 1]))
  const repeat = (handle: string, count: number) => expectedCounts.set(handle, count)
  repeat(contract.assignmentSlots[0]!.assignmentAdapterRef, 4)
  for (const { forkAdapterRef } of contract.assignmentSlots) repeat(forkAdapterRef, 2)
  for (const row of contract.armTransitions) {
    repeat(row.validationAdapterRef, 2); repeat(row.creditAdapterRef, 2)
    if (row.revisionReceiptAdapterRef !== null) repeat(row.revisionReceiptAdapterRef, 2)
    if (row.restoreTransactionAdapterRef !== null) repeat(row.restoreTransactionAdapterRef, 2)
  }
  for (const { behaviorProjectionAdapterRef, probeTrajectoryAdapterRef } of contract.probeResponses) { repeat(behaviorProjectionAdapterRef, 2); repeat(probeTrajectoryAdapterRef, 2) }
  repeat(audit.hiddenOutcomeAdapterRef, 2); repeat(audit.escrowAdapterRef, 2)
  for (const handle of audit.probeOutcomeAdapterRefs) repeat(handle, 2)
  const actualCounts = countHandles(logicalHandles)
  if (actualCounts.size !== expectedCounts.size || [...actualCounts.entries()].some(([handle, count]) => expectedCounts.get(handle) !== count)) return fail("CONTRACT_INVALID", "logical adapter handles must be globally unique except declared structural reuses")
  if (!equal(contract.hardNonclaims, NONCLAIMS)) return fail("NONCLAIM_INVALID", "structural adapter nonclaims drifted")
  return Either.right({ directProjectionCount: 46, status: "STRUCTURAL_ADAPTER_VALIDATED_NOT_OCCURRENCE" })
}
