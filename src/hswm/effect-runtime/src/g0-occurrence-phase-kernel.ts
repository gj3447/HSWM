/**
 * Descriptor-only G0 occurrence phase kernel.
 *
 * This is a TypeScript/Effect transition-result projection of the Python
 * one-shot workflow contract. It does not claim wire-schema, timeout-loop,
 * signal-queue, or completion-handshake parity. It neither starts a workflow,
 * owns an endpoint or credential, reads private material, nor establishes
 * outcome truth, G0, canonical admission, Permit, causal credit, or learning.
 * External systems remain opaque readback ports whose only return values are
 * content descriptors.
 */
import { Context, Data, Effect, Either, Layer, Schema } from "effect"

export const HSWM_G0_OCCURRENCE_PHASE_KERNEL_V1_CONTRACT_VERSION =
  "hswm-g0-occurrence-phase-kernel/v1" as const
export const HSWM_G0_OCCURRENCE_DESCRIPTOR_V1_MEDIA_TYPE =
  "application/vnd.hswm.content-descriptor+json" as const
export const HSWM_G0_OCCURRENCE_CLAIM_CEILING =
  "PHASE_KERNEL_ONLY_NOT_WIRE_PARITY_NOT_TIMEOUT_EXECUTION_NOT_SIGNAL_QUEUE_NOT_COMPLETION_HANDSHAKE_NOT_LIVE_EXECUTION_NOT_OUTCOME_TRUTH_NOT_G0_NOT_G1_NOT_PERMIT_NOT_CANONICAL_ADMISSION_NOT_CAUSAL_CREDIT_NOT_LEARNING" as const
export const HSWM_G0_RECEIPT_FINALIZATION_GRACE_SECONDS = 60 as const
export const HSWM_G0_MAX_PENDING_SIGNALS = 8 as const

const IdentifierSchema = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z][A-Za-z0-9._:-]{0,127}(?![\s\S])/)
)
const DescriptorNameSchema = Schema.String.pipe(
  Schema.pattern(/^[a-z][a-z0-9_]{0,63}(?![\s\S])/)
)
const Sha256Schema = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}(?![\s\S])/)
)
const TimeoutSchema = Schema.Number.pipe(Schema.int(), Schema.between(1, 86_400))

export const G0ContentDescriptorSchema = Schema.Struct({
  name: DescriptorNameSchema,
  sha256: Sha256Schema,
  mediaType: Schema.Literal(HSWM_G0_OCCURRENCE_DESCRIPTOR_V1_MEDIA_TYPE)
})
export type G0ContentDescriptor = Schema.Schema.Type<typeof G0ContentDescriptorSchema>

export const G0OccurrencePhaseSchema = Schema.Literal(
  "REGISTERED",
  "CLAIMED",
  "SCHEDULED",
  "PRE_PULSE_SEALED",
  "PULSE_VERIFIED",
  "REVEALED",
  "DUAL_EVALUATED",
  "SEALED",
  "VOID"
)
export type G0OccurrencePhase = Schema.Schema.Type<typeof G0OccurrencePhaseSchema>

export const G0PulseTimingSchema = Schema.Literal("PRE_PULSE", "POST_PULSE")
export type G0PulseTiming = Schema.Schema.Type<typeof G0PulseTimingSchema>

export const G0VoidReasonSchema = Schema.Literal(
  "DUPLICATE_OR_RETRY",
  "LATE",
  "ORDER",
  "INVALID_EVIDENCE_DESCRIPTOR",
  "TERMINAL_REENTRY"
)
export type G0VoidReason = Schema.Schema.Type<typeof G0VoidReasonSchema>

export const G0OccurrenceInputSchema = Schema.Struct({
  occurrenceUid: IdentifierSchema,
  wormClaimReceipt: G0ContentDescriptorSchema,
  registrationEvidence: G0ContentDescriptorSchema,
  occurrenceTimeoutSeconds: TimeoutSchema
})
export type G0OccurrenceInput = Schema.Schema.Type<typeof G0OccurrenceInputSchema>

export const G0OccurrenceTransitionSchema = Schema.Struct({
  nextPhase: G0OccurrencePhaseSchema,
  evidence: G0ContentDescriptorSchema,
  timing: G0PulseTimingSchema
})
export type G0OccurrenceTransition = Schema.Schema.Type<typeof G0OccurrenceTransitionSchema>

