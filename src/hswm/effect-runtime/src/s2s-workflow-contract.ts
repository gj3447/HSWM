import { Either } from "effect"

import { canonicalS2SControlSha256 } from "./s2s-canonical.js"
import {
  S2S_ADJUDICATION_ARTIFACT_NAME,
  S2S_CANDIDATE_ARTIFACT_NAME,
  S2S_REGISTRATION_ARTIFACT_NAME
} from "./s2s-confirmatory.js"

/**
 * Pure, source-controlled identity contract for the future confirmatory
 * workflow. This module does not dispatch or inspect GitHub state.
 */
export const S2S_WORKFLOW_CONTRACT_SCHEMA_VERSION =
  "hswm-swm0w-s2s-workflow-contract/v1" as const

export const S2S_CONFIRMATORY_REPOSITORY = "gj3447/HSWM" as const
export const S2S_CONFIRMATORY_REF = "refs/heads/main" as const
export const S2S_CONFIRMATORY_BRANCH = "main" as const
export const S2S_CONFIRMATORY_EVENT = "push" as const
export const S2S_CONFIRMATORY_WORKFLOW_NAME =
  "SWM-0W-S2S confirmatory" as const
export const S2S_CONFIRMATORY_WORKFLOW_ID =
  "swm0w-s2s-confirmatory.yml" as const
export const S2S_CONFIRMATORY_WORKFLOW_PATH =
  `.github/workflows/${S2S_CONFIRMATORY_WORKFLOW_ID}` as const
export const S2S_CONFIRMATORY_PREREGISTRATION_PATH =
  "prereg/PREREG_SWM0W_S2S_GATE_V1.json" as const
export const S2S_CONFIRMATORY_WORKFLOW_REF =
  `${S2S_CONFIRMATORY_REPOSITORY}/${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_REF}` as const
export const S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT = 1 as const

export const S2S_CONFIRMATORY_JOB_STAGES = Object.freeze([
  "REGISTER",
  "CONFIRM",
  "ADJUDICATE"
] as const)

export type S2SConfirmatoryJobStage =
  (typeof S2S_CONFIRMATORY_JOB_STAGES)[number]

export const S2S_CONFIRMATORY_ARTIFACT_ROLES = Object.freeze([
  "REGISTRATION",
  "CANDIDATE",
  "ADJUDICATION"
] as const)

export type S2SConfirmatoryArtifactRole =
  (typeof S2S_CONFIRMATORY_ARTIFACT_ROLES)[number]

export const S2S_CONFIRMATORY_ARTIFACT_READ_OPERATIONS = Object.freeze([
  "CONFIRM_READ_REGISTRATION",
  "ADJUDICATE_READ_REGISTRATION",
  "ADJUDICATE_READ_CANDIDATE_FIRST",
  "ADJUDICATE_REREAD_CANDIDATE"
] as const)

export type S2SConfirmatoryArtifactReadOperation =
  (typeof S2S_CONFIRMATORY_ARTIFACT_READ_OPERATIONS)[number]

export interface S2SConfirmatoryArtifactReadContract {
  readonly operation: S2SConfirmatoryArtifactReadOperation
  readonly artifactRole: "REGISTRATION" | "CANDIDATE"
  readonly ordinalWithinStage: 1 | 2 | 3
  readonly maximumUses: 1
}

export interface S2SConfirmatoryStageContract {
  readonly stage: S2SConfirmatoryJobStage
  readonly jobId: "register" | "confirm" | "adjudicate"
  readonly jobName: "register" | "confirm" | "adjudicate"
  readonly producesArtifactRole: S2SConfirmatoryArtifactRole
  readonly producesArtifactName:
    | typeof S2S_REGISTRATION_ARTIFACT_NAME
    | typeof S2S_CANDIDATE_ARTIFACT_NAME
    | typeof S2S_ADJUDICATION_ARTIFACT_NAME
  readonly consumesArtifactRoles: ReadonlyArray<S2SConfirmatoryArtifactRole>
  readonly artifactReadOperations: ReadonlyArray<
    S2SConfirmatoryArtifactReadContract
  >
}

export const S2S_CONFIRMATORY_STAGE_CONTRACTS: Readonly<
  Record<S2SConfirmatoryJobStage, S2SConfirmatoryStageContract>
