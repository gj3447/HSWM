/**
 * Dependency-free deterministic G0 domain used inside the Temporal sandbox.
 *
 * Do not add Effect, Node, network, filesystem, random, or wall-clock imports
 * here. Temporal supplies deterministic Date.now() to the workflow caller.
 */
export const G0_TEMPORAL_DESCRIPTOR_MEDIA_TYPE =
  "application/vnd.hswm.content-descriptor+json" as const

export type G0TemporalDomainPhase =
  | "REGISTERED"
  | "CLAIMED"
  | "SCHEDULED"
  | "PRE_PULSE_SEALED"
  | "PULSE_VERIFIED"
  | "REVEALED"
  | "DUAL_EVALUATED"
  | "SEALED"
  | "VOID"

export type G0TemporalDomainTiming = "PRE_PULSE" | "POST_PULSE"
export type G0TemporalDomainVoidReason =
  | "DUPLICATE_OR_RETRY"
  | "LATE"
  | "ORDER"
  | "INVALID_EVIDENCE_DESCRIPTOR"
  | "TERMINAL_REENTRY"

export interface G0TemporalDomainDescriptor {
  readonly name: string
  readonly sha256: string
  readonly mediaType: typeof G0_TEMPORAL_DESCRIPTOR_MEDIA_TYPE
}

export interface G0TemporalDomainStart {
  readonly occurrenceUid: string
  readonly wormClaimReceipt: G0TemporalDomainDescriptor
  readonly registrationEvidence: G0TemporalDomainDescriptor
  readonly occurrenceTimeoutSeconds: number
}

export interface G0TemporalDomainTransition {
  readonly nextPhase: string
  readonly evidence: G0TemporalDomainDescriptor
  readonly timing: string
}

export interface G0TemporalDomainState {
  readonly occurrenceUid: string
  readonly occurrenceTimeoutSeconds: number
  readonly phase: G0TemporalDomainPhase
  readonly evidenceSha256s: ReadonlyArray<string>
  readonly voidReason: G0TemporalDomainVoidReason | null
  readonly rejectedEvidenceSha256: string | null
  readonly terminal: boolean
}

export type G0TemporalDomainResult<A> =
  | Readonly<{ ok: true; value: A }>
  | Readonly<{ ok: false; detail: string }>

const uidPattern = /^[A-Za-z][A-Za-z0-9._:-]{0,127}(?![\s\S])/u
const digestPattern = /^[0-9a-f]{64}(?![\s\S])/u
const descriptorNamePattern = /^[a-z][a-z0-9_]{0,63}(?![\s\S])/u
const issuedStates = new WeakSet<G0TemporalDomainState>()

const right = <A>(value: A): G0TemporalDomainResult<A> => Object.freeze({ ok: true, value })
const left = <A = never>(detail: string): G0TemporalDomainResult<A> => Object.freeze({ ok: false, detail })

const exactObject = (
  input: unknown,
  keys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return null
  const raw = input as Readonly<Record<string, unknown>>
  const actual = Object.keys(raw)
  return actual.length === keys.length && actual.every((key) => keys.includes(key))
    ? raw
    : null
}

const decodeDescriptor = (input: unknown): G0TemporalDomainDescriptor | null => {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return null
  const raw = input as Readonly<Record<string, unknown>>
  const keys = Object.keys(raw)
  if (!(
    (keys.length === 2 && keys.includes("name") && keys.includes("sha256")) ||
    (keys.length === 3 && keys.includes("name") && keys.includes("sha256") && keys.includes("media_type"))
  )) return null
  const name = raw["name"]
  const sha256 = raw["sha256"]
  const mediaType = raw["media_type"] ?? G0_TEMPORAL_DESCRIPTOR_MEDIA_TYPE
  if (
    typeof name !== "string" ||
    typeof sha256 !== "string" ||
    typeof mediaType !== "string" ||
    !descriptorNamePattern.test(name) ||
    !digestPattern.test(sha256) ||
    mediaType !== G0_TEMPORAL_DESCRIPTOR_MEDIA_TYPE
  ) return null
  return Object.freeze({ name, sha256, mediaType })
}

export const decodeG0TemporalDomainStart = (
  input: unknown
): G0TemporalDomainResult<G0TemporalDomainStart> => {
  const raw = exactObject(input, [
    "occurrence_uid",
    "worm_claim_receipt",
    "registration_evidence",
    "occurrence_timeout_seconds"
  ])
  if (raw === null) return left("start input has an unsupported shape")
  const uid = raw["occurrence_uid"]
  const timeout = raw["occurrence_timeout_seconds"]
  const worm = decodeDescriptor(raw["worm_claim_receipt"])
  const registration = decodeDescriptor(raw["registration_evidence"])
  if (
    typeof uid !== "string" ||
    !uidPattern.test(uid) ||
    typeof timeout !== "number" ||
    !Number.isInteger(timeout) ||
    timeout < 1 ||
    timeout > 86_400 ||
    worm === null ||
    registration === null ||
    worm.name !== "candidate_worm_claim_receipt" ||
    registration.name !== "registration_evidence"
  ) return left("start input fields or descriptor roles are invalid")
  return right(Object.freeze({
    occurrenceUid: uid,
    wormClaimReceipt: worm,
    registrationEvidence: registration,
    occurrenceTimeoutSeconds: timeout
  }))
}

