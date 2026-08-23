import {
  S2S_ADJUDICATION_ARCHIVE_EXACT_MEMBERS,
  S2S_CONFIRMATORY_POLICY,
  S2S_REGISTRATION_ARCHIVE_EXACT_MEMBERS
} from "./s2s-confirmatory.js"
import { S2S_NUMERIC_ADJUDICATION_MAX_BYTES } from "./s2s-resource-limits.js"
import {
  S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION
} from "./s2s-stage-upload-postcondition-contract.js"
import {
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  type S2SConfirmatoryArtifactRole,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"
import type { S2SExpectedZipMember } from "./s2s-zip.js"

const MEBIBYTE = 1_048_576
const POSTCONDITION_MAX_BYTES = 16_777_216 as const

interface S2SStageArtifactStaticSpecByStage {
  readonly REGISTER: {
    readonly archiveLogicalName: "upload/registration_archive.zip"
    readonly archiveProfileRole: "REGISTRATION_UPLOAD_ARCHIVE"
    readonly postconditionLogicalName: "upload/registration_postcondition.zip"
    readonly postconditionProfileRole: "REGISTRATION_UPLOAD_POSTCONDITION"
    readonly carrierSchemaVersion: "hswm-swm0w-s2s-registration-carrier/v1"
  }
  readonly CONFIRM: {
    readonly archiveLogicalName: "upload/candidate_archive.zip"
    readonly archiveProfileRole: "CANDIDATE_UPLOAD_ARCHIVE"
    readonly postconditionLogicalName: "upload/candidate_postcondition.zip"
    readonly postconditionProfileRole: "CANDIDATE_UPLOAD_POSTCONDITION"
    readonly carrierSchemaVersion: "hswm-swm0w-s2s-candidate-carrier/v1"
  }
  readonly ADJUDICATE: {
    readonly archiveLogicalName: "upload/adjudication_archive.zip"
    readonly archiveProfileRole: "ADJUDICATION_UPLOAD_ARCHIVE"
    readonly postconditionLogicalName: "upload/adjudication_postcondition.zip"
    readonly postconditionProfileRole: "ADJUDICATION_UPLOAD_POSTCONDITION"
    readonly carrierSchemaVersion: "hswm-swm0w-s2s-adjudication-carrier/v1"
  }
}

type S2SStageArtifactStaticSpec =
  S2SStageArtifactStaticSpecByStage[S2SConfirmatoryJobStage]

export type S2SStageArtifactArchiveLogicalName =
  S2SStageArtifactStaticSpec["archiveLogicalName"]
export type S2SStageArtifactPostconditionLogicalName =
  S2SStageArtifactStaticSpec["postconditionLogicalName"]
export type S2SStageArtifactArchiveProfileRole =
  S2SStageArtifactStaticSpec["archiveProfileRole"]
export type S2SStageArtifactPostconditionProfileRole =
  S2SStageArtifactStaticSpec["postconditionProfileRole"]
export type S2SStageArtifactCarrierSchemaVersion =
  S2SStageArtifactStaticSpec["carrierSchemaVersion"]

export interface S2SStageArtifactSpecForStage<
  Stage extends S2SConfirmatoryJobStage
> {
  readonly stage: Stage
  readonly role: (typeof S2S_CONFIRMATORY_STAGE_CONTRACTS)[Stage]["producesArtifactRole"]
  readonly jobId: (typeof S2S_CONFIRMATORY_STAGE_CONTRACTS)[Stage]["jobId"]
  readonly jobName: (typeof S2S_CONFIRMATORY_STAGE_CONTRACTS)[Stage]["jobName"]
  readonly artifactName: (typeof S2S_CONFIRMATORY_STAGE_CONTRACTS)[Stage]["producesArtifactName"]
  readonly archiveLogicalName: S2SStageArtifactStaticSpecByStage[Stage]["archiveLogicalName"]
  readonly archiveProfileRole: S2SStageArtifactStaticSpecByStage[Stage]["archiveProfileRole"]
  readonly postconditionLogicalName: S2SStageArtifactStaticSpecByStage[Stage]["postconditionLogicalName"]
  readonly postconditionProfileRole: S2SStageArtifactStaticSpecByStage[Stage]["postconditionProfileRole"]
  readonly carrierSchemaVersion: S2SStageArtifactStaticSpecByStage[Stage]["carrierSchemaVersion"]
  readonly postconditionSchemaVersion: typeof S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION
  readonly maximumArchiveBytes: number
  readonly maximumExpandedBytes: number
  readonly postconditionCarrierMaximumBytes: number
  readonly postconditionProfileMaximumBytes: 16_777_216
  readonly expectedMembers: ReadonlyArray<S2SExpectedZipMember>
}

export type S2SStageArtifactSpec = {
  readonly [Stage in S2SConfirmatoryJobStage]: S2SStageArtifactSpecForStage<Stage>
}[S2SConfirmatoryJobStage]

const spec = <const Stage extends S2SConfirmatoryJobStage>(
  input: Omit<
    S2SStageArtifactSpecForStage<Stage>,
    | "jobId"
    | "jobName"
    | "role"
    | "artifactName"
    | "postconditionSchemaVersion"
    | "postconditionCarrierMaximumBytes"
    | "postconditionProfileMaximumBytes"
  >
): S2SStageArtifactSpecForStage<Stage> => {
  const contract = S2S_CONFIRMATORY_STAGE_CONTRACTS[input.stage]
  return Object.freeze({
    ...input,
    role: contract.producesArtifactRole,
    jobId: contract.jobId,
    jobName: contract.jobName,
    artifactName: contract.producesArtifactName,
    postconditionSchemaVersion:
      S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
    postconditionCarrierMaximumBytes:
      S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
    postconditionProfileMaximumBytes: POSTCONDITION_MAX_BYTES,
    expectedMembers: Object.freeze(
      input.expectedMembers.map((member) => Object.freeze({ ...member }))
    )
  })
}

export const S2S_STAGE_ARTIFACT_SPECS = Object.freeze({
  REGISTER: spec({
    stage: "REGISTER",
    archiveLogicalName: "upload/registration_archive.zip",
    archiveProfileRole: "REGISTRATION_UPLOAD_ARCHIVE",
    postconditionLogicalName: "upload/registration_postcondition.zip",
    postconditionProfileRole: "REGISTRATION_UPLOAD_POSTCONDITION",
    carrierSchemaVersion: "hswm-swm0w-s2s-registration-carrier/v1",
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    expectedMembers: S2S_REGISTRATION_ARCHIVE_EXACT_MEMBERS.map((name) => ({
      name,
      maximumBytes: MEBIBYTE
    }))
  }),
  CONFIRM: spec({
    stage: "CONFIRM",
    archiveLogicalName: "upload/candidate_archive.zip",
    archiveProfileRole: "CANDIDATE_UPLOAD_ARCHIVE",
    postconditionLogicalName: "upload/candidate_postcondition.zip",
    postconditionProfileRole: "CANDIDATE_UPLOAD_POSTCONDITION",
    carrierSchemaVersion: "hswm-swm0w-s2s-candidate-carrier/v1",
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes,
    expectedMembers: S2S_CONFIRMATORY_POLICY.candidateArchive.exactMembers.map(
      (name) => ({
        name,
        maximumBytes:
          name === "control_receipt.json"
            ? MEBIBYTE
            : S2S_CONFIRMATORY_POLICY.archive.candidateMemberMaximumBytes
      })
    )
  }),
  ADJUDICATE: spec({
    stage: "ADJUDICATE",
    archiveLogicalName: "upload/adjudication_archive.zip",
    archiveProfileRole: "ADJUDICATION_UPLOAD_ARCHIVE",
    postconditionLogicalName: "upload/adjudication_postcondition.zip",
    postconditionProfileRole: "ADJUDICATION_UPLOAD_POSTCONDITION",
    carrierSchemaVersion: "hswm-swm0w-s2s-adjudication-carrier/v1",
    maximumArchiveBytes:
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
    maximumExpandedBytes:
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
    expectedMembers: S2S_ADJUDICATION_ARCHIVE_EXACT_MEMBERS.map((name) => ({
      name,
      maximumBytes:
        name === "control_receipt.json"
          ? MEBIBYTE
          : S2S_NUMERIC_ADJUDICATION_MAX_BYTES
    }))
  })
}) satisfies Readonly<{
  readonly [Stage in S2SConfirmatoryJobStage]: S2SStageArtifactSpecForStage<Stage>
}>

export const s2sStageArtifactSpecForRole = (
  role: S2SConfirmatoryArtifactRole
): S2SStageArtifactSpec => {
  switch (role) {
    case "REGISTRATION":
      return S2S_STAGE_ARTIFACT_SPECS.REGISTER
    case "CANDIDATE":
      return S2S_STAGE_ARTIFACT_SPECS.CONFIRM
    case "ADJUDICATION":
      return S2S_STAGE_ARTIFACT_SPECS.ADJUDICATE
  }
}
