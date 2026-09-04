import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import {
  G0DefaultBlockedExternalPortsLayer,
  G0OccurrencePhaseKernel,
  G0OccurrencePhaseKernelLayer,
  HSWM_G0_OCCURRENCE_CLAIM_CEILING,
  advanceG0Occurrence,
  g0OneShotWorkflowPolicy,
  makeG0TestOnlyMemoryPortsLayer,
  registeredG0Occurrence,
  type G0ContentDescriptor,
  type G0OccurrencePhase,
  type G0OccurrenceState
} from "../src/g0-occurrence-phase-kernel.js"

interface ParityTransition {
  readonly next_phase: string
  readonly evidence_sha256: string
  readonly timing: string
}

interface ParityCase {
  readonly case_id: string
  readonly registration_evidence_sha256: string
  readonly transitions: ReadonlyArray<ParityTransition>
  readonly expected: {
    readonly phase: string
    readonly evidence_sha256s: ReadonlyArray<string>
    readonly void_reason: string | null
    readonly rejected_evidence_sha256: string | null
    readonly terminal: boolean
  }
}

const parityVectors = JSON.parse(readFileSync(
  new URL("../../../../_research/g0_occurrence/HSWM_G0_WORKFLOW_PARITY_VECTORS.v1.json", import.meta.url),
  "utf8"
)) as {
  readonly schema_version: string
  readonly status: string
  readonly parity_scope: string
  readonly occurrence_uid: string
  readonly occurrence_timeout_seconds: number
  readonly cases: ReadonlyArray<ParityCase>
}

const descriptor = (name: string, value: number): G0ContentDescriptor => Object.freeze({
  name,
  sha256: value.toString(16).padStart(64, "0"),
  mediaType: "application/vnd.hswm.content-descriptor+json"
})

const input = () => Object.freeze({
  occurrenceUid: "future-outcome-001",
  wormClaimReceipt: descriptor("candidate_worm_claim_receipt", 1),
  registrationEvidence: descriptor("registration_evidence", 2),
  occurrenceTimeoutSeconds: 600
})

const layer = (ports = G0DefaultBlockedExternalPortsLayer) =>
  G0OccurrencePhaseKernelLayer.pipe(Layer.provide(ports))

const transition = (
  nextPhase: G0OccurrencePhase,
  value: number,
  timing: "PRE_PULSE" | "POST_PULSE"
) => Object.freeze({ nextPhase, evidence: descriptor(`evidence_${value}`, value), timing })

const issuedTerminalState = (): G0OccurrenceState => {
  const registered = registeredG0Occurrence("future-outcome-001", descriptor("registration_evidence", 2).sha256, 600)
  if (Either.isLeft(registered)) throw registered.left
  let state = registered.right
  const steps: ReadonlyArray<readonly [G0OccurrencePhase, "PRE_PULSE" | "POST_PULSE"]> = [
    ["CLAIMED", "PRE_PULSE"], ["SCHEDULED", "PRE_PULSE"],
    ["PRE_PULSE_SEALED", "PRE_PULSE"], ["PULSE_VERIFIED", "POST_PULSE"],
    ["REVEALED", "POST_PULSE"], ["DUAL_EVALUATED", "POST_PULSE"],
    ["SEALED", "POST_PULSE"]
  ]
  for (const [phase, timing] of steps) {
    const advanced = advanceG0Occurrence(state, transition(phase, state.evidenceSha256s.length + 2, timing))
    if (Either.isLeft(advanced)) throw advanced.left
    state = advanced.right
  }
  return state
}

it.effect("preserves the Python one-shot phase order and keeps SEALED below G0", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    let state = yield* control.beginClaimedProjection(input())
    expect(state.phase).toBe("CLAIMED")
    expect(state.occurrenceTimeoutSeconds).toBe(600)
    const policy = yield* control.oneShotPolicy(state)
    expect(policy.executionTimeoutSeconds).toBe(660)
    expect(Object.isFrozen(state)).toBe(true)
    expect(Object.isFrozen(state.evidenceSha256s)).toBe(true)
    const steps: ReadonlyArray<readonly [G0OccurrencePhase, "PRE_PULSE" | "POST_PULSE"]> = [
      ["SCHEDULED", "PRE_PULSE"],
      ["PRE_PULSE_SEALED", "PRE_PULSE"],
      ["PULSE_VERIFIED", "POST_PULSE"],
      ["REVEALED", "POST_PULSE"],
      ["DUAL_EVALUATED", "POST_PULSE"],
      ["SEALED", "POST_PULSE"]
    ]
    for (const [phase, timing] of steps) {
      state = yield* control.advance(state, transition(phase, state.evidenceSha256s.length + 3, timing))
      expect(state.phase).toBe(phase)
    }
    expect(state.terminal).toBe(true)
    expect(state.voidReason).toBeNull()
    expect(state.claimCeiling).toBe(HSWM_G0_OCCURRENCE_CLAIM_CEILING)
    expect(state.claimCeiling).toContain("NOT_G0")
    expect(state.claimCeiling).toContain("NOT_LEARNING")
    expect(state.g0Passed).toBe(false)
    expect(state.publicationEligible).toBe(false)
    expect(state.g0Status).toBe("NOT_EVIDENCE_BY_ITSELF")
  }).pipe(Effect.provide(layer()))
)

