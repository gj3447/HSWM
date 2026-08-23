import { isProxy } from "node:util/types"

import { Data, Either } from "effect"

import { S2S_PROCESS_MAX_TIMEOUT_MILLIS } from "./s2s-bounded-process.js"
import { S2S_STAGE_UPLOAD_ASSERTION_WHOLE_TIMEOUT_MILLIS } from "./s2s-stage-upload-assertion.js"
import {
  S2S_CONFIRMATORY_JOB_STAGES,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"

export const S2S_HOSTED_PROCESS_CONTINUITY_TIMING_SCHEMA_VERSION =
  "hswm-swm0w-s2s-hosted-process-continuity-timing-amendment-candidate/v1" as const

export const S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CLASSIFICATION =
  "REVIEWED_V1_AMENDMENT_CANDIDATE_TEST_ONLY_NON_AUTHORIZING" as const

export const S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION =
  "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f" as const

export const S2S_HOSTED_PROCESS_CONTINUITY_PREPARATION_BASIS =
  "EXISTING_BOUNDED_COMMAND_OR_WORK_BUDGET_NOT_OLD_JOB_TIMEOUT" as const

const MILLISECONDS_PER_MINUTE = 60_000
const REVIEWED_WHOLE_ASSERTION_MILLIS = 1_800_000
const REVIEWED_HOSTED_JOB_HARD_CAP_MILLIS = 21_600_000

export interface S2SHostedProcessContinuitySharedBudgets {
  readonly pinnedUploadMillis: number
  readonly wholeAssertionMillis: number
  readonly reconcileWaitFinalizationMillis: number
  readonly explicitMarginMillis: number
}

export interface S2SHostedProcessContinuityStageTiming {
  readonly stage: S2SConfirmatoryJobStage
  readonly preparationMillis: number
  readonly requiredJobTimeoutMillis: number
  readonly jobTimeoutMillis: number
  readonly jobTimeoutMinutes: number
  readonly withinHostedJobHardCap: true
}

export interface S2SHostedProcessContinuityClaimBoundary {
  readonly axis: "PI_OPERATIONAL_FEASIBILITY_ONLY"
  readonly hChanged: false
  readonly wChanged: false
  readonly aChanged: false
  readonly fChanged: false
  readonly piProductionPolicyChanged: false
  readonly amendmentCandidateDefined: true
  readonly s2sConfirmatoryPolicyMutated: false
  readonly testOnlyFeasibilityWorkflowDefined: true
  readonly productionWorkflowMutated: false
  readonly productionAuthorizationClaimed: false
  readonly scientificVerdictClaimed: false
  readonly causalLearningClaimed: false
}

export interface S2SHostedProcessContinuityTimingContract {
  readonly schemaVersion: typeof S2S_HOSTED_PROCESS_CONTINUITY_TIMING_SCHEMA_VERSION
  readonly classification: typeof S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CLASSIFICATION
  readonly pinnedUploadAction: typeof S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION
  readonly preparationBudgetBasis: typeof S2S_HOSTED_PROCESS_CONTINUITY_PREPARATION_BASIS
  readonly sharedBudgets: S2SHostedProcessContinuitySharedBudgets
  readonly stages: Readonly<
    Record<
      S2SConfirmatoryJobStage,
      S2SHostedProcessContinuityStageTiming
    >
  >
  readonly hostedJobHardCapMillis: number
  readonly claimBoundary: S2SHostedProcessContinuityClaimBoundary
}

const SHARED_BUDGETS: S2SHostedProcessContinuitySharedBudgets = Object.freeze({
  pinnedUploadMillis: 600_000,
  wholeAssertionMillis: REVIEWED_WHOLE_ASSERTION_MILLIS,
  reconcileWaitFinalizationMillis: 600_000,
  explicitMarginMillis: 300_000
})

const REGISTER_TIMING: S2SHostedProcessContinuityStageTiming = Object.freeze({
  stage: "REGISTER",
  preparationMillis: 1_200_000,
  requiredJobTimeoutMillis: 4_500_000,
  jobTimeoutMillis: 4_500_000,
  jobTimeoutMinutes: 75,
  withinHostedJobHardCap: true
})

const CONFIRM_TIMING: S2SHostedProcessContinuityStageTiming = Object.freeze({
  stage: "CONFIRM",
  preparationMillis: 11_400_000,
  requiredJobTimeoutMillis: 14_700_000,
  jobTimeoutMillis: 14_700_000,
  jobTimeoutMinutes: 245,
  withinHostedJobHardCap: true
})

const ADJUDICATE_TIMING: S2SHostedProcessContinuityStageTiming = Object.freeze({
  stage: "ADJUDICATE",
  preparationMillis: 1_200_000,
  requiredJobTimeoutMillis: 4_500_000,
  jobTimeoutMillis: 4_500_000,
  jobTimeoutMinutes: 75,
  withinHostedJobHardCap: true
})

const CLAIM_BOUNDARY: S2SHostedProcessContinuityClaimBoundary = Object.freeze({
  axis: "PI_OPERATIONAL_FEASIBILITY_ONLY",
  hChanged: false,
  wChanged: false,
  aChanged: false,
  fChanged: false,
  piProductionPolicyChanged: false,
  amendmentCandidateDefined: true,
  s2sConfirmatoryPolicyMutated: false,
  testOnlyFeasibilityWorkflowDefined: true,
  productionWorkflowMutated: false,
  productionAuthorizationClaimed: false,
  scientificVerdictClaimed: false,
  causalLearningClaimed: false
})

/**
 * Package-internal timing amendment candidate for hosted-process continuity
 * falsification. It is not a production workflow policy and confers no run,
 * upload, or scientific authority.
 */
export const S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT: S2SHostedProcessContinuityTimingContract =
  Object.freeze({
    schemaVersion: S2S_HOSTED_PROCESS_CONTINUITY_TIMING_SCHEMA_VERSION,
    classification: S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CLASSIFICATION,
    pinnedUploadAction: S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION,
    preparationBudgetBasis: S2S_HOSTED_PROCESS_CONTINUITY_PREPARATION_BASIS,
    sharedBudgets: SHARED_BUDGETS,
    stages: Object.freeze({
      REGISTER: REGISTER_TIMING,
      CONFIRM: CONFIRM_TIMING,
      ADJUDICATE: ADJUDICATE_TIMING
    }),
    hostedJobHardCapMillis: REVIEWED_HOSTED_JOB_HARD_CAP_MILLIS,
    claimBoundary: CLAIM_BOUNDARY
  })

export class S2SHostedProcessContinuityTimingError extends Data.TaggedError(
  "S2SHostedProcessContinuityTimingError"
)<{
  readonly reason:
    | "SURFACE_INVALID"
    | "NUMBER_INVALID"
    | "BUDGET_OVERFLOW"
    | "JOB_TIMEOUT_INSUFFICIENT"
    | "EXPLICIT_MARGIN_MISMATCH"
    | "JOB_TIMEOUT_NOT_WHOLE_MINUTES"
    | "HOSTED_JOB_HARD_CAP_EXCEEDED"
    | "FORMULA_DRIFT"
    | "PINNED_UPLOAD_ACTION_DRIFT"
    | "PROFILE_DRIFT"
    | "CLAIM_BOUNDARY_DRIFT"
  readonly phase: "SURFACE" | "BUDGET" | "FORMULA" | "PIN" | "CLAIM"
  readonly stage: S2SConfirmatoryJobStage | null
  readonly detail: string
}> {}

const timingError = (
  reason: S2SHostedProcessContinuityTimingError["reason"],
  phase: S2SHostedProcessContinuityTimingError["phase"],
  detail: string,
  stage: S2SConfirmatoryJobStage | null = null
): S2SHostedProcessContinuityTimingError =>
  new S2SHostedProcessContinuityTimingError({
    reason,
    phase,
    stage,
    detail
  })

type PlainRecordSnapshot = ReadonlyMap<string, unknown>

const snapshotExactPlainRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>,
  path: string
): Either.Either<
  PlainRecordSnapshot,
  S2SHostedProcessContinuityTimingError
