import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION,
  HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_V1,
  simulateG0TestOnlyOperator
} from "../src/g0-test-only-operator-simulation.js"

const descriptor = (name: string, value: number) => Object.freeze({
  name,
  sha256: value.toString(16).padStart(64, "0"),
  mediaType: "application/vnd.hswm.content-descriptor+json" as const
})

const input = () => Object.freeze({
  occurrenceUid: "simulated-g0-001",
  occurrenceTimeoutSeconds: 600,
  existingOccurrenceUids: [],
  simulatedOperatorId: "simulated-operator-a",
  simulatedCustodianId: "simulated-custodian-b",
  scenario: "HAPPY_PATH" as const,
  wormClaimReceipt: descriptor("candidate_worm_claim_receipt", 1),
  registrationEvidence: descriptor("registration_evidence", 2),
  scheduledEvidence: descriptor("scheduled_evidence", 3),
  prePulseSealEvidence: descriptor("pre_pulse_seal_evidence", 4),
  pulseVerificationEvidence: descriptor("pulse_verification_evidence", 5),
  revealEvidence: descriptor("reveal_evidence", 6),
  dualEvaluationEvidence: descriptor("dual_evaluation_evidence", 7),
  sealEvidence: descriptor("seal_evidence", 8),
  temporalTerminalAuditReceipt: descriptor("temporal_terminal_audit_receipt", 9),
  finalTerminalReceipt: descriptor("final_terminal_receipt", 10)
})

it("runs a deterministic simulated happy path but hard-codes every external and scientific claim false", () => {
  const first = simulateG0TestOnlyOperator(input())
  const second = simulateG0TestOnlyOperator(input())
  expect(Either.isRight(first)).toBe(true)
  expect(Either.isRight(second)).toBe(true)
  if (Either.isLeft(first) || Either.isLeft(second)) return
  expect(first.right).toEqual(second.right)
  expect(first.right.schemaVersion).toBe(HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_V1)
  expect(first.right.classification).toBe(
    HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION
  )
  expect(first.right.states.map((state) => state.phase)).toEqual([
    "REGISTERED", "CLAIMED", "SCHEDULED", "PRE_PULSE_SEALED",
    "PULSE_VERIFIED", "REVEALED", "DUAL_EVALUATED", "SEALED"
  ])
  expect(first.right.simulatedTerminalWorkflowReceipt).toMatchObject({
    classification: HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION,
    occurrenceUid: input().occurrenceUid,
    descriptor: { name: "temporal_terminal_audit_receipt" },
    productionReceiptCompatible: false
  })
  expect(first.right.simulatedFinalTerminalReceipt).toMatchObject({
    descriptor: { name: "final_terminal_receipt" },
    productionReceiptCompatible: false
  })
  expect(first.right.externalQualificationClaimed).toBe(false)
  expect(first.right.externalExecutionClaimed).toBe(false)
  expect(first.right.scientificEvidenceClaimed).toBe(false)
  expect(first.right.g0Passed).toBe(false)
  expect(first.right.publicationEligible).toBe(false)
})

it("rejects a duplicate simulated occurrence UID before any replacement run", () => {
  const result = simulateG0TestOnlyOperator({
    ...input(),
    existingOccurrenceUids: [input().occurrenceUid]
  })
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isRight(result)) return
  expect(result.left.reason).toBe("DUPLICATE_UID")
})

it("turns a duplicate retry and an invalid phase order into local VOID transcripts", () => {
  const retried = simulateG0TestOnlyOperator({ ...input(), scenario: "DUPLICATE_RETRY" })
  const unordered = simulateG0TestOnlyOperator({ ...input(), scenario: "INVALID_PHASE_ORDER" })
  expect(Either.isRight(retried)).toBe(true)
  expect(Either.isRight(unordered)).toBe(true)
  if (Either.isLeft(retried) || Either.isLeft(unordered)) return
  expect(retried.right.states.at(-1)?.phase).toBe("VOID")
  expect(retried.right.states.at(-1)?.voidReason).toBe("DUPLICATE_OR_RETRY")
  expect(unordered.right.states.at(-1)?.phase).toBe("VOID")
  expect(unordered.right.states.at(-1)?.voidReason).toBe("ORDER")
  expect(retried.right.simulatedTerminalWorkflowReceipt).toBeNull()
  expect(unordered.right.simulatedFinalTerminalReceipt).toBeNull()
})

it("rejects role collapse, digest reuse, and every excess external-material field", () => {
  const collapsed = simulateG0TestOnlyOperator({
    ...input(), simulatedCustodianId: input().simulatedOperatorId
  })
  const digestReuse = simulateG0TestOnlyOperator({
    ...input(), finalTerminalReceipt: input().temporalTerminalAuditReceipt
  })
  const forbidden = simulateG0TestOnlyOperator({
    ...input(), endpoint: "https://forbidden.invalid", credential: "forbidden", privateHoldout: "forbidden"
  })
  const nestedForbidden = simulateG0TestOnlyOperator({
    ...input(),
    wormClaimReceipt: { ...input().wormClaimReceipt, endpoint: "https://forbidden.invalid" }
  })
  const nonPlain = simulateG0TestOnlyOperator(Object.assign(
    Object.create({ endpoint: "https://forbidden.invalid" }) as object,
    input()
  ))
  const hostileProxy = simulateG0TestOnlyOperator(new Proxy(input(), {
    getPrototypeOf: () => { throw new Error("sensitive proxy detail") }
  }))
  expect(Either.isLeft(collapsed)).toBe(true)
  expect(Either.isLeft(digestReuse)).toBe(true)
  expect(Either.isLeft(forbidden)).toBe(true)
  expect(Either.isLeft(nestedForbidden)).toBe(true)
  expect(Either.isLeft(nonPlain)).toBe(true)
  expect(Either.isLeft(hostileProxy)).toBe(true)
  if (Either.isLeft(collapsed)) expect(collapsed.left.reason).toBe("ROLE_SEPARATION_INVALID")
  if (Either.isLeft(digestReuse)) expect(digestReuse.left.reason).toBe("DESCRIPTOR_SEPARATION_INVALID")
  if (Either.isLeft(forbidden)) expect(forbidden.left.reason).toBe("INPUT_INVALID")
  if (Either.isLeft(hostileProxy)) {
    expect(hostileProxy.left.reason).toBe("INPUT_INVALID")
    expect(hostileProxy.left.detail).not.toContain("sensitive proxy detail")
  }
})