it.effect("rejects excess start fields and non-module-issued states", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const excess = yield* control.beginClaimedProjection({ ...input(), actorMaterial: "forbidden" }).pipe(Effect.either)
    expect(Either.isLeft(excess)).toBe(true)
    if (Either.isLeft(excess)) expect(excess.left.reason).toBe("INPUT_INVALID")
    const nestedExcess = yield* control.beginClaimedProjection({
      ...input(),
      wormClaimReceipt: { ...input().wormClaimReceipt, endpoint: "forbidden" }
    }).pipe(Effect.either)
    expect(Either.isLeft(nestedExcess)).toBe(true)
    if (Either.isLeft(nestedExcess)) expect(nestedExcess.left.reason).toBe("INPUT_INVALID")
    const trailingNewline = yield* control.beginClaimedProjection({
      ...input(),
      occurrenceUid: `${input().occurrenceUid}\n`
    }).pipe(Effect.either)
    expect(Either.isLeft(trailingNewline)).toBe(true)
    if (Either.isLeft(trailingNewline)) expect(trailingNewline.left.reason).toBe("INPUT_INVALID")

    const fabricated = Object.freeze({
      schemaVersion: "hswm-g0-occurrence-phase-kernel/v1",
      occurrenceUid: "future-outcome-001",
      occurrenceTimeoutSeconds: 600,
      phase: "SEALED",
      evidenceSha256s: Object.freeze([descriptor("registration_evidence", 2).sha256]),
      voidReason: null,
      rejectedEvidenceSha256: null,
      claimCeiling: HSWM_G0_OCCURRENCE_CLAIM_CEILING,
      g0Passed: false,
      publicationEligible: false,
      g0Status: "NOT_EVIDENCE_BY_ITSELF",
      terminal: true
    })
    const rejected = yield* control.advance(fabricated, transition("SEALED", 3, "POST_PULSE")).pipe(Effect.either)
    expect(Either.isLeft(rejected)).toBe(true)
    if (Either.isLeft(rejected)) expect(rejected.left.reason).toBe("STATE_INVALID")
  }).pipe(Effect.provide(layer()))
)

it.effect("malformed ingress becomes immutable VOID without retry", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const initial = yield* control.beginClaimedProjection(input())
    const voided = yield* control.advance(initial, { nextPhase: "CLAIMED", unexpected: true })
    expect(voided.phase).toBe("VOID")
    expect(voided.voidReason).toBe("INVALID_EVIDENCE_DESCRIPTOR")
    const excess = yield* control.advance(initial, {
      ...transition("SCHEDULED", 3, "PRE_PULSE"),
      unexpected: true
    })
    expect(excess.voidReason).toBe("INVALID_EVIDENCE_DESCRIPTOR")
    expect(excess.rejectedEvidenceSha256).toBeNull()
    const later = yield* control.advance(voided, transition("CLAIMED", 3, "PRE_PULSE"))
    expect(later).toBe(voided)
  }).pipe(Effect.provide(layer()))
)

it.effect("duplicate evidence, late timing, and wrong order each fail closed", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const startCollision = yield* control.beginClaimedProjection({
      ...input(),
      wormClaimReceipt: {
        ...input().wormClaimReceipt,
        sha256: input().registrationEvidence.sha256
      }
    })
    expect(startCollision.phase).toBe("VOID")
    expect(startCollision.voidReason).toBe("DUPLICATE_OR_RETRY")
    const initial = yield* control.beginClaimedProjection(input())
    const duplicate = yield* control.advance(initial, {
      nextPhase: "CLAIMED",
      evidence: input().registrationEvidence,
      timing: "PRE_PULSE"
    })
    expect(duplicate.voidReason).toBe("DUPLICATE_OR_RETRY")
    const late = yield* control.advance(initial, transition("SCHEDULED", 3, "POST_PULSE"))
    expect(late.voidReason).toBe("LATE")
    const wrongOrder = yield* control.advance(initial, transition("REVEALED", 4, "POST_PULSE"))
    expect(wrongOrder.voidReason).toBe("ORDER")
  }).pipe(Effect.provide(layer()))
)

