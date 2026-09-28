/**
 * Task-independent instructions for an outcome-bound semantic revision.
 * This is a request contract, not an evaluator, optimizer, or efficacy claim.
 */
export const HSWM_SEMANTIC_REVISION_OBJECTIVE_V1 = "hswm-semantic-revision-objective/v1" as const

export interface SemanticRevisionObjectiveInput {
  readonly executionTraceSha256: string
  readonly outcomeSha256: string
}

export interface SemanticRevisionObjective {
  readonly contract: typeof HSWM_SEMANTIC_REVISION_OBJECTIVE_V1
  /** Content descriptors already present in the request; no environment label is copied here. */
  readonly boundEvidence: Readonly<SemanticRevisionObjectiveInput>
  readonly instructions: readonly string[]
  readonly claimCeiling: "DECLARED_REVISION_REQUEST_GUIDANCE_NOT_EVALUATION_CREDIT_OR_EFFICACY"
}

const instructions = Object.freeze([
  "Use only the bound execution trace, bound outcome, current semantic frame, and pinned role content to identify a condition contradicted by the observed outcome.",
  "The prior model prediction is an observation to explain, not ground truth.",
  "Revise only the smallest semantic portion supported by that evidence; preserve every typed role and every exception reference exactly.",
  "Retain or state uncertainty when the evidence does not determine a condition or revision.",
  "If the bound evidence does not warrant a semantic change, retain the same hypothesis instead of inventing an edit."
] as const)

/** Builds immutable guidance while leaving the bound trace and outcome as the request's authoritative records. */
export const buildSemanticRevisionObjective = (input: SemanticRevisionObjectiveInput): SemanticRevisionObjective =>
  Object.freeze({
    contract: HSWM_SEMANTIC_REVISION_OBJECTIVE_V1,
    boundEvidence: Object.freeze({ executionTraceSha256: input.executionTraceSha256, outcomeSha256: input.outcomeSha256 }),
    instructions,
    claimCeiling: "DECLARED_REVISION_REQUEST_GUIDANCE_NOT_EVALUATION_CREDIT_OR_EFFICACY"
  })
