import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  advanceG0Occurrence,
  registeredG0Occurrence,
  type G0OccurrenceState
} from "../src/g0-occurrence-phase-kernel.js"
import {
  decodeG0OccurrenceTemporalStartJsonBytes,
  decodeG0OccurrenceTemporalStartWire,
  decodeG0OccurrenceTemporalTransitionJsonBytes,
  decodeG0OccurrenceTemporalTransitionWire,
  decodeG0OccurrenceTemporalWorkerConfigurationWire,
  HSWM_G0_OCCURRENCE_MAX_INPUT_JSON_BYTES,
  HSWM_G0_OCCURRENCE_TEMPORAL_WORKER_WIRE_V1,
  projectG0OccurrenceTemporalTerminal
} from "../src/g0-occurrence-temporal-wire.js"

const encoder = new TextEncoder()
const digest = (value: number): string => value.toString(16).padStart(64, "0")

const startWire = Object.freeze({
  occurrence_uid: "future-outcome-001",
  worm_claim_receipt: Object.freeze({ name: "candidate_worm_claim_receipt", sha256: digest(1) }),
  registration_evidence: Object.freeze({
    name: "registration_evidence",
    sha256: digest(2),
    media_type: "application/vnd.hswm.content-descriptor+json"
  }),
  occurrence_timeout_seconds: 600
})

it("maps exact Python-v1 snake_case start input without loss, including optional media_type", () => {
  const decoded = decodeG0OccurrenceTemporalStartWire(startWire)
  expect(Either.isRight(decoded)).toBe(true)
  if (Either.isRight(decoded)) {
    expect(decoded.right).toEqual({
      occurrenceUid: "future-outcome-001",
      wormClaimReceipt: {
        name: "candidate_worm_claim_receipt",
        sha256: digest(1),
        mediaType: "application/vnd.hswm.content-descriptor+json"
      },
      registrationEvidence: {
        name: "registration_evidence",
        sha256: digest(2),
        mediaType: "application/vnd.hswm.content-descriptor+json"
      },
      occurrenceTimeoutSeconds: 600
    })
  }
})

it("strictly parses bounded UTF-8 JSON bytes and rejects invalid, oversized, or excess inputs", () => {
  const valid = decodeG0OccurrenceTemporalStartJsonBytes(encoder.encode(JSON.stringify(startWire)))
  expect(Either.isRight(valid)).toBe(true)

  const malformedUtf8 = decodeG0OccurrenceTemporalStartJsonBytes(new Uint8Array([0xff]))
  expect(Either.isLeft(malformedUtf8)).toBe(true)
  if (Either.isLeft(malformedUtf8)) expect(malformedUtf8.left.reason).toBe("INVALID_JSON")

  const withBom = decodeG0OccurrenceTemporalStartJsonBytes(new Uint8Array([
    0xef, 0xbb, 0xbf, ...encoder.encode(JSON.stringify(startWire))
  ]))
  expect(Either.isLeft(withBom)).toBe(true)
  if (Either.isLeft(withBom)) expect(withBom.left.reason).toBe("INVALID_JSON")

  const extra = decodeG0OccurrenceTemporalStartWire({ ...startWire, credential: "forbidden" })
  expect(Either.isLeft(extra)).toBe(true)
  if (Either.isLeft(extra)) expect(extra.left.reason).toBe("INPUT_INVALID")

  const oversized = decodeG0OccurrenceTemporalStartJsonBytes(
    new Uint8Array(HSWM_G0_OCCURRENCE_MAX_INPUT_JSON_BYTES + 1)
  )
  expect(Either.isLeft(oversized)).toBe(true)
  if (Either.isLeft(oversized)) expect(oversized.left.reason).toBe("INPUT_INVALID")
})

it("enforces Python-v1 descriptor roles, media, and integral timeout without coercion", () => {
  for (const value of [
    { ...startWire, occurrence_timeout_seconds: "600" },
    { ...startWire, occurrence_timeout_seconds: 600.5 },
    { ...startWire, worm_claim_receipt: { ...startWire.worm_claim_receipt, name: "wrong_role" } },
    { ...startWire, registration_evidence: { ...startWire.registration_evidence, media_type: "text/plain" } }
  ]) {
    expect(Either.isLeft(decodeG0OccurrenceTemporalStartWire(value))).toBe(true)
  }
})

it("maps strict signal wire to camelCase while preserving unknown phase/timing for kernel terminal-first handling", () => {
  const exact = decodeG0OccurrenceTemporalTransitionWire({
    next_phase: "SCHEDULED",
    timing: "PRE_PULSE",
    evidence: { name: "schedule", sha256: digest(3) }
  })
  expect(Either.isRight(exact)).toBe(true)
  if (Either.isRight(exact)) {
    expect(exact.right).toEqual({
      nextPhase: "SCHEDULED",
      timing: "PRE_PULSE",
      evidence: { name: "schedule", sha256: digest(3), mediaType: "application/vnd.hswm.content-descriptor+json" }
    })
  }
  const unknown = decodeG0OccurrenceTemporalTransitionJsonBytes(encoder.encode(JSON.stringify({
    next_phase: "NOT_A_PHASE",
    timing: "NOT_A_TIMING",
    evidence: { name: "invalid", sha256: digest(4) }
  })))
  expect(Either.isRight(unknown)).toBe(true)
  if (Either.isRight(unknown)) {
    expect(unknown.right.nextPhase).toBe("NOT_A_PHASE")
    const initial = registeredG0Occurrence("future-outcome-001", digest(2), 600)
    if (Either.isRight(initial)) {
      const voided = advanceG0Occurrence(initial.right, unknown.right)
      expect(Either.isRight(voided)).toBe(true)
      if (Either.isRight(voided)) expect(voided.right.voidReason).toBe("ORDER")
    }
  }
  expect(Either.isLeft(decodeG0OccurrenceTemporalTransitionWire({
    next_phase: "SCHEDULED", timing: "PRE_PULSE",
    evidence: { name: "schedule", sha256: digest(3), extra: true }
  }))).toBe(true)
})

it("requires an exact, non-secret signal-authorization binding configuration", () => {
  const decoded = decodeG0OccurrenceTemporalWorkerConfigurationWire({
    address: "temporal.example:7233",
    namespace: "g0",
    task_queue: "g0-queue",
    signal_authorization_binding_sha256: digest(5)
  })
  expect(Either.isRight(decoded)).toBe(true)
  if (Either.isRight(decoded)) expect(decoded.right.taskQueue).toBe("g0-queue")
  expect(Either.isLeft(decodeG0OccurrenceTemporalWorkerConfigurationWire({
    address: "temporal.example:7233 ", namespace: "g0", task_queue: "g0-queue",
    signal_authorization_binding_sha256: digest(5)
  }))).toBe(true)
})

it("projects terminal schema fields without promoting a phase result", () => {
  const initial = registeredG0Occurrence("future-outcome-001", digest(2), 600)
  if (Either.isLeft(initial)) throw initial.left
  const state: G0OccurrenceState = initial.right
  const projection = projectG0OccurrenceTemporalTerminal(state)
  expect(projection.schema_version).toBe(HSWM_G0_OCCURRENCE_TEMPORAL_WORKER_WIRE_V1)
  expect(projection.completion_handshake_required).toBe(true)
  expect(projection.publication_eligible).toBe(false)
  expect(projection.g0_status).toBe("NOT_EVIDENCE_BY_ITSELF")
  expect(Object.isFrozen(projection.evidence_sha256s)).toBe(true)
})
