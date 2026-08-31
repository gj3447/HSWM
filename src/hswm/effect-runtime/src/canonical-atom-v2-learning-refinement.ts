import { Data, Either, Schema } from "effect"

import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import type { CanonicalAtomV2CurrentStatePermitResolution } from "./canonical-atom-v2-current-state-permit.js"
import type { CanonicalAtomV2OutcomeObservationEvidence } from "./canonical-atom-v2-transition-evidence.js"

/**
 * Exact fail-closed projection of the checked-in TypeScript v1 semantics onto
 * the Lean canonical-learning obligations. It reports an obstruction only; it
 * cannot issue Permit, assign causal credit, admit state, or invoke learning.
 */
export const HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION =
  "hswm-canonical-learning-refinement/v1" as const
export const HSWM_CANONICAL_LEARNING_REFINEMENT_LEAN_BOUNDARY =
  "HSWM.CanonicalLearning.Learn/v1" as const

const SOURCE_PERMIT_CAPABILITY:
  CanonicalAtomV2CurrentStatePermitResolution["capability"] =
    "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
const SOURCE_PERMIT_ADMISSION:
  CanonicalAtomV2CurrentStatePermitResolution["admission"] =
    "NOT_ADMITTED_BY_THIS_RESOLUTION"
const SOURCE_PERMIT_LEARNING:
  CanonicalAtomV2CurrentStatePermitResolution["learning"] =
    "NOT_CAUSAL_CREDIT_NOT_LEARNING"
const SOURCE_OUTCOME_STATUS:
  CanonicalAtomV2OutcomeObservationEvidence["outcomeStatus"] =
    "REPRESENTED_NOT_CAUSAL_CREDIT"

export type CanonicalAtomV2LearningMappedObligation =
  | "SCHEMA_RELATIVE_ADDRESS_FIELDS_REPRESENTED"
  | "CANONICAL_JSON_CONTENT_DESCRIPTORS_AVAILABLE"
  | "PRE_OUTCOME_TRACE_BINDING_REPRESENTED"
  | "EXACT_LOCAL_SNAPSHOT_BINDING_AVAILABLE"

export type CanonicalAtomV2LearningBlockingObligation =
  | "TRUSTED_CURRENT_HEAD_NOT_ESTABLISHED"
  | "EXACT_ONE_TARGET_CURRENT_REVISION_NOT_ESTABLISHED"
  | "EVALUATOR_INDEPENDENCE_NOT_PROVEN"
  | "OUTCOME_RESPONSIBILITY_OWNER_MISSING"
  | "OUTCOME_SUPPORTS_REVISION_MISSING"
  | "CANONICAL_PERMIT_MISSING"
  | "SCHEMA_INVARIANT_WITNESS_MISSING"
  | "ATOMIC_ADMISSION_MISSING"

export interface CanonicalAtomV2LearningRefinementProfile {
  readonly _tag: "CanonicalAtomV2LearningRefinementProfile"
  readonly contractVersion: typeof HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION
  readonly leanBoundary: typeof HSWM_CANONICAL_LEARNING_REFINEMENT_LEAN_BOUNDARY
  readonly sourceSemantics: {
    readonly permitCapability: CanonicalAtomV2CurrentStatePermitResolution["capability"]
    readonly permitAdmission: CanonicalAtomV2CurrentStatePermitResolution["admission"]
    readonly permitLearning: CanonicalAtomV2CurrentStatePermitResolution["learning"]
    readonly outcomeStatus: CanonicalAtomV2OutcomeObservationEvidence["outcomeStatus"]
  }
  readonly mappedObligations: ReadonlyArray<CanonicalAtomV2LearningMappedObligation>
  readonly blockingObligations: ReadonlyArray<CanonicalAtomV2LearningBlockingObligation>
  readonly verdict: "BLOCKED_NOT_REFINED_TO_LEAN_LEARN"
  readonly scientificStatus: "SCIENTIFIC_UNJUDGED"
}

const MappedObligationSchema = Schema.Literal(
  "SCHEMA_RELATIVE_ADDRESS_FIELDS_REPRESENTED",
  "CANONICAL_JSON_CONTENT_DESCRIPTORS_AVAILABLE",
  "PRE_OUTCOME_TRACE_BINDING_REPRESENTED",
  "EXACT_LOCAL_SNAPSHOT_BINDING_AVAILABLE"
)

const BlockingObligationSchema = Schema.Literal(
  "TRUSTED_CURRENT_HEAD_NOT_ESTABLISHED",
  "EXACT_ONE_TARGET_CURRENT_REVISION_NOT_ESTABLISHED",
  "EVALUATOR_INDEPENDENCE_NOT_PROVEN",
  "OUTCOME_RESPONSIBILITY_OWNER_MISSING",
  "OUTCOME_SUPPORTS_REVISION_MISSING",
  "CANONICAL_PERMIT_MISSING",
  "SCHEMA_INVARIANT_WITNESS_MISSING",
  "ATOMIC_ADMISSION_MISSING"
)