> => {
  if (input === null || typeof input !== "object" || isProxy(input)) {
    return Either.left(
      timingError(
        "SURFACE_INVALID",
        "SURFACE",
        `${path} must be one non-proxy plain data object`
      )
    )
  }
  try {
    if (Object.getPrototypeOf(input) !== Object.prototype) {
      return Either.left(
        timingError(
          "SURFACE_INVALID",
          "SURFACE",
          `${path} must have Object.prototype`
        )
      )
    }
    const keys = Reflect.ownKeys(input)
    if (
      keys.length !== expectedKeys.length ||
      keys.some(
        (key) => typeof key !== "string" || !expectedKeys.includes(key)
      )
    ) {
      return Either.left(
        timingError(
          "SURFACE_INVALID",
          "SURFACE",
          `${path} has missing, excess, or symbol keys`
        )
      )
    }
    const values = new Map<string, unknown>()
    for (const key of expectedKeys) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor)
      ) {
        return Either.left(
          timingError(
            "SURFACE_INVALID",
            "SURFACE",
            `${path}.${key} must be an enumerable data property`
          )
        )
      }
      values.set(key, descriptor.value)
    }
    return Either.right(values)
  } catch {
    return Either.left(
      timingError(
        "SURFACE_INVALID",
        "SURFACE",
        `${path} could not be inspected safely`
      )
    )
  }
}

