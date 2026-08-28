import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  DNRD5_V2_EFFECT_PROTOCOL_BOUNDARY,
  DNRD5_V2_EFFECT_PROTOCOL_V1,
  classifyDnrd5V2CrashPrefix,
  validateDnrd5V2CompleteEffectProtocol,
  type Dnrd5V2CrashPrefix,
  type Dnrd5V2EffectReceiptTrace
} from "../src/canonical-atom-v2-dnrd5-v2-effect-protocol.js"
import type { Dnrd5V2AtomicBatchChronology } from "../src/canonical-atom-v2-dnrd5-v2-batch-chronology.js"
import { deriveDnrd5V2PostcommitReceiptIdentity } from "../src/canonical-atom-v2-dnrd5-v2-receipt-identity.js"

const sha = (letter: string) => letter.repeat(64)
const key = (atomUid: string) =>
  `hswm:dnrd5:causal-macroplasticity:v2|lineage:dnrd5:v2:protocol-test|${atomUid}|0`
const topology = (keys: ReadonlyArray<string>): Dnrd5V2AtomicBatchChronology => ({
  topologyAtomKeyIds: keys,
  dependencyEdges: [],
  topologySha256: sha("a"),
  nextState: {} as Dnrd5V2AtomicBatchChronology["nextState"]
})

const prefix = (arm: "ACTIVE" | "OUTCOME_INDEPENDENT_SHAM" | "EXACT_W0_ROLLBACK", transitionKind: "ADMIT" | "RESTORE", suffix: string): Dnrd5V2CrashPrefix => {
  const consumption = key(`consumption:${suffix}`)
  const effect = key(`${transitionKind === "ADMIT" ? "disposition" : "restore"}:${suffix}`)
  return {
    arm, transitionKind, blockId: "block:1", transitionId: `transition:${suffix}`,
    decisionAtomKeyId: key(`decision:${suffix}`),
    effectConsumptionAtomKeyId: consumption, effectAtomKeyId: effect,
    effectBatch: {
      topology: topology([consumption, effect]), writeAtomKeyIds: [consumption, effect],
      writeKinds: transitionKind === "ADMIT"
        ? ["capability_consumption", "macro_disposition"]
        : ["capability_consumption", "restore_transaction"]
    },
    recoveredEffect: {
      journalLineageId: "journal:one", recordDescriptorSha256: sha(suffix), commitIdentity: `transition:${suffix}`,
      priorRevision: suffix === "a" ? 0 : suffix === "b" ? 1 : suffix === "c" ? 2 : 3,
      nextRevision: suffix === "a" ? 1 : suffix === "b" ? 2 : suffix === "c" ? 3 : 4,
      priorStateSha256: sha("d"), nextStateSha256: sha("e"), journalHeadSha256: sha("f")
    }
  }
}

const sealed = (crash: Dnrd5V2CrashPrefix): Dnrd5V2EffectReceiptTrace => {
  const classified = classifyDnrd5V2CrashPrefix({
    _tag: "Dnrd5V2CrashPrefixProtocol", contractVersion: DNRD5_V2_EFFECT_PROTOCOL_V1, prefix: crash
  })
  if (Either.isLeft(classified)) throw new Error(classified.left.detail)
  const evidence = key(`evidence:${crash.transitionId}`)
  const receiptUid = `receipt:${classified.right.deterministicReceiptIdentity}`
  const receipt = key(receiptUid)
  return {
    ...crash,
    receiptAtomKeyId: receipt,
    receiptAtomUid: receiptUid,
    evidenceSealConsumptionAtomKeyId: evidence,
    receiptBatch: {
      topology: topology([evidence, receipt]), writeAtomKeyIds: [evidence, receipt],
      writeKinds: crash.transitionKind === "ADMIT"
        ? ["evidence_seal_consumption", "revision_transition_receipt"]
        : ["evidence_seal_consumption", "rollback_transition_receipt"]
    },
    receiptEffectRecordDescriptorSha256: crash.recoveredEffect.recordDescriptorSha256,
    receiptEffectCommitIdentity: crash.recoveredEffect.commitIdentity,
    receiptJournalLineageId: crash.recoveredEffect.journalLineageId,
    receiptPriorRevision: crash.recoveredEffect.priorRevision,
    receiptNextRevision: crash.recoveredEffect.nextRevision,
    receiptPriorStateSha256: crash.recoveredEffect.priorStateSha256,
    receiptNextStateSha256: crash.recoveredEffect.nextStateSha256,
    receiptJournalHeadSha256: crash.recoveredEffect.journalHeadSha256,
    receiptIdentity: classified.right.deterministicReceiptIdentity
  }
}