> = Object.freeze({
  REGISTER: Object.freeze({
    stage: "REGISTER",
    jobId: "register",
    jobName: "register",
    producesArtifactRole: "REGISTRATION",
    producesArtifactName: S2S_REGISTRATION_ARTIFACT_NAME,
    consumesArtifactRoles: Object.freeze([] as const),
    artifactReadOperations: Object.freeze([] as const)
  }),
  CONFIRM: Object.freeze({
    stage: "CONFIRM",
    jobId: "confirm",
    jobName: "confirm",
    producesArtifactRole: "CANDIDATE",
    producesArtifactName: S2S_CANDIDATE_ARTIFACT_NAME,
    consumesArtifactRoles: Object.freeze(["REGISTRATION"] as const),
    artifactReadOperations: Object.freeze([
      Object.freeze({
        operation: "CONFIRM_READ_REGISTRATION",
        artifactRole: "REGISTRATION",
        ordinalWithinStage: 1,
        maximumUses: 1
      })
    ] as const)
  }),
  ADJUDICATE: Object.freeze({
    stage: "ADJUDICATE",
    jobId: "adjudicate",
    jobName: "adjudicate",
    producesArtifactRole: "ADJUDICATION",
    producesArtifactName: S2S_ADJUDICATION_ARTIFACT_NAME,
    consumesArtifactRoles: Object.freeze([
      "REGISTRATION",
      "CANDIDATE"
    ] as const),
    artifactReadOperations: Object.freeze([
      Object.freeze({
        operation: "ADJUDICATE_READ_REGISTRATION",
        artifactRole: "REGISTRATION",
        ordinalWithinStage: 1,
        maximumUses: 1
      }),
      Object.freeze({
        operation: "ADJUDICATE_READ_CANDIDATE_FIRST",
        artifactRole: "CANDIDATE",
        ordinalWithinStage: 2,
        maximumUses: 1
      }),
      Object.freeze({
        operation: "ADJUDICATE_REREAD_CANDIDATE",
        artifactRole: "CANDIDATE",
        ordinalWithinStage: 3,
        maximumUses: 1
      })
    ] as const)
  })
})

export const S2S_CONFIRMATORY_JOB_IDS = Object.freeze([
  S2S_CONFIRMATORY_STAGE_CONTRACTS.REGISTER.jobId,
  S2S_CONFIRMATORY_STAGE_CONTRACTS.CONFIRM.jobId,
  S2S_CONFIRMATORY_STAGE_CONTRACTS.ADJUDICATE.jobId
] as const)

export type S2SConfirmatoryJobId =
  (typeof S2S_CONFIRMATORY_JOB_IDS)[number]

const WORKFLOW_CONTRACT_CORE = Object.freeze({
  schemaVersion: S2S_WORKFLOW_CONTRACT_SCHEMA_VERSION,
  repository: S2S_CONFIRMATORY_REPOSITORY,
  ref: S2S_CONFIRMATORY_REF,
  branch: S2S_CONFIRMATORY_BRANCH,
  event: S2S_CONFIRMATORY_EVENT,
  workflowName: S2S_CONFIRMATORY_WORKFLOW_NAME,
  workflowPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
  workflowRef: S2S_CONFIRMATORY_WORKFLOW_REF,
  workflowRunAttempt: S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT,
  preregistrationTriggerPath: S2S_CONFIRMATORY_PREREGISTRATION_PATH,
  sourceManifestWorkflowEntry: Object.freeze({
    path: S2S_CONFIRMATORY_WORKFLOW_PATH,
    mode: "100644" as const,
    objectType: "blob" as const,
    sha256Authority: "PINNED_REVIEWED_WORKFLOW_BYTES" as const,
    sha256Status: "OPEN_UNTIL_WORKFLOW_BYTES_EXIST" as const
  }),
  stages: Object.freeze(
    S2S_CONFIRMATORY_JOB_STAGES.map((stage) =>
      S2S_CONFIRMATORY_STAGE_CONTRACTS[stage]
    )
  )
})

export type S2SConfirmatoryWorkflowContractCore =
  typeof WORKFLOW_CONTRACT_CORE

export const S2S_CONFIRMATORY_WORKFLOW_CONTRACT = WORKFLOW_CONTRACT_CORE

export const s2sConfirmatoryWorkflowContractSha256 = (): Either.Either<
  string,
  import("./s2s-canonical.js").S2SCanonicalJsonError
> => canonicalS2SControlSha256(WORKFLOW_CONTRACT_CORE)

export const s2sStageForJobId = (
  input: unknown
): S2SConfirmatoryJobStage | undefined => {
  if (typeof input !== "string") return undefined
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    if (S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobId === input) return stage
  }
  return undefined
}

export const s2sArtifactRoleProducedByStage = (
  stage: S2SConfirmatoryJobStage
): S2SConfirmatoryArtifactRole =>
  S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].producesArtifactRole

export const s2sArtifactRoleMayBeConsumedByStage = (
  stage: S2SConfirmatoryJobStage,
  role: S2SConfirmatoryArtifactRole
): boolean =>
  S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].consumesArtifactRoles.includes(role)

export const s2sArtifactReadContract = (
  stage: S2SConfirmatoryJobStage,
  operation: unknown
): S2SConfirmatoryArtifactReadContract | undefined => {
  if (typeof operation !== "string") return undefined
  return S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].artifactReadOperations.find(
    (entry) => entry.operation === operation
  )
}