const CanonicalAtomV2LearningRefinementProfileSchema: Schema.Schema<CanonicalAtomV2LearningRefinementProfile> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalAtomV2LearningRefinementProfile"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION
    ),
    leanBoundary: Schema.Literal(
      HSWM_CANONICAL_LEARNING_REFINEMENT_LEAN_BOUNDARY
    ),
    sourceSemantics: Schema.Struct({
      permitCapability: Schema.Literal(
        "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
      ),
      permitAdmission: Schema.Literal("NOT_ADMITTED_BY_THIS_RESOLUTION"),
      permitLearning: Schema.Literal("NOT_CAUSAL_CREDIT_NOT_LEARNING"),
      outcomeStatus: Schema.Literal("REPRESENTED_NOT_CAUSAL_CREDIT")
    }),
    mappedObligations: Schema.Array(MappedObligationSchema).pipe(
      Schema.minItems(4),
      Schema.maxItems(4)
    ),
    blockingObligations: Schema.Array(BlockingObligationSchema).pipe(
      Schema.minItems(8),
      Schema.maxItems(8)
    ),
    verdict: Schema.Literal("BLOCKED_NOT_REFINED_TO_LEAN_LEARN"),
    scientificStatus: Schema.Literal("SCIENTIFIC_UNJUDGED")
  })

const MAPPED_OBLIGATIONS: ReadonlyArray<CanonicalAtomV2LearningMappedObligation> =
  Object.freeze([
    "SCHEMA_RELATIVE_ADDRESS_FIELDS_REPRESENTED",
    "CANONICAL_JSON_CONTENT_DESCRIPTORS_AVAILABLE",
    "PRE_OUTCOME_TRACE_BINDING_REPRESENTED",
    "EXACT_LOCAL_SNAPSHOT_BINDING_AVAILABLE"
  ] as const)

const BLOCKING_OBLIGATIONS: ReadonlyArray<CanonicalAtomV2LearningBlockingObligation> =
  Object.freeze([
    "TRUSTED_CURRENT_HEAD_NOT_ESTABLISHED",
    "EXACT_ONE_TARGET_CURRENT_REVISION_NOT_ESTABLISHED",
    "EVALUATOR_INDEPENDENCE_NOT_PROVEN",
    "OUTCOME_RESPONSIBILITY_OWNER_MISSING",
    "OUTCOME_SUPPORTS_REVISION_MISSING",
    "CANONICAL_PERMIT_MISSING",
    "SCHEMA_INVARIANT_WITNESS_MISSING",
    "ATOMIC_ADMISSION_MISSING"
  ] as const)

const PROFILE: CanonicalAtomV2LearningRefinementProfile = Object.freeze({
  _tag: "CanonicalAtomV2LearningRefinementProfile",
  contractVersion: HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION,
  leanBoundary: HSWM_CANONICAL_LEARNING_REFINEMENT_LEAN_BOUNDARY,
  sourceSemantics: Object.freeze({
    permitCapability: SOURCE_PERMIT_CAPABILITY,
    permitAdmission: SOURCE_PERMIT_ADMISSION,
    permitLearning: SOURCE_PERMIT_LEARNING,
    outcomeStatus: SOURCE_OUTCOME_STATUS
  }),
  mappedObligations: MAPPED_OBLIGATIONS,
  blockingObligations: BLOCKING_OBLIGATIONS,
  verdict: "BLOCKED_NOT_REFINED_TO_LEAN_LEARN",
  scientificStatus: "SCIENTIFIC_UNJUDGED"
})

export class CanonicalAtomV2LearningRefinementError extends Data.TaggedError(
  "CanonicalAtomV2LearningRefinementError"
)<{
  readonly code: "CANONICAL_ENCODING_INVALID" | "PROFILE_MISMATCH"
  readonly detail: string
}> {}

const fail = (
  code: CanonicalAtomV2LearningRefinementError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2LearningRefinementError> =>
  Either.left(new CanonicalAtomV2LearningRefinementError({ code, detail }))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

/** Immutable exact semantic profile; no caller-supplied fact can promote it. */
export const canonicalAtomV2LearningRefinementProfile =
  (): CanonicalAtomV2LearningRefinementProfile => PROFILE

export const canonicalAtomV2LearningRefinementProfileBytes =
  (): Either.Either<Uint8Array, CanonicalAtomV2LearningRefinementError> => {
    const bytes = canonicalJsonBytes(PROFILE)
    return Either.isLeft(bytes)
      ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
      : Either.right(Uint8Array.from(bytes.right))
  }

/** Accepts only the one exact canonical profile, including blocker order. */
export const decodeCanonicalAtomV2LearningRefinementProfileBytes = (
  input: Uint8Array
): Either.Either<
  CanonicalAtomV2LearningRefinementProfile,
  CanonicalAtomV2LearningRefinementError
> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = Schema.decodeUnknownEither(
    CanonicalAtomV2LearningRefinementProfileSchema,
    { onExcessProperty: "error" }
  )(parsed.right)
  if (Either.isLeft(checked)) {
    return fail(
      "PROFILE_MISMATCH",
      "profile does not satisfy the exact v1 refinement-obstruction schema"
    )
  }
  const expected = canonicalAtomV2LearningRefinementProfileBytes()
  if (Either.isLeft(expected)) return Either.left(expected.left)
  return sameBytes(input, expected.right)
    ? Either.right(PROFILE)
    : fail(
        "PROFILE_MISMATCH",
        "profile bytes differ from the exact checked-in v1 obstruction"
      )
}
