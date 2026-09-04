/**
 * Deterministic, descriptor-only G0 operator simulation for tests.
 *
 * This module makes no network, filesystem, clock, credential, endpoint, or
 * private-material call. It is not an external operator, qualification,
 * Temporal execution, receipt verifier, scientific occurrence, or G0 result.
 * Keep it root-private: production callers must not import it through index.
 */
import { Data, Either, Schema } from "effect"

import {
  G0ContentDescriptorSchema,
  advanceG0Occurrence,
  registeredG0Occurrence,
  type G0ContentDescriptor,
  type G0OccurrenceState,
  type G0PulseTiming
} from "./g0-occurrence-phase-kernel.js"

export const HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_V1 =
  "hswm-g0-test-only-operator-simulation/v1" as const
export const HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION =
  "TEST_ONLY_NON_QUALIFYING_NON_AUTHORIZING" as const

const IdentifierSchema = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z][A-Za-z0-9._:-]{0,127}(?![\s\S])/)
)
const TimeoutSchema = Schema.Number.pipe(Schema.int(), Schema.between(1, 86_400))
const SimulationScenarioSchema = Schema.Literal(
  "HAPPY_PATH",
  "DUPLICATE_RETRY",
  "INVALID_PHASE_ORDER"
)

const SimulationInputSchema = Schema.Struct({
  occurrenceUid: IdentifierSchema,
  occurrenceTimeoutSeconds: TimeoutSchema,
  existingOccurrenceUids: Schema.Array(IdentifierSchema),
  simulatedOperatorId: IdentifierSchema,
  simulatedCustodianId: IdentifierSchema,
  scenario: SimulationScenarioSchema,
  wormClaimReceipt: G0ContentDescriptorSchema,
  registrationEvidence: G0ContentDescriptorSchema,
  scheduledEvidence: G0ContentDescriptorSchema,
  prePulseSealEvidence: G0ContentDescriptorSchema,
  pulseVerificationEvidence: G0ContentDescriptorSchema,
  revealEvidence: G0ContentDescriptorSchema,
  dualEvaluationEvidence: G0ContentDescriptorSchema,
  sealEvidence: G0ContentDescriptorSchema,
  temporalTerminalAuditReceipt: G0ContentDescriptorSchema,
  finalTerminalReceipt: G0ContentDescriptorSchema
})

export type G0TestOnlyOperatorSimulationInput = Schema.Schema.Type<
  typeof SimulationInputSchema
>

export class G0TestOnlyOperatorSimulationError extends Data.TaggedError(
  "G0TestOnlyOperatorSimulationError"
)<{
  readonly reason:
    | "INPUT_INVALID"
    | "DUPLICATE_UID"
    | "ROLE_SEPARATION_INVALID"
    | "DESCRIPTOR_SEPARATION_INVALID"
    | "KERNEL_REJECTED"
  readonly detail: string
}> {}

export interface G0TestOnlySyntheticReceipt {
  readonly classification: typeof HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION
  readonly occurrenceUid: string
  readonly descriptor: G0ContentDescriptor
  readonly productionReceiptCompatible: false
}

export interface G0TestOnlyOperatorSimulationTranscript {
  readonly schemaVersion: typeof HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_V1
  readonly classification: typeof HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION
  readonly occurrenceUid: string
  readonly simulatedOperatorId: string
  readonly simulatedCustodianId: string
  readonly scenario: "HAPPY_PATH" | "DUPLICATE_RETRY" | "INVALID_PHASE_ORDER"
  readonly states: ReadonlyArray<G0OccurrenceState>
  readonly simulatedTerminalWorkflowReceipt: G0TestOnlySyntheticReceipt | null
  readonly simulatedFinalTerminalReceipt: G0TestOnlySyntheticReceipt | null
  readonly externalQualificationClaimed: false
  readonly externalExecutionClaimed: false
  readonly scientificEvidenceClaimed: false
  readonly g0Passed: false
  readonly publicationEligible: false
}

const simulationError = (
  reason: G0TestOnlyOperatorSimulationError["reason"],
  detail: string
): G0TestOnlyOperatorSimulationError =>
  new G0TestOnlyOperatorSimulationError({ reason, detail })

const freezeDescriptor = (descriptor: G0ContentDescriptor): G0ContentDescriptor =>
  Object.freeze({ ...descriptor })