export interface G0OccurrenceState {
  readonly schemaVersion: typeof HSWM_G0_OCCURRENCE_PHASE_KERNEL_V1_CONTRACT_VERSION
  readonly occurrenceUid: string
  readonly occurrenceTimeoutSeconds: number
  readonly phase: G0OccurrencePhase
  readonly evidenceSha256s: ReadonlyArray<string>
  readonly voidReason: G0VoidReason | null
  readonly rejectedEvidenceSha256: string | null
  readonly claimCeiling: typeof HSWM_G0_OCCURRENCE_CLAIM_CEILING
  readonly g0Passed: false
  readonly publicationEligible: false
  readonly g0Status: "NOT_EVIDENCE_BY_ITSELF"
  readonly terminal: boolean
}

export interface G0OneShotWorkflowPolicy {
  readonly occurrenceUid: string
  readonly workflowId: string
  readonly workflowIdReusePolicy: "REJECT_DUPLICATE"
  readonly workflowMaximumAttempts: 1
  readonly activityMaximumAttempts: 1
  readonly replacementRoundAllowed: false
  readonly occurrenceTimeoutSeconds: number
  readonly receiptFinalizationGraceSeconds: typeof HSWM_G0_RECEIPT_FINALIZATION_GRACE_SECONDS
  readonly executionTimeoutSeconds: number
  readonly maximumPendingSignals: typeof HSWM_G0_MAX_PENDING_SIGNALS
  readonly postStartEvidence: "SIGNAL_ONLY_NOT_PRELOADED"
}

export class G0OccurrencePhaseKernelError extends Data.TaggedError(
  "G0OccurrencePhaseKernelError"
)<{
  readonly reason:
    | "INPUT_INVALID"
    | "STATE_INVALID"
    | "PORT_BLOCKED"
    | "PORT_FAILED"
    | "PORT_RECEIPT_INVALID"
  readonly detail: string
}> {}

/** A narrow workflow readback port with no execute, endpoint, credential, or signal API. */
export class G0OneShotWorkflowReceiptPort extends Context.Tag(
  "hswm/G0OneShotWorkflowReceiptPort"
)<
  G0OneShotWorkflowReceiptPort,
  {
    readonly readOneShotReceipt: (
      state: G0OccurrenceState,
      policy: G0OneShotWorkflowPolicy
    ) => Effect.Effect<G0ContentDescriptor, G0OccurrencePhaseKernelError>
  }
>() {}

/** An implementation-neutral integrity/completion readback port. */
export class G0IntegrityCompletionReceiptPort extends Context.Tag(
  "hswm/G0IntegrityCompletionReceiptPort"
)<
  G0IntegrityCompletionReceiptPort,
  {
    readonly readCompletionReceipt: (
      state: G0OccurrenceState
    ) => Effect.Effect<G0ContentDescriptor, G0OccurrencePhaseKernelError>
  }
>() {}

export class G0OccurrencePhaseKernel extends Context.Tag(
  "hswm/G0OccurrencePhaseKernel"
)<
  G0OccurrencePhaseKernel,
  {
    /**
     * Projects structurally valid caller-supplied descriptors into CLAIMED.
     * It neither verifies external facts nor starts anything.
     */
    readonly beginClaimedProjection: (
      input: unknown
    ) => Effect.Effect<G0OccurrenceState, G0OccurrencePhaseKernelError>
    /** Malformed transition ingress becomes a terminal VOID rather than a retry. */
    readonly advance: (
      state: unknown,
      transition: unknown
    ) => Effect.Effect<G0OccurrenceState, G0OccurrencePhaseKernelError>
    readonly oneShotPolicy: (
      state: unknown
    ) => Effect.Effect<G0OneShotWorkflowPolicy, G0OccurrencePhaseKernelError>
    /** Reads opaque external receipts only; it does not interpret an outcome. */
    readonly readTerminalReceiptDescriptors: (
      state: unknown
    ) => Effect.Effect<
      Readonly<{ workflow: G0ContentDescriptor; completion: G0ContentDescriptor }>,
      G0OccurrencePhaseKernelError
    >
  }
>() {}

const error = (
  reason: G0OccurrencePhaseKernelError["reason"],
  detail: string
): G0OccurrencePhaseKernelError => new G0OccurrencePhaseKernelError({ reason, detail })

