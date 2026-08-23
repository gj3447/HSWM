import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import * as publicApi from "../src/index.js"
import { S2S_CONFIRMATORY_POLICY } from "../src/s2s-confirmatory.js"
import {
  S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION,
  S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
  validateS2SHostedProcessContinuityTimingContract
} from "../src/s2s-hosted-process-continuity-contract.js"

const expectReason = (
  input: unknown,
  reason: string,
  stage: "REGISTER" | "CONFIRM" | "ADJUDICATE" | null = null
): void => {
  const result = validateS2SHostedProcessContinuityTimingContract(input)
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) {
    expect(result.left).toMatchObject({ reason, stage })
  }
}

it("freezes one exact additive, whole-minute hosted timing candidate", () => {
  const result = validateS2SHostedProcessContinuityTimingContract(
    S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT
  )
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right).toBe(
      S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT
    )
  }
  expect(S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION).toBe(
    "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
  )
  expect(S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.sharedBudgets).toEqual({
    pinnedUploadMillis: 600_000,
    wholeAssertionMillis: 1_800_000,
    reconcileWaitFinalizationMillis: 600_000,
    explicitMarginMillis: 300_000
  })
  expect(S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages).toEqual({
    REGISTER: {
      stage: "REGISTER",
      preparationMillis: 1_200_000,
      requiredJobTimeoutMillis: 4_500_000,
      jobTimeoutMillis: 4_500_000,
      jobTimeoutMinutes: 75,
      withinHostedJobHardCap: true
    },
    CONFIRM: {
      stage: "CONFIRM",
      preparationMillis: 11_400_000,
      requiredJobTimeoutMillis: 14_700_000,
      jobTimeoutMillis: 14_700_000,
      jobTimeoutMinutes: 245,
      withinHostedJobHardCap: true
    },
    ADJUDICATE: {
      stage: "ADJUDICATE",
      preparationMillis: 1_200_000,
      requiredJobTimeoutMillis: 4_500_000,
      jobTimeoutMillis: 4_500_000,
      jobTimeoutMinutes: 75,
      withinHostedJobHardCap: true
    }
  })
  expect(S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.hostedJobHardCapMillis).toBe(
    21_600_000
  )
})

it("is deeply frozen and advances only a non-authorizing Pi candidate", () => {
  const contract = S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT
  expect(Object.isFrozen(contract)).toBe(true)
  expect(Object.isFrozen(contract.sharedBudgets)).toBe(true)
  expect(Object.isFrozen(contract.stages)).toBe(true)
  expect(
    Object.values(contract.stages).every((stage) => Object.isFrozen(stage))
  ).toBe(true)
  expect(Object.isFrozen(contract.claimBoundary)).toBe(true)
  expect(contract.classification).toBe(
    "REVIEWED_V1_AMENDMENT_CANDIDATE_TEST_ONLY_NON_AUTHORIZING"
  )
  expect(contract.claimBoundary).toEqual({
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

  expect(S2S_CONFIRMATORY_POLICY.deadlines).toMatchObject({
    registerJobTimeoutSeconds: 1_200,
    confirmCommandTimeoutSeconds: 11_400,
    confirmJobTimeoutSeconds: 12_600,
    adjudicationCommandTimeoutSeconds: 1_200,
    adjudicationJobTimeoutSeconds: 1_800
  })
})

it("rejects the wrong action pin and formula-consistent profile drift", () => {
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      pinnedUploadAction: "actions/upload-artifact@v4"
    },
    "PINNED_UPLOAD_ACTION_DRIFT"
  )

  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      sharedBudgets: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.sharedBudgets,
        pinnedUploadMillis: 660_000
      },
      stages: {
        REGISTER: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.REGISTER,
          requiredJobTimeoutMillis: 4_560_000,
          jobTimeoutMillis: 4_560_000,
          jobTimeoutMinutes: 76
        },
        CONFIRM: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.CONFIRM,
          requiredJobTimeoutMillis: 14_760_000,
          jobTimeoutMillis: 14_760_000,
          jobTimeoutMinutes: 246
        },
        ADJUDICATE: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.ADJUDICATE,
          requiredJobTimeoutMillis: 4_560_000,
          jobTimeoutMillis: 4_560_000,
          jobTimeoutMinutes: 76
        }
      }
    },
    "PROFILE_DRIFT",
    "REGISTER"
  )
})

it("rejects insufficient timeout separately from an inexact positive margin", () => {
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      stages: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages,
        REGISTER: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.REGISTER,
          jobTimeoutMillis: 4_199_999
        }
      }
    },
    "JOB_TIMEOUT_INSUFFICIENT",
    "REGISTER"
  )
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      stages: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages,
        REGISTER: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.REGISTER,
          jobTimeoutMillis: 4_499_999
        }
      }
    },
    "EXPLICIT_MARGIN_MISMATCH",
    "REGISTER"
  )
})

it("rejects unsafe additive overflow, fractional budgets, and non-minute totals", () => {
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      stages: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages,
        REGISTER: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.REGISTER,
          preparationMillis: Number.MAX_SAFE_INTEGER
        }
      }
    },
    "BUDGET_OVERFLOW",
    "REGISTER"
  )
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      sharedBudgets: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.sharedBudgets,
        pinnedUploadMillis: 600_000.5
      }
    },
    "NUMBER_INVALID"
  )
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      sharedBudgets: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.sharedBudgets,
        explicitMarginMillis: 300_001
      },
      stages: {
        REGISTER: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.REGISTER,
          requiredJobTimeoutMillis: 4_500_001,
          jobTimeoutMillis: 4_500_001
        },
        CONFIRM: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.CONFIRM,
          requiredJobTimeoutMillis: 14_700_001,
          jobTimeoutMillis: 14_700_001
        },
        ADJUDICATE: {
          ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages.ADJUDICATE,
          requiredJobTimeoutMillis: 4_500_001,
          jobTimeoutMillis: 4_500_001
        }
      }
    },
    "JOB_TIMEOUT_NOT_WHOLE_MINUTES",
    "REGISTER"
  )
})

it("rejects authorization drift and hostile surfaces without invoking accessors", () => {
  expectReason(
    {
      ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT,
      claimBoundary: {
        ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.claimBoundary,
        productionAuthorizationClaimed: true
      }
    },
    "CLAIM_BOUNDARY_DRIFT"
  )

  let reads = 0
  const accessor = {
    ...S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT
  }
  Object.defineProperty(accessor, "sharedBudgets", {
    enumerable: true,
    get: () => {
      reads += 1
      return S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.sharedBudgets
    }
  })
  expectReason(accessor, "SURFACE_INVALID")
  expect(reads).toBe(0)
})

it("keeps the timing amendment candidate out of the package root", () => {
  for (const key of [
    "S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT",
    "S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION",
    "validateS2SHostedProcessContinuityTimingContract"
  ]) {
    expect(key in publicApi).toBe(false)
  }
})
