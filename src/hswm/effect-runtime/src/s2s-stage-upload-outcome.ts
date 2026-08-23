import { Either, Schema } from "effect"
import type { ParseResult } from "effect"

export const S2S_STAGE_UPLOAD_OUTCOME_LITERALS = Object.freeze([
  "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED",
  "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
  "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
  "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
  "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
  "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH",
  "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED"
] as const)

export const S2SStageUploadOutcomeSchema = Schema.Literal(
  ...S2S_STAGE_UPLOAD_OUTCOME_LITERALS
)

export type S2SStageUploadOutcome = Schema.Schema.Type<
  typeof S2SStageUploadOutcomeSchema
>

export type S2SStageUploadHealthyOutcome =
  "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"

export type S2SStageUploadDefinitiveFailureOutcome =
  "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE"

export type S2SStageUploadReconciliationOutcome = Exclude<
  S2SStageUploadOutcome,
  S2SStageUploadHealthyOutcome | S2SStageUploadDefinitiveFailureOutcome
>

interface S2SStageUploadOutcomeClassificationBase {
  readonly authorityScope: "NON_AUTHORIZING_PURE_CLASSIFIER"
  readonly authorizationClaimed: false
  readonly implicitRetryAuthorized: false
  readonly externalExactlyOnceClaimed: false
}

export interface S2SStageUploadHealthyClassification
  extends S2SStageUploadOutcomeClassificationBase {
  readonly _tag: "Healthy"
  readonly outcome: S2SStageUploadHealthyOutcome
}

export interface S2SStageUploadDefinitiveFailureClassification
  extends S2SStageUploadOutcomeClassificationBase {
  readonly _tag: "DefinitiveFailure"
  readonly outcome: S2SStageUploadDefinitiveFailureOutcome
}

export interface S2SStageUploadReconciliationClassification
  extends S2SStageUploadOutcomeClassificationBase {
  readonly _tag: "ReconciliationRequired"
  readonly outcome: S2SStageUploadReconciliationOutcome
}

export type S2SStageUploadOutcomeClassification =
  | S2SStageUploadHealthyClassification
  | S2SStageUploadDefinitiveFailureClassification
  | S2SStageUploadReconciliationClassification

const baseClassification = Object.freeze({
  authorityScope: "NON_AUTHORIZING_PURE_CLASSIFIER" as const,
  authorizationClaimed: false as const,
  implicitRetryAuthorized: false as const,
  externalExactlyOnceClaimed: false as const
})

const healthyClassification: S2SStageUploadHealthyClassification =
  Object.freeze({
    _tag: "Healthy" as const,
    outcome:
      "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
    ...baseClassification
  })

const definitiveFailureClassification: S2SStageUploadDefinitiveFailureClassification =
  Object.freeze({
    _tag: "DefinitiveFailure" as const,
    outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
    ...baseClassification
  })

const reconciliationClassifications: Readonly<
  Record<
    S2SStageUploadReconciliationOutcome,
    S2SStageUploadReconciliationClassification
  >
> = Object.freeze({
  BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION: Object.freeze({
    _tag: "ReconciliationRequired" as const,
    outcome: "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION" as const,
    ...baseClassification
  }),
  DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY: Object.freeze({
    _tag: "ReconciliationRequired" as const,
    outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY" as const,
    ...baseClassification
  }),
  GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN: Object.freeze({
    _tag: "ReconciliationRequired" as const,
    outcome: "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN" as const,
    ...baseClassification
  }),
  EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH: Object.freeze({
    _tag: "ReconciliationRequired" as const,
    outcome: "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH" as const,
    ...baseClassification
  }),
  COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED: Object.freeze({
    _tag: "ReconciliationRequired" as const,
    outcome: "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED" as const,
    ...baseClassification
  })
})

export const decodeS2SStageUploadOutcome = Schema.decodeUnknownEither(
  S2SStageUploadOutcomeSchema,
  { onExcessProperty: "error" }
)

const classifyDecodedOutcome = (
  outcome: S2SStageUploadOutcome
): S2SStageUploadOutcomeClassification => {
  switch (outcome) {
    case "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED":
      return healthyClassification
    case "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE":
      return definitiveFailureClassification
    case "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION":
    case "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY":
    case "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN":
    case "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH":
    case "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED":
      return reconciliationClassifications[outcome]
  }
}

/**
 * Pure, non-authorizing classification of one exact frozen v16 outcome
 * literal. Objects, error records, evidence, and descriptive strings are not
 * classifier inputs and cannot confer a healthy result.
 */
export const classifyS2SStageUploadOutcome = (
  input: unknown
): Either.Either<
  S2SStageUploadOutcomeClassification,
  ParseResult.ParseError
> => {
  const decoded = decodeS2SStageUploadOutcome(input)
  return Either.isLeft(decoded)
    ? Either.left(decoded.left)
    : Either.right(classifyDecodedOutcome(decoded.right))
}