const transitionExpected: Readonly<Record<Exclude<G0OccurrencePhase, "SEALED" | "VOID">, G0OccurrencePhase>> = {
  REGISTERED: "CLAIMED",
  CLAIMED: "SCHEDULED",
  SCHEDULED: "PRE_PULSE_SEALED",
  PRE_PULSE_SEALED: "PULSE_VERIFIED",
  PULSE_VERIFIED: "REVEALED",
  REVEALED: "DUAL_EVALUATED",
  DUAL_EVALUATED: "SEALED"
}

const issuedStates = new WeakSet<G0OccurrenceState>()

const freezeDescriptor = (descriptor: G0ContentDescriptor): G0ContentDescriptor =>
  Object.freeze({ ...descriptor })

const freezeState = (state: Omit<G0OccurrenceState, "terminal">): G0OccurrenceState => {
  const issued = Object.freeze({
    ...state,
    evidenceSha256s: Object.freeze([...state.evidenceSha256s]),
    terminal: state.phase === "SEALED" || state.phase === "VOID"
  })
  issuedStates.add(issued)
  return issued
}

const voidState = (
  state: G0OccurrenceState,
  reason: G0VoidReason,
  rejectedEvidenceSha256: string | null = null
): G0OccurrenceState =>
  state.phase === "VOID"
    ? state
    : freezeState({
      occurrenceUid: state.occurrenceUid,
      occurrenceTimeoutSeconds: state.occurrenceTimeoutSeconds,
      schemaVersion: HSWM_G0_OCCURRENCE_PHASE_KERNEL_V1_CONTRACT_VERSION,
      phase: "VOID",
      evidenceSha256s: state.evidenceSha256s,
      voidReason: reason,
      rejectedEvidenceSha256,
      claimCeiling: HSWM_G0_OCCURRENCE_CLAIM_CEILING,
      g0Passed: false,
      publicationEligible: false,
      g0Status: "NOT_EVIDENCE_BY_ITSELF"
    })

const descriptorDigestFromUnknown = (input: unknown): string | null => {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return null
  const raw = input as Readonly<Record<string, unknown>>
  const exactKeys = ["evidence", "nextPhase", "timing"]
  if (
    Object.keys(raw).length !== exactKeys.length ||
    Object.keys(raw).some((key) => !exactKeys.includes(key)) ||
    typeof raw["nextPhase"] !== "string" ||
    typeof raw["timing"] !== "string"
  ) return null
  if (
    typeof raw["evidence"] !== "object" ||
    raw["evidence"] === null ||
    Array.isArray(raw["evidence"])
  ) return null
  const descriptor = Schema.decodeUnknownEither(G0ContentDescriptorSchema, {
    onExcessProperty: "error"
  })(raw["evidence"])
  return Either.isRight(descriptor) ? descriptor.right.sha256 : null
}

const decodeTransitionIngress = (
  ingress: unknown
): Either.Either<
  G0OccurrenceTransition,
  {
    readonly reason: "ORDER" | "INVALID_EVIDENCE_DESCRIPTOR"
    readonly digest: string | null
  }
> => {
  if (typeof ingress !== "object" || ingress === null || Array.isArray(ingress)) {
    return Either.left({ reason: "INVALID_EVIDENCE_DESCRIPTOR", digest: null })
  }
  const raw = ingress as Readonly<Record<string, unknown>>
  const exactKeys = ["evidence", "nextPhase", "timing"]
  if (Object.keys(raw).length !== exactKeys.length || Object.keys(raw).some((key) => !exactKeys.includes(key))) {
    return Either.left({ reason: "INVALID_EVIDENCE_DESCRIPTOR", digest: null })
  }
  const descriptor = Schema.decodeUnknownEither(G0ContentDescriptorSchema, {
    onExcessProperty: "error"
  })(raw["evidence"])
  if (Either.isLeft(descriptor)) {
    return Either.left({ reason: "INVALID_EVIDENCE_DESCRIPTOR", digest: null })
  }
  const phase = Schema.decodeUnknownEither(G0OccurrencePhaseSchema)(raw["nextPhase"])
  const timing = Schema.decodeUnknownEither(G0PulseTimingSchema)(raw["timing"])
  if (Either.isLeft(phase) || Either.isLeft(timing)) {
    return Either.left({ reason: "ORDER", digest: descriptor.right.sha256 })
  }
  return Either.right(Object.freeze({
    nextPhase: phase.right,
    evidence: freezeDescriptor(descriptor.right),
    timing: timing.right
  }))
}