const isPlainRecord = (value: unknown): value is Readonly<Record<string, unknown>> => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value) as unknown
  return prototype === Object.prototype || prototype === null
}

const exactInput = (
  input: unknown
): Either.Either<G0TestOnlyOperatorSimulationInput, G0TestOnlyOperatorSimulationError> => {
  try {
    if (!isPlainRecord(input)) {
      return Either.left(simulationError("INPUT_INVALID", "simulation input must be a plain descriptor-only object"))
    }
    const descriptorFields = [
      "wormClaimReceipt", "registrationEvidence", "scheduledEvidence",
      "prePulseSealEvidence", "pulseVerificationEvidence", "revealEvidence",
      "dualEvaluationEvidence", "sealEvidence", "temporalTerminalAuditReceipt",
      "finalTerminalReceipt"
    ]
    if (descriptorFields.some((field) => !isPlainRecord(input[field]))) {
      return Either.left(simulationError("INPUT_INVALID", "simulation descriptors must be plain objects"))
    }
    const decoded = Schema.decodeUnknownEither(SimulationInputSchema, {
      onExcessProperty: "error"
    })(input)
    return Either.isLeft(decoded)
      ? Either.left(simulationError("INPUT_INVALID", "simulation input is not an exact descriptor-only shape"))
      : Either.right(decoded.right)
  } catch {
    return Either.left(simulationError("INPUT_INVALID", "simulation input could not be inspected safely"))
  }
}

const hasUniqueDigests = (descriptors: ReadonlyArray<G0ContentDescriptor>): boolean =>
  new Set(descriptors.map((descriptor) => descriptor.sha256)).size === descriptors.length

const expectedDescriptorRoles = (
  input: G0TestOnlyOperatorSimulationInput
): boolean =>
  input.wormClaimReceipt.name === "candidate_worm_claim_receipt" &&
  input.registrationEvidence.name === "registration_evidence" &&
  input.scheduledEvidence.name === "scheduled_evidence" &&
  input.prePulseSealEvidence.name === "pre_pulse_seal_evidence" &&
  input.pulseVerificationEvidence.name === "pulse_verification_evidence" &&
  input.revealEvidence.name === "reveal_evidence" &&
  input.dualEvaluationEvidence.name === "dual_evaluation_evidence" &&
  input.sealEvidence.name === "seal_evidence" &&
  input.temporalTerminalAuditReceipt.name === "temporal_terminal_audit_receipt" &&
  input.finalTerminalReceipt.name === "final_terminal_receipt"

const advance = (
  state: G0OccurrenceState,
  nextPhase: "CLAIMED" | "SCHEDULED" | "PRE_PULSE_SEALED" | "PULSE_VERIFIED" | "REVEALED" | "DUAL_EVALUATED" | "SEALED",
  evidence: G0ContentDescriptor,
  timing: G0PulseTiming
): Either.Either<G0OccurrenceState, G0TestOnlyOperatorSimulationError> => {
  const result = advanceG0Occurrence(state, Object.freeze({ nextPhase, evidence, timing }))
  return Either.isLeft(result)
    ? Either.left(simulationError("KERNEL_REJECTED", result.left.detail))
    : Either.right(result.right)
}

const freezeTranscript = (
  input: G0TestOnlyOperatorSimulationInput,
  states: ReadonlyArray<G0OccurrenceState>,
  receipts: Readonly<{ workflow: G0ContentDescriptor | null; completion: G0ContentDescriptor | null }>
): G0TestOnlyOperatorSimulationTranscript =>
  Object.freeze({
    schemaVersion: HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_V1,
    classification: HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION,
    occurrenceUid: input.occurrenceUid,
    simulatedOperatorId: input.simulatedOperatorId,
    simulatedCustodianId: input.simulatedCustodianId,
    scenario: input.scenario,
    states: Object.freeze([...states]),
    simulatedTerminalWorkflowReceipt: receipts.workflow === null
      ? null
      : Object.freeze({
        classification: HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION,
        occurrenceUid: input.occurrenceUid,
        descriptor: freezeDescriptor(receipts.workflow),
        productionReceiptCompatible: false as const
      }),
    simulatedFinalTerminalReceipt: receipts.completion === null
      ? null
      : Object.freeze({
        classification: HSWM_G0_TEST_ONLY_OPERATOR_SIMULATION_CLASSIFICATION,
        occurrenceUid: input.occurrenceUid,
        descriptor: freezeDescriptor(receipts.completion),
        productionReceiptCompatible: false as const
      }),
    externalQualificationClaimed: false,
    externalExecutionClaimed: false,
    scientificEvidenceClaimed: false,
    g0Passed: false,
    publicationEligible: false
  })