it.effect("a post-seal signal is terminal reentry and therefore VOID", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    let state = yield* control.beginClaimedProjection(input())
    const steps: ReadonlyArray<readonly [G0OccurrencePhase, "PRE_PULSE" | "POST_PULSE"]> = [
      ["SCHEDULED", "PRE_PULSE"],
      ["PRE_PULSE_SEALED", "PRE_PULSE"], ["PULSE_VERIFIED", "POST_PULSE"],
      ["REVEALED", "POST_PULSE"], ["DUAL_EVALUATED", "POST_PULSE"], ["SEALED", "POST_PULSE"]
    ]
    for (const [phase, timing] of steps) {
      state = yield* control.advance(
        state,
        transition(phase, state.evidenceSha256s.length + 3, timing)
      )
    }
    const reentered = yield* control.advance(state, transition("SEALED", 99, "POST_PULSE"))
    expect(reentered.phase).toBe("VOID")
    expect(reentered.voidReason).toBe("TERMINAL_REENTRY")
    expect(reentered.rejectedEvidenceSha256).toBe(descriptor("reentry", 99).sha256)
    const malformed = yield* control.advance(issuedTerminalState(), {
      nextPhase: "NOT_A_PHASE",
      evidence: descriptor("malformed_reentry", 100),
      timing: "NOT_A_TIMING"
    })
    expect(malformed.voidReason).toBe("TERMINAL_REENTRY")
    expect(malformed.rejectedEvidenceSha256).toBe(descriptor("malformed_reentry", 100).sha256)
    const malformedEnvelope = yield* control.advance(issuedTerminalState(), {
      ...transition("SEALED", 101, "POST_PULSE"),
      unexpected: true
    })
    expect(malformedEnvelope.voidReason).toBe("TERMINAL_REENTRY")
    expect(malformedEnvelope.rejectedEvidenceSha256).toBeNull()
  }).pipe(Effect.provide(layer()))
)

it("projects the exact one-shot policy including the retained timeout", () => {
  const result = g0OneShotWorkflowPolicy("future-outcome-001", 600)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right).toEqual({
      occurrenceUid: "future-outcome-001",
      workflowId: "g0-occurrence/future-outcome-001",
      workflowIdReusePolicy: "REJECT_DUPLICATE",
      workflowMaximumAttempts: 1,
      activityMaximumAttempts: 1,
      replacementRoundAllowed: false,
      occurrenceTimeoutSeconds: 600,
      receiptFinalizationGraceSeconds: 60,
      executionTimeoutSeconds: 660,
      maximumPendingSignals: 8,
      postStartEvidence: "SIGNAL_ONLY_NOT_PRELOADED"
    })
    expect(Object.isFrozen(result.right)).toBe(true)
  }
  expect(Either.isLeft(g0OneShotWorkflowPolicy("bad uid", 600))).toBe(true)
  expect(Either.isLeft(g0OneShotWorkflowPolicy("future-outcome-001\n", 600))).toBe(true)
  expect(Either.isLeft(g0OneShotWorkflowPolicy("future-outcome-001", 0))).toBe(true)
})

it.effect("the default external ports are blocked", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const nonterminal = yield* control.beginClaimedProjection(input())
    const early = yield* control.readTerminalReceiptDescriptors(nonterminal).pipe(Effect.either)
    expect(Either.isLeft(early)).toBe(true)
    if (Either.isLeft(early)) expect(early.left.reason).toBe("STATE_INVALID")
    const attempted = yield* control.readTerminalReceiptDescriptors(issuedTerminalState()).pipe(Effect.either)
    expect(Either.isLeft(attempted)).toBe(true)
    if (Either.isLeft(attempted)) expect(attempted.left.reason).toBe("PORT_BLOCKED")
  }).pipe(Effect.provide(layer()))
)

it.effect("rejects valid descriptor shapes carrying the wrong terminal roles", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const attempted = yield* control.readTerminalReceiptDescriptors(issuedTerminalState()).pipe(Effect.either)
    expect(Either.isLeft(attempted)).toBe(true)
    if (Either.isLeft(attempted)) expect(attempted.left.reason).toBe("PORT_RECEIPT_INVALID")
  }).pipe(Effect.provide(layer(makeG0TestOnlyMemoryPortsLayer(
    new Map([["future-outcome-001", descriptor("unbound_workflow_receipt", 7)]]),
    new Map([["future-outcome-001", descriptor("unbound_completion_receipt", 8)]])
  ))))
)