const complete = () => {
  const active = sealed(prefix("ACTIVE", "ADMIT", "a"))
  const sham = sealed(prefix("OUTCOME_INDEPENDENT_SHAM", "ADMIT", "b"))
  const staging = sealed(prefix("EXACT_W0_ROLLBACK", "ADMIT", "c"))
  const restore = sealed(prefix("EXACT_W0_ROLLBACK", "RESTORE", "f"))
  return {
    _tag: "Dnrd5V2CompleteEffectProtocol" as const,
    contractVersion: DNRD5_V2_EFFECT_PROTOCOL_V1,
    blockId: "block:1",
    effects: [active, sham, staging, restore],
    rollbackDecisionStagingReceiptAtomKeyId: staging.receiptAtomKeyId,
    terminal: "DECLARED_TRACE_CONSISTENT_ONLY" as const
  }
}

it("requires the exact 3 admission + 1 restore receipt closure before a probe terminal", () => {
  const result = validateDnrd5V2CompleteEffectProtocol(complete())
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right.revisionReceiptCount).toBe(3)
    expect(result.right.rollbackReceiptCount).toBe(1)
  }
})

it("binds a receipt to its preceding effect journal record and rejects replay or staging-order changes", () => {
  const changedDescriptor = complete()
  changedDescriptor.effects[0] = { ...changedDescriptor.effects[0]!, receiptEffectRecordDescriptorSha256: sha("0") }
  const descriptor = validateDnrd5V2CompleteEffectProtocol(changedDescriptor)
  expect(Either.isLeft(descriptor)).toBe(true)
  if (Either.isLeft(descriptor)) expect(descriptor.left.code).toBe("BINDING_MISMATCH")

  const replayed = complete()
  const duplicateReceipt = replayed.effects[0]!.receiptAtomKeyId
  const duplicatedEvidence = replayed.effects[1]!.evidenceSealConsumptionAtomKeyId
  replayed.effects[1] = {
    ...replayed.effects[1]!, receiptAtomKeyId: duplicateReceipt,
    receiptBatch: {
      ...replayed.effects[1]!.receiptBatch,
      topology: topology([duplicatedEvidence, duplicateReceipt]),
      writeAtomKeyIds: [duplicatedEvidence, duplicateReceipt]
    }
  }
  const replay = validateDnrd5V2CompleteEffectProtocol(replayed)
  expect(Either.isLeft(replay)).toBe(true)
  if (Either.isLeft(replay)) expect(replay.left.code).toBe("REPLAY_INVALID")

  const misordered = complete()
  misordered.rollbackDecisionStagingReceiptAtomKeyId = misordered.effects[0]!.receiptAtomKeyId
  const order = validateDnrd5V2CompleteEffectProtocol(misordered)
  expect(Either.isLeft(order)).toBe(true)
  if (Either.isLeft(order)) expect(order.left.code).toBe("PHASE_INVALID")

  const unsafeTerminal = { ...complete(), terminal: "PROBE_READY" } as unknown as ReturnType<typeof complete>
  const terminal = validateDnrd5V2CompleteEffectProtocol(unsafeTerminal)
  expect(Either.isLeft(terminal)).toBe(true)
  if (Either.isLeft(terminal)) expect(terminal.left.code).toBe("TERMINAL_FORBIDDEN")
})

