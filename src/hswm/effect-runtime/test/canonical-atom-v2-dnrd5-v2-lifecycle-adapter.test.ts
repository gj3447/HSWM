import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  DNRD5_V1_ALIGNMENT_VECTOR_SHA256,
  DNRD5_V1_LIFECYCLE_VECTOR_SHA256,
  DNRD5_V2_LIFECYCLE_ADAPTER_VERSION,
  validateDnrd5V2LifecycleAdapter,
  type Dnrd5V2LifecycleAdapterContract
} from "../src/canonical-atom-v2-dnrd5-v2-lifecycle-adapter.js"
import { DNRD5_V2_SCHEMA_CONTENT_SHA256 } from "../src/canonical-atom-v2-dnrd5-v2-schema.js"

const alignmentBytes = new Uint8Array(readFileSync(new URL("../../../../_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json", import.meta.url)))
const lifecycleBytes = new Uint8Array(readFileSync(new URL("../../../../_research/dnrd5/vectors/lifecycle_contract_v1.json", import.meta.url)))
const lifecycle = JSON.parse(new TextDecoder().decode(lifecycleBytes)) as { lifecycle: { events: Array<{ artifacts: Array<{ artifactId: string; kind: string; arm: any }> }> } }
const artifacts = lifecycle.lifecycle.events.flatMap(({ artifacts }) => artifacts)
const rows = (kind: string) => artifacts.filter((row) => row.kind === kind)
const ref = (value: string) => `adapter:${value}`

const contract = (): Dnrd5V2LifecycleAdapterContract => {
  const direct = artifacts.filter(({ kind }) => !["ARM_ASSIGNMENT", "ARM_TRANSITION", "PROBE_RESPONSE_SEAL", "DELAYED_AUDIT_RELEASE"].includes(kind))
  const directProjections = direct.map(({ artifactId, kind }) => ({ lifecycleArtifactId: artifactId, v2Kind: (kind === "TRANSITION_RECEIPT" ? "revision_transition_receipt" : kind.toLowerCase()) as any, adapterRef: ref(artifactId) }))
  const directRef = (kind: string, arm?: any) => directProjections.find(({ lifecycleArtifactId }) => {
    const row = artifacts.find(({ artifactId }) => artifactId === lifecycleArtifactId)
    return row?.kind === kind && (arm === undefined || row.arm === arm)
  })!.adapterRef
  const forkRefs = rows("FORK_INCIDENCE").map(({ artifactId }) =>
    directProjections.find(({ lifecycleArtifactId }) => lifecycleArtifactId === artifactId)!.adapterRef
  )
  const transition = rows("ARM_TRANSITION")
  const probes = rows("PROBE_RESPONSE_SEAL")
  const trajectories = probes.map(({ arm }) => ref(`probe-trajectory:${arm}`))
  return {
    contractVersion: DNRD5_V2_LIFECYCLE_ADAPTER_VERSION,
    lifecycleVectorSha256: DNRD5_V1_LIFECYCLE_VECTOR_SHA256,
    alignmentVectorSha256: DNRD5_V1_ALIGNMENT_VECTOR_SHA256,
    schemaContentSha256: DNRD5_V2_SCHEMA_CONTENT_SHA256,
    directProjections,
    assignmentSlots: rows("ARM_ASSIGNMENT").map(({ artifactId, arm }, index) => ({ arm, lifecycleArtifactId: artifactId, assignmentAdapterRef: ref("one-assignment"), forkAdapterRef: forkRefs[index]! })),
    armTransitions: transition.map(({ artifactId, arm }) => ({
      arm, lifecycleArtifactId: artifactId, validationAdapterRef: directRef("CANDIDATE_VALIDATION", arm), creditAdapterRef: directRef("CREDIT_DECISION", arm),
      stagingMainConsumptionAdapterRef: arm === "DELAYED_NO_CREDIT" ? null : ref(`staging-consumption:${arm}`),
      macroDispositionAdapterRef: arm === "DELAYED_NO_CREDIT" ? null : ref(`macro:${arm}`),
      revisionReceiptAdapterRef: arm === "DELAYED_NO_CREDIT" ? null : directRef("TRANSITION_RECEIPT", arm),
      restoreTransactionAdapterRef: arm === "EXACT_W0_ROLLBACK" ? directRef("RESTORE_TRANSACTION") : null,
      restoreMainConsumptionAdapterRef: arm === "EXACT_W0_ROLLBACK" ? ref("restore-consumption") : null,
      rollbackReceiptAdapterRef: arm === "EXACT_W0_ROLLBACK" ? ref("rollback-receipt") : null
    })),
    probeResponses: probes.map(({ artifactId, arm }, index) => ({ arm, lifecycleArtifactId: artifactId, behaviorProjectionAdapterRef: directRef("BEHAVIOR_PROJECTION", arm), probeTrajectoryAdapterRef: trajectories[index]! })),
    auditRelease: { lifecycleArtifactId: rows("DELAYED_AUDIT_RELEASE")[0]!.artifactId, auditReleaseAdapterRef: ref("audit-release"), hiddenOutcomeAdapterRef: directRef("HIDDEN_OUTCOME"), escrowAdapterRef: directRef("OUTCOME_CREDIT_ESCROW"), probeTrajectoryAdapterRefs: trajectories, probeOutcomeAdapterRefs: rows("PROBE_OUTCOME").map(({ arm }) => directRef("PROBE_OUTCOME", arm)) },
    supportKinds: ["permit_policy", "authorization_decision", "capability_issuance", "revocation_status", "evaluator_capability", "audit_release_capability", "grant_snapshot", "revision_admission_decision", "rollback_decision", "capability_consumption", "evidence_seal_consumption", "rollback_transition_receipt", "restore_policy", "macro_disposition", "projection_policy", "block_evidence_manifest"],
    hardNonclaims: ["NO_CANONICAL_ATOMS_OR_CONTENT_BYTES_ARE_PRESENT", "NO_RAW_PROVIDER_REQUEST_RESPONSE_OR_OCCURRENCE_IS_ESTABLISHED", "NO_PERMIT_ADMISSION_DURABILITY_CUSTODY_OR_RECEIPT_SEAL_IS_ESTABLISHED", "NO_CAUSAL_LEARNING_EFFICACY_OR_SCIENTIFIC_RESULT_IS_ESTABLISHED", "LIFECYCLE_AND_ADAPTER_HANDLES_ARE_BOUNDED_PROJECTIONS_NOT_HSWM_COGNITION"]
  }
}