const startState = (
  occurrenceUid: string,
  registrationEvidenceSha256: string,
  occurrenceTimeoutSeconds: number
): G0OccurrenceState =>
  freezeState({
    schemaVersion: HSWM_G0_OCCURRENCE_PHASE_KERNEL_V1_CONTRACT_VERSION,
    occurrenceUid,
    occurrenceTimeoutSeconds,
    phase: "REGISTERED",
    evidenceSha256s: [registrationEvidenceSha256],
    voidReason: null,
    rejectedEvidenceSha256: null,
    claimCeiling: HSWM_G0_OCCURRENCE_CLAIM_CEILING,
    g0Passed: false,
    publicationEligible: false,
    g0Status: "NOT_EVIDENCE_BY_ITSELF"
  })

/** @internal Pure parity entrypoint: registered protocol evidence only, never an execution. */
export const registeredG0Occurrence = (
  occurrenceUid: unknown,
  registrationEvidenceSha256: unknown,
  occurrenceTimeoutSeconds: unknown
): Either.Either<G0OccurrenceState, G0OccurrencePhaseKernelError> => {
  const uid = Schema.decodeUnknownEither(IdentifierSchema)(occurrenceUid)
  const digest = Schema.decodeUnknownEither(Sha256Schema)(registrationEvidenceSha256)
  const timeout = Schema.decodeUnknownEither(TimeoutSchema)(occurrenceTimeoutSeconds)
  if (Either.isLeft(uid) || Either.isLeft(digest) || Either.isLeft(timeout)) {
    return Either.left(error(
      "INPUT_INVALID",
      "registered occurrence needs a UID, registration digest, and bounded timeout"
    ))
  }
  return Either.right(startState(uid.right, digest.right, timeout.right))
}

export const g0OneShotWorkflowPolicy = (
  occurrenceUid: unknown,
  occurrenceTimeoutSeconds: unknown
): Either.Either<G0OneShotWorkflowPolicy, G0OccurrencePhaseKernelError> => {
  const uid = Schema.decodeUnknownEither(IdentifierSchema)(occurrenceUid)
  const timeout = Schema.decodeUnknownEither(TimeoutSchema)(occurrenceTimeoutSeconds)
  return Either.isLeft(uid) || Either.isLeft(timeout)
    ? Either.left(error("INPUT_INVALID", "one-shot policy needs a bounded UID and timeout"))
    : Either.right(Object.freeze({
      occurrenceUid: uid.right,
      workflowId: `g0-occurrence/${uid.right}`,
      workflowIdReusePolicy: "REJECT_DUPLICATE" as const,
      workflowMaximumAttempts: 1 as const,
      activityMaximumAttempts: 1 as const,
      replacementRoundAllowed: false as const,
      occurrenceTimeoutSeconds: timeout.right,
      receiptFinalizationGraceSeconds: HSWM_G0_RECEIPT_FINALIZATION_GRACE_SECONDS,
      executionTimeoutSeconds: timeout.right + HSWM_G0_RECEIPT_FINALIZATION_GRACE_SECONDS,
      maximumPendingSignals: HSWM_G0_MAX_PENDING_SIGNALS,
      postStartEvidence: "SIGNAL_ONLY_NOT_PRELOADED" as const
    }))
}

const issuedStateFromUnknown = (
  state: unknown
): Either.Either<G0OccurrenceState, G0OccurrencePhaseKernelError> =>
  typeof state === "object" &&
  state !== null &&
  issuedStates.has(state as G0OccurrenceState)
    ? Either.right(state as G0OccurrenceState)
    : Either.left(error("STATE_INVALID", "occurrence state is not a module-issued immutable value"))

