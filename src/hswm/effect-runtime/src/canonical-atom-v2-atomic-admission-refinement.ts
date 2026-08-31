import { Data, Either, Schema } from "effect"

import type { CanonicalAtomV2CurrentStatePermitResolution } from "./canonical-atom-v2-current-state-permit.js"
import type { Dnrd5V2TwoCasAdmitConfirmed } from "./canonical-atom-v2-dnrd5-durable-permit.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import type { CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle } from "./canonical-atom-v2-outcome-judgment.js"

/**
 * Exact read-only projection of the separately bounded checked-in contracts
 * onto the Lean atomic-admission obligations. It cannot compose those
 * contracts, issue Permit, validate Inv, mutate state, or invoke learning.
 */
export const HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION =
  "hswm-canonical-atomic-admission-refinement/v1" as const
export const HSWM_CANONICAL_ATOMIC_ADMISSION_LEAN_BOUNDARY =
  "HSWM.CanonicalLearning.AtomicAdmission.AtomicLearnAdmission/v1" as const

const SOURCE_OUTCOME_BUNDLE_STATUS:
  CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle["bundleStatus"] =
    "STRUCTURALLY_BOUND_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
const SOURCE_GENERIC_PERMIT_CAPABILITY:
  CanonicalAtomV2CurrentStatePermitResolution["capability"] =
    "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
const SOURCE_GENERIC_PERMIT_ADMISSION:
  CanonicalAtomV2CurrentStatePermitResolution["admission"] =
    "NOT_ADMITTED_BY_THIS_RESOLUTION"
const SOURCE_DNRD_TWO_CAS_TERMINAL:
  Dnrd5V2TwoCasAdmitConfirmed["terminal"] =
    "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"

export type CanonicalAtomV2AtomicAdmissionPresentBoundary =
  | "OWNER_BOUND_OUTCOME_SHAPE_PRESENT"
  | "DNRD5_TWO_CAS_HISTORY_BOUNDARY_PRESENT"

export type CanonicalAtomV2AtomicAdmissionBlockingObligation =
  | "OUTCOME_SUPPORT_WITNESS_NOT_ESTABLISHED"
  | "CANONICAL_PERMIT_AT_LINEARIZATION_NOT_ESTABLISHED"
  | "EXACT_TRANSITION_INVARIANT_WITNESS_NOT_ESTABLISHED"
  | "SAME_TRANSITION_COMPOSITION_NOT_ESTABLISHED"
  | "ATOMIC_ADMISSION_RUNTIME_MAPPING_NOT_ESTABLISHED"

export interface CanonicalAtomV2AtomicAdmissionRefinementProfile {
  readonly _tag: "CanonicalAtomV2AtomicAdmissionRefinementProfile"
  readonly contractVersion: typeof HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION
  readonly leanBoundary: typeof HSWM_CANONICAL_ATOMIC_ADMISSION_LEAN_BOUNDARY
  readonly sourceSemantics: {
    readonly outcomeBundleStatus: CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle["bundleStatus"]
    readonly genericPermitCapability: CanonicalAtomV2CurrentStatePermitResolution["capability"]
    readonly genericPermitAdmission: CanonicalAtomV2CurrentStatePermitResolution["admission"]
    readonly dnrdTwoCasTerminal: Dnrd5V2TwoCasAdmitConfirmed["terminal"]
  }
  readonly presentBoundaries: ReadonlyArray<CanonicalAtomV2AtomicAdmissionPresentBoundary>
  readonly blockingObligations: ReadonlyArray<CanonicalAtomV2AtomicAdmissionBlockingObligation>
  readonly verdict: "BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION"
  readonly scientificStatus: "SCIENTIFIC_UNJUDGED"
}

const PresentBoundarySchema = Schema.Literal(
  "OWNER_BOUND_OUTCOME_SHAPE_PRESENT",
  "DNRD5_TWO_CAS_HISTORY_BOUNDARY_PRESENT"
)

const BlockingObligationSchema = Schema.Literal(
  "OUTCOME_SUPPORT_WITNESS_NOT_ESTABLISHED",
  "CANONICAL_PERMIT_AT_LINEARIZATION_NOT_ESTABLISHED",
  "EXACT_TRANSITION_INVARIANT_WITNESS_NOT_ESTABLISHED",
  "SAME_TRANSITION_COMPOSITION_NOT_ESTABLISHED",
  "ATOMIC_ADMISSION_RUNTIME_MAPPING_NOT_ESTABLISHED"
)