const expectCode = (value: ReturnType<typeof validateDnrd5V2LifecycleAdapter>, code: string) => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isLeft(value)) expect(value.left.code).toBe(code)
}

it("binds exact v1 lifecycle/alignment bytes to v2's 46 direct structural projections", () => {
  const result = validateDnrd5V2LifecycleAdapter(contract(), alignmentBytes, lifecycleBytes)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) expect(result.right).toEqual({ directProjectionCount: 46, status: "STRUCTURAL_ADAPTER_VALIDATED_NOT_OCCURRENCE" })
})

it("fails closed for every declared direct cross-link and global handle reuse", () => {
  const baseFork = contract(); const repeatedFork = { ...baseFork, assignmentSlots: baseFork.assignmentSlots.map((row) => ({ ...row, forkAdapterRef: ref("fork:reused") })) }
  expectCode(validateDnrd5V2LifecycleAdapter(repeatedFork, alignmentBytes, lifecycleBytes), "ASSIGNMENT_ADAPTER_INVALID")
  const baseValidation = contract(); const wrongValidation = { ...baseValidation, armTransitions: baseValidation.armTransitions.map((row) => row.arm === "ACTIVE" ? { ...row, validationAdapterRef: ref("wrong-validation") } : row) }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongValidation, alignmentBytes, lifecycleBytes), "ARM_ADAPTER_INVALID")
  const baseCredit = contract(); const wrongCredit = { ...baseCredit, armTransitions: baseCredit.armTransitions.map((row) => row.arm === "ACTIVE" ? { ...row, creditAdapterRef: ref("wrong-credit") } : row) }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongCredit, alignmentBytes, lifecycleBytes), "ARM_ADAPTER_INVALID")
  const baseReceipt = contract(); const wrongRevisionReceipt = { ...baseReceipt, armTransitions: baseReceipt.armTransitions.map((row) => row.arm === "ACTIVE" ? { ...row, revisionReceiptAdapterRef: ref("wrong-revision-receipt") } : row) }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongRevisionReceipt, alignmentBytes, lifecycleBytes), "ARM_ADAPTER_INVALID")
  const baseRestore = contract(); const wrongRestore = { ...baseRestore, armTransitions: baseRestore.armTransitions.map((row) => row.arm === "EXACT_W0_ROLLBACK" ? { ...row, restoreTransactionAdapterRef: ref("wrong-restore") } : row) }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongRestore, alignmentBytes, lifecycleBytes), "ARM_ADAPTER_INVALID")
  const baseRollback = contract(); const noRollbackReceipt = { ...baseRollback, armTransitions: baseRollback.armTransitions.map((row) => row.arm === "EXACT_W0_ROLLBACK" ? { ...row, rollbackReceiptAdapterRef: null } : row) }
  expectCode(validateDnrd5V2LifecycleAdapter(noRollbackReceipt, alignmentBytes, lifecycleBytes), "ARM_ADAPTER_INVALID")
  const baseBehavior = contract(); const wrongBehavior = { ...baseBehavior, probeResponses: baseBehavior.probeResponses.map((row) => row.arm === "ACTIVE" ? { ...row, behaviorProjectionAdapterRef: ref("wrong-projection") } : row) }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongBehavior, alignmentBytes, lifecycleBytes), "PROBE_ADAPTER_INVALID")
  const baseProbe = contract(); const wrongProbe = { ...baseProbe, auditRelease: { ...baseProbe.auditRelease, probeTrajectoryAdapterRefs: [...baseProbe.auditRelease.probeTrajectoryAdapterRefs].reverse() } }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongProbe, alignmentBytes, lifecycleBytes), "AUDIT_ADAPTER_INVALID")
  const baseHidden = contract(); const wrongHidden = { ...baseHidden, auditRelease: { ...baseHidden.auditRelease, hiddenOutcomeAdapterRef: ref("wrong-hidden-outcome") } }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongHidden, alignmentBytes, lifecycleBytes), "AUDIT_ADAPTER_INVALID")
  const baseEscrow = contract(); const wrongEscrow = { ...baseEscrow, auditRelease: { ...baseEscrow.auditRelease, escrowAdapterRef: ref("wrong-escrow") } }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongEscrow, alignmentBytes, lifecycleBytes), "AUDIT_ADAPTER_INVALID")
  const baseOutcome = contract(); const wrongOutcome = { ...baseOutcome, auditRelease: { ...baseOutcome.auditRelease, probeOutcomeAdapterRefs: [...baseOutcome.auditRelease.probeOutcomeAdapterRefs].reverse() } }
  expectCode(validateDnrd5V2LifecycleAdapter(wrongOutcome, alignmentBytes, lifecycleBytes), "AUDIT_ADAPTER_INVALID")
  const baseGlobal = contract(); const duplicatedLogicalHandle = { ...baseGlobal, auditRelease: { ...baseGlobal.auditRelease, auditReleaseAdapterRef: baseGlobal.armTransitions[0]!.macroDispositionAdapterRef! } }
  expectCode(validateDnrd5V2LifecycleAdapter(duplicatedLogicalHandle, alignmentBytes, lifecycleBytes), "CONTRACT_INVALID")
  const baseSupport = contract(); const missingSupport = { ...baseSupport, supportKinds: baseSupport.supportKinds.slice(1) }
  expectCode(validateDnrd5V2LifecycleAdapter(missingSupport, alignmentBytes, lifecycleBytes), "SUPPORT_KIND_INVALID")
  const sourceDrift = Uint8Array.from([...lifecycleBytes, 0x20])
  expectCode(validateDnrd5V2LifecycleAdapter(contract(), alignmentBytes, sourceDrift), "INPUT_BYTES_INVALID")
})