/** @internal Pure reducer used by the service and cross-language parity tests. */
export const advanceG0Occurrence = (
  state: unknown,
  ingress: unknown
): Either.Either<G0OccurrenceState, G0OccurrencePhaseKernelError> => {
  const decodedState = issuedStateFromUnknown(state)
  if (Either.isLeft(decodedState)) return decodedState
  const issuedState = decodedState.right
  if (issuedState.phase === "VOID") return Either.right(issuedState)
  if (issuedState.phase === "SEALED") {
    return Either.right(voidState(
      issuedState,
      "TERMINAL_REENTRY",
      descriptorDigestFromUnknown(ingress)
    ))
  }
  const decoded = decodeTransitionIngress(ingress)
  if (Either.isLeft(decoded)) {
    return Either.right(voidState(issuedState, decoded.left.reason, decoded.left.digest))
  }
  const transition = decoded.right
  if (issuedState.evidenceSha256s.includes(transition.evidence.sha256)) {
    return Either.right(voidState(issuedState, "DUPLICATE_OR_RETRY", transition.evidence.sha256))
  }
  const expected = transitionExpected[issuedState.phase]
  if (transition.nextPhase === issuedState.phase) {
    return Either.right(voidState(issuedState, "DUPLICATE_OR_RETRY", transition.evidence.sha256))
  }
  if (transition.nextPhase !== expected) {
    return Either.right(voidState(issuedState, "ORDER", transition.evidence.sha256))
  }
  const requiredTiming: G0PulseTiming = transition.nextPhase === "PRE_PULSE_SEALED"
    ? "PRE_PULSE"
    : transition.nextPhase === "PULSE_VERIFIED" ||
        transition.nextPhase === "REVEALED" ||
        transition.nextPhase === "DUAL_EVALUATED" ||
        transition.nextPhase === "SEALED"
      ? "POST_PULSE"
      : "PRE_PULSE"
  if (transition.timing !== requiredTiming) {
    return Either.right(voidState(issuedState, "LATE", transition.evidence.sha256))
  }
  return Either.right(freezeState({
    schemaVersion: HSWM_G0_OCCURRENCE_PHASE_KERNEL_V1_CONTRACT_VERSION,
    occurrenceUid: issuedState.occurrenceUid,
    occurrenceTimeoutSeconds: issuedState.occurrenceTimeoutSeconds,
    phase: transition.nextPhase,
    evidenceSha256s: [...issuedState.evidenceSha256s, transition.evidence.sha256],
    voidReason: null,
    rejectedEvidenceSha256: null,
    claimCeiling: HSWM_G0_OCCURRENCE_CLAIM_CEILING,
    g0Passed: false,
    publicationEligible: false,
    g0Status: "NOT_EVIDENCE_BY_ITSELF"
  }))
}