const CanonicalAtomV2AtomicAdmissionRefinementProfileSchema:
  Schema.Schema<CanonicalAtomV2AtomicAdmissionRefinementProfile> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2AtomicAdmissionRefinementProfile"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION
    ),
    leanBoundary: Schema.Literal(
      HSWM_CANONICAL_ATOMIC_ADMISSION_LEAN_BOUNDARY
    ),
    sourceSemantics: Schema.Struct({
      outcomeBundleStatus: Schema.Literal(
        "STRUCTURALLY_BOUND_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
      ),
      genericPermitCapability: Schema.Literal(
        "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
      ),
      genericPermitAdmission: Schema.Literal(
        "NOT_ADMITTED_BY_THIS_RESOLUTION"
      ),
      dnrdTwoCasTerminal: Schema.Literal(
        "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
      )
    }),
    presentBoundaries: Schema.Array(PresentBoundarySchema).pipe(
      Schema.minItems(2),
      Schema.maxItems(2)
    ),
    blockingObligations: Schema.Array(BlockingObligationSchema).pipe(
      Schema.minItems(5),
      Schema.maxItems(5)
    ),
    verdict: Schema.Literal(
      "BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION"
    ),
    scientificStatus: Schema.Literal("SCIENTIFIC_UNJUDGED")
  })

const PRESENT_BOUNDARIES:
  ReadonlyArray<CanonicalAtomV2AtomicAdmissionPresentBoundary> = Object.freeze([
    "OWNER_BOUND_OUTCOME_SHAPE_PRESENT",
    "DNRD5_TWO_CAS_HISTORY_BOUNDARY_PRESENT"
  ] as const)

const BLOCKING_OBLIGATIONS:
  ReadonlyArray<CanonicalAtomV2AtomicAdmissionBlockingObligation> =
  Object.freeze([
    "OUTCOME_SUPPORT_WITNESS_NOT_ESTABLISHED",
    "CANONICAL_PERMIT_AT_LINEARIZATION_NOT_ESTABLISHED",
    "EXACT_TRANSITION_INVARIANT_WITNESS_NOT_ESTABLISHED",
    "SAME_TRANSITION_COMPOSITION_NOT_ESTABLISHED",
    "ATOMIC_ADMISSION_RUNTIME_MAPPING_NOT_ESTABLISHED"
  ] as const)

const PROFILE: CanonicalAtomV2AtomicAdmissionRefinementProfile = Object.freeze({
  _tag: "CanonicalAtomV2AtomicAdmissionRefinementProfile",
  contractVersion:
    HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION,
  leanBoundary: HSWM_CANONICAL_ATOMIC_ADMISSION_LEAN_BOUNDARY,
  sourceSemantics: Object.freeze({
    outcomeBundleStatus: SOURCE_OUTCOME_BUNDLE_STATUS,
    genericPermitCapability: SOURCE_GENERIC_PERMIT_CAPABILITY,
    genericPermitAdmission: SOURCE_GENERIC_PERMIT_ADMISSION,
    dnrdTwoCasTerminal: SOURCE_DNRD_TWO_CAS_TERMINAL
  }),
  presentBoundaries: PRESENT_BOUNDARIES,
  blockingObligations: BLOCKING_OBLIGATIONS,
  verdict: "BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION",
  scientificStatus: "SCIENTIFIC_UNJUDGED"
})

export class CanonicalAtomV2AtomicAdmissionRefinementError extends Data.TaggedError(
  "CanonicalAtomV2AtomicAdmissionRefinementError"
)<{
  readonly code: "CANONICAL_ENCODING_INVALID" | "PROFILE_MISMATCH"
  readonly detail: string
}> {}

const fail = (
  code: CanonicalAtomV2AtomicAdmissionRefinementError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2AtomicAdmissionRefinementError> =>
  Either.left(
    new CanonicalAtomV2AtomicAdmissionRefinementError({ code, detail })
  )

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

/** Immutable exact obstruction profile; no caller input can promote it. */
export const canonicalAtomV2AtomicAdmissionRefinementProfile =
  (): CanonicalAtomV2AtomicAdmissionRefinementProfile => PROFILE

export const canonicalAtomV2AtomicAdmissionRefinementProfileBytes =
  (): Either.Either<
    Uint8Array,
    CanonicalAtomV2AtomicAdmissionRefinementError
  > => {
    const bytes = canonicalJsonBytes(PROFILE)
    return Either.isLeft(bytes)
      ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
      : Either.right(Uint8Array.from(bytes.right))
  }

/** Accepts only the exact canonical checked-in obstruction profile. */
export const decodeCanonicalAtomV2AtomicAdmissionRefinementProfileBytes = (
  input: Uint8Array
): Either.Either<
  CanonicalAtomV2AtomicAdmissionRefinementProfile,
  CanonicalAtomV2AtomicAdmissionRefinementError
> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = Schema.decodeUnknownEither(
    CanonicalAtomV2AtomicAdmissionRefinementProfileSchema,
    { onExcessProperty: "error" }
  )(parsed.right)
  if (Either.isLeft(checked)) {
    return fail(
      "PROFILE_MISMATCH",
      "profile does not satisfy the exact atomic-admission obstruction schema"
    )
  }
  const expected = canonicalAtomV2AtomicAdmissionRefinementProfileBytes()
  if (Either.isLeft(expected)) return Either.left(expected.left)
  return sameBytes(input, expected.right)
    ? Either.right(PROFILE)
    : fail(
        "PROFILE_MISMATCH",
        "profile bytes differ from the exact checked-in obstruction"
      )
}