it("classifies an effect-committed receipt-missing crash as recovery-only with a deterministic identity", () => {
  const crash = prefix("ACTIVE", "ADMIT", "a")
  const first = classifyDnrd5V2CrashPrefix({ _tag: "Dnrd5V2CrashPrefixProtocol", contractVersion: DNRD5_V2_EFFECT_PROTOCOL_V1, prefix: crash })
  const second = classifyDnrd5V2CrashPrefix({ _tag: "Dnrd5V2CrashPrefixProtocol", contractVersion: DNRD5_V2_EFFECT_PROTOCOL_V1, prefix: crash })
  const shared = deriveDnrd5V2PostcommitReceiptIdentity({ effectRecordDescriptorSha256: crash.recoveredEffect.recordDescriptorSha256, journalLineageId: crash.recoveredEffect.journalLineageId, transitionId: crash.transitionId, decisionAtomKeyId: crash.decisionAtomKeyId, effectConsumptionAtomKeyId: crash.effectConsumptionAtomKeyId, effectAtomKeyId: crash.effectAtomKeyId })
  expect(Either.isRight(first)).toBe(true)
  expect(Either.isRight(second)).toBe(true)
  expect(Either.isRight(shared)).toBe(true)
  if (Either.isRight(first) && Either.isRight(second) && Either.isRight(shared)) {
    expect(first.right.status).toBe("DECLARED_EFFECT_RECORD_PRESENT_RECEIPT_RECOVERY_ONLY_NOT_DURABILITY_VERIFIED")
    expect(first.right.deterministicReceiptIdentity).toBe(second.right.deterministicReceiptIdentity)
    expect(first.right.deterministicReceiptIdentity).toBe(shared.right)
  }
  expect(DNRD5_V2_EFFECT_PROTOCOL_BOUNDARY.doesNotValidate).toContain("DURABLE_RECOVERY_IMPLEMENTATION")
})

it("rejects missing/extra/delayed effects and recursive receipt grammar", () => {
  const missing = complete()
  missing.effects = missing.effects.slice(0, 3)
  const missingResult = validateDnrd5V2CompleteEffectProtocol(missing)
  expect(Either.isLeft(missingResult)).toBe(true)
  if (Either.isLeft(missingResult)) expect(missingResult.left.code).toBe("CARDINALITY_INVALID")

  const extra = complete()
  extra.effects = [...extra.effects, extra.effects[0]!]
  const extraResult = validateDnrd5V2CompleteEffectProtocol(extra)
  expect(Either.isLeft(extraResult)).toBe(true)
  if (Either.isLeft(extraResult)) expect(extraResult.left.code).toBe("CARDINALITY_INVALID")

  const delayed = complete()
  delayed.effects[0] = { ...delayed.effects[0]!, arm: "DELAYED_NO_CREDIT" as never }
  const delayedResult = validateDnrd5V2CompleteEffectProtocol(delayed)
  expect(Either.isLeft(delayedResult)).toBe(true)
  if (Either.isLeft(delayedResult)) expect(delayedResult.left.code).toBe("CARDINALITY_INVALID")

  const recursive = complete()
  recursive.effects[0] = {
    ...recursive.effects[0]!,
    receiptBatch: { ...recursive.effects[0]!.receiptBatch, writeKinds: ["evidence_seal_consumption", "revision_transition_receipt", "revision_transition_receipt"] }
  }
  const recursiveResult = validateDnrd5V2CompleteEffectProtocol(recursive)
  expect(Either.isLeft(recursiveResult)).toBe(true)
  if (Either.isLeft(recursiveResult)) expect(recursiveResult.left.code).toBe("BATCH_INVALID")
})