const decodeSafeNonNegativeInteger = (
  input: unknown,
  path: string,
  stage: S2SConfirmatoryJobStage | null = null
): Either.Either<number, S2SHostedProcessContinuityTimingError> =>
  typeof input === "number" && Number.isSafeInteger(input) && input >= 0
    ? Either.right(input)
    : Either.left(
        timingError(
          "NUMBER_INVALID",
          "BUDGET",
          `${path} must be a non-negative safe integer`,
          stage
        )
      )

const addBudgets = (
  values: ReadonlyArray<number>,
  stage: S2SConfirmatoryJobStage
): Either.Either<number, S2SHostedProcessContinuityTimingError> => {
  let total = 0
  for (const value of values) {
    if (value > Number.MAX_SAFE_INTEGER - total) {
      return Either.left(
        timingError(
          "BUDGET_OVERFLOW",
          "FORMULA",
          "additive timing budget exceeds the safe-integer range",
          stage
        )
      )
    }
    total += value
  }
  return Either.right(total)
}

const ROOT_KEYS = Object.freeze([
  "schemaVersion",
  "classification",
  "pinnedUploadAction",
  "preparationBudgetBasis",
  "sharedBudgets",
  "stages",
  "hostedJobHardCapMillis",
  "claimBoundary"
] as const)

const SHARED_BUDGET_KEYS = Object.freeze([
  "pinnedUploadMillis",
  "wholeAssertionMillis",
  "reconcileWaitFinalizationMillis",
  "explicitMarginMillis"
] as const)

const STAGE_KEYS = Object.freeze([
  "stage",
  "preparationMillis",
  "requiredJobTimeoutMillis",
  "jobTimeoutMillis",
  "jobTimeoutMinutes",
  "withinHostedJobHardCap"
] as const)

const CLAIM_KEYS = Object.freeze([
  "axis",
  "hChanged",
  "wChanged",
  "aChanged",
  "fChanged",
  "piProductionPolicyChanged",
  "amendmentCandidateDefined",
  "s2sConfirmatoryPolicyMutated",
  "testOnlyFeasibilityWorkflowDefined",
  "productionWorkflowMutated",
  "productionAuthorizationClaimed",
  "scientificVerdictClaimed",
  "causalLearningClaimed"
] as const)

