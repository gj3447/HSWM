import { readFileSync } from "node:fs"

import { expect, it } from "vitest"

import {
  advanceG0TemporalDomain,
  decodeG0TemporalDomainStart,
  decodeG0TemporalDomainTransition,
  registeredG0TemporalDomain,
  voidG0TemporalDomain,
  type G0TemporalDomainState
} from "../src/g0-occurrence-temporal-domain.js"

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

const vectors = JSON.parse(readFileSync(
  new URL("../../../../_research/g0_occurrence/HSWM_G0_WORKFLOW_PARITY_VECTORS.v1.json", import.meta.url),
  "utf8"
)) as {
  readonly occurrence_uid: string
  readonly occurrence_timeout_seconds: number
  readonly cases: ReadonlyArray<ParityCase>
}

const descriptor = (name: string, sha256: string) => ({ name, sha256 })

const applyFixture = (
  state: G0TemporalDomainState,
  item: ParityTransition
): G0TemporalDomainState => {
  const decoded = decodeG0TemporalDomainTransition({
    next_phase: item.next_phase,
    evidence: descriptor("parity_evidence", item.evidence_sha256),
    timing: item.timing
  })
  if (!decoded.ok) {
    const voided = voidG0TemporalDomain(
      state,
      state.phase === "SEALED" ? "TERMINAL_REENTRY" : "INVALID_EVIDENCE_DESCRIPTOR"
    )
    if (!voided.ok) throw new Error(voided.detail)
    return voided.value
  }
  const advanced = advanceG0TemporalDomain(state, decoded.value)
  if (!advanced.ok) throw new Error(advanced.detail)
  return advanced.value
}

it("matches all Python/Effect transition-result vectors in the dependency-free Temporal domain", () => {
  expect(vectors.cases).toHaveLength(11)
  for (const fixture of vectors.cases) {
    const claimDigest = fixture.transitions[0]?.evidence_sha256 ?? "f".repeat(64)
    const start = decodeG0TemporalDomainStart({
      occurrence_uid: vectors.occurrence_uid,
      worm_claim_receipt: descriptor("candidate_worm_claim_receipt", claimDigest),
      registration_evidence: descriptor("registration_evidence", fixture.registration_evidence_sha256),
      occurrence_timeout_seconds: vectors.occurrence_timeout_seconds
    })
    expect(start.ok, fixture.case_id).toBe(true)
    if (!start.ok) continue
    let state = registeredG0TemporalDomain(start.value)
    for (const item of fixture.transitions) state = applyFixture(state, item)
    expect(state.phase, fixture.case_id).toBe(fixture.expected.phase)
    expect(state.evidenceSha256s, fixture.case_id).toEqual(fixture.expected.evidence_sha256s)
    expect(state.voidReason, fixture.case_id).toBe(fixture.expected.void_reason)
    expect(state.rejectedEvidenceSha256, fixture.case_id).toBe(fixture.expected.rejected_evidence_sha256)
    expect(state.terminal, fixture.case_id).toBe(fixture.expected.terminal)
  }
})

it("rejects structural state forgery and preserves the first explicit VOID", () => {
  const forged = {
    occurrenceUid: vectors.occurrence_uid,
    occurrenceTimeoutSeconds: 600,
    phase: "CLAIMED",
    evidenceSha256s: Object.freeze(["1".repeat(64)]),
    voidReason: null,
    rejectedEvidenceSha256: null,
    terminal: false
  } as const
  expect(advanceG0TemporalDomain(forged, {
    nextPhase: "SCHEDULED",
    evidence: {
      name: "evidence",
      sha256: "2".repeat(64),
      mediaType: "application/vnd.hswm.content-descriptor+json"
    },
    timing: "PRE_PULSE"
  }).ok).toBe(false)

  const start = decodeG0TemporalDomainStart({
    occurrence_uid: vectors.occurrence_uid,
    worm_claim_receipt: descriptor("candidate_worm_claim_receipt", "2".repeat(64)),
    registration_evidence: descriptor("registration_evidence", "1".repeat(64)),
    occurrence_timeout_seconds: 600
  })
  if (!start.ok) throw new Error(start.detail)
  const state = registeredG0TemporalDomain(start.value)
  const first = voidG0TemporalDomain(state, "LATE")
  if (!first.ok) throw new Error(first.detail)
  const second = voidG0TemporalDomain(first.value, "ORDER", "3".repeat(64))
  if (!second.ok) throw new Error(second.detail)
  expect(second.value).toBe(first.value)
  expect(second.value.voidReason).toBe("LATE")
  expect(second.value.rejectedEvidenceSha256).toBeNull()
})