it.effect("rejects a digest collision across distinct terminal roles", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const attempted = yield* control.readTerminalReceiptDescriptors(issuedTerminalState()).pipe(Effect.either)
    expect(Either.isLeft(attempted)).toBe(true)
    if (Either.isLeft(attempted)) expect(attempted.left.reason).toBe("PORT_RECEIPT_INVALID")
  }).pipe(Effect.provide(layer(makeG0TestOnlyMemoryPortsLayer(
    new Map([["future-outcome-001", descriptor("temporal_terminal_audit_receipt", 7)]]),
    new Map([["future-outcome-001", descriptor("final_terminal_receipt", 7)]])
  ))))
)

it.effect("test-only ports read SEALED and VOID descriptors without promoting G0", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const receipts = yield* control.readTerminalReceiptDescriptors(issuedTerminalState())
    expect(receipts.workflow.sha256).toBe(descriptor("temporal_terminal_audit_receipt", 7).sha256)
    expect(receipts.completion.sha256).toBe(descriptor("final_terminal_receipt", 8).sha256)
    expect(Object.isFrozen(receipts)).toBe(true)

    const claimed = yield* control.beginClaimedProjection(input())
    const voided = yield* control.advance(claimed, transition("REVEALED", 9, "POST_PULSE"))
    expect(voided.phase).toBe("VOID")
    const voidReceipts = yield* control.readTerminalReceiptDescriptors(voided)
    expect(voidReceipts.workflow.sha256).toBe(receipts.workflow.sha256)
    expect(voidReceipts.completion.sha256).toBe(receipts.completion.sha256)
  }).pipe(Effect.provide(layer(makeG0TestOnlyMemoryPortsLayer(
    new Map([["future-outcome-001", descriptor("temporal_terminal_audit_receipt", 7)]]),
    new Map([["future-outcome-001", descriptor("final_terminal_receipt", 8)]])
  ))))
)

it.effect("revalidates and rejects malformed descriptors returned by a port", () =>
  Effect.gen(function* () {
    const control = yield* G0OccurrencePhaseKernel
    const attempted = yield* control.readTerminalReceiptDescriptors(issuedTerminalState()).pipe(Effect.either)
    expect(Either.isLeft(attempted)).toBe(true)
    if (Either.isLeft(attempted)) expect(attempted.left.reason).toBe("PORT_RECEIPT_INVALID")
  }).pipe(Effect.provide(layer(makeG0TestOnlyMemoryPortsLayer(
    new Map([["future-outcome-001", {
      ...descriptor("temporal_terminal_audit_receipt", 7),
      unexpected: true
    } as unknown as G0ContentDescriptor]]),
    new Map([["future-outcome-001", descriptor("final_terminal_receipt", 8)]])
  ))))
)

it("matches all checked-in Python workflow parity vectors", () => {
  expect(parityVectors.schema_version).toBe("hswm-g0-occurrence-workflow-parity-vectors/v1")
  expect(parityVectors.status).toBe("CROSS_LANGUAGE_ENGINEERING_FIXTURE_ONLY_NOT_EXECUTED_NOT_G0")
  expect(parityVectors.parity_scope).toBe(
    "TRANSITION_RESULT_PARITY_ONLY_NOT_WIRE_SCHEMA_NOT_TIMEOUT_LOOP_NOT_SIGNAL_QUEUE_NOT_COMPLETION_HANDSHAKE"
  )
  expect(parityVectors.cases).toHaveLength(11)
  for (const fixture of parityVectors.cases) {
    const registered = registeredG0Occurrence(
      parityVectors.occurrence_uid,
      fixture.registration_evidence_sha256,
      parityVectors.occurrence_timeout_seconds
    )
    expect(Either.isRight(registered), fixture.case_id).toBe(true)
    if (Either.isLeft(registered)) continue
    let state = registered.right
    for (const item of fixture.transitions) {
      state = advanceForParity(state, item)
    }
    expect(state.phase, fixture.case_id).toBe(fixture.expected.phase)
    expect(state.evidenceSha256s, fixture.case_id).toEqual(fixture.expected.evidence_sha256s)
    expect(state.voidReason, fixture.case_id).toBe(fixture.expected.void_reason)
    expect(state.rejectedEvidenceSha256, fixture.case_id).toBe(fixture.expected.rejected_evidence_sha256)
    expect(state.terminal, fixture.case_id).toBe(fixture.expected.terminal)
  }
})

const advanceForParity = (
  state: G0OccurrenceState,
  item: ParityTransition
) => {
  const advanced = advanceG0Occurrence(state, {
      nextPhase: item.next_phase,
      evidence: {
        name: "parity_evidence",
        sha256: item.evidence_sha256,
        mediaType: "application/vnd.hswm.content-descriptor+json"
      },
      timing: item.timing
    })
  if (Either.isLeft(advanced)) throw advanced.left
  return advanced.right
}