export const G0OccurrencePhaseKernelLayer = Layer.effect(
  G0OccurrencePhaseKernel,
  Effect.gen(function* () {
    const workflow = yield* G0OneShotWorkflowReceiptPort
    const completion = yield* G0IntegrityCompletionReceiptPort
    return G0OccurrencePhaseKernel.of({
      beginClaimedProjection: (input) => {
        const decoded = Schema.decodeUnknownEither(G0OccurrenceInputSchema, {
          onExcessProperty: "error"
        })(input)
        if (Either.isLeft(decoded)) {
          return Effect.fail(error("INPUT_INVALID", "occurrence start input is not an exact descriptor-only shape"))
        }
        if (
          decoded.right.wormClaimReceipt.name !== "candidate_worm_claim_receipt" ||
          decoded.right.registrationEvidence.name !== "registration_evidence"
        ) {
          return Effect.fail(error("INPUT_INVALID", "start descriptors have an unsupported role"))
        }
        const accepted = Object.freeze({
          ...decoded.right,
          wormClaimReceipt: freezeDescriptor(decoded.right.wormClaimReceipt),
          registrationEvidence: freezeDescriptor(decoded.right.registrationEvidence)
        })
        const claimed = advanceG0Occurrence(startState(
          accepted.occurrenceUid,
          accepted.registrationEvidence.sha256,
          accepted.occurrenceTimeoutSeconds
        ), Object.freeze({
          nextPhase: "CLAIMED",
          evidence: accepted.wormClaimReceipt,
          timing: "PRE_PULSE"
        }))
        return Either.isLeft(claimed) ? Effect.fail(claimed.left) : Effect.succeed(claimed.right)
      },
      advance: (state, transition) => {
        const advanced = advanceG0Occurrence(state, transition)
        return Either.isLeft(advanced) ? Effect.fail(advanced.left) : Effect.succeed(advanced.right)
      },
      oneShotPolicy: (state) => {
        const issued = issuedStateFromUnknown(state)
        if (Either.isLeft(issued)) return Effect.fail(issued.left)
        const policy = g0OneShotWorkflowPolicy(
          issued.right.occurrenceUid,
          issued.right.occurrenceTimeoutSeconds
        )
        return Either.isLeft(policy) ? Effect.fail(policy.left) : Effect.succeed(policy.right)
      },
      readTerminalReceiptDescriptors: (state) => Effect.gen(function* () {
        const issued = issuedStateFromUnknown(state)
        const acceptedState = yield* Either.isLeft(issued)
          ? Effect.fail(issued.left)
          : Effect.succeed(issued.right)
        if (!acceptedState.terminal) {
          return yield* Effect.fail(error("STATE_INVALID", "terminal receipt readback needs a terminal issued state"))
        }
        const validatedPolicy = g0OneShotWorkflowPolicy(
          acceptedState.occurrenceUid,
          acceptedState.occurrenceTimeoutSeconds
        )
        const policy = yield* Either.isLeft(validatedPolicy)
          ? Effect.fail(validatedPolicy.left)
          : Effect.succeed(validatedPolicy.right)
        const temporalReceipt = yield* workflow.readOneShotReceipt(acceptedState, policy)
        const completionReceipt = yield* completion.readCompletionReceipt(acceptedState)
        const validatedTemporal = Schema.decodeUnknownEither(G0ContentDescriptorSchema, {
          onExcessProperty: "error"
        })(temporalReceipt)
        const validatedCompletion = Schema.decodeUnknownEither(G0ContentDescriptorSchema, {
          onExcessProperty: "error"
        })(completionReceipt)
        if (
          Either.isLeft(validatedTemporal) ||
          Either.isLeft(validatedCompletion) ||
          validatedTemporal.right.name !== "temporal_terminal_audit_receipt" ||
          validatedCompletion.right.name !== "final_terminal_receipt" ||
          validatedTemporal.right.sha256 === validatedCompletion.right.sha256
        ) {
          return yield* Effect.fail(error(
            "PORT_RECEIPT_INVALID",
            "external terminal descriptors have an invalid shape, role, or digest collision"
          ))
        }
        return Object.freeze({
          workflow: freezeDescriptor(validatedTemporal.right),
          completion: freezeDescriptor(validatedCompletion.right)
        })
      })
    })
  })
)

/** Production default: external bindings are absent until an independent operator supplies them. */
export const G0DefaultBlockedExternalPortsLayer = Layer.merge(
  Layer.succeed(G0OneShotWorkflowReceiptPort, G0OneShotWorkflowReceiptPort.of({
    readOneShotReceipt: () => Effect.fail(error("PORT_BLOCKED", "no one-shot workflow receipt binding is installed"))
  })),
  Layer.succeed(G0IntegrityCompletionReceiptPort, G0IntegrityCompletionReceiptPort.of({
    readCompletionReceipt: () => Effect.fail(error("PORT_BLOCKED", "no integrity-completion binding is installed"))
  }))
)

/** @internal Explicitly test-only opaque descriptor fakes. They cannot execute an occurrence. */
export const makeG0TestOnlyMemoryPortsLayer = (
  temporalReceipts: ReadonlyMap<string, G0ContentDescriptor> = new Map(),
  completionReceipts: ReadonlyMap<string, G0ContentDescriptor> = new Map()
) => Layer.merge(
  Layer.succeed(G0OneShotWorkflowReceiptPort, G0OneShotWorkflowReceiptPort.of({
    readOneShotReceipt: (state) => {
      const value = temporalReceipts.get(state.occurrenceUid)
      return value === undefined
        ? Effect.fail(error("PORT_FAILED", "test-only Temporal receipt is absent"))
        : Effect.succeed(freezeDescriptor(value))
    }
  })),
  Layer.succeed(G0IntegrityCompletionReceiptPort, G0IntegrityCompletionReceiptPort.of({
    readCompletionReceipt: (state) => {
      const value = completionReceipts.get(state.occurrenceUid)
      return value === undefined
        ? Effect.fail(error("PORT_FAILED", "test-only completion receipt is absent"))
        : Effect.succeed(freezeDescriptor(value))
    }
  }))
)