/**
 * Runs only a pure, deterministic test fixture against the phase reducer.
 * A returned SEALED label is a local simulated state, never a G0 claim.
 */
export const simulateG0TestOnlyOperator = (
  rawInput: unknown
): Either.Either<G0TestOnlyOperatorSimulationTranscript, G0TestOnlyOperatorSimulationError> => {
  const decoded = exactInput(rawInput)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const input = decoded.right
  if (input.existingOccurrenceUids.includes(input.occurrenceUid)) {
    return Either.left(simulationError("DUPLICATE_UID", "simulated UID was already observed; no replacement is allowed"))
  }
  if (input.simulatedOperatorId === input.simulatedCustodianId) {
    return Either.left(simulationError("ROLE_SEPARATION_INVALID", "simulated operator and custodian identities must differ"))
  }
  const allDescriptors = [
    input.wormClaimReceipt, input.registrationEvidence, input.scheduledEvidence,
    input.prePulseSealEvidence, input.pulseVerificationEvidence, input.revealEvidence,
    input.dualEvaluationEvidence, input.sealEvidence, input.temporalTerminalAuditReceipt,
    input.finalTerminalReceipt
  ]
  if (!expectedDescriptorRoles(input) || !hasUniqueDigests(allDescriptors)) {
    return Either.left(simulationError(
      "DESCRIPTOR_SEPARATION_INVALID",
      "simulated descriptor roles must be exact and every digest must be role-separated"
    ))
  }
  const registered = registeredG0Occurrence(
    input.occurrenceUid,
    input.registrationEvidence.sha256,
    input.occurrenceTimeoutSeconds
  )
  if (Either.isLeft(registered)) return Either.left(simulationError("KERNEL_REJECTED", registered.left.detail))
  const states: G0OccurrenceState[] = [registered.right]
  const claim = advance(registered.right, "CLAIMED", input.wormClaimReceipt, "PRE_PULSE")
  if (Either.isLeft(claim)) return Either.left(claim.left)
  states.push(claim.right)

  if (input.scenario === "DUPLICATE_RETRY") {
    const duplicate = advance(claim.right, "CLAIMED", input.scheduledEvidence, "PRE_PULSE")
    if (Either.isLeft(duplicate)) return Either.left(duplicate.left)
    states.push(duplicate.right)
    return Either.right(freezeTranscript(input, states, { workflow: null, completion: null }))
  }
  if (input.scenario === "INVALID_PHASE_ORDER") {
    const invalid = advance(claim.right, "REVEALED", input.scheduledEvidence, "POST_PULSE")
    if (Either.isLeft(invalid)) return Either.left(invalid.left)
    states.push(invalid.right)
    return Either.right(freezeTranscript(input, states, { workflow: null, completion: null }))
  }

  const steps: ReadonlyArray<readonly [
    "SCHEDULED" | "PRE_PULSE_SEALED" | "PULSE_VERIFIED" | "REVEALED" | "DUAL_EVALUATED" | "SEALED",
    G0ContentDescriptor,
    G0PulseTiming
  ]> = [
    ["SCHEDULED", input.scheduledEvidence, "PRE_PULSE"],
    ["PRE_PULSE_SEALED", input.prePulseSealEvidence, "PRE_PULSE"],
    ["PULSE_VERIFIED", input.pulseVerificationEvidence, "POST_PULSE"],
    ["REVEALED", input.revealEvidence, "POST_PULSE"],
    ["DUAL_EVALUATED", input.dualEvaluationEvidence, "POST_PULSE"],
    ["SEALED", input.sealEvidence, "POST_PULSE"]
  ]
  for (const [nextPhase, evidence, timing] of steps) {
    const next = advance(states.at(-1) as G0OccurrenceState, nextPhase, evidence, timing)
    if (Either.isLeft(next)) return Either.left(next.left)
    states.push(next.right)
  }
  return Either.right(freezeTranscript(input, states, {
    workflow: input.temporalTerminalAuditReceipt,
    completion: input.finalTerminalReceipt
  }))
}