const EXPECTED_PREPARATION_MILLIS: Readonly<
  Record<S2SConfirmatoryJobStage, number>
> = Object.freeze({
  REGISTER: 1_200_000,
  CONFIRM: 11_400_000,
  ADJUDICATE: 1_200_000
})

const EXPECTED_JOB_TIMEOUT_MILLIS: Readonly<
  Record<S2SConfirmatoryJobStage, number>
> = Object.freeze({
  REGISTER: 4_500_000,
  CONFIRM: 14_700_000,
  ADJUDICATE: 4_500_000
})

const EXPECTED_JOB_TIMEOUT_MINUTES: Readonly<
  Record<S2SConfirmatoryJobStage, number>
> = Object.freeze({
  REGISTER: 75,
  CONFIRM: 245,
  ADJUDICATE: 75
})

/**
 * Pure fail-closed validation of the reviewed v1 candidate. A successful
 * result is the deeply frozen canonical contract, never caller-owned data.
 */
export const validateS2SHostedProcessContinuityTimingContract = (
  input: unknown
): Either.Either<
  S2SHostedProcessContinuityTimingContract,
  S2SHostedProcessContinuityTimingError
> => {
  const root = snapshotExactPlainRecord(input, ROOT_KEYS, "contract")
  if (Either.isLeft(root)) return Either.left(root.left)

  if (
    root.right.get("schemaVersion") !==
      S2S_HOSTED_PROCESS_CONTINUITY_TIMING_SCHEMA_VERSION ||
    root.right.get("classification") !==
      S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CLASSIFICATION ||
    root.right.get("preparationBudgetBasis") !==
      S2S_HOSTED_PROCESS_CONTINUITY_PREPARATION_BASIS
  ) {
    return Either.left(
      timingError(
        "PROFILE_DRIFT",
        "PIN",
        "schema, classification, or preparation-budget basis drifted"
      )
    )
  }
  if (
    root.right.get("pinnedUploadAction") !==
    S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION
  ) {
    return Either.left(
      timingError(
        "PINNED_UPLOAD_ACTION_DRIFT",
        "PIN",
        "upload action is not the exact reviewed commit pin"
      )
    )
  }

  const shared = snapshotExactPlainRecord(
    root.right.get("sharedBudgets"),
    SHARED_BUDGET_KEYS,
    "contract.sharedBudgets"
  )
  if (Either.isLeft(shared)) return Either.left(shared.left)
  const pinnedUploadMillis = decodeSafeNonNegativeInteger(
    shared.right.get("pinnedUploadMillis"),
    "contract.sharedBudgets.pinnedUploadMillis"
  )
  if (Either.isLeft(pinnedUploadMillis)) {
    return Either.left(pinnedUploadMillis.left)
  }
  const wholeAssertionMillis = decodeSafeNonNegativeInteger(
    shared.right.get("wholeAssertionMillis"),
    "contract.sharedBudgets.wholeAssertionMillis"
  )
  if (Either.isLeft(wholeAssertionMillis)) {
    return Either.left(wholeAssertionMillis.left)
  }
  const reconcileWaitFinalizationMillis = decodeSafeNonNegativeInteger(
    shared.right.get("reconcileWaitFinalizationMillis"),
    "contract.sharedBudgets.reconcileWaitFinalizationMillis"
  )
  if (Either.isLeft(reconcileWaitFinalizationMillis)) {
    return Either.left(reconcileWaitFinalizationMillis.left)
  }
  const explicitMarginMillis = decodeSafeNonNegativeInteger(
    shared.right.get("explicitMarginMillis"),
    "contract.sharedBudgets.explicitMarginMillis"
  )
  if (Either.isLeft(explicitMarginMillis)) {
    return Either.left(explicitMarginMillis.left)
  }

  const hostedJobHardCapMillis = decodeSafeNonNegativeInteger(
    root.right.get("hostedJobHardCapMillis"),
    "contract.hostedJobHardCapMillis"
  )
  if (Either.isLeft(hostedJobHardCapMillis)) {
    return Either.left(hostedJobHardCapMillis.left)
  }

  const stages = snapshotExactPlainRecord(
    root.right.get("stages"),
    S2S_CONFIRMATORY_JOB_STAGES,
    "contract.stages"
  )
  if (Either.isLeft(stages)) return Either.left(stages.left)

  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    const timing = snapshotExactPlainRecord(
      stages.right.get(stage),
      STAGE_KEYS,
      `contract.stages.${stage}`
    )
    if (Either.isLeft(timing)) return Either.left(timing.left)
    if (timing.right.get("stage") !== stage) {
      return Either.left(
        timingError(
          "PROFILE_DRIFT",
          "PIN",
          "stage identity drifted",
          stage
        )
      )
    }
    const preparationMillis = decodeSafeNonNegativeInteger(
      timing.right.get("preparationMillis"),
      `contract.stages.${stage}.preparationMillis`,
      stage
    )
    if (Either.isLeft(preparationMillis)) {
      return Either.left(preparationMillis.left)
    }
    const requiredJobTimeoutMillis = decodeSafeNonNegativeInteger(
      timing.right.get("requiredJobTimeoutMillis"),
      `contract.stages.${stage}.requiredJobTimeoutMillis`,
      stage
    )
    if (Either.isLeft(requiredJobTimeoutMillis)) {
      return Either.left(requiredJobTimeoutMillis.left)
    }
    const jobTimeoutMillis = decodeSafeNonNegativeInteger(
      timing.right.get("jobTimeoutMillis"),
      `contract.stages.${stage}.jobTimeoutMillis`,
      stage
    )
    if (Either.isLeft(jobTimeoutMillis)) {
      return Either.left(jobTimeoutMillis.left)
    }
    const jobTimeoutMinutes = decodeSafeNonNegativeInteger(
      timing.right.get("jobTimeoutMinutes"),
      `contract.stages.${stage}.jobTimeoutMinutes`,
      stage
    )
    if (Either.isLeft(jobTimeoutMinutes)) {
      return Either.left(jobTimeoutMinutes.left)
    }

    const nonMarginTotal = addBudgets(
      [
        preparationMillis.right,
        pinnedUploadMillis.right,
        wholeAssertionMillis.right,
        reconcileWaitFinalizationMillis.right
      ],
      stage
    )
    if (Either.isLeft(nonMarginTotal)) {
      return Either.left(nonMarginTotal.left)
    }
    const requiredTotal = addBudgets(
      [nonMarginTotal.right, explicitMarginMillis.right],
      stage
    )
    if (Either.isLeft(requiredTotal)) {
      return Either.left(requiredTotal.left)
    }

    if (requiredJobTimeoutMillis.right !== requiredTotal.right) {
      return Either.left(
        timingError(
          "FORMULA_DRIFT",
          "FORMULA",
          "required timeout is not the exact additive component total",
          stage
        )
      )
    }
    if (jobTimeoutMillis.right < nonMarginTotal.right) {
      return Either.left(
        timingError(
          "JOB_TIMEOUT_INSUFFICIENT",
          "FORMULA",
          "job timeout cannot contain even the non-margin components",
          stage
        )
      )
    }
    if (
      jobTimeoutMillis.right - nonMarginTotal.right !==
      explicitMarginMillis.right
    ) {
      return Either.left(
        timingError(
          "EXPLICIT_MARGIN_MISMATCH",
          "FORMULA",
          "job timeout does not leave exactly the declared margin",
          stage
        )
      )
    }
    if (
      jobTimeoutMillis.right % MILLISECONDS_PER_MINUTE !== 0 ||
      jobTimeoutMinutes.right !==
        jobTimeoutMillis.right / MILLISECONDS_PER_MINUTE
    ) {
      return Either.left(
        timingError(
          "JOB_TIMEOUT_NOT_WHOLE_MINUTES",
          "FORMULA",
          "job timeout must project to the exact declared integer minutes",
          stage
        )
      )
    }
    if (jobTimeoutMillis.right > hostedJobHardCapMillis.right) {
      return Either.left(
        timingError(
          "HOSTED_JOB_HARD_CAP_EXCEEDED",
          "FORMULA",
          "job timeout exceeds the hosted-job hard cap",
          stage
        )
      )
    }
    if (timing.right.get("withinHostedJobHardCap") !== true) {
      return Either.left(
        timingError(
          "FORMULA_DRIFT",
          "FORMULA",
          "feasibility marker disagrees with the validated timeout",
          stage
        )
      )
    }
    if (
      preparationMillis.right !== EXPECTED_PREPARATION_MILLIS[stage] ||
      requiredJobTimeoutMillis.right !==
        EXPECTED_JOB_TIMEOUT_MILLIS[stage] ||
      jobTimeoutMillis.right !== EXPECTED_JOB_TIMEOUT_MILLIS[stage] ||
      jobTimeoutMinutes.right !== EXPECTED_JOB_TIMEOUT_MINUTES[stage]
    ) {
      return Either.left(
        timingError(
          "PROFILE_DRIFT",
          "PIN",
          "stage timing differs from the reviewed v1 amendment candidate",
          stage
        )
      )
    }
  }

  if (
    pinnedUploadMillis.right !== 600_000 ||
    wholeAssertionMillis.right !== REVIEWED_WHOLE_ASSERTION_MILLIS ||
    reconcileWaitFinalizationMillis.right !== 600_000 ||
    explicitMarginMillis.right !== 300_000 ||
    hostedJobHardCapMillis.right !== REVIEWED_HOSTED_JOB_HARD_CAP_MILLIS
  ) {
    return Either.left(
      timingError(
        "PROFILE_DRIFT",
        "PIN",
        "shared timing components differ from the reviewed v1 candidate"
      )
    )
  }

  const claim = snapshotExactPlainRecord(
    root.right.get("claimBoundary"),
    CLAIM_KEYS,
    "contract.claimBoundary"
  )
  if (Either.isLeft(claim)) return Either.left(claim.left)
  if (
    claim.right.get("axis") !== "PI_OPERATIONAL_FEASIBILITY_ONLY" ||
    claim.right.get("hChanged") !== false ||
    claim.right.get("wChanged") !== false ||
    claim.right.get("aChanged") !== false ||
    claim.right.get("fChanged") !== false ||
    claim.right.get("piProductionPolicyChanged") !== false ||
    claim.right.get("amendmentCandidateDefined") !== true ||
    claim.right.get("s2sConfirmatoryPolicyMutated") !== false ||
    claim.right.get("testOnlyFeasibilityWorkflowDefined") !== true ||
    claim.right.get("productionWorkflowMutated") !== false ||
    claim.right.get("productionAuthorizationClaimed") !== false ||
    claim.right.get("scientificVerdictClaimed") !== false ||
    claim.right.get("causalLearningClaimed") !== false
  ) {
    return Either.left(
      timingError(
        "CLAIM_BOUNDARY_DRIFT",
        "CLAIM",
        "H/W/A/F, Pi, authorization, or scientific claim boundary drifted"
      )
    )
  }

  return Either.right(S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT)
}

if (
  S2S_STAGE_UPLOAD_ASSERTION_WHOLE_TIMEOUT_MILLIS !==
    REVIEWED_WHOLE_ASSERTION_MILLIS ||
  S2S_PROCESS_MAX_TIMEOUT_MILLIS !== REVIEWED_HOSTED_JOB_HARD_CAP_MILLIS ||
  Either.isLeft(
    validateS2SHostedProcessContinuityTimingContract(
      S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT
    )
  )
) {
  throw new Error(
    "S2S hosted-process continuity timing amendment candidate drifted"
  )
}