export const decodeG0TemporalDomainTransition = (
  input: unknown
): G0TemporalDomainResult<G0TemporalDomainTransition> => {
  const raw = exactObject(input, ["next_phase", "evidence", "timing"])
  if (raw === null) return left("transition has an unsupported shape")
  const nextPhase = raw["next_phase"]
  const timing = raw["timing"]
  const evidence = decodeDescriptor(raw["evidence"])
  if (typeof nextPhase !== "string" || typeof timing !== "string" || evidence === null) {
    return left("transition fields are invalid")
  }
  return right(Object.freeze({ nextPhase, evidence, timing }))
}

const freezeState = (
  state: Omit<G0TemporalDomainState, "terminal">
): G0TemporalDomainState => {
  const issued = Object.freeze({
    ...state,
    evidenceSha256s: Object.freeze([...state.evidenceSha256s]),
    terminal: state.phase === "SEALED" || state.phase === "VOID"
  })
  issuedStates.add(issued)
  return issued
}

const validPhase = (value: string): value is G0TemporalDomainPhase => [
  "REGISTERED",
  "CLAIMED",
  "SCHEDULED",
  "PRE_PULSE_SEALED",
  "PULSE_VERIFIED",
  "REVEALED",
  "DUAL_EVALUATED",
  "SEALED",
  "VOID"
].includes(value)

const validTiming = (value: string): value is G0TemporalDomainTiming =>
  value === "PRE_PULSE" || value === "POST_PULSE"

const nextByPhase: Readonly<Record<G0TemporalDomainPhase, G0TemporalDomainPhase | null>> = {
  REGISTERED: "CLAIMED",
  CLAIMED: "SCHEDULED",
  SCHEDULED: "PRE_PULSE_SEALED",
  PRE_PULSE_SEALED: "PULSE_VERIFIED",
  PULSE_VERIFIED: "REVEALED",
  REVEALED: "DUAL_EVALUATED",
  DUAL_EVALUATED: "SEALED",
  SEALED: null,
  VOID: null
}

const expectedNext = (phase: G0TemporalDomainPhase): G0TemporalDomainPhase | null =>
  nextByPhase[phase]

const requiredTiming = (phase: G0TemporalDomainPhase): G0TemporalDomainTiming =>
  phase === "PULSE_VERIFIED" ||
  phase === "REVEALED" ||
  phase === "DUAL_EVALUATED" ||
  phase === "SEALED"
    ? "POST_PULSE"
    : "PRE_PULSE"

export const registeredG0TemporalDomain = (
  start: G0TemporalDomainStart
): G0TemporalDomainState => freezeState({
  occurrenceUid: start.occurrenceUid,
  occurrenceTimeoutSeconds: start.occurrenceTimeoutSeconds,
  phase: "REGISTERED",
  evidenceSha256s: [start.registrationEvidence.sha256],
  voidReason: null,
  rejectedEvidenceSha256: null
})

export const voidG0TemporalDomain = (
  state: G0TemporalDomainState,
  reason: G0TemporalDomainVoidReason,
  rejectedEvidenceSha256: string | null = null
): G0TemporalDomainResult<G0TemporalDomainState> => {
  if (!issuedStates.has(state)) return left("state was not issued by the Temporal domain")
  if (state.phase === "VOID") return right(state)
  return right(freezeState({
    occurrenceUid: state.occurrenceUid,
    occurrenceTimeoutSeconds: state.occurrenceTimeoutSeconds,
    phase: "VOID",
    evidenceSha256s: state.evidenceSha256s,
    voidReason: reason,
    rejectedEvidenceSha256:
      rejectedEvidenceSha256 !== null && digestPattern.test(rejectedEvidenceSha256)
        ? rejectedEvidenceSha256
        : null
  }))
}

export const advanceG0TemporalDomain = (
  state: G0TemporalDomainState,
  transition: G0TemporalDomainTransition
): G0TemporalDomainResult<G0TemporalDomainState> => {
  if (!issuedStates.has(state)) return left("state was not issued by the Temporal domain")
  if (state.phase === "VOID") return right(state)
  if (state.phase === "SEALED") {
    return voidG0TemporalDomain(state, "TERMINAL_REENTRY", transition.evidence.sha256)
  }
  const { nextPhase, evidence, timing } = transition
  if (!validPhase(nextPhase) || !validTiming(timing)) {
    return voidG0TemporalDomain(state, "ORDER", evidence.sha256)
  }
  if (state.evidenceSha256s.includes(evidence.sha256) || nextPhase === state.phase) {
    return voidG0TemporalDomain(state, "DUPLICATE_OR_RETRY", evidence.sha256)
  }
  if (nextPhase !== expectedNext(state.phase)) {
    return voidG0TemporalDomain(state, "ORDER", evidence.sha256)
  }
  if (timing !== requiredTiming(nextPhase)) {
    return voidG0TemporalDomain(state, "LATE", evidence.sha256)
  }
  return right(freezeState({
    occurrenceUid: state.occurrenceUid,
    occurrenceTimeoutSeconds: state.occurrenceTimeoutSeconds,
    phase: nextPhase,
    evidenceSha256s: [...state.evidenceSha256s, evidence.sha256],
    voidReason: null,
    rejectedEvidenceSha256: null
  }))
}
